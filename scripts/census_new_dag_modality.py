"""Compute modality + budget-gap aggregation for the 24 new DAGs from the action-gate census."""
import json
import collections
from pathlib import Path

WT = Path(__file__).resolve().parents[1]
BASE = WT / "benchmarks" / "qgis_planner_v1" / "authority"

catalog_artifact = json.loads((BASE / "qgis_catalog.json").read_text(encoding="utf-8"))
catalog = {row["operator_id"]: row for row in catalog_artifact["operators"]}

def modality_of(ops):
    kinds = set()
    for op in ops:
        entry = catalog.get(op, {})
        # mirror pool builder's _modality via operator catalog input/output kinds if present
        for key in ("input_kind", "output_kind", "data_kind", "modality"):
            v = entry.get(key)
            if isinstance(v, str):
                kinds.add(v.lower())
    return kinds

cen = json.loads((BASE / "v02_action_gate_reconciliation_v1.json").read_text(encoding="utf-8"))
# rebuild operator lists for new DAGs from discovery refs
P1 = WT / "docs/reports/qgis_mapping_high_impact_blockers_2026-07-24/stable101_all1442_source_replay_v1/routing_v6/routing_manifest.jsonl"
P2 = WT / "docs/reports/qgis_processing_mapping_gap_stable106_v1/l3_replay_v1/l3_gated_manifest_v1.jsonl"
recs = {}
for label, p in [("stable101_routing_v6", P1), ("stable106_catalog_miss_replay", P2)]:
    for i, line in enumerate(p.read_text(encoding="utf-8").splitlines()):
        if line.strip():
            recs[f"{label}:{i}"] = json.loads(line)

RASTER_HINTS = {"raster", "grid", "dem"}
VECTOR_HINTS = {"vector", "feature", "table"}

def guess_modality(ops):
    has_r = False
    has_v = False
    for op in ops:
        entry = catalog.get(op, {})
        blob = json.dumps(entry).lower()
        if any(h in blob for h in RASTER_HINTS):
            has_r = True
        if any(h in blob for h in VECTOR_HINTS):
            has_v = True
    if has_r and has_v:
        return "mixed"
    if has_r:
        return "raster"
    if has_v:
        return "vector"
    return "unknown"

new_dags = cen["new_dags"]
mods = []
for d in new_dags:
    ref = d["discovery_refs"][0]
    ops = [str(v).lower() for v in (recs[ref].get("ordered_operator_ids") or recs[ref].get("operator_ids") or [])]
    m = guess_modality(ops)
    mods.append((d["topology_class"], d["graph_size_stratum"], m, d["quota_anchor_l3"], len(d["discovery_refs"])))

print("24 new DAGs (topology, size, modality, anchor, records):")
for t in mods:
    print("  ", t)
print()
print("modality:", dict(collections.Counter(m for _,_,m,_,_ in mods)))
print("raster+mixed:", sum(1 for _,_,m,_,_ in mods if m in ("raster", "mixed")))
print("1-step:", sum(1 for d in new_dags if d["graph_size_stratum"] == "one_step"))
