"""Persisted counterfeit / blacklisted part serial registry."""
from __future__ import annotations

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.sql import func

from app.database import Base


class BlacklistedSerial(Base):
    """
    A part serial number that has been flagged as counterfeit or unsafe.

    Replaces the in-memory `_BLACKLISTED_SERIALS` set in events.py so that
    the registry survives backend restarts and is shared across instances.
    """
    __tablename__ = "blacklisted_serials"

    id = Column(Integer, primary_key=True, autoincrement=True)
    serial_number = Column(String(256), nullable=False, unique=True, index=True)
    reason = Column(Text, nullable=True)
    added_by_did = Column(
        String(256),
        ForeignKey("actors.did", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    created_at = Column(DateTime(timezone=True), server_default=func.now())
