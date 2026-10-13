# Step 1 人工 Gold 构建规程（v0，有条件批准执行）

状态：STEP1_AUTHORIZED_CONDITIONAL / NOT_ADMITTED / NOT_TRAINING
日期：2026-10-09
批准范围：仅 6 条样本人工 duty-sequence gold + 可行性检查
授权边界：见第 7 节

## 1. 输入

六个脚本的原始记录与 parser 证据（全部已存在，只读）：

```text
docs/reports/gee_semantic_planner_v1_pilot_round3/g0_semantic_review_priority6_raw_v1.jsonl
docs/reports/gee_semantic_planner_v1_pilot_round3/g0_semantic_review_priority6_scripts_v1.jsonl
docs/reports/gee_semantic_planner_v1_pilot_round3/parser_evidence_v1/{script}_parser_evidence_v1.json
```

模板：

```text
docs/reports/gee_semantic_planner_v1_pilot_round3/duty_gold_template_v0.json
```

## 2. 目标 B 的标注定义（Task → duty sequence）

每个阶段记录四个字段，缺一不可：

| 字段 | 含义 | 取值 |
|---|---|---|
| `duty` | 阶段职责（开放短语，非封闭标签） | 自由文本短语 |
| `task_evidence` | Task 中支持该职责的原文片段 | 引文，可为空 |
| `source_evidence` | 源码/parser 中对应实现的证据（行号或 callee） | 引文或 ordinal，可为空 |
| `order_basis` | 顺序依据 | `task_explicit` / `task_implied` / `source_order_only` / `unknown` |
| `provenance` | 该职责由谁决定 | `task_determined` / `source_required` / `undeterminable` |

关键规则（防止 B 退化为实现轨迹标签）：

1. `duty` 是**任务要求做什么**，不是源码调用了什么 API。例：Task 说"估算土壤流失"→ duty 是"组合侵蚀因子并计算流失量"，而不是"ee.Image.multiply"；
2. 同一 duty 可对应多种合理实现；标注时若意识到某 duty 只有这一种实现方式才能满足，须在 notes 里标记 `implementation_specific_risk`；
3. 仅凭 Task 无法确定的阶段必须标 `provenance=undeterminable`，**禁止用源码反向补全后伪装成 task_determined**；源码补全的信息只能进 `source_evidence`；
4. 顺序依据必须是 `task_explicit` 或 `task_implied` 才算 Task 级监督信号；`source_order_only` 阶段单独统计，它们不构成 Task→duty 的可学习证据。

## 3. 目标 C 的标注定义（重复结构）

对含重复结构的任务，分三个独立问题记录：

```json
{
  "repeat_count_task_inferable": true|false|unknown,
  "repeat_count_value": null|N,
  "task_evidence_for_count": "...",
  "unit_structure_homogeneous": true|false|unknown,
  "unit_structure": [duty 序列 或 null],
  "binding_evidence": "per-target-variable | per-year | per-region | per-class | none | unknown",
  "binding_source_evidence": "...",
  "binding_task_inferable": true|false|unknown
}
```

关键规则（防止标签泄漏）：

- `repeat_count_task_inferable` 与 `binding_task_inferable` 分开记录；
- 若 Task 只列了目标名而未明说"对每个目标分别建模"，则 count 可能为 task_inferable，但 binding 必须检查源码后才可标 true，并附 `binding_source_evidence`；
- `unit_structure_homogeneous` 需要源码证据证明每段子流程确实同构；仅凭 Task 措辞不可标 true。

## 4. 六条样本各自的标注焦点

| 脚本 | 焦点 |
|---|---|
| script_302840 | C 全三问：count 推断性、8 段同构性、目标绑定证据 |
| script_269131 | 多因子 duty 的任务语义（Task 与代码输出存在已知不一致，逐 duty 记录 description_mismatch 风险） |
| script_36595 | R/K/LS/C/P 五个 duty 是否 task_determined，乘积依赖是否 task_implied |
| script_275285 | NDVI→FV→EMM→LST 中间链：哪些环节 Task 明说，哪些只存在于代码 |
| script_405410 | 七因子 duty 是否可在 Task 中找到依据；最终归一化是否 task_explicit |
| script_93009 | 时序对比 duty（1985 vs 2018）是 task_explicit 还是 source_order_only |

## 5. 验收报告要求（三问）

完成后输出 `duty_gold_step1_report_v0.md`，必须回答：

1. 六条任务中多少条能建立可信 duty 序列（判定标准：≥60% 阶段 provenance ∈ {task_determined, source_required} 且顺序含至少一个非 source_order_only 依据）；
2. 按 provenance 三分类统计全部阶段，并给出每类的典型例子；
3. B/C 定义清晰度：逐条列出标注中遇到的定义模糊点，判断第二标注者能否大体复现（诚实记录，不强行乐观）。

## 6. 输出

```text
docs/reports/gee_semantic_planner_v1_pilot_round3/duty_gold_v0/
  duty_gold_6_v0.jsonl          # 6 条记录（每脚本一条）
  duty_gold_step1_report_v0.md  # 三问验收报告
  duty_gold_hash_ledger_v0.json # 输入/输出 hash
```

## 7. 授权边界（冻结）

允许：
- 人工阅读六个脚本与 parser 证据；
- 构建 6 条 duty gold；
- 撰写验收报告。

不授权：
- 批量规则构建或 30–50 条扩展；
- 结果并入训练集或冻结为正式监督 schema；
- 训练/推理/RL；
- 修改 G0/G1/G2/G3、Blueprint 版本、locked test；
- 修改 E3 判据（normalized edit distance < 0.1 仅为候选，须先定义 B↔G2 语义投影后再定）。

Step 1 通过后进入**下一次设计审查**，不自动获得 Step 2 权限。
