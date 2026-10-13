"""Build the six Step-1 duty-gold records and acceptance report (manual gold)."""
import hashlib
import json
from pathlib import Path

out_dir = Path("docs/reports/gee_semantic_planner_v1_pilot_round3/duty_gold_v0")
out_dir.mkdir(parents=True, exist_ok=True)


def duty(duty_text, task_ev, src_ev, order, prov, notes="", risk=None):
    rec = {"duty": duty_text, "task_evidence": task_ev, "source_evidence": src_ev,
           "order_basis": order, "provenance": prov}
    if risk:
        rec["implementation_specific_risk"] = risk
    if notes:
        rec["notes"] = notes
    return rec


records = []

records.append({
    "source_script": "script_302840",
    "review_label": "21_predict_vegetation_cover_components",
    "duty_sequence": [
        duty("acquire field training features and spectral predictor imagery",
             "trained on field training data (ftTrain); using spectral bands as predictors",
             "ftTrain / bands variables; parser core chain image loads",
             "task_explicit", "task_determined",
             risk="G0 instructions are code-derived summaries; acquisition details are source-only"),
        duty("train a separate random-forest regression model for each target variable",
             "For each target variable (coi), a separate Random Forest classifier is trained with specified parameters",
             "rf1/rf2/rf4... ee.Classifier.smileRandomForest().setOutputMode('REGRESSION').train({classProperty: coiN})",
             "task_explicit", "task_determined"),
        duty("apply each trained model and sample per-feature predictions",
             "The trained models are applied to predicted image collections (predLst) sampled over specific features (tfoiLst), generating per-feature predictions",
             "FeatureCollection.classify(rfN); Image.sampleRegions over tfoiLst",
             "task_explicit", "task_determined"),
        duty("filter out invalid validation pixels before export",
             "filtered to exclude pixels where lsNDVI or mdNDVI equals -1",
             "ee.Filter.neq('lsNDVI', -1) / ('mdNDVI', -1)",
             "task_explicit", "task_determined"),
        duty("export per-target CSV with key, observed value, and prediction",
             "Each export includes the primary key, observed value, and model prediction",
             "Export.table.toCloudStorage(selectors: pnN)",
             "task_explicit", "task_determined"),
    ],
    "repeat_structure": {
        "repeat_count_task_inferable": True,
        "repeat_count_value": 8,
        "task_evidence_for_count": "eight named targets (BareGround, TotalFolia, GapPct_251, InvAnnGras, NonInvPe_1, NonInvShru, NonInvTree, SageBrushC) plus 'For each target variable (coi)'",
        "unit_structure_homogeneous": True,
        "unit_structure": ["train RF per target", "apply model and sample predictions", "filter invalid pixels", "export CSV"],
        "binding": "per-target-variable",
        "binding_task_inferable": True,
        "binding_source_evidence": "each rfN trains with classProperty: coiN; each export named by coiN; G0 raw chain shows the 4-step block repeating 8 times",
        "notes": "count is directly countable from the Task's named list; the specific variable-to-model mapping is source-only but per-target binding is task-explicit",
    },
    "task_level_notes": "Task narrates the workflow in execution order; duty granularity follows the Task's own enumeration.",
})

records.append({
    "source_script": "script_269131",
    "review_label": "27_fire_susceptibility",
    "duty_sequence": [
        duty("acquire environmental and terrain factor layers over the AOI",
             "combining multiple environmental and human factors including elevation, population density, temperature, relative humidity, wind speed, solar radiation, precipitation, and slope",
             "GFS0P25 selects; WorldPop; NASADEM/ee.Terrain.slope; parser dataset.select.filter.mean blocks",
             "task_explicit", "task_determined"),
        duty("transform each factor with logarithmic scaling and weighted coefficients",
             "Each variable is transformed using logarithmic scaling and weighted coefficients to compute individual contribution indices (pi_*)",
             "count_X.multiply(w).log(); pi_X = count_X_min.multiply(log_X) blocks",
             "task_explicit", "task_determined"),
        duty("combine weighted factors into a single susceptibility index",
             "which are then summed and inverted to generate a final Fire Susceptibility Index (Fire_Sus)",
             "pi_all = pi_dem.add(...)...multiply(-1); Fire_Sus = count_*...pow(-1).multiply(1826.07)",
             "task_explicit", "task_determined",
             risk="source shows two parallel fusion formulas (pi_all and Fire_Sus); the Task describes one 'summed and inverted' index - the exact relationship is ambiguous in Task"),
        duty("classify the index into five risk categories",
             "The index is classified into five categories (Very Low to Very High)",
             "class1..class5 via Fire_Sus.lt/gte(.and.lte).selfMask().set('val',n)",
             "task_explicit", "task_determined"),
        duty("summarize and visualize regional values",
             "Outputs include classified fire risk zones, a chart showing regional mean values over time, and exported population data",
             "reduceRegion min/max; ui.Chart.image.byRegion(xProperty:'Estate'); Map.layers().set",
             "task_explicit", "task_determined",
             notes="known description/implementation inconsistency: chart xProperty 'Estate' vs AOI geometry; the Task itself flags this"),
    ],
    "repeat_structure": {
        "repeat_count_task_inferable": False,
        "repeat_count_value": None,
        "unit_structure_homogeneous": False,
        "binding": "none",
        "notes": "no repeated homogeneous subworkflow; factor transforms are heterogeneous (different weights per factor)",
    },
    "task_level_notes": "Task is a faithful summary except the chart/export mismatch already flagged inside the Task text itself.",
})

records.append({
    "source_script": "script_36595",
    "review_label": "30_rusle_soil_loss",
    "duty_sequence": [
        duty("define the study area as the target basin and its subbasins",
             "Estimate annual soil loss in the Mahi Basin",
             "HydroSHEDS filter(eq MAIN_BAS 4120031730)",
             "task_implied", "task_determined"),
        duty("compute the rainfall erosivity (R) factor",
             "combining rainfall erosivity (R)",
             "CHIRPS.sum().multiply(0.363).add(79)",
             "task_explicit", "task_determined"),
        duty("compute the soil erodibility (K) factor",
             "soil erodibility (K)",
             "soil.expression lookup table by soil class",
             "task_explicit", "task_determined"),
        duty("compute the slope length and steepness (LS) factor",
             "slope length and steepness (LS)",
             "ee.Terrain.slope -> percent -> LS polynomial",
             "task_explicit", "task_determined"),
        duty("compute the vegetation cover (C) factor from NDVI",
             "vegetation cover (C)",
             "s2.normalizedDifference(B8,B4) -> min-max normalization chain",
             "task_explicit", "task_determined"),
        duty("compute the land management (P) factor",
             "land management (P)",
             "lulc+slope expression lookup",
             "task_explicit", "task_determined"),
        duty("combine the five factors into the soil-loss equation",
             "combining rainfall erosivity (R), soil erodibility (K), slope length and steepness (LS), vegetation cover (C), and land management (P) factors",
             "soil_loss = R.multiply(K).multiply(LS).multiply(C).multiply(P)",
             "task_explicit", "task_determined"),
        duty("classify soil loss into severity classes",
             "Outputs include ... soil loss classes",
             "SL_class expression thresholds 5/10/20/40",
             "task_explicit", "task_determined"),
        duty("compute per-subbasin means and per-class area statistics",
             "mean soil loss per subbasin, and area statistics by class",
             "reduceRegions(mean) per subbasin; pixelArea group-sum by class; pie chart",
             "task_explicit", "task_determined"),
    ],
    "repeat_structure": {
        "repeat_count_task_inferable": False,
        "repeat_count_value": None,
        "unit_structure_homogeneous": False,
        "binding": "none",
        "notes": "factor computation is a fixed chain, not a repeated homogeneous unit",
    },
    "task_level_notes": "Task enumerates all five factors and outputs in order; highest task-explicit coverage of the six samples.",
})

records.append({
    "source_script": "script_275285",
    "review_label": "33_land_surface_temperature_inversion",
    "duty_sequence": [
        duty("mask clouds and shadows from the collection",
             "It applies cloud and shadow masking via the pixel_qa band",
             "maskL8sr: qa.bitwiseAnd(cloudShadow/cloudsBitMask) -> updateMask",
             "task_explicit", "task_determined"),
        duty("build a composite image for the study period",
             None,
             "col.median().clip(geometry)",
             "source_order_only", "source_required",
             notes="Task never states a composite step; position between masking and NDVI is source-only"),
        duty("compute NDVI",
             "computes NDVI",
             "image.normalizedDifference(['B5','B4'])",
             "task_explicit", "task_determined"),
        duty("derive fractional vegetation cover (FV) from NDVI min/max",
             "computes NDVI to derive fractional vegetation cover (FV)",
             "fv = ((ndvi-min)/(max-min)).pow(2); min/max via reduceRegion",
             "task_explicit", "task_determined"),
        duty("estimate surface emissivity (EMM) from FV",
             "estimates surface emissivity (EMM)",
             "EM = fv.multiply(0.004).add(0.986)",
             "task_explicit", "task_determined"),
        duty("prepare the thermal brightness band",
             "brightness temperature (B10)",
             "image.select('B10').multiply(0.1)",
             "task_explicit", "task_determined"),
        duty("compute LST via radiative-transfer expression over brightness and emissivity",
             "calculates LST using a radiative transfer-based expression involving brightness temperature (B10) and emissivity",
             "thermal.expression('(Tb/(1+(0.00115*(Tb/1.438))*log(Ep)))-273.15')",
             "task_explicit", "task_determined"),
    ],
    "repeat_structure": {
        "repeat_count_task_inferable": False,
        "repeat_count_value": None,
        "unit_structure_homogeneous": False,
        "binding": "none",
    },
    "task_level_notes": "Explicit intermediate chain is almost fully task-determined; only the composite step is source-required. Cleanest dependency-structure sample of the six.",
})

records.append({
    "source_script": "script_405410",
    "review_label": "35_ancient_road_cost_surface",
    "duty_sequence": [
        duty("compute topographic slope and altitude costs from the DSM",
             "topographic slope (using critical-slope quadratic cost), altitude-dependent physiological cost (>2000 m)",
             "ee.Terrain.slope -> critical-slope quadratic; altitude cost x dsm.gt(2000)",
             "task_explicit", "task_determined"),
        duty("compute seasonal snow-cover cost",
             "seasonal snow cover (MOD10A1 NDSI-derived)",
             "MOD10A1 NDSI filter(period).reduce(mean) -> cost_snow",
             "task_explicit", "task_determined"),
        duty("apply sea-water and surface-water barriers",
             "sea water barriers (MOD44W), surface water recurrence (JRC GSW MonthlyRecurrence)",
             "MOD44W remap -> mask_sea; MonthlyRecurrence -> cost_surface_water",
             "task_explicit", "task_determined"),
        duty("apply the reservoir mask",
             "reservoir presence (GRanD-based vector mask)",
             "GRanD FeatureCollection paint -> remap -> reservoirs_new_value",
             "task_explicit", "task_determined"),
        duty("compute potable-water accessibility as a cost reducer",
             "potable water accessibility (Landsat EVI-derived attraction)",
             "Landsat EVI -> threshold band math -> cost_reducer_water_accessibility",
             "task_explicit", "task_determined"),
        duty("fuse all factors into one cost surface",
             "into a unified raster cost surface",
             "costs_raw = cost_slope.multiply(cost_snow).multiply(cost_altitude).multiply(cost_surface_water).divide(cost_reducer).multiply(mask_reservoirs).add(...).add(mask_sea)",
             "task_explicit", "task_determined"),
        duty("cap outlier costs and normalize to 0-255 uint8",
             "a scaled, normalized 8-bit unsigned integer cost raster (0-255)",
             "costs_max_assigned (gt/lte cap) -> divide(max).multiply(255).byte()",
             "task_explicit", "task_determined"),
        duty("export the cost raster to Google Drive",
             "exported to Google Drive with metadata-encoded filename",
             "Export.image.toDrive with metadata description",
             "task_explicit", "task_determined",
             notes="source contains the recorded output_resolution/outrr defect (source_code_defect, not extraction)"),
    ],
    "repeat_structure": {
        "repeat_count_task_inferable": False,
        "repeat_count_value": None,
        "unit_structure_homogeneous": False,
        "binding": "none",
    },
    "task_level_notes": "Seven factors enumerated in Task match source comments (FACTOR A-D) one-to-one.",
})

records.append({
    "source_script": "script_93009",
    "review_label": "38_urban_expansion_change_detection",
    "duty_sequence": [
        duty("load historical urban reference layers",
             "validating against older urban layers from 1985 and 2017",
             "col_old_1985/col_old_2017 .eq(24).selfMask()",
             "task_explicit", "task_determined"),
        duty("filter the classification time series (cloud/frequency)",
             "applying temporal filters to a time series of classified Landsat images",
             "tf_lib.applyFilterCloud / applyFilterFreq (external library bodies not in source)",
             "task_implied", "task_determined",
             notes="internal filter logic lives in required libraries; only call names are source-visible"),
        duty("compute urban detection frequency before and after filtering",
             "frequency of urban detection before and after filtering",
             "freq_antes/freq_depois = image_tf.eq(24).reduce(sum)",
             "task_explicit", "task_determined"),
        duty("detect classification-change incidence across the series",
             "detecting incidence of classification changes",
             "incidence(): imc.iterate where classification0.neq(classification1) accumulate",
             "task_explicit", "task_determined"),
        duty("extract urban extent for comparison years",
             "comparing urban extent in 1985 and 2018",
             "get_image_year(image_tf, 1985/2000/1999/1998/2018) remap",
             "task_explicit", "task_determined"),
        duty("filter recent urban development",
             "recent urban development",
             "tf_lib.applyFilterRecent",
             "task_explicit", "task_determined"),
        duty("visualize and cross-validate against historical layers",
             "validating against older urban layers from 1985 and 2017",
             "Map.addLayer col_old_1985/2017 overlays, incidents/freq layers",
             "task_explicit", "task_determined"),
    ],
    "repeat_structure": {
        "repeat_count_task_inferable": True,
        "repeat_count_value": None,
        "task_evidence_for_count": "Task names two comparison years (1985, 2018); source extracts five years (1985/1998/1999/2000/2018)",
        "unit_structure_homogeneous": True,
        "unit_structure": ["select classification_<year> band", "remap urban class", "mask"],
        "binding": "per-year",
        "binding_task_inferable": True,
        "binding_source_evidence": "get_image_year per year; Task explicitly compares 1985 vs 2018",
        "notes": "count mismatch: Task implies 2, source builds 5 - year count is NOT directly task-countable; flagged as count-inference risk",
    },
    "task_level_notes": "Duty sequence is task-determined; year-extraction count reveals Task-vs-source divergence (2 vs 5).",
})

out = out_dir / "duty_gold_6_v0.jsonl"
out.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in records), encoding="utf-8")

tally = {"task_determined": 0, "source_required": 0, "undeterminable": 0}
for r in records:
    for d in r["duty_sequence"]:
        tally[d["provenance"]] += 1
total = sum(tally.values())

report = f"""# Step 1 Duty Gold - Acceptance Report (v0)

**Status: STEP1_COMPLETE / NOT_ADMITTED / NOT_TRAINING**
Rows: 6 scripts; duty stages total: {total}

## Q1 - How many tasks yield a trustworthy duty sequence?

**6 / 6.** Every script satisfies the frozen criterion (>=60% of stages with
provenance in {{task_determined, source_required}} and at least one
non-source_order_only order basis). All six have task_explicit ordering for
their main chain.

## Q2 - Field provenance counts (over {total} stages)

| provenance | count | share |
|---|---:|---:|
| task_determined | {tally['task_determined']} | {tally['task_determined'] / total:.0%} |
| source_required | {tally['source_required']} | {tally['source_required'] / total:.0%} |
| undeterminable | {tally['undeterminable']} | {tally['undeterminable'] / total:.0%} |

The single source_required stage is the median-composite step in script_275285
(Task never states a compositing step; col.median() is source-only).

**Critical caveat (recorded honestly):** G0 instructions read as code-derived
workflow summaries - they narrate the implementation in execution order. The
high task_determined rate therefore does NOT prove independent human task
intent; it may reflect that the Task text was itself generated from the script.
For training Task->duty this creates a circularity risk: the model may learn to
invert summarization rather than to plan. Any Step-2 design must treat this as
the primary validity threat (e.g., tasks authored independently of code, or
held-out tasks from other sources).

## Q3 - Definition clarity / inter-annotator reproducibility

Ambiguity points encountered, with severity:

1. **Duty granularity** (moderate): RUSLE's five factors could be one
   "factor computation" duty or five; I followed the Task's own enumeration.
   A second annotator applying the same rule (Task-granularity) should agree.
2. **Presentation vs workflow duty** (moderate): charts/Map.addLayer are
   counted as duties when the Task lists them as outputs (269131, 36595,
   93009). Reasonable annotators could exclude them; impact ~1 stage/script.
3. **Composite step** (low): not in the Task text for 275285; the rule says
   source_required, not dropped - the rule is explicit.
4. **C-target count inference** (high for 93009): Task names 2 years, source
   builds 5 (+2 historical layers). Recorded count mismatch instead of forcing
   2 or 5. For 302840 the count (8) is directly listable from the Task.

Overall: B and C definitions are clear enough that a second annotator should
reach substantial agreement on stage identity and order; C-count inference is
reliable only when the Task explicitly enumerates the repeated units.

## C-target results

| script | count inferable | value | homogeneous | binding |
|---|---|---|---|---|
| 302840 | yes | 8 | yes | per-target-variable (task-level; specifics source-only) |
| 93009 | partial | Task=2 vs source=5 | yes | per-year (task-explicit) |
| others | no | - | - | none |

## Conclusion

- B (task->duty) is constructible for all six with explicit evidence chains.
- The dominant validity threat is G0-Task circularity, not annotatability.
- C is viable only where the Task enumerates repeated units (302840 pattern).
"""
(out_dir / "duty_gold_step1_report_v0.md").write_text(report, encoding="utf-8")

(out_dir / "duty_gold_hash_ledger_v0.json").write_text(json.dumps({
    "inputs": {
        "raw_packet": "docs/reports/gee_semantic_planner_v1_pilot_round3/g0_semantic_review_priority6_raw_v1.jsonl",
        "scripts_packet": "docs/reports/gee_semantic_planner_v1_pilot_round3/g0_semantic_review_priority6_scripts_v1.jsonl",
    },
    "outputs": {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                for p in out_dir.iterdir() if p.name != "duty_gold_hash_ledger_v0.json"},
    "policy": {"training_admission": "not_granted", "semantic_gold": False,
               "batch_expansion_authorized": False},
}, indent=2), encoding="utf-8")

print(json.dumps({"rows": len(records), "stages": total, **tally}, indent=1))
