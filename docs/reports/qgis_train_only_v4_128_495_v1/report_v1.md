# QGIS V4-128 Train-Only 495 v1

## Decision

`qgis_train_only_v4_128_495_v1.jsonl` is the current formal QGIS train-only
entrypoint. It contains 495 rows with SHA256
`7d94233ad3d37b5ea9e49a1d1ff01ebfac851304762360c630ad7a2e99e1de25`.
It supersedes the 492-row package, which remains reproducible provenance only.

## Point Geometry Increment

- `stable126` adds only `L3_01_01_05 Create Point Features from Coordinates`
  / token 125. It is restricted to the source-verified local macro
  `QgsGeometry.fromPoint/fromPointXY(QgsPoint/QgsPointXY) -> same-feature
  setGeometry -> target sink`; whole-function semantics are not claimed.
- The frozen proposal has 55 complete coordinate-pair macros from 54 normalized
  source-body authorities, with 22/33 calibration/holdout units and no source
  authority leakage. All 55 source-fact descriptions passed without an LLM.
- Four-layer dedup retained three semantically distinct training pairs by
  coordinate fact origin and suppressed 52 exact pairs. Cross-pool deduplication
  against the prior 492-row package suppressed zero additional rows.
- `Create Points from Table` was not used: that L3 requires proof that the
  coordinates originate in table fields, while this local macro permits any
  proven coordinate pair.

## Training-Path Gate

- Real local `bert-base-uncased` tokenization retained 495/495 rows at the
  fixed 128-token limit, with zero text deferrals.
- `TaskConditionedL3DatasetV4`, weighted sequence cross entropy, and backward
  covered all 495 rows in 16 batches with finite loss and gradients.
- The isolated smoke vocabulary contains 126 content tokens plus four special
  tokens. No training ran and no checkpoint was written.

The package is train-only. Validation/test use and production merge remain
ungranted. `admission_v1.json` is the hash-bound admission authority.
