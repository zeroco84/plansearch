"""PlanSearch — BCMS Ingest Worker.

Building Control Management System open data.
Two datasets:
  A) Commencement Notices + Certificates of Compliance on Completion (CN/CCC)
  B) Fire Safety Certificate / Disability Access Certificate applications (FSC/DAC)

Both are free, no auth, updated regularly.
Join key to planning applications: planning permission reference number.
"""

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


async def download_csv(url: str) -> pd.DataFrame:
    """Download a CSV file from BCMS open data."""
    logger.info(f"Downloading CSV from {url}")
    async with httpx.AsyncClient(
        headers=HEADERS, follow_redirects=True, timeout=120.0
    ) as client:
        r = await client.get(url)
        r.raise_for_status()
    df = pd.read_csv(io.StringIO(r.text), low_memory=False)
    logger.info(f"Downloaded {len(df)} rows")
    return df


async def ingest_commencement_notices(
    db: AsyncSession, df: pd.DataFrame
) -> int:
    """Upsert commencement notices into commencement_notices table.

    Also updates lifecycle_stage on matching applications.
    Uses the existing model schema (reg_ref as the join key).
    """
    count = 0
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
                    row.get("CN_Local_Authority") or row.get("local_authority")
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

            if stage:
                await db.execute(
                    text("""
                        UPDATE applications
                        SET lifecycle_stage = :stage,
                            lifecycle_updated_at = NOW()
                        WHERE reg_ref = :ref
                          AND (lifecycle_stage IS NULL
                               OR lifecycle_stage NOT IN ('complete'))
                    """),
                    {"stage": stage, "ref": planning_ref},
                )

            count += 1
            if count % 500 == 0:
                await db.commit()
                logger.info(f"Committed {count} commencement notices...")

        except Exception as e:
            logger.error(f"Error processing commencement notice: {e}")
            continue

    await db.commit()
    logger.info(f"Upserted {count} commencement notices")
    return count


async def ingest_fsc_applications(
    db: AsyncSession, df: pd.DataFrame
) -> int:
    """Upsert FSC/DAC applications into fsc_applications table.

    FSC filing is a strong signal developer is committed to build.
    Updates lifecycle_stage to 'fsc_filed' on matching applications.
    Uses the existing model schema.
    """
    count = 0
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

            count += 1
            if count % 500 == 0:
                await db.commit()
                logger.info(f"Committed {count} FSC applications...")

        except Exception as e:
            logger.error(f"Error processing FSC application: {e}")
            continue

    await db.commit()
    logger.info(f"Upserted {count} FSC applications")
    return count


async def run_bcms_ingest(db: AsyncSession) -> dict:
    """Run the full BCMS ingest pipeline.

    Downloads and upserts both commencement notices and FSC applications.
    """
    logger.info("Starting BCMS ingest...")

    sync_log = SyncLog(sync_type="bcms_ingest", status="running")
    db.add(sync_log)
    await db.flush()

    stats = {"cn_count": 0, "fsc_count": 0}

    try:
        logger.info("Downloading BCMS commencement notices...")
        cn_df = await download_csv(BCMS_CN_URL)
        stats["cn_count"] = await ingest_commencement_notices(db, cn_df)

        logger.info("Downloading BCMS FSC applications...")
        fsc_df = await download_csv(BCMS_FSC_URL)
        stats["fsc_count"] = await ingest_fsc_applications(db, fsc_df)

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
