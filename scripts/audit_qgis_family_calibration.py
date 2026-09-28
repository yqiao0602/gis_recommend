#!/usr/bin/env python3
"""Audit a family calibration packet at occurrence and matched-span level."""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any


SCHEMA = "gis_recommend.qgis_family_calibration_audit.v1"


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _calls(tree: ast.AST) -> list[ast.Call]:
    calls = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        if isinstance(node.func, ast.Attribute) and isinstance(node.func.value, ast.Name) and node.func.value.id.lower() == "processing" and node.func.attr.lower() in {"run", "runandloadresults"}:
            calls.append(node)
        elif isinstance(node.func, ast.Name) and node.func.id.lower() in {"run", "runandloadresults"}:
            calls.append(node)
    return sorted(calls, key=lambda node: (node.lineno, getattr(node, "col_offset", 0)))


def _id(call: ast.Call) -> str | None:
    return call.args[0].value.strip().lower() if call.args and isinstance(call.args[0], ast.Constant) and isinstance(call.args[0].value, str) else None


def _assigned(tree: ast.AST, call: ast.Call) -> set[str]:
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign) and any(child is call for child in ast.walk(node.value)):
            names.update(target.id for target in node.targets if isinstance(target, ast.Name))
        elif isinstance(node, ast.AnnAssign) and any(child is call for child in ast.walk(node.value)) and isinstance(node.target, ast.Name):
            names.add(node.target.id)
    return names


def _uses(call: ast.Call) -> set[str]:
    return {node.id for node in ast.walk(call) if isinstance(node, ast.Name)}


def _target_names(node: ast.AST) -> set[str]:
    """Return names bound by an assignment/loop target."""
    return {child.id for child in ast.walk(node) if isinstance(child, ast.Name)}


def _name_refs(node: ast.AST | None) -> set[str]:
    return {child.id for child in ast.walk(node) if isinstance(child, ast.Name)} if node else set()


def _contains(node: ast.AST | None, target: ast.AST) -> bool:
    return node is not None and any(child is target for child in ast.walk(node))


def _container_writes(tree: ast.AST, first: ast.Call, known: set[str]) -> set[str]:
    """Recover explicit list/dict-like result sinks fed by the first call.

    This deliberately accepts only ``name.append(value)``/``extend(value)``
    calls.  It does not infer arbitrary mutation or runtime aliasing.
    """
    containers: set[str] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
            continue
        if node.func.attr.lower() not in {"append", "extend", "insert"}:
            continue
        receiver = node.func.value
        if not isinstance(receiver, ast.Name):
            continue
        if _contains(node, first):
            containers.add(receiver.id)
        elif known and known & _name_refs(node):
            containers.add(receiver.id)
    return containers


def _linked(tree: ast.AST, first: ast.Call, second: ast.Call) -> bool:
    known = _assigned(tree, first)
    containers = _container_writes(tree, first, known)
    known |= containers
    if not known:
        return False

    # Propagate only explicit assignments, container writes, and for-loop
    # iteration between the two calls.  This covers common Processing result
    # plumbing without treating same-scope call order as a dependency.
    nodes = sorted(ast.walk(tree), key=lambda item: (getattr(item, "lineno", -1), getattr(item, "col_offset", -1)))
    for node in nodes:
        line = getattr(node, "lineno", -1)
        if not (first.lineno < line < second.lineno):
            continue
        if isinstance(node, (ast.Assign, ast.AnnAssign, ast.AugAssign)):
            value = getattr(node, "value", None)
            if known & _name_refs(value):
                target = getattr(node, "targets", None)
                if target is None:
                    target_names = _target_names(node.target)
                else:
                    target_names = {name for item in target for name in _target_names(item)}
                known |= target_names
        elif isinstance(node, ast.For):
            if known & _name_refs(node.iter):
                known |= _target_names(node.target)
        elif isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            if node.func.attr.lower() in {"append", "extend", "insert"} and known & _name_refs(node):
                if isinstance(node.func.value, ast.Name):
                    known.add(node.func.value.id)
    return bool(known & _uses(second))


def audit_row(row: dict[str, Any]) -> dict[str, Any]:
    path = Path(str(row.get("source_path") or ""))
    failures: list[str] = []
    if not path.is_file():
        return {**row, "schema": SCHEMA, "audit_status": "deferred_source_missing", "audit_failures": ["source_missing"], "training_rows_emitted": 0}
    raw = path.read_bytes()
    actual_sha = hashlib.sha256(raw).hexdigest()
    if actual_sha != str(row.get("source_sha256") or ""):
        failures.append("source_sha_mismatch")
    try:
        tree = ast.parse(raw.decode("utf-8-sig", errors="strict"))
    except (UnicodeDecodeError, SyntaxError) as exc:
        return {**row, "schema": SCHEMA, "actual_source_sha256": actual_sha, "audit_status": "deferred_parse", "audit_failures": [type(exc).__name__], "training_rows_emitted": 0}
    calls = _calls(tree)
    actual_ids = [_id(call) for call in calls]
    expected_full = [str(value).lower() for value in row.get("full_parent_operator_sequence") or []]
    target = [str(value).lower() for value in row.get("family_sequence") or []]
    span = row.get("matched_span") or {}
    start, end = int(span.get("start_index", -1)), int(span.get("end_index_exclusive", -1))
    if any(value is None for value in actual_ids):
        failures.append("dynamic_or_missing_operator_id")
    if actual_ids != expected_full:
        failures.append("full_operator_sequence_mismatch")
    if start < 0 or end != start + len(target) or actual_ids[start:end] != target:
        failures.append("matched_span_mismatch")
    if len(calls) != len(expected_full):
        failures.append("call_count_mismatch")
    parameter_evidence = [bool(call.args[1:]) or any(keyword.arg is not None for keyword in call.keywords) for call in calls]
    if not all(parameter_evidence):
        failures.append("parameter_evidence_missing")
    linked = _linked(tree, calls[start], calls[start + 1]) if 0 <= start < len(calls) - 1 and end == start + 2 else False
    if not linked:
        failures.append("matched_pair_dependency_missing")
    audit_status = "passed" if not failures else ("deferred_dependency_rule_gap" if failures == ["matched_pair_dependency_missing"] else "failed")
    return {
        **row,
        "schema": SCHEMA,
        "actual_source_sha256": actual_sha,
        "audit_status": audit_status,
        "audit_failures": failures,
        "audit_checks": {"source_sha": actual_sha == str(row.get("source_sha256") or ""), "full_sequence": actual_ids == expected_full, "matched_span": actual_ids[start:end] == target if 0 <= start <= end <= len(actual_ids) else False, "parameter_evidence": all(parameter_evidence), "matched_pair_dependency": linked},
        "ast_operator_ids": actual_ids,
        "call_spans": [{"line_start": call.lineno, "line_end": getattr(call, "end_lineno", call.lineno)} for call in calls],
        "training_admission": "not_granted_family_calibration_audit_v1",
        "training_rows_emitted": 0,
        "validation_eligible": False,
        "test_eligible": False,
        "production_merge": "not_granted",
    }


def audit(rows: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    audited = [audit_row(row) for row in rows]
    calibration = {row.get("source_sha256") for row in audited if row.get("split") == "calibration"}
    holdout = {row.get("source_sha256") for row in audited if row.get("split") == "holdout"}
    summary = {
        "schema": f"{SCHEMA}.summary",
        "input_rows": len(audited),
        "passed_rows": sum(row.get("audit_status") == "passed" for row in audited),
        "failed_rows": sum(row.get("audit_status") == "failed" for row in audited),
        "deferred_rows": sum(str(row.get("audit_status", "")).startswith("deferred") for row in audited),
        "source_sha_verified_rows": sum(bool(row.get("audit_checks", {}).get("source_sha")) for row in audited),
        "calibration_source_count": len(calibration),
        "holdout_source_count": len(holdout),
        "source_sha_overlap": len(calibration & holdout),
        "failure_counts": dict(sorted(Counter(failure for row in audited for failure in row.get("audit_failures") or []).items())),
        "training_rows_emitted": 0,
        "training_admission": "not_granted_family_calibration_audit_v1",
        "l3_mapping": "unchanged",
    }
    return audited, summary


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--packet", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    audited, summary = audit(read_jsonl(args.packet))
    args.output_dir.mkdir(parents=True, exist_ok=True)
    ledger = args.output_dir / "calibration_audit_v1.jsonl"
    ledger.write_text("".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in audited), encoding="utf-8")
    summary_path = args.output_dir / "summary_v1.json"
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (args.output_dir / "hash_ledger_v1.json").write_text(json.dumps({ledger.name: hashlib.sha256(ledger.read_bytes()).hexdigest(), summary_path.name: hashlib.sha256(summary_path.read_bytes()).hexdigest()}, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if summary["failed_rows"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
