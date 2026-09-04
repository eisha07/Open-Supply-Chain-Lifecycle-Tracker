"""
Public passport view endpoint (Feature 4) — no authentication required.

GET /passport/{twin_id}           — Mobile-first public provenance view
GET /passport/{twin_id}/timeline  — Sanitised public event timeline (paginated)
GET /passport/{twin_id}/qr        — QR code PNG pointing to this passport URL
"""
from __future__ import annotations

import io
from typing import Any, Dict, List, Optional

import qrcode
from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import Response, StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.api_key import require_api_key
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
            summary="Public Digital Product Passport (mobile-first)",
            dependencies=[Depends(require_api_key)])
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


@router.get("/{twin_id}/timeline", summary="Public provenance timeline (paginated)",
            dependencies=[Depends(require_api_key)])
async def get_public_timeline(
    twin_id: str,
    limit: int = Query(50, ge=1, le=200, description="Max events per page"),
    offset: int = Query(0, ge=0, description="Pagination offset"),
    event_type: Optional[str] = Query(None, description="Filter by event type"),
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """
    Return a sanitised, paginated event timeline for the public passport view.

    - Actor DIDs are partially masked.
    - Only public-safe metadata keys are included.
    - SECURITY_ALERT events are excluded (internal audit data).
    - Supports pagination via limit/offset and event_type filtering.
    """
    twin = await db.get(ProductTwin, twin_id)
    if not twin:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No Digital Product Passport found for ID {twin_id!r}",
        )

    q = (
        select(ProductEvent)
        .where(
            ProductEvent.twin_id == twin_id,
            ProductEvent.event_type != "SECURITY_ALERT",
        )
        .order_by(ProductEvent.sequence_num)
    )
    if event_type:
        q = q.where(ProductEvent.event_type == event_type)

    # Get total count for pagination metadata
    count_q = select(ProductEvent).where(
        ProductEvent.twin_id == twin_id,
        ProductEvent.event_type != "SECURITY_ALERT",
    )
    if event_type:
        count_q = count_q.where(ProductEvent.event_type == event_type)
    count_result = await db.execute(count_q)
    total_count = len(count_result.scalars().all())

    q = q.limit(limit).offset(offset)
    result = await db.execute(q)
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
        "pagination": {
            "total": total_count,
            "limit": limit,
            "offset": offset,
            "has_more": offset + limit < total_count,
        },
        "compliance_badges": _build_compliance_badges(twin),
        "safety_warnings": _build_safety_warnings(twin),
    }


@router.get("/{twin_id}/qr", summary="Generate a QR code PNG for the public passport URL",
            dependencies=[Depends(require_api_key)])
async def get_passport_qr(
    twin_id: str,
    base_url: str = Query(
        "http://localhost:3000",
        description="Frontend base URL used to construct the passport link",
    ),
    db: AsyncSession = Depends(get_db),
) -> Response:
    """
    Returns a PNG image containing a QR code that encodes the public passport URL
    for this twin.  Scan it with any QR reader to open the Digital Product Passport.
    """
    twin = await db.get(ProductTwin, twin_id)
    if not twin:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No Digital Product Passport found for ID {twin_id!r}",
        )

    passport_url = f"{base_url.rstrip('/')}/passport/{twin_id}"

    qr = qrcode.QRCode(
        version=None,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=10,
        border=4,
    )
    qr.add_data(passport_url)
    qr.make(fit=True)

    img = qr.make_image(fill_color="black", back_color="white")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)

    return Response(
        content=buf.getvalue(),
        media_type="image/png",
        headers={
            "Content-Disposition": f'inline; filename="passport_qr_{twin_id[:20]}.png"',
            "Cache-Control": "public, max-age=86400",
        },
    )


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
