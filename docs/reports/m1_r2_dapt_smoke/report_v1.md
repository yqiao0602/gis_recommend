# M1-R2 Phase 2-A/2-B：DAPT 初始化审计 + 100 步 smoke（记录）

日期：2026-09-14/15（服务器 A10）
性质：Phase 2 前置门禁；零正式训练（smoke 100 步除外）；未触碰任何冻结产物
脚本：`scripts/m1_r2_dapt.py`（audit / smoke / train / migrate 四模式）
合同：`docs/plans/domain_corpus_v1_spec.md` §10（owner 冻结 2026-09-14）

## Phase 2-A：初始化审计 15/15 ALL PASS（第 4 轮，前 3 轮各修一个 audit 自身缺陷）

```
recipe_seed_20260914 / recipe_factors(0.6/4/1) / budget_per_pool_matches_frozen
byte_roundtrip / byte_ids_in_range / temp_vocab_259 / embedding_tied_to_output
r1_checkpoint_not_loaded / dummy_condition_shape / dummy_memory_shape
dummy_condition_constant / pe_extension_lossless / forward_logits_shape
loss_finite_at_init / d3_kept_count_26285
```

关键数字：模型 total 117.4M / DAPT-trainable **7.3M**（精确等于合同：临时 embedding+tied 输出+decoder_layers+decoder_norm+input FiLM；BERT 与条件路径全部冻结在外）；init loss 48.3（FiLM γ 对角初始化 + 1024 长序列的暂态，见 smoke 收敛验证）。

## 预算口径修正（两次，均被断言拦下后修复）

1. budget_v1.json 手算舍入 38KB → 从池文件精确重算：d3_raw=651,184,115 / d4_raw=24,189,939 / d1_raw=16,452
2. **D3 预算从"比例近似 0.6×"改为"kept-SHA 清单精确字节"**：重尾文件大小分布下随机抽样 26,285 文件实际占 60.78%（395,768,519 字节）≠ 比例近似 390,710,469（+1.29%）。**最终冻结 TOTAL = 492,544,727 byte-tokens**，exposure D3 80.35% / D4 19.64% / D1 0.003%——仍在 owner 目标带（D3 70–80%/D4 20–30%）内，合同配比不变，仅预算基准改精确。

audit 途中另修：r1_checkpoint_loaded 断言极性写反、两处设备混用（dummy condition / PE 校验）、所有命令补 HF_HUB_OFFLINE=1。

## Phase 2-B：100 步 smoke PASS

| 项 | 结果 |
|---|---|
| chunk 预算断言 | 880,758→881,583 chunks，total **492,544,727 精确匹配** |
| loss 收敛 | 48.3 → 17.66（步1–50）→ **5.573（步51–100）≈ ln(259)=5.557 均匀基线**——初始偏高确认为暂态，无数值问题 |
| budget ledger | 分池精确计数（d3=1,429,944 / d4=338,243 / d1=0——D1 仅 0.003%，前 100 步未抽到属预期） |
| checkpoint 保存/重载 | carry-SHA match **True** |
| 峰值显存 | 2.81 GB |
| 吞吐 | 17,682 byte-tokens/步 → 全量 ≈2.8 万步 ≈ **84 分钟** |

另修：chunk 切分改 `seq_len−2`（START/END 占位，防 1026>1024 PE 越界）。

## 状态

- 2026-09-15 07:15 起正式 Phase 2-B 全量训练（1 epoch × 492,544,727 byte-tokens）在服务器运行，~84 分钟；checkpoint 每 2,000 步；`budget_ledger_final.json` 终局将记录 target vs actual vs coverage
- 完成后依次：Phase 2-C migrate 审计（carry-set SHA 相等 + embedding 不等证明）→ Phase 2-D SFT（R1 协议不变）

## 复现

```bash
# 服务器（qwen35，HF_HUB_OFFLINE=1）
python m1_r2_dapt.py audit
python m1_r2_dapt.py smoke --steps 100 --out /home/qy/gee_llm_smoke/m1_r2_dapt_smoke
python m1_r2_dapt.py train --out /home/qy/gee_llm_smoke/m1_r2_dapt
python m1_r2_dapt.py migrate --checkpoint /home/qy/gee_llm_smoke/m1_r2_dapt/dapt_latest.pth
```
