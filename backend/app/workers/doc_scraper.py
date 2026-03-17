"""PlanSearch — Document Metadata Scraper.

Scrapes document metadata from the planning portal
and stores file references in the application_documents table.
"""

import asyncio
import logging
from datetime import datetime
from typing import Optional

import httpx
from bs4 import BeautifulSoup
from sqlalchemy import select, update, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models import Application, ApplicationDocument, DocumentScrapeStatus

logger = logging.getLogger(__name__)
settings = get_settings()

USER_AGENT = "PlanSearch/1.0 (public data research)"


class RateLimiter:
    """Simple async rate limiter."""
    def __init__(self, interval_seconds: float):
        self.interval = interval_seconds
        self._last_request = 0.0

    async def __aenter__(self):
        now = asyncio.get_event_loop().time()
        elapsed = now - self._last_request
        if elapsed < self.interval:
            await asyncio.sleep(self.interval - elapsed)
        self._last_request = asyncio.get_event_loop().time()
        return self

    async def __aexit__(self, *args):
        pass


rate_limiter = RateLimiter(3.0)  # 1 request per 3 seconds


async def scrape_documents_for_application(
    reg_ref: str,
    year: Optional[int],
    db: AsyncSession,
) -> int:
    """Scrape document metadata for a single application.

    Returns the number of documents found.
    """
    if year and year >= 2024:
        url = f"https://planning.localgov.ie/en/view-planning-applications?reference={reg_ref}"
    else:
        url = f"https://planning.agileapplications.ie/dublincity/application-details/{reg_ref}"

    try:
        async with rate_limiter:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(
                    url,
                    headers={"User-Agent": USER_AGENT},
                    follow_redirects=True,
                )

        if response.status_code == 429:
            logger.warning(f"Rate limited on {reg_ref}")
            return 0

        if response.status_code != 200:
            logger.warning(f"HTTP {response.status_code} for {reg_ref}")
            return 0

        soup = BeautifulSoup(response.text, "html.parser")
        documents = extract_documents_from_html(soup, reg_ref, year)

        for doc_data in documents:
            # Check if document already exists
            existing = await db.execute(
                select(ApplicationDocument).where(
                    and_(
                        ApplicationDocument.reg_ref == reg_ref,
                        ApplicationDocument.doc_name == doc_data["doc_name"],
                    )
                )
            )
            if not existing.scalar_one_or_none():
                doc = ApplicationDocument(
                    reg_ref=reg_ref,
                    doc_name=doc_data["doc_name"],
                    doc_type=doc_data.get("doc_type"),
                    file_extension=doc_data.get("file_extension"),
                    file_size_bytes=doc_data.get("file_size_bytes"),
                    portal_source="localgov" if (year and year >= 2024) else "agile",
                    direct_url=doc_data.get("direct_url"),
                    portal_url=url,
                    uploaded_date=doc_data.get("uploaded_date"),
                    doc_category=doc_data.get("doc_category"),
                )
                db.add(doc)

        return len(documents)

    except Exception as e:
        logger.error(f"Error scraping documents for {reg_ref}: {e}")
        return 0


def extract_documents_from_html(soup: BeautifulSoup, reg_ref: str, year: Optional[int]) -> list[dict]:
    """Extract document metadata from portal HTML.

    Adaptable to both Agile Applications and LocalGov portals.
    """
    documents = []

    # Look for document links
    for link in soup.find_all("a", href=True):
        href = link.get("href", "")
        text = link.get_text(strip=True)

        # Filter for document-like links (PDFs, etc.)
        if any(ext in href.lower() for ext in [".pdf", ".doc", ".docx", ".dwg", ".tif", ".jpg", ".png"]):
            ext = None
            for e in [".pdf", ".doc", ".docx", ".dwg", ".tif", ".jpg", ".png"]:
                if e in href.lower():
                    ext = e.lstrip(".")
                    break

            doc_data = {
                "doc_name": text or href.split("/")[-1],
                "direct_url": href if href.startswith("http") else None,
                "file_extension": ext,
                "doc_type": categorize_document(text),
            }
            documents.append(doc_data)

    # Look for document tables
    for table in soup.find_all("table"):
        headers = [th.get_text(strip=True).lower() for th in table.find_all("th")]
        if any("document" in h or "file" in h for h in headers):
            for row in table.find_all("tr")[1:]:  # Skip header row
                cells = row.find_all("td")
                if len(cells) >= 2:
                    name = cells[0].get_text(strip=True)
                    link_el = row.find("a", href=True)
                    url = link_el.get("href") if link_el else None

                    doc_data = {
                        "doc_name": name,
                        "direct_url": url if url and url.startswith("http") else None,
                        "doc_type": categorize_document(name),
                    }
                    documents.append(doc_data)

    return documents


def categorize_document(name: str) -> Optional[str]:
    """Categorize a document by its name."""
    if not name:
        return None

    name_lower = name.lower()

    if any(w in name_lower for w in ["plan", "elevation", "section", "drawing", "layout"]):
        return "drawing"
    elif any(w in name_lower for w in ["report", "assessment", "study", "survey"]):
        return "report"
    elif any(w in name_lower for w in ["notification", "notice", "newspaper"]):
        return "notice"
    elif any(w in name_lower for w in ["observation", "submission", "comment"]):
        return "observation"
    elif any(w in name_lower for w in ["certificate", "cert"]):
        return "certificate"
    elif any(w in name_lower for w in ["grant", "decision", "order"]):
        return "decision"
    elif any(w in name_lower for w in ["site", "photo", "image"]):
        return "site_media"
    elif any(w in name_lower for w in ["application", "form"]):
        return "application_form"
    else:
        return "other"


async def run_document_scraper_batch(
    db: AsyncSession,
    batch_size: int = 50,
) -> dict:
    """Run document scraping for a batch of applications.

    Only processes applications that haven't had their documents scraped.
    """
    stats = {"processed": 0, "documents_found": 0, "failed": 0}

    # Get applications without document scrape status
    result = await db.execute(
        select(Application)
        .outerjoin(
            DocumentScrapeStatus,
            Application.reg_ref == DocumentScrapeStatus.reg_ref,
        )
        .where(DocumentScrapeStatus.id.is_(None))
        .order_by(Application.apn_date.desc().nullslast())
        .limit(batch_size)
    )
    applications = result.scalars().all()

    logger.info(f"Scraping documents for {len(applications)} applications")

    for app in applications:
        try:
            count = await scrape_documents_for_application(app.reg_ref, app.year, db)

            # Record scrape status
            scrape_status = DocumentScrapeStatus(
                reg_ref=app.reg_ref,
                scraped_at=datetime.utcnow(),
                documents_found=count,
                status="completed",
            )
            db.add(scrape_status)

            stats["processed"] += 1
            stats["documents_found"] += count

            if stats["processed"] % 10 == 0:
                await db.commit()
                logger.info(f"Scraped {stats['processed']} applications, found {stats['documents_found']} documents")

        except Exception as e:
            logger.error(f"Error scraping docs for {app.reg_ref}: {e}")
            stats["failed"] += 1

    await db.commit()
    logger.info(f"Document scraper batch complete: {stats}")
    return stats
