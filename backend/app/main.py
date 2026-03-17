"""PlanSearch — FastAPI Application Entry Point.

Dublin Planning Intelligence Platform API.
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.api.routes import search, applications, map, stats, admin, export

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)
settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler."""
    logger.info(f"PlanSearch API v{settings.app_version} starting...")
    yield
    logger.info("PlanSearch API shutting down...")


app = FastAPI(
    title="PlanSearch API",
    description="Dublin Planning Intelligence Platform — search, classify, and explore Dublin City Council planning applications.",
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


@app.get("/api/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "app": settings.app_name,
        "version": settings.app_version,
    }
