# GEE Raster Core Reviewed Train-only Manifest

This manifest combines the 17-row accepted GEE raster-core train-only
package with the 18-row P4 L3-ready package. It also keeps unresolved
P4 rows in a separate fail-closed sidecar. This is not a production merge
and does not authorize validation/test use or a training run.

## Summary

- Manifest rows: 35
- Existing accepted package rows: 17
- P4 L3-ready rows: 18
- P4 unresolved sidecar rows: 6
- Unique source SHA256 values: 35
- Unique L3 sequences: 35
- Unique operator sequences: 35
- Training admission: `not_granted_reviewed_train_only_manifest_gate_passed`
- Production merge: `not_granted`
- Validation eligible: `False`
- Test eligible: `False`
- Training run started: `False`

## Source packages

- `gee_p4_l3_ready_train_only_18_v1`: 18
- `gee_raster_core_accepted_train_only_17_v1`: 17

## Deferred P4 rows

- `gee_raster_core_review_018`
- `gee_raster_core_review_020`
- `gee_raster_core_review_027`
- `gee_raster_core_review_038`
- `gee_raster_core_review_044`
- `gee_raster_core_review_045`

## Boundary

- `source_platform=GEE`
- `target_platform=L3`
- `training_scope=core_subworkflow`
- `manifest_split=train_only`
- `sample_weight <= 0.5`
- Validation/test and production merge are explicitly forbidden.
- This manifest is not QGIS operator-chain gold.
