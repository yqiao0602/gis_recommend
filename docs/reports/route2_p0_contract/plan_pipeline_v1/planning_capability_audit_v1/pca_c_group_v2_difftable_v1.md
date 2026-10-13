# PCA C 组 v2 + 配对 v2 定点修订差异表 v1（owner round-14 要求格式，2026-10-13）

> 覆盖对象：C 组任务金标 v1（`18aace83…`）→ v2（`92c5fdfd79694327`，22 条差异记录于
> `pca_c_group_tasks_gold_v2_diffs.json`）；配对 v1（`5223971d…`）→ v2（`48572738236c8a62`）。
> 差异表字段：任务 ID / 原规则 / 修订后规则 / 题面依据 / 对评分代码的影响。

## 一、F1 金标内部一致性（8 条 P0）

| 任务 | 原规则 | 修订后规则 | 题面依据 | 评分代码影响 |
|---|---|---|---|---|
| C-01 | 质心采样=无条件等价 | 总量分配直估；质心降为**条件代理路线**（须声明面积假设） | 建筑人口是总量，质心密度≠总量 | 代理路线按"声明假设"评分；缺声明=缺陷 |
| C-03 | 失败条件"No downstream ordering"可能被读为特定算法 | 失败谓词=**标识符存在性**（算法自由）；cell/type 独立性加 `cell_note` | 任务要的是标识符非算法 | 失败检查=标识符存在，无算法匹配 |
| C-05 | "Continents undefined/missing"=失败 | 洲界=命名来源**或声明数据需求**；缺输出且缺声明才失败 | 题面未提供也未要求获取洲界 | 双条件失败检查（缺输出 AND 缺声明） |
| C-09 | 原始编码无映射=失败 | 原始编码接受；名称映射降为可选展示 | 题面只要 class 值 | 映射存在与否不评分 |
| C-13 | "Attribute rule ignored"强制用未提供阈值 | **apply-or-declare**：应用已提供阈值或声明阈值缺失均通过 | "e.g., area below a minimum"是示例非供给 | 失败谓词=既不应用也不声明 |
| C-14 | 同上（tier 阈值） | 同 apply-or-declare | 题面无阈值数值 | 同上 |
| C-17 | （无失败项冲突但欠三值） | 加 audit_note：模型可显式声明基准/月份/统计量，按**声明假设**评分；硬项仅差值结构/排序/强度栅格 | 三值题面均未定 | judge 评声明存在性，不比对特定基准 |
| C-19 | "Threshold undefined and arbitrary"=失败 | 只罚"应用阈值却无依据/未声明假设" | 阈值 selectable 设计 | 失败谓词=依据缺失，非数值不符 |

## 二、F2 "stated"参数口径统一（全部 20 行）

- **题面措辞修订**（9 条）：C-05/08/10/13/14/15/16/18/20 的 "a stated X" → "**an X you state explicitly**"（C-16 "own stated radius"→"assign and declare your own radius"；C-05 洲界→"naming the source you use or declaring it as required external input"）。
- **机械字段 `parameter_availability`** 落全部 20 行（值域：selectable / selectable_with_declaration / selectable_with_suitability_statement），逐参数标注（如 C-08: slope_threshold=selectable, buffer_width=selectable；C-05: continent_boundary_source=selectable_with_declaration）。
- **评分代码影响**：一律检查**声明**（是否给出并声明选择），永不检查"猜中某值"。
- 设计说明：C 组未冻结，题面文本修订合规；每条记录于 `pca_c_group_tasks_gold_v2_diffs.json`。

## 三、F3 单项修正

| 任务 | 修订 |
|---|---|
| C-06 | alternatives 要求 CRS 选择**附长度变形适用性说明**（equal-area 扭曲长度）——缺说明=声明缺陷非整计划失败 |
| C-10 | 阈值 apply-or-declare（同 F1 模式）；密度需真实面积保留为合理语义约束 |
| C-12 | "合计 100%"改为"**有效土地覆盖像元**上 ~100% 且声明排除"（NoData/边界/未分类合法减少总数；朴素全像元 100% 非必需） |
| C-16 | 多匹配注记规则确认保持欠定义（无需改动，审计确认） |
| C-18 | 条件约束改为"按 DEM 状态**按需**条件化；不强制特定预处理算子" |

## 四、配对 v2

| 对 | 处置（round-14） |
|---|---|
| P01–P04 | conditional_keep（逐项难度不对称已在 difficulty_check 披露；P04 的"训练 vs 统计不是同一能力"风险在联合终审中重点复核） |
| P05 | **exploratory_re-evaluate**：核心推理结构不同（分类+时间验证 vs 变化编码+面积核算）；允许寻找更近 A/C 对，否则单独报告 |
| P06 | **structural_exploratory**：排除出主配对汇总；审计记录保留（结构相似≠共同目标——owner 方法学原则落实） |
| 难度编码 | 四维各映射有序等级 0/1/2（自冻结描述符机械生成；编码规则入文件）——**维度不加总**，仅做 profile 对比；显式约束覆盖度保持独立分层 |

## 五、Stage-4 机械检查映射（五项 → 已就绪的检查对象）

| # | 检查 | 检查对象 |
|---|------|----------|
| 1 | Schema/评分映射一致 | A/C 金标同 schema + parameter_availability 字段消费规则 |
| 2 | 硬约束有题面证据 | [EXPLICIT] 行逐条可溯源（审 point：C 组题面刚修订，[EXPLICIT] 全部基于 v2 题面） |
| 3 | 展示独立计分 | presentation_requirements 字段与核心链分离（task-stated 标记） |
| 4 | 证据来源合法 + 欠定义不误罚 | evidence_source ∈ {task_text, gold_constraint, model_output}；apply-or-declare 谓词 |
| 5 | 配对/分层可机械复现 | status 字段（P05/P06 已编码）+ 难度有序 profile + parameter_availability + eligibility_status |
