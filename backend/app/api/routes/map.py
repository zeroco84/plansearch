"""PlanSearch — Map API endpoint.

GET /api/map/points — GeoJSON FeatureCollection for map display.
"""

from typing import Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, text, and_, func
from sqlalchemy.ext.asyncio import AsyncSession
from geoalchemy2.functions import ST_X, ST_Y, ST_DWithin, ST_SetSRID, ST_MakePoint

from app.database import get_db
from app.models import Application

router = APIRouter()


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
