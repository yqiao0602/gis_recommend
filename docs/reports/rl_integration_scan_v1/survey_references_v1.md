# 《RL 在 GIS 工作流生成中的应用调研》文献清单 v1（按章节映射）

日期：2026-09-18
说明：服务 `gis_rl_survey_outline_v1.md` 的配文文献。分三部分：A=本次核验的新增经典/对齐文献（18 篇，标题已逐一核验）；B=已有的 16 篇 workflow/Geo-RL 文献（见 report_v2 附录 A，此处只标章号）；C=经典期刊文献（无 arXiv）。

**下载状态（2026-09-18 更新）：A 类 18 篇全部下载入库并校验通过**（首页标题+页数逐一核验，papers/ 目录现共 34 篇正式 PDF）。**去重备案**：发现 6 个重名副本（另一会话以不同命名下载了同一批，md5 逐一比对为字节相同），保留未删，文件名对照：
- `2501.12948_DeepSeek-R1.pdf` = `2501.12948_DeepSeek-R1_RLVR.pdf`
- `1511.06732_Sequence_Level_Training_MIXER.pdf` = `1511.06732_MIXER_Sequence_Level_Training.pdf`
- `2312.08935_Math-Shepherd_Step_Rewards.pdf` = `2312.08935_Math-Shepherd_Process_Reward.pdf`
- `2209.13085_Reward_Hacking_Defined.pdf` = `2209.13085_Defining_Reward_Hacking.pdf`
- `2210.10760_RM_Overoptimization_Scaling_Laws.pdf` = `2210.10760_Scaling_Laws_Reward_Overoptimization.pdf`
- `2503.20783_DrGRPO_Understanding_R1Zero.pdf` = `2503.20783_Dr.GRPO_Critical_Perspective.pdf`
（清理与否由 owner 决定。）

本清单 A 类的本地文件名 = arXiv ID + 描述性后缀，如 `2203.02155_InstructGPT_RLHF.pdf`。

## A. 新增核验文献（arXiv，标题已核实）

| arXiv | 年 | 标题（缩写） | 服务章 | 用途 |
|---|---|---|---|---|
| 2203.02155 | 2022 | InstructGPT: Training LMs to follow instructions with human feedback | 3 | RLHF 开山：奖励模型+PPO 三阶段范式 |
| 2305.18290 | 2023 | DPO: Your Language Model is Secretly a Reward Model | 3/6 | 偏好优化路线源头（M1 路线依据） |
| 2402.03300 | 2024 | DeepSeekMath（GRPO 原始论文） | 3/6 | GRPO 公式与组相对优势定义 |
| 2501.12948 | 2025 | DeepSeek-R1 | 3 | RLVR 规模化范式；多阶段训练管线 |
| 2309.00267 | 2023 | RLAIF vs. RLHF | 3 | AI 反馈替代人工反馈（打分程序=我们的验证器） |
| 2308.01825 | 2023 | RFT: Scaling Relationship on Learning Mathematical Reasoning | 3/6/7 | **Rejection Sampling Fine-Tuning 原文——路线 B（最易落地）的理论依据** |
| 1707.06347 | 2017 | PPO | 2/3 | clip 目标经典原文 |
| 1502.05477 | 2015 | TRPO | 2 | trust region 思想源头（2.4 一句话带过） |
| 1506.03099 | 2015 | Scheduled Sampling | 2/4 | exposure bias 的经典补救（第 3 站谱系③原文） |
| 1511.06732 | 2015 | MIXER: Sequence Level Training with RNN | 2/4 | 序列级训练/exposure bias 最早的 LLM 前身工作 |
| 2305.20050 | 2023 | Let's Verify Step by Step（OpenAI PRM） | 5 | 过程奖励模型开山（步级 reward 思路） |
| 2312.08935 | 2023 | Math-Shepherd | 5 | **免人工标注的步级奖励自动构造**——与"我们的验证器可自动产步级分"直接同构 |
| 2209.13085 | 2022 | Defining and Characterizing Reward Hacking（Skalse et al.） | 5/8 | reward hacking 的严格定义与分类（此前 2609.13866 是 LLM 场景实例） |
| 2210.10760 | 2022 | Scaling Laws for Reward Model Overoptimization（Gao et al.） | 5/8 | 过优化规律 + **BoN/rejection sampling 作为对照基线的理论位置** |
| 2503.14476 | 2025 | DAPO | 3/6 | 备选补丁：clip-higher/动态采样（零梯度组解法） |
| 2507.18071 | 2025 | GSPO（Qwen） | 3 | 备选补丁：序列级重要性比 |
| 2503.20783 | 2025 | Dr.GRPO: Understanding R1-Zero-Like Training | 3/6 | GRPO 偏置修正（建议默认采用其去 std 变体的依据） |
| 2504.12328 | 2025 | A Comprehensive Survey of Reward Models | 5 | reward 设计综述（taxonomy 参照）；备选 2510.01925 |

### 检索备注
- TTRL 原始论文本次查询未直接命中（返回大量 2026 后续变体，说明该线活跃）；test-time RL 仅在第 6 章路线 C/自进化 6c 一笔带过，如需可后补。
- Reward model survey 二选一：2504.12328（LLM 向、全面）为主，2510.01925（推理向分析）备选。

## B. 已有 16 篇（report_v2 附录 A）→ 章号映射

| 章号 | 文献 |
|---|---|
| 第 1/3 章（背景/序列生成） | 2509.02547 Agentic RL 综述 |
| 第 3/5 章（workflow 生成与奖励） | 2506.09790 ComfyUI-R1、2410.10762 AFlow、2511.20693 A²Flow、2509.21834 RobustFlow、2608.10039 FlowScout、2410.07869 WorFEval |
| 第 4/8 章（领域与难点） | 2605.20006 GeoX、2511.22645 GeoZero、2510.16555 Urban-R1、2603.09551 GeoSolver、2609.12533 Earth-Agent-Pro |
| 第 5/8 章（风险） | 2609.13866 Phantom Advantages、2609.16268 Spurious Tool Use |
| 第 6 章（基础设施） | 2608.22167 MCP-Universe RL、2608.28447 Learning to Use Tools |

## C. 经典期刊/教材文献（无 arXiv，引用时按原文格式）

| 文献 | 年 | 服务章 | 用途 |
|---|---|---|---|
| Watkins & Dayan, Q-learning (Machine Learning) | 1992 | 2 | 价值方法源头 |
| Williams, REINFORCE (Machine Learning) | 1992 | 2/3 | 策略梯度源头（第 5 站推导的正式出处） |
| Mnih et al., DQN (Nature) | 2015 | 2 | 深度 RL 里程碑（2.4 一句话） |
| Sutton & Barto, Reinforcement Learning: An Introduction (教材) | 2018 | 2 | 术语标准出处（policy/value/MDP 定义引用） |

## 统计

- A 类新增 18 篇（未下载）+ C 类 4 项期刊
- B 类已有 16 篇 PDF 已在库
- 全清单 ≈ 38 项，覆盖大纲全部 9 章；第 4 章（MDP 建模）以自有论证为主、文献辅证，无额外缺口
