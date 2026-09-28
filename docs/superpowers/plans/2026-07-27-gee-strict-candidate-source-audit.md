# GEE Strict Candidate Source Audit Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build and execute a deterministic 60-row source-backed calibration audit over the 3,106-row GEE strict candidate package.

**Architecture:** A single focused audit module exposes independent sample-selection and source-replay functions. Formal execution first freezes the sample, then retrieves hash-bound sources, parses them with the existing Acorn parser, and writes non-admitting replay artifacts.

**Tech Stack:** Python 3.12, unittest, existing GEE ESTree extractor, Node/Acorn, OpenSSH SCP.

---

### Task 1: Lock deterministic selection and replay contracts

**Files:**
- Create: `tests/test_build_gee_strict_candidate_source_audit.py`

- [x] Write a selection test requiring 60 unique rows, all task types covered,
  stable repeated output, frozen sequences, and non-admission fields.
- [x] Write replay tests for exact match, changed chain, missing source, hash
  mismatch, AST failure, and fatal extractor quality flags.
- [x] Run `python -m unittest tests.test_build_gee_strict_candidate_source_audit -v`
  and verify RED because the audit module does not exist.

### Task 2: Implement the audit module

**Files:**
- Create: `scripts/build_gee_strict_candidate_source_audit.py`

- [x] Implement Windows-long-path-safe JSON/JSONL/hash/atomic-write helpers.
- [x] Implement deterministic 60-row selection with task-type-first coverage
  and diversity fill over chain length, operator family, source group, and
  chain-frequency class.
- [x] Implement hash-verified AST replay through
  `extract_gee_source_evidence`, sequence relationship classification, and
  fail-closed status assignment.
- [x] Implement CLI output for sample/retrieval/replay JSONL/CSV, summary,
  report, and hash ledger.
- [x] Run the new unit tests and keep implementation minimal until GREEN.

### Task 3: Materialize verified source and AST inputs

**Files:**
- Create temporary cache: `.tmp_gee_strict_candidate_audit_sources_20260727/`
- Create temporary cache: `.tmp_gee_strict_candidate_audit_ast_20260727/`

- [x] Generate the formal 60-row sample and retrieval manifest.
- [x] Fetch each recorded source path read-only with OpenSSH/SCP using the
  configured key-based server login.
- [x] Verify all 60 SHA256 values before parsing.
- [x] Parse all 60 sources with `scripts/parse_gee_js_with_locations.js` and
  fail closed on any parse error.

### Task 4: Generate formal source-backed artifacts

**Files:**
- Create: `docs/reports/gee_raster_core_v1_review_split_2026-07-24/gee_raster_core_batch_training_package_v1/strict_candidate_v1/source_audit_60_v1/`

- [x] Run the replay CLI against the verified source/AST caches.
- [x] Confirm 60 unique sample IDs/source hashes, complete source verification,
  explicit replay statuses, empty human fields, and zero emitted training rows.
- [x] Record one-sided zero-failure bound only if adjudication later observes
  zero failures; do not infer it from replay success alone.

### Task 5: Verify and update project memory

**Files:**
- Modify: `docs/CURRENT_STATE.md`
- Modify: `docs/CURRENT_STATE.zh-CN.md`
- Modify: `docs/PROJECT_CONTEXT.md`
- Modify: `docs/PROJECT_CONTEXT.zh-CN.md`
- Modify: `progress.md`
- Modify: `task_plan.md`

- [x] Run new tests, focused GEE regressions, Python compilation, structured
  artifact readback, source-package hash verification, and `git diff --check`.
- [x] Record measured replay counts and hashes without granting training,
  validation/test, or production admission.
