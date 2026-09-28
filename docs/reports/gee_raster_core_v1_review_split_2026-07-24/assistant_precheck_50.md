# GEE raster-core review_50 assistant precheck

This is not human adjudication. It is a triage view to accelerate manual review; original `review_50.csv` remains unchanged.

## Summary

- assistant_task_text_faithful_to_core_chain: {'yes': 41, 'partial': 9}
- assistant_l3_chain_correct: {'partial': 18, 'yes': 32}
- assistant_chain_complete_for_task: {'partial': 30, 'yes': 20}
- assistant_should_enter_training: {'defer': 30, 'accept_train_only_candidate': 20}

## Rows

### gee_raster_core_review_001 — Identify built-up areas

- split/script: `train` / `Workflowoutput160000_script_152283`
- task_type: Human settlements
- assistant verdict: text=yes; l3=partial; complete=partial; training=defer
- source flags: model_evidence=false, chain_model=false, feature_evidence=false, chain_feature=false
- notes: description centers on model/classification/training but extracted chain lacks model train/inference/eval L3
- task_description: The script identifies built-up (urban) areas by analyzing the Dynamic World land cover dataset from January 2020 to January 2021 over a region near Tsukuba, Japan, using a mode-reduced classification composite and extracting pixels labeled as 'built' (class 6). It calculates the percentage of built area within the study region.
- L3: L3_03_09_01:Filter by Date Range > L3_03_09_06:Filter by Spatial Bounds > L3_03_01_04:Select Bands > L3_03_10_R:Temporal Reducer > L3_03_03_L:Logical & Comparison > L3_01_02_03:Alter Field > L3_03_02_01:Zonal Statistics > L3_03_01_05:Update Mask > L3_03_02_01:Zonal Statistics
- ops: ee.imagecollection.filterdate > ee.imagecollection.filterbounds > ee.image.select > ee.imagecollection.reduce > ee.image.eq > ee.image.rename > ee.image.reduceregion > ee.image.selfmask > ee.image.reduceregion
- source evidence preview: L5 var geometry = ee.Geometry.Polygon([[[139.995968, 36.238901], [139.995968, 35.945904], [140.174438, 35.945904], [140.174438, 36.238901]]])      // つくば | L7 Map.setCenter(lon, lat, 15); | L13 var dw = ee.ImageCollection('GOOGLE/DYNAMICWORLD/V1') | L15 .filterDate(startDate, endDate) | L17 .filterBounds(geometry); | L19 var classification = dw.select('label'); | L21 var dwComposite = classification.reduce(ee.Reducer.mode()); | L41 Map.addLayer(dwComposite.clip(geometry), dwVisParams, 'Classified Composite');

### gee_raster_core_review_002 — Estimate water vapor volume in polygons

- split/script: `train` / `Workflowoutput150000_script_148378`
- task_type: Terrestrial hydrosphere indicators
- assistant verdict: text=yes; l3=yes; complete=yes; training=accept_train_only_candidate
- source flags: model_evidence=false, chain_model=false, feature_evidence=false, chain_feature=false
- notes: precheck found no obvious mismatch; needs human semantic confirmation
- task_description: The script calculates the mean water vapor pressure (WVP) from Sentinel-2 surface reflectance data within a given feature collection, then estimates the total water vapor volume per polygon by multiplying the mean WVP (scaled by 100) with the polygon's area. It returns the top 5 features ranked by this estimated volume.
- L3: L3_03_01_04:Select Bands > L3_03_07_01:Mosaic to New Raster > L3_03_02_01:Zonal Statistics > L3_03_09_07:Filter by Image Count/Limit
- ops: ee.imagecollection.select > ee.imagecollection.mosaic > ee.image.reduceregions > ee.imagecollection.limit
- source evidence preview: L1 var aoi = ee.FeatureCollection('users/hugheslloyd/ZZ2/Ramatoela'); | L3 var wvp = ee.Image(ee.ImageCollection("COPERNICUS/S2_SR").select('WVP').mosaic()); | L5 var withWVP = wvp.reduceRegions({ | L9 reducer: ee.Reducer.mean(), | L17 var volume = ee.Number(feature.get('mean')) | L19 .divide(100).multiply(feature.geometry().area()); | L27 .map(wvpVolume) | L33 print(highVolume)

### gee_raster_core_review_003 — Identify vegetation area

- split/script: `train` / `Workflowoutput290000_script_285470`
- task_type: Vegetation
- assistant verdict: text=partial; l3=partial; complete=partial; training=defer
- source flags: model_evidence=false, chain_model=false, feature_evidence=true, chain_feature=true
- notes: description includes presentation/export/output wording outside retained core chain; description centers on model/classification/training but extracted chain lacks model train/inference/eval L3
- task_description: The script calculates the extent of vegetated areas within a study region using Sentinel-2 imagery from July 2021. It computes NDVI from bands B8 and B4, applies a threshold (NDVI ≥ 0.369) to classify vegetation, masks non-vegetated pixels, and quantifies the total vegetated area in hectares. Outputs include a classified vegetation layer, an NDVI map with a color palette, and printed area statistics for vegetated, non-vegetated, and total regions.
- L3: L3_03_09_06:Filter by Spatial Bounds > L3_03_09_01:Filter by Date Range > L3_03_09_05:Filter by Metadata Property > L3_03_07_01:Mosaic to New Raster > L3_03_01_01:Clip Raster by Geometry > L3_03_08_01:Vegetation Indices > L3_01_02_03:Alter Field > L3_03_01_05:Update Mask > L3_03_01_04:Select Bands > L3_03_03_L:Logical & Comparison > L3_03_03_A:Arithmetic & Math > L3_03_03_A:Arithmetic & Math > L3_03_02_01:Zonal Statistics
- ops: ee.imagecollection.filterbounds > ee.imagecollection.filterdate > ee.imagecollection.filtermetadata > ee.imagecollection.mosaic > ee.image.clip > ee.image.normalizeddifference > ee.image.rename > ee.image.mask > ee.image.select > ee.image.gte > ee.image.multiply > ee.image.pixelarea > ...(+1)
- source evidence preview: L1 var imagen = s2.filterBounds(geometry).filterDate('2021-04-01','2021-04-15') | L3 .filterMetadata('CLOUDY_PIXEL_PERCENTAGE',"less_than",5); | L5 print(imagen) | L7 Map.addLayer(imagen,{"opacity":1,"bands":["B4","B3","B2"],"min":182.55645812984517,"max":1282.1259225419285,"gamma":1}, 'imagen') | L9 var imagen1 = s2.filterBounds(geometry).filterDate('2021-07-01','2021-07-15') | L11 .filterMetadata('CLOUDY_PIXEL_PERCENTAGE',"less_than",5); | L13 print(imagen1) | L15 var mosaico1 =imagen1.mosaic().clip(geometry);

### gee_raster_core_review_004 — Detect surface water using NDWI

- split/script: `train` / `Workflowoutput80000_script_75877`
- task_type: Terrestrial hydrosphere indicators
- assistant verdict: text=yes; l3=partial; complete=partial; training=defer
- source flags: model_evidence=false, chain_model=false, feature_evidence=true, chain_feature=false
- notes: source evidence contains feature/index construction not represented in extracted chain
- task_description: The script detects surface water extent by computing multiple water indices (NDWI1, NDWI2, NWI, AWEIsh, AWEInsh, TCwet, SWI, etc.) from Sentinel-2 imagery over a specific region (site4) during May–June 2021. It applies cloud masking, clips images to the region, and generates a mosaic based on the 'NDWI2' band quality, likely to produce a clear composite image highlighting water bodies.
- L3: L3_03_09_05:Filter by Metadata Property > L3_03_09_06:Filter by Spatial Bounds > L3_03_09_01:Filter by Date Range > L3_03_01_01:Clip Raster by Geometry > L3_10_02_01:Quality Mosaic / Best Pixel Composite
- ops: ee.imagecollection.filter > ee.imagecollection.filterbounds > ee.imagecollection.filterdate > ee.image.clip > ee.imagecollection.qualitymosaic
- source evidence preview: L3 print(GAMDAM); | L5 Map.addLayer(GAMDAM); | L7 var site1 = (table.filter(ee.Filter.eq("FID_1", 12171))); | L9 var site2 = (table.filter(ee.Filter.eq("FID_1", 1561))); | L11 var site3 = (table.filter(ee.Filter.eq("FID_1", 3527))); | L13 var site4 = (table.filter(ee.Filter.eq("FID_1", 4481))); | L25 var collection = ee.ImageCollection("COPERNICUS/S2") | L27 .filterBounds(site4)

### gee_raster_core_review_005 — Classify land cover types

- split/script: `train` / `Workflowoutput70000_script_68120`
- task_type: Land use/land cover
- assistant verdict: text=yes; l3=partial; complete=partial; training=defer
- source flags: model_evidence=true, chain_model=false, feature_evidence=false, chain_feature=false
- notes: description centers on model/classification/training but extracted chain lacks model train/inference/eval L3; source evidence contains model train/inference/eval calls not represented in extracted chain
- task_description: The script merges multiple user-generated feature collections of training data points, each labeled with a land cover class, converts polygon features to centroids if necessary, and joins them with Landsat 8 surface reflectance imagery within a 30-day temporal window. It applies pixel value extraction at the point locations to generate a final training dataset for supervised land cover classification. The output is a flattened feature collection containing spectral values from Landsat bands matched to labeled training points, intended for use in a land cover classification model.
- L3: L3_01_03_04:Merge > L3_02_04_01:Spatial Join > L3_03_10_R:Temporal Reducer > L3_02_03_05:Collect Features
- ops: ee.imagecollection.merge > ee.join.saveall > ee.imagecollection.first > ee.featurecollection.flatten
- source evidence preview: L1 var fC1 = ee.FeatureCollection('users/zepyoorohanian/Ohanian_gtd') | L3 var fC2 = ee.FeatureCollection('users/samuelmatey/SamMatey600PtsFC') | L5 var fC3 = ee.FeatureCollection('users/mmagana0212/MaganaGtd1') | L7 var fC4 = ee.FeatureCollection('users/kylietaylorrr44/Geog415/myExportTableTask2') | L9 var fC5 = ee.FeatureCollection('users/chloehoke/hokePath42Row36Points') // already point | L11 var fC6 = ee.FeatureCollection('users/briennesolis/Solis600FC') | L13 var fC8 = ee.FeatureCollection('users/claylevy53/All_Points') | L15 var fC9 = ee.FeatureCollection('users/zhouyiwei123/GEOG415/gtdTotal')

### gee_raster_core_review_006 — Identify tea cultivation area

- split/script: `train` / `Workflowoutput50000_script_49585`
- task_type: Land use/land cover
- assistant verdict: text=yes; l3=partial; complete=partial; training=defer
- source flags: model_evidence=false, chain_model=false, feature_evidence=true, chain_feature=true
- notes: description centers on model/classification/training but extracted chain lacks model train/inference/eval L3
- task_description: The script identifies tea cultivation areas using Sentinel-2 Level 1-C data by computing spectral indices and GLCM texture features (Entropy and Dissimilarity) from the B8 band, training and testing with labeled sample points, and classifying within a defined region of interest in Turkey.
- L3: L3_03_09_01:Filter by Date Range > L3_03_09_05:Filter by Metadata Property > L3_03_09_06:Filter by Spatial Bounds > L3_03_10_R:Temporal Reducer > L3_03_01_04:Select Bands > L3_03_01_01:Clip Raster by Geometry > L3_03_01_04:Select Bands > L3_08_02_02:Texture & Context Metrics
- ops: ee.imagecollection.filterdate > ee.imagecollection.filtermetadata > ee.imagecollection.filterbounds > ee.imagecollection.first > ee.image.select > ee.image.clip > ee.image.select > ee.image.glcmtexture
- source evidence preview: L1 var sampleTestingPoints = ee.FeatureCollection("users/berkayozen92/sampleTestingPoints5000"); | L3 var sampleTrainingPoints = ee.FeatureCollection("users/berkayozen92/sampleTrainingPoints5000"); | L5 var allArea = ee.FeatureCollection("users/berkayozen92/allArea"); | L7 var nonteaArea = ee.FeatureCollection("users/berkayozen92/nonTea"); | L9 var teaArea = ee.FeatureCollection("users/berkayozen92/tea"); | L15 var qa = image.select('QA60'); | L29 Map.setCenter(40.3541, 40.8787, 12); | L33 level1 : ee.ImageCollection('COPERNICUS/S2'), // Level 1-C Data

### gee_raster_core_review_007 — Estimate surface temperature

- split/script: `train` / `Workflowoutput5000-10000_script_5624`
- task_type: Surface thermal properties
- assistant verdict: text=yes; l3=partial; complete=partial; training=defer
- source flags: model_evidence=true, chain_model=false, feature_evidence=true, chain_feature=false
- notes: description centers on model/classification/training but extracted chain lacks model train/inference/eval L3; source evidence contains model train/inference/eval calls not represented in extracted chain; source evidence contains feature/index construction not represented in extracted chain
- task_description: The script estimates surface temperature (T2) by training a Random Forest regression model using environmental and biophysical variables, then applies the model to predict daily temperature values for August 2016 over the Yellow River basin.
- L3: L3_03_09_01:Filter by Date Range > L3_03_01_04:Select Bands > L3_03_09_06:Filter by Spatial Bounds > L3_03_09_01:Filter by Date Range > L3_03_09_06:Filter by Spatial Bounds
- ops: ee.imagecollection.filterdate > ee.imagecollection.select > ee.imagecollection.filterbounds > ee.imagecollection.filterdate > ee.imagecollection.filterbounds
- source evidence preview: L1 var roi = ee.FeatureCollection("users/gao/yellowriver"), | L3 normal = ee.FeatureCollection("users/gao/day_mean-normal"); | L11 var imglist2=ee.List([]); | L15 var imglist=ee.List([]) | L19 var EVI = ee.ImageCollection('MODIS/006/MOD13A2') | L21 .filterDate("2016-01-01","2017-01-05") | L23 .select('EVI') | L25 .filterBounds(roi)

### gee_raster_core_review_008 — Detect edges in satellite imagery

- split/script: `train` / `Workflowoutput30000_script_22464`
- task_type: Geomorphic landforms/processes
- assistant verdict: text=yes; l3=yes; complete=yes; training=accept_train_only_candidate
- source flags: model_evidence=false, chain_model=false, feature_evidence=false, chain_feature=false
- notes: precheck found no obvious mismatch; needs human semantic confirmation
- task_description: The script detects edges in a median composite of Sentinel-2 imagery over the Peninsula region using Laplacian and Gaussian convolution kernels, highlighting sharp transitions in surface reflectance for feature delineation.
- L3: L3_03_09_01:Filter by Date Range > L3_03_09_06:Filter by Spatial Bounds > L3_03_09_05:Filter by Metadata Property > L3_10_02_03:Multi-temporal Averaging > L3_09_03_01:Mean/Median/Bilateral Filtering > L3_09_09_01:Laplacian/Directional Edge Enhancement > L3_09_03_01:Mean/Median/Bilateral Filtering
- ops: ee.imagecollection.filterdate > ee.imagecollection.filterbounds > ee.imagecollection.filter > ee.imagecollection.median > ee.kernel.gaussian > ee.kernel.laplacian8 > ee.image.convolve
- source evidence preview: L1 var Peninsula = ee.FeatureCollection('users/Alejandro_AmayaH/EJE_ENE23_00-15'); | L3 Map.addLayer (Peninsula, {'palette': 'F03B20', opacity:1}, 'Peninsula',false); | L5 var composite = ee.ImageCollection('COPERNICUS/S2') | L7 .filterDate ('2020-01-01','2022-12-31') | L9 .filterBounds (Peninsula) | L11 .filter(ee.Filter.lte('CLOUDY_PIXEL_PERCENTAGE', 5)); | L17 Map.addLayer(sentinel_comp.clip(Peninsula),visParams,'Composite Peninsula', false) ; | L19 var Gausiana = ee.Kernel.gaussian({radius:1.4, sigma:1, units:'pixels', normalize:true});

### gee_raster_core_review_009 — Estimate land surface temperature

- split/script: `train` / `Workflowoutput30000_script_28452`
- task_type: Surface thermal properties
- assistant verdict: text=yes; l3=partial; complete=partial; training=defer
- source flags: model_evidence=false, chain_model=false, feature_evidence=true, chain_feature=false
- notes: source evidence contains feature/index construction not represented in extracted chain
- task_description: The script estimates land surface temperature (LST) in Punjab using Landsat 8 Surface Reflectance data by computing NDVI, PVI, TOA radiance, brightness temperature, and emissivity corrections for the summer months of 2021 and 2022.
- L3: L3_03_09_06:Filter by Spatial Bounds > L3_03_09_01:Filter by Date Range > L3_03_09_05:Filter by Metadata Property > L3_10_02_03:Multi-temporal Averaging > L3_03_01_01:Clip Raster by Geometry
- ops: ee.imagecollection.filterbounds > ee.filter.date > ee.imagecollection.filter > ee.imagecollection.median > ee.image.clip
- source evidence preview: L1 var image = ee.ImageCollection('LANDSAT/LC08/C01/T1_SR') | L3 .filterBounds(punjab); | L11 var qa = image.select('pixel_qa'); | L19 .select("B[0-9]*") | L25 var sum21 = ee.Filter.date('2021-06-01','2021-09-30'); | L27 var sum22 = ee.Filter.date('2022-06-01','2022-09-30'); | L29 var SumFilter = ee.Filter.or(sum21, sum22); | L31 var allSum = image.filter(SumFilter);

### gee_raster_core_review_010 — Classify human settlements using PlanetScope imagery

- split/script: `train` / `Workflowoutput40000_script_31183`
- task_type: Land use/land cover
- assistant verdict: text=yes; l3=partial; complete=partial; training=defer
- source flags: model_evidence=true, chain_model=false, feature_evidence=true, chain_feature=false
- notes: description centers on model/classification/training but extracted chain lacks model train/inference/eval L3; source evidence contains model train/inference/eval calls not represented in extracted chain; source evidence contains feature/index construction not represented in extracted chain
- task_description: The script classifies land cover, specifically identifying human settlements, using a Random Forest classifier applied to a PlanetScope image collection. It preprocesses images by removing zero-value pixels and masking out floodplain areas using a HAND threshold, then computes spectral indices (NDVI, NDWI, RGDIFF) before training the classifier on building point labels. The output is a classified image stack with accuracy metrics (overall, producer’s, consumer’s) stored as metadata, culminating in a median reduction of the classified results.
- L3: L3_03_01_04:Select Bands > L3_03_09_06:Filter by Spatial Bounds > L3_03_01_04:Select Bands > L3_03_10_R:Temporal Reducer > L3_03_10_R:Temporal Reducer
- ops: ee.image.select > ee.imagecollection.filterbounds > ee.image.select > ee.imagecollection.first > ee.imagecollection.reduce
- source evidence preview: L1 var ImgCollection = ee.ImageCollection("users/andreahess42/PlanetScope/AnAw_collection"); | L13 var handTile =ee.Image("users/andreahess42/Ethiopia/hand_all"); | L15 var handThresh = ee.Number(1);   //threshold below which pixels will be not considered, since they're in river banks | L17 var geometry = ee.FeatureCollection("users/andreahess42/Ethiopia/AnAw_boundaries"); | L19 var buildings = ee.FeatureCollection("users/andreahess42/Ethiopia/AnAw_Buildings_points_20200310"); | L23 .select(['b1', 'b2', 'b3', 'b4'], ['blue', 'green', 'red', 'nir']) | L25 .filterBounds(geometry); | L33 var maskImage = zeroFilter.clip(geometry);

### gee_raster_core_review_011 — Identify agriculture expansion into forest loss areas

- split/script: `train` / `Workflowoutput120000_script_116424`
- task_type: Habitat conversion/fragmentation
- assistant verdict: text=yes; l3=yes; complete=partial; training=defer
- source flags: model_evidence=false, chain_model=false, feature_evidence=true, chain_feature=true
- notes: area/statistics wording but no zonal/focal statistics step captured
- task_description: The script identifies areas where agriculture has expanded into locations of prior forest loss by combining a forest loss layer with an agriculture land cover layer, then detecting overlapping pixels with a value sum of 2, indicating both forest loss and agricultural presence.
- L3: L3_03_03_A:Arithmetic & Math > L3_10_04_01:Feature Stacking > L3_03_03_A:Arithmetic & Math > L3_03_01_05:Update Mask > L3_03_03_L:Logical & Comparison
- ops: ee.image.expression > ee.image.addbands > ee.image.expression > ee.image.updatemask > ee.image.eq
- source evidence preview: L1 var AGRICULTURA = ee.Image('users/franklinlmc/AGRICOLA_00001') | L3 Map.addLayer(BOSQUE,vis,"PERDIDA") | L5 var PERDIDA = BOSQUE.expression ('B1 == 5',{'B1': BOSQUE.select ('b1')}); | L7 Map.addLayer(PERDIDA) | L9 Map.addLayer(AGRICULTURA,{palette:"green"},"AGRICULTURA") | L13 print(juntos) | L15 var imagen_suma = juntos.expression('B1+B2',{'B1':juntos.select('b1'), | L17 'B2':juntos.select('b1_1'),})

### gee_raster_core_review_012 — Detect water bodies and coastline changes

- split/script: `train` / `Workflowoutput120000_script_112129`
- task_type: Terrestrial hydrosphere indicators
- assistant verdict: text=yes; l3=partial; complete=partial; training=defer
- source flags: model_evidence=false, chain_model=false, feature_evidence=true, chain_feature=false
- notes: description centers on model/classification/training but extracted chain lacks model train/inference/eval L3; source evidence contains feature/index construction not represented in extracted chain; area/statistics wording but no zonal/focal statistics step captured
- task_description: The script detects surface water extent and coastline dynamics using Sentinel-1 and Sentinel-2 satellite imagery over a dam area (Alaco Dam) from 2019, applying Otsu thresholding on AWEI and HSV-based classification for optical data, speckle filtering and thresholding for SAR data, and computes water area and confusion matrix metrics (tp, fp, tn, fn) for accuracy assessment across three different water detection approaches.
- L3: L3_03_01_04:Select Bands > L3_03_01_04:Select Bands > L3_03_10_R:Temporal Reducer > L3_03_10_R:Temporal Reducer > L3_03_03_A:Arithmetic & Math > L3_03_01_01:Clip Raster by Geometry > L3_03_03_L:Logical & Comparison
- ops: ee.image.select > ee.image.select > ee.imagecollection.first > ee.imagecollection.first > ee.image.subtract > ee.image.clip > ee.image.where
- source evidence preview: L3 var point = /* color: d63000 */ ee.Geometry.Point([16.41, 38.59]); // alaco dam | L5 Map.centerObject(point, 12) | L13 var Date_Start = ee.Date('2019-01-01'); | L15 var Date_End = ee.Date('2019-12-31'); | L23 var dates = ee.List.sequence(0,ee.Number(n_months).subtract(1),perido_lenght); | L25 print('n_months',n_months); | L27 print('dates', dates); | L35 dates = dates.map(make_datelist);

### gee_raster_core_review_013 — Classify flooded vegetation

- split/script: `train` / `Workflowoutput160000_script_151885`
- task_type: Land use/land cover
- assistant verdict: text=partial; l3=yes; complete=partial; training=defer
- source flags: model_evidence=true, chain_model=true, feature_evidence=false, chain_feature=true
- notes: description includes presentation/export/output wording outside retained core chain; area/statistics wording but no zonal/focal statistics step captured
- task_description: The script classifies land cover types, with a focus on detecting flooded vegetation, using pre- and post-flood Sentinel-1 SAR imagery over a specific area. It applies terrain correction, temporal filtering, and a CART-based classification model trained on labeled regions to produce a thematic map of land cover including permanent water, flooded vegetation, urban areas, and other classes.
- L3: L3_03_09_05:Filter by Metadata Property > L3_03_09_05:Filter by Metadata Property > L3_03_09_06:Filter by Spatial Bounds > L3_03_01_04:Select Bands > L3_03_09_01:Filter by Date Range > L3_03_07_01:Mosaic to New Raster > L3_03_01_09:Add/Concatenate Bands > L3_03_01_04:Select Bands > L3_08_01_01:Region-based Sample Extraction > L3_08_03_01:Train Random Forest Classifier > L3_08_03_01:Train Random Forest Classifier > L3_03_01_04:Select Bands > L3_08_04_01:Apply Classifier to Imagery
- ops: ee.imagecollection.filter > ee.imagecollection.filter > ee.imagecollection.filterbounds > ee.imagecollection.select > ee.imagecollection.filterdate > ee.imagecollection.mosaic > ee.image.cat > ee.image.select > ee.image.sampleregions > ee.classifier.smilecart > ee.classifier.train > ee.image.select > ...(+1)
- source evidence preview: L1 var collection = ee.ImageCollection("COPERNICUS/S1_GRD") | L3 .filter(ee.Filter.eq('instrumentMode','IW')) | L5 .filter(ee.Filter.eq('orbitProperties_pass','ASCENDING')) | L7 .filter(ee.Filter.eq('resolution_meters',10)) | L9 .filterBounds(Area_of_Intrest) | L11 .select('VV','VH') | L13 print(collection) | L15 var before = collection.filterDate('2016-10-04','2016-10-05').mosaic();

### gee_raster_core_review_014 — Assess NDVI fusion accuracy

- split/script: `train` / `Workflowoutput210000_script_200286`
- task_type: Vegetation
- assistant verdict: text=yes; l3=partial; complete=partial; training=defer
- source flags: model_evidence=false, chain_model=false, feature_evidence=false, chain_feature=false
- notes: description centers on model/classification/training but extracted chain lacks model train/inference/eval L3
- task_description: The script evaluates the accuracy of a fused NDVI image (img_fus) by comparing it with a base NDVI image (img_base) over a region of interest (roi). It computes the squared difference between the two NDVI images, sums the result over the ROI, normalizes by the pixel count, and calculates the RMSE. The output is a single RMSE value printed to the console, representing the root mean square error between the base and fused NDVI datasets.
- L3: L3_03_03_A:Arithmetic & Math > L3_03_03_A:Arithmetic & Math > L3_03_02_01:Zonal Statistics
- ops: ee.image.subtract > ee.image.multiply > ee.image.reduceregion
- source evidence preview: L15 var sum2 = ndvi_sub2.reduceRegion({ | L17 reducer:ee.Reducer.sum(), | L19 geometry:roi, | L25 var count = img_base.reduceRegion({ | L27 reducer:ee.Reducer.count(), | L29 geometry:roi, | L35 var rmse = (ee.Number(sum2).divide(ee.Number(count))).sqrt() | L37 print(rmse)

### gee_raster_core_review_015 — Estimate annual precipitation mean

- split/script: `train` / `Workflowoutput240000_script_239786`
- task_type: Precipitation
- assistant verdict: text=yes; l3=yes; complete=yes; training=accept_train_only_candidate
- source flags: model_evidence=false, chain_model=false, feature_evidence=false, chain_feature=false
- notes: precheck found no obvious mismatch; needs human semantic confirmation
- task_description: The script calculates the mean annual precipitation for watershed polygons in Oregon using daily precipitation data from the GRIDMET dataset for 2017. It reduces a daily precipitation image collection to an annual total, then extracts zonal statistics (mean) over watershed boundaries. Additionally, it computes the area of each watershed polygon and appends it as a property. Outputs include the annual precipitation raster, a feature collection with mean precipitation per watershed, and area values for each polygon for further analysis.
- L3: L3_03_01_04:Select Bands > L3_03_09_01:Filter by Date Range > L3_03_10_R:Temporal Reducer > L3_03_02_01:Zonal Statistics
- ops: ee.imagecollection.select > ee.imagecollection.filterdate > ee.imagecollection.reduce > ee.image.reduceregions
- source evidence preview: L1 var polys = ee.FeatureCollection("users/mweber36/OR_Watersheds_Example"); | L3 Map.addLayer(polys); | L5 var precipCollection = ee.ImageCollection('IDAHO_EPSCOR/GRIDMET') | L7 .select('pr')   // select  precip band only | L9 .filterDate('2017-01-01', '2017-12-31'); | L11 print(precipCollection); | L13 var annualPrecip = precipCollection.reduce(ee.Reducer.sum()); | L15 print(annualPrecip);

### gee_raster_core_review_016 — Identify alert buffer near peat forests

- split/script: `train` / `Workflowoutput180000_script_178749`
- task_type: Habitat conversion/fragmentation
- assistant verdict: text=yes; l3=yes; complete=yes; training=accept_train_only_candidate
- source flags: model_evidence=false, chain_model=false, feature_evidence=false, chain_feature=false
- notes: precheck found no obvious mismatch; needs human semantic confirmation
- task_description: The script calculates a 500-meter cumulative cost buffer around alert locations (drcroc_alert) within the Democratic Republic of Congo (CG) and Republic of Congo (CF), using a cost surface derived from a constant raster. It masks areas within 500 meters of alerts and overlays this buffer on peat forest extent (drcroc_peatforest). The output includes visual layers for peat forests, alert points, and a semi-transparent buffer zone, enabling spatial assessment of proximity between alerts and ecologically sensitive peat forests.
- L3: L3_03_02_03:Focal Statistics > L3_03_03_L:Logical & Comparison > L3_03_09_05:Filter by Metadata Property
- ops: ee.image.cumulativecost > ee.image.lt > ee.imagecollection.filter
- source evidence preview: L1 var alertbuffer = ee.Image(1) | L11 Map.addLayer(drcroc_peatforest, {palette:['green']}, 'drcroc_peatforests'); | L15 Map.addLayer(alertbuffer.updateMask(alertbuffer), params, 'drcroc_alert_buffer'); | L17 Map.addLayer(drcroc_alert, {palette:['coral']}, 'drcroc_alert'); | L19 var shapes = ee.FeatureCollection('USDOS/LSIB_SIMPLE/2017'); // connect to features | L21 var drcShape = shapes.filter(ee.Filter.eq('country_co', 'CG')); // filter drc shape | L23 var rocShape = shapes.filter(ee.Filter.eq('country_co', 'CF')); // filter roc shape

### gee_raster_core_review_017 — Analyze mean EVI

- split/script: `train` / `Workflowoutput60000_script_52490`
- task_type: Vegetation
- assistant verdict: text=yes; l3=yes; complete=partial; training=defer
- source flags: model_evidence=false, chain_model=false, feature_evidence=false, chain_feature=false
- notes: area/statistics wording but no zonal/focal statistics step captured
- task_description: The script calculates the mean Enhanced Vegetation Index (EVI) from an image collection over a specified date range (2021-01-01 to 2022-01-01), then clips the result to a user-defined geometry for spatial focus. The output is a single mean EVI image representing temporal aggregation of EVI values within the study period and area.
- L3: L3_03_01_04:Select Bands > L3_03_09_01:Filter by Date Range > L3_03_10_R:Temporal Reducer > L3_03_01_01:Clip Raster by Geometry
- ops: ee.image.select > ee.imagecollection.filterdate > ee.imagecollection.reduce > ee.image.clip
- source evidence preview: L1 var dataset= imageCollection2.select ('EVI'); | L3 print(dataset.size()); | L5 var date_filter = dataset.filterDate('2021-01-01','2022-01-01'); | L7 print(date_filter.size()); | L9 var mean_EVI = date_filter.reduce(ee.Reducer.mean()); | L11 var study_area = mean_EVI.clip(geometry); | L31 Map.addLayer(study_area,ndviVis)

### gee_raster_core_review_018 — Extract rainfall at HQ locations

- split/script: `train` / `Workflowoutput50000_script_46825`
- task_type: Precipitation
- assistant verdict: text=yes; l3=yes; complete=partial; training=defer
- source flags: model_evidence=false, chain_model=false, feature_evidence=false, chain_feature=false
- notes: area/statistics wording but no zonal/focal statistics step captured
- task_description: The script calculates mean daily precipitation values from CHIRPS data for a feature collection of HQ locations during May 2020, clips the data to a specified geometry, and generates a time-series table mapping each location to its corresponding daily rainfall values.
- L3: L3_03_09_01:Filter by Date Range > L3_03_01_01:Clip Raster by Geometry > L3_03_01_04:Select Bands > L3_02_03_05:Collect Features
- ops: ee.imagecollection.filterdate > ee.image.clip > ee.image.select > ee.featurecollection.flatten
- source evidence preview: L1 var hq = ee.FeatureCollection("users/BBiswas/s24pgsHQ4GEE"); | L3 Map.setCenter(88.5, 22, 8); | L5 var geometry = sa.geometry() | L7 Map.addLayer(geometry, {color: 'grey',line: 'red'}, 'SArea',0); | L9 var image = ee.ImageCollection('UCSB-CHG/CHIRPS/DAILY') | L11 var data=image.filterDate('2020-05-01', '2020-05-31'); | L13 var preci=data.map(function(data){ | L21 var rainfall=preci.select('precipitation');

### gee_raster_core_review_019 — Identify irrigated agricultural areas

- split/script: `train` / `Workflowoutput230000_script_222963`
- task_type: Land surface/agriculture indicators
- assistant verdict: text=yes; l3=yes; complete=yes; training=accept_train_only_candidate
- source flags: model_evidence=false, chain_model=false, feature_evidence=true, chain_feature=true
- notes: precheck found no obvious mismatch; needs human semantic confirmation
- task_description: The script identifies irrigated agricultural areas in the Miandoab region using multi-temporal Landsat 8 TOA reflectance data from 2019. It computes NDVI and land surface temperature (LST) from nine cloud-free median composite images, calculates mean NDVI and mean LST, then applies a threshold-based mask (NDVI > 0.3 and LST < 33°C) to detect irrigated zones. Outputs include a binary irrigation mask, its area calculation in square meters, and histograms of mean NDVI and temperature for analysis.
- L3: L3_03_09_01:Filter by Date Range > L3_03_09_05:Filter by Metadata Property > L3_10_02_03:Multi-temporal Averaging > L3_03_08_01:Vegetation Indices > L3_01_02_03:Alter Field > L3_03_01_01:Clip Raster by Geometry > L3_03_03_A:Arithmetic & Math > L3_03_03_A:Arithmetic & Math > L3_03_01_04:Select Bands > L3_03_03_A:Arithmetic & Math > L3_03_03_A:Arithmetic & Math > L3_03_01_01:Clip Raster by Geometry > L3_03_03_L:Logical & Comparison > L3_03_03_L:Logical & Comparison > L3_03_01_05:Update Mask > L3_03_03_A:Arithmetic & Math > L3_03_03_A:Arithmetic & Math > L3_03_02_01:Zonal Statistics
- ops: ee.imagecollection.filterdate > ee.imagecollection.filter > ee.imagecollection.median > ee.image.normalizeddifference > ee.image.rename > ee.image.clip > ee.image.add > ee.image.divide > ee.image.select > ee.image.add > ee.image.divide > ee.image.clip > ...(+6)
- source evidence preview: L1 Map.centerObject(KRB_Agr,10); | L3 var img1 = ee.ImageCollection('LANDSAT/LC08/C01/T1_TOA') | L5 .filterDate('2019-01-20', '2019-01-30') | L7 .filter(ee.Filter.eq('WRS_PATH', 174)) | L9 .filter(ee.Filter.eq('WRS_ROW', 36)) | L13 print(img1, 'img1'); | L15 var img2 = ee.ImageCollection('LANDSAT/LC08/C01/T1_TOA') | L17 .filterDate('2019-02-10', '2019-02-20')

### gee_raster_core_review_020 — Identify built-up areas

- split/script: `train` / `Workflowoutput110000_script_108423`
- task_type: Human settlements
- assistant verdict: text=yes; l3=yes; complete=yes; training=accept_train_only_candidate
- source flags: model_evidence=false, chain_model=false, feature_evidence=true, chain_feature=true
- notes: precheck found no obvious mismatch; needs human semantic confirmation
- task_description: The script identifies built-up (urban/constructed) areas in Surakarta, Indonesia, using NDBI (Normalized Difference Built-up Index) derived from atmospherically corrected Landsat 8 surface reflectance data from 2020. It classifies pixels with NDBI > 0 as built-up, converts the result into vector polygons, labels them as 'Bangunan' (Building) or 'Non Bangunan', and calculates the total built-up area in square kilometers.
- L3: L3_03_09_06:Filter by Spatial Bounds > L3_03_09_01:Filter by Date Range > L3_03_10_R:Temporal Reducer > L3_03_01_01:Clip Raster by Geometry > L3_03_03_A:Arithmetic & Math > L3_03_03_L:Logical & Comparison > L3_03_01_05:Update Mask > L3_03_03_A:Arithmetic & Math > L3_03_03_A:Arithmetic & Math > L3_03_01_05:Update Mask > L3_03_03_A:Arithmetic & Math > L3_01_02_03:Alter Field > L3_03_02_01:Zonal Statistics
- ops: ee.imagecollection.filterbounds > ee.imagecollection.filterdate > ee.imagecollection.first > ee.image.clip > ee.image.expression > ee.image.gt > ee.image.selfmask > ee.image.multiply > ee.image.pixelarea > ee.image.selfmask > ee.image.multiply > ee.image.rename > ...(+1)
- source evidence preview: L3 ee.Geometry.Polygon( | L13 l8 = ee.ImageCollection("LANDSAT/LC08/C02/T1_L2"), | L23 Map.centerObject(surakarta); | L25 var l8_filter = l8.filterBounds(surakarta) | L27 .filterDate('2020-01-01', '2020-12-31') | L31 var l8_paling_bersih = ee.Image(l8_filter.first()) | L37 var opticalBands = image.select('SR_B.').multiply(0.0000275).add(-0.2); | L39 var thermalBands = image.select('ST_B.*').multiply(0.00341802).add(149.0);

### gee_raster_core_review_021 — Extract SAR backscatter for land surface

- split/script: `train` / `Workflowoutput220000_script_214115`
- task_type: Land use/land cover
- assistant verdict: text=yes; l3=yes; complete=yes; training=accept_train_only_candidate
- source flags: model_evidence=false, chain_model=false, feature_evidence=false, chain_feature=false
- notes: precheck found no obvious mismatch; needs human semantic confirmation
- task_description: The script computes minimum VV and VH polarization backscatter values from Sentinel-1 GRD imagery over a specified region (TZS_polygon) between 2020 and 2021. It applies terrain correction to the image collection, selects the minimum pixel value across the time series, clips the result to the polygon boundary, and outputs a dual-polarization (VV, VH) radar backscatter image representing stabilized surface scattering characteristics for land surface analysis.
- L3: L3_03_09_05:Filter by Metadata Property > L3_03_09_05:Filter by Metadata Property > L3_03_09_06:Filter by Spatial Bounds > L3_03_09_01:Filter by Date Range > L3_03_10_R:Temporal Reducer > L3_03_01_04:Select Bands > L3_03_01_01:Clip Raster by Geometry
- ops: ee.imagecollection.filter > ee.imagecollection.filter > ee.imagecollection.filterbounds > ee.imagecollection.filterdate > ee.imagecollection.min > ee.imagecollection.select > ee.image.clip
- source evidence preview: L1 Map.centerObject(TZS_polygon); | L3 var S1_GRD =  ee.ImageCollection('COPERNICUS/S1_GRD') | L5 .filter(ee.Filter.listContains('transmitterReceiverPolarisation', 'VH')) | L7 .filter(ee.Filter.listContains('transmitterReceiverPolarisation', 'VV')) | L9 .filter(ee.Filter.eq('instrumentMode', 'IW')) | L11 .filterBounds(TZS_polygon) | L13 .filterDate('2020-01-01','2021-01-01') | L15 .map(terrainCorrection)

### gee_raster_core_review_022 — Detect vegetation change thresholds

- split/script: `train` / `Workflowoutput50000_script_47799`
- task_type: Land surface/agriculture indicators
- assistant verdict: text=yes; l3=yes; complete=yes; training=accept_train_only_candidate
- source flags: model_evidence=false, chain_model=false, feature_evidence=true, chain_feature=true
- notes: precheck found no obvious mismatch; needs human semantic confirmation
- task_description: The script analyzes time-series NDVI and day-of-year (DOY) data to compute forward differences in NDVI over time, then applies a daily change threshold based on DOY intervals to identify periods of minimal NDVI change. It constructs masked NDVI arrays using logical conditions on these differences, aiming to detect stable vs. changing vegetation states over time within a specified region.
- L3: L3_03_01_04:Select Bands > L3_03_03_A:Arithmetic & Math > L3_03_01_09:Add/Concatenate Bands
- ops: ee.image.select > ee.image.multiply > ee.image.toarray
- source evidence preview: L1 ee.Geometry.Polygon( | L15 Map.addLayer(DOYs, {}, 'DOYs') | L17 var NDVIs = Q250.select('NDVI').toArrayPerBand() | L21 Map.addLayer(NDVIs, {}, 'NDVIs') | L39 var indexes = ee.Image.constant(ee.Array(ee.List.sequence(0, maxSize))); | L45 Map.addLayer(indexes, {}, 'indexes2') | L47 var daily_ch_th = ee.Number(0.1/8) | L49 print('daily_ch_th', daily_ch_th)

### gee_raster_core_review_023 — Count classified pixels

- split/script: `train` / `Workflowoutput50000_script_49293`
- task_type: Land use/land cover
- assistant verdict: text=yes; l3=partial; complete=partial; training=defer
- source flags: model_evidence=false, chain_model=false, feature_evidence=false, chain_feature=false
- notes: description centers on model/classification/training but extracted chain lacks model train/inference/eval L3
- task_description: The script calculates the total number of pixels classified as class 1 (e.g., a specific land cover type) in a single image by applying an equality mask and summing the remaining pixel values within the image's geometry using a reduceRegion operation.
- L3: L3_03_03_L:Logical & Comparison > L3_03_01_05:Update Mask > L3_03_02_01:Zonal Statistics
- ops: ee.image.eq > ee.image.selfmask > ee.image.reduceregion
- source evidence preview: L1 var classifiedCL = ee.ImageCollection([image,image2,image3,image4,image5,image6,image8,image9,image10, | L5 var sum1 = image.eq(1).selfMask().reduceRegion({ | L7 reducer: ee.Reducer.sum(), | L9 geometry: image.geometry(), | L19 print(sum1)

### gee_raster_core_review_024 — Classify land cover types

- split/script: `train` / `Workflowoutput170000_script_160413`
- task_type: Land use/land cover
- assistant verdict: text=partial; l3=yes; complete=yes; training=accept_train_only_candidate
- source flags: model_evidence=true, chain_model=true, feature_evidence=true, chain_feature=true
- notes: description includes presentation/export/output wording outside retained core chain
- task_description: The script classifies land cover types using Landsat 8 TOA reflectance data from 2018. It computes spectral indices (MNDWI, NDBI, NDVI), applies cloud masking, and trains a CART classifier on labeled sample regions (built, water, cultivated, forest, glass) to generate a land cover classification map. The output includes a classified raster with a color palette for five classes, along with accuracy assessment metrics: confusion matrix, overall accuracy, and kappa coefficient derived from 30% testing samples.
- L3: L3_03_09_01:Filter by Date Range > L3_03_09_06:Filter by Spatial Bounds > L3_03_09_05:Filter by Metadata Property > L3_03_07_01:Mosaic to New Raster > L3_03_01_01:Clip Raster by Geometry > L3_03_08_01:Vegetation Indices > L3_01_02_03:Alter Field > L3_01_03_04:Merge > L3_03_01_04:Select Bands > L3_08_01_01:Region-based Sample Extraction > L3_03_09_05:Filter by Metadata Property > L3_03_09_05:Filter by Metadata Property > L3_08_03_01:Train Random Forest Classifier > L3_08_03_01:Train Random Forest Classifier > L3_03_01_04:Select Bands > L3_08_04_01:Apply Classifier to Imagery
- ops: ee.imagecollection.filterdate > ee.imagecollection.filterbounds > ee.imagecollection.filter > ee.imagecollection.mosaic > ee.image.clip > ee.image.normalizeddifference > ee.image.rename > ee.imagecollection.merge > ee.image.select > ee.image.sampleregions > ee.imagecollection.filter > ee.imagecollection.filter > ...(+4)
- source evidence preview: L11 return ee.Algorithms.Landsat.simpleCloudScore(ee.Image(image));//simpleCloudScore计算TOA数据每一个像元的云指数 | L15 var calCloudScore = ee.ImageCollection(collection) | L17 .map(fun_calCloudScore) | L23 var mask = image.select(['cloud']).lte(10);//TOA数据经simpleCloudScore计算产生“cloud”属性，“cloud”小于10的像元保留 | L29 var maskCloud = ee.ImageCollection(calCloudScore) | L31 .map(fun_maskCloud) | L41 var startDate = ee.Date('2018-01-01'); | L43 var endDate = ee.Date('2018-12-31');

### gee_raster_core_review_025 — Classify land cover types

- split/script: `train` / `Workflowoutput110000_script_104566`
- task_type: Land use/land cover
- assistant verdict: text=yes; l3=yes; complete=yes; training=accept_train_only_candidate
- source flags: model_evidence=true, chain_model=true, feature_evidence=true, chain_feature=true
- notes: precheck found no obvious mismatch; needs human semantic confirmation
- task_description: The script classifies land cover types using a Random Forest model trained on spectral indices and surface reflectance bands from satellite imagery, with output classes including anthropogenic areas, logging, oil palm, shifting agriculture, and cocoa. It evaluates classification accuracy and estimates the area (in hectares) of each class within a defined region.
- L3: L3_10_04_01:Feature Stacking > L3_03_09_05:Filter by Metadata Property > L3_03_09_05:Filter by Metadata Property > L3_03_01_04:Select Bands > L3_08_01_01:Region-based Sample Extraction > L3_08_03_01:Train Random Forest Classifier > L3_08_03_01:Train Random Forest Classifier > L3_03_01_04:Select Bands > L3_08_04_01:Apply Classifier to Imagery > L3_03_03_A:Arithmetic & Math > L3_10_04_01:Feature Stacking > L3_03_02_01:Zonal Statistics > L3_02_03_05:Collect Features
- ops: ee.image.addbands > ee.imagecollection.filter > ee.imagecollection.filter > ee.image.select > ee.image.sampleregions > ee.classifier.smilerandomforest > ee.classifier.train > ee.image.select > ee.image.classify > ee.image.pixelarea > ee.image.addbands > ee.image.reduceregion > ...(+1)
- source evidence preview: L1 Map.centerObject(homeRange_PH, 8); | L3 Map.setOptions('SATELLITE'); | L5 Map.addLayer(mergedTable_total,{}, 'training points', false); | L35 print('collection', collection); | L63 var trainingPts = sample.filter(ee.Filter.lt('random', split)); | L65 var validationPts = sample.filter(ee.Filter.gte('random', split)); | L67 Map.addLayer(trainingPts, {color:'red', 'opacity':0.2}, 'trainingPts - red', false); | L69 Map.addLayer(validationPts, {color:'blue', 'opacity':0.2}, 'validationPts - blue', false);

### gee_raster_core_review_026 — Classify land cover types

- split/script: `train` / `Workflowoutput100000_script_96592`
- task_type: Land use/land cover
- assistant verdict: text=partial; l3=partial; complete=partial; training=defer
- source flags: model_evidence=true, chain_model=true, feature_evidence=true, chain_feature=false
- notes: description includes presentation/export/output wording outside retained core chain; source evidence contains feature/index construction not represented in extracted chain; area/statistics wording but no zonal/focal statistics step captured
- task_description: The script classifies land cover into 7 classes using Landsat 7 surface reflectance data from 2018 and a Random Forest classifier trained on spectral indices and band statistics. It generates stratified sample points based on an existing land cover map (LC2), computes multiple vegetation and built-up indices, and evaluates classification accuracy using training and testing datasets.
- L3: L3_03_09_01:Filter by Date Range > L3_03_01_04:Select Bands > L3_08_01_02:Stratified Random Sampling > L3_03_09_05:Filter by Metadata Property > L3_03_09_05:Filter by Metadata Property > L3_08_03_01:Train Random Forest Classifier > L3_08_04_01:Apply Classifier to Imagery
- ops: ee.imagecollection.filterdate > ee.image.select > ee.image.stratifiedsample > ee.imagecollection.filter > ee.imagecollection.filter > ee.classifier.smilerandomforest > ee.classifier.setoutputmode
- source evidence preview: L9 var qa = image.select('pixel_qa'); | L17 var mask2 = image.mask().reduce(ee.Reducer.min()); | L61 var dataset = ee.ImageCollection('LANDSAT/LE07/C01/T1_SR') | L63 .filterDate(year+'-01-01', year+'-12-31') | L65 .map(cloudMaskL457) | L71 var minDict = image.reduceRegion({ | L73 reducer: ee.Reducer.min(), | L75 geometry: roi,

### gee_raster_core_review_027 — Normalize Sentinel-2 surface reflectance

- split/script: `train` / `Workflowoutput20000_script_19339`
- task_type: Land surface/agriculture indicators
- assistant verdict: text=yes; l3=yes; complete=yes; training=accept_train_only_candidate
- source flags: model_evidence=false, chain_model=false, feature_evidence=false, chain_feature=true
- notes: precheck found no obvious mismatch; needs human semantic confirmation
- task_description: The script computes a median composite of Sentinel-2 surface reflectance images from February 2020, masked for clouds and scaled between 0 and 1 per band using min-max normalization, clipped to the 'indus' region, resulting in a unit-scaled, cloud-cleared, normalized reflectance image for analysis.
- L3: L3_03_09_05:Filter by Metadata Property > L3_03_09_01:Filter by Date Range > L3_03_09_05:Filter by Metadata Property > L3_03_09_06:Filter by Spatial Bounds > L3_03_09_05:Filter by Metadata Property > L3_03_01_04:Select Bands > L3_10_02_03:Multi-temporal Averaging > L3_01_13_01:Change Pixel Data Type > L3_03_01_01:Clip Raster by Geometry > L3_03_02_01:Zonal Statistics > L3_03_03_A:Arithmetic & Math > L3_03_01_09:Add/Concatenate Bands > L3_03_01_09:Add/Concatenate Bands
- ops: ee.imagecollection.filter > ee.filter.date > ee.imagecollection.filter > ee.imagecollection.filterbounds > ee.imagecollection.filtermetadata > ee.imagecollection.select > ee.imagecollection.median > ee.image.tofloat > ee.image.clip > ee.image.reduceregion > ee.image.unitscale > ee.image.cat > ...(+1)
- source evidence preview: L5 var collection = ee.ImageCollection("COPERNICUS/S2_SR") | L7 .filter(ee.Filter.date('2020-02-01', '2020-02-29')) | L9 .filterBounds(indus) | L11 .filterMetadata('CLOUDY_PIXEL_PERCENTAGE', 'less_than', 25) | L13 .map(s2mask()) | L15 .select('B2','B3','B4','B5','B6','B7','B8','B8A','B11','B12'); | L17 var composite = ee.Image(collection.median()).toFloat().clip(indus); | L21 var minMax = composite.reduceRegion({

### gee_raster_core_review_028 — Classify land cover change

- split/script: `train` / `Workflowoutput120000_script_116238`
- task_type: Land use/land cover
- assistant verdict: text=yes; l3=partial; complete=partial; training=defer
- source flags: model_evidence=false, chain_model=false, feature_evidence=false, chain_feature=false
- notes: description centers on model/classification/training but extracted chain lacks model train/inference/eval L3
- task_description: The script performs land cover classification and change detection in the Amazon region using CCDC (Continuous Change Detection and Classification) algorithm on spectral mixture analysis (SMA) fractions derived from Landsat time series. It outputs a classified image of land cover changes and an annualized mosaic showing the first year of detected change between 1995 and 2018.
- L3: L3_03_01_04:Select Bands > L3_03_03_L:Logical & Comparison > L3_03_01_05:Update Mask > L3_03_07_01:Mosaic to New Raster
- ops: ee.image.select > ee.image.gte > ee.image.selfmask > ee.imagecollection.mosaic
- source evidence preview: L1 var saveRegion = geometry; | L9 var params = ee.Dictionary({ | L33 var gfc2018 = ee.Image('UMD/hansen/global_forest_change_2018_v1_6'); | L35 var canopyCover = gfc2018.select(['treecover2000']); | L39 var c1 = ee.ImageCollection(ccdc_SMA_utlis.get_col_wmask(saveRegion, params, mask)); | L41 var SMA_c1 = ee.ImageCollection(ccdc_SMA_utlis.get_C1_SR_SMA(c1, params)); //use get_C1_SR_NDFI_SMA for running NDFI band only | L43 var ccdc = ee.Algorithms.TemporalSegmentation.Ccdc(SMA_c1, null, null, 6);//, 0.99, 1.33, 0, 0.002, 10000 | L45 var classify = ccdc_SMA_utlis.classifySegmentsNDFI(saveRegion, ccdc, forest_mask);

### gee_raster_core_review_029 — Identify open water and submerged vegetation

- split/script: `train` / `Workflowoutput70000_script_64579`
- task_type: Terrestrial hydrosphere indicators
- assistant verdict: text=yes; l3=partial; complete=partial; training=defer
- source flags: model_evidence=true, chain_model=true, feature_evidence=true, chain_feature=false
- notes: source evidence contains feature/index construction not represented in extracted chain; area/statistics wording but no zonal/focal statistics step captured
- task_description: The script identifies open water and vegetated water bodies using Sentinel-1 VV backscatter thresholds and adaptive thresholding based on mean and standard deviation within the area of interest. It also implements a supervised Random Forest classification model trained on sample points to classify water types, with outputs including classified water maps and threshold values as image bands.
- L3: L3_03_03_A:Arithmetic & Math > L3_03_03_L:Logical & Comparison > L3_03_09_05:Filter by Metadata Property > L3_03_09_01:Filter by Date Range > L3_03_10_R:Temporal Reducer > L3_03_01_01:Clip Raster by Geometry > L3_08_01_01:Region-based Sample Extraction > L3_08_03_01:Train Random Forest Classifier
- ops: ee.image.subtract > ee.image.eq > ee.imagecollection.filtermetadata > ee.imagecollection.filterdate > ee.imagecollection.first > ee.image.clip > ee.image.sampleregions > ee.classifier.smilerandomforest
- source evidence preview: L3 var water_non_veg = image.clip(aoi).select("VV").lt(-15.0) | L5 var water_veg = image.clip(aoi).select("VV").gt(-9.5) | L7 var mosaic = ee.ImageCollection([ | L19 var start = ee.Date('2017-07-01') | L21 var finish = ee.Date('2017-08-01') | L25 var dayOffsets = ee.List.sequence(0, days.subtract(1)) | L27 var allImagesInRangeS1 = ee.ImageCollection(dayOffsets | L29 .map(function (dayOffset) {

### gee_raster_core_review_030 — Map vegetation and moisture dynamics

- split/script: `train` / `Workflowoutput50000_script_40197`
- task_type: Land surface/agriculture indicators
- assistant verdict: text=yes; l3=partial; complete=partial; training=defer
- source flags: model_evidence=false, chain_model=false, feature_evidence=true, chain_feature=false
- notes: source evidence contains feature/index construction not represented in extracted chain
- task_description: The script computes maximum NDVI and LSWI, and integrates FAPAR over a time period from Sentinel-2 data to generate spatial maps representing peak vegetation greenness, land surface water content, and cumulative photosynthetically active radiation absorption for agricultural or vegetated land monitoring.
- L3: L3_03_09_06:Filter by Spatial Bounds > L3_03_09_01:Filter by Date Range > L3_03_10_R:Temporal Reducer > L3_03_10_R:Temporal Reducer
- ops: ee.imagecollection.filterbounds > ee.imagecollection.filterdate > ee.imagecollection.reduce > ee.imagecollection.max
- source evidence preview: L1 var s2 = ee.ImageCollection('COPERNICUS/S2') | L3 .filterBounds(fc) // where 'fc' is your feature collection shapefile | L5 .filterDate('2022-09-01', '2023-03-30') // select a specific time period | L9 return img.normalizedDifference(['B8', 'B4']).rename('NDVI') | L15 return img.normalizedDifference(['B8', 'B11']).rename('LSWI') | L21 var red = image.select('B4'); | L23 var nir = image.select('B8'); | L31 var s2_fapar = s2.map(fapar);

### gee_raster_core_review_031 — Analyze crop residue cover

- split/script: `train` / `Workflowoutput150000_script_148921`
- task_type: Land surface/agriculture indicators
- assistant verdict: text=partial; l3=yes; complete=partial; training=defer
- source flags: model_evidence=false, chain_model=false, feature_evidence=false, chain_feature=true
- notes: description includes presentation/export/output wording outside retained core chain; area/statistics wording but no zonal/focal statistics step captured
- task_description: The script analyzes minimum crop residue cover at the field level across monthly intervals in 2022 using GeoTIFF data loaded from a Google Cloud bucket, aggregating weekly observations into monthly bands and computing mean residue values per agricultural field geometry.
- L3: L3_03_01_09:Add/Concatenate Bands > L3_03_01_04:Select Bands > L3_03_10_R:Temporal Reducer
- ops: ee.imagecollection.tobands > ee.imagecollection.select > ee.imagecollection.first
- source evidence preview: L1 ee.data.setDefaultWorkloadTag('preview_data_france_residue_ali'); | L7 var imgList = ee.List.sequence(1, 12).map(function(month){ | L9 return ee.Image.loadGeoTIFF( | L11 ee.String('gs://aliz-test/fr_') | L13 .cat(geohash).cat('_2022_').cat(ee.Number(month).int()).cat('_v2.tif') | L15 ).select(["week_1_min_residue", "week_2_min_residue", "week_3_min_residue", "week_4_min_residue", "number_images_used"], | L17 [ee.String("week_1_min_residue_").cat(ee.Number(month).int()), ee.String("week_2_min_residue_").cat(ee.Number(month).int()), ee.String("week_3_min_residue_").cat(ee.Number(month).int()), ee.String("week_4_min_residue_").cat(ee.Number(month).int()), ee.String("number_images_used_").cat(ee.Number(month).int())]); | L27 var reduced = fields.map(function(field){

### gee_raster_core_review_032 — Extract precipitation data

- split/script: `train` / `Workflowoutput280000_script_279533`
- task_type: Precipitation
- assistant verdict: text=yes; l3=yes; complete=yes; training=accept_train_only_candidate
- source flags: model_evidence=false, chain_model=false, feature_evidence=false, chain_feature=false
- notes: precheck found no obvious mismatch; needs human semantic confirmation
- task_description: The script extracts calibrated precipitation data from the NASA GPM IMERG dataset for a specified geographic region and time period (January 1, 2014 to February 1, 2014). It filters the IMERG daily precipitation collection by date and spatial bounds, selecting the 'precipitationCal' band, and outputs a clipped ImageCollection for further temporal or spatial analysis.
- L3: L3_03_01_04:Select Bands > L3_03_09_01:Filter by Date Range > L3_03_09_06:Filter by Spatial Bounds
- ops: ee.imagecollection.select > ee.imagecollection.filterdate > ee.imagecollection.filterbounds
- source evidence preview: L1 ee.Geometry.Polygon( | L11 ee.Geometry.Polygon( | L21 var inidate = ee.Date.fromYMD(2014,01,01) | L23 var enddate = ee.Date.fromYMD(2014,02,01) | L27 var gsmap = ee.ImageCollection('NASA/GPM_L3/IMERG_V06').select(['precipitationCal']) | L29 .filterDate(inidate, enddate).filterBounds(geometry);

### gee_raster_core_review_033 — Analyze winter wheat NDVI trends

- split/script: `train` / `Workflowoutput140000_script_132851`
- task_type: Vegetation
- assistant verdict: text=yes; l3=partial; complete=partial; training=defer
- source flags: model_evidence=false, chain_model=false, feature_evidence=true, chain_feature=false
- notes: source evidence contains feature/index construction not represented in extracted chain; area/statistics wording but no zonal/focal statistics step captured
- task_description: The script analyzes winter wheat growth patterns using NDVI derived from Landsat 8 surface reflectance data in 2020, and computes long-term EVI and SAVI vegetation indices from 1990 to 2015 for yearly mean composites. Outputs include a time series of NDVI images, a GIF animation, and annual vegetation index composites.
- L3: L3_03_09_06:Filter by Spatial Bounds > L3_03_09_01:Filter by Date Range > L3_03_09_01:Filter by Date Range > L3_03_01_04:Select Bands > L3_07_01_05:Render Raster (RGB Composite) > L3_03_09_01:Filter by Date Range > L3_10_02_03:Multi-temporal Averaging
- ops: ee.imagecollection.filterbounds > ee.imagecollection.filterdate > ee.imagecollection.filterdate > ee.image.select > ee.image.visualize > ee.imagecollection.filterdate > ee.imagecollection.mean
- source evidence preview: L1 Map.centerObject(geometry) | L3 var L8 = ee.ImageCollection('LANDSAT/LC08/C01/T1_SR').filterBounds(geometry) | L7 return image.clip(geometry) | L13 var ndvi = image.normalizedDifference(['B5', 'B4']).rename('NDVI'); | L19 function maskL8sr(imageCollection) { | L25 var qa = imageCollection.select('pixel_qa'); | L31 return imageCollection.updateMask(mask); | L35 var year = ee.Number(2020); // start with the previous year because of winter wheat

### gee_raster_core_review_034 — Extract phenology metrics from MODIS

- split/script: `train` / `Workflowoutput50000_script_45485`
- task_type: Vegetation
- assistant verdict: text=yes; l3=yes; complete=partial; training=defer
- source flags: model_evidence=false, chain_model=false, feature_evidence=false, chain_feature=false
- notes: area/statistics wording but no zonal/focal statistics step captured
- task_description: The script calculates and extracts phenological metrics (Greenup, MidGreenup, Peak, Maturity, Senescence, MidGreendown, Dormancy) in day-of-year format from the MCD12Q2 MODIS dataset for 2003, adjusts them relative to a temporal baseline, and masks results based on quality and cycle count. It also processes LAI data from MCD15A3H for the same period, capping extreme values. The output includes time-corrected phenology images and filtered LAI imagery for analysis.
- L3: L3_03_01_05:Update Mask > L3_03_03_L:Logical & Comparison > L3_03_09_05:Filter by Metadata Property > L3_03_09_01:Filter by Date Range > L3_03_01_04:Select Bands > L3_03_01_04:Select Bands > L3_03_09_01:Filter by Date Range
- ops: ee.image.updatemask > ee.image.gte > ee.imagecollection.filter > ee.filter.date > ee.image.select > ee.imagecollection.select > ee.imagecollection.filterdate
- source evidence preview: L3 var MCD12Q2 = ee.ImageCollection("MODIS/006/MCD12Q2").filter(ee.Filter.date('2003-01-01','2004-01-01')); | L7 var Pheno = image.select(['Greenup_1','MidGreenup_1','Peak_1','Maturity_1','Senescence_1','MidGreendown_1','Dormancy_1']); | L9 var QA = image.select('QA_Detailed_1'); | L13 var mask = image.select('NumCycles').gte(1); | L15 var time = ee.Image.constant(image.date().difference(ee.Date('1970-01-01'), 'day')).subtract(ee.Image(1)).int(); | L17 var year = ee.Image(image.date().difference(ee.Date('2000-01-01'), 'year')).int().rename("year"); | L25 var Pheno = MCD12Q2.map(DOY1); | L27 print("Pheno is",Pheno);

### gee_raster_core_review_035 — Compute monthly NDVI and SR

- split/script: `train` / `Workflowoutput210000_script_202604`
- task_type: Vegetation
- assistant verdict: text=yes; l3=yes; complete=partial; training=defer
- source flags: model_evidence=false, chain_model=false, feature_evidence=false, chain_feature=false
- notes: area/statistics wording but no zonal/focal statistics step captured
- task_description: The script computes monthly mean NDVI and derived Soil Reflectance (SR) from MODIS MOD13Q1 imagery over a region of interest for the year 2018. It processes the NDVI band by scaling it (dividing by 10000), then calculates SR using a mathematical transformation of NDVI, renames it, and aggregates images into monthly composites by taking the mean. The output is a monthly time-series ImageCollection with NDVI and SR bands, each image labeled with year, month, and timestamp for temporal analysis.
- L3: L3_03_09_01:Filter by Date Range > L3_03_09_06:Filter by Spatial Bounds > L3_03_01_04:Select Bands > L3_03_09_05:Filter by Metadata Property > L3_03_09_05:Filter by Metadata Property > L3_10_02_03:Multi-temporal Averaging > L3_02_03_05:Collect Features
- ops: ee.imagecollection.filterdate > ee.imagecollection.filterbounds > ee.imagecollection.select > ee.imagecollection.filter > ee.imagecollection.filter > ee.imagecollection.mean > ee.featurecollection.flatten
- source evidence preview: L7 var d16NDVI = ee.ImageCollection('MODIS/061/MOD13Q1') | L9 .filterDate('2018-01-01', '2018-12-31') | L11 .filterBounds(roi) | L13 .select('NDVI') | L15 .map(clipImg) | L17 .map(function(image){ | L27 var years = ee.List.sequence(2018, 2018); | L29 var months = ee.List.sequence(1, 12);

### gee_raster_core_review_036 — Detect soy-to-other crop conversion

- split/script: `train` / `Workflowoutput150000_script_147202`
- task_type: Land use/land cover
- assistant verdict: text=partial; l3=yes; complete=yes; training=accept_train_only_candidate
- source flags: model_evidence=false, chain_model=false, feature_evidence=false, chain_feature=false
- notes: description includes presentation/export/output wording outside retained core chain
- task_description: The script identifies changes in cropland use between 2008 and 2015 in a specific region (FIPS_2, region1=3), focusing on the conversion of soybean (label 5) to other crops or non-crop land. It uses NLCD land cover data to mask forest areas (class 82) and USDA CDL data to track annual cropland type changes, reclassifying soybean as 0 and other crops as 1. The output is a change map where pixel values encode transitions: 100 for new crop (gain), 10 for lost crop (loss), and 1 for no change. A final binary map highlights persistent change over time.
- L3: L3_03_01_04:Select Bands > L3_03_09_05:Filter by Metadata Property > L3_03_09_01:Filter by Date Range > L3_03_10_R:Temporal Reducer > L3_03_01_04:Select Bands > L3_03_01_01:Clip Raster by Geometry > L3_03_03_L:Logical & Comparison > L3_03_09_01:Filter by Date Range > L3_03_09_05:Filter by Metadata Property > L3_03_09_05:Filter by Metadata Property > L3_03_10_R:Temporal Reducer > L3_03_01_01:Clip Raster by Geometry > L3_03_01_05:Update Mask > L3_03_03_L:Logical & Comparison > L3_03_03_L:Logical & Comparison > L3_03_03_A:Arithmetic & Math > L3_03_03_L:Logical & Comparison > L3_03_03_L:Logical & Comparison
- ops: ee.image.select > ee.imagecollection.filter > ee.imagecollection.filterdate > ee.imagecollection.first > ee.image.select > ee.image.clip > ee.image.eq > ee.imagecollection.filterdate > ee.imagecollection.filter > ee.imagecollection.filter > ee.imagecollection.first > ee.image.clip > ...(+6)
- source evidence preview: L1 var region=table.select(['region1','FIPS_2','NAME','NAME_1']); | L3 var region_f=region.filter(ee.Filter.eq('region1', 3)) | L5 var NLCD=imageCollection.filterDate('2008-01-01','2008-12-31').first().select('landcover').clip(region_f).eq(82); | L9 var CDL=ee.ImageCollection("USDA/NASS/CDL").filterDate('2008-01-01','2020-12-31');//.clip(region_f); | L15 var CDL_1=CDL.filter(ee.Filter.eq("system:index",(start+1).toString())).first().select('cropland').clip(region_f).updateMask(NLCD_1); | L17 var CDL_1_1=CDL_1.where(CDL_1.select('cropland').eq(5),0);//transform soybean's label from 5 to 0 | L19 var CDL_1_2 =CDL_1_1.where(CDL_1_1.select('cropland').gte(1),1);//transform all other crop's label from 5 to 1 | L21 var CDL_0=CDL.filter(ee.Filter.eq("system:index",(start).toString())).first().select('cropland').clip(region_f).updateMask(NLCD);

### gee_raster_core_review_037 — Analyze VV backscatter changes

- split/script: `train` / `Workflowoutput50000_script_46925`
- task_type: Land surface/agriculture indicators
- assistant verdict: text=yes; l3=yes; complete=partial; training=defer
- source flags: model_evidence=false, chain_model=false, feature_evidence=false, chain_feature=true
- notes: area/statistics wording but no zonal/focal statistics step captured
- task_description: The script computes the mean VV polarization SAR backscatter from Sentinel-1 GRD data across three seasonal periods (spring, late spring, summer) for both ascending and descending orbits, producing two multi-band images representing temporal changes in radar response over the same region and time range.
- L3: L3_03_09_05:Filter by Metadata Property > L3_03_09_05:Filter by Metadata Property > L3_03_01_04:Select Bands > L3_03_01_05:Update Mask > L3_03_09_05:Filter by Metadata Property > L3_03_09_01:Filter by Date Range > L3_03_01_09:Add/Concatenate Bands > L3_03_09_05:Filter by Metadata Property > L3_10_02_03:Multi-temporal Averaging
- ops: ee.imagecollection.filter > ee.imagecollection.filter > ee.imagecollection.select > ee.image.updatemask > ee.imagecollection.filter > ee.filter.date > ee.image.cat > ee.imagecollection.filter > ee.imagecollection.mean
- source evidence preview: L1 var imgVV = ee.ImageCollection('COPERNICUS/S1_GRD') | L3 .filter(ee.Filter.listContains('transmitterReceiverPolarisation', 'VV')) | L5 .filter(ee.Filter.eq('instrumentMode', 'IW')) | L7 .select('VV') | L9 .map(function(image) { | L19 var desc = imgVV.filter(ee.Filter.eq('orbitProperties_pass', 'DESCENDING')); | L21 var asc = imgVV.filter(ee.Filter.eq('orbitProperties_pass', 'ASCENDING')); | L23 var spring = ee.Filter.date('2014-10-03', '2022-05-19');

### gee_raster_core_review_038 — Detect snow-covered areas using SAR

- split/script: `train` / `Workflowoutput120000_script_111026`
- task_type: Snow/ice
- assistant verdict: text=yes; l3=yes; complete=yes; training=accept_train_only_candidate
- source flags: model_evidence=false, chain_model=false, feature_evidence=false, chain_feature=false
- notes: precheck found no obvious mismatch; needs human semantic confirmation
- task_description: The script identifies snow-covered areas by analyzing the difference in HH-polarized Sentinel-1 SAR backscatter before and after snow events, applying median filtering and thresholding to detect significant changes indicative of snow presence.
- L3: L3_03_09_05:Filter by Metadata Property > L3_03_09_05:Filter by Metadata Property > L3_03_09_06:Filter by Spatial Bounds > L3_03_01_04:Select Bands > L3_03_09_01:Filter by Date Range > L3_03_07_01:Mosaic to New Raster > L3_03_03_A:Arithmetic & Math > L3_03_03_L:Logical & Comparison
- ops: ee.imagecollection.filter > ee.imagecollection.filter > ee.imagecollection.filterbounds > ee.imagecollection.select > ee.imagecollection.filterdate > ee.imagecollection.mosaic > ee.image.divide > ee.image.gt
- source evidence preview: L1 var collectionHH= ee.ImageCollection("COPERNICUS/S1_GRD") | L3 .filter(ee.Filter.eq("instrumentMode", "EW")) | L5 .filter(ee.Filter.listContains("transmitterReceiverPolarisation", "HH")) | L7 .filter(ee.Filter.eq("orbitProperties_pass", "DESCENDING")) | L9 .filterMetadata("resolution_meters", "equals", 25) | L11 .filterBounds(geometry) | L13 .select ("HH"); | L15 print(collectionHH, "Collection HH");

### gee_raster_core_review_039 — Extract spectral band arrays

- split/script: `train` / `Workflowoutput160000_script_156482`
- task_type: Surface radiative properties
- assistant verdict: text=yes; l3=partial; complete=partial; training=defer
- source flags: model_evidence=false, chain_model=false, feature_evidence=false, chain_feature=true
- notes: description centers on model/classification/training but extracted chain lacks model train/inference/eval L3
- task_description: The script processes a single Landsat 5 TOA reflectance image, selecting its six optical and shortwave infrared bands (B1–B5, B7), converting them into 1D and 2D pixel value arrays, transposing the array structure, and sampling the original and transposed array images at a specified geometry. It outputs the transposed array image for potential use in matrix-based spectral analysis or machine learning workflows, with no classification or time-series processing performed.
- L3: L3_03_01_04:Select Bands > L3_03_01_09:Add/Concatenate Bands > L3_08_01_01:Region-based Sample Extraction
- ops: ee.image.select > ee.image.toarray > ee.image.sample
- source evidence preview: L1 var image = ee.Image('LANDSAT/LT05/C01/T1_TOA/LT05_044034_20081011') | L3 .select(['B1', 'B2', 'B3', 'B4', 'B5', 'B7']); | L9 print(arrayImage2D) | L13 Map.addLayer(arrayImage2D,{}) | L15 var x_pre = arrayImage2D.sample(geometry) | L17 print(x) | L19 var x_post = arrayImage2Dtransposed.sample(geometry);

### gee_raster_core_review_040 — Analyze cropland productivity trends

- split/script: `train` / `Workflowoutput190000_script_180782`
- task_type: Land surface/agriculture indicators
- assistant verdict: text=yes; l3=yes; complete=partial; training=defer
- source flags: model_evidence=false, chain_model=false, feature_evidence=false, chain_feature=false
- notes: area/statistics wording but no zonal/focal statistics step captured
- task_description: The script analyzes long-term agricultural performance indicators over irrigated, rainfed, and all croplands from 2009 to 2020 using WaPOR data. It computes average annual values (e.g., AETI, TBP, GBWP) and percentage changes based on Theil-Sen slope estimation and Mann-Kendall trend significance testing. The output includes interactive split-panel maps showing mean conditions (left) and percentage change (right), with clickable inspection of pixel-level statistics, legends, and layer selection for different cropland types and indicators.
- L3: L3_03_03_A:Arithmetic & Math > L3_03_01_04:Select Bands > L3_03_03_A:Arithmetic & Math > L3_03_03_A:Arithmetic & Math > L3_03_01_04:Select Bands
- ops: ee.image.divide > ee.image.select > ee.image.multiply > ee.image.divide > ee.image.select
- source evidence preview: L1 var countries = ee.FeatureCollection("USDOS/LSIB_SIMPLE/2017"); | L5 var all_cropland = ee.Image('users/kbremer_metameta/WaPOR_Country_ind_Annual/All_cropland_2009-2020_WaPOR_extent_filtered'); | L7 var Irrigated_mask = ee.Image('users/kbremer_metameta/WaPOR_Country_ind_Annual/All_irrigated_2009-2020_WaPOR_extent_filtered'); | L9 var Rainfed_mask = ee.Image('users/kbremer_metameta/WaPOR_Country_ind_Annual/All_rainfed_2009-2020_WaPOR_extent_filtered'); | L11 var AETI = ee.Image('users/kbremer_metameta/WaPOR_Country_ind_Annual/AETI_A_mean_2009-2020_Cropland'); | L15 var MK_AETI = ee.Image('users/kbremer_metameta/WaPOR_Country_ind_Annual/MK_AETI_2009-2020_Cropland'); | L17 var TBP_kg = ee.Image('users/kbremer_metameta/WaPOR_Country_ind_Annual/TBP_A_mean_2009-2020_Cropland'); | L23 var MK_TBP = ee.Image('users/kbremer_metameta/WaPOR_Country_ind_Annual/MK_TBP_2009-2020_Cropland');

### gee_raster_core_review_041 — Analyze sea surface temperature anomalies

- split/script: `val` / `Workflowoutput240000_script_231870`
- task_type: Salinity/density
- assistant verdict: text=yes; l3=yes; complete=partial; training=defer
- source flags: model_evidence=false, chain_model=false, feature_evidence=false, chain_feature=false
- notes: area/statistics wording but no zonal/focal statistics step captured
- task_description: The script calculates daily sea surface temperature (SST) anomalies by subtracting long-term monthly mean SST (from 2002–2012) from daily SST images in October 2016. It first filters MODIS-Aqua SST data for the target month, then computes monthly climatology using a 11-year baseline, and finally generates an anomaly time series by differencing daily observations against corresponding monthly means. Outputs include the original SST image collection, the monthly climatology collection, and the daily anomaly collection with preserved timestamps for temporal analysis.
- L3: L3_03_09_06:Filter by Spatial Bounds > L3_03_09_01:Filter by Date Range > L3_03_01_04:Select Bands > L3_03_01_04:Select Bands > L3_03_09_01:Filter by Date Range > L3_03_09_05:Filter by Metadata Property > L3_03_09_05:Filter by Metadata Property > L3_03_01_04:Select Bands > L3_10_02_03:Multi-temporal Averaging > L3_03_03_A:Arithmetic & Math
- ops: ee.imagecollection.filterbounds > ee.imagecollection.filterdate > ee.imagecollection.select > ee.imagecollection.select > ee.imagecollection.filterdate > ee.imagecollection.filter > ee.imagecollection.filter > ee.image.select > ee.imagecollection.mean > ee.image.subtract
- source evidence preview: L1 var startDate = ee.Date('2016-10-01'); | L3 var endDate = ee.Date(startDate.advance(1,'month')); | L5 var date_range = ee.DateRange(startDate,endDate); | L7 var sstImg = ee.ImageCollection('NASA/OCEANDATA/MODIS-Aqua/L3SMI') | L9 .filterBounds(EEZ) //Filter by Study Area | L11 .filterDate(date_range) // startdate, enddate | L13 .select('sst') | L17 print('sstImg', sstImg);

### gee_raster_core_review_042 — Identify sugarcane suitable areas

- split/script: `val` / `Workflowoutput280000_script_271425`
- task_type: Land surface/agriculture indicators
- assistant verdict: text=partial; l3=yes; complete=yes; training=accept_train_only_candidate
- source flags: model_evidence=false, chain_model=false, feature_evidence=false, chain_feature=false
- notes: description includes presentation/export/output wording outside retained core chain
- task_description: The script evaluates biophysical and climatic conditions for sugarcane cultivation by applying multiple threshold filters on environmental variables derived from geospatial datasets. It computes suitability criteria based on temperature seasonality (Tr, Tf, diff_Trf), soil moisture indices (SIOS, LIOS), thermal integral differences (diff_integral), and growing season length (GSL). The output is a series of binary raster masks indicating areas that meet varying combinations of these thresholds, intended to map regions climatically suitable for sugarcane growth.
- L3: L3_03_01_04:Select Bands > L3_03_03_L:Logical & Comparison > L3_03_03_L:Logical & Comparison > L3_03_01_04:Select Bands > L3_03_03_L:Logical & Comparison
- ops: ee.image.select > ee.image.gt > ee.image.and > ee.image.select > ee.image.lt
- source evidence preview: L1 var SUG1 = SUG.select('Tr').gt(30).and(SUG.select('Tr').lt(209))//factor_sug1 | L3 var SUG2 = SUG.select('Tf').gt(60).and(SUG.select('Tf').lt(210))//90% | L5 var SUG3 = SUG.select('diff_Trf').gt(-120).and(SUG.select('diff_Trf').lt(120))//90%-90 | L7 var SUG4 = SUG.select('SIOS').gt(102).and(SUG.select('SIOS').lt(174))//90% | L9 var SUG6 = SUG.select('LIOS').gt(132).and(SUG.select('LIOS').lt(214))//90% | L11 var SUG7 = SUG.select('diff_integral').gt(20).and(SUG.select('diff_integral').lt(69))//90% | L13 var SUG8 = SUG.select('GSL').gt(260).and(SUG.select('GSL').lt(389))//90% | L15 var SUG1 = SUG.select('Tr').gt(49).and(SUG.select('Tr').lt(209))//factor_sug1

### gee_raster_core_review_043 — Extract panchromatic band for fusion

- split/script: `val` / `Workflowoutput280000_script_271898`
- task_type: Land use/land cover
- assistant verdict: text=yes; l3=yes; complete=yes; training=accept_train_only_candidate
- source flags: model_evidence=false, chain_model=false, feature_evidence=false, chain_feature=true
- notes: precheck found no obvious mismatch; needs human semantic confirmation
- task_description: The script processes Landsat 8 and Landsat 7 TOA reflectance collections over a region of interest, applying cloud masking using the simpleCloudScore algorithm. It selects the first cloud-free image from each collection: the panchromatic band (B8) from Landsat 8, renamed as 'quanse', and the shortwave infrared band (B5) from Landsat 7. These are intended for band fusion or spatial enhancement, where the high-resolution panchromatic band from Landsat 8 is to be combined with the multispectral band from Landsat 7. The output includes the first masked Landsat 8 panchromatic image, the first masked Landsat 7 B5 band, and an attempt to add the panchromatic band to the Landsat 7 image as a new band named 'quanse'.
- L3: L3_03_09_06:Filter by Spatial Bounds > L3_03_09_01:Filter by Date Range > L3_03_01_05:Update Mask > L3_03_01_04:Select Bands > L3_03_03_L:Logical & Comparison > L3_03_10_R:Temporal Reducer > L3_03_01_04:Select Bands > L3_01_02_03:Alter Field > L3_03_09_06:Filter by Spatial Bounds > L3_03_09_01:Filter by Date Range > L3_03_01_05:Update Mask > L3_03_01_04:Select Bands > L3_03_03_L:Logical & Comparison > L3_03_09_06:Filter by Spatial Bounds > L3_03_09_01:Filter by Date Range > L3_03_10_R:Temporal Reducer > L3_03_01_04:Select Bands > L3_10_04_01:Feature Stacking
- ops: ee.imagecollection.filterbounds > ee.imagecollection.filterdate > ee.image.updatemask > ee.image.select > ee.image.lte > ee.imagecollection.first > ee.image.select > ee.image.rename > ee.imagecollection.filterbounds > ee.imagecollection.filterdate > ee.image.updatemask > ee.image.select > ...(+6)
- source evidence preview: L1 var l8 = ee.ImageCollection("LANDSAT/LC08/C01/T1_TOA") | L3 .filterBounds(roi) | L5 .filterDate("2017-8-31", "2019-7-1") | L7 .map(ee.Algorithms.Landsat.simpleCloudScore) | L9 .map(function(image) { | L11 return image.updateMask(image.select("cloud").lte(0)); | L15 var l8_first=l8.first().select("B8").rename("quanse") | L17 print(l8_first)

### gee_raster_core_review_044 — Identify snow algae timing by elevation

- split/script: `val` / `Workflowoutput70000_script_60516`
- task_type: Cryospheric indicators
- assistant verdict: text=yes; l3=yes; complete=partial; training=defer
- source flags: model_evidence=false, chain_model=false, feature_evidence=false, chain_feature=true
- notes: area/statistics wording but no zonal/focal statistics step captured
- task_description: The script identifies the timing of maximum red snow algae presence (via RGND index) on glaciers in North America, stratified by elevation (high vs low), using MODIS Terra and Aqua data from 2000 to 2022. Outputs include regional and pixel-level statistics on the day of year with peak RGND values, masked by glacier and snow algae extent, and aggregated over user-defined regions.
- L3: L3_03_07_01:Mosaic to New Raster > L3_03_01_05:Update Mask > L3_03_05_02:Reproject > L3_03_01_05:Update Mask > L3_01_02_03:Alter Field > L3_03_03_L:Logical & Comparison > L3_01_02_03:Alter Field > L3_03_09_05:Filter by Metadata Property > L3_03_09_05:Filter by Metadata Property > L3_10_04_01:Feature Stacking > L3_10_04_01:Feature Stacking > L3_02_03_05:Collect Features > L3_01_02_03:Alter Field > L3_02_03_05:Collect Features > L3_03_09_05:Filter by Metadata Property > L3_03_01_04:Select Bands > L3_03_01_04:Select Bands > L3_02_03_05:Collect Features > L3_03_09_05:Filter by Metadata Property > L3_03_09_05:Filter by Metadata Property
- ops: ee.imagecollection.mosaic > ee.image.unmask > ee.image.reproject > ee.image.unmask > ee.image.rename > ee.image.not > ee.image.rename > ee.imagecollection.filter > ee.imagecollection.filter > ee.image.addbands > ee.image.addbands > ee.featurecollection.flatten > ...(+8)
- source evidence preview: L5 var finalAlgae = ee.ImageCollection("projects/ee-caseyengstrom/assets/globalSnowAlgae/3_algaeMaps/final"), | L7 terraDay = ee.ImageCollection("MODIS/061/MOD09GA"), | L9 s2sr = ee.ImageCollection("COPERNICUS/S2_SR"), | L11 snow = ee.ImageCollection("MODIS/006/MOD10A1"), | L13 dem_raw = ee.Image("MERIT/DEM/v1_0_3"), | L15 terra8 = ee.ImageCollection("MODIS/061/MOD09A1"), | L17 aqua8 = ee.ImageCollection("MODIS/061/MYD09A1"), | L19 aqua = ee.ImageCollection("MODIS/061/MYD09GA"),

### gee_raster_core_review_045 — Aggregate municipalities by code

- split/script: `val` / `Workflowoutput200000_script_196514`
- task_type: Boundaries
- assistant verdict: text=yes; l3=yes; complete=yes; training=accept_train_only_candidate
- source flags: model_evidence=false, chain_model=false, feature_evidence=false, chain_feature=false
- notes: precheck found no obvious mismatch; needs human semantic confirmation
- task_description: The script aggregates municipal features from a FeatureCollection based on the 'CD_GEOCME' attribute, dissolves geometries to form meso-regions, computes the total area of the resulting region using two different pixel-based methods (pixel count and pixel area), and prints the area in square kilometers. The workflow includes feature union by property, geometry dissolution, image reduction over a region, and unit conversion for area calculation.
- L3: L3_03_01_01:Clip Raster by Geometry > L3_03_02_01:Zonal Statistics > L3_03_03_A:Arithmetic & Math > L3_03_03_A:Arithmetic & Math > L3_03_02_01:Zonal Statistics
- ops: ee.image.clip > ee.image.reduceregion > ee.image.pixelarea > ee.image.divide > ee.image.reduceregion
- source evidence preview: L1 var countries = ee.FeatureCollection(municipios); | L3 Map.addLayer(municipios); | L5 Map.centerObject(municipios, 8); | L7 print(municipios) | L9 var featurecol_union_func = function(featurecollection, nameProperty){ | L11 var propVals = ee.List(featurecollection.aggregate_array(nameProperty)).distinct(); | L13 var unionByProp = ee.FeatureCollection(propVals.map(function(propVal){ | L15 var tempFC = featurecollection.filter(ee.Filter.eq(nameProperty, propVal));

### gee_raster_core_review_046 — Identify surface water extent

- split/script: `test` / `Workflowoutput160000_script_151585`
- task_type: Terrestrial hydrosphere indicators
- assistant verdict: text=yes; l3=yes; complete=yes; training=accept_train_only_candidate
- source flags: model_evidence=true, chain_model=true, feature_evidence=true, chain_feature=true
- notes: precheck found no obvious mismatch; needs human semantic confirmation
- task_description: The script identifies surface water extent using MODIS MOD09A1 data from 2000 to 2018, validates it with Landsat 5 SR data on a specific date (2010-12-29), computes confusion matrix metrics (accuracy, kappa, omission/commission errors), and generates annual recurrence, probability, and return interval maps of flooding within a basin.
- L3: L3_03_09_01:Filter by Date Range > L3_03_09_01:Filter by Date Range > L3_03_10_R:Temporal Reducer > L3_03_01_01:Clip Raster by Geometry > L3_03_09_01:Filter by Date Range > L3_01_02_03:Alter Field > L3_03_07_01:Mosaic to New Raster > L3_03_01_01:Clip Raster by Geometry > L3_03_03_L:Logical & Comparison > L3_01_02_03:Alter Field > L3_03_03_L:Logical & Comparison > L3_03_03_L:Logical & Comparison > L3_03_01_09:Add/Concatenate Bands > L3_03_02_01:Zonal Statistics > L3_08_07_01:Confusion Matrix & Accuracy Report > L3_03_09_01:Filter by Date Range > L3_03_10_R:Temporal Reducer > L3_03_03_A:Arithmetic & Math > L3_03_10_R:Temporal Reducer
- ops: ee.imagecollection.filterdate > ee.imagecollection.filterdate > ee.imagecollection.first > ee.image.clip > ee.imagecollection.filterdate > ee.image.rename > ee.imagecollection.mosaic > ee.image.clip > ee.image.and > ee.image.rename > ee.image.not > ee.image.not > ...(+7)
- source evidence preview: L1 var basin=ee.FeatureCollection('ft:1GjF33IwiL-_LVejaHJzOnfxeJNVb0PO8-IrO8FNY'); | L3 maskWater = maskWater.select('water_mask').eq(0) | L7 var startDate=ee.Date(date1); | L9 var endDate = ee.Date('2018-01-01') | L13 var daysList = ee.List.sequence(1, days, 1) | L15 var Date0 = ee.Date('2010-12-29') | L17 var ROI2 = ee.Geometry.Rectangle([ee.Geometry.Point([148.3237, -30.406]), | L19 ee.Geometry.Point([148.7563, -30.1356])]);

### gee_raster_core_review_047 — Identify cloud and shadow pixels

- split/script: `test` / `Workflowoutput180000_script_171584`
- task_type: Clouds
- assistant verdict: text=yes; l3=yes; complete=yes; training=accept_train_only_candidate
- source flags: model_evidence=false, chain_model=false, feature_evidence=true, chain_feature=true
- notes: precheck found no obvious mismatch; needs human semantic confirmation
- task_description: The script processes MODIS MOD09GA surface reflectance data to extract and mask cloud, shadow, and land/water conditions using the state_1km QA band. It decodes specific bit ranges from the QA layer to isolate cloud state, land/water flag, internal cloud shadows, and high clouds, then creates a combined mask to filter out poor-quality pixels. The output includes visualizations of the original and masked imagery, along with overlay layers showing detected clouds, shadows, high clouds, and land/water areas for quality assessment.
- L3: L3_03_01_04:Select Bands > L3_03_03_A:Arithmetic & Math > L3_03_03_L:Logical & Comparison > L3_03_03_L:Logical & Comparison
- ops: ee.image.select > ee.image.expression > ee.image.eq > ee.image.and
- source evidence preview: L11 return image.select([0], [newName]) | L19 var image = ee.Image('MODIS/006/MOD09GA/2012_06_01'); | L21 var QA = image.select('state_1km'); | L25 .expression("b(0) == 1 || b(0) == 2"); | L29 .expression("b(0)==7"); | L33 .expression("b(0)==1"); | L37 .expression("b(0)==1"); | L41 Map.addLayer(image,

### gee_raster_core_review_048 — Extract climate variable means

- split/script: `test` / `Workflowoutput290000_script_281423`
- task_type: Climate indicators
- assistant verdict: text=yes; l3=yes; complete=partial; training=defer
- source flags: model_evidence=false, chain_model=false, feature_evidence=false, chain_feature=true
- notes: area/statistics wording but no zonal/focal statistics step captured
- task_description: The script computes long-term mean values of maximum temperature, minimum temperature, precipitation, and water deficit from the TerraClimate dataset (1958–2020), and also extracts multi-year banded precipitation data. It prepares climatic baseline data by aggregating monthly imagery into annual composites for specific years (2001–2019) and imports a WorldClim biovars image for comparison. Outputs include a renamed multi-band mean climate image (with bands: maxTemp, minTemp, RAINFALL, waterDef) and a time-composited precipitation image where each band represents a month/year combination, intended for temporal climate analysis.
- L3: L3_03_01_04:Select Bands > L3_10_02_03:Multi-temporal Averaging > L3_03_01_04:Select Bands > L3_03_01_09:Add/Concatenate Bands > L3_03_01_04:Select Bands > L3_01_02_03:Alter Field
- ops: ee.imagecollection.select > ee.imagecollection.mean > ee.imagecollection.select > ee.imagecollection.tobands > ee.image.select > ee.image.rename
- source evidence preview: L1 var dataset = ee.ImageCollection('IDAHO_EPSCOR/TERRACLIMATE') | L3 var bio = ee.ImageCollection('IDAHO_EPSCOR/TERRACLIMATE').select(['tmmx', 'tmmn', 'pr', 'def']).mean().rename(["maxTemp", "minTemp", "RAINFALL", "waterDef"]) | L5 var precip = ee.ImageCollection('IDAHO_EPSCOR/TERRACLIMATE').select(['pr']).toBands() | L7 var years = ee.List.sequence(1958, 2020) | L9 print(precip) | L11 print(years) | L13 var YEARS = ee.List.sequence(2001, 2019).map(function(x){return ee.Number(x).toInt()}) | L15 print(YEARS)

### gee_raster_core_review_049 — Estimate land surface temperature

- split/script: `test` / `Workflowoutput40000_script_33946`
- task_type: Surface thermal properties
- assistant verdict: text=partial; l3=yes; complete=yes; training=accept_train_only_candidate
- source flags: model_evidence=false, chain_model=false, feature_evidence=false, chain_feature=false
- notes: description includes presentation/export/output wording outside retained core chain
- task_description: The script estimates Land Surface Temperature (LST) from Landsat 8 thermal band data by computing brightness temperature, deriving NDVI, calculating vegetation proportion and emissivity, and applying atmospheric correction. Outputs include a true-color image, NDVI map, and LST result derived through radiometric calibration and emissivity adjustment.
- L3: L3_03_09_06:Filter by Spatial Bounds > L3_03_09_01:Filter by Date Range > L3_03_10_R:Temporal Reducer > L3_03_01_04:Select Bands > L3_03_03_A:Arithmetic & Math > L3_03_03_A:Arithmetic & Math > L3_03_01_04:Select Bands > L3_03_03_A:Arithmetic & Math > L3_03_02_01:Zonal Statistics > L3_03_03_A:Arithmetic & Math > L3_03_03_A:Arithmetic & Math
- ops: ee.imagecollection.filterbounds > ee.imagecollection.filterdate > ee.imagecollection.first > ee.image.select > ee.image.multiply > ee.image.add > ee.image.select > ee.image.subtract > ee.image.reduceregion > ee.image.subtract > ee.image.divide
- source evidence preview: L5 var l8 = ee.ImageCollection("LANDSAT/LC08/C01/T1"); | L7 var spatialFiltered = l8.filterBounds(point); | L9 var temporalFiltered = spatialFiltered.filterDate('2015-06-01', '2015-06-30'); | L13 var image = ee.Image(sorted.first()); | L15 print(image); | L17 var date = ee.Date(image.get('system:time_start')); | L19 print('Timestamp: ', date); // ee.Date | L23 var clouds = ee.Algorithms.Landsat.simpleCloudScore(image).select(['cloud']);

### gee_raster_core_review_050 — Classify land cover using Sentinel-2 and FIRMS

- split/script: `test` / `Workflowoutput240000_script_235195`
- task_type: Land use/land cover
- assistant verdict: text=partial; l3=partial; complete=partial; training=defer
- source flags: model_evidence=true, chain_model=true, feature_evidence=true, chain_feature=false
- notes: description includes presentation/export/output wording outside retained core chain; source evidence contains feature/index construction not represented in extracted chain; area/statistics wording but no zonal/focal statistics step captured
- task_description: The script classifies land cover in a specified area using Sentinel-2 surface reflectance imagery from April 2019, masked for water and forest using JAXA ALOS PALSAR data, and validated with FIRMS active fire data. It applies cloud masking via QA60 band, masks pixels over water (B11 > 700) and non-forest (FNF ≤ 1), then performs Random Forest classification on the mosaic of images from April 22–30 using training samples derived from ground control points. The output includes a classified land cover map for late April 2019 and an accuracy assessment via confusion matrix and overall accuracy.
- L3: L3_03_09_05:Filter by Metadata Property > L3_03_09_01:Filter by Date Range > L3_03_09_06:Filter by Spatial Bounds > L3_03_09_01:Filter by Date Range > L3_03_10_R:Temporal Reducer > L3_03_01_04:Select Bands > L3_03_07_01:Mosaic to New Raster > L3_03_01_01:Clip Raster by Geometry > L3_03_09_05:Filter by Metadata Property > L3_03_09_01:Filter by Date Range > L3_03_01_04:Select Bands > L3_01_03_04:Merge > L3_03_09_05:Filter by Metadata Property > L3_03_09_05:Filter by Metadata Property > L3_08_01_01:Region-based Sample Extraction > L3_08_03_01:Train Random Forest Classifier > L3_08_03_01:Train Random Forest Classifier > L3_08_04_01:Apply Classifier to Imagery > L3_08_01_01:Region-based Sample Extraction
- ops: ee.imagecollection.filter > ee.imagecollection.filterdate > ee.imagecollection.filterbounds > ee.imagecollection.filterdate > ee.imagecollection.first > ee.image.select > ee.imagecollection.mosaic > ee.image.clip > ee.imagecollection.filter > ee.filter.date > ee.image.select > ee.imagecollection.merge > ...(+7)
- source evidence preview: L1 var s2= ee.ImageCollection("COPERNICUS/S2_SR").filter(ee.Filter.lt("CLOUDY_PIXEL_PERCENTAGE", 10)); | L5 var area = ee.FeatureCollection(geometry); | L9 Map.centerObject(area, 6.5); | L11 var fireImColA1 = ee.ImageCollection(s2.filterDate('2019-04-01', '2019-04-07')  //// Filter by dates. | L13 .filterBounds(area)); | L15 var fireImColA2 = ee.ImageCollection(s2.filterDate('2019-04-08', '2019-04-14')  //// Filter by dates. | L17 .filterBounds(area)); | L19 var fireImColA3 = ee.ImageCollection(s2.filterDate('2019-04-15', '2019-04-21')  //// Filter by dates.
