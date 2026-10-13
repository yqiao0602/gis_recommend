# PCA 原链一致性审计 — 四标签判定标准 v1（2026-10-13 固化）

> 依据：owner 阶段 2 指令（"将四种原链审计标签的判定标准固化入账本"）。
> 适用：对每条任务的原始 gold 链（dev-120 `processes/links`）对照 `pca_b_gold_worksheet_v2.json`
> （SHA `cf8b8dfe2b05ef9c`）的可接受方案集合逐条裁定。
> 纪律：**金标是裁定参照，原链有问题就单独记录——不为保持一致性收紧题面或放宽标准**
> （owner 原则：金标链是审计参照，不是任务语义的最高权威）。

## 判定标准（链级主标签）

| 标签 | 判定条件 |
|------|----------|
| `CONSISTENT` | 原链整体属于金标 `acceptable_alternatives`；满足全部 `required_constraints` 与 `required_outcome`；不触发任何 `failure_conditions`；`underdetermined_aspects` 覆盖的维度不参与此判定 |
| `PARTIALLY_CONSISTENT` | 核心 outcome 正确，但存在可识别的遗漏、多余约束或与某条 required_constraint 的偏差，且该偏差不改变任务语义主干（例：缺一个条件性步骤但主干可达目标） |
| `INCONSISTENT` | 原链与题面冲突：违反任务语义、触发核心 failure_condition（如 W056274 用全域最近点、W000890 未按等级优先消解重叠），或产出与 required_outcome 结构不符 |
| `UNDERDETERMINED` | 现有证据（冻结题面 + 金标 + 原链）不足以可靠判定——典型情形：判定恰好落在某条 `underdetermined_aspects` 上（如 W033927 跨类别重叠优先、W068342 阈值级正确性） |

## 判定纪律

1. **判定单位 = 链级主标签 + 分维度注记**：`underdetermined_aspects` 中的维度单独列出
   （`DIM-UNDERDETERMINED`），不与主标签混合——主标签只对可判定维度负责。
2. **路线名不等于合规**：链中出现某算子（如 proximity、viewshed）不自动满足语义要求；
   按 required_capabilities 与 outcome 语义判定（W067268 的 BS 5228 硬约束适用）。
3. **未规定参数不是错误**：原链选择的分辨率/抽样规模/合并顺序等题面未规定项，不构成
   偏差信号（对应各条 `underdetermined_aspects` 与 NOTE 行）。
4. **发现原链有问题时**：照实记录（含证据句），不改题面、不改金标、不删原链；
   `INCONSISTENT` 的条目进入 owner 裁定清单（该任务的评测可用性由 owner 定）。
5. **逐条记录字段**：`wid` / `label` / `dimension_notes[]` / `evidence`（题面与金标依据）
   / `adjudication`（是否需 owner 裁）。账本 = `pca_b_chain_audit_v1.json`（阶段 2 执行时生成）。
6. **审计对象是语义一致性**（owner round-5）：验证任务语义与链的一致性，**不是**验证
   新金标与旧链的表面相似度；"原链采用了某算子"不能证明该算子是唯一正确路线——链中
   的遗漏、冗余或潜在错误照实记录，但不得因链存在某步骤就修改金标迁就它。
7. **无法裁定的情形保留待裁**（`adjudication: ESCALATE-OWNER`）：题面本身无法裁定的
   情形不强行归入四标签，列为待 owner 裁定项。

## 流程位置

阶段 1（金标 v2，本轮）→ **owner 复核 v2** → 阶段 2（按本标准逐条审计 19 条原链）→
阶段 3（A/C 组金标 + 配对）→ 阶段 4（评测账本冻结 → 才申请正式生成）。
