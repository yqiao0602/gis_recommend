# STEP 2-3：Planner-v1 vs Planner-v2 统一评估报告（v1，2026-10-06）

> STEP 1 统一 evaluator + STEP 2 统一评估完成。共同评测集 = **v2 dev 1,852 行**
> （行级验证为 v1 eval 子集，任务全匹配、顺序一致）。统一内部格式 = 有序展开
> family 序列（SemanticWorkflow）。7 指标同公式；**粒度差异（v1=19 plan family /
> v2=30 语义 family）已作为口径变量登记**。
> 脚本 `planner_unified_eval_v1.py`；结果 `PLANNER_UNIFIED_EVAL_v1.json`。

## 1. 主表（双读数：parse-exclusive / parse-inclusive）

v2 formal 有 19.1% 的行未产出合法 JSON（S1 0.809）——这些行在 parse-exclusive
读数下不计分，在 parse-inclusive 读数下计 0 分。**两个读数都是真实的**，
对照表同时给出：

| 指标 | v1（P1-B） | v2（formal） | Δ(parse-excl) | Δ(parse-incl) |
|---|---|---|---|---|
| **Bag-F1（parse-excl）** | 0.6462 | **0.6820** | **+3.6pp** | — |
| **Bag-F1（parse-incl）** | **0.6462** | 0.5517 | **−9.4pp** | — |
| Family precision | 0.7479 | **0.8324** | +8.5pp | — |
| Family recall | **0.8265** | 0.7826 | −4.4pp | — |
| Count accuracy | 0.4347 | 0.4621 | +2.7pp | — |
| Over-emission/行 | 2.40 | **1.66** | −0.74 | — |
| Under-emission/行 | 5.31 | 6.38 | +1.07 | — |
| **Ordered LCS-F1（parse-excl）** | 0.6057 | **0.6415** | **+3.6pp** | — |
| Ordered LCS-F1（parse-incl） | **0.6057** | 0.5189 | −8.7pp | — |
| Length error mean | −2.91 | −4.71 | — | — |

## 2. 判读——真实结论是"有代价的结构增强"

1. **parse-exclusive 读数（结构质量）**：v2 在 family-selection（bag +3.6pp、
   precision +8.5pp）、order（LCS +3.6pp）上**全面优于 v1**，over-emission 更少——
   **v2 结构增强版假设在此读数下成立**。
2. **parse-inclusive 读数（端到端可靠性）**：v2 的 19.1% parse 失败把全部优势
   反转为劣势（bag −9.4pp）——**v2 的 JSON 格式稳定性是当前最大短板**
   （S1 0.809 vs v1 ≈1.0）。
3. **诚实的 STEP 3 结论**：**"v2 = v1 结构增强版"在有条件成立**——条件是
   格式稳定性提升到 v1 水平。两个选择：(a) v2 + 1 more epoch / format 专项
   （P0 经验：格式学习随步数快速增长，1,042 步处 S1 0.809 仍在上升通道）；
   (b) 接受 v2 现状并以 parse-exclusive 口径报告结构增益（论文需双读数并陈）。
   **归 owner。**

## 3. 对账矩阵更新（STEP 3 完成后）

| 行 | General GIS Reasoning | 状态 |
|---|---|---|
| Planner mainline | **待定**：v2 结构增强成立但有格式代价 / v1 稳定但无结构 | owner 裁定 |

## 4. 局限

1. v2 预测取自 384-token 重生成（与 formal eval 同设置）；19.1% parse 失败行
   的 0 分计入 parse-inclusive 读数；
2. 粒度差异（19 vs 30 family）意味着两个 bag-F1 的"满分难度"不同——
   同公式不同词汇表，跨读数比较以方向与幅度为主，非精确等值；
3. Count accuracy 的 gold 口径随粒度变化（v1 counts vs v2 stage repeat）。
