from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path

from scripts import build_qgis_benchmark_expert_proposals as expert_module
from scripts.build_qgis_benchmark_expert_proposals import (
    REVIEW_SCHEMA,
    SCHEMA,
    apply_gate2,
    apply_review,
    build_expert_proposals,
    deduplicate_proposals,
    emit_proposal,
    graph_fingerprints,
    graph_profile,
    validate_review,
    validate_proposal,
    write_expert_outputs,
)
from scripts.qgis_benchmark_semantic_intent import (
    SEMANTIC_REVIEW_SCHEMA,
    semantic_review_sha256,
)


def _authorities() -> tuple[dict[str, dict[str, object]], dict[str, dict[str, object]]]:
    mapping = {
        "native:buffer": {
            "l3_code": "L3_02_01_01",
            "mapping_status": "stable101_direct",
            "headline_eligible": True,
        },
        "native:nonheadline": {
            "l3_code": "L3_02_01_02",
            "mapping_status": "stable101_direct",
            "headline_eligible": False,
        },
    }
    catalog = {
        "native:buffer": {
            "operator_id": "native:buffer",
            "input_types": ["vector"],
            "output_types": ["vector"],
        },
        "native:nonheadline": {
            "operator_id": "native:nonheadline",
            "input_types": ["vector"],
            "output_types": ["vector"],
        },
    }
    return mapping, catalog


def _valid_row() -> dict[str, object]:
    return {
        "schema": SCHEMA,
        "proposal_id": "proposal-001",
        "authoring_batch_id": "expert_authoring_batch_v1",
        "provenance_class": "expert_authored",
        "inspiration_class": "none",
        "processes": [
            {
                "process_id": "p0",
                "operator_id": "native:buffer",
                "l3_code": "L3_02_01_01",
            }
        ],
        "links": [],
        "parameters_included": False,
        "quota_anchor_l3": "L3_02_01_01",
        "covered_l3": ["L3_02_01_01"],
        "modality": "vector",
        "topology": "linear",
        "graph_size_stratum": "one_step",
        "target_strata": {
            "anchor_family": "vector_overlay",
            "modality": "vector",
            "topology": "linear",
            "graph_size_stratum": "one_step",
        },
    }


def _linear_row(
    process_count: int, *, graph_size_stratum: str
) -> dict[str, object]:
    row = _valid_row()
    row["processes"] = [
        {
            "process_id": f"p{index}",
            "operator_id": "native:buffer",
            "l3_code": "L3_02_01_01",
        }
        for index in range(process_count)
    ]
    row["links"] = [
        {"source_process_id": f"p{index}", "target_process_id": f"p{index + 1}"}
        for index in range(process_count - 1)
    ]
    row["graph_size_stratum"] = graph_size_stratum
    row["target_strata"]["graph_size_stratum"] = graph_size_stratum
    return row


def _four_step_row() -> dict[str, object]:
    return _linear_row(4, graph_size_stratum="four_to_six")


def test_valid_parameter_free_proposal_emits_closed_review_only_row() -> None:
    mapping, catalog = _authorities()
    row = _valid_row()

    assert validate_proposal(
        row, mapping_by_operator=mapping, catalog_by_operator=catalog
    ) == []

    emitted = emit_proposal(
        row, mapping_by_operator=mapping, catalog_by_operator=catalog
    )
    assert emitted["schema"] == SCHEMA
    assert emitted["provenance_class"] == "expert_authored"
    assert emitted["parameters_included"] is False
    assert emitted["graph_review_status"] == "unreviewed"
    assert emitted["gate2_status"] == "pending"
    assert emitted["semantic_review_required"] is False
    assert emitted["semantic_review_status"] == "not_required"
    assert emitted["supply_admission"] == "proposal_only"
    assert emitted["review_refs"] == []
    assert emitted["training_admission"] is False
    assert emitted["validation_eligible"] is False
    assert emitted["test_eligible"] is False
    assert emitted["production_merge"] is False


def test_four_step_proposal_requires_pending_semantic_review() -> None:
    mapping, catalog = _authorities()

    emitted = emit_proposal(
        _four_step_row(), mapping_by_operator=mapping, catalog_by_operator=catalog
    )

    assert emitted["semantic_review_required"] is True
    assert emitted["semantic_review_status"] == "pending"
    assert emitted["supply_admission"] == "proposal_only"


def test_seven_step_proposal_also_requires_pending_semantic_review() -> None:
    mapping, catalog = _authorities()

    emitted = emit_proposal(
        _linear_row(7, graph_size_stratum="seven_plus"),
        mapping_by_operator=mapping,
        catalog_by_operator=catalog,
    )

    assert emitted["semantic_review_required"] is True
    assert emitted["semantic_review_status"] == "pending"
    assert emitted["supply_admission"] == "proposal_only"


def test_task_text_is_rejected_with_stable_error_code() -> None:
    mapping, catalog = _authorities()
    row = _valid_row()
    row["task_text"] = "buffer the roads"

    assert validate_proposal(
        row, mapping_by_operator=mapping, catalog_by_operator=catalog
    ) == ["forbidden_field:task_text"]


def test_nonheadline_operator_is_rejected_with_stable_error_code() -> None:
    mapping, catalog = _authorities()
    row = _valid_row()
    row["processes"] = [
        {
            "process_id": "p0",
            "operator_id": "native:nonheadline",
            "l3_code": "L3_02_01_02",
        }
    ]
    row["quota_anchor_l3"] = "L3_02_01_02"
    row["covered_l3"] = ["L3_02_01_02"]

    assert validate_proposal(
        row, mapping_by_operator=mapping, catalog_by_operator=catalog
    ) == ["operator_not_headline_eligible:native:nonheadline"]


def test_invalid_process_id_and_unknown_link_are_rejected_deterministically() -> None:
    mapping, catalog = _authorities()
    row = deepcopy(_valid_row())
    row["processes"] = [
        {
            "process_id": "bad id",
            "operator_id": "native:buffer",
            "l3_code": "L3_02_01_01",
        }
    ]
    row["links"] = [{"source_process_id": "bad id", "target_process_id": "p9"}]

    assert validate_proposal(
        row, mapping_by_operator=mapping, catalog_by_operator=catalog
    ) == [
        "invalid_process_id:bad id",
        "link_unknown_source:bad id",
        "link_unknown_target:p9",
    ]


def test_graph_profile_reuses_gate3_contract_for_topology_and_size() -> None:
    assert graph_profile(1, []) == {
        "graph_size_stratum": "one_step",
        "topology": "linear",
    }
    assert graph_profile(3, [(0, 1), (1, 2)]) == {
        "graph_size_stratum": "two_to_three",
        "topology": "linear",
    }
    assert graph_profile(4, [(0, 1), (0, 2), (2, 3)]) == {
        "graph_size_stratum": "four_to_six",
        "topology": "branch_or_multi_output",
    }
    assert graph_profile(7, [(index, index + 1) for index in range(6)]) == {
        "graph_size_stratum": "seven_plus",
        "topology": "linear",
    }
    assert graph_profile(3, [(0, 1)]) is None
    assert graph_profile(2, [(0, 1), (1, 0)]) is None


def test_derived_graph_labels_must_match_deterministic_recomputation() -> None:
    mapping, catalog = _authorities()
    row = _valid_row()
    row["topology"] = "branch_or_multi_output"

    assert validate_proposal(
        row, mapping_by_operator=mapping, catalog_by_operator=catalog
    ) == ["topology_mismatch:linear"]


def _valid_review(
    proposal: dict[str, object], *, reviewer_id: str = "reviewer-a"
) -> dict[str, object]:
    return {
        "schema": REVIEW_SCHEMA,
        "review_id": f"review-{reviewer_id}",
        "proposal_id": proposal["proposal_id"],
        "reviewer_id": reviewer_id,
        "reviewer_kind": "ai_independent_technical",
        "approval_authority": False,
        "reviewed_at": "2026-07-29T00:00:00Z",
        "decision": "accept",
        "checked_operator_ids": [
            process["operator_id"] for process in proposal["processes"]
        ],
        "checked_links": proposal["links"],
        "strata_verdicts": {
            "modality": True,
            "topology": True,
            "graph_size_stratum": True,
        },
        "exclusion_verdict": "pending_gate2",
        "reason": "Graph structure is executable in principle.",
    }


def test_simple_accept_review_cannot_bypass_pending_gate2() -> None:
    mapping, catalog = _authorities()
    proposal = emit_proposal(
        _valid_row(), mapping_by_operator=mapping, catalog_by_operator=catalog
    )

    updated = apply_review(proposal, _valid_review(proposal))

    assert updated["graph_review_status"] == "independent_reviewed"
    assert updated["human_approval_status"] == "pending"
    assert updated["gate2_status"] == "pending"
    assert updated["supply_admission"] == "proposal_only"
    assert updated["processes"] == proposal["processes"]
    assert updated["links"] == proposal["links"]


def test_rejected_proposal_cannot_transition_back_to_reviewed() -> None:
    mapping, catalog = _authorities()
    proposal = emit_proposal(
        _valid_row(), mapping_by_operator=mapping, catalog_by_operator=catalog
    )
    rejection = _valid_review(proposal)
    rejection["decision"] = "reject"
    rejected = apply_review(proposal, rejection)

    accepted_later = apply_review(rejected, _valid_review(rejected, reviewer_id="reviewer-b"))

    assert accepted_later["graph_review_status"] == "rejected"
    assert accepted_later["supply_admission"] == "proposal_only"


def test_conflicting_simple_reviews_require_revision_regardless_of_order() -> None:
    mapping, catalog = _authorities()
    proposal = emit_proposal(
        _valid_row(), mapping_by_operator=mapping, catalog_by_operator=catalog
    )
    acceptance = _valid_review(proposal, reviewer_id="reviewer-a")
    revision = _valid_review(proposal, reviewer_id="reviewer-b")
    revision["decision"] = "revise"

    accept_then_revise = apply_review(apply_review(proposal, acceptance), revision)
    revise_then_accept = apply_review(apply_review(proposal, revision), acceptance)

    assert accept_then_revise["graph_review_status"] == "revision_required"
    assert revise_then_accept["graph_review_status"] == "revision_required"
    assert accept_then_revise["graph_reviewer_ids"] == ["reviewer-a", "reviewer-b"]
    assert revise_then_accept["graph_reviewer_ids"] == ["reviewer-b", "reviewer-a"]
    assert accept_then_revise["supply_admission"] == "proposal_only"
    assert revise_then_accept["supply_admission"] == "proposal_only"


def test_complex_graph_requires_two_distinct_reviewers() -> None:
    mapping, catalog = _authorities()
    row = _valid_row()
    row["processes"] = [
        {"process_id": "p0", "operator_id": "native:buffer", "l3_code": "L3_02_01_01"},
        {"process_id": "p1", "operator_id": "native:buffer", "l3_code": "L3_02_01_01"},
        {"process_id": "p2", "operator_id": "native:buffer", "l3_code": "L3_02_01_01"},
    ]
    row["links"] = [
        {"source_process_id": "p0", "target_process_id": "p2"},
        {"source_process_id": "p1", "target_process_id": "p2"},
    ]
    row["topology"] = "multi_input_merge"
    row["graph_size_stratum"] = "two_to_three"
    row["target_strata"]["topology"] = "multi_input_merge"
    row["target_strata"]["graph_size_stratum"] = "two_to_three"
    proposal = emit_proposal(row, mapping_by_operator=mapping, catalog_by_operator=catalog)

    assert proposal["quota_credit_eligible"] is True

    once = apply_review(proposal, _valid_review(proposal, reviewer_id="reviewer-a"))
    repeated = apply_review(once, _valid_review(once, reviewer_id="reviewer-a"))
    twice = apply_review(repeated, _valid_review(repeated, reviewer_id="reviewer-b"))

    assert once["graph_review_status"] == "unreviewed"
    assert repeated["graph_review_status"] == "unreviewed"
    assert twice["graph_review_status"] == "independent_reviewed"
    assert twice["graph_reviewer_ids"] == ["reviewer-a", "reviewer-b"]


def test_multi_sink_branch_is_not_eligible_for_arbitrary_family_credit() -> None:
    mapping, catalog = _authorities()
    row = _valid_row()
    row["processes"] = [
        {"process_id": "p0", "operator_id": "native:buffer", "l3_code": "L3_02_01_01"},
        {"process_id": "p1", "operator_id": "native:buffer", "l3_code": "L3_02_01_01"},
        {"process_id": "p2", "operator_id": "native:buffer", "l3_code": "L3_02_01_01"},
    ]
    row["links"] = [
        {"source_process_id": "p0", "target_process_id": "p1"},
        {"source_process_id": "p0", "target_process_id": "p2"},
    ]
    row["topology"] = "branch_or_multi_output"
    row["graph_size_stratum"] = "two_to_three"
    row["target_strata"]["topology"] = "branch_or_multi_output"
    row["target_strata"]["graph_size_stratum"] = "two_to_three"

    proposal = emit_proposal(row, mapping_by_operator=mapping, catalog_by_operator=catalog)

    assert proposal["quota_credit_eligible"] is False


def test_review_schema_reports_missing_evidence_with_stable_codes() -> None:
    mapping, catalog = _authorities()
    proposal = emit_proposal(
        _valid_row(), mapping_by_operator=mapping, catalog_by_operator=catalog
    )
    review = _valid_review(proposal)
    review.pop("checked_links")
    review["strata_verdicts"] = {"modality": True}

    assert validate_review(proposal, review) == [
        "review_missing_field:checked_links",
        "review_strata_verdict_missing:graph_size_stratum",
        "review_strata_verdict_missing:topology",
    ]


def test_review_semantic_concern_requires_boolean_flag_and_nonempty_reason() -> None:
    mapping, catalog = _authorities()
    proposal = emit_proposal(
        _valid_row(), mapping_by_operator=mapping, catalog_by_operator=catalog
    )
    invalid_shape = _valid_review(proposal)
    invalid_shape["semantic_review_required"] = "yes"
    missing_reason = _valid_review(proposal)
    missing_reason["semantic_review_required"] = True

    assert validate_review(proposal, invalid_shape) == [
        "review_semantic_review_required_invalid"
    ]
    assert validate_review(proposal, missing_reason) == [
        "review_semantic_concern_reason_required"
    ]


def test_reviewer_concern_for_smaller_graph_is_monotonic() -> None:
    mapping, catalog = _authorities()
    proposal = emit_proposal(
        _valid_row(), mapping_by_operator=mapping, catalog_by_operator=catalog
    )
    concern = _valid_review(proposal, reviewer_id="reviewer-a")
    concern["semantic_review_required"] = True
    concern["semantic_concern_reason"] = "The output intent is ambiguous."

    concerned = apply_review(proposal, concern)
    accepted_later = apply_review(
        concerned, _valid_review(concerned, reviewer_id="reviewer-b")
    )

    assert concerned["semantic_review_required"] is True
    assert concerned["semantic_review_status"] == "pending"
    assert concerned["supply_admission"] == "proposal_only"
    assert accepted_later["semantic_review_required"] is True
    assert accepted_later["semantic_review_status"] == "pending"
    assert accepted_later["supply_admission"] == "proposal_only"


def test_gate2_graph_collision_is_recorded_and_blocks_admission() -> None:
    mapping, catalog = _authorities()
    proposal = emit_proposal(
        _valid_row(), mapping_by_operator=mapping, catalog_by_operator=catalog
    )
    reviewed = apply_review(proposal, _valid_review(proposal))
    fingerprints = graph_fingerprints(reviewed)
    exclusion_rows = [
        {
            "record_type": "exclusion",
            "normalized_dag_key": fingerprints["normalized_dag_key"],
            "forbidden_near_dag_key": "",
            "semantic_dag_key": "",
        }
    ]

    collided = apply_gate2(reviewed, exclusion_rows)

    assert collided["gate2_status"] == "failed_overlap"
    assert collided["gate2_overlap_fields"] == ["normalized_dag_key"]
    assert collided["supply_admission"] == "proposal_only"


def test_clean_gate2_check_stays_closed_until_dedup_is_canonical() -> None:
    mapping, catalog = _authorities()
    proposal = emit_proposal(
        _valid_row(), mapping_by_operator=mapping, catalog_by_operator=catalog
    )
    reviewed = apply_review(proposal, _valid_review(proposal))

    clean = apply_gate2(reviewed, [])

    assert clean["gate2_status"] == "passed"
    assert clean["gate2_overlap_fields"] == []
    assert clean["supply_admission"] == "proposal_only"


def test_clean_gate2_and_canonical_dedup_stay_closed_without_human_approval() -> None:
    mapping, catalog = _authorities()
    proposal = emit_proposal(
        _valid_row(), mapping_by_operator=mapping, catalog_by_operator=catalog
    )
    reviewed = apply_review(proposal, _valid_review(proposal))
    screened = apply_gate2(reviewed, [])

    canonical, suppressions = deduplicate_proposals([screened])

    assert suppressions == []
    assert canonical[0]["dedup_status"] == "canonical"
    assert canonical[0]["human_approval_status"] == "pending"
    assert canonical[0]["supply_admission"] == "proposal_only"


def _approval_ready_proposal() -> dict[str, object]:
    mapping, catalog = _authorities()
    proposal = emit_proposal(
        _valid_row(), mapping_by_operator=mapping, catalog_by_operator=catalog
    )
    reviewed = apply_review(proposal, _valid_review(proposal))
    screened = apply_gate2(reviewed, [])
    canonical, _ = deduplicate_proposals([screened])
    return canonical[0]


def _valid_human_approval(queue: dict[str, object]) -> dict[str, object]:
    return {
        "schema": "gis_recommend.qgis_benchmark_expert_human_approval.v1",
        "approval_id": "human-approval-proposal-001-v1",
        "proposal_id": queue["proposal_id"],
        "queue_record_sha256": queue["queue_record_sha256"],
        "proposal_graph_sha256": queue["proposal_graph_sha256"],
        "gate2_exclusion_sha256": queue["gate2_exclusion_sha256"],
        "approver_id": "qgis-expert-01",
        "approver_kind": "human_qgis_expert",
        "decided_at": "2026-07-29T12:00:00Z",
        "decision": "approve",
        "rationale": "The reviewed graph is suitable for benchmark supply.",
        "conflict_of_interest_declared": False,
        "qgis_expertise_attested": True,
    }


def _valid_semantic_review(
    proposal: dict[str, object],
    *,
    decision: str = "closed",
    review_id: str = "semantic-review-proposal-001-v1",
) -> dict[str, object]:
    review = {
        "schema": SEMANTIC_REVIEW_SCHEMA,
        "semantic_review_id": review_id,
        "proposal_id": proposal["proposal_id"],
        "proposal_graph_sha256": expert_module.proposal_graph_sha256(proposal),
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
                    {
                        "process_id": process["process_id"],
                        "role": "Required transformation.",
                    }
                    for process in proposal["processes"]
                ],
                "reason_codes": [],
                "rationale": (
                    "Every process is necessary for the declared output layer."
                ),
            }
        )
    review["semantic_review_sha256"] = semantic_review_sha256(review)
    return review


def test_apply_semantic_reviews_closes_review_and_refreshes_admission() -> None:
    proposal = _approval_ready_proposal()
    proposal["human_approval_status"] = "approved"
    proposal["semantic_review_required"] = True
    proposal["semantic_review_status"] = "pending"
    review = _valid_semantic_review(proposal)

    updated, failures, emitted_reviews = expert_module.apply_semantic_reviews(
        [proposal], [review]
    )

    assert proposal["semantic_review_status"] == "pending"
    assert failures == []
    assert [row["semantic_review_id"] for row in emitted_reviews] == [
        "semantic-review-proposal-001-v1"
    ]
    assert emitted_reviews[0] is not review
    assert emitted_reviews[0]["semantic_review_sha256"] == semantic_review_sha256(
        review
    )
    assert updated[0]["semantic_review_status"] == "closed"
    assert updated[0]["semantic_review_ref"] == review["semantic_review_id"]
    assert updated[0]["semantic_reviewer_id"] == "qgis-expert-01"
    assert updated[0]["supply_admission"] == "gate3_candidate_admitted"
    assert updated[0]["processes"] == proposal["processes"]
    assert updated[0]["links"] == proposal["links"]


def test_apply_semantic_reviews_missing_duplicate_and_stale_fail_closed() -> None:
    proposal = _approval_ready_proposal()
    proposal["semantic_review_required"] = True
    proposal["semantic_review_status"] = "pending"
    stale_proposal = deepcopy(proposal)
    stale_proposal["proposal_id"] = "proposal-002"
    missing = _valid_semantic_review(proposal, review_id="semantic-review-missing")
    missing["proposal_id"] = "proposal-missing"
    missing["semantic_review_sha256"] = semantic_review_sha256(missing)
    duplicate_a = _valid_semantic_review(proposal, review_id="semantic-review-a")
    duplicate_b = _valid_semantic_review(proposal, review_id="semantic-review-b")
    stale = _valid_semantic_review(stale_proposal, review_id="semantic-review-stale")
    stale["proposal_graph_sha256"] = "0" * 64
    stale["semantic_review_sha256"] = semantic_review_sha256(stale)

    updated, failures, emitted_reviews = expert_module.apply_semantic_reviews(
        [proposal, stale_proposal],
        [missing, duplicate_b, stale, duplicate_a],
    )

    assert emitted_reviews == []
    assert updated[0]["semantic_review_status"] == "pending"
    assert updated[1]["semantic_review_status"] == "pending"
    assert failures == [
        {
            "proposal_id": "proposal-001",
            "error_codes": ["semantic_review_duplicate_decisions"],
        },
        {
            "proposal_id": "proposal-002",
            "semantic_review_id": "semantic-review-stale",
            "error_codes": ["semantic_review_proposal_graph_sha256_mismatch"],
        },
        {
            "proposal_id": "proposal-missing",
            "semantic_review_id": "semantic-review-missing",
            "error_codes": ["semantic_review_proposal_not_found"],
        },
    ]


def test_apply_semantic_reviews_surfaces_schema_and_independence_errors() -> None:
    proposal = _approval_ready_proposal()
    proposal["semantic_review_required"] = True
    proposal["semantic_review_status"] = "pending"
    review = _valid_semantic_review(proposal)
    review["schema"] = "invalid"
    review["reviewer_id"] = "reviewer-a"
    review["semantic_review_sha256"] = semantic_review_sha256(review)

    updated, failures, emitted_reviews = expert_module.apply_semantic_reviews(
        [proposal], [review]
    )

    assert emitted_reviews == []
    assert updated[0]["semantic_review_status"] == "pending"
    assert failures == [
        {
            "proposal_id": "proposal-001",
            "semantic_review_id": "semantic-review-proposal-001-v1",
            "error_codes": [
                "semantic_review_schema_invalid",
                "semantic_review_not_independent_from_graph_review",
            ],
        }
    ]


def test_human_approval_queue_contains_only_reviewed_zero_overlap_candidates() -> None:
    ready = _approval_ready_proposal()
    blocked = dict(ready)
    blocked["proposal_id"] = "proposal-blocked"
    blocked["gate2_status"] = "pending"

    queue = expert_module.build_human_approval_queue(
        [blocked, ready], gate2_exclusion_sha256="e" * 64
    )

    assert [row["proposal_id"] for row in queue] == ["proposal-001"]
    assert queue[0]["proposal_graph_sha256"]
    assert queue[0]["queue_record_sha256"]
    assert queue[0]["processes"] == ready["processes"]
    assert queue[0]["links"] == ready["links"]
    assert queue[0]["topology"] == ready["topology"]
    assert queue[0]["graph_size_stratum"] == ready["graph_size_stratum"]
    assert queue[0]["gate2_exclusion_sha256"] == "e" * 64
    assert queue[0]["technical_review_refs"] == ["review-reviewer-a"]
    assert queue[0]["approval_status"] == "pending_human"
    assert queue[0]["approver_id"] is None
    assert queue[0]["decision"] is None
    assert queue[0]["decided_at"] is None
    assert queue[0]["rationale"] is None


def test_semantic_pending_proposal_remains_in_human_approval_queue() -> None:
    mapping, catalog = _authorities()
    proposal = emit_proposal(
        _four_step_row(), mapping_by_operator=mapping, catalog_by_operator=catalog
    )
    reviewed = apply_review(proposal, _valid_review(proposal))
    screened = apply_gate2(reviewed, [])
    canonical, _ = deduplicate_proposals([screened])

    queue = expert_module.build_human_approval_queue(
        canonical, gate2_exclusion_sha256="e" * 64
    )

    assert [row["proposal_id"] for row in queue] == ["proposal-001"]
    assert queue[0]["semantic_review_required"] is True
    assert queue[0]["semantic_review_status"] == "pending"


def test_approve_is_blocked_until_semantic_review_closes_but_return_is_allowed() -> None:
    mapping, catalog = _authorities()
    proposal = emit_proposal(
        _four_step_row(), mapping_by_operator=mapping, catalog_by_operator=catalog
    )
    reviewed = apply_review(proposal, _valid_review(proposal))
    screened = apply_gate2(reviewed, [])
    canonical, _ = deduplicate_proposals([screened])
    proposal = canonical[0]
    queue = expert_module.build_human_approval_queue(
        [proposal], gate2_exclusion_sha256="e" * 64
    )[0]
    approval = _valid_human_approval(queue)
    returned = dict(approval)
    returned["decision"] = "return_for_revision"
    rejected = dict(approval)
    rejected["decision"] = "reject"

    assert expert_module.validate_human_approval(proposal, queue, approval) == [
        "approval_semantic_review_not_closed"
    ]
    assert expert_module.validate_human_approval(proposal, queue, returned) == []
    assert expert_module.validate_human_approval(proposal, queue, rejected) == []


def test_admission_refresh_requires_closed_semantics_after_human_approval() -> None:
    mapping, catalog = _authorities()
    proposal = emit_proposal(
        _four_step_row(), mapping_by_operator=mapping, catalog_by_operator=catalog
    )
    proposal["semantic_review_status"] = "closed"
    reviewed = apply_review(proposal, _valid_review(proposal))
    screened = apply_gate2(reviewed, [])
    canonical, _ = deduplicate_proposals([screened])
    proposal = canonical[0]
    queue = expert_module.build_human_approval_queue(
        [proposal], gate2_exclusion_sha256="e" * 64
    )[0]

    approved = expert_module.apply_human_approval(
        proposal, queue, _valid_human_approval(queue)
    )
    assert approved["supply_admission"] == "gate3_candidate_admitted"

    pending = deepcopy(approved)
    pending["semantic_review_status"] = "pending"
    refreshed = apply_gate2(pending, [])

    assert refreshed["human_approval_status"] == "approved"
    assert refreshed["supply_admission"] == "proposal_only"


def test_valid_human_approval_is_bound_to_queue_and_admits_candidate() -> None:
    proposal = _approval_ready_proposal()
    queue = expert_module.build_human_approval_queue(
        [proposal], gate2_exclusion_sha256="e" * 64
    )[0]
    approval = _valid_human_approval(queue)

    updated = expert_module.apply_human_approval(proposal, queue, approval)

    assert updated["human_approval_status"] == "approved"
    assert updated["human_approval_ref"] == approval["approval_id"]
    assert updated["supply_admission"] == "gate3_candidate_admitted"


def test_ai_or_stale_human_approval_fails_closed() -> None:
    proposal = _approval_ready_proposal()
    queue = expert_module.build_human_approval_queue(
        [proposal], gate2_exclusion_sha256="e" * 64
    )[0]
    ai_approval = _valid_human_approval(queue)
    ai_approval["approver_kind"] = "ai_independent_technical"
    stale_approval = _valid_human_approval(queue)
    stale_approval["proposal_graph_sha256"] = "0" * 64

    assert expert_module.validate_human_approval(
        proposal, queue, ai_approval
    ) == ["approval_approver_kind_invalid"]
    assert expert_module.validate_human_approval(
        proposal, queue, stale_approval
    ) == ["approval_proposal_graph_sha256_mismatch"]


def test_four_layer_dedup_keeps_first_deterministic_proposal() -> None:
    mapping, catalog = _authorities()
    first = emit_proposal(
        _valid_row(), mapping_by_operator=mapping, catalog_by_operator=catalog
    )
    second_row = _valid_row()
    second_row["proposal_id"] = "proposal-002"
    second = emit_proposal(
        second_row, mapping_by_operator=mapping, catalog_by_operator=catalog
    )

    canonical, suppressions = deduplicate_proposals([second, first])

    assert [row["proposal_id"] for row in canonical] == ["proposal-001"]
    assert canonical[0]["dedup_status"] == "canonical"
    assert suppressions == [
        {
            "proposal_id": "proposal-002",
            "canonical_proposal_id": "proposal-001",
            "reason_code": "duplicate_canonical_graph_identity",
        }
    ]


def test_build_outputs_are_byte_stable_and_keep_all_admissions_closed(
    tmp_path: Path,
) -> None:
    mapping, catalog = _authorities()
    row = _valid_row()
    batch_path = tmp_path / "batch.jsonl"
    mapping_path = tmp_path / "mapping.json"
    catalog_path = tmp_path / "catalog.json"
    review_path = tmp_path / "reviews.jsonl"
    semantic_review_path = tmp_path / "semantic_reviews.jsonl"
    exclusion_path = tmp_path / "exclusions.jsonl"
    batch_path.write_text(json.dumps(row) + "\n", encoding="utf-8")
    mapping_path.write_text(
        json.dumps(
            {
                "entries": [
                    {"operator_id": operator_id, **entry}
                    for operator_id, entry in mapping.items()
                ]
            }
        ),
        encoding="utf-8",
    )
    catalog_path.write_text(
        json.dumps({"operators": list(catalog.values())}), encoding="utf-8"
    )
    review_path.write_text(
        json.dumps(
            {
                "schema": "gis_recommend.qgis_benchmark_expert_proposal_review_ledger.v1",
                "record_type": "schema_header",
                "review_count": 0,
            }
        )
        + "\n",
        encoding="utf-8",
    )
    semantic_review_path.write_text(
        json.dumps(
            {
                "schema": "gis_recommend.qgis_benchmark_semantic_intent_review_ledger.v1",
                "record_type": "schema_header",
                "review_count": 0,
            }
        )
        + "\n",
        encoding="utf-8",
    )
    exclusion_path.write_text("", encoding="utf-8")

    result = build_expert_proposals(
        batch_path=batch_path,
        mapping_path=mapping_path,
        catalog_path=catalog_path,
        review_path=review_path,
        semantic_review_path=semantic_review_path,
        exclusion_path=exclusion_path,
    )
    first_dir = tmp_path / "first"
    second_dir = tmp_path / "second"
    first_paths = write_expert_outputs(result, first_dir)
    second_paths = write_expert_outputs(result, second_dir)

    assert result["summary"]["proposal_count"] == 1
    assert result["summary"]["admitted_expert_count"] == 0
    assert result["summary"]["semantic_review_input_count"] == 0
    assert result["summary"]["semantic_review_count"] == 0
    assert result["summary"]["semantic_review_failure_count"] == 0
    assert result["summary"]["semantic_review_failures"] == []
    assert result["summary"]["input_hashes"]["semantic_review_ledger_sha256"]
    assert result["semantic_summary"] == {
        "schema": "gis_recommend.qgis_benchmark_semantic_intent_review_summary.v1",
        "review_count": 0,
        "failure_count": 0,
        "failures": [],
        "status_counts": {"not_required": 1},
        "admission_flags": {
            "training_admission": False,
            "validation_eligible": False,
            "test_eligible": False,
            "production_merge": False,
        },
    }
    assert result["rows"][0]["supply_admission"] == "proposal_only"
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
    for name in first_paths:
        assert first_paths[name].read_bytes() == second_paths[name].read_bytes()
    hash_ledger = json.loads(
        first_paths["expert_proposal_hash_ledger"].read_text(encoding="utf-8")
    )
    assert set(hash_ledger["artifacts"]) == {
        "expert_proposals_v1.jsonl",
        "expert_proposal_reviews_v1.jsonl",
        "expert_human_approval_queue_v1.jsonl",
        "expert_human_approvals_v1.jsonl",
        "expert_semantic_intent_reviews_v1.jsonl",
        "expert_semantic_intent_review_summary_v1.json",
        "expert_proposal_summary_v1.json",
    }
