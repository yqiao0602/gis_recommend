# GEE Full Batch Policy Gate Dry Run v1

This dry run applies the six sampling-audit policy candidates to the
current 11,397-row GEE raster-core silver package as a sidecar only.

## Result

- Gate rows: 11,397
- Rows with policy hits: 8,291
- Strict regeneration defer rows: 4,283
- Sidecar/text-review rows: 4,008
- Provisionally keep rows: 3,106
- Training rows emitted: 0

## Policy hits

- `display_export_noise_sidecar`: 6,041
- `evaluation_metrics_sidecar`: 1,672
- `external_context_sidecar`: 727
- `generic_rule_review_fail_closed`: 1,451
- `manual_boundary_review_fail_closed`: 0
- `rule_repair_before_regeneration`: 3,148

## Boundary

- This is a surface-policy dry run, not row-level source-backed admission.
- It does not modify `train11397_*`.
- It does not create validation/test data.
- It does not call an LLM or start training.
- Full regeneration requires an explicit next step.
