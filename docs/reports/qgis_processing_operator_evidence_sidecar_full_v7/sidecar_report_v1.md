# QGIS Processing operator evidence sidecar v1

Source-backed evidence only; no L3 mapping or training rows are emitted.

- Input rows: **47852**
- Operator input rows: **591**
- Expected-row check: **matched**
- Source-verified rows: **591**
- Call-evidence rows: **591**
- Static parameter-dict call rows: **511**
- Static INPUT/OUTPUT-key call rows: **438**
- I/O evidence call rows (including positional): **504**
- Provider-prefix evidence call rows: **589**
- Status counts: `{"source_verified_ast": 591}`
- Reason counts: `{}`
- Parameter status counts: `{"deferred": 12, "verified_positional_arguments": 68, "verified_static_dict": 511}`
- Parameter binding counts: `{"inline_static_dict": 287, "missing_parameter_argument": 2, "name_to_static_assignment": 224, "positional_processing_api": 68, "unresolved_name_binding": 10}`
- Parameter completeness counts: `{"parameter_unresolved": 12, "static_parameter_complete": 50, "static_parameter_partial": 529}`
- Parameter defer reasons: `{"interfering_write_before_call": 5, "no_dominating_assignment": 5, "parameter_expression_not_static_dict": 2}`
- Name-binding rule: `dominating_same_scope_static_dict_v2`
- Name-bound accepted calls: **224**
- Name-bound provenance: `{"assignment_lineno": 224, "assignment_scope_verified": 224, "assignment_span": 224, "dominance_verified": 224, "mutation_guard_verified": 224}`
- L3 mapping changed: **false**
- Training rows emitted: **0**
