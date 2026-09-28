# GEE Batch Source-Backed Rewrites

This packet rewrites only the source-backed rows that were routed as
train-only text-rewrite candidates. It keeps the frozen operator/L3
chains unchanged and writes the other sampled audit rows to a
fail-closed rule backlog.

## Result

- Output prefix: `rewrite_candidates_low_v1`
- Rule-proposal rows: 31
- Rewrite candidates: 0
- Schema-valid train-only candidate rows: 0
- Deferred backlog rows: 31
- Training rows emitted into train11397 package: 0
- Validation rows emitted: 0
- Test rows emitted: 0
- Training admission: `not_granted_rewrite_sidecar_schema_gate_passed`
- Production merge: `not_granted`
- LLM used: `False`

## Rewritten rows

## Deferred rule backlog

- `defer_generic_rule_review` / `gee_raster_core_batch_v1_53050140bfa81086`: keep fail-closed until a source-backed rule owner resolves this decision
- `defer_generic_rule_review` / `gee_raster_core_batch_v1_706e19da019c6042`: keep fail-closed until a source-backed rule owner resolves this decision
- `defer_generic_rule_review` / `gee_raster_core_batch_v1_e3aff3db2d771318`: keep fail-closed until a source-backed rule owner resolves this decision
- `defer_generic_rule_review` / `gee_raster_core_batch_v1_db893d3f37eb1658`: keep fail-closed until a source-backed rule owner resolves this decision
- `defer_generic_rule_review` / `gee_raster_core_batch_v1_2a5d812e161bf1e1`: keep fail-closed until a source-backed rule owner resolves this decision
- `defer_generic_rule_review` / `gee_raster_core_batch_v1_290b208f158e8601`: keep fail-closed until a source-backed rule owner resolves this decision
- `defer_generic_rule_review` / `gee_raster_core_batch_v1_c76d8471905ff9bd`: keep fail-closed until a source-backed rule owner resolves this decision
- `defer_manual_boundary_review` / `gee_raster_core_batch_v1_aa1fd1460731394e`: review external vector/training-label boundary and retained chain scope before admission
- `defer_generic_rule_review` / `gee_raster_core_batch_v1_458c7ae9e165a573`: keep fail-closed until a source-backed rule owner resolves this decision
- `defer_generic_rule_review` / `gee_raster_core_batch_v1_349e42a3eef4aefc`: keep fail-closed until a source-backed rule owner resolves this decision
- `defer_generic_rule_review` / `gee_raster_core_batch_v1_0c8e9110caf5758c`: keep fail-closed until a source-backed rule owner resolves this decision
- `defer_generic_rule_review` / `gee_raster_core_batch_v1_de33f1db271835d8`: keep fail-closed until a source-backed rule owner resolves this decision
- `defer_generic_rule_review` / `gee_raster_core_batch_v1_087edc464479f090`: keep fail-closed until a source-backed rule owner resolves this decision
- `defer_generic_rule_review` / `gee_raster_core_batch_v1_9345e8dece2c8bf9`: keep fail-closed until a source-backed rule owner resolves this decision
- `defer_generic_rule_review` / `gee_raster_core_batch_v1_77ca7766f014f94b`: keep fail-closed until a source-backed rule owner resolves this decision
- `defer_manual_boundary_review` / `gee_raster_core_batch_v1_8a8b62b60c4cedbe`: review external vector/training-label boundary and retained chain scope before admission
- `defer_generic_rule_review` / `gee_raster_core_batch_v1_bbb16f8fd43667e7`: keep fail-closed until a source-backed rule owner resolves this decision
- `defer_generic_rule_review` / `gee_raster_core_batch_v1_2032ef0dbf6bd642`: keep fail-closed until a source-backed rule owner resolves this decision
- `defer_generic_rule_review` / `gee_raster_core_batch_v1_2d002ab5febce7db`: keep fail-closed until a source-backed rule owner resolves this decision
- `defer_generic_rule_review` / `gee_raster_core_batch_v1_2eeb1b1fef383c5c`: keep fail-closed until a source-backed rule owner resolves this decision
- `defer_generic_rule_review` / `gee_raster_core_batch_v1_5e39ff1258927600`: keep fail-closed until a source-backed rule owner resolves this decision
- `defer_generic_rule_review` / `gee_raster_core_batch_v1_dfedbac1b83aae53`: keep fail-closed until a source-backed rule owner resolves this decision
- `defer_generic_rule_review` / `gee_raster_core_batch_v1_e7476cd2364d17c4`: keep fail-closed until a source-backed rule owner resolves this decision
- `defer_generic_rule_review` / `gee_raster_core_batch_v1_73688d624e4a019d`: keep fail-closed until a source-backed rule owner resolves this decision
- `defer_generic_rule_review` / `gee_raster_core_batch_v1_4628f978dfa546a9`: keep fail-closed until a source-backed rule owner resolves this decision
- `defer_generic_rule_review` / `gee_raster_core_batch_v1_b0455102943d2856`: keep fail-closed until a source-backed rule owner resolves this decision
- `defer_generic_rule_review` / `gee_raster_core_batch_v1_68c468969b568529`: keep fail-closed until a source-backed rule owner resolves this decision
- `defer_generic_rule_review` / `gee_raster_core_batch_v1_0394ee3c816a37f4`: keep fail-closed until a source-backed rule owner resolves this decision
- `defer_generic_rule_review` / `gee_raster_core_batch_v1_836146c21e4e900f`: keep fail-closed until a source-backed rule owner resolves this decision
- `defer_generic_rule_review` / `gee_raster_core_batch_v1_a967212001a79150`: keep fail-closed until a source-backed rule owner resolves this decision
- `defer_generic_rule_review` / `gee_raster_core_batch_v1_b1781642f7af6a68`: keep fail-closed until a source-backed rule owner resolves this decision

## Boundary

- This sidecar does not append to or rewrite `train11397_full.json` / `train11397_v4_100.json`.
- Candidate rows remain train-only and validation/test ineligible.
- Operator and L3 sequences are copied from the source-backed rule proposal without reordering.
