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
