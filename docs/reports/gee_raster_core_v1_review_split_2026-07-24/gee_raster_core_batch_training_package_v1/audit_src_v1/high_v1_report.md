# GEE Batch Source-Backed Audit Packet v1

This packet reviews the high-risk GEE batch audit-precheck cluster against
verified source files. It is used to decide whether systemic failures
should repair extractor/text/mapping rules or move rows to sidecars.

## Result

- Input precheck rows: 50
- Selected risk level: `high`
- Source-audit rows: 5
- Source hash verified rows: 5
- Source missing rows: 0
- Source hash mismatch rows: 0
- Training rows emitted: 0
- Mutated training package: False
- Validation eligible: False
- Test eligible: False

## Recommended rule actions

- `extend_extractor_for_temporal_module_or_sidecar_external_algorithm`: 1
- `keep_display_export_as_noise_sidecar_not_training_target`: 4
- `manual_chain_boundary_review`: 1
- `move_evaluation_to_sidecar_or_extend_evaluation_extractor`: 1
- `repair_extractor_or_l3_mapping_for_regional_statistics`: 1
- `retain_train_only_split_audit_note`: 2
- `rewrite_task_text_classification_claim_or_defer`: 3
- `rewrite_task_text_evaluation_claim_or_defer`: 1
- `rewrite_task_text_label_vector_claim_or_defer`: 1
- `separate_external_vector_context_from_core_operator_chain`: 3

## Boundary

- Source-backed findings are rule-calibration evidence, not training admission.
- Operator and L3 sequences are copied unchanged from the precheck rows.
- GEE rows remain train-only and excluded from validation/test.
