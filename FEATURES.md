# Implemented Features

A comprehensive inventory of every feature currently built into the OSLT platform.

---

## Backend API

### Authentication (`backend/app/routers/auth.py`)

| Endpoint | Method | Description |
|---|---|---|
| `/auth/challenge` | POST | Request a server nonce for DID-based authentication. Accepts `actor_did` and `role`; auto-registers unknown actors on first call. |
| `/auth/token` | POST | Exchange actor DID, role, challenge nonce, and Ed25519 signature for a JWT access token (default 1h TTL). |

- **JWT access tokens** — Industry-standard JWT with `sub` (actor DID), `role`, `jti` (unique ID), `exp` claims
- **Challenge-response flow** — Server nonce prevents replay attacks; signature proves key ownership
- **Auto-registration** — Unknown actors are automatically registered on first challenge request
- **Token blacklisting** — Per-token revocation via Redis or in-memory set

### Actor Management (`backend/app/routers/actors.py`)

| Endpoint | Method | Description |
|---|---|---|
| `/actors` | POST | Register a new supply-chain actor. Generates an Ed25519 keypair, derives a `did:key` DID, and returns the private key once (never persisted). |
| `/actors/{did}` | GET | Look up an actor by their DID. **Protected:** requires `admin` role or self-lookup. |
| `/actors/{did}/blacklist` | POST | Revoke an actor's access. **Protected:** requires `admin` role. Blacklists DID across auth and JWT middleware. |

### Digital Twin Management (`backend/app/routers/twins.py`)

| Endpoint | Method | Description |
|---|---|---|
| `/twins` | POST | Create a new Digital Twin with optional `parent_twin_id` for hierarchical BOM support. **Protected:** requires `supplier` or `oem` role. |
| `/twins` | GET | List all twins with optional filtering by `product_type` and `status`. Supports pagination. API key auth for read access. |
| `/twins/{twin_id}` | GET | Retrieve full twin state with Redis cache (60s TTL). API key auth. |
| `/twins/{twin_id}/children` | GET | List child twins in the BOM hierarchy. API key auth. |
| `/twins/{twin_id}/zkp` | POST | Generate zero-knowledge proof selective-disclosure flags. **Protected:** requires `oem` role. |
| `/twins/{twin_id}/second-life` | GET | Get secondary-market reuse recommendation. API key auth. |
| `/twins/{twin_id}/recycling` | GET | Generate an automated dismantling/recycling matrix. API key auth. |

### Event Ledger (Append-Only) (`backend/app/routers/events.py`)

| Endpoint | Method | Description |
|---|---|---|
| `/events` | POST | Append an event to the ledger. **Protected:** role-based. Runs validation pipeline: actor verification, timestamp freshness, Ed25519 signature, optimistic concurrency, telemetry anomaly detection, counterfeit part detection, provenance gap detection. Uses **incremental state engine** for O(1) state updates. Invalidates Redis cache after mutation. |
| `/events/{twin_id}` | GET | Retrieve event history with pagination. Redis cache (30s TTL) for unfiltered reads. API key auth. |
| `/events/{twin_id}/verify` | GET | Recompute and verify SHA-256 chain-hash integrity across the entire event ledger. API key auth. |

### Public Digital Product Passport (`backend/app/routers/passport.py`)

| Endpoint | Method | Description |
|---|---|---|
| `/passport/{twin_id}` | GET | Public, sanitized view of a twin with **ETag + Cache-Control** headers and Redis cache (60s TTL). API key auth. |
| `/passport/{twin_id}/timeline` | GET | Public event timeline with masked DIDs, excluded SECURITY_ALERT events, compliance badges. Optimized **COUNT(\*)** pagination. API key auth. |

### Telemetry & IoT (`backend/app/routers/telemetry_ws.py`)

| Endpoint | Method | Description |
|---|---|---|
| `/telemetry/ws/{twin_id}` | WebSocket | Streams mock BMS telemetry at 1-second intervals. **Connection pooling** (max 5 per twin, 100 total). DB session released after initial lookup. Auto-stops after 300 messages. |
| `/telemetry/batch` | POST | Offline-first batch sync. **Protected:** role-based. Processes events one-by-one with per-event error handling. |

### System (`backend/app/main.py`)

| Endpoint | Method | Description |
|---|---|---|
| `/health` | GET | Enhanced health check: status, version (1.2.0), uptime, Redis connectivity, WebSocket connection count, cache enabled. |
| `/docs` | GET | Swagger UI (JWT Bearer auth pre-configured). |
| `/redoc` | GET | ReDoc API documentation. |

---

## Cryptographic Services

### Ed25519 Cryptography (`backend/app/services/crypto.py`)

- **Keypair generation** — Ed25519 keypairs for all supply-chain actors
- **DID derivation** — `did:key` method identifiers from public keys
- **Canonical payload serialization** — Deterministic JSON for signature consistency
- **Signature verification** — Ed25519 signature validation on every event submission
- **Timestamp freshness checks** — Configurable replay-attack window (default 300s)

### State Engine (`backend/app/services/state_engine.py`)

- **Full event replay** — `reduce_events()` replays complete history for cold-start or initial materialization
- **Incremental state reduction** — `reduce_incremental()` starts from twin's current materialized state, only processes new delta events — **O(1)** for single-event appends instead of O(n)
- **SoH tracking** — State of Health percentage and capacity degradation
- **Status transitions** — Automatic status updates based on SoH thresholds (ACTIVE → DEGRADED → END_OF_LIFE)
- **Recyclability scoring** — Heuristic score based on material composition and event history
- **Provenance gap detection** — Flags non-consecutive sequence numbers in event chains

### Zero-Knowledge Proof Flags (`backend/app/services/zkp.py`)

- **Selective disclosure** — Mock ZKP commitment hashes for:
  - Conflict-free sourcing verification
  - Recycled content threshold compliance
  - EU regulatory compliance flags

### Second-Life Estimation (`backend/app/services/second_life.py`)

- **Reuse pathway recommendation** — Based on SoH percentage, repair count, and tamper status
- **Market viability scoring** — Evaluates secondary-market suitability

### Recycling Matrix (`backend/app/services/recycling_matrix.py`)

- **Dismantling guide generation** — Automated material-specific disassembly sequences
- **Hazard identification** — Flags hazardous materials in the BOM
- **Target metal recovery** — Identifies high-value metals for recovery
- **Safety recommendations** — PPE and handling instructions per material type

---

## Security & Middleware

### JWT Authentication (`backend/app/routers/auth.py`, `backend/app/dependencies.py`)

- **Challenge-response flow** — Server nonce prevents replay attacks
- **Ed25519 signature proof** — Token issuance requires valid signature over challenge nonce
- **JWT with role claims** — `RequireAuth` + `RequireRole` FastAPI dependencies enforce role-based access
- **Token blacklisting** — Per-token revocation (Redis-backed when available, in-memory fallback)
- **Auto-registration** — Unknown actors auto-register on first challenge

### HMAC-SHA256 API Key Authentication (`backend/app/api_key.py`)

- **Two authentication modes:**
  - **Simple mode** — `X-API-Key` header for server-to-server access
  - **HMAC mode** — `X-API-Key` + `X-Signature` (HMAC-SHA256) + `X-Timestamp` for tamper-proof, replay-protected requests
- **Timestamp freshness** — Configurable max age (default 5 minutes) prevents replay attacks
- **No-op when unconfigured** — Disabled gracefully when `API_KEY` env var is empty
- **Wired to 13 read endpoints** across twins, events, and passport routers

### Structured Audit Logging (`backend/app/middleware/audit.py`)

- **AuditMiddleware** — Logs every HTTP request as structured JSON to stderr
- **Fields:** timestamp, severity (INFO/WARN/ERROR), event name, actor DID, HTTP method, path, status code, duration_ms, client IP, user agent
- **Security event logging** — Auth challenges, token issuance, RBAC denials, blacklist hits, rate limit blocks
- **Noise filtering** — Health checks and favicon requests logged at DEBUG level only
- **JWT actor extraction** — Automatically identifies authenticated actors in audit logs

### Rate Limiting (`backend/app/middleware/rate_limiter.py`)

- **Redis-backed** — Sliding window rate limiter using Redis sorted sets
- **Global:** 600 requests/min per IP
- **Telemetry:** 120 requests/min per IP
- **Persists across restarts** — Shared Redis connection pool (pool=20)
- **Graceful degradation** — Allows all requests if Redis is unavailable

### Other Security

- **CORS** — Configurable allowed origins
- **Ed25519 Event Signatures** — All event submissions cryptographically signed
- **Replay Attack Prevention** — Timestamp freshness window (configurable, default 300s)
- **Optimistic Concurrency** — Version-based conflict detection on twin updates
- **Secrets extraction** — All sensitive values in `.env`, excluded from git

---

## Caching & Performance

### Redis Caching Layer (`backend/app/cache.py`)

- **Shared Redis connection** — Pool of 20 connections with keepalive and 2s timeout
- **JSON cache helpers** — `cache_set()` / `cache_get()` with TTL
- **Cache key builders** — For twins, events, passport, QR endpoints
- **Pattern-based invalidation** — `invalidate_twin()` / `invalidate_events()` using SCAN+DELETE
- **Graceful degradation** — All operations silently no-op when Redis is unavailable

### Caching Integration

| Endpoint | TTL | Invalidation Trigger |
|---|---|---|
| `GET /twins/{id}` | 60s | Event append, ZKP generation |
| `GET /events/{id}` | 30s | Event append |
| `GET /passport/{id}` | 60s | Event append |

### Database Indexes

| Table | Index | Columns |
|---|---|---|
| events | `ix_product_events_twin_seq` | twin_id, sequence_num |
| events | `ix_product_events_twin_type` | twin_id, event_type |
| events | `ix_product_events_twin_ts` | twin_id, actor_timestamp |
| events | `ix_product_events_twin_actor` | twin_id, actor_did |
| twins | `ix_twins_product_type_status` | product_type, status |
| twins | `ix_twins_product_type` | product_type |
| twins | `ix_twins_manufacturer` | manufacturer_did |

### HTTP Caching

- **ETag headers** — Based on `version_id` for cache validation
- **Cache-Control** — `public, max-age=30, must-revalidate` on public passport endpoints

### Lifespan Optimization

- **DB connectivity validation** — `SELECT 1` on startup confirms PostgreSQL is reachable
- **Redis pre-warm** — Establishes connection during startup to avoid cold-start latency
- **Graceful shutdown** — Closes Redis and disposes DB engine cleanly
- **Uptime tracking** — Health endpoint reports server uptime in seconds

---

## Data Models (`backend/app/models/`)

| Model | Table | Description |
|---|---|---|
| `Actor` | `actors` | Supply-chain participant with Ed25519 DID, role, and blacklist flag |
| `ProductTwin` | `twins` | Digital twin with hierarchical BOM, optimistic concurrency, computed SoH/capacity/recyclability, 3 query indexes |
| `ProductEvent` | `events` | Append-only event ledger with SHA-256 chain-hash integrity, role-event permission mapping, 4 query indexes |
| `UntrustedTelemetry` | `untrusted_telemetry` | Quarantine table for anomalous or rate-exceeded IoT data |

---

## Frontend UI

### Pages (`frontend/src/app/`)

| Page | Path | Description |
|---|---|---|
| Landing Page | `/` | Role selector grid, feature highlights, QR scan form |
| Supplier Dashboard | `/dashboard/supplier` | Create material batch twins, list existing twins |
| OEM Dashboard | `/dashboard/oem` | Create hierarchical twins (BOM), view children, generate ZKP flags |
| Technician Dashboard | `/dashboard/technician` | View twins, live telemetry WebSocket, offline event queue with localStorage, manual sync |
| Recycler Dashboard | `/dashboard/recycler` | View twins, export recycling matrix as JSON, view second-life recommendations |
| Passport Viewer | `/passport/[twin_id]` | Mobile-first public DPP view with safety warnings, compliance badges, provenance timeline, SoH gauge |

### Components (`frontend/src/components/`)

| Component | Description |
|---|---|
| `TwinCard` | Compact twin display with SoH gauge, status badge, recyclability score |
| `EventTimeline` | Ordered event list with icons, actor masking, metadata chips |
| `SoHGauge` | Circular SVG gauge with color-coded status (green / warn / red) |
| `TelemetryPanel` | Live WebSocket connection, real-time BMS metrics, sparkline trend chart |
| `ChromaGrid` | Interactive spotlight grid for role selection on the landing page |

### API Client (`frontend/src/lib/api.ts`)

- Functions for all backend endpoints (registerActor, createTwin, appendEvent, getPublicPassport, etc.)
- WebSocket factory for telemetry streaming
- TypeScript type definitions matching backend schemas (`frontend/src/lib/types.ts`)

---

## Infrastructure

| Component | Details |
|---|---|
| **Docker Compose** | Four-service orchestration (PostgreSQL, Redis 7, Backend, Frontend) with health checks and dependency ordering |
| **PostgreSQL 16** | Async connections via asyncpg, connection pooling (pool_size=10, max_overflow=20) |
| **Redis 7** | Shared for caching (pool=20) and rate limiting (sliding window sorted sets) |
| **Backend Container** | Python 3.12-slim, Uvicorn with hot-reload in dev mode |
| **Frontend Container** | Multi-stage Node 20 Alpine build, standalone Next.js output |
| **nginx (TLS profile)** | TLS 1.2/1.3 termination, HSTS, security headers, HTTP→HTTPS redirect, WebSocket proxy |
| **Alembic Migrations** | Full migration history with upgrade/downgrade support |
| **Volume Persistence** | `pgdata` and `redis_data` named volumes |
| **Secrets Management** | All secrets in `.env` (git-ignored), `.env.example` for documentation |

---

## Event Types & Validation Pipeline

Supported event types with role-based permission checks:

| Event Type | Allowed Roles | Special Validation |
|---|---|---|
| `MATERIAL_BATCH` | RAW_MATERIAL_SUPPLIER | — |
| `BOM_ASSEMBLY` | OEM_MANUFACTURER | Parent twin must exist |
| `QUALITY_CHECK` | OEM_MANUFACTURER | — |
| `TELEMETRY_SNAPSHOT` | FIELD_TECHNICIAN | Bounds validation; quarantines anomalous readings |
| `REPAIR_PART_SWAP` | FIELD_TECHNICIAN | Counterfeit serial blacklist check |
| `DECOMMISSION` | RECYCLER | — |
| `SECURITY_ALERT` | Any | Flagged for provenance audit |

---

## Testing (`backend/tests/`)

| File | Coverage |
|---|---|
| `test_crypto.py` | Ed25519 keypair generation, DID derivation, signature verification |
| `test_twins.py` | Twin CRUD, BOM hierarchy, state engine |
| `test_edge_cases.py` | Edge cases and boundary conditions |
| `conftest.py` | Shared test fixtures and async session setup |
