# QGIS Processing Unified Replay Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Provide one fail-closed driver that calibrates on 200 stratified Processing authorities and then replays the frozen policy over all 8,466 rows.

**Architecture:** A single script loads the authority and evidence manifests, performs strict identity joins, assigns a unique final state, selects a deterministic calibration packet, and writes hash-bound audit artifacts. Full replay is gated by the successful calibration summary and identical input hashes.

**Tech Stack:** Python 3.12 standard library, pytest, existing JSONL QGIS authorities.

---

### Task 1: Lock strict joins and state transitions

**Files:**
- Create: `tests/test_run_qgis_processing_batch.py`
- Create: `scripts/run_qgis_processing_batch.py`

- [ ] Write failing tests for exact authority/base coverage, latest-overlay subset checks, accepted-chain alignment, and fail-closed direct candidates.
- [ ] Run `python -m pytest tests/test_run_qgis_processing_batch.py -q` and confirm failure because the driver does not exist.
- [ ] Implement the minimal identity indexes, training-authority validation, dedup keys, and state machine.
- [ ] Re-run the focused tests and require all tests to pass.

### Task 2: Lock calibration sampling and full-replay gate

**Files:**
- Modify: `tests/test_run_qgis_processing_batch.py`
- Modify: `scripts/run_qgis_processing_batch.py`

- [ ] Add failing tests proving that a 200-row packet retains all direct/accepted rows when capacity permits and covers every remaining status.
- [ ] Add failing tests proving that full replay rejects a failed, stale, or policy-mismatched calibration summary.
- [ ] Implement deterministic source-root-diverse sampling and hash-bound full gating.
- [ ] Re-run the focused tests and require all tests to pass.

### Task 3: Run real calibration and full replay

**Files:**
- Create: `docs/reports/qgis_processing_unified_replay_v1/calibration_200_v1/*`
- Create: `docs/reports/qgis_processing_unified_replay_v1/full_8466_v1/*`

- [ ] Run the driver in calibration mode against the real authority/evidence manifests.
- [ ] Inspect summary invariants and sampled accepted/deferred/excluded/duplicate strata.
- [ ] Run full mode only with the passed calibration summary.
- [ ] Verify 8,466 unique ledger identities, exact state-count totals, accepted JSONL alignment, and artifact hashes.

### Task 4: Regression and durable handoff

**Files:**
- Modify: `docs/CURRENT_STATE.md`
- Modify: `docs/CURRENT_STATE.zh-CN.md`
- Modify: `docs/PROJECT_CONTEXT.md`
- Modify: `docs/PROJECT_CONTEXT.zh-CN.md`
- Modify: `task_plan.md`
- Modify: `progress.md`

- [ ] Run focused QGIS tests, `compileall`, and scoped `git diff --check`.
- [ ] Record only the QGIS result, exact counts, artifact paths, verification, and next high-value recovery work.
- [ ] Confirm `outputs/`, `outputs_v2/`, GEE state, and benchmark state were not changed by this phase.

