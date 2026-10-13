#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""PCA C-group v2 — owner round-14 targeted revisions.

Every patch below is a discrete, auditable JSON operation on v1
(SHA 18aace83f9af72fc). Three patch families:
  F1 (P0 gold-consistency): C-01/03/05/09/13/14/17/19 alternatives-vs-
     failures conflicts resolved;
  F2 (stated-parameter caliber): task texts "stated X" -> "you state X"
     (selectable semantics) + machine field parameter_availability on all
     20 rows; scoring checks DECLARATION, never value-guessing;
  F3 (single-item fixes): C-03 cell note, C-06 CRS-suitability, C-10
     threshold wording, C-12 100% denominator, C-18 conditioning freedom.
Diff table emitted separately (pca_c_group_v2_difftable_v1.md).
"""
import json, hashlib

V1 = "docs/reports/route2_p0_contract/plan_pipeline_v1/planning_capability_audit_v1/pca_c_group_tasks_gold_v1.json"
OUT = "docs/reports/route2_p0_contract/plan_pipeline_v1/planning_capability_audit_v1/pca_c_group_tasks_gold_v2.json"

# ---- F2: task-text "stated X" -> selectable wording ----
TEXT_PATCH = {
"PCA-C-05": ("compute area-weighted global mean and per-continent totals of the raster values, so that pixel counts are converted to true areas rather than naive counts.",
             "compute area-weighted global mean and per-continent totals of the raster values — naming the continent-boundary source you use (or explicitly declaring it as a required external input) — so that pixel counts are converted to true areas rather than naive counts."),
"PCA-C-08": ("flag cells above a stated slope threshold that also fall inside a road-corridor buffer",
             "flag cells above a slope threshold you state explicitly that also fall inside a road-corridor buffer"),
"PCA-C-10": ("flag zones whose density exceeds a stated threshold.",
             "flag zones whose density exceeds a density threshold you state explicitly."),
"PCA-C-13": ("flag features violating a stated attribute rule (e.g., area below a minimum).",
             "flag features violating an attribute rule you state explicitly (for example, an area-below-minimum rule)."),
"PCA-C-14": ("Grade water samples (point locations with turbidity and chlorophyll attributes) into quality tiers defined by stated thresholds,",
             "Grade water samples (point locations with turbidity and chlorophyll attributes) into quality tiers defined by thresholds you state explicitly,"),
"PCA-C-15": ("flag areas where the absolute difference exceeds a stated tolerance, and output a confidence raster combining difference magnitude with a stated slope-stability hint.",
             "flag areas where the absolute difference exceeds a tolerance you state explicitly, and output a confidence raster combining difference magnitude with a slope-stability hint you state explicitly."),
"PCA-C-16": ("Apply class-dependent buffer zones around road segments — each road class has its own stated radius —",
             "Apply class-dependent buffer zones around road segments — assign and declare your own radius per road class —"),
"PCA-C-18": ("combine with a stated depth-proxy rule to screen potential inundation cells,",
             "combine with a depth-proxy rule you state explicitly to screen potential inundation cells,"),
"PCA-C-20": ("screen areas by stated slope and aspect suitability rules, exclude stated exclusion zones,",
             "screen areas by slope and aspect suitability rules you state explicitly, exclude exclusion zones you name explicitly,"),
}

# ---- parameter_availability per row (F2 machine field) ----
PAV = {
"PCA-C-01": {"allocation_rule": "selectable", "common_crs": "selectable"},
"PCA-C-02": {"change_encoding": "selectable", "reference_grid": "selectable"},
"PCA-C-03": {"ordering_convention": "selectable"},
"PCA-C-04": {"target_crs": "selectable", "repair_strategy": "selectable"},
"PCA-C-05": {"equal_area_projection": "selectable", "continent_boundary_source": "selectable_with_declaration"},
"PCA-C-06": {"common_crs": "selectable_with_suitability_statement", "seam_dedup": "selectable"},
"PCA-C-07": {"percentage_denominator": "selectable"},
"PCA-C-08": {"slope_threshold": "selectable", "buffer_width": "selectable"},
"PCA-C-09": {"nodata_handling": "selectable"},
"PCA-C-10": {"density_threshold": "selectable", "pixel_allocation": "selectable"},
"PCA-C-11": {"season_boundaries": "selectable"},
"PCA-C-12": {"diversity_measure": "selectable", "dominant_tie_break": "selectable"},
"PCA-C-13": {"attribute_rule_threshold": "selectable", "overlap_tolerance": "selectable"},
"PCA-C-14": {"tier_thresholds": "selectable", "tier_intervals": "selectable"},
"PCA-C-15": {"difference_tolerance": "selectable", "confidence_formula": "selectable"},
"PCA-C-16": {"per_class_radii": "selectable", "multiple_match_rule": "selectable"},
"PCA-C-17": {"rural_baseline": "selectable", "summer_months": "selectable", "ranking_statistic": "selectable"},
"PCA-C-18": {"depth_proxy_rule": "selectable", "accumulation_cut": "selectable", "sink_handling": "selectable"},
"PCA-C-19": {"model_family": "selectable", "high_suitability_threshold": "selectable"},
"PCA-C-20": {"slope_aspect_rules": "selectable", "score_normalization": "selectable"},
}

def main():
    d = json.load(open(V1, encoding="utf-8"))
    rows = {r["task_id"]: r for r in d["rows"]}
    diffs = []
    def rec(tid, field, old, new, basis, impact):
        diffs.append({"task_id": tid, "field": field, "old": old, "new": new,
                      "basis": basis, "scoring_code_impact": impact})

    # ---- F2: task texts ----
    for tid, (old, new) in TEXT_PATCH.items():
        r = rows[tid]
        assert old in r["task_text"], tid
        r["task_text"] = r["task_text"].replace(old, new)
        r["task_sha256"] = hashlib.sha256(r["task_text"].encode()).hexdigest()
        rec(tid, "task_text", old[:70] + "...", new[:70] + "...",
            "round-14: 'stated' wording promised unavailable parameters -> selectable declaration semantics",
            "scoring checks DECLARATION of the choice, never a specific value")

    # ---- F2: parameter_availability everywhere ----
    for tid, r in rows.items():
        r["parameter_availability"] = PAV[tid]
        # C-group rows carry no external reference; evidence = the task's own text
        r["evidence"] = "task_text (freshly drafted C-group task; gold derived from this text only; no reference chain exists)"
    rec("ALL", "parameter_availability", None,
        "machine field on all 20 rows (values: selectable | selectable_with_declaration | selectable_with_suitability_statement)",
        "round-14 caliber unification",
        "scoring must check declaration/status per field; value-guessing never scored")

    # ---- F1: gold-consistency patches ----
    r = rows["PCA-C-01"]
    r["acceptable_alternatives"] = [
        "Area-proportional allocation of raster totals to building footprints (a total-allocation method that directly estimates building population)",
        "Centroid/point sampling of density values ONLY as a proxy estimate with an explicitly declared footprint-area assumption — conditional route, NOT unconditionally equivalent to allocation"]
    rec("PCA-C-01", "acceptable_alternatives",
        "centroid sampling listed as unconditionally equivalent",
        "centroid demoted to conditional proxy route requiring declared area assumption",
        "centroid density != building total without an area assumption",
        "proxy routes score as declared-assumption routes; omission of the assumption is the scorable defect")

    r = rows["PCA-C-03"]
    r["cell_note"] = ("coverage_cell describes INPUT structure (two fused sources); task_type describes the "
                      "analytic domain (terrain) — the two dimensions are independent by design")
    r["required_constraints"] = [c for c in r["required_constraints"]]
    r["failure_conditions"] = ["Reaches without slope values", "No downstream-order identifier present",
                               "Slope computed off-channel"]
    r["underdetermined_aspects"] = ["Ordering convention (strahler vs simple flow direction) — multiple valid, must be stated"]
    rec("PCA-C-03", "failure_conditions + cell_note",
        "'No downstream ordering' ambiguous vs specific algorithm; cell/type apparent mismatch unexplained",
        "failure requires the IDENTIFIER only (algorithm free); cell-vs-type independence documented",
        "identifier presence is task-required; the ordering algorithm never was",
        "failure predicate = identifier presence check, no algorithm match")

    r = rows["PCA-C-05"]
    r["required_constraints"] = [c if "continent" not in c.lower() else
        "[EXPLICIT] per-continent totals (continent-boundary source named by the model, or its absence declared as a required external input)"
        for c in r["required_constraints"]]
    r["failure_conditions"] = ["Naive pixel mean reported as area-weighted",
                               "Per-continent totals missing without declaring the continent layer as a required external input",
                               "Reprojection to non-equal-area CRS"]
    rec("PCA-C-05", "failure_conditions",
        "'Continents undefined/missing' penalized while continent data was never provided or required",
        "missing totals fail only if the model neither names a source nor declares the data requirement",
        "a declared data need is valid planning behavior",
        "failure predicate = missing output AND missing declaration (two-condition check)")

    r = rows["PCA-C-09"]
    r["failure_conditions"] = ["Points without valid raster values dropped silently",
                               "Class column absent", "Row count != point count"]
    rec("PCA-C-09", "failure_conditions",
        "'stored as raw code without mapping' was a hard failure",
        "raw-code class column accepted; name mapping demoted to optional presentation",
        "task requires the class value, not a name mapping",
        "mapping presence no longer scored; absence never a failure")

    r = rows["PCA-C-13"]
    r["failure_conditions"] = ["Checks run before repair",
                               "Issue types collapsed into one column without distinction",
                               "Attribute rule neither applied (when its threshold is provided) nor its missing threshold declared as a clarification requirement"]
    rec("PCA-C-13", "failure_conditions",
        "'Attribute rule ignored' forced use of a threshold the task never supplied",
        "apply-or-declare rule: applying a provided threshold OR declaring the missing threshold both pass",
        "'e.g., area below a minimum' was an example, not a supplied value",
        "failure predicate = neither-apply-nor-declare")

    r = rows["PCA-C-14"]
    r["failure_conditions"] = ["Samples with missing data silently assigned a tier",
                               "Tier boundaries applied to a variable other than the one stated",
                               "Confidence column absent",
                               "Tiers assigned without applying provided thresholds or declaring their absence as a clarification requirement"]
    rec("PCA-C-14", "failure_conditions", "same forced-threshold defect as C-13",
        "apply-or-declare rule", "task text did not contain the threshold values",
        "failure predicate = neither-apply-nor-declare")

    r = rows["PCA-C-17"]
    r["audit_note"] = ("Scoring note (round-14): the model MAY explicitly state its rural baseline, summer "
                       "months, and ranking statistic; stated choices are scored as declared assumptions. "
                       "Hard requirements are limited to: urban/rural differential structure, ranking output, "
                       "intensity raster.")
    rec("PCA-C-17", "audit_note", None,
        "baseline/seasons/statistic = declared-assumption scoring; hard items limited to structure",
        "task text defines none of those three values",
        "judge scores declaration presence; never compares to a specific baseline")

    r = rows["PCA-C-19"]
    r["failure_conditions"] = ["Model built but suitability never mapped",
                               "Coverage split not reported",
                               "High-suitability threshold applied without any stated basis or declared assumption"]
    rec("PCA-C-19", "failure_conditions",
        "'Threshold undefined and arbitrary' penalized the absence of a unique value the task never gave",
        "penalize only the absence of a stated basis/declared assumption for whatever threshold is used",
        "threshold is selectable by design",
        "failure predicate = basis/assumption missing, not value mismatch")

    r = rows["PCA-C-06"]
    r["acceptable_alternatives"] = ["Common CRS chosen WITH a stated length-distortion suitability note "
                                    "(equal-area CRSs distort length; conformal/equidistant choices preferred for length work)",
                                    "Any seam-dedup strategy for duplicated boundary features (stated)"]
    rec("PCA-C-06", "acceptable_alternatives",
        "'any common CRS (stated)' treated all CRSs as equivalent",
        "suitability statement for length work required",
        "length measurement validity depends on distortion properties",
        "missing suitability note is a declared-assumption defect, not auto-fail of the whole plan")

    r = rows["PCA-C-10"]
    r["failure_conditions"] = ["Density computed without true areas (naive pixel count)",
                               "Flagging without applying the provided threshold or declaring a self-stated one",
                               "Zone totals double-counted across boundary pixels"]
    rec("PCA-C-10", "failure_conditions", "'Flag threshold ignored' forced an unsupplied value",
        "apply-or-declare rule", "threshold selectable by design",
        "failure predicate = neither-apply-nor-declare")

    r = rows["PCA-C-12"]
    r["failure_conditions"] = ["Dominant class ties unresolved without note",
                               "Shares not summing to ~100% over VALID land-cover pixels without declaring exclusions (NoData / boundary / unclassified pixels legitimately reduce the sum; a naive all-pixel 100% is not required)",
                               "Diversity missing"]
    rec("PCA-C-12", "failure_conditions", "'Shares not summing to 100%' ignored the valid-pixel denominator",
        "~100% over valid pixels with declared exclusions",
        "NoData/boundary/unclassified pixels legitimately reduce totals",
        "failure predicate = unexplained deviation, not exact 100%")

    r = rows["PCA-C-18"]
    r["required_constraints"] = [c.replace("[IMPLICIT] hydrological conditioning before accumulation",
        "[IMPLICIT] DEM hydrological state assessed; conditioning applied AS NEEDED (no specific conditioning operator mandated)")
        for c in r["required_constraints"]]
    rec("PCA-C-18", "required_constraints",
        "conditioning implied one specific mandatory treatment",
        "condition-as-needed per DEM state; no operator mandated",
        "appropriate preprocessing depends on the DEM, not on a fixed recipe",
        "no specific conditioning operator scored as required")

    # ---- F3: pairing revisions ----
    d2_meta = dict(d["_meta"])
    d2_meta["revision"] = ("v2 per owner round-14: F1 gold-consistency (8 rows), F2 stated-parameter "
                           "caliber (text wording + parameter_availability on all rows), F3 single-item fixes")
    v1_sha = hashlib.sha256(json.dumps(d, sort_keys=True).encode()).hexdigest()[:16]
    d2_meta["supersedes_sha_prefix"] = "18aace83f9af72fc"
    payload = {"_meta": d2_meta, "rows": [rows[r["task_id"]] for r in d["rows"]]}
    blob = json.dumps(payload, ensure_ascii=False, indent=1)
    open(OUT, "w", encoding="utf-8", newline="").write(blob)
    print("rows:", len(payload["rows"]), "| new sha:", hashlib.sha256(blob.encode()).hexdigest()[:16])
    json.dump(diffs, open(OUT.replace(".json", "_diffs.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    print("diff records:", len(diffs))

if __name__ == "__main__":
    main()
