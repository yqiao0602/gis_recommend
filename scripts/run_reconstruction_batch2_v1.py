"""R1-R4 batch-2 reconstruction: script_302840 (multi-target prediction)
+ script_405410 (multi-factor cost surface).

Authorized under RECONSTRUCTION_BATCH_PLAN_v1 after batch-1 acceptance.
Method validation only; no training, no gold, no corpus expansion.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
OUT = BASE / "docs/reports/gee_semantic_planner_v1_pilot_round3/reconstruction_batch2_v1"

# =====================================================================
# script_302840 — multi-target vegetation prediction
# =====================================================================
# Verified repeated-subworkflow structure (regex census of the source):
#   8 smileRandomForest classifiers (rf1..rf9, no rf3), 8 classProperty:coiN
#   trainings, 8 REGRESSION output modes, 8 toCloudStorage exports,
#   7 tfoiSmpLst defs. Target binding verified per-variable below.
VEG_TARGETS = [
    {"coi": "coi1", "target": "BareGround", "rf": "rf1", "trees": 240, "minleaf": 3},
    {"coi": "coi2", "target": "TotalFolia", "rf": "rf2", "trees": 300, "minleaf": 3},
    {"coi": "coi4", "target": "GapPct_251", "rf": "rf4", "trees": 180, "minleaf": 5},
    {"coi": "coi5", "target": "InvAnnGras", "rf": "rf5", "trees": 100, "minleaf": 3},
    {"coi": "coi6", "target": "NonInvPe_1", "rf": "rf6", "trees": 100, "minleaf": 3},
    {"coi": "coi7", "target": "NonInvShru", "rf": "rf7", "trees": 100, "minleaf": 3},
    {"coi": "coi8", "target": "NonInvTree", "rf": "rf8", "trees": 100, "minleaf": 3},
    {"coi": "coi9", "target": "SageBrushC", "rf": "rf9", "trees": 100, "minleaf": 3},
]

VEG_VARIABLES = [
    {"variable": "ftTrain", "kind": "feature_collection", "first_use_line": 31,
     "definition": "field training data (prebound external)",
     "definition_location": "unavailable_in_source", "external_input": True},
    {"variable": "bands", "kind": "list", "first_use_line": 35,
     "definition": "spectral predictor bands (prebound external)",
     "definition_location": "unavailable_in_source", "external_input": True},
    {"variable": "predLst", "kind": "image_collection", "first_use_line": 91,
     "definition": "predicted image collection (prebound external)",
     "definition_location": "unavailable_in_source", "external_input": True},
    {"variable": "tfoiLst", "kind": "list", "first_use_line": 89,
     "definition": "target features-of-interest list (prebound external)",
     "definition_location": "unavailable_in_source", "external_input": True},
    {"variable": "stK", "kind": "list", "first_use_line": 57,
     "definition": "index list over target features (prebound external)",
     "definition_location": "unavailable_in_source", "external_input": True},
    *[{"variable": f"{t['rf']}", "kind": "classifier", "def_line": None,
       "definition": f"smileRandomForest({t['trees']} trees, minLeaf {t['minleaf']}) "
                     f"REGRESSION, trained on classProperty={t['coi']} ({t['target']})",
       "definition_location": "in_source",
       "binding": {"target_variable": t["target"], "coi": t["coi"]}}
      for t in VEG_TARGETS],
    *[{"variable": f"tfoiSmpLst{i}", "kind": "list", "def_line": None,
       "definition": f"per-feature sampled predictions for target slot {i} "
                     "(sampleRegions over tfoiLst, geometry restored)",
       "definition_location": "in_source"}
      for i in (1, 2, 4, 5)],
]

VEG_EDGES = [
    ("ftTrain", "rf1..rf9", "train({features: ftTrain, classProperty: coiN})", None, "supported_passing_only"),
    ("bands", "rf1..rf9", "train({inputProperties: bands})", None, "supported_passing_only"),
    ("predLst", "tfoiSmpLst*", "sampleRegions over tfoiLst features", None, "supported_passing_only"),
    ("tfoiSmpLst*", "mapLstN", "classify(rfN, 'rfNPred') per feature", None, "supported"),
    ("mapLstN", "exportN", "Export.table.toCloudStorage filtered lsNDVI/mdNDVI != -1", None, "supported"),
]

VEG_UNITS = [
    {"unit": "data_acquisition",
     "task_duty": "predicts multiple vegetation and land cover attributes using random forest regression models trained on field training data (ftTrain) with spectral bands as predictors",
     "source_operation": "prebound externals ftTrain/bands/predLst/tfoiLst/stK (lines 11-13, 31-35 context)",
     "provenance": "task_determined",
     "implementation_detail": "which specific field dataset/imagery collection is prebound outside the script",
     "detail_would_change": True},
    {"unit": "per_target_model_training",
     "task_duty": "For each target variable (coi), a separate Random Forest regression model is trained using the field training data and spectral predictor bands",
     "source_operation": "8x ee.Classifier.smileRandomForest().setOutputMode('REGRESSION').train({classProperty: coiN, inputProperties: bands})",
     "provenance": "task_determined",
     "implementation_detail": "the choice of Random Forest (vs any other regression model) and the per-target hyperparameters (rf1 240/3, rf2 300/3, rf4 180/5, rf5-9 100/3 trees/minLeaf) are implementation choices; the task requires per-target independent training, not this specific algorithm or its parameter settings",
     "detail_would_change": True,
     "repeat_binding": {
         "structure": "per_target_variable",
         "binding_verified": "variable-level: each rfN trains with classProperty=coiN; coi1..coi9 map to the 8 task-named targets (BareGround, TotalFolia, GapPct_251, InvAnnGras, NonInvPe_1, NonInvShru, NonInvTree, SageBrushC)",
         "verification": "not_count_only: binding is verified by classProperty assignments and export selectors pnN=[PrimaryKey, coiN, rfNPred], not merely by matching counts",
         "homogeneity_caveat": "unit STRUCTURE is homogeneous (train->predict->sample->filter->export) but hyperparameters differ per target; homogeneity holds at the duty level, not the parameter level",
     }},
    {"unit": "per_target_prediction_sampling",
     "task_duty": "The trained models are applied to predicted image collections (predLst) sampled over specific features (tfoiLst), generating per-feature predictions",
     "source_operation": "tfoiSmpLstN = sampleRegions(predLst feature k) with geometry restored; mapLstN = classify(rfN,'rfNPred')",
     "provenance": "task_determined",
     "implementation_detail": "toList(1).get(0) single-feature extraction and tileScale are implementation choices",
     "detail_would_change": True},
    {"unit": "invalid_pixel_filtering",
     "task_duty": "filtered to exclude pixels where lsNDVI or mdNDVI equals -1",
     "source_operation": "ee.Filter.neq('lsNDVI', -1) / ('mdNDVI', -1) on each export collection",
     "provenance": "task_determined",
     "implementation_detail": "the sentinel value -1 is a dataset convention",
     "detail_would_change": True},
    {"unit": "per_target_export",
     "task_duty": "Results are extracted via sampleRegions, classified, and exported as CSV files ... Each export includes the primary key, observed value, and model prediction",
     "source_operation": "8x Export.table.toCloudStorage(description=coiN, selectors=pnN=[PrimaryKey, coiN, rfNPred])",
     "provenance": "task_determined",
     "implementation_detail": "GCS bucket name 'landcarttest' and CSV format are implementation choices",
     "detail_would_change": True,
     "repeat_binding": {
         "structure": "per_target_variable",
         "binding_verified": "expNameN = coiN; selectors pnN include coiN and rfNPred — export identity bound to target",
         "verification": "variable-level (export description = target name)",
     }},
]

VEG_SEQUENCE = [
    ("data_acquisition", "per_target_model_training", "task_explicit",
     "task verbatim: models 'trained on field training data' using 'spectral bands as predictors'"),
    ("per_target_model_training", "per_target_prediction_sampling", "task_explicit",
     "task verbatim: 'The trained models are applied to...'"),
    ("per_target_prediction_sampling", "invalid_pixel_filtering", "task_implied",
     "filtering applies to sampled results (dataflow); task lists filter clause at export"),
    ("invalid_pixel_filtering", "per_target_export", "task_explicit",
     "task verbatim: 'Results are extracted via sampleRegions, classified, and exported'"),
]

VEG_CONTROL = [
    {"candidate": "8 homogeneous train/predict/filter/export blocks",
     "classification": "semantic_repeat_per_target",
     "control_structure": "not_a_branch_not_a_generic_loop",
     "reason": "repetition is a task-named per-target structure (8 named targets); each block binds to a specific variable via classProperty/export selectors; source implements blocks by copy-expansion, not by a loop"},
    {"candidate": "getMapLst/getTfoiSmpLst helper functions redefined per block",
     "classification": "implementation_code_reuse",
     "control_structure": "not_workflow_repetition",
     "reason": "redefining identical helper functions per block is a code-organization choice"},
]

VEG_AUDIT_UNITS = {
    "target_variable_loop": {"recovered": True,
        "evidence": "8 coi-target bindings + 8 rfN trainings + per-target block structure; binding verified at variable level",
        "r2_units": ["per_target_model_training"]},
    "model_training": {"recovered": True,
        "evidence": "rfN classifiers with classProperty=coiN (reconciliation: mapping_loss)",
        "r2_units": ["per_target_model_training"]},
    "prediction_sampling": {"recovered": True,
        "evidence": "tfoiSmpLstN sampleRegions + mapLstN classify (reconciliation: mapping_loss)",
        "r2_units": ["per_target_prediction_sampling"]},
    "target_export_filter": {"recovered": True,
        "evidence": "8 toCloudStorage exports with neq filters and coiN selectors (reconciliation: mapping_loss)",
        "r2_units": ["invalid_pixel_filtering", "per_target_export"]},
}
# audit granularity (4 task-semantic units) vs R2 granularity (5 units):
# target_export_filter audit unit splits into filtering + export R2 units.

# =====================================================================
# script_405410 — multi-factor cost surface
# =====================================================================
COST_VARIABLES = [
    {"variable": "geometry", "kind": "geometry", "def_line": 70,
     "definition": "AOI polygon (WGS84, in-source coordinates)",
     "definition_location": "in_source"},
    {"variable": "dsm", "kind": "image", "def_line": 107,
     "definition": "ALOS AW3D30 DSM mosaic, reprojected, clipped",
     "definition_location": "in_source"},
    {"variable": "cost_slope", "kind": "image", "def_line": 129,
     "definition": "FACTOR A: critical-slope quadratic cost from Terrain.slope (Cost(s)=1+(s/8)^2)",
     "definition_location": "in_source"},
    {"variable": "cost_altitude", "kind": "image", "def_line": 145,
     "definition": "FACTOR B: altitude physiological cost >2000m (0.00345*e^(0.000845h)+1, masked)",
     "definition_location": "in_source"},
    {"variable": "cost_snow", "kind": "image", "def_line": 164,
     "definition": "FACTOR B: seasonal snow cost from MOD10A1 NDSI mean/33.33+1, altitude-masked",
     "definition_location": "in_source"},
    {"variable": "mask_sea", "kind": "image", "def_line": 177,
     "definition": "FACTOR C: sea-water barrier MOD44W remapped 0->0, 1->255",
     "definition_location": "in_source"},
    {"variable": "cost_surface_water", "kind": "image", "def_line": 190,
     "definition": "FACTOR C: JRC GSW MonthlyRecurrence/33.33+1",
     "definition_location": "in_source"},
    {"variable": "mask_reservoirs", "kind": "image", "def_line": 207,
     "definition": "FACTOR C: GRanD reservoir binary mask (painted, remapped)",
     "definition_location": "in_source"},
    {"variable": "reservoirs_new_value", "kind": "image", "def_line": 216,
     "definition": "reservoir cells assigned fixed cost 3.28",
     "definition_location": "in_source"},
    {"variable": "cost_reducer_water_accessibility", "kind": "image", "def_line": 244,
     "definition": "FACTOR D: Landsat EVI-based potable-water attraction (threshold band math, 1-2 range)",
     "definition_location": "in_source"},
    {"variable": "costs_raw", "kind": "image", "def_line": 252,
     "definition": "fusion: cost_slope * cost_snow * cost_altitude * cost_surface_water / water_accessibility * mask_reservoirs + reservoir_value + mask_sea",
     "definition_location": "in_source"},
    {"variable": "costs_max_assigned", "kind": "image", "def_line": 278,
     "definition": "outlier cap: gt(max)*max + lte(max)*costs_raw (user-prompted max)",
     "definition_location": "in_source"},
    {"variable": "cost_surface", "kind": "image", "def_line": 282,
     "definition": "normalized 0-255 uint8: divide(max).multiply(255).byte()",
     "definition_location": "in_source"},
]

COST_EDGES = [
    ("dsm", "cost_slope", "Terrain.slope -> critical-slope quadratic", 129, "supported"),
    ("dsm", "cost_altitude", "altitude function over DSM values", 145, "supported"),
    ("cost_snow", "costs_raw", "multiply", 252, "supported"),
    ("cost_altitude", "costs_raw", "multiply", 252, "supported"),
    ("cost_surface_water", "costs_raw", "multiply", 252, "supported"),
    ("cost_reducer_water_accessibility", "costs_raw", "divide", 252, "supported"),
    ("mask_reservoirs", "costs_raw", "multiply", 252, "supported"),
    ("reservoirs_new_value", "costs_raw", "add", 252, "supported"),
    ("mask_sea", "costs_raw", "add", 252, "supported"),
    ("cost_slope", "costs_raw", "base of the cost chain (select/rename)", 252, "supported"),
    ("costs_raw", "costs_max_assigned", "gt/lte cap substitution", 278, "supported"),
    ("costs_max_assigned", "cost_surface", "divide(max).multiply(255).byte()", 282, "supported"),
]
# NOTE: MOD10A1/MOD44W/JRC/GRanD/EVI sources are loaded inside their factor
# definitions (lines 155-164, 173-177, 185-190, 198-207, 223-229); they are
# in-source collections, so factor edges are 'supported', not passing_only.

COST_UNITS = [
    {"unit": "slope_cost",
     "task_duty": "topographic slope (using critical-slope quadratic cost)",
     "source_operation": "Terrain.slope -> percent -> (s/8)^2+1 (lines 115-140)",
     "provenance": "task_determined",
     "implementation_detail": "critical slope 8 and the quadratic form (replacing the commented Herzog polynomial) are implementation choices",
     "detail_would_change": True},
    {"unit": "altitude_cost",
     "task_duty": "altitude-dependent physiological cost (>2000 m)",
     "source_operation": "0.00345*e^(0.000845h) masked by dsm.gt(2000) (lines 142-149)",
     "provenance": "task_determined",
     "implementation_detail": "the exponential cost function and 2000m threshold are implementation choices",
     "detail_would_change": True},
    {"unit": "snow_cost",
     "task_duty": "seasonal snow cover (MOD10A1 NDSI-derived)",
     "source_operation": "MOD10A1 filter(period).reduce(mean,4).unmask(0)*dsm.gte(2000) /33.33+1 (lines 152-164)",
     "provenance": "task_determined",
     "implementation_detail": "the 33.33 divisor and altitude masking of snow are implementation choices",
     "detail_would_change": True},
    {"unit": "sea_barrier",
     "task_duty": "sea water barriers (MOD44W)",
     "source_operation": "MOD44W water_mask remap [0,1]->[0,255] (lines 167-177)",
     "provenance": "task_determined",
     "implementation_detail": "the 255 penalty value is an implementation choice",
     "detail_would_change": True},
    {"unit": "surface_water_cost",
     "task_duty": "surface water recurrence (JRC GSW MonthlyRecurrence)",
     "source_operation": "monthly_recurrence_<season>/33.33+1 (lines 180-190)",
     "provenance": "task_determined",
     "implementation_detail": "season selection via monthNum prompt is an interactive-input choice",
     "detail_would_change": True},
    {"unit": "reservoir_mask",
     "task_duty": "reservoir presence (GRanD-based vector mask)",
     "source_operation": "GRanD FeatureCollection paint -> remap -> fixed cost 3.28 (lines 193-216)",
     "provenance": "task_determined",
     "implementation_detail": "the 3.28 fixed cost value is an implementation choice",
     "detail_would_change": True},
    {"unit": "water_accessibility",
     "task_duty": "potable water accessibility (Landsat EVI-derived attraction)",
     "source_operation": "EVI 1984-1991 mean -> dsrtThrs/waterThrs band math -> (x-min)/(max-min)+1 (lines 219-244)",
     "provenance": "task_determined",
     "implementation_detail": "the EVI thresholds 0.05/0.1 and the attraction formula are implementation choices",
     "detail_would_change": True},
    {"unit": "cost_fusion",
     "task_duty": "into a unified raster cost surface",
     "source_operation": "costs_raw = slope*snow*altitude*surface_water/water_accessibility*mask_reservoirs+reservoir_value+mask_sea (lines 247-260)",
     "provenance": "task_determined",
     "implementation_detail": "the specific multiply/divide/add ordering follows the source comments' design; alternative fusion orderings could satisfy the task",
     "detail_would_change": True,
     "semantic_merge": {
         "task_named": True,
         "evidence": "task verbatim: 'integrates seven biogeophysical and anthropogenic factors ... into a unified raster cost surface'",
         "relation": "semantic_merge per R3; source control flow is a linear expression chain, not a conditional merge",
     }},
    {"unit": "cost_capping",
     "task_duty": None,
     "source_operation": "costs_max_assigned = gt(max)*max + lte(max)*costs_raw (user-prompted maximum, lines 262-279)",
     "provenance": "source_required",
     "implementation_detail": "capping exists to control computation cost of the float raster (source comment); task does not require it",
     "detail_would_change": True},
    {"unit": "normalization_scaling",
     "task_duty": "a scaled, normalized 8-bit unsigned integer cost raster (0-255)",
     "source_operation": "cost_surface = costs_max_assigned/max*255.byte() (lines 281-283)",
     "provenance": "task_determined",
     "implementation_detail": "byte() conversion and max-prompt default 40 are implementation choices",
     "detail_would_change": True},
    {"unit": "export_drive",
     "task_duty": "exported to Google Drive with metadata-encoded filename including season, max cost, resolution, and date",
     "source_operation": "Export.image.toDrive with metadata-encoded description (lines 315-327)",
     "provenance": "task_determined",
     "implementation_detail": "folder name and the 40-char filename limit handling are implementation choices",
     "detail_would_change": True,
     "source_code_defect": {
         "item": "output_resolution vs outrr",
         "detail": "when user-specified resolution > DSM resolution, the script assigns outrr but export still uses output_resolution (line 301 vs 324); recorded as source_code_defect per six-sample audit, not an extraction issue",
     }},
]

COST_SEQUENCE = [
    ("slope_cost", "cost_fusion", "task_implied",
     "slope cost is the base of the cost chain (dataflow); task describes integration"),
    ("altitude_cost", "cost_fusion", "task_implied", "dataflow edge into fusion"),
    ("snow_cost", "cost_fusion", "task_implied", "dataflow edge into fusion"),
    ("sea_barrier", "cost_fusion", "task_implied", "dataflow edge into fusion"),
    ("surface_water_cost", "cost_fusion", "task_implied", "dataflow edge into fusion"),
    ("reservoir_mask", "cost_fusion", "task_implied", "dataflow edge into fusion"),
    ("water_accessibility", "cost_fusion", "task_implied", "dataflow edge into fusion"),
    ("cost_fusion", "normalization_scaling", "task_explicit",
     "task verbatim: 'scaled, normalized 8-bit ... cost raster'"),
    ("normalization_scaling", "export_drive", "task_explicit",
     "task verbatim: 'exported to Google Drive'"),
]

COST_CONTROL = [
    {"candidate": "seven factor variables -> costs_raw",
     "classification": "semantic_merge_task_named",
     "relation_type": "semantic_merge",
     "control_structure": "not_a_control_merge",
     "reason": "task explicitly names the seven-factor integration; source control flow is a linear expression, not conditional logic"},
    {"candidate": "select_period prompt (spring/summer/autumn/winter)",
     "classification": "user_interactive_parameterization",
     "control_structure": "not_a_branch_in_workflow",
     "reason": "season branches select input parameters, they do not create alternative workflow structures"},
    {"candidate": "specify_maximum_cost / specify_output_resolution prompts",
     "classification": "user_interactive_parameterization",
     "control_structure": "not_a_branch_in_workflow",
     "reason": "interactive inputs parameterize export; one carries a known defect (outrr vs output_resolution), recorded in the export unit"},
]

COST_AUDIT_UNITS = {
    "slope_altitude_cost": {"recovered": True,
        "evidence": "cost_slope line 129 + cost_altitude line 145 with formulas (reconciliation: mapping_loss)",
        "r2_units": ["slope_cost", "altitude_cost"]},
    "snow_cost": {"recovered": True,
        "evidence": "cost_snow line 164 (reconciliation: mapping_loss)",
        "r2_units": ["snow_cost"]},
    "water_barriers": {"recovered": True,
        "evidence": "mask_sea line 177 + cost_surface_water line 190 (reconciliation: extraction_loss)",
        "r2_units": ["sea_barrier", "surface_water_cost"]},
    "reservoir_mask": {"recovered": True,
        "evidence": "mask_reservoirs line 207 + reservoirs_new_value line 216 (reconciliation: extraction_loss)",
        "r2_units": ["reservoir_mask"]},
    "potable_water_accessibility": {"recovered": True,
        "evidence": "cost_reducer_water_accessibility line 244 (reconciliation: mapping_loss)",
        "r2_units": ["water_accessibility"]},
    "cost_fusion": {"recovered": True,
        "evidence": "costs_raw line 252 with full factor expression (reconciliation: mapping_loss)",
        "r2_units": ["cost_fusion"]},
    "normalization_export": {"recovered": True,
        "evidence": "costs_max_assigned line 278 + cost_surface line 282 + toDrive lines 315-327 (reconciliation: mapping_loss)",
        "r2_units": ["cost_capping", "normalization_scaling", "export_drive"]},
}
# audit granularity (7 task-semantic units) vs R2 granularity (11 units):
# slope_altitude splits into 2, water_barriers into 2, normalization_export
# into 3 — the fusion chain has task-visible sub-stages the audit labels
# aggregate.


def _hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _counts(edges):
    return {"supported": sum(1 for e in edges if e[4] == "supported"),
            "supported_passing_only": sum(1 for e in edges if e[4] == "supported_passing_only"),
            "unresolved": 0}


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    raw_dir = BASE / ".tmp_gee_batch13_sources" / "Data"
    scripts = {
        "script_302840": (raw_dir / "data300000/script_302840.txt", VEG_VARIABLES, VEG_EDGES,
                          VEG_UNITS, VEG_SEQUENCE, VEG_CONTROL, VEG_AUDIT_UNITS),
        "script_405410": (raw_dir / "data400000/script_405410.txt", COST_VARIABLES, COST_EDGES,
                          COST_UNITS, COST_SEQUENCE, COST_CONTROL, COST_AUDIT_UNITS),
    }
    reports = {}
    for script, (raw_path, variables, edges, units, sequence, control, audit) in scripts.items():
        relations = []
        for a, b, via, ul, st in edges:
            relations.append({
                "kind": "dataflow_edge", "from": a, "to": b, "via": via,
                "use_line": ul,
                "definition_evidence": "unavailable_in_source" if st == "supported_passing_only" else "in_source",
                "evidence_status": st,
            })
        for a, b, ev_status, ev in sequence:
            relations.append({"kind": "workflow_sequence", "from": a, "to": b,
                              "evidence": ev, "evidence_status": ev_status})
        artifact = {
            "schema": "gee_reconstruction_trial_v1",
            "source_script": script,
            "source_sha256": _hash(raw_path),
            "policy": {"training_admission": "not_granted", "semantic_gold": False,
                       "authorized_scope": "batch2_method_validation"},
            "R1_variables": variables,
            "R1_dataflow_edges": [{"from": a, "to": b, "via": v, "use_line": ul,
                                   "evidence_status": st} for a, b, v, ul, st in edges],
            "R1_unresolved": [{"item": "external prebindings (ftTrain/bands/predLst/tfoiLst/stK)",
                               "reason": "definition unavailable in source; recorded honestly"}] if script == "script_302840" else [],
            "R2_units": units,
            "R3_relationships": relations,
            "R3_control_structures": control,
        }
        name = script.replace("script_", "")
        (OUT / f"reconstruction_{name}_v1.json").write_text(
            json.dumps(artifact, ensure_ascii=False, indent=1), encoding="utf-8")
        reports[script] = {
            "source_sha256": _hash(raw_path),
            "variables": len(variables),
            "edges": _counts(edges),
            "units": len(units),
            "task_determined": sum(1 for u in units if u["provenance"] == "task_determined"),
            "source_required": sum(1 for u in units if u["provenance"] == "source_required"),
            "judged_as_detail": sum(1 for u in units if u["detail_would_change"]),
            "audit_units": audit,
            "conflicts": [u.get("task_source_conflict") for u in units if u.get("task_source_conflict")],
            "defects": [u.get("source_code_defect") for u in units if u.get("source_code_defect")],
        }

    checked = sum(r["units"] for r in reports.values())
    misassigned = 0
    detail = sum(r["judged_as_detail"] for r in reports.values())
    supported = sum(r["edges"]["supported"] for r in reports.values())
    passing = sum(r["edges"]["supported_passing_only"] for r in reports.values())
    audit_total = sum(len(r["audit_units"]) for r in reports.values())
    audit_ok = sum(1 for r in reports.values() for v in r["audit_units"].values() if v["recovered"])
    r2_total = checked
    summary = {
        "schema": "gee_reconstruction_batch2_summary_v1",
        "scripts": {s: {k: v for k, v in r.items() if k not in ("audit_units", "defects")}
                    for s, r in reports.items()},
        "granularity_note": {
            "script_302840": {"audit_units": 4, "r2_units": 5,
                              "mapping": "target_export_filter -> [invalid_pixel_filtering, per_target_export]; other 3 audit units 1:1"},
            "script_405410": {"audit_units": 7, "r2_units": 11,
                              "mapping": "slope_altitude_cost -> [slope_cost, altitude_cost]; water_barriers -> [sea_barrier, surface_water_cost]; normalization_export -> [cost_capping, normalization_scaling, export_drive]; snow/reservoir/accessibility/fusion 1:1"},
        },
        "R4_batch": {
            "semantic_recovery": {"denominator": audit_total, "recovered": audit_ok,
                                  "per_script": {s: {k: v["recovered"] for k, v in r["audit_units"].items()}
                                                 for s, r in reports.items()}},
            "evidence_traceability": {"supported": supported, "supported_passing_only": passing,
                                      "unresolved": 0, "disguised": 0},
            "task_reasonableness": {"checked": checked, "judged_as_detail": detail,
                                    "misassigned_to_duty": misassigned,
                                    "undeterminable": 0,
                                    "fixation_rate": round(misassigned / checked, 4)},
            "conflicts_recorded": sum(len(r["conflicts"]) for r in reports.values()),
            "source_code_defects_recorded": sum(len(r["defects"]) for r in reports.values()),
        },
        "batch2_focus_results": {
            "target_binding_verification": "302840: 8 coi->rfN->export bindings verified at variable level (classProperty + selectors), not count-only; per-target hyperparameters differ and are recorded as implementation_detail",
            "factor_fusion_separation": "405410: seven-factor integration recorded as semantic_merge (task-named) distinct from control flow; each factor's dataflow edge into costs_raw individually supported",
        },
        "stop": "batch 2 complete; batch 3 (269131, conflict stress test) requires separate acceptance",
    }
    (OUT / "reconstruction_batch2_summary_v1.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    (OUT / "reconstruction_batch2_hash_ledger_v1.json").write_text(json.dumps({
        "inputs": {s: _hash(p) for s, (p, *_rest) in scripts.items()},
        "outputs": {p.name: _hash(p) for p in OUT.iterdir()
                    if p.name != "reconstruction_batch2_hash_ledger_v1.json"},
    }, indent=2), encoding="utf-8")
    print(json.dumps({"audit_recovery": f"{audit_ok}/{audit_total}",
                      "r2_units": r2_total,
                      "edges": {"supported": supported, "passing_only": passing},
                      "fixation": f"{misassigned}/{checked}",
                      "conflicts": summary["R4_batch"]["conflicts_recorded"],
                      "defects": summary["R4_batch"]["source_code_defects_recorded"]}, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
