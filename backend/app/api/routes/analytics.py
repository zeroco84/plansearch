"""PlanSearch — Analytics API endpoints.

Public endpoints for the /analytics dashboard. All queries run against
PostgreSQL and are cached in Redis for 1–6 hours.

10 endpoints covering: pipeline gap, permissions by year, lifecycle funnel,
refusal rates, value by county, data centres, renewables, top applications,
extensions trend, and commencement lag.
"""

import logging
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.utils.redis_cache import cached

logger = logging.getLogger(__name__)
router = APIRouter()

CACHE_1H = 3600
CACHE_6H = 21600


# ── Helper ──────────────────────────────────────────────────────────────


def _rows_to_dicts(result) -> list[dict]:
    """Convert SQLAlchemy result rows to list of dicts."""
    return [dict(row._mapping) for row in result.all()]


# ── 1. Pipeline Gap ─────────────────────────────────────────────────────


async def _compute_pipeline_gap(db: AsyncSession):
    result = await db.execute(text("""
        SELECT
            a.planning_authority,
            COUNT(*) AS unbuilt_count,
            COALESCE(SUM(a.est_value_high), 0) AS unbuilt_value
        FROM applications a
        LEFT JOIN commencement_notices cn ON cn.reg_ref = a.reg_ref
        WHERE a.decision IN ('granted', 'conditional')
          AND a.dev_category IN (
              'residential_new_build', 'residential_apartments', 'mixed_use'
          )
          AND a.dec_date >= '2019-01-01'
          AND a.dec_date < '2024-01-01'
          AND cn.id IS NULL
        GROUP BY a.planning_authority
        ORDER BY unbuilt_count DESC
    """))
    return _rows_to_dicts(result)


@router.get("/analytics/pipeline-gap")
async def pipeline_gap(db: AsyncSession = Depends(get_db)):
    """Granted residential with no BCMS match, by county."""
    data = await cached("analytics:pipeline-gap", CACHE_1H, _compute_pipeline_gap, db)
    return {"data": data}


# ── 2. Permissions by Year ──────────────────────────────────────────────


async def _compute_permissions_by_year(db: AsyncSession):
    result = await db.execute(text("""
        SELECT
            year,
            dev_category,
            COUNT(*) AS count
        FROM applications
        WHERE year >= 2015 AND year <= 2025
          AND dev_category IS NOT NULL
        GROUP BY year, dev_category
        ORDER BY year, count DESC
    """))
    return _rows_to_dicts(result)


@router.get("/analytics/permissions-by-year")
async def permissions_by_year(db: AsyncSession = Depends(get_db)):
    """Application counts by year and dev_category."""
    data = await cached(
        "analytics:permissions-by-year", CACHE_1H,
        _compute_permissions_by_year, db,
    )
    return {"data": data}


# ── 3. Lifecycle Funnel ─────────────────────────────────────────────────


async def _compute_lifecycle_funnel(db: AsyncSession):
    result = await db.execute(text("""
        SELECT 'all_residential' AS stage, COUNT(*) AS count
        FROM applications WHERE dev_category LIKE 'residential%%'
        UNION ALL
        SELECT 'granted', COUNT(*)
        FROM applications
        WHERE dev_category LIKE 'residential%%'
          AND decision IN ('granted', 'conditional')
        UNION ALL
        SELECT 'commenced', COUNT(*)
        FROM applications
        WHERE dev_category LIKE 'residential%%'
          AND lifecycle_stage = 'under_construction'
        UNION ALL
        SELECT 'completed', COUNT(*)
        FROM applications
        WHERE dev_category LIKE 'residential%%'
          AND lifecycle_stage = 'complete'
    """))
    return _rows_to_dicts(result)


@router.get("/analytics/lifecycle-funnel")
async def lifecycle_funnel(db: AsyncSession = Depends(get_db)):
    """Lifecycle stage counts: received → granted → commenced → completed."""
    data = await cached(
        "analytics:lifecycle-funnel", CACHE_1H,
        _compute_lifecycle_funnel, db,
    )
    return {"data": data}


# ── 4. Refusal Rates ────────────────────────────────────────────────────


async def _compute_refusal_rates(db: AsyncSession):
    result = await db.execute(text("""
        SELECT
            planning_authority,
            dev_category,
            COUNT(*) FILTER (WHERE decision IN ('granted', 'conditional')) AS granted,
            COUNT(*) FILTER (WHERE decision = 'refused') AS refused,
            COUNT(*) AS total,
            ROUND(
                COUNT(*) FILTER (WHERE decision = 'refused')::numeric /
                NULLIF(COUNT(*), 0) * 100, 1
            ) AS refusal_rate
        FROM applications
        WHERE decision IS NOT NULL
          AND dev_category IS NOT NULL
        GROUP BY planning_authority, dev_category
        ORDER BY planning_authority
    """))
    return _rows_to_dicts(result)


@router.get("/analytics/refusal-rates")
async def refusal_rates(db: AsyncSession = Depends(get_db)):
    """Grant/refuse counts by council and dev_category."""
    data = await cached(
        "analytics:refusal-rates", CACHE_1H,
        _compute_refusal_rates, db,
    )
    return {"data": data}


# ── 5. Value by County ──────────────────────────────────────────────────


async def _compute_value_by_county(db: AsyncSession):
    result = await db.execute(text("""
        SELECT
            planning_authority,
            dev_category,
            COUNT(*) AS count,
            COALESCE(SUM(est_value_high), 0) AS total_value,
            COALESCE(AVG(est_value_high), 0)::bigint AS avg_value
        FROM applications
        WHERE decision IN ('granted', 'conditional')
          AND est_value_high IS NOT NULL
          AND est_value_high > 0
        GROUP BY planning_authority, dev_category
        ORDER BY total_value DESC
    """))
    return _rows_to_dicts(result)


@router.get("/analytics/value-by-county")
async def value_by_county(db: AsyncSession = Depends(get_db)):
    """Aggregated est_value_high by county and category."""
    data = await cached(
        "analytics:value-by-county", CACHE_1H,
        _compute_value_by_county, db,
    )
    return {"data": data}


# ── 6. Data Centres ─────────────────────────────────────────────────────


async def _compute_data_centres(db: AsyncSession):
    result = await db.execute(text("""
        SELECT
            reg_ref, planning_authority, proposal, location, decision,
            dec_date, est_value_high, lifecycle_stage, year,
            applicant_name,
            ST_Y(location_point::geometry) AS lat,
            ST_X(location_point::geometry) AS lng
        FROM applications
        WHERE dev_category = 'data_centre'
        ORDER BY year DESC NULLS LAST, est_value_high DESC NULLS LAST
    """))
    return _rows_to_dicts(result)


@router.get("/analytics/data-centres")
async def data_centres(db: AsyncSession = Depends(get_db)):
    """All data_centre applications with geocodes."""
    data = await cached(
        "analytics:data-centres", CACHE_6H,
        _compute_data_centres, db,
    )
    return {"data": data}


# ── 7. Renewables by County ─────────────────────────────────────────────


async def _compute_renewables_by_county(db: AsyncSession):
    result = await db.execute(text("""
        SELECT
            planning_authority,
            year,
            COUNT(*) AS total,
            COUNT(*) FILTER (WHERE decision IN ('granted', 'conditional')) AS granted,
            COUNT(*) FILTER (WHERE decision = 'refused') AS refused,
            ROUND(
                COUNT(*) FILTER (WHERE decision IN ('granted', 'conditional'))::numeric /
                NULLIF(COUNT(*), 0) * 100, 1
            ) AS grant_rate
        FROM applications
        WHERE dev_category = 'renewable_energy'
        GROUP BY planning_authority, year
        ORDER BY planning_authority, year
    """))
    return _rows_to_dicts(result)


@router.get("/analytics/renewables-by-county")
async def renewables_by_county(db: AsyncSession = Depends(get_db)):
    """renewable_energy grant rates by county and year."""
    data = await cached(
        "analytics:renewables-by-county", CACHE_1H,
        _compute_renewables_by_county, db,
    )
    return {"data": data}


# ── 8. Top Applications ─────────────────────────────────────────────────


async def _compute_top_applications(db: AsyncSession):
    result = await db.execute(text("""
        SELECT
            reg_ref, planning_authority, proposal, location,
            applicant_name, dev_category, est_value_high,
            decision, lifecycle_stage, dec_date
        FROM applications
        WHERE decision IN ('granted', 'conditional')
          AND dec_date >= NOW() - INTERVAL '12 months'
          AND est_value_high IS NOT NULL
          AND est_value_high > 0
        ORDER BY est_value_high DESC
        LIMIT 20
    """))
    return _rows_to_dicts(result)


@router.get("/analytics/top-applications")
async def top_applications(db: AsyncSession = Depends(get_db)):
    """Top 20 by value, last 12 months."""
    data = await cached(
        "analytics:top-applications", CACHE_1H,
        _compute_top_applications, db,
    )
    return {"data": data}


# ── 9. Extensions Trend ─────────────────────────────────────────────────


async def _compute_extensions_trend(db: AsyncSession):
    result = await db.execute(text("""
        SELECT
            year,
            planning_authority,
            COUNT(*) AS count
        FROM applications
        WHERE dev_category = 'residential_extension'
          AND year >= 2015
        GROUP BY year, planning_authority
        ORDER BY year, count DESC
    """))
    return _rows_to_dicts(result)


@router.get("/analytics/extensions-trend")
async def extensions_trend(db: AsyncSession = Depends(get_db)):
    """residential_extension counts by year and county."""
    data = await cached(
        "analytics:extensions-trend", CACHE_1H,
        _compute_extensions_trend, db,
    )
    return {"data": data}


# ── 10. Commencement Lag ────────────────────────────────────────────────


async def _compute_commencement_lag(db: AsyncSession):
    result = await db.execute(text("""
        SELECT
            (EXTRACT(YEAR FROM AGE(cn.cn_commencement_date, a.dec_date))::integer * 12 +
             EXTRACT(MONTH FROM AGE(cn.cn_commencement_date, a.dec_date))::integer
            ) AS months_lag,
            COUNT(*) AS count
        FROM applications a
        JOIN commencement_notices cn ON cn.reg_ref = a.reg_ref
        WHERE a.decision IN ('granted', 'conditional')
          AND cn.cn_commencement_date IS NOT NULL
          AND a.dec_date IS NOT NULL
          AND cn.cn_commencement_date > a.dec_date
        GROUP BY months_lag
        ORDER BY months_lag
    """))
    return _rows_to_dicts(result)


@router.get("/analytics/commencement-lag")
async def commencement_lag(db: AsyncSession = Depends(get_db)):
    """Distribution of months between grant and BCMS commencement."""
    data = await cached(
        "analytics:commencement-lag", CACHE_6H,
        _compute_commencement_lag, db,
    )
    return {"data": data}
