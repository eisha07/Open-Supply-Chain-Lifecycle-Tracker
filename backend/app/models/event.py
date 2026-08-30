"""Append-only product event store — the immutable ledger."""
from __future__ import annotations

import enum

from sqlalchemy import (
    CheckConstraint, Column, DateTime, Enum as SAEnum,
    ForeignKey, Index, Integer, JSON, String, Text,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.database import Base


class EventType(str, enum.Enum):
    """All legal lifecycle event types."""
    EXTRACTION = "EXTRACTION"
    ASSEMBLY = "ASSEMBLY"
    CUSTODY_TRANSFER = "CUSTODY_TRANSFER"
    REPAIR_PART_SWAP = "REPAIR_PART_SWAP"
    TELEMETRY_SNAPSHOT = "TELEMETRY_SNAPSHOT"
    DECOMMISSION = "DECOMMISSION"
    # Internal audit events — written by the system, not actors
    SECURITY_ALERT = "SECURITY_ALERT"
    PROVENANCE_GAP_AUDIT = "PROVENANCE_GAP_AUDIT"


# Map which roles are allowed to submit each event type
ROLE_EVENT_PERMISSIONS: dict[EventType, list[str]] = {
    EventType.EXTRACTION:        ["RAW_MATERIAL_SUPPLIER"],
    EventType.ASSEMBLY:          ["OEM_MANUFACTURER"],
    EventType.CUSTODY_TRANSFER:  ["RAW_MATERIAL_SUPPLIER", "OEM_MANUFACTURER",
                                   "FIELD_TECHNICIAN", "RECYCLER_DISMANTLER"],
    EventType.REPAIR_PART_SWAP:  ["FIELD_TECHNICIAN"],
    EventType.TELEMETRY_SNAPSHOT:["FIELD_TECHNICIAN", "OEM_MANUFACTURER"],
    EventType.DECOMMISSION:      ["RECYCLER_DISMANTLER"],
    EventType.SECURITY_ALERT:    [],  # system-only
    EventType.PROVENANCE_GAP_AUDIT: [],  # system-only
}


class ProductEvent(Base):
    """
    Single immutable entry in the append-only event ledger.

    Rows are NEVER updated or deleted after insertion — delete triggers are
    intentionally absent.  The (twin_id, sequence_num) unique constraint
    enforces ordering and enables optimistic concurrency checks.
    """
    __tablename__ = "product_events"

    id = Column(Integer, primary_key=True, autoincrement=True)

    twin_id = Column(String(256), ForeignKey("twins.id", ondelete="CASCADE"),
                     nullable=False, index=True)
    event_type = Column(SAEnum(EventType), nullable=False, index=True)

    # Monotonically increasing per twin — used for ordering & concurrency
    sequence_num = Column(Integer, nullable=False)

    actor_did = Column(String(256), ForeignKey("actors.did", ondelete="RESTRICT"),
                       nullable=False, index=True)

    # ISO-8601 timestamp supplied by the actor (not trusted for ordering)
    actor_timestamp = Column(DateTime(timezone=True), nullable=False)
    # Server-assigned ingestion time (used for replay protection)
    server_timestamp = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    # Arbitrary structured payload (e.g. SoH %, part serial, custody address)
    metadata_json = Column(JSON, nullable=False, default=dict)

    # Base64url-encoded Ed25519 signature over canonical payload bytes
    cryptographic_signature = Column(Text, nullable=False)

    # previous_event_hash: SHA-256 of the previous row's canonical payload
    # Enables chained-hash verification (blockchain-lite integrity check)
    previous_event_hash = Column(String(64), nullable=True)

    __table_args__ = (
        # Enforce strict per-twin ordering — also prevents duplicate sequence
        UniqueConstraint("twin_id", "sequence_num", name="uq_twin_sequence"),
        Index("ix_product_events_twin_seq", "twin_id", "sequence_num"),
    )

    # ── Relationships ────────────────────────────────────────────────────────
    twin = relationship("ProductTwin", back_populates="events")
    actor = relationship("Actor", back_populates="events",
                         foreign_keys=[actor_did])
