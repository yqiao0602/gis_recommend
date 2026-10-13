# r5 v0 盲跑验证报告 v1（对照 owner 24 项人工盲评）

> 日期：2026-10-13 ｜ 判别器：`scripts/r5_requirement_parser_v0.py`（确定性规则，无学习组件/无 LLM）
> 输入：`r5_validation_packet_v1.json`（S2 真实候选）× `r5_labels_frozen_v1.json`（owner 盲评，24/24 omission）
> 完整审计轨迹：`r5_v0_blind_run_v1.json`（逐槽位 hit 词/规则/状态/等价条件/弃权原因）
> 口径：owner 六轮——24 项只能决定"是否值得继续"，不能证明泛化；误伤率本轮**不可测量**（0 个 both_reasonable）。

## 1. 逐组对照（解盲后）

| 组 | owner 判定 | r5 required 槽位 | r5 结果 | 一致性 |
|---|---|---|---|---|
| 5227 | 4×omission（缺云掩膜） | TEMPORAL/MASK/COMPOSITE | 4×incomplete，**缺失恰为 MASK** | **完全一致** |
| 17970 | 4×omission（剖面采样/图表不可表达） | （无可表达槽位） | **4×abstain** + PROFILE_TRANSECT/CHART_PLOT 词汇边界信号 | **证据级一致**（F3 弃权 = 设计成功案例） |
| 823 | 4×omission（云掩膜/流域裁剪/分类不充分） | TEMPORAL/MASK/SPATIAL/COMPOSITE/CLASSIFY | 4×incomplete，逐候选缺失清单与附注吻合（D 最差缺 5 项） | **一致** |
| 29519 | 4×omission（NDWI+云掩膜缺失，最佳 INDEX 测试例） | TEMPORAL/MASK/INDEX/SPATIAL/COMPOSITE | 4×incomplete，**INDEX 全缺** | **完全一致** |
| 13612 | 4×omission（NDVI 缺失；聚合次数≠统计覆盖） | TEMPORAL/INDEX/SPATIAL/COMPOSITE/STATS | 4×incomplete，INDEX 全缺；SPATIAL/STATS=covered_coarse+不确定性注记 | **一致**（粒度警告结构化落地） |
| 30160 | 4×omission（精度评估不可表达；A/D 缺分类） | TEMPORAL/STATS/CLASSIFY + ACCURACY_ASSESSMENT 边界信号 | A/D incomplete；B/C **complete_coarse_uncertain**（非 complete） | **部分一致**（2/24 标签级分歧，见 §3） |

## 2. 验证过程中发现并修复的缺陷（判别器先验证的价值）

| 缺陷 | 组 | 修复 |
|---|---|---|
| `\barea\b` 误命中 "study **area**" → 伪 STATS 需求 | 29519 | 负向断言 `(?<!study )\bareas?\b` |
| TERRAIN 的 `elevation` 过宽（DEM 加载≠地形派生）→ k=17970 误需求 | 17970 | 移除 elevation，保留 slope/hillshade；修复后该组正确**弃权** |
| covered_coarse 被计入 complete（一个 AGGREGATION"覆盖"精度评估） | 30160 | 新判定级 `complete_coarse_uncertain`——coarse 覆盖永不等于 complete（owner 粒度警告的结构化落地） |

三条全部由 F4 审计轨迹（hit_text 逐条可查）暴露，无一条靠猜。

## 3. 指标（按 owner 六轮统计口径，分子分母全列）

- **候选级 omission 标签一致**：22/24（91.7%）；**分歧 2/24** = k=30160 B/C（r5: complete_coarse_uncertain vs owner: omission）。分歧原因 = covered_coarse 语义；**证据级一致**：r5 的 ACCURACY_ASSESSMENT 词汇边界信号恰对应 owner 附注"精度评估不可表达"——r5 没有把粗覆盖当完整，只是没有进一步判 omission。
- **任务级一致**：5/6 完全一致；1/6（17970）证据级一致（双端识别同一词汇边界，r5 按 F3 弃权）。
- **误伤率**：**本轮不可测量**（0 个 both_reasonable 正样本）——不做任何宣称。
- **ABSTAIN 率**：1/6 组（16.7%），有原因+有词汇边界证据；未以降低弃权率为目标。
- **需求提取对照**（owner omission_detail vs r5 槽位）：云掩膜（3 组）/INDEX（2 组）/分类（2 组）/时间/合成/面积统计全部对应命中；owner 提到的"不可表达需求"（剖面/图表/精度评估/RGB 可视化）全部由 vocab-gap 信号承接，未进入计分。

## 4. 结论（对应 owner 六轮执行顺序第 4 步）

1. r5 v0 在本包上**没有误伤案例**、没有漏检 owner 明示需求；唯一标签级分歧由 coarse 语义承载且证据级一致；
2. 两个规则缺陷在部署前被人工标签暴露并修复——"先验证判别器"流程有效；
3. **本包无法测量的关键指标 = 误伤率**：必须补充含明确"合理替代路径"的正样本（建议：对 29519/13612 构造含 BAND_ARITHMETIC+MASKING+SPATIAL+AGGREGATION 的合成完整候选与部分变体，标 synthetic，单独一批盲评）；
4. r5 具备"初步可用性"，**不自动授权 Phase 2/3**（owner 六轮第 5 步）；接入 RL 前还需：补充正样本包的第二轮盲评 + 离线审计（24 组有效覆盖提升幅度 + 长度/模板/family 三项偏差）。

## 5. 边界与登记

- 判别器输出仅供研究诊断；本报告不构成训练授权；
- 规则版本 = v0.2（含本轮两处修复，逐条留痕于代码 SLOT_RULES）；
- 人工标注的判定语义 = "蓝图表示充分性"保守口径（owner 六轮原文），非底层代码真值。
