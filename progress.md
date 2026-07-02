# 进度日志

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
- deepseek-chat 临时 key: sk-89eb3f39563c470180aedeb6da3db5c1（批量生产用）
- 服务器端代码通过 env var DEEPSEEK_API_KEY 读取，不落盘

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
