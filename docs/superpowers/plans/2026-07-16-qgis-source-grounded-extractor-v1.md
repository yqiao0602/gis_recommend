# QGIS Source-Grounded Extractor V1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a deterministic, fail-closed extractor that converts real QGIS AST/step evidence into explicit catalog operators, ordered semantic steps, and preserved custom workflows without using LLM inference.

**Architecture:** A reusable data module parses AST JSON, class self-description, catalog metadata, and ordered `_steps.csv` calls into one source-grounded record. A CLI joins those records to the existing 15-row adjudicated regression subset, reports known-answer recovery and forbidden-top1 avoidance, then freezes the same implementation before producing predictions for the untouched 35-row holdout.

**Tech Stack:** Python standard library, existing `gis_recommend.data.qgis_pilot` normalization helpers, `unittest`, JSON/JSONL/CSV artifacts, server read-only sources under `/home/yll`, writes only under `/home/qy`.

---

## File Structure

- Create `src/gis_recommend/data/qgis_source_grounded_extractor.py`: pure parsing, catalog resolution, E0-E3 evidence assembly, deterministic record schema.
- Create `scripts/run_qgis_source_grounded_extractor.py`: CLI orchestration for selected diagnostic rows, regression evaluation, holdout prediction, summary, and hash ledger.
- Create `tests/test_qgis_source_grounded_extractor.py`: unit and regression-contract tests using compact AST/steps fixtures.
- Create `docs/reports/qgis_pilot/phase4_source_grounded_extractor_v1/`: bounded server-generated regression and holdout artifacts synchronized locally; full source evidence remains server-side.
- Modify `task_plan.md`, `progress.md`, and both project context files after server verification.

### Task 1: AST and Catalog Evidence (E0/E1)

**Files:**
- Create: `src/gis_recommend/data/qgis_source_grounded_extractor.py`
- Create: `tests/test_qgis_source_grounded_extractor.py`

- [ ] **Step 1: Write failing E0 tests**

```python
def test_extracts_explicit_processing_ids_in_source_order():
    ast = module_with_constants("qgis:hypsometriccurves", "gdal:warpreproject")
    catalog = {"qgis:hypsometriccurves": {}, "gdal:warpreproject": {}}
    result = extract_ast_evidence(ast, catalog)
    assert [item["operator_id"] for item in result["explicit_operators"]] == [
        "qgis:hypsometriccurves",
        "gdal:warpreproject",
    ]
```

- [ ] **Step 2: Run the focused test and verify missing-module failure**

Run: `python -m unittest tests.test_qgis_source_grounded_extractor`

Expected: FAIL because `qgis_source_grounded_extractor` does not exist.

- [ ] **Step 3: Implement deterministic AST traversal**

Implement:

```python
def extract_ast_evidence(ast_record, catalog):
    # Traverse dict/list nodes by lineno/col_offset and stable visit ordinal.
    # Extract only literal provider-qualified IDs present in catalog.
    # Preserve unknown explicit IDs separately; never fuzzy-map them.
```

- [ ] **Step 4: Add failing E1 tests**

Cover a `ClassDef` with `name() -> "convertgeometrytype"`, `groupId() -> "vectorgeometry"`, and a QGIS algorithm base. Assert exact resolution to `qgis:convertgeometrytype`. Cover a custom class without `name()` and assert it remains custom/unbounded.

- [ ] **Step 5: Implement class self-description and exact provider resolution**

Provider precedence: explicit provider-qualified ID, class base/import evidence, then unique catalog suffix match. Multiple provider matches must remain unresolved.

- [ ] **Step 6: Run tests**

Run: `python -m unittest tests.test_qgis_source_grounded_extractor`

Expected: PASS for E0/E1 tests.

### Task 2: Ordered Direct-API Semantic Compiler (E2/E3)

**Files:**
- Modify: `src/gis_recommend/data/qgis_source_grounded_extractor.py`
- Modify: `tests/test_qgis_source_grounded_extractor.py`

- [ ] **Step 1: Write failing ordered-step tests**

Fixtures must prove:

```python
QgsGeometry.simplify -> native:simplifygeometries
QgsRasterCalculator + QgsRasterCalculatorEntry -> qgis:rastercalculator
gdal.Open -> data_access only, no operator
QgsVectorLayer.featureCount -> data_access only, no operator
```

- [ ] **Step 2: Implement source-grounded semantic rules**

Rules emit catalog operators only for high-specificity API evidence. Generic/data-access calls remain supporting evidence. Deduplicate repeated macro/micro calls while preserving first occurrence and evidence IDs.

- [ ] **Step 3: Write failing multi-step/custom tests**

Cover explicit `gdal:warpreproject -> gdal:buildvirtualraster -> gdal:merge` order and a custom `UrbanSummaryWorker` class. Assert the custom identity is preserved alongside any grounded substeps.

- [ ] **Step 4: Implement E3 custom output**

The record must contain `custom_components`, `unsupported_evidence`, `operator_chain`, `evidence_tiers`, and `training_admission=not_granted`. Custom identities must not be inserted into the standard catalog chain.

- [ ] **Step 5: Run tests**

Run: `python -m unittest tests.test_qgis_source_grounded_extractor`

Expected: all E0-E3 tests pass.

### Task 3: CLI, Regression Contract, and Deterministic Artifacts

**Files:**
- Create: `scripts/run_qgis_source_grounded_extractor.py`
- Modify: `tests/test_qgis_source_grounded_extractor.py`

- [ ] **Step 1: Write failing CLI/help test**

Run the script with `--help` from repository root and assert options for selection JSONL, review CSV, adjudications, catalog, source root remap, review-order range, output directory, and regression mode.

- [ ] **Step 2: Implement source-path remapping and fail-closed reads**

The CLI accepts server paths from `artifact_hashes`, verifies file SHA256 when supplied, rejects paths outside allowed read roots, and writes only under an explicit allowed output root.

- [ ] **Step 3: Write failing regression-evaluation tests**

Use adjudication fixtures to assert:

- incorrect old top1 is not selected as extractor primary operator;
- correct old top1 is recovered;
- expected catalog IDs are recovered when grounded;
- custom/unbounded status is recovered;
- rows without complete expected answers report `not_measurable`, not failure.

- [ ] **Step 4: Implement regression metrics**

Report operator recovery, forbidden-top1 avoidance, custom recovery, measurable rows, per-tier counts, and evidence/failure tags. Do not reuse old exact-transfer coverage as accuracy.

- [ ] **Step 5: Implement deterministic output files**

Write LF-only:

- `extractions.jsonl`
- `regression_results.jsonl` when adjudications are supplied
- `summary.json`
- `hash_ledger.json`

All outputs retain `taxonomy_admission=not_granted` and `training_rows_emitted=0`.

- [ ] **Step 6: Run focused tests and py_compile**

Run:

```powershell
python -m unittest tests.test_qgis_source_grounded_extractor
python -m py_compile src\gis_recommend\data\qgis_source_grounded_extractor.py scripts\run_qgis_source_grounded_extractor.py
```

Expected: PASS.

### Task 4: Server Regression Run on Review Orders 1-15

**Files:**
- Server output: `/home/qy/system_redesign/outputs_v2/qgis_pilot/pilot_v1/phase4_source_grounded_extractor_v1/regression_15/`
- Local bounded report: `docs/reports/qgis_pilot/phase4_source_grounded_extractor_v1/regression_15/`

- [ ] **Step 1: Upload only extractor code/tests to `/home/qy/system_redesign`**

- [ ] **Step 2: Run server unit tests**

Run: `python3 -m unittest tests.test_qgis_source_grounded_extractor`

- [ ] **Step 3: Run extractor with review orders 1-15**

Use `/home/yll` only as an allowed read root and `/home/qy` as the sole write root. No LLM calls and no source modifications.

- [ ] **Step 4: Inspect failures by evidence tier**

Fix only general extraction rules supported by multiple examples or catalog semantics. Do not add record-ID-specific branches.

- [ ] **Step 5: Repeat tests and regression run into a new versioned output directory**

Never delete prior server outputs.

### Task 5: Freeze V1 and Produce Blind Holdout Predictions

**Files:**
- Server output: `/home/qy/system_redesign/outputs_v2/qgis_pilot/pilot_v1/phase4_source_grounded_extractor_v1/holdout_35/`
- Local bounded report: `docs/reports/qgis_pilot/phase4_source_grounded_extractor_v1/holdout_35/`

- [ ] **Step 1: Record extractor code hash and regression summary**

- [ ] **Step 2: Run review orders 16-50 without loading adjudications**

The holdout command must reject `--adjudications` in blind mode and persist `labels_read=false`.

- [ ] **Step 3: Lock holdout prediction hashes**

Sync prediction summary, review workbook, code hash, and ledger locally. Do not inspect or fill human labels in this implementation phase.

### Task 6: Full Verification, Context, and Commit

**Files:**
- Modify: `task_plan.md`
- Modify: `progress.md`
- Modify: `docs/PROJECT_CONTEXT.md`
- Modify: `docs/PROJECT_CONTEXT.zh-CN.md`

- [ ] **Step 1: Run full local QGIS suite under stable-94 profile**

Run:

```powershell
$env:PYTHONPATH='src'
$env:GIS_VOCAB_PROFILE='v2_94_stable'
python -m unittest discover -s tests -p "test_qgis*.py"
```

- [ ] **Step 2: Run server focused tests and verify local/server artifact hashes**

- [ ] **Step 3: Update durable context**

Record implementation, regression results, locked holdout paths/hashes, remaining blind-review work, and explicit no-training status.

- [ ] **Step 4: Stage only extractor-related files and commit with Lore trailers**

Do not stage patent files, `vocab_profile.py`, temporary scripts, or unrelated data.
