#!/usr/bin/env python3
"""Repair source-root provenance on the full API steps manifest by exact ID join."""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any


def _read(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def repair(source_manifest: Path, steps_manifest: Path, output_dir: Path) -> dict[str, Any]:
    sources = _read(source_manifest)
    steps = _read(steps_manifest)
    by_id = {str(row["record_id"]): row for row in sources}
    if len(sources) != 39386 or len(by_id) != 39386:
        raise ValueError("source authority IDs are not unique")
    repaired = []
    for row in steps:
        source = by_id.get(str(row.get("record_id")))
        if source is None:
            raise ValueError(f"steps row lacks source authority: {row.get('record_id')}")
        for field in ("source_path", "source_sha256"):
            if row.get(field) != source.get(field):
                raise ValueError(f"source identity mismatch for {row.get('record_id')}: {field}")
        repaired.append({
            **row,
            "schema": "gis_recommend.qgis_api_source_steps.v2",
            "source_root_id": source["source_root_id"],
            "relative_path": source["relative_path"],
            "provenance_repair": "exact_record_id_source_path_source_sha_join",
        })
    if len(repaired) != 39386 or any(not row["source_root_id"] for row in repaired):
        raise ValueError("repaired API steps authority is incomplete")
    output_dir.mkdir(parents=True, exist_ok=True)
    output = output_dir / "api_steps_manifest_v2.jsonl"
    output.write_text("".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in repaired), encoding="utf-8")
    summary = {
        "schema": "gis_recommend.qgis_api_steps_provenance_repair_summary.v1",
        "input_rows": len(steps),
        "repaired_rows": len(repaired),
        "unique_record_ids": len({row["record_id"] for row in repaired}),
        "source_root_counts": dict(sorted(Counter(row["source_root_id"] for row in repaired).items())),
        "training_rows_emitted": 0,
        "training_admission": "not_granted_provenance_repair_only",
        "production_merge": "not_granted",
    }
    summary_path = output_dir / "provenance_repair_summary_v1.json"
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (output_dir / "provenance_repair_hash_ledger_v1.json").write_text(json.dumps({
        "schema": "gis_recommend.hash_ledger.v1",
        "inputs": {
            "source_manifest": {"path": str(source_manifest), "sha256": _sha(source_manifest)},
            "steps_manifest": {"path": str(steps_manifest), "sha256": _sha(steps_manifest)},
        },
        "artifacts": {output.name: _sha(output), summary_path.name: _sha(summary_path)},
    }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return summary


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-manifest", type=Path, required=True)
    parser.add_argument("--steps-manifest", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(repair(args.source_manifest, args.steps_manifest, args.output_dir), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
