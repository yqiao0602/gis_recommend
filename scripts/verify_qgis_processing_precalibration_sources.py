#!/usr/bin/env python3
"""SHA-verify selected Processing sources and attach normalized-body authority."""

from __future__ import annotations

import argparse
import hashlib
import json
import tempfile
from pathlib import Path
from typing import Any

from gis_recommend.data.qgis_source_authority import source_authority


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify(rows: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, str]]]:
    verified: list[dict[str, Any]] = []
    failures: list[dict[str, str]] = []
    for source in rows:
        row = dict(source)
        record_id = str(row.get("record_id") or "")
        expected = str(row.get("source_sha256") or "")
        path = Path(str(row.get("source_path") or ""))
        if not record_id or not expected or not path.is_file():
            failures.append({"record_id": record_id, "reason": "source_file_missing"})
            continue
        if _sha256(path) != expected:
            failures.append({"record_id": record_id, "reason": "source_sha256_mismatch"})
            continue
        authority = source_authority(path, source_sha256=expected)
        if not authority["normalized_source_body_sha256"]:
            failures.append({"record_id": record_id, "reason": "normalized_source_body_missing"})
            continue
        row.update(authority)
        row["precalibration_source_status"] = "server_sha_and_normalized_body_verified"
        verified.append(row)
    return verified, failures


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    content = "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", newline="", dir=path.parent, delete=False) as handle:
        handle.write(content)
        temporary = Path(handle.name)
    temporary.replace(path)


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", newline="", dir=path.parent, delete=False) as handle:
        json.dump(value, handle, ensure_ascii=False, indent=2, sort_keys=True)
        handle.write("\n")
        temporary = Path(handle.name)
    temporary.replace(path)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--verified-output", type=Path, required=True)
    parser.add_argument("--failure-output", type=Path, required=True)
    parser.add_argument("--summary-output", type=Path, required=True)
    args = parser.parse_args()
    rows = _read_jsonl(args.input)
    verified, failures = verify(rows)
    _write_jsonl(args.verified_output, verified)
    _write_json(args.failure_output, failures)
    _write_json(
        args.summary_output,
        {
            "schema": "gis_recommend.qgis_processing_precalibration_source_verification.v1",
            "input_rows": len(rows),
            "verified_rows": len(verified),
            "failure_rows": len(failures),
            "normalized_source_body_authorities": len(
                {row["normalized_source_body_sha256"] for row in verified}
            ),
            "training_rows_emitted": 0,
            "training_admission": "not_granted_source_verification_only",
            "validation_eligible": False,
            "test_eligible": False,
            "production_merge": "not_granted",
            "llm_called": False,
        },
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
