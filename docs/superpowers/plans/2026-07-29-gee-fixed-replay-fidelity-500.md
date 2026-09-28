# GEE Fixed Replay, Fidelity Gate, And 500-Source Pilot Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn the complete-output-DAG calibration into a deterministic, scalable GEE candidate pipeline, then measure it on a source-disjoint 500-source evidence-first pilot.

**Architecture:** Extend the existing DAG builder with a fixed-selection input that verifies and reads only selected source files. Add a separate post-DAG fidelity module and artifact builder so DAG recovery, semantic rejection, exact-output deduplication, and later task/L3 generation remain independent gates. The 500-source pilot reuses the same builders and remains non-training until taxonomy and faithful task text are added.

**Tech Stack:** Python 3 standard library, ESTree JSON AST, existing GEE extractor/dataflow gate, `unittest`, Node parser on the server.

---

### Task 1: Fixed-Selection Fast Replay

**Files:**
- Modify: `scripts/build_gee_workflow_dag_calibration.py`
- Modify: `tests/test_build_gee_workflow_dag_calibration.py`

- [ ] Add a failing test that writes a fixed `selection.jsonl`, points unrelated canonical/join paths at missing files, and proves replay reads only the selected verified source.
- [ ] Add rejection tests for duplicate SHA, invalid stratum, missing source, byte-SHA mismatch, and size mismatch.
- [ ] Run `python -m unittest tests.test_build_gee_workflow_dag_calibration -v` and confirm the new tests fail for missing fixed-selection support.
- [ ] Implement `_load_fixed_selection_records(selection_manifest, source_root)` with strict schema, unique SHA, source-file existence, byte SHA, byte size, facts-supported, and stratum checks.
- [ ] Make `canonical_manifest` and `join_ledger` optional only when `selection_manifest` is provided. Record the selection manifest and parser SHA in `hash_ledger.json`; do not read the full authority ledgers in fixed mode.
- [ ] Add CLI `--selection-manifest`; require either this option or the canonical-manifest plus join-ledger pair.
- [ ] Run the focused tests and the combined DAG/slicer regression suite.
- [ ] Replay run3's fixed selection twice on the server. Verify the five core artifacts are byte-identical to each other and that `workflow_dags.jsonl`, `summary.json`, and `selection.jsonl` match run3.

### Task 2: Deterministic Post-DAG Fidelity Gate

**Files:**
- Create: `src/gis_recommend/data/gee_workflow_fidelity_gate.py`
- Create: `tests/test_gee_workflow_fidelity_gate.py`

- [ ] Add failing tests for a passed complete DAG, an unresolved DAG rejection, spatial accessor normalization, an exact duplicate output DAG, and a statically proven single-band rename/select mismatch.
- [ ] Define immutable decision records containing source/workflow identity, fidelity status, fail-closed reasons, normalized core chain, removed auxiliary calls, external spatial inputs, and exact DAG fingerprint.
- [ ] Normalize only proven auxiliary spatial accessors whose final method is `geometry` or `bounds`; do not remove geometry transformations or arbitrary API calls.
- [ ] Detect a band mismatch only when all facts are static: a top-level collection is narrowed to one literal band, a map callback returns that image renamed to one literal band without `addBands`, and the admitted workflow later selects a different literal band from the mapped collection.
- [ ] Build an exact-output fingerprint from source SHA, definition closure, dependency edges, normalized core chain, and external input contract. Mark later identical outputs from the same source as duplicates; do not collapse different source SHA or merely similar chains.
- [ ] Keep `training_admission=not_granted_taxonomy_and_task_text_pending` for every fidelity-passed row.
- [ ] Run the new gate tests and all related DAG/extractor/slicer tests.

### Task 3: Fidelity Artifact Builder And Fixed-50 Calibration

**Files:**
- Create: `scripts/build_gee_workflow_fidelity_calibration.py`
- Create: `tests/test_build_gee_workflow_fidelity_calibration.py`

- [ ] Add a failing end-to-end fixture test that consumes DAG JSONL plus SHA-keyed AST files and emits deterministic decision, candidate, rejection, duplicate, summary, report, and hash-ledger artifacts.
- [ ] Validate every source SHA, AST filename, workflow schema, and DAG status before applying the fidelity gate. Fail closed on missing/malformed inputs.
- [ ] Emit accepted candidates separately from rejected and duplicate ledgers. Accepted candidates are next-stage inputs, not training rows.
- [ ] Run the fixed-50 fidelity builder twice on server run3 AST/DAG artifacts and verify byte-identical artifacts.
- [ ] Confirm the known duplicate NDVI export is suppressed and the known `rename('lst')` then `select('scale')` case is rejected. Inspect every distinct new reason, not every row.
- [ ] Freeze the fixed-50 fidelity rule only if those two positive controls behave as expected and no existing fail-closed DAG is promoted.

### Task 4: Source-Disjoint 500-Source Pilot

**Files:**
- Reuse: `scripts/build_gee_workflow_dag_calibration.py`
- Reuse: `scripts/build_gee_workflow_fidelity_calibration.py`
- Generate large artifacts only under `/home/qy/system_redesign/diagnostics/`

- [ ] Build a deterministic 500-source selection from the canonical authority with quotas `linear_export=400`, `helper_export=75`, and `control_flow_export=25`.
- [ ] Verify 500 unique source SHA, exact facts support, byte hashes, stratum counts, and 500/500 expected selection rows before parsing.
- [ ] Recover complete output DAGs for all 500 selected sources; report AST success/failure, source status, workflow status, and fail-closed reasons.
- [ ] Apply the frozen fidelity gate twice and verify byte-identical core artifacts.
- [ ] Report fidelity-passed candidates, exact-output duplicates, semantic rejections, normalized auxiliary calls, external-input prevalence, unique source support, and per-stratum rates.
- [ ] Keep training rows at zero. Do not generate task text or L3 labels in this phase.

### Task 5: Durable GEE Handoff

**Files:**
- Modify: `docs/GEE_CURRENT_STATE.md`
- Modify: `docs/GEE_CURRENT_STATE.zh-CN.md`
- Modify: `docs/GEE_PROJECT_CONTEXT.md`
- Modify: `docs/GEE_PROJECT_CONTEXT.zh-CN.md`
- Modify: GEE section only in `task_plan.md`
- Append milestone only: `progress.md`
- Create: `docs/reports/gee_workflow_fidelity_500_pilot_2026-07-29.md`

- [ ] Record measured fixed-50 and 500-pilot results, hashes, server paths, admission boundaries, and known residual risks.
- [ ] Keep English and Chinese GEE context substantively aligned and replace stale current-state text.
- [ ] Mark only completed GEE tasks as done. Do not edit QGIS or benchmark sections.
- [ ] Run focused tests, `py_compile`, structured artifact assertions, and scoped `git diff --check` before reporting completion.
