"""
Secondary-Market Safety & Reuse Estimator (Feature 6).

Evaluates accumulated telemetry and repair history to recommend the most
appropriate next life for a battery asset.
"""
from __future__ import annotations

from typing import Any, Dict, Optional

from app.schemas.twin import SecondLifeEstimate

# ── Thresholds (aligned with EU Battery Regulation 2023/1542) ────────────────
_AUTOMOTIVE_SOH_FLOOR = 75.0    # % — minimum SoH for automotive reuse
_STATIONARY_SOH_FLOOR = 40.0   # % — minimum SoH for stationary storage
_CRITICAL_SOH_FLOOR = 20.0     # % — below this → only material recycling
_MAX_SAFETY_RISK_REPAIRS = 3   # number of REPAIR_PART_SWAP events before extra scrutiny


def estimate_second_life(
    twin_id: str,
    current_soh_pct: Optional[float],
    repair_count: int,
    tamper_alert: bool,
    chemistry: Dict[str, Any],
) -> SecondLifeEstimate:
    """
    Produce a human-readable + machine-readable reuse recommendation.

    Logic:
      1. TAMPERED → reject any reuse, flag for inspection.
      2. SoH ≥ 75 % → suitable for continued automotive use.
      3. 40 ≤ SoH < 75 % → recommended for stationary energy storage.
      4. 20 ≤ SoH < 40 % → viable for low-power IoT / grid buffering.
      5. SoH < 20 % → material recycling only.
      6. Unknown SoH → manual inspection required.
    """
    if tamper_alert:
        return SecondLifeEstimate(
            twin_id=twin_id,
            current_soh_pct=current_soh_pct,
            recommendation="REJECTED_TAMPER_DETECTED",
            suitable_for_automotive=False,
            suitable_for_stationary_storage=False,
            reasoning=(
                "Asset has been flagged for a tamper/counterfeit event.  "
                "All reuse pathways are blocked until a certified inspection clears the flag."
            ),
        )

    if current_soh_pct is None:
        return SecondLifeEstimate(
            twin_id=twin_id,
            current_soh_pct=None,
            recommendation="MANUAL_INSPECTION_REQUIRED",
            suitable_for_automotive=False,
            suitable_for_stationary_storage=False,
            reasoning="No telemetry data available.  A certified inspector must assess SoH before reuse.",
        )

    soh = current_soh_pct
    extra_note = (
        f"  Note: {repair_count} repair event(s) recorded; increased inspection recommended."
        if repair_count >= _MAX_SAFETY_RISK_REPAIRS else ""
    )

    if soh >= _AUTOMOTIVE_SOH_FLOOR:
        return SecondLifeEstimate(
            twin_id=twin_id,
            current_soh_pct=soh,
            recommendation="SUITABLE_FOR_AUTOMOTIVE",
            suitable_for_automotive=True,
            suitable_for_stationary_storage=True,
            reasoning=(
                f"SoH is {soh:.1f}% ≥ {_AUTOMOTIVE_SOH_FLOOR}%.  "
                f"Asset meets EU Battery Regulation automotive reuse threshold.{extra_note}"
            ),
        )

    if soh >= _STATIONARY_SOH_FLOOR:
        return SecondLifeEstimate(
            twin_id=twin_id,
            current_soh_pct=soh,
            recommendation="UNSUITABLE_FOR_AUTOMOTIVE -> RECOMMENDED_FOR_STATIONARY_STORAGE",
            suitable_for_automotive=False,
            suitable_for_stationary_storage=True,
            reasoning=(
                f"SoH is {soh:.1f}% < {_AUTOMOTIVE_SOH_FLOOR}% (automotive floor) but "
                f"≥ {_STATIONARY_SOH_FLOOR}% (stationary floor).  "
                f"Recommended repurposing: grid-scale energy buffer / home storage.{extra_note}"
            ),
        )

    if soh >= _CRITICAL_SOH_FLOOR:
        return SecondLifeEstimate(
            twin_id=twin_id,
            current_soh_pct=soh,
            recommendation="LOW_POWER_IOT_BUFFER_ONLY",
            suitable_for_automotive=False,
            suitable_for_stationary_storage=False,
            reasoning=(
                f"SoH is {soh:.1f}% — below stationary threshold.  "
                f"Limited reuse viable for low-power IoT or small grid-buffering.{extra_note}"
            ),
        )

    return SecondLifeEstimate(
        twin_id=twin_id,
        current_soh_pct=soh,
        recommendation="MATERIAL_RECYCLING_ONLY",
        suitable_for_automotive=False,
        suitable_for_stationary_storage=False,
        reasoning=(
            f"SoH is {soh:.1f}% — critically degraded (< {_CRITICAL_SOH_FLOOR}%).  "
            f"No safe reuse pathway exists.  Refer to recycling matrix for material recovery.{extra_note}"
        ),
    )
