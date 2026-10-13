# 能力定位实验——阶段 1 结果（Planner 侧失败拆解）

状态：CAPLOC_PHASE1_COMPLETE / 单人探索性口径 / 阶段 2 待资产
日期：2026-10-11
数据：P0 dev 1,852 行（Arm A 768 预测，逐行六类失败分型 + family diff）
设计：`CAPABILITY_LOCALIZATION_DESIGN_V0.md`（分型预注册）

## 1. 失败分型分布（行可多命中）

| 码 | 模式 | 行数 | 占比 |
|---|---|---:|---:|
| **X4 阶段缺失** | gold 有而预测无的 family | 882 | **47.6%** |
| **X5 阶段捏造** | 预测有而 gold 无的 family | 777 | **42.0%** |
| **X6 计数错误** | family 对但 repeat/次数错 | 702 | 37.9% |
| X3 重复失控 | 同族连发 ≥3（应为一组 repetition_group） | 313 | 16.9% |
| X1 格式截断 | parse fail + 触顶 | 283 | 15.3% |
| **X0 完全正确** | exact_seq | 247 | **13.3%** |
| **X7 顺序错误** | multiset 对但序列错 | **19** | **1.0%** |

## 2. 三个直接回答（对照 owner 三问）

**Q1 模型有没有学会工作流组合？——组合/排序基本已学会。**
X7 顺序错误仅 **1.0%**：当模型把 family 集合选对时，顺序几乎总是对的（X0+X7 的对比说明 multiset 对 ⇒ 序对）。工作流组合结构不是瓶颈。

**真正的瓶颈是"任务条件化的阶段选择与重复定量"**：
- X4（47.6%）+ X5（42.0%）近乎对称——模型在 gold 邻近扰动阶段集合：漏掉常规管线家族（BAND_SELECT 缺 367、TEMPORAL_FILTER 343、SPATIAL_FILTER 327、ATTRIBUTE_FILTER 292、RASTER_LOAD 282——全是"管线胶水"类）+ 捏造额外家族；
- X6（37.9%）+ X3（16.9%）——知道某阶段该重复，但**定量失控**（该 ×3 的写成 ×1 连发三遍，或该停不停）。

**Q2/P0-B2 的位置——格式问题只是第三大项。** X1 截断 15.3%：P1/解码干预全部只瞄准这 15.3%，对 47.6% 的阶段缺失和 37.9% 的计数错误**零覆盖**。这解释了"每轮修一个指标、整体仍远"的循环感。

**Q3 多解混淆的可能性——部分存在但不足以解释全部。** X4/X5 对称扰动与多解任务的边界情形一致；但"漏 BAND_SELECT/TEMPORAL_FILTER"这类常规管线缺失更可能是真实的条件化选择失败，而非等价解。**判别需要阶段 2 补充多解诊断集**（owner 已预埋此步）。

## 3. 瓶颈定位建议（阶段 1 口径）

| 排序 | 瓶颈 | 证据 | 归因方向 |
|---|---|---|---|
| **1** | **任务条件化阶段选择**（漏胶水阶段+捏造） | X4/X5 ~45% 行 | 工作流推理/任务分解精度——**数据或监督问题方向**（gold 胶水阶段一致性待查） |
| **2** | **重复定量与终止控制** | X3+X6 ~38% 行 | 生成控制与计数能力（P0-B2 B/C 臂只动了终止，未动定量） |
| 3 | 格式可靠性 | X1 15.3% | 生成控制（P1/解码候选瞄准的就是这 15.3%） |
| ✗ | 顺序/组合 | 1.0% | **已解决**——不是瓶颈 |

**对 P1 的直接含义**：P1（格式专项）瞄准的是第 3 优先级；即使 P1 成功把 15.3% 的截断全变合法，X4/X5/X6 依然存在——**主指标不会质变**。P1 应降级，服从瓶颈排序。

## 4. 阶段 2/3（待资产/批准）

1. **多解判别诊断集**：从 dev 抽取 X4/X5 行的 gold，人工判"缺失的胶水阶段是否任务必需"（区分 gold 方差 vs 真失败）——CPU 可做，需 owner 认可抽样方案；
2. **QGIS 侧同构拆解**：C0 dev 预测在笔记本（`RENTED_SERVER_PULL_20261005`）——需 owner 同步或指定路径；
3. **训练数据对照**：1,334 条 v2a + GEE 链的胶水阶段 gold 一致性审计（X4 归因的分叉点：模型没学会 vs gold 本身不一致）。

## 补充：复核工作表已生成（2026-10-11，owner 裁定 C 优先）

- `WS1_ITERATIVE_93.json/.md`：93 项 c_likely_real_error 迭代语义行——预分类（repeated_execution 87 / loop_structure 1 / undetermined 5）+ owner 裁定列（repeated_execution / loop_structure / batch_same_op / not_an_error——四种 Workflow 表达不等价）；
- `WS2_BAND_ISOLATED_181.json/.md`：181 项 isolated BAND_SELECT——三分类裁定列（gold_inconsistent / alternative_workflow / clearly_necessary）+ 任务语义证据；
- 修复记录：首版工作表生成器存在 WS1/WS2 收集耦合缺陷（ws1 的 continue 跳过了 16 个双缺失行）与 idx 未重置缺陷——已修复并验证（WS1=93、WS2=181 isolated 全量无遗漏）；
- 124 项无关键词 ITERATIVE_APPLY FN（a_or_b_needs_review）留在主裁定表 V1_4 中，不进入本轮人工复核。

## WS1 复审进度（2026-10-11）

- **已裁定 27/93**（第一批 17 + 第二批 10），裁定分布：repeated_execution 16 / batch_same_op 7 / undetermined 3 / loop_structure 1（附条件待源码核验）；
- **统一口径已采纳**（owner 定义，入标注规范附则）：repeated_execution=同一操作沿时间步/连续对象重复；batch_same_op=多个独立输入/时间窗分别执行同类操作成并列分支；loop_structure=下一轮依赖前一轮更新状态或任务明确要求迭代收敛。同时满足前两者时按 gold 表达意图（时序逐项 vs 独立分支）判定；
- **两层标签设计已采纳**：`semantic_type`（任务层）+ `gold_status`（节点层：正确/冗余或不一致/合理替代/证据不足）——避免"任务需要重复"被错误转化为"gold 必须含 ITERATIVE_APPLY"；
- **gold 结构审计项登记**：k=303（67 阶段/13 个 ITERATIVE_APPLY/repetition_groups=0——疑月度展开）与 k=370（**723 阶段/114 个 ITERATIVE_APPLY/39 repetition_groups**——疑系统性人工展开）→ gold_status=undetermined，待完整 DAG 核验；
- 剩余 66 项，第三批 15 项已发出（`WS1_BATCH3_PENDING.md`）。

## WS1 复审进度（续，2026-10-11）

- **第三批 20 行 + 第四批 27 行已裁定**（第三批表头写 19 但列出 20 行，按 20 全数应用并登记差异）。累计 **74/93**：repeated_execution 47 / batch_same_op 21 / undetermined 5 / loop_structure 1；
- **gold_status 分层启用**（owner 两层设计）：suspicious 6（k303/370/377/847/1061/1292/1391 结构风险项——377 与 847 新增：24 个同邻接/96 阶段、4 个同邻接）、undetermined 其余（含多分支疑义 k561/572/706/762/1011/1069/1262/1388）；
- **语义修正两项**（owner）：k1034/k1497 原预分类 undetermined → repeated_execution（摘要明确逐影像处理；gold 仍待核查）；
- **gold 风险优先级清单（累计）**：最高 k1061（16 节点/97 阶段）、k1292（12 节点/54 阶段 vs 摘要仅三时期——疑多源展开）、k1391（10 节点/54 阶段 vs 仅明确导出 2010）、k370（723 阶段/114 节点/39 组）、k377（24 同邻接/96 阶段）、k847（4 同邻接）、k303（13 节点/0 组）；中优先级：并行分支疑似误表达为迭代（k1069/1011/1262/1388/561/572/706/762）；
- **最后一批 19 项已发出**（`WS1_BATCH5_PENDING.md`，k=1503–1821）。

## WS1 最终汇总（93/93 全量裁定完成，2026-10-11）

### 最终类别分布（semantic_type，任务语义层）

| 类别 | 数量 | 占比 |
|---|---:|---:|
| repeated_execution | 60 | 64.5% |
| batch_same_op | 25 | 26.9% |
| undetermined | 7 | 7.5% |
| **loop_structure** | **1** | **1.1%**（k=39，且标注"待源码核验"——尚无已确认案例） |

分批高度一致：五批 loop_structure 分别为 1/10/0/0/0——**gold 蓝图几乎不含真正的迭代收敛结构**；ITERATIVE_APPLY 家族的实际语义是"重复执行/批处理"的混合表达。这将是实验 C（gold 一致性审计）的核心发现。

### gold_status 分层（节点标注层）

| 状态 | 数量 |
|---|---:|
| suspicious（结构风险：k303/370/377/847/1061/1292/1391/1503/1773） | 9 |
| undetermined（待完整 DAG/源码核验，含节点语义待查 k1608/1738/1753、结构表达待查 k1546/1595/1590/1819 等） | 69 |
| task_semantics_confirmed_pending_gold_check | 16 |

### 需查看源码或完整 DAG 的样本清单（owner 要求单列）

- **gold 展开冗余疑点（高优先）**：k370（723 阶段/114 节点/39 组）、k1061（16/97）、k1292（12/54）、k1391（10/54）、k377（24 邻接/96）、k847（4 邻接）、k303（13 节点/0 组）、k1503+1773（6 邻接 vs 3 时段×传感器）；
- **节点语义待定（中优先）**：k1608/1738/1753（多指标×传感器分支混淆）、k1546/1595/1590/1819（next:null 与 repeat:2 的结构表达）、k216（三指数组合 vs 逐时相）、k39（累积求和）、k442/494/514/745/1011/1069/1160/1262/1274/1296/1388（分支/时段归属）；
- **undetermined 整行（7 项）**：k4/112/133/673/1090/1608/1630。

## 对监督与审计的结论性含义

1. **ITERATIVE_APPLY 家族语义需要拆分重定义**：按本轮 93 项裁定，其真实语义 ≈ 64% 重复执行 + 27% 并行批处理 + 7% 未定——与"循环迭代"的家族名严重不符。presence 监督若按现家族名构造将注入系统性语义噪声；
2. **两层标签（semantic_type + gold_status）是后续 gold 修订与 presence 监督的前提**——单层家族标签不足以支撑训练；
3. WS2（181 项 isolated BAND_SELECT 三分类）复核仍待 owner 继续；两项完成后即可冻结高可信评估子集（owner 三步计划第 1 步）。

## WS2 复审进度（2026-10-11，第一批 37/181）

- **isolated 定义澄清（owner 关键质询，审计口径修正）**：`isolated:true` 是实验 C 首遍的窄代理——"gold 蓝图 stages 中无 SPECTRAL_INDEX/BAND_ARITHMETIC 消费者"，**不是完整 DAG 级孤立判定**。37 条全部 isolated:true 是查询构造的必然结果，不能读作节点在图中孤立；字段更名 `no_spectral_arithmetic_consumer_in_gold` 已登记，三分类定案须对照完整蓝图连接/源脚本；
- **37 项裁定回填**（节点合理性+Gold 核查双轨）：分三档——A 档明确有波段选择需求、优先核验连接关系 21 项（k1/8/26/28/30/52/58/63/93/100/107/117/118/178/198/201/202/246/280/318/336）；B 档需完整 DAG/源码定归属 13 项（k18/19/101/141/182/185/191/197/293/314/316/320/340）；C 档优先查节点展开与图构建 3 项（k338/346/370）+末端孤立结构 3 项（k63/118/316）；
- **gold_status 更新**：suspicious 新增 k346（17 节点 vs 摘要五年+昼夜——模板化复制疑点）、k338（12 节点规律重复 vs 源码核对）、k63/118/316/293/18/197（末端孤立/边界错位/跨源连接存疑）；
- **新登记审计方向**：gold 蓝图**连接丢失**疑点（next:null/无消费者多发）——若证实为图构建缺陷，影响面不止 BAND_SELECT，与冻结数据影响分析（F-C 项）交叉；WS2 剩余 144 项待续。

## WS2 复审进度（续，2026-10-11 第二批）

- **第二批 57 行裁定回填**（表头写 53、列出 57，按列出行全数应用并登记差异）：repeated_execution 23 / batch_same_op 23 / undetermined 7 / loop_structure 0——**loop_structure 在 WS2 全部 94 项复核中仍为 0**（延续 WS1 的 1/93）；
- **k=956 登记为最高优先级 gold 风险**：20 年降水均值任务出现 20 组 ATTRIBUTE_FILTER→AGGREGATION 重复（与逐年求和相符，不能直接判错）；须核验 gold 是否真逐年展开、最终是否有对 20 个年总量取平均的节点；若为重复复制同一筛选-聚合节点则为明显结构风险；
- 其他登记项：k425（7 窗 vs 6 邻接——核覆盖月份/传感器 vs 冗余）、k690（18 年 vs 2 ITERATIVE——核 map 集合操作是否被映射成循环语义）、k457（两期对照 vs 2 ITERATIVE——核逐景 NBR 还是前后期分支误标）、k902（单中值合成含 ITERATIVE——核集合映射 vs 显式迭代）；
- **owner 方向指令已入档**：暂停按摘要扩充标签；下一步=对高风险记录读取完整 processes/links 或原始 GEE 源码，逐条独立 gold_status（valid/suspicious/undetermined）；
- WS2 181 = 语义裁定 57 + presence 合理性 37 + 未触 87；suspicious 累计 10。

## WS2 复审进度（续二，2026-10-11）

- **遗漏批恢复**：k=946–1109 段 8 项裁定（表头写 7、列出 8）此前未回填，已补齐（含 k994 最高优先级 gold 风险、k1061 数量不匹配、k980 7v8、k1109 非典型邻接各标注）；
- **累计 141/181 语义裁定**：repeated_execution 66（46.8%）/ batch_same_op 60（42.6%）/ undetermined 14（9.9%）/ **loop_structure 1（0.7%）**；
- **剩余 40 项**：37 项=第一批 presence 格式行（owner 已给节点合理性，语义分类按调整后协议可留待完整蓝图核验阶段，或补裁定）；3 项=946/956/958 从未裁定（956 已标 suspicious，语义分类待补）。

## WS2 终裁与状态（2026-10-11，owner 三项终裁后）

- **k=946/956/958 终裁已回填**：
  - k=946：semantic_type=**undetermined**（两品种=一次解混的两个输出类别，非两次执行）/ gold_status=**suspicious**（ITERATIVE_APPLY 存在性与末端 BAND_SELECT 输出关联待核；不直接升 gold_inconsistent——后者需源码反证或完整图数据流违例）；
  - k=956：semantic_type=**repeated_execution**（高置信，逐年处理为任务要求的重复语义）/ gold_status=**suspicious**（20 年度块语义必要但 100 阶段人工展开未用 repetition_groups——表示规范疑点，非操作语义错误）；
  - k=958：semantic_type=**repeated_execution**（高置信）/ gold_status=**undetermined**（单 TEMPORAL_FILTER 紧凑表达不构成遗漏证据）；
- **k=956 模型预测语义核对**：7 阶段未表达年度划分、逐年求和与最终平均——**压缩表示非语义等价**，owner 的谨慎被个案证实（材料入 EXP_A_VERIFICATION_BUNDLE_V1.json）；
- **新风险类型登记：表示粒度不一致（representation granularity inconsistency）**——独立于节点错误与连接错误；配对审计样本 k=956（显式展开 100 阶段）× k=958（紧凑 8 阶段）；
- **评价体系三层拆分登记**（owner 裁定）：操作语义正确性 / 工作流结构正确性 / 表示一致性——**count-exact 与阶段数匹配率降级为结构相似度指标**，不得单独承担工作流质量评价；后续加入表示归一化评价（归一化必须保留各年过滤条件，禁止无时间区分去重）；
- **WS2 状态：144/181 进入统计口径**（141 终裁 + 946/958 暂定；946/958 待上下文核验后转正）+ 37 项挂起至完整蓝图核验。suspicious 累计 10，其中"表示粒度不一致"独立记录为新风险类型。

## 多解判别集候选检索完成（2026-10-11，owner 三问裁定后执行）

- **检测器修正**：首版同族连发检测漏掉 k=956 式**周期性展开**（5 节点循环×20，非同族连发）——新增周期性检测（周期≤8、≥2 循环、匹配率≥0.9）后，训练语料 33,339 行中检出 unrolled 式 **789 行（2.4%）**、compact 式 26,349 行；
- **分布发现**：unrolled 式在训练语料中真实存在（模型见过该表示），k=956 非 dev 孤例——表示粒度不一致是**语料级现象**；
- **候选产出（全部超探索性下限）**：D1 算子链多解组 **40**（下限 10）；D2 粒度等价对 **20**（下限 5）；D3 粒度不等价风险对 **20**（下限 5）；
- **D2 样本**：famJ=1.0 的 unrolled(20st/rg0) vs compact(4st/rg0) 对（"vegetation dynamics/trends"）——同家族集、节点数 5 倍差、均无重复组——正是等价性判定的典型材料；
- **D3 样本**：famJ=1.0 但任务语义不同（如 53st"Madre de Dios 制图" vs 8st"分类"）——归一化若抹平差异将掩盖真实语义差距，验证"归一化不得消除语义差异"约束的必要性；
- **D1 样本**：titleSim=1.0（同题"Classify land cover types"）但 famJ=0.5 的两条链（5 家族 vs 7 家族含 BAND_ARITHMETIC/BAND_SELECT/CLASSIFICATION）——典型替代链候选，需人工核验各自成立条件；
- 全部候选为**待语义确认**状态（CANDIDATES ONLY），脚本 `scripts/build_multisolution_candidates_v1.py`，数据 `MULTISOLUTION_CANDIDATES_V0.json`。

## 候选池重构（v1.1 字段协议，2026-10-11 owner 质量审计裁定后执行）

- **字段协议 v1.1 已应用**：candidate_class / task_equivalence / workflow_a_valid / workflow_b_valid / granularity_relation / critical_semantics_preserved / evidence / review_priority（含两条约束：task_equivalence≠equivalent 时不得凭 famJ=1.0 判粒度等价；证据不足允许 undetermined 不强制二分类）；
- **D2 筛选**：20 对中按 owner 初判——高优先保留 1（同题 31v6 阶段）、条件保留 1、误召回筛出 2（TOA/SR 对照、Classify vs Cluster）、语义负对照 1（气温 vs SST）、其余待筛；
- **D3 拆分**：D3-A 粒度风险候选 12 / **D3-B 语义负对照 8**（Madre de Dios 对入 B 类）——两子类分开计算不混合；
- D1 40 组带两问裁定结构（q1 A 是否满足核心目标 / q2 B 是否满足同一目标）；首个候选（同题 Classify land cover types 5 vs 7 家族）的完整核验材料已导出（`D1_FIRST_CANDIDATE_VERIFICATION.json`，含匹配行的全任务文本与蓝图）；
- **检测器人工验证抽样完成**：50 周期命中 + 50 未命中（seed 20261011），字段含 stages_n/rg_n/max_run/period/families + 四分类标签列（true_periodic / mechanical_template / legal_independent_repeats / false_positive）——`DETECTOR_VALIDATION_SAMPLE_V1.json` 待 owner 标注以估计检测器精确率与漏检模式（探索性审计，非总体统计）；
- 候选池文件：`MULTISOLUTION_CANDIDATES_V1.json`。执行顺序按 owner：D2 → D3 → D1 → 通过者冻结诊断集 v1，未通过者转负对照/困难案例集（不删除）。

## 三维度首轮裁定回填 + 两项即时核验（2026-10-11）

### D2 首轮（owner 20 对）
- **10 项 not_equivalent → D2-NC 负对照候选**（#2/3/4/6/7/9/13/16/17/19——算子族同、任务目标异）；
- **10 项 needs_full_dag**（#1/5/8/10/11/12/14/15/18/20——语义边界样本）；**#8 升高优先**（同题 31→6 阶段+重复组 0→1——最强 D2-EQ 候选，核同构性/依赖/迭代次数）；
- 三分法启用：D2-EQ（同任务仅表示不同）/ D2-NE（相关任务 compact 丢约束）/ D2-NC（任务语义负对照）——needs_full_dag 为待核状态非最终标签。

### D3 首轮（owner 20 对）
- **全部 needs_full_dag**（semantic_loss_confirmed=0、actually_equivalent=0——三条件未满足，非无语义丢失）；#7-8 高优先（重复展开 vs 趋势语义）；#4/#6 provenance check（k=1473 极端配对）。

### D1 首轮（owner 40 组）
- 全部 **needs_source**（证据等级裁定）；task_equivalence 字段采纳——仅 equivalent 组进入多解合法性核验，其余作语义近邻/困难负例不计入有效多解数；
- **链 A 系统性核验（owner 指定第 1 步）结果**：精确锚点核验=恰好 40 行、全部为加载/过滤/聚合五家族、**0 行含 CLASSIFICATION 或 THRESHOLD_LOGIC**，而 32/40 任务文本提及波段/指数操作 → **链 A 系统性缺少分类核心步骤的疑点成立**；归因分叉待查：gold 蓝图=完整工作流还是抽取片段（关联 F-C 项）。

### 深度核验队列 v1（汇总）
最高优先：k956（20 组重复+模型压缩非等价）→ k994（120 规律 BAND_SELECT）→ k1061/1292/1391/370/377/847（展开疑点）→ 数量不匹配 4（k425/690/457/902）→ DAG 待定 13+3 → D1 链 A 蓝图核验 40。

## 🔴 关键发现：极端阶段行 = 生成器展开循环（2026-10-11）

dev 1,852 行中 8 行 stages>100，四个极端行对照揭示**gold 蓝图生成管线的系统性展开问题**：

| 行 | 阶段数 | 任务 | 结构 |
|---|---:|---|---|
| k=370 | 723 | Identify perennial water bodies | 114×4 家族循环 |
| k=994 | **723** | Identify perennial water bodies | **与 k=370 完全相同的蓝图** |
| k=1024 | 1464 | Identify high wind speed days | 366×4 家族循环 |
| k=1341 | 1464 | Estimate annual AOD mean | **与 k=1024 相同结构但不同任务** |

**两层结论**：
1. **蓝图重复**：k=370≡k=994（同任务同蓝图 723 阶段）——同一工作流在 dev 集中出现两次；
2. **模板错配**：k=1024≡k=1341 结构（1464=366 天×4 操作——**按日展开的逐日循环**）但绑定不同任务描述——**同一生成器模板被映射到不同任务**，这是"生成器机械展开"的直接实锤；
3. **与主线问题的因果链闭合**：P0 截断（384/768 token 不够）+ under-emission 9.9/行 + X3 重复失控——都因为**部分 gold 蓝图是数百阶段的逐日展开**，模型在 token 预算内根本无法复现，也不应该复现（紧凑表示才是正确目标）；
4. **分布**：dev 阶段数 median=6、p95=25、max=1464——极端长尾（8 行>100 阶段）是 under-emission 统计的主要来源。

**对主线的指向**：gold 蓝图管线的**逐日/逐景展开机制**是把 ImageCollection.map() 语义展开成逐元素阶段的根源——修复方向=蓝图生成时用 repetition/loop 表示保留集合语义（紧凑表示），而非逐元素展开。这与"压缩≠等价"（k=956 核对）不矛盾：正确的紧凑表示必须保留年度/时相区分（如 repetition_groups），而当前 366×4 展开块缺少的正是这种结构化重复信息。

## 检测器验证审核表冻结（2026-10-11，owner 标注标准裁定后执行）

- **双侧审核表已冻结**：`DETECTOR_VALIDATION_REVIEW_TABLE_V1.json`——100 行（50 周期命中 + 50 未命中），每行含完整阶段序列、任务全文、结构特征与 owner 六字段标注列（periodicity_valid / repeat_semantics / expansion_valid / compact_equivalent / dependency_preserved / evidence）；
- **owner 分层优先级入表**：高优先 10 项（k956/581/13209/1881/10850/31367/13615/14062/5465/27418）+ 中高 5 + 漏检候选 2（k11078/k12637）；
- **k=11078 口径澄清**：period=4 检出但 is_periodic_hit=False——原因是检测器进入门槛 stages_n≥10 而 11078 仅 8 阶段；**周期字段与命中标志不是同一概念**（owner 预判证实），审核时保留检测器原始阈值与判定原因；
- **标注标准关键约束入表**：compact_equivalent=yes 不能仅凭家族序列相同判定——须核每个重复实例的参数差异能否通过重复组迭代变量完整表达；
- **边界**：100 行为探索性审核规模，非统计结论保证；如需总体性能报告，应采用明确抽样设计并给出置信区间。

## 本轮能力定位实验的累计价值

至此，能力定位实验已经产出五层递进的证据链：
1. **失败分型**（X0–X7）：定位阶段选择+重复定量为瓶颈（非格式非顺序）；
2. **实验 A 七家族诊断**：发现按边际频率选、不按任务选的机制；
3. **实验 B 频率基线**：否定强形式频率先验，修正为条件化不足+稀有家族监督不足混合；
4. **实验 C 首遍 + WS1/WS2 复审**：gold 一致性问题浮出（表示粒度不一致、孤立阶段、重复展开）；
5. **极端行核验**：发现生成器逐日/逐景展开循环（366/114 周期）——**gold 蓝图管线本身的表示缺陷**，同时解释了 P0 截断、under-emission、计数失控三个训练/评测现象。

## 🔴🔴 重大发现：dev 集 35.6% 存在蓝图重复/绑定错误（2026-10-11）

### 数据

| 指标 | 数值 |
|---|---|
| dev 总行 | 1,852 |
| 唯一蓝图 | 1,368 |
| 有重复的蓝图 | 176 个（覆盖 660 行） |
| 其中同任务重复 | 90 行 |
| 其中**不同任务绑定同一蓝图** | **570 行** |
| 影响 | **dev 35.6%** |

### 570 行 task-blueprint binding error 的含义

同一蓝图被绑定到多个完全不同的任务描述（如同一 4 阶段蓝图同时绑定"Generate cloud-masked S2 composite"和"Map land surface reflectance"）。这意味着：
1. **模型无法从这些行学到正确的 task→workflow 映射**——同一蓝图对应多种任务语义，梯度信号互相冲突；
2. **评测指标失真**——如果模型记住了这个蓝图，会在所有绑定它的任务上得高分（假阳性）；如果模型为不同任务生成不同工作流，会在共享蓝图的行上被判错（假阴性）；
3. **这不是边缘案例**——570 行占 dev 35.6%，影响面足够改变指标结论。

### 根因推测

蓝图生成管线从 semantic_chain 折叠生成 blueprint 时，将不同源脚本的**相同抽象模式**（如"load→filter→composite→clip"）合并为同一蓝图表示——丢弃了任务语义差异。这是**表示粒度不一致**（k=956/958 配对）与**表示语义冲突**（570 行绑定错误）的组合。

### 与训练集的交叉

同一蓝图折叠管线也产出 planner_v2_train.jsonl（33,339 行）——训练集中同类绑定错误的规模待查，但**可预测为同量级**。

### 对所有已计算指标的影响

- A2 状态一致率 89.64% 和计数一致率 92.16%：受重复行权重影响，精确数字待去重后重算；
- A3 严格一致率 92.02%：同上；
- under-emission 9.9/行：极端展开行贡献比待量化；
- **核心结论不变但精度有限**：瓶颈定位（阶段选择+重复定量）不受重复行影响方向性改变，但可信区间需去重后重算。

## B1 蓝图重复分组报告（2026-10-11，owner 裁定 B 后执行）

### 全景数字（精确口径）

| 指标 | 数值 |
|---|---|
| dev 总行 | 1,852 |
| 唯一蓝图哈希 | 1,368 |
| 单行蓝图（无重复） | 1,192 |
| **重复蓝图组** | **176** |
| 重复组覆盖行 | 660（35.6%） |
| 超出首行的额外重复行 | 484 |
| 同任务组（标题一致） | 35 组 / 90 行 |
| 近似任务组（sim≥0.7） | 3 组 / 6 行 |
| **不同任务组** | **138 组 / 564 行** |

### 最重要发现：最大重复组的抽象程度

| 组大小 | 唯一任务数 | 家族数 | 含义 |
|---|---:|---:|---|
| **48** | **33** | **3** | 48 行共享一个仅含 3 家族的蓝图，横跨 33 种不同任务 |
| 18 | 13 | 3 | 同上 |
| 15 | 14 | 3 | 同上 |
| 15 | 15 | 3 | 同上 |
| 13 | 11 | 3 | 同上 |

最大组：48 行（33 个不同任务）共享一个仅含 3 个算子家族的蓝图——这些家族（load/filter/aggregate）不足以区分"提取云掩膜 S2 影像"与"分析作物反射率光谱"。**binding error 确认**。

### 62/176 组家族集合不足

62 个重复组的家族集合仅限于 load/filter/aggregate——无法区分其绑定的不同任务。这些组的 binding error 概率高。

### 分类框架（与 owner 三误区对照）

| 类别 | 判据 | 处置 |
|---|---|---|
| **合法多对一** | 共享子流程足以完成任务，不同任务确可复用同一蓝图 | 保留（多解 training 信号） |
| **binding error** | 蓝图缺少区分任务所需的关键操作/参数/数据语义 | 标记，待蓝图管线修复后重生成 |
| **真重复** | 同任务同蓝图（完全重复样本） | 去重（保 1 删余） |

判定需结合任务文本语义与蓝图结构——**本轮只做结构分型，语义裁定留待标注者复核**。

## B2-P0：最大共享组审计完成（2026-10-11）

### 五大组审计结果

| 组 | 行 | 唯一任务 | 家族数 | 结构一致 | 判定 |
|---|---:|---:|---:|---|---|
| 1 | 48 | 33 | **3** | ✓ | **binding error**——3 家族（RASTER/TEMPORAL/ATTRIBUTE_FILTER）不足以区分 33 种任务（含 S2 云掩膜/作物光谱/土地覆盖/夏季反射率/叶绿素/水体分类等） |
| 2 | 18 | 13 | 3 | ✓ | **binding error**——3 家族（AGGREGATION/RASTER/TEMPORAL）绑定提取反射率/制图/红树林矢量导出等异质任务 |
| 3 | 15 | 14 | 3 | ✓ | **binding error**——3 家族（ITERATIVE/RASTER/TEMPORAL）绑定 L8 合成/真彩/城市覆盖等 |
| 4 | 15 | 15 | 3 | ✓ | **binding error**——3 家族（AGGREGATION/RASTER/TEMPORAL）绑定植被绿度/水体识别/降水/NDVI 中值 |
| 5 | 13 | 11 | 3 | ✓ | **binding error**——3 家族（ATTRIBUTE/RASTER/TEMPORAL）绑定 NDVI+LSWI/云掩膜 S2/叶绿素/LST |

### P0 结论

五大组全部为 **binding error**：每个组绑定 11–33 种不同任务，但蓝图仅含 3 个粗粒度算子家族——远不足以表达这些任务在波段选择、指数计算、分类、导出等维度的语义差异。

**根因定位**：蓝图折叠管线将所有符合 load/filter 模式的源码段折叠为相同的 3 家族最小表示——**丢失了波段选择、指数计算、分类、导出等所有语义区分操作**。这不是个别映射错误，而是折叠规则的系统性缺陷。

### P0→P1 的修复方向

折叠管线需要保留源码中实际出现的**全部**算子家族序列（而非仅保留前 N 个或匹配折叠模板的子集），并新增折叠终止条件：当折叠后蓝图的操作多样性不足以区分已绑定的不同任务时，停止折叠（保留更长序列）。

## B2-P1 实施定位（2026-10-11）

### 折叠逻辑定位结果

| 管线步骤 | 代码位置 | 状态 |
|---|---|---|
| GEE 源码 → ee_chain_folded | 生产管线（Batch8 等） | 不在本仓库（mdzhang 归档） |
| ee_chain_folded → semantic_workflow（30 类分类） | `gee_route2_semantic_workflow_v1.py::classify()` | **分类正确**——全部 30 类均有映射 |
| semantic_workflow → blueprint（stages+repetition_groups） | **未在本仓库找到**——疑为笔记本线（86cf76e4 合并）产出 | **待定位——修复目标在这一步** |

### R1/R2/R3 实施方案

蓝图生成代码不在本仓库直接可见位置。两种实施路径：

| 路径 | 内容 | 优劣 |
|---|---|---|
| **A：修正原始生成代码** | 需要先定位笔记本线蓝图生成脚本 | 根治但需先找到代码 |
| **B：后处理校正** | 写一个校正脚本，从 semantic_chain 重建丢失的操作到 blueprint 中 | 可立即实施，但为补丁而非根治 |

建议采用**路径 A+B**：先实施 B（后处理校正）解决燃眉之急，同时定位 A 的原始代码做根治修复。

### R1/R2/R3 实施规格（路径 B 后处理校正）

**输入**：semantic_workflow（30 类链）+ 当前 blueprint（stages+repetition_groups）
**输出**：校正后 blueprint（补回丢失的非 AUX 操作）

R1 逻辑：遍历 semantic_workflow 中的每个 category，若在 blueprint.stages 中缺失则插入（保持原序）。
R2 逻辑：检查折叠后 blueprint 家族数是否足以区分已绑定的任务——若 family 数 < 5 且任务数 > 3 则标记为 over-folded，拒绝折叠。
R3 逻辑：保留 repetition_groups 中的迭代范围与参数变化信息。

### 待 owner 确认

1. 路径 A 还是 A+B？
2. 蓝图生成脚本的位置（如在笔记本线上，可否拉回或告知路径）？

## B2-P1 根因定位更新（2026-10-11，蓝图生成代码定位后）

### 代码定位结果

蓝图折叠脚本 `reconstruct_planner_gold_v2.py::fold_v2()` **不丢失操作**——它只折叠相邻同族节点（保留 repeat:n），操作总数不变。

### 根因修正

操作丢失发生在**上游：semantic chain 生成阶段**（mdzhang Batch8 管线），非蓝图折叠脚本。

证据：k=370/994 的 gold 蓝图中完全没有 BAND_SELECT——不是 fold_v2 丢弃了它，而是 **semantic chain 本身就不包含 BAND_SELECT 类别**。也就是说，从 GEE 源码 → canonical chain → semantic chain 的转换中，波段选择操作被映射为其他类别（或被丢弃）。

### 修复层级修正

| 层级 | 修复内容 | 可在本仓库修复？ |
|---|---|---|
| **semantic chain 生成**（Batch8） | 检查 classify() 映射是否将 BAND_SELECT/CLASSIFICATION 等映射为 AUX 或被 DROP | **是**——classify() 在本仓库 |
| blueprint folding（reconstruct_gold_v2） | **无需修改**——fold_v2 保留全部操作 | 不需要 |

### classify() 需要核查的映射

| token 模式 | 当前映射 | 应映射 |
|---|---|---|
| `ee.Image.select` | METHOD_MAP['select'] → ? | 应为 BAND_SELECT |
| `ee.ImageClassifier.*` | CLASSIF | ✓ 已有 |
| `ee.Image.normalizedDifference` | ? | 应为 SPECTRAL_INDEX |
| **关键问题**：`classify()` 输出的 semantic chain 中是否存在 BAND_SELECT/CLASSIFICATION 类别？ | 待验证 | — |

**下一步**：对 k=370/994 的源脚本运行 classify() 函数，检查 BAND_SELECT 等 8 个高频缺失家族是否被正确映射到 semantic chain 中。如果是，则问题在 ee_chain_folded → classify 的输入 token 匹配（而非映射规则本身）。

## B2-P1 审计结果：classify() 正确、semantic chain 含 BAND_SELECT——**管线无缺陷**

### 审计结论

| 检查项 | 结果 |
|---|---|
| classify('ee.Image.select') | **= BAND_SELECT ✓** |
| classify('select') | **= BAND_SELECT ✓** |
| semantic chain 含 BAND_SELECT？ | **是 ✓**（corpus row 13248/17666 确认） |
| gold blueprint 含 BAND_SELECT？ | **是 ✓**（k=370 展开序列确认） |
| **根因结论** | **管线无缺陷。BAND_SELECT 缺失是模型能力缺口，非数据质量缺陷。** |

### 这意味着什么

1. **P1 格式专项 SFT / P0 解码干预**——不解决 BAND_SELECT 漏选问题（模型能生成合法 JSON 但漏阶段）
2. **presence 辅助监督**——可能有帮助，但前提是**模型确实学过这个家族但选择不输出它**
3. **数据去偏**——如果 BAND_SELECT 在训练集中代表性不足（0.316 prevalence），增加表示可能有助于条件化学习
4. **蓝图管线不需要修改**——semantic chain 和 gold blueprint 都正确保留了 BAND_SELECT

### 剩余的真实数据质量问题（与 BAND_SELECT 缺失无关）

1. **dev 35.6% 蓝图重复/绑定错误**（k=1024≡k=1341 不同任务同蓝图 SHA 一致）——这是蓝图生成问题，不是分类问题
2. **同任务重复行**（90 行）——评测集权重复杂
3. **训练集中 unrolled 表示 789 行 vs compact 26,349 行**——表示粒度不一致是语料级现象

### 下一步

BAND_SELECT 漏选是**模型能力缺陷**，修复路径应回到**模型训练侧**（presence 辅助监督 / 稀有家族过采样），而非数据管线修复。但前提是先处理 dev 集的 35.6% 重复/绑定错误——否则评测基准不可信。

## 工作线 A+B 并行执行结果（2026-10-11，owner C 裁定后）

### 工作线 A：评测可信度审计

| 分类 | 组数 | 行数 |
|---|---:|---:|
| binding_error_suspect | **90** | 464 |
| true_duplicate | 35 | 90 |
| possible_valid_shared | 51 | 106 |

高优先 binding_error 组（前 8）已列出（最大 48 行/33 任务/3 家族）。62 组家族集合不足已标记。

### 工作线 B：BAND_SELECT 能力诊断

- **gold 含 BAND_SELECT 的 576 行中 miss 367 行（miss rate 63.7%——含 parse fail 行）**
- parse-only miss rate 52.8%
- 长度分层：short 44% / mid 71.6% / long 65.9%
- **共发漏检 top 5**：ITERATIVE_APPLY(45) / BAND_ARITHMETIC(38) / SPATIAL_FILTER(28) / VECTOR_LOAD(24) / TEMPORAL_FILTER(20)
- 解读：**BAND_SELECT 漏检是稳定的家族选择缺陷，伴随多种其他操作同步漏检**

## B1 四组审计最终汇总（2026-10-11，全部完成）

### 四组裁定

| 组 | 行数 | 蓝图 | 裁定 | 核心问题 |
|---|---:|---|---|---|
| `233b0472` | 48 | RASTER→TEMPORAL→ATTRIBUTE×2 | ❌ 不通过 | ATTRIBUTE_FILTER×2 缺跨任务语义依据；指数/合成/分类/导出未表达 |
| `abeef159` | 18 | AGGREGATION→RASTER→TEMPORAL | ❌ 不通过 | AGGREGATION 排在 RASTER_LOAD 前（顺序冲突）；关键操作系统性缺失 |
| `f748c3df` | 15 | RASTER→TEMPORAL→ITERATIVE_APPLY | ❌ 不通过 | ITERATIVE_APPLY 兜底掩盖合成/指数/分类/时序/多源叠加差异 |
| `c74fe277` | 15 | RASTER→TEMPORAL→AGGREGATION | ❌ 不通过 | AGGREGATION 混合时间合成/区域归约/分组统计/阈值估计/元数据提取 |

### 跨组系统性结论

1. **四组共享蓝图的共同缺陷**：折叠后保留的操作家族数（3–4 个）远低于任务实际需要的操作多样性——这不是个别映射错误，而是折叠规则的系统性设计问题；
2. **AGGREGATION 语义过载**：影像合成、区域归约、分组统计、阈值估计、元数据提取被统一归为一个阶段类别——需要拆分为更细的子类别；
3. **阶段顺序问题**：AGGREGATION 排在 RASTER_LOAD 前（abeef159 组），违背处理依赖；
4. **ITERATIVE_APPLY 兜底效应**：逐景 map() 被统一归为 ITERATIVE_APPLY，掩盖了合成策略、指数计算和分类等下游差异。

### 对蓝图生成管线修复的指向

| 修复方向 | 具体内容 |
|---|---|
| 保留全部算子家族序列 | 折叠时不应仅保留匹配模板的子集 |
| 新增折叠终止条件 | 操作多样性不足以区分已绑定任务时停止折叠 |
| AGGREGATION 拆分子类别 | 时间合成 / 区域归约 / 分组统计 / 阈值估计分开表示 |
| ITERATIVE_APPLY 语义拆分 | 区分逐景 map() / 并行分支 / 状态迭代 |
| 阶段顺序校验 | 输出前检查 AGGREGATION 是否出现在数据加载前 |

### 统计影响

96 行（四组总行数）的高风险蓝图确认：这些行的监督信号存在系统性质量缺陷。修复管线后重生成数据是必要的。
