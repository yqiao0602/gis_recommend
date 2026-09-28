# GEE Raster Core Batch Training Package v1

This is the scalable GEE raster/L3 train-only export. It converts the
source-identity grafted candidate pool in batch and uses deterministic
gates plus sidecars instead of row-by-row production review.

## Result

- Input rows: 11,454
- Accepted train-only rows: 11,397
- V4-100 no-truncation rows: 11,397
- Deferred gate sidecar rows: 57
- Long-chain sidecar rows: 0
- Audit sample rows: 50
- Unique source SHA256 values: 11,397
- Unique L3 sequences: 8,494
- Unique operator sequences: 9,089
- Model sequence length: 5..22
- Training admission: `granted_train_only_gee_raster_core_batch_silver_v1`
- Split: `train_only_gee_raster_core_batch_v1`
- Validation eligible: `False`
- Test eligible: `False`
- Production merge granted: `False`
- Training run started: `False`
- Manual review role: sampling audit only = `True`

## Gate failures

- `source_identity_not_authoritative`: 57
- `source_path_missing`: 57
- `source_sha256_missing_or_invalid`: 57

## Review split handling

The prior source/sequence-disjoint split is retained only as an audit
field. This exporter does not emit validation/test rows because GEE
validation/test promotion has not been granted.

- original `test` audit rows: 1,140
- original `train` audit rows: 9,117
- original `val` audit rows: 1,140

## Boundary

- This package is GEE raster/L3 silver supervision, not QGIS operator-chain gold.
- It does not rewrite task descriptions or infer missing operators.
- Unmatched source-identity rows fail closed into sidecar.
- Human review is a stratified audit sample used to calibrate future rules.
