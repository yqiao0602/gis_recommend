# QGIS Processing 第二批 blocker replay v1

## 结论

本阶段对 757 条 unresolved Processing blocker 做了统一、可复现的源码重放：

- recovery：191
- split：179
- operator-resolution：387
- 源码 authority：757/757 SHA verified，0 source failure

产出 257 条预准入 candidate pool，确定性选出 250 条第二批候选；这 250 条不是训练
JSONL。四层去重后只有 50 条 canonical candidate，207 条为既有训练对或候选池内的
exact training-pair duplicate，全部保留为审计证据但不授予训练准入。

## Direct 复核

两条原先缺少 source replay 的 direct 均回 `/home/yll` 只读核验：

- `75d61f25ddb86ea9d5e4531d`：`reclassifybytable -> cliprasterbymasklayer`
- `a1c59ad27c1c3530ab2c4d50`：`mergevectorlayers -> dissolve -> multiparttosingleparts`

两条均通过 SHA、AST、调用位置、参数字典、依赖链和描述 fidelity；参数证据为
`verified_source_ast`。但两条都被既有 train-only authority 的 exact training pair
压制，不能重复导出训练行。

## Blocker 结果

### Recovery / split

- 原 191 recovery：274 local units，17 个 recovery 结构 eligible，13 条描述 fidelity
  通过；最终局部结构门禁仅保留 3 条 `local_structure_status=eligible`，另外 10 条
  final-local-structure deferred 已从候选池排除。
- 原 179 split：805 units（207 multi-step、598 single-step），9 个 multi-step
  eligible，7 条描述 fidelity 通过；另有 199 条无结构风险且描述通过的 single-step
  local candidate。
- 387 条 operator-resolution 解锁后再次进入 recovery/split：18 个 recovery parent
  产生的 3 条 fidelity-passed recovery unit 均为 final-local-structure deferred，候选数为
  0；14 个 split parent 产生 47 条 fidelity-passed single-step candidate。

所有候选均保留源码片段、调用位置、依赖边、L3 链和确定性中文描述；控制流、下游
低层变换、未解析输出和缺失 dependency 继续 fail-closed。

### Operator resolution

只启用 catalog-backed 的保守规则：

- `gdalogr:* -> gdal:*` 同 slug
- `grass:* -> grass7:*` 同 slug
- `sagang:* -> saga:*` 同 slug
- 4 个已审历史别名：`native:rastercalc`、`native:modelerrastercalc`、
  `native:voronoipolygons`、`qgis:fixeddistancebuffer`

387 条重放结果：fully normalized 89，其中完整 stable110 L3 mapping 54；partial
normalized 298，其中 288 仅有标准子集映射，不能称为完整链。action 分布为：
`auto_accept_candidate` 1、`defer_mapping` 45、`defer_operator_resolution` 288、
`recover_call_graph` 18、`split_subworkflow` 14、`review_api_sidecar` 6、
alignment exclusion 15。

## 候选与审核包

候选池按 lane：recovery multistep 3、split multistep 7、split single-step 199、
operator-resolution split single 47、operator-resolution direct 1，共 257。第二批选中
250 条，覆盖 100 个 normalized source authorities；其中 50 条 canonical、200 条
duplicate。候选汇聚层显式要求 recovery 的 `local_structure_status=eligible` 且
`local_structure_reasons=[]`，不再把 deferred recovery 送入审核包。

source-disjoint 审核包 100 条，calibration/holdout 各 50，authority overlap=0；人工
字段全部留空。所有 `training_row_emitted=false`、validation/test=false、production
merge=not_granted，未调用 LLM、未训练。

## 权威产物

- `summary_v1.json`
- `blocker_source_replay_v1.jsonl`（757 行）
- `operator_resolution_v1.jsonl`（387 行）
- `operator_direct_descriptions_v1.jsonl`（1 行）
- `direct_source_replay_v1.jsonl`（2 行）
- `candidate_pool_v1.jsonl`（270 行）
- `candidate_batch_v1.jsonl`（250 行）
- `source_disjoint_review_v1.jsonl/.csv`（100 行）
- `hash_ledger_v1.json`

下一步是先审核 100 条 source-disjoint 包，只有边界、operator、L3、描述和去重门禁
均通过的 canonical 行才进入下一批 train-only JSONL；当前不把 250 条候选直接当训练集。
