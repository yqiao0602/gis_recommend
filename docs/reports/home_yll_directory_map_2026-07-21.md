# `/home/yll` 数据目录地图（2026-07-21）

## 盘点方式

- 服务器：`qy@10.191.2.38`
- 源目录：`/home/yll`，全程只读
- 遍历粒度：没有子目录的叶子目录
- 每个叶子目录记录：路径、直接文件数、扩展名分布、内容类别、随机 2 个文件及最多 800 字节正文预览
- 完整逐目录记录：`/home/qy/home_yll_inventory/leaf_samples_20260721.jsonl`
- 完整记录共 `50,155` 条，文件约 `75 MB`
- `49,143` 个叶子目录成功抽样，`1,011` 个为空或无普通文件；`/home/yll/.ssh` 仅登记路径，未读取正文

## 顶层结论

| 路径 | 约容量 | 叶子目录 | 实际内容 |
|---|---:|---:|---|
| `/home/yll/GEE` | 101 GB | 13,613 | GIS 源码爬取、清洗分层、AST/步骤图抽取、匹配结果、描述知识、训练数据和处理脚本 |
| `/home/yll/zAPI_data` | 71 GB | 35 | 约 70 GB 模型权重，以及 GeoSFT/GEE 指令数据、LoRA 训练代码、评测材料 |
| `/home/yll/anaconda3` | 23 GB | 33,156 | Python/Conda 环境和第三方包，不是业务数据 |
| `/home/yll/.cache` | 15 GB | 876 | 模型、编译和软件下载缓存，不是权威数据 |
| `/home/yll/anaconda` | 1.1 GB | 1 | 安装包或旧环境文件，不是业务数据 |
| 其他隐藏目录 | < 1 GB/项 | 2,473 | VS Code、npm、PaddleX、本地包和工具缓存 |

因此真正需要找数据时，先看 `/home/yll/GEE`；需要找训练模型和大模型微调数据时，再看 `/home/yll/zAPI_data`。

## 原始和半原始爬取数据

| 目录 | 约容量/文件数 | 随机文件中实际看到的内容 |
|---|---:|---|
| `/home/yll/GEE/爬取GithubQGIS` | 3.1 GB / 307,300 文件 | PyQGIS/QGIS 插件 Python 源码；每条源码对应的 JSON 元数据；CSV 索引；合并和按索引去重后的副本。元数据含仓库、查询词、原始路径、SHA、工作流等级等字段 |
| `/home/yll/GEE/爬取多源数据源/QGIS_Official_Plugins` | 6.9 GB / 128,645 文件 | QGIS 官方插件解压后的完整目录树，包含算法、对话框、README、图标和插件资源；不是只有工作流脚本 |
| `/home/yll/GEE/爬取多源数据源/QGIS_Core_Processing` | 81 MB / 3,485 文件 | QGIS Core/Processing 源码树、测试和构建配置，同时有扫描 CSV 和 summary JSON |
| `/home/yll/GEE/爬取多源数据源/QGIS_Model_Tutorial_Workflows` | 36 MB | QGIS Model/教程工作流候选及采集结果 |
| `/home/yll/GEE/爬取多源数据源/QGIS_Plugins_GitLab_Supplement` | 483 MB | GitLab/官方插件补充抓取、插件索引和状态文件 |
| `/home/yll/GEE/QGIS_ArcGIS_RouteB_Gitee_GitLab` | 47 MB | 来自 Gitee/GitLab 的 QGIS/ArcGIS 源码；样本含 `QgsProcessingAlgorithm` 插件算法代码 |
| `/home/yll/GEE/爬取GithubGEE/GEE_GitHub_Incremental_Harvest` | 189 MB / 11,453 文件 | GEE JavaScript 示例和教程代码、爬虫状态、元数据；样本直接使用 `ee.ImageCollection`、Sentinel/Landsat 数据和 `Map.addLayer` |
| `/home/yll/GEE/爬取gee脚本/collected_scripts` | 27 GB / 172,823 文件 | 按 Python、JavaScript、Jupyter Notebook、R 分目录收集的通用脚本。随机样本出现普通 R 海洋分析代码，说明该目录不是纯 GEE |
| `/home/yll/GEE/爬取gee脚本/爬取PWCGEE` | 546 MB / 308,663 文件 | Papers With Code 仓库元数据和脚本。`raw_meta` 随机样本明确出现 `is_gee: false` 的深度学习仓库；真正 GEE 内容主要在 `pwc_scripts_output/js_gee_scripts`，不能把整个目录算作 GEE |
| `/home/yll/GEE/爬取GithubArcGIS` | 2.2 GB | ArcPy/ArcGIS Python、Notebook 转存文本、逐脚本 JSON 元数据、合并去重副本 |
| `/home/yll/GEE/爬取EsriGithubCommunity` | 698 KB | Esri GitHub 工作流脚本和 Community 帖子索引；样本是 ArcGIS 网络分析/并行处理脚本 |
| `/home/yll/GEE/爬取GIS代码` | 1.2 GB | QGIS/ArcGIS 教材、教学仓库和候选代码；同时包含测试、GUI、provider 支持代码，不全是工作流 |
| `/home/yll/GEE/爬取Zenodo网站` | 15 GB | Zenodo 下载、解压、平台分类和筛选结果。即使位于 `zenodo_extracted/QGIS`，随机样本也可能只是通用 Python 工程代码，平台分类存在噪声 |
| `/home/yll/GEE/爬取HuggingFace` | 2 MB | HuggingFace/Papers With Code 候选仓库状态、索引和少量 QGIS/ArcGIS 源码，体量较小且含弱候选 |

## 整理、抽取和派生结果

| 目录 | 约容量/文件数 | 实际内容 |
|---|---:|---|
| `/home/yll/GEE/Data` | 3.5 GB | 分批编号源码库。`data0` 至 `data400000` 的随机样本主要是 GEE JavaScript 文本；`data-QGIS` 是 Python；`data-ArcGIS` 是 ArcPy；`*_AST_failed` 是解析失败脚本 |
| `/home/yll/GEE/Data/data-QGIS` | 53,569 文件 | 已整理的 QGIS Python 源码，不是 AST 结果 |
| `/home/yll/GEE/Data/data-QGIS_remaining_layered_after_strict` | 62,876 文件 | 严格 QGIS 集之外的分层剩余源码，仍属于候选源码池 |
| `/home/yll/GEE/工作流抽取结果` | 37 GB | AST JSON，以及 steps/data/edges/process_relations 等 CSV；这是源码派生的结构化抽取产物，不是原始源码 |
| `/home/yll/GEE/工作流抽取结果/QGIS` | 262,901 文件 | QGIS AST、步骤、数据节点、边和关系 CSV。随机样本为 Python AST JSON 和节点表；该目录不能当作 QGIS 源码总量 |
| `/home/yll/GEE/匹配` | 159 MB | 抽取步骤到标准函数路径/算子的匹配结果、审核 CSV、缓存和匹配脚本。样本 JSON 含 Process、Operator、数据流和 QGIS 参数同步信息 |
| `/home/yll/GEE/描述性知识抽取汇总` | 216 MB | `facts_summary*.csv`，字段包括任务类型、任务名、数据源、地理值、时间范围和自然语言任务描述；随机样本主要为 GEE 遥感任务 |
| `/home/yll/GEE/描述性知识抽取qgis_chain_selected_script` | 50 MB | 针对 QGIS 链选择脚本的描述性知识抽取结果 |
| `/home/yll/GEE/源代码模板去重` | 122 MB | 去重程序、代码 hash、模板分组、代表脚本和重复计数；CSV 引用 `Data` 中的源码路径，本身不是源码语料 |
| `/home/yll/GEE/筛选ArcGIS工作流` | 458 MB | 按 A 高质量/B 候选等层级筛出的 ArcPy 工作流源码 |
| `/home/yll/GEE/筛选QGIS工作流` | 20 KB | QGIS 分层、去重和剩余候选处理脚本，数据主体在 `Data/data-QGIS*` |
| `/home/yll/GEE/筛选精评样本` | 1 MB | 少量人工精评候选、复杂度和调用预览 CSV，以及被选中的 QGIS 源码 |
| `/home/yll/GEE/workflow/1-Training Data` | 28 MB 所在目录 | GEE 指令到工作流步骤/API 的 JSONL 训练对；同目录还有格式转换和抽取程序 |
| `/home/yll/GEE/文献抽取` | 441 MB | 文献下载、卫星/传感器/波段知识表、RDF/CSV 处理代码和模型试验脚本 |

## `zAPI_data` 实际内容

| 目录 | 约容量 | 实际内容 |
|---|---:|---|
| `/home/yll/zAPI_data/3-Model` | 70 GB | Base Model、GeoTool-GPT、LoRA adapter、合并模型和试验模型，是整个目录的主要容量来源 |
| `/home/yll/zAPI_data/1-TrainingData` | 1.1 MB | ArcGIS 工具箱/工具元数据 JSON、Alpaca 数据处理和训练/评估拆分脚本 |
| `/home/yll/zAPI_data/Data` | 475 MB | `BB-GeoSFT.json` GIS 问答指令数据及 HuggingFace Arrow 缓存；缓存元数据显示 35,876 条训练样本 |
| `/home/yll/zAPI_data/DEEdata` | 5.2 MB | GEE 用户目标到工作流步骤/API 的 conversational、Alpaca 和 Markdown 格式训练数据 |
| `/home/yll/zAPI_data/ceshiDEE` | 44 MB | GEE API 解释和标准化工作流数据，以及 tokenized HuggingFace Dataset 缓存 |
| `/home/yll/zAPI_data/2-TrainingCode` | 51 KB | LLaMA/LoRA SFT、DeepSpeed ZeRO-2、FlashAttention 补丁和训练启动代码 |
| `/home/yll/zAPI_data/Evaluation` | 110 KB | 客观题和主观题 Excel 评测材料 |

## QGIS 数据去哪里找

### 九个主要原始源码池的当前规模

2026-07-21 对下列九个目录递归统计 `.py`，并按**原始文件字节 SHA256** 去重。这里统计的是源码路径和不同源码内容，不是抽取组、AST/CSV 产物或最终训练样本。

| 来源目录 | `.py` 路径数 |
|---|---:|
| GitHub QGIS 七源合并去重目录 | 54,240 |
| `QGIS_Official_Plugins` | 44,536 |
| `QGIS_Plugins_GitLab_Supplement` | 3,410 |
| `QGIS_Core_Processing/workflow_scripts` | 110 |
| `QGIS_Model_Tutorial_Workflows` | 846 |
| `QGIS_ArcGIS_RouteB_Gitee_GitLab/downloaded_scripts` | 4,302 |
| `zenodo_extracted/QGIS` | 444 |
| `爬取PWCQGIS/downloaded_scripts` | 1,183 |
| `QGIS_ArcGIS_Textbook_Candidates_Broad/downloaded_scripts_strict` | 19,958 |
| **合计** | **129,029** |

- 129,029 个路径按源码字节去重后为 **112,758 个唯一 SHA256**，说明跨来源或目录阶段至少存在 16,271 个内容副本。
- 其中 **88,400 个路径**出现强 QGIS 代码信号，按内容去重后为 **80,998 份不同源码**。强信号口径为出现 QGIS import、`Qgs*`、`processing.run`、`QgisAlgorithm` 或 `QgsProcessingAlgorithm` 等模式。
- `80,998` 是当前更合理的“大 QGIS 源码候选池”，但仍含插件实现、GUI、test、provider、support、Core 算子实现和单步/低层 API 代码，不能直接作为训练条数。
- GitHub 合并目录的历史报告记录 54,231 个唯一脚本；当前实测 54,240 个 `.py`，多出的 9 个反映目录后来发生过变动，报告口径和当前文件系统口径应分别保留。
- 完整 hash 清单位于 `/home/qy/home_yll_inventory/qgis_raw_py_hashes_20260721.tsv`；强信号路径清单位于 `/home/qy/home_yll_inventory/qgis_raw_py_strong_signal_paths_20260721.nul`。`/home/yll` 未被修改。

对 80,998 份强信号唯一源码进一步做 AST 静态分层后：catalog 精确多步 Processing 3,938、精确单步 2,534、Processing 待解决 8,466、低层 PyQGIS API 候选 39,386、排除/隔离 26,674。这里的 3,938 仍需验证顺序、依赖、工作流角色和 stable-94 L3，不能直接作为训练量。详见 `docs/reports/qgis_corpus_layering_2026-07-21.md`。

### 原始或接近原始源码

1. `/home/yll/GEE/爬取GithubQGIS`
2. `/home/yll/GEE/爬取多源数据源/QGIS_Official_Plugins`
3. `/home/yll/GEE/爬取多源数据源/QGIS_Core_Processing`
4. `/home/yll/GEE/爬取多源数据源/QGIS_Model_Tutorial_Workflows`
5. `/home/yll/GEE/爬取多源数据源/QGIS_Plugins_GitLab_Supplement`
6. `/home/yll/GEE/QGIS_ArcGIS_RouteB_Gitee_GitLab`
7. `/home/yll/GEE/爬取GIS代码/QGIS_ArcGIS_Textbook_Candidates_Broad`
8. `/home/yll/GEE/爬取Zenodo网站/zenodo_extracted/QGIS`，但平台噪声较高

### 整理后的 QGIS 源码

1. `/home/yll/GEE/Data/data-QGIS`
2. `/home/yll/GEE/Data/data-QGIS_remaining_layered_after_strict`
3. `/home/yll/GEE/筛选ArcGIS工作流` 不是 QGIS，不应混用

### QGIS 派生产物

1. `/home/yll/GEE/工作流抽取结果/QGIS`
2. `/home/yll/GEE/匹配/output_qgis_*`
3. `/home/yll/GEE/描述性知识抽取qgis_chain_selected_script`
4. `/home/yll/GEE/筛选精评样本/筛选_qgis_精评样本`

## GEE 数据去哪里找

### 原始或接近原始脚本

1. `/home/yll/GEE/爬取GithubGEE/GEE_GitHub_Incremental_Harvest/downloaded_scripts*`
2. `/home/yll/GEE/爬取gee脚本/爬取PWCGEE/pwc_scripts_output/js_gee_scripts`
3. `/home/yll/GEE/爬取gee脚本/collected_scripts/JavaScript`，但整个 `collected_scripts` 不是纯 GEE

### 整理后的 GEE 脚本和派生数据

1. `/home/yll/GEE/Data/data0` 至 `/home/yll/GEE/Data/data400000`
2. `/home/yll/GEE/描述性知识抽取汇总/facts_summary*.csv`
3. `/home/yll/GEE/workflow/1-Training Data`
4. `/home/yll/zAPI_data/DEEdata`
5. `/home/yll/zAPI_data/ceshiDEE`

## 内容抽样暴露出的主要问题

1. 名为“GEE”的目录不一定是纯 GEE：`爬取PWCGEE/raw_meta` 中有大量 `is_gee: false`，`collected_scripts` 也包含普通 R/Python 代码。
2. 名为“QGIS”的分类目录不一定每个文件都使用 QGIS API：Zenodo、教材和宽松候选中存在通用 Python、测试、GUI 和支持代码。
3. `工作流抽取结果/QGIS` 是 CSV/JSON 派生产物，不是 QGIS 源码目录。
4. `爬取GithubQGIS/合并脚本` 与各原始抓取子目录存在源码和元数据副本，查原始来源时优先使用索引中的 `repo_full_name`、`file_path` 和 `content_sha1`。
5. `/home/yll/zAPI_data` 的 71 GB 主要是模型权重，不是新爬取的源码数据。

## 指定目录的进一步内容核实

### `/home/yll/GEE/爬取EsriGithubCommunity/Esri_Github_Community_Scraper/github_workflow_scripts`

- 约 686 KB，共 26 个 Python 文件。
- 随机样本为 Esri 官方网络分析、OD Cost Matrix、交通可达性和 TomTom 网络数据处理脚本。
- 22/26 个文件有明确 ArcPy 调用，0/26 有强 QGIS/PyQGIS 信号。
- 结论：这是 ArcGIS/Esri 工作流补充源，不应进入 QGIS 数据构造。

### `/home/yll/GEE/QGIS_ArcGIS_RouteB_Gitee_GitLab`

- 约 47 MB，共 4,319 个文件，其中 `downloaded_scripts` 有 4,302 个 Python 文件。
- 源码头包含来源平台、仓库、原始路径和 URL；随机样本包含 `QgsProject`、`QgsVectorLayer`、`QgsProcessingAlgorithm` 等真实 PyQGIS 代码。
- 3,659 个脚本有强 QGIS/PyQGIS 或 `processing.run` 信号。
- `routeB_gitee_gitlab_index.csv` 只有 198 条数据记录，明显没有覆盖当前全部 4,302 个脚本，不能单独作为完整索引。
- 对应抽取结果：`/home/yll/GEE/工作流抽取结果/QGIS/WorkflowoutputQGIS_ArcGIS_RouteB_Gitee_GitLab`，共 18,480 个五类产物，即 3,696 组脚本。
- 结论：可作为 GitLab/Gitee QGIS 补充源码池，但应使用源码头、hash 和抽取产物联合确定来源。

### `/home/yll/GEE/爬取多源数据源/QGIS_Model_Tutorial_Workflows`

- 约 36 MB，共 2,755 个文件。
- `downloaded_scripts`：851 个采集脚本；随机样本是 QGIS Processing 模型导出代码、插件算法和教程代码。
- `qgis_model_tutorial_metadata`：851 个 JSON，记录仓库、原始文档路径、保存路径、采集原因、`processing_run_count`、算子 ID、model/QGIS 信号和内容 hash。
- `qgis_model_tutorial_index.csv`：851 条记录；810 条包含至少一次 `processing.run`，482 条有 model 信号，849 条有 QGIS 信号。
- `downloaded_scripts 清洗后`、`downloaded_scriptsast3` 是同批数据的清洗/AST 阶段，不应与原始 851 条重复计数。
- 对应抽取结果：`/home/yll/GEE/工作流抽取结果/QGIS/WorkflowoutputQGIS_Model_Tutorial_Workflows`，260 组脚本、1,300 个五类产物。
- 结论：这是显式 Processing 多步链的高价值来源，优先级高于宽松插件和 Zenodo 候选。

### `/home/yll/GEE/爬取多源数据源/QGIS_Core_Processing/workflow_scripts`

- 约 892 KB，共 110 个 Python 文件。
- `qgis_core_processing_candidates.csv` 将它们分为 93 个 `algorithm_script`、14 个 `processing_support_script`、3 个 `provider_script`。
- 随机样本为 QGIS/GDAL Processing 算子的实现类，例如 fill nodata、slope、offset curve，包含 `name()`、`displayName()`、`initAlgorithm()`、`processAlgorithm()` 和参数定义。
- 这些文件是“算子实现/目录依据”，不是用户多步工作流；适合确认算子名称、参数和语义，不适合直接当自然语言到工作流训练样本。
- 对应抽取结果位于 QGIS 子目录之外：`/home/yll/GEE/工作流抽取结果/WorkflowoutputQGIS_QGIS_Core_Processing`，共 554 个 AST/steps/data/edges/relations 文件。

### `/home/yll/GEE/爬取Zenodo网站/zenodo_extracted/QGIS`

- 约 1.7 MB，共 444 个 Python 文件。
- 只有 48 个文件有强 QGIS/PyQGIS 或 `processing.run` 信号。
- 随机样本大量来自 qGreenland/Luigi/通用 Python 工程，说明 `QGIS` 分类只是宽松平台候选，不代表每个文件都是 QGIS 工作流。
- `QGIS_script_url_mapping.txt` 可回溯脚本到 Zenodo DOI。
- 对应抽取结果：`/home/yll/GEE/工作流抽取结果/QGIS/Workflowoutput爬取Zenodo网站QGIS`，426 组脚本、2,130 个五类产物。
- 结论：必须二次过滤，不能把 444 条全部纳入 QGIS。

### `/home/yll/GEE/爬取gee脚本/爬取PWCQGIS`

- 约 19 MB，共 1,191 个文件，其中 `downloaded_scripts` 有 1,183 个 Python 文件。
- `downloaded_index.csv` 只记录 PWC 仓库、论文、文件路径和下载 URL，没有可靠的 QGIS 判定字段。
- 随机样本包含普通表格学习、气候数据下载和栅格类别统计代码；只有 30/1,183 个脚本有强 QGIS/PyQGIS 或 `processing.run` 信号。
- 对应抽取组 `WorkflowoutputPWCQGIS` 有 5,915 个五类产物，恰好对应 1,183 组脚本，说明抽取阶段基本覆盖了整个下载目录，而不是只覆盖 30 个强 QGIS 样本。
- 结论：这是高污染候选池，当前不能作为 QGIS 权威源码目录；必须先做 QGIS 强信号和内容审核。

## QGIS 数据构造应从哪里取

### 1. 任务级自然语言描述

首选：

- `/home/yll/GEE/描述性知识抽取qgis_chain_selected_script/facts_summary1000.csv`
- 实际为 20,428 条，不是旧文档中的约 1,000 条。
- 字段：`File Name`、`Task Type`、`Task Name`、`DataSource`、`Geospatial Values`、`Time Ranges`、`Task Description`。
- 20,428 条描述均非空，20,394 条描述唯一。
- 这是根据代码生成/抽取的 code-grounded silver 描述，不等同于人工 gold 描述。

不要直接仅按 `script_*.py` basename 连接。已经验证：

- 20,413/20,428 能匹配 AST 和 steps，15 条缺失。
- 18,526 条只有一个 extraction group。
- 1,887 条同时出现在 2-3 个 extraction group，必须用路径/hash 消歧。
- 现成关联文件：`/home/qy/system_redesign/outputs_v2/qgis_pilot/pilot_v1/phase1/facts_artifact_candidates.jsonl`。

补充描述来源：

- QGIS 官方插件 `metadata.txt`：2,009 个，`description`/`about` 是插件级用途描述。
- QGIS 官方插件 README：2,054 个，是插件/仓库级说明。
- Model/Tutorial metadata：851 个，主要提供来源、信号、算子 ID 和 hash，不一定有完整任务描述。
- 精评 CSV：2 个，提供候选复杂度、调用预览和精评选择路径。
- 源码/docstring：48,011 个候选，只能作为补充证据，不能自动当合格描述。

### 2. 源码

建议按优先级取：

1. `QGIS_Model_Tutorial_Workflows/downloaded_scripts`：显式 Processing 链最集中。
2. `爬取GithubQGIS/合并脚本/QGIS_merged_dedup_by_index/strict_multistep_spatial_workflows/downloaded_scripts_strict`。
3. `爬取GithubQGIS/合并脚本/QGIS_merged_dedup_by_index/qgis_processing_chained_workflows/downloaded_scripts`。
4. `/home/yll/GEE/Data/data-QGIS_remaining_layered_after_strict/L1_near_strict_spatial_workflow_candidates`。
5. `/home/yll/GEE/Data/data-QGIS_remaining_layered_after_strict/L2_general_qgis_processing_workflows_part1` 和 `part2`。
6. RouteB 的 `downloaded_scripts`，使用强 QGIS 信号和抽取结果筛选。
7. QGIS Official Plugins、Zenodo、PWCQGIS 只作为补充候选，不能整目录直接纳入。

`L3_support_modules`、QGIS Core Processing 实现、GUI/test/provider/support 代码应单独管理，不应与多步工作流混算。

### 3. 每一步调用及算子信息

主目录：`/home/yll/GEE/工作流抽取结果/QGIS/<extraction_group>/`。

每个已抽取脚本通常有五个文件：

- `*_ast.json`：Python AST。
- `*_steps.csv`：逐调用步骤；含 `name`、`normalized_api_name`、`raw_api_name`、参数、macro/micro 层级、QGIS 类型、语义角色、输入输出类型和描述。
- `*_data.csv`：变量、参数、对象成员等数据节点。
- `*_edges.csv`：步骤和数据之间的图边。
- `*_process_relations.csv`：步骤嵌套、顺序和依赖关系。

已核实示例：

- 源码 `QGIS_Model_Tutorial_Workflows/downloaded_scripts/script_55771.py` 调用了 `native:extractbyexpression`、`native:intersection`、`native:dissolve`、`native:refactorfields`、`native:fixgeometries` 等。
- 对应 `WorkflowoutputQGIS_Model_Tutorial_Workflows/script_55771_steps.csv` 中，`processing.run` 行被规范为准确的 literal operator ID，`api_source_type=qgis_processing_algorithm`，`semantic_role=GIS_TOOL`。
- 对应 `edges.csv` 和 `process_relations.csv` 已记录子步骤和流程关系。

覆盖口径：

- 52,422 组 AST/steps/data/edges/relations，共 262,110 个产物。
- 52,329 个路径级 script 记录，49,997 个唯一 basename。
- 8,080 个路径记录明确包含 `processing.run`。

2026-07-24补充复核：高影响阻塞算子源码片段不是从`工作流抽取结果/QGIS`直接读取，而是用该目录派生出的索引回溯到`/home/yll`真实源码。复核脚本`review_qgis_high_impact_source_snippets.py`读取服务器侧：

- `/home/qy/system_redesign/outputs_v2/qgis_corpus_screening/nine_sources_canonical_v2_layers_v2/layered_unique_content.jsonl`
- `/home/qy/system_redesign/outputs_v2/qgis_corpus_screening/nine_sources_canonical_v2/corpus_manifest.jsonl`
- `/home/yll`下的真实`source_path`

已对6个QGIS高影响阻塞算子各抽3个`content_sha256`去重源码样本，共18条AST证明的活动`processing.run*()`片段。4个保守能力映射（`native:reprojectlayer`、`native:fixgeometries`、`gdal:polygonize`、`gdal:rasterize`）可以作为正式stable-N草案候选；`native:createspatialindex`和`native:saveselectedfeatures`虽有真实调用，但分别是support/performance和export输出类型边界，不能直接作为训练目标。复核报告位于本地`docs/reports/qgis_mapping_high_impact_blockers_2026-07-24/qgis_high_impact_6ops_source_snippet_review_2026-07-24.md`。

因此，yll 所说“每个步骤调用了什么算子已经抽取”在**调用级/步骤级**是成立的，特别是字面量 `processing.run('provider:operator')`。但需要区分：

- `steps.csv` 中的低层 PyQGIS 方法调用不一定等同于标准 Processing operator ID。
- 动态拼接的 operator ID、custom algorithm 和低层 API 仍需额外解析或保留为 custom。
- `/home/yll/GEE/匹配/output_qgis_*/*publish.json` 的最终 `Process -> Operators` 标准化发布结果目前只有 8 个文件，是小规模匹配产物，不是 52,422 组的全量最终标准算子链。
