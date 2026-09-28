# QGIS Workflow Admission v2: Gold/Silver Pilot

Date: 2026-08-12

## Scope

This bounded pass consumed only the 455 Processing workflow-tier candidates:
169 tier1 multi-step and 286 tier2 single-operator sources. It reread server
sources under SHA verification, ran AST/entrypoint extraction, catalog/alias
normalization, existing boundary checks, stable124 mapping, deterministic task
description, and four-layer deduplication. No LLM was called.

The result is a quality-tiered training pilot, not a promotion of 455 sources
to a workflow corpus or a change to the formal QGIS authority.

## Effective Funnel

| stage | rows | decision |
|---|---:|---|
| selected Processing candidates | 455 | input population |
| structural candidates | 70 | source SHA, AST, supported extraction, boundary, and stable124 mapping passed |
| deterministic description fidelity passed | 69 | one description deferred |
| Silver candidates after 294/508 dual-baseline four-layer dedup | 21 | source-verified train-only candidates |
| Gold candidates | 0 | independent semantic review is required and was not performed |
| Reject | 49 | baseline/local duplicate or a required gate failure |

Structural deferrals are retained in `summary_v1.json`: boundary=161,
extractor-unsupported=36, mapping=80, operator-resolution=108. These are
Reject/deferred evidence, not Silver training data.

## Silver Export

`silver_train_only_v1/qgis_silver_train_only_v1.jsonl` contains 21 rows with
21 unique source SHA256 values. Every row has:

- source SHA verification, deterministic operator/L3 alignment and source-AST
  parameter evidence;
- deterministic fidelity pass and no conflict with the 294 Processing or 508
  all-QGIS baselines under source-region, call-graph, normalized-DAG and
  training-pair keys;
- `training_admission=granted_train_only_qgis_silver_pilot_v1` and
  `sample_weight=0.7`;
- `validation_eligible=false`, `test_eligible=false`,
  `production_merge=not_granted`, and
  `gold_admission=not_granted_independent_semantic_review_required`.

The formal 508-row authority was not changed. Gold remains zero.

## Text and V4 Smoke

The real BERT tokenizer initially found four descriptions above 128 tokens.
They were compacted deterministically from their ordered operator chains; no
LLM was called. The repaired 21-row sidecar has 17 unchanged and 4 compacted
rows, with none deferred.

Because the Silver rows use stable124 content tokens (maximum 118), the smoke
uses an isolated stable124 runtime adapter rather than mutating the production
94/107 profiles. It used cached `bert-base-uncased`, the real
`TaskConditionedL3DatasetV4`, and the real
`weighted_sequence_cross_entropy`:

| check | result |
|---|---|
| BERT prompt length | 21/21 no truncation; maximum 122 tokens |
| V4 loader coverage | 21/21 rows across 6 batches |
| stable124 runtime | 124 content / 128 total tokens; max content token 118 |
| loss and gradient | finite |
| checkpoint or training run | none |

This validates only the data path for the isolated Silver pilot. It does not
authorize a production vocabulary profile, benchmark use, model training, or
authority merge.

## Reproducibility

Server root: `/home/qy/system_redesign/docs/reports/qgis_workflow_admission_v2_structural_replay_v1/`.

| artifact | SHA256 |
|---|---|
| Silver export | `137c39afd263aa343cf7dac9cc52f349c42e80d1f02e8138cceacbb0c2475fc3` |
| text-repaired Silver sidecar | `fa6ccd6555863d7d453c2cc61cf01e14c434647574dc0259fb85813565fb5129` |
| V4 smoke summary | `6faeee647db164d1862a52e1244a78d07ab0ceba1647910ee5472e097509af40` |

## Next Actions

1. Independently audit the 21 Silver source/task/operator chains before any
   Gold promotion; a failed semantic audit must not be relabeled Silver.
2. Keep Silver as a train-only isolated package. Do not modify the 508 formal
   authority, validation/test splits, benchmark, or checkpoints.
3. Resume extractor work only as a bounded entrypoint-family calibration after
   this output pilot, starting with one family and a source-disjoint holdout.
