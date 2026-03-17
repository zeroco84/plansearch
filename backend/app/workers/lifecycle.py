"""PlanSearch — Lifecycle Stage Computation.

Determines the current lifecycle stage of each planning application
by joining data across NPAD, BCMS CN/CCC, and FSC/DAC datasets.

9-stage lifecycle:
  submitted → registered → further_info → decided_granted/decided_refused
  → appealed → appeal_granted/appeal_refused → fsc_filed
  → under_construction → complete (+ expired)
"""

import logging
from datetime import date, datetime

from sqlalchemy import select, update, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Application, CommencementNotice, FSCApplication

logger = logging.getLogger(__name__)


def compute_lifecycle_stage(
    app: Application,
    cn_commencement_date=None,
    ccc_date_validated=None,
    fsc_submission_date=None,
) -> str:
    """Determine the current lifecycle stage in priority order.

    Completion takes highest priority, working backwards to submission.
    """
    # Stage 9: Building Complete
    if ccc_date_validated:
        return "complete"

    # Stage 8: Under Construction
    if cn_commencement_date:
        return "under_construction"

    # Stage 7: FSC Filed
    if fsc_submission_date:
        return "fsc_filed"

    # Stage 6: Appeal Decided
    if app.appeal_decision_date:
        decision = (app.appeal_decision or "").lower()
        if "grant" in decision:
            return "appeal_granted"
        return "appeal_refused"

    # Stage 5: Appeal Lodged
    if app.appeal_ref_number:
        return "appealed"

    # Stage 4: Decision Made
    if app.dec_date:
        d = (app.decision or "").lower()
        if "grant" in d:
            # Check if permission expired without commencement
            if app.time_exp and app.time_exp < date.today() and not cn_commencement_date:
                return "expired"
            return "decided_granted"
        return "decided_refused"

    # Stage 3: Further Information
    if app.fi_request_date:
        return "further_info"

    # Stage 2: Registered
    if app.rgn_date:
        return "registered"

    # Stage 1: Application Submitted
    return "submitted"


async def update_lifecycle_stages(db: AsyncSession, limit: int = 0) -> dict:
    """Recompute lifecycle stages for all applications.

    Joins against commencement_notices and fsc_applications to determine
    the most advanced stage for each application.
    """
    stats = {"updated": 0, "total": 0}

    # Get all applications
    query = select(Application)
    if limit > 0:
        query = query.limit(limit)

    result = await db.execute(query)
    applications = result.scalars().all()

    logger.info(f"Lifecycle: Processing {len(applications)} applications")

    for app in applications:
        stats["total"] += 1

        # Look up BCMS data for this reg_ref
        cn_result = await db.execute(
            select(
                func.max(CommencementNotice.cn_commencement_date),
                func.max(CommencementNotice.ccc_date_validated),
            ).where(CommencementNotice.reg_ref == app.reg_ref)
        )
        cn_row = cn_result.one_or_none()
        cn_commencement = cn_row[0] if cn_row else None
        ccc_validated = cn_row[1] if cn_row else None

        fsc_result = await db.execute(
            select(func.min(FSCApplication.submission_date))
            .where(FSCApplication.reg_ref == app.reg_ref)
        )
        fsc_date = fsc_result.scalar()

        new_stage = compute_lifecycle_stage(
            app,
            cn_commencement_date=cn_commencement,
            ccc_date_validated=ccc_validated,
            fsc_submission_date=fsc_date,
        )

        if app.lifecycle_stage != new_stage:
            app.lifecycle_stage = new_stage
            app.lifecycle_updated_at = datetime.utcnow()
            stats["updated"] += 1

        if stats["total"] % 10000 == 0:
            await db.commit()
            logger.info(f"Lifecycle: {stats['total']:,} processed, {stats['updated']:,} updated")

    await db.commit()
    logger.info(f"Lifecycle: Complete — {stats}")
    return stats
