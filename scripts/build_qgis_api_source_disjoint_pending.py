#!/usr/bin/env python3
"""Freeze pending source-disjoint packets for QGIS API boundary review."""

from __future__ import annotations

import argparse
import hashlib
import json
import tempfile
from collections import defaultdict
from pathlib import Path
from typing import Any, Iterable

from scripts.build_qgis_api_source_disjoint_gate import (
    assign_alias_groups,
    rebase_source_rows,
    split_alias_groups,
)


HUMAN_FIELDS = (
    "task_boundary_decision",
    "dependency_decision",
    "terminal_decision",
    "failure_labels",
    "reviewer_notes",
)


def _with_context(row: dict[str, Any]) -> dict[str, Any]:
    lines = Path(str(row["source_path"])).read_text(
        encoding="utf-8-sig", errors="replace"
    ).splitlines()
    evidence = sorted(
        list(row.get("upstream_calls") or []) + list(row.get("steps") or []),
        key=lambda item: (int(item["line_start"]), int(item["line_end"])),
    )
    raw_windows = [
        (
            max(1, int(item["line_start"]) - 4),
            min(len(lines), int(item["line_end"]) + 4),
        )
        for item in evidence
    ]
    windows: list[tuple[int, int]] = []
    if raw_windows and raw_windows[-1][1] - raw_windows[0][0] <= 200:
        windows.append((raw_windows[0][0], raw_windows[-1][1]))
    for start, end in ([] if windows else raw_windows):
        if windows and start <= windows[-1][1] + 1:
            windows[-1] = (windows[-1][0], max(windows[-1][1], end))
        else:
            windows.append((start, end))
    return {
        **row,
        "source_windows": [
            {
                "line_start": start,
                "line_end": end,
                "text": "\n".join(lines[start - 1 : end]),
            }
            for start, end in windows
        ],
    }


def build_pending(
    rows: list[dict[str, Any]], *, seed: int
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    rebased, source_summary = rebase_source_rows(rows)
    grouped, alias_summary = assign_alias_groups(rebased)
    calibration, holdout, split_summary = split_alias_groups(grouped, seed=seed)

    def pending(split_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        values = []
        for row in split_rows:
            annotated = {
                **_with_context(row),
                "schema": "gis_recommend.qgis_api_source_disjoint_pending_review.v1",
                "review_status": "pending_human_boundary_review",
                "description_fidelity": "not_started",
                "deduplication": "not_started",
                "training_admission": "not_granted_pending_boundary_review",
                "training_row_emitted": False,
                "validation_eligible": False,
                "test_eligible": False,
                "production_merge": "not_granted",
            }
            annotated.update({field: "" for field in HUMAN_FIELDS})
            values.append(annotated)
        return values

    calibration = pending(calibration)
    holdout = pending(holdout)
    summary = {
        "schema": "gis_recommend.qgis_api_source_disjoint_pending_summary.v1",
        "source_rebase": source_summary,
        "alias_clustering": alias_summary,
        "split": split_summary,
        "review_status": "pending_human_boundary_review",
        "l3_mapping_rows": 0,
        "description_fidelity_rows": 0,
        "dedup_rows": 0,
        "training_rows_emitted": 0,
        "training_admission": "not_granted_pending_boundary_review",
    }
    return calibration, holdout, summary


def _authority_ledger(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[str(row["source_authority_key"])].append(row)
    return [
        {
            "schema": "gis_recommend.qgis_api_source_disjoint_pending_authority.v1",
            "source_authority_key": authority,
            "declared_source_authority_keys": sorted(
                {str(row["declared_source_authority_key"]) for row in members}
            ),
            "candidate_ids": sorted(str(row["candidate_id"]) for row in members),
            "unit_ids": sorted({str(row["unit_id"]) for row in members}),
            "candidate_unit_count": len(members),
            "calibration_alias_group_id": str(
                members[0]["calibration_alias_group_id"]
            ),
            "review_split": str(members[0]["review_split"]),
            "review_status": "pending_human_boundary_review",
            "training_row_emitted": False,
        }
        for authority, members in sorted(grouped.items())
    ]


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
    parser.add_argument("--candidate-units", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--seed", type=int, default=20260730)
    args = parser.parse_args()
    if args.output_dir.exists() and any(args.output_dir.iterdir()):
        raise ValueError(f"output directory is not empty: {args.output_dir}")
    calibration, holdout, summary = build_pending(
        _read_jsonl(args.candidate_units), seed=args.seed
    )
    authority_ledger = _authority_ledger(calibration + holdout)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    outputs = {
        "calibration_pending_v1.jsonl": calibration,
        "frozen_holdout_pending_v1.jsonl": holdout,
        "source_authority_ledger_v1.jsonl": authority_ledger,
    }
    paths = []
    for name, rows in outputs.items():
        path = args.output_dir / name
        _write_jsonl(path, rows)
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
            "candidate_units": {
                "path": str(args.candidate_units),
                "sha256": _sha256(args.candidate_units),
            }
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
