# Missing Features & Known Gaps

A prioritized inventory of features that are planned, incomplete, or absent from the current OSLT implementation.

---

## 1. Authentication & Authorization

| Gap | Impact | Priority |
|---|---|---|
| No JWT / OAuth / session-based auth | Anyone can call any API endpoint — no user identity verification | **Critical** |
| Actor DID passed as query parameter without verification | Easy to impersonate any actor | **Critical** |
| No password, MFA, or secure key storage | Private keys returned once at registration with no recovery | **Critical** |
| Blacklist endpoint has no admin role enforcement | Any caller can blacklist any actor | **High** |
| No role-based middleware at the HTTP layer | Role checks are ad-hoc in service logic, not enforced globally | **High** |

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

## 3. Database & Migrations

| Gap | Details | Priority |
|---|---|---|
| Alembic migrations not active | `alembic.ini` and `env.py` exist but no migration history is generated; tables auto-created on startup | **High** |
| No schema migration versioning | Production deployments cannot safely evolve the schema | **High** |
| In-memory rate limiters | Lost on restart; not shared across multiple backend instances | **Medium** |
| In-memory counterfeit serial registry | `_BLACKLISTED_SERIALS` is a Python `set()` — not persisted, lost on restart | **Medium** |
| No database indexing strategy | No documented or optimized indexes for query-heavy tables | **Medium** |

---

## 4. Security & Production Readiness

| Gap | Details | Priority |
|---|---|---|
| Rate limiter uses in-memory dict | Should be Redis-backed for multi-process / multi-instance deployments | **High** |
| Secret key hardcoded in docker-compose | `dev-secret-change-in-production` is committed in `docker-compose.yml` | **High** |
| No HTTPS/TLS configuration | All traffic is plaintext HTTP — no production-grade transport security | **High** |
| No request signing beyond Ed25519 events | No HMAC or API key auth for read endpoints | **Medium** |
| No audit logging | No structured logging of security events, failed auth attempts, or state changes | **Medium** |
| No input validation on some endpoints | Twin name length, material weight ranges not enforced in all code paths | **Low** |
| Rate limit state not persisted | Resets to zero on every backend restart | **Medium** |

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

## 8. Performance & Scalability

| Gap | Details | Priority |
|---|---|---|
| No caching layer | No Redis/Memcached — every request hits the database directly | **Medium** |
| Full event replay on every mutation | State engine replays entire event history on each event append — O(n) per event | **Medium** |
| No pagination on passport timeline | Loads all events at once for the public passport view | **Medium** |
| No database query optimization | No eager loading, query profiling, or connection tuning | **Low** |
| WebSocket connections not pooled | Each telemetry stream creates a new connection with no lifecycle management | **Low** |

---

## Suggested Priority Roadmap

### Phase 1 — Security Foundation
1. JWT/OAuth authentication flow
2. Admin role enforcement on sensitive endpoints
3. Move rate limiter to Redis
4. Activate Alembic migrations
5. Remove hardcoded secrets from docker-compose

### Phase 2 — Core UX Completion
1. Actor registration & login UI
2. Event submission forms on technician dashboard
3. Complete twin creation forms (all fields)
4. Loading states and error boundaries

### Phase 3 — Production Hardening
1. HTTPS/TLS configuration
2. End-to-end test suite
3. CI/CD pipeline
4. Audit logging
5. Database indexing and query optimization

### Phase 4 — Enterprise Features
1. Multi-tenancy and organization management
2. Reporting and analytics dashboard
3. Webhook notifications
4. QR code generation
5. External system integrations
