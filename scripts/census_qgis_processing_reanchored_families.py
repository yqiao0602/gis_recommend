#!/usr/bin/env python3
"""Cluster strict Processing units after exact provider reanchoring.

This census is deliberately upstream of L3 admission and training export.  It
only permits units whose source SHA, normalized-body authority, and provider
alias proof are already present in the source manifest.  A family is eligible
for a source-disjoint calibration packet only at the requested independent-body
support threshold.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import tempfile
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

SCHEMA = "gis_recommend.qgis_processing_reanchored_family_census.v1"


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _stable_key(*values: str) -> str:
    return hashlib.sha256("\x1f".join(values).encode("utf-8")).hexdigest()


def _is_strict_complete(unit: dict[str, Any]) -> bool:
    return (
        unit.get("split_class") == "multi_step_local_dag"
        and unit.get("local_structure_status") == "eligible"
        and unit.get("description_fidelity_passed") is True
        and bool(unit.get("frozen_operator_ids"))
        and bool(unit.get("frozen_l3_chain"))
    )


def _family_signature(unit: dict[str, Any], parser: str) -> tuple[str, dict[str, Any]]:
    # frozen_* IDs were already converted to canonical IDs by the exact alias verifier.
    signature = {
        "boundary_parser": parser,
        "boundary_rule": unit.get("recovery_rule_id")
        if parser == "recovery"
        else "split-local-structure-v9",
        "operator_ids": unit["frozen_operator_ids"],
        "dependency_edges": unit["frozen_dependency_edges"],
        "l3_chain": unit["frozen_l3_chain"],
    }
    encoded = json.dumps(
        signature, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest(), signature


def _representatives(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_body: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        by_body[str(row["normalized_source_body_sha256"])].append(row)
    return [
        min(
            group,
            key=lambda row: (
                str(row["source_sha256"]),
                str(row.get("unit_id") or row.get("record_id") or ""),
            ),
        )
        for _, group in sorted(by_body.items())
    ]


def _operator_resolution_clusters(
    source_rows: list[dict[str, Any]], *, minimum_authority_support: int
) -> tuple[list[dict[str, Any]], dict[str, int]]:
    """Census canonical operator sequences without claiming a recovered boundary."""
    candidates = [
        row
        for row in source_rows
        if row.get("precalibration_lane") == "defer_operator_resolution"
        and row.get("normalized_source_body_sha256")
        and row.get("operator_sequence")
    ]
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    signatures: dict[str, dict[str, Any]] = {}
    for row in candidates:
        signature = {
            "canonical_operator_sequence": row["operator_sequence"],
            "dependency_edges": row.get("dependency_edges") or [],
        }
        encoded = json.dumps(
            signature, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        )
        signature_hash = hashlib.sha256(encoded.encode("utf-8")).hexdigest()
        grouped[signature_hash].append(row)
        signatures[signature_hash] = signature

    clusters = []
    for signature_hash, rows in grouped.items():
        representatives = _representatives(rows)
        support = len(representatives)
        clusters.append(
            {
                "schema": "gis_recommend.qgis_processing_reanchored_operator_cluster.v1",
                "operator_signature_hash": signature_hash,
                "operator_signature": signatures[signature_hash],
                "source_row_count": len(rows),
                "normalized_body_authority_support": support,
                "support_ge_threshold": support >= minimum_authority_support,
                "boundary_status": "unproven_operator_resolution_pending",
                "calibration_eligible": False,
                "training_admission": "not_granted_operator_resolution_and_boundary_pending",
                "training_rows_emitted": 0,
                "representative_record_ids": [
                    row["record_id"] for row in representatives
                ],
            }
        )
    clusters.sort(
        key=lambda row: (
            -int(row["normalized_body_authority_support"]),
            str(row["operator_signature_hash"]),
        )
    )
    return clusters, {
        "operator_resolution_source_rows": len(candidates),
        "operator_resolution_unique_normalized_bodies": len(
            {row["normalized_source_body_sha256"] for row in candidates}
        ),
        "operator_resolution_exact_sequence_cluster_count": len(clusters),
        "operator_resolution_maximum_normalized_body_support": max(
            (int(row["normalized_body_authority_support"]) for row in clusters),
            default=0,
        ),
        "operator_resolution_support_ge_threshold_cluster_count": sum(
            bool(row["support_ge_threshold"]) for row in clusters
        ),
    }


def census(
    source_rows: list[dict[str, Any]],
    recovery_units: list[dict[str, Any]],
    split_units: list[dict[str, Any]],
    *,
    minimum_authority_support: int,
    seed: int,
) -> tuple[
    list[dict[str, Any]],
    list[dict[str, Any]],
    list[dict[str, Any]],
    list[dict[str, Any]],
    dict[str, Any],
]:
    if minimum_authority_support < 2:
        raise ValueError("minimum_authority_support must be at least two")
    sources = {str(row.get("record_id") or ""): row for row in source_rows}
    if len(sources) != len(source_rows):
        raise ValueError("source manifest has duplicate or blank record IDs")

    strict: list[dict[str, Any]] = []
    excluded = Counter()
    parser_counts = {"recovery": len(recovery_units), "split": len(split_units)}
    for parser, units in (("recovery", recovery_units), ("split", split_units)):
        for unit in units:
            parent = sources.get(str(unit.get("parent_record_id") or ""))
            if parent is None:
                raise ValueError(
                    f"unit parent is absent from source manifest: {unit.get('parent_record_id')}"
                )
            if unit.get("source_sha256") != parent.get("source_sha256"):
                raise ValueError(
                    f"unit source SHA differs from parent manifest: {unit.get('unit_id')}"
                )
            body = str(parent.get("normalized_source_body_sha256") or "")
            if not body:
                raise ValueError(
                    f"verified parent lacks normalized body: {unit.get('parent_record_id')}"
                )
            if str(parent.get("provider_alias_status") or "") not in {
                "already_literal_canonical",
                "verified_exact_same_slug",
            }:
                raise ValueError(
                    f"parent lacks exact provider proof: {unit.get('parent_record_id')}"
                )
            if not _is_strict_complete(unit):
                excluded[f"{parser}:not_strict_complete"] += 1
                continue
            signature_hash, signature = _family_signature(unit, parser)
            row = dict(unit)
            row.update(
                {
                    "schema": "gis_recommend.qgis_processing_reanchored_strict_unit.v1",
                    "boundary_parser": parser,
                    "family_signature_hash": signature_hash,
                    "family_signature": signature,
                    "normalized_source_body_sha256": body,
                    "provider_alias_status": parent["provider_alias_status"],
                    "provider_migrations": parent.get("provider_migrations") or [],
                    "canonical_provider_anchor": "exact_source_literal_or_qgis_to_native_same_slug",
                    "training_admission": "not_granted_pending_family_calibration",
                    "training_row_emitted": False,
                    "validation_eligible": False,
                    "test_eligible": False,
                    "production_merge": "not_granted",
                    "llm_called": False,
                }
            )
            strict.append(row)

    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in strict:
        grouped[str(row["family_signature_hash"])].append(row)

    clusters: list[dict[str, Any]] = []
    calibration: list[dict[str, Any]] = []
    for signature_hash, rows in sorted(grouped.items()):
        representatives = _representatives(rows)
        signature = representatives[0]["family_signature"]
        support = len(representatives)
        qualified = support >= minimum_authority_support
        clusters.append(
            {
                "schema": "gis_recommend.qgis_processing_reanchored_family_cluster.v1",
                "family_signature_hash": signature_hash,
                "family_signature": signature,
                "strict_unit_count": len(rows),
                "normalized_body_authority_support": support,
                "source_sha256_support": len(
                    {row["source_sha256"] for row in representatives}
                ),
                "provider_reanchored_unit_count": sum(
                    bool(row["provider_migrations"]) for row in rows
                ),
                "calibration_eligible": qualified,
                "calibration_status": "eligible_for_source_disjoint_packet"
                if qualified
                else "insufficient_independent_body_support",
                "training_admission": "not_granted_pending_family_calibration",
                "training_rows_emitted": 0,
                "representative_unit_ids": [row["unit_id"] for row in representatives],
            }
        )
        if not qualified:
            continue
        ranked = sorted(
            representatives,
            key=lambda row: _stable_key(
                str(seed), signature_hash, str(row["normalized_source_body_sha256"])
            ),
        )
        for index, row in enumerate(ranked):
            packet = dict(row)
            packet.update(
                {
                    "schema": "gis_recommend.qgis_processing_reanchored_family_calibration.v1",
                    "calibration_role": "calibration" if index % 2 == 0 else "holdout",
                    "calibration_seed": seed,
                    "calibration_group": signature_hash,
                    "training_admission": "not_granted_pending_source_disjoint_calibration",
                    "training_row_emitted": False,
                }
            )
            calibration.append(packet)

    calibration_bodies = {
        row["normalized_source_body_sha256"]
        for row in calibration
        if row["calibration_role"] == "calibration"
    }
    holdout_bodies = {
        row["normalized_source_body_sha256"]
        for row in calibration
        if row["calibration_role"] == "holdout"
    }
    if calibration_bodies & holdout_bodies:
        raise AssertionError("calibration/holdout normalized-body leakage")
    operator_clusters, operator_summary = _operator_resolution_clusters(
        source_rows, minimum_authority_support=minimum_authority_support
    )
    summary = {
        "schema": f"{SCHEMA}.summary",
        "source_manifest_rows": len(source_rows),
        "source_manifest_provider_reanchored": sum(
            bool(row.get("provider_migrations")) for row in source_rows
        ),
        "unit_rows_by_parser": parser_counts,
        "strict_complete_unit_count": len(strict),
        "strict_complete_unique_normalized_bodies": len(
            {row["normalized_source_body_sha256"] for row in strict}
        ),
        "excluded_unit_counts": dict(sorted(excluded.items())),
        "family_cluster_count": len(clusters),
        "qualified_family_count": sum(
            bool(row["calibration_eligible"]) for row in clusters
        ),
        "maximum_normalized_body_support": max(
            (row["normalized_body_authority_support"] for row in clusters), default=0
        ),
        "minimum_authority_support": minimum_authority_support,
        "holdout_rows": sum(
            row["calibration_role"] == "holdout" for row in calibration
        ),
        "calibration_rows": sum(
            row["calibration_role"] == "calibration" for row in calibration
        ),
        "calibration_holdout_normalized_body_overlap": len(
            calibration_bodies & holdout_bodies
        ),
        "training_rows_emitted": 0,
        "training_admission": "not_granted_pending_family_calibration",
        "validation_eligible": False,
        "test_eligible": False,
        "production_merge": "not_granted",
        "llm_called": False,
        "decision": "no_calibration_packet_when_no_family_meets_independent_body_support",
    }
    summary.update(operator_summary)
    return strict, clusters, calibration, operator_clusters, summary


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "w", encoding="utf-8", newline="", dir=path.parent, delete=False
    ) as handle:
        for row in rows:
            handle.write(
                json.dumps(
                    row, ensure_ascii=False, sort_keys=True, separators=(",", ":")
                )
                + "\n"
            )
        temporary = Path(handle.name)
    temporary.replace(path)


def _write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "w", encoding="utf-8", newline="", dir=path.parent, delete=False
    ) as handle:
        json.dump(value, handle, ensure_ascii=False, indent=2, sort_keys=True)
        handle.write("\n")
        temporary = Path(handle.name)
    temporary.replace(path)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-manifest", type=Path, required=True)
    parser.add_argument("--recovery-units", type=Path, required=True)
    parser.add_argument("--split-units", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--minimum-authority-support", type=int, default=30)
    parser.add_argument("--seed", type=int, default=20260807)
    args = parser.parse_args()
    if args.output_dir.exists() and any(args.output_dir.iterdir()):
        raise ValueError(f"output directory is not empty: {args.output_dir}")
    strict, clusters, calibration, operator_clusters, summary = census(
        _read_jsonl(args.source_manifest),
        _read_jsonl(args.recovery_units),
        _read_jsonl(args.split_units),
        minimum_authority_support=args.minimum_authority_support,
        seed=args.seed,
    )
    strict_path = args.output_dir / "strict_units_v1.jsonl"
    clusters_path = args.output_dir / "family_clusters_v1.jsonl"
    calibration_path = args.output_dir / "calibration_packet_v1.jsonl"
    operator_clusters_path = args.output_dir / "operator_sequence_clusters_v1.jsonl"
    summary_path = args.output_dir / "summary_v1.json"
    _write_jsonl(strict_path, strict)
    _write_jsonl(clusters_path, clusters)
    _write_jsonl(calibration_path, calibration)
    _write_jsonl(operator_clusters_path, operator_clusters)
    _write_json(summary_path, summary)
    _write_json(
        args.output_dir / "hash_ledger_v1.json",
        {
            "schema": "gis_recommend.hash_ledger.v1",
            "inputs": {
                path.name: {"path": str(path), "sha256": _sha256(path)}
                for path in (
                    args.source_manifest,
                    args.recovery_units,
                    args.split_units,
                )
            },
            "artifacts": {
                path.name: {"sha256": _sha256(path), "bytes": path.stat().st_size}
                for path in (
                    strict_path,
                    clusters_path,
                    calibration_path,
                    operator_clusters_path,
                    summary_path,
                )
            },
        },
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
