# GEE Raster Core Train-Only Schema v1

Date: 2026-07-24

This document defines the P1 row contract for converting reviewed GEE evidence
into train-only raster/L3 core-subworkflow supervision. It does not grant
dataset-level training admission, validation admission, or test admission.

## Purpose

The schema represents only the retained core analysis subworkflow. It is not a
full GEE script label and is not a QGIS operator-chain gold label.

P2 may rewrite task text against this contract. P3 may repair extractor gaps
and then emit rows against the same contract. Final token-id export remains a
separate later gate.

## Code authority

- Module: `src/gis_recommend/data/gee_raster_core_schema.py`
- Schema id: `gis_recommend.gee_raster_core_train_row.v1`
- Validator: `validate_core_train_row`
- Data class: `GeeRasterCoreTrainRow`
- Tests: `tests/test_gee_raster_core_schema.py`

## Required fields

| Field | Rule |
| --- | --- |
| `schema` | Must be `gis_recommend.gee_raster_core_train_row.v1` when present. |
| `source_platform` | Must be `GEE`. |
| `target_platform` | Must be `L3`. |
| `training_scope` | Must be `core_subworkflow`. |
| `review_id` | Non-empty source review id. |
| `script_id` | Non-empty source script id. |
| `task_name` | Non-empty chain-faithful task name. |
| `task_description` | Non-empty chain-faithful task description. |
| `l3_sequence` | Non-empty content L3 code list. No `<START>`/`<END>` or token ids. |
| `operator_sequence` | Non-empty GEE operator list, same length as `l3_sequence`. |
| `source_sha256` | Lowercase 64-character source content SHA256. |
| `source_path` | Non-empty source path/provenance string. |
| `evidence_snippet` | Non-empty source evidence snippet. |
| `admission_tier` | One reviewed train-only admission route. |
| `sample_weight` | Numeric and `0 < sample_weight <= 0.5`; default is `0.5`. |
| `validation_eligible` | Must be `false`. |
| `test_eligible` | Must be `false`. |
| `description_policy` | One approved chain-faithful description policy. |
| `known_omissions` | Sidecar list of omission notes; not model target text. |
| `review_split` | Optional original review split (`train`, `val`, `test`, or `train_only`). |

## Admission tiers

Allowed `admission_tier` values:

- `gee_core_p0_accept`
- `gee_core_p2_rewrite`
- `gee_core_p3_extractor_repair`
- `gee_core_p3_taxonomy_repair`
- `gee_core_p4_reviewed`

The P0 buckets `extractor_repair_required`, `taxonomy_or_mapping_gap`, and
`reject` are not valid training-row admission tiers. They must be repaired or
re-reviewed before any row can be emitted against this schema.

## Description policies

Allowed `description_policy` values:

- `original_core_faithful`
- `rewritten_chain_faithful`
- `template_chain_faithful`
- `manual_chain_faithful`

Descriptions must only state the retained core chain. Export, UI/map display,
charts, print/console output, full evaluation, and unresolved helper behavior
must stay out of `task_name` and `task_description`. If they matter for audit,
record them in `known_omissions`.

## P0 compatibility check

The validator was tested against the real P0 `accept_core_now` rows from:

- `docs/reports/gee_raster_core_v1_review_split_2026-07-24/gee_salvage_50_v1.csv`
- `docs/reports/gee_raster_core_v1_review_split_2026-07-24/source_evidence_snippets.jsonl`

All 9 `accept_core_now` rows can be represented under this schema when tagged
as `admission_tier=gee_core_p0_accept`, `description_policy=original_core_faithful`,
`validation_eligible=false`, and `test_eligible=false`.

## Non-goals

- No LLM description generation.
- No extractor repair.
- No expansion to 200 rows.
- No training export or token-id conversion.
- No promotion of GEE rows to validation/test.
- No treatment of GEE rows as QGIS operator-chain gold.

## Next gate

P2 should generate or manually curate chain-faithful task names/descriptions for
the `rewrite_description_then_train` bucket and validate any emitted candidate
against this schema. P3 should use the same validator after extractor repairs.
