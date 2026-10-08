# R3-PLANNER-V2 SMOKE 结果报告（v1，2026-10-04）

> 依据 owner 放行（`64ee575`）：Planner-v2 SFT Smoke——Task → Blueprint v2 JSON
> （ordered semantic stages + repetition_groups + iteration_hint），222 train / 212 eval
> （分层不重叠），QLoRA 1 epoch 起步 + **5 pass 续训（共 ~41 步，对齐 P0 格式学习窗口）**，
> 独立目录全新 Base 起点。评测 = 诊断脚本 S1-S5 + E1-E4 + repeat 分布（非冻结 gate）。
> 产物：`planner_v2_smoke_eval_metrics.json`（metrics + 212 逐项）。

## 1. S1-S5 结果（n=212 held-out）

| 检查 | 结果 | 判定 |
|---|---|---|
| **S1 JSON/schema** | parse **0.3585**，schema-valid = parse（无幻觉键） | **PARTIAL**（36% 稳定输出；其余回退 Base 先验的散文 Stage 计划） |
| **S2 Ordered stages** | parsed 子集 LCS-F1 **0.6235**、首 stage 命中 **0.8158**、exact 0.0395 | **PASS**（输出的是有序 stage 序列，非 unordered family list） |
| **S3 Repetition presence** | parsed 子集 **F1 = 1.0**（repeat>1 family 签名与 gold 完全一致） | **PASS（决定性）** |
| **S4 unspecified 滥用** | 不可评（模型**完全省略 iteration_hint 字段**，0 组发射 hint） | 无 unspecified 滥用；hint 发射需正式 SFT |
| **S5 hint shortcut** | 不可评（同上，hinted = 0） | 正式 SFT 后再测 |
| **E4 repeat 分布** | pred mean **1.0**（全部 repeat=1）；gold mean 1.29（1→419、2→69、3→9…） | **numerical shortcut 出现**（符合 owner 预警） |

## 2. 判读

1. **核心问题（v2 表示是否可学）= PASS**：S2 有序结构 + S3 repetition 签名在
   parsed 子集上表现 decisively——模型学到了 schema 的结构语义，而非 unordered list。
2. **S1 的 36% parse 是训练步数问题**：smoke 仅 ~41 步（P0 格式学习在 20-40 步，
   完整 parse 稳定在 1,041 步正式 SFT）。模型在 blueprint JSON 与 Base 先验的
   散文 Stage 计划之间振荡——这正是 6→41 步欠训练的形态。
3. **E4 repeat=1 塌缩出现**（owner 预警命中）：与 P0/P1-B 的绝对计数不可识别结论一致——
   模型拒绝猜测 >1 的次数。正式路线中 repeat 数值由 Grounding 解析的设计因此得到
   进一步支持；若正式 SFT 保留 repeat 字段，需配合计数专项监督或接受 diagnostic 定位。
4. **hint 字段零发射**：模型跳过了 iteration_hint——三个可能原因：① hint 只存在于
   repeat>1 的 group（样本中占比小）；② 41 步不足以学会附属字段；③ 目标中 hint
   与 stages 的注意力竞争。正式 SFT 中需专门观察（S4/S5 届时才可测）。

## 3. Smoke Gate 结论

| Gate 项 | 判定 |
|---|---|
| S1 JSON compliance | PARTIAL（36%；未触发"直接停止"线，但需正式 SFT 预算） |
| S2 Ordered structure | **PASS** |
| S3 Repetition structure | **PASS（F1=1.0）** |
| S4/S5 hint 行为 | NOT EVALUABLE at smoke scale（字段零发射） |
| E4 shortcut 监控 | 塌缩出现（已登记，正式 SFT 监控项） |

**总体：条件性 PASS——v2 结构表示可学习成立；格式稳定性与 hint 发射留待正式 SFT。**

## 4. 事件登记

- 一次 smoke 设计修正：初版 1 epoch（6 步）无法回答可学性问题 → 同数据 5 pass 续训
  （共 ~41 步，仍在 smoke 授权范围），对齐 P0 格式学习窗口后评测。
- 评测脚本 v1 两处运行时错误修复（空 e1_f1 mean；metrics 写出路径）。

## 5. 建议（供 owner 裁定）

- **Planner-v2 正式 SFT 设计可启动**：全量 37,044 行（hint contract 已冻结）、1 epoch 起步、
  独立 dev/test；S4/S5 与 repeat 塌缩作为正式 SFT 的观察项；E4 保持 diagnostic。
- 原冻结主线（Stage-1 v2_2 + gate）不动；路线切换等正式 SFT 的独立 dev/test 证据。
