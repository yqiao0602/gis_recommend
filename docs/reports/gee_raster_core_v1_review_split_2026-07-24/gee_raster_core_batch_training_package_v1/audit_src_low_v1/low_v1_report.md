# GEE Batch Source-Backed Audit Packet v1

This packet reviews a selected GEE batch audit-precheck risk cluster against
verified source files. It is used to decide whether systemic failures
should repair extractor/text/mapping rules or move rows to sidecars.

## Result

- Input precheck rows: 50
- Selected risk level: `low`
- Source-audit rows: 31
- Source hash verified rows: 31
- Source missing rows: 0
- Source hash mismatch rows: 0
- Training rows emitted: 0
- Mutated training package: False
- Validation eligible: False
- Test eligible: False

## Recommended rule actions

- `keep_display_export_as_noise_sidecar_not_training_target`: 12
- `manual_chain_boundary_review`: 2
- `no_source_backed_rule_change_suggested`: 14
- `retain_train_only_split_audit_note`: 3

## Boundary

- Source-backed findings are rule-calibration evidence, not training admission.
- Operator and L3 sequences are copied unchanged from the precheck rows.
- GEE rows remain train-only and excluded from validation/test.
