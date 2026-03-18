"""PlanSearch — Admin API endpoints.

All endpoints protected by bearer token authentication.
"""

import asyncio
import json
from typing import Optional
from datetime import datetime

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Header, Query
from sqlalchemy import select, func, update, text
from sqlalchemy.ext.asyncio import AsyncSession
from sse_starlette.sse import EventSourceResponse

from app.database import get_db, async_session_factory
from app.config import get_settings
from app.models import (
    AdminConfig, Application, SyncLog, ScrapeJob,
    ApplicationDocument, DocumentScrapeStatus,
)
from app.schemas import (
    AdminConfigItem, AdminConfigUpdate, SyncLogEntry,
    SyncTriggerResponse, ClassifyStatusResponse, ScrapeStatusResponse,
)
from app.utils.crypto import encrypt_value, decrypt_value, mask_value

router = APIRouter()
settings = get_settings()

# In-memory SSE event queue for live progress
_sse_events: list[dict] = []

# In-memory sync progress — updated by background tasks, read by polling endpoint
sync_progress = {
    "running": False,
    "processed": 0,
    "errors": 0,
    "started_at": None,
    "source": None,
    "stop_requested": False,
}


def verify_admin_token(authorization: str = Header(...)):
    """Verify the admin bearer token."""
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Invalid authorization header")
    token = authorization.replace("Bearer ", "")
    if token != settings.admin_token:
        raise HTTPException(status_code=403, detail="Invalid admin token")
    return token


# ── Config Management ────────────────────────────────────────────────────

@router.get("/admin/config", response_model=list[AdminConfigItem])
async def list_config(
    _token: str = Depends(verify_admin_token),
    db: AsyncSession = Depends(get_db),
):
    """List all config keys with masked values."""
    result = await db.execute(select(AdminConfig))
    configs = result.scalars().all()

    return [
        AdminConfigItem(
            key=c.key,
            value_masked=mask_value(decrypt_value(c.value) if c.encrypted else c.value),
            encrypted=c.encrypted,
            description=c.description,
            updated_at=c.updated_at,
        )
        for c in configs
    ]


@router.post("/admin/config")
async def update_config(
    update_data: AdminConfigUpdate,
    _token: str = Depends(verify_admin_token),
    db: AsyncSession = Depends(get_db),
):
    """Update or create a config key/value pair."""
    value = encrypt_value(update_data.value) if update_data.encrypted else update_data.value

    # Upsert
    existing = await db.execute(
        select(AdminConfig).where(AdminConfig.key == update_data.key)
    )
    config = existing.scalar_one_or_none()

    if config:
        config.value = value
        config.encrypted = update_data.encrypted
        config.description = update_data.description or config.description
        config.updated_at = datetime.utcnow()
    else:
        config = AdminConfig(
            key=update_data.key,
            value=value,
            encrypted=update_data.encrypted,
            description=update_data.description,
        )
        db.add(config)

    await db.flush()
    return {"message": f"Config key '{update_data.key}' updated"}


@router.post("/admin/keys/claude")
async def update_claude_key(
    key_data: dict,
    _token: str = Depends(verify_admin_token),
    db: AsyncSession = Depends(get_db),
):
    """Update the Claude API key (stored encrypted)."""
    api_key = key_data.get("api_key", "")
    if not api_key:
        raise HTTPException(status_code=400, detail="api_key is required")

    encrypted = encrypt_value(api_key)

    existing = await db.execute(
        select(AdminConfig).where(AdminConfig.key == "claude_api_key")
    )
    config = existing.scalar_one_or_none()

    if config:
        config.value = encrypted
        config.encrypted = True
        config.updated_at = datetime.utcnow()
    else:
        config = AdminConfig(
            key="claude_api_key",
            value=encrypted,
            encrypted=True,
            description="Anthropic Claude API key for AI classification",
        )
        db.add(config)

    await db.flush()
    return {"message": "Claude API key updated"}


@router.post("/admin/keys/cro")
async def update_cro_key(
    key_data: dict,
    _token: str = Depends(verify_admin_token),
    db: AsyncSession = Depends(get_db),
):
    """Update the CRO API key (stored encrypted)."""
    api_key = key_data.get("api_key", "")
    if not api_key:
        raise HTTPException(status_code=400, detail="api_key is required")

    encrypted = encrypt_value(api_key)

    existing = await db.execute(
        select(AdminConfig).where(AdminConfig.key == "cro_api_key")
    )
    config = existing.scalar_one_or_none()

    if config:
        config.value = encrypted
        config.encrypted = True
        config.updated_at = datetime.utcnow()
    else:
        config = AdminConfig(
            key="cro_api_key",
            value=encrypted,
            encrypted=True,
            description="Companies Registration Office API key",
        )
        db.add(config)

    await db.flush()
    return {"message": "CRO API key updated"}


# ── Sync Controls ────────────────────────────────────────────────────────

@router.get("/admin/sync/progress")
async def get_sync_progress(
    _token: str = Depends(verify_admin_token),
):
    """Get live sync progress — polled by the frontend every 3 seconds."""
    return sync_progress


@router.post("/admin/sync/stop")
async def stop_sync(
    _token: str = Depends(verify_admin_token),
):
    """Request a running sync to stop gracefully."""
    if not sync_progress["running"]:
        return {"status": "not_running"}
    sync_progress["stop_requested"] = True
    return {"status": "stop_requested", "source": sync_progress["source"]}


@router.post("/admin/sync/trigger", response_model=SyncTriggerResponse)
async def trigger_sync(
    _token: str = Depends(verify_admin_token),
    db: AsyncSession = Depends(get_db),
):
    """Trigger NPAD data sync (default sync source)."""
    sync_progress.update({
        "running": True, "processed": 0, "errors": 0,
        "started_at": datetime.utcnow().isoformat(), "source": "npad",
    })
    sync_log = SyncLog(sync_type="npad_ingest", status="running")
    db.add(sync_log)
    await db.flush()

    asyncio.create_task(_run_npad_background(sync_log.id))

    return SyncTriggerResponse(message="NPAD sync triggered", sync_id=sync_log.id)


@router.post("/admin/sync/npad")
async def trigger_npad_sync(
    _token: str = Depends(verify_admin_token),
    db: AsyncSession = Depends(get_db),
):
    """Trigger NPAD ArcGIS ingest — all 31 local authorities."""
    sync_progress.update({
        "running": True, "processed": 0, "errors": 0,
        "started_at": datetime.utcnow().isoformat(), "source": "npad",
    })
    sync_log = SyncLog(sync_type="npad_ingest", status="running")
    db.add(sync_log)
    await db.flush()

    asyncio.create_task(_run_npad_background(sync_log.id))

    return {"message": "NPAD sync triggered", "sync_id": sync_log.id}


@router.post("/admin/sync/bcms")
async def trigger_bcms_sync(
    _token: str = Depends(verify_admin_token),
    db: AsyncSession = Depends(get_db),
):
    """Trigger BCMS ingest — commencement notices + FSC applications."""
    sync_progress.update({
        "running": True, "processed": 0, "errors": 0,
        "started_at": datetime.utcnow().isoformat(), "source": "bcms",
    })
    sync_log = SyncLog(sync_type="bcms_ingest", status="running")
    db.add(sync_log)
    await db.flush()

    asyncio.create_task(_run_bcms_background(sync_log.id))

    return {"message": "BCMS sync triggered", "sync_id": sync_log.id}


async def _run_npad_background(sync_id: int):
    """Run NPAD ingest in background, updating sync_progress in real-time."""
    from app.workers.npad_ingest import run_npad_ingest_with_progress

    async with async_session_factory() as db:
        try:
            stats = await run_npad_ingest_with_progress(db, sync_progress)
            await db.execute(
                update(SyncLog)
                .where(SyncLog.id == sync_id)
                .values(
                    status="completed",
                    completed_at=datetime.utcnow(),
                    records_processed=sync_progress["processed"],
                )
            )
            await db.commit()
            _sse_events.append({"event": "sync_complete", "data": json.dumps(stats)})
        except Exception as e:
            sync_progress["running"] = False
            await db.execute(
                update(SyncLog)
                .where(SyncLog.id == sync_id)
                .values(
                    status="failed",
                    completed_at=datetime.utcnow(),
                    error_message=str(e),
                )
            )
            await db.commit()
            _sse_events.append({"event": "sync_error", "data": json.dumps({"error": str(e)})})


async def _run_bcms_background(sync_id: int):
    """Run BCMS ingest in background, updating sync_progress in real-time."""
    from app.workers.bcms_ingest import run_bcms_ingest_with_progress

    async with async_session_factory() as db:
        try:
            stats = await run_bcms_ingest_with_progress(db, sync_progress)
            await db.execute(
                update(SyncLog)
                .where(SyncLog.id == sync_id)
                .values(
                    status="completed",
                    completed_at=datetime.utcnow(),
                    records_processed=sync_progress["processed"],
                )
            )
            await db.commit()
            _sse_events.append({"event": "sync_complete", "data": json.dumps(stats)})
        except Exception as e:
            sync_progress["running"] = False
            await db.execute(
                update(SyncLog)
                .where(SyncLog.id == sync_id)
                .values(
                    status="failed",
                    completed_at=datetime.utcnow(),
                    error_message=str(e),
                )
            )
            await db.commit()
            _sse_events.append({"event": "sync_error", "data": json.dumps({"error": str(e)})})


@router.get("/admin/sync/status", response_model=SyncLogEntry)
async def sync_status(
    _token: str = Depends(verify_admin_token),
    db: AsyncSession = Depends(get_db),
):
    """Get the most recent sync log entry."""
    result = await db.execute(
        select(SyncLog).order_by(SyncLog.started_at.desc()).limit(1)
    )
    entry = result.scalar_one_or_none()
    if not entry:
        raise HTTPException(status_code=404, detail="No sync runs found")
    return entry


# ── Classify Controls ────────────────────────────────────────────────────

# In-memory classify progress — updated by background task, read by polling
classify_progress = {
    "running": False,
    "processed": 0,
    "errors": 0,
    "total": 0,
    "started_at": None,
    "stop_requested": False,
}


@router.get("/admin/classify/progress")
async def get_classify_progress(
    _token: str = Depends(verify_admin_token),
):
    """Get live classification progress — polled by the frontend every 3 seconds."""
    return classify_progress


@router.post("/admin/classify/stop")
async def stop_classify(
    _token: str = Depends(verify_admin_token),
):
    """Request a running classification to stop gracefully."""
    if not classify_progress["running"]:
        return {"status": "not_running"}
    classify_progress["stop_requested"] = True
    return {"status": "stop_requested"}


@router.post("/admin/classify/trigger")
async def trigger_classification(
    _token: str = Depends(verify_admin_token),
):
    """Trigger concurrent AI classification of all unclassified records."""
    classify_progress.update({
        "running": True,
        "processed": 0,
        "errors": 0,
        "total": 0,
        "started_at": datetime.utcnow().isoformat(),
        "stop_requested": False,
    })

    asyncio.create_task(_run_classify_background())

    return {
        "status": "triggered",
        "mode": "concurrent",
        "concurrency": 50,
    }


async def _run_classify_background():
    """Run concurrent classifier in background."""
    from app.workers.classifier import classify_all

    async with async_session_factory() as db:
        try:
            result = await classify_all(db, progress=classify_progress)
            _sse_events.append(
                {"event": "classify_complete", "data": json.dumps(result)}
            )
        except Exception as e:
            classify_progress["running"] = False
            _sse_events.append(
                {"event": "classify_error", "data": json.dumps({"error": str(e)})}
            )


@router.get("/admin/classify/status", response_model=ClassifyStatusResponse)
async def classify_status(
    _token: str = Depends(verify_admin_token),
    db: AsyncSession = Depends(get_db),
):
    """Get classification queue status."""
    total = (await db.execute(select(func.count(Application.id)))).scalar() or 0
    classified = (await db.execute(
        select(func.count(Application.id)).where(Application.dev_category.isnot(None))
    )).scalar() or 0
    unclassified = total - classified

    # Category breakdown
    cat_result = await db.execute(
        select(Application.dev_category, func.count(Application.id))
        .where(Application.dev_category.isnot(None))
        .group_by(Application.dev_category)
    )
    categories = {row[0]: row[1] for row in cat_result.all()}

    return ClassifyStatusResponse(
        total_unclassified=unclassified,
        total_classified=classified,
        total_applications=total,
        percentage_classified=round((classified / total * 100) if total > 0 else 0, 1),
        categories=categories,
    )


# ── Scraper Controls ────────────────────────────────────────────────────

@router.post("/admin/scrape/trigger")
async def trigger_scraping(
    _token: str = Depends(verify_admin_token),
    db: AsyncSession = Depends(get_db),
):
    """Trigger applicant name scraping."""
    from app.workers.scraper import run_scraper_batch

    asyncio.create_task(_run_scraper_background())

    return {"message": "Applicant scraping triggered"}


async def _run_scraper_background():
    """Run scraper in background."""
    from app.workers.scraper import run_scraper_batch

    async with async_session_factory() as db:
        try:
            result = await run_scraper_batch(db)
            _sse_events.append({"event": "scrape_complete", "data": json.dumps(result)})
        except Exception as e:
            _sse_events.append({"event": "scrape_error", "data": json.dumps({"error": str(e)})})


@router.get("/admin/scrape/status", response_model=ScrapeStatusResponse)
async def scrape_status(
    _token: str = Depends(verify_admin_token),
    db: AsyncSession = Depends(get_db),
):
    """Get scraper queue status."""
    total = (await db.execute(select(func.count(Application.id)))).scalar() or 0
    scraped = (await db.execute(
        select(func.count(Application.id)).where(Application.applicant_name.isnot(None))
    )).scalar() or 0
    failed = (await db.execute(
        select(func.count(Application.id)).where(Application.applicant_scrape_failed == True)
    )).scalar() or 0
    unscraped = total - scraped - failed

    return ScrapeStatusResponse(
        total_unscraped=unscraped,
        total_scraped=scraped,
        total_failed=failed,
        total_applications=total,
        percentage_scraped=round((scraped / total * 100) if total > 0 else 0, 1),
    )


# ── Logs ────────────────────────────────────────────────────────────────

@router.get("/admin/logs")
async def get_logs(
    limit: int = Query(50, le=200),
    _token: str = Depends(verify_admin_token),
    db: AsyncSession = Depends(get_db),
):
    """Get recent sync log entries."""
    result = await db.execute(
        select(SyncLog).order_by(SyncLog.started_at.desc()).limit(limit)
    )
    entries = result.scalars().all()
    return [
        SyncLogEntry.model_validate(e)
        for e in entries
    ]


# ── Benchmarks (Mitchell McDermott) ──────────────────────────────────────

@router.post("/admin/benchmarks/scrape")
async def trigger_benchmark_scrape(
    _token: str = Depends(verify_admin_token),
    db: AsyncSession = Depends(get_db),
):
    """Trigger Mitchell McDermott InfoCard benchmark extraction.

    Source: https://mitchellmcdermott.com/infocards/
    """
    asyncio.create_task(_run_benchmark_scrape_background())
    return {
        "status": "triggered",
        "source": "Mitchell McDermott",
        "source_url": "https://mitchellmcdermott.com/infocards/",
    }


async def _run_benchmark_scrape_background():
    """Run benchmark scrape in background."""
    from app.workers.benchmark_scraper import run_benchmark_scrape

    async with async_session_factory() as db:
        try:
            stats = await run_benchmark_scrape(db)
            _sse_events.append({
                "event": "benchmark_complete",
                "data": json.dumps(stats),
            })
        except Exception as e:
            _sse_events.append({
                "event": "benchmark_error",
                "data": json.dumps({"error": str(e)}),
            })


@router.get("/admin/benchmarks")
async def get_benchmarks(
    _token: str = Depends(verify_admin_token),
    db: AsyncSession = Depends(get_db),
):
    """Get all stored Mitchell McDermott benchmarks.

    Source: https://mitchellmcdermott.com/infocards/
    """
    result = await db.execute(text("""
        SELECT id, building_type, cost_per_sqm_low, cost_per_sqm_high,
               cost_per_unit_low, cost_per_unit_high, cost_basis,
               infocard_name, valid_from, inflation_rate,
               exclusions, inclusions, notes, extracted_at
        FROM cost_benchmarks
        ORDER BY valid_from DESC, building_type
    """))
    rows = result.fetchall()
    return {
        "source": "Mitchell McDermott",
        "source_url": "https://mitchellmcdermott.com/infocards/",
        "benchmarks": [dict(r._mapping) for r in rows],
    }


# ── Data Reset ──────────────────────────────────────────────────────────

@router.post("/admin/sync/reset-applications")
async def reset_applications(
    _token: str = Depends(verify_admin_token),
    db: AsyncSession = Depends(get_db),
):
    """Truncate applications table and reset for fresh sync.

    Required after schema changes like the reg_ref council prefix migration
    to avoid stale data with wrong keys.
    """
    await db.execute(text("TRUNCATE TABLE applications RESTART IDENTITY CASCADE"))
    await db.commit()
    return {"status": "reset", "message": "Applications table cleared. Run NPAD sync to reload."}


# ── CRO Enrichment ──────────────────────────────────────────────────────

@router.post("/admin/enrich/cro")
async def trigger_cro_enrichment(
    background_tasks: BackgroundTasks,
    _token: str = Depends(verify_admin_token),
    db: AsyncSession = Depends(get_db),
):
    """Trigger CRO company enrichment for applications with company-like names."""
    from app.workers.cro import run_cro_enrichment_batch
    background_tasks.add_task(run_cro_enrichment_batch, db)
    return {"status": "triggered", "source": "cro"}


# ── SSE Stream ──────────────────────────────────────────────────────────

@router.get("/admin/stream")
async def sse_stream(
    _token: str = Depends(verify_admin_token),
):
    """Server-Sent Events stream for live progress updates."""

    async def event_generator():
        last_index = len(_sse_events)
        while True:
            if len(_sse_events) > last_index:
                for event in _sse_events[last_index:]:
                    yield event
                last_index = len(_sse_events)
            await asyncio.sleep(1)

    return EventSourceResponse(event_generator())
