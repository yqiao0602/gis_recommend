# R2 Gate Threshold Review — 评审输入一页表（v1，2026-09-29）

> **用途**：R2 Gate Threshold Review 专场的唯一输入表。所有数字来自冻结工件，
> 组装过程不产生任何新数值裁定。**W1-W4 下限数值由 owner 在本评审中裁定。**
> 裁定框架 = MASTER_LEDGER R2 共识（2026-09-28，冻结性裁定），本文仅汇总。

## 0. 数据来源与有效性（对账记录）

| 项 | 值 | 状态 |
|---|---|---|
| dev 报告 | `base_zero_shot_v1/gate_report_base_zero_shot_dev.json`（mdzhang，09-27） | 三 SHA 对账通过 |
| test 报告 | `base_zero_shot_v1/gate_report_base_zero_shot_test.json`（租卡机，09-29 03:44，elapsed 50,594s） | 三 SHA 对账通过 |
| probe SHA | dev `c3d95f67…` / test `866c3762…`（本地冻结文件实测一致） | ✅ |
| inference_config SHA | `6355bab4…`（双 split 报告逐字一致：greedy / NF4-double-bf16 / left padding / 96,560 / batch 1） | ✅ |
| evaluator | gate-eval-v1.3.1（代码 SHA `c2e7d725`） | ✅ |
| 运行质量 | dev：0 OOM/0 超时/0 批减半；test：0 OOM/0 超时/0 批减半 | ✅ |

## 1. Base zero-shot 锚点（evaluator v1.3.1 实测）

| 能力 | dev | test |
|---|---|---|
| W1 | 0.000 | 0.000 |
| W2 | 0.000 | 0.000 |
| W3 as-is F1（macro/micro） | 0.000 / 0.000 | 0.000 / 0.000 |
| W3 rewrite F1（macro/micro） | 0.000 / 0.000 | 0.000 / 0.000 |
| W3 rewrite gap | 0.000 | 0.000 |
| W4 | 0.000 | 0.000 |
| invalid | 2,795/3,236（86.4%） | 2,752/3,256（84.5%） |

**含义**：Base 双 split 全 0 ⇒ Δ 条件（Base+Δ）仅作诊断记录，无判别力；
Gate 全部判别力压在绝对下限上（R2 共识第 1 条）。注册文本须含冻结声明：
*"Base-relative margin is recorded diagnostically but is non-discriminative on the
current dev baseline because Base zero-shot scores are 0."*

## 2. 平凡策略基线（CPU 对冻结探针精确计算，2026-09-28，非估计）

| 能力 | 平凡策略 | dev | test | 对设门的硬约束 |
|---|---|---|---|---|
| W1 | 任意输出 | ≈0 | ≈0 | 下限须显式 >0（由合理可达性推理，owner 定） |
| W2 | **恒答 Yes** | **0.7791**（Yes 610 / No 173） | **0.7903**（Yes 520 / No 138） | 下限必须显著 >0.7903（test 口径）；否则"学会说 Yes"即过门 |
| W3 | 恒输出众数 family 序列 | **0.4973**（n=474；众数频次 42/474≈8.9%） | **0.5044**（n=512） | 下限必须显著 >0.5044（test 口径） |
| W4 | 抄写损坏 plan（不修复） | ≡0（构造上） | ≡0 | 下限 >0 即有意义 |

## 3. 各能力探针数与 No 类数（双条件门结构用）

| 能力 | dev | test |
|---|---|---|
| W1 | 1,690 | 1,805 |
| W2 总数 | 783 | 658 |
| W2 Yes / **No** | 610 / **173** | 520 / **138** |
| W3 as-is / rewrite | 238 / 236 | 256 / 256 |
| W4 | 289 | 281 |
| 合计 | 3,236 | 3,256 |

W2 No-class 准确率可从 `gate_items_base_zero_shot_*.jsonl` 事后计算（gold 字段在案，无需改 evaluator）。

## 4. owner 逐项裁定清单（数值留白，仅列结构）

已冻结的裁定框架（不得更改）：

- **Δ 条件**：仅诊断记录（第 1 节冻结声明原文入注册文档）。
- **Floor 三层框架**：L1 非平凡性（压过平凡基线）→ L2 有意义能力门槛（注册的真门，须同时满足"击穿平凡策略"+"现实可达性"）→ L3 参考性能（oracle/human，仅解读，不入 Gate，不得事后临时找）。
- **W2 双条件门**：`overall ≥ X AND No-class ≥ Y`（两个数值 owner 定）。
- **W3**：rewrite 仅诊断，不转正、不设阈值；gap 大 → 查表面模板依赖。
- **W1/W4**：平凡基线 ≈0，floor 由"合理可达性 + dev 二项噪声"推理，逐项裁定。
- **硬约束**：任何下限不得低于对应平凡基线（W2 0.79 / W3 0.50 口径见第 2 节）。

| 能力 | L1 非平凡下限（参考） | L2 注册下限（owner 填） | W2 No-class 条件（owner 填） |
|---|---|---|---|
| W1 | >0 | ___ | — |
| W2 | >0.7903 (test) | ___ | No-class ≥ ___ |
| W3 | >0.5044 (test) | ___ | — |
| W4 | >0 | ___ | — |

## 5. 裁定后的既定序列（NEXT_ACTION，原文摘录）

1. owner 逐项裁定 → 2. 写注册文档 `ROUTE2_V2_STAGE1_THRESHOLDS_v1.md`（含第 1 节冻结声明）→ commit → 3. **owner 显式放行令** → Stage-1 训练（⑦ 冻结协议：v2_2 数据 SHA `02b5b476…`、QLoRA r16α32 NF4、1e-4 cosine、batch 32、max_len 1024、1 epoch、Chain LM 0、Task 保护截断）。
