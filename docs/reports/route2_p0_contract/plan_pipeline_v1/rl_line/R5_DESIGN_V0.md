# r5 任务需求覆盖奖励 — 设计草案 v0（DRAFT，待 owner 审定后实现）

> 路径：`plan_pipeline_v1/rl_line/R5_DESIGN_V0.md` ｜ 日期：2026-10-13
> 上游裁定：owner 四轮/五轮——S2 工程验证通过、信号覆盖有限入档、Phase 2 暂停；
> 下一优先级 = r5 可信度与离线判别验证。本文只设计**机制与验证协议**，不含实现。

## 1. r5 要回答的问题（以及明确不做的事）

**问题**：候选 Blueprint 是否覆盖了任务真正需要的处理能力，且允许多条语义合理路径。

**明确不做**（owner 五轮原文 + 反 37 类教训）：
- 不奖励阶段数量更多、覆盖类别更多、或匹配某个固定模板；
- 不因与单一金标的顺序/阶段集合不同而判错（多解容忍为一等公民）；
- 不做全任务覆盖承诺——只在有可靠判定依据的子集上生效，证据不足即 abstain/mask。

## 2. 机制 v0：需求槽位匹配（deterministic，可审计）

```
task 文本 ──规则触发器──> 需求槽位集 R（带置信档）
                              │
候选 Blueprint 的 family 集 F ─┤
                              ▼
      r5 = f(R, F)；R 为空或低置信 → ABSTAIN（masked，不打分）
```

### 2.1 需求槽位触发器（初版规则族，全部落账可审计）

| 槽位 | 触发词例（中英） | 映射 family（含等价类） |
|---|---|---|
| TEMPORAL | 年/季/月/annual/seasonal/monthly/日期区间 | TEMPORAL_FILTER |
| INDEX/ARITH | NDVI/EVI/植被指数/地表温度/归一化/difference/ratio | SPECTRAL_INDEX ≈ BAND_ARITHMETIC（等价类） |
| SPATIAL_REL | 范围内/缓冲/裁剪/clip/buffer/within/保护区 | SPATIAL_CLIP ≈ SPATIAL_FILTER（等价类） |
| AGGREGATE | 均值/总和/平均/面积/占比/mean/sum/area/statistics | AGGREGATION ≈ REGIONAL_STATS（等价类） |
| CLASSIFY | 分类/土地覆盖/classify/land cover | CLASSIFICATION |
| TERRAIN | 坡度/高程/山体阴影/slope/elevation/hillshade | TERRAIN_DERIVED |
| THRESHOLD | 大于/小于/阈值/threshold/提取高(低) | THRESHOLD_LOGIC |
| MASK | 云/掩膜/cloud/mask | MASKING |
| SAMPLE | 采样/随机点/sample | SAMPLE_EXTRACTION |
| NEIGHBOR | 插值/克里金/interpolate/kriging | NEIGHBORHOOD |

- **管道类 family（LOAD/EXPORT/COLLECTION_MGMT/GEOMETRY_DEFINE）永不进入需求槽位**——
  它们在几乎任何管线都合理，进入需求集只会制造伪精确。
- 触发器规则版本化（v0.1 起），每条规则在判定记录里留痕（哪条规则、命中词）。

### 2.2 计分

- **覆盖分**（主分量）：`coverage = |R 覆盖到的等价类| / |R|`——R 中每个槽位在 F（含
  等价类展开）中有对应即算覆盖；**顺序无关、集合语义**。
- **无依据阶段罚**（次分量，保守）：只对**内容类 family**（非管道类）检查任务文本是否
  存在可关联触发词；无法关联且不在任何等价类比邻（如 SPECTRAL_INDEX 邻接 INDEX 槽位）
  → 记 `unsupported_candidate`，**先只记录不扣分**（v0 审计口径），是否计罚由验证
  数据定。
- **多解容忍**：等价类 + 顺序无关是结构级容忍；更深的多解（同一槽位由不同机制满足，
  如 AGGREGATION vs REGIONAL_STATS 已入等价类）由验证包人工判定补充等价表。

### 2.3 ABSTAIN 门（置信门控）

- R 为空 / 触发词置信低（规则命中数 < 2 且槽位数 < 2）/ 任务文本过短 → **ABSTAIN**：
  r5 masked，不进 C0 分母。ABSTAIN 率是 r5 的核心汇报指标之一（owner 五轮：报告
  覆盖率、判别一致性、拒判率、偏差）。

### 2.4 反偏差护栏（离线审计必查项）

无长度项、无词频项、无模板项（机制层面即不存在）；审计报告必须给出：
①各 family 的 FN 率（漏需求）与 FP 率（误需求）；②r5 分数与计划长度的相关；
③ABSTAIN 率按任务带分层；④与冻结评测口径的外部一致性（r5 不用自己的分数证明自己）。

## 3. 验证协议（先验证判别器，再接入 RL）

### 3.1 小规模人工判定包（本轮交付，材料 = S2 真实候选）

- 抽样：S2 的 24 组中按带分层取 6 组（short/mid/long 各 2）× 每组 4 候选 = **24 判定项**；
- **盲评**：只给任务全文 + 候选 stage 列表（乱序、无奖励分、无 gold）；
- owner 逐项标注：`omission`（缺什么能力）/ `unsupported`（哪个阶段无依据）/
  `both_reasonable`（与组内其他候选不同但都合理）/ `unclear`；
- r5 对同一批候选盲跑 → 一致性指标：omission 检出率、**误伤率（把合理备选判为缺失）**、
  unsupported 精度、ABSTAIN 率、按带偏差。

### 3.2 通过门槛（预注册草案，owner 可改）

- 误伤率 ≤ 10%（多解容忍是硬要求）；
- omission 检出率 ≥ 80%（对人工明确标注的缺失）；
- ABSTAIN 率如实报告（预期 30-50%，宁可弃权不可误判）；
- 任何一项不过 → 修规则或缩小于集，**不接入 RL**。

### 3.3 离线奖励审计（判别器过门槛后）

- 不更新模型；r5 跑满 S2 的 24 组 × 8 候选；
- 观察：有效组覆盖率从 6/24 提升到多少；组内差异是否可解释（对着人工标注看）；
- 长度/模板/family 偏差三项审计（§2.4）；
- 与冻结评测并行报告，r5 自身评分不作 self-proof。

### 3.4 与多解判别线的接口

- 本包的人工标注（both_reasonable 判例）登记后**移交多解判别线**作 D2/D3（粒度等价/
  不等价）素材；两线共享等价类表，避免两套标准。

## 4. 边界

- r5 v0 为**确定性规则判别器**，无学习组件、无 LLM 调用（项目硬边界）；
- 规则覆盖不了的任务 → ABSTAIN，不强行打分；
- r5 通过验证 ≠ 训练授权；接入 RL 仍走 owner 逐级放行。
