# 任务计划：QGIS 工作流推荐系统 — 评测体系 + 矢量修复

## 目标
建立系统无关的多指标 QGIS 链评测体系（①②③），用 V4.6 模型实测并定位"矢量能力缺失"的根因，通过数据扩充+词汇扩展+模型重训，持续提升矢量规划能力。

## QGIS Planner Benchmark v0.1 独立工作流（2026-07-31）

## QGIS Planner Benchmark v0.2 roster-first 规划（2026-09-10）

本 agent 的唯一职责仍是构建正式 QGIS planner benchmark，当前目标是冻结 v0.2 supported family roster 与约 120 条 final 的结构预算；不负责 GEE、QGIS 训练数据或模型训练。

- [x] v0.1 保持 immutable；v0.1 errata、hash-bound artifacts 与 sealed gold 不重生成。
- [x] 确认 v0.2 采用 roster-first：先 stable101 四态分类，再冻结 quota，再做 candidate supply repair。
- [x] 复核既有 roster freeze 记录；R1-R5 gate、预算原则和禁止事项以现有 benchmark authority 与本段计划为准。
- [x] R1：stable101 四态 roster 已冻结；权威文件为 `benchmarks/qgis_planner_v1/authority/v02_supported_family_roster.json` 及同名 `.md`，提交 `f186d31`，20 supported / 8 deferred / 22 out_of_scope。
- [x] R2：已冻结 `benchmarks/qgis_planner_v1/authority/v02_budget_matrix.json` 与同名 `.md`；development 40 / 36 canonical DAG，final 120 / 60 canonical DAG，含 family tier envelope 与 P0 结构 floors。
- [x] R3：149 条既有 source-backed/expert candidate 已逐条生成 v0.2 intake ledger；87 条符合 20-family roster，62 条因 family 不在 roster 排除；Gate 1、Gate 2、parameter-free 和结构检查结果已绑定。
- [x] R3 review envelope：31 个 eligible DAG 生成 38 个 hash-bound review jobs；linear 主审 31，merge 二审 7，queue SHA 固定。
- [ ] R4：完成独立 graph review、merge/branch 双 reviewer 与人工批准，累计可评测 task+gold。
- [ ] R5：生成 v0.2 manifest、sealed gold、review/leakage ledger、scorer 与 checksums。

当前 v0.2 可交付 task+gold 计数仍为 `0`；脚本、schema、review job、candidate 数量均不计进度。R3 已完成入场准备，下一步是 R4 独立 graph review；模型 prediction 必须等 v0.2 freeze 且 inference config 冻结后才开始。

本工作流只负责构建评测集，不负责 GEE 数据、QGIS 训练数据或模型训练。
阶段验收只统计已形成模型可见 `task_text` 且有一一对应 parameter-free
`processes + links` gold 的可评测记录数；脚本、schema、候选 DAG、review job
和门禁数量均不计为评测数据交付。

- [x] 首批 8 个 graph authority 已选定，全部避免未完成双审的 merge DAG。
- [x] 首批 development pilot：8 条 task + 8 条 gold 完成独立语义复核并可直接评分。
- [x] development set：40 条 task + 40 条 gold 已完成独立 task-to-gold 语义复核，可直接评分。
- [x] sealed final：120 条 task + 120 条 gold 完成主审、30 条盲二审和 development 隔离检查。
- [x] refusal diagnostic：12 条完成主审和盲二审，单独计数，不混入 operator+links 主任务。
- [x] v0.1 Freeze：版本、24 项 artifact manifest、27 项 checksum ledger 与统一 graph/refusal scorer 已冻结并通过 synthetic verification。

当前 development set 已达到 `40/40 reviewed_usable`，sealed final 已达到
`120/120 sealed_reviewed_usable`，refusal diagnostic 已达到 `12/12
sealed_reviewed_usable`。正式 v0.1 Freeze 包已完成；下一阶段仅允许 prediction
lock 与 evaluation handoff，任何 gold 修订必须升级 benchmark 版本。

## 当前阶段
**2026-07-14 — 停止继续复制/上采样无自然语言语义的激活数据，按已批准的 evidence-first 计划重构约 300 条 QGIS 真实数据 pilot。当前只授权推进到 Phase 4 人工确认门禁，不训练、不扩量、不切换默认词表。**

## 2026-07-14：真实 QGIS 数据 Pilot 批准计划

正式计划：`.omx/plans/full-107-qgis-pilot.md`（本机 `.omx/` 当前被 Git 忽略，关键结论同时维护在本文件、`progress.md` 和中英文 `PROJECT_CONTEXT`）。

### 已确认目标

- 当前 107 类只是实验 taxonomy 起点，最终类别数可根据真实证据增删、合并或调整。
- 最终目标是用证据充分的新 taxonomy 替换 94 默认系统，但在迁移前必须保留并验证 94/GEE 稳定基线。
- 现有 GEE 标签不全量重构，只修复空文本、重复和冲突，并作为 replay 与 held-out 回归 authority。
- 任何未来模型的核心 GEE held-out 指标相对稳定基线最多允许下降 5%；理想目标是不下降。
- QGIS/facts 数据必须从有序代码证据重建完整链，不能只提取新增码，也不能使用无序 set 或纯描述强猜。

### Pilot 范围与门禁

- [ ] Phase 0：authority 差异报告已生成；用户决定暂缓旧 94 备份，不再阻塞 QGIS 数据重建主线。
- [x] Phase 1：完成 `/home/yll` 只读 inventory，索引 facts、AST/steps 和补充描述来源，所有产物写入 `/home/qy`。
- [ ] Phase 2：构建 path/hash provenance、碰撞处理和 T0-T4 证据等级；basename 冲突不自动选择。
- [ ] Phase 3：按 `statement_index`、scope、调用嵌套和 process relation 恢复有序 API/QGIS 操作证据。
- [ ] Phase 4：提出约 300 条、互不混合指标的 `estimation_reference_subset` 和 `coverage_diagnostic_subset`。
- [ ] **人工确认门禁：** Phase 4 后停止，等待确认两个子集的具体数量、审核人数、裁决人和分歧处理规则。
- [ ] Phase 5/6 仅在门禁批准后执行 DeepSeek 单条 smoke 和 pilot batch；扩量、训练和 taxonomy 修改仍需再次批准。

### 硬性安全边界

- `/home/yll` 只读，禁止创建、修改、删除文件；所有写操作限定在 `/home/qy` 和本机仓库工作区。
- 禁止删除服务器任何数据。
- 临时 DeepSeek key 仅通过 `DEEPSEEK_API_KEY` 进程环境变量传递，不写入代码、日志、报告或 Git；pilot 后必须轮换/撤销。
- 只持久化 `brief_rationale`，禁止保存 `reasoning_content`、思维链、provider thinking trace 或原始 prompt/completion dump。
- 只有人工审核后的 T4 样本可以进入准确率分母；estimation、coverage、collision diagnostic 指标禁止合并。
- Pilot 结束后的扩量仍需明确批准数值质量阈值和允许进入语料/SFT 的 provenance/label 等级。

### 本机同步协议

- 服务器上新增或修改的关键脚本、配置、schema、prompt、测试和报告生成代码，必须在阶段收口前同步回本机仓库；不得只留服务器临时版本。
- taxonomy、ID 映射、stable authority、数据门禁、抽样策略、审核协议、质量阈值、训练准入和生产切换等关键决策，必须同步更新本机 `task_plan.md`、`progress.md`、`docs/PROJECT_CONTEXT.md` 和 `docs/PROJECT_CONTEXT.zh-CN.md`。
- 每个 Phase 完成后更新：完成项、实际产物路径、输入/输出 hash、验证命令、失败项、阻塞和下一门禁。
- 大型数据不直接同步到 Git；同步 manifest、schema、统计报告、可复现脚本和小型审核样本。服务器正式产物必须有本机可追溯路径记录。
- 禁止在任何本机同步文件中写入服务器密码或 API key。

### Phase 0 执行门禁（2026-07-14）

- 报告确认存在三套不一致口径：`vocab_profile_v2_94_stable`、`step8_v4_6_run_contract`、`quality_gate_v4_6_entrypoints`。
- `step8_v4_6_run_contract` 在服务器缺少默认 Transformer 和 Set Predictor checkpoint，不能直接作为可恢复 authority。
- vec11277 profile 资产完整，但不是当前主要训练/评测入口；quality-gate V4.6 入口资产完整。
- 修正版报告新增 `phase11_vector_sft_94`：将 oversampled 数据包、epoch 4 `best_gen_composite_model.pth`、训练/评测日志绑定为一套可复现实验口径；其公开评测关闭 Set Predictor。
- 现有 quality-gate evaluation JSON 只是 500 条 smoke，指标全 0，且配置 checkpoint 与实际 inference checkpoint 冲突，不能作为 GEE 基线 authority。
- 当前状态：`authority_decision_required`。未 hash/copy 大 checkpoint，未运行 restore smoke，未进入 Phase 1。
- 服务器报告：`/home/qy/system_redesign/outputs_v2/qgis_pilot/pilot_v1/phase0/authority_decision_report.{json,md}`。
- 本机镜像：`docs/reports/qgis_pilot/phase0/authority_decision_report.{json,md}`。

### QGIS 数据重建主线（2026-07-14 调整）

- Stage 1：从 merged process、AST、steps 和 relations 恢复有序 QGIS processing、底层 API 与 custom algorithm 证据，并绑定真实任务描述。
- Stage 2：将完整有序操作链映射到实验性 107 taxonomy；先生成可审核 crosswalk，不使用旧的宽泛字符串猜测。
- Phase 1 inventory 已完成：20,413/20,428 facts 匹配 artifact；1,887 条多目录碰撞必须 path/hash 消歧。
- 可补充描述来源：2,009 plugin metadata、2,054 README、851 model/tutorial metadata、2 个精评 CSV，以及可进一步抽 docstring 的 48,011 个源码文件。
- 当前 107 id mapping 的 464 条 `qgis_to_l3` 映射没有任何一条指向新增 13 类，必须重建 107 专属 QGIS crosswalk。
- Taxonomy 证据扫描确认当前 13 个新增 code 复用了 legacy 350 中不同语义的 code，禁止直接冻结当前 107。
- 工作草案改为 112-114 类，默认建议 113 类；待确认 Spatial Index、Concave Hull、Rasterize/Polygonize 三项边界后分配无冲突 ID。

## 📊 全面状态总览 (2026-07-08)

### 训练数据演进

| 版本 | 样本数 | 矢量占比 | 词表 | L3 码数 |
|------|--------|---------|------|---------|
| v1 (基线) | 84,078 | 10.9% | 94 | 17 vector |
| v2 (vec11277) | 95,355 | 21.4% | 94 | 17 vector |
| **v3 (vocab107)** | **113,466** | **34.0%** | **107** | **30 vector** |

### 模型演进

| 版本 | 词表 | 训练模式 | Best Composite | Best SetF1 | epoch |
|------|------|---------|---------------|------------|-------|
| ScratchGentle | 94 | from-scratch | 0.537 | 0.505 | 42 |
| vec11277 warmstart | 94 | warmstart | **0.599** | 0.563 | 23 |
| vocab107 scratch | 107 | from-scratch | 0.564 | 0.513 | 31 |

### open_landing 评测对比 (80题)

| 版本 | vec usable | vec complete | vec→vec L3% | vec→rast L3% | rast usable |
|------|-----------|-------------|-------------|-------------|-------------|
| V4.6 原始 | 35% | - | ~0% | ~98% | - |
| gentle_typed | 78% | 75% | 56% | 30% | 96% |
| vec11277 fp05fix | **95%** | 95% | 55% | 30% | 96% |
| **vocab107 scratch** | **98%** | **100%** | **84%** | **3%** | 96% |

关键发现：
- vocab107 模型对矢量任务几乎不再输出栅格码（3% vs 之前 30%）
- 矢量完整性和可用性创历史最佳
- **但 13 个新 L3 码 0 个被模型使用**（罕见 token 淹没）

### 当前阻塞
- [ ] 新 L3 码未被模型使用 — 需要稀有 token 上采样或微调
- [ ] Set Predictor 仍基于 94 词表，需同步更新
- [ ] QGIS landing 语料 native: 主导，未优化

### 🔑 金标标注发现 (2026-07-03)
- [x] 40 道矢量 open_landing 题目人工标注金标 L3 链
- [x] **50% (20/40) 任务在现有 17 个矢量 L3 码中无对应码** — 词汇缺口是首要问题
- [x] 可评分 20 题：Grade A=0%, B=35%, C=50%, D=15%
- [x] **SetF1=0.399**（可评分任务）— 低于 Phase B 的 0.531
- [x] 标注表: `outputs_v2/diagnostics/quality_gate/vector_gold_annotated.csv`

### L3 词汇缺口清单（20 个任务无 L3 码）
| 缺失操作 | 影响任务 |
|---------|---------|
| Reproject | 11, 33 |
| Simplify | 13 |
| Fix Geometries | 12 |
| Voronoi / Delaunay / Thiessen | 15, 27, 28 |
| Grid Generation | 14 |
| Concave Hull | 26 |
| Heatmap / Density | 16 |
| Nearest Facility (Network) | 17 |
| Smooth | 25 |
| Delete Holes | 24 |
| Snap | 35 |
| Delete Duplicate | 36 |
| Polygon→Polyline | 21 |
| Singlepart→Multipart | 38 |
| Extract Vertices | 39 |
| Export | 32 |
| Table Join (attribute) | 37 |
| Update/Add Field | 31 |

### 已完成工作 (2026-07-02—03)
- [x] FP05 修复: 数据源自动注入，矢量完整性 80%→95%
- [x] 端到端质量门控: `quality_gate.py` — L3→QGIS→Workflow 3 阶段检查
- [x] 意图识别集成: `task_type_classifier.py` + `auto_classify` 参数
- [x] `.env` 配置系统: 统一管理 API key/服务器/路径
- [x] L3 链 6 维质量诊断: `diagnose_l3_quality.py`

## 当前阶段
**2026-07-02 — 矢量质量评估：从"能生成"到"生成得对"。L3链多维度质量评测 + 意图识别集成 + 端到端质量门控。**

### 新阶段目标
1. **L3链质量多维度评估**：不只统计 usable/executable，要建立 correctness、完整性、效率等多轴指标
2. **意图识别集成**：task_type 分类从外挂脚本→推理管线前置步骤，解决用户 NL 任务→模型推理的模态信号缺失
3. **端到端质量门控**：L3 输出→可用性检查→QGIS landing→workflow JSON，全程质量可追踪

### L3 链质量评估维度（待设计）
- ① 可用性（rule-usable）：现有，L3 序列满足 I/O 约束
- ② 可执行性（executable）：现有，能 land 到 QGIS 算子
- ③ 正确性（correctness）：现有 SetF1 vs 金标，需扩充矢量金标
- 🆕 ④ 完整性（completeness）：是否缺少关键步骤（missing_critical_steps）
- 🆕 ⑤ 简洁性（conciseness）：是否有多余/冗余步骤
- 🆕 ⑥ 模态一致性（modality consistency）：矢量任务生成矢量链，栅格任务生成栅格链

### 意图识别（task_type classification）
- [ ] 集成进推理管线：`NL query → classify_task_type() → infer_l3(task_type=X) → beam → QGIS`
- [ ] 不依赖 LLM API 的可选方案：训练轻量文本分类器（fastText/BERT-small）
- [ ] 评估分类准确率对下游 L3 质量的影响

## 已完成（截至 2026-07-02）
**2026-06-30—07-02 — 矢量样本合并 + L3/Set Predictor 重训 + 两步评测。**

### 🔑 关键突破：task_type 分类修复矢量 L3 输出 (2026-06-30)
- [x] `scripts/classify_task_type.py`：LLM (deepseek-chat) 对 80 open_landing 任务分类→48 task types
- [x] 分类后跑 L3 推理 + QGIS landing → `open_landing_gentle_typed/` 评测
- [x] **矢量 L3 token 占比从 ~0%（Phase A）→ 26.5%（无 task_type）→ 55.8%（有 task_type）**
- [x] 模型不再把矢量任务塌成栅格码 —— **task_type 条件化是正确路径**
- [x] vec L3 usable: 31/40 (78%), rast: 24/25 (96%), mixed: 14/15 (93%)
- [ ] 仍有 `missing_critical_steps` 警告，链质量待提升

### 大规模矢量样本挖掘 (2026-06-25—30)
- [x] `scripts/mine_vector_samples.py`：398K+ QGIS .py 脚本池全量扫描
- [x] **45,000+ 脚本含 processing.run() 调用，31,838 个矢量脚本**
- [x] QGIS alg_id → L3 语义映射 + OP_PATCH 手动补丁表
- [x] **产出 11,277 条精选矢量训练样本**（17/17 矢量 L3 码全覆盖）
- [x] 每码上限 2,000 截断，偏少码全保留
- [x] 输出：`outputs_v2/targeted_vector_mining_v2/vector_py_samples_selected.jsonl`
- [ ] **尚未合并进训练包**：合并后矢量占比 10.9%→21.4%

### 11,277 矢量样本明细
| 状态 | 数量 | 码 |
|------|------|-----|
| ✅ 截断(2000) | 3 | Buffer(4,667), Clip(5,040), Intersect(2,798) |
| ✅ 充足(1000-2000) | 4 | Erase(2,081), Feature to Point(2,075), Multipart(2,476), Union(1,335) |
| ✅ 达标(300-1000) | 6 | Select by Attribute(1,154), Extract by Location(609), Min Bounding(491), Spatial Join(450), Split Line(409), Sym Diff(309) |
| ⚠️ 偏少(<300) | 4 | Filter Geometry(276), Collect(211), Extract by Attr(164), Update(74) |

### V4.6 ScratchGentle 从零训练 (2026-06-27—28)
- [x] 50 epoch from-scratch，使用含 gap 修复的 84,078 训练包
- [x] 训练完成 0 错误，checkpoint: `outputs_v2/transformer_checkpoints_v4_6_scratch_gentle/`
- [x] 指标：best set_f1=0.5367 @ep42, best lcs=0.3858, val_loss 3.37→2.94
- [x] val_top1_acc=0.2865, val_top5_acc=0.6766, val_top10_acc=0.7969
- [x] rep_rate 0.863→0.433 (改善), early_eos 0.188→0.117 (改善)
- [ ] 与 Phase6 VectorFix (set_f1=0.5796) 对比，泛化指标略低，但 val_loss 更低(2.94 vs 3.28)

### 训练历程总对比 (截至 2026-06-30)
| 训练 | Ep | Best set_f1 | Best lcs | val_loss final | 数据量 |
|------|-----|------------|----------|---------------|--------|
| Phase6-VectorFix warmstart | 50 | **0.5796** | 0.4341 | 3.2766 | 77,981 |
| GapFix-12ep smoke | 12 | 0.4534 | 0.3315 | 3.0191 | 84,078 |
| ScratchGentle from-scratch | 50 | 0.5367 | 0.3858 | **2.9385** | 84,078 |

### L3 模型重训 (2026-07-01) ✅
- [x] 11,277 矢量样本合并进训练包：84,078→**95,355** (矢量 10.9%→21.4%)
- [x] 30 epoch warmstart (ScratchGentle)，A10 GPU，~24h
- [x] 最佳 epoch 23: Composite=**0.5990** (+11.6%), SetF1=**0.563**, LCS=**0.413**
- [x] TokenAcc 16.1%→19.2%, train_loss 1.50→0.97
- [x] checkpoint: `outputs_v2/transformer_checkpoints_v4_6_vec11277_warmstart/best_model.pth`

### Set Predictor V3 重训 (2026-07-01) ✅
- [x] 同训练包，30 epoch，~3h
- [x] 最佳 epoch 19: F1@0.70=**0.675**, top10R=**0.892**, over% 80%→43%
- [x] checkpoint: `outputs_v2/set_predictor_checkpoints_v3_vec11277/best_model.pth`

### 两步评测 (2026-07-02) ✅
- [x] **open_landing 80 题**：vec usable 78%→**88%** (+10pp), mixed 93%→**100%**
- [x] **held-out 104 题 (③ correctness)**：overall SetF1=0.518（仅 2 矢量样本，参考价值有限）
- [x] 矢量 L3 token 占比稳定在 55.3%

### 关键发现
- **生成能力已修复**（vec usable 88%），下一步重点是**链质量**
- 评测中有大量 `missing_critical_steps` 警告——模型输出不够完整
- QGIS landing 语料仍偏栅格（native_bridge 占 78% 在 held-out 中）
- task_type 分类是关键杠杆，但还作为外挂脚本，未集成进推理管线

### 缺口分析 + 定向挖掘成果 (2026-06-25)
- [x] `scripts/analyze_l3_coverage_gaps.py`：94 L3 码 × 训练数据 × 语义映射 → 排序风险矩阵
- [x] **发现 47/94 (50%) L3 码零训练样本**，其中 12 个矢量码全部有 QGIS 算子可挖
- [x] `scripts/targeted_vector_mining.py`：搜索 52k QGIS 脚本池 → 6,336 匹配 → LLM 定向生成
- [x] **产出 1,009 条高质量训练样本**（平均置信度 0.836），12 个矢量 DATA_GAP 码全部覆盖
- [x] 矢量 L3_02 码从 5/17 覆盖 → **17/17 全覆盖**

## 历史阶段
**2026-06-24 — 训练入口高优先级修复 + API-trace 数据门禁已验证。**

全面静态审查发现 20 个问题（12 个高优先级 + 8 个中优先级）。核心结论：

1. **训练数据混用问题严重**：vector_v2/API_trace_to_L3_TRAINING_FINAL 含弱 prompt、LLM 标签噪声、val/test 污染、同 prompt 多 label 冲突。
2. **训练入口参数不一致**：`_push_and_train.py` 的 `--workflows`/`--epochs` 与 `train_v4_6_quality_gate.py` 的 `--data`/`--num-epochs` 不匹配。
3. **from-scratch 短 epoch 全 TF**：传 `--num-epochs 5` 没有 `--warmstart` 时，5 个 epoch 全是 Teacher Forcing 无 AR-SS。
4. **推荐主线**：使用 `step8_quality_gate_qgis_vector_oversampled` 包（train-only QGIS 注入、干净 split）。

已修复并本地验证的高优先级项：
- [x] `train_v4_6_quality_gate.py`：修复语法错误；`--length-stats` 默认改为可检测的 None；from-scratch TF-only 短训默认退出，只有显式 `--allow-tf-only-smoke` 才允许继续。
- [x] `_push_and_train.py`：默认直接退出，不再执行 SSH/SFTP/远程训练；如复现旧行为必须显式 `--force-deprecated`；移除自动 pkill 风险。
- [x] `train_v4_6_vector_unified.py`：修正 docstring；不再错误归因 val/test 污染；缺少 `task_type_length_stats_vector_unified.json` 时默认退出，要求显式 stats 或改用 oversampled 主线。
- [x] `_upsample_splits.py`：默认直接退出，不再生成 duplicate-index split；如复现旧输出必须显式 `--force-deprecated`。
- [x] `clean_api_trace_l3_training_data.py`：新增 API-trace 训练数据门禁，把 raw 6,031 行切成 clean/weak/rejected/conflicts；拒绝 placeholder prompt、同 prompt 多 label、task/code 错配、task/L3 模态错配、低/缺失置信度和“只靠描述强猜”的样本。
- [x] `server_batch_api_to_l3.py` / `server_batch_source_to_l3.py` / `llm_generate_l3_from_api_traces.py`：prompt 改为无证据时拒绝/空链，不再鼓励猜测；置信度门槛收紧，missing/invalid confidence 直接拒绝。

训练机制改造已完成（用于真正提升矢量规划能力，而非只提升 QGIS landing）：
- [x] `TaskConditionedL3DatasetV4` 返回 `_training_quality.sample_weight`；TF 和 AR scheduled-sampling loss 都改为 per-sample weighted CE。
- [x] 训练 prompt 统一为结构化 `Task type / Task name / Goal`，训练入口默认 `--max-text-length 256` 并在 dry-run 报告截断风险。
- [x] sampler 支持 task type、vector operation family、source quality、confidence、sample weight 组合加权，重点补 intersection/union/difference/geometry_repair/CRS 等目标族。
- [x] 非默认 mixed/vector 包必须使用同目录或显式 `--length-stats`，避免误用旧 quality-gate 长度先验。
- [x] `qgis_unmappable_penalty > 0` 被禁止，避免按错误方向强化 unmappable target。
- [x] `--ar-max-steps` 可配置，避免复杂矢量长链后半段完全没有 AR scheduled-sampling 训练信号。
- [x] 推理/评估增加 `legacy|structured` prompt style；旧 DPO/SFT 默认保持 legacy，新结构化 prompt 模型评估时显式传 structured。
- [x] QG parent inferencer 保持 legacy 128-token prompt，避免主线 checkpoint 输入分布被意外改变。

验证：
- `python -m py_compile scripts\train_v4_6_quality_gate.py scripts\train_v4_6_vector_unified.py scripts\_push_and_train.py scripts\_upsample_splits.py` 通过。
- `python scripts\train_v4_6_quality_gate.py --dry-run --num-epochs 5` 会阻止 TF-only from-scratch 误跑。
- 加 `--allow-tf-only-smoke` 后可执行显式 TF-only dry-run。
- oversampled 主线包 dry-run 通过：81,137 workflows，train/val/test=65,748/7,694/7,695，48 task types，tf_phase_epochs=0。
- `python -m unittest tests.test_api_trace_l3_training_cleaning -v` -> 21 tests OK。
- `python -m unittest tests.test_v4_6_vector_training_mechanisms tests.test_v4_6_training_readiness tests.test_v4_6_training_stability tests.test_v4_training_entry_smoke -v` -> 26 tests OK。
- `python -m unittest tests.test_v4_qg_planner tests.test_runtime_consistency tests.test_v4_6_vector_training_mechanisms -v` -> 21 tests OK。
- `python -m py_compile src\gis_recommend\training\loss_utils.py src\gis_recommend\training\train_v4_2.py src\gis_recommend\training\train_v4_5.py src\gis_recommend\training\train_v4_6.py src\gis_recommend\inference\infer_l3_candidates_v4.py src\gis_recommend\inference\infer_l3_candidates_v4_qg.py scripts\train_v4_6_quality_gate.py scripts\train_v4_6_vector_unified.py scripts\evaluate_vector_generalization.py scripts\evaluate_sft_vector_impact.py` -> OK。
- oversampled warmstart dry-run（显式 vocab/stats + `--enable-family-sampler` + `--max-text-length 256`）通过：65,748 train rows，prompt max 189/p99 128，无 prompt 截断；sequence max 64/p99 31，无 max_seq=100 截断；`tf_phase_epochs=0`；family sampler 覆盖 intersection 1,038、union 785、difference 688、geometry_repair 1,580、crs_transform 11,567。
- oversampled warmstart dry-run 加 `--ar-max-steps 32` 通过：超过 AR horizon 的 train sequences 从默认 3,219 降到 545。
- `python -m py_compile scripts\clean_api_trace_l3_training_data.py scripts\server_batch_api_to_l3.py scripts\server_batch_source_to_l3.py scripts\llm_generate_l3_from_api_traces.py` -> OK。
- `python scripts\clean_api_trace_l3_training_data.py --input outputs_v2\API_trace_to_L3_TRAINING_FINAL.jsonl --out-dir outputs_v2\diagnostics\api_trace_l3_cleaning` -> clean=1,112 / weak=1,384 / rejected=3,535 / conflicts=1,367。

当前未完成：
- [ ] 尚未跑新的 GPU 全量训练；不能声称矢量规划能力已经提升。
- [ ] clean API-trace rows 还未封装成 train-only Step8 兼容包；下一步应只从 CLEAN 或人工审核后的 weak 构建包。
- [ ] `vector_v2` val/test 污染问题仍不应作为最终指标来源；继续使用 held-out 手写 vector prompts / family recall 评估。
- [ ] `--ar-max-steps 32` 已可用但未训练验证；长链完整性仍需在服务器结果里单独看。

## 各阶段

### 阶段 1：T3 评测体系架构 ✅
- [x] `score_qgis_chain` (①②③) 纯函数、依赖注入、无 Neo4j
- [x] `qgis_operator_registry` (alg-id keyed, 1291 算子)
- [x] `aggregate_by` / `open_landing_report` / `score_open_landing` CLI
- [x] **21 测试绿**，已合并 main（`dd3f1a6`）
- [x] 检索基线 80 题实测 → **关键发现：可执行 ≠ 正确**（C 档有效率 > A 档）
- **状态：** complete

### 阶段 2：V4.6 模型实测（Phase A + B）✅
- [x] Phase A：V4.6 text-only 80 题 → 对比检索基线（按模态）
- [x] **发现：模型把矢量任务塌成栅格 L3**（vec executable 0.875→0.350，unique_ratio 0.525→0.200）
- [x] Phase B：150 题 held-out（真实 task_type + 金标 L3）→ **首个 correctness 数 L3 set_f1=0.531**
- [x] 证实 ② 和 ③ 解耦（executable≠correct）
- [x] 25 测试绿，已合并 main（`78ae715`）
- **状态：** complete

### 阶段 3：根因诊断 — 语料模态偏斜 ✅
- [x] `analyze_corpus_modality.py`：训练语料 **99.3% 栅格 / 0.2% 矢量**
- [x] task_type 词表 = 47 个主题类，**无模态轴、无矢量为主的主题**
- [x] 结论：**矢量是数据缺口，不是推理能修的**
- **状态：** complete

### 阶段 4：建矢量训练集 ✅
- [x] 服务器数据审计（`docs/server_data_inventory.md`）
- [x] 从 yll 的 QGIS 抽取池挖链（~4,097 raw → 2,175 去重）
- [x] `facts_summary1000` 真实描述 join → **2,733 完整样本(链+描述+类型)**
- [x] ①+② 归一化 + crosswalk 扩充（101→186 l3_bridge）
- [x] **v2 矢量训练集：1,097 条（描述→L3），954 矢量相关**，≈ 本地 323 的 3x
- [x] LLM 全局切换 deepseek-v4-pro（含移除 3 处明文旧 key）
- [x] 28 测试绿，已合并 main
- **状态：** complete

### 阶段 5：交互式 Demo ✅
- [x] workflow JSON 格式（参数 description 无 value + links）
- [x] `workflow_json_builder`（TDD, 3 测试）+ `build_workflow_jsons.py`
- [x] `demo_interactive_workflow_qa.py`（NL 输入→JSON 链→deepseek 对话式 QA）
- [x] 实测验证：追问参数+数据流，LLM 基于 workflow context 回答
- **状态：** complete

### 阶段 6：重训（矢量修复 v1）✅
- [x] 合并 1,097 矢量样本进 labeled_workflows（77,981 total）
- [x] 重平衡通过 `compute_token_freq_weights`（L3_02 罕见码高 CE 权重）
- [x] 推代码+数据到服务器（qy@10.191.2.38，A10 GPU，conda env transformer）
- [x] 干训冒烟通过（cuda:0，数据加载 OK）
- [x] 全量训练完成（50 epoch，composite=0.5972 best@epoch 41，0 错误）
- [x] 三向对比评测完成：vec executable 0.35→**0.40**(+0.05), unique_ratio 0.20→0.25, io_exec 0.787→0.812
- [x] **核心发现：L3 层没变** — vecfix 对 40 个矢量任务，0/40 是矢量主导 L3，98% 仍是栅格码
- [x] **1,097 条矢量在 76,341 条栅格中被绝对淹没。freq_weights 不足够。需要 50x+ 上采样 + 大幅扩数据。**
- **状态：** complete（git: `d0d4468`）

### 阶段 7：大幅扩矢量 + 激进上采样 + ③ 真·L3 缺口补全 ✅ (已合并进阶段9)
- [ ] ③ 真·L3 词表缺口补全（~7 个核心矢量原语：Simplify/Heatmap/SplitLines/DeleteHoles 等→94→~101）
- [ ] 放宽严格映射（含不可映算子则保留其余，不整链丢弃）→ mapped_rate 40%→~70%，得 ~1,500+
- [ ] 合并本地 323 + v2 1,097 → 统一矢量训练集
- [ ] 上采样 50x+（矢量占训练步 ~50%+，改 merge&train 配置）
- [ ] 服务器重训 V4.6-base（epoch 匹配、early stop）
- [ ] harness 重评矢量（Phase A 40 题 + 可能选有金标 L3 的链做 ③）
- **状态：** in_progress

### 阶段 7：后续（待定）
- [ ] 若重训有效 → 扩大量（放宽映射 / 扩 crosswalk ③ 真·L3 缺口 / 抽 data-QGIS 53k）
- [ ] GPT-4o 横评（等矢量能力补齐后）
- [ ] 服务器环境长期化（配 SSH key 免密 / 训练常态化）

### 阶段 9：C++ API 痕迹→LLM→L3 规模化 🔄
- [x] POC 10 脚本验证（6/10→7/10，后缀粘连已修复）
- [x] 建 `llm_generate_l3_from_api_traces.py`（提取+LLM+质量门控）
- [x] 码表 25→40 扩充：15 新码激活，40/40 全覆盖
- [x] 2k 批次：804 条，产率 62%，conf 0.71
- [x] 3k 批次：1,011 条，产率 57%，conf 0.70
- [x] 5k v1：1,689 条，产率 47%
- [x] 5k v2（修复版）：1,603 条，产率 45%，加渲染过滤+自否修复
- [x] 10k 批次：3,200 条，产率 42%，回填描述 97%
- [x] 建 `server_batch_api_to_l3.py`（checkpoint 恢复 + facts join）
- [x] 建 `backfill_descriptions.py`（已生成样本回填描述，97%覆盖）
- [x] 发现并修复 0.60 统一地板 bug（曾误杀 80% LLM 输出）
- [x] 人工审计 90 条：高/中层 100%，低层 0 错误，0 LLM 自否
- [x] 发现 yll 完整 20k QGIS facts_summary（非本地 2,260 子集）
- [x] 全量 v3：5,594 条，产率 25%
- [x] 路线 4 源码→L3：4,605 条，产率 67%
- [x] 人工审计 90 条：高/中层 100%，修复后 0 错误
- [x] 全量合并：16,800 条训练数据（94% 有真实描述）
- [x] API-trace 数据门禁：6,031 raw -> 1,112 clean / 1,384 weak / 3,535 rejected / 1,367 conflicts
- [ ] Phase 10 重训：3 次尝试（scratch/warmstart×2）均因栅格稀释失败
- [ ] 待决：缩小训练集至 Phase 8 配方（排除 67k 纯栅格）

### 阶段 12：task_type 分类修复 L3 输出 ✅ (2026-06-30)
- [x] 发现模型推理时 task_type="Unknown" 导致无法利用 task_type embedding 条件化
- [x] `scripts/classify_task_type.py`：LLM 分类 80 open_landing→48 task types
- [x] 评测：**矢量 L3 token 占比 ~0%→55.8%**，任务不再塌成栅格码
- [x] 验证 task_type 条件化是关键杠杆（非更多数据）
- **状态：** complete

### 阶段 11：大规模 PY 脚本矢量挖掘 ✅ (2026-06-25—30)
- [x] 398K+ QGIS .py 脚本全量扫描 → 45K+ 含 processing.run()
- [x] QGIS alg_id → L3 语义映射 + OP_PATCH 补丁 → 识别矢量操作
- [x] **11,277 条精选训练样本**，17/17 矢量码全覆盖
- [x] Per-code 上限截断 + 偏少码全保留策略
- [x] 矢量占比预估 10.9%→21.4%（合并后）
- [ ] **未合并进训练包、未重训验证**
- **状态：** data_ready（待合并重训）

### 阶段 10：V4.6 矢量规划训练机制修复 🔄
- [x] 训练入口守卫：from-scratch 小 epoch 默认阻断 TF-only 误读，显式 `--allow-tf-only-smoke` 才允许 smoke。
- [x] length stats 守卫：非默认 mixed/vector 包必须使用同目录或显式 `--length-stats`，不再静默复用旧 quality-gate stats。
- [x] 数据门禁：API-trace raw 6,031 -> clean 1,112 / weak 1,384 / rejected 3,535 / conflicts 1,367；低置信和 placeholder 不再等权进入 SFT。
- [x] 训练机制：sample_weight 进入 TF/AR loss；prompt 结构化；family/source-aware sampler 可启用；AR max steps 可配置；unsafe `qgis_unmappable_penalty>0` 禁用。
- [x] 评估门禁：`eval_source_guard` 默认拒绝 val/test 中的 generated/LLM/API-trace source，旧污染包只能显式 `--allow-generated-eval-sources` 诊断复现。
- [x] 兼容性：推理/eval 支持 `legacy|structured` prompt；旧 DPO/QG checkpoint 默认 legacy，避免破坏基线。
- [x] 本地验证：64 条相关 unittest OK；关键训练/清洗/推理/评估文件 py_compile OK；真实 oversampled warmstart dry-run OK，eval generated rows=0。
- [ ] 服务器训练：用 oversampled 主线包 + warmstart checkpoint + `--enable-family-sampler --max-text-length 256 --ar-max-steps 32` 跑 GPU SFT。
- [ ] 训练后评估：held-out vector-family recall、raster contamination、QGIS seed absorption、人工 A/B/C。只有这些指标改善后，才能声明矢量规划能力提升。
- **状态：** mechanism_fixed_local_verified；capability_not_yet_proven

## 已做关键决策
| 决策 | 理由 |
|------|------|
| 评测多指标（①②+③④）而非单维度 | 数据证明 executable≠correct，横评必须多轴 |
| ③ correctness 走 L3 级 set_f1 | 平台无关、order-invariant，金标 L3 必有 |
| 矢量修复走重训（非推理 trick） | 语料 99.3% 栅格、无矢量 task_type 可 cue |
| crosswalk 补全走①② 不动词表 | 大多缺映射非缺原语；③ 真 gap 仅 ~7 个核心算子 |
| LLM 换 deepseek-v4-pro | 推理模型，描述质量好；max_tokens 需 ≥4000 |
| 重平衡走 WeightedRandomSampler（token freq），非重复索引 | splits 校验拒绝重复；CE loss 给罕见 L3_02 更高权重更优雅 |

## 遇到的错误
| 错误 | 情况 | 解决方案 |
|------|------|---------|
| exec 分类器 outage（~2 小时） | Bash 全部被门控 | 设 cron 自动重试 + 用户 `!` 前缀绕过 |
| split 校验：train_indices 重复 | WeightedRandomSampler 不应复制索引 | 改 splits 为单次添加，靠 freq_weights 重平衡 |
| deepseek 描述生成频密空返回 | 推理模型 max_tokens=800 偏小 | 改为 4000 + reason_content 回退 + JSON 子串提取 |
| L2 池 steps.csv glob 返回 0 | 93,900 文件炸 shell argument list | 改用 `find` 命令 |
| qgis↔native 别名未归一化 | 106 个 pending + 21 native_bridge 未生效 | expand_qgis_l3_crosswalk.py 加别名 |
| paramiko ssh 超时 | 大输出时管道超时 | 后台 nohup + Monitor + cron 异步查 |

## 备注
- 服务器密码/API key 不落盘，仅本会话内联使用
- 服务器 `/home/yll/GEE` 只读 / `/home/qy/system_redesign` 为工作区
- git-workflow 使用 feat 分支、Conventional Commits、`--no-ff` 合并
- 详细发现见 `docs/server_data_inventory.md` + `memory/v46-eval-findings-2026-06.md`

## 2026-07-14：QGIS 114 类 taxonomy 冻结门禁 ✅

- [x] 否决旧 107 草案：13 个新增 code 与 legacy 350 registry 发生语义复用，禁止按 code string 直接迁移。
- [x] 冻结实验 sidecar `qgis_l3_v1_114_experimental`：保留 stable-94 的 ID `0..93`，20 个审核新增类固定为 `94..113`。
- [x] 用户确认三项边界：保留 Add Spatial Index；Concave Hull 独立；Rasterize / Polygonize 分为两个方向类。
- [x] 生成 taxonomy、invalid-107 source-profile-aware migration、49 条 QGIS alias index 和 20 类 CSV。
- [x] 完整 legacy 350 collision、alias collision、迁移闭合、父级 metadata、跨平台可复现哈希校验通过。
- [x] Delaunay 使用 legacy `L3_06_01_02`，并显式记录实验 sidecar 重新引入 stable-94 已删除的 `L1_06/L2_06_01`；不修改生产 L1/L2 vocab。
- [x] 本机与服务器三份产物 SHA256 完全一致；服务器 taxonomy 数据产物仅写入 `/home/qy/system_redesign/configs/taxonomy/`，同步代码位于同一 `/home/qy` 工作区。
- [ ] 下一步：以 114 alias/crosswalk 重建 path/hash-qualified 有序 QGIS 算子证据，随后提出约 300 条分层人工审核样本；本阶段不训练、不调用 DeepSeek、不切生产默认。

关键产物：
- `configs/taxonomy/qgis_l3_v1_114.json`
- `configs/taxonomy/qgis_l3_v1_114_migration_from_invalid_107.json`
- `configs/taxonomy/qgis_l3_v1_114_added_classes.csv`
- `scripts/build_qgis_taxonomy_v1.py`
- `tests/test_qgis_taxonomy_v1.py`

## 2026-07-14：114-aware 有序证据首轮全量扫描 ✅

- [x] 合并 expanded stable-94 crosswalk 与 49 条新增 alias，得到 325 个审计条目 / 228 条 exact L3 alias。
- [x] 显式记录 10 条旧错映射的语义重分配；未审核的不同目标仍 fail-fast。
- [x] 流式扫描 15,942,213 行，按 extraction group + script 保留路径身份和 AST/steps hash，不使用 set。
- [x] 20 个新增类全部有真实调用证据，最低 Concave Hull 12 records，最高 Reproject 599 records。
- [ ] 暂不进入 300 条抽样：21,085 records 中 complete_exact 仅 24，ordering degraded 18,507，T0 collision 4,149；先完成 direct API compact/semantic aggregation 和顺序修复。

## 2026-07-14：Direct API 语义聚合与 300 条 Coverage Pilot 🔄

- [x] 底层 API 分类和压缩：processing operator、semantic anchor、data access、infrastructure、unknown；重复调用做 run-length encoding，缺失 statement index 保持 fallback 标记。
- [x] 300 条 coverage-diagnostic 按 extraction group、证据来源模式、modality hint、trace 长度、operation family、ordering quality 分层。
- [x] 服务器最终构建：21,085 source -> 5,107 eligible -> 300 pilot；排除 T0/碰撞 4,149 条、无 processing/semantic anchor 11,829 条。
- [x] Pilot 分布：direct API 174、processing 83、processing+custom 38、custom 5；vector 108、raster 44、mixed 124、unknown 24；short/medium/long 50/93/157。
- [x] 严格 provider contract：仅允许 bounded 114 crosswalk operator；候选必须引用 evidence ID、L3 一致、confidence >= 0.70；refusal、未知字段、hidden reasoning、unsupported positive 全部 fail closed。
- [x] 离线 preflight：228 个 taxonomy-mapped operators；292/300 条有候选，8 条无候选并在 provider 调用前 reject。
- [x] 生成正式 provider preflight workbook、summary、ledger 和 8 条 zero-candidate queue；live request=0。
- [x] 服务器已安装 OpenAI SDK `2.45.0`；本机 43 项相关回归和服务器 23 项 aggregation tests 通过。
- [x] Live compatibility smoke：官方文档确认 OpenAI SDK 兼容；实测网关误封 SDK 默认 `User-Agent: OpenAI/Python 2.41.0/2.45.0`，覆盖为 pilot 专用 User-Agent 后恢复调用。
- [x] `reasoning_effort=none` 对当前渠道无效；正式请求增加 `thinking.type=disabled`，服务器返回无 reasoning 的 JSON，并通过现有 strict validator。
- [x] 最终服务器 smoke：attempted=1、validated=1、proposal=1 行；review=`pending_human_review`、training=`forbidden_until_reviewed`，无 raw/reasoning 落盘。
- [x] 24 条分层 canary 已完成：source 8/8/8、24 个 primary family、record/source 全唯一；15/24 通过 contract，8 条返回 reasoning，1 条 unknown operator。
- [x] 停止门禁已触发：contract pass=62.5% <70%，单一 reasoning failure=33.3% >30%；scaling admission=`blocked`，未处理剩余 268 条。
- [ ] 下一步不是继续调用：先解决 reasoning 路由不稳定、custom operator 缺口和 direct-API 语义链不完整，再做新的小 canary。
- [x] 独立 110 条 Core Processing signature 审核包已构建：保留 `scope + args + provider/path + parameter/output schema`；61 条唯一且 provider 一致的候选仅作 pending proposal，60 条保持 unresolved。
- [ ] 110 条审核通过后只作为 operator signature anchor；另抽普通 direct-API workflow 验证迁移效果，禁止把 110 个算子定义重复扩行为训练规模。
- [ ] 人工审核 300 条 CSV；未经人工 adjudication 不得进入 SFT。

### 2026-07-15：代码约束任务描述政策已确认

- [x] 对 path/hash-qualified 的真实脚本，若有序 QGIS 算子链和 114-L3 链通过证据校验及人工审核，但没有可靠原始任务文本，允许由 LLM 生成代码约束任务描述。
- [x] 该类记录必须标为 `silver`，不得伪装成原始人工金标；`facts_summary1000.csv` 在无法证明人工原始 provenance 时也按 code-grounded/silver 候选处理。
- [x] 描述只能表达已验证证据：不得新增、删除或重排操作，必须保留可见的 modality、输入角色、关键参数、CRS、overlay 方向和输出类型；证据不足时 reject。
- [x] `silver` 记录保留 source path/hash、evidence IDs、operator chain、L3 chain、生成器版本、审核状态和父记录 ID；按 source/script group 划分且只允许进入 train，禁止进入 val/test。
- [ ] 先在 300 条 pilot 中测量 operator/L3 proposal 和描述生成的分层准确率、拒绝率及错误类型，再决定是否扩大到 5,107 eligible 和更广的原始脚本漏斗。
- [ ] 受控同义变体数量、样本权重和 20K 训练行配额尚未批准；不得在 pilot 结果前物理复制 prompt 或构造大规模训练包。

关键产物：
- `scripts/build_qgis_api_aggregation_pilot.py`
- `scripts/run_qgis_api_aggregation_pilot.py`
- `docs/reports/qgis_pilot/phase3_api_aggregation/`
- 服务器 `/home/qy/system_redesign/outputs_v2/qgis_pilot/pilot_v1/phase3_api_aggregation/`

## 2026-07-15：Core Processing 110 条签名审核包 ✅

- [x] 使用结构化 CSV parser 读取 110 个 trace 和 1,292 条 catalog；不再按文本行或 `split(',')` 解析多行描述。
- [x] 保留 source/AST hash、imports、class bases、完整有序 structured args、参数/输出 label/type 和 provider evidence。
- [x] 候选门禁：只有 class 精确匹配且 provider 一致、过滤后唯一时生成 `auto_proposed_pending_review`；歧义/冲突/无匹配全部 fail closed。
- [x] 真实结果：110 files、117 class signatures、121 review rows；61 pending auto proposals、60 unresolved、0 accepted、0 training rows。
- [x] 未解析细分：54 no exact、1 provider-evidence ambiguity（RasterCalculator）、1 provider conflict（GDAL Buffer）、4 no class scope。
- [x] 服务器完整 15MB JSONL 保留 `/home/qy`；本机同步 579KB 审核表、歧义队列、summary、hash ledger 和初审报告。
- [ ] 人工完成全部 121 行 adjudication；自动提议不能直接成为 anchor。
- [x] 联合审核 Batch 01：10 条 GDAL 精确签名全部人工接受；独立 decision log 校验通过，剩余 111 行。
- [x] 联合审核 Batch 02：再接受 10 条 GDAL 精确签名；`contour`/`contour_polygon` 只作为独立 anchor，累计 20/121，剩余 101 行。
- [x] Review v2 修复参数方向：`merge.NODATA_OUTPUT`、`Heatmap.OUTPUT_VALUE` 从误判 output 改为 input；121 个 key/trace/candidate/status 不变，20 条已确认决策带 provenance 迁移。
- [x] 联合审核 Batch 03：接受 10 条 GDAL 精确签名；`gdalinfo/ogrinfo` 仅获得 anchor 身份，不自动进入 taxonomy/训练；累计 30/121，剩余 91 行。
- [x] 联合审核 Batch 04：接受 10 条 GDAL 精确签名；`rasterize/translate` 由 GDAL provider 与参数 schema 消歧；累计 40/121，剩余 81 行。
- [x] 联合审核 Batch 05：接受 10 条 GDAL/QGIS provider 精确签名；Plot 等算子仅获得 anchor 身份，不自动进入 taxonomy/训练；累计 50/121，剩余 71 行。
- [x] 联合审核 Batch 06：接受 10 条 QGIS 精确签名；Histogram/Scatterplot 等报告算子保持 anchor-only；累计 60/121，剩余 61 行。
- [x] 联合审核 Batch 07：5 条 provider/参数 alias 接受，4 条 GDAL framework/UI 类拒绝为 non-anchor；累计 decisions=69、accepted=65、remaining=52。
- [ ] `CreateCloudOptimizedGeoTIFF(createcog)`、`DatasetIdentify(dataset_identify)` 是真实算法，但 v2 无正确 bounded candidate；暂不写最终 decision，后续受控扩展候选。
- [x] 联合审核 Batch 08：7 条源码 `name()` 与参数 schema 支持的 GDAL alias 接受，2 条 utility/data class 拒绝；累计 decisions=78、accepted=72、rejected=6、remaining=43。
- [ ] `ogrinfojson` 是独立真实算法，不得错误并入 `gdal:ogrinfo`；等待受控 bounded candidate 扩展。
- [x] 联合审核 Batch 09：8 条 GDAL/QGIS 参数 alias 接受，空 class 与 `ParameterExecuteSql` 拒绝为 non-anchor；累计 decisions=88、accepted=80、rejected=8、remaining=33。
- [x] 联合审核 Batch 10：7 条 QGIS alias 接受，3 条 QGIS framework/provider 类拒绝；`PointsFromLines`、`RasterCalculator` 以源码继承和 `name()` 消解 provider 歧义；累计 decisions=98、accepted=87、rejected=11、remaining=23。
- [x] 联合审核 Batch 11：只接受 3 条实际 Processing operator，拒绝 7 条 parameter/graph/framework/config support 类；累计 decisions=108、accepted=90、rejected=18、remaining=13。
- [x] 联合审核 Batch 12：最后 10 条 script action/provider/editor/example/no-class 记录全部拒绝为 non-anchor；累计 decisions=118、accepted=90、rejected=28、remaining=3。
- [x] v2 普通审核已结束；仅剩 `createcog`、`dataset_identify`、`ogrinfojson` 三条真实算法。
- [x] 受控 review v3 authority 已生成：只修改三行的 candidate/proposal 五字段，其他 118 行逐字段不变；118 条 decision 带 provenance 迁移。
- [x] 联合确认 v3 最后三条 proposal：`gdal:createcog`、`gdal:dataset_identify`、`gdal:ogrinfojson` 全部接受；121/121 adjudication 完成。
- [x] 仅从人工 accepted 行导出 signature anchor library，并用独立 50 条普通 direct-API workflow 构建迁移诊断包。
- **状态：** review_v3_complete（121/121 decisions；93 accepted；28 rejected）；anchor_export_ready；transfer_human_review_pending；training_forbidden

## 2026-07-15：Signature Anchor 导出与 50 条独立迁移诊断

- [x] 从完整 v3 人工裁决中确定性导出 93 条 accepted signature anchors；operator ID 唯一，GDAL 59 / QGIS 34，taxonomy admission=`not_granted`，training rows=0。
- [x] 将服务器 anchor library 同步到 `docs/reports/qgis_pilot/phase3_signature_anchor_library_v1/` 并逐文件核对 SHA256；anchor JSONL=`0a3e1ebf...40e2`。
- [x] TDD 实现 `scripts/evaluate_qgis_signature_anchor_transfer.py`：排除既有 300 pilot 和 24 canary，仅使用 source/record 均唯一的普通 `direct_api_only` workflow。
- [x] 复现预声明 dual-IDF 基线：独立集 4,673 条，candidate=3,388（72.50%），abstain=1,285；此指标只表示候选覆盖，不能表示准确率。
- [x] 确定性抽取 50 条人工诊断集：30 candidate + 20 abstain，覆盖 modality、primary family、trace length 和 ordering quality；人工字段保持空白，training admission=`not_a_training_artifact`。
- [x] 初检定位系统性假阳性：`gdal.open` 以 439/4,673=9.39% 刚好通过 10% 门槛，导致 30 个 candidate 中 12 个 top-1 为 `gdal:extractprojection`；底层 shared calls 不能直接代表 operator identity。
- [x] `semantic_anchor`-only 消融把覆盖降至 1,127/4,673，但仍有共享调用假阳性，证明问题不是单一阈值。
- [ ] 联合人工审核 `phase3_signature_transfer_evaluation_50_v2/diagnostic_review.csv` 的 50 条记录，分别计算 candidate top-1 precision、abstention accuracy 和 overall diagnostic accuracy；当前完成 15/50，partial candidate precision=13.33%。
- [x] Transfer review Batch 01：用户确认第 1、2、3、5 条 top-1 错误，第 4 条 `qgis:rastercalculator` 正确；append-only adjudication 与 validator summary 已生成。
- [x] Transfer review Batch 02：第 6-10 条均为错误 top-1；核实明确 catalog operator、多步链和 custom-unbounded 三类正确答案，不把插件类伪造成标准 operator。
- [x] Transfer review Batch 03：第 11-14 条错误、第 15 条正确；进一步确认 multi-step/custom workflow 不能压成单 anchor。
- [x] 写出 source-grounded operator-chain extractor 设计：E0 explicit ID、E1 self-describing class、E2 ordered direct-API semantic chain、E3 custom/unbounded 四级证据路线。
- [x] 新增 `qgis_training_data_mainline.drawio`，固化真实脚本 -> extractor -> 回归/pilot 门禁 -> train-only package -> 模型评估的主线关系。
- [ ] 完成 50 条审核后，以这些 regression cases 构建约 300 条分层 source-grounded extractor pilot；当前不生成训练行。
- [ ] 只有人工结果证明 anchor 有增益后，才设计 family/text-aware rerank；当前禁止用 signature transfer 自动生成 operator/L3 标签或训练行。

## 2026-07-16：Source-Grounded Extractor v1 与盲测门禁 🔄

- [x] 实现确定性 extractor 与 fail-closed CLI；全流程不调用 LLM/API，不输出训练行。
- [x] 落地 E0/E1/E2/E3 四级证据，并阻断 generic GDAL open、metadata、UI、infrastructure 假算子。
- [x] 修复 distinct repeated operation、macro/micro 合并和 AST/steps 不可比较顺序问题；保留 input/output role 与 dependency。
- [x] 冻结 strict exact-ID Run6 开发回归：12/14=85.714%；correct old top1 2/2、incorrect old top1 avoided 13/13、custom 4/4。
- [x] 否决 provider suffix 聚合指标；`qgis:rastercalculator`、`qgis:simplifygeometries` 保持 exact miss，等待人工 alternative-set 裁决。
- [x] 用同一冻结代码生成 review order 16-50 的 35 条 blind holdout；`labels_read=false`、training rows=0、taxonomy/training admission=`not_granted`。
- [x] 核对 Run6 与 holdout 的同步输出哈希、extractor/CLI 代码哈希；权威产物仅为 `regression_15_run6_exact/` 与 `holdout_35_v1/`。
- [x] 用 scoped `.gitattributes` 固定 Phase 4 产物为 LF，防止 Windows 自动换行导致 ledger SHA256 失效。
- [x] 人工审核 `holdout_35_v1/review_workbook.csv`；35 条 review order 16-50 全部由 joint user/Codex 分批确认，未修改冻结预测。
- [x] 计算 E0-E3 item precision、overall precision、workflow 完整率和错误分布；裁决、summary、报告和 hash ledger 已生成。
- [ ] 约 300 条分层 source-grounded pilot 被盲测门禁阻断；当前不生成 QGIS 训练包。
- **状态：** extractor_v1_reviewed；pilot_blocked_pending_extractor_v2；training_forbidden

### Extractor v2 修复门禁

- [x] 用户确认两阶段设计：v2.1 precision gate，v2.2 completeness gate；全程 deterministic、无 LLM、无训练。
- [x] 正式设计规格写入 `docs/superpowers/specs/2026-07-16-qgis-source-grounded-extractor-v2-design.md`。
- [x] v2.1 Precision Gate 正式实施计划与测试规格写入 `docs/superpowers/plans/2026-07-16-qgis-source-grounded-extractor-v2-1.md`。
- [x] 实施边界锁定：冻结 v1 核心，v2.1 采用显式 profile 的确定性后处理；新增 source-quality、class-role、identity/suppression/dedup 和 locked-gate 独立模块。
- [x] 锁定裁决口径修正：旧 E3 仅因 bounded identity 漏失而保留的类，在 v2 金标中升级为 E1，不重复要求 E3 fallback。
- [ ] 按计划执行 v2.1 TDD；实现开始前不得修改 extractor v1 规则或进入 v2.2。

- [ ] 数据源预过滤：test/mock/example/provider/UI-only 文件在 operator extraction 前拒绝。
- [ ] E3 role classifier：区分 algorithm/orchestrator 与 helper/data container/provider/mock/test/GUI shell。
- [ ] constructor suppression：`QgsCoordinateTransform(...)` 等配置对象不再产生 operator，只保留真实 execution call。
- [ ] bounded identity 优先：legacy/self-describing class 先解析为高层算子，避免内部 E2 substep 泄漏。
- [ ] 支持 module-level custom function/workflow 及 dependency 保留。
- [ ] 补齐已确认 identity gap：`gdal:proximity`、`gdal:merge`、`qgis:rastersampling`、`qgis:eliminateselectedpolygons`、extract/save 和 `native:polygonize`。
- [ ] 合并 same-input/same-output semantic duplicate，并区分 parallel evidence 与真实重复步骤。
- [ ] 用同一 35 条 locked regression 验证 v2；通过后才允许重新抽取新 blind pilot。
