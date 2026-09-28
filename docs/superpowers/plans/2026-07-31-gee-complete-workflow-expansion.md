# GEE Complete-Workflow Expansion Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Apply the complete-workflow converter to the 126 unreviewed canonical candidates, produce a 30-source stratified audit gate, and prevent any larger-batch or train-only admission until that gate passes.

**Architecture:** Refactor the existing source-backed fact/text validator into a reusable entrypoint, then build a separate proposal-only expansion driver. The driver freezes all input authorities, excludes every source used by the reviewed 50-row package, applies the same semantic/mapping/dedup/length gates, selects one risk-prioritized representative per source, and emits a deterministic source-disjoint audit sample. A separate evaluator can grant only a rule-level expansion decision after completed audit fields meet the fixed precision and Wilson gates.

**Tech Stack:** Python standard library, existing GEE fact/text authorities, stable-94 mapping, pytest, server source replay under read-only `/home/yll`.

---

### Task 1: Reusable source-backed candidate validator

**Files:**
- Modify: `scripts/export_gee_complete_workflow_training_package.py`
- Modify: `tests/test_export_gee_complete_workflow_training_package.py`

- [ ] Add a failing test calling `validate_source_backed_candidate(fact, text)` and requiring identity/path/workflow-key, real schema/status, calibration stratum, omissions, ordered operator/L3 chain, transformation facts, 64-hex DAG, exactly one output fact, and clause fact references.
- [ ] Run `python -m pytest tests/test_export_gee_complete_workflow_training_package.py -q` and confirm failure because the public validator is absent.
- [ ] Extract the fact/text portion of `_validate_joined_authorities` into `validate_source_backed_candidate`; keep risk/adjudication checks in the reviewed-package wrapper.
- [ ] Re-run the focused exporter tests and confirm reviewed-package behavior remains unchanged.

### Task 2: Proposal-only expansion census

**Files:**
- Create: `scripts/build_gee_complete_workflow_expansion_batch.py`
- Create: `tests/test_build_gee_complete_workflow_expansion_batch.py`

- [ ] Write fixture authorities containing reviewed identities, source-overlap candidates, source-disjoint candidates, an existing training-pair duplicate, an over-length candidate, and a malformed candidate.
- [ ] Write failing tests requiring exactly one terminal status per remaining identity: `proposal_eligible`, `excluded_reviewed_source_overlap`, `excluded_existing_or_batch_duplicate`, `deferred_length`, or `fail_closed_semantic_gate`.
- [ ] Require the production profile to pin fact bundle, task text, reviewed packet, existing semantic rows, and stable-94 SHA256 values plus complete expected counts.
- [ ] Implement deterministic census construction without granting training, validation, test, or production admission.
- [ ] For the frozen rulefix2 authorities, require 126 remaining rows, 43 reviewed-source overlaps, 83 proposal-eligible rows, 0 duplicate, 0 length defer, and 0 semantic failure.

### Task 3: Source-disjoint stratified audit packet

**Files:**
- Modify: `scripts/build_gee_complete_workflow_expansion_batch.py`
- Modify: `tests/test_build_gee_complete_workflow_expansion_batch.py`

- [ ] Add failing tests for six deterministic risk strata: `external_dynamic`, `long_or_repeated`, `multi_dataset_private`, `no_temporal_operation`, `other`, and `spatial_omission`.
- [ ] Add failing tests requiring one risk-prioritized representative per source, exact source-disjointness from the reviewed packet, unique sampled sources, deterministic largest-remainder quotas, and byte-identical replay.
- [ ] Implement the frozen 30-source quota `13/3/5/4/1/4` derived from source-representative support `22/5/9/7/1/6`.
- [ ] Verify each sampled source under read-only `source_root`, extract bounded source snippets from fact locations, and leave every human decision field blank.
- [ ] Emit `audit_sample_30.jsonl`, CSV, source manifest, proposal/sidecar ledgers, summary, report, and hash ledger atomically.

### Task 4: Sampling-audit decision gate

**Files:**
- Create: `scripts/evaluate_gee_complete_workflow_expansion_audit.py`
- Create: `tests/test_evaluate_gee_complete_workflow_expansion_audit.py`

- [ ] Write failing tests for incomplete decisions, identity/hash drift, non-source-disjoint audit rows, and invalid verdict values.
- [ ] Implement Wilson 95% lower-bound evaluation with fixed gates: reviewed rows 30, point precision at least 0.95, Wilson lower at least 0.85, and zero critical chain/L3/fact hallucination failures.
- [ ] Emit only `passed_for_larger_source_disjoint_replay` or `failed_rule_repair_required`; never emit train rows from the evaluator.
- [ ] Keep the initial packet pending until the 30 sampled rows are source-backed reviewed.

### Task 5: Server replay and durable handoff

**Files:**
- Generate: `/home/qy/system_redesign/diagnostics/gee_complete_workflow_expansion_v1_20260731_a/`
- Generate: `/home/qy/system_redesign/diagnostics/gee_complete_workflow_expansion_v1_20260731_b/`
- Modify: `docs/GEE_CURRENT_STATE.md`
- Modify: `docs/GEE_CURRENT_STATE.zh-CN.md`
- Modify: `docs/GEE_PROJECT_CONTEXT.md`
- Modify: `docs/GEE_PROJECT_CONTEXT.zh-CN.md`
- Modify: `task_plan.md` (GEE section only)
- Modify: `progress.md` only after a verified milestone

- [ ] Run the proposal driver twice on the server and compare all artifacts byte-for-byte.
- [ ] Verify all 30 source hashes and snippets without modifying `/home/yll`.
- [ ] Run focused tests, `py_compile`, hash verification, and scoped `git diff --check`.
- [ ] Record proposal yield separately from admitted training yield; until Task 4 passes, new training rows remain zero.
- [ ] After Task 4 passes, freeze a larger source-disjoint selection manifest from the 219,914-source authority and replay the existing DAG/fidelity/mapping/fact/text pipeline. Do not select or process that larger batch before the audit gate passes.
