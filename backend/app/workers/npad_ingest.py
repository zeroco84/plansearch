"""PlanSearch — NPAD ArcGIS Ingest Worker.

National Planning Application Database — covers 30/31 local authorities.
~362,000 applications, updated weekly, CC BY 4.0, no auth required.
"""

import logging
from datetime import datetime
from typing import Optional

import httpx
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import SyncLog
from app.utils.text_clean import clean_text, normalise_reg_ref, normalise_decision

logger = logging.getLogger(__name__)

NPAD_BASE = (
    "https://services.arcgis.com/NzlPQPKn5QF9v2US/arcgis/rest/services"
    "/IrishPlanningApplications/FeatureServer/0"
)
PAGE_SIZE = 2000

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; PlanSearch/1.0; +https://plansearch.cc)",
    "Accept": "application/json",
}


def safe_str(val) -> Optional[str]:
    if val is None or str(val).strip() in ("", "None", "nan", "null"):
        return None
    return str(val).strip()


def safe_date(val):
    """Parse NPAD date (Unix ms timestamp) to Python date."""
    if val is None:
        return None
    try:
        if isinstance(val, (int, float)) and val > 0:
            return datetime.utcfromtimestamp(val / 1000).date()
    except Exception:
        pass
    return None


async def fetch_npad_page(client: httpx.AsyncClient, offset: int) -> list:
    """Fetch one page of NPAD records."""
    params = {
        "where": "1=1",
        "outFields": "*",
        "resultRecordCount": PAGE_SIZE,
        "resultOffset": offset,
        "f": "json",
    }
    r = await client.get(f"{NPAD_BASE}/query", params=params, timeout=60.0)
    r.raise_for_status()
    data = r.json()
    return [f["attributes"] for f in data.get("features", [])]


async def upsert_npad_record(db: AsyncSession, attrs: dict) -> bool:
    """Upsert a single NPAD record into the applications table."""
    reg_ref = safe_str(attrs.get("AppRegRef") or attrs.get("ReferenceNumber"))
    if not reg_ref:
        return False
    reg_ref = normalise_reg_ref(reg_ref)

    forename = safe_str(attrs.get("ApplicantForename"))
    surname = safe_str(attrs.get("ApplicantSurname"))
    full_name = " ".join(filter(None, [forename, surname])) or None

    values = {
        "reg_ref": reg_ref,
        "planning_authority": safe_str(
            attrs.get("LocalAuthority") or attrs.get("PlanningAuthority")
        ),
        "applicant_forename": forename,
        "applicant_surname": surname,
        "applicant_name": full_name,
        "proposal": clean_text(
            safe_str(attrs.get("Development") or attrs.get("Description"))
        ),
        "location": clean_text(
            safe_str(attrs.get("Location") or attrs.get("Address"))
        ),
        "decision": normalise_decision(safe_str(attrs.get("Decision")) or ""),
        "apn_date": safe_date(
            attrs.get("ReceivedDate") or attrs.get("ApplicationDate")
        ),
        "rgn_date": safe_date(attrs.get("RegisteredDate")),
        "dec_date": safe_date(attrs.get("DecisionDate")),
        "app_type": safe_str(attrs.get("ApplicationType")),
        "land_use_code": safe_str(attrs.get("LandUseCode")),
        "floor_area": float(attrs["FloorArea"]) if attrs.get("FloorArea") else None,
        "num_residential_units": (
            int(attrs["NumResidentialUnits"])
            if attrs.get("NumResidentialUnits")
            else None
        ),
        "area_of_site": (
            float(attrs["AreaofSite"]) if attrs.get("AreaofSite") else None
        ),
        "one_off_house": bool(attrs.get("OneOffHouse")),
        "link_app_details": safe_str(attrs.get("LinkAppDetails")),
        "npad_object_id": (
            int(attrs["OBJECTID"]) if attrs.get("OBJECTID") else None
        ),
        "data_source": "npad",
    }

    lat = attrs.get("Latitude") or attrs.get("lat")
    lng = attrs.get("Longitude") or attrs.get("lon") or attrs.get("lng")

    # Clean None/nan strings
    for k in list(values.keys()):
        if isinstance(values[k], str) and values[k] in ("nan", "None", "null", ""):
            values[k] = None

    try:
        cols = list(values.keys())
        placeholders = [f":{k}" for k in cols]
        update_parts = [f"{k} = EXCLUDED.{k}" for k in cols if k != "reg_ref"]

        if lat and lng:
            lat, lng = float(lat), float(lng)
            sql = text(f"""
                INSERT INTO applications ({', '.join(cols)}, location_point)
                VALUES ({', '.join(placeholders)},
                        ST_SetSRID(ST_MakePoint({lng}, {lat}), 4326))
                ON CONFLICT (reg_ref) DO UPDATE SET
                    {', '.join(update_parts)},
                    location_point = EXCLUDED.location_point
            """)
        else:
            sql = text(f"""
                INSERT INTO applications ({', '.join(cols)})
                VALUES ({', '.join(placeholders)})
                ON CONFLICT (reg_ref) DO UPDATE SET {', '.join(update_parts)}
            """)

        await db.execute(sql, values)
        return True
    except Exception as e:
        logger.error(f"Error upserting {reg_ref}: {e}")
        return False


async def run_npad_ingest(
    db: AsyncSession, limit: Optional[int] = None
) -> dict:
    """Run the full NPAD ingest pipeline.

    Paginates through the ArcGIS REST API in pages of 2000 records.
    Total dataset is ~362,000 applications across 31 local authorities.
    """
    logger.info("Starting NPAD ingest...")

    sync_log = SyncLog(sync_type="npad_ingest", status="running")
    db.add(sync_log)
    await db.flush()

    stats = {"processed": 0, "errors": 0}

    try:
        async with httpx.AsyncClient(
            headers=HEADERS, follow_redirects=True
        ) as client:
            offset = 0
            while True:
                logger.info(f"Fetching NPAD page at offset {offset}...")
                records = await fetch_npad_page(client, offset)

                if not records:
                    logger.info("No more records — ingest complete")
                    break

                for attrs in records:
                    ok = await upsert_npad_record(db, attrs)
                    if ok:
                        stats["processed"] += 1
                    else:
                        stats["errors"] += 1

                    if stats["processed"] % 500 == 0 and stats["processed"] > 0:
                        await db.commit()
                        logger.info(f"Committed {stats['processed']} records...")

                    if limit and stats["processed"] >= limit:
                        break

                await db.commit()
                offset += PAGE_SIZE

                if len(records) < PAGE_SIZE:
                    break
                if limit and stats["processed"] >= limit:
                    break

        sync_log.status = "completed"
        sync_log.completed_at = datetime.utcnow()
        sync_log.records_processed = stats["processed"]
        await db.commit()

        logger.info(f"NPAD ingest complete: {stats}")
        return stats

    except Exception as e:
        sync_log.status = "failed"
        sync_log.error_message = str(e)
        sync_log.completed_at = datetime.utcnow()
        await db.commit()
        logger.error(f"NPAD ingest failed: {e}")
        raise
