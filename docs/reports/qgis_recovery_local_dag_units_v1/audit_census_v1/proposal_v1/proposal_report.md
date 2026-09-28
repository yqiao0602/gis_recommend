# QGIS Recovery Cluster Proposal Replay

This is a source-backed cluster proposal, not human adjudication and not training admission.

- Reviewed clusters: 12
- Replayed rows: 31
- Raw file SHA support: 31
- Unique source authorities: 13
- Row proposals: `{"defer": 3, "reject_current_recovery": 3, "valid": 25}`
- Combined observed precision: 0.8462
- Combined Wilson lower 95%: 0.5776
- Rule training eligible: `false`
- Training rows emitted: `0`
- Validation/test/production merge: `not_granted`

## Rule Metrics

| Rule | Support | Valid | Defer | Reject current | Precision | Wilson lower 95% | Eligible |
|---|---:|---:|---:|---:|---:|---:|---|
| recovery-connected-local-dag-v1 | 7 | 5 | 1 | 1 | 0.7143 | 0.3589 | false |
| recovery-multi-root-fanin-dag-v1 | 6 | 6 | 0 | 0 | 1.0000 | 0.6097 | false |
