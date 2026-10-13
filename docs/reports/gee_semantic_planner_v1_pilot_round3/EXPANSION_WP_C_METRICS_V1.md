# 工作包 C：指标计算口径 v1（冻结）

状态：EXPANSION_WP_C_METRICS_V1 / DENOMINATORS_FROZEN / NOT_EXECUTED
日期：2026-10-09
授权依据：owner 裁定（2026-10-09）——冻结指标口径；保留候选阈值。
前置：EXPANSION_DESIGN_V1.md §3；六脚本回测（wp_a_backtest_v1）。

## 1. 固化率（C1，候选阈值 ≤5%）

四类计数**全部随结果产出**，缺一不可：

| 字段 | 定义 |
|---|---|
| `checked_units` | 人工/自动检查的总单元数 |
| `judged_implementation_detail_candidates` | 已裁定为实现细节候选的数量 |
| `misassigned_to_duty` | 错误提升为任务职责的数量（固化案例） |
| `undeterminable` | 无法裁定的数量 |

**固化率 = misassigned_to_duty / (judged_implementation_detail_candidates + misassigned_to_duty)**

- 分母 = 已裁定单元；`unchecked` 与 `undeterminable` 单独报告，**不得进入分母稀释**；
- 原始计数与比率并列报告；
- 每个固化案例逐条解释并登记；无法归因、无法修正的超标触发停止条件 S2。

## 2. 自动化-人工一致率（C2，目标 ≥90%，按检测器分列）

对 **A1、A2、A3、A4 各自独立计算**：

```
agreement_X = 一致样本数_X / 盲标子集总样本数_X
```

- 数据来源 = 工作包 B3 **盲标独立子集**（两名标注者不知自动化结论，独立标注完成后才对照）；
- 分歧案例逐条归因三分类：`detector_rule_defect` / `annotator_criteria_divergence` / `genuine_edge_case`，归因记录进 `divergence_ledger`；
- 区间判读：≥90% 达标；**80–90% 未达标**（需归因与复审，不自动通过）；<80% 触发停止条件 S3；
- **禁止**只报告四检测器汇总的单一百分比。

## 3. 冲突静默调和（C3，零容忍）

- 计数：`silent_reconciliations` = 冲突登记项中任一侧被丢弃/被自动调和的次数；
- 判据：`= 0` 即通过；`> 0` 即 fail，**不得被其他任何指标抵消**；
- 每个已登记冲突必须输出两侧完整保留证据（`side_task` / `side_source` / `resolution: preserved_both`）。

## 4. 描述性指标（如实报告，不设阈值）

| 指标 | 口径 |
|---|---|
| 语义恢复率 | 每脚本 audit-unit 分母内恢复比例；报告 min/median/分布；非单一成败指标 |
| 证据支持率 | `supported` / `supported_passing_only` 分列计数与比例；两态不合并 |
| 未决项比例 | `unresolved / 总关系数`；附主要原因归类（外部依赖 / 信息不足 / 边界） |
| 重复边比例 | 原始记录数 vs 去重逻辑边数；去重后逻辑重复应为 0 |
| 人工复核成本 | 每脚本人工分钟数；分脚本与分阶段（重建核对 / 盲标 / 裁定）记录 |
| 各层样本数 | L1–L5 各层入选数 + 去重脚本总数 + R/C 组规模，全部并列报告 |

## 5. 停止条件（与 EXPANSION_DESIGN_V1 §3.C4 一致）

1. **S1** 冲突静默调和 > 0；
2. **S2** 固化率 > 5% 且无法归因为可修规则缺陷；
3. **S3** 任一检测器一致率 < 80%；
4. **S4** 出现六试点未见过的新型失效模式且现有规则无法分类。

## 6. 实现绑定

- 指标计算脚本：`scripts/compute_expansion_metrics_v1.py`（执行阶段随批准一并运行；输入 = 重建产物 JSON + 盲标记录 + 分歧台账）；
- 抽样脚本：`scripts/build_expansion_validation_sample_v1.py`（已实现并通过设计冻结测试 23/23；`--design-only` 输出冻结设计清单，`--execute` 需 owner 批准后一次性运行）；
- 设计清单：`expansion_validation_prep_v1/sampling_design_manifest_v1.json`（seed=20261009 已冻结）。
