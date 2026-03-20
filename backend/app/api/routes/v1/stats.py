"""PlanSearch Public API v1 — Statistics & Authority List.

GET /v1/stats       — Aggregate statistics (cached hourly)
GET /v1/authorities — All 43 planning authorities with counts
"""

import logging
import time
from typing import Optional

from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import Application, ApiKey
from app.middleware.api_auth import (
    require_api_key, wrap_response, add_rate_limit_headers, _log_usage,
)

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/stats")
async def get_stats(
    request: Request,
    response: Response,
    api_key: ApiKey = Depends(require_api_key),
    db: AsyncSession = Depends(get_db),
):
    """Aggregate statistics: totals, breakdown by authority/category/decision/lifecycle."""
    start = time.time()

    # Total applications
    total_result = await db.execute(select(func.count(Application.id)))
    total = total_result.scalar() or 0

    # By category
    cat_result = await db.execute(
        select(Application.dev_category, func.count(Application.id))
        .where(Application.dev_category.isnot(None))
        .group_by(Application.dev_category)
        .order_by(func.count(Application.id).desc())
    )
    categories = {row[0]: row[1] for row in cat_result.all()}

    # By decision
    dec_result = await db.execute(
        select(Application.decision, func.count(Application.id))
        .where(Application.decision.isnot(None))
        .group_by(Application.decision)
        .order_by(func.count(Application.id).desc())
    )
    decisions = {row[0]: row[1] for row in dec_result.all()}

    # By lifecycle stage
    lifecycle_result = await db.execute(
        select(Application.lifecycle_stage, func.count(Application.id))
        .where(Application.lifecycle_stage.isnot(None))
        .group_by(Application.lifecycle_stage)
        .order_by(func.count(Application.id).desc())
    )
    lifecycle = {row[0]: row[1] for row in lifecycle_result.all()}

    # By year (last 15 years)
    year_result = await db.execute(
        select(Application.year, func.count(Application.id))
        .where(Application.year.isnot(None))
        .group_by(Application.year)
        .order_by(Application.year.desc())
        .limit(15)
    )
    years = {str(row[0]): row[1] for row in year_result.all()}

    query_time_ms = (time.time() - start) * 1000
    await _log_usage(api_key.id, "/v1/stats", 200, int(query_time_ms), db)
    add_rate_limit_headers(response, request)

    return wrap_response({
        "total_applications": total,
        "categories": categories,
        "decisions": decisions,
        "lifecycle_stages": lifecycle,
        "years": years,
    }, request)


@router.get("/authorities")
async def list_authorities(
    request: Request,
    response: Response,
    jurisdiction: Optional[str] = None,
    api_key: ApiKey = Depends(require_api_key),
    db: AsyncSession = Depends(get_db),
):
    """List all 43 planning authorities with record counts and jurisdiction."""
    start = time.time()

    query = (
        select(
            Application.planning_authority,
            Application.data_source,
            func.count(Application.id).label("count"),
        )
        .where(Application.planning_authority.isnot(None))
        .group_by(Application.planning_authority, Application.data_source)
        .order_by(func.count(Application.id).desc())
    )

    result = await db.execute(query)
    rows = result.all()

    NI_SOURCES = {"NIDFT"}
    authorities = []
    for row in rows:
        j = "ni" if row.data_source in NI_SOURCES else "roi"
        if jurisdiction and j != jurisdiction:
            continue
        authorities.append({
            "name": row.planning_authority,
            "jurisdiction": j,
            "application_count": row.count,
        })

    query_time_ms = (time.time() - start) * 1000
    await _log_usage(api_key.id, "/v1/authorities", 200, int(query_time_ms), db)
    add_rate_limit_headers(response, request)

    return wrap_response({
        "authorities": authorities,
        "total": len(authorities),
    }, request)
