# GEE 项目上下文

最后更新：2026-09-02

本文是 GEE 数据处理工作区的长期技术交接。日常接手先读
`docs/GEE_CURRENT_STATE.zh-CN.md`。

## 语料权威决策

旧 11,397 行 graft 子集不是生产母池，只是早期筛选形成的历史校准子集。生产路线现从存量
GEE 原始主批次开始，在任何工作流或训练准入判断前先确定源码内容身份。

权威总账实现位于：

- `src/gis_recommend/data/gee_corpus_authority.py`
- `scripts/build_gee_corpus_authority_manifest.py`
- `tests/test_gee_corpus_authority.py`

其契约为确定性、fail-closed：

- 显式允许 `data10000` 至 `data400000` 的 31 个主批次；
- 只接受直接路径 `dataNNNNN/script_<id>.txt`；
- 按字节 SHA256 分组并确定性选择 canonical；
- facts 只按预期 batch 与 `File Name` 精确连接；
- basename-only 匹配只作诊断，绝不作为权威连接；
- 严格校验 facts 范围并输出明确失败账本；
- 目录级原子发布，失败时保留备份。

facts 覆盖单位明确为 `source_content_sha256_with_exact_instance_join`。同内容副本可在 SHA 层
继承 facts 支持，但 `join_ledger.jsonl` 只记录实际发生精确连接的源码实例。

## 已验证全语料重放

只读输入：

- `/home/yll/GEE/Data`
- `/home/yll/GEE/描述性知识抽取汇总`

服务器产物：

- `/home/qy/system_redesign/diagnostics/gee_corpus_authority_20260729_run1`
- `/home/qy/system_redesign/diagnostics/gee_corpus_authority_20260729_run2`

权威统计记录在 `docs/GEE_CURRENT_STATE.zh-CN.md`。两次运行的 7 个产物全部逐字节一致。
关键 SHA256：

- `canonical_sources.jsonl`: `7e6547e66a39c1c07fb05f950718ba15bd3ec3a7ac9ae03519d1e50afddd6752`
- `facts_ledger.jsonl`: `4e6e338421ce1cde92de04331d078c010425201ed6116b7c98c43d58e10617aa`
- `join_ledger.jsonl`: `4c4fd20b9f794804efebcf2bba4d9bc5be25b3670b2b40f4088badcdb89f8f2d`
- `source_instances.jsonl`: `7c7be8e6d55c976ec02c159937ae15cb455669bb3a28c2266de1e65e7f05f7af`
- `summary.json`: `2a09c243117c72240cfc0015e135c47e9e8d51d9025c78e8d5b9600950c646c0`

本机与服务器聚焦测试均为 16/16 通过，builder、CLI 和测试文件编译成功。小型证据保存在：

- `docs/reports/gee_corpus_authority_2026-07-29.md`
- `docs/reports/gee_corpus_authority_2026-07-29.summary.json`
- `docs/reports/gee_corpus_authority_2026-07-29.hash_ledger.json`

## DAG 校准前的准入边界

219,914 行 canonical source-content manifest 是数据资产总账，不是训练 manifest。进入总账或
获得 facts 覆盖均不自动授予 training、validation、test 或 production 准入。

下一门禁是：从 canonical manifest 抽取固定、source-disjoint 的校准样本，恢复完整的
output-relevant dependency DAG。抽样必须要求存在可观测输出 sink，并具有足够源码结构来验证
完整 backward slice。校准需要报告完整工作流恢复率和 fail-closed 原因，不能把局部正确片段
冒充完整训练行。

不得重复此前的问题：长期逐条审核单一局部模式，无法形成可推广的批量转换方法。

## 完整输出 DAG 校准

完整 DAG 门禁实现在 `src/gis_recommend/data/gee_workflow_dag_gate.py`，由
`scripts/build_gee_workflow_dag_calibration.py` 驱动。门禁只接受显式顶层 Export sink，沿输出
反向恢复依赖闭包，按源码顺序保留 core call，并对缺失计算、未解析调用和闭包内控制流
fail-closed；`Map.addLayer` 等展示 sink 不计为输出工作流。

固定、source-disjoint 的 50 源码样本用同一个 selection 重放三次；selection SHA256 为
`43d2d6fcfcbf14906aa07c2b2ec2ba8d3a0c2b1709aea0ae5d083645d4582576`：

- run1：11 passed、39 fail-closed、73 次未解析依赖；
- run2：18 passed、1 partial、31 fail-closed、63 次未解析依赖；
- run3：20 passed、30 fail-closed、61 次未解析依赖。

run2/run3 只识别有源码角色证据的外部空间输入。直接 `clip`/`filterBounds` 参数及
`geometry.geometry().bounds()` 等嵌套 region 表达式成为显式 sidecar；任意未解析 dataset、
image、派生变量和普通调用继续 fail-closed。本机与服务器聚焦测试均为 16/16 通过。

run3 有 114 个输出 DAG，其中 41 passed、73 fail-closed；source 级分层通过为 linear 15/30、
helper 4/10、control-flow 1/10。4 个样本只在循环或 helper 内含 Export，因执行次数和顺序
无法证明而正确保持关闭。

DAG 完整性只是训练准入的必要条件。抽查发现重复导出、仍混入 raw core chain 的空间访问器，
以及 rename 后选择其他 band 的静态可疑源码。下一门禁必须可批量、确定性执行：按语义身份
去重输出 DAG，在输入契约中保留空间 sidecar，把辅助调用移出 core chain，并拒绝无需猜测即可
证明的源码不一致。在该门禁前不生成 LLM 任务文本，也不导出训练行。

详细证据：`docs/reports/gee_workflow_dag_spatial_sidecar_calibration_2026-07-29.md`。

## 确定性 fidelity 门禁与 500-source pilot

post-DAG 门禁实现在 `src/gis_recommend/data/gee_workflow_fidelity_gate.py`，由
`scripts/build_gee_workflow_fidelity_calibration.py` 发布产物。它把 DAG 恢复、语义 fidelity
和训练准入分成独立门禁，当前契约为：

- 只有 receiver root 被证明为外部空间输入时，才把 `.geometry`/`.bounds` 从 core chain
  规范化移除；
- 只有源码同时静态证明单一 literal band select、map return rename 且 return path 不含
  `addBands`，以及 mapped collection 后续选择不同 literal band 时，才拒绝 band mismatch；
- 只对同一 source 的 exact output-DAG fingerprint 去重；
- 保留 source/workflow 身份、规范化链、依赖边、外部输入、移除的辅助调用和 fail-closed 证据；
- 所有 passed 行继续保持 `not_granted_taxonomy_and_task_text_pending`。

fixed-50 最终重放位于
`/home/qy/system_redesign/diagnostics/gee_workflow_fidelity_fixed50_20260729_c` 和 `_d`，
两次 7 个产物逐字节一致。114 个 workflow decision 为 35 passed、5 exact duplicate、
74 fail-closed，accepted candidate 由 19 个唯一 source 支持；73 个上游 fail-closed DAG
全部保持拒绝。同源 NDVI 双导出被正确去重，已知 `rename('lst') -> select('scale')` 被
`static_single_band_map_output_mismatch` 正确拒绝。

source-disjoint pilot 权威路径为
`/home/qy/system_redesign/diagnostics/gee_workflow_dag_pilot500_20260729_run3`。
它包含 500 个唯一 source SHA，排除全部 fixed-50 SHA，linear/helper/control-flow 配额严格为
400/75/25。500 行 selection 均通过 `/home/yll/GEE/Data` 下的 schema、size 与字节 SHA
重放；AST 成功/失败为 500/0，source 状态为 234 passed、16 partial、250 fail-closed。

`/home/qy/system_redesign/diagnostics/gee_workflow_fidelity_pilot500_20260729_*` 下的 `_a`、
`_b` 两次 fidelity replay 的 7 个产物逐字节一致。1,105 个 decision 中 546 passed、
10 duplicate、549 fail-closed；accepted set 由 250 个唯一 source authority 支持。352 个
workflow 带外部空间输入，移除的辅助调用为 0。本 pilot 没有出现新的静态语义不一致，
所有拒绝都保留上游 DAG 证据。另有 22 个 source-level fail-closed 行的 workflow list 为空，
因此没有 workflow-level fidelity decision，但仍保留在 500-source 分母中。

账本严格守恒且互斥：546 accepted + 549 rejected + 10 duplicate = 1,105 个唯一
`(source_sha256, workflow_id)`；所有行的训练行数均为 0。核心 authority hash 与分层通过率
见 `docs/reports/gee_workflow_fidelity_500_pilot_2026-07-29.md`。

## 当前生产门禁

下一阶段必须先把冻结的 546 个 candidate 转换成真实 train-only 行，而不是继续扩大只诊断
不产数的样本。首先绑定 candidate/AST/DAG hash，规范化已验证 core call，只把精确支持的
operation 映射到当前 L3 taxonomy，unresolved 继续 fail-closed。任务文本只能使用源码支持的
dataset、temporal、spatial-input、transformation 和 output facts；原始整脚本描述不是权威，
LLM 也不得改链。通过 task-text fidelity、规范化文本+L3 链去重、schema 和风险分层小批校准后，
再对全部 546 条重放。

validation/test 准入、production merge 和模型训练仍是独立决定，本阶段不授予。

## 保留 ordinal 的类型化 operator/L3 census

fidelity 契约现在把 `normalized_core_call_ordinals` 与 `normalized_core_chain` 成对保留。
fixed-50 和 pilot500 各自双跑逐字节一致，判定数量仍为 35/5/74 和 546/10/549；旧版与新版逐
workflow 状态投影 hash 相同。所有 passed/duplicate 行的 ordinal 与 normalized chain 一一对齐。

稳定 canonicalization 核心位于
`src/gis_recommend/data/gee_operator_canonicalization.py`。类型化领域门禁位于
`src/gis_recommend/data/gee_typed_canonicalization.py`，它把每个 ordinal 回接到 source-SHA-keyed
AST evidence，要求 `core` 分类和 raw callee 精确一致，并且只使用已证明的 EE receiver type。
生产 typed 模块不再依赖历史 P4 CLI 脚本。

服务器两次 census 位于
`/home/qy/system_redesign/diagnostics/gee_typed_l3_mapping_pilot500_20260730_*`，6 个产物逐字节
一致。546 个唯一 workflow 含 7,773 个 retained call，其中 6,871 个调用完成映射。workflow
结果为 266 mapping-complete（来自 131 个唯一源码）和 280 fail-closed：232 个
retained-core/support 角色冲突、42 个 catalog-without-L3 workflow、6 个 raw-call-gap workflow。
evidence mismatch 为 0；闭合候选覆盖 158 个 canonical operator 和 56 个 L3。

所有行仍为 `not_granted_task_text_and_final_dedup_pending`，训练行=0。当前生产门禁只处理 266
个 mapping-complete workflow 的 source-backed task facts 与忠实文本；三类 fail-closed 队列单独
恢复，不得阻塞首批真实产数。

详细证据：`docs/reports/gee_typed_l3_mapping_500_pilot_2026-07-30.md`。

## Source-Backed Workflow Facts 与任务文本

生产 facts/text 门禁由 `src/gis_recommend/data/gee_workflow_task_facts.py` 和
`scripts/build_gee_workflow_task_facts.py` 实现。它只接受 mapping-complete typed 行与
fidelity-passed 行的精确 `(source_sha256, workflow_id)` join，校验源码 SHA 与 AST、每个冻结 call
span 和 Export sink，再从精确依赖闭包构造 dataset、temporal、spatial-input、transformation、output
五类事实。

首轮 266 条 replay 通过确定性回归测试修正了以下问题：`updateMask` 不再被当成 temporal operator；
`ee.Date(...)`、`ee.Date.fromYMD(...)` 和静态字符串日期表达式可恢复；Export 的 `region` 计入空间
证据；影像 `.geometry()` 不会被误提升为外部空间资源；image/table/video 的 positional Export
signature 分开解析。

服务器最终 `_i` 与 `_j` replay 位于
`/home/qy/system_redesign/diagnostics/gee_workflow_task_facts_pilot500_20260730_*`，8 个产物逐字节
一致：266 个 fact bundle、0 个 fact failure、208 条 canonical task-text candidate、58 条 duplicate
和 50 条 source-disjoint risk-review 行。文本子句保留 fact ID、冻结 operator/L3 顺序不变、私有
asset 不出现在文本中，动态日期/空间声明以 omission 保留。所有 training admission 继续关闭。
完整证据见 `docs/reports/gee_workflow_task_facts_500_pilot_2026-07-30.md`。

## 风险审核规则修复与冻结 AST 重放

首轮 50 条审核发现的是可推广的确定性缺陷：helper 实参没有继续传播到局部别名、重复 helper
span 造成链膨胀、callback 算子在缺少结构化 `map` 时被错误线性化、部分静态对象被整体丢弃、
legacy Export config 未展开、数值 `ee.Image` 常量被当成资产 ID、已审核公开 project 被脱敏，
以及 raw chain 命名空间覆盖已证明的 receiver 返回类型。

所有修复均先增加回归，再修改 DAG gate、task-fact builder 和 operator canonicalizer。固定
selection 新增 `--ast-replay-dir`，无需 Node 重解析仍核验源码 size/SHA 和冻结 Program AST。
DAG A/B 核心数据逐字节一致，AST 500/500 成功：149 source passed、12 partial、339
fail-closed；fidelity 为 340 passed、10 duplicate、755 fail-closed；typed 为 209
mapping-complete（102 个源码）和 131 独立 gap；facts/text 为 209 bundle、0 failure、176
canonical candidate、33 duplicate、100 个候选源码。

稳定的 50 个 workflow identity 已按精确源码 SHA 完成六维复核，最终为 47 pass、3
`defer_source_ambiguity`、0 remaining rule fix。其中 1 条 pass workflow 含 155 个算子，当前
V4 loader 必须进入长度 sidecar。完整 workflow 专用 schema/export 与 lineage gate 完成前，
此处的训练行 0 是 schema/export 门禁建立前的校准状态，已被下节完整工作流交付结果取代。
服务器源码权威目录：
`/home/qy/system_redesign/diagnostics/gee_workflow_task_facts_pilot500_20260730_rulefix2_a`。

## 完整工作流 Train-Only V1 交付

完整 workflow 准入边界现由 `src/gis_recommend/data/gee_workflow_train_schema.py`、
`scripts/export_gee_complete_workflow_training_package.py` 和
`scripts/smoke_gee_complete_workflow_training_package.py` 实现。新 schema 为
`gis_recommend.gee_workflow_train_row.v1`，固定
`training_scope=complete_output_workflow`，不复用历史局部 `core_subworkflow` 契约。

不可变生产 profile 以 SHA256 同时绑定 risk packet、fact bundle、task-text candidate、正式审核
报告、adjudication ledger 和 stable-94 mapping，并固定 3 条 defer identity 与 8 项完整包计数。
展开后得到 50 条显式逐行决定；缺失、多余、重复或未列为 exception 的 defer identity 均
fail-closed。对每条 pass，exporter 强制核验 source lineage、schema/status、workflow key、
calibration stratum、omission、risk flag、clause lineage、exact DAG/output fact、文本子句事实回指、
operator/L3 对齐、stable-94 精确解析、规范化训练对去重，以及不截断的 V4 长度门禁。

服务器最终 `_g`、`_h` 双跑位于
`/home/qy/system_redesign/diagnostics/gee_complete_workflow_train_v1_20260731_*`，全部数据产物
连同 loader/loss smoke 逐字节一致。每次得到 47 条 schema-valid 完整语义行，对应 47 个唯一源码和 DAG；46 条进入
当前 V4-100 train-only 主包，1 条 155 步链进入 length sidecar，3 条源码歧义进入
fail-closed sidecar，duplicate=0。真实 V4 loader/weighted-loss/backward 覆盖 46/46 行，loss 与
gradient 有限，内容/总词表为 94/98，max token=92，最大模型序列长度=92，未写 checkpoint，
未运行训练。

trust-root 加固后的新鲜验证为聚焦测试 27 passed、1 个本机 torch 依赖测试 skipped；服务器
`py_compile` 通过。真实 smoke 使用 `/home/qy/miniconda3/envs/transformer` 的 PyTorch 2.2.2。
服务器 base Python 未安装 pytest，因此不宣称服务器 pytest 通过。

首次导出因服务器上无关的 `outputs_v2` mapping 含 107 项而正确 fail-closed。最终包使用本仓库
冻结 stable-94 mapping，其 SHA256 为
`005699dfd438e966cda28db8891795a07b9867856951de022cd8704c6e6a4558`；两份 mapping 均未修改。
完整证据见 `docs/reports/gee_complete_workflow_train_v1_2026-07-31.md`。

这是扩展阶段开始前的边界：剩余 126 条 canonical candidate 不能自动准入，必须复用相同门禁
并采用 source-disjoint 分层抽样。该阶段已由下节的 census 和抽样 selection 完成。独立的 131 条
mapping gap 继续 fail-closed，不阻塞 mapping-complete 扩展。

## 完整工作流扩展 Census 与抽样门禁

完整工作流 fact/text authority 校验已提取为公共门禁，
`scripts/build_gee_complete_workflow_expansion_batch.py` 对已审核 50 identity 之外的 126 条
canonical candidate 运行同一套转换。hash-bound 生产 census 要求每条 remaining identity 只能
进入一个终态：43 条因 reviewed-source overlap 排除，83 条成为 source-disjoint proposal；
semantic failure、stable-94 mapping gap、训练对 duplicate 和 V4 length defer 均为 0。proposal
状态固定为 `pending_sampling_audit`，不生成 train schema。

83 条 proposal 对应 50 个唯一源码 authority。按源码选择最高风险代表后，六层支持为：
external/dynamic 22、long/repeated 5、multi-dataset/private 9、no-temporal 7、other 1、
spatial-omission 6；largest-remainder 的 30-source 配额为 `13/3/5/4/1/4`。每个抽样源码均在
只读 `/home/yll/GEE/Data` 下重放 SHA，代码片段只来自 fact-backed source location 并受长度上限
约束；人工 verdict 字段全部保持空白。

服务器
`/home/qy/system_redesign/diagnostics/gee_complete_workflow_expansion_v1_20260731_*`
下 `_a`、`_b` 双跑逐字节一致。原始审核 JSONL SHA256 为
`c629543fe56fe1d3462466cebb0fbd90a8d25174df9cb33e8cdbb1704bf8ee8d`，source manifest SHA256 为
`e21f07c6cf3880c993b50e26c49d6b2367f532f39efe87a8def3a96b8d5c42f3`。evaluator 绑定原始 selection，
只允许输出 `passed_for_larger_source_disjoint_replay` 或 `failed_rule_repair_required`。通过要求
30 条全部完成、point precision>=0.95、Wilson 95% lower>=0.85、critical chain/L3/fact
hallucination failure=0；evaluator 不产出训练行，生产空白审核包已验证会 fail-closed。

本机审核包：`docs/reports/gee_complete_workflow_expansion_v1/`。详细报告：
`docs/reports/gee_complete_workflow_expansion_v1_2026-07-31.md`。

## 抽样授权批次准入与首批扩展训练集

type-gated 重放后的冻结 proposal authority 为 78 条、45 个源码 authority。30-source 分层审核
为 30/30 pass，point precision=1.0、Wilson 95% lower=0.8864866，critical chain/L3/fact
failure=0。旧政策只把该结果视为继续扩大 replay 的许可，导致审核通过后仍不产数；现按分阶段
交付目标改为：确定性全 population 门禁与 source-disjoint 分层抽样共同授权同一冻结规则
population，抽样达到固定门槛后不再要求逐条人工审核。

`scripts/export_gee_expansion_training_batch.py` 会重新运行 hash-bound audit evaluator，校验 proposal
权限、stable-94 映射和与既有训练 authority 的 source overlap，执行规范化任务文本/L3 去重，并
同时导出增量与合并 train-only 包。78 条 proposal 全部准入，duplicate=0、length defer=0；合并
结果为 125 条语义行、124 条当前 V4-100 行和既有 1 条 155 步 length sidecar。

服务器
`/home/qy/system_redesign/diagnostics/gee_expansion_training_batch_v1_20260731_*`
下 `_a`、`_b` 双跑逐字节一致。真实 loader/weighted-loss/backward smoke 在一个 `[124, 100]`
batch 中覆盖 124/124 行，loss 与 gradient 有限，max token=92，最大模型序列长度=92，未写
checkpoint，也未运行训练 epoch。本机包：`docs/reports/gee_expansion_training_batch_v1/`；报告：
`docs/reports/gee_expansion_training_batch_v1_2026-07-31.md`。

当前扩展契约改为以产量为中心：冻结本转换器，通过新的 source-disjoint 批次使累计 V4 行达到
200-300；每批只抽 30-50 条审核，只有系统性抽样失败才修一条通用规则并整批重放。该门禁通过后
再扩到 500-1000 条，最后才考虑全量语料。

## 第二个 Source-Disjoint 批次与 200-300 行门禁

第二批扩展把同一套确定性完整工作流转换器应用到新的 500-source authority。修复后的 facts
重放得到 193 条 mapping-complete 输入、185 个 fact bundle、8 条 fail-closed、157 条 canonical
task text、28 条 duplicate 和 102 个候选源码；facts A/B 产物逐字节一致。

独立审核暴露了两类输出契约缺陷：一个 `ImageCollection` 被错误放入
`Export.table.toDrive`，一个有效的 `Export.map.toCloudStorage` 工作流被错误描述为 video。
按回归优先修复后，`Export.table*` 必须接收可证明的 `ee.featurecollection`，`Export.image*`
和 `Export.map*` 必须接收可证明的 `ee.image`，map 输出写为 `map tiles`，未知 `Export.*`
family 统一 fail-closed。新 facts/text authority 与上一轮相比只改变 map workflow 对应的一行，
SHA256 分别为
`34db42c625b18acd6c051c63882f8c4209c9b4991a010d90e2dbd0162e55cbe9` 和
`334ae48905d2983d3e065496c948b0b56cf865464d00a578af977dabcbc24bc3`。

expansion v6 含 154 条 proposal、100 个源码 authority。30-source 审核排除前两轮 32 个已审核
source 的并集，source manifest 与 v5 完全相同，仅修复后的 map authority 发生变化。29 条按
精确 authority 继承审核结论，`data140000/script_137440.txt` 重新按完整源码核对。最终为
30/30 pass、point precision=1.0、Wilson 95% lower=0.8864866068260312、critical failure=0；
`passed_for_larger_source_disjoint_replay` 授权同一冻结规则下全部 154 条 population。

确定性 exporter 准入全部 154 条，duplicate=0、length defer=0。合并结果为 279 条语义行、
278 条 V4-100 行和既有 1 条 155 步 length sidecar；服务器训练包 A/B 逐字节一致。真实 V4
loader/weighted-loss/backward 在一个 `[278, 100]` batch 中覆盖 278/278 行，loss 与 gradient
有限，max token=92，最大模型序列长度=92，未写 checkpoint、未运行训练；validation/test 和
production merge 继续关闭。

至此 200-300 行门禁已经完成。当前门禁切换为新的 source-disjoint 扩展：冻结 v6 转换器，
对完整 population 运行确定性门禁，只抽 30-50 个分层源码代表，把累计 V4 行扩到 500-1000。
详细证据见
`docs/reports/gee_expansion_training_batch2_exportmap_v6_2026-08-01.md`。

## 第三个 Source-Disjoint 批次与 500 行下限门禁

新的 1,000-source replay 继续使用完整 output-relevant DAG、类型化映射、facts、任务文本、
expansion、抽样和导出边界。首次完整源码审核发现 1 条 critical：畸形数据集字面量
`LANDSAT/LO08/C01/T1_RT`。旧 facts 会接受所有静态 dataset 字符串。TDD 修复现会在第二段
符合标准 `L[A-Z][0-9]{2}` 形态时拒绝未知 Landsat platform token，同时保留合法 `LC08` 和
历史 `LANDSAT/LC8_L1T_TOA`；该规则明确不等同于完整 catalog 校验。

facts v5 A/B 逐文件一致，把 368 条 mapping-complete 输入分为 354 个 fact bundle 和 14 条
fail-closed，并生成 296 条 canonical task text 与 58 条 duplicate。新增失败恰好是审核发现的
`LO08` workflow。expansion v5 A/B 同样逐文件一致：288 条 proposal、180 个 eligible source、
6 条既有或批内 duplicate，以及 2 条未准入的超长候选。

规则修复后，30 条审核 identity 中 28 条不变。两条替换样本分别是 35 步 ASTER 多指数逻辑链
和 JRC wet/dry sibling-export 工作流，均按完整源码通过六项 fidelity。最终审核为 30/30 pass、
point precision=1.0、Wilson 95% lower=0.8864866068260312、critical failure=0，授权同一规则
下全部 288 条 proposal。

合并交付包含 567 条语义行、566 条 V4-100 行和既有 1 条 155 步 length sidecar；训练包 A/B
逐文件一致。真实 loader、weighted loss 和 backward smoke 在两个包上均覆盖 566/566 行，
batch 为 `[512,100]` 和 `[54,100]`，loss/gradient finite，未写 checkpoint、未运行训练。
stable-94 使用 `configs/taxonomy/inputs/id_mappings_v2.json` 的冻结副本；已漂移的可变
`outputs_v2` 副本没有参与本次准入。

下一门禁是累计 800-1000 条 V4 行。并行冻结官方 GEE STAC snapshot，并对 57 个唯一 legacy
或 unverified 公共 dataset ID 建立规则级 authority；模糊匹配和自动 successor 替换不得作为
准入证据。详细报告见
`docs/reports/gee_expansion_training_batch3_rulefix_v5_2026-08-02.md`。

## 第四个 Source-Disjoint 批次与 800 行门禁

第四个 1,000-source replay 复用冻结的 source selection，并针对 30-source 审核发现的三类系统性
问题修正规则：属性级 backward slice 只跟踪可静态证明对象字面量中实际引用的键；
`ee.imagecollection.sort` 在 output-relevant 时不再被跳过；`ee.Date(Date.now())` 被明确记录为
运行时当前日期参数，同时保持 `static_status=partial`。动态键和不可证明参数继续 fail-closed。

修复后的 A/B population 确定性一致。285 条 canonical task candidate 经 10 条既有或批内重复
压制后形成 275 条 source-disjoint proposal，semantic failure=0、length defer=0。修复后的
30-source 审核为 30/30 pass、point precision=1.0、Wilson 95% lower=
0.8864866068260312、critical failure=0；只有 3 条抽样语义投影发生变化，其余 27 条的 operator、
L3、DAG、evidence 和 task text 投影保持不变。

hash-bound batch exporter 准入全部 275 条同规则 proposal。合并结果为 842 条完整语义行、841 条
当前 V4-100 行和既有 1 条 155 步 length sidecar。训练包 A/B 的 10 个文件全部一致；合并 semantic
与 V4 的 SHA256 分别为
`1d58d0f9a07e6c102bd31e4c626dc633f09dbb50420243216091574789cc3c47` 和
`fde1964dd7305ecc0f23779b440cd79cbbe02a9b5ac6a15ad32bb187f8516fad`。

两个包均通过真实 loader、weighted loss 和 backward smoke，覆盖 841/841 行，batch 为
`[512,100]` 与 `[329,100]`；loss/gradient finite，max token=92，最大模型序列长度=92，未写
checkpoint、未运行训练 epoch。当前门禁切换为冻结 v6 后的新 source-disjoint replay，把累计
V4 行扩到 1,000 条以上。详细证据见
`docs/reports/gee_batch4_rulefix_v6_training_2026-08-03.md`。

## 第五个 Source-Disjoint 批次与 1,000 行门禁

Batch5 选择 1,000 个新 source，与此前累计 3,244 个 source authority 零重叠；冻结 AST 对 998 个
源码重放成功，2 个 parser failure 保持关闭。首轮 30-source 审核在
`data40000/script_36676.txt` 发现 1 条 critical 假完整 workflow：callback 结果经 `map`、循环和
`Array.push` 收集，但输出 DAG 只保留 `Image.cat -> rename`。TDD 修复现会拒绝经原生集合
mutator 修改、但 producer closure 无法证明的 output-relevant binding；5 个 workflow 得到
`unresolved_mutated_collection_dependency`，其中 4 个退出 accepted population。

首个补位 source 暴露 candidate population 中唯一的逆序字面量日期区间
`[2020-01-01, 2019-12-30)`。第二条 TDD 规则拒绝 ISO start 不早于 end 的静态
`filterDate` 和 `ee.Filter.date`，但不改变允许跨年环绕的 calendar/day-of-year 窗口。无效行进入
`fact_fail_closed.jsonl`，不生成任务文本。

最终 v8 A/B population 确定性一致：552 条 fidelity-passed workflow、363 条 mapping-complete、
353 个 fact bundle、10 条 fact failure、256 条 canonical task text、97 条文本 duplicate、35 条
既有或批内 duplicate、2 条 length defer，以及 219 条 source-disjoint proposal。最终审核继承
29 个未变化 authority，并完整复核 1 个补位 source；结果为 30/30 pass、point precision=1.0、
Wilson 95% lower=0.8864866068260312、critical failure=0。

exporter 准入全部 219 条同规则 proposal。合并交付为 1,061 条完整语义行、1,060 条 V4-100 行和
既有 1 条 155 步 length sidecar，新增 export duplicate=0、length defer=0；训练包 A/B 全部一致。
真实 loader、weighted loss 和 backward smoke 覆盖 1,060/1,060 行，batch 为 `[512,100]`、
`[512,100]` 和 `[36,100]`，loss/gradient finite，未写 checkpoint、未运行训练 epoch。

累计 1,000 行门禁已经完成。下一步冻结 v8，扩展到 5,000 个新 source-disjoint source，只审核
50 个分层源码代表，目标累计至少 2,000 条 V4 行。详细证据见
`docs/reports/gee_batch5_rulefix_v8_training_2026-08-03.md`。

## 第六个 Source-Disjoint 批次、v8.4 修正与 2,000 行门禁

Batch6 对 5,000 个新的 source-disjoint source 完成全链重放。随后独立完整源码复核撤销了 v8.3
暂定的“50/50 pass”结论：1 条抽样 workflow 漏掉两个变量绑定的
`ee.Filter.calendarRange` 约束，另一条使用当前缺少执行 authority 的旧式可调用
`Export.image(...)`。v8.4 恢复类型可证的变量绑定 filter，并只拒绝可调用 `Export.image`；
`Export.image.toDrive`、`toAsset` 和 `toCloudStorage` 保持支持。全量重放把 17 条受影响 workflow
路由为 fail-closed。

facts A/B 逐字节一致，把 2,070 条 mapping-complete 输入划分为 1,974 个 fact bundle 和 96 条
failure，并生成 1,321 条 canonical task candidate 与 653 条文本 duplicate。expansion A/B 同样
逐字节一致：从 742 个 eligible source 得到 1,206 条 proposal、109 条既有/批内 duplicate 和
6 条 length defer。

审核继承现按 `(source_sha256, workflow_id)` 执行，不再依赖会移动的 audit index；门禁同时核验
新旧 packet SHA 和完整语义投影。47 个未变化 identity 继承既有 pass，修正/补位的 index 22、26、
50 按完整源码显式复核。最终审核为 50/50 pass、point precision=1.0、Wilson 95% lower=
0.9286524008666414、critical failure=0。

exporter 准入全部 1,206 条同规则 proposal。合并交付为 2,267 条完整语义行、2,266 条 V4-100 行
和既有 1 条 155 步 length sidecar，新增 export duplicate=0、length defer=0；训练包 A/B
逐字节一致。真实 loader、weighted loss 和 backward smoke 覆盖 2,266/2,266 行，batch 为四个
`[512,100]` 与一个 `[218,100]`，loss/gradient finite，未写 checkpoint、未运行训练 epoch。

累计 2,000 行门禁已经完成。v8.4 作为下一批更大 source-disjoint replay 的冻结生产规则；继续
采用批次级产数和 50 条分层完整源码审核，只有系统性抽样失败才允许修复一条通用规则并整批重放。
详细证据见 `docs/reports/gee_batch6_5000_v8_4_rulefix_training_2026-08-04.md`。

## 第七个 Source-Disjoint 批次、v8.6 原生运算门禁与 4,000 行门禁

Batch7 对 10,000 个新的 source-disjoint source 完成重放，9,993 个 source AST 成功。完整源码
native-expression 复核发现 1 条 `ee.Image - ee.Image` payload 和 3 条 EE Image `&&` payload。
v8.6 现会拒绝输出依赖闭包中 EE 对象参与的原生 JavaScript 运算，明确 `getInfo()` 返回客户端值，
并把每个 declarator 的类型归属限制在自己的 initializer。8 个真实模式定向重放得到 4 条合法
pass 和 4 条正确 fail-closed。相对 v8.5，只有 4 个 source 从 passed 转为 fail-closed，既有准入
workflow 无变化。

确定性 A/B population 包含 3,029 个 DAG-passed source 和 311 个 partial source。下游重放得到
6,280 条 fidelity-passed workflow/3,127 个唯一 source、3,809 条 mapping-complete workflow/
1,882 个 source、3,605 个 fact bundle、204 条 fact failure、2,490 条 canonical task candidate、
1,115 条文本 duplicate，以及来自 1,321 个 eligible source 的 2,235 条 proposal；另有 7 条超长
候选保持 defer。DAG、fidelity、typed、facts 和 expansion A/B 业务产物均逐字节一致。

v8.6 审核与 v8.5 共享 49 个 identity，完整语义 authority 投影变化为 0；这 49 条完整源码 PASS
按 workflow identity 继承。被移除的是已确认的 native-operator critical failure；补位的
`data160000/script_150169.txt` / `output-workflow-3` 已按完整源码显式复核并通过。最终评估为
50/50 pass、point precision=1.0、Wilson 95% lower=0.9286524008666414、critical failure=0。

exporter 准入全部 2,235 条同规则 proposal，duplicate=0、新 length defer=0。合并交付为 4,502 条
完整语义行、4,501 条 V4-100 行和既有 1 条 155 步 sidecar；训练包 A/B 逐字节一致。真实 loader、
weighted loss 和 backward smoke 覆盖 4,501/4,501 行，batch 为八个 `[512,100]` 与一个
`[405,100]`；loss/gradient finite，max token=93，最大模型序列长度=99，未写 checkpoint、未运行
训练 epoch。smoke A/B 同样逐字节一致。

累计 4,000 行门禁已经完成。v8.6 冻结用于下一批新的 source-disjoint population；继续采用完整
population 确定性门禁和每批 50 条分层完整源码审核，只有系统性抽样失败才允许修复通用规则并
整批重放。详细证据见
`docs/reports/gee_batch7_10000_v8_6_authority_training_2026-08-05.md`。

## 训练行接口审计与真实示例

字段级检查已经把 `gee_workflow_51e86cacc69bac9c_output_workflow_1` 同时回指到最新 Batch7 合并
authority 和只读源码 `/home/yll/GEE/Data/data250000/script_246471.txt`。该样本正确隔离最终导出的
MODIS 分支，排除了无关 Sentinel 分支和 UI 调用；源码链为
`filterDate -> median -> clip -> select`，stable-94 token 为 `50 -> 90 -> 25 -> 28`，序列化模型
标签为 `[-3, 50, 90, 25, 28, -4]`。

本次检查明确了数据契约：语义行保存任务文本、可审计 GEE operator 链、L3 标签、源码/workflow
身份、不可变证据哈希、准入状态、已知 omission 和样本权重。当前 V4 loader 使用任务 prompt，
自回归监督 L3 token 序列；它不直接监督 GEE operator、QGIS operator、可执行参数或 DAG 边。

检查同时暴露了此前没有评价的任务接口问题：当前任务名称会给出链长，描述会按顺序枚举 GEE
算子。因此这些行的源码/DAG/L3 authority 有效且格式上可训练，但当前文本视图会泄漏论文主线
“自然语言规划”的答案。应冻结现有 authority，保留 `operator_explicit` 作为对齐预训练/消融视图，
另行派生不含算子名称和步数的 `goal_only` 主线视图；训练或继续大规模扩量前先抽 50 条成对审核，
不重新执行 DAG/L3 抽取。完整字段和真实 JSON 示例见
`docs/reports/gee_training_data_contents_and_example_2026-08-05.md`。

后续执行顺序决定：数据恢复/质量治理与最终训练接口分为两个阶段。先继续完成 source-disjoint
源码恢复、DAG/L3/fact 门禁、去重和抽样规则审核，直到目标数据池处理完成；之后才从同一份冻结
语义 authority 统一派生并审核 `operator_explicit` 与 `goal_only`。文本泄漏结论仍然有效，但不再
阻塞语义 authority 扩量；它是模型训练和最终训练集发布前的硬门禁。

## 2026-08-06：Batch8 v8.8 band-alias 规则修复重放

Fidelity gate 现在解析源码顺序明确的顶层字面数组别名 `select(bands)`；动态、正则或重绑定
选择仍 fail-closed，服务器测试 33/33 通过。新的 A/B 重放逐字节一致：17,585 个 source（AST
成功 17,567、失败 18）；fidelity 为 39,110 workflows（11,342 passed、320 duplicate、27,448
fail-closed），已用 `static_band_lineage_select_mismatch` 关闭 `script_22112.txt` 漏检。Typed/facts
得到 7,124 mapping-complete workflow、6,801 fact bundle、4,245 task candidate。Expansion 得到
2,035 个 source 的 3,469 条 proposal 和 26 条 length sidecar。新 50 条源码审核 50/50 通过、
critical=0。

## 2026-08-06：Batch8 v8.8 hash-bound export 与 V4 smoke

冻结审核已授权全部 3,469 条 proposal。hash-bound exporter 新增 3,469 条语义行，duplicate=0、
新增 length defer=0；当前合并 authority 为 7,971 条 semantic train-only 行、7,970 条 V4-100 行和
既有 1 条 155-step sidecar，A/B 包哈希一致。

真实 `TaskConditionedL3DatasetV4`、weighted loss 与 backward smoke 覆盖全部 7,970 条 V4-100 行：
15 个 `[512,100]` batch 与 1 个 `[290,100]` batch，loss/gradient finite，max token=93、最大模型长度=99，
未写 checkpoint、未运行训练 epoch。初次 smoke 因服务器可变的 `outputs_v2/id_mappings_v2.json` 与
stable-94 SHA 不同而正确 fail-closed；改用 SHA256
`005699dfd438e966cda28db8891795a07b9867856951de022cd8704c6e6a4558` 对应的
`configs/taxonomy/inputs/id_mappings_v2.json` 后通过。现在
`scripts/smoke_gee_complete_workflow_training_package.py` 默认即使用该冻结路径。完整证据见
`docs/reports/gee_batch8_v8_8_authority_training_2026-08-06.md`。

## 2026-08-06：Batch9 v8.8 source-disjoint selection

Batch9 在未改动 v8.8 规则下冻结 5,000 个新的 hard-structure source：helper export=4,000、
control-flow export=1,000。source 边界排除了此前处理/排除的 36,663 个 source hash；selection A/B
逐字节一致且零重叠。尝试的 20,000-source 组成因剩余严格 population 不存在 15,000 条 eligible
linear export 而 fail-closed；这记录为容量约束而非门禁放宽。Batch9 目前仅为 selection，下一步必须
运行 AST A/B replay。详见
`docs/reports/gee_batch9_v8_8_source_disjoint_selection_2026-08-06.md`。

## 2026-08-07：Batch9 v8.8 AST/DAG A/B replay

冻结的 Batch9 population 已在未改动 v8.8 规则下完成 AST/DAG gate。两个独立运行均选择 5,000 个
source，AST 成功 4,997、3 条 parse failure 保持 fail-closed；DAG source status 为 passed=187、
partial=140、fail-closed=4,670。selection、workflow DAG、parse-failure 和 summary 业务产物均逐字节
一致；`workflow_dags.jsonl` 的 SHA256 为
`73479cdd3b079f441fef7ea76e40a32d92fe06cee15ee98623afbe25ddcd7340`。

本结果不授予 facts、任务文本或 train-only 准入。下一道 gate 是 fidelity A/B replay，之后依次为
typed mapping、facts、expansion 与抽样完整源码审核。证据见
`docs/reports/gee_batch9_v8_8_ast_replay_2026-08-07.md`。

## 2026-08-07：Batch9 v8.8 fidelity A/B replay

Batch9 fidelity 只使用 v8.8 受控快照执行，因为 live `gee_workflow_fidelity_gate.py` 的 SHA 与快照
不同。两个独立运行消费相同 DAG authority，决策逐字节一致：11,117 个 workflow、644 条 passed
candidate（来自 306 个 source）、6 条 exact duplicate、10,467 条 fail-closed，未生成训练行。下一道
gate 是对 passed candidate 执行 typed canonicalization/mapping A/B。完整证据见
`docs/reports/gee_batch9_v8_8_fidelity_replay_2026-08-07.md`。

## 2026-08-07：Batch9 v8.8 typed mapping A/B replay

冻结的 typed publisher、canonicalizer、stable-94 mapping、v8.5 override 与 v2.7 skip-list 对全部
644 条 fidelity-passed workflow 产生逐字节一致的 A/B 输出。其中 355 条来自 154 个 source 的 workflow
mapping-complete，289 条保持 fail-closed；complete 集覆盖 126 个 canonical GEE operator 和 47 个 L3
code，未生成训练行。下一道 gate 是只对 mapping-complete 输出运行 source/AST-backed facts A/B。证据见
`docs/reports/gee_batch9_v8_8_typed_mapping_replay_2026-08-07.md`。

## 2026-08-07：Batch9 v8.8 source/AST-backed facts A/B replay

冻结 facts publisher 对全部 355 条 mapping-complete workflow 回指只读源码和 AST。结果为 339 条 fact
bundle、16 条 fail-closed；确定性 task-text/L3 去重将 97 条 exact duplicate 写入 sidecar，保留来自 133
个 source 的 242 条 candidate。50 条风险审核包已生成，但未生成训练行。下一道 gate 是对 canonical
candidate population 执行 expansion/proposal A/B。证据见
`docs/reports/gee_batch9_v8_8_facts_replay_2026-08-07.md`。

## 2026-08-07：Batch9 冻结 expansion 审核 fail-closed

hash-bound 的 50 条完整源码审核结果为 43 条 pass、7 条 critical failure（point precision=0.86；Wilson
95% lower=0.7381380628941446）。evaluator 决策为 `failed_rule_repair_required`，生成训练行数为 0，
未授予 validation/test eligibility 或 production merge。

5 个独立 source 证明存在可复用缺口：输出相关 EE 值在控制流中发生循环重赋值、集合 mutation、动态
asset enumeration 或多次 reaching write，但 slice 只保留末端操作。下一次修复仅限为该模式增加
fail-closed lineage gate，随后全量 Batch9 A/B 重放并重新抽样审核。另有不可达 callback 语句和字面
catalog 日期不可能两个 singleton defect，均保持 fail-closed。证据见
`docs/reports/gee_batch9_v8_8_expansion_audit_2026-08-07.md`。

## 2026-08-07：Batch9 v8.8 expansion/proposal A/B replay

冻结的 expansion publisher 使用受控 v8.8 快照、只读源码证据、已审核 identity 排除集和既有 Batch8
semantic authority，对全部 242 条 Batch9 canonical task-text candidate 执行重放。包括 `hash_ledger.json`
在内的 A/B 业务产物逐字节一致。最终划分为来自 114 个 unique source 的 197 条 proposal-eligible、44 条
existing/batch duplicate、1 条 length defer、0 条 reviewed-source overlap 和 0 条 semantic failure。

50 条分层完整源码审核包及确定性配额已经冻结，状态为 `pending_sampling_audit`。未授予任何训练行、
validation/test eligibility 或 production merge。只有审核发现系统性且可复用的缺陷，才允许修改规则。
证据见 `docs/reports/gee_batch9_v8_8_expansion_replay_2026-08-07.md`。

## 2026-08-07：Batch9 v8.9.3 loop-lineage 重放与审核包冻结

已证实的控制流修复保持 fail-closed：若 export 输出依赖闭包中的变量在 sink 前控制流内被重赋值或
重新声明，且无法静态证明完整 lineage，则拒绝该 workflow。该规则不推断循环语义，也不改变无关的
top-level reassignment。新的 DAG 结果为 AST success=4,997、source passed=152、partial=133、
fail-closed=4,712；其中 410 个 source 带有 `unresolved_output_control_flow_lineage`。

在 `code_snapshot_v8_9_3_loop_lineage_facts_ledger_determinism_authority` 下，全部下游 A/B 发布物
逐字节一致：fidelity 接收 563 条 decision，typed mapping 产生 326 条 complete decision，facts 产生
315 条 fact bundle 和去重后的 224 条 task-text candidate。facts ledger 已改为记录逻辑
`source/<corpus path>` 与 `ast/<source SHA>.json` key，因此账本也不再受 A/B 物理目录影响。

显式 v8.9.3 proposal profile 冻结了新的 authority hash 与分区：来自 107 个 eligible source 的 183 条
proposal、41 条 duplicate sidecar，以及 0 条 length、semantic、reviewed-source-overlap sidecar。新的
50-source 分层审核包冻结为 `pending_sampling_audit`，未授予 train-only、validation/test 或 production
准入。证据见 `docs/reports/gee_batch9_v8_9_3_replay_and_audit_freeze_2026-08-07.md`。

## 2026-08-07：Batch9 v8.9.5 catalog 时间覆盖 authority

下一轮 50-source 审核发现并完整源码核验了两个日期缺陷：一条 Landsat 查询早于覆盖期，以及
Sentinel-2 查询早于覆盖期。最小化修复仅在已支持的公开 `ee.ImageCollection("<literal>")` 和字面
`filterDate` / `ee.Filter.date` 范围无 catalog 覆盖交集时触发
`catalog_temporal_coverage_empty`；不推断动态 dataset 或动态日期。

在受控 `code_snapshot_v8_9_5_catalog_temporal_filter_authority` 下，完整 Batch9 重放 A/B
逐字节一致：fidelity 接收 545 条 workflow（6 duplicate、10,566 fail-closed），typed mapping 有
来自 140 个 source 的 323 条 complete workflow，facts 有 312 条 bundle 和 221 条 canonical candidate，
expansion 有来自 105 个 source 的 180 条 proposal 与 41 条 duplicate。替换后的 hash-bound 审核为
50/50 pass、0 critical，Wilson 下界 0.9286524008666414，evaluator 授予更大 source-disjoint replay。

hash-bound exporter 准入全部 180 条 proposal，未新增 duplicate 或 length defer。合并权威包为
8,151 条 semantic、8,150 条 V4-100 和 1 条既有 155-step sidecar。服务器 `transformer` 环境
（PyTorch 2.2.2+cu121）中，真实 `TaskConditionedL3DatasetV4`、weighted loss 与 backward smoke
覆盖 8,150/8,150 条、共 16 个 batch；loss/gradient finite，A/B smoke 逐字节一致。未写 checkpoint、
未运行训练。冻结 stable-94 mapping SHA 为
`005699dfd438e966cda28db8891795a07b9867856951de022cd8704c6e6a4558`。证据见
`docs/reports/gee_batch9_v8_9_5_authority_training_2026-08-07.md`。

本机 GEE 回归必须设置 `PYTHONPATH=src`；否则父目录中的 legacy `gis_recommend` 包会遮蔽本工作区
实现并产生假失败。固定该路径后，v8.9.5 聚焦测试为 40 passed、1 个 torch-dependent skip。

## 2026-08-08：Batch10 v8.9.6 expression-band lineage 修复

Batch10 选择了 2,000 个新的 source-disjoint source。其 v8.9.5 A/B 重放形成 37 条待审 proposal、
30 个 eligible source，但完整源码审核发现可复用 fidelity 缺陷：`ee.Image.expression()` 未重命名时默认
输出 `constant` band，保留下游的静态 `select('HV')` 却被错误接受。新的 v8.9.6 受控快照将 expression
输出 band 记录为 `constant`，并把静态检查传播到 expression 参数；只拒绝可证明的矛盾。本地 pytest 和
服务器 unittest 的 64 项聚焦测试均通过。

Batch10 全量重放的 A/B 逐字节一致：143 条 fidelity candidate（82 source）、57 条 mapping-complete
workflow（43 source）、55 条 fact bundle、48 条 canonical task-text candidate，以及来自 29 个 eligible
source 的 36 条 pending proposal。`exhaustive_29` 是该批全覆盖审核；未导出或合并任何行，Batch9
v8.9.5 的 8,150 条权威包保持不变。

完成的 `exhaustive_29` 审核为 28 条 pass、1 条 fail-closed。失败行是
`data300000/script_304794.txt` / `output-workflow-1`：输出相关链经循环依赖 `annual_col` 影像，
但 dataset facts 和任务文本仅保留 Laos boundary FeatureCollection。对 Batch10 的确定性普查表明，37 条
含 ImageCollection 链的 bundle 中只有这一条缺少 ImageCollection dataset fact，因而不能据此修改通用
extractor；该行保持排除。hash-bound evaluator 的 point precision 为 `0.9655172413793104`、Wilson 下界为
`0.8282447812067973`，结论 `failed_rule_repair_required`，所以 Batch10 全批不得准入。
证据见 `docs/reports/gee_batch10_v8_9_6_full_audit_2026-08-08.md`。

## 2026-08-09：Batch11 v8.9.6 source-disjoint selection

Batch11 在冻结 v8.9.6 规则下扩展，不再围绕 Batch10 的孤立 facts 遗漏反复处理。排除 authority 合并了
43,663 个既有或已触及的 source hash。A/B selection 逐字节一致，冻结 5,000 个新 source：2,500 条
`helper_export` 和 2,500 条 `control_flow_export`。这只是 selection；AST/DAG replay、facts、proposal、
训练准入和 merge 均仍未开始。

首个 Batch11 DAG 调用已替代，不能作为语料结论：后台环境先无法解析 `node`，随后无法解析 Acorn，因此生成
5,000 条 parser 环境失败和零 DAG。单源码 smoke 已确认：设置
`NODE_PATH=/home/qy/system_redesign/.runtime/gee-ast-parser/node_modules` 后，现有 Acorn runtime 会输出带
location 的 Program AST；有效重放还显式指定 `/home/yll/.local/node-20/bin/node`。

## 2026-08-10：Batch11 v8.9.6 有效重放至 typed mapping

在显式固定 Node/Acorn runtime 后，Batch11 AST/DAG A/B 有效且逐字节一致：AST 成功 4,995、parse failure
5、workflow DAG 9,069；source status 为 passed=143、partial=98、fail-closed=4,754。其 fidelity A/B 也逐字节
一致：388 条 passed candidate（217 个 source）、14 条 exact duplicate、8,667 条 fail-closed。

冻结 v8.9.6 typed publisher 分别以 stable-94 mapping、v8.5 override 和 v2.7 skip list 处理两份 fidelity
输出，得到 206 条 mapping-complete workflow（125 个 source）、182 条 fail-closed、107 个 canonical GEE
operator 和 42 个 L3 code。五个业务产物和 hash ledger 均逐字节一致；服务器证据目录为
`/home/qy/system_redesign/diagnostics/gee_batch11_5000_v8_9_6_20260808/typed_v8_9_6_{a,b}`。
未授权任何 facts、task text、proposal、export 或训练行。下一门禁是仅对
`mapping_complete_candidates.jsonl` 运行 source/AST-backed facts A/B。证据见
`docs/reports/gee_batch11_v8_9_6_typed_mapping_replay_2026-08-10.md`。

## 2026-08-10：Batch11 审计失败与 v8.9.7 受控修复

Batch11 v8.9.6 的 50-source 完整源码审计验证全部 source SHA256 匹配，但未达到准入：47 pass、3 条
critical failure、precision=0.94、Wilson lower=0.8378290831116182。一条源码证明
`COPERNICUS/S2_SR_HARMONIZED` 的公开 catalog coverage 区间遗漏；另两条独立源码证明 `sort` 在
`first()` 或 `mosaic()` 前会影响输出，不能被全局 skip。因此 v8.9.6 的 95 条 proposal 均未准入。

v8.9.7 仅增加已知 S2 SR Harmonized coverage 下界，并派生只移除 `ee.imagecollection.sort` 的版本化 skip
authority；stable-94 已将其映射至 `L3_03_09_07`。从有效 Batch11 DAG A/B 起的受控重放在每个下游阶段均
逐字节一致：387 条 fidelity-passed、205 条 mapping-complete、199 条 facts、134 条 canonical task-text
candidate、以及来自 76 个 source 的 93 条 pending proposal。新的 50-source 审计包已冻结，hash-bound export
前必须完成审核。证据见
`docs/reports/gee_batch11_v8_9_6_audit_and_v8_9_7_replay_2026-08-10.md`。

## 2026-08-10：Batch11 v8.9.9 EE-image lineage 修复与审计

新的 v8.9.7 审计发现一条 critical temporal-coverage failure：
`COPERNICUS/S2_HARMONIZED` 的请求整体早于其 2017-03-28 catalog 起点，但单参数
`ee.Image(collection...median())` 包装器在 temporal gate 前丢失了已证明的 collection lineage。
v8.9.9 仅将该包装器设为透明 lineage，并记录 S2 Harmonized 下界；focused fidelity-gate 测试
`40/40` 通过。

从有效 Batch11 DAG A/B 起，v8.9.9 从 fidelity 至 proposal 的 A/B 逐字节一致：386 条
fidelity-passed workflow、204 条 mapping-complete workflow、75 个 eligible source 的 92 条
pending proposal、40 条 duplicate 和 1 条 length sidecar。冻结 audit sample 与 source manifest 的
SHA256 分别为 `221fd1e4a9d702b9143e5dd2c017b8ade1ddf37736be377669ba87f68eae3fad` 与
`d20ea5c5475cca843ac8ee30e7d3d8f4d7b3b12918009342237d323a45d873b4`。

50 条样本均从只读 `/home/yll/GEE/Data` 重算 SHA256 且全部匹配。完整源码审核逐条通过 dataset、
temporal、spatial、output-relevant DAG、output closure 与 task-text fidelity，critical=0。hash-bound
evaluator 为 50/50 pass、precision=1.0、Wilson 95% lower=0.9286524008666414，决策
`passed_for_larger_source_disjoint_replay`。审计产物位于
`/home/qy/system_redesign/diagnostics/gee_batch11_5000_v8_9_6_20260808/audit_v8_9_9_full/`。
随后 hash-bound exporter 生成逐字节一致的 A/B 包并准入全部 92 条（duplicate=0、new length defer=0）。
合并 authority 为 8,243 条语义 train-only 行、8,242 条 V4-100 行和 1 条既有 155-step sidecar。真实 V4
loader/loss/backward smoke 在两份 8,242 行包上均覆盖全部行、共 17 个 batch，loss/gradient finite，未写
checkpoint、未运行训练。Batch11 因此只准入 GEE train-only authority；validation/test 与 production merge 继续关闭。

## 2026-08-10：Batch12 v8.9.9 全链重放与审计失败

受控 v8.9.9 全链重放已完成，A/B 业务产物逐字节一致。AST/DAG 覆盖 5,000 个 selected source：4,994 个
AST 成功、6 个解析失败；source status 为 227 passed、119 partial、4,648 fail-closed。fidelity 保留 699 个
workflow（313 个 source）；typed mapping 保留 338 个 mapping-complete workflow（166 个 source）；facts 生成
335 个 fact bundle，去重后保留 228 条任务文本候选（130 个 source）。profile 以当前 8,243 条 semantic authority
作为跨批去重基线，拒绝 26 条跨批重复和 47 条已审核 source 重叠，得到 105 条 pending proposal（66 个 source）。

冻结的 50-source 审计对 `/home/yll/GEE/Data` 全部 source 重新计算 SHA256，均匹配；但语义审核只有 37 pass、
13 条 critical failure。evaluator precision=`0.74`、Wilson 95% lower=`0.6044684273515117`，结论为
`failed_rule_repair_required`，训练行=0。critical 共同证明：由 loop/list/map/helper 构成的导出对象可能只留下
末端调用，遗漏 output-relevant 的上游 dataset、filter 和 transformation。这是可复用 lineage 缺陷。

Batch12 完整不准入。不得 export 105 条 proposal，也不得运行训练 smoke。下一步只修复该特定 fail-closed 控制流
上游 lineage 缺口，然后从冻结 AST/DAG 输入全链重放并替换 50-source 审计。证据根目录为
`/home/qy/system_redesign/diagnostics/gee_batch12_5000_v8_9_9_20260810/`；报告为
`docs/reports/gee_batch12_v8_9_9_full_audit_2026-08-10.md`。

## 2026-08-10：Batch12 v8.9.9 快照 authority 修复与替换审计

首轮 Batch12 重放使用了 live DAG gate SHA `472607...`；冻结 v8.9.9 snapshot gate SHA 为
`4cb297...`，其中已经包含 loop-carried 和 unresolved output control-flow lineage predicates。
对 13 个 critical source hash 定向重放后 13/13 全部 fail-closed，因此没有新增宽松规则。

快照 authority 全批 A/B 逐字节一致：4,994 AST 成功、6 解析失败，DAG 为 135 passed / 105 partial /
4,754 fail-closed；fidelity 467、mapping-complete 219、facts 218、task-text 162、proposal 70（41 个 source）。
proposal hash ledger 为 `772218209cae88a9a407bd51b9ee6c1e889a210b37bfd59c816445adc7db3223`。

修复后只剩 41 个独立 eligible source。为保持 source independence，不能复用已拒绝 source 凑足 50，因此对
全部 41 个 source 做穷尽审计。结果 41/41 pass、0 critical，precision=1.0，Wilson 95% lower=0.9143324298155681，
evaluator=`passed_for_larger_source_disjoint_replay`。Batch12 仍未准入；下一门禁是 hash-bound export 和真实
V4 loader/loss/backward smoke。详见 `docs/reports/gee_batch12_v8_9_9_snapshot_authority_replay_audit_2026-08-10.md`。

## 2026-08-10：Batch12 v8.9.9 source-disjoint selection

Batch12 仅在 Batch11 获得 train-only 准入后扩展。新的累计 exclusion authority 将此前 43,663 个 source 的
union 与 Batch11 的 5,000 个 selected source 合并；两次构建逐字节一致，共 48,663 个唯一且 selector-compatible
的 source SHA256，无 duplicate 或 incompatible source record。

以该冻结 exclusion selection 为边界，Batch12 A/B 冻结 5,000 个 canonical source：2,500 个
`helper_export`、2,500 个 `control_flow_export`。selection manifest 和 hash ledger 逐字节一致；5,000 个
selected source SHA 均唯一，且与 48,663 个 excluded hash 零重叠。本阶段只做 selection，不产生 facts、文本、
proposal 或训练行。下一门禁是在受控 v8.9.9 code snapshot 下进行 AST/DAG A/B replay。

## 2026-08-11：Batch12 export 与 loader/loss smoke

41 个 exhaustive-audit pass source 已生成独立 hash-bound 包：semantic=41、V4-100=41、duplicate=0、
fail-closed=0、length sidecar=0，最大模型序列长度 20。包目录为
`/home/qy/system_redesign/diagnostics/gee_batch12_5000_v8_9_9_20260810/export_snapshot_authority_41/`，
authority 与 artifact SHA 均记录于 `hash_ledger.json`。

真实 `TaskConditionedL3DatasetV4`、weighted loss 和 backward smoke 覆盖 41/41 行、2 个 batch，loss 与
gradient 均 finite，未写 checkpoint、未训练。服务器默认 Python 没有 torch，因此用本地 PyTorch 2.7.1
CPU 对服务器复制的 hash-bound 包完成；训练主机仍需复跑。该包可以进入增量 train-only manifest，
validation/test、production merge 和模型训练保持关闭。详见
`docs/reports/gee_batch12_v8_9_9_snapshot_export_smoke_2026-08-11.md`。

## 2026-08-16：replacement Batch13 DAG 与 fidelity

旧 Batch13 与 Batch12 重复（selection=`2bdadd...`、audit=`983537...`、proposal ledger=`772218...`），
仅保留诊断用途。replacement 批次排除 53,663 条既有 source，冻结 5,000 个新的 SHA-disjoint source
（selection=`61f737...`），与 Batch12、错误 Batch13 及 exclusion set 均零重叠。快照 v8.9.9 DAG A/B
一致（AST success=4,993、parse failure=7；120 passed / 124 partial / 4,749 fail-closed）。fidelity A/B
也一致：454 条 passed candidate、228 个 unique source、17 条 duplicate、8,939 条 fail-closed。尚未授予
mapping、facts、proposal、export 或训练准入。
## 2026-09-02：replacement Batch13 facts/任务文本重放

针对 replacement Batch13 的 266 条 mapping-complete candidate，使用冻结 v8.9.9
facts builder 完成确定性重放。源码根目录纠正为
`/home/yll/GEE/Data/data20000_AST_failed`；此前使用其父目录导致全部安全
fail-closed（source missing）的初次结果已废弃。纠正后得到 259 条
`source_backed_complete` fact bundle、177 条去重 task-text candidate、82 条
duplicate sidecar、7 条 facts fail-closed，并生成 50 条风险审核包。全程未使用
LLM。A/B 目录复制后，facts、任务文本、重复 sidecar、失败清单、风险包、summary
和 hash ledger 七类产物逐字节一致。冻结的 50 条机械风险审核现为 50/50 通过。
审核器曾漏识别 `Export.table.toDrive` 与 `Export.image.toAsset`，已修复并加入回归测试。
最终确定性去重保留 177 个唯一 candidate key，与 82 条 duplicate sidecar 无交集。
该审核仅是机械证据，不等同人工批准；training、proposal、export、validation/test 与
production 准入仍关闭。
## 2026-09-02：replacement Batch13 proposal census

将 177 条审核 task-text candidate 针对 Batch11+Batch12 合并 semantic authority 执行冻结 expansion
census：127 条剩余 identity、26 条 reviewed-source overlap、25 条既有 authority duplicate、76 条
proposal-eligible；semantic fail-closed 与 length defer 均为 0。生成 35-source 分层审核包。A/B
proposal 产物与 hash ledger 逐字节一致；76 条均保持 `pending_sampling_audit`，不授予 export 或训练准入。
