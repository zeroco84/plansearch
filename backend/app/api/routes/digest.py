"""PlanSearch — Digest API Routes.

Public endpoints for weekly digest feed and RSS.
No authentication required.
"""

from fastapi import APIRouter, Depends
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import WeeklyDigest
from app.workers.digest import generate_rss_xml

router = APIRouter()


@router.get("/digest/latest")
async def get_latest_digest(db: AsyncSession = Depends(get_db)):
    """Get the latest weekly digest as JSON. Free, open, no auth required."""
    result = await db.execute(
        select(WeeklyDigest)
        .where(WeeklyDigest.published == True)
        .order_by(WeeklyDigest.week_start.desc())
        .limit(1)
    )
    digest = result.scalar_one_or_none()

    if not digest:
        return {
            "week_start": None,
            "week_end": None,
            "total_entries": 0,
            "entries": [],
        }

    return {
        "week_start": str(digest.week_start),
        "week_end": str(digest.week_end),
        "generated_at": str(digest.generated_at),
        "total_entries": digest.total_entries,
        "entries": digest.digest_data.get("entries", []) if digest.digest_data else [],
    }


@router.get("/feed/weekly-digest.xml")
async def get_rss_feed(db: AsyncSession = Depends(get_db)):
    """RSS feed of weekly significant approvals. Subscribable in any RSS reader."""
    result = await db.execute(
        select(WeeklyDigest)
        .where(WeeklyDigest.published == True)
        .order_by(WeeklyDigest.week_start.desc())
        .limit(1)
    )
    digest = result.scalar_one_or_none()

    if not digest or not digest.digest_data:
        xml = '<?xml version="1.0" encoding="UTF-8"?><rss version="2.0"><channel><title>PlanSearch</title></channel></rss>'
        return Response(content=xml, media_type="application/rss+xml")

    xml = generate_rss_xml(digest.digest_data, digest.week_start)
    return Response(content=xml, media_type="application/rss+xml")
