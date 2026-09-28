# 外部 GIS 训练数据资源调研 v1

日期：2026-09-16
性质：paper_v2 数据规划前置调研。**只读调研**：未下载、未消费任何外部数据；未修改任何 authority/评测/checkpoint；未产生训练行。
报告定位：回答"外部世界有没有更好的训练样本"——覆盖论文开源数据集、GEE↔QGIS 算子映射资源、GitHub 开源资源三类。

## 背景与价值判断标准

benchmark v0.2.1 的 gold 是 **parameter-free QGIS 算子 DAG**（`processes + links`，operator_id 为 `native:*` 等），L3 只出现在构造侧与模型侧——gold 与指标中没有任何 L3 code。据此，外部数据的价值判断标准只有三条：

1. 能否提供 **NL 意图 → 算子链/DAG** 的配对监督（直接对口：SFT 是转写、benchmark 考意图的错位是第一约束）；
2. 能否提供 **QGIS 侧多步 DAG 监督**（`.model3` 与 gold 格式同构）；
3. 能否提供 **GEE↔QGIS / 跨平台算子映射**（吃掉 GEE 8,283 行存量 + 修 78/128 无桥问题）。

## 核心结论

1. **不存在现成的"NL 意图 → QGIS 算子 DAG"训练集**——Hugging Face 与学术文献双空白。这是坏事（自建成本）也是机会（dataset contribution：谁先建谁先得）。
2. **三条可转化的外部增量**：GeoAnalystBench（Apache-2.0，唯一 license 干净）、AutoGEEval-plus（2,612 用例，无 license）、GISAgentBench（349 任务，GIS Stack Exchange 来源，仓库未公开）。
3. **GEE↔QGIS / ArcPy↔QGIS 算子 crosswalk 在外部世界不存在**（学术检索 + GitHub 检索均无）——内部 KG（350 L3 同时挂 GEE 1,425 + QGIS 1,291 算子）是已知唯一实现，应在论文中作为贡献显式声明。
4. 外部资源角色定位 = **评测集 + 意图重写种子/few-shot + 引用对标**；意图重写的主料仍是内部 25.7 万脚本描述库（已定位哈希验证）。

## 一、已核验资源清单

核验等级说明：【仓库核验】= 直接访问 GitHub 仓库页确认了文件结构与 license；【摘要核验】= arXiv 摘要页确认了论文内容，仓库/数据未直接核验。

### A. 立即可用（license 干净）

| 资源 | 核验 | 内容与形态 | 与项目的对接方式 |
|---|---|---|---|
| **GeoAnalystBench**<br>[GeoDS/GeoAnalystBench](https://github.com/GeoDS/GeoAnalystBench)（55★）<br>arXiv [2509.05881](https://arxiv.org/abs/2509.05881)，Trans. in GIS 2025 | 【仓库核验】Apache-2.0；数据 `dataset/GeoAnalystBench.csv` + Google Drive 原始数据 | 50 个真实任务 × 3-10 子任务；每条含 NL 指令 + 领域知识 + 数据集描述 + **人工编号工作流** + 参考 Python 代码；GIS 专家验证；来源 ArcGIS Learn 教程 / SciTools Iris / geoplot / 学术论文 | 唯一 license 干净的**意图式** NL→工作流数据（~150-300 子任务级样本）。三个用途：①意图式 OOD dev/评测集 ②意图重写器的 few-shot 种子/模板参照 ③跨模型对照。需 ArcPy/geopandas→L3 映射（复用 GEE→L3 方法论，一次性工程）。注意：工作流在 ArcPy 生态侧，非 QGIS 算子 |
| **GEE-Ops / Geo-SORB**<br>[whuhsy/GEE-Ops](https://github.com/whuhsy/GEE-Ops)（3★）<br>arXiv [2412.05587](https://arxiv.org/abs/2412.05587) | 【仓库核验】**无 license**（数据已可下载，复用需联系作者 whuhsy） | 从真实 GEE 脚本（论文称 185,236 个）AST 挖掘的：算子链 CSV（`1302_Chain_from_AST_clean.csv`）、频繁项集/关联规则（SPMF）、sequential/parallel/nested 关系 JSON、调用频次表 + 完整挖掘管线代码 | 与项目 L3 链挖掘**直接同构**的平行工作：①related work 引用与对比基线 ②其关联规则/共现表可补充 KG 的 GEE 侧先验 ③管线方法论互证 |

### B. 可用但需联系作者（无 license / 未挂仓库）

| 资源 | 核验 | 内容 | 价值与风险 |
|---|---|---|---|
| **AutoGEEval-plus**<br>[szx-0633/AutoGEEval-plus](https://github.com/szx-0633/AutoGEEval-plus)（3★）<br>论文 [2506.10365](https://arxiv.org/abs/2506.10365)（AutoGEEval++） | 【仓库核验】**无 license**；`test_code/` 含原子 1,325 / 组合 1,199 / 场景 88 = **2,612 个测试用例**（README 口径；论文称 6,365，存在差异待确认）；LLM 生成 + 人工审校 | 格式 = NL 指令 + 参考 GEE Python 代码；另含 `frequent_operator_chain_mining.py` + spmf.jar | **最大可直接转化的意图式数据源**：GEE→L3 映射内部已有，NL→GEE code 可机械转 NL 意图→L3 链；组合+场景级 1,287 条是多步意图监督。风险：无 license（学术用途通常可谈）、原子级占一半、规模口径不一 |
| **GISAgentBench**<br>arXiv [2608.01645](https://arxiv.org/abs/2608.01645)（2026-08） | 【全文核验 2026-09-22】CC BY 4.0（论文）；仓库未公开 | **349 个多步 GIS 任务，全部来自 GIS Stack Exchange 实践者真实问题**；128 个类型化 GIS API 固定 harness，**约 2/3 经 qgis_process 分发到 QGIS processing 算子**（含 GDAL 后端），1/3 为 GeoPandas/Rasterio/Shapely 等 Python 栈；无 ArcGIS；金标 = 可执行参考轨迹（2-43 步，均值 11.7）+ 精确输出文件；评分 = 任务级输出容差匹配，轨迹对比仅粗类别诊断；最强 agent 仅解 32.7% | **价值升级（2026-09-22 全文核验）**：动作空间即 QGIS 算子级（选算子+填参+排序，ReAct 工具调用，非自由代码），轨迹中约 2/3 步骤（~4,000 步中 ~2,700 步）直接是 QGIS 算子调用——转化为算子级监督的成本低于自由代码类基准。转化四道工序：128 自定义 API↔原生算子映射 / 参数剥离至 parameter-free / Python 栈步骤映射缺口 / 仓库未公开（需联系作者） |
| **GIS Copilot**<br>arXiv [2411.03205](https://arxiv.org/abs/2411.03205)（Li 组，OpenAlex 引用 52） | 【摘要核验】摘要页无仓库链接（GitHub 搜索受限流影响，可复查） | QGIS 原生 agent：100+ 空间分析任务（单工具 / 多步用户引导 / 多步自主三级）+ QGIS 工具与参数全量文档 | 工具文档部分与内部 Neo4j KG 互补；任务集若公开可作 QGIS 侧意图式补充 |

### C. 相关但不直接可用（评测范式 / 引用价值）

| 资源 | 核验 | 说明 |
|---|---|---|
| **GeoAgentBench** arXiv [2604.13888](https://arxiv.org/abs/2604.13888)（2026-04） | 【摘要核验】+ 3 个 GitHub 同名仓库（0★，未确证官方） | 117 原子 GIS 工具、53 任务、6 领域、执行沙盒、参数执行准确率（PEA）指标——**评测范式可借鉴**（执行式验证 vs 我们的 lock scorer） |
| **GeoNatureAgent** arXiv [2606.12821](https://arxiv.org/abs/2606.12821)（SIGSPATIAL 2026） | 【摘要核验】 | 93 任务 / 18 类 / 16 工具，生产级 API，西班牙葡萄牙环境指标；结论：结构化工具调用比通用 benchmark 低 25-35 分 |
| **QGIS Hub 模型库** [hub.qgis.org/models](https://hub.qgis.org/models/) | 【站点核验】 | 官方共享 .model3 仅 **30 个**（带 API `/api/v1/resources/`）；量太小，只能当种子/评测样本/DAG 结构参照 |
| **GeoScience-QGIS-CUA**（HF） | 【站点核验】 | 28.1GB GUI-agent 轨迹 bundle（截图+动作+计费），gated、禁止再分发 GT、仅 3 任务——不适用 |
| **GeoCode-Eval / GeoCode-Bench** arXiv [2410.09738](https://arxiv.org/abs/2410.09738) | 【摘要核验】 | 5,000 选择 + 1,500 填空 + 1,500 判断 + 1,000 主观题——知识考核型，非工作流生成 |
| **qgis-earthengine**（gee-community 官方插件） | 【搜索核验】 | GEE 运行时嵌入 QGIS 的集成插件，**不是算子映射表** |
| **awesome-gee-community-catalog / Awesome-EarthEngine** | 【搜索核验】 | GEE 资源目录（数据集/工具为主），无统一脚本 dump |
| GEE 侧其他论文 | 【摘要核验】 | Evaluation of Code LLMs on Geospatial Code Generation (2410.04617)、CoP for Geospatial Code (2411.10753)、IC-EO (2602.00117)、LLM Agent for Automatic Geospatial Data Analysis (2410.18792)、GeoJSON Agents (2509.08863)——引用价值 |

### related work 备选（老线，非 LLM 时代）

- Autonomous GIS 愿景线：Autonomous GIS (2305.06453)、GIScience-in-the-Era-of-AI 议程 (2503.23633)、GeoGPT (2307.07930 / RAG 2509.09686)、GIS 数据检索 agent (2407.21024)、Spatial Text-to-SQL 多 agent (2510.21045)
- 算子语义形式化线（与 L3 taxonomy 同族）：geooperators 形式化 (2015, OpenAlex)、SHACL 参数约束 (2021)、GeoJModelBuilder (2017)、GeoSquare (2015)——工作流建模工具/形式化方法，无数据集

## 二、五大数据约束匹配分析

| 数据约束 | 外部资源能否补 | 判定 |
|---|---|---|
| ① 任务形态错位（转写 vs 意图）— 最大单项 | AutoGEEval 组合/场景级 1,287 + GeoAnalystBench ~200 + GISAgentBench 349 ≈ **~1,800 条意图式样本**（需转化/授权/获取） | ✅ 能补但量级有限；**25.7 万内部描述库仍是主力**，外部做种子+评测 |
| ② QGIS 监督薄 + 语言/长度错配 | GeoAnalystBench 英文+多步但 ArcPy 生态；QGIS 侧无直接新增 | ⚠️ 部分（间接，需跨平台映射） |
| ③ L3 桥接损耗（78/128 无桥） | 外部无映射表；GEE-Ops 提供 GEE 侧算子关系辅助 | ❌ 基本要靠自己修（架构侧） |
| ④ 拓扑天花板（DAG） | .model3 是 DAG 但仅 30 个；无外部 DAG 监督语料 | ❌ 无外部解 |
| ⑤ 长尾算子 | AutoGEEval 原子级 1,325 覆盖 GEE 函数面 | ⚠️ GEE 侧可以，QGIS 侧不行 |

## 三、关键判断

1. **主次关系不变**：paper_v2 意图重写主料 = 内部 25.7 万描述库。外部数据最优角色：①意图式 OOD 评测集（GeoAnalystBench 可立即充当）②重写器种子/few-shot 模板（AutoGEEval 的 question 是真意图——答案算子不在题面，正是 8,201 行 answer-echo 数据缺的性质）③引用对标。
2. **稀缺性是双刃剑**：无现成数据集 = 自建成本高；但"首个开源的 intent-form QGIS workflow supervision set"是合格的 dataset contribution。
3. **唯一没有的映射恰恰是内部已有的**：GEE↔L3↔QGIS 三层映射外部不存在——论文 KG 贡献点应显式声明。
4. **方法论有平行佐证**：GEE-Ops/Geo-FuB（18.5 万 / 15.4 万脚本）用 AST+频繁项集挖掘 GIS 算子链，与内部管线同构——related work 可写"该方向活跃但无人做 QGIS 侧意图式监督"。

## 四、建议行动（未批准，待 owner 拍板）

1. **立即可做**（半小时级）：克隆 GeoAnalystBench（Apache-2.0）+ GEE-Ops 仓库做结构审计——前者进评测/种子池候选，后者进引用与对比。
2. **本周可做**：邮件联系 AutoGEEval-plus 作者（szx-0633）询问 license/学术复用授权；从 GISAgentBench (2608.01645) PDF 找仓库链接或联系作者。
3. **paper_v2 设计时**：把 AutoGEEval 组合/场景级用例作为意图重写格式参照；GeoAnalystBench 子任务作为意图式 dev 评测候选。
4. **暂缓**：GitHub 全量 .model3 / PyQGIS 脚本爬取（GitHub 搜索限流中；内部 47,852 源码池已覆盖大部分可及语料，边际收益低）。

## 五、调研方法与失败记录（操作注意，供后续调研会话复用）

- **检索面**：arXiv API（https，5 组 query 电池 + id_list 批量摘要）、OpenAlex API、GitHub API + 仓库页 WebFetch、Hugging Face API、QGIS Hub 站点。
- **arXiv API 必须用 https**：`http://export.arxiv.org` 在本机静默失败（curl exit=0 但 0 字节）。
- **Semantic Scholar 无 key 必 429**：本次放弃 S2，用 OpenAlex 替代（完全开放）。
- **GitHub API 匿名配额 60/hr 极易用尽**；HTML 搜索被 429 且 Retry-After 3600——GitHub 全量语料扫描（.model3 / PyQGIS 脚本）未完成，如需要应在服务器侧或配额恢复后做。
- **WebSearch 工具会返回不可靠结果**：本次曾返回（a）自称"simulated response"的占位内容、（b）错误的 LLM-Geo arXiv ID（2405.15266，实际是机器人学论文，经 WebFetch 核验排除）。**本报告所有结论均以直接核验（仓库页/API 原始响应）为准，未采信任何未核验的搜索摘要。**
- 论文侧规模数字（任务数/脚本数）以 arXiv 摘要为准，标注【摘要核验】，仓库未逐条复核。

## 来源

[GeoAnalystBench](https://github.com/GeoDS/GeoAnalystBench) · [AutoGEEval](https://github.com/szx-0633/AutoGEEval) · [AutoGEEval-plus](https://github.com/szx-0633/AutoGEEval-plus) · [GEE-Ops/SORB](https://github.com/whuhsy/GEE-Ops) · [GISAgentBench](https://arxiv.org/abs/2608.01645) · [GeoAgentBench](https://arxiv.org/abs/2604.13888) · [GIS Copilot](https://arxiv.org/abs/2411.03205) · [AutoGEEval++](https://arxiv.org/abs/2506.10365) · [AutoGEEval](https://arxiv.org/abs/2505.12900) · [GEE-OPs](https://arxiv.org/abs/2412.05587) · [Geo-FuB](https://arxiv.org/abs/2410.20975) · [GeoNatureAgent](https://arxiv.org/abs/2606.12821) · [GeoCode-Eval](https://arxiv.org/abs/2410.09738) · [QGIS Hub Models](https://hub.qgis.org/models/) · [qgis-earthengine](https://github.com/gee-community/qgis-earthengine) · [awesome-gee-community-catalog](https://github.com/gee-community/awesome-gee-community-catalog) · [Awesome-EarthEngine](https://github.com/sacridini/Awesome-EarthEngine) · [GeoScience-QGIS-CUA](https://huggingface.co/datasets/daipath/GeoScience-QGIS-CUA)
