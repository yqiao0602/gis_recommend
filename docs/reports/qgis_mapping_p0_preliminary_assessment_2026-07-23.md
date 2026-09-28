# QGIS P0算子映射初审（2026-07-23）

## 口径

本报告审核17个高频QGIS `operator_id`，不是审核17个新算法。证据包括QGIS
官方说明、输入输出结构、每个算子3条实际执行源码，以及stable-94和原350类
定义。结论是初审建议，不修改taxonomy或训练authority。

## 初审结果

| operator ID | 频次 | 初审类别 | 候选L3 | 置信度 | 理由 |
|---|---:|---|---|---|---|
| `native:extractvertices` | 46 | existing stable-94 alias | `L3_02_05_11` Feature to Point | high | 输出输入线/面的全部顶点，现有定义明确包含vertices。 |
| `native:extractspecificvertices` | 38 | existing stable-94 alias | `L3_02_05_11` Feature to Point | high | 输出指定首/尾/索引顶点，属于Feature to Point的指定位置语义。 |
| `native:polygonfromlayerextent` | 33 | existing stable-94 alias | `L3_02_05_12` Minimum Bounding Geometry | high | 为输入图层生成覆盖全图层的轴向最小矩形。 |
| `native:collect` | 23 | existing stable-94 alias | `L3_02_03_05` Collect Features | high | 按字段或全体收集为multipart且不dissolve，与现有定义一致。 |
| `gdal:convertformat` | 38 | restore old350 L3 | `L3_01_09_01` Vector Format Conversion | high | 原350类已有矢量格式转换，压缩后不在stable-94。 |
| `qgis:checkvalidity` | 35 | restore old350 L3 | `L3_01_05_01` Check Geometry | high | 只检查并分类valid/invalid/error，不是几何修复。 |
| `native:extendlines` | 24 | restore old350 L3 | `L3_02_05_07` Extend Line | high | 按起终点方向和距离外延线段，原350定义直接覆盖。 |
| `qgis:randompointsinsidepolygons` | 31 | restore old350 L3 | `L3_02_06_06` Sample Points | high | 在面内按数量/密度生成随机点，原350定义包含随机分布。 |
| `qgis:regularpoints` | 20 | restore old350 L3 | `L3_02_06_06` Sample Points | high | 在范围内按规则间距生成点，原350定义包含regular distribution。 |
| `native:package` | 25 | restore old350 candidate | `L3_01_11_05` Other Format Import/Export | medium | 输出GeoPackage且可打包多图层；需确认是否单独保留Package能力。 |
| `native:extenttolayer` | 21 | restore old350 candidate | `L3_02_06_08` Feature Envelope to Polygon | medium | 把显式extent变成矩形图层；旧定义针对feature envelope，需决定是否扩宽。 |
| `qgis:tininterpolation` | 42 | restore old350 multi-candidate | `L3_06_01_01` / `L3_06_02_04` | medium | 同时构造TIN三角网并输出插值栅格，可能是Create TIN和TIN To Raster的复合能力。 |
| `native:dropmzvalues` | 45 | new L3 candidate | 待定义：Drop M/Z Geometry Dimensions | high | 删除M/Z维度，原350没有对应反向维度清理能力。 |
| `native:removeduplicatevertices` | 26 | new L3 candidate | 待定义：Remove Duplicate Vertices | high | 删除要素内部重复顶点，不等于删除重复要素记录。 |
| `gdal:contour_polygon` | 21 | new L3 candidate | 待定义：Raster Contour Polygons | high | 从高程栅格生成等值区间面，区别于TIN contour line。 |
| `native:calculatevectoroverlaps` | 21 | new L3 candidate | 待定义：Vector Overlap Statistics | high | 保留输入几何并追加各叠加层的重叠面积和比例，不等同于Intersect或普通Spatial Join。 |
| `native:geometrybyexpression` | 45 | defer parameter-dependent | 无固定L3 | high | 算子语义由任意QGIS几何表达式决定，同一operator ID可表示不同算法，不能静态映射成单一L3。 |

## 汇总

- 4个operator ID可直接补为现有stable-94 alias；
- 5个可高置信恢复原350类定义；
- 3个需要在旧350类基础上进一步裁定或调整定义；
- 4个是原350也未覆盖的新L3候选；
- 1个是参数决定语义的meta-operator，应保持deferred或做参数级解析。

因此，本轮17个高频缺口并不意味着缺17个算法。当前初审只发现4个较明确的
真正新能力候选；其余主要是漏映射、stable-94压缩损失或动态语义问题。

## 下一门禁

1. 对4个existing stable-94 alias做独立复核后，可只补crosswalk，不改词表；
2. 对8个old350恢复候选检查94类压缩依据和旧token兼容方案；
3. 对4个新L3候选检查全语料频次、共现链、输入输出和是否能合并；
4. `geometrybyexpression`必须进入表达式级解析，不能按operator ID直接训练。

本报告不授予taxonomy admission或training admission。

## 裁判落盘与机器复核

17条P0初审已落盘为
`qgis_mapping_coverage_audit_2026-07-23/p0_mapping_adjudications_v1.jsonl`，并由
`scripts/validate_qgis_p0_mapping_adjudications.py`做严格一致性复核。复核结果为：

- 17个唯一operator ID与`p0_mapping_review.csv`逐项匹配；
- 每个operator ID恰好有3条`active_call`源码证据，共51条；
- 4条existing stable-94 alias的候选代码均存在于当前stable-94；
- 5条高置信old350恢复提案的候选代码均存在于旧350类且不在stable-94；
- 最终9条为`accepted_mapping_proposal`，8条继续deferred；
- 所有17条的taxonomy/training admission仍为`not_granted`。

可复现摘要和输入哈希位于
`qgis_mapping_coverage_audit_2026-07-23/p0_mapping_adjudication_summary_v1.json`。
这里的“accepted”只表示证据支持进入正式映射设计，不表示已经修改词表、授予训练
准入或生成新的训练样本。
