#!/usr/bin/env python3
"""Replay stable111 Snap proposal split routes without granting training admission."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import tempfile
from pathlib import Path
from typing import Any, Iterable


ROOT = Path(__file__).resolve().parents[1]
for import_root in (ROOT, ROOT / "src", ROOT / "scripts"):
    if str(import_root) not in sys.path:
        sys.path.insert(0, str(import_root))

from build_qgis_split_subworkflow_units import build_split_units  # noqa: E402
from evaluate_qgis_stable118_structure_increment import (  # noqa: E402
    _fetch_ssh_source,
    materialize_sources,
)


DEFAULT_TRANSITIONS = (
    ROOT
    / "docs/reports/qgis_processing_snap_stable111_proposal_v1"
    / "dry_run_transitions_v1.jsonl"
)


def build_snap_split_units(
    transition_rows: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    parents = [
        row
        for row in transition_rows
        if row.get("action") == "split_subworkflow"
        and row.get("rule_id") == "split-disconnected-scopes-v1"
    ]
    rows, base_summary = build_split_units(parents)
    for row in rows:
        row["proposal_only"] = True
        row["taxonomy_profile"] = "stable111_snap_proposal_only"
        row["training_admission"] = "not_granted_taxonomy_proposal_only"
        row["training_row_emitted"] = False
    summary = {
        **base_summary,
        "schema": "gis_recommend.qgis_stable111_snap_split_replay.summary.v1",
        "taxonomy_profile": "stable111_snap_proposal_only",
        "training_rows_emitted": 0,
        "training_admission": "not_granted_taxonomy_proposal_only",
    }
    return rows, summary


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", newline="", dir=path.parent, delete=False) as handle:
        handle.write(text)
        temporary = Path(handle.name)
    temporary.replace(path)


def _jsonl(rows: Iterable[dict[str, Any]]) -> str:
    return "".join(json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n" for row in rows)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--transitions", type=Path, default=DEFAULT_TRANSITIONS)
    parser.add_argument("--ssh-host", default="qy@10.191.2.38")
    parser.add_argument("--remote-prefix-alias", action="append", default=[])
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    if args.output_dir.exists() and any(args.output_dir.iterdir()):
        raise ValueError(f"output directory is not empty: {args.output_dir}")
    aliases = []
    for value in args.remote_prefix_alias:
        old, separator, new = value.partition("=")
        if not separator or not old or not new:
            raise ValueError(f"invalid remote prefix alias: {value!r}")
        aliases.append((old, new))
    transitions = _read_jsonl(args.transitions)
    parents = [row for row in transitions if row.get("action") == "split_subworkflow"]
    with tempfile.TemporaryDirectory(prefix="qgis_snap_split_") as temp:
        materialized = materialize_sources(
            parents,
            Path(temp),
            lambda path: _fetch_ssh_source(args.ssh_host, path),
            path_aliases=aliases,
        )
        original_paths = {
            str(row["record_id"]): str(row.pop("source_path_original"))
            for row in materialized
        }
        rows, summary = build_snap_split_units(materialized)
    for row in rows:
        row["source_path"] = original_paths[str(row["parent_record_id"])]
    summary["source_sha_verified_parents"] = len(materialized)
    units_path = args.output_dir / "split_units_v1.jsonl"
    summary_path = args.output_dir / "summary_v1.json"
    _write(units_path, _jsonl(rows))
    _write(summary_path, json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
    hash_path = args.output_dir / "hash_ledger_v1.json"
    _write(
        hash_path,
        json.dumps(
            {
                "schema": "gis_recommend.hash_ledger.v1",
                "inputs": {str(args.transitions): _sha256(args.transitions)},
                "artifacts": {
                    units_path.name: _sha256(units_path),
                    summary_path.name: _sha256(summary_path),
                },
                "remote_prefix_aliases": [{"from": old, "to": new} for old, new in aliases],
            },
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n",
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
