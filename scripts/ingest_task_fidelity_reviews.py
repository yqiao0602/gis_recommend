"""Ingest dual task-fidelity review outputs, build consensus, write the ledger."""
import json
import collections
from pathlib import Path

WT = Path(__file__).resolve().parents[1]
BASE = WT / "benchmarks" / "qgis_planner_v1" / "authority"
DISP = BASE / "review_dispatch"
BANNER = ('"glm-5.3"', "Until then", "[claude-code")

def load(path):
    rows = []
    for line in path.read_text(encoding="utf-8-sig").splitlines():
        line = line.strip()
        if not line or any(line.startswith(b) for b in BANNER):
            continue
        rows.append(json.loads(line))
    return rows

A = load(DISP / "taskfid_a_raw_output.txt")
B = load(DISP / "taskfid_b_raw_output.txt")
print("A:", len(A), "| B:", len(B))

tasks = [json.loads(l) for l in (BASE / "v02_task_derivation_v2.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
ids = [t["packet_entry_id"] for t in tasks[1:]]
assert {r["packet_entry_id"] for r in A} == set(ids)
assert {r["packet_entry_id"] for r in B} == set(ids)

by_a = {r["packet_entry_id"]: r for r in A}
by_b = {r["packet_entry_id"]: r for r in B}

consensus = []
for pid in ids:
    a, b = by_a[pid], by_b[pid]
    if a["decision"] == "accept" and b["decision"] == "accept":
        outcome = "dual_accept"
        action = "proceed_to_candidate_pool"
    elif a["decision"] == b["decision"]:
        outcome = f"dual_{a['decision']}"
        action = "owner_adjudication_required" if a["decision"] != "reject" else "excluded"
    else:
        outcome = "disagreement"
        action = "owner_adjudication_required"
    consensus.append({
        "packet_entry_id": pid,
        "reviewer_a_decision": a["decision"],
        "reviewer_b_decision": b["decision"],
        "outcome": outcome,
        "action": action,
        "a_verdicts": a["verdicts"],
        "b_verdicts": b["verdicts"],
        "a_reason": a["reason"],
        "b_reason": b["reason"],
    })

tally = collections.Counter(c["outcome"] for c in consensus)
print("consensus:", dict(tally))
qfail = []
for c in consensus:
    for side in ("a_verdicts", "b_verdicts"):
        for q, v in c[side].items():
            if not v:
                qfail.append(f"{c['packet_entry_id'][:20]}:{side[0]}:{q}")
print("failed sub-verdicts:", qfail if qfail else "NONE")
for c in consensus:
    if c["action"] != "proceed_to_candidate_pool":
        print("NEEDS ATTENTION:", c["packet_entry_id"], c["reviewer_a_decision"], "/", c["reviewer_b_decision"])
        print("  A:", c["a_reason"][:220])
        print("  B:", c["b_reason"][:220])

out = BASE / "v02_task_fidelity_reviews_v1.jsonl"
with out.open("w", encoding="utf-8") as f:
    f.write(json.dumps({
        "schema": "gis_recommend.qgis_benchmark_v02_task_fidelity_reviews.v1",
        "ledger_id": "v02-task-fidelity-reviews-1",
        "date": "2026-09-10",
        "brief": "review_dispatch/v02_task_fidelity_review_brief_v1.md (six questions, DAG-eligibility re-adjudication forbidden)",
        "task_set": "v02_task_derivation_v2.jsonl (pre-review final, 19 accept + 2 owner revisions)",
        "reviewer_channel": "claude CLI headless, model glm-5.3, read-only tools, two independent sessions",
        "records": len(A) + len(B),
    }, ensure_ascii=False) + "\n")
    for r in A + B:
        f.write(json.dumps({"record_type": "review", **r}, ensure_ascii=False) + "\n")
    for c in consensus:
        f.write(json.dumps({"record_type": "consensus", **c}, ensure_ascii=False) + "\n")
print("written:", out.name)
