"""
Counterfeit / blacklisted part serial management endpoints.

All mutating endpoints require the X-Admin-Secret header.

GET    /serials          — List all blacklisted serials
POST   /serials          — Add a new blacklisted serial
DELETE /serials/{serial} — Remove a serial from the blacklist
"""
from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter, Depends, Header, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.database import get_db
from app.models.blacklisted_serial import BlacklistedSerial

settings = get_settings()
router = APIRouter(prefix="/serials", tags=["Counterfeit Serials"])


def _require_admin(x_admin_secret: Optional[str] = Header(None)) -> None:
    """Dependency: reject requests without the correct admin secret header."""
    if not x_admin_secret or x_admin_secret != settings.ADMIN_SECRET:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Valid X-Admin-Secret header required for this operation",
        )


class SerialCreate(BaseModel):
    serial_number: str = Field(..., min_length=1, max_length=256)
    reason: Optional[str] = None
    added_by_did: Optional[str] = None


class SerialRead(BaseModel):
    model_config = {"from_attributes": True}

    id: int
    serial_number: str
    reason: Optional[str]
    added_by_did: Optional[str]


@router.get("", response_model=List[SerialRead],
            summary="List all blacklisted part serials")
async def list_serials(
    db: AsyncSession = Depends(get_db),
) -> List[SerialRead]:
    result = await db.execute(select(BlacklistedSerial).order_by(BlacklistedSerial.id))
    return [SerialRead.model_validate(s) for s in result.scalars().all()]


@router.post("", response_model=SerialRead, status_code=status.HTTP_201_CREATED,
             summary="Add a counterfeit serial to the blacklist (admin only)",
             dependencies=[Depends(_require_admin)])
async def add_serial(
    payload: SerialCreate,
    db: AsyncSession = Depends(get_db),
) -> SerialRead:
    # Check for duplicate
    existing = await db.execute(
        select(BlacklistedSerial).where(
            BlacklistedSerial.serial_number == payload.serial_number
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Serial {payload.serial_number!r} is already blacklisted",
        )
    serial = BlacklistedSerial(
        serial_number=payload.serial_number,
        reason=payload.reason,
        added_by_did=payload.added_by_did,
    )
    db.add(serial)
    await db.flush()
    return SerialRead.model_validate(serial)


@router.delete("/{serial_number}", status_code=status.HTTP_204_NO_CONTENT,
               summary="Remove a serial from the blacklist (admin only)",
               response_model=None,
               dependencies=[Depends(_require_admin)])
async def remove_serial(
    serial_number: str,
    db: AsyncSession = Depends(get_db),
) -> None:
    result = await db.execute(
        select(BlacklistedSerial).where(
            BlacklistedSerial.serial_number == serial_number
        )
    )
    serial = result.scalar_one_or_none()
    if not serial:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail=f"Serial {serial_number!r} not found in blacklist")
    await db.delete(serial)
