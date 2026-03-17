"""PlanSearch — ARQ Job Scheduler.

Manages background job scheduling via ARQ (Redis-based async task queue).
Schedules: nightly ingest (2am), classifier (3am), scraper (1am-6am).
"""

import asyncio
import logging
from datetime import datetime, timedelta

from arq import create_pool, cron
from arq.connections import RedisSettings

from app.config import get_settings
from app.database import async_session_factory

logger = logging.getLogger(__name__)
settings = get_settings()


async def ingest_job(ctx: dict):
    """ARQ job: run DCC data ingest."""
    from app.workers.ingest import run_ingest

    logger.info("Starting scheduled ingest job")
    async with async_session_factory() as db:
        result = await run_ingest(db)
    logger.info(f"Ingest job complete: {result}")
    return result


async def classify_job(ctx: dict):
    """ARQ job: run AI classification batch."""
    from app.workers.classifier import run_classification_batch

    logger.info("Starting scheduled classification job")
    async with async_session_factory() as db:
        result = await run_classification_batch(db, batch_size=500)
    logger.info(f"Classification job complete: {result}")
    return result


async def scraper_job(ctx: dict):
    """ARQ job: run applicant name scraper."""
    from app.workers.scraper import run_scraper_batch

    logger.info("Starting scheduled scraper job")
    async with async_session_factory() as db:
        result = await run_scraper_batch(db, batch_size=500)
    logger.info(f"Scraper job complete: {result}")
    return result


async def cro_job(ctx: dict):
    """ARQ job: run CRO enrichment."""
    from app.workers.cro import run_cro_enrichment_batch

    logger.info("Starting scheduled CRO enrichment job")
    async with async_session_factory() as db:
        result = await run_cro_enrichment_batch(db, batch_size=100)
    logger.info(f"CRO enrichment job complete: {result}")
    return result


class WorkerSettings:
    """ARQ worker settings."""

    functions = [ingest_job, classify_job, scraper_job, cro_job]

    cron_jobs = [
        # Nightly ingest at 2am
        cron(ingest_job, hour=2, minute=0),
        # Classification at 3am (after ingest)
        cron(classify_job, hour=3, minute=0),
        # Scraper at 1am (runs during 1am-6am off-peak)
        cron(scraper_job, hour=1, minute=0),
        # CRO enrichment at 4am
        cron(cro_job, hour=4, minute=0),
    ]

    redis_settings = RedisSettings.from_dsn(settings.redis_url)

    # Allow longer timeouts for data-heavy jobs
    max_jobs = 5
    job_timeout = 7200  # 2 hours
    health_check_interval = 60


if __name__ == "__main__":
    """Run the ARQ worker directly."""
    from arq import run_worker

    logging.basicConfig(level=logging.INFO)
    run_worker(WorkerSettings)
