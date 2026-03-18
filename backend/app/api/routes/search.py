"""PlanSearch — Search API endpoint.

GET /api/search — single optimised PostgreSQL query combining:
  - tsvector full-text search
  - trigram fuzzy matching
  - PostGIS spatial filtering
  - faceted filters (category, decision, year, etc.)
  - Location-aware query parsing (auto-detects Irish counties/cities)
"""

import time
from typing import Optional, List
from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, text, select, and_, or_, case, literal_column
from sqlalchemy.ext.asyncio import AsyncSession
from geoalchemy2.functions import ST_DWithin, ST_SetSRID, ST_MakePoint, ST_X, ST_Y

from app.database import get_db
from app.models import Application
from app.schemas import SearchResponse, ApplicationSummary

router = APIRouter()


# ── Location-aware query parsing ─────────────────────────────────────────

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


def parse_location_from_query(query: str) -> tuple[str, list[str]]:
    """Extract location intent from a search query.

    Returns (cleaned_query, list_of_matching_authorities).

    Examples:
    - "apartments dublin" → ("apartments", [DCC, Fingal, DLRCC, SDCC])
    - "hotel cork" → ("hotel", [Cork City, Cork County])
    - "data centre kildare" → ("data centre", [Kildare CC])
    - "protected structure" → ("protected structure", [])
    """
    query_lower = query.lower().strip()
    matched_authorities: list[str] = []
    cleaned_query = query_lower

    # Sort by length descending so "dun laoghaire" matches before "dublin", etc.
    for location_term, authorities in sorted(
        LOCATION_AUTHORITY_MAP.items(),
        key=lambda x: len(x[0]),
        reverse=True,
    ):
        if location_term in query_lower:
            matched_authorities = authorities
            # Remove the location term from the search query
            cleaned_query = query_lower.replace(location_term, "").strip()
            # Clean up any double spaces left behind
            while "  " in cleaned_query:
                cleaned_query = cleaned_query.replace("  ", " ")
            break

    return cleaned_query, matched_authorities


# ── Search endpoint ──────────────────────────────────────────────────────

@router.get("/search", response_model=SearchResponse)
async def search_applications(
    q: Optional[str] = Query(None, description="Full-text search query"),
    category: Optional[str] = Query(None, description="Development category filter"),
    decision: Optional[str] = Query(None, description="Decision status filter"),
    applicant: Optional[str] = Query(None, description="Fuzzy applicant name search"),
    location: Optional[str] = Query(None, description="Fuzzy location search"),
    year_from: Optional[int] = Query(None, description="Minimum year"),
    year_to: Optional[int] = Query(None, description="Maximum year"),
    lat: Optional[float] = Query(None, description="Latitude for proximity search"),
    lng: Optional[float] = Query(None, description="Longitude for proximity search"),
    radius_m: Optional[int] = Query(None, description="Radius in metres for proximity search"),
    authority: Optional[str] = Query(None, description="Planning authority filter (national)"),
    lifecycle_stage: Optional[str] = Query(None, description="Lifecycle stage filter"),
    value_min: Optional[int] = Query(None, description="Minimum estimated value (€)"),
    value_max: Optional[int] = Query(None, description="Maximum estimated value (€)"),
    one_off_house: Optional[bool] = Query(None, description="Filter one-off houses"),
    sort: str = Query("date_desc", description="Sort order"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(25, ge=1, le=100, description="Results per page"),
    db: AsyncSession = Depends(get_db),
):
    """Search planning applications with full-text, fuzzy, spatial, and faceted filtering.

    All parameters are optional and fully composable.
    Location terms in the query (e.g. "apartments dublin") are automatically
    detected and applied as planning_authority filters.
    """
    start_time = time.time()

    # ── Parse location intent from free text query ──
    text_query = q or ""
    inferred_authorities: list[str] = []
    inferred_location: Optional[str] = None

    if q and not authority:
        text_query, inferred_authorities = parse_location_from_query(q)
        if inferred_authorities:
            # Derive a friendly label: "Dublin", "Cork", etc.
            inferred_location = (
                inferred_authorities[0]
                .split(" County")[0]
                .split(" City")[0]
            )

    # Build base query
    conditions = []

    # Full-text search using plainto_tsquery (handles multi-word naturally)
    if text_query:
        ts_query = func.plainto_tsquery("english", text_query)
        conditions.append(Application.search_vector.op("@@")(ts_query))

    # Category filter
    if category:
        conditions.append(Application.dev_category == category)

    # Decision filter
    if decision:
        conditions.append(Application.decision.ilike(f"%{decision}%"))

    # Fuzzy applicant search using trigram
    if applicant:
        conditions.append(
            Application.applicant_name.ilike(f"%{applicant}%")
        )

    # Fuzzy location search using trigram
    if location:
        conditions.append(
            Application.location.ilike(f"%{location}%")
        )

    # Year range filter
    if year_from:
        conditions.append(Application.year >= year_from)
    if year_to:
        conditions.append(Application.year <= year_to)

    # Spatial proximity filter
    if lat is not None and lng is not None and radius_m:
        point = ST_SetSRID(ST_MakePoint(lng, lat), 4326)
        conditions.append(
            ST_DWithin(
                Application.location_point,
                point,
                radius_m,
                use_spheroid=True,
            )
        )

    # Planning authority filter — explicit param OR inferred from query
    if authority:
        conditions.append(Application.planning_authority == authority)
    elif inferred_authorities:
        conditions.append(
            Application.planning_authority.in_(inferred_authorities)
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

    # Build count query
    where_clause = and_(*conditions) if conditions else text("1=1")

    count_query = select(func.count()).select_from(Application).where(where_clause)
    count_result = await db.execute(count_query)
    total = count_result.scalar() or 0

    # Build data query with sorting
    data_query = select(Application).where(where_clause)

    # Add relevance score for full-text queries
    if text_query:
        ts_query = func.plainto_tsquery("english", text_query)
        rank = func.ts_rank(Application.search_vector, ts_query)
        data_query = data_query.add_columns(rank.label("relevance_score"))

    # Sorting
    if sort == "date_desc":
        data_query = data_query.order_by(Application.apn_date.desc().nullslast())
    elif sort == "date_asc":
        data_query = data_query.order_by(Application.apn_date.asc().nullsfirst())
    elif sort == "relevance" and text_query:
        ts_query = func.plainto_tsquery("english", text_query)
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
        if text_query and len(row) > 1:
            app, relevance = row
        else:
            app = row[0] if isinstance(row, tuple) else row
            relevance = None

        lat_val = None
        lng_val = None
        if app.location_point is not None:
            try:
                # Extract lat/lng from the geometry
                coord_result = await db.execute(
                    select(
                        ST_Y(Application.location_point).label("lat"),
                        ST_X(Application.location_point).label("lng"),
                    ).where(Application.id == app.id)
                )
                coords = coord_result.first()
                if coords:
                    lat_val = coords.lat
                    lng_val = coords.lng
            except Exception:
                pass

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
    )
