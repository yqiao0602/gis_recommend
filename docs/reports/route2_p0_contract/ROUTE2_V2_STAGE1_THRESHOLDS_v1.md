# Stage-1 Capability Gate 阈值注册（THRESHOLDS v1，FROZEN）

注册：2026-09-29 凌晨，owner 裁定（R2 Gate Threshold Review 收口）。
性质：**预注册**——在 Stage-1 训练启动前冻结；未使用任何 Stage-1 结果倒推。
依据输入：`ROUTE2_V2_R2_REVIEW_INPUTS_v1.md`（双侧 Base 全 0 + 平凡基线实测）。

## 1. Stage-1 正式通过条件（全部同时满足）

```text
W1         ≥ 0.20
W2 overall ≥ 0.85  AND  W2 No-class ≥ 0.70
W3         ≥ 0.60
W4         ≥ 0.20
```

任一项不满足 → **Stage-1 FAIL**，不进入 Teacher Plan / B2；按 MASTER_LEDGER R3
四分叉归因（模型 / 数据噪声 / 合同缺陷 / 转换损失），⑦ 条款"FAIL 同协议续训"适用。

## 2. 逐项理由（注册时的书面依据）

| 项 | 值 | 依据 |
|---|---|---|
| W1 ≥ 0.20 | Base=0、无平凡锚点；0.20 = 结构化 I/O/slot 预测的最低非偶然能力线（预先承诺），留可达空间（n=1,690/1,805） |
| W2 overall ≥ 0.85 | 恒答 Yes = 0.779/0.790，0.85 才真正越过多数类基线 |
| W2 No-class ≥ 0.70 | 结构性堵死"恒答 Yes"；W2 本质 = 合法/非法连接判别 |
| W3 ≥ 0.60 | 众数序列平凡基线 0.497/0.504；0.60 拉开 ≥10pp，足以支持"任务→规划"能力形成（防把 ~0.50 模式记忆误判为规划） |
| W4 ≥ 0.20 | Base=0、平凡 ≡0、parse 双侧 100%（格式可学已证）；0.20 = 结构恢复的最低能力线 |

## 3. W2 No-class 的官方计算口径（不触碰冻结 evaluator）

从 `gate_items_{label}_{split}.jsonl` 事后计算（纯函数，与 EV 版本无关）：
取 `probe_type` 以 `W2:` 开头、gold（`target`/`expected`）为 **No** 的条目，
No-class accuracy = 其中 `correct=true` 的比例。dev n=173 / test n=138。

## 4. 附随裁定（一并冻结）

- **Δ(Base) 降级为诊断记录**："Base-relative margin is recorded diagnostically but is
  non-discriminative on the current baselines because Base zero-shot scores are 0."
- **W3 rewrite 不设独立硬门**：仅鲁棒性诊断（gap 大 → 查表面模板依赖）。
- **checkpoint 选择**：gate-dev 上，仅限四项全过 floor 的候选中按冻结加权分选择
  （W1 .20 / W2 .25 / W3 .40 / W4 .15）。
- **gate-test**：仅最终 PASS/FAIL 判定，不参与选点。
- 评分器 = `gate-eval-v1.3.1`（c2e7d725…）；探针 SHA dev `c3d95f67…` / test `866c3762…`；
  推理配置 SHA `6355bab4…`——评测链三 SHA 与 Base 基线完全一致。

## 5. 放行

本注册完成即满足 Stage-1 开训全部前置条件；owner 已放行（2026-09-29）。
执行序列：100 行 overfit smoke（工程验证）→ 通过 → 1 epoch 全量（⑦ 冻结协议）。
