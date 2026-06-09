# -*- coding: utf-8 -*-
"""
Apply Phase B triage decisions to the mapping files.

Reads outputs_v2/mapping_audit_triage.json and rewrites:
  - outputs_v2/mapping_metadata_v2.json
  - outputs_v2/gee_skip_list_v2.json

Rules:
  - bucket == "AGREE" or "REVIEW":  leave as-is
  - bucket == "STRONG_FIX":  rewrite primary_l3 + all_candidates to proposed
  - bucket == "SKIP":        remove from gee_to_l3 and add to skip list

The id_mappings_v2.json downstream also needs rebuilding (it embeds
mapping_metadata), so we call build_id_mappings_v2 afterwards in the pipeline.
"""
from __future__ import annotations
import csv
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TRIAGE = ROOT / "outputs_v2" / "mapping_audit_triage.json"
MAPPING = ROOT / "outputs_v2" / "mapping_metadata_v2.json"
SKIP = ROOT / "outputs_v2" / "gee_skip_list_v2.json"
HIER_V2 = ROOT / "outputs_v2" / "classification_hierarchy_v2.csv"
ID_MAPPINGS = ROOT / "outputs_v2" / "id_mappings_v2.json"


def main():
    with TRIAGE.open(encoding="utf-8") as f:
        triage = json.load(f)
    decisions = triage["decisions"]

    with MAPPING.open(encoding="utf-8") as f:
        mapping = json.load(f)
    gee_to_l3: dict = mapping["gee_to_l3"]

    with ID_MAPPINGS.open(encoding="utf-8") as f:
        id_map = json.load(f)
    qgis_to_l3: dict = id_map["mapping_metadata"]["qgis_to_l3"]

    with SKIP.open(encoding="utf-8") as f:
        skip_doc = json.load(f)
    skip_list: set[str] = set(skip_doc["skip_operators"])

    l3_name = {}
    for r in csv.DictReader(HIER_V2.open(encoding="utf-8")):
        l3_name[r["l3_code"]] = r["l3_name"]

    # Build case-insensitive key index for GEE (v1 remap kept camelCase)
    gee_ci = {k.lower(): k for k in gee_to_l3}

    stats = {"strong_fix_applied_gee": 0, "strong_fix_applied_qgis": 0,
             "skip_applied": 0, "skipped_missing_key": 0}

    for key, dec in decisions.items():
        if dec["bucket"] not in ("STRONG_FIX", "SKIP"):
            continue
        op = dec["op"]
        side = dec["side"]

        if dec["bucket"] == "STRONG_FIX":
            new_l3 = dec["proposed_l3"]
            if not new_l3 or new_l3 == "SKIP":
                continue
            new_name = l3_name.get(new_l3, "?")
            if side == "GEE":
                canon = gee_ci.get(op.lower())
                if not canon:
                    stats["skipped_missing_key"] += 1
                    continue
                entry = gee_to_l3[canon]
                entry["primary_l3"] = new_l3
                entry["all_candidates"] = [{
                    "l3_code": new_l3, "confidence": dec["confidence"],
                    "role": "audit_v2_override", "execution_order": 1,
                }]
                entry["num_candidates"] = 1
                entry["mapping_type"] = "audit_v2_override"
                entry["mapping_confidence"] = dec["confidence"]
                entry["rationale"] = f"LLM audit: {dec['reason'][:80]}"
                entry["has_ambiguity"] = False
                entry["source"] = "audit_override"
                stats["strong_fix_applied_gee"] += 1
            else:  # QGIS
                if op not in qgis_to_l3:
                    stats["skipped_missing_key"] += 1
                    continue
                entry = qgis_to_l3[op]
                entry["primary_l3"] = new_l3
                entry["all_candidates"] = [{
                    "l3_code": new_l3, "confidence": dec["confidence"],
                    "role": "audit_v2_override", "execution_order": 1,
                }]
                entry["num_candidates"] = 1
                entry["mapping_type"] = "audit_v2_override"
                entry["mapping_confidence"] = dec["confidence"]
                entry["rationale"] = f"LLM audit: {dec['reason'][:80]}"
                entry["has_ambiguity"] = False
                entry["source"] = "audit_override"
                stats["strong_fix_applied_qgis"] += 1

        elif dec["bucket"] == "SKIP":
            # All SKIP entries are GEE per triage output
            canon = gee_ci.get(op.lower())
            if canon and canon in gee_to_l3:
                del gee_to_l3[canon]
            skip_list.add(op.lower())
            stats["skip_applied"] += 1

    # Rewrite outputs
    mapping["stats"]["total_entries"] = len(gee_to_l3)
    mapping["version"] = "v2.1-audited"
    with MAPPING.open("w", encoding="utf-8") as f:
        json.dump(mapping, f, ensure_ascii=False, indent=2)

    id_map["mapping_metadata"]["qgis_to_l3"] = qgis_to_l3
    id_map["mapping_metadata"]["gee_to_l3"] = gee_to_l3  # sync copy in id_mappings too
    id_map["metadata"]["version"] = "v2.1-audited"
    with ID_MAPPINGS.open("w", encoding="utf-8") as f:
        json.dump(id_map, f, ensure_ascii=False)

    skip_doc["skip_operators"] = sorted(skip_list)
    skip_doc["version"] = "v2.1-audited"
    with SKIP.open("w", encoding="utf-8") as f:
        json.dump(skip_doc, f, ensure_ascii=False, indent=2)

    print("=== Apply Mapping Audit — Summary ===")
    for k, v in stats.items():
        print(f"  {k}: {v}")
    print(f"  gee_to_l3 entries after : {len(gee_to_l3)}")
    print(f"  qgis_to_l3 entries after: {len(qgis_to_l3)}")
    print(f"  skip_list entries after : {len(skip_list)}")
    print(f"\nWrote:\n  {MAPPING}\n  {SKIP}\n  {ID_MAPPINGS}")


if __name__ == "__main__":
    main()
