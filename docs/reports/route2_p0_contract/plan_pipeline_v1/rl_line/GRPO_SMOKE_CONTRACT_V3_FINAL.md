# GRPO 冒烟契约 v3 FINAL（已签字批准——启动待 GPU 资源与外部进程安全检查）

> **签字记录**：owner 十八轮终审"契约签字批准"（2026-10-14）；启动授权仍等 GPU 资源
> （≥12GB 裕量）与外部进程安全检查通过。签字前核验：`GRPO_LAUNCH_READINESS_VERIFICATION_V1.md`
> （六项清单 5 静态 ✅ + 1 动态启动时点条件）。

> 日期：2026-10-14 ｜ 前版：`GRPO_SMOKE_CONTRACT_V2_FINAL_CANDIDATE.md`（全文继续有效，保留为历史）
> 本版变更 = owner 十七轮三个签字前条件的冻结件；**其余条款（§0-§7）不变**。
> 冻结规格：`eval_procurement/eval_set_frozen_spec_v1.json`（公式、Δ 定义、E0 基线、投机监控全量）。

## §8 三条件冻结附录（owner 十七轮）

### 条件 1：槽位覆盖率计算公式（冻结）

- **候选级**：`C_cand = covered_required / (covered_required + missing_required)`；
  - `required` = v0.6 口径必需槽位，**双侧排除**：TERRAIN（unscored_representation_boundary）、not_required、requirement_uncertain；
  - `covered` = covered + covered_coarse（备选族覆盖计入，粗粒度注记随行）；
- **任务级（主单位）**：`C_task = mean(C_cand over 8 candidates)`；
- **评估集级（ΔC 基准）**：`C_eval = mean(C_task over tasks with scorable slots)`；
- **无可评分槽位任务（7 个，冻结 ID）**：script_150328 / 158835 / 19546 / 235273（无可解析需求）+ 407954 / 411264 / 411270（全空候选）——排除出分子分母，单列报告；
- E0 与 E1 使用**同一冻结任务集 + 同一 v0.6 解析器 + 同一公式**（本附录 SHA 即身份）。

### 条件 2：Δ 定义与同时验收（冻结）

- `ΔC = C_eval(E1) − C_eval(E0)`；`ΔF = F_eval(E1) − F_eval(E0)`（F = 有序阶段 LCS-F1，候选 repeat 展开序列 vs **b1 semantic_chain_rle 真链**）；
- **验收 = 五条同时满足，任何单项增益不抵消单项退化**：
  1. ΔC ≥ +5pp；
  2. ΔF ≥ −3pp；
  3. 解析率下降 ≤5pp；
  4. invalid 率上升 ≤5pp；
  5. 无投机红线触发；
- 5pp/3pp = 工程阈值（非统计显著性）；E1 结果必须附**任务级变化分布 + 逐任务计数**。

### 条件 3：投机检查判定规则（冻结，揭盲前生效）

| 监控 | E0 基线 | 触发 |
|---|---|---|
| 空/不可解析率 | 14.06% | 升 >5pp → **直接判失败**（与解析安全线同） |
| 相邻重复族率 | 0.0% | 升 >5pp → 人工审查；>10pp → 直接判失败 |
| 无关未链接阶段率 | 45.21% | 升 >10pp → 人工审查 |
| 平均阶段数（过度生成） | 3.1 | 相对升 >25% → 人工审查 |

每项记录 E0/E1 变化与对应案例；标准揭盲前冻结，E1 后不得临时调整。

## E0 冻结基线（192 候选实测）

- **C_E0（任务级均值）= 0.4975**；
- **F_E0（任务级均值，vs 真链 LCS-F1）= 0.3577**；
- 金标参照 = b1 semantic_chain_rle（任务真链；**退化共同门槛参照**，非多解改进参照——改善主张仍按 §3.5 四前置）；
- 24/24 金标链齐备；投机基线见 §条件 3 表。

## 授权链（重申）

1. owner 对本 v3 FINAL（含 §8 附录）签字；
2. GPU 窗口 + ≥12GB 显存预检 + 启动清单 SHA 复核（§0 全套）；
3. 训练启动 → ≤48 task-group updates → E1 一次性重评 → 按冻结验收规则出结论。

**Phase 2/3 冻结；RAFT/DPO/GRPO 不启动——本 v3 为待签字终稿。**
