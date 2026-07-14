# QGIS Direct-API Semantic Aggregation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Produce a deterministic 300-record compact pilot and an evidence-grounded `gpt-5.6-luna` aggregation path for low-level QGIS API traces.

**Architecture:** Add pure compaction and validation primitives to the pilot data module, then expose separate CLIs for building the pilot and invoking an OpenAI-compatible provider. Deterministic evidence remains authoritative; model output is validated and stored as a proposal only.

**Tech Stack:** Python 3.12 stdlib, existing `openai` SDK, `unittest`, JSONL/CSV.

---

### Task 1: Direct-API Classification and Compaction

**Files:**
- Modify: `src/gis_recommend/data/qgis_pilot.py`
- Test: `tests/test_qgis_api_aggregation.py`

- [ ] Write failing tests proving parameter/UI/logging calls become infrastructure, geometry operations become semantic anchors, duplicate runs are compressed, and missing statement indices remain fallback order.
- [ ] Run `python -m unittest tests.test_qgis_api_aggregation -v`; expect missing-symbol failures.
- [ ] Implement `classify_qgis_api_call`, `repair_evidence_order`, and `compact_api_trace` with evidence IDs, run counts, omitted counts, and explicit ordering source.
- [ ] Re-run the test module and existing QGIS pilot tests; expect all pass.

### Task 2: Deterministic 300-Record Pilot Builder

**Files:**
- Create: `scripts/build_qgis_api_aggregation_pilot.py`
- Test: `tests/test_qgis_api_aggregation.py`

- [ ] Write a failing fixture test that streams ordered evidence, excludes T0, rejects infrastructure-only rows, stratifies by source/anchor/order quality, and reproduces the same 300 IDs for a fixed seed.
- [ ] Implement bounded JSONL streaming, compact record schema, stratum allocation, JSONL/CSV outputs, summary, and write ledger.
- [ ] Verify fixture tests and a server smoke with a bounded input.

### Task 3: Strict Provider Contract

**Files:**
- Create: `scripts/run_qgis_api_aggregation_pilot.py`
- Test: `tests/test_qgis_api_aggregation.py`

- [ ] Write failing tests for prompt evidence references, strict response schema, reject behavior, forbidden reasoning fields, unsupported operator rejection, and resumable request IDs.
- [ ] Implement an injected-client aggregation function and CLI defaults: `GGUUAI_API_KEY`, `https://gguuai.com/v1`, `gpt-5.6-luna`.
- [ ] Persist only validated proposals, brief rationale, request fingerprint, and response hash; never raw provider output or reasoning.
- [ ] Run mocked success/refusal/malformed-response tests.

### Task 4: Server Pilot Preparation

**Files:**
- Generate server-side: `outputs_v2/qgis_pilot/pilot_v1/phase3_api_aggregation/`
- Sync bounded reports: `docs/reports/qgis_pilot/phase3_api_aggregation/`

- [ ] Synchronize code/tests to `/home/qy/system_redesign`.
- [ ] Build compact eligible pool and deterministic 300-record coverage pilot from the 1.6GB ordered evidence JSONL.
- [ ] Verify counts, strata, ordering labels, infrastructure rejection, hashes, and `/home/yll` read-only boundary.
- [ ] Run one live request only when `GGUUAI_API_KEY` exists in the process environment; otherwise emit a clean blocked smoke report without embedding a key.

### Task 5: Durable Closeout

**Files:**
- Modify: `task_plan.md`
- Modify: `progress.md`
- Modify: `docs/PROJECT_CONTEXT.md`
- Modify: `docs/PROJECT_CONTEXT.zh-CN.md`

- [ ] Record outputs, hashes, pilot composition, live-smoke status, blockers, and the human-review gate.
- [ ] Run relevant unit tests, `py_compile`, JSON validation, secret scan, and `git diff --check`.
- [ ] Commit only phase-owned files with Lore trailers.
