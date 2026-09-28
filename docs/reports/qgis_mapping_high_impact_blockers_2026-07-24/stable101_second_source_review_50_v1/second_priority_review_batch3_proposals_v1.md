# stable101 Second Batch Priority Review: Batch 3 Proposals

Status: `proposal_only`

Review order: `29, 30, 32, 33, 35, 37, 42, 50, 2, 3`

This document proposes human-review decisions from source evidence. It does not
modify source-review human fields, create an adjudication sidecar, grant
training admission, call an LLM, or emit training rows.

## Proposed Summary

- accepted: 3 (`#30`, `#32`, `#37`)
- deferred: 7 (`#29`, `#33`, `#35`, `#42`, `#50`, `#2`, `#3`)
- rejected current chain: 0

## #29 - Defer The Progressive Depth-Band Loop

- Proposed decision: `deferred`
- Candidate chain: `native:fixgeometries -> native:savefeatures -> native:mergevectorlayers`
- Boundary: fail for the current static chain
- Operator order: fail
- Dependency: uncertain until call-graph and loop recovery
- Existing task text: fail
- Evidence: module execution fixes `depthareas` before entering `range(1, 7)`.
  Each band then conditionally runs dynamically constructed
  `native:difference` calls, merges area/contour/sounding layers, strips fields,
  and only then saves three outputs. The candidate follows helper-definition
  order, places save before merge, omits difference, and compresses repeated
  calls into one occurrence.
- Recovery action: resolve the `native:{cmd}` calls, recover the fixed six-band
  control-flow graph, and either expand it faithfully or split area, contour,
  and sounding templates under a cardinality-aware schema.

## #30 - Accept Geometry Repair Followed By Dissolve

- Proposed decision: `accepted`
- Candidate chain: `native:fixgeometries -> native:dissolve`
- Boundary: pass for the successful geometry-cleanup branch
- Operator order: pass
- Dependency: pass
- Existing task text: fail
- Evidence: the method writes generated hotspot polygons, repairs that exact
  GeoJSON into `fixed_polygon_layer_path`, then passes the repaired path to
  dissolve with `SEPARATE_DISJOINT=True`. The exception path writes an unchecked
  fallback and is outside the successful two-step branch.
- Proposed task name: `修复并融合热点多边形`
- Proposed task description: `修复生成的热点多边形中的无效几何，再融合修复结果，并将不相连的几何部分保留为独立要素。`

## #32 - Accept Reprojection And Study-Area Clipping

- Proposed decision: `accepted`
- Candidate chain: `native:reprojectlayer -> native:clip`
- Boundary: pass for the OSM line-response branch
- Operator order: pass
- Dependency: pass
- Existing task text: partial; rewrite for fidelity
- Evidence: `process_response` dispatches line output to
  `process_line_response`, which copies the OSM line layer, reprojects it from
  EPSG:4326 to the configured output CRS, and passes the returned in-memory
  layer directly to `_clip_to_study_area`. The clip uses that layer as `INPUT`
  and an AOI memory layer as `OVERLAY`.
- Proposed task name: `重投影并裁剪下载的 OSM 线要素`
- Proposed task description: `将下载的 OSM 线要素从 EPSG:4326 重投影到目标坐标系，再按研究区多边形裁剪，保留研究区内的线要素。`
- Boundary note: missing or invalid study-area data follows a documented
  unclipped fallback and does not invalidate the successful clip branch.

## #33 - Defer Mutually Exclusive Buffer Workflows

- Proposed decision: `deferred`
- Candidate chain: `native:reprojectlayer -> native:clip -> native:buffer -> native:dissolve -> native:difference -> native:mergevectorlayers`
- Boundary: fail as one serial workflow
- Operator order: fail for the combined candidate
- Dependency: fail between mutually exclusive branches
- Existing task text: partial
- Evidence: `_process_features_for_area` returns immediately through the simple
  regional-buffer branch when `use_simple_buffer` is enabled. The alternative
  network branch conditionally reprojects and clips a road network, invokes an
  external isochrone task, then loops over configured distances to dissolve
  ranges, compute differences, and merge bands. `native:buffer` is not upstream
  of the dissolve/difference/merge chain, and loop cardinality depends on the
  configured distances.
- Recovery action: split the simple-buffer/grid-scoring branch from the network
  isochrone-band branch. Preserve the external network task and low-level grid
  scoring as sidecars, and defer the repeated band chain until cardinality can
  be represented faithfully.

## #35 - Defer And Recover The Curve-Number DAG

- Proposed decision: `deferred`
- Candidate chain: `native:reprojectlayer -> gdal:cliprasterbymasklayer -> gdal:cliprasterbyextent -> gdal:translate -> gdal:warpreproject -> gdal:rastercalculator`
- Boundary: pass only after call-graph recovery
- Operator order: fail
- Dependency: fail for the current order
- Existing task text: pass
- Evidence: source-definition order incorrectly places the final mask clip
  before helper calls. Runtime order conditionally reprojects the AOI, clips ESA
  WorldCover by AOI extent, downloads and translates the soil raster, aligns
  soil to the land-cover grid, calculates Curve Number from both rasters, and
  finally clips the Curve Number raster by the AOI mask.
- Recovery action: emit a DAG with land-cover and soil preparation branches
  joining at `gdal:rastercalculator`, followed by
  `gdal:cliprasterbymasklayer`; retain conditional AOI reprojection and the
  external soil download as control/data-access evidence.

## #37 - Accept Conditional Reprojection And Zonal Statistics

- Proposed decision: `accepted`
- Candidate chain: `native:reprojectlayer -> native:zonalstatisticsfb`
- Boundary: pass through raster aggregation
- Operator order: pass
- Dependency: pass
- Existing task text: partial; rewrite for fidelity
- Evidence: when plot and flood-raster coordinate systems differ, the plot
  layer is reprojected to the raster CRS. Zonal statistics directly consumes
  the resulting `plots_reproj` layer and computes count and sum from the flood
  raster. Later area-comparison fields are low-level QGIS logic outside the
  two-operator boundary.
- Proposed task name: `对齐地块坐标系并统计淹没像元`
- Proposed task description: `当地块图层与洪水栅格的坐标系不一致时先重投影地块，再按地块分区统计洪水栅格的像元数量和值之和。`

## #42 - Defer Runtime Call-Order Recovery

- Proposed decision: `deferred`
- Candidate chain: `native:reprojectlayer -> native:reprojectlayer -> native:savefeatures -> native:clip`
- Boundary: potentially valid after recovery
- Operator order: fail
- Dependency: fail for the current order
- Existing task text: fail
- Evidence: `run_task` first conditionally reprojects the input to the clipper
  CRS, then clips it, conditionally reprojects the clip result to the
  user-selected output CRS, and finally saves the result as a shapefile. Static
  helper-definition order places clip last and therefore does not describe the
  executable chain.
- Recovery action: recover
  `optional reproject -> clip -> optional reproject -> savefeatures`, preserving
  both CRS guards; keep AutoCAD import and DXF fallback outside the QGIS target
  chain.

## #50 - Defer Variable Per-Layer Cardinality

- Proposed decision: `deferred`
- Candidate chain: `native:reprojectlayer -> native:extractbyexpression -> native:mergevectorlayers`
- Boundary: pass as a workflow template, not as a fixed target sequence
- Operator order: pass within each successful execution path
- Dependency: dynamic cardinality not representable
- Existing task text: pass
- Evidence: the task loops over a variable list of GML layers. Reprojection and
  expression filtering each run zero to N times, invalid or empty layers are
  skipped, and merge runs only when more than one layer survives. A fixed
  three-token sequence cannot encode the runtime call counts faithfully.
- Recovery action: retain the source-faithful workflow description, but defer
  admission until repeated per-layer preprocessing plus aggregate merge has a
  cardinality-aware target representation.

## #2 - Defer And Split Independent Hydrology Workflows

- Proposed decision: `deferred`
- Candidate chain: `gdal:warpreproject -> saga:fillsinksxxlwangliu -> native:zonalstatistics -> native:zonalstatistics -> gdal:cliprasterbyextent -> native:fixgeometries -> native:buffer -> native:clip -> native:clip -> gdal:polygonize -> native:zonalstatistics -> native:zonalstatistics`
- Boundary: fail as one file-level chain
- Operator order: fail across disconnected methods
- Dependency: fail for the concatenated candidate
- Existing task text: partial
- Evidence: the calls belong to unrelated methods for DEM resampling, the main
  GRASS/SAGA hydrology path, CDEM download, WFS depot conversion, point-buffer
  construction, CanVec clipping, depot/basin analysis, and a Whitebox fallback.
  The main path also contains seven omitted Processing calls, including GRASS
  fill, watershed, drain, raster-to-vector, outlet, and slope operations. The
  Whitebox path has low-level Whitebox steps between polygonize and statistics.
- Recovery action: split download/support helpers from the GRASS/SAGA and
  Whitebox analysis DAGs. Recover omitted provider calls and mapping first;
  separately review the Whitebox-local polygonize/elevation-statistics and
  slope/statistics units without pretending they are adjacent in the full
  workflow.

## #3 - Defer And Split Wind-Suitability Helpers

- Proposed decision: `deferred`
- Candidate chain: `native:extractbyextent -> native:fixgeometries -> native:clip -> native:reprojectlayer -> gdal:rasterize -> gdal:warpreproject -> native:savefeatures -> native:reprojectlayer -> native:fixgeometries -> native:clip -> native:multiparttosingleparts -> native:reprojectlayer`
- Boundary: fail as one file-level chain
- Operator order: fail across disconnected helpers
- Dependency: fail for the concatenated candidate
- Existing task text: fail
- Evidence: the file contains independent helpers rather than one twelve-step
  workflow. Recoverable local units include conditional AOI extent filtering
  followed by geometry repair and clip; conditional reprojection followed by
  reference-grid rasterization; geometry repair followed by AOI clip; and
  separate raster warp, save-or-reproject, multipart conversion, and vector
  reprojection operations.
- Recovery action: emit separate helper-level units with their CRS/error guards.
  Do not concatenate `_warp_raster_to_reference_grid`, mutually exclusive
  save/reproject branches, or standalone multipart/reprojection helpers onto
  the AOI clipping and rasterization chains.

## Confirmation Gate

No decision in this document is authoritative until jointly confirmed. After
confirmation, write a separate batch-3 adjudication sidecar; do not overwrite
the source-review JSONL, preclassification JSONL, batch-1/batch-2 sidecars, or
blank human fields.
