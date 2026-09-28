# QGIS Recovery Cluster Proposal Replay

This is a source-backed cluster proposal, not human adjudication and not training admission.

- Reviewed clusters: 11
- Replayed rows: 28
- Raw file SHA support: 28
- Unique source authorities: 12
- Row proposals: `{"reject_current_recovery": 3, "valid": 25}`
- Combined observed precision: 0.9167
- Combined Wilson lower 95%: 0.6461
- Rule training eligible: `false`
- Training rows emitted: `0`
- Validation/test/production merge: `not_granted`

## Rule Metrics

| Rule | Support | Valid | Defer | Reject current | Precision | Wilson lower 95% | Eligible |
|---|---:|---:|---:|---:|---:|---:|---|
| recovery-connected-local-dag-v1 | 6 | 5 | 0 | 1 | 0.8333 | 0.4365 | false |
| recovery-multi-root-fanin-dag-v1 | 6 | 6 | 0 | 0 | 1.0000 | 0.6097 | false |
