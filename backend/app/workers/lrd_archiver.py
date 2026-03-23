"""PlanSearch — LRD (Local Register of Documents) Archiver.

Downloads and archives planning application documents from council portals
so they remain accessible even after portal links expire. Downloads are
stored on disk and served via the archived_docs API endpoint.
"""

import asyncio
import logging
import os
import hashlib
from datetime import datetime
from pathlib import Path
from typing import Optional

import aiohttp
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.database import async_session_factory

logger = logging.getLogger(__name__)
settings = get_settings()

ARCHIVE_DIR = os.environ.get("ARCHIVE_DIR", "/data/archived_docs")
ARCHIVE_URL_PREFIX = os.environ.get("ARCHIVE_URL_PREFIX", "/api/docs/archived")

# In-memory progress — updated by background task, read by polling
lrd_archiver_progress = {
    "running": False,
    "applications_processed": 0,
    "files_downloaded": 0,
    "bytes_downloaded": 0,
    "last_reg_ref": None,
    "started_at": None,
    "error": None,
}

# LRD archiver stats (aggregate, queried on demand)
# Not stored in memory — fetched from DB via get_lrd_stats()


async def get_lrd_stats(db: AsyncSession) -> dict:
    """Get aggregate LRD archiver statistics from the database."""
    result = await db.execute(text("""
        SELECT
            COUNT(DISTINCT reg_ref) FILTER (WHERE archived = true) as total_applications_archived,
            COUNT(*) FILTER (WHERE archived = true) as total_files,
            COALESCE(SUM(file_size_bytes) FILTER (WHERE archived = true), 0) as total_storage_bytes
        FROM application_documents
    """))
    row = result.fetchone()
    return {
        "total_applications_archived": row.total_applications_archived or 0,
        "total_files": row.total_files or 0,
        "total_storage_bytes": row.total_storage_bytes or 0,
    }


def _safe_filename(reg_ref: str, doc_name: str, doc_id: int) -> str:
    """Generate a safe filesystem path for an archived document."""
    # Sanitise reg_ref for directory name
    safe_ref = reg_ref.replace("/", "_").replace("\\", "_").replace(" ", "_")
    # Hash the doc name + id for uniqueness
    name_hash = hashlib.md5(f"{doc_id}:{doc_name}".encode()).hexdigest()[:8]
    # Keep original extension if present
    ext = Path(doc_name).suffix.lower() if "." in doc_name else ".pdf"
    return f"{safe_ref}/{name_hash}{ext}"


async def _download_file(
    session: aiohttp.ClientSession,
    url: str,
    dest_path: Path,
) -> int:
    """Download a file and return the number of bytes written."""
    dest_path.parent.mkdir(parents=True, exist_ok=True)

    async with session.get(url, timeout=aiohttp.ClientTimeout(total=120)) as resp:
        if resp.status != 200:
            raise Exception(f"HTTP {resp.status} downloading {url}")

        total = 0
        with open(dest_path, "wb") as f:
            async for chunk in resp.content.iter_chunked(65536):
                f.write(chunk)
                total += len(chunk)

        return total


async def _archive_single_doc(
    http_session: aiohttp.ClientSession,
    db: AsyncSession,
    doc_id: int,
    reg_ref: str,
    doc_name: str,
    direct_url: str,
) -> int:
    """Archive one document. Returns bytes downloaded or 0 on skip/failure."""
    relative_path = _safe_filename(reg_ref, doc_name, doc_id)
    dest = Path(ARCHIVE_DIR) / relative_path

    # Skip if already on disk
    if dest.exists():
        # Mark as archived in DB if not already
        await db.execute(text("""
            UPDATE application_documents
            SET archived = true,
                archived_path = :path,
                archived_at = NOW()
            WHERE id = :id AND archived IS NOT true
        """), {"path": relative_path, "id": doc_id})
        return 0

    try:
        n_bytes = await _download_file(http_session, direct_url, dest)

        # Update DB
        await db.execute(text("""
            UPDATE application_documents
            SET archived = true,
                archived_path = :path,
                archived_at = NOW(),
                file_size_bytes = COALESCE(file_size_bytes, :size)
            WHERE id = :id
        """), {"path": relative_path, "id": doc_id, "size": n_bytes})

        return n_bytes
    except Exception as e:
        logger.warning(f"Failed to archive doc {doc_id} ({reg_ref}): {e}")
        return 0


async def run_lrd_archiver_loop():
    """Main archiver loop — finds unarchived documents with direct_urls and downloads them.

    Prioritises documents from applications filed 2023+ that already have
    direct_url populated by the doc scraper. Rate limited to avoid
    overwhelming council portals.
    """
    lrd_archiver_progress["running"] = True
    lrd_archiver_progress["started_at"] = datetime.utcnow().isoformat()
    lrd_archiver_progress["applications_processed"] = 0
    lrd_archiver_progress["files_downloaded"] = 0
    lrd_archiver_progress["bytes_downloaded"] = 0
    lrd_archiver_progress["error"] = None

    # Ensure archive directory exists
    Path(ARCHIVE_DIR).mkdir(parents=True, exist_ok=True)

    try:
        async with aiohttp.ClientSession(
            headers={"User-Agent": "PlanSearch-Archiver/1.0"}
        ) as http_session:
            async with async_session_factory() as db:
                while lrd_archiver_progress["running"]:
                    # Find the next batch of unarchived docs with direct URLs
                    result = await db.execute(text("""
                        SELECT d.id, d.reg_ref, d.doc_name, d.direct_url
                        FROM application_documents d
                        JOIN applications a ON a.reg_ref = d.reg_ref
                        WHERE d.direct_url IS NOT NULL
                          AND (d.archived IS NULL OR d.archived = false)
                          AND d.direct_url != ''
                        ORDER BY a.apn_date DESC NULLS LAST
                        LIMIT 50
                    """))
                    rows = result.fetchall()

                    if not rows:
                        logger.info("LRD archiver: no more documents to archive, sleeping 5 min")
                        await asyncio.sleep(300)
                        continue

                    current_ref = None
                    for row in rows:
                        if not lrd_archiver_progress["running"]:
                            break

                        if row.reg_ref != current_ref:
                            current_ref = row.reg_ref
                            lrd_archiver_progress["applications_processed"] += 1
                            lrd_archiver_progress["last_reg_ref"] = row.reg_ref

                        n_bytes = await _archive_single_doc(
                            http_session, db, row.id, row.reg_ref,
                            row.doc_name, row.direct_url,
                        )

                        if n_bytes > 0:
                            lrd_archiver_progress["files_downloaded"] += 1
                            lrd_archiver_progress["bytes_downloaded"] += n_bytes

                        # Rate limit — 2 second pause between downloads
                        await asyncio.sleep(2)

                    await db.commit()

    except Exception as e:
        logger.error(f"LRD archiver loop error: {e}")
        lrd_archiver_progress["error"] = str(e)
    finally:
        lrd_archiver_progress["running"] = False
