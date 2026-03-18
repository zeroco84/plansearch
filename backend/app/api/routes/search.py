"""PlanSearch — Search API endpoint.

GET /api/search — AI-powered intent parsing + structured database query.
  - Claude Haiku extracts dev_category, location, decision from natural language
  - Category and authority filters applied as exact database conditions
  - Full-text search only used for remaining keywords
  - Composable with manual advanced filter overrides
"""

import json
import logging
import time
from typing import Optional, List

import httpx
from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, text, select, and_, or_, case, literal_column
from sqlalchemy.ext.asyncio import AsyncSession
from geoalchemy2.functions import ST_DWithin, ST_SetSRID, ST_MakePoint, ST_X, ST_Y

from app.database import get_db
from app.models import Application, AdminConfig
from app.schemas import SearchResponse, ApplicationSummary
from app.utils.crypto import decrypt_value

router = APIRouter()
logger = logging.getLogger(__name__)


# ── AI Intent Parsing ────────────────────────────────────────────────────

INTENT_PROMPT = """Extract search intent from this Irish planning search query.

Query: "{query}"

Available dev_categories:
residential_new_build, residential_extension, residential_conversion,
hotel_accommodation, student_accommodation, commercial_retail,
commercial_office, industrial_warehouse, data_centre, mixed_use,
protected_structure, telecommunications, renewable_energy, signage,
change_of_use, demolition, other

Available planning authorities (use exact spelling):
Dublin City Council, Fingal County Council, South Dublin County Council,
Dún Laoghaire-Rathdown County Council, Cork City Council, Cork County Council,
Galway City Council, Galway County Council, Kerry County Council,
Kildare County Council, Kilkenny County Council, Limerick City & County Council,
Meath County Council, Wicklow County Council, Wexford County Council,
Donegal County Council, Tipperary County Council, Waterford City and County Council,
Clare County Council, Mayo County Council, Sligo County Council,
Leitrim County Council, Roscommon County Council, Longford County Council,
Westmeath County Council, Offaly County Council, Laois County Council,
Louth County Council, Cavan County Council, Monaghan County Council,
Carlow County Council

Respond ONLY with JSON:
{{
  "dev_category": "exact category from list above, or null",
  "planning_authorities": ["exact name(s) from list above"] or [],
  "keywords": "any remaining search terms not captured above, or null",
  "decision": "granted or refused or pending, or null"
}}

Examples:
"student accommodation galway" -> {{"dev_category": "student_accommodation", "planning_authorities": ["Galway City Council", "Galway County Council"], "keywords": null, "decision": null}}
"refused hotels cork" -> {{"dev_category": "hotel_accommodation", "planning_authorities": ["Cork City Council", "Cork County Council"], "keywords": null, "decision": "refused"}}
"data centre kildare" -> {{"dev_category": "data_centre", "planning_authorities": ["Kildare County Council"], "keywords": null, "decision": null}}
"apartments near DART" -> {{"dev_category": "residential_new_build", "planning_authorities": [], "keywords": "DART", "decision": null}}
"protected structure Dublin 4" -> {{"dev_category": "protected_structure", "planning_authorities": ["Dublin City Council"], "keywords": "Dublin 4", "decision": null}}
"wind farm donegal" -> {{"dev_category": "renewable_energy", "planning_authorities": ["Donegal County Council"], "keywords": "wind farm", "decision": null}}
"office block dublin" -> {{"dev_category": "commercial_office", "planning_authorities": ["Dublin City Council", "Fingal County Council", "South Dublin County Council", "Dún Laoghaire-Rathdown County Council"], "keywords": null, "decision": null}}"""


# Fallback location parsing (used when AI is unavailable)
LOCATION_AUTHORITY_MAP = {
    "dublin": [
        "Dublin City Council",
        "Fingal County Council",
        "Dún Laoghaire-Rathdown County Council",
        "South Dublin County Council",
    ],
    "cork": ["Cork City Council", "Cork County Council"],
    "galway": ["Galway City Council", "Galway County Council"],
    "limerick": ["Limerick City & County Council"],
    "waterford": ["Waterford City & County Council"],
    "tipperary": ["Tipperary County Council"],
    "kilkenny": ["Kilkenny County Council"],
    "wexford": ["Wexford County Council"],
    "wicklow": ["Wicklow County Council"],
    "kildare": ["Kildare County Council"],
    "meath": ["Meath County Council"],
    "louth": ["Louth County Council"],
    "offaly": ["Offaly County Council"],
    "laois": ["Laois County Council"],
    "longford": ["Longford County Council"],
    "westmeath": ["Westmeath County Council"],
    "carlow": ["Carlow County Council"],
    "clare": ["Clare County Council"],
    "kerry": ["Kerry County Council"],
    "mayo": ["Mayo County Council"],
    "roscommon": ["Roscommon County Council"],
    "sligo": ["Sligo County Council"],
    "leitrim": ["Leitrim County Council"],
    "donegal": ["Donegal County Council"],
    "cavan": ["Cavan County Council"],
    "monaghan": ["Monaghan County Council"],
    "fingal": ["Fingal County Council"],
    "dun laoghaire": ["Dún Laoghaire-Rathdown County Council"],
    "dlr": ["Dún Laoghaire-Rathdown County Council"],
    "south dublin": ["South Dublin County Council"],
}


async def _get_claude_api_key(db: AsyncSession) -> Optional[str]:
    """Retrieve the Claude API key from encrypted admin_config."""
    try:
        result = await db.execute(
            select(AdminConfig).where(AdminConfig.key == "claude_api_key")
        )
        config = result.scalar_one_or_none()
        if not config:
            return None
        if config.encrypted:
            return decrypt_value(config.value)
        return config.value
    except Exception:
        return None


async def parse_search_intent(query: str, db: AsyncSession) -> dict:
    """Use Claude Haiku to extract structured search intent from natural language."""
    fallback = {
        "dev_category": None,
        "planning_authorities": [],
        "keywords": query,
        "decision": None,
    }

    # Skip AI for very short queries
    if len(query.strip()) < 3:
        return fallback

    api_key = await _get_claude_api_key(db)
    if not api_key:
        logger.warning("No Claude API key — falling back to text search")
        return _fallback_parse(query)

    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.post(
                "https://api.anthropic.com/v1/messages",
                headers={
                    "x-api-key": api_key,
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json",
                },
                json={
                    "model": "claude-haiku-4-5-20251001",
                    "max_tokens": 200,
                    "messages": [
                        {"role": "user", "content": INTENT_PROMPT.format(query=query)}
                    ],
                },
            )
            resp.raise_for_status()
            data = resp.json()
            raw_text = data["content"][0]["text"].strip()

            # Strip markdown code fences if present
            if raw_text.startswith("```"):
                raw_text = raw_text.split("```")[1].lstrip("json").strip()

            intent = json.loads(raw_text)

            # Validate dev_category
            valid_categories = {
                "residential_new_build", "residential_extension", "residential_conversion",
                "hotel_accommodation", "student_accommodation", "commercial_retail",
                "commercial_office", "industrial_warehouse", "data_centre", "mixed_use",
                "protected_structure", "telecommunications", "renewable_energy", "signage",
                "change_of_use", "demolition", "other",
            }
            if intent.get("dev_category") and intent["dev_category"] not in valid_categories:
                intent["dev_category"] = None

            # Validate decision
            if intent.get("decision") and intent["decision"] not in ("granted", "refused", "pending"):
                intent["decision"] = None

            return intent

    except Exception as e:
        logger.warning(f"AI intent parsing failed for '{query}': {e}")
        return _fallback_parse(query)


def _fallback_parse(query: str) -> dict:
    """Simple text-based location extraction as fallback when AI unavailable."""
    query_lower = query.lower().strip()
    for location_term, authorities in sorted(
        LOCATION_AUTHORITY_MAP.items(), key=lambda x: len(x[0]), reverse=True
    ):
        if location_term in query_lower:
            cleaned = query_lower.replace(location_term, "").strip()
            while "  " in cleaned:
                cleaned = cleaned.replace("  ", " ")
            return {
                "dev_category": None,
                "planning_authorities": authorities,
                "keywords": cleaned if cleaned else None,
                "decision": None,
            }
    return {
        "dev_category": None,
        "planning_authorities": [],
        "keywords": query,
        "decision": None,
    }


# ── Search endpoint ──────────────────────────────────────────────────────

@router.get("/search", response_model=SearchResponse)
async def search_applications(
    q: Optional[str] = Query(None, description="Full-text search query"),
    category: Optional[str] = Query(None, description="Development category filter (overrides AI)"),
    decision: Optional[str] = Query(None, description="Decision status filter (overrides AI)"),
    applicant: Optional[str] = Query(None, description="Fuzzy applicant name search"),
    location: Optional[str] = Query(None, description="Fuzzy location search"),
    year_from: Optional[int] = Query(None, description="Minimum year"),
    year_to: Optional[int] = Query(None, description="Maximum year"),
    lat: Optional[float] = Query(None, description="Latitude for proximity search"),
    lng: Optional[float] = Query(None, description="Longitude for proximity search"),
    radius_m: Optional[int] = Query(None, description="Radius in metres for proximity search"),
    authority: Optional[str] = Query(None, description="Planning authority filter (overrides AI)"),
    lifecycle_stage: Optional[str] = Query(None, description="Lifecycle stage filter"),
    value_min: Optional[int] = Query(None, description="Minimum estimated value (€)"),
    value_max: Optional[int] = Query(None, description="Maximum estimated value (€)"),
    one_off_house: Optional[bool] = Query(None, description="Filter one-off houses"),
    sort: str = Query("date_desc", description="Sort order"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(25, ge=1, le=100, description="Results per page"),
    db: AsyncSession = Depends(get_db),
):
    """Search planning applications with AI intent parsing + structured filters.

    When a free-text query is provided, it is sent to Claude Haiku to extract:
    - dev_category (exact DB filter)
    - planning_authorities (location filter)
    - decision (status filter)
    - keywords (remaining full-text search terms)

    Manual filter params override the AI-inferred values.
    """
    start_time = time.time()

    # ── Parse intent from free text query ──
    text_query = q or ""
    intent = None
    inferred_location: Optional[str] = None

    # Only use AI intent when there's a text query and no manual overrides
    if text_query.strip():
        intent = await parse_search_intent(text_query, db)

        # Derive friendly location label
        authorities = intent.get("planning_authorities", [])
        if authorities:
            inferred_location = (
                authorities[0].split(" County")[0].split(" City")[0]
            )

    # ── Build query conditions ──
    conditions = []

    # Category filter — manual override takes precedence over AI
    effective_category = category or (intent.get("dev_category") if intent else None)
    if effective_category:
        conditions.append(Application.dev_category == effective_category)

    # Authority filter — manual override takes precedence
    if authority:
        conditions.append(Application.planning_authority == authority)
    elif intent and intent.get("planning_authorities"):
        conditions.append(
            Application.planning_authority.in_(intent["planning_authorities"])
        )

    # Decision filter — manual override takes precedence
    effective_decision = decision
    if not effective_decision and intent and intent.get("decision"):
        ai_decision = intent["decision"]
        if ai_decision == "granted":
            effective_decision = "GRANTED"
        elif ai_decision == "refused":
            effective_decision = "REFUSED"
        elif ai_decision == "pending":
            effective_decision = None  # handled below

    if effective_decision:
        conditions.append(Application.decision.ilike(f"%{effective_decision}%"))
    elif intent and intent.get("decision") == "pending":
        conditions.append(
            or_(Application.decision.is_(None), Application.decision == "N/A")
        )

    # Full-text search — only on remaining keywords (not the whole query)
    keywords = (intent.get("keywords") if intent else text_query) or ""
    if keywords.strip():
        ts_query = func.plainto_tsquery("english", keywords)
        conditions.append(Application.search_vector.op("@@")(ts_query))

    # Fuzzy applicant search
    if applicant:
        conditions.append(Application.applicant_name.ilike(f"%{applicant}%"))

    # Fuzzy location search
    if location:
        conditions.append(Application.location.ilike(f"%{location}%"))

    # Year range filter
    if year_from:
        conditions.append(Application.year >= year_from)
    if year_to:
        conditions.append(Application.year <= year_to)

    # Spatial proximity filter
    if lat is not None and lng is not None and radius_m:
        point = ST_SetSRID(ST_MakePoint(lng, lat), 4326)
        conditions.append(
            ST_DWithin(Application.location_point, point, radius_m, use_spheroid=True)
        )

    # Lifecycle stage filter
    if lifecycle_stage:
        conditions.append(Application.lifecycle_stage == lifecycle_stage)

    # Value range filter
    if value_min is not None:
        conditions.append(Application.est_value_high >= value_min)
    if value_max is not None:
        conditions.append(Application.est_value_high <= value_max)

    # One-off house filter
    if one_off_house is not None:
        conditions.append(Application.one_off_house == one_off_house)

    # ── Execute queries ──
    where_clause = and_(*conditions) if conditions else text("1=1")

    count_query = select(func.count()).select_from(Application).where(where_clause)
    count_result = await db.execute(count_query)
    total = count_result.scalar() or 0

    data_query = select(
        Application,
        ST_Y(Application.location_point).label("lat"),
        ST_X(Application.location_point).label("lng"),
    ).where(where_clause)

    # Add relevance score for keyword searches
    if keywords.strip():
        ts_query = func.plainto_tsquery("english", keywords)
        rank = func.ts_rank(Application.search_vector, ts_query)
        data_query = data_query.add_columns(rank.label("relevance_score"))

    # Sorting
    if sort == "date_desc":
        data_query = data_query.order_by(Application.apn_date.desc().nullslast())
    elif sort == "date_asc":
        data_query = data_query.order_by(Application.apn_date.asc().nullsfirst())
    elif sort == "relevance" and keywords.strip():
        ts_query = func.plainto_tsquery("english", keywords)
        data_query = data_query.order_by(
            func.ts_rank(Application.search_vector, ts_query).desc()
        )
    elif sort == "value_desc":
        data_query = data_query.order_by(Application.est_value_high.desc().nullslast())
    elif sort == "significance":
        data_query = data_query.order_by(Application.significance_score.desc())
    else:
        data_query = data_query.order_by(Application.apn_date.desc().nullslast())

    # Pagination
    offset = (page - 1) * page_size
    data_query = data_query.offset(offset).limit(page_size)

    result = await db.execute(data_query)
    rows = result.all()

    # Transform results
    results = []
    for row in rows:
        # Row structure: (Application, lat, lng) or (Application, lat, lng, relevance)
        if isinstance(row, tuple):
            app = row[0]
            lat_val = row[1]
            lng_val = row[2]
            relevance = row[3] if len(row) > 3 else None
        else:
            app = row
            lat_val = None
            lng_val = None
            relevance = None

        results.append(
            ApplicationSummary(
                id=app.id,
                reg_ref=app.reg_ref,
                apn_date=app.apn_date,
                proposal=app.proposal[:200] if app.proposal else None,
                location=app.location,
                decision=app.decision,
                dev_category=app.dev_category,
                dev_subcategory=app.dev_subcategory,
                applicant_name=app.applicant_name,
                lat=lat_val,
                lng=lng_val,
                relevance_score=float(relevance) if relevance else None,
                planning_authority=app.planning_authority,
                lifecycle_stage=app.lifecycle_stage,
                est_value_low=app.est_value_low,
                est_value_high=app.est_value_high,
                significance_score=app.significance_score,
                num_residential_units=app.num_residential_units,
                floor_area=app.floor_area,
            )
        )

    query_time_ms = (time.time() - start_time) * 1000
    total_pages = max(1, (total + page_size - 1) // page_size)

    return SearchResponse(
        results=results,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
        query_time_ms=round(query_time_ms, 2),
        inferred_location=inferred_location,
        intent=intent,
    )
