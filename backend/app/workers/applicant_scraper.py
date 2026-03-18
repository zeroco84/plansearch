"""PlanSearch — Applicant Name Scraper.

Scrapes applicant names from Irish planning portals continuously.
Runs as a background asyncio task, 1 request per 4 seconds.
Prioritises 2023+ applications, then works backwards.

Portal systems (confirmed from live testing):
- www.eplanning.ie — most Irish counties
  Applicant URL: {link_app_details}/Applicant
  Name in table row: "Applicant name: John Murphy"
- planning.agileapplications.ie — Dublin councils
  Same URL pattern: {link_app_details}/Applicant
"""

import asyncio
import logging
from datetime import datetime
from typing import Optional

import httpx
from bs4 import BeautifulSoup
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.database import engine

logger = logging.getLogger(__name__)

USER_AGENT = "Mozilla/5.0 (compatible; PlanSearch/1.0; +https://plansearch.cc)"
RATE_LIMIT_SECONDS = 4.0
BATCH_SIZE = 25
LOOP_PAUSE_SECONDS = 30

# Module-level progress tracker — polled by the admin UI
scraper_progress = {
    "running": False,
    "scraped_today": 0,
    "names_found_today": 0,
    "last_scraped_ref": None,
    "started_at": None,
    "error": None,
}


async def fetch_applicant_name(
    url: str, client: httpx.AsyncClient
) -> Optional[str]:
    """Fetch applicant name from portal URL by appending /Applicant."""
    applicant_url = url.rstrip("/") + "/Applicant"
    try:
        response = await client.get(
            applicant_url,
            headers={"User-Agent": USER_AGENT},
            timeout=20.0,
            follow_redirects=True,
        )
        if response.status_code != 200:
            return None

        soup = BeautifulSoup(response.text, "html.parser")

        # Find table rows containing "Applicant name:" / "Applicant Name"
        for row in soup.find_all("tr"):
            text_content = row.get_text(" ", strip=True)
            if "Applicant name" in text_content or "Applicant Name" in text_content:
                cells = row.find_all(["td", "th"])
                for i, cell in enumerate(cells):
                    cell_text = cell.get_text(strip=True)
                    if "Applicant name" in cell_text or "Applicant Name" in cell_text:
                        # Try next cell first
                        if i + 1 < len(cells):
                            name = cells[i + 1].get_text(strip=True)
                            if name and len(name) > 1:
                                return name
                        # Try extracting from same cell after the label
                        name = (
                            cell_text
                            .replace("Applicant name:", "")
                            .replace("Applicant Name:", "")
                            .strip()
                        )
                        if name and len(name) > 1:
                            return name

        # Also check definition lists
        for dt in soup.find_all("dt"):
            if "applicant" in dt.get_text(strip=True).lower():
                dd = dt.find_next_sibling("dd")
                if dd:
                    name = dd.get_text(strip=True)
                    if name and len(name) > 1 and name.lower() not in (
                        "n/a", "none", "-",
                    ):
                        return name

        return None

    except Exception as e:
        logger.debug(f"Error fetching {applicant_url}: {e}")
        return None


async def get_next_batch(session_factory) -> list:
    """Get next batch of applications to scrape."""
    async with session_factory() as db:
        # First try 2023+ applications
        result = await db.execute(
            text("""
                SELECT id, reg_ref, link_app_details
                FROM applications
                WHERE applicant_name IS NULL
                  AND applicant_scraped_at IS NULL
                  AND link_app_details IS NOT NULL
                  AND link_app_details NOT LIKE '%corkcity%'
                  AND apn_date >= '2023-01-01'
                ORDER BY apn_date DESC NULLS LAST
                LIMIT :limit
            """),
            {"limit": BATCH_SIZE},
        )
        rows = result.fetchall()

        if not rows:
            # Fall back to all remaining applications
            result = await db.execute(
                text("""
                    SELECT id, reg_ref, link_app_details
                    FROM applications
                    WHERE applicant_name IS NULL
                      AND applicant_scraped_at IS NULL
                      AND link_app_details IS NOT NULL
                      AND link_app_details NOT LIKE '%corkcity%'
                    ORDER BY apn_date DESC NULLS LAST
                    LIMIT :limit
                """),
                {"limit": BATCH_SIZE},
            )
            rows = result.fetchall()

        return list(rows)


async def process_batch(rows: list, session_factory) -> dict:
    """Process one batch of applications."""
    stats = {"processed": 0, "found": 0, "failed": 0}

    async with httpx.AsyncClient() as client:
        for row in rows:
            if not scraper_progress["running"]:
                break

            try:
                name = await fetch_applicant_name(row.link_app_details, client)

                async with session_factory() as db:
                    await db.execute(
                        text("""
                            UPDATE applications
                            SET applicant_name = :name,
                                applicant_scraped_at = NOW()
                            WHERE id = :id
                        """),
                        {"name": name, "id": row.id},
                    )
                    await db.commit()

                stats["processed"] += 1
                if name:
                    stats["found"] += 1
                    scraper_progress["names_found_today"] += 1

                scraper_progress["scraped_today"] += 1
                scraper_progress["last_scraped_ref"] = row.reg_ref

            except Exception as e:
                logger.error(f"Error scraping {row.reg_ref}: {e}")
                stats["failed"] += 1
                # Mark as attempted so we don't retry forever
                try:
                    async with session_factory() as db:
                        await db.execute(
                            text("""
                                UPDATE applications
                                SET applicant_scraped_at = NOW()
                                WHERE id = :id
                            """),
                            {"id": row.id},
                        )
                        await db.commit()
                except Exception:
                    pass

            # Rate limit — be polite to the portals
            await asyncio.sleep(RATE_LIMIT_SECONDS)

    return stats


async def run_applicant_scraper_loop():
    """Run the applicant scraper continuously as a background loop.

    1 request per 4 seconds = ~900/hour = ~21,600/day.
    """
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    scraper_progress["running"] = True
    scraper_progress["started_at"] = datetime.utcnow().isoformat()
    scraper_progress["scraped_today"] = 0
    scraper_progress["names_found_today"] = 0
    scraper_progress["error"] = None

    logger.info("Applicant name scraper loop started — 1 req/4s")

    try:
        while scraper_progress["running"]:
            rows = await get_next_batch(session_factory)

            if not rows:
                logger.info(
                    "Applicant scraper: all applications scraped, sleeping 10 min"
                )
                await asyncio.sleep(600)
                continue

            stats = await process_batch(rows, session_factory)
            logger.info(f"Applicant scraper batch: {stats}")

            # Short pause between batches
            await asyncio.sleep(LOOP_PAUSE_SECONDS)

    except asyncio.CancelledError:
        logger.info("Applicant scraper loop cancelled")
    except Exception as e:
        logger.error(f"Applicant scraper loop crashed: {e}")
        scraper_progress["error"] = str(e)
    finally:
        scraper_progress["running"] = False
        logger.info("Applicant scraper loop stopped")
