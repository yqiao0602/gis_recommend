"""Final accounting of the 24 recovered DAGs after adjudication, revision, and re-review.

Computes the surviving set's structural profile and the updated v0.2 supply
ceiling, then writes v02_recovered_dag_final_accounting_v1.json.
"""
import json
import collections
from pathlib import Path

WT = Path(__file__).resolve().parents[1]
BASE = WT / "benchmarks" / "qgis_planner_v1" / "authority"

cen = json.loads((BASE / "v02_action_gate_reconciliation_v1.json").read_text(encoding="utf-8"))
adj = json.loads((BASE / "v02_recovered_dag_adjudication_v1.json").read_text(encoding="utf-8"))
rev = json.loads((BASE / "v02_recovered_dag_revision_batch_v1.json").read_text(encoding="utf-8"))

# classify the 24 by final outcome
accepted_ids = set()
for o in adj["final_outcomes"]:
    pid = o["packet_entry_id"]
    if o["outcome"] in ("REJECTED",):
        pass
# rebuild from consensus + adjudication + revision:
ledger = [json.loads(l) for l in (BASE / "v02_recovered_dag_reviews_v1.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
cons = {r["packet_entry_id"]: r for r in ledger if r.get("record_type") == "consensus"}

reject = {
    "recovered-c4b53b68a27f2468",   # dual_reject cartogram
    "recovered-cb16fe08fbe1fb28",   # owner reject (BFS)
    "recovered-099e2c2db0f38ba6",   # owner reject (RF prefix)
}
readjudicated_accept = {"recovered-dec749a979996d6f"}  # #10
subchain = {r["packet_entry_id"] for r in rev["resolutions"] if r["resolution"].startswith("SUBCHAIN")}
corrected = {r["packet_entry_id"] for r in rev["resolutions"] if r["resolution"] == "CORRECTED_GRAPH_REVIEW_REQUIRED"}

final = {}
for pid, c in cons.items():
    if pid in reject:
        final[pid] = "rejected"
    elif pid in readjudicated_accept:
        final[pid] = "accept"
    elif c["outcome"] == "dual_accept":
        final[pid] = "accept"
    elif pid in subchain:
        final[pid] = "accept_subchain_scoped"
    elif pid in corrected:
        final[pid] = "accept_corrected_graph_dual_rereviewed"
    else:
        final[pid] = "ERROR_UNCLASSIFIED"

assert "ERROR_UNCLASSIFIED" not in final.values(), [k for k, v in final.items() if v == "ERROR_UNCLASSIFIED"]
tally = collections.Counter(final.values())
print("final outcome tally:", dict(tally))

# structural profile of survivors (with #9's corrected topology = hybrid)
by_key = {d["normalized_dag_key"][:10]: d for d in cen["new_dags"]}
def entry_key(pid):
    return pid.replace("recovered-", "")[:10]
survivors = []
for pid, outcome in final.items():
    if outcome == "rejected":
        continue
    d = by_key[entry_key(pid)]
    topo = d["topology_class"]
    if pid in corrected:
        topo = "hybrid"
    survivors.append({
        "packet_entry_id": pid,
        "outcome": outcome,
        "topology_class": topo,
        "graph_size_stratum": d["graph_size_stratum"],
        "covered_l3": d["covered_l3"],
        "quota_anchor_l3": d["quota_anchor_l3"],
    })

print("survivors:", len(survivors))
print("topology:", dict(collections.Counter(s["topology_class"] for s in survivors)))
print("size:", dict(collections.Counter(s["graph_size_stratum"] for s in survivors)))
mixed_families = {"L3_03_02_01", "L3_03_03_A", "L3_03_05_02", "L3_01_09_03", "L3_08_01_01"}
mods = []
for s in survivors:
    has_raster = any(f in mixed_families for f in s["covered_l3"])
    has_vector = len(s["covered_l3"]) > (1 if has_raster and len(s["covered_l3"]) == 1 else 0)
    mods.append("mixed" if has_raster and len(s["covered_l3"]) > 1 else ("raster-ish" if has_raster else "vector"))
print("approx modality:", dict(collections.Counter(mods)))

out = {
    "schema": "gis_recommend.qgis_benchmark_v02_recovered_dag_final_accounting.v1",
    "accounting_id": "v02-recovered-dag-final-accounting-1",
    "date": "2026-09-10",
    "inputs": [
        "v02_recovered_dag_reviews_v1.jsonl (dual review)",
        "v02_recovered_dag_adjudication_v1.json (owner adjudication)",
        "v02_recovered_dag_revision_batch_v1.json (revision resolutions)",
        "dual re-review of the corrected fc01749f30 graph: both reviewers accept, hybrid confirmed, rule C holds (review_dispatch/rereview_{a,b}_fc01749f30.txt)",
    ],
    "final_outcomes": {pid: outcome for pid, outcome in sorted(final.items())},
    "tally": dict(tally),
    "survivor_profile": {
        "count": len(survivors),
        "topology_class": dict(collections.Counter(s["topology_class"] for s in survivors)),
        "graph_size_stratum": dict(collections.Counter(s["graph_size_stratum"] for s in survivors)),
    },
    "v02_supply_ceiling": {
        "existing_c_eligible_dags": 37,
        "recovered_survivors_pending_task_fidelity": len(survivors),
        "new_ceiling": 37 + len(survivors),
        "budget_target": 96,
        "gap": 96 - (37 + len(survivors)),
        "honest_shortfalls": {
            "pure_branch": {"target": 8, "available": dict(collections.Counter(s["topology_class"] for s in survivors))["pure_branch"], "note": "shortfall recorded per roster rule R1 and the positioning decision; L4 expert fill is closed"},
            "one_step": {"target": 6, "available": 1, "note": "corpus has zero admissible single-operator records; shortfall recorded, frozen mapping untouched"},
        },
    },
    "next_stage": "task-text fidelity: source-derived task texts for the survivors (task_scope=subchain_scoped where designated), then v0.2 candidate pool assembly",
    "count_discipline_final": "this accounting is final for the recovered-24 cohort; survivors are NOT yet admitted -- task fidelity and human approval remain",
}
path = BASE / "v02_recovered_dag_final_accounting_v1.json"
path.write_text(json.dumps(out, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
print("written:", path.name)
