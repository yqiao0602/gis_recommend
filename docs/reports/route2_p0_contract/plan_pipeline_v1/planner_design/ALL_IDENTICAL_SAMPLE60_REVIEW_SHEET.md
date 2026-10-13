# all_identical 分层初审 49 例（owner 裁定材料）

来源: ALL_IDENTICAL_SAMPLE60_V1.json | 单位=独立游程(每源任务<=2) | 27 层全覆盖
证据边界: canonical 仅方法名无参数; all_identical = 同方法名重复, 循环/同方法多规则不可分

裁定字段: repeat_meaning (true_iteration/rule_count/api_call_count/undetermined) ·
granularity_disposition (one_stage/multi_stage/multi_rule_one_stage/unresolved_granularity) ·
evidence_note · confidence

## #1 | dev_idx=589 seq=7 | AGGREGATION|r2_3 | repeat=2
- task: Task: Extract surface water area | Identify surface water extent in a reservoir (embalse) using Sentinel-2 surface reflectance imagery from October to December 2021. It applies cloud masking using the QA60 band, computes NDWI from Green (B3) and NIR (B8) bands, performs k-means clustering to classify 
- canonical_span: ee.Reducer.sum -> ee.Reducer.sum
- repeat_meaning: 
- granularity_disposition: 
- evidence_note: 
- confidence: 

## #2 | dev_idx=1576 seq=5 | AGGREGATION|r2_3 | repeat=2
- task: Task: Analyze NDVI and EVI time series | Analyze temporal patterns of NDVI and EVI vegetation indices over a user-defined region using MODIS MOD13A1 data from 2017 to 2022. It generates a time-series chart of mean index values, creates animated thumbnails with date overlays for NDVI and EVI separately
- canonical_span: ee.Reducer.mean -> ee.Reducer.mean
- repeat_meaning: 
- granularity_disposition: 
- evidence_note: 
- confidence: 

## #3 | dev_idx=1774 seq=5 | AGGREGATION|r4_7 | repeat=4
- task: Task: Analyze crop NDVI LSWI RVI DVI time series | Analyze temporal vegetation and moisture indices for different crop types (Cropland, Forest, Sugarcane, Tea) using Sentinel-2 imagery from February to July 2018. It computes NDVI, LSWI, RVI, and DVI time series by applying cloud masking and median red
- canonical_span: ee.Reducer.mean -> ee.Reducer.mean -> ee.Reducer.mean -> ee.Reducer.mean
- repeat_meaning: 
- granularity_disposition: 
- evidence_note: 
- confidence: 

## #4 | dev_idx=979 seq=16 | AGGREGATION|r4_7 | repeat=4
- task: Task: Classify land cover types | Classify land cover types using Sentinel-2 surface reflectance data, computing NDVI and NDBI indices, and applies a Random Forest classifier trained on labeled regions. It outputs a classified land cover map, evaluates classification accuracy using a confusion matrix 
- canonical_span: ee.Reducer.count -> ee.Reducer.count -> ee.Reducer.count -> ee.Reducer.count
- repeat_meaning: 
- granularity_disposition: 
- evidence_note: 
- confidence: 

## #5 | dev_idx=17 seq=13 | AGGREGATION|r8plus | repeat=15
- task: Task: Analyze NDVI time series for land cover change | Analyze NDVI time series from Landsat data (2000–2020) over specific regions in southern Chile, including burned areas (e.g., China Muerta fire), timber extraction zones (e.g., Hallen Mapu), exotic plantations (e.g., Pinus radiata), and livestock/
- canonical_span: ee.Reducer.mean -> ee.Reducer.mean -> ee.Reducer.mean -> ee.Reducer.mean -> ee.Reducer.mean -> ee.Reducer.mean -> ee.Reducer.mean -> ee.Reducer.mean -> ee.Reducer.mean -> ee.Reducer.mean
- repeat_meaning: 
- granularity_disposition: 
- evidence_note: 
- confidence: 

## #6 | dev_idx=657 seq=19 | AGGREGATION|r8plus | repeat=8
- task: Task: Estimate urban land surface temperature | Estimate land surface temperature (LST) in urban and rural areas of New Haven using MODIS and Landsat data, incorporating NDVI-based emissivity correction and urban-rural classification to analyze thermal differences across land cover types.
- canonical_span: ee.Reducer.mean -> ee.Reducer.mean -> ee.Reducer.mean -> ee.Reducer.mean -> ee.Reducer.mean -> ee.Reducer.mean -> ee.Reducer.mean -> ee.Reducer.mean
- repeat_meaning: 
- granularity_disposition: 
- evidence_note: 
- confidence: 

## #7 | dev_idx=716 seq=2 | ATTRIBUTE_FILTER|r2_3 | repeat=2
- task: Task: Identify water bodies using k-means clustering | Identify water bodies by applying a k-means clustering algorithm on spectral indices and Landsat 7 surface reflectance bands, using pre-labeled training samples to filter and refine the classification through comparison of cluster results with ref
- canonical_span: ee.Filter.eq -> ee.Filter.eq
- repeat_meaning: 
- granularity_disposition: 
- evidence_note: 
- confidence: 

## #8 | dev_idx=1223 seq=46 | ATTRIBUTE_FILTER|r2_3 | repeat=2
- task: Task: Identify urban areas using Landsat classification | Identify urban areas by classifying Landsat imagery using training data derived from ground truth features and applying machine learning classifiers. It processes annual or quarterly TOA reflectance composites (greenest, standard, or simple com
- canonical_span: ee.Filter.eq -> ee.Filter.eq
- repeat_meaning: 
- granularity_disposition: 
- evidence_note: 
- confidence: 

## #9 | dev_idx=1204 seq=12 | ATTRIBUTE_FILTER|r8plus | repeat=9
- task: Task: Identify sugarcane cultivation area | Identify sugarcane cultivation areas using Sentinel-2 imagery from April and November 2020. It computes multiple vegetation indices (NDVI, EVI, DVI, RVI, LSWI) and applies a threshold-based classification rule combining EVI, DVI, RVI, and NDVI to generate a 
- canonical_span: ee.Filter.eq -> ee.Filter.eq -> ee.Filter.eq -> ee.Filter.eq -> ee.Filter.eq -> ee.Filter.eq -> ee.Filter.eq -> ee.Filter.eq -> ee.Filter.eq
- repeat_meaning: 
- granularity_disposition: 
- evidence_note: 
- confidence: 

## #10 | dev_idx=1732 seq=3 | BAND_ARITHMETIC|r2_3 | repeat=3
- task: Task: Identify suitable high-altitude grazing areas | Analyze environmental suitability for high-altitude livestock farming in Peruvian departments by integrating elevation, slope, temperature (day/night), NDVI from Sentinel-2 and Landsat-8, MODIS land surface temperature, and land cover features such
- canonical_span: ee.Image.pixelLonLat -> ee.Image.pixelLonLat -> ee.Image.pixelLonLat
- repeat_meaning: 
- granularity_disposition: 
- evidence_note: 
- confidence: 

## #11 | dev_idx=1144 seq=4 | BAND_ARITHMETIC|r2_3 | repeat=3
- task: Task: Analyze urbanization using NDVI and nightlight data | Compute a normalized difference urban index (NDUI) by combining harmonized Landsat surface reflectance data and calibrated DMSP nightlight imagery over Shenzhen. It generates median, maximum, and minimum NDVI composites from multiple years of
- canonical_span: ee.Image.constant -> ee.Image.constant -> ee.Image.constant
- repeat_meaning: 
- granularity_disposition: 
- evidence_note: 
- confidence: 

## #12 | dev_idx=557 seq=2 | BAND_ARITHMETIC|r4_7 | repeat=4
- task: Task: Analyze NDVI trend in Uruguay | Analyze long-term vegetation dynamics in Uruguay using MODIS MOD13Q1 NDVI data from 2000 to 2021. It computes annual mean and standard deviation of NDVI, masks poor-quality observations using the DetailedQA band, and derives an Integrated Plant Stress Estimator (I
- canonical_span: ee.Image.constant -> ee.Image.constant -> ee.Image.constant -> ee.Image.constant
- repeat_meaning: 
- granularity_disposition: 
- evidence_note: 
- confidence: 

## #13 | dev_idx=1145 seq=8 | BAND_ARITHMETIC|r4_7 | repeat=4
- task: Task: Analyze built-up area change | Analyze changes in built-up areas between 2000 and 2021 using Landsat surface reflectance imagery. It computes NDVI and NDBI indices for both time periods, derives binary built-up indicators (bu_2000 and bu_2021) by thresholding the indices, and calculates the diff
- canonical_span: ee.Image.constant -> ee.Image.constant -> ee.Image.constant -> ee.Image.constant
- repeat_meaning: 
- granularity_disposition: 
- evidence_note: 
- confidence: 

## #14 | dev_idx=648 seq=9 | BAND_SELECT|r2_3 | repeat=2
- task: Task: Estimate runoff using CN method | Calculate surface runoff using the SCS Curve Number (CN) method by combining soil texture and land use/land cover data. It derives CN values, computes potential maximum retention (S), classifies antecedent moisture conditions (AMC), and models daily runoff from 
- canonical_span: ee.Image.cat -> ee.Image.cat
- repeat_meaning: 
- granularity_disposition: 
- evidence_note: 
- confidence: 

## #15 | dev_idx=1195 seq=6 | BAND_SELECT|r2_3 | repeat=3
- task: Task: Detect forest loss using radar | Analyze multitemporal deforestation in a forested region using Sentinel-1 C-band SAR data. It computes mean VH backscatter for three annual periods (2018, 2019, 2020), combines them into a three-band composite (DEFORESTACION), and applies masking to remove low-ba
- canonical_span: ee.Image.cat -> ee.Image.cat -> ee.Image.cat
- repeat_meaning: 
- granularity_disposition: 
- evidence_note: 
- confidence: 

## #16 | dev_idx=1102 seq=14 | BAND_SELECT|r4_7 | repeat=4
- task: Task: Detect forest blowdown areas | Detect forest blowdown areas by analyzing changes in Sentinel-1 SAR amplitude before and after an event, combined with slope and curvature derived from SRTM terrain data. It identifies surface disturbance using pre- and post-event radar backscatter differences, mas
- canonical_span: ee.Image.cat -> ee.Image.cat -> ee.Image.cat -> ee.Image.cat
- repeat_meaning: 
- granularity_disposition: 
- evidence_note: 
- confidence: 

## #17 | dev_idx=1806 seq=17 | CLASSIFICATION|r2_3 | repeat=3
- task: Task: Classify land cover types | Classify land cover types (Cropland, Forest, Grassland, Shrubland, Water, Impervious Surface, Bareland) using multi-temporal Sentinel-2 surface reflectance data and a Random Forest classifier, generating a classified land cover map and accuracy assessment via validati
- canonical_span: ee.Classifier.smileRandomForest -> ee.Classifier.smileRandomForest -> ee.Classifier.smileRandomForest
- repeat_meaning: 
- granularity_disposition: 
- evidence_note: 
- confidence: 

## #18 | dev_idx=1266 seq=8 | CLASSIFICATION|r2_3 | repeat=3
- task: Task: Classify dry forest land cover | Classify land cover types in a dry forest region using PlanetScope optical imagery and Sentinel-1 SAR data from June 2018. It computes NDVI and NDWBI indices from optical bands, applies focal mean filtering to SAR VV and VH polarizations, and trains Random Forest
- canonical_span: ee.Classifier.smileRandomForest -> ee.Classifier.smileRandomForest -> ee.Classifier.smileRandomForest
- repeat_meaning: 
- granularity_disposition: 
- evidence_note: 
- confidence: 

## #19 | dev_idx=306 seq=8 | EXPORT_OUTPUT|r2_3 | repeat=2
- task: Task: Compute vegetation and water indices | Compute multiple spectral indices (NDVI, LSWI, MNDWI, NDWI, EVI) from Sentinel-2 surface reflectance imagery over Porto Alegre between May and December 2020. It processes cloud-filtered images (<10% cloud cover), calculates indices using specific band combi
- canonical_span: Export.image.toDrive -> Export.image.toDrive
- repeat_meaning: 
- granularity_disposition: 
- evidence_note: 
- confidence: 

## #20 | dev_idx=1121 seq=2 | EXPORT_OUTPUT|r2_3 | repeat=3
- task: Task: Compute SATVI percentiles for stable vegetation | Compute 5th and 95th percentiles of the Soil-Adjusted Total Vegetation Index (SATVI) from a time series of Landsat Surface Reflectance data between 1984 and 2018, focusing on a specific Julian day range (80–273), to characterize stable, undisturb
- canonical_span: Export.image.toDrive -> Export.image.toDrive -> Export.image.toDrive
- repeat_meaning: 
- granularity_disposition: 
- evidence_note: 
- confidence: 

## #21 | dev_idx=951 seq=5 | EXPORT_OUTPUT|r4_7 | repeat=7
- task: Task: Analyze vegetation and sand dune changes | Analyze multiple vegetation and surface condition indices (BSCI, NDVI, GRVI, NDWI, GSI, FS, CS) using NAIP, Landsat 8, and Sentinel-2 imagery over a user-defined area of interest. It computes time-averaged index layers, generates zonal statistics (mean,
- canonical_span: Export.image.toDrive -> Export.image.toDrive -> Export.image.toDrive -> Export.image.toDrive -> Export.image.toDrive -> Export.image.toDrive -> Export.image.toDrive
- repeat_meaning: 
- granularity_disposition: 
- evidence_note: 
- confidence: 

## #22 | dev_idx=951 seq=24 | EXPORT_OUTPUT|r4_7 | repeat=7
- task: Task: Analyze vegetation and sand dune changes | Analyze multiple vegetation and surface condition indices (BSCI, NDVI, GRVI, NDWI, GSI, FS, CS) using NAIP, Landsat 8, and Sentinel-2 imagery over a user-defined area of interest. It computes time-averaged index layers, generates zonal statistics (mean,
- canonical_span: Export.image.toDrive -> Export.image.toDrive -> Export.image.toDrive -> Export.image.toDrive -> Export.image.toDrive -> Export.image.toDrive -> Export.image.toDrive
- repeat_meaning: 
- granularity_disposition: 
- evidence_note: 
- confidence: 

## #23 | dev_idx=448 seq=9 | GEOMETRY_DEFINE|r2_3 | repeat=2
- task: Task: Classify vegetation coverage in Pampas | Classify vegetation coverage in the Pampas de Heat ecosystem using NDVI derived from Sentinel-2 surface reflectance imagery. It applies cloud masking via the QA60 band, computes a median composite within a user-defined date range, and calculates NDVI usin
- canonical_span: ee.Geometry.Point -> ee.Geometry.Point
- repeat_meaning: 
- granularity_disposition: 
- evidence_note: 
- confidence: 

## #24 | dev_idx=1732 seq=13 | ITERATIVE_APPLY|r2_3 | repeat=2
- task: Task: Identify suitable high-altitude grazing areas | Analyze environmental suitability for high-altitude livestock farming in Peruvian departments by integrating elevation, slope, temperature (day/night), NDVI from Sentinel-2 and Landsat-8, MODIS land surface temperature, and land cover features such
- canonical_span: ee.ImageCollection.map -> ee.ImageCollection.map
- repeat_meaning: 
- granularity_disposition: 
- evidence_note: 
- confidence: 

## #25 | dev_idx=514 seq=7 | ITERATIVE_APPLY|r2_3 | repeat=2
- task: Task: Analyze surface water extent and climate variables | Analyze monthly surface water extent from the JRC Global Surface Water dataset and climate variables (actual evapotranspiration and PDSI) from the TerraClimate dataset over a specific Arctic region between 2000 and 2001, with reprojected and r
- canonical_span: ee.ImageCollection.map -> ee.ImageCollection.map
- repeat_meaning: 
- granularity_disposition: 
- evidence_note: 
- confidence: 

## #26 | dev_idx=1006 seq=2 | MASKING|r2_3 | repeat=2
- task: Task: Map forest cover and loss dynamics | Analyze forest cover, loss, carbon stock, and emissions in Indonesia's cocoa-producing regions from 2000 to 2018 using Hansen Global Forest Change and biomass datasets. It defines forest based on minimum canopy cover (10%), tracks annual forest loss, computes
- canonical_span: ee.Image.updateMask -> ee.Image.updateMask
- repeat_meaning: 
- granularity_disposition: 
- evidence_note: 
- confidence: 

## #27 | dev_idx=691 seq=2 | MASKING|r4_7 | repeat=4
- task: Task: Identify peanut cultivation area | Identify peanut cultivation areas in Heilongjiang Province, China, for the year 2018 using multi-source remote sensing indices. It applies threshold-based masking on PA (Probability of Agriculture), CCCI (Canopy Chlorophyll Content Index), and CARI (Chlorophyll
- canonical_span: ee.Image.updateMask -> ee.Image.updateMask -> ee.Image.updateMask -> ee.Image.updateMask
- repeat_meaning: 
- granularity_disposition: 
- evidence_note: 
- confidence: 

## #28 | dev_idx=18 seq=17 | RASTER_LOAD|r2_3 | repeat=2
- task: Task: Classify land cover in 1995 | Classify historical land use and land cover in 1995 using Landsat 5 imagery, trained by 2020 reference data through a Random Forest classifier. It generates a classified map of six land cover types—plowland, other vegetation, eucalyptus, water, and constructed areas
- canonical_span: ee.Image -> ee.Image
- repeat_meaning: 
- granularity_disposition: 
- evidence_note: 
- confidence: 

## #29 | dev_idx=53 seq=11 | RASTER_LOAD|r2_3 | repeat=2
- task: Task: Correct land cover classification | the workflow corrects a land cover classification map for the Zvimba district in Zimbabwe by applying a series of rule-based reclassifications using geometric overlays, where specific classes are re-mapped based on user-defined regions to improve classificatio
- canonical_span: ee.Image -> ee.Image
- repeat_meaning: 
- granularity_disposition: 
- evidence_note: 
- confidence: 

## #30 | dev_idx=826 seq=11 | RASTER_LOAD|r4_7 | repeat=6
- task: Task: Identify cropland areas using multi-source land cover data | Identify cropland areas by combining multiple land cover classifications from MODIS, Copernicus, GLOBCOVER, GFSAD, and JRC Global Surface Water datasets. It applies logical AND operations across consistent land cover classes (e.g., IGB
- canonical_span: ee.Image -> ee.Image -> ee.Image -> ee.Image -> ee.Image -> ee.Image
- repeat_meaning: 
- granularity_disposition: 
- evidence_note: 
- confidence: 

## #31 | dev_idx=564 seq=12 | RASTER_LOAD|r4_7 | repeat=7
- task: Task: Classify water and shadow areas | Classify water and shadow areas using Landsat 7 and 8 surface reflectance imagery from 2020. It applies sensor-specific cloud masking (for Landsat 7 and 8) and merges collections to compute a median composite. A Random Forest classifier is trained using spectral
- canonical_span: ee.Image -> ee.Image -> ee.Image -> ee.Image -> ee.Image -> ee.Image -> ee.Image
- repeat_meaning: 
- granularity_disposition: 
- evidence_note: 
- confidence: 

## #32 | dev_idx=1243 seq=4 | RASTER_LOAD|r8plus | repeat=8
- task: Task: Analyze SAR backscatter intensity | Analyze temporal patterns of Sentinel-1 C-band VV and VH polarization backscatter over an agricultural or land surface area, generating multi-temporal composites for early 2019. It computes a VH/VV ratio as an indicator of surface structure and moisture, and e
- canonical_span: ee.Image -> ee.Image -> ee.Image -> ee.Image -> ee.Image -> ee.Image -> ee.Image -> ee.Image
- repeat_meaning: 
- granularity_disposition: 
- evidence_note: 
- confidence: 

## #33 | dev_idx=603 seq=38 | RASTER_LOAD|r8plus | repeat=8
- task: Task: Assess post-fire vegetation recovery | the workflow assesses post-fire vegetation disturbance and recovery using dNBR, RdNBR, and RBR indices derived from pre- and post-fire Landsat imagery. It computes spectral indices from Landsat 5 and 7 TOA reflectance data, applies cloud masking, and calcul
- canonical_span: ee.Image -> ee.Image -> ee.Image -> ee.Image -> ee.Image -> ee.Image -> ee.Image -> ee.Image
- repeat_meaning: 
- granularity_disposition: 
- evidence_note: 
- confidence: 

## #34 | dev_idx=1448 seq=5 | TEMPORAL_FILTER|r2_3 | repeat=2
- task: Task: Analyze monthly maximum kNDVI | Compute a time series of monthly maximum kNDVI (kernel NDVI) from MODIS MOD13Q1 data between 2005 and 2020, applies a tanh-transformed NDVI scaling, and visualizes both the individual monthly composites and their long-term mean over a user-defined region. It also 
- canonical_span: ee.Filter.calendarRange -> ee.Filter.calendarRange
- repeat_meaning: 
- granularity_disposition: 
- evidence_note: 
- confidence: 

## #35 | dev_idx=1470 seq=6 | TEMPORAL_FILTER|r2_3 | repeat=2
- task: Task: Project hottest month temperature | Compute and projects the hottest-month mean temperature (derived from daily tmax/tmin) for the year 2100 under RCP85, then extrapolates linearly to a speculative '2500' (implemented as +34°C offset to 2100 values), and classifies global land pixels into 12 dis
- canonical_span: ee.Filter.calendarRange -> ee.Filter.calendarRange
- repeat_meaning: 
- granularity_disposition: 
- evidence_note: 
- confidence: 

## #36 | dev_idx=504 seq=13 | TEMPORAL_FILTER|r4_7 | repeat=6
- task: Task: Calculate water balance from climate data | Calculate monthly water balance using precipitation, actual evapotranspiration, and runoff from TerraClimate data over the Kahayan-Sebangau Watershed (KHG) between 2010 and 2020. It outputs time-series charts of evapotranspiration, precipitation, runof
- canonical_span: ee.Filter.calendarRange -> ee.Filter.calendarRange -> ee.Filter.calendarRange -> ee.Filter.calendarRange -> ee.Filter.calendarRange -> ee.Filter.calendarRange
- repeat_meaning: 
- granularity_disposition: 
- evidence_note: 
- confidence: 

## #37 | dev_idx=744 seq=8 | TEMPORAL_FILTER|r4_7 | repeat=4
- task: Task: Identify wetland loss and gain | Identify areas of potential wetland loss and gain following Hurricane Ida by analyzing changes in Sentinel-1 (VH polarization) backscatter and Sentinel-2 (mNDWI) spectral index across five post-hurricane time periods, combining results into a confidence-level map
- canonical_span: ee.Filter.calendarRange -> ee.Filter.calendarRange -> ee.Filter.calendarRange -> ee.Filter.calendarRange
- repeat_meaning: 
- granularity_disposition: 
- evidence_note: 
- confidence: 

## #38 | dev_idx=697 seq=5 | TEMPORAL_FILTER|r8plus | repeat=14
- task: Task: Detect wetland change using SAR | Identify wetland loss and gain areas by analyzing changes in Sentinel-1 VH backscatter over time, using pre- and post-event radar imagery to detect significant decreases (loss) and increases (gain) in signal intensity associated with land cover change.
- canonical_span: ee.Filter.calendarRange -> ee.Filter.calendarRange -> ee.Filter.calendarRange -> ee.Filter.calendarRange -> ee.Filter.calendarRange -> ee.Filter.calendarRange -> ee.Filter.calendarRange -> ee.Filter.calendarRange -> ee.Filter.calendarRange -> ee.Filter.calendarRange
- repeat_meaning: 
- granularity_disposition: 
- evidence_note: 
- confidence: 

## #39 | dev_idx=467 seq=15 | TEMPORAL_FILTER|r8plus | repeat=8
- task: Task: Analyze summer backscatter intensity | Analyze VV and VH polarized backscatter from Sentinel-1 SAR data over a region during the summer months (June–September) of 2022. It computes monthly mean backscatter images for both VV and VH polarizations, filtered by ascending orbit and IW mode, and visu
- canonical_span: ee.Filter.calendarRange -> ee.Filter.calendarRange -> ee.Filter.calendarRange -> ee.Filter.calendarRange -> ee.Filter.calendarRange -> ee.Filter.calendarRange -> ee.Filter.calendarRange -> ee.Filter.calendarRange
- repeat_meaning: 
- granularity_disposition: 
- evidence_note: 
- confidence: 

## #40 | dev_idx=674 seq=7 | THRESHOLD_LOGIC|r2_3 | repeat=2
- task: Task: Identify flooded areas using NDWI | Identify flooded areas by computing and comparing NDWI (Normalized Difference Water Index) from Sentinel-2 imagery during dry and rainy seasons. It calculates NDWI using bands B3 and B11, reclassifies the results into water and non-water classes, performs a ra
- canonical_span: ee.Image.where -> ee.Image.where
- repeat_meaning: 
- granularity_disposition: 
- evidence_note: 
- confidence: 

## #41 | dev_idx=1088 seq=4 | THRESHOLD_LOGIC|r2_3 | repeat=3
- task: Task: Compare tree cover classification | Compare tree cover classification between a user-defined map (myTrees) and Hansen's global forest change data (treecover2000) using a threshold of 10% canopy cover, generating an agreement map with four categories: agreement on presence, Hansen-only, user-only
- canonical_span: ee.Image.where -> ee.Image.where -> ee.Image.where
- repeat_meaning: 
- granularity_disposition: 
- evidence_note: 
- confidence: 

## #42 | dev_idx=1196 seq=50 | THRESHOLD_LOGIC|r4_7 | repeat=4
- task: Task: Classify paddy cultivation area | Classify paddy (rice) cultivation areas in Dakshin Bastar Dantewada using multi-temporal Sentinel-1 SAR imagery from June to September 2022. It computes VH backscatter time series, trains a Random Forest classifier on labeled ground truth data, applies land cove
- canonical_span: ee.Image.where -> ee.Image.where -> ee.Image.where -> ee.Image.where
- repeat_meaning: 
- granularity_disposition: 
- evidence_note: 
- confidence: 

## #43 | dev_idx=673 seq=9 | THRESHOLD_LOGIC|r4_7 | repeat=4
- task: Task: Analyze vegetation density and water index | Analyze vegetation health, water content, and fuel moisture in a study area using Sentinel-2A/B surface reflectance data from 2020. It applies cloud masking via the QA60 band, computes NDVI, NDWI, and NDFI indices, and classifies each into discrete ca
- canonical_span: ee.Image.where -> ee.Image.where -> ee.Image.where -> ee.Image.where
- repeat_meaning: 
- granularity_disposition: 
- evidence_note: 
- confidence: 

## #44 | dev_idx=854 seq=3 | THRESHOLD_LOGIC|r8plus | repeat=20
- task: Task: Classify NDVI levels over time | Compute and classifies median NDVI values from Landsat surface reflectance imagery over a region of interest (aoi1) for six different years (2000, 2005, 2010, 2015, 2020). It calculates NDVI using band ratios (B4/B3 for Landsat 5/7 and B5/B4 for Landsat 8), appli
- canonical_span: ee.Image.where -> ee.Image.where -> ee.Image.where -> ee.Image.where -> ee.Image.where -> ee.Image.where -> ee.Image.where -> ee.Image.where -> ee.Image.where -> ee.Image.where
- repeat_meaning: 
- granularity_disposition: 
- evidence_note: 
- confidence: 

## #45 | dev_idx=114 seq=25 | THRESHOLD_LOGIC|r8plus | repeat=10
- task: Task: Model soil wind erosion potential | the workflow models soil wind erosion potential (SWEP) by integrating multiple environmental factors including weather, erodible fraction, soil crust, roughness, and vegetation cover. It computes a weather factor (WF) using ERA5-Land wind speed, snow depth fre
- canonical_span: ee.Image.where -> ee.Image.where -> ee.Image.where -> ee.Image.where -> ee.Image.where -> ee.Image.where -> ee.Image.where -> ee.Image.where -> ee.Image.where -> ee.Image.where
- repeat_meaning: 
- granularity_disposition: 
- evidence_note: 
- confidence: 

## #46 | dev_idx=958 seq=8 | VECTOR_LOAD|r2_3 | repeat=2
- task: Task: Estimate wheat yield from Sentinel-2 time series | Estimate winter wheat yield in Henan Province by generating a time series of Sentinel-2 surface reflectance images from October 15, 2016, to June 15, 2017, extracting spectral features at point sample locations with known yield values, and struc
- canonical_span: ee.FeatureCollection -> ee.FeatureCollection
- repeat_meaning: 
- granularity_disposition: 
- evidence_note: 
- confidence: 

## #47 | dev_idx=1204 seq=11 | VECTOR_LOAD|r2_3 | repeat=2
- task: Task: Identify sugarcane cultivation area | Identify sugarcane cultivation areas using Sentinel-2 imagery from April and November 2020. It computes multiple vegetation indices (NDVI, EVI, DVI, RVI, LSWI) and applies a threshold-based classification rule combining EVI, DVI, RVI, and NDVI to generate a 
- canonical_span: ee.Feature -> ee.Feature
- repeat_meaning: 
- granularity_disposition: 
- evidence_note: 
- confidence: 

## #48 | dev_idx=631 seq=17 | VECTOR_LOAD|r8plus | repeat=10
- task: Task: Classify land cover types | Classify land cover into five categories—Cropland, Forest, Impervious surfaces, Water, and Tea plantations—using a combination of spectral indices (NDVI, NDWI, NDBI, LSWI, NBR, EVI), elevation from SRTM, and GLCM texture features derived from Landsat 8 surface reflect
- canonical_span: ee.Feature -> ee.Feature -> ee.Feature -> ee.Feature -> ee.Feature -> ee.Feature -> ee.Feature -> ee.Feature -> ee.Feature -> ee.Feature
- repeat_meaning: 
- granularity_disposition: 
- evidence_note: 
- confidence: 

## #49 | dev_idx=994 seq=723 | VECTOR_LOAD|r8plus | repeat=38
- task: Task: Identify perennial water bodies | Calculate the frequency of water occurrence in a region using Landsat 5, 7, and 8 surface reflectance data from 1984 to 2021. It computes multiple vegetation and water indices (NDVI, EVI, LSWI, mNDWI), applies a water detection threshold based on mNDWI and EVI, 
- canonical_span: ee.Feature -> ee.Feature -> ee.Feature -> ee.Feature -> ee.Feature -> ee.Feature -> ee.Feature -> ee.Feature -> ee.Feature -> ee.Feature
- repeat_meaning: 
- granularity_disposition: 
- evidence_note: 
- confidence: 
