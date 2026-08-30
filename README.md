# Open Supply-Chain Lifecycle Tracker (OSLT)

A **Digital Product Passport (DPP)** system aligned with **EU DPP / ESPR** standards. Creates verifiable Digital Twins for physical products and tracks their state across a multi-party supply chain via an append-only cryptographic event ledger.

Designed for batteries, EVs, and critical raw materials — supporting compliance with EU Battery Regulation, conflict-mineral due diligence, and circular-economy mandates.

---

## Tech Stack

| Layer        | Technology                          |
| ------------ | ----------------------------------- |
| Database     | PostgreSQL 16 (Alpine)              |
| Backend      | Python · FastAPI · Uvicorn          |
| Frontend     | Next.js 14 · Tailwind CSS           |
| Cryptography | Ed25519 (DIDs, signatures)          |
| Infra        | Docker Compose                      |

## Architecture

```
┌───────────────────────────────────────────────────────┐
│                    Frontend (Next.js)                  │
│  Supplier  │  OEM  │  Technician  │  Recycler  │  DPP │
└────────────────────────┬──────────────────────────────┘
                         │ REST / WebSocket
┌────────────────────────▼──────────────────────────────┐
│                  Backend (FastAPI)                     │
│  Actors │ Twins │ Events │ Passport │ Telemetry        │
│  Crypto │ State Engine │ ZKP │ Second-Life │ Recycling │
└────────────────────────┬──────────────────────────────┘
                         │ asyncpg
┌────────────────────────▼──────────────────────────────┐
│                PostgreSQL 16                           │
│  actors │ twins │ events │ untrusted_telemetry         │
└───────────────────────────────────────────────────────┘
```

## Quick Start

```bash
# Clone the repo
git clone https://github.com/<your-username>/oslt.git
cd oslt

# Start all services
docker compose up --build -d
```

| Service    | URL                         |
| ---------- | --------------------------- |
| Frontend   | http://localhost:3000        |
| API Docs   | http://localhost:8000/docs   |
| PostgreSQL | localhost:5432               |

### Local Development (without Docker)

**Backend:**
```bash
cd backend
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
uvicorn app.main:app --reload --port 8000
```

**Frontend:**
```bash
cd frontend
npm install --legacy-peer-deps
npm run dev
```

## Project Structure

```
├── backend/
│   ├── app/
│   │   ├── middleware/        # Rate limiting
│   │   ├── models/            # SQLAlchemy ORM (Actor, Twin, Event, Telemetry)
│   │   ├── routers/           # API endpoints
│   │   ├── schemas/           # Pydantic request/response schemas
│   │   ├── services/          # Business logic (crypto, state engine, ZKP, etc.)
│   │   ├── config.py          # Environment settings
│   │   ├── database.py        # Async SQLAlchemy engine
│   │   └── main.py            # FastAPI app entry point
│   ├── tests/                 # Pytest test suite
│   ├── alembic/               # Migration scaffolding (not yet active)
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── app/               # Next.js pages (dashboards, passport viewer)
│   │   ├── components/        # Reusable UI components
│   │   └── lib/               # API client & TypeScript types
│   └── package.json
└── docker-compose.yml
```

## Documentation

- [FEATURES.md](./FEATURES.md) — Complete list of all implemented features
- [MISSING_FEATURES.md](./MISSING_FEATURES.md) — Planned features and known gaps

## License

MIT
