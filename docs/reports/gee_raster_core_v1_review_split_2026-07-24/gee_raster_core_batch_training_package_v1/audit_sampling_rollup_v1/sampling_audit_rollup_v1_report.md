# GEE Batch Sampling-Audit Rollup v1

This report aggregates the completed high/medium/low source-backed
sampling audit sidecars for the 50-row GEE batch audit sample.

## Result

- Source-audit rows: 50
- Source hash verified rows: 50
- Rule proposal rows: 50
- Deterministic rewrite sidecar candidates: 3
- Schema-valid train-only sidecar candidates: 3
- Deferred/backlog rows: 47
- Training rows emitted: 0

## Risk layers

- `high`: source=5, rewrite=2, backlog=3
- `medium`: source=14, rewrite=1, backlog=13
- `low`: source=31, rewrite=0, backlog=31

## Policy candidates

- `generic_rule_review_fail_closed` support=39: keep generic rule-review rows fail-closed; do not use them to change or admit training rows
- `display_export_noise_sidecar` support=27: always keep display/export/UI evidence as sidecar unless a separate export target is explicitly admitted
- `external_context_sidecar` support=6: record external context as provenance/sidecar; do not add it to target chains by inference
- `manual_boundary_review_fail_closed` support=4: keep manual-boundary rows out of training until a bounded structural rule is approved
- `rule_repair_before_regeneration` support=4: repair rule families first; regenerate only through an explicit batch gate
- `evaluation_metrics_sidecar` support=2: keep evaluation/confusion/accuracy as sidecar unless an evaluation-operator taxonomy rule is admitted

## Boundary

- Rollup output is calibration evidence only.
- It does not append to or rewrite `train11397_full.json` / `train11397_v4_100.json`.
- GEE rows remain train-only and validation/test ineligible.
