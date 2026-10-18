# A/B/C 样本清单 V1（2026-10-18，基于已审计样本）

- **范围**：已审计 221 脚本/行（Q2 117 对）；全量 128,447 行中其余行 **未审计、未准入**。
- **原则**：A 保留原始序列监督；B 应用治理规则；C 在 B 基础上改变表示；
  三组逐一对应，不比较总样本量而不报构成。
- **关键限制**：合格训练样本仅 **113 行**（A/C1/M），见 `B_TRACK_FULL_CORPUS_INVENTORY_V1.md` §3。

## 1. 组定义与样本数（新划分 V2）

| 组 | 数据 | train | val | test | 说明 |
| --- | --- | --- | --- | --- | --- |
| **A_full** | 全量原始序列监督 | 102,731 | 12,835 | 12,881 | 现有基线，含未审计行 |
| **A_matched** | 与 B 同任务、同规模的原始序列监督 | **113** | 21 | 21 | 用于同规模对照，消除样本量混杂 |
| **B** | 审核后序列监督（A/C1/M） | **113** | 21 | 21 | Q1/Q2 排除；C2 待修复，暂不入 |
| **C** | 双层表示监督（与 B 同任务集） | **113** | 21 | 21 | 仅表示改变；L1/L2/L4 |

- **推荐主比较**：A_matched − 原始基线用于**治理效应**（同规模），A_full 仅作规模参考；
  C − B 为双层表示增量。若 owner 要求 B−A 使用 A_full，则必须声明该比较包含样本量差异，
  不得归因于治理规则（见协议 §1）。
- **排除清单**：Q1 缺实 10、Q2 不可判 4；C2 欠描述 52（待证据化修复后另批纳入）。

## 2. 逐样本字段（清单 JSON）

每条记录包含：
`task_group_id`（划分组件根）、`sample_id`（script id）、`pair_ids`、`source_split`（原池 split）、
`split_v2`（t/v/s）、`admission_bucket`、`admission_status`、`exclusion_reason`、
`sequence_length`（RLE 步数）、`representation_version`（A=raw_seq_v1；B=curated_seq_v1；
C=two_layer_v1）、`provenance`（Q2 判读记录）。

- 机器可读：`B_TRACK_ABC_SAMPLE_LISTS_V1.json`（当前仅含 221 条已审计样本的元数据；
  全量未审计行不生成训练样本）。
- A_matched/B/C 使用**同一 sample_id 集合**；C 的 `representation_version` 不同，任务集不变。

## 3. 禁止事项

1. 不得把未审计行默认纳入 B/C；
2. 不得为对齐 A/B/C 样本量而删除合格样本或纳入不合格样本；
3. 不得用测试集结果反向调整治理规则后继续用同一测试集；
4. 不得把 `split` 归属当作准入（split 是全量划分，准入是审计结论）。

## 4. 当前状态

- 样本清单 V1 完成（221 条元数据 + 113 条合格子集）；
- 全量 B/C 训练集**未构建**，等待 owner 在 S1/S2/S3 中选择扩样策略；
- 第 6 项状态 = `audited_subset_ready_full_corpus_blocked`.
