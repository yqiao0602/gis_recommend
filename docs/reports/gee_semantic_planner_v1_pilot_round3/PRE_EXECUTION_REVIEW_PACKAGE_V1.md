# 执行前审查包（Pre-Execution Review Package）v1

状态：PRE_EXECUTION_REVIEW_PACKAGE_V1 / AWAITING_OWNER_RULING / NOT_EXECUTED
日期：2026-10-09
授权依据：owner 裁定（2026-10-09）——完成 B/C 冻结，提交执行前审查包；**由 owner 裁定是否启动小规模验证**。
本包是**审阅文档**，不包含任何新样本抽取或重建执行。

## 1. 包内容清单

| # | 组件 | 位置 | 状态 |
|---|---|---|---|
| 1 | 设计文档 v1（含 owner 三修订） | `EXPANSION_DESIGN_V1.md` | 已冻结 |
| 2 | 抽样方案 v1 | `EXPANSION_WP_B_SAMPLING_V1.md` | 已冻结 |
| 3 | 抽样脚本 | `scripts/build_expansion_validation_sample_v1.py` | 已实现，未执行 |
| 4 | 抽样设计清单 | `expansion_validation_prep_v1/sampling_design_manifest_v1.json` | seed=20261009 冻结 |
| 5 | 指标口径 v1 | `EXPANSION_WP_C_METRICS_V1.md` | 分母冻结 |
| 6 | 盲标协议 | 本文 §3 | 预注册 |
| 7 | 停止条件 | 本文 §4（=WP-C §5） | 冻结 |
| 8 | 测试 | `tests/test_expansion_validation_sample_v1.py`（10 项）+ `tests/test_wp_a_detector_backtest_v1.py`（13 项） | 23/23 通过 |
| 9 | 哈希记录 | 本文 §5 | 已登记 |

## 2. 抽样脚本要点（批准后一次性运行）

- 用法：`python scripts/build_expansion_validation_sample_v1.py --execute --train-split <G0 train split 清单>`；
- `--train-split` 执行时 pin 清单路径与 SHA（设计阶段不预设路径，与冻结方案一致）；
- 七组：L1–L5（每层 ≥5，检测器判据）+ C 对照（≥10，零命中）+ R 独立随机（≥10，Algorithm-R reservoir，**不依赖检测器**）；
- 确定性：候选按 script id 排序；层内按命中分降序、id 升序破并列；R 组独立 RNG 流（同 seed）；
- 六试点硬编码排除；每入选脚本 pin `source_sha256`；
- 输出 `sample_ledger_v1.json` + 哈希账本；清单冻结后不可再改（改动须重开裁定）；
- L1–L5 允许重叠，同时报告各层样本数与去重脚本总数。

## 3. 人工盲标协议（预注册）

### 3.1 盲标独立子集

- 抽样后，从复核样本中**预先**指定盲标子集（建议：每检测器 ≥10 个判定样本，覆盖 A1 候选 / A2 三分类 / A3 分类 / A4 去重对）；
- 两名标注者**不知道**自动化结论，仅看源码独立标注；
- 双方标注完成并登记后才与自动化结果对照；
- 一致率按 A1–A4 **分别计算**（WP-C §2 口径）。

### 3.2 流程

1. 自动重建产出 → 封存（盲标者不可见）；
2. 盲标（双盲、独立）；
3. 对照：一致 → 计入 agreement；分歧 → `divergence_ledger` 逐条归因（`detector_rule_defect` / `annotator_criteria_divergence` / `genuine_edge_case`）；
4. 裁定：分歧不平均，记录后由第三方裁定；
5. duty 粒度争用样本：两人独立标注（承接 Step 1 Q3 inter-annotator 检验）。

### 3.3 抽验

- 非盲标子集：每脚本人工抽验 ≥30% 单元。

## 4. 停止条件（任一触发即停止扩展并回审）

1. **S1** 冲突静默调和 >0（零容忍，不可被其他指标抵消）；
2. **S2** 固化率 >5% 且无法归因为可修规则缺陷；
3. **S3** 任一检测器一致率 <80%（80–90% 为未达标区间：归因+复审，不自动通过）；
4. **S4** 出现六试点未见过的新型失效模式且现有规则无法分类。

## 5. 哈希记录

| 产物 | SHA-256 |
|---|---|
| `sampling_design_manifest_v1.json` | `7b0769c7177b4d465997de6e0fad6b92b31cd7e87b416833f1783f97169bc06a` |
| 六试点源码（回测输入） | `wp_a_backtest_v1/wp_a_backtest_hash_ledger_v1.json` |
| 回测结果 | 同上账本首项 |

（批准执行后，`sample_ledger_v1.json` 及每入选脚本 SHA 将生成并追加至 `sample_ledger_hash_v1.json`。）

## 6. 批准后执行序列（待裁定）

1. owner 批准 → 冻结最终样本量 N（预估 30–60 含重叠）；
2. 运行抽样脚本（一次性）→ `sample_ledger_v1.json` 冻结；
3. 指定盲标子集 → 双盲标注；
4. 自动重建（逐脚本，按 RECONSTRUCTION_PILOT_METHOD_V1 规则）；
5. 对照 + 分歧归因 → WP-C 指标计算；
6. 报告 → owner 裁定下一步（扩大 / 修正规则后再试 / 停止）。

## 7. 边界（不变）

不修改冻结试点产物；不开展全库重建；不进入训练/推理/RL；G0/G1/G2/G3、Blueprint、GATE_B、S3、locked test 保持冻结；产物仅为监督候选材料，非 gold。
