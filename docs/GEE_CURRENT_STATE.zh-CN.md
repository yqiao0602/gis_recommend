# GEE 当前状态

最后更新：2026-09-02

## 职责与目标

本工作区只负责 **GEE 数据处理**，固定目标是把现有 GEE 语料转换为可规模推广的高质量完整
工作流训练集；不修改 QGIS 数据、评测集或模型训练。

训练行必须覆盖完整的 output-relevant workflow DAG。历史 `mean -> clip`、11,397 行和局部链包
只保留为规则校准证据，不代表当前生产产量。

## 最新已验证状态

- Batch8 v8.8 band-alias 修复已在受控快照
  `code_snapshot_v8_8_band_alias_rulefix_authority` 上完成重放；新增规则只解析
  可证明的同作用域字面数组别名 `select(bands)`，动态或重绑定选择仍 fail-closed。
  服务器单元测试 33/33 通过。
- 17,585 个 source 的 DAG A/B 逐字节一致（AST 成功 17,567、失败 18；source status 为
  passed=5,090、partial=520、fail-closed=11,957）。Fidelity A/B 逐字节一致：39,110
  workflows、11,342 passed、320 exact duplicate、27,448 fail-closed、5,214 个唯一 accepted source。
- 已关闭此前审核发现的 `data30000/script_22112.txt` 漏检：`bandas=[B1..B7]` 别名后请求
  `select('ndvi')` 现在命中 `static_band_lineage_select_mismatch`，不能进入 facts 或 proposal。
- downstream typed/facts A/B 逐字节一致：7,124 mapping-complete workflow、6,801 fact bundle、
  4,245 task candidate、323 条 facts fail-closed。新的 expansion census 有 2,035 个 source 的
  3,469 条 source-disjoint proposal、26 条 length sidecar、0 条 semantic sidecar。
- 新抽取的 50 条完整源码审核为 50/50 pass、0 fail/defer、0 critical failure，全部 source SHA
  verified；evaluator 结论为 `passed_for_larger_source_disjoint_replay`，不需要新增规则。
- hash-bound exporter 已准入全部 3,469 条 proposal，export duplicate=0、新增 length defer=0；当前
  合并权威包为 **7,971 条语义 train-only 行、7,970 条 V4-100 行和 1 条既有 155-step sidecar**，
  A/B 训练产物逐字节一致。
- 真实 `TaskConditionedL3DatasetV4`、weighted loss 与 backward smoke 覆盖 7,970/7,970 行：15 个
  `[512,100]` batch 和 1 个 `[290,100]` batch，loss/gradient finite，max token=93、最大模型序列
  长度=99；未写 checkpoint、未运行训练 epoch，smoke A/B 逐字节一致。
- smoke CLI 现默认使用冻结 taxonomy mapping authority。服务器 `outputs_v2/id_mappings_v2.json`
  SHA 不同并正确 fail-closed；Batch8 实际验证使用 required stable-94 SHA 对应的
  `configs/taxonomy/inputs/id_mappings_v2.json`。
- Batch9 已对 5,000 个新的 source-disjoint source 完成冻结 v8.8 AST/DAG A/B replay，A/B
  逐字节一致：AST 成功 4,997、parse fail-closed 3；DAG source status 为 passed=187、partial=140、
  fail-closed=4,670。`workflow_dags.jsonl`、`parse_failures.jsonl` 与 `summary.json` 均一致。
  本阶段不生成 facts、任务文本或训练行；详见
  `docs/reports/gee_batch9_v8_8_ast_replay_2026-08-07.md`。
- Batch9 已对相同 DAG 输入完成冻结 v8.8 fidelity A/B replay；因 live fidelity module 与冻结快照
  SHA 不同，本次明确使用受控快照。11,117 个 workflow decision 的 A/B 逐字节一致：644 条 passed
  candidate、来自 306 个 source，6 条 exact duplicate，10,467 条 fail-closed，训练行仍为 0。证据见
  `docs/reports/gee_batch9_v8_8_fidelity_replay_2026-08-07.md`。
- Batch9 已完成冻结 v8.8 typed canonicalization/mapping A/B：355 条 mapping-complete workflow、
  来自 154 个 source；289 条 fail-closed，覆盖 126 个 canonical GEE operator 与 47 个 L3 code，
  A/B 业务产物逐字节一致、训练行=0。证据见
  `docs/reports/gee_batch9_v8_8_typed_mapping_replay_2026-08-07.md`。
- Batch9 已完成冻结 source/AST-backed facts A/B：339 条 fact bundle、16 条 fail-closed，确定性去重
  压制 97 条 exact task-text/L3 duplicate 后保留 242 条 task-text candidate，并生成 50 条风险审核包；
  训练行仍为 0。证据见 `docs/reports/gee_batch9_v8_8_facts_replay_2026-08-07.md`。
- Batch9 已对全部 242 条 canonical task-text candidate 完成冻结 expansion/proposal A/B。包括 hash ledger
  在内的业务产物逐字节一致：197 条 proposal（114 个 eligible source）、44 条 duplicate sidecar、1 条
  length defer，semantic 和 reviewed-source-overlap failure 均为 0。50 条分层完整源码审核包已经冻结、
  等待审核；训练行仍为 0。证据见
  `docs/reports/gee_batch9_v8_8_expansion_replay_2026-08-07.md`。
- 冻结的 Batch9 50 条完整源码语义审核已 fail-closed：43 条 pass、7 条 critical failure，point
  precision=0.86、Wilson 95% lower=0.7381380628941446，evaluator 决策为
  `failed_rule_repair_required`。其中 5 条共同证明控制流循环 lineage 缺口是可复用问题；未授予任何
  proposal 或训练准入。证据见 `docs/reports/gee_batch9_v8_8_expansion_audit_2026-08-07.md`。
- 已在 `code_snapshot_v8_9_3_loop_lineage_facts_ledger_determinism_authority` 上应用最小化的
  v8.9 loop-lineage fail-closed 修复，并从 Batch9 DAG 重放到 proposal。每个 A/B 产物均逐字节一致：
  326 条 mapping-complete workflow 生成 315 条 facts 和 224 条 canonical task-text candidate；扣除
  41 条重复后保留来自 107 个 source 的 183 条 proposal。facts ledger 现使用逻辑 source/AST identity，
  不再泄露 A/B 物理目录。新的 50-source 分层审核包已冻结为 `pending_sampling_audit`，训练行仍为 0。
  证据见 `docs/reports/gee_batch9_v8_9_3_replay_and_audit_freeze_2026-08-07.md`。
- v8.9.5 新增字面量 catalog 时间覆盖门禁，并从 Batch9 fidelity 重放至 proposal/export；它只拒绝
  已证明的公开 ImageCollection 字面量 ID 与字面日期范围无覆盖交集的 workflow。A/B 保留来自 105 个
  source 的 180 条 proposal；新的 50-source 完整源码审核为 50/50 pass、0 critical，Wilson 下界为
  0.9286524008666414。hash-bound exporter 已准入全部 180 条。当时 Batch9 v8.9.5 合并权威包为 **8,151 条语义行、
  8,150 条 V4-100 行和 1 条 155-step sidecar**。真实 V4 loader/loss/backward 对 A/B 均覆盖
  8,150/8,150 行，loss/gradient finite、输出一致，未写 checkpoint、未运行训练。证据见
  `docs/reports/gee_batch9_v8_9_5_authority_training_2026-08-07.md`。

- 生产母池仍为 219,914 个唯一源码内容。Batch7 对 10,000 个新的 source-disjoint source 完成
  全链重放；`/home/yll` 全程只读，9,993 个 source AST 成功。
- v8.6 新增 EE 对象原生 JavaScript 运算 fail-closed，明确 `getInfo()` 返回客户端值，并把多变量
  declaration 的类型归属收窄到各自 initializer。相对 v8.5，只有 4 条错误 pass workflow 转为
  fail-closed，既有准入 workflow 无变化。
- v8.6 authority 包含 3,029 个 DAG passed source 和 311 个 partial source。下游 A/B 得到 3,809 条
  mapping-complete workflow、3,605 个 fact bundle、2,490 条 canonical task candidate，以及来自
  1,321 个 eligible source 的 **2,235 条 source-disjoint proposal**；另有 7 条超长候选保持关闭。
- 50 条审核迁移按 identity 继承 49 条完整源码 PASS；被移除的是已确认的 native-operator critical
  failure，唯一补位 identity 已按完整源码显式复核并通过。v8.6 最终审核为 50/50 pass、point
  precision=1.0、Wilson 95% lower=0.9286524008666414、critical failure=0。
- 批次级准入全部 2,235 条同规则 proposal，export duplicate=0、新 length defer=0。合并 train-only
  包现有 **4,502 条完整语义行、4,501 条 V4-100 行和 1 条既有 155 步 length sidecar**。
- 真实 `TaskConditionedL3DatasetV4`、weighted loss 和 backward smoke 覆盖 4,501/4,501 行，batch
  为八个 `[512,100]` 和一个 `[405,100]`；loss/gradient finite，max token=93，最大模型序列长度
  为 99，未写 checkpoint、未运行训练 epoch。training/smoke A/B 逐字节一致。

当前权威产物：

- 服务器根目录：
  `/home/qy/system_redesign/diagnostics/gee_batch9_5000_v8_8_20260806`
- 当前训练包：`training_v8_9_5_catalog_temporal_filter_authority_a` 与 `_b`；
  Batch8 v8.8 包只保留为 provenance
- smoke：每个当前 A/B 训练包目录下的 `loader_loss_smoke_v8_9_5.json`
- 正式报告：
  `docs/reports/gee_batch9_v8_9_5_authority_training_2026-08-07.md`
- 数据内容与真实样本说明：
  `docs/reports/gee_training_data_contents_and_example_2026-08-05.md`

真实样本说明已经把一条当前 Batch7 行同时回指到 `/home/yll/GEE/Data` 源码和最新合并 authority。
该检查也确认一个此前链/源码审核没有评价的模型接口风险：当前 `task_name` 会泄漏工作流步数，
`task_description` 会按顺序枚举 GEE 算子。4,502 条语义行的源码、DAG、operator 和 L3 authority
仍然有效，但当前文本视图属于 operator-explicit 的 GEE-to-L3 翻译输入，还不是无答案泄漏的
自然语言规划输入。

## 当前门禁

Batch10 是新的 source-disjoint 扩展批次，尚不属于现有 8,150 条权威训练包。v8.9.5 首轮重放得到
37 条待审 proposal、30 个 eligible source。完整源码审核证实一项可复用缺陷：未 `rename()` 的
`Image.expression()` 默认 band 为 `constant`，后续静态 `select('HV')` 必须 fail-closed。v8.9.6
受控快照已修复该规则；本地 pytest 与服务器 unittest 的 64 项聚焦回归均通过。Batch10 从 fidelity 到
proposal 的 v8.9.6 A/B 产物逐字节一致：143 fidelity candidate、57 mapping-complete、55 facts、48 条
canonical task-text candidate，以及来自 29 个 eligible source 的 36 条 pending proposal。
冻结的 29/29 全覆盖审核现已完成：28 条 pass、1 条 isolated fail-closed
（`data300000/script_304794.txt`）。该条经循环得到的影像依赖没有进入 dataset facts 和任务文本；在 37 条含
`ee.imagecollection.*` 链的 facts bundle 中，这也是唯一缺少 `ee.ImageCollection` dataset fact 的样本，
故不修改规则也不重放。hash-bound evaluator 的 Wilson 下界为 `0.8282448`，低于 `0.85`，结论为
`failed_rule_repair_required`；Batch10 全批不准入，也不计入 8,150 条。详见
`docs/reports/gee_batch10_v8_9_6_full_audit_2026-08-08.md`。

累计 8,000 行语义门禁已完成。Batch9 v8.9.5 是当前 GEE train-only authority。其 5,000 个 hard-structure
source（helper export=4,000、control-flow export=1,000）与前 36,663-source exclusion union 零重叠。旧
v8.8 审核曾 fail-closed，随后 loop-lineage 修复完成重放，字面 catalog 时间覆盖门禁又移除了两个已证实的
日期缺陷。替换后的 50-source 审核通过，同规则的 180 条 proposal 已被准入为 train-only。下一道 gate 是
在冻结 v8.9.5 下选择新的 source-disjoint population，而不是继续复核已准入行。

尝试的 20,000-source selection 因剩余严格 population 无法提供 15,000 条 linear export 而正确触发
exact-quota fail-closed。这是容量结论，不是放宽规则；只有后续抽样发现系统性、可复用缺陷时才修改
规则并整批重放。

后续每批仍需全 population A/B 确定性重放和分层完整源码审核。下一步是在冻结 v8.9.6 下选择新的
source-disjoint population，规模应保证至少 50 个 eligible source，以获得统计上足够的审核。只有审核发现
系统性失败，才允许修改一条可复用规则并整批重放。

Batch11 已在冻结 v8.9.6 下完成选择：排除 43,663 个既有或已触及的 source hash 后，冻结 5,000 个
source（`helper_export=2,500`、`control_flow_export=2,500`）。有效 AST/DAG A/B replay 显式使用
`/home/yll/.local/node-20/bin/node` 和
`NODE_PATH=/home/qy/system_redesign/.runtime/gee-ast-parser/node_modules`，结果逐字节一致：AST 成功
4,995、parse failure 5；DAG source status 为 passed=143、partial=98、fail-closed=4,754，共 9,069 个
workflow DAG。fidelity A/B 同样一致：388 条 passed candidate（217 个 source）、14 条 exact duplicate、
8,667 条 fail-closed。

冻结 v8.9.6 typed canonicalization/mapping A/B 已处理全部 388 条 fidelity-passed candidate，业务产物和
hash ledger 均逐字节一致：206 条 mapping-complete workflow（125 个唯一 source）、182 条 fail-closed、
107 个 canonical GEE operator、42 个 L3 code。随后 facts A/B 生成 200 条 fact bundle、6 条 facts fail-closed，
经确定性去重保留 135 条 task-text candidate（101 个 source、65 条 duplicate sidecar）。冻结 expansion A/B 保留
95 条 pending proposal（78 个 eligible source），排除 39 条 existing/batch duplicate，另有 1 条超长链进入
length sidecar；所有 expansion 业务产物和 hash ledger 逐字节一致。下一门禁是冻结的 50-source 完整源码审计；
审计裁定前不得把 proposal 视为 train-only 行。

该 Batch11 v8.9.6 审计已完成：50/50 source SHA256 均匹配，但仅 47 条 pass。3 条 critical failure 共同证明
两类可复用缺陷：catalog coverage 表遗漏 `COPERNICUS/S2_SR_HARMONIZED`，以及 skip authority 在
`first()` 或 `mosaic()` 前删除了 output-relevant `ee.imagecollection.sort`。hash-bound evaluator 结论为
`failed_rule_repair_required`（precision=0.94、Wilson lower=0.8378290831、critical=3），因此 95 条 proposal
均未准入。

最小 v8.9.7 修复仅补充公开 S2 SR Harmonized 的 coverage 下界，并将 `ee.imagecollection.sort` 从版本化
skip authority 移除；stable-94 已映射其至 `L3_03_09_07`。但其完整源码审计又发现一条 critical：
`ee.Image(...)` 包装器隐藏 collection lineage 后，`COPERNICUS/S2_HARMONIZED` 在 2017-03-28 之前的
空时间请求未被拒绝；93 条 proposal 仍未准入。

v8.9.9 增加 S2 Harmonized 下界并让单参数 `ee.Image(value)` 透明保留已证明 lineage。全链 A/B 逐字节一致：
386 条 fidelity-passed、204 条 mapping-complete、来自 75 个 eligible source 的 92 条 proposal（40 条 duplicate、
1 条 length sidecar）。新冻结的 50-source 审计全部 SHA256 匹配，50/50 pass、0 critical，precision `1.0`、
Wilson 下界 `0.9286524008666414`。

Hash-bound export A/B 逐字节一致：新增 92 条行、duplicate=0、new length defer=0。当前合并 authority 为
**8,243 条语义 train-only 行、8,242 条 V4-100 行和 1 条既有 155-step sidecar**。真实 V4 loader/loss/backward
smoke 在 A/B 均覆盖 8,242/8,242 行（17 个 batch，最后 `[50,100]`），loss/gradient finite，最大 token=93、
最大模型序列长度=99，未写 checkpoint、未运行训练。Batch11 已获 train-only 准入；validation/test 与 production
merge 仍关闭。

Batch12 已冻结下一批 v8.9.9 source-disjoint population：5,000 个 source（`helper_export=2,500`、
`control_flow_export=2,500`）与累计 48,663 个 exclusion source SHA256 零重叠。selection A/B 与 hash ledger
逐字节一致。本阶段仅 selection、训练行=0；直接下一门禁是冻结 v8.9.9 的 AST/DAG A/B replay。

训练接口转换明确延后到目标数据池处理完成之后。届时以同一份冻结语义 authority 统一派生两种
视图：`operator_explicit` 用于 GEE-to-L3 对齐预训练/消融，`goal_only` 用于无答案泄漏的自然语言
规划。两种视图在最终训练接口阶段统一生成和审核；当前不得让文本接口阻塞源码/DAG/L3/fact
恢复，也不得遗忘已经登记的标签泄漏风险。

57 个 legacy/unverified 公共 dataset ID 继续作为独立规则 authority 队列；模糊匹配、embedding
或自动 dataset-ID 替换不得授予准入，也不得阻塞已准入训练包。

## Batch12 快照重放与审计

首轮 Batch12 重放误用了漂移的 live DAG gate（SHA `472607...`），而不是冻结 v8.9.9 gate（SHA
`4cb297...`）；前者缺少既有 control-flow lineage predicates。用快照对 13 条已知 critical source
定向重放后，13/13 全部 fail-closed，证明根因是运行时 authority 错误，而不是需要放宽规则。

快照 authority 的全批 A/B 重放逐字节一致：AST 4,994 成功/6 失败；DAG source status 为
`passed=135`、`partial=105`、`fail_closed=4,754`；fidelity 467 workflow（218 source）；typed mapping
219 workflow（112 source）；facts 218 bundles、162 task-text candidates（97 source）；proposal 70 条、
41 个 eligible source。proposal hash ledger 一致（`772218...`），训练行=0。

修复后的 41-source 穷尽完整源码审计（可用独立 source 只有 41，不能重复使用已拒绝 source 凑 50）为
41/41 pass、0 critical，precision=`1.0`、Wilson 95% lower=`0.9143324298155681`，evaluator=
`passed_for_larger_source_disjoint_replay`。Batch12 仍未准入；下一门禁是 hash-bound export 和真实
V4 loader/loss/backward smoke。证据见
`docs/reports/gee_batch12_v8_9_9_snapshot_authority_replay_audit_2026-08-10.md`。

### Batch12 导出与 loader/loss smoke（2026-08-11）

冻结审计通过的 41 个独立 source 已通过 hash-bound exporter：41 条 semantic complete-workflow、
41 条 V4-100、0 条 duplicate、0 条 fail-closed、0 条 length sidecar，最大模型序列长度 20。包位于
`/home/qy/system_redesign/diagnostics/gee_batch12_5000_v8_9_9_20260810/export_snapshot_authority_41/`，
完整 authority/artifact SHA 写在 `hash_ledger.json`。

使用真实 `TaskConditionedL3DatasetV4`、weighted sequence cross-entropy 和 backward smoke，41/41
行在两个 batch（`[32,100]`、`[9,100]`）中加载，loss/gradient 均 finite，未写 checkpoint、未启动训练。
服务器默认 Python 缺少 torch，因此本次以本地 PyTorch 2.7.1 CPU 对从服务器复制的 hash-bound 包执行；
这不是数据失败，模型训练前仍需在训练主机的完整 PyTorch 环境复跑。该包现在可进入增量
`train-only` authority manifest，但 validation/test、production merge 和训练仍关闭。详见
`docs/reports/gee_batch12_v8_9_9_snapshot_export_smoke_2026-08-11.md`。

## Batch13 replacement 选择与 DAG 重放（2026-08-16）

此前的 `gee_batch13_5000_v8_9_9_20260811` **不是新批次**：其 selection（`2bdadd...`）、
41-source audit packet（`983537...`）和 proposal ledger（`772218...`）均与 Batch12 逐字节一致。
该目录仅保留为诊断证据，绝不能再次导出或重复计入产量。

新的 replacement population 已冻结在
`/home/qy/system_redesign/diagnostics/gee_batch13_replacement_5000_v8_9_9_20260816`。
exclusion authority 扩展至 53,663 条 selector-compatible source；新 selection 为 5,000 条
（helper=2,500、control-flow=2,500），SHA=`61f737...`，与 Batch12、错误 Batch13 及 exclusion
authority 的 source SHA 交集均为 0。冻结 v8.9.9 AST/DAG A/B 逐字节一致：AST success=4,993、
parse failure=7，source status 为 passed=120 / partial=124 / fail-closed=4,749。当前未产生 facts、
proposal 或训练行。

replacement fidelity A/B 已逐字节一致：来自 4,993 个已解析 source 的 9,410 个 workflow decision 中，
454 条 passed candidate（228 个唯一 source）、17 条 exact duplicate、8,939 条 fail-closed。尚未执行
mapping、任务文本、proposal、export 或训练行生成；下一门禁仅能对这 454 条执行 typed
canonicalization/mapping A/B。

replacement typed canonicalization/mapping A/B 已完成且逐字节一致：454 条 fidelity candidate 中，266 条
mapping-complete（121 个唯一 source），188 条 fail-closed；覆盖 108 个 canonical operator 和 47 个 L3。
fail-closed 包括 43 条 canonical-L3 gap、22 条 override taxonomy gap、13 条 override signature mismatch、
96 条 support-classified retained call 和 14 条 unmapped raw call。尚未生成 facts、任务文本、proposal、
export 或训练行；下一门禁是对 266 条 mapping-complete candidate 生成 facts/task-text。

## Batch13 replacement facts 与任务文本（2026-09-02）

使用冻结的 v8.9.9 快照以及正确的只读源码根目录
`/home/yll/GEE/Data/data20000_AST_failed`，对 266 条 mapping-complete candidate
完成确定性 facts/任务文本生成：得到 259 条 source/AST-backed fact bundle、177 条去重后的
task-text candidate（82 条 duplicate sidecar）和 7 条 fail-closed；同时生成 50 条风险审核包。
修正审核器以识别 `Export.image.toAsset` 与 `Export.table.toDrive` 后，50/50 条机械审核通过，
并由回归测试覆盖。最终确定性去重得到 177 个唯一 candidate key，candidate 与 sidecar 无交集。
snapshot B 使用同一审核得到的结果与 A 逐字节一致（SHA256
`fbfb969a345a920c8e02734bd6f5fbfdbe52aae9c6a4a74f9064c577427e98c8`）。A/B 产物及 hash ledger
逐字节一致。当前未准入 proposal、export 或训练行；下一门禁是经明确推进
后才可执行 proposal 生成。

## Batch13 replacement proposal census（2026-09-02）

已将审核通过的 177 条候选送入冻结 expansion census：76 条进入 proposal-eligible，26 条因与已审核
source 重叠排除，25 条与既有 semantic authority 重复；无 semantic fail-closed、无长度延期。A/B
proposal 产物和 hash ledger 逐字节一致。76 条仍处于 `pending_sampling_audit`，尚未 export 或训练准入。

## 硬性边界

- `/home/yll` 只读；大型产物只放 `/home/qy`。
- 不修改 `outputs/`、`outputs_v2/` 或 `train11397_*`。
- 不训练，不让 LLM 猜测、增加、删除或重排算子链。
- validation/test 准入和 production merge 继续关闭。
- 必须使用 `configs/taxonomy/inputs/id_mappings_v2_94_frozen.json` 中冻结的 stable-94 mapping，SHA256：
  `005699dfd438e966cda28db8891795a07b9867856951de022cd8704c6e6a4558`。
