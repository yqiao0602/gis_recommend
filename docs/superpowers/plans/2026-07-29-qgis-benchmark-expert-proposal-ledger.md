# QGIS Planner Benchmark Expert Proposal Ledger Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a review-only, parameter-free expert-authored proposal ledger that can be admitted into Gate 3 only after independent graph review, Gate 1 validation, Gate 2 exclusion checks, and deduplication.

**Architecture:** A declarative authoring batch feeds a deterministic validator and proposal ledger. The validator reuses the existing stable101 mapping/catalog and graph-profile logic, while a review ledger records independent decisions separately from proposals. Only explicitly admitted expert rows are exposed to the existing Gate 3 candidate accounting; proposal-only rows cannot change the current 146-row summary.

**Tech Stack:** Python 3, JSONL/JSON, existing QGIS benchmark authority artifacts, `pytest`, SHA-256 hashing.

---

### Task 1: Define the declarative authoring batch and proposal schema

**Files:**
- Create: `benchmarks/qgis_planner_v1/authority/expert_authoring_batch_v1.jsonl`
- Create: `scripts/build_qgis_benchmark_expert_proposals.py`
- Test: `tests/test_build_qgis_benchmark_expert_proposals.py`

- [x] **Step 1: Write failing schema tests**

Add tests for one valid proposal, one proposal containing `task_text`, one proposal with a non-headline operator, and one proposal with invalid process IDs. Assert that failures are deterministic error codes rather than exceptions with free-form messages.

- [x] **Step 2: Run the focused test file and verify it fails**

Run:

```powershell
rtk pytest -q tests/test_build_qgis_benchmark_expert_proposals.py
```

Expected: collection or assertion failures because the proposal builder and validator do not exist.

- [x] **Step 3: Implement the proposal loader and validator**

Implement these functions in `scripts/build_qgis_benchmark_expert_proposals.py`:

```python
SCHEMA = "gis_recommend.qgis_benchmark_expert_proposal.v1"
FORBIDDEN_FIELDS = {
    "task_text", "task_description", "source_path", "source_snippet",
    "parameter_facts", "dataset_id", "field_name", "threshold",
}

def validate_proposal(
    row: dict[str, Any],
    *,
    mapping_by_operator: dict[str, dict[str, Any]],
    catalog_by_operator: dict[str, dict[str, Any]],
) -> list[str]:
    """Return stable error codes; never promote an invalid proposal."""
```

Require schema version, `provenance_class=expert_authored`, non-empty ordered
processes, `parameters_included is False`, strict-catalog operator IDs, exact
stable101 L3 matches, no forbidden fields, valid unique process IDs, and links
that reference only declared process IDs. Preserve `proposal_only`, closed
training flags, and blank review references in the emitted row.

- [x] **Step 4: Add a minimal declarative batch**

Store a small, explicitly authored batch with no task text or parameters. Each
row declares only an ordered operator/L3 graph, links, intended anchor family,
and target strata. Include at least one vector one-step graph, one raster graph,
one merge graph, one branch graph, and one seven-plus graph so every validator
path is exercised. The batch is proposal input, not Gate 3 supply.

- [x] **Step 5: Run the focused tests and verify they pass**

Run the same `pytest` command. Expected: all schema and forbidden-field tests pass, with proposal rows still marked `proposal_only`.

- [x] **Step 6: Commit the isolated schema/batch change**

```powershell
rtk git add benchmarks/qgis_planner_v1/authority/expert_authoring_batch_v1.jsonl scripts/build_qgis_benchmark_expert_proposals.py tests/test_build_qgis_benchmark_expert_proposals.py
rtk git commit -m "Add review-only expert benchmark proposal schema"
```

### Task 2: Deterministic graph profiling and Gate 1 checks

**Files:**
- Modify: `scripts/build_qgis_benchmark_expert_proposals.py`
- Test: `tests/test_build_qgis_benchmark_expert_proposals.py`

- [x] **Step 1: Add failing profile tests**

Cover disconnected graphs, cycles, invalid links, linear chains, multi-input merges, branches, and all four graph-size strata. Assert the profile matches the existing Gate 3 definitions exactly.

- [x] **Step 2: Reuse the existing graph contract**

Import the existing `graph_profile` implementation from `scripts.build_qgis_benchmark_candidate_pool` rather than creating a second topology definition. Add a public wrapper only if the current private name prevents stable import. Compute modality from the strict catalog using the same input/output type rule as Gate 3.

- [x] **Step 3: Enforce Gate 1 and recomputed labels**

Reject any operator whose mapping entry is absent, not `stable101_direct`, not strict-catalog present, or not `headline_eligible`. Recompute `quota_anchor_l3`, `covered_l3`, `modality`, `topology`, and `graph_size_stratum`; reject author-supplied values that differ from recomputation.

- [x] **Step 4: Run the profile tests**

Run:

```powershell
rtk pytest -q tests/test_build_qgis_benchmark_expert_proposals.py
```

Expected: all valid/invalid graph profile cases pass and Gate 1 remains closed for invalid operators.

### Task 3: Review ledger and monotone review-state transitions

**Files:**
- Create: `benchmarks/qgis_planner_v1/authority/expert_proposal_reviews_v1.jsonl`
- Modify: `scripts/build_qgis_benchmark_expert_proposals.py`
- Test: `tests/test_build_qgis_benchmark_expert_proposals.py`

- [x] **Step 1: Write failing review transition tests**

Test that an unreviewed proposal cannot become admitted, a rejected proposal cannot become admitted, a simple independent review can become reviewed, and a branch/merge proposal requires two distinct reviewer IDs. Test that review records require a decision, checked operator IDs, checked links, strata verdicts, exclusion verdict, reviewer ID, and timestamp.

- [x] **Step 2: Implement review validation**

Implement:

```python
def apply_review(
    proposal: dict[str, Any],
    review: dict[str, Any],
) -> dict[str, Any]:
    """Return a copied proposal with monotone review status and admission."""
```

Allow only `accept`, `revise`, or `reject`. `accept` sets
`graph_review_status=independent_reviewed`; it sets `supply_admission` to
`gate3_candidate_admitted` only when the review is complete and Gate 2 later
passes. `revise` and `reject` remain non-admitted. Never modify process/link
content during review application.

- [x] **Step 3: Add an initially empty review artifact**

Write an empty JSONL review ledger with a schema header only through the builder,
so the first proposal build cannot accidentally imply human approval.

- [x] **Step 4: Run review tests**

Run:

```powershell
rtk pytest -q tests/test_build_qgis_benchmark_expert_proposals.py
```

Expected: all review-state tests pass and zero rows are admitted with an empty review ledger.

### Task 4: Gate 2 graph-overlap adapter and four-layer deduplication

**Files:**
- Modify: `scripts/build_qgis_benchmark_expert_proposals.py`
- Test: `tests/test_build_qgis_benchmark_expert_proposals.py`

- [x] **Step 1: Write failing overlap tests**

Create fixtures where an expert graph has the same normalized DAG or semantic DAG as an existing exclusion row, and a control graph with no collision. Assert collisions are recorded by index name and prevent admission.

- [x] **Step 2: Implement graph-only Gate 2 fingerprints**

Reuse the nine-index logic from `scripts.build_qgis_benchmark_exclusion_ledger.py`. Build deterministic normalized DAG, forbidden-near-DAG, and semantic-DAG keys from the proposal `processes + links`; leave source/body/AST/call-graph/task-text identities empty rather than inventing them. Set `gate2_status=pending` until the adapter receives the frozen exclusion indexes.

- [x] **Step 3: Implement four-layer proposal deduplication**

Deduplicate in order: exact proposal identity, canonical graph identity, normalized DAG identity, and training-pair-style process/link identity. Keep the first deterministic canonical row and record suppressed IDs/reason codes in the summary. Deduplication must not alter source-backed artifacts.

- [x] **Step 4: Run overlap and dedup tests**

Run the focused test file. Expected: collisions and duplicates remain non-admitted; clean reviewed proposals retain empty overlap fields.

### Task 5: Build artifacts and Gate 3 accounting adapter

**Files:**
- Modify: `scripts/build_qgis_benchmark_expert_proposals.py`
- Modify: `scripts/build_qgis_benchmark_candidate_pool.py`
- Create: `benchmarks/qgis_planner_v1/authority/expert_proposals_v1.jsonl`
- Create: `benchmarks/qgis_planner_v1/authority/expert_proposal_summary_v1.json`
- Test: `tests/test_build_qgis_benchmark_expert_proposals.py`
- Test: `tests/test_build_qgis_benchmark_candidate_pool.py`

- [x] **Step 1: Add deterministic CLI build test**

Build the same authoring batch twice into isolated directories and assert byte-identical proposal JSONL, review JSONL, summary, and hash ledger. Assert the existing candidate pool summary remains exactly 146 source-backed rows when no admitted expert proposals are supplied.

- [x] **Step 2: Implement the CLI and summary**

Add required inputs for batch, stable101 mapping, strict catalog, capability matrix, and Gate 2 exclusion ledger. Emit proposal/review/summary/hash artifacts. Summary must report proposal count, review status counts, Gate 1 failures, Gate 2 overlap counts, dedup suppressions, admitted expert count, target-stratum counts, and all closed admission flags.

- [x] **Step 3: Add optional admitted-expert input to Gate 3**

Add an optional `expert_proposals` input to the existing candidate-pool builder. The default path remains unchanged. When supplied, include only rows satisfying `independent_reviewed`, Gate 1 passed, Gate 2 passed, dedup canonical, and `gate3_candidate_admitted`; classify them as `expert_authored` and never as `qgis_source_backed`.

- [x] **Step 4: Run Gate 3 regression tests**

Run:

```powershell
rtk pytest -q tests/test_build_qgis_benchmark_expert_proposals.py tests/test_build_qgis_benchmark_candidate_pool.py
```

Expected: the existing 146-row source-only summary is unchanged, proposal-only rows contribute zero, and a fully admitted fixture contributes exactly one expert-authored row with no source-backed count increase.

- [x] **Step 5: Commit the implementation batch**

```powershell
rtk git add scripts/build_qgis_benchmark_expert_proposals.py scripts/build_qgis_benchmark_candidate_pool.py tests/test_build_qgis_benchmark_expert_proposals.py tests/test_build_qgis_benchmark_candidate_pool.py benchmarks/qgis_planner_v1/authority/expert_authoring_batch_v1.jsonl benchmarks/qgis_planner_v1/authority/expert_proposals_v1.jsonl benchmarks/qgis_planner_v1/authority/expert_proposal_reviews_v1.jsonl benchmarks/qgis_planner_v1/authority/expert_proposal_summary_v1.json
rtk git commit -m "Add review-gated expert supply to benchmark Gate 3"
```

### Task 6: Benchmark-only documentation and handoff

**Files:**
- Modify: `task_plan.md:评测集`
- Modify: `docs/CURRENT_STATE.zh-CN.md:评测集`
- Modify: `docs/CURRENT_STATE.md:Benchmark`
- Modify: `progress.md`

- [x] **Step 1: Record the proposal-only gate status**

State the number of proposals, reviewed rows, admitted rows, and remaining strata gaps. Keep Gate 3 failed unless the combined pool actually satisfies all joint quotas.

- [x] **Step 2: Verify scope boundaries**

Confirm the documentation does not claim any change to GEE/QGIS training data, stable101/stable110 mapping, production vocabulary, model training, or final benchmark splits.

- [x] **Step 3: Run final checks**

```powershell
rtk git diff --check
rtk pytest -q tests/test_build_qgis_benchmark_expert_proposals.py tests/test_build_qgis_benchmark_candidate_pool.py
```

Expected: zero whitespace errors and all focused benchmark tests pass. No Gate 4 artifacts are created.
