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
- 服务器结果：21,085 source、4,506 eligible、300 pilot、300 unique IDs、T0=0、ineligible=0。
- 分层：ordering deterministic/fallback=134/166；source custom/direct/processing+custom/processing=5/166/39/90；modality mixed/raster/unknown/vector=125/36/18/121；long/medium/short=159/98/43。
- Provider preflight：228 个 operator 可映射到冻结 114；292/300 有 bounded candidates，8 条无候选并 fail closed。
- OpenAI SDK `2.45.0` 已安装；本机 41 项相关回归、服务器 21 项 aggregation tests 通过。
- 本机同步 300 条审查 CSV、pilot summary、ledger、validation summary、live smoke status；51.7MB pool 和 3.34MB full pilot JSONL 只留服务器。

### 当前阻塞 / 下一步
- 服务器 `GGUUAI_API_KEY` 未设置，live request=0；状态见 `docs/reports/qgis_pilot/phase3_api_aggregation/live_smoke_status.json`。
- 外部设置环境变量后先运行 `--max-records 1` compatibility smoke；strict JSON、evidence references、hash 和无 reasoning 落盘全部通过后，才允许 proposal batch。
- Proposal batch 后进入 300 条人工审核。当前 pilot 是 coverage diagnostic，不是 accuracy reference，也不是训练数据。
