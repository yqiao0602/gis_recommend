"""Final-variant dual review: consensus ledger + apply the four verified text fixes.
The gold-defect escalation (79dde3ac5c missing p6->p7 edge) is NOT auto-fixed --
it awaits the owner's O1/O2 ruling. Text fixes for 79dde3ac are written to include
the clip/selection steps AND the intersection->difference flow as the author
intended (both reviewers described that flow from the source); if the owner
chooses O2 (reject the DAG), these two texts are withdrawn with it.
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

A = load(BASE / "review_dispatch/finvar_a_raw_output.txt")
B = load(BASE / "review_dispatch/finvar_b_raw_output.txt")
by_a = {(r["pool_key"], r["variant"]): r for r in A}
by_b = {(r["pool_key"], r["variant"]): r for r in B}

draft = [json.loads(l) for l in (BASE / "v02_final_variant_draft_v1.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
header, records = draft[0], draft[1:]

def jhash(s):
    return hashlib.sha256(s.encode("utf-8")).hexdigest()

FIXES = {
    ("571c057b7e", "v1"): None,  # dual accept, no fix
    ("79dde3ac5c", "v1"): "Clip the input layer to the boundary, extract the qualifying selected areas and split them into the attached and the detached classes, buffer each class separately, intersect the selection with the attached-class buffers, subtract the detached-class buffers from the intersection, and keep the single-part results that meet the minimum size.",
    ("303d4eb115", "v1"): "Stamp the burnt-area attribute table with a chain of computed fields -- the feature identifier, the mapping period, the current month, the region, the upload date, the current-state flag, and the comments -- each field computed from the previous step's output.",
    ("302f34cdd7", "v2"): None,
    ("429556807a", "v2"): "Dissolve the study-area polygons, add derived attributes to the dissolved polygons, intersect the study-area grid with the enriched polygons to refine the regions, rasterize the enriched polygons, and compute zonal statistics of the building heights over the refined regions, delivering both the rasterized layer and the statistics.",
    ("7a19dc431b", "v2"): None,
    ("571c057b7e", "v2"): None,
    ("79dde3ac5c", "v2"): "Clip the input layer to the boundary and select the qualifying areas, extract the attached and the detached area classes by expression, buffer each class, intersect the selection with the attached-class buffers, erase the detached-class buffers from the intersection, split the result into single parts, and filter by the area condition.",
    ("303d4eb115", "v2"): "Assign the feature identifier to each burnt-area feature, then successively add the mapping period, the current month, the region, the upload date, the current-state flag, and the comments as computed attributes, each step reading the table produced by the previous one.",
}

consensus = []
for r in records:
    key = (r["pool_key"], r["variant"])
    a, b = by_a[key], by_b[key]
    if a["decision"] == "accept" and b["decision"] == "accept":
        outcome = "dual_accept"
    elif a["decision"] == b["decision"]:
        outcome = "dual_revise"
    else:
        outcome = "single_revise_" + ("a" if a["decision"] != "accept" else "b")
    consensus.append({"pool_key": key[0], "variant": key[1], "a": a["decision"], "b": b["decision"],
                      "outcome": outcome, "a_reason": a["reason"], "b_reason": b["reason"]})
    fix = FIXES.get(key)
    if fix:
        r["finvar_original_text"] = r["task_text"]
        r["task_text"] = fix
        r["finvar_verdict"] = "REVISE_APPLIED_SOURCE_VERIFIED"
        r["finvar_reason"] = ("dual-reviewer converged" if outcome == "dual_revise" else
                              "single-reviewer claim, independently source-verified")
        r["provenance_text_hash"] = jhash(fix)
    else:
        r["finvar_verdict"] = "ACCEPT"

tally = collections.Counter(c["outcome"] for c in consensus)
print("consensus:", dict(tally))
applied = sum(1 for r in records if r.get("finvar_verdict") == "REVISE_APPLIED_SOURCE_VERIFIED")
print("fixes applied:", applied)
print("note: 79dde3ac5c texts describe the intended intersection->difference flow; the gold edge correction itself awaits owner O1/O2")

header = dict(header)
header["schema"] = "gis_recommend.qgis_benchmark_v02_final_variant_set.v2"
header["variant_set_id"] = "v02-final-variant-set-2"
header["supersedes"] = "v02_final_variant_draft_v1.jsonl"
header["dual_review"] = {
    "date": "2026-09-11",
    "tally": dict(tally),
    "gold_defect_escalation": "79dde3ac5c missing p6->p7 edge (source typo interesection/intersection; original script NameError-crashes); owner O1 (correct edge set, keep 99) vs O2 (reject DAG, final 97) PENDING -- the two 79dde3ac texts are contingent on O1 and are withdrawn if O2",
}
out = BASE / "v02_final_variant_set_v2.jsonl"
with out.open("w", encoding="utf-8") as f:
    f.write(json.dumps(header, ensure_ascii=False) + "\n")
    for r in records:
        f.write(json.dumps(r, ensure_ascii=False) + "\n")

ledger = BASE / "v02_final_variant_reviews_v1.jsonl"
with ledger.open("w", encoding="utf-8") as f:
    f.write(json.dumps({"schema": "gis_recommend.qgis_benchmark_v02_final_variant_reviews.v1",
                        "records": len(A) + len(B)}, ensure_ascii=False) + "\n")
    for r in A + B:
        f.write(json.dumps({"record_type": "review", **r}, ensure_ascii=False) + "\n")
    for c in consensus:
        f.write(json.dumps({"record_type": "consensus", **c}, ensure_ascii=False) + "\n")
print("written:", out.name, "and", ledger.name)
