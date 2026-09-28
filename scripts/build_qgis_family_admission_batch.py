#!/usr/bin/env python3
"""Run one four-layer Gold/Silver candidate admission pass over family lanes."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

try:
    from .build_qgis_workflow_gold_silver import classify, read_jsonl
except ImportError:
    from build_qgis_workflow_gold_silver import classify, read_jsonl


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--candidates", type=Path, action="append", required=True)
    parser.add_argument("--baseline", type=Path, action="append", required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    candidates = [row for path in args.candidates for row in read_jsonl(path)]
    baselines = [row for path in args.baseline for row in read_jsonl(path)]
    output, summary = classify(candidates, baselines)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    ledger = args.output_dir / "gold_silver_reject_ledger_v1.jsonl"
    summary_path = args.output_dir / "summary_v1.json"
    ledger.write_text("".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in output), encoding="utf-8")
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    inputs = [*args.candidates, *args.baseline]
    hashes = {
        "schema": "gis_recommend.hash_ledger.v1",
        "inputs": {path.name: hashlib.sha256(path.read_bytes()).hexdigest() for path in inputs},
        "artifacts": {path.name: hashlib.sha256(path.read_bytes()).hexdigest() for path in (ledger, summary_path)},
    }
    (args.output_dir / "hash_ledger_v1.json").write_text(json.dumps(hashes, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
