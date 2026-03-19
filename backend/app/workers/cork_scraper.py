"""PlanSearch — Cork County Council ePlan Scraper.

Scrapes planning applications from planning.corkcoco.ie/ePlan.
Cork County Council is the only major ROI council missing from NPAD.

Two modes:
- Continuous: scrapes recent 42-day windows regularly
- Backfill: walks back through 2 years in 42-day chunks

Rate limiting: 2s between requests, off-peak hours only (8pm–8am Irish time).
Geocoding: Cork records have no coordinates — the geocoder picks them up automatically.

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
RECEIVED_URL = f"{EPLAN_BASE}/SearchListing/RECEIVED"
DECIDED_URL = f"{EPLAN_BASE}/SearchListing/MADE"
DETAIL_URL_TPL = f"{EPLAN_BASE}/AppFileRefDetails/{{internal_id}}/0"

USER_AGENT = "PlanSearch/1.0 (+https://plansearch.cc; planning research)"
RATE_LIMIT_SECONDS = 2.0
BATCH_PAUSE_SECONDS = 10
MAX_WINDOW_DAYS = 42  # ePlan maximum per request

# Irish timezone for off-peak check
IRISH_TZ = timezone(timedelta(hours=0))  # UTC ≈ Irish winter; summer is UTC+1

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
}


# ── Off-peak check ──────────────────────────────────────────────────────

def is_off_peak() -> bool:
    """Check if current time is within off-peak hours (8pm–8am Irish time).

    During regular continuous scraping we honour this; backfill can override.
    """
    now = datetime.now(timezone.utc)
    irish_hour = (now.hour) % 24  # UTC ≈ Irish time (close enough)
    return irish_hour >= 20 or irish_hour < 8


# ── HTML Scraping ────────────────────────────────────────────────────────

async def fetch_listing_page(
    client: httpx.AsyncClient,
    listing_url: str,
    date_from: date,
    date_to: date,
) -> str:
    """Fetch a listing page from the Cork ePlan portal."""
    params = {
        "from": date_from.strftime("%d/%m/%Y"),
        "to": date_to.strftime("%d/%m/%Y"),
    }
    response = await client.get(
        listing_url,
        params=params,
        headers={"User-Agent": USER_AGENT},
        timeout=30.0,
        follow_redirects=True,
    )
    response.raise_for_status()
    return response.text


def parse_listing_html(html: str) -> list[dict]:
    """Parse Cork ePlan listing page HTML to extract application rows.

    Table columns (confirmed from live inspection):
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

    table = soup.find("table")
    if not table:
        return records

    rows = table.find_all("tr")
    for row in rows:
        cells = row.find_all("td")
        if len(cells) < 9:
            continue

        # Extract internal ID from href
        link = cells[0].find("a")
        if not link:
            continue

        href = link.get("href", "")
        internal_id = None
        file_ref = link.get_text(strip=True)

        # Pattern: /ePlan/AppFileRefDetails/254299/0
        id_match = re.search(r"/AppFileRefDetails/(\d+)/", href)
        if id_match:
            internal_id = int(id_match.group(1))

        if not internal_id and not file_ref:
            continue

        # Extract fields from cells
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
            return None  # Will fill from decision_code
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


# ── Scrape a date window ────────────────────────────────────────────────

async def scrape_window(
    session_factory,
    client: httpx.AsyncClient,
    date_from: date,
    date_to: date,
) -> dict:
    """Scrape both received and decided listings for a date window."""
    stats = {"received": 0, "decided": 0, "errors": 0, "upserted": 0}

    for listing_url, listing_type in [
        (RECEIVED_URL, "received"),
        (DECIDED_URL, "decided"),
    ]:
        try:
            html = await fetch_listing_page(client, listing_url, date_from, date_to)
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

                # Rate limit between individual record inserts isn't needed,
                # but we do rate-limit between HTTP requests
            await asyncio.sleep(RATE_LIMIT_SECONDS)

        except httpx.HTTPStatusError as e:
            status = e.response.status_code
            if status == 429:
                logger.warning("Cork ePlan returned 429 — backing off 1 hour")
                await asyncio.sleep(3600)
            elif status == 503:
                logger.warning("Cork ePlan returned 503 — stopping, retry in 4 hours")
                cork_scraper_progress["error"] = "503 Service Unavailable — retry later"
                raise
            else:
                logger.error(f"Cork ePlan HTTP error: {e}")
                stats["errors"] += 1

        except Exception as e:
            logger.error(f"Cork scrape error ({listing_type} {date_from}→{date_to}): {e}")
            stats["errors"] += 1

    logger.info(
        f"Cork window {date_from}→{date_to}: "
        f"received={stats['received']}, decided={stats['decided']}, "
        f"upserted={stats['upserted']}, errors={stats['errors']}"
    )
    return stats


# ── Continuous mode ──────────────────────────────────────────────────────

async def run_cork_continuous_loop():
    """Run the Cork scraper in continuous mode.

    Scrapes the most recent 42-day window every 4 hours during off-peak.
    ~12,500-15,000 apps/year for Cork County.
    """
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    cork_scraper_progress["running"] = True
    cork_scraper_progress["mode"] = "continuous"
    cork_scraper_progress["started_at"] = datetime.utcnow().isoformat()
    cork_scraper_progress["scraped_today"] = 0
    cork_scraper_progress["records_found_today"] = 0
    cork_scraper_progress["error"] = None

    logger.info("Cork County scraper started — continuous mode")

    try:
        async with httpx.AsyncClient() as client:
            while cork_scraper_progress["running"]:
                # Wait for off-peak hours
                if not is_off_peak():
                    logger.info("Cork scraper: outside off-peak hours, sleeping 1 hour")
                    await asyncio.sleep(3600)
                    continue

                today = date.today()
                date_from = today - timedelta(days=MAX_WINDOW_DAYS)
                date_to = today

                cork_scraper_progress["current_window"] = (
                    f"{date_from.isoformat()} → {date_to.isoformat()}"
                )

                await scrape_window(session_factory, client, date_from, date_to)

                # Sleep 4 hours between continuous scrapes
                logger.info("Cork scraper: sleeping 4 hours until next run")
                for _ in range(240):  # Check every minute if still running
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
    """Run 2-year backfill of Cork County applications.

    Walks backwards in 42-day windows from today to 2 years ago.
    2 years / 42 days ≈ 18 windows × 2 (received + decided) = ~36 HTTP requests.
    Total: ~25,000–30,000 records.
    """
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    cork_scraper_progress["running"] = True
    cork_scraper_progress["mode"] = "backfill"
    cork_scraper_progress["started_at"] = datetime.utcnow().isoformat()
    cork_scraper_progress["scraped_today"] = 0
    cork_scraper_progress["records_found_today"] = 0
    cork_scraper_progress["error"] = None

    today = date.today()
    two_years_ago = today - timedelta(days=730)

    # Generate 42-day windows walking backwards
    windows = []
    current_end = today
    while current_end > two_years_ago:
        current_start = max(current_end - timedelta(days=MAX_WINDOW_DAYS), two_years_ago)
        windows.append((current_start, current_end))
        current_end = current_start - timedelta(days=1)

    cork_scraper_progress["total_windows"] = len(windows)
    cork_scraper_progress["windows_done"] = 0

    logger.info(f"Cork backfill starting: {len(windows)} windows, ~2 years")

    try:
        async with httpx.AsyncClient() as client:
            for i, (w_start, w_end) in enumerate(windows):
                if not cork_scraper_progress["running"]:
                    break

                cork_scraper_progress["current_window"] = (
                    f"{w_start.isoformat()} → {w_end.isoformat()}"
                )

                await scrape_window(session_factory, client, w_start, w_end)

                cork_scraper_progress["windows_done"] = i + 1

                # Rate limit between windows
                await asyncio.sleep(RATE_LIMIT_SECONDS * 2)

    except asyncio.CancelledError:
        logger.info("Cork backfill cancelled")
    except Exception as e:
        logger.error(f"Cork backfill crashed: {e}")
        cork_scraper_progress["error"] = str(e)
    finally:
        cork_scraper_progress["running"] = False
        cork_scraper_progress["mode"] = None
        logger.info(
            f"Cork backfill complete: {cork_scraper_progress['records_found_today']} records, "
            f"{cork_scraper_progress['windows_done']}/{len(windows)} windows"
        )
