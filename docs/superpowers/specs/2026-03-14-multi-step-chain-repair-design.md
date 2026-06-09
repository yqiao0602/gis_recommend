# Multi-Step Chain Repair 设计

## 问题

当前 Chain Repair（Stage 4c）只修复链中第一个 I/O 不兼容的步骤。当链包含多个不兼容步骤时（如向量任务链混入 2-3 个栅格算子），一次修复不足以解决问题。

此外，现有修复逻辑内嵌在 `interactive_system.py`（~80 行），使编排器承担了过多职责。

## 方案

**独立模块 + 迭代修复**：

1. 新建 `knowledge_graph/chain_repair.py`，将修复逻辑从编排器中解耦
2. 迭代策略：修一步 → 重新验证 → 找下一个问题 → 再修，最多 `max_rounds` 轮
3. 每轮修复后用 `ChainValidator` 重新验证，保证状态一致性

## 数据流

```
interactive_system.py (Stage 4c)
    │
    │  repair(candidate, validation, user_query)
    ▼
ChainRepairer
    │
    │  Loop (max_rounds=3):
    │    1. _find_worst_problem(validation)     → problem_idx, severity
    │    2. _get_alternatives(step, problem_op)  → filtered alternatives
    │    3. _select_replacement(alternatives)     → new operator name (str) or None
    │    4. _apply_repair(candidate, idx, new_op) → new candidate (deepcopy)
    │    5. validator.validate_chain(new_cand.qgis_sequence) → new validation
    │    6. If issues_count increased → rollback, stop
    │
    │  Early exit conditions:
    │    - _get_alternatives returns [] → skip this step, try next worst
    │    - _select_replacement returns None → skip this step, try next worst
    │    - All problems skipped in one round → stop loop
    │    - No problems found → stop loop
    │
    │  Return: (repaired_candidate, final_validation, repair_log)
    ▼
interactive_system.py (continues with repaired result)
```

## 模块设计

### 新文件：`knowledge_graph/chain_repair.py`

**类 `ChainRepairer`**

构造函数注入所有依赖（不自己创建）：

```python
class ChainRepairer:
    def __init__(self, retriever, validator, llm_scorer, io_types: dict):
        self.retriever = retriever    # Neo4jGraphRAGRetriever
        self.validator = validator    # ChainValidator
        self.llm_scorer = llm_scorer  # LLMScorer (可选, None)
        self.io_types = io_types      # dict from qgis_operator_io_types.json
```

**`io_types` 数据格式**：来自 `outputs/qgis_operator_io_types.json` 的预计算缓存，已归一化为扁平字符串列表。格式为 `{"Slope": {"inputs": ["raster"], "outputs": ["raster"]}, ...}`。**不是** `neo4j_graphrag_retriever.get_operator_io_types()` 返回的嵌套 dict 格式。所有 `set()` 交集运算直接作用于 `List[str]`。

**公开方法**（唯一入口）：

```python
def repair(self, candidate, validation, user_query: str, max_rounds: int = 3):
    """
    迭代修复候选链中的 I/O 不兼容步骤。

    Args:
        candidate: QGISCandidate 对象
        validation: ChainValidationResult 对象
        user_query: 用户原始查询，传给 LLM 作为修复选择的上下文
        max_rounds: 最大修复轮次

    Returns:
        (repaired_candidate, final_validation, repair_log)
        repair_log: List[Dict] 每轮修复记录
    """
```

**私有方法**：

| 方法 | 职责 |
|------|------|
| `_find_worst_problem(validation, chain)` | 从 step_details 中按严重度排序选最差步骤，跳过 UNKNOWN 步骤 |
| `_get_alternatives(step, problem_op, prev_op, next_op)` | 两种来源(同L3+同L2) + I/O 预过滤 |
| `_fetch_raw_alternatives(step, problem_op)` | 从 GraphRAG 获取原始替代算子（同L3映射 + 同L2族） |
| `_select_replacement(alternatives, context, user_query)` | LLM 选择或 fallback 到最高置信度。返回 `str` (算子名) 或 `None` |
| `_apply_repair(candidate, idx, new_op)` | **深拷贝**链再替换（`copy.deepcopy`），返回新 candidate 对象 |
| `_compute_severity(detail, chain, idx, all_step_details)` | 计算单步不兼容的严重度 |

### 问题严重度排序

当前实现取"第一个"不兼容步骤，不考虑严重度。改为：

```python
def _compute_severity(self, detail, chain, idx, all_step_details):
    """
    严重度计算：
    - 2: 前后两端都不兼容（完全孤立）
    - 1: 只有一端不兼容
    - 0: 兼容或 UNKNOWN 步骤（不需要修复）

    注：UNKNOWN 步骤（算子名以 "UNKNOWN" 开头）不参与修复，severity=0。

    step_details 索引语义（来自 chain_validator.py）：
      step_details[i].io_check 表示 chain[i] → chain[i+1] 的兼容性
    因此：
      chain[idx-1] → chain[idx] 的兼容性在 step_details[idx-1].io_check
      chain[idx] → chain[idx+1] 的兼容性在 step_details[idx].io_check
    """
    # UNKNOWN 步骤不修复
    if chain[idx].startswith("UNKNOWN"):
        return 0

    # 检查前一步 → 当前步是否不兼容（即 step_details[idx-1].io_check）
    prev_incompatible = False
    if idx > 0:
        prev_detail = all_step_details[idx - 1]
        prev_io = prev_detail.get("io_check")
        if isinstance(prev_io, dict) and not prev_io.get("compatible", True):
            prev_incompatible = True

    if not prev_incompatible:
        # 前一步兼容，再检查当前步 → 后一步
        curr_io = detail.get("io_check")
        if isinstance(curr_io, dict) and not curr_io.get("compatible", True):
            return 1  # 只有后端不兼容
        return 0  # 两端都兼容

    # 前一步不兼容，检查当前步 → 后一步
    curr_io = detail.get("io_check")
    if isinstance(curr_io, dict) and not curr_io.get("compatible", True):
        return 2  # 前后两端都不兼容（完全孤立）

    return 1  # 只有前端不兼容
```

选严重度最高的步骤优先修复。同等严重度时，选位置靠前的。

注意：当 `chain[i]→chain[i+1]` 不兼容时，`_find_worst_problem` 不直接取发送端或接收端，而是对链中每个算子分别计算前后两端的严重度，选严重度最高的替换。这样能正确处理"一个栅格算子夹在两个向量算子之间"的场景（severity=2）。

```python
def _find_worst_problem(self, validation, chain):
    """返回 (problem_idx, severity) 或 (None, 0)。跳过 UNKNOWN。"""
    problems = []
    for detail in validation.step_details:
        idx = detail["index"]
        severity = self._compute_severity(detail, chain, idx, validation.step_details)
        if severity > 0:
            problems.append((idx, severity))
    if not problems:
        return None, 0
    # 按 severity 降序，同 severity 按 idx 升序
    problems.sort(key=lambda x: (-x[1], x[0]))
    return problems[0]
```

### I/O 预过滤替代算子

在送 LLM 评选之前，用 io_types 缓存过滤明显不兼容的替代：

```python
def _fetch_raw_alternatives(self, step, problem_op):
    """从 GraphRAG 获取原始替代算子。来源：同 L3 映射 + 同 L2 族。"""
    alternatives = []
    # 来源1：同 L3 映射的其他算子
    if hasattr(step, 'l3_code') and step.l3_code:
        l3_ops = self.retriever.get_operators_for_l3(step.l3_code, top_k=10)
        for op in l3_ops:
            if op["name"] != problem_op:
                alternatives.append({
                    "operator_name": op["name"],
                    "confidence": op["confidence"],
                    "source": "same_l3"
                })
    # 来源2：同族算子（同 L2 类别）
    related = self.retriever.get_related_operators(problem_op, top_k=10)
    seen = {a["operator_name"] for a in alternatives}
    for r in related:
        if r["name"] != problem_op and r["name"] not in seen:
            alternatives.append({
                "operator_name": r["name"],
                "confidence": r["confidence"],
                "source": "same_l2"
            })
    return alternatives

def _get_alternatives(self, step, problem_op, prev_op, next_op):
    # 1. 从 GraphRAG 获取候选（同 L3 + 同 L2）
    raw_alternatives = self._fetch_raw_alternatives(step, problem_op)

    # 2. I/O 预过滤：只保留与前后步骤至少一端兼容的替代
    filtered = []
    for alt in raw_alternatives:
        alt_name = alt["operator_name"]
        alt_info = self.io_types.get(alt_name, {})
        alt_in = alt_info.get("inputs", [])
        alt_out = alt_info.get("outputs", [])

        # 与前一步输出兼容？
        prev_ok = True
        if prev_op:
            prev_out = self.io_types.get(prev_op, {}).get("outputs", [])
            if prev_out and alt_in:
                prev_ok = bool(set(prev_out) & set(alt_in))

        # 与后一步输入兼容？
        next_ok = True
        if next_op:
            next_in = self.io_types.get(next_op, {}).get("inputs", [])
            if alt_out and next_in:
                next_ok = bool(set(alt_out) & set(next_in))

        if prev_ok and next_ok:
            alt["io_match"] = "both"
            filtered.append(alt)
        elif prev_ok or next_ok:
            alt["io_match"] = "partial"
            filtered.append(alt)
        # 两端都不兼容：丢弃

    # 排序：both > partial，然后按 confidence
    filtered.sort(key=lambda a: (a["io_match"] == "both", a["confidence"]), reverse=True)
    return filtered
```

### 回退保护

每轮修复后比较问题数量。注意：`validator.validate_chain()` 接受 `List[str]`，传入 `new_candidate.qgis_sequence`。

```python
import copy

def _apply_repair(self, candidate, idx, new_op):
    """深拷贝 candidate 并替换指定位置算子。不修改原对象。"""
    new_cand = copy.deepcopy(candidate)
    new_chain = list(new_cand.qgis_sequence)
    new_chain[idx] = new_op
    new_cand.qgis_sequence = new_chain
    return new_cand

# 在 repair() 循环中：
new_candidate = self._apply_repair(candidate, problem_idx, new_op)
new_validation = self.validator.validate_chain(new_candidate.qgis_sequence)
new_issue_count = len(new_validation.issues)

if new_issue_count >= old_issue_count:
    # 修复无效或更差 → 回滚，停止
    repair_log.append({"round": round_num, "action": "rollback", "reason": "no improvement"})
    break

# 修复有效 → 继续
candidate = new_candidate
validation = new_validation
old_issue_count = new_issue_count
```

### 修复日志

每轮记录修复操作，返回给编排器用于打印和调试：

```python
repair_log = [
    {
        "round": 1,
        "problem_idx": 2,
        "old_op": "Mosaic",
        "new_op": "Merge vector layers",
        "severity": 2,
        "alternatives_count": 5,
        "issues_before": 3,
        "issues_after": 1,
    },
    ...
]
```

## interactive_system.py 变更

### 删除

- `_repair_chain()` 方法（lines 511-596，~85 行）

### 修改

Stage 4c 简化为：

```python
# ── 4c. 链修复（如有问题）────────────────────────
if best_validation.issues:
    print(f"\n  [4c] 链校验发现 {len(best_validation.issues)} 个问题，尝试修复...")
    repairer = ChainRepairer(
        retriever=self.graphrag_retriever,
        validator=self.chain_validator,
        llm_scorer=self.llm_scorer,
        io_types=self.candidate_generator.io_types,
    )
    best_cand, best_validation, repair_log = repairer.repair(
        best_cand, best_validation, user_query
    )
    for entry in repair_log:
        if entry.get("new_op"):
            print(f"    轮次{entry['round']}: {entry['old_op']} -> {entry['new_op']} "
                  f"(问题: {entry['issues_before']}->{entry['issues_after']})")
```

注：`candidate_generator.io_types` 在 `__init__` 中由 `_load_io_types()` 设置，是稳定的公开属性。

### 新增 import

```python
from gis_recommend.knowledge_graph.chain_repair import ChainRepairer
```

## 不改动的部分

- `chain_validator.py`：纯验证，不添加修复逻辑
- `neo4j_graphrag_retriever.py`：纯数据查询，接口不变
- `llm_scorer.py`：`score_candidates()` 接口不变
- `qgis_candidate_generator.py`：`io_types` 属性被读取但不修改
- `rag_context_builder.py`：不参与修复

## 模块边界总结

| 模块 | 操作 | 职责变化 |
|------|------|---------|
| `interactive_system.py` | 修改（减少 ~80 行） | 更轻：只调用 `ChainRepairer.repair()` |
| `chain_repair.py` | 新建 | 单一职责：迭代修复链中的 I/O 不兼容问题 |
| `chain_validator.py` | 不变 | 纯验证（被 ChainRepairer 调用） |
| `neo4j_graphrag_retriever.py` | 不变 | 纯查询（被 ChainRepairer 调用） |
| `llm_scorer.py` | 不变 | 纯评分（被 ChainRepairer 调用） |
| `qgis_candidate_generator.py` | 不变 | io_types 共享读取 |

## 验证

1. 语法检查：`python -c "import ast; ast.parse(...)"`
2. 对 5 个标准测试用例运行端到端测试，比较修复前后：
   - 向量任务链中栅格算子数量应减少
   - DEM/NDVI 任务链应保持正确
   - 修复日志显示合理的替换操作
3. 边界情况：无问题的链（不触发修复）、无替代算子的步骤（跳过）、修复后更差（回滚）
