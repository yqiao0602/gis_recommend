# GEE 语料池混淆审计 v1：三池结构、错配定量与链源重建

日期：2026-09-17
触发：owner 两次指向 `/data/yll/工作流抽取结果` 与 `/home/yll/GEE/描述性知识抽取汇总`，复查后发现前两轮溯源结论均建立在错误前提上。
影响：`gee_conversion_full_v1/v2` 的 44,220 行"指令↔链"配对 **~70% 错配，作废重建**。

---

## 1. 结论（先行）

服务器上同时存在**三套独立编号的 GEE 脚本池**，script_NNNNN 同号不同内容：

| 池 | 位置 | 规模 | 性质 | 溯源 |
|---|---|---:|---|---|
| **A** | `/data/yll/GeoWorkflow-Knowledge-Dataset/.../GEE_OPs/01_Input_raw_script` | 295,943 | GEE Code Editor playground 分享语料（GEE-OPs 官方管线，mtime 2023-12~2024-01，68.6% 带导出头） | 无 repo；资产路径含 `users/{author}/` |
| **B** | `/home/yll/GEE/Data/data20000_AST_failed/dataNNNNN`（原 F:\XLW\01原始脚本\GEE） | 241,206 | yll 自建池（去注释重排版），按 dataN 批次组织 | 无 repo；**Workflowoutput 抽取 + 描述库都产自它** |
| **C** | `/home/yll/GEE/爬取gee脚本/collected_scripts` | 86,410 | 另一次 GitHub 爬取（按语言分目录） | **index.json 有完整 repo 映射**——但只对 C 有效 |

**实测重叠**（comment+空白剥离后内容哈希，113 对随机抽样）：A∩B 同脚本 **30%**、不同 **70%**；B∩C **0/40**；A∩C **0/5**。
三池是独立编号的独立采集，同 id 不保证同脚本。

## 2. 两轮错误与纠正时间线

| 轮次 | 当时的做法 | 错误 | 发现方式 |
|---|---|---|---|
| 试点 v1-v3 | 链 = A 池 15_表；repo = C 池 index.json | **双重错配**：B 池描述 × A 池链（~70% 错），A 池脚本 × C 池 repo（100% 错） | 首轮 5/5 md5 不符揭出 repo 错配 |
| 修正 v4/full_v2 | 移除 C 溯源（正确）；链仍 = A 池 15_表；作者代理从 A 池头部提取 | **链源错误延续**：描述仍是 B 池，链仍是 A 池——30% 侥幸配对、70% 指令描述的脚本与链所属脚本不同 | owner 指向 `描述性知识抽取汇总` → source_manifest.csv 揭出 `F:\XLW\...\dataNNNNN` 输入路径 → 批次行数对账（11,877↔11,877）实锤描述=B 池 → A/B 内容抽样 30/70 揭出链源错配 |

**正确结构（本轮确立）**：
```
描述（facts_summary*.csv）     ← B 池（dataNNNNN）         ✓
链（Workflowoutput* 步骤表）  ← B 池（dataNNNNN，242,029 脚本 100% 覆盖）✓
作者代理（datasource 节点）    ← B 池资产引用 users/{author}/ ✓
```

## 3. 重建方案（`gee_route2_conversion_workflow_chains_v1.py`）

- **链构建**：每脚本按 steps 文件序取 token；`raw_api_name` 起于 `ee.`/`Export.` → `类.末方法`（保留 filterDate/filterBounds 真名）；否则用 `normalized_api_name`（接收者前缀→canonical）；噪声（Map./ui./print）剔除；连续重复去重
- **优势**：Workflowoutput 步骤表带 `semantic_role / control context / datasource`，比 15_ 表信息更富
- **作者代理**：`merged_nodes_datasource.csv` 的 `users|projects/{author}/` 资产引用（B 池脚本本体已去注释，头部无作者信号，此为唯一来源）
- 四关漏斗、canonical 折叠、指令改写、union-find split（作者∪链 + 枢纽分量作者子组）全部沿用 v1 逻辑
- 首验 script_234511：链 = boundary.filter → ee.Filter.eq(ADM2) → filterDate/filterBounds → sort → updateMask → select×3 → NDVI arithmetic —— 与描述（Multan 作物分类）逐项吻合 ✓

## 4. 教训（写给后续审计）

1. **同键不同池是系统性风险**：三池共用 script_NNNNN 编号，任何"按键 join"前必须先做内容级验证（本审计的 30/70 测量即此用途）
2. **元数据血缘要追到输入路径**：描述库的 source_manifest.csv（F:\XLW\...\dataNNNNN）是定性证据；批次行数对账（11,877↔11,877）是定量实锤
3. **owner 的两次目录提示各自揭出一层**：`/data/yll/工作流抽取结果` → 正确链源；`描述性知识抽取汇总` → 描述的真实池属
4. 报告口径：本轮修正作废 `gee_conversion_full_v1`（de5b1fdb）与 `gee_conversion_full_v2`（eab9494d）两个产物的配对有效性；其 canonical 折叠/指令改写/分流算法仍可复用（已复用）

## 5. 复现

- 池属证据：`gee_missing_description_scripts_903_20260912/source_manifest.csv`（source_path 全为 F:\XLW\...\dataNNNNN）
- 批次对账：facts_summary300000=11,877 行 ↔ data300000=11,877 文件；400000：10,645↔10,647
- 重叠率：113 随机 id，comment+ws 剥离哈希 30 同/70 异/37 不配对
- B∩C：40 对归一化内容 0 同；A∩C：5/5 md5 异（首轮已测）
