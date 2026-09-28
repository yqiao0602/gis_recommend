# QGIS External Analysis Novelty Checkpoint (40 Sources)

## Scope

- 20 Processing blockers and 20 low-level API deferred sources.
- Source-disjoint by frozen normalized source body.
- Sidecar evidence only; no training admission, L3/catalog change, LLM call, or training.

## Verified Result

- Source SHA and normalized-body authority: 40/40 verified.
- Joern: 11 complete, 6 ambiguous, 23 insufficient, 0 query/runtime failure.
- DataTrove exact reconciliation: passed; MinHash remains report-only.
- Comparison hard gate: passed with 11 `joern_only_complete` and 29 `existing_only`.
- Zero source mismatch, false-complete evidence, claimed-complete truncation, Registry fallback, or incomplete provenance.

The checkpoint therefore authorized the bounded 200-source pilot. Promotion was not evaluated at this checkpoint and no rule family was admitted.

## Evidence Boundary

Large Joern/DataTrove sidecars, staged source copies, CPG files, and container outputs remain under `/home/qy/system_redesign/diagnostics/qgis_joern_pilot_v1/`. This directory stores only small summaries, comparison rows, and hashes.
