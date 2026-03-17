"""PlanSearch — CSV Export endpoint.

GET /api/export/csv — Export search results as downloadable CSV.
"""

import csv
import io
from typing import Optional
from datetime import datetime

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy import func, text, select, and_
from sqlalchemy.ext.asyncio import AsyncSession
from geoalchemy2.functions import ST_DWithin, ST_SetSRID, ST_MakePoint, ST_X, ST_Y

from app.database import get_db
from app.models import Application

router = APIRouter()


@router.get("/export/csv")
async def export_csv(
    q: Optional[str] = Query(None),
    category: Optional[str] = Query(None),
    decision: Optional[str] = Query(None),
    applicant: Optional[str] = Query(None),
    location: Optional[str] = Query(None),
    year_from: Optional[int] = Query(None),
    year_to: Optional[int] = Query(None),
    lat: Optional[float] = Query(None),
    lng: Optional[float] = Query(None),
    radius_m: Optional[int] = Query(None),
    limit: int = Query(5000, le=10000),
    db: AsyncSession = Depends(get_db),
):
    """Export filtered search results as CSV file.

    Maximum 5000 rows by default, up to 10000.
    """
    conditions = []

    if q:
        ts_query = func.plainto_tsquery("english", q)
        conditions.append(Application.search_vector.op("@@")(ts_query))
    if category:
        conditions.append(Application.dev_category == category)
    if decision:
        conditions.append(Application.decision.ilike(f"%{decision}%"))
    if applicant:
        conditions.append(Application.applicant_name.ilike(f"%{applicant}%"))
    if location:
        conditions.append(Application.location.ilike(f"%{location}%"))
    if year_from:
        conditions.append(Application.year >= year_from)
    if year_to:
        conditions.append(Application.year <= year_to)
    if lat is not None and lng is not None and radius_m:
        point = ST_SetSRID(ST_MakePoint(lng, lat), 4326)
        conditions.append(ST_DWithin(Application.location_point, point, radius_m, use_spheroid=True))

    where_clause = and_(*conditions) if conditions else text("1=1")

    query = (
        select(
            Application.reg_ref,
            Application.apn_date,
            Application.rgn_date,
            Application.dec_date,
            Application.proposal,
            Application.location,
            Application.decision,
            Application.app_type,
            Application.dev_category,
            Application.dev_subcategory,
            Application.applicant_name,
            Application.cro_number,
            ST_Y(Application.location_point).label("lat"),
            ST_X(Application.location_point).label("lng"),
        )
        .where(where_clause)
        .order_by(Application.apn_date.desc().nullslast())
        .limit(limit)
    )

    result = await db.execute(query)
    rows = result.all()

    # Generate CSV
    output = io.StringIO()
    writer = csv.writer(output)

    # Header
    writer.writerow([
        "Reg Ref", "Application Date", "Registration Date", "Decision Date",
        "Proposal", "Location", "Decision", "Application Type",
        "Category", "Subcategory", "Applicant Name", "CRO Number",
        "Latitude", "Longitude",
    ])

    for row in rows:
        writer.writerow([
            row.reg_ref,
            row.apn_date or "",
            row.rgn_date or "",
            row.dec_date or "",
            (row.proposal or "").replace("\n", " "),
            row.location or "",
            row.decision or "",
            row.app_type or "",
            row.dev_category or "",
            row.dev_subcategory or "",
            row.applicant_name or "",
            row.cro_number or "",
            row.lat or "",
            row.lng or "",
        ])

    output.seek(0)

    filename = f"plansearch_export_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.csv"

    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={
            "Content-Disposition": f"attachment; filename={filename}",
        },
    )
