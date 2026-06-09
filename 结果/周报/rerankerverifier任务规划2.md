# Reranker / Verifier 模块任务规划

## 1. 目标

当前系统 beam search 后直接取 top-1，丢弃了其余 9 条候选。本模块的目标是：

1. **先做 Oracle Analysis**：验证 top-N 中是否存在更好的候选
2. **构建 Reranker**：对 top-N 候选做全局打分，选出真正最优
3. **接入 Verifier**：对最终候选做结构验证 + 修复

## 2. 当前可复用资源

| 模块 | 文件 | 复用度 | 说明 |
|------|------|--------|------|
| 结构化评分 | `interactive_system.py:461-466` | 100% | confidence×0.4 + known_ratio×0.2 + io_score×0.2 + validation×0.2 |
| 链校验 | `chain_validator.py` | 100% | 存在性 + I/O 兼容性检查 |
| LLM 打分 | `llm_scorer.py:score_chain()` | 100% | 0-10 分制，含 RAG 上下文 |
| RAG 上下文 | `rag_context_builder.py` | 100% | 构建算子链的知识图谱上下文 |
| 链修复 | `chain_repair.py` | 95% | 迭代修复最严重的 I/O 问题 |
| Neo4j 检索 | `neo4j_graphrag_retriever.py` | 100% | I/O 兼容性、算子信息、关联算子 |
| 评估指标 | `semantic_metrics.py` | 100% | Set F1、LCS、Token Accuracy 等 |

**关键数字**：当前 beam search 返回 **10 条候选**（V4_RETURN_TOP_N=10），但 evaluate_system.py 只取 `candidates[0]`。

## 3. 执行步骤

### Step 0: Oracle Analysis（前置实验，1 天）

**目的**：回答"top-N 里有没有更好的候选"

**做法**：改 evaluate_system.py，对 beam search 返回的 top-10 每一条都计算 Set F1，取最优值作为 oracle。

**输出**：
```
top-1 Set F1:     49.23%  （当前）
top-3 oracle F1:  ??%
top-5 oracle F1:  ??%
top-10 oracle F1: ??%
```

**决策**：
- oracle gap > 5% → reranker 价值大，继续 Step 1-3
- oracle gap < 2% → 问题在生成端，应转向 P2 骨架规划

**实现**：新建 `scripts/oracle_analysis.py`
- 加载 V4.6 checkpoint
- 对测试集每个样本生成 top-10 候选
- 对每条候选独立计算 Set F1
- 输出 top-1 / top-3 oracle / top-5 oracle / top-10 oracle

### Step 1: L3 级 Reranker（2-3 天）

**在 QGIS 映射之前，先对 L3 候选做重排序。**

当前 `_score_and_rank()` 只用 4 个特征（log_prob, transition, length, diversity）。L3 Reranker 增加：

- **set predictor 一致性**：候选 token 集合与 set predictor 预测集合的重叠度
- **L2 类别覆盖**：候选是否覆盖了任务所需的 L2 类别
- **语义连贯性**：相邻 L3 token 的语义相似度（用已有的 L3 embeddings）

**实现**：
- 新建 `src/gis_recommend/reranker/__init__.py`
- 新建 `src/gis_recommend/reranker/l3_reranker.py`
- 核心类 `L3Reranker`，接收 top-N L3Candidate，输出重排序后的列表

**评估**：对比 rerank 前后的 top-1 Set F1

### Step 2: QGIS 链级 Reranker（2-3 天）

**对映射后的 QGIS 链做全局打分。**

复用 `interactive_system.py` 的 4a/4b 逻辑，但正式化为独立模块：

```
输入：多条 QGIS 候选链 + 用户任务描述
  ↓
Layer 1: 结构化评分（无需 Neo4j 的快速筛选）
  - known_ratio、unknown_count、链长度
  ↓
Layer 2: GraphRAG 评分（需要 Neo4j）
  - I/O 兼容性、算子存在性
  ↓
Layer 3: LLM 评分（可选，成本高）
  - 只对 top-3 做 LLM 打分
  ↓
输出：排序后的候选 + 最优链
```

**实现**：
- 新建 `src/gis_recommend/reranker/chain_reranker.py`
- 核心类 `QGISChainReranker`
- 支持三层评分的开关（`use_graphrag=True, use_llm=False`）

### Step 3: Verifier + Repair（1-2 天）

**对 reranker 选出的最优链做验证和修复。**

直接复用 `chain_validator.py` + `chain_repair.py`：

```
最优 QGIS 链
  ↓
ChainValidator.validate_chain() → issues
  ↓
如果有 issues → ChainRepairer.repair() → 修复后的链
  ↓
最终输出
```

**实现**：
- 不需要新建文件，直接在 reranker 流程中调用
- 在 evaluate_system.py 中接入完整链路

### Step 4: 接入评估主线（1 天）

改造 `scripts/evaluate_system.py`：

```python
# 当前
candidates = inferencer.infer(..., mode="beam")
pred_tokens = candidates[0].tokens  # top-1

# 改后
candidates = inferencer.infer(..., mode="beam")  # top-10
reranked = l3_reranker.rerank(candidates, context)  # L3 重排序
pred_tokens = reranked[0].tokens  # rerank 后的 top-1
```

新增 `--use-reranker` 开关，方便 A/B 对比。

## 4. 不需要 Neo4j 的最小版本

如果服务器没有 Neo4j，Step 2 的 Layer 2/3 可以跳过，只用 Layer 1（结构化评分）。

Step 1（L3 Reranker）完全不依赖 Neo4j，只需要：
- L3 embeddings（已有）
- Set Predictor（已有）
- Transition matrix（已有）

**建议先做 Step 0 + Step 1，不需要 Neo4j 就能验证 reranker 效果。**

## 5. 预期收益

| 阶段 | 预期 Set F1 提升 | 依赖 |
|------|-----------------|------|
| Step 0 (oracle) | 0（诊断性实验） | 无 |
| Step 1 (L3 rerank) | +1-3% | L3 embeddings + Set Predictor |
| Step 2 (QGIS rerank) | +2-5% | Neo4j |
| Step 3 (verify+repair) | +1-2% | Neo4j + LLM |

## 6. 文件清单

| 文件 | 类型 | 描述 |
|------|------|------|
| `scripts/oracle_analysis.py` | 新建 | Oracle 分析脚本 |
| `src/gis_recommend/reranker/__init__.py` | 新建 | 模块初始化 |
| `src/gis_recommend/reranker/l3_reranker.py` | 新建 | L3 序列重排序 |
| `src/gis_recommend/reranker/chain_reranker.py` | 新建 | QGIS 链重排序 |
| `scripts/evaluate_system.py` | 修改 | 接入 reranker + --use-reranker 开关 |

## 7. 时间线

```
Day 1:     Oracle Analysis → 决定是否继续
Day 2-3:   L3 Reranker 实现 + 评估
Day 4-5:   QGIS Chain Reranker（如果有 Neo4j）
Day 6:     Verifier + Repair 接入
Day 7:     评估主线接入 + A/B 对比报告
```
