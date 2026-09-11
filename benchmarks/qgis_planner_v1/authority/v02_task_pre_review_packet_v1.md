# v0.2 Task Pre-Review Packet v1 (owner structural pre-review)

### recovered-287be70f78ee0c0c  [subchain_scoped | planning_oriented | L3_deterministic_paraphrase]
TASK: From the overlaid target and mapping polygons, remove the features that lack a valid target-unit identifier, then remove the features that lack a valid mapping-unit identifier, and dissolve the remaining features by their target-unit and mapping-unit identifiers.
GOLD: extractbyattribute[0] -> extractbyattribute[1] -> dissolve[2]
  sinks: [2] | multi=single
SRC: script_0000007.py sha=655824e9e8 | extractbyattribute@L489-L498; extractbyattribute@L499-L508; dissolve@L510-L518
  head: def Generate_Grid_Poly_From_NetCDF_QGIS( | NetCDF_Path="#", | Output_Folder="#", | Coor_x_NM="lon", | Coor_y_NM="lat", | Is_Rotated_Grid=1,
STRIP: ['FIELD', 'INPUT', 'OPERATOR', 'OUTPUT', 'VALUE']
AMB: the recovered chain is exactly the direct-call subchain; surrounding helper-wrapped prep/post stay outside scope; task text at fidelity stage must describe only filter-filter-dissolve
AMB: [dual-review] Verified script_0000007.py:489-518: the two native:extractbyattribute calls chained into native:dissolve are real, but the workflow's upstream (fix-geometries x2 and union via basinmaker

### recovered-29be1d80531328b3  [full_workflow | operator_explicit | L3_deterministic_paraphrase]
TASK: Reproject the input layer to the target coordinate reference system, then split any multipart geometries into single-part features.
GOLD: reprojectlayer[0] -> multiparttosingleparts[1]
  sinks: [1] | multi=single
SRC: script_0000959.py sha=a4669d4555 | reprojectlayer@L206-L206; multiparttosingleparts@L211-L211
  head: # -*- coding: utf-8 -*- | """ | Author: Mario Königbauer (mkoenigb@gmx.de) | (C) 2022 - today by Mario Koenigbauer | License: GNU General Public License v3.0 | /***************************************************************************
STRIP: ['INPUT', 'OUTPUT', 'TARGET_CRS']
AMB: [dual-review] script_0000959.py:206,211 confirms native:reprojectlayer -> native:multiparttosingleparts with the reproject output reassigned to points_layer_vl before the multi-type conversion consume

### recovered-302f34cdd7d87920  [full_workflow | planning_oriented | L2_deterministic_composition]
TASK: Assign each zone a distance value, create buffer zones around them from those distances, and select the point features that fall within the buffers; deliver both the selected points and the buffer zones of the best distance configuration.
GOLD: fieldcalculator[0] -> buffer[1] -> extractbylocation[2] -> buffer[3]
  fan-out: 0->[1, 3]
  sinks: [2, 3] | multi=multi
SRC: script_0000478.py sha=2d738eb273 | fieldcalculator@L53-L53; buffer@L55-L55; extractbylocation@L57-L57; buffer@L66-L66
  head: path = os.path.join(os.path.expanduser("~"),"Documents","skrypty_geoprzetwarzania") | punkty_adresowe = QgsVectorLayer(os.path.join(path,"punkty_adresowe.gpkg")+"|layername=punkty_adresowe","punkty","ogr") | nadajniki = QgsVectorLayer(os.path.join(path,"punkty_adresowe.gpkg")+"|layername=nadajniki",
STRIP: ['DISSOLVE', 'DISTANCE', 'FIELD_NAME', 'FIELD_TYPE', 'FORMULA', 'INPUT', 'INTERSECT', 'METHOD', 'OUTPUT', 'PREDICATE']
AMB: [dual-review] script_0000478.py:53-66 confirms all four operators and edges [[0,1],[0,3],[1,2]]: fieldcalculator feeds the in-loop buffer (line 54) and the final best-distance buffer (lines 62-66), an

### recovered-361c5eb306dbc618  [full_workflow | planning_oriented | L1_source_description_stripped]
TASK: Produce an impact assessment of the input habitat areas by building buffered zones around them, successively erasing the differences between differently buffered zones, and deriving attributes at each stage, ending with the final attribute layer.
GOLD: buffer[0] -> buffer[1] -> fieldcalculator[2] -> buffer[3] -> difference[4] -> difference[5] -> buffer[6] -> difference[7] -> difference[8] -> fieldcalculator[9] -> fieldcalculator[10]
  sinks: [10] | multi=single
SRC: script_0000588.py sha=a3717858a0 | buffer@L50-L50; buffer@L67-L67; fieldcalculator@L83-L83; buffer@L100-L100; difference@L113-L113; difference@L126-L126; buffer@L143-L143; difference@L156-L156; difference@L169-L169; fieldcalculator@L185-L185; fieldcalculator@L201-L201
  head: """ | Model exported as python. | Name : impact_Assessment | Group : Qgis course | With QGIS : 32804 | """
STRIP: ['FORMULA', 'INPUT', 'MITER_LIMIT', 'OUTPUT', 'OVERLAY', 'SEGMENTS']
AMB: [dual-review] Full read of script_0000588.py verified all 11 operators and all 10 edges, including the OVERLAY fan-in edges BaeaBuffer->BaeaDifference (line 110) and BuowlBuffer->BuowlDifference (line

### recovered-429556807ae79c01  [full_workflow | planning_oriented | L1_source_description_stripped]
TASK: Prepare an urban-surface database from the building footprints: dissolve them by type, enrich them with derived attributes, and deliver two results -- a rasterized version of the enriched footprints, and zonal statistics over the study-area-refined footprint regions.
GOLD: dissolve[0] -> fieldcalculator[1] -> intersection[2] -> dissolve[3] -> rasterize[4] -> zonalstatisticsfb[5] -> zonalstatisticsfb[6]
  fan-out: 1->[2, 4]
  sinks: [4, 6] | multi=multi
SRC: script_0000912.py sha=e8e3d7f982 | dissolve@L874-L874; fieldcalculator@L888-L888; intersection@L923-L923; dissolve@L931-L931; rasterize@L973-L973; zonalstatisticsfb@L986-L986; zonalstatisticsfb@L997-L997
  head: # -*- coding: utf-8 -*- | """ | /*************************************************************************** | SUEWSPrepareDatabase | A QGIS plugin | Prepares inputdata for the SUEWS model using typology database
STRIP: ['COLUMN_PREFIX', 'DATA_TYPE', 'EXTENT', 'EXTRA', 'FIELD', 'FIELD_LENGTH', 'FIELD_PRECISION', 'FIELD_TYPE', 'FORMULA', 'INIT', 'INPUT', 'INVERT', 'NODATA', 'OPTIONS', 'OUTPUT', 'OVERLAY', 'OVERLAY_FIELDS', 'OVERLAY_FIELDS_PREFIX', 'SEPARATE_DISJOINT', 'STATISTICS']
AMB: [dual-review] Full read of script_0000912.py verified all 7 operators and 6 edges: dissolve->fieldcalculator (lines 874-888), fieldcalculator feeding both native:intersection (via polyTypolayer, lines

### recovered-4792105e9cd94dde  [full_workflow | operator_explicit | L3_deterministic_paraphrase]
TASK: Reproject the input layer to the target coordinate reference system, extract the vertices of its geometries as points, and split any multipart point features into single parts.
GOLD: reprojectlayer[0] -> extractvertices[1] -> multiparttosingleparts[2]
  sinks: [2] | multi=single
SRC: script_0000960.py sha=42ea91e3f5 | reprojectlayer@L250-L250; extractvertices@L255-L255; multiparttosingleparts@L260-L260
  head: # -*- coding: utf-8 -*- | """ | Author: Mario Königbauer (mkoenigb@gmx.de) | (C) 2022 - today by Mario Koenigbauer | License: GNU General Public License v3.0 | /***************************************************************************
STRIP: ['INPUT', 'OUTPUT', 'TARGET_CRS']
AMB: [dual-review] script_0000960.py:250,255,260 confirms the linear chain reprojectlayer -> extractvertices -> multiparttosingleparts, each behind a geometry/CRS guard, with outputs chained via points_lay

### recovered-4cb8772d44c58cc4  [full_workflow | operator_explicit | L3_deterministic_paraphrase]
TASK: Compute the intersection of two layers, then subtract an overlay region from the intersection result.
GOLD: intersection[0] -> difference[1]
  sinks: [1] | multi=single
SRC: script_0000903.py sha=0f880d13e5 | intersection@L46-L46; difference@L59-L59
  head: QgsProject, | QgsProcessingFeatureSourceDefinition, | QgsProcessing | ) | # 입력 설정 | input_layer_names = ["1", "2"]  # 잘라낼 대상 레이어 이름 리스트
STRIP: ['INPUT', 'OUTPUT', 'OVERLAY']
AMB: [dual-review] script_0000903.py:46,59 confirms native:intersection -> native:difference, with the difference INPUT taken from the intersection output (lines 56-57). The only listed transform, QgsProce

### recovered-55d364d9cdcd6585  [full_workflow | planning_oriented | L2_deterministic_composition]
TASK: Enrich each watershed feature with a chain of derived attributes -- its area, the centroid coordinates, and the outlet coordinates -- each attribute computed from the layer produced by the previous step.
GOLD: fieldcalculator[0] -> fieldcalculator[1] -> fieldcalculator[2] -> fieldcalculator[3] -> fieldcalculator[4]
  sinks: [4] | multi=single
SRC: script_0007946.py sha=2af3391d81 | fieldcalculator@L531-L545; fieldcalculator@L547-L561; fieldcalculator@L566-L580; fieldcalculator@L585-L599; fieldcalculator@L604-L618
  head: QgsVectorLayer, | QgsExpression, | QgsField, | QgsFeature, | QgsFeatureSink, | QgsProcessing,
STRIP: ['FIELD_LENGTH', 'FIELD_NAME', 'FIELD_PRECISION', 'FIELD_TYPE', 'FORMULA', 'INPUT', 'OUTPUT']
AMB: [dual-review] Full read of script_0007946.py verified all five native:fieldcalculator calls chained area->centroid_x->centroid_y->outlet_x->outlet_y (lines 531-618), exactly matching edges [[0,1],[1,2

### recovered-5900c6409f7a6294  [full_workflow | planning_oriented | L1_source_description_stripped]
TASK: Assess flood exposure: derive the flood extent from a raster, convert it to polygons, buffer the waterways, combine the flood polygons and the buffered waterways into a single flood-impact layer, and extract the exposed areas from it.
GOLD: rastercalculator[0] -> polygonize[1] -> buffer[2] -> mergevectorlayers[3] -> union[4] -> extractbylocation[5]
  sinks: [5] | multi=single
SRC: script_4838.py sha=cdd0ea9f85 | rastercalculator@L127-L132; polygonize@L134-L137; buffer@L141-L145; mergevectorlayers@L150-L153; union@L156-L160; extractbylocation@L176-L181
  head: # -*- coding: utf-8 -*- | """ | /*************************************************************************** | FloodRisk | A QGIS plugin | This plugin works by assessing the risk of flooding in areas
STRIP: ['BAND_A', 'DISTANCE', 'FORMULA', 'INPUT', 'INPUT_A', 'INTERSECT', 'LAYERS', 'OUTPUT', 'OVERLAY', 'PREDICATE']
AMB: [dual-review] script_4838.py (resolved local mirror of the second source) confirms all six operators and edges: rastercalculator->polygonize (lines 121-131), polygonize and buffer fan-in to mergevecto

### recovered-7a19dc431ba7e1b8  [full_workflow | planning_oriented | L1_source_description_stripped]
TASK: Assess a sea-level-rise flood scenario: align the elevation raster, compute the flooded-area mask from the water level, bring the area of interest into the raster's coordinate system, and compute zonal statistics of the flooded mask over the area of interest.
GOLD: warpreproject[0] -> rastercalculator[1] -> reprojectlayer[2] -> zonalstatisticsfb[3]
  fan-out: 1->[2, 3]
  sinks: [3] | multi=single
SRC: script_0007090.py sha=3f56b559ae | warpreproject@L434-L441; rastercalculator@L570-L577; reprojectlayer@L593-L598; zonalstatisticsfb@L603-L608
  head: # -*- coding: utf-8 -*- | """ | DEM → Flooded extent + AOI stats (AR6 CSV + CODEC return levels) | - AR6 CSV expected at:  Data/slr_ipcc_ar6_sea_level_projection_global_total.csv | Columns: process, confidence, scenario (ssp119/126/245/370/585), | quantile (5/17/50/83/95), years 2020..2150 (metres)
STRIP: ['BAND_A', 'COLUMN_PREFIX', 'DATA_TYPE', 'EXTRA', 'FORMULA', 'INPUT', 'INPUT_A', 'INPUT_RASTER', 'MULTITHREADING', 'NODATA', 'NO_DATA', 'OPTIONS', 'OUTPUT', 'RASTER_BAND', 'RESAMPLING', 'RTYPE', 'SOURCE_CRS', 'STATISTICS', 'TARGET_CRS', 'TARGET_RESOLUTION']
AMB: [dual-review] script_0007090.py:435,571,594,604 confirms all four operators and the hybrid topology: gdal:rastercalculator output drives native:reprojectlayer of the AOI to the flooded raster's CRS (l

### recovered-81bbd4ba77af88e3  [subchain_scoped | operator_explicit | L3_deterministic_paraphrase]
TASK: Clip the input layer to a study boundary, then create buffer zones around the clipped features.
GOLD: clip[0] -> buffer[1]
  sinks: [1] | multi=single
SRC: script_0000594.py sha=f8b7eda5de | clip@L157-L157; buffer@L186-L186
  head: # -*- coding: utf-8 -*- | """ | /*************************************************************************** | Geoproceso | A QGIS plugin | Geoprocesos de datos vectoriales
STRIP: ['DISSOLVE', 'INPUT', 'OUTPUT', 'OVERLAY', 'SEGMENTS']
AMB: the setSubsetString filter is a layer method, not a call; scoped task = clip then buffer the clipped output without the per-class filtering semantics
AMB: [dual-review] script_0000594.py:157,186 and script_0000759.py:217,243 confirm native:clip -> native:buffer, with the buffer consuming a filtered sublayer of the clipped rivers (materialize, script_000

### recovered-85e32230f111f006  [subchain_scoped | operator_explicit | L1_source_description_stripped]
TASK: Merge the input layers into a single layer, then reproject the merged result to the target coordinate reference system.
GOLD: mergevectorlayers[0] -> reprojectlayer[1]
  sinks: [1] | multi=single
SRC: script_0000716.py sha=008631b91f | mergevectorlayers@L93-L96; reprojectlayer@L131-L135
  head: # load all layers from geopkg and merge/union them | # easier to create layer from selected features in various layers. | # Get the project instance | project = QgsProject.instance() | project.setCrs(QgsCoordinateReferenceSystem("EPSG:4326")) | # functions
STRIP: ['CRS', 'INPUT', 'LAYERS', 'OUTPUT', 'TARGET_CRS']
AMB: the attribute-fixing stage is edit-buffer code between the two calls; the merge->reproject edge is data-lineage through custom edits; scoped task = merge then reproject
AMB: [dual-review] script_0000716.py:93-135 confirms mergevectorlayers -> reprojectlayer, but between them the script performs substantive custom edits on the merged layer (per-feature KLC_ID overwrite, ma

### recovered-8c87bab93cfc8fe5  [subchain_scoped | operator_explicit | L3_deterministic_paraphrase]
TASK: Reproject the line layer, buffer the reprojected lines, erase the overlapping region from the buffered result, and split any multipart features of the remaining areas into single parts.
GOLD: reprojectlayer[0] -> buffer[1] -> difference[2] -> multiparttosingleparts[3]
  sinks: [3] | multi=single
SRC: script_0000736.py sha=09e18978e4 | reprojectlayer@L20-L20; buffer@L22-L22; difference@L28-L28; multiparttosingleparts@L49-L49
  head: conic_proj4 = "+proj=eqdc +lat_0=0 +lon_0=100 +lat_1=46.4 +lat_2=71.8 +x_0=0 +y_0=0 +ellps=GSK2011 +units=m +no_defs" | conic_crs = QgsCoordinateReferenceSystem() | conic_crs.createFromProj4(conic_proj4) | QgsProject.instance().setCrs(conic_crs) | active_id = iface.activeLayer().id() if iface.active
STRIP: ['DISTANCE', 'INPUT', 'OUTPUT', 'OVERLAY', 'SEGMENTS', 'TARGET_CRS']
AMB: scoped task must not describe the rebuild
AMB: [dual-review] script_0000736.py:20,22,28,49 confirms reproject -> buffer -> difference as direct calls, but the difference output is rebuilt into a new memory layer with FID stripped (lines 30-47) bef

### recovered-98b45c90e33c0954  [full_workflow | operator_explicit | L1_source_description_stripped]
TASK: Clip the sample points to the validation extent and sample the raster values at the clipped point locations.
GOLD: clip[0] -> rastersampling[1]
  sinks: [1] | multi=single
SRC: script_0000792.py sha=1d9f0190db | clip@L19-L19; rastersampling@L28-L28
  head: def differences(point_layer, extent, raster, field): | # Select only points used for interpolation | clip_params = { | 'INPUT': point_layer, | 'OVERLAY': extent, | 'OUTPUT': 'TEMPORARY_OUTPUT'
STRIP: ['COLUMN_PREFIX', 'INPUT', 'OUTPUT', 'OVERLAY']
AMB: [dual-review] script_0000792.py:19,28 confirms native:clip -> native:rastersampling on the clipped points, with the sampling INPUT taken from the clip output (lines 21-27). The downstream code is RMSE

### recovered-c5863951f3b98f92  [full_workflow | planning_oriented | L2_deterministic_composition]
TASK: Merge the yearly event layers of the region into one layer, then split any multipart geometries into single parts.
GOLD: mergevectorlayers[0] -> multiparttosingleparts[1]
  sinks: [1] | multi=single
SRC: script_41874.py sha=d0193949a3 | mergevectorlayers@L17-L17; multiparttosingleparts@L21-L21
  head: country = 'vietnam' | # subsetting yearly fires | directory = Path(r"E:\WORK January 2024\yearlycountryfires\sea\{}".format(country)) | layers = glob.glob(str(directory) + '/*.shp') | destination = str(directory.joinpath("{}_2012-2023.shp".format(country))) | parameters = {'LAYERS': layers,
STRIP: ['CRS', 'INPUT', 'OUTPUT']
AMB: [dual-review] The source is a non-resolvable Linux replay path, but the capped snippet shows a complete self-contained script: qgis:mergevectorlayers -> qgis:multiparttosingleparts chained exactly as 

### recovered-d57f26d6bca916c9  [full_workflow | planning_oriented | L1_source_description_stripped]
TASK: Build a series of nested buffer zones around the road network, each successive zone grown from the previous buffer's extent.
GOLD: buffer[0] -> buffer[1] -> buffer[2]
  sinks: [2] | multi=single
SRC: script_31926.py sha=1e0b9d9548 | buffer@L28-L28; buffer@L35-L35; buffer@L40-L40
  head: """ Import data libraries """ | """ Task 1. Adding Geopackae as Layers into QGIS """ | """ 1.2. Creating a Dialog Box to ask for User Input on File to Add """ | envPath = QFileDialog.getOpenFileName(QFileDialog(), "Environment Layer Select", "/home/abhishek/Desktop/M.Sc-GIS/data")[0] | """ 1.3. Addi
STRIP: ['DISSOLVE', 'DISTANCE', 'END_CAP_STYLE', 'INPUT', 'JOIN_STYLE', 'MITER_LIMIT', 'OUTPUT', 'SEGMENTS']
AMB: [dual-review] The local mirror script_31926.py (same merged-dedup root) confirms the nested three-buffer chain autobahn20->autobahn100->autobahn300 with each buffer's INPUT reassigning the previous ou

### recovered-debe9501a653ec47  [full_workflow | planning_oriented | L1_source_description_stripped]
TASK: Remove the redundant geometry-attribute column from the input layer, then add a computed area attribute to each feature.
GOLD: deletecolumn[0] -> fieldcalculator[1]
  sinks: [1] | multi=single
SRC: script_37222.py sha=12d3d23414 | deletecolumn@L10-L12; fieldcalculator@L15-L23
  head: # source: https://courses.spatialthoughts.com/pyqgis-in-a-day.html#saving-layers-to-disk | data_dir = os.path.join(os.path.expanduser('~'), 'Downloads', 'pyqgis_in_a_day') | filename = 'sf.gpkg|layername=blocks' | uri = os.path.join(data_dir, filename) | blocks = QgsVectorLayer(uri, 'blocks', 'ogr')
STRIP: ['COLUMN', 'FIELD_LENGTH', 'FIELD_NAME', 'FIELD_PRECISION', 'FIELD_TYPE', 'FORMULA', 'INPUT', 'NEW_FIELD', 'OUTPUT']
AMB: [dual-review] The source path is a non-resolvable Linux replay path, but the capped snippet plus sha256 show a complete self-contained script: qgis:deletecolumn (COLUMN multigeom) -> qgis:fieldcalcula

### recovered-dec749a979996d6f  [full_workflow | planning_oriented | L1_source_description_stripped]
TASK: Identify thermal refugia locations from a classified raster: convert the valid mask cells to polygons, keep only the qualifying patches, add an area attribute to each patch, filter the patches further by a condition, and compute the raster statistics for every remaining patch.
GOLD: polygonize[0] -> extractbyattribute[1] -> fieldcalculator[2] -> extractbyexpression[3] -> zonalstatistics[4]
  sinks: [4] | multi=single
SRC: script_6649.py sha=8e5f3b705e | polygonize@L66-L72; extractbyattribute@L81-L87; fieldcalculator@L96-L104; extractbyexpression@L111-L115; zonalstatistics@L126-L132
  head: # Polygonize and identify locations of Thermal Refugia | # Date: January 2026 | # by: JPena | # --------------------------------------------- | #  Polygonizes a clean mask raster | #  Computes mean temperature per patch
STRIP: ['BAND', 'COLUMN_PREFIX', 'EIGHT_CONNECTEDNESS', 'EXPRESSION', 'FIELD', 'FIELD_LENGTH', 'FIELD_NAME', 'FIELD_PRECISION', 'FIELD_TYPE', 'FORMULA', 'INPUT', 'INPUT_RASTER', 'INPUT_VECTOR', 'OPERATOR', 'OUTPUT', 'RASTER_BAND', 'STATISTICS', 'VALUE']
AMB: [dual-review] script_6649.py:66,81,96,111,126 confirms the five-step linear chain polygonize->extractbyattribute->fieldcalculator->extractbyexpression->zonal-statistics with all edges real, but the fi

### recovered-dfeda93ca52d334e  [subchain_scoped | operator_explicit | L1_source_description_stripped]
TASK: Compute the minimum bounding geometry of the input features and extract the vertices of that bounding geometry as points.
GOLD: minimumboundinggeometry[0] -> extractvertices[1]
  sinks: [1] | multi=single
SRC: script_0000439.py sha=26e5daaf56 | minimumboundinggeometry@L52-L52; extractvertices@L55-L55
  head: #PARAMETERS AND LAYERS | rotation = 45 #use any value between 0 and <90 #90 would make a mess | layer1 = iface.activeLayer() # Load the layer (from active) | crs = layer1.crs().authid() #get crs | #---------------------------------------------------------------------------------------- | #LINE EQUAT
STRIP: ['FIELD', 'INPUT', 'OUTPUT', 'TYPE']
AMB: scoped to convex-hull vertex extraction per adjudication
AMB: [dual-review] script_0000439.py:52-55 confirms qgis:minimumboundinggeometry -> native:extractvertices exactly as recorded, but the script's substance is a pure-Python rotated-bounding-box computation 

### recovered-f950402772c6e9d1  [subchain_scoped | operator_explicit | L1_source_description_stripped]
TASK: Reproject the stream segments and, from the reprojected segments, extract two separate outputs: the starting vertices of every segment and the ending vertices of every segment.
GOLD: reprojectlayer[0] -> extractspecificvertices[1] -> extractspecificvertices[2]
  fan-out: 0->[1, 2]
  sinks: [1, 2] | multi=multi
SRC: script_0000749.py sha=7160bcf772 | reprojectlayer@L98-L105; extractspecificvertices@L121-L128; extractspecificvertices@L131-L138
  head: # -*- coding: utf-8 -*- | """ | /*************************************************************************** | HydroUtils | A QGIS plugin | Identifie le bassin versant de polygones d'intérêt
STRIP: ['INPUT', 'OUTPUT', 'TARGET_CRS', 'VERTICES']
AMB: pure_branch retained; the with-edit FID bookkeeping (script_0000749.py L102-111) is script-internal provenance, not task semantics; scoped task = reproject then extract first and last vertices as two 
AMB: [dual-review] script_0000749.py:98,121,131 confirms reprojectlayer feeding two native:extractspecificvertices calls (fan-out [[0,1],[0,2]]), but a mid-chain 'with edit' block (lines 102-111) adds and 

### recovered-fc01749f30a8e4ea  [full_workflow | planning_oriented | L1_source_description_stripped]
TASK: Build a series of nested buffer zones around the road network, then combine them through successive unions into a single overall impact-area layer.
GOLD: buffer[0] -> buffer[1] -> buffer[2] -> union[3] -> union[4]
  fan-out: 0->[1, 3], 1->[2, 3]
  sinks: [4] | multi=single
SRC: script_31927.py sha=6d5e91f918 | buffer@L28-L28; buffer@L35-L35; buffer@L40-L40; union@L46-L46; union@L51-L51
  head: """ Import data libraries """ | """ Task 1. Adding Geopackae as Layers into QGIS """ | """ 1.2. Creating a Dialog Box to ask for User Input on File to Add """ | envPath = QFileDialog.getOpenFileName(QFileDialog(), "Environment Layer Select", "/home/abhishek/Desktop/M.Sc-GIS/data")[0] | """ 1.3. Addi
STRIP: ['DISSOLVE', 'DISTANCE', 'END_CAP_STYLE', 'INPUT', 'JOIN_STYLE', 'MITER_LIMIT', 'OUTPUT', 'OVERLAY', 'SEGMENTS']
AMB: source-verified correction (v02_recovered_dag_corrections_v1.json); every operator and edge is a real processing.run call in script_31927.py; requires dual re-review before admission
AMB: [dual-review] The local mirror script_31927.py:45-51 shows the true structure: the three buffers are chained, but union #1 consumes autobahn20 AND autobahn100 (INPUT/OVERLAY) and union #2 consumes inn
