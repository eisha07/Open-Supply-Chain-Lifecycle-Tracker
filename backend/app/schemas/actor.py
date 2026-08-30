"""Pydantic schemas for Actor (supply-chain participant)."""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from app.models.actor import ActorRole


class ActorCreate(BaseModel):
    """Payload to register a new actor.  The server generates the DID + keypair."""
    display_name: str = Field(..., min_length=1, max_length=128)
    role: ActorRole


class ActorRead(BaseModel):
    """Actor representation returned to authenticated callers."""
    model_config = {"from_attributes": True}

    did: str
    display_name: str
    role: ActorRole
    is_blacklisted: bool
    created_at: datetime


class ActorKeypairOut(BaseModel):
    """
    Returned ONCE at actor registration — the private key is never persisted
    server-side.  The caller must store it securely.
    """
    actor: ActorRead
    private_key_hex: str = Field(
        ..., description="Hex-encoded Ed25519 private key — store securely, never re-transmitted"
    )
    public_key_hex: str
    did: str
