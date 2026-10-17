# Q3 多参考候选清单 V1（精确同指令 → 异模板；语义等价性待人工抽验）

seed 20261017；按组内行数降序抽 18 组。

## G-1  (n_rows=2, task_type=Vegetation)
- **Instruction**: task: estimate fpar from evi calculate enhanced vegetation index (evi) from starfm-fused imagery, applies temporal smoothing to reduce noise, integrates observed and smoothed evi values, and derives fraction of photosynthetically active radiation (fpar) using both evi and simple ratio (sr) models based on reference percentiles. the final output is a time series of fpar images.
  - `AGGREGATION -> RASTER_LOAD -> MASKING -> BAND_SELECT -> RASTER_LOAD -> COMPOSITE -> RASTER_LOAD -> BAND_SELECT -> RASTER_LOAD`  x1
  - `AGGREGATION -> RASTER_LOAD -> MASKING -> BAND_SELECT -> RASTER_LOAD -> COMPOSITE -> RASTER_LOAD -> BAND_SELECT`  x1

## G-2  (n_rows=10, task_type=Vegetation)
- **Instruction**: task: estimate vegetation cover fraction estimate fractional vegetation cover (fvc) from landsat 5 surface reflectance data by computing ndvi, generating a greenest-pixel composite, and applying a percentile-based fvc model. it classifies fvc into five levels, computes area statistics per class, and exports maps and charts.
  - `AGGREGATION -> RASTER_LOAD -> TEMPORAL_FILTER -> SPATIAL_FILTER -> COLLECTION_MGMT -> AGGREGATION -> RASTER_LOAD -> BAND_ARITHMETIC -> BAND_SELECT -> AGGREGATION -> VECTOR_LOAD`  x9
  - `AGGREGATION -> RASTER_LOAD -> TEMPORAL_FILTER -> AGGREGATION -> RASTER_LOAD -> BAND_ARITHMETIC -> BAND_SELECT -> AGGREGATION -> VECTOR_LOAD`  x1

## G-3  (n_rows=2, task_type=Land surface/agriculture indicators)
- **Instruction**: task: estimate vegetation cover fraction estimate fractional vegetation cover (fvc) from landsat 5 surface reflectance data by computing ndvi, generating a greenest-pixel composite, and applying a pixel-wise fvc model based on ndvi percentiles. it classifies fvc into five coverage levels, calculates area statistics per class, and exports maps and tabular results.
  - `AGGREGATION -> RASTER_LOAD -> TEMPORAL_FILTER -> SPATIAL_FILTER -> COLLECTION_MGMT -> AGGREGATION -> RASTER_LOAD -> BAND_ARITHMETIC -> BAND_SELECT -> AGGREGATION -> VECTOR_LOAD`  x1
  - `AGGREGATION -> RASTER_LOAD -> TEMPORAL_FILTER -> SPATIAL_FILTER -> AGGREGATION -> RASTER_LOAD -> BAND_ARITHMETIC -> BAND_SELECT -> AGGREGATION -> VECTOR_LOAD`  x1

## G-4  (n_rows=4, task_type=Terrestrial hydrosphere indicators)
- **Instruction**: task: identify surface water area calculate the modified normalized difference water index (mndwi) using green and swir bands from landsat 8 toa reflectance data to identify surface water extent. it computes the water-covered area in square meters per pixel, adds it as a band to each image, and generates a time series chart of total water area within a region of interest by summing pixel values over time.
  - `RASTER_LOAD -> SPATIAL_FILTER -> BAND_ARITHMETIC -> AGGREGATION`  x3
  - `RASTER_LOAD -> SPATIAL_FILTER -> TEMPORAL_FILTER -> ATTRIBUTE_FILTER -> BAND_ARITHMETIC -> AGGREGATION`  x1

## G-5  (n_rows=2, task_type=Land use/land cover)
- **Instruction**: task: classify land cover types classify land cover types using a random forest classifier trained on spectral indices, surface reflectance bands, and terrain features derived from landsat 7 and landsat 8 data for the year 2016. the output includes a classified land cover map and accuracy assessment metrics such as error matrix, overall accuracy, user accuracy, producer accuracy, and kappa coefficient.
  - `VECTOR_LOAD -> RASTER_LOAD -> TEMPORAL_FILTER -> ATTRIBUTE_FILTER -> SPATIAL_FILTER -> ITERATIVE_APPLY -> RASTER_LOAD -> VECTOR_LOAD -> RASTER_LOAD -> TEMPORAL_FILTER -> ATTRIBUTE_FILTER -> SPATIAL_FILTER -> ITERATIVE_APPLY -> RASTER_LOAD -> TEMPORAL_FILTER -> ATTRIBUTE_FILTER -> SPATIAL_FILTER -> ITERATIVE_APPLY -> RASTER_LOAD -> TERRAIN_DERIVED -> ATTRIBUTE_FILTER -> CLASSIFICATION`  x1
  - `VECTOR_LOAD -> RASTER_LOAD -> TEMPORAL_FILTER -> ATTRIBUTE_FILTER -> SPATIAL_FILTER -> ITERATIVE_APPLY -> RASTER_LOAD -> VECTOR_LOAD -> RASTER_LOAD -> TEMPORAL_FILTER -> ATTRIBUTE_FILTER -> SPATIAL_FILTER -> ITERATIVE_APPLY -> RASTER_LOAD -> TERRAIN_DERIVED -> ATTRIBUTE_FILTER -> CLASSIFICATION`  x1

## G-6  (n_rows=8, task_type=Land use/land cover)
- **Instruction**: task: identify tidal flats identify tidal flats using a random forest classifier trained on spectral indices (awei, ndwi, mndwi, etc.), topographic data (etopo1), and surface water occurrence (jrc global surface water) derived from landsat 4, 5, 7, and 8 surface reflectance data for the year 2018. the output is a classified binary raster where tidal flats are masked and exported.
  - `RASTER_LOAD -> TEMPORAL_FILTER -> ITERATIVE_APPLY -> AGGREGATION -> RASTER_LOAD -> BAND_SELECT -> RESAMPLE_REPROJECT -> RASTER_LOAD -> BAND_SELECT -> MASKING -> RASTER_LOAD -> CLASSIFICATION`  x4
  - `RASTER_LOAD -> TEMPORAL_FILTER -> ITERATIVE_APPLY -> AGGREGATION -> RASTER_LOAD -> BAND_SELECT -> RESAMPLE_REPROJECT -> RASTER_LOAD -> BAND_SELECT -> MASKING -> RASTER_LOAD -> ATTRIBUTE_FILTER -> CLASSIFICATION`  x4

## G-7  (n_rows=2, task_type=Terrestrial hydrosphere indicators)
- **Instruction**: task: identify water inundation from sar identify water inundation areas using vv-polarized sentinel-1 grd sar imagery by applying a speckle filter and threshold-based classification (vv < -16 db), then visualizes temporal changes in inundated pixels over the region of interest.
  - `RASTER_LOAD -> SPATIAL_FILTER -> TEMPORAL_FILTER -> ATTRIBUTE_FILTER -> NEIGHBORHOOD -> AGGREGATION -> ATTRIBUTE_FILTER -> RASTER_LOAD -> SPATIAL_CLIP -> BAND_SELECT -> RASTER_LOAD`  x1
  - `RASTER_LOAD -> SPATIAL_FILTER -> TEMPORAL_FILTER -> ATTRIBUTE_FILTER -> NEIGHBORHOOD -> AGGREGATION -> ATTRIBUTE_FILTER -> RASTER_LOAD -> SPATIAL_CLIP -> BAND_SELECT -> RASTER_LOAD -> EXPORT_OUTPUT`  x1

## G-8  (n_rows=2, task_type=Vegetation)
- **Instruction**: task: estimate vegetation coverage from ndvi calculate ndvi from landsat 5 surface reflectance data, masks clouds and water, computes fractional vegetation cover (fvc) using pixel percentile thresholds, classifies fvc into five coverage levels, and exports the results along with a legend and area statistics table.
  - `AGGREGATION -> RASTER_LOAD -> TEMPORAL_FILTER -> SPATIAL_FILTER -> COLLECTION_MGMT -> AGGREGATION -> RASTER_LOAD -> BAND_ARITHMETIC -> BAND_SELECT -> AGGREGATION -> VECTOR_LOAD`  x1
  - `AGGREGATION -> RASTER_LOAD -> TEMPORAL_FILTER -> ATTRIBUTE_FILTER -> COLLECTION_MGMT -> SPATIAL_FILTER -> AGGREGATION -> RASTER_LOAD -> BAND_ARITHMETIC -> BAND_SELECT -> AGGREGATION -> VECTOR_LOAD`  x1

## G-9  (n_rows=2, task_type=Habitat conversion/fragmentation)
- **Instruction**: task: identify forest degradation and deforestation identify intact forest, degraded forest, and deforested areas between 2000 and 2018 using multi-source remote sensing data including tree cover, land cover change, and forest loss year. it generates a classified raster map and exports stratified training and validation sample points for accuracy assessment.
  - `RASTER_LOAD -> NEIGHBORHOOD -> ATTRIBUTE_FILTER -> AGGREGATION -> ATTRIBUTE_FILTER -> VECTOR_LOAD -> BAND_SELECT`  x1
  - `RASTER_LOAD -> NEIGHBORHOOD -> ATTRIBUTE_FILTER -> AGGREGATION -> ATTRIBUTE_FILTER`  x1

## G-10  (n_rows=2, task_type=Vegetation)
- **Instruction**: task: analyze vegetation and water indices compute ndvi and ndwi from sentinel-2 surface reflectance data to analyze vegetation health and surface water presence, producing a composite image with added spectral indices for visualization and further analysis.
  - `RASTER_LOAD -> TEMPORAL_FILTER -> ATTRIBUTE_FILTER -> SPATIAL_FILTER -> ITERATIVE_APPLY`  x1
  - `RASTER_LOAD -> SPATIAL_FILTER -> TEMPORAL_FILTER -> ATTRIBUTE_FILTER -> ITERATIVE_APPLY`  x1

## G-11  (n_rows=3, task_type=Water quality)
- **Instruction**: task: monitor algal bloom in reservoirs monitor algal blooms in reservoirs across latin america using sentinel-2 data and the ndci index to estimate chlorophyll-a concentration, detect bloom presence, classify trophic state (tsi), and generate temporal statistics and visualizations for user-selected water bodies.
  - `ATTRIBUTE_FILTER -> RASTER_LOAD -> SPATIAL_CLIP -> RASTER_LOAD -> COMPOSITE -> RASTER_LOAD -> SPATIAL_FILTER -> RASTER_LOAD -> SPATIAL_FILTER -> RASTER_LOAD -> SPATIAL_JOIN -> ATTRIBUTE_FILTER -> RASTER_LOAD -> SPATIAL_CLIP -> RASTER_LOAD -> SPATIAL_CLIP -> RASTER_LOAD -> COMPOSITE -> GEOMETRY_DEFINE -> AGGREGATION -> BAND_ARITHMETIC -> BAND_SELECT -> RASTER_LOAD -> SPATIAL_CLIP -> RASTER_LOAD -> SPATIAL_CLIP -> RASTER_LOAD -> COMPOSITE -> RASTER_LOAD -> SPATIAL_FILTER -> RASTER_LOAD -> SPATIAL_FILTER -> RASTER_LOAD -> SPATIAL_JOIN -> ATTRIBUTE_FILTER -> RASTER_LOAD -> BAND_SELECT -> SPATIAL_FILTER -> ATTRIBUTE_FILTER -> VECTOR_LOAD -> RASTER_LOAD -> SPATIAL_CLIP -> RASTER_LOAD -> SPATIAL_CLIP -> RASTER_LOAD -> COMPOSITE -> RASTER_LOAD -> SPATIAL_FILTER -> RASTER_LOAD -> SPATIAL_FILTER -> RASTER_LOAD -> SPATIAL_JOIN -> ATTRIBUTE_FILTER -> RASTER_LOAD -> SPATIAL_CLIP -> RASTER_LOAD -> SPATIAL_CLIP -> RASTER_LOAD -> COMPOSITE -> RASTER_LOAD -> TEMPORAL_FILTER -> BAND_SELECT -> BAND_ARITHMETIC -> SPATIAL_CLIP -> MASKING -> GEOMETRY_DEFINE -> AGGREGATION -> RASTER_LOAD -> BAND_SELECT -> SPATIAL_FILTER -> ATTRIBUTE_FILTER -> VECTOR_LOAD -> RASTER_LOAD -> SPATIAL_CLIP -> RASTER_LOAD -> SPATIAL_CLIP -> RASTER_LOAD -> COMPOSITE -> RASTER_LOAD -> SPATIAL_FILTER -> RASTER_LOAD -> SPATIAL_FILTER -> RASTER_LOAD -> SPATIAL_JOIN -> ATTRIBUTE_FILTER -> RASTER_LOAD -> SPATIAL_CLIP -> RASTER_LOAD -> SPATIAL_CLIP -> RASTER_LOAD -> COMPOSITE -> RASTER_LOAD -> TEMPORAL_FILTER -> BAND_SELECT -> BAND_ARITHMETIC -> SPATIAL_CLIP -> MASKING -> GEOMETRY_DEFINE -> AGGREGATION -> RASTER_LOAD -> SPATIAL_CLIP -> RASTER_LOAD -> SPATIAL_CLIP -> RASTER_LOAD -> COMPOSITE -> RASTER_LOAD -> SPATIAL_FILTER -> RASTER_LOAD -> SPATIAL_FILTER -> RASTER_LOAD -> SPATIAL_JOIN -> ATTRIBUTE_FILTER -> RASTER_LOAD -> SPATIAL_CLIP -> RASTER_LOAD -> SPATIAL_CLIP -> RASTER_LOAD -> COMPOSITE -> ATTRIBUTE_FILTER -> AGGREGATION -> ATTRIBUTE_FILTER -> GEOMETRY_DEFINE -> RASTER_LOAD`  x1
  - `RASTER_LOAD -> ATTRIBUTE_FILTER -> RASTER_LOAD -> BAND_SELECT -> RASTER_LOAD -> BAND_SELECT -> RASTER_LOAD -> SPATIAL_FILTER -> RASTER_LOAD -> SPATIAL_FILTER -> RASTER_LOAD -> SPATIAL_JOIN -> ATTRIBUTE_FILTER -> RASTER_LOAD -> GEOMETRY_DEFINE -> AGGREGATION -> BAND_ARITHMETIC -> BAND_SELECT -> RASTER_LOAD -> BAND_SELECT -> RASTER_LOAD -> SPATIAL_FILTER -> RASTER_LOAD -> SPATIAL_FILTER -> RASTER_LOAD -> SPATIAL_JOIN -> ATTRIBUTE_FILTER -> RASTER_LOAD -> BAND_SELECT -> SPATIAL_FILTER -> ATTRIBUTE_FILTER -> VECTOR_LOAD -> RASTER_LOAD -> SPATIAL_FILTER -> RASTER_LOAD -> SPATIAL_FILTER -> RASTER_LOAD -> SPATIAL_JOIN -> ATTRIBUTE_FILTER -> RASTER_LOAD -> TEMPORAL_FILTER -> BAND_SELECT -> BAND_ARITHMETIC -> SPATIAL_CLIP -> MASKING -> GEOMETRY_DEFINE -> AGGREGATION -> RASTER_LOAD -> BAND_SELECT -> SPATIAL_FILTER -> ATTRIBUTE_FILTER -> VECTOR_LOAD -> RASTER_LOAD -> SPATIAL_FILTER -> RASTER_LOAD -> SPATIAL_FILTER -> RASTER_LOAD -> SPATIAL_JOIN -> ATTRIBUTE_FILTER -> RASTER_LOAD -> TEMPORAL_FILTER -> BAND_SELECT -> BAND_ARITHMETIC -> SPATIAL_CLIP -> MASKING -> GEOMETRY_DEFINE -> AGGREGATION -> RASTER_LOAD -> BAND_SELECT -> RASTER_LOAD -> SPATIAL_FILTER -> RASTER_LOAD -> SPATIAL_FILTER -> RASTER_LOAD -> SPATIAL_JOIN -> ATTRIBUTE_FILTER -> RASTER_LOAD -> ATTRIBUTE_FILTER -> AGGREGATION -> ATTRIBUTE_FILTER -> GEOMETRY_DEFINE -> RASTER_LOAD`  x1
  - `RASTER_LOAD -> ATTRIBUTE_FILTER -> RASTER_LOAD -> SPATIAL_CLIP -> RASTER_LOAD -> COMPOSITE -> RASTER_LOAD -> SPATIAL_FILTER -> RASTER_LOAD -> SPATIAL_FILTER -> RASTER_LOAD -> SPATIAL_JOIN -> ATTRIBUTE_FILTER -> RASTER_LOAD -> SPATIAL_CLIP -> RASTER_LOAD -> SPATIAL_CLIP -> RASTER_LOAD -> COMPOSITE -> GEOMETRY_DEFINE -> AGGREGATION -> BAND_ARITHMETIC -> BAND_SELECT -> RASTER_LOAD -> SPATIAL_CLIP -> RASTER_LOAD -> SPATIAL_CLIP -> RASTER_LOAD -> COMPOSITE -> RASTER_LOAD -> SPATIAL_FILTER -> RASTER_LOAD -> SPATIAL_FILTER -> RASTER_LOAD -> SPATIAL_JOIN -> ATTRIBUTE_FILTER -> RASTER_LOAD -> BAND_SELECT -> SPATIAL_FILTER -> ATTRIBUTE_FILTER -> VECTOR_LOAD -> RASTER_LOAD -> SPATIAL_CLIP -> RASTER_LOAD -> SPATIAL_CLIP -> RASTER_LOAD -> COMPOSITE -> RASTER_LOAD -> SPATIAL_FILTER -> RASTER_LOAD -> SPATIAL_FILTER -> RASTER_LOAD -> SPATIAL_JOIN -> ATTRIBUTE_FILTER -> RASTER_LOAD -> SPATIAL_CLIP -> RASTER_LOAD -> SPATIAL_CLIP -> RASTER_LOAD -> COMPOSITE -> RASTER_LOAD -> TEMPORAL_FILTER -> BAND_SELECT -> BAND_ARITHMETIC -> SPATIAL_CLIP -> MASKING -> GEOMETRY_DEFINE -> AGGREGATION -> RASTER_LOAD -> BAND_SELECT -> SPATIAL_FILTER -> ATTRIBUTE_FILTER -> VECTOR_LOAD -> RASTER_LOAD -> SPATIAL_CLIP -> RASTER_LOAD -> SPATIAL_CLIP -> RASTER_LOAD -> COMPOSITE -> RASTER_LOAD -> SPATIAL_FILTER -> RASTER_LOAD -> SPATIAL_FILTER -> RASTER_LOAD -> SPATIAL_JOIN -> ATTRIBUTE_FILTER -> RASTER_LOAD -> SPATIAL_CLIP -> RASTER_LOAD -> SPATIAL_CLIP -> RASTER_LOAD -> COMPOSITE -> RASTER_LOAD -> TEMPORAL_FILTER -> BAND_SELECT -> BAND_ARITHMETIC -> SPATIAL_CLIP -> MASKING -> GEOMETRY_DEFINE -> AGGREGATION -> RASTER_LOAD -> SPATIAL_CLIP -> RASTER_LOAD -> SPATIAL_CLIP -> RASTER_LOAD -> COMPOSITE -> RASTER_LOAD -> SPATIAL_FILTER -> RASTER_LOAD -> SPATIAL_FILTER -> RASTER_LOAD -> SPATIAL_JOIN -> ATTRIBUTE_FILTER -> RASTER_LOAD -> SPATIAL_CLIP -> RASTER_LOAD -> SPATIAL_CLIP -> RASTER_LOAD -> COMPOSITE -> ATTRIBUTE_FILTER -> AGGREGATION -> ATTRIBUTE_FILTER -> GEOMETRY_DEFINE -> RASTER_LOAD`  x1

## G-12  (n_rows=3, task_type=Land surface/agriculture indicators)
- **Instruction**: task: estimate vegetation coverage from ndvi calculate ndvi from landsat 5 surface reflectance data, masks clouds and water, computes fractional vegetation cover (fvc) using pixel percentiles, classifies fvc into five coverage levels, and exports the results along with a legend and area statistics table.
  - `AGGREGATION -> RASTER_LOAD -> TEMPORAL_FILTER -> ATTRIBUTE_FILTER -> COLLECTION_MGMT -> SPATIAL_FILTER -> AGGREGATION -> RASTER_LOAD -> BAND_ARITHMETIC -> BAND_SELECT -> AGGREGATION -> VECTOR_LOAD`  x2
  - `AGGREGATION -> RASTER_LOAD -> TEMPORAL_FILTER -> SPATIAL_FILTER -> COLLECTION_MGMT -> AGGREGATION -> RASTER_LOAD -> BAND_ARITHMETIC -> BAND_SELECT -> AGGREGATION -> VECTOR_LOAD`  x1

## G-13  (n_rows=2, task_type=Biospheric indicators)
- **Instruction**: task: smooth ndvi time series process a modis ndvi time series from 2016, applying a savitzky-golay filter to smooth the data for improved vegetation trend analysis.
  - `OTHER_UNMAPPED -> TEMPORAL_FILTER -> OTHER_UNMAPPED -> BAND_SELECT`  x1
  - `RASTER_LOAD -> TEMPORAL_FILTER -> BAND_SELECT`  x1

## G-14  (n_rows=3, task_type=Vegetation)
- **Instruction**: task: estimate vegetation cover fraction estimate fractional vegetation cover (fvc) from landsat 5 surface reflectance data by computing ndvi, generating a greenest-pixel composite, and applying a percentile-based fvc model. it classifies fvc into five levels, calculates area statistics per class, and exports maps and charts.
  - `AGGREGATION -> RASTER_LOAD -> TEMPORAL_FILTER -> SPATIAL_FILTER -> COLLECTION_MGMT -> AGGREGATION -> RASTER_LOAD -> BAND_ARITHMETIC -> BAND_SELECT -> AGGREGATION -> VECTOR_LOAD`  x2
  - `AGGREGATION -> RASTER_LOAD -> TEMPORAL_FILTER -> SPATIAL_FILTER -> AGGREGATION -> RASTER_LOAD -> BAND_ARITHMETIC -> BAND_SELECT -> AGGREGATION -> VECTOR_LOAD`  x1

## G-15  (n_rows=2, task_type=Precipitation)
- **Instruction**: task: calculate annual precipitation by region calculate the total annual precipitation for the year 2019 by summing daily chirps precipitation data, then extracts mean precipitation values for peruvian administrative regions and exports the results as a csv file.
  - `RASTER_LOAD -> BAND_SELECT -> AGGREGATION`  x1
  - `RASTER_LOAD -> BAND_SELECT -> RASTER_LOAD -> BAND_SELECT -> AGGREGATION`  x1

## G-16  (n_rows=2, task_type=Erosion/sedimentation)
- **Instruction**: task: estimate soil loss using rusle estimate annual soil loss in the mahi basin using the revised universal soil loss equation (rusle) model, combining rainfall erosivity (r), soil erodibility (k), slope length and steepness (ls), cover management (c), and support practice (p) factors. it outputs a soil loss map, classified soil loss severity, mean soil loss per subbasin, and area statistics by class for export.
  - `ATTRIBUTE_FILTER -> RASTER_LOAD -> TERRAIN_DERIVED -> RASTER_LOAD -> BAND_ARITHMETIC -> RASTER_LOAD -> AGGREGATION -> RASTER_LOAD -> AGGREGATION -> BAND_ARITHMETIC -> AGGREGATION -> BAND_ARITHMETIC -> BAND_SELECT -> AGGREGATION -> REGIONAL_STATS -> VECTOR_LOAD`  x1
  - `RASTER_LOAD -> TERRAIN_DERIVED -> RASTER_LOAD -> BAND_ARITHMETIC -> RASTER_LOAD -> AGGREGATION -> RASTER_LOAD -> AGGREGATION -> BAND_ARITHMETIC -> AGGREGATION -> BAND_ARITHMETIC -> BAND_SELECT -> AGGREGATION -> REGIONAL_STATS -> VECTOR_LOAD`  x1

## G-17  (n_rows=2, task_type=Land use/land cover)
- **Instruction**: task: classify land cover types classify land cover types in the arkavathy basin using a random forest classifier trained on sentinel-2 surface reflectance data, alos elevation, and derived spectral indices (ndvi, ndbi, mndwi, bsi), with accuracy assessment performed using ground control points.
  - `ATTRIBUTE_FILTER -> TEMPORAL_FILTER -> SPATIAL_FILTER -> TERRAIN_DERIVED -> BAND_ARITHMETIC -> ATTRIBUTE_FILTER -> CLASSIFICATION -> VECTOR_LOAD`  x1
  - `ATTRIBUTE_FILTER -> TEMPORAL_FILTER -> SPATIAL_FILTER -> TERRAIN_DERIVED -> AGGREGATION -> ATTRIBUTE_FILTER -> CLASSIFICATION -> VECTOR_LOAD`  x1

## G-18  (n_rows=2, task_type=Vegetation)
- **Instruction**: task: estimate vegetation coverage from ndvi calculate ndvi from landsat 5 surface reflectance data, identifies the greenest pixel composite based on ndvi, computes fractional vegetation cover (fvc) using ndvi percentiles, classifies fvc into five coverage levels, and exports classified maps and area statistics. it also generates a histogram and a table of area distribution by coverage class.
  - `AGGREGATION -> RASTER_LOAD -> TEMPORAL_FILTER -> SPATIAL_FILTER -> COLLECTION_MGMT -> AGGREGATION -> RASTER_LOAD -> BAND_ARITHMETIC -> BAND_SELECT -> AGGREGATION -> VECTOR_LOAD`  x1
  - `AGGREGATION -> RASTER_LOAD -> TEMPORAL_FILTER -> SPATIAL_FILTER -> AGGREGATION -> RASTER_LOAD -> BAND_ARITHMETIC -> BAND_SELECT -> AGGREGATION -> VECTOR_LOAD`  x1
