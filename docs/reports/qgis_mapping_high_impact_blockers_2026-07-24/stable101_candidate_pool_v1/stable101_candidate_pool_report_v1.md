# QGIS stable101 Newly Complete Candidate Pool

This report re-evaluates the multi-step Processing candidate pool after the four stable101 mappings were adjudicated. It is chain-level triage only: no `outputs_v2` production mapping, training export, LLM description generation, or model training is performed.

## Summary

- Newly complete records: 640
- Unique record hashes: 542
- Unique ordered chains: 179
- Recommended next-review batch: 50 unique chain representatives
- Source snippet join required before full manual review CSV: True
- Taxonomy admission: `granted_for_four_stable101_mappings`
- Training admission: `not_granted`

## Chain Pool Shape

| dimension | counts |
|---|---|
| record modality | `{"mixed": 278, "pure_raster": 25, "pure_vector": 337}` |
| unique-chain modality | `{"mixed": 71, "pure_raster": 7, "pure_vector": 101}` |
| next-batch modality | `{"mixed": 20, "pure_raster": 3, "pure_vector": 27}` |
| record task-text quality | `{"usable_seed_text": 330, "weak_code_fragment": 1, "weak_code_import": 1, "weak_metadata": 18, "weak_short_or_empty": 268, "weak_symbol_or_method": 9, "weak_too_few_words": 13}` |
| unique-chain task-text quality | `{"usable_seed_text": 89, "weak_code_fragment": 1, "weak_metadata": 3, "weak_short_or_empty": 78, "weak_symbol_or_method": 4, "weak_too_few_words": 4}` |
| next-batch task-text quality | `{"usable_seed_text": 47, "weak_short_or_empty": 3}` |
| next batch strata | `{"multi_stable101_operator_combo": 12, "single_fixgeometries_representative": 10, "single_polygonize_representative": 10, "single_rasterize_representative": 8, "single_reprojectlayer_representative": 10}` |

## Recommended Next Review Batch

| # | stratum | chain frequency | modality | stable101 ops | ordered QGIS chain | task seed |
|---:|---|---:|---|---|---|---|
| 1 | multi_stable101_operator_combo | 3 | mixed | `gdal:rasterize, native:fixgeometries` | `gdal:rasterize -> native:fixgeometries -> native:zonalstatisticsfb -> native:zonalhistogram` | Model exported as python. initAlgorithm |
| 2 | multi_stable101_operator_combo | 6 | mixed | `native:fixgeometries, native:reprojectlayer` | `gdal:assignprojection -> native:assignprojection -> native:extractbyextent -> native:fixgeometries -> native:reprojectlayer -> gdal:buildvirtualraster` | 📦 Utilities module. assign crs to raster layer |
| 3 | multi_stable101_operator_combo | 2 | mixed | `gdal:rasterize, native:reprojectlayer` | `native:reprojectlayer -> gdal:rasterize -> gdal:cliprasterbyextent` | generate_tiles.py load config |
| 4 | multi_stable101_operator_combo | 3 | pure_vector | `native:fixgeometries, native:reprojectlayer` | `native:fixgeometries -> native:reprojectlayer -> native:difference -> native:mergevectorlayers` | Remove acentos e converte para minúsculas init |
| 5 | multi_stable101_operator_combo | 4 | pure_vector | `native:fixgeometries, native:reprojectlayer` | `native:union -> native:multiparttosingleparts -> native:fixgeometries -> native:multiparttosingleparts -> native:reprojectlayer` | Decorator to catch sql exceptions. sql error handler |
| 6 | multi_stable101_operator_combo | 3 | pure_vector | `native:fixgeometries, native:reprojectlayer` | `native:fixgeometries -> native:extractbyattribute -> native:reprojectlayer -> native:refactorfields -> native:refactorfields -> native:savefeatures` | Model exported as python (patched). initAlgorithm |
| 7 | multi_stable101_operator_combo | 3 | pure_vector | `native:fixgeometries, native:reprojectlayer` | `native:fixgeometries -> native:reprojectlayer -> native:intersection -> native:difference -> native:intersection -> native:difference -> native:difference -> native:mergevectorlayers` | Remove acentos e converte para minúsculas init |
| 8 | multi_stable101_operator_combo | 1 | pure_vector | `native:fixgeometries, native:reprojectlayer` | `native:fixgeometries -> native:reprojectlayer -> native:extractbyextent -> native:fieldcalculator` | Clip layer by extent clip in projectcrs |
| 9 | multi_stable101_operator_combo | 1 | pure_vector | `native:fixgeometries, native:reprojectlayer` | `native:reprojectlayer -> native:fixgeometries -> native:clip` | USDA Soil Data Retrieval - Final Production Version (v2.0) init |
| 10 | multi_stable101_operator_combo | 1 | pure_vector | `native:fixgeometries, native:reprojectlayer` | `native:dissolve -> native:reprojectlayer -> native:fixgeometries -> native:reprojectlayer -> native:intersection` | Multi-Basin CN Generation Runner Script (v2.0) init |
| 11 | multi_stable101_operator_combo | 1 | pure_vector | `native:fixgeometries, native:reprojectlayer` | `native:reprojectlayer -> native:fixgeometries -> native:clip -> native:reprojectlayer -> native:fixgeometries` | Simple USDA Soil Retrieval - Matches CN Generator pattern exactly. get soil data |
| 12 | multi_stable101_operator_combo | 6 | pure_vector | `native:fixgeometries, native:reprojectlayer` | `native:reprojectlayer -> native:reprojectlayer -> native:fixgeometries -> native:fixgeometries -> native:fixgeometries -> native:intersection -> native:intersection -> native:fieldcalculator -> native:fieldcalculator -> native:fieldcalculator -> native:fieldcalculator -> native:fieldcalculator -> native:fieldcalculator -> native:fieldcalculator` | WHEN "class_name" = 'Built-up' THEN 'Concrete' initAlgorithm |
| 13 | single_polygonize_representative | 66 | mixed | `gdal:polygonize` | `native:reclassifybytable -> native:reclassifybytable -> native:reclassifybytable -> gdal:polygonize -> native:zonalstatisticsfb` | Module 7: Market Classification & Zoning |
| 14 | single_polygonize_representative | 3 | mixed | `gdal:polygonize` | `native:clip -> gdal:polygonize -> gdal:cliprasterbyextent` | Clip a QgsVector layer by different QgsVector layer simple clip |
| 15 | single_polygonize_representative | 3 | mixed | `gdal:polygonize` | `qgis:rastercalculator -> gdal:polygonize -> native:buffer -> gdal:cliprasterbymasklayer` | Model exported as python. initAlgorithm |
| 16 | single_polygonize_representative | 2 | mixed | `gdal:polygonize` | `gdal:polygonize -> native:extractbyattribute -> gdal:cliprasterbymasklayer` | Black Frame Remover: main.py v1.1.0 init |
| 17 | single_polygonize_representative | 2 | mixed | `gdal:polygonize` | `qgis:rastercalculator -> gdal:polygonize -> native:dissolve` | 1. Находит в проекте растр по имени `raster_name`. create single polygon per color |
| 18 | single_polygonize_representative | 3 | pure_raster | `gdal:polygonize` | `gdal:cliprasterbymasklayer -> gdal:warpreproject -> gdal:polygonize -> gdal:hillshade` | Bilinear interpolation of raster value at (x, y). cleanup file |
| 19 | single_polygonize_representative | 3 | pure_raster | `gdal:polygonize` | `gdal:slope -> gdal:hillshade -> qgis:rastercalculator -> gdal:polygonize` | Initialize the Debris Flow Paths Detector init |
| 20 | single_polygonize_representative | 1 | mixed | `gdal:polygonize` | `gdal:rastercalculator -> gdal:rastercalculator -> gdal:polygonize -> native:fieldcalculator` | Fonction pour lancer le calcul NDVI depuis main.py initAlgorithm |
| 21 | single_polygonize_representative | 1 | mixed | `gdal:polygonize` | `gdal:translate -> gdal:fillnodata -> gdal:translate -> gdal:sieve -> gdal:polygonize -> native:extractbyattribute` | Writes a raster where pixels in [min_val, max_val] become 1, else 0. create range mask |
| 22 | single_polygonize_representative | 3 | pure_raster | `gdal:polygonize` | `native:reclassifybytable -> gdal:polygonize` | Aplica a simbologia categorizada no campo 'DN'. definir simbologia vetor |
| 23 | single_rasterize_representative | 6 | mixed | `gdal:rasterize` | `gdal:warpreproject -> native:fillnodata -> gdal:rasterize -> gdal:cliprasterbymasklayer` | 📦 Workflow Base module. init |
| 24 | single_rasterize_representative | 6 | mixed | `gdal:rasterize` | `native:buffer -> native:clip -> gdal:rasterize -> gdal:warpreproject -> gdal:rastercalculator` | 📦 Opportunities Mask Processor module. init |
| 25 | single_rasterize_representative | 3 | mixed | `gdal:rasterize` | `native:buffer -> native:union -> native:promotetomulti -> native:polygonfromlayerextent -> gdal:clipvectorbypolygon -> gdal:rasterize -> gdal:warpreproject` | build water rasterized |
| 26 | single_rasterize_representative | 3 | mixed | `gdal:rasterize` | `native:extractbylocation -> gdal:rasterize -> gdal:cliprasterbymasklayer` | Model exported as python. initAlgorithm |
| 27 | single_rasterize_representative | 2 | mixed | `gdal:rasterize` | `gdal:rasterize -> gdal:translate` | Create binary masks from selected vector layers, based on a single chosen DTM tile extent, |
| 28 | single_rasterize_representative | 12 | pure_vector | `gdal:rasterize` | `native:dissolve -> native:fieldcalculator -> native:intersection -> native:dissolve -> gdal:rasterize -> native:zonalstatisticsfb -> native:zonalstatisticsfb` | init |
| 29 | single_rasterize_representative | 3 | mixed | `gdal:rasterize` | `gdal:rasterize -> gdal:warpreproject -> gdal:rastercalculator -> gdal:cliprasterbymasklayer` | init |
| 30 | single_rasterize_representative | 3 | mixed | `gdal:rasterize` | `native:buffer -> native:zonalstatisticsfb -> gdal:rasterize -> gdal:merge -> saga:fillsinksxxlwangliu -> gdal:warpreproject -> native:hillshade` |  |
| 31 | single_fixgeometries_representative | 12 | pure_vector | `native:fixgeometries` | `native:fixgeometries -> native:clip` | Fix invalid geometries in input layer and return temporary layer with valid geoms fix geom |
| 32 | single_fixgeometries_representative | 14 | pure_vector | `native:fixgeometries` | `native:fixgeometries -> native:zonalstatisticsfb` | Calculate the height of bounding box in meters calculate centroid |
| 33 | single_fixgeometries_representative | 3 | pure_vector | `native:fixgeometries` | `native:fixgeometries -> native:buffer -> native:difference` | The script defines functions that can be used in the QGIS python console to speed up the g |
| 34 | single_fixgeometries_representative | 3 | pure_vector | `native:fixgeometries` | `native:fixgeometries -> native:multiparttosingleparts -> native:clip -> native:extractbyexpression` | Fixes the geometries of a shapefile and saves the fixed version. fix geometries |
| 35 | single_fixgeometries_representative | 2 | pure_vector | `native:fixgeometries` | `native:fixgeometries -> native:dissolve -> native:polygonize` | SolarPanelGenerator Plugin Coverage Logic init |
| 36 | single_fixgeometries_representative | 3 | pure_vector | `native:fixgeometries` | `native:fixgeometries -> native:fixgeometries -> native:fixgeometries -> native:clip -> native:clip` | Model exported as python. initAlgorithm |
| 37 | single_fixgeometries_representative | 3 | pure_vector | `native:fixgeometries` | `native:fixgeometries -> native:fixgeometries -> native:fixgeometries -> native:mergevectorlayers -> native:dissolve` | This makes parameters for wfs-request of specific area getBboxWmsFormat |
| 38 | single_fixgeometries_representative | 2 | pure_vector | `native:fixgeometries` | `native:fixgeometries -> native:fixgeometries -> native:fixgeometries -> native:fixgeometries -> native:fixgeometries` | Modulo: AyudasGEO RegisterFunction |
| 39 | single_fixgeometries_representative | 1 | pure_vector | `native:fixgeometries` | `native:extractbylocation -> native:fixgeometries -> native:intersection` | GeoLote - Plugin QGIS sanitize field name |
| 40 | single_fixgeometries_representative | 3 | pure_vector | `native:fixgeometries` | `native:difference -> native:dissolve -> native:dissolve -> native:mergevectorlayers -> native:fixgeometries -> native:difference -> native:removenullgeometries -> native:fixgeometries -> native:fixgeometries -> native:union -> native:fixgeometries -> native:mergevectorlayers` | Apply a simple difference operation to the input layers. apply simple difference |
| 41 | single_reprojectlayer_representative | 7 | pure_vector | `native:reprojectlayer` | `native:reprojectlayer -> native:buffer -> native:clip` | PyQGIS Code Snippets |
| 42 | single_reprojectlayer_representative | 7 | pure_vector | `native:reprojectlayer` | `native:reprojectlayer -> native:intersection` | CN Calculator Tool for Hydro Suite init |
| 43 | single_reprojectlayer_representative | 21 | pure_vector | `native:reprojectlayer` | `native:reprojectlayer -> native:reprojectlayer` | This algorithm generates a full sidewalk network based on OSM data within a specified boun |
| 44 | single_reprojectlayer_representative | 4 | mixed | `native:reprojectlayer` | `gdal:warpreproject -> native:reprojectlayer -> native:rastersampling` | process raster sample points |
| 45 | single_reprojectlayer_representative | 6 | pure_vector | `native:reprojectlayer` | `native:reprojectlayer -> native:extractbyexpression` | reproject layer if needed |
| 46 | single_reprojectlayer_representative | 3 | pure_vector | `native:reprojectlayer` | `native:extractbyexpression -> native:intersection -> native:dissolve -> native:retainfields -> native:reprojectlayer -> native:fieldcalculator -> native:savefeatures` | Script using pyqgis |
| 47 | single_reprojectlayer_representative | 7 | mixed | `native:reprojectlayer` | `native:reprojectlayer -> gdal:warpreproject` | Simple feedback object that prints all messages to console reportError |
| 48 | single_reprojectlayer_representative | 3 | pure_vector | `native:reprojectlayer` | `native:reprojectlayer -> native:joinattributesbylocation -> native:multiintersection` | Quite specific to the French case. Add a boolean attribute, for every building of a vector |
| 49 | single_reprojectlayer_representative | 3 | pure_vector | `native:reprojectlayer` | `native:reprojectlayer -> native:renametablefield -> native:retainfields` | parse time interval |
| 50 | single_reprojectlayer_representative | 6 | mixed | `native:reprojectlayer` | `native:reprojectlayer -> gdal:cliprasterbymasklayer` | Create a new print layout and remove any previous layout with the same name. create layout |

## Admission Boundary

- The 179 unique chains can enter chain-level human review.
- The 50-row batch is a balanced first slice, not a training set.
- Before actual manual source review, join each representative back to `/home/yll` provenance and embed source snippets.
- Before training export, require chain-level human approval plus faithful task-description generation.
