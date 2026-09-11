# QGIS Planner Benchmark v0.1 评测协议

> **SUPERSEDED — Historical v0.1 Protocol**
> 本文件为 qgis-planner-benchmark v0.1 历史评测协议原件，适用于 v0.1（Final 120 / Dev 40 / Refusal 12）。
> 现行评测以 `qgis-planner-benchmark-v0.2.1 @ 6006e49` 及其 freeze manifest
> （`benchmarks/qgis_planner_v1/releases/v0.2.1-freeze/freeze_manifest.json`，
> Dev 20 DAG / Final 100 / Refusal 12）为准。
> 本文件仅作为 v0.1 provenance 保留，不得作为 v0.2.1 当前评测协议使用。

最后更新：2026-07-31

## 1. 当前状态

QGIS Planner Benchmark v0.1 已完成数据构建与冻结，版本为 `0.1.0`，冻结状态为
`internal_sealed_freeze`。当前模型尚未开始训练，因此：

- 已经有可使用的 development、final core 和 refusal diagnostic 评测集；
- 尚未产生任何真实模型 prediction；
- 尚未得到任何模型性能结论；
- prediction lock、sealed final 评分和论文结果汇总必须等待模型及推理配置冻结后再进行。

冻结实现对应 Git commit：
`358bdea55617fcd90a0123b9db2d3285fa27be4b`。正式评测前，应确认实验分支已经包含该提交。

## 2. 评测对象与职责边界

主任务是：

> 自然语言 GIS 任务 -> 不带具体业务参数的 QGIS operator chain

模型输出由两部分组成：

- `processes`：QGIS 算子实例，每个实例包含局部 `process_id` 和 `operator_id`；
- `links`：算子实例之间的有向依赖关系。

主评测严格比较 operator 与 links，不评测以下内容：

- 输入数据文件、图层名称或字段名称；
- 距离、阈值、CRS 编号等具体参数值；
- QGIS 工程文件、Python 代码或实际执行结果；
- 自然语言解释、执行日志或界面操作步骤。

因此，本 benchmark 评测的是 planner 能否给出正确的参数无关处理方法，不等同于完整的
QGIS workflow execution benchmark。

## 3. 数据集组成

| Split | 数量 | 用途 | 使用规则 |
| --- | ---: | --- | --- |
| Development | 40 | 接口调试、误差分析和开发阶段比较 | 可在开发阶段使用，但不得混入训练语料后继续把它报告为独立开发集 |
| Final core | 120 | 论文主结果与最终模型比较 | 模型、prompt、规则、检索库和解码配置冻结前不得查看 gold、review 或 sidecar |
| Refusal diagnostic | 12 | 诊断不支持能力和目标信息不足时的拒答行为 | 与 graph 主任务使用独立分母，不得混入 graph 主指标 |

Development、final core 和 refusal 三个 split 的 `sample_id`、任务文本和来源身份保持隔离。
Final core 与 refusal 的 gold、authority sidecar 和 review 作为 sealed artifacts 管理。

## 4. Graph prediction 格式

单条 graph prediction 使用 JSONL 记录：

```json
{
  "sample_id": "qgis-v01-final-001",
  "processes": [
    {"process_id": "p0", "operator_id": "native:fixgeometries"},
    {"process_id": "p1", "operator_id": "native:buffer"}
  ],
  "links": [
    {"source_process_id": "p0", "target_process_id": "p1"}
  ]
}
```

约束如下：

- `process_id` 只用于单条预测内部引用，可任意命名；
- `process_id` 重命名、JSON 数组顺序和字段序列化顺序不影响评分；
- 同一 process ID 不得重复；
- link 的源和目标必须引用已声明的 process；
- graph 必须是无环有向图；
- 不要求输出具体参数，额外参数字段不进入 v0.1 主评分。

## 5. Refusal prediction 格式

单条 refusal prediction 使用：

```json
{
  "sample_id": "qgis-v01-refusal-001",
  "decision": "abstain",
  "reason_code": "unsupported_capability"
}
```

v0.1 支持两个 reason code：

- `unsupported_capability`：任务超出 stable101/QGIS 冻结能力边界；
- `underspecified_goal`：任务目标不足以确定可靠 operator chain。

仅返回空 `processes` 或空 `links` 不等于拒答。Refusal 样本只要输出任一 process、link，
或给出非 `abstain` 的规划决策，就计入 unsafe planning。

## 6. Graph 评测指标

### 6.1 Operator micro precision、recall、F1

将每条预测和 gold 中的 `operator_id` 视为 multiset，在全部 graph 样本上累计 matched、
predicted 和 gold 数量后计算 micro precision、recall 和 F1。重复算子按出现次数计算。

### 6.2 Edge micro precision、recall、F1

每条依赖边表示为：

`(source operator_id, target operator_id)`

在全部 graph 样本上按 edge multiset 计算 micro precision、recall 和 F1。该指标反映局部
依赖是否正确，但不能单独区分含重复 operator 的所有拓扑。

### 6.3 Graph exact match rate

使用带 `operator_id` 节点标签的有向图同构判断完整 graph 是否与 gold 一致。该指标：

- 忽略 process ID 命名；
- 忽略 JSON 序列化顺序；
- 保留 operator 标签、节点重数和完整有向拓扑；
- 能区分重复 operator 构成的链、分支和汇合结构。

### 6.4 Dependency closure rate

预测只有在 process/link schema 合法、所有 link 引用有效且 graph 无环时，才记为 dependency
closed。该指标不表示语义正确，只表示预测形成了结构闭合的可解释 DAG。

### 6.5 Harmful extra operator rate

预测中超出 gold operator multiset 的算子数量，除以预测算子总数。它用于衡量模型是否加入
任务未要求的处理步骤。

### 6.6 False refusal rate

在 supported graph 样本上输出 `decision="abstain"` 的比例。False refusal 会使该样本的
operator 与 edge matched 数量归零，但 refusal diagnostic 仍保持独立统计。

## 7. Refusal 评测指标

- `refusal_accuracy`：是否正确输出 `decision="abstain"`；
- `reason_code_accuracy`：拒答决策和 reason code 是否同时正确；
- `unsafe_planning_rate`：应拒答时是否仍输出 process、link 或其他规划决策。

Graph 与 refusal 必须分别报告样本数和指标，不计算一个混合总分。

## 8. 多解任务的处理

GIS 任务可能存在多个合理 operator chain，例如先裁剪再计算，或先计算再裁剪。v0.1 的处理
原则是：

- 入选任务应具有足够明确的目标、依赖和输出约束，尽量减少未受控多解；
- exact match 当前以冻结的 gold graph 为准，不自动接受任意语义近似 graph；
- operator/edge PRF 用于展示未 exact match 预测与 gold 的局部接近程度；
- 如果人工复核确认某个不同 graph 在任务约束下确实等价，应记录 adjudication，不能静默改动
  sealed gold；接受新等价答案必须发布新的 benchmark 版本或显式 alternative-gold 扩展。

因此，v0.1 的 exact match 是严格、可复现的主指标，但不能被解释为所有未 exact match 的
预测在 GIS 语义上必然错误。

## 9. 正式评测流程

### 阶段 A：模型训练与开发

1. 只使用获准的 train-only 数据训练模型。
2. 使用 development 40 调试输入输出接口、graph schema 和系统集成。
3. 记录所有基于 development set 做出的模型、prompt、规则和解码调整。
4. 不读取 final/refusal gold、review 或 authority sidecar。

### 阶段 B：实验配置冻结

在正式 final 推理前冻结并记录：

- 模型 checkpoint 及 SHA-256；
- tokenizer、taxonomy 和 QGIS operator authority 版本；
- system/user prompt；
- retrieval index 或外部知识库版本；
- decoding 参数、随机种子和软件环境；
- 任何规则后处理、拒答阈值和 graph repair 策略。

冻结后不得根据 final/refusal 结果回改配置并继续沿用同一个结果名称。

### 阶段 C：Prediction lock

1. 仅使用公开任务文本生成 final core 120 和 refusal 12 的预测。
2. 将 graph 与 refusal prediction 分别保存为 JSONL。
3. 在查看 sealed gold 前计算并记录两个 prediction 文件的 SHA-256。
4. 锁定 prediction 文件，后续评分必须使用完全相同的字节内容。

### 阶段 D：评分与报告

1. 验证 freeze manifest 和 checksum ledger。
2. 使用统一 scorer 读取锁定 prediction 和 sealed gold。
3. 输出逐样本结果、汇总指标、benchmark 版本及 prediction SHA-256。
4. 保存运行命令、环境、checkpoint hash、score artifact 和失败日志。
5. 论文中分别报告 graph、refusal 和 development 指标，不隐藏无效 graph 或缺失预测。

## 10. 统一评分入口

冻结评分器为：

`scripts/score_qgis_planner_benchmark_v01.py`

标准命令为：

```powershell
python scripts/score_qgis_planner_benchmark_v01.py `
  --freeze-manifest benchmarks/qgis_planner_v1/releases/v0.1-freeze/benchmark_manifest.json `
  --graph-predictions path/to/final_predictions.jsonl `
  --refusal-predictions path/to/refusal_predictions.jsonl `
  --output path/to/scores.json
```

评分器会先哈希并解析 prediction 文件，再验证 freeze artifacts 和读取 sealed gold。输出记录
benchmark 版本、graph split、freeze 校验结果和两个 prediction SHA-256。

## 11. 版本与变更规则

- v0.1 Freeze 的 manifest 绑定 24 个 artifacts，顶层 checksum ledger 校验 27 个路径；
- Gold、task text、review、authority、taxonomy、scorer 或指标定义发生影响结果的修改时，必须
  重新生成 checksum，并判断是否需要升级 benchmark 版本；
- Freeze 后不得原地修改 final/refusal gold；
- 发现泄漏、错误 gold 或新的等价 graph 时，应保留问题记录和 adjudication 证据；
- 论文结果必须同时声明 benchmark version、commit、checkpoint hash 和 prediction hash。

## 12. 当前允许的下一步

当前模型尚未训练，benchmark 建设阶段已经结束。因此现在不执行 prediction lock，也不进行
sealed final 评分。下一步应先完成模型训练、development 调试和实验配置冻结；之后再恢复本
协议的阶段 C 与阶段 D。
