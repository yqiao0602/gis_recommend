# GEE Batch Source-Backed Rewrites

This packet rewrites only the source-backed rows that were routed as
train-only text-rewrite candidates. It keeps the frozen operator/L3
chains unchanged and writes the other sampled audit rows to a
fail-closed rule backlog.

## Result

- Output prefix: `rewrite_candidates_medium_v1`
- Rule-proposal rows: 14
- Rewrite candidates: 1
- Schema-valid train-only candidate rows: 1
- Deferred backlog rows: 13
- Training rows emitted into train11397 package: 0
- Validation rows emitted: 0
- Test rows emitted: 0
- Training admission: `not_granted_rewrite_sidecar_schema_gate_passed`
- Production merge: `not_granted`
- LLM used: `False`

## Rewritten rows

### gee_raster_core_batch_rewrite_78327a27fc37eeec

- Proposal decision: `rewrite_core_classifier_keep_eval_sidecar`
- Task name: Classify land cover from Sentinel-2 training samples
- Task description: The retained core workflow filters Sentinel-2 imagery by region, date, and metadata, selects spectral bands, mosaics and averages the image collection, builds training sample regions, trains a Random Forest land-cover classifier, and applies it to generate classified land-cover rasters.
- Operator calls retained: 18
- L3 calls retained: 18
- Known omissions: external feature collections and labeled sample provenance are source context, confusion matrices and accuracy metrics, Map display, print output, and display/export noise

## Deferred rule backlog

- `defer_generic_rule_review` / `gee_raster_core_batch_v1_75c30ac29b14f137`: keep fail-closed until a source-backed rule owner resolves this decision
- `defer_generic_rule_review` / `gee_raster_core_batch_v1_39ddf8ee8db4243d`: keep fail-closed until a source-backed rule owner resolves this decision
- `defer_generic_rule_review` / `gee_raster_core_batch_v1_ecf791e47c854393`: keep fail-closed until a source-backed rule owner resolves this decision
- `defer_generic_rule_review` / `gee_raster_core_batch_v1_4dabfc16c36669e6`: keep fail-closed until a source-backed rule owner resolves this decision
- `rewrite_or_defer_text_overclaim` / `gee_raster_core_batch_v1_533863f11e12008d`: keep fail-closed until a source-backed rule owner resolves this decision
- `defer_manual_boundary_review` / `gee_raster_core_batch_v1_fe154f6a7a2929b1`: review external vector/training-label boundary and retained chain scope before admission
- `rewrite_or_defer_text_overclaim` / `gee_raster_core_batch_v1_bed1c5dbc2033aea`: keep fail-closed until a source-backed rule owner resolves this decision
- `defer_generic_rule_review` / `gee_raster_core_batch_v1_70a146c3311b869d`: keep fail-closed until a source-backed rule owner resolves this decision
- `defer_generic_rule_review` / `gee_raster_core_batch_v1_b7bb0897f4c8e25d`: keep fail-closed until a source-backed rule owner resolves this decision
- `defer_generic_rule_review` / `gee_raster_core_batch_v1_7027fa287be94183`: keep fail-closed until a source-backed rule owner resolves this decision
- `defer_generic_rule_review` / `gee_raster_core_batch_v1_08899a4f296de3d1`: keep fail-closed until a source-backed rule owner resolves this decision
- `defer_generic_rule_review` / `gee_raster_core_batch_v1_f1c234d464724255`: keep fail-closed until a source-backed rule owner resolves this decision
- `defer_generic_rule_review` / `gee_raster_core_batch_v1_d4880f5276430669`: keep fail-closed until a source-backed rule owner resolves this decision

## Boundary

- This sidecar does not append to or rewrite `train11397_full.json` / `train11397_v4_100.json`.
- Candidate rows remain train-only and validation/test ineligible.
- Operator and L3 sequences are copied from the source-backed rule proposal without reordering.
