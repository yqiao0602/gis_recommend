# GEE P4 Review Proposals

Proposal-only sidecar. It does not mutate human fields or grant admission.

- Batch: `1_10`
- Rows: 10
- Proposed yes_train_only: 5
- Proposed needs_edit: 3
- Proposed defer: 2
- Proposed reject: 0

## Rows

### gee_raster_core_review_004

- Proposed task text: needs_edit
- Proposed chain correct: yes
- Proposed core completeness: yes
- Proposed train-only: needs_edit
- Known omissions: Final thresholded water-extent product, map display, print output, and non-retained presentation layers remain outside the target. If accepted later, rewrite the task around water-index/mask feature construction and quality mosaic, not full water-extent detection.
- Notes: The new chain recovers table/site filters, Sentinel-2 filter/date/bounds, clipping, QA cloud masking, multiple normalizedDifference/expression index bands, addBands, and qualityMosaic. Original task text overstates final surface-water detection, so this should be text-rewritten before train-only export.

### gee_raster_core_review_005

- Proposed task text: needs_edit
- Proposed chain correct: yes
- Proposed core completeness: yes
- Proposed train-only: needs_edit
- Known omissions: Full land-cover classifier training/prediction is not retained. Map styling, palettes, display layers, and final model use remain outside the target.
- Notes: The new chain recovers point-centroid conversion, feature-collection merges, temporal/spatial image join, cloud masking, calibrated image selection, sampleRegions, flatten, and first-row inspection. It is useful as training-sample construction, but the current task name says land-cover classification and needs rewriting.

### gee_raster_core_review_006

- Proposed task text: needs_edit
- Proposed chain correct: partial
- Proposed core completeness: partial
- Proposed train-only: needs_edit
- Known omissions: Training/testing samples and final tea-area classification are not recovered in the retained chain. Map display and printed band/type diagnostics remain omitted.
- Notes: The new chain recovers Sentinel-2 date/cloud/bounds filtering, QA masking, first image selection, clipping, and B8 GLCM texture selection. Because the original task claims tea-cultivation classification while the recovered chain is only feature preparation, this needs a narrower task rewrite and possibly another source check for the unbound/index helper.

### gee_raster_core_review_007

- Proposed task text: needs_edit
- Proposed chain correct: partial
- Proposed core completeness: partial
- Proposed train-only: defer
- Known omissions: Runtime loop cardinality, repeated temporal interpolation bands, and exact prediction sequence are not safely representable as one fixed training chain yet.
- Notes: The new chain recovers EVI/LST/GLDAS preparation, Random Forest regression training, prediction/classify calls, and many addBands operations, but it carries loop_order_unresolved and a very long synthetic call-site sequence. Keep deferred until loop-aware representation or a manually bounded subworkflow is defined.

### gee_raster_core_review_009

- Proposed task text: yes
- Proposed chain correct: yes
- Proposed core completeness: yes
- Proposed train-only: yes_train_only
- Known omissions: Map display layers and print diagnostics are outside the target; retained chain focuses on image filtering, cloud masking, NDVI/thermal arithmetic, and LST-related band construction.
- Notes: The new chain recovers Landsat filtering, seasonal filtering, cloud masking, median/clip, NDVI expression, and thermal/constant arithmetic for LST construction. The task text is broadly faithful to the retained core.

### gee_raster_core_review_010

- Proposed task text: yes
- Proposed chain correct: yes
- Proposed core completeness: yes
- Proposed train-only: yes_train_only
- Known omissions: Visualization and non-core display behavior remain omitted. The retained target is classification plus accuracy/aggregation core, not UI rendering.
- Notes: The new chain recovers PlanetScope selection/filtering, masking, index creation, sampling/training/classification, confusion-matrix accuracy metrics, and median aggregation. It is suitable as a train-only proposal if confirmed.

### gee_raster_core_review_012

- Proposed task text: needs_edit
- Proposed chain correct: partial
- Proposed core completeness: partial
- Proposed train-only: defer
- Known omissions: Monthly/date-list runtime expansion, exact temporal aggregation cardinality, map display, and final coastline-change interpretation are not safely encoded as a fixed sequence yet.
- Notes: The new chain is much more complete than the old chain, but it is 386 core calls with date-list mapping and an unbound identifier flag. Defer until a smaller manually bounded water/coastline subworkflow or loop-aware representation is available.

### gee_raster_core_review_014

- Proposed task text: yes
- Proposed chain correct: yes
- Proposed core completeness: yes
- Proposed train-only: yes_train_only
- Known omissions: Print output is omitted; retained target is RMSE-style NDVI fusion error computation.
- Notes: The new chain cleanly recovers band checks, NDVI difference/squared error, reducer sum/count, divide, and sqrt. This is a compact complete core-subworkflow.

### gee_raster_core_review_018

- Proposed task text: yes
- Proposed chain correct: yes
- Proposed core completeness: yes
- Proposed train-only: yes_train_only
- Known omissions: Map layers and non-core display behavior remain outside the target.
- Notes: The new chain recovers CHIRPS date filtering, clipping/copyProperties, precipitation selection, reduceRegions with mean output, flattening, distinct/join behavior, and row feature construction. The task text is faithful to extracting rainfall at locations.

### gee_raster_core_review_020

- Proposed task text: yes
- Proposed chain correct: yes
- Proposed core completeness: yes
- Proposed train-only: yes_train_only
- Known omissions: Visualization, vector display, and printed area output are omitted; retained target is built-up index/mask and area summarization.
- Notes: The new chain recovers Landsat filter/sort/first, scaling, NDBI expression, threshold/selfMask, pixelArea multiplication/rename, reducer sum, reduceRegion, and rounded area conversion. It is suitable as a train-only proposal if confirmed.
