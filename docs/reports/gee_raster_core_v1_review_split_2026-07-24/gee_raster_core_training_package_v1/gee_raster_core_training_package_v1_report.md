# GEE Raster Core Training Package v1

This package converts the reviewed 35-row GEE raster-core manifest into
the integer L3-token format expected by the existing V4 data path.

## Result

- Full train-only rows: 35
- V4-100 no-truncation rows: 33
- Long-chain sidecar rows: 2
- Unique source SHA256 values: 35
- Unique operator sequences: 35
- Unique L3 sequences: 35
- Model sequence length: 5..142
- Training admission: `granted_train_only_gee_raster_core_v1`
- Validation eligible: `False`
- Test eligible: `False`
- Production merge granted: `False`

## Long-chain policy

Rows longer than the current V4 default max sequence length of 100 are
not included in the V4-100 package, because silent truncation would damage
the gold chain. They remain available in the full package and sidecar.

- `gee_raster_core_review_042`
- `gee_raster_core_review_050`
