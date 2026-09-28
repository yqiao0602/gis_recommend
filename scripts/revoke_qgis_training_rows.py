#!/usr/bin/env python3
"""Fail closed QGIS training rows invalidated by mapping exclusions."""
from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any, Iterable


def _operator_chain(row: dict[str, Any]) -> list[str]:
    for key in (
        "qgis_operator_chain",
        "operator_sequence",
        "chain",
        "operator_ids",
        "ordered_operator_ids",
    ):
        values = row.get(key)
        if isinstance(values, list):
            return [str(value).strip().lower() for value in values if str(value).strip()]
    return []


def filter_training_rows(
    rows: Iterable[dict[str, Any]], exclusions: dict[str, Any]
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    excluded = {str(value).strip().lower() for value in exclusions}
    kept: list[dict[str, Any]] = []
    revoked: list[dict[str, Any]] = []
    for row in rows:
        matches = sorted(set(_operator_chain(row)) & excluded)
        if not matches:
            kept.append(row)
            continue
        revoked.append(
            {
                "schema": "gis_recommend.qgis_training_revocation.v1",
                "action": "revoke_training_row",
                "reason": "semantic_mapping_exclusion",
                "sample_id": row.get("sample_id"),
                "record_id": row.get("record_id"),
                "source_sha256": row.get("source_sha256"),
                "original_training_admission": row.get("training_admission"),
                "excluded_operator_ids": matches,
                "excluded_mappings": {value: exclusions[value] for value in matches},
                "training_admission": "revoked_fail_closed_semantic_mapping",
                "validation_eligible": False,
                "test_eligible": False,
                "production_merge": "not_granted",
            }
        )
    return kept, revoked


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _write_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> None:
    path.write_text(
        "".join(
            json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"
            for row in rows
        ),
        encoding="utf-8",
    )


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--exclusion-authority", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    if args.output_dir.exists() and any(args.output_dir.iterdir()):
        raise ValueError(f"output directory is not empty: {args.output_dir}")
    args.output_dir.mkdir(parents=True, exist_ok=True)

    authority = json.loads(args.exclusion_authority.read_text(encoding="utf-8"))
    exclusions = authority.get("mapping_exclusions") or {}
    if not exclusions:
        raise ValueError("mapping exclusion authority is empty")
    rows = _read_jsonl(args.input)
    kept, revoked = filter_training_rows(rows, exclusions)

    corrected_path = args.output_dir / "train_only_corrected_v1.jsonl"
    revocation_path = args.output_dir / "revocation_ledger_v1.jsonl"
    summary_path = args.output_dir / "summary_v1.json"
    hash_path = args.output_dir / "hash_ledger_v1.json"
    _write_jsonl(corrected_path, kept)
    _write_jsonl(revocation_path, revoked)
    summary = {
        "schema": "gis_recommend.qgis_training_revocation_summary.v1",
        "input_rows": len(rows),
        "corrected_rows": len(kept),
        "revoked_rows": len(revoked),
        "revoked_operator_counts": dict(
            Counter(value for row in revoked for value in row["excluded_operator_ids"])
        ),
        "training_admission": "granted_train_only_after_semantic_revocation",
        "validation_eligible": False,
        "test_eligible": False,
        "production_merge": "not_granted",
    }
    summary_path.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    hash_path.write_text(
        json.dumps(
            {
                "schema": "gis_recommend.hash_ledger.v1",
                "inputs": {
                    str(args.input): _sha256(args.input),
                    str(args.exclusion_authority): _sha256(args.exclusion_authority),
                },
                "artifacts": {
                    path.name: _sha256(path)
                    for path in (corrected_path, revocation_path, summary_path)
                },
            },
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    print(json.dumps(summary, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
