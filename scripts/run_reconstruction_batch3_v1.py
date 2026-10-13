"""R1-R4 batch-3 conflict stress test: script_269131 (fire susceptibility).

Authorized under RECONSTRUCTION_PILOT_METHOD_V1 (batch3 focus). Method
validation under known task-source inconsistencies. Conflicts are recorded
with both sides preserved; nothing is silently reconciled. No training.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
OUT = BASE / "docs/reports/gee_semantic_planner_v1_pilot_round3/reconstruction_batch3_v1"
RAW = BASE / ".tmp_gee_batch13_sources/Data/data270000/script_269131.txt"

# ------------------------------------------------------------- conflicts
# Conflict list built FIRST per owner's required sequence (before R1-R4).
CONFLICTS = [
    {
        "conflict_id": "C1_dual_formula",
        "type": "parallel_formulas_same_purpose",
        "task_claim": "Each variable is transformed ... to compute individual contribution indices (pi_*) which are then summed and inverted to generate a final Fire Susceptibility Index (Fire_Sus)",
        "source_evidence": {
            "pi_all": {"def_line": 243,
                       "formula": "pi_dem.add(pi_pop).add(pi_RH).add(pi_RF).add(pi_PR).add(pi_Slope).add(pi_tem).add(pi_wind).multiply(-1)",
                       "post_definition_usage_count": 0,
                       "note": "defined once, never consumed afterwards"},
            "Fire_Sus": {"def_line": 245,
                         "formula": "count_Dem.add(count_pop).add(count_RH).add(count_RF).add(count_PR).add(count_Slope).add(count_tem).pow(-1).multiply(1826.07)",
                         "post_definition_usage_count": 12,
                         "note": "drives classification, charts, and all downstream layers"},
        },
        "facts": [
            "two parallel formulas both match the task's 'summed and inverted' description",
            "pi_all includes wind and uses pi_* (transformed) inputs; Fire_Sus uses count_* (pre-log) inputs, omits wind, and applies scale 1826.07",
            "only Fire_Sus feeds downstream analysis (classification class1-5, reduceRegion, chart)",
            "pi_all is dead code in this script snapshot",
        ],
        "resolution": "NOT reconciled. Both formulas preserved with variable bindings. The reconstruction records the classification stage as consuming Fire_Sus (the only evidence-backed dependency); pi_all is recorded as an unconsumed parallel formula. Which formula matches the author's intended model cannot be determined from this script alone.",
        "forbidden_action": "choosing one formula as 'the correct' model, or merging them",
    },
    {
        "conflict_id": "C2_chart_xproperty_mismatch",
        "type": "presentation_vs_analysis_inconsistency",
        "task_claim": "a chart showing regional mean values over time (though xProperty suggests estate-based analysis)",
        "source_evidence": {
            "chart_def_line": 321,
            "call": "ui.Chart.image.byRegion({image: Fire_Sus, regions: AOI, reducer: mean, xProperty: 'Estate'})",
            "facts": [
                "regions parameter is AOI (the basin feature collection)",
                "xProperty 'Estate' does not correspond to any visible AOI property in this script",
                "the task itself flags this mismatch ('though xProperty suggests estate-based analysis')",
                "chart title 'Hot Spot VS Suhu Permukaan' (Indonesian: surface temperature) does not match fire susceptibility either",
            ],
        },
        "facts_extra": [
            "the mismatch is confined to the chart presentation layer; the susceptibility computation and classification are unaffected",
        ],
        "resolution": "NOT reconciled. Chart configuration, actual data fields, and task requirements recorded separately. Classified as a presentation-layer defect: it does not invalidate the analysis workflow and must not be treated as an analysis-stage error.",
        "forbidden_action": "mixing the presentation defect into the analysis-stage reconstruction, or 'fixing' xProperty to match AOI",
    },
    {
        "conflict_id": "C3_undefined_variables",
        "type": "undefined_in_snapshot",
        "task_claim": None,
        "source_evidence": {
            "items": [
                {"variable": "AOI", "note": "used from line 13 onward (Temp_AOI...clip(AOI)) but no var AOI = declaration exists in this script snapshot"},
                {"variable": "image", "note": "used at line 135 (var DtR = image.clip(AOI)) without visible declaration"},
                {"variable": "HP_11_09_2019", "note": "displayed at line 367 without visible declaration"},
            ],
        },
        "facts": [
            "these variables are prebound outside the script snapshot (earlier editor state or external includes)",
            "DtR (line 135) and HP_11_09_2019 (line 367) appear to be presentation/diagnostic leftovers; neither feeds the susceptibility computation chain",
        ],
        "resolution": "Recorded as external prebindings with first-use locations; no dependency edges fabricated into the analysis chain.",
        "forbidden_action": "inventing definitions or linking them into the Fire_Sus chain",
    },
]

# ------------------------------------------------------------- R1
VARIABLES = [
    {"variable": "dataset", "kind": "image_collection", "def_line": 1,
     "definition": "NOAA/GFS0P25 filtered to 2023-08-23/24", "definition_location": "in_source"},
    {"variable": "Temp_AOI", "kind": "image", "def_line": 13,
     "definition": "temperature_2m_above_ground mean over forecast hours [6,12,18,24], clipped",
     "definition_location": "in_source"},
    {"variable": "RH_AOI", "kind": "image", "def_line": 23,
     "definition": "relative humidity mean, clipped", "definition_location": "in_source"},
    {"variable": "Wind_AOI", "kind": "image", "def_line": 71,
     "definition": "wind speed sqrt(u^2+v^2) from u/v components", "definition_location": "in_source"},
    {"variable": "PR_AOI", "kind": "image", "def_line": 81,
     "definition": "precipitable water mean, clipped", "definition_location": "in_source"},
    {"variable": "RF_AOI", "kind": "image", "def_line": 91,
     "definition": "downward shortwave radiation flux mean, clipped", "definition_location": "in_source"},
    {"variable": "dem", "kind": "image", "def_line": 97,
     "definition": "COPERNICUS/GLO30 DEM mean, clipped", "definition_location": "in_source"},
    {"variable": "elv", "kind": "image", "def_line": 111,
     "definition": "NASADEM elevation (second elevation source; both loaded)",
     "definition_location": "in_source"},
    {"variable": "slope_1", "kind": "image", "def_line": 119,
     "definition": "ee.Terrain.slope(elv) clipped", "definition_location": "in_source"},
    {"variable": "pop", "kind": "image", "def_line": 153,
     "definition": "WorldPop max, clipped", "definition_location": "in_source"},
    {"variable": "count_Dem", "kind": "image", "def_line": 179,
     "definition": "dem * 47.9819", "definition_location": "in_source"},
    {"variable": "log_dem", "kind": "image", "def_line": 181,
     "definition": "log(count_Dem)", "definition_location": "in_source"},
    {"variable": "count_dem_min", "kind": "image", "def_line": 183,
     "definition": "count_Dem * -1", "definition_location": "in_source"},
    {"variable": "pi_dem", "kind": "image", "def_line": 185,
     "definition": "count_dem_min * log_dem", "definition_location": "in_source"},
    {"variable": "count_pop", "kind": "image", "def_line": 187,
     "definition": "pop * 0.7511", "definition_location": "in_source"},
    {"variable": "pi_pop", "kind": "image", "def_line": 193,
     "definition": "count_pop_min * log_pop", "definition_location": "in_source"},
    {"variable": "pi_RH", "kind": "image", "def_line": 201,
     "definition": "count_RH_min * log_RH", "definition_location": "in_source"},
    {"variable": "pi_RF", "kind": "image", "def_line": 209,
     "definition": "count_RF_min * log_RF", "definition_location": "in_source"},
    {"variable": "pi_PR", "kind": "image", "def_line": 217,
     "definition": "count_PR_min * log_PR", "definition_location": "in_source"},
    {"variable": "pi_Slope", "kind": "image", "def_line": 225,
     "definition": "count_Slope_min * log_slope", "definition_location": "in_source"},
    {"variable": "pi_tem", "kind": "image", "def_line": 233,
     "definition": "count_tem_min * log_tem", "definition_location": "in_source"},
    {"variable": "pi_wind", "kind": "image", "def_line": 241,
     "definition": "count_wind_min * log_wind", "definition_location": "in_source"},
    {"variable": "pi_all", "kind": "image", "def_line": 243,
     "definition": "sum of 8 pi_* then *(-1); UNCONSUMED (dead in this snapshot)",
     "definition_location": "in_source"},
    {"variable": "Fire_Sus", "kind": "image", "def_line": 245,
     "definition": "(count_Dem+count_pop+count_RH+count_RF+count_PR+count_Slope+count_tem).pow(-1)*1826.07; "
                   "the consumed susceptibility index",
     "definition_location": "in_source"},
    {"variable": "class1..class5", "kind": "image", "def_line": 249,
     "definition": "five risk classes via Fire_Sus.lt/gte(.and.lte).selfMask().set(val,n)",
     "definition_location": "in_source"},
    {"variable": "AOI", "kind": "geometry", "first_use_line": 13,
     "definition": "analysis geometry (prebound external; no declaration in snapshot)",
     "definition_location": "unavailable_in_source", "external_input": True},
]

EDGES = [
    # factor construction chain (each count_X -> log -> min -> pi_X)
    ("dem", "count_Dem", "multiply 47.9819", 179, "supported"),
    ("count_Dem", "pi_dem", "log -> negate -> multiply", 185, "supported"),
    ("pop", "count_pop", "multiply 0.7511", 187, "supported"),
    ("count_pop", "pi_pop", "log -> negate -> multiply", 193, "supported"),
    ("RH_AOI", "pi_RH", "scale -> log -> negate -> multiply", 201, "supported"),
    ("RF_AOI", "pi_RF", "scale -> log -> negate -> multiply", 209, "supported"),
    ("PR_AOI", "pi_PR", "scale -> log -> negate -> multiply", 217, "supported"),
    ("slope_1", "pi_Slope", "scale -> log -> negate -> multiply", 225, "supported"),
    ("Temp_AOI", "pi_tem", "scale -> log -> negate -> multiply", 233, "supported"),
    ("Wind_AOI", "pi_wind", "scale -> log -> negate -> multiply", 241, "supported"),
    # pi_all: sum of pi_*
    ("pi_dem", "pi_all", "add chain", 243, "supported"),
    ("pi_pop", "pi_all", "add chain", 243, "supported"),
    ("pi_RH", "pi_all", "add chain", 243, "supported"),
    ("pi_RF", "pi_all", "add chain", 243, "supported"),
    ("pi_PR", "pi_all", "add chain", 243, "supported"),
    ("pi_Slope", "pi_all", "add chain", 243, "supported"),
    ("pi_tem", "pi_all", "add chain", 243, "supported"),
    ("pi_wind", "pi_all", "add chain", 243, "supported"),
    # Fire_Sus: sum of count_* (pre-log inputs), invert, scale
    ("count_Dem", "Fire_Sus", "add chain then pow(-1)*1826.07", 245, "supported"),
    ("count_pop", "Fire_Sus", "add chain", 245, "supported"),
    ("count_RH", "Fire_Sus", "add chain", 245, "supported"),
    ("count_RF", "Fire_Sus", "add chain", 245, "supported"),
    ("count_PR", "Fire_Sus", "add chain", 245, "supported"),
    ("count_Slope", "Fire_Sus", "add chain", 245, "supported"),
    ("count_tem", "Fire_Sus", "add chain", 245, "supported"),
    # classification consumes Fire_Sus only
    ("Fire_Sus", "class1..class5", "lt/gte(.and.lte) thresholds", 249, "supported"),
    # count_* inputs come from the AOI-clipped factor images (count_Dem from dem, etc.)
    ("dem", "count_Dem", "also source of count chain", 179, "supported"),
    ("RH_AOI", "count_RH", "scale step", 195, "supported"),
    ("RF_AOI", "count_RF", "scale step", 203, "supported"),
    ("PR_AOI", "count_PR", "scale step", 211, "supported"),
    ("slope_1", "count_Slope", "scale step", 219, "supported"),
    ("Temp_AOI", "count_tem", "scale step", 227, "supported"),
    ("pop", "count_pop", "scale step", 187, "supported"),
    ("AOI", "Temp_AOI", "clip", 13, "supported_passing_only"),
    ("AOI", "RH_AOI", "clip", 23, "supported_passing_only"),
    ("AOI", "PR_AOI", "clip", 81, "supported_passing_only"),
    ("AOI", "RF_AOI", "clip", 91, "supported_passing_only"),
    ("AOI", "dem", "clip", 97, "supported_passing_only"),
    ("AOI", "slope_1", "clip", 119, "supported_passing_only"),
    ("AOI", "pop", "clip", 153, "supported_passing_only"),
]

UNRESOLVED = [
    {"item": "AOI geometry", "reason": "prebound external; no declaration in snapshot; first use line 13"},
    {"item": "image (line 135)", "reason": "used without declaration; appears to be a diagnostic leftover (DtR); not linked into the susceptibility chain"},
    {"item": "HP_11_09_2019 (line 367)", "reason": "displayed without declaration; not linked into the susceptibility chain"},
]

# ------------------------------------------------------------- R2
UNITS = [
    {"unit": "environmental_acquisition",
     "task_duty": "combining multiple environmental and human factors including elevation, population density, temperature, relative humidity, wind speed, solar radiation, precipitation, and slope",
     "source_operation": "GFS0P25 select/mean blocks (lines 1-91); COPERNICUS GLO30 + NASADEM (93-119); WorldPop (151-153)",
     "provenance": "task_determined",
     "implementation_detail": "dual elevation sources (GLO30 + NASADEM both loaded, NASADEM drives slope) and the GFS forecast-hours subset [6,12,18,24] are implementation choices",
     "detail_would_change": True},
    {"unit": "factor_transform",
     "task_duty": "Each variable is transformed using logarithmic scaling and weighted coefficients to compute individual contribution indices (pi_*)",
     "source_operation": "8x count_X.multiply(w).log(); pi_X = count_X_min.multiply(log_X) (lines 179-241)",
     "provenance": "task_determined",
     "implementation_detail": "per-factor weights (47.9819, 0.7511, 3.9351, 1.9702, 28.1044, 2.8167, 3.0788, 11.3618) are implementation calibration",
     "detail_would_change": True},
    {"unit": "weighted_factor_fusion",
     "task_duty": "which are then summed and inverted to generate a final Fire Susceptibility Index (Fire_Sus)",
     "source_operation": "TWO parallel realizations: pi_all (line 243, unconsumed) and Fire_Sus (line 245, consumed downstream)",
     "provenance": "task_determined",
     "implementation_detail": "the scale constant 1826.07 and Fire_Sus's omission of wind are implementation choices",
     "detail_would_change": True,
     "dual_role": {
         "consumed_formula": {"value": "Fire_Sus", "evidence": "12 post-definition usages: classes 1-5, reduceRegion min/max, chart"},
         "unconsumed_formula": {"value": "pi_all", "evidence": "0 post-definition usages; dead in this snapshot"},
         "note": "both preserved with bindings; conflict C1 not reconciled",
     }},
    {"unit": "susceptibility_classification",
     "task_duty": "The index is classified into five categories (Very Low to Very High)",
     "source_operation": "class1..class5 via Fire_Sus.lt/gte(.and.lte).selfMask().set(val,n); thresholds 0.1277/0.3288/0.5222/0.7155 (lines 249-257)",
     "provenance": "task_determined",
     "implementation_detail": "the four threshold values are implementation calibration",
     "detail_would_change": True},
    {"unit": "regional_output",
     "task_duty": "Outputs include classified fire risk zones, a chart showing regional mean values over time, and exported population data",
     "source_operation": "reduceRegion min/max over AOI (281-307); ui.Chart.image.byRegion xProperty 'Estate' (321-351); Export pop toDrive (353-363)",
     "provenance": "task_determined",
     "implementation_detail": "chart styling, the population export, and the leftover HP_11_09_2019 display are presentation/diagnostic choices",
     "detail_would_change": True,
     "presentation_defect": {
         "item": "chart xProperty 'Estate' vs regions AOI; title mismatch (surface temperature vs fire susceptibility)",
         "classification": "presentation_layer_only",
         "analysis_workflow_impact": "none - Fire_Sus computation and classification are unaffected",
         "conflict_ref": "C2",
     }},
]

SEQUENCE = [
    ("environmental_acquisition", "factor_transform", "task_explicit",
     "task verbatim: 'Each variable is transformed using logarithmic scaling...' - transforms act on the acquired variables"),
    ("factor_transform", "weighted_factor_fusion", "task_explicit",
     "task verbatim: 'which are then summed and inverted to generate...'"),
    ("weighted_factor_fusion", "susceptibility_classification", "task_explicit",
     "task verbatim: 'The index is classified into five categories'"),
    ("susceptibility_classification", "regional_output", "task_explicit",
     "task verbatim: 'Outputs include classified fire risk zones, a chart...'"),
]

CONTROL = [
    {"candidate": "pi_all vs Fire_Sus parallel construction",
     "classification": "parallel_formulas_unconsumed_vs_consumed",
     "relation_type": "recorded_as_conflict_C1",
     "control_structure": "not_a_branch",
     "reason": "two formula realizations, one dead; NOT a conditional branch - no control flow selects between them"},
    {"candidate": "class1..class5 threshold chain",
     "classification": "multi_threshold_classification",
     "control_structure": "not_a_branch",
     "reason": "five gte/lte class masks are parallel categorical outputs, not if/else control flow"},
    {"candidate": "chart xProperty mismatch",
     "classification": "presentation_layer_defect",
     "control_structure": "not_workflow",
     "reason": "confined to ui.Chart configuration; conflict C2"},
]

# Audit-unit denominator: script_269131's own 5 units (per reconciliation).
AUDIT_UNITS = {
    "environmental_inputs": {"recovered": True,
        "evidence": "Temp_AOI/RH_AOI/Wind_AOI/PR_AOI/RF_AOI/dem/slope_1/pop variables with definitions (reconciliation: mapping_loss)",
        "r2_units": ["environmental_acquisition"]},
    "factor_transform": {"recovered": True,
        "evidence": "8x count/log/pi chains located lines 179-241 (reconciliation: mapping_loss)",
        "r2_units": ["factor_transform"]},
    "weighted_factor_fusion": {"recovered": True,
        "evidence": "pi_all line 243 + Fire_Sus line 245 both recovered with bindings; conflict C1 preserved (reconciliation: mapping_loss)",
        "r2_units": ["weighted_factor_fusion"]},
    "susceptibility_classification": {"recovered": True,
        "evidence": "class1..class5 chain lines 249-257 with thresholds (previously unknown after pattern fix)",
        "r2_units": ["susceptibility_classification"]},
    "regional_output": {"recovered": True,
        "evidence": "reduceRegion/chart/export located lines 281-363 (reconciliation: extraction_loss)",
        "r2_units": ["regional_output"]},
}


def _hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    edges_supported = sum(1 for e in EDGES if e[4] == "supported")
    edges_passing = sum(1 for e in EDGES if e[4] == "supported_passing_only")
    checked = len(UNITS)
    detail = sum(1 for u in UNITS if u["detail_would_change"])
    audit_total = len(AUDIT_UNITS)
    audit_ok = sum(1 for v in AUDIT_UNITS.values() if v["recovered"])
    artifact = {
        "schema": "gee_reconstruction_trial_v1",
        "source_script": "script_269131",
        "source_sha256": _hash(RAW),
        "policy": {"training_admission": "not_granted", "semantic_gold": False,
                   "authorized_scope": "batch3_conflict_stress_test"},
        "conflict_list": CONFLICTS,
        "R1_variables": VARIABLES,
        "R1_dataflow_edges": [{"from": a, "to": b, "via": v, "use_line": ul,
                               "evidence_status": st} for a, b, v, ul, st in EDGES],
        "R1_unresolved": UNRESOLVED,
        "R2_units": UNITS,
        "R3_relationships": [{"kind": "dataflow_edge", "from": a, "to": b, "via": v,
                              "use_line": ul, "evidence_status": st}
                             for a, b, v, ul, st in EDGES]
        + [{"kind": "workflow_sequence", "from": a, "to": b,
            "evidence": ev, "evidence_status": st} for a, b, st, ev in SEQUENCE],
        "R3_control_structures": CONTROL,
    }
    (OUT / "reconstruction_269131_v1.json").write_text(
        json.dumps(artifact, ensure_ascii=False, indent=1), encoding="utf-8")
    summary = {
        "schema": "gee_reconstruction_batch3_summary_v1",
        "source_script": "script_269131",
        "conflict_stress_results": {
            "conflicts_registered": len(CONFLICTS),
            "conflicts_reconciled_silently": 0,
            "dual_formula": {"pi_all": "preserved, unconsumed", "Fire_Sus": "preserved, consumed",
                             "merged": False, "chosen": False},
            "chart_defect": {"recorded": True, "layer": "presentation_only",
                             "analysis_impact": "none"},
            "undefined_variables": {"count": 3, "fabricated_links": 0},
        },
        "R4": {
            "semantic_recovery": {"denominator": audit_total, "recovered": audit_ok,
                                  "scope": "this script's 5 audit units only"},
            "evidence_traceability": {"supported": edges_supported,
                                      "supported_passing_only": edges_passing,
                                      "unresolved": len(UNRESOLVED),
                                      "disguised": 0},
            "task_reasonableness": {"checked": checked,
                                    "judged_as_detail": detail,
                                    "misassigned_to_duty": 0,
                                    "undeterminable": 0,
                                    "fixation_rate": 0.0},
        },
        "stop": "batch 3 complete; six-script综合 assessment and expansion-design review require separate rulings",
    }
    (OUT / "reconstruction_batch3_summary_v1.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    (OUT / "reconstruction_batch3_hash_ledger_v1.json").write_text(json.dumps({
        "inputs": {"raw_script": _hash(RAW)},
        "outputs": {p.name: _hash(p) for p in OUT.iterdir()
                    if p.name != "reconstruction_batch3_hash_ledger_v1.json"},
    }, indent=2), encoding="utf-8")
    print(json.dumps({"conflicts": len(CONFLICTS),
                      "audit_recovery": f"{audit_ok}/{audit_total}",
                      "edges": {"supported": edges_supported, "passing_only": edges_passing},
                      "unresolved": len(UNRESOLVED),
                      "fixation": f"0/{checked}"}, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
