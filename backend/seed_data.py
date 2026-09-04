"""Seed script to populate the database with realistic supply-chain twins and events."""
import asyncio
import base64
import json
import time
from datetime import datetime, timezone, timedelta

import httpx

BASE = "http://127.0.0.1:8000"

# ── Helpers ────────────────────────────────────────────────────────────────────

def sign_payload(private_key_hex: str, payload_bytes: bytes) -> str:
    """Sign bytes with Ed25519 private key and return base64url signature."""
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    priv = Ed25519PrivateKey.from_private_bytes(bytes.fromhex(private_key_hex))
    sig = priv.sign(payload_bytes)
    return base64.urlsafe_b64encode(sig).decode()


def canonical_payload(twin_id: str, event_type: str, actor_did: str,
                      actor_timestamp: str, metadata_json: dict) -> bytes:
    """Build the canonical payload bytes for signing."""
    obj = {
        "twin_id": twin_id,
        "event_type": event_type,
        "actor_did": actor_did,
        "actor_timestamp": actor_timestamp,
        "metadata_json": metadata_json,
    }
    return json.dumps(obj, sort_keys=True, separators=(",", ":")).encode()


async def register_actor(client: httpx.AsyncClient, name: str, role: str) -> dict:
    await asyncio.sleep(0.2)
    resp = await client.post(f"{BASE}/actors", json={"display_name": name, "role": role})
    resp.raise_for_status()
    return resp.json()


async def create_twin(client: httpx.AsyncClient, actor_did: str, payload: dict) -> dict:
    await asyncio.sleep(0.2)
    resp = await client.post(f"{BASE}/twins", params={"actor_did": actor_did}, json=payload)
    resp.raise_for_status()
    return resp.json()


async def append_event(client: httpx.AsyncClient, private_key_hex: str,
                       twin_id: str, event_type: str, actor_did: str,
                       metadata: dict, ts: datetime = None) -> dict:
    if ts is None:
        ts = datetime.now(timezone.utc)
    ts_str = ts.isoformat()
    payload_bytes = canonical_payload(twin_id, event_type, actor_did, ts_str, metadata)
    sig = sign_payload(private_key_hex, payload_bytes)
    body = {
        "twin_id": twin_id,
        "event_type": event_type,
        "actor_did": actor_did,
        "actor_timestamp": ts_str,
        "metadata_json": metadata,
        "cryptographic_signature": sig,
    }
    await asyncio.sleep(0.2)
    resp = await client.post(f"{BASE}/events", json=body)
    if resp.status_code >= 400:
        print(f"    ERROR {resp.status_code}: {resp.text}")
    resp.raise_for_status()
    return resp.json()


# ── Seed Data ──────────────────────────────────────────────────────────────────

async def seed():
    async with httpx.AsyncClient(timeout=30) as c:

        # Health check
        h = await c.get(f"{BASE}/health")
        print(f"Backend: {h.json()}")

        # ── 1. Register Actors ───────────────────────────────────────────────
        print("\n=== Registering Actors ===")
        supplier  = await register_actor(c, "Congo Mining Corp", "RAW_MATERIAL_SUPPLIER")
        supplier2 = await register_actor(c, "Chile Lithium Ltd", "RAW_MATERIAL_SUPPLIER")
        oem       = await register_actor(c, "VoltDrive Motors", "OEM_MANUFACTURER")
        oem2      = await register_actor(c, "GreenCell Energy", "OEM_MANUFACTURER")
        tech      = await register_actor(c, "FieldOps Technician Alpha", "FIELD_TECHNICIAN")
        tech2     = await register_actor(c, "FieldOps Technician Beta", "FIELD_TECHNICIAN")
        recycler  = await register_actor(c, "EcoRecycle GmbH", "RECYCLER_DISMANTLER")

        actors = {
            "supplier": supplier, "supplier2": supplier2,
            "oem": oem, "oem2": oem2,
            "tech": tech, "tech2": tech2,
            "recycler": recycler,
        }
        for k, v in actors.items():
            print(f"  {k}: {v['actor']['did'][:40]}… ({v['actor']['role']})")

        # ── 2. Create Raw Material Twins (Supplier) ──────────────────────────
        print("\n=== Creating Raw Material Twins ===")
        now = datetime.now(timezone.utc)

        uid = int(now.timestamp())

        lithium_batch = await create_twin(c, supplier2["did"], {
            "name": "Lithium Carbonate Batch LC-2025-0412",
            "product_type": "LITHIUM_CARBONATE",
            "serial_number": f"LC-2025-0412-{uid}",
            "manufacturing_date": "2025-04-12T08:00:00Z",
            "material_weights_kg": {"lithium": 500.0, "carbon": 136.0, "oxygen": 214.0},
            "baseline_chemistry": {"Li2CO3": 0.995, "impurities": 0.005},
            "initial_safety_rating": "CLASS_9_UN3480",
        })
        print(f"  Lithium batch: {lithium_batch['id'][:40]}…")

        cobalt_batch = await create_twin(c, supplier["did"], {
            "name": "Cobalt Sulphate Batch CS-2025-0301",
            "product_type": "COBALT_SULPHATE",
            "serial_number": f"CS-2025-0301-{uid}",
            "manufacturing_date": "2025-03-01T10:00:00Z",
            "material_weights_kg": {"cobalt": 300.0, "sulphur": 164.0, "oxygen": 256.0},
            "baseline_chemistry": {"CoSO4": 0.98, "nickel_trace": 0.02},
            "initial_safety_rating": "CLASS_9_UN3288",
        })
        print(f"  Cobalt batch: {cobalt_batch['id'][:40]}…")

        nickel_batch = await create_twin(c, supplier["did"], {
            "name": "Nickel Class-1 Briquettes NB-2025-0215",
            "product_type": "NICKEL_CLASS1",
            "serial_number": f"NB-2025-0215-{uid}",
            "manufacturing_date": "2025-02-15T06:00:00Z",
            "material_weights_kg": {"nickel": 1000.0, "iron": 2.5, "cobalt": 0.8},
            "baseline_chemistry": {"Ni": 0.9965, "Fe": 0.0025, "Co": 0.0008},
            "initial_safety_rating": "CLASS_9_UN3077",
        })
        print(f"  Nickel batch: {nickel_batch['id'][:40]}…")

        graphite_batch = await create_twin(c, supplier2["did"], {
            "name": "Synthetic Graphite Anode Material SG-2025-0501",
            "product_type": "GRAPHITE_ANODE",
            "serial_number": f"SG-2025-0501-{uid}",
            "manufacturing_date": "2025-05-01T12:00:00Z",
            "material_weights_kg": {"graphite": 800.0, "silicon_oxide": 40.0},
            "baseline_chemistry": {"C_graphite": 0.952, "SiO2": 0.048},
            "initial_safety_rating": "NON_HAZARDOUS",
        })
        print(f"  Graphite batch: {graphite_batch['id'][:40]}…")

        # ── 3. Create Battery Cell Twins (OEM — children of raw materials) ───
        print("\n=== Creating Battery Cell Twins ===")

        cell_1 = await create_twin(c, oem["did"], {
            "name": "NMC-811 Cell Module A (VoltDrive Model Y)",
            "product_type": "EV_BATTERY_CELL",
            "parent_twin_id": lithium_batch["id"],
            "serial_number": f"VD-CELL-A-{uid}-001",
            "manufacturing_date": "2025-06-01T09:00:00Z",
            "material_weights_kg": {"lithium": 2.1, "cobalt": 1.3, "nickel": 4.5, "manganese": 0.5, "graphite": 3.2},
            "baseline_chemistry": {"NMC_811": 0.65, "graphite": 0.28, "electrolyte": 0.07},
            "initial_capacity_kwh": 5.2,
            "initial_safety_rating": "UL2580_CERTIFIED",
        })
        print(f"  Cell A: {cell_1['id'][:40]}… (5.2 kWh)")

        cell_2 = await create_twin(c, oem["did"], {
            "name": "NMC-811 Cell Module B (VoltDrive Model Y)",
            "product_type": "EV_BATTERY_CELL",
            "parent_twin_id": cobalt_batch["id"],
            "serial_number": f"VD-CELL-B-{uid}-002",
            "manufacturing_date": "2025-06-15T10:00:00Z",
            "material_weights_kg": {"lithium": 2.1, "cobalt": 1.3, "nickel": 4.5, "manganese": 0.5, "graphite": 3.2},
            "baseline_chemistry": {"NMC_811": 0.65, "graphite": 0.28, "electrolyte": 0.07},
            "initial_capacity_kwh": 5.2,
            "initial_safety_rating": "UL2580_CERTIFIED",
        })
        print(f"  Cell B: {cell_2['id'][:40]}… (5.2 kWh)")

        cell_3 = await create_twin(c, oem2["did"], {
            "name": "LFP Cell Module (GreenCell Grid Storage)",
            "product_type": "STATIONARY_BATTERY_CELL",
            "serial_number": f"GC-LFP-{uid}-001",
            "manufacturing_date": "2025-04-01T08:00:00Z",
            "material_weights_kg": {"lithium": 1.8, "iron": 5.6, "phosphate": 3.1, "graphite": 2.8},
            "baseline_chemistry": {"LFP": 0.60, "graphite": 0.30, "electrolyte": 0.10},
            "initial_capacity_kwh": 3.8,
            "initial_safety_rating": "IEC62619_CERTIFIED",
        })
        print(f"  LFP Cell: {cell_3['id'][:40]}… (3.8 kWh)")

        # ── 4. Create Battery Pack Twin (OEM — parent of cells) ──────────────
        print("\n=== Creating Battery Pack Twin ===")

        pack_1 = await create_twin(c, oem["did"], {
            "name": "VoltDrive 75kWh Battery Pack (Model Y Long Range)",
            "product_type": "BATTERY_PACK",
            "parent_twin_id": cell_1["id"],
            "serial_number": f"VD-PACK-75-LR-{uid}-0042",
            "manufacturing_date": "2025-07-10T14:00:00Z",
            "material_weights_kg": {"lithium": 30.0, "cobalt": 18.0, "nickel": 62.0, "aluminium": 45.0, "copper": 22.0},
            "baseline_chemistry": {"NMC_811": 0.65, "graphite": 0.28, "electrolyte": 0.07},
            "initial_capacity_kwh": 75.0,
            "initial_safety_rating": "UN38.3_PASSED",
        })
        print(f"  Pack: {pack_1['id'][:40]}… (75 kWh)")

        pack_2 = await create_twin(c, oem2["did"], {
            "name": "GreenCell MegaPack 500kWh (Grid Storage)",
            "product_type": "GRID_STORAGE_PACK",
            "parent_twin_id": cell_3["id"],
            "serial_number": f"GC-MEGA-500-{uid}-007",
            "manufacturing_date": "2025-08-01T10:00:00Z",
            "material_weights_kg": {"lithium": 120.0, "iron": 380.0, "phosphate": 210.0, "aluminium": 200.0},
            "baseline_chemistry": {"LFP": 0.60, "graphite": 0.30, "electrolyte": 0.10},
            "initial_capacity_kwh": 500.0,
            "initial_safety_rating": "UL9540_CERTIFIED",
        })
        print(f"  Grid Pack: {pack_2['id'][:40]}… (500 kWh)")

        # ── 5. Create EV Twin (OEM — top-level product) ──────────────────────
        print("\n=== Creating EV Twin ===")

        ev_1 = await create_twin(c, oem["did"], {
            "name": "VoltDrive Model Y Long Range 2025 (VIN: VD5YLR2025A0042)",
            "product_type": "EV",
            "parent_twin_id": pack_1["id"],
            "serial_number": f"VD5YLR{uid}A0042",
            "manufacturing_date": "2025-08-15T16:00:00Z",
            "material_weights_kg": {"battery": 480.0, "steel": 850.0, "aluminium": 220.0, "copper": 80.0, "plastics": 150.0},
            "initial_safety_rating": "EURO_NCAP_5_STAR",
        })
        print(f"  EV: {ev_1['id'][:40]}…")

        # ── 6. Append Lifecycle Events ───────────────────────────────────────
        print("\n=== Appending Lifecycle Events ===")
        base_time = now - timedelta(seconds=30)

        # Extraction events for raw materials
        await append_event(c, supplier2["private_key_hex"], lithium_batch["id"],
                           "EXTRACTION", supplier2["did"], {
                               "mine_location": "Salar de Atacama, Chile",
                               "extraction_method": "brine_evaporation",
                               "purity_pct": 99.5,
                               "batch_weight_kg": 850.0,
                           }, base_time)
        print("  ✓ EXTRACTION event: Lithium batch")

        await append_event(c, supplier["private_key_hex"], cobalt_batch["id"],
                           "EXTRACTION", supplier["did"], {
                               "mine_location": "Kolwezi, DRC",
                               "extraction_method": "artisanal_and_industrial",
                               "purity_pct": 98.0,
                               "batch_weight_kg": 720.0,
                               "conflict_free_certified": True,
                           }, base_time + timedelta(seconds=5))
        print("  ✓ EXTRACTION event: Cobalt batch")

        await append_event(c, supplier["private_key_hex"], nickel_batch["id"],
                           "EXTRACTION", supplier["did"], {
                               "mine_location": "Sudbury, Ontario, Canada",
                               "extraction_method": "underground_mining",
                               "purity_pct": 99.65,
                               "batch_weight_kg": 1003.3,
                           }, base_time + timedelta(seconds=10))
        print("  ✓ EXTRACTION event: Nickel batch")

        # Custody transfer: supplier → OEM
        await append_event(c, supplier2["private_key_hex"], lithium_batch["id"],
                           "CUSTODY_TRANSFER", supplier2["did"], {
                               "from_party": "Chile Lithium Ltd",
                               "to_party": "VoltDrive Motors",
                               "destination": "Gigafactory Berlin, Germany",
                               "transport_mode": "maritime_freight",
                           }, base_time + timedelta(seconds=15))
        print("  ✓ CUSTODY_TRANSFER: Lithium → VoltDrive")

        await append_event(c, supplier["private_key_hex"], cobalt_batch["id"],
                           "CUSTODY_TRANSFER", supplier["did"], {
                               "from_party": "Congo Mining Corp",
                               "to_party": "VoltDrive Motors",
                               "destination": "Gigafactory Berlin, Germany",
                               "transport_mode": "air_freight",
                           }, base_time + timedelta(seconds=20))
        print("  ✓ CUSTODY_TRANSFER: Cobalt → VoltDrive")

        # Assembly event for pack
        await append_event(c, oem["private_key_hex"], pack_1["id"],
                           "ASSEMBLY", oem["did"], {
                               "assembly_line": "Line-7, Gigafactory Berlin",
                               "cell_count": 4416,
                               "configuration": "110s40p",
                               "bom_child_ids": [cell_1["id"], cell_2["id"]],
                               "quality_check": "PASSED",
                           }, base_time + timedelta(seconds=25))
        print("  ✓ ASSEMBLY event: Battery Pack")

        # Telemetry snapshots for the EV pack
        telemetry_readings = [
            {"temperature_celsius": 28.5, "voltage_v": 3.82, "current_a": 45.0, "soh_pct": 99.8, "capacity_kwh": 74.8},
            {"temperature_celsius": 32.1, "voltage_v": 3.75, "current_a": 120.0, "soh_pct": 99.5, "capacity_kwh": 74.6},
            {"temperature_celsius": 38.7, "voltage_v": 3.65, "current_a": 200.0, "soh_pct": 99.1, "capacity_kwh": 74.3},
            {"temperature_celsius": 25.2, "voltage_v": 3.90, "current_a": -30.0, "soh_pct": 99.0, "capacity_kwh": 74.2},
        ]
        for i, reading in enumerate(telemetry_readings):
            await append_event(c, tech["private_key_hex"], pack_1["id"],
                               "TELEMETRY_SNAPSHOT", tech["did"],
                               reading, base_time + timedelta(seconds=30+i*5))
        print(f"  ✓ {len(telemetry_readings)} TELEMETRY_SNAPSHOT events: Battery Pack")

        # Repair event on cell
        await append_event(c, tech2["private_key_hex"], cell_2["id"],
                           "REPAIR_PART_SWAP", tech2["did"], {
                               "repaired_component": "thermal_management_sensor",
                               "old_part_serial": "TMS-2025-0041",
                               "new_part_serial": "TMS-2025-0099",
                               "repair_location": "Service Center Munich",
                               "warranty_claim": True,
                           }, base_time + timedelta(seconds=55))
        print("  ✓ REPAIR_PART_SWAP event: Cell B")

        # Telemetry for grid storage pack
        grid_readings = [
            {"temperature_celsius": 22.0, "voltage_v": 3.45, "current_a": 500.0, "soh_pct": 99.9, "capacity_kwh": 499.5},
            {"temperature_celsius": 24.3, "voltage_v": 3.40, "current_a": 480.0, "soh_pct": 99.7, "capacity_kwh": 498.5},
        ]
        for i, reading in enumerate(grid_readings):
            await append_event(c, tech["private_key_hex"], pack_2["id"],
                               "TELEMETRY_SNAPSHOT", tech["did"],
                               reading, base_time + timedelta(seconds=60+i*5))
        print(f"  ✓ {len(grid_readings)} TELEMETRY_SNAPSHOT events: Grid Pack")

        # Custody transfer: OEM → Recycler (for decommissioned pack scenario)
        await append_event(c, oem["private_key_hex"], cell_3["id"],
                           "CUSTODY_TRANSFER", oem["did"], {
                               "from_party": "GreenCell Energy",
                               "to_party": "EcoRecycle GmbH",
                               "destination": "Recycling Facility, Hamburg",
                               "reason": "end_of_life_evaluation",
                           }, base_time + timedelta(seconds=75))
        print("  ✓ CUSTODY_TRANSFER: LFP Cell → EcoRecycle")

        # ── 7. Summary ───────────────────────────────────────────────────────
        print("\n=== Seed Complete ===")
        twins_resp = await c.get(f"{BASE}/twins", params={"limit": 200})
        twins = twins_resp.json()
        print(f"  Total twins: {len(twins)}")
        for t in twins:
            print(f"    [{t['product_type']}] {t['name']}")
            print(f"      Status: {t['status']} | SoH: {t.get('current_soh_pct', 'N/A')}% | ID: {t['id'][:50]}…")

        print("\n=== Public passport URLs ===")
        for t in twins[:3]:
            print(f"  http://localhost:3000/passport/{t['id']}")

        print("\nDone!")


if __name__ == "__main__":
    asyncio.run(seed())
