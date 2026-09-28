# QGIS Stable-98 Impact Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Generate a non-admitted stable-98 extension draft and measure its record-level and unique-chain impact without modifying production authorities.

**Architecture:** A standalone deterministic CLI reads the frozen P0 adjudications and current hierarchy/crosswalk/dataset authorities. Pure functions validate and build the four-L3 extension, apply the nine-operator delta in memory, and compare baseline/alias/stable98 chain completeness before writing report-only artifacts.

**Tech Stack:** Python standard library, JSON/JSONL/CSV, pytest-compatible tests.

---

### Task 1: Lock taxonomy-extension behavior

**Files:**
- Create: `tests/test_build_qgis_stable98_draft.py`
- Create: `scripts/build_qgis_stable98_draft.py`

- [x] Write a failing test proving existing token IDs remain unchanged and restored codes append contiguously.
- [x] Run the focused test and confirm failure because the builder module does not exist.
- [x] Implement hierarchy/vocabulary validation and extension proposal construction.
- [x] Run the focused test and confirm it passes.

### Task 2: Lock three-stage impact behavior

**Files:**
- Modify: `tests/test_build_qgis_stable98_draft.py`
- Modify: `scripts/build_qgis_stable98_draft.py`

- [x] Write failing tests for baseline, alias-only, stable98 completion, unique-chain deduplication, and remaining blockers.
- [x] Run the focused tests and confirm expected failures.
- [x] Implement mapping-delta construction and deterministic impact comparison.
- [x] Run the focused tests and confirm they pass.

### Task 3: Generate and verify real-data artifacts

**Files:**
- Create: `docs/reports/qgis_mapping_coverage_audit_2026-07-23/stable98_extension_proposal_v1.json`
- Create: `docs/reports/qgis_mapping_coverage_audit_2026-07-23/qgis_mapping_authority_stable98_delta_draft_v1.json`
- Create: `docs/reports/qgis_mapping_coverage_audit_2026-07-23/p0_mapping_impact_stable98_v1.json`
- Create: `docs/reports/qgis_mapping_coverage_audit_2026-07-23/p0_mapping_impact_records_v1.jsonl`

- [x] Run the CLI against frozen authorities.
- [x] Verify nine mapped operators, four proposed L3 codes, unchanged IDs 0-93, frozen admissions, record counts, unique-chain counts, and artifact hashes.
- [x] Run focused tests, `py_compile`, JSON/JSONL parsing, and `git diff --check`.

### Task 4: Update durable project state

**Files:**
- Modify: `docs/CURRENT_STATE.md`
- Modify: `docs/CURRENT_STATE.zh-CN.md`
- Modify: `docs/PROJECT_CONTEXT.md`
- Modify: `docs/PROJECT_CONTEXT.zh-CN.md`
- Modify: `progress.md`
- Modify: `task_plan.md`

- [x] Record measured impact with record and unique-chain denominators kept separate.
- [x] Keep stable-98, taxonomy admission, training admission, expansion, and training explicitly frozen.
