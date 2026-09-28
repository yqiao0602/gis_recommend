#!/usr/bin/env python3
"""Build the full-population replay manifest for the setattributes family.

All priority units with producers=[] / mutations=['setattributes'] /
sink='addfeature' (575 source shas / 883 units per composite census v1).
Each manifest row anchors one sink window by source sha + sink line; the
same source may contribute multiple windows.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import tempfile
from collections import defaultdict
from collections.abc import Iterable
from pathlib import Path
from typing import Any

RULE_ID = "qgis-api-setattributes-full-population-selection-v1"


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
    parser.add_argument("--priority-units", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    if args.output_dir.exists() and any(args.output_dir.iterdir()):
        raise ValueError(f"output directory is not empty: {args.output_dir}")
    rows = _read_jsonl(args.priority_units)
    selected = [
        row
        for row in rows
        if not (row.get("producer_signature") or [])
        and tuple(sorted(row.get("mutation_signature") or [])) == ("setattributes",)
        and row.get("sink_signature") == "addfeature"
    ]
    if not selected:
        raise ValueError("no setattributes family units found")
    for row in selected:
        if len(str(row.get("source_sha256") or "")) != 64:
            raise ValueError("setattributes unit has invalid source SHA")
    source_shas = {row["source_sha256"] for row in selected}
    by_sha: dict[str, int] = defaultdict(int)
    for row in selected:
        by_sha[row["source_sha256"]] += 1
    manifest = [
        {
            **row,
            "schema": "gis_recommend.qgis_api_setattributes_full_population_manifest.v1",
            "setattributes_rule_id": RULE_ID,
            "selection_stage": "pre_source_replay",
            "training_admission": "not_granted_source_replay_only",
            "training_row_emitted": False,
            "validation_eligible": False,
            "test_eligible": False,
            "production_merge": "not_granted",
            "llm_called": False,
        }
        for row in selected
    ]
    args.output_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = args.output_dir / "setattributes_full_population_v1.jsonl"
    _write_jsonl(manifest_path, manifest)
    summary_path = args.output_dir / "summary_v1.json"
    _write_json(
        summary_path,
        {
            "schema": "gis_recommend.qgis_api_setattributes_full_population_selection_summary.v1",
            "setattributes_rule_id": RULE_ID,
            "selected_units": len(selected),
            "selected_source_sha_unique": len(source_shas),
            "windows_per_source_max": max(by_sha.values()) if by_sha else 0,
            "windows_per_source_distribution": dict(
                sorted(
                    {
                        count: sum(1 for value in by_sha.values() if value == count)
                        for count in sorted(set(by_sha.values()))
                    }.items()
                )
            ),
            "training_rows_emitted": 0,
            "training_admission": "not_granted_source_replay_only",
            "llm_called": False,
        },
    )
    _write_json(
        args.output_dir / "hash_ledger_v1.json",
        {
            "schema": "gis_recommend.hash_ledger.v1",
            "inputs": {
                "priority_units": {
                    "path": str(args.priority_units),
                    "sha256": _sha256(args.priority_units),
                }
            },
            "artifacts": {
                path.name: {"bytes": path.stat().st_size, "sha256": _sha256(path)}
                for path in (manifest_path, summary_path)
            },
        },
    )
    print((args.output_dir / "summary_v1.json").read_text(encoding="utf-8"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
