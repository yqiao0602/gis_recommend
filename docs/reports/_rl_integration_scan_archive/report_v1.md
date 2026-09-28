# RL 结合初步调研报告（rl_integration_scan_v1）

日期：2026-09-16
状态：初步扫描（first-pass scan）。仅为文献/生态调研与整合点假设，未精读、未做任何工程或实验决策，不改动任何冻结矩阵（M1-R1 / M2 三臂 / M3 收束结论均不翻案）。
方法：academic-search skill（arXiv REST API + OpenAlex；Semantic Scholar 无 Key 触发 429 降级）+ WebSearch（框架生态）。16 篇核心 PDF 已存 `papers/`，全部为 arXiv 合法开放获取。

## 1. RL 进展主线（2024–2026）

演化脉络：**RLHF/PPO → DPO 系直接对齐 → RLVR（可验证奖励 + GRPO，DeepSeek-R1 路线）→ Agentic RL（长程、多轮、真实环境）**。

- **Agentic RL 综述**（2509.02547, v5）：把 LLM-RL 形式化为退化的单步 MDP，把 Agentic RL 形式化为时序扩展的 POMDP，提出双分类法（模型/环境两条轴）。当前社区共识框架。
- **GRPO 已成为小规模/垂直领域标配**：无 critic、组内相对基线， Urban-R1、GeoX、GeoZero、ComfyUI-R1 等均采用 GRPO 或可验证奖励范式。对我们 A10-23GB 级别的算力尤其友好。
- **过程奖励（PRM）/密集奖励**：GeoSolver 构建 Geo-PRM-2M 做 token 级过程监督；DRACO 做长程细粒度 credit assignment。
- **训练稳定性研究活跃**：RTPO（稳定 agentic RL）、GCPO（rollout RL 子空间几何约束）、Elastic Horizon（交互边界发现）。
- **Reward hacking 警示**：Group-Relative RL 在 shaped reward 下会产生 phantom advantages（2609.13866）；RL agent 会学到错误的工具触发原因（Spurious Tool Use, 2609.16268）。
- **开源框架生态**：verl（ByteDance，当前主流大规模 RLHF/RLVR 框架）、OpenRLHF（Ray+DeepSpeed+vLLM，成熟）、**TRL（HF，GRPOTrainer 开箱即用，最适合我们的小规模研究场景）**、AReaL（异步架构，新）。

## 2. 文献清单（16 篇已存 papers/，按相关度分四类）

### A 类：Workflow / 算子图生成（与我们任务同构：NL → 算子 DAG）

| 论文 | arXiv | venue | 关键相关点 |
|---|---|---|---|
| ComfyUI-R1: Exploring Reasoning Models for Workflow Generation | 2506.09790 | ACL 2026 Findings | **首个 workflow 生成推理模型**。4K 工作流数据 → 长 CoT（节点选择→工作流规划→代码）→ 训练。与我们"NL 任务→L3 算子链"最同构 |
| AFlow: Automating Agentic Workflow Generation | 2410.10762 | ICLR 2025 | MCTS 搜索代码空间表示的 workflow，执行反馈做奖励。工作流=可搜索程序空间 |
| A²Flow: Self-Adaptive Abstraction Operators | 2511.20693 | arXiv 2025-11 | 三阶段自适应算子提取，摆脱人工预定义算子——与我们"128 L3 词汇表是人工冻结权威"形成对照 |
| RobustFlow: Towards Robust Agentic Workflow Generation | 2509.21834 | arXiv 2025-09 | **偏好优化学语义不变性**：等价改写的指令 → 一致 workflow。直击我们 task_type conditioning 脆弱性（Phase 0-B 结论） |
| FlowScout: From Execution Feedback to Reliable Tool-Using Agent Workflows | 2608.10039 | arXiv 2026-08 | 真实工具执行反馈（vs LLM 模拟节点）构建 workflow。与我们的链修复（ChainValidator+GraphRAG）阶段同位 |
| Benchmarking Agentic Workflow Generation | 2410.07869 | arXiv v3 | ComfyBench 期刊版：workflow 生成评测方法论（可执行性判定）可参考 |

### B 类：Geo/地球科学 RL（领域最近邻）

| 论文 | arXiv | 关键相关点 |
|---|---|---|
| GeoX: Geospatial Reasoning Through Self-Play and Verifiable Rewards | 2605.20006 | 自博弈 + 可执行程序可验证奖励，**无需大规模人工标注**——对我们数据稀缺（8,817 行）的数据飞轮思路 |
| GeoZero: Incentivizing Reasoning from Scratch on Geospatial Scenes | 2511.22645 | 无 CoT 冷启动直接 RL，避开人工标注偏差 |
| Urban-R1: Reinforced MLLMs Mitigate Geospatial Biases | 2510.16555 | **GRPO 后训练对齐城市通用智能目标**——SFT 后残余 bias 用 RL 修，与我们 M3 SFT 后遗留问题的处置范式相同 |
| GeoSolver: Fine-Grained Process Supervision | 2603.09551 | Geo-PRM-2M 过程奖励模型；步级监督思想可用于我们的步级奖励（io_factor/ChainValidator） |
| Earth-Agent-Pro: Full-Chain Earth Observation with Agents | 2609.12533 | 全链路"科学问题→可执行工作流"，专家技能约束规划——与我们 L3 语义约束 + 落地边界同构 |

### C 类：工具使用 RL / 基础设施

| 论文 | arXiv | 关键相关点 |
|---|---|---|
| MCP-Universe RL: Training MCP Tool-Use Agents via RL | 2608.22167 | 开源框架：环境编排 + rollout 调度（数百并发轨迹、慢工具调用下的 GPU 利用率）——若做多轮工具调用 RL 的工程参照 |
| Learning to Use Tools: RL for Tool-Integrated Mathematical Reasoning | 2608.28447 | 端到端 RL 学工具调用序列（非 SFT 蒸馏） |

### D 类：风险警示

| 论文 | arXiv | 警示点 |
|---|---|---|
| Phantom Advantages in Group-Relative RL under Shaped Rewards | 2609.13866 | shaped reward（长度/格式类）下 GRPO 组相对优势是虚假的——对我们若用 length/EOS shaping 直接相关 |
| Spurious Tool Use: When RL Agents Learn the Wrong Reason to Act | 2609.16268 | RL 学到错误触发规律而非真实因果 |

另识别未下载：ComfyBench（CVPR 2025, 10.1109/cvpr52734.2025.02292）、ComfyGPT（2503.17671）、Knowledge-Centric Agents for Workflow Generation in ComfyUI（2607.15845）、"From Search to Synthesis: Training LLMs as Zero-Shot Workflow Generators"（2606.30704）、GraphPlanner（2604.23626）、GeoRisk-RAG（2608.22634）。

## 3. 与本系统的整合点假设（待 owner 决策，未启动）

### 3.1 我们的资产（RL 视角盘点）

1. **奖励天然可验证、零标注成本**：metric contract 主指标 set_f1 / usable / executable / qgis_mapping 全部是确定性计算（gold L3 链对比、Neo4j I/O 契约、bridge 映射）→ 这是 RLVR（可验证奖励强化学习）的标准前提，我们已天然具备。
2. **动作空间极小**：132 个 L3 token、链长 ~5–13、beam search 基础设施现成 → rollout 廉价，GRPO 组采样开销低。
3. **training_contract 已声明的已知限制，恰好都是 RL 的对症领域**：
   - "token_ce_is_single_reference_supervision"（单参考 CE）→ set_f1 部分匹配偏好对；
   - "ranking_is_post_training_not_a_training_objective"（ranking 是 post-training 目标）→ DPO/GRPO 正是 post-training ranking 优化；
   - "inference_beam_constraints_are_not_fully_mirrored_in_ar_sampling"→ RL 奖励直接对齐推理期行为。
4. **已量化痛点与文献一一对应**：task_type conditioning 崩塌（P 0.13→0）↔ RobustFlow；EOS/截断伪影（M3-P1 42/49 前缀正确但 0/49 exact）↔ RL 对终止行为的直接优化；数据稀缺 ↔ GeoX self-play 飞轮。

### 3.2 候选整合方案（按成本/风险递增排序）

1. **M1-DPO**（task_plan 已列"可选 DPO"，最小改动）：beam search top-k 候选 × composite score → 构造偏好对（best vs worst）→ DPO 微调自研 decoder。基础设施全部现成（beam、评分、checkpoint 管线）。
2. **M3/M2-GRPO（RLVR）**（对标 Urban-R1/GeoX/ComfyUI-R1）：TRL GRPOTrainer + Qwen-9B NF4+LoRA（A10 23GB 可跑），约束解码限制在 L3 词表，reward = set_f1（+ executable bonus + EOS shaping）。直接冲着 M3-P2 遗留的序列控制/EOS 问题去。
3. **步级密集奖励**（GeoSolver/DRACO 思路）：用 ChainValidator + io_factor + mapping confidence 做过程奖励，缓解稀疏 set_f1。
4. **Self-play 数据飞轮**（Phase 3+，GeoX/AFlow 思路）：生成-验证-准入循环产出新监督行；**必须走本项目 train-only candidate 纪律**（provenance/四层去重/审计），绝不直接进 authority。
5. **链修复 RL**（FlowScout 思路）：把 fusion/repair 阶段（现为 GraphRAG 候选 + LLM 选择）升级为 RL 训练的修复策略。
6. **自进化路径（self-evolving agent）**（2026-09-17 补充，owner 关心"越用越好"）：文献中三档实现，效果与部署成本递增——
   - **档 6a 非参数记忆积累**（最成熟，权重不动）：把使用中产生的经验（高分链、失败归因）写入外部记忆库，推理时检索注入 prompt/context（ExpeL、Voyager 路线）。我们的 GraphRAG+链修复已具备该形态雏形，增量是把推理期经验结构化入库。
   - **档 6b 数据飞轮 + 周期性离线 RL**（工业主流，**版本间变好而非实时变好**）：线上推理产出 → 验证器过滤（RLVR 可验证奖励在此复用：set_f1/I-O 契约/ChainValidator，零标注成本）→ 高置信经验入 train-only candidate 池（走 provenance/四层去重/审计纪律）→ 周期性离线 GRPO/DPO 重训 → 发布新版本。零件全部现成：验证器、beam 基础设施、QLoRA 重训管线、candidate 审计流程。
   - **档 6c 在线权重更新**（研究前沿，**不建议现阶段碰**）：边用边更新权重（TTRL test-time RL、BlueLM-GUI self-improving flywheel 属此线）。风险：reward hacking、灾难性遗忘、推理/训练引擎不一致的基础设施成本、不可回滚；与我们 A10 单卡算力和审计纪律不匹配。
   - 边界澄清：ComfyUI-R1/RobustFlow 的 RL 均为离线训练，部署后冻结；AFlow 的 MCTS 是测试期搜索，沉淀的是外部资产（workflow 库）而非权重——最接近 6a 的实例。

## 3.2-bis 两条 RL 路径：强化模型（LLM-RL）vs 强化智能体（Agentic RL）（2026-09-17 补充）

用户关心的区分即 Agentic RL 综述（2509.02547）的核心立论。两者形式化差异：

| 维度 | 路径一：强化模型（LLM-RL） | 路径二：强化智能体（Agentic RL） |
|---|---|---|
| **形式化** | 退化的**单步 MDP**：输入 prompt → 一次生成 → 奖励 | 时序扩展的 **POMDP**：多轮观察-行动-环境反馈循环 |
| **模型角色** | 被动的序列生成器 | 嵌入动态环境的自主决策者 |
| **训练信号** | 单条输出的端级奖励（对/错/偏好） | 轨迹级奖励 + 环境反馈（工具返回值、执行结果、状态变化） |
| **典型算法** | RLHF/PPO、DPO、GRPO（单轮可验证奖励） | 多轮 PPO/GRPO + 环境编排 + 长程 credit assignment |
| **代表** | DeepSeek-R1（数学/代码单轮推理）、ComfyUI-R1、Urban-R1 | WebRL（浏览器任务）、MCP-Universe RL、T1（长程终端任务） |
| **基础设施** | 相对简单：rollout=采样 | 复杂：需并发环境实例、慢工具调用下的调度（MCP-U RL 解决的就是这个） |

**本系统映射**：L3 链生成阶段（M1/M2/M3 主输出）= 天然单步 MDP，"强化模型"领地，GRPO 直接适用、基础设施最便宜；交互式落地阶段（GraphRAG 融合 → 链修复 → 追问循环）= 已是多轮 agent 循环，RL 化它才进入"强化智能体"领地。**结论：先路径一（链生成），路径二（修复循环，即档 5）作后续扩展，自进化飞轮（档 6）横跨两者。**

### 3.3 风险清单

- **Reward hacking**：length/EOS 类 shaped reward 在组相对 RL 下会产生 phantom advantages（2609.13866）——若做 GRPO，reward 主干应保持 outcome 型（set_f1/executable），shaping 项需消融验证。
- **Benchmark 过拟合**：RL 只能消费 train split；final-100、prediction-lock、冻结协议纪律完全不变。
- **多解 gold**：GRPO 组内样本同分时梯度为零 → 需要 executable/qgis_mapping 做分层/字典序奖励。
- **val-49 过小**：不足以监控 RL 训练动态 → 需从 train 划出 RL 专属 holdout。
- **约束解码 vs on-policy 探索的张力**：强约束可能限制策略探索，需要在实验协议里显式处理。
- **自进化专属——数据飞轮污染**（档 6b）：模型自身产出回流训练会造成分布漂移与误差累积（self-consuming loop）；回流行必须过独立验证器且单独标记 provenance（如 `self_play_v1`），与人工审计行分层，禁止与 paper_v1 authority 混合；每个飞轮版本需固定 val 集做回归对比。

## 4. 建议下一步（供讨论，不启动）

1. 精读顺序：ComfyUI-R1 → AFlow → RobustFlow → Agentic RL 综述 → GeoX。
2. 若决定推进：先写 RLVR-P0 冻结协议（reward 定义、数据边界、防泄漏断言、实验账本条目），沿用本项目门禁纪律；不直接开始训练。
3. 与 M1-R2 收尾的衔接：M1-R2 final-100 结果出来后再定 RL 挂哪条路线（挂 M1=数据稀缺路线 vs 挂 M3=先验充足路线，两种假设检验意义不同）。

## 5. 文献 workflow vs 本项目算子链：概念对比（2026-09-16 补充，基于三篇 PDF 精读）

| 维度 | ComfyUI-R1 workflow | AFlow workflow | RobustFlow workflow | 本项目 L3 算子链 |
|---|---|---|---|---|
| 输出表示 | 开放式 ComfyUI JSON 图（数百种异构节点+参数） | 自由 Python 代码（"workflow as code"，无限搜索空间） | agentic workflow（LLM+工具编排结构） | **闭合 132-token 词表上的同质序列**（DAG 序列化，V4 不消费边） |
| 节点语义 | 异构功能组件（LoadImage/sampler/LoRA…，带参数） | LLM 调用+控制逻辑（Ensemble/Review/Revise/Judge/Debate），**运行时仍调用 LLM** | LLM/工具节点 | **同质语义抽象类（L3）**，一对多映射到具体 QGIS 算子，实例化推迟到下游 |
| 运行时角色 | 完整可执行规格 | 元程序（workflow 是骨架、LLM 是执行节点） | 同 AFlow 系 | 语义骨架 → bridge+beam+fusion 落地为**参数无关** QGIS processes+links，运行时无 LLM（M1） |
| 训练/搜索 | 4K 工作流→长 CoT（节点选择→规划→代码）→SFT+GRPO | MCTS 搜索代码空间，LLM 做 proposal | 偏好优化（DPO 系）对齐 canonical structures，利用 model-generated workflows 的 structural agreement | beam search + 约束评分（合法性/长度/I-O factor）+ weighted CE |
| 奖励性质 | **rule-metric hybrid**：格式合法性、结构完整性、节点级保真；负奖励惩罚结构破坏/节点幻觉（**非端到端任务成功**） | 端到端执行反馈（下游 QA/coding benchmark 准确率，昂贵） | 无执行奖励，纯偏好（等价改写输入→一致输出） | 候选：set_f1 vs gold + Neo4j I/O 契约 + 可执行性（**结构上与 ComfyUI-R1 同范式**，且多出 KG 步级验证器） |
| 数据来源 | 社区工作流 27K→筛选 4K | 从种子 workflow 搜索合成 | 7,530 queries / 31,889 workflows 评测构造（paraphrase+noise injection） | 真实源码确定性转换 + provenance + 四层去重 + source-disjoint（监督密度低但可审计） |
| 多解性 | 节点+参数使 workflow 唯一性较强 | 搜索目标单一最优 | 显式研究对象（structural agreement） | **显式声明**（TokenAcc/EM 仅诊断），L3 序列天然一对多 |

**对 RL 整合的三个含义**：① 我们的设定（闭合小词表 + 可验证中间结构 + 无端到端成功信号）最接近 ComfyUI-R1 已验证的 hybrid-reward GRPO 范式，比 AFlow 的下游执行反馈便宜一个量级；② 我们独有的"语义层（L3）→实例层（QGIS 算子）"两级结构允许两级奖励（set_f1 + I/O 契约/可执行性），文献没有对应物，是潜在贡献点；③ L3 无参数 → 信息瓶颈 + 多解性更强 → GRPO 组内奖励必须分层（否则同分零梯度），RobustFlow 的 structural agreement 思路可用于构造多解等价类。

