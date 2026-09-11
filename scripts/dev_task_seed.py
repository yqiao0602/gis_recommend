"""Enumerate the 20 dev DAGs, map them to available task texts or derivation needs.

The 21 reviewed task candidates (v02_task_derivation_v4.jsonl) cover 21
recovered DAGs. The dev selection ledger's entries reference pool keys
(existing-pool 12-hex prefixes or recovered 10-hex ids). This script:
  - resolves each dev DAG's identity (existing pool vs recovered)
  - marks which already have a reviewed task text (recovered ones)
  - for the rest, pulls full derivation inputs (operators, edges, call
    sites, source refs) into a dev derivation worksheet seed
"""
import json
import collections
from pathlib import Path

WT = Path(__file__).resolve().parents[1]
BASE = WT / "benchmarks" / "qgis_planner_v1" / "authority"
P1 = WT / "docs/reports/qgis_mapping_high_impact_blockers_2026-07-24/stable101_all1442_source_replay_v1/routing_v6/routing_manifest.jsonl"
P2 = WT / "docs/reports/qgis_processing_mapping_gap_stable106_v1/l3_replay_v1/l3_gated_manifest_v1.jsonl"

led = json.loads((BASE / "v02_dev_final_selection_ledger_v1.json").read_text(encoding="utf-8"))
dev_entries = led["dev_side"]["entries"]
print("dev DAGs:", len(dev_entries))

# task set v4: which recovered DAGs have reviewed texts
v4 = [json.loads(l) for l in (BASE / "v02_task_derivation_v4.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
tasked_keys = {r["packet_entry_id"].replace("recovered-", "")[:10] for r in v4[1:]}

# pool reconstruction for identity resolution
roster = json.loads((BASE / "v02_supported_family_roster.json").read_text(encoding="utf-8"))
SUPPORTED = {f["l3_code"] for f in roster["supported_families"]}
DEFERRED = {f["l3_code"] for f in roster["deferred_families"]}
OOS = {f["l3_code"] for f in roster["out_of_scope_families"]}

cands = [json.loads(l) for l in (BASE / "candidate_supply.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
dag_groups = collections.defaultdict(list)
for c in cands:
    dag_groups[c["normalized_dag_key"]].append(c)

recs = {}
for label, p in [("stable101_routing_v6", P1), ("stable106_catalog_miss_replay", P2)]:
    for i, line in enumerate(p.read_text(encoding="utf-8").splitlines()):
        if line.strip():
            recs[f"{label}:{i}"] = json.loads(line)

cen = json.loads((BASE / "v02_action_gate_reconciliation_v1.json").read_text(encoding="utf-8"))
recovered_dags = {d["normalized_dag_key"][:10]: d for d in cen["new_dags"]}

seed = []
for e in dev_entries:
    key = e["key"]
    if len(key) == 10 and key in recovered_dags:
        d = recovered_dags[key]
        has_task = key in tasked_keys
        seed.append({"key": key, "origin": "recovered", "topology": e["topology"],
                     "size": e["size"], "modality": e["modality"], "has_reviewed_task": has_task,
                     "discovery_refs": d["discovery_refs"], "covered_l3": d["covered_l3"],
                     "anchor": d["quota_anchor_l3"]})
    else:
        # existing pool: find the candidate group whose key starts with the 12-hex prefix
        match = None
        for k, cs in dag_groups.items():
            if k.startswith(key):
                match = (k, cs)
                break
        if not match:
            print("UNRESOLVED:", key)
            continue
        k, cs = match
        c = cs[0]
        if "discovery_ref" not in c:
            # expert-authored DAG: no source record; under the frozen spec it
            # cannot yield ANY benchmark task (dev included) via derivation --
            # flagged here, resolved by the owner's dev-policy decision
            seed.append({"key": k[:16], "origin": "expert_authored", "topology": e["topology"],
                         "size": e["size"], "modality": e["modality"], "has_reviewed_task": False,
                         "covered_l3": sorted(set(c["covered_l3"])),
                         "anchor": c["quota_anchor_l3"], "candidate_ids": [x["candidate_id"] for x in cs],
                         "spec_note": "expert-authored: no source record; spec-strict forbids task derivation; needs an owner policy decision for dev use"})
            continue
        seed.append({"key": k[:16], "origin": "existing", "topology": e["topology"],
                     "size": e["size"], "modality": e["modality"], "has_reviewed_task": False,
                     "discovery_ref": c["discovery_ref"], "covered_l3": sorted(set(c["covered_l3"])),
                     "anchor": c["quota_anchor_l3"], "candidate_ids": [x["candidate_id"] for x in cs]})

n_tasked = sum(1 for s in seed if s["has_reviewed_task"])
print(f"resolved: {len(seed)} | already tasked: {n_tasked} | need derivation: {len(seed)-n_tasked}")
for s in seed:
    tag = "HAS-TASK" if s["has_reviewed_task"] else "derive  "
    print(f"  {tag} {s['key'][:12]} [{s['origin']}] {s['topology']}/{s['size']}/{s['modality']} anchor={s['anchor']}")

out = BASE / "v02_dev_task_derivation_seed_v1.json"
out.write_text(json.dumps({
    "schema": "gis_recommend.qgis_benchmark_v02_dev_task_seed.v1",
    "seed_id": "v02-dev-task-seed-1",
    "date": "2026-09-11",
    "note": "dev selection frozen; DAGs never change during task derivation",
    "entries": seed,
}, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
print("written:", out.name)
