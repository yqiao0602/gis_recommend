# GEE Pipeline P0-C Auxiliary Context Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Preserve real `ee.Number.*`, `ee.Date.*`, and `ee.List.*` operations while filtering only exact auxiliary constructors in Step2 and Step8.

**Architecture:** Centralize the existing constructor names in one deterministic exact-match policy. Both legacy cleaning stages call the same policy so their behavior cannot drift.

**Tech Stack:** Python 3.12, unittest/pytest, existing legacy GEE pipeline modules.

---

### Task 1: Lock the defect with RED tests

**Files:**
- Create: `tests/test_gee_auxiliary_operator_policy.py`

- [x] Test that Step2 and Step8 retain `ee.Number.add`, `ee.Date.advance`, and `ee.List.sequence`.
- [x] Test that both stages still identify exact `ee.Number`, `ee.Date`, and `ee.List` constructors as auxiliary.
- [x] Test that native `Number.parseInt`, native `Date.getFullYear`, and unknown `decisionTree.join` are not claimed as auxiliary.
- [x] Add an integration assertion that `clean_workflow()` drops exact constructors but preserves real method operations.
- [x] Run the focused tests and confirm the method-path assertions fail on the old implementation.

### Task 2: Implement the exact-constructor policy

**Files:**
- Create: `src/gis_recommend/data/gee_operator_policy.py`
- Modify: `src/gis_recommend/legacy/gee_pipeline/step2_clean_workflows.py`
- Modify: `src/gis_recommend/legacy/gee_pipeline/enhanced_sequence_cleaner_final.py`

- [x] Define the closed exact three-constructor set and reject non-string/special-token inputs.
- [x] Replace Step2's Number/Date/List prefix matching with the shared exact-match policy while preserving its other historical categories.
- [x] Replace Step8's Number/Date/List category matching with the shared exact-match policy while preserving its other historical categories.
- [x] Run the focused tests and confirm all pass.

### Task 3: Verify compatibility and record evidence

**Files:**
- Modify: `docs/CURRENT_STATE.md`
- Modify: `docs/CURRENT_STATE.zh-CN.md`
- Modify: `docs/PROJECT_CONTEXT.md`
- Modify: `docs/PROJECT_CONTEXT.zh-CN.md`
- Modify: `progress.md`
- Modify: `task_plan.md`

- [x] Run focused GEE, legacy compatibility, P0, and provenance tests.
- [x] Run compileall and scoped `git diff --check`.
- [x] Record exact test counts and the no-regeneration/no-training boundary.
