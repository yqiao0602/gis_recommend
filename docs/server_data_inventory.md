# 服务器数据资产清单（10.191.2.38:/home/yll/GEE）

> 只读审计，2026-06-14。目标视角：**我们的 text→L3(QGIS) 模型**需要的是 **(自然语言描述 → L3 序列)** 训练对（L3 = 94 码，矢量族 L3_02_*、栅格族 L3_03_*）。本清单按"对这个目标的可用性"分层。
> 访问：`qy@10.191.2.38`（host `mdzhang`，**GPU NVIDIA A10**）。源数据/管线属 yll，活跃开发中。**只读、不删不改**。

## ⚠️ 贯穿性结论：整条上游语料 GEE/遥感主导，QGIS/矢量在每一层都是小头
- 描述抽取 `facts_summary*` 编号到 **40 万**脚本；算子链表 `15_Operator_Relationship_Chain`(211,517 行) **QGIS 算子 = 0**（全 GEE/非QGIS）。
- 这与本地实测"训练语料 99.3% 栅格 / 0.2% 矢量"**同源**——矢量稀缺是**源数据现实**，不是采样问题。
- ⇒ 即便动用服务器全量管线，矢量数据上限仍受限于少数 QGIS 库（下方 Tier 2/3 的 QGIS 项）。

---

## Tier 0 — 现在就能直接喂 text→L3 训练（已是 描述+L3 对）
| 资产 | 规模 | 位置 | 说明 |
|---|--:|---|---|
| **本地 `vector_training_samples.jsonl`** | **323 矢量** | 本地 outputs_v2（已建） | 唯一 (描述+L3) 就绪集；描述由 deepseek 生成。源自本地 `qgis_chain_dataset.jsonl`(3053, 323 矢量带 L3) |

**服务器上：Tier 0 = 无**（没有现成的 描述+L3 QGIS 对）。

## Tier 1 — 轻处理可用（数据已有，缺 join 或 L3 映射一步）
| 资产 | 规模 | 位置 | 缺什么 |
|---|--:|---|---|
| `qgis_chain_dataset_v2.jsonl` | 2319 | `筛选ArcGIS工作流/` | = 本地 enriched_v3；有 QGIS 链，**无 L3**，需过 op→L3 crosswalk |
| `facts_summary1000.csv` | ~1000 QGIS | `描述性知识抽取qgis_chain_selected_script/` | **高质真实描述+TaskType**，但**只有描述侧**，需 join 对应脚本的 QGIS 链+L3 |
| `15_Operator_Relationship_Chain_Knowledge_Table.csv` | 211k 行 | `工作流抽取结果参考/` | Script→算子链，但 **全 GEE、0 QGIS** → 对矢量**无用**；对 GEE 任务可 join facts 成对 |
| `facts_summary*汇总` | ~40万脚本 | `描述性知识抽取汇总/` | 同上，GEE 为主的描述侧 |

## Tier 2/3 — 重处理才可用（需走 yll 的 抽取→匹配→L3 管线）
| 资产 | 规模 | 位置 | 形态 |
|---|--:|---|---|
| `qgis_strict_multistep_spatial_workflows` | 1,869 | `工作流抽取结果/QGIS/` | **最高质多步空间工作流**；AST 节点/边 csv，需抽链+L3 |
| `qgis_L2_general_qgis_processing` | 93,900 | 同上 | QGIS 处理工作流 AST |
| `qgis_L3_support_modules` | 121,328 | 同上 | QGIS 支持模块 AST |
| `WorkflowoutputPWCQGIS` / `L1_near_strict` / `Model_Tutorial` | 5,931 / 6,027 / 1,304 | 同上 | QGIS AST |
| `gis_vector_*.jsonl`（workflow_dataset 237 / final_robust 464 / vip 86+59） | ~846 | `爬取GIS代码/` | **矢量域源代码**（{source_repo,gis_domain:vector,**code**}），需全管线 |
| `匹配/test_1000_steps` 等 | 2000 文件 | `匹配/` | function-level 标准化**步骤图**（micro/macro+关系），L3 扁平化前的中间态 |
| `Data/data*/script_NN.py` | 47 子目录 | `Data/` | 源脚本本体 |
| `爬取GithubQGIS` / 爬取多源 / HF / Zenodo … | 大量 | `爬取*/` | 原始爬取脚本/索引 |

## 参考/知识（非训练对，别误用）
- `workflow/1-Training Data/gee_sft_dataset.jsonl`(14,240)：**API 讲解 SFT**（{instruction,input,output}，"Explain ee.X"）——给 GEE LLM 用，**非** text→L3。
- `gee_workflow_alpaca_en_v3_final.jsonl`(569) / conversational / aligned：GEE 工作流指令微调集（GEE LLM）。
- `Unified_GIS_Knowledge_Table_v2_*`(14MB) / `GEE_APIs`/`GEE_Params` / `nasa_glossary.jsonl`(3607) / `remote_sensing_knowledge.py`：算子/领域知识库。
- `源代码模板去重/`：脚本去重聚类（script_dedup_index 39MB 等）。

---

## 结论与建议
1. **矢量训练对就绪量 = 本地 323**；服务器没有现成的 QGIS (描述+L3) 对。
2. **要更多矢量**，只能处理 Tier 2/3 的 QGIS 池（`qgis_strict_multistep` 1869 质量最好；`qgis_chain_dataset_v2` 2319 已半成只缺 L3；`facts_summary1000` 有 ~1000 真实描述待 join 链）。这些都要走 **op→L3 映射 / yll 的匹配管线**——是真工程，且不该碰坏 yll 的 WIP。
3. **GEE 资产很大但与矢量目标无关**（甚至会加重栅格偏置，别混入）。
4. **务实路线**：先用本地 323（上采样重平衡）在 **A10** 上跑首个重训实验验证"补矢量能否救矢量"；同时把"QGIS 池→L3"的处理与 yll 对齐后再扩量。
