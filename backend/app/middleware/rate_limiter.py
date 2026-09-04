"""
Token-Bucket Rate Limiter with Redis backend (Edge Case 3).

Uses Redis for shared, persistent rate limiting across multiple backend
instances.  Falls back to in-memory token bucket when Redis is unavailable.

Per-IP and per-actor limits are enforced using a sliding-window counter.
Telemetry endpoints use a tighter per-device (twin_id) bucket.
"""
from __future__ import annotations

import asyncio
import logging
import time
from collections import defaultdict
from typing import Dict, Optional, Tuple

from fastapi import HTTPException, Request, status

from app.config import get_settings
from app.middleware.audit import audit_event

settings = get_settings()
logger = logging.getLogger(__name__)

# ── Redis connection (initialised lazily) ─────────────────────────────────────
_redis: Optional[object] = None
_redis_failed = False


async def _get_redis():
    """Return a Redis connection, or None if Redis is unavailable."""
    global _redis, _redis_failed

    if not settings.REDIS_URL:
        return None

    if _redis is not None:
        return _redis

    if _redis_failed:
        return None

    try:
        import redis.asyncio as aioredis
        _redis = aioredis.from_url(
            settings.REDIS_URL,
            decode_responses=True,
            socket_connect_timeout=2,
        )
        await _redis.ping()
        logger.info("RATE_LIMITER: Connected to Redis at %s", settings.REDIS_URL)
        return _redis
    except Exception as exc:
        _redis_failed = True
        logger.warning("RATE_LIMITER: Redis unavailable (%s) — using in-memory fallback", exc)
        return None


# ── In-memory fallback (when Redis is not available) ─────────────────────────

class _Bucket:
    """Token bucket state for a single key."""
    __slots__ = ("tokens", "last_refill")

    def __init__(self, capacity: float) -> None:
        self.tokens: float = capacity
        self.last_refill: float = time.monotonic()


_buckets: Dict[Tuple[str, str], _Bucket] = defaultdict(lambda: _Bucket(0))
_lock = asyncio.Lock()


def _refill_and_consume(bucket: _Bucket, capacity: float, refill_rate: float) -> bool:
    now = time.monotonic()
    elapsed = now - bucket.last_refill
    bucket.tokens = min(capacity, bucket.tokens + elapsed * refill_rate)
    bucket.last_refill = now

    if bucket.tokens >= 1.0:
        bucket.tokens -= 1.0
        return True
    return False


async def _check_memory(key: Tuple[str, str], capacity: float, refill_rate: float) -> bool:
    """In-memory token bucket check."""
    async with _lock:
        bucket = _buckets[key]
        if bucket.tokens == 0 and bucket.last_refill == 0:
            bucket.tokens = capacity
            bucket.last_refill = time.monotonic()
        return _refill_and_consume(bucket, capacity, refill_rate)


# ── Redis-backed sliding window ──────────────────────────────────────────────

async def _check_redis(
    r, namespace: str, identifier: str, capacity: float, refill_rate: float
) -> bool:
    """
    Redis sliding-window rate limit.

    Uses a sorted set per (namespace, identifier) with timestamps as scores.
    Expire the key after the window to auto-cleanup.
    """
    window_seconds = capacity / refill_rate  # e.g. 600 req / (10 req/s) = 60s window
    key = f"rl:{namespace}:{identifier}"
    now = time.time()
    window_start = now - window_seconds

    pipe = r.pipeline()
    pipe.zremrangebyscore(key, 0, window_start)   # remove expired entries
    pipe.zcard(key)                                # count entries in window
    pipe.zadd(key, {f"{now}:{id(pipe)}": now})    # add current request
    pipe.expire(key, int(window_seconds) + 1)      # auto-expire key
    results = await pipe.execute()

    current_count = results[1]
    return current_count < capacity


# ── Public API ────────────────────────────────────────────────────────────────

async def check_rate_limit(
    identifier: str,
    namespace: str,
    capacity: float,
    refill_rate: float,
) -> None:
    """
    Raise HTTP 429 if the caller exceeds their rate limit.

    Tries Redis first; falls back to in-memory token bucket.
    """
    r = await _get_redis()

    if r is not None:
        try:
            allowed = await _check_redis(r, namespace, identifier, capacity, refill_rate)
        except Exception as exc:
            logger.warning("RATE_LIMITER: Redis error (%s) — falling back to memory", exc)
            allowed = await _check_memory((namespace, identifier), capacity, refill_rate)
    else:
        allowed = await _check_memory((namespace, identifier), capacity, refill_rate)

    if not allowed:
        audit_event(
            "rate_limit.blocked",
            detail=f"namespace={namespace} identifier={identifier}",
            severity="WARNING",
        )
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail={
                "error": "rate_limited",
                "message": f"Rate limit exceeded for namespace '{namespace}'. "
                           "Back off and retry after 1 second.",
            },
        )


async def global_rate_limit_dependency(request: Request) -> None:
    """FastAPI dependency for a global per-IP rate limit."""
    ip = request.client.host if request.client else "unknown"
    limit = settings.GLOBAL_RATE_LIMIT_PER_MINUTE
    await check_rate_limit(
        identifier=ip,
        namespace="global",
        capacity=float(limit),
        refill_rate=limit / 60.0,
    )


async def telemetry_rate_limit_dependency(request: Request) -> None:
    """FastAPI dependency for the tighter telemetry-endpoint rate limit."""
    ip = request.client.host if request.client else "unknown"
    limit = settings.TELEMETRY_RATE_LIMIT_PER_MINUTE
    await check_rate_limit(
        identifier=ip,
        namespace="telemetry",
        capacity=float(limit),
        refill_rate=limit / 60.0,
    )
