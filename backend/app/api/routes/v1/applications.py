"""PlanSearch Public API v1 — Application Endpoints.

GET  /v1/applications         — Search/filter applications
GET  /v1/applications/nearby  — Proximity search (PostGIS)
GET  /v1/applications/address — Address/eircode lookup
GET  /v1/applications/{reg_ref} — Single application detail
"""

import logging
import time
from typing import Optional

from fastapi import APIRouter, Depends, Query, Request, Response
from sqlalchemy import func, text, select, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from geoalchemy2.functions import ST_DWithin, ST_SetSRID, ST_MakePoint, ST_X, ST_Y

from app.database import get_db
from app.models import Application, ApiKey, ApplicationCompany
from app.middleware.api_auth import (
    require_api_key, wrap_response, add_rate_limit_headers, _log_usage,
)
from app.api.routes.search import parse_search_intent

router = APIRouter()
logger = logging.getLogger(__name__)


def _serialize_application_summary(app, lat_val=None, lng_val=None, distance_m=None) -> dict:
    """Serialize an Application to the public API summary format."""
    result = {
        "id": app.id,
        "reg_ref": app.reg_ref,
        "apn_date": str(app.apn_date) if app.apn_date else None,
        "dec_date": str(app.dec_date) if app.dec_date else None,
        "proposal": app.proposal[:300] if app.proposal else None,
        "location": app.location,
        "decision": app.decision,
        "dev_category": app.dev_category,
        "dev_subcategory": app.dev_subcategory,
        "applicant_name": app.applicant_name,
        "planning_authority": app.planning_authority,
        "lifecycle_stage": app.lifecycle_stage,
        "est_value_low": app.est_value_low,
        "est_value_high": app.est_value_high,
        "significance_score": app.significance_score,
        "num_residential_units": app.num_residential_units,
        "floor_area": app.floor_area,
        "lat": lat_val,
        "lng": lng_val,
        "link_app_details": app.link_app_details,
    }
    if distance_m is not None:
        result["distance_m"] = round(distance_m, 1)
    return result


def _serialize_application_detail(app, lat_val=None, lng_val=None, bcms=None, documents=None) -> dict:
    """Serialize an Application to the full public API detail format."""
    result = {
        "id": app.id,
        "reg_ref": app.reg_ref,
        "year": app.year,
        "apn_date": str(app.apn_date) if app.apn_date else None,
        "rgn_date": str(app.rgn_date) if app.rgn_date else None,
        "dec_date": str(app.dec_date) if app.dec_date else None,
        "final_grant_date": str(app.final_grant_date) if app.final_grant_date else None,
        "time_exp": str(app.time_exp) if app.time_exp else None,
        "proposal": app.proposal,
        "proposal_summary": app.proposal_summary,
        "location": app.location,
        "app_type": app.app_type,
        "stage": app.stage,
        "decision": app.decision,
        "dev_category": app.dev_category,
        "dev_subcategory": app.dev_subcategory,
        "applicant_name": app.applicant_name,
        "planning_authority": app.planning_authority,
        "data_source": app.data_source,
        "area_of_site": app.area_of_site,
        "num_residential_units": app.num_residential_units,
        "floor_area": app.floor_area,
        "eircode": app.eircode,
        "lifecycle_stage": app.lifecycle_stage,
        "est_value_low": app.est_value_low,
        "est_value_high": app.est_value_high,
        "est_value_basis": app.est_value_basis,
        "est_value_type": app.est_value_type,
        "est_value_confidence": app.est_value_confidence,
        "significance_score": app.significance_score,
        "lat": lat_val,
        "lng": lng_val,
        "link_app_details": app.link_app_details,
        # Appeal fields
        "appeal_ref_number": app.appeal_ref_number,
        "appeal_status": app.appeal_status,
        "appeal_decision": app.appeal_decision,
        "appeal_decision_date": str(app.appeal_decision_date) if app.appeal_decision_date else None,
    }
    if bcms:
        result["bcms"] = bcms
    if documents:
        result["documents"] = documents
    return result


# ── Search ────────────────────────────────────────────────────────────────

@router.get("/applications")
async def search_applications(
    request: Request,
    response: Response,
    q: Optional[str] = Query(None, description="Natural language query (AI-parsed)"),
    reg_ref: Optional[str] = Query(None, description="Planning reference direct lookup"),
    authority: Optional[str] = Query(None, description="Planning authority (exact match)"),
    category: Optional[str] = Query(None, description="Dev category filter"),
    decision: Optional[str] = Query(None, description="Decision: granted, refused, pending, withdrawn"),
    lifecycle_stage: Optional[str] = Query(None, description="Lifecycle stage filter"),
    value_min: Optional[int] = Query(None, description="Minimum estimated value (EUR)"),
    value_max: Optional[int] = Query(None, description="Maximum estimated value (EUR)"),
    keywords: Optional[str] = Query(None, description="Full-text search within proposal text"),
    applicant: Optional[str] = Query(None, description="Applicant name partial match"),
    year_from: Optional[int] = Query(None, description="Minimum application year"),
    year_to: Optional[int] = Query(None, description="Maximum application year"),
    sort: str = Query("date_desc", description="Sort: date_desc, date_asc, value_desc, relevance"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(25, ge=1, le=100, description="Results per page"),
    api_key: ApiKey = Depends(require_api_key),
    db: AsyncSession = Depends(get_db),
):
    """Search planning applications with optional AI intent parsing."""
    start = time.time()
    conditions = []
    intent = None

    # Direct reg_ref lookup
    if reg_ref:
        conditions.append(Application.reg_ref.ilike(f"%{reg_ref.strip()}%"))
    # AI-powered natural language search
    elif q and q.strip():
        intent = await parse_search_intent(q, db)
        if intent.get("dev_category") and not category:
            category = intent["dev_category"]
        if intent.get("planning_authorities") and not authority:
            conditions.append(
                Application.planning_authority.in_(intent["planning_authorities"])
            )
        if intent.get("decision") and not decision:
            decision = intent["decision"]
        if intent.get("keywords") and not keywords:
            keywords = intent["keywords"]

    # Apply filters
    if category:
        conditions.append(Application.dev_category == category)
    if authority:
        conditions.append(Application.planning_authority == authority)

    if decision:
        decision_upper = decision.upper()
        if decision_upper == "PENDING":
            conditions.append(or_(Application.decision.is_(None), Application.decision == "N/A"))
        else:
            conditions.append(Application.decision.ilike(f"%{decision_upper}%"))

    if lifecycle_stage:
        conditions.append(Application.lifecycle_stage == lifecycle_stage)
    if value_min is not None:
        conditions.append(Application.est_value_high >= value_min)
    if value_max is not None:
        conditions.append(Application.est_value_high <= value_max)
    if applicant:
        conditions.append(Application.applicant_name.ilike(f"%{applicant}%"))
    if year_from:
        conditions.append(Application.year >= year_from)
    if year_to:
        conditions.append(Application.year <= year_to)

    # Full-text search on keywords
    search_keywords = keywords or ""
    if search_keywords.strip():
        ts_query = func.plainto_tsquery("english", search_keywords)
        conditions.append(Application.search_vector.op("@@")(ts_query))

    where_clause = and_(*conditions) if conditions else text("1=1")

    # Count
    count_result = await db.execute(
        select(func.count()).select_from(Application).where(where_clause)
    )
    total = count_result.scalar() or 0

    # Data query
    data_query = select(
        Application,
        ST_Y(Application.location_point).label("lat"),
        ST_X(Application.location_point).label("lng"),
    ).where(where_clause)

    # Sorting
    if sort == "date_asc":
        data_query = data_query.order_by(Application.apn_date.asc().nullsfirst())
    elif sort == "value_desc":
        data_query = data_query.order_by(Application.est_value_high.desc().nullslast())
    elif sort == "relevance" and search_keywords.strip():
        ts_query = func.plainto_tsquery("english", search_keywords)
        data_query = data_query.order_by(func.ts_rank(Application.search_vector, ts_query).desc())
    else:
        data_query = data_query.order_by(Application.apn_date.desc().nullslast())

    offset = (page - 1) * page_size
    data_query = data_query.offset(offset).limit(page_size)

    result = await db.execute(data_query)
    rows = result.all()

    results = [_serialize_application_summary(row[0], row[1], row[2]) for row in rows]

    query_time_ms = (time.time() - start) * 1000
    total_pages = max(1, (total + page_size - 1) // page_size)

    # Log usage
    await _log_usage(api_key.id, "/v1/applications", 200, int(query_time_ms), db)
    add_rate_limit_headers(response, request)

    return wrap_response({
        "results": results,
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": total_pages,
        "query_time_ms": round(query_time_ms, 2),
        "intent": intent,
    }, request)


# ── Nearby search ─────────────────────────────────────────────────────────

@router.get("/applications/nearby")
async def nearby_applications(
    request: Request,
    response: Response,
    lat: float = Query(..., description="Latitude"),
    lng: float = Query(..., description="Longitude"),
    radius_m: int = Query(1000, ge=1, le=50000, description="Radius in metres (max 50,000)"),
    category: Optional[str] = Query(None),
    decision: Optional[str] = Query(None),
    year_from: Optional[int] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
    api_key: ApiKey = Depends(require_api_key),
    db: AsyncSession = Depends(get_db),
):
    """Find all applications within a radius of a point, sorted by distance."""
    start = time.time()
    point = ST_SetSRID(ST_MakePoint(lng, lat), 4326)
    conditions = [
        ST_DWithin(Application.location_point, point, radius_m, use_spheroid=True),
        Application.location_point.isnot(None),
    ]

    if category:
        conditions.append(Application.dev_category == category)
    if decision:
        conditions.append(Application.decision.ilike(f"%{decision}%"))
    if year_from:
        conditions.append(Application.year >= year_from)

    where_clause = and_(*conditions)

    # Count
    count_result = await db.execute(
        select(func.count()).select_from(Application).where(where_clause)
    )
    total = count_result.scalar() or 0

    from geoalchemy2.functions import ST_Distance
    distance_col = ST_Distance(
        Application.location_point, point, use_spheroid=True
    ).label("distance_m")

    data_query = (
        select(
            Application,
            ST_Y(Application.location_point).label("lat"),
            ST_X(Application.location_point).label("lng"),
            distance_col,
        )
        .where(where_clause)
        .order_by(distance_col)
        .offset((page - 1) * page_size)
        .limit(page_size)
    )

    result = await db.execute(data_query)
    rows = result.all()
    results = [
        _serialize_application_summary(row[0], row[1], row[2], distance_m=row[3])
        for row in rows
    ]

    query_time_ms = (time.time() - start) * 1000
    await _log_usage(api_key.id, "/v1/applications/nearby", 200, int(query_time_ms), db)
    add_rate_limit_headers(response, request)

    return wrap_response({
        "results": results,
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": max(1, (total + page_size - 1) // page_size),
        "center": {"lat": lat, "lng": lng},
        "radius_m": radius_m,
        "query_time_ms": round(query_time_ms, 2),
    }, request)


# ── Address / eircode lookup ──────────────────────────────────────────────

@router.get("/applications/address")
async def address_lookup(
    request: Request,
    response: Response,
    address: Optional[str] = Query(None, description="Street address partial match"),
    eircode: Optional[str] = Query(None, description="Eircode prefix or exact match"),
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
    api_key: ApiKey = Depends(require_api_key),
    db: AsyncSession = Depends(get_db),
):
    """Planning history by address or eircode."""
    start = time.time()

    if not address and not eircode:
        from app.middleware.api_auth import api_error_response
        api_error_response(
            "MISSING_PARAMETER",
            "Provide either 'address' or 'eircode' parameter.",
            status=400,
        )

    conditions = []
    if eircode:
        conditions.append(
            or_(
                Application.eircode.ilike(f"{eircode.strip()}%"),
                Application.location.ilike(f"%{eircode.strip()}%"),
            )
        )
    if address:
        conditions.append(Application.location.ilike(f"%{address.strip()}%"))

    where_clause = and_(*conditions) if conditions else text("1=1")

    count_result = await db.execute(
        select(func.count()).select_from(Application).where(where_clause)
    )
    total = count_result.scalar() or 0

    data_query = (
        select(
            Application,
            ST_Y(Application.location_point).label("lat"),
            ST_X(Application.location_point).label("lng"),
        )
        .where(where_clause)
        .order_by(Application.apn_date.desc().nullslast())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )

    result = await db.execute(data_query)
    rows = result.all()
    results = [_serialize_application_summary(row[0], row[1], row[2]) for row in rows]

    query_time_ms = (time.time() - start) * 1000
    await _log_usage(api_key.id, "/v1/applications/address", 200, int(query_time_ms), db)
    add_rate_limit_headers(response, request)

    return wrap_response({
        "results": results,
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": max(1, (total + page_size - 1) // page_size),
        "query_time_ms": round(query_time_ms, 2),
    }, request)


# ── Single application detail ────────────────────────────────────────────

@router.get("/applications/{reg_ref:path}")
async def get_application_detail(
    reg_ref: str,
    request: Request,
    response: Response,
    api_key: ApiKey = Depends(require_api_key),
    db: AsyncSession = Depends(get_db),
):
    """Full detail for a single planning application."""
    start = time.time()

    query = (
        select(Application)
        .options(
            selectinload(Application.appeals),
            selectinload(Application.further_info_items),
            selectinload(Application.documents),
            selectinload(Application.company_links).selectinload(ApplicationCompany.company),
        )
        .where(Application.reg_ref == reg_ref)
    )

    result = await db.execute(query)
    app = result.scalar_one_or_none()

    if not app:
        from app.middleware.api_auth import api_error_response
        api_error_response("NOT_FOUND", f"Application {reg_ref} not found.", status=404)

    # Extract coordinates
    lat_val = lng_val = None
    if app.location_point is not None:
        try:
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

    # BCMS data
    bcms = None
    try:
        raw_ref = reg_ref.split("/", 1)[1] if "/" in reg_ref else reg_ref
        bcms_result = await db.execute(text("""
            SELECT cn_commencement_date, cn_total_dwelling_units, cn_total_floor_area,
                   ccc_date_validated, ccc_units_completed, local_authority,
                   cn_total_apartments, cn_number_stories_above, cn_lat, cn_lng,
                   cn_description, cn_project_status
            FROM commencement_notices WHERE reg_ref = :raw_ref LIMIT 1
        """), {"raw_ref": raw_ref})
        bcms_row = bcms_result.fetchone()
        if bcms_row:
            m = bcms_row._mapping
            bcms = {k: (str(v) if hasattr(v, "isoformat") else v) for k, v in m.items() if v is not None}
    except Exception:
        pass

    # Documents
    documents = [
        {
            "doc_name": d.doc_name,
            "doc_type": d.doc_type,
            "file_extension": d.file_extension,
            "portal_url": d.portal_url,
            "uploaded_date": str(d.uploaded_date) if d.uploaded_date else None,
            "doc_category": d.doc_category,
        }
        for d in app.documents
    ]

    detail = _serialize_application_detail(app, lat_val, lng_val, bcms, documents)

    query_time_ms = (time.time() - start) * 1000
    await _log_usage(api_key.id, "/v1/applications/{reg_ref}", 200, int(query_time_ms), db)
    add_rate_limit_headers(response, request)

    return wrap_response(detail, request)
