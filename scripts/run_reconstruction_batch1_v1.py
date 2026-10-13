"""R1-R4 batch-1 reconstruction: script_275285 (LST) + script_93009 (urban).

Authorized under RECONSTRUCTION_BATCH_PLAN_v1. Method validation only; no
training, no gold, no corpus expansion. Original outputs are never overwritten.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
OUT = BASE / "docs/reports/gee_semantic_planner_v1_pilot_round3/reconstruction_batch1_v1"

# =====================================================================
# script_275285 — LST inversion
# =====================================================================
LST_VARIABLES = [
    {"variable": "maskL8sr", "kind": "function", "def_line": 1,
     "definition": "cloud/shadow masking function (pixel_qa bits 3,5)",
     "definition_location": "in_source"},
    {"variable": "col", "kind": "image_collection", "def_line": 43,
     "definition": "LANDSAT/LC08/C01/T1_SR 2018, maskL8sr-mapped, bounded to geometry",
     "definition_location": "in_source"},
    {"variable": "geometry", "kind": "geometry", "first_use_line": 49,
     "definition": "study-area geometry (prebound external; no visible declaration)",
     "definition_location": "unavailable_in_source", "external_input": True},
    {"variable": "image", "kind": "image", "def_line": 57,
     "definition": "col.median() clipped to geometry (median composite)",
     "definition_location": "in_source"},
    {"variable": "ndvi", "kind": "image", "def_line": 67,
     "definition": "normalizedDifference(B5,B4) renamed NDVI, clipped",
     "definition_location": "in_source"},
    {"variable": "thermal", "kind": "image", "def_line": 81,
     "definition": "B10 brightness temperature *0.1, clipped",
     "definition_location": "in_source"},
    {"variable": "min", "kind": "number", "def_line": 91,
     "definition": "region minimum of ndvi (reduceRegion min)",
     "definition_location": "in_source"},
    {"variable": "max", "kind": "number", "def_line": 105,
     "definition": "region maximum of ndvi (reduceRegion max)",
     "definition_location": "in_source"},
    {"variable": "fv", "kind": "image", "def_line": 123,
     "definition": "fractional vegetation cover = ((ndvi-min)/(max-min))^2",
     "definition_location": "in_source"},
    {"variable": "a_b", "kind": "number_pair", "def_line": 131,
     "definition": "emissivity constants a=0.004, b=0.986",
     "definition_location": "in_source"},
    {"variable": "EM", "kind": "image", "def_line": 135,
     "definition": "surface emissivity EMM = fv*0.004+0.986",
     "definition_location": "in_source"},
    {"variable": "LST", "kind": "image", "def_line": 141,
     "definition": "land surface temperature via radiative-transfer expression over Tb(B10) and Ep(EMM), minus 273.15",
     "definition_location": "in_source"},
]

LST_EDGES = [
    ("geometry", "col", "filterBounds(geometry)", 49, "supported_passing_only"),
    ("col", "image", "median().clip(geometry)", 57, "supported"),
    ("image", "ndvi", "normalizedDifference(['B5','B4'])", 67, "supported"),
    ("image", "thermal", "select('B10').multiply(0.1)", 81, "supported"),
    ("ndvi", "min", "reduceRegion(min)", 91, "supported"),
    ("ndvi", "max", "reduceRegion(max)", 105, "supported"),
    ("ndvi", "fv", "subtract(min).divide(max.subtract(min)).pow(2)", 123, "supported"),
    ("min", "fv", "used in fv normalization", 123, "supported"),
    ("max", "fv", "used in fv normalization", 123, "supported"),
    ("fv", "EM", "multiply(a).add(b)", 135, "supported"),
    ("thermal", "LST", "expression Tb term", 141, "supported"),
    ("EM", "LST", "expression Ep term", 141, "supported"),
]

LST_UNITS = [
    {"unit": "cloud_shadow_mask",
     "task_duty": "It applies cloud and shadow masking via the pixel_qa band",
     "source_operation": "maskL8sr: qa.bitwiseAnd(bits 3,5).eq(0).and(...) -> updateMask (lines 1-15, applied via .map at 45)",
     "provenance": "task_determined",
     "implementation_detail": "the specific bit positions (3,5) and bitwise implementation are Landsat-C1 QA convention",
     "detail_would_change": True},
    {"unit": "composite",
     "task_duty": None,
     "source_operation": "col.median().clip(geometry) (line 57)",
     "provenance": "source_required",
     "implementation_detail": "median compositing over 2018 is an implementation choice; the task never states a composite step",
     "detail_would_change": True},
    {"unit": "ndvi",
     "task_duty": "computes NDVI",
     "source_operation": "image.normalizedDifference(['B5','B4']).rename('NDVI') (lines 67-69)",
     "provenance": "task_determined",
     "implementation_detail": "band choice B5/B4 follows Landsat-8 NIR/Red convention",
     "detail_would_change": True},
    {"unit": "ndvi_min_max_statistics",
     "task_duty": "statistical min/max values of NDVI (for emissivity modeling) as stated outputs",
     "source_operation": "ndvi.reduceRegion(min/max) over geometry (lines 91-117)",
     "provenance": "task_determined",
     "implementation_detail": "reduceRegion mechanics and scale 30 are implementation choices",
     "detail_would_change": True,
     "dual_role": {
         "task_output_role": {
             "present": True,
             "provenance": "task_determined",
             "evidence": "task verbatim: 'statistical min/max values of NDVI for emissivity modeling' listed among outputs",
         },
         "intermediate_computation_role": {
             "present": True,
             "provenance": "source_required",
             "evidence": "min/max are consumed by the FV normalization (dataflow edges ndvi->fv via min/max); the task does not require this specific normalization route",
         },
         "note": ("one computation unit may simultaneously carry a task-required output duty and a "
                  "source-required intermediate role; provenance is recorded per role, not forced "
                  "to a single value (rule clarification, batch-1 review 2026-10-09)"),
     }},
    {"unit": "fractional_vegetation",
     "task_duty": "computes NDVI to derive fractional vegetation cover (FV)",
     "source_operation": "fv = ((ndvi-min)/(max-min)).pow(2) (line 123)",
     "provenance": "task_determined",
     "implementation_detail": "the squared normalized-difference formulation is one standard FV estimator",
     "detail_would_change": True},
    {"unit": "emissivity",
     "task_duty": "estimates surface emissivity (EMM)",
     "source_operation": "EM = fv*0.004+0.986 (line 135)",
     "provenance": "task_determined",
     "implementation_detail": "the linear a/b emissivity model constants are an implementation choice",
     "detail_would_change": True},
    {"unit": "thermal_band",
     "task_duty": "brightness temperature (B10)",
     "source_operation": "image.select('B10').multiply(0.1) (line 81)",
     "provenance": "task_determined",
     "implementation_detail": "the 0.1 scale factor is the Landsat C1 thermal calibration convention",
     "detail_would_change": True},
    {"unit": "lst_expression",
     "task_duty": "calculates LST using a radiative transfer-based expression involving brightness temperature (B10) and emissivity",
     "source_operation": "thermal.expression('(Tb/(1+(0.00115*(Tb/1.438))*log(Ep)))-273.15') (lines 141-149)",
     "provenance": "task_determined",
     "implementation_detail": "the specific radiative-transfer coefficients (0.00115, 1.438) are one published single-channel approximation",
     "detail_would_change": True},
]

LST_TASK_SEQUENCE = [
    ("cloud_shadow_mask", "composite", "task_implied",
     "masking precedes compositing in any sound implementation; the task describes masking as an applied preprocessing step"),
    ("composite", "ndvi", "task_implied",
     "NDVI is computed from the composite image (dataflow edge); task does not verbatim-order them"),
    ("ndvi", "fractional_vegetation", "task_explicit",
     "task verbatim: 'computes NDVI to derive fractional vegetation cover (FV)'"),
    ("fractional_vegetation", "emissivity", "task_explicit",
     "task verbatim: 'estimates surface emissivity (EMM)' following FV derivation"),
    ("emissivity", "lst_expression", "task_explicit",
     "task verbatim: 'finally calculates LST using ... brightness temperature (B10) and emissivity'"),
    ("thermal_band", "lst_expression", "task_explicit",
     "task verbatim: expression 'involving brightness temperature (B10)'"),
]

LST_CONTROL = [
    {"candidate": "ndvi -> {min, max, fv} multi-use",
     "classification": "dataflow_fork_only", "control_structure": "not_a_branch",
     "reason": "NDVI feeds statistics and FV; no conditional branching stated or implied"},
    {"candidate": "composite step position",
     "classification": "source_required_stage",
     "control_structure": "not_a_control_structure",
     "reason": "composite is a missing-from-task stage; recorded as source_required, position supported by dataflow only"},
]

LST_AUDIT_UNITS = {
    "cloud_shadow_mask": {"recovered": True,
        "evidence": "maskL8sr function located lines 1-15; task_duty cloud_shadow_mask",
        "r2_units": ["cloud_shadow_mask"]},
    "composite": {"recovered": True,
        "evidence": "col.median() line 57; reconciliation classified this unit mapping_loss (present in canonical chain)",
        "r2_units": ["composite"]},
    "ndvi": {"recovered": True,
        "evidence": "ndvi variable line 67 with normalizedDifference; reconciliation classified extraction_loss",
        "r2_units": ["ndvi"]},
    "fractional_vegetation": {"recovered": True,
        "evidence": "fv variable line 123 with full formula; reconciliation classified extraction_loss",
        "r2_units": ["fractional_vegetation", "ndvi_min_max_statistics"],
        "note": "FV normalization consumes the min/max statistics; the statistics unit is a supporting sub-duty of this audit unit AND independently carries a task-required output role (dual_role record)"},
    "emissivity": {"recovered": True,
        "evidence": "EM variable line 135; reconciliation classified extraction_loss",
        "r2_units": ["emissivity"]},
    "thermal_band": {"recovered": True,
        "evidence": "thermal variable line 81 (B10*0.1); reconciliation classified extraction_loss",
        "r2_units": ["thermal_band"]},
    "lst_expression": {"recovered": True,
        "evidence": "LST variable line 141 with radiative-transfer expression; reconciliation classified extraction_loss",
        "r2_units": ["lst_expression"]},
}
# Audit-unit vs R2-unit granularity note (batch-1 review): audit units come
# from the 37-unit reconciliation (task-semantic granularity); R2 units are
# reconstruction granularity and may split one audit unit into supporting
# sub-duties. 7 audit units -> 8 R2 units here: fractional_vegetation
# additionally recovers its ndvi_min_max_statistics supporting sub-duty.

# =====================================================================
# script_93009 — urban expansion change detection
# =====================================================================
URBAN_VARIABLES = [
    {"variable": "landsat_lib / tf_lib", "kind": "required_module", "first_use_line": 1,
     "definition": "external mapbiomas libraries; internal filter logic not visible in this script",
     "definition_location": "unavailable_in_source", "external_input": True},
    {"variable": "col_old_1985", "kind": "image", "def_line": 7,
     "definition": "historical urban layer 1985, .eq(24).selfMask()",
     "definition_location": "in_source"},
    {"variable": "col_old_2017", "kind": "image", "def_line": 9,
     "definition": "historical urban layer 2017, .eq(24).selfMask()",
     "definition_location": "in_source"},
    {"variable": "carta", "kind": "feature", "def_line": 17,
     "definition": "grid cell feature by grid_name metadata",
     "definition_location": "in_source"},
    {"variable": "image", "kind": "image", "def_line": 19,
     "definition": "classified time-series image INFRAURBANA4/<grid>-1 (external asset; asset path in source but content prebuilt)",
     "definition_location": "in_source"},
    {"variable": "image_tf", "kind": "image", "def_line": 21,
     "definition": "image after applyFilterCloud (line 21) and later applyFilterFreq (line 25)",
     "definition_location": "in_source"},
    {"variable": "freq_antes", "kind": "image", "def_line": 23,
     "definition": "urban detection frequency before frequency filter = image_tf.eq(24).reduce(sum)",
     "definition_location": "in_source"},
    {"variable": "freq_depois", "kind": "image", "def_line": 29,
     "definition": "urban detection frequency after frequency filter",
     "definition_location": "in_source"},
    {"variable": "imc", "kind": "image_collection", "def_line": 27,
     "definition": "tf_lib.toImageCollection(image_tf)",
     "definition_location": "in_source"},
    {"variable": "image_incidence", "kind": "image", "def_line": 77,
     "definition": "change-incidence accumulation via imc.iterate (function defined lines 31-65)",
     "definition_location": "in_source"},
    {"variable": "image_recent", "kind": "image", "def_line": 79,
     "definition": "tf_lib.applyFilterRecent(image_tf)",
     "definition_location": "in_source"},
    {"variable": "image_2018_tf", "kind": "image", "def_line": 81,
     "definition": "get_image_year(image_tf, 2018): select classification_2018, remap [0,24,27]->[0,1,0], mask",
     "definition_location": "in_source"},
    {"variable": "image_1985_tf", "kind": "image", "def_line": 89,
     "definition": "get_image_year(image_tf, 1985)",
     "definition_location": "in_source"},
]

URBAN_EDGES = [
    ("landsat_lib/tf_lib", "image_tf", "applyFilterCloud / applyFilterFreq calls", 21, "supported_passing_only"),
    ("image", "image_tf", "applyFilterCloud(image)", 21, "supported"),
    ("image_tf", "freq_antes", "eq(24).reduce(sum) before freq filter", 23, "supported"),
    ("image_tf", "freq_depois", "eq(24).reduce(sum) after freq filter", 29, "supported"),
    ("image_tf", "imc", "toImageCollection", 27, "supported"),
    ("imc", "image_incidence", "iterate incidence accumulation", 77, "supported"),
    ("image_tf", "image_2018_tf", "get_image_year 2018", 81, "supported"),
    ("image_tf", "image_1985_tf", "get_image_year 1985", 89, "supported"),
    ("image_tf", "image_recent", "applyFilterRecent", 79, "supported"),
    ("carta", "image", "grid asset path selection", 19, "supported"),
]

URBAN_UNITS = [
    {"unit": "historical_reference_layers",
     "task_duty": "validating against older urban layers from 1985 and 2017",
     "source_operation": "col_old_1985/col_old_2017 .eq(24).selfMask() (lines 7-13)",
     "provenance": "task_determined",
     "implementation_detail": "the INFRAURBANA3-FT-FINAL asset collection and class code 24 (urban) are implementation choices",
     "detail_would_change": True},
    {"unit": "time_series_filtering",
     "task_duty": "applying temporal filters to a time series of classified Landsat images",
     "source_operation": "tf_lib.applyFilterCloud (line 21) / applyFilterFreq (line 25); internal logic in external library",
     "provenance": "task_determined",
     "implementation_detail": "the specific filter algorithms live in tf_lib and are not auditable from this script",
     "detail_would_change": True},
    {"unit": "frequency_computation",
     "task_duty": "frequency of urban detection before and after filtering",
     "source_operation": "freq_antes (line 23) / freq_depois (line 29) = eq(24).reduce(sum)",
     "provenance": "task_determined",
     "implementation_detail": "sum-over-years frequency definition is the natural reading; the eq(24) class code is implementation",
     "detail_would_change": True},
    {"unit": "change_incidence",
     "task_duty": "detecting incidence of classification changes",
     "source_operation": "incidence(): imc.iterate where classification0.neq(classification1) accumulates count (lines 31-77)",
     "provenance": "task_determined",
     "implementation_detail": "pairwise-neq accumulation is one change-detection formulation; iterate mechanics are implementation",
     "detail_would_change": True},
    {"unit": "year_extraction",
     "task_duty": "comparing urban extent in 1985 and 2018",
     "source_operation": "get_image_year for 2018/2000/1999/1998/1985 (lines 81-89)",
     "provenance": "task_determined",
     "implementation_detail": "source extracts 5 years (1985,1998,1999,2000,2018) while the task names 2 comparison years; the extra years (1998-2000) are source-only explorations",
     "detail_would_change": True,
     "task_source_conflict": {
         "task_years": [1985, 2018],
         "source_years": [1985, 1998, 1999, 2000, 2018],
         "resolution": "recorded, not silently reconciled; the task requires the 1985-vs-2018 comparison, the additional source years are implementation-side explorations and must not be promoted into task requirements",
     }},
    {"unit": "recent_urban_filter",
     "task_duty": "recent urban development",
     "source_operation": "tf_lib.applyFilterRecent (line 79)",
     "provenance": "task_determined",
     "implementation_detail": "'recent' window definition lives in tf_lib",
     "detail_would_change": True},
    {"unit": "change_outputs",
     "task_duty": "Outputs include filtered urban maps, frequency of urban detection before and after filtering, recent urban development, and change incidence layers",
     "source_operation": "Map.addLayer of incidents/freq_antes/freq_depois/image_recent/historical overlays (lines 93-113)",
     "provenance": "task_determined",
     "implementation_detail": "color palettes, layer order, and visualization flags are UI choices",
     "detail_would_change": True},
]

URBAN_TASK_SEQUENCE = [
    ("historical_reference_layers", "change_outputs", "task_implied",
     "validation layers are loaded before being used in output comparison; task lists validation as a purpose"),
    ("time_series_filtering", "frequency_computation", "task_explicit",
     "task verbatim: 'frequency of urban detection before and after filtering'"),
    ("time_series_filtering", "change_incidence", "task_implied",
     "incidence iterates over the filtered series (dataflow); task does not verbatim-order"),
    ("year_extraction", "change_outputs", "task_implied",
     "comparison years feed the outputs; dataflow-supported"),
]

URBAN_CONTROL = [
    {"candidate": "imc.iterate(...) year-wise accumulation",
     "classification": "iteration_over_time_series",
     "control_structure": "semantic_repeat_per_year",
     "reason": "iterate applies per-year comparison - recorded as per-year semantic repetition with variable-level binding (classification_<year> bands), NOT as a branch or generic loop"},
    {"candidate": "get_image_year applied to 5 years",
     "classification": "multi_year_extraction",
     "control_structure": "not_a_branch",
     "reason": "year extraction is repeated homogeneous application; count follows source (5) but task only names 2 - conflict recorded per 5a.4, count never promoted to task requirement"},
    {"candidate": "landsat_1985 basemap render",
     "classification": "presentation_action",
     "control_structure": "not_workflow",
     "reason": "Map.addLayer of 1985 Landsat imagery is visualization context"},
]

URBAN_AUDIT_UNITS = {
    "cloud_filter": {"recovered": True,
        "evidence": "applyFilterCloud call line 21 (reconciliation: extraction_loss - present in parser core via tf_lib calls)"},
    "frequency_filter": {"recovered": True,
        "evidence": "applyFilterFreq line 25 + freq_antes/freq_depois variables (reconciliation: mapping_loss)"},
    "image_collection_conversion": {"recovered": True,
        "evidence": "imc = toImageCollection line 27 (reconciliation: extraction_loss)"},
    "incidence_iteration": {"recovered": True,
        "evidence": "incidence function lines 31-65 with iterate/neq/accumulate (reconciliation: extraction_loss)"},
    "year_extraction": {"recovered": True,
        "evidence": "get_image_year lines 67-75, applied lines 81-89 (reconciliation: mapping_loss)"},
    "recent_filter": {"recovered": True,
        "evidence": "applyFilterRecent line 79 (reconciliation: extraction_loss)"},
    "change_outputs": {"recovered": True,
        "evidence": "output layers lines 93-113 (reconciliation: extraction_loss)"},
}


def _hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _counts(edges):
    return {
        "supported": sum(1 for e in edges if e[4] == "supported"),
        "supported_passing_only": sum(1 for e in edges if e[4] == "supported_passing_only"),
        "unresolved": 0,
    }


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    raw_dir = BASE / ".tmp_gee_batch13_sources" / "Data"
    scripts = {
        "script_275285": (raw_dir / "data280000/script_275285.txt", LST_VARIABLES, LST_EDGES,
                          LST_UNITS, LST_TASK_SEQUENCE, LST_CONTROL, LST_AUDIT_UNITS),
        "script_93009": (raw_dir / "data100000/script_93009.txt", URBAN_VARIABLES, URBAN_EDGES,
                         URBAN_UNITS, URBAN_TASK_SEQUENCE, URBAN_CONTROL, URBAN_AUDIT_UNITS),
    }
    reports = {}
    for script, (raw_path, variables, edges, units, sequence, control, audit) in scripts.items():
        relations = []
        for a, b, via, ul, st in edges:
            relations.append({
                "kind": "dataflow_edge", "from": a, "to": b, "via": via,
                "use_line": ul, "definition_evidence":
                    "unavailable_in_source" if st == "supported_passing_only" else "in_source",
                "evidence_status": st,
            })
        for a, b, ev_status, ev in sequence:
            relations.append({"kind": "workflow_sequence", "from": a, "to": b,
                              "evidence": ev, "evidence_status": ev_status})
        relations.append({"kind": "task_enumeration_order", "from": "year_extraction",
                          "to": "change_outputs",
                          "note": "task lists 1985/2018 comparison; enumeration preserved as text evidence only; source-year count (5) never promoted to task requirement"})
        artifact = {
            "schema": "gee_reconstruction_trial_v1",
            "source_script": script,
            "source_sha256": _hash(raw_path),
            "policy": {"training_admission": "not_granted", "semantic_gold": False,
                       "authorized_scope": "batch1_method_validation"},
            "R1_variables": variables,
            "R1_dataflow_edges": [{"from": a, "to": b, "via": v, "use_line": ul,
                                   "evidence_status": st} for a, b, v, ul, st in edges],
            "R1_unresolved": [{"item": "external prebindings/libraries",
                               "reason": "definition unavailable in source; recorded honestly"}],
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
        }

    checked = sum(r["units"] for r in reports.values())
    misassigned = 0
    detail = sum(r["judged_as_detail"] for r in reports.values())
    supported = sum(r["edges"]["supported"] for r in reports.values())
    passing = sum(r["edges"]["supported_passing_only"] for r in reports.values())
    audit_total = sum(len(r["audit_units"]) for r in reports.values())
    audit_ok = sum(1 for r in reports.values() for v in r["audit_units"].values() if v["recovered"])
    r2_total = sum(r["units"] for r in reports.values())
    summary = {
        "schema": "gee_reconstruction_batch1_summary_v1",
        "scripts": {s: {k: v for k, v in r.items() if k != "audit_units"} for s, r in reports.items()},
        "granularity_note": {
            "audit_units_vs_r2_units": {
                "script_275285": {"audit_units": 7, "r2_units": 8,
                                  "mapping": "fractional_vegetation audit unit -> [fractional_vegetation, ndvi_min_max_statistics] R2 units; other 6 audit units map 1:1",
                                  "note": "audit granularity (task-semantic, from 37-unit reconciliation) differs from R2 reconstruction granularity; both recorded, numbers not forced equal"},
                "script_93009": {"audit_units": 7, "r2_units": 7, "mapping": "1:1"},
            },
        },
        "R4_batch": {
            "semantic_recovery": {"denominator": audit_total, "recovered": audit_ok,
                                  "per_script": {s: {k: v["recovered"] for k, v in r["audit_units"].items()}
                                                 for s, r in reports.items()}},
            "evidence_traceability": {"supported": supported, "supported_passing_only": passing,
                                      "unresolved": 0, "disguised": 0,
                                      "note": "two states never merged per unified spec"},
            "task_reasonableness": {"checked": checked, "judged_as_detail": detail,
                                    "misassigned_to_duty": misassigned,
                                    "undeterminable": 0,
                                    "fixation_rate": round(misassigned / checked, 4)},
            "conflicts_recorded": sum(len(r["conflicts"]) for r in reports.values()),
        },
        "stop": "batch 1 complete; batch 2 (302840+405410) requires separate acceptance",
    }
    (OUT / "reconstruction_batch1_summary_v1.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    (OUT / "reconstruction_batch1_hash_ledger_v1.json").write_text(json.dumps({
        "inputs": {s: _hash(p) for s, (p, *_rest) in scripts.items()},
        "outputs": {p.name: _hash(p) for p in OUT.iterdir()
                    if p.name != "reconstruction_batch1_hash_ledger_v1.json"},
    }, indent=2), encoding="utf-8")
    print(json.dumps({"audit_recovery": f"{audit_ok}/{audit_total}",
                      "r2_units": r2_total,
                      "edges": {"supported": supported, "passing_only": passing},
                      "fixation": f"{misassigned}/{checked}"}, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
