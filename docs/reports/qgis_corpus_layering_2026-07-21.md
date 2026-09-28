# QGIS 九源源码静态分层统计（2026-07-21）

## 统计范围

对九个已确认 QGIS 原始或接近原始源码 authority 做只读 AST 静态扫描：

- 路径数：129,029
- 原始字节 SHA256 唯一源码：112,758
- 先前宽口径强 QGIS 信号路径：88,400
- 强信号唯一源码：80,998

GitHub 只使用 `QGIS_merged_dedup_by_index/downloaded_scripts`，Official Plugins 只使用 `plugin_unpacked`。`qgis_chain_selected_scripts`、`processing_chained`、`strict`、`workflow_candidates` 等派生副本不重复计入原始路径。

扫描使用 `/home/yll/GEE/爬取GithubQGIS/QGIS_Input.csv` 的 1,289 个 provider-qualified ID 做 catalog exact 检查。不调用 LLM，不生成训练数据，不修改 `/home/yll`。

## 80,998 份强信号唯一源码的最终分层

| 主层 | 数量 | 比例 | 当前用途 |
|---|---:|---:|---|
| Catalog 精确多步 Processing | 3,938 | 4.86% | 第一优先级，进入顺序/依赖/工作流完整性/L3 门禁 |
| Catalog 精确单步 Processing | 2,534 | 3.13% | 单算子语义、参数和描述参考，不计多步主训练量 |
| Processing 待解决 | 8,466 | 10.45% | catalog 缺口、动态 ID、自定义算法实现，需分流处理 |
| 低层 PyQGIS API 候选 | 39,386 | 48.63% | 延后做 API-pattern/语义聚合，不能直接生成 operator chain |
| 排除或隔离 | 26,674 | 32.93% | 测试、非业务支持、无 operational QGIS、语法/读取异常 |
| **合计** | **80,998** | **100%** |  |

### Processing 待解决的内部组成

| 子层 | 数量 | 说明 |
|---|---:|---|
| 字面量 operator 但 catalog miss | 3,163 | 旧 `qgis:*` ID、第三方 provider、自定义 provider 或 catalog 缺口 |
| 动态或空 operator ID | 445 | 需要常量传播、分支和参数解析，禁止猜 ID |
| `QgsProcessingAlgorithm` 实现或 custom | 4,858 | 多数是算法实现类，不自动等同于用户多步 workflow |

### 排除或隔离的内部组成

| 子层 | 数量 |
|---|---:|
| 强测试证据 | 8,655 |
| 无 operational QGIS 证据 | 16,166 |
| Python 语法错误/伪装文档 | 1,846 |
| 读取/编码异常 | 7 |

“无 operational QGIS 证据”仍可能命中旧的宽正则，例如只导入 `qgis.PyQt`、插件 GUI、捆绑第三方库或文本中出现 `Qgs*`，因此会出现在 80,998 强信号宽池中，但不进入工作流候选。

## 全部 112,758 份唯一源码的静态层级

基础分类器得到：

- Tier A catalog-exact Processing：6,510
- Tier B Processing review/custom：8,592
- Tier C direct PyQGIS API：44,612
- quarantine：53,044

在进一步识别被爬虫重命名为 `script_*.py` 的隐藏测试后，全体唯一源码的互斥主层为：

- catalog 精确多步 3,938
- catalog 精确单步 2,534
- Processing 待解决 8,466
- 低层 API 候选 39,387
- 排除/隔离 58,433

强信号池与全体池差异主要来自没有 operational QGIS 的普通第三方 Python 文件。

## 强信号池的 canonical 来源

以下按跨来源 SHA256 去重后的 canonical owner 统计，不是原始路径数：

| 来源 | 唯一强信号源码 |
|---|---:|
| GitHub merged | 46,382 |
| Textbook strict | 15,753 |
| Official Plugins | 10,879 |
| RouteB | 3,573 |
| GitLab supplement | 3,397 |
| Model/Tutorial | 846 |
| Core Processing | 110 |
| Zenodo QGIS | 48 |
| PWCQGIS | 10 |

第一优先级 catalog 精确多步来源：GitHub 1,810、Textbook 937、GitLab supplement 543、Model/Tutorial 393、Official Plugins 200、RouteB 51、Zenodo 3、PWCQGIS 1。

## 内容抽样核实

每个主层固定随机抽取 3 份源码，共 33 份，全部成功读取。典型样本：

- 精确多步：Textbook `script_0009538.py` 实际连续调用两次 `grass7:v.clean`。
- 精确单步：GitHub `script_3858.py` 实际执行 `native:rotatefeatures`。
- catalog miss：GitHub `script_51577.py` 是 `QgsProcessingAlgorithm`，调用自定义 provider `qscout:droppins`。
- 动态 ID：GitHub `script_670.py` 是实际河口填充 QGIS 工作流，但 operator ID 通过变量/逻辑组织。
- custom/实现：GitHub `script_7051.py` 是带参数和输出定义的 `QgsProcessingAlgorithm` 实现类。
- 低层 API：Textbook `script_0009446.py` 是 LandWise terrain/slope profile 分析，直接使用 PyQGIS 逻辑而非 `processing.run()`。
- 测试排除：Official Plugin `test_geokkp_dockwidget.py` 明确是 `unittest` DockWidget 测试。
- 无 operational QGIS：Official Plugin 中捆绑的 `openpyxl` 源码，与 QGIS 工作流无关。
- 语法隔离：部分 `.py` 实际是 RST/QGIS script 文档格式，不是可解析 Python。

首轮抽样还发现爬虫会把原始 `tests/...` 重命名为 `script_*.py`。最终统计因此加入源码头 `Source path`、`pytestmark/@pytest.fixture`、`unittest.TestCase/QgisTestCase` 等强证据，额外隔离 8,463 份隐藏测试；不会仅凭普通单词 `test` 排除。

## 如何理解 3,938 条

3,938 只是“至少两个字面量 Processing ID 且全部命中当前 QGIS catalog”的源码，不等于训练样本。仍需检查：

1. 是否是用户任务工作流，而非算法实现类、示例或支持函数。
2. 源码执行顺序、跨 helper 调用和循环/分支是否可恢复。
3. 输入输出依赖是否闭合。
4. 链长是否合理，是否存在重复初始化或多入口拼接。
5. 每个 QGIS operator 是否能审核映射到 stable-94 L3。
6. 是否有可信原始描述；没有时只能在链确认后生成 train-only silver 描述。

所以当前最现实的漏斗是：

`3,938 catalog-exact multistep -> 结构/依赖/L3 审核 -> 可训练多步样本`

同时处理 3,163 条 catalog miss 可能扩大显式链池；39,386 条低层 API 不作为第一批产量承诺。

## 可复现产物

- 基础扫描：`/home/qy/system_redesign/outputs_v2/qgis_corpus_screening/nine_sources_canonical_v2`
- 细分结果：`/home/qy/system_redesign/outputs_v2/qgis_corpus_screening/nine_sources_canonical_v2_layers_v2`
- `screening_summary.json` SHA256：`4fe8fe3aa4f48cca6138853a1acb3a604eb36b5223c764fad272f9282ea918dd`
- `layer_summary.json` SHA256：`a70b224971c7e21f90275d583278eb3a1b1eb99be37d74a5abd8681b812e051a`
- `layer_samples.jsonl` SHA256：`9131ab275d2ffc4dc99230453fa8b223b55a17637531c5bbbc780a1153a4add9`
- 当前工作区汇总/抽样工具：`scripts/summarize_qgis_corpus_layers.py`、`scripts/summarize_qgis_strong_signal_layers.py`、`scripts/sample_qgis_corpus_layers.py`
- 基础筛选 CLI `scripts/build_qgis_corpus_screening.py` 当前位于功能工作树 `feature/qgis-corpus-screening-funnel`，并已部署到服务器 `/home/qy/system_redesign/`；合入主工作区前不要误认为当前分支已有该文件。
