#!/usr/bin/env python3
"""Merge the 508 aggregate with all 31 isolated train-only rows into one package.

Isolated sources (all cross-pool-verified at export time):
  15-step 1 + polygon 3 + coordinate_transform 1 + rectangle 2
  + setattributes 3 + addattributes 21 (addattributes 19 + setattribute 2).

Merge gates: row count contract, no training-pair duplicates across pools,
source-SHA overlap is informational (different macros may share a source).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import tempfile
from collections import Counter
from collections.abc import Iterable
from pathlib import Path
from typing import Any

SCHEMA = "gis_recommend.qgis_train_only_aggregate_539.summary.v1"


def _pair_key(row: dict[str, Any]) -> str:
    codes = row.get("l3_code_sequence") or [
        code for code in row.get("l3_codes", []) if code not in {"<START>", "<END>"}
    ]
    return json.dumps(
        {"task_description": str(row.get("task_description") or "").strip(), "l3_code_sequence": codes},
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


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


def _write_json(path: Path, value: Any) -> None:
    _atomic_write(path, json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n")


def _write_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> None:
    _atomic_write(
        path,
        "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows),
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-aggregate", type=Path, required=True)
    parser.add_argument("--isolated", type=Path, action="append", required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--expected-isolated-rows", type=int, default=31)
    args = parser.parse_args()
    if args.output_dir.exists() and any(args.output_dir.iterdir()):
        raise ValueError(f"output directory is not empty: {args.output_dir}")
    base = _read_jsonl(args.base_aggregate)
    isolated: list[dict[str, Any]] = []
    for path in args.isolated:
        isolated.extend(_read_jsonl(path))
    if len(isolated) != args.expected_isolated_rows:
        raise ValueError(
            f"isolated rows {len(isolated)} != expected {args.expected_isolated_rows}"
        )
    merged = [*base, *isolated]
    base_pairs = {_pair_key(row) for row in base}
    iso_pairs = {_pair_key(row) for row in isolated}
    if base_pairs & iso_pairs:
        raise ValueError("training pair overlaps between base and isolated")
    if len(iso_pairs) != len(isolated):
        raise ValueError("training pair duplicates inside isolated")
    if len({row["source_sha256"] for row in merged}) != len(merged):
        duplicate_sources = {
            sha for sha, count in Counter(row["source_sha256"] for row in merged).items() if count > 1
        }
        # same-source different macros are legal; only report them
        duplicate_count = len(duplicate_sources)
    else:
        duplicate_count = 0
    args.output_dir.mkdir(parents=True, exist_ok=True)
    dataset = args.output_dir / "qgis_train_only_aggregate_539_v1.jsonl"
    _write_jsonl(dataset, merged)
    summary_path = args.output_dir / "summary_v1.json"
    _write_json(
        summary_path,
        {
            "schema": SCHEMA,
            "aggregate_rows": len(merged),
            "base_aggregate_rows": len(base),
            "isolated_rows": len(isolated),
            "isolated_breakdown": {
                "stable124_15step": 1,
                "polygon_geometry": 3,
                "coordinate_transform": 1,
                "rectangle_geometry": 2,
                "setattributes": 3,
                "addattributes": 19,
                "setattribute": 2,
            },
            "package_sha256": _sha256(dataset),
            "source_sha_rows_with_duplicates": duplicate_count,
            "training_pair_duplicates": 0,
            "training_admission": "granted_train_only_qgis_aggregate_539_v1",
            "training_run": False,
            "validation_eligible": False,
            "test_eligible": False,
            "production_merge": "not_granted",
            "supersedes": ["qgis_train_only_aggregate_508_v1"],
        },
    )
    _write_json(
        args.output_dir / "hash_ledger_v1.json",
        {
            "schema": "gis_recommend.hash_ledger.v1",
            "inputs": {
                "base": {"path": str(args.base_aggregate), "sha256": _sha256(args.base_aggregate)},
                **{
                    str(index): {"path": str(path), "sha256": _sha256(path)}
                    for index, path in enumerate(args.isolated, start=1)
                },
            },
            "artifacts": {
                path.name: {"bytes": path.stat().st_size, "sha256": _sha256(path)}
                for path in (dataset, summary_path)
            },
        },
    )
    print((args.output_dir / "summary_v1.json").read_text(encoding="utf-8"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
