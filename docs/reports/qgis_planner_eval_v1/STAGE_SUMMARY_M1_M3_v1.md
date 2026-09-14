# 阶段性实验结论：M1 / M3 / M3-P2（qgis-planner-benchmark v0.2.1, final-100）

日期：2026-09-14
基准：qgis-planner-benchmark v0.2.1 @ 6006e49（final-100 + refusal-12）
评测栈：materializer（33/33 断言）→ 桥接 v1（50 code）→ 冻结推理配置 → prediction lock → 冻结 scorer
账本：13 条（M1×2、M3-P0×1、M3-P1×10；1 条 superseded）

---

## 1. 实验矩阵（全部为锁定后正式分数）

| 实验 | 模型 | 训练方式 | Operator F1 | Recall | Precision | Runaway¹ | 空图 | 核心发现 |
|---|---|---|---:|---:|---:|---:|---:|---|
| M1-R1 | 117M scratch | V4.6+平台分层采样 | 0.005 | 0.002 | 0.040 | — | 88/100 | 能力边界：OOD 塌缩到单一 code |
| M3-P1 | Qwen 9B (post-trained) | plain SFT | 0.1605 | 0.2649 | 0.1152 | 31 | 4 | 算子选择出现，sequence control 缺失 |
| M3-P2-D1 | 同 P1 | decode: rep_penalty 1.2 | 0.0982 | 0.0545 | 0.500 | 0 | 69 | token 惩罚压制 L3_ 前缀 → 空图 |
| M3-P2-D2 | 同 P1 | decode: no-repeat-ngram 3 | 0.0284 | 0.0149 | 0.333 | 0 | 82 | trigram 阻断 × 共享前缀词表 = 致命 |
| M3-P2-D3 | 同 P1 | decode: 两者同时 | 0.0289 | 0.0149 | 0.545 | 0 | 89 | 组合加剧塌缩 |
| **M3-P2-T1** | 同底座 | **SFT + 终端EOS loss×2** | **0.1991** | **0.2624** | **0.1604** | **18** | 10 | sequence control 可训练改善 |

¹ runaway = 预测 ≥20 算子的行数。诊断参照（非正式分数）：后处理连续去重上限 **0.2838**；oracle 截断 **0.2949**。

辅助指标：Edge F1 — P1 0.045 → T1 0.058；Graph EM — P1 1/100 → T1 2/100；Harmful Extra — 0.885 → 0.840。
Refusal（always-plan 裁定）：两条路线 refusal_accuracy 均 0；unsafe_planning P1 4/12、T1 6/12。

## 2. 三条结论（对应三个预注册问题）

### M1（scratch capability boundary）

> 8.8k 监督下从零训练 117M 条件序列生成器，无法同时学会 task understanding、operator mapping 与 sequence generation：OOD 任务上 100/100 塌缩到同一吸引子 code（Define Projection），88/100 空图。EOS/终止行为倒是健康（48/49）——但终止的常常是错误的链。

### M3-P1（general LLM + SFT）

> 9B 预训练语言先验可迁移出真实算子选择能力：43/100 首算子正确、35/100 行 set recall ≥ 0.5、69 个正常行 precision 0.399。但 31/100 行陷入 ≥20 步复读（intersection ×490），precision 被 harmful extra（0.885）拖垮。**planning competence 已出现，sequence control competence 不足。**

### M3-P2（sequence-control 干预，两层否定一层肯定）

> ① decoding 层否定：token 级重复控制（rep_penalty / no-repeat-ngram）与共享前缀结构化词表（所有 L3 code 共享 `L3_` 前缀）结构性不兼容——runaway 清零的代价是 69-89% 空图。
> ② 训练层部分肯定：仅将终端 EOS 的 loss 权重 ×2（λ=1 时与标准 loss 数学等价已验证），F1 +24%（0.1605→0.1991）、runaway -42%（31→18）、**recall 完整保持**（0.265→0.262）——模型学到的是"更好地停"而非"尽早停"（停线未触发）。
> ③ 残余瓶颈定位：审计显示 25.2% 训练行含连续重复 code（最长 60 连）——重复是数据合法先验，λ=2 的 EOS 信号只能对抗一部分。距后处理上限（0.2838）的剩余差距主要来自此数据先验 + 算子选择精度。

## 3. M3 线收束声明

**M3 在 P2-T1 收束**（owner 裁定 2026-09-14）。不做：T2、T1+T2、λ 扫描、更多 decoding search、M3-P3。理由：T1 已回答预注册问题；继续优化将把 M3 从"研究路线"变成"调参对象"；25.2% 重复先验属于数据分布问题，归 M2 处理。

## 4. M2 的研究问题（由上述证据直接生成）

M3 的 operator selection 上限：recall ~0.26、首算子 43%、35 行 set recall ≥ 0.5 但 precision 受限。问题分解：

```text
Q-M2a  GIS domain knowledge 不足是否限制了算子选择？
Q-M2b  长尾 L3 coverage（15/50 可落地 code 低样本）是否是 recall 上限的主因？
Q-M2c  GIS 术语/概念的语言先验（DAPT 可提供）对 task→operator mapping 有无增量？
```

M2 实验设计见 `M2_EXPERIMENT_DESIGN_v1.md`。预期 M2 > M3 > M1 为**假设而非结论**——M2 完全可能"DAPT 提升 GIS 知识但损害 workflow generation"，该结果同样有价值。
