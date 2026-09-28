# QGIS Asset Miner v1 — full-pool inventory

全量 47,852 条 QGIS 原始 manifest 已通过分片、checkpoint 和确定性合并完成。源码
均直接从服务器 `/home/yll` 读取，按 raw-byte SHA 校验；本轮不映射 L3、不生成
训练行、不修改 authority。

## Result

| 指标 | 数量 |
|---|---:|
| manifest rows | 47,852 |
| parsed | 47,542 |
| source unresolved | 310 |
| Processing workflow candidate | 1,236 |
| Processing implementation candidate | 1,088 |
| Processing operator candidate | 591 |
| Dynamic recovery candidate | 496 |
| API semantic-unit candidate | 1,874 |
| API pattern candidate | 6,215 |
| API plumbing evidence | 12,407 |
| parsed but unresolved/no known signature | 23,945 |

按 manifest pool 统计时，Processing pool 仍包含部分 API-shaped implementation：

- Processing pool：8,466 rows，parsed=8,171，dynamic Processing calls=1,384；
  workflow=1,210，implementation=1,088，operator=526，dynamic=489。
- API pool：39,386 rows，parsed=39,371，dynamic Processing calls=7；
  API semantic-unit=1,821，pattern=5,108，plumbing=10,166。

## Interpretation

这次首次给出了“47,852 → 47,542 parsed assets”的完整发现基线。它不是 47,542
条可训练样本：其中 23,945 条尚未出现已知 GIS signature，12,407 条主要是 plumbing，
496 条需要动态 operator recovery；所有资产仍需按类型进入后续语义标准化、L3、I/O、
任务文本和去重流程。

服务器结果目录：`/home/qy/system_redesign/diagnostics/qgis_asset_miner_full_sharded_v1/`。
其中 `qgis_asset_miner_sharded_v1.jsonl` 是完整 ledger，`sharded_summary_v1.json`
和 `hash_ledger_v1.json` 是汇总与哈希证明。
