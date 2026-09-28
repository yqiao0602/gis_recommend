# GEE 完整输出 DAG 与空间 sidecar 校准

日期：2026-07-29

## 目的与边界

本轮只验证能否从固定、source-disjoint 的 GEE 源码样本中确定性恢复完整的
output-relevant workflow DAG。结果是 extractor/gate 校准，不授予 training、validation、test
或 production 准入，也不把局部链计为训练产量。

固定输入为 50 个唯一 source SHA：linear export 30、helper export 10、control-flow export 10。
三次 replay 的 `selection.jsonl` SHA256 均为
`43d2d6fcfcbf14906aa07c2b2ec2ba8d3a0c2b1709aea0ae5d083645d4582576`，AST 均为
50/50 成功，因此状态变化可归因于 gate 规则，不是换样。

## 校准结果

| Replay | Passed source | Partial source | Fail-closed source | Unresolved dependency occurrences |
| --- | ---: | ---: | ---: | ---: |
| run1 baseline | 11 | 0 | 39 | 73 |
| run2 direct spatial method/property roles | 18 | 1 | 31 | 63 |
| run3 nested spatial-expression role propagation | 20 | 0 | 30 | 61 |

run3 共恢复 114 个输出 DAG，其中 41 passed、73 fail-closed。source 级通过率为 20/50；
分层结果为 linear 15/30、helper 4/10、control-flow 1/10。该分层样本用于诊断困难层，不能
外推为 219,914 个母池源码的预计产量。

两条规则只允许有源码角色证据的外部空间输入：

- `clip(geometry)`、`filterBounds(table)` 等最外层静态空间方法参数；
- `region: TMK.geometry()`、`region: geometry.geometry().bounds()` 等嵌套空间表达式。

任意未解析 dataset、image、派生变量或普通调用不会按外部输入放行。相对 run1，9 个 source
状态转为 passed，共有 12 个输出 DAG 新转为 passed；这些变化只移除了 `geometry`、`table`、
`Big_Square`、`BK_02t` 等空间 sidecar 标识符。

## 保持关闭的失败类型

- 4 个 `no_explicit_output_sink` 源码的 Export 均位于 `for` 循环或 helper 函数内；当前不证明
  迭代次数、分支或跨作用域顺序，继续 fail-closed。
- 12 个输出 DAG 没有 core call，不能以“导出现有对象”冒充处理工作流。
- 1 个输出 DAG 含 unresolved call，2 个含依赖闭包内控制流。
- 61 次 unresolved dependency 继续保留；其中包括真实尾部片段和缺失派生对象。

## 训练准入前仍需解决

完整 DAG 门禁通过不等于训练行通过。源码抽查发现三个需要确定性处理的系统性风险：

- `data300000/script_290909.txt` 对同一 NDVI 对象重复导出，输出 DAG 需要按语义身份去重；
- 外部空间对象必须进入显式 input sidecar，不能从训练链中消失，也不能被当作核心算子；
- `data280000/script_289501.txt` 在 map 中把输出重命名为 `lst`，随后却执行
  `modis.select('scale')`，属于可静态发现的源码语义可疑项，不能因 DAG 闭合而直接准入。

此外，`TMK.geometry`、`geometry.geometry.bounds` 等空间访问调用仍出现在 raw core chain 中，
训练导出前必须规范化为 sidecar/auxiliary，而不是 L3 核心步骤。

## 证据与验证

- 实现：`src/gis_recommend/data/gee_workflow_dag_gate.py`
- 回归：`tests/test_gee_workflow_dag_gate.py`
- 构建器：`scripts/build_gee_workflow_dag_calibration.py`
- 本机与服务器联合回归：16/16 通过
- 服务器 run3：`/home/qy/system_redesign/diagnostics/gee_workflow_dag_calibration_20260729_run3`
- 本机 compact artifacts：`docs/reports/gee_workflow_dag_calibration_2026-07-29-run3/`
- run3 `workflow_dags.jsonl` SHA256：
  `7acb841d87fe85ee6c4d7b5efc78258f43630b1983d81f4c94039c1bc90afcd1`

当前 `training_rows_emitted=0`。下一门禁是对完整 DAG 候选执行可规模推广的 deterministic
fidelity/admission gate，而不是继续逐条修 50 条或生成任务文本。
