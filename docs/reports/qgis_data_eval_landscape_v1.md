# QGIS 数据与评测资源全景调研 v1

日期：2026-09-18
性质：**综合整理报告**（只读调研；未消费任何外部数据；训练行 0；authority/评测/checkpoint 未修改）。
整合来源：`docs/reports/external_gis_training_data_survey_v1.md`（GIS 专用数据，2026-09-16）、
`docs/reports/external_gis_training_data_survey_v2.md`（通用工具链文献与方法，2026-09-17）、
内部锁定状态（实验账本、benchmark freeze 记录、三路线收束结论）。
本报告新增整理的维度是**评测资源对比**——v1/v2 以数据为主线，评测只在条目内附带；§4 为新整理内容，§5-§6 为综合分析，其余为索引性摘要（细节以 v1/v2 为准）。

## 0. 一页结论

1. **数据**：外部不存在"NL 意图 → QGIS 算子 DAG"训练集（HF + 学术双空白）。主料 = 内部 25.7 万脚本描述库 + GEE 44,220 行转化资产；外部三源（GeoAnalystBench / AutoGEEval-plus / GISAgentBench）合计 ≈1,800 条意图式样本，只能当配菜（OOD 评测 / few-shot 种子 / 引用）。
2. **评测**：benchmark v0.2.1 占据一个**独特的生态位**——已知唯一以"结构化算子 DAG"（而非代码或轨迹）为输出空间的 GIS 评测、唯一带 refusal diagnostic 与 unsafe-planning 指标、唯一 prediction-lock + 冻结 scorer 纪律。但三个外部标杆各有我们没有的东西：**执行级 ground truth**（GISAgentBench）、**规模**（AutoGEEval++ 6,365 用例）、**动态执行沙盒**（GeoAgentBench）。
3. **评测方法学分野**：静态匹配（我们、WorfBench、GeoAnalystBench）vs 执行验证（AutoGEEval、GISAgentBench、GeoAgentBench）vs LLM judge（被 GISAgentBench 作者点名批评会混淆"形似"与"做对"）。我们的 parameter-free 设计天然放弃了执行验证——这是可移植性的代价，也是 v0.3 最值得讨论的升级方向（§5.3-a）。
4. **对齐问题要分侧说**：benchmark 本身已是意图式（人工任务文本 + 人工 gold DAG），错位在**训练侧**（GEE 8,201 行 100% answer-echo vs 意图式 benchmark）。所以修的是训练数据，不是评测；评测侧真正的短板是**规模与执行验证**，不是任务形态。

## 1. 价值判断框架

数据侧（v1 提出，沿用）：
- **D1**：NL 意图 → 算子链/DAG 配对监督（直接对口第一约束）
- **D2**：QGIS 侧多步 DAG 监督
- **D3**：GEE↔QGIS 跨平台算子映射

评测侧（本报告新增）：
- **E1**：任务形态可分离——评测任务必须是意图式（输入不得泄漏答案算子）
- **E2**：协议可对话——operator/DAG 级指标、可复现（lock/checksum）、license 或授权可得

## 2. 内部现状速览（全部为锁定账本数字）

### 2.1 数据底盘

| 资产 | 规模 | 状态 |
|---|---|---|
| paper_v1 v2 manifest | 8,912 行（GEE 8,283 + QGIS 629）；train 8,817 / val 49 / test 46 | 已冻结；source-disjoint 8,797 身份、跨 split 0 重叠 |
| GEE 脚本描述库 | 257,101 脚本（含 Task Type/Name/Description） | 已定位并哈希验证；paper_v2 意图重写主料 |
| GEE 描述×链转化资产 | 44,220 行可用（99.96% canonical 覆盖） | 转化闸门通过并全量完成；四臂实验 C0/A1/B1/B2 定案 |
| QGIS 训练池 | 629 行（GOLD 52 / SILVER 454 / PATTERN 120 / STANDALONE 3） | 已并入 paper_v1 train；扩产 fail-closed 上限 ~700-800（方案 A 封死） |

**形态问题清单**（诊断已锁定）：GEE 100% answer-echo（算子全列在输入里）；QGIS 44% 算子点名；25.2% 训练行含连续重复（最长 60 连）；QGIS 监督 81.7% 中文/混合；L3 桥 78/128 无桥、32/50 多候选代表失配；benchmark 有 branch/merge 图而自回归模型只能出线性链（edge F1 ≤0.076 的根因之一）。

### 2.2 benchmark v0.2.1 结构

- 构成：final 100（+1 audited increment，6006e49 冻结、c515c77 并 main）+ dev + refusal 12（4 intents × 3 变体：6 unsupported_capability + 6 underspecified_goal）。
- gold：**parameter-free QGIS 算子 DAG**（`processes + links`，operator_id 如 `native:*`）——gold 与指标中没有任何 L3 code，L3 只在模型侧。
- 拓扑覆盖：pure_branch / hybrid / multi_input_merge（算子图层面）。
- 纪律：prediction lock → 冻结 scorer；指标 = operator 多重集 micro PRF、(source_op, target_op) 边 PRF、带标签有向图同构 EM（防重复算子时链/星混淆）、dependency closure、harmful extra operator、false refusal；refusal 侧 accuracy / reason-code accuracy / unsafe-planning rate。

### 2.3 三路线锁定成绩（final-100 operator F1）

| 路线 | 成绩 | 一句话定性 |
|---|---|---|
| M1-R1（scratch V4.6） | 0.0047 | 无预训练小模型 OOD 塌缩（88 空图、100/100 Define Projection 开头） |
| M1-R2（+decoder DAPT） | 0.0857（×18） | 修复"生成什么样的序列"，未修复"根据语义生成哪一条"（条件映射） |
| M3-P1（post-trained+朴素 SFT） | 0.1605 | 能选对、停不下（runaway） |
| M3-P2-T1（+EOS 加权） | 0.1991 | 训练层干预部分成功，距后处理上限 0.2838 尚差 0.08 |
| **M2-C0（Base+plain SFT）** | **0.2236（全场最优）** | "什么都不加"就是当前最好配方 |
| M2-P2（+DAPT） | 0.1610 | 代码 DAPT 净效应 −28%，方向分裂 |

共同约束：recall 卡 0.21-0.27；edge F1 ≤0.076；所有路线 always-plan（refusal_accuracy=0、unsafe_planning 12/12）。**定性：数据形态是第一约束（约束 recall）；修好后约束转移到架构层（拓扑表达、桥接方式、拒答设计）。**

## 3. 外部数据资源全景（v1+v2 摘要）

### 3.1 GIS 专用数据（细节见 v1 §一）

| 级别 | 资源 | 要点 |
|---|---|---|
| 🟢 立即可用 | **GeoAnalystBench**（Apache-2.0） | 50 任务×3-10 子任务，NL+人工工作流+参考代码（ArcPy 生态）；唯一 license 干净的意图式数据 |
| 🟢 立即可用 | **GEE-Ops/Geo-SORB**（无 license，数据已公开） | 18.5 万脚本挖的算子链/频繁模式；平行工作，引用+对比 |
| 🟡 需联系作者 | **AutoGEEval-plus** | 2,612 用例 NL→GEE Python code（原子 1,325/组合 1,199/场景 88）；GEE→L3 映射内部已有，可机械转化 |
| 🟡 需联系作者 | **GISAgentBench** | 349 任务全部来自 GIS Stack Exchange + 可执行轨迹 + 精确 GT；仓库未公开 |
| 🔵 参考 | GIS Copilot、GeoAgentBench、GeoNatureAgent、QGIS Hub（仅 30 个 .model3）、GeoScience-QGIS-CUA（不适用） | 评测范式/工具文档/种子级价值 |

五大约束匹配结论（v1 §二）：外部能补①任务形态错位的一部分（~1,800 条）与⑤长尾的 GEE 侧；②部分间接；③桥接、④拓扑**无外部解**。

### 3.2 通用工具链数据（细节见 v2 §一）

TaskBench（Tool Graph + back-instruct）、WorkflowLLM/WorkflowBench（106,763 样本，真实工作流→转录→重写→验证）、ToolBench（16,464 APIs/126,486 指令，Apache-2.0）、APIGen/xLAM（三段验证合成）、Gorilla/BFCL、WorfBench（subgraph 评测）。
**判定**：域不重叠，不作训练主粮；价值 = 重写管线方法蓝本 + few-shot 格式校准 + related work 锚点。

### 3.3 方法与机制文献（细节见 v2 §二/§三/§五）

意图合成配方（back-instruct / WorkflowLLM 三阶段 / APIGen 三段验证 / Self-Instruct / Evol-Instruct / Magpie / PersonaHub）；DAPT 先例对照（K2、GeoGalactica 正面 vs M2 负结果，差异在任务形态）；经典语义地理处理谱系（geooperator 形式化 2015、服务链语义组合 2006、"Finding and sharing GIS methods based on the questions they answer" 2018）；机制挂靠（shortcut learning 2208.11857 ↔ echo→copy；constrained decoding ↔ V2a 硬约束教训）。

## 4. 外部评测资源全景（本报告新整理）

### 4.1 GIS 专用 benchmark 对比

| Benchmark | 任务形态 | 输出空间 | 评测方式 | 规模 | 可得性 | 与 v0.2.1 的关系 |
|---|---|---|---|---|---|---|
| **本项目 v0.2.1** | 意图式 NL 任务（人工撰写+审计） | **parameter-free 算子 DAG** | 冻结 scorer 静态匹配（operator/边 PRF + 图同构 EM + refusal 三指标） | 100 final + dev + 12 refusal | 内部 sealed | — |
| **GeoAnalystBench** (2509.05881) | 意图式 NL 真实任务 | Python 工作流 + 代码 | workflow validity + 结构对齐 + 语义相似 + CodeBLEU | 50 任务（×3-10 子任务） | Apache-2.0 ✓ | **可立即作跨域意图式 OOD dev**；其"minimum deliverable"思路可借鉴 |
| **AutoGEEval / ++** (2505.12900 / 2506.10365) | NL + API 文档 | GEE Python 代码 | **执行验证**（pass@k、错误分类、资源消耗） | 1,325 / 论文 6,365（repo README 可见 2,612） | 无 license | GEE 侧最大执行式评测；组合/场景级用例 = 可转化意图源 |
| **GISAgentBench** (2608.01645) | 实践者真实任务（Stack Exchange） | 128 类型化 API 调用序列（**~2/3 为 QGIS processing 算子**，qgis_process 分发；全文核验 09-22） | **执行 + GT 输出文件**容差匹配（明确拒绝 surrogate/judge）；轨迹对比仅诊断 | 349 | 论文 CC BY；仓库未公开 | 评测哲学最接近我们（反对形似指标）；GT 执行输出是独有优势；**动作空间与我们的算子层同构** |
| **GeoAgentBench** (2604.13888) | 空间分析任务 | 工具调用序列 | **动态执行沙盒** + PEA（参数执行准确率） | 53 任务/117 工具/6 域 | 摘要核验 | 沙盒+参数维度是我们没有的 |
| **GeoNatureAgent** (2606.12821) | 环境分析任务 | 生产 API 结构化调用 | API 执行 | 93 任务/16 工具 | 摘要核验 | "结构化工具调用比通用评测低 25-35 分"——与我们"规划 vs 代码"分离的观察同向 |
| **GIS Copilot** (2411.03205) | NL 命令（3 复杂度级） | QGIS 内代码/工作流 | 执行+人工（100+ 任务） | 100+ | 未见公开仓库 | QGIS 原生工具文档与内部 KG 互补 |
| **GeoCode-Eval** (2410.09738) | 知识考核 | 选择/填空/判断/主观 | 静态判分 | 9,000 题 | 摘要核验 | 与规划评测互补性低 |

### 4.2 通用 benchmark（细节见 v2 §一）

| Benchmark | 输出空间 | 评测方式 | 对我们的用途 |
|---|---|---|---|
| TaskBench (2311.18760) | Tool Graph（分解+选择+参数三阶段） | TaskEval 多维 | Tool Graph 与我们 DAG 评测同构；back-instruct 方法 |
| WorfBench (2410.07869) | 图结构工作流 | **WorfEval：子序列+子图匹配** | 与我们边 PRF/图同构 EM 相互校验的外部参照 |
| BFCL V1-V4 (Gorilla, Apache-2.0) | 函数调用 | V3 多轮状态、V4 agent（错误恢复/记忆） | 未来多轮/错误恢复维度的设计参照 |
| WorkflowBench (WorkflowLLM) | Python 代码（AST 树/DAG） | —（数据中心，非评测主线） | 106k 级重写管线的规模化先例 |

### 4.3 评测方法学谱系（三层 + 参数维度）

**三层**：
1. **静态匹配**：operator/边多重集 PRF（我们）、CodeBLEU（GeoAnalystBench）、子图匹配（WorfBench）、结构对齐。优点：可复现、零基础设施；缺点：GISAgentBench 作者的核心批评——**"surrogate signals（代码相似、轨迹匹配、LLM/VLM judge）会混淆工作流形似与任务正确性"**。
2. **执行验证**：AutoGEEval（pass@k）、GISAgentBench（GT 输出文件+容差）、GeoAgentBench（沙盒 PEA）。金标准，但需要每任务数据+沙盒+GT 构造成本。
3. **LLM/VLM judge**：最弱，已被点名批评，我们不采用（与 lock 纪律一致）。

**参数维度**（我们的关键设计取舍）：我们选 parameter-free gold——换来平台可移植、gold 可人工审计、评测零执行基础设施；代价是**语义正确性只能靠图匹配代理**，执行才能暴露的错误（参数语义、数据类型不匹配）不可见。外部执行式评测全部带参数/数据。这是光谱两端，不是谁对谁错。

## 5. 对照定位

### 5.1 v0.2.1 的独特性（论文可声明的评测贡献）

1. **输出空间隔离**：唯一评"结构化算子 DAG"而非代码/轨迹的 GIS 评测——把**规划能力**从**代码能力**里剥出来（外部 GIS benchmark 全部混在一起评）。
2. **refusal diagnostic + unsafe-planning 指标**：外部 GIS benchmark 无一测量拒答/危险规划；我们 12 条四类 intent。
3. **lock 纪律**：prediction lock + checksum + 冻结 scorer——可复现性档次不同（我们的所有分数可精确复现，如 M3 块重评分 0.1605 精确复现）。
4. **拓扑分级 gold**：pure_branch/hybrid/multi_input_merge 的 DAG 级覆盖（外部多为线性链）。
5. **gold 质量**：人工双语审计 + primary/blind secondary review + source-backed DAG。

### 5.2 外部标杆暴露的三个差距

1. **无执行证据**（GISAgentBench 模式）：我们的 F1 无法区分"图对但语义错"与"真做对"。
2. **规模**（100 vs AutoGEEval++ 千级）：质量优先策略的代价；单任务人工成本高，扩容需靠重写管线+人工金标小批注入。
3. **静态单轮**（对比 BFCL V4 / GeoAgentBench 的多轮、错误恢复、状态跟踪）：我们测的是一次性规划。

### 5.3 benchmark v0.3 候选方向（**全部未批准，需 owner 裁定**）

| 候选 | 内容 | 成本 | 依据 |
|---|---|---|---|
| a. 执行增强层 | 对 final-100 抽样子集：catalog 默认参数自动填参 → 服务器 QGIS 沙盒跑 gold 生成执行 GT → 跑预测比对输出（"图匹配为主 + 抽样执行校验"两层） | 中（每任务填参+沙盒） | 把 parameter-free 的可移植性与执行的保真度分层兼得；直接回应 §5.2-1 |
| b. 规模扩充 | 四臂重写管线产物中，人工金标一小批**新增** DAG（与训练数据 source-disjoint）→ dev/secondary 扩容 | 高（人工） | 意图重写管线就绪后顺路产出 |
| c. 拓扑细分报告 | 现有预测+gold 按三拓扑分层重算 edge F1/operator F1——纯后处理计算，不新增任务 | 低 | edge F1 ≤0.076 的归因（线性链 vs branch/merge）目前只有总量级证据 |
| d. refusal 扩容 | 12 → ~50（按 capability matrix 逐格铺设） | 中 | 所有路线 refusal_accuracy=0，当前 12 条只够定性 |

## 6. 数据-评测对齐：问题到底在哪一侧

| 组件 | 任务形态 | 判定 |
|---|---|---|
| benchmark v0.2.1 任务文本 | 意图式（人工写，无算子泄漏，有泄漏审计） | ✅ 已经是对的 |
| GEE 训练行（8,201/8,283） | **100% answer-echo** | ❌ 最大错位项——修法 = 四臂意图重写（方法锚点：back-instruct / WorkflowLLM 三阶段 / APIGen 三段验证） |
| QGIS 训练行（629） | 44% 算子点名；81.7% 中文 | ⚠️ 次要错位 + 语言错配（"522 行中文英文化"增广 + 120 条 docstring 清洗待权衡） |
| 评测侧短板 | — | 不是任务形态，是**规模**与**执行验证**（§5.2/§5.3） |

外部资源在两侧的角色：数据侧 = OOD 评测 + few-shot 种子 + 引用（§3）；评测侧 = 方法学校准（WorfBench 子图匹配 ↔ 我们的边 PRF/EM；GISAgentBench 的"拒绝 surrogate"立场与我们 lock 纪律同向）+ v0.3 执行层的设计参照（GeoAnalystBench minimum deliverable / GISAgentBench GT 文件容差匹配）。

## 7. 行动建议（未批准，按优先级）

| P | 动作 | 侧 |
|---|---|---|
| P0 | 四臂意图重写实验（已有设计；方法文献锚点见 §3.3） | 数据 |
| P1 | 克隆审计 GeoAnalystBench（Apache-2.0）→ 接入跨域意图式 OOD dev | 评测（零风险增量） |
| P2 | 邮件联系 AutoGEEval-plus 作者（license）+ 从 GISAgentBench PDF 找仓库/联系作者 | 数据 |
| P3 | benchmark v0.3-c 拓扑细分报告（纯后处理，随时可做）；然后 v0.3-a 执行增强层 10 条试点讨论 | 评测 |
| P4 | refusal 扩容设计（12→50，capability matrix 驱动） | 评测 |
| 暂缓 | GitHub 全量 .model3/PyQGIS 爬取（内部 47,852 池已覆盖，边际低）；CNKI 中文文献线（需 CDP，可另开） | — |

## 8. 来源

合并自 v1/v2 报告来源列表，新增无独立来源（§4-§5 为已有核验材料的综合分析）。
关键锚点：[GeoAnalystBench](https://github.com/GeoDS/GeoAnalystBench) · [AutoGEEval++](https://arxiv.org/abs/2506.10365) · [GISAgentBench](https://arxiv.org/abs/2608.01645) · [GeoAgentBench](https://arxiv.org/abs/2604.13888) · [GeoNatureAgent](https://arxiv.org/abs/2606.12821) · [GIS Copilot](https://arxiv.org/abs/2411.03205) · [TaskBench](https://arxiv.org/abs/2311.18760) · [WorkflowLLM](https://arxiv.org/abs/2411.05451) · [ToolBench](https://github.com/OpenBMB/ToolBench) · [APIGen](https://arxiv.org/abs/2406.18518) · [Gorilla/BFCL](https://github.com/ShishirPatil/gorilla) · [WorfBench](https://arxiv.org/abs/2410.07869) · [K2](https://arxiv.org/abs/2306.05064) · [Shortcut Learning of LLMs](https://arxiv.org/abs/2208.11857)
