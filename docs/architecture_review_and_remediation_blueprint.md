# 系统架构审查与修复蓝图（Architecture Review & Remediation Blueprint）

> 本文档分两部分：
> **第一部分** 是基于 Runtime Truth 的架构审查（已验证的问题 + 证据 + 证据等级）。
> **第二部分** 是架构修复蓝图（按"修复轨道"组织的演化方案，非代码补丁清单）。
>
> **方法纪律**：本文档**不以** `MEMORY.md` / `PROJECT_CONTEXT.md` / 注释 / 版本命名作为结论依据。每条结论标注**证据来源**与**证据等级**：
> - **A** = 代码与运行路径直接验证
> - **B** = 多模块间接验证
> - **C** = 文档推断
> - **D** = 猜测
>
> 证据优先级：运行行为 > 实际调用关系 > 数据流 > 代码结构 > 文档描述。
> 文档只用于"该去验证什么"，不用于"事实是什么"。

---

## 目录

- [第一部分：架构审查](#第一部分架构审查基于-runtime-truth)
  - [〇、实测运行时真相图](#〇实测运行时真相图与设计意图的首层背离)
  - [问题一：分层体系 L1→L2→L3 在运行时不参与计算](#问题一分层体系-l1l2l3-在运行时生成路径中不参与任何计算)
  - [问题二：声明身份与运行时身份系统性背离](#问题二系统声明身份与运行时身份系统性背离)
  - [问题三：评测目标位移](#问题三评测目标位移)
  - [问题四：系统身份碎片化](#问题四系统身份碎片化)
  - [问题五：配置无耦合校验 + 静默回退](#问题五配置无耦合校验--静默回退)
  - [问题六：evidence/ 治理模块孤立](#问题六evidence-治理模块建成不接线测试断言永不接线)
  - [问题七：治理/可观测性元工程过度增长](#问题七治理可观测性元工程过度增长)
  - [问题八：基础设施重复 + Neo4j 单点 + 全局可变状态](#问题八基础设施重复发散--neo4j-单点强耦合--全局可变状态注入)
  - [问题九：数据层级泄漏与监督歧义](#问题九数据层级泄漏与监督歧义核心能力天花板的真实根因)
  - [十、跨维度根因诊断](#十跨维度根因诊断meta)
  - [十一、需要进一步验证的问题](#十一需要进一步验证的问题证据不足)
- [第二部分：架构修复蓝图](#第二部分架构修复蓝图architecture-evolution-blueprint)
  - [组织说明 + 问题→轨道映射](#组织说明按修复轨道而非逐题编排)
  - [T1 运行时单一事实源 + 一致性契约](#t1运行时单一事实源--一致性契约)
  - [T2 概念架构 vs 计算架构对齐](#t2概念架构-vs-计算架构对齐含一个必须的决断闸门)
  - [T3 度量效度修复](#t3度量效度修复)
  - [T4 死代码与元工程治理](#t4死代码与元工程治理)
  - [T5 外部依赖解耦 + 全局状态消除](#t5外部依赖解耦--全局状态消除)
  - [T6 数据级瓶颈](#t6数据级瓶颈内容级去重--长尾)
  - [七、跨轨道演化总排序](#七跨轨道演化总排序与共同基础设施)

---

# 第一部分：架构审查（基于 Runtime Truth）

## 〇、实测运行时真相图（与设计意图的首层背离）

**主线入口 `gis-evaluate`（`evaluation/runner.py:main`）的真实默认调用链**（证据等级 A，已逐行读 `runner.py` / `reranker_pipeline.py` / `infer_l3_candidates_v4.py` / `transformer_model_v4.py` / `config`）：

```
build_test_set(test_indices from dataset_splits_v4.json)          # 持出测试集，索引级无泄漏
  → run_l3_inference → L3SequenceInferencerV4(V4.6/best_model.pth) # 默认 V4.6
      → diverse_beam_search + soft set-prior(+0.5 bias, p>0.70)    # 默认 soft
  → SemanticMetricsCalculator.compute (set_f1/lcs/l2_set_f1...)    # L2 仅作"指标"
  [可选 --use-reranker] → 改写 pred_tokens                          # 默认关
  [可选 --use-repair]   → 仅写 repair_suggested，repair_applied=False # 永不落地
  [可选 --retrieval-shadow-k] → 仅挂 retrieval_shadow_pool          # decision_core_mode="shadow"，从不参与选择
  [可选 不 --skip-qgis] → 连 Neo4j 做链校验                          # 强耦合 live DB
```

由此立即得到三条与"设计意图"冲突的硬事实：

- **运行时默认 = V4.6 beam 生成 + soft set-prior**。`reranker / repair / retrieval / planning` 要么是 opt-in、要么 report-only。
- **`PROJECT_CONTEXT` 自述系统身份是"retrieval-centered / execution-aware / rerank-driven / constrained-planning"**（`docs/v5_system_consolidation_protocol.md` 摘要），但该身份在主线运行时**不成立**。文档本身在 Current Data Truth 第 60 行也承认 "mainline still selects from V4.6 beam outputs and does not call the historical retrieval path"。
- **`src/gis_recommend/planning/`（ExecutionAwareSelector，被周报当作核心成果）从未被主线 import**（证据 A：全 `src/` 仅 `planning/__init__.py` 自引用），只在 `scripts/` 里跑。

---

## 问题一：分层体系 L1→L2→L3 在运行时生成路径中不参与任何计算

**（名义分层，实际扁平）**

【问题】
文档、专利稿（`docs/patent/专利修改建议-分层参与生成过程.md`、`核心区别加固方案_分层计算作用.md`）将系统表述为"L1→L2→L3 分层参与生成"。但实际生成模型 `TaskConditionedL3TransformerModelV4` 只以「BERT 编码的自由文本 + 一个扁平 `task_type_id` 嵌入」为条件（`transformer_model_v4.py:300-307,309-369`），在 **94 个 L3 token 词表**上自回归预测。L1/L2 既不是输入、不是约束、也不是输出。解码端的转移约束矩阵是纯 **L3-token→L3-token**（`infer_l3_candidates_v4.py:265-269,402-410`）。L2 在解码器里**只出现在打印函数** `infer_and_print`（`:909-917`），对 logits / 评分 / 选择零影响。

【产生原因】
分层体系最初是为"知识图谱构建 + 人工分类标注"设计的组织原则，而生成模型是后接的、独立演化的 seq2seq。两者从未在"计算图"层面对齐——分层只在三处留下痕迹：①离线图嵌入训练（`build_graph_embeddings.py` 用 `l3_belongs_to_l2/l2_belongs_to_l1` 边）→ 初始化 L3 token 嵌入（`train_v4_2.py:1372-1373 use_l3_embeddings=True`）；②评测指标 `l2_set_f1/l2_accuracy`；③Neo4j GraphRAG 的可选校验/修复/QA。

【短期影响】
分层目前的唯一因果作用是「冻结在初始化里的嵌入几何先验」，且推理时 `use_l3_embeddings=False`、加载的是已训练 checkpoint，先验早被微调覆盖。对外宣称的"分层参与生成"在可复现的运行路径上**拿不出证据**——这是专利/论文的核心风险点。

【长期风险】
若继续在"分层驱动生成"叙事上加固，会形成**叙事与实现的不可调和分叉**：任何审稿人/审查员只要追一次调用链就能证伪；同时团队会持续把分层当成"已经在用"的能力而不去真正实现它，导致 L2 永远停留在标签层。

【严重程度】**致命**（对研究/专利定位而言）；对工程功能本身为中。

【优化方向】
二选一并明确承诺：(a)**诚实降级叙事**——把分层定位为"离线本体/嵌入先验/评测口径/KG 载体"，不再声称参与生成；或 (b)**让分层真正进入计算**——例如以 L2 为粗粒度意图层做分层解码/分层约束/分层条件，使 L2 对解码概率有可验证的因果作用。当前处于"既宣称又未实现"的最坏中间态。

【证据来源】`transformer_model_v4.py:300-369`；`infer_l3_candidates_v4.py:134,250-252,265-269,402-410,909-917`；`train_v4_2.py:1372-1373`；L2 全量 grep（仅 KG-build/metrics/print）。【证据等级】**A**。

---

## 问题二：系统"声明身份"与"运行时身份"系统性背离

**（retrieval/rerank/repair 的能力幻觉）**

【问题】
近三个月的成果（ExecutionAwareSelector、retrieval-centered planner、repair oracle、reranker v2/v3）在文档中被整合为"系统已是检索中心/执行感知/重排驱动"。运行时实测：reranker 仅 `--use-reranker` 时改写 `pred_tokens`（`runner.py:325-338`）；repair 即使开启也 `repair_applied=False`（`runner.py:398-401`）；retrieval 仅 shadow（`runner.py:205-217`，`decision_core_mode="shadow"`）；planning/ 不被主线 import。

【产生原因】
大量工作以"evaluation-only / report-only / 不改 pred_tokens"为安全边界推进（这是好的纪律），但**评估产物被回写进 handoff 文档当作系统能力**，造成"做了很多 ablation"被读成"系统具备这些能力"。

【短期影响】
对系统能力的自我认知偏乐观；新人/评审按文档以为主线已是 rerank/repair/retrieval，实际跑 `gis-evaluate` 得到的是裸 beam 数字，二者对不上。

【长期风险】
**可解释性塌陷**：当"系统是什么"取决于读哪份报告时，任何性能归因都不可信；后续决策（freeze L3、押注 QGIS landing）建立在未落地能力的假设上，可能投入到永远不进主线的支路。

【严重程度】**高**。

【优化方向】
建立单一权威的"运行时能力清单"（哪些组件真正进入默认选择路径），与"研究/评测探针"严格分账；任何"系统具备 X"的表述必须能映射到主线调用链的一行代码。`MainlineRunContract` 已是雏形，应升级为唯一事实源并禁止文档绕过它叙事。

【证据来源】`runner.py:130-139,205-217,325-401`；planning import grep；`run_contract.py`。【证据等级】**A**。

---

## 问题三：评测目标位移

**（硬指标长期低位 → 改用近乎恒满足的"可用性"软指标 + self-retrieval 召回）**

【问题】
主线序列指标长期低（V4.6 Top1≈31–56%、AR-SeqEM≈0%、Set Predictor F1=48%、向量任务模板坍塌）。文档头条却换成 `evaluate_workflow_usability.py`/`run_v4_qg_planner.py` 的规则可用性：Top-3/Top-5 usable=1.0、reranked Top1 usable=1.0；而 QGIS 检索召回的"100%"是 **self-retrieval**（`PROJECT_CONTEXT` 自标 "self-retrieval"）。

【产生原因】
真实生成质量遇到能力天花板（数据歧义+扁平模型），转向"能落地即算可用"的规则口径；该口径只要 Top-5 里有任一条规则可用链就判定成功，几乎必然满足。

【短期影响】
头条数字好看但与用户真实收益脱钩；"reranked Top1 usable=1.0" 实质是"池里有可用候选且重排把它提前"，不是生成正确性。

【长期风险】
**度量失效（measurement validity）**：一旦团队以可用性=1.0 / 召回=100% 作为里程碑，会停止改进真正的生成/泛化能力；self-retrieval 召回若被下游"可用率"依赖，则所有头条都带乐观偏置，形成自我欺骗的闭环。

【严重程度】**高**。

【优化方向】
确立指标分层契约：把"序列正确性/泛化"列为主 KPI，"规则可用性/landing"列为辅助证据，并强制标注其可满足性上界与是否 self-retrieval；持出集的检索必须排除 gold 自命中。

【证据来源】`PROJECT_CONTEXT` Current Data Truth/Completed 多条；`runner.py`（主线只算序列指标，无 usable）；`sampling.py:146-150`（索引级 split 干净，但 usable 来自 eval-only 脚本）。【证据等级】**B**（机制为 A：规则可用性与 self-retrieval 是真实代码；"被当头条"为文档推断）。需进一步验证：usable=1.0 是否在任何场景被当作主线结论上报。

---

## 问题四：系统"身份碎片化"

**（版本×数据根×训练制度×选择策略的笛卡尔爆炸）**

【问题】
并存：模型 V3 / V4.0–4.6 / V5_final / DPO / set_predictor_v3；数据根 `outputs`(350-L3) 与 `outputs_v2`(94-L3)；训练制度 TF / AR-SS / DPO / SFT / quality-gate / oversampled / MRV(mr_5/mr_10/mr_all_42)；选择策略 beam / reranker / retrieval / planner。`config` 里有 9 个版本常量块（`transformer_config.py:154-404`），多块标 ARCHIVED 但常量保留，`V4_1_WARMSTART_PATH` 指向已删除 checkpoint。"当前系统"在不同产物里定义不一致。

【产生原因】
长期单线快速迭代、"保留以兼容 import / 可重训再生"的保守策略、以及每次实验都新开 checkpoint 目录与数据包，从不回收。

【短期影响】
同名 `best_model.pth` 在不同版本是**不同选择标准**（`train_v3`=val_loss；`train_v4_6`=composite `0.5·SetF1+0.3·LCS+0.2·(1−earlyEOS)`，并另存 `best_gen_composite_model.pth`，`train_v4_6.py:612-703`）；warmstart 链 V4.6←V4.3←V4.2←(V4.0 已删)，且 V4.6 删除了 `memory.detach()`（`train_v4_6.py:334`）而 V4.2/4.3 保留（`train_v4_2.py:588`）——**两种梯度连通制度被拼接 warmstart**，行为不可直接比较。

【长期风险】
**路径锁定 + 不可复现**：跨 run 的指标对比（文档已自承"cross-run not perfectly controlled"，因全局转移矩阵被重建）失去对照基线；"哪一个是系统"无法回答，演化只能不断 fork 新版本，复杂度指数增长。

【严重程度】**高**。

【优化方向】
冻结一个"金标系统定义"（一个数据根 + 一个 checkpoint + 一套选择策略 + 一份转移矩阵）作为唯一发布物；checkpoint 文件名必须自带选择标准与口径指纹；废弃版本常量与目录应物理归档而非留在主 config。

【证据来源】`transformer_config.py:154-404,481-502`；`train_v3/v4_2/v4_6` 选择逻辑；`PROJECT_CONTEXT`（转移矩阵全局重建自承）。【证据等级】**A**。

---

## 问题五：配置无耦合校验 + 静默回退

**（潜在的"沉默错位"链）**

【问题】
多个独立失配点缺乏交叉校验：
1. `VOCAB_SIZE = env GIS_VOCAB_SIZE 默认94`（`transformer_config.py:63`）与数据根 `env GIS_OUTPUTS_DIR`（`:30-34`）**完全解耦**——指向 350-L3 数据而不改 vocab 不会报错。
2. `_active_outputs_is_v2()` 用**目录名等值**判断（`:37-42`，`OUTPUT_DIR.name=="outputs_v2"`）——把数据复制/改名为 `outputs_v2_bak`、`outputs_v3` 会**静默翻回 350-L3 文件名与 `classification_hierarchy.csv`**。
3. 转移矩阵加载器（`infer_l3_candidates_v4.py:258-270`）**不校验 token id 是否落在当前词表 0–93**；陈旧 350-L3 矩阵（含 id 352）会静默错约束或越界。
4. `pipelines/{interactive_system,recommend_pipeline,demo_complete_pipeline,stage2_completion_pipeline}.py` 与 `llm/llm_pipeline.py`、`data/length_bucket_predictor.py:49`、`knowledge_graph/graphrag_retriever.py:59` 仍**硬编码 `outputs/`(350-L3) 与 V3 checkpoint**。

【产生原因】
350→94 迁移以 config 默认路径切换为主，未建立"数据/词表/checkpoint/转移矩阵四者一致性"的运行时不变量；旧交互式管线未随迁移更新。

【短期影响】
checkpoint↔config 的 vocab 失配会被 `load_state_dict(strict=True)` 兜住（`infer:217`）——这是唯一隐式护栏；但**数据资产↔vocab 失配无人兜底**，可能静默产出语义错误的 L3（token 5 在 94/350 词表含义不同）。

【长期风险】
随平台/词表演化（接 GEE 之外、扩 L3、迁 v3 数据），无耦合校验会使"看似在跑、结果全错"成为常态，且极难定位（无报错）。

【严重程度】**高**。

【优化方向】
引入单一"数据指纹/词表/词表大小/转移矩阵版本"的一致性契约，在任意推理/训练入口启动时强校验（不匹配即拒绝运行）；以显式版本标识替代目录名等值；旧 `pipelines/`/`llm/` 管线要么迁移到 v2、要么物理隔离到 `legacy/` 并禁止默认 import。

【证据来源】`config:30-42,63`；`infer_l3_candidates_v4.py:206-217,258-270`；legacy `"outputs/"` grep（11+ 处）。【证据等级】**A**。

---

## 问题六：evidence/ 治理模块建成 → 不接线 → 测试断言永不接线

**（投机式架构债）**

【问题】
`src/gis_recommend/evidence/`（10+ 文件，导出 ~30 个治理对象：ProvenanceBlock/MetricBundle/CheckpointV5/lineage/validity/archaeology…，即 Phase 15C "统一语义契约"）**没有任何运行时模块 import 它**（证据 A：全仓 `from gis_recommend.evidence import` 仅命中其自身 `__init__.py` 与 test mock）。它自带 `__layer__/__allowed_imports__/__forbidden_imports__` 和"禁止被 training/inference import"的边界声明（`evidence/__init__.py:4-55`），而测试 `test_mvcs_closure_harness.py` 的"training→rank_checkpoints→evidence"是**模拟**——`rank_checkpoints` 在 `src/` 中根本不存在（grep 无命中）。

【产生原因】
Phase 11–15C 投入巨大精力设计"语义契约/10 条不变律/快照-解释-运行三层真相"，但最终结论是"运行时不接线、只做 report-only"，于是落成一个自我描述、自我禁止、却无人调用的子系统。

【短期影响】
死代码维护成本；更隐蔽的是**"evidence" 语义双关**——`shadow_phase.py`/`report.py` 里另有一套 "evidence-aware ranking / evidence bundle"（`shadow_phase.py:644,820`）是**完全不同的实现**，同名异义。

【长期风险】
后人无法判断哪套 evidence 是"真的治理"，可能误接孤立模块或误改 live 的 shadow evidence；治理意图（provenance/lineage）实际从未生效，却给人"已有治理"的错觉。

【严重程度】**中**（功能）/ **高**（认知一致性）。

【优化方向】
二选一：把 `evidence/` 真正接入 checkpoint 生命周期（让 provenance/lineage 在保存/加载时强制写读），或将其降级归档并消除与 `shadow_phase` 的命名冲突。不允许"建好放着 + 测试锁定它放着"这种状态长期存在。

【证据来源】`evidence/__init__.py:1-90`；evidence import grep；`rank_checkpoints` grep 无命中；`shadow_phase.py:634-820`。【证据等级】**A**。

---

## 问题七：治理/可观测性"元工程"过度增长

**（挤占核心能力推进）**

【问题】
围绕"如何安全地观察与不改变系统"的基础设施异常庞大：`run_contract.py`（MainlineRunContract）、`shadow_phase.py`、`evidence/`、`test_mvcs_closure_harness.py`、forbidden-pattern scan、~40 个 `scripts/evaluate_*` 探针、330KB 的 `PROJECT_CONTEXT.md`、十余份 protocol 文档。相对地，核心生成能力指标长期停滞。

【产生原因】
为防止"静默改变主线"而建立的强纪律（合理）逐渐自我增殖，"写报告/写契约/写边界测试"成了产出主体。

【短期影响】
每次迭代的固定开销（写 contract、写 report、写 forbidden scan、更新两份 context 文档）很高；真正改进模型/数据的边际投入被稀释。

【长期风险】
**目标置换**：系统越来越擅长"描述与约束自己"，而非"把工作流预测对"。元工程债与核心能力债同时累积，且元工程会让任何核心改动成本更高（要同时改 contract/test/doc）。

【严重程度】**中/高**。

【优化方向】
为元工程设预算上限；区分"必要的运行时契约（少量、强制、单一事实源）"与"一次性诊断脚本（用完归档）"；把诊断结论沉淀为少数稳定指标而非持续增长的报告资产。

【证据来源】`run_contract.py`、`shadow_phase.py`、`evidence/`、`scripts/` 清单、`PROJECT_CONTEXT.md`(330KB)。【证据等级】**A/B**。

---

## 问题八：基础设施重复发散 + Neo4j 单点强耦合 + 全局可变状态注入

【问题】（合并三个中等问题）
- **重复且发散的根/路径解析**：`_resolve_project_root` 至少 4 份独立实现，逻辑不一致（`config:19-26` 查 v2∨outputs；`infer_l3_candidates_v4.py:57-64` **只查 `outputs`**；`qgis_candidate_generator.py:22-28` 查 v2∨outputs；`recommend_pipeline.py:333`）。**3 个检索器**：`graphrag_retriever.py`(mock/legacy `outputs/`)、`neo4j_graphrag_retriever.py`(v2/live)、`planning` 内的 QGISChainRetriever。
- **Neo4j 单点强耦合**：QGIS 评测/校验/修复/QA 均依赖 live Neo4j（`reranker_pipeline.py:263-271`），且 KG 是 L1/L2 层次在运行时的唯一载体；默认 `neo4j/12345678`、单实例。
- **全局可变状态**：`runner.py:145-152` 通过对 `cfg` 与 `infer_mod` **双重 monkeypatch 模块级常量**来覆盖阈值（因为 `infer_mod` 在 import 时按值拷贝了常量）。

【产生原因】快速迭代下复制粘贴基础设施、模块级常量被当作可变配置、KG 既当语义载体又当校验后端。

【短期影响】改一处根解析/阈值需同步多处；离开 Neo4j 整条 QGIS 评测/修复链失效（且 set predictor 缺失时 soft prior 静默降级为 off，`reranker_pipeline.py:187-189`）。

【长期风险】级联失效与"改 A 漏 B"的回归；扩展到非 Neo4j 部署或多实例时需要大改；全局可变状态使并发/多配置评测不可靠。

【严重程度】**中**。

【优化方向】单一路径/配置解析源；检索器统一接口、legacy 物理隔离；KG 访问层抽象为可替换后端并去除硬编码口令；以显式参数传递替代模块级常量 monkeypatch。

【证据来源】各 `_resolve_project_root` 实现；三检索器文件；`reranker_pipeline.py:187-189,263-271`；`runner.py:145-152`。【证据等级】**A**。

---

## 问题九：数据层级泄漏与监督歧义

**（核心能力天花板的真实根因）**

【问题】
索引级 split 干净（`sampling.py:146-150` 用 `test_indices`），但 `PROJECT_CONTEXT` 的 training-data-quality 审计列出：内容级跨 split 重复 **5,934 条 L3 序列**、Top10 L3 占 **70.2%**、**67** 个 task type <10 样本、val/test 含 train 缺失的 task type、50,036 低置信 token。Set Predictor F1=48% 的根因被归为短序列偏置+高频 token 偏置+任务不均衡。

【产生原因】
训练数据来自 GEE 工作流爬取 + 自动映射 + 人工覆盖的混合，类别天然长尾；split 仅按索引去重、未按内容去重。

【短期影响】
内容级泄漏会高估持出指标；长尾使模型对低频任务/向量任务退化为模板（与"向量模板坍塌"一致）。

【长期风险】
**规模放大反噬**：数据量×10 而分布不变时，高频 L3 主导会更严重，扁平模型 + 弱 prior 的模板坍塌会固化；任何"加数据"的演化路径都会被分布问题吞掉。这是比模型容量更根本的瓶颈（文档 empirical bottleneck audit 亦如此结论，需独立复核）。

【严重程度】**高**。

【优化方向】
把"内容级去重 + 分布均衡 + 监督歧义消解"列为优先于换模型/加训练制度的工作；按内容指纹而非索引切分；为长尾任务建立专门的数据策略而非依赖采样器权重补偿。

【证据来源】`sampling.py:146-150`（索引级干净，A）；`PROJECT_CONTEXT` 审计与 empirical bottleneck audit（B/C）。【证据等级】**B**。需进一步验证：独立重算 5,934 跨 split 内容重复、Top10 占比、F1=48% 的可分解归因。

---

## 十、跨维度根因诊断（meta）

把上面九条收敛到三个根因：

1. **"组织原则"与"计算实现"从未对齐**（问题一/二）：分层、检索中心、执行感知都活在标签/文档/评测里，没进生成与选择的计算图。系统的"概念架构"和"运行架构"是两套。
2. **只增不删的演化**（问题四/五/六/七/八）：版本、数据根、训练制度、评测脚本、治理模块、基础设施副本——全部累积、几乎不回收。复杂度来自历史叠加而非当前需求。
3. **度量与叙事的乐观漂移**（问题三/九）：硬指标受限 → 改软指标/自检索 → 文档把探针结果当能力，掩盖了数据级与生成级的真实瓶颈。

---

## 十一、需要进一步验证的问题（证据不足）

- 【假设，需 A 级验证】`train_v4_4._train_step_ar` 是否真为死代码（`train_v4_4` 是否覆写 `train_epoch` 来分派 AR step）。已确认其定义存在（`train_v4_4.py:128`）但未追分派路径。
- 【假设，需 A 级验证】问题九的 5,934 内容级跨 split 重复、Top10=70.2%、F1=48% 归因——目前来自审计产物，应以脚本独立重算。
- 【假设，需 A 级验证】问题三：是否存在任何主线/对外结论直接采用 usable=1.0 或 self-retrieval 100% 作为头条（而非辅助证据）。
- 【未验证】`pipelines/interactive_system.py` 等 350-L3 旧管线是否仍被任何活跃入口/演示调用（grep 仅见 plan 文档里的语法自检），还是纯死代码——决定其属"分叉第二系统"还是"可删历史包袱"。
- 【未验证】V5_final（`models/v5_final/`、`train_v5.py`）与主线 V4.6 的关系：是继任者、平行研究分支还是已弃用。
- 【未深入】DPO v2 与 SFT(quality_gate_qgis_vector_*) checkpoint 与主线 `V4_6_TRANSFORMER_CHECKPOINT_DIR` 的实际对应关系需对账。

---

# 第二部分：架构修复蓝图（Architecture Evolution Blueprint）

## 组织说明：按"修复轨道"而非逐题编排

逐题修复会重复建设——上述 9 个问题在**修复手段**上高度共享。例如"身份碎片化(四)"、"配置无校验(五)"、"重复 root 解析(八)"三者的修复都收敛到**同一个运行时事实源**；"分层扁平(一)"与"声明身份背离(二)"都收敛到**概念架构与计算架构对齐**。所以修复按 6 条轨道组织，每条标注它**关闭哪些已验证问题**。

| 修复轨道 | 关闭的已验证问题 | 是否需要重训 | 依赖前置 |
|---|---|---|---|
| **T1 运行时单一事实源 + 一致性契约** | 四(碎片化)、五(静默回退)、八(重复解析) | 否 | 无（地基） |
| **T2 概念架构 vs 计算架构对齐** | 一(分层扁平)、二(身份背离) | Fork-B 需要 | T1 |
| **T3 度量效度修复** | 三(目标位移/self-retrieval) | 否 | 无 |
| **T4 死代码与元工程治理** | 六(evidence 孤立)、七(元工程过度)、八(legacy 管线/三检索器) | 否 | T1 |
| **T5 外部依赖解耦 + 全局状态消除** | 八(Neo4j 单点、monkeypatch) | 否 | 无 |
| **T6 数据级瓶颈** | 九(内容泄漏/长尾) | 是（数据再生） | T3 |

---

## T1｜运行时单一事实源 + 一致性契约

【问题】
"当前系统"没有唯一定义：词表大小、数据根、checkpoint、转移矩阵、层次表由各模块**独立解析、独立加载、互不校验**，存在多条静默错位路径。

【问题证据】
- **数据流（当前）**：每个组件 `import` config 常量后各自 `open()`：
  - `config.VOCAB_SIZE = env GIS_VOCAB_SIZE 默认94`（`transformer_config.py:63`）与数据根 `env GIS_OUTPUTS_DIR`（`:30-34`）**取自两个互不关联的 env**。
  - `_active_outputs_is_v2()` 用**目录名等值** `OUTPUT_DIR.name=="outputs_v2"` 决定 v2/legacy 文件名与层次表（`:37-42,416-420,437`）。
  - 转移矩阵加载 `_load_transition_matrix()` 直接读 `allowed_next` 转 int，**无 token 范围校验**（`infer_l3_candidates_v4.py:258-270`）。
- **模块依赖**：`_resolve_project_root` 至少 4 份独立副本，逻辑不一致（`config:19-26`；`infer_l3_candidates_v4.py:57-64` 只查 outputs；`qgis_candidate_generator.py:22-28`；`recommend_pipeline.py:333`）。
- **实际运行行为**：`runner.py:131` 已构造 `MainlineRunContract`，其 `DataAuthorityManifest` 已聚合 workflow/split/task_vocab/id_mappings/l3_vocab/io_types/checkpoint 七类路径（`run_contract.py:73-102,227-240`）——**但它是 report-only，infer/generator 并不从它加载**。
- **唯一现存护栏**：`load_state_dict(strict=True)`（`infer:217`）只能兜住 checkpoint↔config 的 vocab 维度失配；**数据资产↔vocab 失配无人兜底**。

【根因分析】
- **架构原因**：配置以"模块级常量"形态存在，被 `import` 即按值拷贝（这正是 `runner.py:145-152` 必须对 `cfg` 与 `infer_mod` **双重 monkeypatch** 才能改阈值的原因）。常量天生无法承载"解析+校验"职责。
- **历史原因**：350→94 迁移是"改 config 默认路径"式的就地替换，只保证默认路径正确，未建立"四资产一致"的不变量；旧模块复制了各自的 root 解析。
- **设计原因**：`run_contract` 出现得晚，定位被限定为"报告"（符合当时"report-only 不改主线"的纪律），于是聚合了正确字段却不被赋予加载权威。
- **扩展原因**：没有"系统配置 = 一个对象"的概念，每加一个版本/数据包就新增一组常量。

【修复目标】
- 当前：词表/数据/checkpoint/转移矩阵/层次表由 N 个点分散解析、零交叉校验、可静默错位。
- 目标：存在**唯一的运行时清单（Runtime Manifest）**作为事实源；所有训练/推理/评测入口从它取资产；启动时对"四资产指纹一致性"做强校验，不一致即**拒绝运行**（而非静默产错）。

【修复策略】

**1. 模块职责调整**
- `config/transformer_config.py`：职责**收窄**为"原始默认值与架构超参提供者"，剥离"激活配置解析 + v2/legacy 判定"职责。
- `evaluation/run_contract.py` 的 `DataAuthorityManifest`：职责**提升**——从"报告对象"升为"加载权威与一致性校验器"。它已聚合正确字段，是承载该职责的天然落点（无需新建平行体系）。
- 各模块的 `_resolve_*`：解析职责**上交**给 manifest，模块自身不再解析数据根/词表。

**2. 数据流调整**
- 当前：`config 常量 → 各组件各自 open()`；`runner → run_contract（仅报告）`。
- 建议：`config(原始默认) → D[RuntimeManifest: 解析+指纹+一致性校验] → infer / generator / trainer / calc 消费`。
- 为什么：把"解析+校验"从 N 个分散点收敛到单点 D，是消除"vocab=94 + 350 数据/转移矩阵"静默路径的**唯一结构性手段**；分散点上加再多局部校验也无法保证全局一致。

**3. 运行流程调整**
- 隐式逻辑显式化：①"目录名等值 → v2"翻译为显式版本标识读取；②转移矩阵 token 越界从"静默/越界崩"变为"启动期一致性校验项"。
- 特殊路径消失：数据目录被改名/复制后静默翻 legacy 的路径被消除。

**4. 接口契约调整**
- `QGISCandidateGenerator` 已接收 `run_contract=` 参数（`qgis_candidate_generator.py:191,207`）——**延续该模式**，让 `L3SequenceInferencerV4` 与训练器同样接收 manifest/authority 对象，而非各自读 config 常量。
- 状态变化：`VOCAB_SIZE` 由"可被 env 独立覆盖的全局"变为"manifest 的派生只读属性，与数据根绑定派生"。

【涉及代码范围】
- `config/transformer_config.py`（解析/判定职责上移）——所有 `import` 常量者的上游。
- `evaluation/run_contract.py`（manifest 升级为加载权威 + 指纹/校验）。
- `inference/infer_l3_candidates_v4.py` + `infer_l3_candidates_v4_qg.py`（`_load_model/_load_vocab/_load_transition_matrix` 改为从 manifest 取并校验）。
- `operators/qgis_candidate_generator.py`（已半就位，扩展为权威消费者）。
- `evaluation/runner.py`、`reranker_pipeline.py`（注入 manifest 而非默认 config）。
- `training/train_v4_2.py`（及继承者）：训练侧也消费同一 manifest，保证训练/推理同口径——否则 T2/T6 的重训会再次引入口径漂移。
- 受影响原因：以上都是当前**直接 open() 数据资产或 import VOCAB_SIZE** 的点。

【迁移策略】（沿用项目既有"先影子后强制"纪律——provenance gate 就是这么落地的，有先例）
- **Phase1（加校验、不改行为）**：在 `run_contract` 上补"四资产指纹 + 一致性校验"，输出为**警告 + 报告**，不阻断；跑现有 dev/smoke eval 收集真实失配清单。验收：现有指标**逐位不变**（证明零行为改变）。
- **Phase2（收敛解析、保留兼容）**：infer/trainer 改从 manifest 取路径（generator 已半就位）；`VOCAB_SIZE` 改为 manifest 派生但仍兼容读 env 并在不一致时告警；分散 `_resolve_*` 副本从"被调用路径"摘除（函数体可暂留以免 import 断裂）。
- **Phase3（启用强校验）**：警告升级为拒绝运行；显式版本标识取代目录名等值；9 个历史版本常量块迁入 legacy 命名空间，主 config 只留当前金标。

【风险分析】
- **兼容性**：现存 `outputs_v2` Step6-8 产物**早于 provenance 机制、审计为 `missing_provenance`**（`PROJECT_CONTEXT` 第 47 行）——Phase3 强校验会误伤；必须先补指纹或设"未知指纹=告警不阻断"的过渡态。
- **性能**：大文件 SHA-256 有一次性成本——指纹需缓存，不可每次推理重算。
- **隐式依赖暴露**：训练侧与推理侧 manifest 对齐后，会**暴露**历史上训练/推理口径不一致（短期"变红"是好事，但需预期）。

【验证方案】
- **调用链验证**：构造失配 manifest（vocab=94 + 350 转移矩阵 / 数据根改名），断言启动期**拒绝**（当前为静默/越界）。
- **数据流验证**：单测覆盖"数据目录改名后不再翻 legacy 文件名"。
- **回归验证**：Phase1 report-only 下 dev/smoke eval 数字不变。
- **极端测试**：缺指纹、半迁移（数据 v2 + checkpoint legacy）、env 与目录冲突三类组合。

---

## T2｜概念架构 vs 计算架构对齐（含一个必须的决断闸门）

【问题】
系统对外的概念架构（L1→L2→L3 分层参与生成；retrieval-centered / rerank-driven）在运行时**不成立**：生成模型是扁平的 text+task_type→L3；L2/L1 不参与解码；retrieval/rerank/repair 是 opt-in 或 report-only。

【问题证据】
- **模型层**：`TaskConditionedL3TransformerModelV4` 的 condition = `fuse(text_CLS, task_type_emb)`（`transformer_model_v4.py:300-307`），输出在 98-token L3 词表（`:262,369`）。L1/L2 非输入/约束/输出。
- **解码层**：转移约束是 L3-token→L3-token（`infer_l3_candidates_v4.py:265-269,402-410`）；L2 仅在 `infer_and_print` 打印（`:909-917`）。
- **分层的唯一因果点**：训练初始化加载图嵌入（`train_v4_2.py:1372-1373 use_l3_embeddings=True`，图嵌入含 `l3_belongs_to_l2/l2_belongs_to_l1` 边，`build_graph_embeddings.py`）——是**冻结在初始化的嵌入几何先验**，且推理 `use_l3_embeddings=False`（`infer:203`）。
- **身份背离**：reranker 仅 `--use-reranker` 改写 `pred_tokens`（`runner.py:325-338`）、repair `repair_applied=False`（`:398`）、retrieval `decision_core_mode="shadow"`（`:137`）；`gis_recommend.planning` 全 `src/` 无主线 import。
- **契约其实已诚实**：`run_contract.l2_role={affects_decoding:False, affects_selection:False}`（`run_contract.py:268-272`）——是**文档叙事绕过了这个契约**。

【根因分析】
- **架构原因**：分层体系为"KG 构建 + 人工标注"而生，生成模型是后接的独立 seq2seq，两者从未在计算图层面对齐。
- **语义原因**："分层"一词在系统里有四个互不等价的含义（本体设计 / 嵌入先验 / 评测口径 / KG 载体），对外叙事把它们**合并表述为"参与生成"**。
- **设计原因**：retrieval/rerank/repair 以"evaluation-only 不改主线"为安全边界推进（纪律正确），但评测产物被回写文档当作"系统能力"。
- **扩展原因**：缺少"声明能力集 = 运行时可达能力集"的强制对账机制。

【修复目标】
- 当前：声明能力 ⊋ 运行时能力；分层是装饰性叙事。
- 目标：**声明能力集 ≡ 运行时可达能力集**；且对"L2 是否参与生成"做出**显式架构决断**，使分层要么诚实降级、要么真正具备可验证的解码因果作用。

【修复策略】

> 本轨道的核心不是"加抽象层"，而是一个**决断闸门（Decision Gate）**：L2 在生成中扮演什么。两条分叉都要落到代码可映射的结构上。

**1. 模块职责调整**
- **能力注册职责**：`run_contract` 的 `candidate_pool_enabled/decision_core_mode/retrieval_mode/l2_authority`（`run_contract.py:248-251`）从"描述单次 run"提升为**系统能力的唯一声明源**；对外能力表（论文/专利/handoff）必须由它生成，不允许脱离它叙事。
- **planning/ 的归属决断**：`ExecutionAwareSelector` 要么接入主线选择路径（让"rerank-driven"成真），要么显式标注"研究探针·未上线"。二者不可并存于模糊态。

**Fork A（诚实降级·低风险·立即可做）**
- L2 运行时角色正式锁定为 `interpretation/eval/KG`（契约已写，只需让产物强制引用）。这是**叙事-契约对齐**，不动模型。

**Fork B（真正实现"分层参与生成"·高研究/专利价值·需重训）**——三个可落地的架构选项：
- **B1 分层约束解码**：当前 set predictor 预测 L3 token presence（`set_predictor_v3`），soft prior 仅 +0.5 偏置（`infer:349-357`）。演化为"先预测 L2 意图分布 → 以 L2 约束/偏置 L3 解码"，使 L2 对解码概率有**可消融验证**的因果作用。
- **B2 分层条件注入**：模型 condition（`transformer_model_v4.py:300-307` 的 FiLM 融合）增加 L2 意图嵌入维度，让 L2 进入每层 FiLM 调制。
- **B3 两段式规划**：L2 序列规划 → L3 落地，与 KG `belongs_to_l2` 天然对齐，也与 `docs/v5_l2_semantic_recovery_protocol.md` 的长期目标一致。

**2. 数据流调整**
- Fork B1 当前：`text → set_predictor(L3 presence) → +0.5 soft bias → L3 beam`。
- Fork B1 建议：`text → L2 意图预测 → L2-约束的 L3 解码`（L2 进入 `_apply_constraints` 的约束来源，与现有 transition/setprior 约束并列）。
- 为什么：只有当 L2 出现在"改变 logits 的那一步"，"分层参与生成"才在 runtime 成立、才可被消融证明。

**3. 运行流程调整**
- 隐式显式化：把"L2 不参与生成"这一事实从"埋在调用链里"提升为契约里的显式声明（Fork A），或把 L2 真正插入解码路径（Fork B）。
- 特殊路径：planning/ 的"scripts-only"模糊态消失（接入或明确下线）。

**4. 接口契约调整**
- Fork B 下，解码器约束接口从"transition + set-prior"扩展为"transition + set-prior + L2-intent"；模型 forward 的 condition 入参语义扩展。
- 能力声明接口：对外报告/论文的能力字段统一从 `run_contract` 派生。

【涉及代码范围】
- Fork A：`run_contract.py`（能力声明权威化）、所有对外报告生成处（`evaluation/report.py`）、文档/专利稿（叙事对齐）、`planning/__init__.py`（标注上线状态）。
- Fork B：`models/transformer_model_v4.py`（条件/输出）、`models/set_predictor_v3.py`（L2 头）、`inference/infer_l3_candidates_v4*.py`（`_apply_constraints` 约束来源）、`training/train_v4_2.py`（损失/监督）、`build_graph_embeddings.py`（L2 监督信号）——**这是一次模型代际演化，不是局部修补**。
- 受影响原因：Fork B 触及"条件 → 解码 → 损失"全链，因为要让 L2 真正进入计算图。

【迁移策略】
- **Phase1（立即·Fork A）**：能力声明权威化 + 叙事对齐 + planning 状态标注。**零模型风险**，立刻消除"声明 ⊋ 运行时"的认知风险与专利证伪风险。
- **Phase2（研究闸门）**：在冻结的 V4.6 上做**L2 因果消融实验**——构造"有/无 L2 信号"两版，量化 L2 对解码的边际贡献。若贡献显著 → 进 Phase3；若不显著 → 永久采纳 Fork A 并据实修订专利。
- **Phase3（Fork B 实现）**：选 B1/B2/B3 之一，作为新模型代（建议 B1，改动面最小且最贴现有 set predictor 结构），按 T1 的同口径 manifest 重训。
- 兼容：Phase1/2 不动主线；Phase3 作为新版本与 V4.6 并行评测，达标才替换。

【风险分析】
- **精度风险**：Fork B 引入 L2 约束可能在数据长尾下**收紧搜索空间反而降召回**（与问题九耦合）——必须先做 T6 数据修复或同步评估。
- **兼容性**：Fork B 改变 condition/词表语义 → 与所有 V4.x checkpoint warmstart 不兼容（`strict=True` 会拒绝），需全新训练谱系。
- **研究风险**：Phase2 消融若证明 L2 无因果贡献，等于自证"分层参与生成"在当前实现下不成立——这对专利是**必须提前知道**的事实，越早越好。

【验证方案】
- **行为验证（Fork A）**：断言任意对外能力陈述都能映射到 `run_contract` 字段；planning 无主线 import 的事实被显式标注。
- **因果验证（Fork B 核心）**：L2 信号消融——固定随机种子，对比"注入 L2 / 屏蔽 L2"的解码分布差异（KL、Top-1 变化率）。**这是"分层参与生成"唯一可接受的证明**。
- **回归验证**：Fork B 新模型在持出集上序列指标不低于 V4.6 才允许上线。

---

## T3｜度量效度修复

【问题】
头条指标用近乎恒满足的规则可用性（Top3/5 usable=1.0、reranked Top1 usable=1.0）与 self-retrieval 100% 召回，硬指标（序列正确性）被降级为 diagnostic，造成度量乐观漂移。

【问题证据】
- **运行行为**：主线 `runner.py` 只算序列指标（set_f1/lcs/l2_set_f1，`:417-508`），不产出 usable；usable=1.0 来自 eval-only 的 `evaluate_workflow_usability.py` 与 `run_v4_qg_planner.py`（`PROJECT_CONTEXT` 第 76-77 行）。
- **self-retrieval**：召回 100% 自标 "self-retrieval"（`PROJECT_CONTEXT` 第 16/184/186 行），索引含 gold。
- **可满足性**：reranked Top1 usable=1.0 的机制是"Top5 内只要有任一规则可用候选，重排把它提前"——指标几乎必然满足。

【根因分析】
- **架构原因**：评测体系（`evaluation/` + ~40 个 `scripts/evaluate_*`）与主线生成解耦，各自定义"成功"，无统一指标层级契约。
- **历史原因**：真实生成质量遇到数据级天花板（问题九），叙事转向"能落地即可用"的软口径。
- **语义原因**："usable"被定义为规则可满足而非用户价值；"recall"在 self-retrieval 下度量的是索引成员资格而非泛化。

【修复目标】
- 当前：头条=软指标（近乎恒满足）+ self-retrieval 召回。
- 目标：主 KPI 反映真实泛化（持出、排除自命中）；可用性/landing 作辅助证据且**强制标注可满足性上界与是否 self-retrieval**。

【修复策略】
**1. 模块职责调整**：`evaluate_v4_quality_gate.py` 已有 `five_tier_metrics` 五层视图（`PROJECT_CONTEXT` 2026-05-19）——框架在，但层级排序把 usability 置顶。修复=**指标层级契约**：序列/泛化为主，usability/landing 为辅，元数据强制标注口径。
**2. 数据流调整**：检索评测（`empirical.py::LexicalRetrieval`、QGISChainRetriever）当前 `build index(含 gold) → retrieve`；建议 `build index(按内容指纹排除同源 query) → retrieve`，使召回反映真实泛化。
**3. 运行流程调整**：self-retrieval 与 held-out-retrieval 显式分流为两个命名口径，禁止混用为头条。
**4. 接口契约调整**：每个指标产物携带 `is_self_retrieval / satisfiability_ceiling / split_source` 元字段（与 T1 manifest 的 token_profile 报告风格一致）。

【涉及代码范围】
- `evaluation/empirical.py`、`evaluation/report.py`、`evaluation/runner.py`（指标层级与元标注）；`scripts/evaluate_workflow_usability.py`、`run_v4_qg_planner.py`、QGISChainRetriever（self-retrieval 排除）。受影响原因：这些是 usable/recall 头条数字的产生点。

【迁移策略】
- Phase1：给现有指标产物加口径元标注（不改算法），让"哪些是 self-retrieval / 软指标"在报告里一目了然。
- Phase2：检索评测加入"同源内容指纹排除"，产出 held-out 召回，与旧 self-retrieval 并列展示落差。
- Phase3：对外/handoff 头条切换为持出序列+泛化指标，usable/landing 降为附录证据。

【风险分析】
- **精度/观感风险**：去掉自命中后召回会**显著下降**，landing usable 会从 1.0 回落——这是修复"度量幻觉"的必然代价，需提前与利益相关方沟通预期。
- **数据问题**：内容指纹排除依赖 T6 的内容去重能力（耦合）。

【验证方案】
- **数据流验证**：断言 held-out 检索的索引不含与 query 同内容指纹的条目。
- **行为验证**：同一模型在"self vs held-out"两口径下的召回落差被显式量化报告。
- **回归**：序列指标计算路径不被本轨道改动（只加元标注）。

---

## T4｜死代码与元工程治理

【问题】
`evidence/` 治理模块完全孤立（建成→不接线→测试断言不接线），与 `shadow_phase` 的 "evidence" 命名冲突；元工程（契约/报告/影子/边界测试/~40 评测脚本/330KB 文档）过度增长；legacy `pipelines/`+`llm/` 与三检索器并存。

【问题证据】
- `evidence/`（10+ 文件、~30 导出）**无任何运行时 importer**（`from gis_recommend.evidence import` 仅命中其 `__init__.py` 与 test mock）；测试假设的 `rank_checkpoints` 在 `src/` **不存在**（grep 无命中）；自带 `__forbidden_imports__/__layer__`（`evidence/__init__.py:4-55`）。
- 命名冲突：`shadow_phase.py:644,820` 的 "evidence-aware" 是另一套实现。
- legacy 管线硬编码 350-L3/V3：`pipelines/{interactive_system,recommend_pipeline,demo_complete_pipeline,stage2_completion_pipeline}.py`、`llm/llm_pipeline.py`（`"outputs/...v3..."`）。
- 三检索器：`graphrag_retriever.py`(mock/legacy) / `neo4j_graphrag_retriever.py`(v2/live) / `planning` QGISChainRetriever。

【根因分析】
- **历史原因**：Phase 11–15C 投入巨量精力设计"语义契约/10 不变律/三层真相"，最终结论是"运行时不接线"，落成自描述但无人调用的子系统。
- **设计原因**："report-only / 不改主线"纪律被推到极致，产出主体变成"描述与约束系统"。
- **扩展原因**：只增不删——旧管线、旧检索器、旧版本从不回收。

【修复目标】
- 当前：孤立治理模块 + 命名双关 + legacy 并存 + 元工程无预算。
- 目标：每个模块**要么接入运行时、要么物理隔离归档**；"evidence"语义唯一；元工程区分"运行时契约（少、强制、单一）"与"一次性诊断脚本（用完归档）"。

【修复策略】
**1. 模块职责调整**：`evidence/` 决断——接入 checkpoint 生命周期（让 provenance/lineage 在保存/加载强制读写，与 T1 指纹天然合并），或降级归档；与 `shadow_phase` 的 evidence 语义二选一保留。legacy `pipelines/`/`llm/` 旧管线职责标注为"历史/演示"，从默认调用路径摘除。检索器统一为单一接口、多后端（live/mock）。
**2. 数据流调整**：若 `evidence/` 接入，则 `保存 checkpoint → 写 provenance 块` 与 `加载 → 校验 provenance` 成为 T1 一致性校验的一部分（两轨合并，避免重复造指纹）。
**3. 运行流程调整**：legacy 管线从"可被默认 import"变为"显式 legacy 命名空间、默认不可达"；诊断脚本产物进入归档区而非持续累积在主 outputs。
**4. 接口契约调整**：检索器统一抽象（召回接口一致，后端可换），消除调用方对具体后端的硬依赖。

【涉及代码范围】
- `evidence/*`（接入或归档）；`evaluation/shadow_phase.py`、`report.py`（命名消歧）；`pipelines/*`、`llm/llm_pipeline.py`（隔离）；`knowledge_graph/graphrag_retriever.py` vs `neo4j_graphrag_retriever.py` vs `planning/qgis_chain_planner.py`（检索器统一）。

【迁移策略】
- Phase1：标注与冻结——`evidence/` 与 legacy 管线打"未接线/历史"标记，禁止新增依赖；命名冲突先在文档/注释层澄清。
- Phase2：决断执行——`evidence/` 接入 T1 指纹链 或 归档；检索器收敛到统一接口（live/mock 作后端）。
- Phase3：物理隔离——legacy 管线与废弃版本迁入 legacy 命名空间，主代码树只保留金标。

【风险分析】
- **隐式依赖**：legacy 管线可能被某些未识别的 `scripts/`/notebook 调用——隔离前需 grep 全量 importer（已部分完成：仅文档语法自检引用）。
- **测试耦合**：`test_mvcs_closure_harness.py` 断言"training 不 import evidence"——`evidence/` 决断后该测试语义需相应调整。

【验证方案】
- **调用链验证**：隔离后断言 legacy 管线/`evidence/` 在主线调用图中不可达。
- **回归**：检索器接口统一后，主线 QGIS 评测结果不变（live 后端行为等价）。

---

## T5｜外部依赖解耦 + 全局状态消除

【问题】
QGIS 评测/校验/修复/QA 强耦合 live Neo4j（默认口令、单实例）；阈值覆盖通过对模块级常量双重 monkeypatch 实现。

【问题证据】
- `reranker_pipeline.py:263-271` 直接 `Neo4jGraphRAGRetriever()+ChainValidator`；KG 是 L1/L2 在运行时的唯一载体。
- set predictor 缺失时 soft prior **静默降级为 off**（`reranker_pipeline.py:187-189`）。
- `runner.py:145-152` 对 `cfg` 与 `infer_mod` **双重 monkeypatch** 阈值常量（因 import 时按值拷贝）。

【根因分析】
- **架构原因**：KG 既当语义载体又当校验后端，无访问抽象层；配置以模块常量形态存在，无法运行时注入。
- **扩展原因**：未考虑无 Neo4j 部署或多实例/并发评测。

【修复目标】
- 当前：离开 Neo4j 整条 QGIS 链失效；阈值改写靠 monkeypatch。
- 目标：KG 访问经抽象层，无 Neo4j 时优雅降级（功能子集仍可跑）；运行参数经显式传递，无模块级可变全局。

【修复策略】
**1. 模块职责调整**：KG 访问抽象为"检索后端接口"（`graphrag_retriever.py` 的 mock 模式可作降级后端雏形）；配置消费从"读模块常量"改为"接收运行时参数对象"（与 T1 manifest 合流）。
**2. 数据流调整**：当前 `runner → monkeypatch cfg/infer_mod → infer 读常量`；建议 `runner → 参数对象 → infer 接收`，消除按值拷贝导致的双改。
**3. 运行流程调整**：无 Neo4j 时，QGIS 校验从"崩溃/异常"变为"显式降级标记 + 跳过链校验"（行为可预测）；set-prior 静默降级改为显式状态上报。
**4. 接口契约调整**：检索/校验接口声明后端能力（live/degraded），调用方据此分支而非靠 try/except 捕获连接失败。

【涉及代码范围】
- `knowledge_graph/neo4j_graphrag_retriever.py`、`chain_validator.py`、`reranker_pipeline.py`、`runner.py`（阈值传递）、`config`（阈值常量）。

【迁移策略】
- Phase1：阈值改显式参数传递（与 T1 manifest 合并），保留 monkeypatch 兼容路径并告警。
- Phase2：KG 访问抽象层 + 降级后端；无 Neo4j 运行的功能子集明确化。
- Phase3：移除 monkeypatch；硬编码口令移出代码（配置/环境）。

【风险分析】
- **兼容性**：降级后端的 QGIS 指标与 live 不可直接比较——需标注口径（与 T3 元标注一致）。
- **隐式依赖**：现有脚本可能依赖"连不上就静默降 off"的行为——显式化会改变其观感。

【验证方案】
- **调用链验证**：无 Neo4j 环境下主线 `--skip-qgis` 与"QGIS 降级"两路径均不崩溃且状态显式。
- **行为验证**：阈值经参数传递后，单进程内多配置评测互不污染（消除全局可变状态的并发隐患）。

---

## T6｜数据级瓶颈（内容级去重 + 长尾）

【问题】
索引级 split 干净，但内容级跨 split 重复（5,934 L3 序列）、Top10 L3 占 70.2%、67 task type <10 样本、val/test 含 train 缺失类型；Set Predictor F1=48% 根因在数据而非模型容量。

【问题证据】
- `sampling.py:146-150` 用 `test_indices`——**索引级**无泄漏。
- 内容级泄漏/长尾来自 `training_data_quality` 审计（`PROJECT_CONTEXT` 第 51 行）；`data/training_data_quality.py` + `quality_gate.py` 已具备审计能力。

【根因分析】
- **数据原因**：训练数据来自 GEE 爬取 + 自动映射 + 人工覆盖混合，类别天然长尾；split 仅按索引去重、未按内容去重。
- **扩展原因**：数据规模放大而分布不变时，高频 L3 主导与模板坍塌会固化——任何"加数据/换训练制度"的演化都会被分布问题吞掉。

【修复目标】
- 当前：内容级泄漏高估持出指标；长尾驱动模板坍塌。
- 目标：split 按**内容指纹**而非索引切分；长尾任务有专门数据策略；持出指标无内容级泄漏。

【修复策略】
**1. 模块职责调整**：`data/quality_gate.py`（已建 grouped split by L3 sequence hash，`PROJECT_CONTEXT` 2026-05-07）的"内容分组"职责**升格为强制 gate**——split 构造从索引去重升级为内容指纹去重。
**2. 数据流调整**：当前 `workflows → index split → 内容仍跨 split 重复`；建议 `workflows → 内容指纹聚类 → 按簇分配 split`，保证同内容不跨 split。
**3. 运行流程调整**：长尾任务（<10 样本）从"采样器权重补偿"显式化为"数据策略决策"（合并/增广/单列）。
**4. 接口契约调整**：split 文件携带"去重粒度=内容指纹"的口径声明，供 T3 检索评测复用同一指纹做自命中排除。

【涉及代码范围】
- `data/quality_gate.py`、`training_data_quality.py`、`training/splits.py`、`evaluation/sampling.py`；下游所有读 `dataset_splits_v4.json` 者。受影响原因：split 语义变化会触及训练/评测的数据入口。

【迁移策略】
- Phase1：审计——量化内容级泄漏的真实影响（重算 5,934、Top10 占比对持出指标的高估幅度）。
- Phase2：产出"内容指纹 split"作为**并行新数据包**（不覆盖现有，沿用项目"派生候选不覆盖 Step8"的纪律），对比新旧持出指标落差。
- Phase3：长尾数据策略实施 + 切换为内容级 split 作金标（配合 T1 manifest 与 T2-Fork B 重训）。

【风险分析】
- **精度风险**：内容级去重后训练集变小、持出指标下降——这是修正"泄漏高估"的真实代价。
- **数据问题**：内容指纹定义（精确序列 vs 规范化后）会影响去重力度——需与 `empirical.py` 的 canonicalize 逻辑对齐，避免两套指纹。

【验证方案】
- **数据流验证**：断言新 split 下无内容指纹跨 train/val/test。
- **行为验证**：同模型在"索引 split vs 内容 split"上的持出指标落差被量化（暴露原泄漏高估）。
- **回归**：长尾任务的逐类型指标在新数据策略下不退化。

---

## 七、跨轨道演化总排序与共同基础设施

修复有**依赖偏序**，不能并行乱做：

```
        T1 (运行时事实源/一致性契约)  ← 地基，最先
        ├──► T4 (死代码/元工程: evidence 接入 T1 指纹链)
        ├──► T5 (全局状态消除: 阈值并入 T1 参数对象)
        └──► T2 (概念/计算对齐)
                  └─ Phase2 决断闸门 ─► T6 (数据修复) ─► T2-ForkB 重训
        T3 (度量效度) 可与 T1 并行，但其"自命中排除"依赖 T6 的内容指纹
```

**关键编排逻辑**：
1. **T1 先行**——它是其余所有轨道的共同地基（指纹、manifest、参数注入被 T4/T5/T6 复用），且**零行为改变即可落地 Phase1**（report-only 有先例）。
2. **T2 的决断闸门是全局分水岭**：在投入 T6 数据修复与重训之前，必须先用 Phase2 消融实验确定"L2 是否值得进入计算图"。这避免了"先重训再发现分层无用"的不可逆浪费——这是整张蓝图里**唯一的不可逆决策点**，必须用实验而非直觉裁决。
3. **T3 与 T6 共享"内容指纹"**：两轨必须用同一套指纹定义（与 `empirical.py` canonicalize 对齐），否则会再造一组发散基础设施（重蹈问题八覆辙）。

**贯穿所有轨道的统一纪律**（项目已有先例，应固化为蓝图级约束）：
- 每轨 **Phase1 一律 report-only/告警**，用现有 dev/smoke eval 证明"零行为改变"，再逐步升级为强制——这是 provenance gate 已验证可行的安全迁移范式。
- 任何"派生产物不覆盖金标"（沿用 step8_quality_gate 不覆盖 step8 的纪律）。
- 每轨的验收都包含一条**调用链断言**（证明运行时真相已改变，而非仅文档改变）——这是对抗"声明 ⊋ 运行时"复发的结构性免疫。

---

## 附：本文档的边界与使用说明

- 本文档的"第一部分"结论以 **A 级证据**为主（直接读 `runner.py` / `reranker_pipeline.py` / `infer_l3_candidates_v4.py` / `transformer_model_v4.py` / `transformer_config.py` / `sampling.py` / `run_contract.py` / `evidence/__init__.py` / 训练器，以及多次 grep 交叉验证）；**B/C 级**结论（问题三、九）已在文中标注，需以独立脚本复算确认（见"十一、需要进一步验证的问题"）。
- "第二部分"是**架构演化方向与迁移序列**，不是代码补丁。所有"修复策略"停留在模块职责 / 数据流 / 运行流程 / 接口契约层；落地时应先按各轨 Phase1（report-only）验证零行为改变，再逐步强制。
- 本文档**不修改任何代码、数据或 checkpoint**；它是规划与决策依据，与 `docs/PROJECT_CONTEXT.md`（运行手册）互补：前者诊断"为什么要改、怎么改"，后者记录"当前真实状态"。
