# V2a-P1 Spec：EOS-aware SFT（冻结）

日期：2026-09-17
状态：spec 冻结；**未动 GPU**（训练待 spec+审计+sanity 全部通过后另行启动）
前置：P0 报告（`72f7d5f`）确认 truncation 仍是主瓶颈（dev 35% / test 41% 行主因）
实验性质：**因果实验** —— 只测试"显式强化合法 EOS"能否拉回生成可靠性

## 1. Gold EOS 位置审计（已完成，2026-09-17，真实 tokenizer 编码，非字符串推断）

对象：Qwen3.5-9B tokenizer + `v2a_A_train.jsonl` 1334 行（前 400 行全检，CPU）

| 审计项 | 结果 |
|---|---|
| tokenizer eos | `<|im_end|>` = id **248046**；pad = `` = id 248044 |
| gold target 尾部结构 | **每行恒为** `…1"}]}` + `<|im_end|>`（单 token，位置=序列最后） |
| JSON 文本内部特殊 token | **0 个**（400/400 行）——EOS 位置无歧义，`}`/`,`/算子重复都不会被误当 EOS |
| 追加 EOS 后的 eos 计数 | 每行恰好 1 个（400/400）——不存在双重 EOS |
| **gold 合法重复** | **479/1334 行（36%）含连续重复算子，最大 run=16** |

**审计结论**：
1. EOS supervision 位置**唯一且无歧义**：target 序列最后一个 token（`<|im_end|>` 248046）。λ 强化该位置不会碰到 JSON 内部任何 token。
2. **36% 的 gold 行含合法连续重复**（最大 16 连）——再次确证 E1 绝不能含任何重复抑制，只做 EOS 位置加权。
3. eval 停止集 = {248046, 248044}（eos+pad），训练只监督 248046——一致，无需改。
4. **现状**：A 的训练已含 EOS 监督（`v2a_sft.py:65` 拼接 eos_token，CE 权重 1.0）。E1 的唯一变化 = 该 token 的 loss 权重 λ>1。

## 2. 实验设计

### 2.1 变体

| 变体 | 定义 | 训练 |
|---|---|---|
| **P1-C0** | 普通 SFT = **现有 A checkpoint**（`v2a_a/adapter_v1`，seed 20260916） | **不重训**，直接复用已有全文预测与 Protocol v2 打分 |
| **P1-E1** | EOS-aware SFT：target 最后的 `<|im_end|>` 位置 loss 权重 = λ | 重训一次（与 C0 同 seed 同超参，唯一差异 = λ） |

λ 取值：λ=20 起步。依据：target ~150 token 中 EOS 占 1 个，均匀 CE 下其梯度质量 ~1/150；要让它主导需要量级提升。若 sanity 显示 λ=20 对总 loss 影响仍弱，smoke 阶段可加测 λ=50（**λ 的选择在 smoke 阶段定，不进正式比较后仍改**）。

### 2.2 冻结面（与 C0 完全一致，逐项锁死）

数据 A 1334/120/111；Qwen3.5-9B；QLoRA NF4 r=16（q/k/v/o）；lr 1e-4；1 epoch；seed 20260916；max_len 2560；microbatch 1 × accum 32（有效批 32）；length bucketing；prompt 模板；JSON schema；解码（greedy/512/显式 EOS stop，**无 ngram、无 repetition penalty**）；canonicalization 规则（R1-R4 冻结）；Protocol v2 scorer（`v2a_score.py`，`b6d3f52`）。

### 2.3 E1 的 loss 定义（token 级）

```
L = Σ_t w_t · CE(logits_t, label_t)
w_t = 1            对所有非 EOS target token
w_t = λ            当且仅当 label_t == 248046 且 t 是该行 target 的最后一个 token
```

实现约束：
- λ 只作用于**最后一个** `<|im_end|>`（审计已证每行恰 1 个，防御式按位置判定）
- prompt mask（-100）不变；per-sample weight（A 全 1.0）不变
- **明确禁止**：重复检测惩罚、长度先验、ngram 约束、对 JSON 内 token 的任何额外权重

## 3. Loss sanity（必须 PASS 才准训练，三层）

S1（纯数学，CPU 可验）：λ=1 ⇒ 逐 token 权重全 1 ⇒ loss 恒等现有 CE 路径。
S2（真实前向，smoke 时 GPU 验）：构造含已知 EOS 位置的微批，λ=2 时 loss 增量 == 单 EOS token CE × (λ−1)（解析精确值比对，同 B 实验的 1.598273=1.598273 级别的对齐）。
S3（位置断言）：λ>1 时，梯度非零位置 ⊆ {EOS 位置} ∪ {原 CE 位置}——即没有 JSON 内 token 被误加权（审计已证不可能，但代码必须显式断言）。

## 4. 成功标准（观察性，不预设 F1 提升量）

| 方向 | 指标 |
|---|---|
| 期望 ↑ | parse_ok、E2E op F1、E2E link F1 |
| 期望 ↓ | hit_cap（当前 dev 0.35 / test 0.41）、repetition_rate |
| 不得恶化 | invalid_operator_rate、conditional F1（容许小幅波动，明显下降记失败） |

**判读纪律**：hit_cap 明显下降 + E2E 上升 + conditional 基本稳定 ⇒ P1 解决了 reliability bottleneck。hit_cap 降但 parse error 升 ⇒ **如实记为失败**（与 ngram8 同等对待）。E1 与 C0 的比较一律在 Protocol v2 双口径 + canon 双列下进行（dev+test 全量）。

## 5. 执行顺序（冻结）

```
spec 冻结（本文档）
  ↓ 已完成：Gold EOS 位置审计（§1）
  ↓ E1 代码：v2a_sft.py 加 --eos-lambda（默认 1.0 = 恒等现有路径）
  ↓ S1 数学验证 + S2/S3 smoke（--smoke 扩展，GPU，待启动批准）
  ↓ E1 正式训练（GPU，待启动批准）
  ↓ Protocol v2 打分（dev+test，双口径+canon）
  ↓ P1 报告
```

## 6. 结案条款（沿用 owner 2026-09-17 决策）

epoch ablation / catalog constrained decoding / RL-DPO：全部后置。P1 期间不并行任何其他 V2a 实验。
