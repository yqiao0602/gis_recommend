# QGIS V4-128 Train-Only 498 v1

## Decision

`qgis_train_only_v4_128_498_v1.jsonl` is the current formal QGIS train-only
entrypoint. It has 498 rows and SHA256
`7aa61adddf5faa0ea77ed74be4df8a65d5dbbf35b271c214e1bb032cc8dec5e9`.
It supersedes the 495-row entrypoint, retained only as reproducible provenance.
The preliminary `qgis_api_polyline_geometry_train_only_v1/` export is
superseded by v2: its evidence-string check did not recognize the already
AST-verified instance-style `QgsGeometry().fromPolyline(...)` form. V2 restores
that complete macro without relaxing the AST boundary contract.

## Polyline Geometry Increment

- The strict local-macro contract is `QgsGeometry.fromPolyline/fromPolylineXY`
  with an explicit literal or unique same-control-path literal vertex sequence,
  followed by same-feature `setGeometry` and a literal single-feature sink.
- A 200-source calibration produced source-SHA-disjoint complete subsets of
  9 calibration and 9 holdout macros. The full replay verified all 611 input
  units and retained 54 complete macros from 34 normalized-source authorities;
  557 ambiguous or incomplete records remained fail-closed.
- `stable127` adds only `L3_01_01_06 Create Polyline Features from Vertices`
  / token 126. It describes the verified local macro, not the enclosing script
  or dataset-creation task.
- All 54 descriptions are deterministic source facts and use no LLM. Four-layer
  dedup suppresses 51 exact training-pair copies and retains three distinct
  pairs. Cross-pool deduplication against the prior 495-row package suppresses
  zero additional rows.

## Training-Path Gate

- Local real `bert-base-uncased` tokenization accepts 498/498 rows at the fixed
  128-token limit; no text row is deferred.
- `TaskConditionedL3DatasetV4`, weighted sequence cross entropy, and backward
  cover all 498 rows in 16 batches with finite loss and gradients.
- The smoke vocabulary has 127 content tokens plus four special tokens. No
  training ran and no checkpoint was written.

The package is train-only. Validation/test use and production merge remain
ungranted. `admission_v1.json` is the hash-bound admission authority.
