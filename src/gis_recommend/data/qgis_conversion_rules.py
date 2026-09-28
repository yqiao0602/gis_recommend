"""Fail-closed routing rules for source-grounded QGIS workflow candidates."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


PROHIBITED_RULE_FIELDS = {
    "review_index",
    "record_id",
    "source_path",
    "relative_path",
    "repository",
    "repo_name",
}

NON_TRANSFORMING_INTERMEDIATE_CALLS = {"QgsRasterLayer", "print"}


@dataclass(frozen=True)
class RoutingDecision:
    rule_id: str
    action: str
    confidence: str
    evidence: dict[str, Any]


def _mapping_complete(row: dict[str, Any], features: dict[str, Any]) -> bool:
    operators = features.get("operator_ids") or []
    mapped = row.get("mapped_l3_chain") or []
    return bool(operators) and len(mapped) == len(operators) and all(mapped)


def _all_nodes_have_upstream(features: dict[str, Any]) -> bool:
    operators = features.get("operator_ids") or []
    if len(operators) <= 1:
        return bool(operators)
    consumers = {int(edge[1]) for edge in features.get("dependency_edges") or []}
    return consumers == set(range(1, len(operators)))


def route_candidate(row: dict[str, Any], features: dict[str, Any]) -> RoutingDecision:
    workflow_unit_scope = features.get("workflow_unit_scope", "unknown")
    description_requirement = {
        "whole_processing_scope": "whole_scope_task_description_required",
        "local_subworkflow": "local_subworkflow_description_required",
    }.get(workflow_unit_scope, "description_scope_unresolved")
    raw_intermediate_calls = features.get("intermediate_data_transform_calls") or []
    non_transforming_calls = [
        call for call in raw_intermediate_calls if call in NON_TRANSFORMING_INTERMEDIATE_CALLS
    ]
    blocking_intermediate_calls = [
        call for call in raw_intermediate_calls if call not in NON_TRANSFORMING_INTERMEDIATE_CALLS
    ]
    evidence = {
        "parse_status": features.get("parse_status"),
        "candidate_alignment_status": features.get("candidate_alignment_status"),
        "operator_count": len(features.get("operator_ids") or []),
        "dependency_edges": features.get("dependency_edges") or [],
        "unresolved_output_references": features.get(
            "unresolved_output_references"
        )
        or [],
        "processing_temporary_input_references": features.get(
            "processing_temporary_input_references"
        )
        or [],
        "control_flow_kinds": features.get("control_flow_kinds") or [],
        "api_pattern_count": len(row.get("api_pattern_calls") or []),
        "mapping_complete": _mapping_complete(row, features),
        "call_graph_status": row.get("call_graph_status"),
        "intermediate_data_transform_calls": blocking_intermediate_calls,
        "non_transforming_intermediate_calls": non_transforming_calls,
        "downstream_data_transform_calls": features.get(
            "downstream_data_transform_calls"
        )
        or [],
        "unused_temporary_terminal_indices": features.get(
            "unused_temporary_terminal_indices"
        )
        or [],
        "workflow_unit_scope": workflow_unit_scope,
        "structure_class": "unresolved",
        "description_requirement": description_requirement,
    }
    if features.get("parse_status") != "parsed":
        return RoutingDecision("reject-unparseable-v1", "exclude_current_chain", "high", evidence)
    if features.get("candidate_alignment_status") not in {
        "candidate_alignment_matched",
        "all_literal_calls",
    }:
        return RoutingDecision("reject-unaligned-v1", "exclude_current_chain", "high", evidence)
    if not evidence["mapping_complete"]:
        return RoutingDecision("defer-mapping-gap-v1", "defer_mapping", "high", evidence)
    if row.get("call_graph_status") == "disconnected_candidate_scopes":
        return RoutingDecision("split-disconnected-scopes-v1", "split_subworkflow", "high", evidence)
    if evidence["intermediate_data_transform_calls"]:
        evidence["structure_class"] = "blocked_custom_transform"
        return RoutingDecision(
            "review-intermediate-data-transform-v1",
            "review_api_sidecar",
            "high",
            evidence,
        )
    if row.get("api_pattern_calls"):
        return RoutingDecision("review-api-sidecar-v1", "review_api_sidecar", "medium", evidence)
    if workflow_unit_scope == "cross_scope_candidate":
        return RoutingDecision(
            "recover-cross-scope-candidate-v1",
            "recover_call_graph",
            "high",
            evidence,
        )
    if features.get("control_flow_kinds"):
        return RoutingDecision("recover-control-flow-v1", "recover_call_graph", "medium", evidence)
    if evidence["unresolved_output_references"]:
        evidence["structure_class"] = "blocked_unresolved_output_reference"
        return RoutingDecision(
            "recover-unresolved-output-reference-v1",
            "recover_call_graph",
            "high",
            evidence,
        )
    if evidence["processing_temporary_input_references"]:
        evidence["structure_class"] = "blocked_processing_temporary_input_reference"
        return RoutingDecision(
            "recover-processing-temp-input-reference-v1",
            "recover_call_graph",
            "high",
            evidence,
        )
    if not _all_nodes_have_upstream(features):
        return RoutingDecision("recover-missing-data-edges-v1", "recover_call_graph", "high", evidence)
    if evidence["downstream_data_transform_calls"]:
        evidence["structure_class"] = "blocked_downstream_transform"
        return RoutingDecision(
            "review-downstream-data-transform-v1",
            "review_api_sidecar",
            "high",
            evidence,
        )
    if evidence["unused_temporary_terminal_indices"]:
        evidence["structure_class"] = "blocked_unused_temporary_terminal"
        return RoutingDecision(
            "recover-unused-temporary-terminal-v1",
            "recover_call_graph",
            "high",
            evidence,
        )
    evidence["structure_class"] = (
        "valid_local_subworkflow_candidate"
        if workflow_unit_scope == "local_subworkflow"
        else "valid_whole_processing_scope_candidate"
    )
    return RoutingDecision("direct-explicit-dag-v1", "auto_accept_candidate", "high", evidence)


def validate_rule_fields(fields: set[str]) -> None:
    forbidden = fields & PROHIBITED_RULE_FIELDS
    if forbidden:
        raise ValueError(f"identity fields are prohibited in conversion rules: {sorted(forbidden)}")
