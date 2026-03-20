"""PlanSearch Public API v1 — Webhook Management.

POST   /v1/webhooks       — Create a webhook (returns secret ONCE)
GET    /v1/webhooks       — List webhooks for an API key
GET    /v1/webhooks/{id}  — Get webhook detail with recent deliveries
DELETE /v1/webhooks/{id}  — Delete a webhook
"""

import logging
import secrets
import hashlib
import time
from typing import Optional, List

from fastapi import APIRouter, Depends, Request, Response
from pydantic import BaseModel
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import ApiKey, Webhook, WebhookDelivery
from app.middleware.api_auth import (
    require_api_key, wrap_response, add_rate_limit_headers,
    _log_usage, api_error_response, TIER_CONFIG,
)
from app.utils.crypto import encrypt_value

router = APIRouter()
logger = logging.getLogger(__name__)

VALID_EVENTS = {
    "application.new",
    "application.granted",
    "application.refused",
    "application.commenced",
    "application.completed",
    "application.fsc_filed",
    "application.withdrawn",
}


class CreateWebhookRequest(BaseModel):
    url: str
    events: List[str] = []
    filters: Optional[dict] = None


@router.post("/webhooks")
async def create_webhook(
    body: CreateWebhookRequest,
    request: Request,
    response: Response,
    api_key: ApiKey = Depends(require_api_key),
    db: AsyncSession = Depends(get_db),
):
    """Create a webhook. Returns the webhook_secret ONCE — store it securely."""
    start = time.time()

    # Validate URL
    if not body.url or not body.url.startswith(("https://", "http://")):
        api_error_response("INVALID_URL", "Webhook URL must start with https:// or http://", status=400)

    # Validate events
    if body.events:
        invalid = set(body.events) - VALID_EVENTS
        if invalid:
            api_error_response(
                "INVALID_EVENTS",
                f"Invalid events: {', '.join(invalid)}. Valid: {', '.join(sorted(VALID_EVENTS))}",
                status=400,
            )

    # Check webhook limit for this tier
    tier_config = TIER_CONFIG.get(api_key.tier, TIER_CONFIG["developer"])
    max_webhooks = tier_config["max_webhooks"]
    existing_count = await db.execute(
        select(func.count()).select_from(Webhook).where(
            Webhook.api_key_id == api_key.id, Webhook.is_active == True
        )
    )
    count = existing_count.scalar() or 0
    if count >= max_webhooks:
        api_error_response(
            "WEBHOOK_LIMIT_REACHED",
            f"Your {api_key.tier} tier allows {max_webhooks} webhook(s). Upgrade for more.",
            status=403,
        )

    # Generate secret
    raw_secret = "whsec_" + secrets.token_hex(32)
    secret_encrypted = encrypt_value(raw_secret)

    webhook = Webhook(
        api_key_id=api_key.id,
        url=body.url,
        events=body.events or list(VALID_EVENTS),
        filters=body.filters or {},
        secret_encrypted=secret_encrypted,
    )
    db.add(webhook)
    await db.flush()

    query_time_ms = (time.time() - start) * 1000
    await _log_usage(api_key.id, "/v1/webhooks", 200, int(query_time_ms), db)
    add_rate_limit_headers(response, request)

    return wrap_response({
        "id": str(webhook.id),
        "url": webhook.url,
        "events": webhook.events,
        "filters": webhook.filters,
        "webhook_secret": raw_secret,  # Shown ONCE — never stored in plain text
        "is_active": True,
        "created_at": webhook.created_at.isoformat() if webhook.created_at else None,
        "_warning": "Store the webhook_secret securely. It will not be shown again.",
    }, request)


@router.get("/webhooks")
async def list_webhooks(
    request: Request,
    response: Response,
    api_key: ApiKey = Depends(require_api_key),
    db: AsyncSession = Depends(get_db),
):
    """List all webhooks for the authenticated API key."""
    start = time.time()

    result = await db.execute(
        select(Webhook)
        .where(Webhook.api_key_id == api_key.id)
        .order_by(Webhook.created_at.desc())
    )
    webhooks = result.scalars().all()

    data = []
    for wh in webhooks:
        data.append({
            "id": str(wh.id),
            "url": wh.url,
            "events": wh.events,
            "filters": wh.filters,
            "is_active": wh.is_active,
            "failure_count": wh.failure_count,
            "created_at": wh.created_at.isoformat() if wh.created_at else None,
            "last_delivered_at": wh.last_delivered_at.isoformat() if wh.last_delivered_at else None,
        })

    query_time_ms = (time.time() - start) * 1000
    await _log_usage(api_key.id, "/v1/webhooks", 200, int(query_time_ms), db)
    add_rate_limit_headers(response, request)

    return wrap_response({"webhooks": data, "total": len(data)}, request)


@router.get("/webhooks/{webhook_id}")
async def get_webhook(
    webhook_id: str,
    request: Request,
    response: Response,
    api_key: ApiKey = Depends(require_api_key),
    db: AsyncSession = Depends(get_db),
):
    """Get webhook detail with recent deliveries."""
    start = time.time()

    result = await db.execute(
        select(Webhook).where(
            Webhook.id == webhook_id, Webhook.api_key_id == api_key.id
        )
    )
    wh = result.scalar_one_or_none()
    if not wh:
        api_error_response("NOT_FOUND", "Webhook not found.", status=404)

    # Recent deliveries
    del_result = await db.execute(
        select(WebhookDelivery)
        .where(WebhookDelivery.webhook_id == webhook_id)
        .order_by(WebhookDelivery.created_at.desc())
        .limit(50)
    )
    deliveries = del_result.scalars().all()

    query_time_ms = (time.time() - start) * 1000
    await _log_usage(api_key.id, f"/v1/webhooks/{webhook_id}", 200, int(query_time_ms), db)
    add_rate_limit_headers(response, request)

    return wrap_response({
        "id": str(wh.id),
        "url": wh.url,
        "events": wh.events,
        "filters": wh.filters,
        "is_active": wh.is_active,
        "failure_count": wh.failure_count,
        "created_at": wh.created_at.isoformat() if wh.created_at else None,
        "last_delivered_at": wh.last_delivered_at.isoformat() if wh.last_delivered_at else None,
        "deliveries": [
            {
                "id": str(d.id),
                "event": d.event,
                "reg_ref": d.reg_ref,
                "status": d.status,
                "attempts": d.attempts,
                "http_status": d.http_status,
                "delivered_at": d.delivered_at.isoformat() if d.delivered_at else None,
                "created_at": d.created_at.isoformat() if d.created_at else None,
            }
            for d in deliveries
        ],
    }, request)


@router.delete("/webhooks/{webhook_id}")
async def delete_webhook(
    webhook_id: str,
    request: Request,
    response: Response,
    api_key: ApiKey = Depends(require_api_key),
    db: AsyncSession = Depends(get_db),
):
    """Delete a webhook."""
    result = await db.execute(
        select(Webhook).where(
            Webhook.id == webhook_id, Webhook.api_key_id == api_key.id
        )
    )
    wh = result.scalar_one_or_none()
    if not wh:
        api_error_response("NOT_FOUND", "Webhook not found.", status=404)

    await db.delete(wh)
    add_rate_limit_headers(response, request)

    return wrap_response({"deleted": True, "id": webhook_id}, request)
