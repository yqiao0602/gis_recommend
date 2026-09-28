# GEE 完整工作流扩展与分层抽样门禁

日期：2026-07-31

## 结论

同一 complete-workflow 确定性转换器已覆盖剩余 126 条 canonical candidate。43 条因源码与已审核
包重叠进入 sidecar，83 条来自 50 个独立源码并通过 semantic、stable-94 mapping、dedup 和 V4
长度门禁。83 条当前只是 `pending_sampling_audit` proposal；本阶段新增训练行仍为 0。

## 生产统计

- canonical candidate：176
- reviewed identity：50
- remaining：126
- reviewed-source overlap：43
- proposal eligible：83
- semantic failure / duplicate / length defer：0 / 0 / 0
- eligible source authority：50
- audit sample：30
- training rows emitted：0

六层源码代表支持为：external/dynamic 22、long/repeated 5、multi-dataset/private 9、
no-temporal 7、other 1、spatial-omission 6。largest-remainder 配额为 `13/3/5/4/1/4`。

## 证据与门禁

`scripts/build_gee_complete_workflow_expansion_batch.py` 固定五类输入 authority SHA 和完整计数，
每条 remaining identity 只能进入一个终态。30 个抽样源码均在只读 `/home/yll/GEE/Data` 下验证
字节 SHA，审核片段只从 fact-backed source location 提取且最多 80 行。人工字段未预填。

`scripts/evaluate_gee_complete_workflow_expansion_audit.py` 绑定原始 audit、source manifest、既有
reviewed packet 和 expansion hash ledger。通过门槛为：30 条全部审核、point precision>=0.95、
Wilson 95% lower>=0.85、critical chain/L3/fact hallucination failure=0。evaluator 只决定是否允许
更大 source-disjoint replay，不授予 train-only、validation、test 或 production merge。

## 可复现性

- 主包：`/home/qy/system_redesign/diagnostics/gee_complete_workflow_expansion_v1_20260731_a`
- 双跑：`/home/qy/system_redesign/diagnostics/gee_complete_workflow_expansion_v1_20260731_b`
- 本机包：`docs/reports/gee_complete_workflow_expansion_v1/`
- A/B 全目录逐字节一致。
- audit JSONL SHA256：`c629543fe56fe1d3462466cebb0fbd90a8d25174df9cb33e8cdbb1704bf8ee8d`
- source manifest SHA256：`e21f07c6cf3880c993b50e26c49d6b2367f532f39efe87a8def3a96b8d5c42f3`
- expansion hash ledger SHA256：`276a9caecbe602ecdd4c7be4b18883f5c23f68d81c6ea82310c0bf9534f64561`

## 下一步

只审核冻结的 `audit_sample_30.csv/jsonl`。发现问题时修复通用确定性规则并对 126 条全量重放，
不对 83 条 proposal 逐条修补。只有 evaluator 通过后，才冻结更大的 source-disjoint selection。
