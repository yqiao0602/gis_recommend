#!/usr/bin/env python3
"""Extract source-backed evidence for normalized Processing operator assets.

The normalized ledger identifies operator assets but intentionally omits the
source-level parameter and I/O details needed for qualification. This sidecar
replays each source file with a small, fail-closed AST extractor. It records
evidence only; it does not infer L3 labels or emit training rows.

A parameter dictionary passed by name is only recovered when the binding is
provable: exactly one assignment must structurally dominate the call on its own
block path, sit in the same scope, and no rebinding or dict mutation may occur
between that assignment and the call span. Every accepted recovery keeps its
assignment line and span so the proof chain can be replayed later.
"""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any, NamedTuple

SCHEMA = "gis_recommend.qgis_processing_operator_evidence_sidecar.v1"
NAME_BINDING_RULE = "dominating_same_scope_static_dict_v2"
MUTATING_METHODS = frozenset({"update", "setdefault", "pop", "popitem", "clear"})
# ``except`` and ``match case`` clauses hold statement bodies but are not statements
# themselves, so they must be traversed for their bodies to be indexed at all.
STATEMENT_CONTAINERS: tuple[type, ...] = (ast.ExceptHandler,) + (
    (ast.match_case,) if hasattr(ast, "match_case") else ()
)
_MISSING = object()


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _source_segment(source: str, node: ast.AST | None) -> str | None:
    if node is None:
        return None
    return ast.get_source_segment(source, node)


def _literal(node: ast.AST | None) -> Any:
    value = _literal_or_missing(node)
    return None if value is _MISSING else value


def _literal_or_missing(node: ast.AST | None) -> Any:
    """Distinguish "not a literal" from a literal ``None``/``False``/``0``."""
    if node is None:
        return _MISSING
    try:
        return ast.literal_eval(node)
    except (ValueError, TypeError, SyntaxError):
        return _MISSING


class BindingContext(NamedTuple):
    """Structural indexes needed to prove a parameter binding; built once per source."""

    tree: ast.AST
    parents: dict[ast.AST, ast.AST]
    paths: dict[ast.stmt, list[tuple[list[ast.stmt], int]]]


def _binding_context(tree: ast.AST) -> BindingContext:
    parents = {child: node for node in ast.walk(tree) for child in ast.iter_child_nodes(node)}
    paths: dict[ast.stmt, list[tuple[list[ast.stmt], int]]] = {}

    def descend(node: ast.AST, prefix: list[tuple[list[ast.stmt], int]]) -> None:
        for _, value in ast.iter_fields(node):
            if not isinstance(value, list) or not value:
                continue
            if all(isinstance(item, ast.stmt) for item in value):
                for index, statement in enumerate(value):
                    chain = prefix + [(value, index)]
                    paths[statement] = chain
                    descend(statement, chain)
            elif all(isinstance(item, STATEMENT_CONTAINERS) for item in value):
                for clause in value:
                    descend(clause, prefix)

    descend(tree, [])
    return BindingContext(tree, parents, paths)


def _enclosing_statement(context: BindingContext, node: ast.AST) -> ast.stmt | None:
    current: ast.AST | None = node
    while current is not None and not isinstance(current, ast.stmt):
        current = context.parents.get(current)
    return current if isinstance(current, ast.stmt) else None


def _scope_label(context: BindingContext, node: ast.AST) -> str:
    current: ast.AST | None = node
    while current is not None:
        if isinstance(current, (ast.FunctionDef, ast.AsyncFunctionDef)):
            return f"function:{current.name}:{current.lineno}"
        if isinstance(current, ast.ClassDef):
            return f"class:{current.name}:{current.lineno}"
        current = context.parents.get(current)
    return "module"


def _dominates(
    assignment_chain: list[tuple[list[ast.stmt], int]],
    call_chain: list[tuple[list[ast.stmt], int]],
) -> bool:
    """True when the assignment sits on the call's own block path, strictly before it."""
    if not assignment_chain or len(assignment_chain) > len(call_chain):
        return False
    for index, (body, position) in enumerate(assignment_chain):
        call_body, call_position = call_chain[index]
        if body is not call_body:
            return False
        if index == len(assignment_chain) - 1:
            return position < call_position
        if position != call_position:
            return False
    return False


def _touches_name(node: ast.AST | None, name: str) -> bool:
    return node is not None and any(isinstance(inner, ast.Name) and inner.id == name for inner in ast.walk(node))


def _name_write_lines(tree: ast.AST, name: str) -> list[int]:
    """Every line that may rebind ``name`` or mutate the object it holds."""
    lines: set[int] = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Assign, ast.Delete)):
            targets: list[ast.AST | None] = list(node.targets)
        elif isinstance(node, (ast.AugAssign, ast.AnnAssign, ast.For, ast.AsyncFor, ast.NamedExpr)):
            targets = [node.target]
        elif isinstance(node, (ast.With, ast.AsyncWith)):
            targets = [item.optional_vars for item in node.items]
        elif isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr in MUTATING_METHODS:
            targets = [node.func.value]
        else:
            continue
        if any(_touches_name(target, name) for target in targets):
            lines.add(node.lineno)
    return sorted(lines)


def _processing_calls(tree: ast.AST) -> list[ast.Call]:
    calls = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        if isinstance(node.func, ast.Attribute) and node.func.attr in {"run", "runalg", "runAndLoadResults"} and isinstance(node.func.value, ast.Name) and node.func.value.id == "processing":
            calls.append(node)
        elif isinstance(node.func, ast.Name) and node.func.id in {"runalg", "run", "runAndLoadResults"}:
            calls.append(node)
    return sorted(calls, key=lambda call: (call.lineno, call.col_offset))


def _resolve_name_binding(
    context: BindingContext, call: ast.Call, name: str
) -> tuple[ast.Assign | None, dict[str, Any]]:
    """Recover the one assignment that provably supplies ``name`` at this call site."""
    provenance: dict[str, Any] = {
        "name": name,
        "rule": NAME_BINDING_RULE,
        "call_scope": _scope_label(context, call),
        "assignment_lineno": None,
        "assignment_scope": None,
        "assignment_scope_verified": False,
        "dominance_verified": False,
        "mutation_guard": "not_evaluated",
        "interfering_write_lines": [],
    }
    statement = _enclosing_statement(context, call)
    call_chain = context.paths.get(statement) if statement is not None else None
    if call_chain is None:
        provenance["defer_reason"] = "call_statement_not_located"
        return None, provenance
    candidates = [
        node
        for node, chain in context.paths.items()
        if isinstance(node, ast.Assign)
        and len(node.targets) == 1
        and isinstance(node.targets[0], ast.Name)
        and node.targets[0].id == name
        and _dominates(chain, call_chain)
    ]
    provenance["dominating_assignment_lines"] = sorted(node.lineno for node in candidates)
    if not candidates:
        provenance["defer_reason"] = "no_dominating_assignment"
        return None, provenance
    if len(candidates) > 1:
        provenance["defer_reason"] = "multiple_dominating_assignments"
        return None, provenance
    chosen = candidates[0]
    provenance["dominance_verified"] = True
    provenance["assignment_lineno"] = chosen.lineno
    provenance["assignment_scope"] = _scope_label(context, chosen)
    if provenance["assignment_scope"] != provenance["call_scope"]:
        provenance["defer_reason"] = "assignment_outside_call_scope"
        return None, provenance
    provenance["assignment_scope_verified"] = True
    interfering = [line for line in _name_write_lines(context.tree, name) if chosen.lineno < line < call.lineno]
    provenance["interfering_write_lines"] = interfering
    if interfering:
        provenance["mutation_guard"] = "interfering_write_detected"
        provenance["defer_reason"] = "interfering_write_before_call"
        return None, provenance
    provenance["mutation_guard"] = "no_interfering_write"
    return chosen, provenance


def _parameter_node(call: ast.Call, context: BindingContext) -> tuple[ast.AST | None, str, dict[str, Any] | None]:
    node = call.args[1] if len(call.args) > 1 else next(
        (keyword.value for keyword in call.keywords if keyword.arg in {"parameters", "params"}), None
    )
    if isinstance(node, ast.Dict):
        return node, "inline_static_dict", None
    if isinstance(node, ast.Name):
        assignment, provenance = _resolve_name_binding(context, call, node.id)
        if assignment is None:
            return node, "unresolved_name_binding", provenance
        return assignment.value, "name_to_static_assignment", provenance
    if node is None:
        return None, "missing_parameter_argument", None
    return node, "unresolved_parameter_expression", None


def _span(node: ast.AST | None) -> dict[str, int] | None:
    if node is None or not hasattr(node, "lineno"):
        return None
    return {
        "line_start": int(node.lineno),
        "line_end": int(getattr(node, "end_lineno", None) or node.lineno),
        "column_start": int(node.col_offset),
        "column_end": int(getattr(node, "end_col_offset", None) or node.col_offset),
    }


def _completeness(status: str, entries: list[dict[str, Any]], unresolved_keys: int) -> str:
    """Report how much of the parameter payload is statically determined."""
    if status.startswith("deferred"):
        return "parameter_unresolved"
    if entries and unresolved_keys == 0 and all(entry["value_kind"] == "literal" for entry in entries):
        return "static_parameter_complete"
    return "static_parameter_partial"


def _parameter_evidence(
    source: str, node: ast.AST | None, provenance: dict[str, Any] | None = None
) -> dict[str, Any]:
    if not isinstance(node, ast.Dict):
        reason = (provenance or {}).get("defer_reason") or "parameter_expression_not_static_dict"
        return {
            "status": "deferred",
            "reason": reason,
            "source_expression": _source_segment(source, node),
            "resolved_span": _span(node),
            "keys": [],
            "values": [],
            "unresolved_key_count": 0,
            "completeness": "parameter_unresolved",
            "binding_provenance": provenance,
        }
    entries: list[dict[str, Any]] = []
    unresolved_keys = 0
    for key, value in zip(node.keys, node.values):
        key_value = _literal_or_missing(key)
        if not isinstance(key_value, str):
            unresolved_keys += 1
            continue
        literal_value = _literal_or_missing(value)
        entries.append(
            {
                "key": key_value,
                "value_expression": _source_segment(source, value),
                "value_kind": "expression" if literal_value is _MISSING else "literal",
                "literal_value": None if literal_value is _MISSING else literal_value,
            }
        )
    return {
        "status": "verified_static_dict",
        "reason": None,
        "source_expression": _source_segment(source, node),
        "resolved_span": _span(node),
        "keys": [entry["key"] for entry in entries],
        "values": entries,
        "unresolved_key_count": unresolved_keys,
        "completeness": _completeness("verified_static_dict", entries, unresolved_keys),
        "binding_provenance": provenance,
    }


def _positional_parameter_evidence(source: str, call: ast.Call) -> dict[str, Any]:
    values = []
    for index, node in enumerate(call.args[1:], start=1):
        literal_value = _literal_or_missing(node)
        values.append(
            {
                "position": index,
                "value_expression": _source_segment(source, node),
                "value_kind": "expression" if literal_value is _MISSING else "literal",
                "literal_value": None if literal_value is _MISSING else literal_value,
            }
        )
    status = "verified_positional_arguments" if values else "deferred_no_positional_arguments"
    return {
        "status": status,
        "reason": None if values else "no_positional_arguments",
        "source_expression": _source_segment(source, call),
        "resolved_span": _span(call),
        "keys": [],
        "values": values,
        "unresolved_key_count": 0,
        "completeness": _completeness(status, values, 0),
        "binding_provenance": None,
    }


def _call_evidence(source: str, call: ast.Call, operator_id: str, context: BindingContext) -> dict[str, Any]:
    operator_node = call.args[0] if call.args else None
    literal_operator = _literal(operator_node)
    if isinstance(literal_operator, str):
        resolution_kind = "literal_source_evidence"
    else:
        resolution_kind = "dynamic_source_evidence"
    entrypoint = str(call.func.attr if isinstance(call.func, ast.Attribute) else call.func.id)
    if entrypoint == "runalg":
        parameter_binding = "positional_processing_api"
        parameters = _positional_parameter_evidence(source, call)
    else:
        parameter_node, parameter_binding, provenance = _parameter_node(call, context)
        parameters = _parameter_evidence(source, parameter_node, provenance)
        if provenance is not None and parameters["resolved_span"] is not None:
            provenance["assignment_span"] = parameters["resolved_span"]
    keys = parameters["keys"]
    io_keys = [key for key in keys if key.upper() == "INPUT" or key.upper().startswith("INPUT_") or key.upper() == "OUTPUT" or key.upper().startswith("OUTPUT_")]
    provider = operator_id.split(":", 1)[0] if ":" in operator_id else None
    return {
        "operator_id": operator_id,
        "entrypoint": entrypoint,
        "resolution_kind": resolution_kind,
        "operator_expression": _source_segment(source, operator_node),
        "parameter_binding": parameter_binding,
        "parameter_evidence": parameters,
        "io_evidence": {
            "status": "parameter_keys_present" if io_keys else ("positional_arguments_present" if entrypoint == "runalg" and len(call.args) >= 3 else "no_static_io_keys"),
            "keys": io_keys,
            "input_expression": _source_segment(source, call.args[1]) if entrypoint == "runalg" and len(call.args) >= 2 else None,
            "output_expression": _source_segment(source, call.args[-1]) if entrypoint == "runalg" and len(call.args) >= 3 else None,
        },
        "provider_evidence": {
            "status": "operator_id_prefix" if provider else "provider_not_encoded",
            "provider_id": provider,
        },
        "source_span": {
            "line_start": call.lineno,
            "line_end": int(call.end_lineno or call.lineno),
            "column_start": call.col_offset,
            "column_end": int(call.end_col_offset or call.col_offset),
        },
        "source_expression": _source_segment(source, call),
    }


def extract_row(row: dict[str, Any]) -> dict[str, Any]:
    source_path = Path(str(row.get("source_path") or ""))
    declared_sha = str(row.get("source_sha256") or "")
    operator_ids = sorted(set(str(value).strip().lower() for value in row.get("processing_operator_ids") or [] if str(value).strip()))
    base = {
        "schema": SCHEMA,
        "record_id": row.get("record_id"),
        "operator_ids": operator_ids,
        "source_path": str(source_path),
        "source_sha256": declared_sha,
        "source_verified": False,
        "status": "deferred",
        "calls": [],
        "training_admission": "not_granted_candidate_only_evidence",
        "training_rows_emitted": 0,
        "provenance": {"normalized_schema": row.get("schema"), "candidate_only": True},
    }
    if not source_path.is_file():
        base["reason"] = "source_unavailable"
        return base
    payload = source_path.read_bytes()
    actual_sha = sha256_bytes(payload)
    if actual_sha != declared_sha:
        base["reason"] = "source_sha256_mismatch"
        base["actual_source_sha256"] = actual_sha
        return base
    base["source_verified"] = True
    try:
        source = payload.decode("utf-8-sig")
        tree = ast.parse(source, filename=str(source_path))
    except (UnicodeDecodeError, SyntaxError) as exc:
        base["reason"] = "source_parse_error"
        base["parse_error"] = str(exc)
        return base
    context = _binding_context(tree)
    expected = set(operator_ids)
    all_calls = _processing_calls(tree)
    calls = []
    literal_ids: set[str] = set()
    dynamic_call_count = 0
    for call in all_calls:
        literal_operator = _literal(call.args[0]) if call.args else None
        operator_id = str(literal_operator).strip().lower() if isinstance(literal_operator, str) else None
        if operator_id is None:
            dynamic_call_count += 1
            continue
        literal_ids.add(operator_id)
        if operator_id in expected:
            calls.append(_call_evidence(source, call, operator_id, context))
    base["calls"] = calls
    if not calls:
        if dynamic_call_count:
            base["reason"] = "dynamic_operator_unresolved"
        elif literal_ids:
            base["reason"] = "operator_id_mismatch"
        else:
            base["reason"] = "operator_call_not_found"
        return base
    base["status"] = "source_verified_ast"
    base["reason"] = None
    return base


def build_sidecar(rows: list[dict[str, Any]], *, expected_operator_rows: int | None = 591, asset_type: str = "processing_operator") -> tuple[list[dict[str, Any]], dict[str, Any]]:
    scoped = [row for row in rows if not asset_type or str(row.get("asset_type") or "") == asset_type]
    sidecar = [extract_row(row) for row in scoped]
    status_counts = Counter(str(row["status"]) for row in sidecar)
    reason_counts = Counter(str(row.get("reason") or "") for row in sidecar if row.get("reason"))
    calls = [call for row in sidecar for call in row["calls"]]
    name_bound = [call for call in calls if call["parameter_binding"] == "name_to_static_assignment"]
    provenances = [call["parameter_evidence"]["binding_provenance"] or {} for call in name_bound]
    summary = {
        "schema": f"{SCHEMA}.summary",
        "input_rows": len(rows),
        "operator_input_rows": len(scoped),
        "expected_operator_rows": expected_operator_rows,
        "expected_operator_rows_status": "matched" if expected_operator_rows is None or len(scoped) == expected_operator_rows else "input_incomplete_or_count_mismatch",
        "sidecar_rows": len(sidecar),
        "status_counts": dict(sorted(status_counts.items())),
        "reason_counts": dict(sorted(reason_counts.items())),
        "source_verified_rows": sum(row["source_verified"] for row in sidecar),
        "call_evidence_rows": sum(bool(row["calls"]) for row in sidecar),
        "parameter_verified_call_rows": sum(call["parameter_evidence"]["status"] == "verified_static_dict" for row in sidecar for call in row["calls"]),
        "parameter_status_counts": dict(sorted(Counter(call["parameter_evidence"]["status"] for call in calls).items())),
        "parameter_binding_counts": dict(sorted(Counter(call["parameter_binding"] for call in calls).items())),
        "parameter_completeness_counts": dict(sorted(Counter(call["parameter_evidence"]["completeness"] for call in calls).items())),
        "parameter_defer_reason_counts": dict(
            sorted(Counter(str(call["parameter_evidence"]["reason"]) for call in calls if call["parameter_evidence"]["reason"]).items())
        ),
        "name_bound_accepted_calls": len(name_bound),
        "name_bound_provenance": {
            "assignment_lineno": sum(item.get("assignment_lineno") is not None for item in provenances),
            "assignment_scope_verified": sum(bool(item.get("assignment_scope_verified")) for item in provenances),
            "dominance_verified": sum(bool(item.get("dominance_verified")) for item in provenances),
            "mutation_guard_verified": sum(item.get("mutation_guard") == "no_interfering_write" for item in provenances),
            "assignment_span": sum(item.get("assignment_span") is not None for item in provenances),
        },
        "name_binding_rule": NAME_BINDING_RULE,
        "io_key_evidence_call_rows": sum(call["io_evidence"]["status"] == "parameter_keys_present" for row in sidecar for call in row["calls"]),
        "io_evidence_call_rows": sum(call["io_evidence"]["status"] != "no_static_io_keys" for row in sidecar for call in row["calls"]),
        "provider_prefix_evidence_call_rows": sum(call["provider_evidence"]["status"] == "operator_id_prefix" for row in sidecar for call in row["calls"]),
        "l3_mapping": "unchanged",
        "training_admission": "not_granted_candidate_only_evidence_sidecar",
        "training_rows_emitted": 0,
        "formal_authority_modified": False,
    }
    return sidecar, summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-ledger", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--expected-operator-rows", type=int, default=591)
    parser.add_argument("--asset-type", default="processing_operator")
    args = parser.parse_args()
    sidecar, summary = build_sidecar(read_jsonl(args.input_ledger), expected_operator_rows=args.expected_operator_rows, asset_type=args.asset_type)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    sidecar_path = args.output_dir / "operator_evidence_sidecar_v1.jsonl"
    summary_path = args.output_dir / "summary_v1.json"
    report_path = args.output_dir / "sidecar_report_v1.md"
    sidecar_path.write_text("".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in sidecar), encoding="utf-8")
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    report_path.write_text(
        "# QGIS Processing operator evidence sidecar v1\n\n"
        "Source-backed evidence only; no L3 mapping or training rows are emitted.\n\n"
        + "\n".join(
            [
                f"- Input rows: **{summary['input_rows']}**",
                f"- Operator input rows: **{summary['operator_input_rows']}**",
                f"- Expected-row check: **{summary['expected_operator_rows_status']}**",
                f"- Source-verified rows: **{summary['source_verified_rows']}**",
                f"- Call-evidence rows: **{summary['call_evidence_rows']}**",
                f"- Static parameter-dict call rows: **{summary['parameter_verified_call_rows']}**",
                f"- Static INPUT/OUTPUT-key call rows: **{summary['io_key_evidence_call_rows']}**",
                f"- I/O evidence call rows (including positional): **{summary['io_evidence_call_rows']}**",
                f"- Provider-prefix evidence call rows: **{summary['provider_prefix_evidence_call_rows']}**",
                f"- Status counts: `{json.dumps(summary['status_counts'], ensure_ascii=False, sort_keys=True)}`",
                f"- Reason counts: `{json.dumps(summary['reason_counts'], ensure_ascii=False, sort_keys=True)}`",
                f"- Parameter status counts: `{json.dumps(summary['parameter_status_counts'], ensure_ascii=False, sort_keys=True)}`",
                f"- Parameter binding counts: `{json.dumps(summary['parameter_binding_counts'], ensure_ascii=False, sort_keys=True)}`",
                f"- Parameter completeness counts: `{json.dumps(summary['parameter_completeness_counts'], ensure_ascii=False, sort_keys=True)}`",
                f"- Parameter defer reasons: `{json.dumps(summary['parameter_defer_reason_counts'], ensure_ascii=False, sort_keys=True)}`",
                f"- Name-binding rule: `{summary['name_binding_rule']}`",
                f"- Name-bound accepted calls: **{summary['name_bound_accepted_calls']}**",
                f"- Name-bound provenance: `{json.dumps(summary['name_bound_provenance'], ensure_ascii=False, sort_keys=True)}`",
                "- L3 mapping changed: **false**",
                "- Training rows emitted: **0**",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    hashes = {path.name: sha256_bytes(path.read_bytes()) for path in (sidecar_path, summary_path, report_path)}
    hashes["input_ledger"] = sha256_bytes(args.input_ledger.read_bytes())
    (args.output_dir / "hash_ledger_v1.json").write_text(json.dumps(hashes, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
