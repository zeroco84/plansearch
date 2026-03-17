"""PlanSearch — DCC CSV Ingest Worker.

Downloads 4 CSV files from Dublin City Council Open Data nightly,
converts ITM coordinates to WGS84, and upserts into the database.
"""

import io
import logging
from datetime import datetime
from typing import Optional

import httpx
import pandas as pd
from sqlalchemy import text, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.dialects.postgresql import insert

from app.config import get_settings
from app.models import Application, Appeal, FurtherInfo, SyncLog
from app.utils.itm_to_wgs84 import itm_to_wgs84, is_valid_dublin_coords
from app.utils.text_clean import clean_text, normalise_reg_ref, normalise_decision

logger = logging.getLogger(__name__)
settings = get_settings()


def detect_year_from_ref(reg_ref: str) -> Optional[int]:
    """Extract the year from a registration reference.

    Handles formats like:
    - "1234/24" -> 2024
    - "FRL/2024/12345" -> 2024
    - "1234/05" -> 2005
    """
    if not reg_ref:
        return None

    import re

    # Try 4-digit year
    match = re.search(r'/(20\d{2})/', reg_ref)
    if match:
        return int(match.group(1))

    # Try 2-digit year at end (e.g., "1234/24")
    match = re.search(r'/(\d{2})$', reg_ref)
    if match:
        yy = int(match.group(1))
        return 2000 + yy if yy < 50 else 1900 + yy

    return None


def parse_csv_row(row: dict) -> Optional[dict]:
    """Parse a raw CSV row into application fields.

    Returns None if the row has no valid reg_ref.
    """
    reg_ref = str(row.get("APPLICATION_NUMBER", "") or row.get("REG_REF", "")).strip()
    if not reg_ref or reg_ref == "nan":
        return None

    return {
        "reg_ref": reg_ref,
        "app_type": clean_text(str(row.get("APPLICATION_TYPE", ""))),
        "apn_date": row.get("APPLICATION_DATE"),
        "location": clean_text(str(row.get("LOCATION_1", "") or row.get("LOCATION", ""))),
        "proposal": clean_text(str(row.get("DESCRIPTION", "") or row.get("PROPOSAL", ""))),
        "decision": str(row.get("DECISION", "")),
        "dec_date": row.get("DECISION_DATE"),
        "rgn_date": row.get("REGISTRATION_DATE"),
        "year": detect_year_from_ref(reg_ref),
    }


def merge_spatial_data(base_df: pd.DataFrame, spatial_df: pd.DataFrame) -> pd.DataFrame:
    """Merge spatial dataframe with base applications on REG_REF.

    Returns merged dataframe.
    """
    base_ref = find_column(base_df, "REG_REF", "REGREF", "APPLICATION_NUMBER")
    spatial_ref = find_column(spatial_df, "REG_REF", "REGREF", "APPLICATION_NUMBER")

    if not base_ref or not spatial_ref:
        logger.warning("Cannot merge — REG_REF column not found")
        return base_df

    spatial_cols = [spatial_ref]
    for col in ["lat", "lng", "itm_easting", "itm_northing"]:
        if col in spatial_df.columns:
            spatial_cols.append(col)

    merged = base_df.merge(
        spatial_df[spatial_cols].drop_duplicates(subset=[spatial_ref]),
        left_on=base_ref,
        right_on=spatial_ref,
        how="left",
    )
    return merged


async def download_csv(url: str, limit: Optional[int] = None) -> pd.DataFrame:
    """Download a CSV file from DCC Open Data.

    Args:
        url: URL to the CSV file
        limit: Optional row limit for testing (first N rows)
    """
    logger.info(f"Downloading CSV from {url}")
    headers = {
        "User-Agent": "Mozilla/5.0 (compatible; PlanSearch/1.0; +https://plansearch.cc)",
        "Accept": "text/csv,text/plain,*/*",
        "Accept-Language": "en-IE,en;q=0.9",
    }
    async with httpx.AsyncClient(headers=headers, follow_redirects=True, timeout=120.0) as client:
        response = await client.get(url)
        response.raise_for_status()

    df = pd.read_csv(io.StringIO(response.text), low_memory=False)
    logger.info(f"Downloaded {len(df)} rows from {url}")

    if limit:
        df = df.head(limit)
        logger.info(f"Limited to {limit} rows for testing")

    return df


def convert_spatial_coordinates(df: pd.DataFrame) -> pd.DataFrame:
    """Convert ITM coordinates to WGS84 lat/lng.

    The DCC_PlanApps.csv uses ITM (EPSG:2157) coordinates.
    We convert to WGS84 (EPSG:4326) for mapping.
    """
    # Identify the ITM coordinate columns (they may have different names)
    easting_col = None
    northing_col = None

    for col in df.columns:
        col_upper = col.upper()
        if "EAST" in col_upper or "X" == col_upper or col_upper == "ITM_E":
            easting_col = col
        elif "NORTH" in col_upper or "Y" == col_upper or col_upper == "ITM_N":
            northing_col = col

    if not easting_col or not northing_col:
        logger.warning("Could not find ITM coordinate columns in spatial CSV")
        return df

    logger.info(f"Converting ITM coordinates: {easting_col}, {northing_col}")

    lats = []
    lngs = []

    for _, row in df.iterrows():
        try:
            e = float(row[easting_col])
            n = float(row[northing_col])
            if e > 0 and n > 0:
                lat, lng = itm_to_wgs84(e, n)
                if is_valid_dublin_coords(lat, lng):
                    lats.append(lat)
                    lngs.append(lng)
                else:
                    lats.append(None)
                    lngs.append(None)
            else:
                lats.append(None)
                lngs.append(None)
        except (ValueError, TypeError):
            lats.append(None)
            lngs.append(None)

    df["lat"] = lats
    df["lng"] = lngs
    df["itm_easting"] = df[easting_col]
    df["itm_northing"] = df[northing_col]

    valid = df["lat"].notna().sum()
    logger.info(f"Converted {valid}/{len(df)} coordinates successfully")

    return df


def find_column(df: pd.DataFrame, *candidates: str) -> Optional[str]:
    """Find the first matching column name (case-insensitive)."""
    df_cols_upper = {c.upper(): c for c in df.columns}
    for candidate in candidates:
        if candidate.upper() in df_cols_upper:
            return df_cols_upper[candidate.upper()]
    return None


def safe_date(val) -> Optional[datetime]:
    """Safely parse a date value."""
    if pd.isna(val) or val is None or str(val).strip() == "":
        return None
    try:
        return pd.to_datetime(val).date()
    except Exception:
        return None


async def upsert_applications(db: AsyncSession, merged_df: pd.DataFrame) -> dict:
    """Upsert application records into the database.

    Uses INSERT ... ON CONFLICT DO UPDATE to handle both new
    and updated records efficiently.
    """
    stats = {"processed": 0, "new": 0, "updated": 0, "errors": 0}

    reg_ref_col = find_column(merged_df, "REG_REF", "REGREF", "REG REF")
    if not reg_ref_col:
        logger.error("Cannot find REG_REF column in merged data")
        return stats

    for _, row in merged_df.iterrows():
        try:
            reg_ref = str(row.get(reg_ref_col, "")).strip()
            if not reg_ref or reg_ref == "nan":
                continue

            reg_ref = normalise_reg_ref(reg_ref)

            values = {
                "reg_ref": reg_ref,
                "apn_date": safe_date(row.get(find_column(merged_df, "APNDAT", "APN_DATE") or "APNDAT")),
                "rgn_date": safe_date(row.get(find_column(merged_df, "RGNDAT", "RGN_DATE") or "RGNDAT")),
                "dec_date": safe_date(row.get(find_column(merged_df, "DECDAT", "DEC_DATE") or "DECDAT")),
                "final_grant_date": safe_date(row.get(find_column(merged_df, "FINAL_GRNT_DATE", "FINALGRANTDATE") or "FINAL_GRNT_DATE")),
                "proposal": clean_text(str(row.get(find_column(merged_df, "PROPOSAL") or "PROPOSAL", ""))),
                "long_proposal": clean_text(str(row.get(find_column(merged_df, "LONG_PROPOSAL", "LONGPROPOSAL") or "LONG_PROPOSAL", ""))),
                "location": clean_text(str(row.get(find_column(merged_df, "LOCATION") or "LOCATION", ""))),
                "app_type": clean_text(str(row.get(find_column(merged_df, "APPTYPE", "APP_TYPE") or "APPTYPE", ""))),
                "stage": clean_text(str(row.get(find_column(merged_df, "STAGE") or "STAGE", ""))),
                "decision": normalise_decision(str(row.get(find_column(merged_df, "DECISION") or "DECISION", ""))),
            }

            # Add spatial data if available
            if "lat" in row.index and pd.notna(row.get("lat")):
                lat = float(row["lat"])
                lng = float(row["lng"])
                values["itm_easting"] = float(row.get("itm_easting", 0)) if pd.notna(row.get("itm_easting")) else None
                values["itm_northing"] = float(row.get("itm_northing", 0)) if pd.notna(row.get("itm_northing")) else None
                values["location_point"] = text(f"ST_SetSRID(ST_MakePoint({lng}, {lat}), 4326)")

            # Clean None/nan strings
            for key in list(values.keys()):
                if isinstance(values[key], str) and (values[key] == "nan" or values[key] == "None"):
                    values[key] = None

            # Store raw data as JSONB
            raw_data = {}
            for col in merged_df.columns:
                val = row.get(col)
                if pd.notna(val):
                    raw_data[col] = str(val)
            values["raw_data"] = raw_data

            # Upsert using raw SQL for PostGIS point handling
            if "location_point" in values and values["location_point"] is not None:
                point_sql = values.pop("location_point")
                cols = list(values.keys())
                placeholders = [f":{k}" for k in cols]
                update_parts = [f"{k} = EXCLUDED.{k}" for k in cols if k != "reg_ref"]

                sql = text(f"""
                    INSERT INTO applications ({', '.join(cols)}, location_point)
                    VALUES ({', '.join(placeholders)}, {point_sql.text})
                    ON CONFLICT (reg_ref) DO UPDATE SET
                    {', '.join(update_parts)},
                    location_point = EXCLUDED.location_point
                """)
                await db.execute(sql, values)
            else:
                cols = list(values.keys())
                placeholders = [f":{k}" for k in cols]
                update_parts = [f"{k} = EXCLUDED.{k}" for k in cols if k != "reg_ref"]

                sql = text(f"""
                    INSERT INTO applications ({', '.join(cols)})
                    VALUES ({', '.join(placeholders)})
                    ON CONFLICT (reg_ref) DO UPDATE SET
                    {', '.join(update_parts)}
                """)
                await db.execute(sql, values)

            stats["processed"] += 1

            # Commit in batches of 500
            if stats["processed"] % 500 == 0:
                await db.commit()
                logger.info(f"Processed {stats['processed']} applications...")

        except Exception as e:
            stats["errors"] += 1
            logger.error(f"Error processing row: {e}")
            continue

    await db.commit()
    logger.info(f"Ingest complete: {stats}")
    return stats


async def upsert_appeals(db: AsyncSession, appeal_df: pd.DataFrame) -> int:
    """Upsert appeal records."""
    count = 0
    reg_ref_col = find_column(appeal_df, "REG_REF", "REGREF")
    if not reg_ref_col:
        return 0

    for _, row in appeal_df.iterrows():
        try:
            reg_ref = normalise_reg_ref(str(row.get(reg_ref_col, "")))
            if not reg_ref or reg_ref == "NAN":
                continue

            appeal_ref = clean_text(str(row.get(find_column(appeal_df, "APPEAL_REF", "APPEALREF") or "", "")))

            values = {
                "reg_ref": reg_ref,
                "appeal_ref": appeal_ref,
                "appeal_date": safe_date(row.get(find_column(appeal_df, "APPEAL_DATE", "APPEALDATE") or "")),
                "appellant": clean_text(str(row.get(find_column(appeal_df, "APPELLANT") or "", ""))),
                "appeal_decision": clean_text(str(row.get(find_column(appeal_df, "APPEAL_DECISION", "APPEALDECISION") or "", ""))),
                "appeal_dec_date": safe_date(row.get(find_column(appeal_df, "APPEAL_DEC_DATE", "APPEALDECDATE") or "")),
            }

            # Clean None/nan strings
            for key in list(values.keys()):
                if isinstance(values[key], str) and (values[key] == "nan" or values[key] == "None" or values[key] == ""):
                    values[key] = None

            raw_data = {}
            for col in appeal_df.columns:
                val = row.get(col)
                if pd.notna(val):
                    raw_data[col] = str(val)
            values["raw_data"] = raw_data

            cols = list(values.keys())
            placeholders = [f":{k}" for k in cols]
            sql = text(f"""
                INSERT INTO appeals ({', '.join(cols)})
                VALUES ({', '.join(placeholders)})
                ON CONFLICT DO NOTHING
            """)
            await db.execute(sql, values)
            count += 1

        except Exception as e:
            logger.error(f"Error processing appeal: {e}")
            continue

    await db.commit()
    logger.info(f"Upserted {count} appeal records")
    return count


async def upsert_further_info(db: AsyncSession, fi_df: pd.DataFrame) -> int:
    """Upsert further information records."""
    count = 0
    reg_ref_col = find_column(fi_df, "REG_REF", "REGREF")
    if not reg_ref_col:
        return 0

    for _, row in fi_df.iterrows():
        try:
            reg_ref = normalise_reg_ref(str(row.get(reg_ref_col, "")))
            if not reg_ref or reg_ref == "NAN":
                continue

            values = {
                "reg_ref": reg_ref,
                "fi_date": safe_date(row.get(find_column(fi_df, "FI_DATE", "FIDATE") or "")),
                "fi_type": clean_text(str(row.get(find_column(fi_df, "FI_TYPE", "FITYPE") or "", ""))),
                "fi_response_date": safe_date(row.get(find_column(fi_df, "FI_RESPONSE_DATE", "FIRESPONSEDATE") or "")),
            }

            for key in list(values.keys()):
                if isinstance(values[key], str) and (values[key] == "nan" or values[key] == "None" or values[key] == ""):
                    values[key] = None

            raw_data = {}
            for col in fi_df.columns:
                val = row.get(col)
                if pd.notna(val):
                    raw_data[col] = str(val)
            values["raw_data"] = raw_data

            cols = list(values.keys())
            placeholders = [f":{k}" for k in cols]
            sql = text(f"""
                INSERT INTO further_info ({', '.join(cols)})
                VALUES ({', '.join(placeholders)})
                ON CONFLICT DO NOTHING
            """)
            await db.execute(sql, values)
            count += 1

        except Exception as e:
            logger.error(f"Error processing further info: {e}")
            continue

    await db.commit()
    logger.info(f"Upserted {count} further info records")
    return count


async def run_ingest(db: AsyncSession, limit: Optional[int] = None) -> dict:
    """Run the complete DCC data ingest pipeline.

    1. Download 4 CSV files from DCC open data
    2. Convert ITM coordinates to WGS84
    3. Merge base + spatial on REG_REF
    4. Upsert into applications table
    5. Upsert appeals and further info
    6. Queue new records for enrichment

    Args:
        db: Database session
        limit: Optional row limit for testing

    Returns:
        Dictionary with ingest statistics
    """
    logger.info("Starting DCC data ingest...")

    # Create sync log
    sync_log = SyncLog(sync_type="ingest", status="running")
    db.add(sync_log)
    await db.flush()

    try:
        # 1. Download CSVs
        base_df = await download_csv(settings.dcc_base_url, limit=limit)
        spatial_df = await download_csv(settings.dcc_spatial_url, limit=limit)
        appeal_df = await download_csv(settings.dcc_appeal_url, limit=limit)
        furinfo_df = await download_csv(settings.dcc_furinfo_url, limit=limit)

        # 2. Convert ITM coordinates
        spatial_df = convert_spatial_coordinates(spatial_df)

        # 3. Merge base + spatial on REG_REF
        base_ref_col = find_column(base_df, "REG_REF", "REGREF")
        spatial_ref_col = find_column(spatial_df, "REG_REF", "REGREF")

        if base_ref_col and spatial_ref_col:
            merged = base_df.merge(
                spatial_df[[spatial_ref_col, "lat", "lng", "itm_easting", "itm_northing"]].drop_duplicates(subset=[spatial_ref_col]),
                left_on=base_ref_col,
                right_on=spatial_ref_col,
                how="left",
            )
        else:
            merged = base_df
            logger.warning("Could not merge spatial data — REG_REF columns not found")

        # 4. Upsert applications
        stats = await upsert_applications(db, merged)

        # 5. Upsert appeals and further info
        appeal_count = await upsert_appeals(db, appeal_df)
        fi_count = await upsert_further_info(db, furinfo_df)

        stats["appeals"] = appeal_count
        stats["further_info"] = fi_count

        # Update sync log
        sync_log.status = "completed"
        sync_log.completed_at = datetime.utcnow()
        sync_log.records_processed = stats["processed"]
        sync_log.records_new = stats.get("new", 0)
        sync_log.records_updated = stats.get("updated", 0)
        await db.commit()

        logger.info(f"Ingest complete: {stats}")
        return stats

    except Exception as e:
        sync_log.status = "failed"
        sync_log.error_message = str(e)
        sync_log.completed_at = datetime.utcnow()
        await db.commit()
        logger.error(f"Ingest failed: {e}")
        raise
