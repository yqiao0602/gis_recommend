# Route-2 v2 Stage-1 能力定义冻结（2026-09-24，owner 裁定）

## 冻结文本

**GIS Workflow Reasoning**：

> 一种平台相对独立、操作级的 GIS 任务处理能力，使模型能够理解基本操作的
> 行为与输入输出约束（W1），识别操作之间的数据流组合关系（W2），并根据
> 任务目标组织出合理的连续 GIS 处理计划（W3），同时能够识别和修复工作流
> 中的结构错误（W4）。

## 能力结构与定位（owner 三项裁定）

| 能力 | 定位 | Stage 1 地位 | 协议约束 |
|---|---|---|---|
| W1 算子行为知识 | 基础 | 必须 | — |
| W2 数据流组合律 | 基础 | 必须 | — |
| W3 目标分解规划 | **核心（整合 W1/W2）** | 必须 | 能力门须防"背模板过 W3"（W1/W2 分项验收交叉印证） |
| W4 结构判别与修复 | 鲁棒性/辅助 | 必须但受限 | **token budget ≤ 25%，默认工作点 ~20%**（按 token 非样本数计） |
| W5 分支/多父组合 | DAG 能力 | **下放 Stage 2** | 不作为 Stage 1 能力承诺与验收要求 |

## 阶段能力边界（论文须明示）

> **Stage 1 = Sequential / Linear GIS Workflow Reasoning；
> Stage 2 = QGIS-specific DAG Grounding。**

Stage 1 不是"不会 DAG"，而是 DAG 分支不列入其正式能力承诺——GEE 微步
链语料对分支监督薄弱，强行合成会引入人为分布。

## 术语冻结

废弃说法："Stage 1 输出 Semantic Workflow"。
正式说法："**Stage 1 形成并显式暴露 Workflow Reasoning
representation / plan**"。表示形态（37 类 semantic token 等抽象）**不在
本次冻结范围**——只冻结能力，不冻结表示，为接口设计（步骤③）保留空间。

## 设计边界条件（继承）

- **A1 边界**：纯 causal-LM 链暴露已被证死；Stage 1 目标必须含与
  workflow structure 相关的学习压力（恢复/补全/判别/组织结构关系）。
  硬要求：新目标必须能明确说明"为什么会产生 W1-W4 而 A1 不会"。
- **B1/Oracle 边界**：不得引入降信息抽象层（37 类教训）。
- **非 API 记忆**：各能力验收须在 held-out 操作词汇与重组组合上进行。

## 执行顺序更新

```
① 架构            ✅（ROUTE2_V2_ARCHITECTURE_v1.md，426053e）
② 能力定义        ✅（本记录）
③ Stage-1 输出/接口 ← 下一步（训练目标 × 接口表示联合设计）
④ Stage-2 信息需求
⑤ B2 数据
⑥ 训练协议（含 W4 ≤25% 落地）
```

步骤③待 owner 开题。届时比较对象：原始 chain LM / chain completion /
dependency prediction / workflow reconstruction / multi-task /
Task→Workflow planning——判据 = 对"为何产生 W1-W4 而 A1 不会"的回答力。
