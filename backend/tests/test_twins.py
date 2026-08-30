"""Integration tests for Twin endpoints and state engine."""
from __future__ import annotations

import pytest
from datetime import datetime, timezone
from httpx import AsyncClient

from app.services.crypto import build_event_canonical_payload, sign_payload
from tests.conftest import create_actor, create_twin


def _event(twin_id, etype, actor_did, priv_hex, meta=None):
    ts = datetime.now(tz=timezone.utc)
    meta = meta or {}
    canon = build_event_canonical_payload(twin_id, etype, actor_did, ts, meta)
    sig = sign_payload(canon, priv_hex)
    return {"twin_id": twin_id, "event_type": etype, "actor_did": actor_did,
            "actor_timestamp": ts.isoformat(), "metadata_json": meta,
            "cryptographic_signature": sig}


@pytest.mark.asyncio
class TestTwinCRUD:
    async def test_create_twin_supplier(self, client: AsyncClient):
        actor = await create_actor(client, "RAW_MATERIAL_SUPPLIER", "SupCo")
        twin = await create_twin(client, actor["did"])
        assert twin["id"].startswith("did:key:z")
        assert twin["status"] == "ACTIVE"
        assert twin["manufacturer_did"] == actor["did"]

    async def test_create_twin_oem(self, client: AsyncClient):
        actor = await create_actor(client, "OEM_MANUFACTURER", "OEM Inc.")
        twin = await create_twin(client, actor["did"], product_type="BATTERY_PACK")
        assert twin["product_type"] == "BATTERY_PACK"

    async def test_technician_cannot_create_twin(self, client: AsyncClient):
        tech = await create_actor(client, "FIELD_TECHNICIAN", "Tech")
        r = await client.post(f"/twins?actor_did={tech['did']}", json={
            "name": "T", "product_type": "EV_BATTERY_CELL"
        })
        assert r.status_code == 403

    async def test_list_twins(self, client: AsyncClient):
        actor = await create_actor(client, "OEM_MANUFACTURER")
        await create_twin(client, actor["did"])
        await create_twin(client, actor["did"], name="Twin B")
        r = await client.get("/twins")
        assert r.status_code == 200
        assert len(r.json()) >= 2

    async def test_get_twin_not_found(self, client: AsyncClient):
        r = await client.get("/twins/did:key:zNONEXISTENT")
        assert r.status_code == 404

    async def test_parent_child_bom(self, client: AsyncClient):
        oem = await create_actor(client, "OEM_MANUFACTURER")
        cell = await create_twin(client, oem["did"], name="Cell", product_type="EV_BATTERY_CELL")
        pack = await create_twin(client, oem["did"], name="Pack",
                                 product_type="BATTERY_PACK",
                                 parent_twin_id=cell["id"])
        assert pack["parent_twin_id"] == cell["id"]

        # Verify children endpoint
        r = await client.get(f"/twins/{cell['id']}/children")
        assert any(c["id"] == pack["id"] for c in r.json())


@pytest.mark.asyncio
class TestStateEngine:
    """Verify the state engine correctly reduces events over the baseline."""

    async def test_telemetry_updates_soh(self, client: AsyncClient):
        oem = await create_actor(client, "OEM_MANUFACTURER")
        twin = await create_twin(client, oem["did"], initial_capacity_kwh=75.0)
        twin_id = twin["id"]
        tech = await create_actor(client, "FIELD_TECHNICIAN")

        r = await client.post("/events", json=_event(
            twin_id, "TELEMETRY_SNAPSHOT", tech["did"], tech["private_key_hex"],
            {"soh_pct": 68.0, "capacity_kwh": 51.0}
        ))
        assert r.status_code == 201

        updated = await client.get(f"/twins/{twin_id}")
        data = updated.json()
        assert data["current_soh_pct"] == 68.0
        assert data["current_capacity_kwh"] == 51.0
        assert data["status"] == "UNSUITABLE_FOR_AUTOMOTIVE"

    async def test_repair_updates_chemistry(self, client: AsyncClient):
        oem = await create_actor(client, "OEM_MANUFACTURER")
        twin = await create_twin(client, oem["did"], baseline_chemistry={"NMC_811": 0.85})
        twin_id = twin["id"]
        tech = await create_actor(client, "FIELD_TECHNICIAN")

        r = await client.post("/events", json=_event(
            twin_id, "REPAIR_PART_SWAP", tech["did"], tech["private_key_hex"],
            {"new_chemistry": {"LFP": 0.90}, "new_part_serial": "SN-OK-123"}
        ))
        assert r.status_code == 201

        updated = (await client.get(f"/twins/{twin_id}")).json()
        # LFP should now be present in current_chemistry
        assert "LFP" in updated["current_chemistry"]

    async def test_second_life_below_threshold(self, client: AsyncClient):
        oem = await create_actor(client, "OEM_MANUFACTURER")
        twin = await create_twin(client, oem["did"], initial_capacity_kwh=50.0)
        twin_id = twin["id"]
        tech = await create_actor(client, "FIELD_TECHNICIAN")

        await client.post("/events", json=_event(
            twin_id, "TELEMETRY_SNAPSHOT", tech["did"], tech["private_key_hex"],
            {"soh_pct": 55.0}
        ))
        r = await client.get(f"/twins/{twin_id}/second-life")
        data = r.json()
        assert data["suitable_for_automotive"] is False
        assert data["suitable_for_stationary_storage"] is True

    async def test_recycling_matrix_has_hazards(self, client: AsyncClient):
        oem = await create_actor(client, "OEM_MANUFACTURER")
        twin = await create_twin(client, oem["did"],
                                 material_weights_kg={"lithium": 2.1, "cobalt": 1.3, "flame_retardant": 0.5})
        r = await client.get(f"/twins/{twin['id']}/recycling")
        data = r.json()
        hazard_names = [h["material"] for h in data["hazardous_materials"]]
        assert "lithium" in hazard_names
        assert "cobalt" in hazard_names
        assert len(data["disassembly_sequence"]) > 0
