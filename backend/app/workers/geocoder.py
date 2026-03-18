"""PlanSearch — Address Geocoder.

Geocodes planning application locations using OpenStreetMap Nominatim.
Free, no API key required. Rate limited to 1 request per second per OSM policy.
Runs as a continuous background loop, prioritising recent applications.
"""

import asyncio
import logging
from datetime import datetime
from typing import Optional

import httpx
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.database import engine

logger = logging.getLogger(__name__)

NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
RATE_LIMIT_SECONDS = 1.1  # OSM policy: max 1 request/second
BATCH_SIZE = 50
LOOP_PAUSE_SECONDS = 10

# Module-level progress tracker — polled by the admin UI
geocoder_progress = {
    "running": False,
    "geocoded_today": 0,
    "found_today": 0,
    "last_ref": None,
    "started_at": None,
    "error": None,
}


def clean_address(location: str, planning_authority: str) -> str:
    """Clean and augment address for geocoding."""
    if not location:
        return ""
    clean = location.strip()
    # Add Ireland to help Nominatim disambiguate
    if "ireland" not in clean.lower() and "co." not in clean.lower():
        clean = f"{clean}, Ireland"
    return clean


async def geocode_address(
    location: str,
    planning_authority: str,
    client: httpx.AsyncClient,
) -> Optional[tuple[float, float]]:
    """Geocode an address using Nominatim. Returns (lat, lng) or None."""
    address = clean_address(location, planning_authority)
    if not address:
        return None

    try:
        response = await client.get(
            NOMINATIM_URL,
            params={
                "q": address,
                "format": "json",
                "limit": 1,
                "countrycodes": "ie",
            },
            headers={
                "User-Agent": "PlanSearch/1.0 (https://plansearch.cc; planning data research)",
            },
            timeout=10.0,
        )
        if response.status_code != 200:
            return None

        results = response.json()
        if results:
            lat = float(results[0]["lat"])
            lng = float(results[0]["lon"])
            # Validate coordinates are within Ireland bounding box
            if 51.2 <= lat <= 55.5 and -10.7 <= lng <= -5.9:
                return lat, lng

        return None

    except Exception as e:
        logger.debug(f"Geocoding error for '{address}': {e}")
        return None


async def geocode_batch(session_factory) -> dict:
    """Geocode one batch of applications."""
    stats = {"processed": 0, "found": 0, "failed": 0}

    async with session_factory() as db:
        # Prioritise recent applications without coordinates
        result = await db.execute(
            text("""
                SELECT id, reg_ref, location, planning_authority
                FROM applications
                WHERE location_point IS NULL
                  AND location IS NOT NULL
                  AND location != ''
                  AND geocoded_at IS NULL
                ORDER BY apn_date DESC NULLS LAST
                LIMIT :limit
            """),
            {"limit": BATCH_SIZE},
        )
        rows = result.fetchall()

    if not rows:
        return stats

    async with httpx.AsyncClient() as client:
        for row in rows:
            if not geocoder_progress["running"]:
                break

            try:
                coords = await geocode_address(
                    row.location,
                    row.planning_authority or "",
                    client,
                )

                async with session_factory() as db:
                    if coords:
                        lat, lng = coords
                        await db.execute(
                            text("""
                                UPDATE applications
                                SET location_point = ST_SetSRID(
                                        ST_MakePoint(:lng, :lat), 4326
                                    ),
                                    geocoded_at = NOW()
                                WHERE id = :id
                            """),
                            {"lat": lat, "lng": lng, "id": row.id},
                        )
                        stats["found"] += 1
                        geocoder_progress["found_today"] += 1
                    else:
                        await db.execute(
                            text("""
                                UPDATE applications
                                SET geocoded_at = NOW()
                                WHERE id = :id
                            """),
                            {"id": row.id},
                        )

                    await db.commit()

                stats["processed"] += 1
                geocoder_progress["geocoded_today"] += 1
                geocoder_progress["last_ref"] = row.reg_ref

                # OSM rate limit — 1 request per second
                await asyncio.sleep(RATE_LIMIT_SECONDS)

            except Exception as e:
                logger.error(f"Error geocoding {row.reg_ref}: {e}")
                stats["failed"] += 1

    return stats


async def run_geocoder_loop():
    """Run geocoder continuously as a background loop.

    1 request per 1.1 seconds ≈ 3,270/hour ≈ 78,500/day.
    """
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    geocoder_progress["running"] = True
    geocoder_progress["started_at"] = datetime.utcnow().isoformat()
    geocoder_progress["geocoded_today"] = 0
    geocoder_progress["found_today"] = 0
    geocoder_progress["error"] = None

    logger.info("Geocoder loop started — 1 req/sec (OSM Nominatim)")

    try:
        while geocoder_progress["running"]:
            stats = await geocode_batch(session_factory)

            if stats["processed"] == 0:
                logger.info("Geocoder: nothing to process, sleeping 10 minutes")
                await asyncio.sleep(600)
                continue

            logger.info(f"Geocoder batch: {stats}")
            await asyncio.sleep(LOOP_PAUSE_SECONDS)

    except asyncio.CancelledError:
        logger.info("Geocoder loop cancelled")
    except Exception as e:
        logger.error(f"Geocoder loop crashed: {e}")
        geocoder_progress["error"] = str(e)
    finally:
        geocoder_progress["running"] = False
        logger.info("Geocoder loop stopped")
