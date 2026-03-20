"""PlanSearch — BCMS Ingest Worker.

Building Control Management System open data.
Two datasets:
  A) Commencement Notices + Certificates of Compliance on Completion (CN/CCC)
  B) Fire Safety Certificate / Disability Access Certificate applications (FSC/DAC)

Both are free, no auth, updated regularly.
Join key to planning applications: planning permission reference number.
"""

import asyncio
import io
import logging
from datetime import datetime
from typing import Optional

import httpx
import pandas as pd
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import SyncLog
from app.utils.text_clean import normalise_reg_ref

logger = logging.getLogger(__name__)

# Dataset A: Commencement Notices + Certificates of Compliance on Completion
BCMS_CN_URL = (
    "https://data.nbco.gov.ie/dataset/"
    "2704a333-874d-46f5-b3bc-3673766bf816/resource/"
    "0774e781-7af8-46da-b623-872e74cf541e/download/buildingscnscccs.csv"
)

# Dataset B: FSC/DAC Applications
BCMS_FSC_URL = (
    "https://data.nbco.gov.ie/dataset/"
    "ae8f9134-fc5a-41e1-a150-bcccede234a0/resource/"
    "b1de41a3-e14c-40b7-b0d7-4e85d7a648fc/download/applications.csv"
)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; PlanSearch/1.0; +https://plansearch.cc)",
    "Accept": "text/csv,text/plain,*/*",
}

CSV_CHUNK_SIZE = 1000

# Reverse of NPAD AUTHORITY_CODES — maps full authority name to code
BCMS_AUTHORITY_TO_CODE = {
    "Carlow County Council": "CW",
    "Cavan County Council": "CN",
    "Clare County Council": "CE",
    "Cork City Council": "CO",
    "Cork County Council": "CC",
    "Donegal County Council": "DL",
    "Dublin City Council": "DC",
    "Dún Laoghaire-Rathdown County Council": "DLR",
    "Dun Laoghaire-Rathdown County Council": "DLR",
    "Fingal County Council": "FG",
    "Galway City Council": "GY",
    "Galway County Council": "GC",
    "Kerry County Council": "KY",
    "Kildare County Council": "KE",
    "Kilkenny County Council": "KK",
    "Laois County Council": "LS",
    "Leitrim County Council": "LM",
    "Limerick City & County Council": "LK",
    "Limerick County Council": "LK",
    "Longford County Council": "LD",
    "Louth County Council": "LH",
    "Mayo County Council": "MO",
    "Meath County Council": "MH",
    "Monaghan County Council": "MN",
    "Offaly County Council": "OY",
    "Roscommon County Council": "RN",
    "Sligo County Council": "SO",
    "South Dublin County Council": "SD",
    "Tipperary County Council": "TA",
    "Waterford City & County Council": "WD",
    "Waterford City and County Council": "WD",
    "Westmeath County Council": "WH",
    "Wexford County Council": "WX",
    "Wicklow County Council": "WW",
}


def safe_str(val) -> Optional[str]:
    if val is None or str(val).strip() in ("", "None", "nan", "null"):
        return None
    return str(val).strip()


def safe_date(val):
    if pd.isna(val) or val is None:
        return None
    try:
        return pd.to_datetime(val).date()
    except Exception:
        return None


def safe_float(val) -> Optional[float]:
    try:
        f = float(val)
        return f if f > 0 else None
    except (TypeError, ValueError):
        return None


def safe_int(val) -> Optional[int]:
    try:
        if pd.notna(val):
            return int(float(val))
    except (TypeError, ValueError):
        pass
    return None


async def download_csv_text(url: str) -> str:
    """Download a CSV file from BCMS open data — returns raw text."""
    logger.info(f"Downloading CSV from {url}")
    async with httpx.AsyncClient(
        headers=HEADERS, follow_redirects=True, timeout=120.0
    ) as client:
        r = await client.get(url)
        r.raise_for_status()
    logger.info(f"Downloaded {len(r.text)} bytes")
    return r.text


async def ingest_commencement_notices(
    db: AsyncSession, df: pd.DataFrame, progress: Optional[dict] = None
) -> int:
    """Upsert commencement notices into commencement_notices table.

    Also updates lifecycle_stage on matching applications.
    Uses savepoints per record and commits every 100 rows.
    """
    count = 0
    errors = 0
    for _, row in df.iterrows():
        try:
            planning_ref = safe_str(
                row.get("CN_Planning_Permission_Number")
                or row.get("planning_permission_number")
            )
            if not planning_ref:
                continue
            planning_ref = normalise_reg_ref(planning_ref)

            values = {
                "reg_ref": planning_ref,
                "local_authority": safe_str(
                    row.get("LocalAuthority") or row.get("local_authority")
                ),
                "cn_commencement_date": safe_date(row.get("CN_Commencement_Date")),
                "cn_total_floor_area": safe_float(
                    row.get("CN_Total_floor_area_of_building")
                ),
                "cn_total_dwelling_units": safe_int(
                    row.get("CN_Total_Number_of_Dwelling_Units")
                ),
                "cn_total_apartments": safe_int(row.get("CN_Total_apartments")),
                "cn_number_stories_above": safe_int(
                    row.get("CN_Number_stories_above_ground")
                ),
                "cn_number_bedrooms": safe_int(row.get("CN_Number_bedrooms")),
                "cn_protected_structure": bool(row.get("CN_Protected_structure")),
                "cn_lat": safe_float(row.get("CN_LAT")),
                "cn_lng": safe_float(row.get("CN_LNG")),
                "ccc_date_validated": safe_date(row.get("CCC_Date_Validated")),
                "ccc_units_completed": safe_int(row.get("CCC_Units_Completed")),
            }

            # Clean None/nan strings
            for k in list(values.keys()):
                if isinstance(values[k], str) and values[k] in (
                    "nan", "None", "null", ""
                ):
                    values[k] = None

            # Savepoint per record
            await db.execute(text("SAVEPOINT bcms_cn_upsert"))
            try:
                cols = list(values.keys())
                placeholders = [f":{k}" for k in cols]
                update_parts = [
                    f"{k} = EXCLUDED.{k}" for k in cols if k != "reg_ref"
                ]
                sql = text(f"""
                    INSERT INTO commencement_notices ({', '.join(cols)})
                    VALUES ({', '.join(placeholders)})
                    ON CONFLICT (reg_ref) DO UPDATE SET {', '.join(update_parts)}
                """)
                await db.execute(sql, values)

                # Update lifecycle_stage on matching application
                if values.get("ccc_date_validated"):
                    stage = "complete"
                elif values.get("cn_commencement_date"):
                    stage = "under_construction"
                else:
                    stage = None

                if stage and values.get("local_authority"):
                    # Build prefixed ref matching applications table format
                    code = BCMS_AUTHORITY_TO_CODE.get(
                        values["local_authority"], ""
                    )
                    if code:
                        prefixed_ref = f"{code}/{planning_ref}"
                        await db.execute(
                            text("""
                                UPDATE applications
                                SET lifecycle_stage = :stage,
                                    lifecycle_updated_at = NOW()
                                WHERE reg_ref = :ref
                                  AND (lifecycle_stage IS NULL
                                       OR lifecycle_stage NOT IN ('complete'))
                            """),
                            {"stage": stage, "ref": prefixed_ref},
                        )

                await db.execute(text("RELEASE SAVEPOINT bcms_cn_upsert"))

                # ── Webhook dispatch for lifecycle changes ──
                try:
                    if stage and code:
                        from app.workers.webhook_dispatcher import create_webhook_delivery
                        event = "application.completed" if stage == "complete" else "application.commenced"
                        payload = {
                            "event": event,
                            "data": {
                                "reg_ref": prefixed_ref,
                                "planning_authority": values.get("local_authority"),
                                "lifecycle_stage": stage,
                                "cn_commencement_date": str(values.get("cn_commencement_date")) if values.get("cn_commencement_date") else None,
                                "ccc_date_validated": str(values.get("ccc_date_validated")) if values.get("ccc_date_validated") else None,
                            },
                        }
                        await create_webhook_delivery(event, prefixed_ref, payload, db)
                except Exception as wh_err:
                    logger.debug(f"Webhook dispatch skipped for CN {planning_ref}: {wh_err}")
            except Exception as db_err:
                await db.execute(text("ROLLBACK TO SAVEPOINT bcms_cn_upsert"))
                logger.error(f"DB error for CN {planning_ref}: {db_err}")
                errors += 1
                if progress:
                    progress["errors"] += 1
                continue

            count += 1
            if progress:
                progress["processed"] += 1

            if count % 100 == 0:
                await db.commit()
                logger.info(f"Committed {count} commencement notices...")

            if count % 1000 == 0:
                await asyncio.sleep(0.5)

        except Exception as e:
            logger.error(f"Error processing commencement notice: {e}")
            errors += 1
            if progress:
                progress["errors"] += 1
            continue

    await db.commit()
    logger.info(f"Upserted {count} commencement notices ({errors} errors)")
    return count


async def ingest_fsc_applications(
    db: AsyncSession, df: pd.DataFrame, progress: Optional[dict] = None
) -> int:
    """Upsert FSC/DAC applications into fsc_applications table.

    FSC filing is a strong signal developer is committed to build.
    Updates lifecycle_stage to 'fsc_filed' on matching applications.
    Uses savepoints per record and commits every 100 rows.
    """
    count = 0
    errors = 0
    for _, row in df.iterrows():
        try:
            planning_ref = safe_str(
                row.get("planning_permission_reference_no")
                or row.get("PlanningPermissionReferenceNo")
            )
            if not planning_ref:
                continue
            planning_ref = normalise_reg_ref(planning_ref)

            values = {
                "reg_ref": planning_ref,
                "application_reference_no": safe_str(
                    row.get("application_reference_no")
                ),
                "application_type": safe_str(row.get("application_type")),
                "local_authority": safe_str(row.get("local_authority")),
                "submission_date": safe_date(row.get("submission_date")),
                "date_of_decision": safe_date(row.get("date_of_decision")),
                "decision_type": safe_str(row.get("decision_type")),
                "floor_area_of_building": safe_float(
                    row.get("floor_area_of_building")
                ),
                "no_of_stories_above_ground": safe_int(
                    row.get("no_of_stories_above_ground_level")
                ),
                "date_construction_started": safe_date(
                    row.get("date_construction_started")
                ),
                "is_construction_complete": bool(
                    row.get("is_construction_of_building_complete")
                ),
                "applicant_name": safe_str(row.get("applicant_name")),
            }

            for k in list(values.keys()):
                if isinstance(values[k], str) and values[k] in (
                    "nan", "None", "null", ""
                ):
                    values[k] = None

            # Savepoint per record
            await db.execute(text("SAVEPOINT bcms_fsc_upsert"))
            try:
                cols = list(values.keys())
                placeholders = [f":{k}" for k in cols]
                update_parts = [
                    f"{k} = EXCLUDED.{k}" for k in cols if k != "reg_ref"
                ]
                sql = text(f"""
                    INSERT INTO fsc_applications ({', '.join(cols)})
                    VALUES ({', '.join(placeholders)})
                    ON CONFLICT (reg_ref) DO UPDATE SET {', '.join(update_parts)}
                """)
                await db.execute(sql, values)

                # Update lifecycle_stage — FSC filed means construction is imminent
                await db.execute(
                    text("""
                        UPDATE applications
                        SET lifecycle_stage = 'fsc_filed',
                            lifecycle_updated_at = NOW()
                        WHERE reg_ref = :ref
                          AND (lifecycle_stage IS NULL
                               OR lifecycle_stage IN (
                                   'submitted', 'registered',
                                   'decided_granted', 'appealed',
                                   'appeal_granted'
                               ))
                    """),
                    {"ref": planning_ref},
                )

                await db.execute(text("RELEASE SAVEPOINT bcms_fsc_upsert"))

                # ── Webhook dispatch for FSC filed ──
                try:
                    from app.workers.webhook_dispatcher import create_webhook_delivery
                    event = "application.fsc_filed"
                    payload = {
                        "event": event,
                        "data": {
                            "reg_ref": planning_ref,
                            "planning_authority": values.get("local_authority"),
                            "application_type": values.get("application_type"),
                            "submission_date": str(values.get("submission_date")) if values.get("submission_date") else None,
                            "lifecycle_stage": "fsc_filed",
                        },
                    }
                    await create_webhook_delivery(event, planning_ref, payload, db)
                except Exception as wh_err:
                    logger.debug(f"Webhook dispatch skipped for FSC {planning_ref}: {wh_err}")
            except Exception as db_err:
                await db.execute(text("ROLLBACK TO SAVEPOINT bcms_fsc_upsert"))
                logger.error(f"DB error for FSC {planning_ref}: {db_err}")
                errors += 1
                if progress:
                    progress["errors"] += 1
                continue

            count += 1
            if progress:
                progress["processed"] += 1

            if count % 100 == 0:
                await db.commit()
                logger.info(f"Committed {count} FSC applications...")

            if count % 1000 == 0:
                await asyncio.sleep(0.5)

        except Exception as e:
            logger.error(f"Error processing FSC application: {e}")
            errors += 1
            if progress:
                progress["errors"] += 1
            continue

    await db.commit()
    logger.info(f"Upserted {count} FSC applications ({errors} errors)")
    return count


async def run_bcms_ingest(db: AsyncSession) -> dict:
    """Run the full BCMS ingest pipeline.

    Downloads CSVs and processes in chunks of 1000 rows to avoid
    loading everything into RAM at once.
    """
    logger.info("Starting BCMS ingest...")

    sync_log = SyncLog(sync_type="bcms_ingest", status="running")
    db.add(sync_log)
    await db.flush()

    stats = {"cn_count": 0, "fsc_count": 0}

    try:
        logger.info("Downloading BCMS commencement notices...")
        cn_text = await download_csv_text(BCMS_CN_URL)
        chunks = pd.read_csv(io.StringIO(cn_text), low_memory=False, chunksize=CSV_CHUNK_SIZE)
        for chunk in chunks:
            stats["cn_count"] += await ingest_commencement_notices(db, chunk)

        logger.info("Downloading BCMS FSC applications...")
        fsc_text = await download_csv_text(BCMS_FSC_URL)
        chunks = pd.read_csv(io.StringIO(fsc_text), low_memory=False, chunksize=CSV_CHUNK_SIZE)
        for chunk in chunks:
            stats["fsc_count"] += await ingest_fsc_applications(db, chunk)

        sync_log.status = "completed"
        sync_log.completed_at = datetime.utcnow()
        sync_log.records_processed = stats["cn_count"] + stats["fsc_count"]
        await db.commit()

        logger.info(f"BCMS ingest complete: {stats}")
        return stats

    except Exception as e:
        sync_log.status = "failed"
        sync_log.error_message = str(e)
        sync_log.completed_at = datetime.utcnow()
        await db.commit()
        logger.error(f"BCMS ingest failed: {e}")
        raise


async def run_bcms_ingest_with_progress(
    db: AsyncSession, progress: dict
) -> dict:
    """Run BCMS ingest with live progress updates to a shared dict.

    Downloads CSVs and processes in chunks of 1000 rows.
    Supports stop_requested flag from admin UI.
    """
    logger.info("Starting BCMS ingest (with progress)...")

    stats = {"cn_count": 0, "fsc_count": 0}

    try:
        logger.info("Downloading BCMS commencement notices...")
        cn_text = await download_csv_text(BCMS_CN_URL)
        chunks = pd.read_csv(io.StringIO(cn_text), low_memory=False, chunksize=CSV_CHUNK_SIZE)
        for chunk in chunks:
            if progress.get("stop_requested"):
                logger.info("BCMS ingest stopped by admin")
                await db.commit()
                break
            stats["cn_count"] += await ingest_commencement_notices(db, chunk, progress)

        if not progress.get("stop_requested"):
            logger.info("Downloading BCMS FSC applications...")
            fsc_text = await download_csv_text(BCMS_FSC_URL)
            chunks = pd.read_csv(io.StringIO(fsc_text), low_memory=False, chunksize=CSV_CHUNK_SIZE)
            for chunk in chunks:
                if progress.get("stop_requested"):
                    logger.info("BCMS ingest stopped by admin")
                    await db.commit()
                    break
                stats["fsc_count"] += await ingest_fsc_applications(db, chunk, progress)

        progress["running"] = False
        progress["stop_requested"] = False
        logger.info(f"BCMS ingest complete: {stats}")
        return stats

    except Exception as e:
        progress["running"] = False
        progress["stop_requested"] = False
        logger.error(f"BCMS ingest failed: {e}")
        raise
