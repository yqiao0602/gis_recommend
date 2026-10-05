# C 类二次裁决（v1，2026-10-05，CPU-only 分析；基于 Formal SFT 已完成的事实）

> 依据 owner 指令：对 C1/C2 做二次裁决，回答三问；不训练。**事实前提更正**：Formal SFT
> 已于 10-05 03:31 完成（1,041 步，dev 全量已评 E1 0.6636/E2 0.9670/S1 0.8089），GPU 现空闲。

## 裁定一：C1-2（GEE reasoning → QGIS grounding gain）是否需要补实验？

**结论：需要，但分两步；且第一步不需要训练。**

已有证据能回答的部分：

| 子问题 | 已有证据 | 状态 |
|---|---|---|
| C1-0 GEE reasoning 可学？ | Planner-v2：E1 0.6636 / E2 0.9670（GEE 33,339 行 1 epoch） | **已回答 ✓** |
| C1-1 跨平台结构同源？ | Transfer Audit：17 family 共享 / 69.7% 实例可映射 / 首尾模式同构 | **已回答 ✓** |
| C1-2 GEE reasoning 是否提高 QGIS grounding？ | **无任何实验测试过**——历史 Gate 2 测的是 GEE-as-DAPT（负迁移 0.267 vs 0.343），与新架构的"GEE-as-planning-supervision"是不同的监督形式 | **未回答 ✗** |

C1-2 的历史不可替代性核查：
- Gate 2：GEE-as-DAPT（混层）→ 负迁移——**不能回答**新架构问题（监督形式不同）；
- Planner-v2 formal：只在 GEE 任务上评过（blueprint dev）——**从未在 QGIS 任务上测过**；
- C0：QGIS-only——没有 GEE 成分；
- Transfer Audit：结构对比（非模型行为）。

**但 C1-2 存在一个零训练的低成本前置实验**：

> **Zero-shot cross-platform transfer assay**：用 Planner-v2 adapter（GEE 训练，已有
> checkpoint）对 **QGIS 任务文本**（held-out 子样本 ~200-400 行，零训练）直接生成
> semantic stage plan，与 QGIS gold（经 69.7% 映射表转成语义 family）对比 bag-F1
> 与 ordered F1，并对照三个参照：
> ① trivial baseline（modal 语义序列）；② Planner-v2 在 GEE dev 上的 in-domain
> 表现（0.6636）；③ C0 的 QGIS 表现（0.343/0.370，operator 口径）。

**判读树**：
- zero-shot F1 ≫ trivial baseline → GEE reasoning **零样本迁移存在** → A1' 训练实验
  的先验大幅提升，正式因果实验（少量训练）值得做；
- ≈ baseline → 零样本无迁移 → **A1' 训练实验成为唯一判据**（需要训练，defer）；
- < baseline → 负迁移信号 → GEE reasoning 与 QGIS 任务分布冲突，重大设计警示。

**成本**：GPU ~30-60 分钟（生成 200-400 行 + 评分），**零训练**；checkpoint 复用。

**Q1 最终结论**：C1-2 的完整因果论证需要 A1' 训练实验（defer）；但**第一步应先做
零训练的 zero-shot transfer assay**——它决定 A1' 是否值得做、以何种预期做。

## 裁定二：历史 checkpoint 能否复用？

**结论：能，且这正是最小成本路径。**

| checkpoint | 位置 | 在 C1-2 中的角色 | 状态 |
|---|---|---|---|
| **Planner-v2 adapter**（GEE 训练） | `/root/data/stage1_run_planner_v2/stage1_adapter` | zero-shot assay 的生成器 | **✓ 在位** |
| **C0**（QGIS-only 基线） | `/root/gee_llm_smoke/route2_C0/` | 对照基线（op 口径 0.343/0.370） | **✓ 在位**（test-111 预测在案） |
| Planner-v1（P1-B） | `stage1_run_planner_p0/stage1_adapter` | v1 参照（bag 口径） | ✓ 在位（被 P1-B 覆盖后即 P1-B 权重） |

**不需要新建训练**：zero-shot assay 只需生成。若 assay 正面 → A1' 训练实验的设计
（grounding head 形态、数据配比）再议——那才是需要新训练的环节。

## 裁定三：C2（DAG 生成）是论文核心实验还是系统能力验证？

**结论：系统能力验证 + 论文的第二阶段贡献，不是核心 transfer 实验的一部分。**

理由：
1. **核心 transfer 问题（C1）不涉及 DAG**——GEE reasoning 的可迁移性测试
   （zero-shot 或 A1'）都在**语义 stage 序列**层面，DAG 结构是 QGIS 落实层的新维度；
2. **QGIS gold 42.4% branch/merge 只证明"数据中存在 DAG"**——不能证明
   "论文必须额外训练 DAG Planner"；它证明的是 **QGIS gold 的独有监督价值**
   （已被 transfer audit 列为 platform-specific）；
3. **DAG 生成的表示设计未解决**（branch/merge 的序列化方案未定）——在表示未定前
   训练 DAG 生成会重蹈"先设计再证明有用"的覆辙；
4. **正确时机**：C1-2 解决后（无论结果），DAG 生成作为**最终系统的能力扩展**
   进入 Grounding/工程线，与 QGIS operator schema 表（P0-3）衔接。

**C2 定位**：deferred to system-engineering track；论文中作为 discussion/future work
或第二阶段实验（取决于 C1-2 结果与论文篇幅）。

## 裁定后的行动队列

| 优先 | 动作 | 成本 | 前置 |
|---|---|---|---|
| **1** | **Zero-shot transfer assay**（Planner-v2 adapter × QGIS held-out 200-400 行） | GPU 30-60 min，零训练 | 无（checkpoint 在位） |
| 2 | assay 结果 → A1' 实验设计裁定 | CPU | 1 |
| 3 | A1' 训练实验（若 2 放行） | GPU ~10h+ | 2 |
| — | C2 DAG 生成 | — | deferred to system track |
| — | P0-3 Registry 审计 | CPU + QGIS 文档获取 | 可与 1 并行 |

## 状态

- Formal SFT：**已完成**（03:31）；dev 全量已评；GPU 空闲。
- 本裁决不涉及任何训练/冻结物变更。
- **待 owner 放行**：zero-shot transfer assay（GPU 30-60 min）。
