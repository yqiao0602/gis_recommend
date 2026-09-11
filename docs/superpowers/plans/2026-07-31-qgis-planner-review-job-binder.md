# QGIS Planner v0.1 Review-Job Binder Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Generate hash-bound DAG review jobs and bind semantic-only reviewer drafts into valid v0.1 review records with an explicit type-compatibility verdict.

**Architecture:** Extend the existing adjudicator module and its test file. Reuse the current JSONL loader, queue authority, validator, and state machine; add only deterministic job generation/binding plus one generated job authority.

**Tech Stack:** Python standard library, JSONL, SHA-256, pytest.

---

### Task 1: Lock The Type Verdict Contract

**Files:**
- Modify: `tests/test_adjudicate_qgis_benchmark_v01_dag_reviews.py`
- Modify: `scripts/adjudicate_qgis_benchmark_v01_dag_reviews.py`

- [ ] Add `type_compatibility_verdict="compatible"` to the valid-review helper.
- [ ] Add failing tests proving `approve` rejects `incompatible` and `uncertain`, while `reject` and `return_for_revision` accept explicit non-compatible verdicts when `type_compatibility_attested=true`.
- [ ] Run `rtk pytest tests/test_adjudicate_qgis_benchmark_v01_dag_reviews.py -q` and confirm the new tests fail for the missing verdict behavior.
- [ ] Add `ALLOWED_TYPE_COMPATIBILITY_VERDICTS` and the minimum validation needed to pass the tests.
- [ ] Re-run the focused test file and confirm it passes.

### Task 2: Generate And Bind Review Jobs

**Files:**
- Modify: `tests/test_adjudicate_qgis_benchmark_v01_dag_reviews.py`
- Modify: `scripts/adjudicate_qgis_benchmark_v01_dag_reviews.py`
- Create: `benchmarks/qgis_planner_v1/authority/v01_dag_review_jobs.jsonl`

- [ ] Add failing tests for deterministic job IDs, queue-hash binding, semantic-only drafts, exact process coverage, wrong reviewer, duplicate/unknown jobs, and stale queue hash.
- [ ] Run the focused tests and confirm RED for missing job/binder APIs.
- [ ] Implement `build_review_jobs(...)` and `bind_review_drafts(...)` by reusing `_queue_authority` and the existing validator. Do not add a dependency, class hierarchy, alias layer, or silent repair.
- [ ] Re-run focused tests and the existing 46-test benchmark authority suite.
- [ ] Generate jobs twice from the immutable queue and compare bytes.

### Task 3: Review And Rebind Wave 1

**Files:**
- Modify only binder-owned review artifacts after the implementation passes review.

- [ ] Obtain independent spec review, then independent code-quality review; fix and re-review every finding.
- [ ] Convert the normalized wave-1 semantic drafts to the new draft contract without changing their semantic decisions.
- [ ] Bind them through the deterministic jobs and run the existing adjudicator.
- [ ] Report closed, failed, disagreement, incompatible, and uncertain counts. Do not admit malformed drafts or claim all 52 DAGs are reviewed.

### Acceptance Criteria

1. `attested=true` means review performed; the verdict carries the result.
2. Approval is possible only with `type_compatibility_verdict=compatible`.
3. Reviewer drafts cannot control graph ID/hash, reviewer kind, or attestations.
4. Jobs and bound reviews fail closed on identity, queue, reviewer, or process mismatch.
5. Generated job authority is byte-identical across repeated builds.
6. Existing semantic-closure behavior and all prior tests remain green.
