"""PlanSearch Public API v1 — Bulk Export (Enterprise Tier).

GET /v1/export — Paginated bulk export in CSV, JSON, or GeoJSON format.
Enterprise tier only. 10,000 rows per page.
"""

import csv
import io
import json
import logging
import time
from typing import Optional

from fastapi import APIRouter, Depends, Query, Request, Response
from fastapi.responses import StreamingResponse
from sqlalchemy import func, text, select, and_
from sqlalchemy.ext.asyncio import AsyncSession
from geoalchemy2.functions import ST_X, ST_Y

from app.database import get_db
from app.models import Application, ApiKey
from app.middleware.api_auth import (
    require_api_key, wrap_response, add_rate_limit_headers,
    _log_usage, api_error_response,
)

router = APIRouter()
logger = logging.getLogger(__name__)

MAX_ROWS_PER_PAGE = 10_000


@router.get("/export")
async def bulk_export(
    request: Request,
    response: Response,
    format: str = Query("json", description="Export format: json, csv, geojson"),
    authority: Optional[str] = Query(None),
    category: Optional[str] = Query(None),
    decision: Optional[str] = Query(None),
    year_from: Optional[int] = Query(None),
    year_to: Optional[int] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(10000, ge=1, le=10000),
    api_key: ApiKey = Depends(require_api_key),
    db: AsyncSession = Depends(get_db),
):
    """Paginated bulk export. Enterprise tier required. Max 10,000 rows per page."""
    start = time.time()

    # Gate to Enterprise tier
    if api_key.tier not in ("enterprise",):
        api_error_response(
            "TIER_REQUIRED",
            "Bulk export requires an Enterprise tier API key. Upgrade at https://plansearch.cc/pricing",
            status=403,
        )

    if format not in ("json", "csv", "geojson"):
        api_error_response("INVALID_FORMAT", "Format must be json, csv, or geojson.", status=400)

    conditions = []
    if authority:
        conditions.append(Application.planning_authority == authority)
    if category:
        conditions.append(Application.dev_category == category)
    if decision:
        conditions.append(Application.decision.ilike(f"%{decision}%"))
    if year_from:
        conditions.append(Application.year >= year_from)
    if year_to:
        conditions.append(Application.year <= year_to)

    where_clause = and_(*conditions) if conditions else text("1=1")

    # Count
    count_result = await db.execute(
        select(func.count()).select_from(Application).where(where_clause)
    )
    total = count_result.scalar() or 0

    # Data
    offset = (page - 1) * page_size
    data_query = (
        select(
            Application.reg_ref,
            Application.apn_date,
            Application.dec_date,
            Application.proposal,
            Application.location,
            Application.decision,
            Application.dev_category,
            Application.dev_subcategory,
            Application.applicant_name,
            Application.planning_authority,
            Application.lifecycle_stage,
            Application.est_value_low,
            Application.est_value_high,
            Application.num_residential_units,
            Application.floor_area,
            Application.eircode,
            ST_Y(Application.location_point).label("lat"),
            ST_X(Application.location_point).label("lng"),
        )
        .where(where_clause)
        .order_by(Application.apn_date.desc().nullslast())
        .offset(offset)
        .limit(page_size)
    )

    result = await db.execute(data_query)
    rows = result.all()

    query_time_ms = (time.time() - start) * 1000
    await _log_usage(api_key.id, "/v1/export", 200, int(query_time_ms), db)

    # ── CSV format ──
    if format == "csv":
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow([
            "reg_ref", "apn_date", "dec_date", "proposal", "location", "decision",
            "dev_category", "dev_subcategory", "applicant_name", "planning_authority",
            "lifecycle_stage", "est_value_low", "est_value_high",
            "num_residential_units", "floor_area", "eircode", "lat", "lng",
        ])
        for row in rows:
            writer.writerow([
                row.reg_ref, row.apn_date or "", row.dec_date or "",
                (row.proposal or "").replace("\n", " ")[:500],
                row.location or "", row.decision or "",
                row.dev_category or "", row.dev_subcategory or "",
                row.applicant_name or "", row.planning_authority or "",
                row.lifecycle_stage or "",
                row.est_value_low or "", row.est_value_high or "",
                row.num_residential_units or "", row.floor_area or "",
                row.eircode or "", row.lat or "", row.lng or "",
            ])
        output.seek(0)
        add_rate_limit_headers(response, request)
        return StreamingResponse(
            iter([output.getvalue()]),
            media_type="text/csv",
            headers={"Content-Disposition": f"attachment; filename=plansearch_export_p{page}.csv"},
        )

    # ── GeoJSON format ──
    if format == "geojson":
        features = []
        for row in rows:
            feature = {
                "type": "Feature",
                "geometry": {
                    "type": "Point",
                    "coordinates": [row.lng, row.lat],
                } if row.lat and row.lng else None,
                "properties": {
                    "reg_ref": row.reg_ref,
                    "apn_date": str(row.apn_date) if row.apn_date else None,
                    "dec_date": str(row.dec_date) if row.dec_date else None,
                    "proposal": (row.proposal or "")[:300],
                    "location": row.location,
                    "decision": row.decision,
                    "dev_category": row.dev_category,
                    "applicant_name": row.applicant_name,
                    "planning_authority": row.planning_authority,
                    "est_value_high": row.est_value_high,
                },
            }
            features.append(feature)

        add_rate_limit_headers(response, request)
        return wrap_response({
            "type": "FeatureCollection",
            "features": features,
            "total": total,
            "page": page,
            "page_size": page_size,
            "total_pages": max(1, (total + page_size - 1) // page_size),
        }, request)

    # ── JSON format (default) ──
    data = []
    for row in rows:
        data.append({
            "reg_ref": row.reg_ref,
            "apn_date": str(row.apn_date) if row.apn_date else None,
            "dec_date": str(row.dec_date) if row.dec_date else None,
            "proposal": (row.proposal or "")[:500],
            "location": row.location,
            "decision": row.decision,
            "dev_category": row.dev_category,
            "dev_subcategory": row.dev_subcategory,
            "applicant_name": row.applicant_name,
            "planning_authority": row.planning_authority,
            "lifecycle_stage": row.lifecycle_stage,
            "est_value_low": row.est_value_low,
            "est_value_high": row.est_value_high,
            "num_residential_units": row.num_residential_units,
            "floor_area": row.floor_area,
            "eircode": row.eircode,
            "lat": row.lat,
            "lng": row.lng,
        })

    add_rate_limit_headers(response, request)
    return wrap_response({
        "results": data,
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": max(1, (total + page_size - 1) // page_size),
    }, request)
