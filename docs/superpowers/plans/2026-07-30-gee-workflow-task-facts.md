# GEE Workflow Source-Backed Facts Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Convert the frozen 266 mapping-complete GEE workflows into deterministic source-backed fact bundles and chain-faithful task-text candidates.

**Architecture:** Add a pure fact-domain module that joins typed/fidelity/AST authority and extracts five evidence-bearing fact families. Add a small publisher CLI that renders fact-traceable text, partitions failures/duplicates/risks, and atomically writes reproducible artifacts without granting training admission.

**Tech Stack:** Python 3, ESTree JSON, existing GEE DAG/fidelity/typed modules, pytest, JSONL/hash ledgers.

---

### Task 1: Freeze the fact-domain contract

**Files:**
- Create: `tests/test_gee_workflow_task_facts.py`
- Create: `src/gis_recommend/data/gee_workflow_task_facts.py`

- [ ] Write failing tests for exact typed/fidelity joins, constructor-scoped dataset facts, literal and dynamic temporal facts, spatial fallbacks, ordered transformation facts, and Export output facts.
- [ ] Run `python -m pytest tests/test_gee_workflow_task_facts.py -q` and confirm failure because the module is absent.
- [ ] Implement immutable fact records and AST helpers with fail-closed validation.
- [ ] Re-run the focused tests and retain only source-backed values and explicit omissions.

### Task 2: Add fact-traceable task text and gates

**Files:**
- Modify: `tests/test_gee_workflow_task_facts.py`
- Modify: `src/gis_recommend/data/gee_workflow_task_facts.py`

- [ ] Add failing tests that every rendered clause cites existing fact IDs, private assets are redacted, dynamic regions use the source-defined fallback, and operator/L3 order cannot change.
- [ ] Implement conservative deterministic rendering and clause-level `used_fact_ids`.
- [ ] Add failing tests for normalized text plus L3-chain deduplication and long-chain risk routing.
- [ ] Implement dedup/risk decisions without granting training admission.

### Task 3: Build the atomic census publisher

**Files:**
- Create: `tests/test_build_gee_workflow_task_facts.py`
- Create: `scripts/build_gee_workflow_task_facts.py`

- [ ] Add a failing end-to-end fixture with repeated workflows in one source, one duplicate, one dynamic omission, and one invalid join.
- [ ] Implement input loading, one-to-one composite-key joins, source/AST hash verification, artifact partitioning, summary conservation, atomic publication, and hash ledger generation.
- [ ] Verify the fixture produces deterministic bytes across two output directories.

### Task 4: Replay the frozen 266 candidates

**Files:**
- Create: `docs/reports/gee_workflow_task_facts_500_pilot_2026-07-30.md`

- [ ] Sync only the new GEE code/tests to `/home/qy/system_redesign` while keeping `/home/yll` read-only.
- [ ] Run the publisher against the frozen typed, fidelity, AST, and source authority inputs twice.
- [ ] Compare every output artifact byte-for-byte and verify partition conservation.
- [ ] Record facts-complete, task-text candidate, duplicate, risk, and fail-closed counts without calling candidates training rows.

### Task 5: Update GEE-only durable state

**Files:**
- Modify: `docs/GEE_CURRENT_STATE.md`
- Modify: `docs/GEE_CURRENT_STATE.zh-CN.md`
- Modify: `docs/GEE_PROJECT_CONTEXT.md`
- Modify: `docs/GEE_PROJECT_CONTEXT.zh-CN.md`
- Modify: `task_plan.md` (GEE section only)
- Modify: `progress.md` only if the replay reaches a measured dataset gate

- [ ] Replace stale GEE next-step text with the verified counts, artifact authority, remaining risks, and immediate calibration action.
- [ ] Keep English/Chinese GEE context substantively aligned and leave QGIS/benchmark sections unchanged.
- [ ] Run focused tests, compile the new files, inspect the GEE-only diff, and report any environmental test gaps.

Implementation is inline in the current shared dirty worktree because the user explicitly prohibited worktree cleanup, commits, and unrelated git operations.
