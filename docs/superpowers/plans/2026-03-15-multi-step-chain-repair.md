# Multi-Step Chain Repair Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将 Chain Repair 从单步修复增强为迭代多步修复，同时从编排器中解耦为独立模块。

**Architecture:** 新建 `knowledge_graph/chain_repair.py` 封装 `ChainRepairer` 类。迭代修复循环：找最严重问题 → 获取 I/O 预过滤后的替代算子 → LLM 选择 → deepcopy 替换 → 重新验证 → 回退保护。`interactive_system.py` 的 Stage 4c 从 ~85 行减少到 ~10 行。

**Tech Stack:** Python, Neo4j (neo4j driver), copy.deepcopy, JSON cache.

**Spec:** `docs/superpowers/specs/2026-03-14-multi-step-chain-repair-design.md`

---

## File Structure

| File | Action | Responsibility |
|------|--------|---------------|
| `src/gis_recommend/knowledge_graph/chain_repair.py` | Create | ChainRepairer 类：迭代多步修复逻辑 |
| `src/gis_recommend/pipelines/interactive_system.py` | Modify | Stage 4c 改为调用 ChainRepairer，删除 `_repair_chain()` |

---

## Task 1: 创建 ChainRepairer 骨架 + 辅助方法

**Files:**
- Create: `src/gis_recommend/knowledge_graph/chain_repair.py`

- [ ] **Step 1: 创建 ChainRepairer 类骨架**

```python
"""
chain_repair.py

迭代多步链修复器。

从编排器解耦的独立模块，负责修复 QGIS 候选链中的 I/O 不兼容步骤。
策略：找最严重问题 → I/O 预过滤替代算子 → LLM 选择 → deepcopy 替换 → 重新验证。
最多 max_rounds 轮，如修复后问题数未减少则回滚停止。
"""

import copy
from typing import List, Dict, Tuple, Optional


class ChainRepairer:
    """迭代多步链修复器。"""

    def __init__(self, retriever, validator, llm_scorer, io_types: dict):
        """
        Args:
            retriever: Neo4jGraphRAGRetriever 实例
            validator: ChainValidator 实例
            llm_scorer: LLMScorer 实例（可为 None）
            io_types: dict, 来自 qgis_operator_io_types.json 的预计算缓存。
                      格式: {"Slope": {"inputs": ["raster"], "outputs": ["raster"]}, ...}
                      已归一化为扁平字符串列表，可直接做 set() 交集运算。
        """
        self.retriever = retriever
        self.validator = validator
        self.llm_scorer = llm_scorer
        self.io_types = io_types

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
        repair_log = []
        old_issue_count = len(validation.issues)
        skipped_indices = set()  # 跳过的问题索引（无替代或选择失败）

        for round_num in range(1, max_rounds + 1):
            chain = list(candidate.qgis_sequence)

            # 1. 找最严重问题（跳过已知无法修复的）
            problem_idx, severity = self._find_worst_problem(
                validation, chain, skipped_indices
            )
            if problem_idx is None:
                break

            problem_op = chain[problem_idx]
            step = candidate.steps[problem_idx] if problem_idx < len(candidate.steps) else None

            # 2. 获取 I/O 预过滤后的替代算子
            prev_op = chain[problem_idx - 1] if problem_idx > 0 else None
            next_op = chain[problem_idx + 1] if problem_idx < len(chain) - 1 else None
            alternatives = self._get_alternatives(step, problem_op, prev_op, next_op)

            if not alternatives:
                repair_log.append({
                    "round": round_num, "problem_idx": problem_idx,
                    "old_op": problem_op, "new_op": None,
                    "action": "skipped", "reason": "no alternatives",
                })
                skipped_indices.add(problem_idx)
                continue  # 尝试次严重的问题

            # 3. LLM 选择或 fallback
            context = {
                "prev_operator": prev_op or "None",
                "next_operator": next_op or "None",
                "prev_l3": step.l3_code if step and hasattr(step, 'l3_code') else "Unknown",
                "user_query": user_query,
            }
            new_op = self._select_replacement(alternatives, context, user_query, step)

            if new_op is None:
                repair_log.append({
                    "round": round_num, "problem_idx": problem_idx,
                    "old_op": problem_op, "new_op": None,
                    "action": "skipped", "reason": "selection failed",
                })
                skipped_indices.add(problem_idx)
                continue  # 尝试次严重的问题

            # 4. deepcopy + 替换
            new_candidate = self._apply_repair(candidate, problem_idx, new_op)

            # 5. 重新验证
            new_validation = self.validator.validate_chain(new_candidate.qgis_sequence)
            new_issue_count = len(new_validation.issues)

            # 6. 回退保护
            if new_issue_count >= old_issue_count:
                repair_log.append({
                    "round": round_num, "problem_idx": problem_idx,
                    "old_op": problem_op, "new_op": new_op,
                    "severity": severity, "alternatives_count": len(alternatives),
                    "issues_before": old_issue_count, "issues_after": new_issue_count,
                    "action": "rollback", "reason": "no improvement",
                })
                break

            # 修复有效
            repair_log.append({
                "round": round_num, "problem_idx": problem_idx,
                "old_op": problem_op, "new_op": new_op,
                "severity": severity, "alternatives_count": len(alternatives),
                "issues_before": old_issue_count, "issues_after": new_issue_count,
            })
            candidate = new_candidate
            validation = new_validation
            old_issue_count = new_issue_count

        return candidate, validation, repair_log

    # ── 私有方法 ──────────────────────────────────────────

    def _compute_severity(self, detail, chain, idx, all_step_details):
        """
        计算单步不兼容的严重度。

        Returns:
            2: 前后两端都不兼容（完全孤立）
            1: 只有一端不兼容
            0: 兼容或 UNKNOWN 步骤

        step_details 索引语义（来自 chain_validator.py）：
          step_details[i].io_check 表示 chain[i] → chain[i+1] 的兼容性
        因此：
          chain[idx-1] → chain[idx] 的兼容性在 step_details[idx-1].io_check
          chain[idx] → chain[idx+1] 的兼容性在 step_details[idx].io_check
        """
        if chain[idx].startswith("UNKNOWN"):
            return 0

        # 前一步 → 当前步
        prev_incompatible = False
        if idx > 0:
            prev_detail = all_step_details[idx - 1]
            prev_io = prev_detail.get("io_check")
            if isinstance(prev_io, dict) and not prev_io.get("compatible", True):
                prev_incompatible = True

        # 当前步 → 后一步
        curr_incompatible = False
        curr_io = detail.get("io_check")
        if isinstance(curr_io, dict) and not curr_io.get("compatible", True):
            curr_incompatible = True

        if prev_incompatible and curr_incompatible:
            return 2
        elif prev_incompatible or curr_incompatible:
            return 1
        return 0

    def _find_worst_problem(self, validation, chain, skipped_indices=None):
        """返回 (problem_idx, severity) 或 (None, 0)。跳过 UNKNOWN 和已跳过的索引。"""
        skipped = skipped_indices or set()
        problems = []
        for detail in validation.step_details:
            idx = detail["index"]
            if idx in skipped:
                continue
            severity = self._compute_severity(detail, chain, idx, validation.step_details)
            if severity > 0:
                problems.append((idx, severity))
        if not problems:
            return None, 0
        problems.sort(key=lambda x: (-x[1], x[0]))
        return problems[0]

    def _fetch_raw_alternatives(self, step, problem_op):
        """从 GraphRAG 获取原始替代算子。来源：同 L3 映射 + 同 L2 族。"""
        alternatives = []
        # 来源1：同 L3 映射
        if step and hasattr(step, 'l3_code') and step.l3_code:
            l3_ops = self.retriever.get_operators_for_l3(step.l3_code, top_k=10)
            for op in l3_ops:
                if op["name"] != problem_op:
                    alternatives.append({
                        "operator_name": op["name"],
                        "confidence": op["confidence"],
                        "source": "same_l3",
                    })
        # 来源2：同 L2 族
        related = self.retriever.get_related_operators(problem_op, top_k=10)
        seen = {a["operator_name"] for a in alternatives}
        for r in related:
            if r["name"] != problem_op and r["name"] not in seen:
                alternatives.append({
                    "operator_name": r["name"],
                    "confidence": r["confidence"],
                    "source": "same_l2",
                })
        return alternatives

    def _get_alternatives(self, step, problem_op, prev_op, next_op):
        """获取 I/O 预过滤后的替代算子。"""
        raw = self._fetch_raw_alternatives(step, problem_op)
        filtered = []
        for alt in raw:
            alt_name = alt["operator_name"]
            alt_info = self.io_types.get(alt_name, {})
            alt_in = alt_info.get("inputs", [])
            alt_out = alt_info.get("outputs", [])

            prev_ok = True
            if prev_op:
                prev_out = self.io_types.get(prev_op, {}).get("outputs", [])
                if prev_out and alt_in:
                    prev_ok = bool(set(prev_out) & set(alt_in))

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

        # both > partial，然后按 confidence 降序
        filtered.sort(key=lambda a: (a["io_match"] == "both", a["confidence"]), reverse=True)
        return filtered

    def _select_replacement(self, alternatives, context, user_query, step):
        """LLM 选择最佳替代算子，或 fallback 到最高置信度。返回 str 或 None。"""
        if not alternatives:
            return None

        if self.llm_scorer:
            l3_code = step.l3_code if step and hasattr(step, 'l3_code') else "Unknown"
            constraints = {"platform": "QGIS", "position_type": "middle"}
            try:
                result = self.llm_scorer.score_candidates(
                    l3_code=l3_code,
                    unknown_type="repair",
                    candidates=alternatives[:10],
                    context=context,
                    constraints=constraints,
                )
                if result.selected_operator != "Unknown":
                    return result.selected_operator
            except Exception:
                pass

        # Fallback: 最高置信度
        return alternatives[0]["operator_name"]

    def _apply_repair(self, candidate, idx, new_op):
        """深拷贝 candidate 并替换指定位置算子。不修改原对象。"""
        new_cand = copy.deepcopy(candidate)
        new_chain = list(new_cand.qgis_sequence)
        new_chain[idx] = new_op
        new_cand.qgis_sequence = new_chain
        return new_cand
```

- [ ] **Step 2: 验证语法**

```bash
cd E:/02_projects/03_PythonProject/Operator-recommend-system/Algorithm_classification/system_redesign
python -c "import ast; ast.parse(open('src/gis_recommend/knowledge_graph/chain_repair.py', encoding='utf-8').read()); print('OK')"
```

Expected: `OK`

---

## Task 2: 修改 interactive_system.py — 集成 ChainRepairer

**Files:**
- Modify: `src/gis_recommend/pipelines/interactive_system.py:36` (add import), `:504-596` (replace Stage 4c)

- [ ] **Step 1: 添加 import**

在 `interactive_system.py` 的 import 区域（line 35 `from ...chain_validator import ChainValidator` 之后），添加：

```python
from gis_recommend.knowledge_graph.chain_repair import ChainRepairer
```

- [ ] **Step 2: 替换 Stage 4c 调用**

将 `interactive_system.py` 中 Stage 4c 部分（lines 504-507）：

```python
        # ── 4c. 链修复（如有问题）────────────────────────
        if best_validation.issues:
            print(f"\n  [4c] 链校验发现 {len(best_validation.issues)} 个问题，尝试修复...")
            best_cand = self._repair_chain(best_cand, best_validation, user_query)
```

替换为：

```python
        # ── 4c. 链修复（如有问题）────────────────────────
        if best_validation.issues:
            print(f"\n  [4c] 链校验发现 {len(best_validation.issues)} 个问题，尝试迭代修复...")
            repairer = ChainRepairer(
                retriever=self.graphrag_retriever,
                validator=self.chain_validator,
                llm_scorer=self.llm_scorer,
                io_types=self.qgis_generator.io_types,
            )
            best_cand, best_validation, repair_log = repairer.repair(
                best_cand, best_validation, user_query
            )
            for entry in repair_log:
                if entry.get("new_op"):
                    print(f"    轮次{entry['round']}: {entry['old_op']} -> {entry['new_op']} "
                          f"(严重度:{entry.get('severity','?')}, "
                          f"问题: {entry['issues_before']}->{entry['issues_after']})")
                elif entry.get("action") == "rollback":
                    print(f"    轮次{entry['round']}: 回滚 ({entry['reason']})")
                elif entry.get("action") == "skipped":
                    print(f"    轮次{entry['round']}: 跳过 ({entry['reason']})")
```

- [ ] **Step 3: 删除旧的 `_repair_chain()` 方法**

删除 `interactive_system.py` 中整个 `_repair_chain()` 方法（lines 511-596）。

- [ ] **Step 4: 验证语法**

```bash
cd E:/02_projects/03_PythonProject/Operator-recommend-system/Algorithm_classification/system_redesign
python -c "import ast; ast.parse(open('src/gis_recommend/pipelines/interactive_system.py', encoding='utf-8').read()); print('OK')"
```

Expected: `OK`

---

## Task 3: 端到端验证

**Files:**
- No file changes — verification only

- [ ] **Step 1: 运行 5 个标准测试用例**

```bash
cd E:/02_projects/03_PythonProject/Operator-recommend-system/Algorithm_classification/system_redesign
python -u << 'PYEOF'
import sys, json
sys.path.insert(0, 'src')
from gis_recommend.pipelines.interactive_system import InteractiveQGISSystem

system = InteractiveQGISSystem()
queries = [
    "Calculate terrain slope from DEM and classify slope categories",
    "Create buffer zones around rivers and intersect with buildings",
    "Calculate NDVI from satellite imagery and classify vegetation health",
    "Merge multiple vector layers and dissolve by attribute field",
    "Reproject raster data from WGS84 to UTM and clip to study area boundary",
]
for q in queries:
    r = system.process_user_query(q)
    if r['success']:
        print(f"\n{q[:55]}...")
        print(f"  QGIS: {' -> '.join(r['qgis_chain'][:5])}{'...' if len(r['qgis_chain']) > 5 else ''}")
        print(f"  Length: {len(r['qgis_chain'])}, Unknown: {r['unknown_count']}")
system.close()
PYEOF
```

Expected:
- 所有 5 个查询成功执行，无异常报错
- 有 I/O 问题的链应显示修复日志（"轮次N: X -> Y"）
- 向量任务（Buffer, Merge）链中栅格算子应减少
- DEM/NDVI 链保持栅格算子为主

- [ ] **Step 2: 验证修复日志输出**

重点关注控制台输出中的 `[4c]` 部分：
- 应该能看到多轮修复（如 "轮次1", "轮次2"）
- 回滚保护应在问题数未减少时触发
- 无替代算子时应显示"跳过"
