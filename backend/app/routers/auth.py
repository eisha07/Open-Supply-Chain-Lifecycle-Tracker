"""
DID-based authentication endpoints.

GET  /auth/challenge   — Generate a one-time nonce for an actor to sign
POST /auth/token       — Exchange a signed challenge for a JWT access token
GET  /auth/me          — Decode and return the current token's actor info
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Header, status
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional

from app.config import get_settings
from app.database import get_db
from app.models.actor import Actor
from app.schemas.actor import ActorRead
from app.schemas.auth import ChallengeResponse, TokenRequest, TokenResponse
from app.services.auth import (
    create_access_token,
    decode_access_token,
    generate_challenge,
    consume_challenge,
)
from app.services.crypto import verify_signature

settings = get_settings()
router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.get("/challenge", response_model=ChallengeResponse,
            summary="Request a one-time challenge nonce")
async def get_challenge(
    actor_did: str,
    db: AsyncSession = Depends(get_db),
) -> ChallengeResponse:
    """
    Returns a one-time nonce that the actor must sign with their Ed25519 private key
    before calling POST /auth/token.

    The nonce expires after 120 seconds.
    """
    actor = await db.get(Actor, actor_did)
    if not actor:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail=f"Actor {actor_did!r} not registered")
    if actor.is_blacklisted:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                            detail="Actor is blacklisted")

    nonce = generate_challenge(actor_did)
    return ChallengeResponse(challenge=nonce, actor_did=actor_did, expires_in_seconds=120)


@router.post("/token", response_model=TokenResponse,
             summary="Exchange a signed challenge for a JWT access token")
async def get_token(
    payload: TokenRequest,
    db: AsyncSession = Depends(get_db),
) -> TokenResponse:
    """
    Verifies the Ed25519 signature over the challenge nonce and — if valid —
    returns a signed JWT access token.

    The JWT payload contains: `sub` (actor DID), `role`, `iat`, `exp`.
    """
    actor: Actor | None = await db.get(Actor, payload.actor_did)
    if not actor:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail=f"Actor {payload.actor_did!r} not registered")
    if actor.is_blacklisted:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                            detail="Actor is blacklisted")

    # Validate + consume the challenge nonce
    if not consume_challenge(payload.challenge, payload.actor_did):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired challenge — call GET /auth/challenge to get a new one",
        )

    # Verify Ed25519 signature: actor signed the raw challenge bytes
    challenge_bytes = payload.challenge.encode("utf-8")
    if not verify_signature(challenge_bytes, payload.signature, actor.public_key_hex):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Cryptographic signature verification failed",
        )

    token = create_access_token(actor_did=actor.did, role=actor.role.value)
    return TokenResponse(
        access_token=token,
        token_type="bearer",
        expires_in_seconds=settings.JWT_EXPIRE_MINUTES * 60,
        actor=ActorRead.model_validate(actor),
    )


@router.get("/me", response_model=ActorRead, summary="Get current authenticated actor")
async def get_me(
    authorization: Optional[str] = Header(None),
    db: AsyncSession = Depends(get_db),
) -> ActorRead:
    """Return the actor associated with the supplied Bearer JWT."""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,
                            detail="Missing or invalid Authorization header")
    token = authorization.removeprefix("Bearer ")
    claims = decode_access_token(token)
    if not claims:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,
                            detail="Invalid or expired token")

    actor = await db.get(Actor, claims["sub"])
    if not actor:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail="Actor not found")
    return ActorRead.model_validate(actor)
