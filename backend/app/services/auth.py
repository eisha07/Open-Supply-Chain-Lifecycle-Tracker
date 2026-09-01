"""
JWT-based authentication service.

Flow:
  1. Client calls GET /auth/challenge?actor_did=<did>  → receives a one-time nonce.
  2. Client signs the nonce bytes with their Ed25519 private key.
  3. Client calls POST /auth/token with {actor_did, challenge, signature}.
  4. Server verifies the signature, issues a signed JWT.
  5. Protected endpoints require `Authorization: Bearer <jwt>`.
"""
from __future__ import annotations

import os
import secrets
import time
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from jose import JWTError, jwt

from app.config import get_settings

settings = get_settings()

# ── In-memory challenge store (nonce → (actor_did, expires_at)) ──────────────
# Each challenge expires after 120 seconds.
_CHALLENGE_TTL_SECONDS = 120
_challenges: Dict[str, tuple[str, float]] = {}


def generate_challenge(actor_did: str) -> str:
    """
    Create a one-time challenge nonce for a given actor DID.

    The nonce is stored in memory with a TTL.  Any previous challenge for
    the same DID is overwritten (one active challenge per DID at a time).
    """
    nonce = secrets.token_hex(32)
    expires_at = time.monotonic() + _CHALLENGE_TTL_SECONDS
    _challenges[nonce] = (actor_did, expires_at)
    return nonce


def consume_challenge(nonce: str, actor_did: str) -> bool:
    """
    Validate and consume a challenge nonce.

    Returns True if the nonce is valid, belongs to actor_did, and has not expired.
    Always removes the nonce from the store (one-time use).
    """
    entry = _challenges.pop(nonce, None)
    if entry is None:
        return False
    stored_did, expires_at = entry
    if time.monotonic() > expires_at:
        return False
    return stored_did == actor_did


# ── JWT creation & verification ───────────────────────────────────────────────

def create_access_token(actor_did: str, role: str) -> str:
    """Issue a signed JWT for the given actor."""
    now = int(time.time())
    payload = {
        "sub": actor_did,
        "role": role,
        "iat": now,
        "exp": now + (settings.JWT_EXPIRE_MINUTES * 60),
    }
    return jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def decode_access_token(token: str) -> Optional[Dict[str, Any]]:
    """
    Decode and verify a JWT.

    Returns the decoded payload dict on success, None if the token is
    invalid, expired, or tampered with.
    """
    try:
        return jwt.decode(
            token,
            settings.JWT_SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM],
        )
    except JWTError:
        return None
