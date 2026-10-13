# Planning Capability Audit（PCA）协议 — v1 FROZEN（2026-10-13）

> 依据：owner 审查裁定（2026-10-13）——批准实验主线与七项 OQ 建议方向，按五处修订后冻结。
> v0 草案：`PCA_PROTOCOL_V0_DRAFT.md`（保留作历史，已被本文件取代）。
> 状态：**FROZEN。冻结后如需改动 → 升级 v1.1 并记录 diff，不得静默修改。**
> 定位声明（owner 判断标准）：本轮实验**不是为了证明 Stage 1 成功或失败**，目标是确定
> 现有证据能支持什么结论。若模型在工具无关计划中已能提出合理步骤并建立正确依赖，则
> 此前 QGIS Blueprint 低分不能否定其规划能力；反之，在格式问题被排除、金标可靠的前提
> 下仍无法提出充分计划，才有依据调整 Stage-1 训练目标或监督数据。

## 变更记录（v0 → v1，owner 五处修订的落实位置）

| # | 修订 | 落实 |
|---|------|------|
| R1 | 格式健康与规划质量分开；B′ 不等崩坏、预选子集常跑 | §3.3（B′ 重定义）、§4.0（格式健康四指标）、§6 Phase-2 smoke 门 |
| R2 | A/B/C 差异不全是迁移；分层记录 + 语义配对任务 + 分开报告 | §2.2（task_type 分层）、§2.5（配对任务）、§5.1（迁移读数三分解） |
| R3 | C 臂结论限定为"工具信息对计划质量的影响"；三类统计 | §4.3、§5.1 情况-3 措辞 |
| R4 | 冻结算子检索与生成环境全量参数 | §3.4、§6 冻结账本 |
| R5 | 人工复核统计口径预注册（κ 种类、计算方式、抽样方案） | §4.2 |

---

## 0. 目的与三个解耦问题

| # | 问题 | 测量位置 |
|---|------|----------|
| Q1 | **会不会规划**：给定 GIS 任务，能否推断出合理、完整、顺序正确、依赖正确的操作步骤 | 全部三组 × B 臂（无工具提示） |
| Q2 | **能不能迁移**：能力是 GEE 学到的通用分解能力，还是 GEE 工作流模式记忆 | 配对任务内差 + task_type 分层组间差 + 域内/跨域分解（§5.1） |
| Q3 | **能不能落地**：合理规划能否选对 QGIS 算子并构造正确 DAG | 本协议只做 C 臂前置消融；完整 Q3 = 后续 Oracle/Predicted Plan→DAG 实验（另行立项） |

**不做**：不重训、不改 21-family/blueprint 合同、不加训练数据、不启动 Stage-2/RL。

---

## 1. 冻结对象与可复用资产

| 资产 | 位置 / 标识 | 用途 |
|------|------------|------|
| Stage-1 checkpoint（P0 fmt adapter） | mdzhang `/home/qy/stage1_run_planner_v2_fmt/stage1_adapter`（dev-1852 parse .8445） | B/C 臂被测模型；本协议发布即冻结 |
| Base 模型 | mdzhang `/home/qy/models/Qwen3.5/Qwen3.5-9B-Base` | A 臂被测模型 |
| 批量生成仪器 | `scripts/p0_dev120_blueprint_gen.py` 模式（bs=8 left-pad、greedy、trunc 1024） | 三臂生成骨架 |
| QGIS 算子能力档案 | `route2_training/profile/qgis_operator_capability_profile_v0_4.json`（1,291 算子） | C 臂算子卡唯一来源 |
| B 组任务候选源 | `docs/reports/v2a_manifest/v2a_A_dev.jsonl`（dev-120） | B 组任务文本与金标反推材料 |
| A 组去重/隔离参照 | `blueprint_v2_gold_v3.jsonl`（37,044 行，SHA `621090bc…`）+ GEE 8,283 authority + QGIS 1,334 SFT task_text | 训练文本池与来源记录 |
| B′ 转译参照 | Blueprint 21-family 语义名称表（`C6_V2_STAGE_CLASSES_DEV.json` 及合同文件） | B′ Blueprint→语义步骤转译 |

---

## 2. 任务集（60 试点：A/B/C 三组 × 20）

### 2.1 组定义

- **A 组（GEE 域内 held-out，20 条）**：内部 GEE 权威池未参与 P0 训练的任务。
  金标从任务语义独立撰写；GEE canonical chain 仅作参考证据，**禁止把 GEE API 链直译为金标**。
- **B 组（QGIS 任务、不考具体算子，20 条）**：dev-120 文本筛选（无算子名/ID + 分层）。
  金标 = gold `processes/links` 反推语义层后经 owner 审核。
- **C 组（复杂/组合型，20 条）**：新写。覆盖矩阵（每格≥2）：多源融合 / 坐标系投影 /
  栅格-矢量组合 / 分区统计 / 条件与质量分支 / 多步依赖长链。代理起草 → owner 逐条批准。

### 2.2 分层字段（v1 扩展）

每条任务标注：

```json
"task_type": "<closed list: raster_temporal | vector_topology | projection_crs |
              raster_vector_combo | zonal_stats | quality_branching |
              multi_source_fusion | terrain_analysis | sampling_stats | other>",
"complexity": {"n_data_sources": N, "expected_steps_band": "≤4|5-7|≥8",
               "has_branching": bool}
```

三组内 `task_type` 分布表入金标文件；组间读数按 task_type 分层复核；复杂度配平目标
6/10/4 不变。**禁止拿简单 GEE 任务与困难 QGIS 任务直接比较。**

### 2.3 去重门 + A 组隔离证据分级（OQ-1 条件落实）

- 去重：60 条 task_text 归一化后对训练文本池做 8-gram 扫描 + 近似重复检查；命中即替换，
  账本入 git。
- A 组每条带 `isolation: source_record_verified | text_dedup_only`：
  - `source_record_verified`：来源记录（record_id / source_sha）不在 P0 训练数据来源集合；
  - `text_dedup_only`：仅文本去重通过、来源级隔离无法证明
    → 报告中标记 `isolation_evidence_insufficient` 单列披露。
  选取优先 `source_record_verified`；两类条数在报告中强制披露。

### 2.4 B 组复用审计（OQ-2 条件落实）

- 筛选规则（无算子名扫描 + task_type/complexity 分层 + 预注册 seed）**先于查看任何
  E2E Step-1 预测结果冻结**；筛选脚本与审计注记声明：任务挑选零参考预测文件，
  禁止用已见预测挑选"有利任务"。
- dev-120 曾被 E2E Step-1 / 实验 A 推理消费（无梯度影响）；注记入任务账本。
- 金标反推由 owner 独立审核，与预测结果无关。

### 2.5 语义配对任务（v1 新增，≥6 对）

构造 ≥6 对配对任务（占用 A/B/C 组名额）：每对 = **同一空间分析目标**，GEE 习惯表述版
（A 组）+ 工具无关 GIS 表述版（B 或 C 组），复杂度对齐。`pair_id` 入金标。配对内同臂
分数差 = 表述/域偏差的最干净控制。

### 2.6 金标 schema

```json
{
  "task_id": "PCA-B-07", "group": "A|B|C", "pair_id": null | "P01",
  "task_type": "vector_topology",
  "complexity": {"n_data_sources": 2, "expected_steps_band": "5-7", "has_branching": false},
  "task_text": "...",
  "gold": {
    "required_steps": [{"sid": "S1", "semantic": "...",
                        "necessity": "essential|conditional",
                        "alternatives": ["..."]}],
    "dependencies": [{"from": "S1", "to": "S3", "kind": "data|control"}],
    "required_conditions": ["verify CRS compatibility", "..."],
    "acceptable_variations": ["whole-plan alternative route: ..."],
    "harmful_examples": ["..."]
  },
  "isolation": "source_record_verified | text_dedup_only | n/a(B/C组)",
  "provenance": {"source": "...", "dedup": "pass", "author": "draft-agent",
                 "owner_review": "pending|approved"},
  "sha256": "..."
}
```

语言：全英文（任务、金标、prompt、judge rubric；OQ-6 裁定）。

---

## 3. 三臂对照设计

### 3.1 臂定义

| 臂 | 模型与输入 | 回答 |
|----|-----------|------|
| A（base） | Qwen3.5-9B-Base | 原本具备多少 GIS 规划能力 |
| B（stage1） | P0 adapter，仅任务描述，无算子信息 | GEE 训练是否提升可迁移规划 |
| C（stage1+tool） | 同 B + per-task 算子卡 | 工具知识对计划质量的影响 |
| B′（诊断，常设） | P0 adapter + **Blueprint 训练格式 prompt**，生成后确定性转译为语义步骤再评 | 格式敏感性诊断；**不进主比较** |

### 3.2 公平性约束与声明

- A/B/C 三臂同一评测 prompt 模板、同一 decode、同一预算；唯一差异 = C 臂插入
  `[OPERATOR REFERENCE]` 段。
- 评测 prompt 不含 21-family 词汇、不要求 QGIS 算子 ID、无训练格式线索；不禁算子名词，
  评分只按操作语义，算子名对错不计分。
- **预注册声明（owner R1）**：三臂同 prompt 只保证输入条件一致，**不保证格式难度相同**——
  Base 与 Stage-1 训练经历不同、格式熟悉度本就可能不同。格式健康按臂分别报告（§4.0），
  判读时格式效应与内容效应分离。

### 3.3 B′ 诊断臂（v1 重定义，OQ-4 落实）

- **常设子集**：预选 6 个任务（A/B/C 各 2，配对任务优先）× B′ 必跑——不等主臂崩坏。
- **机械扩大条件**（预注册，可自动判定）：主评测中 B 臂 `content_assessable_rate < 0.70`
  → B′ 扩大到全部 60 条。
- 转译器（Blueprint JSON → 语义步骤序列）在 Phase 2 前实现并冻结（含 21-family 语义名
  映射表与 repeat 展开规则），SHA 入账本。
- B′ 结果只进报告的诊断章节，用于区分"不会规划"与"不会新格式"。

### 3.4 C 臂检索（冻结规则，R4 落实）

- 来源：capability profile v0.4 唯一来源。
- 检索：sentence-transformers **all-MiniLM-L6-v2**（记录模型确切版本/revision hash）、
  归一化嵌入、余弦相似度、task_text vs 算子 name+description，top-K=15。
- 卡片渲染：`operator_id | description | normalized inputs → outputs | mandatory params`
  （截断规则冻结）。
- **冻结存档**：每任务 top-15 的算子 ID + 相似度分数 + 最终注入的卡片渲染全文，一次性
  物化为 `pca_retrieval_v1.json`（SHA 冻结），三臂运行共用，不得运行期重算。

### 3.5 Decode 与终止（冻结）

裸 greedy（不加 rep-penalty / ngram 约束），`max_new_tokens=768`，`gen_tokens` + `hit_cap`
逐行记录。终止健康是被测能力信号（R1 教训：评测期加终止修正会掩盖能力缺陷）。
smoke 后若改预算：**必须版本化**（v1.1 + diff 记录），不得静默调整（OQ-3 条件）。

---

## 4. 评测指标

### 4.0 格式健康（v1 新增，先于质量指标独立报告，R1 落实）

每条生成记录标注四个字段，**与规划质量分开报告**：

| 字段 | 判定 |
|------|------|
| `format_valid` | 输出可辨认出 ≥1 个步骤节点（有结构） |
| `content_assessable` | 内容足以判分（步骤语义可理解，非空壳/纯重复） |
| `hit_cap` | 达到 max_new_tokens（仪器已有） |
| `termination_status` | 四分类：`END_OF_PLAN` / `EOS` / `CAP_TRUNC` / `DEGENERATE_LOOP`（沿用 R1 终止四分法口径） |

**可评集定义**：`content_assessable=true` 的记录进入 §4.1 质量指标；不可评记录不计入
质量分母，但其**占比按臂×组强制报告**（占比本身是能力信号）。判读规则：质量结论只在
可评率不构成混杂时成立（如 B 臂可评率 <70% 时，其质量分须与 B′ 诊断联合解读）。

### 4.1 规划质量五指标（可评集内计算）

| 指标 | 定义 | 级别 |
|------|------|------|
| **任务完成充分性**（核心） | 整计划能否实现目标；judge 盲评 0–3 | 计划级 |
| **依赖关系准确率**（核心） | 计划依赖 vs gold dependencies + 计划自洽性（顺序矛盾计数） | 计划级 |
| 必要步骤召回率 | required_steps 被语义等价覆盖的比例（alternatives 认可即覆盖） | 步骤级 |
| 不必要步骤率 | 未被认可的步骤，分 `extra_benign` / `extra_harmful` | 步骤级 |
| 条件与约束处理 | required_conditions 被处理的比例 | 条件级 |

### 4.2 判分执行与人工复核（统计口径预注册，R5 落实）

- Judge：deepseek-v4-pro（env key），温度 0，结构化 JSON + 证据引文，prompt SHA 冻结；
  **声明：模型评分不是独立真值**（OQ-7 条件），一切质量结论以"judge + 人工复核信度"
  为限。
- 盲评：judge 不知臂别/组别；风格泄露残差如实声明。
- 多合理路线：对照 `acceptable_variations`，不同但有效路线不判错；争议标 `escalated`
  由 owner 仲裁。
- **人工复核抽样方案（预注册）**：18 任务 = A/B/C 各 6，按 task_type×complexity 分层
  随机（seed=20261013 预注册），三臂全评 = 54 份；报告抽样清单与任务覆盖表
  （OQ-5 条件）。
- **一致性统计口径（预注册，不得见结果后选择）**：
  - sufficiency 0–3（有序）：**quadratic weighted κ**（`sklearn cohen_kappa_score,
    weights='quadratic'`）+ 完整 4×4 混淆矩阵 + 逐级一致率；
  - 步骤覆盖（三分类 yes/alternative_ok/no）：一致率 + unweighted κ；
  - 依赖结构（任务级二值：无矛盾且覆盖全部必要依赖）：一致率 + unweighted κ；
  - 条件处理覆盖率：数值一致率 + 平均绝对误差。
  - **信度线**：sufficiency QWκ ≥ 0.6 且核心项（依赖结构）一致率 ≥ 75%；不达标 →
    修订 rubric → 全量重评 → 再抽复核（不得只保留较一致案例，OQ-7 条件）。

### 4.3 C 臂归因三类统计（R3 落实）

judge 对 C 臂逐计划输出并汇总三类：

1. `steps_hinted_by_cards`：算子卡**明确提示或强烈暗示**的步骤（judge 判级
   explicit/strong/none，引用卡文本为证）；
2. `steps_unhinted_correct`：**未被卡直接提示但正确规划出**的步骤；
3. Δdependency / Δsufficiency：B→C 的依赖与充分性增量。

**结论限定（预注册措辞）**：C 臂结果只允许表述为"**工具信息对计划质量的影响**"；
除非另有对照，不得表述为"C 臂证明了通用规划能力提升"。

---

## 5. 判读（预注册）

### 5.1 四情况判读树

判读单位 = 分组 × 臂的核心指标向量（sufficiency + dependency），按 task_type 与
complexity 分层复核；**不设单总分裁决**；60 样本 = 方向性判读 + 效应量参考（组间差
≥15pp 视为明显），不做显著性检验。最终判读归 owner。

**迁移读数三分解（R2 落实）**——A vs B/C 原始均值差**不得直接称为迁移效应**；迁移读数 =
(i) 配对任务内差（§2.5）+ (ii) task_type 分层控制后的组间差 + (iii) 域内/跨域分解；
三者一致指向时才可称为"迁移障碍/迁移成功"的初步证据。

| 情况 | 观测 | 结论与方向 |
|------|------|-----------|
| 1 | B/C 臂在 B、C 组都好 | 具备工具无关规划能力 → 主攻 grounding/参数/DAG（Stage-2 方向），不重做 Stage-1 |
| 2 | 域内（A 组）好、跨域（B/C 组）差 | 迁移存在障碍但不能断言"完全不会规划" → 用三分解区分迁移困难 vs 任务类型差异 |
| 3 | B 差、C 明显好 | 用 §4.3 三类统计判断是分解改善还是卡片直接补了步骤知识；结论限定"工具信息的影响"；再定 Stage-2 知识注入设计 |
| 4 | Base 与 Stage-1 都差 | 当前 Stage-1 训练未展示可靠规划增益 → 优先诊断训练数据、Task→Plan 监督信号与规划目标，不归因于 QGIS 工具知识 |

### 5.2 后续实验（另行立项）

规划评测基本可信后：Oracle Plan → QGIS DAG；Predicted Plan → QGIS DAG。
**预注册声明：两者分数差不是严格因果贡献**（错误相互影响）。

---

## 6. 执行阶段与冻结账本

| Phase | 内容 | 状态 |
|-------|------|------|
| 0 | 协议 v0 起草 → owner 五处修订裁定 → **本 v1 冻结** | ✅ 完成（2026-10-13） |
| 1 | 任务+金标构建：60 条起草、去重账本、配对任务、分层配平 → **owner 逐条审核** | **当前阶段** |
| 2 | 仪器 smoke 门：预选 5 任务（跨 task_type，金标已批）× 3 臂 + B′ 常设 6 任务；检查可解析性/终止/可评性/**预算充足性**；预算变更须 v1.1 版本化；owner 快检一致性 | 待 Phase 1 审核通过 |
| 3 | 正式跑：180 生成 + judge + 人工复核 54 份（GPU 共租纪律：先查 nvidia-smi） | 待 Phase 2 通过 |
| 4 | 分析 + `PCA_RESULTS_V1.json` + `PCA_REPORT_V1.md` → owner 判读 | — |

**执行权限（owner 重申）**：不重训、不改 21-family 合同、不启动 Stage-2/RL；
任务金标经 owner 审核通过前，不运行正式 180 次生成。

**冻结账本（SHA 清单，Phase 2 前齐备）**：

1. 任务集 `pca_tasks_v1.jsonl` + 金标 `pca_gold_v1.jsonl` SHA；
2. 评测 prompt 模板、judge prompt（含 rubric）SHA；
3. 检索环境：embedding 模型名+revision、向量化/相似度配置、`pca_retrieval_v1.json`
   （每任务 top-15 ID+分数+注入卡片全文）SHA；
4. 生成环境：base 权重指纹（safetensors SHA / HF revision）、adapter 文件 SHA 账本、
   精度设置（NF4 参数）、每条记录 prompt token 数、decode 参数（greedy/768/bs=8/left-pad）、
   B′ 转译器脚本 SHA；
5. 复核抽样清单（seed=20261013）与计算脚本 SHA。

产物目录：`planning_capability_audit_v1/`。

---

## 7. OQ 裁定记录（owner，2026-10-13）

| # | 裁定 | 执行条件（已落实于） |
|---|------|---------------------|
| OQ-1 | 批准，有条件：内部 GEE 池 held-out | 核实来源级隔离；只能证文本不重时标 `text_dedup_only`（§2.3） |
| OQ-2 | 有条件批准：复用 dev-120 文本 | 筛选先于查看预测冻结、不得挑有利任务、金标独立审核（§2.4） |
| OQ-3 | 有条件批准：768 / 1200 / K=15 | smoke 验证格式与长度充足性；改预算必须版本化（§3.5、§6 Phase-2） |
| OQ-4 | 批准：B′ 诊断臂 | 预选 6 任务常跑 + 机械扩大条件（content_assessable_rate<0.70）（§3.3） |
| OQ-5 | 批准：54 份复核 | 披露抽样方案、任务覆盖、一致性计算方式（§4.2） |
| OQ-6 | 批准：全英文 | §2.6 |
| OQ-7 | 有条件批准：单 judge + owner 复核 | 模型评分不作独立真值；信度线不达标必须修 rubric 重评、不得择优保留（§4.2） |

---

## 8. 硬性边界

- 被测对象冻结为 P0 adapter + Base，本协议期间不追加任何训练/合并。
- 不修改 21-family/blueprint 合同（`PLANNER_V2_CONTRACT_FREEZE_v1.md` 继续有效）；
  不动 Stage-2/RL；不动 benchmark v0.2.1 sealed gold 与 refusal 行。
- PCA 金标是**诊断评测资产**：不入训练池、不反向修改 benchmark 或训练数据。
- v1 冻结后任何修改走 v1.1 + diff 记录；评测执行期禁止静默改预算/改 prompt/改 rubric。
- GPU 共租纪律（mdzhang）与租卡机产物回迁规则
  （`RENTED_BOX_ARTIFACT_POLICY_v1.md`）适用。
- 训练文本池数据只读；去重扫描不修改数据。
