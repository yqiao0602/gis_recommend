# QGIS API Add Field Existing-Layer train-only delivery v1

## Decision

- Admit 24 source-verified existing-layer Add Field local macros as isolated train-only rows.
- Reuse stable125 `L3_01_02_01 Add Field` / token 1.
- Grant only the 30-unit bounded population reviewed in v2; do not promote the family rule because normalized-body support is 23, below the support>=30 gate.
- Do not claim field-value calculation, whole-function semantics, validation/test eligibility, or production merge.

## Population and review

- Full-pool corrected replay screened 2,651 authorities and recovered 30 complete units across 23 normalized-body authorities.
- The corrected rule groups every same-layer `addAttribute(s)` before one `updateFields()` schema commit; the superseded v1 population with known chain truncations is not reused.
- All 30 candidate unit IDs are hash-bound into the review authority. Multiple units from one source remain in the same split.
- Source-disjoint review: 15 calibration rows and 15 holdout rows, covering the entire bounded population.
- Calibration/holdout source SHA overlap: 0.
- Calibration/holdout normalized-body overlap: 0.
- Observed false positives: 0.
- Observed chain truncations: 0.

## Description, mapping, and deduplication

- Deterministic descriptions use all recovered literal field names and do not infer field types from snippets.
- Description fidelity: 30 passed, 0 deferred; LLM calls: 0.
- Four-layer dedup retains 24 canonical training pairs and suppresses 6 exact duplicates.
- Cross-pool comparison against the existing 483 QGIS train-only rows suppresses 0 additional rows.
- Train-only JSONL SHA256: `320bce3f65d6e8573c20f32999000ebe43f88c017cc73954ca0803e2c9288c78`.

## Verification

- Train-only rows: 24.
- Real `TaskConditionedL3DatasetV4` loader/weighted-loss/backward: 24/24 rows, 2 batches.
- Loss finite: true.
- Gradient finite: true.
- Checkpoint written: false.
- Training run: false.
- Production merge: not granted.

The authoritative artifacts are in this directory. The review authority is in
`docs/reports/qgis_api_add_field_existing_layer_source_disjoint_review_v2/`.
