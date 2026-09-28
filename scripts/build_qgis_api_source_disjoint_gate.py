#!/usr/bin/env python3
"""Freeze source- and terminal-DAG-disjoint QGIS API boundary review splits."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import tempfile
from collections import defaultdict
from pathlib import Path
from typing import Any, Iterable

from gis_recommend.data.qgis_source_authority import source_authority


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _rank(seed: int, key: str) -> str:
    return hashlib.sha256(f"{seed}|{key}".encode("utf-8")).hexdigest()


def _decision_status(row: dict[str, Any]) -> str:
    task = str(row.get("task_boundary_decision") or "")
    dependency = str(row.get("dependency_decision") or "")
    terminal = str(row.get("terminal_decision") or "")
    failures = str(row.get("failure_labels") or "").strip()
    if (task, dependency, terminal, failures) == (
        "true_positive",
        "complete",
        "complete",
        "",
    ):
        return "accepted_boundary"
    if task == "false_positive" and (
        dependency == "truncated" or terminal == "incomplete" or failures
    ):
        return "deferred_boundary"
    raise ValueError(f"invalid fail-closed boundary decision: {row}")


def rebase_source_rows(
    rows: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    rebased_rows = []
    declared = {str(row.get("source_authority_key") or "") for row in rows}
    if "" in declared:
        raise ValueError("candidate unit lacks declared source authority")
    for row in rows:
        if row.get("training_row_emitted") is not False:
            raise ValueError("boundary input must emit zero training rows")
        path = Path(str(row.get("source_path") or ""))
        if not path.is_file():
            raise ValueError(f"source file missing: {path}")
        actual_sha = _sha256(path)
        declared_sha = str(row.get("source_sha256") or "")
        if actual_sha != declared_sha:
            raise ValueError(f"source SHA mismatch: {path}")
        declared_authority = str(row["source_authority_key"])
        rebased = source_authority(path, source_sha256=actual_sha)
        rebased_rows.append(
            {
                **row,
                **rebased,
                "declared_source_authority_key": declared_authority,
                "declared_normalized_source_body_sha256": str(
                    row.get("normalized_source_body_sha256") or ""
                ),
                "source_verification": "verified_sha256",
                "candidate_l3_sequence": [],
                "training_admission": "not_granted_source_disjoint_review_only",
                "training_row_emitted": False,
                "validation_eligible": False,
                "test_eligible": False,
                "production_merge": "not_granted",
            }
        )
    rebased_authorities = {
        str(row["source_authority_key"]) for row in rebased_rows
    }
    return rebased_rows, {
        "input_units": len(rows),
        "declared_source_authorities": len(declared),
        "rebased_source_authorities": len(rebased_authorities),
        "collapsed_harvest_authorities": len(declared) - len(rebased_authorities),
        "verified_source_sha256": len(rebased_rows),
        "training_rows_emitted": 0,
    }


def rebase_and_adjudicate(
    rows: list[dict[str, Any]],
    decisions: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    decision_by_authority: dict[str, dict[str, Any]] = {}
    for decision in decisions:
        key = str(decision.get("declared_source_authority_key") or "")
        if not key or key in decision_by_authority:
            raise ValueError(f"invalid or duplicate review authority: {key!r}")
        _decision_status(decision)
        decision_by_authority[key] = decision
    declared = {str(row.get("source_authority_key") or "") for row in rows}
    if "" in declared or declared != set(decision_by_authority):
        raise ValueError(
            "review coverage must exactly match declared source authorities"
        )

    rebased_rows, source_summary = rebase_source_rows(rows)
    accepted: list[dict[str, Any]] = []
    deferred: list[dict[str, Any]] = []
    decisions_by_rebased_authority: dict[str, set[str]] = defaultdict(set)
    for row in rebased_rows:
        declared_authority = str(row["declared_source_authority_key"])
        decision = decision_by_authority[declared_authority]
        status = _decision_status(decision)
        rebased_key = str(row["source_authority_key"])
        decisions_by_rebased_authority[rebased_key].add(status)
        annotated = {
            **row,
            "schema": "gis_recommend.qgis_api_source_disjoint_review_unit.v1",
            "task_boundary_decision": str(decision["task_boundary_decision"]),
            "dependency_decision": str(decision["dependency_decision"]),
            "terminal_decision": str(decision["terminal_decision"]),
            "failure_labels": [
                label
                for label in str(decision.get("failure_labels") or "").split("|")
                if label
            ],
            "reviewer_notes": str(decision.get("reviewer_notes") or ""),
            "boundary_review_status": status,
            "candidate_l3_sequence": [],
            "training_admission": "not_granted_source_disjoint_review_only",
            "training_row_emitted": False,
            "validation_eligible": False,
            "test_eligible": False,
            "production_merge": "not_granted",
        }
        (accepted if status == "accepted_boundary" else deferred).append(annotated)
    conflicts = {
        key: sorted(statuses)
        for key, statuses in decisions_by_rebased_authority.items()
        if len(statuses) != 1
    }
    if conflicts:
        raise ValueError(f"conflicting decisions within rebased source: {conflicts}")
    summary = {
        **source_summary,
        "accepted_units": len(accepted),
        "accepted_source_authorities": len(
            {str(row["source_authority_key"]) for row in accepted}
        ),
        "deferred_units": len(deferred),
        "deferred_source_authorities": len(
            {str(row["source_authority_key"]) for row in deferred}
        ),
        "training_rows_emitted": 0,
    }
    return accepted, deferred, summary


def assign_alias_groups(
    rows: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    authorities = sorted({str(row["source_authority_key"]) for row in rows})
    parent = {key: key for key in authorities}

    def find(key: str) -> str:
        while parent[key] != key:
            parent[key] = parent[parent[key]]
            key = parent[key]
        return key

    def union(first: str, second: str) -> None:
        left, right = find(first), find(second)
        if left != right:
            parent[max(left, right)] = min(left, right)

    unit_authorities: dict[str, set[str]] = defaultdict(set)
    for row in rows:
        unit_authorities[str(row["unit_id"])].add(str(row["source_authority_key"]))
    for aliases in unit_authorities.values():
        ordered = sorted(aliases)
        for alias in ordered[1:]:
            union(ordered[0], alias)

    clusters: dict[str, list[str]] = defaultdict(list)
    for authority in authorities:
        clusters[find(authority)].append(authority)
    authority_to_group: dict[str, tuple[str, list[str]]] = {}
    for aliases in clusters.values():
        ordered = sorted(aliases)
        group_id = "terminal_dag_alias_sha256:" + hashlib.sha256(
            "\n".join(ordered).encode("utf-8")
        ).hexdigest()
        for authority in ordered:
            authority_to_group[authority] = (group_id, ordered)

    annotated = []
    for row in rows:
        group_id, aliases = authority_to_group[str(row["source_authority_key"])]
        annotated.append(
            {
                **row,
                "calibration_alias_group_id": group_id,
                "calibration_alias_authority_keys": aliases,
            }
        )
    summary = {
        "accepted_units": len(rows),
        "source_authorities": len(authorities),
        "alias_groups": len(clusters),
        "multi_source_alias_groups": sum(
            len(aliases) > 1 for aliases in clusters.values()
        ),
    }
    return annotated, summary


def split_alias_groups(
    rows: list[dict[str, Any]], *, seed: int
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[str(row["calibration_alias_group_id"])].append(row)
    if len(grouped) < 2:
        raise ValueError("at least two alias groups are required for a holdout")
    ordered_groups = sorted(
        grouped.items(), key=lambda item: (-len(item[1]), _rank(seed, item[0]))
    )
    partitions: dict[str, list[dict[str, Any]]] = {
        "calibration": [],
        "holdout": [],
    }
    for _, members in ordered_groups:
        split = min(partitions, key=lambda key: (len(partitions[key]), key))
        partitions[split].extend(members)

    def annotate(split: str) -> list[dict[str, Any]]:
        return sorted(
            (
                {
                    **row,
                    "review_split": split,
                    "training_admission": "not_granted_source_disjoint_review_only",
                    "training_row_emitted": False,
                }
                for row in partitions[split]
            ),
            key=lambda row: (str(row["source_authority_key"]), str(row["candidate_id"])),
        )

    calibration = annotate("calibration")
    holdout = annotate("holdout")

    def values(split_rows: list[dict[str, Any]], field: str) -> set[str]:
        return {str(row[field]) for row in split_rows}

    overlaps = {
        "source_authority_overlap": len(
            values(calibration, "source_authority_key")
            & values(holdout, "source_authority_key")
        ),
        "source_sha256_overlap": len(
            values(calibration, "source_sha256") & values(holdout, "source_sha256")
        ),
        "alias_group_overlap": len(
            values(calibration, "calibration_alias_group_id")
            & values(holdout, "calibration_alias_group_id")
        ),
        "unit_id_overlap": len(
            values(calibration, "unit_id") & values(holdout, "unit_id")
        ),
    }
    if any(overlaps.values()):
        raise ValueError(f"source-disjoint split leakage: {overlaps}")
    summary = {
        "calibration_units": len(calibration),
        "holdout_units": len(holdout),
        "calibration_source_authorities": len(
            values(calibration, "source_authority_key")
        ),
        "holdout_source_authorities": len(values(holdout, "source_authority_key")),
        "calibration_alias_groups": len(
            values(calibration, "calibration_alias_group_id")
        ),
        "holdout_alias_groups": len(values(holdout, "calibration_alias_group_id")),
        **overlaps,
        "seed": seed,
        "training_rows_emitted": 0,
    }
    return calibration, holdout, summary


def _authority_ledger(
    rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[str(row["source_authority_key"])].append(row)
    ledger = []
    for authority, members in sorted(grouped.items()):
        ledger.append(
            {
                "schema": "gis_recommend.qgis_api_source_disjoint_authority.v1",
                "source_authority_key": authority,
                "declared_source_authority_keys": sorted(
                    {str(row["declared_source_authority_key"]) for row in members}
                ),
                "source_sha256_members": sorted(
                    {str(row["source_sha256"]) for row in members}
                ),
                "candidate_ids": sorted(str(row["candidate_id"]) for row in members),
                "unit_ids": sorted({str(row["unit_id"]) for row in members}),
                "candidate_unit_count": len(members),
                "boundary_review_status": str(members[0]["boundary_review_status"]),
                "calibration_alias_group_id": str(
                    members[0].get("calibration_alias_group_id") or ""
                ),
                "review_split": str(members[0].get("review_split") or "deferred"),
                "training_row_emitted": False,
            }
        )
    return ledger


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    with path.open(encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def _read_decisions(path: Path) -> list[dict[str, Any]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


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
    parser.add_argument("--candidate-units", type=Path, required=True)
    parser.add_argument("--authority-decisions", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--seed", type=int, default=20260730)
    args = parser.parse_args()
    if args.output_dir.exists() and any(args.output_dir.iterdir()):
        raise ValueError(f"output directory is not empty: {args.output_dir}")

    accepted, deferred, adjudication_summary = rebase_and_adjudicate(
        _read_jsonl(args.candidate_units), _read_decisions(args.authority_decisions)
    )
    grouped, alias_summary = assign_alias_groups(accepted)
    calibration, holdout, split_summary = split_alias_groups(grouped, seed=args.seed)
    admitted = calibration + holdout
    authority_ledger = _authority_ledger(admitted + deferred)
    summary = {
        "schema": "gis_recommend.qgis_api_source_disjoint_gate_summary.v1",
        "adjudication": adjudication_summary,
        "alias_clustering": alias_summary,
        "split": split_summary,
        "boundary_gate": "passed_after_fail_closed_deferral",
        "l3_mapping_rows": 0,
        "description_fidelity_rows": 0,
        "dedup_rows": 0,
        "training_rows_emitted": 0,
        "training_admission": "not_granted_source_disjoint_review_only",
    }

    args.output_dir.mkdir(parents=True, exist_ok=True)
    artifacts = {
        "accepted_candidate_units_v1.jsonl": admitted,
        "deferred_candidate_units_v1.jsonl": deferred,
        "calibration_units_v1.jsonl": calibration,
        "frozen_holdout_units_v1.jsonl": holdout,
        "source_authority_ledger_v1.jsonl": authority_ledger,
    }
    paths = []
    for name, artifact_rows in artifacts.items():
        path = args.output_dir / name
        _write_jsonl(path, artifact_rows)
        paths.append(path)
    summary_path = args.output_dir / "summary_v1.json"
    _atomic_write(
        summary_path,
        json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
    )
    paths.append(summary_path)
    ledger = {
        "schema": "gis_recommend.hash_ledger.v1",
        "inputs": {
            str(path): {
                "sha256": _sha256(path),
                "bytes": path.stat().st_size,
            }
            for path in (args.candidate_units, args.authority_decisions)
        },
        "artifacts": {
            path.name: {"sha256": _sha256(path), "bytes": path.stat().st_size}
            for path in paths
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
