# GEE Batch7 10,000-source v8.6 authority and training delivery

Date: 2026-08-05

## Scope

This phase converts a fresh 10,000-source, source-disjoint GEE batch into complete
output-relevant train-only workflow rows. It does not admit validation/test data,
merge production data, or run model training. `/home/yll` remained read-only and
large artifacts were written under `/home/qy`.

Server authority root:

`/home/qy/system_redesign/diagnostics/gee_batch7_10000_v8_4_20260804`

The frozen stable-94 mapping SHA256 is
`005699dfd438e966cda28db8891795a07b9867856951de022cd8704c6e6a4558`.

## v8.6 rule correction

The DAG gate now rejects native JavaScript arithmetic/logical operations over EE
objects when they are part of an exported payload dependency closure. It treats
`getInfo()` output as a client value and limits receiver/type ownership in a
multi-declarator statement to each declarator's initializer.

The targeted source replay correctly rejects one `ee.Image - ee.Image` workflow and
three EE Image `&&` workflows while preserving four valid client-side patterns. In
the full 10,000-source replay, exactly four sources move from passed to fail-closed
relative to v8.5; no previously admitted workflow changes.

Local focused verification completed with 37 tests passed and one optional smoke
test skipped. The server replay provides the production-scale regression evidence.

## Deterministic population

The v8.6 DAG A/B authorities are byte-identical. Their `workflow_dags.jsonl` SHA256
is `cb28b823e56b642621bdc3197b110e070ecdedf02f4716b9f6bc19bbfb521e49`.

Population counts:

- selected sources: 10,000
- AST success: 9,993
- DAG passed / partial / fail-closed: 3,029 / 311 / 6,653
- fidelity-passed workflows: 6,280 from 3,127 unique sources
- mapping-complete workflows: 3,809 from 1,882 unique sources
- fact bundles / fact fail-closed: 3,605 / 204
- canonical task candidates / text duplicates: 2,490 / 1,115
- proposal rows / eligible sources: 2,235 / 1,321
- length-deferred candidates: 7

All downstream fidelity, typed mapping, facts, and expansion A/B business artifacts
are byte-identical. The proposal authority SHA256 is
`98fcf9de5e46dd32519e35e14dbdb0a3b13160226c5c778c7667dd522ee21369`.

## Sampling audit

The v8.6 and v8.5 audit samples share 49 identities, and their complete semantic
authority projections are unchanged. Those 49 prior full-source PASS decisions are
carried by `(source_sha256, workflow_id)`. The removed identity is the confirmed
native-operator critical failure at `data170000/script_169132.txt`. The replacement,
`data160000/script_150169.txt` / `output-workflow-3`, was explicitly reviewed against
full source and passed all six fidelity dimensions.

Final evaluation:

- reviewed rows: 50
- pass / fail: 50 / 0
- point precision: 1.0
- Wilson 95% lower: 0.9286524008666414
- critical failures: 0
- decision: `passed_for_larger_source_disjoint_replay`

The reviewed audit SHA256 is
`db4ffde7c9da6bcf67307e877557b429b50cfdd1837ff589a1bc752a0513e805`.
The evaluation profile and identity-bound adjudication manifest are stored beside
this report as `gee_batch7_v8_6_evaluation_profile.json` and
`gee_batch7_v8_6_adjudication_manifest.json`. The original/reviewed audit rows,
source manifest, expansion ledger, prior v8.5 review, and 192-row reviewed exclusion
packet are synchronized under `docs/reports/gee_batch7_v8_6_authority_audit/`.

## Train-only delivery

The hash-bound exporter admits all 2,235 same-rule proposals. It emits zero duplicate
rows and zero new length defer. Combined with the Batch6 authority, delivery counts
are:

- complete semantic rows: 4,502
- current-loader V4-100 rows: 4,501
- length sidecar: one existing 155-step workflow
- validation/test eligibility: false
- production merge: not granted

Training A/B directories are byte-identical across all artifacts:

- `training_v8_6_authority_a`
- `training_v8_6_authority_b`

The combined semantic JSONL SHA256 is
`2bdb56c0c586f49074c4a286180230fd288edc8fac7d97491806ba360ba6a2a7`.
The combined V4-100 JSON SHA256 is
`371d8cb4d05e024b5e86d40996bc3b3fb19a9448b4cef2055f5f08ed8471c4ea`.

## Loader/loss/backward smoke

Both A and B packages were exercised under
`/home/qy/miniconda3/envs/transformer` with the real
`TaskConditionedL3DatasetV4`, weighted loss, and backward path.

- rows loaded and seen: 4,501 / 4,501
- batches: eight `[512,100]` plus one `[405,100]`
- mean smoke loss: 4.584968090057373
- loss finite / gradient finite: true / true
- max L3 token: 93
- max model sequence length: 99
- checkpoint written: false
- training epoch run: false

Smoke A/B directories and summaries are byte-identical:

- `smoke_v8_6_authority_a`
- `smoke_v8_6_authority_b`

## Decision and next gate

Batch7 is admitted as train-only complete-workflow data. The cumulative 4,000-row
gate is complete. Freeze v8.6 and continue with a new source-disjoint population,
using deterministic full-population gates plus one 50-row stratified full-source
audit. Only a systematic sampled failure may change a reusable rule and trigger one
whole-batch replay. Do not return to per-row production review.

The 57 legacy or unverified public dataset IDs remain a separate authority queue and
do not block this delivery. Fuzzy matching, embedding similarity, or automatic
dataset-ID replacement cannot grant admission.
