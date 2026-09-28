#!/usr/bin/env python3
"""Rank unresolved QGIS API upstream families by normalized source authority."""

from __future__ import annotations

import argparse
import hashlib
import json
import tempfile
from collections import Counter, defaultdict
from itertools import combinations
from pathlib import Path
from typing import Any, Iterable, Mapping


STATIC_QGIS_ROOTS = {
    "qgsfeature",
    "qgsgeometry",
    "qgspoint",
    "qgspointxy",
    "qgsrectangle",
}
KNOWN_TRAINING_SEMANTICS = {
    "buffer",
    "centroid",
    "convexhull",
    "intersection",
    "simplify",
}
SUPPORT_ONLY_CALLS = {
    "addfeature",
    "constgeometry",
    "geometry",
    "qgsfeature",
    "qgsgeometry",
    "qgspoint",
    "qgspointxy",
    "qgsrectangle",
    "setattributes",
    "setgeometry",
    "write",
}
RULE_ID = "receiver-independent-upstream-family-v1"
ANCHOR_RULE_ID = "source-visible-upstream-semantic-anchor-v1"
DISCOVERY_RULE_ID = "authority-call-cooccurrence-discovery-v2"


def normalize_call_name(call_name: str) -> str:
    normalized = call_name.strip().lower()
    root = normalized.split(".", 1)[0]
    if root in STATIC_QGIS_ROOTS:
        return normalized
    return normalized.rsplit(".", 1)[-1]


def reviewed_candidate_ids(rows: Iterable[dict[str, Any]]) -> set[str]:
    identities = set()
    for row in rows:
        identity = str(
            row.get("baseline_candidate_id") or row.get("candidate_id") or ""
        )
        if not identity:
            raise ValueError("reviewed row lacks candidate identity")
        identities.add(identity)
    return identities


def build_reviewed_exclusion_provenance(
    reviewed_sources: Iterable[tuple[str, Iterable[dict[str, Any]]]],
) -> dict[str, list[str]]:
    provenance: dict[str, set[str]] = defaultdict(set)
    for source_label, rows in reviewed_sources:
        if not source_label:
            raise ValueError("reviewed source label must not be empty")
        for identity in reviewed_candidate_ids(rows):
            provenance[identity].add(source_label)
    return {
        identity: sorted(source_labels)
        for identity, source_labels in sorted(provenance.items())
    }


def _calls(row: dict[str, Any]) -> list[str]:
    upstream_calls = row.get("upstream_calls") or []
    if upstream_calls:
        return [str(call.get("call_name") or "") for call in upstream_calls]
    return [str(call) for call in row.get("upstream_signature") or []]


def _has_factory(signature: tuple[str, ...], prefix: str) -> bool:
    return any(call.startswith(prefix) for call in signature)


def _anchor_families(signature: tuple[str, ...]) -> list[str]:
    calls = set(signature)
    anchors = []
    if (
        "random" in calls
        and calls.intersection({"boundingbox", "sourceextent"})
        and _has_factory(signature, "qgsgeometry.frompoint")
    ):
        anchors.append("random_point_construction")
    if {"cos", "sin"}.issubset(calls) and _has_factory(
        signature, "qgsgeometry.frompolygon"
    ):
        anchors.append("trigonometric_polygon_construction")
    if "qgsgeometry.unaryunion" in calls:
        anchors.append("unary_union")
    if {"boundingbox", "center"}.issubset(calls) and _has_factory(
        signature, "qgsgeometry.frompoint"
    ):
        anchors.append("bounding_box_center_point")
    if "densifygeometry" in calls:
        anchors.append("densify_geometry")
    if "nearestneighbor" in calls and _has_factory(
        signature, "qgsgeometry.frompolyline"
    ):
        anchors.append("nearest_neighbor_line")
    if "difference" in calls:
        anchors.append("geometry_difference")
    if "coordinatetransform" in calls and _has_factory(
        signature, "qgsgeometry.frompoint"
    ):
        anchors.append("coordinate_transform_point")
    return anchors


def _review_priority(signature: tuple[str, ...], support: int, minimum: int) -> str:
    if not signature:
        return "defer_empty_signature"
    if any(call.rsplit(".", 1)[-1] in KNOWN_TRAINING_SEMANTICS for call in signature):
        return "defer_known_training_semantic_overlap"
    if all(
        call in SUPPORT_ONLY_CALLS or call.startswith("qgsgeometry.from")
        for call in signature
    ):
        return "defer_support_only_signature"
    if support < minimum:
        return "defer_support_below_threshold"
    return "calibration_required"


def build_family_census(
    rows: list[dict[str, Any]],
    *,
    excluded_candidate_ids: set[str],
    excluded_candidate_provenance: Mapping[str, list[str]] | None = None,
    minimum_authority_support: int,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    if minimum_authority_support < 1:
        raise ValueError("minimum authority support must be positive")

    remaining = []
    excluded = []
    for row in rows:
        if row.get("training_row_emitted") is not False:
            raise ValueError("upstream census input must emit zero training rows")
        if str(row.get("candidate_id") or "") in excluded_candidate_ids:
            candidate_id = str(row.get("candidate_id") or "")
            excluded.append(
                {
                    **row,
                    "schema": "gis_recommend.qgis_api_upstream_family_exclusion.v1",
                    "family_rule_id": RULE_ID,
                    "family_exclusion_reason": "previously_reviewed_family",
                    "reviewed_family_provenance": list(
                        (excluded_candidate_provenance or {}).get(
                            candidate_id, ["unspecified_reviewed_manifest"]
                        )
                    ),
                    "training_row_emitted": False,
                }
            )
        else:
            remaining.append(row)

    resolved = [
        row
        for row in remaining
        if row.get("slice_status") == "resolved_local_call_chain"
    ]
    grouped: dict[tuple[str, ...], list[dict[str, Any]]] = defaultdict(list)
    for row in resolved:
        signature = tuple(normalize_call_name(call) for call in _calls(row) if call)
        grouped[signature].append(row)

    families = []
    for signature, members in grouped.items():
        authorities = sorted(
            {str(member["source_authority_key"]) for member in members}
        )
        original_signatures = sorted(
            {tuple(str(call) for call in member.get("upstream_signature") or []) for member in members}
        )
        priority = _review_priority(
            signature, len(authorities), minimum_authority_support
        )
        families.append(
            {
                "schema": "gis_recommend.qgis_api_upstream_family_census.v1",
                "family_rule_id": RULE_ID,
                "normalized_signature": list(signature),
                "unit_count": len(members),
                "source_authority_count": len(authorities),
                "source_authority_keys": authorities,
                "original_signature_count": len(original_signatures),
                "example_candidate_ids": sorted(
                    str(member["candidate_id"]) for member in members
                )[:5],
                "review_priority": priority,
                "mapping_admission": "not_granted_family_census_only",
                "training_admission": "not_granted_family_census_only",
                "training_row_emitted": False,
            }
        )
    families.sort(
        key=lambda row: (
            -int(row["source_authority_count"]),
            -int(row["unit_count"]),
            tuple(row["normalized_signature"]),
        )
    )
    priorities = [
        row for row in families if row["review_priority"] == "calibration_required"
    ]
    status_counts = Counter(str(row["slice_status"]) for row in remaining)
    priority_units = sum(int(row["unit_count"]) for row in priorities)
    summary = {
        "schema": "gis_recommend.qgis_api_upstream_family_census_summary.v1",
        "family_rule_id": RULE_ID,
        "input_units": len(rows),
        "excluded_previously_reviewed_units": len(excluded),
        "remaining_units": len(remaining),
        "remaining_slice_status_counts": dict(sorted(status_counts.items())),
        "resolved_units": len(resolved),
        "family_count": len(families),
        "minimum_source_authority_support": minimum_authority_support,
        "priority_family_count": len(priorities),
        "priority_family_units": priority_units,
        "priority_family_source_authorities": len(
            {
                authority
                for family in priorities
                for authority in family["source_authority_keys"]
            }
        ),
        "mapping_rows_emitted": 0,
        "description_fidelity_rows": 0,
        "training_rows_emitted": 0,
        "training_admission": "not_granted_family_census_only",
    }
    return families, priorities, excluded, summary


def _normalized_unique_calls(row: dict[str, Any]) -> tuple[str, ...]:
    return tuple(sorted({normalize_call_name(call) for call in _calls(row) if call}))


def _discovery_priority(
    calls: tuple[str, ...], support: int, minimum: int
) -> str:
    if support < minimum:
        return "defer_support_below_threshold"
    if any(call.rsplit(".", 1)[-1] in KNOWN_TRAINING_SEMANTICS for call in calls):
        return "defer_known_training_semantic_overlap"
    if all(
        call in SUPPORT_ONLY_CALLS or call.startswith("qgsgeometry.from")
        for call in calls
    ):
        return "defer_support_only_cooccurrence"
    return "calibration_required"


def _discovery_row(
    *,
    schema: str,
    calls: tuple[str, ...],
    members: list[dict[str, Any]],
    minimum_authority_support: int,
) -> dict[str, Any]:
    authorities = sorted({str(row["source_authority_key"]) for row in members})
    row = {
        "schema": schema,
        "discovery_rule_id": DISCOVERY_RULE_ID,
        "unit_count": len(members),
        "source_authority_count": len(authorities),
        "source_authority_keys": authorities,
        "example_candidate_ids": sorted(
            {str(member["candidate_id"]) for member in members}
        )[:10],
        "minimum_source_authority_support": minimum_authority_support,
        "mapping_admission": "not_granted_discovery_only",
        "description_fidelity": "not_started",
        "training_admission": "not_granted_discovery_only",
        "training_row_emitted": False,
    }
    if len(calls) == 1:
        row.update(
            {
                "normalized_call": calls[0],
                "review_priority": "defer_single_call_not_task_boundary",
                "support_gate_passed": len(authorities)
                >= minimum_authority_support,
            }
        )
    else:
        row.update(
            {
                "normalized_call_cooccurrence": list(calls),
                "review_priority": _discovery_priority(
                    calls, len(authorities), minimum_authority_support
                ),
                "task_boundary_status": "not_reviewed_discovery_anchor_only",
            }
        )
    return row


def build_discovery_census(
    rows: list[dict[str, Any]],
    *,
    excluded_candidate_ids: set[str],
    minimum_authority_support: int,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    if minimum_authority_support < 1:
        raise ValueError("minimum authority support must be positive")
    remaining = []
    for row in rows:
        if row.get("training_row_emitted") is not False:
            raise ValueError("discovery census input must emit zero training rows")
        if str(row.get("candidate_id") or "") not in excluded_candidate_ids:
            remaining.append(row)
    resolved = [
        row for row in remaining if row.get("slice_status") == "resolved_local_call_chain"
    ]
    call_groups: dict[tuple[str, ...], list[dict[str, Any]]] = defaultdict(list)
    pair_groups: dict[tuple[str, ...], list[dict[str, Any]]] = defaultdict(list)
    for row in resolved:
        calls = _normalized_unique_calls(row)
        for call in calls:
            call_groups[(call,)].append(row)
        for pair in combinations(calls, 2):
            pair_groups[pair].append(row)

    calls = [
        _discovery_row(
            schema="gis_recommend.qgis_api_upstream_call_census.v2",
            calls=call,
            members=members,
            minimum_authority_support=minimum_authority_support,
        )
        for call, members in call_groups.items()
    ]
    pairs = [
        _discovery_row(
            schema="gis_recommend.qgis_api_upstream_call_cooccurrence_census.v2",
            calls=pair,
            members=members,
            minimum_authority_support=minimum_authority_support,
        )
        for pair, members in pair_groups.items()
    ]
    calls.sort(
        key=lambda row: (
            -int(row["source_authority_count"]),
            -int(row["unit_count"]),
            str(row["normalized_call"]),
        )
    )
    pairs.sort(
        key=lambda row: (
            -int(row["source_authority_count"]),
            -int(row["unit_count"]),
            tuple(row["normalized_call_cooccurrence"]),
        )
    )
    priority_pairs = [
        row for row in pairs if row["review_priority"] == "calibration_required"
    ]
    summary = {
        "schema": "gis_recommend.qgis_api_upstream_discovery_census_summary.v2",
        "discovery_rule_id": DISCOVERY_RULE_ID,
        "input_units": len(rows),
        "excluded_reviewed_units": len(rows) - len(remaining),
        "remaining_units": len(remaining),
        "resolved_units": len(resolved),
        "single_call_count": len(calls),
        "high_support_single_call_count": sum(
            1 for row in calls if row["support_gate_passed"]
        ),
        "cooccurrence_count": len(pairs),
        "priority_cooccurrence_count": len(priority_pairs),
        "priority_cooccurrence_units": sum(
            int(row["unit_count"]) for row in priority_pairs
        ),
        "minimum_source_authority_support": minimum_authority_support,
        "mapping_rows_emitted": 0,
        "description_fidelity_rows": 0,
        "training_rows_emitted": 0,
        "training_admission": "not_granted_discovery_census_only",
    }
    return calls, pairs, summary


def build_anchor_census(
    rows: list[dict[str, Any]],
    *,
    excluded_candidate_ids: set[str],
    minimum_authority_support: int,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        if str(row.get("candidate_id") or "") in excluded_candidate_ids:
            continue
        if row.get("slice_status") != "resolved_local_call_chain":
            continue
        signature = tuple(normalize_call_name(call) for call in _calls(row) if call)
        for anchor in _anchor_families(signature):
            grouped[anchor].append(row)

    anchors = []
    for anchor, members in grouped.items():
        authorities = sorted(
            {str(member["source_authority_key"]) for member in members}
        )
        support = len(authorities)
        anchors.append(
            {
                "schema": "gis_recommend.qgis_api_upstream_semantic_anchor_census.v1",
                "anchor_rule_id": ANCHOR_RULE_ID,
                "anchor_family": anchor,
                "unit_count": len(members),
                "source_authority_count": support,
                "source_authority_keys": authorities,
                "example_candidate_ids": sorted(
                    str(member["candidate_id"]) for member in members
                )[:10],
                "review_priority": (
                    "calibration_required"
                    if support >= minimum_authority_support
                    else "defer_support_below_threshold"
                ),
                "mapping_admission": "not_granted_anchor_census_only",
                "training_admission": "not_granted_anchor_census_only",
                "training_row_emitted": False,
            }
        )
    anchors.sort(
        key=lambda row: (
            -int(row["source_authority_count"]),
            -int(row["unit_count"]),
            str(row["anchor_family"]),
        )
    )
    priorities = [
        row for row in anchors if row["review_priority"] == "calibration_required"
    ]
    summary = {
        "schema": "gis_recommend.qgis_api_upstream_semantic_anchor_summary.v1",
        "anchor_rule_id": ANCHOR_RULE_ID,
        "anchor_family_count": len(anchors),
        "priority_anchor_family_count": len(priorities),
        "priority_anchor_units": sum(int(row["unit_count"]) for row in priorities),
        "minimum_source_authority_support": minimum_authority_support,
        "mapping_rows_emitted": 0,
        "description_fidelity_rows": 0,
        "training_rows_emitted": 0,
        "training_admission": "not_granted_anchor_census_only",
    }
    return anchors, priorities, summary


def build_anchor_candidate_units(
    rows: list[dict[str, Any]],
    *,
    excluded_candidate_ids: set[str],
    priority_anchor_families: set[str],
) -> list[dict[str, Any]]:
    candidates = []
    for row in rows:
        if str(row.get("candidate_id") or "") in excluded_candidate_ids:
            continue
        if row.get("slice_status") != "resolved_local_call_chain":
            continue
        signature = tuple(normalize_call_name(call) for call in _calls(row) if call)
        anchors = sorted(
            set(_anchor_families(signature)).intersection(priority_anchor_families)
        )
        if not anchors:
            continue
        candidates.append(
            {
                **row,
                "schema": "gis_recommend.qgis_api_upstream_anchor_candidate.v1",
                "anchor_rule_id": ANCHOR_RULE_ID,
                "semantic_anchor_families": anchors,
                "review_status": "pending_source_disjoint_boundary_review",
                "candidate_l3_sequence": [],
                "mapping_admission": "not_granted_anchor_candidate_only",
                "description_fidelity": "not_started",
                "deduplication": "not_started",
                "training_admission": "not_granted_anchor_candidate_only",
                "training_row_emitted": False,
                "validation_eligible": False,
                "test_eligible": False,
                "production_merge": "not_granted",
            }
        )
    candidates.sort(
        key=lambda row: (
            tuple(row["semantic_anchor_families"]),
            str(row["source_authority_key"]),
            str(row["candidate_id"]),
        )
    )
    return candidates


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    with path.open(encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _atomic_write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "w", encoding="utf-8", newline="", dir=path.parent, delete=False
    ) as handle:
        handle.write(content)
        temporary = Path(handle.name)
    temporary.replace(path)


def _write_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> None:
    _atomic_write(
        path,
        "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows),
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mutation-upstream", type=Path, required=True)
    parser.add_argument("--exclude-reviewed", type=Path, action="append", default=[])
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--minimum-authority-support", type=int, default=30)
    parser.add_argument("--expected-rows", type=int, default=2605)
    parser.add_argument("--expected-excluded", type=int, default=85)
    args = parser.parse_args()
    if args.output_dir.exists() and any(args.output_dir.iterdir()):
        raise ValueError(f"output directory is not empty: {args.output_dir}")

    rows = _read_jsonl(args.mutation_upstream)
    if len(rows) != args.expected_rows:
        raise ValueError(f"input rows {len(rows)} != expected {args.expected_rows}")
    reviewed_sources = [
        (
            f"{path.parent.name}/{path.name}",
            _read_jsonl(path),
        )
        for path in args.exclude_reviewed
    ]
    exclusion_provenance = build_reviewed_exclusion_provenance(reviewed_sources)
    exclusions = set(exclusion_provenance)
    families, priorities, excluded, summary = build_family_census(
        rows,
        excluded_candidate_ids=exclusions,
        excluded_candidate_provenance=exclusion_provenance,
        minimum_authority_support=args.minimum_authority_support,
    )
    discovery_calls, discovery_pairs, discovery_summary = build_discovery_census(
        rows,
        excluded_candidate_ids=exclusions,
        minimum_authority_support=args.minimum_authority_support,
    )
    anchors, priority_anchors, anchor_summary = build_anchor_census(
        rows,
        excluded_candidate_ids=exclusions,
        minimum_authority_support=args.minimum_authority_support,
    )
    anchor_candidates = build_anchor_candidate_units(
        rows,
        excluded_candidate_ids=exclusions,
        priority_anchor_families={
            str(row["anchor_family"]) for row in priority_anchors
        },
    )
    if len(excluded) != args.expected_excluded:
        raise ValueError(
            f"excluded rows {len(excluded)} != expected {args.expected_excluded}"
        )

    args.output_dir.mkdir(parents=True, exist_ok=True)
    outputs = {
        "upstream_family_census_v1.jsonl": families,
        "priority_families_v1.jsonl": priorities,
        "semantic_anchor_census_v1.jsonl": anchors,
        "priority_semantic_anchors_v1.jsonl": priority_anchors,
        "priority_anchor_candidate_units_v1.jsonl": anchor_candidates,
        "excluded_reviewed_units_v1.jsonl": excluded,
        "upstream_call_census_v2.jsonl": discovery_calls,
        "upstream_call_cooccurrence_census_v2.jsonl": discovery_pairs,
        "priority_call_cooccurrences_v2.jsonl": [
            row
            for row in discovery_pairs
            if row["review_priority"] == "calibration_required"
        ],
    }
    artifacts = []
    for name, output_rows in outputs.items():
        path = args.output_dir / name
        _write_jsonl(path, output_rows)
        artifacts.append(path)
    summary_path = args.output_dir / "summary_v1.json"
    summary["semantic_anchor_census"] = anchor_summary
    summary["discovery_census"] = discovery_summary
    summary["semantic_anchor_census"]["priority_candidate_units"] = len(
        anchor_candidates
    )
    _atomic_write(
        summary_path,
        json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
    )
    artifacts.append(summary_path)
    ledger = {
        "schema": "gis_recommend.hash_ledger.v1",
        "inputs": {
            "mutation_upstream": {
                "path": str(args.mutation_upstream),
                "sha256": _sha256(args.mutation_upstream),
            },
            **{
                f"exclude_reviewed_{index}": {
                    "path": str(path),
                    "sha256": _sha256(path),
                }
                for index, path in enumerate(args.exclude_reviewed)
            },
        },
        "artifacts": {
            path.name: {"sha256": _sha256(path), "bytes": path.stat().st_size}
            for path in artifacts
        },
    }
    _atomic_write(
        args.output_dir / "hash_ledger_v1.json",
        json.dumps(ledger, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
