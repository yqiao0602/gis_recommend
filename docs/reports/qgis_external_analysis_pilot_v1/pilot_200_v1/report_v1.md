# QGIS External Analysis Pilot (200 Sources)

## Scope

- 100 Processing blockers and 100 low-level API deferred sources.
- 200/200 source SHA values verified and 200 normalized source bodies unique.
- Fixed source-prefix alias used for three model-tutorial files.
- Sidecar evidence only; no training admission, L3/catalog change, LLM call, or training.

## Verified Result

- Joern: 31 complete, 17 ambiguous, 152 insufficient, 0 query/runtime failure.
- Joern normalized SHA256: `ee80881b3a0fb1147f2fe533a7d62c75bd1ef73a6045f5356713be2949ecea4e`.
- DataTrove exact reconciliation: passed; dual runs are byte-identical; MinHash reports 29 near-duplicate clusters without filtering.
- DataTrove normalized SHA256: `737310af4149155a14af76699c1300bef647a27cb2bcc0c54b0f8f33938bc210`.
- Comparison hard gate: passed with 31 `joern_only_complete` and 169 `existing_only`.
- Zero source mismatch, false-complete evidence, claimed-complete truncation, Registry fallback, or incomplete provenance.

## Novelty Difference

Lexical-scope verification showed that only 7 of the 31 complete rows contain Joern paths that actually cross Python function boundaries. The remaining 24 are local dataflow and are not counted as unique Joern capability.

- API cross-function parameter/return dataflow: support 5.
- Processing cross-function parameter/return dataflow: support 2.

Both families are below the support>=30 promotion threshold. No source-disjoint calibration/holdout was authorized, the promotion gate failed closed, and no family was adopted into the production extractor.

## Decision

The pilot proves that Joern, QGIS Registry, and DataTrove can run reproducibly and provide a small cross-function evidence delta. It does not prove enough family-level value to justify broader Joern rollout. Stop expansion at 200 sources and return to the QGIS source-to-training-data mainline. DataTrove exact remains useful as an authority reconciliation check; Registry differences remain report-only.

Large sidecars, staged source copies, CPG files, and container outputs remain under `/home/qy/system_redesign/diagnostics/qgis_joern_pilot_v1/`. This directory stores only small summaries, novelty evidence, comparison rows, and hashes.
