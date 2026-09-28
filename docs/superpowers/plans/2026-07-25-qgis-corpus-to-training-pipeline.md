# QGIS Corpus-to-Training Pipeline Implementation Plan

> **Execution rule:** The 50 reviewed rows are a calibration set. Do not scale the same row-by-row adjudication process to the remaining corpus. Every automatic decision must be explained by source-derived features and a versioned rule, never by `review_index`.

**Goal:** Convert the existing QGIS source corpus into high-quality, traceable train-only samples through a deterministic, measurable pipeline that can be rerun after the corpus changes.

**Architecture:** Join every candidate back to immutable source identity, recover executable Processing calls and their data dependencies, classify structural risk with versioned signatures, route only calibrated high-precision patterns to automatic admission, and send novel or ambiguous patterns to bounded stratified review. Accepted rows pass four-layer deduplication and a fail-closed export gate. An LLM may later rewrite task text only after the workflow DAG is frozen; it can never infer or modify the operator chain.

**Tech stack:** Python standard library, `ast`, existing stable101 mapping/provenance artifacts, JSONL/JSON hash ledgers, `unittest`, existing V4 loader/loss smoke path.

## Non-Negotiable Boundaries

- The source file SHA, source span, executable call sites, operator IDs, dependencies, and L3 mapping are deterministic authority.
- `review_index`, file name, repository name, seed text, and LLM output are not admission authority.
- Validation/test eligibility stays false for generated, recovered, weakly described, API-pattern, or near-duplicate rows until an independent dataset-split authority is approved.
- Unknown pattern, source drift, parse failure, dynamic operator ID, unresolved loop cardinality, mapping gap, or rule conflict fails closed to review/deferred.
- No production merge and no training run are part of this plan.

## Task 1: Freeze the 50-Row Calibration Ledger

**Files:**
- Create: `scripts/build_qgis_conversion_calibration_ledger.py`
- Create: `tests/test_build_qgis_conversion_calibration_ledger.py`
- Read: `stable101_second_source_review_50_v1/second_adjudications_batch{1..5}_v1.jsonl`
- Create: `stable101_second_source_review_50_v1/calibration_v1/*`

- [ ] Compute the exact remaining ten review indices from set subtraction, not memory.
- [ ] Complete batch 5 adjudication and verify 50/50 unique decisions with no overlap or omission.
- [ ] Join each decision to source review and preclassification by record ID plus source SHA.
- [ ] Emit one immutable calibration ledger containing source features, structural signature, decision, reason, and recovery action.
- [ ] Reject duplicate decisions, SHA drift, missing task text for accepted rows, or nonblank authority fields in the original review pack.
- [ ] Record ledger and input hashes.

## Task 2: Define Stable Structural Signatures

**Files:**
- Create: `src/gis_recommend/data/qgis_conversion_features.py`
- Create: `tests/test_qgis_conversion_features.py`

- [ ] Add tests for same behavior under changed file path, function name, line number, and `review_index`; signatures must remain stable.
- [ ] Extract normalized features: AST parse status, literal/dynamic Processing IDs, lexical scopes, local call graph, assignment/result flow, branch type, loop cardinality, exception/fallback paths, API calls, mapping completeness, and task-text provenance.
- [ ] Normalize volatile identifiers and source locations while retaining semantic facts such as operator order, dependency edges, branch topology, and API role.
- [ ] Emit `signature_schema_version`, `feature_extractor_version`, and a canonical signature hash.
- [ ] Add regression fixtures for ready-now, connected helpers, disconnected subworkflows, mutually exclusive branches, fixed loops, dynamic loops, API configuration sidecars, API data transformations, comments/docstrings, and generated code.

## Task 3: Build a Versioned Rule Registry

**Files:**
- Create: `src/gis_recommend/data/qgis_conversion_rules.py`
- Create: `config/qgis_conversion_rules_v1.json`
- Create: `tests/test_qgis_conversion_rules.py`

- [ ] Define actions: `auto_accept`, `recover_call_graph`, `split_subworkflow`, `review_api_sidecar`, `defer_mapping`, `defer_dynamic`, `exclude_current_chain`, and `human_review`.
- [ ] Encode rules only over structural features. Assert that `review_index`, path substrings, record ID, and repository names are prohibited rule fields.
- [ ] Encode the calibrated API boundary: parameter/configuration/result-annotation sidecars may retain an explicit Processing DAG; data-transforming or execution-cardinality-changing APIs cannot auto-accept.
- [ ] Require complete admitted operator-to-L3 mapping and an executable literal-ID chain for every `auto_accept`.
- [ ] Emit rule ID, version, matched evidence, confidence, and reason for every routed row.
- [ ] Fail closed when zero or multiple conflicting terminal rules match.

## Task 4: Measure Rule Precision and Coverage

**Files:**
- Create: `scripts/evaluate_qgis_conversion_rules.py`
- Create: `tests/test_evaluate_qgis_conversion_rules.py`
- Create: `stable101_second_source_review_50_v1/calibration_v1/rule_metrics_v1.*`

- [ ] Evaluate rules against the frozen 50-row ledger without fitting on `review_index`.
- [ ] Report per-rule support, accepted precision, deferred/rejected confusion, coverage, and Wilson confidence interval.
- [ ] Permit `auto_accept` only when observed precision is at least 95% and the lower confidence bound/support requirement configured for the rule is satisfied.
- [ ] Treat unsupported or low-support signatures as `human_review` even if all observed examples happened to pass.
- [ ] Produce a machine-readable allowlist of calibrated auto-accept rule versions and a deny/defer list for known failure signatures.

## Task 5: Recover Call Graphs and Executable DAGs

**Files:**
- Create: `src/gis_recommend/data/qgis_workflow_recovery.py`
- Create: `tests/test_qgis_workflow_recovery.py`

- [ ] Recover local helper call order from explicit call sites and assignments.
- [ ] Track Processing outputs into later `INPUT` parameters and emit normalized dependency edges.
- [ ] Split disconnected helpers and mutually exclusive task branches into independent workflow units.
- [ ] Represent parallel branches as a DAG, not a false linear dependency.
- [ ] Unroll only statically provable small loop cardinality; defer dynamic or data-dependent iteration.
- [ ] Record omissions and API sidecars separately from the target Processing chain.
- [ ] Re-parse the exact source SHA before emitting any recovered unit.

## Task 6: Generate Faithful Task Descriptions

**Files:**
- Create: `src/gis_recommend/data/qgis_task_description.py`
- Create: `tests/test_qgis_task_description.py`

- [ ] Prefer reviewed source text when it exactly matches the frozen DAG.
- [ ] Otherwise generate deterministic descriptions from operator semantics, dependency edges, input/output roles, predicates, and admitted sidecars.
- [ ] Reject descriptions that omit a material branch, invent an output format, or describe an excluded API transformation.
- [ ] Keep an optional later LLM rewrite stage behind a separate review gate. Its input is the frozen DAG and deterministic description; its output may only improve wording and must pass a chain-fidelity checker.
- [ ] Never allow description generation to change operator IDs, order, edges, L3 codes, or admission state.

## Task 7: Run Full-Corpus Routing

**Files:**
- Create: `scripts/route_qgis_corpus_to_training.py`
- Create: `tests/test_route_qgis_corpus_to_training.py`
- Create: `docs/reports/qgis_corpus_conversion_v1/`

- [ ] Stream the canonical deduplicated QGIS source authority rather than loading large derived duplicates as independent records.
- [ ] Join source identity, extract features, apply rules, and write separate immutable partitions for each routing action.
- [ ] Resume by source SHA plus extractor/rule version; changed files are automatically reprocessed.
- [ ] Report counts by source root, operator family, structural signature, rule, confidence, mapping status, and task-text status.
- [ ] Emit a drift report comparing signature/rule distributions with the calibration set and prior run.
- [ ] Do not emit training rows from this task.

## Task 8: Use Bounded Stratified Review

**Files:**
- Create: `scripts/sample_qgis_conversion_review.py`
- Create: `tests/test_sample_qgis_conversion_review.py`

- [ ] Always review every new signature, rule conflict, source-drift failure, mapping gap, and low-confidence auto-accept candidate.
- [ ] Randomly audit calibrated auto-accept patterns per rule and source root, with deterministic seed and hash-backed manifests.
- [ ] Escalate a rule back to `human_review` when an audited false positive is found or distribution drift exceeds the configured threshold.
- [ ] Add reviewed examples to a new calibration-ledger version; never mutate v1 decisions.
- [ ] Report sampling coverage and estimated false-admission rate.

## Task 9: Deduplicate and Export Train-Only Rows

**Files:**
- Reuse/extend: `scripts/build_qgis_stable101_recovered_dedup_ledger.py`
- Create: `scripts/export_qgis_corpus_train_only.py`
- Create: `tests/test_export_qgis_corpus_train_only.py`

- [ ] Deduplicate in order: source region identity, recovered call graph, normalized DAG, then task-text near duplication.
- [ ] Do not delete equal operator sequences when source semantics and task intent are independently supported.
- [ ] Require source SHA/span, complete mapping, frozen DAG, faithful task text, calibrated rule evidence, and no unresolved blocker.
- [ ] Assign weights by authority tier; recovered/API-sidecar rows remain lower weight than direct reviewed Processing DAGs.
- [ ] Enforce source-disjoint export partitions and keep validation/test false.
- [ ] Run schema validation, secret scan, deterministic rebuild/hash comparison, and real V4 loader/loss/backward smoke.
- [ ] Emit a train-only manifest and a separate unresolved ledger; do not merge into production automatically.

## Completion Gates

- [ ] All 50 calibration rows have exactly one hash-backed decision.
- [ ] No rule references sample identity or path-specific shortcuts.
- [ ] Every automatic decision exposes source evidence, signature, rule ID, version, and confidence.
- [ ] Auto-accept rules meet the configured precision/support gate; otherwise they fail closed.
- [ ] New signatures and distribution drift reliably enter bounded review.
- [ ] A full-corpus dry run is deterministic and produces routing metrics without training rows.
- [ ] Train-only export passes four-layer dedup, schema, provenance, secret, loader/loss, and permission-boundary checks.
- [ ] Documentation records exact counts, hashes, false-positive estimates, unresolved risks, and the next calibration version.
