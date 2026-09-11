"""Stage-1b: n-gram overlap of v0.1 final texts against exclusion-ledger task texts.

The token-signature match (M4) only catches exact token-distribution
duplicates. Near-duplicates (rewrites) need n-gram overlap. The
exclusion ledger records task_text_signature per exclusion record but
not the raw texts; however the discovery corpora (which feed the
exclusion ledger via the training pipeline) carry task_text fields.
For the training-source side we use paper_v1 training manifest texts
(8,912 rows) -- the same corpus the 2026-09-10 audit measured zero
overlap against, now re-verified as the v0.2 spec's source-disjoint
check for RETAIN qualification.
"""
import json
from pathlib import Path

WT = Path(__file__).resolve().parents[1]
BASE = WT / "benchmarks" / "qgis_planner_v1" / "authority"
MAIN = Path(r"E:\02_projects\03_PythonProject\Operator-recommend-system\Algorithm_classification\system_redesign")
TASKS = BASE.parent / "releases/v0.1-final-core-120/tasks.jsonl"

tasks = [json.loads(l) for l in TASKS.read_text(encoding="utf-8").splitlines() if l.strip()]
train = [json.loads(l) for l in (MAIN / "docs/reports/paper_v1_supervision/paper_v1_supervision_manifest.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]

def ngrams(text, n=6):
    toks = text.lower().split()
    return set(tuple(toks[i:i+n]) for i in range(len(toks)-n+1))

T = set()
for r in train:
    T |= ngrams(r.get("task_text", ""))

hits = []
total_shared = 0
for t in tasks:
    g = ngrams(t["task_text"])
    shared = g & T
    if shared:
        hits.append((t["sample_id"], len(shared), sorted(" ".join(x) for x in shared)[:3]))
        total_shared += len(shared)

print("final tasks:", len(tasks), "| training texts:", len(train))
print("tasks with >=1 shared 6-gram:", len(hits), "| total shared 6-grams:", total_shared)
for h in hits[:10]:
    print(" ", h)
