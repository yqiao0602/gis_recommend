"""Pure semantic-closure review contract for QGIS benchmark proposals."""

from __future__ import annotations

from copy import deepcopy
import hashlib
import json
import re
from typing import Any


SEMANTIC_REVIEW_SCHEMA = (
    "gis_recommend.qgis_benchmark_semantic_intent_review.v1"
)
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
SEMANTIC_FORBIDDEN_FIELDS = {
    "dataset_id",
    "field_name",
    "threshold",
    "crs",
    "source_path",
    "source_snippet",
    "parameter_facts",
}

_PROCESS_NECESSITY_FIELDS = {"process_id", "role"}
_REASON_CODE_RE = re.compile(r"^[a-z][a-z0-9_]*$")


def requires_semantic_review(proposal: dict[str, Any]) -> bool:
    """Return whether graph size or an explicit flag requires semantic review."""

    processes = proposal.get("processes")
    process_count = len(processes) if isinstance(processes, list) else 0
    return process_count >= 4 or proposal.get("semantic_review_required") is True


def semantic_review_sha256(review: dict[str, Any]) -> str:
    """Hash the canonical review payload, excluding its self-declared hash."""

    payload = {
        key: value
        for key, value in review.items()
        if key != "semantic_review_sha256"
    }
    encoded = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _forbidden_keys(value: Any) -> list[str]:
    found: set[str] = set()
    if isinstance(value, dict):
        for key, child in value.items():
            if key in SEMANTIC_FORBIDDEN_FIELDS:
                found.add(key)
            found.update(_forbidden_keys(child))
    elif isinstance(value, list):
        for child in value:
            found.update(_forbidden_keys(child))
    return sorted(found)


def _is_non_empty_string(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def validate_semantic_review(
    proposal: dict[str, Any],
    review: Any,
    *,
    graph_sha256: str,
) -> list[str]:
    """Return deterministic errors for one human semantic-closure review."""

    if not isinstance(review, dict):
        return ["semantic_review_not_object"]

    errors: list[str] = []
    errors.extend(
        f"semantic_review_missing_field:{field}"
        for field in sorted(SEMANTIC_REQUIRED_FIELDS.difference(review))
    )
    errors.extend(
        f"semantic_review_unknown_field:{field}"
        for field in sorted(set(review).difference(SEMANTIC_ALLOWED_FIELDS))
    )

    if review.get("schema") != SEMANTIC_REVIEW_SCHEMA:
        errors.append("semantic_review_schema_invalid")
    if review.get("proposal_id") != proposal.get("proposal_id"):
        errors.append("semantic_review_proposal_id_mismatch")
    if review.get("proposal_graph_sha256") != graph_sha256:
        errors.append("semantic_review_proposal_graph_sha256_mismatch")

    for field in (
        "semantic_review_id",
        "reviewer_id",
        "reviewed_at",
        "rationale",
    ):
        if field in review and not _is_non_empty_string(review.get(field)):
            errors.append(f"semantic_review_{field}_invalid")

    if review.get("reviewer_kind") != "human_qgis_expert":
        errors.append("semantic_review_reviewer_kind_invalid")
    graph_reviewer_ids = proposal.get("graph_reviewer_ids", [])
    if not isinstance(graph_reviewer_ids, list):
        graph_reviewer_ids = []
    if review.get("reviewer_id") in graph_reviewer_ids:
        errors.append("semantic_review_not_independent_from_graph_review")

    if review.get("conflict_of_interest_declared") is not False:
        errors.append("semantic_review_conflict_of_interest_invalid")
    if review.get("qgis_expertise_attested") is not True:
        errors.append("semantic_review_qgis_expertise_not_attested")
    if review.get("concrete_data_facts_included") is not False:
        errors.append("semantic_review_concrete_data_facts_included")
    if review.get("execution_parameters_included") is not False:
        errors.append("semantic_review_execution_parameters_included")

    errors.extend(
        f"semantic_review_forbidden_field:{field}"
        for field in _forbidden_keys(review)
    )

    decision = review.get("semantic_closure_decision")
    if decision not in SEMANTIC_DECISIONS:
        errors.append("semantic_review_decision_invalid")

    reason_codes = review.get("reason_codes")
    if not isinstance(reason_codes, list):
        errors.append("semantic_review_reason_codes_invalid")
    else:
        for reason_code in reason_codes:
            if not isinstance(reason_code, str) or _REASON_CODE_RE.fullmatch(
                reason_code
            ) is None:
                errors.append(
                    f"semantic_review_reason_code_format_invalid:{reason_code}"
                )
            if (
                not isinstance(reason_code, str)
                or reason_code not in SEMANTIC_REASON_CODES
            ):
                errors.append(f"semantic_review_reason_code_unknown:{reason_code}")

    process_necessity = review.get("process_necessity")
    process_ids: list[Any] = []
    if not isinstance(process_necessity, list):
        errors.append("semantic_review_process_necessity_invalid")
    else:
        for index, entry in enumerate(process_necessity):
            if not isinstance(entry, dict):
                errors.append(
                    f"semantic_review_process_necessity_entry_invalid:{index}"
                )
                process_ids.append(None)
                continue
            if set(entry) != _PROCESS_NECESSITY_FIELDS:
                errors.append(
                    f"semantic_review_process_necessity_fields_invalid:{index}"
                )
            process_id = entry.get("process_id")
            process_ids.append(process_id)
            if not _is_non_empty_string(process_id):
                errors.append(
                    f"semantic_review_process_necessity_process_id_invalid:{index}"
                )
            if not _is_non_empty_string(entry.get("role")):
                errors.append(
                    f"semantic_review_process_necessity_role_invalid:{index}"
                )

    if decision == "closed":
        if not _is_non_empty_string(review.get("task_intent")):
            errors.append("semantic_review_task_intent_invalid")
        if not _is_non_empty_string(review.get("output_constraint")):
            errors.append("semantic_review_output_constraint_invalid")
        expected_process_ids = [
            process.get("process_id")
            for process in proposal.get("processes", [])
            if isinstance(process, dict)
        ]
        if (
            not isinstance(process_necessity, list)
            or process_ids != expected_process_ids
        ):
            errors.append("semantic_review_process_necessity_coverage_mismatch")
        if isinstance(reason_codes, list) and reason_codes:
            errors.append("semantic_review_closed_with_reason_codes")
    elif decision in {"return_for_revision", "rejected"}:
        if not isinstance(reason_codes, list) or not reason_codes:
            errors.append("semantic_review_reason_codes_required")

    if "semantic_review_sha256" in review and review.get(
        "semantic_review_sha256"
    ) != semantic_review_sha256(review):
        errors.append("semantic_review_sha256_mismatch")

    return list(dict.fromkeys(errors))


def emit_semantic_review(
    proposal: dict[str, Any],
    review: dict[str, Any],
    *,
    graph_sha256: str,
) -> dict[str, Any]:
    """Return an integrity-bound review, refusing invalid input."""

    errors = validate_semantic_review(proposal, review, graph_sha256=graph_sha256)
    if errors:
        raise ValueError("invalid semantic review: " + ",".join(errors))
    emitted = deepcopy(review)
    emitted["semantic_review_sha256"] = semantic_review_sha256(emitted)
    return emitted


def apply_semantic_review(
    proposal: dict[str, Any],
    review: dict[str, Any],
    *,
    graph_sha256: str,
) -> dict[str, Any]:
    """Apply a valid semantic decision without mutating proposal graph content."""

    emitted = emit_semantic_review(
        proposal,
        review,
        graph_sha256=graph_sha256,
    )
    updated = deepcopy(proposal)
    updated["semantic_review_status"] = {
        "closed": "closed",
        "return_for_revision": "returned_for_revision",
        "rejected": "rejected",
    }[emitted["semantic_closure_decision"]]
    updated["semantic_review_ref"] = emitted["semantic_review_id"]
    updated["semantic_reviewer_id"] = emitted["reviewer_id"]
    return updated
