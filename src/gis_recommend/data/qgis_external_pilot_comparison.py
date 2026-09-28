"""Compare external QGIS analysis evidence without granting training admission."""

from __future__ import annotations

import hashlib
import json
import re
from collections import Counter
from collections.abc import Mapping, Sequence
from typing import Any, NamedTuple

DELTA_STATES = {
    "existing_only",
    "shared_equivalent",
    "joern_only_partial",
    "joern_only_complete",
    "contradictory",
}
_SHA256 = re.compile(r"^[0-9a-f]{64}$")


class EvidenceDelta(NamedTuple):
    record_id: str
    delta_status: str
    authority_signature_sha256: str
    joern_signature_sha256: str
    source_hash_match: bool
    provenance_complete: bool
    query_runtime_failure: bool
    coverage_miss: bool
    false_complete_evidence: bool
    claimed_complete_truncation: bool
    novelty_kinds: tuple[str, ...]


def _canonical_call(value: Any) -> str:
    call = str(value or "").strip().lower()
    if not call:
        return ""
    call = call.split("(", 1)[0]
    if ":" not in call:
        call = call.rsplit(".", 1)[-1]
    return call


def _edges(value: Any) -> tuple[tuple[int, int], ...]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        return ()
    edges: set[tuple[int, int]] = set()
    for edge in value:
        if (
            isinstance(edge, Sequence)
            and not isinstance(edge, (str, bytes))
            and len(edge) == 2
            and all(isinstance(item, int) and not isinstance(item, bool) for item in edge)
        ):
            edges.add((int(edge[0]), int(edge[1])))
    return tuple(sorted(edges))


def _authority_calls(authority: Mapping[str, Any]) -> tuple[str, ...]:
    explicit = authority.get("operator_ids")
    if isinstance(explicit, Sequence) and not isinstance(explicit, (str, bytes)):
        calls = tuple(filter(None, (_canonical_call(value) for value in explicit)))
        if calls:
            return calls
    steps = authority.get("steps", [])
    if not isinstance(steps, Sequence) or isinstance(steps, (str, bytes)):
        return ()
    return tuple(
        filter(
            None,
            (
                _canonical_call(step.get("operator_id") or step.get("call_name"))
                for step in steps
                if isinstance(step, Mapping)
            ),
        )
    )


def _joern_calls(joern: Mapping[str, Any]) -> tuple[str, ...]:
    for field in ("operator_ids", "semantic_calls"):
        values = joern.get(field, [])
        if isinstance(values, Sequence) and not isinstance(values, (str, bytes)):
            calls = tuple(filter(None, (_canonical_call(value) for value in values)))
            if calls:
                return calls
    return ()


def _authority_has_terminal(authority: Mapping[str, Any]) -> bool:
    count = authority.get("terminal_evidence_count")
    if isinstance(count, int) and not isinstance(count, bool):
        return count > 0
    steps = authority.get("steps", [])
    return isinstance(steps, Sequence) and any(
        bool(step.get("terminal_evidence"))
        for step in steps
        if isinstance(step, Mapping)
    )


def _joern_has_terminal(joern: Mapping[str, Any]) -> bool:
    terminals = joern.get("terminal_node_ids", [])
    return isinstance(terminals, Sequence) and not isinstance(
        terminals, (str, bytes)
    ) and bool(terminals)


def _signature(calls: tuple[str, ...], edges: tuple[tuple[int, int], ...], terminal: bool) -> str:
    payload = {
        "calls": list(calls),
        "dependency_edges": [list(edge) for edge in edges],
        "terminal": terminal,
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode(
        "utf-8"
    )
    return hashlib.sha256(encoded).hexdigest()


def _novelty_kinds(joern: Mapping[str, Any]) -> tuple[str, ...]:
    aliases = {
        "cross_function_parameter": "cross_function_parameter",
        "cross_function_return": "cross_function_return",
        "return_propagation": "cross_function_return",
        "fqn_import": "fqn_import_resolution",
        "fqn_import_resolution": "fqn_import_resolution",
        "multi_hop_def_use": "multi_hop_def_use",
        "branch_dominance": "branch_dominance",
        "alias_propagation": "alias_propagation",
    }
    result: set[str] = set()
    queries = joern.get("queries", [])
    if not isinstance(queries, Sequence) or isinstance(queries, (str, bytes)):
        return ()
    for query in queries:
        if not isinstance(query, Mapping):
            continue
        kinds = query.get("evidence_kinds", [])
        if not isinstance(kinds, Sequence) or isinstance(kinds, (str, bytes)):
            continue
        for raw_kind in kinds:
            kind = str(raw_kind).strip().lower()
            canonical = aliases.get(kind)
            if canonical:
                result.add(canonical)
    return tuple(sorted(result))


def _provenance_complete(authority: Mapping[str, Any]) -> bool:
    declared = authority.get("provenance_complete")
    if declared is not None:
        return bool(declared)
    return bool(authority.get("source_sha256")) and bool(
        authority.get("source_path")
        or authority.get("normalized_source_body_sha256")
        or authority.get("source_authority_key")
    )


def compare_evidence(
    *, authority: Mapping[str, Any], joern: Mapping[str, Any]
) -> EvidenceDelta:
    """Classify one authority/Joern pair while preserving failure distinctions."""
    record_id = str(authority.get("record_id") or joern.get("record_id") or "")
    if not record_id or record_id != str(joern.get("record_id") or ""):
        raise ValueError("authority and Joern record_id must match")
    verdict = str(authority.get("authority_verdict") or "unresolved")
    if verdict not in {"positive", "negative", "unresolved"}:
        raise ValueError(f"unsupported authority_verdict {verdict!r}")
    joern_status = str(joern.get("evidence_status") or "")
    if joern_status not in {
        "complete",
        "partial",
        "insufficient",
        "ambiguous",
        "query_failure",
    }:
        raise ValueError(f"unsupported Joern evidence_status {joern_status!r}")

    authority_calls = _authority_calls(authority)
    authority_edges = _edges(authority.get("dependency_edges", []))
    authority_terminal = _authority_has_terminal(authority)
    joern_calls = _joern_calls(joern)
    joern_edges = _edges(joern.get("dependency_edges", []))
    joern_terminal = _joern_has_terminal(joern)
    authority_signature = _signature(
        authority_calls, authority_edges, authority_terminal
    )
    joern_signature = _signature(joern_calls, joern_edges, joern_terminal)

    claimed_truncation = joern_status == "complete" and not joern_terminal
    query_failure = joern_status == "query_failure" or bool(
        joern.get("query_failures")
    )
    coverage_miss = verdict == "positive" and joern_status in {
        "insufficient",
        "ambiguous",
        "query_failure",
    }
    false_complete = verdict == "negative" and joern_status == "complete"

    if coverage_miss:
        delta_status = "existing_only"
    elif verdict == "positive":
        equivalent = (
            joern_status in {"complete", "partial"}
            and authority_calls == joern_calls
            and authority_edges == joern_edges
            and authority_terminal == joern_terminal
        )
        delta_status = "shared_equivalent" if equivalent else "contradictory"
    elif joern_status == "complete":
        delta_status = "joern_only_complete"
    elif joern_status == "partial":
        delta_status = "joern_only_partial"
    else:
        delta_status = "existing_only"
    if claimed_truncation:
        delta_status = "contradictory"

    authority_sha = str(authority.get("source_sha256") or "").lower()
    joern_sha = str(joern.get("source_sha256") or "").lower()
    source_hash_match = bool(_SHA256.fullmatch(authority_sha)) and (
        authority_sha == joern_sha
    )
    return EvidenceDelta(
        record_id=record_id,
        delta_status=delta_status,
        authority_signature_sha256=authority_signature,
        joern_signature_sha256=joern_signature,
        source_hash_match=source_hash_match,
        provenance_complete=_provenance_complete(authority),
        query_runtime_failure=query_failure,
        coverage_miss=coverage_miss,
        false_complete_evidence=false_complete,
        claimed_complete_truncation=claimed_truncation,
        novelty_kinds=_novelty_kinds(joern),
    )


def evaluate_hard_gate(
    comparisons: Sequence[EvidenceDelta],
    *,
    expected_source_count: int,
    registry_fallback_count: int,
    datatrove_report: Mapping[str, Any],
) -> dict[str, Any]:
    """Evaluate non-negotiable pilot integrity gates."""
    metrics = {
        "source_count": len(comparisons),
        "expected_source_count": expected_source_count,
        "source_hash_mismatch_count": sum(
            not row.source_hash_match for row in comparisons
        ),
        "query_runtime_failure_count": sum(
            row.query_runtime_failure for row in comparisons
        ),
        "coverage_miss_count": sum(row.coverage_miss for row in comparisons),
        "false_complete_count": sum(
            row.false_complete_evidence for row in comparisons
        ),
        "claimed_complete_truncation_count": sum(
            row.claimed_complete_truncation for row in comparisons
        ),
        "provenance_incomplete_count": sum(
            not row.provenance_complete for row in comparisons
        ),
        "registry_fallback_count": registry_fallback_count,
        "delta_status_counts": dict(
            sorted(Counter(row.delta_status for row in comparisons).items())
        ),
    }
    failures: list[str] = []
    if len(comparisons) != expected_source_count or metrics[
        "source_hash_mismatch_count"
    ]:
        failures.append("source_hash_incomplete_or_mismatch")
    if metrics["query_runtime_failure_count"]:
        failures.append("query_or_runtime_failure")
    if metrics["false_complete_count"]:
        failures.append("false_complete_evidence")
    if metrics["claimed_complete_truncation_count"]:
        failures.append("claimed_complete_truncation")
    if registry_fallback_count:
        failures.append("registry_fallback")
    if not bool(
        datatrove_report.get("exact_reconciliation", {}).get("matched")
    ):
        failures.append("exact_cluster_reconciliation")
    if metrics["provenance_incomplete_count"]:
        failures.append("provenance_incomplete")
    return {
        "schema": "gis_recommend.qgis_external_pilot_hard_gate.v1",
        "passed": not failures,
        "failures": failures,
        "metrics": metrics,
        "training_admission": "not_granted_external_analysis_pilot_only",
        "training_rows_emitted": 0,
    }


def evaluate_promotion_gate(
    families: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    """Require one supported unresolved family with zero-FP disjoint splits."""
    eligible = sorted(
        str(row.get("family_id"))
        for row in families
        if row.get("family_id")
        and bool(row.get("previously_unresolved"))
        and int(row.get("support") or 0) >= 30
        and bool(row.get("source_disjoint"))
        and int(row.get("calibration_false_positives") or 0) == 0
        and int(row.get("holdout_false_positives") or 0) == 0
    )
    return {
        "schema": "gis_recommend.qgis_external_pilot_promotion_gate.v1",
        "passed": bool(eligible),
        "eligible_family_ids": eligible,
        "training_admission": "not_granted_external_analysis_pilot_only",
        "training_rows_emitted": 0,
    }
