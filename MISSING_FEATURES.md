# Missing Features & Known Gaps

A prioritized inventory of features that are planned, incomplete, or absent from the current OSLT implementation.

---

## 1. Authentication & Authorization — MOSTLY COMPLETE

| Gap | Status | Priority |
|---|---|---|
| JWT authentication flow | **DONE** — Challenge-response with Ed25519 signature proof, JWT tokens with role claims, token blacklisting | - |
| Role-based middleware at HTTP layer | **DONE** — `RequireAuth` + `RequireRole` FastAPI dependencies, wired across all protected endpoints | - |
| Admin role enforcement on sensitive endpoints | **DONE** — Actor lookup and blacklist require `admin` role | - |
| Actor DID passed as query parameter without verification | **DONE** — JWT `sub` claim cross-checked against `actor_did` on events/twins endpoints | - |
| Redis-backed rate limiter | **DONE** — Sliding window via Redis sorted sets, shared connection pool | - |
| No password, MFA, or secure key storage | Private keys returned once at registration with no recovery mechanism | **Medium** |
| No multi-user / organizational auth | No support for multiple users per organization or org-level role delegation | **Medium** |

---

## 2. Frontend UI Gaps

| Gap | Details | Priority |
|---|---|---|
| No actor registration/login UI | Actors must be created via API/Swagger — no frontend flow | **High** |
| No event submission UI | Technician dashboard shows an empty event timeline; no form to submit events | **High** |
| Twin creation forms incomplete | Missing `material_weights_kg`, `baseline_chemistry` inputs on supplier/OEM dashboards | **Medium** |
| No batch event upload UI | Technicians have no way to bulk-upload offline events beyond one-by-one sync | **Medium** |
| No actor management UI | No way to view all actors or blacklist them from the frontend | **Medium** |
| No loading states or error boundaries | Components lack proper loading indicators and error handling UX | **Low** |

---

## 3. Database & Migrations — MOSTLY COMPLETE

| Gap | Status | Priority |
|---|---|---|
| Alembic migrations not active | **DONE** — Full initial migration (`0001_initial.py`) with all tables, indexes, and constraints | - |
| No schema migration versioning | **DONE** — Alembic revision history with upgrade/downgrade support | - |
| In-memory rate limiters | **DONE** — Migrated to Redis sorted-set sliding window | - |
| In-memory counterfeit serial registry | `_BLACKLISTED_SERIALS` is a Python `set()` — not persisted, lost on restart | **Medium** |
| No database indexing strategy | **DONE** — 7 composite indexes on events and twins tables optimized for common query patterns | - |

---

## 4. Security & Production Readiness — SIGNIFICANT PROGRESS

| Gap | Status | Priority |
|---|---|---|
| Rate limiter uses in-memory dict | **DONE** — Redis-backed sliding window rate limiter | - |
| Secret key hardcoded in docker-compose | **DONE** — All secrets extracted to `.env`, `.env.example` documents required variables | - |
| No HTTPS/TLS configuration | **DONE** — nginx reverse proxy with TLS 1.2/1.3, HSTS, security headers, HTTP→HTTPS redirect, WebSocket support | - |
| No request signing beyond Ed25519 events | **DONE** — HMAC-SHA256 API key authentication with `X-API-Key`, `X-Signature`, `X-Timestamp` headers; replay protection via timestamp freshness | - |
| No audit logging | **DONE** — Structured JSON audit middleware logging every HTTP request with actor DID, duration, IP; security events logged from auth, RBAC, and rate limiter | - |
| No input validation on some endpoints | Twin name length, material weight ranges not enforced in all code paths | **Low** |

---

## 5. Incomplete Implementations

| Feature | Current State | What's Needed |
|---|---|---|
| Technician event timeline | Hardcoded empty array — never fetches real events from the API | Wire to `GET /events/{twin_id}` |
| Offline queue sync | Processes events one-by-one via individual POST calls | Use `POST /telemetry/batch` for true batch upload |
| WebSocket telemetry | Generates random mock values — not connected to any real BMS data source | Integrate real telemetry feed or simulation engine |
| ZKP flags | Mock commitment hashes without actual ZK-SNARK/STARK library | Integrate a real ZKP library (e.g., gnark, circom) |
| Provenance gap detection | Minimal — only flags `has_provenance_gap` boolean | Detailed gap audit report with missing sequence ranges |
| Counterfeit part detection | Uses in-memory Python `set()` | Persist to database table with proper querying |

---

## 6. Missing Common DPP Features

| Feature | Why It Matters | Effort |
|---|---|---|
| User account management | No support for multiple users per organization | Large |
| Organizational / tenant isolation | No multi-tenancy — all actors share a single namespace | Large |
| Event search & filtering | Only filterable by `twin_id` — no date range, event type, or actor filters | Medium |
| Export event history | No CSV/PDF export of event ledgers (only recycling matrix has JSON export) | Medium |
| Webhook / event notifications | No push notifications when events occur (e.g., SECURITY_ALERT, DECOMMISSION) | Medium |
| Versioning & rollback | No ability to view or rollback to previous twin states | Medium |
| Bulk operations | No batch creation of twins or events | Medium |
| Reporting & analytics | No dashboard for aggregate metrics (twins created, events/sec, compliance rates) | Large |
| External system integration | No ERP, supply-chain platform, or regulatory body connectors | Large |
| QR code generation | Landing page has a QR scan form, but no QR code generation for passports | Small |
| i18n / localization | English-only UI — EU DPP targets multi-language markets | Large |
| Accessibility (a11y) | No ARIA labels, keyboard navigation, or screen-reader support evident | Medium |

---

## 7. Testing & Documentation

| Gap | Details | Priority |
|---|---|---|
| No end-to-end tests | Only unit tests exist — no integration or E2E test coverage | **High** |
| No API documentation beyond Swagger | No developer guides, onboarding docs, or architecture decision records | **Medium** |
| Limited test coverage | Only 3 test files covering crypto, twins, and edge cases — routers and services largely untested | **High** |
| No CI/CD pipeline | No GitHub Actions or similar automation for testing and deployment | **Medium** |

---

## 8. Performance & Scalability — COMPLETE

| Gap | Status | Priority |
|---|---|---|
| No caching layer | **DONE** — Redis caching with 60s TTL on twins/passport, 30s on events, pattern-based invalidation | - |
| Full event replay on every mutation | **DONE** — Incremental state engine (`reduce_incremental()`) achieves O(1) for single-event appends | - |
| No pagination on passport timeline | **DONE** — Paginated with optimized COUNT(*) query (no full row loading) | - |
| No database query optimization | **DONE** — 7 composite indexes, COUNT(*) instead of len(all()), eager session management | - |
| WebSocket connections not pooled | **DONE** — Connection pool (max 5/twin, 100 total), DB session released after lookup, structured logging | - |
| No HTTP caching headers | **DONE** — ETag + Cache-Control on passport endpoints | - |
| No lifespan optimization | **DONE** — DB validation, Redis pre-warm on startup, graceful shutdown, enhanced health endpoint | - |

---

## Suggested Priority Roadmap

### Phase 1 — Security Foundation  COMPLETE
1. ~~JWT/OAuth authentication flow~~
2. ~~Admin role enforcement on sensitive endpoints~~
3. ~~Move rate limiter to Redis~~
4. ~~Activate Alembic migrations~~
5. ~~Remove hardcoded secrets from docker-compose~~
6. ~~HTTPS/TLS via nginx reverse proxy~~
7. ~~HMAC-SHA256 API key authentication~~
8. ~~Structured audit logging~~

### Phase 2 — Performance & Scalability  COMPLETE
1. ~~Redis caching layer~~
2. ~~Incremental state engine~~
3. ~~Database indexes~~
4. ~~WebSocket connection pooling~~
5. ~~Lifespan optimization~~
6. ~~HTTP caching headers (ETag, Cache-Control)~~

### Phase 3 — Core UX Completion
1. Actor registration & login UI on the frontend
2. Event submission forms on technician dashboard
3. Wire technician timeline to real API events
4. Complete twin creation forms (all fields)
5. Loading states and error boundaries
6. Offline queue batch sync via `/telemetry/batch`

### Phase 4 — Enterprise Features
1. Multi-tenancy and organization management
2. Reporting and analytics dashboard
3. Webhook notifications
4. QR code generation for passports
5. External system integrations
6. CSV/PDF export of event ledgers

### Phase 5 — Production Hardening
1. End-to-end test suite
2. CI/CD pipeline (GitHub Actions)
3. Expand unit/integration test coverage
4. Persist counterfeit serial registry to database
5. Real ZKP library integration
6. i18n / localization
7. Accessibility (a11y) compliance
