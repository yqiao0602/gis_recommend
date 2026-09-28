# Processing Expansion Calibration v1

## Scope

This package starts the next Processing expansion from the 8,466-source replay
population. It is calibration evidence only. It grants no L3 change, task
boundary rule promotion, training row, validation/test row, or production merge.

## Intake and Source Authority

- Baseline: 294-row `qgis_processing_aggregate_294_v1` authority.
- High-signal blocker lanes: `recover_call_graph`, `split_subworkflow`, and
  `defer_operator_resolution`.
- Source-SHA intake: 360 rows, 120 per lane. Relative to the 294-row authority,
  eligible sources were 187, 146, and 370 respectively.
- Server `/home/yll` verification: 319/360 source SHA verified; 41 missing
  source files were fail-closed. The verified rows contain 296 normalized source
  bodies.
- Cross-authority normalized-body dedup suppressed 3 rows already represented
  in the 294-row authority and 23 internal duplicates, leaving 293 canonical
  bodies.
- Final calibration packet: 200 rows, 100 calibration and 100 holdout. Lanes
  are 67 recovery, 67 split, and 66 operator-resolution. Calibration and
  holdout have zero overlap in both normalized body and source SHA.

## Boundary Replay

The first replay failed closed because ledger call sites used canonical
`native:<slug>` IDs while source literals used equivalent `qgis:<slug>` IDs.
The generic provider-alias verifier then accepted only AST-proven exact
`qgis:<slug> -> native:<slug>` migrations. It verified 200/200 rows with zero
provider/span failures before a second replay.

- Recovery: 67/67 parent sources replayed with zero failures; five strict local
  units were found under `recovery-multi-root-fanin-dag-v1`. Their independent
  support is calibration=4 and holdout=1, so promotion is not granted.
- Split: 67/67 parent sources replayed with zero failures; 327 local units were
  found, but only one strict multi-step unit passed description fidelity and it
  is holdout-only. Promotion is not granted.
- The 66 operator-resolution rows remain in the same source-disjoint packet but
  require their dedicated literal-ID resolver; they are not reclassified as
  boundary candidates.

## Decision

No row from this package is a training sample. The reusable artifacts are the
source-SHA intake selector, server source/body verifier, normalized-body
calibration splitter, and exact provider-alias verifier. The next batch must
census the remaining verified boundary/operator blockers by post-alias structural
signature, select only families with adequate independent support, then replay
the selected family and perform source-disjoint audit before export.

## Evidence

- `precalibration_selection_v1.jsonl`, `server_verified_sources_v1.jsonl`, and
  `server_verification_summary_v1.json` in the sibling
  `qgis_processing_expansion_precalibration_v2/` package.
- `calibration_holdout_manifest_v1.jsonl` and `summary_v1.json` in this package.
- Server replay artifacts: `docs/reports/qgis_processing_expansion_boundary_server_v2/`.
