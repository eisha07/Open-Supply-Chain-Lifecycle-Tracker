# Use Cases & Instructions for Real Products

Practical guide to using the OSLT platform for actual products across industries.

---

## Table of Contents

1. [EV Battery Manufacturing](#1-ev-battery-manufacturing)
2. [Grid-Scale Energy Storage](#2-grid-scale-energy-storage)
3. [Consumer Electronics (Laptops, Phones)](#3-consumer-electronics)
4. [Critical Raw Material Tracking](#4-critical-raw-material-tracking)
5. [Aerospace & Defence Components](#5-aerospace--defence-components)
6. [Medical Device Batteries](#6-medical-device-batteries)
7. [Solar Panel Supply Chain](#7-solar-panel-supply-chain)
8. [Second-Life & Circular Economy](#8-second-life--circular-economy)

---

## 1. EV Battery Manufacturing

**Scenario:** An OEM manufactures EV battery packs from raw materials sourced globally, and needs to provide EU Battery Regulation-compliant Digital Product Passports.

### Setup

```bash
# 1. Register your supply-chain actors
curl -X POST http://localhost:8000/actors \
  -H "Content-Type: application/json" \
  -d '{"display_name": "Your Mining Supplier", "role": "RAW_MATERIAL_SUPPLIER"}'

curl -X POST http://localhost:8000/actors \
  -H "Content-Type: application/json" \
  -d '{"display_name": "Your EV OEM", "role": "OEM_MANUFACTURER"}'

curl -X POST http://localhost:8000/actors \
  -H "Content-Type: application/json" \
  -d '{"display_name": "Service Technician", "role": "FIELD_TECHNICIAN"}'
```

> **Important:** Save the `private_key_hex` returned at registration — it's shown only once.

### Step-by-Step Workflow

**Step 1 — Supplier creates raw material twin:**
```bash
curl -X POST "http://localhost:8000/twins?actor_did=<SUPPLIER_DID>" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Lithium Carbonate Batch LC-2025-0412",
    "product_type": "LITHIUM_CARBONATE",
    "serial_number": "LC-2025-0412",
    "manufacturing_date": "2025-04-12T08:00:00Z",
    "material_weights_kg": {"lithium": 500.0, "carbon": 136.0, "oxygen": 214.0},
    "baseline_chemistry": {"Li2CO3": 0.995, "impurities": 0.005},
    "initial_safety_rating": "CLASS_9_UN3480"
  }'
```

**Step 2 — Supplier records extraction event:**
```bash
# First, build the canonical payload and sign it with the supplier's private key
# Canonical format: {"actor_did":"...","actor_timestamp":"...","event_type":"EXTRACTION","metadata_json":{...},"twin_id":"..."}
# Sign with Ed25519 and base64url-encode

curl -X POST http://localhost:8000/events \
  -H "Content-Type: application/json" \
  -d '{
    "twin_id": "<LITHIUM_TWIN_ID>",
    "event_type": "EXTRACTION",
    "actor_did": "<SUPPLIER_DID>",
    "actor_timestamp": "2025-04-12T10:00:00Z",
    "metadata_json": {
      "mine_location": "Salar de Atacama, Chile",
      "extraction_method": "brine_evaporation",
      "purity_pct": 99.5,
      "conflict_free_certified": true
    },
    "cryptographic_signature": "<BASE64URL_ED25519_SIGNATURE>"
  }'
```

**Step 3 — OEM creates battery cell twin (child of raw material):**
```bash
curl -X POST "http://localhost:8000/twins?actor_did=<OEM_DID>" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "NMC-811 Cell Module A",
    "product_type": "EV_BATTERY_CELL",
    "parent_twin_id": "<LITHIUM_TWIN_ID>",
    "serial_number": "VD-CELL-A-001",
    "material_weights_kg": {"lithium": 2.1, "cobalt": 1.3, "nickel": 4.5},
    "baseline_chemistry": {"NMC_811": 0.65, "graphite": 0.28, "electrolyte": 0.07},
    "initial_capacity_kwh": 5.2,
    "initial_safety_rating": "UL2580_CERTIFIED"
  }'
```

**Step 4 — OEM assembles battery pack and records event:**
```bash
curl -X POST http://localhost:8000/events \
  -H "Content-Type: application/json" \
  -d '{
    "twin_id": "<PACK_TWIN_ID>",
    "event_type": "ASSEMBLY",
    "actor_did": "<OEM_DID>",
    "actor_timestamp": "2025-07-10T14:30:00Z",
    "metadata_json": {
      "assembly_line": "Line-7, Gigafactory Berlin",
      "cell_count": 4416,
      "configuration": "110s40p",
      "quality_check": "PASSED"
    },
    "cryptographic_signature": "<SIGNATURE>"
  }'
```

**Step 5 — Generate ZKP compliance flags:**
```bash
curl -X POST "http://localhost:8000/twins/<PACK_TWIN_ID>/zkp?actor_did=<OEM_DID>" \
  -H "Content-Type: application/json" \
  -d '{"claims": {"is_conflict_free": true, "recycled_cobalt_pct_gte": 30}}'
```

**Step 6 — View public passport:**
Open `http://localhost:3000/passport/<PACK_TWIN_ID>` in a browser, or:
```bash
curl http://localhost:8000/passport/<PACK_TWIN_ID>
```

### Regulatory Alignment
- **EU Battery Regulation 2023/1542** — DPP requirements for batteries >2kWh
- **Carbon Border Adjustment Mechanism (CBAM)** — Material provenance tracking
- **Conflict Minerals Regulation** — Cobalt/tantalum sourcing verification

---

## 2. Grid-Scale Energy Storage

**Scenario:** A utility deploys 500kWh+ grid storage systems using LFP chemistry and needs lifecycle monitoring for warranty and safety compliance.

### Key Differences from EV
- Uses `STATIONARY_BATTERY_CELL` and `GRID_STORAGE_PACK` product types
- Larger material weights (100s of kg of lithium iron phosphate)
- Telemetry events track grid charge/discharge cycles
- IEC 62619 and UL 9540 safety ratings

### Workflow

1. **Supplier** creates LFP material batch twins
2. **OEM** creates cell twins with parent reference to raw materials
3. **OEM** assembles grid pack (parent = cell) with `ASSEMBLY` event
4. **Technician** sends periodic `TELEMETRY_SNAPSHOT` events (SoH, capacity, temperature)
5. **Recycler** receives `CUSTODY_TRANSFER` when pack reaches end-of-life
6. Use `GET /twins/<id>/second-life` to evaluate reuse pathways

### Useful Endpoints
```bash
# Monitor SoH degradation over time
curl http://localhost:8000/events/<PACK_ID>

# Get recycling guidance
curl http://localhost:8000/twins/<PACK_ID>/recycling

# Verify ledger integrity
curl http://localhost:8000/events/<PACK_ID>/verify
```

---

## 3. Consumer Electronics

**Scenario:** A laptop manufacturer needs DPP compliance for batteries >100Wh sold in the EU market.

### Adaptation
- Product types: `CONSUMER_BATTERY_CELL`, `LAPTOP_BATTERY_PACK`
- Smaller material weights (grams, not kg)
- Parent hierarchy: Cell → Pack → Laptop
- Focus on conflict-free tantalum (from capacitors) and cobalt

### Workflow
1. Supplier creates cobalt/lithium twins with mining provenance
2. OEM creates cell twins, chains custody transfers
3. OEM assembles laptop battery pack with `ASSEMBLY` event
4. Technician records `TELEMETRY_SNAPSHOT` at warranty service intervals
5. ZKP flags prove conflict-free sourcing for ESG reporting

---

## 4. Critical Raw Material Tracking

**Scenario:** A commodity trader needs to prove conflict-free sourcing of cobalt, lithium, and rare earth elements for EU import compliance.

### Workflow
1. **Register supplier** at each mine/refinery
2. **Create material batch twins** with full chemistry and weight data
3. **Record `EXTRACTION` events** with mine coordinates, extraction method, and certifications
4. **Chain `CUSTODY_TRANSFER` events** for every hand-off (mine → trader → smelter → OEM)
5. **Verify chain integrity** at any point: `GET /events/<TWIN_ID>/verify`
6. **Generate ZKP flags** to prove compliance without revealing trade secrets

### Key Metadata for Each Transfer
```json
{
  "from_party": "Mine Corp",
  "to_party": "Trading House",
  "destination": "Rotterdam, NL",
  "transport_mode": "maritime_freight",
  "customs_declaration": "EU-CN-2025-12345",
  "conflict_free_certified": true,
  "certificate_id": "RMI-AUDIT-2025-0892"
}
```

---

## 5. Aerospace & Defence Components

**Scenario:** An aerospace OEM needs full material traceability for battery systems used in aircraft or satellites.

### Adaptation
- Product type: `AEROSPACE_BATTERY_SYSTEM`
- Stricter safety ratings (DO-311A, RTCA standards)
- Every component swap must be recorded with certified part serials
- `REPAIR_PART_SWAP` events are critical — counterfeit detection catches unauthorised parts

### Workflow
1. Create twins with `initial_safety_rating: "DO311A_CERTIFIED"`
2. Every maintenance event → `REPAIR_PART_SWAP` with certified part serial
3. Counterfeit parts are auto-detected via blacklisted serial registry
4. Twin status auto-transitions to `TAMPERED_SAFETY_RISK` if unauthorised parts detected

---

## 6. Medical Device Batteries

**Scenario:** Medical device manufacturers need battery traceability for FDA/CE marking compliance.

### Adaptation
- Product type: `MEDICAL_BATTERY_PACK`
- Safety rating: IEC 62133, UL 2054
- Smaller, high-reliability cells
- Critical for devices like defibrillators, insulin pumps, surgical tools

### Workflow
1. Supplier creates cell twins with full chemistry traceability
2. OEM assembles medical battery packs with quality gate events
3. Each calibration/service event → `TELEMETRY_SNAPSHOT` with SoH data
4. End-of-life → `DECOMMISSION` event by certified recycler
5. Public passport provides auditors with full provenance without revealing suppliers

---

## 7. Solar Panel Supply Chain

**Scenario:** Track photovoltaic panels from polysilicon through cell manufacturing to installed modules.

### Adaptation
- Product types: `POLYSILICON_BATCH`, `SOLAR_CELL`, `SOLAR_MODULE`
- Material weights: silicon, silver paste, glass, aluminium frame
- Chemistry: monocrystalline vs polycrystalline percentages

### Workflow
1. Supplier creates polysilicon batch twin with purity data
2. Cell manufacturer creates solar cell twins (child of polysilicon)
3. Module assembler creates module twin (parent = cell)
4. Telemetry snapshots track degradation (power output vs nameplate)
5. Recycling matrix identifies recoverable materials (silicon, silver, glass)

---

## 8. Second-Life & Circular Economy

**Scenario:** An EV battery pack reaches 70% SoH — no longer suitable for automotive use but viable for stationary storage.

### Workflow

**Step 1 — Check second-life recommendation:**
```bash
curl http://localhost:8000/twins/<PACK_ID>/second-life
```
Response includes:
- `suitable_for_automotive`: false (below 80% threshold)
- `suitable_for_stationary_storage`: true
- `recommendation`: "RECOMMENDED_FOR_STATIONARY_STORAGE"

**Step 2 — Get recycling matrix (if not suitable for reuse):**
```bash
curl http://localhost:8000/twins/<PACK_ID>/recycling
```
Returns:
- Hazardous materials identification
- Target metal recovery percentages
- Disassembly sequence with safety instructions
- PPE requirements per step

**Step 3 — Record custody transfer to recycler:**
```bash
curl -X POST http://localhost:8000/events \
  -H "Content-Type: application/json" \
  -d '{
    "twin_id": "<PACK_ID>",
    "event_type": "CUSTODY_TRANSFER",
    "actor_did": "<OEM_DID>",
    "actor_timestamp": "2026-01-15T10:00:00Z",
    "metadata_json": {
      "from_party": "VoltDrive Motors",
      "to_party": "EcoRecycle GmbH",
      "reason": "second_life_redeployment"
    },
    "cryptographic_signature": "<SIGNATURE>"
  }'
```

**Step 4 — Recycler decommissions or redeploys:**
```bash
curl -X POST http://localhost:8000/events \
  -H "Content-Type: application/json" \
  -d '{
    "twin_id": "<PACK_ID>",
    "event_type": "DECOMMISSION",
    "actor_did": "<RECYCLER_DID>",
    "actor_timestamp": "2026-02-01T09:00:00Z",
    "metadata_json": {
      "disposition": "repurposed_for_stationary_storage",
      "new_application": "grid_peak_shaving",
      "expected_additional_years": 8,
      "materials_recovered_pct": 0
    },
    "cryptographic_signature": "<SIGNATURE>"
  }'
```

---

## Signing Events — How It Works

Every event must be cryptographically signed by the submitting actor. Here's how:

### Python Example
```python
import base64, json
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

# Your private key (from actor registration — stored securely)
private_key = Ed25519PrivateKey.from_private_bytes(bytes.fromhex("YOUR_PRIVATE_KEY_HEX"))

# Build canonical payload (sorted keys, compact JSON)
canonical = json.dumps({
    "actor_did": "did:key:z6Mk...",
    "actor_timestamp": "2025-08-30T12:00:00+00:00",
    "event_type": "EXTRACTION",
    "metadata_json": {"mine_location": "Chile", "purity_pct": 99.5},
    "twin_id": "did:key:z6Mk...",
}, sort_keys=True, separators=(",", ":")).encode()

# Sign and encode
signature = base64.urlsafe_b64encode(private_key.sign(canonical)).decode()
```

### Using the Seed Script
The included `backend/seed_data.py` handles all signing automatically. Run it inside Docker:
```bash
docker cp backend/seed_data.py chat-1-backend-1:/app/seed_data.py
docker exec chat-1-backend-1 python /app/seed_data.py
```

---

## API Quick Reference

| Action | Endpoint | Auth |
|---|---|---|
| Register actor | `POST /actors` | None |
| Create twin | `POST /twins?actor_did=...` | Actor DID |
| Append event | `POST /events` | Signed payload |
| List twins | `GET /twins` | None |
| Get twin details | `GET /twins/{id}` | None |
| Get BOM children | `GET /twins/{id}/children` | None |
| Get event history | `GET /events/{id}` | None |
| Verify chain integrity | `GET /events/{id}/verify` | None |
| Generate ZKP flags | `POST /twins/{id}/zkp` | OEM role |
| Second-life estimate | `GET /twins/{id}/second-life` | None |
| Recycling matrix | `GET /twins/{id}/recycling` | None |
| Public passport | `GET /passport/{id}` | None |
| Blacklist actor | `POST /actors/{did}/blacklist` | None (admin in prod) |

---

## Frontend Dashboard Guide

| Dashboard | URL | Who Uses It | What It Does |
|---|---|---|---|
| Home | `http://localhost:3000` | Anyone | Role selector, feature overview, QR scanner |
| Supplier | `/dashboard/supplier` | Raw material suppliers | Create material batch twins |
| OEM | `/dashboard/oem` | Manufacturers | Create BOM twins, generate ZKP flags |
| Technician | `/dashboard/technician` | Field engineers | View telemetry, offline event queue |
| Recycler | `/dashboard/recycler` | Recyclers/dismantlers | Recycling matrix, second-life estimates |
| Passport | `/passport/{twin_id}` | Public / regulators | DPP view with compliance badges |
