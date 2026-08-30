"""Pydantic schemas for ProductTwin."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from app.models.twin import TwinStatus


class TwinCreate(BaseModel):
    """Request body for instantiating a new Digital Twin."""
    name: str = Field(..., min_length=1, max_length=256)
    product_type: str = Field(..., min_length=1, max_length=128,
                               examples=["EV_BATTERY_CELL", "BATTERY_PACK", "EV"])
    parent_twin_id: Optional[str] = Field(None, description="DID of the parent twin in the BOM")
    serial_number: Optional[str] = Field(None, max_length=128)
    manufacturing_date: Optional[datetime] = None
    material_weights_kg: Optional[Dict[str, float]] = Field(
        None, examples=[{"lithium": 2.1, "cobalt": 1.3, "nickel": 4.5}]
    )
    baseline_chemistry: Optional[Dict[str, float]] = Field(
        None, examples=[{"NMC_811": 0.85, "graphite": 0.15}]
    )
    initial_capacity_kwh: Optional[float] = Field(None, ge=0)
    initial_safety_rating: Optional[str] = Field(None, max_length=64)


class TwinRead(BaseModel):
    """Full twin view for authenticated actors."""
    model_config = {"from_attributes": True}

    id: str
    name: str
    product_type: str
    parent_twin_id: Optional[str]
    status: TwinStatus
    version_id: int
    manufacturer_did: str
    manufacturing_date: Optional[datetime]
    serial_number: Optional[str]
    material_weights_kg: Optional[Dict[str, Any]]
    baseline_chemistry: Optional[Dict[str, Any]]
    initial_capacity_kwh: Optional[float]
    current_capacity_kwh: Optional[float]
    current_soh_pct: Optional[float]
    current_chemistry: Optional[Dict[str, Any]]
    current_safety_rating: Optional[str]
    recyclability_score: Optional[float]
    zkp_flags: Optional[Dict[str, Any]]
    has_provenance_gap: bool
    created_at: datetime
    updated_at: Optional[datetime]


class TwinPublicRead(BaseModel):
    """
    Sanitised view for unauthenticated public / QR-code scans.

    Strips: manufacturer_did, exact material weights/chemistry, vendor pricing.
    Exposes: provenance timeline, safety ratings, recyclability, ZKP flags.
    """
    model_config = {"from_attributes": True}

    id: str
    name: str
    product_type: str
    status: TwinStatus
    current_soh_pct: Optional[float]
    current_safety_rating: Optional[str]
    recyclability_score: Optional[float]
    zkp_flags: Optional[Dict[str, Any]]
    has_provenance_gap: bool
    created_at: datetime


class SecondLifeEstimate(BaseModel):
    """Output of the secondary-market reuse estimator (Feature 6)."""
    twin_id: str
    current_soh_pct: Optional[float]
    recommendation: str
    suitable_for_automotive: bool
    suitable_for_stationary_storage: bool
    reasoning: str


class ZKPDisclosureRequest(BaseModel):
    """Request body to generate a ZKP flag set (Feature 5)."""
    claims: Dict[str, Any] = Field(
        ...,
        examples=[{"is_conflict_free": True, "recycled_cobalt_pct_gte": 30}]
    )
