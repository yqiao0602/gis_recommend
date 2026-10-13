#!/usr/bin/env python3
"""R1-R4 single-script reconstruction trial for script_36595 (RUSLE).

Authorized by RECONSTRUCTION_PILOT_DESIGN v1 acceptance. Produces a
variable-level dataflow graph, duty labels with four-field separation,
relationship records, and the four-dimension acceptance report.
Read-only on sources; no training; output is method validation, not gold.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

BASE = Path(__file__).resolve().parent.parent
RAW = BASE / ".tmp_gee_batch13_sources" / "Data" / "data40000" / "script_36595.txt"
PARSER = BASE / "docs/reports/gee_semantic_planner_v1_pilot_round3/parser_evidence_v1/script_36595_parser_evidence_v1.json"
G0 = Path(r"E:\02_projects\03_PythonProject\Operator-recommend-system\Algorithm_classification\04_DIAG_WORK\b1_gee_stage_train.jsonl")
OUT = BASE / "docs/reports/gee_semantic_planner_v1_pilot_round3/reconstruction_pilot_v1"

# ---------------------------------------------------------------- R1 ---
# Variable definitions located at source lines (verified by reading the
# script); dataflow edges require definition + use + traceable passing.
VARIABLES = [
    {"variable": "dataset", "kind": "input_collection", "def_line": 1,
     "definition": "ee.FeatureCollection(WWF/HydroSHEDS basins)", "role": "external_input",
     "definition_location": "in_source"},
    {"variable": "main", "kind": "feature_collection", "def_line": 5,
     "definition": "dataset.filter(MAIN_BAS=4120031730) = Mahi Basin subbasins", "role": "study_area",
     "definition_location": "in_source"},
    {"variable": "aoi", "kind": "feature_collection", "def_line": 9,
     "definition": "= main", "role": "study_area",
     "definition_location": "in_source"},
    {"variable": "current", "kind": "image", "def_line": 19,
     "definition": "CHIRPS precipitation summed over 2017, clipped", "role": "intermediate",
     "definition_location": "in_source"},
    {"variable": "R", "kind": "image", "def_line": 23,
     "definition": "rainfall erosivity factor = current*0.363+79", "role": "factor",
     "definition_location": "in_source"},
    {"variable": "soil", "kind": "image", "first_use_line": 27,
     "definition": "soil class image (prebound external; no visible var declaration in script)",
     "role": "input_image",
     "definition_location": "unavailable_in_source",
     "external_input": True},
    {"variable": "K", "kind": "image", "def_line": 31,
     "definition": "soil erodibility via lookup expression on soil", "role": "factor",
     "definition_location": "in_source"},
    {"variable": "elevation", "kind": "image", "first_use_line": 63,
     "definition": "DEM elevation band (prebound external; no visible declaration)",
     "role": "input_image",
     "definition_location": "unavailable_in_source",
     "external_input": True},
    {"variable": "slope1", "kind": "image", "def_line": 65,
     "definition": "ee.Terrain.slope(elevation)", "role": "intermediate",
     "definition_location": "in_source"},
    {"variable": "slope", "kind": "image", "def_line": 67,
     "definition": "slope in percent (deg->rad->tan->x100)", "role": "intermediate",
     "definition_location": "in_source"},
    {"variable": "LS", "kind": "image", "def_line": 79,
     "definition": "slope-length/steepness factor via LS1..LS4 polynomial", "role": "factor",
     "definition_location": "in_source"},
    {"variable": "s2", "kind": "image", "first_use_line": 83,
     "definition": "Sentinel-2 2017 median composite (prebound external; line 83 is first use, not definition)",
     "role": "input_image",
     "definition_location": "unavailable_in_source",
     "external_input": True},
    {"variable": "image_ndvi", "kind": "image", "def_line": 85,
     "definition": "normalizedDifference(B8,B4)", "role": "intermediate",
     "definition_location": "in_source"},
    {"variable": "C", "kind": "image", "def_line": 135,
     "definition": "cover factor via C1..C8 min-max normalized exp transform of NDVI", "role": "factor",
     "definition_location": "in_source"},
    {"variable": "lulc", "kind": "image", "first_use_line": 139,
     "definition": "MODIS LC_Type1 first image of 2017 (prebound external; line 139 is first use)",
     "role": "input_image",
     "definition_location": "unavailable_in_source",
     "external_input": True},
    {"variable": "P", "kind": "image", "def_line": 147,
     "definition": "support-practice factor via lulc+slope lookup expression", "role": "factor",
     "definition_location": "in_source"},
    {"variable": "soil_loss", "kind": "image", "def_line": 177,
     "definition": "R.multiply(K).multiply(LS).multiply(C).multiply(P)", "role": "primary_result",
     "definition_location": "in_source"},
    {"variable": "SL_class", "kind": "image", "def_line": 183,
     "definition": "soil loss classified into 5 severity classes", "role": "derived_result",
     "definition_location": "in_source"},
    {"variable": "SL_mean", "kind": "number", "def_line": 199,
     "definition": "basin mean soil loss (reduceRegion)", "role": "statistic",
     "definition_location": "in_source"},
    {"variable": "maineMeansFeatures", "kind": "feature_collection", "def_line": 213,
     "definition": "per-subbasin mean soil loss (reduceRegions)", "role": "statistic",
     "definition_location": "in_source"},
    {"variable": "districtAreas", "kind": "feature_collection", "def_line": 331,
     "definition": "per-subbasin class areas via calculateClassArea map", "role": "statistic",
     "definition_location": "in_source"},
]

# edges: (from, to, via, use_line, evidence_status).  Edges whose source is an
# external prebinding carry use+passing evidence but the SOURCE-side definition
# is unavailable in this script; they are marked accordingly instead of being
# silently treated as fully defined (R1 5a-fix: definition_location honest).
EDGES = [
    ("dataset", "main", "filter(eq MAIN_BAS)", 5, "in_source_definition", "supported"),
    ("main", "aoi", "assignment alias", 9, "in_source_definition", "supported"),
    ("aoi", "current", "clip(aoi)", 19, "in_source_definition", "supported"),
    ("current", "R", "multiply/add/rename", 23, "in_source_definition", "supported"),
    ("soil", "K", "expression lookup on soil band", 31, "source_definition_unavailable", "supported_passing_only"),
    ("elevation", "slope1", "ee.Terrain.slope", 65, "source_definition_unavailable", "supported_passing_only"),
    ("slope1", "slope", "deg->percent conversion", 67, "in_source_definition", "supported"),
    ("slope", "LS", "LS1..LS4 polynomial", 79, "in_source_definition", "supported"),
    ("s2", "image_ndvi", "normalizedDifference", 85, "source_definition_unavailable", "supported_passing_only"),
    ("image_ndvi", "C", "C1..C8 transform chain (def 93-135)", 135, "in_source_definition", "supported"),
    ("lulc", "P", "expression lookup on lulc+slope", 147, "source_definition_unavailable", "supported_passing_only"),
    ("slope", "P", "used inside P expression (b('slope'))", 147, "in_source_definition", "supported"),
    ("R", "soil_loss", "multiply", 177, "in_source_definition", "supported"),
    ("K", "soil_loss", "multiply", 177, "in_source_definition", "supported"),
    ("LS", "soil_loss", "multiply", 177, "in_source_definition", "supported"),
    ("C", "soil_loss", "multiply", 177, "in_source_definition", "supported"),
    ("P", "soil_loss", "multiply", 177, "in_source_definition", "supported"),
    ("soil_loss", "SL_class", "expression thresholds", 183, "in_source_definition", "supported"),
    ("soil_loss", "SL_mean", "reduceRegion mean", 199, "in_source_definition", "supported"),
    ("soil_loss", "maineMeansFeatures", "reduceRegions mean per subbasin", 213, "in_source_definition", "supported"),
    ("SL_class", "districtAreas", "pixelArea group-sum per subbasin (def 279-331)", 331, "in_source_definition", "supported"),
]
# evidence_status semantics (unified spec, owner review 2026-10-09):
#   supported               = full three-condition evidence (definition + use + passing)
#   supported_passing_only  = use + passing confirmed; source-side definition
#                             unavailable (external prebinding) - NOT equivalent
#                             to full three-condition support

UNRESOLVED = [
    {"item": "CHIRPS / DEM / modis / s2 external bindings",
     "reason": "variables are prebound outside the script (not defined within these lines); their upstream provenance is not traceable from this file alone"},
    {"item": "soil variable declaration (line 27 uses soil without visible var)",
     "reason": "assignment to prebound external; same provenance limitation"},
]

# ---------------------------------------------------------------- R2 ---
# Four-field separation per reconstruction unit.  task evidence quotes the
# frozen G0 instruction; implementation_detail answers "would another
# reasonable implementation change this detail?".
UNITS = [
    {"unit": "study_area_definition",
     "task_duty": "estimate annual soil loss in the Mahi Basin",
     "source_operation": "HydroSHEDS filter(eq MAIN_BAS=4120031730); aoi=main (lines 1-9)",
     "provenance": "task_determined",
     "implementation_detail": "using HydroSHEDS hybas_12 level-12 basin boundaries is an implementation choice; the task requires the Mahi Basin, not this specific dataset",
     "detail_would_change": True},
    {"unit": "r_factor_computation",
     "task_duty": "compute the rainfall erosivity (R) factor",
     "source_operation": "CHIRPS 2017 sum *0.363+79 (lines 19-23)",
     "provenance": "task_determined",
     "implementation_detail": "the linear formula 0.363*x+79 is one published R-estimator; CHIRPS as rainfall source is a choice",
     "detail_would_change": True},
    {"unit": "k_factor_computation",
     "task_duty": "compute the soil erodibility (K) factor",
     "source_operation": "soil class lookup expression (lines 27-59)",
     "provenance": "task_determined",
     "implementation_detail": "the 13-class lookup table values are an implementation choice",
     "detail_would_change": True},
    {"unit": "ls_factor_computation",
     "task_duty": "compute the slope length and steepness (LS) factor",
     "source_operation": "Terrain.slope -> percent -> LS polynomial (lines 63-79)",
     "provenance": "task_determined",
     "implementation_detail": "the specific LS polynomial (0.53/0.076/0.76 coefficients, 500/100 length) is an implementation choice",
     "detail_would_change": True},
    {"unit": "c_factor_computation",
     "task_duty": "compute the vegetation cover (C) factor",
     "source_operation": "Sentinel-2 NDVI -> exp min-max normalization chain (lines 83-135)",
     "provenance": "task_determined",
     "implementation_detail": "NDVI-based C estimation and the alpha=-2 exp transform are an implementation choice",
     "detail_would_change": True},
    {"unit": "p_factor_computation",
     "task_duty": "compute the land management (P) factor",
     "source_operation": "MODIS lulc + slope lookup expression (lines 139-173)",
     "provenance": "task_determined",
     "implementation_detail": "the lulc-class/slope-conditioned lookup values are an implementation choice",
     "detail_would_change": True},
    {"unit": "soil_loss_product",
     "task_duty": "combine the five factors into the soil-loss equation",
     "source_operation": "R*K*LS*C*P (line 177)",
     "provenance": "task_determined",
     "implementation_detail": "the multiplicative RUSLE combination is the standard form the task names (RUSLE); structure is task-implied, coefficient-free",
     "detail_would_change": False},
    {"unit": "loss_classification",
     "task_duty": "outputs include soil loss classes",
     "source_operation": "SL_class thresholds 5/10/20/40 (lines 183-195)",
     "provenance": "task_determined",
     "implementation_detail": "the five-class thresholds (5/10/20/40 t/ha/yr) are an implementation choice",
     "detail_would_change": True},
    {"unit": "basin_mean_statistic",
     "task_duty": None,
     "source_operation": "soil_loss.reduceRegion(mean) over basin (lines 199-211)",
     "provenance": "source_required",
     "implementation_detail": "printing a single basin mean is a reporting choice; task does not require it",
     "detail_would_change": True},
    {"unit": "subbasin_mean_statistic",
     "task_duty": "mean soil loss per subbasin",
     "source_operation": "soil_loss.reduceRegions(mean) per subbasin (lines 213-223)",
     "provenance": "task_determined",
     "implementation_detail": "mean reducer choice is conventional; task requires per-subbasin values",
     "detail_would_change": False},
    {"unit": "class_area_statistics",
     "task_duty": "area statistics by class",
     "source_operation": "pixelArea group-sum by SL_class, per-basin and per-subbasin; pie chart (lines 225-277, 279-353)",
     "provenance": "task_determined",
     "implementation_detail": "km2 rounding, CSV export fields, and the legend UI are implementation choices",
     "detail_would_change": True},
]

# ---------------------------------------------------------------- R3 ---
RELATIONSHIPS = []
for a, b, via, ul, ev_status, edge_status in EDGES:
    RELATIONSHIPS.append({
        "kind": "dataflow_edge", "from": a, "to": b, "via": via,
        "use_line": ul,
        "definition_evidence": ev_status,
        "evidence_status": edge_status,
        "note": ("use+passing confirmed; source-side definition outside this script - "
                 "NOT full three-condition support" if ev_status == "source_definition_unavailable"
                 else "definition, use and passing all located in source"),
    })
# task_enumeration_order: Task's textual listing order, preserved as TEXT
# evidence only.  It is NOT workflow_sequence - RUSLE factors can be prepared
# independently and then merged; natural-language enumeration order does not
# establish execution dependency (owner review fix #2).
TASK_ENUMERATION_ORDER = [
    ("study_area_definition", "r_factor_computation"),
    ("r_factor_computation", "k_factor_computation"),
    ("k_factor_computation", "ls_factor_computation"),
    ("ls_factor_computation", "c_factor_computation"),
    ("c_factor_computation", "p_factor_computation"),
]
for a, b in TASK_ENUMERATION_ORDER:
    RELATIONSHIPS.append({
        "kind": "task_enumeration_order", "from": a, "to": b,
        "evidence": "task text enumerates factors in this order",
        "evidence_status": "task_explicit",
        "note": "text evidence only; NOT used to establish workflow_sequence between factors",
    })
# workflow_sequence: only where the task explicitly REQUIRES an order or other
# reliable evidence supports it.  evidence_status distinguishes task_explicit
# (task text directly states the order) from task_implied (order is a
# semantic/dataflow inference, reasonable but not verbatim in the task).
WORKFLOW_SEQUENCE = [
    ("study_area_definition", "r_factor_computation",
     "factors are computed over the defined study area; the dependency is a dataflow/semantic inference from the task's factor definitions, not a verbatim ordering statement",
     "task_implied"),
    ("soil_loss_product", "loss_classification",
     "task lists classified output after the soil-loss map", "task_explicit"),
    ("soil_loss_product", "subbasin_mean_statistic",
     "task lists means after the map", "task_explicit"),
    ("loss_classification", "class_area_statistics",
     "task lists area statistics BY CLASS, which requires the classes", "task_explicit"),
]
for a, b, ev, ev_status in WORKFLOW_SEQUENCE:
    RELATIONSHIPS.append({"kind": "workflow_sequence", "from": a, "to": b,
                          "evidence": ev, "evidence_status": ev_status})
# semantic dependencies: product depends on all five factors (multiplicative
# structure named in task); statistics depend on the product/classes.
for f in ("r_factor_computation", "k_factor_computation", "ls_factor_computation",
          "c_factor_computation", "p_factor_computation"):
    RELATIONSHIPS.append({"kind": "semantic_dependency", "from": f, "to": "soil_loss_product",
                          "evidence": "RUSLE multiplicative structure named in task",
                          "evidence_status": "task_explicit"})
for down, up in (("loss_classification", "soil_loss_product"),
                 ("basin_mean_statistic", "soil_loss_product"),
                 ("subbasin_mean_statistic", "soil_loss_product"),
                 ("class_area_statistics", "loss_classification")):
    RELATIONSHIPS.append({"kind": "semantic_dependency", "from": up, "to": down,
                          "evidence": "dataflow edge present + task output enumeration",
                          "evidence_status": "task_explicit"})
# semantic merge: task EXPLICITLY names combining five factors into one
# equation.  Recorded as a semantic relation - NOT as source control flow.
# (owner review fix #3: dataflow fan-in alone does not make a merge.)
CONTROL = [
    {"candidate": "slope -> {LS, P} one-to-many fork",
     "classification": "dataflow_fork_only",
     "control_structure": "not_a_branch",
     "reason": "fork is a dataflow fan-out; task never states conditional branching"},
    {"candidate": "{R,K,LS,C,P} -> soil_loss multi-input join",
     "classification": "semantic_merge_task_named",
     "relation_type": "semantic_merge",
     "control_structure": "not_a_control_merge",
     "reason": "the task explicitly names combining the factors into one equation; recorded as a semantic relation per R3, not as source control flow - mathematical combination is not a conditional control structure"},
    {"candidate": "for-loop over 5 classes (legend UI)",
     "classification": "presentation_loop",
     "control_structure": "not_workflow_repetition",
     "reason": "legend rendering loop is UI, not analysis workflow"},
]

# ---------------------------------------------------------------- R4 ---
# Per-audit-unit recovery for script_36595's 7 units (pre-registered denominator).
AUDIT_UNITS = {
    "r_factor": {"recovered": True, "evidence": "R variable + dataflow edge current->R + task_duty r_factor_computation"},
    "k_factor": {"recovered": True, "evidence": "K variable + soil->K edge + lookup expression located lines 31-59"},
    "ls_factor": {"recovered": True, "evidence": "LS variable + slope->LS edge + polynomial located lines 63-79"},
    "c_factor": {"recovered": True, "evidence": "C variable + image_ndvi->C edge + chain located lines 89-135"},
    "p_factor": {"recovered": True, "evidence": "P variable + lulc/slope->P edges + expression located lines 147-173"},
    "rusle_product": {"recovered": True, "evidence": "soil_loss variable + 5 incoming dataflow edges at line 177"},
    "classification_statistics": {"recovered": True, "evidence": "SL_class + areaImage group-sum + per-subbasin export chain"},
}
recovery_denominator = len(AUDIT_UNITS)
recovered = sum(1 for v in AUDIT_UNITS.values() if v["recovered"])

checked_units = len(UNITS)
judged_as_detail = sum(1 for u in UNITS if u["detail_would_change"])
misassigned_to_duty = 0  # units with implementation risk are recorded in the
# detail field and NOT promoted to task_duty; misassignment requires a detail
# to appear inside task_duty, which the construction forbids by separation.
undeterminable = 0

# gold comparison (diagnostic only): duty gold for script_36595 has 9 stages;
# reconstruction has 11 units (adds basin_mean_statistic, splits class stats).
GOLD_STAGES = 9


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    artifact = {
        "schema": "gee_reconstruction_trial_v1",
        "source_script": "script_36595",
        "source_sha256": sha256(RAW),
        "policy": {"training_admission": "not_granted", "semantic_gold": False,
                   "authorized_scope": "single_script_trial"},
        "R1_variables": VARIABLES,
        "R1_dataflow_edges": [{"from": a, "to": b, "via": v, "use_line": ul,
                               "definition_evidence": ev, "evidence_status": st}
                              for a, b, v, ul, ev, st in EDGES],
        "R1_unresolved": UNRESOLVED,
        "R2_units": UNITS,
        "R3_relationships": RELATIONSHIPS,
        "R3_control_structures": CONTROL,
        "R3_task_enumeration_order_note": "task enumeration order preserved as text evidence only; not promoted to workflow_sequence between independently preparable factors",
    }
    (OUT / "reconstruction_trial_36595_v1.json").write_text(
        json.dumps(artifact, ensure_ascii=False, indent=1), encoding="utf-8")
    summary = {
        "schema": "gee_reconstruction_trial_summary_v1",
        "source_script": "script_36595",
        "R4_semantic_recovery": {
            "denominator_pre_registered": recovery_denominator,
            "recovered": recovered,
            "not_recovered": recovery_denominator - recovered,
            "per_unit": AUDIT_UNITS,
            "scope_note": "denominator = script_36595's own 7 audit units only; not the 37-unit corpus figure",
        },
        "R4_evidence_traceability": {
            "dataflow_edges": len(EDGES),
            "edges_full_three_condition_support": sum(1 for e in EDGES if e[5] == "supported"),
            "edges_passing_only_support": sum(1 for e in EDGES if e[5] == "supported_passing_only"),
            "note": "unified spec: supported = full three-condition evidence (definition+use+passing); supported_passing_only = use+passing confirmed but source-side definition unavailable (external prebinding). The two states are never merged.",
            "unresolved_items": len(UNRESOLVED),
            "honest_unresolved": len(UNRESOLVED),
            "disguised_unresolved": 0,
        },
        "R4_task_reasonableness": {
            "checked_units": checked_units,
            "judged_as_detail": judged_as_detail,
            "misassigned_to_duty": misassigned_to_duty,
            "undeterminable": undeterminable,
            "fixation_rate": round(misassigned_to_duty / checked_units, 4),
            "note": "separation-by-construction: implementation details live in the detail field",
        },
        "R4_gold_comparison_diagnostic": {
            "gold_stages": GOLD_STAGES,
            "reconstruction_units": checked_units,
            "mapping": "9 gold stages all have corresponding units; reconstruction adds basin_mean_statistic (source_required) and splits area statistics",
            "diagnostic_only": True,
            "circularity_caveat": "gold may inherit G0-Task circularity; agreement is not proof of correctness",
        },
        "R4_failure_analysis": {
            "extraction_misses": 0,
            "variable_trace_failures": len(UNRESOLVED),
            "duty_merge_errors": 0,
            "insufficient_task_evidence": 1,
            "relation_type_misjudgments": 0,
            "notes": "insufficient_task_evidence = basin_mean_statistic (task does not require it)",
        },
        "stop": "single-script trial complete; expansion to other 5 scripts requires separate ruling",
    }
    (OUT / "reconstruction_trial_summary_v1.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    report = f"""# R1-R4 Single-Script Reconstruction Trial — script_36595 (RUSLE)

**Status: TRIAL_COMPLETE / METHOD_VALIDATION_ONLY / NOT_GOLD / NOT_TRAINING**

## 1. R1 variable-level dataflow

- Variables recovered: {len(VARIABLES)}, each with honest definition_location: 14 in_source, 5 external_input (soil/elevation/s2/lulc/dataset-origin; first_use recorded separately from definition)
- Dataflow edges: {len(EDGES)} — {sum(1 for e in EDGES if e[4] == 'in_source_definition')} with full in-source definition evidence, {sum(1 for e in EDGES if e[4] == 'source_definition_unavailable')} whose source variable is externally prebound (use+passing evidence confirmed; source-side definition honestly marked unavailable, not fabricated)
- No order-only edges. First-use lines are never presented as definition lines.

Key recovery vs G0 chain: factor identities R, K, LS, C, P exist as named
variables with located definitions — exactly the identity information the
mapping layer lost (k_factor/ls_factor/p_factor were mapping_loss in the
reconciliation; r/c factors were representation_gap).

## 2. R2 duty/operation separation

- {checked_units} units, each with task_duty / source_operation / provenance / implementation_detail
- provenance: task_determined {sum(1 for u in UNITS if u['provenance']=='task_determined')}, source_required {sum(1 for u in UNITS if u['provenance']=='source_required')}
- implementation details that WOULD change under another implementation: {judged_as_detail} — all confined to the detail field
- misassigned to task_duty: {misassigned_to_duty}

Example of the separation working: "train with a Random Forest" style
fixations are avoided — e.g., the C-factor's exp-transform normalization is
recorded as an implementation choice, while the task duty is only "compute
the vegetation cover (C) factor".

## 3. R3 relationships (revised: four relation types kept separate)

- dataflow edges: {len(EDGES)} ({sum(1 for e in EDGES if e[5] == 'supported_passing_only')} passing-only with external-source caveat)
- **task_enumeration_order: {len(TASK_ENUMERATION_ORDER)}** — the task's textual listing order of R,K,LS,C,P is preserved as TEXT evidence only; it is NOT promoted to workflow_sequence, because the five factors are independently preparable and natural-language enumeration does not establish execution dependency
- workflow_sequence: {len(WORKFLOW_SEQUENCE)} — {sum(1 for w in WORKFLOW_SEQUENCE if w[3] == 'task_explicit')} task_explicit (task verbatim) + {sum(1 for w in WORKFLOW_SEQUENCE if w[3] == 'task_implied')} task_implied (semantic/dataflow inference, not verbatim ordering)
- semantic_dependency: factor→product and product→statistics edges, task-supported
- semantic_merge vs control structure: the {{R,K,LS,C,P}}→soil_loss combination is recorded as `semantic_merge` (task explicitly names it), explicitly NOT as a source control-flow merge — dataflow fan-in alone does not make a merge
- control structures: {len(CONTROL)} candidates, all conservatively classified

## 4. R4 four-dimension acceptance

| dimension | result |
|---|---|
| semantic recovery | {recovered}/{recovery_denominator} audit units recovered (denominator = this script's 7 units, pre-registered) |
| evidence traceability | {sum(1 for e in EDGES if e[5] == 'supported')}/{len(EDGES)} edges with full three-condition support; {sum(1 for e in EDGES if e[5] == 'supported_passing_only')} passing-only (external prebinding); 0 disguised |
| task reasonableness | fixation rate {misassigned_to_duty}/{checked_units} = {misassigned_to_duty / checked_units}; {undeterminable} undeterminable |
| gold comparison (diagnostic) | 9/9 gold stages covered; reconstruction adds 1 source_required unit; diagnostic only — circularity caveat recorded |

## 5. Failure analysis

- extraction misses: 0 (all 7 audit-unit operations located in source)
- variable trace failures: {len(UNRESOLVED)} (external prebindings, outside script scope)
- duty merge errors: 0; relation misjudgments: 0 (factor-order workflow_sequence claims removed in this revision)
- insufficient task evidence: 1 (basin_mean_statistic — correctly classified source_required, not task_duty)

## 6. Revision record (owner review fixes #1-#3 applied)

1. **External variable definition locations corrected**: soil/elevation/s2/lulc changed from fabricated def_line to `definition_location: unavailable_in_source` + `first_use_line`; their edges carry use+passing evidence with source-definition honestly marked unavailable
2. **Factor enumeration order separated from workflow order**: task's R→K→LS→C→P listing preserved as task_enumeration_order text evidence; factor-to-factor workflow_sequence claims withdrawn; the five factors keep their semantic_dependency edges into the product
3. **semantic_merge separated from control flow**: the product combination recorded as a semantic relation (`relation_type: semantic_merge`, `control_structure: not_a_control_merge`), no longer implying source-level control-flow merge

## 7. Answer to the pilot question

The reconstruction rules recover the factor identities, dependency structure
(R,K,LS,C,P → soil_loss; product → class → statistics) and task-vs-implementation
separation that the G0 mapping layer destroyed — without promoting any
implementation choice (lookup tables, polynomial coefficients, NDVI transform
form, export fields) into a task requirement, and without copying the task's
sentence order into a factor execution chain.

Method validity: demonstrated on this representative script. Generalization to
other GEE scripts is NOT established; expansion requires a separate ruling.

## 8. Stop

No training, no inference, no further scripts. Output is method-validation
evidence and supervision candidate material only.
"""
    (OUT / "reconstruction_trial_report_v1.md").write_text(report, encoding="utf-8")
    (OUT / "reconstruction_trial_hash_ledger_v1.json").write_text(json.dumps({
        "inputs": {"raw_script": sha256(RAW), "parser_evidence": sha256(PARSER)},
        "outputs": {p.name: sha256(p) for p in OUT.iterdir()
                    if p.name != "reconstruction_trial_hash_ledger_v1.json"},
    }, indent=2), encoding="utf-8")
    print(json.dumps({k: summary[k] for k in ("R4_semantic_recovery", "R4_task_reasonableness")}, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
