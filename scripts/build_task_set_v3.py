"""Build task set v3: apply the owner's dual-review adjudication fixes.

v2 already carries the pre-review fixes (best-configuration, spatial
difference regions). v3 adds the four source-fidelity fixes adjudicated
from the dual-review disagreements, all verified against source code:
  entry 302f34cdd7 (#3): 'each zone' -> 'each of the input features'
  entry 429556807a (#5): root input is the study-area surface polygon
      grid (not building footprints); dissolve is unconditional
  entry 4cb8772d44 (#7): difference direction corrected
  entry 8c87bab93c (#13): difference direction corrected + the target
      layer named as the base input
Owner final texts adopted verbatim (including 'derived attributes' for
#5 and 'target layer' for #13).
"""
import json
import hashlib
import re
from pathlib import Path

WT = Path(__file__).resolve().parents[1]
BASE = WT / "benchmarks" / "qgis_planner_v1" / "authority"

def jhash(s):
    return hashlib.sha256(s.encode("utf-8")).hexdigest()

FIXES = {
    "recovered-302f34cdd7d87920": {
        "task_text": "Assign a distance value to each of the input features, create buffer zones from those distances, and select the point features that fall within the buffers; deliver both the selected points and the resulting buffer zones.",
        "reason": "dual-review adjudication (B verified, source-confirmed): 'zone' has no source concept; the buffered features are the input layer's features",
    },
    "recovered-429556807ae79c01": {
        "task_text": "Prepare an urban-surface database from the study-area surface polygons: dissolve them and enrich them with derived attributes, and deliver two results -- a rasterized version of the enriched polygons, and zonal statistics over the study-area-refined regions.",
        "reason": "dual-review adjudication (B verified, source-confirmed): root input is the user-selected polygon grid layer, not building footprints; dissolve is unconditional (FIELD:[]) with the type code assigned after; owner chose 'derived attributes' phrasing",
    },
    "recovered-4cb8772d44c58cc4": {
        "task_text": "Compute the intersection of two layers, then remove that intersection from the original input layer.",
        "reason": "dual-review adjudication (B verified, source-confirmed): difference takes INPUT=original layer, OVERLAY=intersection result; previous text inverted base and overlay",
    },
    "recovered-8c87bab93cfc8fe5": {
        "task_text": "Reproject the line layer, buffer the reprojected lines, erase the buffered region from the target layer, and split any multipart features of the remaining areas into single parts.",
        "reason": "dual-review adjudication (B verified, source-confirmed): difference takes INPUT=target layer, OVERLAY=buffer; direction corrected and the second business input named",
    },
}

v2 = [json.loads(l) for l in (BASE / "v02_task_derivation_v2.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
header, records = v2[0], v2[1:]
assert len(records) == 21

for r in records:
    pid = r["packet_entry_id"]
    if pid in FIXES:
        fx = FIXES[pid]
        r["dual_review_original_text"] = r["task_text"]
        r["task_text"] = fx["task_text"]
        r["dual_review_verdict"] = "MINOR_REVISE_APPLIED"
        r["dual_review_reason"] = fx["reason"]
        r["provenance"]["derived_text_sha256"] = jhash(r["task_text"])
    else:
        r["dual_review_verdict"] = "ACCEPT"
    r["provenance"]["review_status"] = "dual_review_adjudicated_pending_focused_rereview_and_gate2"

header = dict(header)
header["schema"] = "gis_recommend.qgis_benchmark_v02_task_derivation.v3"
header["task_set_id"] = "v02-task-set-3"
header["supersedes"] = "v02_task_derivation_v2.jsonl"
header["dual_review_adjudication"] = {
    "date": "2026-09-10",
    "decided_by": "qiaoyun (benchmark owner)",
    "round": "dual task-fidelity review on v2 (A: 21/21 accept; B: 17 accept + 4 revise, all 4 source-verified correct)",
    "final_tally": {"ACCEPT": 16, "MINOR_REVISE": 5, "MAJOR_REVISE": 0, "REJECT": 0},
    "revision_nature": "the four dual-review fixes are source-fact fidelity corrections (difference INPUT/OVERLAY direction, root input identity, unsupported terminology), not language polish; the two pre-review fixes remain in place",
    "not_yet_delivered": "these 21 records are task-text candidates only; v0.2 deliverable task+gold count remains 0; remaining pipeline: focused re-review of revised texts, Gate 2 nine-index recheck on task texts, human approval, candidate pool, dev/final selection, freeze",
}
out = BASE / "v02_task_derivation_v3.jsonl"
with out.open("w", encoding="utf-8") as f:
    f.write(json.dumps(header, ensure_ascii=False) + "\n")
    for r in records:
        f.write(json.dumps(r, ensure_ascii=False) + "\n")

FORBIDDEN = [r"EPSG:\s*\d+", r"\b\d{2,4}\s*m\b", r"\bHRU_ID\b", r"\bMap_FGID\b", r"\bmultigeom\b",
             r"\bDescripc\b", r"\bFID_", r"\bvietnam\b", r"\bAutobahn\b", r"\bbuild_count\b",
             r"\bKLC\b", r"\bBaea\b", r"\bBuowl\b", r"\bpoly_area\b", r"\bs_area\b", r"\bnadajniki\b"]
bad = [r["packet_entry_id"] for r in records for pat in FORBIDDEN if re.search(pat, r["task_text"], re.IGNORECASE)]
multi_ok = all(("multi" in r["output_expression"]) == (pid in ("recovered-302f34cdd7d87920", "recovered-429556807ae79c01", "recovered-f950402772c6e9d1")) for r in records for pid in [r["packet_entry_id"]])
print("v3 written:", out.name)
print("leak recheck:", "CLEAN" if not bad else bad)
print("multi-output consistency:", multi_ok)
print("verdicts:", {v: sum(1 for r in records if r["dual_review_verdict"] == v) for v in ("ACCEPT", "MINOR_REVISE_APPLIED")})
