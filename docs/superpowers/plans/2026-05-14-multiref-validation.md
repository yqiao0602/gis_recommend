# Multi-Reference Validation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build an evaluation-only MRV runner that validates whether current quality-gate data can support reliable multi-reference supervision.

**Architecture:** Add one focused script, `scripts/evaluate_multiref_validation.py`, with pure helper functions for variant generation, automatic validation, aggregation, and artifact writing. Add one focused test module covering labels, sensitive guards, registry output, review sampling, and the boundary that QGIS landing failures are auxiliary rather than primary MRV label blockers.

**Tech Stack:** Python standard library, existing `scripts.evaluate_workflow_usability`, existing `scripts.evaluate_canonicalized_metrics`, existing `L3ToPlatformMapper`.

---

### Task 1: Tests

**Files:**
- Create: `tests/test_multiref_validation_experiment.py`

- [ ] **Step 1: Write failing tests**

Tests cover adjacent-swap generation, sensitive guard rejection, strict auto-verification, and stratified review sample counts.

- [ ] **Step 2: Run tests and confirm failure**

Run: `python -m unittest tests.test_multiref_validation_experiment -v`

Expected: import failure because `scripts.evaluate_multiref_validation` does not exist yet.

### Task 2: MRV Script

**Files:**
- Create: `scripts/evaluate_multiref_validation.py`

- [ ] **Step 1: Implement data classes and pure helpers**

Implement `VariantRecord`, `ValidationDecision`, `is_sensitive_role`, `generate_adjacent_swap_variants`, `semantic_usable`, `strict_qgis_landing_usable`, `summarize_toolchain`, `validate_variant`, `build_human_review_sample`, and artifact writers.

- [ ] **Step 2: Run focused tests**

Run: `python -m unittest tests.test_multiref_validation_experiment -v`

Expected: all tests pass.

### Task 3: Smoke Run

**Files:**
- Runtime artifacts under `outputs_v2/v4_qg_multiref_validation/`

- [ ] **Step 1: Run a bounded smoke evaluation**

Run: `python scripts/evaluate_multiref_validation.py --max-workflows 50 --max-variants 100 --review-auto-verified 10 --review-plausible 5 --review-rejected 5`

Expected: JSON, Markdown, JSONL, and CSV artifacts are written.

### Task 4: Documentation

**Files:**
- Modify: `docs/PROJECT_CONTEXT.md`
- Modify: `docs/PROJECT_CONTEXT.zh-CN.md`

- [ ] **Step 1: Update project context**

Record that MRV Stage 1-2 plus human-review export was implemented, list artifacts and verification commands, and preserve the boundary that this is not multi-reference training.
