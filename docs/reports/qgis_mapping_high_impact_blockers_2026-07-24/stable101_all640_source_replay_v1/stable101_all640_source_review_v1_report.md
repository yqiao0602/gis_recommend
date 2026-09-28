# QGIS stable101 Source Review Pack

This report joins the stable101 50-row chain-level candidate batch back to source files. It is for human review only and does not grant training admission.

## Summary

- Review rows: 640
- Joined sources: 640
- Snippets containing all ordered operators: 640
- Source roots: `{"standard_v2": 191, "workflow": 203, "workflow_A": 246}`
- Modalities: `{"mixed": 278, "pure_raster": 25, "pure_vector": 337}`
- Text quality: `{"usable_seed_text": 330, "weak_code_fragment": 1, "weak_code_import": 1, "weak_metadata": 18, "weak_short_or_empty": 268, "weak_symbol_or_method": 9, "weak_too_few_words": 13}`
- Taxonomy admission: `granted_for_four_stable101_mappings`
- Training admission: `not_granted`

## Review Rows

| # | source | chain freq | modality | operators | source file | task seed |
|---:|---|---:|---|---|---|---|
| 1 | standard_v2 | 9 | pure_raster | `saga:upslopearea -> gdal:polygonize` | `script_0000001.py` | initAlgorithm |
| 2 | standard_v2 | 9 | pure_raster | `saga:upslopearea -> gdal:polygonize` | `script_0000002.py` |  |
| 3 | standard_v2 | 3 | mixed | `native:reprojectlayer -> gdal:merge -> native:slope -> native:zonalstatisticsfb` | `script_0000016.py` | init |
| 4 | standard_v2 | 3 | mixed | `gdal:rastercalculator -> gdal:rasterize -> gdal:rasterize -> gdal:rastercalculator` | `script_0000022.py` | initAlgorithm |
| 5 | standard_v2 | 3 | pure_vector | `native:extractbyexpression -> native:extractbyexpression -> native:fixgeometries -> native:addautoincrementalfield -> native:deletecolumn -> native:renametablefield` | `script_0000023.py` | initAlgorithm |
| 6 | standard_v2 | 3 | mixed | `gdal:warpreproject -> gdal:rasterize -> gdal:assignprojection -> gdal:cliprasterbymasklayer -> gdal:warpreproject -> gdal:warpreproject` | `script_0000029.py` | addAdvancedParameter |
| 7 | standard_v2 | 12 | pure_vector | `native:fixgeometries -> native:clip` | `script_0000034.py` | Fix invalid geometries in input layer and return temporary layer with valid geoms fix geom |
| 8 | standard_v2 | 2 | mixed | `native:reprojectlayer -> gdal:cliprasterbyextent -> gdal:rastercalculator` | `script_0000038.py` | Manning's Roughness Generator - A QGIS Plugin name |
| 9 | standard_v2 | 7 | pure_vector | `native:reprojectlayer -> native:buffer -> native:clip` | `script_0000047.txt` |  |
| 10 | standard_v2 | 7 | pure_vector | `native:reprojectlayer -> native:buffer -> native:clip` | `script_0000048.py` | PyQGIS Code Snippets |
| 11 | standard_v2 | 14 | pure_vector | `native:fixgeometries -> native:zonalstatisticsfb` | `script_0000055.py` |  |
| 12 | standard_v2 | 6 | mixed | `native:buffer -> native:clip -> gdal:rasterize -> gdal:warpreproject -> gdal:rastercalculator` | `script_0000058.py` | 📦 Opportunities Mask Processor module. init |
| 13 | standard_v2 | 6 | pure_vector | `native:fixgeometries -> native:retainfields -> native:zonalstatisticsfb` | `script_0000060.py` | 📦 Subnational Aggregation Processor module. init |
| 14 | standard_v2 | 6 | mixed | `gdal:assignprojection -> native:assignprojection -> native:extractbyextent -> native:fixgeometries -> native:reprojectlayer -> gdal:buildvirtualraster` | `script_0000061.py` | 📦 Utilities module. assign crs to raster layer |
| 15 | standard_v2 | 6 | pure_vector | `native:reprojectlayer -> native:clip` | `script_0000063.py` | 📦 Osm Data Downloader Base module. init |
| 16 | standard_v2 | 3 | pure_vector | `native:reprojectlayer -> native:clip -> native:buffer -> native:dissolve -> native:difference -> native:mergevectorlayers` | `script_0000064.py` | Multi-buffer distances workflow using native QGIS network analysis. init |
| 17 | standard_v2 | 6 | pure_vector | `native:mergevectorlayers -> native:dissolve -> native:difference -> native:mergevectorlayers -> native:reprojectlayer` | `script_0000065.py` | 📦 Multi Buffer Distances Ors Workflow module. init |
| 18 | standard_v2 | 6 | mixed | `gdal:warpreproject -> native:fillnodata -> gdal:rasterize -> gdal:cliprasterbymasklayer` | `script_0000067.py` | 📦 Workflow Base module. init |
| 19 | standard_v2 | 3 | pure_vector | `native:fixgeometries -> native:savefeatures -> native:mergevectorlayers` | `script_0000076.py` | layer |
| 20 | standard_v2 | 12 | pure_vector | `native:dissolve -> native:fieldcalculator -> native:intersection -> native:dissolve -> gdal:rasterize -> native:zonalstatisticsfb -> native:zonalstatisticsfb` | `script_0000080.py` | init |
| 21 | standard_v2 | 3 | pure_vector | `native:fixgeometries -> native:mergevectorlayers -> native:difference -> native:mergevectorlayers` | `script_0000083.py` | init |
| 22 | standard_v2 | 12 | pure_vector | `native:fixgeometries -> native:clip` | `script_0000096.txt` | Fix invalid geometries in input layer and return temporary layer with valid geoms fix geom |
| 23 | standard_v2 | 3 | pure_raster | `gdal:cliprasterbymasklayer -> gdal:polygonize` | `script_0000097.py` | init |
| 24 | standard_v2 | 2 | mixed | `qgis:rastercalculator -> qgis:rastercalculator -> qgis:rastercalculator -> gdal:polygonize -> native:dissolve -> native:clip` | `script_0000105.py` | Class to classify landuse from OSM init |
| 25 | standard_v2 | 3 | pure_vector | `native:multiparttosingleparts -> native:reprojectlayer -> qgis:advancedpythonfieldcalculator -> native:clip -> native:multiparttosingleparts -> native:extractbyexpression -> native:symmetricaldifference -> native:multiparttosingleparts` | `script_0000106.py` | init |
| 26 | standard_v2 | 3 | pure_vector | `native:removenullgeometries -> native:reprojectlayer` | `script_0000119.py` | initAlgorithm |
| 27 | standard_v2 | 3 | pure_vector | `native:fixgeometries -> native:fixgeometries -> native:intersection -> qgis:statisticsbycategories` | `script_0000158.py` |  |
| 28 | standard_v2 | 3 | pure_vector | `native:fixgeometries -> native:dissolve -> native:dissolve -> qgis:statisticsbycategories` | `script_0000159.py` |  |
| 29 | standard_v2 | 66 | mixed | `native:reclassifybytable -> native:reclassifybytable -> native:reclassifybytable -> gdal:polygonize -> native:zonalstatisticsfb` | `script_0000231.py` | Module 7: Market Classification & Zoning |
| 30 | standard_v2 | 66 | mixed | `native:reclassifybytable -> native:reclassifybytable -> native:reclassifybytable -> gdal:polygonize -> native:zonalstatisticsfb` | `script_0000232.py` | Module 7: Market Classification & Zoning |
| 31 | standard_v2 | 66 | mixed | `native:reclassifybytable -> native:reclassifybytable -> native:reclassifybytable -> gdal:polygonize -> native:zonalstatisticsfb` | `script_0000233.py` | Module 7: Market Classification & Zoning |
| 32 | standard_v2 | 66 | mixed | `native:reclassifybytable -> native:reclassifybytable -> native:reclassifybytable -> gdal:polygonize -> native:zonalstatisticsfb` | `script_0000234.py` | Module 7: Market Classification & Zoning |
| 33 | standard_v2 | 66 | mixed | `native:reclassifybytable -> native:reclassifybytable -> native:reclassifybytable -> gdal:polygonize -> native:zonalstatisticsfb` | `script_0000235.py` | Module 7: Market Classification & Zoning |
| 34 | standard_v2 | 66 | mixed | `native:reclassifybytable -> native:reclassifybytable -> native:reclassifybytable -> gdal:polygonize -> native:zonalstatisticsfb` | `script_0000236.py` | Module 7: Market Classification & Zoning |
| 35 | standard_v2 | 66 | mixed | `native:reclassifybytable -> native:reclassifybytable -> native:reclassifybytable -> gdal:polygonize -> native:zonalstatisticsfb` | `script_0000237.py` | Module 7: Market Classification & Zoning |
| 36 | standard_v2 | 66 | mixed | `native:reclassifybytable -> native:reclassifybytable -> native:reclassifybytable -> gdal:polygonize -> native:zonalstatisticsfb` | `script_0000238.py` | Module 7: Market Classification & Zoning |
| 37 | standard_v2 | 66 | mixed | `native:reclassifybytable -> native:reclassifybytable -> native:reclassifybytable -> gdal:polygonize -> native:zonalstatisticsfb` | `script_0000239.py` | Module 7: Market Classification & Zoning |
| 38 | standard_v2 | 66 | mixed | `native:reclassifybytable -> native:reclassifybytable -> native:reclassifybytable -> gdal:polygonize -> native:zonalstatisticsfb` | `script_0000240.py` | Module 7: Market Classification & Zoning |
| 39 | standard_v2 | 66 | mixed | `native:reclassifybytable -> native:reclassifybytable -> native:reclassifybytable -> gdal:polygonize -> native:zonalstatisticsfb` | `script_0000241.py` | Module 7: Market Classification & Zoning |
| 40 | standard_v2 | 66 | mixed | `native:reclassifybytable -> native:reclassifybytable -> native:reclassifybytable -> gdal:polygonize -> native:zonalstatisticsfb` | `script_0000242.py` | Module 7: Market Classification & Zoning |
| 41 | standard_v2 | 66 | mixed | `native:reclassifybytable -> native:reclassifybytable -> native:reclassifybytable -> gdal:polygonize -> native:zonalstatisticsfb` | `script_0000243.py` | Module 7: Market Classification & Zoning |
| 42 | standard_v2 | 66 | mixed | `native:reclassifybytable -> native:reclassifybytable -> native:reclassifybytable -> gdal:polygonize -> native:zonalstatisticsfb` | `script_0000244.py` | Module 7: Market Classification & Zoning |
| 43 | standard_v2 | 66 | mixed | `native:reclassifybytable -> native:reclassifybytable -> native:reclassifybytable -> gdal:polygonize -> native:zonalstatisticsfb` | `script_0000245.py` | Module 7: Market Classification & Zoning |
| 44 | standard_v2 | 66 | mixed | `native:reclassifybytable -> native:reclassifybytable -> native:reclassifybytable -> gdal:polygonize -> native:zonalstatisticsfb` | `script_0000246.py` | Module 7: Market Classification & Zoning |
| 45 | standard_v2 | 66 | mixed | `native:reclassifybytable -> native:reclassifybytable -> native:reclassifybytable -> gdal:polygonize -> native:zonalstatisticsfb` | `script_0000247.py` | Module 7: Market Classification & Zoning |
| 46 | standard_v2 | 66 | mixed | `native:reclassifybytable -> native:reclassifybytable -> native:reclassifybytable -> gdal:polygonize -> native:zonalstatisticsfb` | `script_0000248.py` | Module 7: Market Classification & Zoning |
| 47 | standard_v2 | 66 | mixed | `native:reclassifybytable -> native:reclassifybytable -> native:reclassifybytable -> gdal:polygonize -> native:zonalstatisticsfb` | `script_0000249.py` | Module 7: Market Classification & Zoning |
| 48 | standard_v2 | 66 | mixed | `native:reclassifybytable -> native:reclassifybytable -> native:reclassifybytable -> gdal:polygonize -> native:zonalstatisticsfb` | `script_0000250.py` | Module 7: Market Classification & Zoning |
| 49 | standard_v2 | 66 | mixed | `native:reclassifybytable -> native:reclassifybytable -> native:reclassifybytable -> gdal:polygonize -> native:zonalstatisticsfb` | `script_0000251.py` | Module 7: Market Classification & Zoning |
| 50 | standard_v2 | 66 | mixed | `native:reclassifybytable -> native:reclassifybytable -> native:reclassifybytable -> gdal:polygonize -> native:zonalstatisticsfb` | `script_0000252.py` | Module 7: Market Classification & Zoning |
| 51 | standard_v2 | 6 | pure_vector | `native:reprojectlayer -> native:extractbyexpression` | `script_0000269.py` | reproject layer if needed |
| 52 | standard_v2 | 3 | mixed | `native:reprojectlayer -> native:buffer -> gdal:cliprasterbymasklayer -> gdal:warpreproject` | `script_0000270.py` | init |
| 53 | standard_v2 | 3 | pure_vector | `gdal:rasterize -> native:fieldcalculator -> gdal:rasterize` | `script_0000275.py` | initAlgorithm |
| 54 | standard_v2 | 3 | mixed | `native:extractbyattribute -> native:reprojectlayer -> gdal:cliprasterbymasklayer -> gdal:warpreproject -> gdal:cliprasterbymasklayer -> gdal:warpreproject -> gdal:fillnodata` | `script_0000279.py` | climate extraction |
| 55 | standard_v2 | 3 | pure_vector | `native:refactorfields -> native:fixgeometries` | `script_0000305.py` | create table |
| 56 | standard_v2 | 3 | mixed | `qgis:rastercalculator -> gdal:polygonize -> native:buffer -> gdal:cliprasterbymasklayer` | `script_0000313.py` | Model exported as python. initAlgorithm |
| 57 | standard_v2 | 3 | mixed | `native:extractbylocation -> gdal:rasterize -> gdal:cliprasterbymasklayer` | `script_0000315.py` | Model exported as python. initAlgorithm |
| 58 | standard_v2 | 3 | mixed | `native:buffer -> native:zonalstatisticsfb -> gdal:rasterize -> gdal:merge -> saga:fillsinksxxlwangliu -> gdal:warpreproject -> native:hillshade` | `script_0000332.py` |  |
| 59 | standard_v2 | 3 | mixed | `gdal:polygonize -> native:extractbyexpression -> native:dissolve -> gdal:polygonize -> native:extractbyexpression -> native:fieldcalculator -> native:fieldcalculator -> native:zonalstatisticsfb -> native:zonalstatisticsfb -> native:zonalstatisticsfb -> native:fieldcalculator` | `script_0000342.py` | <h3>Analisi del Catchment</h3> name |
| 60 | standard_v2 | 3 | mixed | `gdal:rasterize -> native:fixgeometries -> native:zonalstatisticsfb -> native:zonalhistogram` | `script_0000343.py` | Model exported as python. initAlgorithm |
| 61 | standard_v2 | 3 | pure_vector | `native:fixgeometries -> native:fixgeometries -> native:fixgeometries -> native:clip -> native:clip` | `script_0000349.py` | Model exported as python. initAlgorithm |
| 62 | standard_v2 | 4 | mixed | `gdal:rasterize -> gdal:polygonize` | `script_0000359.txt` | getBboxWmsFormat |
| 63 | standard_v2 | 3 | pure_vector | `native:fixgeometries -> native:fixgeometries -> native:fixgeometries -> native:mergevectorlayers -> native:dissolve` | `script_0000363.py` | This makes parameters for wfs-request of specific area getBboxWmsFormat |
| 64 | standard_v2 | 3 | mixed | `native:buffer -> native:union -> native:promotetomulti -> native:polygonfromlayerextent -> gdal:clipvectorbypolygon -> gdal:rasterize -> gdal:warpreproject` | `script_0000375.py` | build water rasterized |
| 65 | standard_v2 | 9 | mixed | `gdal:translate -> native:reprojectlayer` | `script_0000398.py` |  |
| 66 | standard_v2 | 9 | mixed | `gdal:translate -> native:reprojectlayer` | `script_0000399.py` |  |
| 67 | standard_v2 | 9 | mixed | `gdal:translate -> native:reprojectlayer` | `script_0000400.py` |  |
| 68 | standard_v2 | 3 | mixed | `native:mergevectorlayers -> gdal:polygonize` | `script_0000401.py` | checkLayerPoints |
| 69 | standard_v2 | 3 | mixed | `native:savefeatures -> gdal:translate -> native:reprojectlayer -> gdal:warpreproject -> gdal:rasterize -> native:fixgeometries -> native:union -> native:rastersampling -> native:rastersampling -> native:savefeatures` | `script_0000404.py` | init |
| 70 | standard_v2 | 6 | mixed | `native:buffer -> native:difference -> native:reclassifybytable -> gdal:polygonize -> native:extractbyexpression -> native:reclassifybytable -> gdal:polygonize -> native:extractbyexpression -> native:buffer -> native:difference -> native:savefeatures` | `script_0000423.py` | ================================================================================ init |
| 71 | standard_v2 | 6 | mixed | `native:buffer -> native:difference -> native:reclassifybytable -> gdal:polygonize -> native:extractbyexpression -> native:reclassifybytable -> gdal:polygonize -> native:extractbyexpression -> native:buffer -> native:difference -> native:savefeatures` | `script_0000425.py` | ================================================================================ init |
| 72 | standard_v2 | 3 | pure_raster | `gdal:cliprasterbymasklayer -> gdal:warpreproject -> gdal:polygonize -> gdal:hillshade` | `script_0000434.py` | Bilinear interpolation of raster value at (x, y). cleanup file |
| 73 | standard_v2 | 3 | mixed | `gdal:polygonize -> native:joinattributesbylocation -> native:joinattributesbylocation` | `script_0000436.py` |  |
| 74 | standard_v2 | 3 | mixed | `native:reprojectlayer -> gdal:cliprasterbymasklayer -> gdal:cliprasterbyextent -> gdal:translate -> gdal:warpreproject -> gdal:rastercalculator` | `script_0000442.py` | Calculates the Curve Number using global datasets from ESA WorldCover and ORNL HYSOG. init |
| 75 | standard_v2 | 8 | mixed | `gdal:polygonize -> native:intersection` | `script_0000448.py` | initAlgorithm |
| 76 | standard_v2 | 8 | mixed | `gdal:polygonize -> native:intersection` | `script_0000451.py` | prompt raster |
| 77 | standard_v2 | 3 | mixed | `gdal:polygonize -> gdal:polygonize -> native:clip -> gdal:polygonize -> native:buffer -> native:clip -> native:buffer -> native:buffer -> native:buffer -> native:dissolve -> native:clip` | `script_0000469.py` | to avoid havign to use "stroke to path" which keeps crashing in inkscape buffer params |
| 78 | standard_v2 | 3 | mixed | `gdal:warpreproject -> native:reclassifybytable -> gdal:polygonize -> native:fixgeometries -> native:zonalstatisticsfb -> native:fieldcalculator -> native:extractbyexpression -> native:fieldcalculator -> native:centroids` | `script_0000493.py` | Automated Keyline Keypoint Detection Algorithm |
| 79 | standard_v2 | 3 | mixed | `gdal:warpreproject -> saga:fillsinksxxlwangliu -> native:zonalstatistics -> native:zonalstatistics -> gdal:cliprasterbyextent -> native:fixgeometries -> native:buffer -> native:clip -> native:clip -> gdal:polygonize -> native:zonalstatistics -> native:zonalstatistics` | `script_0000498.py` | HydroAnalysis.py - Module d'analyse hydrologique pour SigLogix (QGIS) init |
| 80 | standard_v2 | 9 | pure_raster | `saga:upslopearea -> gdal:polygonize` | `script_0000502.py` |  |
| 81 | standard_v2 | 1 | pure_vector | `native:extractbylocation -> native:reprojectlayer -> native:refactorfields` | `script_0000507.py` |  |
| 82 | standard_v2 | 3 | mixed | `gdal:cliprasterbymasklayer -> native:clip -> native:reclassifybytable -> gdal:polygonize` | `script_0000510.py` |  |
| 83 | standard_v2 | 3 | mixed | `native:reprojectlayer -> native:reprojectlayer -> native:reprojectlayer -> gdal:warpreproject -> native:reprojectlayer` | `script_0000513.py` | init |
| 84 | standard_v2 | 14 | pure_vector | `native:fixgeometries -> native:zonalstatisticsfb` | `script_0000515.py` |  |
| 85 | standard_v2 | 14 | pure_vector | `native:fixgeometries -> native:zonalstatisticsfb` | `script_0000537.py` |  |
| 86 | standard_v2 | 6 | pure_vector | `native:reprojectlayer -> native:reprojectlayer -> native:fixgeometries -> native:fixgeometries -> native:fixgeometries -> native:intersection -> native:intersection -> native:fieldcalculator -> native:fieldcalculator -> native:fieldcalculator -> native:fieldcalculator -> native:fieldcalculator -> native:fieldcalculator -> native:fieldcalculator` | `script_0000540.py` | WHEN "class_name" = 'Built-up' THEN 'Concrete' initAlgorithm |
| 87 | standard_v2 | 6 | pure_vector | `native:reprojectlayer -> native:reprojectlayer -> native:fixgeometries -> native:fixgeometries -> native:fixgeometries -> native:intersection -> native:intersection -> native:fieldcalculator -> native:fieldcalculator -> native:fieldcalculator -> native:fieldcalculator -> native:fieldcalculator -> native:fieldcalculator -> native:fieldcalculator` | `script_0000541.py` | WHEN "class_name" = 'Built-up' THEN 'Concrete' initAlgorithm |
| 88 | standard_v2 | 3 | pure_vector | `native:fixgeometries -> native:buffer -> native:difference` | `script_0000553.py` | The script defines functions that can be used in the QGIS python console to speed up the g |
| 89 | standard_v2 | 3 | pure_vector | `native:reprojectlayer -> native:buffer` | `script_0000587.py` | initAlgorithm |
| 90 | standard_v2 | 3 | pure_vector | `native:reprojectlayer -> native:renametablefield -> native:retainfields` | `script_0000592.py` | parse time interval |
| 91 | standard_v2 | 3 | pure_vector | `native:reprojectlayer -> native:retainfields` | `script_0000593.py` | parse time interval |
| 92 | standard_v2 | 3 | pure_vector | `native:reprojectlayer -> native:savefeatures -> native:savefeatures -> native:savefeatures -> native:reprojectlayer -> native:savefeatures -> native:reprojectlayer -> native:savefeatures` | `script_0000598.py` | init |
| 93 | standard_v2 | 6 | pure_vector | `native:reprojectlayer -> native:extractbyexpression` | `script_0000615.py` |  |
| 94 | standard_v2 | 3 | pure_vector | `native:fixgeometries -> native:clip -> native:clip -> native:buffer -> native:extractbylocation -> native:countpointsinpolygon` | `script_0000616.py` |  |
| 95 | standard_v2 | 3 | pure_vector | `native:fixgeometries -> native:dissolve -> native:buffer -> native:extractbylocation` | `script_0000620.py` |  |
| 96 | standard_v2 | 3 | mixed | `gdal:polygonize -> native:buffer -> gdal:rasterize` | `script_0000622.py` |  |
| 97 | standard_v2 | 3 | pure_vector | `native:fixgeometries -> native:buffer -> native:intersection` | `script_0000633.py` |  |
| 98 | standard_v2 | 6 | mixed | `native:buffer -> native:clip -> gdal:rasterize -> gdal:warpreproject -> gdal:rastercalculator` | `script_0000641.py` | A QgsTask subclass for generating job opportunity mask layers. init |
| 99 | standard_v2 | 6 | pure_vector | `native:fixgeometries -> native:retainfields -> native:zonalstatisticsfb` | `script_0000643.py` | A QgsTask subclass for calculating WEE x Population SCORE and or WEE score per aggregation |
| 100 | standard_v2 | 6 | mixed | `gdal:assignprojection -> native:assignprojection -> native:extractbyextent -> native:fixgeometries -> native:reprojectlayer -> gdal:buildvirtualraster` | `script_0000644.py` | Assigns a CRS to a layer and returns the layer. assign crs to raster layer |
| 101 | standard_v2 | 6 | pure_vector | `native:mergevectorlayers -> native:dissolve -> native:difference -> native:mergevectorlayers -> native:reprojectlayer` | `script_0000646.py` | Concrete implementation of a 'multi_buffer_distances' workflow. init |
| 102 | standard_v2 | 6 | mixed | `gdal:warpreproject -> native:fillnodata -> gdal:rasterize -> gdal:cliprasterbymasklayer` | `script_0000648.py` | Abstract base class for all workflows. init |
| 103 | standard_v2 | 7 | pure_vector | `native:reprojectlayer -> native:intersection` | `script_0000649.py` | init |
| 104 | standard_v2 | 3 | pure_vector | `native:dissolve -> native:multiparttosingleparts -> native:buffer -> native:dissolve -> native:dissolve -> native:reprojectlayer -> qgis:checkvalidity` | `script_0000655.py` | init |
| 105 | standard_v2 | 3 | pure_vector | `native:reprojectlayer -> native:reprojectlayer -> native:buffer -> native:clip -> native:fieldcalculator` | `script_0000668.py` | Vector Geoprocessing — PyQGIS Processing Script |
| 106 | standard_v2 | 2 | mixed | `gdal:warpreproject -> native:reprojectlayer` | `script_0000669.py` | 重投影 Skill — 支持矢量和栅格. |
| 107 | standard_v2 | 2 | pure_vector | `native:reprojectlayer -> native:clip -> native:buffer -> native:joinattributesbylocation -> native:savefeatures` | `script_0000670.py` | Executor Agent — PyQGIS 脚本注入执行与闭环自愈验证. verify hash |
| 108 | standard_v2 | 5 | pure_vector | `native:fixgeometries -> native:dissolve` | `script_0000677.py` | init |
| 109 | standard_v2 | 3 | pure_vector | `native:fixgeometries -> native:joinattributesbylocation -> native:reprojectlayer -> native:extractbyexpression -> native:dissolve` | `script_0000686.py` | shortHelpString |
| 110 | standard_v2 | 14 | pure_vector | `native:fixgeometries -> native:zonalstatisticsfb` | `script_0000693.py` |  |
| 111 | standard_v2 | 3 | mixed | `gdal:rgbtopct -> gdal:polygonize -> native:extractbyattribute -> native:fixgeometries` | `script_0000695.py` |  |
| 112 | standard_v2 | 3 | pure_vector | `native:reprojectlayer -> native:dissolve -> native:buffer -> native:reprojectlayer -> native:intersection -> native:fixgeometries` | `script_0000696.py` |  |
| 113 | standard_v2 | 3 | pure_vector | `native:mergevectorlayers -> native:reprojectlayer` | `script_0000716.py` | editAttribute |
| 114 | standard_v2 | 3 | pure_vector | `native:reprojectlayer -> native:reprojectlayer -> native:reprojectlayer -> native:buffer -> qgis:joinbylocationsummary -> native:buffer -> qgis:joinbylocationsummary -> native:fieldcalculator -> native:dbscanclustering -> native:reprojectlayer -> native:reprojectlayer` | `script_0000717.py` | Sample 01: Utility Outage Prioritization load layer |
| 115 | standard_v2 | 3 | pure_vector | `native:reprojectlayer -> native:reprojectlayer -> native:reprojectlayer -> native:buffer -> qgis:joinbylocationsummary -> qgis:joinbylocationsummary -> native:fieldcalculator -> native:reprojectlayer` | `script_0000718.py` | Sample 02: Right-of-Way Vegetation + Flood Risk load layer |
| 116 | standard_v2 | 2 | pure_vector | `native:reprojectlayer -> native:buffer -> native:reprojectlayer` | `script_0000730.py` | PyQGIS pipeline — builds a QGIS project with styled layers, buffers, and per-school map ex |
| 117 | standard_v2 | 3 | pure_vector | `native:reprojectlayer -> native:buffer -> native:difference -> native:multiparttosingleparts` | `script_0000736.py` |  |
| 118 | standard_v2 | 3 | pure_vector | `qgis:checkvalidity -> native:fixgeometries -> qgis:checkvalidity -> native:fixgeometries` | `script_0000737.py` |  |
| 119 | standard_v2 | 3 | pure_vector | `native:reprojectlayer -> native:extractspecificvertices -> native:extractspecificvertices` | `script_0000749.py` | initAlgorithm |
| 120 | standard_v2 | 5 | pure_vector | `native:reprojectlayer -> gdal:rasterize` | `script_0000751.py` | get config |
| 121 | standard_v2 | 3 | pure_vector | `native:reprojectlayer -> native:joinattributesbylocation -> native:multiintersection` | `script_0000754.py` | Quite specific to the French case. Add a boolean attribute, for every building of a vector |
| 122 | standard_v2 | 4 | mixed | `gdal:cliprasterbymasklayer -> gdal:cliprasterbymasklayer -> native:reprojectlayer` | `script_0000764.py` | initAlgorithm |
| 123 | standard_v2 | 3 | pure_vector | `native:reprojectlayer -> native:extractbyexpression -> native:buffer -> native:mergevectorlayers -> native:reprojectlayer` | `script_0000780.py` | main |
| 124 | standard_v2 | 3 | pure_vector | `native:difference -> native:buffer -> native:clip -> native:fixgeometries -> native:mergevectorlayers -> native:reprojectlayer` | `script_0000783.py` | config |
| 125 | standard_v2 | 3 | mixed | `native:reprojectlayer -> native:clip -> native:fixgeometries -> native:clip -> native:clip -> native:fixgeometries -> native:clip -> native:reprojectlayer -> gdal:cliprasterbymasklayer -> gdal:polygonize -> native:addfieldtoattributestable -> native:mergevectorlayers -> native:reprojectlayer -> native:reprojectlayer` | `script_0000802.py` | enable logging |
| 126 | standard_v2 | 3 | pure_vector | `native:fixgeometries -> native:multiparttosingleparts -> native:clip -> native:extractbyexpression` | `script_0000817.py` | Fixes the geometries of a shapefile and saves the fixed version. fix geometries |
| 127 | standard_v2 | 3 | pure_vector | `native:difference -> native:dissolve -> native:dissolve -> native:mergevectorlayers -> native:fixgeometries -> native:difference -> native:removenullgeometries -> native:fixgeometries -> native:fixgeometries -> native:union -> native:fixgeometries -> native:mergevectorlayers` | `script_0000819.py` | Apply a simple difference operation to the input layers. apply simple difference |
| 128 | standard_v2 | 3 | mixed | `native:clip -> gdal:polygonize -> gdal:cliprasterbyextent` | `script_0000820.py` | Clip a QgsVector layer by different QgsVector layer simple clip |
| 129 | standard_v2 | 3 | pure_vector | `native:fixgeometries -> native:fixgeometries -> native:clip` | `script_0000821.py` | Class to download and clip WFS layers, used before and during WFStask init |
| 130 | standard_v2 | 3 | pure_vector | `native:reprojectlayer -> native:clip -> native:reprojectlayer` | `script_0000827.py` | Download features from an ArcGIS Feature/MapServer layer using paged requests, return Feat |
| 131 | standard_v2 | 3 | pure_vector | `native:reprojectlayer -> native:mergevectorlayers -> native:clip` | `script_0000828.py` | load road layer |
| 132 | standard_v2 | 6 | pure_vector | `native:reprojectlayer -> native:clip` | `script_0000829.py` |  |
| 133 | standard_v2 | 3 | pure_vector | `native:reprojectlayer -> native:union -> native:union -> native:reprojectlayer` | `script_0000831.py` | select nombre_esquema,nombre_capa from acervo_descripcion_1.mapa_master_vw where id in (se |
| 134 | standard_v2 | 3 | mixed | `native:extractbyextent -> native:fixgeometries -> native:clip -> native:reprojectlayer -> gdal:rasterize -> gdal:warpreproject -> native:savefeatures -> native:reprojectlayer -> native:fixgeometries -> native:clip -> native:multiparttosingleparts -> native:reprojectlayer` | `script_0000833.py` | Dialog for filtering vector layer features by attribute values. init |
| 135 | standard_v2 | 3 | pure_vector | `native:extractbyexpression -> native:intersection -> native:intersection -> native:dissolve -> native:dissolve -> native:refactorfields -> native:fixgeometries -> native:refactorfields -> native:fixgeometries -> native:promotetomulti -> native:promotetomulti -> native:dissolve -> native:dissolve -> native:refactorfields -> native:refactorfields` | `script_0000844.py` | Model exported as python. initAlgorithm |
| 136 | standard_v2 | 3 | pure_vector | `native:refactorfields -> native:refactorfields -> native:extractbyattribute -> native:extractbyattribute -> native:fixgeometries -> native:fixgeometries -> native:mergevectorlayers -> native:refactorfields -> native:dissolve -> native:refactorfields` | `script_0000847.py` | Model exported as python. initAlgorithm |
| 137 | standard_v2 | 12 | pure_vector | `native:fixgeometries -> native:clip` | `script_0000862.py` | Fix invalid geometries in input layer and return temporary layer with valid geoms addlayer |
| 138 | standard_v2 | 3 | pure_vector | `native:reprojectlayer -> native:reprojectlayer -> native:savefeatures -> native:clip` | `script_0000871.py` | Return all polygon vector layers currently loaded in the project. polygon layers |
| 139 | standard_v2 | 3 | pure_vector | `native:fixgeometries -> native:extractbyattribute -> native:reprojectlayer -> native:refactorfields -> native:refactorfields -> native:savefeatures` | `script_0000872.py` | Model exported as python (patched). initAlgorithm |
| 140 | standard_v2 | 3 | mixed | `native:reprojectlayer -> native:clip -> native:reprojectlayer -> gdal:cliprasterbymasklayer` | `script_0000877.py` |  |
| 141 | standard_v2 | 3 | pure_vector | `native:intersection -> native:intersection -> native:fixgeometries` | `script_0000879.py` | get project crs |
| 142 | standard_v2 | 2 | pure_raster | `gdal:rastercalculator -> gdal:polygonize` | `script_0000882.py` | This shared script processes a raster dataset (NDVI) by performing the following steps: |
| 143 | standard_v2 | 3 | pure_raster | `native:reclassifybytable -> gdal:polygonize` | `script_0000888.py` | Aplica a simbologia categorizada no campo 'DN'. definir simbologia vetor |
| 144 | standard_v2 | 8 | mixed | `gdal:polygonize -> native:intersection` | `script_0000892.py` |  |
| 145 | standard_v2 | 3 | pure_vector | `native:fixgeometries -> native:reprojectlayer -> native:intersection -> native:difference -> native:intersection -> native:difference -> native:difference -> native:mergevectorlayers` | `script_0000894.py` | Remove acentos e converte para minúsculas init |
| 146 | standard_v2 | 3 | pure_vector | `native:fixgeometries -> native:reprojectlayer -> native:difference -> native:mergevectorlayers` | `script_0000895.py` | Remove acentos e converte para minúsculas init |
| 147 | standard_v2 | 7 | pure_vector | `native:reprojectlayer -> native:intersection` | `script_0000899.py` | CN Calculator Tool for Hydro Suite init |
| 148 | standard_v2 | 7 | pure_vector | `native:reprojectlayer -> native:intersection` | `script_0000900.py` | Rational C Calculator Tool for Hydro Suite init |
| 149 | standard_v2 | 3 | pure_vector | `native:extractbyexpression -> native:intersection -> native:dissolve -> native:retainfields -> native:reprojectlayer -> native:fieldcalculator -> native:savefeatures` | `script_0000902.py` | Script using pyqgis |
| 150 | standard_v2 | 1 | pure_vector | `native:renametablefield -> native:renametablefield -> native:assignprojection -> native:fixgeometries -> native:reprojectlayer -> native:promotetomulti -> native:reprojectlayer -> native:joinattributesbylocation -> native:fieldcalculator` | `script_0000909.py` | ensure plugins path |
| 151 | standard_v2 | 1 | pure_vector | `native:savefeatures -> native:reprojectlayer -> native:savefeatures` | `script_0000910.py` | run_pipeline_debug_v3.py |
| 152 | standard_v2 | 12 | pure_vector | `native:dissolve -> native:fieldcalculator -> native:intersection -> native:dissolve -> gdal:rasterize -> native:zonalstatisticsfb -> native:zonalstatisticsfb` | `script_0000912.py` | init |
| 153 | standard_v2 | 12 | pure_vector | `native:dissolve -> native:fieldcalculator -> native:intersection -> native:dissolve -> gdal:rasterize -> native:zonalstatisticsfb -> native:zonalstatisticsfb` | `script_0000913.py` | init |
| 154 | standard_v2 | 12 | pure_vector | `native:dissolve -> native:fieldcalculator -> native:intersection -> native:dissolve -> gdal:rasterize -> native:zonalstatisticsfb -> native:zonalstatisticsfb` | `script_0000914.py` | init |
| 155 | standard_v2 | 3 | pure_vector | `native:reprojectlayer -> native:rastersampling -> native:zonalstatisticsfb -> native:reprojectlayer -> native:savefeatures` | `script_0000918.py` | v0.2 2024-09-03 rainfall factor |
| 156 | standard_v2 | 3 | pure_vector | `native:reprojectlayer -> native:fixgeometries -> native:intersection -> native:extractbylocation` | `script_0000924.py` |  |
| 157 | standard_v2 | 3 | mixed | `native:translategeometry -> gdal:rasterize -> gdal:cliprasterbymasklayer` | `script_0000926.py` | init |
| 158 | standard_v2 | 9 | mixed | `gdal:translate -> native:fixgeometries` | `script_0000927.py` | qgisName |
| 159 | standard_v2 | 9 | mixed | `gdal:translate -> native:fixgeometries` | `script_0000929.py` | qgisName |
| 160 | standard_v2 | 9 | mixed | `gdal:translate -> native:fixgeometries` | `script_0000933.py` | qgisName |
| 161 | standard_v2 | 2 | pure_vector | `native:mergevectorlayers -> native:retainfields -> native:reprojectlayer -> native:mergevectorlayers -> native:mergevectorlayers` | `script_0000938.py` | init |
| 162 | standard_v2 | 3 | mixed | `native:reprojectlayer -> native:reprojectlayer -> qgis:minimumboundinggeometry -> native:selectbylocation -> gdal:translate -> gdal:translate -> gdal:assignprojection` | `script_0000943.py` | mainFunction |
| 163 | standard_v2 | 3 | pure_vector | `native:centroids -> native:reprojectlayer -> native:rastersampling` | `script_0000945.py` | initAlgorithm |
| 164 | standard_v2 | 3 | pure_vector | `native:centroids -> native:reprojectlayer -> native:joinattributesbylocation` | `script_0000946.py` | initAlgorithm |
| 165 | standard_v2 | 6 | mixed | `native:reprojectlayer -> gdal:cliprasterbymasklayer` | `script_0000956.py` | Create a new print layout and remove any previous layout with the same name. create layout |
| 166 | standard_v2 | 6 | mixed | `native:reprojectlayer -> gdal:cliprasterbymasklayer` | `script_0000957.py` | Create a new print layout and remove any previous layout with the same name. create layout |
| 167 | standard_v2 | 7 | mixed | `native:reprojectlayer -> gdal:warpreproject` | `script_0000958.py` | Simple feedback object that prints all messages to console reportError |
| 168 | standard_v2 | 12 | pure_vector | `native:reprojectlayer -> native:multiparttosingleparts` | `script_0000959.py` | Author: Mario Königbauer (mkoenigb@gmx.de) initAlgorithm |
| 169 | standard_v2 | 3 | pure_vector | `native:reprojectlayer -> native:extractvertices -> native:multiparttosingleparts` | `script_0000960.py` | Author: Mario Königbauer (mkoenigb@gmx.de) initAlgorithm |
| 170 | standard_v2 | 3 | pure_vector | `native:reprojectlayer -> native:centroids` | `script_0000961.py` | Author: Mario Königbauer (mkoenigb@gmx.de) initAlgorithm |
| 171 | standard_v2 | 12 | pure_vector | `native:reprojectlayer -> native:multiparttosingleparts` | `script_0000962.py` | Author: Mario Königbauer (mkoenigb@gmx.de) initAlgorithm |
| 172 | standard_v2 | 12 | pure_vector | `native:reprojectlayer -> native:multiparttosingleparts` | `script_0000963.py` | Author: Mario Königbauer (mkoenigb@gmx.de) initAlgorithm |
| 173 | standard_v2 | 12 | pure_vector | `native:reprojectlayer -> native:multiparttosingleparts` | `script_0000964.py` | Author: Mario Königbauer (mkoenigb@gmx.de) initAlgorithm |
| 174 | standard_v2 | 3 | pure_vector | `native:fixgeometries -> native:dissolve -> native:reprojectlayer` | `script_0000972.py` | init |
| 175 | standard_v2 | 4 | pure_vector | `native:union -> native:multiparttosingleparts -> native:fixgeometries -> native:multiparttosingleparts -> native:reprojectlayer` | `script_0000973.py` | Decorator to catch sql exceptions. sql error handler |
| 176 | standard_v2 | 1 | pure_vector | `native:fixgeometries -> native:reprojectlayer -> native:extractbyextent -> native:fieldcalculator` | `script_0000977.py` | Clip layer by extent clip in projectcrs |
| 177 | standard_v2 | 1 | pure_vector | `native:reprojectlayer -> native:savefeatures` | `script_0000978.py` | Utility functions for olive tree canopy segmentation using Otsu. load layer from output |
| 178 | standard_v2 | 1 | pure_vector | `native:reprojectlayer -> native:joinattributesbylocation` | `script_0000979.py` |  |
| 179 | standard_v2 | 1 | mixed | `gdal:polygonize -> native:reprojectlayer -> native:reprojectlayer -> native:joinattributesbylocation` | `script_0000980.py` | reprojected = processing.run("native:reprojectlayer", { |
| 180 | standard_v2 | 4 | pure_vector | `native:union -> native:multiparttosingleparts -> native:fixgeometries -> native:multiparttosingleparts -> native:reprojectlayer` | `script_0000981.py` | Decorator to catch sql exceptions. sql error handler |
| 181 | standard_v2 | 1 | pure_vector | `native:reprojectlayer -> native:reprojectlayer -> native:assignprojection` | `script_0000982.py` | initAlgorithm |
| 182 | standard_v2 | 1 | mixed | `native:reprojectlayer -> native:zonalhistogram -> native:zonalhistogram -> native:zonalhistogram` | `script_0000983.py` |  |
| 183 | standard_v2 | 7 | mixed | `native:reprojectlayer -> gdal:warpreproject` | `script_0000986.py` | Reproject raster and vector layers reproject raster and vector |
| 184 | standard_v2 | 1 | pure_vector | `native:multiparttosingleparts -> native:reprojectlayer` | `script_0000994.py` | POST an Overpass QL query to each mirror until one returns 2xx. overpass post |
| 185 | standard_v2 | 2 | pure_vector | `native:selectbylocation -> native:reprojectlayer` | `script_0000996.py` | car_PrepareCarKml |
| 186 | standard_v2 | 1 | mixed | `native:reclassifybytable -> native:reprojectlayer` | `script_0000997.py` | progress callback |
| 187 | standard_v2 | 3 | mixed | `gdal:cliprasterbyextent -> gdal:warpreproject -> native:reprojectlayer -> gdal:warpreproject` | `script_0000999.py` | get shapefile as json pyqgis |
| 188 | standard_v2 | 2 | mixed | `native:reprojectlayer -> gdal:rasterize -> gdal:cliprasterbyextent` | `script_0001000.py` | generate_tiles.py load config |
| 189 | standard_v2 | 3 | mixed | `gdal:warpreproject -> native:reprojectlayer -> gdal:cliprasterbymasklayer` | `script_0001002.py` | some utils func with qgis sauce reproject raster |
| 190 | standard_v2 | 2 | mixed | `gdal:buildvirtualraster -> native:reprojectlayer` | `script_0001003.py` | init |
| 191 | standard_v2 | 3 | mixed | `gdal:rasterize -> gdal:warpreproject -> gdal:rastercalculator -> gdal:cliprasterbymasklayer` | `script_0001027.py` | init |
| 192 | workflow | 7 | mixed | `native:reprojectlayer -> gdal:warpreproject` | `script_0000296.py` | Dialog class for visualizing and comparing original GIS data with field data from AMRUT fi |
| 193 | workflow | 12 | pure_vector | `native:dissolve -> native:fieldcalculator -> native:intersection -> native:dissolve -> gdal:rasterize -> native:zonalstatisticsfb -> native:zonalstatisticsfb` | `script_0000691.py` | init |
| 194 | workflow | 14 | pure_vector | `native:fixgeometries -> native:zonalstatisticsfb` | `script_0000702.py` |  |
| 195 | workflow | 3 | mixed | `gdal:rastercalculator -> gdal:rasterize -> gdal:rasterize -> gdal:rastercalculator` | `script_0000893.py` | initAlgorithm |
| 196 | workflow | 3 | pure_vector | `native:extractbyexpression -> native:extractbyexpression -> native:fixgeometries -> native:addautoincrementalfield -> native:deletecolumn -> native:renametablefield` | `script_0000894.py` | initAlgorithm |
| 197 | workflow | 3 | mixed | `gdal:warpreproject -> gdal:rasterize -> gdal:assignprojection -> gdal:cliprasterbymasklayer -> gdal:warpreproject -> gdal:warpreproject` | `script_0000901.py` | addAdvancedParameter |
| 198 | workflow | 9 | mixed | `gdal:translate -> native:fixgeometries` | `script_0000945.py` | qgisName |
| 199 | workflow | 3 | pure_vector | `native:multiparttosingleparts -> native:reprojectlayer -> qgis:advancedpythonfieldcalculator -> native:clip -> native:multiparttosingleparts -> native:extractbyexpression -> native:symmetricaldifference -> native:multiparttosingleparts` | `script_0001184.py` | init |
| 200 | workflow | 3 | pure_vector | `native:removenullgeometries -> native:reprojectlayer` | `script_0001233.py` | initAlgorithm |
| 201 | workflow | 3 | mixed | `gdal:polygonize -> gdal:polygonize -> native:clip -> gdal:polygonize -> native:buffer -> native:clip -> native:buffer -> native:buffer -> native:buffer -> native:dissolve -> native:clip` | `script_0001280.py` | to avoid havign to use "stroke to path" which keeps crashing in inkscape buffer params |
| 202 | workflow | 21 | pure_vector | `native:reprojectlayer -> native:reprojectlayer` | `script_0001443.py` | This algorithm generates a full sidewalk network based on OSM data within a specified boun |
| 203 | workflow | 21 | pure_vector | `native:reprojectlayer -> native:reprojectlayer` | `script_0001444.py` | compat osm query bbox |
| 204 | workflow | 21 | pure_vector | `native:reprojectlayer -> native:reprojectlayer` | `script_0001445.py` | Generates protoblocks by fetching OSM street data within an input polygon, |
| 205 | workflow | 3 | pure_vector | `native:intersection -> native:intersection -> native:fixgeometries` | `script_0001545.py` | get project crs |
| 206 | workflow | 3 | mixed | `gdal:cliprasterbyextent -> gdal:warpreproject -> native:reprojectlayer -> gdal:warpreproject` | `script_0001574.py` | get shapefile as json pyqgis |
| 207 | workflow | 3 | mixed | `native:mergevectorlayers -> gdal:polygonize` | `script_0001616.py` | checkLayerPoints |
| 208 | workflow | 3 | mixed | `native:reprojectlayer -> gdal:merge -> native:slope -> native:zonalstatisticsfb` | `script_0002158.py` | init |
| 209 | workflow | 3 | pure_vector | `native:reprojectlayer -> native:savefeatures -> native:savefeatures -> native:savefeatures -> native:reprojectlayer -> native:savefeatures -> native:reprojectlayer -> native:savefeatures` | `script_0002569.py` | init |
| 210 | workflow | 3 | mixed | `native:buffer -> native:zonalstatisticsfb -> gdal:rasterize -> gdal:merge -> saga:fillsinksxxlwangliu -> gdal:warpreproject -> native:hillshade` | `script_0002622.py` |  |
| 211 | workflow | 3 | pure_vector | `native:fixgeometries -> native:savefeatures -> native:mergevectorlayers` | `script_0002669.py` | layer |
| 212 | workflow | 3 | pure_raster | `gdal:cliprasterbymasklayer -> gdal:polygonize` | `script_0002670.py` | init |
| 213 | workflow | 12 | pure_vector | `native:fixgeometries -> native:clip` | `script_0002742.py` | Fix invalid geometries in input layer and return temporary layer with valid geoms fix geom |
| 214 | workflow | 3 | pure_vector | `native:fixgeometries -> native:mergevectorlayers -> native:difference -> native:mergevectorlayers` | `script_0002769.py` | init |
| 215 | workflow | 2 | mixed | `native:reprojectlayer -> native:buffer -> gdal:cliprasterbyextent -> gdal:cliprasterbyextent -> gdal:cliprasterbyextent -> native:reprojectlayer -> gdal:clipvectorbyextent -> native:union -> native:reprojectlayer` | `script_0002885.py` | Created on Fri May 1 12:39:38 2020 optimisationCalcul |
| 216 | workflow | 3 | mixed | `native:reprojectlayer -> native:reprojectlayer -> qgis:minimumboundinggeometry -> native:selectbylocation -> gdal:translate -> gdal:translate -> gdal:assignprojection` | `script_0002895.py` | mainFunction |
| 217 | workflow | 12 | pure_vector | `native:fixgeometries -> native:clip` | `script_0002904.txt` | Fix invalid geometries in input layer and return temporary layer with valid geoms fix geom |
| 218 | workflow | 3 | mixed | `gdal:cliprasterbymasklayer -> native:clip -> native:reclassifybytable -> gdal:polygonize` | `script_0002931.py` |  |
| 219 | workflow | 3 | mixed | `native:reprojectlayer -> native:reprojectlayer -> native:reprojectlayer -> gdal:warpreproject -> native:reprojectlayer` | `script_0002947.py` | init |
| 220 | workflow | 14 | pure_vector | `native:fixgeometries -> native:zonalstatisticsfb` | `script_0002955.py` |  |
| 221 | workflow | 3 | pure_vector | `native:fixgeometries -> native:buffer -> native:difference` | `script_0003056.py` | The script defines functions that can be used in the QGIS python console to speed up the g |
| 222 | workflow | 14 | pure_vector | `native:fixgeometries -> native:zonalstatisticsfb` | `script_0003088.py` |  |
| 223 | workflow | 6 | pure_vector | `native:reprojectlayer -> native:reprojectlayer -> native:fixgeometries -> native:fixgeometries -> native:fixgeometries -> native:intersection -> native:intersection -> native:fieldcalculator -> native:fieldcalculator -> native:fieldcalculator -> native:fieldcalculator -> native:fieldcalculator -> native:fieldcalculator -> native:fieldcalculator` | `script_0003174.py` | WHEN "class_name" = 'Built-up' THEN 'Concrete' initAlgorithm |
| 224 | workflow | 6 | pure_vector | `native:reprojectlayer -> native:reprojectlayer -> native:fixgeometries -> native:fixgeometries -> native:fixgeometries -> native:intersection -> native:intersection -> native:fieldcalculator -> native:fieldcalculator -> native:fieldcalculator -> native:fieldcalculator -> native:fieldcalculator -> native:fieldcalculator -> native:fieldcalculator` | `script_0003179.py` | WHEN "class_name" = 'Built-up' THEN 'Concrete' initAlgorithm |
| 225 | workflow | 3 | pure_vector | `native:centroids -> native:reprojectlayer -> native:rastersampling` | `script_0003684.py` | initAlgorithm |
| 226 | workflow | 3 | pure_vector | `native:centroids -> native:reprojectlayer -> native:joinattributesbylocation` | `script_0003685.py` | initAlgorithm |
| 227 | workflow | 3 | mixed | `gdal:rasterize -> gdal:warpreproject -> gdal:rastercalculator -> gdal:cliprasterbymasklayer` | `script_0003781.py` | init |
| 228 | workflow | 6 | mixed | `native:buffer -> native:difference -> native:reclassifybytable -> gdal:polygonize -> native:extractbyexpression -> native:reclassifybytable -> gdal:polygonize -> native:extractbyexpression -> native:buffer -> native:difference -> native:savefeatures` | `script_0003933.py` | ================================================================================ init |
| 229 | workflow | 6 | mixed | `native:buffer -> native:difference -> native:reclassifybytable -> gdal:polygonize -> native:extractbyexpression -> native:reclassifybytable -> gdal:polygonize -> native:extractbyexpression -> native:buffer -> native:difference -> native:savefeatures` | `script_0003938.py` | ================================================================================ init |
| 230 | workflow | 3 | pure_raster | `gdal:cliprasterbymasklayer -> gdal:warpreproject -> gdal:polygonize -> gdal:hillshade` | `script_0003963.py` | Bilinear interpolation of raster value at (x, y). cleanup file |
| 231 | workflow | 3 | mixed | `gdal:polygonize -> native:extractbyexpression -> native:dissolve -> gdal:polygonize -> native:extractbyexpression -> native:fieldcalculator -> native:fieldcalculator -> native:zonalstatisticsfb -> native:zonalstatisticsfb -> native:zonalstatisticsfb -> native:fieldcalculator` | `script_0004009.py` | <h3>Analisi del Catchment</h3> name |
| 232 | workflow | 3 | mixed | `gdal:rasterize -> native:fixgeometries -> native:zonalstatisticsfb -> native:zonalhistogram` | `script_0004010.py` | Model exported as python. initAlgorithm |
| 233 | workflow | 21 | pure_vector | `native:reprojectlayer -> native:reprojectlayer` | `script_0004027.py` | 指定されたレイヤーのCRSを変換する関数（Processingツール使用） convert layer crs |
| 234 | workflow | 21 | pure_vector | `native:reprojectlayer -> native:reprojectlayer` | `script_0004044.py` | 指定された中心点、幅、角度で正方形ポリゴンを作成する create square polygon |
| 235 | workflow | 3 | pure_vector | `native:reprojectlayer -> native:extractbyexpression -> native:buffer -> native:mergevectorlayers -> native:reprojectlayer` | `script_0004045.py` | main |
| 236 | workflow | 3 | pure_raster | `native:reclassifybytable -> gdal:polygonize` | `script_0004056.py` | Aplica a simbologia categorizada no campo 'DN'. definir simbologia vetor |
| 237 | workflow | 9 | mixed | `gdal:translate -> native:fixgeometries` | `script_0004570.py` | qgisName |
| 238 | workflow | 1 | pure_vector | `native:reprojectlayer -> native:fixgeometries` | `script_0004586.py` |  |
| 239 | workflow | 3 | pure_vector | `native:fixgeometries -> native:fixgeometries -> native:intersection -> qgis:statisticsbycategories` | `script_0004614.py` |  |
| 240 | workflow | 3 | pure_vector | `native:fixgeometries -> native:dissolve -> native:dissolve -> qgis:statisticsbycategories` | `script_0004618.py` |  |
| 241 | workflow | 9 | mixed | `gdal:translate -> native:fixgeometries` | `script_0004676.py` | qgisName |
| 242 | workflow | 3 | pure_vector | `native:reprojectlayer -> native:union -> native:union -> native:reprojectlayer` | `script_0004710.py` | select nombre_esquema,nombre_capa from acervo_descripcion_1.mapa_master_vw where id in (se |
| 243 | workflow | 3 | pure_vector | `native:reprojectlayer -> native:reprojectlayer -> native:savefeatures -> native:clip` | `script_0004726.py` | Return all polygon vector layers currently loaded in the project. polygon layers |
| 244 | workflow | 3 | pure_vector | `native:fixgeometries -> native:extractbyattribute -> native:reprojectlayer -> native:refactorfields -> native:refactorfields -> native:savefeatures` | `script_0004727.py` | Model exported as python (patched). initAlgorithm |
| 245 | workflow | 14 | pure_vector | `native:fixgeometries -> native:zonalstatisticsfb` | `script_0005275.py` |  |
| 246 | workflow | 3 | mixed | `gdal:rgbtopct -> gdal:polygonize -> native:extractbyattribute -> native:fixgeometries` | `script_0005283.py` |  |
| 247 | workflow | 7 | mixed | `native:reprojectlayer -> gdal:warpreproject` | `script_0005305.py` | Simple feedback object that prints all messages to console reportError |
| 248 | workflow | 3 | pure_vector | `native:reprojectlayer -> native:extractspecificvertices -> native:extractspecificvertices` | `script_0005325.py` | initAlgorithm |
| 249 | workflow | 5 | pure_vector | `native:reprojectlayer -> gdal:rasterize` | `script_0005327.py` | get config |
| 250 | workflow | 3 | mixed | `native:extractbyattribute -> native:reprojectlayer -> gdal:cliprasterbymasklayer -> gdal:warpreproject -> gdal:cliprasterbymasklayer -> gdal:warpreproject -> gdal:fillnodata` | `script_0005344.py` | climate extraction |
| 251 | workflow | 2 | mixed | `native:extractbyattribute -> native:reprojectlayer -> gdal:cliprasterbymasklayer -> gdal:warpreproject -> native:reprojectlayer -> native:clip -> native:rastersampling -> native:rastersampling` | `script_0005345.py` | Generates random non-fire points within the BC boundary. get hotspots |
| 252 | workflow | 3 | pure_vector | `native:difference -> native:dissolve -> native:dissolve -> native:mergevectorlayers -> native:fixgeometries -> native:difference -> native:removenullgeometries -> native:fixgeometries -> native:fixgeometries -> native:union -> native:fixgeometries -> native:mergevectorlayers` | `script_0005358.py` | Apply a simple difference operation to the input layers. apply simple difference |
| 253 | workflow | 3 | mixed | `native:clip -> gdal:polygonize -> gdal:cliprasterbyextent` | `script_0005360.py` | Clip a QgsVector layer by different QgsVector layer simple clip |
| 254 | workflow | 3 | pure_vector | `native:fixgeometries -> native:fixgeometries -> native:clip` | `script_0005361.py` | Class to download and clip WFS layers, used before and during WFStask init |
| 255 | workflow | 3 | pure_vector | `native:fixgeometries -> native:reprojectlayer -> native:intersection -> native:difference -> native:intersection -> native:difference -> native:difference -> native:mergevectorlayers` | `script_0005365.py` | Remove acentos e converte para minúsculas init |
| 256 | workflow | 3 | pure_vector | `native:fixgeometries -> native:reprojectlayer -> native:difference -> native:mergevectorlayers` | `script_0005366.py` | Remove acentos e converte para minúsculas init |
| 257 | workflow | 8 | mixed | `gdal:polygonize -> native:intersection` | `script_0005386.py` | initAlgorithm |
| 258 | workflow | 3 | mixed | `native:buffer -> native:union -> native:promotetomulti -> native:polygonfromlayerextent -> gdal:clipvectorbypolygon -> gdal:rasterize -> gdal:warpreproject` | `script_0005393.py` | build water rasterized |
| 259 | workflow | 8 | mixed | `gdal:polygonize -> native:intersection` | `script_0005399.py` | prompt raster |
| 260 | workflow | 2 | mixed | `native:extractbyattribute -> native:reprojectlayer -> gdal:cliprasterbymasklayer -> gdal:warpreproject -> native:reprojectlayer -> native:clip -> native:rastersampling -> native:rastersampling` | `script_0005421.py` | Generates random non-fire points within the BC boundary. get hotspots |
| 261 | workflow | 21 | pure_vector | `native:reprojectlayer -> native:reprojectlayer` | `script_0005523.py` | Constructor. init |
| 262 | workflow | 14 | pure_vector | `native:fixgeometries -> native:zonalstatisticsfb` | `script_0005582.py` |  |
| 263 | workflow | 14 | pure_vector | `native:fixgeometries -> native:zonalstatisticsfb` | `script_0005583.py` | Calculate the height of bounding box in meters calculate centroid |
| 264 | workflow | 2 | mixed | `gdal:buildvirtualraster -> native:reprojectlayer` | `script_0005589.py` | init |
| 265 | workflow | 4 | mixed | `gdal:rasterize -> gdal:polygonize` | `script_0005621.txt` | getBboxWmsFormat |
| 266 | workflow | 2 | pure_raster | `gdal:polygonize -> gdal:polygonize` | `script_0005627.py` | transfrom input buffer zone raster to vector raster2vector |
| 267 | workflow | 3 | pure_vector | `native:fixgeometries -> native:fixgeometries -> native:fixgeometries -> native:mergevectorlayers -> native:dissolve` | `script_0005629.py` | This makes parameters for wfs-request of specific area getBboxWmsFormat |
| 268 | workflow | 1 | mixed | `gdal:polygonize -> native:extractbyexpression -> native:fixgeometries` | `script_0005693.py` | initialize processing |
| 269 | workflow | 7 | pure_vector | `native:reprojectlayer -> native:buffer -> native:clip` | `script_0005754.txt` |  |
| 270 | workflow | 7 | pure_vector | `native:reprojectlayer -> native:buffer -> native:clip` | `script_0005756.py` | PyQGIS Code Snippets |
| 271 | workflow | 6 | mixed | `native:buffer -> native:clip -> gdal:rasterize -> gdal:warpreproject -> gdal:rastercalculator` | `script_0005798.py` | 📦 Opportunities Mask Processor module. init |
| 272 | workflow | 6 | pure_vector | `native:fixgeometries -> native:retainfields -> native:zonalstatisticsfb` | `script_0005801.py` | 📦 Subnational Aggregation Processor module. init |
| 273 | workflow | 6 | mixed | `gdal:assignprojection -> native:assignprojection -> native:extractbyextent -> native:fixgeometries -> native:reprojectlayer -> gdal:buildvirtualraster` | `script_0005802.py` | 📦 Utilities module. assign crs to raster layer |
| 274 | workflow | 6 | pure_vector | `native:reprojectlayer -> native:clip` | `script_0005804.py` | 📦 Osm Data Downloader Base module. init |
| 275 | workflow | 3 | pure_vector | `native:reprojectlayer -> native:clip -> native:buffer -> native:dissolve -> native:difference -> native:mergevectorlayers` | `script_0005817.py` | Multi-buffer distances workflow using native QGIS network analysis. init |
| 276 | workflow | 6 | pure_vector | `native:mergevectorlayers -> native:dissolve -> native:difference -> native:mergevectorlayers -> native:reprojectlayer` | `script_0005818.py` | 📦 Multi Buffer Distances Ors Workflow module. init |
| 277 | workflow | 6 | mixed | `gdal:warpreproject -> native:fillnodata -> gdal:rasterize -> gdal:cliprasterbymasklayer` | `script_0005824.py` | 📦 Workflow Base module. init |
| 278 | workflow | 3 | pure_vector | `native:reprojectlayer -> native:buffer` | `script_0005844.py` | initAlgorithm |
| 279 | workflow | 6 | pure_vector | `native:reprojectlayer -> native:extractbyexpression` | `script_0005861.py` | reproject layer if needed |
| 280 | workflow | 3 | pure_vector | `native:reprojectlayer -> native:buffer -> native:difference -> native:multiparttosingleparts` | `script_0005875.py` |  |
| 281 | workflow | 3 | pure_vector | `qgis:checkvalidity -> native:fixgeometries -> qgis:checkvalidity -> native:fixgeometries` | `script_0005876.py` |  |
| 282 | workflow | 3 | mixed | `native:reprojectlayer -> native:buffer -> gdal:cliprasterbymasklayer -> gdal:warpreproject` | `script_0005903.py` | init |
| 283 | workflow | 3 | pure_vector | `gdal:rasterize -> native:fieldcalculator -> gdal:rasterize` | `script_0005909.py` | initAlgorithm |
| 284 | workflow | 3 | pure_vector | `native:fixgeometries -> native:fixgeometries -> native:fixgeometries -> native:clip -> native:clip` | `script_0005925.py` | Model exported as python. initAlgorithm |
| 285 | workflow | 6 | pure_vector | `native:reprojectlayer -> native:extractbyexpression` | `script_0005933.py` |  |
| 286 | workflow | 3 | pure_vector | `native:fixgeometries -> native:clip -> native:clip -> native:buffer -> native:extractbylocation -> native:countpointsinpolygon` | `script_0005934.py` |  |
| 287 | workflow | 3 | mixed | `gdal:polygonize -> native:buffer -> gdal:rasterize` | `script_0005935.py` |  |
| 288 | workflow | 3 | pure_vector | `native:fixgeometries -> native:buffer -> native:intersection` | `script_0005989.py` |  |
| 289 | workflow | 6 | mixed | `native:buffer -> native:clip -> gdal:rasterize -> gdal:warpreproject -> gdal:rastercalculator` | `script_0006032.py` | A QgsTask subclass for generating job opportunity mask layers. init |
| 290 | workflow | 6 | pure_vector | `native:fixgeometries -> native:retainfields -> native:zonalstatisticsfb` | `script_0006035.py` | A QgsTask subclass for calculating WEE x Population SCORE and or WEE score per aggregation |
| 291 | workflow | 6 | mixed | `gdal:assignprojection -> native:assignprojection -> native:extractbyextent -> native:fixgeometries -> native:reprojectlayer -> gdal:buildvirtualraster` | `script_0006036.py` | Assigns a CRS to a layer and returns the layer. assign crs to raster layer |
| 292 | workflow | 6 | pure_vector | `native:mergevectorlayers -> native:dissolve -> native:difference -> native:mergevectorlayers -> native:reprojectlayer` | `script_0006042.py` | Concrete implementation of a 'multi_buffer_distances' workflow. init |
| 293 | workflow | 6 | mixed | `gdal:warpreproject -> native:fillnodata -> gdal:rasterize -> gdal:cliprasterbymasklayer` | `script_0006048.py` | Abstract base class for all workflows. init |
| 294 | workflow | 3 | pure_vector | `native:reprojectlayer -> native:reprojectlayer -> native:buffer -> native:clip -> native:fieldcalculator` | `script_0006058.py` | Vector Geoprocessing — PyQGIS Processing Script |
| 295 | workflow | 2 | pure_vector | `native:fixgeometries -> native:fixgeometries -> native:fixgeometries -> native:fixgeometries -> native:fixgeometries` | `script_0006060.py` | Modulo: AyudasGEO RegisterFunction |
| 296 | workflow | 7 | pure_vector | `native:reprojectlayer -> native:intersection` | `script_0006107.py` | init |
| 297 | workflow | 3 | pure_vector | `native:dissolve -> native:multiparttosingleparts -> native:buffer -> native:dissolve -> native:dissolve -> native:reprojectlayer -> qgis:checkvalidity` | `script_0006108.py` | init |
| 298 | workflow | 21 | pure_vector | `native:reprojectlayer -> native:reprojectlayer` | `script_0006174.py` | Convertit un objet QColor en hexadécimal #RRGGBB init |
| 299 | workflow | 3 | mixed | `gdal:warpreproject -> saga:fillsinksxxlwangliu -> native:zonalstatistics -> native:zonalstatistics -> gdal:cliprasterbyextent -> native:fixgeometries -> native:buffer -> native:clip -> native:clip -> gdal:polygonize -> native:zonalstatistics -> native:zonalstatistics` | `script_0006181.py` | HydroAnalysis.py - Module d'analyse hydrologique pour SigLogix (QGIS) init |
| 300 | workflow | 3 | mixed | `qgis:rastercalculator -> gdal:polygonize -> native:buffer -> gdal:cliprasterbymasklayer` | `script_0006207.py` | Model exported as python. initAlgorithm |
| 301 | workflow | 3 | mixed | `native:extractbylocation -> gdal:rasterize -> gdal:cliprasterbymasklayer` | `script_0006209.py` | Model exported as python. initAlgorithm |
| 302 | workflow | 5 | pure_vector | `native:fixgeometries -> native:dissolve` | `script_0006290.py` | init |
| 303 | workflow | 3 | pure_vector | `native:fixgeometries -> native:joinattributesbylocation -> native:reprojectlayer -> native:extractbyexpression -> native:dissolve` | `script_0006313.py` | shortHelpString |
| 304 | workflow | 4 | mixed | `gdal:cliprasterbymasklayer -> gdal:cliprasterbymasklayer -> native:reprojectlayer` | `script_0006340.py` | initAlgorithm |
| 305 | workflow | 21 | pure_vector | `native:reprojectlayer -> native:reprojectlayer` | `script_0006383.py` | all polygons intersecting fGetExtentPolygonCoords |
| 306 | workflow | 21 | pure_vector | `native:reprojectlayer -> native:reprojectlayer` | `script_0006384.py` | Normalize product version into table suffix format. fGetExtentPolygonCoords |
| 307 | workflow | 3 | pure_vector | `native:mergevectorlayers -> native:reprojectlayer` | `script_0006477.py` | editAttribute |
| 308 | workflow | 3 | pure_vector | `native:reprojectlayer -> native:reprojectlayer -> native:reprojectlayer -> native:buffer -> qgis:joinbylocationsummary -> native:buffer -> qgis:joinbylocationsummary -> native:fieldcalculator -> native:dbscanclustering -> native:reprojectlayer -> native:reprojectlayer` | `script_0006490.py` | Sample 01: Utility Outage Prioritization load layer |
| 309 | workflow | 3 | pure_vector | `native:reprojectlayer -> native:reprojectlayer -> native:reprojectlayer -> native:buffer -> qgis:joinbylocationsummary -> qgis:joinbylocationsummary -> native:fieldcalculator -> native:reprojectlayer` | `script_0006491.py` | Sample 02: Right-of-Way Vegetation + Flood Risk load layer |
| 310 | workflow | 3 | pure_vector | `native:refactorfields -> native:fixgeometries` | `script_0006561.py` | create table |
| 311 | workflow | 3 | pure_vector | `native:reprojectlayer -> native:renametablefield -> native:retainfields` | `script_0006565.py` | parse time interval |
| 312 | workflow | 3 | pure_vector | `native:reprojectlayer -> native:retainfields` | `script_0006566.py` | parse time interval |
| 313 | workflow | 3 | pure_vector | `native:difference -> native:buffer -> native:clip -> native:fixgeometries -> native:mergevectorlayers -> native:reprojectlayer` | `script_0006567.py` | config |
| 314 | workflow | 3 | pure_vector | `native:reprojectlayer -> native:dissolve -> native:buffer -> native:reprojectlayer -> native:intersection -> native:fixgeometries` | `script_0006570.py` |  |
| 315 | workflow | 3 | pure_vector | `native:reprojectlayer -> native:joinattributesbylocation -> native:multiintersection` | `script_0006594.py` | Quite specific to the French case. Add a boolean attribute, for every building of a vector |
| 316 | workflow | 21 | pure_vector | `native:reprojectlayer -> native:reprojectlayer` | `script_0006681.py` | init |
| 317 | workflow | 4 | pure_vector | `native:fixgeometries -> native:fixgeometries -> native:fixgeometries` | `script_0006739.py` |  |
| 318 | workflow | 3 | mixed | `native:reprojectlayer -> native:clip -> native:fixgeometries -> native:clip -> native:clip -> native:fixgeometries -> native:clip -> native:reprojectlayer -> gdal:cliprasterbymasklayer -> gdal:polygonize -> native:addfieldtoattributestable -> native:mergevectorlayers -> native:reprojectlayer -> native:reprojectlayer` | `script_0006757.py` | enable logging |
| 319 | workflow | 3 | pure_vector | `native:extractbyexpression -> native:intersection -> native:intersection -> native:dissolve -> native:dissolve -> native:refactorfields -> native:fixgeometries -> native:refactorfields -> native:fixgeometries -> native:promotetomulti -> native:promotetomulti -> native:dissolve -> native:dissolve -> native:refactorfields -> native:refactorfields` | `script_0006816.py` | Model exported as python. initAlgorithm |
| 320 | workflow | 3 | pure_vector | `native:refactorfields -> native:refactorfields -> native:extractbyattribute -> native:extractbyattribute -> native:fixgeometries -> native:fixgeometries -> native:mergevectorlayers -> native:refactorfields -> native:dissolve -> native:refactorfields` | `script_0006819.py` | Model exported as python. initAlgorithm |
| 321 | workflow | 3 | pure_vector | `native:reprojectlayer -> native:clip -> native:reprojectlayer` | `script_0006843.py` | Download features from an ArcGIS Feature/MapServer layer using paged requests, return Feat |
| 322 | workflow | 3 | pure_vector | `native:reprojectlayer -> native:mergevectorlayers -> native:clip` | `script_0006844.py` | load road layer |
| 323 | workflow | 6 | pure_vector | `native:reprojectlayer -> native:clip` | `script_0006845.py` |  |
| 324 | workflow | 3 | mixed | `native:extractbyextent -> native:fixgeometries -> native:clip -> native:reprojectlayer -> gdal:rasterize -> gdal:warpreproject -> native:savefeatures -> native:reprojectlayer -> native:fixgeometries -> native:clip -> native:multiparttosingleparts -> native:reprojectlayer` | `script_0006846.py` | Dialog for filtering vector layer features by attribute values. init |
| 325 | workflow | 66 | mixed | `native:reclassifybytable -> native:reclassifybytable -> native:reclassifybytable -> gdal:polygonize -> native:zonalstatisticsfb` | `script_0006940.py` | Module 7: Market Classification & Zoning |
| 326 | workflow | 66 | mixed | `native:reclassifybytable -> native:reclassifybytable -> native:reclassifybytable -> gdal:polygonize -> native:zonalstatisticsfb` | `script_0006941.py` | Module 7: Market Classification & Zoning |
| 327 | workflow | 66 | mixed | `native:reclassifybytable -> native:reclassifybytable -> native:reclassifybytable -> gdal:polygonize -> native:zonalstatisticsfb` | `script_0006942.py` | Module 7: Market Classification & Zoning |
| 328 | workflow | 66 | mixed | `native:reclassifybytable -> native:reclassifybytable -> native:reclassifybytable -> gdal:polygonize -> native:zonalstatisticsfb` | `script_0006943.py` | Module 7: Market Classification & Zoning |
| 329 | workflow | 66 | mixed | `native:reclassifybytable -> native:reclassifybytable -> native:reclassifybytable -> gdal:polygonize -> native:zonalstatisticsfb` | `script_0006944.py` | Module 7: Market Classification & Zoning |
| 330 | workflow | 66 | mixed | `native:reclassifybytable -> native:reclassifybytable -> native:reclassifybytable -> gdal:polygonize -> native:zonalstatisticsfb` | `script_0006945.py` | Module 7: Market Classification & Zoning |
| 331 | workflow | 66 | mixed | `native:reclassifybytable -> native:reclassifybytable -> native:reclassifybytable -> gdal:polygonize -> native:zonalstatisticsfb` | `script_0006946.py` | Module 7: Market Classification & Zoning |
| 332 | workflow | 66 | mixed | `native:reclassifybytable -> native:reclassifybytable -> native:reclassifybytable -> gdal:polygonize -> native:zonalstatisticsfb` | `script_0006947.py` | Module 7: Market Classification & Zoning |
| 333 | workflow | 66 | mixed | `native:reclassifybytable -> native:reclassifybytable -> native:reclassifybytable -> gdal:polygonize -> native:zonalstatisticsfb` | `script_0006948.py` | Module 7: Market Classification & Zoning |
| 334 | workflow | 66 | mixed | `native:reclassifybytable -> native:reclassifybytable -> native:reclassifybytable -> gdal:polygonize -> native:zonalstatisticsfb` | `script_0006949.py` | Module 7: Market Classification & Zoning |
| 335 | workflow | 66 | mixed | `native:reclassifybytable -> native:reclassifybytable -> native:reclassifybytable -> gdal:polygonize -> native:zonalstatisticsfb` | `script_0006950.py` | Module 7: Market Classification & Zoning |
| 336 | workflow | 66 | mixed | `native:reclassifybytable -> native:reclassifybytable -> native:reclassifybytable -> gdal:polygonize -> native:zonalstatisticsfb` | `script_0006951.py` | Module 7: Market Classification & Zoning |
| 337 | workflow | 66 | mixed | `native:reclassifybytable -> native:reclassifybytable -> native:reclassifybytable -> gdal:polygonize -> native:zonalstatisticsfb` | `script_0006952.py` | Module 7: Market Classification & Zoning |
| 338 | workflow | 66 | mixed | `native:reclassifybytable -> native:reclassifybytable -> native:reclassifybytable -> gdal:polygonize -> native:zonalstatisticsfb` | `script_0006953.py` | Module 7: Market Classification & Zoning |
| 339 | workflow | 66 | mixed | `native:reclassifybytable -> native:reclassifybytable -> native:reclassifybytable -> gdal:polygonize -> native:zonalstatisticsfb` | `script_0006954.py` | Module 7: Market Classification & Zoning |
| 340 | workflow | 66 | mixed | `native:reclassifybytable -> native:reclassifybytable -> native:reclassifybytable -> gdal:polygonize -> native:zonalstatisticsfb` | `script_0006955.py` | Module 7: Market Classification & Zoning |
| 341 | workflow | 66 | mixed | `native:reclassifybytable -> native:reclassifybytable -> native:reclassifybytable -> gdal:polygonize -> native:zonalstatisticsfb` | `script_0006956.py` | Module 7: Market Classification & Zoning |
| 342 | workflow | 66 | mixed | `native:reclassifybytable -> native:reclassifybytable -> native:reclassifybytable -> gdal:polygonize -> native:zonalstatisticsfb` | `script_0006957.py` | Module 7: Market Classification & Zoning |
| 343 | workflow | 66 | mixed | `native:reclassifybytable -> native:reclassifybytable -> native:reclassifybytable -> gdal:polygonize -> native:zonalstatisticsfb` | `script_0006958.py` | Module 7: Market Classification & Zoning |
| 344 | workflow | 66 | mixed | `native:reclassifybytable -> native:reclassifybytable -> native:reclassifybytable -> gdal:polygonize -> native:zonalstatisticsfb` | `script_0006959.py` | Module 7: Market Classification & Zoning |
| 345 | workflow | 66 | mixed | `native:reclassifybytable -> native:reclassifybytable -> native:reclassifybytable -> gdal:polygonize -> native:zonalstatisticsfb` | `script_0006960.py` | Module 7: Market Classification & Zoning |
| 346 | workflow | 66 | mixed | `native:reclassifybytable -> native:reclassifybytable -> native:reclassifybytable -> gdal:polygonize -> native:zonalstatisticsfb` | `script_0006961.py` | Module 7: Market Classification & Zoning |
| 347 | workflow | 12 | pure_vector | `native:fixgeometries -> native:clip` | `script_0006997.py` | Model exported as python. initAlgorithm |
| 348 | workflow | 3 | pure_vector | `native:fixgeometries -> native:multiparttosingleparts -> native:clip -> native:extractbyexpression` | `script_0007005.py` | Fixes the geometries of a shapefile and saves the fixed version. fix geometries |
| 349 | workflow | 12 | pure_vector | `native:fixgeometries -> native:clip` | `script_0007031.py` | Fix invalid geometries in input layer and return temporary layer with valid geoms addlayer |
| 350 | workflow | 3 | mixed | `native:reprojectlayer -> gdal:cliprasterbymasklayer -> gdal:cliprasterbyextent -> gdal:translate -> gdal:warpreproject -> gdal:rastercalculator` | `script_0007059.py` | Calculates the Curve Number using global datasets from ESA WorldCover and ORNL HYSOG. init |
| 351 | workflow | 21 | pure_vector | `native:reprojectlayer -> native:reprojectlayer` | `script_0007072.py` | initAlgorithm |
| 352 | workflow | 3 | mixed | `native:reprojectlayer -> native:clip -> native:reprojectlayer -> gdal:cliprasterbymasklayer` | `script_0007092.py` |  |
| 353 | workflow | 1 | pure_vector | `native:clip -> native:fixgeometries -> native:savefeatures` | `script_0007095.py` | init |
| 354 | workflow | 3 | pure_vector | `native:extractbyexpression -> native:intersection -> native:dissolve -> native:retainfields -> native:reprojectlayer -> native:fieldcalculator -> native:savefeatures` | `script_0007112.py` | Script using pyqgis |
| 355 | workflow | 2 | pure_vector | `native:fixgeometries -> native:dissolve -> native:mergevectorlayers` | `script_0007119.py` | file ext search |
| 356 | workflow | 2 | pure_vector | `native:dissolve -> native:fixgeometries -> native:dissolve -> native:promotetomulti` | `script_0007126.py` | init |
| 357 | workflow | 2 | pure_vector | `native:fixgeometries -> native:dissolve -> native:polygonize` | `script_0007127.py` | SolarPanelGenerator Plugin Coverage Logic init |
| 358 | workflow | 5 | pure_vector | `native:fixgeometries -> native:dissolve` | `script_0007134.py` | initAlgorithm |
| 359 | workflow | 2 | mixed | `gdal:rasterize -> gdal:merge` | `script_0007136.py` | initAlgorithm |
| 360 | workflow | 3 | pure_vector | `native:fixgeometries -> native:dissolve -> native:buffer -> native:extractbylocation` | `script_0007142.py` |  |
| 361 | workflow | 4 | pure_vector | `native:fixgeometries -> native:fixgeometries -> native:fixgeometries` | `script_0007154.py` | select apex model |
| 362 | workflow | 3 | pure_vector | `native:fixgeometries -> native:dissolve -> native:reprojectlayer` | `script_0007190.py` | init |
| 363 | workflow | 12 | pure_vector | `native:dissolve -> native:fieldcalculator -> native:intersection -> native:dissolve -> gdal:rasterize -> native:zonalstatisticsfb -> native:zonalstatisticsfb` | `script_0007204.py` | init |
| 364 | workflow | 12 | pure_vector | `native:dissolve -> native:fieldcalculator -> native:intersection -> native:dissolve -> gdal:rasterize -> native:zonalstatisticsfb -> native:zonalstatisticsfb` | `script_0007205.py` | init |
| 365 | workflow | 12 | pure_vector | `native:dissolve -> native:fieldcalculator -> native:intersection -> native:dissolve -> gdal:rasterize -> native:zonalstatisticsfb -> native:zonalstatisticsfb` | `script_0007227.py` | init |
| 366 | workflow | 4 | mixed | `gdal:polygonize -> native:dissolve` | `script_0007228.py` | init |
| 367 | workflow | 4 | mixed | `gdal:polygonize -> native:dissolve` | `script_0007232.py` | read ASCII |
| 368 | workflow | 2 | mixed | `qgis:rastercalculator -> gdal:polygonize -> native:dissolve` | `script_0007273.py` | 1. Находит в проекте растр по имени `raster_name`. create single polygon per color |
| 369 | workflow | 7 | mixed | `native:reprojectlayer -> gdal:warpreproject` | `script_0007476.py` | Reproject raster and vector layers reproject raster and vector |
| 370 | workflow | 3 | mixed | `gdal:warpreproject -> native:reclassifybytable -> gdal:polygonize -> native:fixgeometries -> native:zonalstatisticsfb -> native:fieldcalculator -> native:extractbyexpression -> native:fieldcalculator -> native:centroids` | `script_0007489.py` | Automated Keyline Keypoint Detection Algorithm |
| 371 | workflow | 1 | mixed | `gdal:rasterize -> gdal:cliprasterbymasklayer -> gdal:warpreproject -> native:reprojectlayer` | `script_0007497.py` | init |
| 372 | workflow | 3 | mixed | `native:savefeatures -> gdal:translate -> native:reprojectlayer -> gdal:warpreproject -> gdal:rasterize -> native:fixgeometries -> native:union -> native:rastersampling -> native:rastersampling -> native:savefeatures` | `script_0007523.py` | init |
| 373 | workflow | 3 | mixed | `gdal:warpreproject -> native:reprojectlayer -> gdal:cliprasterbymasklayer` | `script_0007543.py` | some utils func with qgis sauce reproject raster |
| 374 | workflow | 6 | mixed | `native:reprojectlayer -> gdal:cliprasterbymasklayer` | `script_0007563.py` | Create a new print layout and remove any previous layout with the same name. create layout |
| 375 | workflow | 6 | mixed | `native:reprojectlayer -> gdal:cliprasterbymasklayer` | `script_0007564.py` | Create a new print layout and remove any previous layout with the same name. create layout |
| 376 | workflow | 2 | mixed | `gdal:polygonize -> native:extractbyattribute -> gdal:cliprasterbymasklayer` | `script_0007653.py` | Black Frame Remover: main.py v1.1.0 init |
| 377 | workflow | 3 | mixed | `native:translategeometry -> gdal:rasterize -> gdal:cliprasterbymasklayer` | `script_0007670.py` | init |
| 378 | workflow | 9 | mixed | `gdal:translate -> native:reprojectlayer` | `script_0007701.py` |  |
| 379 | workflow | 9 | mixed | `gdal:translate -> native:reprojectlayer` | `script_0007702.py` |  |
| 380 | workflow | 9 | mixed | `gdal:translate -> native:reprojectlayer` | `script_0007703.py` |  |
| 381 | workflow | 3 | mixed | `gdal:polygonize -> native:joinattributesbylocation -> native:joinattributesbylocation` | `script_0007727.py` |  |
| 382 | workflow | 9 | pure_raster | `saga:upslopearea -> gdal:polygonize` | `script_0007753.py` | initAlgorithm |
| 383 | workflow | 9 | pure_raster | `saga:upslopearea -> gdal:polygonize` | `script_0007754.py` |  |
| 384 | workflow | 9 | pure_raster | `saga:upslopearea -> gdal:polygonize` | `script_0007795.py` |  |
| 385 | workflow | 3 | pure_vector | `native:reprojectlayer -> native:rastersampling -> native:zonalstatisticsfb -> native:reprojectlayer -> native:savefeatures` | `script_0007943.py` | v0.2 2024-09-03 rainfall factor |
| 386 | workflow | 1 | pure_vector | `native:reprojectlayer -> native:reprojectlayer -> native:reprojectlayer` | `script_0007951.py` | initAlgorithm |
| 387 | workflow | 12 | pure_vector | `native:reprojectlayer -> native:multiparttosingleparts` | `script_0008064.py` | Author: Mario Königbauer (mkoenigb@gmx.de) initAlgorithm |
| 388 | workflow | 3 | pure_vector | `native:reprojectlayer -> native:extractvertices -> native:multiparttosingleparts` | `script_0008065.py` | Author: Mario Königbauer (mkoenigb@gmx.de) initAlgorithm |
| 389 | workflow | 3 | pure_vector | `native:reprojectlayer -> native:centroids` | `script_0008066.py` | Author: Mario Königbauer (mkoenigb@gmx.de) initAlgorithm |
| 390 | workflow | 12 | pure_vector | `native:reprojectlayer -> native:multiparttosingleparts` | `script_0008068.py` | Author: Mario Königbauer (mkoenigb@gmx.de) initAlgorithm |
| 391 | workflow | 12 | pure_vector | `native:reprojectlayer -> native:multiparttosingleparts` | `script_0008069.py` | Author: Mario Königbauer (mkoenigb@gmx.de) initAlgorithm |
| 392 | workflow | 12 | pure_vector | `native:reprojectlayer -> native:multiparttosingleparts` | `script_0008071.py` | Author: Mario Königbauer (mkoenigb@gmx.de) initAlgorithm |
| 393 | workflow | 3 | pure_vector | `native:reprojectlayer -> native:fixgeometries -> native:intersection -> native:extractbylocation` | `script_0008086.py` |  |
| 394 | workflow | 2 | mixed | `gdal:rasterize -> gdal:translate` | `script_0008220.py` | Create binary masks from selected vector layers, based on a single chosen DTM tile extent, |
| 395 | workflow_A | 1 | pure_vector | `gdal:rasterize -> gdal:rasterize` | `script_0000022.py` | initAlgorithm |
| 396 | workflow_A | 3 | mixed | `native:reprojectlayer -> native:buffer -> gdal:cliprasterbymasklayer -> gdal:warpreproject` | `script_0000056.py` | init |
| 397 | workflow_A | 3 | pure_vector | `gdal:rasterize -> native:fieldcalculator -> gdal:rasterize` | `script_0000062.py` | initAlgorithm |
| 398 | workflow_A | 2 | mixed | `native:reprojectlayer -> native:buffer -> gdal:cliprasterbyextent -> gdal:cliprasterbyextent -> gdal:cliprasterbyextent -> native:reprojectlayer -> gdal:clipvectorbyextent -> native:union -> native:reprojectlayer` | `script_0000334.py` | Created on Fri May 1 12:39:38 2020 optimisationCalcul |
| 399 | workflow_A | 1 | mixed | `gdal:warpreproject -> native:slope -> gdal:rastercalculator -> gdal:polygonize -> native:extractbyattribute -> native:clip` | `script_0000531.py` | initAlgorithm |
| 400 | workflow_A | 3 | pure_vector | `native:reprojectlayer -> native:dissolve -> native:buffer -> native:reprojectlayer -> native:intersection -> native:fixgeometries` | `script_0000532.py` |  |
| 401 | workflow_A | 3 | mixed | `gdal:polygonize -> native:extractbyexpression -> native:dissolve -> gdal:polygonize -> native:extractbyexpression -> native:fieldcalculator -> native:fieldcalculator -> native:zonalstatisticsfb -> native:zonalstatisticsfb -> native:zonalstatisticsfb -> native:fieldcalculator` | `script_0000581.py` | <h3>Analisi del Catchment</h3> name |
| 402 | workflow_A | 3 | mixed | `gdal:rasterize -> native:fixgeometries -> native:zonalstatisticsfb -> native:zonalhistogram` | `script_0000582.py` | Model exported as python. initAlgorithm |
| 403 | workflow_A | 3 | pure_vector | `native:fixgeometries -> native:joinattributesbylocation -> native:reprojectlayer -> native:extractbyexpression -> native:dissolve` | `script_0000621.py` | shortHelpString |
| 404 | workflow_A | 6 | pure_vector | `native:reprojectlayer -> native:reprojectlayer -> native:fixgeometries -> native:fixgeometries -> native:fixgeometries -> native:intersection -> native:intersection -> native:fieldcalculator -> native:fieldcalculator -> native:fieldcalculator -> native:fieldcalculator -> native:fieldcalculator -> native:fieldcalculator -> native:fieldcalculator` | `script_0000698.py` | WHEN "class_name" = 'Built-up' THEN 'Concrete' initAlgorithm |
| 405 | workflow_A | 6 | pure_vector | `native:reprojectlayer -> native:reprojectlayer -> native:fixgeometries -> native:fixgeometries -> native:fixgeometries -> native:intersection -> native:intersection -> native:fieldcalculator -> native:fieldcalculator -> native:fieldcalculator -> native:fieldcalculator -> native:fieldcalculator -> native:fieldcalculator -> native:fieldcalculator` | `script_0000703.py` | WHEN "class_name" = 'Built-up' THEN 'Concrete' initAlgorithm |
| 406 | workflow_A | 4 | mixed | `gdal:cliprasterbymasklayer -> gdal:cliprasterbymasklayer -> native:reprojectlayer` | `script_0000728.py` | initAlgorithm |
| 407 | workflow_A | 3 | pure_vector | `native:reprojectlayer -> native:fixgeometries -> native:intersection -> native:extractbylocation` | `script_0000769.py` |  |
| 408 | workflow_A | 6 | pure_vector | `native:reprojectlayer -> native:extractbyexpression` | `script_0001073.py` | reproject layer if needed |
| 409 | workflow_A | 3 | mixed | `qgis:rastercalculator -> gdal:polygonize -> native:buffer -> gdal:cliprasterbymasklayer` | `script_0001089.py` | Model exported as python. initAlgorithm |
| 410 | workflow_A | 3 | mixed | `native:extractbylocation -> gdal:rasterize -> gdal:cliprasterbymasklayer` | `script_0001093.py` | Model exported as python. initAlgorithm |
| 411 | workflow_A | 12 | pure_vector | `native:fixgeometries -> native:clip` | `script_0001245.txt` | Fix invalid geometries in input layer and return temporary layer with valid geoms fix geom |
| 412 | workflow_A | 3 | pure_vector | `native:multiparttosingleparts -> native:reprojectlayer -> qgis:advancedpythonfieldcalculator -> native:clip -> native:multiparttosingleparts -> native:extractbyexpression -> native:symmetricaldifference -> native:multiparttosingleparts` | `script_0001409.py` | init |
| 413 | workflow_A | 3 | pure_vector | `native:removenullgeometries -> native:reprojectlayer` | `script_0001461.py` | initAlgorithm |
| 414 | workflow_A | 12 | pure_vector | `native:reprojectlayer -> native:multiparttosingleparts` | `script_0001518.py` | Author: Mario Königbauer (mkoenigb@gmx.de) initAlgorithm |
| 415 | workflow_A | 3 | pure_vector | `native:reprojectlayer -> native:extractvertices -> native:multiparttosingleparts` | `script_0001519.py` | Author: Mario Königbauer (mkoenigb@gmx.de) initAlgorithm |
| 416 | workflow_A | 3 | pure_vector | `native:reprojectlayer -> native:centroids` | `script_0001520.py` | Author: Mario Königbauer (mkoenigb@gmx.de) initAlgorithm |
| 417 | workflow_A | 12 | pure_vector | `native:reprojectlayer -> native:multiparttosingleparts` | `script_0001523.py` | Author: Mario Königbauer (mkoenigb@gmx.de) initAlgorithm |
| 418 | workflow_A | 12 | pure_vector | `native:reprojectlayer -> native:multiparttosingleparts` | `script_0001524.py` | Author: Mario Königbauer (mkoenigb@gmx.de) initAlgorithm |
| 419 | workflow_A | 12 | pure_vector | `native:reprojectlayer -> native:multiparttosingleparts` | `script_0001526.py` | Author: Mario Königbauer (mkoenigb@gmx.de) initAlgorithm |
| 420 | workflow_A | 4 | mixed | `gdal:rasterize -> gdal:polygonize` | `script_0001678.txt` | getBboxWmsFormat |
| 421 | workflow_A | 7 | pure_vector | `native:reprojectlayer -> native:buffer -> native:clip` | `script_0002065.txt` |  |
| 422 | workflow_A | 3 | pure_vector | `native:reprojectlayer -> native:extractspecificvertices -> native:extractspecificvertices` | `script_0002358.py` | processAlgorithm |
| 423 | workflow_A | 5 | pure_vector | `native:reprojectlayer -> gdal:rasterize` | `script_0002360.py` | processAlgorithm |
| 424 | workflow_A | 3 | pure_vector | `native:centroids -> native:reprojectlayer -> native:rastersampling` | `script_0002364.py` | processAlgorithm |
| 425 | workflow_A | 3 | pure_vector | `native:centroids -> native:reprojectlayer -> native:joinattributesbylocation` | `script_0002365.py` | processAlgorithm |
| 426 | workflow_A | 3 | pure_vector | `native:reprojectlayer -> native:buffer` | `script_0002410.py` | processAlgorithm |
| 427 | workflow_A | 3 | pure_vector | `native:reprojectlayer -> native:rastersampling -> native:zonalstatisticsfb -> native:reprojectlayer -> native:savefeatures` | `script_0002428.py` | v0.2 2024-09-03 processAlgorithm |
| 428 | workflow_A | 4 | pure_vector | `native:union -> native:multiparttosingleparts -> native:fixgeometries -> native:multiparttosingleparts -> native:reprojectlayer` | `script_0002631.py` | Decorator to catch sql exceptions. processAlgorithm |
| 429 | workflow_A | 14 | pure_vector | `native:fixgeometries -> native:zonalstatisticsfb` | `script_0002741.py` | processAlgorithm |
| 430 | workflow_A | 3 | pure_vector | `native:fixgeometries -> native:savefeatures -> native:mergevectorlayers` | `script_0003033.py` | layer |
| 431 | workflow_A | 3 | pure_raster | `gdal:cliprasterbymasklayer -> gdal:polygonize` | `script_0003042.py` | init |
| 432 | workflow_A | 9 | pure_raster | `saga:upslopearea -> gdal:polygonize` | `script_0003046.py` | initAlgorithm |
| 433 | workflow_A | 9 | pure_raster | `saga:upslopearea -> gdal:polygonize` | `script_0003047.py` |  |
| 434 | workflow_A | 6 | mixed | `native:buffer -> native:clip -> gdal:rasterize -> gdal:warpreproject -> gdal:rastercalculator` | `script_0003065.py` | 📦 Opportunities Mask Processor module. init |
| 435 | workflow_A | 6 | pure_vector | `native:fixgeometries -> native:retainfields -> native:zonalstatisticsfb` | `script_0003067.py` | 📦 Subnational Aggregation Processor module. init |
| 436 | workflow_A | 6 | mixed | `gdal:assignprojection -> native:assignprojection -> native:extractbyextent -> native:fixgeometries -> native:reprojectlayer -> gdal:buildvirtualraster` | `script_0003068.py` | 📦 Utilities module. assign crs to raster layer |
| 437 | workflow_A | 6 | pure_vector | `native:reprojectlayer -> native:clip` | `script_0003070.py` | 📦 Osm Data Downloader Base module. init |
| 438 | workflow_A | 3 | pure_vector | `native:reprojectlayer -> native:clip -> native:buffer -> native:dissolve -> native:difference -> native:mergevectorlayers` | `script_0003083.py` | Multi-buffer distances workflow using native QGIS network analysis. init |
| 439 | workflow_A | 6 | pure_vector | `native:mergevectorlayers -> native:dissolve -> native:difference -> native:mergevectorlayers -> native:reprojectlayer` | `script_0003084.py` | 📦 Multi Buffer Distances Ors Workflow module. init |
| 440 | workflow_A | 6 | mixed | `gdal:warpreproject -> native:fillnodata -> gdal:rasterize -> gdal:cliprasterbymasklayer` | `script_0003094.py` | 📦 Workflow Base module. init |
| 441 | workflow_A | 3 | mixed | `gdal:rastercalculator -> gdal:rasterize -> gdal:rasterize -> gdal:rastercalculator` | `script_0003186.py` | initAlgorithm |
| 442 | workflow_A | 3 | pure_vector | `native:extractbyexpression -> native:extractbyexpression -> native:fixgeometries -> native:addautoincrementalfield -> native:deletecolumn -> native:renametablefield` | `script_0003187.py` | initAlgorithm |
| 443 | workflow_A | 3 | mixed | `gdal:warpreproject -> gdal:rasterize -> gdal:assignprojection -> gdal:cliprasterbymasklayer -> gdal:warpreproject -> gdal:warpreproject` | `script_0003195.py` | addAdvancedParameter |
| 444 | workflow_A | 21 | pure_vector | `native:reprojectlayer -> native:reprojectlayer` | `script_0003206.py` | This algorithm generates a full sidewalk network based on OSM data within a specified boun |
| 445 | workflow_A | 21 | pure_vector | `native:reprojectlayer -> native:reprojectlayer` | `script_0003207.py` | compat osm query bbox |
| 446 | workflow_A | 21 | pure_vector | `native:reprojectlayer -> native:reprojectlayer` | `script_0003208.py` | Generates protoblocks by fetching OSM street data within an input polygon, |
| 447 | workflow_A | 3 | pure_vector | `native:fixgeometries -> native:mergevectorlayers -> native:difference -> native:mergevectorlayers` | `script_0003222.py` | init |
| 448 | workflow_A | 3 | pure_raster | `gdal:slope -> gdal:hillshade -> qgis:rastercalculator -> gdal:polygonize` | `script_0003237.py` | Save analysis results as JSON with metadata save json result |
| 449 | workflow_A | 12 | pure_vector | `native:fixgeometries -> native:clip` | `script_0003245.py` | Fix invalid geometries in input layer and return temporary layer with valid geoms addlayer |
| 450 | workflow_A | 12 | pure_vector | `native:fixgeometries -> native:clip` | `script_0003275.py` | Fix invalid geometries in input layer and return temporary layer with valid geoms fix geom |
| 451 | workflow_A | 3 | mixed | `gdal:cliprasterbymasklayer -> native:clip -> native:reclassifybytable -> gdal:polygonize` | `script_0003358.py` |  |
| 452 | workflow_A | 3 | mixed | `native:reprojectlayer -> native:reprojectlayer -> qgis:minimumboundinggeometry -> native:selectbylocation -> gdal:translate -> gdal:translate -> gdal:assignprojection` | `script_0003368.py` | mainFunction |
| 453 | workflow_A | 3 | mixed | `gdal:polygonize -> gdal:polygonize -> native:clip -> gdal:polygonize -> native:buffer -> native:clip -> native:buffer -> native:buffer -> native:buffer -> native:dissolve -> native:clip` | `script_0003395.py` | to avoid havign to use "stroke to path" which keeps crashing in inkscape buffer params |
| 454 | workflow_A | 2 | mixed | `gdal:warpreproject -> native:reprojectlayer` | `script_0003428.py` | 重投影 Skill — 支持矢量和栅格. |
| 455 | workflow_A | 2 | pure_vector | `native:reprojectlayer -> native:clip -> native:buffer -> native:joinattributesbylocation -> native:savefeatures` | `script_0003429.py` | Executor Agent — PyQGIS 脚本注入执行与闭环自愈验证. verify hash |
| 456 | workflow_A | 6 | mixed | `native:reprojectlayer -> gdal:cliprasterbymasklayer` | `script_0003464.py` | Create a new print layout and remove any previous layout with the same name. create layout |
| 457 | workflow_A | 6 | mixed | `native:reprojectlayer -> gdal:cliprasterbymasklayer` | `script_0003465.py` | Create a new print layout and remove any previous layout with the same name. create layout |
| 458 | workflow_A | 4 | pure_vector | `native:fixgeometries -> native:fixgeometries -> native:fixgeometries` | `script_0003471.py` |  |
| 459 | workflow_A | 3 | pure_vector | `native:reprojectlayer -> native:reprojectlayer -> native:savefeatures -> native:clip` | `script_0003522.py` | Return all polygon vector layers currently loaded in the project. polygon layers |
| 460 | workflow_A | 3 | pure_vector | `native:fixgeometries -> native:extractbyattribute -> native:reprojectlayer -> native:refactorfields -> native:refactorfields -> native:savefeatures` | `script_0003523.py` | Model exported as python (patched). initAlgorithm |
| 461 | workflow_A | 3 | mixed | `gdal:polygonize -> native:joinattributesbylocation -> native:joinattributesbylocation` | `script_0003602.py` |  |
| 462 | workflow_A | 7 | mixed | `native:reprojectlayer -> gdal:warpreproject` | `script_0003609.py` | Simple feedback object that prints all messages to console reportError |
| 463 | workflow_A | 66 | mixed | `native:reclassifybytable -> native:reclassifybytable -> native:reclassifybytable -> gdal:polygonize -> native:zonalstatisticsfb` | `script_0003811.py` | Module 7: Market Classification & Zoning |
| 464 | workflow_A | 66 | mixed | `native:reclassifybytable -> native:reclassifybytable -> native:reclassifybytable -> gdal:polygonize -> native:zonalstatisticsfb` | `script_0003812.py` | Module 7: Market Classification & Zoning |
| 465 | workflow_A | 66 | mixed | `native:reclassifybytable -> native:reclassifybytable -> native:reclassifybytable -> gdal:polygonize -> native:zonalstatisticsfb` | `script_0003813.py` | Module 7: Market Classification & Zoning |
| 466 | workflow_A | 66 | mixed | `native:reclassifybytable -> native:reclassifybytable -> native:reclassifybytable -> gdal:polygonize -> native:zonalstatisticsfb` | `script_0003814.py` | Module 7: Market Classification & Zoning |
| 467 | workflow_A | 66 | mixed | `native:reclassifybytable -> native:reclassifybytable -> native:reclassifybytable -> gdal:polygonize -> native:zonalstatisticsfb` | `script_0003815.py` | Module 7: Market Classification & Zoning |
| 468 | workflow_A | 66 | mixed | `native:reclassifybytable -> native:reclassifybytable -> native:reclassifybytable -> gdal:polygonize -> native:zonalstatisticsfb` | `script_0003816.py` | Module 7: Market Classification & Zoning |
| 469 | workflow_A | 66 | mixed | `native:reclassifybytable -> native:reclassifybytable -> native:reclassifybytable -> gdal:polygonize -> native:zonalstatisticsfb` | `script_0003817.py` | Module 7: Market Classification & Zoning |
| 470 | workflow_A | 66 | mixed | `native:reclassifybytable -> native:reclassifybytable -> native:reclassifybytable -> gdal:polygonize -> native:zonalstatisticsfb` | `script_0003818.py` | Module 7: Market Classification & Zoning |
| 471 | workflow_A | 66 | mixed | `native:reclassifybytable -> native:reclassifybytable -> native:reclassifybytable -> gdal:polygonize -> native:zonalstatisticsfb` | `script_0003819.py` | Module 7: Market Classification & Zoning |
| 472 | workflow_A | 66 | mixed | `native:reclassifybytable -> native:reclassifybytable -> native:reclassifybytable -> gdal:polygonize -> native:zonalstatisticsfb` | `script_0003820.py` | Module 7: Market Classification & Zoning |
| 473 | workflow_A | 66 | mixed | `native:reclassifybytable -> native:reclassifybytable -> native:reclassifybytable -> gdal:polygonize -> native:zonalstatisticsfb` | `script_0003821.py` | Module 7: Market Classification & Zoning |
| 474 | workflow_A | 66 | mixed | `native:reclassifybytable -> native:reclassifybytable -> native:reclassifybytable -> gdal:polygonize -> native:zonalstatisticsfb` | `script_0003822.py` | Module 7: Market Classification & Zoning |
| 475 | workflow_A | 66 | mixed | `native:reclassifybytable -> native:reclassifybytable -> native:reclassifybytable -> gdal:polygonize -> native:zonalstatisticsfb` | `script_0003823.py` | Module 7: Market Classification & Zoning |
| 476 | workflow_A | 66 | mixed | `native:reclassifybytable -> native:reclassifybytable -> native:reclassifybytable -> gdal:polygonize -> native:zonalstatisticsfb` | `script_0003824.py` | Module 7: Market Classification & Zoning |
| 477 | workflow_A | 66 | mixed | `native:reclassifybytable -> native:reclassifybytable -> native:reclassifybytable -> gdal:polygonize -> native:zonalstatisticsfb` | `script_0003825.py` | Module 7: Market Classification & Zoning |
| 478 | workflow_A | 66 | mixed | `native:reclassifybytable -> native:reclassifybytable -> native:reclassifybytable -> gdal:polygonize -> native:zonalstatisticsfb` | `script_0003826.py` | Module 7: Market Classification & Zoning |
| 479 | workflow_A | 66 | mixed | `native:reclassifybytable -> native:reclassifybytable -> native:reclassifybytable -> gdal:polygonize -> native:zonalstatisticsfb` | `script_0003827.py` | Module 7: Market Classification & Zoning |
| 480 | workflow_A | 66 | mixed | `native:reclassifybytable -> native:reclassifybytable -> native:reclassifybytable -> gdal:polygonize -> native:zonalstatisticsfb` | `script_0003828.py` | Module 7: Market Classification & Zoning |
| 481 | workflow_A | 66 | mixed | `native:reclassifybytable -> native:reclassifybytable -> native:reclassifybytable -> gdal:polygonize -> native:zonalstatisticsfb` | `script_0003829.py` | Module 7: Market Classification & Zoning |
| 482 | workflow_A | 66 | mixed | `native:reclassifybytable -> native:reclassifybytable -> native:reclassifybytable -> gdal:polygonize -> native:zonalstatisticsfb` | `script_0003830.py` | Module 7: Market Classification & Zoning |
| 483 | workflow_A | 66 | mixed | `native:reclassifybytable -> native:reclassifybytable -> native:reclassifybytable -> gdal:polygonize -> native:zonalstatisticsfb` | `script_0003831.py` | Module 7: Market Classification & Zoning |
| 484 | workflow_A | 66 | mixed | `native:reclassifybytable -> native:reclassifybytable -> native:reclassifybytable -> gdal:polygonize -> native:zonalstatisticsfb` | `script_0003832.py` | Module 7: Market Classification & Zoning |
| 485 | workflow_A | 4 | pure_vector | `native:fixgeometries -> native:fixgeometries -> native:fixgeometries` | `script_0003856.py` | select apex model |
| 486 | workflow_A | 21 | pure_vector | `native:reprojectlayer -> native:reprojectlayer` | `script_0003889.py` | init |
| 487 | workflow_A | 4 | pure_vector | `native:union -> native:multiparttosingleparts -> native:fixgeometries -> native:multiparttosingleparts -> native:reprojectlayer` | `script_0003910.py` | Decorator to catch sql exceptions. sql error handler |
| 488 | workflow_A | 3 | pure_vector | `native:difference -> native:dissolve -> native:dissolve -> native:mergevectorlayers -> native:fixgeometries -> native:difference -> native:removenullgeometries -> native:fixgeometries -> native:fixgeometries -> native:union -> native:fixgeometries -> native:mergevectorlayers` | `script_0003975.py` | Apply a simple difference operation to the input layers. apply simple difference |
| 489 | workflow_A | 3 | mixed | `native:clip -> gdal:polygonize -> gdal:cliprasterbyextent` | `script_0003977.py` | Clip a QgsVector layer by different QgsVector layer simple clip |
| 490 | workflow_A | 3 | pure_vector | `native:fixgeometries -> native:fixgeometries -> native:clip` | `script_0003979.py` | Class to download and clip WFS layers, used before and during WFStask init |
| 491 | workflow_A | 3 | mixed | `native:extractbyattribute -> native:reprojectlayer -> gdal:cliprasterbymasklayer -> gdal:warpreproject -> gdal:cliprasterbymasklayer -> gdal:warpreproject -> gdal:fillnodata` | `script_0004023.py` | climate extraction |
| 492 | workflow_A | 6 | mixed | `native:buffer -> native:clip -> gdal:rasterize -> gdal:warpreproject -> gdal:rastercalculator` | `script_0004096.py` | A QgsTask subclass for generating job opportunity mask layers. init |
| 493 | workflow_A | 6 | pure_vector | `native:fixgeometries -> native:retainfields -> native:zonalstatisticsfb` | `script_0004098.py` | A QgsTask subclass for calculating WEE x Population SCORE and or WEE score per aggregation |
| 494 | workflow_A | 6 | mixed | `gdal:assignprojection -> native:assignprojection -> native:extractbyextent -> native:fixgeometries -> native:reprojectlayer -> gdal:buildvirtualraster` | `script_0004099.py` | Assigns a CRS to a layer and returns the layer. assign crs to raster layer |
| 495 | workflow_A | 6 | pure_vector | `native:mergevectorlayers -> native:dissolve -> native:difference -> native:mergevectorlayers -> native:reprojectlayer` | `script_0004106.py` | Concrete implementation of a 'multi_buffer_distances' workflow. init |
| 496 | workflow_A | 6 | mixed | `gdal:warpreproject -> native:fillnodata -> gdal:rasterize -> gdal:cliprasterbymasklayer` | `script_0004115.py` | Abstract base class for all workflows. init |
| 497 | workflow_A | 3 | pure_vector | `native:extractbyexpression -> native:intersection -> native:intersection -> native:dissolve -> native:dissolve -> native:refactorfields -> native:fixgeometries -> native:refactorfields -> native:fixgeometries -> native:promotetomulti -> native:promotetomulti -> native:dissolve -> native:dissolve -> native:refactorfields -> native:refactorfields` | `script_0004119.py` | Model exported as python. initAlgorithm |
| 498 | workflow_A | 3 | pure_vector | `native:refactorfields -> native:refactorfields -> native:extractbyattribute -> native:extractbyattribute -> native:fixgeometries -> native:fixgeometries -> native:mergevectorlayers -> native:refactorfields -> native:dissolve -> native:refactorfields` | `script_0004122.py` | Model exported as python. initAlgorithm |
| 499 | workflow_A | 2 | pure_vector | `native:fixgeometries -> native:fixgeometries -> native:fixgeometries -> native:fixgeometries -> native:fixgeometries` | `script_0004140.py` | Modulo: AyudasGEO RegisterFunction |
| 500 | workflow_A | 5 | pure_vector | `native:fixgeometries -> native:dissolve` | `script_0004150.py` | initAlgorithm |
| 501 | workflow_A | 2 | mixed | `gdal:rasterize -> gdal:merge` | `script_0004154.py` | initAlgorithm |
| 502 | workflow_A | 3 | pure_vector | `native:reprojectlayer -> native:union -> native:union -> native:reprojectlayer` | `script_0004203.py` | select nombre_esquema,nombre_capa from acervo_descripcion_1.mapa_master_vw where id in (se |
| 503 | workflow_A | 3 | mixed | `native:extractbyextent -> native:fixgeometries -> native:clip -> native:reprojectlayer -> gdal:rasterize -> gdal:warpreproject -> native:savefeatures -> native:reprojectlayer -> native:fixgeometries -> native:clip -> native:multiparttosingleparts -> native:reprojectlayer` | `script_0004214.py` | Dialog for filtering vector layer features by attribute values. init |
| 504 | workflow_A | 4 | mixed | `gdal:rasterize -> gdal:polygonize` | `script_0004233.txt` | getBboxWmsFormat |
| 505 | workflow_A | 2 | pure_raster | `gdal:polygonize -> gdal:polygonize` | `script_0004239.py` | transfrom input buffer zone raster to vector raster2vector |
| 506 | workflow_A | 3 | pure_vector | `native:fixgeometries -> native:fixgeometries -> native:fixgeometries -> native:mergevectorlayers -> native:dissolve` | `script_0004242.py` | This makes parameters for wfs-request of specific area getBboxWmsFormat |
| 507 | workflow_A | 21 | pure_vector | `native:reprojectlayer -> native:reprojectlayer` | `script_0004273.py` | Convertit un objet QColor en hexadécimal #RRGGBB init |
| 508 | workflow_A | 3 | mixed | `gdal:warpreproject -> saga:fillsinksxxlwangliu -> native:zonalstatistics -> native:zonalstatistics -> gdal:cliprasterbyextent -> native:fixgeometries -> native:buffer -> native:clip -> native:clip -> gdal:polygonize -> native:zonalstatistics -> native:zonalstatistics` | `script_0004279.py` | HydroAnalysis.py - Module d'analyse hydrologique pour SigLogix (QGIS) init |
| 509 | workflow_A | 8 | mixed | `gdal:polygonize -> native:intersection` | `script_0004317.py` | initAlgorithm |
| 510 | workflow_A | 3 | mixed | `native:buffer -> native:union -> native:promotetomulti -> native:polygonfromlayerextent -> gdal:clipvectorbypolygon -> gdal:rasterize -> gdal:warpreproject` | `script_0004326.py` | build water rasterized |
| 511 | workflow_A | 8 | mixed | `gdal:polygonize -> native:intersection` | `script_0004332.py` | prompt raster |
| 512 | workflow_A | 3 | pure_vector | `native:reprojectlayer -> native:joinattributesbylocation -> native:multiintersection` | `script_0004347.py` | Quite specific to the French case. Add a boolean attribute, for every building of a vector |
| 513 | workflow_A | 6 | pure_vector | `native:reprojectlayer -> native:extractbyexpression` | `script_0004350.py` |  |
| 514 | workflow_A | 3 | pure_vector | `native:fixgeometries -> native:clip -> native:clip -> native:buffer -> native:extractbylocation -> native:countpointsinpolygon` | `script_0004351.py` |  |
| 515 | workflow_A | 3 | pure_vector | `native:fixgeometries -> native:fixgeometries -> native:intersection -> qgis:statisticsbycategories` | `script_0004386.py` |  |
| 516 | workflow_A | 3 | pure_vector | `native:fixgeometries -> native:dissolve -> native:dissolve -> qgis:statisticsbycategories` | `script_0004390.py` |  |
| 517 | workflow_A | 2 | pure_vector | `native:mergevectorlayers -> native:retainfields -> native:reprojectlayer -> native:mergevectorlayers -> native:mergevectorlayers` | `script_0004411.py` | init |
| 518 | workflow_A | 2 | mixed | `qgis:rastercalculator -> qgis:rastercalculator -> qgis:rastercalculator -> gdal:polygonize -> native:dissolve -> native:clip` | `script_0004437.py` | Class to classify landuse from OSM init |
| 519 | workflow_A | 3 | mixed | `native:buffer -> native:zonalstatisticsfb -> gdal:rasterize -> gdal:merge -> saga:fillsinksxxlwangliu -> gdal:warpreproject -> native:hillshade` | `script_0004450.py` |  |
| 520 | workflow_A | 3 | pure_vector | `native:reprojectlayer -> native:clip -> native:reprojectlayer` | `script_0004543.py` | Download features from an ArcGIS Feature/MapServer layer using paged requests, return Feat |
| 521 | workflow_A | 3 | pure_vector | `native:reprojectlayer -> native:mergevectorlayers -> native:clip` | `script_0004544.py` | load road layer |
| 522 | workflow_A | 6 | pure_vector | `native:reprojectlayer -> native:clip` | `script_0004545.py` |  |
| 523 | workflow_A | 3 | mixed | `native:mergevectorlayers -> gdal:polygonize` | `script_0004637.py` | checkLayerPoints |
| 524 | workflow_A | 6 | mixed | `native:buffer -> native:difference -> native:reclassifybytable -> gdal:polygonize -> native:extractbyexpression -> native:reclassifybytable -> gdal:polygonize -> native:extractbyexpression -> native:buffer -> native:difference -> native:savefeatures` | `script_0004661.py` | ================================================================================ init |
| 525 | workflow_A | 6 | mixed | `native:buffer -> native:difference -> native:reclassifybytable -> gdal:polygonize -> native:extractbyexpression -> native:reclassifybytable -> gdal:polygonize -> native:extractbyexpression -> native:buffer -> native:difference -> native:savefeatures` | `script_0004666.py` | ================================================================================ init |
| 526 | workflow_A | 3 | pure_raster | `gdal:cliprasterbymasklayer -> gdal:warpreproject -> gdal:polygonize -> gdal:hillshade` | `script_0004691.py` | Bilinear interpolation of raster value at (x, y). cleanup file |
| 527 | workflow_A | 21 | pure_vector | `native:reprojectlayer -> native:reprojectlayer` | `script_0004695.py` | all polygons intersecting fGetExtentPolygonCoords |
| 528 | workflow_A | 21 | pure_vector | `native:reprojectlayer -> native:reprojectlayer` | `script_0004696.py` | Normalize product version into table suffix format. fGetExtentPolygonCoords |
| 529 | workflow_A | 12 | pure_vector | `native:dissolve -> native:fieldcalculator -> native:intersection -> native:dissolve -> gdal:rasterize -> native:zonalstatisticsfb -> native:zonalstatisticsfb` | `script_0004713.py` | init |
| 530 | workflow_A | 3 | mixed | `native:reprojectlayer -> native:reprojectlayer -> native:reprojectlayer -> gdal:warpreproject -> native:reprojectlayer` | `script_0004724.py` | init |
| 531 | workflow_A | 14 | pure_vector | `native:fixgeometries -> native:zonalstatisticsfb` | `script_0004736.py` |  |
| 532 | workflow_A | 3 | pure_vector | `native:fixgeometries -> native:buffer -> native:difference` | `script_0004778.py` | The script defines functions that can be used in the QGIS python console to speed up the g |
| 533 | workflow_A | 14 | pure_vector | `native:fixgeometries -> native:zonalstatisticsfb` | `script_0004787.py` |  |
| 534 | workflow_A | 21 | pure_vector | `native:reprojectlayer -> native:reprojectlayer` | `script_0004955.py` | initAlgorithm |
| 535 | workflow_A | 3 | mixed | `native:reprojectlayer -> native:clip -> native:fixgeometries -> native:clip -> native:clip -> native:fixgeometries -> native:clip -> native:reprojectlayer -> gdal:cliprasterbymasklayer -> gdal:polygonize -> native:addfieldtoattributestable -> native:mergevectorlayers -> native:reprojectlayer -> native:reprojectlayer` | `script_0005257.py` | enable logging |
| 536 | workflow_A | 3 | mixed | `native:reprojectlayer -> gdal:cliprasterbymasklayer -> gdal:cliprasterbyextent -> gdal:translate -> gdal:warpreproject -> gdal:rastercalculator` | `script_0005283.py` | Calculates the Curve Number using global datasets from ESA WorldCover and ORNL HYSOG. init |
| 537 | workflow_A | 7 | pure_vector | `native:reprojectlayer -> native:intersection` | `script_0005316.py` | init |
| 538 | workflow_A | 2 | mixed | `gdal:rasterize -> gdal:translate` | `script_0005322.py` | Create binary masks from selected vector layers, based on a single chosen DTM tile extent, |
| 539 | workflow_A | 3 | pure_vector | `native:fixgeometries -> native:fixgeometries -> native:fixgeometries -> native:clip -> native:clip` | `script_0005342.py` | Model exported as python. initAlgorithm |
| 540 | workflow_A | 9 | pure_raster | `saga:upslopearea -> gdal:polygonize` | `script_0005362.py` |  |
| 541 | workflow_A | 3 | mixed | `gdal:cliprasterbyextent -> gdal:warpreproject -> native:reprojectlayer -> gdal:warpreproject` | `script_0005479.py` | get shapefile as json pyqgis |
| 542 | workflow_A | 2 | pure_vector | `native:selectbylocation -> native:reprojectlayer` | `script_0005515.py` | car_PrepareCarKml |
| 543 | workflow_A | 2 | mixed | `native:reprojectlayer -> gdal:cliprasterbyextent -> gdal:rastercalculator` | `script_0005667.py` | Manning's Roughness Generator - A QGIS Plugin name |
| 544 | workflow_A | 3 | pure_vector | `native:intersection -> native:intersection -> native:fixgeometries` | `script_0005725.py` | get project crs |
| 545 | workflow_A | 3 | mixed | `gdal:polygonize -> native:buffer -> gdal:rasterize` | `script_0005747.py` |  |
| 546 | workflow_A | 3 | pure_vector | `native:reprojectlayer -> native:buffer -> native:difference -> native:multiparttosingleparts` | `script_0005748.py` |  |
| 547 | workflow_A | 3 | pure_vector | `qgis:checkvalidity -> native:fixgeometries -> qgis:checkvalidity -> native:fixgeometries` | `script_0005749.py` |  |
| 548 | workflow_A | 7 | pure_vector | `native:reprojectlayer -> native:buffer -> native:clip` | `script_0005750.txt` |  |
| 549 | workflow_A | 7 | pure_vector | `native:reprojectlayer -> native:buffer -> native:clip` | `script_0005752.py` | PyQGIS Code Snippets |
| 550 | workflow_A | 3 | pure_vector | `native:fixgeometries -> native:buffer -> native:intersection` | `script_0005826.py` |  |
| 551 | workflow_A | 3 | pure_vector | `native:dissolve -> native:multiparttosingleparts -> native:buffer -> native:dissolve -> native:dissolve -> native:reprojectlayer -> qgis:checkvalidity` | `script_0005851.py` | init |
| 552 | workflow_A | 3 | pure_vector | `native:reprojectlayer -> native:savefeatures -> native:savefeatures -> native:savefeatures -> native:reprojectlayer -> native:savefeatures -> native:reprojectlayer -> native:savefeatures` | `script_0005935.py` | init |
| 553 | workflow_A | 5 | pure_vector | `native:fixgeometries -> native:dissolve` | `script_0005951.py` | init |
| 554 | workflow_A | 14 | pure_vector | `native:fixgeometries -> native:zonalstatisticsfb` | `script_0005969.py` |  |
| 555 | workflow_A | 3 | mixed | `gdal:rgbtopct -> gdal:polygonize -> native:extractbyattribute -> native:fixgeometries` | `script_0005973.py` |  |
| 556 | workflow_A | 3 | pure_vector | `native:reprojectlayer -> native:reprojectlayer -> native:buffer -> native:clip -> native:fieldcalculator` | `script_0005977.py` | Vector Geoprocessing — PyQGIS Processing Script |
| 557 | workflow_A | 3 | pure_vector | `native:mergevectorlayers -> native:reprojectlayer` | `script_0006021.py` | editAttribute |
| 558 | workflow_A | 3 | pure_vector | `native:refactorfields -> native:fixgeometries` | `script_0006060.py` | create table |
| 559 | workflow_A | 3 | pure_vector | `native:reprojectlayer -> native:reprojectlayer -> native:reprojectlayer -> native:buffer -> qgis:joinbylocationsummary -> native:buffer -> qgis:joinbylocationsummary -> native:fieldcalculator -> native:dbscanclustering -> native:reprojectlayer -> native:reprojectlayer` | `script_0006081.py` | Sample 01: Utility Outage Prioritization load layer |
| 560 | workflow_A | 3 | pure_vector | `native:reprojectlayer -> native:reprojectlayer -> native:reprojectlayer -> native:buffer -> qgis:joinbylocationsummary -> qgis:joinbylocationsummary -> native:fieldcalculator -> native:reprojectlayer` | `script_0006082.py` | Sample 02: Right-of-Way Vegetation + Flood Risk load layer |
| 561 | workflow_A | 3 | pure_vector | `native:difference -> native:buffer -> native:clip -> native:fixgeometries -> native:mergevectorlayers -> native:reprojectlayer` | `script_0006083.py` | config |
| 562 | workflow_A | 3 | pure_vector | `native:reprojectlayer -> native:renametablefield -> native:retainfields` | `script_0006093.py` | parse time interval |
| 563 | workflow_A | 3 | pure_vector | `native:reprojectlayer -> native:retainfields` | `script_0006094.py` | parse time interval |
| 564 | workflow_A | 3 | pure_vector | `native:fixgeometries -> native:dissolve -> native:buffer -> native:extractbylocation` | `script_0006096.py` |  |
| 565 | workflow_A | 12 | pure_vector | `native:fixgeometries -> native:clip` | `script_0006129.txt` | Fix invalid geometries in input layer and return temporary layer with valid geoms fix geom |
| 566 | workflow_A | 12 | pure_vector | `native:fixgeometries -> native:clip` | `script_0006154.py` | Model exported as python. initAlgorithm |
| 567 | workflow_A | 3 | pure_vector | `native:fixgeometries -> native:multiparttosingleparts -> native:clip -> native:extractbyexpression` | `script_0006163.py` | Fixes the geometries of a shapefile and saves the fixed version. fix geometries |
| 568 | workflow_A | 21 | pure_vector | `native:reprojectlayer -> native:reprojectlayer` | `script_0006191.py` | 指定されたレイヤーのCRSを変換する関数（Processingツール使用） convert layer crs |
| 569 | workflow_A | 21 | pure_vector | `native:reprojectlayer -> native:reprojectlayer` | `script_0006209.py` | 指定された中心点、幅、角度で正方形ポリゴンを作成する create square polygon |
| 570 | workflow_A | 3 | pure_vector | `native:reprojectlayer -> native:extractbyexpression -> native:buffer -> native:mergevectorlayers -> native:reprojectlayer` | `script_0006210.py` | main |
| 571 | workflow_A | 3 | mixed | `native:reprojectlayer -> native:clip -> native:reprojectlayer -> gdal:cliprasterbymasklayer` | `script_0006240.py` |  |
| 572 | workflow_A | 3 | pure_vector | `native:extractbyexpression -> native:intersection -> native:dissolve -> native:retainfields -> native:reprojectlayer -> native:fieldcalculator -> native:savefeatures` | `script_0006270.py` | Script using pyqgis |
| 573 | workflow_A | 3 | pure_raster | `native:reclassifybytable -> gdal:polygonize` | `script_0006287.py` | Aplica a simbologia categorizada no campo 'DN'. definir simbologia vetor |
| 574 | workflow_A | 2 | pure_vector | `native:fixgeometries -> native:dissolve -> native:mergevectorlayers` | `script_0006288.py` | file ext search |
| 575 | workflow_A | 2 | pure_vector | `native:dissolve -> native:fixgeometries -> native:dissolve -> native:promotetomulti` | `script_0006291.py` | init |
| 576 | workflow_A | 2 | pure_vector | `native:fixgeometries -> native:dissolve -> native:polygonize` | `script_0006293.py` | SolarPanelGenerator Plugin Coverage Logic init |
| 577 | workflow_A | 12 | pure_vector | `native:dissolve -> native:fieldcalculator -> native:intersection -> native:dissolve -> gdal:rasterize -> native:zonalstatisticsfb -> native:zonalstatisticsfb` | `script_0006299.py` | init |
| 578 | workflow_A | 12 | pure_vector | `native:dissolve -> native:fieldcalculator -> native:intersection -> native:dissolve -> gdal:rasterize -> native:zonalstatisticsfb -> native:zonalstatisticsfb` | `script_0006300.py` | init |
| 579 | workflow_A | 4 | mixed | `gdal:polygonize -> native:dissolve` | `script_0006301.py` | init |
| 580 | workflow_A | 4 | mixed | `gdal:polygonize -> native:dissolve` | `script_0006305.py` | read ASCII |
| 581 | workflow_A | 3 | pure_vector | `native:fixgeometries -> native:dissolve -> native:reprojectlayer` | `script_0006319.py` | init |
| 582 | workflow_A | 12 | pure_vector | `native:dissolve -> native:fieldcalculator -> native:intersection -> native:dissolve -> gdal:rasterize -> native:zonalstatisticsfb -> native:zonalstatisticsfb` | `script_0006324.py` | init |
| 583 | workflow_A | 9 | mixed | `gdal:translate -> native:fixgeometries` | `script_0006347.py` | qgisName |
| 584 | workflow_A | 2 | mixed | `qgis:rastercalculator -> gdal:polygonize -> native:dissolve` | `script_0006374.py` | 1. Находит в проекте растр по имени `raster_name`. create single polygon per color |
| 585 | workflow_A | 9 | mixed | `gdal:translate -> native:fixgeometries` | `script_0006378.py` | qgisName |
| 586 | workflow_A | 2 | pure_raster | `gdal:rastercalculator -> gdal:polygonize` | `script_0006396.py` | This shared script processes a raster dataset (NDVI) by performing the following steps: |
| 587 | workflow_A | 8 | mixed | `gdal:polygonize -> native:intersection` | `script_0006412.py` |  |
| 588 | workflow_A | 7 | pure_vector | `native:reprojectlayer -> native:intersection` | `script_0006414.py` | CN Calculator Tool for Hydro Suite init |
| 589 | workflow_A | 7 | pure_vector | `native:reprojectlayer -> native:intersection` | `script_0006415.py` | Rational C Calculator Tool for Hydro Suite init |
| 590 | workflow_A | 3 | pure_vector | `native:fixgeometries -> native:reprojectlayer -> native:intersection -> native:difference -> native:intersection -> native:difference -> native:difference -> native:mergevectorlayers` | `script_0006421.py` | Remove acentos e converte para minúsculas init |
| 591 | workflow_A | 3 | pure_vector | `native:fixgeometries -> native:reprojectlayer -> native:difference -> native:mergevectorlayers` | `script_0006422.py` | Remove acentos e converte para minúsculas init |
| 592 | workflow_A | 3 | mixed | `native:translategeometry -> gdal:rasterize -> gdal:cliprasterbymasklayer` | `script_0006423.py` | init |
| 593 | workflow_A | 7 | mixed | `native:reprojectlayer -> gdal:warpreproject` | `script_0006438.py` | Reproject raster and vector layers reproject raster and vector |
| 594 | workflow_A | 3 | mixed | `gdal:rasterize -> gdal:warpreproject -> gdal:rastercalculator -> gdal:cliprasterbymasklayer` | `script_0006456.py` | init |
| 595 | workflow_A | 3 | mixed | `native:savefeatures -> gdal:translate -> native:reprojectlayer -> gdal:warpreproject -> gdal:rasterize -> native:fixgeometries -> native:union -> native:rastersampling -> native:rastersampling -> native:savefeatures` | `script_0006474.py` | init |
| 596 | workflow_A | 3 | mixed | `gdal:warpreproject -> native:reclassifybytable -> gdal:polygonize -> native:fixgeometries -> native:zonalstatisticsfb -> native:fieldcalculator -> native:extractbyexpression -> native:fieldcalculator -> native:centroids` | `script_0006490.py` | Automated Keyline Keypoint Detection Algorithm |
| 597 | workflow_A | 3 | mixed | `gdal:warpreproject -> native:reprojectlayer -> gdal:cliprasterbymasklayer` | `script_0006504.py` | some utils func with qgis sauce reproject raster |
| 598 | workflow_A | 9 | mixed | `gdal:translate -> native:fixgeometries` | `script_0006515.py` | qgisName |
| 599 | workflow_A | 2 | mixed | `gdal:polygonize -> native:extractbyattribute -> gdal:cliprasterbymasklayer` | `script_0006530.py` | Black Frame Remover: main.py v1.1.0 init |
| 600 | workflow_A | 3 | mixed | `native:reprojectlayer -> gdal:merge -> native:slope -> native:zonalstatisticsfb` | `script_0006575.py` | init |
| 601 | workflow_A | 9 | mixed | `gdal:translate -> native:reprojectlayer` | `script_0006671.py` |  |
| 602 | workflow_A | 9 | mixed | `gdal:translate -> native:reprojectlayer` | `script_0006672.py` |  |
| 603 | workflow_A | 9 | mixed | `gdal:translate -> native:reprojectlayer` | `script_0006673.py` |  |
| 604 | workflow_A | 1 | pure_vector | `gdal:rasterize -> gdal:rasterize -> gdal:rasterize -> gdal:rasterize` | `script_0006822.py` | Rasterize |
| 605 | workflow_A | 1 | pure_vector | `native:reprojectlayer -> native:extractbyexpression -> native:mergevectorlayers` | `script_0006964.py` | This class is responsible for loading, optionally filtering, and merging vector layers fro |
| 606 | workflow_A | 1 | mixed | `gdal:polygonize -> native:fixgeometries` | `script_0006974.py` | init |
| 607 | workflow_A | 1 | mixed | `gdal:polygonize -> native:zonalstatisticsfb` | `script_0007007.py` | Stage 4: Zonal Statistics vectorize mask |
| 608 | workflow_A | 1 | pure_vector | `native:reprojectlayer -> native:dissolve -> native:multiparttosingleparts` | `script_0007068.py` |  |
| 609 | workflow_A | 1 | pure_vector | `native:reprojectlayer -> native:dissolve -> native:union -> native:difference -> native:difference` | `script_0007069.py` | select layer interactively |
| 610 | workflow_A | 1 | pure_vector | `native:reprojectlayer -> native:difference -> native:extractbyexpression -> native:intersection` | `script_0007070.py` | select layer |
| 611 | workflow_A | 4 | pure_vector | `native:reprojectlayer -> native:zonalstatisticsfb` | `script_0007087.py` | Area Comparison Analysis Algorithm |
| 612 | workflow_A | 2 | mixed | `gdal:warpreproject -> gdal:rastercalculator -> native:reprojectlayer -> native:zonalstatisticsfb` | `script_0007089.py` | DEM → Flooded extent + AOI stats (AR6 CSV; matches your Data schema) |
| 613 | workflow_A | 2 | mixed | `gdal:warpreproject -> gdal:rastercalculator -> native:reprojectlayer -> native:zonalstatisticsfb` | `script_0007090.py` | DEM → Flooded extent + AOI stats (AR6 CSV + CODEC return levels) norm |
| 614 | workflow_A | 4 | pure_vector | `native:reprojectlayer -> native:zonalstatisticsfb` | `script_0007091.py` | Feature Comparison Analysis Algorithm |
| 615 | workflow_A | 4 | pure_vector | `native:reprojectlayer -> native:zonalstatisticsfb` | `script_0007097.py` | Inundation Heatmap Visualization Algorithm |
| 616 | workflow_A | 4 | pure_vector | `native:reprojectlayer -> native:zonalstatisticsfb` | `script_0007100.py` | Population Impact Analysis Algorithm |
| 617 | workflow_A | 4 | mixed | `gdal:warpreproject -> native:reprojectlayer -> native:rastersampling` | `script_0007138.py` | process raster sample points |
| 618 | workflow_A | 4 | mixed | `gdal:warpreproject -> native:reprojectlayer -> native:rastersampling` | `script_0007139.py` | process raster sample points |
| 619 | workflow_A | 2 | mixed | `gdal:warpreproject -> native:reprojectlayer -> native:rastersampling -> native:buffer -> native:zonalstatisticsfb -> native:buffer -> native:zonalstatisticsfb` | `script_0007140.py` | process raster points buffer zonal |
| 620 | workflow_A | 1 | mixed | `gdal:warpreproject -> native:reprojectlayer -> native:rastersampling -> native:buffer -> native:zonalstatisticsfb` | `script_0007141.py` | process raster points buffer zonal |
| 621 | workflow_A | 2 | mixed | `gdal:warpreproject -> native:reprojectlayer -> native:rastersampling -> native:buffer -> native:zonalstatisticsfb -> native:buffer -> native:zonalstatisticsfb` | `script_0007142.py` | process raster points buffer zonal |
| 622 | workflow_A | 4 | mixed | `gdal:warpreproject -> native:reprojectlayer -> native:rastersampling` | `script_0007143.py` | process raster sample points |
| 623 | workflow_A | 4 | mixed | `gdal:warpreproject -> native:reprojectlayer -> native:rastersampling` | `script_0007144.py` | process raster sample points |
| 624 | workflow_A | 1 | pure_vector | `native:dissolve -> native:reprojectlayer -> native:fixgeometries -> native:reprojectlayer -> native:intersection` | `script_0007151.py` | Multi-Basin CN Generation Runner Script (v2.0) init |
| 625 | workflow_A | 1 | pure_vector | `native:reprojectlayer -> native:fixgeometries -> native:clip -> native:reprojectlayer -> native:fixgeometries` | `script_0007152.py` | Simple USDA Soil Retrieval - Matches CN Generator pattern exactly. get soil data |
| 626 | workflow_A | 1 | pure_vector | `native:reprojectlayer -> native:fixgeometries -> native:clip` | `script_0007153.py` | USDA Soil Data Retrieval - Final Production Version (v2.0) init |
| 627 | workflow_A | 1 | mixed | `gdal:rastercalculator -> gdal:rastercalculator -> gdal:polygonize -> native:fieldcalculator` | `script_0007163.py` | Fonction pour lancer le calcul NDVI depuis main.py initAlgorithm |
| 628 | workflow_A | 5 | pure_vector | `native:reprojectlayer -> gdal:rasterize` | `script_0007168.py` | from qgis.core import QgsProject, QgsRasterLayer get layer |
| 629 | workflow_A | 5 | pure_vector | `native:reprojectlayer -> gdal:rasterize` | `script_0007169.py` | import processing |
| 630 | workflow_A | 1 | mixed | `gdal:polygonize -> native:fixgeometries -> native:dissolve -> native:zonalstatisticsfb -> native:savefeatures -> native:difference -> native:savefeatures` | `script_0007172.py` | add layer to project |
| 631 | workflow_A | 1 | mixed | `gdal:translate -> gdal:fillnodata -> gdal:translate -> gdal:sieve -> gdal:polygonize -> native:extractbyattribute` | `script_0007175.py` | Writes a raster where pixels in [min_val, max_val] become 1, else 0. create range mask |
| 632 | workflow_A | 2 | mixed | `native:reprojectlayer -> native:buffer -> native:clip -> native:intersection -> native:dissolve -> qgis:rastercalculator` | `script_0007208.py` | 根据用户需求和数据信息生成QGIS空间分析代码。 init |
| 633 | workflow_A | 2 | mixed | `native:reprojectlayer -> native:buffer -> native:clip -> native:intersection -> native:dissolve -> qgis:rastercalculator` | `script_0007210.py` | Code Generator Module init |
| 634 | workflow_A | 2 | pure_vector | `native:reprojectlayer -> native:buffer -> native:reprojectlayer` | `script_0007214.py` | 使用正确的坐标系统转换重新生成圆明园buffer文件 |
| 635 | workflow_A | 3 | pure_raster | `gdal:slope -> gdal:hillshade -> qgis:rastercalculator -> gdal:polygonize` | `script_0007221.py` | Save analysis results as JSON with metadata save json result |
| 636 | workflow_A | 3 | pure_raster | `gdal:slope -> gdal:hillshade -> qgis:rastercalculator -> gdal:polygonize` | `script_0007230.py` | Initialize the Debris Flow Paths Detector init |
| 637 | workflow_A | 1 | pure_vector | `native:extractbylocation -> native:fixgeometries -> native:intersection` | `script_0007279.py` | GeoLote - Plugin QGIS sanitize field name |
| 638 | workflow_A | 2 | mixed | `native:reprojectlayer -> gdal:rasterize -> gdal:cliprasterbyextent` | `script_0007283.py` | generate_tiles.py load config |
| 639 | workflow_A | 4 | mixed | `gdal:cliprasterbymasklayer -> gdal:cliprasterbymasklayer -> native:reprojectlayer` | `script_0007381.py` | initAlgorithm |
| 640 | workflow_A | 1 | pure_vector | `native:buffer -> native:buffer -> native:extractbylocation -> native:reprojectlayer -> native:reprojectlayer` | `script_0007428.py` | Spatial analysis tools for geometry operations and spatial queries. register tools |

## Admission Boundary

- Use `stable101_source_review_50_v1.csv` for manual adjudication.
- Check workflow boundary, operator identity/order, source snippet validity, dependency plausibility, and task-text usability.
- Keep `training_admission=not_granted` until human review and faithful task-description generation pass.
