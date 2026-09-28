# QGIS stable101 Source Review Pack

This report joins the stable101 50-row chain-level candidate batch back to source files. It is for human review only and does not grant training admission.

## Summary

- Review rows: 179
- Joined sources: 179
- Snippets containing all ordered operators: 179
- Source roots: `{"standard_v2": 135, "workflow": 20, "workflow_A": 24}`
- Modalities: `{"mixed": 71, "pure_raster": 7, "pure_vector": 101}`
- Text quality: `{"usable_seed_text": 89, "weak_code_fragment": 1, "weak_metadata": 3, "weak_short_or_empty": 78, "weak_symbol_or_method": 4, "weak_too_few_words": 4}`
- Taxonomy admission: `granted_for_four_stable101_mappings`
- Training admission: `not_granted`

## Review Rows

| # | source | chain freq | modality | operators | source file | task seed |
|---:|---|---:|---|---|---|---|
| 1 | standard_v2 | 3 | mixed | `gdal:rasterize -> native:fixgeometries -> native:zonalstatisticsfb -> native:zonalhistogram` | `script_0000343.py` | Model exported as python. initAlgorithm |
| 2 | standard_v2 | 6 | mixed | `gdal:assignprojection -> native:assignprojection -> native:extractbyextent -> native:fixgeometries -> native:reprojectlayer -> gdal:buildvirtualraster` | `script_0000061.py` | 📦 Utilities module. assign crs to raster layer |
| 3 | standard_v2 | 2 | mixed | `native:reprojectlayer -> gdal:rasterize -> gdal:cliprasterbyextent` | `script_0001000.py` | generate_tiles.py load config |
| 4 | standard_v2 | 66 | mixed | `native:reclassifybytable -> native:reclassifybytable -> native:reclassifybytable -> gdal:polygonize -> native:zonalstatisticsfb` | `script_0000231.py` | Module 7: Market Classification & Zoning |
| 5 | standard_v2 | 6 | mixed | `gdal:warpreproject -> native:fillnodata -> gdal:rasterize -> gdal:cliprasterbymasklayer` | `script_0000067.py` | 📦 Workflow Base module. init |
| 6 | standard_v2 | 6 | mixed | `native:buffer -> native:clip -> gdal:rasterize -> gdal:warpreproject -> gdal:rastercalculator` | `script_0000058.py` | 📦 Opportunities Mask Processor module. init |
| 7 | standard_v2 | 3 | pure_vector | `native:fixgeometries -> native:reprojectlayer -> native:difference -> native:mergevectorlayers` | `script_0000895.py` | Remove acentos e converte para minúsculas init |
| 8 | standard_v2 | 4 | pure_vector | `native:union -> native:multiparttosingleparts -> native:fixgeometries -> native:multiparttosingleparts -> native:reprojectlayer` | `script_0000973.py` | Decorator to catch sql exceptions. sql error handler |
| 9 | standard_v2 | 3 | pure_vector | `native:fixgeometries -> native:extractbyattribute -> native:reprojectlayer -> native:refactorfields -> native:refactorfields -> native:savefeatures` | `script_0000872.py` | Model exported as python (patched). initAlgorithm |
| 10 | standard_v2 | 3 | pure_vector | `native:fixgeometries -> native:reprojectlayer -> native:intersection -> native:difference -> native:intersection -> native:difference -> native:difference -> native:mergevectorlayers` | `script_0000894.py` | Remove acentos e converte para minúsculas init |
| 11 | standard_v2 | 7 | pure_vector | `native:reprojectlayer -> native:buffer -> native:clip` | `script_0000048.py` | PyQGIS Code Snippets |
| 12 | standard_v2 | 6 | pure_vector | `native:fixgeometries -> native:retainfields -> native:zonalstatisticsfb` | `script_0000060.py` | 📦 Subnational Aggregation Processor module. init |
| 13 | standard_v2 | 3 | mixed | `native:buffer -> native:union -> native:promotetomulti -> native:polygonfromlayerextent -> gdal:clipvectorbypolygon -> gdal:rasterize -> gdal:warpreproject` | `script_0000375.py` | build water rasterized |
| 14 | standard_v2 | 3 | mixed | `native:clip -> gdal:polygonize -> gdal:cliprasterbyextent` | `script_0000820.py` | Clip a QgsVector layer by different QgsVector layer simple clip |
| 15 | standard_v2 | 3 | mixed | `native:extractbylocation -> gdal:rasterize -> gdal:cliprasterbymasklayer` | `script_0000315.py` | Model exported as python. initAlgorithm |
| 16 | standard_v2 | 12 | pure_vector | `native:fixgeometries -> native:clip` | `script_0000034.py` | Fix invalid geometries in input layer and return temporary layer with valid geoms fix geom |
| 17 | workflow | 14 | pure_vector | `native:fixgeometries -> native:zonalstatisticsfb` | `script_0005583.py` | Calculate the height of bounding box in meters calculate centroid |
| 18 | standard_v2 | 3 | mixed | `qgis:rastercalculator -> gdal:polygonize -> native:buffer -> gdal:cliprasterbymasklayer` | `script_0000313.py` | Model exported as python. initAlgorithm |
| 19 | standard_v2 | 1 | pure_vector | `native:fixgeometries -> native:reprojectlayer -> native:extractbyextent -> native:fieldcalculator` | `script_0000977.py` | Clip layer by extent clip in projectcrs |
| 20 | workflow_A | 1 | pure_vector | `native:reprojectlayer -> native:fixgeometries -> native:clip` | `script_0007153.py` | USDA Soil Data Retrieval - Final Production Version (v2.0) init |
| 21 | workflow | 2 | mixed | `gdal:polygonize -> native:extractbyattribute -> gdal:cliprasterbymasklayer` | `script_0007653.py` | Black Frame Remover: main.py v1.1.0 init |
| 22 | workflow | 2 | mixed | `qgis:rastercalculator -> gdal:polygonize -> native:dissolve` | `script_0007273.py` | 1. Находит в проекте растр по имени `raster_name`. create single polygon per color |
| 23 | standard_v2 | 6 | pure_vector | `native:mergevectorlayers -> native:dissolve -> native:difference -> native:mergevectorlayers -> native:reprojectlayer` | `script_0000065.py` | 📦 Multi Buffer Distances Ors Workflow module. init |
| 24 | standard_v2 | 7 | pure_vector | `native:reprojectlayer -> native:intersection` | `script_0000899.py` | CN Calculator Tool for Hydro Suite init |
| 25 | workflow | 21 | pure_vector | `native:reprojectlayer -> native:reprojectlayer` | `script_0001443.py` | This algorithm generates a full sidewalk network based on OSM data within a specified boun |
| 26 | workflow_A | 4 | mixed | `gdal:warpreproject -> native:reprojectlayer -> native:rastersampling` | `script_0007138.py` | process raster sample points |
| 27 | standard_v2 | 6 | pure_vector | `native:reprojectlayer -> native:clip` | `script_0000063.py` | 📦 Osm Data Downloader Base module. init |
| 28 | standard_v2 | 6 | pure_vector | `native:reprojectlayer -> native:extractbyexpression` | `script_0000269.py` | reproject layer if needed |
| 29 | standard_v2 | 3 | pure_raster | `gdal:cliprasterbymasklayer -> gdal:warpreproject -> gdal:polygonize -> gdal:hillshade` | `script_0000434.py` | Bilinear interpolation of raster value at (x, y). cleanup file |
| 30 | workflow_A | 3 | pure_raster | `gdal:slope -> gdal:hillshade -> qgis:rastercalculator -> gdal:polygonize` | `script_0007230.py` | Initialize the Debris Flow Paths Detector init |
| 31 | workflow_A | 1 | pure_vector | `native:dissolve -> native:reprojectlayer -> native:fixgeometries -> native:reprojectlayer -> native:intersection` | `script_0007151.py` | Multi-Basin CN Generation Runner Script (v2.0) init |
| 32 | standard_v2 | 3 | pure_vector | `native:extractbyexpression -> native:intersection -> native:dissolve -> native:retainfields -> native:reprojectlayer -> native:fieldcalculator -> native:savefeatures` | `script_0000902.py` | Script using pyqgis |
| 33 | standard_v2 | 3 | pure_vector | `native:fixgeometries -> native:buffer -> native:difference` | `script_0000553.py` | The script defines functions that can be used in the QGIS python console to speed up the g |
| 34 | standard_v2 | 3 | pure_vector | `native:fixgeometries -> native:multiparttosingleparts -> native:clip -> native:extractbyexpression` | `script_0000817.py` | Fixes the geometries of a shapefile and saves the fixed version. fix geometries |
| 35 | standard_v2 | 7 | mixed | `native:reprojectlayer -> gdal:warpreproject` | `script_0000958.py` | Simple feedback object that prints all messages to console reportError |
| 36 | standard_v2 | 3 | pure_vector | `native:reprojectlayer -> native:clip -> native:buffer -> native:dissolve -> native:difference -> native:mergevectorlayers` | `script_0000064.py` | Multi-buffer distances workflow using native QGIS network analysis. init |
| 37 | workflow_A | 1 | pure_vector | `native:reprojectlayer -> native:fixgeometries -> native:clip -> native:reprojectlayer -> native:fixgeometries` | `script_0007152.py` | Simple USDA Soil Retrieval - Matches CN Generator pattern exactly. get soil data |
| 38 | standard_v2 | 3 | pure_vector | `native:reprojectlayer -> native:joinattributesbylocation -> native:multiintersection` | `script_0000754.py` | Quite specific to the French case. Add a boolean attribute, for every building of a vector |
| 39 | standard_v2 | 3 | pure_vector | `native:reprojectlayer -> native:renametablefield -> native:retainfields` | `script_0000592.py` | parse time interval |
| 40 | standard_v2 | 6 | mixed | `native:reprojectlayer -> gdal:cliprasterbymasklayer` | `script_0000956.py` | Create a new print layout and remove any previous layout with the same name. create layout |
| 41 | standard_v2 | 3 | mixed | `gdal:warpreproject -> native:reprojectlayer -> gdal:cliprasterbymasklayer` | `script_0001002.py` | some utils func with qgis sauce reproject raster |
| 42 | standard_v2 | 3 | mixed | `native:reprojectlayer -> gdal:cliprasterbymasklayer -> gdal:cliprasterbyextent -> gdal:translate -> gdal:warpreproject -> gdal:rastercalculator` | `script_0000442.py` | Calculates the Curve Number using global datasets from ESA WorldCover and ORNL HYSOG. init |
| 43 | workflow | 2 | mixed | `gdal:rasterize -> gdal:translate` | `script_0008220.py` | Create binary masks from selected vector layers, based on a single chosen DTM tile extent, |
| 44 | workflow | 2 | pure_vector | `native:fixgeometries -> native:dissolve -> native:polygonize` | `script_0007127.py` | SolarPanelGenerator Plugin Coverage Logic init |
| 45 | standard_v2 | 2 | pure_vector | `native:reprojectlayer -> native:clip -> native:buffer -> native:joinattributesbylocation -> native:savefeatures` | `script_0000670.py` | Executor Agent — PyQGIS 脚本注入执行与闭环自愈验证. verify hash |
| 46 | workflow_A | 4 | pure_vector | `native:reprojectlayer -> native:zonalstatisticsfb` | `script_0007087.py` | Area Comparison Analysis Algorithm |
| 47 | standard_v2 | 6 | pure_vector | `native:reprojectlayer -> native:reprojectlayer -> native:fixgeometries -> native:fixgeometries -> native:fixgeometries -> native:intersection -> native:intersection -> native:fieldcalculator -> native:fieldcalculator -> native:fieldcalculator -> native:fieldcalculator -> native:fieldcalculator -> native:fieldcalculator -> native:fieldcalculator` | `script_0000540.py` | WHEN "class_name" = 'Built-up' THEN 'Concrete' initAlgorithm |
| 48 | standard_v2 | 3 | mixed | `gdal:warpreproject -> native:reclassifybytable -> gdal:polygonize -> native:fixgeometries -> native:zonalstatisticsfb -> native:fieldcalculator -> native:extractbyexpression -> native:fieldcalculator -> native:centroids` | `script_0000493.py` | Automated Keyline Keypoint Detection Algorithm |
| 49 | standard_v2 | 3 | mixed | `gdal:warpreproject -> saga:fillsinksxxlwangliu -> native:zonalstatistics -> native:zonalstatistics -> gdal:cliprasterbyextent -> native:fixgeometries -> native:buffer -> native:clip -> native:clip -> gdal:polygonize -> native:zonalstatistics -> native:zonalstatistics` | `script_0000498.py` | HydroAnalysis.py - Module d'analyse hydrologique pour SigLogix (QGIS) init |
| 50 | standard_v2 | 3 | mixed | `native:extractbyextent -> native:fixgeometries -> native:clip -> native:reprojectlayer -> gdal:rasterize -> gdal:warpreproject -> native:savefeatures -> native:reprojectlayer -> native:fixgeometries -> native:clip -> native:multiparttosingleparts -> native:reprojectlayer` | `script_0000833.py` | Dialog for filtering vector layer features by attribute values. init |
| 51 | standard_v2 | 3 | pure_vector | `native:fixgeometries -> native:fixgeometries -> native:fixgeometries -> native:clip -> native:clip` | `script_0000349.py` | Model exported as python. initAlgorithm |
| 52 | standard_v2 | 3 | pure_vector | `native:fixgeometries -> native:fixgeometries -> native:fixgeometries -> native:mergevectorlayers -> native:dissolve` | `script_0000363.py` | This makes parameters for wfs-request of specific area getBboxWmsFormat |
| 53 | standard_v2 | 3 | pure_vector | `native:reprojectlayer -> native:clip -> native:reprojectlayer` | `script_0000827.py` | Download features from an ArcGIS Feature/MapServer layer using paged requests, return Feat |
| 54 | standard_v2 | 3 | pure_vector | `native:reprojectlayer -> native:rastersampling -> native:zonalstatisticsfb -> native:reprojectlayer -> native:savefeatures` | `script_0000918.py` | v0.2 2024-09-03 rainfall factor |
| 55 | standard_v2 | 3 | pure_vector | `native:reprojectlayer -> native:reprojectlayer -> native:buffer -> native:clip -> native:fieldcalculator` | `script_0000668.py` | Vector Geoprocessing — PyQGIS Processing Script |
| 56 | standard_v2 | 3 | pure_vector | `native:reprojectlayer -> native:reprojectlayer -> native:reprojectlayer -> native:buffer -> qgis:joinbylocationsummary -> qgis:joinbylocationsummary -> native:fieldcalculator -> native:reprojectlayer` | `script_0000718.py` | Sample 02: Right-of-Way Vegetation + Flood Risk load layer |
| 57 | standard_v2 | 3 | pure_vector | `native:reprojectlayer -> native:reprojectlayer -> native:savefeatures -> native:clip` | `script_0000871.py` | Return all polygon vector layers currently loaded in the project. polygon layers |
| 58 | standard_v2 | 3 | pure_vector | `native:reprojectlayer -> native:union -> native:union -> native:reprojectlayer` | `script_0000831.py` | select nombre_esquema,nombre_capa from acervo_descripcion_1.mapa_master_vw where id in (se |
| 59 | workflow_A | 2 | mixed | `gdal:warpreproject -> gdal:rastercalculator -> native:reprojectlayer -> native:zonalstatisticsfb` | `script_0007089.py` | DEM → Flooded extent + AOI stats (AR6 CSV; matches your Data schema) |
| 60 | standard_v2 | 2 | mixed | `native:reprojectlayer -> gdal:cliprasterbyextent -> gdal:rastercalculator` | `script_0000038.py` | Manning's Roughness Generator - A QGIS Plugin name |
| 61 | workflow_A | 2 | mixed | `native:reprojectlayer -> native:buffer -> native:clip -> native:intersection -> native:dissolve -> qgis:rastercalculator` | `script_0007210.py` | Code Generator Module init |
| 62 | standard_v2 | 3 | mixed | `gdal:cliprasterbyextent -> gdal:warpreproject -> native:reprojectlayer -> gdal:warpreproject` | `script_0000999.py` | get shapefile as json pyqgis |
| 63 | workflow_A | 1 | mixed | `gdal:rastercalculator -> gdal:rastercalculator -> gdal:polygonize -> native:fieldcalculator` | `script_0007163.py` | Fonction pour lancer le calcul NDVI depuis main.py initAlgorithm |
| 64 | workflow_A | 1 | mixed | `gdal:translate -> gdal:fillnodata -> gdal:translate -> gdal:sieve -> gdal:polygonize -> native:extractbyattribute` | `script_0007175.py` | Writes a raster where pixels in [min_val, max_val] become 1, else 0. create range mask |
| 65 | standard_v2 | 3 | pure_raster | `native:reclassifybytable -> gdal:polygonize` | `script_0000888.py` | Aplica a simbologia categorizada no campo 'DN'. definir simbologia vetor |
| 66 | standard_v2 | 3 | pure_vector | `native:reprojectlayer -> native:retainfields` | `script_0000593.py` | parse time interval |
| 67 | workflow | 2 | pure_vector | `native:fixgeometries -> native:fixgeometries -> native:fixgeometries -> native:fixgeometries -> native:fixgeometries` | `script_0006060.py` | Modulo: AyudasGEO RegisterFunction |
| 68 | standard_v2 | 2 | pure_vector | `native:reprojectlayer -> native:buffer -> native:reprojectlayer` | `script_0000730.py` | PyQGIS pipeline — builds a QGIS project with styled layers, buffers, and per-school map ex |
| 69 | workflow_A | 1 | mixed | `gdal:polygonize -> native:zonalstatisticsfb` | `script_0007007.py` | Stage 4: Zonal Statistics vectorize mask |
| 70 | workflow_A | 1 | pure_vector | `native:extractbylocation -> native:fixgeometries -> native:intersection` | `script_0007279.py` | GeoLote - Plugin QGIS sanitize field name |
| 71 | workflow_A | 1 | pure_vector | `native:reprojectlayer -> native:extractbyexpression -> native:mergevectorlayers` | `script_0006964.py` | This class is responsible for loading, optionally filtering, and merging vector layers fro |
| 72 | standard_v2 | 2 | pure_raster | `gdal:rastercalculator -> gdal:polygonize` | `script_0000882.py` | This shared script processes a raster dataset (NDVI) by performing the following steps: |
| 73 | workflow_A | 2 | mixed | `gdal:warpreproject -> native:reprojectlayer -> native:rastersampling -> native:buffer -> native:zonalstatisticsfb -> native:buffer -> native:zonalstatisticsfb` | `script_0007140.py` | process raster points buffer zonal |
| 74 | workflow | 2 | mixed | `native:extractbyattribute -> native:reprojectlayer -> gdal:cliprasterbymasklayer -> gdal:warpreproject -> native:reprojectlayer -> native:clip -> native:rastersampling -> native:rastersampling` | `script_0005345.py` | Generates random non-fire points within the BC boundary. get hotspots |
| 75 | workflow_A | 1 | mixed | `gdal:warpreproject -> native:reprojectlayer -> native:rastersampling -> native:buffer -> native:zonalstatisticsfb` | `script_0007141.py` | process raster points buffer zonal |
| 76 | standard_v2 | 2 | mixed | `gdal:warpreproject -> native:reprojectlayer` | `script_0000669.py` | 重投影 Skill — 支持矢量和栅格. |
| 77 | workflow_A | 1 | pure_vector | `native:buffer -> native:buffer -> native:extractbylocation -> native:reprojectlayer -> native:reprojectlayer` | `script_0007428.py` | Spatial analysis tools for geometry operations and spatial queries. register tools |
| 78 | workflow_A | 1 | pure_vector | `native:reprojectlayer -> native:dissolve -> native:union -> native:difference -> native:difference` | `script_0007069.py` | select layer interactively |
| 79 | workflow | 2 | pure_raster | `gdal:polygonize -> gdal:polygonize` | `script_0005627.py` | transfrom input buffer zone raster to vector raster2vector |
| 80 | standard_v2 | 1 | pure_vector | `native:multiparttosingleparts -> native:reprojectlayer` | `script_0000994.py` | POST an Overpass QL query to each mirror until one returns 2xx. overpass post |
| 81 | standard_v2 | 1 | pure_vector | `native:reprojectlayer -> native:savefeatures` | `script_0000978.py` | Utility functions for olive tree canopy segmentation using Otsu. load layer from output |
| 82 | standard_v2 | 3 | mixed | `gdal:polygonize -> gdal:polygonize -> native:clip -> gdal:polygonize -> native:buffer -> native:clip -> native:buffer -> native:buffer -> native:buffer -> native:dissolve -> native:clip` | `script_0000469.py` | to avoid havign to use "stroke to path" which keeps crashing in inkscape buffer params |
| 83 | standard_v2 | 3 | mixed | `gdal:polygonize -> native:extractbyexpression -> native:dissolve -> gdal:polygonize -> native:extractbyexpression -> native:fieldcalculator -> native:fieldcalculator -> native:zonalstatisticsfb -> native:zonalstatisticsfb -> native:zonalstatisticsfb -> native:fieldcalculator` | `script_0000342.py` | <h3>Analisi del Catchment</h3> name |
| 84 | standard_v2 | 1 | pure_vector | `native:renametablefield -> native:renametablefield -> native:assignprojection -> native:fixgeometries -> native:reprojectlayer -> native:promotetomulti -> native:reprojectlayer -> native:joinattributesbylocation -> native:fieldcalculator` | `script_0000909.py` | ensure plugins path |
| 85 | standard_v2 | 3 | pure_vector | `native:difference -> native:dissolve -> native:dissolve -> native:mergevectorlayers -> native:fixgeometries -> native:difference -> native:removenullgeometries -> native:fixgeometries -> native:fixgeometries -> native:union -> native:fixgeometries -> native:mergevectorlayers` | `script_0000819.py` | Apply a simple difference operation to the input layers. apply simple difference |
| 86 | standard_v2 | 3 | pure_vector | `native:extractbyexpression -> native:intersection -> native:intersection -> native:dissolve -> native:dissolve -> native:refactorfields -> native:fixgeometries -> native:refactorfields -> native:fixgeometries -> native:promotetomulti -> native:promotetomulti -> native:dissolve -> native:dissolve -> native:refactorfields -> native:refactorfields` | `script_0000844.py` | Model exported as python. initAlgorithm |
| 87 | standard_v2 | 3 | pure_vector | `native:refactorfields -> native:refactorfields -> native:extractbyattribute -> native:extractbyattribute -> native:fixgeometries -> native:fixgeometries -> native:mergevectorlayers -> native:refactorfields -> native:dissolve -> native:refactorfields` | `script_0000847.py` | Model exported as python. initAlgorithm |
| 88 | standard_v2 | 3 | pure_vector | `native:reprojectlayer -> native:reprojectlayer -> native:reprojectlayer -> native:buffer -> qgis:joinbylocationsummary -> native:buffer -> qgis:joinbylocationsummary -> native:fieldcalculator -> native:dbscanclustering -> native:reprojectlayer -> native:reprojectlayer` | `script_0000717.py` | Sample 01: Utility Outage Prioritization load layer |
| 89 | workflow | 2 | mixed | `native:reprojectlayer -> native:buffer -> gdal:cliprasterbyextent -> gdal:cliprasterbyextent -> gdal:cliprasterbyextent -> native:reprojectlayer -> gdal:clipvectorbyextent -> native:union -> native:reprojectlayer` | `script_0002885.py` | Created on Fri May 1 12:39:38 2020 optimisationCalcul |
| 90 | standard_v2 | 5 | pure_vector | `native:reprojectlayer -> gdal:rasterize` | `script_0000751.py` | get config |
| 91 | standard_v2 | 3 | mixed | `gdal:polygonize -> native:buffer -> gdal:rasterize` | `script_0000622.py` |  |
| 92 | standard_v2 | 3 | mixed | `gdal:rgbtopct -> gdal:polygonize -> native:extractbyattribute -> native:fixgeometries` | `script_0000695.py` |  |
| 93 | standard_v2 | 12 | pure_vector | `native:dissolve -> native:fieldcalculator -> native:intersection -> native:dissolve -> gdal:rasterize -> native:zonalstatisticsfb -> native:zonalstatisticsfb` | `script_0000080.py` | init |
| 94 | standard_v2 | 4 | mixed | `gdal:rasterize -> gdal:polygonize` | `script_0000359.txt` | getBboxWmsFormat |
| 95 | standard_v2 | 3 | pure_vector | `native:difference -> native:buffer -> native:clip -> native:fixgeometries -> native:mergevectorlayers -> native:reprojectlayer` | `script_0000783.py` | config |
| 96 | standard_v2 | 3 | pure_vector | `native:fixgeometries -> native:dissolve -> native:reprojectlayer` | `script_0000972.py` | init |
| 97 | standard_v2 | 3 | pure_vector | `native:fixgeometries -> native:joinattributesbylocation -> native:reprojectlayer -> native:extractbyexpression -> native:dissolve` | `script_0000686.py` | shortHelpString |
| 98 | standard_v2 | 3 | pure_vector | `native:reprojectlayer -> native:fixgeometries -> native:intersection -> native:extractbylocation` | `script_0000924.py` |  |
| 99 | workflow | 1 | mixed | `gdal:polygonize -> native:extractbyexpression -> native:fixgeometries` | `script_0005693.py` | initialize processing |
| 100 | workflow | 1 | mixed | `gdal:rasterize -> gdal:cliprasterbymasklayer -> gdal:warpreproject -> native:reprojectlayer` | `script_0007497.py` | init |
| 101 | standard_v2 | 8 | mixed | `gdal:polygonize -> native:intersection` | `script_0000448.py` | initAlgorithm |
| 102 | standard_v2 | 3 | pure_vector | `native:reprojectlayer -> native:dissolve -> native:buffer -> native:reprojectlayer -> native:intersection -> native:fixgeometries` | `script_0000696.py` |  |
| 103 | standard_v2 | 3 | mixed | `gdal:cliprasterbymasklayer -> native:clip -> native:reclassifybytable -> gdal:polygonize` | `script_0000510.py` |  |
| 104 | workflow_A | 1 | mixed | `gdal:polygonize -> native:fixgeometries -> native:dissolve -> native:zonalstatisticsfb -> native:savefeatures -> native:difference -> native:savefeatures` | `script_0007172.py` | add layer to project |
| 105 | standard_v2 | 1 | mixed | `gdal:polygonize -> native:reprojectlayer -> native:reprojectlayer -> native:joinattributesbylocation` | `script_0000980.py` | reprojected = processing.run("native:reprojectlayer", { |
| 106 | standard_v2 | 3 | mixed | `gdal:rasterize -> gdal:warpreproject -> gdal:rastercalculator -> gdal:cliprasterbymasklayer` | `script_0001027.py` | init |
| 107 | standard_v2 | 3 | mixed | `native:buffer -> native:zonalstatisticsfb -> gdal:rasterize -> gdal:merge -> saga:fillsinksxxlwangliu -> gdal:warpreproject -> native:hillshade` | `script_0000332.py` |  |
| 108 | standard_v2 | 12 | pure_vector | `native:reprojectlayer -> native:multiparttosingleparts` | `script_0000959.py` | Author: Mario Königbauer (mkoenigb@gmx.de) initAlgorithm |
| 109 | standard_v2 | 3 | mixed | `native:translategeometry -> gdal:rasterize -> gdal:cliprasterbymasklayer` | `script_0000926.py` | init |
| 110 | standard_v2 | 9 | pure_raster | `saga:upslopearea -> gdal:polygonize` | `script_0000001.py` | initAlgorithm |
| 111 | workflow_A | 1 | mixed | `gdal:polygonize -> native:fixgeometries` | `script_0006974.py` | init |
| 112 | standard_v2 | 3 | pure_vector | `gdal:rasterize -> native:fieldcalculator -> gdal:rasterize` | `script_0000275.py` | initAlgorithm |
| 113 | workflow | 4 | mixed | `gdal:polygonize -> native:dissolve` | `script_0007228.py` | init |
| 114 | standard_v2 | 9 | mixed | `gdal:translate -> native:fixgeometries` | `script_0000927.py` | qgisName |
| 115 | standard_v2 | 9 | mixed | `gdal:translate -> native:reprojectlayer` | `script_0000398.py` |  |
| 116 | standard_v2 | 3 | mixed | `gdal:polygonize -> native:joinattributesbylocation -> native:joinattributesbylocation` | `script_0000436.py` |  |
| 117 | standard_v2 | 3 | mixed | `gdal:rastercalculator -> gdal:rasterize -> gdal:rasterize -> gdal:rastercalculator` | `script_0000022.py` | initAlgorithm |
| 118 | standard_v2 | 3 | mixed | `gdal:warpreproject -> gdal:rasterize -> gdal:assignprojection -> gdal:cliprasterbymasklayer -> gdal:warpreproject -> gdal:warpreproject` | `script_0000029.py` | addAdvancedParameter |
| 119 | standard_v2 | 3 | pure_vector | `native:centroids -> native:reprojectlayer -> native:joinattributesbylocation` | `script_0000946.py` | initAlgorithm |
| 120 | standard_v2 | 3 | pure_vector | `native:centroids -> native:reprojectlayer -> native:rastersampling` | `script_0000945.py` | initAlgorithm |
| 121 | standard_v2 | 3 | pure_vector | `native:fixgeometries -> native:buffer -> native:intersection` | `script_0000633.py` |  |
| 122 | standard_v2 | 3 | pure_vector | `native:fixgeometries -> native:dissolve -> native:buffer -> native:extractbylocation` | `script_0000620.py` |  |
| 123 | standard_v2 | 3 | pure_vector | `native:fixgeometries -> native:savefeatures -> native:mergevectorlayers` | `script_0000076.py` | layer |
| 124 | standard_v2 | 3 | mixed | `native:mergevectorlayers -> gdal:polygonize` | `script_0000401.py` | checkLayerPoints |
| 125 | standard_v2 | 3 | pure_vector | `native:reprojectlayer -> native:buffer -> native:difference -> native:multiparttosingleparts` | `script_0000736.py` |  |
| 126 | standard_v2 | 3 | pure_vector | `native:reprojectlayer -> native:extractvertices -> native:multiparttosingleparts` | `script_0000960.py` | Author: Mario Königbauer (mkoenigb@gmx.de) initAlgorithm |
| 127 | standard_v2 | 3 | pure_vector | `native:reprojectlayer -> native:mergevectorlayers -> native:clip` | `script_0000828.py` | load road layer |
| 128 | standard_v2 | 5 | pure_vector | `native:fixgeometries -> native:dissolve` | `script_0000677.py` | init |
| 129 | standard_v2 | 2 | mixed | `qgis:rastercalculator -> qgis:rastercalculator -> qgis:rastercalculator -> gdal:polygonize -> native:dissolve -> native:clip` | `script_0000105.py` | Class to classify landuse from OSM init |
| 130 | workflow | 4 | pure_vector | `native:fixgeometries -> native:fixgeometries -> native:fixgeometries` | `script_0006739.py` |  |
| 131 | workflow_A | 1 | mixed | `gdal:warpreproject -> native:slope -> gdal:rastercalculator -> gdal:polygonize -> native:extractbyattribute -> native:clip` | `script_0000531.py` | initAlgorithm |
| 132 | standard_v2 | 3 | mixed | `native:reprojectlayer -> gdal:merge -> native:slope -> native:zonalstatisticsfb` | `script_0000016.py` | init |
| 133 | standard_v2 | 3 | mixed | `native:reprojectlayer -> native:buffer -> gdal:cliprasterbymasklayer -> gdal:warpreproject` | `script_0000270.py` | init |
| 134 | workflow | 1 | pure_vector | `native:reprojectlayer -> native:fixgeometries` | `script_0004586.py` |  |
| 135 | workflow | 2 | mixed | `gdal:rasterize -> gdal:merge` | `script_0007136.py` | initAlgorithm |
| 136 | workflow | 2 | pure_vector | `native:fixgeometries -> native:dissolve -> native:mergevectorlayers` | `script_0007119.py` | file ext search |
| 137 | standard_v2 | 4 | mixed | `gdal:cliprasterbymasklayer -> gdal:cliprasterbymasklayer -> native:reprojectlayer` | `script_0000764.py` | initAlgorithm |
| 138 | workflow_A | 1 | pure_vector | `gdal:rasterize -> gdal:rasterize -> gdal:rasterize -> gdal:rasterize` | `script_0006822.py` | Rasterize |
| 139 | standard_v2 | 3 | pure_vector | `native:dissolve -> native:multiparttosingleparts -> native:buffer -> native:dissolve -> native:dissolve -> native:reprojectlayer -> qgis:checkvalidity` | `script_0000655.py` | init |
| 140 | standard_v2 | 3 | pure_vector | `native:extractbyexpression -> native:extractbyexpression -> native:fixgeometries -> native:addautoincrementalfield -> native:deletecolumn -> native:renametablefield` | `script_0000023.py` | initAlgorithm |
| 141 | standard_v2 | 3 | pure_vector | `native:fixgeometries -> native:clip -> native:clip -> native:buffer -> native:extractbylocation -> native:countpointsinpolygon` | `script_0000616.py` |  |
| 142 | standard_v2 | 3 | pure_vector | `native:fixgeometries -> native:dissolve -> native:dissolve -> qgis:statisticsbycategories` | `script_0000159.py` |  |
| 143 | standard_v2 | 3 | pure_vector | `native:fixgeometries -> native:fixgeometries -> native:clip` | `script_0000821.py` | Class to download and clip WFS layers, used before and during WFStask init |
| 144 | standard_v2 | 3 | pure_vector | `native:fixgeometries -> native:fixgeometries -> native:intersection -> qgis:statisticsbycategories` | `script_0000158.py` |  |
| 145 | standard_v2 | 3 | pure_vector | `native:fixgeometries -> native:mergevectorlayers -> native:difference -> native:mergevectorlayers` | `script_0000083.py` | init |
| 146 | standard_v2 | 3 | pure_vector | `native:intersection -> native:intersection -> native:fixgeometries` | `script_0000879.py` | get project crs |
| 147 | standard_v2 | 3 | pure_vector | `native:multiparttosingleparts -> native:reprojectlayer -> qgis:advancedpythonfieldcalculator -> native:clip -> native:multiparttosingleparts -> native:extractbyexpression -> native:symmetricaldifference -> native:multiparttosingleparts` | `script_0000106.py` | init |
| 148 | standard_v2 | 3 | mixed | `native:reprojectlayer -> native:clip -> native:fixgeometries -> native:clip -> native:clip -> native:fixgeometries -> native:clip -> native:reprojectlayer -> gdal:cliprasterbymasklayer -> gdal:polygonize -> native:addfieldtoattributestable -> native:mergevectorlayers -> native:reprojectlayer -> native:reprojectlayer` | `script_0000802.py` | enable logging |
| 149 | standard_v2 | 3 | pure_vector | `native:reprojectlayer -> native:extractbyexpression -> native:buffer -> native:mergevectorlayers -> native:reprojectlayer` | `script_0000780.py` | main |
| 150 | standard_v2 | 3 | pure_vector | `native:reprojectlayer -> native:extractspecificvertices -> native:extractspecificvertices` | `script_0000749.py` | initAlgorithm |
| 151 | standard_v2 | 3 | pure_vector | `native:reprojectlayer -> native:savefeatures -> native:savefeatures -> native:savefeatures -> native:reprojectlayer -> native:savefeatures -> native:reprojectlayer -> native:savefeatures` | `script_0000598.py` | init |
| 152 | standard_v2 | 3 | mixed | `native:savefeatures -> gdal:translate -> native:reprojectlayer -> gdal:warpreproject -> gdal:rasterize -> native:fixgeometries -> native:union -> native:rastersampling -> native:rastersampling -> native:savefeatures` | `script_0000404.py` | init |
| 153 | standard_v2 | 3 | pure_vector | `qgis:checkvalidity -> native:fixgeometries -> qgis:checkvalidity -> native:fixgeometries` | `script_0000737.py` |  |
| 154 | standard_v2 | 3 | pure_raster | `gdal:cliprasterbymasklayer -> gdal:polygonize` | `script_0000097.py` | init |
| 155 | standard_v2 | 3 | mixed | `native:extractbyattribute -> native:reprojectlayer -> gdal:cliprasterbymasklayer -> gdal:warpreproject -> gdal:cliprasterbymasklayer -> gdal:warpreproject -> gdal:fillnodata` | `script_0000279.py` | climate extraction |
| 156 | standard_v2 | 3 | pure_vector | `native:mergevectorlayers -> native:reprojectlayer` | `script_0000716.py` | editAttribute |
| 157 | standard_v2 | 3 | pure_vector | `native:refactorfields -> native:fixgeometries` | `script_0000305.py` | create table |
| 158 | standard_v2 | 3 | pure_vector | `native:removenullgeometries -> native:reprojectlayer` | `script_0000119.py` | initAlgorithm |
| 159 | standard_v2 | 3 | pure_vector | `native:reprojectlayer -> native:buffer` | `script_0000587.py` | initAlgorithm |
| 160 | standard_v2 | 3 | pure_vector | `native:reprojectlayer -> native:centroids` | `script_0000961.py` | Author: Mario Königbauer (mkoenigb@gmx.de) initAlgorithm |
| 161 | standard_v2 | 3 | mixed | `native:reprojectlayer -> native:clip -> native:reprojectlayer -> gdal:cliprasterbymasklayer` | `script_0000877.py` |  |
| 162 | standard_v2 | 3 | mixed | `native:reprojectlayer -> native:reprojectlayer -> native:reprojectlayer -> gdal:warpreproject -> native:reprojectlayer` | `script_0000513.py` | init |
| 163 | standard_v2 | 3 | mixed | `native:reprojectlayer -> native:reprojectlayer -> qgis:minimumboundinggeometry -> native:selectbylocation -> gdal:translate -> gdal:translate -> gdal:assignprojection` | `script_0000943.py` | mainFunction |
| 164 | workflow | 2 | pure_vector | `native:dissolve -> native:fixgeometries -> native:dissolve -> native:promotetomulti` | `script_0007126.py` | init |
| 165 | standard_v2 | 2 | pure_vector | `native:mergevectorlayers -> native:retainfields -> native:reprojectlayer -> native:mergevectorlayers -> native:mergevectorlayers` | `script_0000938.py` | init |
| 166 | workflow | 1 | pure_vector | `native:clip -> native:fixgeometries -> native:savefeatures` | `script_0007095.py` | init |
| 167 | standard_v2 | 1 | pure_vector | `native:extractbylocation -> native:reprojectlayer -> native:refactorfields` | `script_0000507.py` |  |
| 168 | workflow_A | 1 | pure_vector | `native:reprojectlayer -> native:difference -> native:extractbyexpression -> native:intersection` | `script_0007070.py` | select layer |
| 169 | workflow_A | 1 | pure_vector | `native:reprojectlayer -> native:dissolve -> native:multiparttosingleparts` | `script_0007068.py` |  |
| 170 | standard_v2 | 2 | pure_vector | `native:selectbylocation -> native:reprojectlayer` | `script_0000996.py` | car_PrepareCarKml |
| 171 | standard_v2 | 6 | mixed | `native:buffer -> native:difference -> native:reclassifybytable -> gdal:polygonize -> native:extractbyexpression -> native:reclassifybytable -> gdal:polygonize -> native:extractbyexpression -> native:buffer -> native:difference -> native:savefeatures` | `script_0000423.py` | ================================================================================ init |
| 172 | workflow_A | 1 | pure_vector | `gdal:rasterize -> gdal:rasterize` | `script_0000022.py` | initAlgorithm |
| 173 | standard_v2 | 2 | mixed | `gdal:buildvirtualraster -> native:reprojectlayer` | `script_0001003.py` | init |
| 174 | standard_v2 | 1 | pure_vector | `native:reprojectlayer -> native:reprojectlayer -> native:assignprojection` | `script_0000982.py` | initAlgorithm |
| 175 | workflow | 1 | pure_vector | `native:reprojectlayer -> native:reprojectlayer -> native:reprojectlayer` | `script_0007951.py` | initAlgorithm |
| 176 | standard_v2 | 1 | pure_vector | `native:savefeatures -> native:reprojectlayer -> native:savefeatures` | `script_0000910.py` | run_pipeline_debug_v3.py |
| 177 | standard_v2 | 1 | pure_vector | `native:reprojectlayer -> native:joinattributesbylocation` | `script_0000979.py` |  |
| 178 | standard_v2 | 1 | mixed | `native:reprojectlayer -> native:zonalhistogram -> native:zonalhistogram -> native:zonalhistogram` | `script_0000983.py` |  |
| 179 | standard_v2 | 1 | mixed | `native:reclassifybytable -> native:reprojectlayer` | `script_0000997.py` | progress callback |

## Admission Boundary

- Use `stable101_source_review_50_v1.csv` for manual adjudication.
- Check workflow boundary, operator identity/order, source snippet validity, dependency plausibility, and task-text usability.
- Keep `training_admission=not_granted` until human review and faithful task-description generation pass.
