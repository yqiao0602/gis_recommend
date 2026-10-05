# v2a_A 结构侦察报告（v1.1，2026-10-05，CPU-only 只读，1,565 条全量）

> 依据 owner 指令：11 维结构侦察，回答 5 个问题，为 Planner-v3 路线裁定提供输入。
> 脚本 `v2a_recon_v1.py`；结果 `v2a_recon_out.json`。零训练、冻结物未动。
>
> **⚠️ 口径修正（owner 确立三知识空间框架后追加）**：本报告的 "309 unique operators"
> 是 **workflow supervision coverage**（gold 中实际出现的算子），**不是 QGIS 算子空间规模**
> （QGIS Registry ≈ 1,200）。两者的区分与三级 operator 分类（Seen / Registry-known-but-
> gold-unseen / true-OOD）见 progress.md 2026-10-05 条目及 P0-3 Registry 审计（待执行）。
> 本报告所有 operator 分布数字均应在此口径下解读。

## 1. 图规模（Graph size）

| 指标 | processes | links |
|---|---|---|
| p50 | 4 | 3 |
| p90 | 13 | 14 |
| max | 30 | 93 |
| mean | 6.14 | 5.72 |

**图很紧凑**：中位 4 节点，p90 13 节点——与 owner 样例（4 processes/3 links）同量级。

## 2. DAG 有效性

| 项 | 值 | 备注 |
|---|---|---|
| 环 | **144（9.2%）** | gold 侧存在环——schema/evaluator 需决定处理方式（排除/允许/人工复核） |
| 孤立节点 | 106 | 少量 |
| 悬空 link | **0** | 引用完整性 ✓ |

## 3. 拓扑分类（Topology）

| 类型 | n | 占比 |
|---|---|---|
| 纯链 | 902 | 57.6% |
| 分支+汇合 | 382 | 24.4% |
| 仅分支 | 151 | 9.6% |
| 仅汇合 | 130 | 8.3% |

**42.4% 的 workflow 含分支/汇合**——owner 预期的"AOI 同时连接多个后续过程"的形态
真实存在且占比可观。行内最大 in-degree p90=2/max=20；out-degree p90=3/max=9——
分支浅（多为 1→2/3 扇出），非深扇形。

## 4. link_kinds：四种，direct 绝对主导

| kind | n | 占比 |
|---|---|---|
| **direct** | 7,805 | 81.0% |
| projected | 1,097 | 11.4% |
| patched | 875 | 9.1% |
| linear | 182 | 1.9% |

四种 kind 的语义（direct/patched/projected 的确切含义）需在标注/文档侧确认，
但分布本身已说明 **link 语义不是单一的**——Blueprint v2.5 的 links 字段若要对齐
此数据，需保留 kind 或做 kind 归并。

## 5. Operators：309 个真实 QGIS 算子，Grounding 级标识符

| 项 | 值 |
|---|---|
| unique operator_id | **309** |
| 总出现 | 9,615 |
| 单次出现（长尾） | 49 |
| 前缀分布 | native 157 / qgis 40 / grass7 45 / gdal 34 / saga 33（+其他） |
| Top 5 | native:fieldcalculator 840 / native:buffer 429 / native:reprojectlayer 405 / native:fixgeometries 384 / native:dissolve 291 |

**关键发现：operator_id 是真实 QGIS 算子 ID（Grounding 级）**，不是 owner 样例中的
抽象 identifier（raster_reproject/slope）。**抽象化映射是 Planner-v3 的一个设计任务**：
309 个真实算子 → 抽象语义 identifier 的归并表需要构建（可按前缀/语义分组半自动生成）。

## 6. taskType 与 tier

- taskType 12+ 类：Topography 212 / Infrastructure 202 / LULC 159 / Surface water 125 /
  Boundaries 123…——覆盖面广，图复杂度按类型差异不大（procs mean 5.5-6.6）。
- **tier 全部 = Tier-1**（1,565/1,565）——tier 字段在本数据集中**无判别力**。

## 7. 变量级 I/O：**确认不存在于数据中，但可从 QGIS 算子 schema 确定性恢复**

- 全字段扫描：processes 条目**仅** `{process_id, operator_id}`；links 条目**仅**
  `{source_process_id, target_process_id}`——**无任何隐藏字段**；
- 但变量级 I/O **不需要人工标注**：每个 QGIS 算子的输入/输出端口名是 QGIS 文档中的
  **固定常量**（如 native:slope → OUTPUT；native:rastercalculator → INPUT_A/INPUT_B…）。
  links 的 `targetVariable` 可由 **target 算子的端口 schema 确定性推导**；
- 前提：需要一个 **309 算子的端口 schema 表**（可从 QGIS 文档/pt2 引擎批量生成）。

## 8. 对 owner 5 问的回答

1. **结构**：紧凑 DAG（中位 4 节点），57.6% 纯链 + 42.4% 分支/汇合；9.2% 含环（需处理）。
2. **拓扑**：见第 3 节——branch/merge 真实存在且可观测（in/out degree 浅）。
3. **link_kinds**：4 种（direct 81% 主导），语义需标注侧确认。
4. **operator_id**：309 个真实 QGIS 算子——**Grounding 级**；抽象化映射表是
   Planner-v3 的前置设计任务（可半自动构建）。
5. **Gold 可用性**：**可直接作为 Planner-v3 的结构 gold**（processes+links 结构完整、
   引用干净），两个缺口：①变量级 I/O 需从 QGIS 算子 schema 推导（无需人工）；②
   **抽象 identifier 层需要构建**（309 → 抽象归并表）；③ 144 个环与 106 个孤立节点
   需要处理规则。

## 9. 对三个路线选项的含义

- **选项 1（GEE→QGIS 两阶段）与选项 3（迁移对齐）**：v2a_A 提供的正是
  "QGIS 侧的结构 gold"——两阶段/对齐都需要它；
- **选项 2（QGIS 直接做 Planner-v3）**：1,565 行偏小但结构完整；
  **且 operator_id 粒度问题（309 真实算子 vs 抽象 identifier）必须先解决**——
  若 Planner 直接学 309 算子，则是 Grounding 任务；若抽象化，需要归并表；
- **侦察未发现阻碍选项 1/2/3 任一方案的硬伤**；数据质量（0 悬空、引用完整）良好。
