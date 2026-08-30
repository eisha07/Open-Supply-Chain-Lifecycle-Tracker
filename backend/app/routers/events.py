"""
Append-only event ledger endpoints (Features 2 & 3 + Edge Cases 1–4).

POST /events              — Append a new signed lifecycle event
GET  /events/{twin_id}    — Retrieve full event history for a twin
GET  /events/{twin_id}/verify — Re-verify the chain-hash integrity
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Any, Dict, List

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.actor import Actor, ActorRole
from app.models.event import EventType, ProductEvent, ROLE_EVENT_PERMISSIONS
from app.models.telemetry import UntrustedTelemetry
from app.models.twin import ProductTwin, TwinStatus
from app.schemas.event import EventCreate, EventRead
from app.services.crypto import (
    build_event_canonical_payload,
    is_timestamp_fresh,
    sha256_hex,
    verify_signature,
)
from app.services.state_engine import reduce_events

router = APIRouter(prefix="/events", tags=["Events"])

# ── Telemetry anomaly bounds ──────────────────────────────────────────────────
_BOUNDS: Dict[str, tuple[float, float]] = {
    "temperature_celsius": (-40.0, 85.0),
    "voltage_v": (2.5, 4.5),
    "current_a": (-500.0, 500.0),
    "soh_pct": (0.0, 100.0),
    "capacity_kwh": (0.0, 1000.0),
}

# ── Blacklisted / counterfeit serial registry (in-memory for MVP) ─────────────
# In production this would be a DB table with admin management endpoints.
_BLACKLISTED_SERIALS: set[str] = set()


def _check_telemetry_bounds(metadata: Dict[str, Any]) -> List[str]:
    """Return a list of out-of-bounds field names."""
    violations = []
    for field, (lo, hi) in _BOUNDS.items():
        if field in metadata:
            try:
                v = float(metadata[field])
                if not (lo <= v <= hi):
                    violations.append(f"{field}={v} outside [{lo}, {hi}]")
            except (TypeError, ValueError):
                violations.append(f"{field}: non-numeric value")
    return violations


async def _get_next_sequence(db: AsyncSession, twin_id: str) -> int:
    result = await db.execute(
        select(func.max(ProductEvent.sequence_num)).where(
            ProductEvent.twin_id == twin_id
        )
    )
    current_max = result.scalar_one_or_none()
    return (current_max + 1) if current_max is not None else 0


async def _get_previous_hash(db: AsyncSession, twin_id: str, seq: int) -> str | None:
    if seq == 0:
        return None
    result = await db.execute(
        select(ProductEvent).where(
            ProductEvent.twin_id == twin_id,
            ProductEvent.sequence_num == seq - 1,
        )
    )
    prev = result.scalar_one_or_none()
    if not prev:
        return None
    payload_bytes = build_event_canonical_payload(
        twin_id=prev.twin_id,
        event_type=prev.event_type.value,
        actor_did=prev.actor_did,
        actor_timestamp=prev.actor_timestamp,
        metadata_json=prev.metadata_json,
    )
    return sha256_hex(payload_bytes)


@router.post("", response_model=EventRead, status_code=status.HTTP_201_CREATED,
             summary="Append a signed lifecycle event to the immutable ledger")
async def append_event(
    payload: EventCreate,
    db: AsyncSession = Depends(get_db),
) -> EventRead:
    """
    Multi-step validation pipeline before committing an event:

    1. Resolve and validate the actor (exists, not blacklisted, correct role).
    2. Replay-attack timestamp freshness check.
    3. Ed25519 signature verification.
    4. Optimistic concurrency check (version_id).
    5. Telemetry anomaly bounds check → quarantine if violated.
    6. Counterfeit part detection (Edge Case 2).
    7. Provenance gap detection (Edge Case 1).
    8. Append event + update twin state.
    """
    # ── Step 1: Actor validation ───────────────────────────────────────────
    actor: Actor | None = await db.get(Actor, payload.actor_did)
    if not actor:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail=f"Actor {payload.actor_did!r} not registered")
    if actor.is_blacklisted:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                            detail="Actor is blacklisted — event rejected")

    # RBAC: validate the actor's role against the event type
    allowed_roles = ROLE_EVENT_PERMISSIONS.get(payload.event_type, [])
    if allowed_roles and actor.role.value not in allowed_roles:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Role {actor.role.value!r} is not permitted to submit "
                   f"{payload.event_type.value!r} events",
        )

    # ── Step 2: Timestamp freshness ────────────────────────────────────────
    if not is_timestamp_fresh(payload.actor_timestamp):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                            detail="actor_timestamp is outside the allowed freshness window")

    # ── Step 3: Signature verification ────────────────────────────────────
    canonical_bytes = build_event_canonical_payload(
        twin_id=payload.twin_id,
        event_type=payload.event_type.value,
        actor_did=payload.actor_did,
        actor_timestamp=payload.actor_timestamp,
        metadata_json=payload.metadata_json,
    )
    if not verify_signature(canonical_bytes, payload.cryptographic_signature,
                             actor.public_key_hex):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,
                            detail="Cryptographic signature verification failed")

    # ── Step 4: Resolve and lock the twin ─────────────────────────────────
    twin: ProductTwin | None = await db.get(ProductTwin, payload.twin_id)
    if not twin:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail=f"Digital Twin {payload.twin_id!r} not found")

    # Optimistic concurrency (Edge Case 4)
    if payload.expected_version is not None and twin.version_id != payload.expected_version:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "error": "version_conflict",
                "current_version": twin.version_id,
                "expected_version": payload.expected_version,
                "message": "Concurrent state update detected — refresh and retry",
            },
        )

    # ── Step 5: Telemetry anomaly filter (Edge Case 3) ─────────────────────
    if payload.event_type == EventType.TELEMETRY_SNAPSHOT:
        violations = _check_telemetry_bounds(payload.metadata_json)
        if violations:
            quarantine = UntrustedTelemetry(
                twin_id=payload.twin_id,
                actor_did=payload.actor_did,
                raw_payload=payload.metadata_json,
                quarantine_reason="BOUNDS_VIOLATION",
                detail="; ".join(violations),
                reported_value=payload.metadata_json.get("soh_pct"),
                expected_range_min=_BOUNDS.get("soh_pct", (None, None))[0],
                expected_range_max=_BOUNDS.get("soh_pct", (None, None))[1],
            )
            db.add(quarantine)
            await db.flush()
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={
                    "error": "telemetry_anomaly",
                    "violations": violations,
                    "message": "Payload quarantined — see untrusted_telemetry table",
                },
            )

    # ── Step 6: Counterfeit part detection (Edge Case 2) ──────────────────
    if payload.event_type == EventType.REPAIR_PART_SWAP:
        part_serial = payload.metadata_json.get("new_part_serial")
        new_part_did = payload.metadata_json.get("new_part_did")
        if part_serial and part_serial in _BLACKLISTED_SERIALS:
            # Hard-reject: mark twin as TAMPERED
            twin.status = TwinStatus.TAMPERED_SAFETY_RISK
            alert_payload = {
                "actor_did": payload.actor_did,
                "attempted_part_serial": part_serial,
                "reason": "Blacklisted serial number",
            }
            twin.tamper_alert_payload = alert_payload

            # Append a system SECURITY_ALERT event
            seq = await _get_next_sequence(db, payload.twin_id)
            prev_hash = await _get_previous_hash(db, payload.twin_id, seq)
            alert_event = ProductEvent(
                twin_id=payload.twin_id,
                event_type=EventType.SECURITY_ALERT,
                sequence_num=seq,
                actor_did=payload.actor_did,
                actor_timestamp=datetime.now(tz=timezone.utc),
                metadata_json=alert_payload,
                cryptographic_signature="SYSTEM",
                previous_event_hash=prev_hash,
            )
            db.add(alert_event)
            twin.version_id += 1
            await db.flush()

            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "error": "counterfeit_part_detected",
                    "twin_status": TwinStatus.TAMPERED_SAFETY_RISK,
                    "message": "Part serial is blacklisted.  Twin marked TAMPERED_SAFETY_RISK.",
                },
            )

    # ── Step 7: Provenance gap detection (Edge Case 1) ─────────────────────
    next_seq = await _get_next_sequence(db, payload.twin_id)

    # If a CUSTODY_TRANSFER was expected (e.g. EXTRACTION → ASSEMBLY)
    # but we detect a gap, we accept the event but flag the twin.
    # Gap = the sequence number would be non-consecutive (handled in state engine).

    # ── Step 8: Commit the event ──────────────────────────────────────────
    prev_hash = await _get_previous_hash(db, payload.twin_id, next_seq)

    event = ProductEvent(
        twin_id=payload.twin_id,
        event_type=payload.event_type,
        sequence_num=next_seq,
        actor_did=payload.actor_did,
        actor_timestamp=payload.actor_timestamp,
        metadata_json=payload.metadata_json,
        cryptographic_signature=payload.cryptographic_signature,
        previous_event_hash=prev_hash,
    )
    db.add(event)

    # Re-compute twin state via state engine
    result = await db.execute(
        select(ProductEvent)
        .where(ProductEvent.twin_id == payload.twin_id)
        .order_by(ProductEvent.sequence_num)
    )
    all_events = list(result.scalars().all()) + [event]
    new_state = reduce_events(twin, all_events)

    # Apply computed state back to the twin row
    for field, value in new_state.items():
        setattr(twin, field, value)
    twin.version_id += 1

    try:
        await db.flush()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Concurrent write conflict on sequence number — retry",
        )

    return EventRead.model_validate(event)


@router.get("/{twin_id}", response_model=List[EventRead],
            summary="Retrieve full event history for a twin")
async def get_events(
    twin_id: str,
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
) -> List[EventRead]:
    twin = await db.get(ProductTwin, twin_id)
    if not twin:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail=f"Twin {twin_id!r} not found")

    result = await db.execute(
        select(ProductEvent)
        .where(ProductEvent.twin_id == twin_id)
        .order_by(ProductEvent.sequence_num)
        .limit(limit)
        .offset(offset)
    )
    return [EventRead.model_validate(e) for e in result.scalars().all()]


@router.get("/{twin_id}/verify", summary="Verify chain-hash integrity of the event ledger")
async def verify_chain(
    twin_id: str,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """
    Walk the event chain, recomputing each SHA-256 hash link.
    Returns a per-event verification report.
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
    events = result.scalars().all()

    report = []
    prev_computed_hash = None
    all_valid = True

    for event in events:
        payload_bytes = build_event_canonical_payload(
            twin_id=event.twin_id,
            event_type=event.event_type.value,
            actor_did=event.actor_did,
            actor_timestamp=event.actor_timestamp,
            metadata_json=event.metadata_json,
        )
        current_hash = sha256_hex(payload_bytes)
        chain_valid = (event.previous_event_hash == prev_computed_hash)
        if not chain_valid:
            all_valid = False
        report.append({
            "sequence_num": event.sequence_num,
            "event_type": event.event_type.value,
            "stored_prev_hash": event.previous_event_hash,
            "computed_prev_hash": prev_computed_hash,
            "chain_valid": chain_valid,
        })
        prev_computed_hash = current_hash

    return {"twin_id": twin_id, "all_valid": all_valid, "chain": report}
