"""PlanSearch — CRO Company Enrichment Worker.

Enriches planning applications with Companies Registration Office data
when the applicant name matches a registered Irish company.
"""

import logging
from datetime import datetime
from typing import Optional

import httpx
from sqlalchemy import select, update, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models import Application, Company, ApplicationCompany, AdminConfig
from app.utils.crypto import decrypt_value

logger = logging.getLogger(__name__)
settings = get_settings()

COMPANY_SIGNALS = [
    "Limited", "Ltd", "DAC", "plc", "LLP",
    "Unlimited", "Holdings", "Developments",
    "Properties", "Construction", "Group", "Co.",
]


def looks_like_company(name: str) -> bool:
    """Check if a name likely belongs to a company."""
    if not name:
        return False
    name_lower = name.lower()
    return any(signal.lower() in name_lower for signal in COMPANY_SIGNALS)


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


async def search_cro_company(
    company_name: str,
    api_key: str,
) -> Optional[dict]:
    """Search the CRO API for a company by name.

    Returns the best matching company record or None.
    """
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(
                "https://services.cro.ie/cro/api/company/search",
                params={"company_name": company_name, "skip": 0, "take": 5},
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Accept": "application/json",
                },
            )

        if response.status_code != 200:
            logger.warning(f"CRO API returned {response.status_code}")
            return None

        data = response.json()
        results = data if isinstance(data, list) else data.get("results", [])

        if not results:
            return None

        return find_best_match(company_name, results)

    except Exception as e:
        logger.error(f"CRO API error: {e}")
        return None


def find_best_match(query: str, results: list) -> Optional[dict]:
    """Find the best matching company from CRO search results."""
    if not results:
        return None

    query_lower = query.lower().strip()

    # Exact match
    for r in results:
        name = r.get("company_name", r.get("companyName", ""))
        if name.lower().strip() == query_lower:
            return r

    # Contains match
    for r in results:
        name = r.get("company_name", r.get("companyName", ""))
        if query_lower in name.lower() or name.lower() in query_lower:
            return r

    # Return first result as fallback
    return results[0]


async def get_company_details(
    cro_number: str,
    api_key: str,
) -> Optional[dict]:
    """Get detailed company information from CRO API."""
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(
                f"https://services.cro.ie/cro/api/company/{cro_number}",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Accept": "application/json",
                },
            )

        if response.status_code != 200:
            return None

        return response.json()

    except Exception as e:
        logger.error(f"CRO company detail error: {e}")
        return None


async def enrich_with_cro(
    db: AsyncSession,
    reg_ref: str,
    applicant_name: str,
    api_key: str,
) -> bool:
    """Enrich a single application with CRO company data.

    Returns True if enrichment was successful.
    """
    if not looks_like_company(applicant_name):
        return False

    match = await search_cro_company(applicant_name, api_key)
    if not match:
        return False

    cro_number = str(match.get("cro_number", match.get("companyNumber", match.get("company_num", ""))))
    if not cro_number:
        return False

    # Get detailed company info
    details = await get_company_details(cro_number, api_key)

    company_name = match.get("company_name", match.get("companyName", applicant_name))

    # Upsert company record
    existing = await db.execute(
        select(Company).where(Company.cro_number == cro_number)
    )
    company = existing.scalar_one_or_none()

    if not company:
        company = Company(
            cro_number=cro_number,
            company_name=company_name,
            company_status=details.get("company_status", details.get("status", "")) if details else None,
            registered_address=details.get("registered_address", details.get("address", "")) if details else None,
            incorporation_date=None,  # Parse from details if available
            company_type=details.get("company_type", details.get("type", "")) if details else None,
            directors=details.get("directors", []) if details else None,
            raw_cro_data=details,
            fetched_at=datetime.utcnow(),
        )
        db.add(company)
        await db.flush()

    # Link application to company
    app_result = await db.execute(
        select(Application).where(Application.reg_ref == reg_ref)
    )
    app = app_result.scalar_one_or_none()

    if app:
        # Check if link already exists
        link_result = await db.execute(
            select(ApplicationCompany).where(
                and_(
                    ApplicationCompany.application_id == app.id,
                    ApplicationCompany.company_id == company.id,
                )
            )
        )
        if not link_result.scalar_one_or_none():
            link = ApplicationCompany(
                application_id=app.id,
                company_id=company.id,
                match_confidence=0.8,  # Default confidence for name match
            )
            db.add(link)

        # Update application CRO fields
        app.cro_number = cro_number
        app.cro_enriched_at = datetime.utcnow()

    return True


async def run_cro_enrichment_batch(
    db: AsyncSession,
    batch_size: int = 100,
) -> dict:
    """Run CRO enrichment for a batch of applications.

    Only processes applications that:
    - Have an applicant name
    - Haven't been CRO-enriched yet
    - Have a company-like name
    """
    stats = {"processed": 0, "enriched": 0, "skipped": 0, "failed": 0}

    api_key = await get_cro_api_key(db)
    if not api_key:
        return {"error": "CRO API key not configured. Set it via the admin UI."}

    # Get applications with company-like applicant names
    result = await db.execute(
        select(Application)
        .where(
            and_(
                Application.applicant_name.isnot(None),
                Application.cro_enriched_at.is_(None),
            )
        )
        .order_by(Application.apn_date.desc().nullslast())
        .limit(batch_size)
    )
    applications = result.scalars().all()

    for app in applications:
        try:
            if not looks_like_company(app.applicant_name):
                stats["skipped"] += 1
                continue

            success = await enrich_with_cro(db, app.reg_ref, app.applicant_name, api_key)

            if success:
                stats["enriched"] += 1
            else:
                stats["failed"] += 1

            stats["processed"] += 1

            if stats["processed"] % 10 == 0:
                await db.commit()

        except Exception as e:
            logger.error(f"Error enriching {app.reg_ref}: {e}")
            stats["failed"] += 1

    await db.commit()
    logger.info(f"CRO enrichment batch complete: {stats}")
    return stats
