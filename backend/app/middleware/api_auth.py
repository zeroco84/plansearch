"""PlanSearch — API Key Authentication Middleware.

Validates API keys, enforces rate limits (Redis sliding window),
tracks monthly quota, and logs usage. Used by all /v1/ routes.
"""

import hashlib
import logging
import os
import time
import uuid as uuid_mod
from datetime import datetime, timezone
from typing import Optional

from fastapi import Depends, HTTPException, Request, Response
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import ApiKey, ApiUsage

logger = logging.getLogger(__name__)

# ── Tier configuration ────────────────────────────────────────────────────

TIER_CONFIG = {
    "developer": {"monthly_quota": 1_000, "rate_limit_per_minute": 10, "max_webhooks": 1},
    "starter": {"monthly_quota": 10_000, "rate_limit_per_minute": 60, "max_webhooks": 3},
    "professional": {"monthly_quota": 100_000, "rate_limit_per_minute": 300, "max_webhooks": 10},
    "enterprise": {"monthly_quota": 1_000_000, "rate_limit_per_minute": 1_000, "max_webhooks": 999},
}


def hash_api_key(raw_key: str) -> str:
    """SHA-256 hash of a raw API key."""
    return hashlib.sha256(raw_key.encode()).hexdigest()


def generate_api_key(environment: str = "live") -> tuple[str, str, str]:
    """Generate a new API key. Returns (raw_key, key_hash, key_prefix)."""
    import secrets
    random_part = secrets.token_hex(16)  # 32 chars
    raw_key = f"psk_{environment}_{random_part}"
    key_hash = hash_api_key(raw_key)
    key_prefix = raw_key[:16]  # "psk_live_ab12cd3" or similar
    return raw_key, key_hash, key_prefix


async def _lookup_api_key(raw_key: str, db: AsyncSession) -> Optional[ApiKey]:
    """Look up an API key by its SHA-256 hash."""
    key_hash = hash_api_key(raw_key)
    result = await db.execute(
        select(ApiKey).where(ApiKey.key_hash == key_hash, ApiKey.is_active == True)
    )
    return result.scalar_one_or_none()


async def _check_rate_limit(api_key: ApiKey) -> tuple[bool, int, int, int]:
    """Check Redis sliding-window rate limit.

    Returns (allowed, limit, remaining, reset_timestamp).
    """
    redis_url = os.environ.get("REDIS_URL", "")
    limit = api_key.rate_limit_per_minute
    remaining = limit
    reset_ts = int(time.time()) + 60

    if not redis_url:
        return True, limit, remaining, reset_ts

    try:
        import redis.asyncio as aioredis
        r = aioredis.from_url(redis_url)
        now = time.time()
        window_key = f"api_rate:{api_key.id}"

        pipe = r.pipeline()
        # Remove entries older than 60 seconds
        pipe.zremrangebyscore(window_key, 0, now - 60)
        # Add current request
        pipe.zadd(window_key, {f"{now}:{uuid_mod.uuid4().hex[:8]}": now})
        # Count requests in window
        pipe.zcard(window_key)
        # Set expiry on the key
        pipe.expire(window_key, 120)
        results = await pipe.execute()
        await r.aclose()

        count = results[2]
        remaining = max(0, limit - count)
        allowed = count <= limit
        return allowed, limit, remaining, reset_ts

    except Exception as e:
        logger.warning(f"Redis rate limit check failed: {e}")
        return True, limit, remaining, reset_ts  # Fail open


async def _log_usage(
    api_key_id, endpoint: str, status_code: int,
    response_time_ms: int, db: AsyncSession
):
    """Log an API call to the api_usage table."""
    try:
        usage = ApiUsage(
            api_key_id=api_key_id,
            endpoint=endpoint,
            status_code=status_code,
            response_time_ms=response_time_ms,
        )
        db.add(usage)
        # Update last_used_at and monthly counter on the key
        await db.execute(
            update(ApiKey)
            .where(ApiKey.id == api_key_id)
            .values(
                last_used_at=datetime.now(timezone.utc),
                calls_this_month=ApiKey.calls_this_month + 1,
            )
        )
    except Exception as e:
        logger.warning(f"Usage logging failed: {e}")


def _build_meta(request_id: str | None = None) -> dict:
    """Standard meta block for API responses."""
    return {
        "request_id": request_id or f"req_{uuid_mod.uuid4().hex[:12]}",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "version": "1.0",
    }


def api_error_response(code: str, message: str, status: int = 400, retry_after: int | None = None):
    """Build a standard API error response and raise HTTPException."""
    body = {
        "error": {
            "code": code,
            "message": message,
        },
        "meta": _build_meta(),
    }
    if retry_after:
        body["error"]["retry_after"] = retry_after
    raise HTTPException(status_code=status, detail=body)


async def require_api_key(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> ApiKey:
    """FastAPI dependency: validate API key, check rate limit & quota.

    Sets rate limit headers on the response via request.state.
    """
    # Extract key from header or query param
    raw_key = request.headers.get("X-API-Key") or request.query_params.get("key")
    if not raw_key:
        api_error_response(
            "AUTHENTICATION_REQUIRED",
            "API key required. Pass via X-API-Key header or ?key= query param.",
            status=401,
        )

    api_key = await _lookup_api_key(raw_key, db)
    if not api_key:
        api_error_response("INVALID_API_KEY", "API key is invalid or has been revoked.", status=401)

    # Check expiry
    if api_key.expires_at and api_key.expires_at < datetime.now(timezone.utc):
        api_error_response("API_KEY_EXPIRED", "This API key has expired.", status=401)

    # Check monthly quota (skip for test keys)
    if api_key.environment == "live" and api_key.calls_this_month >= api_key.monthly_quota:
        api_error_response(
            "QUOTA_EXCEEDED",
            f"Monthly quota of {api_key.monthly_quota:,} calls exceeded. Upgrade at https://plansearch.cc/pricing",
            status=429,
        )

    # Check rate limit
    allowed, limit, remaining, reset_ts = await _check_rate_limit(api_key)
    if not allowed:
        api_error_response(
            "RATE_LIMIT_EXCEEDED",
            f"Rate limit of {limit}/min exceeded.",
            status=429,
            retry_after=60,
        )

    # Stash rate limit info for response headers
    request.state.api_key = api_key
    request.state.rate_limit = limit
    request.state.rate_remaining = remaining
    request.state.rate_reset = reset_ts
    request.state.request_id = f"req_{uuid_mod.uuid4().hex[:12]}"
    request.state.request_start = time.time()

    return api_key


def add_rate_limit_headers(response: Response, request: Request):
    """Add rate limit headers to an API response."""
    if hasattr(request.state, "rate_limit"):
        response.headers["X-RateLimit-Limit"] = str(request.state.rate_limit)
        response.headers["X-RateLimit-Remaining"] = str(request.state.rate_remaining)
        response.headers["X-RateLimit-Reset"] = str(request.state.rate_reset)


def wrap_response(data: dict | list, request: Request) -> dict:
    """Wrap data in the standard API envelope."""
    request_id = getattr(request.state, "request_id", None)
    return {
        "data": data,
        "meta": _build_meta(request_id),
    }
