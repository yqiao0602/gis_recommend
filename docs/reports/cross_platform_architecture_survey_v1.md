# 跨平台架构调研：L3 中介层的问题、替代方案与文献证据

日期：2026-09-16
触发：owner 提出「GEE→L3→QGIS 三级映射存在精度/算子丢失，是否应改为①纯 QGIS 训练，或②双角色训练（GEE 学工作流组合 / QGIS 学算子落地）去掉显式中介层」
方法：本地数据实测（3 轮）+ arXiv 文献检索（8 组 query，含 2 篇核心同构工作）

---

## 1. 执行摘要

**你的诊断成立，但丢失的来源与假设不同——关键修正如下：**

| 你假设的 | 实测 | 结论 |
|---|---|---|
| GEE 算子转 L3 后找不到对应 QGIS 算子 | 43.9% 的 GEE 触及 code 无 QGIS 桥；**38.3% 的 GEE 训练 token 落在这类 code 上** | ✅ 成立，量级明确 |
| 原因是"平台算子做不到一一对应" | 断链 code 全是 `no_frozen_qgis_implementation`（映射基础设施未覆盖），**而非 QGIS 语义不可实现** | ⚠️ **需修正**：主要是映射覆盖不足，不是平台语义鸿沟 |
| 应去掉中间层 | 文献：**中间表示本身有益，有害的是"有损的中间表示"**（UNICS 明确批评 AST/IR 丢信息，IRCoder 证明保真 IR 提升跨语言迁移） | ⚠️ **方向对，结论要改** |

**最重要的一条**：38.3% 的丢失中，绝大部分不是"GEE 专有概念"，而是**我们自己的映射管线只建了 50 个桥**——capability matrix 的 101 个 code 里有 48 个被标为 `refusal`（理由统一是 `no_frozen_qgis_implementation`：当时没找到经过审计的 QGIS 实现），而它们多是通用 GIS 操作（按日期筛选、按空间范围筛选、植被指数、改数据类型）。

---

## 2. 数据实测（三轮验证）

### 2.1 L3→QGIS 映射覆盖（修正版口径）

| provider | 目录算子数 | 有 L3 映射 | 覆盖率 |
|---|---:|---:|---:|
| native | 247 | 149 | 60.3% |
| qgis | 58 | 34 | 58.6% |
| gdal | 56 | 38 | 67.9% |
| **核心小计** | **361** | **221** | **61.2%** |
| grass7 / saga / otb（第三方插件） | 930 | 41 | 4.4% |
| 合计 | 1291 | 262 | 20.3% |

**核心算子丢失率 38.8%**（不是初测的 79.7%——那个数字把 930 个第三方插件算子算进去了，它们本就不必映射）。

**benchmark 路径是干净的**：final-100 gold 用到的 34 个算子 **34/34 全部有 L3 映射**。

### 2.2 GEE→L3→QGIS 的真实丢失

```
GEE 训练 token 总量          52,894
其中落在无 QGIS 实现的 code   20,259 (38.3%)   ← 永久不可迁移
  ├─ L3_03_09_01 Filter by Date Range      11.9%
  ├─ L3_10_02_03 Multi-temporal Averaging   6.6%
  ├─ L3_03_09_06 Filter by Spatial Bounds   6.0%
  ├─ L3_03_09_05 Filter by Metadata         5.6%
  ├─ L3_03_08_01 Vegetation Indices         2.1%
  └─ 其余 20 个 code                         6.1%
```

**多对一压缩**：57.9%（33/57）的 L3 code 接收多个 GEE 算子（如 `mean/median/count` → Multi-temporal Averaging），抽象层固有压缩，本身合理。

### 2.4 决定性证据：refusal code 与已桥接 code 语义重叠

查询 capability matrix 的 `refusal` 层 code 与已桥接 code 的对应关系，发现**同一个 QGIS 能力同时挂在两个 L3 code 下**：

| refusal code（无桥） | QGIS 真实实现 | 已桥接 code（同能力） | 桥接算子 |
|---|---|---|---|
| L3_03_08_01 Vegetation Indices | raster calculator | **L3_03_03_A** Arithmetic & Math | gdal:rastercalculator（8 候选） |
| L3_10_02_03 Multi-temporal Averaging | cell statistics | **L3_03_10_R** Temporal Reducer | native:cellstatistics |
| L3_03_09_06 Filter by Spatial Bounds | extract by location | **L3_02_06_03** Extract by Location | native:extractbylocation（4 候选） |
| L3_01_13_01 Change Pixel Data Type | translate / convert format | **L3_01_09_01** Vector Format Conversion | gdal:convertformat |

**机制**：GEE 的 collection 语义把操作切得**细**（时序筛选、空间筛选、时相聚合各自成 code），QGIS 的算子则**粗**（一个 `extractbylocation` 同时服务多种筛选语义）。我们的映射把这些粗算子各登记到**一个** code 下，于是 GEE 侧走另一个 code 的同一操作就"查无此桥"。

**这不是平台能力缺失，是分类粒度与映射登记方式造成的码字不匹配。** 38.3% 的"丢失"有相当部分是这一类伪丢失。

**但仍有一个真实约束**：benchmark 要求 **parameter-free 算子**。按日期/表达式筛选在 QGIS 侧必须带参数（`extractbyexpression` 需要表达式），所以当初归入 refusal 有其道理——**参数无关约束才是真实边界，分类粒度是人为可修的**。

48 个 refusal 层 code 的判定理由**全部相同**：`no_frozen_qgis_implementation`——这是**映射基础设施的状态描述**，不是 QGIS 能力判定。抽查其语义：

| code | 语义 | QGIS 实际能力 |
|---|---|---|
| Filter by Date Range | 按日期筛选 | `native:extractbyexpression`（日期表达式）/ `qgis:selectbyattribute` |
| Filter by Spatial Bounds | 按范围筛选 | `native:extractbylocation` / `native:clip` |
| Vegetation Indices | NDVI 等 | `gdal:rastercalculator`（已有 L3_03_03_A 桥到它） |
| Change Pixel Data Type | 改数据类型 | `gdal:translate`（-ot 参数） |
| Update Mask | 掩膜更新 | `gdal:cliprasterbymasklayer` / raster calculator |
| Multi-temporal Averaging | 多时相均值 | `native:cellstatistics`（已桥到 L3_03_10_R） |

**这些是通用 GIS 操作，QGIS 都支持**。它们未映射的原因是双向的：
1. 我们的 bridge v1 只取 `headline_core` 层（50 code），未处理 refusal 层的 48 个
2. benchmark 要求 **parameter-free 算子**，而按日期/表达式筛选天然需要参数——这可能才是当初归入 refusal 的真实理由（**这是一个真实的表达力约束，不是基础设施疏漏**）

---

## 3. 文献调研（四条脉络）

### 脉络一：中间表示 vs 直接迁移（最核心）

| 工作 | 年份 | 结论 |
|---|---|---|
| **IRCoder** (arXiv 2403.03894) | 2024-03 | 用编译器 IR（跨语言共享）继续预训练 Code-LM，**强制模型学习 IR 并把 IR 构造与各语言构造对齐** → 跨语言迁移显著提升。**IR 有益** |
| **CodePivot** (arXiv 2604.18027) | 2026-04 | 用 Python 作为枢轴语言做跨语言 transpile（RL 训练）；指出成对训练数据稀缺是主要瓶颈 → **高资源语言可作枢轴** |
| **UNICS** (arXiv 2606.27747) | 2026-06 | **明确批评**："AST/IR 等统一表示会丢失关键信息"；解法=两阶段：① 统一伪代码表示（**保留完整语义保真度**）学跨语言算法级逻辑；② 多任务迁移，**把代码分解为语义切片（API 调用、函数体）适配到具体语言** |

**综合**：中间表示有用 ⟺ **保真**。UNICS 的两阶段（通用逻辑 → 平台特定切片）与你的方案 ② 结构完全同构。

### 脉络二：跨系统 SQL 方言翻译（最贴近的同构问题）

| 工作 | 做法 |
|---|---|
| **CrackSQL** (2504.00882) | 规则+LLM 混合；指出纯 LLM 会"生成不存在的函数"；用**跨方言语法嵌入**做对齐，**不用统一 IR** |
| PARROT / MoMQ / RISE | 跨系统 SQL 翻译基准与多方言生成 |

**关键**：SQL 方言翻译界主流是**方言↔方言直接翻译**（辅以规则/嵌入），而非经过统一 IR——因为 SQL 方言间差异是语法性的、可机械对齐的。这与我们的情形不同：GEE↔QGIS 的差异是**概念级**的（collection 时序算子 vs 单幅栅格算子）。

### 脉络三：GIS/EO agent 基准现状（确认问题未被解决）

| 工作 | 要点 |
|---|---|
| **GISAgentBench** (2608.01645, 2026-08) | 349 个多步 GIS 任务（来自 GIS Stack Exchange），**带可执行参考轨迹与真实 ground truth**。明确批评既有基准"依赖代码相似度/轨迹匹配/LLM 判官等代理信号，会混淆流程相似与任务正确" |
| **GEE-OPs** (2412.05587) | 从 **185,236 个真实 GEE 脚本**用 AST+频繁项集挖掘构建算子知识库（语法表/关系频率表/频繁模式表/关系链表），抽取准确率 >90% |
| AutoGEEval / AutoGEEval++ / TerraBench / TerraLogic / Earth-Agent-Pro | GEE 代码生成与 EO agent 评测 |

**检索 `abs:"Google Earth Engine" AND abs:"QGIS"` 返回零结果** → **跨平台（GEE↔QGIS）迁移无人做过**，与 2026-09-16 外部调研结论一致。

### 脉络四：本项目的两个设计已被文献背书

1. **GISAgentBench 对"代理信号"的批评**，正好证明我们坚持**算子级 gold + 冻结 scorer**（而非 code similarity / LLM judge）是对的
2. **GEE-OPs 的 185,236 脚本**是我们 8,283 行的 22 倍——说明 GEE 侧数据还可以大幅扩；且它证明了"从真实脚本挖算子模式"这条路线可规模化

---

## 4. 三个方案的评估

### 方案 A：纯原生 QGIS 训练（放弃 GEE）

**可得数据**（实测）：
- 现成：629 行（paper_v1 QGIS）
- 可提取：QGIS 算子级源包链 **1,351 行**
- 需加工：GitHub 54,240 个 QGIS 脚本中 **10% 含 `processing.run` 调用（≈5,400 个）**，72% 有 docstring（可作任务描述来源），链长 median 2 / p90 16 / max 26

**可行性**：天花板约 **5,000-7,000 行**（需提取+审计），比现有 629 行高一个量级。
**代价**：失去 GEE 的 8,283 条**长工作流组合**样本（GEE 链长 mean 6.4，是学"任务分解"的主要来源）。
**证据警示**：V4.6 冠军（QGIS 矢量过采样数据训练）在冻结基准上是 0.137——**生成行为健康（0 空图 0 失控）但选择能力差（首算子 12%）**。这暗示小规模 QGIS-only 数据能教会"怎么生成"，教不会"选什么"。

### 方案 B：双角色训练（GEE 学组合 / QGIS 学落地，无显式中介层）

**文献支持度：高**
- UNICS 两阶段（通用逻辑 → 平台语义切片）与你描述的结构同构
- CodePivot 证明"高资源平台作枢轴"可行
- IRCoder 证明"学习 IR + 与多平台对齐"有效

**但有两个必须正视的问题**：
1. **"去掉显式 L3" ≠ "没有中间表示"**。模型内部必然形成某种隐式对齐空间；区别只在于它是学出来的（连续、不可审计）还是设计出来的（离散、可审计）。**我们的治理纪律（SHA 对账、审计、可复现）依赖显式中介层**——去掉它，评测链的可解释性会下降。
2. **QGIS 侧数据量是瓶颈**：隐式对齐需要足够的 QGIS 样本才能"锚定"。629 行大概率不够（M2 的 DAPT 实验已证明：代码域适应改善了代码 PPL 但 cloze 算子语义零增益——**语料里有代码 ≠ 学得到算子语义**）。

### 方案 C（数据指向的第三条路）：修保真的 L3，而不是去掉它

**证据链**：
- 丢失主要是 `no_frozen_qgis_implementation` —— **映射管线覆盖不足**，可修
- 48 个 refusal code 中多数是通用 GIS 操作，QGIS 有实现
- 真实约束只有一个：**benchmark 要求 parameter-free**，按日期/表达式筛选天然需要参数

**可执行动作**：
1. 把 bridge 从 50 code 扩到 capability matrix 的 101 code（对 48 个 refusal code 做正经的 QGIS 实现审计）
2. 对确实只能带参数实现的 code，在**桥接层**加"参数化算子"降级策略（如 Filter by Date Range → `native:extractbyexpression`，参数固化），并在评分时标注
3. 用 GEE-OPs 的方法（AST + 频繁项集）扩 GEE 侧数据至 185k 脚本量级

---

## 5. 建议

**短期不做架构切换**，理由：
1. 当前绑定约束**不是 L3 层**——是 SFT 任务形态（转写 vs 意图）。同一个模型在转写式 val 上 41-43/49，在意图式 benchmark 上 F1 0.16-0.22。**先修任务形态**（paper_v2 意图重写，素材已定位），才能在干净的条件下评估 L3 层到底还损失多少。
2. 方案 B 的隐式对齐需要 QGIS 数据锚定，而 QGIS 数据扩产（5,400 脚本提取）**与方案 A/B/C 都需要**，是共同前置。

**建议的推进顺序**：

```
① paper_v2 意图重写（GEE 25.7 万描述库）      ← 当前唯一有证据的杠杆
② QGIS 数据扩产（5,400 脚本 → 算子链+任务）    ← A/B/C 共同前置
③ bridge 扩容 50 → 101 code（含 refusal 层审计）← 方案 C，成本最低
④ 在①②③完成后重新测量 L3 层损失             ← 用同一冻结基准
⑤ 若 L3 仍是瓶颈 → 才做方案 B（双角色训练）     ← 有对照、有数据支撑
```

**一句话**：你的直觉指向了真实的结构性损失（38.3% 的 GEE token 不可迁移），但根因是**映射管线覆盖不足 + 参数无关约束**，不是"中介层本身有害"。文献证据一致：**保真的中间表示提升跨平台迁移，有损的才有害**——所以第一步该修的是"让它保真"，而不是拆掉它。

---

## 附录：检索记录

arXiv API 查询（8 组）：geospatial agent / tool grounding / tool retrieval generalization / pivot error propagation / code translation library / cross-lingual structured prediction / skill composition / cross-platform geospatial workflow。Semantic Scholar 因无 API key 限流（429），引用数未获取。GEE+QGIS 联合检索返回零结果。

关键文献：
- IRCoder — arXiv:2403.03894
- CodePivot — arXiv:2604.18027
- UNICS — arXiv:2606.27747
- CrackSQL — arXiv:2504.00882
- GISAgentBench — arXiv:2608.01645
- GEE-OPs — arXiv:2412.05587
