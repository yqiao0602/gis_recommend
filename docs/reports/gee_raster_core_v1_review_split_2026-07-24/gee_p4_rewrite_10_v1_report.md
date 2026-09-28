# GEE P4 Description Rewrites

Deterministic chain-faithful task-text rewrites for the P4 rows adjudicated as `needs_edit`.
This pass does not emit training rows because the new P4 operator chains still require a separate L3 canonicalization gate.

## Summary

- Rewrite rows: 10
- Training rows emitted: 0
- Training admission: `not_granted_pending_l3_mapping_and_export_gate`
- Validation eligible: `False`
- Test eligible: `False`

## Rows

### gee_raster_core_review_004

- Task name: Prepare Sentinel-2 water-index masks and quality mosaic
- Task description: Filter site features and Sentinel-2 imagery by region and date, clip the images, decode QA cloud bits to update masks, compute water-index and wetness bands, add them to each image, and build a quality mosaic using the retained index band.
- Operator calls retained: 78
- New L3 status: `pending_operator_l3_canonicalization`
- Known omissions: final thresholded water-extent product, map display layers, print output

### gee_raster_core_review_005

- Task name: Construct land-cover training samples from joined imagery
- Task description: Convert labeled training features to centroids, merge training feature collections, join them with nearby Landsat surface-reflectance images, apply cloud masking and calibrated band selection, sample image values at the training locations, flatten the sampled collection, and inspect the first sample row.
- Operator calls retained: 54
- New L3 status: `pending_operator_l3_canonicalization`
- Known omissions: full classifier training and prediction, map styling and display layers, final land-cover map use

### gee_raster_core_review_006

- Task name: Prepare Sentinel-2 spectral and texture features
- Task description: Filter Sentinel-2 Level-1 imagery by date, cloud metadata, and bounds, decode QA bits to mask clouds, select the first retained image, clip it to the region, and derive B8 texture features using a GLCM texture operation.
- Operator calls retained: 22
- New L3 status: `pending_operator_l3_canonicalization`
- Known omissions: training and testing samples, final tea-area classification, map display and band diagnostics

### gee_raster_core_review_021

- Task name: Filter Sentinel-1 SAR imagery for minimum backscatter
- Task description: Filter Sentinel-1 GRD images by required VV/VH polarizations, instrument mode, region, and date; compute the minimum image from the retained collection; select backscatter polarizations; and clip the result to the study polygon.
- Operator calls retained: 11
- New L3 status: `pending_operator_l3_canonicalization`
- Known omissions: terrain-correction internals, map centering and display, downstream interpretation

### gee_raster_core_review_027

- Task name: Min-max normalize a Sentinel-2 median composite
- Task description: Filter Sentinel-2 imagery by date, region, and metadata, build a median composite, clip it to the study geometry, compute per-band min-max statistics, unit-scale each selected band, stack the normalized bands, and rename the output bands.
- Operator calls retained: 23
- New L3 status: `pending_operator_l3_canonicalization`
- Known omissions: cloud-mask update-mask semantics from the source helper, display layers

### gee_raster_core_review_029

- Task name: Build Sentinel-1 composites and train a Random Forest from samples
- Task description: Create date-window Sentinel-1 composites, filter out empty composites, select a representative clipped image, sample training regions from the retained image, initialize a Random Forest classifier, and train it on the sampled features.
- Operator calls retained: 24
- New L3 status: `pending_operator_l3_canonicalization`
- Known omissions: adaptive-threshold reduceRegion logic, post-training classify output, final open-water or submerged-vegetation map

### gee_raster_core_review_033

- Task name: Construct Landsat vegetation-index yearly composites
- Task description: Filter Landsat imagery by region and yearly windows, apply QA cloud masking, clip images, compute NDVI, EVI, and SAVI vegetation-index bands, add the derived bands, and build yearly mean index composites.
- Operator calls retained: 51
- New L3 status: `pending_operator_l3_canonicalization`
- Known omissions: GIF or video thumbnail generation, map display layers, long-form output presentation

### gee_raster_core_review_034

- Task name: Preprocess MODIS phenology bands and masks
- Task description: Filter MCD12Q2 phenology imagery by date, select phenology and cycle-count bands, apply NumCycles and phenology masks, adjust day-of-year values relative to a baseline date, and convert retained phenology-mask outputs to integer bands.
- Operator calls retained: 29
- New L3 status: `pending_operator_l3_canonicalization`
- Known omissions: full LAI capping and processing, phenology interpretation steps, print diagnostics

### gee_raster_core_review_044

- Task name: Summarize algae-mask counts by region and elevation context
- Task description: Prepare glacier and algae masks, filter MODIS imagery and regional features, build mask images for retained algae/elevation strata, compute regional pixel-count summaries with reduceRegions, and carry the bounded grid and region attributes used by the statistical extraction.
- Operator calls retained: 96
- New L3 status: `pending_operator_l3_canonicalization`
- Known omissions: full timing-of-maximum algae analysis, pixel-level temporal statistics, unverified elevation-stratified outputs

### gee_raster_core_review_047

- Task name: Decode MODIS QA bits and build a combined mask
- Task description: Select MODIS QA bands, repeatedly extract bit ranges with bitwise operations and shifts, derive cloud, shadow, and land/water logical conditions, combine the QA conditions, and update the image mask with the retained combined mask.
- Operator calls retained: 29
- New L3 status: `pending_operator_l3_canonicalization`
- Known omissions: overlay and display layers for individual QA components
