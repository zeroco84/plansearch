"""PlanSearch — BCMS Ingest Worker.

Ingests building control data from the National Building Control and Market
Surveillance Office (NBC&MSO) open data portal:

Dataset A: Commencement Notices + Certificates of Compliance on Completion
  https://data.nbco.gov.ie/dataset/bcnccc

Dataset B: FSC / DAC Applications (Fire Safety + Disability Access)
  https://data.nbco.gov.ie/dataset/applications
"""

import asyncio
import csv
import io
import logging
import re
from datetime import datetime, date
from typing import Optional

import httpx
from sqlalchemy import select, func, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.config import get_settings
from app.models import CommencementNotice, FSCApplication, SyncLog

logger = logging.getLogger(__name__)
settings = get_settings()

BCMS_CN_URL = (
    "https://data.nbco.gov.ie/dataset/2704a333-874d-46f5-b3bc-3673766bf816/"
    "resource/0774e781-7af8-46da-b623-872e74cf541e/download/buildingscnscccs.csv"
)

BCMS_FSC_URL = (
    "https://data.nbco.gov.ie/dataset/ae8f9134-fc5a-41e1-a150-bcccede234a0/"
    "resource/b1de41a3-e14c-40b7-b0d7-4e85d7a648fc/download/applications.csv"
)


def normalise_ref(raw_ref: Optional[str]) -> Optional[str]:
    """Normalise planning reference for cross-dataset joining."""
    if not raw_ref:
        return None
    ref = raw_ref.strip().upper()
    ref = re.sub(r'\s+', '', ref)
    return ref


def parse_date(val: Optional[str]) -> Optional[date]:
    """Parse various date formats from BCMS CSV."""
    if not val or not val.strip():
        return None
    val = val.strip()
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%Y-%m-%dT%H:%M:%S", "%d-%m-%Y"):
        try:
            return datetime.strptime(val, fmt).date()
        except ValueError:
            continue
    return None


def safe_float(val) -> Optional[float]:
    """Safely convert to float."""
    if val is None or val == "":
        return None
    try:
        return float(val)
    except (ValueError, TypeError):
        return None


def safe_int(val) -> Optional[int]:
    """Safely convert to integer."""
    if val is None or val == "":
        return None
    try:
        return int(float(val))
    except (ValueError, TypeError):
        return None


def safe_bool(val) -> Optional[bool]:
    """Safely convert to boolean."""
    if val is None or val == "":
        return None
    if isinstance(val, bool):
        return val
    return str(val).strip().lower() in ("true", "yes", "1", "y")


async def download_csv(url: str) -> list[dict]:
    """Download a CSV file and return as list of dicts."""
    async with httpx.AsyncClient(timeout=120.0) as client:
        resp = await client.get(url, follow_redirects=True)
        resp.raise_for_status()
        text_content = resp.text
        reader = csv.DictReader(io.StringIO(text_content))
        return list(reader)


async def ingest_bcms_commencements(db: AsyncSession) -> dict:
    """Download CN/CCC CSV and upsert all records."""
    logger.info("BCMS: Downloading Commencement Notices CSV...")

    sync_log = SyncLog(sync_type="bcms_cn", status="running")
    db.add(sync_log)
    await db.commit()

    stats = {"processed": 0, "new": 0, "skipped": 0}

    try:
        rows = await download_csv(BCMS_CN_URL)
        logger.info(f"BCMS: Downloaded {len(rows):,} CN/CCC rows")

        for row in rows:
            reg_ref = normalise_ref(row.get("CN_Planning_Permission_Number"))
            if not reg_ref:
                stats["skipped"] += 1
                continue

            lat = safe_float(row.get("CN_LAT"))
            lng = safe_float(row.get("CN_LNG"))
            location_wkt = f"SRID=4326;POINT({lng} {lat})" if lat and lng else None

            record = {
                "reg_ref": reg_ref,
                "local_authority": row.get("LocalAuthority"),
                "cn_commencement_date": parse_date(row.get("CN_Commencement_Date")),
                "cn_proposed_end_date": parse_date(row.get("CN_Proposed_End_Date")),
                "cn_project_status": row.get("CN_Project_Status"),
                "cn_date_granted": parse_date(row.get("CN_Date_Granted")),
                "cn_date_expiry": parse_date(row.get("CN_Date_Expiry")),
                "cn_description": row.get("CN_Description_proposed_development"),
                "cn_proposed_use_desc": row.get("CN_Proposed_use_of_building_desc"),
                "cn_total_floor_area": safe_float(row.get("CN_Total_floor_area_of_building")),
                "cn_total_dwelling_units": safe_int(row.get("CN_Total_Number_of_Dwelling_Units")),
                "cn_total_apartments": safe_int(row.get("CN_Total_apartments")),
                "cn_number_stories_above": safe_int(row.get("CN_Number_stories_above_ground")),
                "cn_number_bedrooms": safe_int(row.get("CN_Number_bedrooms")),
                "cn_protected_structure": safe_bool(row.get("CN_Protected_structure")),
                "cn_phase": row.get("CN_Phase"),
                "cn_units_for_phase": safe_int(row.get("CN_Units_for_phase")),
                "cn_total_phases": safe_int(row.get("CN_Total_phases")),
                "cn_street": row.get("CN_Street"),
                "cn_town": row.get("CN_Town"),
                "cn_eircode": row.get("CN_Eircode"),
                "cn_county": row.get("CN_County"),
                "cn_lat": lat,
                "cn_lng": lng,
                "ccc_date_validated": parse_date(row.get("CCC_Date_Validated")),
                "ccc_units_completed": safe_int(row.get("CCC_Units_Completed")),
                "ccc_type": row.get("CCC_Type_of_Completion_Certificate"),
            }

            # Upsert by reg_ref (a project can have multiple CNs for phases)
            stmt = pg_insert(CommencementNotice).values(
                **record,
                location_point=text(f"ST_GeomFromEWKT('{location_wkt}')") if location_wkt else None,
            )

            # For commencement notices, allow multiple per reg_ref (phases)
            # Just insert — no conflict handling needed on serial PK
            db.add(CommencementNotice(
                **record,
            ))

            stats["new"] += 1
            stats["processed"] += 1

            if stats["processed"] % 5000 == 0:
                await db.commit()
                logger.info(f"BCMS CN: Processed {stats['processed']:,} rows")

        await db.commit()

        sync_log.completed_at = datetime.utcnow()
        sync_log.records_processed = stats["processed"]
        sync_log.records_new = stats["new"]
        sync_log.status = "completed"
        await db.commit()

    except Exception as e:
        logger.error(f"BCMS CN ingest error: {e}")
        sync_log.error_message = str(e)[:1000]
        sync_log.status = "failed"
        await db.commit()

    logger.info(f"BCMS CN: Ingest complete — {stats}")
    return stats


async def ingest_bcms_fsc(db: AsyncSession) -> dict:
    """Download FSC/DAC CSV and upsert all records."""
    logger.info("BCMS: Downloading FSC/DAC Applications CSV...")

    sync_log = SyncLog(sync_type="bcms_fsc", status="running")
    db.add(sync_log)
    await db.commit()

    stats = {"processed": 0, "new": 0, "skipped": 0}

    try:
        rows = await download_csv(BCMS_FSC_URL)
        logger.info(f"BCMS: Downloaded {len(rows):,} FSC/DAC rows")

        for row in rows:
            reg_ref = normalise_ref(row.get("planning_permission_reference_no"))
            if not reg_ref:
                stats["skipped"] += 1
                continue

            lat = safe_float(row.get("LAT") or row.get("lat"))
            lng = safe_float(row.get("LONGITUDE") or row.get("longitude"))

            record = {
                "reg_ref": reg_ref,
                "application_reference_no": row.get("application_reference_no"),
                "application_type": row.get("application_type"),
                "local_authority": row.get("local_authority"),
                "submission_date": parse_date(row.get("submission_date")),
                "date_of_decision": parse_date(row.get("date_of_decision")),
                "decision_type": row.get("decision_type"),
                "floor_area_of_building": safe_float(row.get("floor_area_of_building")),
                "total_combined_floor_area": safe_float(row.get("total_combined_floor_area")),
                "no_of_stories_above_ground": safe_int(row.get("no_of_stories_above_ground_level")),
                "site_area": safe_float(row.get("site_area")),
                "use_of_proposed_works": row.get("use_of_proposed_works_or_building"),
                "main_construction_type": row.get("main_construction_type"),
                "date_construction_started": parse_date(row.get("date_construction_started")),
                "is_construction_complete": safe_bool(row.get("is_construction_of_building_complete")),
                "date_of_completion": parse_date(row.get("date_of_completion")),
                "is_building_occupied": safe_bool(row.get("is_building_occupied")),
                "applicant_name": row.get("applicant_name"),
                "applicant_address_line_1": row.get("applicant_address_line_1"),
                "applicant_town": row.get("applicant_town"),
                "applicant_county": row.get("applicant_county"),
                "lat": lat,
                "longitude": lng,
                "eircode": row.get("eircode"),
            }

            db.add(FSCApplication(**record))

            stats["new"] += 1
            stats["processed"] += 1

            if stats["processed"] % 5000 == 0:
                await db.commit()
                logger.info(f"BCMS FSC: Processed {stats['processed']:,} rows")

        await db.commit()

        sync_log.completed_at = datetime.utcnow()
        sync_log.records_processed = stats["processed"]
        sync_log.records_new = stats["new"]
        sync_log.status = "completed"
        await db.commit()

    except Exception as e:
        logger.error(f"BCMS FSC ingest error: {e}")
        sync_log.error_message = str(e)[:1000]
        sync_log.status = "failed"
        await db.commit()

    logger.info(f"BCMS FSC: Ingest complete — {stats}")
    return stats
