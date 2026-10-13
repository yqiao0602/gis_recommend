# -*- coding: utf-8 -*-
"""A2 closeout — owner 5-item rulings (2026-10-10) applied.

Step 1: V1_4 final adjudication table (apply 5 rulings).
Step 2: annotation_results_v2 — apply ALL queued revisions to a revised
annotation file (v1 archived untouched; every revised row keeps v1 values
and revision basis).
"""

import json
import os
import sys
import hashlib
from datetime import datetime

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PREP = os.path.join(REPO, "docs", "reports", "gee_semantic_planner_v1_pilot_round3",
                    "expansion_validation_prep_v1")
A2R = os.path.join(PREP, "a2_review")
WSR = os.path.join(PREP, "annotator1_workspace_v1", "results")

C = {
    ("script_100145", "year"): {"final_uses": 29},
    ("script_101095", "image"): {"final_uses": 3},
    ("script_100110", "landsatTOAcloudmask"): {"final_status": "analysis_chain",
                                               "downstream_effective": False},
    ("script_100110", "maxValue"): {"final_status": "presentation_only"},
    ("script_100110", "maxMedian"): {"final_status": "presentation_only"},
    # myRows / blank: owner confirmed presentation_only = human values, no change
}


def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for c in iter(lambda: f.read(65536), b""):
            h.update(c)
    return h.hexdigest()


def main():
    # ---- Step 1: V1_4 ----
    rows = [json.loads(l) for l in
            open(os.path.join(A2R, "A2_ADJUDICATION_TABLE_V1_3.jsonl"),
                 encoding="utf-8")]
    c_applied = 0
    for row in rows:
        uid = row["unit_id"]
        sid, var = uid.split(":A2:")
        c = C.get((sid, var))
        if not c:
            continue
        if "final_uses" in c:
            row["final_uses"] = c["final_uses"]
            row["count_revision"] = (f"human {row.get('human_uses')} -> final "
                                     f"{c['final_uses']} (owner approved C-ruling)")
        if "final_status" in c:
            row["final_status"] = c["final_status"]
            if c.get("downstream_effective") is not None:
                row["downstream_effective"] = c["downstream_effective"]
            row["status_note"] = "owner C-ruling: semantic status by downstream use"
        row["decision"] = "count_locked" if "final_uses" in c else row.get("decision")
        row["status_locked"] = True
        c_applied += 1
    v14 = os.path.join(A2R, "A2_ADJUDICATION_TABLE_V1_4.jsonl")
    with open(v14, "w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")

    # ---- Step 2: annotation_results_v2 ----
    src = os.path.join(WSR, "annotation_results_v1_20261010T1716.jsonl")
    ann = [json.loads(l) for l in open(src, encoding="utf-8")]
    table = {r["unit_id"]: r for r in rows}
    revised = 0
    for r in ann:
        t = table.get(r["unit_id"])
        if not t:
            continue
        changes = {}
        if t.get("final_status") and t["final_status"] != r.get("human"):
            changes["status"] = (r.get("human"), t["final_status"])
            r["v1_human"] = r.get("human")
            r["human"] = t["final_status"]
        if t.get("final_uses") is not None and r.get("uses_count") is not None \
                and int(t["final_uses"]) != int(r["uses_count"]):
            changes["count"] = (r.get("uses_count"), t["final_uses"])
            r["v1_uses_count"] = r.get("uses_count")
            r["uses_count"] = int(t["final_uses"])
        elif t.get("final_uses") is not None and r.get("uses_count") is None:
            changes["count_set"] = (None, t["final_uses"])
            r["v1_uses_count"] = None
            r["uses_count"] = int(t["final_uses"])
        if r["unit_id"] == "script_100110:A2:landsatTOAcloudmask":
            r["downstream_effective"] = False
        if changes:
            r["revised"] = True
            r["revision"] = changes
            r["revision_basis"] = t.get("decision_basis") or ""
            revised += 1

    v2 = os.path.join(WSR, "annotation_results_v2.jsonl")
    with open(v2, "w", encoding="utf-8") as f:
        for r in ann:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    print(json.dumps({
        "c_rulings_applied": c_applied,
        "v1_4_table": os.path.relpath(v14, REPO),
        "annotation_v2": os.path.relpath(v2, REPO),
        "annotation_v2_sha256": sha(v2),
        "annotation_v1_sha256_untouched": sha(src),
        "units_revised_in_v2": revised,
        "v1_archived": True,
    }, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
