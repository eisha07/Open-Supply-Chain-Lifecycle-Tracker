"""Pydantic schemas for ProductEvent."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Optional

from pydantic import BaseModel, Field

from app.models.event import EventType


class EventCreate(BaseModel):
    """
    Request body for appending a new lifecycle event.

    The actor must sign the canonical payload (twin_id + event_type +
    actor_did + actor_timestamp + metadata_json serialised deterministically)
    with their Ed25519 private key and include the base64url-encoded result.
    """
    twin_id: str
    event_type: EventType
    actor_did: str
    actor_timestamp: datetime
    metadata_json: Dict[str, Any] = Field(default_factory=dict)
    cryptographic_signature: str = Field(
        ..., description="Base64url-encoded Ed25519 signature over the canonical payload"
    )
    # Expected current version_id for optimistic concurrency check
    expected_version: Optional[int] = Field(
        None,
        description="If supplied, server rejects with 409 if twin.version_id differs"
    )


class EventRead(BaseModel):
    """Full event record returned to authenticated callers."""
    model_config = {"from_attributes": True}

    id: int
    twin_id: str
    event_type: EventType
    sequence_num: int
    actor_did: str
    actor_timestamp: datetime
    server_timestamp: datetime
    metadata_json: Dict[str, Any]
    cryptographic_signature: str
    previous_event_hash: Optional[str]


class EventPublicRead(BaseModel):
    """Sanitised event view for the public passport timeline."""
    model_config = {"from_attributes": True}

    id: int
    twin_id: str
    event_type: EventType
    sequence_num: int
    # actor_did is masked — show only first 20 chars + "…" for privacy
    actor_did_masked: str
    actor_timestamp: datetime
    # Only surface non-sensitive metadata keys
    public_metadata: Dict[str, Any]
