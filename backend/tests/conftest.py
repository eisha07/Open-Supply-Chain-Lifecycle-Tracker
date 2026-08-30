"""
Pytest fixtures shared across the test suite.

Uses an in-memory SQLite database (via aiosqlite) so tests run without
a real PostgreSQL instance.
"""
from __future__ import annotations

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.database import Base, get_db
from app.main import app

# ── In-memory SQLite engine for isolated test runs ────────────────────────────
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

test_engine = create_async_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
)

TestSessionLocal = async_sessionmaker(
    bind=test_engine,
    expire_on_commit=False,
    autoflush=False,
)


@pytest_asyncio.fixture(scope="function", autouse=True)
async def setup_db():
    """Create all tables before each test, drop them after."""
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest_asyncio.fixture
async def db_session() -> AsyncSession:
    async with TestSessionLocal() as session:
        yield session


@pytest_asyncio.fixture
async def client(db_session: AsyncSession) -> AsyncClient:
    """HTTP test client with the DB dependency overridden to use SQLite."""
    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as ac:
        yield ac
    app.dependency_overrides.clear()


# ── Helpers ──────────────────────────────────────────────────────────────────

async def create_actor(client: AsyncClient, role: str, name: str = "Test Actor") -> dict:
    resp = await client.post("/actors", json={"display_name": name, "role": role})
    assert resp.status_code == 201, resp.text
    return resp.json()


async def create_twin(client: AsyncClient, actor_did: str, **kwargs) -> dict:
    payload = {
        "name": kwargs.get("name", "Test Battery Cell"),
        "product_type": kwargs.get("product_type", "EV_BATTERY_CELL"),
        "initial_capacity_kwh": kwargs.get("initial_capacity_kwh", 100.0),
        "material_weights_kg": kwargs.get("material_weights_kg",
                                          {"lithium": 2.1, "cobalt": 1.3}),
        "baseline_chemistry": kwargs.get("baseline_chemistry",
                                         {"NMC_811": 0.85, "graphite": 0.15}),
    }
    resp = await client.post(f"/twins?actor_did={actor_did}", json=payload)
    assert resp.status_code == 201, resp.text
    return resp.json()
