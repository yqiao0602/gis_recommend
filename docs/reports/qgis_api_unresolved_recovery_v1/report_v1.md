# QGIS API 未恢复池批量恢复 v1

## 目的

对 mutation/export-only 的 2,605 个低层 API 单元，批量验证三类恢复规则：

1. 分支多定义的 control-path 等价合并；
2. helper caller-to-callee provenance；
3. 无显式 `setGeometry` 时，从 `addFeature`/`writeAsVectorFormat*` 终端参数反向切片。

规则只生成 source-backed census evidence，不直接准入训练集。所有源码仍从
`/home/yll` 只读读取，按原始 `source_sha256` 校验。

## 全池结果

| 阶段 | ambiguous | external | resolved | 无 setGeometry |
|---|---:|---:|---:|---:|
| v1 基线 | 416 | 96 | 1,350 | 743 |
| v2 control-path 等价 | 338 | 96 | 1,428 | 743 |
| v3 caller provenance | 382 | 51 | 1,429 | 743 |
| v4 terminal sidecar | 382 | 51 | 1,429 | 743 |

v3 中 external 的 45 条找到本地 helper 调用点，但其中 44 条因调用链不一致或
部分调用点无法回溯而保持 ambiguous；只有 1 条满足所有调用点等价，新增 resolved
authority 支持为 1。

## Terminal payload 结论

743 条无显式 `setGeometry` 的单元全部保持原有任务边界状态。终端参数 sidecar
结果为：

| terminal 状态 | 数量 |
|---|---:|
| `support_or_custom_only` | 593 |
| `no_local_terminal_payload_chain` | 109 |
| `ambiguous_terminal_payload` | 41 |
| `known_geometry_semantic_candidate` | 0 |

这些单元的抽取 pattern 均为 `field_attribute_edit + sink_output`，没有可证明的
几何算法边界，不能把属性写出或普通 `QgsFeature` 构造当作训练算子。

## Family 与训练门禁

用当前 158 条已审 family 做 source-authority 排除后，剩余 2,447 条的 v4 census
为：1,278 resolved、375 ambiguous、51 external、743 terminal-only。完整
normalized signature 共 210 个，但 `support>=30` 的新 family 为 0；7 个高支持
调用对仍是参数/访问器或混合任务，不进入 calibration。

因此本轮：

- L3 mapping rows: 0
- description fidelity rows: 0
- training rows: 0
- validation/test/production: 未授予
- LLM: 未调用

## 可复用方法

当前分析器已固化为
`control-path-caller-and-terminal-backward-slice-v4`：

- 分支定义只有在归一化调用序列完全相同时才合并；
- helper 只有在所有本地调用点都可回溯且调用序列完全相同时才合并；
- terminal payload 仅作为 report-only sidecar，不绕过 `setGeometry` 任务边界门禁。

## 产物

- 全池 replay：`docs/reports/qgis_api_mutation_upstream_census_v6/`（与 v5 的 mutation JSONL SHA 逐字节一致）
- family census：`docs/reports/qgis_api_remaining_mutation_export_census_v4/`
- 实现：`scripts/analyze_qgis_api_mutation_upstream.py`
- 回归测试：`tests/test_analyze_qgis_api_mutation_upstream.py`（14/14）

## 下一步

停止继续细分这 1,247 条 unresolved recovery lane。回到 Processing 阶梯：先用已经
验证的 30–50 条方法扩展到 200–300 条，再做随机分层 500–1000 条抽检，最后才全量
处理 8,466 条。13,554 个 API-pattern candidate 暂缓；mutation/export 规则产物只
作为审计证据，不计入训练样本。
