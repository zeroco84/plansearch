"""PlanSearch — Northern Ireland CSV Ingest Worker.

Downloads planning application data from OpenDataNI CSV files.
NI data is published annually by the Department for Infrastructure.

Data covers 11 Local Planning Authorities + DfI (regional applications).
~200,000 records across financial years 2017/18 to 2024/25.

Coordinate system: Irish National Grid (EPSG:29903) → WGS84.
Data licence: Open Government Licence v3.0.
"""

import asyncio
import csv
import io
import logging
from datetime import datetime
from typing import Optional

import httpx
from pyproj import Transformer
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import SyncLog
from app.utils.text_clean import clean_text

logger = logging.getLogger(__name__)

# ── CSV source URLs (confirmed March 2026) ───────────────────────────────

NI_CSV_URLS = {
    "2024/25": "https://www.infrastructure-ni.gov.uk/system/files/2025-06/planning-statistics-2024-25-dataset.csv",
    "2023/24": "https://www.infrastructure-ni.gov.uk/system/files/publications/infrastructure/planning-statistics-2023-24-dataset.csv",
    "2022/23": "https://www.infrastructure-ni.gov.uk/system/files/publications/infrastructure/planning-statistics-2022-23-dataset.csv",
    "2021/22": "https://admin.opendatani.gov.uk/dataset/77d2f25e-cc5a-495a-9e6c-d2fe2e3b6869/resource/dc73a5c7-cb66-4e07-b4d0-399b8c73d191/download/planning-statistics-2021-22-dataset.csv",
    "2020/21": "https://www.infrastructure-ni.gov.uk/system/files/publications/infrastructure/planning-statistics-2020-21-dataset.csv",
    "2019/20": "https://www.infrastructure-ni.gov.uk/system/files/publications/infrastructure/planning-statistics-2019-20-dataset.csv",
    "2018/19": "https://www.infrastructure-ni.gov.uk/system/files/publications/infrastructure/planning-statistics-2018-19-dataset.csv",
    "2017/18": "https://www.infrastructure-ni.gov.uk/system/files/publications/infrastructure/planning-statistics-2017-18-dataset.csv",
}

USER_AGENT = "Mozilla/5.0 (compatible; PlanSearch/1.0; +https://plansearch.cc)"

# ── Coordinate transformer: Irish Grid → WGS84 ──────────────────────────

_ig_transformer = Transformer.from_crs("EPSG:29903", "EPSG:4326", always_xy=True)


def irish_grid_to_wgs84(easting: float, northing: float) -> tuple[float, float]:
    """Convert Irish National Grid (EPSG:29903) to WGS84 lat/lng.

    Returns (latitude, longitude).
    """
    lng, lat = _ig_transformer.transform(easting, northing)
    return lat, lng


def is_valid_ni_coords(lat: float, lng: float) -> bool:
    """Validate coordinates are within Northern Ireland bounds."""
    return 54.0 <= lat <= 55.4 and -8.2 <= lng <= -5.4


# ── Authority mapping ────────────────────────────────────────────────────

NI_AUTHORITY_MAP = {
    "Antrim and Newtownabbey LPA": "Antrim and Newtownabbey",
    "Ards and North Down LPA": "Ards and North Down",
    "Armagh City, Banbridge and Craigavon LPA": "Armagh City, Banbridge and Craigavon",
    "Belfast City LPA": "Belfast City Council",
    "Causeway Coast and Glens LPA": "Causeway Coast and Glens",
    "Derry City and Strabane LPA": "Derry City and Strabane",
    "Fermanagh and Omagh LPA": "Fermanagh and Omagh",
    "Lisburn and Castlereagh LPA": "Lisburn and Castlereagh",
    "Mid and East Antrim LPA": "Mid and East Antrim",
    "Mid Ulster LPA": "Mid Ulster",
    "Newry, Mourne and Down LPA": "Newry, Mourne and Down",
    "Derry and Strabane": "Derry City and Strabane",
    "Department for Infrastructure": "Department for Infrastructure (NI)",
}

NI_AUTHORITY_CODES = {
    "Antrim and Newtownabbey": "AAN",
    "Ards and North Down": "AND",
    "Armagh City, Banbridge and Craigavon": "ABC",
    "Belfast City Council": "BCC",
    "Causeway Coast and Glens": "CCG",
    "Derry City and Strabane": "DCS",
    "Fermanagh and Omagh": "FOM",
    "Lisburn and Castlereagh": "LCA",
    "Mid and East Antrim": "MEA",
    "Mid Ulster": "MUL",
    "Newry, Mourne and Down": "NMD",
    "Department for Infrastructure (NI)": "DFI",
}

# ── dev_category mapping from NI StatsCategory ──────────────────────────

STATS_CATEGORY_MAP = {
    "Residential": "residential_new_build",
    "Commercial": "commercial_retail",
    "Industrial": "industrial_warehouse",
    "Office": "commercial_office",
    "Renewable Energy": "renewable_energy",
    "Telecommunications": "telecommunications",
}

HOUSING_TYPE_OVERRIDES = {
    "Student Accommodation": "student_accommodation",
    "Apartments": "residential_new_build",
    "Rural housing": "residential_new_build",
}


# ── Decision normalisation ───────────────────────────────────────────────

NI_DECISION_MAP = {
    "approved": "GRANTED",
    "refused": "REFUSED",
    "withdrawn": "WITHDRAWN",
}


# ── Portal link construction ────────────────────────────────────────────

NI_PORTAL_BASE = "https://planningregister.planningsystemni.gov.uk/Planning/ACase?reference="


def build_portal_url(raw_ref: str, planning_authority: str) -> str:
    """Build the portal URL for an NI application."""
    if planning_authority == "Mid Ulster":
        return "https://www.midulstercouncil.org/planning"
    return f"{NI_PORTAL_BASE}{raw_ref}"


# ── Date parsing ─────────────────────────────────────────────────────────

def parse_ni_date(val: str) -> Optional[object]:
    """Parse NI date format: DD-Mon-YYYY (e.g. 20-Apr-1990)."""
    if not val or not val.strip():
        return None
    try:
        return datetime.strptime(val.strip(), "%d-%b-%Y").date()
    except ValueError:
        # Try alternate formats
        for fmt in ["%d/%m/%Y", "%Y-%m-%d"]:
            try:
                return datetime.strptime(val.strip(), fmt).date()
            except ValueError:
                continue
    return None


# ── Coordinate parsing ──────────────────────────────────────────────────

def parse_ni_coordinate(val: str) -> Optional[float]:
    """Parse NI coordinate value, stripping comma thousand separators."""
    if not val or not val.strip():
        return None
    try:
        return float(val.strip().replace(",", ""))
    except ValueError:
        return None


# ── dev_category mapping ────────────────────────────────────────────────

def map_ni_category(
    stats_category: Optional[str],
    housing_type: Optional[str],
    renewable_type: Optional[str],
) -> Optional[str]:
    """Map NI StatsCategory + HousingType to dev_category.

    NI records also pass through the AI classifier post-ingestion,
    so this is an initial best-effort mapping.
    """
    if housing_type and housing_type.strip() in HOUSING_TYPE_OVERRIDES:
        return HOUSING_TYPE_OVERRIDES[housing_type.strip()]

    if stats_category and stats_category.strip() in STATS_CATEGORY_MAP:
        return STATS_CATEGORY_MAP[stats_category.strip()]

    # Everything else: civic, agricultural, minerals, waste, other
    return "other" if stats_category else None


# ── CSV download and parsing ────────────────────────────────────────────

async def download_ni_csv(url: str) -> list[dict]:
    """Download and parse a single NI CSV file.

    Returns list of row dicts.
    """
    async with httpx.AsyncClient(timeout=120.0, follow_redirects=True) as client:
        response = await client.get(url, headers={"User-Agent": USER_AGENT})
        response.raise_for_status()

    # Handle encoding — NI CSVs are sometimes Windows-1252
    try:
        text_content = response.content.decode("utf-8-sig")
    except UnicodeDecodeError:
        text_content = response.content.decode("latin-1")

    reader = csv.DictReader(io.StringIO(text_content))
    return list(reader)


# ── Record upsert ────────────────────────────────────────────────────────

async def upsert_ni_record(db: AsyncSession, row: dict) -> bool:
    """Upsert a single NI record into the applications table."""
    raw_id = (row.get("ID") or "").strip()
    if not raw_id:
        return False

    # Prefix with NI/ for global uniqueness
    reg_ref = f"NI/{raw_id}"

    # Authority mapping
    raw_authority = (row.get("LPA19NM") or row.get("Authority") or "").strip()
    planning_authority = NI_AUTHORITY_MAP.get(raw_authority, raw_authority)
    if planning_authority.endswith(" LPA"):
        planning_authority = planning_authority[:-4].strip()

    # Coordinates: Irish Grid → WGS84
    lat, lng = None, None
    easting = parse_ni_coordinate(row.get("Easting", ""))
    northing = parse_ni_coordinate(row.get("Northing", ""))
    if easting and northing:
        try:
            lat, lng = irish_grid_to_wgs84(easting, northing)
            if not is_valid_ni_coords(lat, lng):
                lat, lng = None, None
        except Exception:
            lat, lng = None, None

    # Decision normalisation
    raw_decision = (row.get("Decision_Withdrawal") or "").strip().lower()
    decision = NI_DECISION_MAP.get(raw_decision)
    if not decision and raw_decision:
        decision = raw_decision.upper()  # Preserve unknown values

    # dev_category mapping
    dev_category = map_ni_category(
        row.get("StatsCategory"),
        row.get("HousingType"),
        row.get("RenewableType"),
    )

    # Parse date
    apn_date = parse_ni_date(row.get("DateReceived", ""))

    values = {
        "reg_ref": reg_ref,
        "planning_authority": planning_authority,
        "proposal": clean_text(row.get("Proposal")),
        "location": clean_text(row.get("SiteAddress")),
        "decision": decision,
        "apn_date": apn_date,
        "rgn_date": parse_ni_date(row.get("DateValid", "")),
        "dec_date": parse_ni_date(row.get("DecisionIssuedDate", "")),
        "app_type": (row.get("AppType") or "").strip() or None,
        "dev_category": dev_category,
        "link_app_details": build_portal_url(raw_id, planning_authority),
        "data_source": "NIDFT",
    }

    # Clean None/nan strings
    for k in list(values.keys()):
        if isinstance(values[k], str) and values[k] in ("nan", "None", "null", ""):
            values[k] = None

    try:
        await db.execute(text("SAVEPOINT ni_upsert"))

        cols = list(values.keys())
        placeholders = [f":{k}" for k in cols]
        update_parts = [f"{k} = EXCLUDED.{k}" for k in cols if k != "reg_ref"]

        if lat and lng:
            sql = text(f"""
                INSERT INTO applications ({', '.join(cols)}, location_point)
                VALUES ({', '.join(placeholders)}, ST_SetSRID(ST_MakePoint({lng}, {lat}), 4326))
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
        await db.execute(text("RELEASE SAVEPOINT ni_upsert"))
        return True

    except Exception as e:
        await db.execute(text("ROLLBACK TO SAVEPOINT ni_upsert"))
        logger.error(f"Error upserting NI/{raw_id}: {e}")
        return False


# ── Main ingest functions ────────────────────────────────────────────────

ni_ingest_progress = {
    "running": False,
    "current_year": None,
    "total_years": 0,
    "years_done": 0,
    "records_imported": 0,
    "errors": 0,
    "started_at": None,
    "error": None,
}


async def ingest_ni_year(db: AsyncSession, year_key: str, url: str) -> dict:
    """Download and ingest a single NI financial year CSV."""
    logger.info(f"Downloading NI CSV for {year_key}...")
    ni_ingest_progress["current_year"] = year_key

    stats = {"year": year_key, "processed": 0, "errors": 0}

    try:
        rows = await download_ni_csv(url)
        logger.info(f"  NI {year_key}: {len(rows)} rows downloaded")

        for i, row in enumerate(rows):
            ok = await upsert_ni_record(db, row)
            if ok:
                stats["processed"] += 1
            else:
                stats["errors"] += 1

            # Commit in batches of 500
            if (i + 1) % 500 == 0:
                await db.commit()
                logger.info(f"  NI {year_key}: {i + 1}/{len(rows)} records")

        await db.commit()
        logger.info(
            f"  NI {year_key} complete: {stats['processed']} imported, "
            f"{stats['errors']} errors"
        )

    except Exception as e:
        logger.error(f"Failed to ingest NI {year_key}: {e}")
        stats["errors"] += 1

    return stats


async def run_ni_ingest_all(db: AsyncSession) -> dict:
    """Ingest all NI financial years (2017/18 → 2024/25).

    Called via admin API. Downloads all 8 CSVs sequentially.
    """
    ni_ingest_progress["running"] = True
    ni_ingest_progress["started_at"] = datetime.utcnow().isoformat()
    ni_ingest_progress["total_years"] = len(NI_CSV_URLS)
    ni_ingest_progress["years_done"] = 0
    ni_ingest_progress["records_imported"] = 0
    ni_ingest_progress["errors"] = 0
    ni_ingest_progress["error"] = None

    sync_log = SyncLog(sync_type="ni_ingest_all", status="running")
    db.add(sync_log)
    await db.flush()

    all_stats = {"total_processed": 0, "total_errors": 0, "years": {}}

    try:
        for year_key, url in NI_CSV_URLS.items():
            year_stats = await ingest_ni_year(db, year_key, url)
            all_stats["years"][year_key] = year_stats
            all_stats["total_processed"] += year_stats["processed"]
            all_stats["total_errors"] += year_stats["errors"]
            ni_ingest_progress["years_done"] += 1
            ni_ingest_progress["records_imported"] += year_stats["processed"]
            ni_ingest_progress["errors"] += year_stats["errors"]

        sync_log.status = "completed"
        sync_log.records_processed = all_stats["total_processed"]
        sync_log.ended_at = datetime.utcnow()
        await db.commit()

    except Exception as e:
        logger.error(f"NI ingest all failed: {e}")
        sync_log.status = "failed"
        sync_log.error_message = str(e)[:1000]
        sync_log.ended_at = datetime.utcnow()
        ni_ingest_progress["error"] = str(e)
        await db.commit()

    finally:
        ni_ingest_progress["running"] = False
        ni_ingest_progress["current_year"] = None

    logger.info(
        f"NI all-years ingest complete: {all_stats['total_processed']} records, "
        f"{all_stats['total_errors']} errors"
    )
    return all_stats


async def run_ni_ingest_latest(db: AsyncSession) -> dict:
    """Ingest only the latest NI financial year (2024/25)."""
    latest_key = list(NI_CSV_URLS.keys())[0]
    latest_url = NI_CSV_URLS[latest_key]

    ni_ingest_progress["running"] = True
    ni_ingest_progress["started_at"] = datetime.utcnow().isoformat()
    ni_ingest_progress["total_years"] = 1
    ni_ingest_progress["years_done"] = 0
    ni_ingest_progress["records_imported"] = 0
    ni_ingest_progress["errors"] = 0
    ni_ingest_progress["error"] = None

    sync_log = SyncLog(sync_type="ni_ingest_latest", status="running")
    db.add(sync_log)
    await db.flush()

    try:
        stats = await ingest_ni_year(db, latest_key, latest_url)
        ni_ingest_progress["years_done"] = 1
        ni_ingest_progress["records_imported"] = stats["processed"]
        ni_ingest_progress["errors"] = stats["errors"]

        sync_log.status = "completed"
        sync_log.records_processed = stats["processed"]
        sync_log.ended_at = datetime.utcnow()
        await db.commit()

    except Exception as e:
        logger.error(f"NI latest ingest failed: {e}")
        sync_log.status = "failed"
        sync_log.error_message = str(e)[:1000]
        sync_log.ended_at = datetime.utcnow()
        ni_ingest_progress["error"] = str(e)
        await db.commit()

    finally:
        ni_ingest_progress["running"] = False
        ni_ingest_progress["current_year"] = None

    return stats
