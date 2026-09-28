# GEE Raster Core Batch Audit Precheck v1

This packet is for sampling-audit rule calibration over the deterministic
GEE raster-core batch package. It adds risk flags and blank human-review
fields to the 50-row audit sample without emitting or mutating training data.

## Result

- Input audit rows: 50
- Precheck rows: 50
- High-risk rows: 5
- Medium-risk rows: 14
- Low-risk rows: 31
- Rows requiring source lookup: 50
- Training rows emitted: 0
- Mutated training package: False
- Validation eligible: False
- Test eligible: False
- Review role: `sampling_audit_rule_calibration`

## Risk flags

- `advanced_temporal_text_without_temporal_operator`: 4
- `classification_text_without_classifier_operator`: 5
- `complex_or_long_chain_review_priority`: 5
- `display_or_export_language_requires_core_boundary_check`: 27
- `evaluation_text_without_evaluation_operator`: 3
- `prior_review_split_was_not_train_but_output_is_train_only`: 12
- `reducer_heavy_chain_review_priority`: 1
- `regional_statistics_text_without_regional_operator`: 1
- `threshold_mask_heavy_chain_review_priority`: 2
- `vector_or_training_label_text_without_vector_sampling_operator`: 6

## Boundary

- Risk flags are audit priorities, not automatic rejection labels.
- Final adjudication still requires source lookup; current evidence is path/hash only.
- Operator and L3 sequences are copied from the batch audit sample and are not edited here.
- This artifact does not promote GEE rows to validation/test and does not start training.
