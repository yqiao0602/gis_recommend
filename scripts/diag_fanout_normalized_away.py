"""Diagnose the 19 admitted candidates whose discovery fan-out did not survive to candidate links."""
import json
import collections
from pathlib import Path

WT = Path(__file__).resolve().parents[1]
BASE = WT / "benchmarks" / "qgis_planner_v1" / "authority"
P1 = WT / "docs/reports/qgis_mapping_high_impact_blockers_2026-07-24/stable101_all1442_source_replay_v1/routing_v6/routing_manifest.jsonl"
P2 = WT / "docs/reports/qgis_processing_mapping_gap_stable106_v1/l3_replay_v1/l3_gated_manifest_v1.jsonl"

recs = {}
for label, p in [("stable101_routing_v6", P1), ("stable106_catalog_miss_replay", P2)]:
    for i, line in enumerate(p.read_text(encoding="utf-8").splitlines()):
        if line.strip():
            recs[f"{label}:{i}"] = json.loads(line)

cands = [json.loads(l) for l in (BASE / "candidate_supply.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
cap = [json.loads(l) for l in (BASE / "capability_matrix.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
admitted_ops = set()
for r in cap:
    admitted_ops.update(r["admitted_operator_ids"])
byref = {c["discovery_ref"]: c for c in cands if c.get("discovery_ref")}

rows = []
for ref, r in recs.items():
    edges = r.get("dependency_edges") or []
    if not edges:
        continue
    outdeg = collections.Counter(e[0] for e in edges)
    if not any(v >= 2 for v in outdeg.values()):
        continue
    ops = set(r.get("operator_ids") or r.get("canonical_operator_ids") or [])
    if not (ops and ops <= admitted_ops):
        continue
    c = byref.get(ref)
    if c is None:
        continue
    clinks = [(l["source_process_id"], l["target_process_id"]) for l in c["links"]]
    disc = sorted((s, t) for s, t in edges)
    same = sorted((int(s[1:]), int(t[1:])) for s, t in clinks) == disc
    rows.append({
        "ref": ref,
        "action": r.get("action"),
        "discovery_edges": disc,
        "candidate_links": clinks,
        "candidate_topology": c["topology"],
        "edges_preserved": same,
        "n_ops": len(c["processes"]),
    })

print("admitted fan-out records:", len(rows))
preserved = [r for r in rows if r["edges_preserved"]]
print("edges fully preserved:", len(preserved))
print("edges altered/dropped:", len(rows) - len(preserved))
print()
for r in rows[:8]:
    print(r["ref"], "| action:", r["action"], "| topology:", r["candidate_topology"], "| preserved:", r["edges_preserved"])
    print("   disc:", r["discovery_edges"])
    print("   cand:", r["candidate_links"])
topo = collections.Counter(r["candidate_topology"] for r in rows)
print()
print("candidate topology of the admitted fan-out records:", dict(topo))
acts = collections.Counter(r["action"] for r in rows)
print("actions:", dict(acts))
