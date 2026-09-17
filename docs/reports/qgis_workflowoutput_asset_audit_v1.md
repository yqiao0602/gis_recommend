# QGIS Workflowoutput 资产审计 v1：6,138 个意图描述工作流

日期：2026-09-17
触发：owner 指正「QGIS 不只是 629 行」，指向 `/data/yll/GeoWorkflow-Knowledge-Dataset/04抽取结果/QGIS`。
性质：只读审计（全部服务器查询，未写入 /data/yll）。

---

## 1. 结论（先行）

**QGIS 侧存在一个此前完全没进入我们视野的平行资产：6,138 个「意图描述 + 算子图 + 溯源」工作流**，2026-09-15/16 由 yll 的抽取管线（QGIS workflow extractor）产出。它和 GEE 侧的 128,447 行结构同构（descriptionSource="descriptive_knowledge"），是 **Route-2 QGIS-Grounding 的潜在 10 倍扩容**（629 → 最高 ~6,138）。

但**尚未达到训练可用**：三道门（operator 规范化、QA FAIL 解读、与 629 池关系）需要处理后才可判定净增量。

## 2. 资产清单

```
/data/yll/GeoWorkflow-Knowledge-Dataset/04抽取结果/QGIS/
  6,138 个 W* 目录（mtime 2026-09-15/16，两天前刚产出）
  每目录：workflow.json（id/name/description/processes/links/metadata）
          tables/（steps/data/edges/process_relations/accepted_port_relations CSV）
          audit/（core_call_steps/semantic_filter_audit 等）
          ast.json、workflow_phase.json
  _qa/：qa_workflows.csv + qa_issues.jsonl（QA 状态 1,475 PASS / 4,663 FAIL）
```

| 指标 | 值 |
|---|---:|
| 工作流 | 6,138（全部有 description + provenance） |
| 算子总数 | 63,570（mean 10.4/流），链 59,838（mean 9.7） |
| 唯一算子 | 774（PyQGIS API + provider 混合） |
| provider 式调用（`native:*` 等） | 32,791（51.6%），其中 **86.8% 在 benchmark 目录内** |
| 描述 | median 650 字符（p10-90: 425-993），意图文本（"The script calculates…"） |
| 名称 | 6,132/6,138 是祈使式标题（"Calculate watershed union area"） |
| 任务类型 | Topography 803 / LULC 782 / Infrastructure 705 / Human settlements 597 … |
| 来源（03抽取脚本/QGIS） | GitHub direct 3,588 / tutorial direct 1,613 / official plugins 757 / model-tutorial 561 … |
| 与 629 池 | **0 重叠**（完全不同的源集合） |

样本质量（4 条抽验全部语义一致）：流域土地利用影响指数描述 ↔ `selectbylocation→extractbyattribute→buffer`；视域定位质量 ↔ GDAL 波段/变换/投影链。

## 3. 三道未过的门（如实记录）

### 门 1：算子双层混合
51.6% 是 provider 式（benchmark 同空间），48.4% 是 PyQGIS/GDAL API 层（`QgsFeature.setGeometry` 3,401 次、`GDALDataset.GetRasterBand` 1,797 次）。两个层不能直接混作一个输出空间——需要按 Route-2 原则分层（provider 层 = grounding 目标；API 层 = 辅助上下文或剥离）。

### 门 2：QA FAIL 4,663 的主因是抽取器自身配置
`UNKNOWN_OR_UNQUALIFIED_CANONICAL` 影响 4,499 个流——但被标 UNKNOWN 的 top 算子是 `native:fieldcalculator(3,059) / native:buffer(1,117) / native:clip(770)` 这些**目录内算子**。这是抽取器的 canonical 白名单未配（与 GEE 侧 06 表缺口同类），不是数据缺陷。ARG_N（端口命名）影响 381 个流，纯格式问题。
真实结构质量问题（INVALID_PORT / DUPLICATED_PORT / EMPTY_INPUTS）影响面待精确统计，但 PASS+纯格式 FAIL ≈ 1,639+ 个流已经是干净子集。

### 门 3：与现有 629 池的关系
6,138 源脚本与 paper_v1 629 池 **0 交集**——是纯增量不是重复。但 629 池经过我们的 fail-closed 审计（依赖闭合、L3 映射、语义审核），6,138 没有经过我们的标准。两者不是替代关系，是**不同信任等级的两层**：629 = gold/审计层，6,138 = silver/规模层。

## 4. 对 Route-2 四臂实验的影响

| 数据集 | 原计划 | 现在 |
|---|---|---|
| QGIS-Grounding | 629 | **629（gold）+ 最高 ~6,138（silver，待过三道门）** |
| GEE-Expanded | 128,447 | 不变 |
| 配比 | 205:1 | 最好情况 ~21:1（若 silver 全量可用） |

**C0 基线臂也应受益**：QGIS-only 不再被 629 封死，方案 A（纯 QGIS）的天花板需要重估——但先过三道门再下结论。

## 5. 建议的下一步（待 owner 裁定）

1. **算子规范化**（确定性）：`qgis:fieldcalculator → native:fieldcalculator` 旧前缀折叠（1,235+ 次调用）、provider 式与 API 式分层、86.8% 目录内对齐复核
2. **QA 重判**（确定性）：用 benchmark 目录作 canonical 白名单重跑 QA——预期 FAIL 大幅下降，得到真实结构质量分层
3. **结构审计**（我们标准）：对 ≥2 provider 算子的 3,552 个流做依赖闭合/L3 对齐抽验（复用 07-22 多步 pilot 的方法）
4. **对比实验设计更新**：C0/B2 臂的 QGIS 数据量从 629 变成 629+X（X 由 1-3 决定），需在 Step 4 设计中重新配比

## 6. 复现

- 全部为服务器只读查询；统计脚本内嵌本报告命令（os.listdir + json.load + Counter）
- 关键路径：`/data/yll/GeoWorkflow-Knowledge-Dataset/04抽取结果/QGIS/W*/workflow.json`、`_qa/qa_workflows.csv`、`_qa/qa_issues.jsonl`、`03抽取脚本/QGIS/`（源脚本，9 个来源目录）
