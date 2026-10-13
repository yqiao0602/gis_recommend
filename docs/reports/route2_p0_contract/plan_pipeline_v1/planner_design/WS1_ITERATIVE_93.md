# WS1_ITERATIVE_93

## k=1 — Task: Compute NDVI time series

Task: Compute NDVI time series
Compute a cloud-masked NDVI time series from Sentinel-2 Level-2A (SR Harmonized) imagery for a user-defined AOI (identified by 'id' = 1 in a feature collection), spanning 2023. It applies a strict cloud filter (≤5% cloudy pixels), masks clouds and cirrus using QA60 bits 10 and 11, scales reflectance to physical units (÷10000), calculates NDVI as normalizedDifference(['B3','B8']), selects only the NDVI band, clips to the AOI, and exports the full ImageCollection as 

- 预分类: **repeated_execution(same op over time/objects)**
- gold ITERATIVE 位置: [{'seq': 5, 'repeat': 1, 'prev': 'ATTRIBUTE_FILTER', 'next': 'BAND_SELECT'}]
- owner_ruling: ______（repeated_execution / loop_structure / batch_same_op / not_an_error）

## k=4 — Task: Analyze NDVI temporal trend

Task: Analyze NDVI temporal trend
Compute a pixel-wise linear regression of NDVI over time (1984–2021) using Landsat 5, 7, and 8 surface reflectance data to quantify long-term vegetation greenness trends. It outputs: (1) an interactive scatter plot of the NDVI time series at the ROI with a fitted trendline; (2) mean, first, and last NDVI composite images for visualization; and (3) two spatial layers — 'gain' (slope, units: NDVI/year) and 'constant' (intercept) — representing the linear trend par

- 预分类: **repeated_execution(same op over time/objects)**
- gold ITERATIVE 位置: [{'seq': 9, 'repeat': 1, 'prev': 'TEMPORAL_FILTER', 'next': 'RASTER_LOAD'}, {'seq': 15, 'repeat': 1, 'prev': 'SPATIAL_FILTER', 'next': 'RASTER_LOAD'}, {'seq': 21, 'repeat': 1, 'prev': 'SPATIAL_FILTER', 'next': 'AGGREGATION'}]
- owner_ruling: ______（repeated_execution / loop_structure / batch_same_op / not_an_error）

## k=7 — Task: Analyze NDVI time series

Task: Analyze NDVI time series
Calculate and visualizes the mean NDVI over time from Landsat 8 TOA reflectance data within a user-defined polygon, generating a time series chart of average NDVI values and displaying the mean NDVI composite on the map.

- 预分类: **repeated_execution(same op over time/objects)**
- gold ITERATIVE 位置: [{'seq': 4, 'repeat': 1, 'prev': 'TEMPORAL_FILTER', 'next': 'AGGREGATION'}]
- owner_ruling: ______（repeated_execution / loop_structure / batch_same_op / not_an_error）

## k=27 — Task: Analyze snow cover change

Task: Analyze snow cover change
Calculate and compares the Normalized Difference Snow Index (NDSI) from Landsat 7 surface reflectance data for two winter periods: 2000–2015 and 2016–2020, over a user-defined study area. It computes the mean NDSI for each period, masks clouds and cloud shadows, clips to the study boundary, and generates a difference layer showing changes in snow cover between the two time intervals. The outputs include visualizations of true-color and false-color composites, NDSI

- 预分类: **repeated_execution(same op over time/objects)**
- gold ITERATIVE 位置: [{'seq': 7, 'repeat': 1, 'prev': 'SPATIAL_FILTER', 'next': 'RASTER_LOAD'}, {'seq': 14, 'repeat': 1, 'prev': 'SPATIAL_FILTER', 'next': None}]
- owner_ruling: ______（repeated_execution / loop_structure / batch_same_op / not_an_error）

## k=38 — Task: Extract cloud-masked Sentinel-2 imagery

Task: Extract cloud-masked Sentinel-2 imagery
Extract cloud-masked Sentinel-2 surface reflectance images over a user-defined region of interest (ROI) for December 2021. It filters images by low cloud cover (<10%), applies a scaling factor (dividing by 100), selects specific spectral bands, and exports each individual image as a clipped GeoTIFF to Google Drive. The output consists of multiple 8-bit GeoTIFF files named by their 'system:index', representing true-color and multispectral surface refl

- 预分类: **repeated_execution(same op over time/objects)**
- gold ITERATIVE 位置: [{'seq': 5, 'repeat': 1, 'prev': 'ATTRIBUTE_FILTER', 'next': 'AGGREGATION'}]
- owner_ruling: ______（repeated_execution / loop_structure / batch_same_op / not_an_error）

## k=39 — Task: Model wind speed at 10m

Task: Model wind speed at 10m
Calculate wind speed from u and v components of wind at 10m height from ERA5-Land data, applies a logarithmic adjustment, filters days with wind speed greater than 5 m/s, and exports the cumulative sum of daily maximum wind speeds as a single raster image.

- 预分类: **loop_structure(cumulative/iterative computation)**
- gold ITERATIVE 位置: [{'seq': 4, 'repeat': 1, 'prev': 'TEMPORAL_FILTER', 'next': 'BAND_SELECT'}, {'seq': 6, 'repeat': 1, 'prev': 'BAND_SELECT', 'next': 'BAND_SELECT'}, {'seq': 8, 'repeat': 1, 'prev': 'BAND_SELECT', 'next': 'BAND_SELECT'}]
- owner_ruling: ______（repeated_execution / loop_structure / batch_same_op / not_an_error）

## k=52 — Task: Classify land cover types

Task: Classify land cover types
Classify land cover in a specified region using Sentinel-2 surface reflectance imagery from three seasonal periods in 2021. It computes median composites for winter (Jan–Apr), summer (May–Aug), and fall (Sep–Dec), then combines them into a multi-temporal stack. Training samples are extracted from labeled points to train a CART classifier, which is applied to generate a land cover classification map with three classes. the workflow outputs include the trained class

- 预分类: **repeated_execution(same op over time/objects)**
- gold ITERATIVE 位置: [{'seq': 5, 'repeat': 1, 'prev': 'ATTRIBUTE_FILTER', 'next': 'BAND_SELECT'}, {'seq': 11, 'repeat': 1, 'prev': 'ATTRIBUTE_FILTER', 'next': 'BAND_SELECT'}, {'seq': 17, 'repeat': 1, 'prev': 'ATTRIBUTE_FILTER', 'next': 'BAND_SELECT'}]
- owner_ruling: ______（repeated_execution / loop_structure / batch_same_op / not_an_error）

## k=100 — Task: Generate Landsat 8 surface reflectance RGB mosaics

Task: Generate Landsat 8 surface reflectance RGB mosaics
Generate daily-mosaic RGB composites from Landsat 8 Collection 2 Level 2 Surface Reflectance (SR) imagery over the Monterey County, CA region for a one-year period (2014–2015). It applies radiometric scaling to SR bands (SR_B4, SR_B3, SR_B2) using the official C2 L2 scale factor (0.0000275) and offset (−0.2), clips to both a bounding rectangle and the Monterey county FeatureCollection, creates one image per day via mosaic (retaining earlie

- 预分类: **repeated_execution(same op over time/objects)**
- gold ITERATIVE 位置: [{'seq': 5, 'repeat': 1, 'prev': 'SPATIAL_FILTER', 'next': None}]
- owner_ruling: ______（repeated_execution / loop_structure / batch_same_op / not_an_error）

## k=101 — Task: Analyze NDVI time series

Task: Analyze NDVI time series
Analyze NDVI time series from Landsat surface reflectance data between 1999-12-01 and 2021-01-31 over a defined polygon, and compares it with MODIS MOD13Q1 NDVI annual data for 2020. It enables interactive charting of NDVI values at clicked locations by generating temporal profiles from both Landsat and MODIS collections.

- 预分类: **repeated_execution(same op over time/objects)**
- gold ITERATIVE 位置: [{'seq': 18, 'repeat': 1, 'prev': 'RASTER_LOAD', 'next': 'GEOMETRY_DEFINE'}]
- owner_ruling: ______（repeated_execution / loop_structure / batch_same_op / not_an_error）

## k=112 — Task: Estimate annual population distribution

Task: Estimate annual population distribution
Estimate the spatial distribution of population in China for the year 2020 using WorldPop 100m resolution gridded population data. It filters the WorldPop ImageCollection by country (CHN) and date (2001, though likely intended to be 2020), computes the mean annual population surface, clips it to a user-defined geometry, visualizes it with a custom color palette, and generates a time series chart of total population summed over the region across all a

- 预分类: **repeated_execution(same op over time/objects)**
- gold ITERATIVE 位置: [{'seq': 3, 'repeat': 1, 'prev': 'SPATIAL_FILTER', 'next': 'ATTRIBUTE_FILTER'}]
- owner_ruling: ______（repeated_execution / loop_structure / batch_same_op / not_an_error）

## k=118 — Task: Classify land cover using GLCM texture features

Task: Classify land cover using GLCM texture features
Compute and integrates Gray-Level Co-occurrence Matrix (GLCM) texture features from NIR band of Landsat 8 TOA imagery into seasonal composites, then generates a full-year high-quality composite image for land cover classification. The output is a 24-band image combining original spectral bands and derived GLCM textures (e.g., ASM, CONTRAST, CORR) across four seasonal periods, masked and merged to optimize spatial coverage and quality, intende

- 预分类: **repeated_execution(same op over time/objects)**
- gold ITERATIVE 位置: [{'seq': 5, 'repeat': 1, 'prev': 'ATTRIBUTE_FILTER', 'next': 'BAND_SELECT'}]
- owner_ruling: ______（repeated_execution / loop_structure / batch_same_op / not_an_error）

## k=133 — Task: Estimate fractional vegetation cover

Task: Estimate fractional vegetation cover
Estimate Fractional Vegetation Cover (FVC) in the Saihanba region using Landsat 7 SR imagery from August 2007. It computes NDVI from bands B4 and B3, then derives FVC by normalizing NDVI between pre-defined minimum (Vs) and maximum (Vv) vegetation endmembers. A dynamic mask is applied using a thresholded FVC difference layer (dif) to exclude non-vegetated areas. The final output includes a clipped and masked FVC raster, NDVI and FVC time-series charts o

- 预分类: **repeated_execution(same op over time/objects)**
- gold ITERATIVE 位置: [{'seq': 3, 'repeat': 1, 'prev': 'RASTER_LOAD', 'next': 'TEMPORAL_FILTER'}]
- owner_ruling: ______（repeated_execution / loop_structure / batch_same_op / not_an_error）

## k=162 — Task: Analyze NDVI trend over time

Task: Analyze NDVI trend over time
Analyze long-term vegetation trends in a specified region using NDVI derived from Landsat surface reflectance imagery (1984–2019). It processes Landsat 5, 7, and 8 data by applying cloud masking, band renaming for consistency, and calculating annual mean NDVI composites. A linear regression (linearFit) is applied to the time series to estimate the slope (trend) of NDVI change per year, which is then visualized and summarized by region. Outputs include an NDVI t

- 预分类: **repeated_execution(same op over time/objects)**
- gold ITERATIVE 位置: [{'seq': 16, 'repeat': 1, 'prev': 'ATTRIBUTE_FILTER', 'next': 'RASTER_LOAD'}]
- owner_ruling: ______（repeated_execution / loop_structure / batch_same_op / not_an_error）

## k=178 — Task: Monitor dry-season NDVI trends

Task: Monitor dry-season NDVI trends
Compute and compares annual dry-season (April–September) NDVI composites for Kebumen Regency, Central Java, Indonesia, across 2020–2024 using Sentinel-2 SR imagery. It applies SCL-based cloud/shadow/snow masking, generates per-year median NDVI rasters, classifies NDVI into four vegetation health classes (1: bare/low, 2: sparse, 3: moderate, 4: dense), calculates mean NDVI per kecamatan (subdistrict) via reduceRegions, exports a merged FeatureCollection of all

- 预分类: **repeated_execution(same op over time/objects)**
- gold ITERATIVE 位置: [{'seq': 6, 'repeat': 1, 'prev': 'BAND_SELECT', 'next': 'AGGREGATION'}]
- owner_ruling: ______（repeated_execution / loop_structure / batch_same_op / not_an_error）

## k=182 — Task: Estimate Chl_a concentration

Task: Estimate Chl_a concentration
Estimate chlorophyll-a (Chl_a) concentration in the Pearl River Basin using Landsat 8 surface reflectance imagery from 2013 to 2022. It applies atmospheric correction and cloud masking via QA bands, computes NDVI, and derives Chl_a using a linear regression model based on NDVI. A time series of mean annual Chl_a values per region (OBJECTID) is generated and visualized as a scatter chart, with outputs including mapped Chl_a images and regional trend analysis.

- 预分类: **repeated_execution(same op over time/objects)**
- gold ITERATIVE 位置: [{'seq': 4, 'repeat': 1, 'prev': 'SPATIAL_FILTER', 'next': 'RASTER_LOAD'}]
- owner_ruling: ______（repeated_execution / loop_structure / batch_same_op / not_an_error）

## k=216 — Task: Analyze NDVI time series

Task: Analyze NDVI time series
Analyze the temporal evolution of NDVI, EVI, and SAVI vegetation indices over a merged agricultural area using Landsat 5 surface reflectance data from 1993 to 2008. It computes vegetation indices, generates a median composite for visualization, and displays a time-series chart of NDVI values within the region of interest.

- 预分类: **repeated_execution(same op over time/objects)**
- gold ITERATIVE 位置: [{'seq': 4, 'repeat': 1, 'prev': 'TEMPORAL_FILTER', 'next': None}]
- owner_ruling: ______（repeated_execution / loop_structure / batch_same_op / not_an_error）

## k=220 — Task: Analyze NDVI time series

Task: Analyze NDVI time series
Analyze the phenological patterns of vegetation using NDVI derived from MODIS MYD13Q1 imagery over a 20-year period (2002–2022). It computes both a median composite and a full time series collection, applies scaling to NDVI values, and visualizes the results on the map. Upon user click, it generates an interactive time series chart showing temporal dynamics of NDVI at the selected point, enabling phenological analysis such as detecting growing seasons, trends, or a

- 预分类: **repeated_execution(same op over time/objects)**
- gold ITERATIVE 位置: [{'seq': 4, 'repeat': 1, 'prev': 'ATTRIBUTE_FILTER', 'next': 'RASTER_LOAD'}]
- owner_ruling: ______（repeated_execution / loop_structure / batch_same_op / not_an_error）

## k=240 — Task: Compute monthly mean LST

Task: Compute monthly mean LST
Compute monthly mean land surface temperature (LST) from MODIS MOD11A1 daily imagery over the period 2000–2008. It preprocesses the daily LST data by applying a scale factor (0.02), clips to a specified region (ne095), aggregates daily values into monthly means, and generates a time series chart of monthly LST. Outputs include the processed ImageCollection of monthly LST composites and a UI chart visualizing the temporal trend.

- 预分类: **repeated_execution(same op over time/objects)**
- gold ITERATIVE 位置: [{'seq': 5, 'repeat': 1, 'prev': 'SPATIAL_FILTER', 'next': 'TEMPORAL_FILTER'}]
- owner_ruling: ______（repeated_execution / loop_structure / batch_same_op / not_an_error）

## k=246 — Task: Classify land cover in district

Task: Classify land cover in district
Classify land cover in Kanpur Nagar using Sentinel-2 imagery. It trains a Random Forest classifier on labeled regions from a feature collection (table3) using spectral bands from a median composite image (2019-01-01 to 2019-05-30). The trained model is then applied to monthly images of Kanpur Nagar for the years 2016 and 2019, producing classified land cover maps for each month. Outputs are exported as raster images to Google Drive, named by district, month,

- 预分类: **repeated_execution(same op over time/objects)**
- gold ITERATIVE 位置: [{'seq': 6, 'repeat': 1, 'prev': 'COLLECTION_MGMT', 'next': 'BAND_SELECT'}, {'seq': 16, 'repeat': 1, 'prev': 'COLLECTION_MGMT', 'next': 'BAND_SELECT'}]
- owner_ruling: ______（repeated_execution / loop_structure / batch_same_op / not_an_error）

## k=256 — Task: Compare L8 and S2 MNDWI

Task: Compare L8 and S2 MNDWI
Compute and compares the Modified Normalized Difference Water Index (MNDWI) from Landsat 8 and Sentinel-2 imagery over a specified region and time period. It generates monthly median MNDWI images, performs linear regression between the two sensor datasets, and visualizes the relationship through time series and spatial layers. Outputs include a fitted linear model (scale and offset), point-based time series charts, and spatial visualizations of corrected MNDWI value

- 预分类: **repeated_execution(same op over time/objects)**
- gold ITERATIVE 位置: [{'seq': 5, 'repeat': 1, 'prev': 'ATTRIBUTE_FILTER', 'next': 'RASTER_LOAD'}, {'seq': 10, 'repeat': 1, 'prev': 'ATTRIBUTE_FILTER', 'next': 'TEMPORAL_FILTER'}]
- owner_ruling: ______（repeated_execution / loop_structure / batch_same_op / not_an_error）

## k=274 — Task: Analyze vegetation and land cover characteristics

Task: Analyze vegetation and land cover characteristics
Analyze multi-temporal Landsat 8 surface reflectance imagery over a defined region from 2014 to 2019 during a specific day-of-year range (330–15), applying cloud masking and computing a suite of spectral indices (NDVI, LSWI, NBR, NVI, RGRI, RGRI-NDVI, RGRI-LSWI, NRWI, and derived min/max composites) to characterize land surface conditions. It generates mean, minimum, and maximum composite images for these indices and produces histograms of 

- 预分类: **repeated_execution(same op over time/objects)**
- gold ITERATIVE 位置: [{'seq': 4, 'repeat': 1, 'prev': 'SPATIAL_FILTER', 'next': None}]
- owner_ruling: ______（repeated_execution / loop_structure / batch_same_op / not_an_error）

## k=291 — Task: Analyze NDVI and EVI time series

Task: Analyze NDVI and EVI time series
Compute NDVI and EVI vegetation indices from Sentinel-2 imagery over the Kilimanjaro region from 2020 to 2022. It processes a cloud-filtered image collection by applying spectral index calculations (NDVI and EVI) using specific bands, generates time series charts for both polygon and point regions of interest, computes mean composite images, and exports clipped NDVI and EVI rasters to Google Drive. Outputs include line charts of temporal VI trends, mapped m

- 预分类: **repeated_execution(same op over time/objects)**
- gold ITERATIVE 位置: [{'seq': 8, 'repeat': 1, 'prev': 'SPATIAL_FILTER', 'next': 'AGGREGATION'}]
- owner_ruling: ______（repeated_execution / loop_structure / batch_same_op / not_an_error）

## k=303 — Task: Extract NDVI time series for vegetation analysis

Task: Extract NDVI time series for vegetation analysis
Compute monthly NDVI values from Sentinel-2 imagery between May 2020 and May 2021 over a specified region (table). It applies cloud masking using the QA60 band to remove cloudy pixels, then calculates NDVI using the near-infrared (B8) and red (B4) bands. These monthly NDVI images are combined into a multitemporal image stack, which is used to extract mean NDVI values for regions defined in 'alfalfa' via reduceRegions. Additionally, the multi

- 预分类: **repeated_execution(same op over time/objects)**
- gold ITERATIVE 位置: [{'seq': 5, 'repeat': 1, 'prev': 'ATTRIBUTE_FILTER', 'next': 'RASTER_LOAD'}, {'seq': 10, 'repeat': 1, 'prev': 'ATTRIBUTE_FILTER', 'next': 'RASTER_LOAD'}, {'seq': 15, 'repeat': 1, 'prev': 'ATTRIBUTE_FILTER', 'next': 'RASTER_LOAD'}, {'seq': 20, 'repeat': 1, 'prev': 'ATTRIBUTE_FILTER', 'next': 'RASTER_LOAD'}, {'seq': 25, 'repeat': 1, 'prev': 'ATTRIBUTE_FILTER', 'next': 'RASTER_LOAD'}, {'seq': 30, 'repeat': 1, 'prev': 'ATTRIBUTE_FILTER', 'next': 'RASTER_LOAD'}, {'seq': 35, 'repeat': 1, 'prev': 'ATTRIBUTE_FILTER', 'next': 'RASTER_LOAD'}, {'seq': 40, 'repeat': 1, 'prev': 'ATTRIBUTE_FILTER', 'next': 'RASTER_LOAD'}, {'seq': 45, 'repeat': 1, 'prev': 'ATTRIBUTE_FILTER', 'next': 'RASTER_LOAD'}, {'seq': 50, 'repeat': 1, 'prev': 'ATTRIBUTE_FILTER', 'next': 'RASTER_LOAD'}, {'seq': 55, 'repeat': 1, 'prev': 'ATTRIBUTE_FILTER', 'next': 'RASTER_LOAD'}, {'seq': 60, 'repeat': 1, 'prev': 'ATTRIBUTE_FILTER', 'next': 'RASTER_LOAD'}, {'seq': 65, 'repeat': 1, 'prev': 'ATTRIBUTE_FILTER', 'next': 'AGGREGATION'}]
- owner_ruling: ______（repeated_execution / loop_structure / batch_same_op / not_an_error）

## k=325 — Task: Analyze NDVI trends annually

Task: Analyze NDVI trends annually
Calculate annual mean NDVI values from the NASA GIMMS 3GV0 dataset over a user-defined geometry, generating a time series of regional NDVI means aggregated by year from 1982 onward, and exports the results as a CSV file containing mean NDVI per year along with start and end timestamps.

- 预分类: **repeated_execution(same op over time/objects)**
- gold ITERATIVE 位置: [{'seq': 4, 'repeat': 1, 'prev': 'TEMPORAL_FILTER', 'next': 'SPATIAL_FILTER'}]
- owner_ruling: ______（repeated_execution / loop_structure / batch_same_op / not_an_error）

## k=328 — Task: Analyze NDVI time series

Task: Analyze NDVI time series
Analyze the temporal dynamics of vegetation using the Normalized Difference Vegetation Index (NDVI) derived from the MODIS/Terra MOD13A2 product, spanning from January 1, 2012, to a user-defined end date. It processes an ImageCollection by filtering for the date range, selecting the NDVI band, clipping to a study area using a user-defined function (ZonasClip), scaling pixel values to a standard range (-0.2 to 1), adding time and constant auxiliary bands via addVari

- 预分类: **repeated_execution(same op over time/objects)**
- gold ITERATIVE 位置: [{'seq': 5, 'repeat': 1, 'prev': 'BAND_SELECT', 'next': None}]
- owner_ruling: ______（repeated_execution / loop_structure / batch_same_op / not_an_error）

## k=362 — Task: Analyze NDVI time series

Task: Analyze NDVI time series
Compute and analyzes the Normalized Difference Vegetation Index (NDVI) from Landsat 8 Surface Reflectance imagery over a specified geometry for the year 2020. It applies cloud and shadow masking using the pixel_qa band, calculates NDVI using bands B5 and B4, and generates a mean NDVI composite map. Additionally, it creates a time series chart of mean NDVI values over the region with a linear trendline and exports individual NDVI images to Google Drive every four im

- 预分类: **repeated_execution(same op over time/objects)**
- gold ITERATIVE 位置: [{'seq': 2, 'repeat': 1, 'prev': 'RASTER_LOAD', 'next': 'TEMPORAL_FILTER'}, {'seq': 5, 'repeat': 1, 'prev': 'SPATIAL_FILTER', 'next': 'AGGREGATION'}]
- owner_ruling: ______（repeated_execution / loop_structure / batch_same_op / not_an_error）

## k=370 — Task: Identify perennial water bodies

Task: Identify perennial water bodies
Calculate the frequency of water occurrence in a fixed region (34°N–36°N, 114°E–119°E) using Landsat 5, 7, and 8 surface reflectance data from 1984 to 2021. It computes multiple vegetation and water indices (NDVI, EVI, LSWI, mNDWI), applies a water detection rule based on mNDWI > EVI or NDVI and low EVI, and aggregates annual water observations. The output is a binary map indicating areas with ≥75% water frequency over each year, exported annually as 'imgPer

- 预分类: **repeated_execution(same op over time/objects)**
- gold ITERATIVE 位置: [{'seq': 6, 'repeat': 1, 'prev': 'ATTRIBUTE_FILTER', 'next': 'BAND_SELECT'}, {'seq': 12, 'repeat': 1, 'prev': 'ATTRIBUTE_FILTER', 'next': 'BAND_SELECT'}, {'seq': 18, 'repeat': 1, 'prev': 'ATTRIBUTE_FILTER', 'next': 'BAND_SELECT'}, {'seq': 25, 'repeat': 1, 'prev': 'ATTRIBUTE_FILTER', 'next': 'BAND_SELECT'}, {'seq': 31, 'repeat': 1, 'prev': 'ATTRIBUTE_FILTER', 'next': 'BAND_SELECT'}, {'seq': 37, 'repeat': 1, 'prev': 'ATTRIBUTE_FILTER', 'next': 'BAND_SELECT'}, {'seq': 44, 'repeat': 1, 'prev': 'ATTRIBUTE_FILTER', 'next': 'BAND_SELECT'}, {'seq': 50, 'repeat': 1, 'prev': 'ATTRIBUTE_FILTER', 'next': 'BAND_SELECT'}, {'seq': 56, 'repeat': 1, 'prev': 'ATTRIBUTE_FILTER', 'next': 'BAND_SELECT'}, {'seq': 63, 'repeat': 1, 'prev': 'ATTRIBUTE_FILTER', 'next': 'BAND_SELECT'}, {'seq': 69, 'repeat': 1, 'prev': 'ATTRIBUTE_FILTER', 'next': 'BAND_SELECT'}, {'seq': 75, 'repeat': 1, 'prev': 'ATTRIBUTE_FILTER', 'next': 'BAND_SELECT'}, {'seq': 82, 'repeat': 1, 'prev': 'ATTRIBUTE_FILTER', 'next': 'BAND_SELECT'}, {'seq': 88, 'repeat': 1, 'prev': 'ATTRIBUTE_FILTER', 'next': 'BAND_SELECT'}, {'seq': 94, 'repeat': 1, 'prev': 'ATTRIBUTE_FILTER', 'next': 'BAND_SELECT'}, {'seq': 101, 'repeat': 1, 'prev': 'ATTRIBUTE_FILTER', 'next': 'BAND_SELECT'}, {'seq': 107, 'repeat': 1, 'prev': 'ATTRIBUTE_FILTER', 'next': 'BAND_SELECT'}, {'seq': 113, 'repeat': 1, 'prev': 'ATTRIBUTE_FILTER', 'next': 'BAND_SELECT'}, {'seq': 120, 'repeat': 1, 'prev': 'ATTRIBUTE_FILTER', 'next': 'BAND_SELECT'}, {'seq': 126, 'repeat': 1, 'prev': 'ATTRIBUTE_FILTER', 'next': 'BAND_SELECT'}, {'seq': 132, 'repeat': 1, 'prev': 'ATTRIBUTE_FILTER', 'next': 'BAND_SELECT'}, {'seq': 139, 'repeat': 1, 'prev': 'ATTRIBUTE_FILTER', 'next': 'BAND_SELECT'}, {'seq': 145, 'repeat': 1, 'prev': 'ATTRIBUTE_FILTER', 'next': 'BAND_SELECT'}, {'seq': 151, 'repeat': 1, 'prev': 'ATTRIBUTE_FILTER', 'next': 'BAND_SELECT'}, {'seq': 158, 'repeat': 1, 'prev': 'ATTRIBUTE_FILTER', 'next': 'BAND_SELECT'}, {'seq': 164, 'repeat': 1, 'prev': 'ATTRIBUTE_FILTER', 'next': 'BAND_SELECT'}, {'seq': 170, 'repeat': 1, 'prev': 'ATTRIBUTE_FILTER', 'next': 'BAND_SELECT'}, {'seq': 177, 'repeat': 1, 'prev': 'ATTRIBUTE_FILTER', 'next': 'BAND_SELECT'}, {'seq': 183, 'repeat': 1, 'prev': 'ATTRIBUTE_FILTER', 'next': 'BAND_SELECT'}, {'seq': 189, 'repeat': 1, 'prev': 'ATTRIBUTE_FILTER', 'next': 'BAND_SELECT'}, {'seq': 196, 'repeat': 1, 'prev': 'ATTRIBUTE_FILTER', 'next': 'BAND_SELECT'}, {'seq': 202, 'repeat': 1, 'prev': 'ATTRIBUTE_FILTER', 'next': 'BAND_SELECT'}, {'seq': 208, 'repeat': 1, 'prev': 'ATTRIBUTE_FILTER', 'next': 'BAND_SELECT'}, {'seq': 215, 'repeat': 1, 'prev': 'ATTRIBUTE_FILTER', 'next': 'BAND_SELECT'}, {'seq': 221, 'repeat': 1, 'prev': 'ATTRIBUTE_FILTER', 'next': 'BAND_SELECT'}, {'seq': 227, 'repeat': 1, 'prev': 'ATTRIBUTE_FILTER', 'next': 'BAND_SELECT'}, {'seq': 234, 'repeat': 1, 'prev': 'ATTRIBUTE_FILTER', 'next': 'BAND_SELECT'}, {'seq': 240, 'repeat': 1, 'prev': 'ATTRIBUTE_FILTER', 'next': 'BAND_SELECT'}, {'seq': 246, 'repeat': 1, 'prev': 'ATTRIBUTE_FILTER', 'next': 'BAND_SELECT'}, {'seq': 253, 'repeat': 1, 'prev': 'ATTRIBUTE_FILTER', 'next': 'BAND_SELECT'}, {'seq': 259, 'repeat': 1, 'prev': 'ATTRIBUTE_FILTER', 'next': 'BAND_SELECT'}, {'seq': 265, 'repeat': 1, 'prev': 'ATTRIBUTE_FILTER', 'next': 'BAND_SELECT'}, {'seq': 272, 'repeat': 1, 'prev': 'ATTRIBUTE_FILTER', 'next': 'BAND_SELECT'}, {'seq': 278, 'repeat': 1, 'prev': 'ATTRIBUTE_FILTER', 'next': 'BAND_SELECT'}, {'seq': 284, 'repeat': 1, 'prev': 'ATTRIBUTE_FILTER', 'next': 'BAND_SELECT'}, {'seq': 291, 'repeat': 1, 'prev': 'ATTRIBUTE_FILTER', 'next': 'BAND_SELECT'}, {'seq': 297, 'repeat': 1, 'prev': 'ATTRIBUTE_FILTER', 'next': 'BAND_SELECT'}, {'seq': 303, 'repeat': 1, 'prev': 'ATTRIBUTE_FILTER', 'next': 'BAND_SELECT'}, {'seq': 310, 'repeat': 1, 'prev': 'ATTRIBUTE_FILTER', 'next': 'BAND_SELECT'}, {'seq': 316, 'repeat': 1, 'prev': 'ATTRIBUTE_FILTER', 'next': 'BAND_SELECT'}, {'seq': 322, 'repeat': 1, 'prev': 'ATTRIBUTE_FILTER', 'next': 'BAND_SELECT'}, {'seq': 329, 'repeat': 1, 'prev': 'ATTRIBUTE_FILTER', 'next': 'BAND_SELECT'}, {'seq': 335, 'repeat': 1, 'prev': 'ATTRIBUTE_FILTER', 'next': 'BAND_SELECT'}, {'seq': 341, 'repeat': 1, 'prev': 'ATTRIBUTE_FILTER', 'next': 'BAND_SELECT'}, {'seq': 348, 'repeat': 1, 'prev': 'ATTRIBUTE_FILTER', 'next': 'BAND_SELECT'}, {'seq': 354, 'repeat': 1, 'prev': 'ATTRIBUTE_FILTER', 'next': 'BAND_SELECT'}, {'seq': 360, 'repeat': 1, 'prev': 'ATTRIBUTE_FILTER', 'next': 'BAND_SELECT'}, {'seq': 367, 'repeat': 1, 'prev': 'ATTRIBUTE_FILTER', 'next': 'BAND_SELECT'}, {'seq': 373, 'repeat': 1, 'prev': 'ATTRIBUTE_FILTER', 'next': 'BAND_SELECT'}, {'seq': 379, 'repeat': 1, 'prev': 'ATTRIBUTE_FILTER', 'next': 'BAND_SELECT'}, {'seq': 386, 'repeat': 1, 'prev': 'ATTRIBUTE_FILTER', 'next': 'BAND_SELECT'}, {'seq': 392, 'repeat': 1, 'prev': 'ATTRIBUTE_FILTER', 'next': 'BAND_SELECT'}, {'seq': 398, 'repeat': 1, 'prev': 'ATTRIBUTE_FILTER', 'next': 'BAND_SELECT'}, {'seq': 405, 'repeat': 1, 'prev': 'ATTRIBUTE_FILTER', 'next': 'BAND_SELECT'}, {'seq': 411, 'repeat': 1, 'prev': 'ATTRIBUTE_FILTER', 'next': 'BAND_SELECT'}, {'seq': 417, 'repeat': 1, 'prev': 'ATTRIBUTE_FILTER', 'next': 'BAND_SELECT'}, {'seq': 424, 'repeat': 1, 'prev': 'ATTRIBUTE_FILTER', 'next': 'BAND_SELECT'}, {'seq': 430, 'repeat': 1, 'prev': 'ATTRIBUTE_FILTER', 'next': 'BAND_SELECT'}, {'seq': 436, 'repeat': 1, 'prev': 'ATTRIBUTE_FILTER', 'next': 'BAND_SELECT'}, {'seq': 443, 'repeat': 1, 'prev': 'ATTRIBUTE_FILTER', 'next': 'BAND_SELECT'}, {'seq': 449, 'repeat': 1, 'prev': 'ATTRIBUTE_FILTER', 'next': 'BAND_SELECT'}, {'seq': 455, 'repeat': 1, 'prev': 'ATTRIBUTE_FILTER', 'next': 'BAND_SELECT'}, {'seq': 462, 'repeat': 1, 'prev': 'ATTRIBUTE_FILTER', 'next': 'BAND_SELECT'}, {'seq': 468, 'repeat': 1, 'prev': 'ATTRIBUTE_FILTER', 'next': 'BAND_SELECT'}, {'seq': 474, 'repeat': 1, 'prev': 'ATTRIBUTE_FILTER', 'next': 'BAND_SELECT'}, {'seq': 481, 'repeat': 1, 'prev': 'ATTRIBUTE_FILTER', 'next': 'BAND_SELECT'}, {'seq': 487, 'repeat': 1, 'prev': 'ATTRIBUTE_FILTER', 'next': 'BAND_SELECT'}, {'seq': 493, 'repeat': 1, 'prev': 'ATTRIBUTE_FILTER', 'next': 'BAND_SELECT'}, {'seq': 500, 'repeat': 1, 'prev': 'ATTRIBUTE_FILTER', 'next': 'BAND_SELECT'}, {'seq': 506, 'repeat': 1, 'prev': 'ATTRIBUTE_FILTER', 'next': 'BAND_SELECT'}, {'seq': 512, 'repeat': 1, 'prev': 'ATTRIBUTE_FILTER', 'next': 'BAND_SELECT'}, {'seq': 519, 'repeat': 1, 'prev': 'ATTRIBUTE_FILTER', 'next': 'BAND_SELECT'}, {'seq': 525, 'repeat': 1, 'prev': 'ATTRIBUTE_FILTER', 'next': 'BAND_SELECT'}, {'seq': 531, 'repeat': 1, 'prev': 'ATTRIBUTE_FILTER', 'next': 'BAND_SELECT'}, {'seq': 538, 'repeat': 1, 'prev': 'ATTRIBUTE_FILTER', 'next': 'BAND_SELECT'}, {'seq': 544, 'repeat': 1, 'prev': 'ATTRIBUTE_FILTER', 'next': 'BAND_SELECT'}, {'seq': 550, 'repeat': 1, 'prev': 'ATTRIBUTE_FILTER', 'next': 'BAND_SELECT'}, {'seq': 557, 'repeat': 1, 'prev': 'ATTRIBUTE_FILTER', 'next': 'BAND_SELECT'}, {'seq': 563, 'repeat': 1, 'prev': 'ATTRIBUTE_FILTER', 'next': 'BAND_SELECT'}, {'seq': 569, 'repeat': 1, 'prev': 'ATTRIBUTE_FILTER', 'next': 'BAND_SELECT'}, {'seq': 576, 'repeat': 1, 'prev': 'ATTRIBUTE_FILTER', 'next': 'BAND_SELECT'}, {'seq': 582, 'repeat': 1, 'prev': 'ATTRIBUTE_FILTER', 'next': 'BAND_SELECT'}, {'seq': 588, 'repeat': 1, 'prev': 'ATTRIBUTE_FILTER', 'next': 'BAND_SELECT'}, {'seq': 595, 'repeat': 1, 'prev': 'ATTRIBUTE_FILTER', 'next': 'BAND_SELECT'}, {'seq': 601, 'repeat': 1, 'prev': 'ATTRIBUTE_FILTER', 'next': 'BAND_SELECT'}, {'seq': 607, 'repeat': 1, 'prev': 'ATTRIBUTE_FILTER', 'next': 'BAND_SELECT'}, {'seq': 614, 'repeat': 1, 'prev': 'ATTRIBUTE_FILTER', 'next': 'BAND_SELECT'}, {'seq': 620, 'repeat': 1, 'prev': 'ATTRIBUTE_FILTER', 'next': 'BAND_SELECT'}, {'seq': 626, 'repeat': 1, 'prev': 'ATTRIBUTE_FILTER', 'next': 'BAND_SELECT'}, {'seq': 633, 'repeat': 1, 'prev': 'ATTRIBUTE_FILTER', 'next': 'BAND_SELECT'}, {'seq': 639, 'repeat': 1, 'prev': 'ATTRIBUTE_FILTER', 'next': 'BAND_SELECT'}, {'seq': 645, 'repeat': 1, 'prev': 'ATTRIBUTE_FILTER', 'next': 'BAND_SELECT'}, {'seq': 652, 'repeat': 1, 'prev': 'ATTRIBUTE_FILTER', 'next': 'BAND_SELECT'}, {'seq': 658, 'repeat': 1, 'prev': 'ATTRIBUTE_FILTER', 'next': 'BAND_SELECT'}, {'seq': 664, 'repeat': 1, 'prev': 'ATTRIBUTE_FILTER', 'next': 'BAND_SELECT'}, {'seq': 671, 'repeat': 1, 'prev': 'ATTRIBUTE_FILTER', 'next': 'BAND_SELECT'}, {'seq': 677, 'repeat': 1, 'prev': 'ATTRIBUTE_FILTER', 'next': 'BAND_SELECT'}, {'seq': 683, 'repeat': 1, 'prev': 'ATTRIBUTE_FILTER', 'next': 'BAND_SELECT'}, {'seq': 690, 'repeat': 1, 'prev': 'ATTRIBUTE_FILTER', 'next': 'BAND_SELECT'}, {'seq': 696, 'repeat': 1, 'prev': 'ATTRIBUTE_FILTER', 'next': 'BAND_SELECT'}, {'seq': 702, 'repeat': 1, 'prev': 'ATTRIBUTE_FILTER', 'next': 'BAND_SELECT'}, {'seq': 709, 'repeat': 1, 'prev': 'ATTRIBUTE_FILTER', 'next': 'BAND_SELECT'}, {'seq': 715, 'repeat': 1, 'prev': 'ATTRIBUTE_FILTER', 'next': 'BAND_SELECT'}, {'seq': 721, 'repeat': 1, 'prev': 'ATTRIBUTE_FILTER', 'next': 'BAND_SELECT'}]
- owner_ruling: ______（repeated_execution / loop_structure / batch_same_op / not_an_error）

## k=377 — Task: Estimate land surface temperature

Task: Estimate land surface temperature
Estimate monthly Land Surface Temperature (LST) from Landsat 8 Collection 1 Tier 1 Surface Reflectance data using a radiative transfer-based algorithm that incorporates NDVI-derived vegetation fraction and emissivity corrections over the Sinni area between April 2017 and March 2019.

- 预分类: **repeated_execution(same op over time/objects)**
- gold ITERATIVE 位置: [{'seq': 2, 'repeat': 1, 'prev': 'RASTER_LOAD', 'next': 'TEMPORAL_FILTER'}, {'seq': 6, 'repeat': 1, 'prev': 'RASTER_LOAD', 'next': 'TEMPORAL_FILTER'}, {'seq': 10, 'repeat': 1, 'prev': 'RASTER_LOAD', 'next': 'TEMPORAL_FILTER'}, {'seq': 14, 'repeat': 1, 'prev': 'RASTER_LOAD', 'next': 'TEMPORAL_FILTER'}, {'seq': 18, 'repeat': 1, 'prev': 'RASTER_LOAD', 'next': 'TEMPORAL_FILTER'}, {'seq': 22, 'repeat': 1, 'prev': 'RASTER_LOAD', 'next': 'TEMPORAL_FILTER'}, {'seq': 26, 'repeat': 1, 'prev': 'RASTER_LOAD', 'next': 'TEMPORAL_FILTER'}, {'seq': 30, 'repeat': 1, 'prev': 'RASTER_LOAD', 'next': 'TEMPORAL_FILTER'}, {'seq': 34, 'repeat': 1, 'prev': 'RASTER_LOAD', 'next': 'TEMPORAL_FILTER'}, {'seq': 38, 'repeat': 1, 'prev': 'RASTER_LOAD', 'next': 'TEMPORAL_FILTER'}, {'seq': 42, 'repeat': 1, 'prev': 'RASTER_LOAD', 'next': 'TEMPORAL_FILTER'}, {'seq': 46, 'repeat': 1, 'prev': 'RASTER_LOAD', 'next': 'TEMPORAL_FILTER'}, {'seq': 50, 'repeat': 1, 'prev': 'RASTER_LOAD', 'next': 'TEMPORAL_FILTER'}, {'seq': 54, 'repeat': 1, 'prev': 'RASTER_LOAD', 'next': 'TEMPORAL_FILTER'}, {'seq': 58, 'repeat': 1, 'prev': 'RASTER_LOAD', 'next': 'TEMPORAL_FILTER'}, {'seq': 62, 'repeat': 1, 'prev': 'RASTER_LOAD', 'next': 'TEMPORAL_FILTER'}, {'seq': 66, 'repeat': 1, 'prev': 'RASTER_LOAD', 'next': 'TEMPORAL_FILTER'}, {'seq': 70, 'repeat': 1, 'prev': 'RASTER_LOAD', 'next': 'TEMPORAL_FILTER'}, {'seq': 74, 'repeat': 1, 'prev': 'RASTER_LOAD', 'next': 'TEMPORAL_FILTER'}, {'seq': 78, 'repeat': 1, 'prev': 'RASTER_LOAD', 'next': 'TEMPORAL_FILTER'}, {'seq': 82, 'repeat': 1, 'prev': 'RASTER_LOAD', 'next': 'TEMPORAL_FILTER'}, {'seq': 86, 'repeat': 1, 'prev': 'RASTER_LOAD', 'next': 'TEMPORAL_FILTER'}, {'seq': 90, 'repeat': 1, 'prev': 'RASTER_LOAD', 'next': 'TEMPORAL_FILTER'}, {'seq': 94, 'repeat': 1, 'prev': 'RASTER_LOAD', 'next': 'TEMPORAL_FILTER'}]
- owner_ruling: ______（repeated_execution / loop_structure / batch_same_op / not_an_error）

## k=398 — Task: Generate annual max NDVI composite

Task: Generate annual max NDVI composite
Create an annual cloud-masked Landsat 8 surface reflectance composite for 2020 using the maximum NDVI value from each pixel over time. It processes a regional image collection by applying cloud masking, computing NDVI for each image, and compositing using the max-NDVI criterion. Outputs include a false-color mosaic, NDVI layer, and a final composite exported to Earth Engine Assets.

- 预分类: **repeated_execution(same op over time/objects)**
- gold ITERATIVE 位置: [{'seq': 10, 'repeat': 1, 'prev': 'SPATIAL_FILTER', 'next': None}]
- owner_ruling: ______（repeated_execution / loop_structure / batch_same_op / not_an_error）

## k=425 — Task: Count good observations by time window

Task: Count good observations by time window
the workflow counts the number of valid (good quality) optical satellite observations across seven monthly time windows in 2022 over Hainan Island. It processes Landsat 7, Landsat 8, and Sentinel-2 surface reflectance data, applying sensor-specific cloud and shadow masking using QA bands and terrain-based shadow detection. For each time window, it merges observations from all sensors, sums them into a single band indicating observation frequency, clip

- 预分类: **repeated_execution(same op over time/objects)**
- gold ITERATIVE 位置: [{'seq': 6, 'repeat': 1, 'prev': 'BAND_SELECT', 'next': 'BAND_SELECT'}, {'seq': 13, 'repeat': 1, 'prev': 'BAND_SELECT', 'next': 'BAND_SELECT'}, {'seq': 20, 'repeat': 1, 'prev': 'BAND_SELECT', 'next': 'BAND_SELECT'}]
- owner_ruling: ______（repeated_execution / loop_structure / batch_same_op / not_an_error）

## k=442 — Task: Estimate urban heat island intensity

Task: Estimate urban heat island intensity
Estimate Urban Heat Island (UHI) intensity by comparing land surface temperature (LST) between urban and non-urban areas using MODIS LST data from 2017. It first masks MODIS land cover data to separate urban (LC_Type1 = 13) and non-urban regions, applies these masks to MOD11A1 LST data, computes mean LST for each region over time, calculates the difference (UHI = urban LST - non-urban LST), and outputs a UHI image collection, time series chart, and poin

- 预分类: **repeated_execution(same op over time/objects)**
- gold ITERATIVE 位置: [{'seq': 4, 'repeat': 1, 'prev': 'BAND_SELECT', 'next': 'RASTER_LOAD'}, {'seq': 8, 'repeat': 1, 'prev': 'BAND_SELECT', 'next': 'RASTER_LOAD'}, {'seq': 11, 'repeat': 1, 'prev': 'TEMPORAL_FILTER', 'next': 'AGGREGATION'}, {'seq': 15, 'repeat': 1, 'prev': 'TEMPORAL_FILTER', 'next': 'AGGREGATION'}]
- owner_ruling: ______（repeated_execution / loop_structure / batch_same_op / not_an_error）

## k=494 — Task: Estimate land surface temperature

Task: Estimate land surface temperature
Estimate land surface temperature (LST) in Sarepole Zahab using Landsat 8 Top of Atmosphere (TOA) reflectance and thermal data from November 2016 and October–December 2017. It computes NDVI from visible and near-infrared bands, derives land surface emissivity through a threshold-based classification of NDVI values, and calculates at-sensor radiance and brightness temperature from Band 10 (TIRS). LST is then retrieved using a radiative transfer equation tha

- 预分类: **repeated_execution(same op over time/objects)**
- gold ITERATIVE 位置: [{'seq': 7, 'repeat': 1, 'prev': 'TEMPORAL_FILTER', 'next': 'AGGREGATION'}]
- owner_ruling: ______（repeated_execution / loop_structure / batch_same_op / not_an_error）

## k=514 — Task: Analyze surface water extent and climate variables

Task: Analyze surface water extent and climate variables
Analyze monthly surface water extent from the JRC Global Surface Water dataset and climate variables (actual evapotranspiration and PDSI) from the TerraClimate dataset over a specific Arctic region between 2000 and 2001, with reprojected and resolution-reduced outputs for consistent analysis.

- 预分类: **repeated_execution(same op over time/objects)**
- gold ITERATIVE 位置: [{'seq': 7, 'repeat': 2, 'prev': 'AGGREGATION', 'next': 'RASTER_LOAD'}]
- owner_ruling: ______（repeated_execution / loop_structure / batch_same_op / not_an_error）

## k=561 — Task: Analyze vegetation and water indices

Task: Analyze vegetation and water indices
Calculate and visualizes NDVI, EVI, and LSWI vegetation and moisture indices from Landsat 8 TOA reflectance data over a specified region of interest. It generates mean composite images of these indices, displays them on the map with custom visualization parameters, creates a time-series chart of average NDVI and EVI values, and exports the index maps to Google Drive.

- 预分类: **repeated_execution(same op over time/objects)**
- gold ITERATIVE 位置: [{'seq': 4, 'repeat': 2, 'prev': 'SPATIAL_FILTER', 'next': 'RASTER_LOAD'}, {'seq': 8, 'repeat': 2, 'prev': 'SPATIAL_FILTER', 'next': 'AGGREGATION'}]
- owner_ruling: ______（repeated_execution / loop_structure / batch_same_op / not_an_error）

## k=572 — Task: Analyze vegetation change over time

Task: Analyze vegetation change over time
Analyze changes in vegetation over two time periods using Sentinel-2 imagery. It computes median NDVI images before and after a given event (aE, bE), applies cloud masking, clips to a region of interest, and calculates the relative change (normalized difference) between the two periods. The output includes false-color composite images for each period and a change map highlighting areas of increase or decrease in vegetation, visualized using near-infrared

- 预分类: **repeated_execution(same op over time/objects)**
- gold ITERATIVE 位置: [{'seq': 5, 'repeat': 1, 'prev': 'SPATIAL_FILTER', 'next': 'RASTER_LOAD'}, {'seq': 9, 'repeat': 1, 'prev': 'SPATIAL_FILTER', 'next': None}]
- owner_ruling: ______（repeated_execution / loop_structure / batch_same_op / not_an_error）

## k=580 — Task: Analyze NDVI over time

Task: Analyze NDVI over time
Calculate and visualizes NDVI over Utah from MODIS MOD09Q1 data between 2010 and 2019, applying a water mask and hillshade for enhanced visualization, and provides an interactive time series chart of NDVI at clicked locations.

- 预分类: **repeated_execution(same op over time/objects)**
- gold ITERATIVE 位置: [{'seq': 5, 'repeat': 1, 'prev': 'TEMPORAL_FILTER', 'next': 'RASTER_LOAD'}]
- owner_ruling: ______（repeated_execution / loop_structure / batch_same_op / not_an_error）

## k=638 — Task: Analyze vegetation indices over time

Task: Analyze vegetation indices over time
Calculate and visualizes NDVI, NDWI, and EVI vegetation indices from Landsat 8 surface reflectance data over a buffered geometry between 2013 and 2021, producing a time series chart of median values at 30m scale.

- 预分类: **repeated_execution(same op over time/objects)**
- gold ITERATIVE 位置: [{'seq': 4, 'repeat': 1, 'prev': 'TEMPORAL_FILTER', 'next': 'AGGREGATION'}]
- owner_ruling: ______（repeated_execution / loop_structure / batch_same_op / not_an_error）

## k=673 — Task: Analyze vegetation density and water index

Task: Analyze vegetation density and water index
Analyze vegetation health, water content, and fuel moisture in a study area using Sentinel-2A/B surface reflectance data from 2020. It applies cloud masking via the QA60 band, computes NDVI, NDWI, and NDFI indices, and classifies each into discrete categories representing varying levels of vegetation density and moisture conditions. The output includes a median composite image, three classified raster maps (NDVI, NDWI, NDFI) visualized with color 

- 预分类: **undetermined**
- gold ITERATIVE 位置: [{'seq': 4, 'repeat': 1, 'prev': 'ATTRIBUTE_FILTER', 'next': 'AGGREGATION'}]
- owner_ruling: ______（repeated_execution / loop_structure / batch_same_op / not_an_error）

## k=706 — Task: Analyze NDVI time series by land type

Task: Analyze NDVI time series by land type
Analyze and compares NDVI time series from Landsat 8 and MODIS over different land cover types (canyon, residential, built-up) near San Diego in 2018, generating temporal charts of mean NDVI and EVI values for spatial comparison.

- 预分类: **repeated_execution(same op over time/objects)**
- gold ITERATIVE 位置: [{'seq': 3, 'repeat': 1, 'prev': 'TEMPORAL_FILTER', 'next': 'RASTER_LOAD'}]
- owner_ruling: ______（repeated_execution / loop_structure / batch_same_op / not_an_error）

## k=710 — Task: Analyze NDVI time series for farm

Task: Analyze NDVI time series for farm
Analyze the NDVI time series from Sentinel-2 data over a specific farm (Farm_ID: Farmer_39) between 2020 and 2023, generating a median composite, NDVI visualization, and a line chart of mean NDVI values over time. It also exports the NDVI image collection to Google Drive.

- 预分类: **repeated_execution(same op over time/objects)**
- gold ITERATIVE 位置: [{'seq': 5, 'repeat': 1, 'prev': 'TEMPORAL_FILTER', 'next': 'AGGREGATION'}]
- owner_ruling: ______（repeated_execution / loop_structure / batch_same_op / not_an_error）

## k=745 — Task: Map surface water extent

Task: Map surface water extent
Analyze surface water dynamics in a study area using MNDWI derived from Landsat 5, 7, and 8 surface reflectance imagery between 1997 and 2021. It applies sensor-specific cloud masking to ensure data quality, computes MNDWI for water detection, and generates two composite water maps: one for the rainy season (June–October) using the 90th percentile and another for the dry season (November–May). Additionally, it calculates annual surface water extent (in km²) by comp

- 预分类: **repeated_execution(same op over time/objects)**
- gold ITERATIVE 位置: [{'seq': 6, 'repeat': 1, 'prev': 'TEMPORAL_FILTER', 'next': 'RASTER_LOAD'}, {'seq': 10, 'repeat': 1, 'prev': 'TEMPORAL_FILTER', 'next': 'RASTER_LOAD'}, {'seq': 14, 'repeat': 1, 'prev': 'TEMPORAL_FILTER', 'next': 'AGGREGATION'}]
- owner_ruling: ______（repeated_execution / loop_structure / batch_same_op / not_an_error）

## k=762 — Task: Analyze NDVI and backscatter time series

Task: Analyze NDVI and backscatter time series
Analyze temporal patterns of vegetation (via NDVI from Landsat 8 and Sentinel-2) and radar backscatter (VV/VH from Sentinel-1) over a specified region and time period. It computes NDVI for optical collections, applies cloud masking to Landsat and Sentinel-2, merges NDVI results, and generates two time series charts: one for VV/VH backscatter coefficients from Sentinel-1 and another for mean NDVI values from both sensors. The output includes interact

- 预分类: **repeated_execution(same op over time/objects)**
- gold ITERATIVE 位置: [{'seq': 8, 'repeat': 1, 'prev': 'SPATIAL_FILTER', 'next': 'RASTER_LOAD'}, {'seq': 12, 'repeat': 1, 'prev': 'SPATIAL_FILTER', 'next': 'AGGREGATION'}]
- owner_ruling: ______（repeated_execution / loop_structure / batch_same_op / not_an_error）

## k=817 — Task: Extract cloud-masked Landsat imagery

Task: Extract cloud-masked Landsat imagery
Filter and processes Landsat 8 surface reflectance data within a user-defined boundary, removes clouds and cloud shadows using pixel_qa band, clips images to the region of interest, and exports each image in the collection to Google Drive. The output is a series of clipped, cloud-cleared Landsat 8 images from 2015.

- 预分类: **undetermined**
- gold ITERATIVE 位置: [{'seq': 5, 'repeat': 1, 'prev': 'ATTRIBUTE_FILTER', 'next': 'AGGREGATION'}]
- owner_ruling: ______（repeated_execution / loop_structure / batch_same_op / not_an_error）

## k=847 — Task: Analyze NDVI time series

Task: Analyze NDVI time series
Analyze the temporal dynamics of vegetation health in the DryPunaSajama region using MODIS NDVI data from 2000 to 2021, generating a time-series line chart of mean NDVI values and visualizing the NDVI imagery over the study area.

- 预分类: **repeated_execution(same op over time/objects)**
- gold ITERATIVE 位置: [{'seq': 4, 'repeat': 1, 'prev': 'ATTRIBUTE_FILTER', 'next': 'AGGREGATION'}, {'seq': 9, 'repeat': 1, 'prev': 'ATTRIBUTE_FILTER', 'next': 'AGGREGATION'}, {'seq': 14, 'repeat': 1, 'prev': 'ATTRIBUTE_FILTER', 'next': 'AGGREGATION'}, {'seq': 19, 'repeat': 1, 'prev': 'ATTRIBUTE_FILTER', 'next': 'AGGREGATION'}]
- owner_ruling: ______（repeated_execution / loop_structure / batch_same_op / not_an_error）

## k=848 — Task: Analyze cloud and cirrus presence

Task: Analyze cloud and cirrus presence
Analyze cloud and cirrus pixel coverage in Sentinel-2 surface reflectance images over a specific region between January and June 2020, using the QA60 band to derive per-pixel cloud/cirrus masks. It generates time-series charts of cloudiness distribution, identifies the least cloudy image, and exports NDVI visualizations and masked imagery for further analysis.

- 预分类: **repeated_execution(same op over time/objects)**
- gold ITERATIVE 位置: [{'seq': 7, 'repeat': 1, 'prev': 'BAND_SELECT', 'next': 'RASTER_LOAD'}]
- owner_ruling: ______（repeated_execution / loop_structure / batch_same_op / not_an_error）

## k=849 — Task: Extract riparian forest NDVI along rivers

Task: Extract riparian forest NDVI along rivers
Analyze riparian forests along three major rivers in California (Santa Clara River, Salinas River, and South Fork Kern River) using NDVI derived from Landsat 7 Collection 2 Level 2 surface reflectance data from 2000 to 2021. It first identifies riparian forest areas by clipping a precomputed forest layer to 500-meter buffers around river segments. Then, for each cloud-masked image within the summer season (July 1–September 30) and with less than 20

- 预分类: **repeated_execution(same op over time/objects)**
- gold ITERATIVE 位置: [{'seq': 20, 'repeat': 1, 'prev': 'ATTRIBUTE_FILTER', 'next': 'AGGREGATION'}]
- owner_ruling: ______（repeated_execution / loop_structure / batch_same_op / not_an_error）

## k=872 — Task: Extract tropospheric CO time series

Task: Extract tropospheric CO time series
Extract daily mean tropospheric carbon monoxide (CO) column number density values over a 7-km buffered region centered on the Port of Sines, Portugal (coordinates [-8.8667, 37.9500]), using Sentinel-5P Level 3 offline CO data for 2024. It applies cloud masking (cloud_fraction < 0.3), computes spatial means within the buffered region, handles null/missing values by assigning -9999, generates a FeatureCollection with date and CO value attributes, prints th

- 预分类: **repeated_execution(same op over time/objects)**
- gold ITERATIVE 位置: [{'seq': 4, 'repeat': 1, 'prev': 'SPATIAL_FILTER', 'next': 'AGGREGATION'}]
- owner_ruling: ______（repeated_execution / loop_structure / batch_same_op / not_an_error）

## k=921 — Task: Filter non-cloudy MODIS images

Task: Filter non-cloudy MODIS images
Calculate the non-cloud ratio for each 8-day MODIS MOD09A1 image by masking cloudy pixels using the StateQA band, then filters the collection to retain only those images where at least 98% of the region of interest is free of clouds.

- 预分类: **repeated_execution(same op over time/objects)**
- gold ITERATIVE 位置: [{'seq': 11, 'repeat': 1, 'prev': 'SPATIAL_FILTER', 'next': 'ATTRIBUTE_FILTER'}]
- owner_ruling: ______（repeated_execution / loop_structure / batch_same_op / not_an_error）

## k=936 — Task: Analyze NBR over time

Task: Analyze NBR over time
Calculate the Normalized Burn Ratio (NBR) from Landsat 8 TOA reflectance data within a point of interest, masks pixels based on cloud score (≤20), computes mean NBR values at the point, and generates a time series line chart of NBR values versus acquisition dates.

- 预分类: **repeated_execution(same op over time/objects)**
- gold ITERATIVE 位置: [{'seq': 4, 'repeat': 1, 'prev': 'TEMPORAL_FILTER', 'next': 'AGGREGATION'}]
- owner_ruling: ______（repeated_execution / loop_structure / batch_same_op / not_an_error）

## k=985 — Task: Analyze vegetation health using indices

Task: Analyze vegetation health using indices
Generate a median composite of Sentinel-2 surface reflectance data over Ethiopia, computes spectral indices (NDVI, EVI, NDWI, NBR), and visualizes them with color palettes. It allows interactive selection of compositing periods, cloud thresholds, band combinations, and exports the resulting image. Clicking on the map produces a time series chart of the selected index at that location.

- 预分类: **repeated_execution(same op over time/objects)**
- gold ITERATIVE 位置: [{'seq': 5, 'repeat': 1, 'prev': 'ATTRIBUTE_FILTER', 'next': 'EXPORT_OUTPUT'}]
- owner_ruling: ______（repeated_execution / loop_structure / batch_same_op / not_an_error）

## k=1002 — Task: Estimate annual population distribution

Task: Estimate annual population distribution
Estimate the mean annual population distribution for 2020 using WorldPop high-resolution gridded population data. It filters the WorldPop ImageCollection to China within a user-defined geometry, computes the temporal mean of population counts across 2020, clips the result to the study area, and visualizes it on the map with a custom color palette. Additionally, it generates a time series chart of total population dynamics by region using sum reductio

- 预分类: **repeated_execution(same op over time/objects)**
- gold ITERATIVE 位置: [{'seq': 3, 'repeat': 1, 'prev': 'SPATIAL_FILTER', 'next': 'ATTRIBUTE_FILTER'}]
- owner_ruling: ______（repeated_execution / loop_structure / batch_same_op / not_an_error）

## k=1011 — Task: Detect surface water change

Task: Detect surface water change
Detect changes in surface water extent between two time periods (2020 and 2021) using NDWI derived from Landsat 8 Surface Reflectance imagery. It applies cloud masking, computes median composites before and after the period, thresholds NDWI at 0.05 to identify water, calculates water loss and gain by differencing pre- and post-period images, masks non-water and no-data pixels, computes area in km² using pixel area, and outputs map visualizations of before/after 

- 预分类: **repeated_execution(same op over time/objects)**
- gold ITERATIVE 位置: [{'seq': 5, 'repeat': 1, 'prev': 'ATTRIBUTE_FILTER', 'next': 'RASTER_LOAD'}, {'seq': 10, 'repeat': 1, 'prev': 'ATTRIBUTE_FILTER', 'next': 'BAND_ARITHMETIC'}]
- owner_ruling: ______（repeated_execution / loop_structure / batch_same_op / not_an_error）

## k=1034 — Task: Extract cloud-scored Sentinel-2 imagery

Task: Extract cloud-scored Sentinel-2 imagery
Process Sentinel-2 Surface Reflectance (S2_SR) imagery over a defined region from 2020 to 2021, applying scaling, cloud masking using a custom cloud scoring algorithm and QA60 band filtering, and clipping to the region of interest. It outputs the processed image collection size for inspection, with each image including a computed cloud score band and masked pixels based on cloud likelihood. The final output is a cleaned, cloud-filtered image collecti

- 预分类: **undetermined**
- gold ITERATIVE 位置: [{'seq': 4, 'repeat': 1, 'prev': 'SPATIAL_FILTER', 'next': None}]
- owner_ruling: ______（repeated_execution / loop_structure / batch_same_op / not_an_error）

## k=1061 — Task: Analyze NDVI time series

Task: Analyze NDVI time series
Analyze temporal changes in vegetation health across multiple locations in Uzbekistan using NDVI derived from Landsat 5 and Landsat 8 surface reflectance imagery between 1984 and 2019. It computes NDVI for two different sensor configurations (Landsat 5 TM: B4/B3; Landsat 8 OLI: B5/B4), applies no cloud masking beyond fmask usage in function definition (though not applied in final collections), and generates a time-series scatter chart of mean NDVI values per locati

- 预分类: **repeated_execution(same op over time/objects)**
- gold ITERATIVE 位置: [{'seq': 6, 'repeat': 1, 'prev': 'BAND_SELECT', 'next': 'AGGREGATION'}, {'seq': 12, 'repeat': 1, 'prev': 'BAND_SELECT', 'next': 'AGGREGATION'}, {'seq': 18, 'repeat': 1, 'prev': 'BAND_SELECT', 'next': 'AGGREGATION'}, {'seq': 24, 'repeat': 1, 'prev': 'BAND_SELECT', 'next': 'AGGREGATION'}, {'seq': 30, 'repeat': 1, 'prev': 'BAND_SELECT', 'next': 'AGGREGATION'}, {'seq': 36, 'repeat': 1, 'prev': 'BAND_SELECT', 'next': 'AGGREGATION'}, {'seq': 42, 'repeat': 1, 'prev': 'BAND_SELECT', 'next': 'AGGREGATION'}, {'seq': 48, 'repeat': 1, 'prev': 'BAND_SELECT', 'next': 'AGGREGATION'}, {'seq': 54, 'repeat': 1, 'prev': 'BAND_SELECT', 'next': 'AGGREGATION'}, {'seq': 60, 'repeat': 1, 'prev': 'BAND_SELECT', 'next': 'AGGREGATION'}, {'seq': 66, 'repeat': 1, 'prev': 'BAND_SELECT', 'next': 'AGGREGATION'}, {'seq': 72, 'repeat': 1, 'prev': 'BAND_SELECT', 'next': 'AGGREGATION'}, {'seq': 78, 'repeat': 1, 'prev': 'BAND_SELECT', 'next': 'AGGREGATION'}, {'seq': 84, 'repeat': 1, 'prev': 'BAND_SELECT', 'next': 'AGGREGATION'}, {'seq': 90, 'repeat': 1, 'prev': 'BAND_SELECT', 'next': 'AGGREGATION'}, {'seq': 96, 'repeat': 1, 'prev': 'BAND_SELECT', 'next': 'AGGREGATION'}]
- owner_ruling: ______（repeated_execution / loop_structure / batch_same_op / not_an_error）

## k=1069 — Task: Compute EVI from Sentinel-2 imagery

Task: Compute EVI from Sentinel-2 imagery
Calculate the Enhanced Vegetation Index (EVI) from Sentinel-2A/B Surface Reflectance data over a specific region for four overlapping weekly periods in April 2020. It applies cloud and cirrus masking using the QA60 band, filters images by cloud cover (<10%), computes EVI using blue (B2), red (B4), and near-infrared (B8) bands scaled by 10,000, then generates a median EVI composite for each period. Outputs include printed image collections, map visualizat

- 预分类: **repeated_execution(same op over time/objects)**
- gold ITERATIVE 位置: [{'seq': 5, 'repeat': 1, 'prev': 'ATTRIBUTE_FILTER', 'next': 'RASTER_LOAD'}, {'seq': 10, 'repeat': 1, 'prev': 'ATTRIBUTE_FILTER', 'next': 'RASTER_LOAD'}, {'seq': 15, 'repeat': 1, 'prev': 'ATTRIBUTE_FILTER', 'next': 'RASTER_LOAD'}, {'seq': 20, 'repeat': 1, 'prev': 'ATTRIBUTE_FILTER', 'next': None}]
- owner_ruling: ______（repeated_execution / loop_structure / batch_same_op / not_an_error）

## k=1090 — Task: Classify land cover types

Task: Classify land cover types
Classify land cover types in Olavarría using training samples for five classes: Agua, Area_no_vegetada, Cultivos, Lenosas, and Herbacea_natural. It leverages Landsat 8 surface reflectance imagery from 2016 to 2020 and MODIS NDVI data from 2020 to compute NDVI time series. The workflow includes cloud masking, NDVI calculation, and the creation of interactive charts via click events on a map, where users can view temporal NDVI profiles from Landsat and MODIS at spec

- 预分类: **repeated_execution(same op over time/objects)**
- gold ITERATIVE 位置: [{'seq': 19, 'repeat': 1, 'prev': 'RASTER_LOAD', 'next': 'GEOMETRY_DEFINE'}]
- owner_ruling: ______（repeated_execution / loop_structure / batch_same_op / not_an_error）

## k=1138 — Task: Analyze NDMI vegetation moisture

Task: Analyze NDMI vegetation moisture
Analyze vegetation moisture conditions in Thailand using the Normalized Difference Moisture Index (NDMI) derived from Sentinel-2A/B SR surface reflectance data between January and July 2022. It applies cloud masking based on QA60 band, computes NDMI using bands B8 and B11, generates a maximum-value composite of NDMI over time, clips it to Thailand's boundary, and visualizes the result on the map. Additionally, it creates a time series line chart of maximum 

- 预分类: **repeated_execution(same op over time/objects)**
- gold ITERATIVE 位置: [{'seq': 9, 'repeat': 1, 'prev': 'BAND_SELECT', 'next': 'AGGREGATION'}]
- owner_ruling: ______（repeated_execution / loop_structure / batch_same_op / not_an_error）

## k=1160 — Task: Map surface water extent monthly

Task: Map surface water extent monthly
Analyze surface water dynamics from January 2000 to January 2021 using the JRC Global Surface Water (GSW) Monthly History dataset. It filters the image collection to the specified time range, applies pixel reduction using mean resampling to handle mixed pixels, reprojects the images to a common CRS (EPSG:4326) at 1000m scale, selects the 'water' band indicating water occurrence states (no water, seasonal, permanent), and visualizes the first image in the pr

- 预分类: **repeated_execution(same op over time/objects)**
- gold ITERATIVE 位置: [{'seq': 4, 'repeat': 2, 'prev': 'AGGREGATION', 'next': None}]
- owner_ruling: ______（repeated_execution / loop_structure / batch_same_op / not_an_error）

## k=1163 — Task: Analyze NDVI time series

Task: Analyze NDVI time series
Analyze the temporal pattern of NDVI at a specific point location using Sentinel-2 surface reflectance imagery from 2016 to 2022. It applies cloud masking based on the Scene Classification Layer (SCL), computes NDVI using bands B8 and B4, and generates a time series chart of mean NDVI values over the point. The output is an interactive chart visualizing NDVI dynamics over time, intended for monitoring vegetation behavior at that location.

- 预分类: **repeated_execution(same op over time/objects)**
- gold ITERATIVE 位置: [{'seq': 5, 'repeat': 1, 'prev': 'SPATIAL_FILTER', 'next': 'AGGREGATION'}]
- owner_ruling: ______（repeated_execution / loop_structure / batch_same_op / not_an_error）

## k=1211 — Task: Compute NDVI for summer period

Task: Compute NDVI for summer period
Compute the maximum NDVI value over the austral summer period (2019-12-21 to 2020-03-20) using Landsat 8 surface reflectance imagery. It applies cloud filtering (CLOUD_COVER < 99%), calculates NDVI via an expression using NIR (B4) and red (B3) bands, takes the pixel-wise maximum across the time series, clips the result to the 'puq' region, and visualizes it with a color palette from red to dark green. The final NDVI raster is exported to Google Drive.

- 预分类: **repeated_execution(same op over time/objects)**
- gold ITERATIVE 位置: [{'seq': 4, 'repeat': 1, 'prev': 'TEMPORAL_FILTER', 'next': None}]
- owner_ruling: ______（repeated_execution / loop_structure / batch_same_op / not_an_error）

## k=1232 — Task: Monitor wheat and rice cultivation NDVI

Task: Monitor wheat and rice cultivation NDVI
Analyze NDVI time series for wheat and rice cultivation areas in Uttar Pradesh, India, using Sentinel-2 surface reflectance data from 2019. It masks clouds and shadows, computes NDVI from bands B8 and B4, samples farm locations within the cropped area identified by GFSAD, and generates a temporal NDVI chart at a single farm point. Outputs include a median composite image of the study area, mapped farm sample points, and a time-series chart of NDVI va

- 预分类: **repeated_execution(same op over time/objects)**
- gold ITERATIVE 位置: [{'seq': 7, 'repeat': 1, 'prev': 'TEMPORAL_FILTER', 'next': 'SPATIAL_FILTER'}]
- owner_ruling: ______（repeated_execution / loop_structure / batch_same_op / not_an_error）

## k=1262 — Task: Map forest change and hydrology

Task: Map forest change and hydrology
the workflow quantifies forest cover change between 2000 and 2020 in the Nilgiris District using NDVI-derived binary forest/non-forest classifications from Landsat 5 and Landsat 8 surface reflectance data. It computes forest loss, gain, and stability classes via pixel-wise logical comparison, integrates JRC Global Surface Water occurrence data (≥50% threshold) to map permanent water bodies, calculates area statistics in km² for each class, visualizes four th

- 预分类: **repeated_execution(same op over time/objects)**
- gold ITERATIVE 位置: [{'seq': 5, 'repeat': 1, 'prev': 'ATTRIBUTE_FILTER', 'next': 'AGGREGATION'}, {'seq': 11, 'repeat': 1, 'prev': 'ATTRIBUTE_FILTER', 'next': 'AGGREGATION'}]
- owner_ruling: ______（repeated_execution / loop_structure / batch_same_op / not_an_error）

## k=1274 — Task: Estimate annual population distribution

Task: Estimate annual population distribution
Estimate the mean annual population distribution for China in 2020 using WorldPop 100m resolution data. It filters the WorldPop Global Population dataset for China within a user-defined geometry, computes the yearly mean population density, clips it to the region of interest, and visualizes it on the map with a custom palette. Additionally, it generates a time series chart of total population dynamics by region using sum reduction over time and expor

- 预分类: **repeated_execution(same op over time/objects)**
- gold ITERATIVE 位置: [{'seq': 3, 'repeat': 1, 'prev': 'SPATIAL_FILTER', 'next': 'ATTRIBUTE_FILTER'}]
- owner_ruling: ______（repeated_execution / loop_structure / batch_same_op / not_an_error）

## k=1292 — Task: Analyze forest NBR change

Task: Analyze forest NBR change
Analyze changes in the Normalized Burn Ratio (NBR) over forested areas in Europe before and after a fire event by using MODIS MCD43A4 surface reflectance data from 2005 to 2012, masked with CORINE Land Cover data to retain only forest areas (class values >=24). It computes mean NBR for pre-fire (2006), fire-year (2007), and post-fire (2011–2012) periods, then generates a time series chart of regional mean NBR values over Europe.

- 预分类: **repeated_execution(same op over time/objects)**
- gold ITERATIVE 位置: [{'seq': 4, 'repeat': 1, 'prev': 'SPATIAL_FILTER', 'next': 'BAND_SELECT'}, {'seq': 10, 'repeat': 1, 'prev': 'SPATIAL_FILTER', 'next': 'BAND_SELECT'}, {'seq': 18, 'repeat': 1, 'prev': 'SPATIAL_FILTER', 'next': 'BAND_SELECT'}, {'seq': 24, 'repeat': 1, 'prev': 'SPATIAL_FILTER', 'next': 'BAND_SELECT'}, {'seq': 26, 'repeat': 1, 'prev': 'BAND_SELECT', 'next': 'RASTER_LOAD'}, {'seq': 30, 'repeat': 1, 'prev': 'SPATIAL_FILTER', 'next': 'BAND_SELECT'}, {'seq': 32, 'repeat': 1, 'prev': 'BAND_SELECT', 'next': 'RASTER_LOAD'}, {'seq': 36, 'repeat': 1, 'prev': 'SPATIAL_FILTER', 'next': 'BAND_SELECT'}, {'seq': 38, 'repeat': 1, 'prev': 'BAND_SELECT', 'next': 'RASTER_LOAD'}, {'seq': 42, 'repeat': 1, 'prev': 'SPATIAL_FILTER', 'next': 'BAND_SELECT'}, {'seq': 44, 'repeat': 1, 'prev': 'BAND_SELECT', 'next': 'RASTER_LOAD'}, {'seq': 48, 'repeat': 1, 'prev': 'SPATIAL_FILTER', 'next': 'BAND_SELECT'}]
- owner_ruling: ______（repeated_execution / loop_structure / batch_same_op / not_an_error）

## k=1296 — Task: Estimate lake surface area

Task: Estimate lake surface area
Estimate monthly lake surface areas using MNDWI from Landsat 5 and 7 data between February 1990 and March 2022, applying cloud masking, SLC-off gap correction for Landsat 7, and filtering composites based on cloud cover and pixel coverage within the region of interest. Outputs include a time series of lake surface areas in km², exported as a CSV file and visualized as a scatter chart.

- 预分类: **repeated_execution(same op over time/objects)**
- gold ITERATIVE 位置: [{'seq': 4, 'repeat': 1, 'prev': 'SPATIAL_FILTER', 'next': 'BAND_SELECT'}, {'seq': 6, 'repeat': 1, 'prev': 'BAND_SELECT', 'next': 'RASTER_LOAD'}, {'seq': 10, 'repeat': 1, 'prev': 'SPATIAL_FILTER', 'next': 'TEMPORAL_FILTER'}]
- owner_ruling: ______（repeated_execution / loop_structure / batch_same_op / not_an_error）

## k=1303 — Task: Extract snow cover from MODIS

Task: Extract snow cover from MODIS
Extract daily NDSI-based snow cover data from the MODIS MYD10A1 product over a user-defined region of interest (roi) for February 2020, visualizes the first image in the collection with a custom color palette, and exports each clipped image as a GeoTIFF to Google Drive with filenames prefixed by 'Snow_Cover_' followed by the system:index. The output includes a printed list of image IDs and individual export tasks triggered via iteration.

- 预分类: **repeated_execution(same op over time/objects)**
- gold ITERATIVE 位置: [{'seq': 4, 'repeat': 1, 'prev': 'SPATIAL_FILTER', 'next': 'AGGREGATION'}]
- owner_ruling: ______（repeated_execution / loop_structure / batch_same_op / not_an_error）

## k=1365 — Task: Analyze NDVI time series at clicked points

Task: Analyze NDVI time series at clicked points
Analyze NDVI time series from Sentinel-2 surface reflectance imagery between 2019 and 2020. It applies cloud masking using the QA60 band and computes NDVI using bands B8 (NIR) and B4 (red). the workflow enables interactive point selection on the map, dynamically generating a chart of mean NDVI values over time for each clicked location, displayed in a panel. Outputs include mapped point locations and interactive NDVI time series charts per point.

- 预分类: **repeated_execution(same op over time/objects)**
- gold ITERATIVE 位置: [{'seq': 3, 'repeat': 1, 'prev': 'TEMPORAL_FILTER', 'next': 'GEOMETRY_DEFINE'}]
- owner_ruling: ______（repeated_execution / loop_structure / batch_same_op / not_an_error）

## k=1376 — Task: Compute median cloud fraction by day

Task: Compute median cloud fraction by day
Compute the median cloud fraction for each day from May 1 to May 10, 2019, using Sentinel-5P NRTI L3 data over a specified region (krasPoly), producing a time-composited image collection where each image represents the median cloud condition for a specific day of year.

- 预分类: **repeated_execution(same op over time/objects)**
- gold ITERATIVE 位置: [{'seq': 3, 'repeat': 1, 'prev': 'BAND_SELECT', 'next': 'TEMPORAL_FILTER'}]
- owner_ruling: ______（repeated_execution / loop_structure / batch_same_op / not_an_error）

## k=1386 — Task: Identify maize and soybean fields

Task: Identify maize and soybean fields
Identify maize and soybean cropland areas in Iowa using the USDA/NASS Cropland Data Layer (CDL) for 2018–2019. It filters the CDL image collection to a point-based region around Iowa, extracts maize (class 1) and soybean (class 5) classifications by thresholding the 'cropland' band, clips the result to the study area, and visualizes each crop type separately using random color visualization. Additionally, it processes GEDI L2A monthly data from July to Sep

- 预分类: **repeated_execution(same op over time/objects)**
- gold ITERATIVE 位置: [{'seq': 6, 'repeat': 1, 'prev': 'TEMPORAL_FILTER', 'next': 'SPATIAL_FILTER'}]
- owner_ruling: ______（repeated_execution / loop_structure / batch_same_op / not_an_error）

## k=1388 — Task: Assess wildfire impact using NDVI

Task: Assess wildfire impact using NDVI
the workflow assesses the impact of a wildfire by computing and comparing NDVI from Landsat 9 imagery before and after the event in summer 2022. It creates median pre- and post-fire NDVI composites, calculates a difference NDVI image (dNDVI), and generates a time series chart of NDVI trends over user-defined regions (poligonos). Outputs include mapped layers for visualization, a scatter chart of NDVI temporal dynamics, and exports individual images and a s

- 预分类: **repeated_execution(same op over time/objects)**
- gold ITERATIVE 位置: [{'seq': 5, 'repeat': 1, 'prev': 'ATTRIBUTE_FILTER', 'next': 'RASTER_LOAD'}, {'seq': 10, 'repeat': 1, 'prev': 'ATTRIBUTE_FILTER', 'next': 'BAND_SELECT'}, {'seq': 16, 'repeat': 1, 'prev': 'ATTRIBUTE_FILTER', 'next': 'BAND_SELECT'}]
- owner_ruling: ______（repeated_execution / loop_structure / batch_same_op / not_an_error）

## k=1391 — Task: Map annual burn date extent

Task: Map annual burn date extent
Calculate the total annual burned area extent from MODIS MCD64A1 Burn Date data between 2010 and 2019, clipped to a user-defined region (table). For each year, it processes the 'BurnDate' band by summing pixel values after clipping, visualizes each year with a unique color palette, and exports the 2010 result as a GeoTIFF to Google Drive. The output is a time-series of annual fire-affected areas represented as summed burn dates per pixel, intended for change ana

- 预分类: **repeated_execution(same op over time/objects)**
- gold ITERATIVE 位置: [{'seq': 8, 'repeat': 1, 'prev': 'BAND_SELECT', 'next': 'AGGREGATION'}, {'seq': 13, 'repeat': 1, 'prev': 'BAND_SELECT', 'next': 'AGGREGATION'}, {'seq': 18, 'repeat': 1, 'prev': 'BAND_SELECT', 'next': 'AGGREGATION'}, {'seq': 23, 'repeat': 1, 'prev': 'BAND_SELECT', 'next': 'AGGREGATION'}, {'seq': 28, 'repeat': 1, 'prev': 'BAND_SELECT', 'next': 'AGGREGATION'}, {'seq': 33, 'repeat': 1, 'prev': 'BAND_SELECT', 'next': 'AGGREGATION'}, {'seq': 38, 'repeat': 1, 'prev': 'BAND_SELECT', 'next': 'AGGREGATION'}, {'seq': 43, 'repeat': 1, 'prev': 'BAND_SELECT', 'next': 'AGGREGATION'}, {'seq': 48, 'repeat': 1, 'prev': 'BAND_SELECT', 'next': 'AGGREGATION'}, {'seq': 53, 'repeat': 1, 'prev': 'BAND_SELECT', 'next': 'AGGREGATION'}]
- owner_ruling: ______（repeated_execution / loop_structure / batch_same_op / not_an_error）

## k=1472 — Task: Analyze vegetation reflectance trends

Task: Analyze vegetation reflectance trends
Analyze time-series surface reflectance values in the near-infrared (B7) and red (B3) bands from Landsat 7 over a specified geometry, generating a chart of mean pixel values over time to observe vegetation dynamics or land surface changes between 1999 and 2005.

- 预分类: **repeated_execution(same op over time/objects)**
- gold ITERATIVE 位置: [{'seq': 4, 'repeat': 1, 'prev': 'TEMPORAL_FILTER', 'next': 'AGGREGATION'}]
- owner_ruling: ______（repeated_execution / loop_structure / batch_same_op / not_an_error）

## k=1475 — Task: Classify land cover using optical and radar data

Task: Classify land cover using optical and radar data
Classify land cover in the Niayes region using a combination of Landsat 8 surface reflectance, Sentinel-1 SAR, and derived spectral indices (NDVI, NDWI). It applies cloud masking to Landsat and Sentinel-2-like QA60-based masking (though not used), computes NDVI and NDWI, fuses optical, radar, and index bands, and performs Random Forest classification using training samples. Three classifications are generated: (1) using only Landsat spectral

- 预分类: **repeated_execution(same op over time/objects)**
- gold ITERATIVE 位置: [{'seq': 7, 'repeat': 1, 'prev': 'COLLECTION_MGMT', 'next': 'RASTER_LOAD'}]
- owner_ruling: ______（repeated_execution / loop_structure / batch_same_op / not_an_error）

## k=1497 — Task: Extract NDVI and export Sentinel-2 imagery

Task: Extract NDVI and export Sentinel-2 imagery
Process Sentinel-2 surface reflectance data from May to December 2020 over a defined ROI, computes NDVI, sorts images by cloud coverage, and exports the top 1000 images (clipped to the ROI) containing B2, B3, B4, B8, and NDVI bands to Google Drive. It also visualizes each image in the map viewer using true-color composite.

- 预分类: **undetermined**
- gold ITERATIVE 位置: [{'seq': 4, 'repeat': 1, 'prev': 'SPATIAL_FILTER', 'next': None}]
- owner_ruling: ______（repeated_execution / loop_structure / batch_same_op / not_an_error）

## k=1503 — Task: Analyze NDVI change over time

Task: Analyze NDVI change over time
Calculate and visualizes changes in NDVI between multiple dry-season periods (1987–1999, 1999–2013, 2014–2020) using Landsat surface reflectance data, focusing on detecting significant vegetation changes above a threshold of 0.1, masked by land and clipped to a region of interest. Outputs include mapped NDVI change layers and time-series charts for a specified geometry.

- 预分类: **repeated_execution(same op over time/objects)**
- gold ITERATIVE 位置: [{'seq': 5, 'repeat': 1, 'prev': 'SPATIAL_FILTER', 'next': 'COLLECTION_MGMT'}, {'seq': 10, 'repeat': 1, 'prev': 'SPATIAL_FILTER', 'next': 'COLLECTION_MGMT'}, {'seq': 15, 'repeat': 1, 'prev': 'SPATIAL_FILTER', 'next': 'COLLECTION_MGMT'}, {'seq': 20, 'repeat': 1, 'prev': 'SPATIAL_FILTER', 'next': 'COLLECTION_MGMT'}, {'seq': 25, 'repeat': 1, 'prev': 'SPATIAL_FILTER', 'next': 'COLLECTION_MGMT'}, {'seq': 30, 'repeat': 1, 'prev': 'SPATIAL_FILTER', 'next': 'COLLECTION_MGMT'}]
- owner_ruling: ______（repeated_execution / loop_structure / batch_same_op / not_an_error）

## k=1545 — Task: Analyze land surface temperature

Task: Analyze land surface temperature
Calculate and visualizes land surface temperature from Landsat 8 thermal band (B10) data, masked for clouds and cloud shadows, using a median composite from 2018. It also generates a time-series chart of mean temperature values over a specified geometry.

- 预分类: **repeated_execution(same op over time/objects)**
- gold ITERATIVE 位置: [{'seq': 2, 'repeat': 1, 'prev': 'RASTER_LOAD', 'next': 'TEMPORAL_FILTER'}]
- owner_ruling: ______（repeated_execution / loop_structure / batch_same_op / not_an_error）

## k=1546 — Task: Map surface water extent monthly

Task: Map surface water extent monthly
Analyze monthly surface water dynamics from 2000 to 2021 using the JRC Global Surface Water (GSW) dataset. It processes the 'MonthlyHistory' collection by reducing resolution via mean aggregation, reprojecting to a fixed scale and CRS (EPSG:4326 at 1000m), and selecting the 'water' band. The output is a time-series image collection of processed monthly water occurrence images, with the first image visualized on the map using a three-class palette (no water,

- 预分类: **repeated_execution(same op over time/objects)**
- gold ITERATIVE 位置: [{'seq': 4, 'repeat': 2, 'prev': 'AGGREGATION', 'next': None}]
- owner_ruling: ______（repeated_execution / loop_structure / batch_same_op / not_an_error）

## k=1590 — Task: Compute EVI from Sentinel-2 imagery

Task: Compute EVI from Sentinel-2 imagery
Calculate the Enhanced Vegetation Index (EVI) from Sentinel-2 Surface Reflectance imagery over a specific region for four overlapping weekly periods in March 2022. It applies cloud and cirrus masking using the QA60 band, filters images by cloud cover (<10%), computes EVI using B2 (blue), B4 (red), and B8 (NIR) bands scaled by 10,000, then generates a median composite of EVI for each period. The output includes four mean EVI raster maps clipped to the reg

- 预分类: **repeated_execution(same op over time/objects)**
- gold ITERATIVE 位置: [{'seq': 5, 'repeat': 1, 'prev': 'ATTRIBUTE_FILTER', 'next': 'RASTER_LOAD'}, {'seq': 10, 'repeat': 1, 'prev': 'ATTRIBUTE_FILTER', 'next': 'RASTER_LOAD'}, {'seq': 15, 'repeat': 1, 'prev': 'ATTRIBUTE_FILTER', 'next': 'RASTER_LOAD'}, {'seq': 20, 'repeat': 1, 'prev': 'ATTRIBUTE_FILTER', 'next': None}]
- owner_ruling: ______（repeated_execution / loop_structure / batch_same_op / not_an_error）

## k=1594 — Task: Analyze surface reflectance trends

Task: Analyze surface reflectance trends
Analyze time-series surface reflectance values in bands B7 and B3 from Landsat 7 SR data over a specified geometry, generating a chart of mean pixel values over time after applying cloud masking.

- 预分类: **repeated_execution(same op over time/objects)**
- gold ITERATIVE 位置: [{'seq': 4, 'repeat': 1, 'prev': 'TEMPORAL_FILTER', 'next': 'AGGREGATION'}]
- owner_ruling: ______（repeated_execution / loop_structure / batch_same_op / not_an_error）

## k=1595 — Task: Analyze NDVI in study area

Task: Analyze NDVI in study area
Calculate and visualizes NDVI time series from MODIS MOD09Q1 data for a specified study area between day of year 232 and 274 across 2000–2017, masking out permanent water bodies using the JRC Global Surface Water dataset, and generates an animated video of the NDVI progression exported to Google Drive.

- 预分类: **repeated_execution(same op over time/objects)**
- gold ITERATIVE 位置: [{'seq': 6, 'repeat': 1, 'prev': 'ATTRIBUTE_FILTER', 'next': None}]
- owner_ruling: ______（repeated_execution / loop_structure / batch_same_op / not_an_error）

## k=1608 — Task: Analyze vegetation and land cover temporal patterns

Task: Analyze vegetation and land cover temporal patterns
Analyze temporal patterns of multiple vegetation and land surface indices (NDVI, LSWI, EVI, NBR, etc.) and spectral bands across different land cover types (cropland, forest, tea plantations, etc.) in Xishuangbanna, Yunnan, using Landsat 8 and Landsat 7 data from 2018 to 2020. It generates day-of-year composite charts for each index and band, aggregated by region, to compare seasonal dynamics across land cover classes.

- 预分类: **repeated_execution(same op over time/objects)**
- gold ITERATIVE 位置: [{'seq': 5, 'repeat': 1, 'prev': 'TEMPORAL_FILTER', 'next': 'AGGREGATION'}, {'seq': 34, 'repeat': 1, 'prev': 'ATTRIBUTE_FILTER', 'next': 'RASTER_LOAD'}, {'seq': 41, 'repeat': 1, 'prev': 'ATTRIBUTE_FILTER', 'next': 'AGGREGATION'}]
- owner_ruling: ______（repeated_execution / loop_structure / batch_same_op / not_an_error）

## k=1623 — Task: Analyze EVI time series trend

Task: Analyze EVI time series trend
Analyze the temporal trend of Enhanced Vegetation Index (EVI) derived from Sentinel-2 surface reflectance data over Uganda, computes a linear regression to model the trend, and generates both the original and detrended EVI time series charts at a specific point of interest. It also visualizes the trend as a coefficient image.

- 预分类: **repeated_execution(same op over time/objects)**
- gold ITERATIVE 位置: [{'seq': 2, 'repeat': 1, 'prev': 'RASTER_LOAD', 'next': 'SPATIAL_FILTER'}]
- owner_ruling: ______（repeated_execution / loop_structure / batch_same_op / not_an_error）

## k=1630 — Task: Identify land cover clusters

Task: Identify land cover clusters
the workflow segments Sentinel-2 surface reflectance imagery over a user-defined region of interest (initially set to 'congzuo' in Guangxi) using the SNIC (Simple Non-Iterative Clustering) superpixel algorithm. It first applies cloud masking and scaling to the image collection, computes a median composite for 2019, then clips a precomputed UNVI index (Urban Normalized Vegetation Index) to the ROI. The SNIC algorithm generates homogeneous spectral-spatial cluste

- 预分类: **undetermined**
- gold ITERATIVE 位置: [{'seq': 6, 'repeat': 1, 'prev': 'SPATIAL_FILTER', 'next': 'BAND_SELECT'}]
- owner_ruling: ______（repeated_execution / loop_structure / batch_same_op / not_an_error）

## k=1718 — Task: Analyze NDVI time series at clicked points

Task: Analyze NDVI time series at clicked points
Generate a time series of NDVI values from Sentinel-2A/B Surface Reflectance data between 2017 and 2020, masked for clouds using the QA60 band. It enables interactive point selection on the map, where each click creates a mean NDVI time series chart for that location. The output is a dynamic panel displaying the NDVI temporal profile across the specified period, with points visualized in red on the map.

- 预分类: **repeated_execution(same op over time/objects)**
- gold ITERATIVE 位置: [{'seq': 3, 'repeat': 1, 'prev': 'TEMPORAL_FILTER', 'next': 'GEOMETRY_DEFINE'}]
- owner_ruling: ______（repeated_execution / loop_structure / batch_same_op / not_an_error）

## k=1738 — Task: Map annual mean LST and vegetation indices

Task: Map annual mean LST and vegetation indices
Compute and maps the yearly mean values of NDVI (vegetation health), NDBI (urban/built-up intensity), NDWI (surface water presence), and LST (land surface temperature in °C) across Australia for 2025 using cloud-masked Landsat 8 and 9 Collection 2 Level 2 surface reflectance and surface temperature data. It outputs four clipped, spatially continuous raster layers (one per index) visualized in the GEE Code Editor, plus a monthly time-series line ch

- 预分类: **repeated_execution(same op over time/objects)**
- gold ITERATIVE 位置: [{'seq': 6, 'repeat': 1, 'prev': 'TEMPORAL_FILTER', 'next': 'RASTER_LOAD'}, {'seq': 10, 'repeat': 1, 'prev': 'TEMPORAL_FILTER', 'next': 'AGGREGATION'}]
- owner_ruling: ______（repeated_execution / loop_structure / batch_same_op / not_an_error）

## k=1753 — Task: Analyze NDCI variability in water bodies

Task: Analyze NDCI variability in water bodies
Calculate the Normalized Difference Chlorophyll Index (NDCI) from Landsat 5 and 7 surface reflectance data, applies cloud and water masking using pixel QA and NDWI, and computes the standard deviation of NDCI across the combined time series to assess temporal variability of chlorophyll-related water quality in water bodies within the region of interest.

- 预分类: **repeated_execution(same op over time/objects)**
- gold ITERATIVE 位置: [{'seq': 7, 'repeat': 1, 'prev': 'SPATIAL_FILTER', 'next': 'AGGREGATION'}, {'seq': 11, 'repeat': 1, 'prev': 'SPATIAL_FILTER', 'next': 'AGGREGATION'}]
- owner_ruling: ______（repeated_execution / loop_structure / batch_same_op / not_an_error）

## k=1761 — Task: Analyze NDVI time series

Task: Analyze NDVI time series
Analyze NDVI time series from Landsat and MODIS satellite data over a user-defined region, enabling comparison of vegetation dynamics through interactive charts generated upon clicking the map.

- 预分类: **repeated_execution(same op over time/objects)**
- gold ITERATIVE 位置: [{'seq': 18, 'repeat': 1, 'prev': 'RASTER_LOAD', 'next': 'GEOMETRY_DEFINE'}]
- owner_ruling: ______（repeated_execution / loop_structure / batch_same_op / not_an_error）

## k=1773 — Task: Map seasonal land cover

Task: Map seasonal land cover
Create median composite images from Sentinel-2 and Landsat 8 surface reflectance data for three time periods (dry season, early wet season, late wet season) over a region in Cameroon to support seasonal land cover analysis, with cloud masking applied and study area boundaries visualized.

- 预分类: **repeated_execution(same op over time/objects)**
- gold ITERATIVE 位置: [{'seq': 5, 'repeat': 1, 'prev': 'ATTRIBUTE_FILTER', 'next': 'RASTER_LOAD'}, {'seq': 10, 'repeat': 1, 'prev': 'ATTRIBUTE_FILTER', 'next': 'RASTER_LOAD'}, {'seq': 15, 'repeat': 1, 'prev': 'ATTRIBUTE_FILTER', 'next': 'RASTER_LOAD'}, {'seq': 20, 'repeat': 1, 'prev': 'ATTRIBUTE_FILTER', 'next': 'RASTER_LOAD'}, {'seq': 25, 'repeat': 1, 'prev': 'ATTRIBUTE_FILTER', 'next': 'RASTER_LOAD'}, {'seq': 30, 'repeat': 1, 'prev': 'ATTRIBUTE_FILTER', 'next': 'RASTER_LOAD'}]
- owner_ruling: ______（repeated_execution / loop_structure / batch_same_op / not_an_error）

## k=1788 — Task: Classify land cover types

Task: Classify land cover types
Classify land use and land cover (LULC) into two classes—built-up and non-built-up areas—using a CART classifier applied to Landsat 8 TOA reflectance data from 2013–2015. It generates a classified raster, accuracy assessment via confusion matrix, area calculations per class, and exports masked rasters for each class and the full classification.

- 预分类: **repeated_execution(same op over time/objects)**
- gold ITERATIVE 位置: [{'seq': 3, 'repeat': 1, 'prev': 'TEMPORAL_FILTER', 'next': 'AGGREGATION'}]
- owner_ruling: ______（repeated_execution / loop_structure / batch_same_op / not_an_error）

## k=1796 — Task: Analyze NDVI over time

Task: Analyze NDVI over time
Calculate monthly mean NDVI values from Landsat 8 surface reflectance data over Guangdong Province between 2021 and 2022, generating a time series chart of vegetation greenness and displaying the mean NDVI map.

- 预分类: **repeated_execution(same op over time/objects)**
- gold ITERATIVE 位置: [{'seq': 2, 'repeat': 1, 'prev': 'RASTER_LOAD', 'next': 'TEMPORAL_FILTER'}, {'seq': 5, 'repeat': 1, 'prev': 'SPATIAL_FILTER', 'next': 'TEMPORAL_FILTER'}]
- owner_ruling: ______（repeated_execution / loop_structure / batch_same_op / not_an_error）

## k=1817 — Task: Map land cover in OKU

Task: Map land cover in OKU
Generate a cloud-masked median composite of Sentinel-2A surface reflectance imagery over Ogan Komering Ulu (OKU) from January to September 2022. It applies QA60-based cloud and cirrus masking, filters images with less than 10% cloud coverage, computes the median across the time series, and visualizes the result in true color (B4, B3, B2). The output includes a true-color RGB visualization on the map and exports a GeoTIFF containing bands B11, B8, B4, B3, and B2 for of

- 预分类: **repeated_execution(same op over time/objects)**
- gold ITERATIVE 位置: [{'seq': 6, 'repeat': 1, 'prev': 'ATTRIBUTE_FILTER', 'next': None}]
- owner_ruling: ______（repeated_execution / loop_structure / batch_same_op / not_an_error）

## k=1819 — Task: Analyze GNVDI in agricultural lot

Task: Analyze GNVDI in agricultural lot
Calculate and visualizes the Green Normalized Difference Vegetation Index (GNDVI) for a specific agricultural lot (antuco) using Landsat 8 surface reflectance data. It generates a time-series image collection of GNDVI values, clips it to the lot boundary, and creates a composite band stack for visualization and analysis.

- 预分类: **repeated_execution(same op over time/objects)**
- gold ITERATIVE 位置: [{'seq': 5, 'repeat': 2, 'prev': 'ATTRIBUTE_FILTER', 'next': None}]
- owner_ruling: ______（repeated_execution / loop_structure / batch_same_op / not_an_error）

## k=1821 — Task: Calculate albedo from Landsat imagery

Task: Calculate albedo from Landsat imagery
Calculate surface albedo using a weighted sum of reflectance bands from Landsat 5 TM surface reflectance data, applying specific coefficients to bands B1, B3, B4, B5, and B7. It generates a time series of albedo values (albedo2) for a region of interest (lote), creates a multiband stack of albedo images over time, and visualizes both individual albedo images and a chart of median albedo values over time. The output includes a mapped layer of the albedo

- 预分类: **repeated_execution(same op over time/objects)**
- gold ITERATIVE 位置: [{'seq': 4, 'repeat': 1, 'prev': 'ATTRIBUTE_FILTER', 'next': 'RASTER_LOAD'}]
- owner_ruling: ______（repeated_execution / loop_structure / batch_same_op / not_an_error）
