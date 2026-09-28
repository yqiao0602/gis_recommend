# GEE P4 Review Proposals

Proposal-only sidecar. It does not mutate human fields or grant admission.

- Batch: `11_20`
- Rows: 10
- Proposed yes_train_only: 4
- Proposed needs_edit: 5
- Proposed defer: 1
- Proposed reject: 0

## Rows

### gee_raster_core_review_021

- Proposed task text: needs_edit
- Proposed chain correct: yes
- Proposed core completeness: yes
- Proposed train-only: needs_edit
- Known omissions: Terrain-correction internals, map centering/display, and any downstream interpretation remain outside the target unless a terrain-correction rule is added.
- Notes: The new chain recovers Sentinel-1 VH/VV/instrument filters, bounds/date filtering, mapped collection minimum, polarization selection, and clipping. The original description claims terrain correction, but the retained chain does not represent it, so rewrite around SAR filtering/min-backscatter extraction.

### gee_raster_core_review_022

- Proposed task text: yes
- Proposed chain correct: yes
- Proposed core completeness: yes
- Proposed train-only: yes_train_only
- Known omissions: Map layers, printed diagnostics, and visualization of intermediate arrays remain outside the target.
- Notes: The new chain recovers NDVI/DOY array conversion, forward differences, daily threshold construction, logical thresholding, array masking, and toArray/toArrayPerBand operations. It is suitable as a compact time-series threshold-detection core if confirmed.

### gee_raster_core_review_026

- Proposed task text: needs_edit
- Proposed chain correct: partial
- Proposed core completeness: partial
- Proposed train-only: defer
- Known omissions: The full feature-stack/classifier/evaluation workflow is too large for a single fixed chain without split-subworkflow policy. Display and dictionary reporting are also outside the target.
- Notes: The new chain recovers many spectral indices, stratified sampling, Random Forest training, classification, and accuracy metrics, but it is a 272-call composite with multiple model/evaluation phases. Defer until it is split into bounded feature-construction, sampling/training, and evaluation subworkflows.

### gee_raster_core_review_027

- Proposed task text: needs_edit
- Proposed chain correct: yes
- Proposed core completeness: yes
- Proposed train-only: needs_edit
- Known omissions: Cloud-mask/update-mask semantics from the source `.map(s2mask())` are not retained. Display layers are omitted.
- Notes: The new chain recovers Sentinel-2 filter/date/bounds/metadata selection, median composite, clipping, minMax reduceRegion, per-band unitScale, toBands, and rename. Rewrite the task as min-max normalization of a Sentinel-2 composite rather than cloud-masked normalization.

### gee_raster_core_review_029

- Proposed task text: needs_edit
- Proposed chain correct: partial
- Proposed core completeness: partial
- Proposed train-only: needs_edit
- Known omissions: Adaptive-threshold reduceRegion logic, post-training classify output, and final open-water/submerged-vegetation map are not retained.
- Notes: The new chain recovers Sentinel-1 date-window compositing, non-empty filtering, representative image clipping, sampleRegions, Random Forest factory, and training. It can become a training-sample/RF-training subworkflow after a narrower rewrite, but the current task overclaims final water classification.

### gee_raster_core_review_030

- Proposed task text: yes
- Proposed chain correct: yes
- Proposed core completeness: yes
- Proposed train-only: yes_train_only
- Known omissions: Export.image.toDrive calls and Drive/output configuration remain outside the target.
- Notes: The new chain recovers Sentinel-2 filtering, NDVI and LSWI normalizedDifference, FAPAR expression, sum/max reducers, and geometry regions for output. The task text is faithful if interpreted as producing vegetation/moisture/FAPAR raster metrics, not export execution.

### gee_raster_core_review_031

- Proposed task text: yes
- Proposed chain correct: yes
- Proposed core completeness: yes
- Proposed train-only: yes_train_only
- Known omissions: Client-side property-name inspection and print/getInfo behavior remain outside the target.
- Notes: The new chain recovers monthly GeoTIFF loading, band selection/renaming, reduceRegion mean/count, coverage percentage calculation, and field property setting. It is a usable field-level monthly residue-statistics subworkflow.

### gee_raster_core_review_033

- Proposed task text: needs_edit
- Proposed chain correct: yes
- Proposed core completeness: yes
- Proposed train-only: needs_edit
- Known omissions: GIF/video thumbnail generation, map layers, and long-form output presentation are not part of the retained target.
- Notes: The new chain recovers Landsat filtering, cloud masking, clipping, NDVI normalizedDifference, EVI/SAVI expressions, addBands, yearly filtering, and yearly mean collection construction. The task should be rewritten around vegetation-index trend construction, not visualization/time-series output.

### gee_raster_core_review_034

- Proposed task text: needs_edit
- Proposed chain correct: partial
- Proposed core completeness: partial
- Proposed train-only: needs_edit
- Known omissions: Full LAI capping/processing and all phenology interpretation steps are not safely represented. Print diagnostics remain omitted.
- Notes: The new chain recovers MCD12Q2 filtering, phenology band selection, NumCycles mask, DOY baseline adjustment fragments, collection selection/filtering, gt/where/toInt postprocessing, and partial LAI masking. It needs a narrowed description and possibly a manually bounded phenology-band preprocessing target before export.

### gee_raster_core_review_035

- Proposed task text: yes
- Proposed chain correct: yes
- Proposed core completeness: yes
- Proposed train-only: yes_train_only
- Known omissions: Print output and non-core display behavior are omitted; retained target is monthly NDVI/SR image collection construction.
- Notes: The new chain recovers MODIS date/bounds/select, clipping, NDVI scaling, SR arithmetic transform, monthly calendar filtering, mean aggregation, metadata setting, flattening, and ImageCollection.fromImages construction.
