"""
Shared Redis cache for the application.

Provides:
  - A single, lazily-initialized async Redis connection (reused by rate limiter + caching)
  - JSON cache helpers: cache_get / cache_set / cache_delete with TTL
  - Cache-key builders for common resources (twins, passports, events)

When REDIS_URL is empty, all cache operations are silent no-ops.
"""
from __future__ import annotations

import hashlib
import json
import logging
from typing import Any, Optional

from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

# ── Shared Redis connection (lazily initialized) ─────────────────────────────
_redis: Optional[object] = None
_redis_failed: bool = False


async def get_redis():
    """
    Return a shared async Redis connection, or None if Redis is unavailable.

    Reuses a single connection across rate limiting and caching.
    """
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
            max_connections=20,        # connection pool
            socket_keepalive=True,
        )
        await _redis.ping()
        logger.info("CACHE: Connected to Redis at %s (pool=20)", settings.REDIS_URL)
        return _redis
    except Exception as exc:
        _redis_failed = True
        logger.warning("CACHE: Redis unavailable (%s) — caching disabled", exc)
        return None


async def close_redis() -> None:
    """Close the shared Redis connection gracefully."""
    global _redis
    if _redis is not None:
        try:
            await _redis.close()  # type: ignore[union-attr]
        except Exception:
            pass
        _redis = None


# ── JSON cache helpers ───────────────────────────────────────────────────────

async def cache_get(key: str) -> Optional[Any]:
    """Retrieve a JSON-deserialized value from cache, or None."""
    r = await get_redis()
    if r is None:
        return None
    try:
        raw = await r.get(key)  # type: ignore[union-attr]
        if raw is not None:
            return json.loads(raw)
    except Exception:
        pass
    return None


async def cache_set(key: str, value: Any, ttl: int = 60) -> None:
    """Store a JSON-serializable value in cache with TTL (seconds)."""
    r = await get_redis()
    if r is None:
        return
    try:
        await r.set(key, json.dumps(value, default=str), ex=ttl)  # type: ignore[union-attr]
    except Exception:
        pass


async def cache_delete(key: str) -> None:
    """Remove a key from cache (invalidation)."""
    r = await get_redis()
    if r is None:
        return
    try:
        await r.delete(key)  # type: ignore[union-attr]
    except Exception:
        pass


async def cache_delete_pattern(pattern: str) -> None:
    """Delete all keys matching a glob pattern (use sparingly — O(N) scan)."""
    r = await get_redis()
    if r is None:
        return
    try:
        cursor = 0
        while True:
            cursor, keys = await r.scan(cursor, match=pattern, count=100)  # type: ignore[union-attr]
            if keys:
                await r.delete(*keys)  # type: ignore[union-attr]
            if cursor == 0:
                break
    except Exception:
        pass


# ── Cache key builders ──────────────────────────────────────────────────────

def twin_key(twin_id: str) -> str:
    """Cache key for a single twin read."""
    safe = twin_id.replace(":", "_")[:80]
    return f"cache:twin:{safe}"


def passport_key(twin_id: str) -> str:
    """Cache key for public passport data."""
    safe = twin_id.replace(":", "_")[:80]
    return f"cache:passport:{safe}"


def passport_timeline_key(twin_id: str, limit: int, offset: int, event_type: Optional[str]) -> str:
    """Cache key for paginated passport timeline."""
    safe = twin_id.replace(":", "_")[:80]
    et = event_type or "all"
    return f"cache:passport_timeline:{safe}:{limit}:{offset}:{et}"


def events_key(twin_id: str, limit: int, offset: int, event_type: Optional[str]) -> str:
    """Cache key for event listing."""
    safe = twin_id.replace(":", "_")[:80]
    et = event_type or "all"
    return f"cache:events:{safe}:{limit}:{offset}:{et}"


def qr_key(twin_id: str, base_url: str) -> str:
    """Cache key for a QR code PNG."""
    h = hashlib.sha256(f"{twin_id}:{base_url}".encode()).hexdigest()[:16]
    return f"cache:qr:{h}"


# ── Invalidation helpers ────────────────────────────────────────────────────

async def invalidate_twin(twin_id: str) -> None:
    """Invalidate all cached data for a specific twin (call after mutations)."""
    safe = twin_id.replace(":", "_")[:80]
    await cache_delete_pattern(f"cache:twin:{safe}")
    await cache_delete_pattern(f"cache:passport:{safe}")
    await cache_delete_pattern(f"cache:passport_timeline:{safe}:*")
    await cache_delete_pattern(f"cache:events:{safe}:*")
    await cache_delete_pattern(f"cache:qr:*")  # QR codes depend on twin_id indirectly


async def invalidate_events(twin_id: str) -> None:
    """Invalidate event-related caches for a twin."""
    safe = twin_id.replace(":", "_")[:80]
    await cache_delete_pattern(f"cache:events:{safe}:*")
    await cache_delete_pattern(f"cache:passport_timeline:{safe}:*")
    await cache_delete(twin_key(twin_id))
    await cache_delete(passport_key(twin_id))
