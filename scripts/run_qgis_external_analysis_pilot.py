#!/usr/bin/env python3
"""Build deterministic QGIS external-analysis evidence deltas and gate metrics."""

# Schema validation intentionally exposes one ValueError contract for bad payloads.
# ruff: noqa: TRY004

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from gis_recommend.data.qgis_external_pilot_comparison import (
    compare_evidence,
    evaluate_hard_gate,
    evaluate_promotion_gate,
)


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return value


def _read_jsonl_by_id(path: Path) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for line_number, line in enumerate(
        path.read_text(encoding="utf-8").splitlines(), start=1
    ):
        if not line.strip():
            continue
        row = json.loads(line)
        if not isinstance(row, dict):
            raise ValueError(f"{path}:{line_number} must contain an object")
        record_id = str(row.get("record_id") or "")
        if not record_id:
            raise ValueError(f"{path}:{line_number} lacks record_id")
        if record_id in result:
            raise ValueError(f"{path} contains duplicate record_id {record_id}")
        result[record_id] = row
    return result


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    partial = path.with_suffix(path.suffix + ".partial")
    partial.write_text(
        json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        + "\n",
        encoding="utf-8",
        newline="\n",
    )
    partial.replace(path)


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    partial = path.with_suffix(path.suffix + ".partial")
    partial.write_text(
        "".join(
            json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
            + "\n"
            for row in rows
        ),
        encoding="utf-8",
        newline="\n",
    )
    partial.replace(path)


def run_comparison(
    *,
    authority_path: Path,
    joern_path: Path,
    registry_path: Path,
    datatrove_path: Path,
    promotion_path: Path,
    output_dir: Path,
    expected_source_count: int,
) -> dict[str, Any]:
    authority = _read_jsonl_by_id(authority_path)
    joern = _read_jsonl_by_id(joern_path)
    if set(authority) != set(joern):
        raise ValueError(
            "authority and Joern record sets differ: "
            f"authority_only={sorted(set(authority) - set(joern))} "
            f"joern_only={sorted(set(joern) - set(authority))}"
        )
    comparisons = [
        compare_evidence(authority=authority[record_id], joern=joern[record_id])
        for record_id in sorted(authority)
    ]
    registry = _read_json(registry_path)
    fallback_count = int(registry.get("fallback_count") or 0)
    if "fallback_count" not in registry:
        fallback_count = sum(
            bool(row.get("fallback_used"))
            for row in registry.get("operators", [])
            if isinstance(row, dict)
        )
    datatrove = _read_json(datatrove_path)
    promotion = _read_json(promotion_path)
    families = promotion.get("families", [])
    if not isinstance(families, list):
        raise ValueError("promotion families must be a list")

    hard_gate = evaluate_hard_gate(
        comparisons,
        expected_source_count=expected_source_count,
        registry_fallback_count=fallback_count,
        datatrove_report=datatrove,
    )
    promotion_gate = evaluate_promotion_gate(families)
    delta_counts = hard_gate["metrics"]["delta_status_counts"]
    checkpoint_novelty_count = int(delta_counts.get("joern_only_partial", 0)) + int(
        delta_counts.get("joern_only_complete", 0)
    )
    rows = [
        {
            "schema": "gis_recommend.qgis_external_pilot_evidence_delta.v1",
            **row._asdict(),
            "novelty_kinds": list(row.novelty_kinds),
            "training_admission": "not_granted_external_analysis_pilot_only",
            "training_row_emitted": False,
        }
        for row in comparisons
    ]
    summary = {
        "schema": "gis_recommend.qgis_external_pilot_comparison_summary.v1",
        "record_count": len(rows),
        "hard_gate": hard_gate,
        "promotion_gate": promotion_gate,
        "checkpoint_novelty_count": checkpoint_novelty_count,
        "checkpoint_novelty_passed": checkpoint_novelty_count > 0,
        "proceed_to_200_source_pilot": bool(
            hard_gate["passed"] and checkpoint_novelty_count > 0
        ),
        "training_admission": "not_granted_external_analysis_pilot_only",
        "training_rows_emitted": 0,
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    _write_jsonl(output_dir / "comparison_rows_v1.jsonl", rows)
    _write_json(output_dir / "comparison_summary_v1.json", summary)
    return summary


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pilot-root", type=Path)
    parser.add_argument("--stage")
    parser.add_argument("--authority", type=Path)
    parser.add_argument("--joern", type=Path)
    parser.add_argument("--registry", type=Path)
    parser.add_argument("--datatrove", type=Path)
    parser.add_argument("--promotion", type=Path)
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--expected-source-count", type=int)
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    if args.pilot_root and args.stage:
        stage_root = args.pilot_root / "stages" / args.stage
        authority = args.authority or stage_root / "authority_baseline.jsonl"
        joern = args.joern or stage_root / "joern_normalized.jsonl"
        registry = args.registry or stage_root / "registry_comparison.json"
        datatrove = args.datatrove or stage_root / "datatrove_normalized.json"
        promotion = args.promotion or stage_root / "promotion_families.json"
        output_dir = args.output_dir or stage_root / "comparison"
        expected_source_count = args.expected_source_count
        if expected_source_count is None:
            expected_source_count = 40 if args.stage == "checkpoint-40" else 200
    else:
        required = {
            "authority": args.authority,
            "joern": args.joern,
            "registry": args.registry,
            "datatrove": args.datatrove,
            "promotion": args.promotion,
            "output_dir": args.output_dir,
        }
        missing = sorted(name for name, value in required.items() if value is None)
        if missing:
            raise SystemExit(f"missing arguments: {', '.join(missing)}")
        authority = args.authority
        joern = args.joern
        registry = args.registry
        datatrove = args.datatrove
        promotion = args.promotion
        output_dir = args.output_dir
        if args.expected_source_count is None:
            raise SystemExit("missing arguments: expected-source-count")
        expected_source_count = args.expected_source_count
    run_comparison(
        authority_path=authority,
        joern_path=joern,
        registry_path=registry,
        datatrove_path=datatrove,
        promotion_path=promotion,
        output_dir=output_dir,
        expected_source_count=expected_source_count,
    )


if __name__ == "__main__":
    main()
