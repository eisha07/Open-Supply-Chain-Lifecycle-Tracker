"""Application settings loaded from environment / .env file."""
from __future__ import annotations

import json
from functools import lru_cache
from typing import Any, List

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    # ── Database ─────────────────────────────────────────────────────────────
    DATABASE_URL: str = "postgresql+asyncpg://oslt_user:oslt_pass@localhost:5432/oslt_db"
    SYNC_DATABASE_URL: str = "postgresql://oslt_user:oslt_pass@localhost:5432/oslt_db"

    # ── Application ──────────────────────────────────────────────────────────
    APP_ENV: str = "development"
    SECRET_KEY: str = "dev-secret-change-me"

    # CORS origins — accepts JSON array OR comma-separated string
    CORS_ORIGINS: List[str] = ["http://localhost:3000", "http://127.0.0.1:3000"]

    # ── Rate Limiting ─────────────────────────────────────────────────────────
    TELEMETRY_RATE_LIMIT_PER_MINUTE: int = 120
    GLOBAL_RATE_LIMIT_PER_MINUTE: int = 600

    # ── JWT / Auth ────────────────────────────────────────────────────────────
    JWT_SECRET_KEY: str = "jwt-secret-change-in-production"
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_MINUTES: int = 1440  # 24 hours

    # Shared secret required for admin operations (blacklist, serial management)
    ADMIN_SECRET: str = "admin-secret-change-in-production"

    # ── Crypto ────────────────────────────────────────────────────────────────
    SIGNATURE_MAX_AGE_SECONDS: int = 300

    # ── Redis (rate limiter backend) ──────────────────────────────────────────
    REDIS_URL: str = ""  # Empty = fall back to in-memory rate limiter

    # ── API Key (HMAC request signing for read endpoints) ────────────────────
    API_KEY: str = ""  # Empty = disable API key auth (JWT only)
    API_KEY_HEADER: str = "X-API-Key"
    API_KEY_MAX_AGE_SECONDS: int = 300  # Max age for signed requests

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def parse_cors(cls, v: Any) -> List[str]:
        if isinstance(v, list):
            return v
        if isinstance(v, str):
            s = v.strip()
            # Try JSON array first: '["http://...", "http://..."]'
            if s.startswith("["):
                try:
                    parsed = json.loads(s)
                    if isinstance(parsed, list):
                        return [str(o).strip() for o in parsed]
                except json.JSONDecodeError:
                    pass
            # Fall back to comma-separated string
            return [origin.strip() for origin in s.split(",") if origin.strip()]
        return v


@lru_cache
def get_settings() -> Settings:
    return Settings()
