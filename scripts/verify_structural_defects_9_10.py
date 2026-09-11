"""Verify the two structural data defects (#9 fc01749f30 edges, #10 dec749a979 operator id)
against the actual source scripts and discovery records, before fixing them."""
import json
import sys
from pathlib import Path

WT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WT))
BASE = WT / "benchmarks" / "qgis_planner_v1" / "authority"
P1 = WT / "docs/reports/qgis_mapping_high_impact_blockers_2026-07-24/stable101_all1442_source_replay_v1/routing_v6/routing_manifest.jsonl"
P2 = WT / "docs/reports/qgis_processing_mapping_gap_stable106_v1/l3_replay_v1/l3_gated_manifest_v1.jsonl"

recs = {}
for label, p in [("stable101_routing_v6", P1), ("stable106_catalog_miss_replay", P2)]:
    for i, line in enumerate(p.read_text(encoding="utf-8").splitlines()):
        if line.strip():
            recs[f"{label}:{i}"] = json.loads(line)

cen = json.loads((BASE / "v02_action_gate_reconciliation_v1.json").read_text(encoding="utf-8"))

# --- #9: fc01749f30 (packet says linear 4-6, Buffer+Union anchor Buffer) ---
e9 = next(d for d in cen["new_dags"] if d["normalized_dag_key"].startswith("fc01749f30"))
ref9 = e9["discovery_refs"][0]
r9 = recs[ref9]
print("=== #9 fc01749f30 ===")
print("ref:", ref9)
print("operators:", r9.get("ordered_operator_ids") or r9.get("operator_ids"))
print("recorded dependency_edges:", r9.get("dependency_edges"))
print("source_path:", r9.get("source_path"))
print("call_sites (operator, lines, output role):")
for cs in (r9.get("call_sites") or []):
    print("  ", cs.get("operator_id"), f"L{cs.get('line_start')}-{cs.get('line_end')}", "out->", (cs.get("output_role") or {}).get("target"))
print("dependency_edge_evidence:", json.dumps(r9.get("dependency_edge_evidence"), ensure_ascii=False)[:600])
print()

# --- #10: dec749a979 (packet records native:zonalstatisticsfb; B says legacy qgis:zonalstatistics) ---
e10 = next(d for d in cen["new_dags"] if d["normalized_dag_key"].startswith("dec749a979"))
ref10 = e10["discovery_refs"][0]
r10 = recs[ref10]
print("=== #10 dec749a979 ===")
print("ref:", ref10)
print("original_operator_ids:", r10.get("original_operator_ids"))
print("canonical/operator_ids:", r10.get("canonical_operator_ids") or r10.get("operator_ids"))
print("provider_migrations:", json.dumps(r10.get("provider_migrations"), ensure_ascii=False))
print("source_path:", r10.get("source_path"))
for cs in (r10.get("call_sites") or [])[-3:]:
    print("  call_site:", cs.get("operator_id"), f"L{cs.get('line_start')}-{cs.get('line_end')}")
print()

# check the mapping authority for both zonal variants
mapping = json.loads((BASE / "qgis_operator_l3_mapping.json").read_text(encoding="utf-8"))
for op in ("qgis:zonalstatistics", "native:zonalstatisticsfb", "native:zonalstatistics"):
    m = next((e for e in mapping["entries"] if e["operator_id"] == op), None)
    if m:
        print("mapping:", op, "->", m.get("stable101_l3"), "| strict:", m.get("strict_catalog_present"), "| status:", m.get("mapping_status"), "| headline:", m.get("headline_eligible"))
    else:
        print("mapping:", op, "-> NOT IN MAPPING")
