# GEE Extractor v2 P0-B Native JavaScript Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remove only statically provable standard JavaScript namespace calls from the GEE core layer while preserving unknown receiver calls.

**Architecture:** Add a small namespace allowlist beside the existing classifier constants. The classifier returns the existing `support` layer with a new `native_js_namespace` resolution and `native_js_call` flag; no schema classification or traversal interface changes are needed.

**Tech Stack:** Python 3.12, ESTree dictionaries, unittest/pytest.

---

### Task 1: Add RED classification tests

**Files:**
- Modify: `tests/test_gee_source_extractor.py`

- [x] Add a standard namespace test covering `Math.pow`, `Object.keys`, `Date.getFullYear`, and `JSON.parse`.
- [x] Assert all four calls are ordered, placed in `support_calls`, and carry `native_js_namespace`/`native_js_call`.
- [x] Add an unknown receiver assertion for `decisionTree.join` and preserve a GEE `image.select` call as core.
- [x] Run the extractor test and confirm the new standard namespace assertions fail before implementation.

### Task 2: Implement the deterministic allowlist branch

**Files:**
- Modify: `src/gis_recommend/data/gee_source_extractor.py`

- [x] Add the conservative `_NATIVE_JS_NAMESPACES` set.
- [x] Add the native namespace branch after presentation/I/O checks and before constructors/control/core dotted fallback.
- [x] Return `support`, `native_js_namespace`, and `native_js_call` for allowlisted dotted roots.
- [x] Leave unknown dotted receivers as `core`, `receiver_untyped`, `untyped_receiver`.

### Task 3: Run regression gates

**Files:**
- No data files modified.

- [x] Run the complete Extractor v2 test set and confirm all pass.
- [x] Run replay 14-test and P0/legacy/provenance 48-test suites.
- [x] Run compileall and scoped `git diff --check`.

### Task 4: Record P0-B evidence

**Files:**
- Modify: `docs/CURRENT_STATE.md`
- Modify: `docs/CURRENT_STATE.zh-CN.md`
- Modify: `docs/PROJECT_CONTEXT.md`
- Modify: `docs/PROJECT_CONTEXT.zh-CN.md`
- Modify: `progress.md`
- Modify: `task_plan.md`

- [x] Record exact test counts, classifier scope, known residual unknown receivers, and training admission status.
- [x] Keep P0-B separate from P0-A and do not claim overall precision/recall without human adjudication.
