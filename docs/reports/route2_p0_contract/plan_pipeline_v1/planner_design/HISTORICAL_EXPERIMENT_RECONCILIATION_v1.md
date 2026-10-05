# Historical Experiment Reconciliation（历史实验对账）v1（2026-10-05，CPU-only）

> 依据 owner 指令：把全部历史实验映射到两层架构（General GIS Reasoning / QGIS
> Grounding），区分 **A 已回答** / **B 有数据待重析** / **C 真缺口**；只对 C 补最小实验。
> 全部结论基于仓库内真实实验文档与数据（溯源见各项标注）。

## 1. 对账矩阵（按真实实验数据填充）

| 数据/实验 | GIS Reasoning | Grounding: selection | Grounding: generation control | Grounding: DAG structure | Grounding: hint binding | Registry coverage |
|---|---|---|---|---|---|---|
| **GEE 128k**（Gate 0/1） | ✓ Gate0 结构有效 94.56% / Gate1 信号 MIDDLE | - | - | **✗ 线性不可表达** | - | - |
| **Gate 2 三臂（C0/A1 DAPT）** | **✗ 负迁移**（A1 op e2e 0.267 vs C0 0.343，CI<0） | ✓ C0 op e2e **0.343**（test-111） | ✓ C0 控制脆弱（FA：EOS −14.7pp / 注入 ×3.9） | **✗ 未测** | **✗ 未测** | ✗ 未测 |
| **A1 机制结论**（09-24 冻结） | 设计原则 3：**GEE = workflow composition supervision**（两层架构雏形，已冻结） | ✓ D1① teacher-forced 78.8% = C0（选择能力保留） | ✓ 机制冻结：知识完好、控制失效 | - | - | - |
| **M3**（L3 时代） | 旧架构（**L3 已取消**） | - | ✓ **83.7%** 序列输出可学（EOS-aware） | ✗ 线性 | ✗ L3 无 hint | ✗ L3 粒度 |
| **Planner-v1**（P0/P1-B） | ✓ bag-F1 0.645/0.672 | - | - | ✗ bag 无序 | - | - |
| **Planner-v2 formal** | ✓ **E1 0.6636 / E2 0.9670** | - | 部分（S1 0.809） | **✗ 线性 stages** | **✗ S5 per_band 0/9** | **✗ 309 only** |
| **QGIS Gold 1,565** | ？（未单独验证 reasoning 价值） | ✓ **gold 结构完整**（309 ops、0 悬空） | - | ✓ **42.4% branch/merge** | - | **25.8% coverage** |
| **QGIS Registry ≈1,200** | - | ?（**未建**） | - | - | - | **本体待审计** |
| **C0R / Phase R** | - | ✓ 训练管线验证 | ✗ evaluator OOM（未测） | - | - | - |
| **Oracle Grounding**（历史） | - | ✓（历史基线） | - | - | - | - |

## 2. A 类：已回答，不重做

| # | 问题 | 答案 | 来源 |
|---|---|---|---|
| A1 | GEE 泛型 DAPT → QGIS 是否有效？ | **无效（负迁移 0.267 vs 0.343）**，永不以 DAPT 形式重做 | Gate 2（冻结） |
| A2 | A1 失败机制？ | 知识完好（D1① 选择保留）、自由生成控制失效（D1②）；decode 期补丁不可救 | FA/DC（冻结） |
| A3 | GEE 的正确角色？ | **workflow composition supervision**（非 DAPT）——两层架构在 09-24 已由设计原则 3 预写 | A1 机制结论 §4.3 |
| A4 | v2 结构表示可学？ | **可学**（E1 0.664 / E2 0.967 / S1 0.809） | Planner-v2 formal |
| A5 | QGIS gold 结构价值？ | **42.4% branch/merge + 0 悬空 + 309 ops**（GEE 线性目标无法提供的监督） | v2a expressivity audit |
| A6 | 17-family 词汇共享？ | ✓（QGIS 69.7% 实例可映射到 GEE 语义词汇） | Transfer audit |

## 3. B 类：有数据，需按新口径重析（不重训）

| # | 既有数据 | 重析内容 |
|---|---|---|
| B1 | **C0 checkpoint（route2_C0）+ test-111 预测**（op e2e 0.343/0.370 是聚合口径） | 用新 E1-E4 口径**分解**：C0 的 ordered-stage F1 / repetition presence / 各 family 表现——零训练，纯重评 |
| B2 | FA 的 D1① teacher-forced 78.8% | 新架构下重解读为 **"planning selection 能力在 QGIS 侧已存在"** 的证据 |
| B3 | M3 83.7% 序列输出 | 旧口径（L3 已取消），保留为"结构化序列可学"的历史佐证 |
| B4 | Planner-v1 P0/P1-B 的 bag-F1 | 统一对比管线就绪后与 v2 并排（owner 已裁定后置） |

## 4. C 类：真缺口（从未被隔离实验过）

| # | 缺口 | 为何历史实验没覆盖 | 最小实验 |
|---|---|---|---|
| **C1** | **GEE-as-planning-supervision → QGIS Grounding 的迁移**（新架构的核心 assay） | 历史 Gate 2 测的是 GEE-as-DAPT（负迁移）；新架构预测：当 GEE 监督以结构化规划形式（Planner-v1/v2 已证可学）+ QGIS grounding head 组合时，迁移应为正/中性——**从未测过** | Planner-v2 adapter（GEE 训练）+ QGIS grounding head vs C0（QGIS-only）——最小对照 |
| **C2** | **DAG 结构生成**（branch/merge） | 所有历史 Planner 目标均为线性序列；QGIS gold 42.4% DAG 从未作为训练目标 | QGIS gold 直训（含 DAG 目标）后测 branch/merge 生成 |
| **C3** | Hint 绑定监督（S5） | Planner-v2 目标无绑定监督 | 已裁定 P2 前置（Blueprint v2 方向） |
| **C4** | Registry 级 Grounding（L2 unseen operators） | 所有历史实验仅用 gold-covered 309 算子 | P0-3 Registry 审计后设计 |

## 5. 结论与建议

1. **最重要的对账发现**：**A1 机制结论的设计原则 3（09-24 冻结）已经预写了今天的两层架构**——"GEE 不是 DAPT 数据源，其合理位置 = 结构/workflow composition supervision"。今天的 Transfer Audit（69.7% 词汇共享 + 42.7% DAG 新增）为该原则提供了定量数据支撑。**路线在概念上是一致的，缺的只是 C1/C2 两个从未隔离的实验。**
2. **Gate 2 的负迁移教训在新架构下自动解释**：旧 A1 混层（GEE DAPT 直接优化 QGIS decoder）→ 控制失效；新架构分层（GEE 教组合规划 / QGIS 教落地）→ 预测无此失效模式。**这解释了"为什么 A1 失败但 Planner-v2 成功"——不是数据问题，是监督形式问题。**
3. **最小实验建议（仅 C1，待 owner 放行）**：Planner-v2 adapter（GEE 训练）+ QGIS grounding head vs C0（QGIS-only）——但需先完成 B1（C0 重评）确定 C0 基线的新口径数字。
4. C2（DAG 生成）依赖 Planner-v3 的 processes+links 目标定义（owner 已定方向）；C3 已裁定 P2 前置；C4 依赖 P0-3 Registry 审计。
5. **当前状态**：Formal SFT 正常运行中（不受影响）；locked test 未动；零冻结物变更。
