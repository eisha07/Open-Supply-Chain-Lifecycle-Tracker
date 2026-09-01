"""Pydantic schemas for authentication endpoints."""
from __future__ import annotations

from pydantic import BaseModel, Field

from app.schemas.actor import ActorRead


class ChallengeResponse(BaseModel):
    """Nonce returned to the client for signing."""
    challenge: str = Field(..., description="Hex-encoded 32-byte one-time nonce")
    actor_did: str
    expires_in_seconds: int = 120


class TokenRequest(BaseModel):
    """Payload to exchange a signed challenge for a JWT."""
    actor_did: str
    challenge: str = Field(..., description="The nonce received from GET /auth/challenge")
    signature: str = Field(
        ...,
        description="Base64url-encoded Ed25519 signature of the challenge bytes "
                    "produced with the actor's private key",
    )


class TokenResponse(BaseModel):
    """JWT access token returned after successful authentication."""
    access_token: str
    token_type: str = "bearer"
    expires_in_seconds: int
    actor: ActorRead
