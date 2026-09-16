# M1-R2 评测报告：decoder backbone domain pretraining 的完整 R1 vs R2 对照（Phase 2 收官）

日期：2026-09-16
模型链：DAPT（493.4M byte-tokens，ckpt `83d56745…`）→ migrate 审计 8/8 → SFT（R1 协议逐行不变，best composite 0.2802 @ ep15，ckpt `22a77f77…`）
评测纪律：INFERENCE_CONFIG_FREEZE_v1 全套（task_type=Unknown、structured prompt、max_length 40、expected_length 8）；R4 顺序遵守——R2 final-100+refusal-12 预测哈希**先于 gold 访问锁定**（`predictions_r2/PREDICTION_LOCK_R2_v1.json`）；冻结 scorer verbatim（`score_qgis_planner_v021.py`）；M3 块重评分 = 锁定值精确复现（F1 0.1605）✓

## R1 vs R2 完整对照表

### 生成行为（collapse 层，final-100）

| 指标 | M1-R1 | M1-R2 | Δ |
|---|---:|---:|---:|
| 空图率 | 88/100（88%） | **20/100（20%）** | **−68pp** |
| bridge 丢弃率 | 83.8%（129/154） | **43.9%（232/528）** | −39.9pp |
| L3 token 总数 | 154 | **528** | ×3.4 |
| 首 token 去重数 | 2 | 3（AddSpatialIndex 70 / LakeInundation 26 / Simplify 4） | +1 |
| Define Projection 首 token | 99% | **0%** | 吸引子消失 |
| 平均/中位/最大链长 | 1.5 / 1 / 6 | **5.3 / 6 / 11** | 恢复参考量级（gold ~2-6） |
| runaway ≥20 | 0 | 0 | 双方无 |
| 图内算子 top-3 | fixgeometries 12 / convertformat 7 / reproject 6 | fixgeometries 88 / fieldcalculator 42 / reproject 35 | 多样化 |

### 图级分数（冻结 scorer，final-100 operator micro）

| 指标 | M1-R1 | M1-R2 | Δ | M3（参照） |
|---|---:|---:|---:|---:|
| Precision | 0.0400 | **0.1014** | +0.061 | 0.1152 |
| Recall | 0.0025 | **0.0743** | +0.072（×30） | 0.2649 |
| **operator F1** | **0.0047** | **0.0857** | **+0.081（×18）** | 0.1605 |
| edge F1 | 0.000 | 0.000 | 0 | 0.0447 |
| graph EM | 0/100 | 0/100 | 0 | 1/100 |
| harmful extra op rate | 0.960 | 0.899 | −6pp | 0.885 |
| refusal unsafe 12 | 12/12 | 12/12 | always-plan 政策 | 4/12 |

### 近分布能力（val 49 诊断 + 训练侧）

| 指标 | M1-R1 | M1-R2 | Δ |
|---|---:|---:|---:|
| val Top1（训练史最佳） | 14.87%（@ep16） | 15.24%（@ep20） | +0.4pp |
| 诊断 code P | 0.1532 | 0.1635 | +0.010 |
| 诊断 code R | 0.1978 | 0.2180 | +0.020 |
| 诊断 F1（推导） | 0.173 | 0.187 | +0.014 |
| exact chain | 0/49 | 0/49 | 0 |
| 长度误差 | +1.04 | +1.08 | ≈持平 |
| EOS 终止 | 48/49 | 49/49 | ≈持平 |
| 训练 best composite | 0.3310（@ep18） | 0.2802（@ep15） | −0.051 |

## 结论（owner A/B/C 框架判定：B，偏乐观侧）

**核心发现是一个干净的分离**：

1. **OOD 结构性塌缩大幅修复且稳定复现**（dev-20 与 final-100 一致）：空图 −68pp、token 产出 ×3.4、bridge 丢弃 −40pp、单一吸引子消失、链长恢复、operator F1 ×18——**decoder backbone domain pretraining 对"能不能生成"的问题给出强肯定答案**
2. **近分布任务能力基本持平**：val Top1 +0.4pp、诊断 F1 +0.014、训练侧 composite 反而略低——DAPT 没有增加任务知识
3. **任务条件映射与链结构仍未建立**：首 token 仍集中在 3 个码（70/26/4）、edge F1 = 0、harmful extra 0.90（fixgeometries 出现 88/100 次，呈"万能开头"新偏置形态）——**"生成什么"的问题未被解决**

**论文表述**：decoder backbone domain pretraining 在完全冻结协议下将 M1 的结构性生成塌缩（88% 空图）修复至 20%，operator F1 提升 18 倍，但对任务条件映射与链结构（edge）无实质改善——领域序列先验解决生成可行性，不解决任务语义选择。与 Phase 0-B 的四层归因对照：R2 针对③（domain prior 不足）的修复部分有效，①（task_type 条件化）与②（文本 OOD 条件映射）仍是未解瓶颈。

**R3 判断依据（供 owner 决策，不启动）**：R3（BERT encoder 侧领域适配）针对的是条件化通路（encoder→memory），恰好对准剩余瓶颈①/②的方向；R2 的"结构修复+映射未解"格局支持 R3 有明确的假设空间。但按纪律，R3/R4 是否开由 owner 视 R2 定稿结果决定。

## Evaluation Environment Incident（独立记录，不混入 R2 数字）

- **事件**：R2 dev-20 首次运行（2026-09-16 08:41）无效——启动命令漏设 `GIS_OUTPUTS_DIR`/`GIS_ID_MAPPINGS`，inferencer 回退 legacy id 映射，token 114/118 落在旧词表外 → 全部输出为 UNK、bridge 丢弃 87.4%
- **证据**：`m1_r2_dev_20_predictions.jsonl`（无效版，服务器留存）；模型行为与 v2 一致（首 token token-id 分布 10/10 vs 11/9），坏的只是映射环境
- **修复**：v2 重跑带全套冻结环境变量（与 `m1_r1_dev_eval.py` 的防泄漏注释同一纪律），bridge 丢弃 48.2%
- **教训固化**：M1 推理的三个环境变量（`GIS_VOCAB_PROFILE`/`GIS_OUTPUTS_DIR`/`GIS_ID_MAPPINGS`）必须打包成启动入口的一部分，不能依赖调用方记忆——已在此报告中记录，后续任何 M1 推理脚本化时直接内嵌
- 另一同类事件：R2 val 诊断首次运行崩于 `--taxonomy` 默认路径（服务器 repo 缺该文件；Phase 0-B 已知坑），显式传 SHA 核验过的副本后成功

## 产物清单

- `docs/reports/qgis_planner_eval_v1/predictions_r2/`：R2 final-100 + refusal-12 预测（m1_*）、M3 锁定预测副本（复现校验用）、`PREDICTION_LOCK_R2_v1.json`
- `docs/reports/qgis_planner_eval_v1/SCORES_R2_v1.json`：冻结 scorer 输出（含逐样本分数）
- 本目录：`r2_val_diagnostic_metrics_v1.json`（49 行诊断）、`reload_gate.json`、dev-20 v2 / final-100 运行日志
- 服务器：`m1_r2_dev_20_predictions_v2.jsonl`（dev-20 有效版）、`m1_r2_val_eval/`（诊断逐行）、`m1_r2_sft_ckpt/`（SFT checkpoints + 训练史）
