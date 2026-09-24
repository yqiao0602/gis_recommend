# Route-2 v2 ④ Stage-1 接口信息合同 v0（2026-09-24，owner 裁定）

## 定位

④只冻结**信息合同**，不冻结最终 JSON/schema，不开始加工 B2 数据。
边界：**④解决"保留什么"，⑤才解决"还需要什么"**。

## 接口核心判断

> Stage-1 接口不是语义标签序列，而是**带类型、顺序和依赖信息的操作级
> Workflow Plan**；Stage 2 条件输入 = 原始 Task + Workflow Plan。

## 五必需信息层

| 层 | 内容 | 要点 |
|---|---|---|
| P1 Operation Intent | 这一步"要做什么" | **开放词表操作描述，禁用 37 类 ID 作唯一表示**（例："restrict raster data spatially using a specified polygon region"） |
| P2 Input/Output Types | 消费/产出什么 | **typed context 是 37 类的真正缺陷所在**（Raster→Raster clip vs Vector→Vector clip 高层同名但 grounding 不同）；信息源 = KG GEE_Operator hasInput/hasOutput（1425 节点，W1 结构化信息来源） |
| P3 Order | 操作先后 | **与 P4 分字段**——chain adjacency ≠ data dependency |
| P4 Dependency/Data Flow | 谁的数据进谁 | 尽量从真实数据流提取；**提取不到标 unknown，禁止为完整性伪造依赖** |
| P5 Context/Constraints | 步骤相关约束 | 只存与 step 相关的约束（时段/区域/数据条件），**不复制任务描述**（Task 与 Plan 互补：Task=为什么/目标，Plan=怎么做/怎么连） |

## 信息双层隔离（GEE provenance 原则）

```
训练/审计侧（保留）: GEE API、AST、canonical chain、KG signature、provenance
Stage-2 暴露侧:     Task + Workflow Plan（不含 GEE API）
```

原始 GEE 信息不入 Stage-2 显式条件——防止路线退化为 GEE→QGIS API 翻译。

## 开放程度限定

✅ 开放词表操作描述 + 结构化类型/依赖信息
❌ 禁止作为唯一接口：37 类 semantic ID、纯 operation token 序列、GEE API chain
定位：**比 37 类细、比原始 GEE API 更平台中立**（平台无关操作级描述 +
typed workflow structure）。
不重建 L3 ontology；建立的是高信息量、操作级、类型化、带依赖的 Plan 接口。

## 反 37 类瓶颈：三类正式审计（④定义，⑤定 benchmark）

1. **Plan Collision Audit**：多少不同原始 chain 被压成同一 Plan
   （A→B→C / A→D→C 全变 Clip→Stats = 接口压坏）
2. **Information Retention Audit**：chain→Plan 后 identity/order/I/O/
   dependency/dataflow 是否保留（vs 只剩 category）
3. **Grounding Discriminability Audit**：对同高层语义不同实现的候选
   （Spatial Clip ↔ native:clip / gdal:clipvectorbypolygon / …），
   Plan+Task 是否保留区分所需信息——直接连⑤的 Stage-2 信息需求

工程注记：审计①②依赖 chain→plan 转换管线（下一阶段首个工程产物）；
审计③可直接复用 oracle 148 算子映射的同类族分组（clip 家族等已存在）。

## 冻结/不冻结清单

**冻结**：五信息层、Task+Plan 双条件、GEE provenance 隔离、
开放词表原则、三类审计为必过项。
**不冻结**：具体 schema、token 序列化、Plan 语言形态（NL/JSON/混合）、
W1-W4 训练权重、**QGIS plan 获取方式（gold 反推 vs Stage-1 自蒸馏，
维持 open dependency）**。

## 执行顺序

```
①架构 ✅ ②能力 ✅ ③目标/接口 v0 ✅ ④接口信息合同 ✅（本记录）
→ ⑤Stage-2 信息需求（下一步，含三类审计 benchmark 化）
→ ⑥B2 数据 → ⑦训练协议
```
