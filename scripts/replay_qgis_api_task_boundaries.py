#!/usr/bin/env python3
"""Replay conservative low-level PyQGIS task boundaries on source authorities."""

from __future__ import annotations

import argparse
import hashlib
import json
import tempfile
import warnings
from collections import Counter
from pathlib import Path
from typing import Any, Iterable

from gis_recommend.data.qgis_api_task_boundaries import (
    BOUNDARY_RULE_ID,
    extract_task_boundaries,
)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def replay_source_row(row: dict[str, Any]) -> dict[str, Any]:
    path = Path(str(row.get("source_path") or ""))
    if not path.is_file():
        raise ValueError(f"source file missing: {path}")
    actual_sha = _sha256(path)
    if actual_sha != str(row.get("source_sha256") or ""):
        raise ValueError(f"source SHA mismatch: {path}")
    if not str(row.get("normalized_source_body_sha256") or ""):
        raise ValueError(f"normalized source authority missing: {path}")
    source_text = path.read_text(encoding="utf-8-sig", errors="replace")
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", SyntaxWarning)
        boundaries = extract_task_boundaries(source_text)
    identity = {
        "record_id": str(row["record_id"]),
        "source_path": str(path),
        "relative_path": str(row.get("relative_path") or ""),
        "source_root_id": str(row.get("source_root_id") or ""),
        "source_sha256": actual_sha,
        "source_authority_key": str(row["source_authority_key"]),
        "normalized_source_body_sha256": str(row["normalized_source_body_sha256"]),
    }
    candidates = []
    for unit in boundaries["candidate_units"]:
        candidate_id = hashlib.sha256(
            f"{identity['record_id']}|{unit['unit_id']}".encode("utf-8")
        ).hexdigest()
        candidates.append(
            {
                **unit,
                **identity,
                "schema": "gis_recommend.qgis_api_task_boundary_candidate.v1",
                "candidate_id": candidate_id,
                "candidate_l3_sequence": [],
                "description_fidelity": "not_started",
                "deduplication": "not_started",
                "training_admission": "not_granted_task_boundary_only",
                "training_row_emitted": False,
                "validation_eligible": False,
                "test_eligible": False,
                "production_merge": "not_granted",
            }
        )
    return {
        **identity,
        "schema": "gis_recommend.qgis_api_task_boundary_source_replay.v1",
        "source_verification": "verified_sha256",
        "parse_status": "parsed",
        "semantic_step_count": len(boundaries["semantic_steps"]),
        "candidate_unit_count": len(candidates),
        "deferred_terminal_unit_count": len(boundaries["deferred_units"]),
        "candidate_units": candidates,
        "deferred_units": boundaries["deferred_units"],
        "candidate_l3_sequence": [],
        "training_admission": "not_granted_task_boundary_replay_only",
        "training_rows_emitted": 0,
        "validation_eligible": False,
        "test_eligible": False,
        "production_merge": "not_granted",
    }


def unavailable_source_row(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "record_id": str(row["record_id"]),
        "source_path": str(row.get("source_path") or ""),
        "relative_path": str(row.get("relative_path") or ""),
        "source_root_id": str(row.get("source_root_id") or ""),
        "source_sha256": str(row.get("source_sha256") or ""),
        "source_authority_key": str(row["source_authority_key"]),
        "normalized_source_body_sha256": str(row["normalized_source_body_sha256"]),
        "schema": "gis_recommend.qgis_api_task_boundary_source_replay.v1",
        "source_verification": "source_file_missing",
        "parse_status": "not_attempted_source_missing",
        "semantic_step_count": 0,
        "candidate_unit_count": 0,
        "deferred_terminal_unit_count": 0,
        "candidate_units": [],
        "deferred_units": [],
        "candidate_l3_sequence": [],
        "training_admission": "not_granted_source_unavailable",
        "training_rows_emitted": 0,
        "validation_eligible": False,
        "test_eligible": False,
        "production_merge": "not_granted",
    }


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    with path.open(encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


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
    parser.add_argument("--authority-manifest", type=Path, required=True)
    parser.add_argument("--selection-manifest", type=Path)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--expected-rows", type=int, default=39386)
    parser.add_argument("--retain-unavailable-sources", action="store_true")
    args = parser.parse_args()

    authorities = _read_jsonl(args.authority_manifest)
    selection_rows: list[dict[str, Any]] = []
    if args.selection_manifest is not None:
        selection_rows = _read_jsonl(args.selection_manifest)
        selected_ids = {str(row["record_id"]) for row in selection_rows}
        authorities = [
            row for row in authorities if str(row["record_id"]) in selected_ids
        ]
        if len(authorities) != len(selected_ids):
            raise ValueError("selection manifest does not join exactly to authority rows")
    if len(authorities) != args.expected_rows:
        raise ValueError(
            f"authority row count {len(authorities)} != expected {args.expected_rows}"
        )
    if len({str(row["record_id"]) for row in authorities}) != len(authorities):
        raise ValueError("authority record_id values must be unique")

    replay_rows = [
        (
            unavailable_source_row(row)
            if args.retain_unavailable_sources
            and not Path(str(row.get("source_path") or "")).is_file()
            else replay_source_row(row)
        )
        for row in authorities
    ]
    candidate_units = [
        unit for replay in replay_rows for unit in replay["candidate_units"]
    ]
    if any(unit["training_row_emitted"] for unit in candidate_units):
        raise ValueError("task-boundary replay cannot emit training rows")
    source_status = Counter(
        (
            "source_unavailable"
            if row["source_verification"] == "source_file_missing"
            else "candidate_source"
            if row["candidate_unit_count"]
            else "deferred_source"
        )
        for row in replay_rows
    )
    family_support = Counter(
        family for unit in candidate_units for family in unit["pattern_names"]
    )
    summary = {
        "schema": "gis_recommend.qgis_api_task_boundary_replay_summary.v1",
        "source_rows": len(replay_rows),
        "verified_source_sha256": sum(
            row["source_verification"] == "verified_sha256" for row in replay_rows
        ),
        "source_unavailable": sum(
            row["source_verification"] == "source_file_missing" for row in replay_rows
        ),
        "source_unavailable_authorities": len(
            {
                row["source_authority_key"]
                for row in replay_rows
                if row["source_verification"] == "source_file_missing"
            }
        ),
        "unique_record_ids": len({row["record_id"] for row in replay_rows}),
        "unique_source_sha256": len({row["source_sha256"] for row in replay_rows}),
        "unique_normalized_source_bodies": len(
            {row["normalized_source_body_sha256"] for row in replay_rows}
        ),
        "source_status_counts": dict(sorted(source_status.items())),
        "semantic_steps": sum(row["semantic_step_count"] for row in replay_rows),
        "candidate_units": len(candidate_units),
        "candidate_source_authorities": len(
            {unit["source_authority_key"] for unit in candidate_units}
        ),
        "deferred_terminal_units": sum(
            row["deferred_terminal_unit_count"] for row in replay_rows
        ),
        "family_candidate_support": dict(sorted(family_support.items())),
        "boundary_rule_id": BOUNDARY_RULE_ID,
        "task_boundary_calibration": "pending_source_disjoint_review",
        "l3_mapping_rows": 0,
        "description_fidelity_rows": 0,
        "dedup_rows": 0,
        "training_rows_emitted": 0,
        "training_admission": "not_granted_task_boundary_replay_only",
        "validation_eligible": False,
        "test_eligible": False,
        "production_merge": "not_granted",
        "llm_called": False,
    }

    args.output_dir.mkdir(parents=True, exist_ok=True)
    replay_path = args.output_dir / "source_replay_v1.jsonl"
    units_path = args.output_dir / "candidate_units_v1.jsonl"
    summary_path = args.output_dir / "summary_v1.json"
    _write_jsonl(replay_path, replay_rows)
    _write_jsonl(units_path, candidate_units)
    _atomic_write(
        summary_path,
        json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
    )
    ledger = {
        "schema": "gis_recommend.hash_ledger.v1",
        "inputs": {
            "authority_manifest": {
                "path": str(args.authority_manifest),
                "sha256": _sha256(args.authority_manifest),
                "bytes": args.authority_manifest.stat().st_size,
            },
            **(
                {
                    "selection_manifest": {
                        "path": str(args.selection_manifest),
                        "sha256": _sha256(args.selection_manifest),
                        "bytes": args.selection_manifest.stat().st_size,
                    }
                }
                if args.selection_manifest is not None
                else {}
            ),
        },
        "artifacts": {
            path.name: {"sha256": _sha256(path), "bytes": path.stat().st_size}
            for path in (replay_path, units_path, summary_path)
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
