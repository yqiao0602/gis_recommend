# stable101 Second Batch Priority Review: Batch 4 Proposals

Status: `proposal_only`

Review order: `13, 18, 31, 34, 47, 19, 22, 24, 25, 38`

This document proposes human-review decisions from source evidence. It does not
modify source-review human fields, create an adjudication sidecar, grant
training admission, call an LLM, or emit training rows.

## Proposed Summary

- accepted: 3 (`#24`, `#25`, `#38`)
- deferred: 7 (`#13`, `#18`, `#31`, `#34`, `#47`, `#19`, `#22`)
- rejected current chain: 0

## #13 - Defer Two Independent Polygonize Helpers

- Proposed decision: `deferred`
- Candidate chain: `gdal:polygonize -> gdal:polygonize`
- Boundary: fail as one file-level chain
- Operator order: not applicable across helpers
- Dependency: fail for the concatenated candidate
- Existing task text: partial
- Evidence: `raster2vector` and `raster2vector2` are separate functions. Each
  independently polygonizes its own input raster; the first then computes
  areas and the second has a different downstream low-level geometry path. No
  output from the first function feeds the second.
- Recovery action: split into two one-step polygonize units and keep each
  helper's area/geometry support logic as a sidecar.

## #18 - Defer Clip And Edge-Raster Helpers

- Proposed decision: `deferred`
- Candidate chain: `gdal:cliprasterbymasklayer -> gdal:polygonize`
- Boundary: fail as one file-level chain
- Operator order: not established
- Dependency: fail until caller relation is recovered
- Existing task text: fail
- Evidence: `clip_raster` calls `gdal:cliprasterbymasklayer` and returns, while
  `compute_edge_raster` opens a raster with GDAL, performs low-level edge
  processing, and only then calls `gdal:polygonize`. The two helpers have no
  direct call edge in the reviewed source.
- Recovery action: split the clip helper from the edge-raster helper; retain
  the GDAL edge computation boundary before considering polygonize admission.

## #31 - Defer Band Construction And Reprojection Helpers

- Proposed decision: `deferred`
- Candidate chain: `native:mergevectorlayers -> native:dissolve -> native:difference -> native:mergevectorlayers -> native:reprojectlayer`
- Boundary: fail as one file-level chain
- Operator order: fail across helper scopes
- Dependency: uncertain until split and loop recovery
- Existing task text: partial
- Evidence: `_merge_layers` is an independent merge helper; `_create_bands`
  repeatedly dissolves configured ranges, differences adjacent ranges, adds
  distance attributes with low-level edits, and merges the resulting bands.
  `reproject_isochrones` is a separate CRS helper, not a downstream step of
  the final merge. Range count is configuration-dependent.
- Recovery action: split merge, band construction, and reprojection units;
  recover repeated dissolve/difference cardinality before fixed-sequence
  training admission.

## #34 - Defer Three Independent Raster/Vector Utilities

- Proposed decision: `deferred`
- Candidate chain: `gdal:warpreproject -> native:reprojectlayer -> gdal:cliprasterbymasklayer`
- Boundary: fail as one file-level chain
- Operator order: not established
- Dependency: fail across independent utility functions
- Existing task text: partial
- Evidence: `reproject_raster`, `reproject_vector`, and `cut_raster` are
  standalone functions. Their inputs and outputs are not connected by a local
  entrypoint in the reviewed file.
- Recovery action: retain three independent one-step candidates and only
  create a multi-step row if a caller proves a data edge.

## #47 - Defer Impact-Map Branch Splitting

- Proposed decision: `deferred`
- Candidate chain: `gdal:cliprasterbyextent -> gdal:warpreproject -> native:reprojectlayer -> gdal:warpreproject`
- Boundary: fail as one file-level chain
- Operator order: pass only for the first local pair
- Dependency: fail across helper scopes
- Existing task text: fail
- Evidence: `process_raster_for_impactmap` directly clips a raster by extent and
  then warps that clipped raster to the output resolution. `reproject_layers`
  separately reprojects a vector layer and a raster layer; those calls are not
  downstream of the impact-map pair.
- Recovery action: split the clip-to-warp local chain from vector/raster
  reprojection helpers and preserve their independent CRS guards.

## #19 - Defer Rasterize With Low-Level RLE Processing

- Proposed decision: `deferred`
- Candidate chain: `native:translategeometry -> gdal:rasterize -> gdal:cliprasterbymasklayer`
- Boundary: fail for the fixed three-step target
- Operator order: uncertain
- Dependency: API-pattern and loop dependency unresolved
- Existing task text: fail
- Evidence: the model first creates an intersection/grid result, optionally
  translates the grid, then rasterizes one selected intersection feature per
  tile inside a loop. Optional mosaic clipping uses the translated grid as a
  mask, while RLE encoding and raster-array conversion occur between calls.
  `translategeometry` is not the direct input of `gdal:rasterize`.
- Recovery action: review model-child outputs and per-tile cardinality; keep
  raster-array/RLE code outside the target operator sequence until an
  API-pattern rule describes it faithfully.

## #22 - Defer Conditional Raster Preparation And Calculator Logic

- Proposed decision: `deferred`
- Candidate chain: `gdal:warpreproject -> gdal:rasterize -> gdal:assignprojection -> gdal:cliprasterbymasklayer -> gdal:warpreproject -> gdal:warpreproject`
- Boundary: fail for the fixed concatenated chain
- Operator order: branch-dependent
- Dependency: unresolved low-level raster-calculator and conditional branches
- Existing task text: fail
- Evidence: byte conversion, crop, and rasterize-mask options are conditional.
  When rasterize-mask is enabled, a low-level `QgsRasterCalculator` combines
  the source and mask rasters before `gdal:assignprojection`; otherwise the
  direct clip-mask branch runs. Two later warps independently aggregate the
  result to 10 m and 1.5 m resolutions.
- Recovery action: separate conversion, rasterize-mask/calculator, direct
  clip-mask, and resolution-output branches; admit only after reviewed
  API-pattern and conditional-DAG rules exist.

## #24 - Accept The Explicit Dual-Year Boundary DAG

- Proposed decision: `accepted`
- Candidate chain: explicit 2018/2025 branches of `native:extractbyexpression`, `native:intersection`, `native:dissolve`, `native:refactorfields`, `native:fixgeometries`, `native:promotetomulti`, followed by final refactor/dissolve outputs
- Boundary: pass for the exported Processing model DAG
- Operator order: pass as two parallel year branches followed by final outputs
- Dependency: pass
- Existing task text: fail; rewrite required
- Evidence: the exported model makes two year-specific branches explicit,
  joins them through separate configured Processing outputs, then performs
  deterministic field refactoring and dissolve steps. `QgsExpression` calls
  only construct field/value parameters; they are support configuration, not
  hidden geometry operations.
- Proposed task name: `按年份整理并融合海床边界`
- Proposed task description: `分别提取并整理两个年份的边界图层，按年份分支执行相交、几何修复、转为多部件和融合，再统一整理字段并输出年度边界结果。`
- Boundary note: the two year branches remain a DAG and must not be flattened
  as a false single-input linear chain.

## #25 - Accept The Explicit MPA/SAC Protection-Area DAG

- Proposed decision: `accepted`
- Candidate chain: dual `native:refactorfields -> native:extractbyattribute -> native:fixgeometries`, then `native:mergevectorlayers -> native:refactorfields -> native:dissolve -> native:refactorfields`
- Boundary: pass for the exported Processing model DAG
- Operator order: pass with two parallel source branches and a shared merge
- Dependency: pass
- Existing task text: fail; rewrite required
- Evidence: SAC and MPA inputs are separately refactored, filtered by attribute,
  and geometry-fixed. Both outputs feed `mergevectorlayers`; the merged layer
  then flows through field refactoring, dissolve, and final field refactoring.
  `QgsExpression` is used only to specify fields and filter values.
- Proposed task name: `筛选并融合 MPA 与 SAC 保护区`
- Proposed task description: `分别整理 MPA 和 SAC 保护区字段并按属性筛选，修复两类图层几何后合并，融合保护区边界并输出统一字段结果。`
- Boundary note: preserve the two source branches and their merge dependency;
  do not treat the repeated operator IDs as repeated execution of one serial
  input.

## #38 - Accept Spatial Preparation Before Length Sidecar

- Proposed decision: `accepted`
- Candidate chain: `native:reprojectlayer -> native:clip -> native:reprojectlayer`
- Boundary: pass through the measurement-CRS preparation step
- Operator order: pass
- Dependency: pass
- Existing task text: partial; rewrite for fidelity
- Evidence: the remote railway layer is conditionally reprojected to the
  boundary CRS, clipped by the boundary, and then reprojected to EPSG:3857 for
  length measurement. Adding `len_km` and `total_km` fields is low-level
  sidecar logic after the spatial chain and is excluded from the target labels.
- Proposed task name: `裁剪铁路并转换到长度测量坐标系`
- Proposed task description: `将远程铁路图层按需重投影到边界图层坐标系后执行裁剪，再将裁剪结果重投影到 EPSG:3857，供后续长度计算使用。`
- Boundary note: remote provider access and field-length calculation remain
  support sidecars, not additional target operators.

## Confirmation Gate

No decision in this document is authoritative until jointly confirmed. After
confirmation, write a separate batch-4 adjudication sidecar; do not overwrite
the source-review JSONL, preclassification JSONL, or earlier batch sidecars.
