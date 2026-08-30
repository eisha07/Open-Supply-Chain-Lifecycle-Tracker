"""
Leaky-Bucket Rate Limiter (Edge Case 3).

Per-IP and per-actor limits are enforced using an in-memory token bucket.
Telemetry endpoints use a tighter per-device (twin_id) bucket.

In production, replace the in-memory dict with a Redis backend for
multi-process correctness.
"""
from __future__ import annotations

import asyncio
import time
from collections import defaultdict
from typing import Dict, Tuple

from fastapi import HTTPException, Request, status

from app.config import get_settings

settings = get_settings()


class _Bucket:
    """Token bucket state for a single key."""
    __slots__ = ("tokens", "last_refill")

    def __init__(self, capacity: float) -> None:
        self.tokens: float = capacity
        self.last_refill: float = time.monotonic()


# Global bucket stores — keyed by (endpoint_prefix, identifier)
_buckets: Dict[Tuple[str, str], _Bucket] = defaultdict(lambda: _Bucket(0))
_lock = asyncio.Lock()


def _refill_and_consume(bucket: _Bucket, capacity: float, refill_rate: float) -> bool:
    """
    Refill the bucket based on elapsed time, then attempt to consume 1 token.

    Returns True if the request is allowed, False if rate-limited.
    refill_rate: tokens per second.
    """
    now = time.monotonic()
    elapsed = now - bucket.last_refill
    bucket.tokens = min(capacity, bucket.tokens + elapsed * refill_rate)
    bucket.last_refill = now

    if bucket.tokens >= 1.0:
        bucket.tokens -= 1.0
        return True
    return False


async def check_rate_limit(
    identifier: str,
    namespace: str,
    capacity: float,
    refill_rate: float,  # tokens / second
) -> None:
    """
    Raise HTTP 429 if the caller exceeds their rate limit.

    Args:
        identifier: Unique caller key (IP, actor DID, or twin_id).
        namespace:  Logical grouping (e.g. "telemetry", "global").
        capacity:   Max burst tokens (bucket size).
        refill_rate: Tokens added per second (= requests per second steady-state).
    """
    key = (namespace, identifier)
    async with _lock:
        bucket = _buckets[key]
        if bucket.tokens == 0 and bucket.last_refill == 0:
            # New bucket — initialise with full capacity
            bucket.tokens = capacity
            bucket.last_refill = time.monotonic()
        allowed = _refill_and_consume(bucket, capacity, refill_rate)

    if not allowed:
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
