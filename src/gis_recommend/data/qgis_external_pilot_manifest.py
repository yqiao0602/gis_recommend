"""Deterministic target and regression manifests for the QGIS sidecar pilot."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable, Mapping, Sequence
from collections import Counter
from pathlib import Path
from typing import Any


PROCESSING_PRIORITY = (
    "conditional_early_exit",
    "control_flow:for",
    "missing_data_edges",
    "cross_function_helper",
    "cross_function_return",
    "output_alias",
    "result_dictionary",
    "dynamic_operator_id",
    "fill",
)

API_PRIORITY = (
    "cross_function_geometry",
    "cross_function_mutation_export",
    "interleaved_control_flow",
    "terminal_sink",
    "fill",
)

TARGET_FIELDS = (
    "record_id",
    "candidate_id",
    "unit_id",
    "source_path",
    "relative_path",
    "source_root_id",
    "source_sha256",
    "normalized_source_body_sha256",
    "source_authority_key",
    "action",
    "rule_id",
    "structure_rule_id",
    "boundary_rule_id",
    "slice_status",
    "boundary_status",
    "mapping_status",
    "normalization_status",
    "blocker_reasons",
    "families",
    "family_evidence_counts",
    "family_support_max",
    "family_signatures",
    "upstream_call_families",
    "pattern_names",
    "terminal_evidence_count",
    "terminal_payload_status",
    "source_span",
)

BASELINE_FIELDS = (
    "record_id",
    "candidate_id",
    "unit_id",
    "sample_id",
    "source_path",
    "source_paths",
    "relative_path",
    "source_root_id",
    "source_sha256",
    "source_sha256s",
    "normalized_source_body_sha256",
    "source_authority_key",
    "chain",
    "operator_sequence",
    "qgis_operator_chain",
    "operator_ids",
    "dependency_edges",
    "source_span",
    "call_graph_key",
    "known_omissions",
    "condition_family_ids",
    "condition_paths",
    "condition_support_status",
    "family_support_authorities_by_id",
    "units",
    "downstream_calls",
    "downstream_low_level_roles",
    "downstream_role_status",
    "proposal_decision",
    "failure_labels",
    "reason",
    "steps",
    "terminal_evidence_count",
    "boundary_status",
    "boundary_rule_id",
)


def _strings(value: Any) -> list[str]:
    if isinstance(value, str):
        return [value] if value else []
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
        return [str(item) for item in value if str(item)]
    return []


def _body_sha(row: Mapping[str, Any]) -> str:
    body = str(row.get("normalized_source_body_sha256") or "")
    if not body:
        authority = str(row.get("source_authority_key") or "")
        prefix = "normalized_source_body_sha256:"
        if authority.startswith(prefix):
            body = authority.removeprefix(prefix)
    if len(body) != 64:
        raise ValueError("target row lacks normalized source body authority")
    return body


def _source_sha(row: Mapping[str, Any]) -> str:
    source_sha = str(row.get("source_sha256") or "")
    if len(source_sha) != 64:
        raise ValueError("target row lacks source_sha256")
    return source_sha


def _stable_key(row: Mapping[str, Any]) -> tuple[str, str, str, str]:
    return (
        _body_sha(row),
        _source_sha(row),
        str(row.get("record_id") or ""),
        str(row.get("candidate_id") or row.get("unit_id") or ""),
    )


def _processing_strata(row: Mapping[str, Any]) -> tuple[str, ...]:
    explicit = str(row.get("primary_stratum") or "")
    if explicit:
        return (explicit,)

    blockers = set(_strings(row.get("blocker_reasons")))
    families = set(_strings(row.get("families")))
    structure = row.get("structure_evidence")
    if isinstance(structure, Mapping):
        blockers.update(_strings(structure.get("local_structure_reasons")))
        blockers.update(
            f"control_flow:{kind}"
            for kind in _strings(structure.get("control_flow_kinds"))
        )

    strata: list[str] = []
    for blocker in PROCESSING_PRIORITY[:3]:
        if blocker in blockers:
            strata.append(blocker)
    if "helper_function_call" in families or bool(row.get("cross_scope_candidate")):
        strata.append("cross_function_helper")
    if "immediate_output_extract" in families:
        strata.append("cross_function_return")
    if "output_alias" in families or int(row.get("output_alias_key_count") or 0) > 0:
        strata.append("output_alias")
    if "result_dictionary" in families:
        strata.append("result_dictionary")
    unresolved = _strings(row.get("unresolved_operator_ids"))
    if unresolved or "dynamic_operator_id" in families:
        strata.append("dynamic_operator_id")
    return tuple(dict.fromkeys(strata)) or ("fill",)


def _api_strata(row: Mapping[str, Any]) -> tuple[str, ...]:
    explicit = str(row.get("primary_stratum") or "")
    if explicit:
        return (explicit,)

    strata: list[str] = []
    caller_provenance = row.get("caller_payload_provenance")
    upstream_families = set(_strings(row.get("upstream_call_families")))
    patterns = set(_strings(row.get("pattern_names")))
    if caller_provenance or "geometry_return" in upstream_families:
        strata.append("cross_function_geometry")
    if str(row.get("slice_status") or "") == "resolved_local_call_chain":
        strata.append("cross_function_mutation_export")
    steps = row.get("steps")
    has_control_path = isinstance(steps, Sequence) and any(
        isinstance(step, Mapping) and bool(step.get("control_path")) for step in steps
    )
    if has_control_path or bool(row.get("equivalent_branch_definitions")):
        strata.append("interleaved_control_flow")
    if int(row.get("terminal_evidence_count") or 0) > 0 or "sink_output" in patterns:
        strata.append("terminal_sink")
    return tuple(dict.fromkeys(strata)) or ("fill",)


def _select(
    rows: Iterable[Mapping[str, Any]],
    *,
    limit: int,
    priority: tuple[str, ...],
    classifier: Any,
    corpus_kind: str,
    priority_tiers: tuple[tuple[str, ...], ...],
    excluded_bodies: set[str] | None,
    excluded_source_shas: set[str] | None,
) -> list[dict[str, Any]]:
    excluded_bodies = excluded_bodies or set()
    excluded_source_shas = excluded_source_shas or set()
    best_by_body: dict[str, dict[str, Any]] = {}

    for original in rows:
        body = _body_sha(original)
        source_sha = _source_sha(original)
        if body in excluded_bodies or source_sha in excluded_source_shas:
            continue
        strata = classifier(original)
        primary = min(
            strata,
            key=lambda name: priority.index(name) if name in priority else len(priority),
        )
        row = {key: original[key] for key in TARGET_FIELDS if key in original}
        row.update(
            {
                "schema": "gis_recommend.qgis_external_pilot_target.v1",
                "corpus_kind": corpus_kind,
                "normalized_source_body_sha256": body,
                "source_authority_key": f"normalized_source_body_sha256:{body}",
                "source_sha256": source_sha,
                "primary_stratum": primary,
                "strata": list(strata),
                "training_admission": "not_granted_external_analysis_pilot_only",
                "training_row_emitted": False,
            }
        )
        prior = best_by_body.get(body)
        if prior is None:
            best_by_body[body] = row
            continue
        prior_rank = priority.index(prior["primary_stratum"]) if prior["primary_stratum"] in priority else len(priority)
        row_rank = priority.index(primary) if primary in priority else len(priority)
        if (row_rank, _stable_key(row)) < (prior_rank, _stable_key(prior)):
            best_by_body[body] = row

    ranked: dict[str, list[dict[str, Any]]] = {name: [] for name in priority}
    for row in best_by_body.values():
        for stratum in row["strata"]:
            ranked.setdefault(stratum, []).append(row)
    for group in ranked.values():
        group.sort(key=_stable_key)

    selected: list[dict[str, Any]] = []
    selected_bodies: set[str] = set()

    for tier in priority_tiers:
        positions = {stratum: 0 for stratum in tier}
        while len(selected) < limit:
            made_progress = False
            for stratum in tier:
                group = ranked.get(stratum, [])
                position = positions[stratum]
                while (
                    position < len(group)
                    and group[position]["normalized_source_body_sha256"]
                    in selected_bodies
                ):
                    position += 1
                positions[stratum] = position
                if position >= len(group):
                    continue
                row = dict(group[position])
                positions[stratum] += 1
                row["primary_stratum"] = stratum
                selected.append(row)
                selected_bodies.add(row["normalized_source_body_sha256"])
                made_progress = True
                if len(selected) >= limit:
                    break
            if not made_progress:
                break
        if len(selected) >= limit:
            break
    return selected


def select_processing(
    rows: Iterable[Mapping[str, Any]],
    *,
    limit: int,
    excluded_bodies: set[str] | None = None,
    excluded_source_shas: set[str] | None = None,
) -> list[dict[str, Any]]:
    return _select(
        rows,
        limit=limit,
        priority=PROCESSING_PRIORITY,
        classifier=_processing_strata,
        corpus_kind="processing",
        priority_tiers=(PROCESSING_PRIORITY[:3], PROCESSING_PRIORITY[3:]),
        excluded_bodies=excluded_bodies,
        excluded_source_shas=excluded_source_shas,
    )


def select_api(
    rows: Iterable[Mapping[str, Any]],
    *,
    limit: int,
    excluded_bodies: set[str] | None = None,
    excluded_source_shas: set[str] | None = None,
) -> list[dict[str, Any]]:
    return _select(
        rows,
        limit=limit,
        priority=API_PRIORITY,
        classifier=_api_strata,
        corpus_kind="api",
        priority_tiers=(API_PRIORITY[:4], API_PRIORITY[4:]),
        excluded_bodies=excluded_bodies,
        excluded_source_shas=excluded_source_shas,
    )


def build_target_manifest(
    processing_rows: Iterable[Mapping[str, Any]],
    api_rows: Iterable[Mapping[str, Any]],
    *,
    processing_limit: int = 100,
    api_limit: int = 100,
    excluded_bodies: set[str] | None = None,
    excluded_source_shas: set[str] | None = None,
) -> list[dict[str, Any]]:
    processing = select_processing(
        processing_rows,
        limit=processing_limit,
        excluded_bodies=excluded_bodies,
        excluded_source_shas=excluded_source_shas,
    )
    if len(processing) != processing_limit:
        raise ValueError(f"could not select {processing_limit} Processing targets")
    processing_bodies = {
        row["normalized_source_body_sha256"] for row in processing
    }
    api = select_api(
        api_rows,
        limit=api_limit,
        excluded_bodies=(excluded_bodies or set()) | processing_bodies,
        excluded_source_shas=excluded_source_shas,
    )
    if len(api) != api_limit:
        raise ValueError(f"could not select {api_limit} API targets")
    manifest = processing + api
    for index, row in enumerate(manifest, start=1):
        row["target_index"] = index
        row["target_id"] = f"qgis-external-pilot-{row['corpus_kind']}-{index:03d}"
    return manifest


def build_api_baseline(rows: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    baseline: list[dict[str, Any]] = []
    decisions = {"true_positive": "positive", "false_positive": "negative"}
    for original in rows:
        decision = str(original.get("proposal_decision") or "")
        item_id = str(original.get("candidate_id") or original.get("unit_id") or "")
        if decision not in decisions or not item_id:
            raise ValueError("API baseline requires a hash-bound persisted verdict per item")
        row = _baseline_row(
            original,
            role="api_reviewed_boundary",
            verdict=decisions[decision],
        )
        baseline.append(row)
    return sorted(baseline, key=_baseline_key)


def _baseline_key(row: Mapping[str, Any]) -> tuple[str, str, str, str]:
    source_shas = _strings(row.get("source_sha256s"))
    return (
        str(row.get("baseline_role") or ""),
        str(row.get("normalized_source_body_sha256") or ""),
        str(row.get("source_sha256") or (source_shas[0] if source_shas else "")),
        str(row.get("candidate_id") or row.get("unit_id") or row.get("sample_id") or ""),
    )


def _baseline_row(
    original: Mapping[str, Any], *, role: str, verdict: str
) -> dict[str, Any]:
    row = {key: original[key] for key in BASELINE_FIELDS if key in original}
    authority = str(original.get("source_authority_key") or "")
    body = str(original.get("normalized_source_body_sha256") or "")
    if not body and authority.startswith("normalized_source_body_sha256:"):
        body = authority.removeprefix("normalized_source_body_sha256:")
    source_sha = str(original.get("source_sha256") or "")
    source_shas = _strings(original.get("source_sha256s"))
    if not source_sha and not source_shas:
        raise ValueError(f"{role} baseline row lacks source hash")
    if not authority:
        authority = (
            f"normalized_source_body_sha256:{body}"
            if body
            else f"source_sha256:{source_sha or source_shas[0]}"
        )
    row.update(
        {
            "schema": "gis_recommend.qgis_external_pilot_baseline.v1",
            "baseline_role": role,
            "authority_verdict": verdict,
            "source_authority_key": authority,
            "training_admission": "not_granted_external_analysis_pilot_only",
            "training_row_emitted": False,
        }
    )
    if body:
        row["normalized_source_body_sha256"] = body
    if source_sha:
        row["source_sha256"] = source_sha
    if source_shas:
        row["source_sha256s"] = source_shas
    return row


def build_regression_baseline(
    *,
    processing_accepted: Iterable[Mapping[str, Any]],
    same_if_deferred: Iterable[Mapping[str, Any]],
    downstream_negatives: Iterable[Mapping[str, Any]],
    api_reviewed: Iterable[Mapping[str, Any]],
    api_postfilter_negatives: Iterable[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    rows.extend(
        _baseline_row(row, role="processing_accepted_chain", verdict="positive")
        for row in processing_accepted
    )
    rows.extend(
        _baseline_row(
            row,
            role="processing_same_if_support_deferred",
            verdict="support_deferred",
        )
        for row in same_if_deferred
    )
    rows.extend(
        _baseline_row(
            row,
            role="processing_downstream_boundary_negative",
            verdict="negative",
        )
        for row in downstream_negatives
    )
    rows.extend(build_api_baseline(api_reviewed))
    rows.extend(
        _baseline_row(
            row,
            role="api_postfilter_boundary_negative",
            verdict="negative",
        )
        for row in api_postfilter_negatives
    )
    return sorted(rows, key=_baseline_key)


def _json_line(row: Mapping[str, Any]) -> str:
    return json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _atomic_write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(content, encoding="utf-8", newline="\n")
    temporary.replace(path)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_pilot_artifacts(
    output_dir: Path,
    target_manifest: Sequence[Mapping[str, Any]],
    regression_baseline: Sequence[Mapping[str, Any]],
    *,
    input_hashes: Mapping[str, str],
) -> dict[str, Any]:
    """Write the four bounded Task 1 artifacts with stable bytes and hashes."""
    output_dir.mkdir(parents=True, exist_ok=True)
    target_path = output_dir / "target_manifest_200_v1.jsonl"
    baseline_path = output_dir / "regression_baseline_v1.jsonl"
    summary_path = output_dir / "selection_summary_v1.json"
    ledger_path = output_dir / "hash_ledger_v1.json"

    _atomic_write(
        target_path,
        "".join(f"{_json_line(row)}\n" for row in target_manifest),
    )
    _atomic_write(
        baseline_path,
        "".join(f"{_json_line(row)}\n" for row in regression_baseline),
    )
    summary = {
        "schema": "gis_recommend.qgis_external_pilot_selection_summary.v1",
        "target_rows": len(target_manifest),
        "target_counts": dict(
            sorted(Counter(str(row["corpus_kind"]) for row in target_manifest).items())
        ),
        "target_strata": dict(
            sorted(Counter(str(row["primary_stratum"]) for row in target_manifest).items())
        ),
        "target_unique_normalized_bodies": len(
            {str(row["normalized_source_body_sha256"]) for row in target_manifest}
        ),
        "baseline_rows": len(regression_baseline),
        "baseline_roles": dict(
            sorted(
                Counter(str(row["baseline_role"]) for row in regression_baseline).items()
            )
        ),
        "training_rows_emitted": 0,
        "production_merge": "not_granted",
    }
    _atomic_write(summary_path, _json_line(summary) + "\n")

    artifacts = {}
    for path in (target_path, baseline_path, summary_path):
        artifacts[path.name] = {"sha256": _sha256(path), "bytes": path.stat().st_size}
    ledger = {
        "schema": "gis_recommend.qgis_external_pilot_hash_ledger.v1",
        "input_hashes": dict(sorted(input_hashes.items())),
        "artifacts": artifacts,
    }
    _atomic_write(ledger_path, _json_line(ledger) + "\n")
    return summary
