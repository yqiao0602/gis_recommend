# Phase 0 前置确认 A：任务文本语言分布（M1 增强路线）

日期：2026-09-11
性质：只读诊断；零训练、零推理（bert tokenizer 仅做编码统计）；未触碰任何冻结产物
输入（SHA256 见 `language_stats_v1.json`）：
- `docs/reports/paper_v1_supervision/paper_v1_supervision_manifest.jsonl`（8,912 行，v2 权威）
- `docs/reports/qgis_planner_eval_v1/materialized/{dev_20,final_100,refusal_12}.tasks.jsonl`（benchmark v0.2.1 物化输入）

分类规则（样本级，在字母类内容上判定，对应 tokenizer 覆盖实际发生的位置）：`cjk_ratio = n_cjk / (n_cjk + n_latin)`；≥0.8 中文、≤0.2 英文、之间混合；空白文本 = empty；无字母 = other。

## 主表

| Dataset           | N | 中文 | 英文 | 中英混合 | 其他 | 中文占比 |
| ----------------- | --: | --: | --: | --: | --: | --: |
| paper_v1 train    | 8,817 | 171 | 8,313 | 332 | 1 | 1.9% |
| paper_v1 val      |    49 |   2 |    44 |   3 |   0 | 4.1% |
| paper_v1 test     |    46 |   2 |    42 |   2 |   0 | 4.3% |
| benchmark dev     |    20 |   0 |    20 |   0 |   0 | 0% |
| benchmark final   |   100 |   0 |   100 |   0 |   0 | 0% |
| benchmark refusal |    12 |   0 |    12 |   0 |   0 | 0% |

平台分解（paper_v1 内部）：

| 子集 | N | 中文 | 英文 | 混合 | 其他 | 中文+混合占比 |
|---|---:|---:|---:|---:|---:|---:|
| train [GEE] | 8,201 | 0 | 8,201 | 0 | 0 | 0% |
| train [QGIS] | 616 | 171 | 112 | 332 | 1 | **81.7%** |
| val [QGIS] | 8 | 2 | 3 | 3 | 0 | 62.5% |
| test [QGIS] | 5 | 2 | 1 | 2 | 0 | 80.0% |

## 补充统计

**字符级语言占比**：paper train 全体 CJK 字符均值 3.6%；其中 QGIS train 子集 CJK 字符均值 **52.1%**。benchmark 三个 split CJK 字符占比均为 **0.0%**。

**文本长度（字符）**：

| Dataset | mean | median | P95 |
|---|---:|---:|---:|
| paper train | 315.2 | 313 | 454 |
| benchmark final | 152.0 | 120.5 | 337 |
| benchmark dev | 144.6 | 141 | 234 |
| benchmark refusal | 101.4 | 98.5 | 123 |

（次要观察：benchmark 任务文本长度约为训练文本的一半，属长度分布差异，非语言问题，记录备考。）

**混合样本示例**（QGIS train，中文模板 + 英文字段名，共 332 条）：
- `向现有矢量图层新增字段 change_detected，按已验证的条件分支逐要素计算并写入该字段。`
- `向现有矢量图层新增字段 calc、len_test_m，按已定义的 QGIS 表达式逐要素计算并写入相应字段。`

**M1 encoder 实际输入覆盖（bert-base-uncased tokenize task_text，无 prompt 模板词）**：

| Dataset | 样本 UNK 比例 mean | median | 聚合 UNK 占比 | UNK≥50% 样本数 |
|---|---:|---:|---:|---:|
| train [GEE] | 0.000 | 0.000 | 0.000 | 0/8,201 |
| train [QGIS] | **0.544** | **0.657** | **0.517** | **426/616 (69.2%)** |
| val（全体 49） | 0.066 | 0.000 | 0.036 | 4（即 QGIS 的 2 中文+3 混合中 4 条） |
| benchmark dev / final / refusal | 0.000 | 0.000 | 0.000 | 0/132 |

## 三个结论

**Q1：M1 的输入到底主要是什么语言？**
按行数 94.3% 英文（8,313/8,817），聚合 CJK 字符仅 3.6%——整体是英文任务语言。但语言分布高度按平台分裂：GEE 8,201 行 100% 英文、0 UNK；QGIS 616 行中 81.7% 为中文或混合，对 M1 encoder 的样本级 UNK 比例均值 0.544，**69.2%（426/616）的 QGIS 训练行对 encoder 至少一半 token 不可读**，QGIS 子集聚合 UNK 占比 51.7%。M1 有效可读的 QGIS 监督约只有 190 行。

**Q2：benchmark 的语言分布是否明显不同于 paper_v1 train？**
不构成输入语言偏移：benchmark dev/final/refusal 共 132 条**全部英文、UNK 比例 0.0**，与 paper train 的主体（GEE 英文）同语言；中文只存在于训练集内部的 QGIS 子集。benchmark 比 paper train 更短（median 120.5 vs 313 字符）是唯一显著分布差，属长度而非语言。

**Q3：English BERT 是否构成一个必须单独报告的 confounder？**
**是，但方向与预设相反，且比预设更重要**：
1. **推理侧不构成混杂**——benchmark 任务 M1 全部可读（0 UNK），M1 的 OOD 塌缩发生在完全可读的英文输入上，不能归因于输入语言不匹配；
2. **训练侧构成真实且可量化的不对称**——M3（Qwen 双语）原生消费全部 8,817 行，M1 实际可读约 8,391 行（8,201 GEE + ~190 QGIS）；损失集中在目标平台知识本身（QGIS 监督 69% 对 M1 半盲）。这在与 M3 的比较中必须作为独立混杂列出（规模、tokenizer 语言覆盖、task_type 之外的新一项）。

## 对 M1-R2 与论文表述的含义

- **M1-R1 塌缩的候选解释收窄**：排除"benchmark 输入语言不匹配"后，剩余候选为 task_type OOD（前置确认 B 量化）与语言/领域先验不足（M1-R2 量化）。
- **M1-R2 的 DAPT recipe 语言池**：M1 只能消费英文池——D3 源码、D4/D5 中任何中文对 M1 decoder CLM 无效；spec §7.3 的语言分池设计由此获得实测依据。
- **M1-R2 无法修复 QGIS 监督缺口**：该缺口是架构性的（英文 BERT），修复需换 encoder，超出 R2 范围；论文应作为 M1 路线 limitation 单列，并在 M1/M3 对比表中报告"有效可读监督行数"（8,391 vs 8,817）。
- **M1 vs M3 混杂清单更新为五项**：规模（117M vs 9B）、语言覆盖（encoder 对 QGIS 子集）、task_type 条件（B 待量化）、预训练方式、序列控制失败模式（M3 侧 runaway，见 7f28fa1）。

## 复现

```
python scripts/analyze_task_text_language_v1.py
# 产物：docs/reports/m1_phase0_precheck_a_language_v1/language_stats_v1.json（含输入 SHA256）
```
