"""PlanSearch — AI Value Estimation + Significance Scoring.

Uses Claude Haiku to estimate construction values from structural data
(floor area, unit count, site area, land use code, description).
Also computes a 0-100 significance score for commercial relevance.
"""

import json
import logging
from datetime import datetime
from typing import Optional

import httpx
from sqlalchemy import select, and_, or_, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models import Application, AdminConfig, CostBenchmark

logger = logging.getLogger(__name__)
settings = get_settings()

VALUE_ESTIMATION_PROMPT = """You are estimating the construction value of an Irish planning application.
Use these Irish construction cost benchmarks (2026):
- Apartments (private): €350,000/unit average
- Apartments (social): €310,000/unit average
- Houses (scheme): €240,000/unit average
- One-off houses: €220,000/unit average
- Student accommodation: €110,000/bed
- Hotel: €230,000/room
- Office: €3,500/m²
- Retail/restaurant: €2,300/m²
- Industrial/warehouse: €1,100/m²
- Data centre: €11,000/m²
- Mixed use: calculate each component separately

Application data:
Reference: {reg_ref}
Authority: {planning_authority}
Description: {description}
Land Use Code: {land_use_code}
Floor Area: {floor_area} m²
Number of Residential Units: {num_units}
Site Area: {site_area} m²
Development Category: {dev_category}
One-Off House: {one_off_house}

Instructions:
1. Identify the primary development type
2. Select the most appropriate benchmark
3. Calculate a low and high estimate
4. State your primary basis (units × rate OR m² × rate)
5. Flag if data is insufficient for reliable estimate

Respond ONLY in valid JSON:
{{
  "value_low": 0,
  "value_high": 0,
  "primary_basis": "45 units × €320,000",
  "development_type_for_valuation": "Private Apartments",
  "confidence": "high|medium|low",
  "notes": "optional explanation"
}}"""


def should_estimate_value(app: Application) -> bool:
    """Check if an application has sufficient data for value estimation.

    Minimum requirement: either (FloorArea > 0) OR (NumResidentialUnits > 0)
    OR (description length > 50 chars).
    """
    if app.value_estimated_at:
        return False  # Already estimated
    if app.floor_area and app.floor_area > 0:
        return True
    if app.num_residential_units and app.num_residential_units > 0:
        return True
    if app.proposal and len(app.proposal) > 50:
        return True
    return False


def compute_significance_score(app: Application) -> int:
    """Score 0-100. >50 = significant. >80 = high priority."""
    score = 0

    # Value-based scoring (40 points max)
    value = app.est_value_high or 0
    if value >= 50_000_000:
        score += 40
    elif value >= 10_000_000:
        score += 30
    elif value >= 2_000_000:
        score += 20
    elif value >= 500_000:
        score += 10

    # Unit count (20 points max)
    units = app.num_residential_units or 0
    if units >= 100:
        score += 20
    elif units >= 50:
        score += 15
    elif units >= 20:
        score += 10
    elif units >= 5:
        score += 5

    # Development type (20 points max)
    cat = app.dev_category or ""
    if cat in ("hotel_accommodation", "commercial_office", "industrial_warehouse"):
        score += 20
    elif cat in ("residential_new_build", "mixed_use"):
        score += 15
    elif cat in ("commercial_retail",):
        score += 10

    # Decision outcome (10 points max)
    if app.decision and "grant" in app.decision.lower():
        score += 10

    # Explicitly NOT one-off house (10 points)
    if not app.one_off_house:
        score += 10

    return min(score, 100)


async def get_claude_api_key(db: AsyncSession) -> Optional[str]:
    """Get Claude API key from admin config."""
    from app.utils.crypto import decrypt_value

    result = await db.execute(
        select(AdminConfig).where(AdminConfig.key == "claude_api_key")
    )
    config = result.scalar_one_or_none()
    if not config:
        return None
    return decrypt_value(config.value) if config.encrypted else config.value


async def estimate_value_with_claude(
    app: Application,
    api_key: str,
) -> Optional[dict]:
    """Call Claude API to estimate construction value."""
    prompt = VALUE_ESTIMATION_PROMPT.format(
        reg_ref=app.reg_ref,
        planning_authority=app.planning_authority or "Unknown",
        description=app.proposal or "No description",
        land_use_code=app.land_use_code or "Not specified",
        floor_area=app.floor_area or "Not specified",
        num_units=app.num_residential_units or "Not specified",
        site_area=app.area_of_site or "Not specified",
        dev_category=app.dev_category or "Not classified",
        one_off_house="Yes" if app.one_off_house else "No",
    )

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                "https://api.anthropic.com/v1/messages",
                headers={
                    "x-api-key": api_key,
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json",
                },
                json={
                    "model": "claude-3-haiku-20240307",
                    "max_tokens": 300,
                    "messages": [{"role": "user", "content": prompt}],
                },
            )

        if resp.status_code != 200:
            logger.warning(f"Claude API error {resp.status_code} for {app.reg_ref}")
            return None

        data = resp.json()
        content = data["content"][0]["text"]

        # Parse JSON response
        result = json.loads(content)
        return result

    except (json.JSONDecodeError, KeyError, IndexError) as e:
        logger.warning(f"Failed to parse Claude response for {app.reg_ref}: {e}")
        return None
    except Exception as e:
        logger.error(f"Claude API error for {app.reg_ref}: {e}")
        return None


async def run_value_estimation(
    db: AsyncSession,
    batch_size: int = 200,
) -> dict:
    """Run AI value estimation on applications with sufficient data."""
    stats = {"estimated": 0, "skipped": 0, "failed": 0, "scored": 0}

    api_key = await get_claude_api_key(db)
    if not api_key:
        logger.error("No Claude API key configured — skipping value estimation")
        return stats

    # Get applications needing estimation
    result = await db.execute(
        select(Application)
        .where(
            Application.value_estimated_at.is_(None),
            or_(
                Application.floor_area > 0,
                Application.num_residential_units > 0,
                func.length(Application.proposal) > 50,
            ),
        )
        .order_by(Application.apn_date.desc().nullslast())
        .limit(batch_size)
    )
    applications = result.scalars().all()

    logger.info(f"Value estimation: Processing {len(applications)} applications")

    for app in applications:
        if not should_estimate_value(app):
            stats["skipped"] += 1
            continue

        estimation = await estimate_value_with_claude(app, api_key)

        if estimation:
            app.est_value_low = estimation.get("value_low")
            app.est_value_high = estimation.get("value_high")
            app.est_value_basis = estimation.get("primary_basis")
            app.est_value_type = estimation.get("development_type_for_valuation")
            app.est_value_confidence = estimation.get("confidence")
            app.value_estimated_at = datetime.utcnow()
            stats["estimated"] += 1
        else:
            stats["failed"] += 1

        # Update significance score regardless
        app.significance_score = compute_significance_score(app)
        stats["scored"] += 1

        if stats["estimated"] % 25 == 0:
            await db.commit()
            logger.info(f"Value estimation: {stats['estimated']} estimated, {stats['failed']} failed")

    await db.commit()
    logger.info(f"Value estimation: Complete — {stats}")
    return stats


async def run_significance_scoring(db: AsyncSession, limit: int = 0) -> dict:
    """Recompute significance scores for all applications."""
    stats = {"scored": 0}

    query = select(Application)
    if limit > 0:
        query = query.limit(limit)

    result = await db.execute(query)
    applications = result.scalars().all()

    for app in applications:
        new_score = compute_significance_score(app)
        if app.significance_score != new_score:
            app.significance_score = new_score
            stats["scored"] += 1

        if stats["scored"] % 10000 == 0 and stats["scored"] > 0:
            await db.commit()

    await db.commit()
    logger.info(f"Significance scoring: {stats['scored']} updated")
    return stats


# ── Benchmark-Based Value Estimation ─────────────────────────────────────
# No Claude API calls needed — pure DB lookup from cost_benchmarks table.

CATEGORY_TO_BENCHMARK = {
    "residential_new_build": "apartments_overall_range",
    "residential_extension": "housing_suburban",
    "residential_conversion": "housing_suburban",
    "hotel_accommodation": "hotel_3_4_star",
    "commercial_office": "offices_shell_and_core",
    "commercial_retail": "retail_fitout",
    "industrial_warehouse": "industrial_warehouse_shell",
    "data_centre": "data_centre",
    "mixed_use": "apartments_overall_range",
    "student_accommodation": "student_accommodation",
    "change_of_use": "offices_fitout_medium",
}


async def _get_benchmark(db: AsyncSession, building_type: str) -> Optional[dict]:
    """Fetch the latest benchmark for a building type."""
    from sqlalchemy import text as sql_text
    result = await db.execute(
        sql_text("""
            SELECT cost_per_sqm_low, cost_per_sqm_high,
                   cost_per_unit_low, cost_per_unit_high,
                   cost_basis, exclusions, infocard_name, valid_from
            FROM cost_benchmarks
            WHERE building_type = :bt
            ORDER BY valid_from DESC
            LIMIT 1
        """),
        {"bt": building_type},
    )
    row = result.fetchone()
    return dict(row._mapping) if row else None


def _calc_estimate(
    benchmark: dict,
    floor_area: Optional[float],
    num_units: Optional[int],
) -> Optional[dict]:
    """Calculate value estimate from benchmark and application data."""
    low = high = None
    basis = None

    # Unit-based calculation (apartments, hotel keys)
    if (
        num_units and num_units > 0
        and benchmark.get("cost_per_unit_low")
        and benchmark.get("cost_per_unit_high")
    ):
        low = num_units * benchmark["cost_per_unit_low"]
        high = num_units * benchmark["cost_per_unit_high"]
        basis = (
            f"{num_units} units × "
            f"€{benchmark['cost_per_unit_low']:,}–"
            f"€{benchmark['cost_per_unit_high']:,}/unit"
        )

    # Floor area based calculation
    elif (
        floor_area and floor_area > 0
        and floor_area < 500_000  # Cap: 500k m² — anything larger is bad data
        and benchmark.get("cost_per_sqm_low")
        and benchmark.get("cost_per_sqm_high")
    ):
        low = floor_area * benchmark["cost_per_sqm_low"]
        high = floor_area * benchmark["cost_per_sqm_high"]
        basis = (
            f"{floor_area:,.0f}m² × "
            f"€{benchmark['cost_per_sqm_low']:,}–"
            f"€{benchmark['cost_per_sqm_high']:,}/m²"
        )

    if not low or not high:
        return None

    # Sanity check — ignore implausibly small values
    if high < 10_000:
        return None

    # Sanity check — ignore implausibly large values
    # (Largest Irish planning application ever was ~€3bn)
    if high > 5_000_000_000:  # €5bn cap
        logger.warning(
            f"Value estimate too high (€{high:,.0f}), likely bad floor_area data. Skipping."
        )
        return None

    return {
        "est_value_low": int(low),
        "est_value_high": int(high),
        "est_value_basis": basis,
        "est_value_confidence": "medium",
        "est_value_type": benchmark.get(
            "infocard_name", "Mitchell McDermott 2026"
        ),
    }


async def run_benchmark_estimation(
    db: AsyncSession, limit: Optional[int] = None
) -> dict:
    """Run benchmark-based value estimation for classified applications.

    Uses the cost_benchmarks table (Mitchell McDermott InfoCards) — no AI needed.
    """
    from sqlalchemy import text as sql_text

    logger.info("Starting benchmark value estimation...")
    stats = {"processed": 0, "estimated": 0, "no_data": 0, "errors": 0}

    result = await db.execute(
        sql_text("""
            SELECT id, reg_ref, dev_category, floor_area,
                   num_residential_units
            FROM applications
            WHERE dev_category IS NOT NULL
              AND est_value_high IS NULL
              AND (
                (floor_area IS NOT NULL AND floor_area > 0)
                OR (num_residential_units IS NOT NULL
                    AND num_residential_units > 0)
              )
            ORDER BY apn_date DESC NULLS LAST
            LIMIT :limit
        """),
        {"limit": limit or 999999},
    )
    rows = result.fetchall()

    logger.info(f"Found {len(rows)} applications to estimate")

    # Pre-load all benchmarks to avoid repeated DB queries
    benchmarks: dict = {}
    for category, building_type in CATEGORY_TO_BENCHMARK.items():
        benchmark = await _get_benchmark(db, building_type)
        if benchmark:
            benchmarks[category] = benchmark

    for row in rows:
        try:
            benchmark = benchmarks.get(row.dev_category)
            if not benchmark:
                stats["no_data"] += 1
                stats["processed"] += 1
                continue

            est = _calc_estimate(
                benchmark,
                row.floor_area,
                row.num_residential_units,
            )

            if est:
                await db.execute(
                    sql_text("""
                        UPDATE applications
                        SET est_value_low = :low,
                            est_value_high = :high,
                            est_value_basis = :basis,
                            est_value_confidence = :confidence,
                            est_value_type = :est_type,
                            value_estimated_at = NOW()
                        WHERE id = :id
                    """),
                    {
                        "low": est["est_value_low"],
                        "high": est["est_value_high"],
                        "basis": est["est_value_basis"],
                        "confidence": est["est_value_confidence"],
                        "est_type": est["est_value_type"],
                        "id": row.id,
                    },
                )
                stats["estimated"] += 1
            else:
                stats["no_data"] += 1

            stats["processed"] += 1
            if stats["processed"] % 1000 == 0:
                await db.commit()
                logger.info(f"Benchmark estimation progress: {stats}")

        except Exception as e:
            logger.error(f"Error estimating value for {row.reg_ref}: {e}")
            stats["errors"] += 1

    await db.commit()
    logger.info(f"Benchmark estimation complete: {stats}")
    return stats

