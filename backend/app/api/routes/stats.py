"""PlanSearch — Stats API endpoint.

GET /api/stats — Platform-wide statistics.
"""

from fastapi import APIRouter, Depends
from sqlalchemy import select, func, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import Application, SyncLog, ApplicationDocument
from app.schemas import StatsResponse

router = APIRouter()


@router.get("/stats", response_model=StatsResponse)
async def get_stats(db: AsyncSession = Depends(get_db)):
    """Get platform-wide statistics for the dashboard."""

    # Total applications
    total_result = await db.execute(select(func.count(Application.id)))
    total_applications = total_result.scalar() or 0

    # Classified count
    classified_result = await db.execute(
        select(func.count(Application.id)).where(Application.dev_category.isnot(None))
    )
    total_classified = classified_result.scalar() or 0

    # Applicant names scraped
    scraped_result = await db.execute(
        select(func.count(Application.id)).where(Application.applicant_name.isnot(None))
    )
    total_applicants_scraped = scraped_result.scalar() or 0

    # CRO enriched
    cro_result = await db.execute(
        select(func.count(Application.id)).where(Application.cro_number.isnot(None))
    )
    total_cro_enriched = cro_result.scalar() or 0

    # Documents
    docs_result = await db.execute(select(func.count(ApplicationDocument.id)))
    total_documents = docs_result.scalar() or 0

    # Category breakdown
    cat_result = await db.execute(
        select(Application.dev_category, func.count(Application.id))
        .where(Application.dev_category.isnot(None))
        .group_by(Application.dev_category)
        .order_by(func.count(Application.id).desc())
    )
    categories = {row[0]: row[1] for row in cat_result.all()}

    # Decision breakdown
    dec_result = await db.execute(
        select(Application.decision, func.count(Application.id))
        .where(Application.decision.isnot(None))
        .group_by(Application.decision)
        .order_by(func.count(Application.id).desc())
    )
    decisions = {row[0]: row[1] for row in dec_result.all()}

    # Year breakdown (last 10 years)
    year_result = await db.execute(
        select(Application.year, func.count(Application.id))
        .where(Application.year.isnot(None))
        .group_by(Application.year)
        .order_by(Application.year.desc())
        .limit(15)
    )
    years = {str(row[0]): row[1] for row in year_result.all()}

    # Last sync
    sync_result = await db.execute(
        select(SyncLog)
        .where(SyncLog.status == "completed")
        .order_by(SyncLog.completed_at.desc())
        .limit(1)
    )
    last_sync_entry = sync_result.scalar_one_or_none()

    return StatsResponse(
        total_applications=total_applications,
        total_classified=total_classified,
        total_applicants_scraped=total_applicants_scraped,
        total_cro_enriched=total_cro_enriched,
        total_documents=total_documents,
        categories=categories,
        decisions=decisions,
        years=years,
        last_sync=last_sync_entry.completed_at if last_sync_entry else None,
    )
