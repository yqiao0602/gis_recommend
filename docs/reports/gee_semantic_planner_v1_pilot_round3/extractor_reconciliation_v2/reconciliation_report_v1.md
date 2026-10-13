# Six-Script GEE Extractor Reconciliation

**Status: DIAGNOSTIC_ONLY / NOT_ADMITTED**

- Scripts: 6
- Ledger rows: 37
- G0 SHA-256: `09c37104d2fd33138cbc15d5d23676d4d169acf1d0cfb8057a0baf3a100c02a2`

## Mismatch counts
- `extraction_loss`: `13`
- `mapping_loss`: `19`
- `representation_gap`: `2`
- `unknown`: `3`

## Per-script units
### script_269131 (27_fire_susceptibility)
- `environmental_inputs`: `mapping_loss` (source evidence: `supported`)
- `factor_transform`: `mapping_loss` (source evidence: `supported`)
- `weighted_factor_fusion`: `mapping_loss` (source evidence: `supported`)
- `susceptibility_classification`: `unknown` (source evidence: `supported`)
- `regional_output`: `unknown` (source evidence: `supported`)
### script_275285 (33_land_surface_temperature_inversion)
- `cloud_shadow_mask`: `extraction_loss` (source evidence: `supported`)
- `composite`: `mapping_loss` (source evidence: `supported`)
- `ndvi`: `extraction_loss` (source evidence: `supported`)
- `fractional_vegetation`: `extraction_loss` (source evidence: `supported`)
- `emissivity`: `extraction_loss` (source evidence: `supported`)
- `thermal_band`: `extraction_loss` (source evidence: `supported`)
- `lst_expression`: `extraction_loss` (source evidence: `supported`)
### script_302840 (21_predict_vegetation_cover_components)
- `target_variable_loop`: `mapping_loss` (source evidence: `supported`)
- `model_training`: `mapping_loss` (source evidence: `supported`)
- `prediction_sampling`: `mapping_loss` (source evidence: `supported`)
- `target_export_filter`: `mapping_loss` (source evidence: `supported`)
### script_36595 (30_rusle_soil_loss)
- `r_factor`: `representation_gap` (source evidence: `supported`)
- `k_factor`: `mapping_loss` (source evidence: `supported`)
- `ls_factor`: `mapping_loss` (source evidence: `supported`)
- `c_factor`: `representation_gap` (source evidence: `supported`)
- `p_factor`: `mapping_loss` (source evidence: `supported`)
- `rusle_product`: `mapping_loss` (source evidence: `supported`)
- `classification_statistics`: `mapping_loss` (source evidence: `supported`)
### script_405410 (35_ancient_road_cost_surface)
- `slope_altitude_cost`: `mapping_loss` (source evidence: `supported`)
- `snow_cost`: `mapping_loss` (source evidence: `supported`)
- `water_barriers`: `extraction_loss` (source evidence: `supported`)
- `reservoir_mask`: `extraction_loss` (source evidence: `supported`)
- `potable_water_accessibility`: `mapping_loss` (source evidence: `supported`)
- `cost_fusion`: `mapping_loss` (source evidence: `supported`)
- `normalization_export`: `unknown` (source evidence: `supported`)
### script_93009 (38_urban_expansion_change_detection)
- `cloud_filter`: `extraction_loss` (source evidence: `supported`)
- `frequency_filter`: `mapping_loss` (source evidence: `supported`)
- `image_collection_conversion`: `extraction_loss` (source evidence: `supported`)
- `incidence_iteration`: `extraction_loss` (source evidence: `supported`)
- `year_extraction`: `mapping_loss` (source evidence: `supported`)
- `recent_filter`: `extraction_loss` (source evidence: `supported`)
- `change_outputs`: `extraction_loss` (source evidence: `supported`)

## Layer policy

Raw source evidence and G0 canonical/semantic fields are compared without rerunning a full extractor. Parser-layer evidence is marked unavailable unless an explicit per-script AST artifact is supplied. Fail-closed rule: without parser-layer evidence, most units cannot be classified beyond `unknown`.

## Stop

This is diagnostic evidence only; no G0/G1/G2/G3 modification, training, inference, G3 reconstruction, Blueprint-v3 freeze, or RL was performed.
