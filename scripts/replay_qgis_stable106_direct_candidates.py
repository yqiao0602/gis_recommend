#!/usr/bin/env python3
"""Verify stable106 canonical direct candidates against /home/yll authority."""

from __future__ import annotations

import argparse
import hashlib
import json
import tempfile
from collections import Counter
from pathlib import Path
from typing import Any, Iterable

from gis_recommend.data.qgis_source_authority import source_authority


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _index_unique(rows: list[dict[str, Any]], field: str) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for row in rows:
        key = str(row.get(field) or "")
        if not key or key in result:
            raise ValueError(f"missing or duplicate {field}: {key!r}")
        result[key] = row
    return result


def replay_candidates(
    candidates: list[dict[str, Any]],
    ledger: list[dict[str, Any]],
    *,
    source_authority_rows: list[dict[str, Any]] | None = None,
    replay_profile: str = "stable106",
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    by_id = _index_unique(candidates, "record_id")
    canonical_ids = [
        str(row["record_id"])
        for row in ledger
        if row.get("dedup_decision") == "canonical_keep_candidate"
    ]
    missing = sorted(set(canonical_ids) - set(by_id))
    if missing:
        raise ValueError(f"canonical candidates missing from description rows: {missing}")
    authority_by_id = (
        _index_unique(source_authority_rows, "record_id")
        if source_authority_rows is not None
        else {}
    )
    correction_profile = replay_profile != "stable106"
    row_schema = (
        "gis_recommend.qgis_direct_source_replay.v1"
        if correction_profile
        else "gis_recommend.qgis_stable106_source_replay.v1"
    )

    rows: list[dict[str, Any]] = []
    for record_id in canonical_ids:
        candidate = by_id[record_id]
        path = Path(str(candidate.get("source_path") or ""))
        expected_sha = str(candidate.get("source_sha256") or "")
        if path.is_file():
            if _sha256(path) != expected_sha:
                raise ValueError(f"source SHA mismatch: {path}")
            source_lines = path.read_text(
                encoding="utf-8-sig", errors="replace"
            ).splitlines()
            snippets: list[str] = []
            for site in candidate.get("call_sites") or []:
                start = int(site.get("line_start") or 0)
                end = int(site.get("line_end") or start)
                if start < 1 or end < start or end > len(source_lines):
                    raise ValueError(f"invalid call span for {record_id}: {start}-{end}")
                snippet = "\n".join(
                    f"{line_number} | {source_lines[line_number - 1]}"
                    for line_number in range(start, end + 1)
                )
                if "processing.run" not in snippet:
                    raise ValueError(
                        f"call span does not contain processing.run for {record_id}: {start}-{end}"
                    )
                snippets.append(snippet)
            if len(snippets) != len(candidate.get("operator_ids") or []):
                raise ValueError(f"operator/call span count mismatch: {record_id}")
            authority = source_authority(path, source_sha256=expected_sha)
            source_snippet = "\n...\n".join(snippets)
            source_verification = "verified_sha256"
            call_span_verification = "verified_processing_calls"
        else:
            prior = authority_by_id.get(record_id)
            identities = (
                (candidate.get("source_path"), prior.get("source_path") if prior else None),
                (expected_sha, prior.get("source_sha256") if prior else None),
                (candidate.get("operator_ids") or [], prior.get("operator_chain") if prior else None),
            )
            if prior is None or any(left != right for left, right in identities):
                raise ValueError(f"source authority identity mismatch: {record_id}")
            body_sha = str(prior.get("normalized_source_body_sha256") or "")
            authority_key = str(prior.get("source_authority_key") or "")
            if not body_sha or authority_key != f"normalized_source_body_sha256:{body_sha}":
                raise ValueError(f"invalid normalized source authority: {record_id}")
            source_snippet = str(candidate.get("source_snippet") or "")
            if (
                candidate.get("source_snippet_contains_all_ops") is not True
                or source_snippet.count("processing.run")
                < len(candidate.get("call_sites") or [])
            ):
                raise ValueError(f"cached processing call evidence incomplete: {record_id}")
            authority = {
                "source_authority_key": authority_key,
                "normalized_source_body_sha256": body_sha,
            }
            source_verification = "carried_forward_verified_normalized_source_body"
            call_span_verification = "carried_forward_cached_processing_calls"
        rows.append(
            {
                "schema": row_schema,
                "replay_profile": replay_profile,
                "record_id": record_id,
                "source_path": str(path),
                "source_sha256": expected_sha,
                "operator_ids": candidate.get("operator_ids") or [],
                "mapped_l3_chain": candidate.get("mapped_l3_chain") or [],
                "call_sites": candidate.get("call_sites") or [],
                "source_snippet": source_snippet,
                "source_verification": source_verification,
                "call_span_verification": call_span_verification,
                **authority,
                "taxonomy_admission": (
                    "not_changed_existing_taxonomy"
                    if correction_profile
                    else "not_granted"
                ),
                "training_admission": (
                    "not_granted_pending_train_only_export"
                    if correction_profile
                    else "not_granted_stable106_report_only"
                ),
                "training_rows_emitted": 0,
                "validation_eligible": False,
                "test_eligible": False,
                "production_merge": "not_granted",
            }
        )
    summary = {
        "schema": (
            "gis_recommend.qgis_direct_source_replay_summary.v1"
            if correction_profile
            else "gis_recommend.qgis_stable106_source_replay_summary.v1"
        ),
        "replay_profile": replay_profile,
        "canonical_input_rows": len(canonical_ids),
        "verified_rows": len(rows),
        "unique_source_sha256": len({row["source_sha256"] for row in rows}),
        "unique_source_authorities": len(
            {row["source_authority_key"] for row in rows}
        ),
        "verification_mode_counts": dict(
            sorted(Counter(row["source_verification"] for row in rows).items())
        ),
        "taxonomy_admission": (
            "not_changed_existing_taxonomy" if correction_profile else "not_granted"
        ),
        "training_admission": (
            "not_granted_pending_train_only_export"
            if correction_profile
            else "not_granted_stable106_report_only"
        ),
        "training_rows_emitted": 0,
        "next_gate": (
            "explicit train-only export admission"
            if correction_profile
            else "taxonomy authority adjudication for five stable106 classes"
        ),
    }
    return rows, summary


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _atomic_write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "w", encoding="utf-8", newline="", dir=path.parent, delete=False
    ) as handle:
        handle.write(text)
        temporary = Path(handle.name)
    temporary.replace(path)


def _write_json(path: Path, value: Any) -> None:
    _atomic_write(path, json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n")


def _write_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> None:
    _atomic_write(
        path,
        "".join(
            json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
            + "\n"
            for row in rows
        ),
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidates", type=Path, required=True)
    parser.add_argument("--dedup-ledger", type=Path, required=True)
    parser.add_argument("--source-authority-ledger", type=Path)
    parser.add_argument("--replay-profile", default="stable106")
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    if args.output_dir.exists() and any(args.output_dir.iterdir()):
        raise ValueError(f"output directory is not empty: {args.output_dir}")
    rows, summary = replay_candidates(
        _read_jsonl(args.candidates),
        _read_jsonl(args.dedup_ledger),
        source_authority_rows=(
            _read_jsonl(args.source_authority_ledger)
            if args.source_authority_ledger
            else None
        ),
        replay_profile=args.replay_profile,
    )
    replay_path = args.output_dir / "source_replay_v1.jsonl"
    summary_path = args.output_dir / "summary_v1.json"
    hash_path = args.output_dir / "hash_ledger_v1.json"
    _write_jsonl(replay_path, rows)
    _write_json(summary_path, summary)
    _write_json(
        hash_path,
        {
            "schema": "gis_recommend.hash_ledger.v1",
            "inputs": {
                "candidates": {
                    "path": str(args.candidates),
                    "sha256": _sha256(args.candidates),
                },
                "dedup_ledger": {
                    "path": str(args.dedup_ledger),
                    "sha256": _sha256(args.dedup_ledger),
                },
                **(
                    {
                        "source_authority_ledger": {
                            "path": str(args.source_authority_ledger),
                            "sha256": _sha256(args.source_authority_ledger),
                        }
                    }
                    if args.source_authority_ledger
                    else {}
                ),
            },
            "artifacts": {
                replay_path.name: _sha256(replay_path),
                summary_path.name: _sha256(summary_path),
            },
        },
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
