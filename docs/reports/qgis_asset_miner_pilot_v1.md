# QGIS Asset Miner v1 — source-disjoint pilot

本轮首次运行统一的 `QGIS Asset Miner v1`，输入仍是服务器原始 Processing/API
manifest，源码从 `/home/yll` 读取并按 raw-byte SHA 校验。输出只写服务器
diagnostics 目录，不映射 L3、不生成训练行。

## Pilot result

每个池取 manifest 前 100 条，共 200 条：

| 指标 | 数量 |
|---|---:|
| parsed | 194 |
| source unresolved | 6 |
| Processing workflow candidate | 11 |
| Processing implementation candidate | 15 |
| Processing operator candidate | 7 |
| Dynamic recovery candidate | 8 |
| API semantic-unit candidate | 9 |
| API pattern candidate | 16 |
| API plumbing evidence | 56 |
| 无已知签名的 parsed source | 78 |

Processing 池内共识别 15 个 dynamic Processing calls；API manifest 因历史上缺少
`source_root_id`，已采用最具体的 `/home/yll` ancestor 解析，避免嵌套 source root
造成的假 unresolved。

## Interpretation

这是资产发现量，不是训练准入量。当前 194 条 parsed source 已证明统一中间格式能
同时承载 Processing、implementation、dynamic、API semantic、API pattern 和
plumbing 六类资产；其中 78 条 parsed 但没有已知签名，仍应保留为 unresolved/deferred，
不能猜测算子。

训练行：0；L3 mapping：未尝试；production merge：`not_granted`。

服务器完整 ledger：`/home/qy/system_redesign/diagnostics/qgis_asset_miner_pilot_v1/`。
本地摘要：`qgis_asset_miner_pilot_v1_summary_v1.json`。

## Full-pool execution note

尝试直接扫描 47,852 条全池时，旧版逐行路径解析在服务器上超过 10 分钟且没有
增量输出，已停止该进程；这暴露了 v1 需要批处理/增量 checkpoint，而不是质量门禁问题。
当前不把 full-pool 数量外推为结果。后续应按 source-root 分片运行，每片写入独立
ledger，再做确定性合并。

为解决该问题，新增 `scripts/run_qgis_asset_miner_sharded.py`：按 pool 和固定
`shard_size` 切分 manifest，每片写 `DONE.json` checkpoint，合并时只消费已完成
分片。其合并行为已由单元测试覆盖。

服务器端到端 tiny 验证（每池 10 条、共 20 条）成功完成：2 个 shard 均写入
`DONE.json`，合并得到 20 行（parsed=19、source_unresolved=1），训练行仍为 0。
250 条分片因 `/home/yll` NFS 逐文件读取超过 SSH 长连接时限，未将超时批次计入
产量；后续应使用后台任务或更小分片并从 checkpoint 续跑。
