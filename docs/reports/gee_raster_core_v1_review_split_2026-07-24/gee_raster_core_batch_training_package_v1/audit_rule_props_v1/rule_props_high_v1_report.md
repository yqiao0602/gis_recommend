# GEE Batch High-Risk Rule Proposals v1

This packet converts source-backed high-risk audit findings into
proposal-only routing decisions. It does not grant training admission.

## Result

- Source-audit rows: 5
- Proposal rows: 5
- Rewrite-candidate rows: 2
- Deferred/rule-repair rows: 3
- Training rows emitted: 0
- Validation eligible: False
- Test eligible: False

## Proposal decisions

- `defer_external_algorithm_sidecar`: 1
- `defer_manual_boundary_review`: 1
- `defer_regional_statistics_mapping_repair`: 1
- `rewrite_core_classifier_keep_eval_sidecar`: 1
- `rewrite_core_raster_stats_text`: 1

## Rule repair targets

- `optional_evaluation_extractor`: 1
- `regional_statistics_extractor_or_l3_mapping`: 1
- `temporal_module_extractor_or_external_algorithm_policy`: 1

## Boundary

- Proposal rows are not accepted training rows.
- Operator/L3 sequences are copied unchanged from source-audit rows.
- Any rewrite candidate still requires a separate train-only export gate.
