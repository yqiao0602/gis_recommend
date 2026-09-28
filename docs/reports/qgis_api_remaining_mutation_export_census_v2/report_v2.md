# QGIS 剩余 mutation/export authority census v2

## 结论

本轮按 normalized source body 对剩余 mutation/export 池做了两层发现：完整
upstream signature，以及单调用/无序调用对 authority 聚合。严格门禁下没有新的
可直接进入校准的 API family。`unary_union` 在 downstream transform 截断后仍只有
21 个正文 authority，继续 deferred。

## 覆盖范围

| 指标 | 数量 |
|---|---:|
| mutation/export 输入 | 2,605 |
| 已审 family 排除 | 158 |
| 剩余单位 | 2,447 |
| resolved local call chain | 1,200 |
| ambiguous multiple reaching definitions | 408 |
| external payload/no local producer | 96 |
| setGeometry span not found | 743 |
| 完整 signature family | 200 |
| support>=30 的完整 signature family | 0 |
| discovery 单调用 | 217 |
| discovery 调用对 | 1,376 |
| support>=30 且非 support-only 的调用对 | 6 |

## 六个高支持调用对

| 调用对 | authority | scope 数 | 完整 signature 数 | 结论 |
|---|---:|---:|---:|---|
| `x + y` | 40 | 11 | 11 | 坐标访问器，不是任务边界 |
| `asPoint + geometry` | 39 | 13 | 12 | 类型访问/构造支撑，跨多个任务 |
| `boundingBox + geometry` | 39 | 5 | 8 | 混合 random-point 与 Hub Distance |
| `boundingBox + center` | 37 | 4 | 7 | Hub Distance 点/线输出混合 |
| `center + geometry` | 37 | 4 | 7 | Hub Distance 点/线输出混合 |
| `getObjectFromUri + getParameterValue` | 34 | 7 | 7 | 参数解析基础设施 |

Hub Distance 按点/线最终输出拆分后，最大单一 scope 只有 12 个 authority；不能把
共现支持误当成可复用算法 family。所有 discovery 产物均为 report-only，mapping、
description 和 training admission 均为 0。

## 下一步

停止继续细分这六个调用对，转向尚未恢复的 1,247 条：408 条分支多定义、96 条无本地产生者、
743 条未定位 `setGeometry`。恢复规则应按批量校准后全池 replay，不逐条人工准入。

产物：`summary_v1.json`、`priority_call_cooccurrences_v2.jsonl`、
`upstream_call_census_v2.jsonl`、`upstream_call_cooccurrence_census_v2.jsonl`。
