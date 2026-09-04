"""
HMAC-SHA256 API key authentication for read endpoints.

Supports two modes:
  1. Simple API key: client sends `X-API-Key: <key>` header only.
  2. HMAC-signed request: client sends `X-API-Key` + `X-Signature` +
     `X-Timestamp` headers. The signature is HMAC-SHA256(method + path + timestamp)
     keyed by the shared API_KEY.  This prevents replay and tampering.

When API_KEY is empty in settings, this dependency is a no-op (always passes).

Usage:
    from app.api_key import require_api_key

    @router.get("/events/{twin_id}", dependencies=[Depends(require_api_key)])
    async def list_events(twin_id: str): ...
"""
from __future__ import annotations

import hashlib
import hmac
import logging
import time
from typing import Optional

from fastapi import Header, HTTPException, Request, status

from app.config import get_settings
from app.middleware.audit import audit_event

logger = logging.getLogger(__name__)
settings = get_settings()

# Maximum clock skew tolerance for signed requests (seconds)
_MAX_SKEW = 300  # 5 minutes


def _expected_signature(method: str, path: str, timestamp: str, key: str) -> str:
    """Compute HMAC-SHA256(method + path + timestamp, key)."""
    message = f"{method.upper()}{path}{timestamp}"
    return hmac.new(
        key.encode("utf-8"),
        message.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


async def require_api_key(
    request: Request,
    x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
    x_signature: Optional[str] = Header(None, alias="X-Signature"),
    x_timestamp: Optional[str] = Header(None, alias="X-Timestamp"),
) -> None:
    """
    FastAPI dependency that validates an API key header.

    If settings.API_KEY is empty, this is a no-op (auth disabled).
    If API_KEY is set, the request must present the correct key.
    If X-Signature and X-Timestamp are also present, validates HMAC-SHA256.
    """
    # No API key configured — skip check entirely
    if not settings.API_KEY:
        return

    # API key required but not provided
    if not x_api_key:
        audit_event(
            "apikey.missing",
            detail="Request missing X-API-Key header",
            severity="WARNING",
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing X-API-Key header",
        )

    # Constant-time comparison of the API key
    if not hmac.compare_digest(x_api_key, settings.API_KEY):
        audit_event(
            "apikey.invalid",
            detail="Invalid API key presented",
            severity="WARNING",
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key",
        )

    # If signature headers are present, validate HMAC for tamper protection
    if x_signature and x_timestamp:
        try:
            ts = int(x_timestamp)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="X-Timestamp must be a Unix epoch integer",
            )

        # Check timestamp freshness (±5 minutes)
        now = int(time.time())
        if abs(now - ts) > _MAX_SKEW:
            audit_event(
                "apikey.replay",
                detail=f"Timestamp {ts} outside ±{_MAX_SKEW}s window",
                severity="WARNING",
            )
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Request timestamp expired — resend with a fresh timestamp",
            )

        expected = _expected_signature(
            method=request.method,
            path=request.url.path,
            timestamp=x_timestamp,
            key=settings.API_KEY,
        )
        if not hmac.compare_digest(x_signature, expected):
            audit_event(
                "apikey.bad_signature",
                detail=f"HMAC mismatch for {request.method} {request.url.path}",
                severity="WARNING",
            )
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="HMAC signature verification failed",
            )

    # Valid API key (with or without HMAC)
    audit_event("apikey.valid", detail=f"API key auth passed for {request.url.path}")
