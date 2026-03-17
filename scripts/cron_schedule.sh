#!/bin/bash
# PlanSearch Phase 1-3 — Cron Jobs
# Install: crontab -e, paste entries below
#
# Ensure environment variables are set:
#   DATABASE_URL, CLAUDE_API_KEY, ENCRYPTION_KEY

# ── Phase 1 (DCC-specific) ─────────────────────────────────────────────

# DCC CSV ingest: every 6 hours
0 */6 * * * cd /opt/plansearch && /usr/local/bin/python -m app.workers.ingest 2>&1 | tee -a /var/log/plansearch/ingest.log

# AI classification: nightly at 01:00
0 1 * * * cd /opt/plansearch && /usr/local/bin/python -m app.workers.classifier --batch-size=200 2>&1 | tee -a /var/log/plansearch/classify.log

# Applicant scraper: nightly at 02:00
0 2 * * * cd /opt/plansearch && /usr/local/bin/python -m app.workers.scraper 2>&1 | tee -a /var/log/plansearch/scrape.log

# Document scraper: nightly at 03:00
0 3 * * * cd /opt/plansearch && /usr/local/bin/python -m app.workers.doc_scraper 2>&1 | tee -a /var/log/plansearch/docs.log


# ── Phase 2 (National → NPAD + BCMS) ──────────────────────────────────

# NPAD incremental sync: weekly on Sundays at 04:00
0 4 * * 0 cd /opt/plansearch && /usr/local/bin/python -c "
import asyncio
from app.database import async_session
from app.workers.npad_ingest import ingest_npad_incremental
async def run():
    async with async_session() as db:
        await ingest_npad_incremental(db)
asyncio.run(run())
" 2>&1 | tee -a /var/log/plansearch/npad.log

# BCMS Commencement Notice ingest: weekly on Sundays at 05:00
0 5 * * 0 cd /opt/plansearch && /usr/local/bin/python -c "
import asyncio
from app.database import async_session
from app.workers.bcms_ingest import ingest_bcms_commencements
async def run():
    async with async_session() as db:
        await ingest_bcms_commencements(db)
asyncio.run(run())
" 2>&1 | tee -a /var/log/plansearch/bcms_cn.log

# BCMS FSC/DAC ingest: weekly on Sundays at 06:00
0 6 * * 0 cd /opt/plansearch && /usr/local/bin/python -c "
import asyncio
from app.database import async_session
from app.workers.bcms_ingest import ingest_bcms_fsc
async def run():
    async with async_session() as db:
        await ingest_bcms_fsc(db)
asyncio.run(run())
" 2>&1 | tee -a /var/log/plansearch/bcms_fsc.log

# Lifecycle stage update: weekly on Sundays at 07:00 (after data ingest)
0 7 * * 0 cd /opt/plansearch && /usr/local/bin/python -c "
import asyncio
from app.database import async_session
from app.workers.lifecycle import update_lifecycle_stages
async def run():
    async with async_session() as db:
        await update_lifecycle_stages(db)
asyncio.run(run())
" 2>&1 | tee -a /var/log/plansearch/lifecycle.log

# AI value estimation: weekly on Mondays at 01:00 (200 records/batch)
0 1 * * 1 cd /opt/plansearch && /usr/local/bin/python -c "
import asyncio
from app.database import async_session
from app.workers.value_estimator import run_value_estimation
async def run():
    async with async_session() as db:
        await run_value_estimation(db, batch_size=200)
asyncio.run(run())
" 2>&1 | tee -a /var/log/plansearch/value_est.log

# Significance scoring: weekly on Mondays at 02:00
0 2 * * 1 cd /opt/plansearch && /usr/local/bin/python -c "
import asyncio
from app.database import async_session
from app.workers.value_estimator import run_significance_scoring
async def run():
    async with async_session() as db:
        await run_significance_scoring(db)
asyncio.run(run())
" 2>&1 | tee -a /var/log/plansearch/significance.log

# Weekly digest generation: Mondays at 08:00
0 8 * * 1 cd /opt/plansearch && /usr/local/bin/python -c "
import asyncio
from app.database import async_session
from app.workers.digest import generate_weekly_digest
async def run():
    async with async_session() as db:
        await generate_weekly_digest(db)
asyncio.run(run())
" 2>&1 | tee -a /var/log/plansearch/digest.log


# ── Phase 3 (The Build + Advertising) ─────────────────────────────────

# Substack RSS ingest: every 6 hours (per spec 23.7)
0 */6 * * * cd /opt/plansearch && /usr/local/bin/python -c "
import asyncio
from app.database import async_session
from app.workers.substack_ingest import ingest_substack_posts
async def run():
    async with async_session() as db:
        await ingest_substack_posts(db)
asyncio.run(run())
" 2>&1 | tee -a /var/log/plansearch/substack.log

# AI content linking for unlinked posts: 30 min after RSS ingest (per spec 23.7)
30 */6 * * * cd /opt/plansearch && /usr/local/bin/python -c "
import asyncio
from app.database import async_session
from app.workers.content_linker import link_unlinked_posts
async def run():
    async with async_session() as db:
        await link_unlinked_posts(db)
asyncio.run(run())
" 2>&1 | tee -a /var/log/plansearch/content_link.log

# Database backup: daily at 00:00
0 0 * * * /opt/plansearch/scripts/backup.sh 2>&1 | tee -a /var/log/plansearch/backup.log
