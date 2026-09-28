# GEE Batch12 v8.9.9 Snapshot Export And Loader Smoke

## Scope

This is the post-audit delivery gate for the 41 independent sources that
remained eligible after the frozen v8.9.9 snapshot replay. It is a train-only
candidate package; validation/test eligibility, production merge, and model
training remain closed.

## Hash-bound export

The exporter accepted only the 41 audited rows with verified source SHA256,
`human_decision=pass`, `human_critical_failure=no`, and all six fidelity fields
set to `pass`. No LLM was called and no chain was changed.

Package: `/home/qy/system_redesign/diagnostics/gee_batch12_5000_v8_9_9_20260810/export_snapshot_authority_41/`

| Quantity | Result |
| --- | ---: |
| audited/adjudicated rows | 41 |
| semantic complete-workflow rows | 41 |
| V4-100 rows | 41 |
| length sidecar | 0 |
| duplicate sidecar | 0 |
| fail-closed sidecar | 0 |
| maximum semantic content length | 18 |
| maximum model sequence length | 20 |

Hash ledger: `hash_ledger.json`. Stable-94 mapping SHA256 is
`005699dfd438e966cda28db8891795a07b9867856951de022cd8704c6e6a4558`.

## Real loader/loss/backward smoke

The package was exercised with `TaskConditionedL3DatasetV4`, the production
weighted sequence cross-entropy, and backward. All 41 rows were seen in two
batches (`[32,100]`, `[9,100]`); loss and gradients were finite, max token was
92, and no checkpoint was written. Summary:

`loader_loss_smoke.json` (`input_sha256=ed1889f036833ec7eeb14d9649a7b7ebef8dc5ec4fb5f33df3eb5f297505c923`).

The server's default Python environment has no `torch`; therefore this smoke
was run with the repository's local PyTorch 2.7.1 CPU environment against the
hash-bound package copied from `/home/qy`. This is an environment limitation,
not a data failure, and must be rerun on the training host before model
training.

## Decision

The 41 rows pass the GEE package export and loader/loss gates and are eligible
for an incremental `train-only` authority manifest. They are not validation,
test, production-merge, or model-training data. The next production action is
to merge this package into the cumulative GEE train-only manifest, then select
a new source-disjoint batch using the same converter and stratified audit.
