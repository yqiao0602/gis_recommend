# QGIS 语料目录级盘点（2026-07-21）

## 结论

服务器上的“约 38 万”和“约 3 万”不是同一统计口径。

- `/home/yll/GEE/工作流抽取结果` 有 383,256 个文件，但约 303,294 个是 CSV、75,803 个是 JSON，Python 仅 4,119 个；这是多平台、多阶段的抽取产物数，不能称为 38 万条 QGIS 原始脚本。
- GitHub QGIS 合并日志记录 75,289 个输入实例，经既有内容去重后保留 54,231 条，删除重复 21,058 条。
- 同一合并集的旧 workflow 启发式筛选结果为 37,180 条 `Yes`、17,061 条 `No`。yll 所说“约 3 万”最可能指这 37,180 条候选工作流，而不是全部 QGIS 相关源码。
- 37,180 仍只是旧启发式候选，不等于显式 Processing 金标。

## 关键目录口径

| 目录/索引 | 观察量 | 解释 |
| --- | ---: | --- |
| `/home/yll/GEE/工作流抽取结果` | 383,256 files | GEE/QGIS/ArcGIS 等多平台抽取产物总量，不是源码量 |
| `工作流抽取结果/QGIS` | 262,901 files | 主要是每条源码派生的 1 JSON + 4 CSV；文件名约覆盖 50,090 个 script ID |
| GitHub QGIS merge inputs | 75,289 | 七个爬取源的输入实例 |
| GitHub QGIS dedup kept | 54,231 | 既有 merge 日志标记的唯一保留实例 |
| GitHub QGIS duplicate removed | 21,058 | merge 日志中的重复实例 |
| old workflow filter `Yes` | 37,180 | 启发式 QGIS workflow 候选 |
| old workflow filter `No` | 17,061 | 非工作流/弱工作流候选；并不等于非 QGIS |
| facts/AST CSV | 20,428 | 唯一 `File Name` 20,428；已有描述子集，不代表全语料 |

GitHub merge 的七个输入源：

| source dataset | input | unique kept | duplicate |
| --- | ---: | ---: | ---: |
| `QGIS_standard_multi_operator_workflows_v2` | 1,036 | 1,036 | 0 |
| `github_qgis_workflow_A类` | 7,518 | 6,519 | 999 |
| `Github_QGIS_PyQGIS_Workflows_201509` | 32 | 32 | 0 |
| `Github_QGIS_RS_QGISPlatform_Related_201509` | 45,633 | 41,217 | 4,416 |
| `Github_QGIS_RS_Workflows_201509_filtered_QGIS_only` | 8,126 | 855 | 7,271 |
| `Github_QGIS_Scraper` | 4,167 | 2,048 | 2,119 |
| `github_qgis_workflow` | 8,777 | 2,524 | 6,253 |

## 现有 QGIS 分层索引

`/home/yll/GEE/Data/data-QGIS` 有 53,569 个 Python 文件。移出 373 个旧 strict 文件后，`qgis_remaining_layer_index.csv` 记录 53,196 条：

| layer | rows | 含显式 provider `processing.run` | 至少 2 次 | 至少 3 次 |
| --- | ---: | ---: | ---: | ---: |
| L1 near-strict | 1,209 | 1,209 | 1,209 | 1,209 |
| L2 general processing/model | 18,824 | 3,196 | 1,468 | 645 |
| L3 support modules | 24,445 | 0 | 0 | 0 |
| nonworkflow removed | 8,718 | 13 | 1 | 1 |

因此，这个既有索引中可见的单步以上显式 Processing 候选为 4,418 条，多步字面量候选为 2,678 条。另有独立的 `qgis_processing_chained_index.csv` 1,125 条，强调调用间依赖；parse-failed 队列为 1,870 条。旧 strict 目录有 373 个物理脚本，但权威 strict CSV 只有 128 行，不能直接把 373 全部加进高置信数量。

这些层是旧正则/启发式分类结果，不是最终训练准入。尤其 L2/L3 含大量 `processAlgorithm()`、底层 API、插件 UI、provider 和支持模块。

## 用户指定目录

| 目录 | Python/脚本文件 | 当前判断 |
| --- | ---: | --- |
| Esri Community scripts | 22 | 22/22 为 ArcPy 信号，QGIS 候选 0 |
| RouteB Gitee/GitLab | 4,318（SHA256 唯一 4,216） | QGIS 证据 3,739；AST 字面量 Processing 文件 231，动态 8 |
| QGIS Model Tutorial | 1,886 物理 `.py`，仅 846 个内容哈希 | 目录内复制严重；清洗目录 780 条，抽样 29/30 有显式 Processing |
| QGIS Core Processing workflow scripts | 110 | 主要为 QGIS core/provider/底层 API；仅 1 条显式 Processing |

四个指定目录合计 6,336 个 Python 文件，SHA256 去重后 5,194 个；跨四目录未发现相同内容哈希。

## 其他 QGIS 生态目录簇

- Official Plugins：`plugin_unpacked` 有 43,880 个 Python，UI、vendor、测试和支持代码很多；已有 `workflow_candidates` 2,254 条，`refined_strict_workflows` 1,209 条。
- GitLab Supplement：3,410 个 Python、3,010 个文本脚本和 113 个 model3；抽样均有 QGIS 生态信号，但需目录内去重及 workflow gate。
- Textbook candidates：元数据平台分层 QGIS 4,106 条，抽样 UI/测试比例较高。
- PWC QGIS：1,183 条，但抽样仅 7/30 有明确 QGIS 生态信号，目录名明显高估相关性。
- Zenodo 当前平台分层 QGIS 仅 20 条；旧抽取产物目录有 426 个 script ID，表明旧宽松分类与当前分层口径不同。

## 下一步

1. 先建立目录簇 manifest，记录来源、处理阶段、是否派生、已有去重 authority 和抽样类型。
2. 第一批只扫描 GitHub merge/Data 的显式 Processing 候选、Tutorial cleaned、Official Plugin candidates/strict、GitLab 可解析源码和 RouteB 显式 Processing。
3. 优先复用 `rename_log.csv`、crawler `seen_content_hashes`、layer index 和 chained index；只做必要的跨 authority 内容哈希。
4. 分别报告 QGIS 相关源码、启发式 workflow 候选、显式 Processing 候选、通过依赖/catalog/完整性门禁的训练候选。
5. 当前可确定主 GitHub 合并集约有 5.4 万去重源码候选、旧筛选约 3.7 万 workflow 候选，而最容易的显式 Processing 主体为数千条规模，足够先做 50/200 条验证。

## 调查边界

- 所有服务器操作均为只读，未保存凭据。
- 两次大范围逐文件哈希/AST 尝试因小文件 I/O 超时终止，未生成服务器文件；随后改为目录簇抽样和读取既有确定性索引。
- 尚未完成跨全部独立来源的最终内容哈希 union，因此不提供伪精确的“全服务器唯一 QGIS 脚本总数”。
