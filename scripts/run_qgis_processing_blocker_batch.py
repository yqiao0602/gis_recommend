#!/usr/bin/env python3
"""Replay unresolved QGIS Processing blockers into an auditable candidate batch."""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import sys
import tempfile
from collections import Counter, defaultdict, deque
from pathlib import Path
from typing import Any, Iterable


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

from build_qgis_direct_description_candidates import build_candidates
from build_qgis_recovery_local_dag_units import build_recovery_units
from build_qgis_split_subworkflow_units import build_split_units
from gate_qgis_recovered_processing_l3 import (
    apply_l3_gate,
    load_composed_mapping,
    load_explicit_mapping_authority,
)
from recover_qgis_legacy_provider_ids import load_catalog_ids, recover_row
from run_qgis_processing_batch import _dedup_keys
from gis_recommend.data.qgis_source_authority import source_authority


SCHEMA = "gis_recommend.qgis_processing_blocker_batch.v1"
POLICY_VERSION = "qgis-processing-blocker-batch-v1"
MAPPING_AUTHORITY = (
    "stable110_plus_exact_existing_l3_provider_aliases_and_exclusions_v1"
)
BLOCKER_ACTIONS = {
    "recover_call_graph",
    "split_subworkflow",
    "defer_operator_resolution",
}
RULE_SIGNATURE_FIELDS = (
    "candidate_lane",
    "policy_version",
    "feature_extractor_version",
    "splitter_version",
    "recovery_rule_id",
    "parent_rule_id",
    "description_policy",
    "description_source",
    "local_structure_status",
    "split_class",
    "parameter_evidence_status",
    "workflow_unit_scope",
)
DEFAULT_DIRECT_RECORD_IDS = [
    "75d61f25ddb86ea9d5e4531d",
    "a1c59ad27c1c3530ab2c4d50",
]

DEFAULT_LATEST_REPLAY = (
    ROOT
    / "docs/reports/qgis_processing_mapping_gap_stable106_v1"
    / "lineintersections_mapping_correction_v1/replay_v1/l3_gated_manifest_v1.jsonl"
)
DEFAULT_UNIFIED_LEDGER = (
    ROOT
    / "docs/reports/qgis_processing_unified_replay_v1/full_8466_v1"
    / "processing_replay_ledger_v1.jsonl"
)
DEFAULT_TRAIN_AUTHORITY = (
    ROOT / "docs/reports/qgis_train_authority_v1/qgis_unified_train_v1.jsonl"
)
DEFAULT_CROSSWALK = (
    ROOT
    / "docs/reports/qgis_mapping_coverage_audit_2026-07-23"
    / "qgis_alg_id_crosswalk_v1.json"
)
DEFAULT_STABLE98 = (
    ROOT
    / "docs/reports/qgis_mapping_coverage_audit_2026-07-23"
    / "qgis_mapping_authority_stable98_delta_draft_v1.json"
)
DEFAULT_STABLE101 = (
    ROOT
    / "docs/reports/qgis_mapping_high_impact_blockers_2026-07-24"
    / "qgis_mapping_authority_stable101_conservative_delta_draft_v1.json"
)
DEFAULT_ADDITIONAL_DELTAS = [
    ROOT
    / "docs/reports/qgis_processing_mapping_gap_stable106_v1"
    / "stable106_mapping_delta_v1.json",
    ROOT
    / "docs/reports/qgis_processing_mapping_gap_stable106_v1"
    / "stable108_authority_v1/stable108_mapping_delta_v1.json",
    ROOT
    / "docs/reports/qgis_processing_mapping_gap_stable106_v1"
    / "stable110_authority_v1/stable110_mapping_delta_v1.json",
    ROOT
    / "docs/reports/qgis_processing_mapping_gap_stable110_alias_replay_v2"
    / "exact_l3_authority_v1/mapping_delta_v1.json",
    ROOT
    / "docs/reports/qgis_processing_mapping_gap_stable106_v1"
    / "lineintersections_mapping_correction_v1/mapping_correction_v1.json",
    ROOT
    / "docs/reports/qgis_processing_operator_expansion_v1"
    / "provider_equivalence_authority_v1.json",
    ROOT
    / "docs/reports/qgis_processing_semantic_mapping_exclusions_v1"
    / "authority_v1.json",
]


def _identity(row: dict[str, Any]) -> tuple[str, str]:
    return str(row.get("record_id") or ""), str(row.get("source_sha256") or "")


def _index_unique(
    rows: Iterable[dict[str, Any]], label: str
) -> dict[tuple[str, str], dict[str, Any]]:
    result: dict[tuple[str, str], dict[str, Any]] = {}
    for row in rows:
        key = _identity(row)
        if not all(key) or key in result:
            raise ValueError(f"{label} contains blank or duplicate identity: {key!r}")
        result[key] = row
    return result


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    with path.open(encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def select_blocker_rows(
    latest_rows: list[dict[str, Any]],
    ledger_rows: list[dict[str, Any]],
    *,
    actions: set[str] | None = None,
) -> list[dict[str, Any]]:
    latest = _index_unique(latest_rows, "latest replay")
    selected_actions = actions or BLOCKER_ACTIONS
    blockers = [
        row for row in ledger_rows if str(row.get("route_action")) in selected_actions
    ]
    ledger = _index_unique(blockers, "unified blocker ledger")
    selected: list[dict[str, Any]] = []
    for key in sorted(ledger):
        source = latest.get(key)
        if source is None:
            raise ValueError(f"blocker identity is absent from latest replay: {key!r}")
        if source.get("action") != ledger[key].get("route_action"):
            raise ValueError(f"blocker action mismatch for {key!r}")
        selected.append(dict(source))
    return selected


def select_current_action_rows(
    latest_rows: list[dict[str, Any]], *, actions: set[str] | None = None
) -> list[dict[str, Any]]:
    selected_actions = actions or BLOCKER_ACTIONS
    return sorted(
        (dict(row) for row in latest_rows if str(row.get("action")) in selected_actions),
        key=_identity,
    )


def select_action_transitions(
    current_rows: list[dict[str, Any]], previous_rows: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    previous = _index_unique(previous_rows, "previous replay")
    selected: list[dict[str, Any]] = []
    for row in current_rows:
        key = _identity(row)
        prior = previous.get(key)
        if prior is None:
            raise ValueError(f"missing previous replay identity: {key!r}")
        if prior.get("action") != row.get("action"):
            selected.append(dict(row))
    return selected


def select_direct_rows(
    latest_rows: list[dict[str, Any]],
    record_ids: list[str],
    *,
    include_all: bool = False,
) -> list[dict[str, Any]]:
    by_record: dict[str, dict[str, Any]] = {}
    for row in latest_rows:
        record_id = str(row.get("record_id") or "")
        if record_id in by_record:
            raise ValueError(f"duplicate latest replay record_id: {record_id!r}")
        by_record[record_id] = row
    if include_all:
        return [
            dict(by_record[record_id])
            for record_id in sorted(by_record)
            if by_record[record_id].get("action") == "auto_accept_candidate"
        ]
    selected = []
    for record_id in record_ids:
        row = by_record.get(record_id)
        if row is None:
            raise ValueError(f"direct record_id not found: {record_id}")
        if row.get("action") != "auto_accept_candidate":
            raise ValueError(f"direct record {record_id} is not auto_accept_candidate")
        selected.append(dict(row))
    return selected


def resolve_source_rows(
    rows: list[dict[str, Any]], prefix_aliases: list[tuple[str, str]]
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    resolved: list[dict[str, Any]] = []
    failures: list[dict[str, Any]] = []
    for source in rows:
        row = dict(source)
        declared = Path(str(row.get("source_path") or ""))
        expected = str(row.get("source_sha256") or "")
        if declared.is_file():
            if _sha256(declared) == expected:
                row["source_path_resolution"] = "verified_exact"
                resolved.append(row)
            else:
                row["source_path_resolution"] = "source_sha256_mismatch"
                failures.append(row)
            continue

        match: Path | None = None
        declared_text = str(declared)
        for old, new in prefix_aliases:
            try:
                suffix = declared.relative_to(Path(old))
            except ValueError:
                continue
            candidate = Path(new) / suffix
            if candidate.is_file() and _sha256(candidate) == expected:
                match = candidate
                break
        if match is None:
            row["source_path_resolution"] = "source_file_missing"
            failures.append(row)
            continue
        row["source_path_original"] = declared_text
        row["source_path"] = str(match)
        row["source_path_resolution"] = "verified_prefix_alias"
        resolved.append(row)
    return resolved, failures


def _aligned_candidate(row: dict[str, Any]) -> bool:
    operators = list(row.get("operator_ids") or row.get("canonical_operator_ids") or [])
    l3_codes = list(row.get("mapped_l3_chain") or [])
    sites = list(row.get("call_sites") or [])
    if not operators or len(operators) != len(l3_codes) or len(operators) != len(sites):
        return False
    count = len(operators)
    return all(
        len(edge) == 2
        and 0 <= int(edge[0]) < count
        and 0 <= int(edge[1]) < count
        and int(edge[0]) != int(edge[1])
        for edge in row.get("dependency_edges") or []
    )


def _candidate_id(lane: str, row: dict[str, Any]) -> str:
    payload = {
        "lane": lane,
        "source_sha256": row.get("source_sha256"),
        "unit_id": row.get("unit_id"),
        "record_id": row.get("record_id") or row.get("parent_record_id"),
        "call_sites": row.get("call_sites") or [],
    }
    digest = hashlib.sha256(
        json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
    ).hexdigest()
    return f"qgis_blocker_{lane}_{digest[:24]}"


def _as_candidate(row: dict[str, Any], lane: str) -> dict[str, Any]:
    candidate = dict(row)
    candidate["record_id"] = str(
        row.get("record_id") or row.get("parent_record_id") or ""
    )
    candidate.update(
        {
            "schema": SCHEMA,
            "policy_version": POLICY_VERSION,
            "candidate_id": _candidate_id(lane, row),
            "candidate_lane": lane,
            "training_admission": "not_granted",
            "training_row_emitted": False,
            "validation_eligible": False,
            "test_eligible": False,
            "production_merge": "not_granted",
            "llm_called": False,
        }
    )
    return candidate


def build_candidate_pool(
    recovery_rows: list[dict[str, Any]],
    split_rows: list[dict[str, Any]],
    operator_rows: list[dict[str, Any]],
    *,
    direct_rows: list[dict[str, Any]] | None = None,
    operator_recovery_rows: list[dict[str, Any]] | None = None,
    operator_split_rows: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    for row in direct_rows or []:
        if (
            row.get("action") == "auto_accept_candidate"
            and row.get("mapping_complete") is True
            and row.get("description_fidelity_passed") is True
            and row.get("parameter_evidence_status") == "verified_source_ast"
            and _aligned_candidate(row)
        ):
            candidates.append(_as_candidate(row, "direct"))
    for row in recovery_rows:
        if (
            row.get("description_fidelity_passed") is True
            and row.get("local_structure_status") == "eligible"
            and not (row.get("local_structure_reasons") or [])
            and _aligned_candidate(row)
        ):
            candidates.append(_as_candidate(row, "recovery_multistep"))
    for row in split_rows:
        common = (
            row.get("description_fidelity_passed") is True
            and not (row.get("local_structure_reasons") or [])
            and _aligned_candidate(row)
        )
        if not common:
            continue
        if (
            row.get("split_class") == "multi_step_local_dag"
            and row.get("local_structure_status") == "eligible"
        ):
            candidates.append(_as_candidate(row, "split_multistep"))
        elif row.get("split_class") == "single_step_local_unit":
            candidates.append(_as_candidate(row, "split_single_step"))
    for row in operator_rows:
        if (
            row.get("action") == "auto_accept_candidate"
            and row.get("mapping_complete") is True
            and row.get("description_fidelity_passed") is True
            and row.get("parameter_evidence_status") == "verified_source_ast"
            and _aligned_candidate(row)
        ):
            candidates.append(_as_candidate(row, "operator_resolution_direct"))
    for row in operator_recovery_rows or []:
        if (
            row.get("description_fidelity_passed") is True
            and row.get("local_structure_status") == "eligible"
            and not (row.get("local_structure_reasons") or [])
            and _aligned_candidate(row)
        ):
            candidates.append(_as_candidate(row, "operator_resolution_recovery"))
    for row in operator_split_rows or []:
        common = (
            row.get("description_fidelity_passed") is True
            and not (row.get("local_structure_reasons") or [])
            and _aligned_candidate(row)
        )
        if not common:
            continue
        if (
            row.get("split_class") == "multi_step_local_dag"
            and row.get("local_structure_status") == "eligible"
        ):
            lane = "operator_resolution_split_multi"
        elif row.get("split_class") == "single_step_local_unit":
            lane = "operator_resolution_split_single"
        else:
            continue
        candidates.append(_as_candidate(row, lane))
    return sorted(candidates, key=lambda row: row["candidate_id"])


def enrich_source_authority(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for source in rows:
        row = dict(source)
        row.update(
            source_authority(
                Path(str(row.get("source_path") or "")),
                source_sha256=str(row.get("source_sha256") or ""),
            )
        )
        result.append(row)
    return result


def annotate_dedup(
    candidates: list[dict[str, Any]], train_rows: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    indexes: dict[str, dict[str, str]] = {
        name: {} for name in ("source_region", "call_graph", "normalized_dag", "training_pair")
    }
    for row in train_rows:
        reference = str(row.get("sample_id") or row.get("record_id") or "existing_train")
        for name, value in _dedup_keys(row).items():
            indexes[name].setdefault(value, reference)

    output: list[dict[str, Any]] = []
    for source in sorted(
        candidates,
        key=lambda row: str(row.get("candidate_id") or row.get("record_id") or ""),
    ):
        row = dict(source)
        reference = str(
            row.get("candidate_id") or f"qgis_direct_{row.get('record_id', '')}"
        )
        row["dedup_candidate_reference"] = reference
        keys = _dedup_keys(row)
        matches = {name: indexes[name].get(value, "") for name, value in keys.items()}
        suppressing = next(
            (
                (name, matches[name])
                for name in ("source_region", "call_graph", "training_pair")
                if matches[name]
            ),
            None,
        )
        row.update({f"dedup_{name}_key": value for name, value in keys.items()})
        row["dedup_normalized_dag_match"] = matches["normalized_dag"]
        if suppressing:
            name, reference = suppressing
            row["dedup_status"] = f"duplicate_{name}"
            row["dedup_duplicate_of"] = reference
        else:
            row["dedup_status"] = "canonical_candidate"
            row["dedup_duplicate_of"] = ""
            for name, value in keys.items():
                indexes[name].setdefault(value, reference)
        output.append(row)
    return output


def _selection_key(row: dict[str, Any]) -> tuple[Any, ...]:
    return (
        row.get("dedup_status") != "canonical_candidate",
        str(row.get("source_root_id") or row.get("parent_source_root_id") or ""),
        tuple(row.get("operator_ids") or []),
        str(row.get("source_authority_key") or ""),
        str(row.get("candidate_id") or ""),
    )


def select_candidate_batch(
    candidates: list[dict[str, Any]], *, target_count: int
) -> list[dict[str, Any]]:
    if target_count <= 0:
        raise ValueError("target_count must be positive")
    lanes: dict[str, deque[dict[str, Any]]] = {}
    for lane, rows in sorted(
        ((lane, values) for lane, values in _group_by(candidates, "candidate_lane").items())
    ):
        lanes[lane] = deque(sorted(rows, key=_selection_key))
    selected: list[dict[str, Any]] = []
    while lanes and len(selected) < min(target_count, len(candidates)):
        for lane in list(lanes):
            selected.append(lanes[lane].popleft())
            if not lanes[lane]:
                del lanes[lane]
            if len(selected) >= min(target_count, len(candidates)):
                break
    return selected


def _group_by(rows: Iterable[dict[str, Any]], field: str) -> dict[str, list[dict[str, Any]]]:
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        groups[str(row.get(field) or "")].append(row)
    return groups


def _rule_signature(row: dict[str, Any]) -> str:
    payload = [str(row.get(field) or "") for field in RULE_SIGNATURE_FIELDS]
    return hashlib.sha256(
        json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def _source_components(
    candidates: list[dict[str, Any]],
) -> dict[str, list[dict[str, Any]]]:
    parent: dict[str, str] = {}

    def find(node: str) -> str:
        parent.setdefault(node, node)
        while parent[node] != node:
            parent[node] = parent[parent[node]]
            node = parent[node]
        return node

    def union(left: str, right: str) -> None:
        left_root = find(left)
        right_root = find(right)
        if left_root != right_root:
            parent[max(left_root, right_root)] = min(left_root, right_root)

    nodes: list[tuple[str, dict[str, Any]]] = []
    for row in candidates:
        source_sha = str(row.get("source_sha256") or "")
        authority = str(row.get("source_authority_key") or "")
        if not source_sha or not authority:
            raise ValueError("review candidate is missing source SHA or authority")
        sha_node = f"sha:{source_sha}"
        authority_node = f"authority:{authority}"
        union(sha_node, authority_node)
        nodes.append((sha_node, row))

    components: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for node, row in nodes:
        components[find(node)].append(row)
    return dict(components)


def _seeded_digest(seed: int, *values: str) -> bytes:
    return hashlib.sha256(
        "\x1f".join((str(seed), *values)).encode("utf-8")
    ).digest()


def build_source_disjoint_review_packet(
    candidates: list[dict[str, Any]], *, per_split: int, review_seed: int = 0
) -> list[dict[str, Any]]:
    if per_split <= 0:
        raise ValueError("per_split must be positive")
    components = _source_components(candidates)
    component_splits = {"calibration": [], "holdout": []}
    for component in sorted(components):
        split = (
            "calibration"
            if _seeded_digest(review_seed, component)[0] % 2 == 0
            else "holdout"
        )
        component_splits[split].append(component)
    effective_per_split = min(
        per_split,
        len(component_splits["calibration"]),
        len(component_splits["holdout"]),
    )
    if effective_per_split == 0:
        raise ValueError("both source-disjoint hash buckets require a source component")
    chosen = {"calibration": [], "holdout": []}
    for split, split_components in component_splits.items():
        strata: dict[tuple[str, str, str], list[tuple[str, dict[str, Any]]]] = defaultdict(list)
        for component in split_components:
            for row in components[component]:
                stratum = (
                    str(row.get("candidate_lane") or ""),
                    str(row.get("dedup_status") or ""),
                    _rule_signature(row),
                )
                strata[stratum].append((component, row))
        for stratum in strata:
            strata[stratum].sort(
                key=lambda item: _seeded_digest(
                    review_seed,
                    str(item[1].get("candidate_id") or ""),
                    item[0],
                )
            )
        selected_components: set[str] = set()
        ordered_strata = sorted(
            strata, key=lambda value: _seeded_digest(review_seed, *value)
        )
        while len(chosen[split]) < effective_per_split:
            progressed = False
            for stratum in ordered_strata:
                while strata[stratum] and strata[stratum][0][0] in selected_components:
                    strata[stratum].pop(0)
                if not strata[stratum]:
                    continue
                component, source = strata[stratum].pop(0)
                selected_components.add(component)
                row = dict(source)
                row["review_rule_signature"] = _rule_signature(row)
                row["review_seed"] = review_seed
                row["review_source_component"] = component
                row["review_split"] = split
                row["human_boundary_decision"] = ""
                row["human_operator_decision"] = ""
                row["human_description_decision"] = ""
                row["human_notes"] = ""
                chosen[split].append(row)
                progressed = True
                if len(chosen[split]) >= effective_per_split:
                    break
            if not progressed:
                break
    packet = [*chosen["calibration"], *chosen["holdout"]]
    calibration = [row for row in packet if row["review_split"] == "calibration"]
    holdout = [row for row in packet if row["review_split"] == "holdout"]
    for field in ("source_sha256", "source_authority_key"):
        if {row[field] for row in calibration} & {row[field] for row in holdout}:
            raise ValueError(f"source-disjoint review overlap: {field}")
    return packet


def recover_operator_rows(
    rows: list[dict[str, Any]], catalog_ids: set[str], mapping: dict[str, str]
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    recovered: list[dict[str, Any]] = []
    for source in rows:
        if source.get("action") != "defer_operator_resolution":
            continue
        census = {
            **source,
            "content_sha256": source["source_sha256"],
            "primary_layer": "explicit_processing_catalog_miss",
            "screening_literal_operator_ids": source.get("original_operator_ids") or [],
        }
        row = recover_row(census, catalog_ids)
        recovered.append(
            apply_l3_gate(
                row,
                mapping,
                mapping_authority=MAPPING_AUTHORITY,
            )
        )
    summary = summarize_operator_rows(recovered)
    return recovered, summary


def summarize_operator_rows(rows: list[dict[str, Any]]) -> dict[str, Any]:
    fully = [row for row in rows if row.get("normalization_status") == "fully_normalized"]
    partial = [row for row in rows if row.get("normalization_status") == "partially_normalized"]
    return {
        "input_rows": len(rows),
        "normalization_status_counts": dict(Counter(row.get("normalization_status") for row in rows)),
        "action_counts": dict(Counter(row.get("action") for row in rows)),
        "fully_normalized_rows": len(fully),
        "fully_normalized_mapping_complete_rows": sum(
            bool(row.get("mapping_complete")) for row in fully
        ),
        "partially_normalized_rows": len(partial),
        "partially_normalized_mapped_subset_rows": sum(
            bool(row.get("mapping_complete")) for row in partial
        ),
        "training_rows_emitted": 0,
    }


def _source_snippet(row: dict[str, Any], context: int = 2) -> str:
    path = Path(str(row.get("source_path") or ""))
    sites = list(row.get("call_sites") or [])
    if not path.is_file() or not sites:
        return ""
    lines = path.read_text(encoding="utf-8-sig", errors="replace").splitlines()
    chunks = []
    for site in sites:
        start = max(1, int(site["line_start"]) - context)
        end = min(len(lines), int(site["line_end"]) + context)
        chunks.append("\n".join(f"{n} | {lines[n - 1]}" for n in range(start, end + 1)))
    return "\n...\n".join(chunks)


def _atomic_write(path: Path, text: str, *, encoding: str = "utf-8") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "w", encoding=encoding, newline="", dir=path.parent, delete=False
    ) as handle:
        handle.write(text)
        temporary = Path(handle.name)
    temporary.replace(path)


def _write_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> None:
    _atomic_write(
        path,
        "".join(
            json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
            + "\n"
            for row in rows
        ),
    )


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        _atomic_write(path, "", encoding="utf-8-sig")
        return
    fields = sorted(set().union(*(row.keys() for row in rows)))
    buffer = io.StringIO(newline="")
    writer = csv.DictWriter(buffer, fieldnames=fields, extrasaction="ignore")
    writer.writeheader()
    for row in rows:
        writer.writerow(
            {
                key: json.dumps(value, ensure_ascii=False, sort_keys=True)
                if isinstance(value, (list, dict))
                else value
                for key, value in row.items()
            }
        )
    _atomic_write(path, buffer.getvalue(), encoding="utf-8-sig")


def write_outputs(
    *,
    output_dir: Path,
    source_rows: list[dict[str, Any]],
    source_failures: list[dict[str, Any]],
    direct_rows: list[dict[str, Any]],
    direct_failures: list[dict[str, Any]],
    recovery_rows: list[dict[str, Any]],
    recovery_summary: dict[str, Any],
    split_rows: list[dict[str, Any]],
    split_summary: dict[str, Any],
    operator_rows: list[dict[str, Any]],
    operator_description_rows: list[dict[str, Any]],
    operator_summary: dict[str, Any],
    operator_recovery_rows: list[dict[str, Any]],
    operator_split_rows: list[dict[str, Any]],
    candidates: list[dict[str, Any]],
    selected: list[dict[str, Any]],
    review: list[dict[str, Any]],
    inputs: list[Path],
) -> dict[str, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    artifacts = {
        "source_replay": output_dir / "blocker_source_replay_v1.jsonl",
        "direct_replay": output_dir / "direct_source_replay_v1.jsonl",
        "recovery": output_dir / "recovery_candidates_v1.jsonl",
        "split": output_dir / "split_candidates_v1.jsonl",
        "operator": output_dir / "operator_resolution_v1.jsonl",
        "operator_descriptions": output_dir / "operator_direct_descriptions_v1.jsonl",
        "operator_recovery": output_dir / "operator_recovery_candidates_v1.jsonl",
        "operator_split": output_dir / "operator_split_candidates_v1.jsonl",
        "pool": output_dir / "candidate_pool_v1.jsonl",
        "selected": output_dir / "candidate_batch_v1.jsonl",
        "review_jsonl": output_dir / "source_disjoint_review_v1.jsonl",
        "review_csv": output_dir / "source_disjoint_review_v1.csv",
        "summary": output_dir / "summary_v1.json",
        "hashes": output_dir / "hash_ledger_v1.json",
    }
    for key, rows in (
        ("source_replay", source_rows),
        ("direct_replay", direct_rows),
        ("recovery", recovery_rows),
        ("split", split_rows),
        ("operator", operator_rows),
        ("operator_descriptions", operator_description_rows),
        ("operator_recovery", operator_recovery_rows),
        ("operator_split", operator_split_rows),
        ("pool", candidates),
        ("selected", selected),
        ("review_jsonl", review),
    ):
        _write_jsonl(artifacts[key], rows)
    _write_csv(artifacts["review_csv"], review)
    calibration_review = [
        row for row in review if row.get("review_split") == "calibration"
    ]
    holdout_review = [row for row in review if row.get("review_split") == "holdout"]
    source_sha_overlap = {
        row.get("source_sha256") for row in calibration_review
    } & {row.get("source_sha256") for row in holdout_review}
    source_authority_overlap = {
        row.get("source_authority_key") for row in calibration_review
    } & {row.get("source_authority_key") for row in holdout_review}
    summary = {
        "schema": f"{SCHEMA}.summary",
        "policy_version": POLICY_VERSION,
        "blocker_rows": len(source_rows) + len(source_failures),
        "source_verified_rows": len(source_rows),
        "source_failure_rows": len(source_failures),
        "blocker_action_counts": dict(Counter(row["action"] for row in source_rows)),
        "source_path_resolution_counts": dict(
            Counter(row["source_path_resolution"] for row in source_rows)
        ),
        "direct_replay_rows": len(direct_rows),
        "direct_source_failures": len(direct_failures),
        "direct_description_fidelity_passed": sum(
            row.get("description_fidelity_passed") is True for row in direct_rows
        ),
        "direct_parameter_evidence_status_counts": dict(
            Counter(row.get("parameter_evidence_status") for row in direct_rows)
        ),
        "direct_dedup_status_counts": dict(
            Counter(row.get("dedup_status") for row in direct_rows)
        ),
        "recovery_summary": recovery_summary,
        "split_summary": split_summary,
        "operator_summary": operator_summary,
        "candidate_pool_rows": len(candidates),
        "candidate_lane_counts": dict(Counter(row["candidate_lane"] for row in candidates)),
        "dedup_status_counts": dict(Counter(row["dedup_status"] for row in candidates)),
        "selected_candidate_rows": len(selected),
        "selected_candidate_lane_counts": dict(
            Counter(row["candidate_lane"] for row in selected)
        ),
        "selected_dedup_status_counts": dict(
            Counter(row["dedup_status"] for row in selected)
        ),
        "selected_source_authorities": len(
            {row.get("source_authority_key") for row in selected}
        ),
        "candidate_rule_signature_counts": dict(
            Counter(_rule_signature(row) for row in candidates)
        ),
        "review_rows": len(review),
        "review_split_counts": dict(Counter(row["review_split"] for row in review)),
        "review_rule_signature_counts": dict(
            Counter(
                str(row.get("review_rule_signature") or _rule_signature(row))
                for row in review
            )
        ),
        "review_seed": next(
            (row.get("review_seed") for row in review if "review_seed" in row), None
        ),
        "review_source_sha_zero_overlap": not source_sha_overlap,
        "review_source_authority_zero_overlap": not source_authority_overlap,
        "review_source_disjoint_zero_overlap": not source_authority_overlap,
        "quality_gate": {
            "source_authority_failures": len(source_failures),
            "uncertain_training_rows": 0,
            "training_rows_emitted": 0,
            "validation_test_rows": 0,
            "llm_called": False,
        },
        "training_admission": "not_granted_pending_source_disjoint_review",
        "training_rows_emitted": 0,
        "production_merge": "not_granted",
    }
    _atomic_write(
        artifacts["summary"],
        json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
    )
    hash_ledger = {
        "schema": "gis_recommend.hash_ledger.v1",
        "source_inputs": {
            path.name: {"path": str(path), "sha256": _sha256(path)} for path in inputs
        },
        "artifacts": {
            path.name: {
                "path": str(path),
                "sha256": _sha256(path),
                "bytes": path.stat().st_size,
            }
            for key, path in artifacts.items()
            if key != "hashes"
        },
    }
    _atomic_write(
        artifacts["hashes"],
        json.dumps(hash_ledger, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
    )
    return artifacts


def _parse_prefix_aliases(values: list[str]) -> list[tuple[str, str]]:
    aliases = []
    for value in values:
        old, separator, new = value.partition("=")
        if not separator or not old or not new:
            raise ValueError(f"invalid source prefix alias: {value!r}")
        aliases.append((old, new))
    return aliases


def validate_input_paths(paths: Iterable[Path]) -> None:
    missing = [str(path) for path in paths if not path.is_file()]
    if missing:
        raise ValueError(f"missing required input: {missing}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--latest-replay", type=Path, default=DEFAULT_LATEST_REPLAY)
    parser.add_argument("--previous-replay", type=Path)
    parser.add_argument("--unified-ledger", type=Path, default=DEFAULT_UNIFIED_LEDGER)
    parser.add_argument("--train-authority", type=Path, default=DEFAULT_TRAIN_AUTHORITY)
    parser.add_argument("--catalog", type=Path, required=True)
    parser.add_argument("--composed-mapping", type=Path)
    parser.add_argument("--mapping-authority", default=MAPPING_AUTHORITY)
    parser.add_argument("--crosswalk", type=Path, default=DEFAULT_CROSSWALK)
    parser.add_argument("--stable98-delta", type=Path, default=DEFAULT_STABLE98)
    parser.add_argument("--stable101-delta", type=Path, default=DEFAULT_STABLE101)
    parser.add_argument(
        "--additional-delta", type=Path, action="append", default=None
    )
    parser.add_argument("--source-prefix-alias", action="append", default=[])
    parser.add_argument("--direct-record-id", action="append", default=None)
    parser.add_argument(
        "--include-action",
        action="append",
        choices=sorted(BLOCKER_ACTIONS | {"defer_mapping"}),
        default=None,
        help="Add a routing action to the blocker replay set; defaults to the historical three blocker actions.",
    )
    parser.add_argument(
        "--selection-scope",
        choices=("ledger", "current-actions"),
        default="ledger",
        help="Select blockers from the historical ledger or directly from current replay actions.",
    )
    parser.add_argument("--include-all-direct", action="store_true")
    parser.add_argument("--target-count", type=int, default=250)
    parser.add_argument("--review-per-split", type=int, default=50)
    parser.add_argument("--review-seed", type=int, default=0)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args(argv)

    delta_paths = args.additional_delta or DEFAULT_ADDITIONAL_DELTAS
    inputs = [
        args.latest_replay,
        args.unified_ledger,
        args.train_authority,
        args.catalog,
    ]
    if not args.composed_mapping:
        inputs.extend(
            [
                args.crosswalk,
                args.stable98_delta,
                args.stable101_delta,
                *delta_paths,
            ]
        )
    if args.previous_replay:
        inputs.append(args.previous_replay)
    if args.composed_mapping:
        inputs.append(args.composed_mapping)
    validate_input_paths(inputs)
    train_rows = _read_jsonl(args.train_authority)
    catalog_ids = load_catalog_ids(args.catalog)
    mapping = (
        load_explicit_mapping_authority(args.composed_mapping)
        if args.composed_mapping
        else load_composed_mapping(
            args.crosswalk,
            args.stable98_delta,
            args.stable101_delta,
            additional_delta_paths=delta_paths,
        )
    )
    latest = _read_jsonl(args.latest_replay)
    unified = _read_jsonl(args.unified_ledger)
    actions = set(BLOCKER_ACTIONS)
    actions.update(args.include_action or [])
    if args.selection_scope == "current-actions":
        if args.previous_replay:
            raise ValueError(
                "--previous-replay cannot be combined with --selection-scope current-actions"
            )
        blockers = select_current_action_rows(latest, actions=actions)
    elif args.previous_replay:
        blockers = [
            dict(row) for row in latest if str(row.get("action")) in actions
        ]
        blockers = select_action_transitions(
            blockers, _read_jsonl(args.previous_replay)
        )
    else:
        blockers = select_blocker_rows(latest, unified, actions=actions)
    aliases = _parse_prefix_aliases(args.source_prefix_alias)
    resolved, failures = resolve_source_rows(
        blockers, aliases
    )
    resolved = enrich_source_authority(resolved)
    currently_mapped = [
        apply_l3_gate(row, mapping, mapping_authority=args.mapping_authority)
        for row in resolved
    ]
    direct_sources = select_direct_rows(
        latest,
        args.direct_record_id or ([] if args.include_all_direct else DEFAULT_DIRECT_RECORD_IDS),
        include_all=args.include_all_direct,
    )
    direct_sources, direct_failures = resolve_source_rows(direct_sources, aliases)
    direct_descriptions, _ = build_candidates(direct_sources)
    direct_descriptions = annotate_dedup(
        enrich_source_authority(direct_descriptions),
        train_rows,
    )

    recovery_rows, recovery_summary = build_recovery_units(currently_mapped)
    split_rows, split_summary = build_split_units(currently_mapped)
    operator_rows, operator_summary = recover_operator_rows(
        resolved, catalog_ids, mapping
    )
    operator_descriptions, description_summary = build_candidates(operator_rows)
    operator_summary["description_summary"] = description_summary
    operator_recovery_rows, operator_recovery_summary = build_recovery_units(
        operator_rows
    )
    operator_split_rows, operator_split_summary = build_split_units(operator_rows)
    operator_summary["recovery_summary"] = operator_recovery_summary
    operator_summary["split_summary"] = operator_split_summary

    recovery_rows = enrich_source_authority(recovery_rows)
    split_rows = enrich_source_authority(split_rows)
    operator_descriptions = enrich_source_authority(operator_descriptions)
    operator_recovery_rows = enrich_source_authority(operator_recovery_rows)
    operator_split_rows = enrich_source_authority(operator_split_rows)
    for row in [
        *recovery_rows,
        *split_rows,
        *operator_descriptions,
        *operator_recovery_rows,
        *operator_split_rows,
    ]:
        row.setdefault("source_snippet", _source_snippet(row))
    candidates = build_candidate_pool(
        recovery_rows,
        split_rows,
        operator_descriptions,
        direct_rows=direct_descriptions,
        operator_recovery_rows=operator_recovery_rows,
        operator_split_rows=operator_split_rows,
    )
    candidates = annotate_dedup(candidates, train_rows)
    selected = select_candidate_batch(candidates, target_count=args.target_count)
    review = build_source_disjoint_review_packet(
        selected,
        per_split=args.review_per_split,
        review_seed=args.review_seed,
    )
    write_outputs(
        output_dir=args.output_dir,
        source_rows=resolved,
        source_failures=failures,
        direct_rows=direct_descriptions,
        direct_failures=direct_failures,
        recovery_rows=recovery_rows,
        recovery_summary=recovery_summary,
        split_rows=split_rows,
        split_summary=split_summary,
        operator_rows=operator_rows,
        operator_description_rows=operator_descriptions,
        operator_summary=operator_summary,
        operator_recovery_rows=operator_recovery_rows,
        operator_split_rows=operator_split_rows,
        candidates=candidates,
        selected=selected,
        review=review,
        inputs=inputs,
    )
    print(json.dumps({"candidate_rows": len(candidates), "selected_rows": len(selected)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
