"""Actor (supply-chain participant) model with role-based access control."""
from __future__ import annotations

import enum

from sqlalchemy import Boolean, Column, DateTime, Enum as SAEnum, String, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.database import Base


class ActorRole(str, enum.Enum):
    """Distinct RBAC roles — never collapse or alias these."""
    RAW_MATERIAL_SUPPLIER = "RAW_MATERIAL_SUPPLIER"
    OEM_MANUFACTURER = "OEM_MANUFACTURER"
    FIELD_TECHNICIAN = "FIELD_TECHNICIAN"
    RECYCLER_DISMANTLER = "RECYCLER_DISMANTLER"
    PUBLIC = "PUBLIC"


class Actor(Base):
    """
    Represents a supply-chain participant identified by a Decentralized Identifier.

    The DID is derived from the actor's Ed25519 public key (did:key scheme).
    The public_key_hex field is stored to enable server-side signature verification
    without re-resolving the DID every time.
    """
    __tablename__ = "actors"

    # Primary identity: did:key:z6Mk…
    did = Column(String(256), primary_key=True, index=True)

    display_name = Column(String(128), nullable=False)
    role = Column(SAEnum(ActorRole), nullable=False, index=True)

    # Hex-encoded Ed25519 public key (32 bytes → 64 hex chars)
    public_key_hex = Column(String(64), nullable=False, unique=True)

    # Blacklist flag: True = this actor has been revoked and all new events rejected
    is_blacklisted = Column(Boolean, default=False, nullable=False)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    events = relationship("ProductEvent", back_populates="actor",
                          foreign_keys="ProductEvent.actor_did")
