from __future__ import annotations

import importlib
import json
from pathlib import Path

import pytest


module = importlib.import_module(
    "scripts.adjudicate_qgis_benchmark_v01_dag_reviews"
)


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
        "process_necessity": [
            {"process_id": "p0", "necessity": "required"}
        ],
        "type_compatibility_attested": True,
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


def test_linear_dag_closes_with_one_valid_hash_bound_review() -> None:
    result = module.apply_reviews(
        [queue_row()], [approved_review("reviewer-a")]
    )

    assert result["rows"][0]["semantic_closure_status"] == "closed"
    assert result["failure_count"] == 0


def test_merge_dag_requires_two_distinct_reviewers() -> None:
    one = module.apply_reviews(
        [queue_row("multi_input_merge")],
        [approved_review("reviewer-a")],
    )
    assert one["rows"][0]["semantic_closure_status"] == (
        "pending_second_review"
    )

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
    assert disagreement["rows"][0]["semantic_closure_status"] == (
        "disagreement"
    )


def test_return_for_revision_does_not_close() -> None:
    revision = module.apply_reviews(
        [queue_row()], [returned_review("reviewer-a")]
    )
    assert revision["rows"][0]["semantic_closure_status"] == (
        "returned_for_revision"
    )


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
def test_invalid_review_contract_fails_closed(
    field: str, value: object
) -> None:
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
