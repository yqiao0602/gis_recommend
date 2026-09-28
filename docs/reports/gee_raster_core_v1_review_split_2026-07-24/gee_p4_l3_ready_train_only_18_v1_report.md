# GEE P4 L3-ready Train-only Export

This package exports only P4 rows that passed deterministic operator-to-L3 canonicalization.
It remains train-only candidate data: no validation/test rows, no production merge, and no training run.

## Summary

- Input gate rows: 24
- Exported rows: 18
- Source status counts: `{'l3_ready': 18, 'needs_canonicalization_rules': 6}`
- Source bucket counts: `{'p4_accepted': 10, 'p4_rewritten_needs_edit': 8}`
- Unique source SHA256 values: 18
- Unique L3 sequences: 18
- Training admission: `not_granted_train_only_export_gate_passed`
- Production merge: `not_granted`
- Validation eligible: `False`
- Test eligible: `False`

## Included review IDs

- `gee_raster_core_review_004`
- `gee_raster_core_review_005`
- `gee_raster_core_review_006`
- `gee_raster_core_review_009`
- `gee_raster_core_review_010`
- `gee_raster_core_review_014`
- `gee_raster_core_review_021`
- `gee_raster_core_review_022`
- `gee_raster_core_review_029`
- `gee_raster_core_review_030`
- `gee_raster_core_review_031`
- `gee_raster_core_review_033`
- `gee_raster_core_review_034`
- `gee_raster_core_review_035`
- `gee_raster_core_review_042`
- `gee_raster_core_review_047`
- `gee_raster_core_review_049`
- `gee_raster_core_review_050`

## Boundary

- `source_platform=GEE`
- `target_platform=L3`
- `training_scope=core_subworkflow`
- `sample_weight=0.5`
- `validation_eligible=false`, `test_eligible=false`
- Not QGIS operator-chain gold.
