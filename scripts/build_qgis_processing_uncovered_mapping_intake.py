#!/usr/bin/env python3
"""Select an untouched, source-disjoint Mapping-deferred Processing intake.

This selector is intentionally before taxonomy review and task-boundary replay.
It identifies high-support, fully-normalized single-operator mapping gaps after
excluding all already delivered and previously calibrated source SHA values.
The output is a server-verification intake, never a training or L3 authority.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import tempfile
from collections import Counter, defaultdict, deque
from pathlib import Path
from typing import Any

from scripts.build_qgis_processing_mapping_gap_queue import (
    DATABASE_SIDE_EFFECT_OPERATORS,
    SUPPORT_EXPORT_OPERATORS,
)

SCHEMA = "gis_recommend.qgis_processing_uncovered_mapping_intake.v1"


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _source_hashes(rows: list[dict[str, Any]]) -> set[str]:
    return {str(row["source_sha256"]) for row in rows if row.get("source_sha256")}


def _is_mapping_deferred(row: dict[str, Any]) -> bool:
    return (
        row.get("route_action") == "defer_mapping"
        or row.get("status") == "deferred_mapping"
    )


def _single_unmapped_operator(row: dict[str, Any]) -> str:
    gaps = [
        str(value).lower() for value in row.get("unmapped_operator_ids") or [] if value
    ]
    unique = list(dict.fromkeys(gaps))
    return unique[0] if len(unique) == 1 else ""


def _rank(seed: int, operator_id: str, row: dict[str, Any]) -> str:
    return hashlib.sha256(
        f"{seed}\x1f{operator_id}\x1f{row['source_sha256']}".encode()
    ).hexdigest()


def _select_diverse_sources(
    rows: list[dict[str, Any]], *, operator_id: str, count: int, seed: int
) -> list[dict[str, Any]]:
    by_root: dict[str, deque[dict[str, Any]]] = {}
    for root, group in sorted(_group(rows, "source_root_id").items()):
        by_root[root] = deque(
            sorted(group, key=lambda row: _rank(seed, operator_id, row))
        )
    selected: list[dict[str, Any]] = []
    while by_root and len(selected) < count:
        for root in list(by_root):
            selected.append(by_root[root].popleft())
            if not by_root[root]:
                del by_root[root]
            if len(selected) == count:
                break
    return selected


def _group(rows: list[dict[str, Any]], field: str) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[str(row.get(field) or "unknown")].append(row)
    return grouped


def build_intake(
    ledger: list[dict[str, Any]],
    *,
    excluded_source_sha256: set[str],
    minimum_source_support: int,
    sources_per_family: int,
    maximum_family_count: int,
    seed: int,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    if minimum_source_support < 2:
        raise ValueError("minimum_source_support must be at least two")
    if sources_per_family <= 0 or maximum_family_count <= 0:
        raise ValueError("family selection limits must be positive")

    seen_records: set[str] = set()
    by_operator: dict[str, list[dict[str, Any]]] = defaultdict(list)
    exclusions = Counter()
    for row in ledger:
        record_id = str(row.get("record_id") or "")
        source_sha = str(row.get("source_sha256") or "")
        if not record_id or not source_sha or not row.get("source_path"):
            exclusions["missing_source_identity"] += 1
            continue
        if record_id in seen_records:
            raise ValueError(f"duplicate ledger record ID: {record_id}")
        seen_records.add(record_id)
        if not _is_mapping_deferred(row):
            exclusions["not_mapping_deferred"] += 1
            continue
        if source_sha in excluded_source_sha256:
            exclusions["already_delivered_or_calibrated_source"] += 1
            continue
        if row.get("normalization_status") != "fully_normalized":
            exclusions["not_fully_normalized"] += 1
            continue
        operator_id = _single_unmapped_operator(row)
        if not operator_id:
            exclusions["not_single_unmapped_operator"] += 1
            continue
        if operator_id in DATABASE_SIDE_EFFECT_OPERATORS | SUPPORT_EXPORT_OPERATORS:
            exclusions["unsafe_database_or_support_operator"] += 1
            continue
        by_operator[operator_id].append(dict(row))

    clusters: list[dict[str, Any]] = []
    candidates_by_operator: dict[str, list[dict[str, Any]]] = {}
    for operator_id, rows in by_operator.items():
        by_sha = _group(rows, "source_sha256")
        representatives = [
            min(group, key=lambda row: str(row["record_id"]))
            for _, group in sorted(by_sha.items())
        ]
        support = len(representatives)
        qualifying = support >= minimum_source_support
        candidates_by_operator[operator_id] = representatives
        clusters.append(
            {
                "schema": "gis_recommend.qgis_processing_uncovered_mapping_cluster.v1",
                "unmapped_operator_id": operator_id,
                "record_count": len(rows),
                "independent_source_sha256_support": support,
                "source_root_count": len(
                    {row.get("source_root_id") for row in representatives}
                ),
                "precalibration_eligible": qualifying,
                "precalibration_status": "pending_server_sha_and_normalized_body_verification"
                if qualifying
                else "insufficient_independent_source_support",
                "training_admission": "not_granted_mapping_intake_only",
                "training_rows_emitted": 0,
                "validation_eligible": False,
                "test_eligible": False,
                "production_merge": "not_granted",
                "llm_called": False,
            }
        )
    clusters.sort(
        key=lambda row: (
            -int(row["independent_source_sha256_support"]),
            str(row["unmapped_operator_id"]),
        )
    )

    selected: list[dict[str, Any]] = []
    for cluster in [row for row in clusters if row["precalibration_eligible"]][
        :maximum_family_count
    ]:
        operator_id = str(cluster["unmapped_operator_id"])
        selected_rows = _select_diverse_sources(
            candidates_by_operator[operator_id],
            operator_id=operator_id,
            count=min(sources_per_family, len(candidates_by_operator[operator_id])),
            seed=seed,
        )
        for row in selected_rows:
            row.update(
                {
                    "schema": SCHEMA,
                    "intake_operator_id": operator_id,
                    "intake_seed": seed,
                    "intake_status": "pending_server_sha_and_normalized_body_verification",
                    "source_authority_key": "",
                    "normalized_source_body_sha256": "",
                    "taxonomy_admission": "not_granted_mapping_intake_only",
                    "training_admission": "not_granted_mapping_intake_only",
                    "training_row_emitted": False,
                    "validation_eligible": False,
                    "test_eligible": False,
                    "production_merge": "not_granted",
                    "llm_called": False,
                }
            )
            selected.append(row)
    selected.sort(
        key=lambda row: (str(row["intake_operator_id"]), str(row["source_sha256"]))
    )
    summary = {
        "schema": f"{SCHEMA}.summary",
        "ledger_rows": len(ledger),
        "excluded_source_sha256_count": len(excluded_source_sha256),
        "eligible_single_gap_operator_clusters": len(clusters),
        "precalibration_eligible_family_count": sum(
            bool(row["precalibration_eligible"]) for row in clusters
        ),
        "selected_family_count": len({row["intake_operator_id"] for row in selected}),
        "selected_rows": len(selected),
        "selected_source_sha256_unique": len({row["source_sha256"] for row in selected})
        == len(selected),
        "exclusion_counts": dict(sorted(exclusions.items())),
        "minimum_source_support": minimum_source_support,
        "sources_per_family": sources_per_family,
        "maximum_family_count": maximum_family_count,
        "training_rows_emitted": 0,
        "training_admission": "not_granted_mapping_intake_only",
        "validation_eligible": False,
        "test_eligible": False,
        "production_merge": "not_granted",
        "llm_called": False,
        "next_gate": "server_sha_and_normalized_body_verification_before_any_taxonomy_or_boundary_work",
    }
    return selected, clusters, summary


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "w", encoding="utf-8", newline="", dir=path.parent, delete=False
    ) as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
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
    parser.add_argument("--ledger", type=Path, required=True)
    parser.add_argument("--existing-authority", type=Path, required=True)
    parser.add_argument(
        "--exclude-source-manifest", type=Path, action="append", default=[]
    )
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--minimum-source-support", type=int, default=30)
    parser.add_argument("--sources-per-family", type=int, default=60)
    parser.add_argument("--maximum-family-count", type=int, default=4)
    parser.add_argument("--seed", type=int, default=20260807)
    args = parser.parse_args()
    if args.output_dir.exists() and any(args.output_dir.iterdir()):
        raise ValueError(f"output directory is not empty: {args.output_dir}")
    excluded = _source_hashes(_read_jsonl(args.existing_authority))
    for path in args.exclude_source_manifest:
        excluded.update(_source_hashes(_read_jsonl(path)))
    selected, clusters, summary = build_intake(
        _read_jsonl(args.ledger),
        excluded_source_sha256=excluded,
        minimum_source_support=args.minimum_source_support,
        sources_per_family=args.sources_per_family,
        maximum_family_count=args.maximum_family_count,
        seed=args.seed,
    )
    intake_path = args.output_dir / "mapping_intake_selection_v1.jsonl"
    clusters_path = args.output_dir / "mapping_gap_clusters_v1.jsonl"
    summary_path = args.output_dir / "summary_v1.json"
    _write_jsonl(intake_path, selected)
    _write_jsonl(clusters_path, clusters)
    _write_json(summary_path, summary)
    _write_json(
        args.output_dir / "hash_ledger_v1.json",
        {
            "schema": "gis_recommend.hash_ledger.v1",
            "inputs": {
                args.ledger.name: _sha256(args.ledger),
                args.existing_authority.name: _sha256(args.existing_authority),
                **{path.name: _sha256(path) for path in args.exclude_source_manifest},
            },
            "artifacts": {
                path.name: _sha256(path)
                for path in (intake_path, clusters_path, summary_path)
            },
        },
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
