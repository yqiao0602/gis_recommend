# QGIS Planner Benchmark v0.2 Budget Matrix

状态：`frozen_for_supply_repair`  
冻结日期：2026-09-10  
机器可读 authority：`v02_budget_matrix.json`

## 冻结内容

v0.2 固定约 120 条 final task、60 个 canonical DAG、每个 DAG 两个 task text 变体；development 固定约 40 条 task，目标 36 个 canonical DAG。development 与 final 必须 DAG-disjoint、source-disjoint。

Final canonical DAG 目标：

| 维度 | 目标 |
|---|---:|
| chain length: 1-step / 2–3 / 4–6 / 7+ | 6 / 28 / 18 / 8 |
| topology: linear / merge / branch | 32 / 20 / 8 |
| modality: vector / mixed / raster | 40 / 12 / 8 |
| task_style: operator_explicit / planning_oriented | 60 / 60 条 task |

因此 raster 或 mixed 至少覆盖 20 个 DAG，1-step 至少 6 个 DAG，branch 至少 8 个 DAG，7+ 至少 8 个 DAG。

Development canonical DAG 目标为 8 / 18 / 8 / 2（按 chain length）、22 / 8 / 6（按 topology）、24 / 7 / 5（按 modality）。优先一 DAG 一条 task；最多 4 个 DAG 使用第二个文本变体补足 40 条。

## Family envelope

Roster authority 已冻结 20 个 supported family，按 A/B/C/D tier 给出 4/4/3/2 个 DAG 的名义目标，总上限 64 个 DAG。Final 预算上限为 60；若供给足以达到 64，按 D-tier 最低结构贡献优先裁减 4 个 slot，并在 audit 中记录 `quota_shortfall`，不得静默替换 deferred/out_of_scope family。

candidate quota 只表示供给门槛，不等于可评测数据。只有通过独立 graph review、Gate 2 九索引零重叠和人工批准的记录，才可计入 task+gold 交付数。

## Gate 状态

- R1 roster authority：已完成，使用 `v02_supported_family_roster.json`。
- R2 budget authority：已完成，本文件及 `v02_budget_matrix.json` 为冻结入口。
- R3 supply repair：未开始；下一步仅对 supported family 补货。
- R4 review、R5 freeze：未开始。

当前 v0.2 可交付 task+gold 仍为 `0`。脚本、schema、candidate、review job 和配额本身都不计为评测集进度。
