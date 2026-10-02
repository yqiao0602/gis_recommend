# R3-C/R3-D Contract & Conversion 审计报告（v1，2026-10-02，CPU-only，未训练）

> 依据 owner 裁定（`f8b0cfd`）：沿 Task → GEE 原始 workflow → chain extraction →
> chain_to_plan → Plan schema → training target 全链反查"任务复杂度 → 长度/结构"信息的丢失点。
> 数据源：SRC 原始件（b1_gee_stage_train.jsonl，101,513 train 行，从 mdzhang tar 解包）、
> Tier 池（结构化 plan）、冻结 v2_2。脚本与中间结果见 progress.md 登记。

## F1. 上游 run-cap：转换之前，80% 的 workflow 已被压缩（R3-D 主发现）

SRC 行自带审计字段（`original_semantic_length` / `final_semantic_length` / `run_cap_applied`）：

| 指标 | 值 |
|---|---|
| train 行数 | 101,513 |
| `run_cap_applied` 标记 | 14,626（14.4%）——**标记严重低估** |
| **实际 final < original 的行** | **80,509（79.3%）**，平均砍 **12.1 步**，最多砍 3,783 步 |
| original_semantic_length p50/p90/p99/max | 11 / 46 / 177 / 3,793 |
| final_semantic_length p50/p90/p99/max | **7 / 26 / 87 / 1,869** |

**语义链在进入 plan 转换之前就被系统性压缩**：p50 11→7，p99 177→87。
长 workflow（复杂任务）被削最狠——上游就把"复杂度→长度"的分布截短了。

## F2. 逐级长度损耗（17,340 条可回连核心行）

| 阶段 | 步数 mean | 损耗 |
|---|---|---|
| original_semantic | 13.0 | — |
| final_semantic（cap/压缩后） | 9.2 | −29% |
| plan_steps（chain_to_plan 渲染） | 7.0 | −24%（相对 original **−46%**） |

**chain_to_plan 本身是忠实的**：plan_steps ↔ final_semantic 的 Spearman = **0.857**——
它忠实映射"已被压缩的语义链"。**信息丢失发生在它的上游（R3-D 确认），而非转换器内部。**

## F3. 任务文本本身是弱长度信号（R3-C 主发现）

| 相关系数（Spearman） | 值 |
|---|---|
| task 词数 ↔ original_semantic | **0.199** |
| task 词数 ↔ final_semantic | 0.162 |
| task 词数 ↔ plan_steps | **0.151** |
| （对照）original ↔ plan | 0.857 |

任务长度四分位的目标长度条件均值：Q1（23-52 词）→ 5.45 步 … Q4（87-173 词）→ 9.53 步——
**梯度存在但极弱**（任务长度只能解释 ~2-4% 的长度方差）。

**含义**：instruction 是 workflow 的**散文摘要**而非规格说明——它在源头就没有强编码
"该任务需要多长的 workflow"。**这不是管道损坏，而是 Contract/任务表述层面的先天信息限制。**

## F4. 三臂"固定长度输出"（恒 ~140-160 词）得到解释

p(plan 长度 | task) ≈ p(plan 长度)（ρ=0.15）→ 模型学到的最优策略就是输出**边际典型长度**
（训练 Plan p50=148 词，预测恒 ~140 词，与金标 154↔1,160 词无关）。
**观测行为与数据属性精确吻合**——模型没有失灵，它忠实学习了我们给它的条件结构。

## F5. 对三个问题的直接回答

1. **训练 target 是否要求任务条件化的完整 workflow？**——否。target = 线性化语义步序列
   （typed I/O + 部分 constraints；依赖仅"依赖前一步"线性式），task 是唯一条件输入
   （core 行 context 为空），且 task 文本与 target 长度只有 ρ=0.15 的弱关联。
2. **长度是不是训练信号？**——不是显式信号；且长 Plan 的监督被**两次**削弱：
   上游 run-cap（F1，转换前）+ 构建期截断（1,766 行；R3-B-1 已证）。
3. **chain_to_plan 是否丢信息？**——**转换器本身忠实**（ρ=0.857，F2）；
   丢失点在其上游的语义链压缩/run-cap（R3-D 实锤），以及任务文本的先天弱编码（R3-C 实锤）。

## 6. 对下一步的含义（供 owner 裁定）

- **R3-D 的修复点在转换上游**（run-cap/语义压缩策略），不在 chain_to_plan；
  任何修复都意味着重跑数据管道（build-time 级变更，需要 owner 级批准与设计）。
- **R3-C 的问题重新表述**：当前任务文本（散文摘要）在信息上不足以支撑长度条件化——
  修 Contract 不只是改 Plan schema，而是要改"任务如何描述 workflow"（数据工程，更大）。
- **TRUNC-exclusion 的定位更新**：在 F1/F3 背景下，它是"次级因素实验"——即使跑了，
  也只是在不解决上游压缩与任务弱编码的前提下消除一批受损行；预期 W3 变化有限。
  是否仍要跑（作为排除项闭环），归 owner。
- **W2-Yes**：维持 token-阈值假说归档不变。

**本轮零训练、零服务器写入、冻结物未动。**
