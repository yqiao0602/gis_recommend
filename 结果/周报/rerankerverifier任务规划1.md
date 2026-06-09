# reranker / verifier 任务规划 1

## 1. 模块目标

当前系统的主要问题不是单纯“生成能力不够”，而是：

- L3 阶段只取 beam `top-1`
- QGIS 阶段只取候选链 `top-1`
- 缺少真正的全局候选选优
- 缺少把结构校验结果反馈到最终决策的机制

因此，`reranker / verifier` 模块的目标是：

`在不改动当前 V4.6 主生成器的前提下，对多候选进行全局打分、验证、选优，并在必要时进行修复。`

一句话概括：

`从“生成后直接取第一条”改成“生成多条候选 -> 结构化验证 -> 全局选优 -> 必要时修复”。`

## 2. 当前代码现状

当前主评估链路中，`top-1` 选择是硬编码的：

- [evaluate_system.py](E:/02_projects/03_PythonProject/Operator-recommend-system/Algorithm_classification/system_redesign/scripts/evaluate_system.py)
  - L3 阶段直接取 `candidates[0].tokens`
  - QGIS 阶段直接取 `candidates[0]`

当前仓库中已经存在可复用的候选打分与修复逻辑：

- [interactive_system.py](E:/02_projects/03_PythonProject/Operator-recommend-system/Algorithm_classification/system_redesign/src/gis_recommend/pipelines/interactive_system.py)
  - 已有 GraphRAG 结构化评分
  - 已有 top-3 候选二次打分
  - 已有链修复逻辑接入

- [qgis_candidate_generator.py](E:/02_projects/03_PythonProject/Operator-recommend-system/Algorithm_classification/system_redesign/src/gis_recommend/operators/qgis_candidate_generator.py)
  - 候选中已包含 `score / confidence / unknown_count / unknown_ratio / has_critical_unknown`

- [chain_repair.py](E:/02_projects/03_PythonProject/Operator-recommend-system/Algorithm_classification/system_redesign/src/gis_recommend/knowledge_graph/chain_repair.py)
  - 已有修复器

所以当前最优策略不是重新发明，而是把已有逻辑抽成正式模块，接到主评估链路。

## 3. 模块边界

本轮 `reranker / verifier` 只解决以下问题：

- 输入多条候选
- 提取结构化特征
- 计算候选得分
- 选择最终候选
- 必要时做修复
- 输出可解释的中间分数和最终结果

本轮暂时不做：

- 不训练新的 LLM 作为 reranker
- 不替换现有 transformer 主干
- 不与 planner 并行开发
- 不马上做学习式排序模型

原因：

- 当前首先需要的是“快速验证 top-N 候选里是否已有更优解”
- 第一版必须可解释、可控、可复现
- 先做规则/结构化 rerank，才能判断后续是否值得上更重的 learned reranker

## 4. 模块定位

建议把功能拆成两个逻辑子模块：

### 4.1 Verifier

职责：

- 对候选链做结构合法性检查
- 输出结构化特征
- 输出问题诊断信息

它不负责最终排序，只负责“看懂候选好不好”。

### 4.2 Reranker

职责：

- 接收多条候选及其 verifier 特征
- 按统一评分函数排序
- 选出最终 top-1
- 保留 top-k 及各项分数，方便后续分析

它不负责生成新候选，只负责“从已有候选里选最好的一条”。

## 5. 建议的数据流

建议采用如下链路：

`自然语言 -> V4.6 生成 top-N L3 候选 -> 每条 L3 生成 top-M QGIS 候选 -> verifier 提取结构化特征 -> reranker 综合打分 -> 选出最佳候选 -> 如有问题则 repair -> 输出最终链`

这里的关键点是：

- 不再只保留一条 L3 序列
- 不再只保留一条 QGIS 链
- 先做候选池，再做全局选优

## 6. 第一版推荐实现方案

### 6.1 第一版目标

第一版只做：

- `结构化 reranker`
- `非 LLM verifier`
- `可选 repair`

不做：

- LLM 打分器
- 学习式排序模型
- planner 联动

### 6.2 第一版候选粒度

建议优先做 `QGIS chain` 级别 rerank，而不是只做 L3 级别 rerank。

原因：

- 最终系统目标是工作流推荐，不只是 L3 序列生成
- QGIS 候选已经包含更丰富的结构信息
- GraphRAG / validator / repair 都在 QGIS 链级别发挥作用

因此：

- L3 负责生成候选池
- QGIS chain 才是 reranker 真正的排序对象

### 6.3 第一版候选池构造

建议参数：

- L3 top-N：`5` 或 `10`
- 每条 L3 生成 QGIS top-M：`3` 或 `5`

最终形成候选池：

- `N x M` 条候选链
- 去重后进入 reranker

### 6.4 第一版结构化特征

建议优先使用以下特征：

#### A. 来自 L3 生成器的特征

- L3 候选原始 `final_score`
- L3 长度
- 与任务类型期望长度的偏差
- 与 set predictor 的集合一致性
- 高置信 must-have token 是否覆盖

#### B. 来自 QGIS 候选生成器的特征

- `candidate.score`
- `candidate.confidence`
- `unknown_count`
- `unknown_ratio`
- `has_critical_unknown`

#### C. 来自 verifier / GraphRAG 的特征

- known operator ratio
- I/O compatibility ratio
- chain validation confidence
- validation issue count
- 是否存在严重结构问题

#### D. 可选补充特征

- 与历史 workflow 的相似度
- L2 功能覆盖度
- 首尾关键步骤是否合理

### 6.5 第一版评分函数

建议先做加权结构分，不做学习模型。

示例思路：

`final_score = w1 * l3_score + w2 * qgis_score + w3 * set_overlap + w4 * io_score + w5 * validation_confidence - w6 * unknown_penalty - w7 * issue_penalty - w8 * length_penalty`

第一版原则：

- 所有分项都可解释
- 所有分项都可打印
- 权重人工设定
- 后续再根据实验微调

### 6.6 Repair 触发策略

建议第一版只修最终 top-1，不对所有候选都修。

触发条件建议：

- top-1 存在 validation issue
- issue 数量不为 0
- 或 `unknown_ratio` 高于阈值

原因：

- 先保证运行成本可控
- 避免 repair 过重影响整体评估效率

## 7. 分阶段实施方案

### 阶段 1：Oracle 分析与候选池打通

目标：

- 不改评分逻辑
- 先打通“生成多候选 -> 保存候选池 -> 统计 oracle”流程

需要完成的任务：

- 修改评估脚本，保留 top-N L3 候选
- 每条 L3 生成 top-M QGIS 候选
- 输出候选池信息
- 统计 oracle@1 / oracle@3 / oracle@5 / oracle@10

这一阶段要回答的关键问题是：

- `正确或更优的候选是否已经出现在候选池中？`

如果 oracle gap 明显，说明 reranker 很值。

### 阶段 2：结构化 reranker V1

目标：

- 用规则/结构化特征进行正式重排
- 替换当前“直接取 top-1”的逻辑

需要完成的任务：

- 实现 verifier 特征提取
- 实现 reranker 打分器
- 在评估脚本中接入 rerank 开关
- 输出每条候选的分项得分和最终排序

### 阶段 3：repair 接入

目标：

- 对最终 top-1 做轻量修复
- 验证 repair 是否能提升最终链质量

需要完成的任务：

- 接入已有 `chain_repair`
- 只对最终 top-1 调 repair
- 记录 repair 前后指标变化

### 阶段 4：增强版（后续可选）

可选方向：

- learned reranker
- LLM verifier
- retrieval-enhanced reranker
- 与 planner 联动

这一阶段不属于当前立刻开工内容。

## 8. 代码落点建议

建议新增一个正式模块，而不是把逻辑继续堆在 `interactive_system.py`。

### 建议新增文件

- `src/gis_recommend/reranking/reranker_verifier.py`
  - 放 verifier 特征提取
  - 放 reranker 打分逻辑
  - 放最终选择接口

- `src/gis_recommend/reranking/__init__.py`
  - 模块导出

### 建议修改文件

- `scripts/evaluate_system.py`
  - 改成保留多候选
  - 接入 reranker/verifier
  - 输出 oracle 指标和 rerank 后结果

- `src/gis_recommend/pipelines/interactive_system.py`
  - 可复用已有结构化评分逻辑
  - 但建议把通用逻辑抽走，不再让主评估依赖 interactive 分支

如有必要，可补充：

- `src/gis_recommend/inference/infer_l3_candidates_v4.py`
  - 如果需要更稳定地暴露 top-N 分数与候选元信息

## 9. 实验设计建议

建议按以下顺序做实验。

### 实验 1：当前 baseline

- `V4.6 + soft`

目的：

- 作为后续所有 reranker 实验的对照组

### 实验 2：Oracle 分析

- `V4.6 + soft + oracle@K`

目的：

- 判断候选池中是否已经存在更优解

### 实验 3：结构化 reranker V1

- `V4.6 + soft + structured reranker`

目的：

- 判断不训练新模型时，结构化打分能带来多大提升

### 实验 4：结构化 reranker + repair

- `V4.6 + soft + structured reranker + repair`

目的：

- 判断修复环节是否能进一步改善最终结果

## 10. 成功标准

本模块第一阶段成功的最低标准建议定义为：

- 相对当前 `V4.6 + soft` baseline
- `Set F1` 有稳定提升，或至少不下降
- `LCS` 有明显提升
- `Length Ratio` 更接近 1
- 最终有效链比例提升

如果只看到集合指标提升，但顺序与长度继续恶化，则说明 reranker 设计仍有问题。

## 11. 风险点

### 风险 1：候选池本身质量不足

如果 `top-N oracle` 都没有明显提升空间，那么 reranker 收益会有限。

对应结论：

- 下一步应更偏向 planner，而不是继续深挖 reranker

### 风险 2：GraphRAG / Neo4j 依赖过重

如果 verifier 强依赖图数据库，实验复现和服务器运行复杂度会升高。

对应策略：

- 第一版优先支持“轻量结构化 verifier”
- GraphRAG 作为增强项而不是硬依赖

### 风险 3：LLM 打分不稳定

如果一开始就接入 LLM scorer，会带来不稳定性和成本问题。

对应策略：

- 第一版禁止把 LLM scorer 作为主方案
- 只保留为后续增强项

## 12. 当前建议的最终执行顺序

接下来建议严格按以下顺序推进：

1. 打通 top-N L3 候选保留
2. 打通多 QGIS 候选池生成
3. 做 oracle analysis
4. 实现结构化 verifier
5. 实现结构化 reranker
6. 接入 top-1 repair
7. 跑完整对比实验

## 13. 当前一句话结论

`reranker / verifier` 第一版的核心不是“引入更强模型”，而是“把当前已经生成出来的多候选真正用起来”，先用结构化、可解释、可复现的方式验证：问题到底出在“不会生成”，还是“不会选”。 
