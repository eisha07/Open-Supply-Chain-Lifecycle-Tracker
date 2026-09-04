"""
Dynamic State Reduction Engine.

Computes the *current* live state of a Digital Twin by replaying its
append-only event history over the factory-gate baseline.  This approach
ensures that part swaps, repairs, and telemetry readings are always
reflected in the current material profile and SoH — never stale factory specs.

Two modes:
  - `reduce_events()`: Full replay from baseline (O(n), used on first computation
    or when provenance gaps are detected).
  - `reduce_incremental()`: Delta-only replay from the twin's current materialized
    state (O(1) for a single new event).  Skips already-processed events.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from app.models.event import EventType
from app.models.twin import ProductTwin, TwinStatus

# ── Safety thresholds ────────────────────────────────────────────────────────
_SOH_AUTOMOTIVE_MIN_PCT = 75.0   # Below this → unsuitable for automotive
_SOH_STATIONARY_MIN_PCT = 40.0   # Below this → unsuitable even for storage
_TEMP_MIN_CELSIUS = -40.0
_TEMP_MAX_CELSIUS = 85.0
_VOLTAGE_MIN = 2.5
_VOLTAGE_MAX = 4.5


def _compute_recyclability_score(chemistry: Dict[str, float], soh_pct: Optional[float]) -> float:
    """
    Heuristic recyclability score 0–100.

    Higher recycled/recoverable metal content + higher SoH → higher score.
    """
    # Base: presence of high-value, well-recycled metals
    score = 50.0
    recoverable = {"lithium", "cobalt", "nickel", "manganese", "copper"}
    hazardous = {"flame_retardant", "pvc", "brominated_compounds"}

    for material, weight in chemistry.items():
        if material.lower() in recoverable:
            score += min(weight * 5, 15)
        if material.lower() in hazardous:
            score -= min(weight * 8, 20)

    if soh_pct is not None:
        # Higher SoH means less degradation, higher second-life value
        score += (soh_pct / 100.0) * 20
    return max(0.0, min(100.0, round(score, 1)))


def _apply_telemetry(state: Dict[str, Any], metadata: Dict[str, Any]) -> None:
    """Update state fields from a TELEMETRY_SNAPSHOT event."""
    if "soh_pct" in metadata:
        state["current_soh_pct"] = float(metadata["soh_pct"])
    if "capacity_kwh" in metadata:
        state["current_capacity_kwh"] = float(metadata["capacity_kwh"])
    if "safety_rating" in metadata:
        state["current_safety_rating"] = metadata["safety_rating"]


def _apply_repair_part_swap(state: Dict[str, Any], metadata: Dict[str, Any]) -> None:
    """
    Merge replacement part's material/chemistry into the current state.

    Expected metadata keys:
      - replaced_material_id: which material category was swapped
      - new_material_weights_kg: {material: kg} for the new part
      - new_chemistry: {component: pct} for the new part
    """
    if "new_material_weights_kg" in metadata:
        current = dict(state.get("material_weights_kg") or {})
        current.update(metadata["new_material_weights_kg"])
        state["material_weights_kg"] = current

    if "new_chemistry" in metadata:
        current = dict(state.get("current_chemistry") or {})
        current.update(metadata["new_chemistry"])
        state["current_chemistry"] = current

    # Repairs may partially restore capacity
    if "restored_capacity_kwh" in metadata:
        state["current_capacity_kwh"] = float(metadata["restored_capacity_kwh"])


def _apply_decommission(state: Dict[str, Any], metadata: Dict[str, Any]) -> None:
    state["status"] = TwinStatus.DECOMMISSIONED
    if metadata.get("scrapped"):
        state["status"] = TwinStatus.SCRAPPED


def _apply_status_derived(state: Dict[str, Any]) -> None:
    """Re-derive post-reduction status flags (SoH thresholds, provenance gaps)."""
    soh = state.get("current_soh_pct")
    if soh is not None and state["status"] == TwinStatus.ACTIVE:
        if soh < _SOH_AUTOMOTIVE_MIN_PCT:
            state["status"] = TwinStatus.UNSUITABLE_FOR_AUTOMOTIVE
        if soh >= _SOH_STATIONARY_MIN_PCT:
            state["status"] = TwinStatus.RECOMMENDED_FOR_STATIONARY_STORAGE

    if state.get("has_provenance_gap") and state["status"] == TwinStatus.ACTIVE:
        state["status"] = TwinStatus.PROVENANCE_GAP_DETECTED


def _apply_single_event(state: Dict[str, Any], event: Any, prev_sequence: Optional[int]) -> Optional[int]:
    """
    Apply a single event to the state dict.  Returns the updated sequence number.
    Also detects provenance gaps when prev_sequence is provided.
    """
    # Gap detection
    expected = (prev_sequence + 1) if prev_sequence is not None else event.sequence_num
    if event.sequence_num != expected and prev_sequence is not None:
        state["has_provenance_gap"] = True

    meta: Dict[str, Any] = event.metadata_json or {}

    if event.event_type == EventType.TELEMETRY_SNAPSHOT:
        _apply_telemetry(state, meta)
    elif event.event_type == EventType.REPAIR_PART_SWAP:
        _apply_repair_part_swap(state, meta)
    elif event.event_type == EventType.DECOMMISSION:
        _apply_decommission(state, meta)
    elif event.event_type == EventType.SECURITY_ALERT:
        state["status"] = TwinStatus.TAMPERED_SAFETY_RISK

    return event.sequence_num


# ── Full replay (O(n)) ──────────────────────────────────────────────────────

def reduce_events(twin: ProductTwin, events: List[Any]) -> Dict[str, Any]:
    """
    Fold the full event history over the twin's baseline to produce the
    current computed state dict.

    Returns a dict of fields to update on the ProductTwin row.
    """
    state: Dict[str, Any] = {
        "current_capacity_kwh": twin.initial_capacity_kwh,
        "current_soh_pct": 100.0 if twin.initial_capacity_kwh else None,
        "current_chemistry": dict(twin.baseline_chemistry or {}),
        "current_safety_rating": twin.initial_safety_rating,
        "material_weights_kg": dict(twin.material_weights_kg or {}),
        "status": twin.status,
        "has_provenance_gap": twin.has_provenance_gap,
    }

    prev_sequence: Optional[int] = None

    for event in events:
        prev_sequence = _apply_single_event(state, event, prev_sequence)

    _apply_status_derived(state)

    # Recyclability score computed from current chemistry + SoH
    state["recyclability_score"] = _compute_recyclability_score(
        state.get("current_chemistry") or {}, state.get("current_soh_pct")
    )

    return state


# ── Incremental replay (O(k) where k = new events, typically 1) ─────────────

def reduce_incremental(
    twin: ProductTwin,
    new_events: List[Any],
    last_processed_seq: Optional[int] = None,
) -> Dict[str, Any]:
    """
    Apply only the *new* events since the last computation, starting from the
    twin's current materialized state rather than the factory baseline.

    This avoids replaying the entire event history on every mutation.

    Args:
        twin: The ProductTwin row with current materialized state.
        new_events: Events that have NOT yet been applied (sequence > last_processed_seq).
        last_processed_seq: The sequence number of the last event already reflected
            in the twin's state.  If None, falls back to full replay via reduce_events.

    Returns a dict of fields to update on the ProductTwin row.
    """
    # If we don't know the last processed sequence, fall back to full replay
    if last_processed_seq is None and new_events:
        return reduce_events(twin, new_events)

    # Build state from the twin's CURRENT materialized values (not baseline)
    state: Dict[str, Any] = {
        "current_capacity_kwh": twin.current_capacity_kwh or twin.initial_capacity_kwh,
        "current_soh_pct": twin.current_soh_pct if twin.current_soh_pct is not None
                           else (100.0 if twin.initial_capacity_kwh else None),
        "current_chemistry": dict(twin.current_chemistry or twin.baseline_chemistry or {}),
        "current_safety_rating": twin.current_safety_rating or twin.initial_safety_rating,
        "material_weights_kg": dict(twin.material_weights_kg or {}),
        "status": twin.status,
        "has_provenance_gap": twin.has_provenance_gap,
    }

    # Filter to only events after last_processed_seq
    delta = [e for e in new_events if last_processed_seq is None or e.sequence_num > last_processed_seq]

    prev_sequence: Optional[int] = last_processed_seq

    for event in delta:
        prev_sequence = _apply_single_event(state, event, prev_sequence)

    _apply_status_derived(state)

    state["recyclability_score"] = _compute_recyclability_score(
        state.get("current_chemistry") or {}, state.get("current_soh_pct")
    )

    return state
