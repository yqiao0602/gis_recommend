# 任务计划：QGIS 工作流推荐系统 — 评测体系 + 矢量修复

## ⭐ 当前最高主线（2026-10-15，owner 终裁）：QGIS 专项训练路线冻结，先盘点后实施

**owner 终裁（2026-10-15）**：QGIS 专项训练技术路线正式冻结为项目方向；下一步不是训练，
而是先做资产盘点并产出《QGIS 专项训练实施规范》。

- **冻结路线（A→E）**：A QGIS 知识底座（完整算子目录→规范化 Schema→来源/版本管理→混合
  RAG→基础关系与结构校验；完整 GraphRAG 不作前置依赖）→ B 训练数据建设（GEE 规划监督 +
  QGIS 算子语义 + QGIS 工作流组合 + 高质量 DAG 监督；与 A 并行，基础知识记录验证后即入
  数据流水线）→ C 两阶段模型训练（Stage 1 一般 GIS 任务理解与规划 / Stage 2 QGIS 算子
  接地、参数配置与 DAG 生成；保留适量规划监督防遗忘）→ D 完整推理链路（任务规划→证据
  账本→算子检索→`processes + links` DAG 生成→结构与语义检查→有限修正）→ E 初版交付与
  定向优化。
- **三项修正（owner）**：①GEE 规划与 QGIS 专项 = 同一 Qwen3.5-9B 连续训练配方，按数据
  职责划分混入，不做"先训 GEE Planner 再从头训 QGIS"两次独立训练；②复杂任务完整性靠
  分工验证——模型提计划/外部账本追踪/结构化校验器查结构/独立语义检查（模型评审+人工
  抽查），结构合法≠语义正确；③知识整理与训练数据建设并行，防知识工程变长期项目。
- **五原则**：最终工作流质量唯一主目标（损失/问答准确率/知识库规模只是中间证据）；完整
  算子库=权威知识源（模型参数非唯一载体）；规划步骤≠算子抽象层（不引入统一算法分类层，
  最终输出真实 QGIS 算子 DAG）；先完整系统后定向优化（不预铺大量消融）；禁自我评价代替
  外部验证。
- **暂缓**：GRPO 具体方案、完整 GraphRAG（待第一版系统真实瓶颈定位后由 owner 另行裁定）。
  第一版验收 = 6 项清单：算子知识/算子接地/规划完整性/DAG 正确性/问题修复/评估可信度。
- **评测纪律沿用**：dev-120 选点、test-111 终判不调参；route2_C0 dev opF1 0.5611 为统一
  协议对比基线；系统级 vs 模型级贡献分开记账（日志与基线从第一版就保留）。
- **资产盘点四问已完成（2026-10-15，四路并行只读盘点）**：《QGIS 专项训练实施规范》V1 骨架已产出：
  `docs/plans/QGIS_SPECIALIZED_TRAINING_IMPLEMENTATION_SPEC_V1.md`（六节固定 + 盘点四问总答 +
  开放决策点汇总）。盘点要点：目录 = 1,291 算子三源一体（catalog/profile v0_4/operators-json），
  **309 = v2a 1,565 行 gold 已行使子集**（148=test111，38=benchmark v0.1-120）；Capability Profile
  v0_4 = 1,291 全集 + 参数 schema（1,127 ops 含 2,946 非空默认值）= 知识底座主干；四项校验器现成
  可复用（benchmark 结构门/io_factor/rl_reward r 电池/r5 覆盖）；头号数据缺口 = 参数监督为零 +
  接地仅 1,565 行（D5 渲染管线 = 扩量路径）；`stage1_train_v2_2A` 本地缺失且行数出入（35,246 vs
  23,030）冻结勿引用；blueprint_v2_gold_v3 本地镜像已找回（SHA 核验，旧"无镜像"记录作废）。
  **待 owner：审规范骨架 + 六个开放决策点（骨架放行/D1 混合比例/词表 30v23/D5 渲染管线三连/
  验收阈值/训练放行令）**。
- **PCA-2 · 100 任务规划能力审查立项（2026-10-15，owner 方向指示；预注册草案已出）**：一次性
  诊断——双臂（A=P0 fmt 唯一有效规划检查点【P1/P2/LT-1/CB 全 FAIL 出局；adapter SHA
  `82095811…`】vs B=Qwen3.5-9B-Base 零样本）× 100 分层任务（25 基础/35 多步/25 综合/15 时序
  条件），只出 NL 编号步骤清单（不要求算子/参数/processes+links）；0-2×五维量表 +
  critical_miss 标志 + 配对盲评（QWκ 预注册）；三类决策出口（A 可用→进落地不重训 / B 有明确
  短板→择一补 / C 明显不足→重审监督）+ 仪器阻塞独立条款（格式健康率<50% 臂质量不判读）。
  与 PCA-1 关系：复用其基建，关键差异 = 格式解耦（绕开 B 臂塌缩墙）+ n=100 + 双臂。任务来源 =
  PCA-1 已审 B/C 组 40 条复用 + 新起草 60 条（GEE 域不入轮；三道防泄漏）。预注册草案：
  `planning_capability_audit_v1/PCA2_100TASK_PREREGISTRATION_V0_DRAFT.md`。**Owner 六项裁定已落（2026-10-15）**：①③④⑤⑧通过、②有条件通过（阈值先冻/脚本先写/
  截断≠正常完成）；两条执行边界并入——smoke 三结果分报（管线完整性/格式健康/规划可评估性，
  smoke 不判规划质量）+ 归一化三列分记（原始格式符合/归一成功/归一后质量，格式转换不得误读
  为模型能力）。**Owner 任务集策略调整（2026-10-15）**：任务集改用 **GEE 真实任务描述**（held-out 池直接
  检验"现有规划模型能否生成合理步骤清单"）——域内先测；39 条 QGIS 味历史任务与新起草任务
  PARKED（冻结资产保留，跨域问题留后）；防泄漏继承 PCA A 组隔离方法 + RL 评估集采购的指令
  匹配排除法（94,445 从未训练池，另排除 PCA-1 A 组 20 条与 RL 评估集 24 条防评审锚定）；
  分层改按可观测量（final_semantic_length 带）25/35/25/15，分位边界建池时计算并随 manifest
  冻结；seed 20261013 惯例。预注册升版 V2 CANDIDATE（V1 未冻结即被替代，留档）。**CPU 侧
  已完成件**：格式健康自检 6/6 + 归一化电池 15/15 全绿（SHA 钉档）；族→NL 映射表 23 短语待
  owner 逐词审。GPU smoke 待全冻结后单独授权。本轮不扩展额外模型对比或训练实验。
  **任务集已构建（2026-10-15，seed 20261013）**：池 94,405 从未训练候选（排除：train 指令匹配
  33,371=与 RL 采购口径精确互证 / 脚本号 / RL 评估集 24 / PCA-1 A 组 20 行）→ 25/35/25/15 全带
  满额 + smoke 8 条严格不相交；A 组零重叠已独立核验（20/20 行号在案、script 零交集；16/20 专
  用计数差 = 另 4 行被更早的脚本号规则排除，双保险成立）。产物：`pca2_v1/pca2_taskset_100.jsonl`
  （SHA `c0274cc8…`）+ smoke（`afc16cc6…`）+ manifest（`16f721a3…`）+ **owner 审核表
  `PCA2_TASK_REVIEW_WORKSHEET_V1.md`**。**Owner 快看指令（2026-10-15，覆盖既有审核序列）**：跳过逐条审核/映射表审核/冻结清单仪式，
  直接生成看"当前模型究竟能做到什么程度"。正式 PCA-2 预注册 V2 转入 PARKED（若日后要正式
  盲评版须另抽任务——owner 将看到本次输出，同批任务不可再作盲评）。本次运行定性 = **快速
  能力快照（非正式审查）**：复用 PCA-1 冻结生成仪器（NL 步骤清单 prompt / greedy / 768 /
  bs=8 / 截断 1024），任务 = pca2_taskset_100 + smoke 8（held-out 纪律保留）；**臂设计依
  PCA-1 健康证据修正**——stage1 在 NL prompt 下 59/59 全塌（含 GEE 域 A 组）为已知事实，
  故主臂 = **Bprime 形态（P0 原生部署：任务+训练分隔符→Blueprint）** 5/6 健康，对照臂 =
  A_base（NL prompt，100% 健康）；P0 输出经已建归一化器渲染可读。逐条格式健康即时分报。
  **快看结果（2026-10-15，216/216 完成，24.4min，服务器 /home/qy/pca2_gen/ + 本地镜像）**：
  **两臂零塌缩**——P0 原生形态不塌实证确认（NL 问法才塌，59/59 为 PCA-1 旧证）。P0 渲染率
  **63/108=58.3%，分带 L1 74% / L2 73% / L3 37% / L4 35%——瓶颈=长任务 768 预算截断**（45 条
  JSON 全为真截断，0 条尾部垃圾；本次为裸 greedy 仪器，无 R1 护栏）。Base 108/108 顶格写满
  不停（42 条含 END_OF PLAN 仍继续写）。产物：`pca2_v1/QUICKLOOK_RESULTS_V1.json`
  （SHA `228fa6e2…`）+ `QUICKLOOK_WORKBOOK_V1.md`（108 条任务×P0 渲染×Base 摘录对照）。
  正式 PCA-2 维持 PARKED**。**B 档判分收口（2026-10-15）：31/108 = L1 全查 22 + L2/L3/L4
  定向抽查各 3**：P0 CM **31/31=Y、跨带一致**（L1 22/22、L2 3/3、L3 3/3、L4 3/3；L2-L4 均分
  3.0-3.67/10，无复杂度梯度改善）；五维均值 1.32/**0.52**/1.00/0.52/1.00；Base CM 3/31=Y
  （1 参数错误+1 真实缺口+1 截断暂定；Base 撞顶截断为仪器病，多处 caveat）。**关键细分样本
  T-098**：P0 参考链族覆盖高达 14/21 仍 CM=Y——族覆盖广度≠任务特定语义（插值/SG 滤波/邻域
  回归无表达槽位）。**结论定性（owner 手判+顾问复核）**：①Base 优势=预训练先验（从未进训练
  目标，非被训掉）；②P0=23 族压缩表示的信息瓶颈（任务文本标准下金标链同样不达标）+任务条
  件化弱+模板化终止（中位 127 token）；③SFT 忠实复现了贫瘠目标——**换训练方法无用，须换目
  标空间**=unified training design（from-Base+完整 QGIS workflow 输出+keep-all 长尾）已冻结
  方向，本判分为其最强经验证据。机械四指标（族召回/长度比/终止率/可用率）已全在
  `QUICKLOOK_JUDGMENTS_V1.json`。待 owner：判定快看线收口（建议收口，剩 77 条无决策增量）
  → 产出 QUICKLOOK_FINDINGS_V1 归档 → 转 unified training 实施。**故障定位已完成
  （2026-10-15，`PCA2_FAULT_LOCALIZATION_V1.md`，5 代表任务全原始记录并排）**：P0 原始
  Blueprint 仅含 **2-5 个 stage / 88-137 token**（Base 同任务 2,600-3,200 字符）——**转换环节
  被排除**（机械渲染构造上不可能丢信息+电池 15/15），**格式崩溃被排除**（rep15 108/108 稳定
  EOS）。判定=顾问决策表**分支 2 + 表示层结构上限**：①schema 天花板——Blueprint v2 只能表达
  {seq,family,repeat}，完美 Blueprint 也无法表达投影统一/参数/IO 绑定（T-010 覆盖 4/4 仍
  CM=Y）；②模型层条件化弱——自己词表内也只出 2-5 通用族（T-009 已掌握族仍漏）。**推论**：
  Blueprint-v2 不应作为新训练输出目标（至多辅助监督）；P0 不再作 Stage-1 默认检查点（from-
  Base 已双反驳在案）；资源方向 = unified training（from-Base + 完整 QGIS workflow 输出空间
  + 多源数据），与冻结路线一致，**待 owner 终裁确认**。**owner 侧顾问四决定转入
  （2026-10-15）**：①P0 fmt 停止作为 Stage-1 默认候选（不追加训练追赶）；②Base 为 Stage-1
  规划基线（围绕其实际缺口设计增强；Base≠已验证规划器——参数错误/逻辑缺口/不停笔如实记
  录）；③Blueprint 暂停作为核心规划监督目标（数据保留，候选目标=任务→有序步骤含输入/输出/
  依赖/约束）；④资源优先 QGIS 专项落地（算子语义/选择/参数/IO 绑定/processes+links DAG）。
  **与冻结路线的关系**：③④正是 unified training design 的核心（from-Base+输出空间=最终任务
  格式+规划与落地统一训练）——顾问的"NL 步骤清单候选目标"可作为该设计 D1-D4 的辅助监督候
  选；**连带后果登记**：RL 线输出空间钉死 Blueprint v2/P0（预注册条款），P0 除名后 RL 冒烟
  无限挂起（本就等位，无需新动作）。**同接口探针已发**（pca2_nlprobe_v1：8 smoke 任务、
  P0+NL 提示词+rep-pen 1.15、同解码）——关闭"接口分布偏移"混杂的最后一环；PCA-1 旧证
  （NL 下 59/59 塌缩）系裸 greedy 所测，rep-pen 下未测。**同接口探针结果（2026-10-15，
  归因闭环）**：P0+NL 提示+rep-pen 1.15 → **8/8 全部 2-token 立即 EOS 塌缩**（rep-pen 对该
  失败模式无效——它罚重复 token，而 immediate-EOS 是单步分布坍缩，无可罚之物）。**归因
  终版**：①接口脆性=实锤（SFT 后模型丧失训练格式外的响应能力，连同接口对照要求一并关闭
  "只修接口/转换"选项）；②内容贫瘠=实锤（原生格式内也只有 2-5 通用族）；两者同根=Blueprint
  v2 监督目标既语义贫瘠又被训练压死通用接口。顾问四决定证据链齐备。
  **⭐ owner 终裁（2026-10-15，快看线就此关闭）**：①P0 fmt 除名 Stage-1 默认候选（不修补不
  追赶）；②新训练 from-Base；③Blueprint v2 降级（数据保留作辅助监督，输出目标除名，是否用
  其标签由新配方决定）；④unified training，输出空间=完整 QGIS workflow（processes+links，
  含算子/参数/IO/DAG）。**三原则**：先冻结输出契约再扩数据；新训练与 Base 同测试集/提示/
  评测器对比（格式正确率≠工作流质量）；统一≠无差别混合（GEE 仅作通用规划辅助监督、禁跨
  平台标签错配；监督源可异、生成接口与验收目标唯一）。**执行序：D1 冻结 Unified Workflow
  Contract → D2 渲染管线裁定 → D3 训练配方 → D4 评估门槛 → CPU 审查后 GPU（当前不批准任
  何配方/训练启动）**。归档：`pca2_v1/QUICKLOOK_FINDINGS_V1.md`；progress.md 里程碑已记。
  **下一动作 = D1 候选草案已写**：`planner_design/UNIFIED_WORKFLOW_CONTRACT_V0_DRAFT.md`（owner 建议完整支持 DAG 分支/多解表达但首轮不要求覆盖全部模式；先冻 schema 再分阶段扩数据）。**D1 v0 候选草案已写**：`planner_design/UNIFIED_WORKFLOW_CONTRACT_V0_DRAFT.md`；Owner Decision Record 候选 `D1_OWNER_DECISION_RECORD_V1_DRAFT.md` + validator 分级表 `D1_VALIDATOR_CLASSIFICATION_TABLE_V1_DRAFT.md`。顾问技术建议候选：ADR1/3/5/7 ACCEPT、ADR2/4/6 MODIFY；**仍待 owner 签核，未生效、D1 未冻结**。参数状态记录 process/parameter 键+证据并要求 L1 参数 loss mask；输出拆静态推导/条件推导/运行时产物；分支 schema gate 与 training/runtime gate 分开。拒答 authority 已核：v0.2.1 refusal 继承 v0.1，12 条，reason_code=`unsupported_capability`/`underspecified_goal` 各6；预测字段 `sample_id/decision/reason_code`，无 `missing_info` 字段。
- **Owner 新执行顺序（2026-10-15，待按下述方案落地）**：①先裁定并冻结**最小 D1 核心契约**（最终 processes+links、unknown/default、验证边界；扩展能力单列，不等所有高级模式实现）→ ②建立 50-task 通用 GIS 推理诊断（Base、无外部 QGIS 算子资料）→ ③同任务、同 Base、提供最小可追溯 QGIS operator cards，直接产出完整 DAG，配对比较推理/grounding/DAG 瓶颈 → ④根据诊断再定 D2 数据与 D3 from-Base SFT、D4 评估门槛 → CPU 验证后独立申请 GPU。**明确暂缓**：完整 RAG/GraphRAG、SFT、GRPO、训练启动。
- **50 任务配对诊断定案（2026-10-15，owner 终裁；覆盖此前"泄露阻碍"顾虑）**：从快看 100 任务按原四带比例抽 50（12/18/12/8，固定种子，存 ID）；**A 臂=复用既有 A_base**（Base+NL 步骤提示，greedy/768，108/108 已有）；**B 臂=Base+检索 QGIS 算子卡→直接生成最小 `processes+links` JSON**（同解码；新提示词需定义并随 pack 存证；cards 从 capability profile 检索、带 provenance）。100 生成中 A 半边已有，只补 B 50 条。评审四项=步骤完整性/算子正确性/依赖正确性/整体可用性；产出→决定 SFT 数据设计优先级（推理监督 vs 算子知识 vs DAG 监督）。**定位**：能力诊断，非正式 benchmark，不证明模型达标；test-111 纪律不受影响。
- **DIAG-50 执行状态（2026-10-15，B 臂烟测五轮全 FAIL → 已停，待 owner 裁定）**：抽样+检索+pack 完成（`diag50_v1/DIAG50_SAMPLE_50.json`、`DIAG50_RETRIEVAL_V1.json`、`DIAG50_PACK_B_V1.json`，pack SHA `f6533624…`；seed 20261013；卡片=PCA 冻结格式 top-15，MiniLM 本地）。**A 臂 50/50 就绪**（复用 quicklook A_base，rep-pen 1.15，本地齐全）。**B 臂批前烟测（owner 烟测纪律）五轮记录 `diag50_v1/DIAG50_SMOKE_ROUNDS_V1.md`**：v1 仪器 bug=TRUNC 1024 截掉尾部 [Instruction]（提示词实测 1,121–1,439 token）→卡片碎片复读；v2 截断修复→think 不闭合+卡片循环；v3 预算 2560→think 字面循环不止；v4 rep-pen 1.15（对齐 A 臂冻结仪器；v1-v3 greedy 是仪器错误）→循环消失但开放式商议不收敛；v5 prefill `[Output]{`→schema 回声多候选 JSON/T-086 算子循环/T-098 转回 think。**结论：裸 Base+算子卡+JSON 图契约零样本在全部仪器组合下不可解析；A 臂同任务 NL 步骤 50/50 正常 → Base 能力格式条件化（NL 可用 / JSON 图契约不可用）**。v1 仪器下预跑 32 行（服务器 `diag50_b_out/`）superseded 保留不删除、禁入分析。烟测产物五轮全镜像 `diag50_v1/diag50_smoke_out_local/`。**owner 裁定已落（2026-10-15）：选项①**——B 臂零样本 JSON 契约不可用=正式诊断结论；不烧 GPU、3-shot 不立项。**收敛产物已出**：`DIAG50_BARM_FAILURE_SIGNATURES_V1.json`（20 行签名：literal_loop 7/think_unclosed 4/cap_trunc_open_ended 3/card_cycle 3/schema_echo 3/**parsed_ok 0**）+ `DIAG50_WORKBOOK_A_V1.md`（A 臂 50 任务评审工作簿；机械项 CAP_TRUNC 30/END_OF_PLAN 20，gen_tokens 中位 768）。**下一步 = owner 按 A 工作簿评审三项（步骤完整性/依赖正确性/整体可用性；算子正确性无对象）→ 按决策表定 SFT 数据设计优先级（当前证据已指向：格式+接地监督）**。结构统计+配对评审工作簿脚本保留备查（`diag50_analyze_v1.py`）。
- **DX 五阶段诊断线（dx_v1）当前状态（2026-10-17）**：全量 50 完成（392/392 COMMITTED）→ owner 终审收口（S0 50/50 终判确认；S2 弃权 63 行抽查 owner 逐条终审：过度拒绝(明确)=0，首要根因=算子卡贫瘠，其次检索缺失）→ 方法论裁定冻结（`dx_v1/DX_RESEARCH_ROUTE_RULING_OWNER_V1.md`：已证实 vs 待验证严格区分/A 轨四项验收/解析器 v2/推进顺序①证据底座→②仪器→③重建 S2 基线→④再定训练）→ **实验设计细化裁定（`dx_v1/DX_EXPERIMENT_DESIGN_RULING_OWNER_V1.md`）：A1 卡片补全 / A2 检索语料升级 / B 规划能力对照 单变量分离，先分别做再测组合；「在库中/被召回/卡足以证明适用」三态分记**。修正基线（解析器 v2）：无判定 130(44.4%)/显式弃权 119/正选 48(16.4%)。**执行队列：A 轨 P0 = OTB 115 卡证据驱动补全（已放行，补卡前哈希冻结已落 `A_TRACK_P0_HASH_FREEZE_V1.json`：profile v0_4 SHA `95ae97bc…`、desc 键 0/1291 守卫、49 个 retrieval.json 全冻结=A1 固定 Top-10 锚）→ A2 受控对照（不静默改检索）→ B 臂独立推进。交叉风险守卫：补卡禁写顶层 description 键（S1 语料静默变化）；S1 实为 ID 词面检索（语料 0/1291 有 description，layer_c_intent 未读取）。S1 仪器修复=受控变更另立项。**
- **【待办·未立项】DX Workflow Controller（owner 设计指导 2026-10-17「这个作为待办吧」）**：DX-50 后续演化方向——五阶段外加状态化控制层（workflow_state/plan_version/错误路由表/重试预算），从分阶段诊断走向自纠错工作流构建；五步实施序（保落盘→workflow_state 版本化→确定性错误局部回退→语义错误重选/重规划→四臂对照实验：Baseline[=dx50_full_v1 已就绪]/全链重试/局部重试/诊断式回退；核心指标含「原本正确步骤被破坏比例」）。原文归档：`dx_v1/DX_WORKFLOW_CONTROLLER_DESIGN_V0_OWNER.md`（含与现有 S4 错误标签/落盘机制的对位补注与开放点：稳定步骤 ID、目录版式迁移）。**最小状态管理器 dx_state V1 已实现并入库（SQLite 7 表/乐观锁/三维度工件状态/反向边失效/RERUN_S2 恢复闭环；首个人工确认恢复 T-083#S8 已闭合），未获批不进入四臂对照执行序。**
- **50-task 诊断设计硬边界（待 D1 冻结后建池）**：人工审核参考方案允许多解；同一任务双条件；步骤级输出只作诊断评测表示，最终产品目标仍为完整 QGIS DAG。任务必须排除已暴露的 PCA-2 quicklook 108、已见 PCA-1/RL 评审任务及已知训练池；“source-disjoint from known fine-tune data”可以核验，不能声称 Base 预训练语料绝对未见。既有 dev-120/test-111 职责不变：不可把 test-111 用作挑选/调参；新诊断集须单独标注为 diagnostic set，不替代正式 benchmark。**B 档人工判分进行中（2026-10-15，owner+顾问逐条手判）**：已记录 4/108
  （S-01/02、T-001/002，`QUICKLOOK_JUDGMENTS_V1.json`，`scripts/pca2_record_judgments_v1.py`
  转录）。初步形态：P0 全部 CM=Y（输出=高频族通用骨架：仅 RASTER_LOAD/ATTRIBUTE_FILTER/
  SPATIAL_FILTER/TEMPORAL_FILTER/CLASSIFICATION）；Base 覆盖完整但有技术错误（NDVI 波段反、
  stripmap 存疑）。CM 口径采纳严格版（必需环节缺失 OR 核心计算错误=Y），聚合时缺失/错误
  分列。**关键机械核对：参考链本身同为 3 步粗粒度且仅含已掌握族**——P0 对参考链同粒度覆盖
  仅 1/3~2/3（连已掌握族 CLASSIFICATION 都漏）→ 三层归因：①Base 表现=预训练先验（从未进训
  练目标，非"被训掉"）；②P0/参考链=23 族压缩表示（任务文本细粒度标准连金标都不达标——粒度
  口径须双镜头）；③同粒度下 P0 仍欠账=任务条件化不足（边际骨架预测），与 B 线 bag-F1
  0.645/763 漏族一致 → 支持 unified training design 立项理由（from-Base+全 workflow 输出空
  间+keep-all 长尾）。判分继续中。**截断判别+部署解码验证已完成（2026-10-15）**：`TRUNCATION_DIAG_V1.json` 判明 45 条
  渲染失败中 **43=不会停（超长编造：seq 冲到中位 50 vs 期望 10，零重复 tuple，结构性贪走）/
  仅 2=真预算不足**。rep-pen 1.15（部署解码，R1 核心杠杆）重跑 P0 臂 108 条（2.0min）：
  **108/108 EOS 正常终止、中位 127 token、0 撞顶、渲染率 58.3%→100%（L4 35%→100%）**——
  快看全部瓶颈定位为解码期终止病，结构可用率在部署形态下打满；**质量（步骤对错）未评，
  属正式轨范畴**。产物：`QUICKLOOK_REP15_RESULTS_V1.json`（SHA `7ecdd704…`）+
  `QUICKLOOK_WORKBOOK_REP15_V1.md`（108 全渲染对照）。服务器 /home/qy/pca2_gen/（本地镜像
  quicklook_out_local/）。
- **与既有线关系**：RL 线（Stage-3 位）冻结工件与预注册协议保留不删；GRPO 冒烟（契约 v3
  已签，本就等 GPU 窗口+owner 放行）按本裁定继续挂起，启动优先级让位于专项训练主线；
  PCA 结论作为新路线外部输入。

## 当前活跃状态（2026-10-10，双主线）

**GEE 语义规划器主线（Route-2）**：**A2 复审已关闭（2026-10-10）**——146 项分歧全量裁定入表（V1_4），协议 v1.0 冻结，annotation_results_v2（50 单位修订，v2 SHA d3fca732/v1 归档）。复核后指标（单人探索性）：状态 89.64%（复审带，70 项分歧全归因三错误族 F-A/F-B/F-C）、计数 92.16%（达标）。A1 暂时通过 / A3 v1.1 冻结 92.02% / A4 insufficient_sample。三错误族按 owner 裁定不再修复，结论报告即未来修复规格。检测器评估与校准作为数据质量基础设施归档，**回到毕设主线**（GEE 工作流监督→工作流推理；QGIS grounding→processes+links）。未授权：重抽、全库推广、gold、训练。

**主线真实前沿（2026-10-11 十四次更新；B1 四组全部审计完成——全部不通过）**：
- **B1 四组共享蓝图均不通过**：233b0472（ATTRIBUTE×2 缺依据）/ abeef159（AGGREGATION 在 RASTER_LOAD 前）/ f748c3df（ITERATIVE_APPLY 兜底）/ c74fe277（AGGREGATION 语义过载）。96 行受影响；
- **跨组系统性结论**：折叠规则保留粗粒度骨架但丢失语义区分操作——非个别错误而是设计缺陷。修复方向已明确（5 项）；
- WS1 93/93 + WS2 **181/181 语义裁定全部收口**（2026-10-12：末项 k=370 受托裁定——结构解码 38 年×3 传感器×6 阶段=723 精确对齐任务文本，维持 suspicious：rg 标注缺陷（VECTOR_LOAD repeat=38 与字面矛盾）+ 年×传感器循环未入 repetition_groups（表示粒度不一致）+ 源级不可验证；k=370/994 同任务孪生对至多取一入可信子集）。多解判别集设计 v0 + 协议 v1.1 草案已出；
- **当前主线（owner 五步指令，2026-10-12；机制已定位）**：①WS1/WS2 裁定冻结（**已完成**）→ ②B2-P1 修复（P0 证据冻结✓ C6_EVIDENCE_FREEZE_V1；P1 对齐修复✓ 零回归 788→3 partial；P2 政策草案待确认；P3 材料就绪待 owner 逐条裁定）——**生成链已追平**：`blueprint_v2_preflight_v1.py` = 语义链 RLE 机械计数 + 任务关键词 hint 装饰；无执行语义/无交错模式检测/无循环不变量处理——三机制定位：M1 计数无误但不变量归属在上游链（k=370 sid=60463 链尾字面 38×VECTOR_LOAD），M2 条件计数混淆在链 token 粒度（1,411 抽样材料已出），M3 交错循环无 rg 覆盖因生成器无该检测）→ ③修复前后差异报告（repeat=1/repeat>1 计数与和、语义核验后修正总量、99 行补 rg 前后覆盖率）→ ④可信 dev 子集冻结+重算 BAND_SELECT P/R/F1 → ⑤评测基线已冻结（EVAL_BASELINE_FREEZE_V1：全集 0.6165 / trusted-subset 条件基线 0.5589）；错误分解完成（瓶颈=阶段选择 52.9% + 长链终止控制 100%截断型 parse fail + 重复量化低发 2:1；非顺序/非格式）→ owner A/B/C 裁定（2026-10-12）：A 优先（协议+A1 样本已冻结 `A_EXPERIMENT_PROTOCOL_V1_FROZEN.md`/`A1_SAMPLE_131.json`，臂=2048 tokens 单变量；**执行前核验全部通过（样本 v1.1 稳定 ID+终止四分法+统计口径预注册）——等待 GPU 与工件 SHA 对账，恢复后按协议 v1+v1.1 直接执行**）；B 仅设计准入（A 后）；C 暂停。后续全弧已执行：A1 FAIL（预算否定，失控=结构性不终止）→ A′ 围堵诊断（有效非修复）→ A″ FAIL（EOS 加权双负点，结构闭合损坏机制，adapter 已标 FAILED/DO NOT USE）→ **R1 受控部署生效**（`R1_DEPLOY_CONFIG_V1`：开关式默认 P0_RAW、终止四分、比率锚定监控；127/131 预算内终止 vs pre 60.3%）。**下一阶段核心任务=提升模型工作流规划能力本身**（阶段选择/覆盖、顺序依赖、适当终点停止、QGIS grounding 四能力分开测）；B/RL 暂不启动直到训练方案有明确防回归设计（轻量训练前门禁已立：梯度范数+EOS loss+结构闭合指标逐记录、checkpoint 级解析率+覆盖评估、结构解析率=早期停止指标）。**未授权：全量重训、P1 格式改造、RL、自动压缩不可核验循环**。修复序：5 行不变量（schema 标记待核）→ 99 行补 rg（确认循环真实+边界可恢复后）→ 1,411 分层抽样裁定（不整族改 1）→ 986 保留标记。

**Planning Capability Audit（PCA，2026-10-13 立项；协议 v1 已 FROZEN）**：E2E A+B 双分支均触发（L1 内容错误 AND L2 grounding 独立不足）后，owner 裁定**先冻结模型做独立规划能力验证，不重训、不进 Stage 2**：60 任务试点（A 组 GEE held-out / B 组 QGIS 无算子 / C 组复杂组合 各 20）× 三臂（base / stage1 / stage1+tool 算子卡）+ B′ 诊断臂（常设 6 任务），解耦"会不会规划 / 能不能迁移 / 能不能落地"三问题；格式健康（format_valid/content_assessable/hit_cap/termination_status）与规划质量分开报告；迁移读数=配对任务内差+task_type 分层+域内外分解三合一致；C 臂结论限定"工具信息对计划质量的影响"。协议 v1：`plan_pipeline_v1/planning_capability_audit_v1/PCA_PROTOCOL_V1_FROZEN.md`（owner 五处修订+七项 OQ 裁定已落；v0 保留为历史）。**当前阶段 = Phase 1 任务+金标构建**（60 条起草 → owner 逐条审核）；审核通过前不运行正式 180 次生成。执行权限：不重训、不改 21-family、不启动 Stage-2/RL。

**RL 线（Route-2 Stage-3 位，2026-10-13 立项；本裁定将上方 10-12"未授权：…RL…"条款修订为"按预注册协议放行"）**：owner 三项裁定——①采纳四阶段路线（Phase 1 GRPO 工程 smoke → Phase 2 RAFT/DPO 对照 → Phase 3 亲和采样+门控 GRPO → Phase 4 过程奖励/估计增强消融）；②输出空间钉死 Blueprint v2（QGIS Graph RL 属 Stage 2 维持冻结）；③Phase-1 场地 mdzhang 共享。协议已升版：`plan_pipeline_v1/rl_line/RL_LINE_PREREGISTRATION_V1_CANDIDATE.md`（V1 CANDIDATE，v0 DRAFT 留档）——owner 审查轮五项 OQ 全部落定：OQ-1 批准（24 任务×8 候选，seed 20261013）；OQ-2 有条件（等权须先过正反例电池+S2 共现检验，修定义不调权重）；OQ-3 β=0.04 仅初值；OQ-4 S4 硬上限 ≤48 task-group updates + 六项停止条件（KL 阈值与 β 分开：per-token KL>1.0 nat×5 连续或单步>10 nat 硬停）；OQ-5 Phase 2 等 S2 吞吐外推报告后 owner 单独放行。r4 升级为 schema 级可执行定义（非空/seq 连续/rg↔stages 双向一致/hint 标签合法，per_feature 出现即非法；正反例电池 N1-N7+B1-B3 作 pytest，全绿才算奖励实现冻结）；绝对 repeat 量级只记录不评分（Contract E4 口径）。S2 验收拆双结论：工程验收 + 信号诊断（有效组<8/24 登记"信号覆盖有限"，不得解读为可扩量）。**本地实现已交付（10-13）**：`scripts/rl_reward_v1.py` + `tests/test_rl_reward_v1.py`，电池 22/22 全绿（pytest 7/7）；真实数据核验发现**本地语料两种 rg 方言并存**（contract 755 行全过 composite=1.0 / anchor 1,078 行=P1/P2 实验谱系窗口折叠表示，奖励不支援——P2 adapter 非 RL 起点）；P0=contract 方言为推断（planner_v2_train 建于合同冻结后、E3 消费 iteration_hint），**S1 增加方言指纹核验项**；total_iterations/stage_count 在 2,985 行本地目标中 0 出现→只记 field-presence 不判负；5+5 行 non_maximal_run 缺陷在 anchor 谱系（RL 范围外已登记）。报告 `rl_line/REWARD_BATTERY_REPORT_V1.json`（v1 留档）。**owner 二轮裁定已落（10-13）**：D1 修订回归 V1 局部 mask（entry 缺陷只 mask 受影响分量，级联仅保留 r1a/r1b；统一规则=可判定违规>不可判定 masked>通过）；D2 接受；D3 升级（rg 键缺失→r4 masked 不静默通过）；D4 不接受无条件放行（合同无显式 minItems:1——空序列漏洞量化：空=0.833/合法=1.0/解析失败=0.0，处置选项 a/b/c **S2 放行前 owner 定夺**）；P0 方言推断 S1 实证、方言不符先查链路不兼容掩盖。**实现升版 v1.2**（模块 SHA `18c4e5a51d7f916b…`）：**D4=(b) 落地——空序列=gateway 级退化，正式奖励 R=0（empty_stages_gateway）**；gateway 默认 ON=正式 RL 奖励路径，OFF 仅诊断（保留旧行为）；composite 恒载 C0 诊断、r4 V1_empty_stages 诊断保留；不扩大其他惩罚；owner 限定=工程裁定不改冻结合同（无 minItems），非空 stages 入合同须另走变更流程。pytest 12/12（含 on/off 回归矩阵）、电池 23/23（含 formal 期望）、contract 755/755 formal 复验、D1/D3 回归不变；报告 `REWARD_BATTERY_REPORT_V1_2.json`（v1.1/v1 留档）。**状态：v1.2 owner 审查通过（设计口径）+ S1 放行前三项核验完成**：①差异审查=机械回归（v1.2 gateway-off 重放 vs v1.1 记录）23 电池行+3 D4 场景**逐位一致零偏差**；②完整 SHA-256 入报告（模块 `ae72e638ef036c1209ca3f931790ab59c764389ec88dfffd0a238a2607856433`）；③接口契约=`RewardResult.training_reward`（=composite_gateway 别名）为训练器唯一合法字段，composite 仅诊断，gateway 默认 ON。**S1 已执行（10-13，mdzhang 只读）**：数据 SHA `443d5d31…` 精确匹配、33,339 行 0 解析失败；**训练目标方言=contract 100% 实证**（21,714/21,714，0 anchor）+ P0 真实输出 1,852 条全扫（parse 1,560/84.23% 与已知一致、rg 全 stage_seq）——**方言链路端到端证实**；adapter 指纹已录（safetensors `82095811…`，15.7MB）；GPU 外部进程未触碰。**S1 = PASS 附 2 个开放项**：(1) 词表权威差距——合同 30 类 vs 训练实测 23 类（`vocab23_server_verified.json` SHA `8562982d…`，权威 30 名单本地/server 均不可得），用实测词表不会误收、可能误拒合法未见类（S2 r2 未知 token 报告会量化），**待 owner 裁定**；(2) P0 有 1 类 OOV 发射（CLASSIFICATION_LOAD）=r2 的目标缺陷信号，另有 5 训练类 P0 从未发射（X4 型欠发射词表级证据，S2 诊断用）。报告 `S1_VERIFICATION_REPORT_V1.json`。**S1 owner 审查=通过（含开放项 1 选 (i)：vocab23 暂定入 S2 诊断）；S2 纯评分 dry run 已执行（10-13，mdzhang，无参数更新）**：24 任务×8 候选（分层 seed 20261013，temp 1.0+rep-pen 1.15，prompt 同 p0b2），**吞吐 74.46 tok/s / 峰值 8.2GB**（Phase 2 成本门：GRPO 每步≈5min 生成、100 步≈8h+）；**信号诊断=管线通过但覆盖有限**——有效组 6/24=25%（<8/24 条款触发）、formal 均值 0.9809 顶饱和、差异全为"一候选缺陷 vs 其余满分"无分级质量信号→**仅结构奖励 v0 的 GRPO 只能学回避稀有缺陷（X5/格式），对 X4 主瓶颈零信号**，质量分级信号必须来自 r5（Phase 3，依赖多解判别线）；r2 屏蔽敏感性低（5/6 组保留）→vocab23 充分性暂获支持；OOV 完整记录=TEMORAL_FILTER（拼写）+VECTOR_CLIP 各 1 次、CLASSIFICATION_LOAD 未复现、OOV 率 1%；dry run 抓到并修复 AUX13 bug（seq-less stage+rg KeyError→不 crash+回归案例），修复后电池 24/24、pytest 13/13、模块 SHA `2ade2e79…`。报告 `s2_dryrun/S2_DRYRUN_REPORT_V1.md`+`S2_DRYRUN_SCORED_V1.json`（全标 provisional_vocab23）。**Owner 五轮裁定（10-13）：S2 工程验证正式通过、信号覆盖有限入档、Phase 2 继续暂停（不租卡、不排训练）；下一优先级=r5 可信度与离线判别验证**——r5 不得奖励更长计划/更多类别/模板匹配；先小规模人工样例验证判别器再接入 RL；无法判定 abstain/mask；判别器过后才设计 Phase 2/3；RAFT/DPO 只可作可验证结构维度的工具、非 X4 替代；S2 吞吐仅作成本估算非训练授权。**已交付**：①`R5_DESIGN_V0.md`（需求槽位匹配机制：10 规则族+等价类+ABSTAIN 门+反偏差护栏+验证协议：误伤率≤10%/omission 检出≥80%/ABSTAIN 如实报，DRAFT 待 owner 审）；②`R5_VALIDATION_PACKET_V1.md`+`r5_validation_packet_v1.json`（6 组×4 候选=24 盲评项，材料=S2 真实候选，分层 short/mid/long 各 2 组，乱序剥离奖励信息，letter→cand 映射仅存 JSON）+构建脚本 `build_r5_validation_packet_v1.py`。**等 owner：审 r5 设计 + 完成盲评标注 → 实现 r5 v0 → 盲跑 → 一致性指标 → 离线审计（有效组覆盖提升幅度+三项偏差审计）。** **Owner 六轮裁定（10-13）：R5 机制方向通过、触发规则有条件通过、直接接 RL 暂不通过；四项实现前修正（required/plausible/abstain 三态、等价类带适用条件、确定性弃权门非触发词计数、统计口径任务级+候选级并报）；标注协议冻结（4 主标签+omission_detail/unsupported_detail 两证据字段，可并存）；owner 完成 24 项盲评=全 omission（表示充分性保守口径，包缺正样本/unsupported 判例，不能据此宣告 r5 通过）。****已执行（r5 v0 实现+盲跑+解盲）**：`scripts/r5_requirement_parser_v0.py`（规则 v0.2：10 槽位族+条件等价+F3 确定性弃权+F4 全审计轨迹+vocab-gap 信号承接不可表达需求）；盲跑对照 owner 标签：候选级 22/24 一致（2/24 分歧=k=30160 B/C complete_coarse_uncertain vs omission，证据级一致经 ACCURACY_ASSESSMENT 边界信号）、任务级 5/6+1 证据级一致（k=17970 弃权+PROFILE/CHART 边界信号=F3 设计成功案例）、**误伤率不可测量**（0 正样本）、ABSTAIN 1/6；**验证过程修复 2 规则缺陷**（study-area 伪 STATS、elevation 过宽）+1 语义修正（coarse≠complete）。报告 `R5_V0_VALIDATION_REPORT_V1.md`。**下一步等 owner：①补充含合理替代正样本的合成包第二轮盲评；②离线审计（24 组有效覆盖提升+三项偏差）；③裁定是否进入下一阶段（不自动授权 Phase 2/3）。** **Owner 七轮裁定（10-13）：R5 v0.2 一轮验证通过（22/24 为正面但范围有限——缺项识别被验证、多解容忍几乎未验证）；准入合成正样本盲评+全量离线审计（均不更新参数）；RL 接入不通过；complete_coarse_uncertain vs omission 分歧在指标表中持续单列；合成样本必须标 synthetic 且与真实候选分开报告；scorable 三分类（scorable/partially_scorable/abstained）永不合并分子。已交付两份报告**：①`R5_SYNTHETIC_BLIND_VALIDATION_REPORT_V1.md`——合成包 9 项（A 合理完整 3/B 明确遗漏 3/C 边界 3，规则冻结 v0.3：primary_family 语义+CHANGE_DETECTION 探测器），自检 9/9（零自伤/三遗漏精确点名/C1 gap+C2 弃权正确；A2 初版真缺 AGGREGATION 被自检驳回重建——owner 警告的反例自行撞上），**等 owner 盲评 9 项后解盲出误伤率**；②`R5_S2_OFFLINE_AUDIT_REPORT_V1.md`——**scorable 分类 10/13/1（词表表达边界=主导问题，13/23 partially_scorable）；r5 分裂 5 组 vs formal 6 组、重叠仅 1（互补不叠加、密度都低）；长度偏差无（覆盖率随长度升）；模板偏差 0 违例；family 偏差=MASKING 覆盖率≈1%（11 需求任务仅 1 实例）——X4 云掩膜欠发射首次槽位级量化**。数据 `s2_dryrun/R5_S2_OFFLINE_AUDIT_V1.json`。**Phase 2/3 继续冻结；等 owner：盲评合成包 9 项 → 解盲误伤率 → 独立裁定下一阶段。** **Owner 八轮盲评（10-13）：误伤 0/3、omission 检出 3/3、弃权 2/9（S8 边界单列）——多解容忍红线首次测量为零；S2/S3 的 complete_reasonable 与 r5 的 complete_coarse_uncertain 是同一不确定性（owner 手工保留=r5 机械化）；八轮裁定=R5 v0.3 准入下一轮离线验证、不批 Phase 2/3；下一步=盲评标签/规则输出/192 候选逐项对齐+独立复核每个缺失槽位。已交付 `R5_MISSING_SLOT_RECONCILIATION_REPORT_V1.md`**：358 缺失实例全对账（174/192 候选）；**INDEX 90 + MASK 87 = 占 49.4%**（X4 精确到槽位）；V1 无歧义 305 / V2 包裹歧义 53（S8 先例维持 missing 单列）；3 例深查全为真遗漏（含 1 例 V2 边界）；**三方独立方法互证**（能力定位 X4 47.6% / S2 审计 MASKING 1% / 本对账 INDEX+MASK 49.4%）；另登记 1 处我的构造标注错误（A4 预期 gap 触发——错，T_CROP 无精度要求，r5 正确未触发）。**等 owner：抽查对账（V1 各槽位 2-3 例）→ V2 包裹歧义最终口径 → 下一轮裁定（真实任务可复现判别力+不系统性误伤=RL 奖励准入条件）。** **Owner 九轮裁定（10-13）**：①V1 抽查批准（按证据链，未声称核验全部 358）；②**V2 三态口径冻结**：`missing_confirmed`/`covered_confirmed`/`unresolved_wrapper`——53 个 V2 实例保留原始 missing 为审计历史、新统计标 unresolved_wrapper 不计入确定遗漏（防"表示能力不足误判为模型能力不足"）；③**358=规则输出规模≠358 个独立人工确认错误**；Phase 2/3 继续冻结。**owner 亲自抽查 15 个槽位实例**（按 k 合并防 8 候选当 8 任务）：全部"**确认要求；缺失待核实**"——JSON 支持"确认要求"，"确认遗漏"需完整候选 stages；点名两个评估风险（候选非独立样本=须同报任务数/候选数/槽位实例数；槽位出现≠功能实现=须"任务要求—阶段语义—可验证等价"三依据）。**已交付裁定包**：`r5_adjudication_packet_5516_6878_9210_9854_v1.jsonl`（32 条：k+cand+task+完整 stages+r5_missing，owner 点名的 5 个 V2 条目 5516/c3、6878/c4、6878/c5、9210/c5、9210/c7 全部在内且 r5_missing 与其枚举一致）。**等 owner：逐条裁定三态 → 后续反向对照（covered 实例+负对照）→ 未参与调试的真实任务复验 → 奖励准入评审（在此之前 RAFT/DPO/GRPO 不运行）。** **Owner 八~九轮补充抽查（三批至 k=32751）确认全部"要求成立；缺失待核实"并暴露规则缺陷候选——反向控制已执行（规则冻结 v0.4.1）**：确认并修复 5 处规则缺陷——①`EVI` 无词边界匹配 "de**vi**ation"（32751 两次 INDEX 命中全是 "standard deviation"，owner 疑似假阳性坐实）；②SPATIAL `within the`/范围词把范围限定当操作（32593）；③COMPOSITE 命中 "composite indices"（26102）；④STATS 混精度评估与面积（30160，accuracy 移出归 gap-only）；⑤`crop` 名词多义（v0.4 自引，A4 合成例当场抓获，v0.4.1 修复）。**假阳性量化：358→323（-35=-9.8% 全为规则误报/口径降级；INDEX -15/MASK -8/COMPOSITE -6/SPATIAL -4/TEMPORAL -2）；核心结论稳健：INDEX+MASK=154/323=47.7% 仍为主体——X4 非规则伪影**。新增 `requirement_uncertain` 第四态（首批：k=32593 SPATIAL、k=26102 TEMPORAL、k=22822 MASK）；V2=51；合成盲评有效性核验 **0/9 判定变化**（owner 的 0/3 误伤率结论在 v0.4.1 下成立）。报告 `R5_V04_REVERSE_CONTROL_REPORT_V1.md`。**等 owner：抽查本报告（deviation FP 证据链）→ 裁定包 32 条三态判定 → 反向对照+未调试任务复验 → 奖励准入评审。** **Owner 十一轮裁定（10-13）：INDEX 定义冻结=计算新指数（产品波段读取/缩放≠INDEX；9854=not_required）；v0.5 账本 L1/L2/L3 全获批；重跑+独立复验批准；奖励准入另评。已执行 v0.5→v0.5.1 重跑全链**：L1 area 统计动词语境（9210 假需求消除 ✅ 真统计保留 ✅）；L2 INDEX 计算语境判定（9854 not_required ✅ 真计算任务保留 ✅；过程中反向对照命中两次回归并当场修复——9854 STATS 误删【正是 owner step-3 预警情形】+6878 derived-from 表达漏检）；L3 requirement_determination 字段全链路。**数字：323→317（-6 全为口径修正）；INDEX+MASK=153/317=48.3% 稳定；独立任务集复验（未参与规则调试 10 任务×8 候选）：任务级 10/10、候选级 74/80 需求覆盖缺失信号（规则口径，未经人工确认）**。流程教训已登记：规则版本演进应先 git commit 再重跑（本轮 v0.4.1 实例级基线被覆盖，槽位级聚合有双输出支撑）；建议 rl_line 工件随下次 commit 入库。报告 `R5_V05_REVALIDATION_REPORT_V1.md`（含奖励准入评审材料清单：规则↔标签 / 奖励分布 / 冻结外部评测并列，互不佐证）。**Phase 2/3 冻结；等 owner：奖励准入评审裁定。** **Owner 十轮：32 条裁定包已完成双轨裁定并冻结**（`r5_adjudication_5516_6878_9210_9854_frozen_v1.json`）：r5 的 61 个 missing 标记去向=**missing_confirmed 39 / unresolved_wrapper 5 / requirement_uncertain 8 / not_required 8 / 改判 covered 1**。**两个规则层发现入 v0.5 账本（待 owner 批准实施）**：L1=`\bareas?\b` 假需求（9210 "deforested **areas**" 类名触发面积统计 → 8 候选误标，需统计动词语境）；L2=INDEX 槽位定义边界（9854 MODIS 产品波段读取+缩放 ≠ 计算指数 → 8 候选 requirement_uncertain；**INDEX 定义须 owner 先固定**）。L3=记录格式增补 requirement_determination 字段（需求判定与覆盖裁定分轨）。**汇总纪律**：39 不作统一遗漏率分子——9210 非必需、9854 定义边界、AGGREGATION 粒度不确定全部单列。正向结果：wrapper 一致规则运作正常（5 例全落 unresolved）；covered_coarse 经受检验（9854 cand3/4/6 诚实标注与 owner 注记一致）；61 标记中 39 确认（64%），推翻的 16 个全集中于两个可定位问题。报告 `R5_ADJUDICATION_FREEZE_REPORT_V1.md`。**等 owner：①固定 INDEX 槽位定义；②批准 v0.5 账本（L1/L2/L3）；③批准后 v0.5 重跑+反向对照+复验+遗漏率汇总 → 奖励准入评审。Phase 2/3 冻结，RAFT/DPO/GRPO 不运行。** **Owner 十一轮：INDEX 定义冻结=计算新指数（产品波段读取/缩放≠INDEX；9854=not_required）；v0.5 账本 L1/L2/L3 全获批；重跑+独立复验批准；奖励准入另评。已执行 v0.5→v0.5.1 重跑全链**：L1 area 统计动词语境（9210 假需求消除 ✅ 真统计保留 ✅）；L2 INDEX 计算语境判定（9854 not_required ✅ 真计算任务保留 ✅；过程中反向对照命中两次回归并当场修复——9854 STATS 误删【正是 owner step-3 预警情形】+6878 derived-from 表达漏检）；L3 requirement_determination 字段全链路。**数字：323→317（-6 全为口径修正）；INDEX+MASK=153/317=48.3% 稳定；独立任务集复验（未参与规则调试 10 任务×8 候选）：任务级 10/10、候选级 74/80 需求覆盖缺失信号（规则口径，未经人工确认）**。报告 `R5_V05_REVALIDATION_REPORT_V1.md`。 **Owner 十二轮裁定（10-13）：R5 v0.5.1 暂不准入正式训练奖励，批准进入"候选奖励影子评估"（Gate A-D）**；三源证据分别裁定不可互替；统计口径警告：39/317 与 74/80 均不可折算（统计单位与样本范围不同）；GRPO 前三大待验证风险=独立集误伤未量化/组内区分价值未明/过度生成诱导。**影子评估执行状态**：**Gate A 完成——全部工件已入 Git（commit 7ba729a3，61 文件：奖励模块 v1.2 + r5 v0.5.1 + 裁定链 + 影子评估契约，含独立集逐候选输出 `independent_set_r5_outputs_v051.json`）**；Gate B 盲评包就绪（`GATE_B_INDEPENDENT_BLIND_PACKET_V1.md`，10 任务×8 候选全量槽位矩阵，五标签口径：omission/covered/requirement_uncertain/representation_boundary/non_required + 候选级 unnecessary_stages 字段）；**Gate C/D 预注册契约冻结**（`GATE_CD_PREREGISTRATION_V1.md`：CF1-CF4 反事实变体与通过标准【CF3 冗余非上升≥95% 为反过度生成硬门槛】+ Gate D 四指标预注册【任务内区分率≥70%/排序τ≥0.6/误奖率≤10%/饱和率如实报】，任务数<10 标 uncertain）。**等 owner：Gate B 盲评 80 候选 → Gate C 构造执行 → Gate D 分析 → 影子评估结论（过→奖励合成设计；不过→R5 保持 X4 离线测量工具）。Phase 2/3 冻结；RAFT/DPO/GRPO 不运行。** **Gate B 盲评+解盲已完成（10 任务×8 候选=234 槽位实例）**：**TP 128 / FP 误伤 4（2.74%≪10% 红线）/ FN 漏报 0 / TN 88 / unresolved_wrapper 14（9.6% 单列）/ 假需求与需求分歧 0**——十二轮风险#1（误伤未量化）已量化且低位。**4 个误伤全部集中于 k=25159 COMPOSITE 的 wrapper 口径分歧**（owner 判迭代封装=可见合成证据，r5 保守要求 AGGREGATION 在场），非随机误伤；任务级对照：除 25159（+10 全由 wrapper 分歧解释）外偏差≤2 且全部由 B* 桶解释，FN=0。无效阶段 4 处单列；冗余全空（与 r5 不罚冗余无冲突）。**影子门位：A✅ B✅ C/D 待执行**；wrapper 口径修正入 v0.6 账本待 owner 批准（影子期间不改规则）。报告 `R5_GATE_B_UNBLIND_REPORT_V1.md`。 **Gates C+D 已执行并提交（commit 2018cf08）**：Gate C 反事实 **6/6×4 门全过**（CF1 检出/CF2 改善/CF3 冗余非上升【反过度生成硬门槛成立】/CF4 不变性；n=6<10 标 uncertain；冗余阶段正确入 audit-only 清单不抬分）。Gate D 三评分排序（10 独立任务，owner 标签为基准，任务级为主）：**结构 formal=0/10 区分、τ=−0.737 负对齐、2 组误奖、4 饱和——三项全不过**；**r5 覆盖=7/10、τ=+0.796、0 误奖、1 饱和——全过**；组合 λ=0.3/0.5=7/10、τ≈0.77、0 误奖、0 饱和——全过（λ=0.7 区分率 60% 不过）。**影子评估结论（按预注册决策规则）：r5 与低 λ 组合具备进入奖励合成设计的证据；结构 formal 单独不过（在排序层面佐证 S2 dry run 结论）**。诚实边界：n=10 小样本；owner 标签为阶段族粒度；τ 为负的机制解释待 owner 复核。报告 `R5_SHADOW_EVALUATION_VERDICT_V1.md`（含奖励准入评审三源并列材料）。 **Owner 十三轮裁定（10-13）：奖励合成设计获批（仅设计/离线分析/预注册，不含训练放行）；v0.6 正式规则变更暂缓；INDEX 公式级验证设计获批；GRPO 单独放行**。统计口径：39/61 不作模型遗漏率；Gate C 6/6=小样本；Gate D 7/10 恰过线余量小——**下一步优先在新任务上复现而非围绕现有 10 任务调权**。**已交付 `R5_REWARD_SYNTHESIS_DESIGN_V1.md`**：§1 评分方案 S0-S3（R5-only/λ 网格含端点/结构硬约束双方案/audit-only 对照）+ 复现优先纪律（现有 10 任务降级校准集，新采购 24 任务为评估集，评估集数字唯一进准入评审）；§2 校准与防投机预注册（归一化/缺失分量/重复无效阶段处置/uncertain 与 wrapper 入审计附录/三类投机检查【阶段数 KS/覆盖率方差/无效阶段率】/负 τ 独立调查不否定格式约束）；§3 INDEX 公式级 L1/L2/L3 分层（L2/L3 需表示层支持，金标对照集可先行构造）；§4 GRPO 契约骨架（另提）；§5 v0.6 补证清单（四案例证据表+COMPOSITE 判定条件+正反例回归对）。**执行清单：①新评估集采购+owner 盲评 → ②S0-S3 比较 → ③INDEX 金标构造 → ④奖励准入评审+GRPO 契约提交。全程无参数更新无规则修改无 GRPO；Phase 2/3 冻结。** **Owner 十四轮：执行清单第 1 项批准启动；三个约束锁定**（①24 任务独立性可审计=须排除训练污染——**未人工审查≠未参与训练**；②盲评协议先冻结再展示候选，任务金标/生成配置/标签全 SHA；③评估集一次性，失败回校准集，复验须另建未用评估集；④component_missing 须报率并预注册敏感性，缺失分量不得带来优势）。**采购已执行**：源池=b1_gee_stage 128,447 权威备份（本地 SHA 校验）**减去 planner_v2_train 全部指令匹配**（33,371 排除）→ 94,445 从未训练候选 → 分层 8/8/8×长度带、seed 20261013 → **24 任务（22 类型）**。manifest SHA `4366a0c4…`、任务文件 SHA `b9983488…`；披露：planner_v2_train 无源链接字段（provenance=null），指令匹配为唯一可行且充分的排除。component_missing 预注册已入设计文档补丁。**生成阶段被 GPU 预检停止**（空闲 1,365 MiB < 12GB 裕量；外部进程未触碰；VRAM 监视器已挂，窗口开即启动）；生成配置与 S2 完全一致。**等 GPU 窗口：生成 → Gate B 式盲评包 → owner 盲评 → S0-S3 比较。Phase 2/3 冻结。** **Owner 盲评完成 + 解盲 + S0-S3 一次性比较完成（commit 98662901）**：①27 空候选与 r5 不可解析清单**精确 ID 对齐**；槽位顺序 0 不匹配；②314 可裁定槽位实例：**TP 157 / TN 134 / FP 0 / FN 0**——非 TERRAIN 槽位上 r5 与 owner **100% 一致**；**23 例分歧全部为 TERRAIN**（owner 口径：地形处理在阶段摘要不可裁定，统一 B）→ v0.6 账本新增 TERRAIN 从 required 降级；③**S0-S3 一次性比较（从未训练集，可裁定宇宙对齐）**：**S0 r5-only 区分 13/17、τ=+1.0、0 误奖、4 饱和——全过**；λ=0.3/0.5 与 S0 等价；λ=0.7 区分率 11/17 不过；**纯结构 λ=1.0 全不过**（0/17、τ=−0.976、7/17 组误奖、15/17 饱和）——**owner 十三轮要求的"新任务复现"达成**。边界：n=17 任务；owner 分数=阶段族粒度 C/(C+O)；TERRAIN 双侧排除（单侧计入会拖低 S0，已验证披露）。**等 owner：①奖励合成 λ 终选+校准规则裁定；②v0.6 账本（TERRAIN 降级 + wrapper 口径）批准；③GRPO 冒烟契约另审。Phase 2/3 冻结。****Phase 2/3 冻结；RAFT/DPO/GRPO 不启动——本报告不构成训练授权；等 owner：奖励准入评审裁定（进奖励合成设计 vs R5 保持离线工具）+ v0.6 wrapper 账本 + INDEX 公式级验证提案。**S1 为只读核验（SHA 对账/共租检查/词表物化/电池运行），冲突先停。冻结设计原则：GRPO≠去偏（组内归一化只消加性共模偏移，内容相关偏差会被强化）；RAFT 不能创造验证器看不见的正确性；奖励 v0 全 gold-free 四分量（schema/词表封闭/重复合法/结构有效）不可核验维度 masked；rollout 解码 rep-pen 1.15（冻结评测仪器不变）；训练任务 ⊂ planner_v2_train（禁 dev-1852/PCA-60/test）；E0 复用既有 P0 dev-1852 预测。PCA/多解线=外部输入，仅 Phase 3 依赖。E1-E7 单变量阶梯；E7（Kalman/估计增强）启动条件=实测 GRPO 优势估计不稳定。

**GPU 侧主线（自 2026-09-27）**：
- **mdzhang (10.191.2.38, A10 24GB) 已恢复在线**（2026-10-12 owner 确认；SSH 免密可用）。旧备份 `../server_backup_mdzhang_20260927/` 保留。GPU 共享注意：yyt 作业常占 ~6-9GB，大批量任务前查 `nvidia-smi`。A 线全部 GPU 实验已于 2026-10-12 在此机执行完毕（训练+推断+回归）。
- Base zero-shot **dev** 完成（W1-W4 全 0、invalid 86.4%，锚点=地板）；**test** 半边改在租用 GPU 重跑（三冻结 SHA：evaluator v1.3.1 / 探针 / 推理配置）。
- 待 owner 租用 GPU 后依次：test 复跑 → 预注册 W1-W4 绝对下限+Δ_i → Stage-1 开训（须 owner 显式放行）。Phase R evaluator-repair rerun 可复用已保全的 ep1/2/3 checkpoint（免重训）。
- 详细交接看 `docs/CURRENT_STATE.md`。本文其余章节为历史工作流记录。

## 目标
建立系统无关的多指标 QGIS 链评测体系（①②③），用 V4.6 模型实测并定位"矢量能力缺失"的根因，通过数据扩充+词汇扩展+模型重训，持续提升矢量规划能力。

## QGIS Planner Benchmark v0.1 独立工作流（2026-07-31）

## QGIS Planner Benchmark v0.2 roster-first 规划（2026-09-10）

本 agent 的唯一职责仍是构建正式 QGIS planner benchmark，当前目标是冻结 v0.2 supported family roster 与约 120 条 final 的结构预算；不负责 GEE、QGIS 训练数据或模型训练。

v0.2 是 v0.1 的受控修订，不是从零开始：v0.1 protocol/taxonomy/scorer/exclusion/review assets 继续继承；v0.1 sealed release 保持 immutable。当前 31 个 source-backed DAG 中 22 个可作为 v0.1 graph/gold migration 候选，9 个为新增 graph；但 v0.1 手写 task text 必须完成 source provenance rebind 后才能计入 v0.2。

- [x] v0.1 保持 immutable；v0.1 errata、hash-bound artifacts 与 sealed gold 不重生成。
- [x] 确认 v0.2 采用 roster-first：先 stable101 四态分类，再冻结 quota，再做 candidate supply repair。
- [x] 复核既有 roster freeze 记录；R1-R5 gate、预算原则和禁止事项以现有 benchmark authority 与本段计划为准。
- [x] R1：stable101 四态 roster 已冻结；权威文件为 `benchmarks/qgis_planner_v1/authority/v02_supported_family_roster.json` 及同名 `.md`，提交 `f186d31`，20 supported / 8 deferred / 22 out_of_scope。
- [x] R2：已冻结 `benchmarks/qgis_planner_v1/authority/v02_budget_matrix.json` 与同名 `.md`；development 40 / 36 canonical DAG，final 120 / 60 canonical DAG，含 family tier envelope 与 P0 结构 floors。
- [x] R3：149 条既有 source-backed/expert candidate 已逐条生成 v0.2 intake ledger；87 条符合 20-family roster，62 条因 family 不在 roster 排除；Gate 1、Gate 2、parameter-free 和结构检查结果已绑定。
- [x] R3 review envelope：31 个 eligible DAG 生成 38 个 hash-bound review jobs；linear 主审 31，merge 二审 7，queue SHA 固定。
- [x] R4a：31 个 DAG 已完成独立 graph semantic review；38 条 review record、23 个 `closed`、8 个 `returned_for_revision`、0 个 validator failure；7 个 merge DAG 均完成双 reviewer。
- [x] R4b approval：31 个 DAG 已完成 hash-bound approval ledger；23 个批准进入 task authoring，4 个 `return_for_revision`，4 个排除；全部 `task_gold_admission=not_granted`。
- [ ] R4c：从已有 source-backed QGIS workflow/training records 抽取并去参数化 task text，为 23 个批准 DAG 绑定 gold；执行 task-to-gold review 和 Gate 2 重检，累计可交付 task+gold。禁止凭空手写任务。
- [ ] R5：生成 v0.2 manifest、sealed gold、review/leakage ledger、scorer 与 checksums。

当前 v0.2 可交付 task+gold 计数仍为 `0`；脚本、schema、review job、candidate、review closure 或 approval 数量均不计进度。R4a/R4b 已完成，下一步是 R4c source-derived task extraction + task-to-gold review；模型 prediction 必须等 v0.2 freeze 且 inference config 冻结后才开始。

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
**2026-09-11 — benchmark v0.2.1 已冻结（6006e49）并合并 main（c515c77/5647636），M1/M3 推理配置冻结（45f5abb）且 final-100 预测完成。模型实验主线切换为：M1 增强消融（M1-R2）+ domain_corpus_v1 构建 → M2 路线 → 三路线统一比较。M1-R1 冻结为 scratch baseline（准确构成 = 冻结的通用英文 BERT + 从零 decoder，非纯 random init），不重训、不翻案；R4 规则（开 gold 前先锁 prediction hash）继续有效。**

## 模型实验：M1 增强消融路线 + domain_corpus_v1（2026-09-11 立项）

实验动机：M1-R1 在 benchmark v0.2.1 final-100 上 OOD 塌缩（88 空图、100/100 以 Define Projection 开头、val Top1 13.75%），M3 输出跟随任务文本（74% token 覆盖内）→ 预训练先验是任务泛化主来源。M1 增强体系回答"领域适配能弥补多少从零训练的语言先验缺口"，与 M2（Qwen Base + DAPT → SFT）形成"先验 × 领域适配 × 规模"对照矩阵。增强路线是**独立新实验**，不替换 M1-R1，不修改既有 M1/M2/M3 冻结矩阵。

消融矩阵（每级相对上一级只新增一个变量；R3/R4 具体方案 Phase 3 再定）：

| 模型 | Encoder (BERT) | Decoder | TAPT | SFT | 角色 |
|---|---|---|---|---|---|
| M1-R1 | R1 冻结配置（大部分冻结+顶部两层解冻） | 从零训练 | ❌ | ✅ | scratch baseline（已冻结） |
| M1-R2 | 同 R1，**不变** | + 领域 CLM-DAPT 后 SFT | ❌ | ✅ | decoder 领域适配（本轮执行） |
| M1-R3（候选） | + 解冻全层领域 MLM | 同 R2 | ❌ | ✅ | encoder 领域适配（Phase 3 定） |
| M1-R4（候选） | 同 R2 | 同 R2 | ✅ | ✅ | 任务语言适配（Phase 3 定） |

- [x] 前置确认 A 完成（2026-09-11，`docs/reports/m1_phase0_precheck_a_language_v1/`）：benchmark dev/final/refusal 共 132 条**全英文、bert [UNK]=0**——推理侧无语言混杂，M1 塌缩不可归因于输入语言；paper train 整体 94.3% 英文（GEE 8,201 行 100% 英文），但 **QGIS 子集 616 行中 81.7% 中文/混合，426/616（69.2%）对 M1 encoder ≥50% [UNK]**，有效可读 QGIS 监督仅 ~190 行（M3 原生可读全部 8,817 行）——训练侧语言不对称列入 M1 vs M3 混杂清单；M1-R2 的 DAPT 只能消费英文池。次要观察：benchmark 文本长度约为训练文本一半（median 120.5 vs 313 字符）。
- [x] 前置确认 B 完成（2026-09-14，`docs/reports/m1_phase0_precheck_b_tasktype_v1/`）：2×2 消融（task_type {oracle, Unknown} × 长度 {按类型, 固定 8}），同 checkpoint（SHA=冻结记录 97e61fd4…）、同 49 行 val、同进程。**task_type OOD 是塌缩的主要触发/放大因素（非唯一原因）**：仅换 Unknown 即 P/R 0.13/0.20 → 0.00/0.00，首 token 多样性 26-27 → 5，吸引子出现（L3_04_05_09 51-59% + Define Projection 24.5%），wrong_family 48/49，GEE/QGIS 行双归零；但 Oracle 下 exact 仍 0/49、SetF1 仅 0.148——基础能力本来就低。长度策略二阶（Oracle 下固定 8 略增 R +0.058，Unknown 下无关）；空预测率全条件 0/49——benchmark 的 88/100 空图是 bridge 丢弃而非空链。M1 vs M3 混杂量化：task_type 是 M1 特有 handicap（ΔP −0.13 / ΔR −0.20）。9月9日 anchor 定性复现、数值漂移 P 0.115 vs 0.153（跨运行环境差异，同进程对比不受影响，效应量远超漂移）。
- [x] Phase 1 domain_corpus_v1 构建完成（2026-09-14，`docs/reports/domain_corpus_v1/`）：47,852 权威源 → D3 43,809 docs/174.7M WP（91.6% 保留）+ D4 113,472 docs/6.6M WP + D1 128/3.4K；断言电池全过。**泄漏集 GPL 事故已修**（paper_v1 test 1 行 task_text 本身是 GPL 头 → attempt 1 误杀 15,340 GPL 源文件；剔除标准许可证样板 gram 后 attempt 2 真实泄漏命中 46；数据质量注记已记录）。**recipe 冻结（owner 拍板 2026-09-14）**：D3 60% 降采样（seed 20260914，kept 26,285）+ D4 4× epoch 级过采样 + D1 1×；**byte-level training budget = 487.5M byte-tokens**（exposure D3 80.15%/D4 19.85%/D1 0.003%）；wordpiece census 181.3M 仅描述 corpus 规模。**M1-R2 §10 implementation contract 已冻结**（decoder backbone domain pretraining；DAPT=byte-level 临时词表+哑 memory+Unknown；SFT=132 词表重初始化+body/FiLM carry over+R1 协议不变）。下一步：Phase 2 DAPT 实现与训练。
- [x] Phase 2-D SFT + 评测完成（2026-09-16，`docs/reports/m1_r2_eval_v1/`）：SFT EXIT=0（R1 协议逐行不变，唯一变量 = decoder 骨干初始化；best composite 0.2802 @ep15，ckpt `22a77f77…`）。冻结协议评测（R4 遵守：`predictions_r2/PREDICTION_LOCK_R2_v1.json` 先于 gold；M3 块重评分 = 锁定值精确复现）。**final-100：空图 88%→20%、bridge 丢弃 83.8%→43.9%、L3 token ×3.4、DefineProj 首 token 99%→0%、operator F1 0.0047→0.0857（×18）**；近分布持平（val Top1 14.87→15.24%、诊断 F1 0.173→0.187）；edge F1 仍 0、harmful extra 0.90。**判定：B 场景偏乐观——领域序列先验解决"能不能生成"，不解决"生成什么"；剩余瓶颈 = Phase 0-B 归因①②（task_type 条件化 + 文本 OOD 映射）**。评测环境事故 2 起（legacy mapping 泄漏 / taxonomy 路径）已独立归档。**Phase 2 全部收官；Phase 3（R3/R4 或停止）待 owner 决策**。
- [x] **Phase 3 裁决（owner 2026-09-16）：R3/R4 不开，M1 增强线正式收束于 5e3f818**。理由：M1-R1/R2 + M2 三臂 + M3-P2-T1 已形成一致信号——模型侧调整（初始化/领域预训练/监督优化）主要改善生成状态，不改善 task→L3 条件映射；继续堆预训练实验（R3 encoder MLM / R4 DAPT+TAPT）不会改变核心监督信号，边际研究价值低。**M1-R2 最终结论（owner 定稿措辞）：R2 提升了"生成什么样的序列"的结构能力，但没有显著提升"根据任务语义生成哪一条具体工作流"的条件映射能力**——与 Phase 0-B 归因形成闭环（验证并细化：层次A 生成器状态可由 DAPT 修复；层次B 条件映射未动，Top1 14.87→15.24%、EM 0/100）。**下一阶段杠杆转向 paper_v2 数据侧**（25.7 万描述库意图重写 → task→operation→operator 监督增强；如何避免伪任务/模板污染/标签泄漏；如何设计检验"监督信号改善"的实验；R1/R2/M2/M3 作为前置基线与 paper_v2 模型干净比较）。
- [x] owner 三项决策已定（2026-09-11），spec v1 冻结：① D2 外部文档（QGIS/GDAL/OGC docs）本轮不纳入；② M1-R2 = decoder-only CLM-DAPT，BERT 保持 R1 冻结配置，BERT MLM 移为 R3 候选；③ R3/R4 暂不开，R2 后决定。

**V2a 正式立项（owner 批准 2026-09-16，审计 08ed26b）**：V1 假设"QGIS 原生监督不足故须依赖 GEE+L3"已被数据审计证伪（2,265 可训练 ≥ 2,000 门槛）。**V2a = NL → Qwen → QGIS 原生算子/工作流 DAG（processes+links，零跨平台映射损耗），QGIS-only、不用 GEE、不用 L3、不用 bridge**——目标是干净基线而非高 F1。三个不可偷懒条件：① 算子/任务频率采样控制（fieldcalculator 3,684 实例占 18%，防梯度压倒，不粗暴删除）；② 第一版保留完整 369 算子词表不砍 Top-200，head/medium/tail 分带单独报告（否则无法区分"模型不会"vs"没让它学"）；③ 2,265 = structural trainable upper bound，**描述一致性抽样回溯验证是数据冻结前的硬门禁**。禁做清单：不加 GEE/不加 L3/不加 RL/不加 DPO/不改 benchmark/不扩数据/不造新中间表示。V2a 成果后按数据量对照设计开 V2b（B≈C 规模匹配，区分真迁移/纯数据量/任务语言先验）。V1 全部资产（L3 taxonomy/crosswalk/KG/bridge/四基线）归位为"跨平台映射损失实证 + 分析资产"，不删除。

执行顺序（锁定）：**Phase 0（前置确认 A+B，先于一切 DAPT）→ Phase 1（domain_corpus_v1 构建）→ Phase 2（M1-R2：decoder CLM-DAPT → SFT → dev-20 → final-100）→ Phase 3（视 R2 结果决定）**。Phase 3 之前不讨论 R3/R4 具体方案、不爬官方文档。

**Phase 0 收官（2026-09-14，owner 裁定：不再追加 A/B）**。四层归因定稿：M1-R1 benchmark collapse = ① task_type conditioning failure（主要触发/放大因素，B 量化 ΔP −0.13/ΔR −0.20）+ ② benchmark 文本 OOD（放大因素，B 证明非必要条件）+ ③ domain/GIS prior 不足（R2 待验证）+ ④ QGIS 中文监督覆盖不足（A 量化，训练侧结构性限制）。Token-level empty 与 graph-level empty 自此分开表述（空预测率全条件 0/49；benchmark 88/100 空图 = bridge 丢弃——评估方法学发现）。**R2 目标定义（owner 2026-09-14）：不是"修复 M1-R1 benchmark"，而是在 task conditioning 与推理协议完全不变的前提下测 decoder-only DAPT 的独立泛化贡献；R1→R2 唯一主动变量 = decoder DAPT，即使 F1 0.00→0.08 也有明确解释价值。**当前：Phase 1 进行中（domain_corpus_v1 token 规模与语言池可行性检查）。

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
