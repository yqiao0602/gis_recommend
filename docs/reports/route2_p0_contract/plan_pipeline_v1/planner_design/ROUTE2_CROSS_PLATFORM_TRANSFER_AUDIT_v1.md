# ROUTE2_CROSS_PLATFORM_TRANSFER_AUDIT 报告（v1，2026-10-05，CPU-only，只读）

> 依据 owner 指令（Phase 0 冻结后第一步）：GEE 101,513 train workflows ↔ QGIS 1,334 train
> workflows（+ dev/test）的平台无关结构特征对比。不训练、不碰冻结资产、locked test 不动。
> 脚本 `cross_platform_audit_v1.py`；数据 `CROSS_PLATFORM_AUDIT_v1.json`。

## Q1. 任务类型/目标语义重合度

主题归并后（12 主题映射表）：

| 主题 | GEE 行数 | QGIS 行数 | 共享 |
|---|---|---|---|
| Land use/land cover | 34,667 | 136 | ✓ |
| Vegetation/Agriculture | 32,441 | 38 | ✓ |
| Topography | 865 | 181 | ✓ |
| Surface water | 170 | 100 | ✓ |
| Climate/Atmosphere | 4,040 | 15 | ✓ |
| Soil/Geology | 398 | 15 | ✓ |
| Population/Society | 201 | 17 | ✓ |
| Hazards/Change detection | 11 | 52 | ✓ |
| Boundaries/Administration | 64 | 108 | ✓ |
| **Infrastructure/Built environment** | **125** | **254** | ✓ 但 **QGIS 侧独大** |
| GEE "Other"（映射未覆盖） | 28,369 | 545 | 部分 |

**判读**：主题覆盖共享 ✓（QGIS 侧 59% 的行落在与 GEE 共享的主题内）；
两个显著差异：① **Infrastructure/Built environment 在 QGIS 侧独大**（254 行 vs GEE 125）——
矢量/基建分析是 QGIS 特有主题；② GEE 28.4% "Other" 需主题映射精化。

## Q2. 操作 pattern 重合度

关键词规则将 QGIS 309 算子映射到 GEE 语义 family：

| 项 | 值 |
|---|---|
| 实例映射覆盖 | **69.7%**（5,650/8,105） |
| 未映射实例 | 30.3%（2,455） |
| 未映射 top | joinattributestable 251 / rasterize 137 / deletecolumn 132 / postgis import 82 |
| **family 词汇重合** | **17 个 family 完全共享，双向 0 独有** |

**判读**：映射后的 QGIS 操作分布与 GEE family 分布使用**同一语义词汇表**；
30.3% 未映射实例集中在**矢量属性管理**（join/字段删除/数据库导出）——
GEE 语义词汇表（遥感工作流导向）不含此类矢量数据库操作。

## Q3. 长度/复杂度差异（重大）

| 分位 | GEE 语义 stages | QGIS processes |
|---|---|---|
| p50 | **11** | **4** |
| p90 | 46 | 13 |
| p99 | 177 | 29 |
| max | 3,793 | 30 |

**QGIS workflow 在每个分位都短 2-3 倍**——GEE 脚本工作流的规模远大于 QGIS 模型。
这既说明 GEE 可提供"更长规划链"的监督，也提示**直接长度迁移不可假设**。

## Q4. 顺序结构重合

QGIS 首操作：buffer 93 / reprojectlayer 91 / refactorfields 78 / fixgeometries 68——
**数据准备开局**（与 GEE RASTER_LOAD 开局同构）；尾操作：postgis 导出/fieldcalculator/clip——
**产物落盘收尾**（与 GEE EXPORT_OUTPUT 收尾同构）。首尾模式同构 ✓。

## Q5. Branch/merge：QGIS 100% 新增结构

| 平台 | branch/merge |
|---|---|
| GEE（语义链） | **0%——纯线性序列，分支不可表达** |
| QGIS | **570/1,334 = 42.7%** 含分支或汇合 |

**GEE 线性目标对 DAG 结构的监督 = 零**。这是 QGIS gold 的独有价值，
也是 Planner-v3 必须用 QGIS 数据训练 DAG 结构的直接证据。

## 6. 可迁移性分类

| 类别 | 内容 | 证据 |
|---|---|---|
| **Transferable** | ① 任务主题覆盖（59-72% 共享）② 17-family 操作词汇（QGIS 69.7% 实例可映射）③ 首尾模式同构 ④ "load→filter→derive→aggregate→export" 通用 pattern | Q1/Q2/Q4 |
| **Partially transferable** | ① 长度/复杂度规范（QGIS 短得多；GEE 提供长链监督但分布不同）② 矢量属性管理操作的**通用语义**（join/字段管理可迁移思想，但 GEE 无对应 family） | Q2/Q3 |
| **Platform-specific** | ① **DAG branch/merge 结构（42.7%）——GEE 0%** ② 矢量数据库操作（joinattributestable/rasterize/postgis）③ QGIS 算子 ID 粒度（309 真实算子） | Q2/Q5 |

## 7. 对 A1/C0 训练设计的含义（供裁定）

1. **A1（GEE 预训练 → QGIS 微调）有数据支撑**：共享主题 + 共享 17-family 词汇 +
   同构首尾模式——GEE 可教"GIS 解决方案的通用结构规律"；
2. **但 A1 的覆盖上限 ≈ 69.7%**：QGIS 30.3% 的实例（矢量属性管理/DAG 结构）在 GEE
   词汇中无对应——这部分监督只能来自 QGIS gold；
3. **C0（QGIS-only）的可行域**：1,334 行对 SFT 偏小，但 QGIS gold 独有 DAG 结构监督
   （42.7%）是 A1 无法提供的；
4. **建议的训练形态**：A1 提供操作词汇与序列规律 → C0/QGIS gold 提供 DAG 结构与
   平台落实——**两阶段互补而非互斥**；比例与 curriculum 归 owner 裁定。
