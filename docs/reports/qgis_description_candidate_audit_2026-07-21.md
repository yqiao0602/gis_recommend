# QGIS 现有描述候选可用性审计（2026-07-21）

## 目标与边界

审计 `/home/yll/GEE/描述性知识抽取qgis_chain_selected_script/facts_summary1000.csv` 的 20,428 条现有描述，判断是否能直接形成约 10,000 条 stable-94 QGIS/L3 训练样本。

本轮不调用 LLM、不生成训练数据、不修改 `/home/yll`。输入为 Phase 1 的 facts-artifact 关联、QGIS `steps.csv`、冻结 stable-94 ID authority 和现有 operator crosswalk；结果只写 `/home/qy`。

## 审计门禁

一条多步候选必须同时满足：

1. 描述和任务名非空且不是占位文本。
2. facts 能通过唯一 extraction group，或多个 group 的 AST 字节 hash 完全一致而被证明为同源镜像。
3. 不属于 `L3_support_modules`。
4. 至少两个字面量 QGIS Processing operator ID。
5. 链长不超过 15。
6. 所有 operator 均能映射到冻结 stable-94 L3。
7. `statement_index` 可确定顺序；并列或非单调顺序进入修复池。

描述格式门禁只证明字段完整，不能代替代码-描述语义忠实性人工审核。

## 结果

| 口径 | 数量 | 解释 |
|---|---:|---|
| 现有描述 | 20,428 | 全部通过非空/长度/占位文本检查 |
| 能关联抽取产物 | 20,413 | 15 条缺失 |
| 原一对一 group | 18,526 | Phase 1 原始口径 |
| AST hash 同源镜像消歧 | 1,887 | 多 group AST 内容完全一致，可合并为同一来源 |
| 含至少一个 Processing 算子 | 1,365 | 其余主要是低层 API、支持逻辑或无显式 Processing 调用 |
| 多步 Processing | 1,356 | 至少两个算子 |
| stable-94 结构完整多步候选 | 181 | 81 条顺序确定，100 条需恢复顺序 |
| stable-94 映射不完整 | 1,162 | 当前最大显式 Processing 修复池 |
| 单步候选 | 3 | 不计入多步 workflow 主训练集 |
| 超长链 | 9 | 超过 15 步，需拆分或单独审核 |
| 无字面量 Processing operator | 19,048 | 不能直接由现有 operator chain 路线训练 |
| support 排除 | 10 | 明确不作为任务工作流 |

181 条结构完整候选中，81 条只是“机器门禁可直接进入人工审核”，并非已经授予训练准入。100 条需要回到源码或 AST 恢复可靠顺序。

## 来源分布

- `QGIS_Model_Tutorial_Workflows` 的 251 条描述关联中：14 条顺序确定、20 条需恢复顺序、213 条映射不完整、3 条超长、1 条无字面量 Processing。
- `qgis_processing_chained_workflows` 的 1,122 条描述关联中：67 条顺序确定、80 条需恢复顺序、949 条映射不完整、6 条超长、3 条单步、17 条无字面量 Processing。
- L1/L2/strict 当前被选中的描述关联基本没有字面量 Processing operator，主要属于低层 API/自定义实现路线。

## 主要映射缺口

影响记录最多的 stable-94 缺口包括：

- `native:reprojectlayer`：297
- `native:fixgeometries`：261
- `gdal:rasterize`：132
- `native:joinattributestable`：131
- `gdal:polygonize`：118
- `qgis:fieldcalculator`：97
- `native:createspatialindex`：91

这些缺口不能仅靠字符串补表。部分属于 stable-94 未覆盖能力，需要逐项决定 `direct/composite/api_pattern/approximate/unsupported/unresolved`，或保留到实验性 taxonomy，而不是伪造 94-L3 标签。

## 对“一万条先训练”的结论

当前现有描述不能直接形成约一万条可靠训练样本：

- 当前高证据多步结构池只有 181 条。
- 即使 1,162 条映射不完整记录全部修复，显式 Processing 总池仍只有约 1,300 条量级。
- 历史 direct-API semantic aggregation 得到的 5,107 条只是 `eligible`，不是训练准入。35 条 holdout 人工审核只有 9 条完整正确，item precision 为 59.6%，状态为 `blocked_pending_extractor_v2`。

因此现在不启动训练。下一步应并行推进：

1. 人工审核 81 条顺序确定候选，并修复 100 条顺序问题。
2. 对 1,162 条做 stable-94 能力判定和 operator mapping 缺口分层。
3. 从 80,998 份强 QGIS 信号唯一源码中继续筛显式 Processing 链；链验证后再生成描述。
4. 低层 API 记录等 extractor v2 达到预声明人工精度门禁后再扩量。

## 可复现产物

- 结果目录：`/home/qy/system_redesign/outputs_v2/qgis_pilot/description_candidate_audit_v4_stable94`
- `candidate_audit.jsonl` SHA256：`851aa96000ef8930ac665be64ed9e72968c2c08338a0bf45b601d154df2bac35`
- `summary.json` SHA256：`3691472cf5d8129f84f5edd6acc388e33f4ba2eb4418655ac11fc84e7fcd174a`
- frozen stable-94 authority SHA256：`005699dfd438e966cda28db8891795a07b9867856951de022cd8704c6e6a4558`
- 审计工具：`scripts/audit_qgis_description_candidates.py`、`src/gis_recommend/data/qgis_description_audit.py`

