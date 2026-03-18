import asyncio
import logging
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
app.include_router(advertising.router, tags=["Advertising"])


@app.get("/api/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "app": settings.app_name,
        "version": settings.app_version,
    }
