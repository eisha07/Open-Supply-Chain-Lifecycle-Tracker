"""
Open Supply-Chain Lifecycle Tracker — FastAPI application entry-point.

Run locally:
  uvicorn app.main:app --reload --port 8000

Swagger UI available at: http://localhost:8000/docs
ReDoc available at:       http://localhost:8000/redoc
"""
from __future__ import annotations

import logging
import time
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.database import engine, Base
from app.middleware.audit import AuditMiddleware
from app.middleware.rate_limiter import global_rate_limit_dependency
from app.routers import actors, auth, events, passport, serials, telemetry_ws, twins

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s — %(message)s",
)

settings = get_settings()

# Track startup time for health monitoring
_startup_time: float = 0.0


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """
    Startup / shutdown lifecycle:
      1. Validate database connectivity
      2. Create tables (dev) or run migrations (prod)
      3. Pre-warm Redis connection for caching + rate limiting
      4. Gracefully close Redis on shutdown
    """
    global _startup_time
    _startup_time = time.monotonic()

    # ── Step 1: Validate database connectivity ───────────────────────────────
    try:
        from sqlalchemy import text
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        logging.getLogger(__name__).info("LIFESPAN: Database connection validated")
    except Exception as exc:
        logging.getLogger(__name__).error("LIFESPAN: Database connection failed: %s", exc)
        # Don't raise — allow the app to start even if DB is temporarily down

    # ── Step 2: Create tables (dev only — use Alembic in production) ────────
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # ── Step 3: Pre-warm Redis connection ────────────────────────────────────
    try:
        from app.cache import get_redis
        r = await get_redis()
        if r:
            logging.getLogger(__name__).info("LIFESPAN: Redis pre-warmed for caching + rate limiting")
        else:
            logging.getLogger(__name__).info("LIFESPAN: Redis not configured — using in-memory fallback")
    except Exception as exc:
        logging.getLogger(__name__).warning("LIFESPAN: Redis pre-warm failed: %s", exc)

    yield

    # ── Shutdown: close Redis and DB connections ─────────────────────────────
    try:
        from app.cache import close_redis
        await close_redis()
    except Exception:
        pass
    await engine.dispose()


app = FastAPI(
    title="Open Supply-Chain Lifecycle Tracker",
    description=(
        "A Digital Product Passport system aligned with EU DPP / ESPR standards.  "
        "Creates verifiable Digital Twins for physical products and tracks their state "
        "across a multi-party supply chain via an append-only cryptographic event ledger."
    ),
    version="1.2.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# ── Middleware (added in reverse execution order: last added = first to run) ──
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(AuditMiddleware)  # outermost: logs every request

# ── Routers ───────────────────────────────────────────────────────────────────
app.include_router(auth.router)                 # /auth — no global rate limit (low traffic)
app.include_router(actors.router,       dependencies=[Depends(global_rate_limit_dependency)])
app.include_router(twins.router,        dependencies=[Depends(global_rate_limit_dependency)])
app.include_router(events.router,       dependencies=[Depends(global_rate_limit_dependency)])
app.include_router(serials.router,      dependencies=[Depends(global_rate_limit_dependency)])
app.include_router(passport.router)     # Public — no rate-limit dependency
app.include_router(telemetry_ws.router) # Has its own rate-limit for /batch


@app.get("/health", tags=["System"], summary="Health check")
async def health() -> dict:
    uptime = round(time.monotonic() - _startup_time, 1) if _startup_time else 0

    # Check Redis status
    redis_ok = False
    try:
        from app.cache import get_redis
        r = await get_redis()
        if r:
            await r.ping()
            redis_ok = True
    except Exception:
        pass

    # Check WebSocket connections
    from app.routers.telemetry_ws import get_active_connection_count
    ws_connections = get_active_connection_count()

    return {
        "status": "ok",
        "version": "1.2.0",
        "uptime_seconds": uptime,
        "redis": "connected" if redis_ok else "unavailable",
        "websocket_connections": ws_connections,
        "cache_enabled": redis_ok,
    }
