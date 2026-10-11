"""
Pre-deploy database migration step.

Runs before uvicorn starts (see entrypoint.sh) and is idempotent, so it is safe
on every boot and across simultaneously-starting replicas.

Three cases are handled:

  1. Fresh database       -> `alembic upgrade head` builds the full schema.
  2. Already migrated     -> `alembic upgrade head` applies any pending revisions.
  3. Pre-existing schema  -> the schema was created by `Base.metadata.create_all`
                             on an earlier dev boot, before migrations were wired
                             in. There is no `alembic_version` table, so a plain
                             `upgrade head` would fail on "relation already exists".
                             We baseline it with `alembic stamp head` first.

Concurrent replicas are safe: Alembic takes a lock on the `alembic_version`
table, so racing containers serialise instead of corrupting each other.
"""
from __future__ import annotations

import asyncio
import os
import subprocess
import sys
import time

import asyncpg

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MAX_CONNECT_ATTEMPTS = 15
CONNECT_RETRY_DELAY_SECONDS = 2


def _dsn() -> str:
    """Resolve a plain postgresql:// DSN — asyncpg rejects the SQLAlchemy +driver suffix."""
    url = (os.getenv("SYNC_DATABASE_URL") or os.getenv("DATABASE_URL") or "").strip()
    if not url:
        sys.exit("[prestart] FATAL: neither SYNC_DATABASE_URL nor DATABASE_URL is set")
    return url.replace("postgresql+asyncpg://", "postgresql://").replace(
        "postgresql+psycopg2://", "postgresql://"
    )


def _run_alembic(*args: str) -> None:
    cmd = ["alembic", *args]
    print(f"[prestart] $ {' '.join(cmd)}", flush=True)
    result = subprocess.run(cmd, cwd=BASE_DIR)
    if result.returncode != 0:
        sys.exit(f"[prestart] FATAL: 'alembic {' '.join(args)}' exited {result.returncode}")


async def _probe() -> tuple[bool, bool]:
    """Return (has_alembic_version, has_application_schema), retrying until the DB accepts connections."""
    dsn = _dsn()
    last_error: Exception | None = None

    for attempt in range(1, MAX_CONNECT_ATTEMPTS + 1):
        try:
            conn = await asyncpg.connect(dsn, timeout=10)
            try:
                has_version = await conn.fetchval(
                    "SELECT to_regclass('public.alembic_version') IS NOT NULL"
                )
                has_schema = await conn.fetchval(
                    "SELECT to_regclass('public.actors') IS NOT NULL"
                )
                return bool(has_version), bool(has_schema)
            finally:
                await conn.close()
        except Exception as exc:  # noqa: BLE001 — surface the real cause on final attempt
            last_error = exc
            print(
                f"[prestart] Database not reachable (attempt {attempt}/{MAX_CONNECT_ATTEMPTS}): {exc}",
                flush=True,
            )
            if attempt < MAX_CONNECT_ATTEMPTS:
                time.sleep(CONNECT_RETRY_DELAY_SECONDS)

    sys.exit(f"[prestart] FATAL: could not reach the database — {last_error}")


def main() -> None:
    has_version, has_schema = asyncio.run(_probe())

    if has_schema and not has_version:
        print(
            "[prestart] Pre-existing schema found with no Alembic history — "
            "stamping as head so future revisions apply from a known baseline.",
            flush=True,
        )
        _run_alembic("stamp", "head")

    _run_alembic("upgrade", "head")
    print("[prestart] Schema is up to date.", flush=True)


if __name__ == "__main__":
    main()
