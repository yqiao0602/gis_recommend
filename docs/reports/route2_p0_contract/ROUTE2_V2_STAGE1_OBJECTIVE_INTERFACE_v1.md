# Route-2 v2 ③ 训练目标与 Stage-2 接口 v0 决策（2026-09-24，owner 裁定）

## 冻结原则（③-A 至 ③-E）

| # | 原则 | 内容 |
|---|---|---|
| ③-A | **核心训练目标** | **Task → Workflow Plan**（W3 载体） |
| ③-B | **辅助目标** | 从同一 plan 派生：Dependency / Completion / Reconstruction；W4 受控加入（**≤25% token，默认 ~20%**） |
| ③-C | **原始 chain LM** | **不作 Stage-1 核心目标**（A1 反例在案；新目标必须在学习压力上有实质区别） |
| ③-D | **Stage-2 接口** | 不是 Plan→QGIS，而是 **Task + Workflow Plan → QGIS Grounding**（Task 保留原则） |
| ③-E | **Plan 表示信息约束** | 操作级 + 有序 + 数据流 + I/O 类型 + 依赖 + 必要的任务/子目标对应；**不冻结 schema、不建 37 类 ontology、不嵌入 QGIS API** |

## 训练组织形态

**Planning-centered multi-task learning**（非 generic multi-task）：
W3 为主任务，W1/W2 作为生成 plan 的内在压力被组织进主任务
（无类型/依赖信息则 plan 无法成立），W4 作为受控辅助任务。
Multi-task 是训练组织方式，不是能力定义。

## A1 差异化的正式回答（论文必备）

- A1 压力 = "接下来文本应该是什么"（sequence continuation）
- 新 Stage 1 压力 = "这个任务应该怎样组织操作、操作为何能连接"
  （task-conditioned workflow construction + 显式结构约束）
- 差异不在数据量，在**学习目标的方向与约束**。

## Task 保留原则的依据

Oracle：B1 Task→QGIS ≈ 0.479 vs B1 Semantic→QGIS ≈ 0.096——任务文本
携带大量辅助算子选择的上下文。故 Plan 不取代 Task：
**Plan = 把 Task 中隐含的 workflow structure 显式化**，与 Task 语义
互补后共同进入 Stage 2。

## 能力门的 answer-echo 反制设计（继承并具体化）

- 训练：Task A → Workflow A；验收：**改写后的 Task A' → Workflow A**
- 进一步：Task A' + **未出现过的新操作组合** → Workflow
- 通过才算 planning，不通过即 description matching。

## 接口总览（③④衔接）

```
Stage 1:  Task → Workflow Plan →【能力门】
Stage 2:  Task + Workflow Plan → QGIS Grounding → Operator → DAG
```

与被否决路径的根本区别：不把 GIS reasoning 压缩进固定低信息语义标签
集合；输出的是可继续推理、可被 grounding 消费的结构化计划。

## 下一步（接口具体化，待 owner 开题）

1. Workflow Plan 必须保留哪些字段
2. 哪些字段可从 128,447 条 canonical chain **自动**得到
   （已知资产：Neo4j GEE_Operator 1425 节点含 hasInput/hasOutput，
   类型信息可查）
3. 哪些字段需要新增标注/生成
4. 反瓶颈保障：如何确保不退化为 37 类 semantic bottleneck
