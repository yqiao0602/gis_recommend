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
