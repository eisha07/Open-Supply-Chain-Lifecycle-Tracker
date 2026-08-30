"""
Actor registration and management endpoints.

POST /actors          — Register a new supply-chain participant (returns DID + keypair)
GET  /actors/{did}    — Lookup actor by DID (authenticated)
POST /actors/{did}/blacklist — Revoke an actor (admin only — role check omitted for MVP)
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.actor import Actor
from app.schemas.actor import ActorCreate, ActorKeypairOut, ActorRead
from app.services.crypto import (
    generate_keypair,
    private_key_to_hex,
    public_key_to_did,
    public_key_to_hex,
)

router = APIRouter(prefix="/actors", tags=["Actors"])


@router.post("", response_model=ActorKeypairOut, status_code=status.HTTP_201_CREATED,
             summary="Register a new supply-chain actor")
async def register_actor(
    payload: ActorCreate,
    db: AsyncSession = Depends(get_db),
) -> ActorKeypairOut:
    """
    Generate an Ed25519 keypair, derive a did:key DID, and persist the actor.

    **The private key is returned exactly once.  It is never stored server-side.**
    The caller must persist it securely (e.g. hardware wallet, encrypted keystore).
    """
    private_key, public_key = generate_keypair()
    priv_hex = private_key_to_hex(private_key)
    pub_hex = public_key_to_hex(public_key)
    did = public_key_to_did(public_key)

    # Guard against DID collision (astronomically unlikely but defensive)
    existing = await db.get(Actor, did)
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT,
                            detail="DID collision — retry registration")

    actor = Actor(
        did=did,
        display_name=payload.display_name,
        role=payload.role,
        public_key_hex=pub_hex,
    )
    db.add(actor)
    await db.flush()

    return ActorKeypairOut(
        actor=ActorRead.model_validate(actor),
        private_key_hex=priv_hex,
        public_key_hex=pub_hex,
        did=did,
    )


@router.get("/{did}", response_model=ActorRead, summary="Lookup actor by DID")
async def get_actor(
    did: str,
    db: AsyncSession = Depends(get_db),
) -> ActorRead:
    actor = await db.get(Actor, did)
    if not actor:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail=f"Actor {did!r} not found")
    return ActorRead.model_validate(actor)


@router.post("/{did}/blacklist", response_model=ActorRead,
             summary="Revoke / blacklist an actor")
async def blacklist_actor(
    did: str,
    db: AsyncSession = Depends(get_db),
) -> ActorRead:
    """Mark an actor as blacklisted.  All future event submissions from this DID
    will be hard-rejected."""
    actor = await db.get(Actor, did)
    if not actor:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail=f"Actor {did!r} not found")
    actor.is_blacklisted = True
    await db.flush()
    return ActorRead.model_validate(actor)
