"""PlanSearch — Document Metadata Scraper.

Scrapes document lists from Irish planning portals.
Supports:
- ePlanning.ie (most councils) — server-rendered, direct HTML scraping
- planning.agileapplications.ie (Dublin councils) — Angular SPA, needs API
- planning.localgov.ie — national portal for newer applications

Uses link_app_details from the applications table as the base URL.
Rate limited to 1 request per 3 seconds.
Runs as a continuous background loop, prioritising 2023+ applications.
"""

import asyncio
import logging
from datetime import datetime
from typing import Optional
from urllib.parse import urlparse, urljoin

import httpx
from bs4 import BeautifulSoup
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.database import engine

logger = logging.getLogger(__name__)

USER_AGENT = "Mozilla/5.0 (compatible; PlanSearch/1.0; +https://plansearch.cc)"
RATE_LIMIT_SECONDS = 3.0
BATCH_SIZE = 20
LOOP_PAUSE_SECONDS = 30

doc_scraper_progress = {
    "running": False,
    "scraped_today": 0,
    "documents_found_today": 0,
    "last_ref": None,
    "started_at": None,
    "error": None,
}


# ── Document categorisation ──────────────────────────────────────────────


def categorize_document(name: str) -> str:
    """Categorize document by name."""
    name_lower = (name or "").lower()

    if any(w in name_lower for w in [
        "plan", "elevation", "section", "drawing", "layout", "floor",
        "site layout", "ground floor", "first floor",
    ]):
        return "drawing"
    elif any(w in name_lower for w in [
        "report", "assessment", "study", "survey", "eia", "aa",
        "environmental", "traffic", "flood", "daylight",
    ]):
        return "report"
    elif any(w in name_lower for w in [
        "notice", "newspaper", "site notice", "public notice",
    ]):
        return "notice"
    elif any(w in name_lower for w in [
        "decision", "grant", "refuse", "order", "notification of decision",
    ]):
        return "decision"
    elif any(w in name_lower for w in [
        "observation", "submission", "third party", "objection",
    ]):
        return "observation"
    elif any(w in name_lower for w in [
        "further information", "f.i.", "response", "clarification",
    ]):
        return "further_info"
    elif any(w in name_lower for w in [
        "application form", "form",
    ]):
        return "application_form"
    elif any(w in name_lower for w in [
        "photo", "image", "site photo", "render", "cgi",
    ]):
        return "site_media"
    else:
        return "other"


def _extract_file_extension(href: str, text: str = "") -> Optional[str]:
    """Extract file extension from URL or text."""
    extensions = [
        ".pdf", ".dwg", ".doc", ".docx", ".tif", ".tiff",
        ".jpg", ".jpeg", ".png", ".xls", ".xlsx",
    ]
    for e in extensions:
        if e in href.lower():
            return e.lstrip(".")
    for e in extensions:
        if e in text.lower():
            return e.lstrip(".")
    return None


# ── ePlanning portal scraping ────────────────────────────────────────────


def extract_eplanning_documents(
    soup: BeautifulSoup, base_url: str
) -> list[dict]:
    """Extract documents from ePlanning portal HTML.

    ePlanning is server-rendered — documents appear as links in tables
    or as "View Scanned Files" links.
    """
    documents = []
    seen_names = set()

    # Method 1: Look for document tables
    for table in soup.find_all("table"):
        headers = [th.get_text(strip=True).lower() for th in table.find_all("th")]
        if any("document" in h or "file" in h or "description" in h for h in headers):
            for row in table.find_all("tr")[1:]:
                cells = row.find_all("td")
                if len(cells) >= 2:
                    name = cells[0].get_text(strip=True)
                    link_el = row.find("a", href=True)
                    href = link_el.get("href", "") if link_el else ""

                    if name and len(name) > 1 and name not in seen_names:
                        seen_names.add(name)
                        direct_url = _make_absolute_url(href, base_url)
                        documents.append({
                            "doc_name": name[:500],
                            "direct_url": direct_url,
                            "file_extension": _extract_file_extension(href, name),
                            "doc_category": categorize_document(name),
                            "portal_source": "eplanning",
                        })

    # Method 2: Look for all file-type links
    for link in soup.find_all("a", href=True):
        href = link.get("href", "")
        link_text = link.get_text(strip=True)

        ext = _extract_file_extension(href)
        if ext or any(k in href.lower() for k in [
            "download", "getfile", "scannedfile", "viewfile",
        ]):
            if link_text and len(link_text) > 1 and link_text not in seen_names:
                seen_names.add(link_text)
                direct_url = _make_absolute_url(href, base_url)
                documents.append({
                    "doc_name": link_text[:500],
                    "direct_url": direct_url,
                    "file_extension": ext,
                    "doc_category": categorize_document(link_text),
                    "portal_source": "eplanning",
                })

    return documents


def _make_absolute_url(href: str, base_url: str) -> Optional[str]:
    """Convert a relative URL to absolute."""
    if not href:
        return None
    if href.startswith("http"):
        return href
    if href.startswith("/"):
        parsed = urlparse(base_url)
        return f"{parsed.scheme}://{parsed.netloc}{href}"
    return urljoin(base_url, href)


# ── Agile portal scraping ───────────────────────────────────────────────


async def extract_agile_documents_via_api(
    app_id: str,
    base_url: str,
    client: httpx.AsyncClient,
) -> list[dict]:
    """Extract documents from Agile portal via its internal API.

    The Agile portal is an Angular SPA — documents are loaded via
    XHR API calls. The API endpoint pattern is:
    /api/applications/{id}/documents
    """
    documents = []

    # Extract the council slug and application ID from the URL
    # e.g. planning.agileapplications.ie/dublincity/application-details/78954
    parsed = urlparse(base_url)
    path_parts = parsed.path.strip("/").split("/")

    if len(path_parts) < 3:
        return documents

    council_slug = path_parts[0]  # e.g. "dublincity"
    numeric_id = path_parts[-1]  # e.g. "78954"

    # Try the known API endpoint patterns
    api_urls = [
        f"https://{parsed.netloc}/{council_slug}/api/applications/{numeric_id}/documents",
        f"https://{parsed.netloc}/api/{council_slug}/applications/{numeric_id}/documents",
    ]

    for api_url in api_urls:
        try:
            response = await client.get(
                api_url,
                headers={
                    "User-Agent": USER_AGENT,
                    "Accept": "application/json",
                },
                timeout=20.0,
            )
            if response.status_code == 200:
                data = response.json()
                if isinstance(data, list):
                    for doc in data:
                        name = doc.get("name") or doc.get("description") or doc.get("title", "")
                        url = doc.get("url") or doc.get("downloadUrl") or doc.get("fileUrl")
                        if name:
                            documents.append({
                                "doc_name": name[:500],
                                "direct_url": url,
                                "file_extension": _extract_file_extension(url or "", name),
                                "doc_category": categorize_document(name),
                                "portal_source": "agile",
                            })
                    if documents:
                        return documents
        except Exception:
            continue

    return documents


# ── Application scraping dispatcher ──────────────────────────────────────


async def scrape_documents_for_application(
    reg_ref: str,
    link_app_details: str,
    client: httpx.AsyncClient,
) -> list[dict]:
    """Scrape document list for a single application.

    Routes to the correct scraper based on the portal URL.
    """
    if not link_app_details:
        return []

    try:
        if "eplanning.ie" in link_app_details:
            return await _scrape_eplanning(link_app_details, client)
        elif "agileapplications.ie" in link_app_details:
            return await extract_agile_documents_via_api(
                reg_ref, link_app_details, client
            )
        elif "localgov.ie" in link_app_details:
            return await _scrape_eplanning(link_app_details, client)
        else:
            # Unknown portal — try generic HTML scraping
            return await _scrape_eplanning(link_app_details, client)

    except Exception as e:
        logger.debug(f"Error scraping documents for {reg_ref}: {e}")
        return []


async def _scrape_eplanning(
    link_url: str, client: httpx.AsyncClient
) -> list[dict]:
    """Scrape documents from an ePlanning-style portal."""
    # Try the ViewScannedFiles endpoint first
    scanned_url = link_url.rstrip("/") + "/ViewScannedFiles"
    try:
        response = await client.get(
            scanned_url,
            headers={"User-Agent": USER_AGENT},
            timeout=20.0,
            follow_redirects=True,
        )
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, "html.parser")
            docs = extract_eplanning_documents(soup, scanned_url)
            if docs:
                return docs
    except Exception:
        pass

    # Fall back to main application page
    try:
        response = await client.get(
            link_url,
            headers={"User-Agent": USER_AGENT},
            timeout=20.0,
            follow_redirects=True,
        )
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, "html.parser")
            return extract_eplanning_documents(soup, link_url)
    except Exception:
        pass

    return []


# ── Database operations ──────────────────────────────────────────────────


async def get_next_batch(session_factory) -> list:
    """Get next batch of applications to scrape for documents."""
    async with session_factory() as db:
        result = await db.execute(text("""
            SELECT a.id, a.reg_ref, a.link_app_details
            FROM applications a
            LEFT JOIN document_scrape_status dss ON a.reg_ref = dss.reg_ref
            WHERE dss.reg_ref IS NULL
              AND a.link_app_details IS NOT NULL
              AND a.apn_date >= '2023-01-01'
            ORDER BY a.apn_date DESC NULLS LAST
            LIMIT :limit
        """), {"limit": BATCH_SIZE})
        return list(result.fetchall())


async def save_documents(
    session_factory, reg_ref: str, docs: list[dict], portal_url: str
):
    """Save scraped documents to database."""
    async with session_factory() as db:
        for doc in docs:
            try:
                await db.execute(text("""
                    INSERT INTO application_documents
                        (reg_ref, doc_name, doc_type, file_extension,
                         portal_source, direct_url, portal_url, doc_category)
                    VALUES
                        (:reg_ref, :doc_name, :doc_type, :file_extension,
                         :portal_source, :direct_url, :portal_url, :doc_category)
                    ON CONFLICT DO NOTHING
                """), {
                    "reg_ref": reg_ref,
                    "doc_name": doc["doc_name"],
                    "doc_type": doc.get("file_extension"),
                    "file_extension": doc.get("file_extension"),
                    "portal_source": doc.get("portal_source"),
                    "direct_url": doc.get("direct_url"),
                    "portal_url": portal_url,
                    "doc_category": doc.get("doc_category"),
                })
            except Exception as e:
                logger.debug(f"Error saving doc for {reg_ref}: {e}")

        # Mark as scraped
        await db.execute(text("""
            INSERT INTO document_scrape_status
                (reg_ref, last_scraped, doc_count, scrape_status, portal_source)
            VALUES
                (:reg_ref, NOW(), :count, :status, :source)
            ON CONFLICT (reg_ref) DO UPDATE SET
                last_scraped = NOW(),
                doc_count = :count,
                scrape_status = :status
        """), {
            "reg_ref": reg_ref,
            "count": len(docs),
            "status": "done" if docs else "no_docs",
            "source": docs[0]["portal_source"] if docs else None,
        })

        await db.commit()


# ── Continuous loop ──────────────────────────────────────────────────────


async def run_doc_scraper_loop():
    """Run document scraper continuously as a background loop."""
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    doc_scraper_progress["running"] = True
    doc_scraper_progress["started_at"] = datetime.utcnow().isoformat()
    doc_scraper_progress["scraped_today"] = 0
    doc_scraper_progress["documents_found_today"] = 0
    doc_scraper_progress["error"] = None

    logger.info("Document scraper loop started — 1 request per 3 seconds")

    try:
        async with httpx.AsyncClient(follow_redirects=True) as client:
            while doc_scraper_progress["running"]:
                rows = await get_next_batch(session_factory)

                if not rows:
                    logger.info(
                        "Document scraper: nothing to process, sleeping 10 min"
                    )
                    await asyncio.sleep(600)
                    continue

                for row in rows:
                    if not doc_scraper_progress["running"]:
                        break

                    try:
                        docs = await scrape_documents_for_application(
                            row.reg_ref, row.link_app_details, client
                        )

                        await save_documents(
                            session_factory,
                            row.reg_ref,
                            docs,
                            row.link_app_details,
                        )

                        doc_scraper_progress["scraped_today"] += 1
                        doc_scraper_progress["documents_found_today"] += len(docs)
                        doc_scraper_progress["last_ref"] = row.reg_ref

                        if docs:
                            logger.debug(
                                f"Found {len(docs)} docs for {row.reg_ref}"
                            )

                    except Exception as e:
                        logger.error(f"Error processing {row.reg_ref}: {e}")

                    await asyncio.sleep(RATE_LIMIT_SECONDS)

                await asyncio.sleep(LOOP_PAUSE_SECONDS)

    except asyncio.CancelledError:
        logger.info("Document scraper loop cancelled")
    except Exception as e:
        logger.error(f"Document scraper loop crashed: {e}")
        doc_scraper_progress["error"] = str(e)
    finally:
        doc_scraper_progress["running"] = False
        logger.info("Document scraper loop stopped")
