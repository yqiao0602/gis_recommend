# V2a-P0 报告：评测协议 v2 冻结 + 算子名规范化正式实验

日期：2026-09-17
状态：Protocol v2 冻结（`b6d3f52`）；P0 实验 dev+test 全量完成
前置：owner 决策（2026-09-17）：先修测量 → 回收确定性损失 → 再训练干预

## 1. Protocol v2（评测基础设施修正，非模型迭代）

- **打分与生成解耦**：`scripts/v2a_score.py` 是纯函数（全文预测+gold+catalog → 指标），离线可复算，指标争议不再烧 GPU
- **三层分离**：① 生成能力（conditional，标 optimistic）② 生成可靠性（E2E 主指标 + failure taxonomy）③ 输出合法性（invalid/DAG）
- **不换集不动 gold**：dev 120 / test 111；test 预测重跑为全文版（旧版 400 字符截断，72/111 行受损，已替换为 `v2a_test_full_predictions.jsonl`，解码协议冻结不变）
- **自校验**：raw 列与冻结报告精确一致（dev E2E 0.1874 / cond 0.3009 / link cond 0.4331；test cond 0.2395 / link cond 0.4150）

## 2. P0：确定性 Canonicalization（零训练成本）

规则冻结（R1→R4 按序，任一命中即停，**无语义猜测、无去重**）：
R1 精确匹配 → R2 provider 前缀（`native:gdal:`→`gdal:` 等）→ R3 分隔符剥离 → R4 唯一前缀补全（歧义不修）。

### 完整对照表

| 指标 | dev Base | dev +Canon | test Base | test +Canon |
|---|---:|---:|---:|---:|
| parse_ok | 0.633 | 0.633 | 0.577 | 0.577 |
| hit_cap | 0.350 | 0.350 | 0.414 | 0.414 |
| repetition_rate | 0.392 | 0.392 | 0.451 | 0.451 |
| invalid_operator_rate | 0.394 | **0.297** | 0.508 | **0.355** |
| **op E2E F1** | 0.187 | **0.221** | 0.131 | **0.170** |
| op E2E P / R | 0.360 / 0.127 | **0.424** / 0.149 | 0.293 / 0.085 | **0.380** / 0.110 |
| op E2E F1 Δ | — | **+0.033** | — | **+0.039** |
| op conditional F1 | 0.301 | **0.354** | 0.240 | **0.310** |
| link E2E F1 | 0.240 | 0.240 | 0.200 | 0.200 |
| DAG valid rate | 1.0 | 1.0 | 1.0 | 1.0 |

### 规则命中分布

| split | R1 精确 | R2 provider | R3 分隔符 | R4 前缀 | 未修复 |
|---|---:|---:|---:|---:|---:|
| dev | 143 | 11 | 2 | 10 | 67 |
| test | 119 | 5 | 8 | 24 | 81 |

## 3. 判读

1. **收益确凿且方向一致**：dev +0.033 / test +0.039 E2E F1，全部来自 precision（dev 0.360→0.424、test 0.293→0.380）——正是"名称损坏"病灶；recall 微升（部分修复名命中 gold）。
2. **诚实口径低于诊断口径**：确定性规则的 +0.05~0.06（conditional）低于旧 difflib+去重诊断的 +0.087——差额是语义猜测与去重的贡献，P0 按裁决**不采纳**。
3. **主瓶颈确认未变**：canonicalization 修不了 reliability 层——hit_cap 0.35/0.41、repetition 0.39/0.45 原封不动。E2E 主要损失仍是**截断失控**（dev 42 行 / test 46 行主因=truncated）。
4. **82→93 实例未修复**（dev 67 + test 81 中非截断部分）多为彻底损坏名（截断到无前缀可补），属 reliability 层问题，需靠 EOS-SFT 或 catalog 约束解码根治。

## 4. 下一步裁决点（P1 是否立项）

端到端 F1 在 P0 后为 dev 0.221 / test 0.170，仍被 truncation 主导（行主因 truncated 占 35%/41%）。按 owner 路线图：**满足"仍被 truncation 主导"条件 → V2a-P1（EOS-aware SFT）立项**。

P1 设计要点（待批准后展开）：
- 唯一变量 = EOS 强化方式（普通 SFT vs EOS-aware SFT），其余全部冻结（A 数据 / Qwen3.5-9B / QLoRA / 1 epoch / seed / prompt / 解码 / scorer）
- 强化位置 = **完整 JSON 后的 EOS**（不是"见重复就停"）
- 复用 M3-P1 `eos_lambda` 先例但重新审视 gold EOS 位置定义

## 5. 产物

- spec：`docs/plans/v2a_eval_protocol_v2.md`；打分器：`scripts/v2a_score.py`（`b6d3f52`）
- 预测：`v2a_a/v2a_dev_canon_predictions.jsonl`、`v2a_a/v2a_test_full_predictions.jsonl`（全文）
- 打分：`v2a_a/v2a_{dev,test}_score_v2.json`（含 canon 列与规则命中分布）
