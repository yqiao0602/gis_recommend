# GEE Semantic Planner v1 Pilot — 阶段收口与状态登记（2026-10-09）

状态：PHASE_CLOSED / ALL_FREEZES_INTACT / NOT_TRAINING
本文档为 gee_semantic_planner_v1_pilot_round3 目录的收口索引。后续阶段以既有冻结记录为基线，不回头重做。

## 1. 本阶段全部冻结物（唯一有效清单）

| 冻结物 | 文件 | 基线 SHA-256 |
|---|---|---|
| GATE_B_DEFINITION_v1 | `GATE_B_DEFINITION_v1_FREEZE.json` | `c4fd2792f4e249a66495aebb3f6d7f5d3e33aa4677b1d13dba40fa6795460960` |
| S3_PROBES_v1 | `S3_PROBES_V1_FREEZE.json` | `e446a91336e8da0301159bea1fad12b46dc86bd66c1e65206ee896c5a2c7c258` |

**版本管理注意（永久有效）**：S3 设计文档 `S3_PROBES_DESIGN_v0.md` 存在两个 hash：

- `e446a913…` = 冻结基线（v1 验收版正文，判据以此为准）；
- `3f8df374…` = 加入冻结声明头后的当前文件（探针内容/判据未变）。

后续复核一律以冻结记录指定的基线 hash 为准，并核对正文判据与基线一致。两个 hash 不得混用。

## 2. 本阶段已完成工作索引

| 阶段 | 产物 | 结论 |
|---|---|---|
| G0 全量统计 | `g0_audit_sample_20_v1.jsonl` 等 | G0 = implementation-derived coarse semantic trace |
| G1 全量审计 | `g1_audit_sample_10_v1.jsonl`、病理 35 条 | core/W3 结构性监督目标错位；W1/W2/W4 辅助可用 |
| G2 全量审计 | `g2_audit_sample_12_v1.jsonl` + conditioning audit | skeleton conditioning PASS；task-specific FAIL；表示瓶颈 |
| G2→G3 保真审计 | `audit_g2_g3_information_fidelity_v1.py` + fixture tests | fail-closed；G3 lineage 不完整 → fidelity 不可验证 |
| G3 provenance 考古 | 四层对账 + parser evidence | **mapping_loss 21/37 > extraction_loss 14/37 >> RLE 0**；瓶颈=映射层粗化 |
| Schema Pilot 三轮 | Round1 INVALID（自配对）/ Round2 INVALID / **Round3 VALID**（40 独立任务、0 自配对、0 泄漏、0 link 错误） |
| 六样本人工审计 | `g0_semantic_review_priority6_*.jsonl` | 三类损失分离（description/extraction/representation） |
| Step 1 duty gold | `duty_gold_v0/`（6/6 通过，41 阶段） | B 可构建；**首要效度威胁 = G0-Task 循环性**；C 仅在显式枚举时可行 |
| Step 2 设计审查 | `STEP2_DESIGN_REVIEW_v0.md` | 双门槛 A/B；S1 否决；gold 降级为开发样本 |
| GATE_B 冻结 | `GATE_B_DEFINITION_v1_FREEZE.json` | 三项执行限定（B1 分母/B3 两分记录/B4 领域常识区分） |
| S2 审查 | `S2_CANDIDATE_ASSESSMENT_v1.md` | GeoAnalystBench 有条件（投影开发）/ GISAgentBench 有条件（受阻，优先联系）/ AutoGEEval 移出 |
| S3 探针冻结 | `S3_PROBES_V1_FREEZE.json` | 8 探针 4 类；六项修订锁定；只验规程不验能力 |

## 3. 核心研究结论（本阶段的可继承判断）

1. **G0 Task 文本含规划语义，但其语义链监督在映射层过度粗化**——从现有 G0 semantic chain 训练完整 Workflow Gold 不可行；作为粗骨架监督已由 G2 证明可学习；
2. **G0-Task 循环性是 duty 监督的首要效度威胁**——高 task_determined 率可能反映"反写摘要"而非独立意图；
3. **评价方法论已冻结可用**：双门槛（A 标签可靠性 / B 独立规划信号）+ B1–B4 四判据 + uncertainty_appropriateness 诊断字段 + 多正确答案原则。

## 4. 下一阶段范围（未启动，待 owner 启动令）

独立评价设计，只回答三问：

1. 独立任务来源（排除代码反写）；
2. 参考答案构建（允许多条合理工作流）；
3. B1–B4 可执行评分规程（必要职责 / 变化响应 / G2 增量 / 泄漏检测）。

基线：以第 1 节两项冻结记录为起点，不重做 S2/S3。

## 5. 边界（继续有效）

模型运行/训练/推理/RL：未授权。G0/G1/G2/G3、Blueprint、locked test：未触碰。S4 人写任务与 30–50 条扩量：暂缓。Git 提交：本阶段产物尚未提交，提交时机与范围待 owner 指示。
