# GEE Complete-Workflow Train Export Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Export the 47 reviewed-pass complete GEE workflows into a validated train-only package, routing one long chain and three deferred workflows to explicit sidecars.

**Architecture:** A dependency-free semantic-row validator defines the complete-workflow contract. A single deterministic package builder freezes the hash-bound adjudication, joins source-backed facts and text, applies semantic/lineage/dedup/length gates, resolves stable-94 tokens, and writes auditable package artifacts. A dedicated smoke adapter exercises the real V4 loader and weighted loss without training.

**Tech Stack:** Python standard library, existing `outputs_v2/id_mappings_v2.json`, existing V4 PyTorch dataset/loss path, `unittest`/`pytest`.

---

### Task 1: Complete-workflow semantic schema

**Files:**
- Create: `src/gis_recommend/data/gee_workflow_train_schema.py`
- Test: `tests/test_gee_workflow_train_schema.py`

- [ ] Write failing tests for valid serialization and fail-closed rejection of wrong scope, invalid SHA, missing DAG/fact hashes, chain/L3 length mismatch, non-L3 codes, non-pass adjudication, validation/test eligibility, and excessive sample weight.
- [ ] Run `python -m pytest tests/test_gee_workflow_train_schema.py -q` and confirm the import fails because the module does not exist.
- [ ] Implement `GeeWorkflowTrainRow`, `validate_workflow_train_row`, constants, and canonical serialization with `schema=gis_recommend.gee_workflow_train_row.v1` and `training_scope=complete_output_workflow`.
- [ ] Re-run the focused test and confirm it passes.

### Task 2: Hash-bound adjudication freeze and package gates

**Files:**
- Create: `scripts/export_gee_complete_workflow_training_package.py`
- Test: `tests/test_export_gee_complete_workflow_training_package.py`
- Create: `docs/reports/gee_complete_workflow_train_v1/adjudication_ledger.json`

- [ ] Write failing tests using temporary JSON/JSONL authorities for risk-packet hash mismatch, missing exception identity, incorrect 47/3 counts, fact/chain/L3/source-lineage mismatch, unknown clause fact ID, duplicate training pair, and long-chain routing.
- [ ] Run the focused tests and confirm they fail because the exporter API does not exist.
- [ ] Implement structured loaders, canonical JSON hashing, `freeze_adjudication_manifest`, `build_training_package`, stable-94 token conversion, deterministic sidecars, summary/report/hash ledger, and atomic writes.
- [ ] Require the frozen pilot contract to produce 50 adjudications, 47 semantic pass rows, 46 V4-100 rows, one length row, and three fail-closed rows.
- [ ] Re-run focused tests and confirm all package gates pass.

### Task 3: Real loader/loss smoke

**Files:**
- Create: `scripts/smoke_gee_complete_workflow_training_package.py`
- Test: `tests/test_smoke_gee_complete_workflow_training_package.py`

- [ ] Write failing tests for package metadata validation and a one-row real V4 dataset/loss/backward pass.
- [ ] Run the focused tests and confirm the smoke API is missing.
- [ ] Implement a CPU-safe deterministic tokenizer adapter, strict complete-workflow package validation, real `TaskConditionedL3DatasetV4` loading, and `weighted_sequence_cross_entropy` backward verification.
- [ ] Assert all rows are seen, loss/gradients are finite, and no checkpoint or production merge is written.

### Task 4: Authority replay and reproducibility

**Files:**
- Generate on server: `/home/qy/system_redesign/diagnostics/gee_complete_workflow_train_v1_20260731_a/`
- Generate on server: `/home/qy/system_redesign/diagnostics/gee_complete_workflow_train_v1_20260731_b/`
- Sync report: `docs/reports/gee_complete_workflow_train_v1/report.md`

- [ ] Run the exporter twice against the rulefix2 authority and frozen adjudication ledger.
- [ ] Compare all semantic/package/sidecar artifacts byte-for-byte; allow only explicitly documented absolute output paths to differ, or remove them from deterministic ledgers.
- [ ] Run the real loader/loss smoke over exactly 46 current-loader rows and record rows seen, batch shape, finite loss/gradient, max token, and max sequence length.
- [ ] Run all focused GEE regressions, `py_compile`, and scoped `git diff --check`.

### Task 5: Durable GEE handoff

**Files:**
- Modify: `docs/GEE_CURRENT_STATE.md`
- Modify: `docs/GEE_CURRENT_STATE.zh-CN.md`
- Modify: `docs/GEE_PROJECT_CONTEXT.md`
- Modify: `docs/GEE_PROJECT_CONTEXT.zh-CN.md`
- Modify: `task_plan.md` (GEE section only)
- Modify: `progress.md`

- [ ] Record only verified row counts, artifact hashes, smoke evidence, remaining unreviewed/mapping-gap queues, and the next source-disjoint expansion gate.
- [ ] Keep QGIS and benchmark sections unchanged.
- [ ] Confirm current-state documents no longer report zero GEE train-only rows for this complete-workflow package.

