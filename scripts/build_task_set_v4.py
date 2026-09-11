"""Apply the owner's A+B merged revision to entry #5 and produce task set v4.

Also applies the remaining pipeline-resumption step from the coverage-delta
adjudications. Single text change; everything else carried from v3.
"""
import json
import hashlib
from pathlib import Path

WT = Path(__file__).resolve().parents[1]
BASE = WT / "benchmarks" / "qgis_planner_v1" / "authority"

def jhash(s):
    return hashlib.sha256(s.encode("utf-8")).hexdigest()

NEW5 = ("Prepare an urban-surface database from the study-area surface polygons: dissolve them and "
        "enrich them with derived attributes, and deliver two results -- a rasterized version of the "
        "enriched polygons, and zonal statistics of the building heights over the regions formed by "
        "intersecting the study-area polygons with the enriched polygons.")

v3 = [json.loads(l) for l in (BASE / "v02_task_derivation_v3.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
header, records = v3[0], v3[1:]
assert len(records) == 21

for r in records:
    if r["packet_entry_id"] == "recovered-429556807ae79c01":
        r["focused_rereview_original_text"] = r["task_text"]
        r["task_text"] = NEW5
        r["focused_rereview_verdict"] = "DUAL_REVISE_APPLIED_A_B_MERGED"
        r["focused_rereview_reason"] = (
            "dual focused re-review converged on the same defect: both zonalstatisticsfb nodes consume "
            "INPUT_RASTER=build_raster_out, a building-height raster produced outside the gold chain by "
            "DSM-DEM numpy arithmetic (script_0000912.py L902-911, consumed L979/L991); reviewer A additionally "
            "held that 'study-area-refined regions' over-compressed the intersection + second-dissolve region "
            "formation (L917-931). Owner adjudication: A+B merged -- the named raster input AND the "
            "region-formation semantics, no parameter leakage."
        )
        r["provenance"]["derived_text_sha256"] = jhash(NEW5)
    r["provenance"]["review_status"] = "focused_rereview_adjudicated_pending_gate2_recheck"

header = dict(header)
header["schema"] = "gis_recommend.qgis_benchmark_v02_task_derivation.v4"
header["task_set_id"] = "v02-task-set-4"
header["supersedes"] = "v02_task_derivation_v3.jsonl"
header["focused_rereview_adjudication"] = {
    "date": "2026-09-11",
    "decided_by": "qiaoyun (benchmark owner)",
    "verdict": "4 dual_accept + 1 dual_revise (entry 429556807a) -> A+B merged text applied",
}
out = BASE / "v02_task_derivation_v4.jsonl"
with out.open("w", encoding="utf-8") as f:
    f.write(json.dumps(header, ensure_ascii=False) + "\n")
    for r in records:
        f.write(json.dumps(r, ensure_ascii=False) + "\n")
print("v4 written:", out.name)
for r in records:
    if r["packet_entry_id"] == "recovered-429556807ae79c01":
        print("new #5:", r["task_text"])
