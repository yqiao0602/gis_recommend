# GEE P4 Review Proposals

Proposal-only sidecar. It does not mutate human fields or grant admission.

- Batch: `21_28`
- Rows: 8
- Proposed yes_train_only: 5
- Proposed needs_edit: 2
- Proposed defer: 1
- Proposed reject: 0

## Rows

### gee_raster_core_review_038

- Proposed task text: yes
- Proposed chain correct: yes
- Proposed core completeness: yes
- Proposed train-only: yes_train_only
- Known omissions: Map display, print output, and non-core visualization remain outside the target.
- Notes: The new chain recovers Sentinel-1 HH/HV filtering, before/after date mosaics, focal median filtering, ratio/difference thresholding, and updateMask. It now covers the SAR snow-change core that was missing from the old retained chain.

### gee_raster_core_review_042

- Proposed task text: yes
- Proposed chain correct: yes
- Proposed core completeness: yes
- Proposed train-only: yes_train_only
- Known omissions: Downstream map rendering, final suitability interpretation, and any export behavior are omitted.
- Notes: The new chain recovers the repeated environmental-variable select/gt/lt/and threshold criteria for sugarcane suitability. Although long, it is a direct threshold-combination core and does not require an LLM to infer missing operators.

### gee_raster_core_review_044

- Proposed task text: needs_edit
- Proposed chain correct: partial
- Proposed core completeness: partial
- Proposed train-only: needs_edit
- Known omissions: Full timing-of-maximum algae analysis, pixel-level temporal statistics, and some elevation-stratified outputs are not safely represented in the retained target.
- Notes: The new chain recovers glacier/algae mask preparation, MODIS/region filtering, reduceRegions count extraction, and grid/region operations, but the original task is broader than the retained statistical extraction. Rewrite around a bounded algae-mask regional-count/elevation subworkflow before export.

### gee_raster_core_review_045

- Proposed task text: yes
- Proposed chain correct: yes
- Proposed core completeness: yes
- Proposed train-only: yes_train_only
- Known omissions: Client-side getInfo/print behavior and map display are omitted.
- Notes: The new chain recovers aggregate_array/distinct grouping, feature filtering by municipal code, union/dissolve geometry creation, raster clipping, pixel-count area estimation, pixelArea-based area estimation, and reduceRegion summaries.

### gee_raster_core_review_046

- Proposed task text: needs_edit
- Proposed chain correct: partial
- Proposed core completeness: partial
- Proposed train-only: defer
- Known omissions: MODIS water detection, Landsat validation, confusion-matrix metrics, recurrence/probability/return-interval products, and area calculations should be split before training.
- Notes: The new chain is much richer than the old retained chain, but it is a 289-call composite with multiple products and evaluation phases. Keep deferred until manually split into bounded detection, validation/evaluation, recurrence, and area subworkflows.

### gee_raster_core_review_047

- Proposed task text: needs_edit
- Proposed chain correct: partial
- Proposed core completeness: yes
- Proposed train-only: needs_edit
- Known omissions: Overlay/display layers for each QA component are not training targets; retained target is QA bit decoding and combined mask construction.
- Notes: The new chain recovers MODIS state_1km selection, repeated bitwiseAnd/rightShift/expression QA extraction, eq/not/and logic, combined mask construction, and updateMask calls. Because it has loop_order_unresolved/native_js_call flags from helper bit decoding, keep it as needs-edit/confirmation rather than immediate train-only.

### gee_raster_core_review_049

- Proposed task text: yes
- Proposed chain correct: yes
- Proposed core completeness: yes
- Proposed train-only: yes_train_only
- Known omissions: True-color/NDVI map display, print diagnostics, and UI output are omitted.
- Notes: The new chain recovers Landsat filtering/sorting/first image selection, radiance and brightness-temperature arithmetic, NDVI min/max reduceRegion, vegetation proportion, emissivity, and final LST arithmetic. The task text is faithful to the retained LST computation core if display outputs are ignored.

### gee_raster_core_review_050

- Proposed task text: yes
- Proposed chain correct: yes
- Proposed core completeness: yes
- Proposed train-only: yes_train_only
- Known omissions: Map display and non-core layer rendering are omitted; retained target is the masking/classification/evaluation core.
- Notes: The new chain recovers Sentinel-2 cloud filtering, four date-window filters, QA60 cloud masks, water/forest masks, mosaics/clips, FIRMS/date filters and merges, train/test split, sampleRegions, Random Forest training, classification, validation sampling, errorMatrix, and accuracy.
