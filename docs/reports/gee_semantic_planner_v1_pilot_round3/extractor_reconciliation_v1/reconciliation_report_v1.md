# Six-Script GEE Extractor Reconciliation

**Status: DIAGNOSTIC_ONLY / NOT_ADMITTED**

- Scripts: 6
- Ledger rows: 37
- G0 SHA-256: `09c37104d2fd33138cbc15d5d23676d4d169acf1d0cfb8057a0baf3a100c02a2`

## Mismatch counts
- `representation_gap`: `2`
- `unknown`: `35`

## Per-script units
### script_269131 (27_fire_susceptibility)
- `environmental_inputs`: `unknown` (source evidence: `supported`)
- `factor_transform`: `unknown` (source evidence: `supported`)
- `weighted_factor_fusion`: `unknown` (source evidence: `supported`)
- `susceptibility_classification`: `unknown` (source evidence: `supported`)
- `regional_output`: `unknown` (source evidence: `supported`)
### script_275285 (33_land_surface_temperature_inversion)
- `cloud_shadow_mask`: `unknown` (source evidence: `supported`)
- `composite`: `unknown` (source evidence: `supported`)
- `ndvi`: `unknown` (source evidence: `supported`)
- `fractional_vegetation`: `unknown` (source evidence: `supported`)
- `emissivity`: `unknown` (source evidence: `supported`)
- `thermal_band`: `unknown` (source evidence: `supported`)
- `lst_expression`: `unknown` (source evidence: `supported`)
### script_302840 (21_predict_vegetation_cover_components)
- `target_variable_loop`: `unknown` (source evidence: `supported`)
- `model_training`: `unknown` (source evidence: `supported`)
- `prediction_sampling`: `unknown` (source evidence: `supported`)
- `target_export_filter`: `unknown` (source evidence: `supported`)
### script_36595 (30_rusle_soil_loss)
- `r_factor`: `representation_gap` (source evidence: `supported`)
- `k_factor`: `unknown` (source evidence: `supported`)
- `ls_factor`: `unknown` (source evidence: `supported`)
- `c_factor`: `representation_gap` (source evidence: `supported`)
- `p_factor`: `unknown` (source evidence: `supported`)
- `rusle_product`: `unknown` (source evidence: `supported`)
- `classification_statistics`: `unknown` (source evidence: `supported`)
### script_405410 (35_ancient_road_cost_surface)
- `slope_altitude_cost`: `unknown` (source evidence: `supported`)
- `snow_cost`: `unknown` (source evidence: `supported`)
- `water_barriers`: `unknown` (source evidence: `supported`)
- `reservoir_mask`: `unknown` (source evidence: `supported`)
- `potable_water_accessibility`: `unknown` (source evidence: `supported`)
- `cost_fusion`: `unknown` (source evidence: `supported`)
- `normalization_export`: `unknown` (source evidence: `supported`)
### script_93009 (38_urban_expansion_change_detection)
- `cloud_filter`: `unknown` (source evidence: `supported`)
- `frequency_filter`: `unknown` (source evidence: `supported`)
- `image_collection_conversion`: `unknown` (source evidence: `supported`)
- `incidence_iteration`: `unknown` (source evidence: `supported`)
- `year_extraction`: `unknown` (source evidence: `supported`)
- `recent_filter`: `unknown` (source evidence: `supported`)
- `change_outputs`: `unknown` (source evidence: `supported`)

## Layer policy

Raw source evidence and G0 canonical/semantic fields are compared without rerunning a full extractor. Parser-layer evidence is marked unavailable unless an explicit per-script AST artifact is supplied. Fail-closed rule: without parser-layer evidence, most units cannot be classified beyond `unknown`.

## Stop

This is diagnostic evidence only; no G0/G1/G2/G3 modification, training, inference, G3 reconstruction, Blueprint-v3 freeze, or RL was performed.
