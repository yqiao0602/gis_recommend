# Route-2 v2 ⑥ B2 数据构造裁定 v0（2026-09-24，owner 裁定）

## ⑥-0 工程顺序（一票否决制）

```
⑥-0 QGIS Operator Capability Profile
⑥-1 Audit-A: Grounding Discriminability   ← 一票否决：不过不进任何 B2 加工
⑥-2 chain → Plan 管线
⑥-3 Plan 信息保持审计（Retention Audit）
⑥-4 QGIS 1334 train 配 Plan
⑥-5 B2 数据包
```

三件工程产物（完成 + Audit-A 通过才进⑦）：
① Operator Capability Profile ② Grounding Discriminator Matrix / Audit-A
③ Teacher Plan 生成 + Leakage Audit 管线。

## Audit-A 重定义：Information Discriminability Test

不测"模型会不会选"，测"**给定 Task+Plan，接口里是否客观存在区分候选
算子所需的信息**"。母集 = 148 语义映射组 → 挑真有实现差异的组
（Clip/ZonalStats/Reprojection/…）→ 每组建 Grounding Discriminator
Matrix（family × candidate × discriminator，由 Profile 程序化生成）。

**Audit-A 反作弊原则**：从 gold graph 反推的 Plan 不得天然 PASS——
必须审查 Plan 信息是否来自 Task/平台无关 reasoning 而非目标算子
（= provenance/leakage audit）。

## ⑥-B QGIS Plan 主来源（最关键裁定）

**Teacher Plan = Frozen Stage-1 Model(QGIS Task)**，作 B2 主训练输入。
**禁**：gold graph → 反推 Plan → 训练（= 把答案编码进输入的循环泄漏）。

Gold 的允许用途：事后评估 / 诊断 / 上界比较。
Gold 的禁止用途：生成 / 修正 / 选择 / 重写 Teacher Plan。

## ⑥-C Gold-derived Plan：de-grounded 诊断线

只做 upper-bound / diagnostic，与主数据线**绝对不混**：
- de-grounding = 剥离 provider / algorithm id / QGIS 特有参数名 /
  实现细节，只留 intent / I-O / dependency / dataflow / constraints
- **Leakage Audit**：能否从 Gold-derived Plan 直接恢复原 operator ID？
  能 = 仍过于接近实现，不合格

双 plan 对比诊断：Teacher Plan 低 + Gold-derived 高 → Stage-1 Plan 质量
问题；两者都低 → 接口或 Stage-2 信息需求问题。

## ⑥-D B2 双监督 family（数据层显式标识）

| family | 形态 | grounding_unit |
|---|---|---|
| B2-G1 Operation Grounding | Plan step + Task context → QGIS operator（含候选组学习"为何选它"） | `operation` |
| B2-G2 Workflow Grounding | Task + Plan → QGIS Graph | `workflow` |

比例/loss/QLoRA/混合方式 → ⑦。**不混黑盒**：unit 标签使"学到什么"
可分离分析（避免重蹈"F1 涨了但不知道学了什么"）。

## ⑥-E 数据纪律（三 split 同一接口路径）

```
Train 1334 → 冻结 Stage-1 生成 Teacher Plan → B2 训练
Dev 120   → 同一冻结 Stage-1 生成 Plan → checkpoint selection
Test 111  → 同一冻结 Stage-1 生成 Plan → prediction lock → 仅终评用
```

## Stage-1 能力门的前置耦合（关键排序约束）

**禁止用未过能力门的 Stage-1 批量蒸馏 Plan。** 完整链条：

```
Stage-1 训练（⑦协议）→ W1-W4 Capability Gate PASS
→ 冻结 Stage-1 checkpoint → 生成 Teacher Plans → B2
```

即：Teacher Plan 生成夹在 Stage-1 训练/验收与 B2 之间；⑥的三件工程
产物可先行建造（不依赖训练），但 ⑥-4 配 Plan 动作必须等门过。
Teacher Plan 质量差不是缺陷而是实验设计的一部分（Stage-1 门的价值
就在于此）。

## 执行顺序

```
①-⑤ ✅ → ⑥三件工程产物 + Audit-A PASS（当前阶段）
→ ⑦训练协议（Stage-1 协议先行）→ Stage-1 训练+门 → Teacher Plans → B2
```
