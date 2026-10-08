# Blueprint v2 Preflight 报告（v1，2026-10-04，CPU-only，未训练）

> 依据 owner 裁定（`26b5c5b`）：Schema v2 定稿修订 + E1-E4 preflight + 可学习性判别。
> 脚本 `blueprint_v2_preflight_v1.py`；Gold v2（修订版）`blueprint_v2_gold_v2.jsonl`；
> 弱标注人工抽样 `04_DIAG_WORK/iteration_hint_review_sample_v1.jsonl`（396 条）。

## 1. Schema v2 定稿实现（按 owner 修订）

- `stages`：语义级 pre-RLE 极大游程序列 `{seq, family, repeat}`（保留）；
- **`repetition_groups`**（原 loop_groups 更名）：`{stage_seq, family, repeat, iteration_hint[]}`；
- `iteration_hint`：**关键词弱标注多标签**（per_band/per_class/per_year/per_feature/generic_each），
  无命中 → **`["unspecified"]`（合法状态，≠ no repetition）**；无 LLM 标注。

## 2. E1-E4 preflight（含 gold-vs-gold 自洽测试）

| 项 | 结果 |
|---|---|
| E1 Ordered Stage-F1 | 可计算 ✓；gold-vs-gold = 1.0；**旋转序列罚至 0.75**（顺序敏感性的自证） |
| E2 Repetition-group F1 | 可计算 ✓；构造性唯一确定（runs 即结构）；**双方均无 repetition → 1.0** 约定已修 |
| E3 hint 标注 | 396 条分层抽样（33 种 hint 模式 × 12 条）已生成，**待 owner 人工验证 precision** |
| E4 repeat bias | 可计算，diagnostic 位 ✓ |
| 与原始链对齐 | 100%（构造性） |

（过程修正两处：E2 空集约定；hint 弱标注曾误读 V22 行字段，已改用 SRC instruction 重建。）

## 3. 关键判别：v2 是"可学习的 Planner 目标"还是"原始链全量转储"？——**PASS**

TF-IDF 线性探针（80/20，seed 20260924，n=37,044）：

| 探针 | macro AUC | min AUC | 含义 |
|---|---|---|---|
| **v2 语义 stage 集合**（30 类） | **0.922** | 0.845 | 更细粒度**不是噪声** |
| v1 plan family 集合（19 类） | 0.915 | 0.856 | （R3-CD-3 复测一致） |
| **v2 repetition-presence**（哪些 family 重复） | **0.940** | 0.883 | **v2 独有信号，全场最强** |
| iteration_hint（弱标注，6 类） | 0.968 | 0.935 | 标签自洽/可恢复（弱标注来源=关键词，语义质量待人工验证） |

**判读**：v2 语义粒度的可预测性与 v1 相当（0.922 vs 0.915），且 v2 独有的
repetition-presence 信号（0.940）是所有目标中最强的——
**v2 不是"更完整地保存原始链"，而是"Task 可支持的可学习结构表示"**。
Planner-v2 SFT 的信息前提成立。

## 4. 待 owner 完成的唯一人工环节

**396 条弱标注抽样的人工 precision 验证**（`iteration_hint_review_sample_v1.jsonl`：
每行含 task 文本 + repetition_groups + 弱标注 hint）——验证关键词规则是否
把正确的迭代维度贴到了正确的 repetition group 上。若 precision 高（≥0.8-0.9），
E3 口径即可冻结，进入 Planner-v2 smoke 设计。

## 5. 状态

零训练、零 GPU、冻结物未动（Stage-1 v2_2 与现有 gate 继续冻结）。
Planner-v2 SFT 暂缓至：人工验证通过 + owner 放行。
