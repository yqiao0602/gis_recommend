# stable101 Second Batch Priority Review: Batch 2 Proposals

Status: `proposal_only`

Review order: `5, 8, 11, 12, 15, 17, 20, 23, 26, 28`

This document proposes human-review decisions from source evidence. It does not
modify source-review human fields, create an adjudication sidecar, grant
training admission, call an LLM, or emit training rows.

## Proposed Summary

- accepted: 6 (`#5`, `#11`, `#12`, `#17`, `#23`, `#28`)
- deferred: 2 (`#15`, `#20`)
- rejected current chain: 2 (`#8`, `#26`)

## #5 - Accept The Conditional Reprojection Branch

- Proposed decision: `accepted`
- Candidate chain: `native:reprojectlayer -> gdal:rasterize`
- Boundary: pass when the input CRS differs from the target CRS
- Operator order: pass
- Dependency: pass
- Existing task text: fail
- Evidence: `rasterize_AOI` conditionally reprojects the input polygon layer,
  then always rasterizes the resulting layer to a binary mask using the target
  georeference, pixel size, extent, CRS, and NoData value.
- Proposed task name: `重投影研究区并生成参考网格掩膜`
- Proposed task description: `当研究区矢量图层的坐标系与目标坐标系不一致时先进行重投影，再按参考栅格的范围、像元大小和坐标系将研究区栅格化为二值掩膜。`

## #8 - Reject The Two-Step Candidate

- Proposed decision: `rejected`
- Candidate chain: `gdal:rasterize -> gdal:polygonize`
- Boundary: fail
- Operator order: fail as a direct Processing chain
- Dependency: fail
- Existing task text: fail
- Evidence: `rasterizeVector` is called inside `loggingZone` to create an
  intermediate mask. The later `raster2vector` call receives `bzone`, which is
  produced after GDAL array loading, NumPy masking, Whitebox watershed calls,
  percentile loops, mass-flux calculations, and `array2raster`. It does not
  consume the rasterize output directly.
- Salvage note: retain rasterize and polygonize as separately reviewable local
  operations, or model the intervening API/NumPy/Whitebox workflow first. Do
  not train the current two-step chain.

## #11 - Accept A Repeated Zonal-Statistics Unit

- Proposed decision: `accepted`
- Candidate chain: `gdal:polygonize -> native:zonalstatisticsfb`
- Boundary: pass as one mask/feature-raster unit
- Operator order: pass
- Dependency: pass
- Existing task text: partial; rewrite for fidelity
- Evidence: the main entrypoint vectorizes each binary mask, then passes the
  vector path into `calculate_zonal_statistics`, which repeatedly calls
  `calculate_zonal_statistics_vector` for each feature raster. The polygonized
  zones are the direct zonal-statistics input.
- Proposed task name: `矢量化掩膜并计算特征栅格分区统计`
- Proposed task description: `将二值掩膜栅格转换为分区多边形，并针对每个特征栅格在这些分区内计算均值、标准差、最小值、最大值和极差。`
- Loop note: one fixed chain represents one mask/feature-raster unit; source
  grouping must keep repeated units from the same file together.

## #12 - Accept The NDVI Threshold Subworkflow

- Proposed decision: `accepted`
- Candidate chain: `gdal:rastercalculator -> gdal:polygonize`
- Boundary: pass through polygonization
- Operator order: pass
- Dependency: pass
- Existing task text: partial; rewrite for fidelity
- Evidence: raster calculator writes `thresholded_raster` using
  `A*(A > 0.5)`. Polygonize then uses that exact path as input. Later QGIS API
  code removes zero-valued polygons and is outside the reviewed two-operator
  boundary.
- Proposed task name: `提取高 NDVI 像元并矢量化`
- Proposed task description: `使用栅格计算器保留 NDVI 大于 0.5 的像元并生成阈值栅格，再将该阈值栅格转换为多边形。`
- Boundary note: do not claim that this two-step chain performs the later
  low-level deletion of zero-valued polygons.

## #15 - Defer And Split Two Optional Workflows

- Proposed decision: `deferred`
- Current candidate concatenates two optional output branches.
- Boundary: fail for the current combined chain
- Operator order: fail
- Dependency: uncertain until split and recovery
- Existing task text: fail
- Evidence: the optional `StreamPolygons` branch is
  `polygonize -> extract DN>0 -> dissolve`. A separate optional `Catch` branch
  first runs the omitted `grass7:r.water.outlet`, then conditionally builds a
  catchment-vector chain with area/time fields, elevation statistics, optional
  slope/aspect statistics, and outlet elevation. The two outputs are not one
  serial workflow, and the current candidate also omits required GRASS calls.
- Recovery action: emit a three-step stream-polygon unit and a separate
  catchment-vector DAG beginning with `grass7:r.water.outlet`; preserve optional
  slope/aspect branches before mapping and task-text review.

## #17 - Accept A Per-Outlet Catchment Unit

- Proposed decision: `accepted`
- Candidate chain: `saga:upslopearea -> gdal:polygonize`
- Boundary: pass through catchment polygonization
- Operator order: pass
- Dependency: pass
- Existing task text: fail
- Evidence: for every outlet point, SAGA computes an upslope-area raster from
  its coordinates and the DEM; polygonize directly consumes the returned
  `AREA`. QGIS API code then selects `DN=100` polygons and writes a shapefile.
- Proposed task name: `按出口点提取并矢量化上游汇水区`
- Proposed task description: `针对每个出口点，基于数字高程模型计算其上游汇水区栅格，并将该汇水区栅格转换为多边形。`
- Boundary note: low-level `DN=100` selection and file writing remain support
  evidence outside the two-operator target chain.

## #20 - Defer And Split K-Factor And HSG Branches

- Proposed decision: `deferred`
- Candidate chain: `gdal:rasterize -> native:fieldcalculator -> gdal:rasterize`
- Boundary: fail as one serial chain
- Operator order: fail for the combined candidate
- Dependency: fail between the first and second calls
- Existing task text: fail
- Evidence: when `KFactorField` is supplied, the first rasterize independently
  creates the K-factor raster. When `HydrologicSoilGroupField` is supplied,
  field calculator maps soil-group labels to numeric codes and the second
  rasterize consumes that result. The K-factor output never feeds the HSG
  branch, and either branch can be absent.
- Recovery action: split into an optional one-step K-factor rasterization unit
  and a two-step HSG code-calculation/rasterization unit.

## #23 - Accept A Per-Raster Aggregation Unit

- Proposed decision: `accepted`
- Candidate chain: `native:fixgeometries -> native:retainfields -> native:zonalstatisticsfb`
- Boundary: pass for one aggregation raster
- Operator order: pass
- Dependency: pass
- Existing task text: fail
- Evidence: `run` first fixes aggregation polygons and retains only `fid`.
  Each enabled GeoE3 raster then passes that cleaned layer into `aggregate`,
  which computes majority zonal statistics. The same cleaned layer may be used
  for up to four independent raster products.
- Proposed task name: `清理分区多边形并汇总栅格多数值`
- Proposed task description: `修复分区多边形的无效几何，仅保留分区标识字段，再针对一个 GeoE3 栅格计算各分区内的多数像元值。`
- Repeat note: one training unit represents one raster aggregation; all units
  from this source must remain in one source group during splitting.

## #26 - Reject Mutually Exclusive Raster And Vector Paths

- Proposed decision: `rejected`
- Candidate chain: `gdal:translate -> native:fixgeometries`
- Boundary: fail
- Operator order: fail
- Dependency: fail
- Existing task text: fail
- Evidence: `gdal:translate` belongs to `clipLayerToDEM` and only runs for a
  raster layer when `clipToDEM` is enabled. `native:fixgeometries` belongs to
  the vector-file copy path when `runFix` is enabled. In one file-loading call,
  raster and non-raster branches are mutually exclusive; the translate output
  cannot feed geometry repair.
- Salvage note: keep raster clipping and vector geometry repair as separate
  operations. Reject only the concatenated two-step candidate.

## #28 - Accept The Nonzero-Buffer Branch With WFS Support

- Proposed decision: `accepted`
- Candidate chain: `native:fixgeometries -> native:dissolve -> native:buffer -> native:extractbylocation`
- Boundary: pass when the requested buffer distance is nonzero
- Operator order: pass
- Dependency: pass with an external-data support step
- Existing task text: fail
- Evidence: the selected area is repaired and dissolved, then conditionally
  buffered. Its extent is used to retrieve cadastral parcels from a WFS, and
  `extractbylocation` selects parcels intersecting the processed area.
- Proposed task name: `按缓冲后的区域提取地籍宗地`
- Proposed task description: `修复并融合选择区域的几何，在缓冲距离非零时生成缓冲区，按处理区域范围获取地籍宗地图层，并提取与该区域相交的宗地。`
- Sidecar note: `connect_to_wfs` and scratch-layer conversion are deterministic
  support/data-access steps, not additional QGIS target operators.

## Confirmation Gate

No decision in this document is authoritative until jointly confirmed. After
confirmation, write a separate batch-2 adjudication sidecar; do not overwrite
the source-review JSONL, preclassification JSONL, batch-1 sidecar, or blank
human fields.
