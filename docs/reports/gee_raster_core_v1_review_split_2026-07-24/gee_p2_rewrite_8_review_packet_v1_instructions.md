# GEE P2 Rewrite Human Review Packet

This packet reviews only task-text fidelity for deterministic P2 rewrites.
Do not use this packet to grant validation/test admission or QGIS operator-chain gold status.

## Required human fields

- `human_task_text_faithful`: `yes`, `no`, or `needs_edit`.
- `human_known_omissions_correct`: `yes`, `no`, or `needs_edit`.
- `human_should_enter_train_only`: `yes_train_only`, `no`, or `needs_edit`.
- `human_review_notes`: concise reason for the decision.

Accept only if the rewritten task name/description describes exactly the retained operator/L3 chain,
and all omitted original-script behavior is represented only in `known_omissions`.

## Summary

- Rows: 8
- Pending human review: 8
- Training admission: `not_granted_pending_human_text_fidelity_review`

## Rows

### gee_raster_core_review_002

- Rewritten task: Summarize mosaicked water-vapor imagery by polygons
- Description: Select the water-vapor band from a Sentinel-2 image collection, mosaic the selected imagery, compute zonal mean water-vapor values for polygons, and apply the retained limit operation.
- Known omissions: polygon area multiplication, water-vapor volume estimate, top-5 ranking, map display
- Operators: ee.imagecollection.select, ee.imagecollection.mosaic, ee.image.reduceregions, ee.imagecollection.limit

### gee_raster_core_review_003

- Rewritten task: Summarize vegetated area from an NDVI mask
- Description: Filter Sentinel-2 imagery by region, date, and metadata, mosaic and clip the imagery, compute and rename NDVI, apply a vegetation threshold mask, multiply the masked pixels by pixel area, and reduce the result over the region to summarize vegetated area.
- Known omissions: map display layers, NDVI visualization palette, printed non-vegetated and total area summaries
- Operators: ee.imagecollection.filterbounds, ee.imagecollection.filterdate, ee.imagecollection.filtermetadata, ee.imagecollection.mosaic, ee.image.clip, ee.image.normalizeddifference, ee.image.rename, ee.image.mask, ee.image.select, ee.image.gte, ee.image.multiply, ee.image.pixelarea, ee.image.reduceregion

### gee_raster_core_review_015

- Rewritten task: Calculate annual precipitation zonal means
- Description: Select precipitation imagery, filter the image collection to the target year, reduce the collection into an annual precipitation image, and compute polygon zonal mean precipitation with reduceRegions.
- Known omissions: watershed area calculation, appending area properties, raster or feature export
- Operators: ee.imagecollection.select, ee.imagecollection.filterdate, ee.imagecollection.reduce, ee.image.reduceregions

### gee_raster_core_review_016

- Rewritten task: Build an alert-proximity cumulative-cost mask
- Description: Compute cumulative cost from alert locations over a raster cost surface, threshold the cost image to retain locations within the distance limit, and filter the related image collection used by the retained core chain.
- Known omissions: peat-forest overlay, alert-point display, visual buffer assessment, map display layers
- Operators: ee.image.cumulativecost, ee.image.lt, ee.imagecollection.filter

### gee_raster_core_review_019

- Rewritten task: Detect irrigated areas with NDVI-temperature masking
- Description: Filter Landsat imagery by date and cloud criteria, build median composites, compute NDVI and temperature-derived images, combine threshold conditions, apply the resulting irrigation mask, multiply by pixel area, and reduce the masked area over the region.
- Known omissions: histogram outputs, chart analysis, map display layers
- Operators: ee.imagecollection.filterdate, ee.imagecollection.filter, ee.imagecollection.median, ee.image.normalizeddifference, ee.image.rename, ee.image.clip, ee.image.add, ee.image.divide, ee.image.select, ee.image.add, ee.image.divide, ee.image.clip, ee.image.gt, ee.image.and, ee.image.updatemask, ee.image.multiply, ee.image.pixelarea, ee.image.reduceregion

### gee_raster_core_review_025

- Rewritten task: Classify land cover and summarize class area
- Description: Add derived bands to imagery, filter image collections, select predictor bands, sample training regions, configure and train a Random Forest classifier, classify the image, add pixel-area information, reduce the classified image over the region, and flatten the resulting feature collection.
- Known omissions: accuracy evaluation, confusion matrix, class accuracy metrics
- Operators: ee.image.addbands, ee.imagecollection.filter, ee.imagecollection.filter, ee.image.select, ee.image.sampleregions, ee.classifier.smilerandomforest, ee.classifier.train, ee.image.select, ee.image.classify, ee.image.pixelarea, ee.image.addbands, ee.image.reduceregion, ee.featurecollection.flatten

### gee_raster_core_review_032

- Rewritten task: Filter a calibrated GPM precipitation collection
- Description: Select calibrated precipitation from the GPM IMERG image collection, filter the collection by date, and filter it by the study geometry.
- Known omissions: clipping, downstream temporal analysis, downstream spatial analysis
- Operators: ee.imagecollection.select, ee.imagecollection.filterdate, ee.imagecollection.filterbounds

### gee_raster_core_review_048

- Rewritten task: Prepare TerraClimate mean and banded climate imagery
- Description: Select TerraClimate variables, compute their long-term mean image, select precipitation imagery, convert the precipitation collection to bands, select image bands, and rename the retained climate bands.
- Known omissions: annual composites for 2001-2019, WorldClim comparison, print and band-inspection output
- Operators: ee.imagecollection.select, ee.imagecollection.mean, ee.imagecollection.select, ee.imagecollection.tobands, ee.image.select, ee.image.rename
