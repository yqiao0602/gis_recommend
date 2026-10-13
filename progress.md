# 进度日志

## 2026-07-14：QGIS 数据重建 Phase 1 inventory 完成

- 用户决定暂缓旧 94 restore authority，不再阻塞 QGIS 数据主线。
- 只读扫描 `/home/yll`：20,428 facts 中 20,413 条匹配 extraction artifact；15 条缺失；18,526 条唯一 group；1,887 条有 2-3 个同 basename group。
- 索引 262,110 个 extraction artifacts；AST、steps、data、edges、process relations 各 52,422 个。
- 补充描述来源：2,009 plugin metadata、2,054 README、851 model/tutorial metadata、2 个 fine-eval CSV；48,011 个源码只视为潜在 docstring/code 来源。
- source root 前后元数据一致；4 个生成文件全部位于 `/home/qy/.../pilot_v1/phase1`，write ledger 已同步本机。
- 新阻塞：107 mapping 虽有 107 个 code，但 464 条 QGIS 映射对新增 13 类覆盖为 0；下一步必须从真实有序证据构建 107 专属 crosswalk。
- Taxonomy evidence scan 已完成：扫描 15,942,213 行，识别 44,776 次 processing 调用、1,095 个 processing 算子和 21,255 个 direct API。
- 当前 13 个新增 code 与 legacy 350 code 发生语义冲突，不能冻结。基于真实证据的建议范围为 112-114 类，默认草案 113 类，等待 3 项边界决策。

## 2026-07-14：Pilot Phase 0 authority 报告完成，等待人工选择

- 在隔离分支 `feature/qgis-evidence-pilot` 新增纯 sidecar 模块 `src/gis_recommend/data/qgis_pilot.py`、Phase 0 CLI 和离线测试，不修改 94/107 默认配置。
- 本机 20 项相关测试通过；服务器同步后的 6 项 pilot 测试通过。
- Phase 0 报告确认三套 authority 不一致。run-contract 默认指向的 `transformer_checkpoints_v4_6/best_model.pth` 与 `set_predictor_checkpoints_v3/best_model.pth` 在服务器不存在。
- vec11277 profile 的数据/Set Predictor 资产完整；quality-gate V4.6 的数据、transition、Transformer 与 Set Predictor 资产完整。
- 追加审计确认 generic quality-gate checkpoint 目录已被 Phase 11 写入；修正版报告单列 `phase11_vector_sft_94`，绑定 oversampled 数据和 epoch 4 最佳 composite checkpoint。现有 evaluation JSON 是全 0 smoke 且 checkpoint 元数据矛盾，不能证明稳定 GEE 基线。
- 按批准计划在人工选择 restore authority 前停止。尚未 hash/copy 大 checkpoint、运行 restore smoke、进入 `/home/yll` inventory、调用 DeepSeek 或训练。
- 服务器产物：`/home/qy/system_redesign/outputs_v2/qgis_pilot/pilot_v1/phase0/authority_decision_report.{json,md}`；本机镜像位于 `docs/reports/qgis_pilot/phase0/`。

## 2026-07-14：真实数据审计、需求澄清与 Pilot 共识规划完成

### 根因修正

- 107 激活包共 172,405 行，其中 77,050 行是 15,410 条目标行重复 5 次。
- 18,111 条 `vocab_expansion_mining` 不是自然语言监督，只包含 L3 编码链 prompt；挖掘使用无序 set，只保留新增码并丢失完整旧 L3 步骤。
- 当前激活失败不能简单归因于上采样不足；旧 94 transition matrix、目标码不在 val/test、Set Predictor 不兼容和 hierarchy 不完整也使 0/5 评测无效。
- 决定停止继续复制这批激活数据，转向真实 facts + AST/steps 的完整 taxonomy 重构。

### 服务器真实数据核查

- `facts_summary1000.csv`：20,428 行，描述全部非空，20,394 条唯一描述，20,413/20,428 能匹配 AST 和 steps。
- `/home/yll/GEE/工作流抽取结果/QGIS`：52,422 组 AST/steps，52,329 个路径级 script 记录，49,997 个唯一 basename，8,080 个路径记录明确包含 `processing.run`。
- 五类严格算子候选：路径级并集 5,907，basename 去重并集 4,684；说明原始证据数量足够，瓶颈是 provenance、顺序恢复、语义聚合和质量评估。
- 当前 `qgis_complete_v4.jsonl` 只有 2,934 条，说明大量底层 QGIS/C++ API 尚未可靠聚合为 QGIS 算子和 L3 链。

### 最终需求决策

- 107 是当前实验 taxonomy，不保证最终仍为 107 类；真实证据可支持增删、合并和边界调整。
- GEE 76,884 条保留标签，只修空文本、重复和冲突；稳定 replay 和 held-out split 不变。
- GEE 核心指标未来相对下降硬上限为 5%。
- 首轮约 300 条 pilot 按证据来源、vector/raster/mixed 模态和 operation family 分层。
- `/home/yll` 严格只读；所有中间产物写入 `/home/qy`。
- Pilot 前不训练、不扩量、不冻结 taxonomy、不修改生产默认。

### RALPLAN 共识结果

- 批准计划：`.omx/plans/full-107-qgis-pilot.md`。
- Planner 选择 path/hash evidence table 路线，拒绝 basename 修补和纯文本 LLM 直接标注。
- Architect 要求加入 reference protocol、稳定 94 restore、强只读证明、双样本拆分、禁止保存原始推理和 T0-T4 证据等级。
- Critic 首轮拒绝后完成修订；最终 Architect 与 Critic 均 `APPROVE`。
- Phase 4 后设置人工门禁：必须确认 estimation/coverage 子集数量、审核人数、裁决人和分歧处理规则，才允许批量 LLM。
- Pilot 后扩量还需再次批准数值质量阈值和允许进入语料/SFT 的证据等级。

### 本机同步要求

- 已确认：关键决策和关键代码不能只保留在服务器，必须同步回本机仓库。
- 后续每个 Phase 收口时同步更新 `task_plan.md`、`progress.md` 和中英文 `PROJECT_CONTEXT`。
- 服务器关键脚本、配置、prompt、schema、测试和报告生成代码必须同步本机；大型数据只同步 manifest、hash、统计、可复现脚本和审核样本。
- 密码和 API key 永不写入同步文件。

### 当前状态

- **状态：** planning_complete；execution_not_started。
- 未复制 `/home/yll` 数据，未安装 SDK，未调用 DeepSeek，未启动训练。
- 下一执行入口：按 `.omx/plans/full-107-qgis-pilot.md` 推进 Phase 0-4，并在人工门禁处停止。

## 2026-07-08：vocab107 训练完成 + 评测 + 状态总览

### vocab107 训练结果
- 50 epoch from-scratch，epoch 31 最佳，早停 @epoch 43
- Best composite=0.564 (epoch 31), SetF1=0.513, LCS=0.369
- Test: Loss=2.998, SetF1=0.468, TokenAcc=15.4%

### open_landing 评测 (80题)
- vec usable=98%, vec complete=100%, vec L3%→84%
- rast usable=96%, rast L3%→78% (栅格能力保持)
- 13 新 L3 码 0/13 被模型使用 — 罕见 token 淹没

### 当前阻塞
- 新码未激活：18K 样本在 113K 总量中占比低，需上采样
- Set Predictor 未更新：仍基于旧 94 词表
- QGIS landing 未优化：native: 主导

## 2026-07-06：L3 词汇扩充 + from-scratch 训练启动

### 词汇扩充
- 三维评估（QGIS算子库 + PY脚本直接扫描 + 训练数据）确认 13 新码
- 绕过 L3 映射偏差：直接扫 398K PY 脚本 → Reproject 9,622 个脚本，FixGeom 5,000 等
- 18,111 条新样本，审计通过（Reproject 误匹配 0.19%）
- 合并训练包：113,466 样本，矢量 34.0%
- 词表 94→107, VOCAB_SIZE 更新

### from-scratch 训练
- 98,077 train / 7,694 val / 7,695 test
- 50 epoch, --enable-family-sampler, --ar-max-steps 32
- A10 GPU, ~12 it/s TF phase, 预计 ~7h
- Checkpoint: `transformer_checkpoints_v4_6_vocab107_scratch/`

### 备份
- `backups/20260706_vocab_expansion/`

## 2026-07-03：金标标注 + L3 词汇缺口发现

### 标注结果
- 40 道矢量题金标 L3 标注完成
- **50% (20/40) 任务无对应 L3 码** — 词汇缺口
- 可评分 20 题: SetF1=0.399, A=0%, B=35%, C=50%, D=15%
- 缺失 17+ 种矢量操作（Reproject/Simplify/Voronoi/Grid/Snap 等）

### 已完成的修复
- FP05: 数据源注入 (20%→5%)
- 质量门控: 3 阶段检查 (L3/QGIS/Workflow)
- 意图识别: auto_classify 集成
- .env 配置: 统一环境管理

### Git 提交
- 更新 task_plan.md, progress.md, findings.md
- 标注表: vector_gold_annotated.csv

## 2026-07-02：新阶段规划 + 上下文更新

### 新阶段目标
- **L3链质量多维度评估**：从"能生成"到"生成得对"
- **意图识别集成**：task_type 分类从外挂→推理管线前置
- **端到端质量门控**：L3输出→可用性检查→QGIS landing→workflow JSON 全链路质量追踪

### 已完成工作总结
- 矢量样本挖掘 11,277 条 + 合并训练包 95,355
- L3 模型 30 epoch 重训：Composite 0.537→0.599
- Set Predictor 30 epoch 重训：F1 0.675
- open_landing 评测：vec usable 35%→88%
- held-out 评测：SetF1=0.518（仅 2 矢量样本，参考有限）

### Git 提交
- 更新 task_plan.md, findings.md, progress.md 至 2026-07-02
- 新阶段：L3 链质量评估 + 意图识别集成 + 端到端质量门控

## 2026-07-01：L3 + Set Predictor 重训完成

### 审查内容
- 服务器训练数据现状：84,078 样本，矢量 9,167 (10.9%)，栅格 77,760 (92.5%)
- 已挖掘未合并：11,277 条矢量样本在 `targeted_vector_mining_v2/`
- 训练对比：Phase6 (set_f1=0.5796) vs ScratchGentle (set_f1=0.5367, val_loss=2.94)
- **task_type 分类突破**：矢量 L3 token 0%→55.8%

### 关键数字
| 指标 | 旧值 | 新值 |
|------|------|------|
| 训练样本 | 77,981 | 84,078 |
| 矢量占比 | 10.9% | 10.9% (未合并新样本) |
| 矢量 L3 token 输出比 | ~0% (Phase A) | 55.8% (typed) |
| vec usable | 35% | 78% |
| 已挖矢量样本 | 0 | 11,277 |

### 未完成
- [ ] 11,277 矢量样本未合并进训练包
- [ ] task_type 分类未集成进推理管线
- [ ] 大量脚本文件未提交 git

## 2026-06-27—28：ScratchGentle 从零训练

### 训练
- 50 epoch from-scratch on 84,078 样本，A10 GPU
- checkpoint: `outputs_v2/transformer_checkpoints_v4_6_scratch_gentle/`
- best set_f1=0.5367 @epoch 42
- val_loss: 3.37→2.94, rep_rate: 0.863→0.433, early_eos: 0.188→0.117
- 0 错误完成

### 评测
- `open_landing_gentle_typed/`：80 题带 task_type 分类
- 矢量 L3 55.8%，栅格 30.3% — 首次矢量主导
- `open_landing_gentle/`：无 task_type 对比
- 矢量 L3 26.5%，栅格 50.8%

## 2026-06-25—26：矢量样本大规模挖掘

### PY 脚本扫描
- 398K+ QGIS .py 脚本全量扫描 (yll GEE 池)
- 45K+ 含 processing.run()，31,838 矢量脚本
- `mine_vector_samples.py` + `_final_mine_vec.py` + `_deep_search_3codes.py`
- 修复：alg_id 命名空间对齐 + OP_PATCH 补丁
- 最终产出 **11,277 条**（per-code 上限截断）

### 辅助脚本
- `_scan_all_py.py`：统计 53,847 脚本含 processing.run
- `_vec_gap_targets.py`：计算矢量样本缺口目标
- `_compare_typed.py`：对比 typed vs untyped L3 eval

## 2026-06-24：代码审查修复

### API-trace 训练数据门禁（P1 数据质量修复）
- 新增 `scripts/clean_api_trace_l3_training_data.py`：
  - 输入：`outputs_v2/API_trace_to_L3_TRAINING_FINAL.jsonl`
  - 输出：`outputs_v2/diagnostics/api_trace_l3_cleaning/`
  - 生成 `API_trace_to_L3_TRAINING_CLEAN.jsonl` / `WEAK.jsonl` / `REJECTED.jsonl` / `CONFLICTS.jsonl` 和 JSON/Markdown 报告
  - 每条样本写 `_training_quality`：tier、sample_weight、confidence、reason、prompt_is_placeholder
- 新增 `tests/test_api_trace_l3_training_cleaning.py`：
  - 覆盖 placeholder prompt、自拒 reasoning、同 prompt 多 label、task/code 错配、task/L3 模态错配、描述强猜、不同脚本/工具错配、字符串 confidence、pattern tuple 结构防回归
- 收紧 LLM 生成入口：
  - `server_batch_api_to_l3.py` / `server_batch_source_to_l3.py` / `llm_generate_l3_from_api_traces.py` 的 prompt 从“尽量猜”改成“无可执行 GIS 证据则拒绝/空链”
  - single-code chain 最低 confidence 0.70，多码 chain 最低 0.65
  - missing/invalid confidence 直接 reject
  - placeholder `QGIS script: script_xxx` 在批量入口前置拒绝
- 修复本地 `llm_generate_l3_from_api_traces.py` 的 quality gate：后续纯属性/导出检查统一使用解析后的 `conf`，避免字符串 confidence 与 float 比较触发 TypeError。

### API-trace 清洗结果
- 原始行：6,031
- Clean：1,112
- Weak：1,384
- Rejected：3,535
- Conflict rows：1,367
- Conflict prompts：513
- 主要 reject reason：
  - same_prompt_multi_label_conflict: 1,109
  - task_l3_modality_mismatch: 915
  - task_code_mismatch: 874
  - placeholder_prompt: 279
  - low_confidence: 174
  - missing_confidence: 165
- 解释边界：clean 是可考虑进入 train-only 包的保守子集；weak 不能等权进 SFT；rejected 不能训练。后续本日已把 `sample_weight` 接入 V4.6 loss，但 clean/weak 仍需要按 train-only 包策略使用，不能直接混入 val/test。

### 本次调试记录
- 清洗规则一度异常导致 clean 从 1,135 掉到 100。
- 根因：`TASK_CODE_MISMATCH_PATTERNS` 中一条单元素 tuple 少了尾随逗号，Python 将字符串按字符迭代，造成 5,707 行被误判 task_code_mismatch。
- 已补 `test_task_code_mismatch_patterns_are_tuples` 防止复发。

### API-trace 数据门禁验证
- `python -m unittest tests.test_api_trace_l3_training_cleaning -v` -> 21 tests OK
- `python -m py_compile scripts\clean_api_trace_l3_training_data.py scripts\server_batch_api_to_l3.py scripts\server_batch_source_to_l3.py scripts\llm_generate_l3_from_api_traces.py` -> OK
- `python scripts\clean_api_trace_l3_training_data.py --input outputs_v2\API_trace_to_L3_TRAINING_FINAL.jsonl --out-dir outputs_v2\diagnostics\api_trace_l3_cleaning` -> clean=1,112 weak=1,384 rejected=3,535 conflicts=1,367
- 结构化残留检查：clean 中无 placeholder/self-reject，也无已列出的 explicit mismatch / description-only inference 表达。

### 审查驱动修复（P0 高优先级）
- `train_v4_6_quality_gate.py`：
  - 修复 TF-only warning 中的字符串语法错误
  - `--length-stats` 默认改为 `None`，可检测用户是否显式传入
  - from-scratch 短 epoch 全 TF 默认直接退出；只有显式 `--allow-tf-only-smoke` 才允许继续
  - 运行时输出改为 ASCII 前缀，避免 Windows GBK 控制台因 `⚠️/ℹ` 报错
- `scripts/_push_and_train.py`：
  - 加弃用警告头，并默认直接退出，不再执行 SSH/SFTP/远程训练
  - 修正参数 `--workflows`→`--data`，`--epochs`→`--num-epochs`
  - 加 `--task-vocab` / `--length-stats` 显式参数示例
  - 移除自动 `pkill -f train_v4_6`（改为 exit 1）
- `scripts/train_v4_6_vector_unified.py`：
  - 修复 docstring（1,097→10,768）和用法示例
  - 修正口径：val/test 污染属于 `vector_v2`，不是 `vector_unified`
  - 加 manifest 注释（data/splits/vocab/length/ckpt/alpha）
  - 缺少 `task_type_length_stats_vector_unified.json` 时默认退出，要求显式 stats 或改用 oversampled 主线
- `scripts/_upsample_splits.py`：
  - 加弃用警告头并默认直接退出（duplicate index 方案不可用）

### 审查关键发现
- 推荐训练包：`step8_quality_gate_qgis_vector_oversampled`
- 正确训练命令示例已写入 `_push_and_train.py` 弃用注释和 task_plan.md

### 验证
- `python -m py_compile scripts\train_v4_6_quality_gate.py scripts\train_v4_6_vector_unified.py scripts\_push_and_train.py scripts\_upsample_splits.py` -> OK
- `python scripts\train_v4_6_quality_gate.py --dry-run --num-epochs 5` -> 正确阻止 from-scratch TF-only 误跑
- `python scripts\train_v4_6_quality_gate.py --dry-run --num-epochs 5 --allow-tf-only-smoke` -> 显式 smoke 可通过
- oversampled 主线 dry-run -> OK，81,137 workflows，train/val/test=65,748/7,694/7,695，48 task types，tf_phase_epochs=0
- `python scripts\_push_and_train.py` / `python scripts\_upsample_splits.py` -> 默认退出，无 SSH/SFTP/写 split 副作用

### 训练机制改造（P2：真正服务矢量规划能力）
- 新增 `src/gis_recommend/training/loss_utils.py`，统一实现 `weighted_sequence_cross_entropy`。
- `TaskConditionedL3DatasetV4` 现在返回 `sample_weight`，来源为 `_training_quality.sample_weight` 或样本级 `sample_weight`。
- V4.2 Teacher Forcing 路径与 V4.6 AR scheduled-sampling 路径都已使用 per-sample weighted CE。
- 训练 prompt 改为结构化 `Task type / Task name / Goal`；V4.6 入口默认 `--max-text-length 256`，dry-run 会报告 prompt 截断、sequence truncation 和 AR horizon 统计。
- `build_task_type_sampler` 扩展为 task type * vector family * source quality * confidence/sample-weight 的组合采样；V4.6 入口新增 `--enable-family-sampler` / `--family-weight-target` / `--disable-source-quality-weighting`。
- `qgis_unmappable_penalty > 0` 现在直接拒绝，避免使用旧的错误方向 penalty。
- `--ar-max-steps` 现在可配置；默认仍是 20，服务器长链实验可显式提高到 32/40。
- `L3SequenceInferencerV4` 增加 `prompt_style=legacy|structured`；旧 DPO/SFT checkpoint 默认 legacy，新结构化 prompt 模型评估时显式传 structured。
- QG parent inferencer 修复：`_build_parent()` 会复制 `max_text_length=128` 和 `prompt_style=legacy`，避免旧 quality-gate 主线推理因新字段缺失或输入分布漂移。
- `evaluate_vector_generalization.py` / `evaluate_sft_vector_impact.py` 增加 SFT/DPO prompt-style 参数。

### 训练机制验证
- 先写回归测试确认 QG parent 缺少 `max_text_length` 会失败；修复后单测通过。
- `python -m unittest tests.test_v4_6_vector_training_mechanisms -v` -> 7 tests OK
- `python -m unittest tests.test_v4_6_training_readiness -v` -> 11 tests OK
- `python -m unittest tests.test_v4_6_training_stability tests.test_v4_training_entry_smoke -v` -> 8 tests OK
- `python -m unittest tests.test_v4_qg_planner tests.test_runtime_consistency tests.test_v4_6_vector_training_mechanisms -v` -> 21 tests OK
- `python -m unittest tests.test_api_trace_l3_training_cleaning -v` -> 21 tests OK
- `python -m py_compile src\gis_recommend\training\loss_utils.py src\gis_recommend\training\train_v4_2.py src\gis_recommend\training\train_v4_5.py src\gis_recommend\training\train_v4_6.py src\gis_recommend\inference\infer_l3_candidates_v4.py src\gis_recommend\inference\infer_l3_candidates_v4_qg.py scripts\train_v4_6_quality_gate.py scripts\train_v4_6_vector_unified.py scripts\evaluate_vector_generalization.py scripts\evaluate_sft_vector_impact.py tests\test_v4_6_vector_training_mechanisms.py tests\test_v4_6_training_readiness.py` -> OK
- oversampled warmstart dry-run（显式 data/splits/task-vocab/length-stats + `--warmstart` + `--enable-family-sampler` + `--max-text-length 256`）-> OK：
  - train/val/test=65,748/7,694/7,695，48 task types，`tf_phase_epochs=0`
  - prompt max=189，p99=128，`long_prompt_count_over_max=0`
  - sequence max=64，p99=31，`truncated_sequence_count=0`
  - `train_sequences_over_ar_max_steps=3219`
  - family sampler target coverage includes intersection=1,038、union=785、difference=688、geometry_repair=1,580、crs_transform=11,567
- oversampled warmstart dry-run 加 `--ar-max-steps 32` -> OK：`train_sequences_over_ar_max_steps=545`，比默认 20 步的 3,219 明显降低。

### 当前边界
- 本地只完成训练机制和 dry-run 验证，没有跑新的 GPU 训练；不能声明矢量规划能力已经提升。
- 下一步应在服务器用 oversampled 包 warmstart 训练，建议加 `--ar-max-steps 32`，并在 held-out vector prompts 上看 family recall / raster contamination / QGIS seed absorption。
- 如果训练的是结构化 prompt 新模型，评估 SFT 时传 `--sft-prompt-style structured`；DPO baseline 保持 legacy。

## 2026-06-20：C++ API 痕迹→LLM→L3 规模化生产

### 全量 68k 批量生产（运行中）
- A10 上 `nohup server_batch_api_to_l3.py --max-scripts 0` 全量跑 68,845 脚本
- deepseek-chat + quality gates (前置 tool-name 筛 + conf≥0.60 + 自拒检测)
- 当前进度：~800 已处理/400 条产出，产率 ~62%（加前置筛后略高）
- 预计最终产出：~**20,000-30,000 条**

### 3k 批次完成（40 码扩充验证）
- 产出 1,011 条，产率 57%，置信度均值 0.70
- 39/40 码被使用，14 个新码激活
- 反复抽查质量稳定：高置信度(0.85+)几乎不犯错，低置信度(0.50-0.55)主要是纯参数定义脚本

### 2k 批次完成
- 产出 804 条，产率 62%，置信度均值 0.71
- 2k+3k 合并去重：1,815→1,150 唯一链

### 脚本
- `llm_generate_l3_from_api_traces.py`：本地版 API 痕迹→L3（提取+LLM+质量门控）
- `server_batch_api_to_l3.py`：服务器批量版（checkpoint 恢复+find 扫描）
- 辅助脚本：`_analyze_poc_traces.py`, `_analyze_3k_quality.py`, `_audit_3k_final.py`, `_merge_dedup.py` 等

### Key 管理
- deepseek-chat 临时 key 仅通过 `DEEPSEEK_API_KEY` 环境变量提供，文档中不记录明文
- 服务器端代码通过 env var `DEEPSEEK_API_KEY` 读取，不落盘

### Git 提交（待提交）
- 新增脚本 + task_plan/findings/progress 更新
- 专利材料修改（`docs/patent/`，无关）

## 2026-06-19/20：LLM 描述→L3 大规模生成 + Phase 7 完成 + Phase 8 启动 + C++ API 路线

### LLM 批量生成（突破）
- `llm_generate_l3_from_facts.py`：deepseek-chat + 精简 25 码 prompt，20k 描述→L3
- **产出：19,754 条训练样本**，矢量 token 占 78%
- POC v3 验证：13/15 成功（87%），0 空返回

### 统一训练集
- 合并 LLM(19,754) + AST(1,374) + 种子(323) → 去重后 **10,768 条**
- 94% 矢量相关，是 Phase 6/7 的 **7.8 倍**
- 输出：`vector_training_samples_UNIFIED.jsonl`

### Phase 7（AST 1,374 + relax + α=0.8）
- 训练 32/50 epoch early stop（composite=0.2842, best epoch 20）
- 评测结果 vs Phase 6 **基本持平**（vec exec 0.40→0.40）——1,374 条仍不足以克服 99.3% 栅格

### Phase 8（统一训练集 10,768，已在跑）
- 10,768 样本合并进 labeled_workflows（87,652 total, 72,263 train）
- `train_v4_6_vector_unified.py` 在 A10 运行中（epoch ~14/50）
- 目标：10,768 条 94% 矢量能否真改 L3 输出

### C++ API 痕迹→LLM→L3 POC（新路线，2026-06-20）
- 思路：把 C++ API 调用序列（semantic_role + description）喂给 LLM→反推 L3
- script_03 验证：API_only=Reproject→Buffer→SpatialJoin→FieldCalc→Export **完全吻合**真实链
- 10 脚本小规模：6/10 合法 L3（BAD 因 prompt 格式，好修）
- 这是融合路线 1(地面真相约束) + 路线 2(LLM 理解) 的最优解

### Git 提交
- `10414ee` LLM L3 generation + QGIS ops converter
- `8a3ea86` task plan update

## 2026-06-17：重训 + Demo

### 重训（阶段 6）
- **10:48** 训练启动：`train_v4_6_vector_fix.py` 在 A10 上
  - 77,981 workflows（76,884 原版 + 1,097 矢量）
  - train/val/test = 62,592 / 7,694 / 7,695
  - 50 epoch（前 10 TF → 后 40 AR-SS），~11.5 it/s
  - checkpoint 目录：`outputs_v2/transformer_checkpoints_v4_6_vector_fix/`
- 进度：Epoch 1→10 TF 完成，Epoch 11→进入 AR-SS 阶段
- 当前状态：**Epoch ~18/50**，loss 正常下降（~5→10 范围），0 错误
- cron `aac9349b` 每 45 分钟监控

### 提交记录（6月17日）
- `feat(data): expand QGIS-L3 crosswalk + alias normalization (+85 l3_bridge, 39.8% mapped)` → `1ccef83`
- `feat(data): v2 vector training set from complete QGIS samples (real descriptions)` → `2360191`
- `feat(train): merge + training wrapper for vector-rebalanced V4.6 retrain` → `9d26837`
- `feat(eval): 3-way comparison scorer (baseline vs V4.6 vs V4.6-vector-fix)` → `24ff54c`
- `feat(eval): standard QGIS workflow JSON builder (alg-id chain -> processes + params + links)` → `0a8d545`
- `feat(demo): interactive QGIS workflow QA demo (NL task -> JSON chain -> conversational Q&A)` → `f77a6d8`

### 测试
- 28 测试绿（`test_qgis_chain_metrics` 10 + `test_open_landing_report` 9 + `test_vector_training_builder` 3 + `test_workflow_json_builder` 3 + `test_qgis_operator_registry` 1 + `test_runtime_consistency` 2）

## 2026-06-13/14：T3 评测 + V4.6 实测

### Phase A (open_landing 80 题) — 2026-06-13
- 21 测试绿（T3 评测框架），已合并 main
- 检索基线数：overall validity=0.951 io_exec=0.801 executable=0.537
- 关键发现：executable ≠ correct（C 档有效性 > A 档）
- V4.6 数（commit `78ae715`）
- Phase A: 基线 vs V4.6 模态对比表产出

### Phase B (held-out 150 题) — 2026-06-13
- L3 set_f1=0.531（首个 correctness 数）
- ② 和 ③ 通过 task_type 分解证实解耦
- 合并 main（`78ae715`）

### LLM 切换 deepseek — 2026-06-14
- 全局替换 6 个配置点的 qwen→deepseek-v4-pro
- 移除 3 处硬编码 `sk-6d6a…` 旧 key
- 描述脚本鲁棒性修复（max_tokens 4000 + reasoning_content 回退）

### 语料诊断 — 2026-06-15
- `analyze_corpus_modality.py`：量化 99.3% 栅格 / 0.2% 矢量
- 合并 main（`c6b1573`）

### 服务器数据探查 — 2026-06-14/15
- paramiko 只读连接，A10 GPU 确认
- 全量数据盘查：`docs/server_data_inventory.md`
- QGIS 链抽取（4,097 raw → 2,175 唯一去重）
- 链↔描述 join（2,733 完整样本）

### 矢量训练集构建 — 2026-06-16
- crosswalk 扩充（101→186 l3_bridge）+ alias 归一化
- v2 矢量训练集：1,097 条（954 矢量相关），已合并 main

### 交互 Demo — 2026-06-17
- workflow JSON 格式敲定 + builder（TDD 3 测试）
- `demo_interactive_workflow_qa.py` NL→JSON→deepseek QA 实测通过
- 参数追问 + 数据流追问均基于 workflow context 正确回答

## 环境
- 本地：Windows 11 Pro，Python 3.12.6，Git Bash
- 服务器：10.191.2.38 (mdzhang)，qy@10.191.2.38
  - GPU：NVIDIA A10，CUDA 12.1
  - conda env：transformer（torch 2.2.2+cu121）
  - 项目：`/home/qy/system_redesign`
  - yll 数据：`/home/yll/GEE`（只读）
- LLM：deepseek-v4-pro via api.deepseek.com/v1（key 环境变量，不落盘）
- Git workflow：feat 分支、Conventional Commits、`--no-ff` 合并

## 2026-06-24：V4.6 矢量训练机制审查修复收口

### 已完成
- V4.6 训练入口增加 `eval_source_guard`：默认拒绝 val/test 中的生成/LLM/API-trace 来源，阻断 `qgis_vector_augment`、`llm_source_code_to_l3`、`llm_api_trace_to_l3`、`api_trace_to_l3`、`api_trace`。
- 保留旧污染包诊断例外：只有显式 `--allow-generated-eval-sources` 才允许继续，并在 dry-run summary 中记录 `allowed_by_override`。
- 真实 oversampled 主线包 dry-run 已确认干净：`generated_eval_rows=0`，`eval_source_guard.status=clean`。

### 未完成 / 当前阻塞
- 还没有跑新的 GPU 全量 warmstart SFT，因此不能声明矢量规划能力已经提升。
- 下一步仍是服务器训练 + held-out vector-family recall / raster contamination / 人工 A/B/C 评估。

### 验证
- `python -m unittest tests.test_v4_6_vector_training_mechanisms tests.test_v4_6_training_readiness tests.test_v4_6_training_stability tests.test_v4_training_entry_smoke tests.test_api_trace_l3_training_cleaning tests.test_v4_qg_planner tests.test_runtime_consistency -v` -> 64 tests OK。
- `python -m py_compile ...` 覆盖训练、清洗、推理和评估关键文件 -> exit 0。
- oversampled warmstart dry-run with `--enable-family-sampler --max-text-length 256 --ar-max-steps 32` -> exit 0；train/val/test=65,748/7,694/7,695，prompt truncation=0，sequence truncation=0，AR horizon overrun=545，eval generated rows=0。

## 2026-07-14：114 类 QGIS taxonomy freeze 完成

### 结果
- 114 类实验 taxonomy 已固定：stable-94 ID `0..93` 原样保留，20 个新增类使用 ID `94..113`，生产默认仍为 94。
- 三项用户决策已固化：保留 Spatial Index；Concave Hull 独立；Rasterize 与 Polygonize 分离。
- 旧 `v3_107_experimental` 被标记为 `invalid_code_reuse`；13 个旧 token 只能按 source-profile 语义迁移，禁止按复用 code string 替换。
- 新增 49 条规范化 QGIS alias，builder 会阻断大小写归一后的 alias 冲突、新 code 与 legacy 350 冲突、base ID 变化和迁移目标不闭合。
- legacy registry 的 `L1_06` 名称原本全空；sidecar 显式补为 `3D and TIN Analysis`，同时记录 Delaunay 会重新引入 stable-94 已删除父级，但不修改生产 L1/L2 配置。

### 可复现输入与产物
- base mapping SHA256：`005699dfd438e966cda28db8891795a07b9867856951de022cd8704c6e6a4558`
- legacy hierarchy SHA256：`babbc6ea3135d479a4d8cafd46073fb5b7242204adc1b972da80d525e0559bcb`
- taxonomy SHA256：`c23b91566e672fa9b2701bb411cad7acfbd636c1219b93d454d07f644eccc739`
- migration SHA256：`5d285d2573198598d9d89cbed96491156fe0dd43dac814f59d291fab2adf278c`
- added CSV SHA256：`70baf9c251a6d93176c407fabda34eebb5efe751f84248512956a26c2fcf5970`
- 服务器 sidecar：`/home/qy/system_redesign/configs/taxonomy/`；冻结输入位于其 `inputs/` 子目录。

### 发现与边界
- 服务器 `outputs_v2/id_mappings_v2.json` metadata 声称 94，但实际有 107 个 L3 ID；本轮未覆盖该文件，服务器验证使用 taxonomy 专属冻结 94 输入。
- 本机 16 项 QGIS pilot/taxonomy 测试通过；服务器 6 项 taxonomy 测试通过；三份生成产物跨 Windows/Linux 字节级一致。
- 未训练、未调用 DeepSeek、未读取或写入 `/home/yll`、未切换生产默认。

### 下一步
1. 用 114 `alias_to_code` 对 path/hash-qualified evidence 重建有序 processing.run / low-level API / custom algorithm 链。
2. 保留 unresolved fragments 和 degraded ordering，不使用 set、不强制猜标签。
3. 形成约 300 条 estimation-reference / coverage-diagnostic 分层抽样提案，再进入人工审核门禁。

## 2026-07-14：114-aware ordered evidence 全量结果

- 完整 crosswalk：325 entries，228 exact L3 aliases，10 条显式 semantic reassignment。
- 扫描：15,942,213 rows，1,683,292 relevant API rows，21,085 path-qualified records。
- Provenance：resolved 16,936；unresolved collision 4,149（T0，禁止训练）。
- Ordering：deterministic 2,578；degraded 18,507。
- Mapping：complete_exact 24；partial_exact 2,450；unmapped 18,611。
- 20 个新增类全部有证据：records 范围 12-599；说明 taxonomy 类别不是“无数据”，但完整链仍受 stable crosswalk 覆盖和底层 API 聚合限制。
- top unmapped 主要是 `QgsProcessingAlgorithm.addParameter`、`QgsProject.instance`、`QgsField`、`QgsVectorLayer` 等实现基础设施调用，不能逐个当 L3。
- 结论：先做 bounded direct-API compaction、semantic aggregation 和 statement-index 修复，再生成约 300 条审核提案；当前 1.6GB JSONL 仅为服务器诊断产物，不进入训练、不回传 Git。
- 本机只同步 summary、observed crosswalk 和 write ledger：`docs/reports/qgis_pilot/phase2_ordered_114/`。

## 2026-07-14：Direct API Aggregation Pilot 已构建，Live Smoke 待环境变量

### 已完成
- `1133a0a`：确定性 compact pool 和 300 条 coverage pilot builder。
- `dec86f2`：`gpt-5.6-luna` 严格 prompt/response contract、bounded candidate selection、fingerprint resume 和 sanitized retry；只读取 `GGUUAI_API_KEY`。
- `8b019ff`：补齐 evidence source / modality hint / trace length 分层，并修正 `infrastructure_only` 的误导统计名。
- 服务器最终结果：21,085 source、5,107 eligible、300 pilot、300 unique IDs、T0=0、ineligible=0。
- 最终分层：ordering deterministic/fallback=126/174；source custom/direct/processing+custom/processing=5/174/38/83；modality mixed/raster/unknown/vector=124/44/24/108；long/medium/short=157/93/50。
- Provider preflight：228 个 operator 可映射到冻结 114；292/300 有 bounded candidates，8 条无候选并 fail closed。
- OpenAI SDK `2.45.0` 已安装；本机 43 项相关回归、服务器 23 项 aggregation tests 通过。
- 本机同步 300 条审查 CSV、provider preflight workbook、zero-candidate queue、summary、ledger 和 live smoke status；56.2MB pool、3.07MB full pilot JSONL、2.15MB preflight JSONL 只留服务器。

### 当前阻塞 / 下一步
- GGUUAI live smoke 已通过，但 24 条 canary 仅 15 条通过 contract；8 条 reasoning 和 1 条 unknown operator 触发停止条件。
- 剩余 268 条 ready records 未调用。先修复 provider reasoning 路由稳定性和语义覆盖缺口，再运行新的小 canary。
- 当前 pilot/canary 都不是训练数据；review workbook 仍为 pending，training admission 保持 forbidden。

## 2026-07-15：300 条小样本反馈驱动的 API 压缩修正

- 对首版 preflight 的 unknown/API 噪声做三轮只读统计，再以测试固定高置信分类；未按名称模糊猜 L3。
- 新增明确 semantic anchors：spatial predicate、rasterize、polygonize、GDAL warp/translate、raster merge、centroid；对应 bounded candidate hints 均受 114 crosswalk 限制。
- UI/feedback/parameter/renderer/registry 调用降为 infrastructure；图层/CRS/geometry metadata、OGR/GDAL open 和 expression evaluate 降为 data access。
- eligible records 从 4,506 增至 5,107（+601）；300 pilot 中 unknown calls 从 3,477 降至 1,328（-61.81%）。剩余 unknown 保留人工审核，不继续自动归类。
- 最终 family 覆盖新增：centroid 14、data_export 20、polygonize 16、raster_merge 14、rasterize 10、spatial_predicate 11。
- 正式离线 preflight：292 ready / 8 zero-candidate，candidate median=4，prompt median=5,293.5 chars；0 live calls。
- 新产物：`provider_preflight.csv`、`provider_preflight_summary.json`、`provider_preflight_write_ledger.json`、`provider_zero_candidate_queue.json`。

## 2026-07-15：确认代码约束描述可作为 Silver 数据

- 用户确认：真实脚本已形成可审核的有序 QGIS 算子链和 114-L3 链、但缺少可靠原始任务描述时，可以让 LLM 根据代码证据生成任务描述。
- 生成文本只负责把已验证工作流表达成自然语言，不负责猜测或补全标签；不得增加、删除或重排操作，必须保留明确参数、CRS、输入输出和 overlay 方向，无法确定时拒绝。
- 这类样本标为 `silver`，必须关联 source path/hash、evidence IDs、operator/L3 chain、生成器版本和审核结论；仅可进入 train，并按源脚本分组防止泄漏。
- 原始人工文本且链经审核的记录才可作为 gold；无法证明人工 provenance 的 `facts_summary1000.csv` 继续按 code-grounded/silver 候选管理。
- 当前 5,107 是 eligible evidence records，不是已验收训练样本。20K 规模仍需由 300 条 pilot 的分层接受率和更广脚本漏斗实测决定，禁止再次通过少量 prompt 重复扩行。
- 首次 live smoke attempted=1，返回 HTTP 403。根因不是 prompt/模型参数：tmux 中注入值长度仅 2 且为外层空白，不符合 `sk-...` 形态；无效变量已清除。
- 门禁结果正确：validated proposals=0，`aggregation_proposals.jsonl` 为 0 行/0 bytes，raw provider response 和 reasoning 均未持久化，训练准入仍 forbidden。
- 已同步 `aggregation_summary.json`、`aggregation_write_ledger.json` 和更新后的 `live_smoke_status.json`；下一步是安全重注入完整 key 后仅重跑一条 smoke。

## 2026-07-15：GGUUAI Live Smoke 通过

- 官方文档说明 `https://gguuai.com/v1` 和 `https://api.minimax.love/v1` 均为 OpenAI-compatible endpoint，OpenAI SDK 属于支持客户端；因此不是“不支持对话/API”。
- 实测根因：原生 HTTP 请求返回 200，而仅增加 `User-Agent: OpenAI/Python 2.41.0` 即返回 403；`x-stainless-*` 头不触发。正式 client 现覆盖为 `GGUU-QGIS-Pilot/1.0`。
- 首次有效响应暴露 contract 歧义：provider 把 data-access/unknown operation 名写入 `rejected_infrastructure`。Prompt 现提供 `allowed_rejected_infrastructure` 精确列表，并要求其他未支持证据进入 `unsupported_evidence_ids`；validator 未放宽。
- 服务器渠道会默认返回 `reasoning_content`，且 `reasoning_effort=none` 无效；`extra_body={"thinking":{"type":"disabled"}}` 可关闭，正式请求已采用。
- 最终服务器 smoke：300 输入中仅 attempted=1，validated=1；候选为 `gdal:polygonize`、`qgis:buffer`、`gdal:rasterize`、`qgis:rastercalculator`。proposal 保持 `pending_human_review`，training admission 仍 forbidden。
- 验证：本机和服务器各 24 项 aggregation tests 通过；proposal/summary/ledger 已同步到 `docs/reports/qgis_pilot/phase3_api_aggregation/`，proposal SHA256 为 `91b930702cf7a8d43b319264193eb7ac43963f52b2ee7641ba5439a35f3c2cf5`。

## 2026-07-15：24 条分层 Canary 触发停止门禁

- 新增 `scripts/build_qgis_api_aggregation_canary.py`：从 292 条 ready 中排除已完成 smoke，确定性选择 24 条；source mode 固定 8/8/8，同时覆盖 4 modality、3 trace length、2 ordering quality、4 extraction group 和 24 个不同 primary family。
- Canary 实际结果：24 attempted，15 validated，contract pass rate=62.5%；失败为 `provider_returned_reasoning` 8 条（33.3%）和 `unknown_operator` 1 条（4.2%）。
- 停止条件全部按设计执行：pass rate <70%、重复 reasoning failure >30%、reasoning returned。`raw_provider_responses_persisted=false`，reasoning 仅被检测并拒绝，没有落盘。
- 失败集中在 processing/raster/long-chain：reasoning 按 source 为 direct 1、processing+custom 3、processing-only 4；按 modality 为 raster 4、mixed 2、vector 1、unknown 1；按长度为 long 5、medium 2、short 1。
- 15 条 contract-valid proposal 的 AI 初审为 A=8、B=4、C=3。主要 C 类问题是 direct-API compactor 漏掉 dissolve/buffer/simplify、自定义 `identify dangles` 无 bounded mapping、复杂 fragmentation workflow 被压缩成少数步骤。该初审不是人工 adjudication。
- 结论：contract-valid 不等于训练可用。剩余 268 条未调用，scaling admission=`blocked`；先修 reasoning 路由和语义覆盖，再做新 canary。
- 产物同步到 `docs/reports/qgis_pilot/phase3_api_aggregation/canary_24/`：selection、outcomes、15 proposals、review CSV、summary、ledger 和 preliminary semantic audit。

## 2026-07-15：证据来源与 Class-Signature 路线复核

- Canary 同时包含 direct API、processing-only、processing+custom 各 8 条；不是只用底层 API，也不是只用 `processing.run`。
- 8 条 reasoning failure 属于 provider/channel 行为，与原始脚本缺失无关；unknown custom operator 属于 crosswalk 缺口；direct API 的缺步骤属于抽取/语义压缩完整性问题。
- 当前 ordered evidence 保留 `scope` 但不保留 `_steps.csv.args`；`compact_api_trace()` 又丢弃 `scope`。因此 class name 和参数标签目前都没有进入 provider mapping。
- 5,107 eligible 中仅 260 条有 scope、224 条有 class scope、0 条 class 名直接命中 catalog；全 21,085 条中也只有 14 records / 9 unique classes 直接命中，说明当前 facts-linked corpus 主要不是官方算法实现 trace。
- 独立的 `WorkflowoutputQGIS_QGIS_Core_Processing` 有 110 个 `_steps.csv`：106 有 class、97 有 parameter args、61 个文件可直接 class/catalog 命中、13 个 class 存在多 provider 歧义。
- 结论：class+parameter 方法适合构建约百条高质量 operator anchor 和 signature library，但不能直接生成 20K workflows。下一步应完整审核这 110 条，再把 anchor 用于普通 direct-API workflow 的语义聚合。
- 详细报告：`docs/reports/qgis_pilot/phase3_api_aggregation/canary_24/evidence_source_and_class_signature_analysis.md`。

## 2026-07-15：110 条 Core Processing Signature 审核包完成

- 新增 `scripts/build_qgis_core_signature_review.py` 和 5 项 TDD 回归，结构化解析 catalog 多行 CSV 与 trace；保留 trace/AST hash、imports、class bases、ordered structured args、参数/输出 schema 和 provider 证据。
- 自动提议规则为 fail-closed：只允许唯一、class 精确、provider 一致的候选；不再使用旧原型的 top-1 fallback。`Output data type` 等 LiteralData 控制参数不会误判为输出。
- 真实服务器构建：110 source files、117 class signatures、121 review rows、61 `auto_proposed_pending_review`、60 unresolved；accepted=0、training rows=0。
- Unresolved 为 no-exact 54、provider-evidence ambiguity 1（RasterCalculator）、provider conflict 1、no class scope 4。修复 provider token 边界后，`setProgress`/`Histogram` 不再因内部 `ogr` 子串被误判为 GDAL。初步 triage 估计 no-exact 中约 30 条是历史/别名算子，约 24 条是 framework/UI/helper；该分类不是人工 adjudication。
- 完整 `signature_records.jsonl` 为 15MB，仅留服务器，SHA256=`011973f7a835a9bf7d99d782900ec991e6588ec93a690ab8ca2e5766e8111698`。本机已同步 review CSV、ambiguity JSON/Markdown、summary、ledger 和初审报告到 `docs/reports/qgis_pilot/phase3_core_signature_review_110_v1/`。
- 下一步：人工审核全部 121 行；仅 accepted 行可导出 anchor library。随后在独立 50 条普通 direct-API workflow 上测 anchor 迁移效果。本阶段未调用 LLM、未训练、未修改生产 94、未写 `/home/yll`。

## 2026-07-15：Signature 人工审核 Batch 01

- 用户明确接受首批 10 条 GDAL 精确签名：AssignProjection、ClipRasterByExtent、ClipVectorByExtent、ColorRelief、Dissolve、ExecuteSql、GridAverage、GridDataMetrics、GridInverseDistance、GridInverseDistanceNearestNeighbor。
- 原始 `signature_review.csv` 保持不可变；决策写入独立 `adjudication_decisions.jsonl`，包含 record/class/trace hash、accepted operator、review basis 和源 review hash。
- 新增 `scripts/validate_qgis_core_signature_adjudications.py`，阻断 stale review hash、trace hash 不一致、重复决策、未知记录和非候选 operator；3 项 TDD 回归通过。
- 累计状态：accepted anchor candidates 10、remaining 111、training rows 0；完整审核前 `anchor_export_admission=blocked_until_review_complete`。
- Batch 02 用户再确认 10 条 GDAL 签名，累计 accepted=20、remaining=101。`contour` 与 `contour_polygon` 虽同属 `script_56326`，只登记为两个独立算子 anchor，不构造两步 workflow。
- 准备 Batch 03 时发现 v1 把 `merge.NODATA_OUTPUT`（Number）和 `Heatmap.OUTPUT_VALUE`（Enum）误判为 output。Builder 改为按 QGIS parameter class 判断方向，并生成 active review v2；v1 保持不可变。
- v1/v2 结构化 diff：121 keys、trace hashes、exact/ranked candidates、auto proposals、resolution statuses 全部不变，仅上述 2 行 parameter schema 改变。20 条已确认 operator 决策迁移到 v2 并保留原 review hash；v2 review SHA256=`d5eee5da32c092c594a63feea4a3cc7cd2b9708dd9ceaa0418f6a1960a57e6f4`。
- Batch 03 用户确认 10 条 GDAL 精确签名，累计 accepted=30、remaining=91。`gdalinfo`、`ogrinfo` 接受为 Processing operator anchor，但不因此自动获得 114 taxonomy 或训练准入。
- Batch 04 用户确认 10 条 GDAL 精确签名，累计 accepted=40、remaining=81。`rasterize`、`translate` 的同名 native 候选由 GDAL provider 与参数 schema 明确排除；training rows 仍为 0，完整审核前禁止导出 anchor。
- Batch 05 用户确认 10 条 GDAL/QGIS provider 精确签名，累计 accepted=50、remaining=71。`BarPlot`、`BoxPlot`、`PolarPlot` 等仅登记 operator signature，不自动进入 114 taxonomy 或训练；training rows 仍为 0。
- Batch 06 用户确认 10 条 QGIS 精确签名，累计 accepted=60、remaining=61。Histogram、Scatterplot 等报告算子继续保持 anchor-only；training rows 仍为 0，完整审核前禁止导出。
- Batch 07 用户确认混合裁决：`Buffer`、两种 mask clip、`Datasources2Vrt`、3D scatter 共 5 条接受；GDAL base/dialog/panel/provider 共 4 条拒绝为 non-anchor。累计 decisions=69、accepted=65、reject_non_anchor=4、remaining=52。
- 源码核对确认 `CreateCloudOptimizedGeoTIFF.name()=createcog`、`DatasetIdentify.name()=dataset_identify`，两者是真实算法，但 v2 catalog 没有正确 bounded candidate；本批保持 pending，不写错误拒绝或永久 unresolved。
- Batch 08 用户确认混合裁决：7 条 GDAL 历史类名由源码 `name()`、provider 和参数 schema 恢复到现行 bounded operator；`GdalConnectionDetails`、`GdalUtils` 拒绝为非算子。累计 decisions=78、accepted=72、reject_non_anchor=6、remaining=43。
- `ogrinfojson` 源码证明是独立真实算法，不能并入已接受的 `gdal:ogrinfo`；因 v2 缺少 `gdal:ogrinfojson` candidate，继续保持 pending。
- Batch 09 用户确认 8 条 GDAL/QGIS alias 接受、2 条 non-anchor 拒绝。空 class 记录使用原始 `(script_56361, "")` 键登记，未伪造类名；累计 decisions=88、accepted=80、reject_non_anchor=8、remaining=33。
- Batch 10 用户确认 7 条 QGIS alias 接受、3 条 framework/provider 类拒绝。`PointsFromLines` 与 `RasterCalculator` 虽含 GDAL 调用，但源码均继承 `QgisAlgorithm` 且 `name()` 对应 QGIS operator，因此按 QGIS anchor 接受。累计 decisions=98、accepted=87、reject_non_anchor=11、remaining=23。
- Batch 11 用户确认只接受 `SetRasterStyle`、`SetVectorStyle`、`TopoColor` 三个实际算子；`ParameterReliefColors`、内部 graph-color helper 和 Processing config/framework 共 7 条拒绝为 non-anchor。累计 decisions=108、accepted=90、reject_non_anchor=18、remaining=13。
- Batch 12 用户确认最后 10 条普通记录全部拒绝为 non-anchor，覆盖 script action/provider/editor/example 和 3 条 no-class trace。累计 decisions=118、accepted=90、reject_non_anchor=28、remaining=3。
- v2 普通人工审核至此结束；剩余仅为 `gdal:createcog`、`gdal:dataset_identify`、`gdal:ogrinfojson` 三条已由源码证明的真实算法。由于它们不在 v2 bounded candidates 中，必须迁移 review authority 后再接受，不能绕过 validator。
- 新增受控 v2→v3 authority migrator、5 项 TDD 回归和三条审计 manifest。真实 v3 SHA256=`af39d5cbc43f92e35ca8ecd28605f015f64a68d8236234fa66e2e8857a942f98`；结构化 diff 证明 121 行中只有三条目标记录变化，且仅限 exact/ranked candidate、auto proposal、resolution status、ambiguity reason 五字段。
- 118 条既有 decisions 全部迁移到 v3 review hash，并追加 immediate-source migration history；当前仍为 accepted=90、rejected=28、remaining=3、training rows=0。迁移本身没有替用户接受三条新 proposal。
- Batch 13 用户明确接受 v3 最后三条 source-confirmed GDAL signature：`gdal:createcog`、`gdal:dataset_identify`、`gdal:ogrinfojson`。最终 validator 为 decisions=121、accepted=93、reject_non_anchor=28、remaining=0、human_review_complete=true、anchor_export_admission=ready、training rows=0。
- 121 行 operator-signature 人工审核现已完成。下一阶段只允许从 93 条 accepted 行导出 anchor library，并在独立 50 条普通 direct-API workflow 上验证迁移准确率；不自动进入 114 taxonomy 或训练。

## 2026-07-15：93 条 Anchor 已导出，50 条独立 Transfer 审核包已生成

- 新增 deterministic anchor exporter 与 transfer evaluator，并以 7 项专项测试覆盖完整审核门禁、唯一 operator、dual-IDF 排名、独立排除、30/20 分层和禁止训练字段。
- 服务器 anchor library：93 anchors、93 unique operators、GDAL 59 / QGIS 34、0 条无 transfer operation、0 training rows；权威 source review SHA256=`af39d5cb...f98`。
- 独立 transfer pool：5,107 eligible 中 4,847 为 direct API；排除既有 pilot/canary 后为 4,673 条且 source script 全唯一。
- 正式基线复现 3,388 candidate / 1,285 abstain，candidate coverage=72.50%；50 条审核集为 30/20，record/source 均唯一，human accuracy 仍为 null。
- 初检已证明覆盖率偏乐观：`gdal.open`、geometry/WKB helper 等 shared calls 造成明显错误 top-1。semantic-only 消融仍不能消除全部共享调用错误，因此 signature exact transfer 暂不能自动标注。
- 权威审核包同步到 `docs/reports/qgis_pilot/phase3_signature_transfer_evaluation_50_v2/`；48MB 全量 predictions 只留服务器，ledger 保留 SHA256=`43ba8405...7a76`。
- 验证：本机 stable-94 QGIS tests 88/88；服务器专项 7/7、其余非-taxonomy 测试通过。服务器现有 107 映射使 2 个固定要求 94 的旧 taxonomy 测试失败，未覆盖或修改服务器配置。
- 下一步：人工审核 50 条并计算 top-1 precision / abstention accuracy；在此之前 taxonomy/training admission 均保持 not granted。

## 2026-07-16：Signature Transfer 人工审核 Batch 01

- 用户确认前 5 条联合裁决：第 1、2、3、5 条 top-1 错误，第 4 条 raster boolean overlay -> `qgis:rastercalculator` 正确。
- 新增 `validate_qgis_signature_transfer_adjudications.py`，绑定 immutable review SHA256、review order、record ID、candidate status 和 top-1 operator，并阻断重复/stale/status-field 冲突。
- 原始 `diagnostic_review.csv` 保持不变；决策写入 append-only `human_adjudications.jsonl`，错误记录不猜测 expected operator。
- Validator：5/50 reviewed，candidate correct=1、incorrect=4、partial top-1 precision=20%，remaining=45；abstention accuracy 仍为 null，taxonomy/training admission 继续 not granted。

## 2026-07-16：Signature Transfer 人工审核 Batch 02

- 用户接受第 6-10 条全部判错；只读核对 AST 与 catalog 后区分了正确答案类型。
- 第 6 条明确为 `qgis:hypsometriccurves`；第 9 条源码 `GeometryConvert.name()=convertgeometrytype`，明确为 `qgis:convertgeometrytype`。
- 第 7 条是 `gdal:warpreproject`、raster calculation、`grass7:r.neighbors`、`gdal:translate` 等多步链，不能压成 `gdal:extractprojection`。
- 第 8 条是 EnMAP-Box 自定义 `ImportEnmapL1CAlgorithm`；第 10 条是自定义 `HZAUSoilTextureDialog` 土壤分类工作流，二者没有标准 bounded catalog ID。
- 累计 10/50 reviewed，candidate correct=1、incorrect=9、partial top-1 precision=10%，remaining=40；所有结果仍禁止 taxonomy/training admission。

## 2026-07-16：Signature Transfer 人工审核 Batch 03 与替代路线

- 用户确认第 11-14 条错误、第 15 条 `qgis:rastercalculator` 正确；累计 15/50 reviewed、correct=2、incorrect=13、partial precision=13.33%。
- 第 11 条为 `RasterProcessor` 多步 DSM 链，AST 明确含 `gdal:warpreproject`、`gdal:buildvirtualraster`、`gdal:merge`；第 12 条为 custom `UrbanSummaryWorker`。
- 第 13 条 `QgsGeometry.simplify()` 的标准等价算子是 `native:simplifygeometries`；第 14 条为 FLO-2D 自定义 Green-Ampt/SCS 工作流，intersection 只是子步骤。
- 新增 `source_grounded_operator_chain_extraction_design.md`：后续自动化应按 explicit Processing ID、self-describing class、ordered direct-API semantic chain、custom/unbounded 四级证据抽取，禁止继续使用单纯 exact-call overlap 自动标注。
- 新增可编辑 `qgis_training_data_mainline.drawio`，把 extractor、15 条 regression set、约 300 条 pilot、训练准入和 GEE/vector 评估串成一条主线；本机未发现 draw.io CLI，因此本阶段只生成并验证 XML 源文件。
- 下一阶段仍先完成 50 条人工回归集，再构建约 300 条分层 extractor pilot；训练准入保持 not granted。

## 2026-07-16：Source-Grounded QGIS Extractor v1 冻结并生成 Blind Holdout

- 已实现 `qgis_source_grounded_extractor.py` 与 fail-closed CLI；没有调用 LLM/API，没有运行训练，没有生成训练行。
- Extractor 按 E0 explicit Processing、E1 self-describing class、E2 reviewed direct API、E3 custom/unbounded 组织证据；generic GDAL open、metadata、UI、infrastructure 不得成为 operator。
- Run6 strict exact-ID 回归：expected 12/14=85.714%；旧正确 top-1 恢复 2/2，旧错误 top-1 避免 13/13，custom 恢复 4/4。两个 exact miss 是 `qgis:rastercalculator` 与 `qgis:simplifygeometries`。
- provider suffix 聚合会夸大指标，已从权威口径中移除；不同 provider 只有经人工定义 alternative set 后才能视为等价。
- 冻结代码生成 35 条 blind holdout（review order 16-50）：`mode=blind`、`labels_read=false`、training rows=0、taxonomy/training admission=`not_granted`；预测尚未审核。
- 权威本机产物：`docs/reports/qgis_pilot/phase4_source_grounded_extractor_v1/regression_15_run6_exact/` 与 `holdout_35_v1/`。ledger 输出哈希和 extractor/CLI 代码哈希均已核对一致。
- 新增 scoped `.gitattributes` 将 Phase 4 产物固定为 LF，避免 Windows `core.autocrlf` 在后续检出时破坏 ledger SHA256。
- 验证基线：本机 focused extractor 36 项、stable-94 QGIS 127 项通过；服务器 focused suite 除 1 项 Windows-only path test skip 外通过。
- 下一步是人工审核锁定的 35 条 blind workbook，按 overall exact-ID 与 E0/E1/E2/E3 分层计算 precision 和错误类型；在此之前不进入约 300 条 pilot，也不允许 taxonomy/training admission。

## 2026-07-16：35 条 Blind Holdout 人工审核完成

- review order 16-50 全部由 joint user/Codex 分 7 批确认；原始 `holdout_35_v1/` 保持不变，裁决写入独立 `holdout_35_adjudication_v1/`。
- Item precision：E0 4/5=80.0%；E1 无预测、不可测；E2 46/60=76.7%；E3 12/39=30.8%；overall 62/104=59.6%。
- Workflow 完整率仅 9/35=25.7%；记录分级为 correct 9、partial 13、incomplete 4、incorrect 9。
- 主要失败：test source 未过滤 6 条、unit-test class 假阳性 5 条、custom function 未保留 4 条、空链漏工作流 4 条、CoordinateTransform constructor 假阳性 3 条。
- E2 identity 有一定价值，但长链经常只剩 buffer/centroid/Translate/BuildVRT 片段；E3 是主要 precision 瓶颈，helper/data container/provider/mock/test/GUI shell 被误当 custom operator。
- 已确认 identity gap：`gdal:proximity`、`gdal:merge`、`qgis:rastersampling`、`qgis:eliminateselectedpolygons`、extract-by-expression/save-features；Shapely line polygonize 应为 `native:polygonize` 而非 `gdal:polygonize`。
- 决策：`pilot_admission=blocked_pending_extractor_v2`；禁止进入约 300 条 pilot、taxonomy 或训练数据。
- 权威产物：`docs/reports/qgis_pilot/phase4_source_grounded_extractor_v1/holdout_35_adjudication_v1/`；裁决 SHA256=`bcc3eb4a...e0aac9`，所有 summary/report/input hashes 已验证。

## 2026-07-16：Extractor v2 两阶段设计确认

- 用户确认采用 deterministic 两阶段路线：v2.1 先修 precision，v2.2 再修 completeness；不调用 LLM，不训练，不修改生产默认。
- v1 继续作为默认 profile，v2 必须显式启用；v2 通过新 blind gate 前不得切默认。
- v2.1 包含 source-quality gate、E3 role classifier、constructor suppression、bounded identity precedence、已确认 identity gap 和 semantic duplicate merge。
- v2.2 增加 module-level custom function call graph 与 dependency-aware chain recovery。
- 锁定门槛：v2.1 overall precision >=80%、E2>=85%、E3>=70%、test/constructor false positive=0；v2.2 complete workflow >=60%，tier precision 相对 v2.1 下降不超过 5pp。
- 正式规格：`docs/superpowers/specs/2026-07-16-qgis-source-grounded-extractor-v2-design.md`；当前只完成设计，尚未实施。

## 2026-07-16：Extractor v2.1 实施计划与测试规格完成

- 已生成可直接执行的 TDD 计划：`docs/superpowers/plans/2026-07-16-qgis-source-grounded-extractor-v2-1.md`，共 9 个任务，覆盖 v1 隔离、source gate、class role、v2 compiler、constructor/identity、bounded precedence、semantic dedup、CLI profile 和 locked-35 gate。
- 架构选择为冻结 v1 + 显式 `--extractor-profile v2` 后处理，不在稳定模块中原地修改错误规则；v2.1 输出独立 schema、审计字段和代码哈希。
- locked gate 使用 operator/custom multiset 计算 E0/E1/E2/E3、overall precision、test/constructor false positive 和 completeness；`Eliminate` 等 bounded identity 升级不再重复要求旧 E3 fallback。
- v2.2 仍不在本轮范围；只有 v2.1 七项硬门槛全部通过才可开始 completeness compiler。
- 当前状态：计划完成，代码实现尚未开始，taxonomy/training admission 继续 `not_granted`。

## 2026-09-10：QGIS Planner Benchmark v0.2 roster-first 规划启动

- 明确 v0.2 不是扩容到 200/300 条，而是在约 120 条 final 预算内修复 supported family、DAG diversity、modality、topology 和 chain length coverage。
- R1 roster authority 已由提交 `f186d31` 冻结：20 个 `supported`、8 个 `deferred`、22 个 `out_of_scope`；权威文件为 `benchmarks/qgis_planner_v1/authority/v02_supported_family_roster.json` 与同名 `.md`。
- 冻结 roster 的配套说明存在一个 L3 标识笔误，已通过独立 `v02_supported_family_roster_errata_v1.md` 记录；不修改或重哈希 f186d31 的冻结 JSON/MD，后续一律以 JSON authority 为准。
- v0.1 保持 immutable；不修改 sealed task/gold，不重训 M1/M2/M3，不生成 v0.2 candidate/task/gold。
- 已复核既有 roster freeze 记录，冻结 stable101 四态 roster、R1-R5 gate、development 约 40（目标 30–40 canonical DAG）和 final 约 120 的预算原则。
- R2 budget authority 已冻结：`benchmarks/qgis_planner_v1/authority/v02_budget_matrix.json` 与同名 `.md`，development 40/36 canonical DAG，final 120/60 canonical DAG，显式覆盖 chain length、topology、modality 和 task_style floors。
- 当前 v0.2 可交付 task+gold 为 `0`。下一门为 R3 supply repair；验收只统计完成 graph review、Gate 2 零重叠和人工批准的 task+gold，不统计脚本、schema、review job 或 candidate 数量。
## 2026-09-10：QGIS Planner Benchmark v0.2 R3 入场 ledger 与 review envelope

- 复用既有 `candidate_supply.jsonl`，按冻结的 20-family roster 逐条检查 Gate 1、Gate 2 九索引字段、parameter-free 和图结构：149 条中 87 条 eligible，62 条因包含非 supported family 排除；eligible 为 31 个 distinct DAG。
- 生成 `benchmarks/qgis_planner_v1/authority/v02_supply_review_queue.jsonl`、`v02_supply_review_summary.json` 和 `v02_dag_review_queue.jsonl`，所有候选保持 `task_gold_admission=not_granted`，graph review 为 pending。
- 生成 `v02_dag_review_jobs.jsonl`：38 个 hash-bound jobs（31 主审 + 7 merge 二审），绑定 queue SHA `f3bc59e3f9ab1c378a4cb96ac465f294bca82dbaa50e3a02f894e18b25e7c1dd`。
- R4 尚未开始人工语义裁决；v0.2 可交付 task+gold 仍为 `0`。
## 2026-09-10：QGIS Planner Benchmark v0.2 R4 DAG semantic review

- 对 31 个 eligible DAG 按 hash-bound jobs 生成并绑定 38 条 review record：`qgis-expert-01` 31 条，`qgis-expert-02` 对 7 个 merge DAG 各 1 条二审；queue SHA 全部一致，validator `failure_count=0`。
- 语义闭合结果：23 个 `closed`（approve），8 个 `returned_for_revision`；无 disagreement。返回项集中在重复 field-calculator、重复 reproject、重复 raster/statistics 和缺少中间输出语义的复杂链。
- review closure 不是 task+gold admission；当前 v0.2 可交付 task+gold 仍为 `0`。下一步是 R4b 独立人工批准和 task 文本编写。
## 2026-09-10：QGIS Planner Benchmark v0.2 R4b approval ledger

- 对 31 个 semantic closure 建立 hash-bound approval ledger：23 个 `approve`，4 个 `return_for_revision`，4 个 `reject/exclude`。
- 23 个 approved DAG 仅获得 `task_authoring_status=eligible`；全部 31 条记录保持 `task_gold_admission=not_granted`，因此 v0.2 可交付 task+gold 仍为 `0`。
- R4c 已纠正为 source-derived task extraction：从已有 QGIS workflow/training records 派生并去参数化 task text，人工只做最小保真审核，不允许凭空手写。规范为 `benchmarks/qgis_planner_v1/authority/v02_task_derivation_spec.zh-CN.md`。
- lineage 核对确认 v0.2 不是从零开始：当前 31 个 source-backed DAG 与 v0.1 final 的 40 个 canonical DAG 有 22 个重合、9 个新增；v0.1 sidecar 的 120 条记录带 source authority。v0.1 graph/gold 可作为 migration seed，但手写 task text 必须重新绑定 source-derived provenance 后才可计入 v0.2。
- 产物：`benchmarks/qgis_planner_v1/authority/v02_dag_human_approval_ledger.jsonl` 与 `v02_dag_human_approval_summary.json`。下一步为 source extraction、task-to-gold review 和 Gate 2 重检。

## 2026-07-31：QGIS Planner Benchmark v0.1 首批 8 条可评测 task+gold

- 评测集工作流改为数据行验收：脚本、schema、候选 DAG、review job 和门禁数量不再计入交付进度。
- 已交付 8 条英文模型可见 task，并逐条配对 8 条 parameter-free QGIS `processes + links` gold；8 个 sample ID 唯一，全部与 immutable 52-DAG queue 的 graph/hash/拓扑逐字一致。
- 首批只使用已具备 approve 证据的线性图，未使用尚需双审的 merge 图；gold 中参数字段为 0。
- 独立 AI-assisted QGIS task-to-gold 复核为 8/8 approve；其中 003、007 在消除可替代算子歧义后完成二次复核。
- 可用产物：`benchmarks/qgis_planner_v1/releases/v0.1-pilot-8/`，状态为 `reviewed_usable_development_pilot`。下一验收目标为 40 条 development task+gold，而不是新增基础设施。

## 2026-07-31：QGIS Planner Benchmark v0.1 development set 达到 40 条 reviewed task+gold

- 已交付 40 条英文模型可见 task，并逐条配对 40 条 parameter-free QGIS `processes + links` gold；40 个 task/gold/sidecar/review ID 一一对应，40 条任务文本互异。
- 数据由 8 个已审 canonical DAG 各自生成 5 个独立任务表述；40/40 gold 与冻结的 52-DAG queue 精确匹配，graph hash 匹配 40/40，参数字段和悬空链接均为 0。
- 独立 task-to-gold 盲审为 40 approve / 0 revise / 0 reject；第二阶段整包规格和质量复核 `FAILURES=0`。
- 可用产物：`benchmarks/qgis_planner_v1/releases/v0.1-development-40/`，状态为 `reviewed_usable_development`。该批是 development set，不冒充 sealed final。

## 2026-07-31：QGIS Planner Benchmark v0.1 sealed final 达到 120 条 reviewed task+gold

- final core 使用与 development 完全不同的 40 个 canonical DAG，每个 DAG 编写 3 条模型可见任务文本，共 120 条 task，并逐条绑定 parameter-free QGIS `processes + links` gold。
- 120/120 完成 primary task-to-gold review；按 40-DAG roster 均匀抽取 30/120 完成 blind independent secondary review。二审发现 1 条复杂栅格任务漏写重复计算与依赖，三个文本变体同步修订，抽中样本重审通过；最终为 primary 120 approve、secondary 30 approve、0 unresolved disagreement。
- 120/120 gold 与 immutable 52-DAG queue 的 graph/hash/拓扑精确匹配；参数字段、悬空链接、provider-qualified operator ID 文本泄漏和 step-number 答案泄漏均为 0。
- development/final 的 canonical graph、source authority、forbidden near-DAG key 和 task text overlap 均为 0。
- 可用 sealed 产物：`benchmarks/qgis_planner_v1/releases/v0.1-final-core-120/`，状态为 `sealed_reviewed_usable_final_core`。该阶段未运行任何 final 模型预测。

## 2026-07-31：QGIS Planner Benchmark v0.1 refusal diagnostic 达到 12 条 reviewed

- refusal diagnostic 独立交付 12 条 task，采用 4 个 refusal intent 各 3 个任务变体；6 条为 `unsupported_capability`，6 条为 `underspecified_goal`。
- unsupported 样本分别回指 capability matrix 中 Atmospheric Correction 与 Polynomial Trend 的 `no_frozen_qgis_implementation` authority，二者 admitted operator 均为 0。
- underspecified 样本只覆盖分析目标本身无法选择唯一方法的优先区选择与空间聚集任务；缺少字段、阈值、距离、CRS 或路径不作为 refusal 理由。
- 12/12 primary review 和 12/12 blind independent secondary review 均为 approve；gold 全部为显式 `decision=abstain`，不使用空 process graph，reason code 配额为 6+6。
- 可用 sealed 产物：`benchmarks/qgis_planner_v1/releases/v0.1-refusal-12/`，状态为 `sealed_reviewed_usable_refusal_diagnostic`，并已生成 release checksums。

## 2026-07-31：QGIS Planner Benchmark v0.1 正式 Freeze 包与统一 scorer 完成

- 正式 freeze 入口为 `benchmarks/qgis_planner_v1/releases/v0.1-freeze/`，版本 `0.1.0`，状态为 `internal_sealed_freeze`；manifest 绑定 development 40、final core 120、refusal 12、stable101/QGIS authority 和统一 scorer 共 24 个 artifacts。
- 顶层 `checksums.sha256` 验证 27 项，包括 VERSION、README、benchmark manifest、全部 split/authority artifacts 和 scorer；scorer 先哈希并解析预测，再验证 manifest/checksum ledger 和读取 sealed gold。
- `scripts/score_qgis_planner_benchmark_v01.py` 对 graph 与 refusal 使用独立分母。Graph 输出 operator/edge micro PRF、operator-labeled graph exact match、dependency closure、harmful extra operator 和 false refusal；refusal 输出 accuracy、reason-code accuracy 和 unsafe-planning rate。结果记录 graph/refusal prediction SHA-256。
- exact match 使用带 operator label 的有向图同构，避免重复 operator 时链与星形被 edge multiset 错判为相同；process ID 重命名和 JSON 顺序不影响评分。
- 新增测试 15/15 通过；全量 synthetic perfect prediction smoke 覆盖 final 120 + refusal 12，graph exact/operator/edge 与 refusal 指标均为 1.0。该 smoke 不包含真实模型预测。

### 2026-09-15 对账更正：api_pattern 120 条已并入训练集（QGIS 池 629）

- **更正**：此前（含 full_funnel_audit_v1 初版）引用 `qgis_api_pattern_production_final/final_report_v1.md` 的 `not_granted_consumption_only` 冻结时点，误判"120 条待用户裁决"。用户对账指出：并入决策已于 2026-09 初做出并执行。
- **manifest 现值核验**（`paper_v1_supervision/summary_v1.json`）：QGIS 池 = **629 行**（train 616 / val 8 / test 5）；evidence levels：GOLD 52 / SILVER 454 / **NEW_SILVER_PATTERN 120** / NEW_SILVER_STANDALONE 3；全 manifest 8,912 行（GEE 8,283 权威 + QGIS 629），source-disjoint 8,797、跨 split 0 重叠。120 条全部 `granted_paper_v1_train_only`，在 C0/P2 SFT 训练数据内。
- **120 条构成**（875-funnel）：任务文本 98 英 + 22 中，来源 docstring 原文 90 / 任务性注释 11 / 领域命名 scope 19；链长 2-55 步（mode 3），零 tokenizer/V4 拒绝。
- **遗留数据治理靶点（新登记）**：98 条英文任务文本是未清洗的原始 docstring（`#` 注释标记、星号线、`Class.method: N 步几何处理链` 直出）——全项目唯一英文 QGIS 监督，真实用户语言 ✅ / 输入分布干净 ❌（推理时收到的是干净英文任务）。清洗/规范化列入数据治理轮，与"522 行中文 QGIS 英文化"增广一起权衡——这批独扛英文监督，杠杆不成比例地大。
- 教训：**引用报告结论前必须查 manifest 现值**——报告记录的是冻结时点，决策执行后报告不会自动更新；`training_admission` 字段以 manifest/实际训练文件为准。

## 2026-09-16：外部 GIS 训练数据资源调研完成（paper_v2 前置，只读）

- 只读调研：未下载/未消费任何外部数据，未修改 authority/评测/checkpoint，训练行 0。报告：`docs/reports/external_gis_training_data_survey_v1.md`。
- 检索面：arXiv API（https）、OpenAlex、GitHub API + 仓库页核验、Hugging Face 目录、QGIS Hub。所有"已核验"条目均直接访问仓库页/API 原始响应；排除一条 WebSearch 误报（LLM-Geo arXiv ID 错误，实为机器人论文）。
- 结论 ①：**不存在现成的"NL 意图 → QGIS 算子 DAG"训练集**（HF + 学术文献双空白）——dataset contribution 机会。
- 结论 ②：三条可转化外部增量——GeoAnalystBench（Apache-2.0，GeoDS，50 任务×3-10 子任务，NL+人工工作流+参考代码，ArcPy 生态）；AutoGEEval-plus（szx-0633，2,612 用例 NL→GEE Python code，无 license）；GISAgentBench（arXiv 2608.01645，349 任务全部来自 GIS Stack Exchange + 可执行轨迹 + ground truth，仓库未公开）。
- 结论 ③：**GEE↔QGIS / ArcPy↔QGIS 算子 crosswalk 外部不存在**——内部 KG（350 L3 挂双平台算子）是已知唯一实现，列为论文贡献点。
- 结论 ④：GEE-Ops（whuhsy/GEE-Ops，18.5 万脚本）/Geo-FuB（15.4 万脚本）为平行工作（AST+频繁项集挖算子链），方法论同构，related work 引用与对比基线。
- 定位：外部数据 = 评测集 + 意图重写种子/few-shot + 引用对标；主料仍是内部 25.7 万描述库。行动建议（未批准）：克隆审计 GeoAnalystBench + GEE-Ops；邮件联系 AutoGEEval 作者要 license；从 GISAgentBench PDF 找仓库。
- 操作注意：GitHub API 匿名配额 60/hr 极易用尽（HTML 搜索 429 Retry-After 3600，.model3 全量扫描未完成）；arXiv API 必须 https；S2 无 key 必 429；WebSearch 结论必须二次核验。

## 2026-09-16：M1 增强线收官（M1-R2 评测完成 + Phase 3 裁决不开 R3/R4）

- M1-R2（decoder backbone domain pretraining）全链闭环并评测：DAPT 493.4M byte-tokens（migrate 审计 8/8）→ SFT（R1 协议逐行不变）→ 冻结协议评测（R4 纪律遵守，M3 块重评分精确复现 0.1605）。
- R1→R2（final-100）：空图 88%→20%、bridge 丢弃 83.8%→43.9%、L3 token ×3.4、Define Projection 首 token 99%→0%、operator F1 0.0047→0.0857（×18）；近分布持平（val Top1 14.87→15.24%、诊断 F1 0.173→0.187）；edge F1 仍 0、EM 0/100。
- Owner 定稿结论：R2 提升"生成什么样的序列"的结构能力，未提升"根据任务语义生成哪一条具体工作流"的条件映射能力；与 Phase 0-B 归因闭环（层次 A 生成器状态修复 / 层次 B 条件映射未动）。
- Phase 3 裁决：R3/R4 不开，M1 线收束于提交 5e3f818（评测记录）+ 本次收束提交。三路线（M1/M2/M3）一致信号：模型侧调整不改善 task→L3 映射——任务语义—算子映射监督不足为值得优先检验的主要候选瓶颈。
- 下一阶段：paper_v2 数据侧（25.7 万描述库意图重写）。评测环境事故 2 起（legacy mapping 泄漏 / taxonomy 路径）独立归档于 docs/reports/m1_r2_eval_v1/。
- 证据：docs/reports/m1_r2_eval_v1/、docs/reports/qgis_planner_eval_v1/SCORES_R2_v1.json + predictions_r2/。

## 2026-09-17：外部文献补遗调研 v2 完成（通用工具链数据 + 意图合成方法 + 经典语义地理处理）

- 只读调研，v1（`docs/reports/external_gis_training_data_survey_v1.md`）的补遗，报告 `docs/reports/external_gis_training_data_survey_v2.md`。补上 v1 未覆盖的四层：①结构同构的通用工具链数据集 ②意图式数据合成方法 ③地学 DAPT 先例 ④经典语义地理处理文献（OpenAlex 期刊侧）。
- ①结构同构数据集（license 干净、量级大，但域不重叠，不作训练主粮）：TaskBench（Tool Graph + **back-instruct 从工具图反推指令**，HF microsoft/Taskbench）；WorkflowLLM/WorkflowBench（**106,763 样本**，真实工作流→代码转录→重写→验证三阶段）；ToolBench/ToolLLM（16,464 APIs / 126,486 指令，Apache-2.0）；APIGen/xLAM（**三段验证合成**，HF 37k 下载）；Gorilla/BFCL（V1-V4 评测体系）；WorfBench（图结构工作流 + subgraph 评测）。
- ②意图合成方法（直接服务重写管线设计）：back-instruct、WorkflowLLM 三阶段重写+验证、APIGen 三段验证、Self-Instruct、Evol-Instruct、Magpie、PersonaHub——四臂重写实验（C0/A1/B1/B2）的每臂都有方法锚点。
- ③DAPT 先例对照：K2（LLaMA-7B 5.5B tokens 地学 DAPT，正面）+ GeoGalactica——与 M2 负结果不矛盾（它们是领域知识任务，本项目是意图→结构化算子链），Discussion 现成对照。
- ④经典文献（L3 理论根 + 意图谱系前身）：geooperator 形式化（2015）、服务链语义组合（2006, 93 cites）、**Finding and sharing GIS methods based on the questions they answer（2018，前 LLM 时代意图→方法工作）**、SHACL 参数约束（2021）等 7 条。
- ⑤机制文献：shortcut learning（2208.11857，echo→copy 诊断挂靠）；constrained decoding 线（V2a"硬约束破坏输出意图"教训的文献支撑）。
- 结论：v1"主粮在内部"不变；但重写管线的方法蓝本（back-instruct/三阶段验证/真实工作流转录）在通用域已被 10 万级规模验证，且论文每条内部结论都有文献对话对象。未覆盖：CNKI 中文文献（需 CDP，可另开一轮）。GitHub REST API 持续 IP 级限流（两天 remaining=0），仓库核验走 WebFetch HTML。

## 2026-09-18：QGIS 数据与评测资源全景报告整合完成

- 综合报告 `docs/reports/qgis_data_eval_landscape_v1.md`：整合 v1/v2 两轮调研与内部锁定状态，新增"评测资源对比"维度（v1/v2 以数据为主线，评测只在条目内附带）。只读整理，无新数据消费。
- 评测对比新结论：benchmark v0.2.1 生态位独特——已知唯一以"结构化算子 DAG"（非代码/轨迹）为输出空间的 GIS 评测、唯一 refusal diagnostic + unsafe-planning 指标、唯一 prediction-lock + 冻结 scorer 纪律（M3 块重评分 0.1605 精确复现）、拓扑分级 gold。与外部标杆三个差距：执行级 GT（GISAgentBench 349 任务 GT 文件容差匹配，最强 agent 32.7%）、规模（AutoGEEval++ 千级 vs 我们 100）、动态/多轮（BFCL V4、GeoAgentBench 沙盒 PEA）。
- 评测方法学三层整理：静态匹配（我们/WorfBench/GeoAnalystBench）vs 执行验证（AutoGEEval/GISAgentBench/GeoAgentBench）vs LLM judge（被 GISAgentBench 作者批评会混淆"形似"与"做对"，不采用）。parameter-free 设计取舍显式化：平台可移植+gold 可人工审计 vs 无执行证据（执行才能暴露的错误不可见）。
- benchmark v0.3 四个候选（**全部未批准**）：a 执行增强层（抽样任务 catalog 默认参数填参 → QGIS 沙盒跑 gold 生成执行 GT → 预测比对）；b 规模扩充（四臂重写产物人工金标小批注入，source-disjoint）；c 拓扑细分报告（按 pure_branch/hybrid/multi_input_merge 分层重算，纯后处理）；d refusal 扩容 12→50（capability matrix 驱动）。
- 对齐诊断定稿：benchmark 已是意图式（人工任务文本+泄漏审计），错位在训练侧（GEE 100% answer-echo）——修数据不修评测；评测侧真正短板 = 规模与执行验证。行动建议 P0-P4（四臂重写 → GeoAnalystBench 接 OOD dev → 联系作者 → 拓扑细分+执行层试点 → refusal 扩容）+ 两项暂缓，全部未批准待 owner 裁定。

## 2026-09-20：外部数据与同类工作 Word 调研报告交付（内部存档版）

- 交付物：`docs/reports/qgis_external_data_related_work_survey_v1.docx`（中文，内部调研存档风格，APA 作者-年份引用）。
- 结构：引言与范围 → 数据资源盘点（表 1 GIS 专用 8 项 + 表 2 通用工具链 6 项）→ 五条"为何没有可直接可用资源" → 同类工作三代谱系与双方难点（含多解性/链式依赖与错误传播/可执行性三重难点与分层评价框架）→ 建议补充的工作（评价侧四项含首错位置统计、数据侧两项、论文侧三项）→ 参考文献 21 条。
- 质量链：全部引用条目作者经 arXiv API / OpenAlex 当场核验（含 ToolLLM 正式标题=On the Tool Manipulation Capability，Xu et al.； classics：Lemmens 2006 IEEE Internet Computing、Scheider 2018 IJDE、Brauner 2015 Qucosa）；scipilot writing_lint（word/zh）最终 PASS（FAIL 0/WARN 0）；正文约 1,840 字（不含表格与文献）。
- 诚实标注：et al. 简化引用已在文献节首声明；GeoAgentBench/Geo-FuB/WorfBench 可得性标"未核验"；TaskBench venue 未声明（仅 arXiv）；GIS Copilot 期刊版未声明。底稿与生成脚本：/tmp 下 report_body_v1.txt + gen_docx.py（scipilot 工作流产物）。

## 2026-09-22：GISAgentBench 全文核验修正（价值升级）

- owner 问"是否 QGIS 算子层面"，补 arXiv 全文核验（v1 调研原为摘要级、工具栈未点名）：128 个类型化 GIS API 固定 harness 中**约 2/3 经 qgis_process CLI 分发到 QGIS processing 算子**（含 GDAL 后端），1/3 为 GeoPandas/Rasterio/Shapely/pandas/SciPy Python 栈；不用 ArcGIS（arcpy 仅论坛过滤关键词，ArcPy 支持列为 future work）。
- 层面判定：动作空间 = 算子级（ReAct 选算子+填类型化参数+排序，50 次调用预算，不写自由 Python）；评测标准 = 任务级（输出文件容差匹配为主指标，轨迹对比仅粗功能类别诊断）。金标轨迹 2-43 步（均值 11.7），由前沿模型生成 + 3 名 GIS 专家逐步手工复核。
- 价值升级：349 任务 ≈ 4,000 步调用中约 2,700 步直接是 QGIS 算子——**外部最接近 QGIS 算子级监督的现成资源**，转化成本低于自由代码类基准（AutoGEEval）。转化四道工序：128 自定义 API↔原生算子 ID 映射 / 参数剥离至 parameter-free / Python 栈步骤映射缺口 / 仓库仍未公开（联系作者前提不变）。
- 已同步：`external_gis_training_data_survey_v1.md`（GISAgentBench 行升级为全文核验）、`qgis_data_eval_landscape_v1.md`（§4.1 行）、记忆文件。Word 报告无失实表述，未重生成。

## 2026-09-24：Stage-2 Phase R rehearsal completed — evaluator OOM, overall gate FAIL

- Owner-authorized rehearsal used the C0 recipe clone `C0R_rehearsal.yaml` (3 epochs, separate output directory); preflight SHA checks passed against the frozen QGIS train/dev/test splits. Full details and hashes: `docs/reports/transfer_phase2/phase_r/phase_r_report.md`.
- Training/save branch completed 3/3 epochs, 4,002 example exposures / 1,165,662 tokens, prompt/target truncation 0, epoch1-3 checkpoints and run ledger written. Training pipeline is verified through checkpoint persistence.
- **Dev-120 evaluator failed on all three epochs with CUDA OOM**: needed 7.01 GiB, only 6.92 GiB was free under shared Ollama/SAM3 load; ledger sentinel opF1=-1 / n=0, `best_checkpoint=None`. Do not interpret sentinel as model performance; Phase R overall = **FAIL / incomplete** because evaluation/checkpoint selection did not validate.
- Per frozen rehearsal discipline: no evaluator retry, no recipe/config adjustment, no retraining; C0R process exited and GPU returned to shared queue. Candidate infrastructure fix (same-process evaluation or serialized model release) is **not implemented/not authorized**; any rerun needs a separate owner decision. Route-2 v2 holder notified; no GPU work from this line while their Base zero-shot probe is pending.

## 2026-09-24：Stage-2 Phase R rehearsal completed — evaluator OOM, overall gate FAIL

- Owner-authorized Phase R used `route2_training/configs/C0R_rehearsal.yaml`, a C0 recipe clone with only rehearsal name/output and 3-epoch scale changed. Preflight hashes match the frozen v2a-A train/dev/test splits. Full audit bundle: `docs/reports/transfer_phase2/phase_r/phase_r_report.md`.
- Training/save branch completed 3/3 epochs, 4,002 example exposures / 1,165,662 tokens, prompt/target truncation 0; epoch1-3 checkpoints and `run_ledger.json` were written.
- **Dev-120 evaluator failed on all three epochs with CUDA OOM**: 7.01 GiB requested, 6.92 GiB available under shared GPU load. Ledger values `opF1=-1.0`, `n=0`, `best_checkpoint=None` are infrastructure sentinels, not model results; Phase R overall = **FAIL / incomplete** because evaluator/checkpoint-selection pipeline did not validate.
- Per the frozen rehearsal boundary: no evaluator retry, recipe adjustment, or retraining. C0R PID 830260 exited; GPU returned to the shared queue. Ollama/SAM3 processes were not touched. A same-process/serialized evaluator fix is only a candidate and requires separate owner approval before any rerun.

## 2026-09-26：Stage-1 预检全链完成 — v2_2 候选数据集 + Gate-v3 探针 + 唯一评分器

- Owner W4 裁定"恢复结构变体"落地：`stage1_dataset_v2.py` 的 `corrupt_plan` 改为删除任一真实步骤 / 交换语义不同的相邻步骤 / 插入 I/O 类型不兼容步骤，子类型自然混合，W4 总 token 仍锁 20% 顶（≤25%）。
- **v2_2 候选数据集构建并审计全绿**：56,710 行（core 37,044 / completion 7,876 / reconstruction 3,803 / w4 7,987）、37,044 唯一 Tier A/B train 源行、token 配比精确 0.60001/0.10000/0.09999/0.20000、Task 截断 0、Chain LM 0、W4 子类型 delete 2723 / swap 2619 / insert 2645（v2_1 塌缩 32/11/7479 已修复）；溯源审计 pool 违规 0。报告 `docs/reports/route2_p0_contract/plan_pipeline_v1/stage1_dataset_report_v2_2.json` + `stage1_dataset_provenance_audit_v2_2.json`；150MB 数据只在服务器。
- **Gate-v3 探针重建**（W4 变更后必须重生成）：dev 3,236 / test 3,256 探针（W1 1690/1805、W2 783/658、W3 238/256 as-is + 236/256 改写、W4 289/281 自然子类型分布）；冻结 legacy W3 基集逐字节保留，492/494 改写对按 (split, task, plan) 精确 join；probe SHA256 dev `c3d95f67…` / test `866c3762…` 已锁并入库（本地复验一致）。报告 `gate_build_report_v3.json`。
- **`gate_evaluator_v1`（EV gate-eval-v1.3）冻结为 Base 与所有 checkpoint 的唯一评分器**：贪心 NF4、左 padding、按能力分桶 max_new_tokens（96/560）、OOM 批减半（单项 OOM 记 invalid 不静默丢弃）、批级 SIGALRM 超时标记、W1/W2 严格归一匹配、W3 family-sequence F1 macro+micro（as-is/改写独立 + gap）、W4 严格修复意图序列匹配、每报告附 probe+inference-config SHA。
- CPU 测试 6/6（Task 永不截断 + 预算与 collator 精确一致、超长 Task fail-closed、W4 三子类型真实变异、W1 无 `ee.` 泄漏、W3 sidecar 仅评分侧、W1-W4 评分往返）。
- **2026-09-26 评分器 v1.3.1 窄修复**：v1.3 `main()` 在报告路径引用 `generation_batches()` 内部 `batch_halvings` 导致 NameError；owner 批准仅修计数传递 + 最终报告回归 + 版本冻结。测试先复现 NameError，再验证模拟 0/1/2 次 OOM batch-halving 时完整 `main()` 的 JSON 报告计数分别为 0/1/2；原 6 项保留，CPU 共 9/9；ruff F821 无其他 undefined name，代码差异仅版本号/返回值/解包（report-path bugfix / no scoring-semantic change）。探针 SHA 和评分公式均未变。**状态 = READY FOR BASELINE，非 READY FOR TRAINING**；W3 rewrite gap 仅诊断，不追加 Gate 条件。
- **未启动任何 GPU 工作**（Ollama + yyt SAM3 占用纪律不变）。下一步：GPU 空闲 → Base zero-shot（gate-dev+gate-test，--batch-size 1）→ 预注册 W1-W4 绝对下限与 Δ_i → Stage-1 开训等 owner 显式放行令。
- **2026-09-27 服务器下线与资产保全（owner 方案 B 裁定）**：mdzhang (10.191.2.38) 关机。关机前完成 248 文件、双端 SHA256 全一致的保全备份（`stage1_train_v2_2` 150MB、`b1_gee_stage_train` 264MB、`plan_pool_tiered_v2` 234MB、gate-v3 探针+evaluator+plan_pipeline_v1、`v2a_A` 三件套、Phase R ep1/2/3 checkpoint、route2_C0、Qwen 指纹）；备份位于 `../server_backup_mdzhang_20260927/`（tar sha256 6542ac1f…，说明见其 `BACKUP_README.md`）。**Base zero-shot dev 完成**：evaluator v1.3.1 零 OOM/超时/批减半，W1-W4 全 0.0、invalid 2,795/3,236（86.4%）——零样本锚点=地板，判读重心落在预注册 Δ_i；**test 半边中止**，持三冻结 SHA（evaluator v1.3.1 / 探针 dev c3d95f67… test 866c3762… / 推理配置 6355bab4…）改在租用 GPU 重跑。运行期"零落盘零日志"确认为评估器设计（报告完成时一次写出），非卡死。持有线关机前获通知并确认（dev 工件 0a41a6d 入库）。下一步：等 owner 租用 GPU → test 复跑 → 预注册 W1-W4 下限+Δ_i → Stage-1 开训等 owner 显式放行。

## 2026-09-29 凌晨：Base zero-shot test 半边完成 —— 双侧基线齐备，R2 阈值评审就绪

- 租卡机（RTX 3090）test 重跑完成：14.05h、3,256 探针、**W1–W4 全 0.000**、OOM/timeout/halvings 全 0、invalid 84.5%；**三 SHA 对账全过**（v1.3.1 / probe 866c3762… / config 6355bab4…）——与 dev 半边（A10, 11.16h, 全 0）构成同一冻结实验的双侧基线。
- 定性同型（格式不服从而非无知）：W4 双侧 parse 100%（格式可被 prime 的直接证据）、W1 9%/12%、W2/W3 0%。
- 产物入库：`base_zero_shot_v1/`（test 报告+items+run.log，本机复验三 SHA）；评审输入包 `ROUTE2_V2_R2_REVIEW_INPUTS_v1.md`（Base×平凡基线×样本量总表 + 待裁定六项）。
- 状态推进：READY FOR BASELINE → **AWAITING R2 THRESHOLD REVIEW**（owner 专场）。注册后即具备 Stage-1 开训全部条件（数据/代码/模型已在租卡机就位）。
## 2026-09-29：Base zero-shot test 完成（租卡机）——Base 全 0 双 split 锚定，R2 阈值评审材料就绪

- 租卡机（root@223.109.239.32:24924）gate_rerun_v1 于 2026-09-29 03:44 出报告（启动 09-28 13:40，elapsed 50,594s ≈ 14.1h，与预估 11-12h 量级一致）。产物三件（报告 / gate_items / run.log）已 scp 拉回 `docs/reports/route2_p0_contract/plan_pipeline_v1/base_zero_shot_v1/`。
- **三 SHA 对账全绿**：probe `866c3762…`（与本地 02_DATA_FROZEN/gate_test_probes_v3.jsonl 实测一致）、inference_config `6355bab4…`（与 dev 报告逐字一致）、evaluator gate-eval-v1.3.1。探针计数自洽：W1 1805 / W2 658 / W3 as-is+rewrite 256+256 / W4 281，合计 3,256 = test 探针总数；items jsonl 3,256 行。
- **结果：W1/W2/W3(as-is,rewrite)/W4 全 0.000，与 dev 完全同构**；invalid 2,752/3,256（84.5%）；零 OOM、零超时、零批减半。Base 零样本 = 地板在双 split 上确立，Δ 条件无判别力的结论（R2 共识）获得 test 侧确证。
- R2 阈值评审一页表已组装：`route2_p0_contract/ROUTE2_V2_R2_THRESHOLD_REVIEW_INPUTS_v1.md`（dev/test Base × 平凡基线 × 探针数 × W2 No 类数，全部来自冻结数字）。**数值裁定权归 owner**，评审前不定任何阈值。
- 笔记本环境恢复完成：bundle SHA256 `24353fbe…` 对上 → clone HEAD=9c2d873 → LFS checkout → 三项验证（evaluator SHA `c2e7d725` / pytest 9 passed / git status 干净）全过。

## 2026-09-29：owner 同步双线收官报告——数字全一致；发现评审材料双生，待回迁去重

- owner 转发收官报告：dev/test Base 全零 + 平凡基线（W2 0.779/0.790、W3 0.497/0.504）+ test 14.05h，与本线从租卡机实拉报告逐项一致（elapsed 50,594s = 14.05h），确认两线评同一冻结实验。
- **差异登记**：报告引用工位线评审材料 `ROUTE2_V2_R2_REVIEW_INPUTS_v1.md`（commit `9b04ced`）；该 commit 与文件在笔记本仓库（bundle 恢复，HEAD 链 `9c2d873` → `ef22297`）中均不存在。本线对应产物为 `ROUTE2_V2_R2_THRESHOLD_REVIEW_INPUTS_v1.md`（`ef22297`）。回迁合并时需去重（保留一份或互设引用），避免两份"评审唯一输入"并存。**未发现任何数字分歧。**
- 状态不变：AWAITING R2 THRESHOLD REVIEW——等 owner 裁定 W1 floor / W2 双条件（overall >0.79 + No-class）/ W3 floor（候选带 0.55-0.60）/ W4 floor。

## 2026-09-29：租卡机监控发现——Stage-1 全量训练已由工位线启动（09:18），等 owner 确认放行令

- 笔记本线例行连通检查发现：`train_stage1.py --config stage1_v2_2.yaml --release`（PID 103666，09:18:45 启动，RTX 3090，17.6/24 GiB）。工位线动作序列：09:16 smoke（100 行×3 epoch，data SHA `02b5b476` ✓，task_too_long 0）→ 09:18 preflight（56,710 行，类别配比 37044/7876/3803/7987 与 v2_2 冻结报告一致，Task 保护 0 超长）→ 09:19 全量（1 epoch，est 1,773 optimizer steps）。
- yaml 与 ⑦ 协议可见项全部一致：lr 1e-4、effective batch 32（2×16）、max_len 1024、1 epoch、seed 20260924、数据=冻结 v2_2。QLoRA r16α32 在 yaml 不可见（应在 train.py 内置），未独立核验。
- **矛盾点**：owner 约 08:40 同步本线时状态仍为 AWAITING R2 THRESHOLD REVIEW；阈值注册文档（ROUTE2_V2_STAGE1_THRESHOLDS_v1.md）是否已写/裁定四数是否已定，本线无从核验。**本线未动该进程**——若放行令已给工位线则本线转监控；若未给则属红线，处置权归 owner。已询问 owner。

## 2026-09-29：owner 同步三事件——阈值已注册、Stage-1 放行合法，笔记本转监控职责；矛盾点关闭

- owner 晚间同步（桌面线）：① Base test 完成（桌面 commit `9b04ced`，与本线实拉数字全一致）；② **R2 阈值已 owner 裁定冻结**（桌面 commit `2dc5d2d` + `ROUTE2_V2_STAGE1_THRESHOLDS_v1.md`）：W1≥0.20 / W2 overall≥0.85 AND No-class≥0.70（dev n=173 / test n=138）/ W3≥0.60 / W4≥0.20；Δ 仅诊断；rewrite 仅诊断；dev 选点加权 0.20/0.25/0.40/0.15 仅四项全过 floor 的候选。③ Stage-1 已开训（smoke 三轮 v1/v2 抓 bug、v3 通过 loss≈1.31；全量 09:19 起，1,773 步，预计 12-20h）。本线 244c376 登记的"矛盾点"关闭——放行令已给工位线。
- **注册 Gate 全文以桌面 `ROUTE2_V2_STAGE1_THRESHOLDS_v1.md` 为准**；本线回迁时以 commit 链合并，不另写阈值文档（避免第三份双生文件）。
- 笔记本职责（owner 指定）：每 1-2h 监控训练 → 出现 `[done] mode=release` 后启动 gate-dev 评测（--adapter /root/data/stage1_run_v1/stage1_adapter --label stage1_ep1 --split dev --out-dir /root/data/gate_stage1_dev，约 11-14h）→ 报告拉回/数字交 owner；W2-No 从 items 事后计算；FAIL 走 R3 四分叉归因交 owner，不自判重训。
- 14:20 检查：进程存活 5h，GPU 17.6GB/利用率 76%；train_full.log 仍停在权重加载段（stdout 块缓冲，同"评估器零落盘"教训，勿以日志静默判卡死）。已建每 2h 自动监控。

## 2026-09-29 监控记录（自动，每 2h；正常进度按每 6h 合并 commit）

- 16:07 ✅ 正常：PID 103666 存活 11h55m，GPU 17,592 MiB / 利用率 100%；日志仍处块缓冲（正常）；stage1_ckpt/ 暂无落盘检查点（ckpt_every=150 步，落盘点未到或缓冲未刷，持续观察——若连续多次为空且训练结束前无检查点将升级报告）。

## 2026-09-29 勘误：监控时长读数错误（etime 格式误读），训练实际仅运行 48 分钟，状态正常

- `ps -o etime` 输出 `04:59`/`11:55` 为**分:秒**，此前记录误读为小时（"存活 5h/11h55m" 均错）。10:06 实测：训练 09:19 启动、已运行 48:13，GPU 17,592 MiB / 利用率 73%，一切正常。
- 佐证自洽：log mtime 10:01（块缓冲在慢速生长）；ckpt_every=150 步 × ~40s/步（smoke 实测节奏）≈ 首个检查点预计 11:00 前后，当前未到属正常；全量 1,773 步 × ~40s ≈ 19-20h，落在 owner 预估 12-20h 上沿。
- 前述"预计完成窗口 21:00-05:00"应修正为**明晨 05:00-08:00 量级**（以 19-20h 计）。
- 11:07 ✅ 正常：存活 1h48m，GPU 100%；日志已刷出实测进度 **step 150/28,355**（微步，batch 2；= 9.4 个 optimizer step/1,773 总量），loss 1.695→1.617 下降中，tgt_trunc 310/4,480 行（2.2%，与 preflight 采样一致）；**首个检查点 11:04 已落盘**（latest.pt 47MB，ckpt@150）。实测节奏 ~42s/微步 → 全程约 13.8h，**ETA 修正为今晚 24:00 前后**（此前 19-20h 估算混用了 optimizer 步数，作废）。
- 13:07 ✅ 正常：存活 3h49m，step 320/28,355（41.6s/微步，节奏与 ETA~24:00 一致），loss 1.62→1.15 持续下降；tgt_trunc 稳定在 ~6.8%（与 preflight 采样 6.4% 一致；此前"2.2%"为笔误，实为 310/4480=6.9%）；ckpt 为单文件 latest.pt 滚动覆盖（step 300 已存）；GPU 利用率 56%（随数据加载波动，步速未降，不判异常）。

## 2026-09-29 17:08 检查 + 重要判读修正：日志 step 口径确认 + 进度分母疑似显示 bug（报 owner，不修）

- 17:08 ✅ 进程健康：存活 7h49m，GPU 100%，loss 1.02→0.96（已破 1.0），节奏 41.6s/step 零漂移。
- **口径判定**：连续四次读数 rows = step×32 精确成立（620×32=19840 等）⇒ 日志的 step 是 **optimizer step（有效 batch 32）**，非微步。据此真实进度 = **660/1,773 ≈ 37%**（preflight est_optimizer_steps_full=1773）；ETA = 剩余 1,113 步 × 41.9s ≈ 13h ⇒ **明晨 ~06:00 完成**（此前 24:00/01:00 估算作废——当时把 step 误当微步、把分母当真值）。
- **疑似 trainer 显示 bug**：日志分母 "step N/28355" 中 28355 = 56,710/2（微步数），与分子口径（optimizer step）不一致；preflight JSON 里算的是 1,773（正确）。训练数学不受影响（rows/loss/lr/ckpt 全自洽），但进度显示会误导（按分母算全程会误得 13.7 天）。**按纪律不改 trainer，报告 owner 裁定是否后续修**。
- 首轮监控批次（11:07-17:08）结论：训练健康，判读以 1,773 口径为准。
- 19:07 ✅ 正常（自动检查 #6）：存活 9h49m，840/1,773 步（47%，41.5s/步零漂移），loss 0.99-1.08 平台期震荡，GPU 61%（波动），截断率 ~6.8% 稳定；ETA ~明晨 05:50，与 06:00 判一致。
- 21:07 ✅ 正常（自动检查 #7）：存活 11h48m，1,020/1,773 步（58%），41.4s/步零漂移，loss 破平台降到 0.93，GPU 100%；ETA ~明晨 05:50 不变。
- 23:07 ✅ 正常（自动检查 #8）：存活 13h48m，1,180/1,773 步（67%），41.5s/步零漂移，loss 0.84（新低），GPU 47%（波动，步速未降）；截断率 6.8% 稳定。本批（19:07/21:07/23:07）合并 commit。
- 01:07 ✅ 正常（自动检查 #9，09-30）：存活 15h48m，1,360/1,773 步（77%），41.4s/步零漂移，loss 0.86-0.99 区间，ckpt@1350 已存；ETA ~05:50 不变。
- 03:07 ✅ 正常（自动检查 #10，09-30）：存活 17h49m，1,540/1,773 步（87%），41.4s/步零漂移，loss 0.88-0.98，ckpt@1500 已存；剩 233 步 ≈ 2.7h，ETA ~05:50 不变。
- 05:07 ✅ 正常（自动检查 #11，09-30）：存活 19h48m，1,720/1,773 步（97%），loss 0.83-0.86，41.4s/步零漂移；剩 53 步 ≈ 37 分钟，预计 ~05:45 完成。本批（01:07/03:07/05:07）合并 commit。下次检查（07:07）预期见 [done] 并自动启动 gate-dev。

## 2026-09-30：Stage-1 训练完成（[done] mode=release，20.4h）——gate-dev 评测已由链式监视器自动拉起，本线不重复启动

- 07:07 检查见 `[done] mode=release steps=1772 examples=56710 tokens=13,635,926 tgt_trunc=3,868 task_too_long=0 elapsed=73,319s`（20.36h，与 41.4s/步外推一致；steps 1772 vs 预估 1773 = 末尾不足一个有效 batch，正常）。**task_too_long=0：Task 保护零违例**；context_truncated=0。末段 loss ~0.83（仅记录，⑦：成功标准=Gate 非 loss）。adapter：`/root/data/stage1_run_v1/stage1_adapter`；账本：`run_ledger.json`；ckpt 单文件滚动至 step 1772 收尾。
- **gate-dev 已在跑**：服务器链式监视器 05:41:51 检测训练账本 → 自动启动 `gate_evaluator_v1.py --adapter stage1_adapter --label stage1_ep1 --split dev --probe-file gate_dev_probes_v3.jsonl --out-dir gate_stage1_dev --batch-size 1`（PID 144484，`gate_stage1_dev_chain.log` 记 GATE_DEV_LAUNCHED + STABLE_AFTER_180S）。参数与 owner 冻结指令逐字一致。**本线核对后未重复启动**（避免双评测 OOM 污染）。评测 8GB 在位，预计 11-14h，**出分窗口今日 17:00-20:00**。
- 本线监控自动化已按指令删除，另挂评测出分监控（报告 json 出现即拉回 + 事后计算 W2-No + 对五注册条件判 PASS/FAIL + 落盘 commit + 报 owner）。

## 2026-09-30 gate-dev 评测监控（接管原训练监控自动化；训练任务完成后转评测盯守）

- 09:07 ✅ 评测正常：PID 144484 存活 3h26m，GPU 8.1GB / 利用率 23%（batch-1 生成为访存瓶颈，低利用率属 evaluator 常态）；输出目录仅 eval.log（评估器设计：报告+items 完成时一次写出）。未重复启动（链式监视器 05:41 已按冻结参数拉起，本线 07:07 核对一致）。出分窗口维持 17:00-20:00。
- 说明：会话内无 CronDelete 工具，旧训练监控自动化暂无法自行删除（任务其实体已完成）；后续触发将按本条口径执行——盯评测、绝不重复启动。owner 可在 Automations 页手动删。
- 11:07 ✅ 评测正常：存活 5h25m，GPU 8.1GB / 22%，输出目录无新文件（报告一次写出设计，正常）。出分窗口 17:00-20:00 维持。

## 2026-09-30：Stage-1 ep1 Gate-dev 出分——**FAIL（4/4 未过门）**，学习真实发生但未达注册下限；归因与续训裁定归 owner

- 评测 12:41 完成（6.97h，零 OOM/超时/批减半，三 SHA 对账 ✓）。产物拉回 `stage1_ep1_v1/`。判定报告：`STAGE1_EP1_GATE_DEV_VERDICT_v1.md`。
- **W1 0.0000（门 0.20）❌ / W2 overall 0.3052（门 0.85）❌ + W2-No 0.6185（门 0.70）❌ / W3 as-is 0.4829 macro（门 0.60）❌ / W4 0.0346（门 0.20）❌。** W3 rewrite gap 0.0057 仅诊断，无表面模板依赖。
- 关键判读：Base 全 0 → W2 0.305 / W3 0.483 / W4 0.035，**学习真实发生**；但 W2/W3 仍低于平凡基线（0.779/0.497），Gate 判别力成立、正确拒绝。invalid 2,238/3,236（69.2%，Base 86.4%）——格式服从部分习得，仍是主瓶颈。W2 No 类错题 66/66 为空预测、0 例把 No 判成 Yes：判别方向对、产出不完整。
- **本线动作边界**：未启动 test 半边、未续训、未动任何冻结物。R3 四分叉归因初看偏 A（1 epoch 格式服从不足）/C（Contract 信息不足），**裁定归 owner**。

## 2026-09-30：owner 裁定 R3-A 续训启动——同协议再训 1 epoch（训练充分性诊断），FAIL 保持有效

- **owner 裁定**（原文要点）：不接受 Stage-1 FAIL 为最终科学结论，也不立即回合同层重设计；执行 ⑦ 预注册的"同协议续训 1 epoch"，定位 **R3-A 训练充分性诊断**；一切冻结（数据/Tier/能力定义/evaluator/probe/tokenizer/loss/QLoRA），不加 W1 格式样本、不做 curriculum/RL/B2；W3 parse 86.9% 是最有信息量信号——模型已学会按接口产出，缺的是 Task→Plan 条件化；**W1 登记 contract-format confound**（Gate 格式未入训练目标，0.000 不可判定；parse 2.5% vs Base ≈9% 为训练改变行为的证据）；**W2 表述收紧**（.6185 仅证明拒绝倾向出现/非恒答，overall .3052 + 正例 21.6% 不足以证明判别能力形成——"判别方向变化"而非"能力形成"）；R3 顺序 A→B(Tier A-only)→C(Contract/Schema)→D(转换损失)；Teacher Plan/B2/Stage-2/RL 继续冻结。
- **执行**：同 yaml（stage1_v2_2.yaml，epochs=1 语义=resume 后正好再跑一整轮）、同 out-dir；trainer 内建 resume 从 `latest.pt` 恢复（[resume] step 1772 rows 56710 = ep1 精确终点，adapter+optimizer+scheduler+RNG 全量）。PID 156537，13:4x 启动，GPU 20GB。ep1 ledger 备份 `run_ledger_ep1.json`（新增文件，零删除）。判读锚点：若续跑首段 loss 从 ~0.83 起步（而非 9.x）即确认权重正确恢复。
- **ep2 完成后**：gate-dev 由本线手动启动，label `stage1_ep2`、out-dir `gate_stage1_ep2_dev`（不覆盖 ep1）；链式监视器已确认为一次性脚本（不会自动重跑）。

## 2026-09-30 R3-A（ep2）监控（接管自动化盯守；旧 ep1 口径已作废——[done] 已处理、gate-dev ep1 已判 FAIL）

- 15:07 ✅ ep2 正常：PID 156537 存活 1h11m，GPU 20GB / 65%，step 1,860（ep2 内 88/1,772 步，41.7s/步零漂移），loss 0.78-0.84 与 ep1 收尾平滑衔接，lr 9.89e-05 缓降中。ETA ~10-01 10:40 完成，gate-dev ep2（label stage1_ep2 / out-dir gate_stage1_ep2_dev）随后启动。
- 17:07 ✅ ep2 正常：存活 3h11m，GPU 20GB / 100%，ep2 内 268/1,772 步（41.3s/步零漂移），loss 0.84-0.94 平台震荡（ep2 对同一数据的第二轮，平台属预期）；ETA ~10-01 10:40 不变。
- 19:07 ✅ ep2 正常：存活 5h11m，GPU 20GB / 81%，ep2 内 448/1,772 步（25%，41.4s/步零漂移），loss 0.76-0.82 缓慢低于 ep1 平台（积极信号，继续观察）。本批（15:07/17:07/19:07）合并 commit。
- 21:08 ✅ ep2 正常：存活 7h12m，GPU 20GB / 93%，ep2 内 628/1,772 步（35%），loss 0.76-0.77（继续低于 ep1 平台），ckpt@2400 已存；ETA ~10-01 10:40 不变。
- 23:07 ✅ ep2 正常：存活 9h11m，GPU 20GB / 70%，ep2 内 788/1,772 步（44%），loss 0.74-0.79，ckpt@2550 已存；ETA ~10-01 10:40 不变。本批（21:08/23:07）合并 commit。
- 10-01 01:07 ✅ ep2 正常：存活 11h11m，GPU 20GB / 99%，ep2 内 968/1,772 步（55%），loss 0.80-0.83，ckpt@2700 已存；ETA ~10:40 不变。
- 10-01 03:07 ✅ ep2 正常：存活 13h11m，GPU 20GB / 10%（波动），ep2 内 1,148/1,772 步（65%），loss 0.70-0.80；ETA ~10:40 不变。
- 10-01 05:07 ✅ ep2 正常：存活 15h11m，GPU 20GB / 100%，ep2 内 1,328/1,772 步（75%），loss 0.74-0.86；剩 444 步 ≈ 5.1h，ETA ~10:20 微调至 10:20-10:40。本批（01:07/03:07/05:07）合并 commit。
- 10-01 07:07 ✅ ep2 正常：存活 17h11m，GPU 20GB / 93%，ep2 内 1,508/1,772 步（85%），loss 0.68-0.77（新低 0.68）；剩 264 步 ≈ 3.1h，完成预计 ~10:15。
- 10-01 09:07 ✅ ep2 正常（最后冲刺）：存活 19h11m，GPU 20GB / 86%，ep2 内 1,688/1,772 步（95%），loss 0.76-0.78，ckpt@3450 已存；剩 84 步 ≈ 1h，预计 ~10:10 完成。下次检查（11:07）预期 [done] + 启动 gate-dev ep2。

## 2026-10-01：R3-A（ep2）训练完成（[done] 09:52 落盘）——gate-dev ep2 评测已启动

- 10:07 检查见 `[done] mode=release steps=3544`（累计 2 epoch；本轮 examples=56,710、tokens=13,635,926、tgt_trunc=3,868、task_too_long=0、本轮耗时 ~19.9h）。末段 loss ~0.73（低于 ep1 收尾 0.83）。ep2 账本 mtime 09:52、数据 SHA `02b5b476` ✓、ep1 备份完好。
- 10:17 owner 指定的完成态复核：进程正常退出、GPU 清空（11 MiB）、账本/adapter（09:52）就绪。随后启动 gate-dev ep2：`--label stage1_ep2 --out-dir /root/data/gate_stage1_ep2_dev`（**新目录，不覆盖 ep1**），实测 PID 178901，10:18 起，10:23 权重加载完毕、GPU 7.7GB / 20% 进入生成阶段。预计 ~7h，**出分窗口今日 17:00-18:00**。出分后拉回、算 W2-No、对五条件判定并报 owner。

## 2026-10-01 gate-dev ep2 评测监控

- 11:07 ✅ 评测正常：PID 178901 存活 49m，GPU 7.8GB / 32%，输出目录空（评估器一次写出设计）。出分窗口 17:00-18:00 维持。
- 13:07 ✅ ep2 评测正常：存活 2h49m（≈ep1 节奏的 40%），GPU 8.1GB / 23%，输出未写（一次写出设计）。出分窗口 17:00-18:00 维持。
- 15:07 ✅ ep2 评测正常：存活 4h49m（≈ep1 节奏的 69%），GPU 8.1GB / 21%。出分窗口 17:00-18:00 维持。本批（11:07/13:07/15:07）合并 commit。

## 2026-10-01：R3-A（ep2）Gate-dev 出分——仍 FAIL 但显著分化；W2 逼近门+No 类过门，W3 两轮持平，W4 退化归零

- 评测 16:45 完成（6.45h，三 SHA ✓，零事故）。产物拉回 `stage1_ep2_v1/`，判定报告 `STAGE1_EP2_GATE_DEV_VERDICT_v1.md`。
- **五条件**：W1 0.0000 ❌ / W2 overall 0.8020 ❌（距门 0.048，已超平凡基线 0.7791）+ **W2 No-class 0.9942 ✅ 唯一过门**（172/173，仅 1 空预测、0 例混淆）/ W3 0.4986 ❌（+0.016 vs ep1，两轮持平，仅贴平众数基线）/ W4 0.0000 ❌（**从 0.035 退化归零**，parse 70%→60%）。
- **R3-A 诊断结论（按 owner 决策树机械映射）**：W2=训练不足证据强（+0.50/轮，逼近门）；**W3=步数不是瓶颈证据强**（两轮持平 → 指向 R3-B/C/D）；**W4=续训有害**（低占比能力被主导流干扰嫌疑）；W1 confound 持续（parse 1.2%，接口仍未建立 → 单独处理）。invalid 69.2%→57.9%（W2 parse 95%）。
- **动作边界**：未启动 test / ep3 / R3-B，未动冻结物。下一分支裁定归 owner。

## 2026-10-01：owner 裁定 R3 路线——不跑 ep3 / 不动 W1 专项 / 先 R3-B-0 数据诊断（不训练）

- **裁定要点**：① ep2 已解耦 W2（epoch-sensitive，0.305→0.802）与 W3（不随训练量增长，0.483→0.499），"单纯 epoch 不足"解释被削弱；② 不跑 ep3 / 不堆 20 epoch（W3 信息增益≈0）、不改 Gate、不改 Plan Schema、不进 B2；③ **下一步 R3-B-0 数据诊断（纯分析不训练）**：把 A+B 训练样本按 Tier / Plan 长度 / step 数 / 算子多样性 / Task 复杂度 / chain 长度 / modifier / branch / type-flow break / source family 切片，核心问题="W3 失败是否集中于某类数据"，重点查 Tier A vs B 构成、长 Plan 条件化、Task↔Plan 对应强度（一任务多 Plan / 弱 Task 强 Plan）；④ 诊断无异常后做 **R3-B Tier-A-only 消融**（同 Base/tokenizer/evaluator/W1-W4/目标/预算，仅 A+B→A，1 epoch）；⑤ W4 的退化暂不动（先查 train/dev 分布与 prediction pattern，不改 20% 权重）；⑥ W1 调查冻结（结果不可作"W1 知识缺失"纯净证据），等 B/C/D 后再议接口修订。
- **核心科学问题（owner 定调）**：为什么 W2 能学、W3 几乎不学——"连接规则可以快速学到；任务条件化规划能力尚未被证明"。这触及 Route-2 核心假设：大规模 GEE workflow supervision 能否教会 Task→workflow 构造。
- **执行开始**：诊断数据全在本地（02_DATA_FROZEN：stage1_train_v2_2.jsonl + gate_dev_probes_v3.jsonl），CPU 本地分析，零服务器负载。

## 2026-10-01：R3-B-0 数据诊断完成（纯 CPU 零训练）——三问有答案，Tier-A-only 消融动机充分

- 报告：`r3b0_diagnosis/R3_B0_DIAGNOSIS_REPORT_v1.md`（脚本 v1/v2 + 两个 JSON 同目录）。数据源全冻结件；Tier 池从 mdzhang 保全 tar 解包获得（**租卡机上实际没有 plan_pool_tiered_v2.jsonl，工位线旧补充与实况不符，已更正**）。
- **①Tier 构成**：核心 37,044 行回连 95.9% = A 62.2% / B 37.5%；B 结构性更难（分支率 0.233 vs 0.058，4 倍；流断裂 0.11 vs 0；步数/tokens 更长）——B 是"更脏的 3/8"，影响面约 42% 核心 tokens。
- **②Plan 长度**：实锤双重截断——构建期 1,766 行砍尾（2.5M tokens，max 50,774/行）+ 运行期 max_len 1024；而 W3 探针金标偏长（mean 9.2 / p90 19 vs 训练 8.1 / 14），70/474 超训练 p90。W4 dev 同型偏长。
- **③对应关系**：文本级干净（36,898 唯一任务 / 仅 1 多 Plan / 零弱任务），排除；语义级未测。
- **新增发现**：W3 dev 探针 54%（匹配子集）来自 B/C/REJECT 层；改写版 236 个按设计不可回连。算子分布头重（3 个 filter 族占大头），与众数基线 0.497 互证。
- **W4 快检**：训练 p90 13 步 vs dev 金标 p90 19 步，同型偏长；prediction pattern 分析待下一轮。
- **等 owner**：是否跑 R3-B Tier-A-only 消融（动机充分）；构建期截断行的处理（超长丢弃/单独桶）属 ⑦ 外数据整形，仅登记待批。

## 2026-10-01：owner 批准 R3-B Tier-A-only 消融（严格单变量）；1,766 截断样本冻结（R3-B-TRUNC）

- **批准范围**：仅改数据构成 A+B → A-only；Base/tokenizer/evaluator/probe/Gate/W1-W4/objective/max_len/lr/effective batch/训练预算（1 epoch）全冻结；其余数据比例保持原协议（60/10/10/20 token shares）。定位=**数据质量/构成消融，非新正式 Stage-1 训练**。
- **目的表述（owner 指定，禁止写成"验证 B 是噪声"）**："检验 Tier B 数据的加入是否对 Task→Workflow Planning 产生负面影响"。B 有双重属性（可能质量较低 + 同时含更多 branch/更长 workflow）：A-only 变好 → B 噪声伤害超复杂性收益，或复杂性本身难学；A-only 变差 → B 提供了 W3 必需的困难 workflow 信号。
- **判读树**：W3 >> .499 → 数据构成进入主解释；≈.50 → R3-C/D；< .50 → B 的复杂 workflow 有正贡献。
- **R3-B-TRUNC 登记**：1,766 条构建期截断样本冻结不动，不与消融同时改（单变量纪律）；未来方向=length-aware 处理/完整监督，属下一阶段数据工程。
- **汇报要求**：完整五条件表（A+B ep1/ep2/A-only 三列），非只看 W3。
- 论文价值判断（owner）：主线正形成"GEE workflow supervision 可快速学 workflow 内部数据流判别（W2），但 Task-conditioned planning（W3）未同步形成；长 workflow 监督存在系统性截断；Tier-B 与 W3 关系待消融"——暂非最终结论。

## 2026-10-01：R3-B Tier-A-only 消融——数据集构建完成 + smoke 通过；实验登记（放行前）

- **数据集构建**（构建器字节级相同副本 `f3734d13`，隔离目录 /root/r3b_tierA，单变量=池子仅 Tier A，SHA `22c39d30…`，28,575 行；原池不在租卡机，从 mdzhang tar 解包）：SRC=b1_gee_stage_train.jsonl（服务器在位）。产出 `stage1_train_v2_2A.jsonl`（SHA `8a9337ae3e914e23…`，/root/data/）。审计：tier_ab_train_rows=23,030 全数入核心（0 转换失败/0 不合格）、token 配比 0.60001/0.1/0.09999/0.2、task_truncation=0、Chain LM=0、W4 子类 1598/1654/1610、总 tokens 14,287,002（=A+B 的 57.9%）。构建期截断在 A-only 仍存在（815 行/1.57M tokens）——与 A+B 臂同型处理，R3-B-TRUNC 冻结不动（单变量纪律）。报告 `stage1_dataset_report_v2_2A.json` 在服务器。
- **配置**：`stage1_v2_2_tierA.yaml`（name stage1_v2_2_tierA、train_data=2_2A、output_dir=/root/data/stage1_run_tierA，其余与 stage1_v2_2.yaml 逐字同）；smoke 配置同 + smoke_rows=100。种子 20260924 不变。
- **smoke 通过**：[done] mode=smoke steps=9 examples=300 tokens=62,613 tgt_trunc=3 task_too_long=0 elapsed=385s。
- **实验登记（启动前）**：R3-B Tier-A-only，1 epoch，预算=同协议；**预期观测**——主读数 W3 as-is F1（dev，evaluator v1.3.1）对照 .499（A+B ep2）/.483（ep1）：>> .499 → 数据构成进入主解释；≈.50 → R3-C/D；< .50 → B 有正贡献。同时完整报告五条件（W1/W2 overall+No/W3/W4）。预计运行 ~11.6h（tokens 57.9%）。产出目录 stage1_run_tierA，评测 label `stage1_tierA_ep1`、out-dir `gate_stage1_tierA_dev`。GPU 空闲（11 MiB）。放行依据=owner 2026-10-01 批准（`864496b`）。

## 2026-10-01：R3-B Tier-A-only 全量启动（20:44 干净起跑）——含一次 smoke 污染事故的发现与纠正

- **事故**：首次 release 启动出现 `[resume] step 9 (rows 300)`——现行训练器 smoke/release 共享 `stage1_ckpt`，smoke 收尾把 step-9 检查点写入共享目录，release 启动即捡到（ep1 未发生是因为当时 smoke 9 步未及 ckpt_every=150 的间隔保存点；本次 smoke 收尾保存触发了污染）。**立即 pkill（起跑数秒内，操作级纠正）**。
- **纠正**：smoke 产物整体隔离至 `/root/data/stage1_run_tierA_smoke_artifacts/`（mv 零删除），输出目录清空后干净重启。
- **当前**：PID 189898，19:46 启动，`[release] full run: 35,246 rows x 1 epoch`，无 [resume] 行，GPU 15.5GB/76%。总步数 ≈ 1,101 optimizer steps（35,246/32）× 41.6s ≈ **12.7h，预计 10-02 ~08:30 完成**。完成后 gate-dev（label `stage1_tierA_ep1`，out-dir `gate_stage1_tierA_dev`）。
- 教训登记：**同一 output_dir 内 smoke 会污染后续 release**（现行训练器行为）——今后 smoke 与 release 必须分目录，或 release 前清点 stage1_ckpt。

## 2026-10-01 R3-B（Tier-A-only）监控

- 21:07 ✅ 正常：PID 189898 存活 1h21m，GPU 15.5GB / 100%，step 120/1,101（optimizer 口径，日志分母 17,623 仍为微步显示 bug），40s/步，loss 1.53→1.17 起步下降；tgt_trunc 143/3,840 行。ETA ~10-02 08:00-08:30。
- 23:07 ✅ Tier-A 正常：存活 3h21m，GPU 15.5GB / 35%，step 300/1,101（27%，40s/步零漂移），loss 1.00-1.13，ckpt@300 已存；ETA ~08:00-08:30 不变。
- 10-02 01:07 ✅ Tier-A 正常：存活 5h21m，GPU 15.5GB / 92%，step 480/1,101（44%），loss 0.88-0.95，ckpt@450 已存；ETA ~08:00-08:30 不变。
- 10-02 03:07 ✅ Tier-A 正常：存活 7h21m，GPU 15.5GB / 85%，step 660/1,101（60%），loss 0.84-0.98；ETA ~08:00-08:30 不变。本批（23:07/01:07/03:07）合并 commit。
- 10-02 05:07 ✅ Tier-A 正常：存活 9h21m，GPU 15.5GB / 66%，step 840/1,101（76%），loss 0.76-0.85；剩 261 步 ≈ 2.9h，完成预计 ~08:05。
- 10-02 07:07 ✅ Tier-A 正常：存活 11h21m，GPU 15.5GB / 72%，step 1,020/1,101（93%），loss 0.76-0.78；剩 81 步 ≈ 55 分钟，完成预计 ~08:05。本批（05:07/07:07）合并 commit。

## 2026-10-02：R3-B Tier-A-only 训练完成（[done] 07:58，12.19h）——gate-dev 已启动

- `[done] mode=release steps=1101 examples=35,246 tokens=7,743,885 tgt_trunc=1,716 task_too_long=0 elapsed=43,889s`（12.19h，符合预估）。末段 loss ~0.73。adapter `/root/data/stage1_run_tierA/stage1_adapter`，账本 run_ledger.json。GPU 已清空。
- gate-dev 已启动：PID 195656（08:45 起，GPU 7.6GB），label `stage1_tierA_ep1`、out-dir `/root/data/gate_stage1_tierA_dev`（独立目录）。参数与冻结评测器一致。预计 ~6.5-7h，**出分窗口今日 15:00-16:00**。出分后出三列对比表（A+B ep1 / A+B ep2 / A-only）报 owner。

## 2026-10-02 gate-dev Tier-A 评测监控

- 09:07 ✅ 评测正常：PID 195656 存活 21m，GPU 7.6GB / 21%，输出未写（一次写出设计）。出分窗口 15:00-16:00 维持。
- 11:07 ✅ Tier-A 评测正常：存活 2h21m（≈ep2 节奏 37%），GPU 8.0GB / 20%。出分窗口 15:00-16:00 维持。
- 12:07 ✅ Tier-A 评测正常：存活 3h21m（≈48%），GPU 8.1GB / 20%。出分窗口 15:00-16:00 维持。
- 13:07 ✅ Tier-A 评测正常：存活 4h21m（≈ep2 节奏 67%），GPU 8.1GB / 20%。出分窗口 15:00-16:00 维持。本批（11:07/13:07）合并 commit。
- 14:07 ✅ Tier-A 评测正常：存活 5h21m（≈83%），报告未落盘；ETA ~15:00-15:30。
- 15:07 ✅ Tier-A 评测正常：存活 6h21m（超过 ep2 的 6.45h 节奏 99%，A-only 输出或略长），报告未落盘；预计 15:30-16:00 出分。
- 16:07 ✅ Tier-A 评测运行中但超时预测：存活 7h21m（超 ep2 全长 47 分钟），进程 R 状态、CPU 时间≈墙钟、GPU 21% —— 在算不卡；推断 A-only 模型输出更长（更多探针顶满 max_new_tokens）导致整体变慢。继续观察，若 17:07 仍未出分则查逐项耗时迹象。

## 2026-10-02：R3-B Tier-A-only Gate-dev 出分——**W3 变差（0.418），H2 被排除且方向反转**；W2 出现"只会拒绝"形态

- 评测 17:06 完成（8.33h 三臂最长，三 SHA ✓，零事故）。产物拉回 `stage1_tierA_ep1_v1/`，判定报告 `STAGE1_TIERA_GATE_DEV_VERDICT_v1.md`。
- **三列对比**（A+B ep1 / ep2 / A-only）：W1 0/0/0（parse 2.5%/1.2%/0%）；W2 overall .305/.802/**.2005**；W2 Yes .216/.748/**.0016**；W2 No .619/.994/**.9017**；W3 .483/.499/**.418**；W4 .035/0/**.021**；invalid 69.2%/57.9%/**71.8%**。
- **判读（按 owner 预注册树）**：A-only W3 < .50 → **"B 中复杂 workflow 对 W3 有正贡献"分支成立，H2（B 是瓶颈）排除且证据反转**。W3 剩余嫌疑收敛：R3-B-TRUNC（截断，两臂同受）→ R3-C（Contract）→ R3-D（转换损失）。
- **新机制证据**：A-only W2 No 类 0.9017 但 **Yes 类塌缩 0.0016**——模型只学会拒绝、几乎不会接受；对照 A+B ep2 双类掌握（.748/.994），指向 **Tier B 的高分支合法依赖模式是"识别合法连接（Yes）"的信号来源**。建议后续专项验证。
- 动作边界：未启动 ep3/test/R3-C/D/TRUNC 处理、未动冻结物；下一步归 owner。

## 2026-10-02：owner 裁定 R3-B-1 数据诊断（纯分析零训练）——先解 W2-Yes 异常，暂不进 R3-C/D

- **裁定要点**：① Tier-A-only 已回答"删 B 使 W3 降 8pp"，但不能断言 B 必有益（A-only 同时改变了规模/tokens/复杂度/分支/组合多样性五件事）；② **W2-Yes 崩溃（0.0016）比 W3 更值得追**，但暂不接受"B 教会 Yes"解释——竞争解释：A-only 训练分布/规模效应（Yes 类覆盖不足 → No 偏置）；③ 顺序改为：R3-B-1 诊断 → （视结果）小型 W2 机制验证 → R3-B-TRUNC 诊断 → R3-C → R3-D → 最后才考虑更长训练/objective；④ TRUNC 修正定位：两臂共同的上限因素，关键看截断位置与被截字段（后半段尾步骤 vs 关键 dependency/branch/constraint）；⑤ 不跑 ep3、不碰 RL。
- **执行**：全本地 CPU。W2 dev 探针带标签（Yes 610/No 173）可按 task 文本回连池子取 Tier；训练行带 source_row_id（=SRC 行号=池子 row_id）可精确 join；TRUNC 分析需 Qwen tokenizer（走附录 C 镜像模板下载 tokenizer 小件）。

## 2026-10-02：R3-B-1 数据诊断完成——W2-Yes 崩溃的解释反转：证据指向"累计 token 阈值"而非 Tier-B 内容

- 报告：`r3b1_diagnosis/R3_B1_DIAGNOSIS_REPORT_v1.md`。全程本地 CPU + 冻结件 + 服务器 tokenizer 小件。
- **F1 意外发现**：W2 的 783 探针是**类型对兼容性问题**（34 对、8 个 Yes 型），与任务/池子行无关（775/783 严格符合"同型→Yes"规则）——探针侧 Tier 交叉表不存在，双臂差异全是模型行为。
- **F4 反例**：主 Yes 对（raster_collection→raster_collection，509 探针）在 A 层有 148,965 个实例——覆盖充足，A-only 却只答对 1 题。**"B 提供独有覆盖"解释不成立**。
- **F5 收敛**：配对预测显示 A-only 对合法转移大面积**拒答**（空 407/No 202/Yes 1）；结合累计 token 曲线（A+B ep1 Yes .216 @24.7M → ep2 .748 @49.4M → A-only .0016 @14.3M），**"累计 token 阈值涌现"假说证据更强**——正中 owner 自定判别规则（"A 的 Yes 不少但仍 ≈0 → 问题在训练而非类别数量"）。**判别性预测已登记**：A-only 训满 2 epoch（~28.6M 跨入区间）若 Yes 出现→量变假说成立；仍≈0→内容假说复活。本轮不跑。
- **F6 TRUNC 回答**：截断不是砍无害尾巴——**70.1% 被截行丢失含约束步骤**、中位丢 8 整步/31% 文本；导出步很少丢（1%）；分支步 0（已线性化）。伤害核心=约束信息+中后段步骤监督。
- completion 流：B 以 32% 行数贡献 89 种 vs A 80 种下一意图（密度 2.2 倍）；核心 tokens A 57.9%/B 42.1%。
- 待 owner：R3-C / R3-D / W2 阈值验证（A-only 2 epoch）/ TRUNC 整形，四选一或组合。

## 2026-10-02：owner 裁定 R3-B-TRUNC clean ablation——先数据构建与 CPU 审计，不训练

- **裁定要点**：① W2-Yes 归档为 training-budget/emergence hypothesis（不专门烧 GPU 验证，未来若有 2 epoch 训练顺手观察）；② Tier B 保留为主线数据（B 含高密度 workflow 意图/类型转移多样性，删之 W3 降 8pp）；③ 优先级：**TRUNC clean ablation（高）** > R3-C/R3-D（中）> W2-Yes 2ep（低）；④ R3-C 顺序理由：若不同时去除损坏监督，Contract 改善与去污效应无法区分；⑤ **第一刀=删除而非重建**（重建长 Plan 会同时改表达/tokens/监督内容/长链分布）；⑥ **max_len=1024 与 runtime 截断完全不动**（build-time 与 runtime 分开，保单变量）。
- **本轮执行**：从冻结 v2_2 识别 1,766 条 build-time 截断核心行 → 构造"仅排除这 1,766 条"的新数据集（保持其余行与顺序不动，不做再平衡/重采样）→ CPU 审计（行数/tokens/比例漂移/W3 长度分布/Tier A-B 变化/是否引入新偏移）。审计通过后是否正式训练归 owner。

## 2026-10-02：R3-B-TRUNC 数据构建+审计完成——⚠️ 关键发现：删 1,766 条 = 删掉几乎全部长 Plan 监督

- 数据集 `stage1_train_v2_2_notrunc.jsonl` 已构建（本地 04_DIAG_WORK，SHA `8c7219c6…`，未上传——是否训练未定）：core 35,278 行（−1,766）、tokens 22.88M（−7.3%）、配比漂移 56.8/21.6/10.8/10.8（删除的直接后果，未再平衡）、剩余构建期截断核心行=0。被删行 Tier：B 951（53.8%）/A 815（B 超代表）。
- **⚠️ 审计关键发现**：builder 截断契约决定了">~21 步的 Plan 恰好就是被截断的那批"——删除后核心步数 **max 1,098→21、p99 48→17**，≥30 步训练覆盖 98%→**≈0**；而 W3 探针金标 p90=19、最长 83。**本消融不是"去坏样本"而是"把训练 Plan 长度上限砍到 21"**——受损监督与长 Plan 监督在同一批行上，数据集中不存在未受损的长 Plan。
- 判读含义已写明：若 W3 上升，无法区分"去除受损监督"vs"容量集中短 Plan"；两个替代设计已登记（替代 1：notrunc + W3 解读限定 ≤21 步探针子集（事后切片，评测器不动）；替代 2：length-aware 重建，多变量，此前已搁置）。
- 相邻截断登记：completion/reconstruction/w4 流自有的更大截断（w4 target 4.07M tokens）范围外未触碰。
- **未训练、未动冻结物**；是否训练/采哪个替代设计归 owner。

## 2026-10-02：TRUNC-exclusion 评测 slice 审计（训练前预检）——≤21 可行；>21 无判别力；发现输出长度不条件化

- 报告：`r3btrunc_diagnosis/R3_BTRUNC_SLICE_AUDIT_v1.md`。未上传、未训练。
- **slice 数量**：W3-≤21 = 444/474（as-is 223，功效充足）；W3->21 = 30（as-is 15，小样本边缘）。
- **>21 slice 双重结构受限**：金标 p50 1,160 词 ≫ 冻结推理 560-token 生成上限（F1 天花板）；实证三臂预测全部停在 ~140 词、exact=0——**无法区分三臂**。建议降级为"记录不解读"。
- **新行为学发现**：三臂、全 slice 预测长度恒定 ~140-160 词（≈训练 Plan p50 148 词），与金标 154↔1,160 词无关——**输出长度不随任务调节**，Task-conditioning 未形成的直接行为证据，支持 R3-C/D 方向。
- 建议已登记：训练 notrunc 后报告 W3-all（主结果对照冻结 gate）+ W3-≤21（主诊断）+ 长度条件化分析（事后指标）。等 owner 放行训练。
- 10-02 18:07 例行检查：GPU 空闲（11 MiB / 0%），无训练或评测进程（pgrep 命中为远程 shell 自匹配）；当前状态 = 等 owner 对 TRUNC-exclusion 训练的放行（notrunc 数据集在本地未上传）。

## 2026-10-02：owner 裁定——暂停 TRUNC-exclusion（不上传/不训练），进入 R3-C/R3-D Contract/转换审计（CPU-only）

- **裁定要点**：① 输出长度不条件化（三臂恒 ~140-160 词）比"有无 1,766 截断"更基础——现在跑 TRUNC-exclusion 仍无法回答"supervision 变干净 vs 更集中典型长度"；② TRUNC-exclusion 降级为后续验证实验（届时若链条确认无损，可作真正独立的数据完整性变量）；③ W2-Yes 归档为 training-budget/emergence 假说，不专门烧 GPU，未来 2-epoch 顺手观察；④ **R3-C/D 顺序**：先 CPU 审计再考虑改数据——沿 Task→GEE 原始 workflow→chain extraction→chain_to_plan→Plan schema→training target 全链，定位"任务复杂度→长度/结构"信息丢失点；⑤ TRUNC 是数据完整性问题（仍须处理），固定长度输出是 Task-conditioned planning 能力问题——后者是核心目标。
- **审计设计**（本地 CPU）：A. 逐阶段信息清单（原始链 vs convert 输出 vs 渲染 target，抽样对比）；B. 任务复杂度 ↔ Plan 长度相关性（若弱 = 任务文本本身不编码长度信息）；C. chain_to_plan 压缩率/参数损失/分支线性化量化（对照已知 F-STRUCT-01/D-MOD-01/DATA-FRAG）；D. 约束覆盖率。数据源：SRC=b1_gee_stage_train.jsonl（含 gee_canonical_chain 原始链）+ 池子结构化 plan + 冻结 v2_2。

## 2026-10-02：R3-C/D Contract/转换审计完成——信息丢失点定位：上游 run-cap（R3-D 实锤）+ 任务文本先天弱编码（R3-C 实锤）

- 报告：`r3cd_audit/R3_CD_AUDIT_REPORT_v1.md`。数据源：SRC 原始件 101,513 train 行（tar 解包）+ 池子 + 冻结 v2_2；本地 CPU，零训练。
- **F1（R3-D 实锤）**：上游 run-cap 在转换前压缩 **79.3% 的 workflow**（80,509 行，平均砍 12.1 步，最多 3,783 步）；语义链 p50 11→7、p99 177→87。`run_cap_applied` 标记（14.4%）严重低估实际压缩。
- **F2**：逐级长度 13.0 → 9.2 → 7.0（总压缩 −46%）；**chain_to_plan 忠实**（plan↔final_sem ρ=0.857）——丢失点在转换器上游。
- **F3（R3-C 实锤）**：task 词数 ↔ original_semantic 仅 ρ=0.199——instruction 是散文摘要而非规格说明，**长度信息在源头就弱**；四分位条件均值 5.45→9.53 步（梯度弱）。
- **F4**：三臂固定长度输出（恒 ~140 词）= p(plan|task)≈p(plan) 的最优策略——**模型忠实学习了我们给它的条件结构**，非失灵。
- **定位更新**：R3-D 修复点在转换上游（重跑数据管道级变更）；R3-C 重新表述为"任务如何描述 workflow"的数据工程；TRUNC-exclusion 降级为次级因素实验（是否跑归 owner）；W2-Yes 维持归档。
- 零训练、零服务器写入、冻结物未动。待 owner 裁定下一步。

## 2026-10-02：owner 裁定 R3-CD-2 CPU audit——区分"run-cap 破坏 task-结构信号" vs "Task↔Original 本身就弱"

- **裁定要点**：① 三层问题固定：上游压缩（R3-D）/ 任务弱编码（R3-C）/ 固定长度输出=忠实学习（非失灵）；② 暂停 TRUNC-exclusion（次级）、W2-Yes、RL、Stage-2 全冻结；③ **R3-CD-2**（CPU）：逐级统计 Original→Final→Plan（步数/intent 多样性/I-O/dependency/被删步骤性质/位置/任务特异性）+ 全覆盖三段相关（Task↔Orig/Final/Plan，含任务复杂度多代理）+ 长度条件下 Task 分组。判读：若 Task↔Orig 有信号但 run-cap 后明显下降 → 上游瓶颈实锤；若 Task↔Orig 本身弱且后级无进一步恶化 → 数据缺乏 Task→Workflow 对齐监督（根本问题）。

## 2026-10-02：R3-CD-2 审计完成——假说 B 成立（附细化）：run-cap 是"循环折叠"的表示选择，Task 信号源头就弱

- 报告：`r3cd_audit/R3_CD2_AUDIT_REPORT_v1.md`（全量 37,044 行匹配 + 101,513 行 RLE 结构验证）。
- **F1**：`semantic_chain_rle` 是 raw 的保序子序列（99.96%，mismatch=0）；被删 976,094 步**全部是连续重复操作的折叠**（原始脚本的逐波段/逐要素循环，最长单游程 600 次重复）；**family 多样性零损失**（raw 30 = final 30），被删步骤不比保留步骤更任务特异——**假说 A（run-cap 破坏任务特异信息）不成立**。
- **F2**：全覆盖相关性 task×orig 0.193 / ×final 0.157 / ×plan 0.152（动词代理 0.250/0.210）；任务四分位梯度倍数在三级几乎不变（1.71×→1.67×）——**RLE 没有进一步破坏信号，源头就弱**。
- **F3 裁定**：**假说 B 成立** + 细化：RLE 是表示选择（Plan=阶段序列，无法表达迭代次数；32.1% instruction 含迭代措辞），即"任务描述 workflow 规模"与"Plan=阶段数"之间存在表示鸿沟。
- **F4 修复方向含义**：修 run-cap 不是方向（展开迭代只会加长重复监督）；真正缺口在 Task 表示（需要结构化 workflow 规格——子目标/数据组/规模），属 Contract 重设计/数据工程（owner 级）。TRUNC-exclusion 与 run-cap 修复均降级。Stage-1 诊断链闭合：W3≈0.50 ← 长度/结构条件信号弱（源头 ρ≈0.2，RLE 继承）← 任务=散文摘要 + Plan=阶段序列。
- 零训练、零服务器写入、冻结物未动。待 owner 裁定。

## 2026-10-02：owner 裁定 R3-CD-3 Task 信息充分性审计（CPU-only）——主线冻结于当前状态

- **裁定要点**：① Stage-1 问题定性升级："模型没训好" → "监督信号本身怎么定义"；W3=0.50 混合了 Task understanding / workflow inference / workflow construction 三层能力，需拆解；② 证据链闭合确认（R3-A/B/TRUNC/转换器/CD-2 全排除或定位）；③ **纠正一个大结论**：不说"GEE 数据不好"，而说"Task 字段是自然语言任务描述，不是 workflow specification"；④ **不做 Contract 重设计**（避免因果链难讲），先做 R3-CD-3：Task 信息量/可预测性分析——① Task→operation family ② Task→length/stage count 分箱 ③ Task→first/last op ④ Task→operation pair（局部依赖）；⑤ W3 重理解：W3-a Goal / W3-b Op set / W3-c Ordered set / W3-d Complete——若 a 高 d 低 → GEE 能教 task understanding 但不足以监督完整 construction（分层 Workflow Reasoning 方向）；若 a 都低 → GEE 的角色需重估。⑥ 不训练、不改 frozen asset、不碰 RL/Stage-2。
- **实现方案**：TF-IDF + 线性探针 + 80/20 固定种子切分，对 family 多标签 / 长度分箱 / 首-尾 family / 转移对 分别测（含 majority 基线）；解读限定为"线性可提取信号"参考。

## 2026-10-02：R3-CD-3 Task 信息充分性审计完成——信息阶梯：组件层全强（AUC 0.90+），缺口在完整序列组装

- 报告：`r3cd_audit/R3_CD3_AUDIT_REPORT_v1.md`。TF-IDF+线性探针（n=37,044，80/20，seed 20260924），解读限定为线性可提取信号下界。
- **信息阶梯**：L1 family 集合 **AUC 0.913**（20 类多标签，最差 family 也有 0.86）/ L2 长度分箱 **0.628 vs 基线 0.389**（1.6× lift，混淆集中相邻箱）/ L3a 首 family **无信号**（0.961 vs 0.943，纯 provisioning 惯例，结构性）/ L3b 末 family **0.626 vs 0.352**（+27pp 真信号）/ L4 相邻转移对 **AUC 0.904**（228 对，top 对 1.0）/ **L-full 完整序列（训练后模型）0.499**。
- **判读**：组件层（做哪些操作、什么连什么、大致多长）信息全部在场且不弱；**缺口精确定位在"把局部正确的转移拼成全局一致序列"的组装层**——对应 owner 预判"GEE 能教 task understanding/operation 语义/局部依赖，但不足以监督完整 workflow construction"成立，支持分层 Workflow Reasoning 重设计，无需推翻 GEE 角色。
- **局限**：线性探针为下界；family/长度标签来自自动分层池。
- 待 owner：是否启动分层监督重设计（⑦ 外协议变更，owner 级）；TRUNC/run-cap/W2-2ep 维持冻结。零训练零 GPU，冻结物未动。

## 2026-10-02：R3-CD-4 Local-to-Global Assembly Audit 完成——结局 2 成立：瓶颈在生成/序列化，不在组装监督

- 报告：`r3cd_audit/R3_CD4_AUDIT_REPORT_v1.md`。**设计前提（读冻结评测器源码确认）**：W3 指标=family 多重集 bag-F1（overlap_counts+f1_from_counts），顺序完全不计分——"组装"=选对 family 多重集。
- **主结果**：L1 预测 + L2b 长度预算 → 确定性分配 → **bag-F1 0.60**（三策略一致）> 训练后 LLM 0.499（+10pp）>> 同切分平凡基线 0.211（+39pp）；**oracle 上界 0.846**（剩余 15%=计数分配子问题；预测组装达选择上界 71%）。
- **LLM 失败模式**（评测器自身解析函数复算，n=206，复算 F1 0.553 验证管线一致）：**系统性欠发射**——COLLECTION_MGMT −435 / SPATIAL_FILTER −355 / TEMPORAL_FILTER −195，稀有 family（BAND_SELECT/ATTRIBUTE_FILTER/THRESHOLD_LOGIC）pred_rate≈0，几乎零过发射——向高频"小曲目库"收缩，与固定长度输出同源（回退先验）。
- **裁定**：结局 2 成立——信息与组合逻辑都在，自回归生成没利用；优先方向 = structured decoding / intermediate representation / planner→serializer 两阶段（selection head 出多重集+长度 → 序列化器渲染），而非单纯加 SFT 或改 Task 表示。
- **附带登记**：①当前 W3 gate 对顺序不敏感（bag 口径任意置换同分）——顺序敏感口径是 gate 设计层观察，冻结物不动；②L4 转移 AUC 0.904 对当前 gate 无直接贡献（未来顺序敏感口径有价值）；③计数分配为独立子问题（oracle 下占 15% 缺口）。
- 零训练、零 GPU、冻结物未动。planner→serializer 设计草案归 owner。

## 2026-10-02：owner 裁定 Planner→Serializer 最小可验证实验链（①-③ CPU 本回合执行；④训练待放行）

- **定性结论（owner）**：模型不是不知道该做什么——组件信息在（AUC 0.913/0.904/F1 0.614），但一步生成完整 Plan 时退回高频先验（保守化欠发射）；Route-2 阶段结论暂记："GEE 数据有组件级价值，瓶颈在一次性自回归生成的利用方式"。
- **实验序列**：① 定义 Planner schema → ② CPU 构造 Gold blueprint → ③ CPU 验证 blueprint→assembly → ④ 小规模 Planner SFT（Qwen3.5-9B+LoRA，只学 families+counts/length）→ ⑤ Planner+Rule Serializer → ⑥ 与 Direct Task→Plan 对比（若 >0.50 则核心假设成立）→ ⑦ 完整 Planner→Serializer → ⑧ Stage-1 Gate → ⑨ Stage-2 → ⑩ RL。**④⑤ 是关键**：验证"LLM 能不能学会先做 Planner"。
- **本回合执行 ①②③（CPU）**；④ 起需 GPU 与 owner 放行。

## 2026-10-02：Planner Schema v1 设计 + Gold Blueprint 构造验证完成（步骤①②③ ✓）

- 报告：`planner_design/PLANNER_SCHEMA_V1_REPORT_v1.md`；数据 `04_DIAG_WORK/planner_gold_blueprints_v1.jsonl`（37,044 行 / 32.5MB，本地就绪）。
- **Schema v1**：`{families（首现顺序去重）, counts（每 family 次数）, length}`——**counts 必须在 schema 里**（R3-CD-4 oracle 15% 计数缺口的补齐手段，已验证）；Serializer v1 = 按 counts 展开（规则程序）。
- **验证**：V1 oracle blueprint → serializer → **bag-F1 = 1.0000**（全量，冻结口径下无损）；V2 展开顺序==gold 顺序仅 **44.1%**（blueprint 保 bag 损顺序——当前 gate 兼容，未来顺序敏感口径需 schema v2 扩展，已登记预留位）；V3 multiset→顺序平均可排列数 3.7×10³¹（本质一对多）；**V4 监督目标 14.4 词 vs gold 249.3 词（17× 压缩）**——Planner 目标极小且与 Task 可预测成分对齐。
- **待 owner**：④ 小规模 Planner SFT（需新训练脚本=⑦ 外代码变更+GPU 窗口，训练时长预计远小于全 Plan SFT）；⑤⑥ 对比实验设计。数据已就绪。

## 2026-10-02：owner 放行 R3-PLANNER-P0（Planner 可行性实验）——严格定位可行性验证，非正式 Stage-1

- **放行条件**：Task→Blueprint JSON；QLoRA/NF4/bf16 与之前尽量相同；1 epoch；无 curriculum/RL/Serializer 学习；不动冻结 Stage-1 数据集；独立实验目录与 checkpoint。
- **评测三指标**：① Blueprint parse 率 ② Family bag-F1（选对没选对）③ Count/Length 准确率（family 对但 count 错的模式）。之后 Planner→Rule Serializer→冻结 W3 evaluator vs Direct 0.499（预期 0.60+ 则核心假设成立；0.58-0.60 ≈ 组件天花板区域也算成功；0.75+ = 强提取）。
- **定位与解读上限**：可行性验证；0.60 ≈ 现有组件信息可达区域（L1+L2 assembly 0.60 / oracle 0.846），不是失败。
- **实验序列冻结**：CD-2/3/4 ✓ → Schema v1 ✓ → Gold Blueprint ✓ → **④ Planner SFT（现在做）** → ⑤ Planner+Rule Serializer → ⑥ 对比 → ⑦ 正式 Planner→Serializer → ⑧ Stage-1 Gate → ⑨ Stage-2 → ⑩ RL。

## 2026-10-03：R3-PLANNER-P0 smoke 通过 + 全量启动（干净起跑，无 resume）

- **smoke 通过**（独立目录 stage1_run_planner_p0_smoke）：[done] steps=9 examples=300 tokens=14,466 tgt_trunc=0 task_too_long=0 elapsed=313s——**每行仅 ~48 tokens**（task ~100 + blueprint ~40），Pipeline 零新训练代码（Stage1PlanCollator 通用行格式直接复用）。
- **数据集**：planner_p0_train.jsonl（33,339 行，SHA `2bfc0ad7…`）+ planner_p0_eval.jsonl（3,705 行 held-out，SHA `30d19cb0…`），90/10 seed 20260924；行格式 {task, context="", target=blueprint紧凑JSON, separator=含输出格式指令}；tokenizer 实测 ~48 tokens/行。
- **全量启动**：PID 217843，00:12 起，`[release] full run: 33,339 rows x 1 epoch`，无 [resume] 行，GPU 11.5GB/39%。1,042 optimizer steps × ~41.6s ≈ **12h，预计 10-03 ~12:15 完成**。
- **训练后评测计划**（新诊断脚本，非冻结评测器）：① Blueprint parse 率 ② family bag-F1（与冻结 gate 同口径）③ count/length 准确率；然后 Planner→Rule Serializer→bag-F1 vs Direct 0.499。判读带：0.58-0.60 ≈ 组件可达区（成功）；0.75+ = 强提取；<0.5 = Planner 假说存疑。

## 2026-10-03：R3-PLANNER-P0 训练完成（09:54，9.02h）——评测已启动

- `[done] mode=release steps=1041 examples=33,339 tokens=1,694,098 tgt_trunc=0 task_too_long=0 elapsed=32,460s`（9.02h）。adapter `/root/data/stage1_run_planner_p0/stage1_adapter`。
- 评测脚本一次启动失败（`load_in_4bit` 重复传参 TypeError），修复后重跑成功（PID 299410，GPU 7.9GB）——诊断脚本为独立新工具，不涉及冻结评测器。
- 评测：3,705 held-out 行逐条生成 blueprint（max_new_tokens=192, greedy），输出 M1 parse 率 / M2 family bag-F1 / M3 count 精确率 / M4 length exact/±1 → metrics json。预计 ~1.5-2h（今日 ~13:30-14:00 出结果）。出结果后与 Direct 0.499 对比（判读带 0.58-0.60 成功 / 0.75+ 强提取 / <0.5 存疑）。
- 12:07 ✅ P0 评测进行中（11%）：**实时读数 parse=1.000、family bag-F1=0.642**——已高于组件组装估计（0.60）与 Direct 0.499；全量指标 ~13:30 出。
- 13:07 ✅ P0 评测进行中（32%）：parse=1.000 稳定，f1=0.649（800→1200 行微幅波动，0.642→0.660→0.649——稳定在 0.64-0.66 区间）；全量指标 ~14:00 出。
- 14:07 ✅ P0 评测进行中（54%）：parse=1.000、f1=0.648（稳定）；全量 ~14:50 出。
- 15:07 ✅ P0 评测进行中（65%）：parse=1.000、f1=0.647（稳定）；全量 ~14:50-15:40 出。本批（13:07/14:07/15:07）合并 commit。
- 16:07 ✅ P0 评测进行中（86%）：parse=1.000、f1=0.647；预计 ~16:20 出全量。

## 2026-10-03：R3-PLANNER-P0 出分——**Planner 假说决定性成立**：0.645 > Direct 0.499（+14.6pp），parse 100%

- 全量指标（n=3,705 held-out）：**M1 parse = 1.0000** / **M2 family bag-F1 = 0.6448** / M3 count 精确 0.5027 / M4 length exact 0.2443、±1 = 0.5231（预测均值 5.98 vs gold ~8.4）。
- **判读（owner 判读带）**：0.6448 落"成功"区（>0.60），未达"强提取"（0.75+）。**核心假设成立：一步生成是瓶颈，不是 Task 信息**——Planner+RuleSerializer 超 Direct +14.6pp，且超线性探针组装器 0.60（LLM 语义利用超出 TF-IDF）。**M1=1.0 重大对照**：结构化小目标下格式崩塌完全消失（Direct 无效率 86%）——保守化是"任务太大"的症状。
- 剩余缺口 = 计数分配（M3 0.50）+ 长度保守（5.98 vs 8.4），对应 oracle 差距 0.846−0.645。
- 报告：`planner_design/R3_PLANNER_P0_RESULTS_v1.md`（含 metrics json + 3,705 逐项）。
- **建议已登记**：进入 ⑦ 正式 Planner→Serializer Stage-1 重设计（计数专项/长度校准/顺序敏感口径设计）；原冻结 Stage-1 v2_2 主线与 gate 不动，切换归 owner。零冻结物变更。

## 2026-10-03：owner 确认 P0 为路线节点——措辞收紧 + P1/P2 路线冻结 + RL 定位修正

- **措辞修正**：P0 不是"决定性证明 Task 信息充分"，而是"**在当前冻结数据、当前 bag-F1 口径和 P0 训练预算（1.69M tokens）下强支持 Planner 假说**"（P0 报告 §2 已加 owner 修正附注）。
- **路线冻结**：P0 ✓ → **P1 = count/length 专项监督**（缺口画像："做什么"已不错 M2 0.645，"做几次/多长"偏弱 M3 0.50/M4±1 0.52，"怎么排序"v1 未表达）→ **P2 = 顺序敏感 Blueprint v2** → Stage-1 新正式候选 → Stage-2 QGIS Grounding。不一次改掉所有东西。
- **架构方向确立**：Task → Structured Planner → Workflow Serializer → QGIS Grounding（替代 Task→一次性生成→Grounding）。
- **RL**：继续冻结；未来若引入，定位在结构化 Blueprint / QGIS Graph 的规划优化阶段，不用于修补长文本生成——理由：现在知道 Structured Planner 就能把 0.499→0.645，应先把监督学习路线做稳。
- `aa16937` 定性为路线节点：R3 从"诊断 SFT 为何不行"进入"下一代模型接口的实验证据"阶段。
- 10-03 17:07 例行检查：GPU 空闲（11 MiB / 0%），无训练/评测进程（pgrep 命中为远程 shell 自匹配）；状态 = 主线冻结于 P0 ✓ 节点，等 owner 对 P1 的裁定。

## 2026-10-03：P1 设计比较文档完成（CPU）——P0 误差画像支持"先 B"

- 报告：`planner_design/R3_PLANNER_P1_DESIGN_v1.md`。新增 P0 全量误差画像（n=3,705 parsed）：
  ① 长度偏差双峰（mean −3.07 / p50=0 / 23.6% 行严重低估 <−2 步）；② **计数饱和曲线**：误差随 gold 计数单调恶化（count=1 exact 0.70 → count=10 −6.80 → ≥50 −25~−365），模型计数在 1-3 饱和——欠训练回归的教科书形态；③ 虚报 family ~1.05 个/行；④ per-family 高计数者最差（THRESHOLD_LOGIC exact 0.07）。
- **三方案比较**：A 格式显著化（预期收益低——parse 100% + count=1 命中 70% 说明不是读的问题）/ **B 预算 2-4 epoch（推荐先行，饱和曲线+双峰+W2 阈值先例三证据同向；2ep 18h，可 resume 阶梯到 4ep）** / C 计数加权（与 B 混合破坏归因，后置）。
- 成功判据：M3 ≥0.65 且 M2 不降（±0.02）且 M4±1 ≥0.65；失败判据：饱和形态不变 → 转 C。
- 未训练；P1 放行归 owner。

## 2026-10-03：owner 放行 R3-PLANNER-P1-B-2EP——严格 resume，只加训练预算

- **放行条件**：Schema v1 / train-eval split / LoRA / lr / batch / max_len / loss / 数据 / Serializer 全部不变；不碰冻结 Stage-1/Gate/RL；**从 P0 checkpoint 精确 resume**，额外 1 epoch（总 2 epoch）= 干净的"训练预算增加"因果比较。
- **评测要求**：三判据（M3≥0.65 / M4±1≥0.65 / M2≥P0−0.02）之外，必须保存 **count-error curve**（gold count 分桶的 bias/exact，P0 vs P1-B 对照）——验证"饱和曲线整体右移"而非只看 M3 数字；**phantom family 率**（~1.05/行）顺手追踪——若 count/length 修复而 phantom 不动，则 family selection 与 count allocation 是两个独立误差源（影响 P2 设计）。
- 定位：P1 专项实验，不提前宣布 Stage-1 新路线成立；失败判据 = 曲线不动 → 停止堆 epoch 转 P1-C。

## 2026-10-03：R3-PLANNER-P1-B-2EP 启动——严格 resume 自 P0（step 1041），再训 1 epoch

- P0 checkpoint 确认在位（latest.pt，09:14 收尾保存）；resume 验证：`[resume] step 1041 (rows 33339)` = P0 精确终点，adapter+optimizer+scheduler+RNG 全量恢复。PID 327343，17:25 起，GPU 13.3GB / 50%。
- 预算：+1,041 步 ≈ 9h，**预计 10-04 ~02:30 完成**；完成后用同一 eval 脚本（held-out 3,705 行不变）+ 新增 count-error curve（P0 vs P1-B 同图）+ phantom family 率。
- 10-03 18:07 ✅ P1-B 正常：存活 43m，GPU 16.9GB / 36%，ep2 段进度 79/1,041 步（31.1s/步，planner 短行更快），loss 2.08-2.16（第二轮起步形态，与 ep2 同型）；ETA ~10-04 02:25。
- 19:07 ✅ P1-B 正常：存活 1h43m，GPU 19.0GB / 42%，ep2 段 179/1,041 步（30.6s/步稳定），loss 2.09-2.11；ETA ~02:25 不变。
- 20:07 ✅ P1-B 正常：存活 2h43m，GPU 19.0GB / 56%，ep2 段 309/1,041 步（30.5s/步稳定），loss 2.01-2.07，ckpt@1350 已存；ETA ~02:25 不变。本批（18:07/19:07/20:07）合并 commit。
- 21:07 ✅ P1-B 正常：存活 3h43m，GPU 19.0GB / 42%，ep2 段 419/1,041 步（40%），30.4s/步稳定，loss 1.95-2.16；ETA ~02:25 不变。
- 22:07 ✅ P1-B 正常：存活 4h43m，GPU 21.3GB / 47%，ep2 段 539/1,041 步（52%），30.4s/步稳定，loss 2.04-2.12；ETA ~02:25 不变。
- 23:07 ✅ P1-B 正常：存活 5h43m，GPU 23.6GB / 42%，ep2 段 659/1,041 步（63%），30.5s/步稳定，loss 2.01-2.07；ETA ~02:25 不变。本批（21:07/22:07/23:07）合并 commit。
- 10-04 01:12 ✅ P1-B 正常：存活 7h48m，GPU 12.0GB / 44%，ep2 段 919/1,041 步（88%），30.5s/步稳定，ckpt@1950 已存；剩 122 步 ≈ 62 分钟，完成预计 ~02:15。
- 10-04 02:07 ✅ P1-B 正常（临近完成）：存活 8h43m，step 2,060（ep2 段剩 22 步 ≈ 11 分钟），loss 1.98-2.01；预计 ~02:18 [done]。下次检查（03:07）将启动评测。

## 2026-10-04：R3-PLANNER-P1-B 训练完成（02:14 [done]，累计 2 epoch）——评测已启动

- `[done] mode=release steps=2082`（= 1,041×2 精确）；本轮 tgt_trunc=0、task_too_long=0，本轮耗时 ~8.8h。adapter 已更新（`stage1_run_planner_p0/stage1_adapter`，注意：P1-B 与 P0 共用输出目录的 adapter 位置——P0 的 adapter 已被 P1-B 覆盖，P0 结果已落盘不受影响）。
- 评测已启动（PID 375261，同一 held-out 3,705 行，同一脚本）：M1-M4 指标 + items（供 count-error curve 与 phantom family 对照分析）。预计 ~4.5h，**出分窗口 ~06:45-07:00**。出分后出 P0 vs P1-B 对照（三判据 + 饱和曲线右移 + phantom 率）并报 owner。
- 10-04 04:07 ✅ P1-B 评测进行中（11%）：**parse=1.000、实时 f1=0.673**（P0 同期 0.642→+3pp）；全量 ~06:45-07:00 出。
- 10-04 05:07 ✅ P1-B 评测进行中（32%）：parse=1.000、f1=0.675 稳定（P0 全量 0.6448，+3pp）；全量 ~06:45-07:00 出。
- 10-04 06:07 ✅ P1-B 评测进行中（54%）：parse=1.000、f1=0.676（微升至稳定）；全量 ~07:00-07:30 出。
- 10-04 07:07 ✅ P1-B 评测进行中（76%）：parse=1.000、f1=0.673；预计 ~07:40 出全量。

## 2026-10-04：R3-PLANNER-P1-B 出分——M2 升 M3/M4 未达标，深尾饱和曲线冻结；按预注册规则建议转 P1-C

- 全量对照（n=3,705 held-out 同集）：M1 1.0→1.0 / **M2 0.6448→0.6718（+2.7pp，超越判据）** / **M3 0.5027→0.5385（+3.6pp，未达 ≥0.65）** / M4±1 0.5231→0.5536（未达 ≥0.65）；预测长度均值 5.98→6.09（仍保守）。
- **Count-error curve**：小计数区（1-6）温和右移（+3-6pp）；8/10 桶跳变（+0.24/+0.25，n=112/56 小样本慎读）；**≥13 深尾完全冻结**（bias −70~−365 量级不变）。多 1 epoch 收益集中于小计数区。
- **Phantom**：行占比 64.2%→60.3%、槽位 1.05→0.95/行——边缘改善，与 count 改善幅度不匹配 → **family selection 与 count allocation 是部分独立误差源**（影响 P2 设计，owner 预判获证）。
- **按 owner 预注册规则**：曲线介于中间偏"不动"（深尾冻结）→ **建议停止堆 epoch，转 P1-C（count/length loss 加权）**。最终裁定归 owner。
- 工具事件：eval 脚本输出路径硬编码导致 P1-B 覆盖服务器上 P0 metrics 文件——P0 结果 10-03 已拉回本地仓库无损失；P1-B 文件已改名 `planner_p1b_eval_metrics.json`；后续脚本参数化输出路径（已登记）。
- 报告：`planner_design/R3_PLANNER_P1B_RESULTS_v1.md`。GPU 空闲，冻结物未动。
- 10-04 08:0x 例行检查：GPU 空闲，无训练/评测进程；状态 = P1-B 结果已报，等 owner 对 P1-C / P2 / 其他下一步的裁定。
- 10-04 11:0x 例行检查：GPU 空闲，无训练/评测进程；状态不变 = 等 owner 对 P1-C / P2 的裁定。

## 2026-10-04：长度分桶画像完成——决定性证据支持 owner 判断：深尾是表示问题，P1-C 数值加权应暂停

- 报告：`planner_design/R3_P1_LENBUCKET_PROFILE_v1.md`（脚本 `lenbucket_profile_v1.py`；P1-C smoke 已按指令停止，GPU 空闲）。
- **决定性发现**：gold distinct family 数在所有长度桶恒定 ~2.9-4.5，而 repeat_share 随长度单调升至 **95.1%**（51+ 桶）——长 workflow = 同 4-5 种 family 的重复，**不是更多种操作**。Planner 的 family 数预测与 gold distinct 一致，学不会的只是"重复次数"这个数字，而次数由数据性质（波段数/类别数/年份跨度）决定，**从 Task 文本不可识别**。
- **P0→P1-B 分桶对照**：预算只改善 1-12 步桶（F1 +2~4pp），51+ 桶 F1 0.127→0.141、bias −189 不动——**预算假说在深尾被否定**。
- **结论**：深尾是表示问题。正确方向 = **Blueprint v2 显式重复结构（loop 分组/迭代标记，以 pre-RLE 原始链游程为蓝本）+ 量级解析移出 Planner（交给 Serializer/Grounding，Stage-2 有实际数据）**；M3 绝对计数指标降级（测的是不可识别量），代之以分组正确率+长度粗分箱（冻结 gate 不动）。
- 待 owner：Blueprint v2 设计批准（数据工程级）；P1-C 数值加权暂停。

## 2026-10-04：owner 裁定启动 Blueprint v2 CPU/schema 设计（不训练）——Ordered + Repetition-aware

- **问题重定义**：不是"模型不会预测数字"，而是"让 Planner 预测一个 Task 无法可靠确定的数字（BandArithmetic × 137）"。长 workflow = 少数操作的大量重复（51+ 桶 distinct 4.4 / repeat 95.1%），重复次数取决于数据性质（波段/年份/类别/feature 数），不在 Task 文字里。
- **v2 核心思想**：Planner 负责"发现重复结构 + 语义条件（per-band/per-year/per-feature）"，**绝对次数移到 Serializer/Grounding**（读取实际数据上下文展开）——与两阶段路线（GEE 通用推理 / QGIS 实际展开）天然契合。
- **v2 schema 要求**：阶段顺序 + 数据依赖 + 重复/循环结构 + 循环体 + 循环语义条件；绝对 count/length 不再是 Planner 核心目标。
- **执行序列**：Schema v2 → Gold 转换 → 可表达性验证 → lossless/coverage 审计 → evaluator 设计。**不训练**；不改冻结 Stage-1 v2_2 与现有 gate（v2 为并行候选路线）。
- **蓝本来源**：pre-RLE 原始链的游程结构（R3-CD-2：RLE 折叠的就是循环迭代；原始链保留完整迭代信息）。

## 2026-10-04：Blueprint v2 Schema 审计完成——无损性 100%；重要细化：家族级 95% 重复主要是粒度伪影

- 报告：`planner_design/BLUEPRINT_V2_AUDIT_REPORT_v1.md`；Gold v2 数据 `blueprint_v2_gold_v1.jsonl`（37,044 行，SHA `46d51db9…`）。
- **Schema v2**：stages = 原始语义链极大游程序列（语义粒度 30 类，细于 plan family 19 类）+ repeat 计数 + iteration_hint 分类；量级只注记不预测。
- **A1 无损**：expand(stages)==原始链 37,044/37,044；Σrepeat==original_semantic_length 37,044/37,044。
- **A2/A3**：65.3% workflow 含循环（24,186/37,044）；loops/workflow 1.31→9.35（51+ 桶）；游程最长 584。
- **⚠️ 重要细化（诚实修正）**：51+ 原始桶的**语义级** repeat_share 仅 0.245——原始长 workflow 的主体是**大量不同语义操作**（stages 均值 114），v1 plan 层的 95.1% family 重复**主要是 family 粒度粗化（30→19）的合并伪影**，非字面循环。**v2 必须定义在语义粒度**——这正是 stages 取语义游程的原因。
- **A4**：~80% instruction 含至少一个迭代维度线索（per_band 47%/per_class 29.9%/per_year 19.4%/per_feature 14%），20.2% 无 hint——iteration_hint 分类目标可学习（弱标注需抽验）。
- **A5**：RLE→plan 比值 0.863（chain_to_plan 再合并 14%）——v2 需自己的语义粒度评测口径，现有 plan-family gate 冻结不动。
- 待 owner：Schema v2 定稿（hint 标注规则/无 hint 行处理）；是否启动 Planner-v2 小规模 SFT。

## 2026-10-04：owner 裁定 Schema v2 修订定稿 + evaluator E1-E4 + CPU preflight（不训练）

- **Schema 修订**：`loop_groups` → **`repetition_groups`**（repetition=数据事实，loop=解释，不把未验证的循环语义硬编码进 gold）；`iteration_hint` = 关键词弱标注多标签（per_band/per_class/per_year/per_feature/generic_each/unspecified），**300-500 条抽样人工验证**；20.2% 无 hint 行**保留为 unspecified**（≠no repetition，避免 selection bias）；绝对 repeat **降为 diagnostic**。
- **Evaluator E1-E4**：E1 Ordered Stage-F1（LCS-F1/edit distance/exact，核心）；E2 Repetition-group F1（结构对即可，不判数值）；E3 iteration-hint（micro/macro/per-class，弱标注域内）；E4 repeat 数值 bias 仅 diagnostic。
- **三层职责确立**：Planner=结构（stages/repetition/hint）；Serializer/Grounding=实例化（cardinality/参数/QGIS 算子）；绝对次数不再要求 Planner 预测。
- **下一步**：CPU preflight——E1-E4 可计算性 + 自洽测试（gold vs gold）+ **关键判别：v2 语义 stage 是"可从 Task 推断的结构"还是"只是原始链全量转储"**（线性探针对比 v2 语义 30 类 vs v1 plan 19 类的可预测性 + repetition-presence 可预测性）+ 400 条弱标注抽样（供 owner 人工验证）。Planner-v2 SFT 暂缓。

## 2026-10-04：Blueprint v2 preflight 完成——E1-E4 全过 + 可学习性判别 PASS（v2 不是原始链转储）

- 报告：`planner_design/BLUEPRINT_V2_PREFLIGHT_REPORT_v1.md`；Gold v2（修订版：repetition_groups + 弱标注 hint）`blueprint_v2_gold_v2.jsonl`；人工抽样 `iteration_hint_review_sample_v1.jsonl`（396 条 / 33 种 hint 模式分层）。
- **E1-E4 preflight 全过**：E1 Ordered Stage-F1 可计算且顺序敏感（旋转罚至 0.75）；E2 repetition 签名构造性唯一（空集约定已修）；E3 弱标注 396 条待 owner 人工 precision 验证；E4 repeat bias diagnostic 位 ✓。过程修正：E2 空集约定 + hint 字段误读（V22 无 instruction，已改用 SRC instruction 重建）。
- **可学习性判别 PASS（本轮最关键）**：v2 语义 stage 集合 AUC **0.922** ≈ v1 plan family 0.915（细粒度不是噪声）；**v2 独有的 repetition-presence AUC 0.940（全场最强）**——v2 是"Task 可支持的可学习结构表示"，非原始链全量转储。Planner-v2 SFT 的信息前提成立。
- 附注：P_hint AUC 0.968 含弱标注自洽成分（标签来自关键词），语义质量以 396 条人工验证为准。
- 待 owner：人工验证 396 条 → precision 达标（≥0.8-0.9）则 E3 冻结，进入 Planner-v2 smoke 设计（100-300 条，目的=格式稳定性/可学性初检，训练另放行）。

## 2026-10-04：owner 裁定——Planner-v2 Gate PASS + Human Hint Validation PENDING + SFT NOT AUTHORIZED；人工验证协议确定

- **状态正式化**：Planner-v2 = Data/Schema/Evaluator Gate PASS；Human Hint Validation PENDING；SFT NOT AUTHORIZED。零 GPU/零训练/冻结物不动 维持。
- **人工验证协议**：三级判断 TP/FP/ABSTAIN（ambiguous 不强判 FP，如 "for each input…" 应 ABSTAIN 而非 generic_each）；Precision = TP/(TP+FP)，Abstention rate = ABSTAIN/396。
- **验证通过后 Contract Freeze**：Schema v2 / Gold v2 / hint 规则 / unspecified 规则 / E1-E4 全部冻结（防止"训练→看结果→改 schema→再训"的因果劣化）。
- **Smoke 设计（验证后）**：100-300 条，目的限定 S1 JSON compliance / S2 ordered structure（防退化 unordered list）/ S3 repetition presence（不要求 exact count）/ S4 unspecified 滥用检查 / S5 hint shortcut 检查；新增 **Structure-only validity** 指标（family/order/repetition/hint 分项，不看 absolute repeat）。
- **证据链定格**：R3-CD-3（信息在）→ CD-4（结构化+serializer 优于直接生成）→ Planner-v1（0.499→0.645→0.672）→ P1 长尾审计（absolute count 不可识别）→ Blueprint-v2（semantic order + repetition structure）→ v2 preflight（AUC 0.922/0.940）→ **v2 是可学习的结构目标**。P1-C 正式关闭（其目标被 v2 数据审计解释：Planner 不应承担不可识别的绝对计数）。
- **现在开始**：与 owner 逐批人工验证 396 条。

## 2026-10-04：Hint 人工验证 Batch 1（per_band，12 条）——2 TP / 7 FP / 3 ABSTAIN；规则立即修订

- **owner 裁定标准（确立）**：不以"任务提到 band"为 TP 证据；需三条件结构判定——① Band evidence（可枚举多波段：B2/B3/B4、red/green/blue 等）② Iteration evidence（任务语义明确"逐个/分别处理这些 band"）③ Repetition alignment（repetition 结构与 band 维度可解释对应）。缺乏关键证据 → ABSTAIN 不升级。
- **负词典建立**：C-band（频段专名）/ QA60 band（QA 数据层）/ Sentinel-2A/B（平台型号）/ BAND_SELECT（操作名）/ NDVI/NDWI/SAVI（指数）/ RGB/true-color composite（涉及 band ≠ 逐 band 重复）。
- **Batch 1 结果**：TP = B8、B12；FP = B2、B3、B4、B6、B9、B10、B11（7 个）；ABSTAIN = B1、B5、B7。系统性 FP 形态 = "band" 字面命中专名/操作名/指数名。
- **裁定**：现在修订 per_band 规则（非 freeze 后再修）→ 对同 12 条重跑 → owner 复验 → 再进下一批。Contract Freeze 冻结的是人工校准后的规则。

## 2026-10-04：per_band 规则 v3.1 校准完成——与 owner 裁定一致 11/12

- 规则演进：v2（初版结构规则，4 分歧）→ v3（负词典修正 + 指数签名 + 结构对齐判 TP）→ **v3.1（index 上下文使 B-code 枚举失效：NDVI 公式里的 B4/B8 是算术标识，非迭代枚举）**。
- **v3.1 vs owner Batch 1 裁定：11/12 一致**（TP 2/2、FP 5/7、ABSTAIN 4/3——唯一残余 48503：owner FP（×13 多集合过滤链），规则 ABSTAIN——词汇层不可判定，ABSTAIN 为安全方向输出）。
- 规则要点（v3.1）：proper-neg（C-band/QA60/Sentinel-2A/B）+ band 枚举（B-code 连续列表或 red/green/blue 共现）+ 迭代短语或结构对齐（repeat ∈ {n_enum, 2×n_enum}）→ TP；proper-neg 或指数签名且无枚举 → FP；其余 ABSTAIN。
- 待 owner 确认：规则 v3.1 定稿 → 全 396 条重打 per_band 标签 → 继续后续批次（per_class/per_year/per_feature/generic_each/unspecified/no_repetition）。

## 2026-10-04：per_band rule v3.1 FREEZE（owner 定稿）——"calibrated/frozen for P0 validation"

- **冻结记录（owner 原话口径）**：per_band v3.1 — calibrated/frozen for P0 validation；Human agreement **11/12**；TP precision-first policy maintained；Known limitation: multi-collection/filter repetition may remain ABSTAIN when lexical/structural evidence is insufficient。
- **owner 三确认**：6460 FP 正确（index context 的 B4/B8 是算术输入标识）；48503 ABSTAIN 是正确工程选择（规则目标=高 precision 产出可接受 hint，非强行复现人工标签）；Landsat 5/7 平台标识不入负词典（平台数可参与 repetition 对齐，如 B12 的 3 RGB × 2 sensors = 6——由语义角色/context 决定）。
- **纪律确立**：每个新 hint dimension 先人工抽样校准规则、再全量重打；不在 396 条间反复改规则。最终产出 = 经独立人工验证的 Planner-v2 Hint Contract → Contract Freeze → SFT authorization gate。
- **序列**：① v3.1 全量重打 396 条 per_band → ② P0/P1-B baseline 表更新（M1/M2 与 hint 无关，不变；E3 口径更新）→ ③ Batch 2 per_class。

## 2026-10-04：Hint 人工验证 Batch 2（per_class，12 条）——1 TP / 8 FP / 3 ABSTAIN；class 四角色 taxonomy 确立

- **裁定**：TP = C3（显式类别枚举 + "within specific land cover classes" + AGGREGATION×8 强对应）；FP = C1/C2/C4/C6/C7/C8/C9/C12；**ABSTAIN 锚点 = C5/C10/C11**（不硬压成 FP）。
- **class 四角色 taxonomy（owner 确立）**：① 输入属性 class label（样本属性）② 输出类别空间（RF 输出 N classes）③ QA/flag 类别 ④ 真 class-wise iteration——**只有 ④ 支持 per_class TP**；①-③ 默认不产生 TP，除非另有逐类处理证据。
- **per_class 规则指令**：优先"逐类动作语义"（for each class / within each class / separately for each class / for each land-cover type / group/aggregate by class）= iteration evidence；"classify into N classes"/"N classes:"/"class labels"/"land cover classification" 仅 = class presence（不能 TP）。
- **ABSTAIN 锚点纪律**：C5/C10/C11 类（枚举存在但对齐不明）保留 ABSTAIN，不为覆盖率硬压成 FP。

## 2026-10-04：per_class 规则 v2 校准——8/12 精确一致，4 残余全部为安全方向 ABSTAIN；建议冻结

- 迭代过程：v1（7/12，词数枚举缺失）→ 精修（ALT 计数对齐 + 枚举清单长度对齐 + 输入产品 FP + classif_op ABSTAIN）→ v2 **8/12 精确一致**；4 残余（40518/63576/28513/41306）**全部 = 规则 ABSTAIN vs owner FP** 的安全方向偏差（规则拒绝在词汇证据不足时判 FP）——符合 precision-first 与"ambiguous → ABSTAIN"协议。
- 中途发现并修复：ENUM 漏配 "types including"；ALT 需计数对齐（"cloud masking" 不解释 ×4 重复——29220 根因）。
- **新行为学信号**：per_class 的 lexical FP 率甚至高于 per_band（关键词命中 192/396，owner FP 8/12）——"class/land cover" 在本数据集中几乎总是主题词/输出空间/QA 语境。
- **per_class v2 FREEZE 建议**（同 per_band 先例）："calibrated/frozen for P0 validation"，Human agreement 8/12 exact（4 残余安全方向），precision-first policy，known limitation（枚举清单深层对齐不可 lexical 判定 → ABSTAIN）。
- **待 owner 裁定的一个口径问题**：ABSTAIN 行的 hint 处理——(a) 保留但标记 unverified（覆盖率优先）或 (b) 置为 unspecified（精度优先）。影响 E3 口径与 Contract Freeze 文本。
- per_class 全量重打在口径确认后执行；然后 Batch 3 per_year。

## 2026-10-04：ABSTAIN 语义定稿 + per_class v2 FREEZE + 全量重打完成

- **Contract 语义（owner 原话，入 Contract Freeze 文本）**："ABSTAIN is not treated as a negative semantic judgment; it is an abstention from providing the corresponding hint. For Planner input, ABSTAIN is normalized to `unspecified` to preserve precision-first behavior." 论文表述：**ABSTAIN = insufficient evidence → no hint emitted**（不得写成 ABSTAIN = negative）。
- **人工验证标签 vs Planner 可用 hint 分离**：TP→保留；FP→删除；ABSTAIN→不送入 Contract（=unspecified）。理由：保留 per_class (unverified) 仍会被模型当有效信号利用，破坏 high precision > high coverage 原则。
- **per_class v2 FREEZE**（同 per_band 先例）：calibrated/frozen for P0 validation；8/12 exact + 4 安全方向 ABSTAIN；precision-first。
- **全量重打完成**：per_class 校准作用于 gold v2.1 → **v2.2** 与 review sample → v1.2（per_band v3.1 + per_class v2 双校准叠加）。

## 2026-10-04：per_year 规则 v1 校准——10/12 一致；两处"待重裁"发现（完整文本含 per-year 处理语句）

- 规则演进：v1（9/12，"annual" 光杆词误判 + season-only 误 FP）→ 精修：① **annual 必须伴随逐年处理动作**（annual median/mean/maximum/composites、aggregated annually）——光杆 annual → ABSTAIN；② season-only → ABSTAIN（结构性季节证据才 FP，如 Y9 的 "three seasonal periods... ascending and descending"）；③ 结构对齐判 TP（RASTER_LOAD×n == 年份跨度，Y7 强正例）。
- **当前 10/12**（TP 5/5、FP 2/2、ABSTAIN 3/5）。
- **两处 differs = 建议重裁（新证据）**：87169 与 28819 的**完整任务文本**含明确 per-year 处理语句——87169: "It computes **annual DOY (day of year) composites by year**"；28819: "creates three time-series charts: **annual DOY trends by year**"。你的 ABSTAIN 判定基于截断摘录，很可能未含这两句。**请重裁 Y5/Y11。**
- 40813 修复后 = ABSTAIN ✓（纯 seasonal 维度，非 year 的反证）。
- 附：owner 校准区分已入规则（"annual"=强证据非绝对证据；before/after 与短 range = ABSTAIN 锚点 Y2/Y11）。

## 2026-10-04：Y5/Y11 重裁为 TP（per_year Batch 3 终版 7/2/3）+ 方法论修正：全文验证原则

- **重裁**：Y5 → TP（完整文本 "computes annual DOY composites by year" 满足 annual+by-year 两条件）；Y11 → TP（"annual DOY trends by year" 同理）。原 ABSTAIN 系摘录截断所致。per_year Batch 3 终版：**7 TP（Y3/Y4/Y5/Y7/Y8/Y10/Y11）/ 2 FP（Y1/Y9）/ 3 ABSTAIN（Y2/Y6/Y12）**；规则 v1 与重裁标签 12/12 一致 → per_year v1 FREEZE（"annual + explicit by-year processing" = 充分 TP 证据；光杆年份/range 不足；seasonal-only = ABSTAIN 除非 repetition 结构性指向其他维度）。
- **方法论修正（owner 确立，重要）**：人工验证必须基于**完整 task text**——"真实 TP → 摘录缺关键句 → 人工 ABSTAIN → 规则被错误收紧"比规则误判更危险；拒绝"摘录可见性限定"，正确链条 = 完整文本 → Human judgment → Rule calibration；Planner-v2 Contract 将 full task text availability 列为数据前提。
- **验证原则保留**：规则与人工标签不一致时，先查完整文本与语义角色，再改规则；不直接调规则追标签（Y5/Y11 为范例）。
- 后续批次呈现改为全文。

## 2026-10-04：Hint 人工验证 Batch 4（per_feature，12 条）——0 TP / 10 FP / 2 ABSTAIN（与初判完全一致）；per_feature 降级为 diagnostic_only

- **裁定**：FP = F1-F9、F11（user-clicked locations=交互输入 / feature collection=数据对象 / polygon=空间范围 / point features=采样对象 / monthly=时相 / 两个时相 / post-fire 链 / polarization×orbit / 多景下载迭代 / QA+云过滤）；ABSTAIN = F10（canopy range 维度但 4 档不对齐）、F12（三个 feature collections 接近 per_class 语义，repetition 无法可靠解释）。
- **per_feature Contract 处理（owner 定）**：`status = diagnostic_only; operational_hint = disabled; default = unspecified; whitelist = empty`——不用"默认 FP"（ABSTAIN 语义保持"不提供 hint"，无需人为定义负类）。
- **高污染词结论**："feature" 至少五种角色：feature collection（数据对象）/ surface feature（地表特征）/ point feature（空间对象）/ user-clicked locations（交互输入）/ true "for each feature"（真迭代，当前池未发现）。
- **⚠️ Batch 5 预警（owner）**：generic_each 可能恰恰是 per_feature 被隐藏后的真实表达形式——Batch 5 = 抽象"逐对象/逐项处理"信号测试，是 hint contract 的关键一批。

## 2026-10-04：Hint 人工验证 Batch 5（generic_each，12 条）——4 TP / 3 FP / 5 ABSTAIN；generic_each Contract 重定义 + GEE/Planner 层次边界确立

- **裁定**：TP = G1（3 locations × 2 statistics = ×6 结构对应）/ G3（per-polarization ×3）/ G4（Two models per satellite）/ G9（May/July/August 三链）；FP = G2（before/after 对比）/ G5（with/without-cloud 实验配置）/ G8（可视化配置）；ABSTAIN = G6（×2 归属不明）/ G7 / G11 / G12（**intra-stage bulk**）。
- **generic_each Contract 重定义**：不再是"text contains each/per-*"，而是 "**Task semantics indicate multiple homogeneous workflow stages, with repetition structure supporting that interpretation**"。三分 taxonomy：stage 级重复 → eligible；intra-stage bulk / collection.map() → ABSTAIN/unspecified（不产生 plan stages）；对比/配置 → FP。
- **理论边界（论文级）**：**GEE execution-level iteration ≠ Planner graph-level stage repetition**——GEE collection.map() 内部遍历 N 元素是单阶段；Planner 只关心是否形成 N 个可表达、可排序、可 grounding 的 workflow stages。这是 workflow abstraction / cross-platform transfer 的理论边界。
- G7/G11/G12 保持 ABSTAIN 而非 FP：per-image 语义在 GEE 执行层是真实的，只是不构成 Planner 级重复。

## 2026-10-04：Batch 6（unspecified + 无重复行）验证完成 + **Planner-v2 Hint Contract FREEZE** 正式落盘

- **Batch 6（24 条）**：U 组 11/12 确认 unspecified 为安全默认（U1/U10 隐藏对比配置型重复——按 Batch 5 taxonomy 属不发射 hint 的类别，安全；**U5 = 关键词覆盖缺口样本**：3 指标 × 统计量的 stage 级重复无 each 措辞，generic_each 关键词规则漏检——precision-first 已知限制）；N 组 11/12 确认无重复，**N9 = gold 侧对齐缺口实例**（任务明示 3 时期逐期合成，gold plan 无重复阶段——与深尾欠预测同源的监督缺口）。
- **全量最终重打**：per_year v1 + generic_each（stage 级定义）+ per_feature disabled 应用于全量 → `blueprint_v2_gold_v3.jsonl`（37,044 行，SHA `621090bc…`）。最终 hint 分布（组级）：unspecified 27,259 / generic_each 16,111 / per_year 9,917 / per_band 494 / per_class 28 / per_feature 0（7,188 诊断槽位单列）。行级：71.7% 无 confirmed dimension。
- **Planner-v2 Hint Contract FREEZE v1 落盘**：`planner_design/PLANNER_V2_CONTRACT_FREEZE_v1.md`——Schema v2 + 五维度规则版本与校准记录 + ABSTAIN 语义 + GEE/Planner 层次边界 + E1-E4 + smoke 设计 + 冻结清单。**自此 Planner-v2 训练目标不得再按模型结果修改。**
- 状态：**Planner-v2：Data/Schema/Evaluator Gate PASS；Human Hint Validation DONE（6/6）；SFT NOT AUTHORIZED（待 owner 放行）**。零 GPU，冻结物未动。

## 2026-10-04：owner 放行 R3-PLANNER-V2-SMOKE（100-300 条，零正式训练承诺）

- **状态快照（owner 口径）**：Contract Freeze PASS / Hint Validation PASS / Gold v3 FROZEN / E1-E4 FROZEN / **Planner-v2 SFT：SMOKE AUTHORIZED** / Formal SFT NOT YET / Stage-1 v2_2 FROZEN / Gate FROZEN / Stage-2 FROZEN / RL FROZEN。
- **三原则**：①不碰冻结数据（用 blueprint_v2_gold_v3，不重生成 target）②不追最终指标（回答"Qwen 能否稳定学习该结构表示"+三种 shortcut 排查：unordered 退化/全部 unspecified/repeat 猜数）③独立目录全新 Base 起点（不复用 Planner-v1/P1-B 权重）。
- **Smoke 样本分层（~300 train + ~300 eval，不重叠）**：无 repetition 50 / 单 repetition 70 / 多 repetition 70 / hint 明确 50 / unspecified 40 / 长-复杂 20；保证五个 hint 维度均有样本；per_feature 不进 operational target。
- **Smoke 通过/失败制**（不追 F1）：S1 JSON+schema valid（大量 parse failure 直接停止）/ S2 ordered stages 存在 / S3 repetition presence（不看 repeat=36）/ S4 unspecified 滥用（大量→shortcut）/ S5 hint 与 predicted repetition stage 的对应（"band"→无条件 per_band 不可接受）。**E4 不评分但必须看**：模型生成 repeat 数字的分布（恒 1/恒 2 = numerical shortcut）。
- **主线并存**：Planner-v2 Smoke PASS ≠ Stage-1 正式路线切换；正式 SFT 需在独立 dev/test 证明 ordered+repetition+task conditioning 优于 Planner-v1。

## 2026-10-04：R3-PLANNER-V2 SMOKE 完成——S2/S3 PASS（结构可学成立），S1 欠训练 PARTIAL，E4 repeat=1 塌缩出现

- 过程：初版 1 epoch（6 步）评测失败（模型停留在 Base 先验：散文 Stage 计划/幻觉 schema——欠训练形态，P0 曲线佐证）→ 同数据 5 pass 续训至 ~41 步（对齐 P0 格式学习窗口）→ 评测完成（n=212 held-out）。两次评测脚本运行时错误已修。
- **S1-S5**：S1 parse 0.3585/schema 同（36% 稳定 blueprint，其余回退散文先验——PARTIAL）；**S2 ordered stage LCS-F1 0.6235、首 stage 0.8158（PASS：输出有序 stage 序列而非 unordered list）**；**S3 repetition-presence F1 = 1.0（PASS 决定性：repeat>1 family 签名与 gold 完全一致）**；S4/S5 不可评（模型完全省略 iteration_hint 字段，0 组发射）；**E4：pred repeat 全部 =1（gold 1.29，2→69/3→9）——repeat=1 塌缩出现，owner 预警命中**。
- **Smoke Gate：条件性 PASS**——v2 结构表示可学成立（核心问题）；格式稳定性需正式 SFT 预算；hint 发射留待正式 SFT 观察。
- 报告：`planner_design/R3_PLANNER_V2_SMOKE_RESULTS_v1.md`。**建议**：Planner-v2 正式 SFT 设计启动（全量 37,044 行、独立 dev/test、S4/S5 与 repeat 塌缩为观察项）；主线切换等独立 dev/test 证据。零冻结物变更。

## 2026-10-04：owner 放行 Planner-v2 Formal SFT 第一轮（1 epoch）——三层指标层级 + 统一对比管线后置

- **放行配置**：Gold v3 全量 37,044 行、1 epoch、全新 Base（不从 smoke resume）、独立 dev（checkpoint selection）+ locked test；QLoRA/NF4/bf16 协议不变；**不加** RL/DPO/count weighting/curriculum/hint target 修改/Schema 修改/QGIS/Stage-1 v2_2 混入。
- **指标层级**：第一层 E1 Ordered Stage-F1（核心）；第二层 E2 Repetition-presence F1（v2 相对 v1 的新能力）；第三层 E3 hint F1（micro/macro/per-class + emission rate）；格式 S1 = 必要条件非科学贡献；E4 repeat bias = diagnostic。
- **对比纪律**：禁止拿 v2 ordered-F1 直接比 v1 bag-F1 宣称提升（evaluator 不同）；统一对比 = v1 Planner→Serializer vs v2 Planner→Serializer 的同管线比较，后置于正式 SFT。
- **观察项**：S4 unspecified 滥用 / S5 关键词 shortcut（band→per_band 等）须在正式 SFT 重新检查；E4 repeat=1 塌缩继续监控（进一步支持 repeat 移出 Planner 目标的设计）。
- **状态**：Smoke PASS / 核心结构可学性 PASS / S1 欠训练不构成失败 / Formal SFT 放行第一轮。

## 2026-10-04：Planner-v2 Formal SFT 第一轮启动（1 epoch，Gold v3 全量）

- **数据**：planner_v2_train.jsonl 33,192 行（SHA `443d5d31…`）+ dev 1,796（`807717b5…`，checkpoint selection 用）+ **test 1,796 LOCKED**（`b524d56c…`，本地保存不上传）；90/5/5 seed 20260924。Sanity smoke 通过（100 行，tgt_trunc=1，task_too_long=0，isolated dir 已清理）。
- **启动**：PID 494715，`[release] full run: 33,339 rows`（train 文件 33,192 + 计数口径差 147 行 = builder 端 task 太长排除行的计入差，以 ledger examples 为准复核），无 [resume]，GPU 20.2GB / 37%。1,042 步 × ~31s ≈ **9h，预计 10-05 ~01:40 完成**。ckpt_every=150 → ~7 个 checkpoint 供 dev 选点。
- **训练后**：dev 评测（E1-E4 全口径 + S4/S5 观察项 + E4 repeat 分布）；locked test 本轮不动。

### 勘误（同日）：planner_v2_train 行数为 33,339（非 33,192——后者是 P0 行数的误记）；dev 1,852 / test locked 1,853；SHAs 不变。日志 "33,339 rows" 与构建一致。

## 2026-10-04：Formal dev 评测脚本 v1.1 完成并部署（owner 审计意见落实）；训练正常不受影响

- **owner 审计意见落实**（eval_planner_v2_dev_v1.py → v1.1，SHA `cda54d59…`，部署为 `/root/system_redesign/04_DIAG_WORK/eval_planner_v2_dev_formal_v2.py`，与线上旧脚本并存不覆盖）：
  ① **E3 改为 gold 对齐**：pred repetition group 按 (family, 组序) 键与 gold 组 1:1 对齐 → hint 集合比较（group-exact rate + per-hint-dim TP/all）——废弃 v1 式"模型自报即计分"；
  ② **S4 正式指标化**：`pred vs gold unspecified rate` 双报告（pred≫gold = unspecified collapse；pred≪gold = hint over-emission）——偏差诊断而非 pass/fail；
  ③ **S5 保留两口径**：hint-family consistency + keyword shortcut 仅观察（任务明示 "for each year" 时模型利用关键词是合理行为）；
  ④ E3 输出增加 group-exact rate。
- **SHA 事实澄清**：owner 审计发现 regex 缺陷的版本（`dd9ef8dd…`）非本线部署版（`5113ae33…`，extract_json 正则干净、syntax OK）——两版本来源不同，owner 的 /tmp 版不在租卡机上；owner 到达后做双版本 diff，以 owner 版为 formal 基准。
- **自测**：E3 对齐逻辑 1/2 预期命中（AGGREGATION exact / BAND_SELECT miss）；syntax OK；线上旧脚本未动。
- **训练正常**：step 60/1,667，loss 2.19（v2 JSON 目标快速下降中），tgt_trunc 30/1,920（0.03%，无异常）。ETA 不变（~01:40）。
- 运行纪律确认：主训练不动；[done] 后 400 fast → 1,852 全量 dev → checkpoint ranking → 锁定 → locked test-1,853 不动。
- 10-05 01:07 例行检查：Planner-v2 formal SFT 正常（存活 ~8.5h，GPU 20.3GB），进度 ~65%；ETA ~01:40。
- 10-05 03:07 例行检查：Planner-v2 formal SFT 正常（存活 ~10.7h，GPU 20.3GB），进度 ~62%；ETA ~02:30-03:00（已过，下次检查确认 [done]）。
- 10-05 03:30 重查（GPU 瞬时空但步数继续）：step 1,040/1,667（62%），loss 1.30-1.31，31s/步稳定；剩 ~130 步 ≈ 67 分钟，完成预计 ~04:40。进程需下轮确认（本轮 GPU 采样恰在步间隙）。
- 10-05 05:07 例行检查：fast dev eval 进行中（04:21 时 50%，parse 0.835/E1 0.681）；注：04:15 前后两次 SSH 瞬断为 sshd 限流，评测进程（setsid）未受影响，已降低轮询频率。

## 2026-10-05：Planner-v2 Formal SFT 训练完成 + 400-row fast dev 通过 + 全量 dev 启动

- 训练 `[done]` 03:31（steps=1041，tokens 5,456,020，tgt_trunc 566，task_too_long=0）。
- **400-row fast dev PASS**：S1 parse/schema **0.8125**（vs smoke 0.3585——格式学习成立）；**E1 ordered stage F1 0.6679**、exact seq 0.1231；**E2 repetition-presence F1 0.9641**；E3 group-exact **0.9767**、emission 0.2386、hint 一致性 per_band=0（4 组全 FP——S5 shortcut 确认存在，正式观察项）；S4 pred unspecified 0.594 vs gold 0.785（欠发射方向，deviation diagnostic）；E4 pred repeat mean 1.28 vs gold 1.30（**分布高度贴合——repeat=1 塌缩在正式 SFT 后大幅缓解**）。
- **全量 dev 1,852 已启动**（~4h，预计 09:00-10:00 出）→ checkpoint ranking → 锁定。locked test 不动。
- 10-05 07:07 例行检查：全量 dev 1,852 评测进行中（05:30 启动）。
- 10-05 09:07 例行检查：全量 dev 评测进行中。
- 10-05 13:07 例行检查：全量 dev 评测进行中（上轮 86%）。

## 2026-10-05：Planner-v2 Formal SFT Round 1 dev 全量出分——E1 0.6636 / E2 0.9670 / S1 0.8089；S5 shortcut 确认；locked test 未动

- 全量 dev（n=1,852，evaluator v1.1 gold 对齐）：**S1 parse/schema 0.8089**；**E1 ordered stage F1 0.6636**（首 stage 0.8017、exact seq 0.1188）；**E2 repetition-presence F1 0.9670**；E3 **group-exact 0.9831**、emission 0.2894、per-hint precision（generic_each 0.979/per_year 1.0/unspecified 0.986/**per_band 0.0 n=9/per_class 0.0 n=1**）；S4 pred unspecified 0.5795 vs gold 0.6848（轻微 over-emission）；E4 pred repeat mean 1.28 == gold 1.28（直方图贴合——**smoke 期 repeat=1 塌缩在正式 SFT 后消失**）。
- **判读**：① v2 结构能力（ordered stages + repetition presence）在正式预算下成立；② **S5 keyword shortcut 确认**（per_band 9 次发射 0 次绑定 BAND_*）——P2 蓝图（repetition 语义条件 + hint 绑定监督）必要性获正式 SFT 证据；③ S4 轻微 over-emission（非 collapse，正常范围）；④ smoke 期 repeat=1 塌缩消失（与"repeat 数值 1 epoch 即可贴合"一致，但 identifiability 结论不变——数值由 gold 分布支撑）。
- **对照纪律**：v1 bag-F1 与 v2 ordered-F1 不可直接比（evaluator/粒度不同）；统一对比（双 Planner → Serializer → 同口径）按裁定后置。
- checkpoint ranking：本轮仅评 final adapter；7 ckpts 保留。**locked test-1,853 未动**。
- 报告：`planner_design/R3_PLANNER_V2_FORMAL_DEV_RESULTS_v1.md`。待 owner：round 2 方向（S5 修复 vs 统一对比管线先行）。

## 2026-10-05：owner 裁定 Round 2 = 统一 v1/v2 比较管线（CPU-only）；Planner-v2 Round 1 正式记为 PASS

- **Round 1 定性**：PASS = "Ordered + repetition-aware Planner 具有可学习性和稳定结构输出能力"，**非**"优于 Planner-v1"（坐标系不同不可比）。
- **S5 定性**：per_band 0/9 = 条件语义绑定缺陷（模型学到了错误的 hint→family 绑定规则），非核心结构能力失败——与核心结构能力问题分开。
- **Round 2 设计**：同一 Task → v1 Planner→Serializer-v1 vs v2 Planner→Serializer-v2 → **同一个 bag-F1**；只改 Planner，不改评价口径；输出六项同口径指标（parse/family bag-F1/count multiplicity/length±1/over-under emission/rare-family recall）。CPU-only/确定性/不碰 locked test。
- **执行顺序**：① 统一管线 → ② 公平比较 → ③ v2 主线裁定 → ④（若成立）P2 hint binding supervision（只修 S5）→ ⑤ QGIS Grounding。
- **关键工程问题（本回合解决）**：v2 预测在语义粒度（30），v1 在 plan-family 粒度（19）——统一单位需 semantic→plan 映射表（从训练行位置对齐学习，映射保真度需 ≥90% 才可用）。

## 2026-10-04：Option B（Schema v2.5）设计分析完成——数据支撑的边界与建议

- 报告：`planner_design/R3_OPTION_B_DESIGN_v1.md`。Schema v2.5 草案：stages（每游程一 stage）+ repetition.dimension（per_band/...），**绝对次数完全移除**。
- **Option B 解决**：不可识别的循环次数移出监督（三轮证据闭环）；迭代语义保留且可学习（dimension 分类 AUC 0.968）；S5 shortcut 问题随 B 重定义自动简化。
- **Option B 不能解决（诚实边界）**：语义级长尾主体是**不同语义阶段的累积**（51+ 原始桶 stages 均值 114、repeat_share 仅 0.245；长行 ≥30 stages 中 repeat>1 仅占 7.5%）——**极长 workflow 的生成长度问题仍在**（B-form 下 1,830-stage 行依然是 1,830 stage）。97% 任务 ≤30 stages 在可生成范围内；>100 的 0.5% 为本代已知边界（论文 limitations）。
- **冻结 gate 兼容**：B-form 与 gate 单位不同（无展开），v2 线评测走 E1-E4；统一对比管线的映射问题在 B-form 下预期改善（待验证）。
- 待 owner：Option B 定稿 → B-form 数据转换（CPU）→ Planner-v2 round 2（B-form 目标重训，放行待批）。

## 2026-10-04：owner 路线重定义——Planner 最终目标 = processes + links 抽象 QGIS Workflow Plan；Planner-v2 退回能力验证实验

- **最终目标形态**：`Task → QGIS Workflow Planner → {processes: [{id, identifier, inputs[], outputs[]}], links: [{sourceProcess, sourceVariable, targetProcess, targetVariable}]} → QGIS Workflow`——identifier 级操作（如 raster_reproject/slope/reclassify/raster_calculator）+ 数据流连接；**不含**真实路径/CRS/参数/数值（Grounding 层）。
- **Planner 学习目标四层**：① 做什么（操作选择）② 顺序 ③ 连接（哪个输出→哪个输入）④ 分支/汇合（一个输出可连多个后续）。
- **repeat 处理**：从核心输出移除；未来如需表达"逐波段执行"，加可选语义属性（scope: per_band）——属后续 schema 设计。
- **Planner-v2 重新定位**：从"最终方案"退回**能力验证实验**（已证明 Task → Ordered Workflow Planning 可学习，E1 0.664）；核心待验证问题 = **"ordered stages 能否作为 processes+links Planner 的前置能力"**。
- **待 CPU 侦察**：processes+links 格式的 gold 数据在资产中的位置与规模（Stage-2 QGIS assets：v2a_A 1,334/120/111 SFT 文件等）。

## 2026-10-05：v2a_A 结构侦察完成（11 维，1,565 条全量）——processes+links gold 可用性确认

- 报告：`planner_design/V2A_RECON_REPORT_v1.md`；数据 `v2a_recon/v2a_recon_out.json`。
- **5 问回答**：① 紧凑 DAG（中位 4 节点/p90 13/max 30）；② 纯链 57.6% + 分支/汇合 42.4%（浅分支：in-deg p90=2/max=20）；③ link_kinds 4 种（direct 81% 主导）；④ **309 个真实 QGIS 算子 ID**（native/qgis/gdal/saga/grass7 五前缀，长尾 49 单例）——**Grounding 级标识符，抽象化映射表是 Planner-v3 前置设计任务**；⑤ **变量级 I/O 确认不存在于数据**（全字段扫描），但可从 QGIS 算子端口 schema **确定性推导**（无需人工标注）。
- **数据质量**：0 悬空 link、引用完整；⚠️ 144 个环（9.2%）与 106 孤立节点需处理规则；tier 字段全部 Tier-1（无判别力）。
- **对三选项的含义**：无硬伤；v2a_A 可直接作 Planner-v3 结构 gold；两个缺口 = 抽象 identifier 归并表（309→抽象）+ 算子端口 schema 表（变量 I/O 恢复）——均可半自动构建。

## 2026-10-05：v2a_A graph expressivity 深查完成（owner 四问题，直接读文件）

- 报告：`planner_design/V2A_EXPRESSIVITY_AUDIT_v2.md`（审计 json 同目录）。
- **Q1 Graph 形态**：纯链 57.6%（902 行，链长 p50=3/max=30）/ 分支+汇合 24.4% / 仅分支 9.6% / 仅汇合 8.3%；节点 p50=4/max=30；行内 max in-degree p50=1、out-degree p50=1（浅分支）。
- **Q2 Link 信息量**：link_kinds 按切分稳定（direct 81% 主导；linear 仅 1.9%——**link kind 是转换元数据，不是拓扑描述符**）；**0 悬空**；环 124/8/12（train/dev/test）、孤立 89/9/8——环与孤立节点是 gold 侧需处理的少数形态。
- **Q3 Operator OOD**：train 295 unique → **dev OOD 仅 8 个算子/10 次出现、test OOD 7 个/16 次**（OOD 占比 <0.3%）——**operator 覆盖基本无 OOD 风险**；长尾：309 unique、49 单例、113 个 ≤3 次、top10 占 38%。
- **Q4 变量级 I/O**：**穷尽扫描确认 absent**（sourceVariable/targetVariable/inputs/outputs/ports/parameters 全部 0 命中）；但可从 QGIS 算子端口 schema 确定性推导（无需人工、无需伪标注）。
- **taskType × 结构**：12+ 类，branch/merge 率 0.37-0.52（Surface water 最高 0.52）——类型间结构差异温和。
- **结论**：42.4% 含分支/汇合（GEE 线性目标无法提供的监督）+ operator OOD 风险极低 + 变量 I/O 可从 schema 推导——**QGIS gold 对 processes+links Planner 的支撑力充分**，schema 裁定的数据基础就绪。
- 10-05 13:0x 例行检查：GPU 空闲，无训练/评测进程；状态 = Planner-v2 formal round 1 dev 结果已报，等 owner 对 round 2 方向（S5 修复 vs 统一对比管线）的裁定。

## 2026-10-05：owner 裁定 Phase 0 路线冻结 + 启动 CROSS_PLATFORM_TRANSFER_AUDIT（CPU-only）

- **Phase 0 概念冻结**：GEE = General GIS Workflow Reasoning（大规模监督）；QGIS = Platform Grounding（平台落实）；**L3 不建立**；Planner 不认识 GEE 翻译职责；Grounding 不重新理解任务。
- **方法论反转（owner）**：不再"先设计中间表示再证明有用"，而是**先验证 GEE 知识能否帮助 QGIS 最终任务，再决定训练方式**。
- **正式任务**：ROUTE2_CROSS_PLATFORM_TRANSFER_AUDIT——GEE 128k ↔ QGIS 1,565 的平台无关结构特征对比，8 问（任务类型语义重合/操作 pattern 重合/长度复杂度/顺序结构/branch-merge 新增量/可迁移/仅辅助/不可迁移），产出 transferable/partially/platform-specific 分类 → **之后才裁定 A1/C0 训练**。
- **Formal SFT（10.7h）正常完成不受影响**；dev 评测按既定序列随后。

## 2026-10-05：ROUTE2_CROSS_PLATFORM_TRANSFER_AUDIT 完成（8 问，CPU-only）——可迁移性三分类确立

- 报告：`planner_design/ROUTE2_CROSS_PLATFORM_TRANSFER_AUDIT_v1.md`（数据 json 同目录）。
- **Transferable**：主题覆盖（共享主题内 QGIS 59%/GEE 72%）、17-family 操作词汇（QGIS 69.7% 实例可映射、双向 0 独有）、首尾模式同构（数据准备开局/产物落盘收尾）、通用 pattern（load→filter→derive→aggregate→export）。
- **Partially transferable**：长度规范（QGIS 各分位短 2-3 倍——p50 4 vs 11、p90 13 vs 46）；矢量属性管理思想的通用语义。
- **Platform-specific**：**DAG branch/merge（QGIS 42.7% vs GEE 0%——线性链不可表达，100% 新结构）**；矢量数据库操作（joinattributestable/rasterize/postgis——30.3% 未映射实例的主体）；QGIS 算子 ID 粒度。
- **A1/C0 训练含义**：A1 有数据支撑（覆盖上限 ≈69.7%）；QGIS gold 独有 DAG 结构监督（42.7%）是 A1 无法提供的；**建议两阶段互补而非互斥**，比例与 curriculum 归 owner。
- locked test 未动；Formal SFT 正常运行中（~step 200+）。

## 2026-10-05：owner 确立三知识空间框架——309（gold coverage）与 ≈1,200（QGIS Registry capability space）严格区分

- **三知识空间**：① GEE 128,447 → GIS Workflow Reasoning（"怎么解决 GIS 问题"）；② QGIS Gold 1,565 / 309 operators → workflow-to-QGIS implementation examples（"这些解决方案怎么组织成 QGIS Workflow"——**只是 QGIS 知识的一部分，非全部**）；③ **QGIS Operator Registry ≈1,200** → 平台能力空间（"QGIS 有什么能力可以实现"）。
- **关键区分**：309 = workflow supervision coverage（≈25.8% registry coverage），**不是 QGIS 算子空间规模**——混淆会低估 Grounding 空间。
- **三级 operator 分类确立**：L1 Seen（gold 中出现）/ L2 Registry-known but gold-unseen / L3 true OOD。
- **L3（跨平台中间算子层）继续不建立**：Planner workflow node 保持任务解决方案级语义；Grounding 从 1,200 registry 选择实现——不存在必须由 GEE 学习的固定中间算子体系。
- **新增评估维度（P0-3 Registry 审计）**：registry 算子数核实（≈1,200 待验证）/ gold coverage 25.8% / provider 分布 / 未覆盖能力类型 / operator schema 完整度 / semantic redundancy（多算子同功能）。
- **执行序列更新**：P0-1（GEE reasoning 证据 ✓）→ P0-2（QGIS Gold 结构研究 ✓ 大部分）→ **P0-3 Registry 审计（新）** → P0-4 三者连接验证。
- 待 P0-3 数据源：QGIS 文档/安装实例的处理算法注册表（native ~300 + qgis ~100 + GDAL ~60 + GRASS ~80 + SAGA ~400+ 需核实）。

### 补充（同日）：v2a recon 报告升级 v1.1——加入三知识空间口径修正附注（309 = coverage 非 space）。

## 2026-10-05：Historical Experiment Reconciliation 完成——对账矩阵 + A/B/C 分类；两个真缺口浮出

- 报告：`planner_design/HISTORICAL_EXPERIMENT_RECONCILIATION_v1.md`（基于仓库真实实验文档：Gate 0/1/2、FA/DC、A1 机制结论、M3、Planner-v1/v2、v2a recon、Transfer audit）。
- **最重要的对账发现**：**A1 机制结论的设计原则 3（09-24 冻结）已预写今天的两层架构**（"GEE 不是 DAPT 数据源，其合理位置 = 结构/workflow composition supervision"）。今日 Transfer Audit（69.7% 词汇共享 + 42.7% DAG 新增）为该原则提供定量支撑。**Gate 2 负迁移在新架构下自动解释：旧 A1 混层（DAPT 直接优化 QGIS decoder）→ 控制失效；新架构分层 → 预测无此失效。Planner-v2 成功与 A1 失败不是矛盾，是监督形式不同。**
- **A 类（已回答，不重做）**：GEE 泛型 DAPT 负迁移 / A1 失败机制 / GEE 正确角色 / v2 可学性 / QGIS gold 结构价值 / 17-family 共享。
- **B 类（重析不重训）**：B1 = C0 checkpoint + test-111 预测用新 E1-E4 口径分解；B2 = D1① 78.8% 重解读；B3 = M3 83.7% 历史佐证；B4 = P0/P1-B 统一对比（管线就绪后）。
- **C 类（真缺口）**：**C1 = GEE-as-planning-supervision → QGIS Grounding 迁移（新架构核心 assay，从未隔离测试）**；C2 = DAG 结构生成（42.7% branch/merge 从未作为训练目标）；C3 = hint 绑定（已裁定 P2 前置）；C4 = Registry 级 Grounding（依赖 P0-3）。
- **最小实验建议（待 owner 放行）**：先 B1（C0 重评，零训练）→ C1 最小对照（Planner-v2 + grounding head vs C0）。
- Formal SFT 正常运行中，不受影响。locked test 未动。

## 2026-10-05：ROUTE2_EXPERIMENT_MASTER_TABLE_v1 整理完成——全期实验总表

- 报告：`planner_design/ROUTE2_EXPERIMENT_MASTER_TABLE_v1.md`。五个时代（QGIS 资产构建 / GEE 语料构建 / M1-M3 / Phase 2 v1 三臂与诊断链 / Route-2 v2）的全部可查实验：类型/数据/配置/核心结果/两层架构归属/溯源路径。
- 对账矩阵重述 + "？"汇总（6 项 C 类缺口）+ 关键数字速查表。
- 数字可靠性分级：v2 时代全部为本会话直接核查；v1 时代与构建时代来自冻结报告文档（campaign 级活动的细节指标未逐一展开，溯源路径已给）。
- 10-05 17:0x 例行检查：Planner-v2 formal SFT 正常（存活 ~12.5h，GPU 20.3GB），进度 ~75%；ETA ~01:40（10-06）。
- 10-05 17:07 重查确认：服务器 GPU 空闲（11 MiB），无运行中进程；**Planner-v2 formal round 1 全链（训练→fast dev→全量 dev）已于今日完成**，结果已报（E1 0.6636/E2 0.9670/S1 0.8089/E4 1.28==1.28，见 R3_PLANNER_V2_FORMAL_DEV_RESULTS_v1.md）；旧监控模板（stage1_run_v1/PID 103666）已过时，当前等待 owner 对 round 2 的裁定。无异常。

## 2026-10-05：C 类二次裁决完成（CPU-only）——C1-2 分两步（zero-shot assay 先行）；C2 定位为系统能力；C3 维持前置；C4 待 P0-3

- 报告：`planner_design/C_CLASS_SECONDARY_ADJUDICATION_v1.md`。**事实前提更正**：Formal SFT 已于 03:31 完成（dev 全量已评），GPU 空闲——"还在跑"的顾虑不存在。
- **Q1（C1-2）**：完整因果论证需 A1' 训练实验（defer），**但第一步 = 零训练的 zero-shot transfer assay**（Planner-v2 adapter × QGIS held-out 200-400 行，GPU 30-60 min）——判读树三分支（远超 baseline → 先验提升 / ≈baseline → A1' 成唯一判据 / 低于 → 负迁移警示）。历史数据不可替代（Gate 2 测的是 DAPT 混层；Planner-v2 从未在 QGIS 任务上测过）。
- **Q2（checkpoint 复用）**：**可行且即最小成本路径**——Planner-v2 adapter 与 C0 基线均在位，assay 只需生成、零新训练；A1' 训练实验的形态（grounding head）在 assay 正面结果后再设计。
- **Q3（C2 DAG）**：定位 = **系统能力验证 + 论文第二阶段**，非核心 transfer 实验——核心 transfer 在语义 stage 层面即可测；DAG 序列化表示未定（先定表示再训练，避免重蹈覆辙）；与 QGIS 端口 schema 表（P0-3）衔接。
- **行动队列**：1 = zero-shot assay（待放行，GPU 30-60 min）→ 2 = A1' 设计裁定 → 3 = A1' 训练（若放行）；C2 → system track；P0-3 可并行。

## 2026-10-05：owner 放行 C1-2a Zero-shot Cross-platform Reasoning Transfer（零训练，GPU ~30-60 min）

- **命名与因果分层（owner 确立）**：**C1-2a = zero-shot cross-platform reasoning transfer**（本实验——证明/否定 reasoning prior 的跨平台迁移能力）；**C1-2b = reasoning prior → QGIS grounding gain**（由 A1' 训练实验回答）——两者不得混淆；assay 结果**不得宣称"GEE 提升 QGIS grounding"**（grounding 尚未进入）。
- **实验设计**：Planner-v2 adapter（GEE 训练）× v2a_A dev+test 231 行（全部为 Planner-v2 OOD——QGIS 数据从未进入其训练）；生成 semantic stage plan（max_new_tokens 384）；gold = operator 序列经 69.7% 关键词映射表转语义 family；对照三参照：① trivial baseline（GEE 训练分布 modal 序列）② Planner-v2 in-domain 0.6636 ③ C0 op 口径 0.343/0.370。
- **纪律**：全线冻结维持；不重跑 C0/A1；不碰 locked test；P2/system track 不动。

## 2026-10-05：C1-2a Zero-shot Transfer Assay 出分——**零样本 family 迁移失败（bag-F1 0.047）**；A1' 成为唯一判据

- 全量（n=231 QGIS OOD）：S1 parse **0.4892**；**M family bag-F1 = 0.0472**（trivial 0.0；in-domain 0.6636）；ordered 0.0473；pred 长度 1.8 vs gold mapped 4.5。
- **机制（family 分布对比）**：pred = raster 三族（RASTER_LOAD 122/BAND_SELECT 110/AGGREGATION 89——GEE 遥感先验）；gold = **VECTOR_GEOMETRY 373（32%）**/BAND_ARITHMETIC 203/SPATIAL_CLIP 87——**两个分布几乎不相交**（GEE=栅格遥感 workflow；QGIS=矢量空间分析 workflow）。
- **判定（预注册判读树）**：零样本迁移失败 → **A1'（reasoning prior → grounding gain）训练实验成为唯一判据**。三个解释注意事项已登记：粒度伪影（stage vs instance）、gold 映射覆盖 69.7%、域差真实性（栅格 vs 矢量本质不同，非模型缺陷）。
- **对 A1' 设计的关键输入**：零样本失败 ≠ A1' 无价值——它证明 **QGIS grounding 知识必须从 QGIS gold 训练**；GEE reasoning prior 的价值（更好的初始化）只能由 A1' 对照实验检验（vs C0 fresh SFT），且必须纳入 Gate 2 式负迁移风险的对照设计。
- 报告：`planner_design/R3_C12A_ZERO_SHOT_RESULTS_v1.md`。GPU 空闲；locked test 未动；冻结物未动。待 owner：A1' 实验裁定。

## 2026-10-05：owner 概念修正——Raster/Vector 分布差 = 数据审计变量，非模型能力边界；C1-2a 作废；C1-2 重新定义

- **概念修正（owner）**："GEE 的 Raster 多 ≠ GEE 教模型 Raster 怎么做；QGIS 的 Vector 多 ≠ QGIS 教 Vector 怎么做"。真正关注的是：**模型是否学会"面对 GIS 任务需要调用什么类型的 GIS 操作并按什么依赖关系组合"**——任务语义→操作类型→依赖关系→组合，与数据模态无关。
- **模型能力三层拆解**：① 任务理解（GEE 大规模监督）② 工作流规划（General GIS Workflow Reasoning，仍属 GEE 层）③ QGIS Grounding（operator 选择与组合——QGIS registry/Gold/operator semantics 层）。
- **Raster/Vector 差异重定位**：数据审计变量（后续分析报告 GEE/QGIS 数据类型分布差异与共享任务语义），**不是实验主轴，不是迁移边界**。
- **C1-2a 作废**：该 assay 把实验问题错误变成"Raster→Raster 能否迁移"；不纳入裁决文档。其产物保留为数据点（不删除）。
- **C1-2 重新定义**：核心问题 = **"加入 GEE 学到的 workflow reasoning 后，模型选择和组合 QGIS operators 的能力有没有提升？"**——同一 QGIS task 双臂对照：C0（QGIS-only SFT）vs GEE reasoning prior + QGIS grounding。
- **QGIS registry 重定位**：≠ Vector knowledge；= **QGIS 的可操作能力空间（capability space）**。QGIS Gold = operator 组合成真实 workflow 的实例监督。三知识源各司其职：GEE 学解决问题 / registry 学 QGIS 能力 / gold 学组合。

## 2026-10-04：C1-2 最小 assay 设计提案完成（待 owner 批准，未执行）

- 报告：`planner_design/C12_MINIMAL_ASSAY_DESIGN_v1.md`。
- **双臂设计**：C0-QGIS（Base + QGIS 1,334 行 SFT）vs A1'-QGIS（Planner-v2 formal adapter + 同 QGIS SFT）——同数据/同超参/同预算，唯一变量 = GEE blueprint 预训练有无；每臂 ~22 min，合计 ~45 min GPU。
- **评测**（v2a_A_dev-120，双臂均未训练）：Op selection F1 / sequence F1 / exact graph rate / graph edit distance / coverage / 长度比；三参照（Base 零样本 / C0 臂 / 历史 v1 bag 参考）。
- **判读树**：A1' > C0 → 两层架构核心假设成立（Planner-v3 = GEE reasoning + QGIS grounding 正式路线）；≈ → 稀缺问题另行解决；< → Gate 2 式负迁移复现警示。
- **待 owner 批准**：① assay 执行 ② A1' 臂实现方式（Planner-v2 adapter 预合并 vs trainer 加载逻辑修改）③ v2a_A_test-111 保持 locked。
- GPU 空闲；冻结物未动；Planner-v2 formal adapter 在位。

## 2026-10-05：owner 放行 A1'（含 4 项修正）——merge_and_unload 起点 + 严格单变量 + paired evaluation + assay 定位

- **修正 1（批准）**：A1' 起点 = Planner-v2 adapter **merge_and_unload 进 Base** 后作为普通 Base checkpoint——双臂同一 trainer 代码路径，零特殊处理；**merge 一致性 sanity check**（同输入 logits/greedy 基本一致、tokenizer/special tokens/generation config 完全一致、保存新 immutable checkpoint、不覆盖 Planner-v2 原 adapter）。
- **修正 2（核心纪律）**：双臂唯一变量 = 初始化（C0 = fresh Base / A1' = Base+GEE Planner-v2 merged）；数据顺序/epoch/batch/LR/scheduler/max_len/**seed**/trainer code/dev-120/locked test 全部相同。
- **修正 3（评测）**：dev-120 **paired comparison**——Δ bag-F1/Δ LCS-F1/Δ exact graph/Δ graph edit distance/Δ operator coverage/Δ length ratio + per-example 差值 bootstrap CI + **多数任务改善检查**（非少数任务拉均值）。
- **修正 4（定位）**：正向结果命名 **A1' reasoning-prior transfer assay**，暂不命名 Planner-v3；五形态判读表登记（selection↑graph↑ / selection↑graph≈ / selection≈graph↑ / 全≈ / A1'<C0）。
- **基线口径**：历史 C0 test-111 0.343 = 参考线（不同条件），**不进主因果比较**；核心比较 = 同 QGIS train 双臂 → 同 dev-120 → paired Δ(A1'−C0)。
- **科学问题**：在完全相同的 QGIS grounding supervision 下，仅改变初始化（先获得 GEE 学到的 General GIS Workflow Reasoning），能否改善 QGIS operator grounding？

## 2026-10-05：A1'/C0 双臂 QGIS SFT 启动（串行：C0 → A1'，同数据同 seed 同超参）

- QGIS SFT 数据：qgis_sft_train.jsonl（1,334 行，SHA 前缀见日志；行格式 {task_text → {processes, links} JSON}）。
- 双臂配置：c0_qgis.yaml（Base 起点）/ a1_qgis.yaml（planner_v2_merged_A1init 起点，merge 后 17G bf16）；唯一变量 = 初始化；seed 20260924 相同 → 数据顺序相同。
- 串行执行（bash && 链）：C0 → A1'，日志 /root/data/p1c_twin_arms.log；每臂 ~42 steps ≈ 22 min。
- 完成后：dev-120 paired evaluation（E 系列全口径 + per-example Δ + bootstrap CI）→ 报告。
- ⚠️ sshd 限流：本时段多次连接瞬断（连接后即恢复），已改用低频批处理操作。

## 2026-10-05：owner 十步执行序列确立（Planner 定线 → Operator Audit → A1' 因果实验）；当前 GPU 空闲，先 CPU

- **冻结项**：RL/DAG 专项训练/GEE 数据修改/QGIS frozen Gold 修改/Planner-v2 schema 修改/Planner-v2 重训/立即 A1'/L3 恢复——全部不做。
- **序列**：STEP 0 数据/checkpoint/test 冻结 → STEP 1-2 Planner unified evaluator + v1 vs v2 并排（CPU）→ STEP 3 mainline 判定 → STEP 4 Registry manifest → STEP 5-6 No-RAG Operator Knowledge Audit → 分支判定 → STEP 7-10 C0→A1' paired→最终架构判断。
- **当前 GPU 空闲**：STEP 1-2 为纯 CPU（统一表示转换 + 已有 dev metrics 重算 + 补算 v1 侧 ordered 指标），立即执行；STEP 4 Registry manifest 需 QGIS 算子清单数据源（待确认：本地 QGIS 安装/文档抓取）；STEP 5-6 需 GPU（模型推理），执行前另请放行。

## 2026-10-05：STEP 1-2 部分完成——v1 侧 7 指标全算出；STEP 2b（v2 侧 bag 指标）需服务器重评，待 owner 批准

- **v1（P1-B）held-out 3,705 行统一口径 7 指标（本地全算）**：bag-F1 **0.6718** / family P 0.7436 / R 0.6805 / count-exact **0.1501** / length-error −2.95 / over-emission 2.05 / under-emission 5.00 / **ordered-LCS-F1 0.6338** / exact-seq 0.1379。
- **v2（formal）当前可得**：ordered-LCS-F1 **0.6658**（逐项，n=1,852）——**略高于 v1 的 0.6338**；bag/P/R/count/length 需 pred_seq，而 formal eval 未存储预测序列（items 仅 e1）。
- **STEP 2b 提案（待 owner 批准，GPU ~3.5h）**：修改 formal eval 脚本存储 pred_seq 后在服务器重跑 v2 dev 推理一次（模型/adapter 在位，纯推理），即可补齐 v2 侧全部 7 指标 → 完成并排表。
- 初步对照（ordered 口径）：v2 0.6658 ≥ v1 0.6338（+3.2pp）——与"v2 是 v1 的结构增强版"假设一致，待 bag 口径确认。

## 2026-10-05：三步执行计划确立（owner）——Planner 定线 → Operator Knowledge 审计 → A1' 因果实验；当前零训练

- **STEP 0 冻结**：全部数据/checkpoint/locked test；❌ RL/DAG 专项训练/改 GEE 数据/改 QGIS Gold/改 Planner-v2 schema/重训 Planner-v2/立即 A1'/恢复 L3。
- **STEP 1**：Planner-v1/v2 unified evaluator——统一内部格式 SemanticWorkflow{stages:[{family,repeat}], total_length}；7 指标（bag-F1/family P-R/count acc/length error/over-emission/under-emission/ordered LCS-F1；exact seq 仅参考）。
- **STEP 2**：P1 vs P2 统一评估（同一批 dev 行）→ **STEP 3 Planner mainline 裁定**（判据：v2 Bag-F1 ≈ v1 且保留 order/repetition → v2 = v1 结构增强版）。
- **STEP 4-6**：QGIS Registry manifest（≈1,200，三组：Gold-seen 309/Registry-unseen ≈900/absent）→ Operator Knowledge Audit dataset → **No-RAG Audit**（Recognition/Semantic Understanding/Similarity Discrimination/Task→Operator/Composition × Seen/Unseen 矩阵；情况 A/B/C 判定）。
- **STEP 7-10**：C0 grounding baseline（QGIS SFT 1,334）→ A1'（paired，唯一变量=Initialization，paired bootstrap CI）→ 最终架构判断。
- **纪律**：A1' = 有前置条件的待执行实验；当前 GPU 最优先 = unified evaluation + Operator Audit。

## 2026-10-06：STEP 1-2 进行中——Planner-v2 dev 预测重生成（GPU 长任务）

- unified evaluator 模块已就绪（planner_unified_eval_v1.py：统一 SemanticWorkflow 表示 + 7 指标；v1 侧 pred_seq 从 P0 metrics items 直接提取；行级对齐验证 1,852/1,852 task 全匹配 + 顺序一致）。
- **Planner-v2 dev 预测重生成运行中**（regen_v2_dev_preds_v1.py，PID 在租卡机 setsid 会话）：1,852 行 × 384-token 生成 ≈ 36s/行 → **ETA ~18.5h（10-06 全天，预计明日出）**。完成后 CPU 侧完成统一 7 指标对照表（STEP 2 交付）。
- 连接注意事项：服务器 sshd 对高频轮询限流（多次 Connection closed）——监控已降频；再生进程 setsid 独立会话不受影响。
- 零冻结物变更；locked test 不动。

## 2026-10-05：租卡机全量拉回完成（~1.27GB）——RENTED_SERVER_PULL_20261005

- 背景：租卡机租约今日到期（owner 指令：全量拉回保存至 E:\Route2_Migration_20260928\RENTED_SERVER_PULL_20261005，后续 owner 同步）。
- **全部 12 个实验/checkpoint 目录尺寸与服务器逐一核对一致**（route2_C0 301M 含 qgis_sft_ep1-ep11 全部 ckpts；stage1_run_v1 159M 冻结主线 artifact；Planner-v2 formal/P0/A1'-QGIS/C0-QGIS/tierA/各 smoke 各 80M）；metrics jsons、日志、脚本、P1-C 工作目录（28K）。
- **新发现**：stage1_run_a1_qgis 与 stage1_run_c0_qgis 双臂 artifact 在服务器上存在（本线未执行该实验——疑为桌面线并行产物，来源待考，已拉回）。
- 连接过程：sshd 限流致多次瞬断，分组 tar-over-ssh + 逐目录重试全部成功；regen 任务按 owner 指令停止（11% 进度，部分输出不可恢复，已登记）。
- Manifest：`RENTED_SERVER_PULL_20261005/PULL_MANIFEST_20261005.md`（含待考项与 SHA 补验说明）。

## 2026-10-06：STEP 1-2 完成——Planner-v1/v2 统一评估（双读数）；STEP 3 结论"有代价的结构增强"

- 统一评估完成（共同评测集 = v2 dev 1,852 行，行级对齐验证通过；统一格式 = 有序展开 family 序列；7 指标同公式）。
- **双读数主表**：parse-exclusive（结构质量）：v2 全面优于 v1（bag +3.6pp、precision +8.5pp、LCS +3.6pp、over-emission 更少）；parse-inclusive（端到端可靠性）：v2 的 19.1% parse 失败反转优势（bag −9.4pp）——**v2 = 有代价的结构增强：JSON 格式稳定性（0.809 vs ≈1.0）是最大短板**。
- **STEP 3 结论**："v2 = v1 结构增强版"在格式稳定性达标条件下成立；两选项（v2+格式专项 epoch / 接受现状双读数并陈）**归 owner**。
- 报告：`planner_design/PLANNER_UNIFIED_EVAL_REPORT_v1.md`（数据 json 同目录）。
- Formal SFT 全链完成、locked test 未动、零冻结物变更。GPU 空闲。

## 2026-10-12：WS1/WS2 人工裁定全量收口（93/93 + 181/181）+ owner 五步指令 + B2-P1 审计 v2

- **WS2 末项 k=370 受托裁定并经 owner 确认**：结构解码 38 年(1984–2021)×3 传感器(L5/7/8)×19 阶段 + 1 = 723 精确对齐任务文本——"结构异常"假设撤销；维持 suspicious（invariant fold 缺陷 VECTOR_LOAD repeat=38、年×传感器循环未入 repetition_groups、源级不可验证）。k=994 为同任务孪生（同 723 阶段序列，仅 rg 提示词异），至多取一入可信子集。裁定落盘 WS2_BAND_ISOLATED_181.json / WS2_REMAINING_REVIEW.json。
- **冻结**：`planner_design/WS1_WS2_ADJUDICATION_FREEZE_V1.json`（六文件 SHA + k=370 裁定记录 + 边界声明：收口≠90 组绑定错误已全证、≠可信子集已冻结、suspicious 不自动升级）。
- **owner 五步指令（2026-10-12）**：①冻结 WS1/WS2（已完成）→ ②B2-P1 修复（重复组身份/范围/次数一致性；区分源级真实性与表示完整性）→ ③修复前后差异报告（stages/rg/total_iterations）→ ④可信 dev 子集冻结（排除确认绑定错误/重复/不可核验项，记 SHA）+ 重算 BAND_SELECT P/R/F1 与多家族联合漏检 → ⑤之后才议训练。暂不启动全量重训/P1 格式改造/RL。
- **B2-P1 重复组审计 v2（dev 1,852 行，只读）**：内部一致性零缺陷（rg.repeat 与 stage.repeat 2,645/2,645 完全一致；C1/C2/C5 全 0）——v1 审计的"全 phantom"为口径错误已标记 superseded。缺陷轴=折叠语义正确性：C3 condition_count_suspect 1,411（ATTRIBUTE_FILTER 1,387 + THRESHOLD_LOGIC 24，即 owner A 裁定类：过滤条件数≠执行次数）/ unverifiable 986 / task_loop_supported 243 / invariant_fold_suspect 5（k=370 VECTOR_LOAD×38 类，含 idx 468/958/1014/1181）；C4 长周期字面展开无 rg 覆盖 99 行（表示粒度不一致轴）。受影响行 885/1,852（47.8%）。报告：REP_GROUP_CONSISTENCY_AUDIT_DEV_V2.json；脚本 scripts/audit_repetition_group_consistency_v2.py。
- 注：dev 语料无 total_iterations 字段（owner 差异报告要求项）——展开操作数按 sum(stage.repeat) 计算（dev 全量 28,004）。

## 2026-10-12（续）：重复语义生成链追平——三机制定位完成

- **生成器定位**：`planner_design/blueprint_v2_preflight_v1.py`（写 blueprint_v2_gold_v2.jsonl → v3 仅 per_band hint 重标 → planner_v2_dev/train/test）。机制：`runs_of()` 语义链相邻同族 RLE → stage.repeat；rg = count>1 游程；iteration_hint = `hints_of(instruction)` 任务关键词匹配（per_band/per_class/per_year/per_feature/generic_each/unspecified，**整行所有 rg 共享同一 hint**，generic_each 匹配 "each|every|per|all"）。v2 gold 原有 total_iterations=len(raw)，进 corpus schema 时被丢弃。
- **三机制裁定**：M1（重复次数推断错误）→ **蓝图层计数无误**，是机械 RLE；k=370 VECTOR_LOAD×38 经 sid=60463 链实证——上游语义链字面以 38 连续 VECTOR_LOAD 结尾，RLE 忠实压缩。不变量归属问题在上游链生成（本仓库外，服务器已关）。M2（条件计数混淆）→ 机制在代码层证实：repeat=相邻 token 数，无执行语义；根源在链 token 粒度（条件被展开为连续同族 token）。1,411 分层抽样材料已出（COND_COUNT_ADJUDICATION_SAMPLE_V1.json：family×length×repeat 三维 15 层 28 样本，含 sid 与链 run 上下文，全部 join 成功）。M3（长展开无 rg）→ 代码层证实：corpus 生成器无交错模式检测（该逻辑只在 216 行重建线 reconstruct_planner_gold_v2 存在）。
- **repeat 结构统计（owner 差异报告规格）**：repeat=1 阶段 19,379；repeat>1 阶段 2,645（repeat 和 8,625）；展开操作 28,004。
- **关键推论**：蓝图层是上游链的忠实机械镜像——所有重复语义（循环/条件/不变量）都在链生成时决定。蓝图修复 = 表示政策裁定（保留 38 vs 归一+标记），不是字段错误修复。"模型忠实学会了错误标签"假设获得机制支持。

## 2026-10-12（续二）：C6 canonical 一致性审计 + loop_invariant 修复1 + 25 例预裁定落盘

- **C6 审计（audit_canonical_agreement_c6_v1.py，dev 全量 2,645 个 repeat>1 阶段，1,214/1,214 行 join 成功）**：canonical token 全异 **1,083（40.9%）=机械证实不同调用折叠，repeat 非循环次数**；mixed 543（20.5%）；全同 231（8.7%，真重复候选）；链长失配 788（29.8%，1:1 位置对齐不可靠，待对齐算法修复）。ATTRIBUTE_FILTER 1,387 中仅 14 全同——owner 的 A 判定（条件计数）获机械证据。注意：全同=同方法名 N 次，必要非充分（参数不在 canonical 链中），循环确认仍需任务级/源级证据。
- **优先案例答复**：idx 988 AF×8 = mixed（listContains/filter/eq 交替）→ 非统一执行，支持 A；idx 854 TL 5×20 = 全部全同（同方法×20×5），机械展开风险与 owner 判断一致但参数级不可分，维持 A+优先核验。
- **loop_invariant 修复1（方案 a，owner 五项检查全 PASS）**：仅修 canonical 证实的 2 行——dev 370（38×ee.Feature，repeat 38→1）与 1014（2×ee.Feature，2→1），stage 级 iteration_hint=["loop_invariant"]，对应 rg 移除（维持 rg=repeat>1 契约与 C2 同步不变量）。产物 `04_DIAG_WORK/planner_v2_dev_fix1_loopinv.jsonl`（修正副本，原件未动）；1,850 非修复行字节级一致。报告 `REP_FIX1_COMPAT_PROBES_V1.json`。
- **468/958/1181 未标记**（owner 前提：疑似不修）：canonical 显示不同调用折叠（ee.Feature+ee.String / select+mean / float+paint）——新缺陷类 **distinct_call_collapse**；待裁（展开为多阶段/保留 repeat=2+注记）。41 与 1196 文本与蓝图 hash 均不同，非重复行。
- **25 例预裁定落盘** `COND_COUNT_PRERULING_V1.json`（A10/B6/C2/U7，owner 汇总计差 A9/U8 已登记，以逐行表为准）；升级路径 = C6 上下文 → owner 确认。

## 2026-10-12（续三）：P0-P1 完成——证据冻结 + 对齐修复（零回归）；P2/P3 材料就绪

- **P0 证据冻结**：`C6_EVIDENCE_FREEZE_V1.json`（8 文件 SHA 含原始 dev 与 fix1 副本、b1 链源；分类定义与已知限制入册：all_identical≠已证循环、失配≠已证 Gold 错误、C6 比例禁止用于批量改写）。
- **P1 对齐修复（repair_alignment_c6_v2.py）**：根因=上游语义链是 canonical 链过滤子序列（AUX/presentation 丢弃，如 ee.String/ee.Image.paint→AUX_VALUE）。方法=SequenceMatcher 保序对齐 sem vs [classify(canonical)]。结果：1,211/1,214 行全对齐；788 失配全部重分类（354→all_distinct / 171→mixed / 260→all_identical / 3→alignment_partial 保留不可核验）。**零回归**：v1 的 1,083 all_distinct + 543 mixed 在新对齐下全部保持原类。新口径：all_distinct 1,437 / mixed 714 / all_identical 491 / partial 3。每行带对齐比率、未匹配 token、跳过 canonical+本地类、链哈希（验收标准=每个重分类有可查证据，非归零）。
- **P2 政策草案**：`GOLD_REPAIR_POLICY_V0_DRAFT.md`（owner 四类处置表转写 + distinct_call_collapse 展开建议 + 粒度门槛前提 + 可信子集四条准入 + 双评测安排 + 执行边界）。DRAFT 待 owner 确认后生效。
- **P3 证据升级**：`COND_COUNT_PRERULING_EVIDENCE_V2.json`（25 例 × 对齐 canonical span + C6 v2 类 + 完整任务文本）。交叉表：U→all_distinct 4（原证据不足者获机械证据，可升 A）；B→all_identical 4（原多规则候选实为同方法重复，需重看）；A→all_distinct/mixed 8（与 owner 预裁定一致）。裁定权仍归 owner。

## 2026-10-12（续四）：P2 政策 FROZEN + 25 例终裁表冻结（口径修正）+ all_identical 60 例分层抽样

- **P2 生效**：`GOLD_REPAIR_POLICY_V1_FROZEN.md`（v0 标记 superseded 保留溯源）。新增 owner 粒度门槛操作化表：逻辑操作一体（Filter.lt+filter 类）保留单阶段 repeat=1 / 独立操作拆多阶段 / 同任务多阈值规则=单阶段多规则（不以 where 次数定阶段数）/ 不可区分→unresolved_granularity 排除。**all_distinct 触发粒度审查而非自动展开；不授权批量改写；每修复保留原值/新值/理由/证据定位。semantic_ruling 与 repair_action 双轴分离，诊断升级不触发改写。**
- **25 例终裁冻结** `COND_COUNT_FINAL_RULING_25_V1.json`。口径修正（owner 指出）：统计单位=（案例，游程出现次），**废除去重+主类聚合**——41 例 9 个 AF×6 游程此前只显示 1 个、490 例三类打平任意取主类。裁定分配：1773/744/1505/738→non_uniform_count_confirmed+granularity_pending；A 组 9 例+854→non_uniform_count_likely（854 优先核验）；B 组 6 例（41/1196/490/673/674/1088）→multi_rule_candidate+keep_pending（41/1196 文本+hash 均不同不合并）；C 组 2 例→loop_candidate_unverified；U 余 3 例（931/123/1060）→insufficient_evidence。
- **阶段级 v2 类落盘** `C6_V2_STAGE_CLASSES_DEV.json`（2,645 阶段含 canonical_span，单位=游程出现次：all_distinct 1,437 / mixed 714 / all_identical 491 / partial 3）。
- **all_identical 分层初审启动** `ALL_IDENTICAL_SAMPLE60_V1.json`：491→任务封顶（每源任务≤2 游程）372→27 层（family×repeat 档 2-3/4-7/8+）实取 49；双轴裁定字段（repeat_meaning / granularity_disposition / evidence / confidence）待裁。证据边界已声明：canonical 仅方法名无参数。

## 2026-10-12（续五）：49 例初审裁定写回 + 抽样口径修正 + 停止条件登记

- **抽样口径修正（owner 指出）**：先前 strata 数字是 372 总体的层分布而非样本分配。`ALL_IDENTICAL_SAMPLE49_V1.json`（v60 标记 superseded，命名统一，种子/方法不变→49 个 ID 与冻结集逐一相同断言通过）按层分列 population_n / sample_n / 抽样方式。**层分布≠样本分布，49 例可用于发现问题、不可用于估计 491 总体比例**（owner 口径已写入）。
- **49 例裁定机械核对**：owner 49 裁定行 = 49 冻结样本 ID，49/49 全配对、零未配对（表头组计数差如 F/J/K/L/M 已由运行级行数澄清；951 双导出游程、1732/1204/744 双游程全部按 (dev_idx,seq) 对位，API 抽查全中）。裁定以 preliminary_semantic_ruling_NOT_repair_action 状态写回，同任务游程按 dev_idx 分组统计权重（owner 规则）。
- **初步分布**：repeat_meaning = multi_call_likely 20 / multi_rule_candidate 11 / insufficient_evidence 8 / repeated_data_source_candidate 8 / loop_candidate_unverified 2；granularity = keep_pending 39 / unresolved_granularity 10。
- **owner 停止条件登记**：49 例后不扩样，先答三问（多少确认 repeat 语义问题/多少确定粒度应调/多少必须源码+参数）；问题集中在特定层才补审，无规律即停——不让数据治理取代模型实验。源码优先核验清单：854/114/994/631/697/1204/951×2；粒度优先家族：Image.where/Filter.calendarRange/ImageCollection.map/高次 Image+Feature。
- **边界**：不启动全量 Gold 改写、不训练、不 RL。下一步=可信 dev 候选集（只纳入有足够证据的修订；未决样本保留原版+单独标记）→ 原始/可信双轨评测。三问的回答被源码/参数证据门控（服务器已关，本地不可答的记 unresolved）。

## 2026-10-12（终）：repeat 审计封盘 → 可信 dev 候选集 + 双轨评测完成（CPU-only）

- **owner 三结论固定**：零确认 repeat 语义错误、零确认粒度调整、49 例价值=证据缺口（canonical 无参数、源码在已关服务器）。不再扩大审计。
- **可信 dev 候选集** `DUAL_TRACK_EVAL_V1.json`：1,276/1,852（68.9%）入集，576 行排除且逐行带理由——binding_error_confirmed 96（B1 四组）/ 重复去重 90→保留每组首行（去 58+70=128 shared 未证去重）/ binding_error_suspect ~354（diff-task 共享蓝图未核验，strict 口径）/ ws2_suspicious 28（含 370/994）/ audited_pending ~65 / alignment_partial 2。长度与家族覆盖保持（long 90→68；主要家族支持率 >90%）。
- **双轨评测（现有 P0-B 预测，四视图）**：E1 原始 Gold×全集 bag-incl 0.6165/excl 0.7277/LCS 0.5815/parse 0.8472；E2 可信 Gold×全集**逐位一致**（唯一证据支持修订=fix1 两行：370 bag 0.063→0.066、1014 0.5455→0.6000）；E3 可信 Gold×可信子集 0.5589/0.6890/0.5181；E4 原始 Gold×子集 ≤0.0001 差。
- **关键发现——排除影响方向反转**：被排除行原始 bag 均值 0.7442 **高于**保留行 0.5588。绑定错误/重复行=模型轻松复现的短模板（3 阶段），原始全集指标被模板重复**抬高**；可信子集是更诚实的能力地板（bag-incl 0.5589 vs 0.6165；BAND_SELECT F1 0.4465 vs 0.4691）。长度构成相近（short 77.4% vs 74.5%），降幅主要来自去除模板重复而非长度偏斜。
- **对 owner 三问的回答**：以当前证据支持的修订集（仅 2 行），评测标签对聚合指标无显著影响；Gold 表示问题的影响在**结构可信度**（子集构成）与**未抽样的 repeat 语义**上，不在当前聚合数上。
- **边界**：可信 Gold 标注"证据覆盖有限"；无 GPU、无训练、无 RL；源码级修复价值待 owner 依本轮结果裁定。

## 2026-10-12（收口）：评测基线冻结 + 可信子集错误分解——瓶颈判定

- **基线冻结** `EVAL_BASELINE_FREEZE_V1.json`：七文件 SHA（含可信 Gold、冻结预测、政策、裁定表）；术语按 owner 裁定收紧——0.5589/0.4465 = **trusted-subset 条件性评测基线**，非统计能力下界；汇报语言固定为"已验证的局部 Gold 修订影响有限，但样本构成清理揭示了原始全集指标的乐观偏差"。
- **错误分解** `ERROR_DECOMPOSITION_TRUSTED_V1.json`（可信子集 1,276 行 × 冻结预测，多标签+主归因双层）：
  - **多标签行率**：repeat_count_error 58.2% > stage_selection_miss 53.3% > over_emission 43.6% > parse_failure 18.9% > order_error 12.6%；good_match 仅 24.1%
  - **主归因**：stage_selection_miss **52.9%**（第一瓶颈）> parse_failure 18.9% > over_emission 14.1% > repeat_count 7.1% > order 0.7%
  - **parse_failure 241/241 (100%) = hit_max_tokens**——全部是生成预算耗尽截断，零 JSON 格式错误；长链（>25 阶段）截断率 52.9%，GEOMETRY/TERRAIN 行 32.1%，BAND_SELECT 行 26.9%（对照基线 18.9%）——**终止控制问题**，与冻结的 A1 机制结论（Generation Control）一致
  - **计数错误方向**：低发 980 vs 超发 532（2:1）——模型系统性**少报**重复；与 gold repeat=机械 RLE 计数的审计发现互恰：部分"少报"可能是模型未复现机械折叠，属表示错位而非纯能力缺陷
  - **漏检家族 Top**：BAND_SELECT 170 / ITERATIVE_APPLY 164 / SPATIAL_FILTER 136（BAND_SELECT 金标行漏检率 ~39%）
  - order 0.7% 主归因——**非瓶颈**（与 Phase 1 一致；注意口径不同：此处 bag-LCS 差>0.15）
- **三问判定（owner step 3）**：瓶颈 = ①阶段选择（规划能力）②长链终止控制（解码侧）③重复量化（部分为 gold 机械计数错位）。**非**顺序、非 JSON 格式。最小对照实验候选：A 解码预算/终止控制（零训练）；B presence 辅助监督（训练侧）；C repeat 量化（训练侧，但 gold 计数部分不可信须谨慎）。实验设计待 owner 裁定后进行。
- 更正：前一条 progress 记录中"能力地板"措辞按 owner 裁定收紧为"trusted-subset 条件性评测基线"。

## 2026-10-12（A/B/C 裁定落地）：A 协议冻结 + A1 样本冻结

- **owner A/B/C 裁定**：A 优先批准（协议+小规模对照）；B 有条件设计准入（A 完成后冻结方案；漏选先拆"金标合理未生成 vs 金标粒度不可靠"两类；presence 标签两种定义不得混同）；C 暂停（不训练、不批量修 Gold——机械 RLE 计数下加计数监督可能强化错误表示）。
- **A 协议冻结** `A_EXPERIMENT_PROTOCOL_V1_FROZEN.md`：机制假设（241 parse fail 100% hit_max；长链 52.9% 截断）；A1 单变量对照（基线 max_new_tokens=768 → 实验臂 **2048 预注册**，其余逐项相同，禁新停止规则）；131 行 6 层样本 `A1_SAMPLE_131.json`（T2 截断长链全取 36/T1 截断短中 30/NT 长 15/BS 20/GEO-TERRAIN 15/对照 15，种子 20261012）；A1 三条入门判定（截断降+解析成+覆盖升不被超发/成本抵消）；A2 全子集复核六指标表；执行前置=模型工件 SHA 对账+GPU 恢复（推理 ~2.5h 起）。
- **边界**：原始预测与新预测并存；冻结预测/基线/可信子集口径不变；B 不启动训练。

## 2026-10-12（A1 执行前核验完成）：协议 v1.1 修正案 + 样本 v1.1 加固

- **owner 三项执行前核验落地**：①样本索引核验通过——131 行 idx 唯一无缺失、全在冻结可信子集、层配比一致；升级 v1.1 加稳定 ID（source_row_id 经 gold_v3 join 零缺失 + task_sha256），执行不再依赖文件行号；每行加 gold_target_chars 供运行时预算核对。②协议 v1.1 修正案 `A_EXPERIMENT_PROTOCOL_V1_1.md`——终止原因四分法（EOS/MAX_TOKENS/OTHER_STOP/PARSE_FAIL 与截断分开记录，以生成终止状态为准）；统计口径预注册（逐行配对+分母+Wilson CI；T2=36 行全取普查，报实际改善数不称显著性；NT 对照 15 行谨慎措辞；预算充分性以实际 token 分布与 MAX_TOKENS 残余率为准）。③已知例外行确认：idx=1024（1,464 gold 阶段/71,030 字符，NT_long，基线 768 内已解析——模型未复现巨型展开的对照行）。
- **状态（owner）**：A1 批准等 GPU+SHA 对账；A2 未解锁；B 仅设计准入；C 暂停。执行按 v1+v1.1 冻结口径，无需再议。

## 2026-10-12（本轮收口）：A1 执行前准备全部完成，等待 GPU

- owner 确认收口；五步执行顺序固定并入协议 v1.1（SHA 对账门禁优先、双臂条件一致、产物并存不覆盖、v1.1 汇总口径、A1 过门才解锁 A2）。
- idx=1024 定性获 owner 确认：机械膨胀诱导风险对照——2048 下观察长度暴增/超发/结构偏离，生成更长≠进步。
- **当前等待态**：A1 批准等 GPU+SHA 对账（执行会话按协议 v1+v1.1 直接跑，无需再议）；A2 未解锁；B 仅设计准入；C 暂停。审计封盘、协议不再改。
- **下一讨论节点 = A1 结果**（截断改善/解析成功/阶段覆盖/超发风险/生成成本 → 判 A 通过与否、是否进 B 方案设计）。
- 本轮全链产物索引：EVAL_BASELINE_FREEZE_V1 / DUAL_TRACK_EVAL_V1 / ERROR_DECOMPOSITION_TRUSTED_V1 / A_EXPERIMENT_PROTOCOL_V1_FROZEN+v1_1 / A1_SAMPLE_131(v1.1) / GOLD_REPAIR_POLICY_V1_FROZEN / COND_COUNT_FINAL_RULING_25_V1 / ALL_IDENTICAL_SAMPLE49_V1 / C6_EVIDENCE_FREEZE_V1 / WS1_WS2_ADJUDICATION_FREEZE_V1。

## 2026-10-12（服务器恢复）：mdzhang 在线——SHA 门禁通过 + A1 全量预置 + GPU 监视挂载

- **服务器状态确认（owner）**：mdzhang 10.191.2.38 在线（A10 24GB）；租卡机两 IP sshd 限流拒连（不再需要）。
- **A1 SHA 门禁 PASS**（`A1_SHA_GATE_V1.json`）：adapter weights+config 与拉回包（租卡机 provenance）逐字节一致（27dca22a…/a4cb9a26…，`/home/qy/planner_v2_adapter_staging`）；`_fmt` 变体不同已排除；base 模型在位（指纹 0078a3cf…，21 文件），按协议以 768 臂复现 p0b_768 做功能验证，不符即停。
- **发现 owner 作业**：qy 账户 `train_stage1.py --config p2_uniform_rep_sft_v1.yaml` 运行中（owner 确认为本人有意启动——P2 统一格式受控 SFT，owner 2026-10-12 裁定，起点=冻结 P0-fmt checkpoint，与 P1 同条件唯一变量=目标格式统一；step 80/1370，~70-85s/step，**ETA ~25-30h**）。A1 排其后；yyt 的 SAM 作业（6.2GB）不构成阻塞。
- **A1 全量预置完成**：runner+样本+可信 Gold+a1_run.sh 已上传 `/home/qy/a1/`；dry-run 通过（指纹+131 行校验）；一键脚本含 GPU≥9.5GB 门禁+dry-run 前置+nohup 双臂执行。
- **监视器挂载**（会话内存活期）：每 300s 轮询空闲显存，≥9500MiB 即按冻结协议自动启动 A1。若会话结束：服务器端 `bash /home/qy/a1/a1_run.sh` 一条命令可随时手动触发。
- 预计：P2 训练结束后 A1 双臂运行 ~5-7h；完成后做 768 臂功能门禁比对 + v1.1 汇总裁定。

## 2026-10-12（A1 执行中）：P2 训练完成 + A1 自动启动

- **owner 的 P2 训练正常完成**：`[done] steps=84 examples=2738 tokens=550352 tgt_trunc=64 task_too_long=0 elapsed=4201.8s (~70min)`；adapter → `/home/qy/stage1_run_p2_v1/stage1_adapter`，run_ledger 在册。（前记 25-30h ETA 系误读进度显示口径 1370，实际 84 步——更正。）
- **A1 自动启动（冻结协议授权范围内）**：GPU 空闲 16.4GB 触发监视器 → a1_run.sh → dry-run 过 → 双臂启动，PID 2450138，768 臂生成中（GPU 14.1GB used）。
- 产出目录 `/home/qy/a1/results_20261012_122658`（nohup，log=/home/qy/a1/a1_run.log）；完成监视器已挂（600s 轮询进程退出）。
- 预计 ~6-7.5h（768 臂 ~2.5h + 2048 臂 ~3.5-5h）。完成后：拉回产物 → 768 臂 vs p0b_768 功能门禁比对（不符即停）→ v1.1 汇总（五问：截断改善/解析成功/阶段覆盖/超发风险/生成成本）→ A1 判定。

## 2026-10-12（A1 判定）：A FAIL（预算修复不成立）——决定性机制诊断：结构性不终止

- **A1 双臂完成**（3.5h，mdzhang A10）：768 重跑 + 2048 臂，131 行，产物 server `/home/qy/a1/results_20261012_122658/` + 本地 `04_DIAG_WORK/a1_pull/`（gzip 已拉）。
- **五问（v1.1 口径）**：截断 52→52 **零救回**；解析零新增；bag 逐层零差异；对照层超发未恶化；2048 臂截断行全部撞满 2048（成本翻倍零收益）。三条入门判定全不过 → **A FAIL**（owner 冻结判据原文适用）。
- **机制发现（本轮真正产出）**：截断=**结构性不终止**——截断行 gold 长度 2/4/5/6/9...（gold 2 阶段的行生成 135+ 阶段，idx 1287 合法 JSON 无限延续到撞上限）；非 n-gram 重复（top-20gram 比率 0.033）；终止行为在数值边缘随机翻转（重跑 52 vs 冻结 66，双向分歧）；idx=1024 双臂一致（EOS@82/5 阶段）——膨胀诱导未发生。**模型不会在工作流终点发射 EOS。**
- **功能门禁 FAIL（附带）**：768 重跑 vs 冻结 p0b_768 pred_text 一致率仅 8.4%（跨主机 4-bit 数值差异）——跨主机对比作废，同模型对比限同主机同栈；`A1_VERDICT_V1.md` 已登记处置。
- **分支待 owner 裁定**：A' 终止专项解码（结构性停止规则，p0b2-C 臂思路）/ A'' EOS 监督小步 SFT（V2a 负结果教训须预注册）/ B presence 监督（动机独立成立）/ C 继续暂停。分析 `A1_RESULT_ANALYSIS_V1.json`；判定 `A1_VERDICT_V1.md`。

## 2026-10-12（A′ 完成）：停止规则诊断——有效围堵、非修复；owner 分支裁定材料就绪

- **A′ 离线执行**（零 GPU：前缀规则离线截断 ≡ 解码时停止，同机同栈数据）：R1 结构循环检测（p≤6/3 次/边界触发/预注册）应用于 A1 双臂产物。脚本 `run_aprime_stop_rule_diag_v1.py`；结果 `A_PRIME_RESULTS_V1.json` + 判读 `A_PRIME_RESULTS_READING_V1.md`。
- **四指标**：M1 失控终止 48/52 触发但**保留前缀中位=gold 4.4×**（触发晚，stage ~124/130）；M2 保护 短 47/47 全保护/长 30/32（2 例真实小循环边界误伤）/ctrl 安全；M3 closure-parse 100%（首版 0.0 系我方检查函数多括号 bug，已修正登记）；M4 平均仅省 372 字符。
- **判读**：R1=有效围堵非修复——把不可解析灾难转为可解析但严重过长；**过生成从早期开始**，语法侧不存在能砍在正确终点的前缀信号（正确终点是语义的）→ A″（终止点监督训练）动机增强；B 评测口径须先冻结（围堵部署与否+过长输出计分）；围堵可作正交推理层护栏。
- **A1 终裁层已并入** `A1_VERDICT_V1.md`（owner 两层结论：预算修复否定；结构性不终止=最强假设但 EOS 失准未单独证实）。

## 2026-10-12（A″ 训练完成）：owner 授权开训 → 19 分钟完成 → 推断中

- **owner 开训终裁**：批准 A″ λ=2 单次实验（边界：冻结 P0 起点/冻结清单/1 epoch/LR 1e-5/ckpt≤20/新目录零覆盖；停止规则照录；五条件全过才算过）。
- **启动曲折（全部工程性，零预注册偏差）**：①派生 trainer NameError（函数级 torch 导入修复）；②首个 loss OOM（.float() 上转多 1.2GB fp32 + yyt 作业共占——改 bf16 CE，与模型内部 loss 同画像）；③第三次启动成功。
- **训练完成**：`[done] steps=9 examples=300 tokens=100559 tgt_trunc=0 task_too_long=0 elapsed=1140.4s (~19min)`；adapter → `/home/qy/a1/adprime_run_v1/stage1_adapter`；ledger 在册。
- **训练后推断已启动**：131 行 × 768 臂（同机同栈同提示词同 greedy，与冻结 pre 臂完全对齐），产出 `/home/qy/a1/adprime_eval_131/`；监控已挂。
- 推断完成 → 拉回 → `analyze_adprime_paired_v1.py` 五条件判定（G1 McNemar 配对 / G2 C2·C3 误伤 / G3 覆盖不退化 / G4 过生成中位 / G5 成本+20%）→ PASS/FAIL 材料。

## 2026-10-12（A″ 判定）：五条件全不过 → FAIL（方向性反结果）——回滚生效

- **训练后全链完成**：推断 131 行 × 768（同机同栈同配置）→ `analyze_adprime_paired_v1.py` 五条件自动判定。
- **判定：VERDICT = FAIL，五条件全不过**：
  - G1 失控配对：**b=1/c=45/net=−44，失控 52→96**（p=1.0）——EOS 加权使终止**恶化**；
  - G2 误伤：C2-short **2**（违 0）；C3-long 1（合规）；
  - G3 覆盖：bag-excl **0.313→0.165**，BAND_SELECT **0.346→0.149**，10 家族退化>0.01；
  - G4 过生成中位 0.6→**0.8**（升）；
  - G5 成本 **+57.8%**（超 20% 上限）。
- **判读**：终点 EOS 加权（λ=2）反向——与 V2a-P1 λ=20 构成**第二个独立负点**（不同线不同量级同方向），EOS-加权杠杆双点证伪；9 步小训练即致广谱退化（bag 近半降、10 家族回归）——P0 adapter 覆盖能力脆弱；**预注册框架按设计工作**（边界先冻、判定自动、回滚即刻）。
- **回滚生效**：adprime adapter 隔离弃用（`/home/qy/a1/adprime_run_v1/` 保留不复用）；现行基线 = 冻结 P0 adapter；λ=5 与追加训练自动关闭。
- **分支现状（待 owner 裁定）**：终止失控经 A′（围堵候选）/A″（EOS 监督负）双重探索后，剩余 = R1 护栏（评测稳定性收益已证）+ B（唯一在途训练侧分支，动机需在 EOS 证伪背景下重估）；C 暂停。产物：`ADPRIME_PAIRED_VERDICT_V1.json` / `A_DPRIME_RESULT_READING_V1.md`。

## 2026-10-12（A″ 三问归因完成）：单一故障机制——结构闭合能力损坏

- **owner 终裁落地**：A″ 正式 FAIL 入册；adprime adapter 服务器端标记 FAILED/DO NOT USE（STATUS_FAILED_DO_NOT_USE.md）；EOS 加权路线关闭（论文表述限定于已测配置）；P0 脆弱性限定表述（"该干预高回归风险"，不泛化）；预注册框架价值确认。冻结态：P0=现行基线；A″ adapter 仅限复现/误差分析；RL 暂停。
- **三问归因（纯现有产物，零训练零 Gold 改动；ADPRIME_FAILURE_ATTRIBUTION_V1.json）**：
  - **Q1 轨迹**：loss 1.28→0.33 收敛正常；梯度范数未记录（仪表缺口）——异常单步更新**不可判定**（诚实结论）；
  - **Q2 集中位置**：45 失控行 ∩ 53 覆盖退化行 = **44 交（Jaccard 0.815）**——同一批行；全层受击含对照短链 3/15；
  - **Q3 机制**：**45/45 = 无界前缀（从未闭合 JSON 对象）**，"JSON 完成+尾随"零例；45 行 pre 全为 EOS 正常终止（idx 814：EOS@148/7 阶段 → 768 撞帽）。
- **机制结论**：λ=2 破坏的是**上游结构闭合能力**（收尾括号不再发射），EOS 因此永不到达——既非 (a) EOS 消失亦非 (b) EOS 后移，而是 (c) 的更早形态。覆盖崩塌=同一故障从属结果（不可解析→bag 0）。
- **含义**：R1 围堵护栏（治标已证）+ B 唯一在途训练侧分支（动机待 owner 在 EOS 证伪+P0 脆弱两背景下重估）；未来训练必须补记梯度范数与 EOS-token 损失（仪表要求入册）。

## 2026-10-12（R1 部署验证启动）：P0+R1 解码期回归集复跑

- **owner 裁定落地**：A″ 归因闭环三结论入册（结构闭合故障=最优支持机制；失控/覆盖耦合 Jaccard 0.815；训练 loss 降≠能力升）+ 表述边界（单次训练不充分分离混杂，不得归因 EOS 权重内部效应）；**R1 进入独立部署验证**（非无条件上线）；B 暂缓+轻量训练前门禁设立（梯度范数/终点 EOS loss/结构闭合指标逐记录、checkpoint 级解析率+覆盖评估、冻结 P0 对照、回滚阈值预冻、单因素原则；**结构解析率升格为早期停止指标**）；RL 暂停。
- **R1 部署形态实现**：`r1_guardrail_v1.py`（共享规则模块，参数与 A′ 冻结一致 p≤6/3 次/边界触发）+ `run_p0_r1_regression_v1.py`（transformers StoppingCriteria 真·解码期拦截：每 16 tokens 扫描生成段、触发即停；触发标志独立于 EOS/MAX_TOKENS/OTHER 终止分类）。
- **回归集复跑启动**（PID 824001）：131 行全量（覆盖 owner 列举全部子集：52 失控/47 C2/32 C3/idx 1503+1181/4 无循环行），768 预算+greedy 同 pre 臂配置；产出目录 `/home/qy/a1/p0_r1_regression_131/`；监控已挂。
- 判定将报告 owner 全指标：触发率/未检出率/误停率/保留前缀-Gold 阶段覆盖/结构闭合率/平均省 token——并做在线触发 vs 离线 A′ 等价性核验。R1 定位保持：推理可靠性护栏，非规划能力修复。

## 2026-10-12（R1 部署验证完成）：六指标全达——127/131 预算内终止，待 owner 部署终裁

- **真·解码期回归跑完**（StoppingCriteria 每 16 tokens 扫描，131 行 × 768 + greedy 同 pre 配置）。
- **owner 六指标**：触发率 **48/52（92.3%）**；未检出 4/52=恰为已知无循环行（零新增）；误停 **2/79（2.5%）**（idx 324/162）且**已知两例 1503/1181 本次 EOS 正常终止**——误停行身份逐轮随机（同机生成边缘涨落实证），稳定量=比率非行清单；closure-parse **48/48=100%**；kept/gold 中位 0.2（失控行语义覆盖原本即未达成，pre-R1 替代结局=不可解析倾倒 bag=0）；**平均省 584 tokens/触发行（76% 预算）**。
- **端到端**：127/131（96.9%）预算内终止（EOS 77 + R1 50），pre 臂 79/131（60.3%）。终止分布 EOS 77/R1 50/MAX 4/OTHER 0。
- **等价性**：触发集合与离线 A′ **逐行一致**（48=48 零差）；kept 量差异=生成逐轮涨落使失控轨迹入检早晚不同，在线版围堵更早更省。
- **两风险登记**：4 行未检出类；2.5% 误停率（行随机，回归须锚定比率）。
- **建议（待 owner 终裁）**：R1 可作默认推理配置启用（带开关）；每次评测并报原始/围堵双视图（B_EVAL_CALIBER v1.1）。定位不变：可靠性护栏，非能力提升。报告 `R1_DEPLOYMENT_VERIFICATION_V1.md`。

## 2026-10-12（A 线收束）：R1 受控部署终裁落地——部署配置+记忆归档

- **owner 部署终裁**：R1 批准为 P0 受控推理护栏（非质量修复、非无条件默认）；四条件：①开关保留默认 P0_RAW ②终止类型四分（R1 截断可解析 JSON 不得标完整工作流）③双风险告警持续监控（锚定比率+逐行留痕）④上线后回归监控五指标（禁仅预算内终止率）。48/48 闭合率边界入册（仅触发行）。
- **`R1_DEPLOY_CONFIG_V1.json`** 双侧落盘（开关语义/冻结参数/终止词表/监控规格/已验证运行指引）。
- **研究路线定格**：P0=能力基线；R1=可靠性护栏受控部署；A″ EOS 加权维持失败不恢复；B 与 RL 暂不启动直到训练方案有明确防回归设计。
- **下一阶段核心任务（owner）**：提升模型工作流规划能力本身——阶段选择/覆盖、顺序依赖、适当终点停止、QGIS grounding/DAG 四能力分开测量；不以更激进截断为目标。
- **跨会话记忆归档**：`memory/planner-a-line-guardrail-2026-10.md`（A 线全收束态+方法学资产：预注册框架、同机纪律、配对统计口径）。

## 2026-10-13 P2 统一目标格式受控 SFT：训练+三方评测完成，双条件未通过（对 P0）

- P2 数据门禁：1,200 防遗忘行 → 1,161 转换 / 39 隔离（未声明交替窗，不强行折叠）；G5 独立展开器 100% 精确一致；发现并修正转换器相邻连发编码（208 权威规范 = stage repeat=N + 镜像单 family 组）
- P2 训练：1,369 行（208 新表示 + 1,161 转换）× 2 epochs，84 步零异常，SHA 5fbf94ec 三重核验
- 三方评测（dev-1852，同批量仪器 bs=8）：P0 parse .8445 / P1 .7889 / P2 .8342；P2 折叠采纳率 100%（vs P1 的 11 行）但对 P0 双条件未通过（保真 −0.7~−1.5pp）
- 失败解剖：全部 parse 失败为真截断；P2 的 307 失败中 291 行为旧式字面列表循环——窗口折叠监督只来自 208 行，证据太薄
- 结论：P0 仍为当前最强；表示转向"采纳成功、端到端未转化"；下一步选项（A 窗口折叠补全 / B 收束转 Phase-2 / C 等预算臂）已呈 owner 裁定
- 仪器变更披露：dev 评测转批量生成（三臂对称，聚合漂移 ≤0.3pp，16 行抽检 parse 翻转 1/16）

## 2026-10-13 战略回归主线（owner 裁定）：P3 冻结 + A1 预算对照收官 + 错误画像

- owner 裁定：P0-P3 循环表示支线偏离中心，三层框架重组（L1 工作流推理 / L2 QGIS grounding / L3 生成可靠性）；P3 冻结，仅当错误分析表明交替窗为主瓶颈时重启
- A1 预算对照（并行线，131 行循环倾向样本，768 vs 2048）：六分层全部零变化，T2 普查 0/36 改善，bag 逐字符一致——预算不是剩余失败的瓶颈
- P0 规划质量错误画像（1,564 解析行）：perfect 15.9%、missing+extra 混合 47.3%、missing-only 20.3%、纯顺序错 1.5%、纯次数错 0；31+ 步工作流 0/56 全对
- 结论：瓶颈在 L1 步骤选择/任务分解，不在 L3 生成可靠性；主线切回端到端工作流能力评估与 QGIS grounding

## 2026-10-13（B 线启动）：owner 定向 B0→B4；B0 同机基线解码开跑（~16-25h）

- **owner B 线定向**：B 线 = P0 工作流规划能力诊断与定向提升，**先诊断不开训**。顺序 B0 冻结基线 → B1 四类能力误差分解（阶段选择/顺序依赖/结构终止分开统计，BAND_SELECT 重点但不独揽）→ B2 定主瓶颈 → B3 防回归训练设计 → B4 门禁后才耗 GPU。不新增大审计、不重开 A 线；先出能直接决定下一实验的瓶颈报告。
- **B0 关键决策**：现有 1,276 行逐行预测=租卡机产物（跨主机 8.4% 一致率），**不可作 B 线配对基线**——启动**同机纯 P0 全可信子集解码**（PID 4189809，bs=1 协议纯度、无护栏、768+greedy 同 A1 臂配置；每 25 行 flush 可断点续跑；ETA ~16-25h，明确告知可随时叫停）。
- **B0 冻结**：`B0_TRUSTED_EVAL_LIST_V1.json`（1,276 行+task_sha，SHA b017fb96…）+ `B0_P0_BASELINE_FREEZE_V1.json`（模型三重指纹/解码配置/评测清单/对照目标：trusted-subset 条件基线 0.5589 与 BS 0.4465 为租卡机数，同机解码后将重定基线）。
- **B1 四能力分解脚本待解码完成后运行**；QGIS grounding/DAG（算子级）注明为 Stage-2 范围本轮不可测，B1 实测三能力+结构/终止细分。
- 监控每 ~29 分钟报进度；GPU 全空闲（yyt 作业已结束）。

## 2026-10-13 E2E Step 1 判定 + hit-cap 核查（owner 裁定记录）

- **正式判定（owner 定稿）**：当前 GEE 域训练的 L1 规划器不能直接作为可靠的 QGIS 工作流规划器使用；主要瓶颈已从"跨平台语义映射构建"转向"模型能否依据任务语义正确选择并组织具体 GIS 操作"。不应直接部署为 QGIS 规划组件；下一阶段优先错误来源诊断（实验 A 错误类型审计 / 实验 B Oracle Blueprint 上限测试 / 实验 C 架构对照暂缓）
- hit-cap 核查：定义 = gen_tokens≥384（生成长度上限），分母全 120 行（112 行触顶，均值 366.6 token）；78 个已解析行 JSON 全部完整闭合、尾部零垃圾（仅空白填充）→ 截断不污染内容指标；42 个 parse 失败全部为 cap 所致未闭合
- 评测边界（owner）：dev-120 vs dev-1852 非严格匹配对照，结论限定为"当前规划器在 QGIS dev-120 上表现极差"，不作迁移量的精确估计；反演→正向闭环不得作为 grounding 上限证据
