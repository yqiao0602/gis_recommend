# QGIS API Raster Calculator train-only delivery v1

## Decision

- Admit 83 source-verified Raster Calculator local macros as isolated train-only rows.
- Reuse stable125 `L3_03_03_A` / token 34.
- Grant only the local `QgsRasterCalculator(...) -> processCalculation()` macro boundary.
- Do not claim whole-function semantics, validation/test eligibility, or production merge.

## Population and review

- Full family population: 116 complete local macro units across 59 normalized source bodies.
- Source-disjoint technical review: 20 calibration rows and 20 holdout rows.
- Calibration/holdout source SHA overlap: 0.
- Calibration/holdout normalized-body overlap: 0.
- Observed false positives: 0.
- Observed chain truncations: 0.

## Description and deduplication

- Deterministic description-ready units: 114.
- Deferred: 2 `dynamic_subscript` expression facts.
- Four-layer canonical training pairs: 83.
- Exact training-pair duplicates suppressed: 31.
- Cross-pool duplicates against the existing 365 QGIS train-only rows: 0.
- LLM calls: 0.

Descriptions use only source-recovered expression facts. Literal expressions are preserved as
their resolved value; f-strings and source expressions preserve the source construction;
Processing/runtime parameters receive a conservative generic description without inventing a
runtime value.

## Verification

- Train-only JSONL rows: 83.
- JSONL SHA256: `7d12a44625608250d97356d06a5091aba8e43c218cf8f98ac0bcd4c3b81d0a37`.
- Real V4 loader/weighted-loss/backward: 83/83 rows, 6 batches.
- Loss finite: true.
- Gradient finite: true.
- Checkpoint written: false.
- Training run: false.

Authoritative artifacts are in this directory. `hash_ledger_v1.json` binds the conversion inputs
and generated dataset artifacts; `loader_loss_smoke_v1.json` records the isolated runtime smoke.
