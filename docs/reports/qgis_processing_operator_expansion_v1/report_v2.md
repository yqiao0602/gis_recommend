# QGIS Processing blocker expansion report v2

日期：2026-08-01

## 权威替代

本报告以 `replay_v10_exact_authority/` 替代 v9 作为 757 条 blocker 的当前 replay authority。
v10 修复了 driver 未装载 existing-L3 `native:extractwithindistance` authority 的问题；其余
输入、规则和准入门禁不变。

## v10 结果

- 757/757 source SHA verified，source failure=0。
- candidate=166，canonical=45，duplicate=121。
- fully-normalized mapping-complete=130。
- partial mapped-subset=218。
- training rows emitted=0；validation/test/production/LLM/training 均关闭。

v10 与 v9 的候选产量相同，因为该 blocker 池只包含 `script:filterstructures` caller，真正的
Processing DAG 位于 custom implementation body，必须由 custom-scope replay 准入，不能在
caller 行上猜测展开。

## 后续校正

原 v1 的 47 条第二批 train-only 交付事实继续有效。后续发现两条 description/runtime
训练行使用错误映射，已在
`docs/reports/qgis_processing_runtime_parameter_replay_v2_corrected/` 撤销；corrected
custom-scope replay 随后新增 1 条。因此当前 Processing 权威总数为 177，而不是 178。

custom-scope 当前报告：
`docs/reports/qgis_processing_custom_scope_replay_v2_corrected_mapping/report_v1.md`。

