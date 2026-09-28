# QGIS External Analysis Pilot Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Validate whether Joern, QGIS 3.28 Processing Registry, and DataTrove add source-grounded evidence beyond the current QGIS extractors on 100 Processing blockers and 100 API-deferred sources without emitting training rows.

**Architecture:** Keep the three external tools as version-pinned server-side sidecars. A deterministic local Python layer freezes source-disjoint inputs, normalizes each tool's output, compares it with persisted authorities, and stops after the 40-source checkpoint when the Joern evidence delta is empty. `/home/yll` remains read-only; all large artifacts stay under `/home/qy`.

**Tech Stack:** Python standard library and pytest in the repository; Joern official GHCR container pinned by digest; `qgis/qgis:final-3_28_15` pinned by digest; DataTrove 0.9.0 in an isolated Conda Python 3.11 environment; SSH server replay.

---

## File Structure

- `src/gis_recommend/data/qgis_external_pilot_manifest.py`: authority loading, priority selection, source-disjoint checks, and stable manifest hashing.
- `src/gis_recommend/data/qgis_joern_sidecar.py`: normalized Joern evidence schema and evidence-signature extraction.
- `src/gis_recommend/data/qgis_registry_sidecar.py`: normalized QGIS Registry records and report-only catalog comparison.
- `src/gis_recommend/data/qgis_datatrove_sidecar.py`: normalized exact/MinHash cluster records and exact-authority reconciliation.
- `src/gis_recommend/data/qgis_external_pilot_comparison.py`: evidence delta, coverage/false-complete/truncation metrics, checkpoint decision, and summary data.
- `scripts/build_qgis_external_pilot_manifest.py`: thin CLI for the 100+100 manifest and regression-baseline manifest.
- `scripts/qgis_external_pilot/qgis_flow_queries.sc`: Joern P1-P5/A1-A5 query export.
- `scripts/qgis_external_pilot/export_qgis_registry.py`: lazy-PyQGIS exporter run only inside the QGIS container.
- `scripts/qgis_external_pilot/run_datatrove_sidecar.py`: DataTrove pipeline run only in the isolated server environment.
- `scripts/qgis_external_pilot/run_server_pilot.sh`: pinned tool setup, read-only source staging, resource guards, and stage orchestration.
- `scripts/run_qgis_external_analysis_pilot.py`: local/server-neutral validation and comparison driver.
- `tests/fixtures/qgis_external_pilot/`: bounded Python, Joern, Registry, and dedup fixtures.
- `tests/test_qgis_external_pilot_*.py`: focused unit/integration tests.
- `docs/reports/qgis_external_analysis_pilot_v1/`: only small manifests, normalized summaries, hashes, and the final report synchronized from the server.

The project `pyproject.toml` is not modified. Joern, QGIS, and DataTrove remain isolated tools rather than runtime dependencies of `gis-recommend`.

### Task 1: Freeze Schemas and Input Selection

**Files:**
- Create: `src/gis_recommend/data/qgis_external_pilot_manifest.py`
- Create: `scripts/build_qgis_external_pilot_manifest.py`
- Create: `tests/test_qgis_external_pilot_manifest.py`

- [x] **Step 1: Write failing selection and baseline tests**

Cover priority ordering (`conditional_early_exit`, `control_flow:for`, `missing_data_edges`, fill strata), normalized-body uniqueness, holdout exclusion, stable tie-breaking, exactly 100+100 rows, and explicit rejection of aggregate-only API verdicts.

```python
def test_processing_priority_is_mainline_order():
    rows = fixture_processing_rows()
    selected = select_processing(rows, limit=4, excluded_bodies=set())
    assert [row["primary_stratum"] for row in selected] == [
        "conditional_early_exit",
        "control_flow:for",
        "missing_data_edges",
        "cross_function_helper",
    ]


def test_pending_api_reviews_cannot_become_baseline():
    with pytest.raises(ValueError, match="persisted verdict"):
        build_api_baseline([{"review_status": "pending_human_review"}])
```

- [x] **Step 2: Run the focused tests and verify red state**

Run:

```powershell
D:/01_software/02_DevelopmentKits/Python/Anaconda3/python.exe -m pytest tests/test_qgis_external_pilot_manifest.py -q
```

Expected: import failure for `qgis_external_pilot_manifest`.

- [x] **Step 3: Implement deterministic manifest construction**

Use the current Processing inputs:

```text
docs/reports/qgis_processing_boundary_families_v2_condition_evidence/blocker_source_replay_v1.jsonl
docs/reports/mapped_recovery_split_family_census_v2/family_census_v1.jsonl
```

Use the current API-deferred inputs:

```text
docs/reports/qgis_api_mutation_upstream_census_v6/mutation_upstream_census_v1.jsonl
docs/reports/qgis_api_remaining_mutation_export_census_v4/upstream_family_census_v1.jsonl
```

Materialize baseline roles from the exact paths listed in the approved design. Emit `target_manifest_200_v1.jsonl`, `regression_baseline_v1.jsonl`, `selection_summary_v1.json`, and `hash_ledger_v1.json` with sorted keys and LF endings.

- [x] **Step 4: Run tests and a local real-authority dry run**

```powershell
D:/01_software/02_DevelopmentKits/Python/Anaconda3/python.exe -m pytest tests/test_qgis_external_pilot_manifest.py -q
D:/01_software/02_DevelopmentKits/Python/Anaconda3/python.exe scripts/build_qgis_external_pilot_manifest.py --output-dir docs/reports/qgis_external_analysis_pilot_v1/inputs --dry-run
```

Expected: tests pass; dry run reports 100 Processing and 100 API targets, zero target-body duplicates, and zero holdout overlap. If the current authorities cannot supply a stratum, the command fails instead of silently changing quotas.

- [x] **Step 5: Commit the manifest layer**

Commit only the files from this task with a Lore message recording input authorities and the pending-v6-verdict limitation.

### Task 2: Pin and Smoke-Test Server Tool Environments

**Files:**
- Create: `scripts/qgis_external_pilot/run_server_pilot.sh`
- Create: `tests/test_qgis_external_pilot_server_contract.py`

- [x] **Step 1: Write failing server-contract tests**

Parse the shell file as text and require: `/home/yll` read-only mount, `/home/qy` output root, 50 GiB guard, no `latest` tag, explicit digests, Conda Python 3.11, DataTrove 0.9.0, atomic stage directories, and no training exporter invocation.

- [x] **Step 2: Implement the pinned setup stage**

Pin:

```text
ghcr.io/joernio/joern@sha256:27ac49250d279ad9f47d2df9592ffc47a0b10edc2ad1058ad20b48554b18a0d4
qgis/qgis@sha256:ac32c27d2fa816f525e3ac264c1c5243454e6f857cb0cfd04345a4e9022fb85c
datatrove[processing]==0.9.0
```

The script must pull by digest, discover the staged Joern binary inside the official image, capture its actual version/commit, verify QGIS reports 3.28.15, create `/home/qy/.conda/envs/qgis-external-pilot-v1` with Python 3.11, install DataTrove, and write tool versions plus `pip freeze --all` hashes to `hashes/run_manifest_v1.json`. A version mismatch stops the run.

- [x] **Step 3: Run local contract tests**

```powershell
D:/01_software/02_DevelopmentKits/Python/Anaconda3/python.exe -m pytest tests/test_qgis_external_pilot_server_contract.py -q
```

- [x] **Step 4: Synchronize only code and run server environment smoke**

Copy the task files to `/home/qy/system_redesign`, then run:

```bash
bash scripts/qgis_external_pilot/run_server_pilot.sh env-smoke
```

Expected: three tool versions, two image digests, environment lock hash, disk usage below 50 GiB, and no files written under `/home/yll`.

- [x] **Step 5: Stop immediately on environment-gate failure**

If Joern cannot expose its Python frontend, QGIS does not report 3.28.15, or DataTrove cannot import in Python 3.11, write `environment_failure_v1.json` and do not proceed to Task 3.

Gate result (2026-08-03): stopped at `env-smoke:joern_image_pull`. The pinned
GHCR digest did not finish within a detached 20-minute run and logged a layer
retry. The time-boxed failure path produced exit code 124; Task 3 was not
started. Evidence: `docs/reports/qgis_external_analysis_pilot_v1/environment_gate_v1/`.
An on-demand retry with the same digest also exhausted the runner's 1,200-second
timeout after two layers logged retries; it left no residual process or image.

### Task 3: Implement Joern Fixture Queries and Normalization

**Files:**
- Create: `scripts/qgis_external_pilot/qgis_flow_queries.sc`
- Create: `src/gis_recommend/data/qgis_joern_sidecar.py`
- Create: `tests/fixtures/qgis_external_pilot/processing_helper.py`
- Create: `tests/fixtures/qgis_external_pilot/api_to_sink.py`
- Create: `tests/fixtures/qgis_external_pilot/ambiguous_branch.py`
- Create: `tests/test_qgis_joern_sidecar.py`

- [x] **Step 1: Write failing fixture expectations**

Require P1-P5 to recover a helper parameter, returned `result["OUTPUT"]`, and the downstream Processing edge. Require A1-A5 to recover geometry-to-`setGeometry`-to-`addFeature`. The branch fixture must be `ambiguous`, not complete.

```python
def test_complete_processing_flow_is_normalized():
    row = normalize_joern_record(load_fixture_json("processing_helper"))
    assert row.evidence_status == "complete"
    assert row.operator_ids == ("native:buffer", "native:dissolve")
    assert row.dependency_edges == ((0, 1),)


def test_conflicting_branch_is_not_complete():
    row = normalize_joern_record(load_fixture_json("ambiguous_branch"))
    assert row.evidence_status == "ambiguous"
```

- [x] **Step 2: Implement one generic CPG query set**

The Scala query exports JSONL records with `record_id`, `source_sha256`, query IDs, source/sink nodes, node code and positions, ordered flow paths, control-path evidence, and terminal evidence. Query logic is generic by call/FQN/argument role; no record ID, file basename, line number, or source-specific exception is allowed.

- [x] **Step 3: Implement fail-closed Python normalization**

Use explicit terminal states `complete`, `partial`, `insufficient`, `ambiguous`, and `query_failure`. Reject missing source hashes, duplicate query IDs, unsorted or dangling flow nodes, and complete claims without a terminal.

- [x] **Step 4: Run local normalization tests and server Joern fixture smoke**

```powershell
D:/01_software/02_DevelopmentKits/Python/Anaconda3/python.exe -m pytest tests/test_qgis_joern_sidecar.py -q
```

```bash
bash scripts/qgis_external_pilot/run_server_pilot.sh joern-fixture-smoke
```

Expected: all three fixture outcomes match; exported JSONL is byte-identical across two query runs after normalization.

- [x] **Step 5: Apply the first time-box gate**

If cross-function parameter, return, result-dictionary, or API-to-sink fixtures fail after the two-day budget, write a failure report and stop the pilot.

Gate result (2026-08-04): passed. The isolated Processing helper and API-to-sink fixtures are `complete`; the conflicting branch is `ambiguous`. Two normalized exports are byte-identical at SHA256 `14385508ed108aa1981044a365d6a64eafdd0ceb71b5387a52262177a560a2a5`. Evidence: `docs/reports/qgis_external_analysis_pilot_v1/joern_fixture_gate_v1/`.

### Task 4: Export and Compare QGIS 3.28 Registry

**Files:**
- Create: `scripts/qgis_external_pilot/export_qgis_registry.py`
- Create: `src/gis_recommend/data/qgis_registry_sidecar.py`
- Create: `tests/fixtures/qgis_external_pilot/registry_records.json`
- Create: `tests/test_qgis_registry_sidecar.py`

- [x] **Step 1: Write failing normalization and status tests**

Test stable ordering and the separate statuses `matched`, `operator_not_found`, `provider_not_installed`, `provider_version_mismatch`, and `catalog_contract_mismatch`. Verify a mismatch is report-only and never mutates `benchmarks/qgis_planner_v1/authority/qgis_catalog.json`.

- [x] **Step 2: Implement lazy-PyQGIS Registry export**

Initialize QGIS headlessly inside the container, initialize Processing, enumerate providers/algorithms, and emit normalized parameter/output definitions. Include provider availability/version, QGIS version, image digest, and exporter hash. Do not import `qgis` from repository runtime modules.

- [x] **Step 3: Implement catalog comparison**

Join the Registry snapshot to `benchmarks/qgis_planner_v1/authority/qgis_catalog.json` by normalized operator ID. Produce a report-only delta; do not write the benchmark authority.

- [x] **Step 4: Run tests and server Registry smoke twice**

```powershell
D:/01_software/02_DevelopmentKits/Python/Anaconda3/python.exe -m pytest tests/test_qgis_registry_sidecar.py -q
```

```bash
bash scripts/qgis_external_pilot/run_server_pilot.sh registry-smoke
```

Expected: QGIS 3.28.15, `native:buffer` with nonempty INPUT/OUTPUT contract, explicit provider status for GRASS/SAGA, and byte-identical normalized snapshots across two runs.

Gate result (2026-08-04): passed. QGIS 3.28.15 and `native:buffer` INPUT/OUTPUT were verified; normalized snapshots and comparison reports are byte-identical. The report-only catalog delta is 369 matched, 402 operator-not-found, and 520 contract-mismatch; catalog SHA256 remained `a0b2426205b5ba809f03171360f10ab80bf2bc2321d8619eb2994075a132d6bd`. Evidence: `docs/reports/qgis_external_analysis_pilot_v1/registry_gate_v1/`.

### Task 5: Implement DataTrove Exact and MinHash Sidecars

**Files:**
- Create: `scripts/qgis_external_pilot/run_datatrove_sidecar.py`
- Create: `src/gis_recommend/data/qgis_datatrove_sidecar.py`
- Modify: `src/gis_recommend/data/qgis_source_authority.py`
- Create: `tests/fixtures/qgis_external_pilot/dedup_documents.jsonl`
- Create: `tests/test_qgis_datatrove_sidecar.py`
- Modify: `tests/test_qgis_source_authority.py`

- [x] **Step 1: Write failing exact-reconciliation tests**

Fixture rows include exact normalized-body duplicates, comment/header-only variants, near duplicates, and unrelated code. Require exact clusters to equal existing body-hash groups and MinHash clusters to remain report-only.

- [x] **Step 2: Implement normalized DataTrove input/output adapters**

Extract the existing body-normalization block from `source_authority()` into a public
`normalized_source_body(path: Path) -> str` helper, keep the resulting authority hashes
unchanged, and reuse that helper for DataTrove input. Write DataTrove `Document` rows from
those normalized bodies. Configure token-shingle MinHash explicitly and include its
threshold, n-gram size, hash config, and DataTrove version in every summary. Never use
MinHash output to remove a row.

- [x] **Step 3: Run local tests and server DataTrove fixture smoke**

```powershell
D:/01_software/02_DevelopmentKits/Python/Anaconda3/python.exe -m pytest tests/test_qgis_datatrove_sidecar.py -q
```

```bash
bash scripts/qgis_external_pilot/run_server_pilot.sh datatrove-fixture-smoke
```

Expected: exact cluster reconciliation passes; the near-duplicate fixture appears only in MinHash output; two normalized runs are byte-identical.

Gate result (2026-08-04): passed. DataTrove 0.9.0 exact clusters equal the existing normalized-body authority; the near-duplicate pair appears only in report-only MinHash evidence. The custom versioned source-code tokenizer avoids an unplanned SpaCy dependency. Two clean normalized runs are byte-identical at SHA256 `e3bc91dc060138d76d5576b96446bbca147b3f8a4f25e734e4afbfd94e1d227e`; authority mutation=false, training rows=0, and `/home/yll` remains read-only. Evidence: `docs/reports/qgis_external_analysis_pilot_v1/datatrove_gate_v1/`.

### Task 6: Implement Evidence Delta and Metrics

**Files:**
- Create: `src/gis_recommend/data/qgis_external_pilot_comparison.py`
- Create: `scripts/run_qgis_external_analysis_pilot.py`
- Create: `tests/test_qgis_external_pilot_comparison.py`

- [x] **Step 1: Write failing metric-definition tests**

Cover all five evidence-delta states and prove the critical distinctions:

```python
def test_missing_joern_path_is_coverage_miss_not_false_positive():
    result = compare(authority=accepted_chain(), joern=insufficient())
    assert result.delta_status == "existing_only"
    assert result.coverage_miss is True
    assert result.false_complete_evidence is False


def test_complete_claim_missing_terminal_is_truncation():
    result = compare(authority=accepted_chain(), joern=complete_without_terminal())
    assert result.claimed_complete_truncation is True


def test_complete_claim_on_negative_is_false_complete():
    result = compare(authority=negative_boundary(), joern=complete_flow())
    assert result.false_complete_evidence is True
```

- [x] **Step 2: Implement stable evidence signatures and delta classification**

Normalize nodes, edges, control paths, terminals, and evidence kinds before comparison. Emit `existing_only`, `shared_equivalent`, `joern_only_partial`, `joern_only_complete`, or `contradictory`; classify Joern-only evidence by cross-function parameter, return, FQN/import, multi-hop def-use, branch dominance, or alias propagation.

- [x] **Step 3: Implement hard and promotion gates**

Hard gate: source hashes complete, query/runtime failure zero, false-complete zero, claimed-complete truncation zero, Registry fallback zero, exact-cluster reconciliation true, and provenance complete. Promotion gate: at least one previously unresolved normalized-body family with support at least 30 and source-disjoint calibration/holdout zero FP.

- [x] **Step 4: Run focused tests**

```powershell
D:/01_software/02_DevelopmentKits/Python/Anaconda3/python.exe -m pytest tests/test_qgis_external_pilot_comparison.py -q
```

Gate result (2026-08-04): passed locally. All five delta states, coverage-miss/false-complete/truncation distinctions, six Joern novelty kinds, every hard-gate failure, promotion support/source-disjoint conditions, externally declared source count, and byte-stable driver output are covered by 19 passing tests. Training admission remains not granted and emitted training rows=0.

### Task 7: Execute the 40-Source Checkpoint

**Files:**
- Modify: `docs/reports/qgis_external_analysis_pilot_v1/` with small checkpoint artifacts only
- Modify: `docs/superpowers/plans/2026-08-03-qgis-external-analysis-pilot.md` checkbox states

- [ ] **Step 1: Synchronize code and target manifests to `/home/qy`**

Do not synchronize full source text back to the workstation. On the server, copy the selected 20+20 source files from `/home/yll` into the pilot input staging directory and verify 40/40 SHA256 before any tool consumes them.

- [ ] **Step 2: Run all three sidecars on the checkpoint**

```bash
bash scripts/qgis_external_pilot/run_server_pilot.sh checkpoint-40
```

Expected: structured terminal outcome for every applicable query, no runtime failure, Registry snapshot present, exact reconciliation true, and resource ledger below 50 GiB.

- [ ] **Step 3: Run comparison and the novelty gate**

```bash
python3 scripts/run_qgis_external_analysis_pilot.py \
  --pilot-root /home/qy/system_redesign/diagnostics/qgis_joern_pilot_v1 \
  --stage checkpoint-40
```

Stop if `joern_only_partial + joern_only_complete == 0`. Also stop on false-complete evidence, claimed-complete truncation, any query/runtime failure, source mismatch, or source-specific query exception.

- [ ] **Step 4: Synchronize only checkpoint summaries and hashes**

Copy normalized summary JSON, bounded ledger CSV/JSONL, report Markdown, and large-artifact hash manifest to `docs/reports/qgis_external_analysis_pilot_v1/checkpoint_40_v1/`.

- [ ] **Step 5: Commit the checkpoint conclusion**

Commit either the verified stop report or the evidence that authorizes proceeding to 200. Do not claim production adoption at this checkpoint.

### Task 8: Execute the 200-Source Pilot and Finalize the Decision

**Files:**
- Modify: `docs/reports/qgis_external_analysis_pilot_v1/`
- Modify QGIS sections only: `docs/CURRENT_STATE.md`
- Modify QGIS sections only: `docs/CURRENT_STATE.zh-CN.md`
- Modify QGIS section only: `task_plan.md`
- Modify, only if a milestone is reached: `progress.md`

- [ ] **Step 1: Proceed only when the checkpoint authorized expansion**

The driver must read the checkpoint hash and decision. A missing, failed, or empty-delta checkpoint prevents the 200-source command from running.

- [ ] **Step 2: Stage and verify all 200 target sources**

Read from `/home/yll`, write only under `/home/qy`, and verify 200/200 source SHA. Preserve record IDs and normalized-body authority from the frozen manifest.

- [ ] **Step 3: Run the full pilot and repeat the small normalized export**

```bash
bash scripts/qgis_external_pilot/run_server_pilot.sh pilot-200
bash scripts/qgis_external_pilot/run_server_pilot.sh normalize-small-artifacts
bash scripts/qgis_external_pilot/run_server_pilot.sh normalize-small-artifacts
```

Expected: the two small normalized artifact sets have identical SHA256.

- [ ] **Step 4: Generate the final comparison and resource forecast**

Report query completion, accepted exact coverage by query family, false-complete evidence, claimed-complete truncation, all five delta states, Joern-only evidence kinds, Registry/catalog differences, exact/MinHash clusters, runtime, peak memory, disk, and extrapolated 8,466/39,386 costs.

- [ ] **Step 5: Run full focused regression tests**

```powershell
D:/01_software/02_DevelopmentKits/Python/Anaconda3/python.exe -m pytest \
  tests/test_qgis_external_pilot_manifest.py \
  tests/test_qgis_external_pilot_server_contract.py \
  tests/test_qgis_joern_sidecar.py \
  tests/test_qgis_registry_sidecar.py \
  tests/test_qgis_datatrove_sidecar.py \
  tests/test_qgis_external_pilot_comparison.py -q
```

Also run `git diff --check` on every changed repository file.

- [ ] **Step 6: Update only QGIS project memory**

Compress `CURRENT_STATE` rather than appending history. State one of: stopped at environment gate, stopped at 40-source no-novelty gate, hard gate failed, tool runnable but no promotion family, or promotion candidate proven. Do not alter GEE or benchmark conclusions.

- [ ] **Step 7: Commit the final pilot evidence**

The Lore commit must state tool digests, target counts, evidence-delta counts, hard-gate result, promotion-gate result, test commands, and any missing persisted verdict authority.

## Final Verification

Before reporting completion, verify:

```text
/home/yll writes                                  0
training rows emitted                            0
target source hashes                             200/200, unless an earlier designed stop gate fired
query/runtime failures                           0
false_complete_evidence                          0
claimed_complete_truncation                      0
DataTrove exact reconciliation                   true
small normalized artifact repeatability          true
tool/image/environment hashes                    complete
```

If the 40-source novelty gate is empty, stopping there is the successful execution of this plan; continuing to 200 would violate the approved design.
