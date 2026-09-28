# GEE Complete-Workflow Train Export Design

## Goal

Convert the closed 50-workflow rulefix2 review into the first source-backed,
complete-output-workflow GEE train-only package without admitting unreviewed
candidates or changing QGIS, benchmark, taxonomy, or model-training state.

## Scope

The authority input is the byte-exact rulefix2 task-facts directory at
`/home/qy/system_redesign/diagnostics/gee_workflow_task_facts_pilot500_20260730_rulefix2_a`.
The review packet SHA256 is
`c33b1528f98b4ed4a0a2e9a1d2dd021d6eb0f61295ea2ce38a1c02101b6a023f`.
The closed adjudication is 47 `pass` and 3 `defer_source_ambiguity`. One passing
workflow has 155 content operators and is not eligible for the current V4-100
loader.

This phase does not admit the remaining 126 canonical candidates, recover the
131 mapping gaps, modify `outputs_v2`, create validation/test rows, merge a
production dataset, or run model training.

## Schema

Add `gis_recommend.gee_workflow_train_row.v1` with
`training_scope=complete_output_workflow`. Its stable identity is
`(source_sha256, workflow_id)`. A valid row must contain:

- source identity and exact DAG fingerprint;
- source-backed task name and description;
- non-empty, position-aligned canonical GEE operator and L3-code sequences;
- hashes of the exact fact bundle, task-text candidate, adjudication row, and
  authority inputs used to construct it;
- `adjudication_decision=pass`, train-only admission, and explicit exclusion
  from validation, test, and production merge;
- a bounded sample weight and no unresolved source ambiguity.

The schema validator is dependency-free and fail-closed. It does not accept the
old `core_subworkflow` contract or special/model token IDs in the semantic row.

## Adjudication Freeze

A compact decision ledger is hash-bound to the 50-row review packet and the
formal review report. It records the closed default decision (`pass`), exact
expected counts, and three explicit defer exceptions. A freeze command verifies
the packet hash, row count, unique identities, exception identities, and output
counts before emitting an explicit 50-row adjudication manifest. Missing,
additional, or duplicated identities are fatal.

## Export Gates

The exporter joins the explicit adjudication manifest, risk packet, fact
bundles, and deduplicated task-text candidates by workflow identity. For every
passing row it verifies:

1. source SHA/path/workflow identity agrees in all artifacts;
2. fact status is source-backed complete;
3. exact DAG fingerprint and output fact exist;
4. task-text clauses reference existing fact IDs;
5. operator and L3 sequences agree position-for-position across artifacts;
6. the row remains canonical under normalized task name, description, and L3
   sequence deduplication;
7. every L3 code resolves exactly in the frozen 94-L3 mapping;
8. V4 model sequence length is calculated without truncation.

The three deferred rows are written to a fail-closed sidecar. The 155-step pass
is written to a length sidecar. Only passing rows whose model sequence is at
most 100 tokens enter the current-loader package. The expected upper bound is
46 rows; any count drift is fatal for this frozen package.

## Outputs

The versioned package contains:

- `adjudication_manifest.jsonl` with 50 explicit decisions;
- `semantic_train_rows.jsonl` for all schema-valid passing rows, including the
  long-chain row;
- `train_v4_100.json` with current-loader eligible train-only rows;
- `length_sidecar.jsonl` with the 155-step workflow;
- `fail_closed_sidecar.jsonl` with the three source-ambiguity workflows;
- `task_type_vocab.json`, `summary.json`, `hash_ledger.json`, and `report.md`.

All outputs are deterministic and atomically written. Repeating the build from
the same authorities must produce byte-identical data artifacts.

## Verification

Tests first cover schema rejection, hash-bound adjudication expansion, join and
fact-reference failures, chain/L3 mismatch, duplicate suppression, length
routing, and the expected 46/1/3 partition. The production artifact is then
built twice on the server and compared byte-for-byte. Finally the real V4
dataset and weighted sequence loss run over all 46 current-loader rows with
finite loss and gradients, no checkpoint, no training epoch, and no production
merge.

