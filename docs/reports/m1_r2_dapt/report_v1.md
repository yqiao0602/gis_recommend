# M1-R2 Phase 2-B/2-C：DAPT 正式训练 + migration 审计（完成记录）

日期：2026-09-15（训练 08:30–10:50，140.2 分钟；服务器中途整体失联约 40 分钟，训练经 setsid 脱离会话未受影响）
性质：R2 唯一主动变量（decoder 骨干领域预训练）的执行记录；SFT 协议/评测/冻结产物未触碰
脚本：`scripts/m1_r2_dapt.py`（train / migrate）；合同：`docs/plans/domain_corpus_v1_spec.md` §10

## Phase 2-B：DAPT 正式训练（1 epoch × 492.5M byte-tokens）

| 项 | 值 |
|---|---|
| 时长 | 140.2 分钟（A10，峰值 2.81 GB） |
| byte-tokens 实消费 | **493,426,310（coverage 100.18%**；chunk 边界 + special token 计入 ledger 的口径差，在断言带内） |
| 分池账目 | d3=396,168,882 / d4=97,240,848 / d1=16,580（三池全部消费） |
| 样本 | 881,583 chunks 全部 1 epoch（seed 20260914 洗牌） |
| loss 轨迹 | 5.56（均匀基线）→ 2.75（步 300）→ 1.18（步 2,900）→ **0.6257（步 27,550 终值）**，全程平滑无发散 |
| checkpoints | 每 2,000 步（dapt_step2000…27550 + dapt_latest） |
| DAPT checkpoint SHA256 | `83d56745…3059173`（dapt_latest.pth，step 27550） |

事故记录：训练中途服务器整机网络失联约 40 分钟（ping 100% 丢包）；训练因 setsid 脱离会话继续运行并正常完成（exit 0）。

## Phase 2-C：migration 审计 8/8 ALL PASS

```
PASS  carry_decoder_layers / carry_decoder_norm /
      carry_input_film_gamma / carry_input_film_beta     ← carry-set 逐张量 SHA 与 DAPT checkpoint 精确相等
PASS  sft_vocab_132                                      ← SFT 头恢复 132-token L3 词表
PASS  embedding_fresh_random / output_fresh_random       ← 132 词表 embedding/投影为重新随机初始化
PASS  dapt_embedding_discarded                           ← 临时 byte 词表 embedding 确证未迁移
```

**工程证明完成**：R2 的 SFT 初始化只继承 DAPT 的 decoder backbone（decoder_layers + decoder_norm + input FiLM γ/β），lexical embedding 一律不迁移——与冻结合同逐项一致。

**SFT init 产物**：`/home/qy/gee_llm_smoke/m1_r2/m1_r2_sft_init_carry.pth`（SHA256 `0bd32ca2…210fdf3`）

## 下一步：Phase 2-D SFT

消费 `m1_r2_sft_init_carry.pth`，其余一切 = M1-R1 协议完全不变（paper_v1 train 8,817、70:30 平台分层采样、20 epochs、同 loss/同 checkpoint 选择标准/同验证），评测走 INFERENCE_CONFIG_FREEZE_v1（task_type=Unknown、dev-20 → prediction lock → final-100 顺序，不先看 final 选 checkpoint）。

验收三层：① collapse 解除信号（空图率、首 token 多样性、Define Projection 首 token 率）；② 基本生成能力（val Top1、SetF1、P/R、49 行诊断）；③ OOD（dev-20、final-100 的 R1→R2 Δ）。
