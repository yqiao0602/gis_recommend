# Route-2 L-bench 报告：P0-6 final-100 + refusal-12（三臂，补齐）

日期：2026-09-24
地位：P0-6 辅判据补齐（主判据 test-111 已于 Gate 2 报告交付，判定不变）。
协议：P0-6 一次性；生成 = route-2 冻结配方（task_text + "\nQGIS workflow:"，greedy 512，eos 表）；解析 = `text_to_graph` 首行 fail-closed；评分 = `score_benchmark` 逐字导入（`score_qgis_planner_benchmark_v01.py`）；预测 SHA 锁 = `ROUTE2_LBENCH_LOCK_v1.json`。
Refusal 政策（跑前声明于锁文件）：三臂为 SFT-only、无弃权训练 → decision=generate + 实测图；refusal 指标是对 always-plan 行为的诚实测量。

## 1. 主表（qgis-planner-benchmark v0.2.1，final-100 n=100）

| | op F1 | edge F1 | graph EM | dependency closed | harmful extra | false refusal |
|---|---:|---:|---:|---:|---:|---:|
| **C0** | **0.432** | **0.288** | **0.14** | 0.92 | 0.625 | 0.0 |
| A1 | 0.377 | 0.223 | 0.09 | 0.98 | 0.684 | 0.0 |
| B1 | 0.347 | 0.166 | 0.04 | 0.97 | 0.662 | 0.0 |

refusal-12（n=12）：三臂 refusal_accuracy = **0.0**、unsafe_planning_rate = **1.0**——SFT-only 臂不会弃权，全部对不可支持任务强行生成。与 M1/M3 时代 always-plan 行为一致，属预期记录。

## 2. 判读

1. **C0 > A1 > B1（op F1）**：负迁移在第二评价面上复现（test-111 与 final-100 排序 C0 均居首）。
2. **B1/A1 排序随面翻转**：test-111（route2 口径）B1 > A1；final-100（v0.2.1 口径）A1 > B1——B1 的连接面优势（Gate 2 记录）**不跨评价面稳健**，写作时不得作为强结论。
3. **过量生成签名全面复现**：harmful_extra 63-68%（三臂全部），与 FA 的 Generation Control 归因一致；A1 最高（68.4%）。
4. **绝对水平**：C0 op F1 0.432 / EM 0.14——真实任务面（任务族广于 test-111）仍是困难任务；与 GISAgentBench（最高 TSR 32.7%）同为"低绝对值、高诊断价值"区间。

## 3. 工件

`docs/reports/transfer_phase2/dc/`：ROUTE2_LBENCH_SCORES_v1.json、ROUTE2_LBENCH_LOCK_v1.json（三臂 100+12 行 SHA）、`v2a_dc2ar1_a1_predictions.jsonl` 等同批。生成/评分脚本：`scripts/route2_lbench_eval.py`（score_benchmark 逐字导入）。服务器缺口（materialized/gold 文件）已补传。
