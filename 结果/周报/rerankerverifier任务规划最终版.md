# reranker / verifier 最终执行方案

## 1. 当前目标

当前阶段的唯一目标不是继续调 `threshold`，也不是同时启动多个新模块，而是：

`在保留 V4.6 + 默认 soft baseline 不变的前提下，验证并提升“多候选选优”能力。`

也就是说，本模块要回答两个问题：

1. 当前候选池里是否已经存在更好的候选，只是没有被选中
2. 如果存在，能否用结构化、可解释、可复现的方式把它选出来

## 2. 为什么现在先做 reranker / verifier

当前主评估链路的问题很明确：

- L3 阶段只取 beam `top-1`
- QGIS 阶段只取候选链 `top-1`
- 已有的结构校验、GraphRAG、repair 逻辑没有正式接入主评估主线

因此，当前系统更像是：

`会生成候选，但不会系统性地比较候选`

所以现在最应该先补的是：

- `verifier`：看懂候选好不好
- `reranker`：从候选池里选出更优解

而不是立刻去做 planner。

## 3. 最终原则

合并两版规划后，最终执行原则如下：

- 第一版先做 `Oracle Analysis`
- 第一版优先做 `QGIS chain` 级 rerank，不优先做 `L3 rerank`
- 第一版只做 `结构化 verifier + 结构化 reranker + 可选 repair`
- 第一版不依赖 `LLM scorer`
- 第一版不把 `Neo4j / GraphRAG` 作为硬依赖
- `L3 reranker`、`GraphRAG 深度打分`、`LLM scorer` 作为后续增强项，而不是首版核心

## 4. 模块边界

### 4.1 本轮要解决的问题

- 保留 L3 多候选
- 扩展为 QGIS 多候选池
- 对 QGIS 候选链提取结构化特征
- 对候选链做排序
- 对最终 top-1 做验证
- 必要时做修复
- 输出中间分数与排序结果，便于分析

### 4.2 本轮不解决的问题

- 不训练新的大模型/小模型作为 reranker
- 不立刻引入学习式排序模型
- 不同时推进 planner
- 不把 LLM 打分放进第一版主链路

## 5. 模块定位

建议把本模块正式拆成两个逻辑组件。

### 5.1 Verifier

职责：

- 对候选链做结构检查
- 提取结构化特征
- 输出问题诊断信息

它负责“看懂候选”，不负责最终排序。

### 5.2 Reranker

职责：

- 接收候选链及 verifier 特征
- 计算统一综合得分
- 输出排序后的候选列表
- 选出最终 top-1

它负责“选候选”，不负责生成候选。

## 6. 候选粒度的最终决定

最终决定：

- 第一版主排序对象是 `QGIS chain`
- 不是单独做 `L3 sequence` rerank

原因：

- 最终系统目标是工作流推荐，而不是单独优化 L3 排序
- QGIS 候选层有更丰富的结构信息
- unknown、I/O 合法性、链可执行性、repair 都在链级别才有意义

所以本轮数据流定义为：

`自然语言 -> V4.6 生成 top-N L3 候选 -> 每条 L3 生成 top-M QGIS 候选 -> verifier 提取特征 -> reranker 排序 -> top-1 验证 -> 可选 repair -> 最终输出`

## 7. 候选池设计

### 7.1 当前事实

当前 V4.6 推理器默认返回的候选数不是 `10`，而是配置中的 `V4_RETURN_TOP_N`，目前代码默认是 `5`。

因此，第一版不要预设“固定 top-10”，而应做成：

- 当前默认先基于 `top-5`
- 如有需要，再扩成 `top-10`

### 7.2 第一版建议

- L3 top-N：先用当前默认 `5`
- 每条 L3 生成 QGIS top-M：建议 `3`
- 候选池规模：约 `5 x 3 = 15` 条，去重后进入 reranker

这样做的原因：

- 候选池足够大，能做 oracle 和 rerank
- 计算量仍然可控
- 不需要一上来把搜索空间放太大

## 8. Oracle Analysis 的最终方案

Oracle Analysis 必须先做，而且必须比原草案更完整。

### 8.1 目的

回答：

- `top-N` 里是否已经有更好的候选
- 问题更偏向“不会生成”还是“不会选”

### 8.2 不足之处修正

Oracle 不能只看 `Set F1`，还必须至少同时看：

- `Set F1`
- `LCS`
- `Length Ratio`
- 如可行，再看链级合法性/有效率

原因：

- 只看 `Set F1` 容易把“集合更像但顺序更差”的候选误判为更优

### 8.3 第一版 Oracle 设计

对每个样本：

- 保留 L3 top-N 候选
- 每条候选都计算相对于真值的 `Set F1 / LCS / Length Ratio`
- 统计：
  - top-1 实际结果
  - oracle@3
  - oracle@5
  - 如后续扩候选，再统计 oracle@10

如果后续接入 QGIS 候选池，可进一步统计：

- QGIS chain oracle@K
- 最优合法链比例

### 8.4 决策口径

- 如果 oracle gap 明显，说明 reranker 很值
- 如果 oracle gap 很小，说明更应该转向 planner

这里不建议把阈值写死成 `2%` 或 `5%`，而应结合多指标一起看。

## 9. 第一版结构化特征

第一版只保留最可靠、最容易落地的特征。

### 9.1 来自 L3 生成器的特征

- L3 候选原始 `final_score`
- L3 长度
- 与任务类型期望长度的偏差
- 与 set predictor 的集合一致性
- 高置信 must-have token 是否覆盖

### 9.2 来自 QGIS 候选生成器的特征

- `candidate.score`
- `candidate.confidence`
- `unknown_count`
- `unknown_ratio`
- `has_critical_unknown`

### 9.3 来自 verifier 的特征

- known operator ratio
- I/O compatibility ratio
- validation confidence
- validation issue count
- 是否存在严重结构问题

### 9.4 当前不进入第一版核心评分的特征

- 相邻 L3 token embedding 相似度
- LLM 打分
- 复杂 retrieval 分数

这些可以研究，但不进入第一版核心链路。

## 10. 第一版评分函数

第一版不做学习模型，先做可解释的加权结构分。

建议形式：

`final_score = w1 * l3_score + w2 * qgis_score + w3 * set_overlap + w4 * io_score + w5 * validation_confidence - w6 * unknown_penalty - w7 * issue_penalty - w8 * length_penalty`

第一版要求：

- 所有分项可打印
- 所有分项可追踪
- 所有权重人工设定
- 先跑实验验证方向，再决定是否需要 learned reranker

## 11. Repair 的定位

Repair 不是 reranker 的前置步骤，而是后置补救步骤。

第一版策略：

- 只对最终 top-1 调用 repair
- 不对候选池中所有链做 repair

触发条件建议：

- validation issue count > 0
- 或 unknown_ratio 高于阈值
- 或存在关键位置 unknown

这样可以控制运行成本，并保持实验解释清晰。

## 12. 是否依赖 Neo4j / GraphRAG

最终决定：

- 第一版不把 Neo4j / GraphRAG 作为硬依赖
- 第一版默认先支持轻量结构化 verifier
- GraphRAG 作为增强层接入

也就是说，第一版可以分两档：

### 12.1 轻量版

不依赖 Neo4j，仅依赖：

- L3 候选分数
- QGIS 候选分数
- unknown 信息
- 基础结构校验
- set predictor 一致性

### 12.2 增强版

在轻量版基础上再加入：

- GraphRAG I/O 兼容性
- operator existence
- 更强的 verifier 特征

### 12.3 LLM scorer

LLM scorer 只保留为后续增强项，不进入第一版主方案。

## 13. 分阶段实施方案

### 阶段 1：打通候选池 + Oracle Analysis

目标：

- 保留 L3 多候选
- 生成 QGIS 候选池
- 输出 oracle 指标

本阶段产出：

- Oracle 报告
- 候选池数据结构
- 对“生成不到 / 选不好”的初步判断

### 阶段 2：结构化 verifier V1

目标：

- 为每条 QGIS 候选提取结构化特征
- 形成统一特征字典

本阶段产出：

- verifier 特征接口
- 候选诊断日志

### 阶段 3：结构化 reranker V1

目标：

- 基于 verifier 特征做正式重排
- 替换当前直接取 top-1 的逻辑

本阶段产出：

- rerank 后排序结果
- 分项得分日志
- 与 baseline 的 A/B 对比

### 阶段 4：top-1 repair

目标：

- 对最终 top-1 做修复
- 判断 repair 是否带来净收益

本阶段产出：

- repair 前后结果对比

### 阶段 5：后续增强项

后续再考虑：

- L3 reranker
- GraphRAG 深度打分
- LLM verifier / LLM scorer
- learned reranker
- 与 planner 联动

## 14. 代码落点最终建议

建议新增正式模块，而不是继续把逻辑堆在 `interactive_system.py`。

### 建议新增文件

- `src/gis_recommend/reranking/__init__.py`
- `src/gis_recommend/reranking/reranker_verifier.py`

其中 `reranker_verifier.py` 负责：

- verifier 特征提取
- reranker 打分逻辑
- 最终 top-1 选择接口

### 建议修改文件

- `scripts/evaluate_system.py`
  - 保留多候选
  - 输出 oracle 指标
  - 接入 reranker/verifier
  - 增加开关，支持 baseline / oracle / rerank / repair 对比

- `src/gis_recommend/inference/infer_l3_candidates_v4.py`
  - 如有必要，补充稳定暴露 top-N 候选元信息

- `src/gis_recommend/pipelines/interactive_system.py`
  - 复用其现有结构化评分思路
  - 但通用逻辑应抽出，不继续把主评估依赖在 interactive 分支上

### 关于单独的 oracle 脚本

第一版不强制新建独立 `oracle_analysis.py`。

更建议先在 `evaluate_system.py` 中通过开关支持：

- `--oracle-only`
- `--use-reranker`
- `--use-repair`

等流程稳定后，再考虑拆独立脚本。

## 15. 实验方案

建议按以下顺序做实验。

### 实验 1：baseline

- `V4.6 + soft`

作用：

- 作为当前固定对照组

### 实验 2：oracle

- `V4.6 + soft + oracle@K`

作用：

- 判断候选池中是否已有更优解

### 实验 3：结构化 verifier + reranker

- `V4.6 + soft + structured reranker`

作用：

- 验证不引入新模型时，结构化打分是否有效

### 实验 4：结构化 verifier + reranker + repair

- `V4.6 + soft + structured reranker + repair`

作用：

- 验证 repair 是否进一步提升最终结果

### 实验 5：增强版（后续）

- `+ GraphRAG`
- `+ LLM scorer`
- `+ L3 reranker`

这些不属于第一阶段必须完成的内容。

## 16. 成功标准

第一版成功的最低标准定义为：

- 相对当前 `V4.6 + soft` baseline
- `Set F1` 稳定提升，或至少不下降
- `LCS` 有明显提升
- `Length Ratio` 更接近 `1`
- 最终有效链比例提升

如果只看到集合指标提升，但顺序和长度继续恶化，则说明 reranker 方向仍有问题。

## 17. 风险与对应策略

### 风险 1：候选池质量不足

表现：

- oracle gap 很小

对应：

- 说明问题更偏向生成端
- 后续应更偏向 planner

### 风险 2：第一版依赖太重

表现：

- 强依赖 Neo4j / GraphRAG / LLM，导致实现慢、复现难

对应：

- 第一版坚持轻量结构化方案
- 增强项后置

### 风险 3：特征设计过多

表现：

- 第一版评分函数过于复杂，难以解释

对应：

- 只保留最可靠的特征
- 先求稳定，再求复杂

## 18. 最终执行顺序

接下来严格按以下顺序推进：

1. 在 `evaluate_system.py` 中打通多候选保留
2. 输出 oracle 指标
3. 打通 QGIS 候选池
4. 实现结构化 verifier
5. 实现结构化 reranker
6. 接入 top-1 repair
7. 跑完整 A/B 对比实验

## 19. 最终一句话结论

`reranker / verifier` 第一版的核心，不是“再引入一个更强模型”，而是“把当前已经生成出来的多候选真正用起来”，先用结构化、可解释、可复现的方式判断：问题究竟出在“不会生成”，还是“不会选”。  
