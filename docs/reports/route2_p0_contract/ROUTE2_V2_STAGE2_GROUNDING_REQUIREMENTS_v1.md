# Route-2 v2 ⑤ Stage-2 Grounding 信息需求 v0（2026-09-24，owner 裁定）

## 核心原则

Stage 2 的问题不是"Plan 还要更复杂"，而是**判断 Task + Plan 到 QGIS 之间
还缺什么信息**，使算子选择、参数绑定、图结构落地成为可学习问题。

Stage 2 目标形式：

```
Task + Workflow Plan + QGIS Operator Knowledge → QGIS Graph
```

QGIS 知识经 Stage-2 后训练进入模型参数，**不作为额外输入文本**。
分工：Task+Plan 描述"做什么/怎么组织"；QGIS 训练负责"哪些实现能完成它"。

## Grounding 信息四分类（G1-G4）

| 类 | 内容 | 备注 |
|---|---|---|
| G1 数据对象与 I/O 约束 | 输入/输出类型、槽位、多输入关系、输出数量 | KG QGIS_Operator 资产可复用；Raster+Polygon→Raster 与 Vector+Polygon→Vector 高层同名但 grounding 不同 |
| G2 **实现判别约束** | raster/vector？mask 几何类型？保留相交还是属性筛选？栅格网格保持？CRS/extent 行为？输出图层还是统计？ | **Oracle 暴露的真正缺口**；Intent+TypeContext+TaskConstraints 共同决定实现；此层比语义类别更重要 |
| G3 参数语义 | operator→required parameters→bindings（如 buffer 的 distance/segments/endcap/join/dissolve） | Stage-2 训练数据必须具备参数 schema ↔ 任务约束对应，否则只会选算子不会生成完整 process |
| G4 Graph realization | 多输入/多输出、fan-out/in、端口对应、数据流连接 | Stage 1 线性 / Stage 2 DAG 分工的落实处 |

## 信息需求矩阵（④⑤衔接）

| 信息 | Stage-1 Plan | Stage-2 QGIS 知识 |
|---|---|---|
| 操作意图/顺序/依赖/I-O 类型 | ✓ | 使用 |
| 多输入/多输出 | 尽量保留 | **必须** |
| 参数语义 | 部分/必要约束 | **必须** |
| QGIS operator identity | ✗ | **必须学习** |
| operator-specific constraints | ✗ | **必须学习** |
| port mapping | ✗ | **必须学习** |
| DAG realization | ✗ | **必须学习** |

## 三个正式 Benchmark Audit（⑤的核心产物）

- **Audit-A Grounding Discriminability**：Task+Plan → 候选算子组内选对
  实现（候选组复用 oracle 148 算子映射分组）。**接口可用性门槛——
  不过不训 B2**。
- **Audit-B Information Sufficiency**：逐字段 ablation（Task / +Plan /
  −I/O / −Constraints / −dependency…）找 **minimal sufficient interface**，
  防"信息越多越好"式字段膨胀。
- **Audit-C Workflow Realization Sufficiency**：算子/连接/端口/
  fan-in-out/图完整性分项检验 Plan 结构信息是否足以支撑 DAG realization。

三审计覆盖三类失败：grounding 信息不足（A）/ 接口设计缺陷（B）/
结构落地缺陷（C）——B2 不再是"训练看分数"的黑盒。

## 三条冻结边界

1. **Stage 2 禁读 GEE API chain**（ee.Image.* 等不入条件输入）——
   保持 "GIS reasoning → QGIS grounding"，防 API 翻译退化。
2. **QGIS operator knowledge 不塞进 Plan**——不把 native:clip 的参数
   schema/provider/port 提前灌入 Stage-1 Plan；分界保持
   Stage 1 "What should happen?" / Stage 2 "How does QGIS implement it?"
3. **QGIS plan 来源不做裁定**（gold 反推 / 自蒸馏 / hybrid 维持 open
   dependency 到⑥）；唯一约束：**无论来源，进入 Stage 2 的 Plan 必须满足
   ④信息合同并通过 grounding sufficiency audits**。

## 新资产：QGIS Operator Capability Profile（309 算子）

与 148 语义映射表（解决"哪些算子同语义类"）不同层次——Profile 解决
"该算子具体能干什么、需要什么、产生什么"（identity/provider/intent/
I-O types/slots/required+optional parameters/parameter constraints/
type-geometry constraints/graph connection behavior）。**Stage-2
grounding 的知识底座**。可建自 Neo4j QGIS_Operator（1291 节点含
hasInput/hasOutput）+ processing 算法注册表。

## 三问题框架（Stage-2 的真正工作）

① Candidate Discrimination（区分实现）② Parameter/Constraint Grounding
（为何选它+如何配置）③ Graph Realization（连成 DAG）。

## 执行顺序

```
①②③④ ✅ ⑤ ✅（本记录）
→ ⑥B2 数据（核心悬题：1,334 条 QGIS workflow 如何配 Plan——
   既不回 37 类瓶颈，也不发生 gold graph→Plan 循环泄漏）
→ ⑦训练协议
```
