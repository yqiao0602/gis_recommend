# -*- coding: utf-8 -*-
"""
Build outputs_v2/id_mappings_v2.json.

Assembles a v2 id_mappings file that step6 can consume in place of the
original outputs/id_mappings.json.  Sections:
  - gee_op, qgis_op              : copied unchanged from v1
  - l1, l2                       : trimmed to v2-surviving codes
  - l3                           : v2 vocab (94 codes) with new integer ids
  - metadata                     : bumped version
  - mapping_metadata.gee_to_l3  : loaded from outputs_v2/mapping_metadata_v2.json
  - mapping_metadata.qgis_to_l3 : auto-remapped from v1 via the merge plan
"""
from __future__ import annotations
import csv
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OLD_ID_MAPPINGS = ROOT / "outputs" / "id_mappings.json"
HIER_V2_CSV = ROOT / "outputs_v2" / "classification_hierarchy_v2.csv"
MERGE_PLAN_CSV = ROOT / "outputs_v2" / "l3_merge_plan.csv"
MAPPING_V2_JSON = ROOT / "outputs_v2" / "mapping_metadata_v2.json"
VOCAB_V2_JSON = ROOT / "outputs_v2" / "l3_vocab_v2.json"

OUT = ROOT / "outputs_v2" / "id_mappings_v2.json"


def main():
    with OLD_ID_MAPPINGS.open(encoding="utf-8") as f:
        old = json.load(f)
    with MAPPING_V2_JSON.open(encoding="utf-8") as f:
        gee_v2 = json.load(f)["gee_to_l3"]
    with VOCAB_V2_JSON.open(encoding="utf-8") as f:
        vocab = json.load(f)

    # L3 map: use the SAME numeric ids as our vocab file (code_to_id).
    l3_map = dict(vocab["code_to_id"])

    # Build L2/L1 maps from surviving L3s
    surviving_l2: dict[str, int] = {}
    surviving_l1: dict[str, int] = {}
    l2_rows: list[tuple[str, str]] = []
    l1_rows: list[tuple[str, str]] = []
    with HIER_V2_CSV.open(encoding="utf-8") as f:
        for r in csv.DictReader(f):
            if r["l2_code"] not in surviving_l2:
                surviving_l2[r["l2_code"]] = len(surviving_l2)
                l2_rows.append((r["l2_code"], r["l2_name"]))
            if r["l1_code"] not in surviving_l1:
                surviving_l1[r["l1_code"]] = len(surviving_l1)
                l1_rows.append((r["l1_code"], r["l1_name"]))

    # Remap old qgis_to_l3 entries through the merge plan (to the extent we
    # can; step6 only uses gee_to_l3 for GEE ops but the QGIS map is kept for
    # downstream QGIS recommendation).
    merge_map: dict[str, tuple[str, str]] = {}
    with MERGE_PLAN_CSV.open(encoding="utf-8") as f:
        for r in csv.DictReader(f):
            merge_map[r["old_l3"]] = (r["action"], r["new_l3"])

    old_qgis = old.get("mapping_metadata", {}).get("qgis_to_l3", {})
    v2_vocab = set(l3_map.keys())
    new_qgis: dict[str, dict] = {}
    for op, meta in old_qgis.items():
        cands = meta.get("all_candidates", [])
        remapped: dict[str, dict] = {}
        for c in cands:
            old_code = c.get("l3_code")
            if not old_code:
                continue
            action, new_code = merge_map.get(old_code, ("keep", old_code))
            if action == "delete":
                continue
            if new_code not in v2_vocab:
                continue
            existing = remapped.get(new_code)
            if existing is None or c.get("confidence", 0) > existing.get("confidence", 0):
                nc = dict(c)
                nc["l3_code"] = new_code
                remapped[new_code] = nc
        if not remapped:
            continue
        primary = max(remapped.values(), key=lambda c: c.get("confidence", 0))
        new_qgis[op] = {
            "all_candidates": list(remapped.values()),
            "num_candidates": len(remapped),
            "mapping_type": meta.get("mapping_type", "remapped"),
            "mapping_confidence": primary.get("confidence", 0.5),
            "rationale": "v2 remap",
            "has_ambiguity": len(remapped) > 1,
            "primary_l3": primary["l3_code"],
            "source": "auto_remap",
        }

    out = {
        "metadata": {
            "version": "v2",
            "source": "outputs_v2/id_mappings_v2.json",
            "l3_vocab_size": len(l3_map),
            "l2_count": len(surviving_l2),
            "l1_count": len(surviving_l1),
        },
        "gee_op": old.get("gee_op", {}),
        "qgis_op": old.get("qgis_op", {}),
        "l3": l3_map,
        "l2": {code: idx for code, idx in surviving_l2.items()},
        "l1": {code: idx for code, idx in surviving_l1.items()},
        "mapping_metadata": {
            "gee_to_l3": gee_v2,
            "qgis_to_l3": new_qgis,
        },
    }

    with OUT.open("w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False)
    print(f"Wrote {OUT}")
    print(f"  l3: {len(l3_map)}  l2: {len(surviving_l2)}  l1: {len(surviving_l1)}")
    print(f"  gee_to_l3: {len(gee_v2)}  qgis_to_l3: {len(new_qgis)}")


if __name__ == "__main__":
    main()
