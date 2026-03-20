"""PlanSearch Public API v1 — Self-Serve API Key Management.

POST   /v1/keys     — Generate a new API key
GET    /v1/keys     — List all keys for the authenticated user
DELETE /v1/keys/{id} — Revoke an API key
"""

import logging
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.auth import get_current_user
from app.models import User, ApiKey
from app.middleware.api_auth import generate_api_key, TIER_CONFIG

router = APIRouter()
logger = logging.getLogger(__name__)


class CreateKeyRequest(BaseModel):
    name: str = "Default"
    environment: str = "live"  # live or test


class CreateKeyResponse(BaseModel):
    id: str
    name: str
    key: str  # Raw key — shown ONCE
    key_prefix: str
    environment: str
    tier: str
    monthly_quota: int
    rate_limit_per_minute: int
    created_at: str


class KeySummary(BaseModel):
    id: str
    name: str
    key_prefix: str
    environment: str
    tier: str
    is_active: bool
    calls_this_month: int
    monthly_quota: int
    rate_limit_per_minute: int
    created_at: str
    last_used_at: Optional[str] = None


@router.post("/keys")
async def create_api_key(
    body: CreateKeyRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Generate a new API key. The raw key is returned ONCE — store it securely."""
    # Determine tier from user subscription
    tier_map = {
        "free": "developer",
        "starter": "starter",
        "professional": "professional",
        "agency": "enterprise",
    }
    tier = tier_map.get(user.subscription_tier, "developer")
    tier_config = TIER_CONFIG.get(tier, TIER_CONFIG["developer"])

    # Check key limit (max 5 per user)
    existing_count = await db.execute(
        select(func.count()).select_from(ApiKey).where(
            ApiKey.user_id == user.id, ApiKey.is_active == True
        )
    )
    count = existing_count.scalar() or 0
    if count >= 5:
        raise HTTPException(status_code=400, detail="Maximum 5 active API keys per account.")

    # Validate environment
    if body.environment not in ("live", "test"):
        raise HTTPException(status_code=400, detail="Environment must be 'live' or 'test'.")

    # Generate key
    raw_key, key_hash, key_prefix = generate_api_key(body.environment)

    api_key = ApiKey(
        user_id=user.id,
        name=body.name,
        key_hash=key_hash,
        key_prefix=key_prefix,
        environment=body.environment,
        tier=tier,
        monthly_quota=tier_config["monthly_quota"],
        rate_limit_per_minute=tier_config["rate_limit_per_minute"],
    )
    db.add(api_key)
    await db.flush()

    return {
        "data": {
            "id": str(api_key.id),
            "name": api_key.name,
            "key": raw_key,  # Shown ONCE — never stored
            "key_prefix": key_prefix,
            "environment": body.environment,
            "tier": tier,
            "monthly_quota": api_key.monthly_quota,
            "rate_limit_per_minute": api_key.rate_limit_per_minute,
            "created_at": api_key.created_at.isoformat() if api_key.created_at else datetime.now(timezone.utc).isoformat(),
        },
        "meta": {
            "warning": "Store this API key securely. It will not be shown again.",
        },
    }


@router.get("/keys")
async def list_api_keys(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List all API keys for the current user."""
    result = await db.execute(
        select(ApiKey)
        .where(ApiKey.user_id == user.id)
        .order_by(ApiKey.created_at.desc())
    )
    keys = result.scalars().all()

    return {
        "data": {
            "keys": [
                {
                    "id": str(k.id),
                    "name": k.name,
                    "key_prefix": k.key_prefix,
                    "environment": k.environment,
                    "tier": k.tier,
                    "is_active": k.is_active,
                    "calls_this_month": k.calls_this_month,
                    "monthly_quota": k.monthly_quota,
                    "rate_limit_per_minute": k.rate_limit_per_minute,
                    "created_at": k.created_at.isoformat() if k.created_at else None,
                    "last_used_at": k.last_used_at.isoformat() if k.last_used_at else None,
                }
                for k in keys
            ],
            "total": len(keys),
        },
    }


@router.delete("/keys/{key_id}")
async def revoke_api_key(
    key_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Revoke (deactivate) an API key."""
    result = await db.execute(
        select(ApiKey).where(ApiKey.id == key_id, ApiKey.user_id == user.id)
    )
    api_key = result.scalar_one_or_none()
    if not api_key:
        raise HTTPException(status_code=404, detail="API key not found.")

    api_key.is_active = False
    return {"data": {"id": str(api_key.id), "is_active": False, "message": "API key revoked."}}
