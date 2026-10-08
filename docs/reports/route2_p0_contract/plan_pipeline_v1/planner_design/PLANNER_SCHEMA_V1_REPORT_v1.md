# Planner Schema v1 设计 + Gold Blueprint 构造验证报告（v1，2026-10-02，CPU-only）

> 依据 owner 裁定（`5b7d9de`）：Planner→Serializer 最小实验链步骤 ①②③（本回合）；
> ④ 小规模 Planner SFT 待 owner 放行。脚本 `build_planner_blueprints_v1.py`。

## 1. Schema v1（最小定义，owner 方向的落地）

```json
{
  "families": ["RASTER_LOAD", "SPATIAL_FILTER", "TEMPORAL_FILTER", "AGGREGATION"],
  "counts":   {"RASTER_LOAD": 2, "SPATIAL_FILTER": 1, "TEMPORAL_FILTER": 1, "AGGREGATION": 2},
  "length":   6
}
```

- `families`：按 gold **首次出现顺序**的去重列表；
- `counts`：每 family 的重复次数（R3-CD-4 已证明计数分配是 oracle 下 15% 缺口的来源——**必须进 schema**）；
- `length`：总步数（= Σcounts，供 Planner 的长度头/预算约束）。
- **排除项（v1 刻意不做）**：参数、自然语言 Plan 文本、QGIS、DAG——与 owner 的"第一版不要 Plan 文本"一致。

## 2. Serializer v1（规则程序，非模型）

按 `families` 首现顺序展开 `counts` → family 序列。
（更完整的渲染到 Plan 文本层留给后续版本；最小实验的对比口径是 family 多重集 bag-F1，
与冻结 gate 一致。）

## 3. 验证结果（全量 37,044 核心行）

| 验证 | 结果 | 含义 |
|---|---|---|
| **V1** oracle blueprint → serializer → bag-F1 | **1.0000**（37,044/37,044） | blueprint 在冻结 bag 口径下**无损**；R3-CD-4 的 15% 计数缺口被 `counts` 字段补齐——**schema 必须含 counts 得到确认** |
| **V2** 展开顺序 == gold 顺序的比例 | **44.1%** | blueprint 是**保 bag、损顺序**的表示——当前冻结 gate（bag 口径）完全兼容；**未来顺序敏感口径需要 schema 扩展**（如 ordered stages / dependency pairs），已登记 |
| **V3** 同多重集的平均可排列数 | 3.7×10³¹（n≤50 子集） | multiset→顺序本质上一对多；顺序信息只能来自数据本身或额外监督 |
| **V4** 监督目标大小 | blueprint **14.4 词** vs gold target **249.3 词**（**17× 压缩**） | Planner 的学习目标极小且与 Task 可预测成分（R3-CD-3/4）直接对齐 |

## 4. 数据产品（就绪，待 owner 放行 ④）

- `04_DIAG_WORK/planner_gold_blueprints_v1.jsonl`（37,044 行，32.5MB，本地）：
  `{source_row_id, task, blueprint, gold_families}` —— Gold blueprint 训练数据已备好。
- ④ 小规模 Planner SFT 需要：新训练脚本（blueprint 目标格式，⑦ 外代码变更，需 owner 批准设计）
  + GPU 窗口。建议规模：LoRA、blueprint 目标 ~14 词/行 → 训练时长预计远小于全 Plan SFT。

## 5. 风险与边界

1. **V2 的 44% 顺序保真**：若未来把顺序敏感指标转正，blueprint v1 不够——届时 schema v2
   需要携带"阶段顺序约束"（例如 stage-level DAG）。这是设计层预留位，不阻塞当前最小实验。
2. blueprint 的 label 来自池子结构化 plan（自动分层产物），继承上游全部已知限制
   （R3-B-1/CD-2 登记）。
3. 本报告只覆盖 ①②③；④-⑥ 的实验设计（训练配置、对比口径）待 owner 批准后另立登记。
