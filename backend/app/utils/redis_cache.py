"""PlanSearch — Redis caching utility for analytics endpoints.

Provides a simple async cache-or-compute pattern:
    data = await cached("analytics:pipeline-gap", 3600, compute_fn, db)

Serialises results as JSON in Redis. Falls back to compute if Redis
is unavailable so the page always works.
"""

import json
import logging
from typing import Any, Callable, Awaitable

import redis.asyncio as aioredis

from app.config import get_settings

logger = logging.getLogger(__name__)

_redis_pool: aioredis.Redis | None = None


async def get_redis() -> aioredis.Redis:
    """Get or create a Redis connection pool."""
    global _redis_pool
    if _redis_pool is None:
        settings = get_settings()
        _redis_pool = aioredis.from_url(
            settings.redis_url, decode_responses=True
        )
    return _redis_pool


async def cached(
    key: str,
    ttl_seconds: int,
    compute_fn: Callable[..., Awaitable[Any]],
    *args,
    **kwargs,
) -> Any:
    """Return cached data if available, otherwise compute, cache, and return.

    Args:
        key: Redis cache key (e.g. "analytics:pipeline-gap")
        ttl_seconds: Cache TTL in seconds
        compute_fn: Async function to call if cache miss
        *args, **kwargs: Arguments passed to compute_fn
    """
    try:
        r = await get_redis()
        raw = await r.get(key)
        if raw is not None:
            logger.debug(f"Cache HIT: {key}")
            return json.loads(raw)
    except Exception as e:
        logger.warning(f"Redis cache read failed for {key}: {e}")

    # Cache miss or Redis unavailable — compute fresh
    logger.debug(f"Cache MISS: {key}")
    result = await compute_fn(*args, **kwargs)

    try:
        r = await get_redis()
        await r.set(key, json.dumps(result, default=str), ex=ttl_seconds)
    except Exception as e:
        logger.warning(f"Redis cache write failed for {key}: {e}")

    return result


async def invalidate(key: str):
    """Invalidate a specific cache key."""
    try:
        r = await get_redis()
        await r.delete(key)
    except Exception:
        pass
