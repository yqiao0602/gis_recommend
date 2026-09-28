"""Deterministic gates for auditing QGIS description-to-chain candidates."""

from __future__ import annotations

from collections import Counter
from typing import Any, Iterable, Mapping


GENERIC_DESCRIPTIONS = {
    "qgis processing workflow",
    "qgis workflow",
    "processing workflow",
}


def normalize_operation(value: Any) -> str:
    operation = str(value or "").strip().lower()
    while operation.startswith("processing.run:"):
        operation = operation[len("processing.run:") :]
    return operation


def description_quality(record: Mapping[str, Any]) -> dict[str, Any]:
    task_name = str(record.get("task_name") or "").strip()
    description = str(record.get("task_description") or "").strip()
    normalized = " ".join(description.lower().split())
    reasons = []
    if len(task_name) < 3:
        reasons.append("missing_or_short_task_name")
    if len(description) < 40:
        reasons.append("missing_or_short_description")
    if normalized in GENERIC_DESCRIPTIONS:
        reasons.append("generic_placeholder_description")
    return {
        "description_gate_passed": not reasons,
        "description_length": len(description),
        "description_gate_reasons": reasons,
    }


def _statement_index(value: Any) -> int | None:
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return None


def analyze_steps(
    rows: Iterable[Mapping[str, Any]],
    strict_l3_by_operation: Mapping[str, str],
) -> dict[str, Any]:
    operations = []
    step_ids = []
    statement_indices = []
    literal_flags = []
    l3_chain = []
    unmapped = []

    for row in rows:
        if str(row.get("api_source_type") or "").strip().lower() != "qgis_processing_algorithm":
            continue
        operation = normalize_operation(row.get("normalized_api_name"))
        if ":" not in operation:
            continue
        raw_api_name = str(row.get("raw_api_name") or "").strip().lower()
        match_status = str(row.get("gee_match_status") or "").strip().lower()
        literal = (
            raw_api_name == f"processing.run:{operation}"
            or match_status == "qgis_processing_algorithm_id"
        )
        operations.append(operation)
        step_ids.append(str(row.get("id") or ""))
        statement_indices.append(_statement_index(row.get("statement_index")))
        literal_flags.append(literal)
        l3_code = strict_l3_by_operation.get(operation)
        if l3_code:
            l3_chain.append(l3_code)
        else:
            unmapped.append(operation)

    if len(operations) <= 1:
        ordering_quality = "single_step"
    elif any(index is None for index in statement_indices):
        ordering_quality = "extraction_order_only"
    elif all(left < right for left, right in zip(statement_indices, statement_indices[1:])):
        ordering_quality = "deterministic_statement_index"
    elif all(left <= right for left, right in zip(statement_indices, statement_indices[1:])):
        ordering_quality = "tied_statement_index"
    else:
        ordering_quality = "nonmonotonic_statement_index"

    return {
        "processing_step_count": len(operations),
        "qgis_operations": operations,
        "processing_step_ids": step_ids,
        "all_operator_ids_literal": bool(operations) and all(literal_flags),
        "literal_operator_count": sum(literal_flags),
        "ordering_quality": ordering_quality,
        "strict_l3_chain": l3_chain,
        "strict_l3_mapped_count": len(l3_chain),
        "strict_l3_complete": bool(operations) and not unmapped,
        "unmapped_operations": sorted(set(unmapped)),
    }


def classify_candidate(
    record: Mapping[str, Any],
    step_analysis: Mapping[str, Any] | None,
    *,
    max_chain_length: int = 15,
) -> dict[str, Any]:
    result = description_quality(record)
    group_count = int(record.get("candidate_group_count") or 0)
    groups = list((record.get("artifact_candidates") or {}).keys())
    is_unique = group_count == 1
    equivalent_mirrors = bool(record.get("equivalent_mirror_provenance"))
    provenance_resolved = is_unique or equivalent_mirrors
    selected_group = str(record.get("selected_extraction_group") or "")
    is_support = "l3_support" in selected_group.lower() if selected_group else any(
        "l3_support" in group.lower() for group in groups
    )
    result.update(
        {
            "provenance_unique": is_unique,
            "provenance_resolved": provenance_resolved,
            "equivalent_mirror_provenance": equivalent_mirrors,
            "support_group": is_support,
            "extraction_groups": groups,
            "selected_extraction_group": selected_group or None,
        }
    )

    if step_analysis is None:
        result.update(
            {
                "machine_structural_eligible": False,
                "strict_training_ready": False,
                "repairable_training_candidate": False,
                "single_step_training_candidate": False,
                "audit_class": (
                    "unresolved_provenance"
                    if group_count > 1 and not provenance_resolved
                    else "missing_artifact"
                ),
            }
        )
        return result

    result.update(step_analysis)
    step_count = int(step_analysis["processing_step_count"])
    common = (
        provenance_resolved
        and not is_support
        and result["description_gate_passed"]
        and step_analysis["all_operator_ids_literal"]
        and step_analysis["strict_l3_complete"]
        and step_count <= max_chain_length
    )
    multistep = step_count >= 2
    strict_order = step_analysis["ordering_quality"] == "deterministic_statement_index"
    result["machine_structural_eligible"] = common and multistep
    result["strict_training_ready"] = common and multistep and strict_order
    result["repairable_training_candidate"] = common and multistep and not strict_order
    result["single_step_training_candidate"] = common and step_count == 1

    if is_support:
        audit_class = "excluded_support"
    elif not result["description_gate_passed"]:
        audit_class = "description_gate_failed"
    elif step_count == 0:
        audit_class = "no_literal_processing_operator"
    elif not step_analysis["all_operator_ids_literal"]:
        audit_class = "nonliteral_operator_id"
    elif not step_analysis["strict_l3_complete"]:
        audit_class = "incomplete_94_l3_mapping"
    elif step_count > max_chain_length:
        audit_class = "chain_too_long"
    elif step_count == 1:
        audit_class = "single_step_candidate"
    elif strict_order:
        audit_class = "strict_training_ready"
    else:
        audit_class = "needs_order_reconstruction"
    result["audit_class"] = audit_class
    return result


def summarize_audit(records: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    rows = list(records)
    classes = Counter(str(row.get("audit_class") or "unknown") for row in rows)
    groups = Counter()
    selected_groups = Counter()
    selected_group_classes: dict[str, Counter[str]] = {}
    unmapped = Counter()
    processing_lengths = Counter()
    ordering_quality = Counter()
    for row in rows:
        for group in row.get("extraction_groups") or []:
            groups[group] += 1
        selected_group = str(row.get("selected_extraction_group") or "none")
        selected_groups[selected_group] += 1
        selected_group_classes.setdefault(selected_group, Counter())[
            str(row.get("audit_class") or "unknown")
        ] += 1
        for operation in row.get("unmapped_operations") or []:
            unmapped[operation] += 1
        processing_lengths[int(row.get("processing_step_count") or 0)] += 1
        ordering_quality[str(row.get("ordering_quality") or "none")] += 1
    return {
        "total_records": len(rows),
        "description_gate_passed": sum(bool(row.get("description_gate_passed")) for row in rows),
        "provenance_unique": sum(bool(row.get("provenance_unique")) for row in rows),
        "provenance_resolved": sum(bool(row.get("provenance_resolved")) for row in rows),
        "equivalent_mirror_provenance": sum(
            bool(row.get("equivalent_mirror_provenance")) for row in rows
        ),
        "machine_structural_eligible": sum(bool(row.get("machine_structural_eligible")) for row in rows),
        "strict_training_ready": sum(bool(row.get("strict_training_ready")) for row in rows),
        "repairable_training_candidate": sum(bool(row.get("repairable_training_candidate")) for row in rows),
        "single_step_training_candidate": sum(bool(row.get("single_step_training_candidate")) for row in rows),
        "records_with_processing": sum(
            int(row.get("processing_step_count") or 0) > 0 for row in rows
        ),
        "records_with_multistep_processing": sum(
            int(row.get("processing_step_count") or 0) >= 2 for row in rows
        ),
        "by_audit_class": dict(sorted(classes.items())),
        "by_extraction_group": dict(sorted(groups.items())),
        "by_selected_extraction_group": dict(sorted(selected_groups.items())),
        "by_selected_group_and_class": {
            group: dict(sorted(counts.items()))
            for group, counts in sorted(selected_group_classes.items())
        },
        "processing_step_count_distribution": {
            str(length): count for length, count in sorted(processing_lengths.items())
        },
        "ordering_quality_distribution": dict(sorted(ordering_quality.items())),
        "top_unmapped_operations": [
            {"operation": operation, "records": count}
            for operation, count in unmapped.most_common(50)
        ],
    }
