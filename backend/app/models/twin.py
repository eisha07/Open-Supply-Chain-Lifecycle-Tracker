"""Digital Twin model — the central entity of the system."""
from __future__ import annotations

import enum

from sqlalchemy import (
    Boolean, Column, DateTime, Enum as SAEnum, Float,
    ForeignKey, Integer, JSON, String,
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.database import Base


class TwinStatus(str, enum.Enum):
    """Lifecycle state of a Digital Twin."""
    ACTIVE = "ACTIVE"
    PROVENANCE_GAP_DETECTED = "PROVENANCE_GAP_DETECTED"   # Edge Case 1
    TAMPERED_SAFETY_RISK = "TAMPERED_SAFETY_RISK"          # Edge Case 2
    UNSUITABLE_FOR_AUTOMOTIVE = "UNSUITABLE_FOR_AUTOMOTIVE"  # Feature 6
    RECOMMENDED_FOR_STATIONARY_STORAGE = "RECOMMENDED_FOR_STATIONARY_STORAGE"
    DECOMMISSIONED = "DECOMMISSIONED"
    SCRAPPED = "SCRAPPED"


class ProductTwin(Base):
    """
    Digital Twin for a physical product (raw material, component, or finished good).

    Supports a hierarchical Bill of Materials via the self-referential parent_twin_id
    foreign key (e.g. Cell → Battery Pack → EV).

    Optimistic concurrency control is enforced through version_id: callers must
    supply the current version when mutating state; a mismatch raises HTTP 409.
    """
    __tablename__ = "twins"

    # Unique DID assigned at instantiation: did:key:z6Mk…
    id = Column(String(256), primary_key=True, index=True)

    name = Column(String(256), nullable=False)
    product_type = Column(String(128), nullable=False)  # e.g. "EV_BATTERY_CELL"

    # Bill-of-Materials hierarchy
    parent_twin_id = Column(String(256), ForeignKey("twins.id", ondelete="SET NULL"),
                            nullable=True, index=True)

    status = Column(SAEnum(TwinStatus), default=TwinStatus.ACTIVE, nullable=False, index=True)

    # Optimistic concurrency lock — incremented on every state-changing event
    version_id = Column(Integer, default=0, nullable=False)

    # ── Factory-gate baseline (immutable after creation) ─────────────────────
    manufacturer_did = Column(String(256), nullable=False)
    manufacturing_date = Column(DateTime(timezone=True), nullable=True)
    serial_number = Column(String(128), nullable=True, unique=True, index=True)
    material_weights_kg = Column(JSON, nullable=True)   # {"lithium": 2.1, "cobalt": 1.3}
    baseline_chemistry = Column(JSON, nullable=True)    # {"NMC_811": 0.85, "graphite": 0.15}
    initial_capacity_kwh = Column(Float, nullable=True)
    initial_safety_rating = Column(String(64), nullable=True)

    # ── Computed current state (updated by state engine after each event) ─────
    current_capacity_kwh = Column(Float, nullable=True)
    current_soh_pct = Column(Float, nullable=True)     # 0–100
    current_chemistry = Column(JSON, nullable=True)
    current_safety_rating = Column(String(64), nullable=True)
    recyclability_score = Column(Float, nullable=True) # 0–100

    # ZKP disclosure flags (Feature 5)
    zkp_flags = Column(JSON, nullable=True)  # {"is_conflict_free": true, ...}

    # Provenance / audit flags
    has_provenance_gap = Column(Boolean, default=False, nullable=False)
    tamper_alert_payload = Column(JSON, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # ── Relationships ────────────────────────────────────────────────────────
    children = relationship("ProductTwin", foreign_keys=[parent_twin_id],
                            backref=__import__("sqlalchemy.orm", fromlist=["backref"])
                            .backref("parent", remote_side="ProductTwin.id"))
    events = relationship("ProductEvent", back_populates="twin",
                          order_by="ProductEvent.sequence_num",
                          cascade="all, delete-orphan")
