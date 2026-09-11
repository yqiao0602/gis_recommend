# QGIS Planner v0.1 DAG Review And Roster Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Review all 52 distinct Gate 3 DAGs for semantic closure and freeze a source/DAG-disjoint 8-development / 40-final / 4-reserve roster for the one-week QGIS Planner Benchmark v0.1.

**Architecture:** Keep the original full-v1 Gate 3 failure immutable. Build a v0.1-only DAG review queue by collapsing the 149 candidate rows on `normalized_dag_key`, bind independent semantic review records to immutable graph hashes, and admit only closed DAGs into a deterministic roster freeze. Task text is not created in this plan.

**Tech Stack:** Python standard library, JSON/JSONL authority artifacts, pytest, SHA-256, existing stable101/Gate 1/Gate 2 candidate authority.

---

## File Responsibilities

- `scripts/build_qgis_benchmark_v01_dag_review_queue.py`: collapse candidate rows into immutable distinct-DAG review units and emit the review queue plus census.
- `tests/test_build_qgis_benchmark_v01_dag_review_queue.py`: lock graph grouping, canonical hashes, distributions, and parameter-free boundaries.
- `scripts/adjudicate_qgis_benchmark_v01_dag_reviews.py`: validate hash-bound independent reviews and compute semantic closure without editing graph gold.
- `tests/test_adjudicate_qgis_benchmark_v01_dag_reviews.py`: lock fail-closed reviewer, hash, process-necessity, merge-double-review, and disagreement behavior.
- `scripts/freeze_qgis_benchmark_v01_roster.py`: select and freeze the 8/40/4 roster from closed DAG authorities only.
- `tests/test_freeze_qgis_benchmark_v01_roster.py`: lock split isolation, exact counts, deterministic selection, and truthful supported-scope reporting.
- `benchmarks/qgis_planner_v1/authority/v01_*`: generated v0.1 authority artifacts; none are model-visible task rows.

## Frozen Boundaries

- Keep `candidate_supply_summary.gate_status=failed_insufficient_candidate_supply` for the original full-v1 profile.
- Do not modify `outputs/`, `outputs_v2/`, training rows, GEE artifacts, or final task text.
- Do not treat candidate rows as independent DAGs.
- Do not store concrete QGIS parameters or business-data values.
- Record AI-assisted technical review as such; never label it human review.
- Multi-input merge DAGs require two distinct technical reviewers before closure.
- Roster freeze requires 52 closed DAGs. Any rejected DAG creates an explicit replacement gap and blocks the 8/40/4 freeze until a separately reviewed replacement exists.

### Task 1: Build The Immutable 52-DAG Review Queue

**Files:**
- Create: `scripts/build_qgis_benchmark_v01_dag_review_queue.py`
- Create: `tests/test_build_qgis_benchmark_v01_dag_review_queue.py`
- Create: `benchmarks/qgis_planner_v1/authority/v01_dag_review_queue.jsonl`
- Create: `benchmarks/qgis_planner_v1/authority/v01_dag_review_queue_summary.json`

- [ ] **Step 1: Write the failing grouping and boundary tests**

```python
import importlib
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
module = importlib.import_module("scripts.build_qgis_benchmark_v01_dag_review_queue")


def test_real_candidate_pool_collapses_to_52_review_units():
    result = module.build_queue(ROOT / "benchmarks/qgis_planner_v1/authority/candidate_supply.jsonl")
    assert len(result["rows"]) == 52
    assert result["summary"]["candidate_count"] == 149
    assert result["summary"]["distinct_dag_count"] == 52
    assert result["summary"]["modality_counts"] == {"mixed": 13, "raster": 5, "vector": 34}
    assert result["summary"]["topology_counts"] == {"linear": 30, "multi_input_merge": 22}
    assert result["summary"]["graph_size_counts"] == {
        "four_to_six": 12,
        "one_step": 1,
        "seven_plus": 7,
        "two_to_three": 32,
    }


def test_queue_contains_graph_authority_but_no_task_or_parameter_fields():
    result = module.build_queue(ROOT / "benchmarks/qgis_planner_v1/authority/candidate_supply.jsonl")
    forbidden = {
        "task_text", "task_intent", "output_constraint", "process_necessity",
        "parameters", "rationale", "reason_codes",
    }
    assert all(set(row).isdisjoint(forbidden) for row in result["rows"])
    assert all(row["parameters_included"] is False for row in result["rows"])
    assert all(row["review_status"] == "pending" for row in result["rows"])
```

- [ ] **Step 2: Run the tests and verify RED**

Run:

```powershell
$env:PYTHONPATH=(Get-Location).Path
rtk pytest tests/test_build_qgis_benchmark_v01_dag_review_queue.py -q
```

Expected: FAIL because `scripts.build_qgis_benchmark_v01_dag_review_queue` does not exist.

- [ ] **Step 3: Implement deterministic queue construction**

The module must expose these interfaces:

```python
def canonical_graph(processes: list[dict], links: list[dict]) -> dict:
    """Return process-id-normalized, sorted parameter-free processes and links."""


def build_queue(candidate_path: Path) -> dict[str, object]:
    """Group candidates by normalized_dag_key and emit 52 immutable review units."""


def write_outputs(result: dict[str, object], output_dir: Path) -> dict[str, Path]:
    """Write canonical JSONL plus sorted/indented summary with LF endings."""
```

Each queue row must contain exactly the graph-review evidence needed downstream:

```python
{
    "schema": "gis_recommend.qgis_benchmark_v01_dag_review_queue.v1",
    "canonical_graph_id": normalized_dag_key,
    "canonical_graph_sha256": sha256(canonical_processes_and_links),
    "normalized_dag_key": normalized_dag_key,
    "semantic_dag_key": semantic_dag_key,
    "forbidden_near_dag_keys": sorted_unique_keys,
    "candidate_ids": sorted_unique_candidate_ids,
    "source_authority_keys": sorted_unique_nonempty_source_keys,
    "provenance_classes": sorted_unique_provenance_classes,
    "quota_anchor_l3": one_consistent_anchor,
    "covered_l3": sorted_unique_codes,
    "modality": one_consistent_modality,
    "topology": one_consistent_topology,
    "graph_size_stratum": one_consistent_size,
    "processes": canonical_processes,
    "links": canonical_links,
    "parameters_included": False,
    "review_status": "pending",
}
```

Fail closed when one normalized DAG group has conflicting canonical graph content, modality, topology, graph size, or anchor. Preserve all provenance classes rather than choosing one candidate row as the authority.

- [ ] **Step 4: Run queue tests and verify GREEN**

```powershell
$env:PYTHONPATH=(Get-Location).Path
rtk pytest tests/test_build_qgis_benchmark_v01_dag_review_queue.py -q
```

Expected: all queue tests pass.

- [ ] **Step 5: Generate the real queue twice and compare bytes**

```powershell
$env:PYTHONPATH=(Get-Location).Path
rtk proxy python scripts/build_qgis_benchmark_v01_dag_review_queue.py
rtk proxy python scripts/build_qgis_benchmark_v01_dag_review_queue.py
```

Expected: both builds report `candidates=149 dags=52 status=pending_review`; hashes remain unchanged.

- [ ] **Step 6: Commit Task 1 with Lore trailers**

Stage only Task 1 files and record exact tests plus deterministic rebuild evidence.

### Task 2: Validate Independent Semantic DAG Reviews

**Files:**
- Create: `scripts/adjudicate_qgis_benchmark_v01_dag_reviews.py`
- Create: `tests/test_adjudicate_qgis_benchmark_v01_dag_reviews.py`
- Create: `benchmarks/qgis_planner_v1/authority/v01_dag_semantic_reviews.jsonl`
- Create: `benchmarks/qgis_planner_v1/authority/v01_dag_semantic_review_summary.json`

- [ ] **Step 1: Write failing review-state tests**

```python
import importlib


module = importlib.import_module("scripts.adjudicate_qgis_benchmark_v01_dag_reviews")


def queue_row(topology="linear"):
    return {
        "canonical_graph_id": "dag-1",
        "canonical_graph_sha256": "a" * 64,
        "topology": topology,
        "processes": [
            {"process_id": "p0", "operator_id": "native:buffer", "stable101_l3": "L3_02_01_01"}
        ],
        "links": [],
    }


def approved_review(reviewer_id):
    return {
        "schema": "gis_recommend.qgis_benchmark_v01_dag_semantic_review.v1",
        "review_id": f"review-{reviewer_id}",
        "canonical_graph_id": "dag-1",
        "canonical_graph_sha256": "a" * 64,
        "reviewer_id": reviewer_id,
        "reviewer_kind": "ai_assisted_qgis_technical_reviewer",
        "independent_review_attested": True,
        "decision": "approve",
        "task_intent": "Create a distance zone around the input features.",
        "output_constraint": "The result is a polygon buffer layer.",
        "process_necessity": [{"process_id": "p0", "necessity": "required"}],
        "type_compatibility_attested": True,
        "rationale": "The operator and output type close the stated planning intent.",
        "reviewed_at": "2026-07-31T00:00:00Z",
    }


def rejected_review(reviewer_id):
    row = approved_review(reviewer_id)
    row["decision"] = "reject"
    return row


def wrong_hash_review():
    row = approved_review("reviewer-a")
    row["canonical_graph_sha256"] = "b" * 64
    return row


def missing_necessity_review():
    row = approved_review("reviewer-a")
    row["process_necessity"] = []
    return row


def test_linear_dag_closes_with_one_valid_hash_bound_review():
    result = module.apply_reviews([queue_row()], [approved_review("reviewer-a")])
    assert result["rows"][0]["semantic_closure_status"] == "closed"


def test_merge_dag_requires_two_distinct_reviewers():
    one = module.apply_reviews([queue_row("multi_input_merge")], [approved_review("reviewer-a")])
    assert one["rows"][0]["semantic_closure_status"] == "pending_second_review"
    two = module.apply_reviews(
        [queue_row("multi_input_merge")],
        [approved_review("reviewer-a"), approved_review("reviewer-b")],
    )
    assert two["rows"][0]["semantic_closure_status"] == "closed"


def test_hash_mismatch_missing_necessity_and_disagreement_fail_closed():
    assert module.apply_reviews([queue_row()], [wrong_hash_review()])["failure_count"] == 1
    assert module.apply_reviews([queue_row()], [missing_necessity_review()])["failure_count"] == 1
    result = module.apply_reviews(
        [queue_row("multi_input_merge")],
        [approved_review("reviewer-a"), rejected_review("reviewer-b")],
    )
    assert result["rows"][0]["semantic_closure_status"] == "disagreement"
```

- [ ] **Step 2: Run the tests and verify RED**

```powershell
$env:PYTHONPATH=(Get-Location).Path
rtk pytest tests/test_adjudicate_qgis_benchmark_v01_dag_reviews.py -q
```

Expected: FAIL because the adjudicator module does not exist.

- [ ] **Step 3: Implement the review contract and state machine**

Allowed decisions are `approve`, `reject`, and `return_for_revision`. Every review must bind:

```python
{
    "schema": "gis_recommend.qgis_benchmark_v01_dag_semantic_review.v1",
    "review_id": nonempty_string,
    "canonical_graph_id": exact_queue_id,
    "canonical_graph_sha256": exact_queue_hash,
    "reviewer_id": nonempty_string,
    "reviewer_kind": "ai_assisted_qgis_technical_reviewer",
    "independent_review_attested": True,
    "decision": allowed_decision,
    "task_intent": nonempty_string,
    "output_constraint": nonempty_string,
    "process_necessity": one_entry_per_process_id,
    "type_compatibility_attested": True,
    "rationale": nonempty_string,
    "reviewed_at": ISO_8601_UTC,
}
```

`process_necessity` entries use only `required` or `optional`. An approval must cover every process exactly once. Duplicate reviewer IDs, duplicate review IDs, graph/hash mismatch, unexpected processes, missing processes, AI reviews mislabeled as human, and merge approval by fewer than two distinct reviewers fail closed.

- [ ] **Step 4: Run adjudicator tests and verify GREEN**

```powershell
$env:PYTHONPATH=(Get-Location).Path
rtk pytest tests/test_adjudicate_qgis_benchmark_v01_dag_reviews.py -q
```

Expected: all adjudicator tests pass.

- [ ] **Step 5: Commit Task 2 with Lore trailers**

Record that technical review is transparently AI-assisted and does not replace final human task review.

### Task 3: Conduct The 52-DAG Independent Technical Review

**Files:**
- Modify: `benchmarks/qgis_planner_v1/authority/v01_dag_semantic_reviews.jsonl`
- Modify: `benchmarks/qgis_planner_v1/authority/v01_dag_semantic_review_summary.json`

- [ ] **Step 1: Partition immutable queue IDs without changing queue rows**

Create deterministic primary-review batches by sorting `canonical_graph_id` and assigning round-robin batches. Every DAG receives one primary technical review. Every `multi_input_merge` DAG receives a second review by a different reviewer that did not see the first review record.

- [ ] **Step 2: Review task intent, output constraint, process necessity, links, and types**

Reviewers may read only the queue row, strict QGIS catalog evidence, stable101 mapping authority, and source reference needed to resolve ambiguity. They must not read another review before submitting their own record. They must use `return_for_revision` rather than inventing semantics that are not supported by the graph.

- [ ] **Step 3: Apply the adjudicator and inspect every non-closed DAG**

```powershell
$env:PYTHONPATH=(Get-Location).Path
rtk proxy python scripts/adjudicate_qgis_benchmark_v01_dag_reviews.py
```

Expected for roster eligibility: `closed=52 failures=0 disagreements=0`. Any other result blocks Task 4 and produces a replacement-gap list.

- [ ] **Step 4: Independently verify review coverage**

Assert all 52 graph hashes are covered; all 22 merge DAGs have two distinct reviewer IDs; all 30 linear DAGs have at least one; every process has necessity coverage; semantic sidecar fields remain absent from `candidate_supply.jsonl`.

- [ ] **Step 5: Commit Task 3 review authority with Lore trailers**

Record reviewer IDs, exact review counts, closed/rejected/revision/disagreement counts, and the fact that final human task review remains pending.

### Task 4: Freeze The 8/40/4 Supported-Scope Roster

**Files:**
- Create: `scripts/freeze_qgis_benchmark_v01_roster.py`
- Create: `tests/test_freeze_qgis_benchmark_v01_roster.py`
- Create: `benchmarks/qgis_planner_v1/authority/v01_supported_scope_roster.jsonl`
- Create: `benchmarks/qgis_planner_v1/authority/v01_supported_scope_roster_summary.json`

- [ ] **Step 1: Write failing freeze tests**

```python
import importlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
module = importlib.import_module("scripts.freeze_qgis_benchmark_v01_roster")


def real_authority():
    queue_rows = [
        json.loads(line)
        for line in (ROOT / "benchmarks/qgis_planner_v1/authority/v01_dag_review_queue.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
        if line.strip()
    ]
    closure_rows = [
        json.loads(line)
        for line in (ROOT / "benchmarks/qgis_planner_v1/authority/v01_dag_semantic_reviews.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
        if line.strip()
    ]
    return queue_rows, closure_rows


def test_real_closed_authority_freezes_exact_8_40_4_roster():
    queue_rows, closure_rows = real_authority()
    result = module.freeze(queue_rows, closure_rows)
    assert result["summary"]["split_counts"] == {
        "development": 8,
        "final": 40,
        "reserve": 4,
    }
    assert len({row["canonical_graph_id"] for row in result["rows"]}) == 52
    assert all(row["semantic_closure_status"] == "closed" for row in result["rows"])


def test_roster_is_dag_and_source_component_disjoint():
    queue_rows, closure_rows = real_authority()
    result = module.freeze(queue_rows, closure_rows)
    split_by_graph = {row["canonical_graph_id"]: row["split"] for row in result["rows"]}
    assert len(split_by_graph) == 52
    assert result["summary"]["cross_split_source_component_overlap_count"] == 0


def test_non_closed_or_insufficient_authority_fails_without_partial_roster():
    queue_rows, closure_rows = real_authority()
    result = module.freeze(queue_rows, closure_rows[:-1])
    assert result["rows"] == []
    assert result["summary"]["freeze_status"] == "blocked_semantic_closure"
```

- [ ] **Step 2: Run tests and verify RED**

```powershell
$env:PYTHONPATH=(Get-Location).Path
rtk pytest tests/test_freeze_qgis_benchmark_v01_roster.py -q
```

Expected: FAIL because the roster freezer does not exist.

- [ ] **Step 3: Implement deterministic roster selection**

Use `canonical_graph_id` as the final tie-breaker. Select development first for rubric diversity, final second for maximum DAG diversity, and reserve last. The target distribution is:

```python
TARGETS = {
    "development": {
        "count": 8,
        "modality": {"vector": 5, "mixed": 2, "raster": 1},
        "topology": {"linear": 5, "multi_input_merge": 3},
        "graph_size": {"one_step": 1, "two_to_three": 4, "four_to_six": 2, "seven_plus": 1},
    },
    "final": {
        "count": 40,
        "modality": {"vector": 26, "mixed": 10, "raster": 4},
        "topology": {"linear": 23, "multi_input_merge": 17},
        "graph_size": {"one_step": 0, "two_to_three": 25, "four_to_six": 10, "seven_plus": 5},
    },
    "reserve": {
        "count": 4,
        "modality": {"vector": 3, "mixed": 1, "raster": 0},
        "topology": {"linear": 2, "multi_input_merge": 2},
        "graph_size": {"one_step": 0, "two_to_three": 3, "four_to_six": 0, "seven_plus": 1},
    },
}
```

Search exact joint assignments with deterministic dynamic programming over split counts and strata. Do not select each marginal independently. If exact joint targets are infeasible, emit `blocked_joint_roster_infeasible` and no rows; do not silently relax a target.

The 2026-07-31 preimplementation diagnostic found the declared joint target feasible on the current 52-DAG authority (`8/40/4`, search states=444). The production freezer must reproduce feasibility from authority rows rather than embedding the diagnostic assignment.

Each roster row contains the immutable graph hash, split, strata, source component, review IDs, and `task_variant_target` (`5` development, `3` final, `0` reserve). It contains no task text.

- [ ] **Step 4: Run roster tests and verify GREEN**

```powershell
$env:PYTHONPATH=(Get-Location).Path
rtk pytest tests/test_freeze_qgis_benchmark_v01_roster.py -q
```

Expected: all roster tests pass.

- [ ] **Step 5: Freeze twice and prove byte identity**

```powershell
$env:PYTHONPATH=(Get-Location).Path
rtk proxy python scripts/freeze_qgis_benchmark_v01_roster.py
rtk proxy python scripts/freeze_qgis_benchmark_v01_roster.py
```

Expected: `development=8 final=40 reserve=4 status=frozen`; both authority files remain byte-identical.

- [ ] **Step 6: Commit Task 4 with Lore trailers**

Record the exact DAG distribution, supported-scope non-claims, review coverage, and deterministic rebuild evidence.

### Task 5: Phase Verification And Handoff To Task-Text Authoring

**Files:**
- Modify only benchmark-owned current-state/plan documentation present on this branch.

- [ ] **Step 1: Run all benchmark authority tests**

```powershell
$env:PYTHONPATH=(Get-Location).Path
rtk pytest tests/test_qgis_benchmark_semantic_intent.py tests/test_build_qgis_benchmark_expert_proposals.py tests/test_build_qgis_benchmark_candidate_pool.py tests/test_build_qgis_benchmark_v01_dag_review_queue.py tests/test_adjudicate_qgis_benchmark_v01_dag_reviews.py tests/test_freeze_qgis_benchmark_v01_roster.py -q
```

Expected: all tests pass.

- [ ] **Step 2: Verify code and artifact hygiene**

```powershell
rtk proxy python -m py_compile scripts/build_qgis_benchmark_v01_dag_review_queue.py scripts/adjudicate_qgis_benchmark_v01_dag_reviews.py scripts/freeze_qgis_benchmark_v01_roster.py
rtk git diff --check
rtk git status --short
```

Expected: compilation and diff check pass; only the three known untracked build inputs remain outside committed benchmark files.

- [ ] **Step 3: Record the next phase boundary**

The next plan starts only after roster status is `frozen`. It creates 40 development and 120 sealed final task variants, validates semantic text against the frozen graph, builds alternative-aware gold, and performs final human task review. It must not reopen DAG selection after model predictions are viewed.

- [ ] **Step 4: Commit concise benchmark-only handoff documentation**

Do not edit GEE or QGIS training-data state. Record the roster hashes, review counts, blockers, and next plan path only.

## Phase Acceptance Criteria

1. Exactly 149 candidate rows collapse into 52 immutable distinct-DAG review units.
2. All queue rows remain parameter-free and contain no task text or semantic answer fields.
3. Every linear DAG has one valid independent technical review; every merge DAG has two distinct reviews.
4. All 52 DAGs are semantically closed, or the phase explicitly blocks with replacement gaps.
5. The roster freezes exactly 8 development, 40 final, and 4 reserve DAGs with zero source/DAG cross-split overlap.
6. Original full-v1 Gate 3 remains failed; v0.1 is a separate supported-scope profile.
7. Roster artifacts rebuild byte-identically and contain no model-visible tasks.
