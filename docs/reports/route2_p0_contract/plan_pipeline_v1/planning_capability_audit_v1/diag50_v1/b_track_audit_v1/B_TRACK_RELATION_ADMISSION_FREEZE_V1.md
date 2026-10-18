# 阶段三基线：关系与准入冻结清单 V1（28 条）

- **版本**：`B_TRACK_RELATION_ADMISSION_FREEZE_V1`；**基线 commit**：`9a418d1`；**日期**：2026-10-18。
- **冻结范围**：关系三分字段、三状态字段、owner 裁定、open evidence。
- **规则**：不新增无条件多参考准入；变更走变更账本并重检划分约束；外部证据未闭合不改变冻结状态但限制结论扩张。

| ID | 关系（结构/同构/多参考） | 证据 | 准入 | open evidence |
| --- | --- | --- | --- | --- |
| R01 | 结构 | partial | B_candidate_A_excluded | — |
| R02 | — | partial | A_C2_B_Q1 | — |
| R03 | 结构,同构 | complete | 54184_excluded_others_conditional | — |
| R04 | 结构 | partial | A_Q1_B_conditional | — |
| R05 | 结构,同构 | complete | draft_provisional | — |
| R06 | 结构,同构 | partial | draft_provisional | — |
| R07 | 结构,同构 | partial | draft_provisional | — |
| R08 | 同构 | partial | draft_provisional | — |
| R09 | 结构,同构 | complete | B_conditional_A_no_fidelity_supervision | — |
| R10 | 结构,同构 | complete | 54184_excluded_others_conditional | — |
| R11 | 结构,同构 | complete | conditional_instance | — |
| R12 | 结构,同构 | partial | draft_provisional | — |
| R13 | 结构,同构 | complete | draft_provisional | — |
| R14 | 结构,同构 | partial | draft_provisional | — |
| R15 | 结构,同构 | complete | draft_provisional | — |
| R16 | 结构,同构 | partial | draft_provisional | — |
| R17S068 | 结构,同构 | complete | draft_provisional | — |
| R17S105 | 结构,同构 | complete | draft_provisional | — |
| R19 | 结构,同构 | complete_scoped | conditional_applies_when_pending | maskClouds 函数体逐行; 清单逐项差异 |
| R20 | 结构,同构 | complete | draft_provisional | 温度多参考尺度规则待任务定义 |
| R21 | 结构,同构 | complete | core_reference_ui_non_analytical | cc_undefined_reference_in_45675 |
| R22DIFF5 | 结构 | partial | draft_provisional | — |
| R22S013 | 结构,同构 | partial | draft_provisional | — |
| R22S027 | — | partial | draft_provisional | — |
| R23 | — | partial | excluded_planning_supervision | entrenamiento 构造细节; S100 分支特征集差异已核实 |
| R24 | 结构,同构 | partial | draft_provisional | eutrophication var a = feature index 8 vs 33 (different analysis object) |
| R18A | 结构,同构 | partial | draft_provisional | 四导出块与场景映射 |
| R18B | 结构,同构 | partial | draft_provisional | tlist/a/feat 来源; geometry 外部来源; 统计区域几何一致性; 图表/导出锚点 |

## 冻结说明

- `multiref_of` 在全部 28 条中**均为空**：无任何组获得无条件多参考准入；
- 同构模板、条件化参考、同码对照、非分析性 UI、重复噪声五类对象严格分开；
- 外部证据五项：R03/R10 口径漂移、R04 WorldPop 单位、R21 `cc` 缺陷、R24 `table` 来源、R16 `Feature Index`。
