from __future__ import annotations

import pytest

from scripts.qgis_benchmark_semantic_intent import (
    SEMANTIC_REASON_CODES,
    SEMANTIC_REVIEW_SCHEMA,
    apply_semantic_review,
    emit_semantic_review,
    requires_semantic_review,
    semantic_review_sha256,
    validate_semantic_review,
)


GRAPH_SHA256 = "g" * 64


def _proposal(process_count: int = 4) -> dict[str, object]:
    return {
        "schema": "gis_recommend.qgis_benchmark_expert_proposal.v1",
        "proposal_id": "proposal-semantic-001",
        "processes": [
            {
                "process_id": f"p{index}",
                "operator_id": "native:buffer",
                "l3_code": "L3_02_01_01",
            }
            for index in range(process_count)
        ],
        "links": [
            {
                "source_process_id": f"p{index}",
                "target_process_id": f"p{index + 1}",
            }
            for index in range(process_count - 1)
        ],
        "graph_reviewer_ids": ["graph-reviewer-01"],
    }


def _closed_review(proposal: dict[str, object]) -> dict[str, object]:
    return {
        "schema": SEMANTIC_REVIEW_SCHEMA,
        "semantic_review_id": "semantic-review-proposal-semantic-001-v1",
        "proposal_id": proposal["proposal_id"],
        "proposal_graph_sha256": GRAPH_SHA256,
        "reviewer_id": "qgis-expert-01",
        "reviewer_kind": "human_qgis_expert",
        "reviewed_at": "2026-07-29T12:00:00Z",
        "semantic_closure_decision": "closed",
        "task_intent": "Create a final accessibility analysis layer.",
        "output_constraint": "The result must preserve the intended spatial unit.",
        "process_necessity": [
            {
                "process_id": process["process_id"],
                "role": f"Necessary semantic stage {index + 1}.",
            }
            for index, process in enumerate(proposal["processes"])
        ],
        "reason_codes": [],
        "rationale": "Every graph step is necessary for the stated intent and output.",
        "concrete_data_facts_included": False,
        "execution_parameters_included": False,
        "conflict_of_interest_declared": False,
        "qgis_expertise_attested": True,
    }


def test_semantic_review_requirement_uses_graph_size_or_explicit_flag() -> None:
    assert requires_semantic_review(_proposal(4)) is True
    assert requires_semantic_review(_proposal(3)) is False

    flagged = _proposal(3)
    flagged["semantic_review_required"] = True
    assert requires_semantic_review(flagged) is True


def test_closed_review_validates_emits_and_applies_closed_state() -> None:
    proposal = _proposal()
    review = _closed_review(proposal)

    assert validate_semantic_review(
        proposal, review, graph_sha256=GRAPH_SHA256
    ) == []

    emitted = emit_semantic_review(proposal, review, graph_sha256=GRAPH_SHA256)
    assert emitted is not review
    assert emitted["semantic_review_sha256"] == semantic_review_sha256(review)

    applied = apply_semantic_review(proposal, review, graph_sha256=GRAPH_SHA256)
    assert applied is not proposal
    assert applied["semantic_review_status"] == "closed"
    assert applied["semantic_review_ref"] == review["semantic_review_id"]
    assert applied["semantic_reviewer_id"] == "qgis-expert-01"
    assert applied["processes"] == proposal["processes"]
    assert "semantic_review_status" not in proposal


def test_return_for_revision_allows_unresolved_semantics_with_reasons() -> None:
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
            "rationale": "The proposal cannot yet be closed semantically.",
        }
    )

    assert validate_semantic_review(
        proposal, review, graph_sha256=GRAPH_SHA256
    ) == []
    applied = apply_semantic_review(proposal, review, graph_sha256=GRAPH_SHA256)
    assert applied["semantic_review_status"] == "returned_for_revision"


@pytest.mark.parametrize(
    ("mutation", "expected_error"),
    [
        (
            {"proposal_graph_sha256": "0" * 64},
            "semantic_review_proposal_graph_sha256_mismatch",
        ),
        (
            {"reviewer_kind": "ai_independent_technical"},
            "semantic_review_reviewer_kind_invalid",
        ),
        (
            {"reviewer_id": "graph-reviewer-01"},
            "semantic_review_not_independent_from_graph_review",
        ),
        (
            {"concrete_data_facts_included": True},
            "semantic_review_concrete_data_facts_included",
        ),
    ],
)
def test_semantic_review_fails_closed_on_binding_or_authority_violation(
    mutation: dict[str, object], expected_error: str
) -> None:
    proposal = _proposal()
    review = _closed_review(proposal)
    review.update(mutation)

    assert expected_error in validate_semantic_review(
        proposal, review, graph_sha256=GRAPH_SHA256
    )


def test_forbidden_nested_facts_and_unknown_top_level_fields_are_rejected() -> None:
    proposal = _proposal()
    review = _closed_review(proposal)
    review["extra"] = "not in the contract"
    review["process_necessity"][0]["parameter_facts"] = {"threshold": 10}

    errors = validate_semantic_review(proposal, review, graph_sha256=GRAPH_SHA256)

    assert "semantic_review_unknown_field:extra" in errors
    assert "semantic_review_forbidden_field:parameter_facts" in errors
    assert "semantic_review_forbidden_field:threshold" in errors


def test_closed_review_requires_ordered_process_coverage_and_no_reasons() -> None:
    proposal = _proposal()
    review = _closed_review(proposal)
    review["process_necessity"] = list(reversed(review["process_necessity"]))
    review["reason_codes"] = ["process_necessity_incomplete"]

    errors = validate_semantic_review(proposal, review, graph_sha256=GRAPH_SHA256)

    assert "semantic_review_process_necessity_coverage_mismatch" in errors
    assert "semantic_review_closed_with_reason_codes" in errors


def test_rejected_review_requires_a_known_well_formed_reason_code() -> None:
    proposal = _proposal()
    review = _closed_review(proposal)
    review.update(
        {
            "semantic_closure_decision": "rejected",
            "task_intent": None,
            "output_constraint": None,
            "process_necessity": [],
            "reason_codes": [],
        }
    )
    assert "semantic_review_reason_codes_required" in validate_semantic_review(
        proposal, review, graph_sha256=GRAPH_SHA256
    )

    review["reason_codes"] = ["Not_Well_Formed"]
    errors = validate_semantic_review(proposal, review, graph_sha256=GRAPH_SHA256)
    assert "semantic_review_reason_code_format_invalid:Not_Well_Formed" in errors
    assert "semantic_review_reason_code_unknown:Not_Well_Formed" in errors
    assert "semantic_contradiction" in SEMANTIC_REASON_CODES


def test_supplied_semantic_hash_must_match_and_emit_rejects_invalid_review() -> None:
    proposal = _proposal()
    review = _closed_review(proposal)
    review["semantic_review_sha256"] = "f" * 64

    errors = validate_semantic_review(proposal, review, graph_sha256=GRAPH_SHA256)
    assert errors == ["semantic_review_sha256_mismatch"]
    with pytest.raises(
        ValueError,
        match="^invalid semantic review: semantic_review_sha256_mismatch$",
    ):
        emit_semantic_review(proposal, review, graph_sha256=GRAPH_SHA256)


def test_missing_and_unknown_fields_are_sorted_and_non_object_is_stable() -> None:
    proposal = _proposal()
    assert validate_semantic_review(proposal, None, graph_sha256=GRAPH_SHA256) == [
        "semantic_review_not_object"
    ]

    review = _closed_review(proposal)
    review.pop("schema")
    review.pop("reviewed_at")
    review["z_unknown"] = True
    review["a_unknown"] = True

    errors = validate_semantic_review(proposal, review, graph_sha256=GRAPH_SHA256)
    assert errors[:4] == [
        "semantic_review_missing_field:reviewed_at",
        "semantic_review_missing_field:schema",
        "semantic_review_unknown_field:a_unknown",
        "semantic_review_unknown_field:z_unknown",
    ]
