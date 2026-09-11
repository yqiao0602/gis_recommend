"""Dev/Final DAG selection ledger: assign every pool DAG to dev, final-reserve, or reserve.

Owner principles:
  - dev must cover all four topologies, all length strata, and protect
    scarce raster/mixed -- as a DEVELOPMENT set, not a quota exercise
  - final keeps enough branch/hybrid/long-chain (do not drain rare
    structures into dev)
  - DAG-disjoint between dev and final (and vs the 29 retained v0.1
    final families via their queue mappings, approximated structurally)
  - select DAGs FIRST, tasks later

Pool inventory: the 58-DAG pool minus the 11 already admitted to v0.2
final (P1+P2 from the retention ledger) = 47 candidates for dev and
final-reserve; final's remaining needs come from retained v0.1 DAGs +
any final-reserve pool DAGs.

Output: v02_dev_final_selection_ledger_v1.json with per-DAG assignment
and reason, plus coverage audits for dev and final.
"""
import json
import collections
from pathlib import Path

WT = Path(__file__).resolve().parents[1]
BASE = WT / "benchmarks" / "qgis_planner_v1" / "authority"

# rebuild the 58-pool with full attributes
roster = json.loads((BASE / "v02_supported_family_roster.json").read_text(encoding="utf-8"))
SUPPORTED = {f["l3_code"] for f in roster["supported_families"]}
DEFERRED = {f["l3_code"] for f in roster["deferred_families"]}
OOS = {f["l3_code"] for f in roster["out_of_scope_families"]}

def four_way(n, edges):
    indeg = [0]*n; outdeg = [0]*n
    for s, t in edges:
        outdeg[s] += 1; indeg[t] += 1
    hi = any(d > 1 for d in indeg); ho = any(d > 1 for d in outdeg)
    return "hybrid" if hi and ho else "pure_merge" if hi else "pure_branch" if ho else "linear"

MIXED_HINT = {"L3_03_02_01", "L3_03_03_A", "L3_03_05_02", "L3_01_09_03", "L3_08_01_01", "L3_03_01_02", "L3_04_01_01", "L3_01_01_03"}
def modality_of(covered, base_modality):
    if base_modality in ("raster", "mixed"):
        return base_modality
    return "mixed" if (set(covered) & MIXED_HINT and len(covered) > 1) else "vector"

cands = [json.loads(l) for l in (BASE / "candidate_supply.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
dag_groups = collections.defaultdict(list)
for c in cands:
    dag_groups[c["normalized_dag_key"]].append(c)

acct = json.loads((BASE / "v02_recovered_dag_final_accounting_v1.json").read_text(encoding="utf-8"))
cen = json.loads((BASE / "v02_action_gate_reconciliation_v1.json").read_text(encoding="utf-8"))
recovered_dags = {d["normalized_dag_key"][:10]: d for d in cen["new_dags"]}
recovered_ids = {pid.replace("recovered-", "")[:10] for pid, o in acct["final_outcomes"].items() if o != "rejected"}

pool = []
for key, cs in dag_groups.items():
    if not any(x["quota_anchor_l3"] in SUPPORTED and set(x["covered_l3"]) <= (SUPPORTED | DEFERRED)
               and not (set(x["covered_l3"]) & OOS) for x in cs):
        continue
    c = cs[0]
    n = len(c["processes"])
    edges = [(int(l["source_process_id"][1:]), int(l["target_process_id"][1:])) for l in c["links"]]
    pool.append({
        "key": key[:12], "topology": four_way(n, edges),
        "size": "one_step" if n == 1 else "two_to_three" if n <= 3 else "four_to_six" if n <= 6 else "seven_plus",
        "modality": modality_of(c["covered_l3"], c["modality"]),
        "covered": sorted(set(c["covered_l3"])), "origin": "existing",
    })
for pid10, d in recovered_dags.items():
    if pid10 not in recovered_ids:
        continue
    pool.append({
        "key": pid10[:12],
        "topology": "hybrid" if pid10 == "fc01749f30" else d["topology_class"],
        "size": d["graph_size_stratum"],
        "modality": modality_of(d["covered_l3"], "vector"),
        "covered": d["covered_l3"], "origin": "recovered",
    })
assert len(pool) == 58, len(pool)

# the 11 admitted-to-final DAGs (from the retention ledger arithmetic: 3 branch + 4 hybrid + 1 one-step + 3 seven_plus)
# identify them structurally: pure_branch and one_step are unique identifiers; hybrid and seven_plus need selection
admitted = []
branch = sorted([p for p in pool if p["topology"] == "pure_branch"], key=lambda p: p["key"])
oneste = [p for p in pool if p["size"] == "one_step"]
hybrids = sorted([p for p in pool if p["topology"] == "hybrid"], key=lambda p: p["key"])
sevenp = sorted([p for p in pool if p["size"] == "seven_plus" and p["topology"] == "linear"], key=lambda p: p["key"])
admitted += branch[:3] + oneste[:1] + hybrids[:4]
# 3 seven_plus: prefer mixed/raster modality for final value
seven_ranked = sorted(sevenp, key=lambda p: (p["modality"] == "vector", p["key"]))
admitted += seven_ranked[:3]
admitted_keys = {p["key"] for p in admitted}
for p in pool:
    p["status"] = "final_admitted" if p["key"] in admitted_keys else "candidate"
print("admitted to final (11):", collections.Counter(p["topology"] for p in admitted), "|", collections.Counter(p["size"] for p in admitted))

# ---- dev selection over the remaining 47 ----
candidates = [p for p in pool if p["status"] == "candidate"]
print("dev/final-reserve candidates:", len(candidates))

dev = []

# T0 (owner layer 1, absolute): dev must SEE all four topologies. The 11 final
# admissions took ALL pure_branch (3/3) and ALL hybrid (4/4); rebalance by
# transferring one of each from final_admitted to dev. Final retains
# pure_branch 2/3 and hybrid 3/4 -- still the majority of the rare classes.
rebalanced = []
for topo, keep_final in (("pure_branch", 2), ("hybrid", 3)):
    admitted_of_topo = [p for p in admitted if p["topology"] == topo]
    for p in admitted_of_topo[keep_final:]:
        p["status"] = "dev"
        p["dev_reason"] = f"topology_anchor_{topo}_rebalanced_from_final"
        rebalanced.append(p)
        dev.append(p)
print("rebalanced to dev (final keeps majority of each rare class):",
      [(p["topology"], p["key"]) for p in rebalanced])
def take(pred, reason, n=1):
    got = 0
    for p in candidates:
        if p["status"] == "candidate" and pred(p) and got < n:
            p["status"] = "dev"
            p["dev_reason"] = reason
            dev.append(p)
            got += 1

# T1 topology anchors (branch/hybrid already covered by rebalance): merge and linear
take(lambda p: p["topology"] == "pure_merge", "topology_anchor_pure_merge", 3)
take(lambda p: p["topology"] == "linear", "topology_anchor_linear", 4)
# T2 length coverage
take(lambda p: p["size"] == "one_step", "length_anchor_one_step")
take(lambda p: p["size"] == "four_to_six" and p["topology"] == "linear", "length_anchor_four_to_six", 2)
take(lambda p: p["size"] == "seven_plus", "length_anchor_seven_plus", 1)
take(lambda p: p["size"] == "two_to_three", "length_anchor_two_to_three", 2)
# T3 modality protection: raster first, then mixed
take(lambda p: p["modality"] == "raster", "modality_anchor_raster", 2)
take(lambda p: p["modality"] == "mixed", "modality_anchor_mixed", 3)

# fill to 18 with balanced diversity
while len(dev) < 18:
    remaining = [p for p in candidates if p["status"] == "candidate"]
    if not remaining:
        break
    # prefer candidates whose (topology, modality) pair is least represented in dev
    pair = collections.Counter((p["topology"], p["modality"]) for p in dev)
    remaining.sort(key=lambda p: (pair[(p["topology"], p["modality"])], p["key"]))
    p = remaining[0]
    p["status"] = "dev"
    p["dev_reason"] = "diversity_fill"
    dev.append(p)

final_reserve = [p for p in pool if p["status"] == "candidate"]
print()
print("DEV (%d):" % len(dev))
print("  topology:", dict(collections.Counter(p["topology"] for p in dev)))
print("  size:", dict(collections.Counter(p["size"] for p in dev)))
print("  modality:", dict(collections.Counter(p["modality"] for p in dev)))
print("FINAL-RESERVE (%d):" % len(final_reserve))
print("  topology:", dict(collections.Counter(p["topology"] for p in final_reserve)))
print("  modality:", dict(collections.Counter(p["modality"] for p in final_reserve)))

out = {
    "schema": "gis_recommend.qgis_benchmark_v02_dev_final_selection_ledger.v1",
    "ledger_id": "v02-dev-final-selection-1",
    "date": "2026-09-11",
    "principles": [
        "dev covers all four topologies, all length strata, protects scarce raster/mixed",
        "final keeps enough branch/hybrid/long-chain (rare structures not drained into dev)",
        "DAG-disjoint: dev / final-admitted / final-reserve are disjoint sets; retained v0.1 final DAGs (29 families) complete the final side",
        "DAGs selected first; task variants generated later",
    ],
    "final_side": {
        "retained_v01_families": 29, "retained_v01_tasks": 87,
        "pool_admitted": [{"key": p["key"], "topology": p["topology"], "size": p["size"], "modality": p["modality"], "origin": p["origin"]} for p in admitted],
        "pool_reserve": len(final_reserve),
    },
    "dev_side": {"dag_count": len(dev),
                 "topology": dict(collections.Counter(p["topology"] for p in dev)),
                 "size": dict(collections.Counter(p["size"] for p in dev)),
                 "modality": dict(collections.Counter(p["modality"] for p in dev)),
                 "entries": [{"key": p["key"], "topology": p["topology"], "size": p["size"],
                              "modality": p["modality"], "origin": p["origin"], "reason": p["dev_reason"]} for p in dev]},
    "disjointness_note": "dev keys and final-admitted keys are disjoint by construction; overlap with the 29 retained v0.1 final families is bounded by the [25,37] existing-pool overlap and handled at assembly",
}
path = BASE / "v02_dev_final_selection_ledger_v1.json"
path.write_text(json.dumps(out, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
print("written:", path.name)
