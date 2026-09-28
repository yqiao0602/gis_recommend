# 《强化学习在 GIS 工作流自动生成中的应用调研》大纲 v1

日期：2026-09-18
状态：**填充中**。裁定已锁定：D1=参数奖励排除 L3 主体（路线 C 展望）、D2=QGIS Environment 长期展望、D3=经典谱系带过、D4=报告留现目录。填充顺序=方案甲（4→5→2→3→6→7→8→9→1）。
进度：第 4 章**风格定稿 v2**（2026-09-20，`survey_ch04_v2.md` + `survey_ch04_v2.docx`）：全章拆除【】批注块改为叙事体，依据织入引注、假设以"工作假设"显式声明，lint PASS；样式约定写入章首"行文约定"，后续各章照此执行。第 5 章**初稿完成**（2026-09-20，`survey_ch05_v1.md` + `.docx`）：三原则（可验证优先/结构一票否决/主干单一塑形审慎）→ 八维度盘点表 → 候选奖励函数（veto + α·setF1 + (1−α)·feas）→ 奖励与评测契约分流表 → 核心问题②裁定"成立，有边界"，lint PASS。待办：第 5 章**初稿完成**（2026-09-20，`survey_ch05_v1.md` + `.docx`）；第 2 章**初稿完成**（2026-09-20，`survey_ch02_v1.md` + `.docx`：NDVI 贯穿例、最小术语表、SL/RL 两点本质区别、经典谱系速览照 D3 带过）；第 3 章**初稿完成**（2026-09-20，`survey_ch03_v1.md` + `.docx`：rollout/KL 词汇、RLHF-RLAIF-RLVR 信号光谱、八方法对比表、GRPO 三补丁表、开源生态表与 TRL 选型、RFT 小节=路线 B 理论基础）；第 6 章**初稿完成**（2026-09-20，`survey_ch06_v1.md` + `.docx`：挂载点回路图、三路线×六档映射表、与冻结矩阵关系及 M1-R2 触发的立项时序）；第 7 章**初稿完成**（2026-09-20，`survey_ch07_v1.md` + `.docx`：三原则预期校准/冷启动先行/单变量推进、B0+E1-E5 实验矩阵、数据纪律含 RL holdout 400、指标映射表+首错分叉位置分布+双仪表盘、四级规模阶梯与门禁）；第 8 章**初稿完成**（2026-09-20，`survey_ch08_v1.md` + `.docx`：12 条难点三分组（奖励侧 5/学习侧 4/治理侧 3），每条配首选缓解与残余风险，总表+不对称结论）；第 9 章**初稿完成**（2026-09-20，`survey_ch09_v1.md` + `.docx`：三问三答、RL 解决什么（三靶点）与不解决什么（数据侧根问题）、最终定位句、RLVR-P0 协议冻结为下一步+报告边界声明）；第 1 章**初稿完成**（2026-09-20，`survey_ch01_v1.md` + `.docx`：问题定义与语义层/实例化层架构、三条模型路线正式定义（自研轻量模型/领域适配基座/直接微调基座）、四类局限实证、RL 动机与校准预期、阅读导览与全文行文约定）。

**2026-09-20 全文口径清洗（owner 裁定）**：调研为第三方读者文档，内部代号全部移除——M1/M2/M3 → 自研轻量模型/领域适配基座/直接微调基座；L3 → 语义层；taxonomy 文件名/normalized-DAG 键 → 描述性表述；六档方案映射列删除；RLVR-P0 等流水号不出现；学习历程（十站日志）不进正文（仅存 learning_journal.md）。涉及 ch01/02/04/05/06/07/08/09 已全部清洗并重出 docx，残留检查为零（ch04_v1 为风格改造前存档，不清洗）。

**九章全部完成 + 全文合并完成（2026-09-20）**：`survey_full_v1.md` + `survey_full_v1.docx`（YAML 标题元数据 + pandoc TOC，13 表 234 段）；一致性终检通过——章引用 1-9 全有效、节引用零缺失、术语统一（"成熟基座"→直接微调基座、veto 门→否决门，源章与合并稿同步修正）。全文 lint PASS。
定位：毕设导向的调研报告（区别于 `report_v2.md` 的内部决策报告；本文以第三方读者/答辩委员会为受众写作）。
**核心问题（全文锚点）**：
> 强化学习能否解决 GIS 工作流生成中"算子链组合强依赖、多解皆合理、单步错误传播影响后续"的问题？——具体拆为两问：① GIS 工作流能否被形式化为 RL 的 MDP（带诚实简化的声明）；② Reward 能否可靠评价一条工作流。两者成立后，算法选择（PPO/GRPO/DPO）是第二层问题。

---

## 第 1 章 研究背景
**目的**：让读者三段式理解"问题→现有方法→为什么不够"。
- 1.1 GIS 工作流自动生成问题（NL → L3 语义链 → QGIS 落地；三路线架构）
- 1.2 现有监督方法的局限（CE 单参考监督、teacher forcing/exposure bias、多解 gold、EOS/序列控制、task_type conditioning——**用本项目实证**：M1-R1 塌缩、M3-P1 截断 42/49 前缀对但 0/49 exact）
- 1.3 为什么考虑 RL（training_contract 原文引证："ranking_is_post_training_not_a_training_objective"；定位句：**监督学习学"怎么生成"，RL 学"什么是好的"**）
素材：report_v2 §1、学习日志第 0/3 站 ｜ 新做：三路线结论压缩为背景叙述（不翻案）

## 第 2 章 强化学习基础（面向读者，非教程堆砌）
**目的**：给答辩读者最小必要概念集，全部用 GIS 例子贯穿。
- 2.1 MDP 五要素（NDVI 任务贯穿例：任务文本+空链=S0 → 选 Load_Raster → S1 → … → EOS → Reward）
- 2.2 术语表：policy / value / Q / episode / trajectory / return
- 2.3 RL 与 SL 的本质区别（逐位置答案 vs 轨迹级分数 → credit assignment 问题）
- 2.4 经典谱系速览（Q-Learning → REINFORCE → Actor-Critic → PPO 一节带过；LLM 时代分野：RLVR / Agentic RL）【深度见校准点 D3】
素材：学习日志第 0/1/4 站、族谱笔记 ｜ 新做：从教学口吻改写为第三方视角

## 第 3 章 RL 在序列生成中的应用
**目的**：把通用 RL 接到"文本→结构化序列生成"上。
- 3.1 序列生成的 RL 形式化（token 级决策链；exposure bias 作为 RL 动机）
- 3.2 RLHF / RLAIF / 偏好优化版图（RM 路线 vs 规则可验证路线）
- 3.3 方法对比表（大纲维度照用：需要 RM 吗 / 需要环境吗 / 适合离散序列吗 / 训练成本 / 适合 GIS workflow 吗；行：Q-Learning、Policy Gradient、Actor-Critic、PPO、DPO、GRPO、**Rejection Sampling/RFT【新增，路线 B 理论基础】**、Reward Model）
- 3.4 2024–2026 进展与开源生态（RLVR、GRPO、DAPO/GSPO、Agentic RL；verl/OpenRLHF/TRL/AReaL）
素材：族谱笔记、report_v2 §2/§6 ｜ 新做：对比表填格；RFT 小节新写

## 第 4 章 GIS 工作流生成的 RL 问题建模 ★核心原创章
**目的**：回答核心问题①。这是全文最有新意的一章。
- 4.1 形式化为 MDP：
  - State = 任务文本 + 已生成 L3 前缀（**讨论点**：中间数据类型是否入 State——现架构未显式跟踪，推理期由 KG io_factor 代理）
  - Action = 132 L3 词表上的下一 token
  - Transition = 确定性 append（无环境随机性——对照 Agentic RL 的区别）
  - Terminal = EOS；Episode = 一条完整链
- 4.2 形式化与真实工作流的差距（诚实声明）：参数未建模（L3 层 parameter-free by design）、分支/并行被序列化（V4 不消费边）——这些简化是局限还是贡献点，两面写
- 4.3 三个特征的吸收方式：强依赖=序列决策天然表达；多解=部分匹配 reward（set_f1）；错误传播=on-policy 训练分布匹配**缓解** exposure bias（措辞注意：缓解，非解决）
素材：学习日志第 4 站、report_v2 §5 ｜ 新做：全部新写

## 第 5 章 GIS Workflow 的 Reward 设计 ★核心原创章
**目的**：回答核心问题②。
- 5.1 设计原则：可验证优先（RLVR）、veto 分层（ComfyUI-R1 实证）、防 phantom advantage（2609.13866）
- 5.2 奖励维度盘点（对照项目资产，标注现成/需做/超范围）：

| 维度 | 内容 | 项目资产状态 |
|---|---|---|
| 合法性门 | 词表合法 / DAG 合法 | ✅ 现成 |
| 正确性 | set_f1 vs gold | ✅ 现成 |
| 落地性 | executable / qgis_mapping（bridge+I/O 契约） | ✅ 现成 |
| 步级过程奖励 | ChainValidator / io_factor / mapping confidence | ✅ 资产现成，用法需设计 |
| 任务完成度（多解） | 多解等价类 / structural agreement | 🔶 需新做（RobustFlow 思路） |
| 执行奖励 | 真实 QGIS 执行成功 | ❌ 不存在，Phase 3+（与数据飞轮绑定） |
| 参数合法性 | buffer distance 等 | ⚠️ **范围裁定 D1**：benchmark 纪律明确 parameter-free，L3 层不适用 |

- 5.3 组合方式：veto 硬门 + 连续主干（set_f1）+ 可选 shaping（必须单独消融）
- 5.4 Reward 与 metric contract 的关系（同源不同用：训练信号 vs 评测口径）
素材：ComfyUI-R1 笔记、report_v2 §7/§8 ｜ 新做：盘点表落格 + 裁定 D1 后成文

## 第 6 章 RL 与当前模型路线的结合
**目的**：从"别人的 RL"落回"我们的系统"。
- 6.1 挂载点图（GIS Model → Operator Chain → Reward 三维评审 → RL Training → 更好模型；GEE 监督与 QGIS 落地的角色标注）
- 6.2 三条路线（大纲原框架 × 我们六档方案映射）：
  - **路线 A**：SFT → RL（GRPO/DPO）＝ 档 1/2（M1-DPO、M3-GRPO）
  - **路线 B**：SFT + 奖励筛选（RFT/rejection sampling）＝ 档 4/6b 数据飞轮——**最易落地，零件全现成**
  - **路线 C**：QGIS 执行环境作 Environment（agentic）＝ 档 5/6a-6c——长期展望【定位见校准点 D2】
- 6.3 与 M1/M2/M3 冻结矩阵的关系（不翻案；RL=post-training 增量实验；挂线决策等 M1-R2 final-100）
素材：report_v2 §3/§8 ｜ 新做：挂载图 + 路线映射表

## 第 7 章 实验方案设计
**目的**：给出可执行（且合规）的实验矩阵。
- 7.1 基线：冻结 M 臂（M3-SFT/C0/P2-T1）
- 7.2 实验矩阵：SFT（已有）→ +RFT → +DPO（M1）→ +GRPO（M3）→ reward 消融
- 7.3 数据纪律：train-only；RL holdout ~400 从 train 划；val 只报告；final-100 prediction lock 一次开启
- 7.4 指标：四元 primary（set_f1/usable/executable/qgis_mapping）+ 首错位置分布 + 训练健康盘（KL/熵/零梯度组占比）
- 7.5 规模阶梯：smoke(100) → 小步试跑 → 冻结协议
素材：report_v2 §8/§10 ｜ 新做：矩阵表（大纲原指标名映射到 contract 术语）

## 第 8 现有问题与研究难点
**目的**：诚实清单，每条配缓解方向。
多解评价 / 零梯度组 / reward hacking / 长程 credit assignment / 稀疏 reward / QGIS 执行成本 / reward 可靠性 / GEE→QGIS 跨平台语义差 / exposure bias 缓解边界 / task_type conditioning
素材：report_v2 §8.2 + 学习日志 ｜ 新做：整合重写（mostly 已有）

## 第 9 章 对本课题的启示
**目的**：结论章——直接回答核心问题，不做"RL 很有前景"式空话。
- 9.1 三问三答：① MDP 形式化成立（带简化声明）② reward 分层可验证成立（执行级留长期）③ 算法选择是第二层问题（按基础设施与目标定：GRPO/DPO/RFT）
- 9.2 定位句收束：SL 学"怎么生成" + RL 学"什么是好的" → 生成-评价-优化-执行闭环
- 9.3 下一步：RLVR-P0 协议（等 M1-R2 final-100 裁决后立项）
素材：全部 ｜ 新做：立场写作

---

## 填充顺序建议

**方案甲（推荐）**：第 4 → 5 章（原创核心先立，其余章节都能引用它们）→ 第 2 → 3 章（素材最全，快）→ 第 6 → 7 → 8 章 → 第 9 章（结论最后收口）→ 第 1 章（背景最后写，视角最准）。
**方案乙**：按 1→9 顺序线性填充，适合喜欢顺序感的写法。

## 待 owner 裁定的校准点

- **D1 参数合法性奖励**：贴来的大纲含"参数 Reward"，但项目 benchmark 纪律明确 **parameter-free**（L3 层无参数）。建议：L3 层明确排除并写成"范围声明"；参数层只在第 6 章路线 C（QGIS 落地）作为展望提及。
- **D2 路线 C（QGIS 作 Environment）定位**：建议写成长期展望（有理论自然性、无基础设施），不做本轮承诺；避免答辩被问"你执行环境呢"。
- **D3 经典谱系深度**：Q-Learning/Actor-Critic 建议 2.4 一节带过 + 对比表占一行（LLM 时代它们只是 lineage）；若答辩委员会偏传统 RL，可扩为半节。
- **D4 归宿**：本大纲与正文先放 `rl_integration_scan_v1/`（与素材同处）；成稿后若作毕设章节再迁移。亦可现在就建 `docs/surveys/rl_gis_workflow_survey/`。

## 素材资产索引

| 资产 | 位置 | 服务的章 |
|---|---|---|
| 整合调研 report_v2 | 本目录 report_v2.md | 全部 |
| ComfyUI-R1 精读 | comfyui_r1_reading_notes.md | 3/5/7 |
| 算法族谱理论参考 | rl_algorithm_genealogy_notes.md | 2/3 |
| 学习日志（10 站+指标站） | learning_journal.md | 2/4 素材与口吻参考 |
| 16 篇 PDF | papers/ | 3/4/5 |
| 内部决策材料 | report_v2 §8/§10（六档/风险/决策点） | 6/7/8/9 |
