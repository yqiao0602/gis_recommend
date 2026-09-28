# QGIS Processing Name-Binding Census v1

- Processing dynamic/blank-ID records scanned: 445
- Sources containing a `Name` first argument: 316
- `Name` first-argument calls: 997
- Fully normalized fixed chains: 83
- Existing route actions: 8 `auto_accept_candidate`, 35 `recover_call_graph`,
  32 `split_subworkflow`, 8 `review_api_sidecar`, 231 operator defers, and 2
  branch defers.
- All 8 auto candidates contain one operator. They violate the Processing
  two-to-six-operator training boundary and cannot be exported.
- Twenty fully normalized sources have two to six operators and need the
  existing call-graph or local-subworkflow splitter gate. Two additional
  two-operator sources are `review_api_sidecar` and remain outside that replay.
- Training rows emitted: 0
