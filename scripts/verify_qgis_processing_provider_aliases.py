#!/usr/bin/env python3
"""Prove exact QGIS-to-native provider aliases at selected call sites."""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import tempfile
from pathlib import Path
from typing import Any


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _literal_processing_calls(source: str) -> dict[tuple[int, int], str]:
    tree = ast.parse(source)
    calls: dict[tuple[int, int], str] = {}
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or not node.args:
            continue
        function = node.func
        if not (
            isinstance(function, ast.Attribute)
            and function.attr == "run"
            and isinstance(function.value, ast.Name)
            and function.value.id == "processing"
            and isinstance(node.args[0], ast.Constant)
            and isinstance(node.args[0].value, str)
        ):
            continue
        calls[(node.lineno, int(getattr(node, "end_lineno", node.lineno)))] = node.args[0].value.lower()
    return calls


def _is_exact_qgis_native_alias(actual: str, expected: str) -> bool:
    return (
        actual.startswith("qgis:")
        and expected.startswith("native:")
        and actual.partition(":")[2] == expected.partition(":")[2]
    )


def verify(rows: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, str]]]:
    verified: list[dict[str, Any]] = []
    failures: list[dict[str, str]] = []
    for source in rows:
        row = dict(source)
        record_id = str(row.get("record_id") or "")
        path = Path(str(row.get("source_path") or ""))
        if not path.is_file() or _sha256(path) != str(row.get("source_sha256") or ""):
            failures.append({"record_id": record_id, "reason": "source_not_sha_verified"})
            continue
        try:
            calls = _literal_processing_calls(path.read_text(encoding="utf-8-sig"))
        except (SyntaxError, UnicodeError) as exc:
            failures.append({"record_id": record_id, "reason": f"source_parse_error:{type(exc).__name__}"})
            continue
        migrations: list[dict[str, str]] = []
        valid = True
        for site in row.get("call_sites") or []:
            start = int(site.get("line_start") or 0)
            end = int(site.get("line_end") or start)
            expected = str(site.get("operator_id") or "").lower()
            actual = calls.get((start, end), "")
            if actual == expected:
                continue
            if _is_exact_qgis_native_alias(actual, expected):
                migrations.append({"source": actual, "target": expected, "rule": "qgis_to_native_same_slug"})
                continue
            failures.append({"record_id": record_id, "reason": f"unverified_provider_or_span:{expected}@{start}-{end}"})
            valid = False
            break
        if not valid:
            continue
        row["provider_migrations"] = migrations
        row["provider_alias_status"] = "verified_exact_same_slug" if migrations else "already_literal_canonical"
        verified.append(row)
    return verified, failures


def _write(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    content = "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in value) if isinstance(value, list) else json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", newline="", dir=path.parent, delete=False) as handle:
        handle.write(content)
        temporary = Path(handle.name)
    temporary.replace(path)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--verified-output", type=Path, required=True)
    parser.add_argument("--failure-output", type=Path, required=True)
    args = parser.parse_args()
    rows = [json.loads(line) for line in args.input.read_text(encoding="utf-8").splitlines() if line.strip()]
    verified, failures = verify(rows)
    _write(args.verified_output, verified)
    _write(args.failure_output, failures)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
