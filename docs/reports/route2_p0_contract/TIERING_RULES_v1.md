# ⑥-3 Plan Quality Tiering 规则 v1（2026-09-24，阈值预注册）

## 原则

- 阈值在跑全量**之前**冻结（来源 = ⑥-2 已登记错误家族的特征），跑后不反调。
- 48 条人审比例**不用于**设定阈值，只用于**事后交叉验证** tiering 与
  人工判定的一致性（保真≈A / 偏差≈B / 失败≈reject）。
- converter v1.2 与知识表不再改动。

## 特征定义（对每个成功转换的 Plan）

| 特征 | 定义 |
|---|---|
| prov_run_max | 连续 provision 步的最大长度 |
| flow_breaks | 未解释类型流断裂数（branch 消费路径不计） |
| slot_incomplete_steps | 缺 roles 且缺 constraints 且非 provision 的步数 |
| utility_ratio | (provision 步 + 参数类步) / 总步数 |
| branch_ratio | branch 标记步 / 总步数 |
| n_steps | 总步数 |

## 分层规则（按顺序判定，命中即停）

**HARD REJECT**（F-STRUCT-01 / 结构不一致）：
- `prov_run_max ≥ 3`（F-STRUCT-01 特征）
- 或 `flow_breaks ≥ 2`（重复未解释断裂）
- 或 schema 校验失败 / leakage > 0（断言，当前恒 0）

**Tier A**（直接监督）：全部满足
- `flow_breaks == 0`
- `slot_incomplete_steps == 0`
- `prov_run_max ≤ 1`
- `utility_ratio ≤ 0.5`
- `branch_ratio ≤ 0.5`
- `n_steps ≥ 3`

**Tier B**（可用，已登记轻微偏差）：全部满足
- `flow_breaks ≤ 1`
- `slot_incomplete_steps ≤ 1` 且非终端步
- `utility_ratio ≤ 0.7`
- `branch_ratio ≤ 0.7`

**Tier C**（诊断/分析，不入主训练池）：其余。

## 产出

- `plan_pool_tiered_v1.jsonl`（59,835 行：plan + tier + 全部特征）
- `tiering_report_v1.json`（分布 + per-tier 统计）
- 交叉验证：48 条人审样本的 auto-tier vs 人工判定一致性矩阵
