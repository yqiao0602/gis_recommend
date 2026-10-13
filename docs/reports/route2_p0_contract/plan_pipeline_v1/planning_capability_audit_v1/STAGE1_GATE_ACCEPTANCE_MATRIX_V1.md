# Stage-1 Gate 验收矩阵 v1（2026-10-13）

> 状态：STAGE1_GATE_ACCEPTANCE_MATRIX_V1 —— 映射文档：owner 六项验收 ↔ 已有证据 ↔
> PCA v1 测量位置 ↔ 前置条件 ↔ 结论边界。
> 执行权威仍是 `PCA_PROTOCOL_V1_FROZEN.md`；本矩阵回答"每项验收现在有什么证据、
> PCA 在哪里测它、通过/不通过各能支持什么结论"。
> 口径裁定见 `STAGE1_GATE_OWNER_RULING_V1.md`。

## 1. 矩阵

| # | owner 验收项 | 已有证据（数字＋产物） | PCA v1 测量位置 | 数据前置 | 通过支持的结论 | 不支持 / 不能外推 |
|---|---|---|---|---|---|---|
| 1 | 未见任务必要步骤召回 | dev-1852 全集 bag-incl .6165 / trusted 1,276 行 .5589（`EVAL_BASELINE_FREEZE_V1`；全集被模板重复＋绑定错误推高，术语裁定=条件基线非统计下限）；BAND_SELECT presence F1 .4465；CAPLOC X4 阶段缺失 47.6%（trusted 口径阶段选择 52.9%，`CAPLOC_PHASE1_RESULTS_V1.md`）；实验 A：presence recall 随流行度单调（BAND_SELECT .472 / ITERATIVE_APPLY .362，`EXP_A_STAGE_SELECTION_RESULTS_V1.md`）；实验 B：强频率先验否定——全家族 recall>prevalence 且 FP<prevalence，模型确实条件化于任务但精度不足 | §4.1 必要步骤召回率（required_steps 语义等价覆盖；alternatives 认可即覆盖）× A/B/C 三组 | Phase 1 金标 owner 逐条审核；任务过 8-gram 去重＋来源级隔离分级（§2.3） | 模型在新任务上能识别必要步骤（按组/域分列） | 不构成对全部任务族的覆盖证明；`text_dedup_only` 行单列披露 |
| 2 | 不必要步骤率 | 同上基线；CAPLOC X5 捏造 42.0%；E2E 实验 A：跨域 66.7% 解析行为通用模板 | §4.1 不必要步骤率（`extra_benign`/`extra_harmful` 分型） | `harmful_examples` 入金标 | 模型不过度堆砌步骤（benign/harmful 分列） | benign≠有用；不在 gold 的合法替代步骤由 alternatives/acceptable_variations 保护，不计为多余 |
| 3 | 顺序与相邻步骤关系 | CAPLOC X7 顺序错误仅 1.0%（域内组合/排序已解决）；ordered LCS 仪器：dev-1852 LCS .5815 / trusted .5181 | §4.1 依赖关系准确率（计划依赖 vs gold dependencies＋计划内顺序矛盾计数）；顺序隐含于 judge 充分性判分 | 金标 dependencies 为人工新撰（裁定 1 第 2 层"可靠推导"分支） | 步骤组织顺序在金标可靠范围内基本合理 | LCS/邻接≠语义依赖正确（owner 警示）；完整依赖验证 = Gate v2 |
| 4 | 依赖（v1 条件性 / v2 补测） | 既有 blueprint gold 无依赖字段（④合同：提不到标 unknown、禁伪造）——Gate v2 立项原因 | v1：§2.6 gold dependencies（人工新撰）；v2：独立标注集另行立项 | Phase 1 金标 owner 审核 | （v1）金标可靠推导范围内的依赖规划证据；（v2）完整依赖能力 | v1 结果不得表述为"完整依赖规划已验证"（裁定 1 措辞上限） |
| 5 | 组合泛化 | 跨域塌缩已实测：E2E Step-1 域内 parse .8445 / 15.9% exact vs dev-120 跨域 parse .65 / 零 perfect（family P .163 / R .140） | §2.1 C 组（复杂/组合型）＋ §2.2 task_type/complexity 分层 ＋ §2.5 语义配对任务（≥6 对）＋ §5.1 Q2 迁移读数三分解（配对内差＋分层组间差＋域内/跨域分解） | 配对任务与分层配平入金标；筛选先于查看预测冻结（§2.4） | （方向性）能力是否随任务类型/表述/域变化的初步证据 | 60 任务=方向性判读非显著性检验（§5.1）；"迁移"措辞须三分解一致方可使用 |
| 6 | 条件变化适应 | 间接：实验 B 证明任务条件化存在但精度不足；blueprint 侧条件语义 gold 修复中（B2-P1：condition_count_suspect 1,411，GEE 五步②③④） | §4.1 条件与约束处理（required_conditions 处理率）——弱形式 | required_conditions 入金标 | 模型对显式条件约束有基本处理 | **成对条件扰动测试（同任务变条件→步骤应增删替换）未入 PCA v1**——登记为 v1.1/后续轴；blueprint 侧条件 gold 经五步④修复前不在 blueprint 侧测条件适应 |
| 7 | 多解人工审查 | MULTISOLUTION 诊断集设计 v0（D1 算子链多解 / D2 粒度等价 / D3 粒度不等价；种子 k=956×k=958 配对，`MULTISOLUTION_DIAGNOSTIC_SET_DESIGN_V0.md`） | §2.6 `alternatives`/`acceptable_variations`/`harmful_examples` ＋ §4.2 争议 `escalated`→owner 仲裁 ＋ 人工复核信度线（sufficiency QWκ ≥0.6 且依赖结构一致率 ≥75%） | 替代方案逐案记录等价性依据 | 合理替代路线不被误判（judge＋人工复核信度为限；模型评分不作独立真值，OQ-7） | D1/D2/D3 三问（构造投入/检索自动化/规模下限）未裁——作为 blueprint 侧口径校准工具独立推进，不阻塞 PCA |

## 2. 条件 B 现有证据（背景引用，不重跑）

E2E 主线（`plan_pipeline_v1/e2e_mainline_v1/`，dev-120 QGIS 域，commits 608d40f3/da2a2333/0c399113）：

- Step 1：P0 蓝图冻结（SHA b401394e）——parse .65、hit_cap .933、78 解析行 98.7%
  missing+extra-mixed、零 perfect、family P .163 / R .140 / LCS .133；
- 实验 A（错误审计）：66.7% 通用模板计划（32.1% 精确 BAND_SELECT→AGGREGATION）、
  family 分布错配（VECTOR_GEOMETRY 3-vs-129 / EXPORT 0-vs-21 / SPATIAL_CLIP 0-vs-20 /
  TERRAIN 0-vs-10）、2 条词表外幻觉、42/120 截断；
- 实验 B（Oracle blueprint grounding）：fixed-table .2897 / lexical b0 .1013 / b1 .1402，
  全部行有选择＋顺序错误；
- Q3 真 E2E 组合：opF1 .0332。
- 判定：owner 决策树双支触发——L1 内容错误 AND L2 grounding 独立不足。

## 3. 缺口登记（不阻塞 PCA Phase 1–4）

1. **外部轴**：GeoAnalystBench 转换可行性验证 → 补充泛化证据（裁定 2，PCA 后立项）；
2. **成对条件扰动测试**：PCA v1.1 候选或后续独立小实验；
3. **依赖 v2 独立标注集**：Gate v2 立项（前置条件/输入输出连接/分支汇合/DAG 合法性）；
4. **MULTISOLUTION D1/D2/D3 三问**：blueprint 侧口径校准工具，独立推进；
5. **A 组 `text_dedup_only` 行隔离证据补强**（可选项，报告中强制披露即可）。
