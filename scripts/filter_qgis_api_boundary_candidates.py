#!/usr/bin/env python3
"""Apply reviewed fail-closed boundary filters to a frozen API replay."""

from __future__ import annotations

import argparse
import hashlib
import json
import tempfile
from pathlib import Path
from typing import Any

from gis_recommend.data.qgis_api_task_boundaries import (
    TERMINAL_STATIC_CALLS,
    _control_paths_compatible,
)


POST_FILTER_RULE_ID = "adjacent-same-receiver-different-payload-v1"
EXCLUSION_REASON = "adjacent_same_receiver_different_payload_terminal"


def _adjacent_terminal(
    candidate: dict[str, Any], deferred_units: list[dict[str, Any]]
) -> dict[str, Any] | None:
    terminal = next(
        step for step in candidate["steps"] if step["terminal_evidence"]
    )
    if terminal["call_name"].lower() in TERMINAL_STATIC_CALLS:
        return None
    produced_names = {
        name for step in candidate["steps"] for name in step["produced_names"]
    }
    for deferred in deferred_units:
        if deferred["lexical_scope"] != candidate["lexical_scope"]:
            continue
        for step in deferred["steps"]:
            if (
                step["terminal_evidence"]
                and terminal["line_end"] < step["line_start"] <= terminal["line_end"] + 8
                and step["receiver"] == terminal["receiver"]
                and not (produced_names & set(step["consumed_names"]))
                and _control_paths_compatible(
                    terminal.get("control_path", []), step.get("control_path", [])
                )
            ):
                return step
    return None


def filter_candidates(
    source_rows: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    eligible: list[dict[str, Any]] = []
    excluded: list[dict[str, Any]] = []
    for source_row in source_rows:
        deferred_units = source_row.get("deferred_units") or []
        for candidate in source_row.get("candidate_units") or []:
            adjacent = _adjacent_terminal(candidate, deferred_units)
            if adjacent is None:
                eligible.append(
                    {
                        **candidate,
                        "boundary_post_filter_rule_id": POST_FILTER_RULE_ID,
                        "training_admission": "not_granted_l3_intake_only",
                        "training_row_emitted": False,
                    }
                )
                continue
            excluded.append(
                {
                    **candidate,
                    "boundary_status": "deferred",
                    "boundary_post_filter_rule_id": POST_FILTER_RULE_ID,
                    "reason": EXCLUSION_REASON,
                    "adjacent_terminal_evidence": adjacent,
                    "training_admission": "not_granted_boundary_filter",
                    "training_row_emitted": False,
                }
            )
    return eligible, excluded


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


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    content = "".join(
        json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows
    )
    _atomic_write(path, content)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-replay", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()

    source_rows = _read_jsonl(args.source_replay)
    eligible, excluded = filter_candidates(source_rows)
    eligible_path = args.output_dir / "l3_intake_candidate_units_v1.jsonl"
    excluded_path = args.output_dir / "excluded_candidate_units_v1.jsonl"
    summary_path = args.output_dir / "summary_v1.json"
    _write_jsonl(eligible_path, eligible)
    _write_jsonl(excluded_path, excluded)
    summary = {
        "schema": "gis_recommend.qgis_api_boundary_post_filter_summary.v1",
        "post_filter_rule_id": POST_FILTER_RULE_ID,
        "source_replay_rows": len(source_rows),
        "input_candidate_units": len(eligible) + len(excluded),
        "l3_intake_candidate_units": len(eligible),
        "excluded_candidate_units": len(excluded),
        "excluded_reason_counts": {EXCLUSION_REASON: len(excluded)},
        "source_verification": "carried_from_frozen_sha256_verified_replay",
        "l3_mapping_rows": 0,
        "description_fidelity_rows": 0,
        "dedup_rows": 0,
        "training_admission": "not_granted_boundary_filter_only",
        "training_rows_emitted": 0,
        "validation_eligible": False,
        "test_eligible": False,
        "production_merge": "not_granted",
    }
    _atomic_write(
        summary_path,
        json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
    )
    artifacts = [eligible_path, excluded_path, summary_path]
    ledger = {
        "schema": "gis_recommend.hash_ledger.v1",
        "inputs": {
            args.source_replay.name: {
                "path": str(args.source_replay),
                "bytes": args.source_replay.stat().st_size,
                "sha256": _sha256(args.source_replay),
            }
        },
        "artifacts": {
            path.name: {"bytes": path.stat().st_size, "sha256": _sha256(path)}
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
