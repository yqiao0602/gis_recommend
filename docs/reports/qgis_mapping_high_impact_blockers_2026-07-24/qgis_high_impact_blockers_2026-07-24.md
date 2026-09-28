# QGIS高影响阻塞算子映射草案（2026-07-24）

本报告只做影响测算，不修改stable-94/stable-98 authority，不授予训练准入。
初始证据范围为本机已同步的QGIS catalog与当前chain dataset记录；2026-07-24已补充服务器`/home/yll`真实源码片段抽样复核，详见下方“服务器源码片段复核”。

## 影响统计

| 场景 | 完整记录 | 唯一链 | 相对stable-98新增记录 | 相对stable-98新增唯一链 |
|---|---:|---:|---:|---:|
| 严格stable-94 | 766 | 256 | -36 | -14 |
| stable-98草案 | 802 | 270 | 0 | 0 |
| 高影响保守档 | 1442 | 449 | 640 | 179 |
| 高影响扩展档 | 1583 | 496 | 781 | 226 |

## 裁判草案

| 算子 | 场景 | 候选L3 | 置信度 | 训练角色 | 说明 |
|---|---|---|---|---|---|
| `gdal:polygonize` | conservative | `L3_01_09_03` Raster-Vector Conversion | high | core_candidate_after_authority | GDAL polygonize converts raster regions to vector polygons; legacy-350 has Raster-Vector Conversion. |
| `gdal:rasterize` | conservative | `L3_01_09_03` Raster-Vector Conversion | high | core_candidate_after_authority | GDAL rasterize converts vector geometries to raster; same legacy Raster-Vector Conversion class as polygonize. |
| `native:createspatialindex` | support_boundary | `L3_01_07_01` Add Spatial Index | medium | support_step_deferred | QGIS catalog describes spatial-index creation for query performance; legacy-350 has Add Spatial Index, but it is support/performance rather than analytical output. |
| `native:fixgeometries` | conservative | `L3_01_05_02` Repair Geometry | high | core_candidate_after_authority | QGIS catalog says invalid geometry repair; legacy-350 has Repair Geometry, absent from stable-94. |
| `native:reprojectlayer` | conservative | `L3_01_10_01` Project/Reproject | high | core_candidate_after_authority | QGIS catalog says vector CRS reprojection; legacy-350 has Project/Reproject, absent from stable-94. |
| `native:saveselectedfeatures` | support_boundary | `L3_07_04_01` Export To Shapefile | medium | export_step_deferred | QGIS catalog creates an output layer from selected features; current stable-94 has export-to-shapefile but this operator may be temporary-layer copy/export, so it remains a boundary alias. |

## 逐算子影响

| 算子 | 记录 | 唯一链 | 单独加入可解锁记录 | 单独加入可解锁唯一链 | 主要共现阻塞 |
|---|---:|---:|---:|---:|---|
| `gdal:polygonize` | 251 | 67 | 140 | 25 | `native:fixgeometries`:43, `gdal:rasterize`:31, `native:reprojectlayer`:24, `native:saveselectedfeatures`:13, `native:simplifygeometries`:13 |
| `gdal:rasterize` | 261 | 58 | 54 | 15 | `native:reprojectlayer`:99, `qgis:heatmapkerneldensityestimation`:75, `gdal:proximity`:38, `gdal:polygonize`:31, `native:fixgeometries`:25 |
| `native:createspatialindex` | 147 | 48 | 51 | 15 | `native:reprojectlayer`:65, `native:fixgeometries`:44, `native:creategrid`:18, `native:deleteduplicategeometries`:15, `native:polygonstolines`:15 |
| `native:fixgeometries` | 387 | 131 | 117 | 31 | `native:reprojectlayer`:163, `native:snapgeometries`:78, `native:createspatialindex`:44, `gdal:polygonize`:40, `native:deleteholes`:25 |
| `native:reprojectlayer` | 607 | 187 | 243 | 75 | `native:fixgeometries`:154, `native:createspatialindex`:77, `qgis:heatmapkerneldensityestimation`:72, `gdal:rasterize`:60, `native:geometrybyexpression`:25 |
| `native:saveselectedfeatures` | 130 | 50 | 55 | 20 | `native:fixgeometries`:30, `gdal:rasterize`:19, `native:reprojectlayer`:13, `native:createspatialindex`:12, `native:joinattributestable`:11 |

## 结论

- 保守档只包含高置信能力映射，仍需正式taxonomy authority批准后才能进训练。
- `createspatialindex`和`saveselectedfeatures`属于support/export边界；可用于测算潜在覆盖，但不能直接当作训练准入。
- 后续若要进一步扩量，应优先补正式L3 authority和源码片段复核，而不是把历史`optional_l3_sequence`直接当真值。

## 服务器源码片段复核（已完成）

复核脚本：`scripts/review_qgis_high_impact_source_snippets.py`。服务器侧只读读取`/home/yll`真实源码，并通过AST确认存在活动的字面量`processing.run*()`调用；每个目标算子抽取3个`content_sha256`去重源码样本，共18条。

产物：

- `qgis_high_impact_6ops_source_snippet_review_2026-07-24.md`
- `qgis_high_impact_6ops_source_snippet_review_2026-07-24.jsonl`
- `qgis_high_impact_6ops_source_snippet_review_2026-07-24.summary.json`

复核结果：

| 算子 | 源码层唯一命中 | 抽样片段 | 源码复核结论 |
|---|---:|---:|---|
| `native:reprojectlayer` | 1,292 | 3 | 真实调用使用`INPUT`、`TARGET_CRS`、`OUTPUT`，支持`L3_01_10_01` Project/Reproject 映射草案。 |
| `native:fixgeometries` | 924 | 3 | 真实调用使用`INPUT`/`OUTPUT`或`METHOD`/`INPUT`/`OUTPUT`，支持`L3_01_05_02` Repair Geometry 映射草案。 |
| `gdal:polygonize` | 512 | 3 | 真实调用使用`INPUT`、`BAND`、`FIELD`、`OUTPUT`，支持`L3_01_09_03` Raster-Vector Conversion 映射草案。 |
| `gdal:rasterize` | 576 | 3 | 真实调用使用矢量输入、字段/烧录值、范围/尺寸和`OUTPUT`，支持`L3_01_09_03` Raster-Vector Conversion 映射草案。 |
| `native:createspatialindex` | 325 | 3 | 真实调用通常只有`INPUT`，是性能/查询支撑步骤；保留deferred，不单独作为自然语言任务训练目标。 |
| `native:saveselectedfeatures` | 408 | 3 | 真实调用是保存当前选择集为新图层，`OUTPUT`可为临时层或文件路径；未拆分输出类型前不稳定等同shapefile导出，继续deferred。 |

因此，`native:reprojectlayer`、`native:fixgeometries`、`gdal:polygonize`和`gdal:rasterize`可以进入正式stable-N扩展草案；`native:createspatialindex`和`native:saveselectedfeatures`只保留链完整性/support-export证据，不直接训练准入。

## stable-N保守扩展正式草案（已生成）

已基于stable-98草案生成`stable101`保守扩展正式草案。该草案只纳入4个源码复核通过的保守映射，不包含`native:createspatialindex`和`native:saveselectedfeatures`。

新增L3 token只追加到末尾：

| L3 | token | 名称 |
|---|---:|---|
| `L3_01_05_02` | 98 | Repair Geometry |
| `L3_01_09_03` | 99 | Raster-Vector Conversion |
| `L3_01_10_01` | 100 | Project/Reproject |

正式草案映射：

| QGIS operator | L3 |
|---|---|
| `native:reprojectlayer` | `L3_01_10_01` |
| `native:fixgeometries` | `L3_01_05_02` |
| `gdal:polygonize` | `L3_01_09_03` |
| `gdal:rasterize` | `L3_01_09_03` |

覆盖测算：stable-98为802条完整记录/270种唯一链；stable-101保守草案为1,442条完整记录/449种唯一链，增量为640条/179种唯一链。

新增产物：

- `stable101_conservative_extension_proposal_v1.json`
- `qgis_mapping_authority_stable101_conservative_delta_draft_v1.json`
- `stable101_conservative_source_review_gate_v1.json`
- `stable101_conservative_impact_v1.json`
- `stable101_conservative_impact_records_v1.jsonl`
- `stable101_conservative_artifact_manifest_v1.json`
- `qgis_stable101_conservative_extension_2026-07-24.md`

准入状态继续为`taxonomy_admission=not_granted`、`training_admission=not_granted`；下一步是taxonomy authority人工确认，确认前不得写入生产映射或训练集。

## stable101 taxonomy review pack（已生成）

人工审定入口位于`stable101_authority_review_v1/`。该包只包含4条保守映射review行，2个边界项单独写入sidecar，不混入主审定表。

产物：

- `stable101_authority_review.csv`
- `stable101_authority_review.jsonl`
- `stable101_boundary_sidecar.json`
- `stable101_authority_review_summary.json`
- `stable101_authority_review.md`
- `REVIEW_INSTRUCTIONS.md`
- `hash_ledger.json`
- `stable101_authority_review_manifest.json`

该review pack的状态是`review_ready`，不是`approved`；taxonomy/training admission继续保持`not_granted`。
