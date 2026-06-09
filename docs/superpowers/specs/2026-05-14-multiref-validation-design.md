# Multi-Reference Validation Experiment Design

## Goal

Validate whether the current quality-gate workflow data can support reliable multi-reference supervision before any multi-reference training is attempted.

## Scope

This experiment is evaluation-only. It does not train models, mutate checkpoints, change the planner runtime, or claim final semantic equivalence. It generates local adjacent-swap workflow variants from empirically observed commutative-pair candidates, filters them with conservative automatic guards, and exports a stratified human-review sample.

The validation target is GEE/workflow-level multi-reference feasibility. Downstream QGIS landing is reported separately as a transferability signal and must not decide the primary MRV label.

## Inputs

- `outputs_v2/pipeline/step8_quality_gate/labeled_workflows_l3_v4_quality_gate.json`
- `outputs_v2/pipeline/step8_quality_gate/dataset_splits_v4_quality_gate.json`
- `outputs_v2/classification_hierarchy_v2.csv`
- `outputs_v2/id_mappings_v2.json`
- `outputs_v2/l3_vocab_v2.json`
- Train-split commutative pairs discovered with the existing canonicalized-evaluation logic.

## Stages

1. Generate variants from train workflows only. A variant swaps one adjacent token pair if the sorted pair is in the discovered commutative-pair set. Each workflow contributes at most a small bounded number of variants.
2. Apply automatic workflow-semantic validation. The original and variant must pass sensitive-step guards, semantic-usability gates, non-degradation checks, and length preservation. QGIS mapping and QGIS-chain checks are recorded only as auxiliary downstream landing signals. The output label is one of `verified_equivalent_candidate`, `plausible_variant`, `invalid_variant`, or `unknown`.
3. Export review artifacts. `human_review_sample.csv` is a stratified sample with auto-verified candidates and rejected controls. `equivalence_review_packet.csv` contains all auto-verified workflow-semantic candidates with readable L3 names and blank human-review fields. `verified_multi_reference_registry.json` is generated only from rows later marked `human_label=equivalent`.

## Sensitive Guards

Adjacent swaps are rejected when either swapped operator appears sensitive by name, description, or role. Sensitive categories include CRS/projection, resampling, nodata, mask, raster alignment, temporal semantics, thresholding, classification, zonal/statistical aggregation, and export.

## Metrics

- `variant_generation_count`
- `semantic_auto_pass_rate`
- `semantic_usable_rate`
- `strict_qgis_landing_usable_rate`
- `qgis_mapping_valid_rate`
- `qgis_io_valid_rate`
- `guard_pass_rate`
- `invalid_variant_rate`
- `task_family_coverage`
- `human_review_sample_count`
- `human_review_sample_by_auto_label`
- `equivalence_review_packet_count`
- `reviewed_equivalence_group_count`

## Outputs

Artifacts are written under `outputs_v2/v4_qg_multiref_validation/`:

- `multiref_validation_report.json`
- `multiref_validation_summary.md`
- `generated_variants.jsonl`
- `auto_verified_candidates.jsonl`
- `human_review_sample.csv`
- `equivalence_review_packet.csv`
- `verified_equivalence_registry.json`
- `verified_multi_reference_registry.json`
- `guard_rejection_breakdown.csv`
- `qgis_landing_rejection_breakdown.csv`
- `task_family_coverage.csv`

## Decision Contract

This experiment can only recommend multi-reference training if auto-verified workflow-semantic candidates are clean enough for manual review and the manual review later confirms low false-equivalence risk. QGIS landing failures may lower downstream transferability but cannot by themselves reject GEE workflow equivalence. Until reviewed registry coverage is sufficient, the production path remains candidate-based planning plus usability-oriented evaluation.
