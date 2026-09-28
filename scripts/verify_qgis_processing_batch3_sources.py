#!/usr/bin/env python3
"""Reverify Batch-3 calibration sources where the /home/yll authority is mounted."""

from __future__ import annotations

import argparse
import hashlib
import json
import tempfile
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = "gis_recommend.qgis_processing_batch3_source_verification.v1"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def verify(rows: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    verified: list[dict[str, Any]] = []
    seen_records: set[str] = set()
    for row in rows:
        record_id = str(row.get("record_id") or "")
        path = Path(str(row.get("source_path") or ""))
        expected = str(row.get("source_sha256") or "")
        if not record_id or record_id in seen_records or not expected:
            raise ValueError(f"invalid or duplicate manifest identity: {record_id!r}")
        seen_records.add(record_id)
        if not path.is_file():
            status = "missing"
            actual = ""
        else:
            actual = _sha256(path)
            status = "verified_sha256" if actual == expected else "sha256_mismatch"
        verified.append(
            {
                "schema": SCHEMA,
                "record_id": record_id,
                "source_authority_key": str(row.get("source_authority_key") or ""),
                "source_path": str(path),
                "expected_source_sha256": expected,
                "actual_source_sha256": actual,
                "source_verification": status,
                "training_admission": "not_granted_batch3_calibration_only",
                "training_row_emitted": False,
                "validation_eligible": False,
                "test_eligible": False,
                "production_merge": "not_granted",
            }
        )
    counts = Counter(row["source_verification"] for row in verified)
    summary = {
        "schema": f"{SCHEMA}.summary",
        "input_rows": len(rows),
        "verified_rows": counts["verified_sha256"],
        "status_counts": dict(sorted(counts.items())),
        "all_sources_verified": counts == {"verified_sha256": len(rows)},
        "training_admission": "not_granted_batch3_calibration_only",
        "training_rows_emitted": 0,
        "validation_eligible": False,
        "test_eligible": False,
        "production_merge": "not_granted",
    }
    return verified, summary


def _atomic_write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "w", encoding="utf-8", newline="", dir=path.parent, delete=False
    ) as handle:
        handle.write(text)
        temporary = Path(handle.name)
    temporary.replace(path)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    rows, summary = verify(_read_jsonl(args.manifest))
    output = args.output_dir / "batch3_source_verification_v1.jsonl"
    summary_path = args.output_dir / "source_verification_summary_v1.json"
    _atomic_write(
        output,
        "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows),
    )
    _atomic_write(summary_path, json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
    if not summary["all_sources_verified"]:
        raise SystemExit("Batch-3 source verification failed; no rule evaluation is allowed")
    print(json.dumps(summary, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
