"""Adapter from source-backed helper expansion units to existing QGIS gates."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from typing import Any

ADAPTER_VERSION = "qgis_processing_expanded_adapter_v1"


def _key(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def _normalized_text(value: Any) -> str:
    return "".join(str(value or "").lower().split())


def _source_region_key(row: Mapping[str, Any]) -> str:
    """Authority derivation: scripts.run_qgis_processing_batch._source_region_key.

    Structural keys must come from the same derivation the freeze baseline and
    the processing replay ledger use; the adapter must not invent a third
    algorithm or the cross-pool dedup becomes incomparable.
    """

    spans = [
        {
            "line_start": int(site["line_start"]),
            "line_end": int(site["line_end"]),
        }
        for site in row.get("call_sites") or []
    ]
    return _key({"source_sha256": row["source_sha256"], "call_spans": spans})


def _call_graph_key(row: Mapping[str, Any]) -> str:
    """Authority derivation: scripts.run_qgis_processing_batch._call_graph_key."""

    calls = [
        {
            "ordinal": int(site.get("ordinal") or index + 1),
            "operator_id": str(site.get("operator_id") or ""),
            "line_start": int(site["line_start"]),
            "line_end": int(site["line_end"]),
        }
        for index, site in enumerate(row.get("call_sites") or [])
    ]
    return _key(
        {
            "source_sha256": row["source_sha256"],
            "calls": calls,
            "dependency_edges": row.get("dependency_edges") or [],
        }
    )


def _normalized_dag_key(row: Mapping[str, Any]) -> str:
    """Authority derivation: scripts.run_qgis_processing_batch._normalized_dag_key."""

    operators = [
        str(value)
        for value in (
            row.get("operator_sequence")
            or row.get("operator_ids")
            or row.get("ordered_operator_ids")
            or row.get("canonical_operator_ids")
            or []
        )
    ]
    return _key(
        {
            "operator_ids": operators,
            "dependency_edges": row.get("dependency_edges") or [],
            "workflow_unit_scope": row.get("workflow_unit_scope")
            or row.get("workflow_scope"),
        }
    )


def _training_pair_key(row: Mapping[str, Any]) -> str:
    """Authority derivation: scripts.run_qgis_processing_batch._training_pair_key.

    The unified training-pair key is the cross-pool duplicate decision key
    (same pair is a duplicate regardless of how the chain was recovered).  It
    requires task text and L3, so it is computed after description/L3 and never
    inside the adapter itself.
    """

    return _key(
        {
            "task_name": _normalized_text(row.get("task_name")),
            "task_description": _normalized_text(row.get("task_description")),
            "operator_sequence": [
                str(value)
                for value in (
                    row.get("operator_sequence")
                    or row.get("operator_ids")
                    or row.get("ordered_operator_ids")
                    or row.get("canonical_operator_ids")
                    or []
                )
            ],
            "l3_code_sequence": list(row.get("l3_code_sequence") or []),
        }
    )


def _source_snippet(unit: dict[str, Any]) -> str:
    segments = unit.get("source_segments") or {}
    helper = str(segments.get("helper") or "")
    caller = str(segments.get("caller") or "")
    if not helper or not caller:
        raise ValueError("expanded unit must retain helper and caller source segments")
    return f"{helper}\n...\n{caller}"


def adapt_expanded_unit(unit: dict[str, Any], *, source_path: str) -> dict[str, Any]:
    """Return a downstream-compatible local-subworkflow record without rewriting source."""

    operators = [str(value).lower() for value in unit.get("canonical_operator_ids") or []]
    call_sites = list(unit.get("call_sites") or [])
    edges = list(unit.get("dependency_edges") or [])
    if not operators or len(operators) != len(call_sites) or not edges:
        raise ValueError("expanded unit is missing a complete operator DAG")
    if not str(unit.get("recovery_method") or "").startswith("cross_function_inline_v1"):
        raise ValueError("adapter only accepts cross_function_inline_v1 units")
    snippet = _source_snippet(unit)
    source_sha256 = str(unit.get("source_sha256") or "")
    if not source_sha256 or not source_path:
        raise ValueError("expanded unit is missing source identity")
    adapted = {
        **unit,
        "schema": "gis_recommend.qgis_expanded_local_unit_adapter.v1",
        "adapter_version": ADAPTER_VERSION,
        "source_path": source_path,
        "canonical_operator_ids": operators,
        "operator_ids": operators,
        "ordered_operator_ids": operators,
        "call_sites": call_sites,
        "dependency_edges": edges,
        "workflow_unit_scope": "local_subworkflow",
        "structure_action": "auto_accept_candidate",
        "structure_rule_id": "cross-function-inline-single-helper-v1",
        "source_snippet": snippet,
        "source_span": {"call_sites": call_sites, "segments": unit["source_segments"]},
        # Parameter values remain omitted unless the deterministic description
        # policy independently recognizes them. The full proof is retained.
        "parameter_facts": [{} for _ in operators],
        "parameter_evidence_status": "verified_cross_function_binding",
        "feature_signature_hash": _key({"operators": operators, "edges": edges}),
        # Structural keys use the authority derivations so candidates compare
        # against the frozen baseline and the processing replay ledger.
        "source_region_key": _source_region_key(
            {"source_sha256": source_sha256, "call_sites": call_sites}
        ),
        "call_graph_key": _call_graph_key(
            {
                "source_sha256": source_sha256,
                "call_sites": call_sites,
                "dependency_edges": edges,
            }
        ),
        "normalized_dag_key": _normalized_dag_key(
            {
                "operator_ids": operators,
                "dependency_edges": edges,
                "workflow_unit_scope": "local_subworkflow",
            }
        ),
        "training_admission": "not_granted_pending_l3_description_dedup",
        "training_row_emitted": False,
        "validation_eligible": False,
        "test_eligible": False,
        "production_merge": "not_granted",
    }
    return adapted
