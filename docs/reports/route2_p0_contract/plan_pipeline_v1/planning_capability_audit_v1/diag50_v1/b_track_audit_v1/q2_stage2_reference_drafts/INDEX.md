# 阶段二参考集草案索引 V4（25 条）

- **日期**：2026-10-18；**状态**：R01–R11 owner 第三轮复核完成；R12–R17/R21/R22/R24 待复核。
- **统一裁定原则**：关系≠准入；多参考条件一致性硬门槛；证据完整≠语义置信。

## R01–R11 复核结果

| ID | 关系 | 证据 | 准入 | owner 结论 |
| --- | --- | --- | --- | --- |
| R01 | structural_equivalence | partial | B_candidate_A_excluded | pass |
| R02 | — | partial | A_C2_B_Q1 | conditional_pass |
| R03 | structural_equivalence,isomorphic_template_of | complete | 54184_excluded_others_conditional | pass_with_caliber_review |
| R04 | structural_equivalence | partial | A_Q1_B_conditional | not_fully_pass |
| R05 | structural_equivalence,isomorphic_template_of | complete | draft_provisional | multiref_deferred |
| R06 | structural_equivalence,isomorphic_template_of | partial | draft_provisional | modified_pass |
| R07 | structural_equivalence,isomorphic_template_of | partial | draft_provisional | modified_pass_split_subrelations |
| R08 | isomorphic_template_of | partial | draft_provisional | split_recheck |
| R09 | structural_equivalence,isomorphic_template_of | complete | B_conditional_A_no_fidelity_supervision | modified_pass |
| R10 | structural_equivalence,isomorphic_template_of | complete | 54184_excluded_others_conditional | modified_pass |
| R11 | structural_equivalence,isomorphic_template_of | complete | conditional_instance | pass |

## 两项待 owner 裁定

1. **R03/R10 口径漂移**：S001-A 与 S011-A 同脚本、**任务描述文本完全相同**，却分别判欠描述/失实；需确认是否统一口径。
2. **R04 B 单位语义**：`persons/ha` 依赖 WorldPop 2020 像元值定义（外部证据未补），B 暂不升级。

## 下一批待复核（9 条）

- R12（棉花 IWR 方法级差异）、R13（草地刈割平滑级）、R14（L7 C1→C2）、R15（MapBiomas C5→C6）、R16（RUSLE 分区层级）、R17（传感器年代）
- R21（UI 脚手架）、R22（重复块/重构）、R24（同码对照）

## 阶段三规则（已冻结）

- 关系≠准入；条件一致性=多参考硬门槛；按脚本重叠连通分量划分（R03+R10、R18A+R20）。
