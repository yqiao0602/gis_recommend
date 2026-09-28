# GEE Batch8 v8.8 Train-Only Authority

## Decision

Batch8 v8.8 is the current GEE semantic train-only authority. The hash-bound
exporter admitted the 3,469 source-disjoint proposals after the frozen 50-row audit
passed. This is an `operator_explicit` semantic authority only; it is not yet the
leakage-controlled natural-language planning interface.

## Evidence

- Controlled replay population: 17,585 sources, with A/B byte-identical DAG,
  fidelity, typed-mapping, fact, and expansion outputs.
- Proposal population: 3,469 workflows from 2,035 source-disjoint sources; audit:
  50/50 full-source pass, zero critical failures, and evaluator decision
  `passed_for_larger_source_disjoint_replay`.
- Export: 3,469 new semantic rows, zero export duplicates, zero new length defers.
  The combined package contains 7,971 semantic rows, 7,970 V4-100 rows, and one
  existing 155-step sidecar row.
- A/B hashes are identical: combined semantic rows
  `6323a2244cc807b08bb8f0d93689e47b7f2ff221b5233a79c7b53180d13b99d5`;
  combined V4-100 package
  `93adfc91f8f0740f1ba3a68786e74f55050175839461e8c95dfcc67fff21a59a`;
  hash ledger `176c09c5a41ed0213eb7ed3e31dbfaa23e23aa08e06904ab35e66aae37b11cc3`.
- Real `TaskConditionedL3DatasetV4` loader, weighted sequence loss, and backward
  smoke covered 7,970/7,970 rows in fifteen `[512,100]` batches and one
  `[290,100]` batch. Loss and gradients were finite; max L3 token was 93 and max
  model sequence length was 99. No checkpoint or training epoch was written.
  The A/B smoke hash is
  `85613ec212490417bbd247a637c6ec6d0b1414962b428509448ddce790bced39`.

## Mapping Authority Fix

The initial smoke correctly failed against remote
`outputs_v2/id_mappings_v2.json` because its SHA256 is
`7d9dde1ed6f36f0f2178d2ec535d9ecdaba9eb86639894581989b10f0b040946`, not the
frozen stable-94 authority. Rerunning with
`configs/taxonomy/inputs/id_mappings_v2.json` (SHA256
`005699dfd438e966cda28db8891795a07b9867856951de022cd8704c6e6a4558`) passed.
The smoke CLI now defaults to that frozen path, so a mutable `outputs_v2` mapping
cannot silently be used for GEE authority verification.

## Locations And Boundaries

Remote evidence root:
`/home/qy/system_redesign/diagnostics/gee_batch8_20000_v8_6_20260805/`.
The authoritative A/B directories are `training_v8_8_band_alias_authority_a` and
`training_v8_8_band_alias_authority_b`.

Rows remain train-only; validation, test, and production merge are not granted.
No model training was run. Before training for the paper's natural-language planning
objective, derive and audit the paired `goal_only` text view without operator names
or chain length. The next data-governance action is to freeze v8.8 and select a new
source-disjoint population for the same deterministic pipeline.
