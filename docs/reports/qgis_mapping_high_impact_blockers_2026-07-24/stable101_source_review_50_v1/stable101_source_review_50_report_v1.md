# QGIS stable101 Source Review Pack

This report joins the stable101 50-row chain-level candidate batch back to source files. It is for human review only and does not grant training admission.

## Summary

- Review rows: 50
- Joined sources: 50
- Snippets containing all ordered operators: 50
- Source roots: `{"standard_v2": 35, "workflow": 7, "workflow_A": 8}`
- Modalities: `{"mixed": 20, "pure_raster": 3, "pure_vector": 27}`
- Text quality: `{"usable_seed_text": 47, "weak_short_or_empty": 3}`
- Taxonomy admission: `granted_for_four_stable101_mappings`
- Training admission: `not_granted`

## Review Rows

| # | source | chain freq | modality | operators | source file | task seed |
|---:|---|---:|---|---|---|---|
| 1 | standard_v2 | 3 | mixed | `gdal:rasterize -> native:fixgeometries -> native:zonalstatisticsfb -> native:zonalhistogram` | `script_0000343.py` | Model exported as python. initAlgorithm |
| 2 | standard_v2 | 6 | mixed | `gdal:assignprojection -> native:assignprojection -> native:extractbyextent -> native:fixgeometries -> native:reprojectlayer -> gdal:buildvirtualraster` | `script_0000061.py` | 📦 Utilities module. assign crs to raster layer |
| 3 | standard_v2 | 2 | mixed | `native:reprojectlayer -> gdal:rasterize -> gdal:cliprasterbyextent` | `script_0001000.py` | generate_tiles.py load config |
| 4 | standard_v2 | 3 | pure_vector | `native:fixgeometries -> native:reprojectlayer -> native:difference -> native:mergevectorlayers` | `script_0000895.py` | Remove acentos e converte para minúsculas init |
| 5 | standard_v2 | 4 | pure_vector | `native:union -> native:multiparttosingleparts -> native:fixgeometries -> native:multiparttosingleparts -> native:reprojectlayer` | `script_0000973.py` | Decorator to catch sql exceptions. sql error handler |
| 6 | standard_v2 | 3 | pure_vector | `native:fixgeometries -> native:extractbyattribute -> native:reprojectlayer -> native:refactorfields -> native:refactorfields -> native:savefeatures` | `script_0000872.py` | Model exported as python (patched). initAlgorithm |
| 7 | standard_v2 | 3 | pure_vector | `native:fixgeometries -> native:reprojectlayer -> native:intersection -> native:difference -> native:intersection -> native:difference -> native:difference -> native:mergevectorlayers` | `script_0000894.py` | Remove acentos e converte para minúsculas init |
| 8 | standard_v2 | 1 | pure_vector | `native:fixgeometries -> native:reprojectlayer -> native:extractbyextent -> native:fieldcalculator` | `script_0000977.py` | Clip layer by extent clip in projectcrs |
| 9 | workflow_A | 1 | pure_vector | `native:reprojectlayer -> native:fixgeometries -> native:clip` | `script_0007153.py` | USDA Soil Data Retrieval - Final Production Version (v2.0) init |
| 10 | workflow_A | 1 | pure_vector | `native:dissolve -> native:reprojectlayer -> native:fixgeometries -> native:reprojectlayer -> native:intersection` | `script_0007151.py` | Multi-Basin CN Generation Runner Script (v2.0) init |
| 11 | workflow_A | 1 | pure_vector | `native:reprojectlayer -> native:fixgeometries -> native:clip -> native:reprojectlayer -> native:fixgeometries` | `script_0007152.py` | Simple USDA Soil Retrieval - Matches CN Generator pattern exactly. get soil data |
| 12 | standard_v2 | 6 | pure_vector | `native:reprojectlayer -> native:reprojectlayer -> native:fixgeometries -> native:fixgeometries -> native:fixgeometries -> native:intersection -> native:intersection -> native:fieldcalculator -> native:fieldcalculator -> native:fieldcalculator -> native:fieldcalculator -> native:fieldcalculator -> native:fieldcalculator -> native:fieldcalculator` | `script_0000540.py` | WHEN "class_name" = 'Built-up' THEN 'Concrete' initAlgorithm |
| 13 | standard_v2 | 66 | mixed | `native:reclassifybytable -> native:reclassifybytable -> native:reclassifybytable -> gdal:polygonize -> native:zonalstatisticsfb` | `script_0000231.py` | Module 7: Market Classification & Zoning |
| 14 | standard_v2 | 3 | mixed | `native:clip -> gdal:polygonize -> gdal:cliprasterbyextent` | `script_0000820.py` | Clip a QgsVector layer by different QgsVector layer simple clip |
| 15 | standard_v2 | 3 | mixed | `qgis:rastercalculator -> gdal:polygonize -> native:buffer -> gdal:cliprasterbymasklayer` | `script_0000313.py` | Model exported as python. initAlgorithm |
| 16 | workflow | 2 | mixed | `gdal:polygonize -> native:extractbyattribute -> gdal:cliprasterbymasklayer` | `script_0007653.py` | Black Frame Remover: main.py v1.1.0 init |
| 17 | workflow | 2 | mixed | `qgis:rastercalculator -> gdal:polygonize -> native:dissolve` | `script_0007273.py` | 1. Находит в проекте растр по имени `raster_name`. create single polygon per color |
| 18 | standard_v2 | 3 | pure_raster | `gdal:cliprasterbymasklayer -> gdal:warpreproject -> gdal:polygonize -> gdal:hillshade` | `script_0000434.py` | Bilinear interpolation of raster value at (x, y). cleanup file |
| 19 | workflow_A | 3 | pure_raster | `gdal:slope -> gdal:hillshade -> qgis:rastercalculator -> gdal:polygonize` | `script_0007230.py` | Initialize the Debris Flow Paths Detector init |
| 20 | workflow_A | 1 | mixed | `gdal:rastercalculator -> gdal:rastercalculator -> gdal:polygonize -> native:fieldcalculator` | `script_0007163.py` | Fonction pour lancer le calcul NDVI depuis main.py initAlgorithm |
| 21 | workflow_A | 1 | mixed | `gdal:translate -> gdal:fillnodata -> gdal:translate -> gdal:sieve -> gdal:polygonize -> native:extractbyattribute` | `script_0007175.py` | Writes a raster where pixels in [min_val, max_val] become 1, else 0. create range mask |
| 22 | standard_v2 | 3 | pure_raster | `native:reclassifybytable -> gdal:polygonize` | `script_0000888.py` | Aplica a simbologia categorizada no campo 'DN'. definir simbologia vetor |
| 23 | standard_v2 | 6 | mixed | `gdal:warpreproject -> native:fillnodata -> gdal:rasterize -> gdal:cliprasterbymasklayer` | `script_0000067.py` | 📦 Workflow Base module. init |
| 24 | standard_v2 | 6 | mixed | `native:buffer -> native:clip -> gdal:rasterize -> gdal:warpreproject -> gdal:rastercalculator` | `script_0000058.py` | 📦 Opportunities Mask Processor module. init |
| 25 | standard_v2 | 3 | mixed | `native:buffer -> native:union -> native:promotetomulti -> native:polygonfromlayerextent -> gdal:clipvectorbypolygon -> gdal:rasterize -> gdal:warpreproject` | `script_0000375.py` | build water rasterized |
| 26 | standard_v2 | 3 | mixed | `native:extractbylocation -> gdal:rasterize -> gdal:cliprasterbymasklayer` | `script_0000315.py` | Model exported as python. initAlgorithm |
| 27 | workflow | 2 | mixed | `gdal:rasterize -> gdal:translate` | `script_0008220.py` | Create binary masks from selected vector layers, based on a single chosen DTM tile extent, |
| 28 | standard_v2 | 12 | pure_vector | `native:dissolve -> native:fieldcalculator -> native:intersection -> native:dissolve -> gdal:rasterize -> native:zonalstatisticsfb -> native:zonalstatisticsfb` | `script_0000080.py` | init |
| 29 | standard_v2 | 3 | mixed | `gdal:rasterize -> gdal:warpreproject -> gdal:rastercalculator -> gdal:cliprasterbymasklayer` | `script_0001027.py` | init |
| 30 | standard_v2 | 3 | mixed | `native:buffer -> native:zonalstatisticsfb -> gdal:rasterize -> gdal:merge -> saga:fillsinksxxlwangliu -> gdal:warpreproject -> native:hillshade` | `script_0000332.py` |  |
| 31 | standard_v2 | 12 | pure_vector | `native:fixgeometries -> native:clip` | `script_0000034.py` | Fix invalid geometries in input layer and return temporary layer with valid geoms fix geom |
| 32 | workflow | 14 | pure_vector | `native:fixgeometries -> native:zonalstatisticsfb` | `script_0005583.py` | Calculate the height of bounding box in meters calculate centroid |
| 33 | standard_v2 | 3 | pure_vector | `native:fixgeometries -> native:buffer -> native:difference` | `script_0000553.py` | The script defines functions that can be used in the QGIS python console to speed up the g |
| 34 | standard_v2 | 3 | pure_vector | `native:fixgeometries -> native:multiparttosingleparts -> native:clip -> native:extractbyexpression` | `script_0000817.py` | Fixes the geometries of a shapefile and saves the fixed version. fix geometries |
| 35 | workflow | 2 | pure_vector | `native:fixgeometries -> native:dissolve -> native:polygonize` | `script_0007127.py` | SolarPanelGenerator Plugin Coverage Logic init |
| 36 | standard_v2 | 3 | pure_vector | `native:fixgeometries -> native:fixgeometries -> native:fixgeometries -> native:clip -> native:clip` | `script_0000349.py` | Model exported as python. initAlgorithm |
| 37 | standard_v2 | 3 | pure_vector | `native:fixgeometries -> native:fixgeometries -> native:fixgeometries -> native:mergevectorlayers -> native:dissolve` | `script_0000363.py` | This makes parameters for wfs-request of specific area getBboxWmsFormat |
| 38 | workflow | 2 | pure_vector | `native:fixgeometries -> native:fixgeometries -> native:fixgeometries -> native:fixgeometries -> native:fixgeometries` | `script_0006060.py` | Modulo: AyudasGEO RegisterFunction |
| 39 | workflow_A | 1 | pure_vector | `native:extractbylocation -> native:fixgeometries -> native:intersection` | `script_0007279.py` | GeoLote - Plugin QGIS sanitize field name |
| 40 | standard_v2 | 3 | pure_vector | `native:difference -> native:dissolve -> native:dissolve -> native:mergevectorlayers -> native:fixgeometries -> native:difference -> native:removenullgeometries -> native:fixgeometries -> native:fixgeometries -> native:union -> native:fixgeometries -> native:mergevectorlayers` | `script_0000819.py` | Apply a simple difference operation to the input layers. apply simple difference |
| 41 | standard_v2 | 7 | pure_vector | `native:reprojectlayer -> native:buffer -> native:clip` | `script_0000048.py` | PyQGIS Code Snippets |
| 42 | standard_v2 | 7 | pure_vector | `native:reprojectlayer -> native:intersection` | `script_0000899.py` | CN Calculator Tool for Hydro Suite init |
| 43 | workflow | 21 | pure_vector | `native:reprojectlayer -> native:reprojectlayer` | `script_0001443.py` | This algorithm generates a full sidewalk network based on OSM data within a specified boun |
| 44 | workflow_A | 4 | mixed | `gdal:warpreproject -> native:reprojectlayer -> native:rastersampling` | `script_0007138.py` | process raster sample points |
| 45 | standard_v2 | 6 | pure_vector | `native:reprojectlayer -> native:extractbyexpression` | `script_0000269.py` | reproject layer if needed |
| 46 | standard_v2 | 3 | pure_vector | `native:extractbyexpression -> native:intersection -> native:dissolve -> native:retainfields -> native:reprojectlayer -> native:fieldcalculator -> native:savefeatures` | `script_0000902.py` | Script using pyqgis |
| 47 | standard_v2 | 7 | mixed | `native:reprojectlayer -> gdal:warpreproject` | `script_0000958.py` | Simple feedback object that prints all messages to console reportError |
| 48 | standard_v2 | 3 | pure_vector | `native:reprojectlayer -> native:joinattributesbylocation -> native:multiintersection` | `script_0000754.py` | Quite specific to the French case. Add a boolean attribute, for every building of a vector |
| 49 | standard_v2 | 3 | pure_vector | `native:reprojectlayer -> native:renametablefield -> native:retainfields` | `script_0000592.py` | parse time interval |
| 50 | standard_v2 | 6 | mixed | `native:reprojectlayer -> gdal:cliprasterbymasklayer` | `script_0000956.py` | Create a new print layout and remove any previous layout with the same name. create layout |

## Admission Boundary

- Use `stable101_source_review_50_v1.csv` for manual adjudication.
- Check workflow boundary, operator identity/order, source snippet validity, dependency plausibility, and task-text usability.
- Keep `training_admission=not_granted` until human review and faithful task-description generation pass.
