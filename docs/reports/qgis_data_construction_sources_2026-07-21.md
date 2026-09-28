# QGIS 数据构造来源清单（2026-07-21）

## 推荐输入组合

构造一条 QGIS 数据时，不应只取一个目录，而应组合四类证据：

| 内容 | 首选位置 | 用途 |
|---|---|---|
| 任务级描述 | `/home/yll/GEE/描述性知识抽取qgis_chain_selected_script/facts_summary1000.csv` | `Task Name`、`Task Description`、任务类型、数据源和时空信息 |
| 步骤/算子 | `/home/yll/GEE/工作流抽取结果/QGIS/<group>/*_steps.csv` | 逐调用步骤、字面量 Processing operator ID、参数和语义角色 |
| 依赖关系 | 同组的 `*_edges.csv`、`*_process_relations.csv` | 恢复步骤顺序、嵌套、数据依赖 |
| 原始源码 | 对应 source pool 的 `script_*.py` | 验证算子、参数、分支和真实输入输出 |
| 来源信息 | GitHub/RouteB/Model/Zenodo/PWC 索引和 metadata | 仓库、原始路径、URL、hash、采集原因 |

## “2 万”和“5 万”分别是什么

| 数字 | 统计单位 | 含义 |
|---:|---|---|
| 20,428 | 描述行 | `facts_summary1000.csv` 中具有任务名和自然语言任务描述的记录 |
| 52,422 | 脚本抽取组 | 每个 source script 在某个 extraction group 下形成的一组 AST/steps/data/edges/relations |
| 52,329 | 路径级脚本记录 | 去除少量异常后按完整路径统计的脚本记录 |
| 49,997 | 唯一 basename | 只按 `script_*.py` 文件名统计；不能代表唯一源码 |

52,422 个抽取组包括：L2 general 18,721、L3 support 24,229、两个 L1 组各 1,200、Processing chained 1,125、strict multistep 373、PWCQGIS 1,183、RouteB 3,696、Model/Tutorial 260、Zenodo 426 和 data1 9。它们存在派生分层和同名重复，不能直接解释为 52,422 条独立训练样本。

## 全部主要 QGIS 原始脚本池有多大

为避免只围绕 20,428 条已有描述候选工作，已对九个主要 QGIS 原始或接近原始来源递归统计并计算原始文件字节 SHA256：

| 口径 | 数量 | 含义 |
|---|---:|---|
| `.py` 文件路径 | 129,029 | 九个主要来源的当前文件系统路径总数，包含跨目录副本 |
| 唯一源码 SHA256 | 112,758 | 按原始文件字节完全一致去重后的不同源码 |
| 强 QGIS 信号路径 | 88,400 | 出现 QGIS import、`Qgs*`、`processing.run` 或 Processing algorithm 类等代码信号 |
| 强 QGIS 信号唯一 SHA256 | 80,998 | 强信号文件再按原始字节去重后的大候选池 |
| 已有自然语言描述 | 20,428 | 现成 code-grounded silver 描述行，只覆盖原始池的一部分 |

九个来源的路径数分别为：GitHub QGIS merged 54,240、Official Plugins 44,536、GitLab supplement 3,410、Core Processing 110、Model/Tutorial 846、RouteB 4,302、Zenodo 444、PWCQGIS 1,183、Textbook strict candidates 19,958。

因此后续不应把约 2 万条描述候选当作全部 QGIS 源码。更合适的漏斗是：

`129,029 路径 -> 112,758 唯一源码 -> 80,998 强 QGIS 信号唯一源码 -> 工作流/多步/依赖可恢复筛选 -> 可构造训练对`

其中 `80,998` 仍包含插件支持代码、GUI、测试、provider、Core 算子实现、单步脚本和低层 API。AST 静态分层现已完成；下一阶段只对 3,938 条 catalog 精确多步池做链级结构、依赖、角色和 stable-94 L3 门禁。已有 20,428 条描述只作为可复用描述子集，不限制源码候选范围。

审计清单保存在 `/home/qy/home_yll_inventory/qgis_raw_py_hashes_20260721.tsv` 和 `/home/qy/home_yll_inventory/qgis_raw_py_strong_signal_paths_20260721.nul`，未写入 `/home/yll`。

## 20,428 条现有描述的训练可用性审计

使用冻结 stable-94 authority 对现有描述和 `steps.csv` 做确定性审计后：

- 20,413 条能关联抽取产物；1,887 条多 group 记录的 AST hash 完全一致，可作为同源镜像消歧。
- 只有 1,365 条含至少一个明确 Processing operator，1,356 条为多步链。
- 181 条满足多步、字面量 operator、链长和完整 stable-94 映射，其中 81 条顺序确定，100 条需要恢复顺序。
- 1,162 条含 Processing 链但 stable-94 映射不完整，是优先修复池。
- 19,048 条无字面量 Processing operator，主要属于低层 API/支持逻辑，不能直接形成当前主线训练标签。

所以现有两万条不能直接筛出约一万条可靠训练样本。即使显式 Processing 映射缺口全部解决，也只是约 1,300 条量级；必须继续从 80,998 份强 QGIS 信号唯一源码扩充。详细报告见 `docs/reports/qgis_description_candidate_audit_2026-07-21.md`。

## 80,998 份强 QGIS 信号源码的静态分层

九个 canonical 来源全量 AST 扫描后：

- 3,938 条为 catalog 精确多步 Processing，进入第一优先级链验证。
- 2,534 条为 catalog 精确单步，可作单算子语义和参数参考。
- 8,466 条属于 Processing 待解决：3,163 catalog miss、445 动态/空 ID、4,858 算法实现或 custom。
- 39,386 条为低层 PyQGIS API 候选，需要后续 API-pattern/语义聚合。
- 26,674 条为测试、非 operational QGIS、语法/编码异常等排除或隔离数据。

因此 8 万池并非全部低层 API，也并非 8 万条训练样本。最优先处理的是 3,938 条 catalog-exact multistep；详细来源、抽样和复现信息见 `docs/reports/qgis_corpus_layering_2026-07-21.md`。

## 当前可进入训练数据构造的范围

1. 20,413/20,428 条描述能够找到 AST 和 steps，是“描述 + 代码结构”总候选池。
2. 18,526 条只对应一个 extraction group，可以直接建立一对一候选关联。
3. 这 18,526 条中有 18,197 条来自 L2 general、251 条来自 Model/Tutorial、68 条来自 strict multistep、10 条来自 L3 support。
4. 10 条 L3 support 应排除，因此当前一对一、非 support 的描述-源码候选上限是 18,516 条。
5. 18,516 仍不是最终训练量。L2 general 中还要筛除 GUI/test/provider/support、无有效空间操作、只有低层 API、动态/custom 算子和不可恢复依赖的记录。
6. 1,887 条多 group 碰撞记录需要路径/hash 消歧后才能加入；15 条缺失记录暂不可用。

最优先审核的不是直接全收 18,516 条，而是：

- 251 条一对一 Model/Tutorial 描述候选。
- 68 条一对一 strict multistep 描述候选。
- Processing chained 的 1,122 条描述候选，但它们全部或几乎全部存在多 group 关联，需要先消歧。
- L2 general 中含明确字面量 `processing.run('provider:operator')`、多步依赖可恢复的子集。

只有 8 个 `匹配/output_qgis_*/*publish.json` 已完成最终 `Process -> Operators -> StandardFunctionPath` 发布。因此目前“可以构造候选训练对”约为两万量级，但“已完全标准化、可不经审核直接训练”的数据远不是两万条。

## 主描述表

`facts_summary1000.csv` 当前有 20,428 条有效记录：

- 描述全部非空，20,394 条描述唯一。
- 20,413 条能匹配 AST 和 steps；15 条缺失。
- 18,526 条只对应一个 extraction group。
- 1,887 条存在 2-3 个同 basename group，禁止直接按文件名盲连。
- 使用现成候选关联：`/home/qy/system_redesign/outputs_v2/qgis_pilot/pilot_v1/phase1/facts_artifact_candidates.jsonl`。
- 描述是 code-grounded/silver，不应标成人工 gold。

## 源码优先级

### 优先使用

1. `/home/yll/GEE/爬取多源数据源/QGIS_Model_Tutorial_Workflows/downloaded_scripts`
   - 851 条；810 条有 `processing.run`，适合显式多步 Processing 链。
2. `/home/yll/GEE/爬取GithubQGIS/合并脚本/QGIS_merged_dedup_by_index/strict_multistep_spatial_workflows/downloaded_scripts_strict`
   - 严格多步工作流。
3. `/home/yll/GEE/爬取GithubQGIS/合并脚本/QGIS_merged_dedup_by_index/qgis_processing_chained_workflows/downloaded_scripts`
   - Processing chained 工作流。
4. `/home/yll/GEE/Data/data-QGIS_remaining_layered_after_strict/L1_near_strict_spatial_workflow_candidates`
5. `/home/yll/GEE/Data/data-QGIS_remaining_layered_after_strict/L2_general_qgis_processing_workflows_part1`
6. `/home/yll/GEE/Data/data-QGIS_remaining_layered_after_strict/L2_general_qgis_processing_workflows_part2`

### 补充使用

- `/home/yll/GEE/QGIS_ArcGIS_RouteB_Gitee_GitLab/downloaded_scripts`
  - 4,302 条，3,659 条有强 QGIS 信号；索引仅 198 条，需依赖源码头和抽取产物补全来源。
- `/home/yll/GEE/爬取多源数据源/QGIS_Official_Plugins`
  - 完整插件源码和插件级描述，混有 GUI、测试、资源和支持代码。
- `/home/yll/GEE/爬取Zenodo网站/zenodo_extracted/QGIS`
  - 444 条中仅 48 条有强 QGIS 信号，必须二次筛选。
- `/home/yll/GEE/爬取gee脚本/爬取PWCQGIS/downloaded_scripts`
  - 1,183 条中仅 30 条有强 QGIS 信号，当前是高污染候选池。

### 不作为 QGIS 工作流输入

- `/home/yll/GEE/爬取EsriGithubCommunity/Esri_Github_Community_Scraper/github_workflow_scripts`
  - 26 条，22 条有 ArcPy 信号，0 条有强 QGIS 信号。
- `/home/yll/GEE/爬取多源数据源/QGIS_Core_Processing/workflow_scripts`
  - 93 个算法实现、14 个支持脚本、3 个 provider 脚本；用于算子目录和参数依据，不是用户工作流。
- `L3_support_modules`、GUI、test、provider、support 代码应单独分层。

## 描述补充来源

| 来源 | 数量 | 说明 |
|---|---:|---|
| QGIS Official Plugins `metadata.txt` | 2,009 | `description`、`about`，插件级用途描述 |
| README | 2,054 | 插件/仓库级说明 |
| Model/Tutorial metadata | 851 | 仓库、原始路径、采集原因、算子信号和 hash |
| 精评 CSV | 2 | 路径、复杂度、调用预览、选择结果 |
| 源码/docstring 候选 | 48,011 | 只作补充证据，不能直接当任务描述 |
| `匹配/output_qgis_*` | 8 个最终 publish JSON | 小规模 `FunctionalStatement` 和标准路径结果，不是全量描述 authority |

## 算子抽取核实

QGIS 抽取结果包含 52,422 组脚本，每组通常有 AST、steps、data、edges、process-relations 五个文件，共 262,110 个产物。

已核实 `script_55771.py`：源码中的 `native:extractbyexpression`、`native:intersection`、`native:dissolve`、`native:refactorfields`、`native:fixgeometries` 等调用，在对应 `steps.csv` 中均保存为准确 `normalized_api_name`，并标为 QGIS Processing algorithm。

结论：

- 字面量 `processing.run('provider:operator')` 的逐步算子抽取可直接利用。
- `edges.csv` 和 `process_relations.csv` 可用于恢复步骤关系。
- 低层 PyQGIS 方法、动态 operator ID 和 custom algorithm 不能自动等价为标准 Processing 算子。
- 最终 `Process -> Operators -> StandardFunctionPath` 的 publish JSON 目前只有 8 个，尚未覆盖全量。
