"""
Mock IoT telemetry WebSocket (Feature 8 / Edge Case 3 simulation).

WS  /ws/telemetry/{twin_id}  — Stream live SoH readings for a twin
POST /telemetry/batch         — Offline-first batch sync for queued technician events
"""
from __future__ import annotations

import asyncio
import json
import logging
import random
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Set

from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.middleware.rate_limiter import telemetry_rate_limit_dependency
from app.models.twin import ProductTwin
from app.schemas.event import EventCreate
from app.models.event import EventType

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/telemetry", tags=["IoT Telemetry"])


# ── Connection pool tracking ──────────────────────────────────────────────────
# Tracks active WebSocket connections for monitoring and graceful shutdown.
_active_connections: Dict[str, Set[WebSocket]] = {}
_connection_count: int = 0
_connection_count_lock = asyncio.Lock()

MAX_CONNECTIONS_PER_TWIN = 5
MAX_TOTAL_CONNECTIONS = 100


async def _register_connection(twin_id: str, ws: WebSocket) -> bool:
    """Register a WebSocket connection. Returns False if limits exceeded."""
    global _connection_count
    async with _connection_count_lock:
        if _connection_count >= MAX_TOTAL_CONNECTIONS:
            return False
        twin_conns = _active_connections.setdefault(twin_id, set())
        if len(twin_conns) >= MAX_CONNECTIONS_PER_TWIN:
            return False
        twin_conns.add(ws)
        _connection_count += 1
        return True


async def _unregister_connection(twin_id: str, ws: WebSocket) -> None:
    """Remove a WebSocket connection from tracking."""
    global _connection_count
    async with _connection_count_lock:
        twin_conns = _active_connections.get(twin_id, set())
        twin_conns.discard(ws)
        if not twin_conns:
            _active_connections.pop(twin_id, None)
        _connection_count = max(0, _connection_count - 1)


def get_active_connection_count() -> int:
    """Return the number of active WebSocket connections (for monitoring)."""
    return _connection_count


# ── Mock BMS data generator ───────────────────────────────────────────────────

def _generate_bms_reading(twin_id: str, base_soh: float) -> Dict[str, Any]:
    """Simulate a Battery Management System telemetry reading."""
    soh_drift = random.gauss(0, 0.3)
    return {
        "twin_id": twin_id,
        "timestamp": datetime.now(tz=timezone.utc).isoformat(),
        "soh_pct": round(max(0, min(100, base_soh + soh_drift)), 2),
        "temperature_celsius": round(random.uniform(18.0, 35.0), 1),
        "voltage_v": round(random.uniform(3.6, 4.1), 3),
        "current_a": round(random.uniform(-10, 10), 2),
        "cycle_count": random.randint(0, 2000),
    }


@router.websocket("/ws/{twin_id}")
async def telemetry_websocket(
    websocket: WebSocket,
    twin_id: str,
) -> None:
    """
    WebSocket endpoint streaming mock BMS telemetry at 1-second intervals.

    The client can send {"command": "stop"} to terminate the stream.
    The server automatically stops after 300 messages (5 minutes) to
    prevent resource exhaustion.

    Connection pooling:
    - Max 5 concurrent connections per twin
    - Max 100 total concurrent connections
    - DB session released after initial lookup (not held open)
    """
    # Check connection limits BEFORE accepting
    if not await _register_connection(twin_id, websocket):
        await websocket.accept()
        await websocket.close(
            code=4029,
            reason="Too many concurrent connections — retry later",
        )
        return

    await websocket.accept()

    # Quick DB check — release session immediately after lookup
    from app.database import AsyncSessionLocal
    base_soh = 85.0
    try:
        async with AsyncSessionLocal() as db:
            twin = await db.get(ProductTwin, twin_id)
            if not twin:
                await websocket.close(code=4004, reason=f"Twin {twin_id!r} not found")
                await _unregister_connection(twin_id, websocket)
                return
            base_soh = twin.current_soh_pct or 85.0
    except Exception as exc:
        logger.warning("WS: DB lookup failed for twin %s: %s", twin_id, exc)
        await websocket.close(code=4500, reason="Database error")
        await _unregister_connection(twin_id, websocket)
        return

    # DB session is now released — streaming uses no DB resources
    message_count = 0
    MAX_MESSAGES = 300
    start_time = time.monotonic()

    try:
        while message_count < MAX_MESSAGES:
            reading = _generate_bms_reading(twin_id, base_soh)
            # Gradually degrade SoH to simulate real battery behaviour
            base_soh = max(0, base_soh - random.uniform(0, 0.05))

            await websocket.send_text(json.dumps(reading))
            message_count += 1

            # Check for client commands (non-blocking)
            try:
                raw = await asyncio.wait_for(websocket.receive_text(), timeout=1.0)
                msg = json.loads(raw)
                if msg.get("command") == "stop":
                    break
            except asyncio.TimeoutError:
                pass  # No client message — continue streaming

    except WebSocketDisconnect:
        pass  # Client disconnected normally
    finally:
        duration = round(time.monotonic() - start_time, 1)
        await _unregister_connection(twin_id, websocket)
        logger.info(
            "WS: twin=%s msgs=%d duration=%.1fs active=%d",
            twin_id, message_count, duration, get_active_connection_count(),
        )


# ── Offline-first batch sync endpoint (Feature 8) ────────────────────────────

from pydantic import BaseModel


class BatchSyncRequest(BaseModel):
    """Payload for technicians syncing queued offline events."""
    events: List[EventCreate]


class BatchSyncResult(BaseModel):
    accepted: List[int]
    rejected: List[Dict[str, Any]]


@router.post("/batch", response_model=BatchSyncResult,
             summary="Batch-sync offline-queued signed events (Feature 8)",
             dependencies=[Depends(telemetry_rate_limit_dependency)])
async def batch_sync(
    payload: BatchSyncRequest,
    db: AsyncSession = Depends(get_db),
) -> BatchSyncResult:
    """
    Accept a batch of signed events queued by a field technician while offline.

    Each event is processed independently — a failure in one does NOT roll back
    the others, enabling partial sync recovery.
    """
    from app.routers.events import append_event

    accepted: List[int] = []
    rejected: List[Dict[str, Any]] = []

    for i, event_create in enumerate(payload.events):
        try:
            result = await append_event(event_create, db=db)
            accepted.append(result.id)
        except HTTPException as exc:
            rejected.append({
                "index": i,
                "twin_id": event_create.twin_id,
                "event_type": event_create.event_type.value,
                "error": exc.detail,
            })

    return BatchSyncResult(accepted=accepted, rejected=rejected)
