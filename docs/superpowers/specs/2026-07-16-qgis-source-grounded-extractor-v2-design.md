# QGIS Source-Grounded Extractor v2 Design

Date: 2026-07-16

Status: approved design, implementation not started

## 1. Objective

Build a deterministic Extractor v2 that converts QGIS source evidence into trustworthy operator chains without changing the frozen v1 path, production vocabulary, taxonomy, training data, or model checkpoints.

The design responds to the locked 35-record v1 holdout:

- E0 precision: 4/5 = 80.0%
- E1: not measurable, zero predictions
- E2 precision: 46/60 = 76.7%
- E3 precision: 12/39 = 30.8%
- Overall item precision: 62/104 = 59.6%
- Complete workflows: 9/35 = 25.7%

Extractor v2 is split into a precision phase and a completeness phase so regressions can be attributed to a specific mechanism.

## 2. Non-Goals

- Do not call an LLM or external labeling API.
- Do not modify the stable-94 production default or promote the experimental taxonomy.
- Do not generate SFT rows, split files, sample duplication, or training manifests.
- Do not run model training.
- Do not overwrite v1 artifacts or reinterpret their recorded hashes.
- Do not add record-ID-specific exceptions.

## 3. Version Isolation

The CLI will expose `--extractor-profile v1|v2`.

- `v1` remains the default until all v2 gates pass.
- `v1` must preserve current output behavior for the existing focused regression suite.
- `v2` activates the new source gate, role classifier, identity resolver, suppression rules, custom-function compiler, and duplicate merger.
- Changing the default to v2 is a separate, explicit decision after a new blind holdout passes.

Every output record must contain `extractor_profile` and `extractor_schema_version`. v2 artifacts must be written to a new directory and must never overwrite `regression_15_run6_exact/` or `holdout_35_v1/`.

## 4. Architecture

The v2 pipeline has eight deterministic stages.

### 4.1 Source Quality Gate

Classify the source record before emitting operators:

- `accepted_workflow`
- `rejected_test`
- `rejected_mock_or_example`
- `rejected_provider_only`
- `rejected_ui_only`
- `accepted_mixed_ui_workflow`

The decision uses structural signals, not one filename token:

- module/path name
- class names and bases
- `test_*` method density
- assertion and test-fixture calls
- mock/provider registration density
- presence of real execution methods and semantic operations
- whether outputs are geospatial products or only assertions/UI state

Strong test evidence rejects the entire source before E0/E2/E3 emission. A UI class is accepted as `mixed_ui_workflow` only when it directly performs domain execution, as in a real importer; pure Dialog/plugin/provider shells are rejected.

Rejected sources retain a structured rejection report and emit zero operator or training rows.

### 4.2 Evidence Collection

Reuse the v1 AST and steps parsers. Preserve raw evidence IDs, source hashes, input/output roles, dependencies, scope, and source ordering metadata.

No evidence becomes an operator before source gating and role classification are complete.

### 4.3 E3 Class Role Classifier

Assign each class exactly one role:

- `algorithm`
- `domain_orchestrator`
- `helper`
- `data_container`
- `provider`
- `mock`
- `test`
- `gui_shell`
- `unresolved`

Only `algorithm` and `domain_orchestrator` may emit E3 components.

Classification signals include:

- Processing base classes
- `processAlgorithm`, `run`, `execute`, import/export, analysis, or model methods
- parameter and output schemas
- semantic-operation density in class scope
- domain call graph ownership
- test/assert/mock/provider/UI lifecycle methods
- passive data-only fields and trivial accessor methods

Names alone are insufficient. A domain importer that owns the import workflow can pass even if it has a GUI, while a Dialog class that only coordinates widgets cannot.

Every rejected class remains visible in `class_role_decisions` with its evidence and reason.

### 4.4 Constructor and Configuration Suppression

Constructors and configuration objects must not emit operators. Confirmed examples include:

- `QgsCoordinateTransform(...)`
- Processing parameter definitions
- options objects such as Warp/Translate/Rasterize options
- provider/registry construction
- writer configuration

Only execution calls such as `transform`, `transformBoundingBox`, `gdal.Warp`, or `gdal.Translate` may emit an operation.

Suppressed evidence is retained for audit and dependency context.

### 4.5 Bounded Identity Resolver

Resolve high-level operator identity before exposing implementation substeps.

Resolution precedence:

1. E0 explicit Processing ID
2. exact self-describing class identity using provider, base, `name()`, `commandLineName()`, parameter schema, and reviewed catalog anchors
3. reviewed E2 direct API mapping
4. accepted E3 custom identity

When a bounded class identity is established, internal E2 calls in the same class execution scope are marked `implementation_substep` unless they are independently invoked E0 operations or produce separately consumed outputs.

Initial confirmed identity additions:

- `gdal.ComputeProximity` -> `gdal:proximity`
- `gdal_merge.main` -> `gdal:merge`
- explicit `qgis:rastersampling`
- legacy Eliminate class -> `qgis:eliminateselectedpolygons`
- expression filtering -> `native:extractbyexpression`
- vector writer export -> `native:savefeatures`
- Shapely line polygonization -> `native:polygonize`

Exact provider identity remains mandatory. Raster polygonization and line polygonization cannot share an ID merely because both contain the word `polygonize`.

### 4.6 Module-Level Custom Function Compiler

This stage is enabled in v2.2 only.

Build a bounded static call graph for module-level functions and methods not owned by an accepted algorithm class. A function becomes a custom workflow component when it:

- is reachable from a source entry point or accepted orchestration path
- owns a domain operation or multiple dependent semantic steps
- produces a geospatial output or materially transforms geospatial state
- is not a trivial accessor, wrapper, formatter, validator, or test helper

The compiler must retain dependencies and ordering between accepted custom functions and bounded operators. Examples targeted by the locked review include harmonic interpolation, network analysis, HDF5 import, FlatGeobuf spatial query, spectral stacking, shoreline extraction, and susceptibility evaluation.

### 4.7 Semantic Step Deduplication

Merge only when two emissions represent the same semantic step.

Deduplication keys include:

- canonical operator ID
- normalized input identities
- normalized output identities
- enclosing scope
- dependency target
- same source call or explicit cross-source confirmation

Same-input/same-output BuildVRT calls are one step. Distinct calls that write different products remain separate. Parallel AST/steps evidence confirms identity but does not add another workflow step.

All merges are recorded in `duplicate_groups`; no evidence is silently discarded.

### 4.8 Output Audit

Each v2 record emits:

- source-quality decision and signals
- primary operator chain
- parallel/supporting evidence
- class-role decisions
- custom function components
- suppressed constructors/configuration
- bounded identity decisions
- duplicate groups
- unresolved evidence
- workflow completeness diagnostics
- taxonomy/training admission fixed to `not_granted`
- training rows fixed to zero

Invalid role values, unbounded positive operator IDs, missing evidence IDs, or inconsistent duplicate groups fail closed.

## 5. Phase Gates

### 5.1 v2.1 Precision Gate

v2.1 implements sections 4.1 through 4.5, 4.7, and 4.8. Module-level custom-function recovery remains disabled.

Acceptance on the locked 35-record regression:

- E0 precision >= 80%
- E2 precision >= 85%
- E3 precision >= 70%
- overall item precision >= 80%
- test-source false positives = 0
- constructor false positives = 0
- workflow completeness >= 25.7%
- stable-94 QGIS test suite remains green

Failure of any hard threshold blocks v2.2 admission.

### 5.2 v2.2 Completeness Gate

v2.2 adds section 4.6 and expands dependency-aware chain recovery.

Acceptance on the same locked regression:

- complete workflows >= 60%
- no tier precision decreases by more than 5 percentage points from accepted v2.1
- test-source and constructor false positives remain zero
- all admitted custom functions have evidence, entry-point reachability, and dependency records

Passing the locked set allows selection of a new blind holdout, not direct scaling to 300 records.

### 5.3 New Blind Gate

After v2.2 passes:

- freeze code and hashes
- select a new stratified blind set excluding all 50 previously reviewed records
- cover E0/E1/E2/E3, vector/raster/mixed, custom functions, long chains, and rejected-source categories
- review without modifying extractor code

Only a successful new blind gate may admit a roughly 300-record pilot. Training and taxonomy admission remain separate later decisions.

## 6. Test Strategy

### Unit Tests

- source-quality classification for test, mock, provider, UI-only, and mixed UI/workflow files
- E3 class-role classification for accepted and rejected roles
- constructor suppression and execution-call emission
- bounded identity precedence and provider disambiguation
- exact identity additions listed in section 4.5
- same-step duplicate merging and distinct repeated-operation preservation
- module-level call-graph and custom-function acceptance/rejection for v2.2

### Locked Regression Tests

Convert the 35 adjudications into deterministic expectations without record-ID conditionals. Cases must be represented by reusable source patterns and fixtures.

The regression runner reports:

- item precision by evidence tier
- overall item precision
- complete workflow rate
- false-positive and omission tags
- rejected-source counts
- constructor suppression counts
- duplicate merge counts

### Compatibility Tests

- all current focused v1 extractor tests remain green under `--extractor-profile v1`
- stable-94 `test_qgis*.py` remains green
- v1 artifact hashes are not regenerated or changed
- v2 dry runs emit zero training rows and `not_granted` admission

## 7. Artifact Layout

Planned local and server artifact root:

`docs/reports/qgis_pilot/phase5_source_grounded_extractor_v2/`

Subdirectories:

- `v2_1_locked_35_regression/`
- `v2_2_locked_35_regression/`
- `v2_new_blind_holdout/`

Server writes remain under `/home/qy/system_redesign`. `/home/yll` remains read-only. Each run records code, input, output, and source hashes.

## 8. Failure Handling

- Unknown source role: reject record, emit diagnostic.
- Unresolved class role: do not emit E3, retain decision evidence.
- Ambiguous bounded identity: abstain rather than choose top-1.
- Incomparable source ordering: keep parallel evidence; do not invent order.
- Missing source artifact or hash mismatch: fail the run.
- Any attempted training/taxonomy admission from v2 artifacts: fail the run.

## 9. Implementation Sequence

1. Add profile isolation and lock v1 behavior.
2. Implement source-quality gate with tests.
3. Implement E3 role classifier with tests.
4. Add constructor suppression.
5. Add bounded identity precedence and confirmed identity gaps.
6. Add semantic duplicate merger.
7. Run and evaluate v2.1 locked regression.
8. If admitted, implement module-level custom-function compiler.
9. Run and evaluate v2.2 locked regression.
10. If admitted, freeze and construct a new blind holdout.

No later step may begin when the preceding gate fails.
