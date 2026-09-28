"""Fail-closed admission gate for complete output-backed GEE workflow DAGs."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable

from gis_recommend.data.gee_dataflow_slicer import DataflowDefinition, build_backward_slices


_CONTROL_FLOW_NODES = frozenset(
    {
        "DoWhileStatement",
        "ForInStatement",
        "ForOfStatement",
        "ForStatement",
        "IfStatement",
        "SwitchStatement",
        "TryStatement",
        "WhileStatement",
        "WithStatement",
    }
)

_NATIVE_COLLECTION_MUTATORS = frozenset({"push", "splice", "unshift"})
_CALLBACK_SUPPORT_METHODS = frozenset(
    {"copyproperties", "get", "propertynames", "set"}
)
_BARE_OUTPUT_METHODS = frozenset(
    {
        "tobyte",
        "todouble",
        "tofloat",
        "tofloat32",
        "toint",
        "toint8",
        "toint16",
        "toint32",
        "tolong",
        "toshort",
        "touint8",
        "touint16",
        "touint32",
    }
)
_NATIVE_OPERATOR_EXPRESSION_TYPES = frozenset({"BinaryExpression", "LogicalExpression"})


@dataclass(frozen=True)
class OutputWorkflowDag:
    workflow_id: str
    sink_root_id: str
    sink_line: int
    definition_ids: tuple[str, ...]
    dependency_edges: tuple[tuple[str, str], ...]
    core_call_ordinals: tuple[int, ...]
    core_raw_callees: tuple[str, ...]
    external_input_identifiers: tuple[str, ...]
    unresolved_identifiers: tuple[str, ...]
    status: str
    fail_closed_reasons: tuple[str, ...]


@dataclass(frozen=True)
class OutputWorkflowDagResult:
    source_status: str
    workflows: tuple[OutputWorkflowDag, ...]
    source_fail_closed_reasons: tuple[str, ...]
    slicer_quality_flags: tuple[str, ...]


def _location(node: Any) -> tuple[int, int] | None:
    if not isinstance(node, dict):
        return None
    location = node.get("loc")
    if not isinstance(location, dict):
        return None
    start = location.get("start")
    end = location.get("end")
    if not isinstance(start, dict) or not isinstance(end, dict):
        return None
    start_line = start.get("line")
    end_line = end.get("line")
    if not isinstance(start_line, int) or not isinstance(end_line, int):
        return None
    return start_line, end_line


def _call_location(call: dict[str, Any]) -> tuple[int, int] | None:
    location = call.get("source_location")
    if not isinstance(location, dict):
        return None
    start_line = location.get("start_line")
    end_line = location.get("end_line")
    if not isinstance(start_line, int) or not isinstance(end_line, int):
        return None
    return start_line, end_line


def _call_source_span(call: dict[str, Any]) -> tuple[int, int, int, int] | None:
    location = call.get("source_location")
    if not isinstance(location, dict):
        return None
    values = tuple(
        location.get(key)
        for key in ("start_line", "start_column", "end_line", "end_column")
    )
    return values if all(isinstance(value, int) for value in values) else None  # type: ignore[return-value]


def _contains(ranges: tuple[tuple[int, int], ...], location: tuple[int, int] | None) -> bool:
    if location is None:
        return False
    return any(start <= location[0] and location[1] <= end for start, end in ranges)


def _has_control_flow(node: Any, ranges: tuple[tuple[int, int], ...]) -> bool:
    if isinstance(node, list):
        return any(_has_control_flow(child, ranges) for child in node)
    if not isinstance(node, dict):
        return False
    if node.get("type") in _CONTROL_FLOW_NODES and _contains(ranges, _location(node)):
        return True
    return any(
        _has_control_flow(value, ranges)
        for key, value in node.items()
        if key not in {"loc", "range"}
    )


def _static_callee(node: Any) -> str | None:
    if not isinstance(node, dict):
        return None
    if node.get("type") == "Identifier":
        name = node.get("name")
        return name if isinstance(name, str) else None
    if node.get("type") != "MemberExpression" or node.get("computed"):
        return None
    root = _static_callee(node.get("object"))
    prop = node.get("property")
    name = prop.get("name") if isinstance(prop, dict) and prop.get("type") == "Identifier" else None
    if root is None or not isinstance(name, str):
        return None
    return f"{root}.{name}"


def _static_member_name(node: Any) -> str | None:
    if not isinstance(node, dict) or node.get("type") != "MemberExpression" or node.get("computed"):
        return None
    prop = node.get("property")
    if not isinstance(prop, dict) or prop.get("type") != "Identifier":
        return None
    name = prop.get("name")
    return name if isinstance(name, str) else None


def _walk(node: Any) -> Iterable[dict[str, Any]]:
    if isinstance(node, dict):
        yield node
        for key, value in node.items():
            if key not in {"loc", "range"}:
                yield from _walk(value)
    elif isinstance(node, list):
        for value in node:
            yield from _walk(value)


def _walk_executable_statement(node: Any) -> Iterable[dict[str, Any]]:
    """Walk a top-level executable statement without entering nested functions."""

    if isinstance(node, dict):
        yield node
        if node.get("type") in {
            "ArrowFunctionExpression",
            "FunctionDeclaration",
            "FunctionExpression",
        }:
            return
        for key, value in node.items():
            if key not in {"loc", "range"}:
                yield from _walk_executable_statement(value)
    elif isinstance(node, list):
        for value in node:
            yield from _walk_executable_statement(value)


def _mutated_target_root(
    node: dict[str, Any], *, allow_identifier_assignment: bool = False
) -> str | None:
    target: Any = None
    is_native_collection_mutator = False
    if node.get("type") == "CallExpression":
        callee = node.get("callee")
        method = str(_static_member_name(callee) or "").casefold()
        if method not in _NATIVE_COLLECTION_MUTATORS or not isinstance(callee, dict):
            return None
        target = callee.get("object")
        is_native_collection_mutator = True
    elif node.get("type") == "AssignmentExpression":
        target = node.get("left")
    elif node.get("type") == "UpdateExpression":
        target = node.get("argument")
    else:
        return None

    if not isinstance(target, dict):
        return None
    if target.get("type") == "Identifier":
        if not is_native_collection_mutator and not allow_identifier_assignment:
            return None
        name = target.get("name")
        return name if isinstance(name, str) else None
    if target.get("type") != "MemberExpression":
        return None
    if not target.get("computed"):
        return None
    property_node = target.get("property")
    if (
        isinstance(property_node, dict)
        and property_node.get("type") == "Literal"
        and isinstance(property_node.get("value"), str)
    ):
        return None
    receiver = _static_callee(target.get("object"))
    return receiver.split(".", 1)[0] if receiver else None


def _array_binding_names(ast: dict[str, Any]) -> frozenset[str]:
    names: set[str] = set()
    for node in _walk(ast):
        if node.get("type") == "VariableDeclarator":
            identifier = node.get("id")
            value = node.get("init")
        elif node.get("type") == "AssignmentExpression":
            identifier = node.get("left")
            value = node.get("right")
        else:
            continue
        name = identifier.get("name") if isinstance(identifier, dict) else None
        if isinstance(name, str) and isinstance(value, dict) and value.get("type") == "ArrayExpression":
            names.add(name)
    return frozenset(names)


def _executable_mutation_targets(ast: dict[str, Any]) -> tuple[tuple[str, int], ...]:
    """Collect client-side mutations outside callback bodies once per AST."""

    body = ast.get("body") if ast.get("type") == "Program" else None
    if not isinstance(body, list):
        return ()
    array_bindings = _array_binding_names(ast)
    mutations: list[tuple[str, int]] = []
    for statement in body:
        statement_location = _location(statement)
        if statement_location is None:
            continue
        for node in _walk_executable_statement(statement):
            root = _mutated_target_root(node)
            location = _location(node) or statement_location
            is_native_collection_mutator = node.get("type") == "CallExpression"
            if root is not None and (
                is_native_collection_mutator or root in array_bindings
            ):
                mutations.append((root, location[0]))
    return tuple(mutations)


def _has_retained_mutation(
    mutations: tuple[tuple[str, int], ...],
    retained_definitions: tuple[DataflowDefinition, ...],
    sink_line: int,
) -> bool:
    definition_start_by_target = {
        definition.target: definition.start_line
        for definition in retained_definitions
    }
    if not definition_start_by_target:
        return False
    return any(
        root in definition_start_by_target
        and definition_start_by_target[root] <= line <= sink_line
        for root, line in mutations
    )


def _has_top_level_throw_before_sink(ast: dict[str, Any], sink_line: int) -> bool:
    body = ast.get("body") if ast.get("type") == "Program" else None
    if not isinstance(body, list):
        return False
    for statement in body:
        if not isinstance(statement, dict) or statement.get("type") != "ThrowStatement":
            continue
        location = _location(statement)
        if location is not None and location[0] < sink_line:
            return True
    return False


def _has_native_operator_on_retained_ee_dependency(
    ast: dict[str, Any],
    retained_definitions: tuple[DataflowDefinition, ...],
    retained_core_calls: tuple[dict[str, Any], ...],
    sink_line: int,
) -> bool:
    """Reject JavaScript operators applied to server-side EE objects.

    Earth Engine objects must use methods such as ``subtract`` or ``and``.
    Native JavaScript operators coerce those objects client-side, so a sink
    depending on such an expression is not a faithful executable workflow.
    """

    def referenced_identifiers(node: Any) -> set[str]:
        if isinstance(node, list):
            return set().union(*(referenced_identifiers(item) for item in node))
        if not isinstance(node, dict):
            return set()
        if node.get("type") == "Identifier":
            name = node.get("name")
            return {name} if isinstance(name, str) else set()
        if node.get("type") == "MemberExpression":
            names = referenced_identifiers(node.get("object"))
            if node.get("computed"):
                names.update(referenced_identifiers(node.get("property")))
            return names
        if node.get("type") == "Property":
            names = referenced_identifiers(node.get("value"))
            if node.get("computed"):
                names.update(referenced_identifiers(node.get("key")))
            return names
        names: set[str] = set()
        for key, value in node.items():
            if key not in {"loc", "range"}:
                names.update(referenced_identifiers(value))
        return names

    def definition_expression(definition: DataflowDefinition) -> dict[str, Any] | None:
        body = ast.get("body") if ast.get("type") == "Program" else None
        if not isinstance(body, list) or not 0 <= definition.statement_index < len(body):
            return None
        statement = body[definition.statement_index]
        if not isinstance(statement, dict):
            return None
        if statement.get("type") == "VariableDeclaration":
            for declaration in statement.get("declarations") or []:
                if not isinstance(declaration, dict):
                    continue
                identifier = declaration.get("id")
                if (
                    isinstance(identifier, dict)
                    and identifier.get("type") == "Identifier"
                    and identifier.get("name") == definition.target
                ):
                    init = declaration.get("init")
                    return init if isinstance(init, dict) else None
            return None
        if statement.get("type") != "ExpressionStatement":
            return statement
        expression = statement.get("expression")
        candidates = (
            expression.get("expressions") or []
            if isinstance(expression, dict)
            and expression.get("type") == "SequenceExpression"
            else (expression,)
        )
        for candidate in candidates:
            if (
                isinstance(candidate, dict)
                and candidate.get("type") == "AssignmentExpression"
                and candidate.get("operator") == "="
                and _static_callee(candidate.get("left")) == definition.target
            ):
                right = candidate.get("right")
                return right if isinstance(right, dict) else None
        return expression if isinstance(expression, dict) else None

    def export_payload() -> dict[str, Any] | None:
        for statement in ast.get("body", []):
            if not isinstance(statement, dict) or not _contains(
                (_location(statement) or (-1, -1),),
                (sink_line, sink_line),
            ):
                continue
            for node in _walk(statement):
                if node.get("type") != "CallExpression":
                    continue
                callee = str(_static_callee(node.get("callee")) or "")
                if callee.startswith("Export.image"):
                    payload_key = "image"
                elif callee.startswith("Export.table"):
                    payload_key = "collection"
                else:
                    continue
                arguments = node.get("arguments") or []
                first = arguments[0] if arguments else None
                if not isinstance(first, dict):
                    return None
                if first.get("type") != "ObjectExpression":
                    return first
                for prop in first.get("properties") or []:
                    if not isinstance(prop, dict) or prop.get("type") != "Property":
                        continue
                    key = prop.get("key")
                    key_name = None
                    if isinstance(key, dict) and key.get("type") == "Identifier":
                        key_name = key.get("name")
                    elif isinstance(key, dict) and key.get("type") == "Literal":
                        key_name = key.get("value")
                    value = prop.get("value")
                    if key_name == payload_key and isinstance(value, dict):
                        return value
                return None
        return None

    payload_node = export_payload()
    if payload_node is None:
        return False

    definitions_by_id = {
        definition.definition_id: definition for definition in retained_definitions
    }
    latest_definition_by_target: dict[str, DataflowDefinition] = {}
    for definition in retained_definitions:
        previous = latest_definition_by_target.get(definition.target)
        if previous is None or (definition.start_line, definition.version) > (
            previous.start_line,
            previous.version,
        ):
            latest_definition_by_target[definition.target] = definition

    payload_definition_ids = {
        latest_definition_by_target[name].definition_id
        for name in referenced_identifiers(payload_node)
        if name in latest_definition_by_target
    }
    pending = list(payload_definition_ids)
    while pending:
        definition = definitions_by_id.get(pending.pop())
        if definition is None:
            continue
        for dependency_id in definition.dependency_ids:
            if (
                dependency_id in definitions_by_id
                and dependency_id not in payload_definition_ids
            ):
                payload_definition_ids.add(dependency_id)
                pending.append(dependency_id)

    client_value_definition_ids = {
        definition.definition_id
        for definition in retained_definitions
        if definition.definition_id in payload_definition_ids
        if any(
            node.get("type") == "CallExpression"
            and str(_static_member_name(node.get("callee")) or "").casefold()
            == "getinfo"
            for node in _walk(definition_expression(definition))
        )
    }

    def definition_location(definition: DataflowDefinition) -> tuple[int, int]:
        return _location(definition_expression(definition)) or (
            definition.start_line,
            definition.end_line,
        )

    ee_backed_ids = {
        definition.definition_id
        for definition in retained_definitions
        if definition.definition_id in payload_definition_ids
        if definition.definition_id not in client_value_definition_ids
        if any(
            _contains(
                (definition_location(definition),),
                _call_location(call),
            )
            for call in retained_core_calls
        )
    }
    changed = True
    while changed:
        changed = False
        for definition in retained_definitions:
            if (
                definition.definition_id not in payload_definition_ids
                or definition.definition_id in ee_backed_ids
                or definition.definition_id in client_value_definition_ids
            ):
                continue
            if any(
                dependency_id in ee_backed_ids
                for dependency_id in definition.dependency_ids
            ):
                ee_backed_ids.add(definition.definition_id)
                changed = True

    ee_backed_targets = {
        definitions_by_id[definition_id].target
        for definition_id in ee_backed_ids
        if definition_id in definitions_by_id
    }
    if not ee_backed_targets:
        return False

    retained_ranges = tuple(
        definition_location(definition)
        for definition in retained_definitions
        if definition.definition_id in payload_definition_ids
    )

    def has_invalid_native_operator(node: dict[str, Any]) -> bool:
        if node.get("type") not in _NATIVE_OPERATOR_EXPRESSION_TYPES:
            return False
        operand_names = referenced_identifiers(node.get("left"))
        operand_names.update(referenced_identifiers(node.get("right")))
        return bool(operand_names & ee_backed_targets)

    if any(has_invalid_native_operator(node) for node in _walk(payload_node)):
        return True
    return any(
        has_invalid_native_operator(node)
        for node in _walk(ast)
        if _contains(retained_ranges, _location(node))
    )


def _callback_mutation_targets(ast: dict[str, Any]) -> tuple[tuple[str, int], ...]:
    """Collect non-local mutations in executed higher-order callbacks once."""

    function_nodes: dict[str, dict[str, Any]] = {}
    for candidate in _walk(ast):
        if candidate.get("type") == "FunctionDeclaration":
            identifier = candidate.get("id")
            name = identifier.get("name") if isinstance(identifier, dict) else None
            if isinstance(name, str):
                function_nodes[name] = candidate
        elif candidate.get("type") == "VariableDeclarator":
            identifier = candidate.get("id")
            init = candidate.get("init")
            name = identifier.get("name") if isinstance(identifier, dict) else None
            if (
                isinstance(name, str)
                and isinstance(init, dict)
                and init.get("type") in {"ArrowFunctionExpression", "FunctionExpression"}
            ):
                function_nodes[name] = init

    mutations: list[tuple[str, int]] = []
    for node in _walk(ast):
        if node.get("type") != "CallExpression":
            continue
        location = _location(node)
        if location is None:
            continue
        if str(_static_member_name(node.get("callee")) or "").casefold() not in {
            "foreach",
            "iterate",
            "map",
        }:
            continue
        arguments = node.get("arguments") or []
        callback = arguments[0] if arguments else None
        callback_node: dict[str, Any] | None = None
        if isinstance(callback, dict) and callback.get("type") in {
            "ArrowFunctionExpression",
            "FunctionExpression",
        }:
            callback_node = callback
        elif isinstance(callback, dict) and callback.get("type") == "Identifier":
            name = callback.get("name")
            callback_node = function_nodes.get(name) if isinstance(name, str) else None
        if callback_node is None:
            continue

        local_names = {
            parameter.get("name")
            for parameter in callback_node.get("params") or []
            if isinstance(parameter, dict) and parameter.get("type") == "Identifier"
        }
        local_names.update(
            identifier.get("name")
            for child in _walk(callback_node.get("body"))
            if child.get("type") == "VariableDeclarator"
            for identifier in [child.get("id")]
            if isinstance(identifier, dict) and identifier.get("type") == "Identifier"
        )
        for child in _walk(callback_node.get("body")):
            target = _mutated_target_root(
                child, allow_identifier_assignment=True
            )
            assignment_location = _location(child) or location
            if (
                isinstance(target, str)
                and target not in local_names
            ):
                mutations.append((target, assignment_location[0]))
    return tuple(mutations)


def _function_bindings(ast: dict[str, Any]) -> dict[str, tuple[int, int]]:
    bindings: dict[str, tuple[int, int]] = {}
    for node in _walk(ast):
        node_type = node.get("type")
        if node_type == "FunctionDeclaration":
            identifier = node.get("id")
            name = identifier.get("name") if isinstance(identifier, dict) else None
            location = _location(node)
        elif node_type == "VariableDeclarator":
            identifier = node.get("id")
            init = node.get("init")
            if not isinstance(init, dict) or init.get("type") not in {
                "ArrowFunctionExpression",
                "FunctionExpression",
            }:
                continue
            name = identifier.get("name") if isinstance(identifier, dict) else None
            location = _location(init) or _location(node)
        else:
            continue
        if isinstance(name, str) and location is not None:
            bindings[name] = location
    return bindings


def _has_support_higher_order_call_with_retained_callback_core(
    ast: dict[str, Any],
    calls: tuple[dict[str, Any], ...],
    retained_core_calls: tuple[dict[str, Any], ...],
    ranges: tuple[tuple[int, int], ...],
    *,
    method: str,
) -> bool:
    normalized_method = method.casefold()
    support_calls = tuple(
        call
        for call in calls
        if call.get("classification") == "support"
        and str(call.get("raw_callee") or "").casefold().endswith(
            f".{normalized_method}"
        )
    )
    if not support_calls or not retained_core_calls:
        return False

    function_bindings = _function_bindings(ast)
    for node in _walk(ast):
        if node.get("type") != "CallExpression":
            continue
        if (
            str(_static_member_name(node.get("callee")) or "").casefold()
            != normalized_method
        ):
            continue
        call_range = _location(node)
        if call_range is None:
            continue
        if not any(
            _contains((call_range,), _call_location(call)) for call in support_calls
        ):
            continue
        arguments = node.get("arguments") or []
        callback = arguments[0] if arguments else None
        callback_range: tuple[int, int] | None = None
        if isinstance(callback, dict) and callback.get("type") in {
            "ArrowFunctionExpression",
            "FunctionExpression",
        }:
            callback_range = _location(callback)
        elif isinstance(callback, dict) and callback.get("type") == "Identifier":
            name = callback.get("name")
            callback_range = function_bindings.get(name) if isinstance(name, str) else None
        elif isinstance(callback, dict) and callback.get("type") == "CallExpression":
            callee = callback.get("callee")
            name = callee.get("name") if isinstance(callee, dict) and callee.get("type") == "Identifier" else None
            callback_range = function_bindings.get(name) if isinstance(name, str) else None
        if callback_range is not None and any(
            _contains((callback_range,), _call_location(call)) for call in retained_core_calls
        ):
            return True
    return False


def _has_incomplete_callback_core_closure(
    ast: dict[str, Any],
    calls: tuple[dict[str, Any], ...],
    retained_core_calls: tuple[dict[str, Any], ...],
    ranges: tuple[tuple[int, int], ...],
    retained_targets: frozenset[str],
) -> bool:
    support_maps = tuple(
        call
        for call in calls
        if call.get("classification") == "support"
        and str(call.get("raw_callee") or "").casefold().endswith(".map")
    )
    if not support_maps:
        return False

    retained_ordinals = {
        call.get("ordinal")
        for call in retained_core_calls
        if isinstance(call.get("ordinal"), int)
    }
    candidate_maps: list[dict[str, Any]] = []
    for statement in ast.get("body", []):
        if not isinstance(statement, dict):
            continue
        if statement.get("type") == "VariableDeclaration":
            for declaration in statement.get("declarations") or []:
                identifier = declaration.get("id") if isinstance(declaration, dict) else None
                name = identifier.get("name") if isinstance(identifier, dict) and identifier.get("type") == "Identifier" else None
                if name in retained_targets:
                    candidate_maps.extend(
                        node
                        for node in _walk(declaration.get("init"))
                        if node.get("type") == "CallExpression"
                        and str(_static_member_name(node.get("callee")) or "").casefold() == "map"
                    )
        elif statement.get("type") == "ExpressionStatement":
            expression = statement.get("expression")
            left = expression.get("left") if isinstance(expression, dict) and expression.get("type") == "AssignmentExpression" else None
            name = left.get("name") if isinstance(left, dict) and left.get("type") == "Identifier" else None
            if name in retained_targets:
                candidate_maps.extend(
                    node
                    for node in _walk(expression.get("right"))
                    if node.get("type") == "CallExpression"
                    and str(_static_member_name(node.get("callee")) or "").casefold() == "map"
                )

    function_bindings = _function_bindings(ast)
    for node in candidate_maps:
        if node.get("type") != "CallExpression":
            continue
        if str(_static_member_name(node.get("callee")) or "").casefold() != "map":
            continue
        map_range = _location(node)
        if map_range is None:
            continue
        if not any(_contains((map_range,), _call_location(call)) for call in support_maps):
            continue
        arguments = node.get("arguments") or []
        callback = arguments[0] if arguments else None
        callback_range: tuple[int, int] | None = None
        if isinstance(callback, dict) and callback.get("type") in {
            "ArrowFunctionExpression",
            "FunctionExpression",
        }:
            callback_range = _location(callback)
        elif isinstance(callback, dict) and callback.get("type") == "Identifier":
            name = callback.get("name")
            callback_range = function_bindings.get(name) if isinstance(name, str) else None
        elif isinstance(callback, dict) and callback.get("type") == "CallExpression":
            callee = callback.get("callee")
            name = callee.get("name") if isinstance(callee, dict) and callee.get("type") == "Identifier" else None
            callback_range = function_bindings.get(name) if isinstance(name, str) else None
        if callback_range is None:
            continue
        callback_ordinals = {
            call.get("ordinal")
            for call in calls
            if call.get("classification") == "core"
            and isinstance(call.get("ordinal"), int)
            and _contains((callback_range,), _call_location(call))
        }
        if callback_ordinals and not callback_ordinals <= retained_ordinals:
            return True
        retained_locations = tuple(
            _call_location(call) for call in retained_core_calls
        )
        for callback_call in _walk(ast):
            if callback_call.get("type") != "CallExpression":
                continue
            callback_call_location = _location(callback_call)
            method = str(_static_member_name(callback_call.get("callee")) or "").casefold()
            if (
                not method
                or method in _CALLBACK_SUPPORT_METHODS
                or not _contains((callback_range,), callback_call_location)
            ):
                continue
            if not any(
                _contains((callback_call_location,), retained_location)
                for retained_location in retained_locations
                if callback_call_location is not None
            ):
                return True
    return False


def _has_loop_carried_dependency(
    ast: dict[str, Any],
    retained_definitions: tuple[DataflowDefinition, ...],
    sink_line: int,
) -> bool:
    first_definition = {
        definition.target: min(
            definition.start_line,
            *(
                item.start_line
                for item in retained_definitions
                if item.target == definition.target
            ),
        )
        for definition in retained_definitions
    }
    if not first_definition:
        return False
    body = ast.get("body") if ast.get("type") == "Program" else None
    if not isinstance(body, list):
        return False
    for statement in body:
        location = _location(statement)
        if (
            not isinstance(statement, dict)
            or statement.get("type") not in _CONTROL_FLOW_NODES
            or location is None
            or location[0] > sink_line
        ):
            continue
        for node in _walk_executable_statement(statement):
            node_location = _location(node) or location
            target: str | None = None
            if node.get("type") == "AssignmentExpression":
                left = node.get("left")
                target = left.get("name") if isinstance(left, dict) and left.get("type") == "Identifier" else None
            elif node.get("type") == "VariableDeclarator":
                identifier = node.get("id")
                target = identifier.get("name") if isinstance(identifier, dict) and identifier.get("type") == "Identifier" else None
            if (
                isinstance(target, str)
                and target in first_definition
                and first_definition[target] <= node_location[0] <= sink_line
            ):
                return True
    return False


def _referenced_identifier_names(node: Any) -> set[str]:
    """Collect variable references without treating member/property names as bindings."""

    if isinstance(node, list):
        return set().union(*(_referenced_identifier_names(item) for item in node))
    if not isinstance(node, dict):
        return set()
    if node.get("type") == "Identifier":
        name = node.get("name")
        return {name} if isinstance(name, str) else set()
    if node.get("type") == "MemberExpression":
        names = _referenced_identifier_names(node.get("object"))
        if node.get("computed"):
            names.update(_referenced_identifier_names(node.get("property")))
        return names
    if node.get("type") == "Property":
        names = _referenced_identifier_names(node.get("value"))
        if node.get("computed"):
            names.update(_referenced_identifier_names(node.get("key")))
        return names
    names: set[str] = set()
    for key, value in node.items():
        if key not in {"loc", "range"}:
            names.update(_referenced_identifier_names(value))
    return names


def _has_unresolved_output_control_flow_lineage(
    ast: dict[str, Any], sink_line: int
) -> bool:
    """Reject output dependencies reassigned inside unexpanded control flow.

    The dataflow slicer intentionally models top-level definitions only. If a value
    exported by the sink (or one of its top-level dependencies) is overwritten in a
    loop, the latest reaching definition cannot be proved without expanding that
    control flow. Keeping its initial definition would silently truncate the DAG.
    """

    body = ast.get("body") if ast.get("type") == "Program" else None
    if not isinstance(body, list):
        return False

    payload_names: set[str] = set()
    bindings: dict[str, set[str]] = {}
    for statement in body:
        if not isinstance(statement, dict):
            continue
        statement_location = _location(statement)
        if statement_location is None or statement_location[0] > sink_line:
            continue
        if statement.get("type") == "VariableDeclaration":
            for declaration in statement.get("declarations") or []:
                identifier = declaration.get("id") if isinstance(declaration, dict) else None
                name = identifier.get("name") if isinstance(identifier, dict) else None
                init = declaration.get("init") if isinstance(declaration, dict) else None
                if isinstance(name, str) and isinstance(init, dict):
                    bindings[name] = _referenced_identifier_names(init)
        elif statement.get("type") == "ExpressionStatement":
            expression = statement.get("expression")
            if (
                isinstance(expression, dict)
                and expression.get("type") == "AssignmentExpression"
                and expression.get("operator") == "="
            ):
                left = expression.get("left")
                name = left.get("name") if isinstance(left, dict) and left.get("type") == "Identifier" else None
                right = expression.get("right")
                if isinstance(name, str) and isinstance(right, dict):
                    bindings[name] = _referenced_identifier_names(right)

        if not (statement_location[0] <= sink_line <= statement_location[1]):
            continue
        for call in _walk(statement):
            if call.get("type") != "CallExpression":
                continue
            callee = str(_static_callee(call.get("callee")) or "")
            payload_key = "image" if callee.startswith("Export.image") else (
                "collection" if callee.startswith("Export.table") else None
            )
            if payload_key is None:
                continue
            arguments = call.get("arguments") or []
            options = arguments[0] if arguments else None
            if not isinstance(options, dict) or options.get("type") != "ObjectExpression":
                continue
            for prop in options.get("properties") or []:
                if not isinstance(prop, dict) or prop.get("type") != "Property":
                    continue
                key = prop.get("key")
                key_name = (
                    key.get("name")
                    if isinstance(key, dict) and key.get("type") == "Identifier"
                    else key.get("value")
                    if isinstance(key, dict) and key.get("type") == "Literal"
                    else None
                )
                if key_name == payload_key:
                    payload_names.update(_referenced_identifier_names(prop.get("value")))

    tracked = set(payload_names)
    pending = list(payload_names)
    while pending:
        name = pending.pop()
        for dependency in bindings.get(name, set()):
            if dependency not in tracked:
                tracked.add(dependency)
                pending.append(dependency)
    if not tracked:
        return False

    for node in _walk(ast):
        if node.get("type") not in _CONTROL_FLOW_NODES:
            continue
        location = _location(node)
        if location is None or location[0] > sink_line:
            continue
        for child in _walk_executable_statement(node):
            target: str | None = None
            if child.get("type") == "AssignmentExpression" and child.get("operator") == "=":
                left = child.get("left")
                target = left.get("name") if isinstance(left, dict) and left.get("type") == "Identifier" else None
            elif child.get("type") == "VariableDeclarator":
                identifier = child.get("id")
                target = identifier.get("name") if isinstance(identifier, dict) else None
            if isinstance(target, str) and target in tracked:
                return True
    return False


def _has_bare_method_reference_output(ast: dict[str, Any], sink_line: int) -> bool:
    for statement in ast.get("body", []):
        statement_location = _location(statement)
        if statement_location is None or not (
            statement_location[0] <= sink_line <= statement_location[1]
        ):
            continue
        for node in _walk(statement):
            if node.get("type") != "CallExpression":
                continue
            callee = _static_callee(node.get("callee"))
            if callee not in {"Export.image.toAsset", "Export.image.toDrive", "Export.image.toCloudStorage"}:
                continue
            arguments = node.get("arguments") or []
            options = arguments[0] if arguments else None
            if not isinstance(options, dict) or options.get("type") != "ObjectExpression":
                continue
            for prop in options.get("properties") or []:
                if not isinstance(prop, dict) or prop.get("type") != "Property":
                    continue
                key = prop.get("key")
                key_name = key.get("name") if isinstance(key, dict) and key.get("type") == "Identifier" else None
                value = prop.get("value")
                if key_name == "image" and isinstance(value, dict) and value.get("type") == "MemberExpression":
                    if str(_static_member_name(value) or "").casefold() in _BARE_OUTPUT_METHODS:
                        return True
    return False


def _identifier_roles(
    ast: dict[str, Any],
    names: tuple[str, ...],
    ranges: tuple[tuple[int, int], ...],
) -> dict[str, set[str]]:
    roles = {name: set() for name in names}
    spatial_methods = frozenset({"clip", "cliptocollection", "filterbounds"})
    spatial_properties = frozenset({"geometry", "region"})

    def walk(node: Any, *, active: bool = False, role: str = "other") -> None:
        if isinstance(node, list):
            for child in node:
                walk(child, active=active, role=role)
            return
        if not isinstance(node, dict):
            return
        location = _location(node)
        if location is not None:
            active = _contains(ranges, location)
        if node.get("type") == "Identifier":
            name = node.get("name")
            if active and isinstance(name, str) and name in roles:
                roles[name].add(role)
            return
        if node.get("type") == "CallExpression":
            walk(node.get("callee"), active=active, role=role)
            method_name = _static_member_name(node.get("callee"))
            method = method_name.lower() if method_name else ""
            argument_role = (
                "external_spatial"
                if role == "external_spatial" or method in spatial_methods
                else "other"
            )
            for argument in node.get("arguments", []):
                walk(argument, active=active, role=argument_role)
            return
        if node.get("type") == "Property":
            key = node.get("key")
            key_name = None
            if isinstance(key, dict) and key.get("type") == "Identifier" and not node.get("computed"):
                key_name = key.get("name")
            value_role = "external_spatial" if key_name in spatial_properties else "other"
            walk(node.get("value"), active=active, role=value_role)
            if node.get("computed"):
                walk(key, active=active)
            return
        for key, value in node.items():
            if key not in {"loc", "range"}:
                walk(value, active=active, role=role)

    walk(ast)
    return roles


def _sink_ranges(ast: dict[str, Any]) -> dict[int, tuple[int, int]]:
    ranges: dict[int, tuple[int, int]] = {}
    body = ast.get("body") if ast.get("type") == "Program" else None
    if not isinstance(body, list):
        return ranges
    for statement in body:
        if not isinstance(statement, dict) or statement.get("type") != "ExpressionStatement":
            continue
        expression = statement.get("expression")
        if not isinstance(expression, dict) or expression.get("type") != "CallExpression":
            continue
        callee = expression.get("callee")
        while isinstance(callee, dict) and callee.get("type") == "MemberExpression":
            callee = callee.get("object")
        if not isinstance(callee, dict) or callee.get("type") != "Identifier":
            continue
        if callee.get("name") != "Export":
            continue
        location = _location(statement)
        if location is not None:
            ranges[location[0]] = location
    return ranges


def build_output_workflow_dags(
    ast: dict[str, Any], ordered_call_evidence: Iterable[dict[str, Any]]
) -> OutputWorkflowDagResult:
    """Recover one fail-closed workflow candidate per explicit ``Export`` sink."""

    calls = tuple(call for call in ordered_call_evidence if isinstance(call, dict))
    core_calls = tuple(call for call in calls if call.get("classification") == "core")
    dataflow = build_backward_slices(ast, core_calls)
    output_slices = tuple(item for item in dataflow.slices if item.root_kind == "io_sink")
    if not output_slices:
        return OutputWorkflowDagResult(
            source_status="fail_closed",
            workflows=(),
            source_fail_closed_reasons=("no_explicit_output_sink",),
            slicer_quality_flags=dataflow.quality_flags,
        )

    definitions = {item.definition_id: item for item in dataflow.definitions}
    calls_by_ordinal = {
        call["ordinal"]: call
        for call in core_calls
        if isinstance(call.get("ordinal"), int)
    }
    sink_ranges = _sink_ranges(ast)
    executable_mutations = _executable_mutation_targets(ast)
    callback_mutations = _callback_mutation_targets(ast)
    workflows: list[OutputWorkflowDag] = []
    for index, output_slice in enumerate(output_slices, start=1):
        ranges = tuple(
            (definitions[item].start_line, definitions[item].end_line)
            for item in output_slice.definition_ids
            if item in definitions
        ) + (sink_ranges.get(output_slice.root_line, (output_slice.root_line, output_slice.root_line)),)

        relevant_unresolved_calls = tuple(
            call
            for call in calls
            if call.get("classification") == "unresolved"
            and _contains(ranges, _call_location(call))
        )
        identifier_roles = _identifier_roles(
            ast,
            output_slice.unresolved_identifiers,
            ranges,
        )
        external_inputs = tuple(
            sorted(
                name
                for name, roles in identifier_roles.items()
                if roles and roles <= {"external_spatial"}
            )
        )
        unresolved_identifiers = tuple(
            name for name in output_slice.unresolved_identifiers if name not in external_inputs
        )
        reasons: set[str] = set()
        if unresolved_identifiers:
            reasons.add("unresolved_dependency")
        if not output_slice.core_call_ordinals:
            reasons.add("no_core_calls")
        if relevant_unresolved_calls:
            reasons.add("unresolved_call_in_dependency_closure")
        if _has_control_flow(ast, ranges):
            reasons.add("control_flow_in_dependency_closure")

        ordered_core_calls = tuple(
            calls_by_ordinal[ordinal]
            for ordinal in output_slice.core_call_ordinals
            if ordinal in calls_by_ordinal
        )
        spans = [
            span
            for span in (_call_source_span(call) for call in ordered_core_calls)
            if span is not None
        ]
        if len(spans) != len(set(spans)):
            reasons.add("reused_core_call_source_span")
        if _has_support_higher_order_call_with_retained_callback_core(
            ast,
            calls,
            ordered_core_calls,
            ranges,
            method="map",
        ):
            reasons.add("callback_core_calls_without_structural_map")
        if _has_support_higher_order_call_with_retained_callback_core(
            ast,
            calls,
            ordered_core_calls,
            ranges,
            method="iterate",
        ):
            reasons.add("iterate_callback_aggregation_not_closed")
        if _has_incomplete_callback_core_closure(
            ast,
            calls,
            ordered_core_calls,
            ranges,
            frozenset(item.rsplit("@", 1)[0] for item in output_slice.definition_ids),
        ):
            reasons.add("callback_core_calls_not_closed")
        retained_definitions = tuple(
            definitions[item]
            for item in output_slice.definition_ids
            if item in definitions
        )
        has_callback_mutation = _has_retained_mutation(
            callback_mutations,
            retained_definitions,
            output_slice.root_line,
        )
        if _has_retained_mutation(
            executable_mutations,
            retained_definitions,
            output_slice.root_line,
        ) or has_callback_mutation:
            reasons.add("unresolved_mutated_collection_dependency")
        if has_callback_mutation:
            reasons.add("callback_mutates_retained_output_dependency")
        if _has_loop_carried_dependency(ast, retained_definitions, output_slice.root_line):
            reasons.add("loop_carried_dependency_not_closed")
        if _has_unresolved_output_control_flow_lineage(ast, output_slice.root_line):
            reasons.add("unresolved_output_control_flow_lineage")
        if _has_bare_method_reference_output(ast, output_slice.root_line):
            reasons.add("bare_method_reference_output")
        if _has_top_level_throw_before_sink(ast, output_slice.root_line):
            reasons.add("sink_unreachable_after_top_level_throw")
        if _has_native_operator_on_retained_ee_dependency(
            ast,
            retained_definitions,
            ordered_core_calls,
            output_slice.root_line,
        ):
            reasons.add("native_operator_on_ee_object_not_closed")
        workflows.append(
            OutputWorkflowDag(
                workflow_id=f"output-workflow-{index}",
                sink_root_id=output_slice.root_id,
                sink_line=output_slice.root_line,
                definition_ids=output_slice.definition_ids,
                dependency_edges=output_slice.dependency_edges,
                core_call_ordinals=output_slice.core_call_ordinals,
                core_raw_callees=tuple(str(call.get("raw_callee") or "") for call in ordered_core_calls),
                external_input_identifiers=external_inputs,
                unresolved_identifiers=unresolved_identifiers,
                status="fail_closed" if reasons else "passed",
                fail_closed_reasons=tuple(sorted(reasons)),
            )
        )

    passed_count = sum(item.status == "passed" for item in workflows)
    if passed_count == len(workflows):
        source_status = "passed"
    elif passed_count:
        source_status = "partial"
    else:
        source_status = "fail_closed"
    return OutputWorkflowDagResult(
        source_status=source_status,
        workflows=tuple(workflows),
        source_fail_closed_reasons=(),
        slicer_quality_flags=dataflow.quality_flags,
    )
