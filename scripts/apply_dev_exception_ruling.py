"""Apply the owner's controlled dev exception: swap out 2 expert DAGs, keep 1 as DEV_EXCEPTION.

- cfef1a7cffe8 (expert pure_merge) -> replaced by a source-backed pure_merge from final-reserve
- 93ed22f6ceeb (expert linear/raster) -> replaced by a source-backed linear/raster from final-reserve
- d2165c006df4 (expert one_step) -> KEPT as the single, pinned Dev-only exception
  (final_eligible=false, benchmark_final_eligible=false, training_eligible=false;
  task derivation allowed for dev only, on a separate DEV_EXCEPTION track)

Updates v02_dev_final_selection_ledger_v1.json in place (ledger v1.1)
and rewrites the dev seed.
"""
import json
import collections
from pathlib import Path

WT = Path(__file__).resolve().parents[1]
BASE = WT / "benchmarks" / "qgis_planner_v1" / "authority"

led = json.loads((BASE / "v02_dev_final_selection_ledger_v1.json").read_text(encoding="utf-8"))
dev_entries = led["dev_side"]["entries"]
reserve = led["final_side"]["pool_admitted"]  # placeholder; reserve list rebuilt below

# rebuild reserve from pool minus dev minus admitted
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
def modality_of(covered, base):
    if base in ("raster", "mixed"):
        return base
    return "mixed" if (set(covered) & MIXED_HINT and len(covered) > 1) else "vector"

cands = [json.loads(l) for l in (BASE / "candidate_supply.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
dag_groups = collections.defaultdict(list)
for c in cands:
    dag_groups[c["normalized_dag_key"]].append(c)

cen = json.loads((BASE / "v02_action_gate_reconciliation_v1.json").read_text(encoding="utf-8"))
recovered_dags = {d["normalized_dag_key"][:10]: d for d in cen["new_dags"]}
acct = json.loads((BASE / "v02_recovered_dag_final_accounting_v1.json").read_text(encoding="utf-8"))
recovered_ids = {pid.replace("recovered-", "")[:10] for pid, o in acct["final_outcomes"].items() if o != "rejected"}

dev_keys = {e["key"][:10] for e in dev_entries}
final_admitted_keys = {e["key"][:10] for e in led["final_side"]["pool_admitted"]}

pool_free = []
for key, cs in dag_groups.items():
    k10 = key[:10]
    if k10 in dev_keys or k10 in final_admitted_keys:
        continue
    if not any(x["quota_anchor_l3"] in SUPPORTED and set(x["covered_l3"]) <= (SUPPORTED | DEFERRED)
               and not (set(x["covered_l3"]) & OOS) for x in cs):
        continue
    c = cs[0]
    n = len(c["processes"])
    edges = [(int(l["source_process_id"][1:]), int(l["target_process_id"][1:])) for l in c["links"]]
    if c["provenance_class"] == "expert_authored":
        continue  # replacements must be source-backed
    pool_free.append({"key": key[:12], "topology": four_way(n, edges),
                      "size": "one_step" if n == 1 else "two_to_three" if n <= 3 else "four_to_six" if n <= 6 else "seven_plus",
                      "modality": modality_of(c["covered_l3"], c["modality"]),
                      "covered": sorted(set(c["covered_l3"])), "anchor": c["quota_anchor_l3"]})
for pid10, d in recovered_dags.items():
    if pid10 in recovered_ids and pid10 not in dev_keys and pid10 not in final_admitted_keys:
        pool_free.append({"key": pid10[:12], "topology": d["topology_class"],
                          "size": d["graph_size_stratum"],
                          "modality": modality_of(d["covered_l3"], "vector"),
                          "covered": d["covered_l3"], "anchor": d["quota_anchor_l3"]})
print("source-backed free pool for replacement:", len(pool_free))
print("  topology:", dict(collections.Counter(p["topology"] for p in pool_free)),
      "| modality:", dict(collections.Counter(p["modality"] for p in pool_free)))

# swap 1: replace expert pure_merge (cfef1a7cffe8) with a source-backed pure_merge (prefer mixed)
cands_pm = sorted([p for p in pool_free if p["topology"] == "pure_merge"], key=lambda p: (p["modality"] == "vector", p["key"]))
repl1 = cands_pm[0]
# swap 2: replace expert linear/raster (93ed22f6ceeb) with source-backed linear/raster
cands_lr = sorted([p for p in pool_free if p["topology"] == "linear" and p["modality"] == "raster"], key=lambda p: p["key"])
repl2 = cands_lr[0] if cands_lr else sorted([p for p in pool_free if p["topology"] == "linear" and p["modality"] == "mixed"], key=lambda p: p["key"])[0]
print("replacement 1:", repl1["key"], repl1["topology"], repl1["size"], repl1["modality"])
print("replacement 2:", repl2["key"], repl2["topology"], repl2["size"], repl2["modality"])

# apply swaps in dev entries
new_entries = []
for e in dev_entries:
    if e["key"].startswith("cfef1a7cffe8"):
        new_entries.append({**repl1, "origin": "existing", "reason": "replaced expert-authored pure_merge per owner controlled-exception ruling (source-backed substitute)"})
    elif e["key"].startswith("93ed22f6ceeb"):
        new_entries.append({**repl2, "origin": "existing", "reason": "replaced expert-authored linear/raster per owner controlled-exception ruling (source-backed substitute)"})
    elif e["key"].startswith("d2165c006df4"):
        new_entries.append({**e, "origin": "expert_authored", "dev_track": "DEV_EXCEPTION",
                            "expert_dag_dev_exception": True,
                            "exception_reason": "unique_one_step_coverage",
                            "final_eligible": False, "benchmark_final_eligible": False, "training_eligible": False,
                            "reason": "DEV-ONLY pinned exception: the pool's single one_step DAG; dev length-layer completeness; may derive dev tasks only; never enters v0.2 final, main evaluation, training, or formal benchmark gold"})
    else:
        new_entries.append(e)
led["dev_side"]["entries"] = new_entries
led["dev_side"]["dag_count"] = len(new_entries)
led["dev_side"]["topology"] = dict(collections.Counter(e["topology"] for e in new_entries))
led["dev_side"]["size"] = dict(collections.Counter(e["size"] for e in new_entries))
led["dev_side"]["modality"] = dict(collections.Counter(e["modality"] for e in new_entries))
led["dev_exception_ruling"] = {
    "date": "2026-09-11",
    "decided_by": "qiaoyun (benchmark owner)",
    "rule": "Dev-only expert DAG exception: allowed ONLY to preserve the pool's unique one-step structure coverage; exactly ONE expert-authored DAG may stay in dev and derive dev tasks; that task never enters v0.2 final, the main evaluation set, the training set, or any formal benchmark gold. Final remains 100% source-backed with zero exceptions. The exception is pinned to d2165c006df4 and cannot spill.",
    "swapped_out": ["cfef1a7cffe8 (expert pure_merge -> source-backed replacement)", "93ed22f6ceeb (expert linear/raster -> source-backed replacement)"],
    "kept": "d2165c006df4 (expert one_step, DEV_EXCEPTION track, final_eligible=false)",
}
p = BASE / "v02_dev_final_selection_ledger_v1.json"
p.write_text(json.dumps(led, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
print()
print("DEV after ruling:", led["dev_side"]["dag_count"], "DAGs")
print("  topology:", led["dev_side"]["topology"])
print("  size:", led["dev_side"]["size"])
print("  modality:", led["dev_side"]["modality"])
print("ledger updated")
