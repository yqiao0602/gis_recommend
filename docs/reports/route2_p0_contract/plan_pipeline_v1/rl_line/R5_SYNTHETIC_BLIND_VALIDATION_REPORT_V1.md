# R5 合成正样本盲评报告 v1（第二轮）

> 日期：2026-10-13 ｜ 规则版本：**v0.3（冻结）**：primary_family 语义 + CHANGE_DETECTION 边界探测器
> 状态：**包已交付，r5 自检 9/9（provisional）；权威判定 = owner 盲评（待完成）**
> 材料：`R5_SYNTHETIC_PACKET_V1.md`（盲评表，乱序）+ `r5_synthetic_packet_v1.json`（构造意图密封）

## 1. 包结构（owner 七轮三类型全覆盖）

| 类型 | 项 | 构造意图 |
|---|---|---|
| A 合理完整替代（3） | A1 正则族完整 / A2 替代族完整（SPECTRAL_INDEX+SPATIAL_FILTER）/ A4 分类任务+不可表达精度 | 全部 NOT omission；A1/A2/A4 预期 complete_coarse_uncertain（粗不确定性=诚实保守，非误伤） |
| B 明确单项遗漏（3） | 去 MASKING / 去 INDEX / 去 TEMPORAL | 精确点名缺失槽位 |
| C 不可表达/模糊（3） | C1 城市扩张（CHANGE_DETECTION 不可表达）/ C2 模糊任务 / A3 边界例（ITERATIVE_APPLY 包裹） | C1=gap 信号+部分可计分；C2=弃权；A3=按表示充分性口径判缺 INDEX（灰色地带，不入误伤分母） |

**构造纪律**（owner 七轮警告的落实）：未把"BAND_ARITHMETIC+MASKING+SPATIAL+AGGREGATION"自动当完整——A1 的 INDEX 经 BAND_ARITHMETIC 覆盖**有意保留 coarse 不确定性**；A2 初版把 REGIONAL_STATS 当中值合成被自检驳回（真遗漏），重建为真替代路径。

## 2. r5 自检（provisional——同一实现者构造，独立性以 owner 盲评为准）

**9/9 与构造意图一致**：
- 三个合理完整变体全部 NOT omission（零自伤）；coarse 不确定性按 owner 警告正确保留；
- 三个明确遗漏全部检出且**精确点名缺失槽位**（MASK/INDEX/TEMPORAL 各一）；
- C1：CHANGE_DETECTION gap 信号正确触发 + TEMPORAL/STATS 照常计分 = partially_scorable 的完整原料；
- C2：纯模糊任务正确弃权（F3）；
- A3：不被 ITERATIVE_APPLY 迷惑，按冻结口径判缺 INDEX。

## 3. 计分计划（owner 盲评后，分子分母全列）

| 指标 | 分子 / 分母 |
|---|---|
| **误伤率**（核心） | 合理完整样本中被判 omission 数 / 合理完整样本总数（A1+A2+A4=3 + owner 可能新判的） |
| omission 检出 | 明确遗漏样本中检出数 / 总数（B1-B3=3） |
| ABSTAIN 率 | 弃权数 / 总数（9） |
| 边界例 | A3 单列，不入任何分子 |

**已声明的局限**：样本由 r5 实现者构造——本包测试**规则逻辑**，不能证明真实分布可靠性（owner 七轮原文）；独立性来自 owner 盲评。

## 4. 等 owner

① 完成 `R5_SYNTHETIC_PACKET_V1.md` 盲评（9 项）；② 我解盲出上表指标；③ 误伤率>0 的每一例逐条归因（规则缺陷 vs 意图标注争议）。
