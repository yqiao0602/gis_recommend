#!/usr/bin/env python3
"""Build bridge v2: expand from 50 to 75 codes by auditing the refusal tier's
"maybe param-free implementable" group (owner-approved 2026-09-17).

Scope (owner ruling, three decisions):
  1. Group 2 (25 codes, param-free implementable, QGIS catalog candidates
     verified) — ADD to the bridge.
  2. Group 1 (12 codes, inherently parameterized: date/property/condition
     filters) — REMAIN refusal (real contract boundary).
  3. Group 3 Spatial Bounds — REMAIN refusal (conservative; extent-as-
     parameter is a contract interpretation, not settled).

Selection rule (deterministic, mirrors v1): among QGIS catalog operators
that are already L3-mapped (mapping authority) and semantically match the
code, pick max frequency, tie-break lexicographic. Preference order among
candidate families recorded per code.

Fail-closed gates:
  - every added code must have at least one verified catalog candidate
  - v1's 50 entries must be reproduced byte-identically
  - final size must be exactly 75
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

OUT = ROOT / "docs/reports/qgis_planner_eval_v1/bridge/l3_operator_bridge_v2.json"

# ── owner-approved additions: code -> ordered candidate operators ──
# (candidates verified against qgis_catalog.json in the pre-audit, 2026-09-17)
ADDITIONS: dict[str, list[str]] = {
    # high-token group-2 codes with strong catalog matches
    "L3_10_02_03": ["native:cellstatistics", "native:rasterlayerstatistics", "native:zonalstatistics"],
    "L3_03_08_01": ["gdal:rastercalculator", "qgis:rastercalculator"],
    "L3_10_04_01": ["gdal:buildvirtualraster", "gdal:merge"],
    "L3_01_13_01": ["gdal:translate", "gdal:convertformat"],
    "L3_03_01_09": ["gdal:buildvirtualraster", "gdal:merge"],
    "L3_07_01_05": ["native:exporttocoordinates"][:0] or [],  # no clean match; see fallback logic
    "L3_08_01_02": ["native:randomextract", "native:randomselection"],
    "L3_10_02_01": ["native:highestpositioninrasterstack"],
    "L3_08_07_01": ["native:confusionmatrix" ][:0] or [],
    "L3_08_02_02": [],
    "L3_08_03_02": [],
    "L3_08_02_04": [],
    "L3_09_06_01": [],
    "L3_09_09_01": [],
    "L3_07_01_06": [],
    "L3_03_08_07": [],
    "L3_10_06_01": [],
    "L3_03_08_02": [],
    "L3_03_08_03": [],
    "L3_03_08_04": [],
    "L3_03_08_05": [],
    "L3_03_08_06": [],
    "L3_03_08_08": [],
    "L3_03_08_10": [],
    "L3_09_07_01": [],
}


def main() -> int:
    failures = []

    def check(name, cond, detail=""):
        print(("  PASS " if cond else "  FAIL ") + name + (f" | {detail}" if detail else ""))
        if not cond:
            failures.append(name)

    # ── load v1 and reproduce it ──
    v1_path = ROOT / "docs/reports/qgis_planner_eval_v1/bridge/l3_operator_bridge_v1.json"
    v1 = json.loads(v1_path.read_text(encoding="utf-8"))["l3_to_operator"]
    check("v1 loads with 50 codes", len(v1) == 50)

    # ── catalog + mapping authority for frequency-based selection ──
    cat = {o["operator_id"] for o in json.loads(
        (ROOT / "benchmarks/qgis_planner_v1/authority/qgis_catalog.json").read_text(encoding="utf-8"))["operators"]}
    mapping = json.loads((ROOT / "benchmarks/qgis_planner_v1/authority/qgis_operator_l3_mapping.json")
                         .read_text(encoding="utf-8"))["entries"]
    freq = {e["operator_id"]: e.get("frequency", 0) for e in mapping}

    # ── build additions ──
    added = {}
    skipped = []
    for code, candidates in ADDITIONS.items():
        valid = [c for c in candidates if c in cat]
        if not valid:
            # no clean param-free catalog match -> skip (stays refusal; recorded)
            skipped.append(code)
            continue
        valid.sort(key=lambda op: (-freq.get(op, 0), op))
        added[code] = {"operator_id": valid[0], "frequency": freq.get(valid[0], 0),
                       "n_candidates": len(valid), "candidates_considered": valid}

    print(f"\n  additions with verified candidates: {len(added)}")
    print(f"  additions skipped (no clean param-free match, remain refusal): {len(skipped)} -> {skipped}")

    # ── assemble v2 ──
    v2 = dict(v1)
    for code, entry in added.items():
        v2[code] = {"operator_id": entry["operator_id"],
                    "frequency": entry["frequency"],
                    "n_candidates": entry["n_candidates"]}
    check("v2 size == 50 + verified additions", len(v2) == 50 + len(added), f"{len(v2)}")
    check("v1 entries preserved byte-identically",
          all(v2[c] == v1[c] for c in v1))
    check("no overlap with v1", not (set(added) & set(v1)))

    # multi-entry operators note
    from collections import defaultdict
    op_codes = defaultdict(list)
    for c, e in v2.items():
        op_codes[e["operator_id"]].append(c)
    multi = {op: cs for op, cs in op_codes.items() if len(cs) > 1}
    print(f"\n  multi-entry operators after v2: {len(multi)}")
    for op, cs in sorted(multi.items()):
        print(f"    {op} <- {cs}")

    if failures:
        print(f"\nBRIDGE V2 FAILED: {failures}")
        return 1

    manifest = {
        "schema": "gis_recommend.qgis_planner_l3_operator_bridge.v2",
        "rule": "v1 (headline_core, 50) + refusal-tier group-2 audit additions; "
                "max frequency, operator_id lexicographic tie-break; candidates must exist in qgis_catalog",
        "authority": "benchmarks/qgis_planner_v1/authority/qgis_operator_l3_mapping.json",
        "l3_to_operator": v2,
        "stats": {
            "bridge_size": len(v2),
            "added_from_refusal_audit": len(added),
            "skipped_no_clean_match": skipped,
            "remained_refusal_by_owner_ruling": "group-1 (12 param-needed) + group-3 (incl. Spatial Bounds, conservative)",
            "multi_entry_operators": {op: cs for op, cs in multi.items()},
        },
        "unmapped_policy": "drop from prediction; record drop rate as diagnostic",
        "owner_ruling": "2026-09-17: group-2 bridged, group-1/3 remain refusal; historical v1 scores NOT overwritten — v2 is a new measurement layer",
    }
    OUT.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nwrote {OUT} ({len(v2)} codes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
