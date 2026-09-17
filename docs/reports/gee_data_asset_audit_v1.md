# GEE 数据资产审计 v1：24 万描述库 × 21 万算子链的真实规模

日期：2026-09-17
触发：owner 指正「GEE 数据量在二十多万条，不只是 8,000 条，包含大量自然语言任务描述」。本审计在服务器（10.191.2.38，只读）实测三个资产及其链接关系。

---

## 1. 结论（先行）

| 指标 | 数值 |
|---|---:|
| 原始 GEE 脚本 | 295,943 |
| LLM 意图描述（描述性知识抽取汇总） | 241,943 行（30 个 CSV） |
| GEE-OPs 式算子链（15_知识表） | 211,517 行 |
| **描述 ∩ 链（方案 ②/C 的训练池）** | **191,210** |
| 噪声过滤后 ≥2 个真实算子 | 178,652（93.4%） |
| **算子链精确去重后（模板镜像压缩 34%）** | **117,735** |
| 对照：当前 GEE 训练行 | 8,283（源自 5,014 脚本） |

**即使按最保守口径（去重后 117,735），也是现池的 14 倍；可用口径 178,652 是 21.6 倍。**

**关键发现：意图重写（paper_v2 的第一公里）已基本由描述库完成**——98.5% 的描述不含算子名（转写率 1.5%，对照现池 100%），99.9% 英文，median 442 字符，0% 空值。

## 2. 三个资产与链接

### 2.1 意图描述库 `/home/yll/GEE/描述性知识抽取汇总/facts_summary*.csv`

- Schema：`File Name / Task Type / Task Name / DataSource / Geospatial Values / Time Ranges / Task Description`
- 241,943 行；338 个任务类型（Top：LULC 76,100 / 植被 39,620 / 农业指标 34,015 / 水文 14,893）
- 抽样 3,000 行质检：
  - 空描述 **0%**；长度 median 442 / p10 250 / p90 666 字符
  - 含 `ee.*` 或方法名回声：**1.5%**（vs 现池 100% 转写）
  - 提及 Earth Engine/GEE 字样：25%（平台词，可保留或剥离）
  - 中文：0.1%；Task Name 空缺：0.1%
- 描述为第三人称（"The script classifies…"），用于训练需轻量改写为任务指令式（或直接用 Task Name + Description 组合）
- 75 个超限脚本被跳过（skipped_too_large.log）

### 2.2 算子链库 `/data/yll/GeoWorkflow-Knowledge-Dataset/01原始代码/GEE/GEE_OPs/`

这就是 GEE-OPs（arXiv 2412.05587，调研报告引用的那篇）方法论的完整落地：

```
01_Input_raw_script   295,943 个 .txt
04_Script2AST_json  → 05_AST_json        234,067 份 AST（79.1% 解析成功）
07_AST2Relationship → 08_API_relationship 212,282 份逐脚本关系表
14_Chain.py         → 15_Operator_Relationship_Chain_Knowledge_Table.csv
                                          211,517 条 (Script Name, Operator Chain)
```

链形态（原始，含噪声）：`MOD09A1.filterDate.map.median.clip -> print -> Map.addLayer -> …`
含 `print / Map.* / ui.* / for( 循环壳 / 自定义函数名` 等非算子项，需清洗（与现 8,283 管线同性质的工作）。

### 2.3 链接验证（关键）

- 描述库 `File Name`（script_NNNN.txt）→ `/home/yll/GEE/Data/data20000_AST_failed/dataNNNNN/script_NNNN.txt`（248,488 个脚本在盘）
- 内容核实一致：script_234511（Multan 作物分类）描述中的 Landsat-8/NDVI/GNDVI/RF 分类全部在源码中出现
- 两库同键（script_NNNN），交集直接可算：**191,210**

## 3. 去重测量（模板镜像风险实锤）

样本检查发现 script_100001~100007 是同一模板（`yealy.map` 家族）的变体。精确链去重实测：

```
178,652 可用 → 117,735 唯一链（-34.1%，模板镜像）
```

注意这是**下界口径**（仅精确链去重）；语义级去重（类似 QGIS 侧语义签名方法）会再压缩，但也应保留部分变体（同一链不同描述 = 数据增广，对意图学习有益）。**建议训练对采用「链去重 + 描述保留多版本」策略**，规模落在 12-18 万区间。

## 4. 转化为训练数据的剩余工作

| 步骤 | 性质 | 现成基础 |
|---|---|---|
| 链清洗（去 print/Map/ui/循环壳） | 确定性 | 已验证正则过滤可行（本次审计已用）；现 8,283 管线的清洗纪律可复用 |
| 算子名规范化（`MOD09A1.filterDate` → `ee.ImageCollection.filterDate`） | 确定性 | 06_Operator_Syntax_Knowledge_Table + 项目内 GEE canonical alias 审计（306 算子，306/306 已映射） |
| GEE→L3 映射（方案 C 需要） | 权威表 | 现有 mapping authority；38.3% token 落无桥 code 的老问题依旧，但方案 B 不经过 L3，不受影响 |
| 描述 → 任务指令式改写 | 轻量 | 描述已是意图文本，仅需句式改写或直接组合 Task Name |
| 描述质量抽检 | 人工 | 本审计 3,000 行抽样 + 4 条全样核实；需扩到分层抽样 ~200 条 |
| 去重 + source-disjoint split | 纪律 | 项目既有方法（QGIS 侧语义签名、GEE 侧 source-disjoint） |

## 5. 对路线决策的影响

1. **paper_v2 的「意图重写」第一公里从『要做』变成『收尾』**：24 万条意图描述已在盘上，且质量指标全面优于预期（回声率 1.5%）。
2. **方案 B（双角色）与方案 C（修 L3）的数据天花板同时改写**：GEE 侧从 8,283 → 12-18 万（去重后），QGIS 侧维持 629（fail-closed 上限 ~700-800）。两侧不对称进一步加大——B/C 的差异（要不要显式 L3）成为唯一变量，恰好是可控对照实验。
3. **GEE-OPs 方法论同源**：算子链库就是调研报告脉络三里 GEE-OPs（185k 脚本）的复现（295,943 > 185,236），意味着「用频繁项集/关系表扩 GEE 侧数据」的调研建议也已部分就位。
4. 风险如实记录：链长 noise-filter 后 median 9（长于现池 mean 6.4），说明链内含较多细粒度 API 调用，清洗口径需与现 8,283 对齐后再比规模；语义去重率未测（精确去重 34% 是下界）。

## 6. 复现

- 全部命令为服务器只读查询（ls / head / wc / python3 csv 统计），未修改 `/home/yll` 与 `/data/yll`
- 关键路径：
  - 描述库：`/home/yll/GEE/描述性知识抽取汇总/facts_summary{N}.csv`（30 文件，台账 `facts_summary_row_counts.csv` 记 241,083，实测含 header 修正后 241,943 行）
  - 链库：`/data/yll/GeoWorkflow-Knowledge-Dataset/01原始代码/GEE/GEE_OPs/15_Operator_Relationship_Chain_Knowledge_Table.csv`（211,516 数据行）
  - 原始脚本：`/home/yll/GEE/Data/data20000_AST_failed/dataNNNNN/`（248,488 个）
