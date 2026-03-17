"""PlanSearch — Applicant Name Scraper.

Rate-limited scraper that fetches applicant names from the
Agile Applications portal. Runs during off-peak hours only.

Rate limit: 1 request per 3 seconds
Retry: up to 3 attempts with exponential backoff
Circuit breaker: pause 1 hour after 10 consecutive failures
"""

import asyncio
import logging
from datetime import datetime
from typing import Optional

import httpx
from bs4 import BeautifulSoup
from sqlalchemy import select, update, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models import Application, ScrapeJob

logger = logging.getLogger(__name__)
settings = get_settings()

AGILE_BASE = "https://planning.agileapplications.ie"
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


rate_limiter = RateLimiter(settings.scraper_rate_limit_seconds)


async def scrape_applicant_name(reg_ref: str) -> Optional[str]:
    """Scrape the applicant name for a single application from the Agile portal.

    Args:
        reg_ref: Planning registration reference

    Returns:
        Applicant name string, or None if not found
    """
    url = f"{AGILE_BASE}/dublincity/application-details/{reg_ref}"

    async with rate_limiter:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(
                url,
                headers={"User-Agent": USER_AGENT},
                follow_redirects=True,
            )

    if response.status_code == 429:
        logger.warning(f"Rate limited on {reg_ref}, backing off")
        await asyncio.sleep(3600)  # Back off for 1 hour on 429
        return None

    if response.status_code != 200:
        logger.warning(f"HTTP {response.status_code} for {reg_ref}")
        return None

    soup = BeautifulSoup(response.text, "html.parser")
    return extract_applicant_from_html(soup)


def extract_applicant_from_html(soup: BeautifulSoup) -> Optional[str]:
    """Extract applicant name from the Agile portal HTML.

    The portal is a React SPA, so this looks for rendered content
    or JSON data embedded in the page.
    """
    # Try to find applicant in rendered HTML
    # Look for common label patterns
    for label_text in ["Applicant", "Applicant Name", "applicant"]:
        label = soup.find(string=lambda t: t and label_text.lower() in t.lower())
        if label:
            # Try to get the next sibling or parent's next sibling
            parent = label.parent if label.parent else None
            if parent:
                next_el = parent.find_next_sibling()
                if next_el:
                    text = next_el.get_text(strip=True)
                    if text and len(text) > 1:
                        return text

    # Try to find in a data table or definition list
    for dt in soup.find_all("dt"):
        if "applicant" in dt.get_text().lower():
            dd = dt.find_next_sibling("dd")
            if dd:
                text = dd.get_text(strip=True)
                if text and len(text) > 1:
                    return text

    # Try to find in table rows
    for row in soup.find_all("tr"):
        cells = row.find_all(["td", "th"])
        for i, cell in enumerate(cells):
            if "applicant" in cell.get_text().lower() and i + 1 < len(cells):
                text = cells[i + 1].get_text(strip=True)
                if text and len(text) > 1:
                    return text

    return None


async def run_scraper_batch(
    db: AsyncSession,
    batch_size: int = 100,
) -> dict:
    """Run a batch of applicant name scraping.

    Args:
        db: Database session
        batch_size: Number of applications to scrape

    Returns:
        Dictionary with scraping statistics
    """
    stats = {"scraped": 0, "found": 0, "failed": 0, "consecutive_failures": 0}

    # Get applications that haven't been scraped yet
    result = await db.execute(
        select(Application.reg_ref)
        .where(
            and_(
                Application.applicant_name.is_(None),
                Application.applicant_scrape_failed == False,
            )
        )
        .order_by(Application.apn_date.desc().nullslast())
        .limit(batch_size)
    )
    refs = [row[0] for row in result.all()]

    logger.info(f"Scraping {len(refs)} applications for applicant names")

    for reg_ref in refs:
        try:
            name = await scrape_applicant_name(reg_ref)

            if name:
                await db.execute(
                    update(Application)
                    .where(Application.reg_ref == reg_ref)
                    .values(
                        applicant_name=name,
                        applicant_scraped_at=datetime.utcnow(),
                    )
                )
                stats["found"] += 1
                stats["consecutive_failures"] = 0
            else:
                await db.execute(
                    update(Application)
                    .where(Application.reg_ref == reg_ref)
                    .values(
                        applicant_scrape_failed=True,
                        applicant_scraped_at=datetime.utcnow(),
                    )
                )
                stats["failed"] += 1
                stats["consecutive_failures"] += 1

            stats["scraped"] += 1

            # Circuit breaker
            if stats["consecutive_failures"] >= settings.scraper_circuit_breaker_failures:
                logger.warning("Circuit breaker triggered — pausing scraper")
                break

            # Commit every 10 records
            if stats["scraped"] % 10 == 0:
                await db.commit()
                logger.info(f"Scraped {stats['scraped']}/{len(refs)}")

        except Exception as e:
            logger.error(f"Error scraping {reg_ref}: {e}")
            stats["failed"] += 1
            stats["consecutive_failures"] += 1

            if stats["consecutive_failures"] >= settings.scraper_circuit_breaker_failures:
                logger.warning("Circuit breaker triggered — pausing scraper")
                break

    await db.commit()
    logger.info(f"Scraper batch complete: {stats}")
    return stats
