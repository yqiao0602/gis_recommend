# QGIS 6个高影响阻塞算子源码片段复核（2026-07-24）

本报告是 `/home/yll` 服务器真实源码复核，不修改 stable-94/stable-98 authority，不生成训练集，不训练模型。

## 复核口径

- 服务器：`qy@10.191.2.38`。
- 源码根：`/home/yll`，回溯索引：`/home/qy/system_redesign/outputs_v2/qgis_corpus_screening/nine_sources_canonical_v2`。
- 抽样：每个目标算子 3 个 `content_sha256` 去重源码样本，优先 `explicit_processing_multistep_catalog_exact` 层。
- 必须条件：源文件可读、AST 可解析、存在字面量 `processing.run*()` 且首参精确等于目标 operator ID。
- 复核字段：参数语义、输出角色、是否只是 support/export 边界、重复/镜像情况。

## 总体结论

| 算子 | 样本 | 源码层唯一命中 | 结论 | 训练准入建议 |
|---|---:|---:|---|---|
| `native:reprojectlayer` | 3 | 1292 | 真实源码支持 `L3_01_10_01` Project/Reproject 映射 | 通过正式 authority 后可进 core 候选 |
| `native:fixgeometries` | 3 | 924 | 真实源码支持 `L3_01_05_02` Repair Geometry 映射 | 通过正式 authority 后可进 core 候选 |
| `gdal:polygonize` | 3 | 512 | 真实源码支持 `L3_01_09_03` Raster-Vector Conversion 映射 | 通过正式 authority 后可进 core 候选 |
| `gdal:rasterize` | 3 | 576 | 真实源码支持 `L3_01_09_03` Raster-Vector Conversion 映射 | 通过正式 authority 后可进 core 候选 |
| `native:createspatialindex` | 3 | 325 | 真实源码支持 `L3_01_07_01` Add Spatial Index，但多为性能支撑步骤 | 继续 deferred，不单独作为训练目标 |
| `native:saveselectedfeatures` | 3 | 408 | 真实源码支持“保存选择集为新图层”，但不稳定等同 `L3_07_04_01` shapefile 导出 | 继续 deferred；需按 OUTPUT 类型细分 |

## 分算子复核

### `native:reprojectlayer` -> `L3_01_10_01` Project/Reproject

- 草案场景：`conservative`。
- 复核判断：`accept_mapping_after_authority`。
- 依据：真实调用使用 INPUT/TARGET_CRS/OUTPUT，语义是把矢量图层转换到目标CRS。

**样本 1**

- 路径：`/home/yll/GEE/爬取GIS代码/QGIS_ArcGIS_Textbook_Candidates_Broad/downloaded_scripts_strict/script_0012162.py`
- source_root：`textbook_strict`；primary_layer：`explicit_processing_multistep_catalog_exact`；duplicate_count：`1`；hash：`012426501591...`
- 调用：`processing.run` 第 141-150 行；scope：`class PipeTopologyAlgorithm / def processAlgorithm`
- 参数键：`INPUT`, `TARGET_CRS`, `OUTPUT`
- 输出角色：`assigned` target=`pipes_layer_proj` subscript=`OUTPUT`

```python
0138:         # Use the projected CRS of the input if it's already projected
0139:         if is_geographic(pipes_layer.crs()):
0140:             feedback.pushInfo(f"Pipes layer is in geographic CRS ({pipes_layer.crs().authid()}), reprojecting to {default_projected_crs.authid()}")
0141:             pipes_layer_proj = processing.run(
0142:                 "native:reprojectlayer",
0143:                 {
0144:                     'INPUT': pipes_layer,
0145:                     'TARGET_CRS': default_projected_crs,
0146:                     'OUTPUT': 'memory:'
0147:                 },
0148:                 context=context,
0149:                 feedback=feedback
0150:             )['OUTPUT']
0151:         else:
0152:             feedback.pushInfo(f"Pipes layer is already projected: {pipes_layer.crs().authid()}")
0153:             pipes_layer_proj = pipes_layer
```

**样本 2**

- 路径：`/home/yll/GEE/爬取多源数据源/QGIS_Model_Tutorial_Workflows/downloaded_scripts/script_56146.py`
- source_root：`model_tutorial`；primary_layer：`explicit_processing_multistep_catalog_exact`；duplicate_count：`1`；hash：`017202d6dddc...`
- 调用：`processing.run` 第 94-101 行；scope：`class RasterTools / def reproject_plate_polygons`
- 参数键：`INPUT`, `TARGET_CRS`, `CONVERT_CURVED_GEOMETRIES`, `OPERATION`, `OUTPUT`
- 输出角色：`side_effect_or_unassigned` target=`expr` subscript=`None`

```python
0091:         buffer_pos_path = reproj_plates_path.replace('.geojson','buff_pos.geojson')
0092:         buffer_neg_path = reproj_plates_path.replace('.geojson','buff_neg.geojson')
0093: 
0094:         processing.run("native:reprojectlayer", {'INPUT': QgsProcessingFeatureSourceDefinition(
0095:             self.plate_polygons_path , selectedFeaturesOnly=False,
0096:             featureLimit=-1, filterExpression=f' "APPEARANCE" = {age} ',
0097:             geometryCheck=QgsFeatureRequest.GeometryAbortOnInvalid),
0098:                                                  'TARGET_CRS': QgsCoordinateReferenceSystem('ESRI:54034'),
0099:                                                  'CONVERT_CURVED_GEOMETRIES': False,
0100:                                                  'OPERATION': '+proj=pipeline +step +proj=unitconvert +xy_in=deg +xy_out=rad +step +proj=cea +lat_ts=0 +lon_0=0 +x_0=0 +y_0=0 +ellps=WGS84',
0101:                                                  'OUTPUT': reproj_plates_path})
0102: 
0103:         processing.run("native:fixgeometries", {
0104:             'INPUT': reproj_plates_path,
```

**样本 3**

- 路径：`/home/yll/GEE/爬取多源数据源/QGIS_Plugins_GitLab_Supplement/downloaded_scripts/official_plugins/plugin_0009489.py`
- source_root：`gitlab_supplement`；primary_layer：`explicit_processing_multistep_catalog_exact`；duplicate_count：`1`；hash：`02af4c4fbfb8...`
- 调用：`processing.run` 第 50-50 行；scope：`class orderPoints / def processAlgorithm`
- 参数键：无字面量参数键
- 输出角色：`assigned` target=`outputs[...]` subscript=`None`

```python
0047:             'TARGET_CRS': QgsCoordinateReferenceSystem('EPSG:31981'),
0048:             'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
0049:         }
0050:         outputs['base'] = processing.run('native:reprojectlayer', alg_params, context=context, feedback=feedback, is_child_algorithm=True)
0051: 
0052:         # Reprojetar camada
0053:         alg_params = {
```


### `native:fixgeometries` -> `L3_01_05_02` Repair Geometry

- 草案场景：`conservative`。
- 复核判断：`accept_mapping_after_authority`。
- 依据：真实调用使用 INPUT/OUTPUT 或 METHOD/INPUT/OUTPUT，语义是修复无效几何并产生修复后图层。

**样本 1**

- 路径：`/home/yll/GEE/爬取GIS代码/QGIS_ArcGIS_Textbook_Candidates_Broad/downloaded_scripts_strict/script_0008817.py`
- source_root：`textbook_strict`；primary_layer：`explicit_processing_multistep_catalog_exact`；duplicate_count：`1`；hash：`00141e3f7b35...`
- 调用：`processing.run` 第 147-147 行；scope：`def addFieldValue`
- 参数键：`INPUT`, `OUTPUT`
- 输出角色：`assigned` target=`fix` subscript=`None`

```python
0144:     """
0145:     This adds field with given value to the vector layer
0146:     """
0147:     fix = processing.run("native:fixgeometries", {'INPUT':in_feat,'OUTPUT':'TEMPORARY_OUTPUT'})
0148:     fix['OUTPUT'].dataProvider().addAttributes([QgsField(fieldname,QVariant.Double)])
0149:     fix['OUTPUT'].updateFields()
0150:     with edit(fix['OUTPUT']):
```

**样本 2**

- 路径：`/home/yll/GEE/爬取多源数据源/QGIS_Model_Tutorial_Workflows/downloaded_scripts/script_56074.py`
- source_root：`model_tutorial`；primary_layer：`explicit_processing_multistep_catalog_exact`；duplicate_count：`1`；hash：`003de52b5940...`
- 调用：`processing.run` 第 20-20 行；scope：``
- 参数键：`INPUT`, `OUTPUT`
- 输出角色：`side_effect_or_unassigned` target=`expr` subscript=`None`

```python
0017: villages  = QgsVectorLayer(os.path.join(PROC, 'villages_utm.gpkg'), 'villages', 'ogr')
0018: 
0019: # Fix geometries
0020: processing.run("native:fixgeometries", {'INPUT': mh, 'OUTPUT': os.path.join(PROC, 'mh_fixed.gpkg')})
0021: mh_fixed = QgsVectorLayer(os.path.join(PROC, 'mh_fixed.gpkg'), 'mh_fixed', 'ogr')
0022: 
0023: # Clip hospitals to Maharashtra
```

**样本 3**

- 路径：`/home/yll/GEE/爬取GithubQGIS/合并脚本/QGIS_merged_dedup_by_index/downloaded_scripts/script_721.py`
- source_root：`github_merge`；primary_layer：`explicit_processing_multistep_catalog_exact`；duplicate_count：`1`；hash：`021b86270754...`
- 调用：`processing.run` 第 576-580 行；scope：`def repair_geometry`
- 参数键：`INPUT`, `METHOD`, `OUTPUT`
- 输出角色：`side_effect_or_unassigned` target=`expr` subscript=`None`

```python
0573:     input_path_6 = os.path.join(base_output_path, base_layer)
0574:     output_path_6 = os.path.join(base_output_path, output_layer_name_repair)
0575: 
0576:     processing.run("native:fixgeometries", {
0577:         'INPUT': input_path_6,
0578:         'METHOD': 1,
0579:         'OUTPUT': output_path_6
0580:     })
0581: 
0582: 
0583: def difference_between_layers(base_output_path, base_layer, overlay_layer, output_file_name, variable_to_area):
```


### `gdal:polygonize` -> `L3_01_09_03` Raster-Vector Conversion

- 草案场景：`conservative`。
- 复核判断：`accept_mapping_after_authority`。
- 依据：真实调用使用 INPUT/BAND/FIELD/OUTPUT，语义是把栅格像元区域转换为矢量多边形。

**样本 1**

- 路径：`/home/yll/GEE/爬取GIS代码/QGIS_ArcGIS_Textbook_Candidates_Broad/downloaded_scripts_strict/script_0008817.py`
- source_root：`textbook_strict`；primary_layer：`explicit_processing_multistep_catalog_exact`；duplicate_count：`1`；hash：`00141e3f7b35...`
- 调用：`processing.run` 第 135-135 行；scope：`def createTreeMap`
- 参数键：`INPUT`, `BAND`, `FIELD`, `EIGHT_CONNECTEDNESS`, `EXTRA`, `OUTPUT`
- 输出角色：`assigned` target=`tempd` subscript=`None`

```python
0132:     #tempd = tempfile.TemporaryFile()
0133:     #tempd = tempd.name+'.shp'
0134:     focalMax = focalMaximaCHM(input_chm,distance,convert)
0135:     tempd = processing.run("gdal:polygonize", {'INPUT':focalMax,'BAND':1,'FIELD':'CHM','EIGHT_CONNECTEDNESS':False,'EXTRA':'','OUTPUT':'TEMPORARY_OUTPUT'})
0136:     
0137:     delNulls(tempd['OUTPUT'])
0138:     tempd = processing.run("native:centroids", {'INPUT':tempd['OUTPUT'],'ALL_PARTS':False,'OUTPUT':'TEMPORARY_OUTPUT'})
```

**样本 2**

- 路径：`/home/yll/GEE/爬取GithubQGIS/合并脚本/QGIS_merged_dedup_by_index/downloaded_scripts/script_7510.py`
- source_root：`github_merge`；primary_layer：`explicit_processing_multistep_catalog_exact`；duplicate_count：`1`；hash：`003f6972048e...`
- 调用：`processing.run` 第 122-135 行；scope：`class InundationBoundaryAlgorithm / def processAlgorithm`
- 参数键：`INPUT`, `BAND`, `FIELD`, `EIGHT_CONNECTEDNESS`, `EXTRA`, `OUTPUT`
- 输出角色：`assigned` target=`poly_result` subscript=`None`

```python
0119: 
0120:         # Step 2: Polygonize the mask raster
0121:         feedback.pushInfo("Step 2: Polygonizing flood mask...")
0122:         poly_result = processing.run(
0123:             "gdal:polygonize",
0124:             {
0125:                 "INPUT": mask_raster,
0126:                 "BAND": 1,
0127:                 "FIELD": "DN",  # Default field for gdal:polygonize containing the pixel value
0128:                 "EIGHT_CONNECTEDNESS": False,
0129:                 "EXTRA": "",
0130:                 "OUTPUT": "TEMPORARY_OUTPUT",
0131:             },
0132:             context=context,
0133:             feedback=feedback,
0134:             is_child_algorithm=True,
0135:         )
0136: 
0137:         poly_layer = poly_result["OUTPUT"]
0138: 
```

**样本 3**

- 路径：`/home/yll/GEE/爬取多源数据源/QGIS_Model_Tutorial_Workflows/downloaded_scripts/script_55943.py`
- source_root：`model_tutorial`；primary_layer：`explicit_processing_multistep_catalog_exact`；duplicate_count：`1`；hash：`01c28533d7ee...`
- 调用：`processing.run` 第 298-302 行；scope：`class StreamReachAlgorithm / def processAlgorithm`
- 参数键：`INPUT`, `BAND`, `FIELD`, `OUTPUT`
- 输出角色：`assigned` target=`vector_catchments` subscript=`OUTPUT`

```python
0295:             
0296:         QgsProject.instance().addMapLayer(rlayer)
0297: 
0298:         vector_catchments=processing.run("gdal:polygonize", {
0299:         'INPUT':rlayer, 
0300:         'BAND': 1,
0301:         'FIELD':"Value",
0302:         'OUTPUT': 'TEMPORARY_OUTPUT'}, context=context, feedback=feedback)['OUTPUT']
0303:         
0304:         
0305:         fixed_geometry=processing.run("native:fixgeometries", {
```


### `gdal:rasterize` -> `L3_01_09_03` Raster-Vector Conversion

- 草案场景：`conservative`。
- 复核判断：`accept_mapping_after_authority`。
- 依据：真实调用使用 INPUT/FIELD或BURN/EXTENT/尺寸/OUTPUT，语义是把矢量几何烧录为栅格。

**样本 1**

- 路径：`/home/yll/GEE/爬取多源数据源/QGIS_Plugins_GitLab_Supplement/downloaded_scripts/official_plugins/plugin_0004880.py`
- source_root：`gitlab_supplement`；primary_layer：`explicit_processing_multistep_catalog_exact`；duplicate_count：`1`；hash：`0078e317a31f...`
- 调用：`processing.run` 第 145-159 行；scope：`class RasterMakerDialog / def _create_buffer_raster`
- 参数键：`BURN`, `DATA_TYPE`, `EXTENT`, `EXTRA`, `FIELD`, `HEIGHT`, `INIT`, `INPUT`, `INVERT`, `NODATA`, `OPTIONS`, `OUTPUT`, `UNITS`, `WIDTH`
- 输出角色：`assigned` target=`res` subscript=`None`

```python
0142: 
0143:         dem_epsg = dem_layer.crs().authid()
0144:         extent = fix_extent(dem_layer.extent().asWktCoordinates()) + f' [{dem_epsg}]'
0145:         res = processing.run('gdal:rasterize',
0146:                              {'BURN': 0,
0147:                               'DATA_TYPE': 5,
0148:                               'EXTENT': extent,
0149:                               'EXTRA': '',
0150:                               'FIELD': None if binary else 'height',
0151:                               'HEIGHT': dem_layer.height(),
0152:                               'INIT': None,
0153:                               'INPUT': buffer_layer.metadataUri(),
0154:                               'INVERT': False,
0155:                               'NODATA': -9999,
0156:                               'OPTIONS': '',
0157:                               'OUTPUT': 'TEMPORARY_OUTPUT',
0158:                               'UNITS': 0,
0159:                               'WIDTH': dem_layer.width()})
0160:         filled_no_data = self._replace_no_data(res['OUTPUT'])
0161:         layer = QgsRasterLayer(filled_no_data, 'buffer_raster_bin' if binary else 'buffer_raster')
0162:         layer.setCrs(dem_layer.crs())
```

**样本 2**

- 路径：`/home/yll/GEE/爬取GIS代码/QGIS_ArcGIS_Textbook_Candidates_Broad/downloaded_scripts_strict/script_0003933.py`
- source_root：`textbook_strict`；primary_layer：`explicit_processing_multistep_catalog_exact`；duplicate_count：`1`；hash：`00a4321eac1b...`
- 调用：`processing.run` 第 934-939 行；scope：`class WorkflowBase / def _rasterize`
- 参数键：无字面量参数键
- 输出角色：`side_effect_or_unassigned` target=`expr` subscript=`None`

```python
0931:         log_message(f"Rasterize parameters: {params}")
0932:         # 'OUTPUT':'TEMPORARY_OUTPUT'})
0933: 
0934:         processing.run(
0935:             "gdal:rasterize",
0936:             params,
0937:             context=self.context,
0938:             feedback=QgsProcessingFeedback(),
0939:         )
0940:         log_message(f"Rasterize Parameter: {params}")
0941:         log_message(f"Rasterize complete for: {output_path}")
0942:         log_message(f"Created raster: {output_path}")
```

**样本 3**

- 路径：`/home/yll/GEE/爬取多源数据源/QGIS_Model_Tutorial_Workflows/downloaded_scripts/script_55740.py`
- source_root：`model_tutorial`；primary_layer：`explicit_processing_multistep_catalog_exact`；duplicate_count：`1`；hash：`01bf4d16e2b3...`
- 调用：`processing.run` 第 462-465 行；scope：`class CSV2Grid_dialog / def csv2grid_go`
- 参数键：`INPUT`, `FIELD`, `BURN`, `USE_Z`, `UNITS`, `WIDTH`, `HEIGHT`, `EXTENT`, `NODATA`, `OPTIONS`, `DATA_TYPE`, `INIT`, `INVERT`, `EXTRA`, `OUTPUT`
- 输出角色：`assigned` target=`result` subscript=`None`

```python
0459:             #print(resolution)
0460:             self.txtError.append("Resolution of output Grid = " + str(resolution))
0461:             output_file_grid = output_file_name.replace(".shp", ".img", 1)
0462:             result = processing.run("gdal:rasterize", {'INPUT':output_file_name,'FIELD':'depth2','BURN':0,'USE_Z':False,'UNITS':1,
0463:                                               'WIDTH':resolution,'HEIGHT':resolution,'EXTENT':None,'NODATA':0,
0464:                                               'OPTIONS':'','DATA_TYPE':5,'INIT':None,'INVERT':False,'EXTRA':'',
0465:                                               'OUTPUT':'TEMPORARY_OUTPUT'})
0466:             tempfile5 = result['OUTPUT']
0467:             processing.run("gdal:fillnodata", {'INPUT':tempfile5,'BAND':1,'DISTANCE':2,'ITERATIONS':0,
0468:                                                'NO_MASK':False,'MASK_LAYER':None,'OPTIONS':'','EXTRA':'',
```


### `native:createspatialindex` -> `L3_01_07_01` Add Spatial Index

- 草案场景：`support_boundary`。
- 复核判断：`defer_training_support_step`。
- 依据：真实调用通常只接 INPUT，作用是创建空间索引以加速后续查询；它支撑流程，但不是面向任务的分析输出。

**样本 1**

- 路径：`/home/yll/GEE/爬取GIS代码/QGIS_ArcGIS_Textbook_Candidates_Broad/downloaded_scripts_strict/script_0008817.py`
- source_root：`textbook_strict`；primary_layer：`explicit_processing_multistep_catalog_exact`；duplicate_count：`1`；hash：`00141e3f7b35...`
- 调用：`processing.run` 第 139-139 行；scope：`def createTreeMap`
- 参数键：`INPUT`
- 输出角色：`side_effect_or_unassigned` target=`expr` subscript=`None`

```python
0136:     
0137:     delNulls(tempd['OUTPUT'])
0138:     tempd = processing.run("native:centroids", {'INPUT':tempd['OUTPUT'],'ALL_PARTS':False,'OUTPUT':'TEMPORARY_OUTPUT'})
0139:     processing.run("native:createspatialindex", {'INPUT':tempd['OUTPUT']})
0140: 
0141:     return tempd['OUTPUT']
0142: 
```

**样本 2**

- 路径：`/home/yll/GEE/爬取多源数据源/QGIS_Model_Tutorial_Workflows/downloaded_scripts/script_55740.py`
- source_root：`model_tutorial`；primary_layer：`explicit_processing_multistep_catalog_exact`；duplicate_count：`1`；hash：`01bf4d16e2b3...`
- 调用：`processing.run` 第 430-430 行；scope：`class CSV2Grid_dialog / def csv2grid_go`
- 参数键：`INPUT`
- 输出角色：`side_effect_or_unassigned` target=`expr` subscript=`None`

```python
0427:             tempfile3 = newdir + "\\tempfile3.shp"
0428:             tempfile4 = newdir + "\\tempfile4.shp"
0429:             self.txtError.append("Point file indexed")
0430:             processing.run("native:createspatialindex", {'INPUT':output_file_name})
0431:             index = QgsSpatialIndex(infile.getFeatures())
0432:             crs = infile.crs()
0433:             extent = infile.extent()
```

**样本 3**

- 路径：`/home/yll/GEE/爬取GithubQGIS/合并脚本/QGIS_merged_dedup_by_index/downloaded_scripts/script_782.py`
- source_root：`github_merge`；primary_layer：`explicit_processing_multistep_catalog_exact`；duplicate_count：`1`；hash：`050df781a422...`
- 调用：`processing.run` 第 184-186 行；scope：`class ResidentialInductionMetricCalculator / def calc`
- 参数键：`INPUT`
- 输出角色：`side_effect_or_unassigned` target=`expr` subscript=`None`

```python
0181:                 return  # キャンセルチェック
0182: 
0183:             # 空間インデックス作成
0184:             processing.run(
0185:                 "native:createspatialindex", {'INPUT': centroids_all}
0186:             )
0187:             processing.run(
0188:                 "native:createspatialindex", {'INPUT': target_zones_layer}
0189:             )
```


### `native:saveselectedfeatures` -> `L3_07_04_01` Export To Shapefile

- 草案场景：`export_boundary`。
- 复核判断：`defer_training_export_boundary`。
- 依据：真实调用把当前选择集写成新图层，OUTPUT 有时是 TEMPORARY_OUTPUT、有时是文件路径；不能稳定等同 shapefile 导出。

**样本 1**

- 路径：`/home/yll/GEE/爬取GIS代码/QGIS_ArcGIS_Textbook_Candidates_Broad/downloaded_scripts_strict/script_0012288.py`
- source_root：`textbook_strict`；primary_layer：`explicit_processing_multistep_catalog_exact`；duplicate_count：`1`；hash：`00d2299ec0fc...`
- 调用：`processing.run` 第 273-279 行；scope：`class watershed / def processAlgorithm`
- 参数键：`INPUT`, `OUTPUT`
- 输出角色：`assigned` target=`vlayer_occurrence_selected_str` subscript=`OUTPUT`

```python
0270: 
0271:             # Détermine quelles sont les UD touchées par l'occurrence
0272:             vlayer_occurrences_touched.selectByIds([fid])
0273:             vlayer_occurrence_selected_str = processing.run("native:saveselectedfeatures", {
0274:                 'INPUT':vlayer_occurrences_touched,
0275:                 'OUTPUT':'TEMPORARY_OUTPUT'
0276:                 },
0277:                 is_child_algorithm=True,
0278:                 context=context,
0279:                 )["OUTPUT"]
0280:             vlayer_occurrence_selected = QgsProcessingUtils.mapLayerFromString(vlayer_occurrence_selected_str, context)
0281: 
0282:             vlayer_indexUD_touched_str = processing.run("native:extractbylocation", {
```

**样本 2**

- 路径：`/home/yll/GEE/爬取多源数据源/QGIS_Model_Tutorial_Workflows/downloaded_scripts/script_55943.py`
- source_root：`model_tutorial`；primary_layer：`explicit_processing_multistep_catalog_exact`；duplicate_count：`1`；hash：`01c28533d7ee...`
- 调用：`processing.run` 第 271-271 行；scope：`class StreamReachAlgorithm / def processAlgorithm`
- 参数键：`INPUT`, `OUTPUT`
- 输出角色：`assigned` target=`duplicate` subscript=`OUTPUT`

```python
0268:         
0269:         # Adds memory layer with all copied attributes to ToC
0270:         temp.selectAll()
0271:         duplicate=processing.run("native:saveselectedfeatures", {'INPUT': temp, 'OUTPUT': out_stream_reach}, context=context, feedback=feedback)['OUTPUT']
0272:         temp.removeSelection()
0273: 
0274:         QgsProject.instance().removeMapLayer(temp.id())
```

**样本 3**

- 路径：`/home/yll/GEE/爬取GithubQGIS/合并脚本/QGIS_merged_dedup_by_index/downloaded_scripts/script_173.py`
- source_root：`github_merge`；primary_layer：`explicit_processing_multistep_catalog_exact`；duplicate_count：`1`；hash：`02e9b521f9ec...`
- 调用：`processing.run` 第 61-64 行；scope：`def extract_hydroconditioning_inundation`
- 参数键：`INPUT`, `OUTPUT`
- 输出角色：`side_effect_or_unassigned` target=`expr` subscript=`None`

```python
0058:             'METHOD': 0 #creates a new selection
0059:         })
0060: 
0061:         processing.run("native:saveselectedfeatures", {
0062:             'INPUT': horseshoe_layer,
0063:             'OUTPUT': horseshoes_in_mask_path
0064:         })
0065: 
0066:         horseshoes_in_mask = QgsVectorLayer(horseshoes_in_mask_path, "horseshoes_in_mask", "ogr")
0067: 
```

## 后续处理

- `native:reprojectlayer`、`native:fixgeometries`、`gdal:polygonize`、`gdal:rasterize`：可以进入正式 stable-N 扩展草案，但仍需 taxonomy authority 明确批准。
- `native:createspatialindex`：保留为 support/performance 步骤，可用于链完整性，但不建议作为自然语言任务训练目标。
- `native:saveselectedfeatures`：先按 `OUTPUT` 为临时层/文件路径/shapefile 的情况拆分，未拆分前不并入 `Export To Shapefile` 训练目标。
- 本报告只覆盖抽样源码片段复核；不是全量 precision/recall 结论。
