"""PlanSearch — CRO Enricher.

Looks up company details from the Companies Registration Office (CRO)
for applicants that appear to be companies (contain Ltd, DAC, plc, etc).
CRO API: https://api.cro.ie/
"""

import logging
from typing import Optional

import httpx
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AdminConfig
from app.utils.crypto import decrypt_value

logger = logging.getLogger(__name__)

CRO_API_BASE = "https://api.cro.ie/api/v1"
COMPANY_INDICATORS = [
    "ltd", "limited", "dac", "plc", "uc", "clg", "teoranta", "teo",
]


def looks_like_company(name: str) -> bool:
    """Check if an applicant name looks like a registered company."""
    if not name:
        return False
    name_lower = name.lower()
    return any(ind in name_lower for ind in COMPANY_INDICATORS)


async def get_cro_api_key(db: AsyncSession) -> Optional[str]:
    """Retrieve the CRO API key from encrypted admin_config."""
    result = await db.execute(
        select(AdminConfig).where(AdminConfig.key == "cro_api_key")
    )
    config = result.scalar_one_or_none()
    if not config:
        logger.warning("CRO API key not found in admin_config")
        return None
    if config.encrypted:
        return decrypt_value(config.value)
    return config.value


async def lookup_company(name: str, api_key: str) -> Optional[dict]:
    """Search CRO API for a company by name."""
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            r = await client.get(
                f"{CRO_API_BASE}/company/search",
                params={"company_name": name, "max_results": 1},
                headers={
                    "Accept": "application/json",
                    "Authorization": f"Bearer {api_key}",
                },
            )
            if r.status_code != 200:
                return None
            data = r.json()
            results = data.get("companies", data.get("results", []))
            if results:
                return results[0]
    except Exception as e:
        logger.error(f"CRO API error for {name}: {e}")
    return None


async def run_cro_enrichment(
    db: AsyncSession,
    progress: Optional[dict] = None,
    limit: int = 500,
) -> dict:
    """Enrich applicant data with CRO company information.

    Accepts an optional progress dict (same shape as sync_progress) that
    the admin API polls every 3 seconds to show live counts in the UI.
    """
    logger.info("Starting CRO enrichment...")
    stats = {"processed": 0, "enriched": 0, "not_found": 0, "errors": 0}

    api_key = await get_cro_api_key(db)
    if not api_key:
        if progress:
            progress["running"] = False
        return {"error": "CRO API key not configured. Set it via the admin UI."}

    result = await db.execute(
        text("""
            SELECT id, reg_ref, applicant_name
            FROM applications
            WHERE applicant_name IS NOT NULL
              AND cro_number IS NULL
              AND cro_enriched_at IS NULL
            ORDER BY apn_date DESC NULLS LAST
            LIMIT :limit
        """),
        {"limit": limit},
    )
    rows = result.fetchall()

    total = len(rows)
    logger.info(f"Found {total} applications to enrich")

    if progress:
        progress["total"] = total

    for row in rows:
        # Check for stop signal
        if progress and progress.get("stop_requested"):
            logger.info("CRO enrichment stop requested")
            break

        if not looks_like_company(row.applicant_name):
            stats["processed"] += 1
            if progress:
                progress["processed"] = stats["processed"]
            # Mark as checked so we don't retry individuals
            await db.execute(
                text("UPDATE applications SET cro_enriched_at = NOW() WHERE id = :id"),
                {"id": row.id},
            )
            continue

        try:
            company = await lookup_company(row.applicant_name, api_key)
            if company:
                await db.execute(
                    text("""
                        UPDATE applications
                        SET cro_number = :cro_number,
                            cro_enriched_at = NOW()
                        WHERE id = :id
                    """),
                    {
                        "cro_number": str(company.get("company_number", "")),
                        "id": row.id,
                    },
                )
                stats["enriched"] += 1
            else:
                await db.execute(
                    text("UPDATE applications SET cro_enriched_at = NOW() WHERE id = :id"),
                    {"id": row.id},
                )
                stats["not_found"] += 1

            stats["processed"] += 1
            if progress:
                progress["processed"] = stats["processed"]
                progress["errors"] = stats["errors"]

            if stats["processed"] % 50 == 0:
                await db.commit()
                logger.info(f"CRO enrichment progress: {stats}")

        except Exception as e:
            logger.error(f"CRO error for {row.reg_ref}: {e}")
            stats["errors"] += 1
            if progress:
                progress["errors"] = stats["errors"]

    await db.commit()

    if progress:
        progress["running"] = False
        progress["stop_requested"] = False

    logger.info(f"CRO enrichment complete: {stats}")
    return stats

