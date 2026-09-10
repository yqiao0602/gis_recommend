"""Apply the owner pre-review verdicts and build the pre-review final task set v2.

19 ACCEPT (unchanged) + 2 MINOR_REVISE (#3, #4) with the owner's exact
replacement texts. Updates derived text hashes for the revised entries
and records the pre-review verdict and revision provenance per entry.
"""
import json
import hashlib
from pathlib import Path

WT = Path(__file__).resolve().parents[1]
BASE = WT / "benchmarks" / "qgis_planner_v1" / "authority"

def jhash(s):
    return hashlib.sha256(s.encode("utf-8")).hexdigest()

REVISIONS = {
    "recovered-302f34cdd7d87920": {
        "pre_review_verdict": "MINOR_REVISE_APPLIED",
        "reason": "owner pre-review: 'best distance configuration' adds a selection/optimization intent that the gold DAG does not require; source supports it but the task level must stay parameter-free",
        "task_text": "Assign a distance value to each zone, create buffer zones from those distances, and select the point features that fall within the buffers; deliver both the selected points and the resulting buffer zones.",
    },
    "recovered-361c5eb306dbc618": {
        "pre_review_verdict": "MINOR_REVISE_APPLIED",
        "reason": "owner pre-review: 'erasing the differences between differently buffered zones' misreads the spatial difference operation as generic difference-removal; replaced with explicit spatial-difference-region semantics",
        "task_text": "Produce an impact assessment of the input habitat areas by building a series of buffered zones, deriving successive spatial difference regions between them, calculating attributes at the relevant stages, and producing the final attribute layer.",
    },
}

draft = [json.loads(l) for l in (BASE / "v02_task_derivation_draft_v1.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
header, records = draft[0], draft[1:]
assert len(records) == 21

for r in records:
    pid = r["packet_entry_id"]
    if pid in REVISIONS:
        rev = REVISIONS[pid]
        r["pre_review_original_text"] = r["task_text"]
        r["task_text"] = rev["task_text"]
        r["pre_review_verdict"] = rev["pre_review_verdict"]
        r["pre_review_reason"] = rev["reason"]
        r["provenance"]["derived_text_sha256"] = jhash(r["task_text"])
    else:
        r["pre_review_verdict"] = "ACCEPT"
    r["provenance"]["review_status"] = "pre_review_passed_pending_dual_fidelity_review"

header = dict(header)
header["schema"] = "gis_recommend.qgis_benchmark_v02_task_derivation.v2"
header["task_set_id"] = "v02-task-pre-review-final-2"
header["supersedes"] = "v02_task_derivation_draft_v1.jsonl"
header["pre_review"] = {
    "date": "2026-09-10",
    "reviewer": "qiaoyun (benchmark owner)",
    "verdicts": {"ACCEPT": 19, "MINOR_REVISE": 2, "MAJOR_REVISE": 0, "REJECT": 0},
    "revisions_applied": ["recovered-302f34cdd7d87920", "recovered-361c5eb306dbc618"],
    "principle_confirmed": "tasks carry only the semantics the gold DAG can prove; no business background is added to make tasks sound more realistic; the derivation ladder (L1 description / L2 composition / L3 paraphrase) is the standing strategy",
}
out = BASE / "v02_task_derivation_v2.jsonl"
with out.open("w", encoding="utf-8") as f:
    f.write(json.dumps(header, ensure_ascii=False) + "\n")
    for r in records:
        f.write(json.dumps(r, ensure_ascii=False) + "\n")

import re
FORBIDDEN = [r"EPSG:\s*\d+", r"\b\d{2,4}\s*m\b", r"\bHRU_ID\b", r"\bMap_FGID\b", r"\bmultigeom\b",
             r"\bDescripc\b", r"\bFID_", r"\bvietnam\b", r"\bAutobahn\b", r"\bbuild_count\b",
             r"\bKLC\b", r"\bBaea\b", r"\bBuowl\b", r"\bpoly_area\b", r"\bs_area\b"]
bad = [r["packet_entry_id"] for r in records for pat in FORBIDDEN if re.search(pat, r["task_text"], re.IGNORECASE)]
print("v2 written:", out.name, "| leak recheck:", "CLEAN" if not bad else bad)
print("verdicts:", {v: sum(1 for r in records if r["pre_review_verdict"] == v) for v in {"ACCEPT", "MINOR_REVISE_APPLIED"}})
