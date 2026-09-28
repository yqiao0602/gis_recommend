# QGIS Dedup-Aware 50-Row Review Pack Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Generate and verify the frozen `18+12+20` QGIS human-review package.

**Architecture:** A focused library validates the region-dedup authority, selects
the three deterministic strata, recovers source snippets, and assembles four
hash-backed artifacts. A thin CLI enforces output boundaries and atomic publish.

**Tech Stack:** Python standard library, `unittest`, existing QGIS provenance and
write-boundary helpers.

---

### Task 1: Lock Selection And Review Fields

**Files:**
- Create: `tests/test_qgis_review_pack.py`
- Create: `src/gis_recommend/data/qgis_review_pack.py`

- [ ] Write fixtures with 18 high-evidence semantic representatives, eligible
  nonrepresentative controls, and at least 20 remaining representatives.
- [ ] Assert exactly 50 unique rows and exact stratum counts `18/12/20`.
- [ ] Run the focused test and observe the missing module failure.
- [ ] Implement deterministic quota selection and comparison pairing.
- [ ] Run the focused selection tests to green.

### Task 2: Add Snippets And Artifact Assembly

**Files:**
- Modify: `tests/test_qgis_review_pack.py`
- Modify: `src/gis_recommend/data/qgis_review_pack.py`

- [ ] Add failing tests for owner/module snippets, source SHA drift, empty human
  fields, admission denial, ledger validation, and byte determinism.
- [ ] Implement bounded source resolution, AST-backed snippet extraction, CSV,
  JSONL, summary, and hash ledger assembly.
- [ ] Run all focused tests to green.

### Task 3: Add Atomic CLI And Publish Server Authority

**Files:**
- Create: `scripts/build_qgis_review_pack.py`
- Modify: `tests/test_qgis_review_pack.py`

- [ ] Add failing CLI tests for allowed output, overlap rejection, nonempty output,
  and exact artifact publication.
- [ ] Implement the thin atomic CLI and run focused/combined QGIS tests.
- [ ] Synchronize reviewed files to `/home/qy/system_redesign`, run server tests,
  and publish `pilot_v3_review_50_v1`.
- [ ] Rebuild once to a temporary directory, compare every byte hash, and remove
  only the verified temporary output.

### Task 4: Record Measured Results

**Files:**
- Modify: `docs/reports/qgis_multistep_processing_pilot_2026-07-22.md`
- Modify: `docs/CURRENT_STATE.md`
- Modify: `docs/CURRENT_STATE.zh-CN.md`
- Modify: `docs/PROJECT_CONTEXT.md`
- Modify: `docs/PROJECT_CONTEXT.zh-CN.md`
- Modify: `progress.md`
- Modify: `task_plan.md`

- [ ] Record the authority path, exact stratum counts, source/cluster coverage,
  hashes, and verification evidence.
- [ ] Keep description generation, training export, 200-row expansion, and model
  training blocked pending human adjudication.
- [ ] Run focused, combined, full QGIS, compilation, diff, and git-status checks.
- [ ] Commit with Lore trailers.
