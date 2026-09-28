#!/usr/bin/env python3
"""Deterministically audit one Processing family review packet.

Checks source SHA, AST literal Processing IDs, ordered call count, simple
assignment-to-argument data flow, parameter dictionaries, and normalized AST
template repetition.  This is calibration evidence only; it emits no L3 or
training rows.
"""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any


SCHEMA = "gis_recommend.qgis_asset_family_semantic_audit.v1"


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


class _RedactConstants(ast.NodeTransformer):
    def visit_Constant(self, node: ast.Constant) -> ast.AST:  # noqa: N802
        if isinstance(node.value, str):
            return ast.copy_location(ast.Constant(value="<str>"), node)
        if isinstance(node.value, (int, float, complex)):
            return ast.copy_location(ast.Constant(value="<number>"), node)
        return node


def normalized_ast_hash(tree: ast.AST) -> str:
    redacted = _RedactConstants().visit(ast.fix_missing_locations(tree))
    payload = ast.dump(redacted, annotate_fields=True, include_attributes=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _processing_calls(tree: ast.AST) -> list[ast.Call]:
    calls: list[ast.Call] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        if isinstance(node.func, ast.Attribute) and isinstance(node.func.value, ast.Name) and node.func.value.id.lower() == "processing" and node.func.attr.lower() in {"run", "runandloadresults"}:
            calls.append(node)
        elif isinstance(node.func, ast.Name) and node.func.id.lower() in {"run", "runandloadresults"}:
            calls.append(node)
    return sorted(calls, key=lambda call: (int(call.lineno), int(getattr(call, "col_offset", 0))))


def _literal_id(call: ast.Call) -> str | None:
    if not call.args or not isinstance(call.args[0], ast.Constant) or not isinstance(call.args[0].value, str):
        return None
    return call.args[0].value.strip().lower()


def _assigned_names(tree: ast.AST, call: ast.Call) -> list[str]:
    names: list[str] = []
    for parent in ast.walk(tree):
        if isinstance(parent, ast.Assign) and parent.value is call:
            names.extend(target.id for target in parent.targets if isinstance(target, ast.Name))
        elif isinstance(parent, ast.AnnAssign) and parent.value is call and isinstance(parent.target, ast.Name):
            names.append(parent.target.id)
    return names


def _names_in_call(call: ast.Call) -> set[str]:
    return {node.id for node in ast.walk(call) if isinstance(node, ast.Name)}


def _dependency_exists(tree: ast.AST, first: ast.Call, second: ast.Call) -> bool:
    """Follow simple result aliases between two ordered Processing calls."""
    known = set(_assigned_names(tree, first))
    if not known:
        return False
    assignments = sorted(
        (node for node in ast.walk(tree) if isinstance(node, ast.Assign) and first.lineno < node.lineno < second.lineno),
        key=lambda node: (int(node.lineno), int(getattr(node, "col_offset", 0))),
    )
    for assignment in assignments:
        referenced = {node.id for node in ast.walk(assignment.value) if isinstance(node, ast.Name)}
        if referenced & known:
            known.update(target.id for target in assignment.targets if isinstance(target, ast.Name))
    return bool(known & _names_in_call(second))


def audit_row(row: dict[str, Any]) -> dict[str, Any]:
    path = Path(str(row.get("source_path") or ""))
    expected_sha = str(row.get("source_sha256") or "")
    checks: dict[str, Any] = {}
    failures: list[str] = []
    if not path.is_file():
        return {**row, "schema": SCHEMA, "audit_status": "deferred_source_missing", "audit_failures": ["source_missing"], "training_rows_emitted": 0}
    raw = path.read_bytes()
    actual_sha = sha256_bytes(raw)
    checks["source_sha"] = actual_sha == expected_sha
    if not checks["source_sha"]:
        failures.append("source_sha_mismatch")
    try:
        tree = ast.parse(raw.decode("utf-8-sig", errors="strict"))
    except (UnicodeDecodeError, SyntaxError) as exc:
        return {**row, "schema": SCHEMA, "actual_source_sha256": actual_sha, "audit_status": "deferred_parse", "audit_failures": [type(exc).__name__], "training_rows_emitted": 0}
    calls = _processing_calls(tree)
    actual_ids = [_literal_id(call) for call in calls]
    expected_ids = [str(value).lower() for value in row.get("processing_operator_ids") or []]
    checks["literal_operator_ids"] = all(value is not None for value in actual_ids)
    checks["operator_sequence"] = actual_ids == expected_ids
    checks["call_count"] = len(calls) == len(expected_ids)
    if not checks["literal_operator_ids"]:
        failures.append("dynamic_or_missing_operator_id")
    if not checks["operator_sequence"]:
        failures.append("operator_sequence_mismatch")
    if not checks["call_count"]:
        failures.append("call_count_mismatch")
    assignments = [_assigned_names(tree, call) for call in calls]
    dependency_edges: list[list[int]] = []
    for index in range(len(calls) - 1):
        if _dependency_exists(tree, calls[index], calls[index + 1]):
            dependency_edges.append([index, index + 1])
    checks["ordered_dependency"] = len(expected_ids) < 2 or dependency_edges == [[index, index + 1] for index in range(len(expected_ids) - 1)]
    if not checks["ordered_dependency"]:
        failures.append("missing_inter_call_dependency")
    parameter_dicts = []
    for call in calls:
        parameter_dicts.append(bool(call.args[1:]) or any(keyword.arg is not None for keyword in call.keywords))
    checks["parameter_evidence"] = all(parameter_dicts) if parameter_dicts else False
    if not checks["parameter_evidence"]:
        failures.append("parameter_evidence_missing")
    checks["source_span_evidence"] = all(int(getattr(call, "lineno", 0)) > 0 and int(getattr(call, "end_lineno", 0)) >= int(getattr(call, "lineno", 0)) for call in calls)
    template_hash = normalized_ast_hash(tree)
    return {
        **row,
        "schema": SCHEMA,
        "actual_source_sha256": actual_sha,
        "audit_status": "passed" if not failures else "failed",
        "audit_failures": failures,
        "audit_checks": checks,
        "ast_operator_ids": actual_ids,
        "call_spans": [{"line_start": int(call.lineno), "line_end": int(getattr(call, "end_lineno", call.lineno))} for call in calls],
        "assigned_result_names": assignments,
        "dependency_edges": dependency_edges,
        "parameter_evidence": parameter_dicts,
        "normalized_ast_hash": template_hash,
        "training_rows_emitted": 0,
        "training_admission": "not_granted_asset_family_semantic_audit_v1",
        "validation_eligible": False,
        "test_eligible": False,
        "production_merge": "not_granted",
    }


def audit(rows: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    audited = [audit_row(row) for row in rows]
    template_counts = Counter(str(row.get("normalized_ast_hash") or "") for row in audited if row.get("normalized_ast_hash"))
    for row in audited:
        row["template_support"] = template_counts.get(str(row.get("normalized_ast_hash") or ""), 0)
        if row.get("audit_status") == "passed" and row["template_support"] > 1:
            row["audit_warnings"] = ["repeated_normalized_template"]
        else:
            row["audit_warnings"] = []
    summary = {
        "schema": f"{SCHEMA}.summary",
        "input_rows": len(audited),
        "passed_rows": sum(row.get("audit_status") == "passed" for row in audited),
        "failed_rows": sum(row.get("audit_status") == "failed" for row in audited),
        "deferred_rows": sum(str(row.get("audit_status", "")).startswith("deferred") for row in audited),
        "source_sha_verified_rows": sum(bool(row.get("audit_checks", {}).get("source_sha")) for row in audited),
        "unique_normalized_templates": len(template_counts),
        "repeated_template_rows": sum(count for count in template_counts.values() if count > 1),
        "failure_counts": dict(sorted(Counter(failure for row in audited for failure in row.get("audit_failures") or []).items())),
        "source_sha_overlap": len({row.get("source_sha256") for row in audited if row.get("split") == "calibration"} & {row.get("source_sha256") for row in audited if row.get("split") == "holdout"}),
        "training_rows_emitted": 0,
        "training_admission": "not_granted_asset_family_semantic_audit_v1",
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
    ledger = args.output_dir / "semantic_audit_v1.jsonl"
    ledger.write_text("".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in audited), encoding="utf-8")
    summary_path = args.output_dir / "summary_v1.json"
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    hashes = {ledger.name: sha256_bytes(ledger.read_bytes()), summary_path.name: sha256_bytes(summary_path.read_bytes())}
    (args.output_dir / "hash_ledger_v1.json").write_text(json.dumps(hashes, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if summary["deferred_rows"] == 0 and summary["failed_rows"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
