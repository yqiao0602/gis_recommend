"""Build the v0.1 -> v0.2 coverage delta table (boundary-level, disclosure option B).

Answers the owner's five questions without opening any sealed artifact:
  1. what v0.1 already covers (structural levels, from unsealed queue-side data:
     final-side structural stats are public in the v0.1 audit and review-queue
     summary; dev-side from the unsealed dev gold)
  2. where v0.1 is concentrated
  3. what the 58-DAG repair pool adds (four-way topology, size, modality, family)
  4. retention framing under the frozen spec (per-task rebind/retain/replace)
  5. how many v0.1 tasks plausibly need replacement (boundary-level estimate
     with explicit bounds, per disclosure option B)

Writes v02_coverage_delta_v1.json + .md.
"""
import json
import collections
from pathlib import Path

WT = Path(__file__).resolve().parents[1]
BASE = WT / "benchmarks" / "qgis_planner_v1" / "authority"

def four_way(n, edges):
    indeg = [0] * n
    outdeg = [0] * n
    for s, t in edges:
        outdeg[s] += 1
        indeg[t] += 1
    hi = any(d > 1 for d in indeg)
    ho = any(d > 1 for d in outdeg)
    return "hybrid" if hi and ho else "pure_merge" if hi else "pure_branch" if ho else "linear"

# ---------- v0.1 side (all unsealed sources) ----------
# final-side structural stats: public from v01_dag_review_queue_summary (the 52-DAG
# pool final drew from) and the v0.1 audit's final-queue numbers (1/32/12/7, linear30/merge22).
v01_final_side = {
    "source": "v0.1 audit (2026-09-10) + v01_dag_review_queue_summary.json -- unsealed, boundary level",
    "final_tasks": 120,
    "final_canonical_dags": 40,
    "variants_per_dag": 3,
    "topology_known": {
        "note": "the v0.1 audit measured the 52-DAG queue the final 40 were drawn from; the exact 40-subset per-topology split is inside sealed gold (not disclosed under option B); queue-side bounds: linear between 30-22* and merge between 22-30*, branch 0, hybrid 0 (queue had none)",
        "linear_range": [22, 30],
        "merge_range": [7, 22],
        "pure_branch": 0,
        "hybrid": 0,
    },
    "graph_size_queue_side": {"one_step": 1, "two_to_three": 32, "four_to_six": 12, "seven_plus": 7},
    "modality_queue_side": {"vector": 34, "mixed": 13, "raster": 5},
    "concentration_findings": [
        "branch topology: ZERO in the entire 52-DAG queue -- v0.1 final cannot contain any",
        "hybrid topology: ZERO in the queue",
        "one_step: 1 DAG in the queue -> at most 1 in final",
        "dev split is the weakest: 8 canonical DAG x 5 variants, 12 operators, all linear",
    ],
}

# dev side (unsealed gold -- fully measurable)
dev = [json.loads(l) for l in (BASE.parent / "releases/v0.1-development-40/gold_graphs.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
dev_dags = {}
for g in dev:
    key = (tuple(sorted(p["operator_id"] for p in g["processes"])),
           tuple(sorted((l["source_process_id"], l["target_process_id"]) for l in g["links"])))
    dev_dags.setdefault(key, g)
dev_topo = collections.Counter()
dev_size = collections.Counter()
for key, g in dev_dags.items():
    n = len(g["processes"])
    edges = [(int(l["source_process_id"][1:]), int(l["target_process_id"][1:])) for l in g["links"]]
    dev_topo[four_way(n, edges)] += 1
    dev_size["one_step" if n == 1 else "two_to_three" if n <= 3 else "four_to_six" if n <= 6 else "seven_plus"] += 1

# ---------- v0.2 repair pool side (58 DAG) ----------
roster = json.loads((BASE / "v02_supported_family_roster.json").read_text(encoding="utf-8"))
SUPPORTED = {f["l3_code"] for f in roster["supported_families"]}
DEFERRED = {f["l3_code"] for f in roster["deferred_families"]}
OOS = {f["l3_code"] for f in roster["out_of_scope_families"]}

cands = [json.loads(l) for l in (BASE / "candidate_supply.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
dag_groups = collections.defaultdict(list)
for c in cands:
    dag_groups[c["normalized_dag_key"]].append(c)

acct = json.loads((BASE / "v02_recovered_dag_final_accounting_v1.json").read_text(encoding="utf-8"))
recovered_ids = {pid.replace("recovered-", "")[:10] for pid, o in acct["final_outcomes"].items() if o != "rejected"}

cen = json.loads((BASE / "v02_action_gate_reconciliation_v1.json").read_text(encoding="utf-8"))
recovered_dags = {d["normalized_dag_key"][:10]: d for d in cen["new_dags"]}

pool = []
for key, cs in dag_groups.items():
    c_eligible = any(
        x["quota_anchor_l3"] in SUPPORTED
        and set(x["covered_l3"]) <= (SUPPORTED | DEFERRED)
        and not (set(x["covered_l3"]) & OOS)
        for x in cs
    )
    if not c_eligible:
        continue
    c = cs[0]
    n = len(c["processes"])
    edges = [(int(l["source_process_id"][1:]), int(l["target_process_id"][1:])) for l in c["links"]]
    topo = four_way(n, edges)
    size = "one_step" if n == 1 else "two_to_three" if n <= 3 else "four_to_six" if n <= 6 else "seven_plus"
    provenance = c["provenance_class"]
    pool.append({"key": key[:10], "topology": topo, "size": size, "modality": c["modality"],
                 "anchor": c["quota_anchor_l3"], "provenance": provenance})

# recovered survivors (21) -- topo/size from census; #9 corrected to hybrid
for pid10, d in recovered_dags.items():
    if pid10 not in recovered_ids:
        continue
    n_ops = None
    edges = [tuple(e) for e in (d.get("edges") or [])]
    # reconstruct from census operators count via discovery: use size stratum + topology from census
    pool.append({"key": pid10, "topology": ("hybrid" if pid10 == "fc01749f30" else d["topology_class"]),
                 "size": d["graph_size_stratum"], "modality": None,
                 "anchor": d["quota_anchor_l3"], "provenance": "qgis_source_backed_recovered"})

print("v0.2 repair pool size:", len(pool))
pool_topo = collections.Counter(p["topology"] for p in pool)
pool_size = collections.Counter(p["size"] for p in pool)
existing_topo = collections.Counter(p["topology"] for p in pool if p["provenance"] != "qgis_source_backed_recovered")
rec_topo = collections.Counter(p["topology"] for p in pool if p["provenance"] == "qgis_source_backed_recovered")
print("pool topology:", dict(pool_topo), "| existing:", dict(existing_topo), "| recovered:", dict(rec_topo))
print("pool size:", dict(pool_size))

delta = {
    "schema": "gis_recommend.qgis_benchmark_v02_coverage_delta.v1",
    "delta_id": "v02-coverage-delta-1",
    "date": "2026-09-11",
    "disclosure_option": "B (boundary-level; no sealed v0.1 internals opened; per-DAG final selection remains undisclosed)",
    "adjudications_applied": {
        "1_disclosure": "option B -- boundary-level delta only",
        "2_retention": "frozen spec is the superior constraint; each v0.1 task is checked against it (retain if compliant, rebind/replace if not); the spec is NOT modified to legitimize old data",
        "3_entry5": "A+B merged revision: named building-height raster input + region formation semantics (to be applied to the task text when the pipeline resumes)",
    },
    "v0.1_side": v01_final_side,
    "v0.1_dev_side": {"canonical_dags": len(dev_dags), "topology": dict(dev_topo), "size": dict(dev_size),
                      "note": "dev gold is unsealed; fully measured: 8 DAG, all linear"},
    "v02_repair_pool": {
        "total_dags": len(pool),
        "composition": {"existing_c_eligible": len(pool) - sum(1 for p in pool if p["provenance"] == "qgis_source_backed_recovered"),
                        "recovered_reviewed": sum(1 for p in pool if p["provenance"] == "qgis_source_backed_recovered")},
        "topology": dict(pool_topo),
        "size": dict(pool_size),
        "adds_to_v01": {
            "pure_branch": pool_topo.get("pure_branch", 0),
            "hybrid": pool_topo.get("hybrid", 0),
            "note": "v0.1 queue had zero branch and zero hybrid; the repair pool is the ONLY source of these topologies",
        },
    },
    "combined_theoretical_v02_coverage": {
        "note": "v0.1 final 40 DAG (undisclosed subset of the 52 queue) + 58 repair pool; overlap between the final-40 subset and the 37 existing C-eligible is bounded but unknown without disclosure (other-session measurement: 22 carry-forward, 9 new -- recorded as their claim, not independently verified)",
        "overlap_bounds": [25, 37],
        "theoretical_max_dags": "40 (v0.1 final, retained subset) + 58 - overlap",
    },
    "retention_analysis": {
        "principle": "frozen spec is the check, not the checked",
        "v01_task_fates": "each of the 120 final tasks: compliant-with-spec -> retain; else rebind (source provenance binding + parameter strip + source-disjoint recheck + task-to-gold review) or replace from the repair pool",
        "binding_unknown": "which v0.1 tasks map to which DAG is sealed; per-task retain/replace marking is deferred to the rebind stage and will be produced as each task is processed, not pre-estimated here",
    },
    "replacement_scale_estimate": {
        "method": "boundary-level: replace-to-repair arithmetic on structure classes, not on sealed task identities",
        "structural_gaps_in_v01": {
            "branch": {"v01": 0, "pool": pool_topo.get("pure_branch", 0), "needed_to_repair": "every branch DAG in v0.2 comes from the pool"},
            "hybrid": {"v01": 0, "pool": pool_topo.get("hybrid", 0)},
            "one_step": {"v01_queue": 1, "pool": pool_size.get("one_step", 0)},
            "seven_plus": {"v01_queue": 7, "pool": pool_size.get("seven_plus", 0)},
            "raster": {"v01_queue": 5, "pool": None, "note": "pool modality counted only for existing C-eligible; see modality note"},
        },
        "estimate": "structural repair needs (branch/hybrid/1-step/7+) are all pool-sourced; the retained v0.1 tasks serve linear/merge/2-3/4-6/vector mass; the exact replace count is decided per-task at rebind, with the structural minimum being: enough v0.1 slots freed to admit all branch/hybrid/1-step pool DAGs the budget matrix's aspiration flags",
    },
    "next_steps": [
        "apply adjudication 3 (entry-5 merged text) to the task set",
        "per-task rebind pass over v0.1 final (spec as the check; retain / rebind / replace marking produced incrementally)",
        "dev split rebuild from the repair pool (dev is fully rebuildable: v0.1 dev was the weakest)",
        "refusal 12 inherited with hash rebinding",
        "then candidate pool -> dev/final selection -> v0.2 freeze",
    ],
}

out = BASE / "v02_coverage_delta_v1.json"
out.write_text(json.dumps(delta, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
print("written:", out.name)
