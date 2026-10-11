"""Async SQLAlchemy engine, session factory, and declarative Base."""
from __future__ import annotations

from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.config import get_settings

settings = get_settings()


def _asyncpg_ready_url(url: str) -> str:
    """Translate a libpq-style Postgres URL for SQLAlchemy's asyncpg dialect.

    Managed Postgres providers (Neon, Supabase, ...) hand out URLs with
    ``?sslmode=require``, but SQLAlchemy forwards query params to
    ``asyncpg.connect()`` as keyword arguments — and asyncpg names that
    option ``ssl``. Passing ``sslmode`` through raises
    "connect() got an unexpected keyword argument 'sslmode'".
    "channel_binding" is likewise not an asyncpg kwarg (SCRAM channel
    binding is negotiated automatically over TLS), so it is dropped.

    The prepared-statement cache is also disabled: provider poolers such as
    Neon's ``-pooler`` endpoint run PgBouncer in transaction mode, where
    named prepared statements collide across pooled clients.
    """
    parts = urlsplit(url)
    rewritten: list[tuple[str, str]] = []
    for key, value in parse_qsl(parts.query, keep_blank_values=True):
        if key == "sslmode":
            key = "ssl"  # asyncpg's spelling of the same libpq option
        elif key == "channel_binding":
            continue
        rewritten.append((key, value))
    if "prepared_statement_cache_size" not in dict(rewritten):
        rewritten.append(("prepared_statement_cache_size", "0"))
    return urlunsplit(parts._replace(query=urlencode(rewritten)))


engine = create_async_engine(
    _asyncpg_ready_url(settings.DATABASE_URL),
    echo=settings.APP_ENV == "development",
    pool_size=10,
    max_overflow=20,
    pool_pre_ping=True,
)

AsyncSessionLocal: async_sessionmaker[AsyncSession] = async_sessionmaker(
    bind=engine,
    expire_on_commit=False,
    autoflush=False,
)


class Base(DeclarativeBase):
    """Shared declarative base for all ORM models."""
    pass


async def get_db() -> AsyncSession:  # type: ignore[return]
    """FastAPI dependency — yields a database session per request."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
