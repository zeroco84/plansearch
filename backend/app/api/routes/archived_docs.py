"""PlanSearch — Archived Documents API routes.

Serves locally-archived planning documents and provides admin controls
for the LRD archiver worker.
"""

import asyncio
import os
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Header
from fastapi.responses import FileResponse
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.database import get_db

settings = get_settings()
router = APIRouter()

ARCHIVE_DIR = os.environ.get("ARCHIVE_DIR", "/data/archived_docs")
ARCHIVE_URL_PREFIX = os.environ.get("ARCHIVE_URL_PREFIX", "/api/docs/archived")

# ── Auth ────────────────────────────────────────────────────────────────

def verify_admin(authorization: str = Header(...)):
    """Verify admin bearer token."""
    token = authorization.replace("Bearer ", "")
    if token != settings.admin_token:
        raise HTTPException(status_code=403, detail="Invalid admin token")
    return token


# ── File Serving ────────────────────────────────────────────────────────

@router.get("/docs/archived/{file_path:path}")
async def serve_archived_doc(file_path: str):
    """Serve an archived document from the local filesystem.

    Files are stored under ARCHIVE_DIR with structure:
    <reg_ref_safe>/<hash>.<ext>
    """
    full_path = Path(ARCHIVE_DIR) / file_path

    # Security: prevent path traversal
    try:
        full_path = full_path.resolve()
        archive_root = Path(ARCHIVE_DIR).resolve()
        if not str(full_path).startswith(str(archive_root)):
            raise HTTPException(status_code=403, detail="Access denied")
    except (ValueError, OSError):
        raise HTTPException(status_code=400, detail="Invalid path")

    if not full_path.exists() or not full_path.is_file():
        raise HTTPException(status_code=404, detail="Document not found")

    # Guess media type from extension
    ext = full_path.suffix.lower()
    media_types = {
        ".pdf": "application/pdf",
        ".doc": "application/msword",
        ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".png": "image/png",
        ".tif": "image/tiff",
        ".tiff": "image/tiff",
        ".dwg": "application/acad",
        ".dxf": "application/dxf",
    }
    media_type = media_types.get(ext, "application/octet-stream")

    return FileResponse(
        path=str(full_path),
        media_type=media_type,
        filename=full_path.name,
    )


# ── Admin: LRD Archiver Controls ───────────────────────────────────────

_lrd_task = None


@router.post("/admin/scrape/lrd/start")
async def start_lrd_archiver(
    _token: str = Depends(verify_admin),
):
    """Start the LRD document archiver loop."""
    global _lrd_task
    from app.workers.lrd_archiver import lrd_archiver_progress, run_lrd_archiver_loop

    if lrd_archiver_progress["running"]:
        return {"status": "already_running", "progress": lrd_archiver_progress}

    _lrd_task = asyncio.create_task(run_lrd_archiver_loop())
    return {"status": "started"}


@router.post("/admin/scrape/lrd/stop")
async def stop_lrd_archiver(
    _token: str = Depends(verify_admin),
):
    """Stop the LRD document archiver loop."""
    global _lrd_task
    from app.workers.lrd_archiver import lrd_archiver_progress

    lrd_archiver_progress["running"] = False
    if _lrd_task:
        _lrd_task.cancel()
        _lrd_task = None
    return {"status": "stopped"}


@router.get("/admin/scrape/lrd/progress")
async def get_lrd_progress(
    _token: str = Depends(verify_admin),
):
    """Get live LRD archiver progress."""
    from app.workers.lrd_archiver import lrd_archiver_progress

    return lrd_archiver_progress


@router.get("/admin/scrape/lrd/stats")
async def get_lrd_stats_endpoint(
    _token: str = Depends(verify_admin),
    db: AsyncSession = Depends(get_db),
):
    """Get aggregate LRD archiver stats from the database."""
    from app.workers.lrd_archiver import get_lrd_stats

    return await get_lrd_stats(db)
