"""
Automated Recycling Sorting & Dismantling Matrix (Feature 7).

Generates an exportable JSON document for recyclers detailing:
  - Hazardous additives requiring PPE / special handling
  - High-value target metals and estimated recovery weight
  - Step-by-step disassembly sequence based on the twin's current state
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional


# ── Hazard & value lookups ────────────────────────────────────────────────────
_HAZARDOUS_MATERIALS: Dict[str, Dict[str, str]] = {
    "flame_retardant": {
        "hazard_class": "H400 – Aquatic Hazard",
        "ppe_required": "P3 respirator, nitrile gloves, face shield",
        "disposal": "Specialised incineration facility only",
    },
    "pvc": {
        "hazard_class": "H315 – Skin Irritant",
        "ppe_required": "Nitrile gloves, safety glasses",
        "disposal": "Separate from metal stream; licensed PVC recycler",
    },
    "brominated_compounds": {
        "hazard_class": "H411 – Toxic to Aquatic Life",
        "ppe_required": "P3 respirator, chemical suit",
        "disposal": "Broker to licensed hazardous-waste facility",
    },
    "lithium": {
        "hazard_class": "H260 – Reacts violently with water",
        "ppe_required": "Flame-retardant clothing, face shield, dry-sand extinguisher nearby",
        "disposal": "Lithium-certified recycler only; no water exposure",
    },
    "cobalt": {
        "hazard_class": "H350 – May cause cancer",
        "ppe_required": "P3 respirator, nitrile gloves",
        "disposal": "Cobalt refiner; declare weight on shipping manifest",
    },
    "electrolyte_solvent": {
        "hazard_class": "H225 – Highly flammable; H302 – Harmful if swallowed",
        "ppe_required": "Flame-retardant gloves, face shield, ventilated area",
        "disposal": "Solvent recovery facility",
    },
}

_TARGET_METALS: Dict[str, Dict[str, Any]] = {
    "lithium":   {"recovery_purity_pct": 95, "market_value_usd_per_kg": 22},
    "cobalt":    {"recovery_purity_pct": 98, "market_value_usd_per_kg": 33},
    "nickel":    {"recovery_purity_pct": 97, "market_value_usd_per_kg": 14},
    "manganese": {"recovery_purity_pct": 92, "market_value_usd_per_kg": 2},
    "copper":    {"recovery_purity_pct": 99, "market_value_usd_per_kg": 8},
    "aluminium": {"recovery_purity_pct": 99, "market_value_usd_per_kg": 2},
    "steel":     {"recovery_purity_pct": 99, "market_value_usd_per_kg": 0.5},
}

# Product-type → disassembly sequence template
_DISASSEMBLY_SEQUENCES: Dict[str, List[Dict[str, Any]]] = {
    "EV_BATTERY_CELL": [
        {"step": 1, "action": "Discharge to ≤ 2 V using resistive load — CRITICAL SAFETY STEP"},
        {"step": 2, "action": "Remove protective outer casing (4× M6 screws)"},
        {"step": 3, "action": "Separate anode (graphite) from cathode (NMC/LFP) foils"},
        {"step": 4, "action": "Drain and collect electrolyte solvent into sealed container"},
        {"step": 5, "action": "Sort foils by material type; weigh and bag separately"},
    ],
    "BATTERY_PACK": [
        {"step": 1, "action": "Isolate high-voltage system — engage manual service disconnect"},
        {"step": 2, "action": "Discharge pack to < 30 V via controlled load"},
        {"step": 3, "action": "Remove BMS (Battery Management System) PCB — label connector positions"},
        {"step": 4, "action": "Separate individual cell modules — do NOT short terminals"},
        {"step": 5, "action": "Remove thermal management plates (aluminium — high recovery value)"},
        {"step": 6, "action": "Disassemble each cell per EV_BATTERY_CELL sequence"},
    ],
    "EV": [
        {"step": 1, "action": "Deactivate 12 V auxiliary battery first"},
        {"step": 2, "action": "Remove high-voltage traction battery pack (see BATTERY_PACK sequence)"},
        {"step": 3, "action": "Drain coolant loop — collect for reuse"},
        {"step": 4, "action": "Remove electric motor (copper windings — high value)"},
        {"step": 5, "action": "Strip body panels (aluminium) and sort ferrous / non-ferrous"},
        {"step": 6, "action": "Drain and collect remaining fluids (brake, washer) per MSDS"},
    ],
    "DEFAULT": [
        {"step": 1, "action": "Consult product-specific service manual"},
        {"step": 2, "action": "Identify and isolate all power sources"},
        {"step": 3, "action": "Remove outer enclosure; photograph internal layout"},
        {"step": 4, "action": "Separate PCBs, metals, plastics into labelled bins"},
    ],
}


def generate_recycling_matrix(
    twin_id: str,
    product_type: str,
    current_chemistry: Dict[str, Any],
    material_weights_kg: Dict[str, Any],
    current_soh_pct: Optional[float],
) -> Dict[str, Any]:
    """
    Build a complete recycling / dismantling matrix for a Digital Twin.

    Returns a structured dict suitable for direct JSON export.
    """
    chemistry_lower = {k.lower(): v for k, v in (current_chemistry or {}).items()}
    weights_lower = {k.lower(): v for k, v in (material_weights_kg or {}).items()}

    # ── Hazardous additives present in this asset ─────────────────────────────
    hazards: List[Dict[str, Any]] = []
    for material, info in _HAZARDOUS_MATERIALS.items():
        if material in chemistry_lower or material in weights_lower:
            weight = weights_lower.get(material, "unknown")
            hazards.append({
                "material": material,
                "estimated_weight_kg": weight,
                **info,
            })

    # ── High-value target metals ──────────────────────────────────────────────
    targets: List[Dict[str, Any]] = []
    estimated_total_usd = 0.0
    for metal, meta in _TARGET_METALS.items():
        weight_kg = weights_lower.get(metal)
        if weight_kg and isinstance(weight_kg, (int, float)) and weight_kg > 0:
            recoverable_kg = weight_kg * (meta["recovery_purity_pct"] / 100)
            value_usd = recoverable_kg * meta["market_value_usd_per_kg"]
            estimated_total_usd += value_usd
            targets.append({
                "metal": metal,
                "gross_weight_kg": round(weight_kg, 3),
                "recoverable_kg": round(recoverable_kg, 3),
                "recovery_purity_pct": meta["recovery_purity_pct"],
                "estimated_value_usd": round(value_usd, 2),
            })

    # ── Disassembly sequence ──────────────────────────────────────────────────
    sequence = _DISASSEMBLY_SEQUENCES.get(
        product_type.upper(),
        _DISASSEMBLY_SEQUENCES["DEFAULT"]
    )

    # If SoH is very low, prepend extra safety warning
    safety_prefix = []
    if current_soh_pct is not None and current_soh_pct < 20:
        safety_prefix = [{
            "step": 0,
            "action": (
                f"WARNING: SoH = {current_soh_pct:.1f}% — severely degraded cell.  "
                "Increased risk of thermal runaway.  Ensure Class D fire extinguisher present "
                "and work in ventilated area only."
            ),
        }]

    return {
        "twin_id": twin_id,
        "product_type": product_type,
        "current_soh_pct": current_soh_pct,
        "hazardous_materials": hazards,
        "target_metals": sorted(targets, key=lambda x: x["estimated_value_usd"], reverse=True),
        "estimated_recovery_value_usd": round(estimated_total_usd, 2),
        "disassembly_sequence": safety_prefix + sequence,
        "regulatory_references": [
            "EU Battery Regulation 2023/1542 (Annex XIII)",
            "WEEE Directive 2012/19/EU",
            "RoHS Directive 2011/65/EU",
        ],
    }
