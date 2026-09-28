# GEE P0 Data Authority Repair Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Repair deterministic GEE vocabulary, metadata association, description alignment, and source-disjoint split authority without regenerating large data or training models.

**Architecture:** Keep legacy Step7/Step8 implementations behind their existing compatibility wrappers. Add strict, independently tested authority helpers and extend the current quality gate with opt-in strict policies plus explicit audit reporting.

**Tech Stack:** Python standard library, dataclasses, unittest, JSON/CSV pipeline artifacts.

---

### Task 1: Authoritative Step8 L3 Mapping

**Files:**
- Modify: `src/gis_recommend/legacy/gee_pipeline/step8_clean_v4_data.py`
- Modify: `tests/test_pipeline_provenance.py`

- [x] Add failing tests for authoritative mapping use, malformed mapping rejection, unknown L3 rejection, and actual output provenance.
- [x] Run `python -m unittest tests.test_pipeline_provenance -v` and confirm the new tests fail for the missing behavior.
- [x] Load and validate `id_mappings_v2.json.l3`, rebuild every token from that mapping, fail on unknown codes, and write actual cleaning provenance.
- [x] Re-run the focused tests and compatibility tests.

### Task 2: Collision-Safe Step7 Metadata Join

**Files:**
- Modify: `src/gis_recommend/legacy/gee_pipeline/step7_prepare_v4_data.py`
- Create: `tests/test_gee_metadata_join.py`

- [x] Add failing tests for identical duplicate facts, conflicting duplicate facts, source diagnostics, and full-script-id graft compatibility.
- [x] Confirm the conflicting-key test currently demonstrates last-write-wins behavior.
- [x] Replace silent overwrite with deterministic deduplication and fail-closed conflict reporting.
- [x] Re-run Step7 and provenance compatibility tests.

### Task 3: Description-Chain Alignment Gate

**Files:**
- Modify: `src/gis_recommend/data/quality_gate.py`
- Modify: `scripts/build_v4_quality_gate_candidate.py`
- Modify: `tests/test_training_data_quality_gate.py`

- [x] Add failing tests for export/chart/visualization claims in report and quarantine modes.
- [x] Implement deterministic claim detection, label-evidence matching, annotations, counters, and CLI policy selection.
- [x] Verify low-confidence quarantine and sparse-task behavior remain unchanged.

### Task 4: Source-Aware Grouped Split

**Files:**
- Modify: `src/gis_recommend/data/quality_gate.py`
- Modify: `scripts/build_v4_quality_gate_candidate.py`
- Modify: `tests/test_training_data_quality_gate.py`

- [x] Add failing tests proving transitive same-source/same-sequence grouping and strict rejection of missing identity.
- [x] Implement trusted identity extraction, connected grouping, strict/compatibility policies, and source leakage reporting.
- [x] Verify every candidate index appears in exactly one split and train task coverage remains valid.

### Task 5: Read-Only Migration Audit and Documentation

**Files:**
- Create: `scripts/audit_gee_p0_migration.py`
- Create: `tests/test_audit_gee_p0_migration.py`
- Update: `docs/CURRENT_STATE.md`
- Update: `docs/CURRENT_STATE.zh-CN.md`
- Update: `docs/PROJECT_CONTEXT.md`
- Update: `docs/PROJECT_CONTEXT.zh-CN.md`
- Update: `progress.md`
- Update: `task_plan.md`

- [x] Add a synthetic failing test for the migration audit summary.
- [x] Implement a read-only report for Step7 L3 recovery, description mismatches, source identity coverage, and candidate deltas.
- [x] Run the audit against current artifacts without writing under `outputs_v2`.
- [x] Record measured results and remaining regeneration decision in role-appropriate project memory.

### Final Verification

- [x] Run focused `unittest` modules for Step7, Step8, provenance, quality gate, launchers, and legacy compatibility.
- [x] Run `python -m compileall` on changed Python files.
- [x] Run `git diff --check` and inspect only task-owned changes.
- [x] Confirm no large file under `outputs_v2` changed and no training/API process started.
