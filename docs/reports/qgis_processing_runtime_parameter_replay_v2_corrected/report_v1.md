# QGIS Processing runtime-parameter semantic correction v1

日期：2026-08-01

## 结论

对 runtime-parameter 训练增量执行语义复核后，撤销 2 条错误映射行：

- `native:ruggednessindex`
- `qgis:basicstatisticsforfields`

两者都不能由当前 stable110 existing-L3 契约精确表示。修正版输入 6 条，保留 4 条，撤销
2 条；修正后的 train-only JSONL 仍保持 validation/test=false、production merge 未授权。

## 验证

- revocation ledger 明确记录 2 个 operator 和对应行。
- corrected train-only 行数为 4。
- 真实 V4 loader/weighted-loss/backward 覆盖 4/4，loss/gradient finite。
- checkpoint=false，training=false，未调用 LLM。

该撤销把当时的 Processing 178 校正为 176；后续 corrected custom-scope replay 新增 1 条，
所以当前权威总数为 177，距 200 还差 23。

