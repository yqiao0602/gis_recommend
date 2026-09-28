# GEE Raster Core P2 Description Rewrites

Deterministic chain-faithful rewrites for the eight P0 rows marked
`rewrite_description_then_train`. This pass does not call an LLM and does
not grant validation/test or dataset-level training admission.

## Summary

- Rewrite rows: 8
- P1-valid train-only candidate rows: 8
- Training admission: `not_granted_pending_human_text_fidelity_review`
- Validation eligible: `False`
- Test eligible: `False`

## Rewritten rows

### gee_raster_core_review_002

- Task name: Summarize mosaicked water-vapor imagery by polygons
- Task description: Select the water-vapor band from a Sentinel-2 image collection, mosaic the selected imagery, compute zonal mean water-vapor values for polygons, and apply the retained limit operation.
- Known omissions: polygon area multiplication, water-vapor volume estimate, top-5 ranking, map display

### gee_raster_core_review_003

- Task name: Summarize vegetated area from an NDVI mask
- Task description: Filter Sentinel-2 imagery by region, date, and metadata, mosaic and clip the imagery, compute and rename NDVI, apply a vegetation threshold mask, multiply the masked pixels by pixel area, and reduce the result over the region to summarize vegetated area.
- Known omissions: map display layers, NDVI visualization palette, printed non-vegetated and total area summaries

### gee_raster_core_review_015

- Task name: Calculate annual precipitation zonal means
- Task description: Select precipitation imagery, filter the image collection to the target year, reduce the collection into an annual precipitation image, and compute polygon zonal mean precipitation with reduceRegions.
- Known omissions: watershed area calculation, appending area properties, raster or feature export

### gee_raster_core_review_016

- Task name: Build an alert-proximity cumulative-cost mask
- Task description: Compute cumulative cost from alert locations over a raster cost surface, threshold the cost image to retain locations within the distance limit, and filter the related image collection used by the retained core chain.
- Known omissions: peat-forest overlay, alert-point display, visual buffer assessment, map display layers

### gee_raster_core_review_019

- Task name: Detect irrigated areas with NDVI-temperature masking
- Task description: Filter Landsat imagery by date and cloud criteria, build median composites, compute NDVI and temperature-derived images, combine threshold conditions, apply the resulting irrigation mask, multiply by pixel area, and reduce the masked area over the region.
- Known omissions: histogram outputs, chart analysis, map display layers

### gee_raster_core_review_025

- Task name: Classify land cover and summarize class area
- Task description: Add derived bands to imagery, filter image collections, select predictor bands, sample training regions, configure and train a Random Forest classifier, classify the image, add pixel-area information, reduce the classified image over the region, and flatten the resulting feature collection.
- Known omissions: accuracy evaluation, confusion matrix, class accuracy metrics

### gee_raster_core_review_032

- Task name: Filter a calibrated GPM precipitation collection
- Task description: Select calibrated precipitation from the GPM IMERG image collection, filter the collection by date, and filter it by the study geometry.
- Known omissions: clipping, downstream temporal analysis, downstream spatial analysis

### gee_raster_core_review_048

- Task name: Prepare TerraClimate mean and banded climate imagery
- Task description: Select TerraClimate variables, compute their long-term mean image, select precipitation imagery, convert the precipitation collection to bands, select image bands, and rename the retained climate bands.
- Known omissions: annual composites for 2001-2019, WorldClim comparison, print and band-inspection output
