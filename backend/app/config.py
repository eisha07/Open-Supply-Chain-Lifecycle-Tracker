"""Application settings loaded from environment / .env file."""
from __future__ import annotations

from functools import lru_cache
from typing import List

from pydantic import AnyHttpUrl, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    # ── Database ─────────────────────────────────────────────────────────────
    DATABASE_URL: str = "postgresql+asyncpg://oslt_user:oslt_pass@localhost:5432/oslt_db"
    SYNC_DATABASE_URL: str = "postgresql://oslt_user:oslt_pass@localhost:5432/oslt_db"

    # ── Application ──────────────────────────────────────────────────────────
    APP_ENV: str = "development"
    SECRET_KEY: str = "dev-secret-change-me"
    CORS_ORIGINS: List[str] = ["http://localhost:3000", "http://127.0.0.1:3000"]

    # ── Rate Limiting ─────────────────────────────────────────────────────────
    TELEMETRY_RATE_LIMIT_PER_MINUTE: int = 120
    GLOBAL_RATE_LIMIT_PER_MINUTE: int = 600

    # ── Crypto ────────────────────────────────────────────────────────────────
    SIGNATURE_MAX_AGE_SECONDS: int = 300

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def parse_cors(cls, v: str | List[str]) -> List[str]:
        if isinstance(v, str):
            return [origin.strip() for origin in v.split(",")]
        return v


@lru_cache
def get_settings() -> Settings:
    return Settings()
