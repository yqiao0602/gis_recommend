"""List the final-reserve DAGs (the 32 pool DAGs not admitted to final or dev)
with full structural attributes, ranked by what they'd add to final's coverage."""
import json
import collections
from pathlib import Path

WT = Path(__file__).resolve().parents[1]
BASE = WT / "benchmarks" / "qgis_planner_v1" / "authority"

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

sel = json.loads((BASE / "v02_dev_final_selection_ledger_v1.json").read_text(encoding="utf-8"))
used = {e["key"][:10] for e in sel["dev_side"]["entries"]} | {d["key"][:10] for d in sel["final_side"]["pool_admitted"]}

# current final-side structure (after all rulings): retained v0.1 families
# are linear/merge + the 6 admitted pool DAGs; compute the CURRENT final
# modality/length profile for gap analysis
final_profile = {"topology": {"linear": None, "pure_merge": None, "pure_branch": 2, "hybrid": 3},
                 "size": {"one_step": 1, "seven_plus": 4, "four_to_six": 2, "two_to_three": None},
                 "modality": {}}
# admitted pool DAG details:
adm = sel["final_side"]["pool_admitted"]
print("current final-admitted (6):")
for d in adm:
    print(f"  {d['key'][:10]} {d['topology']}/{d['size']}/{d['modality']}")

reserve = []
for key, cs in dag_groups.items():
    k10 = key[:10]
    if k10 in used:
        continue
    if not any(x["quota_anchor_l3"] in SUPPORTED and set(x["covered_l3"]) <= (SUPPORTED | DEFERRED)
               and not (set(x["covered_l3"]) & OOS) for x in cs):
        continue
    c = cs[0]
    n = len(c["processes"])
    edges = [(int(l["source_process_id"][1:]), int(l["target_process_id"][1:])) for l in c["links"]]
    reserve.append({"key": k10, "topology": four_way(n, edges),
                    "size": "one_step" if n == 1 else "two_to_three" if n <= 3 else "four_to_six" if n <= 6 else "seven_plus",
                    "modality": modality_of(c["covered_l3"], c["modality"]),
                    "anchor": c["quota_anchor_l3"], "provenance": c["provenance_class"],
                    "covered": sorted(set(c["covered_l3"]))})
for pid10, d in recovered_dags.items():
    if pid10 in recovered_ids and pid10 not in used:
        reserve.append({"key": pid10, "topology": d["topology_class"],
                        "size": d["graph_size_stratum"],
                        "modality": modality_of(d["covered_l3"], "vector"),
                        "anchor": d["quota_anchor_l3"], "provenance": "recovered",
                        "covered": d["covered_l3"]})

# rank by marginal value for final: raster/mixed > seven_plus/four_to_six > merge > linear-short
def value(r):
    v = 0
    if r["modality"] == "raster": v += 4
    elif r["modality"] == "mixed": v += 3
    if r["size"] == "seven_plus": v += 3
    elif r["size"] == "four_to_six": v += 2
    if r["topology"] in ("pure_merge", "hybrid"): v += 1
    if r["size"] == "two_to_three" and r["topology"] == "linear" and r["modality"] == "vector":
        v -= 2  # the over-concentrated class -- least marginal value
    return v

reserve.sort(key=lambda r: (-value(r), r["key"]))
print(f"\nfinal-reserve: {len(reserve)} DAGs")
print("profile:", dict(collections.Counter(r["topology"] for r in reserve)),
      dict(collections.Counter(r["modality"] for r in reserve)),
      dict(collections.Counter(r["size"] for r in reserve)))
print("\ntop-12 candidates by marginal coverage value:")
for r in reserve[:12]:
    print(f"  {r['key']} [{r['provenance']}] {r['topology']}/{r['size']}/{r['modality']} anchor={r['anchor']} value={value(r)}")
