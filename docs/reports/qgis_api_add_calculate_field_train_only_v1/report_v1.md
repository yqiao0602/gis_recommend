# QGIS Add Field -> Calculate Field train-only delivery v1

- Source-verified input: 30 complete local macros / 28 normalized-body authorities.
- Review: source-disjoint 14 calibration + 14 holdout authorities; FP=0 and chain truncation=0.
- Description fidelity: 30/30 source-fact-only; no LLM call.
- Four-layer dedup: 15 canonical training pairs and 15 exact-pair suppressions.
- Cross-pool dedup: 0 overlaps against the existing 350-row QGIS train-only authority.
- Delivery: 15 net-new train-only rows using stable125 tokens `[1, 4]` and model sequences
  `[-3, 1, 4, -4]`.
- V4 loader/weighted-loss/backward: 15/15 rows, 4 batches, finite loss and gradients.
- No training or checkpoint write occurred. Validation/test eligibility and production merge remain ungranted.

Train-only JSONL: `qgis_api_add_calculate_field_train_only_v1.jsonl`.
