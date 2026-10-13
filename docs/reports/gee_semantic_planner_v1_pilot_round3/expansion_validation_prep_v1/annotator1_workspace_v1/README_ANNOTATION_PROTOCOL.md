# 标注者 1 工作区（owner）

生成时间: 2026-10-10T16:03:56
依据: blind_annotation_units_v1.json（冻结，不含自动化结论）
判定单位规范: EXECUTION_CHECKLIST_JUDGMENT_UNITS_V1.md

## 纪律（owner 裁定 2026-10-10）

1. **只看**源码节选与本说明，**不得打开** `automation_sealed_v1.json`；
2. 独立完成，结果保存到 `results/`，文件名带时间戳（如
   `annotation_results_v1_20261010T1530.jsonl`）；
3. 单人探索性标注阶段：结果**不得**称为双盲验证或双标一致性；
4. 遇 `undeterminable` 如实标记，不强行判定；
5. script_10 非 JS（解析失败），按 `not_judgeable` 跳过。

## 材料

- `annotation_sheets/script_XXXXXX.md` × 24：每脚本标注单
  （A1 三分类 / A2 状态+计数 / A3 角色四分类，附源码节选）；
- `results/annotation_results_template_v1.jsonl`：结果模板，共
  2518 条判定单位，填 `human` 字段即可。

## 提交后流程

两名标注者均提交 → 记录时间戳 → 解封 automation_sealed_v1.json（记录开封
时间戳）→ compute_expansion_metrics_v1.py 计算分检测器一致率与分歧归因。
