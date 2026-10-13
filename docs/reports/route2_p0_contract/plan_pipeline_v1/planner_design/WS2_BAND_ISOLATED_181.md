# WS2_BAND_ISOLATED_181

## k=1 — Task: Compute NDVI time series

Task: Compute NDVI time series
Compute a cloud-masked NDVI time series from Sentinel-2 Level-2A (SR Harmonized) imagery for a user-defined AOI (identified by 'id' = 1 in a feature collection), spanning 2023. It applies a strict cloud filter (≤5% cloudy pixels), masks clouds and cirrus using QA60 bits 10 and 11, scales reflectance to physical units (÷10000), calculates NDVI as normalizedDifference(['B3','B8']), selects only the NDVI band, clips to the AOI, and exports the full ImageCollection as 

- gold BAND_SELECT 位置: [{'seq': 6, 'prev': 'ITERATIVE_APPLY', 'next': None}]
- 下游消费者: （无——isolated）
- owner_ruling: ______（gold_inconsistent / alternative_workflow / clearly_necessary）

## k=8 — Task: Extract VV backscatter over orbit 131

Task: Extract VV backscatter over orbit 131
the workflow retrieves Sentinel-1 GRD imagery with VV polarization from the IW acquisition mode, filtering by a specific relative orbit number (131) and a fixed date range. It selects only the 'VV' band and outputs the filtered image collection and its size, likely for time-series analysis or as input for land surface monitoring in a specific geographic region intersecting this orbit.

- gold BAND_SELECT 位置: [{'seq': 3, 'prev': 'ATTRIBUTE_FILTER', 'next': 'ATTRIBUTE_FILTER'}]
- 下游消费者: （无——isolated）
- owner_ruling: ______（gold_inconsistent / alternative_workflow / clearly_necessary）

## k=18 — Task: Classify land cover in 1995

Task: Classify land cover in 1995
Classify historical land use and land cover in 1995 using Landsat 5 imagery, trained by 2020 reference data through a Random Forest classifier. It generates a classified map of six land cover types—plowland, other vegetation, eucalyptus, water, and constructed areas—and evaluates classification accuracy using an error matrix, including overall accuracy, kappa, and producer/user accuracies. The final output is exported as a GeoTIFF to Google Drive.

- gold BAND_SELECT 位置: [{'seq': 13, 'prev': 'AGGREGATION', 'next': 'ATTRIBUTE_FILTER'}]
- 下游消费者: （无——isolated）
- owner_ruling: ______（gold_inconsistent / alternative_workflow / clearly_necessary）

## k=19 — Task: Classify land cover types

Task: Classify land cover types
Classify land cover types using a Random Forest classifier trained on spectral, texture (GLCM), and index features (NDVI, NDWI, NDBI) derived from a single Landsat 5 TM image. The output is a classified land cover map and an error/confusion matrix based on test samples.

- gold BAND_SELECT 位置: [{'seq': 4, 'prev': 'SPATIAL_FILTER', 'next': 'RASTER_LOAD'}]
- 下游消费者: （无——isolated）
- owner_ruling: ______（gold_inconsistent / alternative_workflow / clearly_necessary）

## k=26 — Task: Map artisanal gold mining sites

Task: Map artisanal gold mining sites
Map Artisanal and Small-scale Gold Mining (ASGM) sites in Senegal by comparing a historical Sentinel-2 image from December 2015 with recent Sentinel-2 surface reflectance imagery. It uses true-color composites (B4, B3, B2) to visualize land surface changes over time, enabling the identification of mining-related land transformations. The output is an interactive split-panel visualization in Google Earth Engine, where the left panel shows the 2015 baseline an

- gold BAND_SELECT 位置: [{'seq': 9, 'prev': 'SPATIAL_FILTER', 'next': 'RASTER_LOAD'}]
- 下游消费者: （无——isolated）
- owner_ruling: ______（gold_inconsistent / alternative_workflow / clearly_necessary）

## k=28 — Task: Analyze NIR reflectance distribution

Task: Analyze NIR reflectance distribution
Compute and visualizes the histogram of digital numbers (DN) in the near-infrared band (B5) from top-of-atmosphere reflectance imagery of Landsat 8 over a specified region. It processes an image collection from February to March 2020, clips each image to the 'hometown' boundary, and generates a histogram chart showing the frequency distribution of DN values. The output is a UI chart displayed in the console with labeled axes and title, used for assessin

- gold BAND_SELECT 位置: [{'seq': 2, 'prev': 'RASTER_LOAD', 'next': 'TEMPORAL_FILTER'}]
- 下游消费者: （无——isolated）
- owner_ruling: ______（gold_inconsistent / alternative_workflow / clearly_necessary）

## k=30 — Task: Analyze AOD anomaly trend

Task: Analyze AOD anomaly trend
Calculate the relative anomaly of aerosol optical depth (AOD) for 2020 compared to a baseline period (2000–2019) using MODIS MCD19A2 data. It computes mean AOD for both periods, clips them to a region 'north8', then derives percentage change as (2020_mean - 2000-2019_mean) / 2000-2019_mean * 100. Outputs include three map layers: baseline AOD (2000–2019), 2020 AOD, and AOD anomaly, visualized with a color palette from black to red, and printed anomaly image metada

- gold BAND_SELECT 位置: [{'seq': 2, 'prev': 'RASTER_LOAD', 'next': 'AGGREGATION'}, {'seq': 5, 'prev': 'RASTER_LOAD', 'next': 'AGGREGATION'}]
- 下游消费者: （无——isolated）
- owner_ruling: ______（gold_inconsistent / alternative_workflow / clearly_necessary）

## k=52 — Task: Classify land cover types

Task: Classify land cover types
Classify land cover in a specified region using Sentinel-2 surface reflectance imagery from three seasonal periods in 2021. It computes median composites for winter (Jan–Apr), summer (May–Aug), and fall (Sep–Dec), then combines them into a multi-temporal stack. Training samples are extracted from labeled points to train a CART classifier, which is applied to generate a land cover classification map with three classes. the workflow outputs include the trained class

- gold BAND_SELECT 位置: [{'seq': 6, 'prev': 'ITERATIVE_APPLY', 'next': 'RASTER_LOAD'}, {'seq': 12, 'prev': 'ITERATIVE_APPLY', 'next': 'RASTER_LOAD'}, {'seq': 18, 'prev': 'ITERATIVE_APPLY', 'next': 'ATTRIBUTE_FILTER'}]
- 下游消费者: （无——isolated）
- owner_ruling: ______（gold_inconsistent / alternative_workflow / clearly_necessary）

## k=58 — Task: Analyze VV backscatter time series

Task: Analyze VV backscatter time series
Extract Sentinel-1 C-band VV polarization backscatter values over a specified geometry (AIM_ELFO) using ascending IW mode data from relative orbit 137. It generates a median-reduced time series chart of VV intensity by region, specifically plotting temporal variations in radar backscatter, and displays the region on the map centered for visual context.

- gold BAND_SELECT 位置: [{'seq': 3, 'prev': 'ATTRIBUTE_FILTER', 'next': 'ATTRIBUTE_FILTER'}]
- 下游消费者: （无——isolated）
- owner_ruling: ______（gold_inconsistent / alternative_workflow / clearly_necessary）

## k=63 — Task: Map rice cultivation periods

Task: Map rice cultivation periods
Analyze Sentinel-1 SAR imagery over West Godavari district, India, to monitor temporal patterns in VV and VH backscatter from December 2019 to November 2020. It generates monthly mean composites, masks edge pixels, and creates seasonal composites for Rabi (Jan–Mar) and Kharif (Jun–Aug) cropping seasons. The workflow includes visualizing time-series backscatter layers and composites, and overlays them with planting date polygons (DSR and TPR weeks) and a final r

- gold BAND_SELECT 位置: [{'seq': 5, 'prev': 'TEMPORAL_FILTER', 'next': None}]
- 下游消费者: （无——isolated）
- owner_ruling: ______（gold_inconsistent / alternative_workflow / clearly_necessary）

## k=93 — Task: Extract mean soil sand content

Task: Extract mean soil sand content
Extract the mean value of sand content from the SoilGrids dataset at six depth layers and exports the averaged raster for a specified geographic region.

- gold BAND_SELECT 位置: [{'seq': 2, 'prev': 'RASTER_LOAD', 'next': 'AGGREGATION'}]
- 下游消费者: （无——isolated）
- owner_ruling: ______（gold_inconsistent / alternative_workflow / clearly_necessary）

## k=100 — Task: Generate Landsat 8 surface reflectance RGB mosaics

Task: Generate Landsat 8 surface reflectance RGB mosaics
Generate daily-mosaic RGB composites from Landsat 8 Collection 2 Level 2 Surface Reflectance (SR) imagery over the Monterey County, CA region for a one-year period (2014–2015). It applies radiometric scaling to SR bands (SR_B4, SR_B3, SR_B2) using the official C2 L2 scale factor (0.0000275) and offset (−0.2), clips to both a bounding rectangle and the Monterey county FeatureCollection, creates one image per day via mosaic (retaining earlie

- gold BAND_SELECT 位置: [{'seq': 2, 'prev': 'RASTER_LOAD', 'next': 'TEMPORAL_FILTER'}]
- 下游消费者: （无——isolated）
- owner_ruling: ______（gold_inconsistent / alternative_workflow / clearly_necessary）

## k=101 — Task: Analyze NDVI time series

Task: Analyze NDVI time series
Analyze NDVI time series from Landsat surface reflectance data between 1999-12-01 and 2021-01-31 over a defined polygon, and compares it with MODIS MOD13Q1 NDVI annual data for 2020. It enables interactive charting of NDVI values at clicked locations by generating temporal profiles from both Landsat and MODIS collections.

- gold BAND_SELECT 位置: [{'seq': 6, 'prev': 'ATTRIBUTE_FILTER', 'next': 'RASTER_LOAD'}, {'seq': 11, 'prev': 'ATTRIBUTE_FILTER', 'next': 'RASTER_LOAD'}, {'seq': 16, 'prev': 'ATTRIBUTE_FILTER', 'next': 'RASTER_LOAD'}]
- 下游消费者: （无——isolated）
- owner_ruling: ______（gold_inconsistent / alternative_workflow / clearly_necessary）

## k=107 — Task: Estimate forest cover percentage

Task: Estimate forest cover percentage
Calculate the percentage of tree cover in the year 2000 for each municipal boundary using the UMD Hansen Global Forest Change dataset. It selects pixels with at least 25% tree canopy cover, applies a reduceRegion operation to sum these values within each municipality's geometry, and appends the resulting forest cover count as a property ('fc00') to each feature. The output is a FeatureCollection exported to Google Drive containing municipalities enriched wi

- gold BAND_SELECT 位置: [{'seq': 2, 'prev': 'RASTER_LOAD', 'next': 'AGGREGATION'}]
- 下游消费者: （无——isolated）
- owner_ruling: ______（gold_inconsistent / alternative_workflow / clearly_necessary）

## k=117 — Task: Monitor VV backscatter changes

Task: Monitor VV backscatter changes
Analyze temporal changes in Sentinel-1 C-band VV polarization backscatter over a point location in the Netherlands. It retrieves the first available IW mode, descending orbit, relative orbit 37, VV-polarized SAR image for each of three consecutive months (April, May, June 2018), composites them into an RGB stack, and displays the result on the map to visualize seasonal or land cover-related backscatter dynamics.

- gold BAND_SELECT 位置: [{'seq': 3, 'prev': 'ATTRIBUTE_FILTER', 'next': None}]
- 下游消费者: （无——isolated）
- owner_ruling: ______（gold_inconsistent / alternative_workflow / clearly_necessary）

## k=118 — Task: Classify land cover using GLCM texture features

Task: Classify land cover using GLCM texture features
Compute and integrates Gray-Level Co-occurrence Matrix (GLCM) texture features from NIR band of Landsat 8 TOA imagery into seasonal composites, then generates a full-year high-quality composite image for land cover classification. The output is a 24-band image combining original spectral bands and derived GLCM textures (e.g., ASM, CONTRAST, CORR) across four seasonal periods, masked and merged to optimize spatial coverage and quality, intende

- gold BAND_SELECT 位置: [{'seq': 6, 'prev': 'ITERATIVE_APPLY', 'next': None}]
- 下游消费者: （无——isolated）
- owner_ruling: ______（gold_inconsistent / alternative_workflow / clearly_necessary）

## k=141 — Task: Map burned areas from satellite fire data

Task: Map burned areas from satellite fire data
Map and quantifies burned areas or active fire detections in a specific region using multiple satellite-based fire datasets (FIRMS, FireCCI, MCD64A1, MOD14A1) for the year 2011. It processes each dataset by filtering dates, clipping to a study area, masking non-fire pixels, computing maximum fire occurrence per pixel, and summarizing burned pixel counts per geographic region (Delta). The outputs are visualized fire layers and exported CSV tables co

- gold BAND_SELECT 位置: [{'seq': 4, 'prev': 'TEMPORAL_FILTER', 'next': 'RASTER_LOAD'}, {'seq': 7, 'prev': 'TEMPORAL_FILTER', 'next': 'RASTER_LOAD'}, {'seq': 10, 'prev': 'TEMPORAL_FILTER', 'next': 'RASTER_LOAD'}, {'seq': 13, 'prev': 'TEMPORAL_FILTER', 'next': 'AGGREGATION'}]
- 下游消费者: （无——isolated）
- owner_ruling: ______（gold_inconsistent / alternative_workflow / clearly_necessary）

## k=178 — Task: Monitor dry-season NDVI trends

Task: Monitor dry-season NDVI trends
Compute and compares annual dry-season (April–September) NDVI composites for Kebumen Regency, Central Java, Indonesia, across 2020–2024 using Sentinel-2 SR imagery. It applies SCL-based cloud/shadow/snow masking, generates per-year median NDVI rasters, classifies NDVI into four vegetation health classes (1: bare/low, 2: sparse, 3: moderate, 4: dense), calculates mean NDVI per kecamatan (subdistrict) via reduceRegions, exports a merged FeatureCollection of all

- gold BAND_SELECT 位置: [{'seq': 5, 'prev': 'ATTRIBUTE_FILTER', 'next': 'ITERATIVE_APPLY'}]
- 下游消费者: （无——isolated）
- owner_ruling: ______（gold_inconsistent / alternative_workflow / clearly_necessary）

## k=182 — Task: Estimate Chl_a concentration

Task: Estimate Chl_a concentration
Estimate chlorophyll-a (Chl_a) concentration in the Pearl River Basin using Landsat 8 surface reflectance imagery from 2013 to 2022. It applies atmospheric correction and cloud masking via QA bands, computes NDVI, and derives Chl_a using a linear regression model based on NDVI. A time series of mean annual Chl_a values per region (OBJECTID) is generated and visualized as a scatter chart, with outputs including mapped Chl_a images and regional trend analysis.

- gold BAND_SELECT 位置: [{'seq': 6, 'prev': 'RASTER_LOAD', 'next': 'AGGREGATION'}]
- 下游消费者: （无——isolated）
- owner_ruling: ______（gold_inconsistent / alternative_workflow / clearly_necessary）

## k=185 — Task: Classify water and land areas

Task: Classify water and land areas
Classify land cover into three categories—water current, non-water land, and sandy areas—using a Random Forest classifier trained on spectral indices and Sentinel-2 surface reflectance data from 2022. The output is a classified image map and accuracy assessment including confusion matrix, overall accuracy, and Kappa coefficient.

- gold BAND_SELECT 位置: [{'seq': 9, 'prev': 'ATTRIBUTE_FILTER', 'next': 'AGGREGATION'}, {'seq': 15, 'prev': 'ATTRIBUTE_FILTER', 'next': 'AGGREGATION'}, {'seq': 18, 'prev': 'RASTER_LOAD', 'next': 'ATTRIBUTE_FILTER'}]
- 下游消费者: （无——isolated）
- owner_ruling: ______（gold_inconsistent / alternative_workflow / clearly_necessary）

## k=191 — Task: Identify water bodies using spectral indices

Task: Identify water bodies using spectral indices
Identify water bodies by computing NDVI, NDWI, and MNDWI from Landsat 8 TOA reflectance data for the year 2015, then applies a threshold-based classification to detect water using the condition: NDVI < 0, NDWI > 0, and MNDWI > 0.5.

- gold BAND_SELECT 位置: [{'seq': 5, 'prev': 'SPATIAL_FILTER', 'next': 'AGGREGATION'}]
- 下游消费者: （无——isolated）
- owner_ruling: ______（gold_inconsistent / alternative_workflow / clearly_necessary）

## k=197 — Task: Analyze NDVI vegetation

Task: Analyze NDVI vegetation
Calculate NDVI to assess vegetation conditions around a specified point using Sentinel-2A surface reflectance imagery from December 2018. It applies cloud masking via the QA60 band, filters images by low cloud percentage, computes the median composite, clips to an ROI (undefined in script), and visualizes NDVI with a custom color palette. Additionally, it loads and displays a false-color composite of Landsat 8 TOA reflectance from January 2014 clipped to another reg

- gold BAND_SELECT 位置: [{'seq': 3, 'prev': 'TEMPORAL_FILTER', 'next': 'ATTRIBUTE_FILTER'}]
- 下游消费者: （无——isolated）
- owner_ruling: ______（gold_inconsistent / alternative_workflow / clearly_necessary）

## k=198 — Task: Analyze Skardu snow cover

Task: Analyze Skardu snow cover
Analyze snow cover dynamics in the Skardu Sub-division of Pakistan using MODIS NDSI Snow Cover data from 2018 to 2020. It extracts the administrative boundary for Skardu, computes the mean NDSI over the period, clips the mean snow cover image to the region, and generates a time series chart of mean NDSI values per date. Outputs include a clipped mean NDSI raster map visualized with min=0 and max=100, displayed over the Skardu region, and a UI chart showing tempora

- gold BAND_SELECT 位置: [{'seq': 3, 'prev': 'RASTER_LOAD', 'next': 'AGGREGATION'}]
- 下游消费者: （无——isolated）
- owner_ruling: ______（gold_inconsistent / alternative_workflow / clearly_necessary）

## k=201 — Task: Classify land cover types

Task: Classify land cover types
Classify land cover types in the Arkavathy basin using Sentinel-2 surface reflectance imagery from 2019 to 2020. It uses ground control points (GCPs) split into training (60%) and validation (40%) sets based on a random column. A Random Forest classifier with 50 trees is trained on spectral bands from the median composite image, and the resulting model is applied to generate a land cover map. Accuracy is assessed using a confusion matrix and overall accuracy metri

- gold BAND_SELECT 位置: [{'seq': 9, 'prev': 'ATTRIBUTE_FILTER', 'next': 'AGGREGATION'}]
- 下游消费者: （无——isolated）
- owner_ruling: ______（gold_inconsistent / alternative_workflow / clearly_necessary）

## k=202 — Task: Generate VV backscatter layer stack

Task: Generate VV backscatter layer stack
Generate a dual-temporal median VV backscatter composite from Sentinel-1 SAR imagery over Subang. It filters IW-mode, VV-polarized, descending-orbit images into two date ranges (2020-01-08 to 2020-01-19 and 2020-01-20 to 2020-01-31), computes median composites for each period, combines them into a single image stack, scales by 100, converts to 16-bit integer, and exports the result to Google Drive. Edge pixels with values below -50 dB are masked out duri

- gold BAND_SELECT 位置: [{'seq': 3, 'prev': 'ATTRIBUTE_FILTER', 'next': 'ATTRIBUTE_FILTER'}]
- 下游消费者: （无——isolated）
- owner_ruling: ______（gold_inconsistent / alternative_workflow / clearly_necessary）

## k=246 — Task: Classify land cover in district

Task: Classify land cover in district
Classify land cover in Kanpur Nagar using Sentinel-2 imagery. It trains a Random Forest classifier on labeled regions from a feature collection (table3) using spectral bands from a median composite image (2019-01-01 to 2019-05-30). The trained model is then applied to monthly images of Kanpur Nagar for the years 2016 and 2019, producing classified land cover maps for each month. Outputs are exported as raster images to Google Drive, named by district, month,

- gold BAND_SELECT 位置: [{'seq': 7, 'prev': 'ITERATIVE_APPLY', 'next': 'CLASSIFICATION'}, {'seq': 17, 'prev': 'ITERATIVE_APPLY', 'next': None}]
- 下游消费者: （无——isolated）
- owner_ruling: ______（gold_inconsistent / alternative_workflow / clearly_necessary）

## k=280 — Task: Extract NDGI from Landsat imagery

Task: Extract NDGI from Landsat imagery
Calculate the Normalized Difference Greenness Index (NDGI) using surface reflectance data from Landsat 8 OLI sensor over a user-defined region of interest. It applies cloud, cloud shadow, and snow masking using the QA_PIXEL band, clips and scales the imagery to the ROI, computes NDGI via a custom spectral index formula involving GREEN, NIR, and RED bands, and exports the median composite image to Google Drive. The output includes the median NDGI image and 

- gold BAND_SELECT 位置: [{'seq': 10, 'prev': 'ATTRIBUTE_FILTER', 'next': 'ITERATIVE_APPLY'}]
- 下游消费者: （无——isolated）
- owner_ruling: ______（gold_inconsistent / alternative_workflow / clearly_necessary）

## k=293 — Task: Analyze vegetation and precipitation dynamics

Task: Analyze vegetation and precipitation dynamics
Analyze multi-temporal vegetation (NDVI/EVI), precipitation (CHIRPS), evapotranspiration (GLDAS), and elevation (SRTM) patterns within a defined perimeter, extracting pixel-level time-series data centered around a reference date for synthesis and export as a CSV. It generates gridded point samples to extract mean values of environmental variables for further analysis.

- gold BAND_SELECT 位置: [{'seq': 14, 'prev': 'RASTER_LOAD', 'next': 'RASTER_LOAD'}, {'seq': 16, 'prev': 'RASTER_LOAD', 'next': 'RASTER_LOAD'}]
- 下游消费者: （无——isolated）
- owner_ruling: ______（gold_inconsistent / alternative_workflow / clearly_necessary）

## k=314 — Task: Analyze elevation statistics and distribution

Task: Analyze elevation statistics and distribution
Calculate and compares statistical measures (mean, median, minimum, maximum, and first quartile) of elevation from two SRTM digital elevation models (30m and 90m resolution) within the Sergipe River Basin. It also generates masked images for pixels below the first quartile and visualizes elevation histograms and maps for both resolutions.

- gold BAND_SELECT 位置: [{'seq': 4, 'prev': 'RASTER_LOAD', 'next': 'RASTER_LOAD'}, {'seq': 6, 'prev': 'RASTER_LOAD', 'next': 'AGGREGATION'}]
- 下游消费者: （无——isolated）
- owner_ruling: ______（gold_inconsistent / alternative_workflow / clearly_necessary）

## k=316 — Task: Extract vegetation texture features

Task: Extract vegetation texture features
Compute NDVI and EVI vegetation indices from Landsat 8 TOA data, generates a greenest-pixel composite based on NDVI, calculates GLCM texture metrics from the composite, and performs zonal statistics to extract mean texture values at sample points in Fujian Province for 2018.

- gold BAND_SELECT 位置: [{'seq': 5, 'prev': 'ATTRIBUTE_FILTER', 'next': None}]
- 下游消费者: （无——isolated）
- owner_ruling: ______（gold_inconsistent / alternative_workflow / clearly_necessary）

## k=318 — Task: Map land surface reflectance

Task: Map land surface reflectance
Generate a median composite of surface reflectance from Landsat 8 imagery, masked for clouds and cloud shadows, clipped to a user-defined geometry, and visualized in true color (B4-B3-B2). The output is used for land surface analysis and exported to Google Drive.

- gold BAND_SELECT 位置: [{'seq': 6, 'prev': 'ITERATIVE_APPLY', 'next': 'AGGREGATION'}]
- 下游消费者: （无——isolated）
- owner_ruling: ______（gold_inconsistent / alternative_workflow / clearly_necessary）

## k=320 — Task: Classify land cover types

Task: Classify land cover types
Classify land cover in Cagayan using Sentinel-1 SAR and Sentinel-2 optical imagery from November 11–14, 2020. It first separates water (sea and inland) using VV/VH backscatter thresholds and NDWI/MNDWI indices, then distinguishes vegetation, agriculture, forests, built-up areas, and bare land using a combination of spectral indices (EVI, MSAVI, GNDVI, LAI, newBUI) and threshold-based masking. Outputs include classified rasters for water, forest, agriculture, bare 

- gold BAND_SELECT 位置: [{'seq': 3, 'prev': 'ATTRIBUTE_FILTER', 'next': 'SPATIAL_FILTER'}, {'seq': 9, 'prev': 'ATTRIBUTE_FILTER', 'next': 'SPATIAL_FILTER'}]
- 下游消费者: （无——isolated）
- owner_ruling: ______（gold_inconsistent / alternative_workflow / clearly_necessary）

## k=336 — Task: Compute NDVI for vegetation analysis

Task: Compute NDVI for vegetation analysis
Compute Normalized Difference Vegetation Index (NDVI) from Landsat 7 Surface Reflectance imagery over a 20 km radius around a point near El Paso, Texas, for the year 2020. It applies cloud masking using pixel_qa bits and filters images with less than 10% cloud cover. The workflow includes clipping to the study area, selecting red (B4) and near-infrared (B5) bands, calculating NDVI, and preserving image timestamps. The output is a median-reduced NDVI ima

- gold BAND_SELECT 位置: [{'seq': 8, 'prev': 'TEMPORAL_FILTER', 'next': 'ATTRIBUTE_FILTER'}]
- 下游消费者: （无——isolated）
- owner_ruling: ______（gold_inconsistent / alternative_workflow / clearly_necessary）

## k=338 — Task: Analyze monthly precipitation patterns

Task: Analyze monthly precipitation patterns
Calculate monthly average precipitation for the year 2016 over Porto Velho municipality using TRMM 3B42 data. It processes each month separately by filtering the image collection to monthly date ranges, computes the mean precipitation, clips results to the municipal boundary, and visualizes monthly layers on the map. Upon user click, it generates a time series chart of precipitation values at the clicked point across all 12 months, enabling localized 

- gold BAND_SELECT 位置: [{'seq': 2, 'prev': 'RASTER_LOAD', 'next': 'TEMPORAL_FILTER'}, {'seq': 5, 'prev': 'RASTER_LOAD', 'next': 'TEMPORAL_FILTER'}, {'seq': 8, 'prev': 'RASTER_LOAD', 'next': 'TEMPORAL_FILTER'}, {'seq': 11, 'prev': 'RASTER_LOAD', 'next': 'TEMPORAL_FILTER'}, {'seq': 14, 'prev': 'RASTER_LOAD', 'next': 'TEMPORAL_FILTER'}, {'seq': 17, 'prev': 'RASTER_LOAD', 'next': 'TEMPORAL_FILTER'}, {'seq': 20, 'prev': 'RASTER_LOAD', 'next': 'TEMPORAL_FILTER'}, {'seq': 23, 'prev': 'RASTER_LOAD', 'next': 'TEMPORAL_FILTER'}, {'seq': 26, 'prev': 'RASTER_LOAD', 'next': 'TEMPORAL_FILTER'}, {'seq': 29, 'prev': 'RASTER_LOAD', 'next': 'TEMPORAL_FILTER'}, {'seq': 32, 'prev': 'RASTER_LOAD', 'next': 'TEMPORAL_FILTER'}, {'seq': 35, 'prev': 'RASTER_LOAD', 'next': 'TEMPORAL_FILTER'}]
- 下游消费者: （无——isolated）
- owner_ruling: ______（gold_inconsistent / alternative_workflow / clearly_necessary）

## k=340 — Task: Classify vegetation types using Sentinel-2 and SAR

Task: Classify vegetation types using Sentinel-2 and SAR
the workflow performs land cover classification to distinguish forests, grasslands, and shrublands in the Fo Tan area of Hong Kong using a Random Forest classifier trained on Sentinel-1 and Sentinel-2 fused imagery. It outputs classified maps, accuracy assessments, and training/validation sample points.

- gold BAND_SELECT 位置: [{'seq': 3, 'prev': 'RASTER_LOAD', 'next': 'AGGREGATION'}]
- 下游消费者: （无——isolated）
- owner_ruling: ______（gold_inconsistent / alternative_workflow / clearly_necessary）

## k=346 — Task: Analyze land surface temperature

Task: Analyze land surface temperature
Calculate and visualizes nighttime and daytime land surface temperature (LST) for Turkey using MODIS data from 1990, 2000, 2006, 2012, and 2018. It converts digital values to Celsius, clips to the country boundary, computes mean temperatures over the region, and exports the 2006 winter nighttime LST mean as a GeoTIFF.

- gold BAND_SELECT 位置: [{'seq': 3, 'prev': 'ITERATIVE_APPLY', 'next': 'RASTER_LOAD'}, {'seq': 6, 'prev': 'ITERATIVE_APPLY', 'next': 'RASTER_LOAD'}, {'seq': 9, 'prev': 'ITERATIVE_APPLY', 'next': 'RASTER_LOAD'}, {'seq': 12, 'prev': 'ITERATIVE_APPLY', 'next': 'RASTER_LOAD'}, {'seq': 15, 'prev': 'ITERATIVE_APPLY', 'next': 'AGGREGATION'}, {'seq': 19, 'prev': 'ITERATIVE_APPLY', 'next': 'RASTER_LOAD'}, {'seq': 22, 'prev': 'ITERATIVE_APPLY', 'next': 'RASTER_LOAD'}, {'seq': 25, 'prev': 'ITERATIVE_APPLY', 'next': 'RASTER_LOAD'}, {'seq': 28, 'prev': 'ITERATIVE_APPLY', 'next': 'AGGREGATION'}, {'seq': 32, 'prev': 'ITERATIVE_APPLY', 'next': 'RASTER_LOAD'}, {'seq': 35, 'prev': 'ITERATIVE_APPLY', 'next': 'RASTER_LOAD'}, {'seq': 38, 'prev': 'ITERATIVE_APPLY', 'next': 'RASTER_LOAD'}, {'seq': 41, 'prev': 'ITERATIVE_APPLY', 'next': 'AGGREGATION'}, {'seq': 45, 'prev': 'ITERATIVE_APPLY', 'next': 'RASTER_LOAD'}, {'seq': 48, 'prev': 'ITERATIVE_APPLY', 'next': 'RASTER_LOAD'}, {'seq': 51, 'prev': 'ITERATIVE_APPLY', 'next': 'RASTER_LOAD'}, {'seq': 54, 'prev': 'ITERATIVE_APPLY', 'next': 'AGGREGATION'}]
- 下游消费者: （无——isolated）
- owner_ruling: ______（gold_inconsistent / alternative_workflow / clearly_necessary）

## k=370 — Task: Identify perennial water bodies

Task: Identify perennial water bodies
Calculate the frequency of water occurrence in a fixed region (34°N–36°N, 114°E–119°E) using Landsat 5, 7, and 8 surface reflectance data from 1984 to 2021. It computes multiple vegetation and water indices (NDVI, EVI, LSWI, mNDWI), applies a water detection rule based on mNDWI > EVI or NDVI and low EVI, and aggregates annual water observations. The output is a binary map indicating areas with ≥75% water frequency over each year, exported annually as 'imgPer

- gold BAND_SELECT 位置: [{'seq': 7, 'prev': 'ITERATIVE_APPLY', 'next': 'RASTER_LOAD'}, {'seq': 13, 'prev': 'ITERATIVE_APPLY', 'next': 'RASTER_LOAD'}, {'seq': 19, 'prev': 'ITERATIVE_APPLY', 'next': 'AGGREGATION'}, {'seq': 26, 'prev': 'ITERATIVE_APPLY', 'next': 'RASTER_LOAD'}, {'seq': 32, 'prev': 'ITERATIVE_APPLY', 'next': 'RASTER_LOAD'}, {'seq': 38, 'prev': 'ITERATIVE_APPLY', 'next': 'AGGREGATION'}, {'seq': 45, 'prev': 'ITERATIVE_APPLY', 'next': 'RASTER_LOAD'}, {'seq': 51, 'prev': 'ITERATIVE_APPLY', 'next': 'RASTER_LOAD'}, {'seq': 57, 'prev': 'ITERATIVE_APPLY', 'next': 'AGGREGATION'}, {'seq': 64, 'prev': 'ITERATIVE_APPLY', 'next': 'RASTER_LOAD'}, {'seq': 70, 'prev': 'ITERATIVE_APPLY', 'next': 'RASTER_LOAD'}, {'seq': 76, 'prev': 'ITERATIVE_APPLY', 'next': 'AGGREGATION'}, {'seq': 83, 'prev': 'ITERATIVE_APPLY', 'next': 'RASTER_LOAD'}, {'seq': 89, 'prev': 'ITERATIVE_APPLY', 'next': 'RASTER_LOAD'}, {'seq': 95, 'prev': 'ITERATIVE_APPLY', 'next': 'AGGREGATION'}, {'seq': 102, 'prev': 'ITERATIVE_APPLY', 'next': 'RASTER_LOAD'}, {'seq': 108, 'prev': 'ITERATIVE_APPLY', 'next': 'RASTER_LOAD'}, {'seq': 114, 'prev': 'ITERATIVE_APPLY', 'next': 'AGGREGATION'}, {'seq': 121, 'prev': 'ITERATIVE_APPLY', 'next': 'RASTER_LOAD'}, {'seq': 127, 'prev': 'ITERATIVE_APPLY', 'next': 'RASTER_LOAD'}, {'seq': 133, 'prev': 'ITERATIVE_APPLY', 'next': 'AGGREGATION'}, {'seq': 140, 'prev': 'ITERATIVE_APPLY', 'next': 'RASTER_LOAD'}, {'seq': 146, 'prev': 'ITERATIVE_APPLY', 'next': 'RASTER_LOAD'}, {'seq': 152, 'prev': 'ITERATIVE_APPLY', 'next': 'AGGREGATION'}, {'seq': 159, 'prev': 'ITERATIVE_APPLY', 'next': 'RASTER_LOAD'}, {'seq': 165, 'prev': 'ITERATIVE_APPLY', 'next': 'RASTER_LOAD'}, {'seq': 171, 'prev': 'ITERATIVE_APPLY', 'next': 'AGGREGATION'}, {'seq': 178, 'prev': 'ITERATIVE_APPLY', 'next': 'RASTER_LOAD'}, {'seq': 184, 'prev': 'ITERATIVE_APPLY', 'next': 'RASTER_LOAD'}, {'seq': 190, 'prev': 'ITERATIVE_APPLY', 'next': 'AGGREGATION'}, {'seq': 197, 'prev': 'ITERATIVE_APPLY', 'next': 'RASTER_LOAD'}, {'seq': 203, 'prev': 'ITERATIVE_APPLY', 'next': 'RASTER_LOAD'}, {'seq': 209, 'prev': 'ITERATIVE_APPLY', 'next': 'AGGREGATION'}, {'seq': 216, 'prev': 'ITERATIVE_APPLY', 'next': 'RASTER_LOAD'}, {'seq': 222, 'prev': 'ITERATIVE_APPLY', 'next': 'RASTER_LOAD'}, {'seq': 228, 'prev': 'ITERATIVE_APPLY', 'next': 'AGGREGATION'}, {'seq': 235, 'prev': 'ITERATIVE_APPLY', 'next': 'RASTER_LOAD'}, {'seq': 241, 'prev': 'ITERATIVE_APPLY', 'next': 'RASTER_LOAD'}, {'seq': 247, 'prev': 'ITERATIVE_APPLY', 'next': 'AGGREGATION'}, {'seq': 254, 'prev': 'ITERATIVE_APPLY', 'next': 'RASTER_LOAD'}, {'seq': 260, 'prev': 'ITERATIVE_APPLY', 'next': 'RASTER_LOAD'}, {'seq': 266, 'prev': 'ITERATIVE_APPLY', 'next': 'AGGREGATION'}, {'seq': 273, 'prev': 'ITERATIVE_APPLY', 'next': 'RASTER_LOAD'}, {'seq': 279, 'prev': 'ITERATIVE_APPLY', 'next': 'RASTER_LOAD'}, {'seq': 285, 'prev': 'ITERATIVE_APPLY', 'next': 'AGGREGATION'}, {'seq': 292, 'prev': 'ITERATIVE_APPLY', 'next': 'RASTER_LOAD'}, {'seq': 298, 'prev': 'ITERATIVE_APPLY', 'next': 'RASTER_LOAD'}, {'seq': 304, 'prev': 'ITERATIVE_APPLY', 'next': 'AGGREGATION'}, {'seq': 311, 'prev': 'ITERATIVE_APPLY', 'next': 'RASTER_LOAD'}, {'seq': 317, 'prev': 'ITERATIVE_APPLY', 'next': 'RASTER_LOAD'}, {'seq': 323, 'prev': 'ITERATIVE_APPLY', 'next': 'AGGREGATION'}, {'seq': 330, 'prev': 'ITERATIVE_APPLY', 'next': 'RASTER_LOAD'}, {'seq': 336, 'prev': 'ITERATIVE_APPLY', 'next': 'RASTER_LOAD'}, {'seq': 342, 'prev': 'ITERATIVE_APPLY', 'next': 'AGGREGATION'}, {'seq': 349, 'prev': 'ITERATIVE_APPLY', 'next': 'RASTER_LOAD'}, {'seq': 355, 'prev': 'ITERATIVE_APPLY', 'next': 'RASTER_LOAD'}, {'seq': 361, 'prev': 'ITERATIVE_APPLY', 'next': 'AGGREGATION'}, {'seq': 368, 'prev': 'ITERATIVE_APPLY', 'next': 'RASTER_LOAD'}, {'seq': 374, 'prev': 'ITERATIVE_APPLY', 'next': 'RASTER_LOAD'}, {'seq': 380, 'prev': 'ITERATIVE_APPLY', 'next': 'AGGREGATION'}, {'seq': 387, 'prev': 'ITERATIVE_APPLY', 'next': 'RASTER_LOAD'}, {'seq': 393, 'prev': 'ITERATIVE_APPLY', 'next': 'RASTER_LOAD'}, {'seq': 399, 'prev': 'ITERATIVE_APPLY', 'next': 'AGGREGATION'}, {'seq': 406, 'prev': 'ITERATIVE_APPLY', 'next': 'RASTER_LOAD'}, {'seq': 412, 'prev': 'ITERATIVE_APPLY', 'next': 'RASTER_LOAD'}, {'seq': 418, 'prev': 'ITERATIVE_APPLY', 'next': 'AGGREGATION'}, {'seq': 425, 'prev': 'ITERATIVE_APPLY', 'next': 'RASTER_LOAD'}, {'seq': 431, 'prev': 'ITERATIVE_APPLY', 'next': 'RASTER_LOAD'}, {'seq': 437, 'prev': 'ITERATIVE_APPLY', 'next': 'AGGREGATION'}, {'seq': 444, 'prev': 'ITERATIVE_APPLY', 'next': 'RASTER_LOAD'}, {'seq': 450, 'prev': 'ITERATIVE_APPLY', 'next': 'RASTER_LOAD'}, {'seq': 456, 'prev': 'ITERATIVE_APPLY', 'next': 'AGGREGATION'}, {'seq': 463, 'prev': 'ITERATIVE_APPLY', 'next': 'RASTER_LOAD'}, {'seq': 469, 'prev': 'ITERATIVE_APPLY', 'next': 'RASTER_LOAD'}, {'seq': 475, 'prev': 'ITERATIVE_APPLY', 'next': 'AGGREGATION'}, {'seq': 482, 'prev': 'ITERATIVE_APPLY', 'next': 'RASTER_LOAD'}, {'seq': 488, 'prev': 'ITERATIVE_APPLY', 'next': 'RASTER_LOAD'}, {'seq': 494, 'prev': 'ITERATIVE_APPLY', 'next': 'AGGREGATION'}, {'seq': 501, 'prev': 'ITERATIVE_APPLY', 'next': 'RASTER_LOAD'}, {'seq': 507, 'prev': 'ITERATIVE_APPLY', 'next': 'RASTER_LOAD'}, {'seq': 513, 'prev': 'ITERATIVE_APPLY', 'next': 'AGGREGATION'}, {'seq': 520, 'prev': 'ITERATIVE_APPLY', 'next': 'RASTER_LOAD'}, {'seq': 526, 'prev': 'ITERATIVE_APPLY', 'next': 'RASTER_LOAD'}, {'seq': 532, 'prev': 'ITERATIVE_APPLY', 'next': 'AGGREGATION'}, {'seq': 539, 'prev': 'ITERATIVE_APPLY', 'next': 'RASTER_LOAD'}, {'seq': 545, 'prev': 'ITERATIVE_APPLY', 'next': 'RASTER_LOAD'}, {'seq': 551, 'prev': 'ITERATIVE_APPLY', 'next': 'AGGREGATION'}, {'seq': 558, 'prev': 'ITERATIVE_APPLY', 'next': 'RASTER_LOAD'}, {'seq': 564, 'prev': 'ITERATIVE_APPLY', 'next': 'RASTER_LOAD'}, {'seq': 570, 'prev': 'ITERATIVE_APPLY', 'next': 'AGGREGATION'}, {'seq': 577, 'prev': 'ITERATIVE_APPLY', 'next': 'RASTER_LOAD'}, {'seq': 583, 'prev': 'ITERATIVE_APPLY', 'next': 'RASTER_LOAD'}, {'seq': 589, 'prev': 'ITERATIVE_APPLY', 'next': 'AGGREGATION'}, {'seq': 596, 'prev': 'ITERATIVE_APPLY', 'next': 'RASTER_LOAD'}, {'seq': 602, 'prev': 'ITERATIVE_APPLY', 'next': 'RASTER_LOAD'}, {'seq': 608, 'prev': 'ITERATIVE_APPLY', 'next': 'AGGREGATION'}, {'seq': 615, 'prev': 'ITERATIVE_APPLY', 'next': 'RASTER_LOAD'}, {'seq': 621, 'prev': 'ITERATIVE_APPLY', 'next': 'RASTER_LOAD'}, {'seq': 627, 'prev': 'ITERATIVE_APPLY', 'next': 'AGGREGATION'}, {'seq': 634, 'prev': 'ITERATIVE_APPLY', 'next': 'RASTER_LOAD'}, {'seq': 640, 'prev': 'ITERATIVE_APPLY', 'next': 'RASTER_LOAD'}, {'seq': 646, 'prev': 'ITERATIVE_APPLY', 'next': 'AGGREGATION'}, {'seq': 653, 'prev': 'ITERATIVE_APPLY', 'next': 'RASTER_LOAD'}, {'seq': 659, 'prev': 'ITERATIVE_APPLY', 'next': 'RASTER_LOAD'}, {'seq': 665, 'prev': 'ITERATIVE_APPLY', 'next': 'AGGREGATION'}, {'seq': 672, 'prev': 'ITERATIVE_APPLY', 'next': 'RASTER_LOAD'}, {'seq': 678, 'prev': 'ITERATIVE_APPLY', 'next': 'RASTER_LOAD'}, {'seq': 684, 'prev': 'ITERATIVE_APPLY', 'next': 'AGGREGATION'}, {'seq': 691, 'prev': 'ITERATIVE_APPLY', 'next': 'RASTER_LOAD'}, {'seq': 697, 'prev': 'ITERATIVE_APPLY', 'next': 'RASTER_LOAD'}, {'seq': 703, 'prev': 'ITERATIVE_APPLY', 'next': 'AGGREGATION'}, {'seq': 710, 'prev': 'ITERATIVE_APPLY', 'next': 'RASTER_LOAD'}, {'seq': 716, 'prev': 'ITERATIVE_APPLY', 'next': 'RASTER_LOAD'}, {'seq': 722, 'prev': 'ITERATIVE_APPLY', 'next': 'VECTOR_LOAD'}]
- 下游消费者: （无——isolated）
- owner_ruling: ______（gold_inconsistent / alternative_workflow / clearly_necessary）

## k=406 — Task: Extract maximum LAI value

Task: Extract maximum LAI value
Calculate the maximum Leaf Area Index (LAI) from MODIS MOD15A2H collection during January 2020, applies a scaling factor, masks values above 10, clips to the region of interest, and visualizes the result. It outputs a single-band raster representing the maximum LAI over the study area with masking applied for values exceeding 10, intended for vegetation density analysis.

- gold BAND_SELECT 位置: [{'seq': 5, 'prev': 'ATTRIBUTE_FILTER', 'next': None}]
- 下游消费者: （无——isolated）
- owner_ruling: ______（gold_inconsistent / alternative_workflow / clearly_necessary）

## k=413 — Task: Extract daily precipitation data

Task: Extract daily precipitation data
Extract and clips daily precipitation data from the CHIRPS dataset for a user-defined region of interest between January 1, 2018, and January 5, 2018, then exports each image in the collection to Google Drive.

- gold BAND_SELECT 位置: [{'seq': 4, 'prev': 'ATTRIBUTE_FILTER', 'next': 'AGGREGATION'}]
- 下游消费者: （无——isolated）
- owner_ruling: ______（gold_inconsistent / alternative_workflow / clearly_necessary）

## k=423 — Task: Extract FAPAR values for sites

Task: Extract FAPAR values for sites
Extract Fraction of Absorbed Photosynthetically Active Radiation (FAPAR) values from MODIS MCD15A3H data for specific geographic sites in Ecuador between 2003 and 2021, computes mean FAPAR per site over time, and exports the results to Google Drive with associated dates.

- gold BAND_SELECT 位置: [{'seq': 3, 'prev': 'TEMPORAL_FILTER', 'next': 'AGGREGATION'}]
- 下游消费者: （无——isolated）
- owner_ruling: ______（gold_inconsistent / alternative_workflow / clearly_necessary）

## k=425 — Task: Count good observations by time window

Task: Count good observations by time window
the workflow counts the number of valid (good quality) optical satellite observations across seven monthly time windows in 2022 over Hainan Island. It processes Landsat 7, Landsat 8, and Sentinel-2 surface reflectance data, applying sensor-specific cloud and shadow masking using QA bands and terrain-based shadow detection. For each time window, it merges observations from all sensors, sums them into a single band indicating observation frequency, clip

- gold BAND_SELECT 位置: [{'seq': 5, 'prev': 'COLLECTION_MGMT', 'next': 'ITERATIVE_APPLY'}, {'seq': 7, 'prev': 'ITERATIVE_APPLY', 'next': 'RASTER_LOAD'}, {'seq': 12, 'prev': 'COLLECTION_MGMT', 'next': 'ITERATIVE_APPLY'}, {'seq': 14, 'prev': 'ITERATIVE_APPLY', 'next': 'RASTER_LOAD'}, {'seq': 19, 'prev': 'COLLECTION_MGMT', 'next': 'ITERATIVE_APPLY'}, {'seq': 21, 'prev': 'ITERATIVE_APPLY', 'next': 'RASTER_LOAD'}]
- 下游消费者: （无——isolated）
- owner_ruling: ______（gold_inconsistent / alternative_workflow / clearly_necessary）

## k=434 — Task: Analyze NDVI for riparian forest

Task: Analyze NDVI for riparian forest
Analyze NDVI time series for riparian forests using MODIS MOD13Q1 imagery from 2004 to 2006. It applies QA filtering by masking non-zero SummaryQA values, scales NDVI by dividing by 10,000, clips images to a user-defined riparian forest geometry, merges collections from two hydrological years (2004–2005 and 2005–2006), and generates a scatter chart of mean annual NDVI by day of year. Outputs include filtered and scaled NDVI image collections and a multi-yea

- gold BAND_SELECT 位置: [{'seq': 2, 'prev': 'RASTER_LOAD', 'next': 'TEMPORAL_FILTER'}, {'seq': 5, 'prev': 'RASTER_LOAD', 'next': 'TEMPORAL_FILTER'}]
- 下游消费者: （无——isolated）
- owner_ruling: ______（gold_inconsistent / alternative_workflow / clearly_necessary）

## k=439 — Task: Detect land cover change

Task: Detect land cover change
Detect land cover change between 2001 and 2020 using MODIS MCD12Q1 annual land cover type (LC_Type1) products over a user-defined rectangular ROI. It computes a binary change map (0 = no change, 1 = class transition), visualizes it with red/white coloring, prints min/max statistics and total changed area in km² (derived via pixelArea multiplication and summation), and exports a scaled (0–255), cloud-optimized GeoTIFF of the change raster at 30 m resolution to Googl

- gold BAND_SELECT 位置: [{'seq': 2, 'prev': 'RASTER_LOAD', 'next': 'RASTER_LOAD'}, {'seq': 4, 'prev': 'RASTER_LOAD', 'next': 'AGGREGATION'}]
- 下游消费者: （无——isolated）
- owner_ruling: ______（gold_inconsistent / alternative_workflow / clearly_necessary）

## k=442 — Task: Estimate urban heat island intensity

Task: Estimate urban heat island intensity
Estimate Urban Heat Island (UHI) intensity by comparing land surface temperature (LST) between urban and non-urban areas using MODIS LST data from 2017. It first masks MODIS land cover data to separate urban (LC_Type1 = 13) and non-urban regions, applies these masks to MOD11A1 LST data, computes mean LST for each region over time, calculates the difference (UHI = urban LST - non-urban LST), and outputs a UHI image collection, time series chart, and poin

- gold BAND_SELECT 位置: [{'seq': 3, 'prev': 'TEMPORAL_FILTER', 'next': 'ITERATIVE_APPLY'}, {'seq': 7, 'prev': 'TEMPORAL_FILTER', 'next': 'ITERATIVE_APPLY'}, {'seq': 19, 'prev': 'AGGREGATION', 'next': 'RASTER_LOAD'}]
- 下游消费者: （无——isolated）
- owner_ruling: ______（gold_inconsistent / alternative_workflow / clearly_necessary）

## k=447 — Task: Extract monthly EVI maxima

Task: Extract monthly EVI maxima
Compute the monthly maximum Enhanced Vegetation Index (EVI) from MODIS MOD13Q1 data for the year 2021 over a user-defined region. It processes the EVI time series by filtering, scaling, clipping, and computing monthly maximum composites using image collection reduction methods. The output includes a time series chart of monthly maximum EVI values, a mean annual EVI map, and individual GeoTIFF exports of each month's maximum EVI image. Additionally, it calculates 

- gold BAND_SELECT 位置: [{'seq': 4, 'prev': 'ATTRIBUTE_FILTER', 'next': 'TEMPORAL_FILTER'}]
- 下游消费者: （无——isolated）
- owner_ruling: ______（gold_inconsistent / alternative_workflow / clearly_necessary）

## k=454 — Task: Detect landslide-affected areas using SAR amplitude change

Task: Detect landslide-affected areas using SAR amplitude change
Detect landslide-affected areas by analyzing pre- and post-event Sentinel-1 SAR amplitude changes. It computes the difference in median VH backscatter between ascending and descending orbits before and after an event, applies slope and curvature masking from SRTM data to focus on steep, convex terrain, and generates a masked amplitude change layer. Outputs include visualizations of pre/post-event amplitude stacks, amplitude ratios,

- gold BAND_SELECT 位置: [{'seq': 9, 'prev': 'ATTRIBUTE_FILTER', 'next': 'SPATIAL_FILTER'}]
- 下游消费者: （无——isolated）
- owner_ruling: ______（gold_inconsistent / alternative_workflow / clearly_necessary）

## k=456 — Task: Cluster vegetation patterns

Task: Cluster vegetation patterns
the workflow clusters vegetation patterns in the Chaco region using MODIS NDVI time series from August 2015 to July 2016, applying unsupervised k-means classification on masked multiband imagery, and visualizes the resulting land cover clusters.

- gold BAND_SELECT 位置: [{'seq': 4, 'prev': 'RASTER_LOAD', 'next': 'CLASSIFICATION'}]
- 下游消费者: （无——isolated）
- owner_ruling: ______（gold_inconsistent / alternative_workflow / clearly_necessary）

## k=457 — Task: Detect land cover change

Task: Detect land cover change
Detect land surface changes between 2016 and 2018 using Landsat 8 Surface Reflectance imagery over a user-defined study area. It computes NBR (Normalized Burn Ratio) from pre- and post-period median composites, calculates dNBR (difference in NBR), and applies a threshold-based change detection (gte 100) to identify significant changes. Outputs include early and late image visualizations, NBR layers for both periods, the dNBR layer, and a binary change detection map

- gold BAND_SELECT 位置: [{'seq': 5, 'prev': 'ITERATIVE_APPLY', 'next': 'RASTER_LOAD'}, {'seq': 10, 'prev': 'ITERATIVE_APPLY', 'next': None}]
- 下游消费者: （无——isolated）
- owner_ruling: ______（gold_inconsistent / alternative_workflow / clearly_necessary）

## k=470 — Task: Analyze multi-temporal backscatter

Task: Analyze multi-temporal backscatter
Compute mean VV-polarized backscatter from Sentinel-1 SAR imagery for three time periods (2018, 2020, 2022) during the August–December season. It masks out pixels with values below -30 dB to remove noise or invalid data, then combines the three temporal means into a single three-band image representing temporal changes in radar backscatter. The output is a composite raster visualized with a fixed stretch (min: -15, max: 5) and added to the map as 'MultiTe

- gold BAND_SELECT 位置: [{'seq': 3, 'prev': 'ATTRIBUTE_FILTER', 'next': None}]
- 下游消费者: （无——isolated）
- owner_ruling: ______（gold_inconsistent / alternative_workflow / clearly_necessary）

## k=471 — Task: Classify land cover types

Task: Classify land cover types
Classify land cover types in Pune using multi-temporal Sentinel-2 imagery. It selects blue, green, red, and near-infrared bands (B2, B3, B4, B8), stacks multiple images over time into a single composite, clips to the study area, and trains a Random Forest classifier using labeled polygons for classes including water, bareland, built-up, tree cover, agriculture, orchards, and grassland. The output is a classified raster map displayed with a custom color palette rep

- gold BAND_SELECT 位置: [{'seq': 2, 'prev': 'RASTER_LOAD', 'next': 'RASTER_LOAD'}, {'seq': 4, 'prev': 'RASTER_LOAD', 'next': 'RASTER_LOAD'}, {'seq': 6, 'prev': 'RASTER_LOAD', 'next': 'RASTER_LOAD'}]
- 下游消费者: （无——isolated）
- owner_ruling: ______（gold_inconsistent / alternative_workflow / clearly_necessary）

## k=495 — Task: Identify surface water using spectral indices

Task: Identify surface water using spectral indices
Identify surface water by computing NDVI, NDWI, and MNDWI from a median Landsat 8 TOA reflectance image for the year 2015, then applying a threshold-based classification to detect water bodies based on spectral characteristics.

- gold BAND_SELECT 位置: [{'seq': 5, 'prev': 'SPATIAL_FILTER', 'next': 'AGGREGATION'}]
- 下游消费者: （无——isolated）
- owner_ruling: ______（gold_inconsistent / alternative_workflow / clearly_necessary）

## k=500 — Task: Identify surface water extent

Task: Identify surface water extent
Identify surface water extent in the Claro River basin using MNDWI derived from Landsat 5 TOA reflectance data from July 1987. It applies a threshold-based mask (MNDWI >= 0.4) combined with slope filtering (slope < 3 degrees) from SRTM to reduce false positives on steep terrain. The output is a binary water mask and the original composite image, both clipped to the study area and exported to Google Drive for further analysis.

- gold BAND_SELECT 位置: [{'seq': 2, 'prev': 'RASTER_LOAD', 'next': 'TEMPORAL_FILTER'}]
- 下游消费者: （无——isolated）
- owner_ruling: ______（gold_inconsistent / alternative_workflow / clearly_necessary）

## k=504 — Task: Calculate water balance from climate data

Task: Calculate water balance from climate data
Calculate monthly water balance using precipitation, actual evapotranspiration, and runoff from TerraClimate data over the Kahayan-Sebangau Watershed (KHG) between 2010 and 2020. It outputs time-series charts of evapotranspiration, precipitation, runoff, and water balance, and visualizes the water balance for a selected date.

- gold BAND_SELECT 位置: [{'seq': 2, 'prev': 'RASTER_LOAD', 'next': 'TEMPORAL_FILTER'}, {'seq': 6, 'prev': 'RASTER_LOAD', 'next': 'TEMPORAL_FILTER'}, {'seq': 10, 'prev': 'RASTER_LOAD', 'next': 'TEMPORAL_FILTER'}]
- 下游消费者: （无——isolated）
- owner_ruling: ______（gold_inconsistent / alternative_workflow / clearly_necessary）

## k=518 — Task: Analyze vegetation and water indices

Task: Analyze vegetation and water indices
Generate a median, minimum, and maximum composite from Sentinel-2 surface reflectance data over a specified region and time period, then computes NDVI and NDWI indices from the median composite to assess vegetation and surface water conditions. It visualizes these composites and indices on the map and prints relevant images for inspection.

- gold BAND_SELECT 位置: [{'seq': 5, 'prev': 'ATTRIBUTE_FILTER', 'next': 'AGGREGATION'}]
- 下游消费者: （无——isolated）
- owner_ruling: ______（gold_inconsistent / alternative_workflow / clearly_necessary）

## k=520 — Task: Analyze NDVI and EVI vegetation indices

Task: Analyze NDVI and EVI vegetation indices
Analyze vegetation conditions in Argentina's endemic region using MODIS-derived NDVI and EVI indices from both MYD13A1 and MOD13A1 products for a specific time period in 2012. It processes and visualizes the vegetation indices over the defined Region_Endemica, clips them to this area, applies scaling, and exports mean NDVI and EVI images for both sensors to Google Drive as GeoTIFFs.

- gold BAND_SELECT 位置: [{'seq': 5, 'prev': 'TEMPORAL_FILTER', 'next': 'RASTER_LOAD'}, {'seq': 9, 'prev': 'TEMPORAL_FILTER', 'next': None}]
- 下游消费者: （无——isolated）
- owner_ruling: ______（gold_inconsistent / alternative_workflow / clearly_necessary）

## k=525 — Task: Identify water bodies using SAR and optical indices

Task: Identify water bodies using SAR and optical indices
Identify water bodies by analyzing Sentinel-1 VV and VH backscatter values (using thresholds of -13 dB and -19 dB, respectively) and combines this with optical indices (NDVI, NDWI, NDSI) derived from Sentinel-2 to support surface water detection. Outputs include binary water masks from SAR and mean composite images of NDVI, NDWI, and NDSI for the year 2020.

- gold BAND_SELECT 位置: [{'seq': 2, 'prev': 'RASTER_LOAD', 'next': 'ATTRIBUTE_FILTER'}, {'seq': 6, 'prev': 'RASTER_LOAD', 'next': 'ATTRIBUTE_FILTER'}]
- 下游消费者: （无——isolated）
- owner_ruling: ______（gold_inconsistent / alternative_workflow / clearly_necessary）

## k=529 — Task: Analyze NDVI and VV time series

Task: Analyze NDVI and VV time series
Analyze temporal patterns of NDVI from Sentinel-2 and VV backscatter from Sentinel-1 over agricultural fields in Pergamino, Argentina. It processes cloud-masked Sentinel-2 imagery to compute NDVI and combines it with filtered Sentinel-1 VV polarization data over the same period. The output is an interactive chart showing NDVI and VV time series at user-clicked locations, enabling comparison of vegetation greenness and radar response throughout 2019.

- gold BAND_SELECT 位置: [{'seq': 5, 'prev': 'ATTRIBUTE_FILTER', 'next': 'SPATIAL_FILTER'}, {'seq': 9, 'prev': 'ATTRIBUTE_FILTER', 'next': 'TEMPORAL_FILTER'}]
- 下游消费者: （无——isolated）
- owner_ruling: ______（gold_inconsistent / alternative_workflow / clearly_necessary）

## k=556 — Task: Visualize urban land cover

Task: Visualize urban land cover
Create a time-lapse visualization of true-color satellite imagery over a user-defined geometry by filtering Sentinel-2 images for low cloud cover (less than 30%) and sorting them by acquisition date in descending order. It visualizes the B4, B3, and B2 bands (red, green, blue) with a fixed stretch (0–3000) to generate natural-color composite images, mosaics them into a single composite, clips to the study area, and exports a video timelapse to Google Drive. It al

- gold BAND_SELECT 位置: [{'seq': 5, 'prev': 'TEMPORAL_FILTER', 'next': 'COLLECTION_MGMT'}]
- 下游消费者: （无——isolated）
- owner_ruling: ______（gold_inconsistent / alternative_workflow / clearly_necessary）

## k=564 — Task: Classify water and shadow areas

Task: Classify water and shadow areas
Classify water and shadow areas using Landsat 7 and 8 surface reflectance imagery from 2020. It applies sensor-specific cloud masking (for Landsat 7 and 8) and merges collections to compute a median composite. A Random Forest classifier is trained using spectral, topographic, and textural features (including SWIR GLCM textures, HSV transform, AWEIsh index, SRTM-derived elevation, slope, mTPI, CHILI, and topographic diversity). The classification output is a 

- gold BAND_SELECT 位置: [{'seq': 3, 'prev': 'RASTER_LOAD', 'next': 'TEMPORAL_FILTER'}, {'seq': 8, 'prev': 'RASTER_LOAD', 'next': 'TEMPORAL_FILTER'}, {'seq': 13, 'prev': 'RASTER_LOAD', 'next': 'RASTER_LOAD'}, {'seq': 15, 'prev': 'RASTER_LOAD', 'next': 'RASTER_LOAD'}, {'seq': 17, 'prev': 'RASTER_LOAD', 'next': 'ATTRIBUTE_FILTER'}]
- 下游消费者: （无——isolated）
- owner_ruling: ______（gold_inconsistent / alternative_workflow / clearly_necessary）

## k=581 — Task: Extract land cover type

Task: Extract land cover type
Extract the annual International Geosphere-Biosphere Programme (IGBP) land cover classification (LC_Type1) from the MODIS MCD12Q1 dataset for the year 2018. It processes the image collection by reducing resolution using a median reducer, reprojects to EPSG:4326 at 11132 m scale, clips to a global extent, and exports each image in the collection individually to Google Drive as a raster file. The output consists of one or more GeoTIFFs representing global land cover t

- gold BAND_SELECT 位置: [{'seq': 8, 'prev': 'ATTRIBUTE_FILTER', 'next': None}]
- 下游消费者: （无——isolated）
- owner_ruling: ______（gold_inconsistent / alternative_workflow / clearly_necessary）

## k=592 — Task: Analyze day surface temperature

Task: Analyze day surface temperature
Extract and converts MODIS LST_Day_1km data to Celsius, then generates a time-series line chart of mean daytime land surface temperature over Patna district from January 2019 to April 2023.

- gold BAND_SELECT 位置: [{'seq': 3, 'prev': 'RASTER_LOAD', 'next': 'AGGREGATION'}]
- 下游消费者: （无——isolated）
- owner_ruling: ______（gold_inconsistent / alternative_workflow / clearly_necessary）

## k=604 — Task: Classify glacier and nunatak areas

Task: Classify glacier and nunatak areas
Classify glacier and nunatak areas on Nevado Ruiz volcano using Sentinel-2 imagery. It computes NDSI variants (ndsi_1, ndsi_2, ndsi_3) and NDWI from band ratios, applies cloud masking based on QA60 and local cloud cover threshold, selects the least cloudy image near a specified date, thresholds NDWI to mask water, then performs k-means clustering (3 clusters) on percentile-reduced NDSI bands trained with sample points. The result is a clustered classifica

- gold BAND_SELECT 位置: [{'seq': 1, 'prev': None, 'next': 'ATTRIBUTE_FILTER'}]
- 下游消费者: （无——isolated）
- owner_ruling: ______（gold_inconsistent / alternative_workflow / clearly_necessary）

## k=634 — Task: Visualize true-color surface reflectance

Task: Visualize true-color surface reflectance
the workflow retrieves Sentinel-2 Level-2A Surface Reflectance (SR) imagery over a user-defined region of interest (roi) for the first half of 2022, applies cloud filtering (<20% cloud coverage), composites to a median image, rescales reflectance values from integer DN (0–10000) to float (0–1), clips to roi, and visualizes the true-color composite (B4=red, B3=green, B2=blue) with stretch parameters (min=0, max=0.4); it exports the clipped, visualize

- gold BAND_SELECT 位置: [{'seq': 5, 'prev': 'TEMPORAL_FILTER', 'next': 'RASTER_LOAD'}, {'seq': 10, 'prev': 'TEMPORAL_FILTER', 'next': None}]
- 下游消费者: （无——isolated）
- owner_ruling: ______（gold_inconsistent / alternative_workflow / clearly_necessary）

## k=667 — Task: Analyze vegetation change using NDVI

Task: Analyze vegetation change using NDVI
Compute and compares NDVI from two Sentinel-2 image composites acquired in late June and early July 2016. It calculates dNDVI by subtracting the earlier NDVI (June 23–30) from the later one (July 1–10), highlighting changes in vegetation greenness over time. The outputs include RGB visualizations of both dates, NDVI maps for each period, and a dNDVI difference map to detect temporal vegetation dynamics such as growth or stress.

- gold BAND_SELECT 位置: [{'seq': 3, 'prev': 'TEMPORAL_FILTER', 'next': 'RASTER_LOAD'}, {'seq': 5, 'prev': 'RASTER_LOAD', 'next': 'TEMPORAL_FILTER'}]
- 下游消费者: （无——isolated）
- owner_ruling: ______（gold_inconsistent / alternative_workflow / clearly_necessary）

## k=672 — Task: Classify land cover types

Task: Classify land cover types
Classify land cover types using Sentinel-2 surface reflectance imagery from the dry season (2020-01-01 to 2020-03-30). It computes NDVI and MVI indices, applies cloud masking via QA60 band, and generates a median composite. A Random Forest classifier is trained on labeled training samples (including 'Herbazal_inundable') with 50 trees, using spectral bands and vegetation indices as predictors. The classification accuracy is assessed through a confusion matrix usin

- gold BAND_SELECT 位置: [{'seq': 5, 'prev': 'ITERATIVE_APPLY', 'next': 'CLASSIFICATION'}]
- 下游消费者: （无——isolated）
- owner_ruling: ______（gold_inconsistent / alternative_workflow / clearly_necessary）

## k=681 — Task: Visualize fire hotspots over time

Task: Visualize fire hotspots over time
Visualize active fire detections from the FIRMS dataset overlaid on cloud-masked Sentinel-2 surface reflectance imagery for the year 2019. It creates a time-series of blended RGB images where fire locations (based on T21 brightness temperature) are highlighted in yellow-orange-red over a median background composite, and generates animated thumbnails for successive monthly intervals to show spatiotemporal fire activity patterns.

- gold BAND_SELECT 位置: [{'seq': 9, 'prev': 'RASTER_LOAD', 'next': 'RASTER_LOAD'}]
- 下游消费者: （无——isolated）
- owner_ruling: ______（gold_inconsistent / alternative_workflow / clearly_necessary）

## k=682 — Task: Map land cover with Landsat composite

Task: Map land cover with Landsat composite
Create a median surface reflectance composite from Landsat 5 and Landsat 7 imagery (bands 3, 2, 1) over a user-defined AOI for the year 2001, filtered by cloud cover, to generate a natural-color visualization for land cover analysis.

- gold BAND_SELECT 位置: [{'seq': 3, 'prev': 'ATTRIBUTE_FILTER', 'next': 'SPATIAL_FILTER'}, {'seq': 7, 'prev': 'ATTRIBUTE_FILTER', 'next': 'SPATIAL_FILTER'}]
- 下游消费者: （无——isolated）
- owner_ruling: ______（gold_inconsistent / alternative_workflow / clearly_necessary）

## k=689 — Task: Classify agricultural vegetation types

Task: Classify agricultural vegetation types
Classify agricultural and land cover types using a Random Forest classifier trained on fused Sentinel-1 SAR (VV/VH) and Sentinel-2 spectral vegetation indices (e.g., NDVI, EVI, SAVI) data. The output is a binary classification map per region indicating presence of specific crop types (e.g., Aloevera, Banana, Cassava) and other land covers, exported as classified raster images for multiple regions.

- gold BAND_SELECT 位置: [{'seq': 19, 'prev': 'SPATIAL_FILTER', 'next': 'TEMPORAL_FILTER'}, {'seq': 24, 'prev': 'SPATIAL_FILTER', 'next': 'TEMPORAL_FILTER'}]
- 下游消费者: （无——isolated）
- owner_ruling: ______（gold_inconsistent / alternative_workflow / clearly_necessary）

## k=690 — Task: Estimate NDVI and GVF from Landsat

Task: Estimate NDVI and GVF from Landsat
Compute median NDVI and Green Vegetation Fraction (GVF) by applying cloud-masked Landsat surface reflectance data from 1998 to 2015, merging Landsat 5, 7, and 8 collections, then reducing them annually before calculating NDVI and scaling it to GVF using fixed min-max values. Outputs include NDVI and GVF maps, along with regional statistics.

- gold BAND_SELECT 位置: [{'seq': 4, 'prev': 'ITERATIVE_APPLY', 'next': 'RASTER_LOAD'}, {'seq': 7, 'prev': 'ITERATIVE_APPLY', 'next': 'RASTER_LOAD'}]
- 下游消费者: （无——isolated）
- owner_ruling: ______（gold_inconsistent / alternative_workflow / clearly_necessary）

## k=706 — Task: Analyze NDVI time series by land type

Task: Analyze NDVI time series by land type
Analyze and compares NDVI time series from Landsat 8 and MODIS over different land cover types (canyon, residential, built-up) near San Diego in 2018, generating temporal charts of mean NDVI and EVI values for spatial comparison.

- gold BAND_SELECT 位置: [{'seq': 7, 'prev': 'ATTRIBUTE_FILTER', 'next': 'AGGREGATION'}, {'seq': 12, 'prev': 'ATTRIBUTE_FILTER', 'next': 'AGGREGATION'}]
- 下游消费者: （无——isolated）
- owner_ruling: ______（gold_inconsistent / alternative_workflow / clearly_necessary）

## k=712 — Task: Compute mean surface temperature

Task: Compute mean surface temperature
Compute the mean land surface temperature (LST) in degrees Celsius from Landsat 8 thermal infrared data over a user-defined area of interest (aoi) for March–April 2018, applying cloud masking and scaling, then visualizes and prints a histogram of the clipped mean temperature.

- gold BAND_SELECT 位置: [{'seq': 2, 'prev': 'RASTER_LOAD', 'next': 'SPATIAL_FILTER'}]
- 下游消费者: （无——isolated）
- owner_ruling: ______（gold_inconsistent / alternative_workflow / clearly_necessary）

## k=714 — Task: Analyze NDVI time series

Task: Analyze NDVI time series
Compute and visualizes a time series of NDVI over a specified geometry using Sentinel-2 surface reflectance imagery from June 10 to June 23, 2021. It applies cloud masking based on the Scene Classification Layer (SCL), filters images by cloud cover and no-data percentage, calculates NDVI using near-infrared (B8) and red (B4) bands, and generates a chart of mean NDVI values over the region. Outputs include a clipped first image visualization in true color, an NDVI m

- gold BAND_SELECT 位置: [{'seq': 5, 'prev': 'SPATIAL_FILTER', 'next': 'AGGREGATION'}]
- 下游消费者: （无——isolated）
- owner_ruling: ______（gold_inconsistent / alternative_workflow / clearly_necessary）

## k=719 — Task: Analyze snow water equivalent trend

Task: Analyze snow water equivalent trend
Analyze the temporal variation of snow water equivalent (SWE) over a rectangular region in Canada using the TerraClimate dataset from 2014 to 2021. It filters the SWE image collection by geometry and date, computes mean SWE values within the region at 100-meter scale, and generates a scatter chart showing monthly SWE dynamics over time. The output includes the filtered SWE image collection, a map layer visualization, and a time-series scatter plot with c

- gold BAND_SELECT 位置: [{'seq': 2, 'prev': 'RASTER_LOAD', 'next': 'SPATIAL_FILTER'}]
- 下游消费者: （无——isolated）
- owner_ruling: ______（gold_inconsistent / alternative_workflow / clearly_necessary）

## k=769 — Task: Analyze vegetation index time series

Task: Analyze vegetation index time series
Analyze temporal patterns of vegetation indices (NDVI, EVI, SAVI) over the semi-arid region using Landsat 5, 7, and 8 surface reflectance data from 1997 to 2014. It applies cloud masking and sample-based masking using a feature collection 'samples', computes monthly composites, and extracts pixel values within sample regions. The outputs include median monthly image collections, time series tables for each Landsat sensor, and line charts showing mean ND

- gold BAND_SELECT 位置: [{'seq': 2, 'prev': 'RASTER_LOAD', 'next': 'RASTER_LOAD'}, {'seq': 4, 'prev': 'RASTER_LOAD', 'next': 'RASTER_LOAD'}, {'seq': 6, 'prev': 'RASTER_LOAD', 'next': 'ATTRIBUTE_FILTER'}]
- 下游消费者: （无——isolated）
- owner_ruling: ______（gold_inconsistent / alternative_workflow / clearly_necessary）

## k=787 — Task: Reproject Sentinel-2 imagery

Task: Reproject Sentinel-2 imagery
Process Sentinel-2 surface reflectance data for a specific region in Shandong Province, China, reprojects it to a UTM coordinate system based on the region's longitude and latitude, and exports the reprojected image to Google Drive. The output is a clipped and reprojected 10-meter resolution RGB and multispectral image from October 27, 2019.

- gold BAND_SELECT 位置: [{'seq': 4, 'prev': 'AGGREGATION', 'next': None}]
- 下游消费者: （无——isolated）
- owner_ruling: ______（gold_inconsistent / alternative_workflow / clearly_necessary）

## k=790 — Task: Assess wildfire severity using spectral indices

Task: Assess wildfire severity using spectral indices
the workflow assesses wildfire severity by computing the difference in Normalized Burn Ratio (NBR) between pre-fire (July 2019) and active fire (August 2019) periods using Sentinel-2, Sentinel-3, Sentinel-5P, and Sentinel-1 data. It generates false-color composites, NDVI, NBR, CO concentration maps, radar backscatter, and burn severity layers for visual and spatial analysis of environmental impact.

- gold BAND_SELECT 位置: [{'seq': 11, 'prev': 'RASTER_LOAD', 'next': 'AGGREGATION'}, {'seq': 14, 'prev': 'RASTER_LOAD', 'next': 'AGGREGATION'}, {'seq': 18, 'prev': 'ATTRIBUTE_FILTER', 'next': 'ATTRIBUTE_FILTER'}]
- 下游消费者: （无——isolated）
- owner_ruling: ______（gold_inconsistent / alternative_workflow / clearly_necessary）

## k=793 — Task: Extract NDVI time series

Task: Extract NDVI time series
Extract MODIS NDVI time series data for August 2021 over a user-defined region of interest (luqu). It processes the MOD13Q1 collection by applying scaling (multiply by 0.0001), clipping to the ROI, and visualizing with a vegetation-appropriate color palette. It then exports each image in the time series individually to Google Drive as GeoTIFF files, named by their system:index, resulting in a complete temporal stack of NDVI rasters for the period.

- gold BAND_SELECT 位置: [{'seq': 4, 'prev': 'SPATIAL_FILTER', 'next': 'AGGREGATION'}]
- 下游消费者: （无——isolated）
- owner_ruling: ______（gold_inconsistent / alternative_workflow / clearly_necessary）

## k=811 — Task: Extract GPP ET LAI time series

Task: Extract GPP ET LAI time series
Extract and processes time series of Gross Primary Productivity (GPP), Evapotranspiration (ET), and Leaf Area Index (LAI) for a specific point location (US-WCr) using MODIS imagery from 2004 to 2019. It applies scaling factors to convert raw digital values into scientifically meaningful units: GPP in gC/m²/day, ET in mm/day, and LAI in m²/m². The processed ImageCollections are filtered by date and optionally visualized on the map, with the primary output bein

- gold BAND_SELECT 位置: [{'seq': 10, 'prev': 'RASTER_LOAD', 'next': 'TEMPORAL_FILTER'}]
- 下游消费者: （无——isolated）
- owner_ruling: ______（gold_inconsistent / alternative_workflow / clearly_necessary）

## k=815 — Task: Analyze actual evapotranspiration in Central African Republic

Task: Analyze actual evapotranspiration in Central African Republic
Analyze daily actual evapotranspiration and transpiration (L1_AETI_D) from the FAO WAPOR dataset over the Central African Republic for April 2021. It processes the image collection by scaling pixel values (multiplying by 0.1), clipping to the country boundary, computing the monthly sum, and extracting mean areal statistics using reduceRegions. Outputs include a clipped and scaled evapotranspiration raster map for the region and 

- gold BAND_SELECT 位置: [{'seq': 3, 'prev': 'RASTER_LOAD', 'next': 'AGGREGATION'}]
- 下游消费者: （无——isolated）
- owner_ruling: ______（gold_inconsistent / alternative_workflow / clearly_necessary）

## k=818 — Task: Classify land cover with Dynamic World

Task: Classify land cover with Dynamic World
Classify land cover types for 71 Chinese cities using the Dynamic World dataset from Google Earth Engine. It processes imagery from June to October of 2022, composites the maximum label probability over time, clips to individual city grid boundaries from a user-defined feature collection, and exports each resulting classified raster to Google Drive at 10m resolution. The output is a series of per-grid land cover maps in raster format, labeled by grid 

- gold BAND_SELECT 位置: [{'seq': 6, 'prev': 'SPATIAL_FILTER', 'next': 'AGGREGATION'}]
- 下游消费者: （无——isolated）
- owner_ruling: ______（gold_inconsistent / alternative_workflow / clearly_necessary）

## k=820 — Task: Analyze mangrove vegetation indices

Task: Analyze mangrove vegetation indices
Compute multiple vegetation and moisture indices from Sentinel-2-like median composite imagery and integrates them with Sentinel-1 SAR data (VV/VH polarizations) and PALSAR data to support mangrove analysis. The output is a stacked image combining optical indices, radar backscatter means, and training labels for potential classification or regression modeling of mangrove extent or condition.

- gold BAND_SELECT 位置: [{'seq': 3, 'prev': 'ATTRIBUTE_FILTER', 'next': 'ATTRIBUTE_FILTER'}, {'seq': 7, 'prev': 'ATTRIBUTE_FILTER', 'next': 'ATTRIBUTE_FILTER'}]
- 下游消费者: （无——isolated）
- owner_ruling: ______（gold_inconsistent / alternative_workflow / clearly_necessary）

## k=824 — Task: Detect landslide-affected areas

Task: Detect landslide-affected areas
Detect landslide-affected areas by analyzing changes in SAR amplitude from Sentinel-1 data before and after a triggering event, combined with slope and curvature masks derived from SRTM to focus on steep, geomorphically active terrain.

- gold BAND_SELECT 位置: [{'seq': 11, 'prev': 'ATTRIBUTE_FILTER', 'next': 'SPATIAL_FILTER'}]
- 下游消费者: （无——isolated）
- owner_ruling: ______（gold_inconsistent / alternative_workflow / clearly_necessary）

## k=829 — Task: Analyze vegetation health using spectral indices

Task: Analyze vegetation health using spectral indices
Compute multiple vegetation and water-related spectral indices (EVI, NDVI, GNDVI, NRGI, RVI, NDWI, SAVI) from Landsat 8 TOA reflectance data, applies outlier filtering based on percentile thresholds, and fits time series models to the indices using a custom TimeSeries module. The output is a collection of enhanced images with added spectral indices and fitted model coefficients for temporal analysis.

- gold BAND_SELECT 位置: [{'seq': 2, 'prev': 'RASTER_LOAD', 'next': 'RASTER_LOAD'}]
- 下游消费者: （无——isolated）
- owner_ruling: ______（gold_inconsistent / alternative_workflow / clearly_necessary）

## k=848 — Task: Analyze cloud and cirrus presence

Task: Analyze cloud and cirrus presence
Analyze cloud and cirrus pixel coverage in Sentinel-2 surface reflectance images over a specific region between January and June 2020, using the QA60 band to derive per-pixel cloud/cirrus masks. It generates time-series charts of cloudiness distribution, identifies the least cloudy image, and exports NDVI visualizations and masked imagery for further analysis.

- gold BAND_SELECT 位置: [{'seq': 6, 'prev': 'ATTRIBUTE_FILTER', 'next': 'ITERATIVE_APPLY'}]
- 下游消费者: （无——isolated）
- owner_ruling: ______（gold_inconsistent / alternative_workflow / clearly_necessary）

## k=849 — Task: Extract riparian forest NDVI along rivers

Task: Extract riparian forest NDVI along rivers
Analyze riparian forests along three major rivers in California (Santa Clara River, Salinas River, and South Fork Kern River) using NDVI derived from Landsat 7 Collection 2 Level 2 surface reflectance data from 2000 to 2021. It first identifies riparian forest areas by clipping a precomputed forest layer to 500-meter buffers around river segments. Then, for each cloud-masked image within the summer season (July 1–September 30) and with less than 20

- gold BAND_SELECT 位置: [{'seq': 5, 'prev': 'SPATIAL_FILTER', 'next': 'ATTRIBUTE_FILTER'}, {'seq': 9, 'prev': 'SPATIAL_FILTER', 'next': 'ATTRIBUTE_FILTER'}, {'seq': 13, 'prev': 'SPATIAL_FILTER', 'next': 'ATTRIBUTE_FILTER'}]
- 下游消费者: （无——isolated）
- owner_ruling: ______（gold_inconsistent / alternative_workflow / clearly_necessary）

## k=860 — Task: Estimate annual ET by county

Task: Estimate annual ET by county
Calculate total evapotranspiration (ET) from MODIS MOD16A2 data over a three-day period in July 2001, then aggregates the mean ET values to U.S. counties (excluding non-CONUS territories), and exports the results as a CSV file for each county with a year attribute set to 2001.

- gold BAND_SELECT 位置: [{'seq': 2, 'prev': 'RASTER_LOAD', 'next': 'AGGREGATION'}]
- 下游消费者: （无——isolated）
- owner_ruling: ______（gold_inconsistent / alternative_workflow / clearly_necessary）

## k=861 — Task: Plot MODIS surface reflectance histogram

Task: Plot MODIS surface reflectance histogram
Compute a histogram of surface reflectance values for three MODIS spectral bands (red, NIR, and SWIR) from a mean-composite image derived from the MOD09A1 collection over a specified rectangular region. It visualizes the frequency distribution of reflectance values (scaled by 1e4) per band as an interactive histogram chart in the GEE Code Editor console, with custom series names, axis labels, colors, and styling — intended for spectral signature ana

- gold BAND_SELECT 位置: [{'seq': 4, 'prev': 'ATTRIBUTE_FILTER', 'next': None}]
- 下游消费者: （无——isolated）
- owner_ruling: ______（gold_inconsistent / alternative_workflow / clearly_necessary）

## k=876 — Task: Classify land cover in Tuguegarao

Task: Classify land cover in Tuguegarao
Classify land cover in Tuguegarao City using Sentinel-1 SAR imagery and ESA WorldCover 2020 as reference data. It performs stratified sampling over a region of interest, trains a Random Forest classifier using backscatter bands from Sentinel-1, evaluates training and validation accuracy through confusion matrices, and generates a classified land cover map. The output includes the classified raster, training/validation sample points, accuracy assessments, a

- gold BAND_SELECT 位置: [{'seq': 7, 'prev': 'SPATIAL_FILTER', 'next': 'AGGREGATION'}]
- 下游消费者: （无——isolated）
- owner_ruling: ______（gold_inconsistent / alternative_workflow / clearly_necessary）

## k=882 — Task: Classify land cover in Tuguegarao

Task: Classify land cover in Tuguegarao
Classify land cover in Tuguegarao City using a Random Forest classifier trained on Landsat 8 surface reflectance imagery. It uses labeled training samples for five classes—Inland Water, Bare Soil, Cropland, Forested Land, and Built-up Land—extracted from the study area. After cloud masking and compositing, the model is trained and validated using accuracy metrics including confusion matrix, overall accuracy, and kappa coefficient. The final classified map 

- gold BAND_SELECT 位置: [{'seq': 6, 'prev': 'SPATIAL_FILTER', 'next': 'ATTRIBUTE_FILTER'}]
- 下游消费者: （无——isolated）
- owner_ruling: ______（gold_inconsistent / alternative_workflow / clearly_necessary）

## k=883 — Task: Classify land cover types

Task: Classify land cover types
Classify land cover in the Mtwara region using Landsat 8 surface reflectance and Sentinel-1 SAR data from 2013–2015. It computes multiple spectral indices (NDVI, NDWI, NDWBI, mNDWBI, and band ratios), combines them with topographic data (dem) into a feature stack, applies Random Forest classification trained on labeled samples (fc1), and generates a classified land cover map. The output includes the classified raster map visualized with a custom palette, accuracy 

- gold BAND_SELECT 位置: [{'seq': 7, 'prev': 'AGGREGATION', 'next': 'CLASSIFICATION'}]
- 下游消费者: （无——isolated）
- owner_ruling: ______（gold_inconsistent / alternative_workflow / clearly_necessary）

## k=891 — Task: Calculate water balance components

Task: Calculate water balance components
Calculate monthly actual evapotranspiration (ET), precipitation (P), and runoff (RO) from TerraClimate data over the Kahayan-Sebangau River Basin (KHG) between 2010 and 2020, then computes a water balance as P - (ET/10) - (P*0.25). It outputs time-series column charts of ET, P, RO, and water balance across the region.

- gold BAND_SELECT 位置: [{'seq': 2, 'prev': 'RASTER_LOAD', 'next': 'TEMPORAL_FILTER'}, {'seq': 6, 'prev': 'RASTER_LOAD', 'next': 'TEMPORAL_FILTER'}, {'seq': 10, 'prev': 'RASTER_LOAD', 'next': 'TEMPORAL_FILTER'}]
- 下游消费者: （无——isolated）
- owner_ruling: ______（gold_inconsistent / alternative_workflow / clearly_necessary）

## k=902 — Task: Generate median surface reflectance composite

Task: Generate median surface reflectance composite
Generate a median surface reflectance composite from Landsat 8 Collection 1 Tier 1 Surface Reflectance data for the specified region and time period, masking clouds and cloud shadows, and visualizing true-color imagery (B4, B3, B2) clipped to the region of interest.

- gold BAND_SELECT 位置: [{'seq': 5, 'prev': 'ITERATIVE_APPLY', 'next': 'AGGREGATION'}]
- 下游消费者: （无——isolated）
- owner_ruling: ______（gold_inconsistent / alternative_workflow / clearly_necessary）

## k=907 — Task: Classify pineapple plantations using multisensor data

Task: Classify pineapple plantations using multisensor data
Classify pineapple plantations versus other land cover types using a Random Forest classifier trained on fused Sentinel-2 optical vegetation indices and Sentinel-1 SAR data (VV/VH) over specific regions of interest. The output is a binary classified map exported to Google Drive for each ROI, where pineapple (class 1) is distinguished from others (class 2).

- gold BAND_SELECT 位置: [{'seq': 8, 'prev': 'SPATIAL_FILTER', 'next': 'TEMPORAL_FILTER'}, {'seq': 13, 'prev': 'SPATIAL_FILTER', 'next': 'TEMPORAL_FILTER'}, {'seq': 22, 'prev': 'SPATIAL_FILTER', 'next': 'TEMPORAL_FILTER'}, {'seq': 27, 'prev': 'SPATIAL_FILTER', 'next': 'TEMPORAL_FILTER'}]
- 下游消费者: （无——isolated）
- owner_ruling: ______（gold_inconsistent / alternative_workflow / clearly_necessary）

## k=920 — Task: Analyze dust aerosol optical depth

Task: Analyze dust aerosol optical depth
Analyze the mean Dust Aerosol Optical Depth at 550nm (DUEXTTAU) from MERRA-2 reanalysis data over Hanoi between August 1 and August 30, 2021. It computes a time-averaged image of AOD and clips it to the Hanoi boundary, then generates a time series chart of daily mean AOD values within the region.

- gold BAND_SELECT 位置: [{'seq': 2, 'prev': 'RASTER_LOAD', 'next': 'TEMPORAL_FILTER'}]
- 下游消费者: （无——isolated）
- owner_ruling: ______（gold_inconsistent / alternative_workflow / clearly_necessary）

## k=946 — Task: Unmix rice crop fractions

Task: Unmix rice crop fractions
Estimate the proportional coverage of two rice varieties (Cakrabuana and Inpari 32) at 29 days after transplanting (29 HST) by spectral unmixing of a cloud-masked Sentinel-2 surface reflectance composite over a specific field geometry.

- gold BAND_SELECT 位置: [{'seq': 4, 'prev': 'ITERATIVE_APPLY', 'next': None}]
- 下游消费者: （无——isolated）
- owner_ruling: ______（gold_inconsistent / alternative_workflow / clearly_necessary）

## k=956 — Task: Compute mean annual precipitation

Task: Compute mean annual precipitation
Calculate the mean annual precipitation from 2002 to 2021 by summing daily CHIRPS precipitation data for each year and then averaging the resulting yearly totals. The final output is a single raster layer representing the 20-year average precipitation, clipped to a specified model area and visualized with a custom palette.

- gold BAND_SELECT 位置: [{'seq': 4, 'prev': 'ATTRIBUTE_FILTER', 'next': 'AGGREGATION'}, {'seq': 9, 'prev': 'ATTRIBUTE_FILTER', 'next': 'AGGREGATION'}, {'seq': 14, 'prev': 'ATTRIBUTE_FILTER', 'next': 'AGGREGATION'}, {'seq': 19, 'prev': 'ATTRIBUTE_FILTER', 'next': 'AGGREGATION'}, {'seq': 24, 'prev': 'ATTRIBUTE_FILTER', 'next': 'AGGREGATION'}, {'seq': 29, 'prev': 'ATTRIBUTE_FILTER', 'next': 'AGGREGATION'}, {'seq': 34, 'prev': 'ATTRIBUTE_FILTER', 'next': 'AGGREGATION'}, {'seq': 39, 'prev': 'ATTRIBUTE_FILTER', 'next': 'AGGREGATION'}, {'seq': 44, 'prev': 'ATTRIBUTE_FILTER', 'next': 'AGGREGATION'}, {'seq': 49, 'prev': 'ATTRIBUTE_FILTER', 'next': 'AGGREGATION'}, {'seq': 54, 'prev': 'ATTRIBUTE_FILTER', 'next': 'AGGREGATION'}, {'seq': 59, 'prev': 'ATTRIBUTE_FILTER', 'next': 'AGGREGATION'}, {'seq': 64, 'prev': 'ATTRIBUTE_FILTER', 'next': 'AGGREGATION'}, {'seq': 69, 'prev': 'ATTRIBUTE_FILTER', 'next': 'AGGREGATION'}, {'seq': 74, 'prev': 'ATTRIBUTE_FILTER', 'next': 'AGGREGATION'}, {'seq': 79, 'prev': 'ATTRIBUTE_FILTER', 'next': 'AGGREGATION'}, {'seq': 84, 'prev': 'ATTRIBUTE_FILTER', 'next': 'AGGREGATION'}, {'seq': 89, 'prev': 'ATTRIBUTE_FILTER', 'next': 'AGGREGATION'}, {'seq': 94, 'prev': 'ATTRIBUTE_FILTER', 'next': 'AGGREGATION'}, {'seq': 99, 'prev': 'ATTRIBUTE_FILTER', 'next': 'AGGREGATION'}]
- 下游消费者: （无——isolated）
- owner_ruling: ______（gold_inconsistent / alternative_workflow / clearly_necessary）

## k=958 — Task: Estimate wheat yield from Sentinel-2 time series

Task: Estimate wheat yield from Sentinel-2 time series
Estimate winter wheat yield in Henan Province by generating a time series of Sentinel-2 surface reflectance images from October 15, 2016, to June 15, 2017, extracting spectral features at point sample locations with known yield values, and structuring the data for machine learning modeling. The output is a CSV file of training samples containing multi-temporal spectral bands and corresponding yield labels (kg/hm²), spatially organized into g

- gold BAND_SELECT 位置: [{'seq': 4, 'prev': 'SPATIAL_FILTER', 'next': 'AGGREGATION'}]
- 下游消费者: （无——isolated）
- owner_ruling: ______（gold_inconsistent / alternative_workflow / clearly_necessary）

## k=980 — Task: Classify land cover types

Task: Classify land cover types
Classify land cover types using multi-temporal Sentinel-2 surface reflectance data, computing multiple vegetation indices (NDVI, EVI, GNDVI, MSAVI, NDWI, GCVI, TCARI) across seven time periods from May to November 2020 over a specific administrative region in Argentina. It applies a Random Forest classifier trained on labeled samples and outputs a classified land cover map with 11 classes, including crops, forests, pastures, and natural lands, along with accuracy 

- gold BAND_SELECT 位置: [{'seq': 4, 'prev': 'TEMPORAL_FILTER', 'next': 'RASTER_LOAD'}, {'seq': 8, 'prev': 'TEMPORAL_FILTER', 'next': 'RASTER_LOAD'}, {'seq': 12, 'prev': 'TEMPORAL_FILTER', 'next': 'RASTER_LOAD'}, {'seq': 16, 'prev': 'TEMPORAL_FILTER', 'next': 'RASTER_LOAD'}, {'seq': 20, 'prev': 'TEMPORAL_FILTER', 'next': 'RASTER_LOAD'}, {'seq': 24, 'prev': 'TEMPORAL_FILTER', 'next': 'RASTER_LOAD'}, {'seq': 28, 'prev': 'TEMPORAL_FILTER', 'next': 'RASTER_LOAD'}, {'seq': 32, 'prev': 'TEMPORAL_FILTER', 'next': 'RASTER_LOAD'}]
- 下游消费者: （无——isolated）
- owner_ruling: ______（gold_inconsistent / alternative_workflow / clearly_necessary）

## k=994 — Task: Identify perennial water bodies

Task: Identify perennial water bodies
Calculate the frequency of water occurrence in a region using Landsat 5, 7, and 8 surface reflectance data from 1984 to 2021. It computes multiple vegetation and water indices (NDVI, EVI, LSWI, mNDWI), applies a water detection threshold based on mNDWI and EVI, and generates an annual 'water frequency' map. A binary mask is created where pixels with water frequency ≥75% are classified as permanent water. The output is a boolean raster (imgPerWater) exported 

- gold BAND_SELECT 位置: [{'seq': 7, 'prev': 'ITERATIVE_APPLY', 'next': 'RASTER_LOAD'}, {'seq': 13, 'prev': 'ITERATIVE_APPLY', 'next': 'RASTER_LOAD'}, {'seq': 19, 'prev': 'ITERATIVE_APPLY', 'next': 'AGGREGATION'}, {'seq': 26, 'prev': 'ITERATIVE_APPLY', 'next': 'RASTER_LOAD'}, {'seq': 32, 'prev': 'ITERATIVE_APPLY', 'next': 'RASTER_LOAD'}, {'seq': 38, 'prev': 'ITERATIVE_APPLY', 'next': 'AGGREGATION'}, {'seq': 45, 'prev': 'ITERATIVE_APPLY', 'next': 'RASTER_LOAD'}, {'seq': 51, 'prev': 'ITERATIVE_APPLY', 'next': 'RASTER_LOAD'}, {'seq': 57, 'prev': 'ITERATIVE_APPLY', 'next': 'AGGREGATION'}, {'seq': 64, 'prev': 'ITERATIVE_APPLY', 'next': 'RASTER_LOAD'}, {'seq': 70, 'prev': 'ITERATIVE_APPLY', 'next': 'RASTER_LOAD'}, {'seq': 76, 'prev': 'ITERATIVE_APPLY', 'next': 'AGGREGATION'}, {'seq': 83, 'prev': 'ITERATIVE_APPLY', 'next': 'RASTER_LOAD'}, {'seq': 89, 'prev': 'ITERATIVE_APPLY', 'next': 'RASTER_LOAD'}, {'seq': 95, 'prev': 'ITERATIVE_APPLY', 'next': 'AGGREGATION'}, {'seq': 102, 'prev': 'ITERATIVE_APPLY', 'next': 'RASTER_LOAD'}, {'seq': 108, 'prev': 'ITERATIVE_APPLY', 'next': 'RASTER_LOAD'}, {'seq': 114, 'prev': 'ITERATIVE_APPLY', 'next': 'AGGREGATION'}, {'seq': 121, 'prev': 'ITERATIVE_APPLY', 'next': 'RASTER_LOAD'}, {'seq': 127, 'prev': 'ITERATIVE_APPLY', 'next': 'RASTER_LOAD'}, {'seq': 133, 'prev': 'ITERATIVE_APPLY', 'next': 'AGGREGATION'}, {'seq': 140, 'prev': 'ITERATIVE_APPLY', 'next': 'RASTER_LOAD'}, {'seq': 146, 'prev': 'ITERATIVE_APPLY', 'next': 'RASTER_LOAD'}, {'seq': 152, 'prev': 'ITERATIVE_APPLY', 'next': 'AGGREGATION'}, {'seq': 159, 'prev': 'ITERATIVE_APPLY', 'next': 'RASTER_LOAD'}, {'seq': 165, 'prev': 'ITERATIVE_APPLY', 'next': 'RASTER_LOAD'}, {'seq': 171, 'prev': 'ITERATIVE_APPLY', 'next': 'AGGREGATION'}, {'seq': 178, 'prev': 'ITERATIVE_APPLY', 'next': 'RASTER_LOAD'}, {'seq': 184, 'prev': 'ITERATIVE_APPLY', 'next': 'RASTER_LOAD'}, {'seq': 190, 'prev': 'ITERATIVE_APPLY', 'next': 'AGGREGATION'}, {'seq': 197, 'prev': 'ITERATIVE_APPLY', 'next': 'RASTER_LOAD'}, {'seq': 203, 'prev': 'ITERATIVE_APPLY', 'next': 'RASTER_LOAD'}, {'seq': 209, 'prev': 'ITERATIVE_APPLY', 'next': 'AGGREGATION'}, {'seq': 216, 'prev': 'ITERATIVE_APPLY', 'next': 'RASTER_LOAD'}, {'seq': 222, 'prev': 'ITERATIVE_APPLY', 'next': 'RASTER_LOAD'}, {'seq': 228, 'prev': 'ITERATIVE_APPLY', 'next': 'AGGREGATION'}, {'seq': 235, 'prev': 'ITERATIVE_APPLY', 'next': 'RASTER_LOAD'}, {'seq': 241, 'prev': 'ITERATIVE_APPLY', 'next': 'RASTER_LOAD'}, {'seq': 247, 'prev': 'ITERATIVE_APPLY', 'next': 'AGGREGATION'}, {'seq': 254, 'prev': 'ITERATIVE_APPLY', 'next': 'RASTER_LOAD'}, {'seq': 260, 'prev': 'ITERATIVE_APPLY', 'next': 'RASTER_LOAD'}, {'seq': 266, 'prev': 'ITERATIVE_APPLY', 'next': 'AGGREGATION'}, {'seq': 273, 'prev': 'ITERATIVE_APPLY', 'next': 'RASTER_LOAD'}, {'seq': 279, 'prev': 'ITERATIVE_APPLY', 'next': 'RASTER_LOAD'}, {'seq': 285, 'prev': 'ITERATIVE_APPLY', 'next': 'AGGREGATION'}, {'seq': 292, 'prev': 'ITERATIVE_APPLY', 'next': 'RASTER_LOAD'}, {'seq': 298, 'prev': 'ITERATIVE_APPLY', 'next': 'RASTER_LOAD'}, {'seq': 304, 'prev': 'ITERATIVE_APPLY', 'next': 'AGGREGATION'}, {'seq': 311, 'prev': 'ITERATIVE_APPLY', 'next': 'RASTER_LOAD'}, {'seq': 317, 'prev': 'ITERATIVE_APPLY', 'next': 'RASTER_LOAD'}, {'seq': 323, 'prev': 'ITERATIVE_APPLY', 'next': 'AGGREGATION'}, {'seq': 330, 'prev': 'ITERATIVE_APPLY', 'next': 'RASTER_LOAD'}, {'seq': 336, 'prev': 'ITERATIVE_APPLY', 'next': 'RASTER_LOAD'}, {'seq': 342, 'prev': 'ITERATIVE_APPLY', 'next': 'AGGREGATION'}, {'seq': 349, 'prev': 'ITERATIVE_APPLY', 'next': 'RASTER_LOAD'}, {'seq': 355, 'prev': 'ITERATIVE_APPLY', 'next': 'RASTER_LOAD'}, {'seq': 361, 'prev': 'ITERATIVE_APPLY', 'next': 'AGGREGATION'}, {'seq': 368, 'prev': 'ITERATIVE_APPLY', 'next': 'RASTER_LOAD'}, {'seq': 374, 'prev': 'ITERATIVE_APPLY', 'next': 'RASTER_LOAD'}, {'seq': 380, 'prev': 'ITERATIVE_APPLY', 'next': 'AGGREGATION'}, {'seq': 387, 'prev': 'ITERATIVE_APPLY', 'next': 'RASTER_LOAD'}, {'seq': 393, 'prev': 'ITERATIVE_APPLY', 'next': 'RASTER_LOAD'}, {'seq': 399, 'prev': 'ITERATIVE_APPLY', 'next': 'AGGREGATION'}, {'seq': 406, 'prev': 'ITERATIVE_APPLY', 'next': 'RASTER_LOAD'}, {'seq': 412, 'prev': 'ITERATIVE_APPLY', 'next': 'RASTER_LOAD'}, {'seq': 418, 'prev': 'ITERATIVE_APPLY', 'next': 'AGGREGATION'}, {'seq': 425, 'prev': 'ITERATIVE_APPLY', 'next': 'RASTER_LOAD'}, {'seq': 431, 'prev': 'ITERATIVE_APPLY', 'next': 'RASTER_LOAD'}, {'seq': 437, 'prev': 'ITERATIVE_APPLY', 'next': 'AGGREGATION'}, {'seq': 444, 'prev': 'ITERATIVE_APPLY', 'next': 'RASTER_LOAD'}, {'seq': 450, 'prev': 'ITERATIVE_APPLY', 'next': 'RASTER_LOAD'}, {'seq': 456, 'prev': 'ITERATIVE_APPLY', 'next': 'AGGREGATION'}, {'seq': 463, 'prev': 'ITERATIVE_APPLY', 'next': 'RASTER_LOAD'}, {'seq': 469, 'prev': 'ITERATIVE_APPLY', 'next': 'RASTER_LOAD'}, {'seq': 475, 'prev': 'ITERATIVE_APPLY', 'next': 'AGGREGATION'}, {'seq': 482, 'prev': 'ITERATIVE_APPLY', 'next': 'RASTER_LOAD'}, {'seq': 488, 'prev': 'ITERATIVE_APPLY', 'next': 'RASTER_LOAD'}, {'seq': 494, 'prev': 'ITERATIVE_APPLY', 'next': 'AGGREGATION'}, {'seq': 501, 'prev': 'ITERATIVE_APPLY', 'next': 'RASTER_LOAD'}, {'seq': 507, 'prev': 'ITERATIVE_APPLY', 'next': 'RASTER_LOAD'}, {'seq': 513, 'prev': 'ITERATIVE_APPLY', 'next': 'AGGREGATION'}, {'seq': 520, 'prev': 'ITERATIVE_APPLY', 'next': 'RASTER_LOAD'}, {'seq': 526, 'prev': 'ITERATIVE_APPLY', 'next': 'RASTER_LOAD'}, {'seq': 532, 'prev': 'ITERATIVE_APPLY', 'next': 'AGGREGATION'}, {'seq': 539, 'prev': 'ITERATIVE_APPLY', 'next': 'RASTER_LOAD'}, {'seq': 545, 'prev': 'ITERATIVE_APPLY', 'next': 'RASTER_LOAD'}, {'seq': 551, 'prev': 'ITERATIVE_APPLY', 'next': 'AGGREGATION'}, {'seq': 558, 'prev': 'ITERATIVE_APPLY', 'next': 'RASTER_LOAD'}, {'seq': 564, 'prev': 'ITERATIVE_APPLY', 'next': 'RASTER_LOAD'}, {'seq': 570, 'prev': 'ITERATIVE_APPLY', 'next': 'AGGREGATION'}, {'seq': 577, 'prev': 'ITERATIVE_APPLY', 'next': 'RASTER_LOAD'}, {'seq': 583, 'prev': 'ITERATIVE_APPLY', 'next': 'RASTER_LOAD'}, {'seq': 589, 'prev': 'ITERATIVE_APPLY', 'next': 'AGGREGATION'}, {'seq': 596, 'prev': 'ITERATIVE_APPLY', 'next': 'RASTER_LOAD'}, {'seq': 602, 'prev': 'ITERATIVE_APPLY', 'next': 'RASTER_LOAD'}, {'seq': 608, 'prev': 'ITERATIVE_APPLY', 'next': 'AGGREGATION'}, {'seq': 615, 'prev': 'ITERATIVE_APPLY', 'next': 'RASTER_LOAD'}, {'seq': 621, 'prev': 'ITERATIVE_APPLY', 'next': 'RASTER_LOAD'}, {'seq': 627, 'prev': 'ITERATIVE_APPLY', 'next': 'AGGREGATION'}, {'seq': 634, 'prev': 'ITERATIVE_APPLY', 'next': 'RASTER_LOAD'}, {'seq': 640, 'prev': 'ITERATIVE_APPLY', 'next': 'RASTER_LOAD'}, {'seq': 646, 'prev': 'ITERATIVE_APPLY', 'next': 'AGGREGATION'}, {'seq': 653, 'prev': 'ITERATIVE_APPLY', 'next': 'RASTER_LOAD'}, {'seq': 659, 'prev': 'ITERATIVE_APPLY', 'next': 'RASTER_LOAD'}, {'seq': 665, 'prev': 'ITERATIVE_APPLY', 'next': 'AGGREGATION'}, {'seq': 672, 'prev': 'ITERATIVE_APPLY', 'next': 'RASTER_LOAD'}, {'seq': 678, 'prev': 'ITERATIVE_APPLY', 'next': 'RASTER_LOAD'}, {'seq': 684, 'prev': 'ITERATIVE_APPLY', 'next': 'AGGREGATION'}, {'seq': 691, 'prev': 'ITERATIVE_APPLY', 'next': 'RASTER_LOAD'}, {'seq': 697, 'prev': 'ITERATIVE_APPLY', 'next': 'RASTER_LOAD'}, {'seq': 703, 'prev': 'ITERATIVE_APPLY', 'next': 'AGGREGATION'}, {'seq': 710, 'prev': 'ITERATIVE_APPLY', 'next': 'RASTER_LOAD'}, {'seq': 716, 'prev': 'ITERATIVE_APPLY', 'next': 'RASTER_LOAD'}, {'seq': 722, 'prev': 'ITERATIVE_APPLY', 'next': 'VECTOR_LOAD'}]
- 下游消费者: （无——isolated）
- owner_ruling: ______（gold_inconsistent / alternative_workflow / clearly_necessary）

## k=1012 — Task: Classify urban and non-urban areas

Task: Classify urban and non-urban areas
Classify urban and non-urban land cover using Landsat 8 surface reflectance data, incorporating NDVI, NDBI, MNDWI, DEM, and slope as input features for a Random Forest classifier, with accuracy assessment performed on test samples.

- gold BAND_SELECT 位置: [{'seq': 3, 'prev': 'RASTER_LOAD', 'next': 'TEMPORAL_FILTER'}]
- 下游消费者: （无——isolated）
- owner_ruling: ______（gold_inconsistent / alternative_workflow / clearly_necessary）

## k=1061 — Task: Analyze NDVI time series

Task: Analyze NDVI time series
Analyze temporal changes in vegetation health across multiple locations in Uzbekistan using NDVI derived from Landsat 5 and Landsat 8 surface reflectance imagery between 1984 and 2019. It computes NDVI for two different sensor configurations (Landsat 5 TM: B4/B3; Landsat 8 OLI: B5/B4), applies no cloud masking beyond fmask usage in function definition (though not applied in final collections), and generates a time-series scatter chart of mean NDVI values per locati

- gold BAND_SELECT 位置: [{'seq': 5, 'prev': 'TEMPORAL_FILTER', 'next': 'ITERATIVE_APPLY'}, {'seq': 11, 'prev': 'TEMPORAL_FILTER', 'next': 'ITERATIVE_APPLY'}, {'seq': 17, 'prev': 'TEMPORAL_FILTER', 'next': 'ITERATIVE_APPLY'}, {'seq': 23, 'prev': 'TEMPORAL_FILTER', 'next': 'ITERATIVE_APPLY'}, {'seq': 29, 'prev': 'TEMPORAL_FILTER', 'next': 'ITERATIVE_APPLY'}, {'seq': 35, 'prev': 'TEMPORAL_FILTER', 'next': 'ITERATIVE_APPLY'}, {'seq': 41, 'prev': 'TEMPORAL_FILTER', 'next': 'ITERATIVE_APPLY'}, {'seq': 47, 'prev': 'TEMPORAL_FILTER', 'next': 'ITERATIVE_APPLY'}, {'seq': 53, 'prev': 'TEMPORAL_FILTER', 'next': 'ITERATIVE_APPLY'}, {'seq': 59, 'prev': 'TEMPORAL_FILTER', 'next': 'ITERATIVE_APPLY'}, {'seq': 65, 'prev': 'TEMPORAL_FILTER', 'next': 'ITERATIVE_APPLY'}, {'seq': 71, 'prev': 'TEMPORAL_FILTER', 'next': 'ITERATIVE_APPLY'}, {'seq': 77, 'prev': 'TEMPORAL_FILTER', 'next': 'ITERATIVE_APPLY'}, {'seq': 83, 'prev': 'TEMPORAL_FILTER', 'next': 'ITERATIVE_APPLY'}, {'seq': 89, 'prev': 'TEMPORAL_FILTER', 'next': 'ITERATIVE_APPLY'}, {'seq': 95, 'prev': 'TEMPORAL_FILTER', 'next': 'ITERATIVE_APPLY'}]
- 下游消费者: （无——isolated）
- owner_ruling: ______（gold_inconsistent / alternative_workflow / clearly_necessary）

## k=1090 — Task: Classify land cover types

Task: Classify land cover types
Classify land cover types in Olavarría using training samples for five classes: Agua, Area_no_vegetada, Cultivos, Lenosas, and Herbacea_natural. It leverages Landsat 8 surface reflectance imagery from 2016 to 2020 and MODIS NDVI data from 2020 to compute NDVI time series. The workflow includes cloud masking, NDVI calculation, and the creation of interactive charts via click events on a map, where users can view temporal NDVI profiles from Landsat and MODIS at spec

- gold BAND_SELECT 位置: [{'seq': 7, 'prev': 'ATTRIBUTE_FILTER', 'next': 'RASTER_LOAD'}, {'seq': 12, 'prev': 'ATTRIBUTE_FILTER', 'next': 'RASTER_LOAD'}, {'seq': 17, 'prev': 'ATTRIBUTE_FILTER', 'next': 'RASTER_LOAD'}]
- 下游消费者: （无——isolated）
- owner_ruling: ______（gold_inconsistent / alternative_workflow / clearly_necessary）

## k=1093 — Task: Analyze NDVI seasonal patterns

Task: Analyze NDVI seasonal patterns
Analyze seasonal patterns of NDVI in the Nuapada district using MODIS MOD13A2 imagery from 2018 to 2019. It groups images by day of year (doy), computes median NDVI for each doy across the time series, visualizes the results as a time-composited RGB animation, and generates a URL for a thumbnail video/gif. The output is a temporally reduced image collection representing median phenological trends.

- gold BAND_SELECT 位置: [{'seq': 2, 'prev': 'RASTER_LOAD', 'next': 'RASTER_LOAD'}]
- 下游消费者: （无——isolated）
- owner_ruling: ______（gold_inconsistent / alternative_workflow / clearly_necessary）

## k=1099 — Task: Generate false color composite video

Task: Generate false color composite video
Create a time-lapse video of false-color composite images from Landsat 5 TOA data over a specific path and row near Henderson, Nevada, using bands B7, B4, and B1, with cloud cover less than 10% between 1991 and 2011, and exports it to Google Drive.

- gold BAND_SELECT 位置: [{'seq': 4, 'prev': 'TEMPORAL_FILTER', 'next': None}]
- 下游消费者: （无——isolated）
- owner_ruling: ______（gold_inconsistent / alternative_workflow / clearly_necessary）

## k=1109 — Task: Classify land cover types

Task: Classify land cover types
Classify land cover in a specific country (ADM0_CODE 133) using Sentinel-2 imagery from 2019 to 2021. It computes NDVI for four seasonal composites (rainy and dry seasons), stacks the bands and indices into a single image, trains a Random Forest classifier on labeled sample points, and generates a classified land cover map with three classes. Accuracy is assessed using a confusion matrix on training data and an error matrix on an independent test set, with overall

- gold BAND_SELECT 位置: [{'seq': 2, 'prev': 'RASTER_LOAD', 'next': 'VECTOR_LOAD'}, {'seq': 8, 'prev': 'TEMPORAL_FILTER', 'next': 'TEMPORAL_FILTER'}]
- 下游消费者: （无——isolated）
- owner_ruling: ______（gold_inconsistent / alternative_workflow / clearly_necessary）

## k=1123 — Task: Classify land cover types

Task: Classify land cover types
Classify land cover types by training a Random Forest model using spectral indices (MVI, EVI, MBI, NDBI, NDWI), Landsat bands, and DEM data, with cloud and region masking applied.

- gold BAND_SELECT 位置: [{'seq': 2, 'prev': 'RASTER_LOAD', 'next': 'SPATIAL_CLIP'}]
- 下游消费者: （无——isolated）
- owner_ruling: ______（gold_inconsistent / alternative_workflow / clearly_necessary）

## k=1138 — Task: Analyze NDMI vegetation moisture

Task: Analyze NDMI vegetation moisture
Analyze vegetation moisture conditions in Thailand using the Normalized Difference Moisture Index (NDMI) derived from Sentinel-2A/B SR surface reflectance data between January and July 2022. It applies cloud masking based on QA60 band, computes NDMI using bands B8 and B11, generates a maximum-value composite of NDMI over time, clips it to Thailand's boundary, and visualizes the result on the map. Additionally, it creates a time series line chart of maximum 

- gold BAND_SELECT 位置: [{'seq': 8, 'prev': 'ATTRIBUTE_FILTER', 'next': 'ITERATIVE_APPLY'}]
- 下游消费者: （无——isolated）
- owner_ruling: ______（gold_inconsistent / alternative_workflow / clearly_necessary）

## k=1142 — Task: Extract ET and PET from MODIS

Task: Extract ET and PET from MODIS
Extract actual evapotranspiration (ET) and potential evapotranspiration (PET) from the MODIS MOD16A2 Version 6 dataset for a specified region and time period, then exports each image in the collection individually to Google Drive as GeoTIFFs.

- gold BAND_SELECT 位置: [{'seq': 2, 'prev': 'RASTER_LOAD', 'next': 'SPATIAL_FILTER'}]
- 下游消费者: （无——isolated）
- owner_ruling: ______（gold_inconsistent / alternative_workflow / clearly_necessary）

## k=1143 — Task: Identify open coal mining areas

Task: Identify open coal mining areas
Identify open coal mining areas using a spectral threshold-based method applied to Landsat surface reflectance imagery from 2000 to 2020. It processes annual image mosaics for each region of interest (from the input table), computes a coal probability index based on SWIR1, SWIR2, and NIR bands, applies a threshold (>=20%) to detect persistent coal-like surfaces, and exports a binary raster map indicating locations of open coal mining activity. The output is 

- gold BAND_SELECT 位置: [{'seq': 3, 'prev': 'RASTER_LOAD', 'next': 'RASTER_LOAD'}]
- 下游消费者: （无——isolated）
- owner_ruling: ______（gold_inconsistent / alternative_workflow / clearly_necessary）

## k=1147 — Task: Analyze NDVI time series for agricultural parcels

Task: Analyze NDVI time series for agricultural parcels
Analyze the temporal variation of NDVI values over specific agricultural parcels (Abraham_S, Benjamin_D, etc.) within the Cuauhtemoc Valley using Sentinel-2 imagery. It computes mean NDVI time series for each parcel and visualizes them as line charts. Additionally, it calculates min and max NDVI composites across the time period and displays the mean NDVI raster clipped to selected parcels.

- gold BAND_SELECT 位置: [{'seq': 4, 'prev': 'RASTER_LOAD', 'next': 'AGGREGATION'}, {'seq': 7, 'prev': 'RASTER_LOAD', 'next': 'AGGREGATION'}]
- 下游消费者: （无——isolated）
- owner_ruling: ______（gold_inconsistent / alternative_workflow / clearly_necessary）

## k=1152 — Task: Estimate mean NDVI

Task: Estimate mean NDVI
Calculate the median Normalized Difference Vegetation Index (NDVI) from Landsat 8 TOA reflectance data over a one-year period (2019). It computes NDVI using bands B5 (NIR) and B4 (Red), then extracts mean NDVI values for each polygon in a feature collection representing administrative wards. The output is a table of ward-level mean NDVI values exported as a CSV file for further analysis.

- gold BAND_SELECT 位置: [{'seq': 3, 'prev': 'TEMPORAL_FILTER', 'next': 'AGGREGATION'}]
- 下游消费者: （无——isolated）
- owner_ruling: ______（gold_inconsistent / alternative_workflow / clearly_necessary）

## k=1153 — Task: Calculate dNBR for burn severity

Task: Calculate dNBR for burn severity
Calculate the differenced Normalized Burn Ratio (dNBR) to assess wildfire burn severity using Landsat surface reflectance imagery from 2022. It computes pre-fire and post-fire NBR using annual composites within HUC-bound regions, derives dNBR and rBRR, applies cloud masking via CFMask, and exports specified bands (e.g., dNBR) as GeoTIFFs to Google Drive per HUC unit and year. The output includes calibrated burn severity rasters for each watershed.

- gold BAND_SELECT 位置: [{'seq': 6, 'prev': 'RASTER_LOAD', 'next': 'RASTER_LOAD'}]
- 下游消费者: （无——isolated）
- owner_ruling: ______（gold_inconsistent / alternative_workflow / clearly_necessary）

## k=1173 — Task: Identify surface water extent

Task: Identify surface water extent
Identify surface water extent in the area defined by 'geometry' using Sentinel-2A/B SR (Surface Reflectance) imagery from January to February 2021. It computes NDWI (Normalized Difference Water Index) using green (B3) and near-infrared (B8) bands, applies a threshold (NDWI ≥ 0.1) to create a water mask, and updates the image mask to retain only water pixels. The resulting water-masked composite is visualized in RGB and exported as a clipped, masked raster to G

- gold BAND_SELECT 位置: [{'seq': 5, 'prev': 'SPATIAL_FILTER', 'next': None}]
- 下游消费者: （无——isolated）
- owner_ruling: ______（gold_inconsistent / alternative_workflow / clearly_necessary）

## k=1176 — Task: Estimate land surface temperature

Task: Estimate land surface temperature
Calculate mean daytime and nighttime land surface temperature (LST) from MODIS MOD11A2 data for Goiania, Brazil, over specific years (1998–2021), converts the values from Kelvin to Celsius, and exports the results as clipped GeoTIFF images to Google Drive for each period.

- gold BAND_SELECT 位置: [{'seq': 4, 'prev': 'SPATIAL_FILTER', 'next': 'RASTER_LOAD'}, {'seq': 8, 'prev': 'SPATIAL_FILTER', 'next': 'RASTER_LOAD'}, {'seq': 12, 'prev': 'SPATIAL_FILTER', 'next': 'RASTER_LOAD'}, {'seq': 16, 'prev': 'SPATIAL_FILTER', 'next': None}]
- 下游消费者: （无——isolated）
- owner_ruling: ______（gold_inconsistent / alternative_workflow / clearly_necessary）

## k=1178 — Task: Extract median Sentinel-2 reflectance

Task: Extract median Sentinel-2 reflectance
Compute the median composite of Sentinel-2 surface reflectance over a specified geometry and time period, using cloud-optimized filtering and band selection. It applies a median reduction across images sorted by descending cloud cover, clips the result to the region of interest, and exports the full-resolution image to Google Drive. The output is a multi-band raster representing median spectral values for selected bands, visualized using B1 (coastal ae

- gold BAND_SELECT 位置: [{'seq': 4, 'prev': 'TEMPORAL_FILTER', 'next': 'COLLECTION_MGMT'}]
- 下游消费者: （无——isolated）
- owner_ruling: ______（gold_inconsistent / alternative_workflow / clearly_necessary）

## k=1179 — Task: Analyze radar backscatter intensity

Task: Analyze radar backscatter intensity
Compute the mean VH polarization backscatter from Sentinel-1 GRD imagery during January to March 2021, masks out image borders and invalid pixels, and visualizes the clipped result over a user-defined polygon. The output is a single composite radar image representing average surface reflectivity in decibels for the specified time period and location.

- gold BAND_SELECT 位置: [{'seq': 3, 'prev': 'ATTRIBUTE_FILTER', 'next': 'ATTRIBUTE_FILTER'}, {'seq': 6, 'prev': 'SPATIAL_FILTER', 'next': None}]
- 下游消费者: （无——isolated）
- owner_ruling: ______（gold_inconsistent / alternative_workflow / clearly_necessary）

## k=1197 — Task: Extract MODIS cloud mask state

Task: Extract MODIS cloud mask state
Process MODIS MOD09GA data to extract and mask cloud conditions using the 'state_1km' band from January 2020 to January 2021, generating a composite mask indicating pixel validity over the region of interest. The output is exported as a uint8 image to Google Drive, where unmasked values represent clear observations and masked values (set to 255) indicate cloudy or invalid pixels.

- gold BAND_SELECT 位置: [{'seq': 4, 'prev': 'ATTRIBUTE_FILTER', 'next': None}]
- 下游消费者: （无——isolated）
- owner_ruling: ______（gold_inconsistent / alternative_workflow / clearly_necessary）

## k=1198 — Task: Analyze NDVI over time

Task: Analyze NDVI over time
Calculate NDVI values from Sentinel-2 surface reflectance data over a user-defined AOI between December 2021 and April 2022, generates a mean NDVI image for the period, visualizes it on the map, exports it to Google Drive, and creates a time series chart of mean NDVI values within the AOI.

- gold BAND_SELECT 位置: [{'seq': 3, 'prev': 'TEMPORAL_FILTER', 'next': 'SPATIAL_FILTER'}]
- 下游消费者: （无——isolated）
- owner_ruling: ______（gold_inconsistent / alternative_workflow / clearly_necessary）

## k=1220 — Task: Calculate NDVI climatological anomaly

Task: Calculate NDVI climatological anomaly
Compute a pixel-wise NDVI anomaly map for Ireland by subtracting a 10-year (2015–2024) historical mean NDVI climatology — derived from VIIRS VNP13A1 data — from the most recent annual NDVI composite (2024). It outputs three visualizable layers (historical mean, current NDVI, and anomaly), with the anomaly layer explicitly interpreted as a vegetation stress/health indicator: negative values indicate below-average greenness (drought or biotic stress), po

- gold BAND_SELECT 位置: [{'seq': 7, 'prev': 'TEMPORAL_FILTER', 'next': 'COLLECTION_MGMT'}]
- 下游消费者: （无——isolated）
- owner_ruling: ______（gold_inconsistent / alternative_workflow / clearly_necessary）

## k=1222 — Task: Extract mean air temperature

Task: Extract mean air temperature
Calculate the median daily mean 2-meter air temperature from ERA5 for a single day (2019-02-01 to 2019-02-02). It filters the ERA5 daily dataset to this date range, computes the median value, clips it to a user-defined region of interest (roi), visualizes it with a custom color palette, and exports the clipped image to Google Drive. It also computes and prints the minimum and maximum temperature values within the roi using reduceRegion.

- gold BAND_SELECT 位置: [{'seq': 2, 'prev': 'RASTER_LOAD', 'next': 'TEMPORAL_FILTER'}]
- 下游消费者: （无——isolated）
- owner_ruling: ______（gold_inconsistent / alternative_workflow / clearly_necessary）

## k=1236 — Task: Analyze NDVI for restoration projects

Task: Analyze NDVI for restoration projects
Calculate NDVI from Sentinel-2 imagery between July and September 2022 over a region of interest to monitor vegetation health, then extracts mean NDVI values within polygon features representing restoration projects, generating a chart of these values and visualizing one specific project area at high resolution.

- gold BAND_SELECT 位置: [{'seq': 5, 'prev': 'ATTRIBUTE_FILTER', 'next': 'AGGREGATION'}]
- 下游消费者: （无——isolated）
- owner_ruling: ______（gold_inconsistent / alternative_workflow / clearly_necessary）

## k=1239 — Task: Analyze soil moisture levels

Task: Analyze soil moisture levels
Analyze surface soil moisture over the Thandla region using SMAP 10 km resolution data from May to November 2021. It computes the mean soil moisture (susm band) across the time period, clips it to the Thandla boundary, and visualizes the result on the map with a custom palette. Additionally, it generates a time series chart of average soil moisture values for the region, showing temporal variations at ~25km scale, and prints the chart for analysis.

- gold BAND_SELECT 位置: [{'seq': 2, 'prev': 'RASTER_LOAD', 'next': 'SPATIAL_FILTER'}]
- 下游消费者: （无——isolated）
- owner_ruling: ______（gold_inconsistent / alternative_workflow / clearly_necessary）

## k=1245 — Task: Analyze NDVI time series

Task: Analyze NDVI time series
Compute a monthly maximum NDVI time series from Sentinel-2 imagery over a specified region and period (2015–2019). It applies cloud masking using the QA60 band to filter clouds and cirrus, calculates NDVI using bands B8 and B4, aggregates the data monthly by taking the maximum NDVI value per month, and generates a multiband image where each band represents the maximum NDVI of a specific month. Finally, it produces a scatter chart showing the mean NDVI over time for

- gold BAND_SELECT 位置: [{'seq': 4, 'prev': 'RASTER_LOAD', 'next': 'RASTER_LOAD'}, {'seq': 6, 'prev': 'RASTER_LOAD', 'next': 'RASTER_LOAD'}]
- 下游消费者: （无——isolated）
- owner_ruling: ______（gold_inconsistent / alternative_workflow / clearly_necessary）

## k=1261 — Task: Classify land cover in Ruvuma

Task: Classify land cover in Ruvuma
Classify land cover in the Ruvuma region using a Random Forest classifier trained on a multi-source data stack derived from Sentinel-2, Sentinel-1, and SRTM. It computes vegetation and water indices (NDVI, NDWI, NDWBI, mNDWBI) and spectral ratios from Sentinel-2, combines them with terrain (elevation, slope) and dual-polarization SAR (VV, VH) composites from Sentinel-1, then samples training and validation datasets based on labeled regions. The resulting class

- gold BAND_SELECT 位置: [{'seq': 5, 'prev': 'AGGREGATION', 'next': 'CLASSIFICATION'}]
- 下游消费者: （无——isolated）
- owner_ruling: ______（gold_inconsistent / alternative_workflow / clearly_necessary）

## k=1268 — Task: Detect surface moisture changes

Task: Detect surface moisture changes
Analyze temporal changes in surface moisture conditions using Sentinel-1 C-band VV backscatter. It computes the mean VV polarization intensity during two distinct periods: a wet period (2022-01-22 to 2022-01-24) and a dry period (2022-01-10 to 2022-01-20). The difference image (T2 - T1) highlights areas of increased or decreased backscatter, interpreted as changes in surface wetness. A false-color RGB composite is generated using dry (Red), green-season (Gre

- gold BAND_SELECT 位置: [{'seq': 5, 'prev': 'ATTRIBUTE_FILTER', 'next': 'RASTER_LOAD'}, {'seq': 10, 'prev': 'ATTRIBUTE_FILTER', 'next': 'RASTER_LOAD'}, {'seq': 15, 'prev': 'ATTRIBUTE_FILTER', 'next': None}]
- 下游消费者: （无——isolated）
- owner_ruling: ______（gold_inconsistent / alternative_workflow / clearly_necessary）

## k=1275 — Task: Generate annual surface water and vegetation indices mosaic

Task: Generate annual surface water and vegetation indices mosaic
Generate an annual cloud-masked median composite mosaic from Landsat TOA surface reflectance imagery (L5, L7, L8, L9) over a continental-scale South American region (approx. -75.5°W to -32.9°W, 6.6°N to -34.6°S). It computes five spectral indices—NDVI (vegetation health), MNDWI (surface water), NDSI (snow/ice), NDWI (water body detection), and MMRI (water-vegetation discrimination)—applies QA-based cloud/shadow/dilated cloud maski

- gold BAND_SELECT 位置: [{'seq': 4, 'prev': 'SPATIAL_FILTER', 'next': 'RASTER_LOAD'}, {'seq': 8, 'prev': 'SPATIAL_FILTER', 'next': 'RASTER_LOAD'}, {'seq': 12, 'prev': 'SPATIAL_FILTER', 'next': 'RASTER_LOAD'}, {'seq': 16, 'prev': 'SPATIAL_FILTER', 'next': 'RASTER_LOAD'}]
- 下游消费者: （无——isolated）
- owner_ruling: ______（gold_inconsistent / alternative_workflow / clearly_necessary）

## k=1277 — Task: Generate cloud-masked Sentinel-2 composite

Task: Generate cloud-masked Sentinel-2 composite
Generate a median cloud-masked surface reflectance composite from Sentinel-2 MSI imagery over a user-defined geometry for the year 2018. It applies QA60-based cloud and cirrus masking, filters images below 20% cloud cover, selects all spectral bands (B.*), computes the median value per pixel, clips to the study area, and visualizes the result as an RGB image (B4, B3, B2). The output is exported to Google Drive as a GeoTIFF file for further use.

- gold BAND_SELECT 位置: [{'seq': 7, 'prev': 'ITERATIVE_APPLY', 'next': 'AGGREGATION'}]
- 下游消费者: （无——isolated）
- owner_ruling: ______（gold_inconsistent / alternative_workflow / clearly_necessary）

## k=1284 — Task: Classify agricultural land cover

Task: Classify agricultural land cover
Classify land cover types, particularly agricultural crops (e.g., maize, soybean, sorghum, potato) and natural vegetation, using multi-temporal Sentinel-2 spectral indices and Sentinel-1 radar data over a specific region in Bolivia. It generates a classified map, evaluates accuracy with a confusion matrix, and exports training/testing samples and the final classified image.

- gold BAND_SELECT 位置: [{'seq': 4, 'prev': 'TEMPORAL_FILTER', 'next': 'RASTER_LOAD'}, {'seq': 8, 'prev': 'TEMPORAL_FILTER', 'next': 'RASTER_LOAD'}, {'seq': 12, 'prev': 'TEMPORAL_FILTER', 'next': 'RASTER_LOAD'}, {'seq': 16, 'prev': 'TEMPORAL_FILTER', 'next': 'RASTER_LOAD'}, {'seq': 20, 'prev': 'TEMPORAL_FILTER', 'next': 'RASTER_LOAD'}, {'seq': 24, 'prev': 'TEMPORAL_FILTER', 'next': 'RASTER_LOAD'}, {'seq': 28, 'prev': 'TEMPORAL_FILTER', 'next': 'RASTER_LOAD'}, {'seq': 32, 'prev': 'TEMPORAL_FILTER', 'next': 'RASTER_LOAD'}, {'seq': 35, 'prev': 'ATTRIBUTE_FILTER', 'next': 'ATTRIBUTE_FILTER'}]
- 下游消费者: （无——isolated）
- owner_ruling: ______（gold_inconsistent / alternative_workflow / clearly_necessary）

## k=1290 — Task: Classify land cover types

Task: Classify land cover types
Classify land cover types for 2018 and 2019 using Landsat 7 surface reflectance data and a Random Forest classifier trained on stratified samples based on MODIS LC_Type4. It generates classified maps, evaluates accuracy using training and test samples, and compares results across years with visualization of histograms for predicted land cover distributions.

- gold BAND_SELECT 位置: [{'seq': 5, 'prev': 'ITERATIVE_APPLY', 'next': 'RASTER_LOAD'}, {'seq': 8, 'prev': 'TEMPORAL_FILTER', 'next': 'AGGREGATION'}]
- 下游消费者: （无——isolated）
- owner_ruling: ______（gold_inconsistent / alternative_workflow / clearly_necessary）

## k=1292 — Task: Analyze forest NBR change

Task: Analyze forest NBR change
Analyze changes in the Normalized Burn Ratio (NBR) over forested areas in Europe before and after a fire event by using MODIS MCD43A4 surface reflectance data from 2005 to 2012, masked with CORINE Land Cover data to retain only forest areas (class values >=24). It computes mean NBR for pre-fire (2006), fire-year (2007), and post-fire (2011–2012) periods, then generates a time series chart of regional mean NBR values over Europe.

- gold BAND_SELECT 位置: [{'seq': 5, 'prev': 'ITERATIVE_APPLY', 'next': 'AGGREGATION'}, {'seq': 11, 'prev': 'ITERATIVE_APPLY', 'next': 'AGGREGATION'}, {'seq': 19, 'prev': 'ITERATIVE_APPLY', 'next': 'AGGREGATION'}, {'seq': 25, 'prev': 'ITERATIVE_APPLY', 'next': 'ITERATIVE_APPLY'}, {'seq': 31, 'prev': 'ITERATIVE_APPLY', 'next': 'ITERATIVE_APPLY'}, {'seq': 37, 'prev': 'ITERATIVE_APPLY', 'next': 'ITERATIVE_APPLY'}, {'seq': 43, 'prev': 'ITERATIVE_APPLY', 'next': 'ITERATIVE_APPLY'}, {'seq': 49, 'prev': 'ITERATIVE_APPLY', 'next': 'RASTER_LOAD'}]
- 下游消费者: （无——isolated）
- owner_ruling: ______（gold_inconsistent / alternative_workflow / clearly_necessary）

## k=1310 — Task: Extract weekly maximum temperature

Task: Extract weekly maximum temperature
Extract weekly maximum temperature (tmax) from the PRISM AN81d dataset for the period from March 28, 2021, to December 1, 2021, clips it to a user-defined region ('table'), and exports each weekly image to Google Drive with filenames formatted by start date.

- gold BAND_SELECT 位置: [{'seq': 2, 'prev': 'RASTER_LOAD', 'next': 'TEMPORAL_FILTER'}]
- 下游消费者: （无——isolated）
- owner_ruling: ______（gold_inconsistent / alternative_workflow / clearly_necessary）

## k=1321 — Task: Classify land cover types

Task: Classify land cover types
Classify land cover types in Kilwa using Sentinel-2 and Sentinel-1 satellite imagery from 2018. It generates a median cloud-masked composite of Sentinel-2, computes spectral indices (NDVI, NDWI, NDWBI, mNDWBI) and band ratios, integrates SRTM DEM and Sentinel-1 VV backscatter, then applies a Random Forest classifier trained on 559 labeled points to produce a land cover map. The output includes the classified raster, accuracy assessment (confusion matrix, overall a

- gold BAND_SELECT 位置: [{'seq': 6, 'prev': 'SPATIAL_FILTER', 'next': 'AGGREGATION'}]
- 下游消费者: （无——isolated）
- owner_ruling: ______（gold_inconsistent / alternative_workflow / clearly_necessary）

## k=1334 — Task: Identify forest and water persistence

Task: Identify forest and water persistence
Analyze annual land cover classifications from MapBiomas to identify persistent forest and water areas between 2000 and 2018. It extracts forest classes (codes 3–6) and water classes (codes 26, 33), computes multi-year persistence using a three-year moving window for forest and cumulative sum for water, then generates binary masks indicating areas with at least three years of continuous forest cover or any occurrence of water. The final output is a com

- gold BAND_SELECT 位置: [{'seq': 4, 'prev': 'AGGREGATION', 'next': 'RASTER_LOAD'}]
- 下游消费者: （无——isolated）
- owner_ruling: ______（gold_inconsistent / alternative_workflow / clearly_necessary）

## k=1375 — Task: Classify land cover using S1 and S2

Task: Classify land cover using S1 and S2
Classify land use and land cover (LULC) in Indiana using Sentinel-1 (radar VH polarization) and Sentinel-2 (optical bands and NDVI) time-series data. It first creates a composite of multi-temporal SAR and optical imagery, then trains a Random Forest classifier on labeled training data (Table1) to generate an LULC map. The classification is applied to the full composite, and histograms are generated for analysis. Additionally, unsupervised clustering (K-m

- gold BAND_SELECT 位置: [{'seq': 15, 'prev': 'ATTRIBUTE_FILTER', 'next': 'CLASSIFICATION'}]
- 下游消费者: （无——isolated）
- owner_ruling: ______（gold_inconsistent / alternative_workflow / clearly_necessary）

## k=1377 — Task: Analyze vegetation health using NDVI

Task: Analyze vegetation health using NDVI
Compute the Normalized Difference Vegetation Index (NDVI) from Sentinel-2A/B surface reflectance data between November 22, 2019, and January 22, 2020, to assess vegetation health. It applies cloud masking using the QA60 band, filters images by cloud cover, and calculates the median composite. The output includes a visualized RGB layer and an exported NDVI image clipped to a user-defined geometry.

- gold BAND_SELECT 位置: [{'seq': 5, 'prev': 'ITERATIVE_APPLY', 'next': 'SPATIAL_FILTER'}]
- 下游消费者: （无——isolated）
- owner_ruling: ______（gold_inconsistent / alternative_workflow / clearly_necessary）

## k=1387 — Task: Detect flooding changes

Task: Detect flooding changes
Detect changes in surface water extent by comparing two Sentinel-1 SAR images acquired before and after a potential flood event, using VV polarization to identify flooded areas, with non-water areas masked out using a global water dataset.

- gold BAND_SELECT 位置: [{'seq': 4, 'prev': 'ATTRIBUTE_FILTER', 'next': 'RASTER_LOAD'}, {'seq': 8, 'prev': 'ATTRIBUTE_FILTER', 'next': 'RASTER_LOAD'}, {'seq': 10, 'prev': 'RASTER_LOAD', 'next': 'AGGREGATION'}]
- 下游消费者: （无——isolated）
- owner_ruling: ______（gold_inconsistent / alternative_workflow / clearly_necessary）

## k=1388 — Task: Assess wildfire impact using NDVI

Task: Assess wildfire impact using NDVI
the workflow assesses the impact of a wildfire by computing and comparing NDVI from Landsat 9 imagery before and after the event in summer 2022. It creates median pre- and post-fire NDVI composites, calculates a difference NDVI image (dNDVI), and generates a time series chart of NDVI trends over user-defined regions (poligonos). Outputs include mapped layers for visualization, a scatter chart of NDVI temporal dynamics, and exports individual images and a s

- gold BAND_SELECT 位置: [{'seq': 11, 'prev': 'ITERATIVE_APPLY', 'next': 'RASTER_LOAD'}, {'seq': 17, 'prev': 'ITERATIVE_APPLY', 'next': 'AGGREGATION'}]
- 下游消费者: （无——isolated）
- owner_ruling: ______（gold_inconsistent / alternative_workflow / clearly_necessary）

## k=1407 — Task: Analyze MODIS surface reflectance distribution

Task: Analyze MODIS surface reflectance distribution
Compute the mean surface reflectance values for red, near-infrared, and shortwave infrared bands from MODIS MOD09A1 over a specific region and time period, then generates a histogram chart to visualize the frequency distribution of reflectance values for each band.

- gold BAND_SELECT 位置: [{'seq': 4, 'prev': 'ATTRIBUTE_FILTER', 'next': None}]
- 下游消费者: （无——isolated）
- owner_ruling: ______（gold_inconsistent / alternative_workflow / clearly_necessary）

## k=1420 — Task: Classify cropland areas using satellite imagery

Task: Classify cropland areas using satellite imagery
the workflow performs land use/land cover classification using Sentinel-2 surface reflectance data from 2021, specifically identifying croplands within a region of interest. It first classifies land cover into five classes (water, urban, forest, road, croplands) using a Random Forest classifier trained on labeled samples. Then, it masks for cropland areas and conducts a time-series analysis of NDVI and Sentinel-1 SAR (VV/VH) data from April t

- gold BAND_SELECT 位置: [{'seq': 11, 'prev': 'RASTER_LOAD', 'next': 'RASTER_LOAD'}, {'seq': 13, 'prev': 'RASTER_LOAD', 'next': 'RASTER_LOAD'}]
- 下游消费者: （无——isolated）
- owner_ruling: ______（gold_inconsistent / alternative_workflow / clearly_necessary）

## k=1422 — Task: Identify urban and agricultural areas

Task: Identify urban and agricultural areas
Identify urban and agricultural land cover areas using Copernicus Land Cover data, then analyzes clay index from Sentinel-2 imagery within those areas by masking for clouds and water using NDWI, and generates vector polygons representing median clay values in the region of interest.

- gold BAND_SELECT 位置: [{'seq': 5, 'prev': 'RASTER_LOAD', 'next': 'SPATIAL_FILTER'}, {'seq': 7, 'prev': 'SPATIAL_FILTER', 'next': None}]
- 下游消费者: （无——isolated）
- owner_ruling: ______（gold_inconsistent / alternative_workflow / clearly_necessary）

## k=1433 — Task: Extract slope min max

Task: Extract slope min max
Compute NDVI and NDWI from Landsat 8 TOA reflectance data over a specified region in China during March to November 2016. It also derives slope from SRTM digital elevation data and calculates zonal statistics (mean for NDVI/NDWI, min and max for slope) over a feature collection of regions. The outputs are four CSV files exported to Google Drive containing mean NDVI, mean NDWI, minimum slope, and maximum slope values per region for further analysis.

- gold BAND_SELECT 位置: [{'seq': 3, 'prev': 'TEMPORAL_FILTER', 'next': 'AGGREGATION'}]
- 下游消费者: （无——isolated）
- owner_ruling: ______（gold_inconsistent / alternative_workflow / clearly_necessary）

## k=1442 — Task: Map land surface reflectance

Task: Map land surface reflectance
Generate a median composite of Sentinel-2 surface reflectance imagery for Al Nairyah, masked for clouds and clipped to the region, using data from January to May 2023. The output is a false-color image (B5, B4, B3) visualizing land surface characteristics and is exported to Google Drive.

- gold BAND_SELECT 位置: [{'seq': 6, 'prev': 'ITERATIVE_APPLY', 'next': None}]
- 下游消费者: （无——isolated）
- owner_ruling: ______（gold_inconsistent / alternative_workflow / clearly_necessary）

## k=1445 — Task: Monitor HCP vegetation and cropland

Task: Monitor HCP vegetation and cropland
the workflow enables the United States Fish and Wildlife Service (USFWS) to monitor Habitat Conservation Plan (HCP) areas by allowing users to select an HCP from a dropdown menu and visualize land cover using USDA Cropland Data Layer (CDL) for 2008. It centers the map on the selected HCP feature, displays it as a blue polygon layer, and overlays classified cropland data clipped to the HCP boundary with a detailed SLD-based color scheme representing crop 

- gold BAND_SELECT 位置: [{'seq': 4, 'prev': 'RASTER_LOAD', 'next': None}]
- 下游消费者: （无——isolated）
- owner_ruling: ______（gold_inconsistent / alternative_workflow / clearly_necessary）

## k=1448 — Task: Analyze monthly maximum kNDVI

Task: Analyze monthly maximum kNDVI
Compute a time series of monthly maximum kNDVI (kernel NDVI) from MODIS MOD13Q1 data between 2005 and 2020, applies a tanh-transformed NDVI scaling, and visualizes both the individual monthly composites and their long-term mean over a user-defined region. It also generates a chart of the monthly maximum NDVI time series and clips outputs to the input geometry.

- gold BAND_SELECT 位置: [{'seq': 4, 'prev': 'ATTRIBUTE_FILTER', 'next': 'TEMPORAL_FILTER'}]
- 下游消费者: （无——isolated）
- owner_ruling: ______（gold_inconsistent / alternative_workflow / clearly_necessary）

## k=1460 — Task: Analyze NDVI in study area

Task: Analyze NDVI in study area
Analyze vegetation health in a specific administrative district (Amphoe) in Thailand using Sentinel-2 satellite imagery from August 2021. It computes the Normalized Difference Vegetation Index (NDVI) by applying the formula (NIR - Red) / (NIR + Red) using bands B8 and B4, clips the result to the study area derived from FAO GAUL level2 boundaries, and visualizes it with a color palette. Additionally, it generates a time series chart of mean surface reflectance val

- gold BAND_SELECT 位置: [{'seq': 9, 'prev': 'SPATIAL_FILTER', 'next': 'ATTRIBUTE_FILTER'}]
- 下游消费者: （无——isolated）
- owner_ruling: ______（gold_inconsistent / alternative_workflow / clearly_necessary）

## k=1465 — Task: Detect deforestation using Sentinel-1 VH backscatter change

Task: Detect deforestation using Sentinel-1 VH backscatter change
Detect tropical or temperate forest loss between 2015 and 2024 using dual-polarization (VV/VH) Sentinel-1 GRD SAR imagery. It computes a pre-deforestation VH reference (2015), a post-deforestation VH image (2024), applies two thresholds — forest presence (VH > −12 dB in 2015) and significant decline (ΔVH > 3 dB) — to generate a binary deforestation mask, calculates the total deforested area in hectares within the ROI, and visualiz

- gold BAND_SELECT 位置: [{'seq': 5, 'prev': 'ATTRIBUTE_FILTER', 'next': 'RASTER_LOAD'}]
- 下游消费者: （无——isolated）
- owner_ruling: ______（gold_inconsistent / alternative_workflow / clearly_necessary）

## k=1469 — Task: Analyze Kabul City LST trends

Task: Analyze Kabul City LST trends
Analyze land surface temperature (LST) patterns in Kabul City using MODIS MOD11A2 data from 2000 to 2019. It processes both daytime and nighttime LST bands by scaling pixel values (multiplying by 0.02) and converting from Kelvin to Celsius. The workflow includes filtering the image collection by region and time, computing mean temperatures over the study area, and generating a time series chart comparing day and night LST. Two charts are created: one for gener

- gold BAND_SELECT 位置: [{'seq': 4, 'prev': 'TEMPORAL_FILTER', 'next': 'AGGREGATION'}, {'seq': 10, 'prev': 'TEMPORAL_FILTER', 'next': 'AGGREGATION'}]
- 下游消费者: （无——isolated）
- owner_ruling: ______（gold_inconsistent / alternative_workflow / clearly_necessary）

## k=1475 — Task: Classify land cover using optical and radar data

Task: Classify land cover using optical and radar data
Classify land cover in the Niayes region using a combination of Landsat 8 surface reflectance, Sentinel-1 SAR, and derived spectral indices (NDVI, NDWI). It applies cloud masking to Landsat and Sentinel-2-like QA60-based masking (though not used), computes NDVI and NDWI, fuses optical, radar, and index bands, and performs Random Forest classification using training samples. Three classifications are generated: (1) using only Landsat spectral

- gold BAND_SELECT 位置: [{'seq': 2, 'prev': 'RASTER_LOAD', 'next': 'RASTER_LOAD'}]
- 下游消费者: （无——isolated）
- owner_ruling: ______（gold_inconsistent / alternative_workflow / clearly_necessary）

## k=1483 — Task: Extract NDVI time series for sites

Task: Extract NDVI time series for sites
Extract NDVI time series from Sentinel-2 TOA reflectance imagery over specific field sites (DPM) using cloud-masked data. It applies a custom cloud masking algorithm (S2CloudRemvAlg1), computes NDVI using bands B8 and B4, and generates a line chart of NDVI values over time for each site. Additionally, it labels the sites on the map and exports per-image NDVI values at specific locations via reduceRegions. Outputs include a labeled map of sites, an interac

- gold BAND_SELECT 位置: [{'seq': 6, 'prev': 'RASTER_LOAD', 'next': 'AGGREGATION'}]
- 下游消费者: （无——isolated）
- owner_ruling: ______（gold_inconsistent / alternative_workflow / clearly_necessary）

## k=1493 — Task: Extract precipitation data

Task: Extract precipitation data
Extract monthly TRMM precipitation data from the 'precipitation' band within a specified date range and geographic region, clips it to the region of interest, and exports each image in the collection to Google Drive.

- gold BAND_SELECT 位置: [{'seq': 4, 'prev': 'TEMPORAL_FILTER', 'next': None}]
- 下游消费者: （无——isolated）
- owner_ruling: ______（gold_inconsistent / alternative_workflow / clearly_necessary）

## k=1496 — Task: Identify least cloudy Landsat image

Task: Identify least cloudy Landsat image
Identify the least cloudy Landsat 8 image from a specific WRS path and row by sorting the image collection based on the 'LAND_COVER' metadata property and selecting the first (least cloudy) image. It visualizes this image in true color and generates a time series chart of mean spectral values within a 500-meter buffer around a sample point, using a 30-meter scale. Outputs include the selected image, a true-color visualization, a sample point overlay, and

- gold BAND_SELECT 位置: [{'seq': 2, 'prev': 'RASTER_LOAD', 'next': 'ATTRIBUTE_FILTER'}]
- 下游消费者: （无——isolated）
- owner_ruling: ______（gold_inconsistent / alternative_workflow / clearly_necessary）

## k=1499 — Task: Analyze B4 vs B6/B5 ratio

Task: Analyze B4 vs B6/B5 ratio
Generate a scatter plot of Landsat 8 TOA band 4 (red) values against the ratio of bands 6 and 5 (SWIR1 and NIR) for pixels within San Francisco, visualizing spectral relationships in the urban landscape.

- gold BAND_SELECT 位置: [{'seq': 2, 'prev': 'RASTER_LOAD', 'next': 'RASTER_LOAD'}]
- 下游消费者: （无——isolated）
- owner_ruling: ______（gold_inconsistent / alternative_workflow / clearly_necessary）

## k=1539 — Task: Classify land cover types

Task: Classify land cover types
Classify land cover into four classes—water, urban, and two vegetation types—using Sentinel-2 surface reflectance data and a Random Forest classifier trained on user-defined feature collections. The output is a classified raster map with distinct color-coded land cover categories and an accuracy assessment via confusion matrix.

- gold BAND_SELECT 位置: [{'seq': 6, 'prev': 'SPATIAL_FILTER', 'next': 'CLASSIFICATION'}]
- 下游消费者: （无——isolated）
- owner_ruling: ______（gold_inconsistent / alternative_workflow / clearly_necessary）

## k=1543 — Task: View near real-time flood and crop conditions

Task: View near real-time flood and crop conditions
the workflow provides an interactive tool for visual inspection of near real-time satellite imagery to support flood response and crop monitoring. It enables users to draw an area of interest, filter images by date range, and overlay multiple satellite datasets (Sentinel-1, Sentinel-2, Sentinel-3, Landsat-8, NAIP) with different visualizations (true/false color, SAR) to assess surface conditions.

- gold BAND_SELECT 位置: [{'seq': 4, 'prev': 'ATTRIBUTE_FILTER', 'next': 'ITERATIVE_APPLY'}, {'seq': 11, 'prev': 'ATTRIBUTE_FILTER', 'next': 'ITERATIVE_APPLY'}]
- 下游消费者: （无——isolated）
- owner_ruling: ______（gold_inconsistent / alternative_workflow / clearly_necessary）

## k=1558 — Task: Extract and visualize S2 NDVI images

Task: Extract and visualize S2 NDVI images
Process Sentinel-2 imagery from April 2020 to compute and export NDVI visualizations for multiple dates, focusing on cloud-masked, surface-reflectance images clipped to a specific region. The outputs are false-color NDVI images exported to Google Drive.

- gold BAND_SELECT 位置: [{'seq': 4, 'prev': 'ATTRIBUTE_FILTER', 'next': 'SPATIAL_FILTER'}]
- 下游消费者: （无——isolated）
- owner_ruling: ______（gold_inconsistent / alternative_workflow / clearly_necessary）

## k=1576 — Task: Analyze NDVI and EVI time series

Task: Analyze NDVI and EVI time series
Analyze temporal patterns of NDVI and EVI vegetation indices over a user-defined region using MODIS MOD13A1 data from 2017 to 2022. It generates a time-series chart of mean index values, creates animated thumbnails with date overlays for NDVI and EVI separately, and exports a CSV table of the monthly reduced values. The workflow includes image collection filtering, scaling of pixel values, region-based reduction, visualization with custom palettes, and inte

- gold BAND_SELECT 位置: [{'seq': 4, 'prev': 'ATTRIBUTE_FILTER', 'next': 'AGGREGATION'}]
- 下游消费者: （无——isolated）
- owner_ruling: ______（gold_inconsistent / alternative_workflow / clearly_necessary）

## k=1578 — Task: Compute NDVI from Landsat bands

Task: Compute NDVI from Landsat bands
Calculate NDVI using near-infrared (B8) and red (B4) bands from surface-reflectance-corrected Landsat 8 TOA imagery collected between July 15 and October 15, 2021, over a user-defined region. It first composites the image collection by computing the mean, clips it to the study area, then computes NDVI as (NIR - Red) / (NIR + Red). The output includes a true-color RGB visualization layer and a false-color NDVI map with a divergent color palette ranging from r

- gold BAND_SELECT 位置: [{'seq': 4, 'prev': 'SPATIAL_FILTER', 'next': None}]
- 下游消费者: （无——isolated）
- owner_ruling: ______（gold_inconsistent / alternative_workflow / clearly_necessary）

## k=1608 — Task: Analyze vegetation and land cover temporal patterns

Task: Analyze vegetation and land cover temporal patterns
Analyze temporal patterns of multiple vegetation and land surface indices (NDVI, LSWI, EVI, NBR, etc.) and spectral bands across different land cover types (cropland, forest, tea plantations, etc.) in Xishuangbanna, Yunnan, using Landsat 8 and Landsat 7 data from 2018 to 2020. It generates day-of-year composite charts for each index and band, aggregated by region, to compare seasonal dynamics across land cover classes.

- gold BAND_SELECT 位置: [{'seq': 7, 'prev': 'AGGREGATION', 'next': 'GEOMETRY_DEFINE'}]
- 下游消费者: （无——isolated）
- owner_ruling: ______（gold_inconsistent / alternative_workflow / clearly_necessary）

## k=1615 — Task: Analyze LAI time series

Task: Analyze LAI time series
Analyze the Leaf Area Index (LAI) over Singburi Province using MODIS MCD15A3H data from 2019 to 2022. It filters the LAI image collection by date and region, computes the mean LAI image clipped to the province boundary, visualizes it on the map with a custom color palette, and generates a time series chart of mean LAI values extracted from the region. The outputs include a mapped LAI layer and an interactive chart showing temporal variation in LAI.

- gold BAND_SELECT 位置: [{'seq': 5, 'prev': 'ATTRIBUTE_FILTER', 'next': 'AGGREGATION'}]
- 下游消费者: （无——isolated）
- owner_ruling: ______（gold_inconsistent / alternative_workflow / clearly_necessary）

## k=1630 — Task: Identify land cover clusters

Task: Identify land cover clusters
the workflow segments Sentinel-2 surface reflectance imagery over a user-defined region of interest (initially set to 'congzuo' in Guangxi) using the SNIC (Simple Non-Iterative Clustering) superpixel algorithm. It first applies cloud masking and scaling to the image collection, computes a median composite for 2019, then clips a precomputed UNVI index (Urban Normalized Vegetation Index) to the ROI. The SNIC algorithm generates homogeneous spectral-spatial cluste

- gold BAND_SELECT 位置: [{'seq': 7, 'prev': 'ITERATIVE_APPLY', 'next': 'AGGREGATION'}]
- 下游消费者: （无——isolated）
- owner_ruling: ______（gold_inconsistent / alternative_workflow / clearly_necessary）

## k=1631 — Task: Model projected January temperatures

Task: Model projected January temperatures
Analyze future daily maximum near-surface air temperature in the San Joaquin watershed using NASA NEX-DCP30 climate model ensemble data. It filters for January months and RCP scenarios (2.6 and 8.5), converts Kelvin to Celsius, labels bands by scenario, and generates a time-series line chart showing median values with interquartile ranges. Additionally, it visualizes the median temperature for a specific year (2050) using a styled raster map over the re

- gold BAND_SELECT 位置: [{'seq': 2, 'prev': 'RASTER_LOAD', 'next': 'TEMPORAL_FILTER'}]
- 下游消费者: （无——isolated）
- owner_ruling: ______（gold_inconsistent / alternative_workflow / clearly_necessary）

## k=1635 — Task: Generate seasonal vegetation composite

Task: Generate seasonal vegetation composite
Generate a multi-season composite image by computing median values of Landsat 8 TOA reflectance and multiple vegetation and moisture indices (NDVI, EVI, RVI, DVI, NDWI, NDBI, SAVI, NDGI) across four seasonal periods in 2019–2020. It masks cloud-contaminated pixels, applies terrain variables (elevation, slope, aspect) from SRTM, and composites seasonal medians into a final 4-season stacked image (winter, autumn, spring, summer) clipped to a study area,

- gold BAND_SELECT 位置: [{'seq': 6, 'prev': 'ITERATIVE_APPLY', 'next': None}]
- 下游消费者: （无——isolated）
- owner_ruling: ______（gold_inconsistent / alternative_workflow / clearly_necessary）

## k=1662 — Task: Compute mean sea surface temperature

Task: Compute mean sea surface temperature
Calculate the mean sea surface temperature (SST) during the Northeast Monsoon period from December 2019 to February 2020 by processing MODIS-Aqua L3SMI data, filtering for the specified time range, reducing the image collection to a single mean composite, and exporting the result.

- gold BAND_SELECT 位置: [{'seq': 2, 'prev': 'RASTER_LOAD', 'next': 'SPATIAL_FILTER'}]
- 下游消费者: （无——isolated）
- owner_ruling: ______（gold_inconsistent / alternative_workflow / clearly_necessary）

## k=1670 — Task: Analyze NDVI time series

Task: Analyze NDVI time series
Analyze the MODIS NDVI time series at a specific point of interest in California, applies cloud masking using the SummaryQA band, and generates a scatter chart of NDVI values over time. It further performs temporal smoothing by joining each image with its neighbors within a 17-day window and computing the mean NDVI across the matched images, then visualizes both raw and smoothed NDVI time series.

- gold BAND_SELECT 位置: [{'seq': 3, 'prev': 'RASTER_LOAD', 'next': 'RASTER_LOAD'}, {'seq': 5, 'prev': 'RASTER_LOAD', 'next': 'AGGREGATION'}]
- 下游消费者: （无——isolated）
- owner_ruling: ______（gold_inconsistent / alternative_workflow / clearly_necessary）

## k=1679 — Task: Analyze NDVI time series

Task: Analyze NDVI time series
Analyze the temporal dynamics of NDVI in Rwanda using Landsat 8 surface reflectance data from 2010 to 2020. It filters the NDVI image collection by date and spatial bounds, rescales pixel values by applying a multiplicative factor (0.0001) through a mapping function, and generates three time-series charts: a mean NDVI profile over Rwanda, a day-of-year composite series, and a year-stratified day-of-year NDVI trend. The outputs are interactive charts visualizing sea

- gold BAND_SELECT 位置: [{'seq': 4, 'prev': 'TEMPORAL_FILTER', 'next': 'AGGREGATION'}]
- 下游消费者: （无——isolated）
- owner_ruling: ______（gold_inconsistent / alternative_workflow / clearly_necessary）

## k=1694 — Task: Classify land cover using multisensor fusion

Task: Classify land cover using multisensor fusion
the workflow prepares a multi-source remote sensing data stack combining Sentinel-2 optical bands, Sentinel-1 SAR (VV and VH), terrain attributes (slope, aspect, TWI), and vegetation/water indices (NDVI, NDWI) for supervised classification. It samples training data from user-defined geometries and existing samples, merges them, and exports the combined feature collection to a GEE asset for subsequent classification modeling. The output is a labe

- gold BAND_SELECT 位置: [{'seq': 8, 'prev': 'ATTRIBUTE_FILTER', 'next': 'AGGREGATION'}, {'seq': 17, 'prev': 'ATTRIBUTE_FILTER', 'next': 'AGGREGATION'}]
- 下游消费者: （无——isolated）
- owner_ruling: ______（gold_inconsistent / alternative_workflow / clearly_necessary）

## k=1695 — Task: Classify vegetation and agriculture areas

Task: Classify vegetation and agriculture areas
Compute NDVI from Landsat 8 TOA reflectance data for the year 2018, clips it to a user-defined geometry, and performs land cover classification using a Random Forest classifier trained on user-provided sample regions (Mata and Agricultura). The output is a classified image distinguishing between two classes—likely forest and agricultural areas—based on NDVI values, which is then exported to Google Drive.

- gold BAND_SELECT 位置: [{'seq': 2, 'prev': 'RASTER_LOAD', 'next': 'SPATIAL_FILTER'}]
- 下游消费者: （无——isolated）
- owner_ruling: ______（gold_inconsistent / alternative_workflow / clearly_necessary）

## k=1698 — Task: Extract NDVI from Landsat imagery

Task: Extract NDVI from Landsat imagery
Process Landsat 8 surface reflectance imagery over a user-defined region (pp) to compute and visualize median summer-fall (2017) true-color composites, and attempts to calculate maximum NDVI from winter-spring (2017) imagery. However, due to a bug (using 'ndvi.max()' instead of 'ndvi1.max()'), the NDVI output is incorrect. It clips results to the study area and adds both the composite and flawed NDVI layer to the map for visualization.

- gold BAND_SELECT 位置: [{'seq': 5, 'prev': 'AGGREGATION', 'next': 'RASTER_LOAD'}]
- 下游消费者: （无——isolated）
- owner_ruling: ______（gold_inconsistent / alternative_workflow / clearly_necessary）

## k=1700 — Task: Extract weekly mean dew point temperature

Task: Extract weekly mean dew point temperature
Extract weekly mean dew point temperature (tdmean) from the PRISM AN81d dataset for each week between March 28, 2021, and December 1, 2021, clips it to a specified region, and exports each weekly image to Google Drive.

- gold BAND_SELECT 位置: [{'seq': 2, 'prev': 'RASTER_LOAD', 'next': 'TEMPORAL_FILTER'}]
- 下游消费者: （无——isolated）
- owner_ruling: ______（gold_inconsistent / alternative_workflow / clearly_necessary）

## k=1703 — Task: Map surface temperature in Vienna

Task: Map surface temperature in Vienna
Compute and visualizes the mean land surface temperature (LST) in degrees Celsius for Vienna, Austria, using Landsat 8 Collection 2 Level 2 thermal band ST_B10. It applies cloud masking via QA_PIXEL bits, scales the raw ST_B10 values to Kelvin (using scale factor 0.00341802 and offset 149.0), converts to Celsius, clips the result to Vienna’s subdistricts geometry, and displays it as a single-layer raster map with a yellow-inclusive palette (min=28°C, max=4

- gold BAND_SELECT 位置: [{'seq': 2, 'prev': 'RASTER_LOAD', 'next': 'SPATIAL_FILTER'}]
- 下游消费者: （无——isolated）
- owner_ruling: ______（gold_inconsistent / alternative_workflow / clearly_necessary）

## k=1714 — Task: Map annual fire occurrence

Task: Map annual fire occurrence
Map the spatial extent of thermal anomalies (fire detections) across Australia from 2000 to 2020 using MODIS Terra FIRMS data. It filters the FIRMS ImageCollection by the Australian polygon, aggregates detections per year by computing the maximum brightness temperature (T21) and applying a >100 K threshold to generate binary fire presence layers, then computes annual counts per region (AUS) to produce a time-series chart showing the total number of fire pixels de

- gold BAND_SELECT 位置: [{'seq': 2, 'prev': 'RASTER_LOAD', 'next': 'TEMPORAL_FILTER'}]
- 下游消费者: （无——isolated）
- owner_ruling: ______（gold_inconsistent / alternative_workflow / clearly_necessary）

## k=1722 — Task: Extract cloud-masked Sentinel-2 imagery

Task: Extract cloud-masked Sentinel-2 imagery
Generate a median composite of Sentinel-2 surface reflectance imagery from 2020, masked for clouds and cirrus using the QA60 band, clipped to a user-defined geometry, and exported at 10m resolution for visual and analytical use.

- gold BAND_SELECT 位置: [{'seq': 7, 'prev': 'ITERATIVE_APPLY', 'next': 'AGGREGATION'}]
- 下游消费者: （无——isolated）
- owner_ruling: ______（gold_inconsistent / alternative_workflow / clearly_necessary）

## k=1753 — Task: Analyze NDCI variability in water bodies

Task: Analyze NDCI variability in water bodies
Calculate the Normalized Difference Chlorophyll Index (NDCI) from Landsat 5 and 7 surface reflectance data, applies cloud and water masking using pixel QA and NDWI, and computes the standard deviation of NDCI across the combined time series to assess temporal variability of chlorophyll-related water quality in water bodies within the region of interest.

- gold BAND_SELECT 位置: [{'seq': 3, 'prev': 'RASTER_LOAD', 'next': 'THRESHOLD_LOGIC'}]
- 下游消费者: （无——isolated）
- owner_ruling: ______（gold_inconsistent / alternative_workflow / clearly_necessary）

## k=1761 — Task: Analyze NDVI time series

Task: Analyze NDVI time series
Analyze NDVI time series from Landsat and MODIS satellite data over a user-defined region, enabling comparison of vegetation dynamics through interactive charts generated upon clicking the map.

- gold BAND_SELECT 位置: [{'seq': 6, 'prev': 'ATTRIBUTE_FILTER', 'next': 'RASTER_LOAD'}, {'seq': 11, 'prev': 'ATTRIBUTE_FILTER', 'next': 'RASTER_LOAD'}, {'seq': 16, 'prev': 'ATTRIBUTE_FILTER', 'next': 'RASTER_LOAD'}]
- 下游消费者: （无——isolated）
- owner_ruling: ______（gold_inconsistent / alternative_workflow / clearly_necessary）

## k=1770 — Task: Classify land cover in river basin

Task: Classify land cover in river basin
Classify land cover types in the Rio do Coco basin using Sentinel-2 surface reflectance imagery from April to May 2020. It applies cloud masking using QA60 bits for cirrus and cumulus clouds, computes NDWI and NDVI indices, and trains a Random Forest classifier on manually labeled training samples (water, exposed soil, pasture, forest). The classification uses B4, B3, B2, NDWI, and NDVI as predictors. The output includes a classified land cover map, accur

- gold BAND_SELECT 位置: [{'seq': 6, 'prev': 'AGGREGATION', 'next': 'ATTRIBUTE_FILTER'}]
- 下游消费者: （无——isolated）
- owner_ruling: ______（gold_inconsistent / alternative_workflow / clearly_necessary）

## k=1777 — Task: Analyze NDVI variation over time

Task: Analyze NDVI variation over time
Analyze the temporal variation of NDVI in a defined region using Landsat 8 TOA reflectance data from 2017 to 2019. It computes NDVI by applying normalized difference on bands B5 and B4, maps the index over time, and generates a time-series chart of mean NDVI values within the study area. The output is an interactive chart displayed on the map showing monthly-annual trends, with no raster export or classification performed.

- gold BAND_SELECT 位置: [{'seq': 2, 'prev': 'RASTER_LOAD', 'next': 'TEMPORAL_FILTER'}, {'seq': 5, 'prev': 'RASTER_LOAD', 'next': 'TEMPORAL_FILTER'}]
- 下游消费者: （无——isolated）
- owner_ruling: ______（gold_inconsistent / alternative_workflow / clearly_necessary）

## k=1805 — Task: Analyze aerosol and CO levels

Task: Analyze aerosol and CO levels
Analyze the temporal variation of absorbing aerosol index and carbon monoxide column density over a specified region of the Amazon, generating scatter charts of median and maximum aerosol values. It also visualizes Sentinel-2 RGB imagery and burned area index (NBR) for land surface monitoring during the period.

- gold BAND_SELECT 位置: [{'seq': 2, 'prev': 'RASTER_LOAD', 'next': 'RASTER_LOAD'}, {'seq': 4, 'prev': 'RASTER_LOAD', 'next': 'RASTER_LOAD'}]
- 下游消费者: （无——isolated）
- owner_ruling: ______（gold_inconsistent / alternative_workflow / clearly_necessary）

## k=1807 — Task: Analyze seasonal VV and VH backscatter changes

Task: Analyze seasonal VV and VH backscatter changes
Compute mean VV and VH polarized radar backscatter from Sentinel-1 GRD data across three seasonal periods (prior autumn, summer, and subsequent autumn), composites them into RGB false-color images to visualize temporal changes, and displays the clipped results over a geometry. The output highlights areas with changing backscatter characteristics over time, likely related to land cover dynamics such as vegetation growth or soil moisture variati

- gold BAND_SELECT 位置: [{'seq': 3, 'prev': 'ATTRIBUTE_FILTER', 'next': 'RASTER_LOAD'}, {'seq': 6, 'prev': 'ATTRIBUTE_FILTER', 'next': 'ATTRIBUTE_FILTER'}]
- 下游消费者: （无——isolated）
- owner_ruling: ______（gold_inconsistent / alternative_workflow / clearly_necessary）

## k=1815 — Task: Analyze ETa over water balance area

Task: Analyze ETa over water balance area
Analyze actual evapotranspiration (ETa) within a defined water balance area using EEFLUX data from 2010 to 2015, generating time series charts of mean ETa with and without zero-value masking. It also visualizes the spatial extent of the water balance area and associated CIMIS stations, and prints summary statistics for a specific agricultural region (Calipatria).

- gold BAND_SELECT 位置: [{'seq': 2, 'prev': 'RASTER_LOAD', 'next': 'AGGREGATION'}]
- 下游消费者: （无——isolated）
- owner_ruling: ______（gold_inconsistent / alternative_workflow / clearly_necessary）

## k=1837 — Task: Extract NDBI from Landsat imagery

Task: Extract NDBI from Landsat imagery
Calculate and exports the Normalized Difference Built-up Index (NDBI) from Landsat 8 Surface Reflectance data over a defined geographic region for the months of May to September between 2013 and 2020. NDBI is computed using SWIR (B6) and NIR (B5) bands, masked for clouds and cloud shadows, reduced in resolution via mean aggregation, reprojected to MODIS projection, and exported to Google Drive annually by date.

- gold BAND_SELECT 位置: [{'seq': 9, 'prev': 'TEMPORAL_FILTER', 'next': 'ITERATIVE_APPLY'}]
- 下游消费者: （无——isolated）
- owner_ruling: ______（gold_inconsistent / alternative_workflow / clearly_necessary）

## k=1843 — Task: Analyze NDVI in filtered area

Task: Analyze NDVI in filtered area
Calculate and visualizes NDVI using Sentinel-2 surface reflectance data for a specific geographic area (filtered by Address90 = '0935') within Zaveh, applying cloud masking and clipping to the region of interest. It outputs an NDVI map with a white-to-green color palette and prints the filtered image collection.

- gold BAND_SELECT 位置: [{'seq': 5, 'prev': 'SPATIAL_FILTER', 'next': None}]
- 下游消费者: （无——isolated）
- owner_ruling: ______（gold_inconsistent / alternative_workflow / clearly_necessary）
