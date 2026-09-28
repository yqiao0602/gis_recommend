# GEE Batch Sampling Policy Gate Dry Run v1

This dry run materializes the rollup policy candidates as row-level
fail-closed gate decisions over the 50 source-backed sampling-audit rows.

## Result

- Gate rows: 50
- Source hash verified rows: 50
- Rewrite sidecar candidates not admitted: 3
- Fail-closed backlog rows: 47
- Training rows emitted: 0

## Policy hits

- `display_export_noise_sidecar`: 27
- `evaluation_metrics_sidecar`: 2
- `external_context_sidecar`: 6
- `generic_rule_review_fail_closed`: 39
- `manual_boundary_review_fail_closed`: 4
- `rule_repair_before_regeneration`: 4

## Boundary

- Dry-run rows are not accepted training rows.
- This artifact does not append to or rewrite `train11397_*`.
- Validation/test and production merge remain forbidden.
