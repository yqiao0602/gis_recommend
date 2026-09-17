# Route-2 P0 Training Contract（冻结 v1）

日期：2026-09-17（owner 六项裁定 + ①②③终裁）
地位：**四臂实验（C0/A1/B1/B2）的执行契约**。任何训练/评测脚本必须与本文件一致；改动需 owner 显式解冻。

---

## P0-1 数据（已冻结）

| 数据集 | 规模 | 冻结位置 | SHA / commit |
|---|---|---|---|
| GEE-Expanded v1 | 128,447 行（101,513 train / 11,075 val / 15,859 test） | 服务器 `outputs_v2/gee_conversion_wf_full_v1/pilot_rows.jsonl` | SHA256 `ab9ab28575c5b9812e5994f0266efb9d032816a76ec02026011c6b197e446a5e`（0f85c83） |
| QGIS v2a-A | 1,334 / 120 / 111 | 仓库 `docs/reports/v2a_manifest/`；服务器训练副本 `/home/qy/gee_llm_smoke/v2a_A_*.jsonl` | commit 63b5db1 |

配对纪律：GEE 侧 B 池同源（描述与链同池、内容验证）；QGIS 侧 v2a 结构审计。历史资产（629 旧池、pool-A 44,220 行）**不得混入**。

## P0-2 QGIS split（owner 裁定 2026-09-17）

```
train 1,334   —— 参数更新
dev   120     —— checkpoint selection / early stopping；不参与任何参数更新
test  111     —— 训练全过程结束后只评一次
```
禁止临时切分（不再出现 M2-C0 的 49 行临时 val）。四臂共用同一 split。

## P0-3 GEE split（已冻结）

作者代理 ∪ 折叠链 union-find 连通分量切分，枢纽分量（>200 行）作者子组切分。**作者泄漏 0**（train/test、train/val、val/test）；链泄漏 281 条多作者通用习语（6.56% 行，全部 ≥2 作者，已声明）。

## P0-4 输出空间（owner 终裁 2026-09-17）

| 臂 | 第一阶段目标 | 第二阶段 | 推理输出 |
|---|---|---|---|
| **C0** | —— | Task → QGIS 图（SFT） | QGIS Graph |
| **A1** | GEE 语料 DAPT（域语言，无任务映射） | Task → QGIS 图（SFT） | QGIS Graph |
| **B1** | **Task → Semantic Workflow**（37 类，SFT） | Task → QGIS 图（SFT） | QGIS Graph |
| B2（占位） | 待 C0/A1/B1 结果后设计 | —— | QGIS Graph |

**关键控制：四臂推理输出全部是 QGIS Graph**（benchmark 契约 processes+links）。

### B1 语义层细则（owner 三点终裁）

1. **RLE = ON**：连续同类操作折叠（表示规范化，非信息删除）；`semantic_chain_raw` 保留审计。
2. **post-RLE run-cap = 3**：交替周期模式（如 A→B→A→B≥3 次）折叠为一个周期，在 RLE 之后应用；逐行记录 `run_cap_applied / original_semantic_length / final_semantic_length`。
3. **B1 监督 = Task → Semantic Workflow（唯一目标）**：GEE canonical 链保留为 audit/evidence 字段，**不进损失**。不加 GEE-chain 辅助损失（0.3 双目标提案被否——保持 H1 因果干净；B1+ 双目标留作第二层对照实验，暂不排期）。

### B1 GEE 阶段数据（本契约产物）

`outputs_v2/gee_b1_stage_data_v1/b1_gee_stage_train.jsonl`（服务器）：
- 128,447 行；RLE+cap3 后 token 1,746,809（raw 的 58.1%）
- 链长 median 8 / p90 26 / max 3,361（极端行后续训练时按 max_len 截断）
- run_cap 触发 15.63% 行（20,081）——交替刷屏被治理
- 字段：instruction / semantic_chain_raw / semantic_chain_rle（训练目标）/ gee_canonical_chain（audit-only）/ run 审计字段 / author_proxy / split

### 语义词汇表（37 类，冻结）

TEMPORAL_FILTER, SPATIAL_FILTER, ATTRIBUTE_FILTER, BAND_SELECT, BAND_ARITHMETIC, SPECTRAL_INDEX, THRESHOLD_LOGIC, MASKING, AGGREGATION, REGIONAL_STATS, CLASSIFICATION, ACCURACY_ASSESSMENT, SAMPLE_EXTRACTION, SPATIAL_CLIP, VECTOR_GEOMETRY, RASTER_TO_VECTOR, VECTOR_TO_RASTER, NEIGHBORHOOD, TERRAIN_DERIVED, CLOUD_PROCESS, COMPOSITE, SPATIAL_JOIN, RESAMPLE_REPROJECT, EXPORT_OUTPUT, ITERATIVE_APPLY, COLLECTION_MGMT, RASTER_LOAD, VECTOR_LOAD, GEOMETRY_DEFINE, AUX_VALUE（drop）, OTHER_UNMAPPED
（工具：`scripts/gee_route2_semantic_workflow_v1.py`，commit 32c88b8；语义映射为确定性规则表，无 LLM）

## P0-5 checkpoint selection（owner 裁定 2026-09-17）

**统一：QGIS dev-120 上的 primary task metric；dev loss 仅作诊断。** 四臂同一指标同一规则。第一轮若 dev scorer 未能稳定计算 operator/graph 指标，则统一退回 dev loss——但四臂仍必须一致，禁止逐臂选不同指标。

## P0-6 最终评价（沿用既有纪律）

final-100 + refusal-12（qgis-planner-benchmark v0.2.1），冻结 scorer 逐字导入，prediction lock → SHA 锁 → append-only ledger。test-111 评价放训练全部结束后一次性执行。

---

## 执行链（owner 定序）

```
P0 Freeze（本文件）
  ↓ B1 语义预处理（已完成：RLE + cap3）
  ↓ C0 / A1 / B1 三臂训练
  ↓ 统一 QGIS dev-120 checkpoint selection
  ↓ 统一 final-100 + refusal-12 终评（test-111 一次性）
  ↓ 迁移效果比较（回答 H1/H2）
  ↓ 依据结果设计 B2（配比由数据说话，不预拍）
```

## H1/H2（正式假设，冻结表述）

- **H1（Workflow Reasoning Transfer）**：大规模 GEE 工作流数据使模型学习平台无关的 GIS 任务分解、操作语义与工作流组合规律，并迁移到 QGIS 工作流生成。
- **H2（Target-platform Grounding）**：少量高质量 QGIS 数据（v2a-A）将上述能力 grounding 到 QGIS 算子、I/O 与图结构。

判读表：B1>C0 → H1 支持；A1≈C0 且 B1>C0 → 迁移来自 workflow supervision 而非领域知识；A1>C0 且 B1>A1 → 两种知识都有贡献。
