# Blueprint v2 Schema 审计报告（v1，2026-10-04，CPU-only，未训练）

> 依据 owner 裁定（`20219c1`）：Ordered + Repetition-aware Blueprint v2 设计——
> Schema → Gold 转换 → 可表达性验证 → lossless/coverage 审计 → evaluator 设计。
> 蓝本 = pre-RLE 原始语义链（R3-CD-2 证明迭代信息在那里）。脚本 `blueprint_v2_audit_v1.py`；
> Gold 数据 `04_DIAG_WORK/blueprint_v2_gold_v1.jsonl`（37,044 行，SHA `46d51db9…`）。

## 1. Schema v2（提议）

```json
{
  "stages": [
    {"seq": 1, "family": "VECTOR_LOAD",  "repeat": 1},
    {"seq": 4, "family": "AGGREGATION",  "repeat": 2},
    ...
  ],
  "loop_groups":  [{"members": [4], "iteration_hint": "per_class|...|unspecified"}],
  "total_iterations": 36      // 仅注记，非 Planner 预测目标
}
```

- **stages** = 原始语义链的极大游程序列（family + 连续重复次数）——**语义粒度（30 类），
  比 plan family（19 类）更细**；
- `repeat > 1` 的 stage 即循环（循环体 = 该 stage 的语义操作，迭代条件 = iteration_hint）；
- **绝对量级只做注记**（total_iterations / repeat 数值），不进 Planner 预测目标。

## 2. A1 无损性：**构造性 100%**

- expand(stages) == 原始链：**37,044/37,044**；
- Σ repeat == `original_semantic_length` 字段：**37,044/37,044**。

v2 对原始 workflow **表示无损**——这是 v1（保 bag 损顺序+完全丢迭代）做不到的。

## 3. A2/A3 循环普遍性与重复份额（按原始长度分桶）

| 原始长度桶 | n | repeat_share | loops/workflow | stages 均值 |
|---|---|---|---|---|
| 1-5 | 11,197 | 0.095 | 0.37 | 3.8 |
| 6-8 | 10,068 | 0.177 | 0.81 | 5.61 |
| 9-12 | 6,032 | 0.227 | 1.32 | 7.96 |
| 13-20 | 5,496 | 0.268 | 1.89 | 11.8 |
| 21-50 | 3,407 | 0.269 | 2.98 | 21.4 |
| 51+ | 844 | 0.245 | **9.35** | **114.1** |

- **65.3%** 的 workflow（24,186/37,044）含至少一个循环；loops/workflow 均值 1.31，
  随长度升至 9.35（51+ 桶）；游程最长 584 次重复。
- **重要细化（诚实修正）**：即便在 51+ 原始桶，语义级 repeat_share 也只有 **0.245**——
  原始长 workflow 的主体是**大量不同的语义操作**（114 个阶段），而非单一操作的巨型循环。
  v1 plan 层观测到的 95.1% family 重复，**主要是 family 粒度粗化（30 语义类 → 19 plan family）
  造成的合并伪影**，而非字面循环。
- **含义**：v2 必须定义在**语义粒度**（30 类）上——在 plan-family 粒度上谈"重复结构"
  会把粒度伪影误当循环。当前 v2 stages（语义游程）正是正确粒度。

## 4. A4 迭代语义条件的可恢复性（Task 文本侧）

| hint | 覆盖率 |
|---|---|
| per_band（band/spectral） | **47.0%** |
| per_class（class/land cover） | 29.9% |
| generic_each（each/every/per/all） | 27.1% |
| per_year（year/annual） | 19.4% |
| per_feature（feature/object/segment） | 14.0% |
| 完全无 hint | **20.2%** |

（多选，行可命中多维度）**~80% 的 instruction 至少含一个迭代维度线索**——
iteration_hint 作为 Planner 的**分类目标**（而非次数回归）是可学习的。
20.2% 无 hint 行 + hint 与真实循环维度的对应精度，需在标注/验证时单独测。

## 5. A5 与现有 Plan 的关系

RLE 阶段数 → plan family 数的均值比 = **0.863**：chain_to_plan 在 RLE 之上还有 ~14% 的
进一步合并。**v2 的 stages（语义游程）因此是比现有 plan family 序列更细的表示**——
v2 Planner 线需要自己的评测口径（stage-sequence F1 @ 语义粒度），不能直接套用现有
plan-family gate（冻结不动）。

## 6. Evaluator 设计提议（v2 线诊断口径，冻结 gate 不动）

1. **Stage-sequence F1**（语义 stage 序列，顺序敏感——这是 v2 相对 v1 的核心增量）；
2. **Loop 检测**：gold run>1 的 stage，Planner 是否标记为循环（precision/recall）；
3. **Iteration-hint 分类**：多标签 vs instruction 关键词弱标签（弱标注需人工抽验）；
4. 量级（repeat 数值/total_iterations）**只记录不评分**——不可从 Task 识别，
   由 Grounding 解析。

## 7. 状态与建议

- Gold v2 数据就绪（`blueprint_v2_gold_v1.jsonl`，37,044 行）；冻结物未动；零训练。
- **待 owner 裁定**：① Schema v2 定稿（含 iteration_hint 标注规则：关键词弱标注 vs 人工/LLM 标注）；
  ② 20.2% 无 hint 行的处理（unspecified 类 vs 排除）；③ 是否按 v2 口径启动小规模
  Planner-v2 SFT（同 P0 模式：新目标格式 + 独立目录，训练仍需单独放行）。
