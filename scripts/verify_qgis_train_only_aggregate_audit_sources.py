#!/usr/bin/env python3
"""Replay source evidence for a QGIS aggregate audit packet."""

from __future__ import annotations

import argparse
import ast
import hashlib
import io
import json
import re
import tempfile
import tokenize
from collections import Counter
from collections.abc import Iterable
from pathlib import Path
from typing import Any

NUMBERED_SOURCE_LINE = re.compile(r"^\s*(\d+) \| (.*)$")


def _sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _sha256(path: Path) -> str:
    return _sha256_bytes(path.read_bytes())


def _decode_python(payload: bytes) -> str:
    encoding, _ = tokenize.detect_encoding(io.BytesIO(payload).readline)
    return payload.decode(encoding)


def _source_ranges(source_span: Any) -> list[tuple[int, int]]:
    if not isinstance(source_span, dict):
        return []
    ranges: list[tuple[int, int]] = []
    if "line_start" in source_span or "line_end" in source_span:
        ranges.append((source_span.get("line_start"), source_span.get("line_end")))
    for key in ("segments", "call_sites"):
        values = source_span.get(key) or []
        if not isinstance(values, list):
            return []
        for value in values:
            if not isinstance(value, dict):
                return []
            ranges.append((value.get("line_start"), value.get("line_end")))
    for line_number in source_span.get("expansion_call_lines") or []:
        ranges.append((line_number, line_number))
    return ranges


def _validate_ranges(source_span: Any, line_count: int) -> tuple[bool, list[dict[str, int]]]:
    ranges = _source_ranges(source_span)
    normalized: list[dict[str, int]] = []
    if not ranges:
        return False, normalized
    for start, end in ranges:
        if (
            not isinstance(start, int)
            or isinstance(start, bool)
            or not isinstance(end, int)
            or isinstance(end, bool)
            or start < 1
            or end < start
            or end > line_count
        ):
            return False, normalized
        normalized.append({"line_start": start, "line_end": end})
    return True, normalized


def _validate_evidence_snippet(
    snippet: Any, source: str, source_lines: list[str]
) -> tuple[bool, str, int, list[dict[str, Any]]]:
    if not isinstance(snippet, str) or not snippet.strip():
        return False, "missing", 0, [{"reason": "missing_evidence_snippet"}]
    numbered_lines = [
        match
        for snippet_line in snippet.splitlines()
        if (match := NUMBERED_SOURCE_LINE.fullmatch(snippet_line))
    ]
    if not numbered_lines:
        if snippet in source:
            return True, "exact_source_segment", len(snippet.splitlines()), []
        return False, "exact_source_segment", 0, [
            {"reason": "evidence_source_segment_mismatch"}
        ]

    checked = 0
    mismatches: list[dict[str, Any]] = []
    for snippet_line in snippet.splitlines():
        match = NUMBERED_SOURCE_LINE.fullmatch(snippet_line)
        if not match:
            if snippet_line.strip() == "...":
                continue
            mismatches.append(
                {"reason": "invalid_numbered_evidence_line", "snippet_line": snippet_line}
            )
            continue
        line_number = int(match.group(1))
        observed = match.group(2)
        checked += 1
        if line_number < 1 or line_number > len(source_lines):
            mismatches.append(
                {"reason": "evidence_line_out_of_range", "line_number": line_number}
            )
            continue
        expected = source_lines[line_number - 1]
        if observed != expected:
            mismatches.append(
                {
                    "reason": "evidence_source_mismatch",
                    "line_number": line_number,
                    "expected": expected,
                    "observed": observed,
                }
            )
    return checked > 0 and not mismatches, "numbered_source_lines", checked, mismatches


def verify_source_row(row: dict[str, Any], payload: bytes | None) -> dict[str, Any]:
    sample_id = str(row.get("sample_id") or "")
    source_path = str(row.get("source_path") or "")
    expected_sha256 = str(row.get("source_sha256") or "")
    result: dict[str, Any] = {
        "schema": "gis_recommend.qgis_train_only_audit_source_replay.v1",
        "sample_id": sample_id,
        "aggregate_source_pool": str(row.get("aggregate_source_pool") or ""),
        "audit_split": str(row.get("audit_split") or ""),
        "audit_risk_stratum": str(row.get("audit_risk_stratum") or ""),
        "source_path": source_path,
        "expected_sha256": expected_sha256,
        "actual_sha256": "",
        "source_exists": payload is not None,
        "sha256_match": False,
        "decode_ok": False,
        "ast_parse_ok": False,
        "source_span_ok": False,
        "evidence_snippet_ok": False,
        "evidence_verification_mode": "not_checked",
        "evidence_lines_checked": 0,
        "source_line_count": 0,
        "validated_ranges": [],
        "errors": [],
        "source_replay_status": "failed_closed",
        "training_rows_emitted": 0,
        "production_merge": "not_granted",
    }
    if not sample_id or not source_path or len(expected_sha256) != 64:
        result["errors"].append({"reason": "invalid_source_identity"})
        return result
    if payload is None:
        result["errors"].append({"reason": "source_missing_or_unreadable"})
        return result

    result["actual_sha256"] = _sha256_bytes(payload)
    result["sha256_match"] = result["actual_sha256"] == expected_sha256
    if not result["sha256_match"]:
        result["errors"].append({"reason": "source_sha256_mismatch"})

    try:
        source = _decode_python(payload)
        result["decode_ok"] = True
    except (SyntaxError, UnicodeDecodeError, LookupError) as exc:
        result["errors"].append(
            {"reason": "source_decode_failed", "detail": str(exc)}
        )
        return result

    source_lines = source.splitlines()
    result["source_line_count"] = len(source_lines)
    try:
        ast.parse(source, filename=source_path)
        result["ast_parse_ok"] = True
    except SyntaxError as exc:
        result["errors"].append(
            {
                "reason": "source_ast_parse_failed",
                "line_number": exc.lineno,
                "detail": exc.msg,
            }
        )

    span_ok, ranges = _validate_ranges(row.get("source_span"), len(source_lines))
    result["source_span_ok"] = span_ok
    result["validated_ranges"] = ranges
    if not span_ok:
        result["errors"].append({"reason": "source_span_invalid"})

    snippet_ok, evidence_mode, checked, mismatches = _validate_evidence_snippet(
        row.get("evidence_snippet"), source, source_lines
    )
    result["evidence_snippet_ok"] = snippet_ok
    result["evidence_verification_mode"] = evidence_mode
    result["evidence_lines_checked"] = checked
    result["errors"].extend(mismatches)

    checks = (
        result["source_exists"],
        result["sha256_match"],
        result["decode_ok"],
        result["ast_parse_ok"],
        result["source_span_ok"],
        result["evidence_snippet_ok"],
    )
    if all(checks):
        result["source_replay_status"] = "verified"
    return result


def verify_audit_sources(
    rows: list[dict[str, Any]], source_reader: Any
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    sample_ids = [str(row.get("sample_id") or "") for row in rows]
    if not rows or any(not sample_id for sample_id in sample_ids):
        raise ValueError("audit packet contains a missing sample_id")
    if len(sample_ids) != len(set(sample_ids)):
        raise ValueError("audit packet contains duplicate sample_id values")

    ledger = [verify_source_row(row, source_reader(str(row["source_path"]))) for row in rows]
    status_counts = Counter(row["source_replay_status"] for row in ledger)
    error_counts = Counter(
        str(error["reason"]) for row in ledger for error in row.get("errors") or []
    )
    summary = {
        "schema": "gis_recommend.qgis_train_only_audit_source_replay.summary.v1",
        "audit_rows": len(rows),
        "verified_rows": status_counts["verified"],
        "failed_closed_rows": status_counts["failed_closed"],
        "source_replay_status_counts": dict(sorted(status_counts.items())),
        "error_counts": dict(sorted(error_counts.items())),
        "source_exists_rows": sum(bool(row["source_exists"]) for row in ledger),
        "sha256_match_rows": sum(bool(row["sha256_match"]) for row in ledger),
        "decode_ok_rows": sum(bool(row["decode_ok"]) for row in ledger),
        "ast_parse_ok_rows": sum(bool(row["ast_parse_ok"]) for row in ledger),
        "source_span_ok_rows": sum(bool(row["source_span_ok"]) for row in ledger),
        "evidence_snippet_ok_rows": sum(
            bool(row["evidence_snippet_ok"]) for row in ledger
        ),
        "evidence_lines_checked": sum(
            int(row["evidence_lines_checked"]) for row in ledger
        ),
        "source_replay_gate": (
            "passed" if status_counts["verified"] == len(rows) else "failed_closed"
        ),
        "semantic_review_status": "pending",
        "training_admission": "not_modified_by_source_replay",
        "training_rows_emitted": 0,
        "production_merge": "not_granted",
    }
    return ledger, summary


def _read_source(path: str) -> bytes | None:
    try:
        return Path(path).read_bytes()
    except OSError:
        return None


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    with path.open(encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def _atomic_write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "w", encoding="utf-8", newline="", dir=path.parent, delete=False
    ) as handle:
        handle.write(content)
        temporary = Path(handle.name)
    temporary.replace(path)


def _write_json(path: Path, value: Any) -> None:
    _atomic_write(path, json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n")


def _write_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> None:
    _atomic_write(
        path,
        "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows),
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--audit-packet", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--expected-rows", type=int, default=50)
    args = parser.parse_args()
    if args.output_dir.exists() and any(args.output_dir.iterdir()):
        raise ValueError(f"output directory is not empty: {args.output_dir}")
    rows = _read_jsonl(args.audit_packet)
    if len(rows) != args.expected_rows:
        raise ValueError("audit packet row count mismatch")

    ledger, summary = verify_audit_sources(rows, _read_source)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    replay_path = args.output_dir / "source_replay_v1.jsonl"
    summary_path = args.output_dir / "source_replay_summary_v1.json"
    _write_jsonl(replay_path, ledger)
    _write_json(summary_path, summary)
    _write_json(
        args.output_dir / "hash_ledger_v1.json",
        {
            "schema": "gis_recommend.hash_ledger.v1",
            "inputs": {
                args.audit_packet.name: {
                    "path": str(args.audit_packet),
                    "sha256": _sha256(args.audit_packet),
                }
            },
            "artifacts": {
                path.name: {"bytes": path.stat().st_size, "sha256": _sha256(path)}
                for path in (replay_path, summary_path)
            },
        },
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if summary["source_replay_gate"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
