from __future__ import annotations

import importlib
import json
from pathlib import Path

import pytest


module = importlib.import_module("scripts.adjudicate_qgis_benchmark_v01_dag_reviews")
QUEUE_SHA256 = "b" * 64
REVIEWED_AT = "2026-07-31T00:00:00Z"
REVIEWER_IDS = ("reviewer-a", "reviewer-b")


def queue_row(topology: str = "linear") -> dict[str, object]:
    return {
        "canonical_graph_id": "dag-1",
        "canonical_graph_sha256": "a" * 64,
        "topology": topology,
        "processes": [
            {
                "process_id": "p0",
                "operator_id": "native:buffer",
                "stable101_l3": "L3_02_01_01",
            }
        ],
        "links": [],
    }


def approved_review(reviewer_id: str) -> dict[str, object]:
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
        "type_compatibility_verdict": "compatible",
        "rationale": "The operator and output type close the stated intent.",
        "reviewed_at": "2026-07-31T00:00:00Z",
    }


def rejected_review(reviewer_id: str) -> dict[str, object]:
    row = approved_review(reviewer_id)
    row["decision"] = "reject"
    return row


def returned_review(reviewer_id: str) -> dict[str, object]:
    row = approved_review(reviewer_id)
    row["decision"] = "return_for_revision"
    return row


def review_jobs(
    row: dict[str, object] | None = None,
) -> list[dict[str, object]]:
    return module.build_review_jobs(
        [row or queue_row()],
        queue_sha256=QUEUE_SHA256,
        reviewer_ids=REVIEWER_IDS,
        reviewed_at=REVIEWED_AT,
    )


def semantic_draft(
    job: dict[str, object],
    *,
    decision: str = "approve",
    verdict: str = "compatible",
) -> dict[str, object]:
    return {
        "review_job_id": job["review_job_id"],
        "decision": decision,
        "task_intent": "Create a distance zone around the input features.",
        "output_constraint": "The result is a polygon buffer layer.",
        "process_necessity": [
            {"process_id": process_id, "necessity": "required"}
            for process_id in job["process_ids"]
        ],
        "type_compatibility_verdict": verdict,
        "rationale": "The operator and output type close the stated intent.",
    }


def test_linear_dag_closes_with_one_valid_hash_bound_review() -> None:
    result = module.apply_reviews([queue_row()], [approved_review("reviewer-a")])

    assert result["rows"][0]["semantic_closure_status"] == "closed"
    assert result["failure_count"] == 0


def test_merge_dag_requires_two_distinct_reviewers() -> None:
    one = module.apply_reviews(
        [queue_row("multi_input_merge")],
        [approved_review("reviewer-a")],
    )
    assert one["rows"][0]["semantic_closure_status"] == ("pending_second_review")

    two = module.apply_reviews(
        [queue_row("multi_input_merge")],
        [approved_review("reviewer-a"), approved_review("reviewer-b")],
    )
    assert two["rows"][0]["semantic_closure_status"] == "closed"


def test_hash_mismatch_fails_closed() -> None:
    wrong_hash = approved_review("reviewer-a")
    wrong_hash["canonical_graph_sha256"] = "b" * 64
    assert module.apply_reviews([queue_row()], [wrong_hash])["failure_count"] == 1


def test_missing_necessity_fails_closed() -> None:
    missing = approved_review("reviewer-a")
    missing["process_necessity"] = []
    assert module.apply_reviews([queue_row()], [missing])["failure_count"] == 1


def test_merge_disagreement_does_not_close() -> None:
    disagreement = module.apply_reviews(
        [queue_row("multi_input_merge")],
        [approved_review("reviewer-a"), rejected_review("reviewer-b")],
    )
    assert disagreement["rows"][0]["semantic_closure_status"] == ("disagreement")


def test_return_for_revision_does_not_close() -> None:
    revision = module.apply_reviews([queue_row()], [returned_review("reviewer-a")])
    assert revision["rows"][0]["semantic_closure_status"] == ("returned_for_revision")


@pytest.mark.parametrize("verdict", ["incompatible", "uncertain"])
def test_approve_requires_compatible_type_verdict(verdict: str) -> None:
    review = approved_review("reviewer-a")
    review["type_compatibility_verdict"] = verdict

    result = module.apply_reviews([queue_row()], [review])

    assert result["failure_count"] == 1
    assert result["rows"][0]["semantic_closure_status"] == "invalid_review"


@pytest.mark.parametrize(
    ("review_factory", "verdict", "expected_status"),
    [
        (rejected_review, "incompatible", "rejected"),
        (rejected_review, "uncertain", "rejected"),
        (returned_review, "incompatible", "returned_for_revision"),
        (returned_review, "uncertain", "returned_for_revision"),
    ],
)
def test_non_approval_accepts_explicit_type_verdict(
    review_factory: object, verdict: str, expected_status: str
) -> None:
    review = review_factory("reviewer-a")
    review["type_compatibility_verdict"] = verdict

    result = module.apply_reviews([queue_row()], [review])

    assert result["failure_count"] == 0
    assert result["rows"][0]["semantic_closure_status"] == expected_status


@pytest.mark.parametrize("verdict", [None, "", "yes"])
def test_type_verdict_is_required_and_explicit(verdict: object) -> None:
    review = approved_review("reviewer-a")
    if verdict is None:
        del review["type_compatibility_verdict"]
    else:
        review["type_compatibility_verdict"] = verdict

    assert module.apply_reviews([queue_row()], [review])["failure_count"] == 1


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("schema", "wrong-schema"),
        ("reviewer_kind", "human_qgis_reviewer"),
        ("independent_review_attested", False),
        ("type_compatibility_attested", False),
        ("decision", "maybe"),
        ("task_intent", ""),
        ("output_constraint", ""),
        ("rationale", ""),
        ("reviewed_at", "2026-07-31"),
    ],
)
def test_invalid_review_contract_fails_closed(field: str, value: object) -> None:
    review = approved_review("reviewer-a")
    review[field] = value

    result = module.apply_reviews([queue_row()], [review])

    assert result["failure_count"] == 1
    assert result["rows"][0]["semantic_closure_status"] == "invalid_review"


def test_duplicate_review_id_fails_closed() -> None:
    duplicate_id = approved_review("reviewer-b")
    duplicate_id["review_id"] = "review-reviewer-a"
    by_id = module.apply_reviews(
        [queue_row("multi_input_merge")],
        [approved_review("reviewer-a"), duplicate_id],
    )

    assert by_id["failure_count"] == 1


def test_duplicate_reviewer_identity_fails_closed() -> None:
    duplicate_reviewer = approved_review("reviewer-a")
    duplicate_reviewer["review_id"] = "another-review"
    by_reviewer = module.apply_reviews(
        [queue_row("multi_input_merge")],
        [approved_review("reviewer-a"), duplicate_reviewer],
    )

    assert by_reviewer["failure_count"] == 1


@pytest.mark.parametrize(
    "necessity",
    [
        [],
        [{"process_id": "p1", "necessity": "required"}],
        [
            {"process_id": "p0", "necessity": "required"},
            {"process_id": "p0", "necessity": "optional"},
        ],
        [{"process_id": "p0", "necessity": "unknown"}],
    ],
)
def test_process_necessity_must_cover_exact_process_set_once(
    necessity: list[dict[str, str]],
) -> None:
    review = approved_review("reviewer-a")
    review["process_necessity"] = necessity

    result = module.apply_reviews([queue_row()], [review])

    assert result["failure_count"] == 1


def test_unknown_graph_fails_closed() -> None:
    unknown = approved_review("reviewer-a")
    unknown["canonical_graph_id"] = "dag-unknown"

    assert module.apply_reviews([queue_row()], [unknown])["failure_count"] == 1


def test_duplicate_queue_id_fails_closed() -> None:
    with pytest.raises(ValueError, match="duplicate canonical_graph_id"):
        module.apply_reviews([queue_row(), queue_row()], [])


def test_empty_queue_returns_empty_closure_authority() -> None:
    result = module.apply_reviews([], [])

    assert result["rows"] == []
    assert result["failure_count"] == 0
    assert result["summary"]["semantic_closure_status_counts"] == {}


def test_empty_reviews_leave_graph_pending() -> None:
    result = module.apply_reviews([queue_row()], [])

    assert result["rows"][0]["semantic_closure_status"] == "pending_review"
    assert result["summary"]["review_record_count"] == 0


def test_main_initializes_missing_review_ledger(
    tmp_path: Path,
) -> None:
    queue_path = tmp_path / "queue.jsonl"
    reviews_path = tmp_path / "reviews.jsonl"
    summary_path = tmp_path / "summary.json"
    queue_path.write_text(
        json.dumps(queue_row(), sort_keys=True) + "\n",
        encoding="utf-8",
    )

    exit_code = module.main(
        [
            "--queue",
            str(queue_path),
            "--reviews",
            str(reviews_path),
            "--summary",
            str(summary_path),
        ]
    )

    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    assert exit_code == 0
    assert reviews_path.read_bytes() == b""
    assert summary["queue_dag_count"] == 1
    assert summary["review_record_count"] == 0
    assert summary["semantic_closure_status_counts"] == {"pending_review": 1}


def test_review_jobs_are_deterministic_and_bind_queue_identity() -> None:
    once = review_jobs()
    twice = review_jobs()

    assert once == twice
    assert len(once) == 1
    assert set(once[0]) == {
        "schema",
        "review_job_id",
        "queue_sha256",
        "canonical_graph_id",
        "canonical_graph_sha256",
        "topology",
        "process_ids",
        "reviewer_id",
        "reviewed_at",
    }
    assert once[0]["queue_sha256"] == QUEUE_SHA256
    assert once[0]["canonical_graph_id"] == "dag-1"
    assert once[0]["canonical_graph_sha256"] == "a" * 64
    assert once[0]["topology"] == "linear"
    assert once[0]["process_ids"] == ["p0"]
    assert once[0]["reviewer_id"] == "reviewer-a"
    assert once[0]["reviewed_at"] == REVIEWED_AT


def test_merge_review_jobs_assign_two_distinct_reviewers() -> None:
    jobs = review_jobs(queue_row("multi_input_merge"))

    assert [job["reviewer_id"] for job in jobs] == list(REVIEWER_IDS)
    assert len({job["review_job_id"] for job in jobs}) == 2


def test_binder_attaches_only_job_controlled_fields_and_reuses_validator() -> None:
    job = review_jobs()[0]
    draft = semantic_draft(job)

    once = module.bind_review_drafts(
        [queue_row()],
        [job],
        [draft],
        queue_sha256=QUEUE_SHA256,
        reviewer_id="reviewer-a",
    )
    twice = module.bind_review_drafts(
        [queue_row()],
        [job],
        [draft],
        queue_sha256=QUEUE_SHA256,
        reviewer_id="reviewer-a",
    )

    assert once == twice
    assert set(draft) == {
        "review_job_id",
        "decision",
        "task_intent",
        "output_constraint",
        "process_necessity",
        "type_compatibility_verdict",
        "rationale",
    }
    assert once[0] == {
        "schema": module.REVIEW_SCHEMA,
        "review_id": once[0]["review_id"],
        "canonical_graph_id": "dag-1",
        "canonical_graph_sha256": "a" * 64,
        "reviewer_id": "reviewer-a",
        "reviewer_kind": module.REVIEWER_KIND,
        "independent_review_attested": True,
        "decision": "approve",
        "task_intent": draft["task_intent"],
        "output_constraint": draft["output_constraint"],
        "process_necessity": draft["process_necessity"],
        "type_compatibility_attested": True,
        "type_compatibility_verdict": "compatible",
        "rationale": draft["rationale"],
        "reviewed_at": REVIEWED_AT,
    }
    assert module.apply_reviews([queue_row()], once)["failure_count"] == 0


def test_review_id_is_bound_to_review_job_queue_identity() -> None:
    first_job = review_jobs()[0]
    second_job = module.build_review_jobs(
        [queue_row()],
        queue_sha256="c" * 64,
        reviewer_ids=REVIEWER_IDS,
        reviewed_at=REVIEWED_AT,
    )[0]

    first = module.bind_review_drafts(
        [queue_row()],
        [first_job],
        [semantic_draft(first_job)],
        queue_sha256=QUEUE_SHA256,
        reviewer_id="reviewer-a",
    )[0]
    second = module.bind_review_drafts(
        [queue_row()],
        [second_job],
        [semantic_draft(second_job)],
        queue_sha256="c" * 64,
        reviewer_id="reviewer-a",
    )[0]

    assert first["review_id"] != second["review_id"]


@pytest.mark.parametrize(
    ("decision", "verdict"),
    [
        ("reject", "incompatible"),
        ("return_for_revision", "uncertain"),
    ],
)
def test_binder_accepts_explicit_non_approval_type_verdicts(
    decision: str, verdict: str
) -> None:
    job = review_jobs()[0]

    bound = module.bind_review_drafts(
        [queue_row()],
        [job],
        [semantic_draft(job, decision=decision, verdict=verdict)],
        queue_sha256=QUEUE_SHA256,
        reviewer_id="reviewer-a",
    )

    assert bound[0]["type_compatibility_verdict"] == verdict


def test_binder_rejects_unknown_and_duplicate_jobs() -> None:
    job = review_jobs()[0]
    unknown = semantic_draft(job)
    unknown["review_job_id"] = "unknown-job"
    with pytest.raises(ValueError, match="unknown review job"):
        module.bind_review_drafts(
            [queue_row()],
            [job],
            [unknown],
            queue_sha256=QUEUE_SHA256,
            reviewer_id="reviewer-a",
        )

    with pytest.raises(ValueError, match="duplicate review job"):
        module.bind_review_drafts(
            [queue_row()],
            [job, job],
            [],
            queue_sha256=QUEUE_SHA256,
            reviewer_id="reviewer-a",
        )


def test_binder_rejects_duplicate_draft_job() -> None:
    job = review_jobs()[0]
    draft = semantic_draft(job)

    with pytest.raises(ValueError, match="duplicate draft review job"):
        module.bind_review_drafts(
            [queue_row()],
            [job],
            [draft, draft],
            queue_sha256=QUEUE_SHA256,
            reviewer_id="reviewer-a",
        )


def test_binder_rejects_stale_queue_and_wrong_reviewer() -> None:
    job = review_jobs()[0]
    draft = semantic_draft(job)

    with pytest.raises(ValueError, match="stale queue SHA256"):
        module.bind_review_drafts(
            [queue_row()],
            [job],
            [draft],
            queue_sha256="c" * 64,
            reviewer_id="reviewer-a",
        )
    with pytest.raises(ValueError, match="wrong reviewer"):
        module.bind_review_drafts(
            [queue_row()],
            [job],
            [draft],
            queue_sha256=QUEUE_SHA256,
            reviewer_id="reviewer-b",
        )


@pytest.mark.parametrize(
    "process_ids",
    [
        [],
        ["p0", "p1", "p2"],
        ["p0", "p0"],
        ["p1", "p0"],
    ],
)
def test_binder_requires_exact_ordered_process_coverage_once(
    process_ids: list[str],
) -> None:
    row = queue_row()
    row["processes"].append(
        {
            "process_id": "p1",
            "operator_id": "native:dissolve",
            "stable101_l3": "L3_02_03_05",
        }
    )
    job = review_jobs(row)[0]
    draft = semantic_draft(job)
    draft["process_necessity"] = [
        {"process_id": process_id, "necessity": "required"}
        for process_id in process_ids
    ]

    with pytest.raises(ValueError, match="process necessity"):
        module.bind_review_drafts(
            [row],
            [job],
            [draft],
            queue_sha256=QUEUE_SHA256,
            reviewer_id="reviewer-a",
        )


@pytest.mark.parametrize(
    "case",
    [
        "missing_field",
        "extra_field",
        "decision_alias",
        "invalid_verdict",
        "approve_incompatible",
        "extra_process_field",
    ],
)
def test_binder_rejects_malformed_or_semantically_invalid_drafts(
    case: str,
) -> None:
    job = review_jobs()[0]
    draft = semantic_draft(job)
    if case == "missing_field":
        del draft["rationale"]
    elif case == "extra_field":
        draft["canonical_graph_id"] = "dag-1"
    elif case == "decision_alias":
        draft["decision"] = "approved"
    elif case == "invalid_verdict":
        draft["type_compatibility_verdict"] = "yes"
    elif case == "approve_incompatible":
        draft["type_compatibility_verdict"] = "incompatible"
    else:
        draft["process_necessity"][0]["note"] = "required"

    with pytest.raises(ValueError, match="draft"):
        module.bind_review_drafts(
            [queue_row()],
            [job],
            [draft],
            queue_sha256=QUEUE_SHA256,
            reviewer_id="reviewer-a",
        )


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("queue_sha256", "c" * 64),
        ("canonical_graph_id", "dag-unknown"),
        ("canonical_graph_sha256", "c" * 64),
        ("topology", "unknown"),
        ("process_ids", []),
        ("reviewer_id", ""),
        ("reviewed_at", "2026-07-31"),
    ],
)
def test_binder_rejects_tampered_review_jobs(field: str, value: object) -> None:
    job = json.loads(json.dumps(review_jobs()[0]))
    job[field] = value

    with pytest.raises(ValueError, match="review job"):
        module.bind_review_drafts(
            [queue_row()],
            [job],
            [],
            queue_sha256=QUEUE_SHA256,
            reviewer_id="reviewer-a",
        )
