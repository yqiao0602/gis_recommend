# 发现记录

## 三条数据路线的对比（关键方法论进展 2026-06-20）

**路线 1：AST 链抽取**（从 steps.csv 挖 `qgis_processing_algorithm` 行）
- 天花板：~3k 脚本用 `processing.run()`，L3 映射去重后 **1,374 条**
- Phase 6/7 证明不足以克服 99.3% 栅格偏置
- 瓶颈：绝大多数 QGIS 脚本走 C++ API 而非 `processing.run()`

**路线 2：LLM 描述→L3**（只给 deepseek-chat 看任务描述文本，不提供 API 细节）
- 产出：20k 描述 → **19,754 条 LLM 生成的 L3 序列**（87% 合法性，78% 矢量 token）
- 与 AST 合并去重 → **10,768 条统一训练集**（94% 矢量相关，Phase 8 在跑）
- 可靠性：不如 AST 链精确——LLM 可能误解描述

**路线 3（新 POC 2026-06-20）：C++ API 痕迹→LLM→L3**
- 把 steps.csv 中的底层 C++ API 调用序列（semantic_role + description）喂给 LLM
- POC 结果（script_03）：API_only 输出 `Reproject→Buffer→SpatialJoin→FieldCalc→Export`，与真实 AST 链**完全吻合**；desc_only 漏掉 Reproject
- 小规模验证（10 脚本）：6/10 合法 L3，53% 矢量
- **优势**：C++ API 痕迹是"地面真相"——LLM 从实际执行的操作反推高层步骤，而非凭描述猜测
- **可规模化**：17k 个 C++ API 脚本都有 steps.csv，每个 feed→LLM→L3
- BAD 原因可修（prompt 导致 L3 码带了描述文本后缀）

## 评测指标：executable ≠ correct（多测证实）
- **open_landing 80 题（检索基线）**：C 档有效率(0.987) > A 档(0.928)，executable 三档几乎不变
- **Phase A（V4.6 text-only）**：同上模式，①② 不随 human grade 单调变化
- **Phase B（held-out + 实 task_type）**：Precipitation/Topography executable=1.0 但 set_f1~0.39；Air quality executable=0.33 但 set_f1=0.63 → **② 和 ③ 彻底解耦**
- → **①② = grounding/runnable 轴，③④ = correctness 轴。横评必须多指标。**

## V4.6 模型：矢量塌成栅格（文本级证据）
- Phase A 矢量任务的 L3 输出全是 `L3_03_*` 栅格/遥感码（Temporal Reducer、Select Bands、Filter by Date）
- vec executable 0.875→0.350（vs 检索基线），unique_ratio 0.525→0.200
- **对比**：raster 反而改善（io_exec 0.507→0.763）——模型有强栅格先验
- **失败标记**：FP06:raster_vector_mismatch 频繁出现

## 根因：训练语料 GEE/遥感主导（量化）
- `labeled_workflows`(76,884)：**99.3% 栅格 workflow，0.2% 矢量**（165 条）
- L3 token 分布：L3_02(矢量) = **1.2%**，L3_03(栅格) = **77.2%**
- task_type 词表 = 47 个 NASA 地球科学主题，**无模态轴**
- 没有任何 task_type 是 ≥50% 矢量为主的（最多 Boundaries 18%）
- → **矢量能力是数据问题，不是推理 trick 能修**

## 服务器数据盘查（10.191.2.38:/home/yll/GEE）
- 主机 mdzhang，GPU **NVIDIA A10**，磁盘 524G 空闲
- **整条上游管线 GEE 主导**：描述抽取到 40 万脚本，`15_Operator_Relationship_Chain_Knowledge_Table.csv`(211K 行) **QGIS 算子 = 0**
- **QGIS 数据可用**：
  - `数据抽取结果/QGIS/` 6 个池：~46,000 个 per-script 抽取，其中 ~4,097 有 QGIS 算法调用
  - `facts_summary1000.csv`：~1,000 个 QGIS 链脚本有真实描述抽取（File Name + Task Type + Task Description）
  - `data-QGIS`：53,569 个原始 QGIS 脚本（后备）
  - join 后 2,733 完整 QGIS 样本（链 + 真实描述 + Task Type）
- 服务器已有 `system_redesign` 项目副本（qy 自有的 outputs_v2 + scripts）、conda env `transformer`（torch 2.2.2+cu121）

## L3 映射缺口分类（①②③ 三桶）
- **① 归一化假缺口**：`qgis:fieldcalculator` 等是已映射 `native:` 的旧别名 → **免费修，+235 链**
- **② crosswalk 不全**：词表有槽只是没映上（joinbynearest→Spatial Join, extractvertices→Feature to Point, explodelines→Multipart to Single...）→ **补 crosswalk，不动词表**
- **③ 真·L3 缺口**：~7 个核心矢量原语 94-L3 压根没有（**Simplify 极常用却无**、Heatmap/KDE 独卡 53 条最多、Delete holes、Points along lines、Split with lines、Smooth）→ **需扩词表+重训**
- ①② 做完后 crosswalk 101→186 l3_bridge，mapped_rate 27.5%→39.8%，训练集 756→1,097

## deepseek-v4-pro 使用经验
- **推理模型**：答案在 `content`，思维链在 `reasoning_content`
- **小 max_tokens 致命**：300→800 仍截断，**需 ≥4000**
- **鲁棒策略**：空 content 回退 reasoning_content + 正则提取 `{...}` JSON 子串
- 描述质量优秀：10/10 冒烟 0 错误；全量 323 调用仅 3 错误
- 全局切换：llm_scorer / qgis_operator_qa / audit 脚本默认全换，3 处硬编码旧 key 改环境变量

## 已有基建（服务器端）
- paramiko 访问（只读）+ SFTP 推送代码/数据
- `/home/qy/system_redesign`：项目副本 + `outputs_v2`（contract + 自己的诊断输出）
- conda env `transformer`：torch 2.2.2+cu121, transformers 4.57.5, sentence-transformers 5.4.1
- `server_bootstrap.sh`：幂等同步代码+数据清单+建 venv 脚本（备用）
