# DC-2A-R1 规格：EOS-only state-conditioned control（修订版，预注册）

日期：2026-09-24 冻结（跑前成文）
沿革：`9a23c13`（DC-2A 原版）冒烟门捕获**设计覆盖洞**——原触发器（仅 link-phase）只覆盖 A1 自由生成的 82%，而 18% 的 hit_cap 故障行**全部**未触发（与 parse-fail 10/10 重合）——原版判"设计 FAIL / 不执行全量"归档，未产生任何全量数据。本 spec 依据 **FA-D3 预先观测到的 runaway 签名**（高频算子 P 阶段连发）修正状态定义，非事后调参。
owner 裁定（2026-09-24）：方案 1 批准；2（P 计数阈值）、3（FAIL-by-design 归档）否决。

## 1. 干预（不变量重申）

```text
z'_{EOS} = z_{EOS} + β · 1[S]
S = link-phase ∨ P-unit repetition run ≥ 3
β = 3.5625（沿用已锁 dc2a_beta.json；C0 健康边际标定，与 state 无关，不重算）
```

- **link-phase**：生成文本含 ≥1 个完整 L: unit（同原版）。
- **P-unit repetition run ≥ 3**：按**完整解析成功的 P unit 序列**（`P:pid:operator`，operator 取二个冒号后的非空段）的 operator 序列，最大连续同 operator run ≥ 3。不对 raw token/子串判断（防 tokenizer 假触发）。
- 唯一干预 = EOS logit bias；无 trie、无 repetition penalty（检测重复≠惩罚重复：后者是 DC-2B）、无 beam/长度项、无训练。

## 2. CPU 覆盖审计（跑前门）

对 A1 自由解码锁定预测（test-111）重算新 state 覆盖率；预期覆盖原 18% 未触发的跑马主体。覆盖率与分解随报告归档；若仍 <95%，本 spec 不执行全量（再归因）。

## 3. 执行序与判据（沿用 9a23c13 全部条款）

β 锁复用 → 8 行冒烟（观察 boost 触发率应显著高于 0.135，hit_cap 行应有触发）→ test-111 全量 → 五判据 + 防作弊对照（hit_cap↓、repetition↓、precision Δ≥−0.01、recall CI 下界>−0.05、link CI 下界>−0.05；趋近 C0-free 停控纪律为附加观察）。
FAIL → 控制层路线整体重估（EOS-only 假设届时才有资格被证伪），不进入参数变体。

## 4. 产物

spec 本文件、`scripts/dc2a_eos_bias_gen.py`（R1 状态函数）、覆盖审计 JSON、冒烟与全量工件、`dc2a_r1_report.md`。
