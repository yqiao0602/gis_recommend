"""Where did all single-operator (1-step potential) discovery records go, by action value?"""
import json
import collections
from pathlib import Path

WT = Path(__file__).resolve().parents[1]
BASE = WT / "benchmarks" / "qgis_planner_v1" / "authority"
P1 = WT / "docs/reports/qgis_mapping_high_impact_blockers_2026-07-24/stable101_all1442_source_replay_v1/routing_v6/routing_manifest.jsonl"
P2 = WT / "docs/reports/qgis_processing_mapping_gap_stable106_v1/l3_replay_v1/l3_gated_manifest_v1.jsonl"
ALLOWED_ACTIONS = {"auto_accept_candidate", "recover_call_graph", "split_subworkflow"}

cands = [json.loads(l) for l in (BASE / "candidate_supply.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
adm_refs = {c["discovery_ref"] for c in cands if c.get("discovery_ref")}
one_step_admitted = [c for c in cands if c.get("graph_size_stratum") == "one_step"]
print("admitted one_step candidates:", len(one_step_admitted),
      "| distinct DAGs:", len({c['normalized_dag_key'] for c in one_step_admitted}),
      "| ops:", {p['operator_id'] for c in one_step_admitted for p in c['processes']})

counts = collections.Counter()
for label, p in [("routing_v6", P1), ("stable106", P2)]:
    for i, line in enumerate(p.read_text(encoding="utf-8").splitlines()):
        if not line.strip():
            continue
        r = json.loads(line)
        ops = r.get("ordered_operator_ids") or r.get("operator_ids") or []
        if len(ops) != 1:
            continue
        ref = f"{label}:{i}"
        if ref in adm_refs:
            counts[("admitted", label)] += 1
        else:
            counts[(r.get("action"), label)] += 1
print()
print("single-operator records by fate (action, pool):")
for k, v in sorted(counts.items(), key=lambda kv: -kv[1]):
    print(f"  {v:5d}  {k}")
