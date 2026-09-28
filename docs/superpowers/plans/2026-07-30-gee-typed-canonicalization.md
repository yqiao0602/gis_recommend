# GEE Typed Canonicalization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build an ordinal-aligned, receiver-typed GEE operator/L3 census over the 546 fidelity-passed pilot workflows without generating training rows.

**Architecture:** First make the fidelity artifact preserve normalized call ordinals, then add a separate builder that re-extracts AST call evidence and invokes the existing strict canonicalizer with proven receiver types. Publish mapping-complete and fail-closed ledgers as independent, hash-bound artifacts.

**Tech Stack:** Python 3 standard library, ESTree JSON AST, existing GEE extractor/fidelity gate/P4 canonicalizer, `unittest`, server replay under `/home/qy`.

---

### Task 1: Preserve Normalized Call Ordinals

**Files:**
- Modify: `src/gis_recommend/data/gee_workflow_fidelity_gate.py`
- Modify: `tests/test_gee_workflow_fidelity_gate.py`
- Modify: `tests/test_build_gee_workflow_fidelity_calibration.py`

- [ ] Add a failing test where two identical auxiliary call strings have different ordinals and only the proven external-spatial accessor is removed.
- [ ] Assert that passed and duplicate decisions expose `normalized_core_call_ordinals` aligned one-to-one with `normalized_core_chain`.
- [ ] Run the focused tests and confirm failure because the field does not exist.
- [ ] Normalize `(ordinal, raw_callee)` pairs together and serialize the new field without changing disposition logic.
- [ ] Run fidelity and artifact-builder tests and confirm all pass.

### Task 2: Typed Mapping Domain Gate And Builder

**Files:**
- Create: `src/gis_recommend/data/gee_typed_canonicalization.py`
- Create: `scripts/build_gee_typed_l3_mapping_census.py`
- Create: `tests/test_build_gee_typed_l3_mapping_census.py`

- [ ] Add failing tests for strict accepted-input validation, AST/source identity, ordinal length/non-negative/unique/order checks, core classification, ordinal/callee alignment, extractor-version agreement, typed receiver disambiguation, unknown receiver failure, catalog-without-L3, canonical operator absent from catalog, ambiguous mapping, retained-support rejection, empty canonical chain, and exact ledger partition.
- [ ] Confirm the new test module fails because the builder does not exist.
- [ ] Implement a pure per-workflow gate in `gee_typed_canonicalization.py`; canonicalize one call at a time so mapped, gap, and retained-support outcomes cannot lose ordinal alignment.
- [ ] Implement strict JSONL/AST/mapping loaders in the script using `extract_gee_source_evidence`, `load_gee_l3_mapping`, `load_gee_operator_catalog`, and the pure domain gate.
- [ ] Emit per-call evidence and deterministic top-level statuses with no confidence threshold invention; any retained core call classified as support is fail-closed rather than skipped.
- [ ] Emit the three JSONL ledgers, summary, report, and hash ledger atomically; bind candidate, AST, and mapping hashes.
- [ ] Run the new tests, then the extractor, canonicalizer, fidelity, and DAG regression suites.

### Task 3: Rebuild Fidelity Authorities

**Files:**
- Reuse: `scripts/build_gee_workflow_fidelity_calibration.py`
- Generate large artifacts only under `/home/qy/system_redesign/diagnostics/`

- [ ] Run fixed-50 fidelity twice from the final fixed DAG authority and verify seven byte-identical artifacts, unchanged 35/5/74 disposition, both controls, and zero upstream promotion.
- [ ] Run pilot500 fidelity twice from DAG run3 and verify seven byte-identical artifacts, unchanged 546/10/549 disposition, 250 unique accepted sources, and zero training rows.
- [ ] Record the new hashes; retain the previous artifacts as superseded provenance rather than deleting them.

### Task 4: Run Typed Mapping Census Twice

**Files:**
- Reuse: `scripts/build_gee_typed_l3_mapping_census.py`
- Generate large artifacts only under `/home/qy/system_redesign/diagnostics/`

- [ ] Consume the rebuilt 546-candidate manifest, matching AST directory, and server `outputs_v2/id_mappings_v2.json`.
- [ ] Run the builder twice into separate directories and require all six files to be byte-identical.
- [ ] Verify decisions equal mapping-complete plus fail-closed rows with unique `(source_sha256, workflow_id)` keys.
- [ ] Report complete workflow/source yield, per-stratum rates, L3/operator coverage, mapping-confidence distribution, support skips, and every fail-closed reason.
- [ ] Keep task text, training admission, validation/test, production merge, and training closed.

### Task 5: Durable GEE Handoff

**Files:**
- Create: `docs/reports/gee_typed_l3_mapping_500_pilot_2026-07-30.md`
- Modify: `docs/GEE_CURRENT_STATE.md`
- Modify: `docs/GEE_CURRENT_STATE.zh-CN.md`
- Modify: `docs/GEE_PROJECT_CONTEXT.md`
- Modify: `docs/GEE_PROJECT_CONTEXT.zh-CN.md`
- Modify: GEE section only in `task_plan.md`
- Append a measured milestone only: `progress.md`

- [ ] Record measured mapping yield, authority hashes, server paths, disposition reasons, residual risks, and the next task-fact gate.
- [ ] Keep English and Chinese GEE context substantively aligned and replace the stale active gate.
- [ ] Run focused tests, `py_compile`, structured artifact assertions, and scoped whitespace/diff checks before reporting completion.

No commit is created from the shared dirty worktree. If a commit is requested later, stage only the files owned by this GEE phase and use the repository Lore protocol.
