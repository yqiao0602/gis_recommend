# 阶段二参考集草案索引 V2（24 组 → 25 条：R18 已拆分）

- **日期**：2026-10-18；**状态**：owner 首轮复核后修订版。
- **修订组**：R19 / R18A / R18B / R20 / R23 → `revised_pending_owner_review`；其余保持 `draft_provisional`。
- **三条统一口径**（治理规范 §2.1/§2.2/§8.1）：结构等价/同构模板/多参考三分；语义置信度/证据完整性/准入状态三分离；跨组素材泄漏约束。
- **跨组重叠**：`B_TRACK_CROSS_GROUP_OVERLAP_V1.md/.json`（2 条边：R03↔R10、R18A↔R20）。

## 复核顺序

1. 已修订待复核：**R19 → R18A → R18B → R20 → R23**
2. 四个代表案例：R09 → R05 → R21 → R01
3. 其余：R02,R03,R04,R06,R07,R08,R10,R11,R12,R13,R14,R15,R16,R17,R22,R24

## 清单

| ID | 覆盖类型 | 关系 | 文件 | 语义置信 | 证据完整 | 准入状态 | 跨组重叠 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| R01 | description_infidelity_target_variable | SAME-15 | `R01.md` | 高 | complete | draft_provisional | — |
| R02 | description_infidelity_capability | S002 | `R02.md` | 高 | complete | draft_provisional | — |
| R03 | description_infidelity_execution | S011,S001 | `R03.md` | 高 | complete | draft_provisional | R03/R10 |
| R04 | unit_level_infidelity_same_code | S090 | `R04.md` | 高 | complete | draft_provisional | — |
| R05 | reasonable_multisolution_validation | S019 | `R05.md` | 高 | partial | draft_provisional | — |
| R06 | reasonable_multisolution_classifier | S094 | `R06.md` | 高 | complete | draft_provisional | — |
| R07 | reasonable_multisolution_classifier_family | S102,S103,S104 | `R07.md` | 高 | complete | draft_provisional | — |
| R08 | reasonable_multisolution_depth_source | S042,S048 | `R08.md` | 高 | complete | draft_provisional | — |
| R09 | threshold_parameter | DIFF-19 | `R09.md` | 高 | complete | draft_provisional | — |
| R10 | threshold_endmember_family | S001,S003 | `R10.md` | 高 | complete | draft_provisional | R03/R10 |
| R11 | condition_point_buffer_year | S026 | `R11.md` | 高 | complete | draft_provisional | — |
| R12 | method_level_parameter | S034,S036,S108 | `R12.md` | 高 | complete | draft_provisional | — |
| R13 | smoothing_detection_variant | S040 | `R13.md` | 高 | complete | draft_provisional | — |
| R14 | dataset_version | DIFF-12 | `R14.md` | 高 | complete | draft_provisional | — |
| R15 | dataset_version_collection | S044 | `R15.md` | 高 | complete | draft_provisional | — |
| R16 | zonal_hierarchy_parameter | S054,S055,S057 | `R16.md` | 高 | complete | draft_provisional | — |
| R17 | sensor_era_migration | S068,S105 | `R17.md` | 高 | complete | draft_provisional | — |
| R19 | long_chain_123 | S056 | `R19.md` | 高 | complete | conditional | — |
| R20 | aggregation_semantics | S021,S009 | `R20.md` | 高 | complete | draft_provisional | R18A/R20 |
| R21 | ui_scaffold | DIFF-6,S033 | `R21.md` | 高 | partial | draft_provisional | — |
| R22 | duplicate_refactor | DIFF-5,S013,S027 | `R22.md` | 高 | complete | draft_provisional | — |
| R23 | extraction_gap | S096,S100,S110 | `R23.md` | 高 | complete | excluded_planning_supervision | — |
| R24 | same_code_normal | SAME-11,SAME-9 | `R24.md` | 高 | complete | draft_provisional | — |
| R18A | isomorphic_template_crop_yield | S009 | `R18A.md` | 高 | partial | draft_provisional | R18A/R20 |
| R18B | candidate_multiref_eutrophication | S113,S115 | `R18B.md` | 高 | complete | draft_provisional | — |

## 验收门槛（更新）

- [x] 三条统一口径落规范（§2.1/§2.2/§8.1）
- [x] 四组（+拆分）修订：证据补链/术语修正/准入分离
- [x] 跨组重叠登记（脚本级全扫）
- [ ] owner 复核修订版五组
- [ ] 其余 19 条按同一口径复核
- [ ] 阶段三：任务组级划分冻结 + 三组对照设计
