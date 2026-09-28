# stable101 QGIS Salvage Ledger

Deterministic salvage classification for the 50-row source-backed review.
No LLM was called. This report does not grant training admission.

## Summary

- Rows: 50
- Decision counts: {'accepted': 19, 'deferred': 3, 'rejected': 28}
- Salvage classes: {'ready_now': 19, 'recoverable_call_graph': 8, 'split_subworkflow': 13, 'api_pattern_deferred': 5, 'exclude': 5}
- Expected rows after follow-up: 53
- Candidate after follow-up: 45

## Class Definitions

- ready_now: accepted source-backed chain; eligible for the first export gate.
- recoverable_call_graph: recover entrypoint, repeated calls, branches, or DAG.
- split_subworkflow: split independent functions/examples into local units.
- api_pattern_deferred: model low-level API/custom intermediates before admission.
- exclude: exclude the current file-level candidate from Processing gold.

## Class Review Indices

- ready_now: [1, 8, 12, 15, 17, 19, 20, 22, 25, 26, 27, 31, 32, 35, 39, 43, 44, 46, 50]
- recoverable_call_graph: [3, 4, 5, 6, 7, 18, 30, 42]
- split_subworkflow: [9, 10, 11, 13, 23, 24, 29, 34, 36, 37, 38, 40, 48]
- api_pattern_deferred: [16, 21, 28, 33, 49]
- exclude: [2, 14, 41, 45, 47]
