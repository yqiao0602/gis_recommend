# GEE Raw-to-Step8 Replay Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Reproduce and audit the legacy GEE data path from surviving raw scripts and preserved Step1 authority through Steps 1-8 without overwriting training artifacts.

**Architecture:** Use two explicitly separated evidence lanes. The exact legacy lane starts from the preserved `outputs_v2/pipeline/step1/raw_workflows.json` because the 31 original `Workflowoutput*` directories are no longer present; it replays Steps 2-8 into a new diagnostic root. The fresh-source lane reruns the surviving legacy JavaScript extractor on selected and then full raw `Data/data*` scripts, compares its `_steps.csv` output against the preserved Step1 records, and never presents fresh extraction as byte-identical historical provenance.

**Tech Stack:** Python, legacy JavaScript AST extractor, JSON/CSV, SHA256 manifests, pytest, Linux server execution over SSH.

---

### Task 1: Freeze authorities and environment

**Files:**
- Create: `diagnostics/gee_step1_8_replay_20260722/authority_manifest.json`
- Create: `diagnostics/gee_step1_8_replay_20260722/hash_ledger.json`

- [ ] Record paths, sizes, mtimes, and SHA256 for the preserved Step1 input, mapping authority, skip list, facts inputs, raw sample scripts, and all Step1-8 code modules.
- [ ] Record Python/package versions, host, free disk, command lines, and the fact that the historical 31 GEE `Workflowoutput*` directories are absent.
- [ ] Refuse any output path under existing `outputs/` or `outputs_v2/`.

### Task 2: Prove the upstream extractor boundary on known samples

**Files:**
- Create: `diagnostics/gee_step1_8_replay_20260722/source_smoke/`
- Create: `diagnostics/gee_step1_8_replay_20260722/sample_trace.jsonl`

- [ ] Freshly extract `script_2030`, `script_3756`, `script_4142`, `script_3956`, and `script_431` with the surviving legacy extractor.
- [ ] Compare fresh calls with original source text and the matching preserved Step1 operation sequence.
- [ ] Record callback/helper omissions, constructor/UI/I/O handling, order differences, and extraction failures per sample.

### Task 3: Exact replay from preserved Step1 through Step8

**Files:**
- Create: `diagnostics/gee_step1_8_replay_20260722/exact_replay/pipeline/step1/raw_workflows.json`
- Create: `diagnostics/gee_step1_8_replay_20260722/exact_replay/pipeline/step2/` through `step8/`
- Create: `diagnostics/gee_step1_8_replay_20260722/exact_replay/run.log`

- [ ] Copy the preserved Step1 file into the isolated diagnostic root and verify its SHA256 before running.
- [ ] Run Steps 2-8 sequentially with explicit `outputs-dir`, `id-mappings`, `skip-list`, `facts-dir`, and metadata authority paths.
- [ ] Stop at the first failed prerequisite; do not silently substitute missing authorities.
- [ ] Hash every generated artifact and compare counts/hashes with legacy `outputs_v2` artifacts where available.

### Task 4: Build a per-step loss ledger

**Files:**
- Create: `diagnostics/gee_step1_8_replay_20260722/step_metrics.json`
- Create: `diagnostics/gee_step1_8_replay_20260722/operator_fate.csv`

- [ ] Measure workflow and operator counts before/after every step.
- [ ] Classify every removed or changed call as core, constructor/infrastructure, I/O contract, presentation/UI, auxiliary, unresolved/custom, duplicate compression, or record-level filtering.
- [ ] Attribute each disappearance to the first responsible stage and preserve example script IDs.
- [ ] Separate policy-driven removals from extraction defects and authority/provenance defects.

### Task 5: Run the fresh-source corpus lane only after the smoke gate

**Files:**
- Create: `diagnostics/gee_step1_8_replay_20260722/fresh_source/`
- Create: `diagnostics/gee_step1_8_replay_20260722/fresh_source_manifest.jsonl`

- [ ] Enumerate the 31 historical raw batch ranges represented in preserved Step1 and map them to current `Data/data*` directories.
- [ ] Exclude ArcGIS/QGIS and later `data400000` sources from the historical GEE comparison unless separately labeled.
- [ ] Run fresh extraction with resumable per-script status and bounded worker count.
- [ ] Run Step1-8 on fresh `_steps.csv` only if the smoke comparison proves the extractor and schemas are operational.
- [ ] Report fresh-versus-preserved coverage and differences; never merge the two authorities.

### Task 6: Verify and publish the audit

**Files:**
- Create: `docs/reports/gee_step1_8_replay_2026-07-22.md`
- Modify: `docs/CURRENT_STATE.md`
- Modify: `docs/CURRENT_STATE.zh-CN.md`
- Modify: `docs/PROJECT_CONTEXT.md`
- Modify: `docs/PROJECT_CONTEXT.zh-CN.md`
- Modify: `progress.md`
- Modify: `task_plan.md`

- [ ] Validate JSON/CSV schemas, count invariants, output-root isolation, and SHA256 ledger completeness.
- [ ] Run focused legacy/P0 tests plus `compileall` and `git diff --check`.
- [ ] Report exact findings, unresolved provenance gaps, changed files, verification commands, and remaining risks.
- [ ] Update durable context only after measured results exist; do not record intended results as completed milestones.

