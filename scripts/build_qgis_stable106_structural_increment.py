#!/usr/bin/env python3
"""Isolate recovery/split routes newly unlocked by stable106."""

from __future__ import annotations

import argparse
import hashlib
import json
import tempfile
from collections import Counter
from pathlib import Path
from typing import Any, Iterable


TARGET_ACTIONS = {"recover_call_graph", "split_subworkflow"}


def _index(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for row in rows:
        record_id = str(row.get("record_id") or "")
        if not record_id or record_id in result:
            raise ValueError(f"missing or duplicate record_id: {record_id!r}")
        result[record_id] = row
    return result


def build_increment(
    stable106_rows: list[dict[str, Any]], authority_rows: list[dict[str, Any]]
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    stable106 = _index(stable106_rows)
    granted = {
        str(row.get("operator_id"))
        for row in authority_rows
        if row.get("mapping_admission") == "granted"
    }
    if len(granted) != 6:
        raise ValueError("expected six granted stable106 mappings")

    rows: list[dict[str, Any]] = []
    for record_id, current in stable106.items():
        action = str(current.get("action") or "")
        if action not in TARGET_ACTIONS or not granted.intersection(current.get("operator_ids") or []):
            continue
        row = dict(current)
        row.update(
            {
                "schema": "gis_recommend.qgis_stable106_structural_increment.v1",
                "baseline_action": "defer_mapping",
                "baseline_mapping_complete": False,
                "increment_reason": "stable106_mapping_authority_unlocked_route",
                "training_admission": "not_granted_pending_structural_replay",
                "training_row_emitted": False,
                "validation_eligible": False,
                "test_eligible": False,
                "production_merge": "not_granted",
            }
        )
        rows.append(row)
    rows.sort(key=lambda row: row["record_id"])
    counts = Counter(row["action"] for row in rows)
    summary = {
        "schema": "gis_recommend.qgis_stable106_structural_increment_summary.v1",
        "stable106_rows": len(stable106),
        "new_structural_rows": len(rows),
        "new_action_counts": dict(sorted(counts.items())),
        "unique_sources": len({row["source_sha256"] for row in rows}),
        "unique_chains": len({tuple(row.get("operator_ids") or []) for row in rows}),
        "training_admission": "not_granted_pending_structural_replay",
        "training_rows_emitted": 0,
        "next_gate": "server source replay through existing recovery and split builders",
    }
    return rows, summary


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _atomic_write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", newline="", dir=path.parent, delete=False) as handle:
        handle.write(text)
        temporary = Path(handle.name)
    temporary.replace(path)


def _write_json(path: Path, value: Any) -> None:
    _atomic_write(path, json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n")


def _write_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> None:
    _atomic_write(path, "".join(json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n" for row in rows))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stable106", type=Path, required=True)
    parser.add_argument("--authority", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    if args.output_dir.exists() and any(args.output_dir.iterdir()):
        raise ValueError(f"output directory is not empty: {args.output_dir}")
    rows, summary = build_increment(_read_jsonl(args.stable106), _read_jsonl(args.authority))
    manifest_path = args.output_dir / "structural_increment_manifest_v1.jsonl"
    summary_path = args.output_dir / "summary_v1.json"
    hash_path = args.output_dir / "hash_ledger_v1.json"
    _write_jsonl(manifest_path, rows)
    _write_json(summary_path, summary)
    _write_json(
        hash_path,
        {
            "schema": "gis_recommend.hash_ledger.v1",
            "inputs": {
                "stable106": {"path": str(args.stable106), "sha256": _sha256(args.stable106)},
                "authority": {"path": str(args.authority), "sha256": _sha256(args.authority)},
            },
            "artifacts": {
                manifest_path.name: _sha256(manifest_path),
                summary_path.name: _sha256(summary_path),
            },
        },
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
