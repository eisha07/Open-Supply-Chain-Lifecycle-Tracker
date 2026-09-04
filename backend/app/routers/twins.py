"""
Digital Twin CRUD endpoints.

POST /twins                       — Instantiate a new Digital Twin (Feature 1)
GET  /twins                       — List twins (filterable by product_type, status)
GET  /twins/{twin_id}             — Get full twin state (authenticated)
GET  /twins/{twin_id}/children    — List child twins (BOM view)
POST /twins/{twin_id}/zkp         — Generate ZKP flags (Feature 5)
GET  /twins/{twin_id}/second-life — Reuse estimator (Feature 6)
GET  /twins/{twin_id}/recycling   — Recycling matrix (Feature 7)
"""
from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.dependencies import optional_auth, AuthenticatedActor
from app.models.actor import Actor, ActorRole
from app.models.event import EventType, ProductEvent
from app.models.twin import ProductTwin, TwinStatus
from app.schemas.twin import (
    SecondLifeEstimate,
    TwinCreate,
    TwinRead,
    ZKPDisclosureRequest,
)
from app.services.recycling_matrix import generate_recycling_matrix
from app.services.second_life import estimate_second_life
from app.services.zkp import generate_zkp_flags

router = APIRouter(prefix="/twins", tags=["Digital Twins"])


# ── Helper ────────────────────────────────────────────────────────────────────

async def _require_actor(db: AsyncSession, actor_did: str) -> Actor:
    """Resolve an actor by DID; raise 404 / 403 on invalid / blacklisted."""
    actor = await db.get(Actor, actor_did)
    if not actor:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail=f"Actor {actor_did!r} not found")
    if actor.is_blacklisted:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                            detail="Actor is blacklisted and cannot perform this action")
    return actor


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.post("", response_model=TwinRead, status_code=status.HTTP_201_CREATED,
             summary="Instantiate a new Digital Twin")
async def create_twin(
    payload: TwinCreate,
    actor_did: str = Query(..., description="DID of the authenticated actor"),
    db: AsyncSession = Depends(get_db),
    auth_actor: Optional[AuthenticatedActor] = Depends(optional_auth),
) -> TwinRead:
    """
    Instantiate a Digital Twin with a unique did:key identifier.

    When a JWT Bearer token is provided, the token's subject must match
    the `actor_did` query parameter (anti-impersonation check).

    **Role restrictions:**
    - `RAW_MATERIAL_SUPPLIER`: may create material-batch twins.
    - `OEM_MANUFACTURER`: may create component / finished-product twins.
    """
    # JWT cross-check: prevent submitting on behalf of another actor
    if auth_actor and auth_actor.did != actor_did:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                            detail="JWT identity does not match the actor_did parameter")

    actor = await _require_actor(db, actor_did)

    if actor.role not in (ActorRole.RAW_MATERIAL_SUPPLIER, ActorRole.OEM_MANUFACTURER):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                            detail="Only suppliers and OEMs may create Digital Twins")

    # Validate parent exists if provided
    if payload.parent_twin_id:
        parent = await db.get(ProductTwin, payload.parent_twin_id)
        if not parent:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                                detail=f"Parent twin {payload.parent_twin_id!r} not found")

    # Generate a new DID for this twin using the actor's key as entropy seed
    from app.services.crypto import generate_keypair, public_key_to_did
    _, pub_key = generate_keypair()
    twin_did = public_key_to_did(pub_key)

    twin = ProductTwin(
        id=twin_did,
        name=payload.name,
        product_type=payload.product_type,
        parent_twin_id=payload.parent_twin_id,
        manufacturer_did=actor_did,
        manufacturing_date=payload.manufacturing_date,
        serial_number=payload.serial_number,
        material_weights_kg=payload.material_weights_kg,
        baseline_chemistry=payload.baseline_chemistry,
        initial_capacity_kwh=payload.initial_capacity_kwh,
        initial_safety_rating=payload.initial_safety_rating,
        current_capacity_kwh=payload.initial_capacity_kwh,
        current_soh_pct=100.0 if payload.initial_capacity_kwh else None,
        current_chemistry=payload.baseline_chemistry,
        current_safety_rating=payload.initial_safety_rating,
    )
    db.add(twin)
    await db.flush()
    return TwinRead.model_validate(twin)


@router.get("", response_model=List[TwinRead], summary="List Digital Twins")
async def list_twins(
    product_type: Optional[str] = Query(None),
    status_filter: Optional[TwinStatus] = Query(None, alias="status"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
) -> List[TwinRead]:
    q = select(ProductTwin)
    if product_type:
        q = q.where(ProductTwin.product_type == product_type)
    if status_filter:
        q = q.where(ProductTwin.status == status_filter)
    q = q.limit(limit).offset(offset)
    result = await db.execute(q)
    twins = result.scalars().all()
    return [TwinRead.model_validate(t) for t in twins]


@router.get("/{twin_id}", response_model=TwinRead, summary="Get a Digital Twin by ID")
async def get_twin(
    twin_id: str,
    db: AsyncSession = Depends(get_db),
) -> TwinRead:
    twin = await db.get(ProductTwin, twin_id)
    if not twin:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail=f"Twin {twin_id!r} not found")
    return TwinRead.model_validate(twin)


@router.get("/{twin_id}/children", response_model=List[TwinRead],
            summary="List child twins (BOM view)")
async def get_twin_children(
    twin_id: str,
    db: AsyncSession = Depends(get_db),
) -> List[TwinRead]:
    result = await db.execute(
        select(ProductTwin).where(ProductTwin.parent_twin_id == twin_id)
    )
    return [TwinRead.model_validate(t) for t in result.scalars().all()]


@router.post("/{twin_id}/zkp", summary="Generate selective ZKP disclosure flags (Feature 5)")
async def generate_zkp(
    twin_id: str,
    payload: ZKPDisclosureRequest,
    actor_did: str = Query(...),
    db: AsyncSession = Depends(get_db),
    auth_actor: Optional[AuthenticatedActor] = Depends(optional_auth),
) -> dict:
    # JWT cross-check
    if auth_actor and auth_actor.did != actor_did:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                            detail="JWT identity does not match the actor_did parameter")

    actor = await _require_actor(db, actor_did)
    if actor.role != ActorRole.OEM_MANUFACTURER:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                            detail="Only OEM Manufacturers may generate ZKP flags")

    twin = await db.get(ProductTwin, twin_id)
    if not twin:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail=f"Twin {twin_id!r} not found")

    raw_data = {
        **(twin.material_weights_kg or {}),
        **(twin.current_chemistry or {}),
        "manufacturer_did": twin.manufacturer_did,
    }
    flags = generate_zkp_flags(raw_data, payload.claims)

    # Persist flags to the twin
    twin.zkp_flags = flags
    await db.flush()
    return {"twin_id": twin_id, "zkp_flags": flags}


@router.get("/{twin_id}/second-life", response_model=SecondLifeEstimate,
            summary="Secondary-market reuse estimation (Feature 6)")
async def second_life_estimate(
    twin_id: str,
    db: AsyncSession = Depends(get_db),
) -> SecondLifeEstimate:
    twin = await db.get(ProductTwin, twin_id)
    if not twin:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail=f"Twin {twin_id!r} not found")

    # Count repair events
    result = await db.execute(
        select(ProductEvent).where(
            ProductEvent.twin_id == twin_id,
            ProductEvent.event_type == EventType.REPAIR_PART_SWAP,
        )
    )
    repair_count = len(result.scalars().all())
    tamper = twin.status == TwinStatus.TAMPERED_SAFETY_RISK

    return estimate_second_life(
        twin_id=twin_id,
        current_soh_pct=twin.current_soh_pct,
        repair_count=repair_count,
        tamper_alert=tamper,
        chemistry=twin.current_chemistry or {},
    )


@router.get("/{twin_id}/provenance-gaps", summary="Detailed provenance gap audit report")
async def provenance_gap_report(
    twin_id: str,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """
    Returns a detailed audit report of sequence gaps in the event ledger.

    A provenance gap means some events between two consecutive recorded
    sequence numbers are missing — indicating lost or unrecorded custody
    transfers in the supply chain.
    """
    twin = await db.get(ProductTwin, twin_id)
    if not twin:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail=f"Twin {twin_id!r} not found")

    result = await db.execute(
        select(ProductEvent)
        .where(ProductEvent.twin_id == twin_id)
        .order_by(ProductEvent.sequence_num)
    )
    events = list(result.scalars().all())

    gaps = []
    seen_sequences = [e.sequence_num for e in events]

    for i in range(len(seen_sequences) - 1):
        current = seen_sequences[i]
        nxt = seen_sequences[i + 1]
        if nxt != current + 1:
            missing_range = list(range(current + 1, nxt))
            gaps.append({
                "after_sequence": current,
                "before_sequence": nxt,
                "missing_sequences": missing_range,
                "gap_size": len(missing_range),
                "after_event_type": events[i].event_type.value,
                "before_event_type": events[i + 1].event_type.value,
                "after_actor_did": events[i].actor_did,
                "before_actor_did": events[i + 1].actor_did,
                "after_timestamp": events[i].actor_timestamp.isoformat(),
                "before_timestamp": events[i + 1].actor_timestamp.isoformat(),
            })

    return {
        "twin_id": twin_id,
        "has_provenance_gap": twin.has_provenance_gap,
        "total_events_recorded": len(events),
        "total_gaps": len(gaps),
        "total_missing_events": sum(g["gap_size"] for g in gaps),
        "gaps": gaps,
        "recommendation": (
            "Review custody transfer records for the flagged sequence ranges. "
            "Contact all actors in the provenance chain to obtain missing event data."
        ) if gaps else "No provenance gaps detected — supply chain is fully traceable.",
    }


@router.get("/{twin_id}/recycling", summary="Recycling & dismantling matrix (Feature 7)")
async def recycling_matrix(
    twin_id: str,
    db: AsyncSession = Depends(get_db),
) -> dict:
    twin = await db.get(ProductTwin, twin_id)
    if not twin:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail=f"Twin {twin_id!r} not found")

    return generate_recycling_matrix(
        twin_id=twin_id,
        product_type=twin.product_type,
        current_chemistry=twin.current_chemistry or {},
        material_weights_kg=twin.material_weights_kg or {},
        current_soh_pct=twin.current_soh_pct,
    )
