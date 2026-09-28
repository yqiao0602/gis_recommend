# GEE Extractor v2 P0-A Function Bindings Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Recover source-provable GEE calls inside variable-bound and static object-property helpers while preserving fail-closed recursion and current classification behavior.

**Architecture:** Extend the existing `_Extractor.functions` registry instead of introducing a JavaScript interpreter. Register non-hoisted bindings while visiting declarations/assignments, reuse `_flatten_callee()` for static dotted names, and route block versus expression function bodies through the existing statement/expression visitors.

**Tech Stack:** Python 3.12, ESTree-compatible dictionaries, unittest/pytest.

---

### Task 1: Lock missing bindings with RED tests

**Files:**
- Modify: `tests/test_gee_source_extractor.py`

- [x] Add a fixture for static assignment expressions.
- [x] Add focused tests for variable `FunctionExpression` direct calls, variable arrow direct calls, variable callback use, object-literal property calls, property assignment calls, nested variable/object helper calls, and recursive variable helpers.
- [x] Run:

  ```powershell
  $env:PYTHONPATH='.;src'
  rtk proxy D:\01_software\02_DevelopmentKits\Python\Anaconda3\python.exe -m pytest tests/test_gee_source_extractor.py -q
  ```

  Expected: the new direct/callback/nested tests fail because helper names are emitted as unresolved/core or omitted; the recursive-variable test must not pass accidentally through existing `FunctionDeclaration` handling.

### Task 2: Register source-provable function bindings

**Files:**
- Modify: `src/gis_recommend/data/gee_source_extractor.py`

- [x] Add a small registry method that preserves the first binding and flags duplicate definitions.
- [x] Reuse it from `_register_functions()` for existing `FunctionDeclaration` nodes.
- [x] In `VariableDeclaration`, register Identifier-bound function expressions and static function-valued object properties before continuing traversal; do not traverse a registered function body as an immediately executed expression.
- [x] In expression traversal, register static `AssignmentExpression` function bindings such as `helpers.mask = function (...) {...}` without executing the function body.
- [x] Keep computed properties, destructuring and non-function values outside the registry.

### Task 3: Expand direct and named callback bodies safely

**Files:**
- Modify: `src/gis_recommend/data/gee_source_extractor.py`

- [x] Route helper block bodies through `_visit_statement()` and arrow expression bodies through `_visit_expression()`.
- [x] Generalize named control callback lookup from Identifier-only to any static name returned by `_static_binding_name()`, including `helpers.mask`.
- [x] Preserve the existing `active_helpers` recursion check and unresolved evidence contract for direct and callback recursion.
- [x] Re-run the focused extractor test and verify all cases pass.

### Task 4: Run local regression gates

**Files:**
- No data files modified.

- [x] Run the full Extractor v2 test set and confirm all tests pass.
- [x] Run replay tests and the P0/legacy/provenance regression set recorded in current project context.
- [x] Run `python -m compileall` on changed modules/tests.
- [x] Run `rtk git diff --check` and inspect the scoped diff.

### Task 5: Perform isolated server before/after verification

**Files:**
- Create under `/home/qy/system_redesign/diagnostics/gee_extractor_v2_pilot_20260722/`: a P0-A code snapshot and independent before/after artifacts.
- Do not modify: `/home/yll/**`, original `review.csv`, `outputs/**`, `outputs_v2/**`.

- [x] Copy only the final extractor code required by the existing isolated pipeline.
- [x] Rebuild evidence for `script_203101`, `script_210697`, `script_217558`, `script_48309`, `script_179599`, plus positive regression `script_4142` from existing location-bearing ASTs; no all-186 rerun was performed.
- [x] Compare ordered calls and core/I/O/presentation layers against the frozen pre-fix evidence.
- [x] Publish a separate machine-readable and Markdown before/after report. Do not populate human-gold fields.
- [x] Stop after the six-record rerun because recovered helpers passed and `script_4142` did not regress.

### Task 6: Update durable project memory

**Files:**
- Modify: `docs/CURRENT_STATE.md`
- Modify: `docs/CURRENT_STATE.zh-CN.md`
- Modify: `docs/PROJECT_CONTEXT.md`
- Modify: `docs/PROJECT_CONTEXT.zh-CN.md`
- Modify on measured milestone: `progress.md`
- Modify when gates/next order change: `task_plan.md`

- [x] Record exact local test counts, server sample deltas, artifact paths/hashes, limitations and remaining P0-B UI/native classification work.
- [x] Keep English and Chinese handoffs substantively aligned.
- [x] Preserve `training_admission=not_granted` and state that P0-A evidence is diagnostic, not human gold.
