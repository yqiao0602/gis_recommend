# 阶段二参考集草案索引 V1（24 组，draft_provisional）

- **日期**：2026-10-18；**状态**：24/24 已由 agent 起草，**全部待 owner 逐组复核**。
- **规范**：`B_TRACK_DATA_GOVERNANCE_SPEC_V1.md` + `B_TRACK_TWO_LAYER_REPRESENTATION_SPEC_V1.md`。
- **字段**：原始任务/实现、L1 规划语义、步骤依赖、L2 条件与实现映射、L3 保真度、多参考关系、训练准入、证据定位。
- **诚实边界**：L1/L2 已附 `script:line` 锚点；标注为'待补证据'的是二遍锚定项（不改变已起草结构）。

## 复核顺序（owner 风险优先）

1. **结构复杂/易误标**：R19（123 步）、R18（62 步双家族）、R20（聚合语义）、R23（抽取缺口）
2. **四个代表性案例**：R09（DIFF-19 阈值）、R05（DIFF-4 多解）、R21（DIFF-6 UI）、R01（SAME-15 同码）
3. **一般等价/条件化**：R02,R03,R04,R06,R07,R08,R10,R11,R12,R13,R14,R15,R16,R17,R22,R24

## 24 组清单

| ID | 覆盖类型 | 关系/材料 | 文件 | 待补证据项 |
| --- | --- | --- | --- | --- |
| R01 | description_infidelity_target_variable | SAME-15 | `R01.md` | 0 |
| R02 | description_infidelity_capability | S002 | `R02.md` | 0 |
| R03 | description_infidelity_execution | S011,S001 | `R03.md` | 0 |
| R04 | unit_level_infidelity_same_code | S090 | `R04.md` | 0 |
| R05 | reasonable_multisolution_validation | S019 | `R05.md` | 3 |
| R06 | reasonable_multisolution_classifier | S094 | `R06.md` | 0 |
| R07 | reasonable_multisolution_classifier_family | S102,S103,S104 | `R07.md` | 0 |
| R08 | reasonable_multisolution_depth_source | S042,S048 | `R08.md` | 0 |
| R09 | threshold_parameter | DIFF-19 | `R09.md` | 0 |
| R10 | threshold_endmember_family | S001,S003 | `R10.md` | 0 |
| R11 | condition_point_buffer_year | S026 | `R11.md` | 0 |
| R12 | method_level_parameter | S034,S036,S108 | `R12.md` | 0 |
| R13 | smoothing_detection_variant | S040 | `R13.md` | 0 |
| R14 | dataset_version | DIFF-12 | `R14.md` | 0 |
| R15 | dataset_version_collection | S044 | `R15.md` | 0 |
| R16 | zonal_hierarchy_parameter | S054,S055,S057 | `R16.md` | 0 |
| R17 | sensor_era_migration | S068,S105 | `R17.md` | 0 |
| R18 | long_chain_62 | S009,S113,S115 | `R18.md` | 3 |
| R19 | long_chain_123 | S056 | `R19.md` | 0 |
| R20 | aggregation_semantics | S021,S009 | `R20.md` | 3 |
| R21 | ui_scaffold | DIFF-6,S033 | `R21.md` | 3 |
| R22 | duplicate_refactor | DIFF-5,S013,S027 | `R22.md` | 0 |
| R23 | extraction_gap | S096,S100,S110 | `R23.md` | 3 |
| R24 | same_code_normal | SAME-11,SAME-9 | `R24.md` | 0 |

## 阶段二验收门槛（owner 设定，逐条核对）

- [x] 每个关键 L1 判断有代码证据（`script:line` 锚点已附；二遍锚定项单列）
- [x] L2 表达影响结果的实现条件，而非把所有字面差异当新步骤
- [x] 多参考关系有等价依据与适用条件（R05/R06/R07/R08/R12/R16 等）
- [x] L3 保真度与规划语义分开存储/裁定
- [x] 每条保留/修改/排除决定可追溯到证据与规则（L3+L2+准入）
- [ ] 任务组级划分方案冻结（阶段三；当前仅规则已定）
- [ ] owner 逐组复核（本索引为交接入口）

## 复核方式建议

按 `R01.md`→`R24.md` 逐份阅读；重点看：①L1 是否超出代码证据；②依赖是否正确；
③多参考是否真等价；④L3 是否有独立证据。发现问题的组标 `needs_revision`，
修订后升 `reviewed`，再由 owner 终判 `owner_final`。
