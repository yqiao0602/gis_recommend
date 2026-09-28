# QGIS V4-128 Train-Only 492 v1

## Decision

The current formal QGIS V4-128 train-only entrypoint contains 492 rows. It
combines the prior 491-row authority with one deduplicated, source-verified
geometry-difference local macro.

## Geometry Difference Increment

- The authority-bound population contains 31 units from 18 normalized source
  bodies; source SHA replay passed for 31/31 units.
- The strict local contract accepted 25 units from 17 authorities. It requires
  a geometry operand, a guarded loop-carried `difference` accumulator,
  `setGeometry`, and a verified feature sink.
- Four units with another write of the same output feature inside a repeated
  loop and two units with post-difference geometry transforms remain deferred.
- Full-population calibration/holdout partitioning has zero source/body
  overlap. Observed false positives and chain truncations are both zero.
- Deterministic source-fact descriptions passed for 25/25 accepted units.
  Four-layer deduplication retained one training pair and suppressed 24 source
  copies; cross-pool duplication against the prior 491 rows is zero.
- No LLM was called and no L3 was added. The increment reuses stable125
  `L3_02_02_04` / token 11. Because support is below 30, no automatic family
  promotion is granted.

## Training-Path Gate

- Real `bert-base-uncased` tokenization retained 492/492 rows at the fixed
  128-token text limit; maximum observed prompt length was 128 tokens.
- `TaskConditionedL3DatasetV4`, weighted sequence loss, and backward covered
  492/492 rows in 16 batches with finite loss and gradients.
- No training ran and no checkpoint was written.

The dataset is train-only. Validation/test use and production merge remain
ungranted. `admission_v1.json` is the final admission authority; the generic
generated `summary_v1.json` field `semantic_audit_status=pending` is not the
final semantic decision.
