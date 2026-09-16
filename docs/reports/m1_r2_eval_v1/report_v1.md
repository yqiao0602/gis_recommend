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

## 结论（owner 定稿 2026-09-16：M1 线收束）

**M1-R2 证明了一个局部因果结论，同时暴露了数据/条件映射是剩余主瓶颈。**

**最终措辞（owner 定稿）**：**R2 提升了"生成什么样的序列"的结构能力，但没有显著提升"根据任务语义生成哪一条具体工作流"的条件映射能力。**

双层分解（与 Phase 0-B 归因闭环——R2 验证并细化了它，未推翻）：
- **层次 A 生成器状态**：R1 有明显 decoder collapse；R2 证明 GIS domain pretraining 能改善 decoder 对 GIS 操作序列结构的建模（空图 88%→20%、F1 ×18、吸引子消失，dev-20 与 final-100 方向一致——非偶然波动）
- **层次 B 条件映射**（task text → 选哪个 operator → 如何组合）：未获明显改善（首 token 3 码集中、edge F1=0、Top1 14.87→15.24%、EM 0/100、近分布诊断基本持平）

**三路线一致信号（论文措辞，owner 定稿）**：三条模型路线（M1-R1/R2、M2 三臂、M3-P2-T1）的实验结果均显示，单纯改变模型初始化、领域预训练或监督优化策略，对 task→L3 条件映射能力的提升有限，因而现有训练数据中的任务语义—算子映射监督不足，成为当前**值得优先检验的主要候选瓶颈**（严格因果角度：模型结构、标签体系、文本质量、L3 粒度等因素仍可能共同作用——不写"已证明瓶颈一定来自数据"）。

**Phase 3 裁决**：R3/R4 不开；M1 增强线收束于本报告 + 提交 5e3f818。下一阶段杠杆转向 paper_v2 数据侧（25.7 万描述库意图重写，补 task→operation→operator 监督），R1/R2/M2/M3 作为前置基线与 paper_v2 模型干净比较。

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
