#!/usr/bin/env python3
"""Run Asset Miner in bounded, resumable manifest shards.

Each shard is written atomically with a completion marker.  The merge command
only consumes completed shard ledgers, so an interrupted full-pool scan can be
resumed without re-reading finished source files.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
MINER = ROOT / "scripts" / "mine_qgis_assets.py"


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _atomic(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=path.parent, delete=False) as handle:
        handle.write(text)
        temporary = Path(handle.name)
    temporary.replace(path)


def _write_manifest(path: Path, rows: list[dict[str, Any]]) -> None:
    _atomic(path, "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows))


def _run_shards(args: argparse.Namespace) -> int:
    processing = _load(args.processing_manifest)
    api = _load(args.api_manifest)
    shards: list[tuple[str, list[dict[str, Any]]]] = []
    for pool, rows in (("processing", processing), ("api", api)):
        for start in range(0, len(rows), args.shard_size):
            shards.append((pool, rows[start : start + args.shard_size]))
    args.output_dir.mkdir(parents=True, exist_ok=True)
    manifest_dir = args.output_dir / "manifests"
    manifest_dir.mkdir(exist_ok=True)
    for index, (pool, rows) in enumerate(shards):
        stem = f"{index:05d}_{pool}"
        shard_dir = args.output_dir / stem
        done = shard_dir / "DONE.json"
        if done.exists() and not args.force:
            continue
        shard_dir.mkdir(exist_ok=True)
        manifest = manifest_dir / f"{stem}.jsonl"
        _write_manifest(manifest, rows)
        command = [
            sys.executable,
            str(args.miner),
            "--processing-manifest", str(manifest if pool == "processing" else args.empty_manifest),
            "--api-manifest", str(manifest if pool == "api" else args.empty_manifest),
            "--output-dir", str(shard_dir),
            "--skip-role-classification",
        ]
        for root in args.source_root:
            command.extend(["--source-root", root])
        result = subprocess.run(command, check=False)
        if result.returncode != 0:
            return result.returncode
        _atomic(done, json.dumps({"schema": "gis_recommend.qgis_asset_miner_shard_done.v1", "pool": pool, "rows": len(rows), "manifest_sha256": _sha(manifest)}, indent=2) + "\n")
    return 0


def _merge(args: argparse.Namespace) -> int:
    rows: list[dict[str, Any]] = []
    shards = sorted(path for path in args.output_dir.iterdir() if path.is_dir() and (path / "DONE.json").is_file())
    for shard in shards:
        ledger = shard / "qgis_asset_miner_v1.jsonl"
        if not ledger.is_file():
            continue
        rows.extend(_load(ledger))
    summary = {
        "schema": "gis_recommend.qgis_asset_miner.v1.sharded_summary",
        "shards_completed": len(shards),
        "rows": len(rows),
        "status_counts": {},
        "asset_type_counts": {},
        "training_rows_emitted": 0,
        "training_admission": "not_granted_asset_miner_v1",
    }
    from collections import Counter
    summary["status_counts"] = dict(sorted(Counter(row.get("status") for row in rows).items()))
    summary["asset_type_counts"] = dict(sorted(Counter(row.get("asset_type") for row in rows).items()))
    ledger = args.output_dir / "qgis_asset_miner_sharded_v1.jsonl"
    _atomic(ledger, "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows))
    summary_path = args.output_dir / "sharded_summary_v1.json"
    _atomic(summary_path, json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
    _atomic(args.output_dir / "hash_ledger_v1.json", json.dumps({ledger.name: _sha(ledger), summary_path.name: _sha(summary_path)}, indent=2, sort_keys=True) + "\n")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    run = sub.add_parser("run")
    run.add_argument("--processing-manifest", type=Path, required=True)
    run.add_argument("--api-manifest", type=Path, required=True)
    run.add_argument("--empty-manifest", type=Path, required=True)
    run.add_argument("--source-root", action="append", required=True)
    run.add_argument("--output-dir", type=Path, required=True)
    run.add_argument("--miner", type=Path, default=MINER)
    run.add_argument("--shard-size", type=int, default=250)
    run.add_argument("--force", action="store_true")
    merge = sub.add_parser("merge")
    merge.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    return _run_shards(args) if args.command == "run" else _merge(args)


if __name__ == "__main__":
    raise SystemExit(main())
