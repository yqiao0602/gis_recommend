"""Fail-closed cross-function expansion for QGIS Processing helpers.

The pass deliberately recognizes one narrow source pattern.  It never rewrites
source text: successful results retain both the helper and caller spans so an
adapter can feed the existing Processing L3/description/dedup gates.
"""

from __future__ import annotations

import ast
import hashlib
import json
from collections.abc import Callable, Mapping
from typing import Any

PASS_VERSION = "cross_function_inline_v1_2"
_PROCESSING_METHODS = {"run", "runandloadresults", "runalg"}
_CONTROL_NODES = (ast.If, ast.For, ast.AsyncFor, ast.While, ast.Try, ast.With, ast.AsyncWith)
_NOT_LITERAL = object()


def _span(node: ast.AST) -> dict[str, int]:
    return {
        "line_start": int(getattr(node, "lineno", 0)),
        "line_end": int(getattr(node, "end_lineno", getattr(node, "lineno", 0))),
    }


def _parents(tree: ast.AST) -> dict[ast.AST, ast.AST]:
    return {
        child: parent
        for parent in ast.walk(tree)
        for child in ast.iter_child_nodes(parent)
    }


def _scope(node: ast.AST, parents: Mapping[ast.AST, ast.AST]) -> ast.AST:
    current = node
    while current in parents:
        current = parents[current]
        if isinstance(current, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Module)):
            return current
    return current


def _is_processing_call(node: ast.AST) -> bool:
    return (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr.lower() in _PROCESSING_METHODS
        and isinstance(node.func.value, ast.Name)
        and node.func.value.id == "processing"
    )


def _literal(value: ast.AST) -> Any:
    try:
        return ast.literal_eval(value)
    except (ValueError, TypeError, MemoryError, RecursionError):
        return _NOT_LITERAL


def _operator_id(call: ast.Call) -> str | None:
    if not call.args or not isinstance(call.args[0], ast.Constant):
        return None
    value = call.args[0].value
    if not isinstance(value, str) or ":" not in value:
        return None
    return value.strip().lower() or None


def _parameter_dict(call: ast.Call) -> ast.Dict | None:
    if len(call.args) < 2 or not isinstance(call.args[1], ast.Dict):
        return None
    return call.args[1]


def _assignment_target(node: ast.AST) -> str | None:
    if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
        return node.targets[0].id
    if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
        return node.target.id
    return None


def _call_assignment(call: ast.Call, parents: Mapping[ast.AST, ast.AST]) -> tuple[ast.AST, str] | None:
    parent = parents.get(call)
    target = _assignment_target(parent) if parent is not None else None
    return (parent, target) if parent is not None and target else None


def _has_control_ancestor(
    node: ast.AST, scope: ast.AST, parents: Mapping[ast.AST, ast.AST]
) -> bool:
    current = node
    while current in parents:
        current = parents[current]
        if current is scope:
            return False
        if isinstance(current, _CONTROL_NODES):
            return True
    return False


def _dict_value_uses_name(value: ast.AST, name: str) -> bool:
    return any(
        isinstance(child, ast.Name) and isinstance(child.ctx, ast.Load) and child.id == name
        for child in ast.walk(value)
    )


def _function_parameter_names(function: ast.AST) -> set[str]:
    if not isinstance(function, (ast.FunctionDef, ast.AsyncFunctionDef)):
        return set()
    arguments = function.args
    return {
        argument.arg
        for argument in [*arguments.posonlyargs, *arguments.args, *arguments.kwonlyargs]
    } | ({arguments.vararg.arg} if arguments.vararg else set()) | ({arguments.kwarg.arg} if arguments.kwarg else set())


def _is_parameter_as_assignment(node: ast.AST) -> bool:
    value = node.value if isinstance(node, (ast.Assign, ast.AnnAssign)) else None
    return (
        isinstance(value, ast.Call)
        and isinstance(value.func, ast.Attribute)
        and value.func.attr.startswith("parameterAs")
    )


def _external_roots(scope: ast.AST) -> set[str]:
    roots = _function_parameter_names(scope)
    for statement in getattr(scope, "body", []):
        target = _assignment_target(statement)
        if target and _is_parameter_as_assignment(statement):
            roots.add(target)
    return roots


def _source_segment(source_text: str, node: ast.AST) -> str:
    lines = source_text.splitlines()
    start = max(1, int(getattr(node, "lineno", 1)))
    end = max(start, int(getattr(node, "end_lineno", start)))
    return "\n".join(lines[start - 1 : end])


def _unit_id(record_id: str, source_sha256: str, helper_call: ast.Call, consumer: ast.Call, operators: list[str]) -> str:
    payload = {
        "record_id": record_id,
        "source_sha256": source_sha256,
        "helper_line": int(helper_call.lineno),
        "consumer_line": int(consumer.lineno),
        "operators": operators,
    }
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def _deferred(helper_name: str, reason: str, helper: ast.AST | None = None) -> dict[str, Any]:
    return {
        "helper_name": helper_name,
        "status": "deferred",
        "reason": reason,
        "helper_span": _span(helper) if helper is not None else None,
        "recovery_method": PASS_VERSION,
    }


def _validate_helper(
    helper: ast.FunctionDef,
) -> tuple[list[tuple[ast.Call, ast.Dict]], str, list[str]] | str:
    """Validate a helper under the v1.2 multi-chain whitelist.

    Accepted body shape (docstring optional):
        <linear Assign statements only>            # static dicts, result[key] reads
        r1 = processing.run(OP_LITERAL, DICT)      # one or more, forming a chain
        r2 = processing.run(OP_LITERAL, DICT)
        ...
        return r_last["FIXED_KEY"]

    Every statement before the return must be a plain single-target Name
    assignment.  Parameter-dict values may be: helper parameters, literals,
    or the extracted output key of an earlier processing call in the same
    helper (r_k["KEY"]).  No control flow, no other calls, no side effects.
    """

    body = list(helper.body)
    if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant) and isinstance(body[0].value.value, str):
        body = body[1:]
    if len(body) < 2 or not isinstance(body[-1], ast.Return):
        return "helper_body_not_linear_whitelisted"

    parameter_names = _function_parameter_names(helper)
    defaults = {
        argument.arg
        for argument, default in zip(helper.args.args[-len(helper.args.defaults) :], helper.args.defaults)
        if _literal(default) is not _NOT_LITERAL
    }
    if len(defaults) != len(helper.args.defaults):
        return "helper_default_not_literal"

    local_dicts: dict[str, ast.Dict] = {}
    processing_assignments: list[tuple[ast.Assign, str]] = []
    for statement in body[:-1]:
        if not isinstance(statement, ast.Assign) or len(statement.targets) != 1:
            return "helper_linear_statement_not_whitelisted"
        name = _assignment_target(statement)
        if not name:
            return "helper_linear_statement_not_whitelisted"
        if _is_processing_call(statement.value):
            processing_assignments.append((statement, name))
        elif isinstance(statement.value, ast.Dict):
            local_dicts[name] = statement.value
        elif _is_result_key_read(statement.value):
            continue
        else:
            return "helper_linear_statement_not_whitelisted"
    if not processing_assignments:
        return "helper_requires_one_processing_assignment"

    processing_results: dict[str, ast.Call] = {}
    calls: list[tuple[ast.Call, ast.Dict]] = []
    for statement, result_name in processing_assignments:
        call = statement.value
        if len(call.args) >= 2 and isinstance(call.args[1], ast.Name):
            if call.args[1].id not in local_dicts:
                return "helper_processing_parameter_dict_not_local_static"
            call = ast.Call(func=call.func, args=[call.args[0], local_dicts[call.args[1].id]], keywords=call.keywords)
            ast.copy_location(call, statement.value)
        params = _parameter_dict(call)
        operator_id = _operator_id(call)
        if not params or not operator_id:
            return "helper_operator_not_static_literal"
        for key, value in zip(params.keys, params.values):
            if not isinstance(key, ast.Constant) or not isinstance(key.value, str) or value is None:
                return "helper_parameter_dict_not_static"
            if isinstance(value, ast.Name):
                if value.id not in parameter_names:
                    return "helper_parameter_uses_non_parameter_name"
            elif _is_result_key_read(value):
                if not isinstance(value.value, ast.Name) or value.value.id not in processing_results:
                    return "helper_parameter_uses_unknown_chain_result"
            elif _literal(value) is _NOT_LITERAL:
                return "helper_parameter_value_not_literal_or_parameter"
        calls.append((call, params))
        processing_results[result_name] = call

    returned = body[-1].value
    if not (
        isinstance(returned, ast.Subscript)
        and isinstance(returned.value, ast.Name)
        and returned.value.id in processing_results
        and isinstance(returned.slice, ast.Constant)
        and isinstance(returned.slice.value, str)
    ):
        return "helper_return_not_fixed_result_key"
    return calls, str(returned.slice.value), sorted(parameter_names)


def _is_result_key_read(value: ast.AST) -> bool:
    """True for r_name["KEY"] reads of a previous processing result."""
    return (
        isinstance(value, ast.Subscript)
        and isinstance(value.value, ast.Name)
        and isinstance(value.slice, ast.Constant)
        and isinstance(value.slice.value, str)
    )


def expand_cross_function_helpers(
    source_text: str,
    *,
    record_id: str,
    source_sha256: str,
    catalog_operator_ids: set[str] | None = None,
    geographic_input_parameter: Callable[[str, str], bool] | None = None,
) -> dict[str, list[dict[str, Any]]]:
    """Return expanded units and explicit deferred evidence for v1 helper calls."""

    try:
        tree = ast.parse(source_text)
    except SyntaxError:
        return {"units": [], "deferred": [{"status": "excluded", "reason": "excluded_unparseable"}]}
    parents = _parents(tree)
    functions = [node for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)]
    statically_called_names = {
        node.func.id
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
    }
    units: list[dict[str, Any]] = []
    deferred: list[dict[str, Any]] = []
    geo_input = geographic_input_parameter or (lambda _operator, key: key == "INPUT")
    skipped_non_processing = 0

    for helper in functions:
        if helper.name not in statically_called_names:
            continue
        if isinstance(parents.get(helper), (ast.FunctionDef, ast.AsyncFunctionDef)):
            deferred.append(_deferred(helper.name, "nested_helper_not_supported", helper))
            continue
        if not any(_is_processing_call(node) for node in ast.walk(helper)):
            skipped_non_processing += 1
            continue
        validated = _validate_helper(helper)
        if isinstance(validated, str):
            deferred.append(_deferred(helper.name, validated, helper))
            continue
        processing_calls, returned_key, helper_parameter_names = validated
        chain_operators = [_operator_id(call) for call, _ in processing_calls]
        assert all(operator is not None for operator in chain_operators)
        if catalog_operator_ids is not None and any(
            operator not in catalog_operator_ids for operator in chain_operators
        ):
            deferred.append(_deferred(helper.name, "helper_operator_catalog_miss", helper))
            continue
        if len(chain_operators) > 5:
            deferred.append(_deferred(helper.name, "helper_chain_too_long", helper))
            continue
        calls = [
            node for node in ast.walk(tree)
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == helper.name
        ]
        if len(calls) != 1:
            deferred.append(_deferred(helper.name, "helper_requires_exactly_one_static_caller", helper))
            continue
        caller_call = calls[0]
        caller_scope = _scope(caller_call, parents)
        if _has_control_ancestor(caller_call, caller_scope, parents):
            deferred.append(_deferred(helper.name, "caller_control_flow_not_supported", helper))
            continue
        assignment = _call_assignment(caller_call, parents)
        if assignment is None:
            deferred.append(_deferred(helper.name, "caller_result_not_assigned", helper))
            continue
        _, output_name = assignment
        if caller_call.keywords or len(caller_call.args) > len(helper_parameter_names):
            deferred.append(_deferred(helper.name, "caller_argument_binding_not_one_to_one", helper))
            continue
        helper_args = list(helper.args.args)
        required_count = len(helper_args) - len(helper.args.defaults)
        if len(caller_call.args) < required_count:
            deferred.append(_deferred(helper.name, "caller_argument_binding_missing_required", helper))
            continue
        bindings: dict[str, ast.AST] = {}
        for argument, value in zip(helper_args, caller_call.args):
            if not isinstance(value, (ast.Name, ast.Constant)):
                deferred.append(_deferred(helper.name, "caller_argument_not_name_or_literal", helper))
                break
            bindings[argument.arg] = value
        else:
            for argument, default in zip(helper_args[-len(helper.args.defaults) :], helper.args.defaults):
                bindings.setdefault(argument.arg, default)
            roots = _external_roots(caller_scope)
            input_names = {
                value.id
                for call, params in processing_calls
                for key, value in zip(params.keys, params.values)
                if isinstance(key, ast.Constant) and key.value == "INPUT" and isinstance(value, ast.Name)
            }
            if any(
                not isinstance(bindings.get(name), ast.Name) or bindings[name].id not in roots
                for name in input_names
            ):
                deferred.append(_deferred(helper.name, "external_input_root_not_proven", helper))
                continue
            consumer_matches: list[tuple[ast.Call, ast.Dict, ast.Constant]] = []
            control_flow_consumers = 0
            for candidate in ast.walk(caller_scope):
                if not _is_processing_call(candidate) or int(candidate.lineno) <= int(caller_call.lineno):
                    continue
                params = _parameter_dict(candidate)
                operator = _operator_id(candidate)
                if not params or not operator:
                    continue
                for key, value in zip(params.keys, params.values):
                    if (
                        isinstance(key, ast.Constant)
                        and isinstance(key.value, str)
                        and value is not None
                        and _dict_value_uses_name(value, output_name)
                        and geo_input(operator, key.value)
                    ):
                        if _has_control_ancestor(candidate, caller_scope, parents):
                            control_flow_consumers += 1
                        else:
                            consumer_matches.append((candidate, params, key))
            if len(consumer_matches) != 1:
                if control_flow_consumers and not consumer_matches:
                    deferred.append(_deferred(helper.name, "consumer_control_flow_not_supported", helper))
                else:
                    deferred.append(_deferred(helper.name, "caller_requires_one_geographic_processing_consumer", helper))
                continue
            consumer, _, consumer_key = consumer_matches[0]
            consumer_operator = _operator_id(consumer)
            assert consumer_operator is not None
            if catalog_operator_ids is not None and consumer_operator not in catalog_operator_ids:
                deferred.append(_deferred(helper.name, "consumer_operator_catalog_miss", helper))
                continue
            all_uses = [
                node for node in ast.walk(caller_scope)
                if isinstance(node, ast.Name)
                and isinstance(node.ctx, ast.Load)
                and node.id == output_name
                and int(node.lineno) > int(caller_call.lineno)
            ]
            consumer_uses = [
                node for node in ast.walk(consumer)
                if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load) and node.id == output_name
            ]
            if len(all_uses) != 1 or len(consumer_uses) != 1:
                deferred.append(_deferred(helper.name, "caller_output_has_nonconsumer_or_multiple_use", helper))
                continue
            operators = [*chain_operators, consumer_operator]
            dependency_edges = [[index, index + 1] for index in range(len(chain_operators))]
            parameter_binding_chain = []
            for call, params in processing_calls:
                for key, value in zip(params.keys, params.values):
                    assert isinstance(key, ast.Constant) and isinstance(key.value, str)
                    helper_parameter = value.id if isinstance(value, ast.Name) else None
                    binding = {
                        "processing_key": key.value,
                        "processing_value_span": _span(value),
                        "helper_parameter": helper_parameter,
                        "caller_expression": (
                            ast.unparse(bindings[value.id])
                            if isinstance(value, ast.Name)
                            else ast.unparse(value)
                        ),
                        "caller_expression_span": (
                            _span(bindings[value.id]) if isinstance(value, ast.Name) else _span(value)
                        ),
                        "binding_status": "verified",
                        "value_status": (
                            "workflow_parameter"
                            if isinstance(value, ast.Name) and isinstance(bindings[value.id], ast.Name)
                            else "literal"
                        ),
                    }
                    parameter_binding_chain.append(binding)
            caller_container = caller_scope if isinstance(caller_scope, (ast.FunctionDef, ast.AsyncFunctionDef)) else consumer
            unit = {
                "schema": "gis_recommend.qgis_expanded_local_unit.v1",
                "unit_id": _unit_id(record_id, source_sha256, processing_calls[0][0], consumer, operators),
                "record_id": record_id,
                "source_sha256": source_sha256,
                "canonical_operator_ids": operators,
                "operator_ids": operators,
                "dependency_edges": dependency_edges,
                "workflow_scope": getattr(caller_scope, "name", "module"),
                "workflow_unit_scope": "expanded_local_subworkflow",
                "call_sites": [
                    {"operator_id": operator, **_span(call), "origin": "helper"}
                    for operator, (call, _) in zip(chain_operators, processing_calls)
                ]
                + [{"operator_id": consumer_operator, **_span(consumer), "origin": "caller_consumer"}],
                "source_segments": {
                    "helper": _source_segment(source_text, helper),
                    "caller": _source_segment(source_text, caller_container),
                },
                "parameter_binding_chain": parameter_binding_chain,
                "expansion_proof": {
                    "pass_version": PASS_VERSION,
                    "helper_name": helper.name,
                    "helper_return_key": returned_key,
                    "caller_output_name": output_name,
                    "consumer_parameter_key": consumer_key.value,
                    "whitelist_checks": [
                        "helper_body_whitelisted",
                        "single_static_caller",
                        "one_to_one_argument_binding",
                        "external_input_root_proven",
                        "single_geographic_processing_consumer",
                        "single_consumer_use",
                    ],
                },
                "recovery_method": PASS_VERSION,
                "call_span_verification": "verified_cross_function_inline_v1",
                "training_admission": "not_granted_pending_boundary_l3_description_dedup",
                "training_row_emitted": False,
                "validation_eligible": False,
                "test_eligible": False,
                "production_merge": "not_granted",
            }
            units.append(unit)
    return {
        "units": units,
        "deferred": deferred,
        "skipped_non_processing_helpers": skipped_non_processing,
    }
