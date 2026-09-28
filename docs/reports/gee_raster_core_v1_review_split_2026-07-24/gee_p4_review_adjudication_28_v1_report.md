# GEE P4 Review Adjudication

Confirmed sidecar derived from P4 proposal batches.
It does not emit training rows and does not grant validation/test admission.

## Summary

- Rows: 28
- Accepted train-only: 14
- Needs edit: 10
- Deferred: 4
- Rejected: 0
- Training admission: `not_granted_pending_rewrite_and_export_gate`

## Rows

### gee_raster_core_review_004

- Task text faithful: needs_edit
- New chain correct: yes
- Core complete: yes
- Should enter train-only: needs_edit
- Notes: Confirmed from P4 proposal batch 1_10: The new chain recovers table/site filters, Sentinel-2 filter/date/bounds, clipping, QA cloud masking, multiple normalizedDifference/expression index bands, addBands, and qualityMosaic. Original task text overstates final surface-water detection, so this should be text-rewritten before train-only export.

### gee_raster_core_review_005

- Task text faithful: needs_edit
- New chain correct: yes
- Core complete: yes
- Should enter train-only: needs_edit
- Notes: Confirmed from P4 proposal batch 1_10: The new chain recovers point-centroid conversion, feature-collection merges, temporal/spatial image join, cloud masking, calibrated image selection, sampleRegions, flatten, and first-row inspection. It is useful as training-sample construction, but the current task name says land-cover classification and needs rewriting.

### gee_raster_core_review_006

- Task text faithful: needs_edit
- New chain correct: partial
- Core complete: partial
- Should enter train-only: needs_edit
- Notes: Confirmed from P4 proposal batch 1_10: The new chain recovers Sentinel-2 date/cloud/bounds filtering, QA masking, first image selection, clipping, and B8 GLCM texture selection. Because the original task claims tea-cultivation classification while the recovered chain is only feature preparation, this needs a narrower task rewrite and possibly another source check for the unbound/index helper.

### gee_raster_core_review_007

- Task text faithful: needs_edit
- New chain correct: partial
- Core complete: partial
- Should enter train-only: defer
- Notes: Confirmed from P4 proposal batch 1_10: The new chain recovers EVI/LST/GLDAS preparation, Random Forest regression training, prediction/classify calls, and many addBands operations, but it carries loop_order_unresolved and a very long synthetic call-site sequence. Keep deferred until loop-aware representation or a manually bounded subworkflow is defined.

### gee_raster_core_review_009

- Task text faithful: yes
- New chain correct: yes
- Core complete: yes
- Should enter train-only: yes_train_only
- Notes: Confirmed from P4 proposal batch 1_10: The new chain recovers Landsat filtering, seasonal filtering, cloud masking, median/clip, NDVI expression, and thermal/constant arithmetic for LST construction. The task text is broadly faithful to the retained core.

### gee_raster_core_review_010

- Task text faithful: yes
- New chain correct: yes
- Core complete: yes
- Should enter train-only: yes_train_only
- Notes: Confirmed from P4 proposal batch 1_10: The new chain recovers PlanetScope selection/filtering, masking, index creation, sampling/training/classification, confusion-matrix accuracy metrics, and median aggregation. It is suitable as a train-only proposal if confirmed.

### gee_raster_core_review_012

- Task text faithful: needs_edit
- New chain correct: partial
- Core complete: partial
- Should enter train-only: defer
- Notes: Confirmed from P4 proposal batch 1_10: The new chain is much more complete than the old chain, but it is 386 core calls with date-list mapping and an unbound identifier flag. Defer until a smaller manually bounded water/coastline subworkflow or loop-aware representation is available.

### gee_raster_core_review_014

- Task text faithful: yes
- New chain correct: yes
- Core complete: yes
- Should enter train-only: yes_train_only
- Notes: Confirmed from P4 proposal batch 1_10: The new chain cleanly recovers band checks, NDVI difference/squared error, reducer sum/count, divide, and sqrt. This is a compact complete core-subworkflow.

### gee_raster_core_review_018

- Task text faithful: yes
- New chain correct: yes
- Core complete: yes
- Should enter train-only: yes_train_only
- Notes: Confirmed from P4 proposal batch 1_10: The new chain recovers CHIRPS date filtering, clipping/copyProperties, precipitation selection, reduceRegions with mean output, flattening, distinct/join behavior, and row feature construction. The task text is faithful to extracting rainfall at locations.

### gee_raster_core_review_020

- Task text faithful: yes
- New chain correct: yes
- Core complete: yes
- Should enter train-only: yes_train_only
- Notes: Confirmed from P4 proposal batch 1_10: The new chain recovers Landsat filter/sort/first, scaling, NDBI expression, threshold/selfMask, pixelArea multiplication/rename, reducer sum, reduceRegion, and rounded area conversion. It is suitable as a train-only proposal if confirmed.

### gee_raster_core_review_021

- Task text faithful: needs_edit
- New chain correct: yes
- Core complete: yes
- Should enter train-only: needs_edit
- Notes: Confirmed from P4 proposal batch 11_20: The new chain recovers Sentinel-1 VH/VV/instrument filters, bounds/date filtering, mapped collection minimum, polarization selection, and clipping. The original description claims terrain correction, but the retained chain does not represent it, so rewrite around SAR filtering/min-backscatter extraction.

### gee_raster_core_review_022

- Task text faithful: yes
- New chain correct: yes
- Core complete: yes
- Should enter train-only: yes_train_only
- Notes: Confirmed from P4 proposal batch 11_20: The new chain recovers NDVI/DOY array conversion, forward differences, daily threshold construction, logical thresholding, array masking, and toArray/toArrayPerBand operations. It is suitable as a compact time-series threshold-detection core if confirmed.

### gee_raster_core_review_026

- Task text faithful: needs_edit
- New chain correct: partial
- Core complete: partial
- Should enter train-only: defer
- Notes: Confirmed from P4 proposal batch 11_20: The new chain recovers many spectral indices, stratified sampling, Random Forest training, classification, and accuracy metrics, but it is a 272-call composite with multiple model/evaluation phases. Defer until it is split into bounded feature-construction, sampling/training, and evaluation subworkflows.

### gee_raster_core_review_027

- Task text faithful: needs_edit
- New chain correct: yes
- Core complete: yes
- Should enter train-only: needs_edit
- Notes: Confirmed from P4 proposal batch 11_20: The new chain recovers Sentinel-2 filter/date/bounds/metadata selection, median composite, clipping, minMax reduceRegion, per-band unitScale, toBands, and rename. Rewrite the task as min-max normalization of a Sentinel-2 composite rather than cloud-masked normalization.

### gee_raster_core_review_029

- Task text faithful: needs_edit
- New chain correct: partial
- Core complete: partial
- Should enter train-only: needs_edit
- Notes: Confirmed from P4 proposal batch 11_20: The new chain recovers Sentinel-1 date-window compositing, non-empty filtering, representative image clipping, sampleRegions, Random Forest factory, and training. It can become a training-sample/RF-training subworkflow after a narrower rewrite, but the current task overclaims final water classification.

### gee_raster_core_review_030

- Task text faithful: yes
- New chain correct: yes
- Core complete: yes
- Should enter train-only: yes_train_only
- Notes: Confirmed from P4 proposal batch 11_20: The new chain recovers Sentinel-2 filtering, NDVI and LSWI normalizedDifference, FAPAR expression, sum/max reducers, and geometry regions for output. The task text is faithful if interpreted as producing vegetation/moisture/FAPAR raster metrics, not export execution.

### gee_raster_core_review_031

- Task text faithful: yes
- New chain correct: yes
- Core complete: yes
- Should enter train-only: yes_train_only
- Notes: Confirmed from P4 proposal batch 11_20: The new chain recovers monthly GeoTIFF loading, band selection/renaming, reduceRegion mean/count, coverage percentage calculation, and field property setting. It is a usable field-level monthly residue-statistics subworkflow.

### gee_raster_core_review_033

- Task text faithful: needs_edit
- New chain correct: yes
- Core complete: yes
- Should enter train-only: needs_edit
- Notes: Confirmed from P4 proposal batch 11_20: The new chain recovers Landsat filtering, cloud masking, clipping, NDVI normalizedDifference, EVI/SAVI expressions, addBands, yearly filtering, and yearly mean collection construction. The task should be rewritten around vegetation-index trend construction, not visualization/time-series output.

### gee_raster_core_review_034

- Task text faithful: needs_edit
- New chain correct: partial
- Core complete: partial
- Should enter train-only: needs_edit
- Notes: Confirmed from P4 proposal batch 11_20: The new chain recovers MCD12Q2 filtering, phenology band selection, NumCycles mask, DOY baseline adjustment fragments, collection selection/filtering, gt/where/toInt postprocessing, and partial LAI masking. It needs a narrowed description and possibly a manually bounded phenology-band preprocessing target before export.

### gee_raster_core_review_035

- Task text faithful: yes
- New chain correct: yes
- Core complete: yes
- Should enter train-only: yes_train_only
- Notes: Confirmed from P4 proposal batch 11_20: The new chain recovers MODIS date/bounds/select, clipping, NDVI scaling, SR arithmetic transform, monthly calendar filtering, mean aggregation, metadata setting, flattening, and ImageCollection.fromImages construction.

### gee_raster_core_review_038

- Task text faithful: yes
- New chain correct: yes
- Core complete: yes
- Should enter train-only: yes_train_only
- Notes: Confirmed from P4 proposal batch 21_28: The new chain recovers Sentinel-1 HH/HV filtering, before/after date mosaics, focal median filtering, ratio/difference thresholding, and updateMask. It now covers the SAR snow-change core that was missing from the old retained chain.

### gee_raster_core_review_042

- Task text faithful: yes
- New chain correct: yes
- Core complete: yes
- Should enter train-only: yes_train_only
- Notes: Confirmed from P4 proposal batch 21_28: The new chain recovers the repeated environmental-variable select/gt/lt/and threshold criteria for sugarcane suitability. Although long, it is a direct threshold-combination core and does not require an LLM to infer missing operators.

### gee_raster_core_review_044

- Task text faithful: needs_edit
- New chain correct: partial
- Core complete: partial
- Should enter train-only: needs_edit
- Notes: Confirmed from P4 proposal batch 21_28: The new chain recovers glacier/algae mask preparation, MODIS/region filtering, reduceRegions count extraction, and grid/region operations, but the original task is broader than the retained statistical extraction. Rewrite around a bounded algae-mask regional-count/elevation subworkflow before export.

### gee_raster_core_review_045

- Task text faithful: yes
- New chain correct: yes
- Core complete: yes
- Should enter train-only: yes_train_only
- Notes: Confirmed from P4 proposal batch 21_28: The new chain recovers aggregate_array/distinct grouping, feature filtering by municipal code, union/dissolve geometry creation, raster clipping, pixel-count area estimation, pixelArea-based area estimation, and reduceRegion summaries.

### gee_raster_core_review_046

- Task text faithful: needs_edit
- New chain correct: partial
- Core complete: partial
- Should enter train-only: defer
- Notes: Confirmed from P4 proposal batch 21_28: The new chain is much richer than the old retained chain, but it is a 289-call composite with multiple products and evaluation phases. Keep deferred until manually split into bounded detection, validation/evaluation, recurrence, and area subworkflows.

### gee_raster_core_review_047

- Task text faithful: needs_edit
- New chain correct: partial
- Core complete: yes
- Should enter train-only: needs_edit
- Notes: Confirmed from P4 proposal batch 21_28: The new chain recovers MODIS state_1km selection, repeated bitwiseAnd/rightShift/expression QA extraction, eq/not/and logic, combined mask construction, and updateMask calls. Because it has loop_order_unresolved/native_js_call flags from helper bit decoding, keep it as needs-edit/confirmation rather than immediate train-only.

### gee_raster_core_review_049

- Task text faithful: yes
- New chain correct: yes
- Core complete: yes
- Should enter train-only: yes_train_only
- Notes: Confirmed from P4 proposal batch 21_28: The new chain recovers Landsat filtering/sorting/first image selection, radiance and brightness-temperature arithmetic, NDVI min/max reduceRegion, vegetation proportion, emissivity, and final LST arithmetic. The task text is faithful to the retained LST computation core if display outputs are ignored.

### gee_raster_core_review_050

- Task text faithful: yes
- New chain correct: yes
- Core complete: yes
- Should enter train-only: yes_train_only
- Notes: Confirmed from P4 proposal batch 21_28: The new chain recovers Sentinel-2 cloud filtering, four date-window filters, QA60 cloud masks, water/forest masks, mosaics/clips, FIRMS/date filters and merges, train/test split, sampleRegions, Random Forest training, classification, validation sampling, errorMatrix, and accuracy.
