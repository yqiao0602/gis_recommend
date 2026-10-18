# 阶段二参考集草案索引 V3（25 条）

- **日期**：2026-10-18；**状态**：owner 第二轮复核后。
- **R19**：结构/同构模板通过；多参考条件已按'条件一致性硬门槛'重写；`conditional_applies_when_pending`。
- **R18A**：同构模板通过；证据 `partial`；准入 `draft_provisional`（补导出-场景映射）。
- **R18B**：结构/聚合通过；多参考暂缓（`geometry` 外部来源未闭合）；证据 `partial`。
- **R20**：聚合语义/尺度通过；P8 已补（7+7 时序图）；多参考仅同构模板。
- **R23**：抽取审计定位通过；S100 分支依赖已核实（RF v2 不用 KMeans；特征集不同）；证据 `partial`。
- **三条阶段三规则**（治理规范 §8.2）：关系≠准入；条件一致性=多参考硬门槛；按脚本重叠连通分量划分。

## 清单（状态）

| ID | 关系判断 | 语义置信 | 证据完整 | 准入状态 |
| --- | --- | --- | --- | --- |
| R01 | — | 高 | complete | draft_provisional |
| R02 | — | 高 | complete | draft_provisional |
| R03 | — | 高 | complete | draft_provisional |
| R04 | — | 高 | complete | draft_provisional |
| R05 | — | 高 | partial | draft_provisional |
| R06 | — | 高 | complete | draft_provisional |
| R07 | — | 高 | complete | draft_provisional |
| R08 | — | 高 | complete | draft_provisional |
| R09 | — | 高 | complete | draft_provisional |
| R10 | — | 高 | complete | draft_provisional |
| R11 | — | 高 | complete | draft_provisional |
| R12 | — | 高 | complete | draft_provisional |
| R13 | — | 高 | complete | draft_provisional |
| R14 | — | 高 | complete | draft_provisional |
| R15 | — | 高 | complete | draft_provisional |
| R16 | — | 高 | complete | draft_provisional |
| R17 | — | 高 | complete | draft_provisional |
| R19 | 结构等价, 同构模板 | 高 | complete_scoped | conditional_applies_when_pending |
| R20 | 结构等价, 同构模板 | 高 | complete | draft_provisional |
| R21 | — | 高 | partial | draft_provisional |
| R22 | — | 高 | complete | draft_provisional |
| R23 | — | 高 | partial | excluded_planning_supervision |
| R24 | — | 高 | complete | draft_provisional |
| R18A | 结构等价, 同构模板 | 高 | partial | draft_provisional |
| R18B | 结构等价, 同构模板 | 高 | partial | draft_provisional |

## 待办

- 其余 19 条按 V1.1 口径复核（关系三分/三状态/跨组）；
- 阶段三：先冻结关系与准入 → 全量重叠扫描合并连通分量 → 任务组级划分 → A/B/C 对照设计。
