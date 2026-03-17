"""PlanSearch — NPAD ArcGIS Ingest Worker.

Ingests planning applications from the National Planning Application Database
(NPAD) ArcGIS Feature Service. Covers 30 of 31 Irish local authorities.

API: https://services.arcgis.com/NzlPQPKn5QF9v2US/arcgis/rest/services/
     IrishPlanningApplications/FeatureServer/0
"""

import asyncio
import logging
import re
from datetime import datetime, date
from typing import Optional

import httpx
from sqlalchemy import select, func, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.config import get_settings
from app.models import Application, SyncLog

logger = logging.getLogger(__name__)
settings = get_settings()

NPAD_URL = (
    "https://services.arcgis.com/NzlPQPKn5QF9v2US/arcgis/rest/services/"
    "IrishPlanningApplications/FeatureServer/0/query"
)

PAGE_SIZE = 2000


def normalise_ref(raw_ref: Optional[str]) -> Optional[str]:
    """Normalise planning reference numbers for cross-dataset joining.

    Handles variations like:
        'FRL/2023/12345' (DCC format)
        '23/1234'        (short county council format)
        'D23A/1234'      (Dublin with area code)
        'PL 12345'       (ABP reference)
    """
    if not raw_ref:
        return None
    ref = raw_ref.strip().upper()
    # Remove extra whitespace, normalise separators
    ref = re.sub(r'\s+', '', ref)
    return ref


def epoch_to_date(epoch_ms: Optional[int]) -> Optional[date]:
    """Convert ArcGIS epoch milliseconds to Python date."""
    if not epoch_ms:
        return None
    try:
        return datetime.utcfromtimestamp(epoch_ms / 1000).date()
    except (ValueError, OSError):
        return None


def map_npad_feature(feature: dict) -> dict:
    """Map an NPAD ArcGIS feature to our Application model fields."""
    attrs = feature.get("attributes", {})
    geom = feature.get("geometry", {})

    # Build applicant_name from forename + surname
    forename = (attrs.get("ApplicantForename") or "").strip()
    surname = (attrs.get("ApplicantSurname") or "").strip()
    applicant_name = f"{forename} {surname}".strip() or None

    # Extract year from received date
    received_date = epoch_to_date(attrs.get("ReceivedDate"))

    return {
        "reg_ref": normalise_ref(attrs.get("ApplicationNumber")),
        "planning_authority": attrs.get("PlanningAuthority"),
        "proposal": attrs.get("DevelopmentDescription"),
        "location": attrs.get("DevelopmentAddress"),
        "eircode": attrs.get("DevelopmentPostcode"),
        "app_type": attrs.get("ApplicationType"),
        "stage": attrs.get("ApplicationStatus"),
        "decision": attrs.get("Decision"),
        "land_use_code": attrs.get("LandUseCode"),
        "area_of_site": attrs.get("AreaofSite"),
        "num_residential_units": attrs.get("NumResidentialUnits"),
        "floor_area": attrs.get("FloorArea"),
        "one_off_house": bool(attrs.get("OneOffHouse")),
        "applicant_forename": forename or None,
        "applicant_surname": surname or None,
        "applicant_name": applicant_name,
        "applicant_address": attrs.get("ApplicantAddress"),
        "link_app_details": attrs.get("LinkAppDetails"),
        "npad_object_id": attrs.get("OBJECTID"),
        "data_source": "npad_arcgis",
        # Dates
        "apn_date": received_date,
        "rgn_date": epoch_to_date(attrs.get("RegistrationDate")),
        "dec_date": epoch_to_date(attrs.get("DecisionDate")),
        "final_grant_date": epoch_to_date(attrs.get("GrantDate")),
        "time_exp": epoch_to_date(attrs.get("ExpiryDate")),
        # Appeals (richer than Phase 1)
        "appeal_ref_number": attrs.get("AppealRefNumber"),
        "appeal_status": attrs.get("AppealStatus"),
        "appeal_decision": attrs.get("AppealDecision"),
        "appeal_decision_date": epoch_to_date(attrs.get("AppealDecisionDate")),
        # Further info
        "fi_request_date": epoch_to_date(attrs.get("FIRequestDate")),
        "fi_rec_date": epoch_to_date(attrs.get("FIRecDate")),
        # Geometry (NPAD returns WGS84 when outSR=4326)
        "itm_easting": attrs.get("ITMEasting"),
        "itm_northing": attrs.get("ITMNorthing"),
    }


async def get_record_count() -> int:
    """Get total record count from NPAD."""
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.get(NPAD_URL, params={
            "where": "1=1",
            "returnCountOnly": "true",
            "f": "json",
        })
        data = resp.json()
        return data.get("count", 0)


async def fetch_page(offset: int, where: str = "1=1") -> list[dict]:
    """Fetch a single page of NPAD features."""
    async with httpx.AsyncClient(timeout=60.0) as client:
        resp = await client.get(NPAD_URL, params={
            "where": where,
            "outFields": "*",
            "returnGeometry": "true",
            "outSR": "4326",
            "f": "json",
            "resultOffset": offset,
            "resultRecordCount": PAGE_SIZE,
            "orderByFields": "OBJECTID ASC",
        })
        data = resp.json()
        return data.get("features", [])


async def upsert_npad_batch(
    features: list[dict],
    db: AsyncSession,
) -> dict:
    """Upsert a batch of NPAD features into the applications table.

    Uses PostgreSQL ON CONFLICT to update existing records only if
    data_source is 'npad_arcgis' or the record is new.
    """
    stats = {"new": 0, "updated": 0, "skipped": 0}

    for feature in features:
        mapped = map_npad_feature(feature)

        if not mapped["reg_ref"]:
            stats["skipped"] += 1
            continue

        # Build WKT point from geometry
        geom = feature.get("geometry", {})
        lng = geom.get("x")
        lat = geom.get("y")
        location_point_wkt = f"SRID=4326;POINT({lng} {lat})" if lng and lat else None

        stmt = pg_insert(Application).values(
            **mapped,
            location_point=text(f"ST_GeomFromEWKT('{location_point_wkt}')") if location_point_wkt else None,
        )

        # On conflict: update if record was from NPAD or has no source
        update_dict = {k: v for k, v in mapped.items() if k != "reg_ref" and v is not None}
        if location_point_wkt:
            update_dict["location_point"] = text(f"ST_GeomFromEWKT('{location_point_wkt}')")
        update_dict["updated_at"] = func.now()

        stmt = stmt.on_conflict_do_update(
            index_elements=["reg_ref"],
            set_=update_dict,
            where=(
                (Application.data_source == "npad_arcgis") |
                (Application.data_source.is_(None))
            ),
        )

        try:
            result = await db.execute(stmt)
            if result.rowcount > 0:
                stats["new"] += 1
            else:
                stats["updated"] += 1
        except Exception as e:
            logger.warning(f"Error upserting {mapped['reg_ref']}: {e}")
            stats["skipped"] += 1

    return stats


async def ingest_npad_full(db: AsyncSession) -> dict:
    """Full NPAD ingestion: paginate through all 362k+ records."""
    total = await get_record_count()
    logger.info(f"NPAD: Starting full ingest of {total:,} records")

    sync_log = SyncLog(
        sync_type="npad_full",
        status="running",
    )
    db.add(sync_log)
    await db.commit()

    offset = 0
    all_stats = {"new": 0, "updated": 0, "skipped": 0, "total": total}

    while offset < total:
        try:
            features = await fetch_page(offset)

            if not features:
                logger.warning(f"NPAD: Empty page at offset {offset}")
                break

            batch_stats = await upsert_npad_batch(features, db)
            all_stats["new"] += batch_stats["new"]
            all_stats["updated"] += batch_stats["updated"]
            all_stats["skipped"] += batch_stats["skipped"]

            await db.commit()

            offset += PAGE_SIZE
            pages_done = offset // PAGE_SIZE
            logger.info(
                f"NPAD: Page {pages_done} ({offset:,}/{total:,}) — "
                f"{all_stats['new']} new, {all_stats['updated']} updated"
            )

            # Gentle rate limit — 1 req/sec
            await asyncio.sleep(1.0)

        except Exception as e:
            logger.error(f"NPAD: Error at offset {offset}: {e}")
            await asyncio.sleep(5.0)
            continue

    # Update sync log
    sync_log.completed_at = datetime.utcnow()
    sync_log.records_processed = all_stats["new"] + all_stats["updated"]
    sync_log.records_new = all_stats["new"]
    sync_log.records_updated = all_stats["updated"]
    sync_log.status = "completed"
    await db.commit()

    logger.info(f"NPAD: Full ingest complete — {all_stats}")
    return all_stats


async def ingest_npad_incremental(db: AsyncSession) -> dict:
    """Incremental NPAD sync: only records updated since last sync.

    Uses ETL_DATE field which tracks when each record was last touched.
    """
    # Find last successful NPAD sync
    result = await db.execute(
        select(SyncLog.completed_at)
        .where(SyncLog.sync_type.in_(["npad_full", "npad_incremental"]))
        .where(SyncLog.status == "completed")
        .order_by(SyncLog.completed_at.desc())
        .limit(1)
    )
    last_sync = result.scalar()

    if not last_sync:
        logger.info("NPAD: No previous sync found, running full ingest")
        return await ingest_npad_full(db)

    where = f"ETL_DATE > DATE '{last_sync.strftime('%Y-%m-%d')}'"
    logger.info(f"NPAD: Incremental sync since {last_sync.date()}")

    sync_log = SyncLog(sync_type="npad_incremental", status="running")
    db.add(sync_log)
    await db.commit()

    offset = 0
    all_stats = {"new": 0, "updated": 0, "skipped": 0}

    while True:
        features = await fetch_page(offset, where=where)
        if not features:
            break

        batch_stats = await upsert_npad_batch(features, db)
        all_stats["new"] += batch_stats["new"]
        all_stats["updated"] += batch_stats["updated"]
        all_stats["skipped"] += batch_stats["skipped"]

        await db.commit()
        offset += PAGE_SIZE
        await asyncio.sleep(1.0)

    sync_log.completed_at = datetime.utcnow()
    sync_log.records_processed = all_stats["new"] + all_stats["updated"]
    sync_log.records_new = all_stats["new"]
    sync_log.records_updated = all_stats["updated"]
    sync_log.status = "completed"
    await db.commit()

    logger.info(f"NPAD: Incremental sync complete — {all_stats}")
    return all_stats
