# QGIS Processing custom-scope corrected replay v1

日期：2026-08-01

## 结论

custom implementation 全池 replay 已使用修正后的 stable110 组合映射重放。冻结输入包含
8,474 条 manifest 记录、8,471 个唯一源码，其中 8,176 条通过源码校验；共识别 97 个
implementation variant。完整展开 variant 从 7 个增加到 9 个，scope parent 从 7 个增加到
9 个，形成 3 条 scope candidate：2 条 canonical、1 条源码区域重复。

质量门禁后只导出 1 条新的 train-only 行。另 1 条 canonical `deletecolumn` 缺少
`mapping_complete` 和 `parameter_evidence_status`，继续 fail-closed；重复行不重复导出。

## 修正内容

组合映射由 153 个 operator 构成，并执行三项语义校正：

- 补入已审定的 `native:extractwithindistance -> L3_02_06_03`。
- 撤销错误的 `native:ruggednessindex` 映射。
- 撤销错误的 `qgis:basicstatisticsforfields` 映射。

该修正不会增加 stable110 词表，仅修复 existing-L3 authority 的装载和语义污染。

## 新增训练行

新增行 `custom_52a95961538dd08215978c85` 来自 `script:filterstructures` 的完整 6 步
Processing DAG：

```text
native:lineintersections
-> native:mergevectorlayers
-> native:buffer
-> native:dissolve
-> native:centroids
-> native:extractwithindistance
```

该行通过 source SHA、Python AST、逐步字面量 `processing.run()` 与 call-span replay，映射到
stable110 后导出为 train-only。JSONL SHA256 为
`45741071fe8ebf16a7da72b7352b991b8f4c2f44e596397d50c0a50f30f275e0`。
真实 V4 loader/weighted-loss/backward 覆盖 1/1，batch `[1,100]`，loss 和 gradient
有限；未训练、未写 checkpoint、未合并生产数据、未调用 LLM。

## 当前口径

两条错误映射对应的旧训练行已撤销，本轮净变化为 `-2 + 1 = -1`：

```text
旧口径 178 -> 校正后 176 -> custom-scope 新增 1 -> 当前 Processing 177
```

因此距 200 条还差 23 条。旧的 178/22 口径已 superseded。

## 下一步

复用同一条确定性流水线处理剩余高频 custom implementation family：implementation hash
聚类、完整内部 Processing DAG、任务边界、stable110 精确映射、确定性描述、当前全 authority
去重、源码 replay、train-only export 和 V4 smoke。caller-to-callee 参数传播已完成 census 且
安全恢复为 0，不再作为生产主线。

