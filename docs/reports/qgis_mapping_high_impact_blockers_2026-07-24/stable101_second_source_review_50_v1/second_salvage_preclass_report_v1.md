# stable101 Second Batch Salvage Preclassification

This is deterministic machine preclassification for human review prioritization.
It is not adjudication and grants no training, validation, test, or production admission.
No LLM was called.

## Counts

- Rows: 50
- Full executable AST chains aligned: 45
- Task text review required: 18
- Classes: {'ready_now': 8, 'recoverable_call_graph': 20, 'split_subworkflow': 7, 'api_pattern_deferred': 10, 'exclude': 5}

## Review Order

- ready_now: [6, 10, 16, 21, 27, 41, 45, 49]
- recoverable_call_graph: [1, 4, 5, 8, 11, 12, 15, 17, 20, 23, 26, 28, 29, 30, 32, 33, 35, 37, 42, 50]
- split_subworkflow: [2, 3, 13, 18, 31, 34, 47]
- api_pattern_deferred: [19, 22, 24, 25, 38, 39, 40, 43, 44, 48]
- exclude: [7, 9, 14, 36, 46]

## Rule Boundary

- ready_now means structurally ready for human review, not training-ready.
- recoverable_call_graph requires deterministic entrypoint or DAG recovery.
- split_subworkflow contains disconnected lexical scopes that must be reviewed separately.
- api_pattern_deferred contains low-level transformations inside the proposed boundary.
- exclude means the current proposed chain lacks a complete executable AST alignment.
