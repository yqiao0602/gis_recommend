#!/usr/bin/env python3
"""Validate and emit review-only expert-authored QGIS graph proposals."""

from __future__ import annotations

import argparse
from collections import Counter
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import re
from typing import Any, Mapping

from scripts import build_qgis_benchmark_exclusion_ledger as exclusion
from scripts.build_qgis_benchmark_candidate_pool import (
    _modality as _gate3_modality,
    graph_profile as _gate3_graph_profile,
)
from scripts.qgis_benchmark_semantic_intent import (
    SEMANTIC_REVIEW_SCHEMA,
    apply_semantic_review,
    emit_semantic_review,
    requires_semantic_review,
    validate_semantic_review,
)


SCHEMA = "gis_recommend.qgis_benchmark_expert_proposal.v1"
REVIEW_SCHEMA = "gis_recommend.qgis_benchmark_expert_proposal_review.v1"
HUMAN_APPROVAL_QUEUE_SCHEMA = (
    "gis_recommend.qgis_benchmark_expert_human_approval_queue.v1"
)
HUMAN_APPROVAL_SCHEMA = "gis_recommend.qgis_benchmark_expert_human_approval.v1"
SEMANTIC_REVIEW_LEDGER_SCHEMA = (
    "gis_recommend.qgis_benchmark_semantic_intent_review_ledger.v1"
)
FORBIDDEN_FIELDS = {
    "task_text",
    "task_description",
    "source_path",
    "source_snippet",
    "parameter_facts",
    "dataset_id",
    "field_name",
    "threshold",
}
_REQUIRED_TOP_LEVEL = {
    "schema",
    "proposal_id",
    "authoring_batch_id",
    "provenance_class",
    "parameters_included",
    "processes",
    "links",
    "quota_anchor_l3",
    "covered_l3",
    "target_strata",
}
_PROCESS_FIELDS = {"process_id", "operator_id", "l3_code"}
_LINK_FIELDS = {"source_process_id", "target_process_id"}
_PROCESS_ID_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_-]*$")
_REVIEW_REQUIRED_FIELDS = {
    "schema",
    "review_id",
    "proposal_id",
    "reviewer_id",
    "reviewer_kind",
    "approval_authority",
    "reviewed_at",
    "decision",
    "checked_operator_ids",
    "checked_links",
    "strata_verdicts",
    "exclusion_verdict",
    "reason",
}
_STRATA_FIELDS = {"modality", "topology", "graph_size_stratum"}
_COMPLEX_TOPOLOGIES = {"branch_or_multi_output", "multi_input_merge"}
_HUMAN_APPROVAL_REQUIRED_FIELDS = {
    "schema",
    "approval_id",
    "proposal_id",
    "queue_record_sha256",
    "proposal_graph_sha256",
    "gate2_exclusion_sha256",
    "approver_id",
    "approver_kind",
    "decided_at",
    "decision",
    "rationale",
    "conflict_of_interest_declared",
    "qgis_expertise_attested",
}


def _hash_json(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(
            value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode("utf-8")
    ).hexdigest()


def _refresh_admission(row: dict[str, Any]) -> None:
    admitted = (
        row.get("graph_review_status") == "independent_reviewed"
        and row.get("gate1_status") == "passed"
        and row.get("gate2_status") == "passed"
        and row.get("dedup_status") == "canonical"
        and row.get("human_approval_status") == "approved"
        and row.get("semantic_review_status") in {"closed", "not_required"}
    )
    row["supply_admission"] = (
        "gate3_candidate_admitted" if admitted else "proposal_only"
    )


def proposal_graph_sha256(proposal: dict[str, Any]) -> str:
    """Bind approval to the exact parameter-free graph, not mutable metadata."""

    return _hash_json(
        {
            "processes": proposal.get("processes", []),
            "links": proposal.get("links", []),
        }
    )


def build_human_approval_queue(
    proposals: list[dict[str, Any]], *, gate2_exclusion_sha256: str
) -> list[dict[str, Any]]:
    """Emit blank human-review records only for technically eligible proposals."""

    queue = []
    for proposal in sorted(proposals, key=lambda row: str(row.get("proposal_id", ""))):
        eligible = (
            proposal.get("graph_review_status") == "independent_reviewed"
            and proposal.get("gate1_status") == "passed"
            and proposal.get("gate2_status") == "passed"
            and not proposal.get("gate2_overlap_fields", [])
            and proposal.get("dedup_status") == "canonical"
            and proposal.get("human_approval_status") == "pending"
        )
        if not eligible:
            continue
        row = {
            "schema": HUMAN_APPROVAL_QUEUE_SCHEMA,
            "record_id": f"human-approval-queue-{proposal['proposal_id']}",
            "proposal_id": proposal["proposal_id"],
            "proposal_graph_sha256": proposal_graph_sha256(proposal),
            "processes": deepcopy(proposal.get("processes", [])),
            "links": deepcopy(proposal.get("links", [])),
            "modality": proposal.get("modality"),
            "topology": proposal.get("topology"),
            "graph_size_stratum": proposal.get("graph_size_stratum"),
            "quota_anchor_l3": proposal.get("quota_anchor_l3"),
            "quota_credit_eligible": proposal.get("quota_credit_eligible", True),
            "gate2_exclusion_sha256": gate2_exclusion_sha256,
            "technical_review_refs": sorted(proposal.get("review_refs", [])),
            "technical_reviewer_ids": sorted(
                proposal.get("graph_reviewer_ids", [])
            ),
            "semantic_review_required": proposal.get(
                "semantic_review_required", True
            ),
            "semantic_review_status": proposal.get(
                "semantic_review_status", "pending"
            ),
            "gate1_status": "passed",
            "gate2_status": "passed",
            "gate2_overlap_fields": [],
            "dedup_status": "canonical",
            "approval_status": "pending_human",
            "approver_id": None,
            "decision": None,
            "decided_at": None,
            "rationale": None,
        }
        row["queue_record_sha256"] = _hash_json(row)
        queue.append(row)
    return queue


def validate_human_approval(
    proposal: dict[str, Any],
    queue_record: dict[str, Any],
    approval: dict[str, Any],
) -> list[str]:
    """Validate one post-Gate-2 human decision against immutable evidence."""

    if not isinstance(approval, dict):
        return ["approval_not_object"]
    errors = [
        f"approval_missing_field:{field}"
        for field in sorted(_HUMAN_APPROVAL_REQUIRED_FIELDS.difference(approval))
    ]
    if approval.get("schema") != HUMAN_APPROVAL_SCHEMA:
        errors.append("approval_schema_invalid")
    if approval.get("proposal_id") != proposal.get("proposal_id"):
        errors.append("approval_proposal_id_mismatch")
    if approval.get("queue_record_sha256") != queue_record.get(
        "queue_record_sha256"
    ):
        errors.append("approval_queue_record_sha256_mismatch")
    if approval.get("proposal_graph_sha256") != proposal_graph_sha256(proposal):
        errors.append("approval_proposal_graph_sha256_mismatch")
    if approval.get("gate2_exclusion_sha256") != queue_record.get(
        "gate2_exclusion_sha256"
    ):
        errors.append("approval_gate2_exclusion_sha256_mismatch")
    for field in ("approval_id", "approver_id", "decided_at", "rationale"):
        if field in approval and (
            not isinstance(approval.get(field), str) or not approval.get(field)
        ):
            errors.append(f"approval_{field}_invalid")
    if approval.get("approver_kind") != "human_qgis_expert":
        errors.append("approval_approver_kind_invalid")
    if approval.get("decision") not in {
        "approve",
        "reject",
        "return_for_revision",
    }:
        errors.append("approval_decision_invalid")
    if approval.get("decision") == "approve" and proposal.get(
        "semantic_review_status"
    ) not in {"closed", "not_required"}:
        errors.append("approval_semantic_review_not_closed")
    if approval.get("conflict_of_interest_declared") is not False:
        errors.append("approval_conflict_of_interest_invalid")
    if approval.get("qgis_expertise_attested") is not True:
        errors.append("approval_qgis_expertise_not_attested")
    if approval.get("approver_id") in queue_record.get(
        "technical_reviewer_ids", []
    ):
        errors.append("approval_not_independent_from_technical_review")
    if queue_record.get("approval_status") != "pending_human":
        errors.append("approval_queue_not_pending")
    return list(dict.fromkeys(errors))


def apply_human_approval(
    proposal: dict[str, Any],
    queue_record: dict[str, Any],
    approval: dict[str, Any],
) -> dict[str, Any]:
    """Apply a valid human decision without modifying processes or links."""

    errors = validate_human_approval(proposal, queue_record, approval)
    if errors:
        raise ValueError("invalid human approval: " + ",".join(errors))
    updated = deepcopy(proposal)
    decision = approval["decision"]
    updated["human_approval_status"] = {
        "approve": "approved",
        "reject": "rejected",
        "return_for_revision": "returned_for_revision",
    }[decision]
    updated["human_approval_ref"] = approval["approval_id"]
    updated["human_approver_id"] = approval["approver_id"]
    _refresh_admission(updated)
    return updated


def apply_semantic_reviews(
    proposals: list[dict[str, Any]], semantic_rows: list[dict[str, Any]]
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    """Apply at most one hash-bound semantic decision per proposal."""

    rows = [deepcopy(row) for row in proposals]
    row_index = {
        str(row.get("proposal_id", "")): index for index, row in enumerate(rows)
    }
    grouped: dict[str, list[dict[str, Any]]] = {}
    for review in semantic_rows:
        grouped.setdefault(str(review.get("proposal_id", "")), []).append(review)

    failures: list[dict[str, Any]] = []
    emitted_reviews: list[dict[str, Any]] = []
    for proposal_id, reviews in sorted(grouped.items()):
        reviews = sorted(
            reviews, key=lambda row: str(row.get("semantic_review_id", ""))
        )
        first_review_id = str(reviews[0].get("semantic_review_id", ""))
        if proposal_id not in row_index:
            failures.append(
                {
                    "proposal_id": proposal_id,
                    "semantic_review_id": first_review_id,
                    "error_codes": ["semantic_review_proposal_not_found"],
                }
            )
            continue
        if len(reviews) != 1:
            failures.append(
                {
                    "proposal_id": proposal_id,
                    "error_codes": ["semantic_review_duplicate_decisions"],
                }
            )
            continue

        proposal = rows[row_index[proposal_id]]
        review = reviews[0]
        graph_sha256 = proposal_graph_sha256(proposal)
        errors = validate_semantic_review(
            proposal, review, graph_sha256=graph_sha256
        )
        if errors:
            failures.append(
                {
                    "proposal_id": proposal_id,
                    "semantic_review_id": first_review_id,
                    "error_codes": errors,
                }
            )
            continue

        emitted = emit_semantic_review(proposal, review, graph_sha256=graph_sha256)
        updated = apply_semantic_review(
            proposal, emitted, graph_sha256=graph_sha256
        )
        _refresh_admission(updated)
        rows[row_index[proposal_id]] = updated
        emitted_reviews.append(emitted)

    return rows, failures, emitted_reviews


def graph_profile(
    node_count: int, edges: list[tuple[int, int]]
) -> dict[str, str] | None:
    """Expose the Gate 3 topology contract without redefining it."""

    return _gate3_graph_profile(node_count, edges)


def _forbidden_keys(value: Any) -> list[str]:
    found: set[str] = set()
    if isinstance(value, dict):
        for key, child in value.items():
            if key in FORBIDDEN_FIELDS:
                found.add(key)
            found.update(_forbidden_keys(child))
    elif isinstance(value, list):
        for child in value:
            found.update(_forbidden_keys(child))
    return sorted(found)


def _catalog_is_strict(entry: Mapping[str, Any]) -> bool:
    if entry.get("strict_catalog") is False:
        return False
    tier = entry.get("admission_tier")
    if tier is not None and tier != "headline_core":
        return False
    return True


def validate_proposal(
    row: dict[str, Any],
    *,
    mapping_by_operator: dict[str, dict[str, Any]],
    catalog_by_operator: dict[str, dict[str, Any]],
) -> list[str]:
    """Return deterministic validation error codes for one proposal."""

    if not isinstance(row, dict):
        return ["row_not_object"]

    errors: list[str] = []
    errors.extend(f"forbidden_field:{key}" for key in _forbidden_keys(row))

    missing = sorted(_REQUIRED_TOP_LEVEL.difference(row))
    errors.extend(f"missing_field:{key}" for key in missing)
    if row.get("schema") != SCHEMA:
        errors.append("schema_invalid")
    if row.get("provenance_class") != "expert_authored":
        errors.append("provenance_not_expert_authored")
    if row.get("parameters_included") is not False:
        errors.append("parameters_included")

    processes = row.get("processes")
    process_ids: list[str] = []
    declared_ids: set[str] = set()
    if not isinstance(processes, list) or not processes:
        errors.append("processes_empty")
        processes = []
    for process in processes:
        if not isinstance(process, dict):
            errors.append("process_not_object")
            continue
        errors.extend(
            f"process_forbidden_field:{key}"
            for key in sorted(set(process).difference(_PROCESS_FIELDS))
        )
        process_id = process.get("process_id")
        if (
            not isinstance(process_id, str)
            or not process_id
            or _PROCESS_ID_RE.fullmatch(process_id) is None
        ):
            errors.append(f"invalid_process_id:{process_id}")
        elif process_id in declared_ids:
            errors.append(f"process_id_duplicate:{process_id}")
        else:
            declared_ids.add(process_id)
            process_ids.append(process_id)

        operator_id = process.get("operator_id")
        if not isinstance(operator_id, str) or not operator_id:
            errors.append("operator_id_invalid")
            continue
        mapping = mapping_by_operator.get(operator_id)
        catalog = catalog_by_operator.get(operator_id)
        if mapping is None:
            errors.append(f"mapping_missing:{operator_id}")
        else:
            if mapping.get("mapping_status") != "stable101_direct":
                errors.append(f"mapping_not_stable101:{operator_id}")
            if mapping.get("headline_eligible") is not True:
                errors.append(f"operator_not_headline_eligible:{operator_id}")
            if process.get("l3_code") != mapping.get("l3_code"):
                errors.append(f"l3_mismatch:{operator_id}")
        if catalog is None:
            errors.append(f"catalog_missing:{operator_id}")
        elif not _catalog_is_strict(catalog):
            errors.append(f"catalog_not_strict:{operator_id}")

    links = row.get("links")
    if not isinstance(links, list):
        errors.append("links_invalid")
        links = []
    for link in links:
        if not isinstance(link, dict):
            errors.append("link_not_object")
            continue
        errors.extend(
            f"link_forbidden_field:{key}"
            for key in sorted(set(link).difference(_LINK_FIELDS))
        )
        source = link.get("source_process_id")
        target = link.get("target_process_id")
        if not isinstance(source, str) or not isinstance(target, str):
            errors.append("link_endpoint_invalid")
            continue
        if source not in declared_ids:
            errors.append(f"link_unknown_source:{source}")
        if target not in declared_ids:
            errors.append(f"link_unknown_target:{target}")

    valid_process_ids = len(process_ids) == len(processes)
    valid_links = all(
        isinstance(link, dict)
        and isinstance(link.get("source_process_id"), str)
        and isinstance(link.get("target_process_id"), str)
        and link.get("source_process_id") in declared_ids
        and link.get("target_process_id") in declared_ids
        for link in links
    )
    if valid_process_ids and valid_links:
        process_index = {process_id: index for index, process_id in enumerate(process_ids)}
        profile = graph_profile(
            len(process_ids),
            [
                (
                    process_index[link["source_process_id"]],
                    process_index[link["target_process_id"]],
                )
                for link in links
            ],
        )
        if profile is None:
            errors.append("graph_invalid")
        else:
            for field in ("topology", "graph_size_stratum"):
                if row.get(field) != profile[field]:
                    errors.append(f"{field}_mismatch:{profile[field]}")
                target_strata = row.get("target_strata")
                if isinstance(target_strata, dict) and target_strata.get(field) != profile[field]:
                    errors.append(f"target_strata_{field}_mismatch:{profile[field]}")

        operator_ids = [
            process.get("operator_id")
            for process in processes
            if isinstance(process, dict) and isinstance(process.get("operator_id"), str)
        ]
        if len(operator_ids) == len(processes) and all(
            operator_id in catalog_by_operator for operator_id in operator_ids
        ):
            modality = _gate3_modality(operator_ids, catalog_by_operator)
            if row.get("modality") != modality:
                errors.append(f"modality_mismatch:{modality}")
            target_strata = row.get("target_strata")
            if isinstance(target_strata, dict) and target_strata.get("modality") != modality:
                errors.append(f"target_strata_modality_mismatch:{modality}")

        expected_l3 = list(
            dict.fromkeys(
                process.get("l3_code")
                for process in processes
                if isinstance(process, dict) and isinstance(process.get("l3_code"), str)
            )
        )
        if row.get("covered_l3") != expected_l3:
            errors.append("covered_l3_mismatch")
        if row.get("quota_anchor_l3") not in expected_l3:
            errors.append("quota_anchor_l3_invalid")

    # Preserve first occurrence order while making duplicate diagnostics stable.
    return list(dict.fromkeys(errors))


def emit_proposal(
    row: dict[str, Any],
    *,
    mapping_by_operator: dict[str, dict[str, Any]],
    catalog_by_operator: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    """Return a closed proposal row, refusing invalid authoring input."""

    errors = validate_proposal(
        row,
        mapping_by_operator=mapping_by_operator,
        catalog_by_operator=catalog_by_operator,
    )
    if errors:
        raise ValueError("invalid proposal: " + ",".join(errors))
    emitted = deepcopy(row)
    semantic_review_required = requires_semantic_review(emitted)
    emitted.update(
        {
            "schema": SCHEMA,
            "provenance_class": "expert_authored",
            "graph_review_status": "unreviewed",
            "gate1_status": "passed",
            "gate2_status": "pending",
            "semantic_review_required": semantic_review_required,
            "semantic_review_status": (
                "pending" if semantic_review_required else "not_required"
            ),
            "supply_admission": "proposal_only",
            "training_admission": False,
            "validation_eligible": False,
            "test_eligible": False,
            "production_merge": False,
            "review_refs": [],
            "graph_reviewer_ids": [],
            "graph_accept_reviewer_ids": [],
            "graph_revision_reviewer_ids": [],
            "graph_reject_reviewer_ids": [],
            "human_approval_status": "pending",
            "quota_credit_eligible": (
                row.get("topology") != "branch_or_multi_output"
            ),
        }
    )
    return emitted


def validate_review(
    proposal: dict[str, Any], review: dict[str, Any]
) -> list[str]:
    """Return deterministic evidence errors for one independent graph review."""

    if not isinstance(review, dict):
        return ["review_not_object"]
    errors = [
        f"review_missing_field:{field}"
        for field in sorted(_REVIEW_REQUIRED_FIELDS.difference(review))
    ]
    if review.get("schema") != REVIEW_SCHEMA:
        errors.append("review_schema_invalid")
    if review.get("proposal_id") != proposal.get("proposal_id"):
        errors.append("review_proposal_id_mismatch")
    if review.get("decision") not in {"accept", "revise", "reject"}:
        errors.append("review_decision_invalid")
    for field in ("review_id", "reviewer_id", "reviewed_at", "reason"):
        if field in review and (
            not isinstance(review.get(field), str) or not review.get(field)
        ):
            errors.append(f"review_{field}_invalid")
    if "reviewer_kind" in review and review.get("reviewer_kind") not in {
        "ai_independent_technical",
        "human_qgis_expert",
    }:
        errors.append("review_reviewer_kind_invalid")
    if "approval_authority" in review and not isinstance(
        review.get("approval_authority"), bool
    ):
        errors.append("review_approval_authority_invalid")

    expected_operator_ids = [
        process.get("operator_id")
        for process in proposal.get("processes", [])
        if isinstance(process, dict)
    ]
    if "checked_operator_ids" in review and review.get("checked_operator_ids") != expected_operator_ids:
        errors.append("review_checked_operator_ids_mismatch")
    if "checked_links" in review and review.get("checked_links") != proposal.get("links"):
        errors.append("review_checked_links_mismatch")

    strata = review.get("strata_verdicts")
    if isinstance(strata, dict):
        errors.extend(
            f"review_strata_verdict_missing:{field}"
            for field in sorted(_STRATA_FIELDS.difference(strata))
        )
        errors.extend(
            f"review_strata_verdict_failed:{field}"
            for field in sorted(_STRATA_FIELDS.intersection(strata))
            if strata.get(field) is not True
        )
    elif "strata_verdicts" in review:
        errors.append("review_strata_verdicts_invalid")

    if "exclusion_verdict" in review and review.get("exclusion_verdict") not in {
        "pending_gate2",
        "no_observed_overlap",
        "overlap_found",
    }:
        errors.append("review_exclusion_verdict_invalid")
    if review.get("decision") == "accept" and review.get("exclusion_verdict") == "overlap_found":
        errors.append("review_accept_with_overlap")
    if "semantic_review_required" in review and not isinstance(
        review.get("semantic_review_required"), bool
    ):
        errors.append("review_semantic_review_required_invalid")
    if review.get("semantic_review_required") is True:
        concern_reason = review.get("semantic_concern_reason")
        if not isinstance(concern_reason, str) or not concern_reason.strip():
            errors.append("review_semantic_concern_reason_required")
    elif "semantic_concern_reason" in review and (
        not isinstance(review.get("semantic_concern_reason"), str)
        or not review["semantic_concern_reason"].strip()
    ):
        errors.append("review_semantic_concern_reason_invalid")
    return list(dict.fromkeys(errors))


def apply_review(
    proposal: dict[str, Any], review: dict[str, Any]
) -> dict[str, Any]:
    """Apply a review without changing graph content or weakening prior rejection."""

    errors = validate_review(proposal, review)
    if errors:
        raise ValueError("invalid review: " + ",".join(errors))

    updated = deepcopy(proposal)
    review_refs = list(updated.get("review_refs", []))
    if review["review_id"] not in review_refs:
        review_refs.append(review["review_id"])
    updated["review_refs"] = review_refs

    reviewer_ids = list(updated.get("graph_reviewer_ids", []))
    if review["reviewer_id"] not in reviewer_ids:
        reviewer_ids.append(review["reviewer_id"])
    updated["graph_reviewer_ids"] = reviewer_ids

    decision_fields = {
        "accept": "graph_accept_reviewer_ids",
        "revise": "graph_revision_reviewer_ids",
        "reject": "graph_reject_reviewer_ids",
    }
    decision_field = decision_fields[review["decision"]]
    decision_reviewer_ids = list(updated.get(decision_field, []))
    if review["reviewer_id"] not in decision_reviewer_ids:
        decision_reviewer_ids.append(review["reviewer_id"])
    updated[decision_field] = decision_reviewer_ids

    if review.get("semantic_review_required") is True:
        updated["semantic_review_required"] = True
        updated["semantic_review_status"] = "pending"

    required_reviews = 2 if updated.get("topology") in _COMPLEX_TOPOLOGIES else 1
    if updated.get("graph_reject_reviewer_ids"):
        updated["graph_review_status"] = "rejected"
    elif updated.get("graph_revision_reviewer_ids"):
        updated["graph_review_status"] = "revision_required"
    elif len(updated.get("graph_accept_reviewer_ids", [])) >= required_reviews:
        updated["graph_review_status"] = "independent_reviewed"
    else:
        updated["graph_review_status"] = "unreviewed"
    _refresh_admission(updated)
    return updated


def graph_fingerprints(proposal: dict[str, Any]) -> dict[str, str]:
    """Build only graph-derived members of the frozen nine-index contract."""

    processes = proposal.get("processes", [])
    process_index = {
        process["process_id"]: index
        for index, process in enumerate(processes)
        if isinstance(process, dict) and isinstance(process.get("process_id"), str)
    }
    adapted = {
        "operator_sequence": [process["operator_id"] for process in processes],
        "l3_code_sequence": [process["l3_code"] for process in processes],
        "dependency_edges": [
            {
                "producer_ordinal": process_index[link["source_process_id"]],
                "consumer_ordinal": process_index[link["target_process_id"]],
                "dependency_kind": "data",
            }
            for link in proposal.get("links", [])
        ],
    }
    fingerprint = exclusion.fingerprint_record(
        adapted,
        artifact_id="expert_authored_graph",
        record_index=0,
        platform="qgis",
        exposure_class="proposal_only",
    )
    return {field: str(fingerprint.get(field, "")) for field in exclusion.OVERLAP_FIELDS}


def apply_gate2(
    proposal: dict[str, Any], exclusion_rows: list[dict[str, Any]]
) -> dict[str, Any]:
    """Apply frozen overlap indexes while leaving absent source/text keys empty."""

    updated = deepcopy(proposal)
    fingerprints = graph_fingerprints(updated)
    overlap_fields = []
    for field in exclusion.OVERLAP_FIELDS:
        value = fingerprints[field]
        if value and any(
            row.get("record_type") == "exclusion" and row.get(field) == value
            for row in exclusion_rows
        ):
            overlap_fields.append(field)
    updated.update(fingerprints)
    updated["gate2_overlap_fields"] = overlap_fields
    updated["gate2_status"] = "failed_overlap" if overlap_fields else "passed"
    _refresh_admission(updated)
    return updated


def _dedup_keys(row: dict[str, Any]) -> list[tuple[str, str]]:
    fingerprints = graph_fingerprints(row)
    graph = {
        "processes": row.get("processes", []),
        "links": row.get("links", []),
    }
    return [
        ("duplicate_exact_proposal_identity", _hash_json(row)),
        ("duplicate_canonical_graph_identity", _hash_json(graph)),
        ("duplicate_normalized_dag_identity", fingerprints["normalized_dag_key"]),
        (
            "duplicate_training_pair_identity",
            _hash_json(
                {
                    "operator_l3": [
                        (process.get("operator_id"), process.get("l3_code"))
                        for process in row.get("processes", [])
                    ],
                    "links": row.get("links", []),
                }
            ),
        ),
    ]


def deduplicate_proposals(
    proposals: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, str]]]:
    """Keep the first proposal by stable ID across four ordered identities."""

    seen: list[dict[str, str]] = [dict() for _ in range(4)]
    canonical: list[dict[str, Any]] = []
    suppressions: list[dict[str, str]] = []
    for proposal in sorted(proposals, key=lambda row: str(row.get("proposal_id", ""))):
        keys = _dedup_keys(proposal)
        duplicate: tuple[str, str] | None = None
        for index, (reason, key) in enumerate(keys):
            if key and key in seen[index]:
                duplicate = (reason, seen[index][key])
                break
        if duplicate is not None:
            suppressions.append(
                {
                    "proposal_id": str(proposal.get("proposal_id", "")),
                    "canonical_proposal_id": duplicate[1],
                    "reason_code": duplicate[0],
                }
            )
            continue
        updated = deepcopy(proposal)
        updated["dedup_status"] = "canonical"
        _refresh_admission(updated)
        canonical.append(updated)
        for index, (_, key) in enumerate(keys):
            if key:
                seen[index][key] = str(proposal.get("proposal_id", ""))
    return canonical, suppressions


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8-sig").splitlines()
        if line.strip()
    ]


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load_mapping(path: Path) -> dict[str, dict[str, Any]]:
    artifact = json.loads(path.read_text(encoding="utf-8"))
    result = {}
    for entry in artifact.get("entries", []):
        operator_id = entry["operator_id"]
        normalized = dict(entry)
        normalized["l3_code"] = entry.get("l3_code", entry.get("stable101_l3"))
        result[operator_id] = normalized
    return result


def _load_catalog(path: Path) -> dict[str, dict[str, Any]]:
    artifact = json.loads(path.read_text(encoding="utf-8"))
    return {entry["operator_id"]: entry for entry in artifact.get("operators", [])}


def build_expert_proposals(
    *,
    batch_path: Path,
    mapping_path: Path,
    catalog_path: Path,
    review_path: Path,
    semantic_review_path: Path | None = None,
    exclusion_path: Path,
    approval_path: Path | None = None,
) -> dict[str, Any]:
    """Build a review-only expert ledger without creating benchmark splits."""

    mapping = _load_mapping(mapping_path)
    catalog = _load_catalog(catalog_path)
    batch_rows = _read_jsonl(batch_path)
    review_rows = [
        row for row in _read_jsonl(review_path) if row.get("schema") == REVIEW_SCHEMA
    ]
    semantic_rows = [
        row
        for row in (
            _read_jsonl(semantic_review_path)
            if semantic_review_path is not None
            else []
        )
        if not (
            row.get("schema") == SEMANTIC_REVIEW_LEDGER_SCHEMA
            and row.get("record_type") == "schema_header"
        )
    ]
    approval_rows = [
        row
        for row in _read_jsonl(approval_path) if row.get("schema") == HUMAN_APPROVAL_SCHEMA
    ] if approval_path is not None else []
    exclusion_rows = _read_jsonl(exclusion_path)
    exclusion_sha256 = _sha256(exclusion_path)
    reviews_by_proposal: dict[str, list[dict[str, Any]]] = {}
    for review in review_rows:
        reviews_by_proposal.setdefault(str(review.get("proposal_id", "")), []).append(review)

    valid_rows = []
    gate1_failures: list[dict[str, Any]] = []
    review_failures: list[dict[str, Any]] = []
    for row in sorted(batch_rows, key=lambda value: str(value.get("proposal_id", ""))):
        errors = validate_proposal(
            row,
            mapping_by_operator=mapping,
            catalog_by_operator=catalog,
        )
        if errors:
            gate1_failures.append(
                {"proposal_id": str(row.get("proposal_id", "")), "error_codes": errors}
            )
            continue
        proposal = emit_proposal(
            row,
            mapping_by_operator=mapping,
            catalog_by_operator=catalog,
        )
        for review in sorted(
            reviews_by_proposal.get(str(proposal["proposal_id"]), []),
            key=lambda value: str(value.get("review_id", "")),
        ):
            review_errors = validate_review(proposal, review)
            if review_errors:
                review_failures.append(
                    {
                        "proposal_id": str(proposal["proposal_id"]),
                        "review_id": str(review.get("review_id", "")),
                        "error_codes": review_errors,
                    }
                )
                continue
            proposal = apply_review(proposal, review)
        if proposal["graph_review_status"] == "independent_reviewed":
            proposal = apply_gate2(proposal, exclusion_rows)
        valid_rows.append(proposal)

    rows, suppressions = deduplicate_proposals(valid_rows)
    rows, semantic_failures, emitted_semantic_reviews = apply_semantic_reviews(
        rows, semantic_rows
    )
    approval_queue = build_human_approval_queue(
        rows, gate2_exclusion_sha256=exclusion_sha256
    )
    queue_by_proposal = {
        str(row["proposal_id"]): row for row in approval_queue
    }
    approvals_by_proposal: dict[str, list[dict[str, Any]]] = {}
    for approval in approval_rows:
        approvals_by_proposal.setdefault(
            str(approval.get("proposal_id", "")), []
        ).append(approval)
    approval_failures: list[dict[str, Any]] = []
    row_index = {
        str(row["proposal_id"]): index for index, row in enumerate(rows)
    }
    for proposal_id, approvals in sorted(approvals_by_proposal.items()):
        if proposal_id not in queue_by_proposal or proposal_id not in row_index:
            approval_failures.append(
                {
                    "proposal_id": proposal_id,
                    "approval_id": str(approvals[0].get("approval_id", "")),
                    "error_codes": ["approval_proposal_not_eligible"],
                }
            )
            continue
        if len(approvals) != 1:
            approval_failures.append(
                {
                    "proposal_id": proposal_id,
                    "approval_id": "",
                    "error_codes": ["approval_duplicate_decisions"],
                }
            )
            continue
        approval = approvals[0]
        proposal = rows[row_index[proposal_id]]
        approval_errors = validate_human_approval(
            proposal, queue_by_proposal[proposal_id], approval
        )
        if approval_errors:
            approval_failures.append(
                {
                    "proposal_id": proposal_id,
                    "approval_id": str(approval.get("approval_id", "")),
                    "error_codes": approval_errors,
                }
            )
            continue
        rows[row_index[proposal_id]] = apply_human_approval(
            proposal, queue_by_proposal[proposal_id], approval
        )
    review_status_counts = dict(
        sorted(Counter(row["graph_review_status"] for row in rows).items())
    )
    human_approval_status_counts = dict(
        sorted(Counter(row["human_approval_status"] for row in rows).items())
    )
    gate2_counts = dict(sorted(Counter(row["gate2_status"] for row in rows).items()))
    semantic_status_counts = dict(
        sorted(Counter(row["semantic_review_status"] for row in rows).items())
    )
    overlap_counts = dict(
        sorted(
            Counter(
                field
                for row in rows
                for field in row.get("gate2_overlap_fields", [])
            ).items()
        )
    )
    admitted = [
        row for row in rows if row["supply_admission"] == "gate3_candidate_admitted"
    ]
    summary = {
        "schema": "gis_recommend.qgis_benchmark_expert_proposal_summary.v1",
        "proposal_count": len(rows),
        "authored_input_count": len(batch_rows),
        "review_record_count": len(review_rows),
        "review_status_counts": review_status_counts,
        "human_approval_status_counts": human_approval_status_counts,
        "human_approval_queue_count": len(approval_queue),
        "human_approval_decision_count": len(approval_rows),
        "human_approval_failure_count": len(approval_failures),
        "human_approval_failures": approval_failures,
        "gate1_failure_count": len(gate1_failures),
        "gate1_failures": gate1_failures,
        "review_failure_count": len(review_failures),
        "review_failures": review_failures,
        "gate2_status_counts": gate2_counts,
        "gate2_overlap_counts": overlap_counts,
        "dedup_suppression_count": len(suppressions),
        "dedup_suppressions": suppressions,
        "admitted_expert_count": len(admitted),
        "target_strata_counts": dict(
            sorted(
                Counter(
                    "|".join(
                        str(row.get("target_strata", {}).get(field, ""))
                        for field in (
                            "anchor_family",
                            "modality",
                            "topology",
                            "graph_size_stratum",
                        )
                    )
                    for row in rows
                ).items()
            )
        ),
        "admission_flags": {
            "training_admission": False,
            "validation_eligible": False,
            "test_eligible": False,
            "production_merge": False,
        },
        "gate4_created": False,
        "input_hashes": {
            "authoring_batch_sha256": _sha256(batch_path),
            "mapping_sha256": _sha256(mapping_path),
            "catalog_sha256": _sha256(catalog_path),
            "review_ledger_sha256": _sha256(review_path),
            "semantic_review_ledger_sha256": (
                _sha256(semantic_review_path)
                if semantic_review_path is not None
                and semantic_review_path.is_file()
                else None
            ),
            "exclusion_ledger_sha256": exclusion_sha256,
            "human_approval_ledger_sha256": (
                _sha256(approval_path)
                if approval_path is not None and approval_path.is_file()
                else None
            ),
        },
    }
    semantic_summary = {
        "schema": "gis_recommend.qgis_benchmark_semantic_intent_review_summary.v1",
        "review_count": len(emitted_semantic_reviews),
        "failure_count": len(semantic_failures),
        "failures": semantic_failures,
        "status_counts": semantic_status_counts,
        "admission_flags": {
            "training_admission": False,
            "validation_eligible": False,
            "test_eligible": False,
            "production_merge": False,
        },
    }
    summary.update(
        {
            "semantic_review_input_count": len(semantic_rows),
            "semantic_review_count": len(emitted_semantic_reviews),
            "semantic_review_failure_count": len(semantic_failures),
            "semantic_review_failures": semantic_failures,
            "semantic_review_status_counts": semantic_status_counts,
        }
    )
    return {
        "rows": rows,
        "reviews": review_rows,
        "semantic_reviews": emitted_semantic_reviews,
        "semantic_summary": semantic_summary,
        "approval_queue": approval_queue,
        "approvals": approval_rows,
        "summary": summary,
    }


def _jsonl_bytes(rows: list[dict[str, Any]]) -> bytes:
    return "".join(
        json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        + "\n"
        for row in rows
    ).encode("utf-8")


def write_expert_outputs(result: dict[str, Any], output_dir: Path) -> dict[str, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    paths = {
        "expert_proposals": output_dir / "expert_proposals_v1.jsonl",
        "expert_proposal_reviews": output_dir / "expert_proposal_reviews_v1.jsonl",
        "expert_human_approval_queue": output_dir / "expert_human_approval_queue_v1.jsonl",
        "expert_human_approvals": output_dir / "expert_human_approvals_v1.jsonl",
        "expert_semantic_intent_reviews": output_dir / "expert_semantic_intent_reviews_v1.jsonl",
        "expert_semantic_intent_review_summary": output_dir / "expert_semantic_intent_review_summary_v1.json",
        "expert_proposal_summary": output_dir / "expert_proposal_summary_v1.json",
        "expert_proposal_hash_ledger": output_dir / "expert_proposal_hash_ledger_v1.json",
    }
    proposal_bytes = _jsonl_bytes(result["rows"])
    review_header = {
        "schema": "gis_recommend.qgis_benchmark_expert_proposal_review_ledger.v1",
        "record_type": "schema_header",
        "review_count": len(result["reviews"]),
    }
    review_bytes = _jsonl_bytes([review_header, *result["reviews"]])
    approval_queue_header = {
        "schema": "gis_recommend.qgis_benchmark_expert_human_approval_queue_ledger.v1",
        "record_type": "schema_header",
        "queue_count": len(result["approval_queue"]),
    }
    approval_queue_bytes = _jsonl_bytes(
        [approval_queue_header, *result["approval_queue"]]
    )
    approval_header = {
        "schema": "gis_recommend.qgis_benchmark_expert_human_approval_ledger.v1",
        "record_type": "schema_header",
        "approval_count": len(result["approvals"]),
    }
    approval_bytes = _jsonl_bytes([approval_header, *result["approvals"]])
    semantic_header = {
        "schema": SEMANTIC_REVIEW_LEDGER_SCHEMA,
        "record_type": "schema_header",
        "review_count": len(result["semantic_reviews"]),
    }
    semantic_bytes = _jsonl_bytes(
        [semantic_header, *result["semantic_reviews"]]
    )
    semantic_summary_bytes = (
        json.dumps(
            result["semantic_summary"],
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n"
    ).encode("utf-8")
    summary_bytes = (
        json.dumps(result["summary"], ensure_ascii=False, indent=2, sort_keys=True)
        + "\n"
    ).encode("utf-8")
    paths["expert_proposals"].write_bytes(proposal_bytes)
    paths["expert_proposal_reviews"].write_bytes(review_bytes)
    paths["expert_human_approval_queue"].write_bytes(approval_queue_bytes)
    paths["expert_human_approvals"].write_bytes(approval_bytes)
    paths["expert_semantic_intent_reviews"].write_bytes(semantic_bytes)
    paths["expert_semantic_intent_review_summary"].write_bytes(
        semantic_summary_bytes
    )
    paths["expert_proposal_summary"].write_bytes(summary_bytes)
    hash_ledger = {
        "schema": "gis_recommend.qgis_benchmark_expert_proposal_hash_ledger.v1",
        "artifacts": {
            paths["expert_proposals"].name: hashlib.sha256(proposal_bytes).hexdigest(),
            paths["expert_proposal_reviews"].name: hashlib.sha256(review_bytes).hexdigest(),
            paths["expert_human_approval_queue"].name: hashlib.sha256(
                approval_queue_bytes
            ).hexdigest(),
            paths["expert_human_approvals"].name: hashlib.sha256(
                approval_bytes
            ).hexdigest(),
            paths["expert_semantic_intent_reviews"].name: hashlib.sha256(
                semantic_bytes
            ).hexdigest(),
            paths["expert_semantic_intent_review_summary"].name: hashlib.sha256(
                semantic_summary_bytes
            ).hexdigest(),
            paths["expert_proposal_summary"].name: hashlib.sha256(summary_bytes).hexdigest(),
        },
    }
    paths["expert_proposal_hash_ledger"].write_text(
        json.dumps(hash_ledger, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return paths


def main(argv: list[str] | None = None) -> int:
    root = Path(__file__).resolve().parents[1]
    authority = root / "benchmarks/qgis_planner_v1/authority"
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--batch", type=Path, default=authority / "expert_authoring_batch_v1.jsonl")
    parser.add_argument("--mapping", type=Path, default=authority / "qgis_operator_l3_mapping.json")
    parser.add_argument("--catalog", type=Path, default=authority / "qgis_catalog.json")
    parser.add_argument("--reviews", type=Path, default=authority / "expert_proposal_reviews_v1.jsonl")
    parser.add_argument(
        "--semantic-reviews",
        type=Path,
        default=authority / "expert_semantic_intent_reviews_v1.jsonl",
    )
    parser.add_argument(
        "--approvals",
        type=Path,
        default=authority / "expert_human_approvals_v1.jsonl",
    )
    parser.add_argument("--exclusions", type=Path, default=authority / "source_exclusion_ledger.jsonl")
    parser.add_argument("--output-dir", type=Path, default=authority)
    args = parser.parse_args(argv)
    result = build_expert_proposals(
        batch_path=args.batch,
        mapping_path=args.mapping,
        catalog_path=args.catalog,
        review_path=args.reviews,
        semantic_review_path=args.semantic_reviews,
        exclusion_path=args.exclusions,
        approval_path=args.approvals,
    )
    write_expert_outputs(result, args.output_dir)
    print(
        f"proposals={len(result['rows'])} "
        f"reviewed={result['summary']['review_status_counts'].get('independent_reviewed', 0)} "
        f"admitted={result['summary']['admitted_expert_count']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
