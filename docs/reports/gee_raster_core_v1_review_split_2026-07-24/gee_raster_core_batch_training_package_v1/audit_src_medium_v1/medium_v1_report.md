# GEE Batch Source-Backed Audit Packet v1

This packet reviews a selected GEE batch audit-precheck risk cluster against
verified source files. It is used to decide whether systemic failures
should repair extractor/text/mapping rules or move rows to sidecars.

## Result

- Input precheck rows: 50
- Selected risk level: `medium`
- Source-audit rows: 14
- Source hash verified rows: 14
- Source missing rows: 0
- Source hash mismatch rows: 0
- Training rows emitted: 0
- Mutated training package: False
- Validation eligible: False
- Test eligible: False

## Recommended rule actions

- `keep_display_export_as_noise_sidecar_not_training_target`: 11
- `manual_chain_boundary_review`: 2
- `move_evaluation_to_sidecar_or_extend_evaluation_extractor`: 1
- `retain_train_only_split_audit_note`: 7
- `rewrite_task_text_classification_claim_or_defer`: 2
- `rewrite_task_text_label_vector_claim_or_defer`: 2
- `rewrite_temporal_claim_or_defer`: 3

## Boundary

- Source-backed findings are rule-calibration evidence, not training admission.
- Operator and L3 sequences are copied unchanged from the precheck rows.
- GEE rows remain train-only and excluded from validation/test.
