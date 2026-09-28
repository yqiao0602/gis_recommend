# GEE Batch Source-Backed Rule Proposals v1

This packet converts source-backed audit findings for one risk layer into
proposal-only routing decisions. It does not grant training admission.

## Result

- Source-audit rows: 31
- Proposal rows: 31
- Rewrite-candidate rows: 0
- Deferred/rule-repair rows: 31
- Training rows emitted: 0
- Validation eligible: False
- Test eligible: False

## Proposal decisions

- `defer_generic_rule_review`: 29
- `defer_manual_boundary_review`: 2

## Rule repair targets


## Boundary

- Proposal rows are not accepted training rows.
- Operator/L3 sequences are copied unchanged from source-audit rows.
- Any rewrite candidate still requires a separate train-only export gate.
