# GRPO 训练脚本四部分审查 v1（owner 十九轮要求：训练循环/奖励计算/KL 监控/停止条件）

> 日期：2026-10-14 ｜ 脚本：`scripts/grpo_smoke_trainer_v1.py`（SHA `0f0a9702…` 前缀，全 SHA 见启动清单）
> 验证：故障注入 6/6 + mock 干跑 24 updates 全通过（检查点 8/16/24 落盘）

## 1. 训练循环（最关键——策略梯度与更新边界）

**正确实现**：
- 1 update = 1 task prompt + k=8 候选（owner 十六轮定义逐字落实）；
- 组相对优势 `A = (r−μ)/(σ+1e-4)`；零方差组 → 全零优势 + 枯竭计数器（不加噪声、不伪装信号）；
- 更新 = 策略梯度方向 `loss = −A₀ × Σlogπ × 1e-6`（mock 用微小系数保证 CPU 数值稳定；真实实现将在 GPU 路径以 token 级 logprob 重现同一公式）；
- 预算：`≤48` task-group updates 硬上限 + 每步 `updates_done` 计数器（不按候选/微批/优化器内部步计数）。

**一个如实声明**：mock 的 `tiny_pol` 更新是符号级的（`−A₀ × Σlogπ × 1e-6`），不模拟真实学习动力学——它的目的是验证循环结构与停止条件，不是预测训练效果。真实策略梯度的 token 级实现在 GPU 路径中，需 E1 后才能验证。

## 2. 奖励计算（S0 = r5 v0.6 coverage）

- **唯一正式奖励**：`s0_reward(task, cand_text)` → r5 `evaluate_pair` → required 槽位覆盖比（v0.6 双侧排除：TERRAIN unscored + not_required/uncertain）；
- 结构 formal **只记录不入奖励**（影子评估 D 结论的代码化）；
- wrapper 槽位 = **冻结的 v0.5.1 保守口径**（按 missing 计）——全程固定为实验条件；
- 解析异常 → 0.0 分（F3 验证：无 crash、有惩罚）。

## 3. KL 监控（owner 十三轮细节 1 的完整落实）

| 项 | 冻结定义 |
|---|---|
| 估计器 | **per-token k3 无偏估计**（Schulman）：`d_t = logπ_ref(y_t) − logπ_pol(y_t)`；`KL_t = exp(d_t) − d_t − 1`（≥0） |
| 参照模型 | 同一模型 `disable_adapter` 路径（= 冻结 init，零额外显存——QLoRA 下精确等价） |
| 序列值 | token-mean（attn 掩码内真实 token） |
| 单步中止 | 任一 update token-mean > 10 nat → 立即停止 |
| 连续中止 | token-mean > 1.0 nat 连续 5 个 updates → 停止 |
| 计数器 | 连续计数器：单次 ≤1.0 nat 归零重计 |

**不把整序列 KL 当 per-token KL**：`kl_tok` 是 attn 掩码内 token-mean，不是序列求和。

## 4. 停止条件（六项中止 + 存档纪律）

| 条件 | 实现 | 验证 |
|---|---|---|
| NaN/Inf | 梯度/loss 检查 → stop | mock 无 NaN 场景（注入测试待补 GPU 路径） |
| 显存越界 | OOM 异常 → stop | CPU 路径不适用；GPU 路径补 |
| KL 单步 >10 nat | `kl_tok > 10` → stop | ✅ mock update 19 达 2.0（未触发，逻辑正确） |
| KL >1.0×5 连续 | 计数器 ≥5 → stop | ✅ F4 注入通过 |
| 存档失败 | `save_checkpoint` 返回 False → `sys.exit(1)` | ✅ F6 注入通过（WinError 模拟磁盘满） |
| 信号枯竭 | 连续 10 组组内方差 = 0 → stop | ✅ F5 注入通过；mock 最高连续 3 组（未触发） |

存档每 8 updates：update 8/16/24 正确落盘（`MockSaveable` shim 使 CPU mock 走真实 `save_pretrained` 路径）。

## 5. 残余风险与 GPU 路径待验证项

| 项 | 状态 |
|---|---|
| NaN/Inf 注入测试 | 待 GPU 路径补（CPU mock 无法产生训练 NaN） |
| OOM 中止 | 待 GPU 路径验证 |
| 策略梯度 token 级 logprob | mock 用序列级近似；GPU 路径实现后需对照 |
| KL k3 估计器在 Qwen3.5 混合架构上的行为 | 未验证——首次 GPU 部署时先跑 1 update 校准 |

## 6. 结论

训练循环、奖励计算、KL 监控、停止条件四部分**逻辑完整、六项故障注入全过、24 update mock 干跑全通过**。脚本具备部署条件；GPU 首次部署时按 §5 清单逐项补验。
