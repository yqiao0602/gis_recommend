# QGIS 算子映射覆盖审计（2026-07-23）

## 目的

在修改 stable-94 之前，先对现有QGIS算子做全量覆盖盘点，回答“哪些算子
已经有L3映射、哪些只是桥接、哪些需要人工判断”。本轮只生成事实审计和
空白review authority，不自动新增分类、不自动写入训练集。

## 数据集级跨walk审计

输入为现有 `outputs_v2/qgis_chain_dataset.jsonl`，使用当前
`build_qgis_alg_id_crosswalk.py` 的确定性规则（已有id mapping、已审核
crosswalk和native bridge）。结果：

| 指标 | 数量 |
|---|---:|
| 不同QGIS算子 | 262 |
| 算子出现总次数 | 14,584 |
| 已覆盖算子（已有L3/crosswalk/native bridge） | 134 |
| 待人工判断算子 | 121 |
| 明确排除算子 | 7 |
| 按出现次数计算的覆盖率 | 84.6% |

这里的“不同QGIS算子”指不同的`operator_id`实现入口，不等于算法能力或
L3类别。134个已覆盖ID中，113个映射到46个已有L3代码，另有21个只是
QGIS-native bridge标签；这说明多个QGIS实现入口会合并到同一能力。121个
待判断项的含义是“121个operator ID还没有得到可信的L3/桥接裁判”，不是
缺少121个新算法。

待人工判断的121个算子共对应1,201次出现。其中：

- P0（出现次数>=20）：17个；
- P1（出现次数>=10）：22个；
- P2长尾：82个。

P0高频缺口包括：`native:extractvertices`、
`native:geometrybyexpression`、`native:dropmzvalues`、
`qgis:tininterpolation`、`native:extractspecificvertices`、
`qgis:checkvalidity`、`native:polygonfromlayerextent`、
`native:collect`和`native:calculatevectoroverlaps`。

## 原始源码级诊断

对指定GitHub QGIS原始目录的独立诊断得到：956个不同算子、40,221次
出现；其中322个被旧规则识别为官方标准但没有旧L3映射，616个属于
provider/plugin或其他非标准算子。

这一组数字用于发现原始语料长尾，不能与stable-94准入数字混算：它使用
历史 `id_mappings_v2.json` 和旧目录规则，不是本次多步Processing恢复
authority。正式准入仍以stable-94逐步映射和源码依赖审核为准。

## Review authority

机器生成的空白缺口表：

`docs/reports/qgis_mapping_coverage_audit_2026-07-23/mapping_gap_review.csv`

配套摘要：

`docs/reports/qgis_mapping_coverage_audit_2026-07-23/mapping_gap_summary.json`

P0源码证据：

`docs/reports/qgis_mapping_coverage_audit_2026-07-23/p0_mapping_gap_evidence.csv`

该表为17个P0算子各抽取3条实际执行调用，共51行；采集器会跳过以`#`开头
的注释调用。本轮发现并跳过了1条`gdal:convertformat`注释示例，避免把
注释代码误当作能力证据。

P0初审结论见：

`docs/reports/qgis_mapping_p0_preliminary_assessment_2026-07-23.md`

每行只允许五种后续裁判：

1. `alias_existing_stable94`：只是现有stable-94能力的QGIS/provider别名；
2. `restore_old350_l3`：原350类已有定义，但压缩为94类时被移出；
3. `new_l3_candidate`：输入输出语义在原350类中也没有对应能力；
4. `exclude_non_target`：UI、加载、保存、索引、支持函数或非训练目标；
5. `defer_unresolved`：源码或语义证据不足，暂不判断。

只有完成源码片段、输入输出语义和重复样本检查后，才允许把前两类写入
mapping authority。新增L3必须追加新token，不能重排或覆盖原stable-94。

## P0裁判与stable-98草案影响

17个P0缺口已完成源码证据裁判和机器一致性复核。9条形成映射提案，其中
4条是现有stable-94 alias，5条映射到4个旧350中证据充分的恢复L3；8条
继续deferred。所有裁判的taxonomy/training admission均保持
`not_granted`。

仅报告用途的stable-98草案保持stable-94 token 0-93不变，候选追加：

| 候选L3 | token |
|---|---:|
| `L3_01_05_01` | 94 |
| `L3_01_09_01` | 95 |
| `L3_02_05_07` | 96 |
| `L3_02_06_06` | 97 |

在`outputs_v2/qgis_chain_dataset.jsonl`上实测：

| 阶段 | 完整记录 | 唯一链 |
|---|---:|---:|
| 严格stable-94 crosswalk | 766 | 256 |
| 加4条stable-94 alias | 786 | 264 |
| 加4个恢复L3的stable-98草案 | 802 | 270 |

P0真实增量为36条记录和14种唯一链。9个提案算子影响222条记录、75种
唯一链，但186条记录、61种唯一链仍被其他未映射算子阻塞。

现有`optional_l3_sequence`字段不能作为当前权威：它在1,687条记录中存在，
但只有766条与严格crosswalk完整集合重合；921条是历史嵌入标签独有，
主要依赖`native:reprojectlayer`、`native:fixgeometries`、`gdal:polygonize`、
`native:createspatialindex`、`native:saveselectedfeatures`和`gdal:rasterize`
等旧弱映射。

新增报告型产物：

- `stable98_extension_proposal_v1.json`
- `qgis_mapping_authority_stable98_delta_draft_v1.json`
- `p0_mapping_impact_stable98_v1.json`
- `p0_mapping_impact_records_v1.jsonl`

## 高频阻塞追加测算

2026-07-24继续处理`optional_l3_sequence`独有和stable-98后仍高频阻塞的6个
算子。该轮只使用本机已同步的QGIS catalog和当前chain dataset记录，未重新访问
服务器原始源码；因此它是mapping边界和影响测算草案，不能直接授予准入。

保守档建议恢复3个旧350类：

- `native:reprojectlayer` -> `L3_01_10_01` Project/Reproject；
- `native:fixgeometries` -> `L3_01_05_02` Repair Geometry；
- `gdal:polygonize`、`gdal:rasterize` -> `L3_01_09_03` Raster-Vector Conversion。

support/export边界档额外测算：

- `native:createspatialindex` -> `L3_01_07_01` Add Spatial Index；
- `native:saveselectedfeatures` -> `L3_07_04_01` Export To Shapefile。

以stable-98草案的802条完整记录/270种唯一链为基线，保守档可到1,442条/449链
（+640条/+179链）；扩展档可到1,583条/496链（+781条/+226链）。

详细产物：

`docs/reports/qgis_mapping_high_impact_blockers_2026-07-24/`

## 下一步

1. 先在服务器`/home/yll`为6个高频阻塞提案补源码片段复核，确认真实调用、
   参数语义、输出角色和重复/镜像情况；
2. 源码复核通过后，起草正式stable-N扩展，且不得重排或覆盖stable-94原token；
3. 继续处理8个P0 deferred和22个P1缺口，仍按源码证据和输入输出语义审核；
4. 只有正式mapping authority通过后，才重建全量strict映射并重新评估
   deferred和200条扩展包；
5. 不把草案映射或历史嵌入标签直接写入训练集。

当前taxonomy admission和training admission均保持`not_granted`。
