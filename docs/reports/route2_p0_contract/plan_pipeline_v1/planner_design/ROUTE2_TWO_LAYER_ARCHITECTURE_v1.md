# Route-2 两层架构定义（v1，2026-10-04，owner 确立）

> 本文档固化 owner 于 2026-10-04 确立的 Route-2 核心架构重定义。此后所有实验设计、
> Schema 决策与论文表述以本文为准。

## 1. 一句话定义

> **利用大规模 GEE workflow 数据学习通用 GIS 任务的 Workflow Reasoning 能力，
> 再利用小规模 QGIS workflow 数据学习该规划方案在 QGIS 平台中的具体 Grounding
> 与图结构实现。**

## 2. 两个不同的问题（不得混淆）

### 第一层：GIS 任务规划（GIS Workflow Planning）

- 输入：自然语言 GIS 任务
- 输出：**GIS Solution Plan**（平台无关的语义操作序列 + 数据流）
  ```json
  {"processes": [{"id": "p1", "operation": "reproject"},
                 {"id": "p2", "operation": "slope"},
                 {"id": "p3", "operation": "reclassify"},
                 {"id": "p4", "operation": "weighted_combination"}],
   "links": [{"source": "p1", "target": "p4"},
             {"source": "p2", "target": "p3"},
             {"source": "p3", "target": "p4"}]}
  ```
- 回答："这个任务从 GIS 方法论上应该怎么解决？"
- **学习信号来源：GEE 128k workflow 数据**
- 不关心：native:buffer、grass7:r.slope.aspect 等平台实现

### 第二层：QGIS Grounding

- 输入：GIS Solution Plan
- 输出：QGIS processes + links（真实算子 ID + 端口 + 参数）
  ```text
  slope → native:slope
  reclassify → native:reclassifybytable
  weighted_combination → native:rastercalc
  ```
- 回答："这个方案在 QGIS 里怎么实现？"
- **学习信号来源：QGIS 1,565 workflow gold**

## 3. L3（跨平台算子中间层）：取消

原思路 "GEE operator → L3 → QGIS operator" 是**翻译问题**；
Route-2 的真问题是**从 GEE 数据学习 GIS 问题的解决思路**（Task → Workflow Reasoning），
不是算子翻译。L3 取消。

## 4. "重复"的三层框架（随架构重定义一并确立）

| 层 | 内容 | 处理 |
|---|---|---|
| 重复语义（scope） | "对每个波段分别处理"——GIS 方法论层面的迭代结构 | **保留**：可作为规划信息（scope = per_band） |
| repetition group | "Stage 3 按波段展开"——供 Grounding 理解的结构标记 | **保留**：Grounding 需要知道展开维度 |
| 绝对 repeat 数 | `repeat = 12`——GEE 当前数据实例的执行细节 | **移出 Planner 目标**：由 Grounding 从实际数据解析 |

核心区分：**GIS planning knowledge ≠ GEE execution detail**。

## 5. 数据/实验的重新定位

| 数据/实验 | 真正作用 |
|---|---|
| GEE 128k | 学 **GIS Task → Workflow Solution** |
| Planner-v1 | 验证 workflow composition 基础能力 |
| Planner-v2 | 验证 ordered/repetition reasoning（**能力验证实验**，非最终方案） |
| QGIS 1,565 | 学 **GIS Solution → QGIS implementation** |
| processes + links | 最终 QGIS workflow 表示 |
| QGIS operator_id | Grounding 层 |
| QGIS port schema | Grounding / execution 层 |
| RL | 后续优化，不进入当前主线 |
| **L3** | **取消** |

## 6. 对当前实验序列的影响

1. **Planner-v2（语义 stage 粒度）**：其 30 语义 family 是向 GIS Solution Plan
   抽象层靠拢的**中间粒度**——比 plan family（19）细、比 owner 样例的命名操作
   （reproject/slope/...）粗。它的能力验证结论（E1 0.664 / E2 0.967）继续有效，
   但**正式 Planner-v3 的操作粒度需要重新裁定**（30 语义 family vs 更细的命名操作）。
2. **Grounding 层的前置件**：309 QGIS 算子的抽象化归并表（semantic/abstract op →
   QGIS operator）+ 算子端口 schema 表——两项均已登记为半自动可构建。
3. **S5（hint 绑定）**：在新架构下，hint = iteration dimension 分类，
   其与具体 stage 的绑定问题需要在 Planner-v3 的目标定义中重新表述。
4. **统一对比管线**：v1/v2 的 bag-F1 统一对比仍有效（family-selection 能力比较），
   但新增粒度维度后，对比设计需纳入"操作粒度"变量。

## 7. 路线图（更新）

```text
GIS Task
   │
   ▼
General GIS Workflow Reasoning     ← GEE 128k（大规模监督）
   │
   ▼
GIS Solution Plan                  ← 抽象操作 + 数据流（粒度待裁定：30 语义 family
   │                                   vs 更细的命名操作）
   ▼
QGIS Grounding                     ← QGIS 1,565 gold（平台落实）
   │
   ▼
QGIS Workflow Graph                ← processes + links（最终表示）
```

## 8. 状态

- 本文档为**架构级定义**，冻结待 owner 确认后生效于所有后续实验设计。
- Planner-v2 formal round 1 结果（E1 0.6636/E2 0.9670）作为能力验证证据保留。
- 下一步（Planner-v3 操作粒度裁定 / Grounding 层设计 / 统一对比管线）**归 owner**。
