#!/usr/bin/env python3
"""Recover and cluster local boundaries for untouched Processing blockers.

The script is intentionally pre-taxonomy. It selects the independent
source-backed call population, validates every source hash, recovers local
subworkflows with the frozen splitter, and clusters only structural boundary
signatures. It never emits L3 labels, task text, or training rows.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import tempfile
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from gis_recommend.data.qgis_subworkflow_splitter import (
    split_candidate_into_local_units,
)
from scripts.build_qgis_processing_independent_blocker_intake import (
    BLOCKER_STATUSES,
    _call_site_ids,
    _operator_ids,
    _source_hashes,
)
from scripts.build_qgis_processing_mapping_gap_queue import (
    DATABASE_SIDE_EFFECT_OPERATORS,
    SUPPORT_EXPORT_OPERATORS,
)
from scripts.verify_qgis_processing_provider_aliases import (
    _is_exact_qgis_native_alias,
    _literal_processing_calls,
)

SCHEMA = "gis_recommend.qgis_processing_independent_local_boundary_replay.v1"


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _canonical_parent_rows(
    ledger: list[dict[str, Any]],
    *,
    excluded_source_sha256: set[str],
    max_call_sites: int,
) -> tuple[list[dict[str, Any]], dict[str, int]]:
    candidates: dict[str, dict[str, Any]] = {}
    exclusions: Counter[str] = Counter()
    for row in ledger:
        source_sha = str(row.get("source_sha256") or "")
        record_id = str(row.get("record_id") or "")
        if not record_id or not source_sha or not row.get("source_path"):
            exclusions["missing_source_identity"] += 1
            continue
        if str(row.get("status") or "") not in BLOCKER_STATUSES:
            exclusions["not_blocker_status"] += 1
            continue
        if source_sha in excluded_source_sha256:
            exclusions["already_delivered_or_scanned_source"] += 1
            continue
        sequence = _operator_ids(row.get("operator_sequence"))
        call_sites = _call_site_ids(row)
        if not sequence or sequence != call_sites:
            exclusions["missing_or_mismatched_call_evidence"] += 1
            continue
        if len(call_sites) > max_call_sites:
            exclusions["too_many_recorded_call_sites"] += 1
            continue
        if any(
            operator_id in DATABASE_SIDE_EFFECT_OPERATORS | SUPPORT_EXPORT_OPERATORS
            for operator_id in sequence
        ):
            exclusions["unsafe_database_or_support_operator"] += 1
            continue
        current = candidates.get(source_sha)
        if current is None or record_id < str(current["record_id"]):
            candidates[source_sha] = dict(row)
    return sorted(candidates.values(), key=lambda row: str(row["source_sha256"])), dict(
        sorted(exclusions.items())
    )


def _select_source_root_stratified(
    rows: list[dict[str, Any]], *, maximum_parents: int, seed: int
) -> list[dict[str, Any]]:
    if maximum_parents <= 0 or len(rows) <= maximum_parents:
        return rows
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[str(row.get("source_root_id") or "unknown")].append(row)
    queues = {
        root: sorted(
            members,
            key=lambda row: hashlib.sha256(
                f"{seed}\x1f{root}\x1f{row['source_sha256']}".encode()
            ).hexdigest(),
        )
        for root, members in grouped.items()
    }
    selected: list[dict[str, Any]] = []
    while queues and len(selected) < maximum_parents:
        for root in sorted(queues):
            selected.append(queues[root].pop(0))
            if not queues[root]:
                del queues[root]
            if len(selected) == maximum_parents:
                break
    return sorted(selected, key=lambda row: str(row["source_sha256"]))


def _structural_signature(unit: dict[str, Any]) -> dict[str, Any]:
    operators = list(unit.get("operator_ids") or [])
    edges = [list(map(int, edge)) for edge in unit.get("dependency_edges") or []]
    indegree = [0] * len(operators)
    outdegree = [0] * len(operators)
    for source, target in edges:
        outdegree[source] += 1
        indegree[target] += 1
    return {
        "split_class": str(unit.get("split_class") or ""),
        "local_structure_status": str(unit.get("local_structure_status") or ""),
        "local_structure_reasons": sorted(
            str(reason) for reason in unit.get("local_structure_reasons") or []
        ),
        "node_count": len(operators),
        "edge_count": len(edges),
        "root_count": sum(value == 0 for value in indegree),
        "sink_count": sum(value == 0 for value in outdegree),
        "degree_shape": sorted(zip(indegree, outdegree)),
    }


def _signature_id(signature: dict[str, Any]) -> str:
    payload = json.dumps(
        signature, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:24]


def _verify_provider_reanchors(
    source_text: str, call_sites: list[dict[str, Any]]
) -> tuple[list[dict[str, str]], list[dict[str, Any]]]:
    calls = _literal_processing_calls(source_text)
    migrations: list[dict[str, str]] = []
    source_call_sites: list[dict[str, Any]] = []
    for site in call_sites:
        start = int(site.get("line_start") or 0)
        end = int(site.get("line_end") or start)
        expected = str(site.get("operator_id") or "").lower()
        actual = calls.get((start, end), "")
        if actual == expected:
            source_call_sites.append({**site, "operator_id": actual})
            continue
        if _is_exact_qgis_native_alias(actual, expected):
            migrations.append(
                {
                    "source": actual,
                    "target": expected,
                    "rule": "qgis_to_native_same_slug",
                }
            )
            source_call_sites.append({**site, "operator_id": actual})
            continue
        raise ValueError(f"unverified_provider_or_span:{expected}@{start}-{end}")
    return migrations, source_call_sites


def _canonical_unit_operator_ids(
    unit: dict[str, Any], *, canonical_call_sites: list[dict[str, Any]]
) -> list[str]:
    canonical_by_span = {
        (int(site["line_start"]), int(site.get("line_end") or site["line_start"])): str(
            site["operator_id"]
        ).lower()
        for site in canonical_call_sites
    }
    values = []
    for site in unit.get("call_sites") or []:
        key = (int(site["line_start"]), int(site.get("line_end") or site["line_start"]))
        canonical = canonical_by_span.get(key)
        if not canonical:
            raise ValueError(f"canonical_call_site_missing:{key[0]}-{key[1]}")
        values.append(canonical)
    return values


def replay_boundaries(
    ledger: list[dict[str, Any]],
    *,
    excluded_source_sha256: set[str],
    max_call_sites: int = 64,
    maximum_parents: int = 0,
    seed: int = 20260807,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    if max_call_sites < 2:
        raise ValueError("max_call_sites must be at least two")
    parents, exclusions = _canonical_parent_rows(
        ledger,
        excluded_source_sha256=excluded_source_sha256,
        max_call_sites=max_call_sites,
    )
    parent_population = len(parents)
    parents = _select_source_root_stratified(
        parents, maximum_parents=maximum_parents, seed=seed
    )
    units: list[dict[str, Any]] = []
    failures: list[dict[str, str]] = []
    provider_reanchored_parents = 0
    for parent in parents:
        source_path = Path(str(parent["source_path"]))
        if not source_path.is_file():
            failures.append(
                {
                    "record_id": str(parent["record_id"]),
                    "source_sha256": str(parent["source_sha256"]),
                    "reason": "source_file_missing",
                }
            )
            continue
        if _sha256(source_path) != str(parent["source_sha256"]):
            failures.append(
                {
                    "record_id": str(parent["record_id"]),
                    "source_sha256": str(parent["source_sha256"]),
                    "reason": "source_sha256_mismatch",
                }
            )
            continue
        try:
            source_text = source_path.read_text(encoding="utf-8-sig")
            call_sites = list(parent.get("call_sites") or [])
            migrations, source_call_sites = _verify_provider_reanchors(
                source_text, call_sites
            )
            if migrations:
                provider_reanchored_parents += 1
            local_units = split_candidate_into_local_units(
                source_text,
                call_sites=source_call_sites,
            )
        except (SyntaxError, UnicodeError, ValueError) as exc:
            failures.append(
                {
                    "record_id": str(parent["record_id"]),
                    "source_sha256": str(parent["source_sha256"]),
                    "reason": f"splitter_fail_closed:{exc}",
                }
            )
            continue
        for ordinal, unit in enumerate(local_units, start=1):
            signature = _structural_signature(unit)
            canonical_operator_ids = _canonical_unit_operator_ids(
                unit, canonical_call_sites=call_sites
            )
            units.append(
                {
                    **unit,
                    "schema": SCHEMA,
                    "parent_record_id": str(parent["record_id"]),
                    "source_sha256": str(parent["source_sha256"]),
                    "source_path": str(parent["source_path"]),
                    "source_root_id": str(parent.get("source_root_id") or ""),
                    "unit_ordinal": ordinal,
                    "provider_migrations": migrations,
                    "canonical_operator_ids": canonical_operator_ids,
                    "boundary_signature": signature,
                    "boundary_signature_id": _signature_id(signature),
                    "task_boundary_admission": "not_granted_boundary_census_only",
                    "taxonomy_admission": "not_granted_boundary_census_only",
                    "training_admission": "not_granted_boundary_census_only",
                    "training_row_emitted": False,
                    "validation_eligible": False,
                    "test_eligible": False,
                    "production_merge": "not_granted",
                    "llm_called": False,
                }
            )

    by_signature: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for unit in units:
        by_signature[str(unit["boundary_signature_id"])].append(unit)
    clusters = []
    for signature_id, members in by_signature.items():
        signature = dict(members[0]["boundary_signature"])
        clusters.append(
            {
                "schema": "gis_recommend.qgis_processing_local_boundary_cluster.v1",
                "boundary_signature_id": signature_id,
                "boundary_signature": signature,
                "unit_count": len(members),
                "independent_source_sha256_support": len(
                    {str(member["source_sha256"]) for member in members}
                ),
                "source_root_count": len(
                    {str(member["source_root_id"]) for member in members}
                ),
                "operator_sequence_examples": sorted(
                    {
                        tuple(str(value) for value in member.get("operator_ids") or [])
                        for member in members
                    }
                )[:5],
                "training_admission": "not_granted_boundary_census_only",
                "training_rows_emitted": 0,
            }
        )
    clusters.sort(
        key=lambda row: (
            -int(row["independent_source_sha256_support"]),
            str(row["boundary_signature_id"]),
        )
    )
    summary = {
        "schema": f"{SCHEMA}.summary",
        "parent_population": parent_population,
        "parent_candidates": len(parents),
        "selection_seed": seed,
        "source_verified_parents": len(parents) - len(failures),
        "source_failure_parents": len(failures),
        "provider_reanchored_parents": provider_reanchored_parents,
        "local_units": len(units),
        "multi_step_local_units": sum(
            row.get("split_class") == "multi_step_local_dag" for row in units
        ),
        "eligible_local_units": sum(
            row.get("local_structure_status") == "eligible" for row in units
        ),
        "boundary_signature_clusters": len(clusters),
        "max_call_sites": max_call_sites,
        "exclusion_counts": exclusions,
        "failure_reason_counts": dict(
            sorted(Counter(row["reason"].split(":", 1)[0] for row in failures).items())
        ),
        "training_rows_emitted": 0,
        "training_admission": "not_granted_boundary_census_only",
        "next_gate": "cluster_review_then_source_disjoint_calibration_of_one_recovered_boundary_family",
    }
    return units, clusters, {"summary": summary, "failures": failures}


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
    parser.add_argument("--max-call-sites", type=int, default=64)
    parser.add_argument("--maximum-parents", type=int, default=0)
    parser.add_argument("--seed", type=int, default=20260807)
    args = parser.parse_args()
    if args.output_dir.exists() and any(args.output_dir.iterdir()):
        raise ValueError(f"output directory is not empty: {args.output_dir}")
    excluded = _source_hashes(_read_jsonl(args.existing_authority))
    for path in args.exclude_source_manifest:
        excluded.update(_source_hashes(_read_jsonl(path)))
    units, clusters, outcome = replay_boundaries(
        _read_jsonl(args.ledger),
        excluded_source_sha256=excluded,
        max_call_sites=args.max_call_sites,
        maximum_parents=args.maximum_parents,
        seed=args.seed,
    )
    units_path = args.output_dir / "local_boundary_units_v1.jsonl"
    clusters_path = args.output_dir / "boundary_signature_clusters_v1.jsonl"
    failures_path = args.output_dir / "source_failures_v1.jsonl"
    summary_path = args.output_dir / "summary_v1.json"
    _write_jsonl(units_path, units)
    _write_jsonl(clusters_path, clusters)
    _write_jsonl(failures_path, outcome["failures"])
    _write_json(summary_path, outcome["summary"])
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
                for path in (units_path, clusters_path, failures_path, summary_path)
            },
        },
    )
    print(json.dumps(outcome["summary"], ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
