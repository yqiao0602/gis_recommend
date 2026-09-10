# QGIS Planner Benchmark v0.2 Task Derivation Specification

状态：`frozen_for_task_authoring`
日期：2026-09-10

## 核心原则

v0.2 的 task 不允许由 reviewer 凭空编写。每条 task 必须从已有、可追溯的 QGIS source-backed workflow/training record 派生，再绑定 parameter-free `processes + links` gold。

人工审核只负责确认来源语义、去参数化是否保真和 task-to-gold 是否闭合；人工可以做最小文字整理，不能新增来源中没有的操作、依赖、业务目标或输出类型。

## 派生优先级

按以下顺序获取 task text：

1. 已有权威 QGIS workflow/task description，执行参数值剥离；
2. 同一 source scope 的注释、变量名和已验证 output role，执行确定性组合；
3. 仅在前两级不足时，使用保留全部 operator/order/output 语义的最小 paraphrase，并标记 `derivation_method=deterministic_paraphrase`；
4. 无法由 source evidence 支撑的记录直接 `reject` 或 `return_for_revision`，不手写补齐。

允许去除的内容仅包括文件路径、数值参数、具体 CRS 数值、字段名和业务实体名称等 execution-layer details。不得去除或改写 modality、输入角色、依赖顺序、分支/合并关系和输出类型。

## 必备 provenance

每条候选 task 至少绑定：`source_authority_key`、`source_sha256`、source record/span、父训练记录（如有）、`derivation_method`、原始文本 hash、派生文本 hash、canonical DAG key、review 状态和 split。

`source-backed candidate` 仍不是 task+gold。只有 source-derived task text 与 parameter-free gold 完成独立 task-to-gold review、Gate 2 九索引重检和人工批准后，才计入 benchmark 交付数。

## 独立性与拆分

v0.2 final 必须与 paper_v1 train/val/test、v0.1 development/final 的 source identity 和禁止近 DAG 索引零重叠。exact text overlap 必须为 0；通用连接性短语的 n-gram 命中必须单独审计，不得把它当作任务语义复用。

同一 source 可以产生有限文本变体，但 coverage 统计按 canonical DAG 计，不按变体倍增。development 与 final 仍需 DAG-disjoint；变体不能替代结构多样性。

## 禁止事项

- 不从 DAG operator 名称反向虚构业务目标；
- 不把参数化真实 workflow JSON 直接当作主 gold；
- 不把 reviewer rationale 当作 task text provenance；
- 不为满足 120 条预算而降低 source evidence 或语义闭合门槛；
- 不把任何 v0.2 final 记录反向加入训练集后继续使用同一 final 结果名。

当前 v0.2 task+gold 交付数为 `0`。下一步是从现有 source-backed 数据中抽取并去参数化 task text，而不是自由手写任务。
