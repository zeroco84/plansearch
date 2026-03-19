"""PlanSearch — Application detail endpoint.

GET /api/applications/{reg_ref} — Full application detail with related records.
"""

import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from geoalchemy2.functions import ST_X, ST_Y

from app.database import get_db
from app.models import Application, Appeal, FurtherInfo, Company, ApplicationCompany, ApplicationDocument
from app.workers.floor_area_extractor import extract_site_area_from_proposal
from app.schemas import ApplicationDetail, AppealDetail, FurtherInfoDetail, CompanyDetail, DocumentDetail, BcmsDetail
from app.workers.summariser import get_or_create_summary

router = APIRouter()
logger = logging.getLogger(__name__)


def get_portal_url(reg_ref: str, year: int | None) -> str:
    """Construct the portal document URL for an application."""
    # Strip council prefix if present (e.g. "DC/2024/12345" → "2024/12345")
    clean_ref = reg_ref
    if "/" in reg_ref and len(reg_ref.split("/")[0]) <= 3:
        clean_ref = reg_ref[reg_ref.index("/") + 1:]

    if year and year >= 2024:
        return f"https://planning.localgov.ie/en/view-planning-applications?reference={clean_ref}"
    else:
        return f"https://planning.agileapplications.ie/dublincity/search-applications/?reg_ref={clean_ref}"


@router.get("/applications/{reg_ref:path}", response_model=ApplicationDetail)
async def get_application(
    reg_ref: str,
    db: AsyncSession = Depends(get_db),
):
    """Get full detail for a single planning application."""

    # Fetch application with eager-loaded relationships
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
        raise HTTPException(status_code=404, detail=f"Application {reg_ref} not found")

    # Extract coordinates
    lat_val = None
    lng_val = None
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

    # Build company detail
    company_detail = None
    if app.company_links:
        link = app.company_links[0]
        c = link.company
        company_detail = CompanyDetail(
            cro_number=c.cro_number,
            company_name=c.company_name,
            company_status=c.company_status,
            registered_address=c.registered_address,
            incorporation_date=c.incorporation_date,
            company_type=c.company_type,
            directors=c.directors,
        )

    # Generate or retrieve AI summary
    proposal_summary = app.proposal_summary
    if app.proposal and not proposal_summary:
        try:
            proposal_summary = await get_or_create_summary(
                db, app.reg_ref, app.long_proposal or app.proposal
            )
        except Exception as e:
            logger.warning(f"Summary generation failed for {reg_ref}: {e}")
            proposal_summary = None

    # Fetch BCMS commencement notice data
    bcms_detail = None
    try:
        # Strip council prefix to match BCMS raw ref
        # e.g. "SD/SD26B/0100W" → "SD26B/0100W"
        raw_ref = reg_ref.split("/", 1)[1] if "/" in reg_ref else reg_ref
        bcms_result = await db.execute(text("""
            SELECT cn_commencement_date, cn_total_dwelling_units, cn_total_floor_area,
                   ccc_date_validated, ccc_units_completed, local_authority,
                   cn_total_apartments, cn_number_stories_above,
                   cn_lat, cn_lng
            FROM commencement_notices
            WHERE reg_ref = :raw_ref
            LIMIT 1
        """), {"raw_ref": raw_ref})
        bcms_row = bcms_result.fetchone()
        if bcms_row:
            m = bcms_row._mapping
            bcms_detail = BcmsDetail(
                cn_commencement_date=m.get("cn_commencement_date"),
                cn_total_dwelling_units=m.get("cn_total_dwelling_units"),
                cn_total_floor_area=m.get("cn_total_floor_area"),
                cn_total_apartments=m.get("cn_total_apartments"),
                cn_number_stories_above=m.get("cn_number_stories_above"),
                cn_lat=m.get("cn_lat"),
                cn_lng=m.get("cn_lng"),
                ccc_date_validated=m.get("ccc_date_validated"),
                ccc_units_completed=m.get("ccc_units_completed"),
                local_authority=m.get("local_authority"),
            )
    except Exception as e:
        logger.warning(f"BCMS lookup failed for {reg_ref}: {e}")

    # Build response
    return ApplicationDetail(
        id=app.id,
        reg_ref=app.reg_ref,
        year=app.year,
        apn_date=app.apn_date,
        rgn_date=app.rgn_date,
        dec_date=app.dec_date,
        final_grant_date=app.final_grant_date,
        time_exp=app.time_exp,
        proposal=app.proposal,
        long_proposal=app.long_proposal,
        proposal_summary=proposal_summary,
        location=app.location,
        app_type=app.app_type,
        stage=app.stage,
        decision=app.decision,
        dev_category=app.dev_category,
        dev_subcategory=app.dev_subcategory,
        classification_confidence=app.classification_confidence,
        applicant_name=app.applicant_name,
        cro_number=app.cro_number,
        planning_authority=app.planning_authority,
        area_of_site=app.area_of_site,
        site_area_ha=extract_site_area_from_proposal(app.proposal),
        num_residential_units=app.num_residential_units,
        floor_area=app.floor_area,
        lat=lat_val,
        lng=lng_val,
        portal_url=get_portal_url(app.reg_ref, app.year),
        est_value_low=app.est_value_low,
        est_value_high=app.est_value_high,
        est_value_basis=app.est_value_basis,
        est_value_type=app.est_value_type,
        est_value_confidence=app.est_value_confidence,
        appeals=[
            AppealDetail(
                id=a.id,
                appeal_ref=a.appeal_ref,
                appeal_date=a.appeal_date,
                appellant=a.appellant,
                appeal_decision=a.appeal_decision,
                appeal_dec_date=a.appeal_dec_date,
            )
            for a in app.appeals
        ],
        further_info=[
            FurtherInfoDetail(
                id=fi.id,
                fi_date=fi.fi_date,
                fi_type=fi.fi_type,
                fi_response_date=fi.fi_response_date,
            )
            for fi in app.further_info_items
        ],
        company=company_detail,
        documents=[
            DocumentDetail(
                id=d.id,
                doc_name=d.doc_name,
                doc_type=d.doc_type,
                file_extension=d.file_extension,
                file_size_bytes=d.file_size_bytes,
                portal_source=d.portal_source,
                direct_url=d.direct_url,
                portal_url=d.portal_url,
                uploaded_date=d.uploaded_date,
                doc_category=d.doc_category,
            )
            for d in app.documents
        ],
        bcms=bcms_detail,
    )
