# QGIS 首批 train-only 交付包 v1

## 交付结论

从 129 条已经通过各自来源门禁的 QGIS authority 中，确定性分层选出 50 条，形成统一
schema 的首批 train-only JSONL。选择器优先覆盖来源池、L3 序列和算子序列；没有逐条重新
审核，也没有调用 LLM 或运行训练。

## 统计

| 指标 | 数量 |
|---|---:|
| authority 输入 | 129 |
| 交付行 | 50 |
| 来源池 | 6 |
| 独立 source SHA | 50 |
| 独立 source region | 50 |
| 独立 call graph | 50 |
| 独立 operator sequence | 50 |
| 独立 L3 sequence | 50 |
| 覆盖 L3 code | 41 |
| 最大算子链长度 | 7 |

首批 50 条中 10 条为显式 `verified_sha256`，1 条为
`carried_forward_verified_normalized_source_body`，39 条为既有
`source_reviewed_evidence`。后者保留原始证据状态，没有伪装成服务器 replay；下一轮批量
source replay 将单独升级该字段。

## 训练路径验证

- V4 `TaskConditionedL3DatasetV4`：50/50 rows loaded。
- weighted sequence cross entropy：finite。
- backward gradient：finite。
- batch：7（8, 8, 8, 8, 8, 8, 2）。
- checkpoint：未写入。
- training run：未运行。
- validation/test：全部 false。
- production merge：`not_granted`。

## 文件

- `qgis_train_delivery_50_v1.jsonl`
- `selection_ledger_v1.jsonl`
- `summary_v1.json`
- `loader_loss_smoke_v1.json`
- `hash_ledger_v1.json`
