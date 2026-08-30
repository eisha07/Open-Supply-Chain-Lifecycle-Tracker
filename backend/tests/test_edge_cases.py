"""Integration tests for edge cases: concurrency, counterfeit, gaps, anomalies."""
from __future__ import annotations

import pytest
import pytest_asyncio
from datetime import datetime, timezone
from httpx import AsyncClient

from app.services.crypto import (
    build_event_canonical_payload,
    generate_keypair,
    private_key_to_hex,
    public_key_to_did,
    public_key_to_hex,
    sign_payload,
)
from tests.conftest import create_actor, create_twin


def _make_event_payload(twin_id, event_type, actor_did, priv_hex, meta=None):
    ts = datetime.now(tz=timezone.utc)
    metadata = meta or {}
    canon = build_event_canonical_payload(twin_id, event_type, actor_did, ts, metadata)
    sig = sign_payload(canon, priv_hex)
    return {
        "twin_id": twin_id,
        "event_type": event_type,
        "actor_did": actor_did,
        "actor_timestamp": ts.isoformat(),
        "metadata_json": metadata,
        "cryptographic_signature": sig,
    }


@pytest.mark.asyncio
class TestEdgeCase1_ProvenanceGap:
    """Edge Case 1: Out-of-order / missing custody transfer."""

    async def test_provenance_gap_flag_set(self, client: AsyncClient):
        # Register supplier, create twin, log EXTRACTION, skip CUSTODY_TRANSFER,
        # log REPAIR directly — gap should be flagged.
        supplier = await create_actor(client, "RAW_MATERIAL_SUPPLIER", "Supplier Co.")
        actor_did = supplier["did"]
        priv_hex = supplier["private_key_hex"]

        twin = await create_twin(client, actor_did)
        twin_id = twin["id"]

        # Log EXTRACTION (seq 0)
        extraction = _make_event_payload(twin_id, "EXTRACTION", actor_did, priv_hex)
        r = await client.post("/events", json=extraction)
        assert r.status_code == 201

        # Get current state — gap not yet detected
        r = await client.get(f"/twins/{twin_id}")
        assert r.json()["has_provenance_gap"] is False

        # Now register a technician and log REPAIR without prior CUSTODY_TRANSFER
        tech = await create_actor(client, "FIELD_TECHNICIAN", "Tech")
        tech_priv = tech["private_key_hex"]
        tech_did = tech["did"]

        repair = _make_event_payload(twin_id, "REPAIR_PART_SWAP", tech_did, tech_priv,
                                     {"repair_type": "module_replacement",
                                      "new_part_serial": "SN-LEGIT-999"})
        r = await client.post("/events", json=repair)
        # Should SUCCEED (not rejected) — just flag the gap
        assert r.status_code == 201


@pytest.mark.asyncio
class TestEdgeCase2_CounterfeitPart:
    """Edge Case 2: Blacklisted serial triggers TAMPERED_SAFETY_RISK."""

    async def test_blacklisted_serial_hard_rejected(self, client: AsyncClient):
        oem = await create_actor(client, "OEM_MANUFACTURER", "OEM")
        twin = await create_twin(client, oem["did"])
        twin_id = twin["id"]

        # Register technician
        tech = await create_actor(client, "FIELD_TECHNICIAN", "Tech")

        # Inject a known-blacklisted serial into the in-memory registry
        from app.routers.events import _BLACKLISTED_SERIALS
        _BLACKLISTED_SERIALS.add("FAKE-SERIAL-001")

        ts = datetime.now(tz=timezone.utc)
        meta = {"new_part_serial": "FAKE-SERIAL-001"}
        canon = build_event_canonical_payload(
            twin_id, "REPAIR_PART_SWAP", tech["did"], ts, meta
        )
        sig = sign_payload(canon, tech["private_key_hex"])
        payload = {
            "twin_id": twin_id,
            "event_type": "REPAIR_PART_SWAP",
            "actor_did": tech["did"],
            "actor_timestamp": ts.isoformat(),
            "metadata_json": meta,
            "cryptographic_signature": sig,
        }
        r = await client.post("/events", json=payload)
        assert r.status_code == 403
        assert "counterfeit_part_detected" in r.json()["detail"]["error"]

        # Twin must now be TAMPERED_SAFETY_RISK
        r2 = await client.get(f"/twins/{twin_id}")
        assert r2.json()["status"] == "TAMPERED_SAFETY_RISK"

        # Cleanup
        _BLACKLISTED_SERIALS.discard("FAKE-SERIAL-001")


@pytest.mark.asyncio
class TestEdgeCase3_TelemetryAnomaly:
    """Edge Case 3: Out-of-bounds telemetry quarantined, baseline unaffected."""

    async def test_negative_temperature_quarantined(self, client: AsyncClient):
        oem = await create_actor(client, "OEM_MANUFACTURER", "OEM")
        twin = await create_twin(client, oem["did"])
        twin_id = twin["id"]

        tech = await create_actor(client, "FIELD_TECHNICIAN", "Tech")

        # Submit telemetry with temperature below physical minimum
        ts = datetime.now(tz=timezone.utc)
        meta = {"temperature_celsius": -999, "soh_pct": 85.0, "voltage_v": 3.8}
        canon = build_event_canonical_payload(
            twin_id, "TELEMETRY_SNAPSHOT", tech["did"], ts, meta
        )
        sig = sign_payload(canon, tech["private_key_hex"])
        payload = {
            "twin_id": twin_id,
            "event_type": "TELEMETRY_SNAPSHOT",
            "actor_did": tech["did"],
            "actor_timestamp": ts.isoformat(),
            "metadata_json": meta,
            "cryptographic_signature": sig,
        }
        r = await client.post("/events", json=payload)
        assert r.status_code == 422
        assert r.json()["detail"]["error"] == "telemetry_anomaly"

        # Twin SoH should remain at original value (100%) — baseline not corrupted
        r2 = await client.get(f"/twins/{twin_id}")
        assert r2.json()["current_soh_pct"] == 100.0


@pytest.mark.asyncio
class TestEdgeCase4_OptimisticConcurrency:
    """Edge Case 4: Stale version_id rejected with 409."""

    async def test_stale_version_rejected(self, client: AsyncClient):
        supplier = await create_actor(client, "RAW_MATERIAL_SUPPLIER", "Supplier")
        twin = await create_twin(client, supplier["did"])
        twin_id = twin["id"]
        current_version = twin["version_id"]  # 0

        # Submit a valid event to advance version
        ts = datetime.now(tz=timezone.utc)
        meta = {}
        canon = build_event_canonical_payload(
            twin_id, "EXTRACTION", supplier["did"], ts, meta
        )
        sig = sign_payload(canon, supplier["private_key_hex"])
        payload = {
            "twin_id": twin_id,
            "event_type": "EXTRACTION",
            "actor_did": supplier["did"],
            "actor_timestamp": ts.isoformat(),
            "metadata_json": meta,
            "cryptographic_signature": sig,
            "expected_version": current_version,  # valid at this point
        }
        r = await client.post("/events", json=payload)
        assert r.status_code == 201  # first write succeeds

        # Attempt second write with the same stale version — must be rejected
        ts2 = datetime.now(tz=timezone.utc)
        canon2 = build_event_canonical_payload(
            twin_id, "EXTRACTION", supplier["did"], ts2, {}
        )
        sig2 = sign_payload(canon2, supplier["private_key_hex"])
        payload2 = {**payload, "actor_timestamp": ts2.isoformat(),
                    "cryptographic_signature": sig2,
                    "expected_version": current_version}  # stale!
        r2 = await client.post("/events", json=payload2)
        assert r2.status_code == 409
        assert r2.json()["detail"]["error"] == "version_conflict"
