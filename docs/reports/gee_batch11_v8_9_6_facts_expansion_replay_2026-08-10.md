# GEE Batch11 v8.9.6 Facts and Expansion A/B Replay

## Decision

The frozen Batch11 population was replayed through source/AST-backed facts and
proposal expansion. All business artifacts and both hash ledgers are byte-identical
between A and B. No row is admitted as training data pending the frozen 50-source
full-source audit.

## Results

- Typed mapping input: 206 mapping-complete workflows from 125 sources.
- Facts: 200 bundles, 6 fail-closed.
- Task text: 200 pre-dedup candidates, 135 canonical candidates from 101 sources,
  65 duplicate sidecars.
- Expansion: 95 pending proposals from 78 eligible sources; 39 existing/batch
  duplicates; one over-length sidecar; zero semantic fail-closed rows.
- Audit packet: 50 source-disjoint rows with deterministic risk quotas
  `external_dynamic=11`, `long_or_repeated=15`, `multi_dataset_private=15`,
  `no_temporal_operation=2`, `other=1`, `spatial_omission=6`.
- Training rows emitted: 0. Validation/test/production merge: not granted.

## A/B Hashes

Expansion root:
`/home/qy/system_redesign/diagnostics/gee_batch11_5000_v8_9_6_20260808/proposal_v8_9_6_{a,b}/`

- `proposal_candidates.jsonl`: `5b615dcdfcffa90f74066bab8971ab2d79f03f82753caf2a41ab4f1ee7b952ae`
- `audit_sample_50.jsonl`: `c799bee2604d940b671681a6fe860783555f9252ff3c5afcc2f7939ce4445b6b`
- `summary.json`: `af3741dc6e1c1052505245bedff1864c39772ec25abc6c3940397d5696f15a66`
- `hash_ledger.json`: `0af3cc058c1d5f9289aecb65fe31a9bfad19cce79553c61c88d600bc6433b4ed`

## Next Gate

Complete the 50-row full-source semantic audit. A proposal can enter the train-only
export only after all six fidelity dimensions pass, no critical failure is present,
and the Wilson/precision admission policy succeeds. A failed audit must first prove
a reusable deterministic defect before any rule change or whole-batch replay.
