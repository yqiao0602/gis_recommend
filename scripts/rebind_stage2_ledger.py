"""Stage-2: build the v0.1 -> v0.2 retention/replacement ledger (pure structural, disclosure option B).

Data available without touching sealed artifacts:
  - 120 final task texts (unsealed) + their DAG families (40 x 3, verified by id pattern)
  - the 52-DAG queue (unsealed): full structures of the pool final drew from
  - the 58-DAG repair pool with four-way topology
  - Stage-1: 120/120 text-clean

What is NOT available (sealed): which queue DAG each family maps to. So the
ledger works at family level with structural inference:
  - infer each family's workflow signature from its 3 task texts (operator
    semantics mentioned) and match against queue DAGs' covered_l3/operator
    signatures; where the match is ambiguous, mark inference_confidence.
  - replacement slots are chosen by the owner's priorities: (1) all 3
    pure_branch + 4 hybrid + 1 one-step pool DAGs enter; (2) selected 7+
    long chains; (3) linear/merge retained maximally.

Output: v02_retention_replacement_ledger_v1.json (+ summary md).
"""
import json
import re
import collections
from pathlib import Path

WT = Path(__file__).resolve().parents[1]
BASE = WT / "benchmarks" / "qgis_planner_v1" / "authority"
TASKS = BASE.parent / "releases/v0.1-final-core-120/tasks.jsonl"

tasks = [json.loads(l) for l in TASKS.read_text(encoding="utf-8").splitlines() if l.strip()]
fam_texts = collections.defaultdict(list)
for t in tasks:
    fam = re.sub(r"-v\d+$", "", t["sample_id"])
    fam_texts[fam].append(t["task_text"])

# semantic keywords -> L3 family mapping (for inference, coarse)
SIG = {
    "reproject": ["L3_01_10_01", "L3_03_05_02"],
    "buffer": ["L3_02_01_01"],
    "clip": ["L3_02_02_06", "L3_03_01_02"],
    "merge": ["L3_01_03_04"],
    "dissolve": ["L3_02_03_05"],
    "intersect": ["L3_02_02_01"],
    "union": ["L3_02_02_02"],
    "erase": ["L3_02_02_04"],
    "zonal": ["L3_03_02_01"],
    "slope": ["L3_04_01_01"],
    "field": ["L3_01_02_06"],
    "centroid": ["L3_02_05_11"],
    "vertex": ["L3_02_05_11"],
    "rasteriz": ["L3_01_09_03"],
    "extract": ["L3_02_06_02", "L3_02_06_03"],
    "single part": ["L3_02_07_01"],
    "boundary": ["L3_02_02_06"],
    "sample": ["L3_08_01_01", "L3_02_06_06"],
}

def family_signature(texts):
    blob = " ".join(texts).lower()
    return sorted({l3 for kw, l3s in SIG.items() for l3 in l3s if kw in blob})

# queue structures (unsealed)
queue = [json.loads(l) for l in (BASE / "v01_dag_review_queue.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
def four_way(n, edges):
    indeg = [0]*n; outdeg = [0]*n
    for s, t in edges:
        outdeg[s] += 1; indeg[t] += 1
    hi = any(d > 1 for d in indeg); ho = any(d > 1 for d in outdeg)
    return "hybrid" if hi and ho else "pure_merge" if hi else "pure_branch" if ho else "linear"

queue_by_id = {}
for q in queue:
    edges = [(l["source_process_id"], l["target_process_id"]) for l in q["links"]]
    n = len(q["processes"])
    topo = four_way(n, [(int(a[1:]), int(b[1:])) for a, b in edges])
    size = "one_step" if n == 1 else "two_to_three" if n <= 3 else "four_to_six" if n <= 6 else "seven_plus"
    queue_by_id[q["canonical_graph_id"]] = {"topology": topo, "size": size,
                                             "covered": set(q["covered_l3"]), "modality": q["modality"]}

# family-level ledger: signature-match families against queue DAGs
queue_structs = list(queue_by_id.values())
ledger = []
for fam in sorted(fam_texts):
    sig = set(family_signature(fam_texts[fam]))
    # candidate queue DAGs whose covered families overlap the signature
    matches = [(qid, len(sig & d["covered"]) / max(1, len(sig | d["covered"])))
               for qid, d in queue_by_id.items() if sig & d["covered"]]
    matches.sort(key=lambda x: -x[1])
    best = matches[0] if matches else None
    plausible = [m for m in matches if m[1] >= 0.5]
    ledger.append({
        "family": fam,
        "inferred_signature": sorted(sig),
        "best_queue_match": best[0][:16] if best else None,
        "match_jaccard": round(best[1], 2) if best else 0,
        "ambiguity": "high" if len(plausible) > 3 or not best else ("medium" if len(plausible) > 1 else "low"),
        "n_texts": len(fam_texts[fam]),
    })

amb = collections.Counter(l["ambiguity"] for l in ledger)
print("family inference ambiguity:", dict(amb))
print("families with signature:", sum(1 for l in ledger if l["inferred_signature"]))
for l in ledger[:8]:
    print(" ", l["family"], "| jac:", l["match_jaccard"], "| amb:", l["ambiguity"], "|", l["inferred_signature"][:6])

out = BASE / "v02_retention_replacement_ledger_v1.json"
out.write_text(json.dumps({
    "schema": "gis_recommend.qgis_benchmark_v02_retention_ledger.v1",
    "ledger_id": "v02-retention-ledger-1",
    "date": "2026-09-11",
    "stage": "family_signatures_inferred (structural inference layer; sealed binding untouched)",
    "families": ledger,
}, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
print("written:", out.name)
