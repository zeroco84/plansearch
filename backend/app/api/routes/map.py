"""PlanSearch — Map API endpoint.

GET /api/map/points — GeoJSON FeatureCollection for map display (legacy).
GET /api/map/pins  — Viewport-based pin loading for clustered map.
"""

from typing import Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, text, and_, func
from sqlalchemy.ext.asyncio import AsyncSession
from geoalchemy2.functions import ST_X, ST_Y, ST_DWithin, ST_SetSRID, ST_MakePoint

from app.database import get_db
from app.models import Application

router = APIRouter()


@router.get("/map/pins")
async def get_map_pins(
    north: float = Query(..., description="North bound latitude"),
    south: float = Query(..., description="South bound latitude"),
    east: float = Query(..., description="East bound longitude"),
    west: float = Query(..., description="West bound longitude"),
    dev_category: Optional[str] = Query(None, description="Filter by development category"),
    decision: Optional[str] = Query(None, description="Filter by decision status"),
    year_from: Optional[int] = Query(None, description="Minimum year"),
    zoom: Optional[int] = Query(None, description="Current zoom level"),
    limit: int = Query(500, le=2000, description="Maximum pins to return"),
    db: AsyncSession = Depends(get_db),
):
    """Return map pins within a bounding box. Max 2000 pins per request.

    Used by the frontend viewport-based map with marker clustering.
    """
    conditions = [
        "location_point IS NOT NULL",
        "ST_Within(location_point, ST_MakeEnvelope(:west, :south, :east, :north, 4326))",
    ]
    params: dict = {"north": north, "south": south, "east": east, "west": west}

    if dev_category:
        conditions.append("dev_category = :dev_category")
        params["dev_category"] = dev_category

    if decision == "granted":
        conditions.append("decision ILIKE '%grant%'")
    elif decision == "refused":
        conditions.append("decision ILIKE '%refus%'")
    elif decision == "pending":
        conditions.append("(decision IS NULL OR decision = 'N/A')")
    elif decision:
        conditions.append("decision ILIKE :decision_pat")
        params["decision_pat"] = f"%{decision}%"

    if year_from:
        conditions.append("year >= :year_from")
        params["year_from"] = year_from

    where = " AND ".join(conditions)

    result = await db.execute(
        text(f"""
            SELECT
                reg_ref,
                ST_Y(location_point) as lat,
                ST_X(location_point) as lng,
                decision,
                dev_category,
                proposal,
                location,
                apn_date,
                est_value_high,
                planning_authority
            FROM applications
            WHERE {where}
            ORDER BY apn_date DESC NULLS LAST
            LIMIT :limit
        """),
        {**params, "limit": limit},
    )

    rows = result.fetchall()

    pins = []
    for r in rows:
        pins.append({
            "reg_ref": r.reg_ref,
            "lat": r.lat,
            "lng": r.lng,
            "decision": r.decision,
            "dev_category": r.dev_category,
            "proposal": r.proposal[:150] if r.proposal else None,
            "location": r.location,
            "apn_date": str(r.apn_date) if r.apn_date else None,
            "est_value_high": r.est_value_high,
            "planning_authority": r.planning_authority,
        })

    return {
        "pins": pins,
        "total": len(pins),
        "capped": len(pins) == limit,
    }


# ── Legacy GeoJSON endpoint (kept for backward compatibility) ──────────

@router.get("/map/points")
async def get_map_points(
    category: Optional[str] = Query(None),
    decision: Optional[str] = Query(None),
    year_from: Optional[int] = Query(None),
    year_to: Optional[int] = Query(None),
    lat: Optional[float] = Query(None),
    lng: Optional[float] = Query(None),
    radius_m: Optional[int] = Query(None),
    q: Optional[str] = Query(None),
    limit: int = Query(5000, le=10000),
    db: AsyncSession = Depends(get_db),
):
    """Return GeoJSON FeatureCollection of map points with filters."""

    conditions = [Application.location_point.isnot(None)]

    if category:
        conditions.append(Application.dev_category == category)
    if decision:
        conditions.append(Application.decision.ilike(f"%{decision}%"))
    if year_from:
        conditions.append(Application.year >= year_from)
    if year_to:
        conditions.append(Application.year <= year_to)
    if q:
        ts_query = func.plainto_tsquery("english", q)
        conditions.append(Application.search_vector.op("@@")(ts_query))
    if lat is not None and lng is not None and radius_m:
        point = ST_SetSRID(ST_MakePoint(lng, lat), 4326)
        conditions.append(ST_DWithin(Application.location_point, point, radius_m, use_spheroid=True))

    where_clause = and_(*conditions)

    query = (
        select(
            Application.reg_ref,
            ST_Y(Application.location_point).label("lat"),
            ST_X(Application.location_point).label("lng"),
            Application.decision,
            Application.dev_category,
            Application.proposal,
            Application.location,
        )
        .where(where_clause)
        .order_by(Application.apn_date.desc().nullslast())
        .limit(limit)
    )

    result = await db.execute(query)
    rows = result.all()

    features = []
    for row in rows:
        features.append({
            "type": "Feature",
            "geometry": {
                "type": "Point",
                "coordinates": [row.lng, row.lat],
            },
            "properties": {
                "reg_ref": row.reg_ref,
                "decision": row.decision,
                "dev_category": row.dev_category,
                "proposal": row.proposal[:150] if row.proposal else None,
                "location": row.location,
            },
        })

    return {
        "type": "FeatureCollection",
        "features": features,
        "total": len(features),
    }
