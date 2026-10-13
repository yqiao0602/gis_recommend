# Planning Capability Audit（PCA）协议 — v0 DRAFT（待 owner 批准后冻结为 v1）

> **状态更新（2026-10-13）：本 v0 草案已经 owner 审查并按五处修订冻结为 v1。
> 当前权威版本：`PCA_PROTOCOL_V1_FROZEN.md`。本文件仅作历史保留，不得作为执行依据。**

> 起草日期：2026-10-13。依据：owner 指令（2026-10-13，本会话）——E2E Experiments A+B 双分支均触发
> （L1 内容错误 AND L2 grounding 独立不足，0c399113）后，**先验证 Stage 1 是否真正学会了 GIS 工作流
> 规划，不重训、不进 Stage 2**。本协议把该指令物化为可执行的预注册设计。
> 状态：**DRAFT — 全文待 owner 审查；§7 Open Questions 逐项裁定后方可冻结 v1。**

---

## 0. 目的与三个解耦问题

本实验回答三个此前混在 dev-120 Blueprint 评测里、未被分开的问题：

| # | 问题 | 本协议中的测量位置 |
|---|------|--------------------|
| Q1 | **会不会规划**：给定 GIS 任务，能否推断出合理、完整、顺序正确、依赖正确的操作步骤？ | 全部三组任务 × B 臂（无工具提示） |
| Q2 | **能不能迁移**：该能力是 GEE 数据学到的通用分解能力，还是 GEE 工作流模式记忆？ | A 组（GEE 域内 held-out）vs B/C 组（非 GEE 分布）的组间对比 |
| Q3 | **能不能落地**：给定合理规划，能否选对 QGIS 算子并构造正确 DAG？ | 本协议只做前置消融（C 臂：有无算子信息的增益）；完整 Q3 = 后续 Oracle/Predicted Plan→DAG 实验（§5.2） |

**明确不做的事**：不修改 21-family/blueprint 合同、不增加训练数据、不重训任何模型、不启动
Stage-2/RL。先测清楚现有模型会什么，再决定补什么训练。

---

## 1. 冻结对象与可复用资产

| 资产 | 位置 / 标识 | 用途 |
|------|------------|------|
| Stage-1 checkpoint（P0 fmt adapter） | mdzhang `/home/qy/stage1_run_planner_v2_fmt/stage1_adapter`（dev-1852 parse .8445，bs=8 批量仪器） | B/C 臂被测模型；**本协议发布即冻结**：不追加训练、不合并新 adapter |
| Base 模型 | mdzhang `/home/qy/models/Qwen3.5/Qwen3.5-9B-Base` | A 臂被测模型 |
| 批量生成仪器 | `scripts/p0_dev120_blueprint_gen.py` 模式（bs=8 left-pad、greedy、truncation 1024、gen_tokens/hit_cap 记录） | 三臂生成复用同一仪器骨架，仅替换 prompt 与臂配置 |
| QGIS 算子能力档案 | `route2_training/profile/qgis_operator_capability_profile_v0_4.json`（1,291 算子：normalized I/O 类型、参数 schema、mandatory/default） | C 臂算子信息卡唯一来源 |
| B 组任务候选源 | `docs/reports/v2a_manifest/v2a_A_dev.jsonl`（dev-120：task_text + processes/links gold + taskType） | B 组任务文本与金标反推材料 |
| A 组去重参照 | P0 训练数据 `blueprint_v2_gold_v3.jsonl`（37,044 行，SHA `621090bc…`）+ GEE 8,283 authority 任务文本池 | 训练文本池（执行时确认本地镜像或自服务器拉取，SHA 对账） |
| 去重参照（补充） | QGIS 1,334 SFT（`v2a_A_train.jsonl`）task_text | 覆盖 QGIS 侧训练文本 |

冻结即记录 SHA：adapter、base 指纹、任务集、金标、prompt 模板、judge prompt、检索产物（§6）。

---

## 2. 任务集（60 任务试点：A/B/C 三组 × 20）

### 2.1 组定义

- **A 组（GEE 域内 held-out，20 条）**：取自 GEE 权威池**未参与 P0 训练**的任务。
  目的：域内基线——模型在熟悉任务分布上是否学会了可泛化分解（vs 记住训练样本）。
  金标撰写规则：**从任务语义独立撰写**操作语义步骤与依赖；GEE canonical chain 仅作参考证据，
  **禁止把 GEE API 链直译为金标**（那是测记忆，不是测规划）。
- **B 组（QGIS 任务、不考具体算子，20 条）**：从 dev-120 任务文本中筛选：文本不含 QGIS
  算子名/ID（自动扫描 + 人工确认）；按复杂度分层选取。金标 = 由 gold `processes/links`
  **反推语义层**（de-grounding：算子→语义动作描述）后经 owner 审核。
  注：dev-120 曾用于 E2E Step-1 推理（无监督更新），"未参与训练"定义成立（OQ-2）。
- **C 组（复杂/组合型 GIS 任务，20 条）**：新写。覆盖矩阵（每格≥2）：
  多源数据融合 / 坐标系与投影处理 / 栅格-矢量组合 / 分区空间统计 / 条件与数据质量分支 /
  多步依赖长链。代理起草 → owner 逐条审核批准。

### 2.2 复杂度控制（硬要求）

每条任务标注 `complexity = {n_data_sources, expected_steps_band ∈ {≤4, 5–7, ≥8}, has_branching}`。
三组内三档分布配平（目标 6/10/4），**禁止拿简单 GEE 任务与困难 QGIS 任务直接比较**；
所有组间读数按 complexity tier 分层复核。

### 2.3 去重门（硬要求）

60 条 task_text 归一化后，对训练文本池（blueprint 37,044 + GEE 8,283 + QGIS 1,334）做：
8-gram 重叠扫描 + 归一化近似重复检查；命中即替换并记录。去重账本（每条的扫描结论）入 git。

### 2.4 金标 schema（每任务一记录，允许多合理路线）

```json
{
  "task_id": "PCA-B-07",
  "group": "A|B|C",
  "complexity": {"n_data_sources": 2, "expected_steps_band": "5-7", "has_branching": false},
  "task_text": "...",
  "gold": {
    "required_steps": [
      {"sid": "S1", "semantic": "...", "necessity": "essential|conditional",
       "alternatives": ["acceptable variant phrasing/vehicle"]}],
    "dependencies": [{"from": "S1", "to": "S3", "kind": "data|control"}],
    "required_conditions": ["verify CRS compatibility", "handle nodata", "..."],
    "acceptable_variations": ["whole-plan alternative route: ..."],
    "harmful_examples": ["a step that would corrupt the result"]
  },
  "provenance": {"source": "...", "dedup": "pass", "author": "draft-agent",
                 "owner_review": "pending|approved"},
  "sha256": "..."
}
```

金标表达**必要操作语义、依赖、必要条件、可接受替代**——不是唯一答案。语言：英文（OQ-6）。

---

## 3. 三臂对照设计

### 3.1 臂定义

| 臂 | 模型与输入 | 回答 |
|----|-----------|------|
| **A（base）** | Qwen3.5-9B-Base，无 adapter | 模型原本具备多少 GIS 规划能力 |
| **B（stage1）** | P0 fmt adapter，只接收任务描述，**无任何 QGIS 算子信息** | GEE 工作流训练是否提升了可迁移规划能力 |
| **C（stage1+tool）** | 同 B，额外注入 per-task 检索的算子能力卡 | 缺少工具知识是否是当前失败的重要原因 |

### 3.2 公平性约束（冻结）

- 三臂使用**同一评测 prompt 模板**、同一 decode 设置、同一生成预算；唯一差异 = C 臂在
  指令与任务之间插入 `[OPERATOR REFERENCE]` 段。B/C 差异**只**在算子信息。
- 评测 prompt 不使用 Blueprint SEP 术语、不使用 21-family 词汇、不出现训练格式线索。
- 输出格式 = 自由描述的操作节点与依赖（步骤名 + 语义 + 声明的依赖 + 数据条件），
  结束标记 `END OF PLAN`。**不禁算子名词**——评分只按操作语义，具体算子名对错不计分。

### 3.3 已知张力：格式 OOD（预注册声明）

P0 在 Blueprint JSON 格式上 SFT；本评测 prompt 对 P0 是格式 OOD。这**有意为之**：测的是
规划能力而非格式服从，且三臂同 prompt 公平。预案（OQ-4）：若 B 臂输出格式崩坏导致大面积
不可评，追加**诊断臂 B′**（P0 + Blueprint 格式 prompt，生成后转译为语义步骤再评）作为
解释性附录——B′ 不进主判读，只用于区分"不会规划"与"不会新格式"。

### 3.4 C 臂算子信息检索（冻结规则）

- 来源：capability profile v0.4（唯一来源，不用 Neo4j 在线查询）。
- 检索：all-MiniLM-L6-v2 嵌入，task_text vs 算子 name+description 余弦相似度，top-K=15
  （OQ-3）。卡片渲染：`operator_id | description | normalized inputs → outputs |
  mandatory params (名称+类型+说明，截断)`。
- 每任务的检索结果清单**整体冻结**（SHA 入账本），三臂运行共用同一份，不得运行期重算。
- 归因残余混淆（预注册声明）：C 臂提升可能来自"分解更好"或"算子描述直接提示了正确步骤"。
  §4.3 的归因字段 + §5.1 情况-3 判读处理此问题；C 臂增益**不能单独证明一般规划能力已学会**。

### 3.5 Decode 与终止（冻结）

裸 greedy（不加 repetition_penalty / ngram 约束），`max_new_tokens=768`（OQ-3），
`gen_tokens` + `hit_cap` 逐行记录。**不加终止修正**：终止健康（END OF PLAN 命中、字面
循环、cap 截断）本身是"适当终点停止"能力的被测信号（R1 教训：修复期加终止控制会掩盖能力
缺陷；本实验是审计不是部署）。judge 评超长输出时按冻结截断规则（保前 60 步 + 注明截断）。

---

## 4. 评测指标（五类，核心两个）

### 4.1 指标定义

| 指标 | 定义 | 级别 |
|------|------|------|
| **任务完成充分性**（核心） | 整计划能否实现任务目标；judge 按 rubric 盲评 0–3（0=不能 … 3=完整可实现） | 计划级 |
| **依赖关系准确率**（核心） | 计划声明/隐含的步骤依赖 vs gold dependencies；含顺序矛盾计数（计划自身是否拓扑自洽） | 计划级 |
| 必要步骤召回率 | gold required_steps 被（语义等价地）覆盖的比例；alternatives 认可即算覆盖 | 步骤级 |
| 不必要步骤率 | 计划中未被 gold 认可且非合理替代的步骤；分 `extra_benign` / `extra_harmful`（参照 harmful_examples 与语义判断） | 步骤级 |
| 条件与约束处理 | required_conditions 被计划显式或隐式处理的比例（CRS、数据类型、单位、空值等） | 条件级 |

步骤数相同 ≠ 计划正确；步骤名相似 ≠ 能得到正确结果——故充分性与依赖准确为主读数，
步骤级指标为分解诊断。

### 4.2 判分执行（LLM-judge + 人工复核闭环）

- Judge：deepseek-v4-pro（env key，项目既有调用链），温度 0，结构化 JSON 判分 + 证据引文；
  judge prompt 固化并 SHA 冻结（OQ-7：是否加第二 judge 交叉）。
- 盲评：judge 不获知臂别与任务组别。残余风险如实声明：SFT 后的风格差异可能泄露臂别，
  无法完全盲；接受该残差并在报告中注明。
- 多合理路线：judge 指令明确"不同但有效的路线不判错"，对照 `acceptable_variations`；
  争议题标 `escalated`，owner 仲裁后定稿。
- **人工复核（试跑主要目的之一）**：owner 盲评子集 ≥30%（=18 任务 × 3 臂 = 54 份，
  A/B/C 组分层覆盖），与 judge 逐题一致率 + sufficiency 加权 κ。**信度线（建议）**：
  κ≥0.6 且核心项一致率 ≥75%；不达标 → 修 rubric → 全量重评 → 再抽复核（OQ-5）。
  自动指标只作辅助；金标、评分规则、人工复核一致性未验证前不扩大任务集。

### 4.3 C 臂归因附加字段

judge 对 C 臂逐计划输出：`steps_suggested_by_reference`（与检索卡算子对应的步骤及其
sid）、`steps_improved_without_reference`。用于区分"工具信息直接提示步骤"与"分解质量
真改善"。

---

## 5. 判读（预注册）

### 5.1 四情况判读树（owner 设计的形式化）

判读单位 = **分组 × 臂的核心指标向量**（sufficiency + dependency 为主，配 complexity
分层与逐案审阅），**不设单总分裁决**；60 样本只做方向性判读 + 效应量参考（如组间差
≥15pp 视为明显），显著性检验不做（OQ：不做，避免小样本伪精确）。最终判读归 owner。

| 情况 | 观测 | 结论与行动方向 |
|------|------|----------------|
| 1 | B/C 臂在 B、C 组都好 | 具备工具无关规划能力 → 主攻 grounding/参数/DAG（Stage-2 方向），不重做 Stage-1 |
| 2 | A 组好、B/C 组明显差 | 迁移存在障碍但不能断言"完全不会规划" → 进一步检查任务差异、领域知识差异、规划结构迁移性 |
| 3 | B 差、C 明显好 | 工具知识是重要因素 → 用 §4.3 归因字段判断是分解改善还是算子描述直接补了步骤知识；再定 Stage-2 知识注入设计 |
| 4 | Base 与 Stage-1 都差 | 当前 Stage-1 训练未展示可靠规划增益 → 优先诊断训练数据、Task→Plan 监督信号与规划目标，**不归因于 QGIS 工具知识** |

### 5.2 后续实验（本协议之后，另行立项）

规划评测基本可信后，隔离验证落地：
1. **Oracle Plan → QGIS DAG**：喂人工审核过的合理计划，测算子/参数/依赖选择；
2. **Predicted Plan → QGIS DAG**：Stage-1 自生成计划交给落地。
两者差距指示端到端错误中规划侧占比；**预注册声明：错误相互影响，分数差不是严格因果贡献**。

---

## 6. 执行阶段与产物

| Phase | 内容 | 依赖 |
|-------|------|------|
| 0 | 本协议 owner 审查 → 裁定 §7 → 升级 `PCA_PROTOCOL_V1_FROZEN.md` | owner |
| 1 | 任务集+金标构建：60 条起草、去重账本、复杂度配平、owner 逐条批准 → `pca_tasks_v1.jsonl` + `pca_gold_v1.jsonl`（SHA 冻结） | blueprint 数据镜像 SHA 对账 |
| 2 | 仪器 smoke：5 任务 × 3 臂跑通生成+judge+评分管线；owner 对 15 份快检一致性 | Phase 1 |
| 3 | 正式跑：180 生成（GPU，分钟级，共租纪律：先查 nvidia-smi）→ judge 180 份 → 人工复核 54 份 | Phase 2 |
| 4 | 分析 + `PCA_RESULTS_V1.json` + `PCA_REPORT_V1.md` → owner 判读 | Phase 3 |

产物目录：本目录（`planning_capability_audit_v1/`）。冻结账本：任务/金标/prompt/judge
prompt/检索清单/adapter/base 的 SHA + 生成配置（bs=8、greedy、768、trunc 1024）。

---

## 7. Open Questions（owner 逐项裁定后冻结 v1）

| # | 问题 | 起草建议 |
|---|------|----------|
| OQ-1 | A 组 GEE held-out 任务来源：内部权威池 held-out vs 外部源（AutoGEEval 等） | 内部池（域内定义干净；外部留作以后 OOD 扩展） |
| OQ-2 | B 组允许用 dev-120 任务文本吗（曾被 E2E Step-1 推理消费，但从未入训练） | 允许 |
| OQ-3 | 生成预算与检索参数：max_new_tokens=768、C 臂算子段 ≤1200 tok、top-K=15 | 按建议值 |
| OQ-4 | 是否接受 B′ 诊断臂预案（仅当 B 臂格式崩坏时启用，不进主判读） | 接受 |
| OQ-5 | 人工复核规模与信度线：18 任务×3 臂=54 份；κ≥0.6 且一致率 ≥75% | 按建议值 |
| OQ-6 | 金标与 judge 语言 | 全英文 |
| OQ-7 | Judge 配置：deepseek-v4-pro 单 judge + owner 复核，还是加第二 judge 交叉 | 单 judge + owner 复核（试跑够用；扩大时再加交叉） |

---

## 8. 硬性边界

- 不重训任何模型；P0 adapter 与 Base 冻结为本协议唯一被测对象。
- 不修改 21-family/blueprint 合同（`PLANNER_V2_CONTRACT_FREEZE_v1.md` 继续有效）；
  不动 Stage-2/RL 冻结；不动 benchmark v0.2.1 sealed gold 与 refusal 行。
- PCA 金标是**诊断评测资产**，不进入任何训练池、不得反向修改 benchmark 或训练数据。
- GPU 共租纪律（mdzhang）：launch 前查 `nvidia-smi --query-compute-apps`；yyt 与并行
  C0/A1' 线共享 GPU；禁杀外部进程。若用租卡机：产物回迁规则
  （`RENTED_BOX_ARTIFACT_POLICY_v1.md`）适用。
- 训练文本池数据文件只读；去重扫描不得修改数据。
