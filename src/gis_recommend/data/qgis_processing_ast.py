"""Fail-closed AST lookup for literal Processing parameter dictionaries."""

from __future__ import annotations

import ast
from typing import Any


def _scope_for_line(tree: ast.AST, line: int) -> ast.Module | ast.FunctionDef | ast.AsyncFunctionDef:
    scopes: list[ast.Module | ast.FunctionDef | ast.AsyncFunctionDef] = [tree]  # type: ignore[list-item]
    scopes.extend(
        node
        for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and node.lineno <= line <= int(node.end_lineno or node.lineno)
    )
    return min(
        scopes,
        key=lambda node: int(getattr(node, "end_lineno", 10**9) or 10**9)
        - int(getattr(node, "lineno", 0) or 0),
    )


def _nearest_direct_assignment(
    scope: ast.Module | ast.FunctionDef | ast.AsyncFunctionDef,
    name: str,
    before_line: int,
    before_column: int,
) -> ast.AST | None:
    matches = []
    for statement in scope.body:
        if not isinstance(statement, ast.Assign) or (
            statement.lineno,
            statement.col_offset,
        ) >= (before_line, before_column):
            continue
        if any(isinstance(target, ast.Name) and target.id == name for target in statement.targets):
            matches.append(statement)
    if not matches:
        return None
    return max(matches, key=lambda node: node.lineno).value


def _processing_calls(tree: ast.AST, operator_id: str) -> list[ast.Call]:
    calls = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
            continue
        if node.func.attr != "run" or not isinstance(node.func.value, ast.Name):
            continue
        if node.func.value.id != "processing" or not node.args:
            continue
        if not isinstance(node.args[0], ast.Constant) or node.args[0].value != operator_id:
            continue
        calls.append(node)
    return sorted(calls, key=lambda node: (node.lineno, node.col_offset))


def processing_parameter_nodes(
    tree: ast.AST, operator_id: str, parameter_name: str
) -> list[dict[str, Any]]:
    """Return one static parameter AST node or a reason for each matching call."""
    output = []
    for call in _processing_calls(tree, operator_id):
        scope = _scope_for_line(tree, call.lineno)
        params: ast.AST | None = call.args[1] if len(call.args) >= 2 else next(
            (keyword.value for keyword in call.keywords if keyword.arg == "parameters"),
            None,
        )
        if isinstance(params, ast.Name):
            params = _nearest_direct_assignment(
                scope, params.id, call.lineno, call.col_offset
            )
        value: ast.AST | None = None
        if isinstance(params, ast.Dict):
            for key, candidate in zip(params.keys, params.values):
                if isinstance(key, ast.Constant) and key.value == parameter_name:
                    value = candidate
                    break
        if isinstance(value, ast.Name):
            value = _nearest_direct_assignment(
                scope, value.id, call.lineno, call.col_offset
            )
        output.append(
            {
                "call": call,
                "parameter_node": value,
                "reason": "resolved_static_parameter"
                if value is not None
                else "parameter_not_static_dict",
            }
        )
    return output
