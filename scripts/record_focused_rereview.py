"""Record the focused re-review round (5 revised texts) into the review ledger."""
import json
import collections
from pathlib import Path

WT = Path(__file__).resolve().parents[1]
BASE = WT / "benchmarks" / "qgis_planner_v1" / "authority"
BANNER = ('"glm-5.3"', "Until then", "[claude-code")

def load(path):
    rows = []
    for line in path.read_text(encoding="utf-8-sig").splitlines():
        line = line.strip()
        if not line or any(line.startswith(b) for b in BANNER):
            continue
        rows.append(json.loads(line))
    return rows

A = load(BASE / "review_dispatch" / "focus_a_raw_output.txt")
B = load(BASE / "review_dispatch" / "focus_b_raw_output.txt")
assert len(A) == 5 and len(B) == 5

TARGETS = ["recovered-302f34cdd7d87920", "recovered-361c5eb306dbc618",
           "recovered-429556807ae79c01", "recovered-4cb8772d44c58cc4",
           "recovered-8c87bab93cfc8fe5"]
by_a = {r["packet_entry_id"]: r for r in A}
by_b = {r["packet_entry_id"]: r for r in B}

consensus = []
for pid in TARGETS:
    a, b = by_a[pid], by_b[pid]
    if a["decision"] == "accept" and b["decision"] == "accept":
        outcome, action = "dual_accept", "proceed_to_gate2_when_pipeline_resumes"
    elif a["decision"] == b["decision"]:
        outcome, action = f"dual_{a['decision']}", "owner_adjudication_required"
    else:
        outcome, action = "disagreement", "owner_adjudication_required"
    consensus.append({
        "packet_entry_id": pid,
        "reviewer_a_decision": a["decision"],
        "reviewer_b_decision": b["decision"],
        "outcome": outcome,
        "action": action,
        "a_reason": a["reason"],
        "b_reason": b["reason"],
    })

tally = collections.Counter(c["outcome"] for c in consensus)
print("focused re-review consensus:", dict(tally))
for c in consensus:
    if c["action"] == "owner_adjudication_required":
        print("DUAL REVISE:", c["packet_entry_id"])
        print("  A:", c["a_reason"][:350])
        print("  B:", c["b_reason"][:350])

out = BASE / "v02_task_fidelity_reviews_v1.jsonl"
with out.open("a", encoding="utf-8") as f:
    f.write(json.dumps({
        "record_type": "round_header",
        "round": "focused_rereview_of_5_revised_texts",
        "date": "2026-09-10",
        "brief": "review_dispatch/v02_focused_rereview_brief_v1.md",
        "task_set": "v02_task_derivation_v3.jsonl",
        "scope": "five owner-revised texts only; seven checks; DAG/gold/Gate/protocol changes forbidden",
        "pipeline_status": "RECORDED BUT PAUSED per owner instruction 2026-09-10 -- no gate2/approval/pool actions until the v0.1->v0.2 coverage-delta decisions are settled",
        "consensus_tally": dict(tally),
    }, ensure_ascii=False) + "\n")
    for r in A + B:
        f.write(json.dumps({"record_type": "focused_review", "round": 2, **r}, ensure_ascii=False) + "\n")
    for c in consensus:
        f.write(json.dumps({"record_type": "focused_consensus", "round": 2, **c}, ensure_ascii=False) + "\n")
print("appended to:", out.name)
