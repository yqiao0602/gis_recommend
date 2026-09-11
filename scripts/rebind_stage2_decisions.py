"""Stage-2 decision layer: which v0.1 DAG-family slots to release.

Pure structural, disclosure option B. The release criteria per owner:
  release ONLY what coverage needs, i.e. slots for
    P1: all 3 pure_branch + 4 hybrid + 1 one-step pool DAGs (v0.1-blind structures)
    P2: a few 7+ long chains from the pool
  retain linear/merge maximally (they are NOT a defect).

Slot-release candidates among the 40 families are ranked by structural
over-concentration signals readable from unsealed texts:
  S1 multi-variant families whose texts describe a SHORT linear 2-op
     workflow (the known v0.1 concentration: queue-side 32/52 were
     two_to_three)
  S2 families whose signature suggests 2-3 step chains AND whose
     workflow appears frequently across the pool (duplicate-ish mass)
  S3 anything else -- retained.

IMPORTANT: the ledger never claims the released family was WRONG; the
reason recorded is coverage-driven substitution, per owner's principle
(REPLACE != incorrect).
"""
import json
import re
import collections
from pathlib import Path

WT = Path(__file__).resolve().parents[1]
BASE = WT / "benchmarks" / "qgis_planner_v1" / "authority"

led = json.loads((BASE / "v02_retention_replacement_ledger_v1.json").read_text(encoding="utf-8"))
families = led["families"]

TASKS = BASE.parent / "releases/v0.1-final-core-120/tasks.jsonl"
tasks = [json.loads(l) for l in TASKS.read_text(encoding="utf-8").splitlines() if l.strip()]
fam_texts = collections.defaultdict(list)
for t in tasks:
    fam_texts[re.sub(r"-v\d+$", "", t["sample_id"])].append(t["task_text"])

# how many ops does each family's text imply (crude: count distinct workflow verbs)
VERBS = ["reproject", "buffer", "clip", "merge", "dissolve", "intersect", "union", "erase",
         "zonal", "slope", "calculate", "centroid", "vertex", "rasterize", "extract",
         "split", "sample", "combine", "filter", "aggregate"]
def implied_steps(texts):
    blob = " ".join(texts).lower()
    return sum(1 for v in VERBS if v in blob)

# pool: what v0.2 wants to admit (owner P1/P2)
pool = json.loads((BASE / "v02_coverage_delta_v1.json").read_text(encoding="utf-8"))
p = pool["v02_repair_pool"]
to_admit = {
    "P1_pure_branch": 3,
    "P1_hybrid": 4,
    "P1_one_step": 1,
    "P2_seven_plus": 3,   # selected long chains, owner's second priority
}
total_admit = sum(to_admit.values())
print("pool DAGs to admit:", to_admit, "=", total_admit)

# rank families by release-worthiness: short linear 2-3 step chains first
ranked = []
for f in families:
    fam = f["family"]
    steps = implied_steps(fam_texts[fam])
    sig = set(f["inferred_signature"])
    # release score: short chains score high; nothing with raster/mixed signature
    # scores high (rare in v0.1, keep)
    rasterish = bool(sig & {"L3_04_01_01", "L3_03_02_01", "L3_03_03_A", "L3_03_05_02", "L3_03_01_02", "L3_01_09_03"})
    score = (3 if steps <= 2 else 2 if steps <= 3 else 1) + (0 if rasterish else 2)
    ranked.append({"family": fam, "implied_steps": steps, "rasterish": rasterish,
                   "release_score": score, "ambiguity": f["ambiguity"]})
ranked.sort(key=lambda r: (-r["release_score"], r["family"]))

release = [r for r in ranked if r["release_score"] >= 4][:total_admit]
retained = [r for r in ranked if r not in release]

print()
print("RELEASE (coverage-driven, slots for pool admission):")
for r in release:
    print(f"  {r['family']} | ~{r['implied_steps']} implied steps | score {r['release_score']}")
print(f"release count: {len(release)} families = {len(release)*3} task slots")
print(f"retained: {len(retained)} families = {len(retained)*3} tasks")

out = {
    "schema": "gis_recommend.qgis_benchmark_v02_retention_ledger.v2",
    "ledger_id": "v02-retention-ledger-2",
    "date": "2026-09-11",
    "principle": "release only what coverage needs; REPLACE = coverage-driven substitution, never an error claim",
    "pool_admission_plan": to_admit,
    "released_families": release,
    "retained_families": retained,
    "task_arithmetic": {
        "v01_final_tasks": 120,
        "retained_tasks": len(retained) * 3,
        "released_task_slots": len(release) * 3,
        "new_tasks_from_pool": total_admit * 2,  # 2 variants per new DAG (v0.2 budget policy)
        "v02_final_task_total": len(retained) * 3 + total_admit * 2,
        "note": "family->3-variants verified by id pattern (40 families x 3 = 120); new DAGs follow the v0.2 2-variant policy",
    },
    "caveats": [
        "family-level inference: which sealed DAG each family maps to is not disclosed; release ranking uses text-implied workflow length and modality, never sealed content",
        "the released slots' structural class is inferred (2-3 step linear concentration), consistent with the queue-side 32/52 two_to_three measurement",
    ],
}
path = BASE / "v02_retention_replacement_ledger_v2.json"
path.write_text(json.dumps(out, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
print()
print("task arithmetic:", json.dumps(out["task_arithmetic"], ensure_ascii=False))
print("written:", path.name)
