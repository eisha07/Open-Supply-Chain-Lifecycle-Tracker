"""
Actor registration and management endpoints.

POST /actors                  — Register a new supply-chain participant
GET  /actors                  — List all actors (paginated)
GET  /actors/{did}            — Lookup actor by DID
POST /actors/{did}/blacklist  — Revoke an actor (requires X-Admin-Secret header)
"""
from __future__ import annotations

import logging
from typing import List, Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.database import get_db
from app.models.actor import Actor, ActorRole
from app.schemas.actor import ActorCreate, ActorKeypairOut, ActorRead
from app.services.crypto import (
    generate_keypair,
    private_key_to_hex,
    public_key_to_did,
    public_key_to_hex,
)

settings = get_settings()
logger = logging.getLogger(__name__)
router = APIRouter(prefix="/actors", tags=["Actors"])


def _require_admin(x_admin_secret: Optional[str] = Header(None)) -> None:
    """Dependency: reject requests without the correct admin secret header."""
    if not x_admin_secret or x_admin_secret != settings.ADMIN_SECRET:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Valid X-Admin-Secret header required for this operation",
        )


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

    logger.info("ACTOR: Registered %s (role=%s, did=%s)", payload.display_name, payload.role.value, did)
    return ActorKeypairOut(
        actor=ActorRead.model_validate(actor),
        private_key_hex=priv_hex,
        public_key_hex=pub_hex,
        did=did,
    )


@router.get("", response_model=List[ActorRead], summary="List all registered actors")
async def list_actors(
    role: Optional[ActorRole] = Query(None, description="Filter by role"),
    is_blacklisted: Optional[bool] = Query(None, description="Filter by blacklist status"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
) -> List[ActorRead]:
    """List all registered supply-chain actors with optional filtering."""
    q = select(Actor)
    if role is not None:
        q = q.where(Actor.role == role)
    if is_blacklisted is not None:
        q = q.where(Actor.is_blacklisted == is_blacklisted)
    q = q.order_by(Actor.created_at.desc()).limit(limit).offset(offset)
    result = await db.execute(q)
    return [ActorRead.model_validate(a) for a in result.scalars().all()]


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
             summary="Revoke / blacklist an actor (admin only)",
             dependencies=[Depends(_require_admin)])
async def blacklist_actor(
    did: str,
    db: AsyncSession = Depends(get_db),
) -> ActorRead:
    """
    Mark an actor as blacklisted.  All future event submissions from this DID
    will be hard-rejected.

    Requires the `X-Admin-Secret` header to match the server-side ADMIN_SECRET.
    """
    actor = await db.get(Actor, did)
    if not actor:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail=f"Actor {did!r} not found")
    actor.is_blacklisted = True
    await db.flush()
    logger.warning("SECURITY: Actor %s has been blacklisted", did)
    return ActorRead.model_validate(actor)
