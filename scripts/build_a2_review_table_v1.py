# -*- coding: utf-8 -*-
"""A2 review — item-by-item adjudication table (Step 2 of owner's plan).

Owner ruling 2026-10-10: A2 enters review; distinguish repeat-var bindings,
scope, function params, presentation-vs-analysis-chain priority, and
cross-sample drift. Old labels are NOT overwritten; this produces the
adjudication table with proposed categories and proposed resolutions only.
"""

import json
import os
import sys
from collections import Counter

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PREP = os.path.join(REPO, "docs", "reports", "gee_semantic_planner_v1_pilot_round3",
                    "expansion_validation_prep_v1")

CHART_PARAM_FAMILY = {
    # variables whose sole downstream consumption is chart/legend/UI
    # construction (the boundary the 100133 revision clarified)
    "data", "xVals", "xValLabels", "xField", "xLabel", "yField", "yLabel",
    "myRows", "stats", "maxValue", "maxMedian", "minValue", "minMedian",
    "myDataTable", "chart", "chartPanel", "getTheChart", "CLASSES", "colors",
    "legend", "BACKGROUND", "ZOOM", "grad", "minScale", "maxScale",
    "paletteBlueRed", "paletteMono", "cmap1", "cmap2",
    "BCimageVisParam", "SO2imageVisParam", "visPar", "visParMedian2",
    "names", "colorBox", "description", "blank", "outline", "grids", "myGrid",
    "chartParam", "cumulative", "shown", "opacity", "label", "i",
}

REACHABILITY_VARS = {  # local-use-but-globally-unreachable cases (frozen判例组)
    ("script_7900", "nbr"), ("script_35821", "illuminationCorrection"),
    ("script_116725", "cloudScore"), ("script_116725", "rescale"),
    ("script_35821", "illuminationCondition"),
}

REPEAT_VAR_BINDINGS = {  # file-level same-binding repeats (var semantics)
    ("script_100110", "emptyImage"), ("script_100133", "empty"),
    ("script_100133", "chartPanel"), ("script_101353", "modis_chlor_a"),
    ("script_100870", "collTOres"), ("script_100870", "collTOres_im"),
    ("script_100870", "collTOres_im_mean"), ("script_100870", "mean_cur"),
    ("script_191158", "lagged34"), ("script_191158", "merged34"),
    ("script_35821", "collection"), ("script_100133", "image"),
    ("script_7900", "image"), ("script_7900", "mask"),
    ("script_7900", "img_plus_ic"), ("script_271544", "img"),
    ("script_100133", "chart"),
}


def load(p):
    return json.load(open(p, encoding="utf-8"))


def main():
    sealed = load(os.path.join(PREP, "automation_sealed_v1.json"))
    ann = {}
    for l in open(os.path.join(PREP, "annotator1_workspace_v1", "results",
                               "annotation_results_v1_20261010T1716.jsonl"),
                  encoding="utf-8"):
        r = json.loads(l)
        if r.get("human"):
            ann[r["unit_id"]] = r

    table = []
    stats = Counter()
    for sid, s in sealed["scripts"].items():
        if not isinstance(s.get("A2"), list):
            continue
        auto_by_var = {c["variable"]: c for c in s["A2"]}
        for var, c in auto_by_var.items():
            uid = f"{sid}:A2:{var}"
            r = ann.get(uid)
            if not r:
                continue
            status_match = r["human"] == c["status"]
            human_uses = r.get("uses_count")
            count_match = (human_uses is not None and
                           int(human_uses) == int(c["post_definition_uses"]))
            if status_match and count_match:
                stats["consistent"] += 1
                continue
            sid_short = sid.replace("script_", "")
            # ---- candidate-cause category (proposal only) ----
            if (sid, var) in REPEAT_VAR_BINDINGS:
                cat = "repeat_var_binding_counting"
            elif (sid, var) in REACHABILITY_VARS:
                cat = "reachability_two_layer"
            elif var in CHART_PARAM_FAMILY and \
                    c["status"] == "analysis_chain" and r["human"] == "presentation_only":
                cat = "chart_param_family_boundary (cross-sample drift: 100133 rule vs 100110 labels)"
            elif r["human"] == "unconsumed" and c["status"] == "analysis_chain":
                cat = "reachability_two_layer"
            elif c["status"] == "unknown_or_other":
                cat = "other"
            else:
                cat = "counting_convention_or_scope"
            # ---- proposed resolution (PROPOSAL, not applied) ----
            if cat.startswith("chart_param_family"):
                proposal = ("adopt 100133 revised rule (variables consumed by "
                            "chart/legend construction = analysis_chain); would "
                            "flip the human label in a FUTURE annotation revision")
            elif cat == "reachability_two_layer":
                proposal = ("keep reference-count-based status; add optional "
                            "globally_reachable=false attribute (two-layer "
                            "reporting, no label change)")
            elif cat == "repeat_var_binding_counting":
                proposal = ("file-level same-binding counts (JS var semantics) "
                            "as canonical; per-declaration counts kept in notes")
            else:
                proposal = ("reconcile count convention (function-param scope / "
                            "definition-expression exclusion / return-counts) "
                            "case by case in review")
            table.append({
                "unit_id": uid, "dimension":
                    ("status+count" if not status_match and not count_match
                     else "status" if not status_match else "count"),
                "auto_status": c["status"],
                "auto_uses": c["post_definition_uses"],
                "human_status": r["human"],
                "human_uses": human_uses,
                "candidate_cause_category": cat,
                "proposed_resolution": proposal,
                "human_note": (r.get("note") or "")[:200],
                "decision": None,  # filled by owner/annotator in review
            })
            stats["divergent"] += 1
            stats["div_" + cat.split(" ")[0]] += 1

    out = os.path.join(PREP, "a2_review", "A2_ADJUDICATION_TABLE_V1.jsonl")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        for row in table:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    summary = {
        "total_units": stats["consistent"] + stats["divergent"],
        "consistent": stats["consistent"],
        "divergent": stats["divergent"],
        "by_category": {k: v for k, v in sorted(stats.items())
                        if k.startswith("div_")},
        "note": "labels NOT modified; decision column open for review",
    }
    json.dump(summary, open(os.path.join(PREP, "a2_review",
                                         "A2_REVIEW_SUMMARY_V1.json"), "w",
                            encoding="utf-8"), indent=2, ensure_ascii=False)
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    print("table:", os.path.relpath(out, REPO))
    return 0


if __name__ == "__main__":
    sys.exit(main())
