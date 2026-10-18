# S1 组件抽样清单 V1（2026-10-18）

- **产物**：`B_TRACK_S1_SAMPLING_LIST_V1.json`（7,562 组件，逐组件含 split/层/旗标/配额/顺序）。
- **可复现**：seed 20261018；输入池 SHA `09c37104…`；清单 SHA `0d95ab17…`；
  脚本 `scripts/b_track_s1_sampling_v1.py`。
- **配额**：train 6,133 / val 758 / test 671；**容量缺口 0**（各层均满足配额）。
- **分层实际分布**：low 2,282 / mid 1,979 / singleton 1,858 / high 1,443；
  medium 3,751 / short 2,648 / long 1,163。
- **风险旗标（原始定义，待校准）**：ui_scaffold 6,849（90.6%）、duplicate_lines 5,410
  （71.5%）、indirect_asset 4,169（55.1%）、empty_rle 1。
- **注意**：清单是**审计计划**，不是准入结果；风险旗标仅为抽样分层参考。
