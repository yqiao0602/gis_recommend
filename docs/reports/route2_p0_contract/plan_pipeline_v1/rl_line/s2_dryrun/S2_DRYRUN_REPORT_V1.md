# S2 Dry-Run 报告 v1（provisional_vocab23，纯评分诊断，无参数更新）

> 日期：2026-10-13 ｜ 协议：`RL_LINE_PREREGISTRATION_V1_CANDIDATE.md` §4.4 S2 + owner 四轮裁定
> 状态：**全部结果标 `provisional_vocab23`**——23 类是当前可验证词表，非已证实的 30 类合同词表；
> r2 结果为暂定诊断，不作为合法性判定最终依据。
> 产物：`s2_dryrun/preds.json` / `config.json` / `run_log.txt` / `S2_DRYRUN_SCORED_V1.json`

## 1. 运行配置（完整披露）

- 模型：P0 fmt adapter（`82095811…`）挂 `Qwen3.5/Qwen3.5-9B-Base`（adapter_config 记录路径）
- 任务：24 = planner_v2_train 分层抽样（short_2_4 / mid_5_8 / long_9plus 各 8，池 9,916/13,356/10,066，seed 20261013）
- 解码：**do_sample=True, temperature=1.0, top_p=1.0, repetition_penalty=1.15（协议钉定）**, max_new_tokens=768，prompt = task + SEP（与 p0b2_arms.py 逐字节一致）
- 无梯度更新；训练数据 SHA 匹配冻结值 `443d5d31…`

## 2. 吞吐外推（Phase 2 成本门输入）

- **74.46 tok/s（全部候选合计）**，wall 297.2s，192 候选 22,128 tokens，峰值 8,204 MiB
- 与外部进程（7.9GB）共存无压力；外推：GRPO 每步 24 组 × 8 候选 ≈ 5 min 生成；100 步 ≈ **8h+ 纯生成**（再加训练计算）——租卡/独占决策的数据基础

## 3. 信号诊断（核心结论）

| 指标 | 值 | 读数 |
|---|---|---|
| 有效组（formal 非恒定） | **6/24 = 25%** | **< 8/24 → 触发"信号覆盖有限"条款**，不得解读为可扩量 |
| formal 均值 | 0.9809 | 分布高度顶饱和：18/24 组全 1.0 |
| r2 屏蔽敏感性 | 5/24 仍非恒定 | 有效差异**不**高度依赖 r2（两个 OOV 各只影响 1 组）——vocab23 充分性暂获支持 |
| parse_fail / 空序列 | 0 / 0 | 采样+rep-pen 下本样本无截断（对照组：全 dev greedy 84% parse） |
| 分量失败行 | r1c=3, r2=2, r4=2 | r1c=1.6%（seq-less stage 变体）；r2=OOV 两行 |
| 分量 mask 行 | r3=2, r4=3 | D1 局部 mask 与 D3 缺键逻辑在真实缺陷上正确触发 |

**实质读数**：6 个非恒定组的差异模式全部是"**一个候选带缺陷 vs 其余满分**"（formal 取值只有 {0, 0.83, 1}），没有分级质量信号。**仅凭结构奖励 v0 跑 GRPO，模型能学到的几乎只有"回避稀有格式/结构缺陷"（X5/格式类）——对主瓶颈 X4（任务条件化阶段选择）零信号。** 这正是 dry run 要的回答：r5（任务需求覆盖，Phase 3，依赖多解判别线交付）才是质量分级信号的来源。

## 4. OOV 完整记录（owner 要求逐 token）

| token | 次数 | 任务组 | 奖励差(Δr2) | 来源判定 |
|---|---|---|---|---|
| `TEMORAL_FILTER` | 1 | 1（k=10540 cand7） | +0.1667 | **新出现**：TEMPORAL_FILTER 采样拼写错误 |
| `VECTOR_CLIP` | 1 | 1（k=24025 cand0） | +0.1667 | **新出现**：采样发明类 |
| `CLASSIFICATION_LOAD` | 0 | — | — | S1 发现的已知 OOV 本轮未复现（1,560→192 样本量差异） |

OOV 率 2/192 行 = 1.0%。无权威名单，"训练未见"不解释为"合同禁止"——两例更可能是采样噪声而非系统能力缺陷，S2 扩样后复查。

## 5. 过程事件（奖励模块 bugfix 1 次）

S2 真实预测暴露 `AUX13` 级 bug：seq-less stage + rg 存在时 V3b KeyError（金标恒有 seq 故电池未暴露）。已修复（缺 seq 的候选覆盖检查→undeterminable，不 crash），新增 AUX13 回归案例；**修复后**重新评分本文件；电池 24/24、pytest 13/13；修复后模块完整 SHA：`2ade2e793c3f51f6e5ef3b78146879b6c87eb19967633f1dbf54ba1599669596`。

## 6. 结论与放行状态

1. **管线验证：通过**——奖励模块在真实采样缺陷上行为正确（gateway、D1 局部 mask、D3 缺键、OOV 捕获全部按合同触发），零 crash；
2. **信号验证：覆盖有限**——25% < 8/24 门槛；结构性缺陷驱动的 {0,1} 型差异，无质量分级信号；
3. **词表：vocab23 暂定可用**——r2 屏蔽敏感性低（5/6 组差异保留），OOV 率 1%；
4. **Phase 2 未放行**——按 owner 裁定，本报告（吞吐外推 + 信号诊断 + OOV 敏感性）提交后等 owner 裁定；暂定词表下的奖励差异**不得**当作模型能力证据。
