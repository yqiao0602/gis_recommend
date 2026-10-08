# Planner-v2 Hint Contract — FREEZE 文档（v1，2026-10-04）

> 依据：6 批人工验证（396 条分层样本）全部完成 + 各维度规则校准冻结 + 全量重打完成。
> 本文档即 **Planner-v2 Contract Freeze**：自此以后，Planner-v2 的训练目标（blueprint +
> iteration hints）不得再根据模型结果修改。状态：**Planner-v2：Data/Schema/Evaluator Gate
> PASS；Human Hint Validation DONE（6/6 batches）；SFT NOT AUTHORIZED（待 owner 放行）。**

## 1. Schema v2（FINAL）

```json
{
  "stages": [{"seq": 1, "family": "<semantic family>", "repeat": <run length>}],
  "repetition_groups": [{"stage_seq": i, "family": f, "repeat": c,
                          "iteration_hint": [<labels>]}],
  "total_iterations": N   // 注记，非 Planner 预测目标
}
```

- stages = pre-RLE 原始语义链极大游程序列（**语义粒度 30 类**）；构造性无损（37,044/37,044）。
- **量级不在 Planner 目标内**：绝对 repeat/total_iterations 只注记，由 Serializer/Grounding
  从实际数据上下文解析（深度尾 bias −70~−365 的根因 = 该量级从 Task 不可识别）。

## 2. iteration_hint 维度状态与校准记录

| 维度 | 规则 | 人工一致率 | Contract 状态 |
|---|---|---|---|
| per_band | v3.1（三条件结构判定 + 负词典 + index-context 失效） | 11/12 | **ACTIVE**（494 组） |
| per_class | v2（class 四角色 taxonomy；逐类动作语义优先） | 8/12 | **ACTIVE**（28 组） |
| per_year | v1（annual 须伴随处理动作；season-only→ABSTAIN；结构对齐→TP） | 12/12（Y5/Y11 全文重裁后） | **ACTIVE**（9,917 组） |
| per_feature | —（0 TP；feature 五角色高污染） | 0/12 | **diagnostic_only / disabled**（7,188 槽位移入 diagnostic） |
| generic_each | **stage 级重定义**：Task semantics indicate multiple homogeneous workflow stages, with repetition structure supporting that interpretation；intra-stage bulk / collection.map() → ABSTAIN；对比/配置 → FP | 4/3/5 | **ACTIVE**（16,111 组） |
| unspecified / no-repetition | 安全默认 ✓（12 行抽查确认；1 个 gold 对齐缺口样本 N9 已标记） | — | 默认（27,259 组） |

**ABSTAIN 语义（Contract 原文）**："ABSTAIN is not treated as a negative semantic
judgment; it is an abstention from providing the corresponding hint. For Planner
input, ABSTAIN is normalized to `unspecified` to preserve precision-first behavior."

**GEE/Planner 层次边界（Contract 原文）**：GEE execution-level iteration
（collection.map()）≠ Planner graph-level stage repetition——前者单阶段，后者才是
Planner 关心的 N 个可表达、可排序、可 grounding 的 stages。

## 3. 最终数据与分布

- `blueprint_v2_gold_v3.jsonl`（37,044 行，SHA `621090bc…`）= **Contract 数据定稿**。
- 组级 hint 分布：unspecified 27,259 / generic_each 16,111 / per_year 9,917 /
  per_band 494 / per_class 28 / per_feature 0（7,188 诊断槽位单列）。
- 行级 confirmed_dimensions：无 26,551（71.7%）/ generic_each 4,746 / per_year 3,574 /
  generic_each+per_year 1,861 / …（多维度并存合法）。

## 4. Evaluator（v2 线诊断口径，冻结 gate 不动）

- **E1 Ordered Stage-F1**：LCS-F1 + edit distance + exact match（顺序敏感；自测：旋转罚至 0.75）。
- **E2 Repetition-group F1**：per-family repetition-presence（结构对即可，不判数值）。
- **E3 Iteration-hint F1**：micro/macro/per-class（6 类，弱标注域内）。
- **E4 Absolute repeat bias**：diagnostic only。

## 5. Smoke 设计（SFT 放行后第一批）

100-300 行，目的限定：S1 JSON compliance / S2 ordered stages（防退化 unordered）/
S3 repetition presence（不要求 exact count）/ S4 unspecified 滥用检查 / S5 hint
shortcut 检查 + **Structure-only validity**（不看 absolute repeat）。

## 6. 冻结清单与未决事项

- **冻结**：Schema v2、Gold v3 数据、各维度规则版本（per_band v3.1 / per_class v2 /
  per_year v1 / generic_each stage 级定义）、ABSTAIN 语义、E1-E4、本文件。
- **继续冻结**：Stage-1 v2_2 主线、现有 gate、RL、Stage-2。
- **待 owner 放行**：Planner-v2 SFT（含 smoke）；正式 Stage-1 新候选的切换裁定。
- **已知限制（登记）**：①关键词规则覆盖缺口（无 each 措辞的 stage 重复漏检，如 U5）；
  ②弱标注语义精度以 396 条人工验证为准（396 条全覆盖完成）；③量级不可识别性
  （Grounding 职责）。
