# GEE Extractor v2 Pilot Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a versioned ESTree evidence extractor that recovers callback/helper calls and a deterministic source-disjoint review-pack builder without changing formal training data.

**Architecture:** Keep the legacy server extractor immutable and implement a local pure-Python AST evidence layer. The extractor emits ordered, source-grounded call records and derives core/I/O/presentation/support/unresolved views without taxonomy mapping. A separate review-pack module deduplicates records by source SHA256, stratifies them deterministically, and publishes review-only artifacts.

**Tech Stack:** Python 3.12, ESTree JSON, dataclasses/typed dictionaries, CSV/JSONL, SHA256, unittest/pytest.

---

### Task 1: Freeze the evidence schema

**Files:**
- Create: `src/gis_recommend/data/gee_source_evidence.py`
- Create: `tests/test_gee_source_evidence.py`

- [x] Write failing tests asserting that schema construction rejects a missing SHA256, duplicate ordinals, an unknown classification, and a layer reference not present in `ordered_calls`.
- [x] Run `python -m unittest tests.test_gee_source_evidence -v`; verify failures are caused by the missing module/API.
- [x] Implement `CallEvidence`, `GeeSourceEvidence`, classification constants, `validate_evidence()`, and `to_dict()` with schema `gis_recommend.gee_source_evidence.v1`.
- [x] Re-run the focused tests and verify all pass.

### Task 2: Recover ordered callback and helper evidence

**Files:**
- Create: `src/gis_recommend/data/gee_source_extractor.py`
- Create: `tests/test_gee_source_extractor.py`

- [x] Write failing tests using small ESTree fixtures for direct chains, `FunctionExpression` callbacks, `ArrowFunctionExpression` callbacks, callback-local declarations, directly invoked `FunctionDeclaration` helpers, nested helpers, repeated calls, recursive helpers, branches, loops, Export/UI, and dynamic callees.
- [x] Run `python -m unittest tests.test_gee_source_extractor -v`; verify each new behavior fails before implementation.
- [x] Implement `extract_gee_source_evidence(ast, *, source_path, source_sha256)` with deterministic statement traversal, call-chain receiver ordering, callback traversal, bounded helper inlining, source locations, context tags, classification, resolution, and quality flags.
- [x] Keep constructors/control containers in `support_calls`; keep dynamic/recursive/unordered evidence in `unresolved_calls`; never synthesize an `ee.image.*` name.
- [x] Re-run focused schema/extractor tests and verify all pass.

### Task 3: Build a source-disjoint review pack

**Files:**
- Create: `src/gis_recommend/data/gee_review_pack.py`
- Create: `scripts/build_gee_review_pack.py`
- Create: `tests/test_gee_review_pack.py`

- [x] Write failing tests for SHA256 grouping, deterministic canonical-path selection, fixed-seed-free strata ordering, insufficient-stratum reporting, conflicting record IDs, blank human fields, and byte-identical reruns.
- [x] Run `python -m unittest tests.test_gee_review_pack -v`; verify the missing API is the failure cause.
- [x] Implement `build_review_selection()` and atomic JSONL/CSV/summary/hash-ledger writers. Inputs are manifest records pointing to source, AST, optional legacy operations, and v2 evidence.
- [x] Implement CLI validation that rejects output paths under declared forbidden roots and verifies source bytes against declared SHA256 before selection.
- [x] Re-run review-pack and combined focused tests.

### Task 4: Run bounded real-data validation

**Files:**
- Create on server only: `/home/qy/system_redesign/diagnostics/gee_extractor_v2_pilot_20260722/`
- Modify after measurement: `docs/reports/gee_extractor_v2_pilot_2026-07-22.md`

- [x] Copy versioned extractor code to the isolated `/home/qy` diagnostic workspace; do not modify `/home/yll`.
- [x] Select source-disjoint examples from the replay manifest for every available stratum, including known `script_4142` and direct-chain controls.
- [x] Generate AST with the existing Node parser, run legacy and v2 extraction separately, and publish source/evidence/review/summary/hash artifacts.
- [ ] Manually adjudicate enough rows to measure core-call precision/recall and order. Stop expansion if recall <95%, precision <98%, or order <95%.

### Task 5: Verify and update durable context

**Files:**
- Modify: `docs/CURRENT_STATE.md`
- Modify: `docs/CURRENT_STATE.zh-CN.md`
- Modify: `docs/PROJECT_CONTEXT.md`
- Modify: `docs/PROJECT_CONTEXT.zh-CN.md`
- Modify only on measured milestone: `progress.md`
- Modify when gates change: `task_plan.md`

- [x] Run all new focused tests plus GEE P0/legacy/provenance regression tests.
- [x] Run `python -m compileall` for new modules/scripts and `git diff --check`.
- [x] Record measured counts, failures, hashes, changed files, commands, and remaining risks; keep English/Chinese context substantively aligned.
- [x] Keep GEE training admission frozen unless a later explicitly approved gate changes it.
