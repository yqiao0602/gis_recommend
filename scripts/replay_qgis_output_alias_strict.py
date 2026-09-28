#!/usr/bin/env python3
"""Replay the promoted strict output-alias rule on the multistep pool."""

from __future__ import annotations

import argparse
import hashlib
import json
import tempfile
from collections import Counter
from pathlib import Path
from typing import Any

from scripts.calibrate_qgis_output_alias_strict import inspect_strict_output_alias


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def replay(
    census_rows: list[dict[str, Any]], manifest_rows: list[dict[str, Any]]
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    manifest_by_id = {str(row["record_id"]): row for row in manifest_rows}
    rows: list[dict[str, Any]] = []
    seen_authorities: set[str] = set()
    for census in sorted(census_rows, key=lambda row: str(row.get("record_id", ""))):
        if "output_alias" not in (census.get("families") or []) or int(census.get("multi_step_local_unit_count") or 0) < 1:
            continue
        authority = str(census.get("source_authority_key") or "")
        if authority in seen_authorities:
            continue
        manifest = manifest_by_id.get(str(census["record_id"]))
        if manifest is None or manifest.get("source_sha256") != census.get("source_sha256"):
            continue
        path = Path(str(manifest.get("source_path") or ""))
        verified = path.is_file() and _sha256(path) == census["source_sha256"]
        result = (
            inspect_strict_output_alias(
                path.read_text(encoding="utf-8-sig", errors="replace"),
                call_sites=manifest.get("call_sites") or [],
            )
            if verified
            else {"status": "fail_closed", "reason": "source_sha_mismatch", "evidence": []}
        )
        rows.append(
            {
                "schema": "gis_recommend.qgis_output_alias_strict_replay.v1",
                "record_id": census["record_id"],
                "source_authority_key": authority,
                "source_path": str(path),
                "source_sha256": census["source_sha256"],
                "source_verification": "verified_sha256" if verified else "failed",
                "replay_status": result["status"],
                "replay_reason": result["reason"],
                "evidence": result["evidence"],
                "ordered_operator_ids": manifest.get("ordered_operator_ids") or [],
                "mapped_l3_chain": manifest.get("mapped_l3_chain") or [],
                "training_admission": "not_granted_replay_sidecar",
                "training_row_emitted": False,
                "validation_eligible": False,
                "test_eligible": False,
                "production_merge": "not_granted",
            }
        )
        seen_authorities.add(authority)
    summary = {
        "schema": "gis_recommend.qgis_output_alias_strict_replay_summary.v1",
        "input_family_rows": sum("output_alias" in (row.get("families") or []) for row in census_rows),
        "multistep_authorities_considered": len(rows),
        "unique_source_authorities": len(seen_authorities),
        "status_counts": dict(sorted(Counter(row["replay_status"] for row in rows).items())),
        "strict_alias_evidence": sum(len(row["evidence"]) for row in rows),
        "source_verification_counts": dict(sorted(Counter(row["source_verification"] for row in rows).items())),
        "training_admission": "not_granted_replay_sidecar",
        "training_rows_emitted": 0,
        "validation_eligible": False,
        "test_eligible": False,
        "production_merge": "not_granted",
    }
    return rows, summary


def _atomic_write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", newline="", dir=path.parent, delete=False) as handle:
        handle.write(text)
        temporary = Path(handle.name)
    temporary.replace(path)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--census", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    rows, summary = replay(_load_jsonl(args.census), _load_jsonl(args.manifest))
    output = args.output_dir / "replay_v1.jsonl"
    summary_path = args.output_dir / "summary_v1.json"
    report = args.output_dir / "report_v1.md"
    hashes = args.output_dir / "hash_ledger_v1.json"
    _atomic_write(output, "".join(json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n" for row in rows))
    _atomic_write(summary_path, json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
    _atomic_write(report, "# QGIS strict output-alias replay v1\n\nReplay sidecar only; no training rows are emitted.\n")
    _atomic_write(hashes, json.dumps({
        "schema": "gis_recommend.hash_ledger.v1",
        "inputs": {str(args.census): _sha256(args.census), str(args.manifest): _sha256(args.manifest)},
        "artifacts": {path.name: _sha256(path) for path in (output, summary_path, report)},
    }, ensure_ascii=False, indent=2, sort_keys=True) + "\n")


if __name__ == "__main__":
    main()
