# QGIS stable101 Source Review Pack

This report joins the stable101 50-row chain-level candidate batch back to source files. It is for human review only and does not grant training admission.

## Summary

- Review rows: 50
- Joined sources: 50
- Snippets containing all ordered operators: 50
- Source roots: `{"standard_v2": 44, "workflow": 1, "workflow_A": 5}`
- Modalities: `{"mixed": 20, "pure_raster": 4, "pure_vector": 26}`
- Text quality: `{"usable_seed_text": 32, "weak_short_or_empty": 17, "weak_symbol_or_method": 1}`
- Taxonomy admission: `granted_for_four_stable101_mappings`
- Training admission: `not_granted`

## Review Rows

| # | source | chain freq | modality | operators | source file | task seed |
|---:|---|---:|---|---|---|---|
| 1 | standard_v2 | 3 | mixed | `gdal:warpreproject -> native:reclassifybytable -> gdal:polygonize -> native:fixgeometries -> native:zonalstatisticsfb -> native:fieldcalculator -> native:extractbyexpression -> native:fieldcalculator -> native:centroids` | `script_0000493.py` | Automated Keyline Keypoint Detection Algorithm |
| 2 | standard_v2 | 3 | mixed | `gdal:warpreproject -> saga:fillsinksxxlwangliu -> native:zonalstatistics -> native:zonalstatistics -> gdal:cliprasterbyextent -> native:fixgeometries -> native:buffer -> native:clip -> native:clip -> gdal:polygonize -> native:zonalstatistics -> native:zonalstatistics` | `script_0000498.py` | HydroAnalysis.py - Module d'analyse hydrologique pour SigLogix (QGIS) init |
| 3 | standard_v2 | 3 | mixed | `native:extractbyextent -> native:fixgeometries -> native:clip -> native:reprojectlayer -> gdal:rasterize -> gdal:warpreproject -> native:savefeatures -> native:reprojectlayer -> native:fixgeometries -> native:clip -> native:multiparttosingleparts -> native:reprojectlayer` | `script_0000833.py` | Dialog for filtering vector layer features by attribute values. init |
| 4 | standard_v2 | 1 | pure_vector | `native:renametablefield -> native:renametablefield -> native:assignprojection -> native:fixgeometries -> native:reprojectlayer -> native:promotetomulti -> native:reprojectlayer -> native:joinattributesbylocation -> native:fieldcalculator` | `script_0000909.py` | ensure plugins path |
| 5 | standard_v2 | 5 | pure_vector | `native:reprojectlayer -> gdal:rasterize` | `script_0000751.py` | get config |
| 6 | standard_v2 | 3 | mixed | `gdal:polygonize -> native:buffer -> gdal:rasterize` | `script_0000622.py` |  |
| 7 | standard_v2 | 3 | mixed | `gdal:rgbtopct -> gdal:polygonize -> native:extractbyattribute -> native:fixgeometries` | `script_0000695.py` |  |
| 8 | standard_v2 | 4 | mixed | `gdal:rasterize -> gdal:polygonize` | `script_0000359.txt` | getBboxWmsFormat |
| 9 | standard_v2 | 3 | pure_vector | `native:difference -> native:buffer -> native:clip -> native:fixgeometries -> native:mergevectorlayers -> native:reprojectlayer` | `script_0000783.py` | config |
| 10 | standard_v2 | 3 | pure_vector | `native:fixgeometries -> native:dissolve -> native:reprojectlayer` | `script_0000972.py` | init |
| 11 | workflow_A | 1 | mixed | `gdal:polygonize -> native:zonalstatisticsfb` | `script_0007007.py` | Stage 4: Zonal Statistics vectorize mask |
| 12 | standard_v2 | 2 | pure_raster | `gdal:rastercalculator -> gdal:polygonize` | `script_0000882.py` | This shared script processes a raster dataset (NDVI) by performing the following steps: |
| 13 | workflow | 2 | pure_raster | `gdal:polygonize -> gdal:polygonize` | `script_0005627.py` | transfrom input buffer zone raster to vector raster2vector |
| 14 | standard_v2 | 3 | mixed | `gdal:polygonize -> gdal:polygonize -> native:clip -> gdal:polygonize -> native:buffer -> native:clip -> native:buffer -> native:buffer -> native:buffer -> native:dissolve -> native:clip` | `script_0000469.py` | to avoid havign to use "stroke to path" which keeps crashing in inkscape buffer params |
| 15 | standard_v2 | 3 | mixed | `gdal:polygonize -> native:extractbyexpression -> native:dissolve -> gdal:polygonize -> native:extractbyexpression -> native:fieldcalculator -> native:fieldcalculator -> native:zonalstatisticsfb -> native:zonalstatisticsfb -> native:zonalstatisticsfb -> native:fieldcalculator` | `script_0000342.py` | <h3>Analisi del Catchment</h3> name |
| 16 | standard_v2 | 8 | mixed | `gdal:polygonize -> native:intersection` | `script_0000448.py` | initAlgorithm |
| 17 | standard_v2 | 9 | pure_raster | `saga:upslopearea -> gdal:polygonize` | `script_0000001.py` | initAlgorithm |
| 18 | standard_v2 | 3 | pure_raster | `gdal:cliprasterbymasklayer -> gdal:polygonize` | `script_0000097.py` | init |
| 19 | standard_v2 | 3 | mixed | `native:translategeometry -> gdal:rasterize -> gdal:cliprasterbymasklayer` | `script_0000926.py` | init |
| 20 | standard_v2 | 3 | pure_vector | `gdal:rasterize -> native:fieldcalculator -> gdal:rasterize` | `script_0000275.py` | initAlgorithm |
| 21 | standard_v2 | 3 | mixed | `gdal:rastercalculator -> gdal:rasterize -> gdal:rasterize -> gdal:rastercalculator` | `script_0000022.py` | initAlgorithm |
| 22 | standard_v2 | 3 | mixed | `gdal:warpreproject -> gdal:rasterize -> gdal:assignprojection -> gdal:cliprasterbymasklayer -> gdal:warpreproject -> gdal:warpreproject` | `script_0000029.py` | addAdvancedParameter |
| 23 | standard_v2 | 6 | pure_vector | `native:fixgeometries -> native:retainfields -> native:zonalstatisticsfb` | `script_0000060.py` | 📦 Subnational Aggregation Processor module. init |
| 24 | standard_v2 | 3 | pure_vector | `native:extractbyexpression -> native:intersection -> native:intersection -> native:dissolve -> native:dissolve -> native:refactorfields -> native:fixgeometries -> native:refactorfields -> native:fixgeometries -> native:promotetomulti -> native:promotetomulti -> native:dissolve -> native:dissolve -> native:refactorfields -> native:refactorfields` | `script_0000844.py` | Model exported as python. initAlgorithm |
| 25 | standard_v2 | 3 | pure_vector | `native:refactorfields -> native:refactorfields -> native:extractbyattribute -> native:extractbyattribute -> native:fixgeometries -> native:fixgeometries -> native:mergevectorlayers -> native:refactorfields -> native:dissolve -> native:refactorfields` | `script_0000847.py` | Model exported as python. initAlgorithm |
| 26 | standard_v2 | 9 | mixed | `gdal:translate -> native:fixgeometries` | `script_0000927.py` | qgisName |
| 27 | standard_v2 | 3 | pure_vector | `native:fixgeometries -> native:buffer -> native:intersection` | `script_0000633.py` |  |
| 28 | standard_v2 | 3 | pure_vector | `native:fixgeometries -> native:dissolve -> native:buffer -> native:extractbylocation` | `script_0000620.py` |  |
| 29 | standard_v2 | 3 | pure_vector | `native:fixgeometries -> native:savefeatures -> native:mergevectorlayers` | `script_0000076.py` | layer |
| 30 | standard_v2 | 5 | pure_vector | `native:fixgeometries -> native:dissolve` | `script_0000677.py` | init |
| 31 | standard_v2 | 6 | pure_vector | `native:mergevectorlayers -> native:dissolve -> native:difference -> native:mergevectorlayers -> native:reprojectlayer` | `script_0000065.py` | 📦 Multi Buffer Distances Ors Workflow module. init |
| 32 | standard_v2 | 6 | pure_vector | `native:reprojectlayer -> native:clip` | `script_0000063.py` | 📦 Osm Data Downloader Base module. init |
| 33 | standard_v2 | 3 | pure_vector | `native:reprojectlayer -> native:clip -> native:buffer -> native:dissolve -> native:difference -> native:mergevectorlayers` | `script_0000064.py` | Multi-buffer distances workflow using native QGIS network analysis. init |
| 34 | standard_v2 | 3 | mixed | `gdal:warpreproject -> native:reprojectlayer -> gdal:cliprasterbymasklayer` | `script_0001002.py` | some utils func with qgis sauce reproject raster |
| 35 | standard_v2 | 3 | mixed | `native:reprojectlayer -> gdal:cliprasterbymasklayer -> gdal:cliprasterbyextent -> gdal:translate -> gdal:warpreproject -> gdal:rastercalculator` | `script_0000442.py` | Calculates the Curve Number using global datasets from ESA WorldCover and ORNL HYSOG. init |
| 36 | standard_v2 | 2 | pure_vector | `native:reprojectlayer -> native:clip -> native:buffer -> native:joinattributesbylocation -> native:savefeatures` | `script_0000670.py` | Executor Agent — PyQGIS 脚本注入执行与闭环自愈验证. verify hash |
| 37 | workflow_A | 4 | pure_vector | `native:reprojectlayer -> native:zonalstatisticsfb` | `script_0007087.py` | Area Comparison Analysis Algorithm |
| 38 | standard_v2 | 3 | pure_vector | `native:reprojectlayer -> native:clip -> native:reprojectlayer` | `script_0000827.py` | Download features from an ArcGIS Feature/MapServer layer using paged requests, return Feat |
| 39 | standard_v2 | 3 | pure_vector | `native:reprojectlayer -> native:rastersampling -> native:zonalstatisticsfb -> native:reprojectlayer -> native:savefeatures` | `script_0000918.py` | v0.2 2024-09-03 rainfall factor |
| 40 | standard_v2 | 3 | pure_vector | `native:reprojectlayer -> native:reprojectlayer -> native:buffer -> native:clip -> native:fieldcalculator` | `script_0000668.py` | Vector Geoprocessing — PyQGIS Processing Script |
| 41 | standard_v2 | 3 | pure_vector | `native:reprojectlayer -> native:reprojectlayer -> native:reprojectlayer -> native:buffer -> qgis:joinbylocationsummary -> qgis:joinbylocationsummary -> native:fieldcalculator -> native:reprojectlayer` | `script_0000718.py` | Sample 02: Right-of-Way Vegetation + Flood Risk load layer |
| 42 | standard_v2 | 3 | pure_vector | `native:reprojectlayer -> native:reprojectlayer -> native:savefeatures -> native:clip` | `script_0000871.py` | Return all polygon vector layers currently loaded in the project. polygon layers |
| 43 | standard_v2 | 3 | pure_vector | `native:reprojectlayer -> native:union -> native:union -> native:reprojectlayer` | `script_0000831.py` | select nombre_esquema,nombre_capa from acervo_descripcion_1.mapa_master_vw where id in (se |
| 44 | workflow_A | 2 | mixed | `gdal:warpreproject -> gdal:rastercalculator -> native:reprojectlayer -> native:zonalstatisticsfb` | `script_0007089.py` | DEM → Flooded extent + AOI stats (AR6 CSV; matches your Data schema) |
| 45 | standard_v2 | 2 | mixed | `native:reprojectlayer -> gdal:cliprasterbyextent -> gdal:rastercalculator` | `script_0000038.py` | Manning's Roughness Generator - A QGIS Plugin name |
| 46 | workflow_A | 2 | mixed | `native:reprojectlayer -> native:buffer -> native:clip -> native:intersection -> native:dissolve -> qgis:rastercalculator` | `script_0007210.py` | Code Generator Module init |
| 47 | standard_v2 | 3 | mixed | `gdal:cliprasterbyextent -> gdal:warpreproject -> native:reprojectlayer -> gdal:warpreproject` | `script_0000999.py` | get shapefile as json pyqgis |
| 48 | standard_v2 | 3 | pure_vector | `native:reprojectlayer -> native:retainfields` | `script_0000593.py` | parse time interval |
| 49 | standard_v2 | 2 | pure_vector | `native:reprojectlayer -> native:buffer -> native:reprojectlayer` | `script_0000730.py` | PyQGIS pipeline — builds a QGIS project with styled layers, buffers, and per-school map ex |
| 50 | workflow_A | 1 | pure_vector | `native:reprojectlayer -> native:extractbyexpression -> native:mergevectorlayers` | `script_0006964.py` | This class is responsible for loading, optionally filtering, and merging vector layers fro |

## Admission Boundary

- Use `stable101_source_review_50_v1.csv` for manual adjudication.
- Check workflow boundary, operator identity/order, source snippet validity, dependency plausibility, and task-text usability.
- Keep `training_admission=not_granted` until human review and faithful task-description generation pass.
