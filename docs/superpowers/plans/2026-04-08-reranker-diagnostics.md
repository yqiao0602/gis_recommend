# Reranker Diagnostics Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add reranker diagnostics to evaluation so each run reveals whether gains are limited by candidate-pool diversity or reranker selection quality.

**Architecture:** Extend `scripts/evaluate_system.py` to keep the baseline top-1 prediction alongside reranked output, compute per-sample delta metrics, summarize changed/improved/degraded counts and candidate-pool diversity, and store the diagnostic block in the report JSON. Reuse existing `SeqMetrics` so diagnostic math matches the current evaluation metric definitions.

**Tech Stack:** Python, `unittest`

---

### Task 1: Add Failing Tests For Diagnostic Summary

**Files:**
- Modify: `tests/test_reranker_evaluate_system.py`
- Test: `tests/test_reranker_evaluate_system.py`

- [ ] **Step 1: Write the failing tests**

```python
def test_summarize_reranker_diagnostics_counts_improvements_and_pool_stats():
    ...

def test_build_report_json_includes_reranker_diagnostics():
    ...
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m unittest tests.test_reranker_evaluate_system -v`
Expected: FAIL because diagnostic helpers/fields do not exist yet.

- [ ] **Step 3: Write minimal implementation**

```python
def summarize_reranker_diagnostics(...):
    ...
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m unittest tests.test_reranker_evaluate_system -v`
Expected: PASS

### Task 2: Wire Diagnostics Into Evaluation And Report

**Files:**
- Modify: `scripts/evaluate_system.py`
- Test: `tests/test_reranker_evaluate_system.py`

- [ ] **Step 1: Preserve baseline prediction before reranking**

```python
l3_res["baseline_pred_tokens"] = list(pred_tokens)
```

- [ ] **Step 2: Compute diagnostics after reranking**

```python
reranker_diagnostics = summarize_reranker_diagnostics(...)
```

- [ ] **Step 3: Print concise diagnostic summary**

```python
print_reranker_diagnostics(reranker_diagnostics)
```

- [ ] **Step 4: Store diagnostics in report JSON**

```python
report["reranker_diagnostics"] = reranker_diagnostics
```

- [ ] **Step 5: Run targeted tests**

Run: `python -m unittest tests.test_reranker_evaluate_system -v`
Expected: PASS

- [ ] **Step 6: Run syntax verification**

Run: `python -m py_compile scripts/evaluate_system.py`
Expected: exit code 0
