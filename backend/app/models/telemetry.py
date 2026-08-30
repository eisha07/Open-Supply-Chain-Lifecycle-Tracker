"""Quarantine table for anomalous / rate-exceeded IoT telemetry (Edge Case 3)."""
from __future__ import annotations

from sqlalchemy import Column, DateTime, Float, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.sql import func

from app.database import Base


class UntrustedTelemetry(Base):
    """
    Rows land here instead of product_events when:
      - payload fails schema bounds validation (e.g. temperature < -273 °C)
      - sender is rate-limited (leaky-bucket overflow)
      - sensor value deviates more than ±3 σ from recent rolling average

    The original raw bytes are preserved for forensic analysis without
    contaminating the trusted historical baseline.
    """
    __tablename__ = "untrusted_telemetry"

    id = Column(Integer, primary_key=True, autoincrement=True)

    twin_id = Column(String(256), ForeignKey("twins.id", ondelete="SET NULL"),
                     nullable=True, index=True)
    actor_did = Column(String(256), nullable=True)

    # Raw payload exactly as received — not parsed / validated
    raw_payload = Column(JSON, nullable=False)

    # Machine-readable reason for quarantine
    quarantine_reason = Column(String(128), nullable=False)
    detail = Column(Text, nullable=True)

    # Anomaly metrics (populated by the anomaly filter)
    reported_value = Column(Float, nullable=True)
    expected_range_min = Column(Float, nullable=True)
    expected_range_max = Column(Float, nullable=True)

    ingested_at = Column(DateTime(timezone=True), server_default=func.now())
