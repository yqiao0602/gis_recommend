# QGIS Processing 字面量别名全池重放 v1

日期：2026-08-01

## 结论

在不扩 stable110、不猜动态参数、不调用 LLM 的前提下，新增 4 条 source-replayed
train-only Processing 训练行。Processing 累计由 174 增至 178，距 200 还差 22。

## 规则

本轮只增加两个保守行为：

1. 同一 lexical scope 内、位于 Processing 调用之前且支配该调用的最近赋值，如果右值可由
   `ast.literal_eval` 或既有安全构造器白名单精确求值，则把该 Name 恢复为字面量参数事实。
2. `OPERATION`、`INPUT_FIELDS`、`OVERLAY_FIELDS` 的显式空字符串视为已证明的默认/全字段
   选择，不把空值写进任务描述，也不再因其阻塞整条描述。

函数参数、f-string、列表推导、字符串拼接、任意计算表达式、分支不支配赋值、字典 mutation
和未解析参数字典继续 fail-closed。空 `FORMULA` 仍明确 deferred。

## 全池结果

| 门禁 | 结果 |
| --- | ---: |
| 冻结 direct 池 | 150 |
| 上一版 fidelity passed / deferred | 97 / 53 |
| 新版 fidelity passed / deferred | 105 / 45 |
| 本轮新增 fidelity pass | 8 |
| existing source-region duplicate | 2 |
| exact training-pair duplicate | 2 |
| canonical | 4 |
| source SHA / AST / call span verified | 4 / 4 |
| train-only exported | 4 |
| V4 loader/loss/backward | 4 / 4 |

4 条 canonical 覆盖：

- `native:joinattributestable`
- `native:creategrid -> native:intersection -> native:fieldcalculator -> native:joinattributesbylocation`
- `native:extractbyexpression`
- `native:reprojectlayer -> native:buffer`

真实 smoke 以 `[4, 100]` 单批次加载 4/4 行，weighted loss 和梯度有限；未写 checkpoint，
未运行训练，未合并生产数据。train-only JSONL SHA256 为
`2c711dba677abf57ee94c07f4121efc16b4d7f66aff6088c80c8d510c34dad14`。

## 产物

- 新 direct 全池重放：`direct_descriptions_v6/`
- 增量四层/跨池去重：`increment_audit_v1/`
- 源码重放：`source_replay_v1/`
- 隔离 train-only 与 smoke：`train_only_v1/`

## 下一步

剩余 45 条的最大可复用阻塞族是函数参数传递。下一轮只做 source-backed caller-to-callee
实参传播：必须恢复唯一调用点、位置/关键字参数绑定、支配性定义和最终静态字面量或
workflow-input provenance；多调用点、默认值冲突、递归、跨文件调用和计算表达式继续 deferred。

## 后续校正（2026-08-01）

本报告记录的是当时的阶段性 178/22 口径，现已 superseded。后续语义复核撤销了
`native:ruggednessindex` 和 `qgis:basicstatisticsforfields` 两条错误映射训练行，corrected
custom-scope replay 再新增 1 条 `filterstructures` 训练行，因此当前 Processing 权威为
177 条，距 200 还差 23 条。

caller-to-callee census 已覆盖 26 个函数形参阻塞和 5 种源码模式，安全恢复数为 0；该路线
已经关闭，不再作为下一生产步骤。当前报告见
`docs/reports/qgis_processing_custom_scope_replay_v2_corrected_mapping/report_v1.md`。
