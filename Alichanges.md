# Ali's Changes — OSLT Implementation Log

A complete record of changes implemented and features left pending during the OSLT hackathon session.

---

## Changes Made

### 1. Authentication & Authorization

- **JWT challenge-response auth system** (`backend/app/services/auth.py`, `backend/app/routers/auth.py`, `backend/app/schemas/auth.py`)
  - `GET /auth/challenge?actor_did=` — server issues a one-time nonce (120s TTL)
  - `POST /auth/token` — actor signs nonce with Ed25519 private key → JWT returned
  - `GET /auth/me` — decodes Bearer JWT and returns actor info
- **Admin role enforcement** — `X-Admin-Secret` header required on all mutating admin endpoints (blacklist, serial management)
- **Audit logging** — structured `logging` throughout routers for failed auth, blacklist events, and state changes

---

### 2. Frontend UI

- **Actor registration/login UI** (`frontend/src/app/actors/page.tsx`)
  - Three tabs: Register, Login, Manage
  - Browser-side Ed25519 signing via Web Crypto API (`crypto.subtle`)
  - JWT stored in `localStorage` on successful login
- **Event submission form** (`frontend/src/app/dashboard/technician/page.tsx`)
  - Full form: event type, actor DID, private key, serial number, notes
  - Browser-side Ed25519 signing before submission
  - Event type filter dropdown
  - CSV export button
  - Fixed hardcoded empty `events={[]}` — now fetches real events from `GET /events/{twin_id}`
- **Complete twin creation forms**
  - `material_weights_kg` key-value editor added to supplier and OEM dashboards
  - `baseline_chemistry` key-value editor added
  - `serial_number` and `initial_safety_rating` fields added
- **Actor management UI** — view all actors, blacklist them from the frontend
- **Loading states** — spinners added to all dashboards (supplier, OEM, technician, recycler)
- **QR code panel** (`frontend/src/app/passport/[twin_id]/page.tsx`) — toggle button, image display, download link
- **Passport pagination** — prev/next controls with total event count display
- **Event type filter** on passport timeline
- **Actors nav link** added to homepage header

---

### 3. Backend Features

- **DB-backed counterfeit serial registry** (`backend/app/models/blacklisted_serial.py`, `backend/app/routers/serials.py`)
  - Replaced in-memory Python `set()` with `blacklisted_serials` database table
  - `GET /serials` — list all blacklisted serials
  - `POST /serials` — add serial (admin only)
  - `DELETE /serials/{serial_number}` — remove serial (admin only)
- **Event filtering** (`backend/app/routers/events.py`)
  - Filter by `event_type`, `actor_did`, `date_from`, `date_to`
- **CSV export** — `GET /events/{twin_id}/export` returns a streaming CSV of event history
- **QR code generation** (`backend/app/routers/passport.py`)
  - `GET /passport/{twin_id}/qr` returns a PNG QR code via `qrcode[pil]` library
- **Passport timeline pagination** — `limit` / `offset` params, response includes `pagination: {total, limit, offset, has_more}`
- **Detailed provenance gap report** (`backend/app/routers/twins.py`)
  - `GET /twins/{twin_id}/provenance-gaps` — missing sequence ranges, actor DIDs, timestamps, gap sizes, recommendations
- **Actor list endpoint** with `role` and `is_blacklisted` filter params

---

### 4. Database

- **`blacklisted_serials` table** — persisted counterfeit serial registry with `serial_number`, `reason`, `added_by_did`, `created_at`
- **Foreign key** from `added_by_did` → `actors.did` (SET NULL on delete)

---

### 5. Configuration & Infrastructure

- **`backend/app/config.py`** — added `JWT_SECRET_KEY`, `JWT_ALGORITHM`, `JWT_EXPIRE_MINUTES`, `ADMIN_SECRET`; rewrote CORS validator to handle both JSON array and comma-separated formats
- **`docker-compose.yml`** — removed hardcoded secrets, all values passed as env vars with safe defaults; CORS_ORIGINS passed as JSON array to satisfy pydantic-settings v2
- **`backend/requirements.txt`** — added `python-jose[cryptography]`, `qrcode[pil]`, `Pillow`
- **`.env.backend.example`** — secrets template with generation instructions
- **`.gitignore`** — added `.env.backend`
- **`frontend/src/lib/types.ts`** — added `ChallengeResponse`, `TokenResponse`, `BlacklistedSerial`, `PaginationMeta`, `ProvenanceGap`, `ProvenanceGapReport`
- **`frontend/src/lib/api.ts`** — added `getChallenge`, `loginActor`, `getMe`, `listActors`, `blacklistActor`, `exportEventsCsvUrl`, `getProvenanceGaps`, `getPassportQrUrl`, `listBlacklistedSerials`, `addBlacklistedSerial`, `removeBlacklistedSerial`

---

### 6. Bug Fixes

| Bug | Fix |
|-----|-----|
| `.env.backend` missing caused docker-compose failure | Removed `env_file` directive; secrets passed inline with defaults |
| TypeScript build error: `crypto.subtle` doesn't include Ed25519 types | Cast `crypto.subtle as any` in actors and technician pages |
| `pydantic_settings.SettingsError` parsing `CORS_ORIGINS` | Changed to JSON array format in docker-compose + robust validator in config.py |
| FastAPI 0.111.1 assertion: 204 response must not have body | Added `response_model=None` to DELETE `/serials/{serial_number}` |

---

## Changes NOT Made

These items remain from the original `MISSING_FEATURES.md` and were not implemented:

### Infrastructure / DevOps
- **Alembic migrations** — tables are still auto-created on startup via `Base.metadata.create_all`; no migration version history
- **Redis-backed rate limiter** — rate limiting is still in-memory; resets on restart, not shared across instances
- **HTTPS / TLS** — all traffic remains plaintext HTTP; no reverse proxy or certificate configuration

### Security
- **Real ZKP library** — ZK-SNARK/STARK commitment hashes are still mock values; no `gnark` or `circom` integration
- **HMAC / API key auth on read endpoints** — only write endpoints are protected; reads are open
- **Password / MFA / secure key storage** — private keys are shown once at registration with no recovery mechanism

### Backend
- **Real BMS telemetry** — WebSocket still generates random simulated values, not connected to a real data source
- **Batch twin / event creation endpoints** — no bulk POST operations
- **Webhook / push notifications** — no event-driven notifications on `SECURITY_ALERT`, `DECOMMISSION`, etc.
- **Twin state versioning & rollback** — no ability to view or revert to previous twin states
- **Offline batch sync via `POST /telemetry/batch`** — technician offline queue still calls individual POSTs

### Frontend
- **Batch event upload UI** — no bulk CSV import for offline events
- **Reporting & analytics dashboard** — no aggregate metrics (twins created, events/sec, compliance rates)
- **i18n / localization** — English only
- **Accessibility (a11y)** — no ARIA labels, keyboard navigation, or screen-reader support

### Testing & CI
- **End-to-end test suite** — no Playwright or Cypress tests
- **Integration tests for routers/services** — only 3 unit test files exist (crypto, twins, edge cases)
- **CI/CD pipeline** — no GitHub Actions or equivalent automation

### Enterprise Features
- **Multi-tenancy / organizational isolation** — all actors share a single namespace
- **External system integrations** — no ERP, regulatory body, or supply-chain platform connectors
- **User account management** — no support for multiple users per organization

---

## Summary

| Category | Implemented | Skipped |
|----------|-------------|---------|
| Auth & Authorization | JWT, admin enforcement, audit logging | MFA, key recovery, HMAC on reads |
| Frontend UI | Login/register, event forms, twin forms, actor management, loading states, QR, pagination | Batch upload UI, analytics, i18n, a11y |
| Backend APIs | Serial registry, event filtering, CSV export, QR generation, pagination, provenance gaps | Webhooks, versioning, batch ops, real telemetry |
| Database | `blacklisted_serials` table | Alembic migrations, Redis, indexing strategy |
| Infrastructure | Env-var secrets, docker-compose fixes | HTTPS/TLS, Redis, CI/CD |
| Testing | — | E2E tests, router/service unit tests, CI pipeline |
| Enterprise | — | Multi-tenancy, ERP integrations, reporting |
