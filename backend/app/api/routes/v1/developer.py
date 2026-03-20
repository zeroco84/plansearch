"""PlanSearch Public API v1 — Developer Usage & Management Endpoints.

Used by the /developer frontend page. All require JWT auth (not API key).

GET  /v1/developer/usage    — Usage stats for all user's API keys
GET  /v1/developer/usage/daily — Daily call breakdown (30 days)
"""

import logging
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import select, func, cast, Date
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.auth import get_current_user
from app.models import User, ApiKey, ApiUsage

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/developer/usage")
async def get_usage_stats(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Usage summary for all of the current user's API keys."""
    # Get all user's API keys
    result = await db.execute(
        select(ApiKey).where(ApiKey.user_id == user.id)
    )
    keys = result.scalars().all()

    if not keys:
        return {
            "data": {
                "total_calls_this_month": 0,
                "monthly_quota": 0,
                "quota_percent": 0,
                "keys_count": 0,
                "top_endpoints": [],
            }
        }

    key_ids = [k.id for k in keys]
    total_calls = sum(k.calls_this_month for k in keys)
    max_quota = max(k.monthly_quota for k in keys)

    # Top endpoints (last 30 days)
    thirty_days_ago = datetime.now(timezone.utc) - timedelta(days=30)
    endpoint_result = await db.execute(
        select(
            ApiUsage.endpoint,
            func.count(ApiUsage.id).label("count"),
            func.avg(ApiUsage.response_time_ms).label("avg_ms"),
        )
        .where(
            ApiUsage.api_key_id.in_(key_ids),
            ApiUsage.called_at >= thirty_days_ago,
        )
        .group_by(ApiUsage.endpoint)
        .order_by(func.count(ApiUsage.id).desc())
        .limit(10)
    )
    top_endpoints = [
        {
            "endpoint": row.endpoint,
            "count": row.count,
            "avg_response_ms": round(float(row.avg_ms), 1) if row.avg_ms else None,
        }
        for row in endpoint_result.all()
    ]

    return {
        "data": {
            "total_calls_this_month": total_calls,
            "monthly_quota": max_quota,
            "quota_percent": round(total_calls / max_quota * 100, 1) if max_quota > 0 else 0,
            "keys_count": len(keys),
            "top_endpoints": top_endpoints,
            "tier": keys[0].tier if keys else "developer",
        }
    }


@router.get("/developer/usage/daily")
async def get_daily_usage(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Daily API call counts for the last 30 days."""
    result = await db.execute(
        select(ApiKey.id).where(ApiKey.user_id == user.id)
    )
    key_ids = [row[0] for row in result.all()]

    if not key_ids:
        return {"data": {"daily": []}}

    thirty_days_ago = datetime.now(timezone.utc) - timedelta(days=30)
    daily_result = await db.execute(
        select(
            cast(ApiUsage.called_at, Date).label("day"),
            func.count(ApiUsage.id).label("count"),
        )
        .where(
            ApiUsage.api_key_id.in_(key_ids),
            ApiUsage.called_at >= thirty_days_ago,
        )
        .group_by(cast(ApiUsage.called_at, Date))
        .order_by(cast(ApiUsage.called_at, Date).asc())
    )

    daily = [
        {"date": str(row.day), "calls": row.count}
        for row in daily_result.all()
    ]

    return {"data": {"daily": daily}}


# ── Developer Webhook Management (JWT auth) ──────────────────────────────


@router.get("/developer/webhooks")
async def list_developer_webhooks(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List all webhooks for the user's API keys (JWT auth for developer portal)."""
    from app.models import Webhook

    # Get all user's API key IDs
    key_result = await db.execute(
        select(ApiKey.id).where(ApiKey.user_id == user.id)
    )
    key_ids = [row[0] for row in key_result.all()]

    if not key_ids:
        return {"data": {"webhooks": [], "total": 0}}

    result = await db.execute(
        select(Webhook)
        .where(Webhook.api_key_id.in_(key_ids))
        .order_by(Webhook.created_at.desc())
    )
    webhooks = result.scalars().all()

    return {
        "data": {
            "webhooks": [
                {
                    "id": str(wh.id),
                    "url": wh.url,
                    "events": wh.events,
                    "filters": wh.filters,
                    "is_active": wh.is_active,
                    "failure_count": wh.failure_count,
                    "created_at": wh.created_at.isoformat() if wh.created_at else None,
                    "last_delivered_at": wh.last_delivered_at.isoformat() if wh.last_delivered_at else None,
                }
                for wh in webhooks
            ],
            "total": len(webhooks),
        }
    }


@router.post("/developer/webhooks")
async def create_developer_webhook(
    body: dict,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create a webhook via JWT auth (developer portal). Uses the user's first active API key."""
    import secrets as sec
    from app.models import Webhook
    from app.utils.crypto import encrypt_value
    from app.middleware.api_auth import TIER_CONFIG

    # Find user's first active API key
    key_result = await db.execute(
        select(ApiKey)
        .where(ApiKey.user_id == user.id, ApiKey.is_active == True)
        .limit(1)
    )
    api_key = key_result.scalar_one_or_none()
    if not api_key:
        from fastapi import HTTPException
        raise HTTPException(status_code=400, detail="Create an API key first before adding webhooks.")

    url = body.get("url", "")
    events = body.get("events", [])

    if not url or not url.startswith(("https://", "http://")):
        from fastapi import HTTPException
        raise HTTPException(status_code=400, detail="Webhook URL must start with https://")

    # Check limit
    tier_config = TIER_CONFIG.get(api_key.tier, TIER_CONFIG["developer"])
    max_webhooks = tier_config["max_webhooks"]
    existing = await db.execute(
        select(func.count()).select_from(Webhook).where(
            Webhook.api_key_id == api_key.id, Webhook.is_active == True
        )
    )
    count = existing.scalar() or 0
    if count >= max_webhooks:
        from fastapi import HTTPException
        raise HTTPException(status_code=403, detail=f"Webhook limit ({max_webhooks}) reached for {api_key.tier} tier.")

    raw_secret = "whsec_" + sec.token_hex(32)
    secret_encrypted = encrypt_value(raw_secret)

    VALID_EVENTS = {
        "application.new", "application.granted", "application.refused",
        "application.commenced", "application.completed",
        "application.fsc_filed", "application.withdrawn",
    }

    webhook = Webhook(
        api_key_id=api_key.id,
        url=url,
        events=events if events else list(VALID_EVENTS),
        filters=body.get("filters", {}),
        secret_encrypted=secret_encrypted,
    )
    db.add(webhook)
    await db.flush()

    return {
        "data": {
            "id": str(webhook.id),
            "url": webhook.url,
            "events": webhook.events,
            "webhook_secret": raw_secret,
            "is_active": True,
            "created_at": webhook.created_at.isoformat() if webhook.created_at else None,
        }
    }


@router.delete("/developer/webhooks/{webhook_id}")
async def delete_developer_webhook(
    webhook_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Delete a webhook via JWT auth (developer portal)."""
    from app.models import Webhook

    # Verify ownership: webhook belongs to one of the user's API keys
    key_result = await db.execute(
        select(ApiKey.id).where(ApiKey.user_id == user.id)
    )
    key_ids = [row[0] for row in key_result.all()]

    result = await db.execute(
        select(Webhook).where(
            Webhook.id == webhook_id,
            Webhook.api_key_id.in_(key_ids),
        )
    )
    wh = result.scalar_one_or_none()
    if not wh:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Webhook not found.")

    await db.delete(wh)
    return {"data": {"deleted": True, "id": webhook_id}}
