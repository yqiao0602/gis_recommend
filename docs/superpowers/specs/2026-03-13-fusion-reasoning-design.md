# Fusion Reasoning Design: LLM + GraphRAG Integration

## Problem

The current pipeline has all components implemented but the fusion layer is disconnected:
- **LLM Scorer**: initialized but never called in fusion reasoning
- **GraphRAG**: 10 query methods available, only 1 used (existence check)
- **RAG Context Builder**: only used in final QA, not in fusion scoring
- **Result**: fusion is just `beam_score + existence_check(+0.03/step) + validation(x0.2)`

## Goals

1. Wire up LLM Scorer and GraphRAG advanced queries in the fusion stage
2. Use multiple L3 candidates (top-3) instead of only the best one
3. Enable chain repair: GraphRAG provides alternatives, LLM selects
4. Keep output lightweight; detailed answers only on user follow-up
5. Preserve system value: LLM judges, never invents operators

## Architecture Constraints

- **LLM role**: score and select from existing candidates only. Never generate operator names.
- **GraphRAG role**: provide structured facts (operator info, I/O types, alternatives). All operator knowledge comes from the knowledge graph.
- **Repair constraint**: replacement operators must come from GraphRAG queries (same-L3 mappings or same-L2 family). LLM picks from the list.

## Data Flow

```
User Input
  |
[Stage 1] LLM Pipeline Phase 0-3              (unchanged)
  | task_type + model_input
[Stage 2] Transformer V4.2 -> top-3 L3        (change: use top-3 not top-1)
  | 3 L3 sequences
[Stage 3] Each L3 -> QGIS chains (beam=5)     (unchanged)
  | up to 15 candidates (deduplicated)
[Stage 4] Fusion Reasoning                     (REWRITE)
  |-- 4a. GraphRAG structural scoring (all candidates)
  |-- 4b. RAG context + LLM scoring (top-3 only)
  |-- 4c. Chain repair (top-1, if issues found)
  | final best chain
[Stage 5] Lightweight output                   (change: summary only)
  | chain + one-line-per-step summary
[Interactive Loop] User follow-up
  | RAG + LLM on-demand answers
```

## Stage 4 Detailed Design

### 4a. GraphRAG Structural Scoring

For each candidate chain, compute three scores using existing methods:

1. **Known ratio**: `get_operator_info()` for each operator -> count found / total steps
2. **I/O compatibility**: `check_chain_io_compatibility(op_i, op_{i+1})` for adjacent pairs -> compatible pairs / (total - 1)
3. **Chain validation**: `chain_validator.validate_chain()` -> validation.confidence

Combined structural score:
```
structural_score = beam_score * 0.4 + known_ratio * 0.2 + io_score * 0.2 + validation_score * 0.2
```

This step is pure computation, no LLM calls.

### 4b. RAG + LLM Scoring (top-3 only)

For each of the top-3 candidates by structural score:

1. Build RAG context: `rag_builder.build_chain_context(chain)`
2. Call LLM scorer with prompt containing:
   - User task description
   - RAG context (operator descriptions, data flow analysis)
   - The candidate chain
3. LLM returns: score (0-10) + reasoning

Final ranking combines structural and LLM scores:
```
final_score = structural_score * 0.5 + llm_score / 10 * 0.5
```

LLM is called at most 3 times in this step.

### 4c. Chain Repair (top-1 only, if needed)

After selecting the best chain, check `validation.issues`:

- If no issues: skip repair, proceed to output.
- If issues found at specific steps:
  1. GraphRAG finds alternatives:
     - `get_operators_for_l3(step.l3_code)` - same L3 mapping
     - `get_related_operators(step.operator)` - same L2 family
  2. LLM selects from alternatives:
     - `llm_scorer.score_candidates(l3_code, candidates, context)`
     - Context includes previous/next operator info
  3. Replace the problematic step

LLM called at most once for repair (only the worst issue).

### Total LLM calls: max 4 (3 scoring + 1 repair)

## Stage 5 Output

Lightweight: LLM generates a brief summary of the chain.

Format:
```
针对您的任务 "XXX"，推荐以下 QGIS 工作流：
1. Warp — 投影转换
2. Slope — 计算坡度
3. Raster Calculator — 坡度重分类
如有疑问请继续提问。
```

No pre-generated detailed explanations. Details are provided on-demand via follow-up.

## Interactive Follow-up Loop

User asks a question -> system responds using RAG + LLM:

1. Extract operator name from question (if mentioned)
2. `rag_builder.build_qa_context(question, operator_name, chain)`
3. `qa_system.answer_with_rag(question, operator_name, chain)`
4. Return answer, wait for next question

Loop continues until user is done. Already implemented in `ask_followup()`.

## Code Changes

### File: `src/gis_recommend/pipelines/interactive_system.py`

| Method | Action | Description |
|--------|--------|-------------|
| `process_user_query()` | Modify | Stage 2: take top-3 L3 candidates. Stage 3: generate QGIS chains for each, deduplicate. |
| `_select_best_chain_with_graphrag()` | Rewrite | Implement 4a + 4b + 4c as described above. |
| `_repair_chain_step()` | New | GraphRAG finds alternatives, LLM selects replacement. |
| `_generate_explanations()` | Simplify | Only generate chain summary, not per-operator details. |

### Unchanged modules

- `llm_pipeline.py` (Stage 1)
- `infer_l3_candidates_v4.py` (Stage 2 model)
- `qgis_candidate_generator.py` (Stage 3)
- `neo4j_graphrag_retriever.py` (called, not modified)
- `rag_context_builder.py` (called, not modified)
- `chain_validator.py` (called, not modified)
- `llm_scorer.py` (called, not modified)
- `qgis_operator_qa.py` (called for follow-up, not modified)

## Verification

Test with 3 scenarios after implementation:

1. **DEM slope analysis**: expect Slope operator ranked first, no irrelevant operators
2. **Land cover classification**: expect classification operators present in chain
3. **Buffer analysis**: expect Buffer vectors in chain, proper I/O flow

For each: compare fusion-enhanced result vs current baseline.
