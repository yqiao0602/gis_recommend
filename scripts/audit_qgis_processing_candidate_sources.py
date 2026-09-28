#!/usr/bin/env python3
"""Verify candidate source hashes and emit bounded source snippets for audit."""

from __future__ import annotations

import argparse
import hashlib
import json
import tempfile
from pathlib import Path
from typing import Any


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(value, list):
        content = "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in value)
    else:
        content = json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=path.parent, delete=False) as handle:
        handle.write(content)
        temporary = Path(handle.name)
    temporary.replace(path)


def audit(rows: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    seen: set[str] = set()
    evidence: list[dict[str, Any]] = []
    for row in rows:
        candidate_id = str(row.get("candidate_id") or "")
        if not candidate_id or candidate_id in seen:
            raise ValueError(f"missing or duplicate candidate_id: {candidate_id!r}")
        seen.add(candidate_id)
        source_path = Path(str(row.get("source_path") or ""))
        expected_sha = str(row.get("source_sha256") or "")
        sites = list(row.get("call_sites") or [])
        if not source_path.is_file():
            status, actual_sha, snippet = "missing", "", ""
        elif not expected_sha or _sha256(source_path) != expected_sha:
            status, actual_sha, snippet = "sha256_mismatch", _sha256(source_path), ""
        elif not sites:
            status, actual_sha, snippet = "call_sites_missing", expected_sha, ""
        else:
            lines = source_path.read_text(encoding="utf-8", errors="replace").splitlines()
            start = max(1, min(int(site["line_start"]) for site in sites) - 3)
            end = min(len(lines), max(int(site["line_end"]) for site in sites) + 3)
            snippet = "\n".join(f"{number:>6} | {lines[number - 1]}" for number in range(start, end + 1))
            status, actual_sha = "verified_sha256", expected_sha
        evidence.append(
            {
                "schema": "gis_recommend.qgis_processing_candidate_source_audit.v1",
                "candidate_id": candidate_id,
                "source_path": str(source_path),
                "expected_source_sha256": expected_sha,
                "actual_source_sha256": actual_sha,
                "source_verification": status,
                "source_span": {"call_sites": sites},
                "evidence_snippet": snippet,
                "training_admission": "not_granted_source_evidence_only",
                "training_row_emitted": False,
                "validation_eligible": False,
                "test_eligible": False,
                "production_merge": "not_granted",
            }
        )
    verified = sum(item["source_verification"] == "verified_sha256" for item in evidence)
    return evidence, {
        "schema": "gis_recommend.qgis_processing_candidate_source_audit.v1.summary",
        "input_rows": len(rows),
        "verified_sha256_rows": verified,
        "all_sources_verified": verified == len(rows),
        "training_rows_emitted": 0,
        "training_admission": "not_granted_source_evidence_only",
        "validation_eligible": False,
        "test_eligible": False,
        "production_merge": "not_granted",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    if args.output_dir.exists() and any(args.output_dir.iterdir()):
        raise ValueError(f"output directory is not empty: {args.output_dir}")
    evidence, summary = audit(_read_jsonl(args.manifest))
    _write(args.output_dir / "source_evidence_v1.jsonl", evidence)
    _write(args.output_dir / "summary_v1.json", summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0 if summary["all_sources_verified"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
