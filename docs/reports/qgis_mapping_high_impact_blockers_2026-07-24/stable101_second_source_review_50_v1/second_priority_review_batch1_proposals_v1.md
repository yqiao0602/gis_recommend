# stable101 Second Batch Priority Review: Batch 1 Proposals

Status: `proposal_only`

Review order: `6, 10, 16, 21, 27, 41, 45, 49, 1, 4`

This document proposes human-review decisions from source evidence. It does not
modify the blank human fields in the source-review pack, create an adjudication
sidecar, grant training admission, call an LLM, or emit training rows.

## Proposed Summary

- accepted: 6 (`#10`, `#16`, `#21`, `#41`, `#45`, `#49`)
- deferred: 2 (`#1`, `#4`)
- rejected current chain: 2 (`#6`, `#27`)

## #6 - Reject Current Chain

- Proposed decision: `rejected`
- Candidate chain: `gdal:polygonize -> native:buffer -> gdal:rasterize`
- Boundary: fail
- Operator order: fail
- Dependency: fail
- Task text: fail
- Evidence: `gdal:polygonize` writes an unbound in-memory output. The following
  `native:buffer` does not consume that output; it consumes `raster_layer`
  directly even though the native buffer algorithm expects vector input.
  `gdal:rasterize` then consumes the buffer result. The comments describe an
  intended polygonize-buffer-rasterize workflow, but the executable source does
  not implement it.
- Reason: the current chain would require correcting the source, not merely
  recovering an omitted edge. Do not create training truth from the intended
  comments.

## #10 - Accept With Rewritten Task Text

- Proposed decision: `accepted`
- Candidate chain: `native:fixgeometries -> native:dissolve -> native:reprojectlayer`
- Boundary: pass
- Operator order: pass
- Dependency: pass
- Existing task text: fail
- Description generation: pass
- Evidence: one `create_alea` function passes `vlayer` through geometry repair,
  dissolves it by occurrence/type/description/intensity fields, and reprojects
  the dissolved output to EPSG:2154.
- Proposed task name: `修复并融合灾害图层后重投影`
- Proposed task description: `修复灾害矢量图层的无效几何，按发生期、灾害类型、描述和强度字段融合要素，并将融合结果重投影到 EPSG:2154。`

## #16 - Accept As A Local Processing Subworkflow

- Proposed decision: `accepted`
- Candidate chain: `gdal:polygonize -> native:intersection`
- Boundary: pass for the local subworkflow only
- Operator order: pass
- Dependency: pass
- Existing task text: fail
- Description generation: pass
- Evidence: custom Python first computes a weathering index and threshold mask.
  The reviewed Processing boundary starts after that custom stage: polygonize
  the mask, then use the polygons as the overlay for intersection with basins.
- Proposed task name: `矢量化风化掩膜并与流域求交`
- Proposed task description: `将已计算的风化阈值掩膜栅格转换为多边形，并把这些多边形与流域边界求交，输出各流域内的风化分区。`
- Boundary note: do not claim that the two-operator chain computes the upstream
  weathering index or mask.

## #21 - Accept As A Four-Node Raster DAG

- Proposed decision: `accepted`
- Candidate chain: `gdal:rastercalculator -> gdal:rasterize -> gdal:rasterize -> gdal:rastercalculator`
- Boundary: pass
- Operator order: pass
- Dependency: pass
- Existing task text: fail
- Description generation: pass
- Evidence: the first calculator derives old/new stand-change classes. The next
  two calls rasterize new and old `hdom` attributes. The final calculator
  consumes all three outputs and applies height and height-difference thresholds
  to identify cleared stands. Cancellation checks do not alter the successful
  execution DAG.
- Proposed task name: `结合林分变化与树高识别采伐区域`
- Proposed task description: `计算新旧林分栅格的变化类别，分别将新旧林分边界中的优势树高字段栅格化，再结合变化类别、旧树高和树高差阈值计算采伐区域分类栅格。`

## #27 - Reject File-Level Chain And Split Examples

- Proposed decision: `rejected`
- Candidate chain: `native:fixgeometries -> native:buffer -> native:intersection`
- Boundary: fail
- Operator order: fail
- Dependency: fail
- Existing task text: fail
- Evidence: the three top-level calls use unrelated hard-coded input and output
  files. The geometry-fix output is not used by buffer or intersection; the
  buffer output is not used by intersection. They are adjacent tutorial
  examples, not one workflow.
- Salvage note: retain the three calls as possible single-step examples after a
  separate single-step review. Do not train the concatenated three-step chain.

## #41 - Accept With A Chain-Faithful Description

- Proposed decision: `accepted`
- Candidate chain: `reprojectlayer x3 -> buffer -> joinbylocationsummary x2 -> fieldcalculator -> reprojectlayer`
- Boundary: pass
- Operator order: pass
- Dependency: pass
- Existing task text: partial; broader than the reviewed chain
- Description generation: pass
- Evidence: rights-of-way, vegetation, and flood layers are reprojected to a
  metric CRS; rights-of-way are buffered; vegetation and flood summaries are
  joined sequentially; a risk score is calculated; the result is reprojected to
  WGS84. Styling and GeoJSON export occur after the reviewed chain.
- Proposed task name: `计算道路用地植被与洪水风险评分`
- Proposed task description: `将道路用地、植被和洪水图层重投影到米制坐标系，对道路用地生成缓冲区，依次汇总相交植被和洪水属性，计算综合风险评分，并将结果重投影到 WGS84。`

## #45 - Accept With A Support-Logic Sidecar

- Proposed decision: `accepted`
- Candidate chain: `native:reprojectlayer -> gdal:cliprasterbyextent -> gdal:rastercalculator`
- Boundary: pass
- Operator order: pass
- Dependency: pass
- Existing task text: fail
- Description generation: pass
- Evidence: the AOI is reprojected to EPSG:4326 and its expanded extent drives
  clipping of ESA WorldCover. The clipped raster becomes calculator input A.
  Python reads the selected roughness lookup CSV and converts it into the raster
  calculator expression.
- Proposed task name: `裁剪土地覆盖并生成曼宁糙率栅格`
- Proposed task description: `将研究区重投影到 WGS84，按扩展后的研究区范围裁剪 ESA WorldCover 栅格，再使用预先选定的土地覆盖到曼宁糙率对照表构造表达式并计算糙率栅格。`
- Sidecar note: CSV parsing and formula construction are deterministic support
  logic, not additional QGIS target operators.

## #49 - Accept The Buffer Helper Boundary

- Proposed decision: `accepted`
- Candidate chain: `native:reprojectlayer -> native:buffer -> native:reprojectlayer`
- Boundary: pass for `build_buffer`
- Operator order: pass
- Dependency: pass
- Existing task text: partial; describes the wider pipeline
- Description generation: pass
- Evidence: `build_buffer` reprojects the input gate layer to a metric CRS,
  buffers it by the requested distance, then reprojects the buffer to WGS84 and
  returns it.
- Proposed task name: `在米制坐标系中生成校门缓冲区`
- Proposed task description: `将校门图层重投影到米制坐标系，按指定距离生成缓冲区，再将缓冲结果重投影到 WGS84。`

## #1 - Defer Until Dynamic Operator Recovery

- Proposed decision: `deferred`
- Candidate chain omits a required dynamic call between
  `gdal:warpreproject` and `native:reclassifybytable`.
- Boundary: uncertain
- Operator order: fail for the current fixed chain
- Dependency: uncertain
- Existing task text: not usable until recovery
- Evidence: lines 203-241 choose one of `sagang:geomorphons` or
  `saga:geomorphons` with alternative input parameter names and execute
  `processing.run(alg_id, ...)`. Its output `saga_target` is the direct input to
  reclassification. Omitting this operator changes the workflow semantics.
- Recovery action: resolve provider-specific Geomorphons IDs and mappings,
  preserve the fallback alternatives as a branch/DAG, then review the complete
  chain and write a constrained task description.

## #4 - Defer Until Call-Graph And Conditional-DAG Recovery

- Proposed decision: `deferred`
- Current candidate begins with two `renametablefield` calls because their helper
  definition appears earlier in the file; that is not runtime order.
- Boundary: uncertain
- Operator order: fail
- Dependency: uncertain
- Existing task text: fail
- Evidence: `main` conditionally assigns a CRS, repairs and conditionally
  reprojects municipality geometry, promotes it to multipart, applies low-level
  unique-ID cloning, conditionally reprojects NUTS, performs the spatial join,
  then calls `rename_reserved_fid`. The helper may execute zero, one, or two
  rename algorithms. The final field calculator is also conditional on available
  year fields, followed by another rename/ID-clone stage.
- Recovery action: expand the `main -> rename_reserved_fid` calls, move rename
  operations to their actual call sites, represent conditional CRS and field
  branches, and keep low-level ID cloning as support/API-pattern evidence before
  reconsidering training admission.

## Confirmation Gate

No decision in this document is authoritative until jointly confirmed. After
confirmation, write a separate adjudication sidecar; do not overwrite the source
review JSONL, preclassification JSONL, or their blank human fields.
