import asyncio
import logging
from datetime import datetime
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.database import engine, Base
from app.api.routes import search, applications, map, stats, admin, export, docs, digest
from app.api.routes import insights, advertising
from app import models  # noqa: F401 — ensure all models are registered
from app.models import CostBenchmark, CommencementNotice, FSCApplication  # noqa: F401
# Phase 5 — Public API
from app.api.routes.v1 import applications as v1_applications
from app.api.routes.v1 import stats as v1_stats
from app.api.routes.v1 import keys as v1_keys
from app.api.routes.v1 import webhooks as v1_webhooks
from app.api.routes.v1 import export as v1_export
from app.api.routes.v1 import developer as v1_developer
from app.models import ApiKey, ApiUsage, Webhook, WebhookDelivery  # noqa: F401
# Phase 4 — optional, depends on python-jose, passlib, stripe, boto3
try:
    from app.api.routes import auth, billing, alerts
    from app.models import User, AlertProfile, AlertDelivery, AlertMatch  # noqa: F401
    PHASE4_AVAILABLE = True
except ImportError as e:
    PHASE4_AVAILABLE = False
    logging.getLogger(__name__).warning(f"Phase 4 (alerts) not available: {e}")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)
settings = get_settings()


async def substack_refresh_loop():
    """Refresh Substack posts every 6 hours."""
    while True:
        await asyncio.sleep(6 * 60 * 60)
        try:
            from app.workers.substack_ingest import ingest_substack_posts

            async with AsyncSession(engine) as db:
                await ingest_substack_posts(db)
            logger.info("Substack posts refreshed")
        except Exception as e:
            logger.error(f"Substack refresh failed: {e}")


async def alert_engine_loop():
    """Run alert engine on schedule."""
    from app.workers.alert_engine import run_alert_engine

    logger.info("Alert engine scheduler started")
    while True:
        now = datetime.utcnow()
        try:
            # Instant alerts: every 30 minutes
            if now.minute in (0, 30):
                asyncio.create_task(run_alert_engine("instant"))
            # Daily alerts: 8am UTC
            if now.hour == 8 and now.minute == 0:
                asyncio.create_task(run_alert_engine("daily"))
            # Weekly alerts: Monday 8am UTC
            if now.weekday() == 0 and now.hour == 8 and now.minute == 0:
                asyncio.create_task(run_alert_engine("weekly"))
        except Exception as e:
            logger.error(f"Alert engine scheduler error: {e}")
        await asyncio.sleep(60)  # Check every minute


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler — creates missing tables on startup."""
    async with engine.begin() as conn:
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS postgis"))
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS pg_trgm"))
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS unaccent"))

        await conn.run_sync(Base.metadata.create_all)

        # Create/update search_vector trigger so it stays in sync automatically
        # Each statement is a separate execute call — required by asyncpg
        await conn.execute(text("""
            CREATE OR REPLACE FUNCTION update_search_vector()
            RETURNS trigger AS $$
            BEGIN
                NEW.search_vector := to_tsvector('english',
                    COALESCE(NEW.proposal, '') || ' ' ||
                    COALESCE(NEW.location, '') || ' ' ||
                    COALESCE(NEW.applicant_name, '') || ' ' ||
                    COALESCE(NEW.planning_authority, '')
                );
                RETURN NEW;
            END;
            $$ LANGUAGE plpgsql
        """))

        await conn.execute(text(
            "DROP TRIGGER IF EXISTS applications_search_vector_trigger ON applications"
        ))

        await conn.execute(text("""
            CREATE TRIGGER applications_search_vector_trigger
                BEFORE INSERT OR UPDATE ON applications
                FOR EACH ROW EXECUTE FUNCTION update_search_vector()
        """))

    # Initial Substack sync on startup
    try:
        from app.workers.substack_ingest import ingest_substack_posts

        async with AsyncSession(engine) as db:
            await ingest_substack_posts(db)
        logger.info("Substack posts synced on startup")
    except Exception as e:
        logger.warning(f"Substack sync on startup failed: {e}")

    # Background refresh loop
    asyncio.create_task(substack_refresh_loop())

    # Alert engine scheduler (Phase 4 — only if dependencies available)
    if PHASE4_AVAILABLE:
        asyncio.create_task(alert_engine_loop())

    # Webhook dispatcher (Phase 5 — public API)
    try:
        from app.workers.webhook_dispatcher import webhook_dispatcher_loop
        asyncio.create_task(webhook_dispatcher_loop())
        logger.info("Webhook dispatcher started")
    except Exception as e:
        logger.warning(f"Webhook dispatcher not started: {e}")

    # Monthly API quota reset (1st of each month, midnight UTC)
    async def api_quota_reset_loop():
        while True:
            try:
                now = datetime.utcnow()
                if now.day == 1 and now.hour == 0 and now.minute < 5:
                    async with AsyncSession(engine) as db:
                        await db.execute(
                            text("UPDATE api_keys SET calls_this_month = 0")
                        )
                        await db.commit()
                    logger.info("Monthly API quota reset complete")
            except Exception as e:
                logger.error(f"API quota reset failed: {e}")
            await asyncio.sleep(300)  # Check every 5 minutes

    asyncio.create_task(api_quota_reset_loop())

    logger.info(f"PlanSearch API v{settings.app_version} starting...")
    yield
    logger.info("PlanSearch API shutting down...")


app = FastAPI(
    title="PlanSearch API",
    description="National Planning Intelligence Platform — search, classify, and explore 650k+ Irish planning applications across all 31 local authorities.",
    version=settings.app_version,
    lifespan=lifespan,
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Restrictable in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register API routes
app.include_router(search.router, prefix="/api", tags=["Search"])
app.include_router(applications.router, prefix="/api", tags=["Applications"])
app.include_router(map.router, prefix="/api", tags=["Map"])
app.include_router(stats.router, prefix="/api", tags=["Stats"])
app.include_router(admin.router, prefix="/api", tags=["Admin"])
app.include_router(export.router, prefix="/api", tags=["Export"])
app.include_router(docs.router, prefix="/api", tags=["Documents"])
app.include_router(digest.router, prefix="/api", tags=["Digest"])
# Phase 3
app.include_router(insights.router, tags=["Insights"])
# Phase 4 — User accounts & alerts (only if deps installed)
if PHASE4_AVAILABLE:
    app.include_router(auth.router, prefix="/api", tags=["Auth"])
    app.include_router(billing.router, prefix="/api", tags=["Billing"])
    app.include_router(alerts.router, prefix="/api", tags=["Alerts"])
app.include_router(advertising.router, tags=["Advertising"])

# Phase 5 — Public API v1 (commercial, API-key authenticated)
app.include_router(v1_applications.router, prefix="/v1", tags=["API v1 — Applications"])
app.include_router(v1_stats.router, prefix="/v1", tags=["API v1 — Stats"])
app.include_router(v1_keys.router, prefix="/v1", tags=["API v1 — Keys"])
app.include_router(v1_webhooks.router, prefix="/v1", tags=["API v1 — Webhooks"])
app.include_router(v1_export.router, prefix="/v1", tags=["API v1 — Export"])
app.include_router(v1_developer.router, prefix="/v1", tags=["API v1 — Developer"])


@app.get("/api/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "app": settings.app_name,
        "version": settings.app_version,
    }
