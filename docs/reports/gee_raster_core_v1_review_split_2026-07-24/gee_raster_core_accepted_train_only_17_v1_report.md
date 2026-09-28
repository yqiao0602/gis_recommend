# GEE Raster Core Accepted Train-only Export

This package combines only P0 accepted core rows and P2 v2 accepted
chain-faithful rewrite rows. It remains a candidate export gate: no LLM
was called, no validation/test rows are created, and no training run is
authorized by this artifact.

## Summary

- Exported rows: 17
- P0 accept rows: 9
- P2 v2 accepted rows: 8
- Unique source SHA256 values: 17
- Unique L3 sequences: 17
- Training admission: `not_granted_train_only_export_gate_passed`
- Production merge: `not_granted`
- Validation eligible: `False`
- Test eligible: `False`

## Included review IDs

### P0 accept_core_now
- `gee_raster_core_review_001`
- `gee_raster_core_review_008`
- `gee_raster_core_review_011`
- `gee_raster_core_review_017`
- `gee_raster_core_review_023`
- `gee_raster_core_review_036`
- `gee_raster_core_review_037`
- `gee_raster_core_review_041`
- `gee_raster_core_review_043`

### P2 v2 yes_train_only
- `gee_raster_core_review_002`
- `gee_raster_core_review_003`
- `gee_raster_core_review_015`
- `gee_raster_core_review_016`
- `gee_raster_core_review_019`
- `gee_raster_core_review_025`
- `gee_raster_core_review_032`
- `gee_raster_core_review_048`

## Boundary

- `source_platform=GEE`
- `target_platform=L3`
- `training_scope=core_subworkflow`
- `sample_weight <= 0.5`
- `validation_eligible=false`, `test_eligible=false`
- Not QGIS operator-chain gold.
