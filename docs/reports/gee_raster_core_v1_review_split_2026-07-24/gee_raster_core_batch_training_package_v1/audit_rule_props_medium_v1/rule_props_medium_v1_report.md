# GEE Batch Source-Backed Rule Proposals v1

This packet converts source-backed audit findings for one risk layer into
proposal-only routing decisions. It does not grant training admission.

## Result

- Source-audit rows: 14
- Proposal rows: 14
- Rewrite-candidate rows: 1
- Deferred/rule-repair rows: 13
- Training rows emitted: 0
- Validation eligible: False
- Test eligible: False

## Proposal decisions

- `defer_generic_rule_review`: 10
- `defer_manual_boundary_review`: 1
- `rewrite_core_classifier_keep_eval_sidecar`: 1
- `rewrite_or_defer_text_overclaim`: 2

## Rule repair targets

- `optional_evaluation_extractor`: 1

## Boundary

- Proposal rows are not accepted training rows.
- Operator/L3 sequences are copied unchanged from source-audit rows.
- Any rewrite candidate still requires a separate train-only export gate.
