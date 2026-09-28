# 强化学习结合调研报告 v2（整合版）

日期：2026-09-18
状态：**调研完成，未授权任何训练/工程动作**。本报告整合 `report_v1.md`（初扫）、`comfyui_r1_reading_notes.md`（精读）、`rl_algorithm_genealogy_notes.md`（理论参考）、`learning_journal.md`（学习日志，附 录C）的全部结论，为后续 RLVR-P0 立项决策的唯一权威入口。v1 与各笔记保留为附件，内容冲突时以本报告为准。

---

## 0. 摘要（一页版）

**背景**：M1/M2/M3 冻结矩阵闭环（M2-C0 F1 0.2236 最优、DAPT 净效应为负、M3 收束于 P2-T1 0.1991），约束在数据侧；training_contract 早已声明 ranking 是 post-training 目标、task_plan M1 路线列有"可选 DPO"——RL 是数据侧杠杆之后的下一个天然杠杆。

**核心结论**：
1. 本系统**天然 RLVR 就绪**：奖励全部确定性可验证（set_f1/executable/qgis_mapping，零标注成本）+ 动作空间极小（132 L3 token、链长 5-13）。
2. 设定最接近 **ComfyUI-R1 已验证的 veto-hybrid-reward GRPO 范式**（ACL 2026 Findings），比端到端执行反馈便宜一个量级。
3. 选型：**M3=GRPO**（Dr.GRPO 变体，on-policy 探索可发现 gold 之外的新有效链——多解场景核心增值）；**M1=DPO**（beam×composite 构对，基础设施全现成）；PPO 不选。
4. RL 定位为**结构性收尾**（+0.02~0.03 量级），主增益仍在数据侧——预期必须校准。
5. 立项时机建议：**M1-R2 final-100 裁决之后**（决定 RL 挂 M1 数据稀缺线还是 M3 先验充足线）。

---

## 1. 背景与目的

- 项目主线：自然语言任务 → L3 语义算子链 → QGIS 工作流落地。三条模型路线共享 L3 输出边界，冻结结论：泛化能力=预训练先验（M1-R1 塌缩 vs M3 跟随任务文本）；DAPT 净效应为负（M2-P2）；SFT 后遗留问题=序列控制/EOS/多解排序。
- RL 调研要回答的三个问题：① 当前 RL 进展到哪了；② 别人的 workflow 生成与我们的算子链有何异同；③ RL 如何与我们三路线整合、从哪切入。
- 调研方法：academic-search skill（arXiv REST + OpenAlex；S2 无 Key 429 降级）+ WebSearch 框架生态 + 16 篇核心 PDF 下载精读（1 篇逐节精读）+ 10 站理论学习（附录 C）。

## 2. RL 进展主线（2024–2026）

演化脉络：**RLHF/PPO → DPO 系直接对齐 → RLVR（可验证奖励 + GRPO，DeepSeek-R1 路线）→ Agentic RL（长程、多轮、真实环境）**。

- Agentic RL 综述（2509.02547）：LLM-RL = 退化单步 MDP；Agentic RL = 时序扩展 POMDP，双分类法。
- GRPO 成为小规模/垂直领域标配（无 critic、组内相对基线），对 A10-23GB 算力友好。
- 过程奖励（PRM）与密集奖励活跃：GeoSolver Geo-PRM-2M（token 级）、DRACO（长程 credit assignment）。
- 稳定化研究：RTPO、GCPO、Dr.GRPO（std 归一偏置）、DAPO（clip-higher/动态采样）、GSPO（序列级比）。
- **开源框架**：verl（主流大规模）、OpenRLHF（成熟）、**TRL（GRPOTrainer 开箱即用，最适合本项目小规模）**、AReaL（异步，新）。

## 3. 两条路径与自进化：我们的定位

### 3.1 路径一 vs 路径二

| 维度 | 强化模型（LLM-RL） | 强化智能体（Agentic RL） |
|---|---|---|
| 形式化 | 退化单步 MDP | 时序扩展 POMDP |
| 模型角色 | 被动序列生成器 | 嵌入环境的自主决策者 |
| 训练信号 | 单条输出端级奖励 | 轨迹级奖励 + 环境反馈 |
| 典型算法 | PPO/DPO/GRPO（单轮 RLVR） | 多轮 PPO/GRPO + 环境编排 + 长程 credit assignment |
| 代表 | DeepSeek-R1、ComfyUI-R1、Urban-R1 | WebRL、MCP-Universe RL、T1 |
| 基础设施 | 简单（rollout=采样） | 复杂（并发环境、慢工具调度） |

**本系统映射**：L3 链生成 = 天然单步 MDP（路径一，GRPO 直接适用、最便宜）；GraphRAG 融合 → 链修复 → 追问循环 = 已是多轮 agent 循环（路径二的最小形态，即整合方案档 5）。**结论：先路径一，路径二作后续扩展。**

### 3.2 自进化三档（"越用越好"的边界澄清）

文献中的 RL 均为离线训练、部署后冻结（ComfyUI-R1/RobustFlow）；AFlow 的 MCTS 是测试期搜索、沉淀外部资产。真正的自进化分三档：

- **6a 非参数记忆积累**（成熟，权重不动）：使用经验（高分链/失败归因）入外部记忆库，推理时检索。我们 GraphRAG+链修复已具雏形。
- **6b 数据飞轮 + 周期性离线 RL**（工业主流，**版本间变好而非实时**）：推理产出 → 验证器过滤（RLVR 奖励复用）→ 高置信经验入 train-only candidate 池（走 provenance/四层去重/审计）→ 周期性离线 GRPO/DPO → 新版本。零件全部现成。
- **6c 在线权重更新**（研究前沿，**现阶段不建议**）：TTRL/BlueLM-GUI flywheel 一线；reward hacking、灾难性遗忘、基础设施成本、不可回滚，与单卡算力和审计纪律不匹配。

## 4. 文献综述（16 篇核心，PDF 见附录 A）

### A 类：Workflow/算子图生成（同构任务）

| 论文 | arXiv | venue | 相关点 |
|---|---|---|---|
| ComfyUI-R1 | 2506.09790 | ACL 2026 Findings | **首个 workflow 生成推理模型**；veto 混合奖励 + GRPO（§7 精读） |
| AFlow | 2410.10762 | ICLR 2025 | MCTS 搜索代码空间 workflow，执行反馈奖励 |
| A²Flow | 2511.20693 | arXiv | 自适应算子提取，摆脱预定义算子 |
| RobustFlow | 2509.21834 | arXiv | 偏好优化学语义不变性——直击 task_type conditioning 脆弱性 |
| FlowScout | 2608.10039 | arXiv | 真实执行反馈构建 workflow（链修复同位） |
| Benchmarking Agentic Workflow Generation | 2410.07869 | arXiv | WorFEval：LIS+MCIS 评测协议 |

另识别未下载：ComfyBench（CVPR 2025）、ComfyGPT（2503.17671）、Knowledge-Centric Agents（2607.15845）、From Search to Synthesis（2606.30704）等。

### B 类：Geo-RL（领域最近邻）

| 论文 | arXiv | 相关点 |
|---|---|---|
| GeoX | 2605.20006 | self-play + 可验证奖励，零人工标注（数据飞轮思路） |
| GeoZero | 2511.22645 | 无 CoT 冷启动直接 RL |
| Urban-R1 | 2510.16555 | GRPO 后训练对齐城市智能——SFT 后残余问题的处置范式 |
| GeoSolver | 2603.09551 | Geo-PRM-2M 过程监督（步级奖励思路） |
| Earth-Agent-Pro | 2609.12533 | 全链路"科学问题→可执行工作流"，专家技能约束规划 |

### C 类：工具使用 RL / 基础设施

MCP-Universe RL（2608.22167，开源环境编排+rollout 调度）；Learning to Use Tools（2608.28447，端到端工具调用 RL）。

### D 类：风险警示

Phantom Advantages in Group-Relative RL under Shaped Rewards（2609.13866：shaped reward 下组相对优势虚假）；Spurious Tool Use（2609.16268：RL 学到错误触发原因）。

## 5. 文献 workflow vs 本项目算子链

| 维度 | ComfyUI-R1 | AFlow | RobustFlow | 本项目 |
|---|---|---|---|---|
| 输出表示 | 开放 ComfyUI JSON 图（异构节点+参数） | 自由 Python 代码（无限空间） | LLM/工具编排结构 | **闭合 132-token 词表同质序列**（DAG 序列化） |
| 节点语义 | 异构功能组件带参数 | LLM 调用+控制逻辑，运行时仍调 LLM | LLM/工具节点 | 同质语义抽象类，一对多映射 QGIS 算子，实例化推迟下游 |
| 运行时角色 | 完整可执行规格 | 元程序 | 同左 | 语义骨架 → bridge+beam+fusion 落地**参数无关**链 |
| 奖励 | rule-metric hybrid（非端到端） | 端到端执行反馈（贵） | 纯偏好 | set_f1 + I/O 契约 + 可执行性（**与 ComfyUI-R1 同范式** + KG 步级验证器） |
| 数据来源 | 社区 27K→4K | 搜索合成 | 评测构造 | 真实源码确定性转换+provenance+四层去重 |
| 多解性 | 节点+参数唯一性较强 | 单一最优 | 显式研究 | **显式声明多解**（TokenAcc/EM 仅诊断） |

**三个含义**：① 我们=ComfyUI-R1 已验证范式，成本便宜一个量级；② 独有的语义层→实例层两级奖励（set_f1 + I/O 契约）是潜在论文贡献点；③ L3 无参数 → 多解性更强 → GRPO 组内奖励必须分层（veto 门 + set_f1），RobustFlow 的 structural agreement 可用于构造多解等价类。

## 6. 理论基础结论（详版见 rl_algorithm_genealogy_notes.md）

- **演化逻辑**：PPO 太重（4 模型）→ 两支减法：DPO 砍采样（离线化）、RLOO/GRPO 砍 critic（组内统计当基线）→ GRPO 实践暴露新问题 → Dr.GRPO/DAPO/GSPO 打补丁。
- **三大核心问题**：① on-policy vs off-policy = 探索能力 vs 数据效率——**探索是我们选 on-policy 的最重要理由**（多解 gold 场景可发现新有效链）；② GRPO 砍 critic = 组均值恰是蒙特卡洛基线，省一半显存（单卡可行性前提）；③ KL 防 reward hacking + 灾难遗忘，β 从小起步（1e-3），KL 曲线进监控。
- **已知坑位**：零梯度组（全同分→优势全 0→采样浪费；多解+模型变确定会加剧）→ 动态采样/两级奖励防御；std 归一偏置 → Dr.GRPO 开关；shaped reward phantom advantages → 第一轮不加塑形。
- **选型定调**：M1=DPO（off-policy 稳定、beam×composite 构对、单卡友好）；M3=GRPO（Dr.GRPO 变体起步）；PPO 不选；DAPO/GSPO 作备选补丁不作第一轮。

## 7. 精读结论：ComfyUI-R1（详版见 comfyui_r1_reading_notes.md）

- **奖励 = veto 分层**：`R_final = −1（格式/DAG/节点保真任一违规）或 (4+R_correct)/4.0 ∈ [0.75,1.0]`；R_correct = 节点集召回。**边/顺序不进奖励**——绕开多解对齐难题，顺序靠 SFT 先验携带。全规则计算，零执行零 RM 零标注。
- **数据构造可抄**：gold + ⌊0.8·|gold|⌋ 干扰候选，多采样增广（3,717 workflows → 11,140 样本）。
- **RL 是精修不是主力**：300 步、lr 1e-6、G=4；SFT-only 已 0.95 FV/0.60 节点F1，GRPO 增量 +0.02~0.03。**主增益来自 SFT 数据侧**——与我们"约束在数据侧"结论一致。
- 其他：代码表示 > JSON 表示；SFT 冷启动必须先行；超参 ε=0.2/β=0.001/max_tokens 32K（我们短链只需数百）。

## 8. 整合方案（六档，按成本/风险递增）与风险

### 8.1 六档方案

1. **M1-DPO**（task_plan 既定，最小改动）：beam top-k × composite → 偏好对（best-vs-rest 起步）→ DPO 自研 decoder。
2. **M3/M2-GRPO（RLVR）**：TRL GRPOTrainer + Qwen-9B NF4+LoRA（A10 可跑），约束解码限 L3 词表，reward = veto 门 + set_f1。直面 M3-P2 遗留 EOS/序列控制问题。
3. **步级密集奖励**：ChainValidator + io_factor + mapping confidence 过程奖励（GeoSolver/DRACO 思路），缓解稀疏 set_f1 与零梯度组。
4. **Self-play 数据飞轮**（Phase 3+）：生成-验证-准入循环；**必须走 train-only candidate 纪律**，单独标记 provenance（如 `self_play_v1`），禁止混入 authority。
5. **链修复 RL**（FlowScout 思路）：fusion/repair 阶段升级为 RL 策略——路径二最小形态。
6. **自进化飞轮**（§3.2）：6a 记忆/6b 周期离线 RL/6c 在线（不建议）。

### 8.2 风险清单

| 风险 | 缓解 |
|---|---|
| Reward hacking（shaped reward phantom advantages） | reward 主干保持 outcome 型；shaping 项单独消融；KL 曲线监控 |
| Benchmark 过拟合 | RL 只消费 train；final-100/prediction-lock 纪律不变 |
| 数据飞轮污染（self-consuming loop） | 回流行独立验证器 + 单独 provenance + 分层；固定 val 回归对比 |
| 多解 gold 同分零梯度 | 分层/字典序奖励（executable 破局）+ 动态采样过滤 |
| val-49 过小 | 从 train 划 RL 专属 holdout（~400 条） |
| 约束解码 vs on-policy 探索张力 | 协议显式处理；smoke 先行 |

## 9. 能力准备状态

10 站理论课程 + 评测指标加餐已完成（学习日志附录 C，含 7 条困惑记录与讲评）。owner 已建立从梯度下降到 GRPO/DPO 的完整理论地图，强项为算法机制理解；实验治理直觉（数据隔离/纪律边界）待真实协议讨论中强化。理论侧无阻塞。

## 10. 建议下一步（供决策，不启动）

1. **立项时机**：等 M1-R2 final-100 裁决（当前 Phase 2-D SFT 已完成：best composite 0.2802 @ epoch 15，SetF1 0.114/LCS 0.078，待 dev-20 → prediction lock → final-100）——R2 结果决定 RL 挂 M1（数据稀缺线）还是 M3（先验充足线）。
2. **若启动**：按 §8.1 档 2（M3-GRPO）先写 RLVR-P0 冻结协议——reward 定义（veto 门 + set_f1）、数据边界（train-only + RL holdout ~400 + val 只报告 + final-100 一次开启）、防泄漏断言、监控清单（KL/熵/奖励分布/零梯度组占比）、实验账本条目；**不直接开始训练**。
3. **优先精读补遗**（可选）：AFlow（MCTS 细节）、RobustFlow（偏好构对细节）、Urban-R1（小数据 GRPO batch 组法）、DeepSeek-R1 论文 RL 章节（GRPO 公式源头）。
4. **评测增强**（独立可做）：把"首错分叉位置分布"升级为标准评测指标（M3-P1 的 42/49 前缀统计已是雏形；区分"不会规划"vs"中途走岔"）；报告时用满 metric contract 四元 primary（set_f1/usable/executable/qgis_mapping），executable 口径=结构可落地（非参数级执行）。

---

## 附录 A：核心论文清单（16 篇，本地 `papers/`）

| # | arXiv | 本地文件 |
|---|---|---|
| 1 | 2509.02547 | 2509.02547_AgenticRL_Survey_Landscape.pdf |
| 2 | 2506.09790 | 2506.09790_ComfyUI-R1_Workflow_Generation.pdf |
| 3 | 2410.10762 | 2410.10762_AFlow_Automating_Agentic_Workflow.pdf |
| 4 | 2511.20693 | 2511.20693_A2Flow_SelfAdaptive_Operators.pdf |
| 5 | 2509.21834 | 2509.21834_RobustFlow_Robust_Workflow.pdf |
| 6 | 2608.10039 | 2608.10039_FlowScout_Execution_Feedback.pdf |
| 7 | 2410.07869 | 2410.07869_Benchmarking_Agentic_Workflow_Generation.pdf |
| 8 | 2510.16555 | 2510.16555_Urban-R1_GRPO_Urban_GI.pdf |
| 9 | 2605.20006 | 2605.20006_GeoX_SelfPlay_Verifiable_Rewards.pdf |
| 10 | 2511.22645 | 2511.22645_GeoZero_Geospatial_Reasoning_Scratch.pdf |
| 11 | 2603.09551 | 2603.09551_GeoSolver_Process_Supervision.pdf |
| 12 | 2609.12533 | 2609.12533_Earth-Agent-Pro_FullChain_EO.pdf |
| 13 | 2608.22167 | 2608.22167_MCP-Universe-RL_ToolUse.pdf |
| 14 | 2608.28447 | 2608.28447_LearningToUseTools_ToolIntegrated_RL.pdf |
| 15 | 2609.16268 | 2609.16268_Spurious_Tool_Use.pdf |
| 16 | 2609.13866 | 2609.13866_Phantom_Advantages_GroupRelative_RL.pdf |

## 附录 B：评测体系备忘

- metric contract 四元 primary：set_f1 / usable / executable / qgis_mapping；supporting：LCS；diagnostic：TokenAcc/sequence_em/loss/top1/top5。
- set_f1=集合级部分匹配（多解公平）；LCS=顺序感知；EM=一票全否仅诊断。P/R 组合可会诊：P高R低=保守短链，R高P低=倾倒长链，双低=不会；指标打架=诊断信息（M3-P1 案例：EM 0/49 + recall 0.885 → 截断伪影）。
- 两块仪表盘：训练健康（loss/KL/熵/奖励分布/零梯度组占比）≠ 评测质量（P/R/F1/SetF1/LCS/EM），前者坏则后者不可信。
- 建议新增：首错分叉位置分布（§10.4）。

## 附录 C：学习日志

`learning_journal.md`：10 站路线图（整体框架→梯度下降→预训练范式→SFT 机关→RL 世界观→REINFORCE→基线/advantage→PPO→GRPO 总装→DPO→RLVR-P0 协议设计）+ 评测指标加餐站 + 困惑清单（7 条，含教学节奏复盘）。理论教学载体，非决策文档。
