# 项目上下文交接文档

最后更新：2026-06-24

这是 `system_redesign` 的长期项目记忆。新会话接手前应先读本文和 `docs/PROJECT_CONTEXT.md`，不要只依赖聊天记录。每完成一个阶段，都要把“已完成 / 未完成 / 当前阻塞 / 下一步动作 / 验证结果”补回本文。

## 当前目标

Phase 1（2026-05-27 至 2026-06-04）：完成 L3 模型的 DPO 偏好训练，构建 QGIS landing 层的检索与评估链路，并通过系统消融明确 L3 -> QGIS bridge 的有效策略。

本阶段关键结果：
- DPO v2 模型已训练完成，3000 GEE test 上 beam top-1 usable 从 59.9% 提升到 99.1%。
- QGIS Chain Retriever + Evaluator 已构建，200-probe 达到 100% combined bridge、0.995 平均质量。
- 基于 GitHub QGIS 脚本构建了 QGIS chain dataset；D1 合并后约 54k 脚本，3,021 条多步链。
- 18 条人工审查 QGIS->L3 crosswalk 已合并，L3 bridge coverage 从 12.3% 提升到 24.8%。
- QGIS retrieval 索引修复完成：把 `facts_summary` 任务文本合并进 chain record 后，self-retrieval recall 从 0.5% 恢复到接近/达到 100%。
- GRPO headroom 诊断完成：当前 DPO 模型在矢量任务上的 beam 多样性不足，不适合继续做 GRPO 训练。
- 开放式 QGIS landing 人工审核完成：80 条任务 modality match 100%，但严格语义分级为 A=2 / B=23 / C=55。
- 端到端原型已跑通：自然语言/L3 planning + QGIS landing 可以输出规则有效的 QGIS 算子链。

当前重点：保留 DPO v2 L3 模型作为 GEE / 遥感 / 栅格规划基座，并把新构建的 QGIS-derived canonical vector planning dataset 作为补齐传统矢量规划短板的主要数据来源。主指标应回到系统能否规划出正确的矢量处理步骤/意图；QGIS landing 指标仍只是这些规划能否落到可执行 QGIS 链的辅助证据。

2026-06-24 最新训练阶段审查：本次只读审查了当前 V4.6 vector / QGIS SFT 训练阶段。结论是，保守的 Step8 quality-gate + QGIS-vector 包结构上比后来 `vector_v2` / API-trace 这条线更干净。需要长期记住的风险包括：from-scratch 训练如果只传较小 `--num-epochs`，会因为固定 10 个 TF phase 而全程 teacher forcing；`--length-stats` 默认仍会读旧 quality-gate stats，训练 mixed/vector 包时必须显式传包专属 stats；`train_v4_6_vector_unified.py` 的说明、真实路径和 checkpoint 命名已不一致；`vector_v2` 把生成的 QGIS/LLM 样本放进了 val/test；`API_trace_to_L3_TRAINING_FINAL.jsonl` 存在占位 prompt、低置信 LLM label、同 prompt 多 label 冲突；`_upsample_splits.py` 生成重复 split index，而当前 split validator 会拒绝。下一步应固定唯一权威训练入口/数据包，显式传 vocab/stats 路径，让生成矢量样本只进 train，对低置信 LLM/API-trace 样本过滤或降权，并用手写 held-out vector prompts 评估，而不是只看 train-source seed absorption。

2026-06-24 后续修复：上述高优先级训练入口问题已补丁并本地验证。`train_v4_6_quality_gate.py` 现在默认阻止 from-scratch TF-only 短训，只有显式 `--allow-tf-only-smoke` 才允许继续；`--length-stats` 默认改为 `None`，可以检测并提示隐式默认值；`_push_and_train.py` 与 `_upsample_splits.py` 默认直接退出，除非显式传 `--force-deprecated`；`train_v4_6_vector_unified.py` 在缺少统一包专属 length stats 或未显式传 `--length-stats` 时会拒绝运行。验证结果：四个脚本 py_compile 通过；TF-only dry-run 会被阻止；显式 TF-only smoke 可通过；oversampled warmstart dry-run 通过，统计为 81,137 workflows，train/val/test=65,748/7,694/7,695，48 task types，`tf_phase_epochs=0`。

2026-06-24 数据门禁后续修复：已实现并验证 API-trace 弱监督清洗。新增 `scripts/clean_api_trace_l3_training_data.py`，把原始 `outputs_v2/API_trace_to_L3_TRAINING_FINAL.jsonl` 切分为 clean / weak / rejected / conflicts，并写入 `_training_quality` 元数据。`server_batch_api_to_l3.py`、`server_batch_source_to_l3.py`、`llm_generate_l3_from_api_traces.py` 的 LLM prompt 和 quality gate 已改为低置信/无 GIS 证据时拒绝或返回空链，不再鼓励强猜。最新本地清洗结果：6,031 原始行 -> 1,112 clean、1,384 weak、3,535 rejected，另有 1,367 conflict rows、513 个 conflict prompts。主要拒绝原因是 same-prompt 多标签冲突 1,109、task/L3 模态错配 915、task/code 错配 874、placeholder prompt 279、低置信 174、缺失置信度 165。边界：weak 行不能等权进 SFT，rejected 行不能训练；clean API-trace rows 仍需先封装成 train-only Step8 兼容包，不能直接混入 val/test。

2026-06-24 训练机制后续修复：V4.6 训练路径现在开始直接服务“矢量规划能力提升”，而不是只修 retrieval/landing。已完成：`TaskConditionedL3DatasetV4` 返回 `_training_quality.sample_weight`；Teacher Forcing 和 AR scheduled-sampling loss 都使用 per-sample weighted CE；训练 prompt 改成结构化 `Task type / Task name / Goal`，默认 `--max-text-length 256`；sampler 支持 task type、vector family、source quality、confidence、sample weight 组合加权；非默认训练包必须使用同目录或显式传入的 length stats；正向 `qgis_unmappable_penalty` 因方向不安全被拒绝；AR scheduled-sampling horizon 现在可通过 `--ar-max-steps` 配置；评估 inferencer 支持 `legacy|structured` prompt style，旧 DPO/SFT checkpoint 默认保持 legacy；QG parent inferencer 明确保留 legacy 128-token prompt，避免破坏旧主线。未完成：还没有跑新的 GPU 全量训练，因此不能声称矢量规划能力已经提升。当前阻塞：需要服务器 warmstart SFT 和 held-out vector-family recall 评估。下一步：用 oversampled 主线包、显式 vocab/stats、`--enable-family-sampler`、`--max-text-length 256`，并优先加 `--ar-max-steps 32` 训练；评估新结构化 prompt 模型时 SFT 传 `--sft-prompt-style structured`，旧 DPO baseline 继续 legacy。验证：相关 unittest、py_compile 和 oversampled dry-run 均已通过；默认 AR horizon dry-run 显示 train 65,748，无 256 prompt 截断、无 100 token 序列截断、`tf_phase_epochs=0`，family sampler 覆盖 intersection/union/difference/geometry_repair/CRS 等目标族；`--ar-max-steps 32` dry-run 将超过 AR horizon 的 train sequences 从 3,219 降到 545。

2026-06-24 评估 source 门禁补充：`train_v4_6_quality_gate.py` 现在默认在 val/test split 中发现生成/LLM/API-trace 来源时直接失败，阻断标记包括 `qgis_vector_augment`、`llm_source_code_to_l3`、`llm_api_trace_to_l3`、`api_trace_to_l3`、`api_trace`。这直接修复此前 `vector_v2` 评估污染风险。旧诊断若必须复现污染包，可显式传 `--allow-generated-eval-sources`；dry-run summary 会写入 `eval_source_guard`。最新 oversampled warmstart dry-run 显示 `eval_source_guard.status=clean`、`generated_eval_rows=0`。这是数据/指标可信度修复；真实矢量规划能力是否提升仍需服务器训练和 held-out family 评估证明。

## 仓库区域

| 区域 | 用途 | 当前状态 |
| --- | --- | --- |
| `src/gis_recommend/` | 运行时代码：配置、推理、映射、评测、KG 相关工具 | 默认路径大部分已切到 `outputs_v2` |
| `outputs/` | 旧版 350-L3 输出 | 仅作为兼容和 env override 保留 |
| `outputs_v2/` | 修复后的 94-L3 输出和 v2 pipeline 产物 | 当前默认数据根目录 |
| `../L1`, `../L2`, `../L3`, `../L3_classification` | 原始分类和平台映射来源 | 参考/遗留数据源 |
| `scripts/` | pipeline、audit、KG 构建、映射修复脚本 | 仍混有 v2 脚本和旧脚本 |

## 当前数据真相

| 项目 | 当前结论 |
| --- | --- |
| L3 词表 | `outputs_v2/classification_hierarchy_v2.csv`，94 个 L3 |
| ID 映射 | `outputs_v2/id_mappings_v2.json`，94 个 L3 |
| GEE 映射 | 修复后 551 个 active mapping，67 个 skip |
| QGIS 映射 | v2 metadata 中 447 个 QGIS 条目；不做阈值过滤时覆盖 75 个 L3 |
| Canonical vector planning dataset | `outputs_v2/canonical_vector_planning_dataset.jsonl` 已存在，包含 2,319 条 QGIS-derived planning 记录。本地核验：1,598 条 vector / 456 条 raster / 265 条 mixed；全模态 full-L3 记录 1,046 条，其中纯矢量 full-L3 记录 733 条；2,319 行都有非空 `task_text`。Top required vector step families 为 `crs_transform` 596、`buffer_analysis` 519、`spatial_overlay` 423、`attribute_filter` 412、`geometry_repair` 401、`spatial_clip` 391。 |
| Clean vector SFT seed | `outputs_v2/canonical_vector_clean_sft_seed.jsonl` 已存在，包含 685 条结构 clean 的矢量 SFT 记录。最新本地核验：全部为 vector、full-L3、无空 L3、无 `other` step、无当前词表非法 L3、链长 2-15、task text 和 QGIS chain 均唯一。Overlay/centroid remap 已在本地修复：无 `L3_02_05_04`；intersection/difference/union/symdiff 不再塌缩到 Clip。 |
| Step8 QGIS vector SFT package | `outputs_v2/pipeline/step8_qgis_vector_sft/` 已存在，是由 685 条 clean vector 行生成的 Step8 兼容包。文件包括 `labeled_workflows_l3_v4_qgis_vector.json`、`dataset_splits_qgis_vector.json`、`task_type_vocabulary_qgis_vector.json` 和 `manifest.json`。最新本地核验：685 条 workflow，train/val/test 为 548/68/69，split 精确覆盖 0-684，token id 全部在 0-93，无缺失 task metadata，source 全部为 `qgis_vector_canonical`，本地单任务类型为 `"Vector Analysis": 0`，L3 序列长度 min/avg/max 为 2/4.657/15。V4.2 和 V4.6 quality-gate 训练入口都能 dry-run 读取该包，V4 training-entry smoke 能在 CPU 上完成一次前向。 |
| Step8 quality-gate + QGIS vector merged package | `outputs_v2/pipeline/step8_quality_gate_qgis_vector/` 已存在，是保守合并训练包：76,884 条 quality-gate GEE workflow 加 685 条 QGIS vector workflow。最新本地核验：77,569 条 workflow，train/val/test 为 62,180/7,694/7,695，split 精确覆盖 0-77,568，48 个 task type，`"Vector Analysis": 47`；QGIS 行连续追加在尾部索引 76,884-77,568 且只进入 train；没有 0-93 之外的普通 token id，原 GEE 行保留 `-3`/`-4` special；跨 split 的 content L3 序列重复为 0；真实 QGIS 样本能以 task type id 47 完成 CPU 前向。2026-06-07 服务器 CUDA smoke 证明 from-scratch 和 expanded-warmstart 两条路线都能执行。当前 warmstart 明显更强：DPO v2 47->48 扩展 checkpoint 加 5 个 AR-SS epoch 的 best validation composite 为 0.5922（epoch 1），test AR SetF1 为 0.523；from-scratch 5 个 TF-only epoch 的 best validation composite 为 0.4916，test AR SetF1 为 0.445。服务器 vector-impact smoke 显示 QGIS seed 吸收明显且 GEE 污染较小：GEE strict-vector rate 从 DPO 0.4% 到 SFT 2.0%（+1.6pp），QGIS seed 从 DPO 1.7% 到 SFT 53.7%（+52.0pp）。 |
| Step8 quality-gate + QGIS vector oversampled package | `outputs_v2/pipeline/step8_quality_gate_qgis_vector_oversampled/` 已存在，是更高 QGIS 占比的矢量 SFT 包。本地 2026-06-07 核验：81,137 条 workflow，train/val/test 为 65,748/7,694/7,695，split 精确覆盖 0-81,136，48 个 task type 且 `"Vector Analysis": 47`，4,253 条 QGIS vector 行位于尾部索引 76,884-81,136 且全部只进 train，没有 0-93 之外的普通 token id，并已生成该包专用 `task_type_length_stats.json`。Vector Analysis 长度统计为 count 4,253、mean 5.6、median 5、p90 10。按 `l3_sequence` 统计的 QGIS 目标 token 行覆盖：intersection 1,038、union 359、difference 638、symdiff 50、clip 1,440、dissolve 1,541、field_calculate 781、centroid 1,322、geometry_cleanup/repair 1,580。服务器 warmstart 训练已完成：先从该包重建 `outputs_v2/transition_allowed_next.json` 到 60 个转移状态，best validation composite 为 0.5895（epoch 1），test AR SetF1/LCS/earlyEOS 为 0.540/0.397/11.3%。Held-out 泛化显示矢量模式更强，但 overlay 细粒度语义仍未解决：vector measurable recall 3.8% -> 27.8%，vector token rate 1.5% -> 57.6%，raster controls 的 vector-token contamination 仍为 0.0%，但当前 prompt 集上 intersection/union/difference recall 仍为 0。 |
| Step8 v2 audit | 1,091,910 个 L3 token 全部匹配当前映射；missing 0，mismatch 0，skip leak 0 |
| Step6/7/8 provenance | 代码现在会写入并报告 mapping provenance warning；但现有 `outputs_v2` Step6-8 产物早于该机制生成，当前 audit 会报 `missing_provenance`。Phase 15C 下 provenance warning 只能 report-only，不能作为执行门禁 |
| Step8 来源计数 | `manual_override`: 920,726；`auto_remap`: 113,841；`audit_override`: 57,055；`manual_25_override`: 288 |
| Dataset splits | `outputs_v2/dataset_splits_v4.json` 现在精确覆盖 107,399 条 Step8 workflow：train 85,919 / val 10,739 / test 10,741，越界 0，缺失 0 |
| Step8 + V4.6 主线运行契约 | `gis-evaluate` 现在会在报告中写入显式 `MainlineRunContract`。Token profile 为 `v2_94_l3`：主线指标会剥离 Step8 负数 special（`-1..-4`）和 V4.6 内部 special（`94..97`）；legacy `350..353` 只在显式 `legacy_350_l3` profile 下剥离。Data authority 默认绑定 Step8 v2 workflow/split/task-vocab/id-mapping/checkpoint 路径和 `outputs_v2/qgis_operator_io_types.json`；如果该 I/O metadata 文件缺失，诊断降级为 missing metadata，不再静默读取 legacy `outputs/`。`QGISCandidateGenerator`、`CandidateVerifier`、后置 QGIS evaluation、executable diagnostics 和报告 decision trace 现在在可用处都消费/记录同一份 authority。 |
| 训练数据质量审计 | 已生成 `outputs_v2/pipeline/audit/training_data_quality_audit.*`；schema 干净，但仍有模型训练风险：60/94 个 L3 活跃，Top10 L3 占 70.20%，67 个 task type 少于 10 条，val/test 有 train 未见 task type，5,934 个跨 split 重复 L3 序列，50,036 个低置信 token |
| API-trace L3 训练数据门禁 | `scripts/clean_api_trace_l3_training_data.py` 现在会在 `outputs_v2/diagnostics/api_trace_l3_cleaning/` 下输出保守切分：`API_trace_to_L3_TRAINING_CLEAN.jsonl` (1,112)、`API_trace_to_L3_TRAINING_WEAK.jsonl` (1,384)、`API_trace_to_L3_TRAINING_REJECTED.jsonl` (3,535)、`API_trace_to_L3_TRAINING_CONFLICTS.jsonl` (1,367)，以及 JSON/Markdown 报告。clean 切分会排除 placeholder `QGIS script: script_xxx`、显式自拒 reason、同 prompt 多 label 冲突、task/code 错配 reason、task/L3 模态错配、缺失/非法/低置信度，以及明确“只靠描述推断”的模式。它只是数据门禁，还不是最终训练包构建。 |
| GEE 官方名称对齐 | 当前 Step8 使用 306 个唯一小写 GEE operator。306/306 都能大小写不敏感匹配 `id_mappings_v2.mapping_metadata.gee_to_l3`，所以 GEE->L3 标注没有因大小写丢 token。但只有 45 个与 metadata key 完全一致，295 个能大小写不敏感匹配爬取的官方 operator `name`，还有 11 个高频已映射 operator 不是官方 `name` 的直接命中；后续官方 API grounding / 代码生成仍需要 canonical alias 审计表。 |
| 质量门禁版 V4 候选集 | `outputs_v2/pipeline/step8_quality_gate/` 已生成且没有覆盖原 Step8。候选集 76,884 条 workflow、657,314 个 L3 token，分组 split 为 61,495 / 7,694 / 7,695，覆盖完整且跨 split 重复 L3 序列 hash 为 0。已 quarantine 30,515 条含低置信 `auto_remap` token 的 workflow，合并 116 条稀疏 task workflow；剩余审计告警是 inactive L3、L3 分布倾斜、222 个非 auto_remap/manual_25 低置信 token。质量门禁长度统计已生成：`outputs_v2/pipeline/step8_quality_gate/task_type_length_stats.json`，按 content L3 token 计数，global median 7、mean 8.5、p90 16，覆盖 47 个 task type。 |
| 质量门禁 transition matrix | `outputs_v2/transition_allowed_next.json` 是当前 V4.6 训练/评测路径读取的全局 transition matrix。基础 quality-gate 训练时该文件从 quality-gated train split 重建：61,495 条 workflow、48 个状态、587,479 条转移、越界转移 0。QGIS-vector 过采样服务器 run 又从 `step8_quality_gate_qgis_vector_oversampled` 重建同一全局文件：65,748 条 train workflow、60 个状态、607,006 条转移、越界转移 0。不要复制/使用 `outputs/transition_allowed_next.json`；旧文件含 350-L3 token id，例如 352，不兼容 v2 的 98-token 训练词表。注意该文件是全局状态；重建后后续 SFT 和 DPO 评测都会读 60-state matrix，所以同一次 SFT-vs-DPO 对比仍对齐，但不能和早先 48-state 报告做完全严格横向比较。 |
| 质量门禁训练入口 | 历史入口 `scripts/train_v4_quality_gate.py` 会用质量门禁候选集训练 V4.2 Transformer，输出到 `outputs_v2/transformer_checkpoints_v4_2_quality_gate`。`scripts/train_v4_6_quality_gate.py` 输出到 `outputs_v2/transformer_checkpoints_v4_6_quality_gate`，对应的 Set Predictor 路径是 `outputs_v2/set_predictor_checkpoints_v3_quality_gate_v4_6`。这些是 quality-gate candidate/research 路径，不是当前 Step8 + V4.6 `gis-evaluate` 主线；严格非 dry-run 训练要求存在 v2 transition matrix。 |
| 实证评测 artifact | `outputs_v2/evaluation_reports/empirical_v2_smoke_artifact.json/.md` 已存在，schema 为 `gis_recommend.empirical_evaluation.v1`。这是 baseline-only / model-optional 的 20 样本 smoke artifact，持久化逐样本 baseline 预测、beam candidates、decode trace、token probability proxy、END timing、重复统计、candidate/retrieval/reranker diagnostics、split/checkpoint metadata、dataset structure audit、canonicalization audit、decode-policy summary 和 bottleneck attribution。当前 smoke 中 LCS 最好的 baseline 是 `lexical_retrieval` = 0.453342。它不是受控 v2 模型预测报告。 |
| V5 hybrid planner prototype | `outputs_v2/v5_final_reports/v5_hybrid_planner_prototype/` 已生成 retrieval-centered / checkpoint-only hybrid planner 报告。该路径保持 retrieved workflow structure 为锚点，只用 V5_final 对完整候选做 plausibility/rerank，不重训，也不让 autoregressive generation 替代 retrieval。当前 50 样本 artifact：hybrid LCS 0.46504845 / SetF1 0.59205726 / token accuracy 0.33411111 / IO validity 1.0；retrieval-only LCS 0.44371511 / SetF1 0.56734786 / token accuracy 0.31911111。当前被选中的 hybrid candidates 全部是 retrieval pool 中的 identity candidates，因此本次提升来自 retrieval-pool selection，不是 local edit improvement。 |
| V5 multistage hybrid planner | `outputs_v2/v5_final_reports/v5_hybrid_planner_multistage/` 已生成下一版 retrieval-centered evaluation artifact。检索源包括 lexical、embedding、intent、workflow-structure 和 graph-aware L2/L3-code features，并用 lexical-primary 权重融合。Safe rerank 防止低 retrieval confidence 候选替换检索锚点。当前 50 样本 artifact：hybrid/retrieval-only LCS 0.45586827，SetF1 0.57529907，token accuracy 0.33928243，IO validity 1.0。Safe policy 下 rerank contribution 和 repair contribution 都是 0.0；全部被选候选仍是 identity workflows。 |
| Retrieval planning stages | `scripts/evaluate_retrieval_planning_stages.py` 新增 retrieval-centered 阶段评测：Set Predictor 兼容的检索过滤、execution-aware rerank、本地局部修复；不训练、不改架构。输出目录为 `outputs_v2/v5_final_reports/retrieval_filtering/`、`execution_aware_rerank/`、`local_repair/`，另有整体 trace/summary。当前 50 样本 artifact 因本地缺少训练好的 Set Predictor checkpoint，使用 train split task-type operator-frequency prior fallback：retrieval-only LCS 0.46677086 / SetF1 0.60017391 / token acc 0.33272688；soft filtering LCS 0.46415182 / SetF1 0.60287787 / token acc 0.32606021；execution-aware rerank LCS 0.45731716 / SetF1 0.61339037 / token acc 0.26513428；local repair 全部选择 identity，因此 repair contribution 为 0.0。这些是 retrieval/filter/rerank/repair 量化，不是 generation gain。 |
| 历史规划检索机制审计 | 当前运行证据显示，history-based planning retrieval 只在 research/evaluation 路径中部分实现。"历史"来源是 train split workflow JSON（`outputs_v2/pipeline/step8_quality_gate/*` 或 Step8 split），不是持久化用户历史、case 库或 feedback 数据库。`LexicalRetrieval` 和 `empirical.py` 检索会从 train workflows 临时构造内存索引/候选池；V4-QG planner 和 V5 research 脚本可以把这些候选用于 rerank/filter/repair，但 Step8 + V4.6 `gis-evaluate` 主线仍从 V4.6 beam 输出中选择，并不调用历史检索路径。当前代码/输出树未发现持久化 FAISS、sqlite、vector store、retrieval index 或自动 feedback updater。 |
| Repair oracle phase | `outputs_v2/v5_final_reports/repair_oracle_phase/` 已生成 evaluation-only local repair oracle 报告。候选池只使用显式局部编辑：substitution、bridge insertion、deletion、local swap。当前 50 样本 artifact 使用本地 set-prior fallback：mean oracle repair gain 为 LCS +0.12149891 / SetF1 +0.1027359 / token accuracy +0.13011901；repair win rate 0.88，repair corruption rate 0.02，repair selection failure rate 0.88。Retrieval-pool oracle gain 更高，LCS +0.24863413。Failure taxonomy 为 `rerank_failure:44`、`repair_quality_failure:3`、`retrieval_saturation:3`，说明有用局部修复经常存在，但当前 scoring/reranking 识别不了。 |
| Repair selection diagnostics | `outputs_v2/v5_final_reports/repair_selection_diagnostics/` 已生成 evaluation-only repair selection 诊断报告，只读取已有 repair oracle traces。相同 50 样本上：identity selection frequency 1.0，modified selection frequency 0.0，margin 0.05 下 modified near-miss rate 0.02；oracle repair 相比 selected 平均 score delta 为 -0.19874815，但 oracle LCS gain 为 +0.12149891。4,939 个 modified candidates 的最大负向项全部是 `edit_penalty`。Failure breakdown 为 `edit_oversuppression:44`、`retrieval_saturation:6`。Conservative / balanced threshold sweep 采用 0 个 repair；aggressive margin -0.10 采用 18%，但 mean LCS 只 +0.00266667。随机 modified selection 为负收益（mean LCS -0.05363936），所以当前问题是 scoring/calibration，不是可以随机或无条件接受 repair。 |
| Repair scorer ablations | `outputs_v2/v5_final_reports/repair_scorer_ablations/` 已生成 evaluation-only scorer ablation 报告，只对已有 repair oracle candidate pools 重新打分，不访问模型或 checkpoint。完全移除 edit penalty 会采用 100% repair，但有害：mean LCS -0.0132707，corruption 0.32。当前测试的 piecewise operation penalties 也有害：mean LCS -0.01555742，corruption 0.26。Execution/set-heavy weighting 也有害：mean LCS -0.0178352，corruption 0.28。在 50 样本 trace 上，uniform edit penalty 从 0.20 降到 0.12 是最好的低腐蚀候选：adoption 0.08，corruption 0.02，mean LCS +0.00333333，SetF1 +0.00488889，token accuracy +0.00952381。这只是 evaluation-only 小样本建议，不是 production scoring change。 |
| Repair calibration sweep | `outputs_v2/v5_final_reports/repair_calibration_sweep/` 已在更大的 200 样本 repair oracle trace 上测试 uniform edit penalty 0.0/0.08/0.10/0.12/0.14/0.16/0.20。200 样本 trace 仍有 oracle repair gain（LCS +0.12405501，SetF1 +0.10355055，token accuracy +0.17590497），但实际选择 repair 的策略不稳定。`uniform_edit_0_12` adoption 13%、corruption 5%、条件 breakage 38.46%、mean LCS -0.00111538，bootstrap LCS CI 为 [-0.00838557, +0.00748109]。没有任何被测 penalty 达到低腐蚀且稳定正收益；0.0 collapse，0.08 over-adopt，所有区域都被标记为 unstable。该结果推翻了 50 样本 `0.12` 可生产化的暗示。 |
| Repair opportunity analysis | `outputs_v2/v5_final_reports/repair_opportunity_analysis/` 已生成 evaluation-only 条件 repair 归因研究，输入是 200 样本 held-out repair trace。Oracle repair gain 仍存在（mean LCS +0.12405501 / SetF1 +0.10355055 / token accuracy +0.17590497），但多数机会信号较弱或不稳定：17 个信号绝对相关低于 0.10，21 个 bootstrap interval 跨 0。可作为后续筛选线索的方向性信号包括 retrieved-set reference deficit、length-ratio error、较低 identity repetition/redundancy、best-repair LCS retention；IO transition 信号在该 trace 中无信息量，因为 identity 和 modified invalid-transition rate 都是 0。宽泛指标几乎触发所有样本，不能作为 runtime gate。 |
| Repair confidence regimes | `outputs_v2/v5_final_reports/repair_confidence_regimes/` 已生成 evaluation-only 高置信 repair regime 搜索，输入是 200 样本 held-out repair trace。该阶段评估 19,919 个候选，其中 19,719 个是 modified candidates，并输出 subtype/context 分解、precision-first regime search、bootstrap validation 和 random controls。没有任何 score-selected regime 满足低腐蚀高置信条件（`score_selected_high_confidence_regime_count=0`），但有 12 个 oracle-only subspaces 通过；这说明 repair opportunity 仍存在，但尚未证明存在可部署的稳定 runtime repair policy。Random modified selection 有害（median LCS delta -0.0542，median corruption 0.455），random narrow gating 也为负（median LCS delta -0.0054）。 |
| Unified workflow benchmark | `outputs_v2/v5_final_reports/unified_benchmark/unified_workflow_benchmark.json/.md` 已把当前多任务 benchmark family 放进同一份 artifact，但不混用指标：V4 quality-gate teacher-forced token prediction、V4 quality-gate AR rollout、V5_final rollout、retrieval-centered planning、hybrid planning、Set Predictor set prediction。V4 和 Set Predictor 数值目前来自用户提供的服务器结果，因为原始 history/checkpoint 目录尚未同步到本地。 |
| System consolidation protocol | `docs/v5_system_consolidation_protocol.md` 是项目级综合协议，统一记录最终系统身份、架构语义、已证明/未证明能力、治理边界、生产解释和研究路线图。它正式定义当前系统是 retrieval-centered、execution-aware、rerank-driven、constrained-planning-oriented，并明确当前证据不支持 autonomous generation 或 deployable repair 声明。 |
| L2 semantic recovery protocol | `docs/v5_l2_semantic_recovery_protocol.md` 在 runtime consolidation 之后恢复长期 L1->L2->L3 架构边界。它明确当前 L3/operator-token 检索运行时只是经验简化，保留 L2 作为平台无关语义意图层，并禁止把检索成功解释成语义抽象不必要或已经被验证。 |
| Semantic retrieval stress evaluation | `outputs_v2/v5_final_reports/semantic_retrieval_stress/` 已生成 evaluation-only 的 lexical/operator-level retrieval 语义扰动压力测试。50 个 held-out 样本、371 个确定性扰动上，wording reorder 完全稳定，platform wording 和轻量 synonym/operator alias shift 基本稳定，但 abstraction / semantic paraphrase 明显脆弱：总体 top1 change rate 0.5202，original top1 retention 0.5391，mean topK overlap 0.4542，mean LCS delta -0.0814，SetF1 delta -0.0833，token accuracy delta -0.0793，retrieval saturation failure 0.4070。该结果只诊断 lexical sensitivity，不验证 L2、semantic retrieval 或 semantic planning。 |
| Semantic indexing simulation | `outputs_v2/v5_final_reports/semantic_indexing_simulation/` 已生成 evaluation-only 的手工语义分组模拟。该阶段只用 10 个预定义 alias/intent buckets，不使用模型、checkpoint、embedding、LLM rewriting 或 runtime replacement。在同一 50 样本 / 371 扰动上，粗粒度 grouping 净效果为负：mean top1 retention delta -0.0620，topK overlap delta -0.1067，LCS preservation delta -0.0151，SetF1 delta -0.0227，token accuracy delta -0.0025，retrieval saturation reduction -0.0728。风险较高：semantic drift risk 0.3854，false equivalence 0.3585，execution-invalid grouping 0.0。该结果只估计风险/上限，不实现 semantic retrieval，也不验证 L2。 |
| Controlled equivalence stress evaluation | `outputs_v2/v5_final_reports/controlled_equivalence_stress/` 已生成 evaluation-only 的等价类安全压力测试。50 样本 / 223 个 variants 上，exact alias equivalence 稳定（`n=12`，corruption 0，false equivalence 0），exact unambiguous GEE<->QGIS mapping 为 platform-transfer-safe（`n=12`）；但 ambiguous/composite cross-platform mapping 作为等价声明不安全（`n=49`，false equivalence 1.0）。Same-L2 operator-family substitution 是 execution-breaking / unsafe（`n=50`，execution-invalid 0.46，corruption 0.68）。Workflow reorder 和 bridge expansion 当前证据下也不安全（各 `n=50`；reorder corruption 0.58，bridge corruption 0.96）。该阶段只识别窄安全类，不实现 semantic retrieval，也不证明全局 execution-preserving equivalence。 |
| Bounded ontology inventory | `outputs_v2/v5_final_reports/bounded_ontology_inventory/` 已生成第一版离线 bounded semantic ontology inventory。它基于当前 GEE/QGIS 映射和 GDAL/ArcGIS unsupported 行，共分类 3,800 个 operator-pair rows：exact 13、execution-sensitive 98、partial 691、ambiguous 2,989、composite 4、unsupported 5。Exact 行被刻意限制为很窄的 GEE<->QGIS 候选，主要是 Buffer 和 Mosaic。GDAL/ArcGIS 因当前没有映射资产而明确标为 `unsupported`。这是 inventory/governance artifact，不实现 semantic retrieval、L2 runtime authority、ontology inference 或 platform translation。 |
| Canonicalized workflow evaluation | `outputs_v2/v5_final_reports/canonicalized_evaluation/` 已生成严格 evaluation-only 的 raw-vs-canonicalized 指标报告。该阶段只复用 train split 中经验发现的 commutative pairs 和 `empirical.py::_canonicalize_sequence()`，不引入语义分组。对 empirical smoke、Stage1 V5 generation 和 hybrid planner artifact 中 369 条持久化预测记录评测后：raw EM 0.0 -> canonicalized EM 0.00542005，LCS +0.0173991，token accuracy +0.06013034，SetF1 +0.01039799。Bootstrap 下 LCS/token accuracy/SetF1 增量多数为正，但 exact recovery 只有 2 条，TopK canonical recovery 只有 6 条。该结果证明 raw sequence metric 会低估部分合法重排序质量，但不是 runtime、retrieval、training、semantic grouping 或 architecture 改动。 |
| Workflow usability evaluation (v1, prediction-record) | `outputs_v2/v5_final_reports/workflow_usability_evaluation/` (v1) 读取 369 条持久化预测记录：Top1 usable 0.035，Top3 0.062，Top5 0.068；`v5_final` pure generation usable rate 0.0。该旧版 artifact 已被下方 v2 取代。 |
| Workflow usability evaluation (v2, self-contained) | `scripts/evaluate_workflow_usability.py`（2026-05-13 重写）是自包含的 evaluation-only pipeline，不需要模型、checkpoint、训练、语义检索、LLM 评判或执行模拟。直接在 200 个质量门禁测试样本上用 7 个严格规则指标评估 lexical retrieval baseline，使用 L1/L2 分类层次类别和 QGIS 映射。关键结果：**Top-1 可用率 0.5600**（56% 测试任务的 Top-1 retrieval 候选可用），**Top-3 任意可用 1.0000**，**Top-5 任意可用 1.0000**（每个任务在 Top-5 中都能找到 >=1 个可用 workflow）。平均可用性得分 0.7663 [95% CI: 0.7552, 0.7780] 超过参考序列 0.7207。平均 QGIS 映射率 0.6365，平均逻辑一致性 0.9368，平均步骤覆盖率 0.6197。主要失败类别：FP04 连续重复 (84)、FP02 导出在加工前 (83)、low_qgis_mapping (60)。发现 533 个交换算子对。76/94 个 L3 代码有 QGIS 映射。这是实用可用性估计，不是序列相似度——表明即使 LCS/SetF1 很低，retrieval 也已经能产出可用链。 |
| V4-QG planner Phase 1 candidate rerank | `scripts/run_v4_qg_planner.py` 是当前实用 V4-QG planner 入口，用于 candidate-pool + constraint-aware rerank。默认指向 V4.6 quality-gate checkpoint 和匹配的 V4.6 Set Predictor checkpoint 路径。该脚本只做 evaluation/rerank：不训练、不改 checkpoint、不改架构、不做语义分组、不用 LLM 评判。由于本地缺少 checkpoint，当前运行使用质量门禁 lexical retrieval 候选和 train-split task-type operator-frequency set prior fallback。1,000 个质量门禁 held-out 样本上，retrieval Top1 可用率为 0.6330，而 rerank 后 selected Top1 可用率为 1.0000；原因是每个样本 Top5 中至少有一个规则可用候选，而 rerank 现在优先选择规则可用候选。平均 selected usability score 0.8449，平均 QGIS mapping rate 0.8082，logic consistency 0.9974，forbidden-pattern scan 通过。这是实用规则可用性，不是语义正确性、参数有效性或真实 QGIS 执行证明。 |
| Multi-reference workflow evaluation | `outputs_v2/v5_final_reports/multi_reference_evaluation/` 已生成严格 evaluation-only 的 single-reference vs multi-reference 报告。多参考答案只允许来自现有 labeled workflows 中 exact normalized task text/name 匹配，再加原始参考答案；不使用 semantic embeddings、LLM judging、runtime 改动、retrieval redesign 或 execution simulation。对同一批 369 条持久化预测记录，保守 reference pool 的 mean reference count 为 1.0，multi-reference record rate 为 0.0，因此 best-of-multi-reference raw deltas 全部为 0.0。Canonicalized multi-reference 复现 canonicalization 提升：EM +0.00542005，LCS +0.0173991，token accuracy +0.06013034，SetF1 +0.01039799，有 2 条 canonical exact recovery、139 条 LCS 改善。当前 artifact 说明存在顺序/规范化导致的指标低估，但无法证明显式多参考答案带来的大幅恢复，因为评测样本几乎没有显式多参考标注。 |
| Multi-reference validation experiment | `scripts/evaluate_multiref_validation.py` 是 evaluation-only MRV runner，用来验证当前 quality-gate GEE workflow 数据是否足以支撑可靠多参考监督。它从 train split 的 commutative pairs 生成相邻交换变体，执行 workflow-semantic gate（敏感步骤、semantic usability、non-degradation、长度保持），并把 QGIS landing 只作为 downstream transferability 辅助信号记录。当前 50 workflow / 100 variant smoke artifact 位于 `outputs_v2/v4_qg_multiref_validation/`：19 个 `verified_equivalent_candidate`、81 个 `invalid_variant`、19 条 auto-verified registry candidates、15 条分层 human-review sample，以及 19 行带可读 L3 名称的 `equivalence_review_packet.csv`。2026-05-15 人工审查初始结果是 14 条 `equivalent`、4 条 `uncertain`、1 条 `not_equivalent`；随后对 4 条 uncertain 做 source inspection，并把 `wf46_pos2_swap53_28` 因 ImageCollection->Image object-chain break 降级为 `not_equivalent`。当前标签是 14 条 `equivalent`、3 条 `uncertain`、2 条 `not_equivalent`；`verified_multi_reference_registry.json` 仍只收 14 条人工接受的等价变体，并按 task 汇总为 7 个 reviewed task groups。QGIS landing 仍弱（`qgis_mapping_valid_rate=0.0`），但不再阻塞 GEE workflow-level MRV 标签。 |
| MRV expansion and equivalence taxonomy | `outputs_v2/v4_qg_multiref_validation_expansion_500/` 已生成 500-variant MRV expansion。该阶段从 200 个 workflow 和 53 个 discovered commutative pairs 生成 500 个相邻交换变体：46 个 auto `verified_equivalent_candidate`、454 个 `invalid_variant`，semantic auto pass rate 0.092，semantic usable rate 0.116，guard pass rate 0.9。`configs/equivalence_taxonomy.yaml` 正式记录 family/risk/rejection 分类；`scripts/analyze_mrv_expansion.py` 会输出 family/risk/rejection summary。Family 分布：`filter_filter=203`（auto pass 0.1281）、`select_filter=63`（0.1746）、`select_clip=17`（0.0588）、`reducer_or_aggregation=96`（0.0208）、`mask_threshold_or_logic=26`（0.0769）、`high_risk_sensitive=6`（0.0）、`other=89`（0.0449）。Risk 分布：low 203、medium 80、high 128、unknown 89。QGIS `landing_only_failure=500` 只是辅助 transferability signal，不能否定 GEE workflow equivalence candidate。46 个 auto candidates 在人工审查前不能作为训练标签。 |
| MRV expansion AI-assisted review draft | `outputs_v2/v4_qg_multiref_validation_expansion_500/equivalence_review_packet_ai_review.csv` 和 `equivalence_review_ai_summary.*` 已完成对 46 个 auto candidates 的第一轮审查草案。按用户复核后的 family 边界，当前草案标签为 36 条 `equivalent`、8 条 `uncertain`、2 条 `not_equivalent`：`metadata_mosaic` 判 uncertain，`select_zonal` / `select_temporal` / `select_logical` 判 uncertain，`mask_logical` 判 not equivalent。Equivalent drafts 主要来自 filter/filter、select/filter/date-select、clip/select、clip/arithmetic，以及 1 条 source-inspected independent select/arithmetic branch。明确 reject 是已知的 `wf46_pos2_swap53_28` ImageCollection/Image object-chain conflict 和 `wf63_pos4_swap29_35` mask/logical failure。`verified_multi_reference_registry_ai_draft.json` 将 36 条 draft-equivalent 变体汇总为 19 个 task groups，但在用户确认并晋升到 manual registry 前，仍**不能作为训练标签**。Expansion 46 条包含第一批 19 条，因此全局总数必须按 `variant_id` 去重，不能把 19+46 当作唯一候选相加。 |
| Verified MRV registry v2 / equivalence KB | `scripts/build_mrv_registry_v2.py` 已把第一批人工审查和用户确认后的 46-candidate expansion review 合并成正式 registry v2，且不覆盖原始 manual registry。输出位于 `outputs_v2/v4_qg_multiref_validation/`：`verified_multi_reference_registry_v2.json`、`verified_equivalence_kb_v2.json/.csv`、`verified_multi_reference_registry_v2_summary.md`。去重后计数：65 行输入 review -> 55 个唯一 reviewed variants；42 个 `equivalent` variant 只允许进入受控训练消融；23 个 task groups；13 个 excluded variants（`uncertain=10`、`not_equivalent=3`）继续排除在训练标签外。Family 计数：`filter_filter=30`、`select_filter=8`、`select_clip=3`、`other=1`。Risk 计数已清洗：`low=31`、`medium=10`、`unknown=1`；`review_flags` 不再污染 `risk_level`。 |
| Controlled MR training ablation artifacts | `scripts/build_mrv_training_ablation.py` 只从 MRV registry v2 / equivalence KB v2 构造隔离的 quality-gate 派生数据。当前输出位于 `outputs_v2/v4_qg_mr_ablation/`：`mr_5`、`mr_10`、`mr_all_42`，以及 `mrv_training_ablation_manifest.json`。基础 quality-gate 数据为 76,884 条 workflow，train/val/test = 61,495 / 7,694 / 7,695。`mr_5` 输出 76,889 条、train 61,500；`mr_10` 输出 76,894 条、train 61,505；`mr_all_42` 输出 76,926 条、train 61,537。所有版本 val/test 不变，注入样本带 `metadata.mrv_ablation` 和 `quality_gate.mrv_ablation` provenance，manifest 记录 `no_training_started=true`。这些只是消融输入，不是主线数据替换，也不是训练结果。 |
| MR ablation comparison scaffold | `scripts/compare_mrv_training_ablation.py` 是给未来 baseline vs `mr_*` 训练/评测输出使用的只读 report comparator。它会从 planner/usability/canonicalized 风格 JSON 中归一化已知指标 key，计算 metric delta 和 relative delta；当报告含可配对 `per_sample` 行时，会计算 paired bootstrap CI；同时写出 JSON/Markdown 摘要，并记录 no training、no inference、no checkpoint loading、no source-data mutation 等 governance flags。它本身不生成模型指标，只比较已经存在的 report。 |
| MR all-42 V4.6 training result | `结果/transformer训练结果/train_v4_6_quality_gate-mr-0517.md` 记录了服务器上对 `outputs_v2/v4_qg_mr_ablation/mr_all_42/` 的 V4.6 from-scratch 完整训练，checkpoint 写入 `outputs_v2/transformer_checkpoints_v4_6_quality_gate_mr_all_42`。最终 test：Loss 2.9974 / PPL 20.0 / Top1 31.3% / Top5 60.0% / TF-SeqEM 0.6% / AR-SeqEM 0.0% / AR-TokenAcc 18.8%。这还不能作为干净的 MR-vs-baseline 结论：epoch 11 进入 AR scheduled sampling 后反复出现 `Train: Loss=inf`，但 validation 仍是有限值；最终评测加载的是 epoch 50 latest snapshot，而 validation 最好大约出现在 Top1 36.9% / Top5 65.0% 附近。本地 trainer 现在已修复确认到的 AR-SS early-END mask 污染 CE logits 问题：训练 loss 使用未 mask logits，dynamic min-length END 禁止只作用于采样 logits；但必须重跑训练后才能声明 MR 效果。 |

重要区别：Step1-8 训练样本构造走的是 GEE -> L3。`id_mappings_v2.json` 里的 `qgis_to_l3` 不直接影响 Step1-8 训练链路；QGIS 映射主要影响后续 L3 -> QGIS 落地链生成和评测。

## 关键决策

| 决策 | 原因 |
| --- | --- |
| `outputs_v2` 作为默认运行数据根目录 | 修复后的 94-L3 体系显著减少旧 350-L3 噪声 |
| 通过环境变量保留 `outputs/` 兼容 | 旧实验、旧 checkpoint 或对照评测可能仍需要 350-L3 |
| 代码迁移阶段不改大数据文件 | 当前任务是修复消费链路，不是重新生成数据 |
| 本阶段不重跑训练 | 必须先稳定 mapping、路径和 provenance，再考虑训练 |
| KG 构建默认优先读 `outputs_v2/classification_hierarchy_v2.csv` | 避免知识图谱继续使用旧 350-L3 |
| Neo4j KG 导入必须显式且默认只读 v2 | 服务器导入应消费 `outputs_v2` / 94-L3 资产，必须显式提供 Neo4j 密码，只有传 `--clear` 才清库，只有传 `--allow-legacy-inputs` 才允许旧 `outputs/` 兼容输入 |
| Phase0/Phase1 主线改动必须保持 report-only | 可以记录 candidate pool trace、evidence bundle、shadow decision core 和 retrieval shadow source，但不能修改 `pred_tokens`、V4 beam 输出、decoder 行为、训练、legacy metrics 或默认 selection |
| v2 QGIS metadata 顶层 `primary_l3` 对人工决策更权威 | 有些条目的 `all_candidates[0]` 仍是旧自动候选 |
| `manual_reviewed` / `manual_override` 的 QGIS 映射不能被数值阈值过滤掉 | 人工审核是显式决策，低旧分数不应覆盖人工保留 |
| Step8 清洗写最终训练数据前记录 Step6 provenance warning | 让 stale `id_mappings_v2` 或 stale skip list 风险进入报告，但 provenance metadata 不能 gate execution |
| 复用已有 dataset split 前必须按当前 Step8 workflow 数量校验索引覆盖和范围 | Step8 清洗会移除样本；旧 split 曾出现越界索引并导致训练/评测 `IndexError` |
| 质量门禁版 V4 候选集是派生产物，不是源数据 | 保留原 Step8 用于审计追溯；smoke training 或实验必须显式指向 `outputs_v2/pipeline/step8_quality_gate/` |

## 已完成工作

| 日期 | 已完成 |
| --- | --- |
| 2026-06-24 | 重新阅读根目录追踪文件（`task_plan.md`、`progress.md`、`findings.md`）以及 Claude memory 目录 `C:\Users\qiaoyun\.claude\projects\...\memory` 下的项目记忆，并核对本地对应代码和产物。当前 Phase 9 数据口径：`outputs_v2/API_trace_to_L3_TRAINING_FINAL.jsonl` 为 6,031 条去重后的 API-trace→L3 样本，`outputs_v2/vector_training_samples_UNIFIED.jsonl` 为 10,768 条 Route 1+2 unified 样本，`_final_merge.py` 中的“约 16,800”来自 6,031 + 10,768 = 16,799，属于进入后续训练候选前的合并口径。`QGISChainRetriever` 当前已索引 facts 文本字段，并使用 semantic tags、op_match 和 native bridge；因此 QGIS workflow 数据不是“用不上”，而是同时作为 QGIS landing 检索库和矢量规划监督数据来源。安全清理：已移除 `run_process.bat` 中硬编码的 `DEEPSEEK_API_KEY`，并把 `progress.md` 中记录的完整 key 改为环境变量说明。 |
| 2026-06-04 | 用户报告的 open landing 三轮对比显示 `op_match` 和 `sem tags` 方向有效：unique chains 1 → 16 → 33，top-3 concentration 100% → 31%，`native:reprojectlayer -> native:buffer -> native:clip` 模板从 30 次降到 7 次。新增 `voronoi`、`density_heatmap`、`nearest_neighbor`、`raster_sampling`、`zonal_statistics` 等标签后，更多任务能匹配到对应专门链。当前 `+sem tags` modality 为 84%，低于 >90% 目标，但原因是 enrichment 重建数据集时没有合并 facts 文本、混入旧索引；这应视为集成问题，不应解释为 semantic tags 损害 modality。 |
| 2026-06-04 | 完成 `outputs_v2/diagnostics/open_landing_eval/open_landing_results.csv` 的严格人工审核：80 条开放式 QGIS landing 任务，modality match 100%，索引修复后 unique chains 1→16，但严格语义分级为 A=2 / B=23 / C=55。主要失败模式是模板塌缩：30 条落到 `native:reprojectlayer -> native:buffer -> native:clip`，16 条落到 `gdal:warpreproject -> native:reprojectlayer -> gdal:cliprasterbymasklayer`，10 条 mixed 任务落到 `native:reprojectlayer -> native:buffer -> gdal:cliprasterbymasklayer -> gdal:warpreproject`。下一步应补细粒度 QGIS operator bridge/native bridge，而不是继续修 modality 或重训 L3。 |
| 2026-06-06 | 完成一次只读 QGIS 数据可用性梳理，重点判断现有 QGIS 数据对矢量处理能力补强的作用。当前 QGIS 资产应分三类使用：`qgis_chain_dataset*.jsonl` 主要作为可执行 QGIS chain 检索池；`qgis_vector_chain_described.jsonl` 和 `qgis_vector_preference_pairs_clean.jsonl` 适合做弱监督的矢量偏好/排序训练；`open_landing_results.csv` 是人工评测证据。当前没有任何单一 QGIS 数据版本同时具备 facts 文本、semantic tags 和 L3 bridge 三类信号；下一步应先合并出一份 canonical vector landing dataset，再继续 reranker 或 preference 训练。 |
| 2026-06-06 | 重新读取本地当前 `outputs_v2/diagnostics/open_landing_eval/open_landing_results.csv`，该文件当前为 80 行，人工等级统计是 A=18 / B=33 / C=29，不是早期 handoff 中的 A=2 / B=23 / C=55。当前模板集中仍存在但已有改善：`gdal:warpreproject -> native:reprojectlayer -> gdal:cliprasterbymasklayer` 为 14 次，`native:reprojectlayer -> native:buffer -> native:clip` 为 7 次，`native:reprojectlayer -> native:buffer -> gdal:cliprasterbymasklayer -> gdal:warpreproject` 为 5 次。旧等级/模板计数应视为历史阶段证据，除非明确恢复旧 CSV 快照。 |
| 2026-06-06 | 构建并核验 `outputs_v2/canonical_vector_planning_dataset.jsonl`，作为 QGIS-derived 矢量规划监督数据集。该文件包含 2,319 条记录，字段包括 `task_text`、`modality`、`qgis_ops`、抽象 `planning_steps`、`l3_steps`、`has_full_l3` 和 `required_step_families`。核验计数：1,598 条矢量记录，全模态 full-L3 1,046 条，纯矢量 full-L3 733 条，非空 required-step family 共 20 类。该产物把 QGIS 数据的角色从主要 landing/retrieval 证据推进为可直接用于矢量规划 SFT/preference 准备的数据源。 |
| 2026-06-06 | 完成 `outputs_v2/canonical_vector_planning_dataset.jsonl` 的训练质量审计。结构层面是好的：必需字段齐全，2,319 行的 `qgis_ops` / `planning_steps` / `l3_steps` 长度全部对齐，QGIS chain 全唯一，`has_full_l3` 与 L3 空/非空 slot 内部一致。但全量数据质量混杂：59 行任务文本过短，463 行 `required_step_families` 为空，20.4% operator step 是 `other`/空 L3，且 140 行包含当前 94-L3 词表中不存在的 `L3_02_05_04`。因此最干净的即时 SFT seed 不是原始 733 条，而是按纯矢量 full-L3、合法 94-L3 code、task text 长度 >=80、required families 非空、链长 <=15、只含 core provider 过滤后的 610 条。 |
| 2026-06-06 | 核验用户生成的 `outputs_v2/canonical_vector_clean_sft_seed.jsonl`。结构检查通过：685 行，全部 `modality=vector`，必需字段齐全，`has_full_l3=true`，无长度不一致，无空 L3，无 `other` planning step，无当前词表非法 L3，链长 2-15，任务文本长度 299-300，task text 和 QGIS chain 均无重复。因此它是结构上可用于 SFT 的 seed。语义注意：构建脚本仍使用较粗的 planning-step -> L3 映射，例如 `geometry_repair`/`fixgeometries` -> `L3_02_07_01`，但该 L3 在当前词表中是 "Multipart to Singlepart"；`raster_sampling`/`rasterize`/`polygonize` -> `L3_03_01_01`，该 L3 是 "Clip Raster by Geometry"；`grid_generation` -> `L3_02_05_12`，该 L3 是 "Minimum Bounding Geometry"；所有 overlay 子类也都压到 `L3_02_02_06`。所以 685 行是结构 clean，但还不是高置信语义全审过的 SFT 真值。 |
| 2026-06-06 | 重新核验 `outputs_v2/canonical_vector_clean_sft_seed.jsonl` 的 overlay 粗映射修复。目标粗映射已修复：`L3_02_05_04` 计数为 0；overlay 子类已经映射到各自当前词表 L3：`Intersect` 110、`Union` 37、`Erase/Difference` 73、`Symmetrical Difference` 5、`Clip` 219。此前 vector overlay 全压到 Clip 的问题已消失。剩余注意点是 taxonomy 粒度，而不是结构质量：geometry repair/validation/simplify/delete-holes 仍共用 `L3_02_07_01`，raster sampling/rasterize/polygonize 仍共用 `L3_03_01_01`；只有在当前训练/评测契约接受这些 family-level 标签时，才应称为语义级 clean。 |
| 2026-06-06 | 核验 `outputs_v2/pipeline/step8_qgis_vector_sft/` 作为 Step8 兼容的 QGIS vector SFT 包。该包包含 685 条 workflow，确定性 split 为 548/68/69，token id 全部合法于 94-L3 词表，task metadata 完整，本地单 task vocab 为 `"Vector Analysis": 0`。V4.2 和 V4.6 训练入口都能 dry-run 读取该包，V4 training-entry smoke 能完成 CPU 前向。该包可作为 QGIS-only SFT 输入，也可作为 GEE+QGIS 混训组件；当前训练入口还没有实现建议的 5:1 mixed-batch 调度。 |
| 2026-06-06 | 审计 `outputs_v2/pipeline/step8_quality_gate_qgis_vector/` 合并包。结构和 loader 检查通过：77,569 条 workflow，62,180/7,694/7,695 split 精确覆盖，685 条 QGIS 行连续追加且只进 train，combined task type 为 `"Vector Analysis": 47`，没有新增普通非法 L3 token，跨 split content-sequence overlap 为 0。V4.6 dry-run 和真实 QGIS 样本 CPU 前向通过。主要阻塞是命令/loader 兼容性：`scripts/train_v4_6_quality_gate.py` 没有 `--lr` 参数，且 current 47-task DPO/quality-gate checkpoint strict `--warmstart` 到 48-task 模型会失败。 |
| 2026-06-07 | 在服务器 CUDA 上跑通合并 quality-gate + QGIS vector 训练 smoke。From-scratch 5 epoch 完成，但由于无 warmstart 且显式 `--num-epochs 5` 时 `tf_phase_epochs=10`，该 run 实际是 TF-only；best validation composite 为 0.4916（epoch 4），test AR SetF1 为 0.445。Expanded-warmstart 路线在 `scripts/expand_checkpoint_task_types.py` 将 DPO v2 task-type 权重 47->48 后成功运行，5 个 warmstart epoch 从 epoch 1 即进入 AR-SS，best validation composite 为 0.5922（epoch 1），test AR SetF1/LCS/earlyEOS 为 0.523/0.386/12.9%。后续应优先把 warmstart 作为候选继续验证；注意本次两条路线复用了同一 checkpoint dir，第二次 warmstart 会覆盖第一次 from-scratch 的 best/history。 |
| 2026-06-07 | 服务器运行 `scripts/evaluate_sft_vector_impact.py`，对比 warmstart SFT checkpoint 与 DPO v2 baseline。修正后复跑确认 SFT 加载 48-task mixed length stats，DPO 加载 47-task quality-gate length stats，指标保持一致。Strict vector token rate：GEE test 上 DPO 0.4% vs SFT 2.0%（+1.6pp），QGIS clean seed 上 DPO 1.7% vs SFT 53.7%（+52.0pp）。结论：685 条 QGIS vector SFT 信号已被模型明显吸收，同时 GEE 栅格侧污染在该 smoke 下较小。边界：QGIS seed 是训练源/吸收证据，不是 held-out 语义级矢量规划泛化证明。 |
| 2026-06-07 | 服务器运行前审查并加固 held-out vector generalization benchmark。`configs/unseen_vector_prompts.jsonl` 是手工任务，和 `canonical_vector_clean_sft_seed.jsonl` 没有 exact/substring overlap，但当前实际 modality split 是 61 vector / 6 mixed / 3 raster，不是早前描述的 55 / 8 / 7。`scripts/evaluate_vector_generalization.py` 现在会对模型/vocab/length stats 缺失 fail fast，显式区分 48-task SFT 与 47-task DPO 的 vocab 和 length stats，推理前调用 task-type complexity profile，避免 raster clip 误算为 vector clip，同时输出 measurable recall、strict/all recall、unsupported expected families、overlay subtype recall 和 metadata-rich JSON 报告。 |
| 2026-06-07 | 服务器运行 `scripts/evaluate_vector_generalization.py`，对 70 条手工未见 prompt 做泛化评测。Vector prompts 上 SFT 相对 DPO 的模态行为明显改善：measurable expected-family recall 2.1% -> 25.7%，strict/all recall 1.6% -> 20.2%，raster-ish token rate 94.8% -> 35.6%，vector token rate 1.4% -> 53.3%。Raster controls 没有出现矢量污染：vector token rate 仍为 0.0%，raster-ish rate 从 77.8% 到 88.6%。解释：QGIS-vector SFT 已经让模型学会进入矢量规划模式，并显著减少矢量 prompt 上的栅格模板塌缩；但细粒度矢量语义仍弱。当前 SFT 主要会输出 `spatial_filter`、`spatial_join/table_join`、`buffer`、`merge`，仍大量漏掉 dissolve、geometry repair/cleanup、clip、intersection、difference、attribute filter、CRS transform、field calculation、export、grid/centroid 等核心族。Overlay subtype 只有单个 union 命中，intersection/difference 仍为 0。 |
| 2026-06-07 | 服务器训练前本地核验 QGIS-vector 过采样包。`outputs_v2/pipeline/step8_quality_gate_qgis_vector_oversampled/` 有 81,137 条 workflow，split 为 65,748/7,694/7,695，4,253 条 QGIS vector 行只在 train，普通 token id 没有 >=94，`"Vector Analysis": 47`。已生成该包专用 `task_type_length_stats.json`；V4.6 训练命令必须显式传 `--length-stats`。`scripts/evaluate_vector_generalization.py` 已支持 SFT checkpoint/vocab/length-stats/report path 的 CLI 覆盖，避免过采样模型训练后仍评到 v1 硬编码路径。 |
| 2026-06-07 | 服务器跑通 QGIS-vector 过采样 warmstart 路线。先从 `step8_quality_gate_qgis_vector_oversampled` 重建 `outputs_v2/transition_allowed_next.json`（65,748 条 train workflow、60 states、607,006 transitions），再把 DPO v2 checkpoint 从 47 task types 扩到 48 task types，并训练 5 个 AR-SS epoch 到 `outputs_v2/transformer_checkpoints_v4_6_quality_gate_qgis_vector_oversampled_warmstart/`。Best checkpoint 为 epoch 1，validation composite 0.5895；test 为 AR SetF1 0.540、LCS 0.397、earlyEOS 11.3%、PPL 17.7。`outputs_v2/diagnostics/vector_generalization_oversampled.json` 显示 vector prompts measurable recall 3.8% -> 27.8%、strict/all 3.0% -> 21.9%、vector token rate 1.5% -> 57.6%、raster-ish token rate 92.8% -> 34.7%，raster controls 的 vector token rate 保持 0.0%。结论：过采样相对 v1 只小幅增强 vector-regime，不足以解决细粒度 overlay 语义；intersection/union/difference 在当前 prompt 集上仍为 0。 |
| 2026-06-07 | 修正 `scripts/evaluate_sft_vector_impact.py`，增加 SFT checkpoint/vocab/length-stats/report path 的 CLI 覆盖，和 `evaluate_vector_generalization.py` 对齐。重要注意：用户在过采样训练后直接运行 `python scripts/evaluate_sft_vector_impact.py` 的日志仍加载保守 v1 checkpoint（`outputs_v2/transformer_checkpoints_v4_6_quality_gate_qgis_vector/best_model.pth`），所以其中 QGIS seed 63.7% 不是 oversampled v2 吸收证据。比较 v2 seed absorption/preservation 前，必须显式传过采样 checkpoint/vocab/length-stats，并写到 `outputs_v2/diagnostics/sft_vector_impact_oversampled.json`。 |
| 2026-06-07 | 服务器用显式过采样 SFT checkpoint/vocab/length-stats 重新运行 `scripts/evaluate_sft_vector_impact.py`。日志确认 SFT 加载 `outputs_v2/transformer_checkpoints_v4_6_quality_gate_qgis_vector_oversampled_warmstart/best_model.pth`、过采样 48-task vocab/stats，以及 60-state transition matrix。结果：GEE strict-vector rate DPO 0.4% vs SFT 2.4%（+2.0pp），QGIS seed DPO 1.7% vs SFT 57.2%（+55.5pp），SFT 两侧 avg length 都为 6.8。解释：v2 过采样 seed absorption 已确认，GEE contamination 在 smoke 下仍小；但这仍不改变 held-out 细粒度 vector semantics 尚未解决的判断。Report：`outputs_v2/diagnostics/sft_vector_impact_oversampled.json`。 |
| 2026-04-29 | 默认配置切到 `outputs_v2`、94 vocab、v2 hierarchy、v2 id mappings、v2 L3 embeddings |
| 2026-04-29 | KG 构建默认优先使用 v2 hierarchy 和 v2 id mappings metadata |
| 2026-04-29 | QGIS candidate generator 和 L3-to-platform mapper 默认读取 `id_mappings_v2.json` 的 `mapping_metadata.qgis_to_l3` |
| 2026-04-29 | inference / evaluation / data helper 改为使用配置层 v2 默认路径 |
| 2026-04-29 | 新增 v2 默认路径和 KG 路径解析测试 |
| 2026-04-29 | 发现并修复 QGIS 人工审核映射被默认置信度阈值过滤的问题：`Write Vector Tiles_mbtiles` 和 `Write Vector Tiles_xyz` 现在保留 |
| 2026-04-29 | 发现并修复 stale candidate 问题：`Remove Duplicate Points`、`Mirror Raster` 使用顶层人工修正后的 `primary_l3`，不再使用旧 `all_candidates[0]` |
| 2026-04-29 | 新增本中文上下文文档，并新增 `AGENTS.md`，要求后续新会话主动维护项目记忆 |
| 2026-05-07 | 新增 Step6/Step8 provenance gate：Step6 写入 mapping/skip-list 指纹，Step7 透传，Step8 校验，pipeline audit 支持按 provenance warning 失败退出 |
| 2026-05-07 | 修复 v2 Step8 数据的 split 对齐：已有 split 不合法时会确定性重建，真实 `outputs_v2/dataset_splits_v4.json` 已匹配 107,399 条 workflow |
| 2026-05-07 | 新增面向模型训练的 Step8 数据质量审计，并在 `outputs_v2/pipeline/audit/` 生成 JSON/Markdown 报告 |
| 2026-05-07 | 在 `outputs_v2/pipeline/step8_quality_gate/` 生成质量门禁版 V4 候选集：低置信 `auto_remap` quarantine、稀疏 task 合并、按 exact L3 sequence 分组 split、候选审计和 GEE alias 审计 |
| 2026-05-07 | 新增并跑通 V4 质量门禁候选集训练入口 smoke test：显式读取候选 data/split/task vocab，默认只读本地 BERT 缓存，使用 v2 L3 embeddings，执行单 batch forward 且不写 checkpoint |
| 2026-05-07 | 新增安全的 V4.2 quality-gate 训练启动脚本，显式指定 data/split/task-vocab/checkpoint 路径，并支持 dry-run 校验 |
| 2026-05-07 | 新增安全的 Set Predictor V3 quality-gate 训练启动脚本，显式指定候选 data/split/task-vocab/active-token/checkpoint 路径，并支持 dry-run 校验 |
| 2026-05-07 | 新增并生成 v2 quality-gate transition matrix；V4 quality-gate launcher 非 dry-run 时必须显式使用该矩阵，避免静默退化为无 transition 正则 |
| 2026-05-21 | 只读验证 `gis-evaluate` 的 Step8 + V4.6 主线边界：入口是 `gis_recommend.evaluation.runner:main`，数据是原 Step8 `outputs_v2/pipeline/step8/labeled_workflows_l3_v4_cleaned.json`，split 是 `outputs_v2/dataset_splits_v4.json`，默认 checkpoint 是 `outputs_v2/transformer_checkpoints_v4_6/best_model.pth`，reranker / repair / QGIS 诊断均为可选；同时确认仍存在若干 report-time contract 风险 |
| 2026-05-21 | 完成 Step8 + V4.6 主线契约加固的 Phase1/2：新增 `MainlineRunContract`，将 semantic metrics 从旧 350-L3 special-token 假设迁出，`gis-evaluate` 报告现在写入 token profile/data authority/repair capability/selection policy/L2 role；`CandidateVerifier` 默认只查 v2 I/O metadata，缺失时降级为 missing metadata，不再静默回退 legacy；V4-QG/V5/retrieval-stage 实验报告也明确标记为 non-mainline research artifact。 |
| 2026-05-21 | 收口 Step8 + V4.6 契约审计后的剩余问题：`QGISCandidateGenerator` 现在和 verifier/report 使用同一份 run-contract I/O metadata authority；被选 QGIS candidate 会把 `qgis_score_components` 写入逐样本 decision trace；后置 QGIS evaluation 可接收同一 run contract；`scripts/evaluate_v4_quality_gate.py` 和配置注释不再把 V4-QG 描述为 final/mainline。 |
| 2026-05-21 | 加固 Neo4j KG 导入入口，使其对齐当前 `outputs_v2` / 94-L3 主线：`scripts/build_ontology_kg.py` 现在要求显式 Neo4j 凭据，默认读取 v2 hierarchy / id mappings / embeddings，兼容 v2 hierarchy CSV 缺少旧 description 列的格式，不传 `--allow-legacy-inputs` 就不回退 legacy，不传 `--clear` 就不清空数据库。`scripts/import_l3_mappings.py` 现在默认读取 `outputs_v2/id_mappings_v2.json`，并使用同样的显式服务器参数和 legacy 门禁。`scripts/README_KG_BUILD.md` 已更新为安全服务器运行说明。 |
| 2026-05-21 | 为 Step8 + V4.6 Constraint Decoder 实现 Phase0/Phase1 report-only shadow instrumentation：run contract 现在记录 `candidate_pool_enabled`、`decision_core_mode`、`retrieval_mode`、`l2_authority`；报告逐样本写入 `candidate_pool_trace`、`evidence_bundle`、`decision_trace.shadow_decision_core`；可选 `--retrieval-shadow-k` 会从 train split 构造 lexical retrieval shadow candidates，不读 test reference，也不替换 legacy 输出。未修改 decoder、beam、训练、metric、`pred_tokens` 或默认 selection。 |
| 2026-05-23 | 从持续扩展 observation-only Phase5.x 中纠偏，转向直接修复 ranking。新增离线 evidence-aware ranking 实验：读取已有 report/candidate artifact，比较 legacy selection、evidence-aware selection 和 oracle best-in-pool，并把诊断结果写入 `outputs_v2/diagnostics/evidence_aware_ranking/`；不改主链 `pred_tokens`、metrics、beam、reranker 或 selection。120 条 empirical 记录的 smoke 结果：evidence-aware LCS 0.4412 vs legacy 0.3957，SetF1 0.6361 vs 0.5666，但 TokenAcc 0.1696 vs 0.1941，oracle 命中率 0.3500 vs 0.3583；说明 ranking 信号有价值但还不能直接上线。 |
| 2026-05-08 | 完成 Phase 1A 到 Phase 15C.1 的只读 V5 语义边界审计：真实 runtime authority 只包括 active dataset/sampler callable、TF/AR train-step callable、train-step return dict ABI、checkpoint selector 条件、eval/inference decode callable 及其直接输入，以及这些 callable 实际读取的 transition/legality 数据 |
| 2026-05-08 | 完成 Phase 15C.3 runtime-boundary enforcement audit：当前还没有实现 V5 governance objects；修复前的具体 reverse-edge 风险来自 legacy Step8 provenance hard gate、audit warning 进程失败、validation/repair 修改已选 QGIS chain，以及 reranker scoring 使用 validation classification |
| 2026-05-09 | 完成 Phase 15C.2 代码收敛：清除活跃脚本里的 `weights_only=False` 加载，legacy `train_v3` / `train_v4_3_rl` / `train_graph_embeddings` 改为 latest-snapshot 语义，修复 report-only repair 测试断言错误 |
| 2026-05-09 | 完成 Phase 15C.2 结构对齐：活跃 inference / warm-start 路径移除 raw/partial checkpoint fallback，provenance validation 改为 report-only，repair suggestion 保持非突变，`gis_recommend.evidence` 降级为 snapshot/report-only stub |
| 2026-05-09 | 完成 `docs/empirical_bottleneck_audit.md` 实证瓶颈审计：量化 quality-gate 数据集、transition graph、歧义、retrieval/Markov baseline，并确认当前主要瓶颈是 supervision/data ambiguity 加 ontology/distribution 问题，而不是已被证明的模型容量不足 |
| 2026-05-09 | 建成 post-convergence 实证评测基础设施：baseline-only artifact builder、error taxonomy、retrieval baselines、canonicalization audit、decode-policy summary、工程瓶颈归因、console entry point、测试，以及 `outputs_v2/evaluation_reports/` 下的 20 样本 v2 smoke artifact |
| 2026-05-09 | 实现隔离的 V5_final runtime 路径：memory-augmented AR planner、PVM retrieval attention、固定 temporal decay、训练期 alpha noise、IO-constrained greedy/beam decode、诊断 alpha/graph 输出、严格 V5 checkpoint schema、empirical prediction attachment、最小训练/推理入口、配置、文档和测试 |
| 2026-05-09 | 新增 V5_final 完整训练/评测引擎：确定性 subset、train/validation loop、可选 AMP、gradient clipping、early stopping、best/latest checkpoint 生命周期、IO-mask bias annealing、report-only stability/collapse monitoring、evaluation JSON/Markdown、empirical prediction attachment、ablation flags、CLI dry-run 和测试 |
| 2026-05-09 | 执行 V5_final 受控实证验证：Stage0 1k/5 稳定完成，Stage1 10k/30 在 CPU 上用 batch size 512 完成；两者都在 `outputs_v2/v5_final_reports/` 写出 checkpoint、report 和 baseline comparison；没有 collapse alert，但 Stage1 在 50 样本报告上没有超过 lexical/Markov retrieval baseline |
| 2026-05-10 | 完成 V5_final 受控实证归因任务：A1 strict no-PVM ablation 产物同步到 `outputs_v2/v5_final_reports/a1_no_pvm/`，Stage1 checkpoint 的 beam=1/3/5/10 复评写入 `outputs_v2/v5_final_reports/beam_search_eval/`，最小 lexical top-3 retrieval-assisted prototype 写入 `outputs_v2/v5_final_reports/retrieval_assisted/` |
| 2026-05-10 | 实现并评测 `V5_hybrid_planner_prototype` retrieval-centered workflow planner：top-K lexical retrieval 保持 workflow 结构锚点，candidate expansion 只允许 IO-filtered 的局部 <=1 edit 变体，V5_final 只用 Stage1 checkpoint 对完整候选打分/重排，reports / attribution / traces 写入 `outputs_v2/v5_final_reports/v5_hybrid_planner_prototype/` |
| 2026-05-10 | 继续演进 hybrid planner：新增 multistage retrieval fusion 和 safe reranking，包括 lexical/embedding/intent/workflow-structure/graph-aware retrieval sources、source attribution、contribution attribution、repair outcome metrics、failure decomposition、retrieval-confidence floor selection，并生成 50 样本 artifact 到 `outputs_v2/v5_final_reports/v5_hybrid_planner_multistage/` |
| 2026-05-10 | 新增 unified workflow benchmark runner 和 artifact：V4 teacher-forced metrics、V4 AR rollout metrics、V5 pure generation、retrieval-only planning、hybrid planning 和 Set Predictor 现在作为独立 task/mode/scope rows 记录，并通过 comparison groups 防止 TF-vs-rollout 或 set-vs-sequence 指标混用 |
| 2026-05-10 | 新增 retrieval-centered planning stage evaluation：Set Predictor 兼容的 soft/hard retrieval filtering、execution-aware rerank features、严格局部 repair candidate generation、attribution/failure reports、forbidden-pattern scan artifact、测试，以及 `outputs_v2/v5_final_reports/retrieval_filtering/`、`execution_aware_rerank/`、`local_repair/` 下的 50 样本输出 |
| 2026-05-10 | 新增 evaluation-only repair oracle phase：显式局部编辑候选池、repair oracle vs identity retrieval、retrieval-pool oracle 对比、逐候选 repair attribution、rerank-selection failure 检测、failure taxonomy、测试、forbidden-pattern scan，以及 `outputs_v2/v5_final_reports/repair_oracle_phase/` 下的 artifact |
| 2026-05-10 | 新增 evaluation-only repair selection diagnostics phase：scorer term decomposition、identity-bias analysis、oracle-gap attribution、conservative/balanced/aggressive threshold sweep、确定性 random modified-candidate control、forbidden-pattern scan、测试，以及 `outputs_v2/v5_final_reports/repair_selection_diagnostics/` 下的 artifact |
| 2026-05-10 | 新增 evaluation-only repair scorer ablations：no-edit-penalty、piecewise operation penalties、uniform edit-penalty sweep、execution/set-heavy weighting、retrieval-preservation-heavy weighting、scorer recommendation artifact、forbidden-pattern scan、测试，以及 `outputs_v2/v5_final_reports/repair_scorer_ablations/` 下的输出 |
| 2026-05-10 | 新增 evaluation-only repair edit-penalty calibration sweep：生成 200 样本 held-out repair oracle trace，对 0.0 到 0.20 的 uniform penalty 做 sweep，输出 bootstrap intervals、task/subset stability analysis、CSV curves、forbidden-pattern scan、测试，以及 `outputs_v2/v5_final_reports/repair_calibration_sweep/` 下的 artifact |
| 2026-05-10 | 新增 evaluation-only repair opportunity attribution study：只读取已有 200 样本 repair candidate traces，量化 retrieval ambiguity、IO inconsistency、set mismatch、structural anomaly、repair locality、heuristic opportunity indicators、failure taxonomy v2、bootstrap correlation cautions、forbidden-pattern scan、测试，以及 `outputs_v2/v5_final_reports/repair_opportunity_analysis/` 下的 artifact |
| 2026-05-10 | 新增 evaluation-only repair confidence regime discovery phase：只读取已有 200 样本 repair candidate traces，分解 repair subtype/context 条件，搜索 precision-first 低腐蚀 regime，验证 bootstrap intervals，对比 random modified/narrow/edit-type controls，写出 forbidden-pattern scan、测试，以及 `outputs_v2/v5_final_reports/repair_confidence_regimes/` 下的 artifact |
| 2026-05-10 | 新增 V5 system consolidation protocol 并整合进中英文上下文：最终系统身份是 retrieval-centered / execution-aware / rerank-driven / constrained-planning-oriented；generation 不是主要已验证能力；repair 仍只有 oracle 支持，不能部署；未来声明必须区分 deployed、experimental 和 oracle-only evidence。 |
| 2026-05-10 | 完成项目级科学综合：将当前实证发现、基准治理、检索中心规划器结果、修复诊断、评分器校准发现、归因边界、评测层级和任务族分离综合为"当前科学共识"部分，写入两个 PROJECT_CONTEXT 文件。该部分现为后续会话的权威继承项目状态。 |
| 2026-05-10 | 新增 `docs/v5_l2_semantic_recovery_protocol.md`，正式区分当前 retrieval-centered 的 L3 运行时和长期 L1->L2->L3 目标架构。该协议恢复 L2 作为未来语义意图层的合法地位，同时保持所有声明受证据约束且不具备 runtime authority。 |
| 2026-05-10 | 完成 bounded ontology inventory 阶段：生成保守 GEE<->QGIS 映射分类、显式 unsupported GDAL/ArcGIS 行、execution-constraint inventory、unsafe mapping registry、窄 workflow-equivalence registry、forbidden-pattern scan、测试，以及 `docs/v5_bounded_ontology_inventory_protocol.md`。 |
| 2026-05-12 | 新增严格 evaluation-only canonicalized workflow metrics：raw vs canonicalized Exact Match/LCS/token accuracy/SetF1、通过既有 empirical canonicalization 逻辑发现 train-split commutative pairs、TopK recovery、per-task/per-pair recovery、bootstrap intervals、examples、forbidden-pattern scan、测试，以及 `outputs_v2/v5_final_reports/canonicalized_evaluation/` 下的 artifact。 |
| 2026-05-12 | 新增严格 evaluation-only workflow usability metrics v1：Top1/Top3/Top5 usable-rate 代理指标读取 369 条持久化预测记录、required-step coverage、harmful/missing step rate、QGIS mapping coverage、顺序/长度/冗余检查、per-task breakdown、failure taxonomy、examples、bootstrap intervals、forbidden-pattern scan、测试，以及 `outputs_v2/v5_final_reports/workflow_usability_evaluation/` 下的 artifact。 |
| 2026-05-13 | 重写 `scripts/evaluate_workflow_usability.py` 为自包含 evaluation pipeline (v2)：不需要模型、checkpoint、训练、语义检索、LLM 评判。直接在 200 个质量门禁测试样本上用 L1/L2 层次类别和 QGIS 映射的 7 个规则指标评估 lexical retrieval。生成全部 7 个报告 artifact。关键发现：Top-1 可用 56%，Top-3/Top-5 100%，平均可用性 0.7663 超过参考 0.7207——retrieval 已经产出实际可用链。 |
| 2026-05-13 | 实现 V4-QG planner Phase 1 candidate-pool/rerank 入口 `scripts/run_v4_qg_planner.py`：质量门禁默认路径、retrieval TopK 候选池、可选 V4 AR candidate hook、本地缺 checkpoint 时的 train-frequency Set Predictor fallback、作为 rerank feature 的 soft transition prior、规则可用性优先选择、JSON/CSV/Markdown artifact、forbidden-pattern scan、测试，以及 `outputs_v2/v4_qg_planner_reports/` 下的 200/1,000 样本报告。 |
| 2026-05-12 | 新增严格 evaluation-only multi-reference workflow evaluation：从现有 labeled workflows 构造 exact-task/text reference pool，比较 raw single-reference、best-of-multi-reference 和 canonicalized-multi-reference 指标，输出 TopK usability deltas、workflow-family breakdown、ambiguity taxonomy、recovered examples、forbidden-pattern scan、测试，以及 `outputs_v2/v5_final_reports/multi_reference_evaluation/` 下的 artifact。 |
| 2026-05-14 | 修正 V4-QG planner 的 Set Predictor checkpoint 默认路径：V4.6 quality-gate Set Predictor artifact 现在默认读取 `outputs_v2/set_predictor_checkpoints_v3_quality_gate_v4_6/best_model.pth`，与最终实用 V4.6 主线一致，避免误读旧 schema checkpoint。 |
| 2026-05-14 | 实现 MRV Stage 1-2 与人工审查导出：从 quality-gate train commutative pairs 生成相邻交换变体，执行保守自动 gate，输出 registry eligibility、分层 review CSV、设计/计划文档、测试，以及 `outputs_v2/v4_qg_multiref_validation/` 下的 smoke artifacts。 |
| 2026-05-14 | 修正 MRV validation-target drift：彻底拆开 GEE/workflow-level semantic validation 和 downstream QGIS landing。QGIS mapping / chain 失败现在只是辅助 transferability signal，不再阻塞 `verified_equivalent_candidate` 标签。 |
| 2026-05-15 | 完成第一批 MRV 人工等价审查：19 条 auto-verified workflow-semantic candidates 中，14 条标为 `equivalent`，4 条 `uncertain`，1 条 `not_equivalent`。manual-only multi-reference registry 现在包含 7 个 task groups，只来自 14 条人工接受的交换变体；uncertain / rejected 行仍禁止进入训练标签。 |
| 2026-05-15 | 完成 4 条 MRV `uncertain` 的 source-level 深挖：3 条记录为 conditional-equivalent 但不具备 registry 资格；`wf46_pos2_swap53_28` 因 `filterMetadata` 在 ImageCollection 链上、`select` 已经是 image-level 操作，交换后会造成 object-chain conflict，因此降级为 `not_equivalent`。 |
| 2026-05-15 | 完成 500-variant MRV expansion，并新增可复跑的 equivalence taxonomy 分析层。扩展结果为 46 个 auto candidates、454 个 invalid variants；新 family/risk/rejection artifacts 显示 filter/filter 和 select/filter 是后续人工审查优先级最高的交换族，同时 QGIS landing failure 继续保持辅助信号。 |
| 2026-05-15 | 完成并修订 46 个 MRV expansion auto candidates 的 AI-assisted review draft：36 条 equivalent、8 条 uncertain、2 条 not equivalent。写出 review CSV/JSON/Markdown，并生成非训练用 registry draft：19 groups / 36 variant sources。 |
| 2026-05-15 | 将用户确认后的 MRV review 晋升为正式 registry v2 / equivalence KB v2。Builder 按 `variant_id` 去重，只把 `equivalent` 行标为 training-eligible，保留 13 条 excluded variants，并清洗 family/risk 汇总，让 `review_flags` 只作为证据字段。最终 v2 计数：55 个唯一 reviewed variants、42 个 equivalent variants、23 个 task groups。 |
| 2026-05-15 | 实现受控 MR training ablation 数据构造，并在 `outputs_v2/v4_qg_mr_ablation/` 下生成隔离的 `mr_5`、`mr_10`、`mr_all_42` quality-gate 派生集。Builder 只读 verified MRV registry v2 / KB v2，只把变体追加到 train split，保持 val/test 不变，写入 provenance 和 no-training manifest，且不覆盖主线 quality-gate 数据或 checkpoint。 |
| 2026-05-15 | 实现只读 MR ablation comparison scaffold。它消费已有 baseline 与 `mr_*` report JSON，抽取可对齐的 usability / canonicalized / diversity / invalid-harmful 指标，计算 delta，并在有 per-sample 行时计算 paired bootstrap CI；输出 comparison JSON/Markdown，不训练、不推理、不加载 checkpoint、不改数据。 |
| 2026-05-17 | 读取并记录服务器端 `mr_all_42` V4.6 quality-gate 训练日志。该 run 从头训练 50 epoch 并完成，但 AR-SS 阶段从 epoch 11 开始出现 `Train: Loss=inf`，最终 latest checkpoint 明显低于历史 quality-gate V4.2 TF 指标。当前应先把它作为训练稳定性/checkpoint-selection 诊断，而不是直接声明 MR 效果。 |
| 2026-05-17 | 修复 V4.6 AR scheduled-sampling 非有限 loss 问题：dynamic minimum-length 的 early-END mask 现在只作用于 decode/sampling logits，CE loss 和 early-END penalty 使用未 mask logits。新增回归测试覆盖旧逻辑中 `END_INDEX` target 被 `-inf` logit 污染导致 CE 为 `inf` 的路径。服务器完整训练仍需重跑验证。 |
| 2026-05-19 | 审查 `结果/周报/周报-2026-05-24.md`，确认评价体系从 sequence generation 转向 workflow planning 的方向合理，并在 smoke 验证中修复两个 V4-QG planner blocker：`fallback_set_prior` 不再在 `set_prior` 赋值前引用；V4 AR candidate generation 现在调用 `set_complexity_profile()`，让 task-adaptive EOS suppression 真正生效；小样本 Markdown CI 渲染现在能处理 `None` bootstrap bounds。 |
| 2026-05-19 | 将长度/复杂度链路对齐到 V4 quality-gate 主线：`scripts/compute_task_type_length_stats.py` 默认读取 quality-gate 数据并写入 quality-gate 目录，已生成 `outputs_v2/pipeline/step8_quality_gate/task_type_length_stats.json`；planner / inferencer 的 length-stats 查找顺序改为优先 quality-gate，其次 `outputs_v2` 根目录，最后才回退 legacy `outputs/`。 |
| 2026-05-19 | 升级 V4-QG 检索与评估报告链路：`LexicalRetrieval` 现在基于 task name / task description 做 query-aware Jaccard 排序，同 task_type 候选优先、全局候选只作为低权补充；`run_v4_qg_planner.py` 已把任务文本传给 retrieval；`evaluate_v4_quality_gate.py` 现在输出五层指标视图和 Markdown 摘要，把 sequence EM / token accuracy 降级为诊断指标，并把 workflow usability / QGIS landing 作为主 KPI 族。这只是 lexical 文本匹配，不是 embedding 或语义检索，仍需服务器大样本 ablation。 |
| 2026-05-16 | 检查本地最小 MR training loop 前置条件：本地没有 V4.6 quality-gate baseline checkpoint，也没有 `mr_all_42` checkpoint；当前 workspace 是 CPU-only（`torch.cuda.is_available=False`）；`l3_embeddings_v2.pt` 和本地 BERT cache 存在；quality-gate 与 `mr_all_42` dry-run 均通过。完整训练交由用户服务器执行；本地不要推断模型效果。 |

## 修改过的文件及原因

### 2026-06-07 — QGIS vector SFT impact smoke 对齐

已完成：
- 解读服务器 `scripts/evaluate_sft_vector_impact.py` 输出：QGIS seed strict-vector rate 从 DPO 1.7% 到 SFT 53.7%，说明 QGIS SFT 信号被明显吸收；GEE test strict-vector rate 从 0.4% 到 2.0%，目前是较小污染信号。
- 修正 `scripts/evaluate_sft_vector_impact.py`：SFT 必须使用 48-task vocab 和 merged `task_type_length_stats.json`；DPO 继续使用原 47-task vocab 和 quality-gate length stats；缺失 checkpoint/vocab/stats 时 fail fast。
- 修正 `src/gis_recommend/inference/infer_l3_candidates_v4.py`：新增可选 `length_stats_path`，让 48-task mixed checkpoint 的推理/评测可以显式对齐长度先验，同时保持默认行为兼容。

解释边界：
- 该脚本是 signal absorption smoke，不是开放式矢量规划能力 benchmark。QGIS 侧抽样来自 `canonical_vector_clean_sft_seed.jsonl`，属于 train-source seed；高 strict-vector rate 只能说明模型学会输出矢量 L3 骨架。
- DPO baseline 没有 `"Vector Analysis"` task type，因此 QGIS delta 同时包含新 task-type embedding 与 SFT 权重更新的影响。

验证记录：
- `python -m py_compile scripts\evaluate_sft_vector_impact.py src\gis_recommend\inference\infer_l3_candidates_v4.py` -> OK。

### 2026-05-29 — DPO 最终策略质量报告加固

已完成：
- 复核 DPO `beam_first_usable` / `beam_usable_quality` 离线评测链路。当前服务器 3k 结果是 final usable 99.8%，真实 final failure 为 6/3000。
- 加固 `scripts/evaluate_execution_aware_selector.py` 的报告口径：final failure 和 final warning 分开统计；顶层报告新增 `final_warning_taxonomy`，与 `final_failure_taxonomy` 分离。
- 为 `beam_usable_quality` 新增保守 `_quality_adjusted_score()`：仍以 usability 作为门控，但在可用 beam 候选内部，用重复 token、连续重复和 non-blocking warning 标记做质量惩罚。
- 首次服务器 3k `beam_usable_quality` 结果显示 duplicate rate 明显下降但 redundant loops 未下降，因此继续扩展 quality score：从 hierarchy 构造 `token_names`，并在选择阶段直接惩罚含 Train/Apply 的三元冗余 loop，而不是只在诊断脚本里事后统计。
- 增加单测覆盖 quality score 惩罚和 final warning/failure taxonomy 分离。

观察事实：
- `scripts/analyze_final_workflow_quality.py` 能在本地已有 `dpo_beam_first_test_3k` 报告上跑通：final usable 2994/3000 (99.8%)，真实 failure 6，duplicate-token rate 25.6%，连续重复 adjacent-pair rate 0.15%，冗余 loop 437，平均长度 5.96，retrieval fallback 30/3000 其中 25 条可用。
- `beam_usable_quality` 应被表述为 execution-aware rule-gated 的离线/候选推理策略，不是纯模型能力。它使用与 usability 指标同源的规则 evaluator 做 beam 候选门控，因此最终声明应写“execution-aware rule usability”，不要写“严格语义准确率”。

验证：
- `python -m unittest tests.test_execution_aware_selector -v` -> 7 tests OK。
- loop 惩罚扩展后：`python -m unittest tests.test_execution_aware_selector -v` -> 8 tests OK。
- `python scripts\evaluate_execution_aware_selector.py --split test --num-samples 5 --selection-policy beam_usable_quality --output-dir outputs_v2\diagnostics\execution_aware_selector\quality_policy_no_beam_smoke_5` -> smoke completed。
- `python scripts\analyze_final_workflow_quality.py --report outputs_v2\diagnostics\execution_aware_selector\dpo_beam_first_test_3k\selector_report.json --output outputs_v2\diagnostics\execution_aware_selector\dpo_beam_first_test_3k\quality_review_smoke_v2` -> quality report smoke completed。

后续：
- `scripts/build_generation_preferences.py` 新增 `--reward-mode quality`，用于 DPO v2 偏好对构造。默认 `base` 保持 v1 行为；quality 模式会扣除重复、连续重复和 warning 惩罚，并允许 clean usable > redundant usable 这类质量偏好对，不再把同等 usability 的 usable 负例过滤掉。
- quality 模式偏好对构造继续新增 `--id-mappings` / `--hierarchy` token-name 加载，使 `beam_usable_quality` 已验证有效的 Train/Apply loop 惩罚也能进入 DPO v2 偏好对。
- `python -m unittest tests.test_generation_preference_pipeline tests.test_execution_aware_selector -v` -> 16 tests OK。
- `python -m compileall scripts\build_generation_preferences.py tests\test_generation_preference_pipeline.py` -> OK。

服务器结果：
- 使用已有 train/val selector traces 和 `--reward-mode quality --min-reward-margin 0.10` 构造质量偏好对：train 8,265 对，val 1,711 对。
- DPO v2 从 `outputs_v2/transformer_checkpoints_v4_6_preference_dpo/best_preference_model.pth` 继续训练 1 epoch，参数为 lr 5e-6、beta 0.05、CE anchor 0.10。Val preference accuracy 为 0.7686。
- DPO v2 在 test 3k + `beam_usable_quality` 下：retrieval top-1 usable 65.5%，beam top-1 usable 99.2%，selector 89.4%，final 99.9%（2998/3000），oracle 100.0%，final 来源 beam 2999 / retrieval 1。
- 初版质量诊断报 redundant loops 302，但复核发现 detector 错把正常 `Region-based Sample Extraction -> Train Random Forest Classifier -> Apply Classifier` 分类流程算成 loop。现已修正 detector 和训练质量惩罚，只统计真正的 `Train -> Apply -> Train` 或 `Apply -> Train -> Apply` 循环。
- 修正后的 DPO v2 质量诊断：真实 failure 2，duplicate-token rate 1.4%，连续重复 0.01%，真实 Train/Apply cycle 为 0，平均长度 5.87。相对 DPO v1 + loop penalty，DPO v2 用多 1 条 final failure 换来了更干净的重复控制（duplicate 7.8% -> 1.4%，beam top-1 usable 98.8% -> 99.2%）；旧 loop 数字不可直接比较，因为包含正常分类链。
- 当前建议：冻结 DPO v2 + `beam_usable_quality` 作为最佳候选，接下来做 30-50 条人工语义抽查；除非抽查发现系统性语义退化，否则不要继续加 epoch。
- Cycle-fixed DPO v2 后续：修正 Train/Apply loop detector 后，不再惩罚正常 `Sample -> Train -> Apply` 分类流程；重建质量偏好对得到 train 8,288 对、val 1,710 对。从 DPO v1 checkpoint 继续 1 epoch 训练到 `outputs_v2/transformer_checkpoints_v4_6_preference_dpo_v2_quality_cycle_fixed`，val preference accuracy 提升到 0.7865（旧 broad-loop DPO v2 为 0.7686）。下一步必须跑该 cycle-fixed checkpoint 的 test 3k eval 和 quality audit。
- Cycle-fixed DPO v2 test 3k 结果：beam top-1 usable 99.1%，final usable 2999/3000，真实 failure 1，duplicate-token rate 2.5%，连续重复 0.02%，真实 Train/Apply cycle 为 0，fallback 2/3000 且都 usable。人工检查 50 条 usable 链，未发现空链/假链/reward hacking，但存在预期中的遥感通用模板复用（`Filter/Select/Reducer/Clip/Math`）和大量 non-blocking `missing_critical_steps` warning。
- `scripts/analyze_final_workflow_quality.py` 新增多样性/模板化诊断：全局唯一链、任务内唯一率和 top3 集中度、Top repeated chains、Select Bands 出现率、重复 Select Bands、非连续重复 Select Bands。Cycle-fixed 3k 报告上：全局唯一链 1,320/2,999（44.0%），Land use 唯一链 477/932（51.2%）且 top3 9.1%，Vegetation 唯一链 303/573（52.9%）且 top3 11.7%，Select Bands 出现 2,556/2,999（85.2%），重复 Select Bands 22/2,999（0.7%）。解释：有跨任务模板，但没有 collapse；Select Bands 高频但通常不是重复调用。

### 2026-05-30 — QGIS GitHub 语料接入审计

已完成：
- 新增 `scripts/audit_qgis_workflow_corpus.py` 离线审计脚本。它读取 `爬取GithubQGIS` 下载语料，从 `QGIS_Input.csv` 构建 QGIS processing algorithm catalog，通过现有 QGIS display name 映射对齐到 L3，统计 workflow 覆盖率，并导出高置信 QGIS->L3 workflow 候选；不修改训练数据。
- 本地审计输出写入 `outputs_v2/diagnostics/qgis_corpus_audit/`。

观察事实：
- 语料结构是混合的。`QGIS_standard_multi_operator_workflows_v2` 最干净，有 1,045 条标准 processing workflow；`github_qgis_workflow_A类` 有 10,827 条；`github_qgis_workflow` 有 8,779 条；`Github_QGIS_RS_Workflows_201509` 有 9,933 条；`Github_QGIS_RS_QGISPlatform_Related_201509` 有 42,550 条。但大集合混有 PyQGIS 对象/方法、插件工具和不一定是 workflow 的 QGIS 相关代码。
- `QGIS_Input.csv` 是算子字典，不是 workflow 数据；其中有 1,292 个 QGIS processing algorithm id 和显示名。
- 现有 `id_mappings_v2.mapping_metadata.qgis_to_l3` 使用的是显示名，不是 `native:buffer` 这种 algorithm id。第一版自动 crosswalk 只能映射 454/1,292 个 alg id（35.1%）。
- workflow mention 映射覆盖率目前不高：standard 为 2,180/4,741（46.0%），A 类为 7,739/20,989（36.9%），general workflow 为 3,616/9,949（36.4%）。严格过滤（2-15 个工具、有输入/输出信号、>=80% 映射）后只得到 111 条唯一高置信 L3 序列。
- 高频未映射工具恰好是重要传统 GIS/QGIS 操作：`native:reprojectlayer`、`native:fixgeometries`、`native:mergevectorlayers`、`gdal:warpreproject`、`native:extractbyexpression`、`gdal:polygonize`、`gdal:rasterize`、`native:joinattributesbylocation`、`qgis:fieldcalculator` 等。这些不是 GIS 概念不存在，而是当前 QGIS display-name-to-L3 映射没有覆盖。

解释：
- 暂时不要把下载的 QGIS 语料直接混进 Transformer 训练。原始语料确实有传统 GIS / 矢量 workflow 信号，但直接训练会引入未映射 alg id、PyQGIS 方法噪声、插件特定工具和弱任务文本。
- 下一步最有效的是扩展并验证 `qgis_alg_id -> L3` crosswalk，然后构建过滤后的 QGIS-L3 数据集。先用于 QGIS transition / I-O / rerank 评估，再考虑 DPO 或 domain-adapted training。

验证：
- `python scripts\audit_qgis_workflow_corpus.py --output-dir outputs_v2\diagnostics\qgis_corpus_audit` -> 完成，写出 catalog/crosswalk/coverage/high-confidence JSONL/Markdown。
- `python -m compileall scripts\audit_qgis_workflow_corpus.py` -> OK。

| 文件 | 修改原因 |
| --- | --- |
| `outputs_v2/diagnostics/open_landing_eval/open_landing_results.csv` | 为 80 条开放式 QGIS landing 任务填写严格人工 `grade` 和 `notes` |
| `outputs_v2/canonical_vector_planning_dataset.jsonl` | 新增 QGIS-derived canonical planning dataset，用于矢量规划监督：任务文本、模态、QGIS 算子链、抽象规划步骤、L3 步骤、full-L3 标记和 required step families |
| `configs/unseen_vector_prompts.jsonl` | 手工 held-out 矢量泛化 prompt benchmark。当前实际为 70 行：61 vector、6 mixed、3 raster；不是从 clean SFT seed 抽样。 |
| `scripts/evaluate_sft_vector_impact.py` | 对比 warmstart SFT 与 DPO v2 在 GEE preservation 和 QGIS vector seed absorption 上的表现；现在显式传每个模型自己的 length stats，SFT 使用 48-task mixed stats，DPO 使用原 47-task quality-gate stats，并支持过采样 SFT checkpoint/vocab/length-stats/report path 的 CLI 覆盖。 |
| `scripts/evaluate_vector_generalization.py` | 对比 DPO v2 与 QGIS-vector SFT 在未见 prompt 上的 expected-family recall、raster/vector token rate、chain length、overlay subtype recall 和抽样预测。脚本现在显式使用每个模型自己的 vocab/length stats、推理前设置 task-type complexity profile、做模态敏感计分，并输出 unsupported-family 和路径/计数 metadata；同时支持过采样 SFT checkpoint/vocab/length-stats/report path 的 CLI 覆盖。 |
| `docs/PROJECT_CONTEXT.md` / `docs/PROJECT_CONTEXT.zh-CN.md` | 记录 QGIS landing 人工审核结果、边界提醒和下一步 bridge/native bridge 补强重点 |
| `docs/PROJECT_CONTEXT.md` / `docs/PROJECT_CONTEXT.zh-CN.md` | 记录 2026-06-06 QGIS 数据可用性只读梳理、当前本地 open landing 等级统计，以及 facts 文本、semantic tags、L3 bridge 混用的数据版本风险 |
| `docs/PROJECT_CONTEXT.md` / `docs/PROJECT_CONTEXT.zh-CN.md` | 在 `canonical_vector_planning_dataset.jsonl` 生成后更新项目定位：QGIS workflow 数据现在是直接的矢量规划监督来源，不只是 landing 证据 |
| `AGENTS.md` | 新增项目级上下文维护协议，让新会话主动读写项目记忆 |
| `docs/PROJECT_CONTEXT.md` | 记录 V4.6 AR-SS 稳定性修复、验证证据、仍需重跑训练，以及旧 `loss=inf` 日志不是 MR 标签证据的解释边界 |
| `docs/PROJECT_CONTEXT.zh-CN.md` | 中文同步记录 V4.6 AR-SS 稳定性修复、验证证据、仍需重跑训练，以及 MR 解释边界 |
| `docs/PROJECT_CONTEXT.md` | 英文版长期交接文档；新增 "Current Scientific Consensus" 综合部分（2026-05-10），整合所有实证发现、基准治理、归因边界和后续会话指南 |
| `docs/PROJECT_CONTEXT.zh-CN.md` | 中文版长期交接文档；新增"当前科学共识"综合部分（2026-05-10） |
| `scripts/run_v4_qg_planner.py` | 新增 V4-QG Phase 1 实用 planner 入口：合并 retrieval 和可选 V4 AR candidates，接入 train-frequency 或 checkpoint Set Predictor prior，综合 soft transition、set coverage、QGIS mapping、规则可用性打分，写出 candidate traces 和 rerank reports，并在不训练、不改 checkpoint 的前提下执行 forbidden-pattern scan；当前默认 Set Predictor prior 已对齐到 V4.6 quality-gate checkpoint 目录。 |
| `scripts/run_v4_qg_planner.py` | 2026-05-19 planner smoke 和 length-path 修复：先构造 `set_prior` 再派生 trained-prior fallback；AR candidates 调用 `set_complexity_profile()` 而不是只设置 expected length；小样本报告的 `None` CI bounds 安全渲染为 `n/a`；`--length-stats` 默认和报告路径改为 `step8_quality_gate`。 |
| `scripts/run_v4_qg_planner.py` | 把 task name / task description 传入 retrieval 候选源，让 query-aware lexical/Jaccard 分数真正影响 planner 候选顺序，而不只是单元测试生效。 |
| `scripts/evaluate_workflow_usability.py` | `LexicalRetrieval` 现在按任务文本 query Jaccard 对同 task workflow 排序，候选不足时再用低权全局 backoff 补齐；同时恢复轻量 workflow-usability 测试辅助 API（record 评估、QGIS mapped-token 提取、forbidden scan）。没有新增 sklearn/embedding 依赖。 |
| `scripts/evaluate_v4_quality_gate.py` | 在 `evaluation_report.json` 中新增 `five_tier_metrics`，并写出 `evaluation_summary.md`；Tier 2/3 workflow usability 与 QGIS landing 优先展示，sequence EM/token accuracy/LCS/SetF1 明确只作为历史 workflow 重现率/诊断指标。 |
| `tests/test_workflow_usability.py` | 覆盖 query-aware retrieval 排序和恢复后的轻量 workflow-usability helper API。 |
| `tests/test_v4_qg_evaluation_report.py` | 覆盖 V4-QG 五层评估报告构造和 Markdown 摘要输出；不加载 checkpoint、不运行推理。 |
| `tests/test_v4_qg_planner.py` | 覆盖质量门禁默认路径（包含 V4.6 Set Predictor checkpoint 目录）、soft transition scoring、set coverage features、candidate-pool 去重与来源保留、规则可用性优先 rerank、forbidden-pattern scan |
| `scripts/compute_task_type_length_stats.py` | 计算 content-token 长度统计并支持显式 CLI 路径；默认读取 quality-gate 数据并写入 `outputs_v2/pipeline/step8_quality_gate/task_type_length_stats.json`，`--legacy-step8` 保留旧 Step8 输出路径。 |
| `scripts/analyze_length_bucket_distribution.py` | 改用共享 length-stats 默认解析器，所以 bucket 分析默认跟随 quality-gate 统计文件。 |
| `src/gis_recommend/data/length_bucket_predictor.py` | 新增 `default_length_stats_path()`，优先级为 `outputs_v2/pipeline/step8_quality_gate` -> `outputs_v2` 根目录 -> legacy `outputs`，避免 task-adaptive EOS bucket 静默优先读旧统计。 |
| `src/gis_recommend/inference/infer_l3_candidates_v4.py` | 期望长度和 task-adaptive EOS 查找改用共享 length-stats 解析器。 |
| `src/gis_recommend/inference/infer_l3_candidates_v4_qg.py` | quality-gate inferencer 的长度统计查找改用共享解析器。 |
| `tests/test_task_type_length_stats.py` | 覆盖 content-token 长度统计、指定输出写入，以及 length-stats 默认路径优先级。 |
| `scripts/evaluate_evidence_aware_ranking.py` | 离线纠偏实验脚本，聚焦六个核心问题中的 Ranking / Evaluation / Semantic Constraint 修复。从已有报告抽取候选池，应用可观测 evidence-aware policy，在 reference 存在时计算 oracle best-in-pool headroom，并输出 JSON/Markdown 诊断；不接入 runtime selection。 |
| `tests/test_evidence_aware_ranking.py` | 覆盖新离线 ranking 契约：可观测证据 tie-break、synthetic 候选排除、缺失分数保持 `None`、oracle 指标必须有 reference、输入记录不被 mutate。 |
| `outputs_v2/diagnostics/evidence_aware_ranking/evidence_aware_ranking.json` | 离线 evidence-aware ranking smoke artifact，比较 legacy、evidence-aware 和 oracle 候选选择。 |
| `outputs_v2/diagnostics/evidence_aware_ranking/evidence_aware_ranking.md` | 离线 evidence-aware ranking smoke 结果的人类可读摘要和契约边界。 |
| `src/gis_recommend/config/transformer_config.py` | 默认运行路径切到 `outputs_v2`；默认 vocab 改为 94；保留 legacy env override；V4.6 quality-gate Set Predictor checkpoint 目录为 `outputs_v2/set_predictor_checkpoints_v3_quality_gate_v4_6` |
| `scripts/build_ontology_kg.py` | KG 构建优先读取 v2 hierarchy 和 v2 id mappings metadata |
| `scripts/build_ontology_kg.py` | 收紧 embedding 载荷读取为 `torch.load(..., weights_only=True)`，只消费张量/快照字段 |
| `scripts/build_ontology_kg.py` | Neo4j KG 构建现在提供服务器 CLI/env 参数，要求密码，默认使用 `outputs_v2` / 94-L3 输入，兼容 v2 hierarchy CSV 没有旧 description 列的行，不传 `--clear` 不清库，只有 `--allow-legacy-inputs` 才允许 legacy 输入回退。 |
| `scripts/import_l3_mappings.py` | 独立 L3 mapping 导入脚本现在默认使用 `outputs_v2/id_mappings_v2.json`，复用 KG 构建里的 v2 mapping loader，支持显式 Neo4j CLI/env 参数，并把 legacy fallback 收到 `--allow-legacy-inputs` 后面。 |
| `scripts/README_KG_BUILD.md` | 更新为当前 v2/94-L3 Neo4j KG 导入流程，说明安全 `--clear` 行为、可选 embedding 导入，以及实例层导入仍需单独审查的限制。 |
| `src/gis_recommend/operators/qgis_candidate_generator.py` | 默认读取 v2 QGIS 映射；人工映射以顶层 `primary_l3` 为准；人工审核映射不被阈值丢弃 |
| `src/gis_recommend/operators/l3_to_platform_mapper.py` | 默认读取 v2 hierarchy/id mappings；解析 v2 QGIS metadata；尊重人工修正 |
| `src/gis_recommend/inference/infer_l3_candidates_v4.py` | 使用配置层 hierarchy 和 id mappings 路径 |
| `src/gis_recommend/inference/infer_l3_candidates.py` | 收紧 legacy V3 checkpoint 读取为 `weights_only=True`，仅从快照字段提取运行配置 |
| `src/gis_recommend/inference/infer_l3_candidates.py` | Phase 15C：inference checkpoint 必须是含 `model_state_dict` 的 supported wrapped payload；`allow_partial_load` 仅为 no-op 兼容参数，加载始终 strict |
| `src/gis_recommend/inference/infer_l3_candidates_v4.py` | Phase 15C：移除 raw state-dict fallback 和 `strict=False` fallback；V4 inference 只加载 supported wrapped checkpoint payload |
| `src/gis_recommend/inference/infer_task_conditioned_v3.py` | Phase 15C：保留 `--allow_partial_load` 作为旧 CLI 兼容参数，但不再改变 loader 行为 |
| `src/gis_recommend/evaluation/runner.py` | 使用配置层 v2 路径进行评测和 reranker 流程 |
| `src/gis_recommend/evaluation/semantic_metrics.py` | 收紧 L3 embedding 读取为 `torch.load(..., weights_only=True)` |
| `src/gis_recommend/evaluation/evaluate_generation_detailed_v3.py` | 收紧 legacy 详细评测脚本 checkpoint/embedding 读取为 `weights_only=True` |
| `src/gis_recommend/evaluation/evaluate_generation_detailed_v3.py` | Phase 15C：详细评测要求 wrapped checkpoint payload；显式 eval-only embedding replacement 后仍 strict 加载模型 |
| `src/gis_recommend/data/__init__.py` | shared data helper 默认 `outputs_v2`，优先 `id_mappings_v2.json` |
| `src/gis_recommend/data/pipeline_provenance.py` | 新增共享 provenance 工具，记录 `id_mappings`、skip list 的 SHA-256、版本、L3 词表和 GEE mapping 数量，并只生成 report-only warning |
| `src/gis_recommend/data/step6_label_with_l3.py` | Step6 产物现在嵌入本次标注使用的 mapping 和 skip list provenance |
| `src/gis_recommend/data/step7_prepare_v4_data.py` | Step7 合并 task metadata 时保留 Step6 provenance |
| `src/gis_recommend/data/step8_clean_v4_data.py` | Step8 写入 cleaned V4 数据前记录 provenance warning，并写出 `provenance_validated` / `provenance_warnings` 快照字段 |
| `src/gis_recommend/data/pipeline_runner.py` | Runner 把选定的 `id_mappings` 和 `skip_list` 继续传给 Step8，保证自定义输出目录也校验正确输入 |
| `src/gis_recommend/training/splits.py` | 新增共享 split 校验/确定性重建工具，检查缺失、非整数、越界、重复和覆盖不完整 |
| `src/gis_recommend/training/train_v4_2.py` | 只有当已有 split 精确覆盖当前 Step8 数据时才复用，否则自动重建 |
| `src/gis_recommend/training/train_v4_6.py` | 通过 V4.2 共享入口继承 split 校验/重建逻辑 |
| `src/gis_recommend/training/train_v4_6.py` | 修复 AR scheduled-sampling 稳定性：CE / early-END penalty 使用未 mask logits，dynamic minimum-length END 禁止只作用于 sampling logits |
| `src/gis_recommend/training/train_set_predictor_v3.py` | Set predictor 训练入口也改用相同 split 校验/重建逻辑 |
| `src/gis_recommend/evaluation/sampling.py` | 评测采样在读取 `test_indices` 后先校验索引范围，避免旧 split 抛出原始 `IndexError` |
| `src/gis_recommend/data/training_data_quality.py` | 新增共享 Step8 训练数据质量审计，检查 schema、L3 不平衡、task 稀疏、split 覆盖、重复、置信度和 mapping source 风险 |
| `src/gis_recommend/data/quality_gate.py` | 新增 V4 质量门禁候选集构建逻辑：隔离低置信 `auto_remap` workflow、合并/过滤稀疏 task type、创建分组 split、写报告、审计 GEE 官方名称 alias |
| `src/gis_recommend/models/transformer_model_v4.py` | V4 模型新增 `bert_model_name` 和 `bert_local_files_only` 参数，便于 smoke test 验证本地缓存 BERT 加载；旧训练默认行为不变 |
| `src/gis_recommend/models/transformer_model_v4.py` | 收紧预训练 embedding 读取为 `torch.load(..., weights_only=True)` |
| `src/gis_recommend/models/set_predictor_v3.py` | Set Predictor 模型新增 `bert_model_name` 和 `bert_local_files_only` 参数；保留旧默认行为，同时允许 quality-gate 训练默认只读本地缓存 BERT |
| `src/gis_recommend/models/set_predictor_v3.py` | Phase 15C：Set Predictor checkpoint loading 要求 supported wrapped payload，并只从 `model_state_dict` 重建结构，不让 snapshot `config` 拥有 runtime authority |
| `scripts/audit_training_data_quality.py` | 新增 CLI，写出 `training_data_quality_audit.json/.md`；只做审计，不改训练数据、不启动训练 |
| `scripts/build_v4_quality_gate_candidate.py` | 新增 CLI，生成 `outputs_v2/pipeline/step8_quality_gate/`，不覆盖 Step8；同时基于爬取官方 operator 写 GEE alias 审计 |
| `scripts/smoke_v4_quality_gate_training_entry.py` | 新增质量门禁 V4 训练入口 smoke CLI；加载候选数据、split、task vocab，用 v2 vocab/embedding 初始化 V4，只跑一次 forward，明确不创建 checkpoint |
| `scripts/train_v4_quality_gate.py` | 新增 quality-gate V4.2 完整训练安全启动脚本；避免原 Step8 默认路径，显式读取候选 data、候选 split、候选 task vocab、v2 embeddings，并写入独立 checkpoint 目录 |
| `scripts/build_quality_gate_transition_matrix.py` | 新增 v2 transition matrix 构建脚本，从 quality-gate train split 统计 `outputs_v2/transition_allowed_next.json`，转换 v2 special token id，并报告/排除越界 token |
| `scripts/train_set_predictor_quality_gate.py` | 新增 quality-gate Set Predictor V3 完整训练安全启动脚本；避免原 Step8 默认路径，显式读取候选 data、候选 split、候选 task vocab，写独立 active-token 文件和独立 checkpoint 目录 |
| `scripts/project_l3_embeddings_v2.py` | 收紧 legacy embedding 合并脚本读取为 `torch.load(..., weights_only=True)` |
| `scripts/audit_pipeline_outputs.py` | audit 报告 provenance warning；`--fail-on-warning` 仅保留为兼容参数，不再非零退出 |
| `tests/test_pipeline_provenance.py` | 覆盖 Step6 provenance、Step7 透传、Step8 缺失/陈旧 provenance report-only warning、audit warning、Runner Step8 参数传递 |
| `tests/test_dataset_splits.py` | 覆盖越界 split 自动重建和合法 split 复用 |
| `tests/test_evaluate_system_sampling.py` | 覆盖评测采样 split 校验和只含 `test_indices` 的部分 split |
| `tests/test_training_data_quality.py` | 覆盖 operator metadata 大小写归一化、split task 缺口和跨 split 重复序列告警 |
| `tests/test_training_data_quality_gate.py` | 覆盖低置信 `auto_remap` quarantine、稀疏 task 合并、分组 split 防泄漏、独立输出文件名、CLI 行为和 GEE alias 审计 |
| `tests/test_v4_training_entry_smoke.py` | 覆盖 quality-gate smoke 默认路径、单 batch forward 不写 checkpoint，以及 HuggingFace 本地 BERT 加载参数透传 |
| `tests/test_v4_quality_gate_training_launcher.py` | 覆盖 quality-gate 训练 launcher 默认路径、显式 split 加载不重建、dry-run 不创建 checkpoint 目录，以及非 dry-run 必须存在 transition matrix |
| `tests/test_v4_6_training_stability.py` | 回归覆盖 AR-SS logits 拆分：target 为 `END_INDEX` 且早于 dynamic min length 时 CE 仍为有限值，但 sampling logits 继续禁止 early END |
| `tests/test_quality_gate_transition_matrix.py` | 覆盖 v2 transition matrix 只从 train split 生成、special token 转换、越界 token 排除、默认输出路径 |
| `tests/test_set_predictor_quality_gate_training_launcher.py` | 覆盖 Set Predictor quality-gate launcher 默认路径、显式 split 加载、只从 train 发现 active token、dry-run 不写文件，以及 HuggingFace 本地 BERT 参数透传 |
| `tests/test_v2_defaults.py` | 覆盖 v2 默认配置、QGIS v2 加载、人工审核映射保留、stale candidate 避免 |
| `tests/test_build_ontology_kg_paths.py` | 覆盖 KG v2 hierarchy 优先级和测试临时目录 |
| `src/gis_recommend/training/train_v3.py` | 去除 legacy trainer 的 metric-best/early-stop 控制；改为每个 epoch 保存 latest snapshot，并用 `weights_only=True` 回载 |
| `src/gis_recommend/training/train_v3.py` | Phase 15C：legacy warm-start / final reload 要求 supported wrapped checkpoint payload，移除 raw state-dict fallback |
| `src/gis_recommend/training/train_v4_3.py` | Phase 15C：warm-start 要求存在 supported wrapped checkpoint payload；runtime 只使用 `model_state_dict` / `task_classifier_state_dict` |
| `src/gis_recommend/training/train_v4_4.py` | Phase 15C：warm-start 要求 supported wrapped checkpoint payload，并把 metric 字段限制为 display-only |
| `src/gis_recommend/training/train_v4_3_rl.py` | 去除 reward-gated best checkpoint 与 early-stop；改为每个 epoch 保存 latest snapshot |
| `src/gis_recommend/training/train_v4_3_rl.py` | Phase 15C：V4.3-RL warm-start 在 missing、raw 或 unsupported-schema checkpoint 上失败，不再 fallback |
| `src/gis_recommend/knowledge_graph/train_graph_embeddings.py` | 去除 val-loss-gated best checkpoint 与 early-stop；改为每个 epoch 保存 `latest` 并保留周期性 epoch 快照 |
| `src/gis_recommend/evidence/__init__.py` | Phase 15C：移除 runtime-enforcement export；evidence package 只允许 snapshot/report-only，必须保持在 runtime imports 外 |
| `src/gis_recommend/evidence/_provenance.py` | Phase 15C：移除 advertised checkpoint loader gate；provenance helper 只能作为观察性 stub |
| `src/gis_recommend/evidence/_metric_bundle.py` | Phase 15C：移除 metric-bundle validation authority；metric bundle 只能是 checkpoint/report snapshot |
| `src/gis_recommend/evidence/_boundary.py` | Phase 15C：boundary metadata 改为 report-only，`verify_import_boundary` 不再 block execution |
| `src/gis_recommend/evidence/_schemas.py` | 修复 import ordering，让 snapshot schema stub 正常 compile |
| `tests/test_reranker_evaluate_system.py` | 修复 `test_interactive_system_repair_is_report_only` 中未定义变量 `summary` 的断言错误 |
| `tests/test_phase15c_runtime_contract.py` | 新增 wrapped checkpoint / schema-only loading、Set Predictor snapshot-config non-authority 的回归覆盖 |
| `tests/test_chain_repair.py` | 更新 report-only repair 断言：拒绝 candidate mutation，repair suggestion 只留在 diagnostics |
| `docs/empirical_bottleneck_audit.md` | 新增实证审计报告，量化 quality-gate 数据结构、label entropy、歧义、transition-mask coverage、简单 baseline、error-taxonomy 证据缺口和实验优先级 |
| `src/gis_recommend/evaluation/empirical.py` | 新增 post-convergence bottleneck validation 的 empirical artifact builder：dataset structure audit、retrieval/Markov baselines、逐样本 prediction diagnostics、error taxonomy、canonicalization audit、decode-policy summary、upper-bound proxy 和工程瓶颈归因 |
| `src/gis_recommend/evaluation/empirical.py` | 新增 `attach_model_predictions_to_artifact`，让 V5_final prediction record 以 storage-only 方式接入现有 empirical artifact，不改变 baseline prediction，也不 gate runtime |
| `src/gis_recommend/models/v5_final/` | 新增隔离 V5_final runtime 包：config、PVM attention、IO mask、AR model、loss、严格 checkpoint save/load、diagnostics、empirical record builder 和 deterministic smoke task embedding |
| `src/gis_recommend/training/train_v5.py` | 新增 V5_final 完整训练/评测引擎：确定性 seed/subset、train/validation loop、gradient clipping、可选 CUDA AMP、early stopping、best/latest checkpoint、IO-mask bias annealing、report-only stability/collapse diagnostics、evaluation report、empirical model-prediction record 和 ablation flags |
| `scripts/train_v5.py` | 新增薄 CLI wrapper，调用 `gis_recommend.training.train_v5`；支持真实 quality-gate dry-run 校验、受控 subset smoke、ablation flags 和训练参数，不引入 runtime governance object；`--disable-pvm` 现在是既有 strict `--no-pvm` runtime flag 的别名 |
| `scripts/evaluate_v5_beam_search.py` | 新增 evaluation-only Stage1 checkpoint beam-search runner，支持 beam 1/3/5/10、可选 length-normalized candidate selection、beam oracle metrics、diversity statistics 和 decode trace artifacts；只 strict 加载 V5 checkpoint，不重训、不修改 checkpoint |
| `scripts/evaluate_v5_retrieval_assisted.py` | 新增最小 retrieval-assisted 评测 prototype：从 train split 做 lexical top-3 retrieval，用 deterministic task-embedding text augmentation 做 eval-time conditioning，输出 generation-only / retrieval-only / retrieval-assisted 指标和 copied/novel operator attribution，不新增可训练模块 |
| `scripts/evaluate_v5_hybrid_planner.py` | 新增 retrieval-centered hybrid planner prototype：top-K lexical retrieval 是 workflow-structure anchor，local expansion 只允许 identity/substitution/insertion/removal <=1 edit 并做 IO filtering，V5_final 只对完整候选打分，输出 hybrid metrics、attribution、candidate traces、preservation metrics 和 modification-rate statistics |
| `scripts/evaluate_v5_hybrid_planner.py` | 新增 multistage retrieval fusion：lexical、embedding、intent、workflow-structure 和 graph-aware L2/L3-code sources；支持可配置 source weights；新增 safe retrieval-confidence rerank selection、contribution attribution、repair outcome aggregation、oracle comparison 和 failure decomposition；不训练、不改模型结构 |
| `scripts/evaluate_retrieval_planning_stages.py` | 新增 retrieval-centered stage evaluator。若 Set Predictor checkpoint 存在则 strict-load，否则显式记录 train-split task-type set-prior fallback；按 operator-set overlap 过滤检索候选，用 execution-aware features rerank，只生成局部 repair candidates，V5_final 只作为完整候选 scorer，并写出可审计 JSON/Markdown reports；不训练、不改架构 |
| `scripts/evaluate_repair_oracle_phase.py` | 新增 evaluation-only local repair oracle runner。从 retrieved identity workflow 构造显式 repair candidate pool，只允许 substitution、bridge insertion、deletion、local swap；对比 best repair、selected repair、identity retrieval 和 retrieval-pool oracle；记录逐候选 attribution 和 failure taxonomy；V5_final 保持冻结，仅作 candidate scorer |
| `scripts/evaluate_repair_selection_diagnostics.py` | 新增 evaluation-only 诊断 runner，只读取已有 repair oracle traces。它分解 retrieval/execution/set/edit/V5/final score terms，量化 identity bias，归因 oracle repair gap，执行 threshold sweep 和 random modified-candidate control，写出 required reports，并做 forbidden-pattern scan；不加载模型、不训练 |
| `scripts/evaluate_repair_scorer_ablations.py` | 新增 evaluation-only ablation runner，只读取已有 repair oracle traces。它按不同 edit/retrieval/execution/set/V5 权重重新打分候选池，比较 adoption/corruption/metric gain，输出量化 scorer recommendation，并写出紧凑 JSON/Markdown reports；不访问 checkpoint 或模型 |
| `scripts/evaluate_repair_calibration_sweep.py` | 新增 evaluation-only uniform edit penalty 校准 runner。它读取已有 repair candidate traces，不加载 checkpoint，重新打分并报告 adoption/corruption/precision/breakage/identity preservation、bootstrap intervals、task/subset stability、CSV curves、Markdown summary 和 forbidden-pattern scan |
| `scripts/evaluate_repair_opportunity_analysis.py` | 新增 evaluation-only repair 归因 runner，只读取持久化 repair traces。它量化 retrieval ambiguity、IO inconsistency、set mismatch、structural anomaly、repair locality、heuristic opportunity indicators、failure taxonomy v2、bootstrap correlation intervals 和 forbidden-pattern scan；不加载 checkpoint、不训练、不生成新候选 |
| `scripts/evaluate_repair_confidence_regimes.py` | 新增 evaluation-only 高置信 regime runner，只读取持久化 repair traces。它 flatten candidates，输出 subtype/context statistics，搜索 runtime-safe precision-first repair subspaces，bootstrap 验证 candidate regimes，对比 random controls，写 Markdown/JSON artifacts，并执行 forbidden-pattern scan；不加载 checkpoint、不训练、不生成候选、不修改 production scoring |
| `scripts/build_unified_workflow_benchmark.py` | 新增多任务 workflow planning benchmark artifact unifier。它读取已有 V5/hybrid reports；在本地缺少 history 时记录用户提供的 V4 quality-gate 与 Set Predictor 指标；写出 JSON/Markdown；并按 task/prediction-mode/metric-scope/vocabulary 分行，避免错误跨任务比较 |
| `scripts/train_v5_final_minimal.py` | 新增最小 V5_final 训练入口，支持 dry-run 校验和一步 smoke training；默认指向 quality-gate 数据，非 dry-run 时才写 strict V5 checkpoint |
| `scripts/infer_v5_final_minimal.py` | 新增最小 V5_final 推理入口，严格加载 V5 checkpoint，并写出带 decode/alpha trace 和 diagnostic graph 的 prediction artifact |
| `configs/v5_final_train_minimal.json` | 新增最小可运行 V5_final 训练配置，记录 quality-gate 路径、模型常量、special-token id 和 runtime-boundary 约束 |
| `configs/v5_final_inference_minimal.json` | 新增最小可运行 V5_final 推理配置，记录 checkpoint、transition matrix、beam/decode 参数和输出 artifact 字段 |
| `docs/v5_final_implementation_notes.md` | 新增 V5_final 最小 runtime 实现说明和 execution-purity 约束 |
| `docs/v5_final_migration_notes.md` | 新增 V4/V5 边界迁移说明、strict checkpoint 兼容性、empirical attachment 和 v2 special-token 映射说明 |
| `docs/v5_final_implementation_report.md` | 新增实现报告，汇总 patch list、runtime contract、empirical output、验证和剩余限制 |
| `docs/v5_system_consolidation_protocol.md` | 新增项目级综合和治理协议，定义最终系统身份、架构语义、能力层级、失败综合、声明治理、生产解释，以及重新开启 generation-centric 或 repair-deployment 声明所需证据 |
| `docs/v5_l2_semantic_recovery_protocol.md` | 新增语义恢复协议，区分当前 L3/operator-token runtime 与长期 L1->L2->L3 架构目标，说明检索中心规划为什么仍需要 L2，并规定未来 L2 恢复工作的允许/禁止边界 |
| `scripts/evaluate_semantic_retrieval_stress.py` | 新增 evaluation-only 语义扰动压力测试脚本。它构造 deterministic paraphrase / synonym / alias / platform-wording / abstraction / word-order 扰动，复用现有 lexical retrieval 路径，量化 retrieval stability、overlap degradation、rerank/top1 robustness、candidate preservation、execution validity preservation、LCS/SetF1/token accuracy degradation 和 lexical sensitivity，并写出 JSON/Markdown/CSV artifact；不训练、不访问 checkpoint、不引入 semantic embedding、不重设计 retrieval |
| `tests/test_semantic_retrieval_stress.py` | 新增扰动族构造、candidate shift / degradation 指标、边界保持型 summary 聚合、脚本入口执行的回归测试 |
| `scripts/evaluate_semantic_indexing_simulation.py` | 新增 evaluation-only 语义索引模拟脚本。它只在评测局部把预定义 alias/intent buckets 用于 retrieval scoring，对比同一扰动族下 lexical retrieval 与 simulated grouped retrieval，并把 recall delta 与 semantic drift、false equivalence、execution-invalid grouping 风险分开报告；不训练、不访问 checkpoint、不使用 embedding model、不使用 LLM rewriting、不实现 production semantic retrieval |
| `tests/test_semantic_indexing_simulation.py` | 新增手工 grouping terms、grouped-vs-lexical 合成检索行为、recall-vs-collapse 归因、summary 声明边界和脚本入口执行测试 |
| `scripts/evaluate_controlled_equivalence_stress.py` | 新增 evaluation-only controlled equivalence stress 脚本。它从现有 mappings 和 retrieval anchors 构造 alias、operator-family、workflow-variant、GEE<->QGIS mapping 压力类，并报告 retrieval preservation、false equivalence、execution-invalid equivalence、workflow corruption、topK retention、LCS/SetF1/token preservation、retrieval saturation change、taxonomy、safe/unsafe tables 和 corruption traces；不训练、不改 checkpoint、不做 vector search、不改 runtime |
| `tests/test_controlled_equivalence_stress.py` | 新增 exact cross-platform alias taxonomy、unsafe same-family substitution、outcome classification、summary metrics 和脚本入口执行测试 |
| `scripts/build_bounded_ontology_inventory.py` | 新增 inventory/governance 构建脚本。它读取当前 v2 mappings、L3 hierarchy、QGIS IO metadata 和 controlled equivalence findings，输出保守 mapping classifications、execution constraints、unsupported GDAL/ArcGIS rows、unsafe mapping registry、workflow-equivalence registry、Markdown summary 和 forbidden-pattern scan；不训练、不使用 embeddings、不实现 semantic retrieval、不做 ontology inference、不改 runtime |
| `tests/test_bounded_ontology_inventory.py` | 新增 exact mapping strictness、same-L2 non-equivalence、execution-sensitive classification、unsupported platform assets、unsafe registry preservation、窄 workflow equivalence registry 和脚本入口测试 |
| `docs/v5_bounded_ontology_inventory_protocol.md` | 新增协议，定义 bounded ontology inventory 的语义、分类标签、执行约束、unsupported-platform policy、unsafe mapping registry、workflow-equivalence boundary 和声明边界 |
| `scripts/evaluate_canonicalized_metrics.py` | 新增严格 evaluation-only canonicalized metric runner。它读取现有 prediction artifacts，用 `compute_canonicalization_audit` 同源逻辑从 quality-gate train split 发现 commutative pairs，复用 `_canonicalize_sequence()`，比较 raw/canonicalized metrics，输出 TopK/per-task/per-pair recovery 和 bootstrap intervals，并写 forbidden-pattern scan；不训练、不访问 checkpoint、不改 retrieval、不做 semantic grouping、不改架构。 |
| `tests/test_canonicalized_metrics.py` | 覆盖 commutative-pair exact recovery、empirical/hybrid artifact 解析、TopK canonical recovery 和 clean forbidden-pattern scan 行为。 |
| `scripts/evaluate_workflow_usability.py` | v1 读取持久化 prediction artifacts 做规则检查；v2 (2026-05-13 重写) 是自包含 evaluation pipeline，直接从 quality-gate 测试数据评估 lexical retrieval baseline，使用 L1/L2 层次类别和 QGIS 映射，不需要模型、checkpoint、训练、语义检索、LLM 评判或执行模拟。 |
| `tests/test_workflow_usability.py` | 覆盖候选可用性规则、missing/harmful/unmapped failure taxonomy、TopK usable recovery 计数、基于 `primary_l3` 和 `all_candidates` 的 QGIS 映射索引构建，以及 clean forbidden-pattern scan 行为。 |
| `scripts/evaluate_multi_reference_workflows.py` | 新增严格 evaluation-only multi-reference workflow evaluator。它只从现有 labeled workflows 中 exact normalized task text/name 匹配派生保守 alternate references，比较 raw single-reference、best-of-multi-reference 和 canonicalized multi-reference 指标，输出 TopK usability deltas、workflow-family summaries、ambiguity taxonomy、recovered examples 和 forbidden-pattern scan；不训练、不改 checkpoint、不用 semantic embeddings、不使用 LLM judging、不改 retrieval、不改 runtime。 |
| `tests/test_multi_reference_workflows.py` | 覆盖 best-of-multi-reference recovery、canonicalized commutative recovery、exact task-text reference pooling、retrieval-vs-generation family deltas、ambiguity labels 和 clean forbidden-pattern scan 行为。 |
| `scripts/evaluate_multiref_validation.py` | Evaluation-only MRV runner。它从 train-split commutative pairs 生成局部相邻交换变体，执行 workflow-semantic gate（sensitive-step / semantic usability / non-degradation / length preservation），把 QGIS mapping 和 QGIS-chain 检查降级为辅助 landing signals，写出 auto-verified candidates，导出可读 `equivalence_review_packet.csv`，并生成只接受人工确认的 `verified_multi_reference_registry.json`；不训练、不改 checkpoint。 |
| `tests/test_multiref_validation_experiment.py` | 覆盖 MRV 相邻交换变体生成、敏感步骤拦截、semantic usable gate、QGIS landing 解耦、auto-labeling、registry eligibility、review packet 导出、manual-only multi-reference registry 构建和人工审查分层采样。 |
| `docs/superpowers/specs/2026-05-14-multiref-validation-design.md` | 记录 MRV 实验设计和边界：在任何训练消融前，先验证当前数据是否足以支持可靠多参考监督。 |
| `docs/superpowers/plans/2026-05-14-multiref-validation.md` | 记录 MRV runner、测试、smoke run 和上下文更新的实施计划。 |
| `outputs_v2/v4_qg_multiref_validation/equivalence_review_packet.csv` | 填入 19 条 auto-verified MRV candidates 的人工审查字段，包括 `human_label`、execution semantics notes、hidden drift notes，以及 CRS/mask/nodata/threshold/aggregation/temporal 风险 flags。 |
| `outputs_v2/v4_qg_multiref_validation/verified_multi_reference_registry.json` | 重建为 manual-only training-eligible registry：7 个 task groups，14 条 accepted equivalent variant sources；4 条 uncertain 和 1 条 not-equivalent 均未入库。 |
| `outputs_v2/v4_qg_multiref_validation/multiref_validation_report.json` 和 `outputs_v2/v4_qg_multiref_validation/multiref_validation_summary.md` | 同步人工审查后的 MRV report/summary 计数，避免后续会话继续继承旧的 0 reviewed groups 状态。 |
| `outputs_v2/v4_qg_multiref_validation/uncertain_deep_review.csv`, `.json`, `.md` | 4 条 previously uncertain MRV candidates 的 source-inspection artifact，包含 equivalence family、conditional constraints、hidden dependency、semantic risk、source operator window 和 reviewer notes；没有新增 training labels 或 registry entries。 |
| `outputs_v2/v4_qg_multiref_validation/equivalence_review_packet.csv` | 新增 deep-review 字段（`source_script_id`、`source_operator_window`、`equivalence_family`、`deep_review_status`、`conditional_constraints`、`hidden_dependency`、`semantic_risk`、`reviewer_notes`），并在 source inspection 后把 `wf46_pos2_swap53_28` 降级为 `not_equivalent`。 |
| `configs/equivalence_taxonomy.yaml` | 新增 MRV equivalence taxonomy 配置：token class、family/risk 定义、conditional constraints、hidden dependencies、risk drivers 和 rejection-type 映射。QGIS landing failure 明确为辅助信号。 |
| `scripts/analyze_mrv_expansion.py` | 新增只读 MRV expansion analyzer。它把 generated variants 分类到 equivalence family/risk bucket，把 validator rejection reasons 映射到研究用 rejection taxonomy，并输出 CSV/JSON/Markdown 分析 artifact；不改标签、不改 registry、不改 checkpoint、不改训练数据。 |
| `tests/test_mrv_expansion_analysis.py` | 新增 taxonomy loading、pair classification、QGIS landing auxiliary mapping、family/risk 总数守恒的回归测试。 |
| `outputs_v2/v4_qg_multiref_validation_expansion_500/*analysis*`, `equivalence_family_summary.csv`, `risk_level_summary.csv`, `family_by_label_summary.csv`, `rejection_taxonomy_summary.csv`, `qgis_auxiliary_rejection_summary.csv` | 500-variant MRV expansion 的分布分析 artifact，用于后续人工审查排序和 equivalence-boundary 分析；这些只是自动分析输出，不是训练标签。 |
| `outputs_v2/v4_qg_multiref_validation_expansion_500/equivalence_review_packet_ai_review.csv` | 46 个 auto candidates 的 AI-assisted review draft。新增 source script id、source operator window、review label、registry recommendation、drift flags 和 reviewer notes；没有覆盖原始 review packet。 |
| `outputs_v2/v4_qg_multiref_validation_expansion_500/equivalence_review_ai_summary.json/.md` | 46-candidate review 摘要：36 equivalent、8 uncertain、2 not equivalent，包含逐条理由，以及第一批 19 与 expansion 46 需要按 variant_id 去重的提示。 |
| `outputs_v2/v4_qg_multiref_validation_expansion_500/verified_multi_reference_registry_ai_draft.json` | 仅供用户确认后晋升的非训练 registry draft：19 groups / 36 equivalent draft variants。不得直接用于训练。 |
| `scripts/build_mrv_registry_v2.py` | 新增 user-confirmed MRV review 合并器。它合并 initial manual review 和 expansion review，按 `variant_id` 去重，只晋升 `equivalent` 行，保留 excluded variants，写出 registry v2 和 equivalence KB v2，并把 `review_flags` 与归一化后的 `risk_level` 分开。 |
| `tests/test_mrv_registry_builder.py` | 新增 registry builder 回归测试，覆盖 token 解析、variant-id 去重、excluded-row 处理、人工 review family/risk 推断，以及防止 `review_flags` 污染 registry risk summary。 |
| `outputs_v2/v4_qg_multiref_validation/verified_multi_reference_registry_v2.json` | 正式 user-confirmed MRV registry v2：42 条 equivalent variants、23 个 task groups；13 条 uncertain/not-equivalent variants 被排除。这是受控 MR training ablation 的输入，不是直接重训主模型的命令。 |
| `outputs_v2/v4_qg_multiref_validation/verified_equivalence_kb_v2.json/.csv` | 行级 equivalence KB v2；每条 accepted variant 记录 source、family、risk、swapped pair、token sequences、constraints、hidden dependencies、review flags 和 reviewer notes。 |
| `outputs_v2/v4_qg_multiref_validation/verified_multi_reference_registry_v2_summary.md` | registry v2 的可读摘要，包含最终计数、清洗后的 family/risk 分布，以及全部 excluded variants。 |
| `scripts/build_mrv_training_ablation.py` | 新增受控 MR ablation 数据构造器。它读取 quality-gate workflow/split/task vocab 与 verified MRV registry v2 / KB v2，以确定性方式选择 verified-MR 子集且不 oversampling，只追加到 train split，复制 task vocab，写出 report/summary/manifest，并记录每条注入样本的 MRV provenance；不会启动训练。 |
| `tests/test_mrv_training_ablation.py` | 新增回归测试，覆盖 train-only 注入、provenance 字段、excluded row 拒绝、subset-size oversampling 防护、隔离 CLI 输出、输入文件不被覆盖，以及 list 形式 `id_to_code` 词表支持。 |
| `outputs_v2/v4_qg_mr_ablation/` | 隔离的派生 ablation 数据根目录，包含 `mr_5`、`mr_10`、`mr_all_42`、各版本 report/summary、复制的 task vocab 和 `mrv_training_ablation_manifest.json`。主 quality-gate 数据和 checkpoint 路径未被改动。 |
| `scripts/compare_mrv_training_ablation.py` | 新增未来 MR ablation report 的只读 comparator。它接收 baseline report 和多个 `NAME=PATH` variant report，可选读取 ablation manifest 以带上 counts/no-training 状态，从异构 report schema 中抽取已知 metric keys，计算 delta/relative delta 和可用时的 paired bootstrap CI，并写出 JSON/Markdown 摘要。 |
| `tests/test_mrv_ablation_comparator.py` | 新增回归测试，覆盖 metric extraction / delta 计算、缺失 metric warning、paired bootstrap CI、manifest counts 绑定，以及 CLI artifact 写出。 |
| `tests/test_v5_training_system.py` | 新增 V5_final 训练系统回归测试，覆盖 IO-mask annealing、soft training mask、确定性 subset、report-only collapse detection、ablation flags、无 FutureWarning 的 smoke training、checkpoint/report 输出和 full-engine CLI dry-run |
| `tests/test_v5_final_runtime.py` | 新增 V5_final contract 测试，覆盖 shape invariant、alpha 行为、IO 合法性、decode、checkpoint strictness、loss purity、diagnostics 和 empirical attachment |
| `tests/test_v5_final_entrypoints.py` | 新增 V5_final entrypoint 测试，覆盖训练 dry-run 校验和推理 artifact 写出 |
| `tests/test_v5_empirical_experiment_scripts.py` | 覆盖 beam oracle/diversity metrics、可选 length-normalized selection、retrieval-assisted copied/novel attribution、retrieval-conditioning text、hybrid candidate expansion/scoring/preservation/top-k helpers，以及脚本文件入口直接执行 |
| `tests/test_retrieval_planning_stages.py` | 新增 operator-set retrieval filtering、filtering pool metrics、严格局部 repair candidate、repair outcome summary、execution-aware rerank feature priority、contribution-channel separation 和脚本入口测试 |
| `tests/test_repair_oracle_phase.py` | 新增 controlled local edit candidate generation、repair attribution delta、oracle repair win / selection failure 分离、failure taxonomy classification、candidate win/corruption aggregation 和脚本入口测试 |
| `tests/test_repair_selection_diagnostics.py` | 新增 score decomposition、modified-candidate suppressor、identity-bias metrics、oracle-gap classification、threshold sweep、random modified-candidate control 和脚本入口测试 |
| `tests/test_repair_scorer_ablations.py` | 新增 no-edit promotion behavior、piecewise operation penalties、ablation gain/corruption/oracle-ceiling summary、low-corruption policy recommendation 和脚本入口测试 |
| `tests/test_repair_calibration_sweep.py` | 新增 calibration metrics、bootstrap interval、region classification、artifact writing 和脚本入口测试 |
| `tests/test_repair_opportunity_analysis.py` | 新增 repair opportunity signal extraction、precision/recall/corruption indicator summary、弱/不稳定信号告警、artifact writing 和脚本入口测试 |
| `tests/test_repair_confidence_regimes.py` | 新增 repair subtype/context extraction、subtype gain/corruption 分离、precision-first regime reporting、random controls、artifact writing 和脚本入口测试 |
| `tests/test_unified_workflow_benchmark.py` | 新增 unified benchmark row typing、comparison-group separation、必需 benchmark family 覆盖和脚本入口执行回归测试 |
| `scripts/build_empirical_evaluation_artifact.py` | 新增薄 CLI wrapper，用于生成 `gis_recommend.empirical_evaluation.v1` artifact；不训练、不执行模型 |
| `tests/test_empirical_evaluation.py` | 覆盖 error taxonomy、canonicalization audit、artifact 必需 diagnostics、engineering attribution 字段和 retrieval tie ordering 的确定性 |
| `pyproject.toml` | 新增 `gis-empirical-evaluate` console script，指向 empirical artifact builder |
| `outputs_v2/evaluation_reports/empirical_v2_smoke_artifact.json` | 生成质量门禁 split 的 20 样本 baseline-only empirical smoke artifact |
| `outputs_v2/evaluation_reports/empirical_v2_smoke_artifact.md` | 生成精简工程报告，汇总 baseline metrics、top error categories、bottleneck attribution 和下一版 benchmark suite |
| `src/gis_recommend/evaluation/run_contract.py` | 新增 Step8 + V4.6 主线运行契约：token profile、data authority manifest、repair capability level、selection policy 和 L2 role，用于报告解释边界。 |
| `src/gis_recommend/evaluation/semantic_metrics.py` | 主线序列指标现在通过 active token profile 剥离 Step8 负数 special 和 V4.6 内部 special，不再假设 legacy 350-L3 控制 token。 |
| `src/gis_recommend/evaluation/report.py` | `build_report_json()` 可嵌入 run-contract metadata，并为逐样本报告写出 decision trace，区分 decision features、diagnostics、hard constraints 和 posthoc metrics。 |
| `src/gis_recommend/evaluation/runner.py` | `gis-evaluate` 现在构造主线运行契约，把 token profile 传给 semantic metrics，把 v2 I/O metadata authority 传给 verifier/executable diagnostics，并新增显式 `--io-types` / `--allow-legacy-io-types` 参数。 |
| `src/gis_recommend/reranking/reranker_verifier.py` | `CandidateVerifier` 默认消费主线 data authority；如果 `outputs_v2/qgis_operator_io_types.json` 缺失，则 I/O 诊断降级为 neutral/missing，不再静默加载 legacy `outputs/`。 |
| `src/gis_recommend/operators/qgis_candidate_generator.py` | `QGISCandidateGenerator` 新增 `run_contract` / 显式 `io_types_path` 输入，I/O metadata 通过和主线 verifier/report 相同的 data authority 解析，并记录 `score_components`，避免 `qgis_score` 成为不可解释的压缩字段。 |
| `src/gis_recommend/evaluation/reranker_pipeline.py` | 后置 QGIS evaluation 现在把 active run contract 传给 `QGISCandidateGenerator`，让 QGIS landing diagnostics 和主线运行保持同一 metadata authority。 |
| `src/gis_recommend/evaluation/report.py` | 当 reranker 选中的 QGIS candidate 提供 `qgis_score_components` 时，逐样本报告和 decision trace 会保留该分解。 |
| `scripts/evaluate_v4_quality_gate.py` | V4-QG evaluation report 和 five-tier metrics 现在写入 `system_lineage=research`、`mainline_eligible=False`、`v4_6_quality_gate_candidate` model profile；CLI/docstring 改为 candidate/research，不再称 mainline。 |
| `src/gis_recommend/config/transformer_config.py` | Quality-gate 配置注释现在把 V4-QG 标为 candidate/research profile，并明确它不替代 Step8 + V4.6 `gis-evaluate` 主线。 |
| `scripts/run_v4_qg_planner.py` | 报告 governance 现在标记 V4-QG planner artifact 为 research/non-mainline，避免与 Step8 + V4.6 `gis-evaluate` 主线报告混用。 |
| `scripts/evaluate_v5_hybrid_planner.py` | V5 hybrid report 新增 lineage/mainline eligibility 元数据，明确其是 research artifact。 |
| `scripts/evaluate_retrieval_planning_stages.py` | Retrieval-stage report 新增 lineage/mainline eligibility 元数据，明确其是 research diagnostic。 |
| `tests/test_mainline_run_contract.py` | 新增 v2 token 剥离、legacy token profile 兼容、报告 contract metadata、verifier I/O metadata 默认行为回归测试。 |
| `tests/test_qgis_candidate_generator_logging.py` | 新增 QGIS candidate `score_components` 回归测试，确保 decision trace 可以解释 `qgis_score` 来源。 |
| `tests/test_v4_qg_evaluation_report.py` | 新增 V4-QG five-tier report 的 research/non-mainline 机器可读字段回归测试。 |
| `src/gis_recommend/evaluation/run_contract.py` | 给报告契约新增 Phase0/Phase1 状态字段：`candidate_pool_enabled`、`decision_core_mode`、`retrieval_mode`、`l2_authority`。 |
| `src/gis_recommend/evaluation/shadow_phase.py` | 新增 report-only helper：构造 candidate pool trace、evidence bundle、shadow decision summary 和 lexical train-split retrieval shadow pool；不修改 legacy selection。 |
| `src/gis_recommend/evaluation/report.py` | 逐样本输出 `candidate_pool_trace`、`evidence_bundle`、`decision_trace.shadow_decision_core`，同时保留现有 legacy metrics 和已选 token。 |
| `src/gis_recommend/evaluation/runner.py` | 新增可选 `--retrieval-shadow-k`，用于把 train-split lexical retrieval shadow candidates 写入报告；默认关闭，不改变 inference / reranker selection。 |
| `tests/test_mainline_shadow_phase.py` | 覆盖契约状态字段、candidate pool trace 必含 legacy selection、evidence 缺失语义、shadow decision 输出，以及 retrieval shadow 只读 train split。 |

## 已踩坑 / 不要重复

| 坑 | 结论 |
| --- | --- |
| 混淆原始路线产出、去重候选数和最终训练包行数 | Phase 9 有多个都合理但口径不同的数量：`vector_training_samples_llm_FULL.jsonl` 是描述到 L3 的原始输出，本地为 19,738 行；`API_trace_to_L3_TRAINING_FINAL.jsonl` 是 API-trace 批次去重合并，本地为 6,031 行；`_final_merge.py` 中“约 16,800”来自 6,031 条 API-trace 样本加 10,768 条 Route 1+2 unified 样本，即 16,799。报告“16,800”时必须说明这是合并候选数据口径，不一定等同最终训练包行数。 |
| 让临时 LLM/API key 进入项目文件 | 项目约定是只通过环境变量读取（`DEEPSEEK_API_KEY` / `LLM_API_KEY`），脚本、进度日志和辅助 `.bat` 文件都不能落明文 key。2026-06-24 已清理 `run_process.bat` 和 `progress.md`。本地生成缓存如 `.codegraph/codegraph.db` 可能仍含索引过的历史/爬虫字符串；不要把这类缓存作为项目产物分享，分享前应排除或重建。 |
| 把 QGIS facts self-retrieval 当成开放用户输入准确率 | `facts_summary` 文本入索引后的 100%/99% recall 是 source-file 级 self-retrieval，证明索引修好了、任务文本信息量足够；不能直接写成任意用户自然语言都能 100% 找回正确 QGIS 链。 |
| 把 QGIS landing 提升等同于矢量规划能力提升 | QGIS 检索多样性、semantic tags 或 modality match 变好，不等于小模型已经学会矢量处理规划。QGIS workflow 数据应被用来定义/评估矢量 intent，并把规划落到可执行 QGIS 链；主要结论仍应落在矢量步骤规划质量上。 |
| 把不同 QGIS 数据版本当作字段等价 | `qgis_chain_dataset.jsonl` 有较多 L3 bridge 和 semantic tags，但 task_text 噪声较大；`qgis_chain_dataset_v2_enriched_v3.jsonl` 有 facts 文本和 semantic tags，但没有 L3 bridge；`qgis_vector_chain_candidates.jsonl` 有干净 modality 和部分 bridge，但没有 task text；`qgis_vector_chain_described.jsonl` 是弱生成描述。应按任务选择版本，或先构造 canonical merged dataset。 |
| 误数 canonical vector planning dataset 的 full-L3 样本 | `outputs_v2/canonical_vector_planning_dataset.jsonl` 的 1,046 条 full-L3 是全模态总数，不是纯矢量 full-L3 数。纯矢量 full-L3 子集是 733 条；纯矢量总数是 1,598 条。做 SFT/preference split 或报告训练规模时必须分清口径。 |
| 把 `has_full_l3=true` 当成词表合法 | `has_full_l3` 当前只表示没有空 L3 slot，不表示所有 L3 code 都存在于 `classification_hierarchy_v2.csv`。140 行含有 `L3_02_05_04`，其中纯矢量 full-L3 有 45 行；当前 94-L3 词表没有 `L3_02_05_04`，但有 `L3_02_05_11` 表示 Feature to Point / centroid 类转换。SFT 前必须修正或过滤。 |
| 不加质量过滤就训练全量 canonical vector dataset | 全量 2,319 行适合做弱监督、coverage mining 和 bridge repair，但不能原样作为干净 SFT。即时 SFT 应使用严格纯矢量有效子集（本次审计过滤后 610 行），或先修正/remap 后重新跑质量检查。 |
| 把 685 条 clean SFT seed 当成任意细粒度语义真值 | `outputs_v2/canonical_vector_clean_sft_seed.jsonl` 中 overlay/centroid 粗映射 bug 已修复：intersection/difference/union/symdiff/clip 现在使用不同的当前词表 L3，`L3_02_05_04` 已消失。剩余标签仍受当前 taxonomy 粒度限制：geometry repair/validation/simplify/delete-holes 共用 `L3_02_07_01`，raster sampling/rasterize/polygonize 共用 `L3_03_01_01`。这对当前 94-L3 family 级 SFT 可接受，但不能说成完全细粒度 operator 语义真值。 |
| 把 `configs/unseen_vector_prompts.jsonl` 当成 55/8/7 split | 当前文件是 70 行，但实际 split 是 61 vector / 6 mixed / 3 raster。仍可作为 held-out prompt benchmark 使用，但报告必须以脚本打印的真实计数为准；如果实验设计必须是 55 / 8 / 7，需要先补/改 prompt 文件。 |
| 把 unseen expected-family recall 当成完整细粒度 QGIS 语义准确率 | 当前 94-L3 taxonomy 无法表达所有手工 family，例如 nearest、tessellation、density、random sampling、concave hull、triangulation、rasterize、polygonize、raster sampling、contour、gap fill。评测时应优先看 measurable recall；strict/all recall 是覆盖压力信号，不能把 unsupported family 直接解释成模型语义失败。 |
| 把 SFT 的高 vector-token rate 当成矢量规划已解决 | 未见任务评测显示的是明显的 vector-regime shift，不是完整语义解决。SFT 在 vector prompt 上更愿意输出矢量 token，但命中集中在 `spatial_filter`、`spatial_join/table_join`、`buffer`、`merge`；许多核心 family 仍为 0-hit。应表述为“学到了矢量模式 + 部分 family recall”，不能写成完整 QGIS 矢量规划能力。 |
| 以为 QGIS Step8 包自动实现 5:1 混训 | `outputs_v2/pipeline/step8_qgis_vector_sft/` 是 Step8 兼容包，现有单数据集训练入口能读取它；但当前脚本没有实现“每 5 个 GEE batch 插 1 个 QGIS batch”。真正混训还需要合并加权数据集、双 dataloader batch mixer，或显式 sampler 策略。 |
| 把合并包的 1.1% QGIS train 占比当成 5:1 训练计划 | `outputs_v2/pipeline/step8_quality_gate_qgis_vector/` 把 685 条 QGIS 样本全部注入 62,180 条 train split，因此 QGIS 只占 train 的 1.1%。这是保守领域提示，不是此前建议的 GEE:QGIS=5:1 batch ratio。 |
| 直接把 QGIS-only task vocab 与 GEE 数据混用 | QGIS SFT 包本地 task vocabulary 只有 `"Vector Analysis": 0`。真实 GEE+QGIS 混训需要 combined task vocabulary 和稳定 id 分配，否则 task-type id 会冲突或静默改变语义。 |
| 不适配就用当前 47-task checkpoint warm-start 48-task 合并包 | 现有 quality-gate 和 DPO v2 checkpoint 的 `task_type_embedding.weight` 形状是 `[47, 256]`，task classifier 也是 47 类。当前 `load_warmstart_checkpoint()` 严格调用 `model.load_state_dict(...)`，所以 `--warmstart` 到合并包 48-task 模型会失败；必须跳过/扩展 task-type 专属权重，并显式初始化新的 `"Vector Analysis"` 行。 |
| 把 5-epoch from-scratch 和 5-epoch warmstart 当作公平对比 | 这两个 run 的训练制度不同。显式 `--num-epochs` 时，from-scratch 会保留 `tf_phase_epochs=10`，所以 5 epoch from-scratch 是 TF-only；warmstart 会设 `tf_phase_epochs=0`，所以 5 epoch warmstart 从 epoch 1 就是 AR scheduled sampling。from-scratch 5 epoch 只能当链路 smoke，不能当公平能力基线。 |
| 不隔离 checkpoint 目录就比较不同训练路线 | 服务器 smoke 中 from-scratch 和 warmstart 都写入 `outputs_v2/transformer_checkpoints_v4_6_quality_gate_qgis_vector`。第二次 run 会覆盖 `best_model.pth`、`latest_model.pth`、history 和 selection manifest。后续比较应使用 `_scratch5`、`_warmstart5` 这类独立目录。 |
| 给 `scripts/train_v4_6_quality_gate.py` 传 `--lr` | V4.6 quality-gate launcher 当前没有 `--lr` CLI 参数，学习率来自内部 `V4_6_BERT_LR` / `V4_6_OTHER_LR` 常量。带 `--lr 1e-5` 的命令会 argument parsing 失败，除非先扩展训练入口。 |
| 忽略 QGIS/mixed length stats | 合并包训练应传 `outputs_v2/pipeline/step8_quality_gate_qgis_vector/task_type_length_stats.json`。V4 inferencer 现在也支持显式 `length_stats_path`；混合 48-task checkpoint 推理/评测时应传该路径，避免 `"Vector Analysis"` 回退到默认 47-task quality-gate stats。 |
| 复用过期 open landing 审核计数 | 当前本地 `open_landing_results.csv` 解析为 A=18 / B=33 / C=29，模板集中度也已改善。早期 A=2 / B=23 / C=55 是历史阶段证据，除非明确恢复旧 CSV 快照，否则不要继续当作当前状态。 |
| 把 GRPO 当成当前矢量短板的下一步训练方案 | 100 个矢量 prompt 的 GRPO headroom 诊断显示 worth training 为 0%，平均 gap 只有 0.031；当前 DPO 模型 beam 候选过于相似。除非后续 headroom 显示有强、多样、可靠 reward 分离的候选，否则不要启动 GRPO。 |
| 把 QGIS reranker 当成召回覆盖修复 | Reranker 只在 gold/相近链已经进入候选池时有用，不能补回没有被 retrieval 召回的链。应先保证 retrieval recall，再把 reranker 作为池内排序器；池内 Top-1 不能写成端到端准确率。 |
| 信旧日志 | `outputs_v2/_step6_final.log` 是旧日志，写着 556 GEE mappings / 62 skip；当前真相是 551 / 67 |
| 默认相信 `all_candidates[0]` | v2 人工修正可能只更新顶层 `primary_l3`，旧候选列表不一定同步 |
| 用数值阈值过滤 `manual_reviewed` | 有些人工保留项旧 confidence 很低，例如 `Write Vector Tiles_mbtiles` 是 0.1944 |
| 把 QGIS 映射当成 Step1-8 输入 | Step1-8 使用 GEE -> L3；QGIS 是后续 L3 -> QGIS 落地链 |
| 以为所有脚本都已迁到 v2 | 仍有部分非主链路脚本硬编码 `classification_hierarchy.csv`、`outputs/l3_embeddings.pt` 或 350 vocab |
| 把旧 V4.6 AR-SS `loss=inf` 日志当作 MR 标签证据 | 已定位根因是 trainer 侧 dynamic-min-length END mask 污染 CE logits。旧 `mr_all_42` 日志只能说明修复前训练稳定性问题；比较 MR 效果前必须重跑 baseline 和 MR 分支。 |
| 把 2026-05-21 前的 Step8 + V4.6 序列报告当成 token-contract 干净 | 当前代码已修复 metric token contract，但旧报告可能仍把 Step8 负数 special 或 V4.6 内部 special 混入指标。用旧 LCS/token accuracy/SetF1/SeqEM 做 checkpoint 或消融结论前，必须重算或显式标注。 |
| 把 V4.6 `repair` 当作已应用的运行时修复 | `gis-evaluate --use-repair --use-reranker` 会写 `repair_candidate_chain` 和 diagnostics，但 `repair_applied=False`、`changed_chain=False`、`repair_stats.applied=0`。只能称为 report-only repair suggestion，不能称为自动修复闭环。 |
| 把 execution-aware diagnostics 当作稳定决策权威 | `StructuredReranker` 和 `TwoStageReranker` 当前按候选/模型/set/长度/unknown 等直接信号打分或剪枝；validation 与 I/O compatibility 可被抽取和报告，但在 Step8 + V4.6 主线中不是硬决策权威。 |
| 把 `qgis_score_components` 当作硬约束 trace | `qgis_score_components` 只是解释 QGIS candidate generation 聚合出的 `qgis_score` 来源，包括 mapping score 和 I/O factor。只有 reranker 真实从 QGIS candidates 中选择时，它才是 decision evidence；后置 QGIS/executable diagnostics 仍是 diagnostics。 |
| 看到 v2 QGIS I/O metadata 缺失就以为系统会自动用 legacy | `CandidateVerifier` 现在默认查 `outputs_v2/qgis_operator_io_types.json`；缺失时报告 `fallback_status=missing`，不会静默读 `outputs/qgis_operator_io_types.json`。Legacy I/O metadata 只能通过显式 compatibility profile 使用，并会让该运行不具备 mainline eligibility。 |
| 把 `mainline_eligible=True` 理解成数据资产完整 | 它只表示运行没有进入不允许的 legacy profile，不代表 `outputs_v2/qgis_operator_io_types.json` 等可选资产存在；解释 I/O/executable diagnostics 前必须看 `io_metadata_profile.fallback_status`。 |
| 继续运行旧 Neo4j KG 导入命令 | 旧 KG 脚本可能默认清空 Neo4j，并静默混入 legacy 350-L3 路径。服务器上应使用当前 `scripts/build_ontology_kg.py` CLI，显式传凭据并默认读取 `outputs_v2`；只有明确要干净重建时才加 `--clear`。 |
| 把 shadow decision 或 retrieval shadow 当成 runtime selection | Phase0/Phase1 shadow 输出只能作为报告。`decision_trace.shadow_decision_core.shadow_selection` 和 `retrieval_shadow_pool` 不得在没有 Phase2+ 契约变更的情况下替换 `l3_res["pred_tokens"]`、reranker top-1、beam 顺序或 legacy metrics。 |
| 依赖 `git diff` | 当前 `system_redesign` 在这个环境里不是 Git 仓库根目录 |
| 使用 `rg` | 当前环境未安装 `rg`，用 PowerShell `Get-ChildItem` + `Select-String` 替代 |
| 把当前 `outputs_v2` Step6-8 产物当作 provenance-clean | 这些产物早于 2026-05-07 provenance gate 生成，现在严格 audit 会报 `missing_provenance`；训练/评测前需要重跑 Step6-8 或显式接受旧产物 |
| 只因为 `dataset_splits_v4.json` 存在就复用 | split 可能对应清洗前样本数量；训练和评测前必须校验索引范围、重复和完整覆盖 |
| 把结构干净的 Step8 文件等同于模型质量干净 | 当前 Step8 没有 schema/mapping/skip 泄漏，但仍有严重 L3/task 不平衡、低置信 auto_remap 片段和 split 设计问题，足以解释模型效果差 |
| 把 `task_type` 当成无关 metadata | V4 使用 task-type embedding 和 task-classification auxiliary loss；1 条样本的 task type 和 val/test-only task type 会直接影响训练和评估解释 |
| 把小写 GEE operator 当成官方 API 名称 | Step4 会小写化 operator，Step6 用大小写不敏感匹配；这对 GEE->L3 标注是安全的，但官方 API / 代码生成需要从爬取的 `gee_operators.json` 的 `name` 和 `code_examples` 里补 canonical alias，尤其是 `ee.Algorithms.Landsat.simpleComposite`、`ee.Algorithms.Image.Segmentation.SNIC` 这类嵌套 API |
| 误以为质量门禁候选集解决了所有模型风险 | 它解决了 split 泄漏、稀疏 task 缺口和最大低置信 `auto_remap` 噪声，但 active L3 降到 47/94，Top20 token share 升到 94.77%；训练仍需要处理不平衡，或人工审核后把部分 quarantine 数据加回来 |
| 混淆旧 `task_conditioned_checkpoints_v3*` 和当前完整系统链路 | 当前 quality-gate 流程使用 V4 Transformer checkpoint 加可选 Set Predictor checkpoint。旧 `task_conditioned_checkpoints_v3*` 是遗留/参考产物；原 `train_set_predictor_v3.py` 仍默认读原 Step8，quality-gate 实验应使用新的 launcher |
| 把旧 transition matrix 复制到 v2 | `outputs/transition_allowed_next.json` 属于旧 350-L3 体系，包含超出 v2 `TOTAL_VOCAB_SIZE=98` 的 id；复制到 `outputs_v2` 可能导致 transition loss 崩溃或引入错误转移。必须通过 `scripts/build_quality_gate_transition_matrix.py` 重建 |
| 把 V5 governance object 扩展成 runtime controller | 唯一有效判断标准是：删除该对象是否会改变 runtime-observable behavior。runtime execution 可以向 snapshot、validation、tooling/reporting 单向输出事实；但 snapshot、manifest、metric ontology、compatibility result、dataset lineage、report 不能反向修改 trainer、inferencer、loader、optimizer、sampler、checkpoint selector 或 decode 语义 |
| 把 provenance、audit warning、validation 或 metric bundle 当成执行门禁 | 严格 execution-only contract 下，这些都是 interpretive outputs。它们可以被记录或报告，但不能决定 data loading、checkpoint loading、decode behavior、chain repair、reranker selection，或 runtime execution 的进程成败 |
| 重新引入 partial checkpoint loading | 活跃 runtime 路径禁止 `strict=False`、raw state-dict fallback 和由 `allow_partial_load` 驱动的行为。只能加载 supported wrapped checkpoint，且只有 `model_state_dict` 加 direct runtime config 能影响执行 |
| 把旧 `outputs/evaluation_reports` 当成当前 v2 证据 | 这些报告指向 legacy `outputs/` 350-L3 checkpoint，例如 `outputs/transformer_checkpoints_v4_6/best_model.pth`。它们只能作为历史警示，当前 v2 / quality-gate 结论必须依赖 `outputs_v2` 评测产物 |
| 把 empirical smoke artifact 当成模型结果 | `outputs_v2/evaluation_reports/empirical_v2_smoke_artifact.*` 是 baseline-only，且记录 `model_predictions_run=False`。它是 artifact schema 和 baseline 证据，不是 V4/V5 模型性能。 |
| 误以为 transition matrix 是强 oracle | quality-gate train transition mask 覆盖 99.9575% test transitions，但 48 个状态上的 weighted average outdegree 是 40.91，说明它非常宽松，不能解释全局 workflow correctness |
| 把 exact-match baseline 为 0 直接理解成纯模型失败 | quality-gate grouped split 本来就消除了跨 split exact sequence leakage；而 broad task type 的 sequence entropy 很高、有效链路变体很多，所以 exact-match-heavy 评测天然脆弱 |
| 把 V5_final 实现当成已训练模型结果 | 新 V5_final 路径只是 runtime/instrumentation。当前还没有受控训练出的 V5_final checkpoint；smoke task embedding 只是为了无网络下载地跑通入口。 |
| 用 V5_final loader 加载 V4 checkpoint | V5_final loader 会拒绝 raw、V4、缺失 PVM key 的 payload。未来如需 V4 warm-start，必须是显式工具，不能变成 loader fallback。 |
| 让 stability / collapse report 反向控制执行 | V5_final collapse 指标只能 report-only。不得改变 optimizer、checkpoint selection、decode ranking、dataset selection 或 loader fallback。 |
| 把语义扰动脆弱性当成 L2 已验证 | semantic retrieval stress artifact 说明 lexical/operator-level retrieval 在 abstraction / paraphrase 下会退化。这只能支持后续研究 semantic indexing，不能证明 L2 已有效，不能说明已实现 semantic retrieval，也不能把 operator-level 错误重新标注为正确。 |
| 把粗粒度语义分组当成安全 semantic indexing | semantic indexing simulation 显示宽泛手工 bucket 的 recall / preservation delta 为负，并伴随较高 false-equivalence / drift 风险。这不否定 L2，但禁止把粗糙 alias/intent grouping 说成可部署。未来 semantic indexing 必须使用更窄、预先定义的 equivalence classes，并证明有 recall gain 且没有 unsafe collapse。 |
| 把 same-family 或 workflow-shape variants 当成安全等价 | Controlled equivalence stress 显示当前诊断里只有 exact alias 和 exact unambiguous GEE<->QGIS mapping 稳定/安全。Same-L2 substitution、adjacent reorder、bridge expansion、ambiguous/composite mapping 必须继续视为 unsafe 或 ambiguous，除非未来有独立证据证明 execution-preserving equivalence。 |
| 把 bounded ontology inventory 当成已部署 semantic retrieval | Bounded inventory 只是离线治理清单。13 条 exact 行是保守候选，不是 active runtime rules；partial / execution-sensitive / ambiguous / composite 行不能当作等价，GDAL/ArcGIS 行因当前没有映射资产必须保持 unsupported。 |
| 把 retrieval-stage set prior fallback 当成已训练 Set Predictor | 本地仍缺少 `outputs_v2/set_predictor_checkpoints_v3_quality_gate/best_model.pth`。`evaluate_retrieval_planning_stages.py` 支持有 checkpoint 时 strict-load，但当前报告使用 train-split task-type operator-frequency prior，并在 artifact 中明确标记。 |
| 误以为当前 V4 评测入口默认已经对齐 quality-gate | `scripts/train_v4_quality_gate.py` 和 `scripts/train_set_predictor_quality_gate.py` 已经对齐 `step8_quality_gate`，但 `src/gis_recommend/evaluation/runner.py`、`src/gis_recommend/evaluation/sampling.py`、`src/gis_recommend/evaluation/reranker_pipeline.py`、`src/gis_recommend/inference/infer_l3_candidates_v4.py` 默认仍会落到旧 Step8 / `dataset_splits_v4.json` / V4.6 checkpoint，除非显式传路径或增加专门的 quality-gate wrapper。 |
| 把 `mr_5` / `mr_10` 误读成百分比注入 | 当前 ablation artifact 注入的是 5 条或 10 条 verified variants 的确定性子集，不是 train split 的 5% 或 10%。实际 train 注入率很小（5/61,495 和 10/61,495）；如果后续需要真正百分比级增强，必须另行设计，且不能 oversampling 或制造泄漏。 |
| 以为 MR ablation artifact 表示已经训练过 | `outputs_v2/v4_qg_mr_ablation/` 只包含派生输入数据。manifest 明确记录 `no_training_started=true`；在单独训练 checkpoint 并与 quality-gate baseline 对比前，不能声明模型效果变化。 |
| 把 MR ablation comparator 当成 evaluator | `scripts/compare_mrv_training_ablation.py` 只比较已有 report。它不会执行模型推理、生成预测、从 raw candidates 计算 usability，也不会训练 checkpoint。输入 report 缺失的指标会被记录为 missing，而不是静默补 0。 |
| 把 `mr_all_42` 训练日志当成 MR 标签有害的证据 | 这次 run 被 V4.6 AR scheduled-sampling 不稳定（epoch 11 后 `Train: Loss=inf`）、epoch 50 latest checkpoint 评测、缺少同 trainer / 同 checkpoint policy 的 V4.6 quality-gate baseline control 共同混淆。它目前更像训练/评测协议问题，而不是 MR 标签质量结论。 |
| 未检查硬件就启动本地完整 MR 训练 | 当前本地 workspace 是 CPU-only，且没有 baseline/MR checkpoints。训练应在用户服务器/GPU 上跑；本地只应在服务器 checkpoint/report 同步回来后继续评测和对比。 |
| 把 local repair 的 `modified_selection_rate=0` 当成 repair 没价值 | Repair oracle phase 显示非 identity repair 在 oracle 选择下经常能提升 retrieved identity。当前主要阻塞是 scorer/reranker 识别不了有用 repair，不一定是局部编辑本身没有价值。 |
| 把 oracle repair gain 当成可以大范围接受 repair 的许可 | Repair selection diagnostics 显示随机 modified-candidate selection 是负收益，即使 aggressive score-margin acceptance 的净 LCS 提升也很小。有用 repair 确实存在，但接受策略需要校准 scorer 和归因验证，不能随机或无条件接受局部编辑。 |
| 直接删除 edit penalty | Repair scorer ablations 显示 no-edit-penalty 会采用所有 modified repair，但 mean LCS 下降且 corruption 达到 32%。Edit penalty 当前 0.20 过强，但它仍是必要安全项；应测试有边界的下调，而不是删除。 |
| 直接推广 50 样本的 `uniform_edit_0_12` 结果 | 更大的 200 样本 calibration sweep 没有确认 50 样本正收益。`uniform_edit_0_12` 的 mean LCS 为 -0.00111538，bootstrap interval 跨 0；更低 penalty 会 over-adopt，no-penalty collapse。不要根据 50 样本结果把 uniform penalty 改动生产化。 |
| 把宽泛 repair opportunity indicator 变成 runtime gate | 200 样本 opportunity analysis 显示 high retrieval ambiguity、set-deficit/length anomaly 这类宽泛指标触发 100% 样本，没有区分度。IO validity / transition 信号在该 trace 中也是平的。除非后续验证出更窄且稳定的 confidence feature，否则这些只能作为 report-only diagnostics。 |
| 把 oracle-only confidence regime 当成可部署 repair policy | Confidence-regime 阶段发现 12 个 oracle-only subspaces，但 score-selected high-confidence regimes 为 0。Oracle-only subspace 只能证明候选存在，不能证明 scorer 能选择；在出现通过 corruption 和 bootstrap 条件的 score-selected policy 前，不得把它们变成 runtime gate 或 scorer 改动。 |
| 把 consolidation protocol 当成新架构 | `docs/v5_system_consolidation_protocol.md` 只是综合和声明边界参考，不授权新增 runtime module、新 loss、graph learning、autonomous generation claim 或 repair deployment。 |
| 把 workflow usability 代理指标当成 QGIS 执行证明 | v2 脚本 (`scripts/evaluate_workflow_usability.py`) 只使用严格规则检查：task-critical coverage、harmful/missing tokens、QGIS mapping coverage、基础顺序/长度/冗余 sanity。即使 Top-1 可用率 56%、Top-3 可用率 100%，也不运行 QGIS、不推断语义等价、不验证参数，不能证明该 workflow 一定能生成正确地图。Usable != correct。 |
| 把 Phase 1 V4-QG 规则 rerank 当成 workflow accuracy 已解决 | `scripts/run_v4_qg_planner.py` 在 retrieval pool 中存在规则可用候选时可以把它选出来，1,000 样本 selected Top1 rule-usability 达到 1.0000。这个结果是 selector/usability 结果，不是 exact-match accuracy，不是 multi-reference correctness，不是参数 grounding，也不是真实 QGIS 执行。对外应表述为“candidate-pool/rerank 能在当前规则下把可用链捞出来”，不能表述为 autonomous workflow generation solved。 |
| 对比新旧长度指标时忽略 token 定义 | 质量门禁长度统计只计 content L3 tokens，排除 `<START>/<END>` id。新生成的 quality-gate artifact global median 为 7、mean 为 8.5，而旧 `outputs/task_type_length_stats.json` 数值更大。对比 early-EOS 或 length-ratio 诊断时必须说明统计定义和数据范围已经改变。 |
| 把缺少显式 multi-reference 标注理解成 workflow 只有单解 | Multi-reference evaluator 在 369 条持久化预测记录中没有找到 alternate exact-task references，但这只是当前标注覆盖事实，不证明 GIS 任务真的只有一个有效工作流。它说明：若没有人工 curated multi-reference labels 或受治理的 equivalence classes，当前 artifact 无法量化广义语义多解恢复。 |
| 把 MRV auto-verified candidates 当成训练标签 | `scripts/evaluate_multiref_validation.py` 只是 candidate-validation 和人工审查导出工具。QGIS landing 解耦后，100 variant smoke run 得到 19 个 workflow-semantic registry candidates，但这些仍不是训练标签。除非人工审查确认低 false-equivalence 风险，且 registry 有足够 reviewed `verified_equivalent` 条目，否则不要启动 multi-reference training。 |
| 把 QGIS-chain gate 失败解释成语义无效 | MRV pipeline 现在已经拆开 workflow-semantic validation 和 downstream QGIS landing。`qgis_chain_unusable` 和低 QGIS mapping 是辅助 transferability failure，不是 GEE workflow variant 语义无效的直接证据。 |
| 把 500-variant expansion 的原始 auto candidates 当成 registry labels | Auto `verified_equivalent_candidate` 行本身仍不是训练标签。后续只能使用已经晋升的 v2 registry/KB：`outputs_v2/v4_qg_multiref_validation/verified_multi_reference_registry_v2.json` 和 `verified_equivalence_kb_v2.*`。 |
| 直接把 AI-assisted review CSV 当训练集 | Review CSV 是 provenance / audit evidence。训练消融必须读取去重后的 v2 registry/KB；其中只有用户确认的 `equivalent` 行会进入候选训练标签，`uncertain` / `not_equivalent` 明确排除。 |

## 验证记录

命令均在 `E:\02_projects\03_PythonProject\Operator-recommend-system\Algorithm_classification\system_redesign` 下执行。

| 命令 | 最近结果 |
| --- | --- |
| 根目录追踪文档和 Claude memory 读取核对（2026-06-24） | 已重新读取 `task_plan.md`、`progress.md`、`findings.md`，以及外部 Claude memory 目录 `C:\Users\qiaoyun\.claude\projects\...\memory` 下的项目记忆。当前长期事实来源应以根目录追踪文件加 `docs/PROJECT_CONTEXT*` 为准；旧 `MEMORY.md` 中被 2026-06-09 git/cleanup 和后续 QGIS/矢量规划更新覆盖的架构段落只作为历史背景。 |
| 对关键 Phase 9 / QGIS vector 产物执行 `Measure-Object -Line`（2026-06-24） | 核验行数：`qgis_chain_dataset_v2_enriched_v3.jsonl` 2,319；`canonical_vector_planning_dataset.jsonl` 2,319；`canonical_vector_clean_sft_seed.jsonl` 685；`vector_training_samples_UNIFIED.jsonl` 10,768；`API_trace_to_L3_TRAINING_FINAL.jsonl` 6,031。`_final_merge.py` 解释了“约 16,800”合并候选数来自 6,031 + 10,768 = 16,799。 |
| `Import-Csv outputs_v2\diagnostics\open_landing_eval\open_landing_results.csv \| Group-Object grade` 和 `Group-Object modality,grade`（2026-06-24） | 当前本地 open landing CSV 仍为 80 条已分级任务：A=18、B=33、C=29。按模态：vector A=13/B=17/C=10，raster A=2/B=10/C=13，mixed A=3/B=6/C=6。 |
| 脱敏后对根目录追踪文档、`run_process.bat`、`scripts/*.py` 和 `src/gis_recommend/**/*.py` 做窄范围 key 扫描（2026-06-24） | 核心文件中没有真实 `sk-...` 明文 key。`src` 中剩余命中是普通英文 `Task-...` 造成的误报。此前广范围扫描发现 `.codegraph/codegraph.db` 这种本地生成缓存可能含历史/爬虫字符串索引，应继续排除在共享项目产物之外。 |
| 用户报告的 open landing 对比：baseline vs `+op_match` vs `+sem tags` | Unique chains 1 → 16 → 33；top-3 concentration 100% → 31%；modality 0% → 100% → 84%。`+sem tags` 已达到 diversity 目标（>20 unique chains），接近 concentration 目标（<25%），下一步需把 facts 文本索引合回 enriched v3 以恢复 modality >90%。 |
| `Import-Csv outputs_v2\diagnostics\open_landing_eval\open_landing_results.csv \| Group-Object grade` 和 Python CSV 读取（2026-06-06） | 当前本地开放式 QGIS landing 审核文件为 80 条：A=18、B=33、C=29。按模态：vector A=13/B=17/C=10，raster A=2/B=10/C=13，mixed A=3/B=6/C=6。 |
| `Import-Csv outputs_v2\diagnostics\open_landing_eval\open_landing_results.csv \| Group-Object top1_ops` 和 Python CSV 读取（2026-06-06） | 当前本地模板集中度：14 条为 `gdal:warpreproject -> native:reprojectlayer -> gdal:cliprasterbymasklayer`，7 条为 `native:reprojectlayer -> native:buffer -> native:clip`，5 条为 `native:reprojectlayer -> native:buffer -> gdal:cliprasterbymasklayer -> gdal:warpreproject`。 |
| 对 `outputs_v2/qgis_chain_dataset*.jsonl`、`qgis_vector_chain*.jsonl`、preference pairs、reranker reports 和 open landing CSV 做只读 QGIS 数据审计（2026-06-06） | `qgis_chain_dataset.jsonl`：3,053 行 / 972 条唯一链 / 55.3% 行有 L3 bridge / 73.6% 有 semantic tags。`qgis_chain_dataset_v2_enriched_v3.jsonl`：2,319 条唯一链 / 97.3% 行有 facts 文本 / 78.6% 有 semantic tags / 无 L3 bridge。`qgis_vector_chain_candidates.jsonl`：957 条 vector 或 mixed 链 / 19.0% 行有 L3 bridge / 91.1% 有 semantic tags。`qgis_vector_preference_pairs_clean.jsonl`：591 条偏好对，负样本主要是 `generic_template`、`modality_mismatch` 和 `missing_step`。 |
| PowerShell JSONL 核验 `outputs_v2\canonical_vector_planning_dataset.jsonl`（2026-06-06） | 文件存在，样例行包含 `task_text`、`modality`、`qgis_ops`、`planning_steps`、`l3_steps`、`has_full_l3`、`required_step_families`、`source`、`source_file` 和 `confidence`。计数：total 2,319；task_text 2,319；modality 为 vector 1,598 / raster 456 / mixed 265；full-L3 总数 1,046；full-L3 按模态为 vector 733 / raster 198 / mixed 115。Required-step family 共 20 类，最高频为 `crs_transform` 596、`buffer_analysis` 519、`spatial_overlay` 423、`attribute_filter` 412、`geometry_repair` 401、`spatial_clip` 391。 |
| PowerShell JSONL 训练质量审计 `outputs_v2\canonical_vector_planning_dataset.jsonl`（2026-06-06） | 必需字段缺失 0；`qgis_ops`/`planning_steps`/`l3_steps` 长度不一致 0；唯一 QGIS chain 2,319；任务文本 <80 字符 59 行；`required_step_families` 为空 463 行；operator step 总数 21,290，其中 `other`/空 L3 为 4,349（20.4%）。非空 L3 step 16,941；非法当前词表 L3 step 163 个，全部是 `L3_02_05_04`，涉及 140 行。纯矢量 full-L3 733 行；过滤非法 L3、短文本、空 required families、链长 >15、非 core provider 后，即时 clean SFT seed 为 610 行，覆盖 19 类 required-step families。 |
| PowerShell JSONL 核验 `outputs_v2\canonical_vector_clean_sft_seed.jsonl` overlay remap 后（2026-06-06） | 结构检查通过：685 行，全部 vector，`has_full_l3=false` 计数 0，必需字段缺失/空值 0（但 `required_step_families` 为空 36 行），长度不一致 0，operator step 3,190，`other` step 0，空 L3 0，当前词表非法 L3 0，`L3_02_05_04` 行 0，链长 min/median/p90/max 为 2/4/9/15，task text 长度 min/median/max 为 299/300/300，重复 task text groups 0，唯一 QGIS chains 685，唯一 L3 chains 619。本地 L3 计数：`L3_02_02_06` 219、`L3_02_02_01` 110、`L3_02_02_02` 37、`L3_02_02_04` 73、`L3_02_02_05` 5。排除 raster clip operator 后，overlay/centroid remap 检查失败数为 0。 |
| JSONL 核验 `configs\unseen_vector_prompts.jsonl`（2026-06-07） | 70 行，modality 计数为 vector=61 / mixed=6 / raster=3，重复 id 0，空 task 0，空 expected-family list 0，44 个唯一 expected families。与 `outputs_v2\canonical_vector_clean_sft_seed.jsonl` task text 的 exact 和 substring overlap 均为 0。 |
| `python -m py_compile scripts\evaluate_vector_generalization.py`（2026-06-07） | OK。这里只做静态语法检查；完整模型评测应在服务器上运行 `python scripts/evaluate_vector_generalization.py`，因为需要加载 DPO/SFT checkpoint 并对 70 条 prompt 解码。 |
| 服务器：`python scripts/evaluate_vector_generalization.py`（2026-06-07） | 写出 `outputs_v2/diagnostics/vector_generalization.json`。Vector prompts（61 条，measurable=48）：DPO measurable recall 2.1% vs SFT 25.7%，strict/all 1.6% vs 20.2%，raster-ish token rate 94.8% vs 35.6%，vector token rate 1.4% vs 53.3%，mean length 5.0 vs 4.1。Mixed prompts（6 条）：measurable recall 都是 20.0%，SFT vector token rate +15.3pp。Raster controls（3 条）：vector token rate 保持 0.0%，raster-ish token rate 提升到 88.6%。Overlay recall：intersection 0/4，union 1/1，difference 0/3。 |
| 服务器：QGIS-vector 过采样 warmstart 训练与泛化评测（2026-06-07） | 从 `step8_quality_gate_qgis_vector_oversampled` 重建 `outputs_v2/transition_allowed_next.json`：65,748 条 train workflow、60 states、607,006 transitions、invalid 0。DPO v2 checkpoint 扩 47->48 task types 后，训练 `outputs_v2/transformer_checkpoints_v4_6_quality_gate_qgis_vector_oversampled_warmstart/` 5 个 AR-SS epoch。Best checkpoint 为 epoch 1，validation composite 0.5895；test AR SetF1 0.540、LCS 0.397、earlyEOS 11.3%、PPL 17.7。`outputs_v2/diagnostics/vector_generalization_oversampled.json`：vector measurable recall DPO 3.8% vs SFT 27.8%，strict/all 3.0% vs 21.9%，vector token rate 1.5% vs 57.6%，raster-ish token rate 92.8% vs 34.7%；raster controls 的 vector token rate 仍为 0.0%；overlay intersection/union/difference 仍为 0。 |
| 服务器：`python scripts/evaluate_sft_vector_impact.py --sft-checkpoint ..._oversampled_warmstart/best_model.pth ... --report-path outputs_v2/diagnostics/sft_vector_impact_oversampled.json`（2026-06-07） | SFT 正确加载过采样 checkpoint、48-task 过采样 vocab/stats；DPO v2 加载 47-task quality-gate vocab/stats；两者都读取 60-state transition matrix。GEE test：DPO 0.4% strict-vector rate / avg len 5.9，SFT 2.4% / avg len 6.8。QGIS seed：DPO 1.7% / avg len 4.8，SFT 57.2% / avg len 6.8。Delta：GEE +2.0pp，QGIS +55.5pp。 |
| `python -m py_compile scripts\evaluate_sft_vector_impact.py scripts\evaluate_vector_generalization.py`（2026-06-07） | OK。`evaluate_sft_vector_impact.py` 增加 CLI 覆盖后，两个矢量评测脚本都能通过参数指定过采样 SFT checkpoint/vocab/length-stats，不再需要改源码。 |
| Python JSON 核验 `outputs_v2\pipeline\step8_qgis_vector_sft\*`（2026-06-06） | 包文件齐全。Manifest 记录 685 条样本、train/val/test 为 548/68/69、token vocab 为 `v2_94_l3`、格式为 `step8_compatible`。Labeled workflows 总数 685；split index 唯一且精确覆盖 0-684；0 个 token id 越出 0-93；缺失 task metadata 为 0；source 全部为 `qgis_vector_canonical`；task vocabulary 为 `"Vector Analysis": 0`；L3 序列长度 min/avg/max 为 2/4.657/15。 |
| Python JSON 核验 `outputs_v2\pipeline\step8_quality_gate_qgis_vector\*`（2026-06-06） | 合并包文件齐全。Manifest 与数据一致：77,569 条 workflow；split 为 train/val/test 62,180/7,694/7,695，唯一且精确覆盖 0-77,568；`task_type_to_id["Vector Analysis"] = 47`；`task_type_length_stats.json` 覆盖 48 个 task type，其中 Vector Analysis 的 median/p10/p90 长度为 4/2/9。QGIS 行为尾部连续 685 行，索引 76,884-77,568，全部在 train。普通 token id 没有越出 0-93；`-3`/`-4` negative specials 继承自原 76,884 条 GEE quality-gate 行。跨 split content L3 sequence overlap 为 0。QGIS L3 序列 619 条唯一，45 个重复组 / 111 行，来源于 685 seed 本身。 |
| `python scripts\train_v4_quality_gate.py --data outputs_v2\pipeline\step8_qgis_vector_sft\labeled_workflows_l3_v4_qgis_vector.json --splits outputs_v2\pipeline\step8_qgis_vector_sft\dataset_splits_qgis_vector.json --task-vocab outputs_v2\pipeline\step8_qgis_vector_sft\task_type_vocabulary_qgis_vector.json --checkpoint-dir outputs_v2\transformer_checkpoints_qgis_vector_sft_smoke --dry-run` | V4.2 训练入口 dry-run 通过：workflows_total 685，train/val/test 为 548/68/69，num_task_types 1，vocab_size 98，device cpu，未启动真实训练。 |
| `python scripts\train_v4_6_quality_gate.py --data outputs_v2\pipeline\step8_qgis_vector_sft\labeled_workflows_l3_v4_qgis_vector.json --splits outputs_v2\pipeline\step8_qgis_vector_sft\dataset_splits_qgis_vector.json --task-vocab outputs_v2\pipeline\step8_qgis_vector_sft\task_type_vocabulary_qgis_vector.json --checkpoint-dir outputs_v2\transformer_checkpoints_qgis_vector_sft_v4_6_smoke --dry-run` | V4.6 训练入口 dry-run 通过：workflows_total 685，train/val/test 为 548/68/69，num_task_types 1，vocab_size 98，device cpu，未启动真实训练。注意：length_bucket_training 仍使用默认 quality-gate length stats 路径，QGIS-only 或混训前仍需生成/指定 QGIS/mixed length stats。 |
| `python scripts\smoke_v4_quality_gate_training_entry.py --data outputs_v2\pipeline\step8_qgis_vector_sft\labeled_workflows_l3_v4_qgis_vector.json --splits outputs_v2\pipeline\step8_qgis_vector_sft\dataset_splits_qgis_vector.json --task-vocab outputs_v2\pipeline\step8_qgis_vector_sft\task_type_vocabulary_qgis_vector.json --batch-size 2 --max-samples 2 --split train` | V4 training-entry smoke 在 CPU 上通过：加载 94 个 L3 embeddings，选取 2 条 train 样本，logits shape `[2, 100, 98]`，length prediction shape `[2, 1]`，contrastive representation shape `[2, 128]`，只使用本地 BERT，未写 checkpoint。 |
| `python scripts\train_v4_6_quality_gate.py --data outputs_v2\pipeline\step8_quality_gate_qgis_vector\labeled_workflows_l3_v4_quality_gate_qgis_vector.json --splits outputs_v2\pipeline\step8_quality_gate_qgis_vector\dataset_splits_v4_quality_gate_qgis_vector.json --task-vocab outputs_v2\pipeline\step8_quality_gate_qgis_vector\task_type_vocabulary_v4_quality_gate_qgis_vector.json --length-stats outputs_v2\pipeline\step8_quality_gate_qgis_vector\task_type_length_stats.json --checkpoint-dir outputs_v2\transformer_checkpoints_v4_6_quality_gate_qgis_vector_smoke --dry-run` | V4.6 合并包 dry-run 通过：workflows_total 77,569，train/val/test 为 62,180/7,694/7,695，num_task_types 48，vocab_size 98，device cpu，未启动真实训练。 |
| 服务器：`python scripts/evaluate_sft_vector_impact.py`（2026-06-07，显式 length-stats 路径修正后） | SFT 加载 `outputs_v2/pipeline/step8_quality_gate_qgis_vector/task_type_length_stats.json`，日志显示 48 task types；DPO v2 加载 `outputs_v2/pipeline/step8_quality_gate/task_type_length_stats.json`，日志显示 47 task types。Strict vector tokens 为 14，因为 `L3_02_05_04` 不在 94-L3 词表。GEE test：DPO 0.4% strict-vector rate / avg len 5.9，SFT 2.0% / avg len 6.3。QGIS seed：DPO 1.7% / avg len 5.0，SFT 53.7% / avg len 6.6。Delta：GEE +1.6pp，QGIS +52.0pp。Report：`outputs_v2/diagnostics/sft_vector_impact.json`。 |
| 对合并包中两条真实 QGIS 行做 CPU forward probe（2026-06-06） | 构建 48-task V4 模型，使用本地 BERT 和 L3 embeddings，输入两条 `source == qgis_vector_canonical` 的样本；batch task type id 为 `[47, 47]`，logits shape `[2, 100, 98]`，length prediction shape `[2, 1]`，contrastive representation shape `[2, 128]`。 |
| 将 `outputs_v2\transformer_checkpoints_v4_6_preference_dpo_v2_quality_cycle_fixed\best_preference_model.pth` warmstart 到 48-task 模型的兼容性探针（2026-06-06） | 按预期失败，错误为 `size mismatch for task_type_embedding.weight`：checkpoint 形状 `[47, 256]`，当前模型形状 `[48, 256]`。现有 quality-gate 和 DPO v2 checkpoint 的 task embedding/classifier 都是 47-task 形状。 |
| `python scripts\train_v4_6_quality_gate.py ... --dry-run --lr 1e-5` 读取合并包（2026-06-06） | 参数解析失败：`unrecognized arguments: --lr 1e-5`；当前 launcher 没有 learning-rate CLI override。 |
| `python scripts\compute_task_type_length_stats.py` | 从 76,884 条 quality-gated workflows 生成 `outputs_v2\pipeline\step8_quality_gate\task_type_length_stats.json`。Content-token 全局统计：median 7、mean 8.5、p90 16；47 个 task types。 |
| `python -m unittest tests.test_v4_qg_planner tests.test_task_type_length_stats -v` | 10 tests OK；覆盖 V4-QG planner 默认路径、显式 length stats 加载、candidate rerank 基础、content-token 长度统计生成和 length-stats 路径优先级。 |
| Step8 + V4.6 主线只读审计（2026-05-21） | 确认 `gis-evaluate = gis_recommend.evaluation.runner:main`；runner 读取 `V4_LABELED_WORKFLOWS_PATH`、`build_test_set()`、`run_l3_inference()`，reranker / repair / QGIS / executable diagnostics 均为可选。真实 Step8 为 107,399 条 workflow，split 为 85,919 / 10,739 / 10,741。 |
| `SemanticMetricsCalculator._strip_special([-3,1,2,-4,94,95,96,97,350,351,352,353])` | 2026-05-21 contract 修复后，主线 `v2_94_l3` 下返回 `[1,2,350,351,352,353]`；`legacy_350_l3_token_profile()` 只剥离 `350..353`。完美预测对 `[-3,54,50,40,-4]` 的 toy case 现在为 LCS 1.0 / token accuracy 1.0 / SeqEM true。 |
| `python -m unittest tests.test_mainline_run_contract -v` | 4 tests OK；覆盖 v2 token 剥离、legacy profile 兼容、run-contract 报告 metadata、`CandidateVerifier` v2 I/O metadata 默认行为。 |
| `python -m unittest tests.test_mainline_run_contract tests.test_reranker_evaluate_system tests.test_two_stage_reranker tests.test_executable_ratio -v` | 50 tests OK；覆盖主线契约、report-only repair、reranker decision/diagnostic 边界、executable diagnostics。 |
| `python -m unittest tests.test_v4_qg_planner tests.test_v5_empirical_experiment_scripts tests.test_retrieval_planning_stages -v` | 33 tests OK；覆盖 V4-QG/V5/retrieval-stage 报告新增 non-mainline lineage metadata 后的脚本回归。 |
| `python -m compileall src\gis_recommend\evaluation\run_contract.py src\gis_recommend\evaluation\semantic_metrics.py src\gis_recommend\evaluation\report.py src\gis_recommend\evaluation\runner.py src\gis_recommend\reranking\reranker_verifier.py scripts\run_v4_qg_planner.py scripts\evaluate_v5_hybrid_planner.py scripts\evaluate_retrieval_planning_stages.py tests\test_mainline_run_contract.py` | OK。 |
| `python -m unittest tests.test_mainline_run_contract tests.test_qgis_candidate_generator_logging tests.test_v4_qg_evaluation_report -v` | 11 tests OK；覆盖 generator 的 run-contract I/O authority、`qgis_score_components` 进入 decision trace，以及 V4-QG research / non-mainline 报告线。 |
| `python -m unittest tests.test_v2_defaults tests.test_mainline_run_contract tests.test_build_ontology_kg_paths tests.test_import_l3_mappings -v` | 21 tests OK；覆盖 v2 默认配置、主线契约、安全 KG 构建 CLI 行为、无隐式 `--clear`、v2 hierarchy schema 兼容、v2-only mapping 默认，以及独立 L3 mapping 导入参数。 |
| `python -m compileall scripts\build_ontology_kg.py scripts\import_l3_mappings.py tests\test_build_ontology_kg_paths.py tests\test_import_l3_mappings.py` | OK。 |
| `python -m unittest tests.test_v2_defaults tests.test_mainline_run_contract tests.test_mainline_shadow_phase tests.test_reranker_evaluate_system tests.test_executable_ratio tests.test_v4_qg_evaluation_report -v` | 49 tests OK；覆盖 v2 默认配置、contract/report 字段、candidate pool trace、evidence bundle 缺失语义、train-only retrieval shadow、report-only repair、reranker/executable diagnostics 和 V4-QG non-mainline 报告。 |
| `python -m compileall src\gis_recommend\evaluation\run_contract.py src\gis_recommend\evaluation\report.py src\gis_recommend\evaluation\runner.py src\gis_recommend\evaluation\shadow_phase.py tests\test_mainline_shadow_phase.py` | OK。 |
| `python -m unittest tests.test_mainline_run_contract tests.test_reranker_evaluate_system tests.test_two_stage_reranker tests.test_executable_ratio tests.test_v4_qg_planner tests.test_v4_qg_evaluation_report tests.test_qgis_candidate_generator_logging tests.test_v2_defaults -v` | 69 tests OK；覆盖在把 generator / report / QGIS evaluation 接入 run contract 后，相邻 reranker / executable / QGIS generator / 默认路径行为不回归。 |
| `python -m compileall src\gis_recommend\operators\qgis_candidate_generator.py src\gis_recommend\evaluation\runner.py src\gis_recommend\evaluation\reranker_pipeline.py src\gis_recommend\evaluation\report.py scripts\evaluate_v4_quality_gate.py src\gis_recommend\config\transformer_config.py tests\test_mainline_run_contract.py tests\test_qgis_candidate_generator_logging.py tests\test_v4_qg_evaluation_report.py` | OK；完成 post-audit contract closure 后编译检查通过。 |
| `python -m unittest tests.test_evidence_aware_ranking tests.test_mainline_shadow_phase -v` | 207 tests OK；覆盖新离线 ranking 测试和既有 shadow/report runtime-contract 回归。 |
| `python scripts\evaluate_evidence_aware_ranking.py --report outputs_v2\evaluation_reports\empirical_v2_smoke_artifact.json --output-dir outputs_v2\diagnostics\evidence_aware_ranking` | 生成 `evidence_aware_ranking.json/.md`。120 条 empirical 记录上：candidate absence 0.0，selection diff 0.7333，legacy mean LCS/TokenAcc/SetF1 = 0.3957/0.1941/0.5666，evidence-aware = 0.4412/0.1696/0.6361，oracle best-in-pool = 0.5862/0.3154/0.7654。契约记录为 offline-only，不改主线输出或指标。 |
| `python -m unittest tests.test_reranker_evaluate_system -v` | 13 tests OK；覆盖 report-only repair 行为，并有测试明确断言 reranker scoring/pruning 忽略 validation 与 compatibility outputs。 |
| `python scripts\analyze_length_bucket_distribution.py` | 默认读取 quality-gate stats artifact。Bucket summary：short 5 个 task types / 562 samples，medium 35 / 47,848，long 7 / 28,474，very_long 0。 |
| `python scripts\run_v4_qg_planner.py --eval-samples 1 --output-dir outputs_v2\tmp_planner_smoke_check` | 2026-05-19 planner smoke 修复后通过。本地缺少 Set Predictor checkpoint，因此使用 train-frequency set prior fallback。Selected Top1 usable 1.0000；retrieval Top1 usable 1.0000；Pool Top5 any usable 1.0000；forbidden-pattern scan pass。 |
| `python -m unittest tests.test_v4_qg_planner tests.test_mrv_registry_builder -v` | 周报/planner smoke 审查后 12 tests OK。 |
| `python -B -c "import ast, pathlib; p=pathlib.Path('scripts/run_v4_qg_planner.py'); ast.parse(p.read_text(encoding='utf-8')); print('syntax ok')"` | 语法检查 OK，且不写入 `__pycache__`。 |
| `python -m unittest tests.test_v4_6_training_stability -v` | 2 tests OK；覆盖 dynamic-min-length END 禁止下 CE logits 与 sampling logits 的拆分 |
| `python -m unittest tests.test_v4_quality_gate_training_launcher tests.test_v4_training_entry_smoke tests.test_v4_6_training_stability -v` | 9 tests OK |
| `python -m compileall src\gis_recommend\training\train_v4_6.py tests\test_v4_6_training_stability.py` | OK |
| `python -m unittest tests.test_v4_qg_planner -v` | 7 tests OK；覆盖 V4-QG planner 默认路径、soft transition prior、set coverage、candidate-pool dedupe、usability-first rerank 和 forbidden-pattern scan |
| `python -m compileall scripts\run_v4_qg_planner.py tests\test_v4_qg_planner.py` | OK |
| `python -m unittest tests.test_v4_qg_planner.V4QGPlannerTests.test_default_paths_are_quality_gate_scoped -v` | 修复前因 planner 默认仍指向 `set_predictor_checkpoints_v3_quality_gate` 而失败；V4.6 Set Predictor 默认路径对齐后通过 |
| `python -m compileall scripts\run_v4_qg_planner.py src\gis_recommend\config\transformer_config.py tests\test_v4_qg_planner.py` | V4.6 Set Predictor 路径对齐后 OK |
| `python scripts\run_v4_qg_planner.py --eval-samples 200 --output-dir outputs_v2\v4_qg_planner_reports\phase1_candidate_rerank` | 只做 evaluation/rerank。本地缺少 Set Predictor checkpoint，因此使用 train-frequency set prior fallback。Selected Top1 rule-usable 1.0000，retrieval Top1 为 0.6350；Pool Top5 any usable 1.0000；forbidden-pattern scan pass。 |
| `python scripts\run_v4_qg_planner.py --eval-samples 1000 --output-dir outputs_v2\v4_qg_planner_reports\phase1_candidate_rerank_1000` | 稳定性检查。本地缺少 Set Predictor checkpoint，因此使用 train-frequency set prior fallback。Selected Top1 rule-usable 1.0000，retrieval Top1 为 0.6330；Pool Top5 any usable 1.0000；mean selected usability 0.8449；mean QGIS mapping 0.8082；forbidden-pattern scan pass。 |
| `python scripts\build_bounded_ontology_inventory.py --output-dir outputs_v2\v5_final_reports\bounded_ontology_inventory` | 已写出 bounded ontology artifacts：3,800 个 operator-pair rows；exact 13、execution-sensitive 98、partial 691、ambiguous 2,989、composite 4、unsupported 5；未实现 semantic retrieval，未改 runtime |
| `python -m unittest tests.test_bounded_ontology_inventory -v` | 7 tests OK |
| `python -m compileall -q scripts\build_bounded_ontology_inventory.py tests\test_bounded_ontology_inventory.py` | OK |
| Bounded ontology artifact sanity check | 必需 JSON/CSV/Markdown artifact 均存在；runtime contract 显示 `semantic_retrieval_implemented=False` 和 `training_run=False`；forbidden-pattern scan 结果为 `pass`，0 matches |
| `python -m unittest tests.test_pipeline_provenance tests.test_v2_defaults tests.test_build_ontology_kg_paths tests.test_qgis_candidate_generator_logging -v` | 18 tests OK |
| `python -m compileall src/gis_recommend/data/pipeline_provenance.py src/gis_recommend/data/pipeline_runner.py src/gis_recommend/data/step6_label_with_l3.py src/gis_recommend/data/step7_prepare_v4_data.py src/gis_recommend/data/step8_clean_v4_data.py scripts/audit_pipeline_outputs.py tests/test_pipeline_provenance.py` | OK |
| `python -m unittest tests.test_dataset_splits tests.test_evaluate_system_sampling tests.test_pipeline_provenance tests.test_v2_defaults tests.test_build_ontology_kg_paths tests.test_qgis_candidate_generator_logging -v` | 29 tests OK |
| `python -m compileall src/gis_recommend/training/splits.py src/gis_recommend/training/train_v4_2.py src/gis_recommend/training/train_v4_6.py src/gis_recommend/training/train_set_predictor_v3.py src/gis_recommend/evaluation/sampling.py tests/test_dataset_splits.py tests/test_evaluate_system_sampling.py` | OK |
| `python scripts/audit_training_data_quality.py --data outputs_v2\pipeline\step8\labeled_workflows_l3_v4_cleaned.json --splits outputs_v2\dataset_splits_v4.json --id-mappings outputs_v2\id_mappings_v2.json --hierarchy outputs_v2\classification_hierarchy_v2.csv --out-dir outputs_v2\pipeline\audit` | 写出训练数据质量审计；告警包括 inactive L3、L3 分布倾斜、task type 稀疏、val/test-only task、跨 split 序列重复、低置信 mapping tokens |
| `python -m unittest tests.test_training_data_quality tests.test_dataset_splits tests.test_evaluate_system_sampling tests.test_pipeline_provenance tests.test_v2_defaults tests.test_build_ontology_kg_paths tests.test_qgis_candidate_generator_logging -v` | 31 tests OK |
| `python -m compileall src/gis_recommend/data/training_data_quality.py scripts/audit_training_data_quality.py tests/test_training_data_quality.py` | OK |
| 当前 Step8 与 v2 mapping / 官方 GEE operator 对齐 smoke | 306 个唯一 Step8 operator；306/306 可大小写不敏感匹配 v2 GEE metadata；295/306 可大小写不敏感匹配爬取的官方 `gee_operators.json` name；11 个已映射 operator 不是官方 name 的直接命中，需要 alias/canonical review |
| `python scripts/build_v4_quality_gate_candidate.py --data outputs_v2\pipeline\step8\labeled_workflows_l3_v4_cleaned.json --id-mappings outputs_v2\id_mappings_v2.json --out-dir outputs_v2\pipeline\step8_quality_gate --min-task-count 10` | 写出候选数据、quarantine、分组 split、task vocab、质量报告和 GEE alias 审计；summary：input 107,399，candidate 76,884，quarantine 30,515，sparse merged 116，cross-split duplicate sequence hashes 0 |
| `python scripts/audit_training_data_quality.py --data outputs_v2\pipeline\step8_quality_gate\labeled_workflows_l3_v4_quality_gate.json --splits outputs_v2\pipeline\step8_quality_gate\dataset_splits_v4_quality_gate.json --id-mappings outputs_v2\id_mappings_v2.json --hierarchy outputs_v2\classification_hierarchy_v2.csv --out-dir outputs_v2\pipeline\step8_quality_gate\audit` | 候选集审计仅剩 inactive L3、L3 分布倾斜、低置信 mapping tokens；task types <10 = 0，val/test-only task = 0，跨 split 重复 L3 序列 = 0 |
| 质量门禁 split 校验 smoke | 候选 split 覆盖 76,884/76,884 条 workflow，唯一索引 76,884，越界 0，重复 0 |
| 质量门禁 GEE alias 审计 | 候选集 150 个唯一 operator；150/150 可大小写不敏感匹配 v2 GEE metadata；140/150 可大小写不敏感匹配爬取的官方 name；10 个 unresolved official-name operator 覆盖 20,593 tokens（3.13%） |
| `python -m unittest tests.test_training_data_quality_gate tests.test_training_data_quality tests.test_dataset_splits tests.test_evaluate_system_sampling tests.test_pipeline_provenance tests.test_v2_defaults tests.test_build_ontology_kg_paths tests.test_qgis_candidate_generator_logging -v` | 36 tests OK |
| `python -m compileall src\gis_recommend\data\quality_gate.py scripts\build_v4_quality_gate_candidate.py tests\test_training_data_quality_gate.py` | OK |
| `python -m unittest tests.test_v4_training_entry_smoke -v` | 3 tests OK，已按 red-green cycle 验证 quality-gate 默认路径、不写 checkpoint 的 smoke 行为、本地 BERT 加载参数 |
| `python -m unittest tests.test_v4_training_entry_smoke tests.test_training_data_quality_gate tests.test_training_data_quality tests.test_dataset_splits tests.test_evaluate_system_sampling tests.test_pipeline_provenance tests.test_v2_defaults tests.test_build_ontology_kg_paths tests.test_qgis_candidate_generator_logging -v` | 39 tests OK |
| `python -m compileall src\gis_recommend\models\transformer_model_v4.py scripts\smoke_v4_quality_gate_training_entry.py tests\test_v4_training_entry_smoke.py` | OK |
| `python scripts\smoke_v4_quality_gate_training_entry.py --batch-size 2 --max-samples 2 --split train` | 真实 quality-gate 训练入口 smoke 在 CPU 上通过，本地 BERT 缓存可用；加载 76,884 条 workflow、47 个 task type、94 个 v2 embedding token，logits shape `[2, 100, 98]`，未写 checkpoint |
| `python -m unittest tests.test_v4_quality_gate_training_launcher tests.test_v4_training_entry_smoke -v` | 6 tests OK |
| `python -m compileall scripts\train_v4_quality_gate.py tests\test_v4_quality_gate_training_launcher.py` | OK |
| `python scripts\train_v4_quality_gate.py --dry-run` | 真实 quality-gate 训练 launcher 校验通过：76,884 条 workflow，split 61,495 / 7,694 / 7,695，47 个 task type，vocab 98，checkpoint dir 为 `outputs_v2\transformer_checkpoints_v4_2_quality_gate`；未创建 checkpoint 目录 |
| `python -m unittest tests.test_set_predictor_quality_gate_training_launcher tests.test_v4_quality_gate_training_launcher tests.test_v4_training_entry_smoke -v` | 10 tests OK |
| `python -m compileall scripts\train_set_predictor_quality_gate.py tests\test_set_predictor_quality_gate_training_launcher.py src\gis_recommend\models\set_predictor_v3.py` | OK |
| `python scripts\train_set_predictor_quality_gate.py --dry-run` | 真实 Set Predictor quality-gate launcher 校验通过：76,884 条 workflow，split 61,495 / 7,694 / 7,695，47 个 task type，47 个 train-active token，checkpoint dir 为 `outputs_v2\set_predictor_checkpoints_v3_quality_gate`，active token 文件为 `outputs_v2\set_predictor_active_tokens_quality_gate.json`；未创建 checkpoint 或 active-token 文件 |
| `python scripts\build_quality_gate_transition_matrix.py` | 生成 `outputs_v2\transition_allowed_next.json`：61,495 条 train workflow，48 个状态，587,479 条转移，越界转移 0 |
| `python -m unittest tests.test_quality_gate_transition_matrix tests.test_v4_quality_gate_training_launcher tests.test_set_predictor_quality_gate_training_launcher tests.test_v4_training_entry_smoke -v` | 14 tests OK |
| `python -m compileall scripts\build_quality_gate_transition_matrix.py scripts\train_v4_quality_gate.py tests\test_quality_gate_transition_matrix.py tests\test_v4_quality_gate_training_launcher.py` | OK |
| 真实 `outputs_v2/dataset_splits_v4.json` split 校验 | 107,399 个总索引，107,399 个唯一索引，越界 0，缺失 0 |
| `train_v4_2.load_or_create_splits` 训练 split smoke | 可加载已对齐 split 并构造 train/val/test 列表：85,919 / 10,739 / 10,741 |
| 评测采样 smoke | `build_test_set(..., max_samples=10)` 可从对齐后的 test split 读取 10 个样本，无 `IndexError` |
| `python scripts/audit_pipeline_outputs.py --outputs-dir outputs_v2` | 已写出 audit report；普通模式报告旧产物缺 provenance，严格模式之后报告 Step6/7/8 `missing_provenance` |
| `python scripts/audit_pipeline_outputs.py --outputs-dir outputs_v2 --require-provenance --fail-on-warning` | legacy gate 命令在 Phase 15C 下保持 report-only；当前旧产物仍报告 `step3:large_drop_from_previous` 和 `step6/7/8:missing_provenance` |
| `python -m unittest tests.test_v2_defaults tests.test_build_ontology_kg_paths -v` | 10 tests OK |
| `python -m unittest tests.test_qgis_candidate_generator_logging -v` | 2 tests OK |
| `python -m compileall src/gis_recommend/operators/qgis_candidate_generator.py src/gis_recommend/operators/l3_to_platform_mapper.py tests/test_v2_defaults.py scripts/build_ontology_kg.py src/gis_recommend/config/transformer_config.py src/gis_recommend/data/__init__.py src/gis_recommend/inference/infer_l3_candidates_v4.py src/gis_recommend/evaluation/runner.py` | OK |
| QGIS 默认 smoke | `QGISCandidateGenerator`: 75 L3 / 438 mappings；`Write Vector Tiles_mbtiles` 保留；`Remove Duplicate Points` 落到修正后的 L3 |
| Platform mapper 默认 smoke | `L3ToPlatformMapper`: 75 L3 / 438 mappings；`Write Vector Tiles_mbtiles` 保留；`Remove Duplicate Points` 落到修正后的 L3 |
| Legacy override smoke | `GIS_OUTPUTS_DIR=outputs`、`GIS_VOCAB_SIZE=350` 时回到 `OUTPUT_DIR=outputs`、`VOCAB_SIZE=350`、`TOTAL_VOCAB_SIZE=354`、旧 id mappings/embeddings |
| Phase 15C.1 V5 语义边界审计 | 只读分析。源码定位确认的关键锚点：`train_v4_2.train_epoch` dispatch 到 `_train_step_autoregressive`，不是 `_train_step_ar`；v4.4 `_train_step_ar` 在 pre-A 是 dead path；v4.5 balanced sampler 通过 `_build_train_loader` runtime-active；v4.6 覆盖 `_train_step_autoregressive` 并按 `ar_token_acc` 选择 best checkpoint；inference constraint 位于 `L3SequenceInferencerV4._apply_constraints`；executable legality diagnostics 只是 reporting/evaluation-only |
| Phase 15C.3 runtime-boundary enforcement audit | 只读分析。已搜索 V5 governance object 名称和 reverse-edge 相关词。没有发现已实现的 `RuntimeProfile` / `CheckpointManifest` / `DatasetLineage` / `GradientProfile` / `MetricRecord` / `CompatibilityResult` / `DecodePolicy` 对象。修复前的 reverse-edge candidate 位于 `step8_clean_v4_data.validate_pipeline_provenance`、`audit_pipeline_outputs --fail-on-warning`、reranker validation scoring，以及可选 chain repair |
| `python -m compileall src\gis_recommend\models\transformer_model_v4.py src\gis_recommend\inference\infer_l3_candidates.py src\gis_recommend\evaluation\semantic_metrics.py src\gis_recommend\evaluation\evaluate_generation_detailed_v3.py src\gis_recommend\training\train_v3.py src\gis_recommend\training\train_v4_3_rl.py src\gis_recommend\knowledge_graph\train_graph_embeddings.py scripts\build_ontology_kg.py scripts\project_l3_embeddings_v2.py tests\test_reranker_evaluate_system.py tests\test_chain_repair.py` | OK |
| `python -m unittest tests.test_pipeline_provenance tests.test_reranker_evaluate_system tests.test_phase15c_runtime_contract tests.test_training_data_quality -v` | 26 tests OK |
| `python -m unittest tests.test_v4_training_entry_smoke tests.test_build_ontology_kg_paths tests.test_chain_repair -v` | 10 tests OK |
| `python -m unittest tests.test_v4_quality_gate_training_launcher tests.test_set_predictor_quality_gate_training_launcher tests.test_quality_gate_transition_matrix -v` | 11 tests OK |
| `python -m unittest tests.test_phase15c_runtime_contract tests.test_chain_repair tests.test_reranker_evaluate_system tests.test_pipeline_provenance -v` | 31 tests OK |
| `python -m unittest tests.test_two_stage_reranker -v` | 13 tests OK |
| `python -m unittest tests.test_v4_quality_gate_training_launcher tests.test_set_predictor_quality_gate_training_launcher tests.test_quality_gate_transition_matrix -v` | 11 tests OK |
| `python -m compileall src\gis_recommend\inference\infer_l3_candidates.py src\gis_recommend\inference\infer_task_conditioned_v3.py src\gis_recommend\inference\infer_l3_candidates_v4.py src\gis_recommend\models\set_predictor_v3.py src\gis_recommend\evaluation\evaluate_generation_detailed_v3.py src\gis_recommend\training\train_v3.py src\gis_recommend\training\train_v4_3.py src\gis_recommend\training\train_v4_4.py src\gis_recommend\training\train_v4_3_rl.py src\gis_recommend\data\pipeline_provenance.py src\gis_recommend\evidence tests\test_phase15c_runtime_contract.py tests\test_chain_repair.py` | OK |
| 通过 `python -` 对 `outputs_v2/pipeline/step8_quality_gate/labeled_workflows_l3_v4_quality_gate.json` 和 split JSON 执行只读实证统计 | 量化得到：76,884 条 workflow，47 个 active L3，Top10 token share 74.94%，explicit join proxy 0.39%，每个 task type 的 unique sequence 中位数 118，transition-mask test coverage 99.9575%，Markov-2 next-token accuracy 33.51%，弱 lexical NN LCS recall 0.607；当时还没有 active `outputs_v2` prediction report |
| 建立基础设施前的 `Get-ChildItem outputs_v2\evaluation_reports` 和 legacy `outputs\evaluation_reports` 检查 | 确认 `outputs/evaluation_reports` 下 legacy reports 是旧 350-L3 产物，不能作为当前 v2 性能证据；当前 v2 证据现在从 baseline-only empirical smoke artifact 开始 |
| `python -m unittest tests.test_empirical_evaluation tests.test_evaluate_system_sampling tests.test_reranker_evaluate_system -v` | 25 tests OK；覆盖 empirical artifact schema/diagnostics、deterministic retrieval ordering、sampling split checks，以及 report-only reranker/repair behavior |
| `python -m compileall src\gis_recommend\evaluation\empirical.py scripts\build_empirical_evaluation_artifact.py tests\test_empirical_evaluation.py` | OK |
| `python scripts\build_empirical_evaluation_artifact.py --samples 20 --retrieval-top-k 5 --canonicalization-limit 2000 --out outputs_v2\evaluation_reports\empirical_v2_smoke_artifact.json` | 写出 baseline-only empirical artifact 和 Markdown report；schema `gis_recommend.empirical_evaluation.v1`，20 samples，LCS 最佳 baseline 为 `lexical_retrieval` = 0.453342 |
| 通过 `python -` 检查 empirical smoke artifact 字段 | 确认 artifact 包含 `dataset_structure_audit`、`upper_bound_analysis`、`engineering_report.bottleneck_attribution`，以及 lexical/embedding/nearest/retrieval-rerank/retrieval-constrained/Markov2 的逐样本 predictions、beam candidates、decode traces、token probabilities、END timing、repetition stats、candidate pool diagnostics、retrieval diagnostics 和 reranker outputs |
| `python -m unittest tests.test_v5_final_entrypoints tests.test_v5_final_runtime tests.test_empirical_evaluation -v` | 16 tests OK；覆盖 V5_final runtime contract、entrypoint 和 empirical artifact 回归 |
| `python scripts\train_v5_final_minimal.py --dry-run` | 使用真实 quality-gate 默认路径完成校验且未写 checkpoint：76,884 workflows，split 61,495 / 7,694 / 7,695，vocab 98 |
| `python -m compileall src\gis_recommend\models\v5_final src\gis_recommend\evaluation\empirical.py scripts\train_v5_final_minimal.py scripts\infer_v5_final_minimal.py tests\test_v5_final_runtime.py tests\test_v5_final_entrypoints.py` | OK |
| `python -m unittest tests.test_phase15c_runtime_contract -v` | V5_final 修改后 8 tests OK |
| V5_final forbidden-edge source scan | 对新 V5 文件执行 `rg`，未发现 `strict=False`、`weights_only=False`、`gis_recommend.evidence` import、runtime governance object，loss 中也没有诊断项参与计算（仅有说明性注释） |
| `python -m unittest tests.test_v5_training_system tests.test_v5_final_runtime tests.test_v5_final_entrypoints tests.test_empirical_evaluation tests.test_phase15c_runtime_contract -v` | 31 tests OK；覆盖 V5 training system、runtime contract、entrypoint、empirical artifact 回归和 Phase 15C checkpoint/runtime 边界 |
| `python -m compileall src\gis_recommend\training\train_v5.py src\gis_recommend\models\v5_final scripts\train_v5.py scripts\train_v5_final_minimal.py scripts\infer_v5_final_minimal.py tests\test_v5_training_system.py tests\test_v5_final_runtime.py tests\test_v5_final_entrypoints.py` | OK |
| `python scripts\train_v5.py --dry-run --no-amp` | V5_final 完整训练引擎使用真实 quality-gate 路径完成 dry-run 校验且未写 checkpoint：76,884 workflows，split 61,495 / 7,694 / 7,695 |
| `python scripts\train_v5.py --dry-run --no-amp --subset-preset 1k` | 确定性 subset dry-run 使用真实 quality-gate 路径完成校验，`train_count=1000`；未创建 `outputs_v2\v5_final_checkpoints` 目录 |
| `python scripts\train_v5.py --subset-preset 1k --epochs 5 --checkpoint-dir outputs_v2\v5_final_reports\stage0\checkpoints --evaluation-report outputs_v2\v5_final_reports\stage0\evaluation_report.json --no-amp --seed 42 --beam-width 5` | Stage0 完成 5 epoch，写出 best/latest checkpoint、history、evaluation JSON/Markdown，stderr 为空；无 collapse alert |
| `python scripts\train_v5.py --subset-preset 10k --epochs 30 --patience 30 --batch-size 512 --checkpoint-dir outputs_v2\v5_final_reports\stage1\checkpoints --evaluation-report outputs_v2\v5_final_reports\stage1\evaluation_report.json --no-amp --seed 42 --beam-width 5` | Stage1 在 CPU 上完成 30 epoch，写出 best/latest checkpoint、history、evaluation JSON/Markdown，stderr 为空；无 collapse alert；best val loss 2.82443161 |
| `python scripts\build_empirical_evaluation_artifact.py --samples 50 --retrieval-top-k 5 --canonicalization-limit 2000 --out outputs_v2\v5_final_reports\stage1\baseline_empirical_50.json` | 写出 Stage1 的 50 样本 lexical/Markov baseline artifact；lexical LCS 0.443715，Markov2 LCS 0.37923 |
| `python scripts\train_v5.py --disable-pvm --subset-preset 10k --epochs 30 --patience 30 --batch-size 512 --checkpoint-dir outputs_v2\v5_final_reports\a1_no_pvm\checkpoints --evaluation-report outputs_v2\v5_final_reports\a1_no_pvm\evaluation_report.json --no-amp --seed 42 --beam-width 5` | A1 no-PVM 在服务器完成并已同步到本地；30 epoch，stderr 0，best val loss 3.07014528，对比产物写入 `outputs_v2\v5_final_reports\a1_no_pvm\comparison_vs_stage1.*` |
| `python scripts\evaluate_v5_beam_search.py --checkpoint outputs_v2\v5_final_reports\stage1\checkpoints\best_model.pt --output-dir outputs_v2\v5_final_reports\beam_search_eval --beam-widths 1 3 5 10 --eval-samples 50 --device cpu` | 不重训，复评 Stage1 checkpoint；raw-logprob beam summary 和 decode traces 写入 `outputs_v2\v5_final_reports\beam_search_eval\` |
| `python scripts\evaluate_v5_beam_search.py --checkpoint outputs_v2\v5_final_reports\stage1\checkpoints\best_model.pt --output-dir outputs_v2\v5_final_reports\beam_search_eval\length_norm_alpha_1 --beam-widths 1 3 5 10 --eval-samples 50 --device cpu --length-norm-alpha 1.0` | 写出可选 length-normalized beam selection report；不修改 checkpoint、不重训 |
| `python scripts\evaluate_v5_retrieval_assisted.py --checkpoint outputs_v2\v5_final_reports\stage1\checkpoints\best_model.pt --output-dir outputs_v2\v5_final_reports\retrieval_assisted --eval-samples 50 --beam-width 5 --retrieval-top-k 3 --device cpu` | 完成最小 lexical retrieval-assisted prototype 评测；stderr 0；生成 `retrieval_assisted_report.json`、Markdown summary、decode traces 和 copied/novel operator attribution |
| `python scripts\evaluate_v5_hybrid_planner.py --checkpoint outputs_v2\v5_final_reports\stage1\checkpoints\best_model.pt --output-dir outputs_v2\v5_final_reports\v5_hybrid_planner_prototype --eval-samples 50 --retrieval-top-k 5 --device cpu` | 使用既有 Stage1 checkpoint 评测 retrieval-centered hybrid planner；写出 `hybrid_planner_report.json`、`hybrid_planner_summary.md`、`attribution_report.json`、`candidate_trace_analysis.json` 和 stdout/stderr logs。Hybrid LCS 0.46504845，对比 retrieval-only 0.44371511；50/50 被选候选都是 retrieval pool identity。 |
| `python scripts\evaluate_v5_hybrid_planner.py --dry-run --eval-samples 3 --output-dir outputs_v2\v5_final_reports\v5_hybrid_planner_prototype_dryrun_check` | Dry-run 校验路径和样本计数，不执行模型、不改正式 artifact，只写 `dry_run_summary.json`：76,884 workflows，61,495 train，7,695 test，3 个 eval samples |
| 通过 `python -c` 检查 hybrid artifact schema | 确认 `hybrid_planner_report.json` schema 为 `gis_recommend.v5_final.hybrid_planner_prototype.v1`，attribution schema 为 `gis_recommend.v5_final.hybrid_attribution.v1`，candidate-trace schema 为 `gis_recommend.v5_final.hybrid_candidate_trace.v1`，并确认 runtime contract flags：`v5_full_generation_used_for_hybrid=false`、`retrained_model=false`、`checkpoint_mutated=false` |
| `python scripts\evaluate_v5_hybrid_planner.py --checkpoint outputs_v2\v5_final_reports\stage1\checkpoints\best_model.pt --output-dir outputs_v2\v5_final_reports\v5_hybrid_planner_multistage --eval-samples 50 --retrieval-top-k 5 --device cpu` | 使用既有 Stage1 checkpoint 评测 multistage retrieval-centered planner；写出 `hybrid_planner_report.json`、`hybrid_planner_summary.md`、`attribution_report.json`、`candidate_trace_analysis.json` 和 logs。指标：LCS 0.45586827，SetF1 0.57529907，token accuracy 0.33928243，IO validity 1.0。Rerank/repair contribution 0.0；50/50 被选候选都是 identity。 |
| `python scripts\build_unified_workflow_benchmark.py --out outputs_v2\v5_final_reports\unified_benchmark\unified_workflow_benchmark.json` | 写出 unified JSON/Markdown benchmark artifact。Rows 包括 `v4_quality_gate_teacher_forced`、`v4_quality_gate_autoregressive`、`set_predictor_quality_gate`、`v5_final_pure_generation`、`retrieval_centered_planner_retrieval_only` 和 `retrieval_centered_planner_hybrid`。Protocol flags 设置 `cross_task_metric_mixing_allowed=false` 和 `teacher_forced_vs_rollout_direct_comparison_allowed=false`。 |
| `python scripts\evaluate_retrieval_planning_stages.py --eval-samples 50 --retrieval-top-k 20 --filtered-top-k 10 --repair-max-edits 1 --repair-top-n-sources 1 --repair-max-candidates 80 --output-root outputs_v2\v5_final_reports` | 写出 retrieval filtering、execution-aware rerank、local repair、trace 和 summary artifacts。由于本地缺少 Set Predictor checkpoint，source 记录为 `task_type_operator_frequency_prior`；local repair 50/50 都选择 identity，repair contribution 为 0.0。 |
| `python scripts\evaluate_repair_oracle_phase.py --eval-samples 50 --retrieval-top-k 20 --max-repair-candidates 100 --substitution-top-k 10 --bridge-top-k 10 --output-dir outputs_v2\v5_final_reports\repair_oracle_phase --device cpu` | 写出 `repair_oracle_report.json`、`repair_failure_taxonomy.json`、`repair_candidate_traces.json` 和 `repair_phase_summary.md`。Mean oracle repair gain：LCS +0.12149891 / SetF1 +0.1027359 / token accuracy +0.13011901；repair win rate 0.88；repair selection failure rate 0.88；failure taxonomy 主要是 rerank failure。 |
| `python -m unittest tests.test_unified_workflow_benchmark tests.test_v5_empirical_experiment_scripts tests.test_v5_training_system tests.test_v5_final_runtime tests.test_phase15c_runtime_contract -v` | 47 tests OK；覆盖 unified benchmark grouping、hybrid multistage retrieval/fusion helpers、safe rerank selection、repair/contribution attribution、empirical experiment scripts、V5 training system、runtime contract 和 Phase 15C checkpoint/runtime 边界 |
| `python -m unittest tests.test_retrieval_planning_stages tests.test_v5_empirical_experiment_scripts tests.test_unified_workflow_benchmark tests.test_v5_training_system tests.test_v5_final_runtime tests.test_phase15c_runtime_contract -v` | 55 tests OK；覆盖 retrieval filtering、显式缺失 Set Predictor checkpoint 失败、local repair、execution-aware rerank、unified benchmark、hybrid helpers、V5 training/runtime 和 Phase 15C runtime contract |
| `python -m unittest tests.test_repair_oracle_phase tests.test_retrieval_planning_stages tests.test_v5_empirical_experiment_scripts tests.test_unified_workflow_benchmark tests.test_v5_training_system tests.test_v5_final_runtime tests.test_phase15c_runtime_contract -v` | 62 tests OK；覆盖 repair oracle phase、retrieval filtering、显式缺失 Set Predictor checkpoint 失败、local repair、execution-aware rerank、unified benchmark、hybrid helpers、V5 training/runtime 和 Phase 15C runtime contract |
| `python -m compileall scripts\evaluate_retrieval_planning_stages.py tests\test_retrieval_planning_stages.py` | OK |
| Retrieval planning forbidden-pattern scan | `outputs_v2/v5_final_reports/forbidden_pattern_scan_retrieval_planning.json` 报告 0 个命中：未发现 `strict=False`、`weights_only=False`、learned gamma、gated write、graph loss、entropy regularization、alpha anneal、backward 或 optimizer-step patterns |
| `python -m compileall scripts\evaluate_repair_oracle_phase.py tests\test_repair_oracle_phase.py scripts\evaluate_retrieval_planning_stages.py tests\test_retrieval_planning_stages.py` | OK |
| Repair oracle forbidden-pattern scan | `outputs_v2/v5_final_reports/repair_oracle_phase/forbidden_pattern_scan_repair_oracle.json` 报告 0 个命中：未发现 `strict=False`、`weights_only=False`、learned gamma、gated write/gating、graph loss、entropy regularization、alpha anneal、backward 或 optimizer-step patterns |
| `python scripts\evaluate_repair_selection_diagnostics.py --oracle-report outputs_v2\v5_final_reports\repair_oracle_phase\repair_oracle_report.json --candidate-traces outputs_v2\v5_final_reports\repair_oracle_phase\repair_candidate_traces.json --output-dir outputs_v2\v5_final_reports\repair_selection_diagnostics --seed 42` | 写出 required diagnostics artifacts。关键结果：identity selection 1.0，modified selection 0.0；oracle repair 的平均 score delta -0.19874815，但 LCS gain +0.12149891；最大 suppressor 是 `edit_penalty`；failure breakdown 为 `edit_oversuppression:44` / `retrieval_saturation:6`；random modified control mean LCS -0.05363936 |
| `python -m unittest tests.test_repair_selection_diagnostics tests.test_repair_oracle_phase tests.test_retrieval_planning_stages tests.test_v5_empirical_experiment_scripts tests.test_unified_workflow_benchmark tests.test_v5_training_system tests.test_v5_final_runtime tests.test_phase15c_runtime_contract -v` | 69 tests OK |
| `python -m compileall scripts\evaluate_repair_selection_diagnostics.py tests\test_repair_selection_diagnostics.py scripts\evaluate_repair_oracle_phase.py tests\test_repair_oracle_phase.py` | OK |
| Repair selection forbidden-pattern scan | `outputs_v2/v5_final_reports/repair_selection_diagnostics/forbidden_pattern_scan_repair_selection_diagnostics.json` 报告 `pass` 且 0 个命中：未发现 `strict=False`、`weights_only=False`、learned gamma、gated write/gating、graph loss、entropy regularization、alpha anneal、backward 或 optimizer-step patterns |
| `python scripts\evaluate_repair_scorer_ablations.py --candidate-traces outputs_v2\v5_final_reports\repair_oracle_phase\repair_candidate_traces.json --oracle-report outputs_v2\v5_final_reports\repair_oracle_phase\repair_oracle_report.json --output-dir outputs_v2\v5_final_reports\repair_scorer_ablations --seed 42` | 写出 scorer ablation artifacts。最佳低腐蚀策略是 `uniform_edit_0_12`：adoption 0.08，corruption 0.02，mean LCS +0.00333333，SetF1 +0.00488889，token accuracy +0.00952381。No-edit penalty 和当前测试的 piecewise penalties 都是净负收益。 |
| `python -m unittest tests.test_repair_scorer_ablations tests.test_repair_selection_diagnostics tests.test_repair_oracle_phase tests.test_retrieval_planning_stages tests.test_v5_empirical_experiment_scripts tests.test_unified_workflow_benchmark tests.test_v5_training_system tests.test_v5_final_runtime tests.test_phase15c_runtime_contract -v` | 74 tests OK |
| `python -m compileall scripts\evaluate_repair_scorer_ablations.py tests\test_repair_scorer_ablations.py scripts\evaluate_repair_selection_diagnostics.py tests\test_repair_selection_diagnostics.py` | OK |
| Repair scorer ablation forbidden-pattern scan | `outputs_v2/v5_final_reports/repair_scorer_ablations/forbidden_pattern_scan_repair_scorer_ablations.json` 报告 `pass` 且 0 个命中：未发现 `strict=False`、`weights_only=False`、learned gamma、gated write/gating、graph loss、entropy regularization、alpha anneal、backward 或 optimizer-step patterns |
| `python scripts\evaluate_repair_oracle_phase.py --checkpoint outputs_v2\v5_final_reports\stage1\checkpoints\best_model.pt --eval-samples 200 --retrieval-top-k 20 --max-repair-candidates 100 --substitution-top-k 10 --bridge-top-k 10 --output-dir outputs_v2\v5_final_reports\repair_oracle_phase_heldout_200 --device cpu` | 生成更大的 evaluation-only repair oracle trace。Oracle repair gain 仍存在：LCS +0.12405501 / SetF1 +0.10355055 / token accuracy +0.17590497；repair selection failure rate 0.85；没有训练或 checkpoint mutation |
| `python scripts\evaluate_repair_calibration_sweep.py --candidate-traces outputs_v2\v5_final_reports\repair_oracle_phase_heldout_200\repair_candidate_traces.json --output-dir outputs_v2\v5_final_reports\repair_calibration_sweep --edit-penalties 0.0 0.08 0.10 0.12 0.14 0.16 0.20 --bootstrap-iterations 500 --subset-sizes 50 100 200 --seed 42` | 写出 `calibration_sweep_report.json`、`calibration_stability_analysis.json`、`calibration_summary.md`、`calibration_curves.csv` 和 `forbidden_pattern_scan_calibration.json`。没有任何被测 penalty 是稳定正收益；0.0 collapse，0.08 over-adopt，`0.12` 没有在 50 样本之外得到确认 |
| `python -m unittest tests.test_repair_calibration_sweep tests.test_repair_scorer_ablations tests.test_repair_selection_diagnostics tests.test_repair_oracle_phase tests.test_retrieval_planning_stages tests.test_v5_empirical_experiment_scripts tests.test_unified_workflow_benchmark tests.test_v5_training_system tests.test_v5_final_runtime tests.test_phase15c_runtime_contract -v` | 78 tests OK |
| `python -m compileall -q scripts\evaluate_repair_calibration_sweep.py tests\test_repair_calibration_sweep.py scripts\evaluate_repair_scorer_ablations.py tests\test_repair_scorer_ablations.py` | OK |
| Repair calibration forbidden-pattern scan | `outputs_v2/v5_final_reports/repair_calibration_sweep/forbidden_pattern_scan_calibration.json` 报告 `pass` 且 0 个命中：未发现 `strict=False`、`weights_only=False`、learned gamma、gated write/gating、graph loss、entropy regularization、alpha anneal、backward、optimizer step 或 `torch.optim` patterns |
| `python scripts\evaluate_repair_opportunity_analysis.py --candidate-traces outputs_v2\v5_final_reports\repair_oracle_phase_heldout_200\repair_candidate_traces.json --transition-matrix outputs_v2\transition_allowed_next.json --output-dir outputs_v2\v5_final_reports\repair_opportunity_analysis --bootstrap-iterations 300 --seed 42` | 写出 `repair_opportunity_analysis.json`、`repair_success_correlations.json`、`repair_failure_taxonomy_v2.json`、`repair_locality_analysis.json`、`opportunity_prediction_summary.md`、`opportunity_signal_table.csv` 和 `forbidden_pattern_scan_repair_opportunity.json`。样本数 200；repair success rate 0.85；harmful rate 0.005；failure taxonomy 主要是 scorer ranking failure 0.85。 |
| `python -m unittest tests.test_repair_opportunity_analysis tests.test_repair_calibration_sweep tests.test_repair_scorer_ablations tests.test_repair_selection_diagnostics tests.test_repair_oracle_phase tests.test_retrieval_planning_stages tests.test_v5_empirical_experiment_scripts tests.test_unified_workflow_benchmark tests.test_v5_training_system tests.test_v5_final_runtime tests.test_phase15c_runtime_contract -v` | 83 tests OK |
| `python -m compileall -q scripts\evaluate_repair_opportunity_analysis.py tests\test_repair_opportunity_analysis.py` | OK |
| Repair opportunity forbidden-pattern scan | `outputs_v2/v5_final_reports/repair_opportunity_analysis/forbidden_pattern_scan_repair_opportunity.json` 报告 `pass` 且 0 个命中：未发现 `strict=False`、`weights_only=False`、learned gamma、gated write/gating、graph loss、entropy regularization、alpha anneal、backward、optimizer step 或 `torch.optim` patterns |
| `python scripts\evaluate_repair_confidence_regimes.py --candidate-traces outputs_v2\v5_final_reports\repair_oracle_phase_heldout_200\repair_candidate_traces.json --output-dir outputs_v2\v5_final_reports\repair_confidence_regimes --bootstrap-iterations 500 --random-iterations 200 --min-sample-count 10 --seed 42` | 写出 `repair_confidence_regime_report.json`、`repair_subtype_statistics.json`、`repair_context_analysis.json`、`precision_first_regimes.json`、`bootstrap_regime_validation.json`、`random_control_comparison.json`、`summary.md` 和 `forbidden_pattern_scan_confidence_regimes.json`。样本数 200；候选数 19,919；modified candidates 19,719；score-selected high-confidence regimes 0；oracle-only high-confidence subspaces 12。 |
| `python -m unittest tests.test_repair_confidence_regimes tests.test_repair_opportunity_analysis tests.test_repair_calibration_sweep tests.test_repair_scorer_ablations tests.test_repair_selection_diagnostics tests.test_repair_oracle_phase tests.test_retrieval_planning_stages tests.test_v5_empirical_experiment_scripts tests.test_unified_workflow_benchmark tests.test_v5_training_system tests.test_v5_final_runtime tests.test_phase15c_runtime_contract -v` | 88 tests OK |
| `python -m compileall -q scripts\evaluate_repair_confidence_regimes.py tests\test_repair_confidence_regimes.py` | OK |
| Repair confidence forbidden-pattern scan | `outputs_v2/v5_final_reports/repair_confidence_regimes/forbidden_pattern_scan_confidence_regimes.json` 报告 `pass` 且 0 个命中：未发现 `strict=False`、`weights_only=False`、learned gamma、gated write/gating、graph loss、entropy regularization、alpha anneal、backward、optimizer step 或 `torch.optim` patterns |
| Consolidation document content verification | Python verifier 检查 `docs/v5_system_consolidation_protocol.md`、`docs/PROJECT_CONTEXT.md` 和 `docs/PROJECT_CONTEXT.zh-CN.md` 是否包含最终系统身份、架构语义、实证层级、失败综合、治理整合、生产解释、研究路线图，以及 deployed/experimental/oracle-only 边界；结果为 `content verification passed` |
| `python scripts\evaluate_workflow_usability.py --eval-samples 200` (v2, 2026-05-13) | 200 samples 评估完成。Top-1 usable rate 0.5600，Top-3 any usable 1.0000，Top-5 any usable 1.0000，mean usability score 0.7663 (bootstrap 95% CI [0.7552, 0.7780])，mean QGIS mapping 0.6365，mean logic consistency 0.9368，mean step coverage 0.6197，reference usability 0.7207。533 个交换算子对，76/94 L3 代码有 QGIS 映射。全部 7 个 artifact 生成完毕。 |
| Workflow usability artifact sanity check (v2) | 7 个必需 artifacts 均存在：`workflow_usability_report.json`、`topk_usable_statistics.json`、`workflow_failure_taxonomy.json`、`usable_workflow_examples.json`、`unusable_workflow_examples.json`、`per_task_usability_breakdown.csv`、`workflow_usability_summary.md`。 |
| `python -m unittest tests.test_multi_reference_workflows` | 6 tests OK |
| `python -m compileall -q scripts\evaluate_multi_reference_workflows.py tests\test_multi_reference_workflows.py` | OK |
| `python scripts\evaluate_multi_reference_workflows.py --output-dir outputs_v2\v5_final_reports\multi_reference_evaluation --bootstrap-iterations 500 --seed 42` | 写出 369 条记录的 multi-reference artifacts。保守 exact-task reference pool 的 mean reference count 为 1.0，multi-reference record rate 为 0.0，因此 raw multi-reference deltas 为 0.0；canonicalized multi-reference 恢复 EM +0.00542005，LCS +0.0173991，token accuracy +0.06013034，SetF1 +0.01039799。 |
| Multi-reference artifact sanity check | 必需 JSON/CSV/Markdown artifacts 均存在；`forbidden_pattern_scan_multi_reference.json` 报告 `pass` 且 0 matches。 |
| `python -m compileall scripts\evaluate_multiref_validation.py tests\test_multiref_validation_experiment.py` | OK |
| `python -m unittest tests.test_multiref_validation_experiment -v` | 10 tests OK；覆盖 MRV variant generation、sensitive guards、semantic usability gates、QGIS landing decoupling、auto-labeling、registry eligibility、review packet export、manual-only registry construction 和 human-review stratification。 |
| `python scripts\evaluate_multiref_validation.py --max-workflows 50 --max-variants 100 --review-auto-verified 10 --review-plausible 5 --review-rejected 5` | 在 semantic-vs-landing 解耦后写出 `outputs_v2\v4_qg_multiref_validation\` artifacts。100 variants；21 个 commutative pairs；19 个 `verified_equivalent_candidate`、81 个 `invalid_variant`；19 条 auto-verified registry candidates；15-row stratified review sample；19-row `equivalence_review_packet.csv`；`verified_multi_reference_registry.json` 中 reviewed equivalence groups 为 0。QGIS landing 为辅助且仍弱：`qgis_mapping_valid_rate=0.0`、`qgis_io_valid_rate=0.74`、`strict_qgis_landing_usable_rate=0.16`。 |
| `Import-Csv outputs_v2\v4_qg_multiref_validation\equivalence_review_packet.csv \| Group-Object human_label` | MRV 人工标签校验通过：`equivalent=14`、`uncertain=4`、`not_equivalent=1`。 |
| `Get-Content outputs_v2\v4_qg_multiref_validation\verified_multi_reference_registry.json \| ConvertFrom-Json` registry sanity check | 手工 registry 校验通过：7 个 task groups、14 个 accepted source variant ids、标签计数 14/4/1，且 5 个 uncertain/rejected variant id 均未出现在 registry sources 中。 |
| `Get-Content outputs_v2\v4_qg_multiref_validation\multiref_validation_report.json` plus summary line check | MRV report 和 Markdown summary 均已记录 `reviewed_equivalence_group_count=7` 与 `reviewed_equivalent_variant_count=14`。 |
| 对 scripts 1559/2699/3986/3871 从 `step1/raw_workflows.json`、`step4/standardized_workflows.json` 和 quality-gate Step8 抽取 source operator windows | 确认 4 条 uncertain 的真实邻接关系。关键边界结论：`wf46_pos2_swap53_28` 从 `imgC.filterDate.filterBounds.filterMetadata` 跨到 `img.select`，把 select 放到 filterMetadata 前会破坏 ImageCollection/Image object chain。 |
| `Import-Csv outputs_v2\v4_qg_multiref_validation\uncertain_deep_review.csv` 加 registry/report sanity checks | Deep-review artifact 校验通过：4 条已检查，3 条 `conditional_equivalent_not_registry_eligible`，1 条 `not_equivalent_source_inspected`；当前 review packet 标签计数为 `equivalent=14`、`uncertain=3`、`not_equivalent=2`；registry 仍是 7 groups / 14 variants，excluded ids 未入库。 |
| `python scripts\evaluate_multiref_validation.py --max-workflows 200 --max-variants 500 --review-auto-verified 100 --review-plausible 30 --review-rejected 30 --output-dir outputs_v2\v4_qg_multiref_validation_expansion_500` | 写出 500-variant MRV expansion：500 variants、53 个 commutative pairs、46 个 auto `verified_equivalent_candidate`、454 个 `invalid_variant`、semantic auto pass 0.092、semantic usable 0.116、guard pass 0.9。QGIS landing 仍作为辅助信号且较弱：strict QGIS landing usable 0.074。 |
| `python scripts\analyze_mrv_expansion.py --input-jsonl outputs_v2\v4_qg_multiref_validation_expansion_500\generated_variants.jsonl --output-dir outputs_v2\v4_qg_multiref_validation_expansion_500 --taxonomy-path configs\equivalence_taxonomy.yaml` | 写出 MRV expansion analysis artifacts。Family total 与 risk total 均为 500；auto-pass 最高的 family 是 `select_filter` 0.1746 和 `filter_filter` 0.1281；`landing_only_failure=500` 只作为辅助 transferability failure。 |
| MRV expansion artifact sanity check | 已校验 500 generated variants、46 review-packet rows、family summary total 500、risk summary total 500，且 report 计数与 `multiref_validation_report.json` 对齐。 |
| AI-assisted review sanity check for `outputs_v2\v4_qg_multiref_validation_expansion_500\equivalence_review_packet_ai_review.csv` | 已校验 46 review rows，标签计数为 `equivalent=36`、`uncertain=8`、`not_equivalent=2`，registry draft 为 19 groups / 36 variant sources。 |
| `python scripts\build_mrv_registry_v2.py --manual-review outputs_v2\v4_qg_multiref_validation\equivalence_review_packet.csv --expansion-review outputs_v2\v4_qg_multiref_validation_expansion_500\equivalence_review_packet_ai_review.csv --output-dir outputs_v2\v4_qg_multiref_validation` | 写出 registry v2 / KB v2。最终计数：55 个唯一 reviewed variants、42 个 equivalent variants、23 个 task groups、13 个 excluded variants。 |
| Registry v2 JSON/CSV sanity check | 已校验 42 个 entry source variant ids、42 行 KB、excluded ids 与 registry entry ids 无重叠，risk keys 只有 `low`、`medium`、`unknown`。 |
| `python -m unittest tests.test_multiref_validation_experiment tests.test_mrv_expansion_analysis tests.test_mrv_registry_builder -v` | 20 tests OK。 |
| `python -m compileall scripts\evaluate_multiref_validation.py scripts\analyze_mrv_expansion.py scripts\build_mrv_registry_v2.py tests\test_multiref_validation_experiment.py tests\test_mrv_expansion_analysis.py tests\test_mrv_registry_builder.py` | OK。 |
| `python scripts\build_mrv_training_ablation.py --subset-sizes 5,10,all` | 写出隔离 MR ablation 数据到 `outputs_v2\v4_qg_mr_ablation\`：`mr_5`、`mr_10`、`mr_all_42` 和 `mrv_training_ablation_manifest.json`。基础 workflow 76,884；输出 workflow 76,889 / 76,894 / 76,926；val/test 不变；manifest 记录 `no_training_started=true`。 |
| `python -m unittest tests.test_mrv_training_ablation -v` | 4 tests OK。 |
| `python -m unittest tests.test_multiref_validation_experiment tests.test_mrv_expansion_analysis tests.test_mrv_registry_builder tests.test_mrv_training_ablation -v` | 24 tests OK。 |
| `python -m compileall scripts\evaluate_multiref_validation.py scripts\analyze_mrv_expansion.py scripts\build_mrv_registry_v2.py scripts\build_mrv_training_ablation.py tests\test_multiref_validation_experiment.py tests\test_mrv_expansion_analysis.py tests\test_mrv_registry_builder.py tests\test_mrv_training_ablation.py` | OK。 |
| 对 `mr_5`、`mr_10`、`mr_all_42` 执行 V4.6 quality-gate dry-run | `scripts/train_v4_6_quality_gate.py --data outputs_v2\v4_qg_mr_ablation\<version>\labeled_workflows_l3_v4_quality_gate.json --splits outputs_v2\v4_qg_mr_ablation\<version>\dataset_splits_v4_quality_gate.json --task-vocab outputs_v2\v4_qg_mr_ablation\<version>\task_type_vocabulary_v4_quality_gate.json --dry-run` 三个版本均通过；没有训练，也没有创建 checkpoint 目录。 |
| MR ablation artifact sanity check | 已校验注入样本 provenance 全部存在、每个版本 selected variant ids 唯一、excluded variants 与注入项无重叠、val/test split 不变、risk keys 仍只有 `low` / `medium` / `unknown`。 |
| `python -m unittest tests.test_mrv_ablation_comparator -v` | 3 tests OK；TDD red-green 后通过，覆盖 report metric extraction、delta 计算、missing-metric warnings、paired bootstrap、manifest counts 绑定和 CLI 输出。 |
| `python -m unittest tests.test_multiref_validation_experiment tests.test_mrv_expansion_analysis tests.test_mrv_registry_builder tests.test_mrv_training_ablation tests.test_mrv_ablation_comparator -v` | 27 tests OK。 |
| `python -m compileall scripts\evaluate_multiref_validation.py scripts\analyze_mrv_expansion.py scripts\build_mrv_registry_v2.py scripts\build_mrv_training_ablation.py scripts\compare_mrv_training_ablation.py tests\test_multiref_validation_experiment.py tests\test_mrv_expansion_analysis.py tests\test_mrv_registry_builder.py tests\test_mrv_training_ablation.py tests\test_mrv_ablation_comparator.py` | OK。 |
| MR comparator real-report smoke | 使用 `scripts\compare_mrv_training_ablation.py` 把 `outputs_v2\v4_qg_planner_reports\phase1_candidate_rerank_1000\planner_report.json` 同时作为 baseline 和 `baseline_self`，附带 manifest，输出到临时目录。脚本抽取 6 个 metric deltas，全部 delta 为 0.0，证明 comparator 能读取当前 planner report schema，且不训练、不访问 checkpoint。 |
| 读取 `结果\transformer训练结果\train_v4_6_quality_gate-mr-0517.md` | 服务器命令使用 `mr_all_42` data/split/task-vocab，checkpoint dir 为 `outputs_v2/transformer_checkpoints_v4_6_quality_gate_mr_all_42`；最终 test 指标为 Top1 31.3%、Top5 60.0%、TF-SeqEM 0.6%、AR-SeqEM 0.0%、AR-TokenAcc 18.8%。AR-SS 从 epoch 11 开始后训练 loss 变为 `inf`。 |
| `python -m compileall scripts\build_unified_workflow_benchmark.py tests\test_unified_workflow_benchmark.py scripts\evaluate_v5_hybrid_planner.py tests\test_v5_empirical_experiment_scripts.py` | OK |
| Unified benchmark forbidden-pattern scan | 对 `scripts/build_unified_workflow_benchmark.py` 和 `tests/test_unified_workflow_benchmark.py` 执行 `rg`，未命中 `strict=False`、`weights_only=False`、learned gamma、gated write、graph loss、entropy regularization、alpha annealing、training/backward/optimizer calls、runtime governance objects 或 `gis_recommend.evidence` imports |
| V5 hybrid script forbidden-pattern scan | 对 `scripts/evaluate_v5_hybrid_planner.py` 和 `tests/test_v5_empirical_experiment_scripts.py` 执行 `rg`，未命中 `strict=False`、`weights_only=False`、learned gamma、gated write、graph loss、entropy regularization、alpha annealing、training/backward/optimizer calls、runtime governance objects 或 `gis_recommend.evidence` imports |
| `python scripts\train_v4_quality_gate.py --dry-run` | 本地 `outputs_v2` 下的 quality-gate Transformer launcher 仍可正常校验：76,884 workflows，split 61,495 / 7,694 / 7,695，47 个 task type，vocab 98，checkpoint dir 为 `outputs_v2\transformer_checkpoints_v4_2_quality_gate`。 |
| `python scripts\train_set_predictor_quality_gate.py --dry-run` | 之前本地 dry-run 可正常校验 quality-gate 输入：76,884 workflows，split 61,495 / 7,694 / 7,695，47 个 task type，47 个 active token。2026-05-14 路径对齐后，launcher 默认 checkpoint dir 为 `outputs_v2\set_predictor_checkpoints_v3_quality_gate_v4_6`；下次本地完整训练前需重新 dry-run。 |
| `python scripts\smoke_v4_quality_gate_training_entry.py --batch-size 2 --max-samples 2 --split train` | V4 quality-gate training-entry smoke 在本地 CPU 上仍通过。成功加载 v2 的 94-token embeddings，输出 logits shape `[2, 100, 98]`，且不会写 checkpoint。 |
| 2026-05-13 V4 全链路路径审计 | 已确认当前最可落地的 V4 主线是 `quality_gate` 训练 + v2 QGIS grounding，并以 V4.6 作为最终实用 checkpoint family。通用 V4 推理/评测 CLI 默认仍不完全安全。本地若要完整复跑，还缺服务器结果 artifact：`outputs_v2/transformer_checkpoints_v4_6_quality_gate/`、`outputs_v2/set_predictor_checkpoints_v3_quality_gate_v4_6/`，以及可选的 `outputs_v2/qgis_operator_io_types.json`。Quality-gate `task_type_length_stats.json` 现在已存在于 `outputs_v2/pipeline/step8_quality_gate/`。 |

## 未完成事项

| 优先级 | 任务 | 说明 |
| --- | --- | --- |
| 高 | 决定并实现受控 GEE+QGIS SFT 训练路径 | `outputs_v2/pipeline/step8_quality_gate_qgis_vector/` 结构上可从头训练，且已有 combined 48-type vocab，但 QGIS 只占 train 的 1.1%，也没有 QGIS val/test 评测。如果必须从 DPO v2 warmstart，需要先实现 47->48 task-type 权重的 partial/expanded warmstart loader。如果目标仍是 GEE:QGIS=5:1，应实现 weighted sampler 或双 dataloader mixer，而不是依赖当前保守合并包比例。 |
| 高 | 用更宽的 QGIS 矢量记录做弱监督和 coverage mining | 1,598 条纯矢量总记录继续用于 preference 构造、missing-L3 bridge 优先级分析和 coverage mining。不要在未重新核验的情况下把全量 canonical vector dataset 当作 clean SFT 训练集。 |
| 高 | 继续补强细粒度 vector family，而不是只追求 vector-token rate | 未见任务评测证明 SFT 已能把 vector prompt 从栅格模板拉回矢量模式，但 family recall 仍低且集中。下一步数据/训练应重点补或过采样 0-hit / 低命中 family：dissolve、geometry repair/cleanup、clip、intersection、difference、attribute filter、CRS transform、field calculation、export、grid/centroid、table join 和 overlay subtypes。 |
| 高 | 把 semantic-tag enrichment 与 facts 文本索引合并后重建 open landing v3 | 当前 `+sem tags` 提升了多样性，但 modality 降到 84%，原因是 enrichment 重建数据集时缺少 facts 文本。应更新 retrieval/eval 构建路径，让 semantic tags 与 `Task Name` / `Task Description` 同时进入索引，然后重新生成 v3 并复跑 80 条 open landing。 |
| 高 | 补开放式 QGIS landing 失败样本对应的细粒度 bridge/native bridge | 优先补人工审核中缺失的矢量意图：mergevectorlayers、difference/erase、spatial/attribute join、extractbyexpression、extractbylocation、fixgeometries、simplifygeometries、creategrid、voronoi/thiessen、heatmap、nearest、polygonstolines、centroids、split/snap、deleteholes、delete duplicates、field calculator、saveselectedfeatures/export。 |
| 高 | 补 raster/mixed 任务中 clip/warp 模板之外的 QGIS bridge | 优先补 zonalstatistics、polygonize、rasterize alignment、rastersampling、fillnodata/interpolation、reclassify/threshold/rastercalculator、contour、hillshade、buildvirtualraster/merge、cost distance、random points in polygons、raster-to-points、table export、area/statistics summary。 |
| 高 | bridge 补强后重跑 80 条 open landing 人工审核 | 成功标准不能再只看 modality，应看严格人工 grade。第一轮目标：C 类比例降到 40% 以下，最高频模板集中度降到 25% 以下。 |
| 高 | 训练/评测前重新生成或显式 provenance-stamp Step6-8 v2 产物 | 现有 `outputs_v2` 产物早于 provenance reporting，仍会报告 `missing_provenance`；不要重跑训练 |
| 高 | 审查质量门禁 quarantine hotlist 并决定回灌策略 | 30,515 条 workflow 因低置信 `auto_remap` 被隔离；审核高影响 operator 后可恢复一部分有用 L3/task 覆盖，同时避免重新引入标签噪声 |
| 高 | 从服务器同步 V4 quality-gate 和 Set Predictor 原始结果 artifact | Unified benchmark 当前把 V4 TF/AR 和 Set Predictor 指标记录为用户提供的 external values。最终实用主线应同步 `outputs_v2/transformer_checkpoints_v4_6_quality_gate/` 和 `outputs_v2/set_predictor_checkpoints_v3_quality_gate_v4_6/`；旧 V4.2 artifact 只作为历史对照材料保留。 |
| 高 | 把受控当前 v2 模型预测接入 empirical artifact schema | Baseline-only 的 `outputs_v2` empirical artifact 基础设施已经存在，V5_final 训练/评测现在可以产出 storage-only model record。等匹配的 v2/V5 checkpoint 存在后，把真实模型预测、beam candidates、decode metadata、candidate pools 和 oracle candidate metrics 写入同一逐样本 schema。 |
| 高 | 继续 conditional repair diagnostics，但不要改 production scoring | Stage0/Stage1、A1 no-PVM、beam-search 复评、retrieval-assisted generation、hybrid/multistage planner、repair oracle、repair-selection diagnostics、scorer ablations、200 样本 calibration sweep、repair opportunity analysis 和 repair confidence-regime search 已存在。Stage2 full training 仍应 blocked。没有任何被测 uniform penalty 是稳定正收益，宽泛 opportunity indicators 没有区分度，且没有找到 score-selected high-confidence repair regime；后续只能 evaluation-only 地测 scorer discrimination/calibration，生产 scoring 暂不修改。 |
| 高 | 在任何 runtime selector 变化前先校准 evidence-aware ranking | 2026-05-23 的离线 smoke 显示 LCS/SetF1 有改善，但 TokenAcc 和 oracle 命中率都没有超过 legacy。下一步应在更大报告上按任务类型/来源/指标族拆分评估、调节或否定 policy term；不要再用 observation-only Phase5.x 字段扩展代替 ranking 修复。 |
| 高 | 把 `docs/v5_system_consolidation_protocol.md` 作为长期声明边界参考 | 后续报告在声明 generation、repair、rerank、retrieval、set prediction 或 execution awareness 前，应先使用其中的 deployed / experimental / oracle-only 区分和能力层级。 |
| 高 | 在任何 semantic-indexing 集成前人工审查 bounded ontology rows | 新 inventory 刻意保持离线。未来如果重新研究 semantic retrieval/rerank，必须先人工审查 13 条 exact GEE<->QGIS 候选，并继续禁止 partial / execution-sensitive / ambiguous / composite 行进入 runtime equivalence。GDAL/ArcGIS 在真实映射资产构建前仍是 unsupported。 |
| 高 | 准备好后启动受控 quality-gate 训练 | 最终实用 Transformer 主线使用 `scripts/train_v4_6_quality_gate.py`，并配套 V4.6 quality-gate Set Predictor artifact。Transformer launcher 依赖 `outputs_v2/transition_allowed_next.json`，如果候选集或 split 变化必须先重建；不要用原 `train_v4_2.py` 或 `train_set_predictor_v3.py` 默认入口做 quality-gate 实验。 |
| 高 | 后续代码生成前解决 GEE alias 缺口 | 候选 alias 审计仍有 10 个 unresolved official-name operator，包括 `ee.imagecollection.filtermetadata`、`ee.imagecollection.clip`、`ee.classifier.randomforest`、`ee.algorithms.snic` |
| 高 | 审查剩余硬编码旧路径的脚本 | 已知仍有旧评测/旧推理/旧训练工具引用 `classification_hierarchy.csv`、`outputs/l3_embeddings.pt` 或 350 vocab |
| 高 | 重算或标注受影响的历史 Step8 + V4.6 报告 | token contract 已在代码中修复，但旧报告的 sequence metrics 可能有偏。用于 checkpoint 选择、MR 消融或论文结论前，必须用 `v2_94_l3` 重新计算重要 V4.6 报告。 |
| 高 | 生成或显式声明 v2 QGIS I/O metadata profile | `gis-evaluate` 不再静默读取 legacy I/O metadata。若主线报告需要 Level-1 executable/I/O diagnostics，应生成 `outputs_v2/qgis_operator_io_types.json`；否则报告应明确 `fallback_status=missing`。`--allow-legacy-io-types` 只能用于显式兼容运行，不能支撑 mainline claims。 |
| 中 | 除非主线决策变更，否则保持 V4-QG artifact 为 research/candidate | `evaluate_v4_quality_gate.py`、V4-QG planner 和配置注释现在都标为 non-mainline/research。若未来要提升 V4-QG，必须新增显式 profile 并更新 lineage/contracts，不要复用当前 Step8 + V4.6 报告语义。 |
| 高 | 将真实 V4-QG 和 Set Predictor checkpoint 接入 Phase 1 planner | `scripts/run_v4_qg_planner.py` 现在默认读取 V4.6 Set Predictor 路径 `outputs_v2/set_predictor_checkpoints_v3_quality_gate_v4_6/best_model.pth`。本地 workspace 仍缺实际 artifact；需要同步服务器训练好的 Transformer/Set Predictor checkpoint，或显式传路径后，才能声明真实 V4 AR / Set Predictor candidate contribution。 |
| 高 | 只有明确要求时才运行受控 MR training ablation | 隔离输入已存在于 `outputs_v2/v4_qg_mr_ablation/`（`mr_5`、`mr_10`、`mr_all_42`）。默认不要启动训练，也不要覆盖 quality-gate baseline/checkpoint。如果用户明确要求训练，必须写入独立输出目录，并用 TopK usable、diversity、invalid/harmful rate、canonicalized LCS/SetF1/token metrics 与 quality-gate baseline 对比，exact match 只能作为次要指标。 |
| 高 | 用 AR-SS 修复后的 trainer 重跑 V4.6 baseline/MR control | 2026-05-17 的 `mr_all_42` run 使用的是修复前逻辑，当时 dynamic-min-length END mask 可能让 CE loss 变成 `inf`。继续训练 `mr_5`/`mr_10` 前，至少先用同策略 V4.6 quality-gate baseline 跑过 epoch 11+，并明确消融比较用 latest epoch、best validation epoch 还是固定 epoch。 |
| 高 | 等真实 ablation reports 出现后使用 MR comparator | 只读 comparator 已完成，但当前还没有 `mr_*` 模型训练/评测 report。用户明确要求训练并完成评测后，运行 `scripts/compare_mrv_training_ablation.py --baseline-report <baseline_report> --variant-report mr_5=<report> ... --manifest outputs_v2\v4_qg_mr_ablation\mrv_training_ablation_manifest.json`，且只解释输入 report 中实际存在的指标。 |
| 高 | 等待服务器侧 baseline 与 `mr_all_42` 训练产物 | 用户会在服务器上训练。回传时需要 baseline checkpoint/report、`mr_all_42` checkpoint/report、准确命令或配置、eval split/sample count/参数，以及训练日志/错误。`mr_5` 和 `mr_10` 继续阻塞，直到 `mr_all_42` 对比无负面信号。 |
| 高 | 把 V5 implementation 限制在最小 runtime semantic kernel 内 | 不要新增 governance authority。唯一可能成为 runtime-authoritative 的新对象是很薄的 frozen `role -> callable` dispatch registry。`RuntimeProfile`、`CheckpointManifest`、`DatasetLineage`、`GradientProfile`、`MetricRecord`、`CompatibilityResult`，以及不在已激活 eval/inference call 内的 `DecodePolicy`，都必须保持为 DTO、snapshot、pure validation return 或 archaeology/reporting artifact |
| 高 | 后续修改继续守住 execution purity | 主 runtime 路径现在对 provenance/audit/repair 只 report-only，对 checkpoint loading 采用 strict structural loading。剩余风险是回归：不要把 `gis_recommend.evidence` 导入 training/inference/models/pipelines，不要恢复 raw/partial checkpoint fallback，不要把 test-only `test_mvcs_closure_harness.py` 里的 counterexample 当成实现模式 |
| 中 | 决定默认 QGIS 映射数量是否应为 438 还是完整 447 | 当前默认保留人工审核/人工覆盖，但仍过滤普通低置信度自动映射；`min_confidence=0.0` 会加载 447 |
| 中 | 给 KG 输出增加 provenance | KG 输出应记录 hierarchy path/count、id mappings path/hash，避免静默用 350-L3 重建 |
| 中 | 如果实例层导入要进入主线，需要先加固可选 KG instance importer | `scripts/import_gee_workflows_v2.py` 仍有硬编码路径和连接假设。当前 Step8 + V4.6 主线 KG 使用重点是 ontology / mapping，不要在服务器上直接运行该实例导入脚本，除非先审查路径和凭据。 |
| 中 | 将 empirical artifact generation 纳入常规评测 | 独立 empirical builder 已记录 retrieval-only、Markov、sequence entropy、task ambiguity、canonicalization 和 decode-policy summary。下一步是在常规评测 pipeline 中调用或镜像它，同时保持 diagnostics 不反向 gate runtime。 |
| 低 | 清理临时/缓存目录 | `.pytest_cache`、`codex_tmp`、测试临时目录存在；如需清理必须显式、非破坏性处理 |

## 下一步建议

1. 如果 quality-gate 候选集或 split 有变化，先用 `scripts/build_quality_gate_transition_matrix.py` 重建 `outputs_v2/transition_allowed_next.json`。
2. 通过 `scripts/train_v4_6_quality_gate.py` 启动受控 Transformer 训练，不要直接运行原 `train_v4_2.py` 默认 `main()`；这样会使用 quality-gate 候选路径、v2 transition matrix，并写入独立的 `outputs_v2/transformer_checkpoints_v4_6_quality_gate` checkpoint 目录。
3. 如果后续完整评测启用 set prior，训练或同步匹配 V4.6 quality-gate 主线的 Set Predictor，让 planner 读取 `outputs_v2/set_predictor_checkpoints_v3_quality_gate_v4_6`。
4. 等匹配的 quality-gate checkpoint 存在后，把受控模型预测接入 `gis_recommend.empirical_evaluation.v1`；当前 baseline-only smoke artifact 是参考 schema 和 baseline floor。
5. 对 retrieval-centered planning，不要把 `uniform_edit_0_12`、宽泛 repair-opportunity indicators 或 oracle-only confidence regimes 生产化。200 样本 calibration sweep 显示 uniform penalty 不稳定且均值为负，opportunity analysis 显示宽泛指标没有选择性，confidence-regime search 找到 0 个 score-selected deployable regime。下一步 scorer 工作应继续 evaluation-only，重点测 scorer discrimination/calibration，同时继续分开报告 retrieval / rerank / repair / generation contribution。
6. 使用 `docs/v5_system_consolidation_protocol.md` 作为项目级声明边界参考。后续报告必须把 retrieval / rerank / repair / generation / set / execution contribution 按 deployed、experimental 或 oracle-only evidence 分开。
7. 将 `outputs_v2/v5_final_reports/bounded_ontology_inventory/` 只作为离线 ontology inventory 使用。若未来重新研究 semantic indexing，应从人工审查 13 条 exact GEE<->QGIS 候选开始；没有新资产前不得推断 GDAL/ArcGIS 映射。
8. 审查 `outputs_v2/pipeline/step8_quality_gate/quality_gate_report.md` 的 quarantine hotlist；决定哪些高影响 `auto_remap` operator 应人工修正后回灌，哪些继续隔离。
9. 在 L3->GEE 代码生成前处理 `outputs_v2/pipeline/step8_quality_gate/gee_operator_alias_audit.md` 中 10 个 unresolved official-name alias。
10. 用新的 provenance gate 重新生成 `outputs_v2` Step6-8，或在不想重生成时设计一个受控 provenance-stamping 路径。
11. 重新执行 `python scripts/audit_pipeline_outputs.py --outputs-dir outputs_v2 --require-provenance --fail-on-warning` 做 report-only provenance check，并处理或显式接受 Step3 drop warning。

## 当前科学共识 (2026-05-10)

本节是项目的权威继承状态，为后续会话提供统一的科学叙述。它综合了截至 2026 年 5 月的所有实证发现、治理协议和科学边界。`docs/v5_system_consolidation_protocol.md` 是最终系统身份、生产解释和声明边界的项目级综合协议。在解读任何 artifact 或做出任何声明之前必须先读本节和该协议。

### A. 当前运行时理解

**重要：本节描述当前经验验证的运行时，主要在目标架构的算子-token 层（L3）运行。** 这是为经验可行性做的简化。长期目标架构（L1→L2→L3→平台）在 A.0 节中保留。以下任务族描述的是当前运行时的操作模式，而非最终架构。

当前运行时包含**三个经验上不同的任务族**，学习难度各不相同：

**任务族 A — 算子集预测。** 预测工作流中包含哪些算子，忽略顺序。实现为多标签分类器（Set Predictor V3），基于 47 个活跃算子 token。这是最可学习的 formulation：仅从任务文本即可达到 SetF1 = 0.711。剩余 ~29% 是不可约简的集合级模糊性。

**任务族 B — 检索中心的工作流规划。** 检索、重排、可选修复训练样本。这是**当前最强策略**。系统通过词法/嵌入相似度检索相似训练工作流，通过评分函数重排候选，并可应用受约束的局部编辑。在此范式下，V5_final 作为**完整候选评分器**，而非生成器。核心组件：检索 (C_ret)、重排 (C_rank)、修复 (C_rep)、IO 约束 (C_io)。

**任务族 C — 自回归工作流生成。** 通过 AR 解码从头生成算子序列。实现为 V5_final：带 PVM 检索注意力的记忆增强 AR 规划器，固定时间衰减，仅训练期 alpha noise，IO 约束 beam decode。这是经验上**最弱的 formulation**。

**Set Predictor** 是独立模型（多标签分类器），提供算子集级别的证据。它**不是**工作流生成器。其 SetF1 = 0.711 是从任务文本可达到的算子集预测上限。

**V5_final** 是 AR 序列模型，直接预测算子（~150 类词表），绕过 V4 使用的 L3 中间表示。在检索中心范式下，它作为候选评分器使用，而非生成器。

**最终当前运行时身份：** 当前已验证系统是 retrieval-centered、execution-aware、rerank-driven、constrained-planning-oriented。当前性能主要由 retrieval preservation 支撑。Generation 不是主要已验证能力，repair 在当前证据下不能生产部署。这描述的是当前 L3 级运行时；长期目标架构（L1→L2→L3）在 A.0 中单独保留。

**关键词表区分：** V4 预测 L3 基元（98 类）；V5 直接预测算子（~150 类）。V4 和 V5 之间的直接 token 级别比较是**无效的**。只有算子序列指标（LCS、SetF1、EM）支持跨版本比较。

**当前运行时实现已冻结。** V5_final 神经架构、训练目标、损失函数和模块设计不得修改，除非满足：(a) 检索中心规划达到 LCS 上限，(b) 评分器校准已穷尽，(c) 修复贡献已最大化，且 (d) 受控消融实验证明神经架构是约束瓶颈。目前四个条件均不满足。

**长期目标架构已保留，且与当前运行时不同。** 见下方 A.0。

#### A.0 关键区分：当前运行时 vs. 长期目标架构

```
┌─────────────────────────────────────────────────────────────────┐
│                                                                 │
│  语义漂移警告：                                                   │
│                                                                 │
│  近期的综合文档描述的是【当前经验验证的运行时】。                     │
│  它们描述的不是【长期目标架构】。                                   │
│                                                                 │
│  混淆两者会导致【架构坍塌】：将一个分层语义架构                       │
│  扁平化为单层算子-token 检索系统。                                 │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

**原始架构（已保留）：**

```
自然语言任务描述
        │
        ▼
┌──────────────────────────────────────────┐
│  L1 — 算法分类                            │
│  例："空间分析"、"水文分析"、"图像处理"       │
│  粗粒度任务分类。                          │
└──────────────────────────────────────────┘
        │
        ▼
┌──────────────────────────────────────────┐
│  L2 — 平台无关的语义意图                    │
│       （核心架构层）                        │
│  例："对要素周围做缓冲区"，                  │
│      "从高程计算坡度"，                     │
│      "求两个面图层的交集"                    │
│                                            │
│  描述工作流需要【完成什么】，而不承诺          │
│  任何特定平台【如何实现】。                   │
│                                            │
│  这不是可选便利层。它是跨平台工作流推理        │
│  的架构基础。                               │
└──────────────────────────────────────────┘
        │
        ▼
┌──────────────────────────────────────────┐
│  L3 — 平台特定算子                         │
│  例：QGIS "Buffer vectors"、              │
│  ArcGIS "Buffer_analysis"、              │
│  GEE "ee.Image.zeroCrossing"             │
│                                            │
│  将每个 L2 语义意图映射到特定平台上可用的      │
│  具体算子。不同平台有不同的算子名称、参数       │
│  约定和能力子集。                           │
└──────────────────────────────────────────┘
        │
        ▼
┌──────────────────────────────────────────┐
│  可执行工作流                              │
│  平台特定的算子链，具备有效的 I/O 连接、      │
│  参数和执行语义。                           │
└──────────────────────────────────────────┘
```

**当前运行时实际做什么：**

当前经验验证的系统主要在 L3 算子-token 层运行：

- V5_final 直接预测算子 token（~150 类平台特定算子名称词表）。
- 检索从训练数据中检索算子序列（平台特定）。
- 重排对候选算子序列评分（平台特定）。
- 修复局部修改算子 token（平台特定）。

这是为**经验可行性做的有意简化**。它不是对仅算子级推理的永久架构承诺。当前系统将 L1→L2→L3 扁平化为单一预测任务，原因如下：

1. 质量门禁训练数据提供带 L3 标签的算子序列，但没有显式的 L2 语义意图标注。
2. 构建 L2 语义本体是独立且规模可观的数据工程任务。
3. 证明算子级检索优于算子级 AR 生成是必要的经验里程碑，而非语义层不必要的声明。

**为什么经验发现【加强】而非削弱了对 L2 语义抽象的需求：**

| 当前问题 | 根因 | L2 抽象如何帮助 |
|----------|------|-----------------|
| V5 纯生成 LCS = 0.25 | 任务文本→算子的鸿沟太大，直接 AR 难以跨越 | L2 提供中间语义目标，缩小预测鸿沟 |
| 检索语料依赖平台特定样本 | 无跨平台训练数据 | L2 使平台无关检索成为可能，扩大有效语料 |
| 算子词表约 150 且与平台纠缠 | 平台特定算子名称 | L2 词表（约 50-80 个语义意图）更小、更稳定、平台无关 |
| 修复候选仅有算子替换 | 无语义等价映射 | L2 算子在不同平台间有定义的等价类 |
| Set Predictor 学习"哪些算子"来自任务文本 | 学习平台特定的共现，而非语义成员关系 | L2 集合预测将学习算子【为什么】共现，使迁移成为可能 |
| raw 精确匹配在严格序列评分下为 0.0 | 重排序或近似等价 workflow 的算子序列也不同；canonicalized evaluation 只能恢复小部分 | L2 序列或受治理的规范化形式未来可能归一化部分变体，但当前证据只支持窄的 evaluation-layer 修正 |

**关键反坍塌规则：**

```
"算子级检索当前优于算子级 AR 生成这一事实，
 并不蕴含语义中间层不必要的结论。

 它蕴含的是：
 (a) 算子级预测问题本身很难，
 (b) 检索在该层级上是比生成更强的策略，
 (c) 任务文本与算子 token 之间的语义鸿沟很大，
 (d) 通过中间语义抽象来桥接这一鸿沟，是当前
     运行时尚未实现的有希望方向，而非已被
     证伪的方向。"
```

**什么已冻结 vs. 什么已保留：**

| 方面 | 状态 | 含义 |
|------|------|------|
| V5_final 神经架构（PVM、AR decoder、memory slots） | **已冻结** | 不得修改模块、损失或训练目标 |
| 当前算子-token 检索运行时 | **已冻结** | 检索中心规划是已验证范式 |
| L1→L2→L3 语义层级 | **已保留** | 这是目标架构；当前运行时是 L3 级的简化 |
| L2 语义意图层 | **已保留** | 核心架构组件；实现推迟，非放弃 |
| 跨平台抽象 | **已保留** | 项目目标仍是 QGIS + ArcGIS + GEE，不仅是 QGIS |
| L2→L3 映射的新神经架构 | **已冻结** | 不符合重开标准则不得提出 |
| L2 本体构建（非神经、数据工程） | **允许** | 构建 L2 分类法是数据工作，非架构重设计 |
| L2 语义级检索（非神经） | **允许** | 检索 L2 意图而非 L3 算子是数据级变更，非架构级 |

### B. 统一基准解读

所有结果均基于**质量门禁数据集**（76,884 条工作流，47 个任务类型，训练/验证/测试 = 61,495/7,694/7,695）。该数据集从 107,399 条原始工作流中过滤，移除了低置信 auto_remap 和跨 split 序列泄露。

**按任务族的基准行（算子序列输出，~150 类词表）：**

| 系统 | 任务族 | LCS | TokenAcc | SetF1 | EM | IO有效性 |
|------|--------|-----|----------|-------|-----|----------|
| Set Predictor (quality-gate) | A (集合) | N/A | N/A | **0.711** | N/A | N/A |
| 词法检索 (top-1) | B (检索) | 0.444 | 0.237 | 0.567 | 0.0 | 1.0 |
| 检索中心规划器 (多阶段) | B (混合) | **0.456** | **0.339** | 0.575 | 0.0 | 1.0 |
| V5_final 纯生成 (greedy) | C (生成) | 0.247 | 0.091 | 0.360 | 0.0 | 1.0 |
| Markov2 | 基线 | 0.379 | N/A | N/A | 0.0 | N/A |

**V4 参考行（L3 token，98 类 — 不同任务，仅供上下文）：**

| 系统 | 任务 | Top1 | Top5 | AR-TokAcc | TF-SeqEM | AR-SeqEM |
|------|------|------|------|-----------|----------|----------|
| V4.2 TF (quality-gate) | L3 token (TF) | 48.3% | 71.3% | N/A | 2.3% | N/A |
| V4.2 AR (quality-gate) | L3 token (AR) | N/A | N/A | 21.1% | N/A | 0.0% |

**不变事实：**
- 当前主要 benchmark 行的 raw 精确匹配 (EM) 为 0.0。这很大程度是评测属性（76,884 个唯一测试序列，组合空间极大），不能单独作为模型失败证明。后续 evaluation-only canonicalized pass 在 369 条持久化预测记录中恢复了 2 条 exact match，并提升 LCS/token accuracy/SetF1，说明合法局部重排序会造成指标低估，但 canonicalized EM 仍然很低。
- IO 有效性 = 1.0，适用于所有 IO 约束系统。
- 检索中心规划 LCS (0.46) >> 纯生成 LCS (0.25)。
- Set Predictor F1 (0.711) 是集合级上限；V5 SetF1 (0.360) 约为上限的 50%。

**禁止比较：**
1. V4 teacher-forced 指标（Top1, TF-SeqEM）vs V5 rollout 指标（TokenAcc, LCS）—— 不同预测模式。
2. V4 token 级指标 vs V5 token 级指标 —— 不同预测任务（L3 vs 算子）。
3. 将检索中心规划指标包装成纯生成能力。
4. 将 Set Predictor SetF1 包装成序列规划准确率。
5. 任何没有显式 task/mode/scope/vocabulary 对齐的跨族比较。

### C. 已被实证证明的事实

1. **检索中心规划显著优于纯 AR 生成。** 检索 LCS ≈ 0.46 vs 生成 LCS ≈ 0.25。该差距在所有评测配置下都大且稳定。

2. **Oracle 证明修复机会存在。** Oracle 修复增益：LCS +0.12，修复胜率 0.88，腐蚀率 0.02。当 oracle 在局部编辑候选中选择时（替换、桥接插入、删除、交换），有用修复频繁存在且腐蚀风险低。

3. **评分器过度压制编辑。** edit_penalty 项是所有 4,939 个修改候选中的最强抑制项。identity 选择频率 = 1.0；修改选择频率 = 0.0。部署评分器从不选择非 identity 修复候选。

4. **完全移除编辑惩罚是有害的。** 无编辑惩罚会采用 100% 修复，但 mean LCS 下降 (-0.013)，腐蚀率 32%。编辑惩罚作为安全项是必要的，但当前 0.20 过强。

5. **尚未找到稳定的全局修复校准。** 200 样本校准扫描测试了 0.0-0.20 的 uniform edit penalty。没有任何被测 penalty 在 bootstrap 区间上稳定为正。0.0 崩溃（腐蚀 0.32），0.08 过度采用（腐蚀 0.18），0.12 的 mean LCS 为 -0.001 且置信区间跨零。50 样本对 penalty 0.12 的提示在更大规模**未被确认**。

6. **当前 score selection 下尚未找到高置信 repair regime。** 200 样本 confidence-regime search 找到 0 个 score-selected 低腐蚀 regime。它确实找到 12 个 oracle-only subspaces，但这只能证明候选存在，不能作为可部署 repair policy。

7. **Set Predictor 包含有意义的信号。** 仅从任务文本即可达到 SetF1 = 0.711，证明算子集成员关系是显著可预测的。这是上限：序列模型还需预测顺序，任务严格更难。

8. **V5_final 稳定训练且无崩溃。** Stage 1（10K 子集，30 epoch）在六个稳定性指标上均无崩溃。模型确实在学习（Top5 token accuracy = 62.1%），但其 argmax（TokenAcc = 9.1%）很差。

9. **PVM 检索注意力功能正常。** Alpha 熵 = 0.822，槽位利用率 = 0.367。记忆检索活跃（未坍塌为均匀分布），但槽位利用率表明可用容量未充分利用。

10. **IO 约束解码有效。** IO 有效性 = 1.0，在所有 IO 约束系统上均成立。

11. **随机选择修改候选是有害的。** mean LCS -0.054。没有校准评分的修复接受会破坏检索价值。

### D. 已被证伪的路径

1. **朴素全 AR 规划。** V5_final 纯生成 LCS = 0.25，TokenAcc = 0.09，显著低于检索基线（LCS 0.46，TokenAcc 0.34）和 Markov2（LCS 0.38）。仅从任务文本进行纯自回归生成目前不可行。

2. **无限制修复采用。** 无编辑惩罚和分段惩罚配置均产生净负 mean LCS，腐蚀率 > 0.25。没有校准评分就接受修复是破坏性的。

3. **全局统一编辑校准。** 没有单一 edit penalty 值在 200 样本评测集上稳定有效。编辑惩罚与修复质量之间的关系在不同任务类型和候选池中是非均匀的。

4. **当前 score selection 下的 precision-first confidence gating。** 高置信 regime search 没有找到同时满足低腐蚀、mean LCS/token accuracy 为正且 bootstrap 支持的 score-selected regime。Oracle-only regimes 不能被当成 runtime gates。

5. **检索辅助生成带来改进。** 当 V5_final 被允许通过生成（而非受约束局部编辑）修改检索候选时，无法改进未修改检索。安全策略下 rerank contribution = 0.0，repair contribution = 0.0。

6. **精确匹配评测。** 主 benchmark 行的 raw EM 为 0.0；即使 canonicalized EM 当前也只恢复少数样本（当前 evaluation-only 报告为 2/369）。严格 EM 区分度很弱，不应作为工作流规划的主要指标。

7. **架构即瓶颈假说。** 架构在 8 个已识别瓶颈中排第 8。主导瓶颈是监督模糊性、评分器校准、数据不平衡和本体缺口。

### E. 当前瓶颈层级

按证据强度排序（最强证据优先）：

1. **监督模糊性** — 主导瓶颈。同一任务存在多个有效工作流；训练数据提供一个参考但许多序列同样是合理的。四条独立证据线汇聚。质量门禁数据集具有高序列熵和宽泛任务类型，许多有效变体。

2. **评分器校准** — 修复选择失败。修复 oracle 显示有用候选存在（胜率 0.88，腐蚀 0.02），但部署评分器约 88% 的情况无法选择它们。主要失败模式是 edit_oversuppression：edit_penalty 项主导所有其他评分分量。Confidence-regime search 找到 0 个 score-selected deployable regimes，因此这仍是 evaluation-only 诊断问题，不是 production scorer 改动依据。

3. **数据不平衡** — Top10 L3 token 占全部 token 约 75%；94 个 L3 中仅 47 个活跃；长尾算子训练样本极少。

4. **本体缺口** — 10 个未解决的 GEE 官方名称别名；目前已有第一版 bounded offline operator-mapping inventory，但它只暴露 13 条保守 exact GEE<->QGIS 候选，且没有 GDAL/ArcGIS 覆盖；可部署的 semantic repair/equivalence mapping 和组合编辑所需的段边界检测仍未构建。

5. **检索语料库覆盖** — 检索饱和影响某些任务类型；检索池 oracle 增益 (+0.25 LCS) 显著超过局部修复 oracle 增益 (+0.12 LCS)，表明检索语料库本身可以改进。

6. **任务类型稀疏** — 某些任务类型训练样本极少，使得检索和生成在这些类型上都不可靠。

7. **序列级评测灵敏度** — LCS 粗粒度；小而重要的编辑可能无法被注册。需要互补的执行感知和约束满足指标。

8. **架构** — 不是主要瓶颈。V5_final 稳定训练且学习判别（Top5=62%）。判别与生成质量之间的差距主要是解码/评分问题，而非模型容量问题。

### F. 当前研究方向

证据支持的主线是：

**检索中心的工作流规划**，配合**受约束修复**和**选择性干预**，使用**执行感知重排**。

具体而言：
- 检索是结构锚点（词法 + 嵌入 + 图感知融合）。
- V5_final 仅作为完整候选评分器，不是生成器。
- 局部编辑（替换、桥接插入、删除、交换）是修复机制。
- 修复采用需要校准置信度 —— 当前关键的未解决问题。
- 执行感知（I/O 兼容性、算子可行性）约束所有阶段。

这**不是**：
- 从任务文本进行无限制自回归生成。
- 模型自由修改候选的检索增强生成。
- 盲目修复接受。
- 图结构学习或 DAG 恢复。

生产解释：可部署系统是 retrieval + conservative rerank + execution reporting。研究探索可以分析 scorer calibration、repair candidates、retrieval coverage、canonicalization 和 set priors。Oracle evidence 只能估计 headroom，不能作为 runtime capability。

**当前优先级：** 评分器校准诊断。在任何生产评分变更之前，必须测量：AUROC（判别力）、ECE（校准误差）、RCA（修复-置信对齐）、SIR（选择反转率）。目标是找到一个 score-selected 配置，使得修复采用能在可接受腐蚀下产生净正 mean LCS，并在 bootstrap 区间上验证；oracle-only regimes 不足以支持生产改动。

**次要优先级：** Oracle 指标计算（Oracle_ret、Oracle_rank、Oracle_repair）、保留偏置量化、采用-精度曲线分析，以及在任何语义修复工作前人工审查/扩展 bounded ontology inventory。

### G. 当前科学边界

**禁止声明（违反任何一条即该声明无效）：**
1. "系统生成工作流" —— 生成（任务 C）是最弱 formulation。只有检索中心规划（任务 B）有实证支持。
2. "系统理解 GIS 工作流" —— 不存在理解指标。系统检索并修改训练样本。
3. "模型学习工作流结构/图拓扑" —— 无图监督、无 DAG 学习、无拓扑标注。
4. "V5 优于 V4" —— 它们在不同词表上预测不同事物。跨版本声明需要算子序列级指标。
5. "修复有效" —— 部署配置下 C_rep ≈ 0。Oracle 显示有空间，但部署修复贡献可忽略。
6. "评分器已校准" —— 未找到稳定校准。ECE、RCA 尚未测量。

**禁止指标混用：**
1. TF 指标（Top1, PPL, TF-SeqEM）vs AR rollout 指标（TokenAcc, LCS, AR-SeqEM）。
2. V4（L3, 98 类）和 V5（算子, ~150 类）之间的 token 级比较。
3. 将集合级指标（SetF1）包装成序列级证据。
4. 将 oracle 指标报告为部署指标。
5. 将检索中心规划指标报告为生成能力。
6. 未经 200+ 样本 bootstrap 确认就推广 50 样本结果。

**禁止归因洗钱：**
1. 将 C_ret + C_gen 报告为 C_gen（通过包含检索来膨胀生成）。
2. 将 oracle 上限报告为部署能力。
3. 将候选存在包装成选择质量。
4. 将 C_set 改进声明为 C_gen 改进（跨族洗钱）。
5. 将保留偏置（从不选择编辑）包装为"安全保守主义"。
6. 报告修复采用率时省略修复腐蚀率。

### H. 后续会话指南

**给未来 Claude/Codex 会话：**

1. **先读本节**，再解读任何 artifact 或做出声明。治理协议（`v5_master_governance_protocol.md` 等）提供详细归因框架，但本综合文档是权威摘要。

2. **架构已冻结。** 不要提出新模型架构、损失函数、神经模块或训练重设计，除非满足显式重新开启标准。

3. **证据标准具有约束力：**
   - 所有声明需要消融测量（组件 vs 基线）。
   - 所有指标需要留存数据上的 bootstrap 置信区间。
   - 50 样本结果是提示，不是证据。声明至少需要 200+ 样本。
   - Oracle 指标必须标记为"oracle"，且绝不能与部署指标混淆。
   - TF 和 AR 指标必须在不同行/表中报告。

4. **当前合理的实验（仅评测，不训练）：**
   - 评分器质量诊断（AUROC、ECE、RCA、SIR 测量）。
   - 保留偏置量化。
   - 采用-精度曲线分析。
   - 修复候选特征分析（区分好坏修复的因素）。
   - 检索语料库覆盖分析。
   - 从已有 trace 计算 oracle 指标。

5. **当前合理的实验（可涉及训练）：**
   - 通过 `scripts/train_v4_quality_gate.py` 进行 quality-gate Transformer 训练。
   - 通过 `scripts/train_set_predictor_quality_gate.py` 进行 quality-gate Set Predictor 训练。
   - 更大规模 V5_final 训练（Stage2）配合受控消融标志。
   - Beam search 和解码策略评测。

6. **当前不支持的方向（需要新证据才能合理化）：**
   - 新模型架构或训练目标。
   - 图神经网络、DAG 结构学习、拓扑损失。
   - 工作流生成的强化学习。
   - 端到端可微检索。
   - 学习式修复策略（超出评分校准）。
   - 无受控比较的跨任务族多任务学习。

7. **关键 artifact 位置：**
   - 治理：`docs/v5_master_governance_protocol.md`（权威）。
   - 综合协议：`docs/v5_system_consolidation_protocol.md`。
   - 基准：`outputs_v2/v5_final_reports/unified_benchmark/`。
   - 修复 oracle：`outputs_v2/v5_final_reports/repair_oracle_phase/`。
   - 修复诊断：`outputs_v2/v5_final_reports/repair_selection_diagnostics/`。
   - 校准扫描：`outputs_v2/v5_final_reports/repair_calibration_sweep/`。
   - 评分器消融：`outputs_v2/v5_final_reports/repair_scorer_ablations/`。
   - 混合规划器：`outputs_v2/v5_final_reports/v5_hybrid_planner_multistage/`。

8. **更新本文时**，保持综合部分最新：如重新运行则更新基准数据，确认后添加已证明发现，证伪后移除失败路径，证据变化时更新瓶颈排序。除非底层证据变化，否则不要移除科学边界。

## 后续维护协议

每完成一个阶段，必须更新本文和 `docs/PROJECT_CONTEXT.md`：

| 部分 | 要更新什么 |
| --- | --- |
| `已完成工作` | 添加一条带日期的阶段成果 |
| `修改过的文件及原因` | 只记录有长期意义的源码/测试/文档改动 |
| `已踩坑 / 不要重复` | 记录误导信息、失败尝试、排查结论 |
| `验证记录` | 替换为最新命令和结果 |
| `未完成事项` | 移除已完成项，补充阻塞和下一步 |

## 最近工作记录

### 2026-05-23 — Verified MRV 训练数据集选择

已完成：
- 新增共享的 `resolve_mrv_training_dataset()` helper，让训练入口可以显式选择 `outputs_v2/v4_qg_mr_ablation` 下的隔离 MRV 增强 quality-gate 数据版本。
- 给 `scripts/train_v4_6_quality_gate.py` 和 `scripts/train_set_predictor_quality_gate.py` 都接入 `--mrv-ablation-version`，Transformer 和 Set Predictor 训练现在可以直接消费 verified equivalent / safe commutative variants。
- resolver 只信任 `mrv_training_ablation_manifest.json` 和对应版本 report，并会拒绝不满足 train-only、no-oversampling、val/test unchanged guard 的版本。
- 已用真实 `mr_all_42` 验证：两个训练入口都会切到 76,926 workflows，split 为 61,537 train / 7,694 val / 7,695 test，并报告 42 个 verified variants 注入。

修改文件及原因：
- `src/gis_recommend/data/mrv_training_data.py`：新增带 guard 校验的 MRV 数据集 resolver。
- `scripts/train_v4_6_quality_gate.py`：Transformer 训练入口新增可选 MRV 增强数据选择。
- `scripts/train_set_predictor_quality_gate.py`：Set Predictor 训练入口新增可选 MRV 增强数据选择。
- `tests/test_v4_6_training_readiness.py` 和 `tests/test_set_predictor_quality_gate_training_launcher.py`：新增回归测试，确认 launcher 会切到 verified 增强数据且 dry-run 行为不变。

验证记录：
- `python scripts/train_v4_6_quality_gate.py --dry-run --num-epochs 1 --mrv-ablation-version mr_all_42 --length-bucket-loss-weight 0.1` -> OK；报告 42 个 injected variants，并在 61,537 个 train samples 上输出长度分桶摘要。
- `python scripts/train_set_predictor_quality_gate.py --dry-run --num-epochs 1 --mrv-ablation-version mr_all_42` -> OK；报告 42 个 injected variants 和 47 个 active tokens。
- `python -m unittest tests.test_set_predictor_quality_gate_training_launcher tests.test_v4_6_training_readiness tests.test_mrv_training_ablation tests.test_v4_quality_gate_training_launcher tests.test_v4_6_training_stability tests.test_v4_6_training_metrics tests.test_v4_training_entry_smoke -v` -> 41 tests OK。

已踩坑 / 不要重复：
- `mr_all_42` 相比 61,495 个基础 train 样本仍然很小。它是正确的 verified 注入路径，但单靠它还不足以彻底解决监督歧义。
- 不要直接用 `outputs_v2/v4_qg_multiref_validation_expansion_500` 训练，除非其中 variants 已经人工/用户确认并重新构建进带 guard 的 MRV ablation manifest。auto-only plausible variants 不能当训练标签。

未完成事项：
- 下一次服务器训练如果目标是纳入全部当前 verified 等价变体，应使用 `--mrv-ablation-version mr_all_42`。
- 若要显著扩大收益，下一步数据任务应继续扩展已审查 MRV registry，然后重建 `outputs_v2/v4_qg_mr_ablation`。

### 2026-05-23 — V4.6 任务类型长度分桶辅助目标

已完成：
- 将 `outputs_v2/pipeline/step8_quality_gate/task_type_length_stats.json` 接入 V4.6 quality-gate 训练入口，作为任务类型长度分桶摘要和辅助损失来源。
- 新增训练摘要段，dry-run 现在会按 split 报告 short/medium/long 的分桶数量，并展示每个 bucket 的期望长度。
- 在 V4.6 trainer 里加入任务类型分桶辅助损失：通过 `task_type_id -> task_type -> expected length bucket` 映射，在已有的精确长度损失和 AR 长度损失之外再叠加一个小权重 MSE 项。
- 该辅助目标只影响训练，不改 inference、selection、beam、reranker 或 runtime metric 路径。

修改文件及原因：
- `scripts/train_v4_6_quality_gate.py`：新增 `--length-stats` 和 `--length-bucket-loss-weight`，加入长度分桶 dry-run 摘要，并把 predictor 传入 trainer。
- `src/gis_recommend/training/train_v4_6.py`：新增可选任务类型分桶 target/loss 辅助函数，并把加权分桶项并入现有 V4.6 length loss。
- `tests/test_v4_6_training_readiness.py`：补充分桶摘要、缺文件失败和辅助函数行为的回归测试。

验证记录：
- `python -m unittest tests.test_v4_6_training_readiness tests.test_v4_quality_gate_training_launcher tests.test_v4_6_training_stability tests.test_v4_6_training_metrics tests.test_v4_training_entry_smoke -v` -> 27 tests OK。
- `python -m compileall scripts/train_v4_6_quality_gate.py src/gis_recommend/training/train_v4_6.py tests/test_v4_6_training_readiness.py` -> OK。
- `python scripts/train_v4_6_quality_gate.py --dry-run --num-epochs 1 --length-bucket-loss-weight 0.1` -> OK；dry-run 已报告 train/val/test 的 bucket 覆盖和 bucket expected lengths：short=3、medium=5、long=8、very_long=13。

已踩坑 / 不要重复：
- 该 bucket 辅助目标是粗粒度的任务复杂度先验，不是精确长度损失的替代，也不是 rollout 评估替代。
- 只有在传入正的 `--length-bucket-loss-weight` 时 launcher 才会启用长度分桶摘要/损失。直接 Python API 仍会保持旧行为，除非显式传入 predictor 和正权重。

未完成事项：
- 决定下一次训练是使用默认 `0.1` 权重，还是再调小到更保守的值。
- 真正启动训练后，要验证分桶辅助项是否真的缓解短链/长链混淆，而不是只看总 loss。

### 2026-05-23 — P0 Evidence-aware Ranking 校准修复

已完成：
- 修复 `scripts/evaluate_evidence_aware_ranking.py`，离线校准判定现在基于多解任务的主指标，而不是只看 evidence-aware 候选是否不同于 legacy。
- 补回测试使用的脚本级接口：`build_evidence_aware_selection`、`compute_candidate_metrics`、`evaluate_records`、`render_markdown`。
- 保持指标契约：主指标 = SetF1、usable、executable、QGIS mapping；辅助指标 = LCS；TokenAcc 和 Sequence EM 仅作诊断。
- 修复 markdown 输出中 `None` 格式化崩溃，并对 delta mean 做稳定 round，避免浮点尾差。

修改文件及原因：
- `scripts/evaluate_evidence_aware_ranking.py`：仅离线校准脚本；不修改 `pred_tokens`、decoder、beam、reranker、metrics 或 runtime selection。

验证记录：
- `python -m unittest tests.test_evidence_aware_ranking -v` -> 6 tests OK。
- `python -m unittest tests.test_mainline_shadow_phase.P0CalibrationScriptTests -v` -> 3 tests OK。

已踩坑 / 不要重复：
- `outputs_v2/evaluation_reports/empirical_v2_smoke_artifact.json` 是 empirical baseline schema，没有顶层 `per_sample`，不能直接作为 `scripts/evaluate_evidence_aware_ranking.py` 的输入。
- 不要再把“EA 与 legacy 不同”当作 PASS 条件。Evidence-aware ranking 必须在主指标上表现更好；TokenAcc 对 GIS 多解任务只能作为诊断指标。

未完成事项：
- 用真实 planner/evaluation report 运行修复后的校准脚本，该 report 必须包含顶层 `per_sample` 和 `decision_trace.evidence_aware_ranking.comparison_metrics`。
- 下一步实现应直接瞄准真实质量提升：candidate pool 上的语义约束硬过滤或校准排序，并先做离线 A/B 验证，再考虑任何 runtime selection 切换。

### 2026-05-23 — V4.2/V4.6 训练就绪加固

已完成：
- 加固 `scripts/train_v4_6_quality_gate.py`：显式传入 MR registry 后，如果文件缺失会失败；如果 `mr_ratio<=0` 会失败；dry-run 摘要会显示 MR 覆盖情况，避免静默关闭多参考注入。
- V4.6 launcher 新增训练契约摘要，把六个核心问题、训练目标边界和训练后必须验证的指标写进 dry-run 输出。
- V4.6 launcher 新增指标契约摘要：主指标是 `SetF1 / usable / executable / QGIS mapping`，`TokenAcc / Sequence EM` 只能作为诊断指标。
- 保留历史兼容的 latest snapshot 文件名 `best_model.pth`，同时新增只用于训练后观察对比的 `best_gen_set_f1_model.pth` 和 `best_gen_lcs_model.pth`。
- 给 V4.2 quality-gate launcher 也补齐训练/指标/checkpoint 契约摘要，保证两个 transformer 训练入口 dry-run 时都明确多解任务的指标边界。
- 将直接运行 `python -m gis_recommend.training.train_v4_6` 收口为委托 `scripts.train_v4_6_quality_gate.main(argv)`，避免绕过 quality-gate 路径、MR registry 控制和指标契约。

修改文件及原因：
- `scripts/train_v4_6_quality_gate.py`：显式 MR registry gate、训练契约、指标契约、checkpoint policy 摘要。
- `scripts/train_v4_quality_gate.py`：V4.2 quality-gate 入口 dry-run 也输出训练/指标/checkpoint 契约。
- `src/gis_recommend/training/train_v4_6.py`：保留 metric-best snapshot 辅助逻辑；direct module main 改为委托 quality-gate launcher。
- `tests/test_v4_6_training_readiness.py`：覆盖 MR 参数校验、checkpoint policy 分离、direct main 委托。
- `tests/test_v4_quality_gate_training_launcher.py`：覆盖 V4.2 launcher 的主指标/诊断指标契约输出。

验证记录：
- `python -m unittest tests.test_v4_6_training_readiness tests.test_v4_quality_gate_training_launcher tests.test_v4_6_training_stability tests.test_v4_6_training_metrics tests.test_v4_training_entry_smoke -v` -> 24 tests OK。
- `python -m compileall scripts\train_v4_quality_gate.py scripts\train_v4_6_quality_gate.py src\gis_recommend\training\train_v4_6.py tests\test_v4_quality_gate_training_launcher.py tests\test_v4_6_training_readiness.py` -> OK。
- `python scripts\train_v4_6_quality_gate.py --dry-run --num-epochs 1 --mr-registry outputs_v2\v4_qg_multiref_validation\verified_multi_reference_registry_v2.json --mr-ratio 0.5` -> OK；dry-run 显示 76,884 workflows，61,495 / 7,694 / 7,695 split，MR registry 启用，23 个 task groups，当前只匹配 7 个 train samples。

已踩坑 / 不要重复：
- 不要把新增的 `best_gen_*` snapshot 当成替代 `best_model.pth`。`best_model.pth` 仍是 latest-epoch 兼容文件。
- 当前 MR registry 在默认 quality-gate train 上只匹配 7 条样本，因此 `--mr-ratio` 的影响范围很小；不要把这次训练直接解释成充分的 multi-reference 训练。
- 不要把 `TokenAcc` 重新提升为训练成功主指标。GIS workflow 是多解任务，训练后必须用 SetF1 / usable / executable / QGIS mapping 加 P0 ranking 校准判断。

未完成事项：
- 真正启动训练前，明确是否使用 `--mr-registry`/`--mr-ratio`；如果目标是快速稳定 baseline，可以先单参考；如果目标是验证 MR，则需要接受当前 registry 覆盖很小或先扩展 registry。
- 训练完成后必须跑 workflow-level 和 QGIS landing 评测，不能只看 loss、Top1、TokenAcc 或 SeqEM。

### 2026-05-23 — Set Predictor 训练就绪加固

已完成：
- 给 Set Predictor quality-gate 训练入口新增可选 MR registry 支持。对匹配到 registry 的训练任务，binary/count targets 现在使用 verified equivalent references 的 operator-set union，等价算子不会再被当成 absent target。
- active token discovery 支持纳入 MR variant tokens。当前默认 quality-gate 数据上，MR 没有新增 active token，因为 variant token 已经在 47 个 active tokens 中。
- `compute_pos_weight` 现在和 Dataset target 使用同一套 MR-union 正样本语义，避免启用 MR 后 BCE 正样本权重仍按单参考计算。
- Set Predictor 训练现在保留 `best_model.pth` 作为 latest-epoch 兼容快照，同时额外保存 `best_set_f1_model.pth` 和 `best_topk_recall5_model.pth`；manifest 推荐 `best_topk_recall5_model.pth`，因为 coverage recall 更贴近 coverage-prior 职责。
- Set Predictor dry-run 新增角色契约：它只负责 coverage prior，不负责 candidate ranking、sequence generation 或 semantic validation。
- 直接运行 `python -m gis_recommend.training.train_set_predictor_v3` 现在委托到 `scripts.train_set_predictor_quality_gate.main(argv)`，避免误用旧默认路径训练。

修改文件及原因：
- `src/gis_recommend/training/train_set_predictor_v3.py`：MR-aware active-token discovery、MR-union target、MR-aware `compute_pos_weight`、direct main 委托。
- `scripts/train_set_predictor_quality_gate.py`：新增 `--mr-registry`、MR 摘要、训练/指标/checkpoint 契约，并把 MR registry 传入 train dataset 和 pos_weight 计算；新增 metric-best checkpoint snapshots。
- `tests/test_set_predictor_quality_gate_training_launcher.py`：覆盖 MR target union、缺失 registry fail-fast、dry-run 指标契约、direct-main 委托、metric-best checkpoint 分离。

验证记录：
- `python -m unittest tests.test_set_predictor_quality_gate_training_launcher tests.test_v4_6_training_readiness tests.test_v4_quality_gate_training_launcher tests.test_v4_6_training_stability tests.test_v4_6_training_metrics tests.test_v4_training_entry_smoke -v` -> 32 tests OK。
- `python -m compileall scripts\train_set_predictor_quality_gate.py src\gis_recommend\training\train_set_predictor_v3.py tests\test_set_predictor_quality_gate_training_launcher.py` -> OK。
- `python scripts\train_set_predictor_quality_gate.py --dry-run --num-epochs 1 --mr-registry outputs_v2\v4_qg_multiref_validation\verified_multi_reference_registry_v2.json` -> OK；dry-run 显示 76,884 workflows，61,495 / 7,694 / 7,695 split，47 active tokens，MR 启用，23 groups，7 matched train samples，variant_active_tokens_added 为空。

已踩坑 / 不要重复：
- 这不是把 Set Predictor 变成 ranker 或 semantic validator。它仍然只是 coverage prior；训练后必须看 Planner 级 selected set coverage、selected_top1_usable_rate 和 QGIS mapping。
- 当前 MR 覆盖很小，只匹配 7 条 train samples。代码路径已修正，但现有数据覆盖限制了预期收益。

### 2026-05-23 — 自动多解候选挖掘与人工抽检闭环

已完成：
- 重写 `scripts/build_multisolution_candidates.py`，形成离线、只读 train split 的自动多解候选挖掘工具。
- 工具只在相同 `task_type` 内召回候选，并计算 multiset SetF1、LCS ratio、长度差、task 文本 Jaccard。相同 `task_type` 只是召回条件，不是等价证明。
- 新增 review bucket：`high_precision_review_candidate`、`boundary_review_candidate`、`auto_rejected_control`。
- 人工 review sheet 支持按 task_type 限额抽样，并可混入 rejected control，用来估计误报/漏报风险。
- 新增 `scripts/build_multisolution_registry_from_review.py`：只把人工标注为 `equivalent` 或 `verified_equivalent` 的行晋升为 v3 registry/KB；空标签、uncertain、not_equivalent 全部 excluded，不能进入训练标签。

真实数据产物：
- 保守正式版：`outputs_v2/v4_qg_multisolution_candidates/`
  - 扫描 train samples: 61,495
  - 总候选对: 20,227
  - 待审候选: 279
  - 人工表: 291 行 = 237 boundary + 4 high precision + 50 rejected controls
  - 用未填写人工标签的 review sheet 跑 v3 registry builder，结果为 0 equivalent、291 excluded，证明不会把未审候选误放进训练。
- 放宽探测版：`outputs_v2/v4_qg_multisolution_candidates_relaxed_probe/`
  - 总候选对: 37,534
  - 待审候选: 1,510
  - high precision: 80
  - review packet: 700 行

修改文件及原因：
- `scripts/build_multisolution_candidates.py`：自动候选生成、review bucket、rejected-control 抽检、报告输出。
- `scripts/build_multisolution_registry_from_review.py`：人工确认后的 v3 registry/KB 安全构建器。
- `tests/test_multisolution_candidate_generation.py`：覆盖 train-only、阈值拒绝、分层抽样、rejected control、review bucket。
- `tests/test_multisolution_registry_from_review.py`：覆盖只有人工 equivalent 才能入库，空标签不会被接受。

验证记录：
- `python -m unittest tests.test_multisolution_candidate_generation tests.test_multisolution_registry_from_review tests.test_mrv_training_ablation -v` -> 12 tests OK。
- `python -m compileall scripts\build_multisolution_candidates.py scripts\build_multisolution_registry_from_review.py tests\test_multisolution_candidate_generation.py tests\test_multisolution_registry_from_review.py` -> OK。
- 已在 quality-gate train split 上完成保守版和放宽 probe 的真实数据运行。

已踩坑 / 不要重复：
- 自动生成的 candidate row 不是训练标签。只有人工填写后，经 v3 registry builder 生成的 registry/KB 才能进入 MRV ablation。
- 同 task_type + 高 token overlap 仍可能混入非等价任务，例如同一个大气/海洋任务族下目标变量不同。人工 review 不能省。
- 保守阈值更精准但产量低；放宽阈值能扩容，但必须用 rejected control 和分层抽检控制噪声。

未完成事项：
- 先人工审查保守版 `candidate_review_sheet.csv`。如果接受率高，再审查 relaxed probe 的 high-precision 行。
- 人工审查后运行 `scripts/build_multisolution_registry_from_review.py`，再把生成的 v3 registry/KB 传给 `scripts/build_mrv_training_ablation.py`，构建更大的 MR 训练 ablation 数据集。

### 2026-05-23 — 多解审查结果已晋升为 MR 训练派生集

已完成：
- 核验人工审查文件 `outputs_v2/v4_qg_multisolution_candidates/candidate_review_sheet_ai_reviewed.csv`。
- 标签统计为：178 条 `equivalent`、63 条 `not_equivalent`、50 条空标签 rejected-control。
- equivalent 覆盖 39 个 task type；非 control 审查行共 241 条，接受率 73.86%。
- 用审查表生成 v3 registry/KB：`outputs_v2/v4_qg_multisolution_candidates/verified_registry_v3/`。
- 将历史 v2 MRV registry 的 42 条 equivalent 和新增 v3 registry 的 178 条 equivalent 合并为 v4：`outputs_v2/v4_qg_multisolution_candidates/merged_registry_v4/`。
- 已生成隔离 MR 训练派生集：`outputs_v2/v4_qg_mr_ablation_from_multisolution/mr_all_220/`。

关键计数：
- v3 registry：178 条 equivalent variants，156 个 task groups，113 条 excluded variants。
- 合并 v4 registry/KB：220 条 equivalent variants，179 个 registry groups，220 条 KB rows。
- `mr_all_220` ablation 数据集：base workflows 76,884 -> output workflows 77,104；train 61,495 -> 61,715；val 7,694 不变；test 7,695 不变；相对 base train 注入率 0.00357753。

修改文件及原因：
- `scripts/merge_multisolution_registries.py`：合并 v2/v3 registry 和真实 KB rows，保留 `variant_tokens`，确保 `build_mrv_training_ablation.py` 能真正注入样本。
- `tests/test_multisolution_registry_merge.py`：覆盖合并计数和 KB `variant_tokens` 保留。

验证记录：
- `python scripts\build_multisolution_registry_from_review.py --review-csv outputs_v2\v4_qg_multisolution_candidates\candidate_review_sheet_ai_reviewed.csv --output-dir outputs_v2\v4_qg_multisolution_candidates\verified_registry_v3` -> 178 equivalent variants。
- `python scripts\merge_multisolution_registries.py ... --output-dir outputs_v2\v4_qg_multisolution_candidates\merged_registry_v4` -> 220 equivalent variants。
- `python scripts\build_mrv_training_ablation.py --registry outputs_v2\v4_qg_multisolution_candidates\merged_registry_v4\verified_multi_reference_registry_v4.json --kb outputs_v2\v4_qg_multisolution_candidates\merged_registry_v4\verified_equivalence_kb_v4.json --out-dir outputs_v2\v4_qg_mr_ablation_from_multisolution --subset-sizes all` -> `mr_all_220: injected=220 train=61715 val=7694 test=7695`。
- `python -m unittest tests.test_multisolution_candidate_generation tests.test_multisolution_registry_from_review tests.test_multisolution_registry_merge tests.test_mrv_training_ablation -v` -> 14 tests OK。
- `python -m compileall scripts\build_multisolution_candidates.py scripts\build_multisolution_registry_from_review.py scripts\merge_multisolution_registries.py tests\test_multisolution_candidate_generation.py tests\test_multisolution_registry_from_review.py tests\test_multisolution_registry_merge.py` -> OK。

已踩坑 / 不要重复：
- `mr_all_220` 相比 61,495 条 train 仍然是小比例注入，但已经明显大于 `mr_all_42`，且覆盖更多 task type。
- 新 registry 适合做受控训练 ablation，不代表以后所有 auto-mined candidates 都能自动进训练；仍必须先有人类标签。

未完成事项：
- 下一轮 Transformer 和 Set Predictor 训练 dry-run / 服务器训练应使用 `outputs_v2/v4_qg_mr_ablation_from_multisolution/mr_all_220/`。

---

### 2026-06-04 — DPO v2 + QGIS landing 阶段总结

已完成：
- DPO v2 模型训练完成：beam top-1 usable 从 59.9% → 99.1%（3000 test），100% FINAL usable（beam_usable_quality策略）。
- QGIS Chain Retriever + Evaluator 构建：200-probe 100% combined bridge，0.995 avg quality。
- QGIS chain dataset 构建：D1 合并去重 54k 脚本中提取 3021 条多步处理链。
- 18 条人工审查 QGIS→L3 crosswalk 映射已合并，L3 bridge 覆盖率 12.3% → 24.8%。
- QGIS 检索索引修复：facts_summary 文本合并入链记录，recall 0.5% → 100%（self-retrieval），op-masked仍99.6% R@1。
- GRPO headroom 诊断完成：0% worth training，当前 DPO 模型 beam 多样性不足，不适合 GRPO。
- 端到端流水线验证：L3 规划 + QGIS landing 在 3000 测试集上达到 100% QGIS chain 有效性。

关键决策：
- 冻结 DPO v2 L3 模型作为遥感/栅格规划基座。
- 使用修复后的 QGIS retriever 做 landing 层主路径。
- 不再在 L3 模型上继续投入 RL 优化；资源投入 QGIS landing 层和 L3→QGIS bridge 扩展。

产出文件：
- `outputs_v2/qgis_chain_dataset_v2_enriched_v3.jsonl`：含 facts 文本的增强链数据集。
- `outputs_v2/qgis_chain_dataset_v2.jsonl`：去重后的 QGIS 链候选池（2319 条）。
- `src/gis_recommend/planning/qgis_chain_planner.py`：QGIS Chain Retriever + Evaluator。
- `scripts/enrich_qgis_chain_dataset_v2.py`：v2 候选池增强脚本。
- `scripts/build_retrieval_eval.py`：检索 recall 评估脚本。
- `scripts/train_qgis_retrieval_reranker.py`：检索对齐 reranker 训练脚本。
- 训练后必须和 baseline、`mr_all_42` 对比主指标：SetF1、usable、executable、QGIS mapping；TokenAcc / SeqEM 仍只能作诊断。

### 2026-05-24 — 统一多解 registry 与 mr_all_1257

已完成：
- 从四类已批准来源构建 unified verified multi-solution registry：
  - `manual_mrv_v2`: 42
  - `structural_equivalence_conservative`: 178
  - `structural_equivalence_relaxed`: 406
  - `local_filter_swap_sampled`: 631
- 说明：当前文件事实是 `combined_equivalents.csv = 584 = 178 conservative + 406 relaxed-only`，不是 `66 + 518`；但总计和仍然是 1,257。
- 生成统一 registry/KB 到 `outputs_v2/v4_qg_multisolution_unified_registry_v1/`。
- 生成训练派生集 `outputs_v2/v4_qg_mr_ablation_from_multisolution_unified/mr_all_1257/`。

关键计数：
- unified registry：1,257 条 equivalent variants，660 个 registry groups。
- `mr_all_1257`：base workflows 76,884 -> output workflows 78,141；train 61,495 -> 62,752；val 7,694 不变；test 7,695 不变。
- 注入率：0.02044069。

修改文件及原因：
- `scripts/build_unified_multisolution_registry.py`：把 MRV v2、结构等价 CSV、sampled filter swaps 合并成一个保留 source_family 的统一 registry/KB。
- `tests/test_unified_multisolution_registry.py`：覆盖 source_family 计数、CSV 嵌套 token 解析和 KB token 保留。

验证记录：
- `python scripts\build_unified_multisolution_registry.py --mrv-registry outputs_v2\v4_qg_multiref_validation\verified_multi_reference_registry_v2.json --mrv-kb outputs_v2\v4_qg_multiref_validation\verified_equivalence_kb_v2.json --conservative-csv outputs_v2\v4_qg_multisolution_candidates\candidate_review_sheet_ai_reviewed.csv --structural-csv outputs_v2\v4_qg_multisolution_candidates_relaxed_probe\combined_equivalents.csv --filter-swap-csv outputs_v2\safe_swap_candidates_v1\sampled_filter_swaps_1000.csv --output-dir outputs_v2\v4_qg_multisolution_unified_registry_v1` -> 1,257 variants。
- `python scripts\build_mrv_training_ablation.py --registry outputs_v2\v4_qg_multisolution_unified_registry_v1\verified_multi_reference_registry_unified.json --kb outputs_v2\v4_qg_multisolution_unified_registry_v1\verified_equivalence_kb_unified.json --out-dir outputs_v2\v4_qg_mr_ablation_from_multisolution_unified --subset-sizes all` -> `mr_all_1257: injected=1257 train=62752 val=7694 test=7695`。
- `python -m unittest tests.test_unified_multisolution_registry tests.test_mrv_training_ablation tests.test_mrv_training_data -v` -> 7 tests OK。
- `python -m compileall scripts\build_unified_multisolution_registry.py tests\test_unified_multisolution_registry.py` -> OK。

已踩坑 / 不要重复：
- `build_mrv_training_ablation.py` 的 report 里仍写着泛化来源名 `verified_mrv_registry_v2_and_equivalence_kb_v2`；对 `mr_all_1257`，应以上游 unified registry 的 `source_family_counts` 作为真实 provenance。
- `local_filter_swap_sampled` 只教局部顺序不敏感，不要和结构等价的收益混为一谈。

未完成事项：
- 训练/评测时把 `mr_all_1257` 和 baseline、`mr_all_42`、`mr_all_220`、以及需要时的 `mr_all_738` 分开比较。
- 结果解释必须按规模和 source mix 分层，不能把结构等价收益和 filter swap 收益混成一个因果结论。

### 2026-05-24 — 统一多解 registry v2 与 mr_all_1841

已完成：
- 核验最终高置信多解数据组成：
  - `manual_mrv_v2`: 42
  - `structural_equivalence`: 584
  - `local_filter_swap_sampled`: 1,215
- 确认 `outputs_v2/unified_multisolution_registry/unified_equivalents_v1.csv` 本身是 1,799 条，不包含 MRV v2 的 42 条；1,799 + 42 = 1,841。
- 确认 93 条 `needs_review` 的 select/filter/clip 候选没有进入 `unified_equivalents_v1.csv`；已入库 local swaps 均为 `tier=auto_verified` 且 `swap_type=filter<>filter`。
- 生成 registry/KB 到 `outputs_v2/v4_qg_multisolution_unified_registry_v2/`。
- 生成隔离训练派生集 `outputs_v2/v4_qg_mr_ablation_from_multisolution_unified_v2/mr_all_1841/`。

关键计数：
- Registry v2：1,841 条 equivalent variants，660 个 registry groups。
- `mr_all_1841`：base workflows 76,884 -> output workflows 78,725；train 61,495 -> 63,336；val 7,694 不变；test 7,695 不变。
- 相对 base train 注入率：0.02993739。

修改文件及原因：
- `scripts/build_unified_multisolution_registry.py`：新增 `--unified-equivalents-csv` 入口，可读取预合并 reviewed-equivalents CSV，保留 source-family provenance，并过滤掉非 `auto_verified` / 非 `filter<>filter` 的 local swap 行。
- `tests/test_unified_multisolution_registry.py`：覆盖 unified CSV ingestion 路径，并验证 `needs_review` select/filter 候选不会进入 registry。

验证记录：
- `python scripts\build_unified_multisolution_registry.py --unified-equivalents-csv outputs_v2\unified_multisolution_registry\unified_equivalents_v1.csv --output-dir outputs_v2\v4_qg_multisolution_unified_registry_v2` -> 1,841 variants。
- `python scripts\build_mrv_training_ablation.py --registry outputs_v2\v4_qg_multisolution_unified_registry_v2\verified_multi_reference_registry_unified.json --kb outputs_v2\v4_qg_multisolution_unified_registry_v2\verified_equivalence_kb_unified.json --out-dir outputs_v2\v4_qg_mr_ablation_from_multisolution_unified_v2 --subset-sizes all` -> `mr_all_1841: injected=1841 train=63336 val=7694 test=7695`。
- `python -m unittest tests.test_unified_multisolution_registry tests.test_mrv_training_ablation tests.test_mrv_training_data -v` -> 8 tests OK。
- `python -m compileall scripts\build_unified_multisolution_registry.py tests\test_unified_multisolution_registry.py` -> OK。

已踩坑 / 不要重复：
- 不要把 round-2 expansion 的原始总数直接当成 verified training data。93 条 `needs_review` select/filter/clip 行仍然是挂起状态。
- `unified_equivalents_v1.csv` 是 1,799 条是正常现象，因为 MRV v2 仍保留在自己的 source registry/KB 中；合并后正确训练计数是 1,841。

未完成事项：
- `outputs_v2/v4_qg_mr_ablation_from_multisolution_unified_v2/mr_all_1841/` 应作为较小 ablation 出现正向后再使用的下一轮高置信规模扩展。
- 训练对比仍需按规模和 source mix 分层：baseline、`mr_all_42`、`mr_all_220`、`mr_all_1257`、`mr_all_1841`。

### 2026-05-24 — 多解数据之后的训练阶段优化路线

当前状态：
- 服务器侧 Transformer / Set Predictor ablation 正在跑或准备跑：baseline、`mr_all_42`、`mr_all_220`、`mr_all_1257`。
- 在这些实验结果出来前，不要继续盲目扩充多解数据。先闭合评测，看数据规模是否真的带来正向变化。

决策：
- 后续优化仍围绕最初六个问题，但从“继续造数据”转向训练目标和评测闭环：
  1. Multi-solution：保持 source-family 分层 ablation；只有当较小规模呈正向时，才使用 `mr_all_1841`。
  2. Workflow Complexity：把 `outputs_v2/pipeline/step8_quality_gate/task_type_length_stats.json` 接入训练摘要和辅助目标，增加短/中/长链或 task-type length-bucket 目标；按 task type / bucket 监控 early END 和过长输出。
  3. Generation Instability：让验证更接近推理，加入 constrained AR rollout validation 和 invalid-transition 诊断；不能只看训练 loss。
  4. Evaluation Misalignment：best checkpoint selection 应优先使用 workflow-level validation metrics：SetF1、usable、executable、QGIS mapping，LCS 辅助；TokenAcc / SeqEM 只作诊断。
  5. Ranking Problem：等 ablation 结果出来后，用 candidate pool 构造有监督候选排序数据；multi-reference / usable / oracle-best 候选作为正样本，invalid / 低 utility 候选作为负样本。
  6. Semantic Constraint：先加入轻量训练期辅助信号，例如 QGIS mapping availability、transition / IO compatibility，再考虑更重的 ontology / KG authority。

立即优先级：
- 监控当前训练是否出现 `nan` / `inf`、AR collapse、early-EOS 过高、invalid transition 过高、checkpoint 保存逻辑异常。
- 准备统一 post-training evaluation，把 baseline、`mr_all_42`、`mr_all_220`、`mr_all_1257` 放在同一套主指标下比较。
- 然后优先实现 P1/P2：workflow 指标驱动的 checkpoint selection，以及长度/复杂度辅助训练信号。

已踩坑 / 不要重复：
- 不要用 CE loss、TokenAcc 或 SeqEM 单独判断训练成败。GIS workflow 是多解任务，精确 token 匹配可能和 workflow usability 方向相反。
- 不要混淆 source-family 效果。结构等价教的是 alternate solutions；local filter swap 主要教的是局部顺序不敏感。

### 2026-05-26 — Workflow Complexity 评测闭环补全

已完成：
- `scripts/evaluate_v4_quality_gate.py` 新增 complexity bucket rollout diagnostics。
- 评测报告现在会按 `task_type_length_stats.json` 的短链 / 中链 / 长链 / 超长链 bucket 分层输出。
- 每个 bucket 输出样本数、reference 平均长度、prediction 平均长度、长度比、early-EOS 率、过长输出率、SetF1、LCS、TokenAcc。
- `scripts/evaluate_checkpoint_epochs.py` 会把 long / very_long 的长度比和 early-EOS 诊断带入 checkpoint ranking JSON/Markdown，方便判断 length-bucket 训练是否真的改善长链任务。

决策：
- 复杂度建模不能只看训练侧加了 length-bucket loss 就算完成，必须通过 bucket-level rollout diagnostics 验证，重点看 `long_early_eos_rate`、`very_long_early_eos_rate` 和长度比。
- TokenAcc 仍然只作诊断，不作为 workflow 正确性主指标；模型比较仍以 SetF1/LCS 加 workflow usability/QGIS/executable 指标为主。

验证记录：
- `python -m unittest tests.test_v4_qg_evaluation_report -v` -> 5 tests OK。
- `python -m unittest tests.test_v4_6_training_stability -v` -> 4 tests OK。
- `python -m compileall scripts\evaluate_v4_quality_gate.py scripts\evaluate_checkpoint_epochs.py tests\test_v4_qg_evaluation_report.py` -> OK。

### 2026-05-26 — 服务器 ablation 结果初步读取

已查看 artifact：
- Transformer 日志：`结果/transformer训练结果/0526/{baseline,mr_all_42,mr_all_220,mr_all_1257}.md`。
- Set Predictor 日志：`结果/train_set_predictor结果/0526/{baseline,mr_all_42,mr_all_220,mr_all_1257}.md`。

初步事实：
- 四组 Transformer 都完成 50 epoch，未观察到旧版 `nan` / `inf` loss 崩溃。
- Transformer latest-checkpoint test 指标没有显示多解数据规模正相关：baseline AR-LCS / SetF1 = 0.433 / 0.565；`mr_all_42` = 0.423 / 0.544；`mr_all_220` = 0.424 / 0.548；`mr_all_1257` = 0.421 / 0.557。
- `mr_all_1257` 虽然 TF loss 略低，但 rollout 长度/噪声诊断比 baseline 更差：pred length 10.5 vs 9.4，len error 5.0 vs 4.0，earlyEOS 7.8% vs 4.7%，bad transitions 44.6% vs 30.9%。
- Set Predictor 基本持平；`mr_all_220` 有最小正向信号，best F1@0.70 = 0.715、best Top5 recall = 0.675；baseline 为 0.713 / 0.673。

解释边界：
- 暂时不要继续扩到 `mr_all_1841`。当前证据不支持“更大 MR 注入能提升 Transformer AR rollout”。
- 下一步应评估保存下来的 best snapshots（Transformer 的 `best_gen_set_f1_model.pth` / `best_gen_lcs_model.pth`，Set Predictor 的 `best_topk_recall5_model.pth`），并跑 workflow-level/QGIS/executable 评测，而不是继续扩数据。

### 2026-05-26 — 训练评估契约修复

已完成：
- `scripts/evaluate_checkpoint_epochs.py` 现在除了 epoch checkpoint，也会评估命名选择快照：`best_model.pth`、`best_gen_set_f1_model.pth`、`best_gen_lcs_model.pth`、`best_gen_composite_model.pth`。
- `scripts/evaluate_v4_quality_gate.py` 的 `eval_config` 现在记录实际传入 inference 的 Transformer checkpoint 和 Set Predictor checkpoint，不再总是写默认 `best_model.pth`。
- `src/gis_recommend/training/train_v4_6.py` 最终 test generation evaluation 至少使用 16 batch，不再硬编码 4 batch。
- `src/gis_recommend/training/train_v4_2.py` 新增 `count_invalid_transitions()`，unknown transition source state 现在会计入 invalid transition 诊断，不再静默跳过。

验证记录：
- `python -m unittest tests.test_v4_6_training_stability -v` -> 5 tests OK。
- `python -m unittest tests.test_v4_qg_evaluation_report -v` -> 6 tests OK。
- `python -m compileall src\gis_recommend\training\train_v4_2.py src\gis_recommend\training\train_v4_6.py scripts\evaluate_v4_quality_gate.py scripts\evaluate_checkpoint_epochs.py tests\test_v4_qg_evaluation_report.py tests\test_v4_6_training_stability.py` -> OK。

未完成要求：
- 2026-05-26 服务器 ablation 日志只能作为 noisy/latest-checkpoint 诊断看待。必须用更新后的 checkpoint/workflow 评估脚本重新评估服务器 checkpoint，才能判断 MR 与 baseline 的真实差异。

### 2026-05-27 — 离线 ExecutionAwareSelector 审核与口径修正

已完成：
- 在接入 runtime 前审核并修正了新的离线 `ExecutionAwareSelector` 路径。
- `src/gis_recommend/planning/execution_aware_selector.py` 现在把 unknown transition source state 计为 invalid，与 `count_invalid_transitions()` 保持一致；`select_from_pool()` 不再重排调用方传入的候选列表；重复率统计也做了简化。
- `scripts/evaluate_execution_aware_selector.py` 现在复用 `evaluate_workflow_usability.py` 中已有的 `UsabilityEvaluator` 作为主可用性标签，不再使用漂移的简化规则。
- Oracle pool usable 现在按完整候选池计算，不再只看 selector 截断后的 top-k。
- 新增 `tests/test_execution_aware_selector.py`，覆盖 no-mutation、unknown transition 诊断、full-pool oracle accounting。

关键结果：
- 之前 20 样本的 `retrieval 45% / selector 40% / oracle 80%` 不可靠，原因是评估脚本使用了与项目 v2 evaluator 不一致的简化 usability 规则，并且 oracle 只在截断 top-k 上计算。
- 修正口径后重跑：
  - 20 样本：retrieval top-1 usable 85.0%，selector top-1 usable 80.0%，oracle pool usable 100.0%。
  - 200 样本：retrieval top-1 usable 66.5%，selector top-1 usable 81.0%，oracle pool usable 99.0%。
- 当前解释：规则版 selector 在线下是有效的，200 样本上明显优于 retrieval top-1；但 selector 81% 到 oracle 99% 仍有大空间。下一步应做 learned / calibrated reranker，不要在 beam 和更大 trace 验证前接入 runtime。

产物：
- `outputs_v2/diagnostics/execution_aware_selector_reviewed/`
- `outputs_v2/diagnostics/execution_aware_selector_reviewed_200/`

验证记录：
- `python -m unittest tests.test_execution_aware_selector tests.test_v4_6_training_stability tests.test_v4_qg_evaluation_report -v` -> 15 tests OK。
- `python -m compileall src\gis_recommend\planning\execution_aware_selector.py scripts\evaluate_execution_aware_selector.py tests\test_execution_aware_selector.py` -> OK。

### 2026-05-27 — Learned Reranker 1k 离线探针

已完成：
- 重新生成带完整 `pool_candidates` trace 的 1,000 样本 selector 报告：`outputs_v2/diagnostics/execution_aware_selector/1k_samples/`。
- 使用 `scripts/train_learned_reranker.py` 训练当前 pairwise logistic-regression reranker，输出 `outputs_v2/reranker_learned_weights_v1.json`。

观察事实：
- Selector report：1,000 个 query group、10,000 个 candidate，candidate pool 缺失为 0。
- `UsabilityEvaluator` 伪标签：6,427 个 usable candidate、3,573 个 unusable candidate。
- Query group 分布：991 个池内至少有一个 usable candidate，95 个全候选 usable，896 个 usable/unusable 混合组。
- 1k 报告上的规则 selector：retrieval top-1 usable 65.8%，selector top-1 usable 81.2%，oracle pool usable 99.1%。
- Learned LR 切分：800 train queries / 200 test queries；pairwise 训练样本 27,560。
- Held-out 结果：learned Top-1 usable 84.8%，同一测试子集上的规则 baseline 约 83.3%；MRR 0.9118 vs 0.8964；增量为 Top-1 +1.5pp / MRR +0.0154。
- 保存后的权重在全部 1,000 组上评估：Top-1 usable 84.0%，MRR 0.9064。

解释边界：
- Learned reranking 方向是正的，但还不是大突破。1k 上可靠增益很小，不能沿用 50 样本 +10pp 的乐观判断。
- 当前权重仍有校准风险：`early_eos_risk` 是较大的正权重，`transition_validity`、`set_predictor_coverage`、`candidate_source` 基本为 0。不要直接接入 runtime。
- 下一步更有价值的是 feature/label 校准和跨 seed 验证，而不是继续微调 Transformer。

### 2026-05-27 — Learned Reranker v2 长度特征校准

已完成：
- `ExecutionAwareSelector` 的 `early_eos_risk` 改为只在低于 task-type P10 长度时触发：`max(0, (p10 - n) / p10)`。
- `length_bucket_fit` 继续作为 P10/P90 范围内奖励。
- `scripts/train_learned_reranker.py` 现在执行 C-sweep `[0.03, 0.1, 0.3, 1.0]`，跨 seeds `[42, 123, 456]`；保存 `selected_C`；并明确 all-groups 指标是最终全量 refit 后的 in-sample diagnostic。
- 新增回归测试，证明合理短链只要在 P10/P90 内就不会触发 `early_eos_risk`。

观察事实：
- 重新生成 `outputs_v2/diagnostics/execution_aware_selector/1k_v2/`：retrieval top-1 usable 65.8%，规则 selector 82.4%，oracle pool 99.1%。
- 仅 early-EOS 特征校准就让规则 selector 从 81.2% 提升到 82.4%。
- `early_eos_risk` 现在非常稀疏：10,000 个候选中 156 个非零，均值 0.00396。
- Learned v2 C-sweep：C=0.03 mean top-1 83.7% (std 3.7%)，C=0.1 83.7% (std 3.3%)，C=0.3 84.1% (std 3.6%)，C=1.0 84.1% (std 3.6%)。最终选择 C=0.3。
- 最终全量 refit 权重：qgis_mapping +5.2606，io_compat +5.6982，length_bucket_fit +1.1699，repetition -1.1213，early_eos +0.2872，model_logprob -0.1459；transition/set/source 仍为 0，因为 retrieval-only 候选池中这些特征没有有效方差。
- 最终 all-groups diagnostic：learned 83.6% Top-1 / 0.9037 MRR，相比规则 baseline 只 +0.4pp / +0.0020。该指标是 in-sample diagnostic，不是 held-out 泛化。

解释边界：
- 真正有用的收益来自规则特征修正，而不是 LR 本身。当前 calibrated rule selector 是更稳的实用候选。
- 当前 learned reranker 还不支持接入 runtime。下一步如果继续，应优先加入新的方差信号，例如 Set Predictor coverage 或 beam candidates，而不是继续调 LR。

验证记录：
- `python -m unittest tests.test_execution_aware_selector -v` -> 5 tests OK。
- `python -m compileall src\gis_recommend\planning\execution_aware_selector.py scripts\train_learned_reranker.py tests\test_execution_aware_selector.py` -> OK。

### 2026-05-27 — Beam + Set Predictor Selector Smoke

已完成：
- 修正 `scripts/evaluate_execution_aware_selector.py`：`--use-beam` 默认读取 V4.6 quality-gate Transformer 目录，不再误用非 QG 的 `outputs_v2/transformer_checkpoints_v4_6`。
- 修正 Set Predictor 默认路径为 `outputs_v2/set_predictor_checkpoints_v3_quality_gate_v4_6/best_model.pth`；旧代码查的是过期 `outputs_v2/set_predictor_checkpoints_v3`，会静默变成 without set-prior constraints。
- 新增 `--set-predictor-checkpoint`，方便离线评估显式覆盖。
- per-sample beam inference 异常不再静默吞掉，现在会打印并写入 `beam_error`。
- `L3SequenceInferencerV4` 通过 `last_token_prior` 暴露最近一次 soft token prior；selector 评估会把它传给 `ExecutionAwareSelector`，所以 `set_predictor_coverage` 不再一直是 0.5 中性值，而是有真实方差。

观察事实：
- 默认 `--use-beam` 现在能用 quality-gate 47-type task vocabulary 严格加载 epoch 43 的 `best_gen_set_f1_model.pth`。
- V4.6 QG Set Predictor 成功加载，active tokens 为 47。
- 20 样本 beam+SP smoke，并把 Set Predictor prior 接入 selector 后：retrieval top-1 usable 85.0%，beam top-1 usable 70.0%，selector top-1 usable 90.0%，oracle pool usable 100.0%。
- 这只是 smoke 结果，只证明路径接通和特征开始有方差，不是生产质量结论。更大样本建议放服务器跑；本地 CPU beam 解码约 19-20 秒/样本。

产物：
- `outputs_v2/diagnostics/execution_aware_selector/beam_sp_prior_smoke_2/`
- `outputs_v2/diagnostics/execution_aware_selector/beam_sp_prior_smoke_20/`

验证记录：
- `python -m compileall scripts\evaluate_execution_aware_selector.py src\gis_recommend\inference\infer_l3_candidates_v4.py` -> OK。
- `python -m unittest tests.test_execution_aware_selector tests.test_v4_6_training_stability tests.test_v4_qg_evaluation_report -v` -> 16 tests OK。
- `python scripts\evaluate_execution_aware_selector.py --num-samples 2 --use-beam --output-dir outputs_v2\diagnostics\execution_aware_selector\beam_sp_prior_smoke_2` -> strict checkpoint load OK，Set Predictor load OK。
- `python scripts\evaluate_execution_aware_selector.py --num-samples 20 --use-beam --output-dir outputs_v2\diagnostics\execution_aware_selector\beam_sp_prior_smoke_20` -> selector smoke 完成。

### 2026-05-28 — V4.6 Preference Fine-Tuning 脚手架

已完成：
- `scripts/evaluate_execution_aware_selector.py` 新增 `--split train|val|test`，默认仍是 test。报告现在写入 `split`、`sample_index` 和完整 `task_metadata`，便于把 train/val trace 转成训练数据，同时避免误用 test 训练。
- 新增 `scripts/build_generation_preferences.py`。它读取 `selector_report.json`，按候选来源过滤（默认 `beam`），在同一个 task 内选择 usable / 高 reward 的正样本和低 reward 负样本，输出 JSONL preference pairs。
- 新增 `scripts/train_v4_6_preference.py`，作为独立 DPO 后训练入口。它严格恢复 V4.6 checkpoint，冻结一份 reference model，训练 policy model，loss 为 `-logsigmoid(beta * ((logP_pos-logP_neg)_policy - (logP_pos-logP_neg)_ref))`，并对正样本加小权重 CE anchor。
- 新增 `tests/test_generation_preference_pipeline.py`，覆盖 split 选择、beam-only pair 构造、JSONL 输出、候选序列准备、masked mean log-probability 和 DPO loss 方向。

观察事实：
- 现有 1k test selector trace 可以生成 1,174 条 beam preference pairs，但这只能用于诊断；正式训练必须重新用 `--split train` 和 `--split val` 生成 trace。
- 1-pair CPU smoke 已跑通 forward/backward/checkpoint 写出，产物在 `outputs_v2/transformer_checkpoints_v4_6_preference_dpo_smoke/`。

验证记录：
- `python -m unittest tests.test_generation_preference_pipeline tests.test_execution_aware_selector tests.test_v4_6_training_stability tests.test_v4_qg_evaluation_report -v` -> 22 tests OK。
- `python -m compileall scripts\evaluate_execution_aware_selector.py scripts\build_generation_preferences.py scripts\train_v4_6_preference.py tests\test_generation_preference_pipeline.py` -> OK。
- `python scripts\evaluate_execution_aware_selector.py --split val --num-samples 1 --output-dir outputs_v2\diagnostics\execution_aware_selector\split_val_smoke_1` -> 成功写入 split/sample metadata。
- `python scripts\build_generation_preferences.py --report outputs_v2\diagnostics\execution_aware_selector\beam_sp_prior_1k\selector_report.json --output outputs_v2\preference_data\smoke_beam_pairs.jsonl --source beam --min-reward-margin 0.15 --max-negatives-per-positive 2` -> 生成 1,174 条诊断 pairs。
- `python scripts\train_v4_6_preference.py --checkpoint outputs_v2\transformer_checkpoints_v4_6_quality_gate\best_gen_set_f1_model.pth --train-pairs outputs_v2\preference_data\smoke_beam_pairs.jsonl --output-dir outputs_v2\transformer_checkpoints_v4_6_preference_dpo_smoke --epochs 1 --max-pairs 1 --batch-size 1 --device cpu --lr 1e-6` -> checkpoint smoke 完成。

未完成要求：
- 必须在服务器上用 train/val split 生成 preference 数据。不要用 `beam_sp_prior_1k` 训练，因为它是 test split 诊断报告。

### 2026-05-31 — QGIS Chain Dataset 核验

已完成：
- 核验用户构建的 QGIS 链数据集：`outputs_v2/qgis_chain_dataset.jsonl` 和 `outputs_v2/qgis_chain_dataset_summary.json`。
- 确认这批数据适合作为 QGIS-native 链库，用于检索、重排、transition/grammar 学习；但目前还不适合作为干净的“自然语言 -> QGIS 算子链”监督生成训练集。

观察事实：
- 数据集共有 3,059 条记录，973 条唯一 QGIS algorithm chain。
- 在 `--require-catalog` 过滤后，所有保留记录都能匹配 QGIS catalog。
- 训练目标分布：2,683 条只能训练 `qgis_head`，376 条同时有 `qgis_head+l3_head`，可作为 L3 <-> QGIS bridge。
- 来源分布：`standard_v2` 867 条，`workflow` 1,021 条，`workflow_A` 1,171 条。
- 链长以短中链为主：长度 2 有 838 条，3 有 583 条，4 有 375 条，5 有 341 条，6 有 253 条，7 有 170 条，8 有 110 条。
- 模态分布：纯矢量 1,634 条，纯栅格 418 条，矢栅混合 931 条。
- `task_text` 仍然有明显噪声：691 条含注释 banner，440 条基本只有 repo/generic 信息，788 条经过基础过滤后少于 4 个有效英文词。

解释边界：
- 不要把完整 QGIS chain dataset 直接混进现有 L3 Transformer 作为 L3 训练数据。只有 376/3,059 条能完整映射到 L3，剩余大量 native QGIS/GDAL 高频算子会在 L3 映射环节丢失。
- 短期架构应把当前 DPO v2 L3 模型作为 semantic planner，把这批 QGIS 数据作为 platform landing layer：L3 plan / task text -> QGIS chain retrieval -> QGIS reranker/evaluator -> 可执行 algorithm sequence。
- 直接新增 QGIS generation head 是后续可选方向，但应等 task text 清洗、QGIS operator vocab 治理、QGIS chain evaluator 都稳定后再做。

下一步建议：
- 先实现 `outputs_v2/qgis_chain_dataset.jsonl` 上的 QGIS chain retrieval baseline。
- 评分不要只依赖弱 `task_text`，应组合 task-text similarity、376 条 bridge 数据的 L3 overlap、矢栅兼容、链长适配、transition frequency。
- 在训练新模型前，先实现 QGIS chain evaluator：catalog coverage、vector/raster consistency、重复算子、transition rarity。

验证记录：
- `Get-Content outputs_v2\qgis_chain_dataset_summary.json` -> 摘要匹配 3,059 条记录 / 973 条唯一链 / 376 条 L3 bridge。
- PowerShell JSONL inspection -> rows 3,059，unique chains 973，target split 2,683 QGIS-only + 376 QGIS+L3，source split 867/1,021/1,171，并确认上述 task-text 质量问题。

后续产物：
- `scripts/generate_qgis_chain_descriptions.py` 已生成 `outputs_v2/qgis_chain_dataset_described.jsonl`，每条唯一 QGIS 链一行。当前使用确定性模板规则，不调用外部 LLM/API（`llm_generated=false`），所以这些描述是 operator intent rewrite，不是原始 GitHub 任务语义真值。
- 已核验 described dataset：973 行 / 973 条唯一链；模态分布为纯矢量 587、纯栅格 140、混合 246；L3 bridge 121 条；ambiguous chain 352 条；严格按 `confidence > 0.8` 统计为 443 条；链长范围 2-15。
- 该产物适合 Phase 2 做 QGIS chain retrieval/rerank 和弱 query augmentation。未经人工或 LLM 审核前，不应作为高置信自然语言监督生成训练真值。
- Phase 2 用户侧 ablation 显示 described data 在 20 个 retrieval probe 上不如 original：avg quality 0.9625 vs 0.9825，L3 bridge hits 12/20 vs 15/20，B better than A 为 0/20。根因是当前 retrieval 更依赖 L3 bridge 覆盖，而不是模板文本。Original 有 376 条 bridge records，unique-chain described data 只有 121 条 bridge chains。
- 已修一个真实兼容 bug：`QGISChainRetriever` 现在除了读 `quality.is_pure_vector/is_pure_raster`，也会读 described row 顶层 `modality`，因此 described 数据能正常获得矢量/栅格类型加分。重新生成 described 数据仍为 121 条 L3 bridge，说明这是 unique-chain bridge 覆盖问题，不是去重误丢映射。

2026-05-31 QGIS bridge 扩展后续：
- 已构建 `outputs_v2/qgis_l3_crosswalk_candidates.csv/.json`，包含 124 个高频未映射 QGIS/GDAL/SAGA algorithm 的人工审查候选。
- 人工审查后接受 18 条映射、拒绝 7 条明确语义不匹配映射、保留 17 条 uncertain。接受映射已合并到 `outputs_v2/id_mappings_v2.json`；备份在 `outputs_v2/id_mappings_v2.backup.20260531T020712.json`；审查摘要在 `outputs_v2/qgis_l3_crosswalk_review_summary.json`。
- 接受示例包括 `native:mergevectorlayers -> L3_01_03_04`，`native:extractbyexpression/native:extractbyattribute -> L3_02_06_02`，`native:extractbylocation/native:selectbylocation -> L3_02_06_03`，`native:joinattributesbylocation/qgis:joinbylocationsummary -> L3_02_04_01`，`gdal:warpreproject -> L3_03_05_02`，`gdal:translate -> L3_07_04_05`，以及 `gdal/native:fillnodata -> L3_03_03_A`。
- 拒绝示例包括 `native:createspatialindex`、`gdal:rasterize`、`gdal:polygonize`、`native:pixelstopolygons`、`gdal:rasterize_over`、`native:joinattributestable`、`native:creategrid`；除非后续 L3 taxonomy 增加合适概念，否则这些应保持 blocklist。
- 用户侧 20-probe ablation：baseline avg top-1 score 0.5757 / quality 0.9825 / L3 bridge hits 15/20 / modality 19/20 / bridge coverage 376 (12.3%)；合并 18 条 crosswalk 后 score 0.6651 / quality 0.9950 / hits 19/20 / modality 20/20 / bridge coverage 760 (24.8%)；加入 QGIS semantic tags 后 score 0.6982 / quality 0.9950 / hits 18/20 / modality 19/20 / bridge coverage 不变。
- `scripts/build_qgis_chain_dataset.py` 现在会为没有 L3 映射的 QGIS-native 概念写入 `qgis_semantic_tags`，其中高频 `native:reprojectlayer` 标为 `vector_crs_transform`。`QGISChainRetriever` 会索引这些 tag 并给小幅加分。
- 注意：当前 semantic-tag bonus 是“有 tag 就加分”，还不是 query/L3 intent 与 tag 匹配后加分。它提高了 top-1 score，但在 20-probe 报告中没有继续提高 L3 bridge hits。后续更合理的版本应改成按 query/L3 意图匹配 tag，而不是所有 tagged chain 无条件加分。
- 后续已把 semantic-tag scoring 改成 query/L3-aware，并为 `native:reprojectlayer` 增加 landing-only native bridge：`qgis_native:vector_crs_transform`。该 bridge 不写入 `id_mappings_v2.json`，不制造 L3 映射。
- 收紧 native-bridge 和 modality-match 统计口径后，本地复跑 `python scripts\evaluate_qgis_retrieval_ablation.py`：avg score 0.7846，avg quality 0.9950，L3 bridge 175/200 (87.5%)，native bridge 40/200 (20.0%)，combined bridge 200/200 (100.0%)，modality 200/200 (100.0%)，accepted boost 138/200 (69.0%)，rejected leakage 1/200（`native:creategrid`，uncertain 类别，非 bridge 映射污染）。分层 L3：vec_analysis/filter/raster_proc/vec_rast_mix 均 100%，crs_geom 75%，uncertain 0%。
- 解释边界：当前应以 combined bridge 作为 QGIS landing 指标，因为部分 QGIS-native 操作被刻意留在 L3 之外。L3 bridge 单独下降，是因为 native bridge 被拆开计数，而不是检索失败。
- 已把 QGIS landing 作为 shadow diagnostics 接入 `scripts/evaluate_execution_aware_selector.py`，通过 `--use-qgis-landing` 启用。它在 final L3 选择之后运行，把 selected token ids 转成 L3 codes，用 `QGISChainRetriever` 检索 QGIS 链并评估 top candidates，在 per-sample 写入 `qgis_landing`，并在顶层报告写入聚合指标。该功能不改变 L3 选择，也不改变 final usability。
- 新增 CLI 参数：`--use-qgis-landing`、`--qgis-chain-dataset`、`--qgis-catalog`、`--qgis-landing-k`。
- Smoke 验证：`python scripts\evaluate_execution_aware_selector.py --num-samples 2 --use-qgis-landing --output-dir outputs_v2\diagnostics\execution_aware_selector\qgis_landing_smoke_2` 完成。2 样本 JSON summary 显示 QGIS top1 valid 1.0、avg quality 1.0、L3 bridge 0.5、native bridge 0.5、combined bridge 1.0。
- 测试验证：`python -m unittest tests.test_execution_aware_selector -v` -> 10 tests OK。
- 服务器 3k shadow 报告路径：`outputs_v2/diagnostics/execution_aware_selector/dpo_qgis_landing_test_3k/`。结果：final L3 usable 0.9997，QGIS landing top1 valid 1.0，avg quality 1.0，combined bridge 1.0。但逐样本分析显示 L3 bridge 仅 1021/3000 (34.0%)，native bridge 1979/3000 (66.0%)，主要由 `native:reprojectlayer` 在 1,979 条 top-1 链中出现驱动。
- 3k 报告中的 QGIS landing top-1 多样性有限：只有 47 条唯一 top-1 QGIS chain，top-10 chain 覆盖 83.1% 样本。若干 task type 的最高频链占比较高，例如 Surface thermal properties 56.6%、Water quality 52.6%、Land use/land cover 32.6%。
- 解释边界：3k 结果证明 shadow landing 机制对当前 GEE-derived final L3 输出总能找到规则有效的 combined bridge，但不能直接证明严格语义正确的 QGIS chain。当前 landing policy 明显依赖 native CRS/reproject 链，生产化表述前需要语义/多样性人工审查。
- 50 条自然语言任务端到端 showcase 结果位于 `outputs_v2/diagnostics/end_to_end_probe_50/`：自然语言任务 -> DPO v2 L3 序列 -> QGIS landing 已经能完整跑通。自动指标为 L3 rule-usable 49/50、QGIS top-1 valid 50/50、combined bridge 50/50、L3 bridge 40/50、native bridge 10/50、mean QGIS quality 1.0。人工审查结论是：遥感/栅格任务的 L3 规划较强，但传统矢量/QGIS-native 任务的意图建模较弱；QGIS landing 能救回一部分链，但仍明显模板化。
- GEE 测试集随机 50 条 L3-only 人工审查结果位于 `outputs_v2/diagnostics/gee_l3_probe_50/`：final usable 50/50，mean LCS/ref length 0.4608，mean Set-F1 0.5692。人工分级为 A=15、A/B=17、B=15、B/C=2、C=1；即 A 或 A/B 为 32/50，B 及以上为 47/50。解释边界：在原始 GEE/遥感分布内，L3 planner 已能生成可用规划骨架；很多序列指标差距来自长 GEE 脚本压缩，而不是硬语义失败。剩余瓶颈集中在 QGIS/vector-native 泛化、专用算法细节和参数/真实执行级 grounding。
- 新增 `docs/llm_graphrag_qgis_workflow_summary_zh.md`，记录 2026-05-31 讨论形成的系统级定位：LLM 适合放在入口做任务结构化、出口做解释交互；训练得到的小模型仍是核心 L3 规划器；QGIS landing + Neo4j/GraphRAG 负责候选 QGIS 链和证据增强；LLM 参与矫正时必须受规则、图谱证据和候选空间约束，不能作为无校验的最终裁判。下一步数据方向是构建高质量 QGIS/矢量 preference 样本，而不是直接混入原始 QGIS 语料。
- 当前主要问题已经收敛成两类：一是传统矢量 / QGIS-native 流程能力不足，需要更高质量的 QGIS/矢量 preference 数据；二是复杂任务的细节完整性还不够，模型常能给出正确骨架，但会漏掉关键步骤。后续要同时从任务结构化、证据约束补全和偏好监督三条线推进。

- 新增 docs/qgis_vector_resolution_and_benchmark_plan_zh.md，作为短期待办：优先解决传统矢量 / QGIS-native 流程能力不足，并设计同一批任务上的横向对比实验，对比 LLM-only、LLM+RAG、当前系统和改进系统。

## 2026-07-13 新词表激活数据审计

- 服务器只读核查确认：107 词表包共有 113,466 行，包括 76,884 条原 quality-gate、18,111 条 `vocab_expansion_mining`、11,277 条 `py_script_vector_mining`、4,253 条 canonical 重复样本及少量 targeted 来源。五码激活包把其中 15,410 条目标行重复 5 次，形成 77,050 条激活行，总计 172,405 行。
- 18,111 条扩词数据不是自然语言监督，仅有 179 种 L3 编码链 prompt；五个激活码覆盖其中相互重叠的 150 种编码链。挖掘脚本使用无序 `set` 收集 QGIS 算子，只保留新增码、丢弃旧 L3 步骤，并使用 `grid`、`warp` 等宽泛匹配。该批数据不能只补描述后继续使用，必须从原脚本重新抽取有序链并重新标注。
- 之前所称“约 2 万条矢量数据”不是同一批数据。`vector_unified` 包含 4,091 条有自然语言的 QGIS augmentation 和 3,037 条 LLM source-code 样本，但存在 placeholder、冲突和弱标签风险；11,277 条 PY 挖掘样本同样是编码链 prompt。Phase 11 较干净的 81,137 行包实际使用 685 条 canonical 自然语言任务，重复后为 4,253 行。
- 已有自然语言候选并不少：`qgis_complete_ALL.jsonl` 共 2,754 行，其中 1,152 行的 QGIS 链至少包含 Reproject/FixGeom/Grid/Simplify/Snap 之一，各码分别为 732/466/135/74/76（允许重叠）。但按 `script_xxx` basename 关联会在不同来源目录发生碰撞，已观察到同 ID 任务变化，因此训练前必须恢复路径级 provenance，并做描述与算子链一致性门禁。
- 685 条 clean canonical seed 中有 299 个唯一任务的真实 `qgis_ops` 至少包含一个激活目标：Reproject 178、FixGeom 120、Grid 40、Simplify 20、Snap 19（各码允许重叠）。685 条文本均非空且唯一，但 Phase 11 包装后的副本缺少显式 START/END，299 条目标任务仍使用旧 94 词表映射。应先在实验性 107 profile 下重建标签和序列边界，再考虑较弱来源。
- 激活评测还必须改用 107 专属 transition matrix、107 hierarchy，关闭或重训旧 Set Predictor，并加入包含新码的 held-out 自然语言任务。当前旧 transition matrix 属于 94 词表，val/test 对五个目标码计数均为 0。
- `/home/yll/GEE/工作流抽取结果/QGIS` 原始来源盘点表明，该目录主要是工作流抽取产物，并非完整的 398,483 个 PY 语料：共 262,901 个文件、约 30.1GB，包括 52,422 个 AST JSON、52,422 个 steps CSV，只有 721 个 `.py`。合并 process 表中有 52,329 个路径级 script 记录、49,997 个唯一 basename，其中 8,080 个明确包含 `processing.run`。
- 严格算子匹配在该目录找到 5,907 个路径级、4,684 个 basename 唯一的五码候选。路径级单码为 Reproject 4,956、FixGeom 1,107、Grid 356、Simplify 188、Snap 181；各码允许重叠，且 L1 output 目录存在一份重复副本。
- AST 文本数量充足但噪声较大：28,906 个 AST 有 module docstring，27,507 个至少包含 5 个英文词，但大量内容是许可证、Plugin Builder banner 或通用 exported-model 文本。首轮应优先处理去重后的 L1、strict-multistep、processing-chained、model/tutorial 和 RouteB；这些目录共有 1,771 个目标路径记录，822 个带 module docstring，严格任务文本启发式过滤后约 162 个，尚未做跨目录去重。
- 当前抽取产物中的 `source_script` 通常只有 basename，没有权威原始路径。下一版数据构建必须恢复上游路径 provenance，按 `statement_index`/scope 保留执行顺序而不是使用 set，对脚本和链做内容 hash 去重，阻断栅格/矢量模式误匹配，并只通过路径级键关联 facts、docstring 和 README 文本。
- `outputs_v2/_yll_update/facts_summary1000.csv` 适合作为完整 107 重构的主要输入：共 20,428 行，task name/description 全部非空，20,394 条描述唯一，20,413/20,428 能同时匹配 AST 和 steps。文本长度中位数 111 词、p90 154、p99 198、最大 307。它属于代码约束的自然语言摘要，不等同于人工编写金标。
- facts 关联仍需门禁：1,887 个匹配 basename 出现在多个抽取目录，原始 Task Type 有 3,073 种字符串。文本启发式发现 798 条测试相关、2,047 条 UI 相关、2,841 条渲染/样式相关记录，各集合有重叠；若 AST 同时含真实数据处理步骤，出现渲染词不能直接判 reject。
- 当前精确链漏斗只得到 `qgis_complete_v4.jsonl` 的 2,934 行（vector 1,520、mixed 1,013、raster 333、unknown 68），虽然 facts-to-AST 关联率接近 100%；其中仅 2,149 条唯一链，且存在最长 607 步的异常链。要利用预计约 15,700 条高质量描述，必须同时从 `processing.run` 算法和有证据的直接 QGIS/GDAL API 重建有序完整 107 标签；不能只用文本训练，也不能在代码证据不足时强制猜标签。
- 首轮真实数据 pilot 的共识规划已完成，批准版为 `.omx/plans/full-107-qgis-pilot.md`。计划保持 94/GEE 稳定，把 107 视为实验起点，构建 path/hash provenance 和 T0-T4 证据等级，提出约 300 条且不可合并指标的 estimation-reference / coverage-diagnostic 双子集，并在批量转换前暂停，等待用户明确确认子集数量和审核规则。该计划不授权训练、taxonomy 变更、扩量或生产默认切换。
- 本机同步现为 Phase 收口硬要求：服务器关键脚本、配置、prompt、schema、测试必须同步回本机仓库；taxonomy、authority、质量门禁、审核、训练准入和迁移决策必须更新 `task_plan.md`、`progress.md` 及中英文 context。大型数据保留服务器，仅同步 manifest、hash、统计、可复现构建脚本和小型审核 fixture；禁止同步任何密钥或密码。
- 2026-07-14 已在隔离分支 `feature/qgis-evidence-pilot` 启动 Phase 0。sidecar authority 报告证明 stable-94 当前存在三套不一致口径：vec11277 `vocab_profile`、Step8/V4.6 `run_contract` 和 quality-gate V4.6 入口。服务器缺少 run-contract 默认 Transformer 与 Set Predictor checkpoint，而 vec11277 和 quality-gate 资产存在。现按计划停在 authority 人工选择门禁，大 checkpoint hash/copy、restore smoke 和 Phase 1 均未开始。报告已同步到本机 `docs/reports/qgis_pilot/phase0/` 和服务器 `/home/qy/system_redesign/outputs_v2/qgis_pilot/pilot_v1/phase0/`；本机相关 20 项测试及服务器 6 项 pilot 测试通过。
- 修正版 authority 报告另外单列 `phase11_vector_sft_94`：绑定 oversampled workflows/splits/task vocab/length stats、quality-gate transition、epoch 4 最佳 composite checkpoint 和 Phase 11 日志。generic quality-gate checkpoint 目录已被 Phase 11 复用，因此不能把该 checkpoint 与基础 quality-gate 数据直接拼成可复现口径。现有 quality-gate evaluation JSON 只是 500 条全 0 smoke，且配置/实际 checkpoint 冲突，不接受为稳定 GEE 指标 authority。

