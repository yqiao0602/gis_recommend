# stable101 Second Batch Salvage Preclassification

This is deterministic machine preclassification for human review prioritization.
It is not adjudication and grants no training, validation, test, or production admission.
No LLM was called.

## Counts

- Rows: 179
- Full executable AST chains aligned: 163
- Task text review required: 90
- Classes: {'ready_now': 29, 'recoverable_call_graph': 74, 'split_subworkflow': 26, 'api_pattern_deferred': 34, 'exclude': 16}

## Review Order

- ready_now: [15, 18, 22, 47, 56, 60, 63, 68, 88, 91, 96, 101, 113, 116, 117, 119, 120, 121, 131, 135, 140, 143, 144, 157, 167, 172, 174, 175, 176]
- recoverable_call_graph: [1, 3, 4, 6, 7, 8, 9, 10, 12, 16, 19, 21, 24, 27, 30, 31, 32, 35, 36, 40, 42, 43, 44, 46, 48, 51, 57, 65, 69, 70, 71, 72, 74, 76, 78, 80, 81, 83, 84, 90, 94, 102, 104, 106, 107, 108, 110, 111, 112, 114, 115, 122, 123, 126, 127, 128, 132, 133, 136, 138, 145, 146, 147, 149, 151, 155, 159, 160, 161, 165, 166, 168, 171, 177]
- split_subworkflow: [2, 5, 14, 23, 28, 34, 38, 41, 49, 50, 62, 67, 77, 79, 85, 89, 100, 103, 124, 129, 137, 152, 154, 158, 162, 173]
- api_pattern_deferred: [13, 17, 20, 25, 26, 29, 33, 37, 39, 53, 54, 55, 58, 59, 64, 66, 86, 87, 93, 97, 98, 109, 118, 125, 130, 141, 150, 153, 156, 163, 164, 169, 170, 179]
- exclude: [11, 45, 52, 61, 73, 75, 82, 92, 95, 99, 105, 134, 139, 142, 148, 178]

## Rule Boundary

- ready_now means structurally ready for human review, not training-ready.
- recoverable_call_graph requires deterministic entrypoint or DAG recovery.
- split_subworkflow contains disconnected lexical scopes that must be reviewed separately.
- api_pattern_deferred contains low-level transformations inside the proposed boundary.
- exclude means the current proposed chain lacks a complete executable AST alignment.
