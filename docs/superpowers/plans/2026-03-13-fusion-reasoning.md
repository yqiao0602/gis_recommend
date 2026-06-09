# Fusion Reasoning Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Wire up LLM Scorer and GraphRAG in the fusion stage so candidate chains are scored with knowledge-graph context and repaired when issues are found.

**Architecture:** Only `interactive_system.py` is rewritten (fusion methods). One small addition to `llm_scorer.py` (chain-level scoring method). All other modules are called, not modified.

**Tech Stack:** Python, Neo4j (via neo4j driver), OpenAI-compatible API (DashScope qwen-plus), existing GraphRAG/RAG modules.

**Spec:** `docs/superpowers/specs/2026-03-13-fusion-reasoning-design.md`

---

## File Structure

| File | Action | Responsibility |
|------|--------|---------------|
| `src/gis_recommend/llm/llm_scorer.py` | Add method | `score_chain()` — LLM scores an entire QGIS chain against a user task |
| `src/gis_recommend/pipelines/interactive_system.py` | Rewrite methods | Fusion reasoning: multi-L3, GraphRAG scoring, LLM scoring, chain repair, lightweight output |

---

## Task 1: Add `score_chain()` to LLM Scorer

**Files:**
- Modify: `src/gis_recommend/llm/llm_scorer.py` (add method after `score_candidates`, ~line 354)

- [ ] **Step 1: Add `score_chain()` method**

Insert after the existing `score_candidates()` method (line 354):

```python
def score_chain(
    self,
    user_task: str,
    qgis_chain: list,
    rag_context: str,
) -> dict:
    """
    Use LLM to score an entire QGIS operator chain against a user task.

    Args:
        user_task: User's natural language task description
        qgis_chain: List of QGIS operator names
        rag_context: Structured context from RAGContextBuilder.build_chain_context()

    Returns:
        {"score": float 0-10, "reasoning": str}
    """
    chain_text = " -> ".join(qgis_chain)
    prompt = f"""You are a GIS workflow evaluation expert.

## User Task
{user_task}

## Candidate QGIS Operator Chain
{chain_text}

## Knowledge Graph Context
{rag_context}

## Instructions
Evaluate how well this operator chain accomplishes the user's task.
Consider:
1. Does the chain contain the essential operations for this task?
2. Is the operator ordering logical (data flows correctly)?
3. Are there redundant or irrelevant operators?
4. Are there missing critical steps?

Respond in JSON:
{{
    "score": <0-10, where 10 is perfect>,
    "reasoning": "<2-3 sentences explaining your evaluation>"
}}
"""
    response = self._call_llm_api(prompt)
    score = response.get("score", 5.0)
    if isinstance(score, str):
        try:
            score = float(score)
        except ValueError:
            score = 5.0
    reasoning = response.get("reasoning", "No reasoning provided")
    return {"score": min(max(score, 0.0), 10.0), "reasoning": reasoning}
```

- [ ] **Step 2: Verify import works**

Run:
```bash
cd E:/02_projects/03_PythonProject/Operator-recommend-system/Algorithm_classification/system_redesign
python -c "import sys; sys.path.insert(0,'src'); from gis_recommend.llm.llm_scorer import LLMScorer; s = LLMScorer(use_mock=True); print(hasattr(s, 'score_chain'))"
```
Expected: `True`

---

## Task 2: Modify `process_user_query()` to use top-3 L3 candidates

**Files:**
- Modify: `src/gis_recommend/pipelines/interactive_system.py:186-210`

- [ ] **Step 1: Change Stage 2 to use top-3 L3 and generate QGIS chains for each**

Replace the current Stage 2 + Stage 3 section (lines 186-210) with:

```python
        # 阶段2：生成L3序列（取 top-3 候选）
        print("\n" + "-"*70)
        print("阶段2：Transformer模型 - 生成L3原语序列")
        print("-"*70)

        l3_sequences = self._generate_l3_sequences(
            task_desc=user_query,
            task_type=task_type,
            task_name=task_info.get("task_name", user_query[:30]),
            model_input=task_info.get("model_input"),
            num_candidates=3
        )

        if not l3_sequences:
            return {"success": False, "error": "L3序列生成失败"}

        print(f"\n共生成 {len(l3_sequences)} 条L3候选序列")

        # 阶段3：对每条L3候选生成QGIS链，汇总去重
        print("\n" + "-"*70)
        print("阶段3：Beam Search - 生成QGIS算子链候选")
        print("-"*70)

        all_qgis_candidates = []
        seen_chains = set()
        for i, l3_seq in enumerate(l3_sequences):
            print(f"\n  L3候选 {i+1}/{len(l3_sequences)}:")
            candidates = self._generate_qgis_candidates(l3_seq, num_candidates=5)
            for cand in candidates:
                chain_key = tuple(cand.qgis_sequence)
                if chain_key not in seen_chains:
                    seen_chains.add(chain_key)
                    all_qgis_candidates.append(cand)

        if not all_qgis_candidates:
            return {"success": False, "error": "QGIS链生成失败"}

        print(f"\n汇总去重后共 {len(all_qgis_candidates)} 条候选链")

        # 阶段4：融合推理
        print("\n" + "-"*70)
        print("阶段4：GraphRAG + LLM - 融合推理选出最佳链")
        print("-"*70)

        best_chain, validation_result = self._select_best_chain_with_graphrag(
            all_qgis_candidates,
            user_query,
            l3_sequences[0]  # 传最佳L3序列作为参考
        )
```

Also update the result dict to use `l3_sequences[0]` for the `l3_sequence` field (keep existing behavior for downstream).

- [ ] **Step 2: Verify syntax**

Run:
```bash
python -c "import sys; sys.path.insert(0,'src'); import ast; ast.parse(open('src/gis_recommend/pipelines/interactive_system.py').read()); print('OK')"
```
Expected: `OK`

---

## Task 3: Rewrite `_select_best_chain_with_graphrag()`

**Files:**
- Modify: `src/gis_recommend/pipelines/interactive_system.py` — replace method body (lines 394-455)

- [ ] **Step 1: Replace the method with the new fusion logic**

```python
    def _select_best_chain_with_graphrag(
        self,
        candidates: List[Any],
        user_query: str,
        l3_sequence: List[str]
    ) -> Tuple[Any, Any]:
        """
        融合推理：GraphRAG结构化评分 → RAG+LLM打分 → 链修复

        4a. GraphRAG 结构化评分（所有候选链）
        4b. RAG + LLM 打分（top-3）
        4c. 链修复（top-1，如有问题）
        """
        from gis_recommend.knowledge_graph.chain_validator import ChainValidationResult

        if not self.graphrag_retriever or not self.chain_validator:
            print("  [INFO] GraphRAG未启用，使用默认评分")
            return candidates[0], ChainValidationResult(is_valid=True, confidence=0.5)

        # ── 4a. GraphRAG 结构化评分（所有候选链）──────────────
        print("\n  [4a] GraphRAG 结构化评分...")
        scored = []
        for cand in candidates:
            chain = cand.qgis_sequence
            total = len(chain)
            if total == 0:
                continue

            # 算子存在性
            known = 0
            for op in chain:
                if op.startswith("UNKNOWN"):
                    continue
                if self.graphrag_retriever.get_operator_info(op):
                    known += 1
            non_unk = sum(1 for op in chain if not op.startswith("UNKNOWN"))
            known_ratio = known / non_unk if non_unk > 0 else 0.0

            # I/O 兼容性
            compat_pairs = 0
            check_pairs = 0
            for i in range(total - 1):
                a, b = chain[i], chain[i + 1]
                if a.startswith("UNKNOWN") or b.startswith("UNKNOWN"):
                    continue
                check_pairs += 1
                result = self.graphrag_retriever.check_chain_io_compatibility(a, b)
                if result["compatible"]:
                    compat_pairs += 1
            io_score = compat_pairs / check_pairs if check_pairs > 0 else 0.5

            # 链校验
            validation = self.chain_validator.validate_chain(chain)

            structural = (
                cand.score * 0.4
                + known_ratio * 0.2
                + io_score * 0.2
                + validation.confidence * 0.2
            )
            scored.append((structural, cand, validation))

        scored.sort(key=lambda x: x[0], reverse=True)

        for i, (s, c, v) in enumerate(scored[:3]):
            print(f"    候选 {i+1}: structural={s:.4f} "
                  f"(beam={c.score:.3f}, known={len([o for o in c.qgis_sequence if not o.startswith('UNKNOWN')])}/"
                  f"{len(c.qgis_sequence)}, issues={len(v.issues)})")

        # ── 4b. RAG + LLM 打分（top-3）───────────────────
        top3 = scored[:3]
        if self.llm_scorer and self.rag_builder:
            print("\n  [4b] RAG + LLM 打分 (top-3)...")
            llm_scored = []
            for structural_score, cand, validation in top3:
                try:
                    rag_ctx = self.rag_builder.build_chain_context(cand.qgis_sequence)
                    llm_result = self.llm_scorer.score_chain(
                        user_task=user_query,
                        qgis_chain=cand.qgis_sequence,
                        rag_context=rag_ctx,
                    )
                    llm_s = llm_result["score"]  # 0-10
                    final = structural_score * 0.5 + (llm_s / 10.0) * 0.5
                    print(f"    LLM score={llm_s:.1f}, final={final:.4f}: {llm_result['reasoning'][:80]}")
                except Exception as e:
                    print(f"    [WARNING] LLM打分失败: {e}")
                    final = structural_score
                llm_scored.append((final, cand, validation))
            llm_scored.sort(key=lambda x: x[0], reverse=True)
            best_score, best_cand, best_validation = llm_scored[0]
        else:
            print("\n  [4b] LLM未启用，使用结构化评分")
            best_score, best_cand, best_validation = top3[0]

        print(f"\n  [OK] 选出最佳链 (final={best_score:.4f})")

        # ── 4c. 链修复（如有问题）────────────────────────
        if best_validation.issues:
            print(f"\n  [4c] 链校验发现 {len(best_validation.issues)} 个问题，尝试修复...")
            best_cand = self._repair_chain(best_cand, best_validation, user_query)

        return best_cand, best_validation
```

- [ ] **Step 2: Verify syntax**

Run same syntax check as Task 2 Step 2.

---

## Task 4: Add `_repair_chain()` method

**Files:**
- Modify: `src/gis_recommend/pipelines/interactive_system.py` — add new method after `_select_best_chain_with_graphrag`

- [ ] **Step 1: Add the repair method**

```python
    def _repair_chain(self, candidate, validation, user_query: str):
        """
        修复候选链中校验失败的步骤。
        GraphRAG 提供替代算子 → LLM 从中选择。
        只修复最严重的 1 个问题。
        """
        if not validation.step_details or not self.graphrag_retriever:
            return candidate

        # 找到第一个有 I/O 不兼容问题的步骤
        problem_idx = None
        for detail in validation.step_details:
            io_check = detail.get("io_check")
            if isinstance(io_check, dict) and not io_check.get("compatible", True):
                problem_idx = detail["index"]
                break

        if problem_idx is None:
            return candidate

        chain = list(candidate.qgis_sequence)
        problem_op = chain[problem_idx]
        print(f"    修复步骤 {problem_idx + 1}: {problem_op}")

        # GraphRAG 找替代算子
        alternatives = []
        # 方式1：同 L3 映射的其他算子
        step = candidate.steps[problem_idx]
        if hasattr(step, 'l3_code') and step.l3_code:
            l3_ops = self.graphrag_retriever.get_operators_for_l3(step.l3_code, top_k=10)
            for op in l3_ops:
                if op["name"] != problem_op:
                    alternatives.append({
                        "operator_name": op["name"],
                        "confidence": op["confidence"],
                        "source": "same_l3"
                    })

        # 方式2：同族算子（同 L2 类别）
        related = self.graphrag_retriever.get_related_operators(problem_op, top_k=10)
        for r in related:
            if r["name"] != problem_op and r["name"] not in [a["operator_name"] for a in alternatives]:
                alternatives.append({
                    "operator_name": r["name"],
                    "confidence": r["confidence"],
                    "source": "same_l2"
                })

        if not alternatives:
            print(f"    未找到替代算子，保持原样")
            return candidate

        print(f"    找到 {len(alternatives)} 个替代候选")

        # LLM 从替代中选择
        if self.llm_scorer:
            prev_op = chain[problem_idx - 1] if problem_idx > 0 else "None"
            next_op = chain[problem_idx + 1] if problem_idx < len(chain) - 1 else "None"
            context = {
                "prev_operator": prev_op,
                "next_operator": next_op,
                "prev_l3": step.l3_code if hasattr(step, 'l3_code') else "Unknown",
                "next_l3": "Unknown",
            }
            constraints = {"platform": "QGIS", "position_type": "middle"}

            result = self.llm_scorer.score_candidates(
                l3_code=step.l3_code if hasattr(step, 'l3_code') else "Unknown",
                unknown_type="repair",
                candidates=alternatives[:10],
                context=context,
                constraints=constraints,
            )

            if result.selected_operator != "Unknown":
                chain[problem_idx] = result.selected_operator
                print(f"    替换: {problem_op} -> {result.selected_operator} ({result.reasoning[:60]})")
                candidate.qgis_sequence = chain
        else:
            # 无 LLM 时选第一个替代
            chain[problem_idx] = alternatives[0]["operator_name"]
            candidate.qgis_sequence = chain

        return candidate
```

- [ ] **Step 2: Verify syntax**

Run same syntax check.

---

## Task 5: Simplify `_generate_explanations()`

**Files:**
- Modify: `src/gis_recommend/pipelines/interactive_system.py:457-498` — replace method body

- [ ] **Step 1: Replace with lightweight summary**

```python
    def _generate_explanations(
        self,
        qgis_chain: List[str],
        user_query: str
    ) -> Dict[str, str]:
        """生成轻量链概述（不预生成每个算子的详细解释）"""
        if not self.qa_system:
            return {}

        try:
            print("\n  生成算子链概述...")
            chain_explanation = self.qa_system.explain_operator_chain(qgis_chain)
            print("  [OK] 概述已生成")
            return {"chain_overview": chain_explanation}
        except Exception as e:
            print(f"  [WARNING] 概述生成失败: {e}")
            return {}
```

---

## Task 6: End-to-end verification

- [ ] **Step 1: Run DEM slope analysis test**

```bash
cd E:/02_projects/03_PythonProject/Operator-recommend-system/Algorithm_classification/system_redesign
python -c "
import sys; sys.path.insert(0, 'src')
from gis_recommend.pipelines.interactive_system import InteractiveQGISSystem
system = InteractiveQGISSystem()
result = system.process_user_query('Calculate terrain slope from DEM and classify slope categories')
if result['success']:
    print('\n=== RESULT ===')
    for i, op in enumerate(result['qgis_chain'], 1):
        print(f'  {i}. {op}')
    print(f'Score: {result[\"score\"]:.4f}, Unknown: {result[\"unknown_count\"]}')
system.close()
"
```

Expected:
- Chain contains `Slope` operator
- 0 unknowns
- LLM scoring output visible in logs (4b step)

- [ ] **Step 2: Run buffer analysis test**

```bash
python -c "
import sys; sys.path.insert(0, 'src')
from gis_recommend.pipelines.interactive_system import InteractiveQGISSystem
system = InteractiveQGISSystem()
result = system.process_user_query('Create buffer zones around rivers and intersect with buildings')
if result['success']:
    print('\n=== RESULT ===')
    for i, op in enumerate(result['qgis_chain'], 1):
        print(f'  {i}. {op}')
system.close()
"
```

Expected:
- Chain contains `Buffer vectors`
- Fusion logs show 4a/4b/4c stages
