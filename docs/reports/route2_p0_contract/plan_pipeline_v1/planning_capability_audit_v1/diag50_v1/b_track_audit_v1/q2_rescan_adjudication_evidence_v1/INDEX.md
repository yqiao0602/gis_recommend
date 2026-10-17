# Q2 池级复核判读证据包索引 V1（117 卷宗）

- 每卷宗 = 指令全文 × 双侧源码全文 × 统一 diff × 机械 flags × 保真度提名 × 七字段判读栏。
- 七字段 schema 与三防误判守则按 owner 2026-10-17 前置审查登记（见 `Q2_POOL_RESCAN_RULING_OWNER_V1.md`）。

## 分层统计口径（owner 锁定）

估计池级占比须按分层加权：p̂ = Σ_h (N_h/N)·p̂_h（N_h=机械类层总体，n_h=该层抽样数）；
置信区间按分层抽样设计；证据不足/不可判/缺失样本处理规则单列；十对源码级已知证据
保留为既有证据但不计入概率抽样比例；**机械漏检（机械层不可见的任务差异）需另设
审计样本**，本包不能估计其发生率。

| 层（bucket/类） | 层总体 N_h | 抽样 n_h |
| --- | --- | --- |
| diff/asset_version_candidate | 25 | 12 |
| diff/duplicate_block_candidate | 27 | 12 |
| diff/reorder_refactor_candidate | 5 | 5 |
| diff/small_literal_cosmetic_candidate | 167 | 12 |
| diff/substantive_structural_candidate | 111 | 12 |
| diff/template_multiplicity_artifact | 4 | 4 |
| diff/ui_scaffold_candidate | 40 | 12 |
| same/formatting_only | 44 | 12 |
| same/same_code_two_descriptions | 716 | 12 |
| same/same_template_canonical_diff | 232 | 12 |
| same/same_template_literal_diff | 3144 | 12 |

## owner 审查优先序（登记）

1. **S058–S069**（第一优先：脚手架/重复节点/操作语义差异；S059/S061-S063 重点；
   S060/S064-S066 依赖链；S068/S069 数据流；S058/S067 相似度污染）
2. **S051–S057**（第二：操作多重集/参数/数据来源；S052/S053/S056 重点）
3. **S070–S117**（第三：先批量分类再复核例外；S078 数据集缺失、S106 Landsat 7/5、
   S110/S112 数据集参数）
4. **S001–S050 中的 owner 点名**: S039/S042/S043/S026（高优先）+ S001/S002/S025/S027/S028

## 三防误判守则（owner）

1. 重复块不必然无害——须查数据依赖与输出使用；
2. 字面量变化不必然表面——数据集/阈值/波段/日期可决定结果；
3. 同码双描述≠指令失实——须独立核对代码与指令对应关系；
结构相似/代码相同/任务等价不得混为一个标签。

## 已知十对的处置

源码级已核验十对（V3 四对 + V2-P0 六对）保留为既有证据；落入本样本即注明沿用。
