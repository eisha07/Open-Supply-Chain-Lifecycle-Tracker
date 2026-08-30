"""
Public passport view endpoint (Feature 4) — no authentication required.

GET /passport/{twin_id}           — Mobile-first public provenance view
GET /passport/{twin_id}/timeline  — Sanitised public event timeline
"""
from __future__ import annotations

from typing import Any, Dict, List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.event import ProductEvent
from app.models.twin import ProductTwin
from app.schemas.event import EventPublicRead
from app.schemas.twin import TwinPublicRead

router = APIRouter(prefix="/passport", tags=["Public Passport"])

# Metadata keys safe to expose to unauthenticated users
_PUBLIC_METADATA_KEYS = {
    "soh_pct", "safety_rating", "event_notes", "location_region",
    "repair_type", "certification_id", "custody_region",
}


def _mask_did(did: str) -> str:
    """Partially mask a DID for public display: show first 20 chars + '…'."""
    return did[:20] + "…" if len(did) > 20 else did


def _filter_public_metadata(meta: Dict[str, Any]) -> Dict[str, Any]:
    """Strip commercially sensitive fields; return only public-safe keys."""
    return {k: v for k, v in meta.items() if k in _PUBLIC_METADATA_KEYS}


@router.get("/{twin_id}", response_model=TwinPublicRead,
            summary="Public Digital Product Passport (mobile-first)")
async def get_public_passport(
    twin_id: str,
    db: AsyncSession = Depends(get_db),
) -> TwinPublicRead:
    """
    Unauthenticated endpoint for QR-code scan landing page.

    Returns a privacy-masked view of the twin:
      - Strips manufacturer_did, exact weights, supplier identities.
      - Exposes: name, type, status, SoH %, safety rating, recyclability score,
        ZKP flags, provenance gap flag.
    """
    twin = await db.get(ProductTwin, twin_id)
    if not twin:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No Digital Product Passport found for ID {twin_id!r}",
        )
    return TwinPublicRead.model_validate(twin)


@router.get("/{twin_id}/timeline", summary="Public provenance timeline")
async def get_public_timeline(
    twin_id: str,
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """
    Return a sanitised event timeline for the public passport view.

    - Actor DIDs are partially masked.
    - Only public-safe metadata keys are included.
    - SECURITY_ALERT events are excluded (internal audit data).
    """
    twin = await db.get(ProductTwin, twin_id)
    if not twin:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No Digital Product Passport found for ID {twin_id!r}",
        )

    result = await db.execute(
        select(ProductEvent)
        .where(
            ProductEvent.twin_id == twin_id,
            ProductEvent.event_type != "SECURITY_ALERT",
        )
        .order_by(ProductEvent.sequence_num)
    )
    events = result.scalars().all()

    timeline = [
        EventPublicRead(
            id=e.id,
            twin_id=e.twin_id,
            event_type=e.event_type,
            sequence_num=e.sequence_num,
            actor_did_masked=_mask_did(e.actor_did),
            actor_timestamp=e.actor_timestamp,
            public_metadata=_filter_public_metadata(e.metadata_json or {}),
        )
        for e in events
    ]

    return {
        "twin_id": twin_id,
        "product_name": twin.name,
        "product_type": twin.product_type,
        "status": twin.status.value,
        "timeline": [t.model_dump() for t in timeline],
        "compliance_badges": _build_compliance_badges(twin),
        "safety_warnings": _build_safety_warnings(twin),
    }


def _build_compliance_badges(twin: ProductTwin) -> List[Dict[str, str]]:
    """Generate regulatory compliance badge data from ZKP flags."""
    badges = []
    flags = twin.zkp_flags or {}

    if flags.get("eu_battery_regulation_compliant", {}).get("value"):
        badges.append({
            "id": "EU_BATTERY_REG",
            "label": "EU Battery Regulation 2023/1542",
            "status": "COMPLIANT",
            "color": "green",
        })
    if flags.get("is_conflict_free", {}).get("value"):
        badges.append({
            "id": "CONFLICT_FREE",
            "label": "Conflict-Free Sourcing",
            "status": "VERIFIED",
            "color": "blue",
        })
    for key, flag in flags.items():
        if "recycled_cobalt" in key and flag.get("value"):
            badges.append({
                "id": key.upper(),
                "label": f"Recycled Cobalt ≥ {flag.get('threshold', '?')}%",
                "status": "VERIFIED",
                "color": "teal",
            })
    return badges


def _build_safety_warnings(twin: ProductTwin) -> List[str]:
    """Build safety warning strings based on current twin state."""
    warnings = []
    if twin.current_soh_pct is not None and twin.current_soh_pct < 20:
        warnings.append(
            "CRITICAL: Battery is severely degraded (SoH < 20%).  "
            "Do not attempt to recharge.  Risk of thermal runaway."
        )
    if twin.status.value == "TAMPERED_SAFETY_RISK":
        warnings.append(
            "WARNING: This asset has been flagged for a potential tampering event.  "
            "Do not use until a certified inspection is completed."
        )
    if twin.has_provenance_gap:
        warnings.append(
            "INFO: Provenance gap detected in supply chain — some custody transfer "
            "records may be missing."
        )
    return warnings
