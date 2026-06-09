#!/usr/bin/env python3
"""
Apply the final small batch of hand-reviewed mapping tail fixes.

Scope is intentionally narrow:
1. Resolve QGIS mappings that still point to deleted v1/v1.5 L3 codes.
2. Remap a small set of REVIEW items that are still obviously stuck in
   L3_03_03_L (Logical & Comparison).
3. Skip a tiny number of obvious GEE helper/configuration methods that are
   not standalone GIS transformation operators.
"""

from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ID_MAPPINGS = ROOT / "outputs_v2" / "id_mappings_v2.json"
GEE_MAPPING = ROOT / "outputs_v2" / "mapping_metadata_v2.json"
GEE_SKIP = ROOT / "outputs_v2" / "gee_skip_list_v2.json"
TRIAGE = ROOT / "outputs_v2" / "mapping_audit_triage.json"

VERSION = "v2.4-tailfixed"

QGIS_REMAPS = {
    "Sieve": {
        "new_l3": "L3_03_04_01",
        "confidence": 0.85,
        "decision": "T2",
        "reason": "Use REVIEW T2 Reclassify / Remap; previous primary_l3 referenced deleted legacy logical-op code.",
    },
    "i.fft": {
        "new_l3": "L3_03_08_07",
        "confidence": 0.95,
        "decision": "L3_03_08_07",
        "reason": "FFT/IFFT no longer have a dedicated active L3 in v2; fold them into Spectral Transformations.",
    },
    "i.ifft": {
        "new_l3": "L3_03_08_07",
        "confidence": 0.95,
        "decision": "L3_03_08_07",
        "reason": "FFT/IFFT no longer have a dedicated active L3 in v2; fold them into Spectral Transformations.",
    },
    "v.univar": {
        "new_l3": "L3_03_02_05",
        "confidence": 0.95,
        "decision": "T3",
        "reason": "Univariate statistics aligns with Global Statistics, not Logical & Comparison.",
    },
    "r.sun.incidout": {
        "new_l3": "L3_04_01_01",
        "confidence": 0.85,
        "decision": "T1",
        "reason": "Solar incidence modeling is a terrain/surface-parameter operation, not a logical comparison.",
    },
    "r.sunhours": {
        "new_l3": "L3_04_01_01",
        "confidence": 0.85,
        "decision": "T1",
        "reason": "Sun-hours calculation belongs with surface-parameter terrain analysis, not Logical & Comparison.",
    },
    "Sky View Factor": {
        "new_l3": "L3_04_01_01",
        "confidence": 0.85,
        "decision": "T1",
        "reason": "Sky-view factor is a terrain-derived surface parameter, not a logical comparison primitive.",
    },
    "Upslope Area": {
        "new_l3": "L3_04_01_01",
        "confidence": 0.85,
        "decision": "T1",
        "reason": "Upslope contributing area is a terrain/surface-analysis quantity, not Logical & Comparison.",
    },
    "Wind Effect": {
        "new_l3": "L3_04_01_01",
        "confidence": 0.85,
        "decision": "T1",
        "reason": "Wind-exposure terrain effect is a surface-parameter style operation, not Logical & Comparison.",
    },
    "Burn Stream Network into DEM": {
        "new_l3": "L3_04_01_01",
        "confidence": 0.85,
        "decision": "T1",
        "reason": "DEM burning is terrain/hydrology adjustment work; Logical & Comparison is clearly the wrong bucket.",
    },
    "i.eb.evapfr": {
        "new_l3": "L3_03_03_A",
        "confidence": 0.82,
        "decision": "L3_03_03_A",
        "reason": "Evaporative-fraction estimation is a formula-driven raster derivation; Arithmetic & Math is a closer survivor than Logical & Comparison.",
    },
    "i.evapo.pt": {
        "new_l3": "L3_03_03_A",
        "confidence": 0.9,
        "decision": "L3_03_03_A",
        "reason": "Priestley-Taylor evapotranspiration is an explicit raster formula calculation; keep it with Arithmetic & Math, consistent with i.evapo.mh.",
    },
    "HyperspectralUnmixing": {
        "new_l3": "L3_03_08_07",
        "confidence": 0.82,
        "decision": "L3_03_08_07",
        "reason": "Linear spectral unmixing transforms hyperspectral bands into abundance components; Spectral Transformations is the closest active class.",
    },
    "Raster Cell Index": {
        "new_l3": "L3_03_04_01",
        "confidence": 0.9,
        "decision": "T1",
        "reason": "Ranking cells into an index grid is a value-to-rank remap, not a logical comparison.",
    },
}

QGIS_REMOVALS = {
    "r.solute.transport": {
        "decision": "REMOVE",
        "reason": "Audit target L3_04_02_01 was deleted in v2 and no defensible active survivor exists; remove instead of forcing a wrong class.",
    }
}

GEE_SKIP_FIXES = {
    "ee.projection.atscale": "Projection helper/configuration method, not a standalone GIS transformation operator.",
    "ee.image.arraylength": "Array-shape helper method; not a standalone GIS analysis operator and clearly not phenology Length of Season.",
    "ee.image.arraylengths": "Array-shape helper method; not a standalone GIS analysis operator and clearly not phenology Length of Season.",
    "ee.image.arrayrepeat": "Array-manipulation helper method; not a standalone GIS analysis operator and clearly not phenology Length of Season.",
    "ee.image.bitstoarrayimage": "Bit/array conversion helper method; not a standalone GIS analysis operator and clearly not phenology Length of Season.",
}


def update_entry(entry: dict, new_l3: str, confidence: float, reason: str) -> None:
    entry["primary_l3"] = new_l3
    entry["all_candidates"] = [{
        "l3_code": new_l3,
        "confidence": confidence,
        "role": "manual_tail_fix",
        "execution_order": 1,
    }]
    entry["num_candidates"] = 1
    entry["mapping_type"] = "manual_tail_fix"
    entry["mapping_confidence"] = confidence
    entry["rationale"] = f"manual tail fix: {reason}"
    entry["has_ambiguity"] = False
    entry["source"] = "manual_tail_fix"
    entry["override_reason"] = reason


def main() -> None:
    with ID_MAPPINGS.open(encoding="utf-8") as f:
        id_map = json.load(f)
    with GEE_MAPPING.open(encoding="utf-8") as f:
        gee_mapping_doc = json.load(f)
    with GEE_SKIP.open(encoding="utf-8") as f:
        gee_skip_doc = json.load(f)
    with TRIAGE.open(encoding="utf-8") as f:
        triage = json.load(f)

    qgis_to_l3 = id_map["mapping_metadata"]["qgis_to_l3"]
    gee_to_l3 = id_map["mapping_metadata"]["gee_to_l3"]
    gee_only = gee_mapping_doc["gee_to_l3"]
    skip_ops = set(gee_skip_doc["skip_operators"])
    triage_decisions = triage["decisions"]

    gee_ci = {k.lower(): k for k in gee_to_l3}
    gee_only_ci = {k.lower(): k for k in gee_only}

    stats = {
        "qgis_remapped": 0,
        "qgis_removed": 0,
        "gee_skipped": 0,
    }

    for op, fix in QGIS_REMAPS.items():
        if op not in qgis_to_l3:
            raise KeyError(f"QGIS mapping not found: {op}")
        update_entry(qgis_to_l3[op], fix["new_l3"], fix["confidence"], fix["reason"])
        triage_key = f"QGIS:{op}"
        if triage_key in triage_decisions:
            triage_decisions[triage_key]["user_decision"] = fix["decision"]
        stats["qgis_remapped"] += 1

    for op, fix in QGIS_REMOVALS.items():
        if op in qgis_to_l3:
            del qgis_to_l3[op]
            stats["qgis_removed"] += 1
        triage_key = f"QGIS:{op}"
        if triage_key in triage_decisions:
            triage_decisions[triage_key]["user_decision"] = fix["decision"]

    for op_lower, reason in GEE_SKIP_FIXES.items():
        skip_ops.add(op_lower)
        canon = gee_ci.get(op_lower)
        if canon:
            del gee_to_l3[canon]
            stats["gee_skipped"] += 1
        canon_only = gee_only_ci.get(op_lower)
        if canon_only:
            del gee_only[canon_only]
        # keep a provenance note in id_mappings metadata if the key exists later

    id_map["mapping_metadata"]["qgis_to_l3"] = qgis_to_l3
    id_map["mapping_metadata"]["gee_to_l3"] = gee_to_l3
    id_map["metadata"]["version"] = VERSION

    gee_mapping_doc["gee_to_l3"] = gee_only
    gee_mapping_doc["stats"]["total_entries"] = len(gee_only)
    gee_mapping_doc["version"] = VERSION

    gee_skip_doc["skip_operators"] = sorted(skip_ops)
    gee_skip_doc["version"] = VERSION

    with ID_MAPPINGS.open("w", encoding="utf-8") as f:
        json.dump(id_map, f, ensure_ascii=False, indent=2)
    with GEE_MAPPING.open("w", encoding="utf-8") as f:
        json.dump(gee_mapping_doc, f, ensure_ascii=False, indent=2)
    with GEE_SKIP.open("w", encoding="utf-8") as f:
        json.dump(gee_skip_doc, f, ensure_ascii=False, indent=2)
    with TRIAGE.open("w", encoding="utf-8") as f:
        json.dump(triage, f, ensure_ascii=False, indent=2)

    print("=== Tail Mapping Fix Summary ===")
    for key, value in stats.items():
        print(f"  {key}: {value}")
    print(f"  qgis_to_l3 entries: {len(qgis_to_l3)}")
    print(f"  gee_to_l3 entries : {len(gee_to_l3)}")
    print(f"  gee skip entries  : {len(skip_ops)}")


if __name__ == "__main__":
    main()
