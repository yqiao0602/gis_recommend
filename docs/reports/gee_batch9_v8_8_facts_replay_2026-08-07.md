# GEE Batch9 v8.8 Source/AST-Backed Facts A/B Replay

## Decision

Batch9 completed the frozen source/AST-backed facts replay. The two independent
runs are byte-identical. Facts and deterministic task-text candidates remain
non-admitted intermediate artifacts; they do not grant train-only status.

## Inputs And Verification

- Mapping-complete input SHA256:
  `f8e468e2438388effc32e5c2b62b22c4d460a628ebf25fdfa46d5a089f68ecec`
- Fidelity authority SHA256:
  `aef0a935d177aa5e2a19f24a5441e415fdfdb15d82fdb41c8e8acf942be34ac4`
- Publisher SHA256:
  `3a90a6847130165b6e4f1c3dd0fd70c6ac1b95f429aa473e956bbfb14764373e`
- Facts module SHA256:
  `36cd797ea449000af410c8cc58e89f1d29e20debd5dff277c6a8c054441f8fe0`

Both runs read sources only from `/home/yll/GEE/Data` and their corresponding
Batch9 AST directories. Each run's ledger records 294 verified source/AST paths.

## Results

- Mapping-complete input workflows: 355.
- Source/AST-backed fact bundles: 339.
- Fact fail-closed: 16.
- Task-text candidates before deduplication: 339.
- Exact task-text/L3 duplicates: 97.
- Canonical task-text candidates: 242 from 133 sources.
- Risk review packet: 50 deterministic rows.
- Training rows emitted: 0.

The 16 fact failures remain closed for unproven export input/output types, missing
definition IDs in the AST, one invalid static `filterDate` interval, or a non-geometry
export region. They are not repaired by the task-text layer.

## A/B Evidence

The A/B business artifacts are byte-identical:

- `workflow_fact_bundles.jsonl`:
  `0facc8e83bd20a805b1c5e785cf2edf57dc11d8684a715814f6ed6d36f6ad8f6`
- `task_text_candidates.jsonl`:
  `4a40fe57c8bcb36bcc6117a6a1fd649c5434dbf04f6583e718d3ea8a4a932901`
- `fact_fail_closed.jsonl`:
  `e8bf71db1f3b63e3113573846309bdc93f9f3f15c8d400ace1d6a3c1c13f04c2`
- `task_text_duplicates.jsonl`:
  `41761a7082a2de21f094500795a4c8c52b4de51247eca1f33ae4135c727afaca`
- `summary.json`:
  `871835291ec34eb6f0eb65d30118b6c4dea5cb3bb021e9b0f05ccca55417365a`

Remote evidence root:
`/home/qy/system_redesign/diagnostics/gee_batch9_5000_v8_8_20260806/`.
The authoritative directories are `facts_v8_8_authority_a` and
`facts_v8_8_authority_b`.

## Next Gate

Run the frozen expansion/proposal A/B process over the 242 canonical task-text
candidates. That stage must retain source lineage, apply cross-batch deduplication
and length sidecars, and still emit no train-only row until the required sampling
audit authorizes batch-level admission.
