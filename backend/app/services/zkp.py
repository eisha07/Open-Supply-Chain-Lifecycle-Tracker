"""
Zero-Knowledge Proof mock layer (Feature 5).

In a production system this would use a ZK-SNARK/STARK library (e.g. SnarkJS,
Bellman).  For the MVP we implement selective disclosure: the OEM supplies
plain-text claims along with a commitment hash.  Verifiers can check the
hash without ever seeing the underlying values.
"""
from __future__ import annotations

import hashlib
import json
from typing import Any, Dict


def generate_zkp_flags(
    raw_material_data: Dict[str, Any],
    claims: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Generate a set of verifiable boolean / threshold disclosure flags.

    Each flag is:
      { "value": true/false, "commitment": "<sha256 of claim + salt>" }

    Supported claim keys:
      - is_conflict_free (bool)
      - recycled_cobalt_pct_gte (float threshold)
      - recycled_lithium_pct_gte (float threshold)
      - eu_battery_regulation_compliant (bool)
      - carbon_footprint_kg_lte (float threshold)

    The commitment ensures the flag cannot be forged without the original data.
    """
    flags: Dict[str, Any] = {}

    # ── Conflict-free sourcing ────────────────────────────────────────────────
    if "is_conflict_free" in claims:
        value = bool(claims["is_conflict_free"])
        flags["is_conflict_free"] = {
            "value": value,
            "commitment": _commitment({"claim": "is_conflict_free", "value": value,
                                       "source_hash": _hash_data(raw_material_data)}),
        }

    # ── Recycled cobalt threshold ─────────────────────────────────────────────
    if "recycled_cobalt_pct_gte" in claims:
        threshold = float(claims["recycled_cobalt_pct_gte"])
        actual_pct = float(raw_material_data.get("recycled_cobalt_pct", 0))
        value = actual_pct >= threshold
        flags[f"recycled_cobalt_pct_gte_{int(threshold)}"] = {
            "value": value,
            "threshold": threshold,
            "commitment": _commitment({"claim": "recycled_cobalt_pct_gte",
                                       "threshold": threshold, "satisfied": value,
                                       "source_hash": _hash_data(raw_material_data)}),
        }

    # ── Recycled lithium threshold ────────────────────────────────────────────
    if "recycled_lithium_pct_gte" in claims:
        threshold = float(claims["recycled_lithium_pct_gte"])
        actual_pct = float(raw_material_data.get("recycled_lithium_pct", 0))
        value = actual_pct >= threshold
        flags[f"recycled_lithium_pct_gte_{int(threshold)}"] = {
            "value": value,
            "threshold": threshold,
            "commitment": _commitment({"claim": "recycled_lithium_pct_gte",
                                       "threshold": threshold, "satisfied": value,
                                       "source_hash": _hash_data(raw_material_data)}),
        }

    # ── EU Battery Regulation compliance ─────────────────────────────────────
    if "eu_battery_regulation_compliant" in claims:
        value = bool(claims["eu_battery_regulation_compliant"])
        flags["eu_battery_regulation_compliant"] = {
            "value": value,
            "commitment": _commitment({"claim": "eu_battery_regulation_compliant",
                                       "value": value,
                                       "source_hash": _hash_data(raw_material_data)}),
        }

    # ── Carbon footprint ceiling ──────────────────────────────────────────────
    if "carbon_footprint_kg_lte" in claims:
        threshold = float(claims["carbon_footprint_kg_lte"])
        actual = float(raw_material_data.get("carbon_footprint_kg", 0))
        value = actual <= threshold
        flags[f"carbon_footprint_kg_lte_{int(threshold)}"] = {
            "value": value,
            "threshold": threshold,
            "commitment": _commitment({"claim": "carbon_footprint_kg_lte",
                                       "threshold": threshold, "satisfied": value,
                                       "source_hash": _hash_data(raw_material_data)}),
        }

    return flags


def _hash_data(data: Dict[str, Any]) -> str:
    canonical = json.dumps(data, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(canonical.encode()).hexdigest()


def _commitment(data: Dict[str, Any]) -> str:
    canonical = json.dumps(data, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(canonical.encode()).hexdigest()
