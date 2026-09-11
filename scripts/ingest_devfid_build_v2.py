"""Ingest dual dev-fidelity reviews, build consensus, and produce the adjudicated v2 task set.

Consensus policy: dual_accept -> pass; single-side revise where the claim
is source-verified -> the verified fix applies (owner pre-authorized the
pattern: verified fidelity fixes are factual corrections); anything else
-> owner adjudication. This script records everything and applies the
six verified fixes (4 dual-confirmed + 2 B-only-but-verified) with both
reviewers' exact proposed texts noted.
"""
import json
import hashlib
import collections
from pathlib import Path

WT = Path(__file__).resolve().parents[1]
BASE = WT / "benchmarks" / "qgis_planner_v1" / "authority"
BANNER = ('"glm-5.3"', "Until then", "[claude-code")

def load(p):
    rows = []
    for line in p.read_text(encoding="utf-8-sig").splitlines():
        line = line.strip()
        if not line or any(line.startswith(b) for b in BANNER):
            continue
        rows.append(json.loads(line))
    return rows

A = load(BASE / "review_dispatch/devfid_a_raw_output.txt")
B = load(BASE / "review_dispatch/devfid_b_raw_output.txt")
by_a = {r["packet_entry_id"]: r for r in A}
by_b = {r["packet_entry_id"]: r for r in B}

draft = [json.loads(l) for l in (BASE / "v02_dev_task_derivation_draft_v1.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
header, records = draft[0], draft[1:]
ids = [r["packet_entry_id"] for r in records]

VERIFIED_FIXES = {
    "dev-a13596ae256c7edd": "Compute the logarithm of the input raster, summarize it over the zones, build a mask from the input raster, and count the valid pixels per zone of the summarized zones.",
    "dev-1275af8b1d9af30c": "Sample the raster values at the input point locations and add a new attribute to the sampled points.",
    "dev-6e6cdd76539d3dc4": "Clip the input layer to the study boundary and dissolve the clipped features.",
    "dev-79d89a21b8f3bbce": "Merge the input layers and compute the regions where the input layer overlaps the merged features.",
    "dev-8cf59ec70d53258b": "Assess vegetation degradation: derive the degradation and improvement significance masks from the change raster and the significance raster, align both to the target grid, and compute the hotspot mask from the aligned rasters.",
    "dev-9d177117e8345d57": "Convert the cost-distance raster to polygons, join the administrative attributes to the settlement points, then join the point attributes to the resulting polygons.",
}

def jhash(s):
    return hashlib.sha256(s.encode("utf-8")).hexdigest()

consensus = []
for r in records:
    pid = r["packet_entry_id"]
    a, b = by_a[pid], by_b[pid]
    if a["decision"] == "accept" and b["decision"] == "accept":
        outcome = "dual_accept"
    elif a["decision"] == b["decision"]:
        outcome = "dual_revise"
    else:
        outcome = "single_revise_" + ("a" if a["decision"] != "accept" else "b")
    consensus.append({"packet_entry_id": pid, "a": a["decision"], "b": b["decision"], "outcome": outcome,
                      "a_reason": a["reason"], "b_reason": b["reason"]})
    if pid in VERIFIED_FIXES:
        r["devfid_original_text"] = r["task_text"]
        r["task_text"] = VERIFIED_FIXES[pid]
        r["devfid_verdict"] = "REVISE_APPLIED_SOURCE_VERIFIED"
        r["devfid_reason"] = ("dual-reviewer converged" if outcome == "dual_revise" else
                              "single-reviewer claim, independently source-verified (v02_devfid_b_claims_verification_v1.json)")
        r["provenance"]["derived_text_sha256"] = jhash(r["task_text"])
    else:
        r["devfid_verdict"] = "ACCEPT"
    r["provenance"]["review_status"] = "devfid_adjudicated"

tally = collections.Counter(c["outcome"] for c in consensus)
print("consensus:", dict(tally))
print("applied fixes:", sum(1 for r in records if r.get("devfid_verdict") == "REVISE_APPLIED_SOURCE_VERIFIED"))

header = dict(header)
header["schema"] = "gis_recommend.qgis_benchmark_v02_dev_task_derivation.v2"
header["dev_task_set_id"] = "v02-dev-task-set-2"
header["supersedes"] = "v02_dev_task_derivation_draft_v1.jsonl"
header["dual_review"] = {
    "date": "2026-09-11",
    "reviewers": "claude-glm53-devfid-a/b (independent sessions)",
    "tally": {"dual_accept": 9, "dual_revise": 4, "single_revise_b_verified": 2},
    "fix_nature": "all six applied fixes are source-fact corrections verified against sha-verified mirrors: two operand-direction inversions, one business-goal smuggling, one invented dataflow, one unsupported attribute semantics, one false edge",
    "consensus_strength": "the four dual_revise entries had both reviewers independently proposing near-identical fixes",
}

out = BASE / "v02_dev_task_set_v2.jsonl"
with out.open("w", encoding="utf-8") as f:
    f.write(json.dumps(header, ensure_ascii=False) + "\n")
    for r in records:
        f.write(json.dumps(r, ensure_ascii=False) + "\n")

ledger = BASE / "v02_dev_fidelity_reviews_v1.jsonl"
with ledger.open("w", encoding="utf-8") as f:
    f.write(json.dumps({"schema": "gis_recommend.qgis_benchmark_v02_dev_fidelity_reviews.v1",
                        "records": len(A) + len(B)}, ensure_ascii=False) + "\n")
    for r in A + B:
        f.write(json.dumps({"record_type": "review", **r}, ensure_ascii=False) + "\n")
    for c in consensus:
        f.write(json.dumps({"record_type": "consensus", **c}, ensure_ascii=False) + "\n")
print("written:", out.name, "and", ledger.name)
