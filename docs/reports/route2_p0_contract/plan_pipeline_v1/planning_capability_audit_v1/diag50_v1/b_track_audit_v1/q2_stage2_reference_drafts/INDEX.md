# 阶段二参考集草案索引 V6（29 条，全部完成 owner 复核）

- **日期**：2026-10-18；R01–R24 全部完成复核（R17/R18/R22 已拆分）。
- **状态**：全部 `draft_provisional` 或特定关系状态；**没有一条获得无条件多参考准入**。
- **五项治理对象严格分开**：同构规划 / 条件化参考 / 同码描述对照 / 非分析性 UI / 重复代码噪声。

## 全量表

| ID | 覆盖/关系 | 语义置信 | 证据 | 准入 | owner 结论 |
| --- | --- | --- | --- | --- | --- |
| R01 | 结构等价 | 高 | partial | B_candidate_A_excluded | pass |
| R02 | description_infidelity_capability | 高 | partial | A_C2_B_Q1 | conditional_pass |
| R03 | 结构等价, 同构模板 | 高 | complete | 54184_excluded_others_conditional | pass_with_caliber_review |
| R04 | 结构等价 | 高 | partial | A_Q1_B_conditional | not_fully_pass |
| R05 | 结构等价, 同构模板 | 高 | complete | draft_provisional | multiref_deferred |
| R06 | 结构等价, 同构模板 | 高 | partial | draft_provisional | modified_pass |
| R07 | 结构等价, 同构模板 | 高 | partial | draft_provisional | modified_pass_split_subrelations |
| R08 | 同构模板 | 高 | partial | draft_provisional | split_recheck |
| R09 | 结构等价, 同构模板 | 高 | complete | B_conditional_A_no_fidelity_supervision | modified_pass |
| R10 | 结构等价, 同构模板 | 高 | complete | 54184_excluded_others_conditional | modified_pass |
| R11 | 结构等价, 同构模板 | 高 | complete | conditional_instance | pass |
| R12 | 结构等价, 同构模板 | 高 | partial | draft_provisional | modified_pass |
| R13 | 结构等价, 同构模板 | 高 | complete | draft_provisional | modified_pass |
| R14 | 结构等价, 同构模板 | 高 | partial | draft_provisional | modified_pass |
| R15 | 结构等价, 同构模板 | 高 | complete | draft_provisional | modified_pass |
| R16 | 结构等价, 同构模板 | 高 | partial | draft_provisional | modified_pass |
| R17S068 | 结构等价, 同构模板 | 高 | complete | draft_provisional | modified_pass_split |
| R17S105 | 结构等价, 同构模板 | 高 | complete | draft_provisional | modified_pass_split |
| R19 | 结构等价, 同构模板 | 高 | complete_scoped | conditional_applies_when_pending | — |
| R20 | 结构等价, 同构模板 | 高 | complete | draft_provisional | — |
| R21 | 结构等价, 同构模板 | 高 | complete | core_reference_ui_non_analytical | modified_pass |
| R22DIFF5 | 结构等价 | 高 | partial | draft_provisional | conditional_equivalence |
| R22S013 | 结构等价, 同构模板 | 高 | partial | draft_provisional | isomorphic_template |
| R22S027 | code_reorder_algal | 高 | partial | draft_provisional | dependent_equivalence_pending |
| R23 | extraction_gap | 高 | partial | excluded_planning_supervision | — |
| R24 | 结构等价, 同构模板 | 高 | partial | draft_provisional | modified_pass |
| R18A | 结构等价, 同构模板 | 高 | partial | draft_provisional | — |
| R18B | 结构等价, 同构模板 | 高 | partial | draft_provisional | — |

## 待外部证据（不阻塞关系冻结）

1. R03/R10 保真度口径漂移（同脚本同描述判欠描述/失实）——待 owner 裁定；
2. R04 WorldPop 2020 像元值单位定义；
3. R21 B 的 `cc` 未定义缺陷需修复/标注；
4. R24 优营养化 `table` 外部来源；
5. R16 `Feature Index` 语义。

## 阶段三入口（按 owner 规则）

1. 冻结关系标签与准入状态；2. 全量脚本重叠扫描并合并连通分量；3. 任务组级划分；4. A/B/C 对照设计。
