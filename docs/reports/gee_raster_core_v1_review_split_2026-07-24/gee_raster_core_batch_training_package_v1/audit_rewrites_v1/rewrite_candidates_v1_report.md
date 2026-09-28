# GEE Batch High-Risk Rewrites v1

This packet rewrites only the two source-backed high-risk rows that were
routed as train-only text-rewrite candidates. It keeps the frozen
operator/L3 chains unchanged and writes the other high-risk rows to a
fail-closed rule backlog.

## Result

- Rule-proposal rows: 5
- Rewrite candidates: 2
- Schema-valid train-only candidate rows: 2
- Deferred backlog rows: 3
- Training rows emitted into train11397 package: 0
- Validation rows emitted: 0
- Test rows emitted: 0
- Training admission: `not_granted_rewrite_sidecar_schema_gate_passed`
- Production merge: `not_granted`
- LLM used: `False`

## Rewritten rows

### gee_raster_core_batch_rewrite_22f227332e2789a0

- Proposal decision: `rewrite_core_classifier_keep_eval_sidecar`
- Task name: Classify sea ice concentration from SAR object properties
- Task description: The retained core workflow trains a Random Forest classifier using SAR HH/HV object-property features and labeled ice-concentration samples, then applies the classifier to create a sea-ice concentration raster output.
- Operator calls retained: 3
- L3 calls retained: 3
- Known omissions: external feature collections and labeled sample provenance are source context, validation classifier, confusion matrices and accuracy metrics, Map display, print output, and display/export noise

### gee_raster_core_batch_rewrite_46d29e8413eae5bd

- Proposal decision: `rewrite_core_raster_stats_text`
- Task name: Quantify built-up surface area from thresholded GHSL raster
- Task description: Select and clip the GHSL built-up surface raster, derive equality and threshold masks for built-up categories, apply those masks to pixel area images, and summarize total and new built-up area with reduceRegion.
- Operator calls retained: 8
- L3 calls retained: 8
- Known omissions: map styling, display, and print outputs, classified-map or built-up intensity visualization language, broader urbanization interpretation beyond threshold-mask area statistics

## Deferred rule backlog

- `defer_external_algorithm_sidecar` / `gee_raster_core_batch_v1_eb341a4ea44a9efe`: define external temporal module sidecar/exclusion policy before considering this family
- `defer_manual_boundary_review` / `gee_raster_core_batch_v1_1dcaec10d74d5605`: review external vector/training-label boundary and retained chain scope before admission
- `defer_regional_statistics_mapping_repair` / `gee_raster_core_batch_v1_c24b717d5492f31e`: repair regional-statistics extractor/L3 mapping authority before admission

## Boundary

- This sidecar does not append to or rewrite `train11397_full.json` / `train11397_v4_100.json`.
- Candidate rows remain train-only and validation/test ineligible.
- Operator and L3 sequences are copied from the source-backed rule proposal without reordering.
