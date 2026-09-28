# QGIS Recovery Cluster Proposal Replay

This is a source-backed cluster proposal, not human adjudication and not training admission.

- Reviewed clusters: 10
- Replayed rows: 25
- Raw file SHA support: 25
- Unique source authorities: 11
- Row proposals: `{"valid": 25}`
- Combined observed precision: 1.0000
- Combined Wilson lower 95%: 0.7412
- Rule training eligible: `false`
- Training rows emitted: `0`
- Validation/test/production merge: `not_granted`

## Rule Metrics

| Rule | Support | Valid | Defer | Reject current | Precision | Wilson lower 95% | Eligible |
|---|---:|---:|---:|---:|---:|---:|---|
| recovery-connected-local-dag-v1 | 5 | 5 | 0 | 0 | 1.0000 | 0.5655 | false |
| recovery-multi-root-fanin-dag-v1 | 6 | 6 | 0 | 0 | 1.0000 | 0.6097 | false |
