# PCA 原链一致性审计 — 四标签判定标准 v1（2026-10-13 固化；round-7 收口）

> 依据：owner 阶段 2 指令（"将四种原链审计标签的判定标准固化入账本"）+ owner round-7
> 协议收口（5 项）。
> 适用：对每条任务的原始 gold 链（dev-120 `processes/links`）对照金标工作表
> `pca_b_gold_worksheet_v2.json`（**SHA `0dc643980e8d4b8e`**；其 19 行任务内容与
> round-6 版 `bad86ac7bc2a333d` 逐字一致，仅 `_meta` 命名按 owner 建议修正）逐条裁定。
> 纪律：**金标是裁定参照，原链有问题就单独记录——不为保持一致性收紧题面或放宽标准**
> （owner 原则：金标链是审计参照，不是任务语义的最高权威）。

## 判定标准（链级主标签）

| 标签 | 判定条件 |
|------|----------|
| `CONSISTENT` | **原链符合冻结题面的语义要求及全部可判定硬约束；金标 `acceptable_alternatives` 用于说明已认可的路线及其条件，不构成对所有合法实现路线的封闭枚举。凡明确标注为条件性路线的，仍须满足相应条件**（owner round-7 措辞）。不触发任何 `failure_conditions`；`underdetermined_aspects` 覆盖的维度不参与此判定 |
| `PARTIALLY_CONSISTENT` | 核心 outcome 正确，但存在可识别的遗漏、多余约束或与某条 required_constraint 的偏差，且该偏差不改变任务语义主干（例：缺一个条件性步骤但主干可达目标） |
| `INCONSISTENT` | 原链与题面冲突：违反任务语义、触发核心 failure_condition（如 W056274 用全域最近点、W000890 未按等级优先消解重叠），或产出与 required_outcome 结构不符 |
| `UNDERDETERMINED` | **审计结论标签**：现有证据（冻结题面 + 金标 + 原链）不足以可靠判定相关维度或整条链——典型：判定恰好落在某 `underdetermined_aspects` 上。它与 `adjudication=ESCALATE-OWNER`（处置状态）各司其职，见下节 |

## 判定纪律

1. **判定单位 = 链级主标签 + 分维度注记**：`underdetermined_aspects` 中的维度单独列出
   （`DIM-UNDERDETERMINED`），不与主标签混合——主标签只对可判定维度负责。
2. **路线名不等于合规**：链中出现某算子（如 proximity、viewshed）不自动满足语义要求；
   按 required_capabilities 与 outcome 语义判定（W067268 的 BS 5228 硬约束适用）。
3. **未规定参数不是错误**：原链选择的分辨率/抽样规模/合并顺序等题面未规定项，不构成
   偏差信号（对应各条 `underdetermined_aspects` 与 NOTE 行）。
4. **发现原链有问题时**：照实记录（含证据句），不改题面、不改金标、不删原链；
   `INCONSISTENT` 的条目进入 owner 裁定清单（该任务的评测可用性由 owner 定）。
5. **逐条记录字段（以正式 JSON schema 为准，owner round-7 统一）**：
   `wid` / `label` / `dimension_evidence[]`（逐维度 `{dimension, support, issue}`，
   **support 与 issue 均可为 null**）/ `missing_required_operations[]`（明确缺失的必要
   操作或关系）/ `suspect_but_not_failures[]`（可疑但不能据此判错的实现选择）/
   `adjudication`（NONE | ESCALATE-OWNER）/ `escalation_reason`（**adjudication=NONE
   时必须为 null**）/ `adjudication_resolved`（裁定后回填）。账本 =
   `pca_b_chain_audit_v1.json`（阶段 2 执行时生成）。
6. **审计对象是语义一致性**（owner round-5）：验证任务语义与链的一致性，**不是**验证
   新金标与旧链的表面相似度；"原链采用了某算子"不能证明该算子是唯一正确路线——链中
   的遗漏、冗余或潜在错误照实记录，但不得因链存在某步骤就修改金标迁就它。
7. **UNDERDETERMINED 与 ESCALATE-OWNER 职责分工（owner round-7 统一）**：
   - `label = UNDERDETERMINED` 是**审计结论**：当前证据不足以判定相关维度或整条链；
   - `adjudication = ESCALATE-OWNER` 是**处置状态**：该不确定性需要 owner 裁定；
     `adjudication = NONE` 表示无需提交裁定；
   - **单个非核心维度不可判定**而其他维度仍可判定 → 只在 `dimension_evidence` 中单独
     标注该维度，**不**自动将整条链升级为 UNDERDETERMINED；
   - **该维度决定整条链的主标签** → 采用 `UNDERDETERMINED + ESCALATE-OWNER`。

## 主标签边界（owner round-7：结构可判定性 vs 不可观察结果）

**主标签仅评价现有证据能够可靠判定的维度。** 对 `underdetermined_aspects` 明确排除的
不可观察结果，**不得仅因缺少执行证据判错**；但如果该未知维度直接影响整条链是否可判定，
则使用 `UNDERDETERMINED` 并按协议决定是否升级。

执行示例（W067268）：结构层记录地形、距离衰减、地面类型、障碍物等因素是否出现；
数值层面的 BS 5228 合规性另记为"不可由当前结构证据确认"。**既不因流程出现相关算子就
宣称数值合规，也不因没有执行结果就断言不合规。**

## ESCALATE-OWNER 完整协议（owner round-6 preflight 固化）

- **触发条件**：冻结题面 + 金标 v2 + 原链三者联合审读后仍无法给出可靠主标签的情形
  ——典型：判定恰好落在某 `underdetermined_aspects` 上、链与题面各自可通但联合语义
  存在两种以上不可仲裁的读法。
- **记录格式**：`adjudication: "ESCALATE-OWNER"` + `escalation_reason`（一句话说明
  哪个维度、为何题面+金标不足以裁定）。
- **裁定后处理**：owner 裁定结果回填 `adjudication_resolved`（含理由）。**裁定不等于
  自动修改金标或题面**——若裁定揭示冻结题面本身不足以支持某判断，保留该事实并按
  v1.1 版本化流程处理（出题面/金标新版），不得为让旧链获得明确标签而反向补充题面。

## Stage-2 三条执行规则（owner round-6）

1. **不同路线 ≠ 错误**：链只要能满足题面要求，不得仅因算子或顺序与旧链不同而判错。
2. **不确定 ≠ 不合格**：题面未规定的参数、阈值、处理顺序或唯一实现方式，不得在审计
   过程中临时补成硬性要求（对应金标 `underdetermined_aspects` 全部声明）。
3. **Owner 裁定 ≠ 自动修改金标**：见上节裁定后处理。

## 每链记录字段（Stage-2 产出 schema，owner round-6 指定）

```json
{
  "wid": "...",
  "label": "CONSISTENT | PARTIALLY_CONSISTENT | INCONSISTENT | UNDERDETERMINED",
  "dimension_evidence": [{"dimension": "...", "support": "...|null", "issue": "...|null"}],
  "missing_required_operations": ["明确缺失的必要操作或关系"],
  "suspect_but_not_failures": ["可疑但不能据此定错的实现选择"],
  "adjudication": "NONE | ESCALATE-OWNER",
  "escalation_reason": null | "...",
  "adjudication_resolved": null | "owner ruling + reason"
}
```

**纪律 6/7**（前文）继续有效：审计对象是任务语义与链的语义一致性；"原链用了某算子"
不能证明该算子唯一正确。

## 流程位置

阶段 1（金标 v2，本轮）→ **owner 复核 v2** → 阶段 2（按本标准逐条审计 19 条原链）→
阶段 3（A/C 组金标 + 配对）→ 阶段 4（评测账本冻结 → 才申请正式生成）。
