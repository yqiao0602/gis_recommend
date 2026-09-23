# Route-2 v2 架构决策记录：两阶段能力形成训练（2026-09-23，owner 裁定）

## 决策

新 Route-2 主线定义为**两阶段能力形成架构**（未来扩展为三阶段）：

```
                    Base Model
                        │
                        ▼
              ┌──────────────────┐
              │   Stage 1: GEE   │
              │ Workflow Learning│
              └────────┬─────────┘
                       ▼
             GIS Workflow Reasoning
        （任务分解 / 算子依赖 / 数据流 / 多步规划 / 组合结构）
                       ▼
              Stage-1 Capability Test（能力是否形成？——独立验收门）
                       ▼
              ┌──────────────────┐
              │ Stage 2: QGIS    │
              │    Grounding     │
              └────────┬─────────┘
                       ▼
            QGIS Operator / Parameter → Workflow → Graph
```

- **Stage 3（未来，本轮不启动）**：RL / preference / constraint
  optimization——仅在能力①②分别验收通过后，才有明确的优化对象
  （正确性/完整性/效率）。
- B2 重新定性：不是"继续 QGIS SFT"，而是 **QGIS Grounding
  Post-training**——教"已形成的 workflow reasoning 在 QGIS 里如何实现"。

## 证据基础（四块合璧，2d94aa4）

1. **Oracle 判决（情况 B）**：gold 37 类语义链 → QGIS 图，三臂全部贴地
   （opF1 0.077-0.117，EM 全零）——37 类抽象不足以决定算子选择；
   任务文本（0.479）携带的算子线索反多于 gold 语义链（0.096）。
2. **B1 的教训（本决策的直接动因）**：B1 形式上两段（GEE 语义 SFT →
   QGIS SFT），实质上第二段直接训练 Task→QGIS——两段之间从未存在
   被验收过的能力接口。模型分别学过 Task→语义 与 Task→QGIS 两个方向，
   却不能零样本组合出语义→QGIS 第三方向。
3. **error audit**：ops_mixed 占 55-58%——失败在算子级 grounding 局部
   错位，非整链不会生成。

## 关键认识：Stage-1 能力 ≠ 37 类 Semantic Workflow

必须摆脱"workflow reasoning = 37 类压缩表示"的旧等式。Stage 1 的正确
形态是**让模型从原始 GEE workflow 中自己形成 reasoning**，而非先人工
把 GEE 压成 37 类再喂入。37 类表示已被 Oracle 证明信息不足，重新走回
该表示等于重蹈覆辙。

## 执行顺序（owner 定序）

```
① 确定两阶段架构（本记录）
② 明确 Stage 1 输出/能力接口（表示形态 + 能力验收门设计）
③ 确定 Stage 2 grounding 所需信息
④ 设计 B2 数据（形态由 ②③ 决定，不预设）
⑤ 确定训练协议
```

**当前推进点 = ②**：核心研究问题是"Stage 1 如何从现有 128,447 条原始
GEE workflow（gee_canonical_chain 已具备）训练出 workflow reasoning，
同时最大限度避免 37 类压缩造成的信息损失"。

## 三能力论文主线（暂定）

| 能力 | 内容 | 对应阶段 |
|---|---|---|
| ① GIS Workflow Reasoning | 知道任务应该怎么做 | Stage 1（GEE） |
| ② QGIS Grounding | 知道在 QGIS 里怎么实现 | Stage 2（B2） |
| ③ Workflow Optimization | 生成更可靠的工作流 | Stage 3（RL，未来） |

## 约束延续

- P0 契约三臂（C0/A1/B1）为已冻结历史对照，不再改动；其产物
  （checkpoint/账本/test 预测）为 v2 架构的 baseline 证据。
- benchmark/gold/scorer 继续冻结；Oracle 仅为诊断，不入主实验。
- 训练类动作（含 B2 数据生成之外的任何 GPU 训练）需 owner 逐项批准。
- RL（Stage 3）本轮不立项（与既有 RL 纪律一致）。
