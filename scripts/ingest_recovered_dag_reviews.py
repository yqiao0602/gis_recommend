"""Ingest dual-reviewer outputs for the 24 recovered DAGs and build the consensus ledger.

Reads the two raw reviewer outputs, validates 24 records each, joins them
per packet entry, applies the consensus policy, and writes
v02_recovered_dag_reviews_v1.jsonl (header + 48 review records + 24
consensus records). Read-only over reviewer outputs.
"""
import json
import collections
from pathlib import Path

WT = Path(__file__).resolve().parents[1]
DISP = WT / "benchmarks" / "qgis_planner_v1" / "authority" / "review_dispatch"
OUT = WT / "benchmarks" / "qgis_planner_v1" / "authority" / "v02_recovered_dag_reviews_v1.jsonl"
PACKET = WT / "benchmarks" / "qgis_planner_v1" / "authority" / "v02_recovered_dag_review_packet_v1.jsonl"

BANNER = ('"glm-5.3"', "Until then", "[claude-code")

def load_reviews(path):
    rows = []
    for line in path.read_text(encoding="utf-8-sig").splitlines():
        line = line.strip()
        if not line or any(line.startswith(b) for b in BANNER):
            continue
        rows.append(json.loads(line))
    return rows

A = load_reviews(DISP / "reviewer_a_raw_output.txt")
B = load_reviews(DISP / "reviewer_b_raw_output.txt")
assert len(A) == 24 and len(B) == 24, (len(A), len(B))
packet_ids = [json.loads(l)["packet_entry_id"] for l in PACKET.read_text(encoding="utf-8").splitlines()[1:] if l.strip()]
assert {r["packet_entry_id"] for r in A} == set(packet_ids)
assert {r["packet_entry_id"] for r in B} == set(packet_ids)

topo_by_entry = {}
for l in PACKET.read_text(encoding="utf-8").splitlines()[1:]:
    if l.strip():
        e = json.loads(l)
        topo_by_entry[e["packet_entry_id"]] = (e["dag"]["topology_class"], e["dag"]["graph_size_stratum"])

by_a = {r["packet_entry_id"]: r for r in A}
by_b = {r["packet_entry_id"]: r for r in B}

consensus = []
for pid in packet_ids:
    a, b = by_a[pid], by_b[pid]
    da, db = a["decision"], b["decision"]
    if da == "accept" and db == "accept":
        outcome = "dual_accept"
        action = "proceed_to_task_fidelity"
    elif da == "reject" and db == "reject":
        outcome = "dual_reject"
        action = "excluded"
    else:
        outcome = "disagreement" if da != db else f"dual_{da}"
        action = "human_adjudication_required"
    consensus.append({
        "packet_entry_id": pid,
        "topology_class": topo_by_entry[pid][0],
        "graph_size_stratum": topo_by_entry[pid][1],
        "reviewer_a_decision": da,
        "reviewer_b_decision": db,
        "outcome": outcome,
        "action": action,
        "a_reason": a["reason"],
        "b_reason": b["reason"],
        "a_task_fidelity": a["task_fidelity_verdict"],
        "b_task_fidelity": b["task_fidelity_verdict"],
    })

tally = collections.Counter(c["outcome"] for c in consensus)
print("consensus tally:", dict(tally))
print()
print("=== disagreements / dual_revise (need attention) ===")
for c in consensus:
    if c["action"] != "proceed_to_task_fidelity" and c["action"] != "excluded":
        print(f"{c['packet_entry_id']} [{c['topology_class']}/{c['graph_size_stratum']}]  A={c['reviewer_a_decision']} B={c['reviewer_b_decision']}")
print()
print("=== dual_reject ===")
for c in consensus:
    if c["outcome"] == "dual_reject":
        print(f"{c['packet_entry_id']}: A: {c['a_reason'][:100]}")
        print(f"   B: {c['b_reason'][:100]}")
print()
# supply impact of dual_accept set
acc = [c for c in consensus if c["outcome"] == "dual_accept"]
print("dual_accept topology:", dict(collections.Counter(c["topology_class"] for c in acc)))
print("dual_accept size:", dict(collections.Counter(c["graph_size_stratum"] for c in acc)))

header = {
    "schema": "gis_recommend.qgis_benchmark_v02_recovered_dag_reviews.v1",
    "ledger_id": "v02-recovered-dag-reviews-1",
    "date": "2026-09-10",
    "brief": "review_dispatch/v02_recovered_dag_review_brief_v1.md",
    "packet": "v02_recovered_dag_review_packet_v1.jsonl (24 entries)",
    "reviewer_channel": "claude CLI headless, model glm-5.3, tools restricted to Read/Grep/Glob, two independent sessions; channel recorded per repo transparency convention (codex/gemini channels were down, see review_dispatch/dispatch_log_2026-09-10.md)",
    "consensus_policy": {"dual_accept": "proceed_to_task_fidelity", "dual_reject": "excluded", "dual_revise": "human_adjudication_required", "disagreement": "human_adjudication_required"},
    "records": 48,
    "consensus_records": 24,
}
with OUT.open("w", encoding="utf-8") as f:
    f.write(json.dumps(header, ensure_ascii=False) + "\n")
    for r in A + B:
        f.write(json.dumps({"record_type": "review", **r}, ensure_ascii=False) + "\n")
    for c in consensus:
        f.write(json.dumps({"record_type": "consensus", **c}, ensure_ascii=False) + "\n")
print("written:", OUT.name)
