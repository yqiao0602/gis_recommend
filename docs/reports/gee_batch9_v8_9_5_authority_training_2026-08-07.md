# GEE Batch9 v8.9.5 Train-Only Authority

## Decision

Batch9 v8.9.5 is admitted as an additive complete-workflow, train-only semantic
authority. It extends the prior frozen GEE package by 180 source-disjoint rows.
The package remains `operator_explicit`; it is not a leakage-controlled natural
language planning interface and is not validation/test or production data.

## Replay And Audit Evidence

- The only new rule is a fail-closed literal catalog temporal-coverage gate. It
  checks supported public `ee.ImageCollection` IDs only when both the collection ID
  and date bounds are literal. The full A/B replay rejected 24 workflows with
  `catalog_temporal_coverage_empty`; the two audited invalid-date sources are no
  longer candidates.
- From the Batch9 5,000-source selection, fidelity accepted 545 workflows from
  268 sources (six exact duplicates and 10,566 fail-closed). Typed mapping retained
  323 workflows from 140 sources; facts retained 312 bundles and 221 canonical
  task-text candidates from 121 sources. Expansion retained 180 proposals from 105
  eligible sources, with 41 duplicate sidecar rows and no length, semantic, or
  reviewed-source-overlap sidecar rows.
- The hash-bound 50-source full-source audit passed 50/50 with zero critical
  failures. Its Wilson 95% lower bound is `0.9286524008666414`; the evaluator
  decision is `passed_for_larger_source_disjoint_replay`. Forty-eight approved
  identities carried forward unchanged from v8.9.3 and two replacement identities
  were checked against complete source.

## Export And Loader Smoke

- A/B exports are byte-identical. Each adds 180 semantic and 180 V4-100 rows with
  zero new duplicates or length defers. The combined authority contains **8,151
  semantic rows, 8,150 V4-100 rows, and one existing 155-step length sidecar**.
- The A/B combined semantic input SHA256 is
  `dd19b9e635925dbd5aa3c7c1cdf785193d85ca4a8f8d320d0277ff6bf44d1186`; the
  combined V4-100 input SHA256 is
  `423de24cf7c757a7c1775faf3d388dc47facc3af58f28fdc0185eb16d5eae629`; the A/B
  loader smoke SHA256 is
  `ec4dcea8e6028dd0add05456f93e98553f159ba867f54cac314af1053bb37556`.
- In the server `transformer` environment (PyTorch `2.2.2+cu121`), the real
  `TaskConditionedL3DatasetV4`, weighted sequence loss, and backward smoke read
  8,150/8,150 rows in fifteen `[512,100]` batches and one `[470,100]` batch. Loss
  and gradients are finite; maximum L3 token is 93 and maximum model sequence length
  is 99. The frozen stable-94 mapping SHA is
  `005699dfd438e966cda28db8891795a07b9867856951de022cd8704c6e6a4558`.
- The smoke uses the preserved complete-workflow task vocabulary authority at
  `gee_complete_workflow_train_v1_20260731_g/task_type_vocab.json` (current SHA
  `989d8900a43b8694612803597d9427a2a00af3a2dead5c83e39441d7986a68c2`). No
  checkpoint or training epoch was written.

## Locations And Boundaries

Remote evidence root:
`/home/qy/system_redesign/diagnostics/gee_batch9_5000_v8_8_20260806/`.
Authoritative directories are
 `training_v8_9_5_catalog_temporal_filter_authority_a` and
`training_v8_9_5_catalog_temporal_filter_authority_b`; each contains
`loader_loss_smoke_v8_9_5.json`.

Rows are train-only. Validation/test admission, production merge, and model training
remain closed. The next GEE data action is a new source-disjoint selection under the
frozen v8.9.5 rules, followed by deterministic A/B replay and stratified sampling;
do not resume exhaustive per-row review or let an LLM infer workflow chains.

Local regression must run with `PYTHONPATH=src`: an outer legacy package otherwise
shadows this workspace's `gis_recommend` module. With that path fixed,
`tests/test_gee_workflow_fidelity_gate.py` and
`tests/test_smoke_gee_complete_workflow_training_package.py` report 40 passed and
one torch-dependent skipped test.
