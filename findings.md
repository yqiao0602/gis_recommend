# 发现记录

## L3 词汇缺口：50% 矢量任务无对应 L3 码（2026-07-03）

### 核心发现
- 40 道 open_landing 矢量任务人工标注金标 L3 链
- **20/40 (50%) 任务在现有 17 个矢量 L3 码中找不到对应操作**
- 可评分 20 题 SetF1=0.399，低于 Phase B 的 0.531
- **词汇缺口比模型质量问题更大** —— 模型不是做错了，是根本没有对应的"语言"来表达

### 缺失的 L3 码（17+ 种）
| 操作 | 常见程度 | 影响 |
|------|---------|------|
| Reproject | 极高 | 几乎所有项目都需要 |
| Simplify | 高 | 制图/发布常用 |
| Fix Geometries | 高 | 数据预处理必备 |
| Voronoi / Delaunay / Thiessen | 中 | 空间分析核心 |
| Grid Generation | 中 | 采样/制图 |
| Snap | 中 | 拓扑修复 |
| Delete Duplicate | 中 | 数据清理 |
| Export | 极高 | 任何流程结尾 |
| Smooth / Concave Hull / Delete Holes | 低 | 专项需求 |

### 方法论结论
- 17 个矢量码远不够覆盖真实 GIS 工作流
- 需要至少扩充到 **30+ 个矢量 L3 码**
- 优先级: Reproject → Simplify → Fix Geometries → Grid → Voronoi/Delaunay/Thiessen

## 新阶段方向：从"能生成"到"生成得对"（2026-07-02）

### 核心判断
- **生成能力已修复**（vec usable 88%），但**链质量才是真正的瓶颈**
- 评测中频繁出现 `missing_critical_steps` 警告——模型输出操作步骤不完整
- 现有评测体系缺少对链质量的细粒度判断（缺少哪步？多了哪步？为什么？）

### L3 链质量评估维度设计
1. **完整性（completeness）**：金标链的关键步骤是否都被覆盖？→ 需要定义"关键步骤"标准
2. **简洁性（conciseness）**：是否有冗余步骤（如连续两个 Clip、不必要的 Collect）？
3. **模态一致性**：矢量任务不应包含栅格专属操作（如 Select Bands）
4. **可落地性**：L3→QGIS mapping 成功率（现有），但需要反推 L3 质量 vs landing 语料质量的归因

### 意图识别（task_type classification）
- 当前是外挂脚本（`classify_task_type.py`），每次评测前手动跑
- 应集成进推理管线：用户 NL 输入 → BERT/LLM 分类 task_type → L3 推理
- 可选方案：
  - 方案 A：保持 LLM (deepseek-chat) 分类，简单可靠但依赖 API
  - 方案 B：训练轻量 BERT 文本分类器（48类），离线可用
  - 方案 C：规则匹配（不推荐，覆盖不全）

### 端到端质量门控
- 应在 pipeline 的每个环节设置质量检查点：
  1. 输入：task_type 分类置信度 > 阈值
  2. L3 输出：SetF1 估计 / rule-usable 检查
  3. QGIS landing：mapping 成功率 / I/O 兼容性
  4. Workflow JSON：参数完整性 / 数据流连通性

## 🔑 关键突破：task_type 分类修复矢量 L3 输出（2026-06-30）

### 核心发现
- V4.6 模型训练时用 task_type embedding 条件化，但推理时一直传 `task_type="Unknown"` → embedding 索引 0（无效类别）
- 加 task_type 分类后，**矢量 L3 token 占比从 ~0% → 55.8%**（同一套 80 题 open_landing）
- **不是更多数据的问题，是推理时模型不知道自己该输出什么模态**
- task_type embedding 是模型选择矢量/栅格的关键信号

### 三次评测对比（同 80 题）
| 评测 | task_type | 矢量 L3% | 栅格 L3% | vec usable |
|------|-----------|---------|---------|------------|
| Phase A (V4.6 原始) | "Unknown" | ~0% | ~98% | 35% |
| open_landing_gentle | "Unknown" | 26.5% | 50.8% | 85% |
| open_landing_gentle_typed | **LLM 分类** | **55.8%** | 30.3% | 78% |

### 方法论结论
- task_type 分类是必须的前置步骤，不能跳过
- LLM 分类准确度够用（deepseek-chat, 整数输出, 48 类）
- vec usable 轻微下降 (85%→78%) 因为 QGIS landing 语料仍偏栅格
- 下一步应该：1) 把 task_type 分类集成进推理管线；2) 扩充 QGIS landing 语料的矢量覆盖

## 大规模 PY 脚本矢量挖掘（2026-06-25—30）

### 核心发现
- 398K+ QGIS .py 脚本中，45,000+ 含 processing.run() 调用，31,838 个有矢量操作
- 通过 QGIS alg_id → L3 语义映射 + OP_PATCH 手动补丁，能识别绝大多数矢量操作
- **11,277 条精选样本**，17/17 矢量 L3 码全覆盖
- 4 个偏少码（Update 74, Collect Features 211, Extract by Attribute 164, Filter by Geometry 276）是 QGIS 脚本中真的罕见操作

### 技术细节
- QGIS alg_id 无空格（"joinattributesbylocation"）但语义映射 key 有空格（"Join attributes by location"）
- 修复：`_normalize()` 函数 strip 所有空格/下划线/特殊字符
- OP_PATCH 表覆盖 12 个常用但语义映射缺失的算子
- regex 需同时匹配单引号和双引号：`processing\.(?:runalg|run)\s*\(\s*['"]([^'"]+)['"]`
- 合并策略：每码上限 2,000，偏少码全保留 → 11,277 条

## 训练数据审查：API-trace 弱监督不能等权进入 SFT（2026-06-24）

### 核心发现
- `API_trace_to_L3_TRAINING_FINAL.jsonl` 的 raw 6,031 行不是干净训练集，而是混合候选池。
- 保守清洗后只有 1,112 行进入 clean，1,384 行只能作为 weak，3,535 行应 rejected。
- 最大问题不是 schema，而是监督信号错配：
  - 同一个 prompt 对应多个不同 L3 label。
  - task text 明确是 vector/raster，但 L3 label 模态相反。
  - LLM reasoning 明说代码片段不完整、来自不同脚本/工具、或实际代码和任务描述不匹配，却仍按描述生成 L3。
  - placeholder prompt 如 `QGIS script: script_xxx` 没有任务语义。

### 数量事实
| 分层 | 数量 |
|------|------|
| Raw | 6,031 |
| Clean | 1,112 |
| Weak | 1,384 |
| Rejected | 3,535 |
| Conflict rows | 1,367 |
| Conflict prompts | 513 |

主要 reject reason：
| Reason | Count |
|--------|-------|
| same_prompt_multi_label_conflict | 1,109 |
| task_l3_modality_mismatch | 915 |
| task_code_mismatch | 874 |
| placeholder_prompt | 279 |
| low_confidence | 174 |
| missing_confidence | 165 |

### 方法论结论
- API-trace + LLM 可以继续作为候选生成/弱监督来源，但必须先过数据门禁。
- Clean rows 可考虑进入 train-only augmentation 包；weak rows 需要人工审核、降权 loss 或后续 preference/rerank 方式使用；rejected rows 不能训练。
- `_training_quality.sample_weight` 现在已接入 V4.6 训练 loss：Teacher Forcing 和 AR scheduled-sampling 都使用 per-sample weighted CE。新的边界是：机制接入不等于模型能力提升，仍需服务器重训和 held-out vector family recall 验证。
- LLM 生成 prompt 不能鼓励“合理猜测”。无明确可执行 GIS 操作时，正确输出是空链或 reject。
- 训练 prompt 改为结构化后必须区分 checkpoint 输入分布：旧 DPO/SFT/QG checkpoint 评估默认 legacy，新结构化 prompt SFT checkpoint 才显式用 `--sft-prompt-style structured`。

## 训练机制审查：矢量规划能力需要 family/source-aware 学习信号（2026-06-24）

### 核心发现
- 单纯让 retriever/QGIS landing 更准，不能证明 L3 模型学会矢量处理规划。
- 旧训练机制主要是单 reference CE + task type 采样，不能确保 intersection / union / difference / repair / CRS / field calculation 等细粒度矢量 family 被有效学习。
- `vector_v2` / API-trace 弱数据混进 val/test 会让指标偏乐观；训练机制应只把生成/弱监督作为 train-only 且可降权的信号。

### 已完成机制修复
- 数据集返回 `sample_weight`，训练 loss 真正消费该权重。
- 结构化训练 prompt 保留 task type/name/goal 三个稳定字段，降低长 facts 文本截断导致的任务意图丢失。
- family/source-aware sampler 把稀有矢量 family、source quality、confidence/sample-weight 纳入采样权重。
- mixed/vector 包 length stats 不再静默回退旧 quality-gate stats。
- 评估脚本支持 prompt style 显式选择，避免旧 checkpoint 和新 structured checkpoint 混口径。

### 仍未证明
- 尚未完成新的 GPU 训练，因此还不能说“矢量规划能力已提升”。
- oversampled dry-run 显示默认 20 步时有 3,219 条 train sequence 超过 AR horizon；`--ar-max-steps 32` 已把该数降到 545，但需要服务器训练验证显存和效果。
- API-trace clean rows 还不是最终训练包；需要构建 train-only Step8 兼容包或经过人工审核后再纳入。

### 额外工程发现
- Python 单元素 tuple 容易踩坑：`("text")` 是字符串，不是 tuple；在 pattern list 中会变成逐字符匹配，造成大面积误拒。已加 `test_task_code_mismatch_patterns_are_tuples` 防回归。
- `llm_generate_l3_from_api_traces.py` 之前在后续 pure-attr/export gate 中使用原始 `confidence` 字段比较，LLM 返回字符串 confidence 时会 TypeError；已统一使用解析后的 `conf`。

## 路线 3 规模化验证（2026-06-20—22）

### 批量生产流水线
- deepseek-chat (via /v1, key sk-89eb...): 稳定，零空返回
- deepseek-v4-flash/pro: 常空返回，不可用于批量
- Base URL: `https://api.deepseek.com/v1`

### 质量门控体系（3 道筛）
1. **置信度门控**：单码<0.60 / 多码<0.50 拒绝，纯属性链 <0.70 拒绝
2. **渲染过滤**：`_is_rendering_only()` 检测 >50% 渲染/配色操作则拒绝
3. **自拒检测**：reasoning 含 "no geoprocessing" "only parameter definitions" 等短语则拒绝

### 重大 Bug：0.60 统一地板（2026-06-21）
- 曾加 `if conf < 0.60: return False` 作为全量门槛 → 80% LLM 输出被误杀
- 产率从 45% 骤降到 10%，自查发现一行代码错误
- 已修复为 per-case 判断，产率恢复到 42%

### 产率数据
| 批次 | 脚本 | 产出 | 产率 | conf 均值 | L3 码 |
|------|------|------|------|----------|------|
| POC (10) | 10 | 7 | 70% | - | - |
| 2k (25码) | 2,000 | 804 | 62% | 0.71 | 25 |
| 3k (40码) | 3,000 | 1,011 | 57% | 0.70 | 39 |
| 5k v1 | 5,000 | 1,689 | 47% | 0.66 | 40 |
| 5k v2 (修复版) | 5,000 | 1,603 | 45% | — | 40 |
| 10k | 10,000 | 3,200 | 42% | 0.66 | 40 |
| 全量v3 (进行中) | 43,000 | ~3,500估 | ~25% | — | — |

### 40 码扩充效果
- 15/15 新增码全部激活，40/40 全覆盖
- 最热新码：`L3_01_02_01:Add Field` + `L3_05_03_03:Raster to Vector`
- 罕见码也出现：`L3_03_05_02:Interpolation`、`L3_04_01_02:Viewshed`

### 全量产率低的原因（2026-06-22 漏斗分析）
```
68,845 脚本:
├── 32% skip_no_trace (UI/配置/测试，完全无 GIS 操作)
├── 8% skip_too_short (<2 步)
├── 29% 送 LLM
│   ├── 70% quality_reject (低置信度/纯属性/自否)
│   └── 30% kept (最终产出)
```
- **不是门控太严，而是 61% 脚本没有 GIS 信号。**
- 2k/3k/5k 产率高是因为先扫了 QGIS Core Processing 目录（处理算法密集）
- 全量扫到的是全区 68k 脚本，后半段多是 UI 代码/配置/测试

### 数据 vs 生成质量诊断
- 迹中有 `native:*` 调用名 → LLM 几乎不犯错（conf 0.85+）
- 纯 API 模式（CreateLayer/IterateFeature）→ LLM 合理但诚实低分（0.50-0.55）
- **核心杠杆是数据前筛，不是 prompt 工程**

### 描述数据发现（2026-06-21）
- yll 完整的 QGIS facts_summary: **20,428 条**（本地只有 2,260 子集）
- 通过门控的训练样本中 **97% 有真实描述** join
- 描述是真实的自然语言，不是模板
- `backfill_descriptions.py` 可回填已有批次，97% 覆盖率确认

### 人工质量审计汇总
- 三批次抽查 (5k v1: 30条, 5k v2: 30条, 10k: 30条) = **90 条**
- 高/中层: 60/60 正确 (100%)
- 低层: 25/30 合理, 3 被低估, 2 错误（渲染脚本误判，已修复）
- 修复后 10k 批次: 0 错误, 0 LLM自否

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

## V4.6 矢量训练机制审查修复（2026-06-24）
- 结论：当前修复的是训练机制和评估可信度，不是已经证明模型矢量规划能力提升。
- 已修：per-sample weighted CE、结构化 prompt、family/source-aware sampler、显式 length stats、TF-only smoke 守卫、AR horizon 可配置、unsafe qgis_unmappable_penalty 禁用、API-trace 清洗、旧 checkpoint legacy prompt 兼容。
- 新增关键发现：只靠文档约束不足以防止 `vector_v2` 式污染；训练入口必须默认拒绝 val/test 中的生成/LLM/API-trace source。现在 `eval_source_guard` 已实现，oversampled 主线包验证为 clean。
- 剩余风险：clean API-trace rows 尚未构造成 train-only Step8 包；weak/rejected rows 不能等权 SFT；structured-prompt 新模型必须用 `--sft-prompt-style structured` 评估。
- 下一步证据：服务器 warmstart SFT 后，用 held-out vector prompts 按 family recall、raster contamination、QGIS seed absorption、人工 A/B/C 共同判断，不能只看 landing validity 或 train-source absorption。
