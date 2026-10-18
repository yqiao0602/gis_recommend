# B_TRACK_DATA_GOVERNANCE_SPEC_V1（B 轨训练数据治理规范 V1）

- **日期**：2026-10-18；**状态**：V1 冻结候选（owner 决策：B 轨自数据审计阶段转入训练数据
  治理与规划能力验证阶段；本规范为阶段一交付）
- **上游证据**：Q2 全链（40 对人工判读 → 10 对源码级核验 → 4,554 对池级机械扫描 →
  117 条双轴判读 → 池级加权估计 → owner 抽查第 1 轮 3/3 维持）
- **权威产物**：`Q2_ADMISSION_V1.json`（117 条准入分桶，机器可读）、
  `Q2_EXTRACT_RELATION_V1.json`（关系级）、`Q2_EXTRACT_SAMPLE_V1.json`（样本级，221 唯一）、
  `Q2_ARCHIVE_FREEZE_INDEX_V1.md/.json`（归档冻结索引）
- **验收标准（owner 原文）**：不是把数据清洗得足够少，而是任何一条样本为什么被保留、
  修改或排除，都可以追溯到具体证据和规则。

---

## 0. 三条上游认识（本规范的前提，不重复论证）

1. **粗粒度链条差异 ≠ 规划能力差异**：P(结构等价|近重复对)=0.942 [0.90, 0.97]；
   117 条中任务逻辑驱动的规划结构差异样本点估计 = 0（上界 0.057）。RLE 序列不同
   不得直接当作不同规划参考答案。
2. **真实任务语义部分存在于操作序列之外**：数据集版本、阈值、时间范围、波段、
   数组/矩阵操作、UI 脚手架——影响代码表现但不一定是规划层变化；反之 RLE 相同
   也不能证明任务语义一致。
3. **数据治理须同时处理"参考答案可信度"与"表示能力"**：只清洗错误样本而保留表达
   不足的 RLE，或只做双层表示而保留失实指令，监督信号都有问题。两件事分轨但同批
   推进（阶段一：治理规则；阶段二：双层表示）。

## 1. 判读层级（adjudicator tier）与置信度语义

| 层级 | 定义 | 写入字段 | 效力 |
| --- | --- | --- | --- |
| `owner` | owner 亲判 | `adjudicator=owner` | 终判；可直接作为规则锚点 |
| `agent-delegated` | agent 在 owner 三轮方法学裁定下判读 | `adjudicator=agent (owner-delegated, ...)` | **provisional**：未经 owner 抽查的记录标注 `provisional=true`；抽查维持后转 `reviewed_maintained` |
| `owner_spot_check` | owner 对 agent 判读的抽查 | `owner_spot_check=reviewed_maintained_with_refinements` | 抽查记录按 owner 精化后的字段为准 |

**置信度**：`高/中/低` + 可选 `不可判`。规则：
- 高 = 静态源码直接支持，不依赖相似度推断；
- 中 = 判定成立但存在未穷尽证据（长 diff 未通读/间接引用未核）；
- 低 = 仅能从机械信号推断；
- 不可判 = 证据不足，**不得强行归类**（`Q2_insufficient` 桶）。

**当前状态**：owner 亲判 8 / agent 109；owner 抽查第 1 轮覆盖 S117/S090/S096（3/3 维持）。
其余 106 条 agent 记录为 `provisional`（见 §7 状态机）。

## 2. 双标签类体系与证据要求

主标签（primary）为**单一**分类；辅标签（secondary）可空或一个。标签本身是**差异
分类**，不是训练标签（owner 第三轮 + S117 抽查裁定）。

| 主标签 | 定义 | 最低证据要求 |
| --- | --- | --- |
| `substantive_structural_candidate` | 必要步骤/依赖/分析阶段发生实质变化 | 源码 diff 定位到具体调用增删或路径切换 |
| `asset_version_candidate` | 数据资产/版本变化，流程不变 | 双方数据集字面量 + 流程同构证据 |
| `ui_scaffold_candidate` | UI/展示/调试输出差异 | 差异定位到 ui.*/Map.*/print 类调用 |
| `duplicate_block_candidate` | 重复声明/拼接造成差异 | 重复计数证据（声明次数/dup_lines） |
| `reorder_refactor_candidate` | 重排/重构，语义可交换 | 多重集相同或交换律论证 |
| `small_literal_cosmetic_candidate` | 小字面量/修饰差异 | 字面量对照表 |
| `template_multiplicity_artifact` | 模板集合差异的重叠伪影 | 双方代表链 + 共享模板证明 |
| `same_code_two_descriptions`（same 桶） | 代码逐字节相同 | sha1 相同 |
| `same_template_literal_diff`（same 桶） | 同 RLE 模板、字面量不同 | canonical/字面量对照 |
| `formatting_only`（same 桶） | 仅格式差异 | 归一化源码相同 |
| `same_template_canonical_diff`（same 桶） | 同 RLE、canonical 不同 | canonical 差异定位（或"未定位"标注） |

**双轴分离**：`difference_source`（规划结构/参数字面量/实现与脚手架/证据不足，可多选）
独立于 `fidelity_A/B`（失实/欠描述/忠实/不可判）。**描述与源码不符不得计入"应学不同
结构"证据**（owner 纪律）。

**三条横切规则（owner 抽查第 1 轮）**：
1. 机械标签是差异分类，不代表实际存在字面量变化——`difference_source` 按源码真实
   差异填写；
2. 同码对可承载事实性描述错误——数量/单位/阈值须与代码**及数据集值定义**一致，
   分辨率不能替代值单位证据；
3. RLE 空步 = 抽取范式缺口（数组/矩阵/序列平滑类），不是"无结构"；空 RLE 普查列入
   机械漏检审计。

## 2.1 三个独立判断（owner 首轮复核裁定，2026-10-18）

**结构等价 / 同构模板 / 多参考不得互相替代**：

| 判断 | 回答的问题 | 字段 | 示例 |
| --- | --- | --- | --- |
| 结构等价 | 两个实现的高层规划结构是否相同？ | `structural_equivalence` | R19 日期窗变化下的同构 |
| 同构模板 | 不同任务是否共享相似规划模式？ | `isomorphic_template_of` | R18-A 棉花 vs 大豆 |
| 多参考 | 同一任务条件下是否接受多个实现为正确答案？ | `multiref_of` + `applies_when` | R18-B 待确认候选 |

- 同构模板**不**产生训练多参考；多参考**必须**同任务条件 + 明确 `applies_when`；
- 结构等价**不**意味着参数/条件可忽略（R19）。

## 2.2 三个独立状态字段（owner 首轮复核裁定，2026-10-18）

每条参考样本必须分别记录：

| 字段 | 取值 | 含义 |
| --- | --- | --- |
| `semantic_judgment_confidence` | 高/中/低 | 对结构或语义关系的判断可靠性 |
| `evidence_completeness` | complete / partial / anchor_pending | 支持判断的源码证据是否定位完整 |
| `admission_status` | draft_provisional / reviewed / owner_final / needs_revision / excluded | 训练准入状态 |

允许"语义判断置信度高 + 证据未完整 + 暂不可准入"并存；不得用一个笼统的高/低置信代替三者。

## 3. 准入规则（117 条已机械落桶）

| 桶 | 数量 | 规则 | 是否进入高置信训练集 |
| --- | --- | --- | --- |
| `A_high_confidence` | **41** | 描述可信、结构等价/合理、无失实——保留原始样本+审核记录 | **可以** |
| `C1_conditional_literal` | **26** | 结构等价但参数字面量影响结果——保留差异、关联为同结构条件化参考 | 满足条件字段后可以 |
| `C2_conditional_underdesc` | **29** | 指令欠描述——补全关键条件或作为条件化参考，标注缺失项 | 修复后可议 |
| `M_multiref_candidate` | **14** | 同目标合理替代实现/实质差异——建多参考关系与各自适用条件 | 可以（多参考、不选唯一答案） |
| `Q1_misdescribed` | **5** | 指令失实或与源码矛盾——隔离标记，核实/修正后再议 | **暂不可以** |
| `Q2_insufficient` | **2** | 证据不足/不可判——隔离待审 | **暂不可以** |

**细则**：
- **不得删除** Q1/Q2 桶样本：保留用于错误分析、描述保真度研究与后续人工核验
  （owner 原文明示）。
- `C2` 的"补全"必须是**证据支持的修正**（源码可证），不得由模型生成想象条件；
  修正记录进变更账本（§6）。
- 一个样本可因出现在多个关系中而落入不同桶——**样本级准入取最严桶**（保守原则）。
- 17 条阻断性深查项在核实前按当前标签处理但标 `provisional`（清单见
  `Q2_ADMISSION_V1.json::pending_deep_check_blocking`）。

## 4. 多参考工作流（M 桶）的等价性与适用条件

- 一个任务组可有**多个参考实现**；每个参考必须带：适用条件（数据版本/阈值/时间窗/
  区域/传感器）、来源脚本、判定依据。
- 训练与评估都**不接受"偏离唯一参考答案即判错"**：评估须支持多参考接受（见阶段三
  评估维度"多参考可用性"）。
- 多参考关系的最小证据：同一分析目标 + 必要步骤集合相同或可映射 + 差异可归入
  §2 的标签类（通常是 `substantive` 主标签 + `duplicate/ui/asset` 辅标签）。

## 5. 可追溯关系（raw → normalized → training sample）

每条训练样本必须可回答四问：
1. **原始实现层**：`script_id` + 源码哈希 + 源码路径（本地语料树/服务器路径）+ 行级证据；
2. **规范化表示层**：`gee_canonical_chain`（API 名级）+ `semantic_chain_rle`（30 类粗链）
   + 版本化的抽取器/映射表哈希；
3. **训练样本层**：任务描述 + 监督目标（序列或双层表示）+ 生成该样本的规则版本；
4. **判定层**：Q2 关系/样本级裁定 + adjudicator + 置信度 + evidence_required 状态。

禁止：同一 `script_id` 在不同来源树有不同内容时不做内容级校验就合并（三池事故教训）；
任何 `script_*` 引用必须带内容哈希。

## 6. 数据版本、哈希与变更记录

- **版本号**：`B_TRACK_GOVERNANCE_V1`（本规范）→ 任何准入规则变更升 V1.x，变更必须
  记录：规则 diff、影响的样本数、重跑命令、生效日期。
- **来源哈希**：池文件 `b1_gee_stage_train.jsonl` SHA256；本地语料树以内容哈希为准
  （不以目录名/`script_*` 编号为准）。
- **记录格式**：`GOVERNANCE_CHANGE_LOG_V1.md`（append-only，每次规则变更一条）。
- **流程纪律**：规则演进先 commit 再重跑（吸取 v0.4.1 被覆盖的教训）；重跑输出带
  `rules_version` 字段。

## 7. 状态机（样本级）

```
raw（未判） → adjudicated（agent，provisional）
            → reviewed_maintained（owner 抽查维持/精化）
            → owner_final（owner 亲判）
隔离：Q1_misdescribed / Q2_insufficient → pending_review → corrected|excluded(需记录理由)
```

- `provisional` 记录可用于**研究/审计**，**不得**直接进入高置信训练集；
- 提升为 `reviewed_maintained` 的唯一路径 = owner 抽查（或 owner 明确授权批量转正）。

## 8. 数据集划分治理（阶段三前置，规则现在冻结）

- **任务组级划分**：同一原始脚本、同一任务族的近重复版本、同一来源高度相似工作流
  必须落在同一 split（防近重复泄漏）；
- **多参考组**：同一任务组的全部参考实现同 split；
- **脚本级去重**：同一脚本哈希不得跨 split；
- **test 独立**：独立测试集不参与任何选点/调参；诊断任务（DX-50/PCA）不入训练集
  （既有纪律延续）；
- **记录**：split manifest 带任务组 ID、脚本哈希、关系 ID、生成规则版本。

## 8.1 跨组素材泄漏约束（owner 首轮复核裁定，2026-10-18）

- 以**任务组**为划分单位；共享原始脚本、共享任务实例、仅改字面量的近重复版本必须建立
  **跨组关联约束**（cross-group edge），不得分属训练/评估不同侧；
- 每轮参考集冻结前运行 `B_TRACK_CROSS_GROUP_OVERLAP_V1.json` 检查（按脚本哈希/脚本 ID/
  任务描述近重复）；
- 已登记示例：R18-A 与 R20 共用 `script_74490`/`script_74517`——二者不得在阶段三分属
  训练与验证。

## 9. Q2 归档冻结（阶段一完成标志）

- 冻结对象：`eb58c83`（117 判读完成+加权估计）、`c67e078`（CURRENT_STATE 同步）、
  `d373203`（抽查修订）、`e0f4df1`（抽查收口）——详见
  `Q2_ARCHIVE_FREEZE_INDEX_V1.md`；
- 17 条阻断性深查项保留为 `provisional`，**不强行归类**；
- 117 对**不等于 117 个训练样本**：样本级去重后 221 个唯一样本，关系级 117 条；
  训练集构建以样本级 + 关系级联合索引为准（`Q2_EXTRACT_*`）。

## 10. 阶段一验收清单

- [x] 117 条准入分桶落 `Q2_ADMISSION_V1.json`（含规则文本与证据字段）
- [x] 样本级/关系级提取落 JSON（221 样本 / 117 关系）
- [x] 归档冻结索引（commit + 文件哈希 + 版本关系）
- [x] 17 条阻断深查项单列，其余 8 条非阻断运行核验单列
- [x] 判读层级/置信度/provisional 状态机
- [x] 多参考等价性与适用条件规则
- [x] 可追溯四问 + 版本/哈希/变更记录要求
- [x] 数据集划分治理规则（阶段三前置）
- [ ] 变更账本文件初始化（`GOVERNANCE_CHANGE_LOG_V1.md`，本 commit 创建）
- [ ] 双层表示规范 V1（独立文件 `B_TRACK_TWO_LAYER_REPRESENTATION_SPEC_V1.md`）
- [ ] 可信规划参考集 V0 选样清单（`B_TRACK_TRUSTED_REFERENCE_SET_V0_SCOPING.md`）
