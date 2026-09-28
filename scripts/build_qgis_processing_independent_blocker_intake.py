#!/usr/bin/env python3
"""Census untouched Processing blockers with source-backed call evidence.

This is an intake-only selector.  It deliberately excludes the delivered
authority and previously scanned blocker populations, then clusters only rows
whose recorded call sites agree with their operator sequence.  A selected row
is not a task boundary, L3 mapping, description, or training authority.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import tempfile
from collections import Counter, defaultdict, deque
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.build_qgis_processing_mapping_gap_queue import (
    DATABASE_SIDE_EFFECT_OPERATORS,
    SUPPORT_EXPORT_OPERATORS,
)

SCHEMA = "gis_recommend.qgis_processing_independent_blocker_intake.v1"
BLOCKER_STATUSES = {
    "deferred_boundary",
    "deferred_mapping",
    "deferred_operator",
}


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


def _operator_ids(values: object) -> tuple[str, ...]:
    if not isinstance(values, list):
        return ()
    return tuple(str(value).lower() for value in values if value)


def _call_site_ids(row: dict[str, Any]) -> tuple[str, ...]:
    sites = row.get("call_sites") or []
    if not isinstance(sites, list):
        return ()
    return tuple(
        str(site.get("operator_id") or "").lower()
        for site in sites
        if isinstance(site, dict) and site.get("operator_id")
    )


def _signature(row: dict[str, Any]) -> tuple[str, str, str, tuple[str, ...]]:
    return (
        str(row.get("status") or ""),
        str(row.get("route_action") or ""),
        str(row.get("normalization_status") or ""),
        _operator_ids(row.get("operator_sequence")),
    )


def _signature_id(signature: tuple[str, str, str, tuple[str, ...]]) -> str:
    payload = "\x1f".join([*signature[:3], "\x1e".join(signature[3])])
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:24]


def _rank(seed: int, signature_id: str, source_sha256: str) -> str:
    return hashlib.sha256(
        f"{seed}\x1f{signature_id}\x1f{source_sha256}".encode()
    ).hexdigest()


def _select_diverse_sources(
    rows: list[dict[str, Any]], *, signature_id: str, count: int, seed: int
) -> list[dict[str, Any]]:
    by_root: dict[str, deque[dict[str, Any]]] = {}
    roots: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        roots[str(row.get("source_root_id") or "unknown")].append(row)
    for root, group in sorted(roots.items()):
        by_root[root] = deque(
            sorted(
                group,
                key=lambda row: _rank(seed, signature_id, str(row["source_sha256"])),
            )
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

    seen_record_ids: set[str] = set()
    representatives: dict[
        tuple[str, str, str, tuple[str, ...]], dict[str, dict[str, Any]]
    ] = defaultdict(dict)
    exclusions: Counter[str] = Counter()
    for row in ledger:
        record_id = str(row.get("record_id") or "")
        source_sha = str(row.get("source_sha256") or "")
        if not record_id or not source_sha or not row.get("source_path"):
            exclusions["missing_source_identity"] += 1
            continue
        if record_id in seen_record_ids:
            raise ValueError(f"duplicate ledger record ID: {record_id}")
        seen_record_ids.add(record_id)
        if str(row.get("status") or "") not in BLOCKER_STATUSES:
            exclusions["not_blocker_status"] += 1
            continue
        if source_sha in excluded_source_sha256:
            exclusions["already_delivered_or_scanned_source"] += 1
            continue
        sequence = _operator_ids(row.get("operator_sequence"))
        call_sites = _call_site_ids(row)
        if not sequence or not call_sites:
            exclusions["missing_recorded_call_evidence"] += 1
            continue
        if sequence != call_sites:
            exclusions["call_evidence_sequence_mismatch"] += 1
            continue
        if any(
            operator_id in DATABASE_SIDE_EFFECT_OPERATORS | SUPPORT_EXPORT_OPERATORS
            for operator_id in sequence
        ):
            exclusions["unsafe_database_or_support_operator"] += 1
            continue
        signature = _signature(row)
        current = representatives[signature].get(source_sha)
        if current is None or record_id < str(current["record_id"]):
            representatives[signature][source_sha] = dict(row)

    clusters: list[dict[str, Any]] = []
    selected: list[dict[str, Any]] = []
    for signature, by_sha in representatives.items():
        rows = list(by_sha.values())
        signature_id = _signature_id(signature)
        support = len(rows)
        qualifying = support >= minimum_source_support
        cluster = {
            "schema": "gis_recommend.qgis_processing_independent_blocker_cluster.v1",
            "signature_id": signature_id,
            "status": signature[0],
            "route_action": signature[1],
            "normalization_status": signature[2],
            "operator_sequence": list(signature[3]),
            "recorded_call_site_sequence": list(signature[3]),
            "record_count": support,
            "independent_source_sha256_support": support,
            "source_root_count": len(
                {str(row.get("source_root_id") or "") for row in rows}
            ),
            "precalibration_eligible": qualifying,
            "precalibration_status": (
                "pending_server_sha_and_normalized_body_verification"
                if qualifying
                else "insufficient_independent_source_support"
            ),
            "training_admission": "not_granted_intake_only",
            "training_rows_emitted": 0,
            "validation_eligible": False,
            "test_eligible": False,
            "production_merge": "not_granted",
            "llm_called": False,
        }
        clusters.append(cluster)
        if qualifying:
            for row in _select_diverse_sources(
                rows,
                signature_id=signature_id,
                count=min(sources_per_family, support),
                seed=seed,
            ):
                selected.append(
                    {
                        **row,
                        "schema": SCHEMA,
                        "intake_signature_id": signature_id,
                        "intake_seed": seed,
                        "intake_status": "pending_server_sha_and_normalized_body_verification",
                        "normalized_source_body_sha256": "",
                        "source_authority_key": "",
                        "task_boundary_admission": "not_granted_intake_only",
                        "taxonomy_admission": "not_granted_intake_only",
                        "training_admission": "not_granted_intake_only",
                        "training_row_emitted": False,
                        "validation_eligible": False,
                        "test_eligible": False,
                        "production_merge": "not_granted",
                        "llm_called": False,
                    }
                )
    clusters.sort(
        key=lambda row: (
            -int(row["independent_source_sha256_support"]),
            str(row["signature_id"]),
        )
    )
    qualified_ids = {
        str(row["signature_id"]) for row in clusters if row["precalibration_eligible"]
    }
    selected = [row for row in selected if row["intake_signature_id"] in qualified_ids]
    selected.sort(
        key=lambda row: (str(row["intake_signature_id"]), str(row["source_sha256"])),
    )
    allowed_ids = {
        str(row["signature_id"])
        for row in clusters[:maximum_family_count]
        if row["precalibration_eligible"]
    }
    selected = [row for row in selected if row["intake_signature_id"] in allowed_ids]
    summary = {
        "schema": f"{SCHEMA}.summary",
        "ledger_rows": len(ledger),
        "excluded_source_sha256_count": len(excluded_source_sha256),
        "call_evidence_clusters": len(clusters),
        "precalibration_eligible_family_count": len(qualified_ids),
        "selected_family_count": len({row["intake_signature_id"] for row in selected}),
        "selected_rows": len(selected),
        "selected_source_sha256_unique": len({row["source_sha256"] for row in selected})
        == len(selected),
        "exclusion_counts": dict(sorted(exclusions.items())),
        "minimum_source_support": minimum_source_support,
        "sources_per_family": sources_per_family,
        "maximum_family_count": maximum_family_count,
        "training_rows_emitted": 0,
        "training_admission": "not_granted_intake_only",
        "validation_eligible": False,
        "test_eligible": False,
        "production_merge": "not_granted",
        "llm_called": False,
        "next_gate": "server_sha_and_normalized_body_verification_then_source_disjoint_boundary_calibration",
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
    intake_path = args.output_dir / "independent_blocker_intake_selection_v1.jsonl"
    clusters_path = args.output_dir / "independent_blocker_clusters_v1.jsonl"
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
