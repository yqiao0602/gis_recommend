# GEE 完整工作流第二批扩展与 200-300 行交付

日期：2026-08-01

## 结论

冻结的确定性完整工作流转换器已完成第二批 source-disjoint 扩展。新增 154 条
`gis_recommend.gee_workflow_train_row.v1` train-only 行，与既有 125 条合并后得到：

| 产物 | 行数 |
| --- | ---: |
| 完整语义训练行 | 279 |
| 当前 V4-100 可加载行 | 278 |
| 155 步 length sidecar | 1 |
| 新增 duplicate | 0 |
| 新增 length defer | 0 |

因此，阶段性 `200-300` 可训练行门禁已经完成。validation/test、production merge 和模型训练
仍未开放。

## 规则修正

独立审核发现两类 Export 输出契约问题，并以通用规则修正后整批重放：

- `Export.table*` 必须接收可证明的 `ee.FeatureCollection`，不能把
  `ImageCollection` 当作 table 输出。
- `Export.map*` 必须接收可证明的 `ee.Image`，任务输出必须描述为 `map tiles`，不能回退为
  `video`。未知 `Export.*` family 统一 fail-closed。

修正后的 facts A/B 双跑保持 `185 fact bundle / 8 fail-closed / 157 canonical task text`。
与上一 authority 相比，facts 和文本均只有 `data140000/script_137440.txt` 对应的一行变化；
该样本完整链为 `filterdate -> select -> filter -> mosaic -> visualize`，输出为
`Export.map.toCloudStorage`。

## 抽样与准入

v6 expansion A/B 双跑一致，得到 154 条 proposal、100 个 proposal source、68 个排除既有
32-source 审核并集后的可抽样 source。冻结的 30-source 分层审核与 v5 使用相同 source manifest，
仅 map 样本 authority 发生预期变化。29 条审核结论按精确 authority 继承，修复后的 map 样本
重新核对源码、链、L3、输出和任务文本。

最终审核结果：

- 30/30 pass；
- point precision = 1.0；
- Wilson 95% lower = 0.8864866068260312；
- critical failure = 0；
- decision = `passed_for_larger_source_disjoint_replay`。

该结果按冻结政策授权同一 v6 规则 population 的全部 154 条 proposal，不要求逐条人工审核。

## 可复现性与训练路径验证

- facts authority SHA256：
  `34db42c625b18acd6c051c63882f8c4209c9b4991a010d90e2dbd0162e55cbe9`
- task-text authority SHA256：
  `334ae48905d2983d3e065496c948b0b56cf865464d00a578af977dabcbc24bc3`
- proposal SHA256：
  `1ecf2966bbd9eb2f343bfb13f44f1cd81dc63b9cbd1e0dbc763bea4906b05e37`
- combined semantic SHA256：
  `846dc53e0a60e5aeb1d4aae71650a5980417a6318eabe569cfc46f9c21a173ac`
- combined V4-100 SHA256：
  `d9baf737a1decd36f279ed9193d5d9e73ea59d7f306a012a8d78f5f794ec4dc0`
- stable-94 mapping SHA256：
  `005699dfd438e966cda28db8891795a07b9867856951de022cd8704c6e6a4558`

服务器训练包 `_a`、`_b` 逐字节一致。真实
`TaskConditionedL3DatasetV4 + weighted_sequence_cross_entropy + backward` smoke 覆盖
278/278 行，单批形状 `[278, 100]`，loss 与 gradient 有限，max token=92，最大模型序列长度=92，
`checkpoint_written=false`、`training_run=false`。

本地聚焦回归为 71 passed、1 skipped；其中 facts 测试 34/34 通过。服务器 base Python 未安装
pytest，因此不宣称服务器 pytest 通过。

## 权威产物

- 服务器 facts：
  `/home/qy/system_redesign/diagnostics/gee_workflow_task_facts_batch2_500_20260801_exportmap_v3_a`
- 服务器 expansion：
  `/home/qy/system_redesign/diagnostics/gee_complete_workflow_expansion_batch2_exportmap_v6_20260801_a`
- 服务器审核：
  `/home/qy/system_redesign/diagnostics/gee_complete_workflow_expansion_batch2_exportmap_v6_audit_evaluation_20260801`
- 服务器训练包：
  `/home/qy/system_redesign/diagnostics/gee_expansion_training_batch2_exportmap_v6_20260801_a`
- 服务器 smoke：
  `/home/qy/system_redesign/diagnostics/gee_expansion_training_batch2_exportmap_v6_smoke_20260801_a`
- 本机产物：`docs/reports/gee_*exportmap_v6*/`

下一阶段使用新的 source-disjoint selection 扩到累计 500-1000 行，继续采用全批确定性 gate 和
30-50 条分层抽样。只有抽样发现系统性错误时才修一条通用规则并整批重放。
