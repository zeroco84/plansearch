"""PlanSearch — Webhook Dispatcher Worker.

Background worker that:
1. Polls webhook_deliveries for pending deliveries every 30 seconds
2. Signs payloads with HMAC-SHA256 using encrypted webhook secrets
3. Delivers to customer endpoints with timeout and retry logic
4. Tracks delivery status and failure counts

Retry policy: 3 attempts (immediate → 5 min → 30 min), then marked as failed.
Webhooks auto-disabled after 100 consecutive failures.
"""

import asyncio
import hashlib
import hmac
import json
import logging
import time
from datetime import datetime, timezone

import httpx
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import async_session_factory
from app.models import Webhook, WebhookDelivery
from app.utils.crypto import decrypt_value

logger = logging.getLogger(__name__)

DELIVERY_TIMEOUT = 10.0  # seconds
MAX_ATTEMPTS = 3
RETRY_DELAYS = [0, 300, 1800]  # immediate, 5 min, 30 min
AUTO_DISABLE_THRESHOLD = 100


def sign_payload(payload: dict, raw_secret: str) -> str:
    """Generate X-PlanSearch-Signature header value."""
    timestamp = str(int(time.time()))
    payload_json = json.dumps(payload, separators=(",", ":"))
    payload_string = f"{timestamp}.{payload_json}"
    sig = hmac.new(
        raw_secret.encode(),
        payload_string.encode(),
        hashlib.sha256,
    ).hexdigest()
    return f"t={timestamp},v1={sig}"


async def deliver_webhook(delivery: WebhookDelivery, webhook: Webhook, db: AsyncSession):
    """Attempt to deliver a single webhook."""
    try:
        # Decrypt the stored secret
        raw_secret = decrypt_value(webhook.secret_encrypted)
    except Exception as e:
        logger.error(f"Failed to decrypt webhook secret for {webhook.id}: {e}")
        delivery.status = "failed"
        delivery.attempts += 1
        return

    # Sign the payload
    signature = sign_payload(delivery.payload, raw_secret)

    headers = {
        "Content-Type": "application/json",
        "X-PlanSearch-Event": delivery.event,
        "X-PlanSearch-Signature": signature,
        "X-PlanSearch-Delivery": str(delivery.id),
        "User-Agent": "PlanSearch-Webhook/1.0",
    }

    try:
        async with httpx.AsyncClient(timeout=DELIVERY_TIMEOUT) as client:
            resp = await client.post(
                webhook.url,
                json=delivery.payload,
                headers=headers,
            )
            delivery.http_status = resp.status_code
            delivery.attempts += 1

            if 200 <= resp.status_code < 300:
                delivery.status = "delivered"
                delivery.delivered_at = datetime.now(timezone.utc)
                # Reset failure count on success
                webhook.failure_count = 0
                webhook.last_delivered_at = datetime.now(timezone.utc)
                logger.info(
                    f"Webhook delivered: {delivery.event} → {webhook.url} "
                    f"(HTTP {resp.status_code})"
                )
            else:
                logger.warning(
                    f"Webhook delivery failed: {delivery.event} → {webhook.url} "
                    f"(HTTP {resp.status_code})"
                )
                webhook.failure_count += 1
                if delivery.attempts >= MAX_ATTEMPTS:
                    delivery.status = "failed"

    except Exception as e:
        delivery.attempts += 1
        webhook.failure_count += 1
        logger.warning(f"Webhook delivery error: {delivery.event} → {webhook.url}: {e}")
        if delivery.attempts >= MAX_ATTEMPTS:
            delivery.status = "failed"

    # Auto-disable webhook after too many failures
    if webhook.failure_count >= AUTO_DISABLE_THRESHOLD:
        webhook.is_active = False
        logger.error(
            f"Webhook {webhook.id} auto-disabled after {AUTO_DISABLE_THRESHOLD} consecutive failures."
        )


async def process_pending_deliveries():
    """Process all pending webhook deliveries."""
    async with async_session_factory() as db:
        try:
            # Fetch pending deliveries
            result = await db.execute(
                select(WebhookDelivery)
                .where(
                    WebhookDelivery.status == "pending",
                    WebhookDelivery.attempts < MAX_ATTEMPTS,
                )
                .order_by(WebhookDelivery.created_at.asc())
                .limit(50)
            )
            deliveries = result.scalars().all()

            if not deliveries:
                return

            logger.info(f"Processing {len(deliveries)} pending webhook deliveries")

            for delivery in deliveries:
                # Fetch the associated webhook
                wh_result = await db.execute(
                    select(Webhook).where(
                        Webhook.id == delivery.webhook_id,
                        Webhook.is_active == True,
                    )
                )
                webhook = wh_result.scalar_one_or_none()

                if not webhook:
                    delivery.status = "failed"
                    continue

                # Check retry delay
                if delivery.attempts > 0:
                    delay = RETRY_DELAYS[min(delivery.attempts, len(RETRY_DELAYS) - 1)]
                    elapsed = (datetime.now(timezone.utc) - delivery.created_at).total_seconds()
                    if elapsed < delay:
                        continue  # Not yet time to retry

                await deliver_webhook(delivery, webhook, db)

            await db.commit()

        except Exception as e:
            logger.error(f"Webhook dispatcher error: {e}")
            await db.rollback()


async def create_webhook_delivery(
    event: str,
    reg_ref: str,
    payload: dict,
    db: AsyncSession,
):
    """Create webhook delivery records for all matching active webhooks.

    Called from ingest workers when a planning event occurs.
    """
    # Find all active webhooks subscribed to this event
    result = await db.execute(
        select(Webhook).where(
            Webhook.is_active == True,
        )
    )
    webhooks = result.scalars().all()

    for webhook in webhooks:
        # Check event subscription
        if webhook.events and event not in webhook.events:
            continue

        # Check filters
        filters = webhook.filters or {}
        if filters.get("planning_authorities"):
            pa = payload.get("data", {}).get("planning_authority", "")
            if pa not in filters["planning_authorities"]:
                continue
        if filters.get("dev_categories"):
            cat = payload.get("data", {}).get("dev_category", "")
            if cat not in filters["dev_categories"]:
                continue
        if filters.get("value_min"):
            val = payload.get("data", {}).get("est_value_high", 0) or 0
            if val < filters["value_min"]:
                continue

        delivery = WebhookDelivery(
            webhook_id=webhook.id,
            event=event,
            reg_ref=reg_ref,
            payload=payload,
        )
        db.add(delivery)

    logger.info(f"Created webhook deliveries for event={event} reg_ref={reg_ref}")


async def webhook_dispatcher_loop():
    """Background loop — runs every 30 seconds."""
    logger.info("Webhook dispatcher started")
    while True:
        try:
            await process_pending_deliveries()
        except Exception as e:
            logger.error(f"Webhook dispatcher loop error: {e}")
        await asyncio.sleep(30)
