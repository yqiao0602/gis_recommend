# QGIS Benchmark Semantic-Intent Review Sidecar Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a hash-bound, human-reviewed semantic-intent sidecar that blocks semantically unclosed expert QGIS graphs from Gate 3 while preserving parameter-free `processes + links` as the sole scored output.

**Architecture:** A new pure module owns semantic-review schema validation, canonical hashing, risk-based requirement detection, and state application. The existing expert proposal builder orchestrates those results with graph review, Gate 2, human approval, and artifact writing; the Gate 3 candidate builder independently verifies the semantic state before consuming an expert row. The current `expert-v1-008` receives a valid `return_for_revision` sidecar record and remains excluded.

**Tech Stack:** Python 3.12 standard library (`hashlib`, `json`, `re`, `copy`, `pathlib`), JSONL authority artifacts, pytest, existing stable101/Gate 2 builders.

---

## File Structure

- Create `scripts/qgis_benchmark_semantic_intent.py`: pure semantic-review schema, validation, hashing, requirement policy, and state transition functions.
- Create `tests/test_qgis_benchmark_semantic_intent.py`: focused unit tests for closed/non-closed records, hash binding, independence, prohibited facts, and process coverage.
- Modify `scripts/build_qgis_benchmark_expert_proposals.py`: integrate semantic state with proposal emission, technical review concerns, human approval, build summaries, CLI inputs, artifact writing, and hash ledger.
- Modify `tests/test_build_qgis_benchmark_expert_proposals.py`: regression tests for risk-based semantic requirements and approval/admission behavior.
- Modify `scripts/build_qgis_benchmark_candidate_pool.py`: defense-in-depth semantic admission check for expert rows.
- Modify `tests/test_build_qgis_benchmark_candidate_pool.py`: reject an otherwise admitted expert row whose semantic state is pending.
- Create `benchmarks/qgis_planner_v1/authority/expert_semantic_intent_reviews_v1.jsonl`: canonical sidecar ledger containing the `expert-v1-008` return decision.
- Create `benchmarks/qgis_planner_v1/authority/expert_semantic_intent_review_summary_v1.json`: deterministic semantic-review summary.
- Regenerate only existing benchmark authority outputs under `benchmarks/qgis_planner_v1/authority/`.
- Modify benchmark-only sections of `docs/CURRENT_STATE*.md`, `docs/PROJECT_CONTEXT*.md`, `task_plan.md`, `progress.md`, and `docs/reports/qgis_benchmark_expert_human_approval_v1.md`.

### Task 1: Pure Semantic-Review Contract

**Files:**
- Create: `scripts/qgis_benchmark_semantic_intent.py`
- Create: `tests/test_qgis_benchmark_semantic_intent.py`

- [ ] **Step 1: Write failing tests for the complete semantic-review contract**

Create the test module with real proposal/review dictionaries:

```python
from __future__ import annotations

from copy import deepcopy

from scripts.qgis_benchmark_semantic_intent import (
    SEMANTIC_REVIEW_SCHEMA,
    apply_semantic_review,
    emit_semantic_review,
    requires_semantic_review,
    semantic_review_sha256,
    validate_semantic_review,
)


def _proposal(process_count: int = 4) -> dict[str, object]:
    return {
        "proposal_id": "expert-test-001",
        "processes": [
            {"process_id": f"p{index}", "operator_id": "native:buffer"}
            for index in range(process_count)
        ],
        "links": [
            {"source_process_id": f"p{index}", "target_process_id": f"p{index + 1}"}
            for index in range(process_count - 1)
        ],
        "graph_reviewer_ids": ["technical-reviewer-a"],
        "semantic_review_required": process_count >= 4,
        "semantic_review_status": "pending" if process_count >= 4 else "not_required",
    }


def _closed_review(proposal: dict[str, object]) -> dict[str, object]:
    row = {
        "schema": SEMANTIC_REVIEW_SCHEMA,
        "semantic_review_id": "semantic-expert-test-001-v1",
        "proposal_id": proposal["proposal_id"],
        "proposal_graph_sha256": "g" * 64,
        "reviewer_id": "qgis-expert-01",
        "reviewer_kind": "human_qgis_expert",
        "reviewed_at": "2026-07-29T12:00:00Z",
        "semantic_closure_decision": "closed",
        "task_intent": "Create representative points for aggregated areas.",
        "output_constraint": "The output is a collected point geometry.",
        "process_necessity": [
            {"process_id": process["process_id"], "role": "Required transformation."}
            for process in proposal["processes"]
        ],
        "reason_codes": [],
        "rationale": "Every graph step is required by the stated output.",
        "concrete_data_facts_included": False,
        "execution_parameters_included": False,
        "conflict_of_interest_declared": False,
        "qgis_expertise_attested": True,
    }
    row["semantic_review_sha256"] = semantic_review_sha256(row)
    return row


def test_four_processes_require_semantic_review_but_three_do_not() -> None:
    assert requires_semantic_review(_proposal(4)) is True
    assert requires_semantic_review(_proposal(3)) is False
    flagged = _proposal(3)
    flagged["semantic_review_required"] = True
    assert requires_semantic_review(flagged) is True


def test_closed_review_requires_exact_process_coverage_and_applies_closed_state() -> None:
    proposal = _proposal()
    review = _closed_review(proposal)

    assert validate_semantic_review(proposal, review, graph_sha256="g" * 64) == []
    emitted = emit_semantic_review(proposal, review, graph_sha256="g" * 64)
    updated = apply_semantic_review(proposal, emitted, graph_sha256="g" * 64)

    assert updated["semantic_review_status"] == "closed"
    assert updated["semantic_review_ref"] == review["semantic_review_id"]


def test_return_for_revision_represents_missing_evidence_without_filler_text() -> None:
    proposal = _proposal()
    review = _closed_review(proposal)
    review.update(
        {
            "semantic_closure_decision": "return_for_revision",
            "task_intent": None,
            "output_constraint": None,
            "process_necessity": [],
            "reason_codes": [
                "task_intent_missing",
                "output_constraint_missing",
                "process_necessity_missing",
            ],
            "rationale": "The graph has no auditable semantic intent evidence.",
        }
    )
    review["semantic_review_sha256"] = semantic_review_sha256(review)

    assert validate_semantic_review(proposal, review, graph_sha256="g" * 64) == []
    updated = apply_semantic_review(proposal, review, graph_sha256="g" * 64)
    assert updated["semantic_review_status"] == "returned_for_revision"


def test_stale_hash_ai_reviewer_conflict_and_concrete_facts_fail_closed() -> None:
    proposal = _proposal()
    review = _closed_review(proposal)
    stale = deepcopy(review)
    stale["proposal_graph_sha256"] = "0" * 64
    ai = deepcopy(review)
    ai["reviewer_kind"] = "ai_independent_technical"
    conflict = deepcopy(review)
    conflict["reviewer_id"] = "technical-reviewer-a"
    concrete = deepcopy(review)
    concrete["concrete_data_facts_included"] = True

    assert "semantic_review_graph_sha256_mismatch" in validate_semantic_review(
        proposal, stale, graph_sha256="g" * 64
    )
    assert "semantic_review_reviewer_kind_invalid" in validate_semantic_review(
        proposal, ai, graph_sha256="g" * 64
    )
    assert "semantic_review_not_independent" in validate_semantic_review(
        proposal, conflict, graph_sha256="g" * 64
    )
    assert "semantic_review_concrete_data_facts_included" in validate_semantic_review(
        proposal, concrete, graph_sha256="g" * 64
    )
```

- [ ] **Step 2: Run the new tests and verify RED**

Run:

```powershell
rtk proxy D:\01_software\02_DevelopmentKits\Python\Anaconda3\python.exe -m pytest tests/test_qgis_benchmark_semantic_intent.py -q
```

Expected: collection fails because `scripts.qgis_benchmark_semantic_intent` does not exist.

- [ ] **Step 3: Implement the pure module**

Create `scripts/qgis_benchmark_semantic_intent.py` with these public functions and stable error codes:

```python
from __future__ import annotations

from copy import deepcopy
import hashlib
import json
import re
from typing import Any


SEMANTIC_REVIEW_SCHEMA = "gis_recommend.qgis_benchmark_semantic_intent_review.v1"
SEMANTIC_DECISIONS = {"closed", "return_for_revision", "rejected"}
SEMANTIC_REASON_CODES = {
    "task_intent_missing",
    "output_constraint_missing",
    "process_necessity_missing",
    "process_necessity_incomplete",
    "output_semantics_ambiguous",
    "step_not_necessary",
    "semantic_contradiction",
    "prohibited_concrete_fact",
}
SEMANTIC_REQUIRED_FIELDS = {
    "schema",
    "semantic_review_id",
    "proposal_id",
    "proposal_graph_sha256",
    "reviewer_id",
    "reviewer_kind",
    "reviewed_at",
    "semantic_closure_decision",
    "task_intent",
    "output_constraint",
    "process_necessity",
    "reason_codes",
    "rationale",
    "concrete_data_facts_included",
    "execution_parameters_included",
    "conflict_of_interest_declared",
    "qgis_expertise_attested",
}
SEMANTIC_ALLOWED_FIELDS = SEMANTIC_REQUIRED_FIELDS | {"semantic_review_sha256"}
SEMANTIC_NESTED_FORBIDDEN_FIELDS = {
    "dataset_id",
    "field_name",
    "threshold",
    "crs",
    "source_path",
    "source_snippet",
    "parameter_facts",
}
_REASON_RE = re.compile(r"^[a-z][a-z0-9_]*$")


def _canonical_hash(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        .encode("utf-8")
    ).hexdigest()


def _nested_keys(value: Any) -> set[str]:
    if isinstance(value, dict):
        return set(value) | {key for child in value.values() for key in _nested_keys(child)}
    if isinstance(value, list):
        return {key for child in value for key in _nested_keys(child)}
    return set()


def _non_empty_text(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def requires_semantic_review(proposal: dict[str, Any]) -> bool:
    return len(proposal.get("processes", [])) >= 4 or proposal.get(
        "semantic_review_required"
    ) is True


def semantic_review_sha256(review: dict[str, Any]) -> str:
    canonical = {key: value for key, value in review.items() if key != "semantic_review_sha256"}
    return _canonical_hash(canonical)


def validate_semantic_review(
    proposal: dict[str, Any], review: dict[str, Any], *, graph_sha256: str
) -> list[str]:
    if not isinstance(review, dict):
        return ["semantic_review_not_object"]
    errors = [
        f"semantic_review_missing_field:{field}"
        for field in sorted(SEMANTIC_REQUIRED_FIELDS.difference(review))
    ]
    errors.extend(
        f"semantic_review_unknown_field:{field}"
        for field in sorted(set(review).difference(SEMANTIC_ALLOWED_FIELDS))
    )
    if review.get("schema") != SEMANTIC_REVIEW_SCHEMA:
        errors.append("semantic_review_schema_invalid")
    if review.get("proposal_id") != proposal.get("proposal_id"):
        errors.append("semantic_review_proposal_id_mismatch")
    if review.get("proposal_graph_sha256") != graph_sha256:
        errors.append("semantic_review_graph_sha256_mismatch")
    for field in ("semantic_review_id", "reviewer_id", "reviewed_at", "rationale"):
        if field in review and not _non_empty_text(review.get(field)):
            errors.append(f"semantic_review_{field}_invalid")
    if review.get("reviewer_kind") != "human_qgis_expert":
        errors.append("semantic_review_reviewer_kind_invalid")
    if review.get("reviewer_id") in proposal.get("graph_reviewer_ids", []):
        errors.append("semantic_review_not_independent")
    if review.get("conflict_of_interest_declared") is not False:
        errors.append("semantic_review_conflict_of_interest_invalid")
    if review.get("qgis_expertise_attested") is not True:
        errors.append("semantic_review_qgis_expertise_not_attested")
    if review.get("concrete_data_facts_included") is not False:
        errors.append("semantic_review_concrete_data_facts_included")
    if review.get("execution_parameters_included") is not False:
        errors.append("semantic_review_execution_parameters_included")
    if _nested_keys(review).intersection(SEMANTIC_NESTED_FORBIDDEN_FIELDS):
        errors.append("semantic_review_forbidden_fact_field")

    decision = review.get("semantic_closure_decision")
    if decision not in SEMANTIC_DECISIONS:
        errors.append("semantic_review_decision_invalid")
    reasons = review.get("reason_codes")
    if not isinstance(reasons, list) or any(
        reason not in SEMANTIC_REASON_CODES or _REASON_RE.fullmatch(str(reason)) is None
        for reason in reasons or []
    ):
        errors.append("semantic_review_reason_codes_invalid")
        reasons = []

    necessities = review.get("process_necessity")
    if not isinstance(necessities, list):
        errors.append("semantic_review_process_necessity_invalid")
        necessities = []
    process_ids = [str(process.get("process_id", "")) for process in proposal.get("processes", [])]
    necessity_ids = [
        str(item.get("process_id", ""))
        for item in necessities
        if isinstance(item, dict)
    ]
    necessity_shape_valid = all(
        isinstance(item, dict)
        and set(item) == {"process_id", "role"}
        and _non_empty_text(item.get("role"))
        for item in necessities
    )
    if necessities and not necessity_shape_valid:
        errors.append("semantic_review_process_necessity_invalid")

    if decision == "closed":
        if not _non_empty_text(review.get("task_intent")):
            errors.append("semantic_review_task_intent_required")
        if not _non_empty_text(review.get("output_constraint")):
            errors.append("semantic_review_output_constraint_required")
        if necessity_ids != process_ids or len(set(necessity_ids)) != len(process_ids):
            errors.append("semantic_review_process_coverage_mismatch")
        if reasons:
            errors.append("semantic_review_closed_with_reason_codes")
    elif decision in {"return_for_revision", "rejected"} and not reasons:
        errors.append("semantic_review_nonclosed_reason_required")

    supplied_hash = review.get("semantic_review_sha256")
    if supplied_hash is not None and supplied_hash != semantic_review_sha256(review):
        errors.append("semantic_review_sha256_mismatch")
    return list(dict.fromkeys(errors))


def emit_semantic_review(
    proposal: dict[str, Any], review: dict[str, Any], *, graph_sha256: str
) -> dict[str, Any]:
    errors = validate_semantic_review(proposal, review, graph_sha256=graph_sha256)
    if errors:
        raise ValueError("invalid semantic review: " + ",".join(errors))
    emitted = deepcopy(review)
    emitted["semantic_review_sha256"] = semantic_review_sha256(emitted)
    return emitted


def apply_semantic_review(
    proposal: dict[str, Any], review: dict[str, Any], *, graph_sha256: str
) -> dict[str, Any]:
    emitted = emit_semantic_review(proposal, review, graph_sha256=graph_sha256)
    updated = deepcopy(proposal)
    updated["semantic_review_status"] = {
        "closed": "closed",
        "return_for_revision": "returned_for_revision",
        "rejected": "rejected",
    }[emitted["semantic_closure_decision"]]
    updated["semantic_review_ref"] = emitted["semantic_review_id"]
    updated["semantic_reviewer_id"] = emitted["reviewer_id"]
    return updated
```

- [ ] **Step 4: Run focused tests and verify GREEN**

Run the Step 2 command again. Expected: all tests in `test_qgis_benchmark_semantic_intent.py` pass.

- [ ] **Step 5: Commit the pure contract**

```powershell
rtk git add -- scripts/qgis_benchmark_semantic_intent.py tests/test_qgis_benchmark_semantic_intent.py
rtk git commit -m "Fail closed on ungrounded expert graph semantics" -m "Constraint: Semantic review remains separate from parameter-free graph gold." -m "Confidence: high" -m "Scope-risk: narrow" -m "Tested: focused semantic-intent unit tests"
```

### Task 2: Proposal and Approval State-Machine Integration

**Files:**
- Modify: `scripts/build_qgis_benchmark_expert_proposals.py:18-240`
- Modify: `scripts/build_qgis_benchmark_expert_proposals.py:430-560`
- Modify: `tests/test_build_qgis_benchmark_expert_proposals.py`

- [ ] **Step 1: Add failing proposal and approval state tests**

Append tests that require four-step graphs or technical reviewer concerns to close semantic review before approval:

```python
def test_four_step_proposal_starts_semantic_review_pending() -> None:
    mapping, catalog = _authorities()
    row = _valid_row()
    row["processes"] = [
        {"process_id": f"p{index}", "operator_id": "native:buffer", "l3_code": "L3_02_01_01"}
        for index in range(4)
    ]
    row["links"] = [
        {"source_process_id": f"p{index}", "target_process_id": f"p{index + 1}"}
        for index in range(3)
    ]
    row["covered_l3"] = ["L3_02_01_01"]
    row["graph_size_stratum"] = "four_to_six"
    row["target_strata"]["graph_size_stratum"] = "four_to_six"

    emitted = emit_proposal(row, mapping_by_operator=mapping, catalog_by_operator=catalog)

    assert emitted["semantic_review_required"] is True
    assert emitted["semantic_review_status"] == "pending"
    assert emitted["supply_admission"] == "proposal_only"


def test_smaller_graph_can_be_flagged_by_technical_reviewer() -> None:
    proposal = _approval_ready_proposal()
    review = _valid_review(proposal, reviewer_id="reviewer-b")
    review["semantic_review_required"] = True
    review["semantic_concern_reason"] = "The output purpose is ambiguous."

    updated = apply_review(proposal, review)

    assert updated["semantic_review_required"] is True
    assert updated["semantic_review_status"] == "pending"
    assert updated["supply_admission"] == "proposal_only"


def test_human_approve_requires_closed_semantic_review_but_return_is_allowed() -> None:
    proposal = _approval_ready_proposal()
    proposal["semantic_review_required"] = True
    proposal["semantic_review_status"] = "pending"
    queue = expert_module.build_human_approval_queue(
        [proposal], gate2_exclusion_sha256="e" * 64
    )[0]
    approve = _valid_human_approval(queue)
    returned = dict(approve)
    returned["approval_id"] = "human-return-proposal-001-v1"
    returned["decision"] = "return_for_revision"

    assert "approval_semantic_review_not_closed" in expert_module.validate_human_approval(
        proposal, queue, approve
    )
    assert expert_module.validate_human_approval(proposal, queue, returned) == []
```

- [ ] **Step 2: Run the three new tests and verify RED**

```powershell
rtk proxy D:\01_software\02_DevelopmentKits\Python\Anaconda3\python.exe -m pytest tests/test_build_qgis_benchmark_expert_proposals.py -q
```

Expected: failures for missing semantic state fields and approval guard.

- [ ] **Step 3: Integrate semantic fields into proposal and technical review state**

Import `requires_semantic_review`, then update admission and proposal emission:

```python
from scripts.qgis_benchmark_semantic_intent import requires_semantic_review


def _semantic_gate_passed(row: dict[str, Any]) -> bool:
    return row.get("semantic_review_status") in {"closed", "not_required"}


def _refresh_admission(row: dict[str, Any]) -> None:
    admitted = (
        row.get("graph_review_status") == "independent_reviewed"
        and row.get("gate1_status") == "passed"
        and row.get("gate2_status") == "passed"
        and row.get("dedup_status") == "canonical"
        and _semantic_gate_passed(row)
        and row.get("human_approval_status") == "approved"
    )
    row["supply_admission"] = (
        "gate3_candidate_admitted" if admitted else "proposal_only"
    )
```

In `emit_proposal`, derive the initial state:

```python
semantic_required = requires_semantic_review(emitted)
emitted["semantic_review_required"] = semantic_required
emitted["semantic_review_status"] = "pending" if semantic_required else "not_required"
```

In `validate_review`, allow the optional technical concern fields only when they are well formed:

```python
if "semantic_review_required" in review and not isinstance(
    review.get("semantic_review_required"), bool
):
    errors.append("review_semantic_review_required_invalid")
if review.get("semantic_review_required") is True and not (
    isinstance(review.get("semantic_concern_reason"), str)
    and review["semantic_concern_reason"].strip()
):
    errors.append("review_semantic_concern_reason_required")
```

In `apply_review`, preserve concerns monotonically:

```python
if review.get("semantic_review_required") is True:
    updated["semantic_review_required"] = True
    updated["semantic_review_status"] = "pending"
    updated["semantic_concern_reason"] = review["semantic_concern_reason"]
```

- [ ] **Step 4: Guard human approval without suppressing revision/rejection records**

Add this validation after the decision enum check:

```python
if (
    approval.get("decision") == "approve"
    and proposal.get("semantic_review_status") not in {"closed", "not_required"}
):
    errors.append("approval_semantic_review_not_closed")
```

Do not remove pending semantic proposals from the immutable approval queue: `return_for_revision` and `reject` must remain representable.

- [ ] **Step 5: Run proposal tests and verify GREEN**

Run the Step 2 command. Expected: all existing and new expert proposal tests pass.

- [ ] **Step 6: Commit the state-machine integration**

```powershell
rtk git add -- scripts/build_qgis_benchmark_expert_proposals.py tests/test_build_qgis_benchmark_expert_proposals.py
rtk git commit -m "Require semantic closure before expert approval" -m "Constraint: Return and reject decisions remain valid before closure so missing evidence is auditable." -m "Confidence: high" -m "Scope-risk: moderate" -m "Tested: expert proposal and approval state regressions"
```

### Task 3: Builder, Artifact, and Hash-Ledger Integration

**Files:**
- Modify: `scripts/build_qgis_benchmark_expert_proposals.py:720-1015`
- Modify: `tests/test_build_qgis_benchmark_expert_proposals.py`

- [ ] **Step 1: Write failing build/output tests**

Extend the byte-stability test and add one real semantic review application:

```python
def _valid_semantic_review(
    proposal: dict[str, object], *, decision: str
) -> dict[str, object]:
    from scripts.qgis_benchmark_semantic_intent import semantic_review_sha256

    graph_sha = expert_module.proposal_graph_sha256(proposal)
    review = {
        "schema": "gis_recommend.qgis_benchmark_semantic_intent_review.v1",
        "semantic_review_id": "semantic-review-proposal-001-v1",
        "proposal_id": proposal["proposal_id"],
        "proposal_graph_sha256": graph_sha,
        "reviewer_id": "qgis-expert-01",
        "reviewer_kind": "human_qgis_expert",
        "reviewed_at": "2026-07-29T12:00:00Z",
        "semantic_closure_decision": decision,
        "task_intent": None,
        "output_constraint": None,
        "process_necessity": [],
        "reason_codes": ["task_intent_missing"],
        "rationale": "The proposal has no auditable semantic intent.",
        "concrete_data_facts_included": False,
        "execution_parameters_included": False,
        "conflict_of_interest_declared": False,
        "qgis_expertise_attested": True,
    }
    if decision == "closed":
        review.update(
            {
                "task_intent": "Create a transformed planning layer.",
                "output_constraint": "The output is one vector layer.",
                "process_necessity": [
                    {"process_id": process["process_id"], "role": "Required transformation."}
                    for process in proposal["processes"]
                ],
                "reason_codes": [],
            }
        )
    review["semantic_review_sha256"] = semantic_review_sha256(review)
    return review


def test_build_applies_one_hash_bound_semantic_review(tmp_path: Path) -> None:
    proposal = _approval_ready_proposal()
    proposal["semantic_review_required"] = True
    proposal["semantic_review_status"] = "pending"
    review = _valid_semantic_review(proposal, decision="return_for_revision")

    updated, failures, emitted_reviews = expert_module.apply_semantic_reviews(
        [proposal], [review]
    )

    assert failures == []
    assert emitted_reviews[0]["semantic_review_sha256"]
    assert updated[0]["semantic_review_status"] == "returned_for_revision"
    assert updated[0]["supply_admission"] == "proposal_only"
```

Update the expected output set:

```python
assert set(first_paths) == {
    "expert_proposals",
    "expert_proposal_reviews",
    "expert_human_approval_queue",
    "expert_human_approvals",
    "expert_semantic_intent_reviews",
    "expert_semantic_intent_review_summary",
    "expert_proposal_summary",
    "expert_proposal_hash_ledger",
}
```

- [ ] **Step 2: Run the expert builder tests and verify RED**

Use the Task 2 Step 2 command. Expected: missing `apply_semantic_reviews` and new output keys.

- [ ] **Step 3: Implement deterministic semantic review aggregation**

Import the pure contract and add a helper that applies at most one valid review
per proposal while recording duplicate/stale failures:

```python
from scripts.qgis_benchmark_semantic_intent import (
    apply_semantic_review,
    emit_semantic_review,
    validate_semantic_review,
)


def apply_semantic_reviews(
    proposals: list[dict[str, Any]], semantic_rows: list[dict[str, Any]]
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    rows = [deepcopy(row) for row in proposals]
    row_index = {str(row["proposal_id"]): index for index, row in enumerate(rows)}
    grouped: dict[str, list[dict[str, Any]]] = {}
    for review in semantic_rows:
        grouped.setdefault(str(review.get("proposal_id", "")), []).append(review)
    failures: list[dict[str, Any]] = []
    emitted_reviews: list[dict[str, Any]] = []
    for proposal_id, reviews in sorted(grouped.items()):
        if proposal_id not in row_index:
            failures.append(
                {"proposal_id": proposal_id, "error_codes": ["semantic_review_proposal_not_found"]}
            )
            continue
        if len(reviews) != 1:
            failures.append(
                {"proposal_id": proposal_id, "error_codes": ["semantic_review_duplicate_decisions"]}
            )
            continue
        proposal = rows[row_index[proposal_id]]
        graph_sha = proposal_graph_sha256(proposal)
        errors = validate_semantic_review(proposal, reviews[0], graph_sha256=graph_sha)
        if errors:
            failures.append({"proposal_id": proposal_id, "error_codes": errors})
            continue
        emitted = emit_semantic_review(proposal, reviews[0], graph_sha256=graph_sha)
        rows[row_index[proposal_id]] = apply_semantic_review(
            proposal, emitted, graph_sha256=graph_sha
        )
        _refresh_admission(rows[row_index[proposal_id]])
        emitted_reviews.append(emitted)
    return rows, failures, emitted_reviews
```

Call this after proposal deduplication and before human approvals. Keep the generated approval queue independent so non-closed return/reject decisions remain valid.

- [ ] **Step 4: Add CLI and output artifacts**

Add `semantic_review_path` to `build_expert_proposals`, a CLI option defaulting to `authority / "expert_semantic_intent_reviews_v1.jsonl"`, and output paths:

```python
"expert_semantic_intent_reviews": output_dir / "expert_semantic_intent_reviews_v1.jsonl",
"expert_semantic_intent_review_summary": output_dir / "expert_semantic_intent_review_summary_v1.json",
```

Write a canonical ledger header plus emitted records, and a summary with:

```python
semantic_summary = {
    "schema": "gis_recommend.qgis_benchmark_semantic_intent_review_summary.v1",
    "review_count": len(emitted_semantic_reviews),
    "failure_count": len(semantic_failures),
    "failures": semantic_failures,
    "status_counts": dict(
        sorted(Counter(row["semantic_review_status"] for row in rows).items())
    ),
    "admission_flags": {
        "training_admission": False,
        "validation_eligible": False,
        "test_eligible": False,
        "production_merge": False,
    },
}
```

Include both artifact hashes in `expert_proposal_hash_ledger_v1.json` and semantic input/failure/count fields in `expert_proposal_summary_v1.json`.

- [ ] **Step 5: Run builder tests and deterministic two-directory comparison**

Run the Task 2 Step 2 command. Expected: all tests pass and every output in the expanded path set is byte-identical between two builds.

- [ ] **Step 6: Commit artifact integration**

```powershell
rtk git add -- scripts/build_qgis_benchmark_expert_proposals.py tests/test_build_qgis_benchmark_expert_proposals.py
rtk git commit -m "Bind semantic reviews into benchmark authority artifacts" -m "Constraint: Sidecar evidence is hashed but excluded from candidate graph rows and gold outputs." -m "Confidence: high" -m "Scope-risk: moderate" -m "Tested: builder aggregation, duplicate failure, artifact, hash, and byte-stability tests"
```

### Task 4: Gate 3 Defense and `expert-v1-008` Authority Record

**Files:**
- Modify: `scripts/build_qgis_benchmark_candidate_pool.py:350-430`
- Modify: `tests/test_build_qgis_benchmark_candidate_pool.py`
- Create: `benchmarks/qgis_planner_v1/authority/expert_semantic_intent_reviews_v1.jsonl`
- Create: `benchmarks/qgis_planner_v1/authority/expert_semantic_intent_review_summary_v1.json`
- Regenerate: `benchmarks/qgis_planner_v1/authority/expert_proposals_v1.jsonl`
- Regenerate: `benchmarks/qgis_planner_v1/authority/expert_proposal_summary_v1.json`
- Regenerate: `benchmarks/qgis_planner_v1/authority/expert_proposal_hash_ledger_v1.json`
- Regenerate: `benchmarks/qgis_planner_v1/authority/candidate_supply.jsonl`
- Regenerate: `benchmarks/qgis_planner_v1/authority/candidate_supply_summary.json`

- [ ] **Step 1: Write the failing Gate 3 defense test**

Update the accepted fixture with `semantic_review_status="not_required"`, then add:

```python
def test_optional_expert_input_rejects_pending_semantic_review(tmp_path: Path) -> None:
    module = _module()
    mapping_path = tmp_path / "mapping.json"
    catalog_path = tmp_path / "catalog.json"
    capability_path = tmp_path / "capability.jsonl"
    exclusion_path = tmp_path / "exclusion.jsonl"
    expert_path = tmp_path / "experts.jsonl"
    mapping_path.write_text(json.dumps({"entries": [{
        "operator_id": "native:buffer", "strict_catalog_present": True,
        "mapping_status": "stable101_direct", "stable101_l3": "L3_02_01_01",
        "headline_eligible": True, "task_role": "analytical",
    }]}), encoding="utf-8")
    catalog_path.write_text(json.dumps({"operators": [{
        "operator_id": "native:buffer", "input_types": ["vector"],
        "output_types": ["vector"],
    }]}), encoding="utf-8")
    capability_path.write_text("", encoding="utf-8")
    exclusion_path.write_text("", encoding="utf-8")
    expert = {
        "proposal_id": "expert-pending-semantic", "provenance_class": "expert_authored",
        "processes": [{"process_id": "p0", "operator_id": "native:buffer", "l3_code": "L3_02_01_01"}],
        "links": [], "parameters_included": False, "quota_anchor_l3": "L3_02_01_01",
        "covered_l3": ["L3_02_01_01"], "modality": "vector", "topology": "linear",
        "graph_size_stratum": "one_step", "normalized_dag_key": "dag-1",
        "forbidden_near_dag_key": "near-1", "semantic_dag_key": "semantic-1",
        "graph_review_status": "independent_reviewed", "gate1_status": "passed",
        "gate2_status": "passed", "dedup_status": "canonical",
        "human_approval_status": "approved", "supply_admission": "gate3_candidate_admitted",
        "semantic_review_required": True, "semantic_review_status": "pending",
    }
    expert_path.write_text(json.dumps(expert) + "\n", encoding="utf-8")

    result = module.build(
        root=tmp_path,
        discovery_pools=(),
        mapping_path=mapping_path,
        catalog_path=catalog_path,
        capability_path=capability_path,
        exclusion_path=exclusion_path,
        expert_proposals_path=expert_path,
    )

    assert result["summary"]["candidate_count"] == 0
    assert result["summary"]["rejection_counts"] == {
        "expert_proposal_not_fully_admitted": 1
    }
```

- [ ] **Step 2: Run candidate-pool tests and verify RED**

```powershell
rtk proxy D:\01_software\02_DevelopmentKits\Python\Anaconda3\python.exe -m pytest tests/test_build_qgis_benchmark_candidate_pool.py -q
```

Expected: the pending semantic expert row is incorrectly accepted.

- [ ] **Step 3: Add semantic defense to expert adapter**

Extend `required_state`:

```python
and proposal.get("semantic_review_status") in {"closed", "not_required"}
```

Run the Step 2 command again. Expected: all candidate-pool tests pass.

- [ ] **Step 4: Add the real `expert-v1-008` return record**

Create the JSONL ledger with a schema header and this hash-bound raw record; the builder adds `semantic_review_sha256` canonically:

```json
{"record_type":"schema_header","review_count":1,"schema":"gis_recommend.qgis_benchmark_semantic_intent_review_ledger.v1"}
{"concrete_data_facts_included":false,"conflict_of_interest_declared":false,"execution_parameters_included":false,"output_constraint":null,"process_necessity":[],"proposal_graph_sha256":"c4eac879d8bc46b30d01115484e031d2e95d56a2a622bdd33969fe99369082f2","proposal_id":"expert-v1-008","qgis_expertise_attested":true,"rationale":"The final dissolve-to-split-to-centroids-to-collect segment is type-compatible, but no task intent or output constraint proves that the collected point output is necessary.","reason_codes":["task_intent_missing","output_constraint_missing","process_necessity_missing"],"reviewed_at":"2026-07-29T10:19:23Z","reviewer_id":"qgis-expert-01","reviewer_kind":"human_qgis_expert","schema":"gis_recommend.qgis_benchmark_semantic_intent_review.v1","semantic_closure_decision":"return_for_revision","semantic_review_id":"semantic-review-expert-v1-008-v1","task_intent":null}
```

- [ ] **Step 5: Rebuild proposal and Gate 3 authorities**

```powershell
rtk proxy D:\01_software\02_DevelopmentKits\Python\Anaconda3\python.exe -m scripts.build_qgis_benchmark_expert_proposals
rtk proxy D:\01_software\02_DevelopmentKits\Python\Anaconda3\python.exe -m scripts.build_qgis_benchmark_candidate_pool --expert-proposals benchmarks/qgis_planner_v1/authority/expert_proposals_v1.jsonl
```

Expected outputs:

```text
proposals=8 reviewed=4 admitted=3
candidates=149 sources=90 dags=52 status=failed_insufficient_candidate_supply
```

Assert `expert-v1-008.semantic_review_status=returned_for_revision`, its sidecar hash is present, semantic failures are zero, and it does not appear in candidate supply. Assert candidate rows contain none of `task_intent`, `output_constraint`, `process_necessity`, `rationale`, or `reason_codes`.

- [ ] **Step 6: Rebuild a second time and compare authority hashes**

Run Step 5 again. Expected: the semantic ledger, semantic summary, expert proposals, expert summary, hash ledger, candidate supply, and candidate summary hashes are unchanged.

- [ ] **Step 7: Commit Gate 3 defense and authority artifacts**

```powershell
rtk git add -- scripts/build_qgis_benchmark_candidate_pool.py tests/test_build_qgis_benchmark_candidate_pool.py benchmarks/qgis_planner_v1/authority/expert_semantic_intent_reviews_v1.jsonl benchmarks/qgis_planner_v1/authority/expert_semantic_intent_review_summary_v1.json benchmarks/qgis_planner_v1/authority/expert_proposals_v1.jsonl benchmarks/qgis_planner_v1/authority/expert_proposal_summary_v1.json benchmarks/qgis_planner_v1/authority/expert_proposal_hash_ledger_v1.json benchmarks/qgis_planner_v1/authority/candidate_supply.jsonl benchmarks/qgis_planner_v1/authority/candidate_supply_summary.json
rtk git commit -m "Keep unclosed expert graphs out of Gate 3" -m "Constraint: expert-v1-008 remains proposal-only until a materially revised graph completes every review gate." -m "Confidence: high" -m "Scope-risk: moderate" -m "Tested: candidate adapter regressions, two-pass authority rebuild, and leakage-field assertions"
```

### Task 5: Benchmark Memory and Final Verification

**Files:**
- Modify benchmark sections only: `docs/CURRENT_STATE.md`
- Modify benchmark sections only: `docs/CURRENT_STATE.zh-CN.md`
- Modify benchmark sections only: `docs/PROJECT_CONTEXT.md`
- Modify benchmark sections only: `docs/PROJECT_CONTEXT.zh-CN.md`
- Modify benchmark section only: `task_plan.md`
- Append milestone only: `progress.md`
- Modify: `docs/reports/qgis_benchmark_expert_human_approval_v1.md`

- [ ] **Step 1: Update benchmark-only project memory**

Record these exact conclusions without rewriting GEE or QGIS data-processing sections:

```text
Semantic-intent sidecar v1 is active for graphs with >=4 processes or a technical reviewer concern.
001/006/007 remain approved and admitted because their semantic status is not_required.
008 has one valid return_for_revision semantic record and remains proposal_only.
Gate 3 remains 149 candidates, 90 source authorities, 52 distinct DAGs, failed_insufficient_candidate_supply.
No development/final/refusal/gold row or family roster was created.
```

- [ ] **Step 2: Run all focused benchmark tests**

```powershell
rtk proxy D:\01_software\02_DevelopmentKits\Python\Anaconda3\python.exe -m pytest tests/test_qgis_benchmark_semantic_intent.py tests/test_build_qgis_benchmark_expert_proposals.py tests/test_build_qgis_benchmark_candidate_pool.py tests/test_build_qgis_benchmark_exclusion_ledger.py tests/test_package_qgis_benchmark_release_artifact.py -q
```

Expected: all selected tests pass with zero failures.

- [ ] **Step 3: Run static and artifact invariants**

```powershell
rtk proxy D:\01_software\02_DevelopmentKits\Python\Anaconda3\python.exe -m py_compile scripts/qgis_benchmark_semantic_intent.py scripts/build_qgis_benchmark_expert_proposals.py scripts/build_qgis_benchmark_candidate_pool.py
rtk git diff --check -- scripts/qgis_benchmark_semantic_intent.py scripts/build_qgis_benchmark_expert_proposals.py scripts/build_qgis_benchmark_candidate_pool.py tests/test_qgis_benchmark_semantic_intent.py tests/test_build_qgis_benchmark_expert_proposals.py tests/test_build_qgis_benchmark_candidate_pool.py benchmarks/qgis_planner_v1/authority docs/CURRENT_STATE.md docs/CURRENT_STATE.zh-CN.md docs/PROJECT_CONTEXT.md docs/PROJECT_CONTEXT.zh-CN.md docs/reports/qgis_benchmark_expert_human_approval_v1.md task_plan.md progress.md
```

Expected: `py_compile` exits zero and `git diff --check` produces no output.

- [ ] **Step 4: Verify final authority values programmatically**

Use a read-only Python assertion that checks:

```python
assert expert_summary["semantic_review_failure_count"] == 0
assert expert_summary["admitted_expert_count"] == 3
assert candidate_summary["candidate_count"] == 149
assert candidate_summary["provenance_counts"] == {
    "expert_authored": 3,
    "qgis_source_backed": 146,
}
assert candidate_summary["gate_status"] == "failed_insufficient_candidate_supply"
assert proposal_008["semantic_review_status"] == "returned_for_revision"
assert proposal_008["supply_admission"] == "proposal_only"
assert not any(row.get("proposal_ref") == "expert-v1-008" for row in candidates)
```

- [ ] **Step 5: Commit benchmark documentation**

```powershell
rtk git add -- docs/CURRENT_STATE.md docs/CURRENT_STATE.zh-CN.md docs/PROJECT_CONTEXT.md docs/PROJECT_CONTEXT.zh-CN.md docs/reports/qgis_benchmark_expert_human_approval_v1.md task_plan.md progress.md
rtk git commit -m "Keep benchmark handoff aligned with semantic review authority" -m "Constraint: Shared documentation changes are limited to benchmark sections." -m "Confidence: high" -m "Scope-risk: narrow" -m "Tested: focused tests, compile, artifact assertions, and diff checks"
```

## Completion Boundary

This plan is complete when the sidecar validator and artifacts are active, `expert-v1-008` is machine-recorded as returned and excluded, Gate 3 deterministically remains at 149 rows, and no scored/gold split exists. Creating a replacement for `008`, adding more expert proposals, solving family quotas, or opening Gate 4 is a subsequent benchmark phase.
