"""PlanSearch — Cork County Council ePlan Scraper.

Scrapes planning applications from planning.corkcoco.ie/ePlan.
Cork County Council is the only major ROI council missing from NPAD.

Two modes:
- Continuous: POST to searchresults with 7-day window, run every 6 hours
- Backfill: enumerate refs (YY/NNNNN) and fetch detail pages directly

The ePlan portal uses POST requests with CSRF tokens. It only supports
fixed time windows (7, 14, 28, 35, 42 days), not arbitrary date ranges.

Rate limiting: 2s between requests.
Geocoding: Cork records have no coordinates — the geocoder picks them up.

Data licence: LGMA public planning register.
"""

import asyncio
import logging
import re
from datetime import datetime, date, timedelta, timezone
from typing import Optional

import httpx
from bs4 import BeautifulSoup
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.database import engine
from app.utils.text_clean import clean_text

logger = logging.getLogger(__name__)

# ── Constants ────────────────────────────────────────────────────────────

EPLAN_BASE = "https://planning.corkcoco.ie/ePlan"
LISTING_URL = f"{EPLAN_BASE}/SearchListing/RECEIVED"
SEARCH_RESULTS_URL = f"{EPLAN_BASE}/searchresults"
DETAIL_URL_TPL = f"{EPLAN_BASE}/AppFileRefDetails/{{internal_id}}/0"

USER_AGENT = "PlanSearch/1.0 (+https://plansearch.cc; planning research)"
RATE_LIMIT_SECONDS = 2.0

# ePlan only supports these fixed windows (days from today)
VALID_TIME_LIMITS = [7, 14, 28, 35, 42]

# ── Progress tracker ─────────────────────────────────────────────────────

cork_scraper_progress = {
    "running": False,
    "mode": None,  # "continuous" or "backfill"
    "scraped_today": 0,
    "records_found_today": 0,
    "last_ref": None,
    "current_window": None,
    "windows_done": 0,
    "total_windows": 0,
    "started_at": None,
    "error": None,
    "backfill_year": None,
    "backfill_ref_num": None,
}


# ── CSRF + POST listing ────────────────────────────────────────────────

async def get_csrf_token(client: httpx.AsyncClient) -> Optional[str]:
    """GET the listing page to extract the CSRF token."""
    resp = await client.get(
        LISTING_URL,
        headers={"User-Agent": USER_AGENT},
        follow_redirects=True,
        timeout=30.0,
    )
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")

    # CSRF token is in the second form on the page (the listing form)
    forms = soup.find_all("form")
    for form in reversed(forms):  # Try last form first (listing form)
        token_input = form.find("input", {"name": "__RequestVerificationToken"})
        if token_input:
            return token_input["value"]

    # Fallback: search entire page
    token_input = soup.find("input", {"name": "__RequestVerificationToken"})
    if token_input:
        return token_input["value"]

    return None


async def fetch_listing_page(
    client: httpx.AsyncClient,
    app_status: str,
    time_limit: int,
    csrf_token: str,
) -> str:
    """POST to /ePlan/searchresults to get listings.

    app_status: "0" = Received, "1" = Decided, "2" = Due
    time_limit: 7, 14, 28, 35, or 42 (days from today)
    """
    form_data = {
        "__RequestVerificationToken": csrf_token,
        "AppStatus": app_status,
        "CheckBoxList[0].Id": "0",
        "CheckBoxList[0].Name": "Cork County Council",
        "CheckBoxList[0].IsSelected": "true",
        "RdoTimeLimit": str(time_limit),
        "SearchType": "Listing",
        "CountyTownCount": "1",
    }

    resp = await client.post(
        SEARCH_RESULTS_URL,
        data=form_data,
        headers={
            "User-Agent": USER_AGENT,
            "Referer": LISTING_URL,
        },
        follow_redirects=True,
        timeout=60.0,
    )
    resp.raise_for_status()
    return resp.text


# ── HTML parsing ─────────────────────────────────────────────────────────

def parse_listing_html(html: str) -> list[dict]:
    """Parse Cork ePlan listing/search results page.

    The table has columns:
    0: File Number (internal ID, linked)
    1: Application Status
    2: Decision Due Date
    3: Decision Date
    4: Decision Code
    5: Received Date
    6: Applicant Name
    7: Development Address
    8: Development Description
    9: Local Authority Name
    """
    soup = BeautifulSoup(html, "html.parser")
    records = []

    # Try class-based table first, then any table
    table = soup.find("table", {"class": "tablesorter"}) or soup.find("table")
    if not table:
        return records

    rows = table.find_all("tr")
    for row in rows:
        cells = row.find_all("td")
        if len(cells) < 4:
            continue

        link = cells[0].find("a")
        if not link:
            continue

        href = link.get("href", "")
        file_ref = link.get_text(strip=True)
        internal_id = None

        id_match = re.search(r"/AppFileRefDetails/(\d+)/", href)
        if id_match:
            internal_id = int(id_match.group(1))

        if not internal_id and not file_ref:
            continue

        record = {
            "file_ref": file_ref,
            "internal_id": internal_id,
            "application_status": cells[1].get_text(strip=True) if len(cells) > 1 else None,
            "decision_due_date": cells[2].get_text(strip=True) if len(cells) > 2 else None,
            "decision_date": cells[3].get_text(strip=True) if len(cells) > 3 else None,
            "decision_code": cells[4].get_text(strip=True) if len(cells) > 4 else None,
            "received_date": cells[5].get_text(strip=True) if len(cells) > 5 else None,
            "applicant_name": cells[6].get_text(strip=True) if len(cells) > 6 else None,
            "address": cells[7].get_text(" ", strip=True) if len(cells) > 7 else None,
            "description": cells[8].get_text(" ", strip=True) if len(cells) > 8 else None,
        }
        records.append(record)

    return records


def parse_detail_page(html: str) -> Optional[dict]:
    """Parse a single Cork ePlan detail page (AppFileRefDetails).

    Used by backfill mode to scrape individual applications by ref.
    """
    soup = BeautifulSoup(html, "html.parser")

    # Check it's not an error/empty page
    title = soup.find("title")
    if title and "error" in title.get_text(strip=True).lower():
        return None

    # Look for the application details — typically in definition lists or tables
    record = {}

    # Try to find the file reference from the breadcrumb or heading
    heading = soup.find("h2") or soup.find("h1")
    if heading:
        heading_text = heading.get_text(strip=True)
        # Heading typically contains the ref like "25/12345"
        ref_match = re.search(r"(\d{2}/\d{3,6})", heading_text)
        if ref_match:
            record["file_ref"] = ref_match.group(1)

    # Extract from detail row pairs (label + value)
    # Cork ePlan uses various structures — try multiple approaches
    detail_rows = soup.find_all("div", {"class": "row"})
    for row in detail_rows:
        label_el = row.find("label") or row.find(class_=re.compile(r"label|field-name", re.I))
        value_el = row.find("span") or row.find("p") or row.find(class_=re.compile(r"value|field-value", re.I))
        if not label_el or not value_el:
            continue

        label = label_el.get_text(strip=True).lower()
        value = value_el.get_text(strip=True)

        if not value or value in ("N/A", ""):
            continue

        if "file number" in label or "file ref" in label:
            record["file_ref"] = value
        elif "applicant" in label:
            record["applicant_name"] = value
        elif "address" in label or "location" in label:
            record["address"] = value
        elif "description" in label or "proposal" in label or "development" in label:
            record["description"] = value
        elif "received" in label or "lodged" in label:
            record["received_date"] = value
        elif "decision date" in label:
            record["decision_date"] = value
        elif "decision" in label:
            record["decision_code"] = value
        elif "status" in label:
            record["application_status"] = value

    # Also try <dl> definition lists
    for dl in soup.find_all("dl"):
        terms = dl.find_all("dt")
        defs = dl.find_all("dd")
        for dt, dd in zip(terms, defs):
            label = dt.get_text(strip=True).lower()
            value = dd.get_text(" ", strip=True)
            if not value or value in ("N/A", ""):
                continue

            if "file number" in label or "file ref" in label:
                record["file_ref"] = value
            elif "applicant" in label:
                record["applicant_name"] = value
            elif "address" in label or "location" in label:
                record["address"] = value
            elif "description" in label or "proposal" in label or "development" in label:
                record["description"] = value
            elif "received" in label or "lodged" in label:
                record["received_date"] = value
            elif "decision date" in label:
                record["decision_date"] = value
            elif "decision" in label:
                record["decision_code"] = value
            elif "status" in label:
                record["application_status"] = value

    if not record.get("file_ref") and not record.get("description"):
        return None

    return record


# ── Date / decision helpers ──────────────────────────────────────────────

def parse_cork_date(val: str) -> Optional[date]:
    """Parse Cork ePlan date format: DD/MM/YYYY."""
    if not val or not val.strip():
        return None
    try:
        return datetime.strptime(val.strip(), "%d/%m/%Y").date()
    except ValueError:
        return None


def normalise_cork_decision(decision_code: str, app_status: str) -> Optional[str]:
    """Normalise Cork ePlan decision to standard format."""
    if not decision_code:
        if app_status and "DECISION" in (app_status or "").upper():
            return None
        return None

    dc = decision_code.strip().upper()
    if "CONDITIONAL" in dc or "GRANT" in dc:
        return "GRANTED"
    if "REFUS" in dc:
        return "REFUSED"
    if "WITHDRAW" in dc:
        return "WITHDRAWN"
    if "INVALID" in dc:
        return "INVALID"
    return decision_code.strip() if decision_code.strip() else None


def make_cork_reg_ref(file_ref: str) -> str:
    """Create globally unique ref: CC/25/12345."""
    ref = file_ref.strip() if file_ref else ""
    if not ref:
        return ""
    if not ref.startswith("CC/"):
        return f"CC/{ref}"
    return ref


# ── Record upsert ────────────────────────────────────────────────────────

async def upsert_cork_record(session_factory, record: dict) -> bool:
    """Upsert a single Cork County record into the applications table."""
    file_ref = record.get("file_ref", "")
    if not file_ref:
        return False

    reg_ref = make_cork_reg_ref(file_ref)
    if not reg_ref:
        return False

    internal_id = record.get("internal_id")
    apn_date = parse_cork_date(record.get("received_date", ""))
    dec_date = parse_cork_date(record.get("decision_date", ""))
    decision = normalise_cork_decision(
        record.get("decision_code", ""),
        record.get("application_status", ""),
    )

    # Clean address — append County Cork for geocoding
    location = clean_text(record.get("address"))
    if location and "cork" not in location.lower():
        location = f"{location}, County Cork"

    values = {
        "reg_ref": reg_ref,
        "planning_authority": "Cork County Council",
        "applicant_name": record.get("applicant_name") or None,
        "proposal": clean_text(record.get("description")),
        "location": location,
        "decision": decision,
        "apn_date": apn_date,
        "dec_date": dec_date,
        "link_app_details": DETAIL_URL_TPL.format(internal_id=internal_id) if internal_id else None,
        "npad_object_id": internal_id,
        "data_source": "CORKCOCO_EPLAN",
    }

    # Clean None/nan strings
    for k in list(values.keys()):
        if isinstance(values[k], str) and values[k] in ("nan", "None", "null", ""):
            values[k] = None

    try:
        async with session_factory() as db:
            await db.execute(text("SAVEPOINT cork_upsert"))

            cols = list(values.keys())
            placeholders = [f":{k}" for k in cols]
            update_parts = [f"{k} = EXCLUDED.{k}" for k in cols if k != "reg_ref"]

            sql = text(f"""
                INSERT INTO applications ({', '.join(cols)})
                VALUES ({', '.join(placeholders)})
                ON CONFLICT (reg_ref) DO UPDATE SET {', '.join(update_parts)}
            """)

            await db.execute(sql, values)
            await db.execute(text("RELEASE SAVEPOINT cork_upsert"))
            await db.commit()
        return True

    except Exception as e:
        try:
            async with session_factory() as db:
                await db.execute(text("ROLLBACK TO SAVEPOINT cork_upsert"))
        except Exception:
            pass
        logger.error(f"Error upserting Cork {reg_ref}: {e}")
        return False


# ── Scrape via POST (listing mode) ──────────────────────────────────────

async def scrape_listing_window(
    session_factory,
    client: httpx.AsyncClient,
    time_limit: int,
) -> dict:
    """Scrape both Received and Decided listings for a time window.

    time_limit: 7, 14, 28, 35, or 42 (days from today)
    """
    stats = {"received": 0, "decided": 0, "errors": 0, "upserted": 0}

    # Get CSRF token first
    csrf_token = await get_csrf_token(client)
    if not csrf_token:
        logger.error("Cork: could not get CSRF token")
        stats["errors"] += 1
        return stats

    await asyncio.sleep(RATE_LIMIT_SECONDS)

    # app_status "0" = Received, "1" = Decided
    for app_status, listing_type in [("0", "received"), ("1", "decided")]:
        try:
            html = await fetch_listing_page(client, app_status, time_limit, csrf_token)
            records = parse_listing_html(html)
            stats[listing_type] = len(records)

            for record in records:
                ok = await upsert_cork_record(session_factory, record)
                if ok:
                    stats["upserted"] += 1
                    cork_scraper_progress["records_found_today"] += 1
                    cork_scraper_progress["last_ref"] = make_cork_reg_ref(
                        record.get("file_ref", "")
                    )
                else:
                    stats["errors"] += 1

                cork_scraper_progress["scraped_today"] += 1

            await asyncio.sleep(RATE_LIMIT_SECONDS)

        except httpx.HTTPStatusError as e:
            status = e.response.status_code
            if status == 429:
                logger.warning("Cork ePlan returned 429 — backing off 1 hour")
                await asyncio.sleep(3600)
            elif status == 503:
                logger.warning("Cork ePlan returned 503 — stopping, retry later")
                cork_scraper_progress["error"] = "503 Service Unavailable — retry later"
                raise
            else:
                logger.error(f"Cork ePlan HTTP error: {e}")
                stats["errors"] += 1

        except Exception as e:
            logger.error(f"Cork scrape error ({listing_type}, {time_limit}d window): {e}")
            stats["errors"] += 1

    logger.info(
        f"Cork {time_limit}d window: "
        f"received={stats['received']}, decided={stats['decided']}, "
        f"upserted={stats['upserted']}, errors={stats['errors']}"
    )
    return stats


# ── Scrape detail page by ref (backfill mode) ───────────────────────────

async def scrape_detail_by_ref(
    session_factory,
    client: httpx.AsyncClient,
    ref: str,
) -> bool:
    """Fetch a single application's detail page by its ref (e.g., '25/12345').

    Returns True if a record was found and upserted.
    """
    # Cork detail pages are at /ePlan/AppFileRefDetails/{ref}/0
    # The ref goes directly in the URL
    url = f"{EPLAN_BASE}/AppFileRefDetails/{ref}/0"

    try:
        resp = await client.get(
            url,
            headers={"User-Agent": USER_AGENT},
            follow_redirects=True,
            timeout=30.0,
        )

        if resp.status_code == 404:
            return False
        if resp.status_code != 200:
            logger.debug(f"Cork detail {ref}: HTTP {resp.status_code}")
            return False

        # Check if we got a valid page (not a redirect to error)
        if len(resp.text) < 500:
            return False

        record = parse_detail_page(resp.text)
        if not record:
            return False

        # Ensure ref is set
        if not record.get("file_ref"):
            record["file_ref"] = ref

        ok = await upsert_cork_record(session_factory, record)
        return ok

    except httpx.HTTPStatusError:
        return False
    except Exception as e:
        logger.error(f"Cork detail scrape error for {ref}: {e}")
        return False


# ── Continuous mode ──────────────────────────────────────────────────────

async def run_cork_continuous_loop():
    """Run the Cork scraper in continuous mode.

    Uses 7-day window via POST, runs every 6 hours.
    Overlap handles duplicates via upsert (ON CONFLICT).
    """
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    cork_scraper_progress["running"] = True
    cork_scraper_progress["mode"] = "continuous"
    cork_scraper_progress["started_at"] = datetime.utcnow().isoformat()
    cork_scraper_progress["scraped_today"] = 0
    cork_scraper_progress["records_found_today"] = 0
    cork_scraper_progress["error"] = None

    logger.info("Cork County scraper started — continuous mode (7-day POST window)")

    try:
        async with httpx.AsyncClient() as client:
            while cork_scraper_progress["running"]:
                cork_scraper_progress["current_window"] = "Last 7 days (POST)"

                await scrape_listing_window(session_factory, client, time_limit=7)

                # Sleep 6 hours between runs
                logger.info("Cork scraper: sleeping 6 hours until next run")
                for _ in range(360):  # Check every minute if still running
                    if not cork_scraper_progress["running"]:
                        break
                    await asyncio.sleep(60)

    except asyncio.CancelledError:
        logger.info("Cork scraper continuous loop cancelled")
    except Exception as e:
        logger.error(f"Cork scraper continuous loop crashed: {e}")
        cork_scraper_progress["error"] = str(e)
    finally:
        cork_scraper_progress["running"] = False
        cork_scraper_progress["mode"] = None
        logger.info("Cork scraper continuous loop stopped")


# ── Backfill mode ────────────────────────────────────────────────────────

async def run_cork_backfill():
    """Run backfill of Cork County applications by enumerating refs.

    Cork refs follow YY/NNNNN format. We enumerate:
    - 23/00001 to 23/15000  (~2023)
    - 24/00001 to 24/15000  (~2024)
    - 25/00001 to 25/15000  (~2025)

    This bypasses the listing page entirely, using detail page scraping.
    ~45,000 requests total, at 2s rate limit ≈ 25 hours.
    """
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    cork_scraper_progress["running"] = True
    cork_scraper_progress["mode"] = "backfill"
    cork_scraper_progress["started_at"] = datetime.utcnow().isoformat()
    cork_scraper_progress["scraped_today"] = 0
    cork_scraper_progress["records_found_today"] = 0
    cork_scraper_progress["error"] = None
    cork_scraper_progress["windows_done"] = 0

    # Year ranges to enumerate — Cork refs are YY/NNNNN
    years = [23, 24, 25]
    max_ref_per_year = 15000
    cork_scraper_progress["total_windows"] = len(years) * max_ref_per_year

    logger.info(
        f"Cork backfill starting: {len(years)} years × {max_ref_per_year} refs "
        f"= {len(years) * max_ref_per_year} refs to try"
    )

    consecutive_misses = 0
    MAX_CONSECUTIVE_MISSES = 500  # If 500 in a row are empty, skip to next year

    try:
        async with httpx.AsyncClient() as client:
            for year in years:
                if not cork_scraper_progress["running"]:
                    break

                cork_scraper_progress["backfill_year"] = year
                consecutive_misses = 0

                for ref_num in range(1, max_ref_per_year + 1):
                    if not cork_scraper_progress["running"]:
                        break

                    ref = f"{year}/{ref_num:05d}"
                    cork_scraper_progress["backfill_ref_num"] = ref_num
                    cork_scraper_progress["current_window"] = f"Ref {ref}"

                    found = await scrape_detail_by_ref(session_factory, client, ref)

                    if found:
                        consecutive_misses = 0
                        cork_scraper_progress["records_found_today"] += 1
                        cork_scraper_progress["last_ref"] = make_cork_reg_ref(ref)
                    else:
                        consecutive_misses += 1

                    cork_scraper_progress["scraped_today"] += 1
                    cork_scraper_progress["windows_done"] += 1

                    # Skip to next year if too many consecutive misses
                    if consecutive_misses >= MAX_CONSECUTIVE_MISSES:
                        logger.info(
                            f"Cork backfill: {MAX_CONSECUTIVE_MISSES} consecutive "
                            f"misses at {ref}, skipping to next year"
                        )
                        break

                    # Rate limit
                    await asyncio.sleep(RATE_LIMIT_SECONDS)

                    # Log progress every 500 refs
                    if ref_num % 500 == 0:
                        logger.info(
                            f"Cork backfill: year={year}, ref={ref_num}/{max_ref_per_year}, "
                            f"found={cork_scraper_progress['records_found_today']}"
                        )

                logger.info(
                    f"Cork backfill year {year} complete: "
                    f"found so far = {cork_scraper_progress['records_found_today']}"
                )

    except asyncio.CancelledError:
        logger.info("Cork backfill cancelled")
    except Exception as e:
        logger.error(f"Cork backfill crashed: {e}")
        cork_scraper_progress["error"] = str(e)
    finally:
        cork_scraper_progress["running"] = False
        cork_scraper_progress["mode"] = None
        cork_scraper_progress["backfill_year"] = None
        cork_scraper_progress["backfill_ref_num"] = None
        logger.info(
            f"Cork backfill complete: {cork_scraper_progress['records_found_today']} records, "
            f"{cork_scraper_progress['windows_done']}/{cork_scraper_progress['total_windows']} refs tried"
        )
