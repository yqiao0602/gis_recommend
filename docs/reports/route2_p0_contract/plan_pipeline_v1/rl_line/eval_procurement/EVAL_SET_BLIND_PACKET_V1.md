# 评估集盲评包 v1（24 任务 × 8 候选 = 192 候选，从未训练任务）

> 规则 v0.5.1；**盲评：不显示 r5 判定**。判定单位 = 候选 × r5-required 槽位。
> 标签口径同 Gate B：omission / covered / requirement_uncertain / representation_boundary / non_required + 候选级 unnecessary_stages。

## 组 script_150328（mid_5_8）

**任务全文：**

Task: Identify groundwater-dependent vegetation extent
Identify the spatial extent of groundwater-dependent ecosystems (GDEs) by buffering and unioning point and polygon features representing GDE indicators and well locations, then exports the resulting buffered and merged feature collection for further analysis or clipping. The output focuses on creating a consolidated geometry layer of potential GDE areas in California based on existing GDE and well data.

**r5-required 槽位：**
（无）

### 候选 0
```
1. ATTRIBUTE_FILTER x2
2. VECTOR_LOAD x3
```

### 候选 1
```
1. RASTER_LOAD x2
2. MASKING x1
```

### 候选 2
```
1. VECTOR_LOAD x2
2. AGGREGATION x1
```

### 候选 3
```
1. RASTER_LOAD x1
2. VECTOR_LOAD x1
3. ATTRIBUTE_FILTER x9
```

### 候选 4
```
1. AGGREGATION x4
2. ATTRIBUTE_FILTER x6
```

### 候选 5
```
1. ATTRIBUTE_FILTER x4
2. TEMPORAL_FILTER x1
```

### 候选 6
```
1. ATTRIBUTE_FILTER x2
2. VECTOR_LOAD x5
```

### 候选 7
```
1. VECTOR_LOAD x2
2. ATTRIBUTE_FILTER x1
3. ITERATIVE_APPLY x2
```

## 组 script_154762（mid_5_8）

**任务全文：**

Task: Analyze population and night light trends
Analyze spatiotemporal trends in population and night light intensity over Eastern Europe from 2015 to 2020. It uses WorldPop and nighttime light (NL) datasets, applies spatial clipping to a regional boundary, computes linear regression (linearFit) over time for trend estimation, and generates mean composite images. Outputs include slope rasters of population and night light trends, mean population and night light maps, and two regional time series charts showing mean population and night light values over the region, with trendlines. All key outputs are exported to Google Drive at 500m scale.

**r5-required 槽位：**
TEMPORAL, COMPOSITE, TERRAIN

（解析注：uncertain = ['SPATIAL']；词表边界 = ['CHART_PLOT']）

### 候选 0
```
1. RASTER_LOAD x4
2. BAND_SELECT x1
3. AGGREGATION x1
```

### 候选 1
```
1. RASTER_LOAD x2
2. SPATIAL_FILTER x1
3. TEMPORAL_FILTER x1
```

### 候选 2
```
1. RASTER_LOAD x4
2. BAND_SELECT x1
3. AGGREGATION x1
```

### 候选 3
```
1. RASTER_LOAD x1
2. ATTRIBUTE_FILTER x3
3. AGGREGATION x1
```

### 候选 4
```
1. RASTER_LOAD x3
2. SPATIAL_CLIP x1
```

### 候选 5
```
1. RASTER_LOAD x1
2. AGGREGATION x1
3. BAND_ARITHMETIC x1
4. VECTOR_LOAD x1
5. ATTRIBUTE_FILTER x2
```

### 候选 6
```
1. RASTER_LOAD x3
2. TEMPORAL_FILTER x1
3. ATTRIBUTE_FILTER x4
4. BAND_SELECT x1
5. AGGREGATION x2
```

### 候选 7
```
1. RASTER_LOAD x6
2. AGGREGATION x3
```

## 组 script_158835（long_9plus）

**任务全文：**

Task: Estimate daily evapotranspiration
Estimate daily actual evapotranspiration (ETa) across Australia using satellite-derived surface reflectance and meteorological data. It supports multiple input data sources including MODIS (MOD09A1/MOD09Q1, MCD43A4), Landsat 5/7/8 SR, Sentinel-2 SR, and VIIRS VNP09GA, combined with AGCD climate data (precipitation and potential evapotranspiration). The CMRSET algorithm is applied to compute ETa, with optional blending of high- and medium-resolution datasets using the BlenDLite framework. Outputs include gridded ETa maps, pixel quality assessments, and blended counts from different sensors, tailored for calibration against flux tower observations.

**r5-required 槽位：**
（无）

### 候选 0
```
1. RASTER_LOAD x1
2. TEMPORAL_FILTER x1
3. ATTRIBUTE_FILTER x1
4. AGGREGATION x1
5. BAND_SELECT x3
```

### 候选 1
```
1. VECTOR_LOAD x1
2. AGGREGATION x3
```

### 候选 2
```
1. RASTER_LOAD x1
2. ITERATIVE_APPLY x1
3. TEMPORAL_FILTER x1
4. AGGREGATION x4
```

### 候选 3
```
1. VECTOR_LOAD x1
2. ATTRIBUTE_FILTER x1
3. RASTER_LOAD x1
4. TEMPORAL_FILTER x1
5. SPATIAL_FILTER x1
6. BAND_SELECT x1
7. ITERATIVE_APPLY x1
8. AGGREGATION x2
```

### 候选 4
```
1. VECTOR_LOAD x1
2. AGGREGATION x1
3. RASTER_LOAD x1
4. TEMPORAL_FILTER x1
5. ATTRIBUTE_FILTER x1
```

### 候选 5
```
1. VECTOR_LOAD x1
2. ATTRIBUTE_FILTER x1
3. RASTER_LOAD x1
4. SPECTRAL_INDEX_ARITHMETIC x1
```

### 候选 6
```
1. VECTOR_LOAD x1
2. ATTRIBUTE_FILTER x1
3. RASTER_LOAD x1
4. SPATIAL_FILTER x1
5. TEMPORAL_FILTER x2
```

### 候选 7
```
1. VECTOR_LOAD x1
2. ATTRIBUTE_FILTER x2
3. RASTER_LOAD x1
4. SPATIAL_FILTER x1
5. AGGREGATION x2
```

## 组 script_160457（mid_5_8）

**任务全文：**

Task: Analyze subsidence time series
Analyze subsidence dynamics on Terceira Island using InSAR-derived displacement data from an ImageCollection. It computes temporal statistics including mean, median, maximum, and percentile (97.5th and 2.5th) values across the time series, visualizes them with color-coded maps, and generates a linear trend (velocity) map via linear regression over time. It also creates time-series charts of original and differenced data (absolute pairwise differences) to examine change magnitude and variability. The outputs include statistical summary maps, a linear fit trend layer, and two interactive charts showing temporal evolution and variation, with final exports of extreme percentile images to Earth Engine Assets.

**r5-required 槽位：**
STATS

（解析注：uncertain = 无；词表边界 = ['CHART_PLOT']）

### 候选 0
```
1. ATTRIBUTE_FILTER x1
2. AGGREGATION x3
3. RASTER_LOAD x1
4. BAND_SELECT x1
```

### 候选 1
```
1. ATTRIBUTE_FILTER x3
2. AGGREGATION x6
```

### 候选 2
```
1. AGGREGATION x1
2. BAND_ARITHMETIC x1
3. BAND_SELECT x1
```

### 候选 3
```
1. RASTER_LOAD x1
2. AGGREGATION x4
3. BAND_ARITHMETIC x1
4. AGGREGATION x2
```

### 候选 4
```
1. ATTRIBUTE_FILTER x5
2. AGGREGATION x4
```

### 候选 5
```
1. ATTRIBUTE_FILTER x1
2. RASTER_LOAD x2
3. AGGREGATION x7
```

### 候选 6
```
1. RASTER_LOAD x1
2. AGGREGATION x6
```

### 候选 7
```
1. AGGREGATION x3
2. RASTER_LOAD x1
3. SPATIAL_FILTER x1
4. ATTRIBUTE_FILTER x8
```

## 组 script_177161（short_2_4）

**任务全文：**

Task: Classify snow cover extent
Classify snow cover extent for the year 2017 over the HKH (Hindu Kush Himalaya) region using a Random Forest classifier applied to multispectral and covariate-enhanced composite imagery. Training points are derived from FAO-related sampled feature collections, where snow is labeled as class 1 and all other land covers as class 0. The model computes probabilities of snow presence, generates a continuous probability map masked by valid pixel coverage, and exports the result as a scaled UINT16 asset. Output includes a classified raster map of snow probability for 2017 at 30m resolution clipped to the HKH boundary buffer.

**r5-required 槽位：**
TEMPORAL, MASK, SPATIAL, COMPOSITE, CLASSIFY

### 候选 0
```
1. RASTER_LOAD x5
2. BAND_SELECT x1
3. CLASSIFICATION x1
```

### 候选 1
```
1. RASTER_LOAD x4
2. BAND_ARITHMETIC x1
3. ATTRIBUTE_FILTER x1
4. CLASSIFICATION x1
```

### 候选 2
```
1. RASTER_LOAD x4
2. BAND_SELECT x1
3. VECTOR_LOAD x1
4. ATTRIBUTE_FILTER x2
5. CLASSIFICATION x1
6. AGGREGATION x1
```

### 候选 3
```
1. RASTER_LOAD x4
2. BAND_SELECT x1
3. AGGREGATION x1
```

### 候选 4
```
1. RASTER_LOAD x4
2. BAND_SELECT x1
3. SPATIAL_FILTER x1
4. ATTRIBUTE_FILTER x1
5. CLASSIFICATION x1
```

### 候选 5
```
1. RASTER_LOAD x5
2. ATTRIBUTE_FILTER x2
```

### 候选 6
```
1. RASTER_LOAD x4
2. BAND_SELECT x1
3. ITERATIVE_APPLY x1
4. ATTRIBUTE_FILTER x3
5. CLASSIFICATION x1
```

### 候选 7
```
1. ATTRIBUTE_FILTER x2
2. RASTER_LOAD x4
3. BAND_SELECT x1
4. AGGREGATION x1
5. CLASSIFICATION x1
```

## 组 script_182431（long_9plus）

**任务全文：**

Task: Analyze chlorophyll-a monthly median
Compute monthly median chlorophyll-a concentrations from MODIS-Aqua ocean color data (2003–2024), clips the results to a user-defined area of interest (aoi), adds a day-of-year band, and exports both individual monthly images and time-composited median images to Google Drive. It also generates a feature collection summarizing median chlorophyll-a values over the AOI at 5km resolution and visualizes layered composites in the map interface.

**r5-required 槽位：**
TEMPORAL, SPATIAL

（解析注：uncertain = 无；词表边界 = ['CHART_PLOT']）

### 候选 0
```
1. RASTER_LOAD x1
2. BAND_SELECT x1
3. SPATIAL_FILTER x1
4. ATTRIBUTE_FILTER x6
5. AGGREGATION x8
```

### 候选 1
```
1. RASTER_LOAD x2
2. BAND_SELECT x1
3. TEMPORAL_FILTER x2
4. AGGREGATION x2
```

### 候选 2
```
1. RASTER_LOAD x1
2. TEMPORAL_FILTER x1
3. ATTRIBUTE_FILTER x1
4. AGGREGATION x2
```

### 候选 3
```
1. RASTER_LOAD x1
2. TEMPORAL_FILTER x6
```

### 候选 4
```
1. RASTER_LOAD x1
2. SPATIAL_FILTER x1
3. TEMPORAL_FILTER x2
4. AGGREGATION x1
```

### 候选 5
```
1. RASTER_LOAD x1
2. BAND_SELECT x1
3. TEMPORAL_FILTER x2
```

### 候选 6
```
1. RASTER_LOAD x1
2. TEMPORAL_FILTER x1
3. ATTRIBUTE_FILTER x1
4. BAND_SELECT x1
```

### 候选 7
```
1. RASTER_LOAD x1
2. BAND_SELECT x1
3. TEMPORAL_FILTER x1
4. AGGREGATION x7
```

## 组 script_187051（short_2_4）

**任务全文：**

Task: Analyze aerosol reflectance over AOI
Analyze mean aerosol reflectance in the B1 band (ultra-blue) of Sentinel-2 imagery over a small AOI from 2016-09-01 to 2017-09-30. It filters the Sentinel-2 image collection by date and region, clips each image to the AOI, computes the mean value of band B1 using reduceRegion, and appends this statistic as a property ('Aerosol_Mean') to each image. The output includes the size of the filtered collection, metadata of individual images, and visualization of up to 12 images using a false-color composite (B8, B3, B4), enabling visual inspection of surface and atmospheric features.

**r5-required 槽位：**
TEMPORAL, SPATIAL, COMPOSITE

（解析注：uncertain = 无；词表边界 = ['CHART_PLOT']）

### 候选 0
```
1. RASTER_LOAD x1
2. TEMPORAL_FILTER x1
3. ATTRIBUTE_FILTER x1
4. SPATIAL_FILTER x1
5. AGGREGATION x1
```

### 候选 1
```
1. RASTER_LOAD x1
2. TEMPORAL_FILTER x1
3. GEOMETRY_DEFINE x1
4. AGGREGATION x2
```

### 候选 2
```
1. VECTOR_LOAD x1
2. RASTER_LOAD x1
3. TEMPORAL_FILTER x1
4. SPATIAL_FILTER x1
5. ATTRIBUTE_FILTER x2
```

### 候选 3
```
1. RASTER_LOAD x1
2. ATTRIBUTE_FILTER x1
3. TEMPORAL_FILTER x1
4. SPATIAL_FILTER x1
5. VECTOR_GEOMETRY x1
```

### 候选 4
```
1. RASTER_LOAD x1
2. TEMPORAL_FILTER x1
3. GEOMETRY_DEFINE x1
4. AGGREGATION x1
```

### 候选 5
```
1. RASTER_LOAD x1
2. TEMPORAL_FILTER x1
3. SPATIAL_FILTER x1
4. AGGREGATION x1
```

### 候选 6
```
1. SPATIAL_FILTER x1
2. RASTER_LOAD x1
3. TEMPORAL_FILTER x1
```

### 候选 7
```
1. RASTER_LOAD x1
2. TEMPORAL_FILTER x1
3. ATTRIBUTE_FILTER x1
```

## 组 script_192304（long_9plus）

**任务全文：**

Task: Correct topographic effects on Landsat reflectance
the workflow corrects topographic illumination effects on Landsat 8 TOA reflectance using a terrain-based irradiance correction model (IC2Ref) that incorporates slope, aspect, solar zenith, and solar azimuth. It applies cloud masking via BQA band, computes topographic normalization using empirical regression coefficients per band, aggregates images from 2020–2021 over the AOI, extracts 15th, 50th, and 85th percentiles as representative min/median/max values, scales them for 16-bit depth, combines into a single multi-band image, converts to 8-bit, and exports the result. Outputs include a composite image with min/med/max bands for B2–B6 and visualizations in RGB combinations (654 and 432), intended for downstream analysis requiring radiometrically consistent surface reflectance under variable terrain illumination.

**r5-required 槽位：**
TEMPORAL, MASK, COMPOSITE, TERRAIN

（解析注：uncertain = 无；词表边界 = ['CHART_PLOT']）

### 候选 0
```
1. AGGREGATION x1
2. RASTER_LOAD x1
3. TEMPORAL_FILTER x1
```

### 候选 1
```
1. RASTER_LOAD x2
2. SPATIAL_FILTER x1
3. TEMPORAL_FILTER x1
4. COLLECTION_MGMT x1
```

### 候选 2
```
1. AGGREGATION x1
2. RASTER_LOAD x1
3. ATTRIBUTE_FILTER x2
```

### 候选 3
```
1. RASTER_LOAD x1
2. SPATIAL_FILTER x1
3. AGGREGATION x1
```

### 候选 4
```
1. AGGREGATION x1
2. RASTER_LOAD x1
3. SPATIAL_FILTER x1
4. TEMPORAL_FILTER x1
```

### 候选 5
```
1. RASTER_LOAD x1
2. AGGREGATION x3
```

### 候选 6
```
1. AGGREGATION x3
2. RASTER_LOAD x1
3. SPATIAL_FILTER x1
4. TEMPORAL_FILTER x1
```

### 候选 7
```
1. SPATIAL_FILTER x1
2. TEMPORAL_FILTER x1
3. RASTER_LOAD x1
4. AGGREGATION x2
```

## 组 script_19546（short_2_4）

**任务全文：**

Task: Find earliest planting and latest harvest dates
Calculate the minimum value of 'EkimTarihi' (planting date) greater than 0 and the maximum value of 'HasatTarih' (harvest date) from a feature collection, outputting these temporal extremes to identify the initial planting and final harvest dates in the dataset.

**r5-required 槽位：**
（无）

### 候选 0
```
1. RASTER_LOAD x1
2. TEMPORAL_FILTER x5
```

### 候选 1
```
1. RASTER_LOAD x2
2. TEMPORAL_FILTER x3
```

### 候选 2
```
1. RASTER_LOAD x1
2. BAND_SELECT x4
```

### 候选 3
```
1. RASTER_LOAD x2
2. ITERATIVE_APPLY x1
3. TEMPORAL_FILTER x4
```

### 候选 4
```
1. RASTER_LOAD x2
2. TEMPORAL_FILTER x3
```

### 候选 5
```
1. RASTER_LOAD x2
2. MASKING x1
```

### 候选 6
```
1. RASTER_LOAD x2
2. TEMPORAL_FILTER x1
```

### 候选 7
```
1. RASTER_LOAD x1
2. BAND_SELECT x1
```

## 组 script_201566（long_9plus）

**任务全文：**

Task: Classify seasonal water bodies using SAR and optical data
Identify and classifies seasonal water bodies in a polar region by combining Sentinel-2 optical imagery (NDWI-based classification) with Sentinel-1 SAR data (HH-HV backscatter difference and refined Lee filtering). It first generates a maximum water extent mask from cloud-filtered Sentinel-2 imagery between June and October 2019, then integrates terrain slope from ArcticDEM and temporal HH-subtracted HV intensity from Sentinel-1 during December 2020 and June 2020 to refine water detection. The output includes a binary water mask, vector polygons of water features with area filtering (49,500–40,000,000 m²), and a final classified raster based on histogram thresholding (Otsu/Rosin) applied per polygon, resulting in a refined surface water map.

**r5-required 槽位：**
TEMPORAL, MASK, CLASSIFY, TERRAIN

（解析注：uncertain = ['INDEX']；词表边界 = ['CHART_PLOT']）

### 候选 0
```
```

### 候选 1
```
1. VECTOR_LOAD x1
2. ATTRIBUTE_FILTER x6
3. BAND_SELECT x1
4. RASTER_LOAD x1
5. SPATIAL_CLIP x1
6. TEMPORAL_FILTER x2
```

### 候选 2
```
1. RASTER_LOAD x1
2. SPATIAL_CLIP x1
3. ATTRIBUTE_FILTER x6
4. TEMPORAL_FILTER x1
5. BAND_SELECT x1
6. ITERATIVE_APPLY x1
```

### 候选 3
```
1. VECTOR_LOAD x1
2. AGGREGATION x1
3. RASTER_LOAD x1
4. TEMPORAL_FILTER x1
5. ATTRIBUTE_FILTER x6
6. SPATIAL_FILTER x1
7. BAND_SELECT x1
8. RASTER_LOAD x1
```

### 候选 4
```
1. RASTER_LOAD x3
2. TEMPORAL_FILTER x1
3. ATTRIBUTE_FILTER x1
4. SPATIAL_FILTER x1
5. AGGREGATION x1
```

### 候选 5
```
1. ATTRIBUTE_FILTER x3
2. RASTER_LOAD x1
3. BAND_SELECT x1
4. TEMPORAL_FILTER x1
5. SPATIAL_FILTER x1
6. AGGREGATION x1
7. RASTER_LOAD x1
8. ITERATIVE_APPLY x1
9. VECTOR_LOAD x1
```

### 候选 6
```
1. ATTRIBUTE_FILTER x1
2. VECTOR_LOAD x1
3. RASTER_LOAD x1
4. TEMPORAL_FILTER x2
5. SPATIAL_FILTER x2
6. ATTRIBUTE_FILTER x7
7. AGGREGATION x4
```

### 候选 7
```
1. RASTER_LOAD x1
2. ATTRIBUTE_FILTER x7
3. BAND_SELECT x1
4. SPATIAL_FILTER x1
5. TEMPORAL_FILTER x1
6. AGGREGATION x2
```

## 组 script_202426（long_9plus）

**任务全文：**

Task: Detect forest disturbance using Delta-rNBR
Detect forest disturbances by computing the difference in relative spectral indices (e.g., rNBR) between a reference and an analysis period using Landsat or Sentinel-2 imagery. It applies self-referencing normalization via focal median adjustment and capping, followed by disturbance-density-related (DDR) filtering to remove isolated noise. Outputs include mapped delta-rNBR layers, optional exports of single rNBR composites, dates, forest masks, and filtered results, with support for multiple sensors and user-defined spatial regions.

**r5-required 槽位：**
MASK

### 候选 0
```
1. AGGREGATION x1
2. ATTRIBUTE_FILTER x4
```

### 候选 1
```
1. RASTER_LOAD x3
2. SPATIAL_FILTER x1
3. ITERATIVE_APPLY x5
```

### 候选 2
```
1. ATTRIBUTE_FILTER x3
2. AGGREGATION x1
3. EXPORT_OUTPUT x1
```

### 候选 3
```
1. ATTRIBUTE_FILTER x3
2. RASTER_LOAD x1
3. SPATIAL_FILTER x1
4. TEMPORAL_FILTER x1
5. COLLECTION_MGMT x1
6. AGGREGATION x8
```

### 候选 4
```
1. RASTER_LOAD x2
2. BAND_SELECT x1
3. SPATIAL_FILTER x1
4. ATTRIBUTE_FILTER x2
5. TEMPORAL_FILTER x2
```

### 候选 5
```
1. RASTER_LOAD x1
2. BAND_SELECT x3
```

### 候选 6
```
```

### 候选 7
```
1. AGGREGATION x3
2. VECTOR_LOAD x1
3. ATTRIBUTE_FILTER x4
```

## 组 script_211527（mid_5_8）

**任务全文：**

Task: Model surface air temperature elevation-adjusted
the workflow models daily surface air temperature adjusted for elevation effects using GLDAS data and NASADEM. It retrieves hourly air temperature at 12:00, converts from Kelvin to Celsius, applies a lapse rate correction using 27.83 km and 1 km resampled DEMs, performs inverse distance interpolation of temperature at point locations, and outputs an elevation-corrected interpolated temperature raster for the region of interest.

**r5-required 槽位：**
TEMPORAL

### 候选 0
```
1. VECTOR_LOAD x1
2. ATTRIBUTE_FILTER x1
3. RASTER_LOAD x4
```

### 候选 1
```
1. RASTER_LOAD x1
2. BAND_SELECT x1
3. AGGREGATION x1
```

### 候选 2
```
1. RASTER_LOAD x1
2. SPATIAL_FILTER x1
3. TEMPORAL_FILTER x1
4. BAND_SELECT x1
```

### 候选 3
```
1. RASTER_LOAD x5
2. BAND_SELECT x1
3. SPATIAL_CLIP x1
```

### 候选 4
```
1. RASTER_LOAD x4
2. VECTOR_LOAD x6
```

### 候选 5
```
1. ATTRIBUTE_FILTER x1
2. RASTER_LOAD x1
3. BAND_SELECT x1
```

### 候选 6
```
1. RASTER_LOAD x1
2. SPATIAL_FILTER x1
3. TEMPORAL_FILTER x2
4. ATTRIBUTE_FILTER x1
5. AGGREGATION x1
```

### 候选 7
```
1. VECTOR_LOAD x1
2. COLLECTION_MGMT x1
3. RASTER_LOAD x1
4. TEMPORAL_FILTER x1
5. ATTRIBUTE_FILTER x1
6. AGGREGATION x2
```

## 组 script_231195（short_2_4）

**任务全文：**

Task: Analyze land surface temperature
Analyze the land surface temperature (LST) time series for Argentina using MODIS MOD11A1 data from 2018. It processes daily LST images by converting digital values to Celsius, computes a mean annual temperature map clipped to the national boundary, generates a time-series chart of mean LST using regional reduction, and exports the clipped mean temperature raster to Google Drive. Outputs include a time-series graph, a mapped temperature layer, and a geotiff export.

**r5-required 槽位：**
TEMPORAL, SPATIAL, STATS

（解析注：uncertain = 无；词表边界 = ['CHART_PLOT']）

### 候选 0
```
1. VECTOR_LOAD x1
2. ATTRIBUTE_FILTER x1
3. RASTER_LOAD x1
4. TEMPORAL_FILTER x1
5. BAND_SELECT x1
6. AGGREGATION x2
```

### 候选 1
```
1. VECTOR_LOAD x1
2. ATTRIBUTE_FILTER x3
```

### 候选 2
```
1. RASTER_LOAD x3
2. TEMPORAL_FILTER x1
3. AGGREGATION x1
4. VECTOR Load x1
```

### 候选 3
```
1. ATTRIBUTE_FILTER x1
2. RASTER_LOAD x1
3. TEMPORAL_FILTER x1
4. AGGREGATION x1
```

### 候选 4
```
1. VECTOR_LOAD x1
2. ATTRIBUTE_FILTER x3
3. RASTER_LOAD x1
4. TEMPORAL_FILTER x1
5. AGGREGATION x2
```

### 候选 5
```
1. ATTRIBUTE_FILTER x1
2. AGGREGATION x1
```

### 候选 6
```
1. VECTOR_LOAD x1
2. ATTRIBUTE_FILTER x1
3. RASTER_LOAD x1
4. TEMPORAL_FILTER x1
5. SPATIAL_FILTER x1
6. BAND_SELECT x1
```

### 候选 7
```
1. ATTRIBUTE_FILTER x1
2. RASTER_LOAD x1
3. TEMPORAL_FILTER x1
4. AGGREGATION x1
```

## 组 script_235273（long_9plus）

**任务全文：**

Task: Monitor sea surface temperature and chlorophyll-a
Analyze sea surface temperature (SST) and chlorophyll-a concentration around Mauritius using GCOM-C satellite data. It retrieves two time-period averages (former and latest) for both SST and chlorophyll-a, applies calibration and logarithmic transformation, visualizes the results with color palettes, and overlays legends on the map. The output includes four layered visualizations: SST and chlorophyll-a for both periods, with legends for interpretation, but no explicit export is triggered in the final display logic.

**r5-required 槽位：**
（无）

（解析注：uncertain = 无；词表边界 = ['CHART_PLOT']）

### 候选 0
```
1. VECTOR_LOAD x2
2. RASTER_LOAD x2
3. BAND_ARITHMETIC x4
```

### 候选 1
```
1. BAND_SELECT x2
2. RASTER_LOAD x1
3. TEMPORAL_FILTER x1
```

### 候选 2
```
1. ATTRIBUTE_FILTER x2
2. RASTER_LOAD x1
```

### 候选 3
```
1. RASTER_LOAD x2
2. TEMPORAL_FILTER x2
3. RASTER_LOAD x1
4. BAND_SELECT x1
```

### 候选 4
```
1. RASTER_LOAD x2
2. TEMPORAL_FILTER x1
3. BAND_SELECT x1
```

### 候选 5
```
1. VECTOR_LOAD x1
2. ATTRIBUTE_FILTER x5
```

### 候选 6
```
1. RASTER_LOAD x2
2. TEMPORAL_FILTER x1
3. BAND_SELECT x1
4. AGGREGATION x1
5. RASTER_LOAD x2
6. SPATIAL_CLIP x1
```

### 候选 7
```
1. AGGREGATION x2
2. BAND_ARITHMETIC x1
3. BAND_SELECT x1
4. RASTER_LOAD x1
```

## 组 script_241490（mid_5_8）

**任务全文：**

Task: Map surface water extent
Map surface water extent in 2020 within selected sub-districts of Dhaka, Bangladesh, using the Global Surface Water (GSW) dataset. It filters GSW yearly data to year 2020, extracts water bodies (classes 2 and 3: seasonal and permanent water), clips to user-selected administrative boundaries, visualizes water as blue pixels on the map, computes total water area in hectares using pixel area summation at 30m resolution, and displays the result dynamically in a UI panel upon region selection.

**r5-required 槽位：**
TEMPORAL, SPATIAL

（解析注：uncertain = 无；词表边界 = ['CHART_PLOT']）

### 候选 0
```
1. ATTRIBUTE_FILTER x1
2. RASTER_LOAD x1
3. TEMPORAL_FILTER x1
```

### 候选 1
```
1. ATTRIBUTE_FILTER x1
2. RASTER_LOAD x1
3. TEMPORAL_FILTER x1
4. SPATIAL_FILTER x1
```

### 候选 2
```
1. ATTRIBUTE_FILTER x1
2. BAND_ARITHMETIC x4
3. AGGREGATION x1
```

### 候选 3
```
1. BAND_ARITHMETIC x2
2. ATTRIBUTE_FILTER x1
3. TEMPORAL_FILTER x1
4. SPATIAL_CLIP x1
```

### 候选 4
```
1. RASTER_LOAD x1
2. TEMPORAL_FILTER x1
3. ATTRIBUTE_FILTER x1
4. BAND_ARITHMETIC x1
```

### 候选 5
```
1. VECTOR_LOAD x2
2. ATTRIBUTE_FILTER x1
3. BAND_ARITHMETIC x2
4. AGGREGATION x1
```

### 候选 6
```
1. BAND_ARITHMETIC x1
2. MASKING x1
3. AGGREGATION x1
```

### 候选 7
```
1. RASTER_LOAD x1
2. TEMPORAL_FILTER x1
3. BAND_ARITHMETIC x2
```

## 组 script_291385（long_9plus）

**任务全文：**

Task: Model erosion deposition ratio
the workflow models the ratio of erosion to deposition (erdep) using RUSLE output, where positive values indicate deposition and negative values (inverted) indicate erosion. It aggregates both components over hexagonal grid cells using sum reduction, then computes their ratio. Additional environmental predictors—including maximum NDVI from Landsat 8, soil organic carbon, vegetation greenness trend from MODIS SAVI, elevation from ALOS DSM, and proportional coverage of cultivated areas—are generated over the same grid. All layers are combined into a single multiband image 'predictors' for potential use in spatial modeling or machine learning. Outputs include individual rasters (erdep, maxndvi, carbon, trend, elev, pcv), a composite predictor layer, and vector-to-raster converted feature collections.

**r5-required 槽位：**
INDEX, COMPOSITE

### 候选 0
```
1. RASTER_LOAD x2
2. SPATIAL_CLIP x1
3. RASTER_LOAD x1
4. AGGREGATION x1
```

### 候选 1
```
1. RASTER_LOAD x2
2. ATTRIBUTE_FILTER x3
3. AGGREGATION x1
```

### 候选 2
```
1. VECTOR_LOAD x1
2. ATTRIBUTE_FILTER x4
3. RASTER_LOAD x1
4. SPATIAL_FILTER x1
5. AGGREGATION x1
```

### 候选 3
```
1. AGGREGATION x1
2. RASTER_LOAD x1
3. TEMPORAL_FILTER x1
4. SPATIAL_FILTER x1
5. ATTRIBUTE_FILTER x1
6. BAND_SELECT x1
```

### 候选 4
```
1. AGGREGATION x2
2. RASTER_LOAD x1
3. TEMPORAL_FILTER x2
```

### 候选 5
```
1. RASTER_LOAD x1
2. ATTRIBUTE_FILTER x1
3. BAND_SELECT x3
```

### 候选 6
```
1. RASTER_LOAD x1
2. ATTRIBUTE_FILTER x5
3. TEMPORAL_FILTER x2
```

### 候选 7
```
1. RASTER_LOAD x2
2. SPATIAL_FILTER x1
3. AGGREGATION x2
```

## 组 script_31001（short_2_4）

**任务全文：**

Task: Analyze SST over time
Calculate monthly mean sea surface temperature (SST) from MODIS-Aqua L3SMI data between January 2019 and June 2020, visualizes the first month's SST on a map, and generates two time series charts: one showing SST variation over time at a point, and another displaying SST by day of year for each year.

**r5-required 槽位：**
TEMPORAL, STATS

（解析注：uncertain = 无；词表边界 = ['CHART_PLOT']）

### 候选 0
```
1. RASTER_LOAD x1
2. BAND_SELECT x1
3. TEMPORAL_FILTER x1
4. AGGREGATION x1
```

### 候选 1
```
1. RASTER_LOAD x1
2. TEMPORAL_FILTER x1
3. ATTRIBUTE_FILTER x1
4. AGGREGATION x2
```

### 候选 2
```
1. RASTER_LOAD x1
2. TEMPORAL_FILTER x1
3. AGGREGATION x1
```

### 候选 3
```
1. RASTER_LOAD x2
2. SPATIAL_FILTER x1
3. BAND_SELECT x1
4. ATTRIBUTE_FILTER x1
```

### 候选 4
```
1. RASTER_LOAD x1
2. BAND_SELECT x1
3. AGGREGATION x2
```

### 候选 5
```
1. RASTER_LOAD x1
2. TEMPORAL_FILTER x1
3. ATTRIBUTE_FILTER x2
4. AGGREGATION x5
```

### 候选 6
```
1. RASTER_LOAD x1
2. BAND_SELECT x1
3. SPATIAL_FILTER x1
4. AGGREGATION x1
```

### 候选 7
```
1. RASTER_LOAD x1
2. BAND_SELECT x1
3. AGGREGATION x2
```

## 组 script_32052（mid_5_8）

**任务全文：**

Task: Calculate mean monthly solar radiation
Calculate the mean monthly solar radiation (srad) for each month from 2000 to 2020 at specific weather station locations by extracting TerraClimate data, aggregating it temporally and spatially, and exporting the results per station.

**r5-required 槽位：**
TEMPORAL

### 候选 0
```
1. RASTER_LOAD x1
2. TEMPORAL_FILTER x1
3. ATTRIBUTE_FILTER x1
4. AGGREGATION x4
```

### 候选 1
```
1. RASTER_LOAD x3
2. TEMPORAL_FILTER x2
3. BAND_SELECT x4
```

### 候选 2
```
1. RASTER_LOAD x1
2. TEMPORAL_FILTER x1
3. ATTRIBUTE_FILTER x1
```

### 候选 3
```
1. RASTER_LOAD x1
2. TEMPORAL_FILTER x36
```

### 候选 4
```
1. RASTER_LOAD x1
2. TEMPORAL_FILTER x39
```

### 候选 5
```
```

### 候选 6
```
1. RASTER_LOAD x1
2. TEMPORAL_FILTER x327
3. ATTRIBUTE_FILTER x2
```

### 候选 7
```
1. RASTER_LOAD x1
2. TEMPORAL_FILTER x1
3. ITERATIVE_APPLY x1
```

## 组 script_407954（mid_5_8）

**任务全文：**

Task: Estimate canopy cover and height
Generate two pairs of spatially aligned, resampled raster layers (250 m resolution, EPSG:4326) representing canopy cover (%) for circa-2001 and circa-2020, and canopy height (m) for 2000 and 2020. Canopy cover is derived by fusing MODIS MOD44B (v061 and v006) and custom GLOBMAPFTC data via temporal compositing (3-year windows: [2000–2002] and [2019–2021]), applying latitude-based sensor version switching (MOD44B v061 north of 57.5°N replaced with v006), and mean resampling. Canopy height is sourced from GLCLU2020 Forest Height products (2000 and 2020), reprojected from native ~30 m to 250 m. All outputs are exported to Google Drive as GeoTIFFs and visualized in the Code Editor with standardized palettes.

**r5-required 槽位：**
TEMPORAL

（解析注：uncertain = 无；词表边界 = ['CHART_PLOT']）

### 候选 0
```
```

### 候选 1
```
```

### 候选 2
```
```

### 候选 3
```
```

### 候选 4
```
```

### 候选 5
```
```

### 候选 6
```
```

### 候选 7
```
```

## 组 script_408172（long_9plus）

**任务全文：**

Task: Detect clouds and cloud shadows
the workflow implements a multi-stage cloud and cloud shadow detection workflow for optical satellite imagery. It computes a cloud score mask using brightness in visible/infrared bands and normalized difference indices (NDVI-like and NDSI), applies the TDOM (Temporal Dark Object Method) to identify cloud shadows based on NIR/SWIR z-scores and darkness thresholds, and projects cloud shadows geometrically using solar geometry and user-defined cloud height assumptions. Outputs are multi-band images with added masks: 'cloudScoreMask', 'tdomMask', 'shadowTdomMask', and 'cloudBQAMask'/'shadowBQAMask', enabling comprehensive cloud and shadow masking for downstream analysis.

**r5-required 槽位：**
MASK, INDEX

### 候选 0
```
1. RASTER_LOAD x4
2. AGGREGATION x3
```

### 候选 1
```
1. ATTRIBUTE_FILTER x2
2. RASTER_LOAD x1
3. AGGREGATION x1
```

### 候选 2
```
1. ATTRIBUTE_FILTER x2
2. RASTER_LOAD x2
```

### 候选 3
```
1. RASTER_LOAD x3
2. MASKING x1
3. ATTRIBUTE_FILTER x6
```

### 候选 4
```
1. RASTER_LOAD x2
2. TEMPORAL_FILTER x4
```

### 候选 5
```
1. AGGREGATION x2
2. RASTER_LOAD x1
3. TEMPORAL_FILTER x1
```

### 候选 6
```
1. RASTER_LOAD x2
2. AGGREGATION x3
```

### 候选 7
```
1. ATTRIBUTE_FILTER x2
2. RASTER_LOAD x1
3. TEMPORAL_FILTER x1
4. AGGREGATION x5
```

## 组 script_411264（short_2_4）

**任务全文：**

Task: Map coastline change over time
Map temporal coastline change across three years (1990, 2005, 2023) by generating annual land/water masks using NDWI thresholding (NDWI ≥ 0.1 for water, < 0.1 for land) applied to Landsat surface reflectance composites; it outputs (1) animated GIF visualizing RGB composites (B6–NIR, B5–SWIR, B2–BLUE) over time, (2) vectorized coastline polygons per year (simplified and clipped to ROI), (3) a classified raster stack ('coast' band encoding year of first land occurrence), (4) styled vector layers for map display with year-coded colors, and (5) a legend panel showing year–color mapping. The workflow includes sensor-specific cloud masking (QA_PIXEL bitmasks for TM/ETM+ and OLI), spectral band harmonization (B2–B7 mapped to consistent band names), radiometric scaling (multiply by 0.0000275 + add −0.2), NDWI computation, binary land/water classification, vectorization via reduceToVectors, geometry simplification, buffering, and intersection with ROI.

**r5-required 槽位：**
TEMPORAL, MASK, INDEX, SPATIAL, CLASSIFY

（解析注：uncertain = 无；词表边界 = ['CHART_PLOT']）

### 候选 0
```
```

### 候选 1
```
```

### 候选 2
```
```

### 候选 3
```
```

### 候选 4
```
```

### 候选 5
```
```

### 候选 6
```
```

### 候选 7
```
```

## 组 script_411270（short_2_4）

**任务全文：**

Task: Detect fog occurrence conditions
Identify hourly fog occurrence conditions across the expanded Southeast US region (100°W–80°W, 25°N–35°N) during October 1–December 31, 2023, using ERA5-Land hourly meteorological variables. It computes relative humidity and temperature-dew point spread from 2m temperature and dew point, derives wind speed from u/v components, calculates net radiation from solar and thermal surface fluxes, and applies a multi-criteria fog detection rule (RH > 95%, spread < 2°C, wind < 5 m/s, and either negative net radiation or positive latent heat flux). It aggregates hourly detections into daily binary fog event layers (one per day), stacks them into a 92-band GeoTIFF, and appends a summary band of total fog event count per pixel over the period. The final output is a multi-band raster suitable for spatiotemporal fog frequency analysis.

**r5-required 槽位：**
TEMPORAL

### 候选 0
```
```

### 候选 1
```
```

### 候选 2
```
```

### 候选 3
```
```

### 候选 4
```
```

### 候选 5
```
```

### 候选 6
```
```

### 候选 7
```
```

## 组 script_61437（short_2_4）

**任务全文：**

Task: Analyze HV backscatter over time
Analyze the temporal variation of SAR backscatter (HV polarization) from Sentinel-1 over multiple buffered point regions in northern Quebec, Canada, between April 2015 and October 2016. It generates a scatter chart showing mean HV backscatter in decibels over time for 16 regions, with one highlighted in red (Pt3), and exports metadata of the filtered image collection as CSV.

**r5-required 槽位：**
TEMPORAL

（解析注：uncertain = 无；词表边界 = ['CHART_PLOT']）

### 候选 0
```
1. ATTRIBUTE_FILTER x1
2. RASTER_LOAD x1
3. BAND_SELECT x1
4. TEMPORAL_FILTER x1
5. SPATIAL_FILTER x1
6. AGGREGATION x1
```

### 候选 1
```
1. RASTER_LOAD x1
2. BAND_SELECT x2
3. TEMPORAL_FILTER x1
4. VECTOR_LOAD x8
```

### 候选 2
```
1. GEOMETRY_DEFINE x1
2. RASTER_LOAD x1
3. SPATIAL_FILTER x1
4. ATTRIBUTE_FILTER x3
5. AGGREGATION x1
```

### 候选 3
```
1. RASTER_LOAD x1
2. TEMPORAL_FILTER x1
3. ATTRIBUTE_FILTER x2
4. VECTOR_LOAD x1
5. AGGREGATION x1
```

### 候选 4
```
1. RASTER_LOAD x1
2. ATTRIBUTE_FILTER x4
```

### 候选 5
```
1. RASTER_LOAD x1
2. TEMPORAL_FILTER x1
3. ATTRIBUTE_FILTER x7
4. SPATIAL_FILTER x1
```

### 候选 6
```
1. VECTOR_LOAD x1
2. ATTRIBUTE_FILTER x4
3. RASTER_LOAD x1
4. TEMPORAL_FILTER x1
```

### 候选 7
```
1. RASTER_LOAD x1
2. TEMPORAL_FILTER x1
3. GEOMETRY_DEFINE x2
```

## 组 script_74076（mid_5_8）

**任务全文：**

Task: Identify flooded rice areas
Identify flooded rice cultivation areas by detecting surface water changes using Sentinel-1 SAR imagery. It computes the difference in VV backscatter between consecutive biweekly periods, applies focal median smoothing and thresholding to detect significant drops in radar signal (indicative of flooding), masks for flooded areas, and calculates the total flooded area per administrative tehsil. Outputs include binary flood maps and tabular summaries of flooded area in square meters for each tehsil across multiple time intervals from June to August 2017.

**r5-required 槽位：**
TEMPORAL, MASK, STATS

（解析注：uncertain = 无；词表边界 = ['CHART_PLOT']）

### 候选 0
```
1. VECTOR_LOAD x3
2. ATTRIBUTE_FILTER x4
3. RASTER_LOAD x1
4. SPATIAL_FILTER x1
5. TEMPORAL_FILTER x1
```

### 候选 1
```
1. ATTRIBUTE_FILTER x1
2. AGGREGATION x3
```

### 候选 2
```
1. RASTER_LOAD x1
2. SPATIAL_FILTER x1
3. TEMPORAL_FILTER x1
4. ATTRIBUTE_FILTER x6
5. AGGREGATION x5
```

### 候选 3
```
1. RASTER_LOAD x1
2. ATTRIBUTE_FILTER x8
```

### 候选 4
```
1. ATTRIBUTE_FILTER x2
2. AGGREGATION x1
```

### 候选 5
```
1. RASTER_LOAD x5
2. SPATIAL_FILTER x1
3. ATTRIBUTE_FILTER x8
4. TEMPORAL_FILTER x1
```

### 候选 6
```
1. ATTRIBUTE_FILTER x3
2. BAND_ARITHMETIC x1
3. MASKING x1
```

### 候选 7
```
1. RASTER_LOAD x1
2. SPATIAL_FILTER x1
3. ATTRIBUTE_FILTER x4
4. TEMPORAL_FILTER x1
5. AGGREGATION x2
```
