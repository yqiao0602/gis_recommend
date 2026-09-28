# 外部文献补遗 v2：通用工具链数据集、意图合成方法与经典语义地理处理

日期：2026-09-17
性质：`docs/reports/external_gis_training_data_survey_v1.md` 的补遗（只读调研，未下载/未消费数据，训练行 0）。
定位：v1 回答的是"**GIS 专用**数据有没有"；本辑补上 v1 未覆盖的四个层级——①与"NL 意图→工具链/DAG"**结构同构**的通用数据集 ②**意图式数据合成方法**（直接服务意图重写管线）③**地学领域预训练先例**（M2 DAPT 负结果的对照文献）④**经典语义地理处理/工作流组合文献**（L3 体系理论根 + related work 深度）。RL 结合方向已有单独报告（`docs/reports/rl_integration_scan_v1/`），本辑不重复。

核验等级沿用 v1：【仓库/站点核验】= 直接访问仓库页/HF API 确认；【摘要核验】= arXiv 摘要页/API 确认论文内容。

## 一、结构同构的通用工具链数据集（NL 意图 → 工具链/DAG）

这一层 v1 完全没扫。它们不是 GIS，但任务形态与本项目**精确同构**（自然语言意图 → 多步工具调用序列/图），且 license 干净、量级大：

| 资源 | 核验 | 规模与形态 | 对本项目的价值 |
|---|---|---|---|
| **TaskBench**<br>arXiv [2311.18760](https://arxiv.org/abs/2311.18760) | 【摘要核验】+ HF `microsoft/Taskbench`（1,241 下载）【站点核验】 | 三阶段评测（任务分解/工具选择/参数预测）；**Tool Graph** 表达分解任务；**back-instruct 方法从工具图反向生成高质量用户指令** | **方法论最贴合**：back-instruct = 从 gold 链反推意图式 NL 指令——正是"链→意图"重写方向；Tool Graph 评测与 benchmark v0.2.1 的 DAG 评测同构 |
| **WorkflowLLM / WorkflowBench**<br>arXiv [2411.05451](https://arxiv.org/abs/2411.05451) | 【摘要核验】 | **106,763 样本 SFT 集**，1,503 APIs / 83 应用 / 28 类；从 Apple Shortcuts + RoutineHub **真实工作流**转录为 Python 风格代码；数据中心式三阶段（收集→重写→验证） | **管线设计同构**："真实工作流→代码转录→指令重写→验证"与本项目"源码链→任务文本"同构且开源；规模证明该路线可以做到 10 万级 |
| **ToolBench / ToolLLM**<br>arXiv [2305.16504](https://arxiv.org/abs/2305.16504)，ICLR'24 spotlight（README 标注） | 【仓库核验】Apache-2.0；数据可下载（Google Drive/清华云） | 3,451 工具 / **16,464 REST APIs** / **126,486 指令实例** / 469,585 真实 API 调用；G1 单工具/G2 类内多工具/G3 集合内多工具三档 | 量级最大的开源意图→工具链数据；G2/G3 多工具链形态与 L3 链同构 |
| **APIGen / xLAM**<br>arXiv [2406.18518](https://arxiv.org/abs/2406.18518) | 【摘要核验】+ HF `Salesforce/xlam-function-calling-60k`（37,490 下载）【站点核验】 | 3,673 可执行 APIs / 21 类；**三段验证**（格式检查→真实执行→语义验证）合成函数调用数据 | **验证纪律方法论对标**：与本项目 fail-closed 逐级门禁同构——"合成数据必须可验证"这条纪律在通用域已被证明能训出超 GPT-4 的 7B 模型 |
| **Gorilla / BFCL**<br>arXiv [2305.15334](https://arxiv.org/abs/2305.15334) | 【仓库核验】Apache-2.0 | APIBench（大规模 API 训练数据）+ Berkeley Function-Calling Leaderboard **V1-V4**（V3 多轮多步带状态评估、V4 agent 设定含错误恢复） | 评测体系参照：V3/V4 的多步+状态+错误恢复维度是 benchmark 未来扩展方向 |
| **WorfBench / WorfEval**<br>arXiv [2410.07869](https://arxiv.org/abs/2410.07869) | 【摘要核验】 | 工作流生成 benchmark，**图结构工作流** + 子序列/子图匹配评测协议 | 与 benchmark v0.2.1 的 DAG+subgraph 评测思路直接可对照（引用+校验我们的 scorer 设计） |
| ToolACE arXiv [2409.00920](https://arxiv.org/abs/2409.00920)、API-Bank arXiv [2304.08244](https://arxiv.org/abs/2304.08244)、Seal-Tools arXiv [2405.08355](https://arxiv.org/abs/2405.08355)、APIGen-MT [2504.03601](https://arxiv.org/abs/2504.03601) | 【摘要核验】 | 函数调用数据合成与评测的同族工作 | related work 引用池 |

**判定**：这一层的价值不是"拿来当 QGIS 训练样本"（域不重叠，直接混入训练收益存疑），而是三件事：①**重写管线的方法蓝本**（back-instruct、三阶段收集→重写→验证、三段验证）②few-shot/格式校准参照 ③related work 与 benchmark 设计的外部锚点。v1 的结论不变：**主粮仍是内部数据**。

## 二、意图式数据合成方法（服务 25.7 万描述库重写 + GEE 转化资产）

| 方法 | 出处 | 核心机制 | 对重写管线的启示 |
|---|---|---|---|
| **back-instruct** | TaskBench [2311.18760](https://arxiv.org/abs/2311.18760) | 从工具图**反向**生成用户指令（链→意图） | 与"25.7 万描述库（含链）→ 意图文本"方向一致；可对照其指令质量过滤环节 |
| **三阶段重写+验证** | WorkflowLLM [2411.05451](https://arxiv.org/abs/2411.05451) | 真实工作流收集→LLM 重写→执行验证 | 重写不是一次生成：要有验证回路；他们靠执行，我们靠 L3 合法性+链保真双检 |
| **三段验证合成** | APIGen [2406.18518](https://arxiv.org/abs/2406.18518) | 格式→执行→语义三层过滤 | 与 fail-closed 门禁同构；其"7B 超 GPT-4"结果证明验证过的合成数据质量可超人工 |
| **Self-Instruct** | arXiv [2212.10560](https://arxiv.org/abs/2212.10560) | 模型自举生成指令（奠基方法） | 重写器的起点方法 |
| **Evol-Instruct** | WizardLM arXiv [2304.12244](https://arxiv.org/abs/2304.12244) | 指令由简到繁演化 | 可用于把简单意图样本演化成多步复杂意图（扩多样性） |
| **Magpie** | arXiv [2406.08464](https://arxiv.org/abs/2406.08464) | 只喂左半模板让对齐模型自己生成用户侧查询 | 无需种子文本的意图生成；与 persona 采样可组合 |
| **PersonaHub** | arXiv [2406.20094](https://arxiv.org/abs/2406.20094) | 10 亿 persona 驱动数据合成 | 用 GIS 从业者/行业 persona 控制意图分布的多样性（规划者/生态学家/城市规划师…） |

**判定**：这一层**直接可用**——不是数据是配方。当前四臂重写实验（C0/A1/B1/B2）的每一臂都能在上述文献里找到方法锚点与消融先例；论文写作时"为什么这样设计重写管线"可以用这组文献做方法论依据。

## 三、地学领域预训练先例（M2 DAPT 负结果的对照）

| 资源 | 核验 | 内容 | 对论文的价值 |
|---|---|---|---|
| **K2** | arXiv [2306.05064](https://arxiv.org/abs/2306.05064) | LLaMA-7B 在 5.5B tokens 地学语料上继续预训练（**完整 DAPT→SFT recipe**）+ GeoSignal 指令集 + GeoBench | 与 M2-P1/P2 实验设计**同构**；其结果为正、本项目代码 DAPT 为负——**差异点在语料形态与任务形态**（散文 vs 代码、领域问答 vs 意图规划），是 Discussion 的现成对照 |
| **GeoGalactica** | arXiv [2401.00434](https://arxiv.org/abs/2401.00434) | Galactica 底座 + 地学语料继续预训练 + SFT | 第二个 DAPT 正面先例，同样非"意图→算子"任务形态 |
| When Geoscience Meets Foundation Models | arXiv [2309.06799](https://arxiv.org/abs/2309.06799) | 地学 FM 综述 | related work 收口 |

**判定**：K2/GeoGalactica 的正面结果与 M2 的负结果不矛盾——它们的任务是领域问答/文本，本项目是意图→结构化算子链。论文里可以正面引用它们来定位差异："domain pretraining 在领域知识任务有效，但在结构化规划任务上我们测得净负"。

## 四、经典语义地理处理与工作流组合文献（L3 理论根）

OpenAlex 检索（期刊侧，v1 的 arXiv 检索天然漏掉这一层）：

| 文献 | 年份 | 引用 | 与本项目的关系 |
|---|---|---|---|
| Integrating Semantic and Syntactic Descriptions to Chain Geographic Services | 2006 | 93 | 服务链语义组合的奠基工作（Lutz/Klien 线）；L3 作为"共享算法语义层"的先例 |
| Formalizations for geooperators-geoprocessing in Spatial Data Infrastructures | 2015 | 15 | geooperator 形式化——与 L3 taxonomy 构建直接同族 |
| Towards a knowledge base to support geoprocessing workflow development | 2016 | 38 | 地理处理工作流知识库 |
| Coupling Knowledge with GIS Operations: The Benefits of Extended Operation Descriptions | 2017 | 10 | 扩展算子描述的知识耦合（与 KG 侧 GraphRAG 融合相关） |
| **Finding and sharing GIS methods based on the questions they answer** | 2018 | 29 | **前 LLM 时代的"意图→GIS 方法"工作**——问题驱动方法检索，与"意图式规划"任务定义同一谱系 |
| A Task-Oriented Knowledge Base for Geospatial Problem-Solving | 2018 | 7 | 任务导向地理知识库 |
| Formalizing Parameter Constraints to Support Intelligent Geoprocessing (SHACL) | 2021 | 22 | 参数约束形式化 |

**判定**：这一层不提供数据，但提供两样论文刚需：①**L3 体系不是无根之水**——geooperator 形式化/服务链语义组合有 20 年谱系，L3 是其在 LLM 时代的续篇；②"从问题找 GIS 方法"的 2018 工作是意图式任务的直接前身。Related work 的历史纵深就靠这组文献。

## 五、机制文献（两个内部结论的外部支撑）

- **Shortcut Learning of Large Language Models in Natural Language Understanding**（arXiv [2208.11857](https://arxiv.org/abs/2208.11857)）：echo→copy 现象的理论挂靠——"转写式 SFT 学到的是输入→输出的抄写捷径"这个诊断可引用 shortcut learning 谱系（另见 Geirhos et al. 2020 Nat. Mach. Intell.，经典综述，未单独核验）。
- **Constrained decoding 一线**（AdapTrack [2510.17376](https://arxiv.org/abs/2510.17376)、Sketch-Guided [2401.09967](https://arxiv.org/abs/2401.09967) 等）：终止/重复控制的文献面——V2a 冒烟教训（n-gram 类约束破坏结构化 JSON 输出、termination 首选 repetition_penalty）与该线"硬约束扭曲输出意图"的已知问题一致，写论文时有现成理论依据。

## 六、与当前实验的对接矩阵

| 当前工作 | 可对接的外部文献 | 对接方式 |
|---|---|---|
| 意图重写四臂实验（C0/A1/B1/B2） | TaskBench back-instruct / WorkflowLLM 三阶段 / APIGen 三段验证 / Evol-Instruct / PersonaHub | 方法蓝本与消融先例；重写管线设计的方法论引用 |
| GEE 44,220 行转化资产的后续利用 | WorkflowLLM（真实工作流→代码转录→指令） | 同构管线的规模化先例（106k） |
| M2 DAPT 负结果（论文 Discussion） | K2 / GeoGalactica | 正面先例对照，定位差异（任务形态） |
| benchmark v0.2.1 DAG 评测 | WorfBench subgraph matching / TaskBench Tool Graph | scorer 设计的外部锚点与校验 |
| V2a 终止控制教训 | constrained decoding 一线 | "硬约束破坏输出意图"的文献支撑 |
| echo→copy 诊断 | shortcut learning（2208.11857） | 机制术语挂靠 |
| L3 taxonomy 贡献声明 | §四经典文献全组 | 历史谱系定位 |

## 七、结论

1. **v1 结论不变**：外部没有"NL 意图→QGIS 算子 DAG"的训练主粮，主料仍是内部 25.7 万描述库与转化资产。
2. **但"配方法"比预期丰富**：意图合成（§二）+ 可验证数据管线（APIGen）+ 真实工作流转录（WorkflowLLM）三条方法线在通用域已被 10 万级规模验证——重写管线不必从零发明，且每一步都有可引用的先例。
3. **结构同构数据集**（TaskBench 106k 级的 WorkflowBench 等）license 全干净（Apache-2.0 为主），如果后续要做"通用工具链先验"的对照实验（如跨域课程学习），素材是现成的——但这是可选项，不是当前主线。
4. **论文叙事的外部锚点齐了**：正面 DAPT 先例（K2/GeoGalactica）vs 本项目负结果、shortcut learning vs echo 诊断、constrained decoding vs V2a 教训、20 年 geooperator 形式化谱系 vs L3——每条内部结论都有文献对话对象。

## 八、检索方法与失败记录

- 检索面：arXiv API（https，17 组 query）+ OpenAlex（4 组）+ HF API（4 组）+ GitHub 仓库页 WebFetch（3 个仓库）。
- **GitHub REST API 仍被 IP 级限流**（本机出口 IP 共享配额，`rate_limit` remaining=0 持续两天）——仓库核验全部改走 WebFetch HTML，未受影响。
- **xLAM GitHub 仓库 URL 404**（SalesforceAIStudio/xLAM 不存在或已改名），改由 HF API 确认 `Salesforce/xlam-function-calling-60k`。
- 未覆盖：CNKI 中文文献（"地理处理工作流推荐"等中文线）需要 CDP 浏览器自动化，未在本轮开启——如需要可单独开一轮。

## 来源

[TaskBench](https://arxiv.org/abs/2311.18760) · [HF microsoft/Taskbench](https://huggingface.co/datasets/microsoft/Taskbench) · [WorkflowLLM](https://arxiv.org/abs/2411.05451) · [ToolLLM/ToolBench](https://arxiv.org/abs/2305.16504) · [GitHub OpenBMB/ToolBench](https://github.com/OpenBMB/ToolBench) · [APIGen](https://arxiv.org/abs/2406.18518) · [HF Salesforce/xlam-function-calling-60k](https://huggingface.co/datasets/Salesforce/xlam-function-calling-60k) · [Gorilla](https://arxiv.org/abs/2305.15334) · [GitHub ShishirPatil/gorilla](https://github.com/ShishirPatil/gorilla) · [WorfBench](https://arxiv.org/abs/2410.07869) · [ToolACE](https://arxiv.org/abs/2409.00920) · [API-Bank](https://arxiv.org/abs/2304.08244) · [Seal-Tools](https://arxiv.org/abs/2405.08355) · [APIGen-MT](https://arxiv.org/abs/2504.03601) · [Self-Instruct](https://arxiv.org/abs/2212.10560) · [WizardLM](https://arxiv.org/abs/2304.12244) · [Magpie](https://arxiv.org/abs/2406.08464) · [PersonaHub](https://arxiv.org/abs/2406.20094) · [K2](https://arxiv.org/abs/2306.05064) · [GeoGalactica](https://arxiv.org/abs/2401.00434) · [Geoscience Meets Foundation Models](https://arxiv.org/abs/2309.06799) · [Shortcut Learning of LLMs](https://arxiv.org/abs/2208.11857) · [AdapTrack](https://arxiv.org/abs/2510.17376) · [Sketch-Guided Constrained Decoding](https://arxiv.org/abs/2401.09967)
