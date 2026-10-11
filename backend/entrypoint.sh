#!/bin/sh
# ── Container entrypoint ───────────────────────────────────────────────────────
# Applies database migrations once per container boot, then hands off to the
# CMD (uvicorn). Safe to run on every start and across multiple replicas —
# see prestart.py for the idempotency logic.
set -e

echo "[entrypoint] Applying database migrations..."
python /app/prestart.py

echo "[entrypoint] Migrations complete — starting application."
exec "$@"
