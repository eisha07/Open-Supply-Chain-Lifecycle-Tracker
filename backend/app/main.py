"""
Open Supply-Chain Lifecycle Tracker — FastAPI application entry-point.

Run locally:
  uvicorn app.main:app --reload --port 8000

Swagger UI available at: http://localhost:8000/docs
ReDoc available at:       http://localhost:8000/redoc
"""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.database import engine, Base
from app.middleware.rate_limiter import global_rate_limit_dependency
from app.routers import actors, auth, events, passport, serials, telemetry_ws, twins

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s — %(message)s",
)

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Create all tables on startup (development only — use Alembic in production)."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    await engine.dispose()


app = FastAPI(
    title="Open Supply-Chain Lifecycle Tracker",
    description=(
        "A Digital Product Passport system aligned with EU DPP / ESPR standards.  "
        "Creates verifiable Digital Twins for physical products and tracks their state "
        "across a multi-party supply chain via an append-only cryptographic event ledger."
    ),
    version="1.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# ── CORS ──────────────────────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

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
    return {"status": "ok", "version": "1.1.0"}
