#!/usr/bin/env python3
"""Independently audit structural edges recovered by the isolated runalg adapter."""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import tempfile
import warnings
from collections import Counter
from pathlib import Path
from typing import Any

SCHEMA = "gis_recommend.qgis_processing_runalg_adapter_audit.v1"


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    with path.open(encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write(path: Path, value: Any) -> None:
    content = (
        "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in value)
        if isinstance(value, list)
        else json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "w", encoding="utf-8", newline="", dir=path.parent, delete=False
    ) as handle:
        handle.write(content)
        temporary = Path(handle.name)
    temporary.replace(path)


def _parents(tree: ast.AST) -> dict[ast.AST, ast.AST]:
    return {
        child: parent
        for parent in ast.walk(tree)
        for child in ast.iter_child_nodes(parent)
    }


SAFE_ALIAS_CALLS = {"QgsRasterLayer", "QgsVectorLayer", "processing.getObject"}


def _node_key(node: ast.AST) -> str:
    if isinstance(node, ast.Name):
        return f"name:{node.id}"
    if isinstance(node, ast.Attribute):
        base = _node_key(node.value)
        return f"{base}.attr:{node.attr}" if base else ""
    if isinstance(node, ast.Subscript):
        base = _node_key(node.value)
        if base and isinstance(node.slice, ast.Constant):
            return f"{base}.key:{node.slice.value}"
    return ""


def _reference_keys(node: ast.AST) -> set[str]:
    return {key for child in ast.walk(node) if (key := _node_key(child))}


def _call_name(node: ast.Call) -> str:
    return _node_key(node.func).removeprefix("name:").replace(".attr:", ".")


def _target_key(call: ast.Call, parents: dict[ast.AST, ast.AST]) -> str:
    current: ast.AST = call
    while current in parents:
        current = parents[current]
        if isinstance(current, ast.Assign) and len(current.targets) == 1:
            return _node_key(current.targets[0])
        if isinstance(current, ast.AnnAssign):
            return _node_key(current.target)
        if isinstance(current, (ast.Expr, ast.Return, ast.FunctionDef, ast.AsyncFunctionDef)):
            return ""
    return ""


def _scope(node: ast.AST, parents: dict[ast.AST, ast.AST]) -> ast.AST:
    current = node
    while current in parents:
        current = parents[current]
        if isinstance(current, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef)):
            return current
    return current


def _definitions(tree: ast.AST, parents: dict[ast.AST, ast.AST]) -> list[tuple[ast.AST, int, str, ast.AST]]:
    result = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            targets, value = node.targets, node.value
        elif isinstance(node, ast.AnnAssign) and node.value is not None:
            targets, value = [node.target], node.value
        else:
            continue
        for target in targets:
            if key := _node_key(target):
                result.append((_scope(node, parents), int(node.lineno), key, value))
    return result


def _latest_definition(
    key: str,
    *,
    scope: ast.AST,
    before_line: int,
    definitions: list[tuple[ast.AST, int, str, ast.AST]],
) -> ast.AST | None:
    candidates = [
        (line, value)
        for definition_scope, line, target, value in definitions
        if definition_scope is scope and target == key and line < before_line
    ]
    return max(candidates, key=lambda item: item[0])[1] if candidates else None


def _safe_alias_references(value: ast.AST) -> set[str] | None:
    if isinstance(value, (ast.Name, ast.Attribute, ast.Subscript)):
        return _reference_keys(value)
    if isinstance(value, ast.Call) and _call_name(value) in SAFE_ALIAS_CALLS:
        return {
            reference
            for argument in [*value.args, *(keyword.value for keyword in value.keywords)]
            for reference in _reference_keys(argument)
        }
    return None


def _expanded_references(
    initial: set[str],
    *,
    call: ast.Call,
    parents: dict[ast.AST, ast.AST],
    definitions: list[tuple[ast.AST, int, str, ast.AST]],
) -> set[str]:
    scope = _scope(call, parents)
    pending = list(initial)
    expanded = set(initial)
    seen = set()
    while pending:
        key = pending.pop()
        if key in seen:
            continue
        seen.add(key)
        value = _latest_definition(
            key, scope=scope, before_line=int(call.lineno), definitions=definitions
        )
        aliases = _safe_alias_references(value) if value is not None else None
        if aliases is None:
            continue
        for alias in aliases:
            if alias not in expanded:
                expanded.add(alias)
                pending.append(alias)
    return expanded


def _is_direct_literal_runalg(node: ast.AST) -> bool:
    return (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and isinstance(node.func.value, ast.Name)
        and node.func.value.id == "processing"
        and node.func.attr == "runalg"
        and bool(node.args)
        and isinstance(node.args[0], ast.Constant)
        and isinstance(node.args[0].value, str)
        and bool(node.args[0].value.strip())
    )


def _operator_id(call: ast.Call) -> str:
    first = call.args[0]
    assert isinstance(first, ast.Constant) and isinstance(first.value, str)
    return first.value.strip().lower()


def _selected_calls(tree: ast.AST, expected: list[str]) -> list[ast.Call] | None:
    calls = sorted(
        (node for node in ast.walk(tree) if _is_direct_literal_runalg(node)),
        key=lambda call: (call.lineno, call.col_offset),
    )
    selected = [call for call in calls if _operator_id(call) in expected]
    if [_operator_id(call) for call in selected] != expected:
        return None
    return selected


def _independent_edges(
    calls: list[ast.Call],
    parents: dict[ast.AST, ast.AST],
    definitions: list[tuple[ast.AST, int, str, ast.AST]],
) -> list[list[int]]:
    targets = [_target_key(call, parents) for call in calls]
    edges: list[list[int]] = []
    for consumer_index, call in enumerate(calls):
        references = _expanded_references(
            {
                reference
                for value in [*call.args[1:], *(keyword.value for keyword in call.keywords)]
                for reference in _reference_keys(value)
            },
            call=call,
            parents=parents,
            definitions=definitions,
        )
        matched_producers = set()
        for reference in references:
            candidates = [
                producer_index
                for producer_index, target in enumerate(targets[:consumer_index])
                if target and (reference == target or reference.startswith(target + "."))
            ]
            if candidates:
                matched_producers.add(max(candidates))
        edges.extend([producer_index, consumer_index] for producer_index in sorted(matched_producers))
    return edges


def audit_row(row: dict[str, Any]) -> dict[str, Any]:
    result = {
        "schema": SCHEMA,
        "record_id": str(row.get("record_id") or ""),
        "source_sha256": str(row.get("source_sha256") or ""),
        "source_path": str(row.get("source_path") or ""),
        "calibration_role": str(row.get("calibration_role") or ""),
        "training_rows_emitted": 0,
        "training_admission": "not_granted_runalg_adapter_audit_only",
        "validation_eligible": False,
        "test_eligible": False,
        "production_merge": "not_granted",
        "llm_called": False,
    }
    if row.get("status") != "adapter_structural_recovered":
        return {**result, "status": "reject_adapter_not_recovered"}
    path = Path(result["source_path"])
    if not path.is_file():
        return {**result, "status": "source_missing"}
    if _sha256_file(path) != result["source_sha256"]:
        return {**result, "status": "source_hash_mismatch"}
    source = path.read_text(encoding="utf-8-sig", errors="replace")
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", SyntaxWarning)
            tree = ast.parse(source)
    except SyntaxError as exc:
        return {**result, "status": "source_unparseable", "reason": str(exc)}
    expected_operators = [str(value) for value in row.get("expected_operator_ids") or []]
    calls = _selected_calls(tree, expected_operators)
    if calls is None:
        return {**result, "status": "reject_call_sequence_mismatch"}
    expected_edges = sorted([list(edge) for edge in row.get("dependency_edges") or []])
    parents = _parents(tree)
    independent_edges = _independent_edges(calls, parents, _definitions(tree, parents))
    if sorted(independent_edges) != expected_edges:
        return {
            **result,
            "status": "reject_dependency_edge_mismatch",
            "expected_edges": expected_edges,
            "independent_edges": independent_edges,
        }
    return {
        **result,
        "status": "accepted_structural_match",
        "operator_ids": expected_operators,
        "dependency_edges": sorted(independent_edges),
        "training_rows_emitted": 0,
    }


def audit(rows: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    output = [audit_row(row) for row in rows]
    accepted = [row for row in output if row["status"] == "accepted_structural_match"]
    summary = {
        "schema": f"{SCHEMA}.summary",
        "input_rows": len(rows),
        "status_counts": dict(sorted(Counter(row["status"] for row in output).items())),
        "accepted_rows": len(accepted),
        "accepted_dependency_edge_rows": sum(bool(row.get("dependency_edges")) for row in accepted),
        "accepted_dependency_edge_count": sum(len(row.get("dependency_edges") or []) for row in accepted),
        "holdout_release": "not_granted_pending_zero_error_calibration",
        "training_rows_emitted": 0,
        "training_admission": "not_granted_runalg_adapter_audit_only",
        "validation_eligible": False,
        "test_eligible": False,
        "production_merge": "not_granted",
        "llm_called": False,
    }
    return output, summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--adapter-ledger", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    if args.output_dir.exists() and any(args.output_dir.iterdir()):
        raise ValueError(f"output directory is not empty: {args.output_dir}")
    output, summary = audit(_read_jsonl(args.adapter_ledger))
    args.output_dir.mkdir(parents=True, exist_ok=True)
    ledger = args.output_dir / "runalg_calibration_independent_audit_v1.jsonl"
    summary_path = args.output_dir / "runalg_calibration_independent_audit_summary_v1.json"
    _write(ledger, output)
    _write(summary_path, summary)
    _write(
        args.output_dir / "hash_ledger_v1.json",
        {
            "schema": "gis_recommend.hash_ledger.v1",
            "inputs": {"adapter_ledger": _sha256_file(args.adapter_ledger)},
            "artifacts": {
                ledger.name: _sha256_file(ledger),
                summary_path.name: _sha256_file(summary_path),
            },
        },
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
