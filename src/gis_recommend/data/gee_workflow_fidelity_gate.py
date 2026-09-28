"""Deterministic fidelity checks for complete output-backed GEE DAGs."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
import hashlib
import json
import re
from typing import Any, Iterable

from gis_recommend.data.gee_workflow_dag_gate import OutputWorkflowDag


_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_SPATIAL_ACCESSORS = frozenset({"bounds", "geometry"})
_PENDING_ADMISSION = "not_granted_taxonomy_and_task_text_pending"
_FAILED_ADMISSION = "not_granted_fidelity_failed"
_DUPLICATE_ADMISSION = "not_granted_exact_output_duplicate"
_CATALOG_TEMPORAL_COVERAGE = {
    "LANDSAT/LC08/C01/T1_SR": (date(2013, 2, 11), date.max),
    "LANDSAT/LE07/C01/T1_SR": (date(1999, 1, 1), date.max),
    "LANDSAT/LT05/C01/T1_SR": (date(1984, 3, 1), date(2012, 5, 6)),
    "COPERNICUS/S2": (date(2015, 6, 23), date.max),
    "COPERNICUS/S2_HARMONIZED": (date(2017, 3, 28), date.max),
    "COPERNICUS/S2_SR": (date(2017, 3, 28), date.max),
    "COPERNICUS/S2_SR_HARMONIZED": (date(2017, 3, 28), date.max),
}


@dataclass(frozen=True)
class WorkflowFidelityDecision:
    """Immutable, source-grounded decision for one output workflow DAG."""

    source_sha256: str
    workflow_id: str
    sink_root_id: str
    sink_line: int
    fidelity_status: str
    fail_closed_reasons: tuple[str, ...]
    normalized_core_call_ordinals: tuple[int, ...]
    normalized_core_chain: tuple[str, ...]
    removed_auxiliary_calls: tuple[str, ...]
    external_spatial_inputs: tuple[str, ...]
    exact_dag_fingerprint: str
    training_admission: str


@dataclass(frozen=True)
class _StaticImageState:
    derived_from_callback_input: bool
    literal_bands: tuple[str, ...] | None


@dataclass(frozen=True)
class _StaticLineageState:
    """Known literal properties propagated through one top-level EE binding."""

    bands: frozenset[str] | None = None
    date_range: tuple[date, date] | None = None
    catalog_coverage: tuple[date, date] | None = None
    catalog_temporal_empty: bool = False


def _walk(node: Any) -> Iterable[dict[str, Any]]:
    if isinstance(node, list):
        for child in node:
            yield from _walk(child)
        return
    if not isinstance(node, dict):
        return
    yield node
    for key, value in node.items():
        if key not in {"loc", "range"}:
            yield from _walk(value)


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


def _member_method(node: Any) -> str | None:
    if not isinstance(node, dict) or node.get("type") != "MemberExpression":
        return None
    if node.get("computed"):
        return None
    prop = node.get("property")
    if not isinstance(prop, dict) or prop.get("type") != "Identifier":
        return None
    name = prop.get("name")
    return name if isinstance(name, str) and name else None


def _call_method(node: Any) -> str | None:
    if not isinstance(node, dict) or node.get("type") != "CallExpression":
        return None
    return _member_method(node.get("callee"))


def _call_receiver(node: Any) -> Any:
    if not isinstance(node, dict) or node.get("type") != "CallExpression":
        return None
    callee = node.get("callee")
    if not isinstance(callee, dict) or callee.get("type") != "MemberExpression":
        return None
    return callee.get("object")


def _member_path(node: Any) -> tuple[str, ...] | None:
    if not isinstance(node, dict):
        return None
    if node.get("type") == "Identifier":
        name = node.get("name")
        return (name,) if isinstance(name, str) and name else None
    if node.get("type") != "MemberExpression" or node.get("computed"):
        return None
    parent = _member_path(node.get("object"))
    prop = node.get("property")
    name = prop.get("name") if isinstance(prop, dict) else None
    if parent is None or not isinstance(name, str) or not name:
        return None
    return (*parent, name)


def _call_path(node: Any) -> tuple[str, ...] | None:
    if not isinstance(node, dict) or node.get("type") != "CallExpression":
        return None
    return _member_path(node.get("callee"))


def _literal_bands(node: Any) -> tuple[str, ...] | None:
    if not isinstance(node, dict):
        return None
    if node.get("type") == "Literal":
        value = node.get("value")
        if isinstance(value, str) and value:
            return (value,)
        if (
            isinstance(value, list)
            and value
            and all(isinstance(item, str) and item for item in value)
        ):
            return tuple(value)
        return None
    if node.get("type") != "ArrayExpression":
        return None
    values: list[str] = []
    for element in node.get("elements", []):
        if not isinstance(element, dict) or element.get("type") != "Literal":
            return None
        value = element.get("value")
        if not isinstance(value, str) or not value:
            return None
        values.append(value)
    return tuple(values) if values else None


def _single_argument_bands(call_node: Any) -> tuple[str, ...] | None:
    if not isinstance(call_node, dict):
        return None
    arguments = call_node.get("arguments")
    if not isinstance(arguments, list) or len(arguments) != 1:
        return None
    return _literal_bands(arguments[0])


def _exact_literal_bands(call_node: Any) -> tuple[str, ...] | None:
    """Return only literal band names that cannot be GEE select regex selectors."""

    bands = _single_argument_bands(call_node)
    if bands is None:
        return None
    return bands if all(not re.search(r"[.\\*+?\[\](){}|^$]", band) for band in bands) else None


def _exact_bound_literal_bands(
    call_node: Any,
    literal_band_bindings: Mapping[str, tuple[str, ...]],
) -> tuple[str, ...] | None:
    """Resolve inline literal bands or a proven top-level literal-array alias."""

    bands = _exact_literal_bands(call_node)
    if bands is not None:
        return bands
    arguments = call_node.get("arguments") if isinstance(call_node, dict) else None
    if not isinstance(arguments, list) or len(arguments) != 1:
        return None
    argument = arguments[0]
    name = (
        argument.get("name")
        if isinstance(argument, dict) and argument.get("type") == "Identifier"
        else None
    )
    return literal_band_bindings.get(name) if isinstance(name, str) else None


def _literal_filter_date_range(call_node: Any) -> tuple[date, date] | None:
    if not isinstance(call_node, dict):
        return None
    method = (_call_method(call_node) or "").casefold()
    arguments = call_node.get("arguments")
    if method == "filter":
        if not isinstance(arguments, list) or len(arguments) != 1:
            return None
        date_filter = arguments[0]
        if _call_path(date_filter) != ("ee", "Filter", "date"):
            return None
        arguments = date_filter.get("arguments") if isinstance(date_filter, dict) else None
    elif method != "filterdate":
        return None
    if not isinstance(arguments, list) or len(arguments) != 2:
        return None
    values = []
    for argument in arguments:
        if not isinstance(argument, dict) or argument.get("type") != "Literal":
            return None
        value = argument.get("value")
        if not isinstance(value, str):
            return None
        try:
            values.append(date.fromisoformat(value[:10]))
        except ValueError:
            return None
    return values[0], values[1]


def _literal_image_collection_coverage(node: Any) -> tuple[date, date] | None:
    """Return coverage only for an exact public ImageCollection literal."""

    if _call_path(node) != ("ee", "ImageCollection"):
        return None
    arguments = node.get("arguments") if isinstance(node, dict) else None
    if not isinstance(arguments, list) or len(arguments) != 1:
        return None
    argument = arguments[0]
    dataset_id = argument.get("value") if isinstance(argument, dict) else None
    if not isinstance(dataset_id, str):
        return None
    return _CATALOG_TEMPORAL_COVERAGE.get(dataset_id)


def _expression_state(
    node: Any,
    *,
    callback_parameter: str,
    bindings: dict[str, _StaticImageState],
) -> _StaticImageState:
    unknown = _StaticImageState(False, None)
    if not isinstance(node, dict):
        return unknown
    if node.get("type") == "Identifier":
        name = node.get("name")
        if name == callback_parameter:
            return _StaticImageState(True, None)
        return bindings.get(name, unknown) if isinstance(name, str) else unknown
    if node.get("type") != "CallExpression":
        return unknown

    receiver_state = _expression_state(
        _call_receiver(node),
        callback_parameter=callback_parameter,
        bindings=bindings,
    )
    method = (_call_method(node) or "").lower()
    if method == "addbands":
        return _StaticImageState(receiver_state.derived_from_callback_input, None)
    if method == "rename" and receiver_state.derived_from_callback_input:
        bands = _single_argument_bands(node)
        if bands is not None:
            return _StaticImageState(True, bands)
    return receiver_state


def _callback_literal_output_band(callback: Any) -> str | None:
    if not isinstance(callback, dict) or callback.get("type") not in {
        "FunctionDeclaration",
        "FunctionExpression",
        "ArrowFunctionExpression",
    }:
        return None
    parameters = callback.get("params")
    if not isinstance(parameters, list) or len(parameters) != 1:
        return None
    parameter = parameters[0]
    if not isinstance(parameter, dict) or parameter.get("type") != "Identifier":
        return None
    parameter_name = parameter.get("name")
    if not isinstance(parameter_name, str) or not parameter_name:
        return None
    body = callback.get("body")
    if not isinstance(body, dict):
        return None
    if body.get("type") != "BlockStatement":
        state = _expression_state(
            body,
            callback_parameter=parameter_name,
            bindings={},
        )
        return (
            state.literal_bands[0]
            if state.derived_from_callback_input
            and state.literal_bands is not None
            and len(state.literal_bands) == 1
            else None
        )

    bindings: dict[str, _StaticImageState] = {}
    returns: list[_StaticImageState] = []
    for statement in body.get("body", []):
        if not isinstance(statement, dict):
            return None
        if statement.get("type") == "VariableDeclaration":
            for declaration in statement.get("declarations", []):
                if not isinstance(declaration, dict):
                    return None
                identifier = declaration.get("id")
                name = identifier.get("name") if isinstance(identifier, dict) else None
                if not isinstance(name, str) or not name:
                    return None
                bindings[name] = _expression_state(
                    declaration.get("init"),
                    callback_parameter=parameter_name,
                    bindings=bindings,
                )
        elif statement.get("type") == "ReturnStatement":
            returns.append(
                _expression_state(
                    statement.get("argument"),
                    callback_parameter=parameter_name,
                    bindings=bindings,
                )
            )
        elif statement.get("type") == "ExpressionStatement":
            return None
        else:
            return None

    if len(returns) != 1:
        return None
    state = returns[0]
    if (
        not state.derived_from_callback_input
        or state.literal_bands is None
        or len(state.literal_bands) != 1
    ):
        return None
    return state.literal_bands[0]


def _function_bindings(ast: dict[str, Any]) -> dict[str, dict[str, Any]]:
    bindings: dict[str, dict[str, Any]] = {}
    for statement in ast.get("body", []):
        if not isinstance(statement, dict):
            continue
        if statement.get("type") == "FunctionDeclaration":
            identifier = statement.get("id")
            name = identifier.get("name") if isinstance(identifier, dict) else None
            if isinstance(name, str) and name:
                bindings[name] = statement
        elif statement.get("type") == "VariableDeclaration":
            for declaration in statement.get("declarations", []):
                if not isinstance(declaration, dict):
                    continue
                identifier = declaration.get("id")
                init = declaration.get("init")
                name = identifier.get("name") if isinstance(identifier, dict) else None
                if (
                    isinstance(name, str)
                    and isinstance(init, dict)
                    and init.get("type")
                    in {"FunctionExpression", "ArrowFunctionExpression"}
                ):
                    bindings[name] = init
    return bindings


def _find_map_calls(node: Any) -> tuple[dict[str, Any], ...]:
    return tuple(
        item
        for item in _walk(node)
        if item.get("type") == "CallExpression"
        and (_call_method(item) or "").lower() == "map"
    )


def _receiver_call_chain(node: Any) -> tuple[dict[str, Any], ...]:
    """Return only the nested receiver path, excluding call arguments."""

    if not isinstance(node, dict) or node.get("type") != "CallExpression":
        return ()
    return (*_receiver_call_chain(_call_receiver(node)), node)


def _single_band_select_before_map(map_call: dict[str, Any]) -> str | None:
    receiver = _call_receiver(map_call)
    receiver_chain = _receiver_call_chain(receiver)
    selects = [
        item
        for item in receiver_chain
        if (_call_method(item) or "").lower() == "select"
    ]
    if not selects:
        return None
    bands = _single_argument_bands(selects[-1])
    if bands is None or len(bands) != 1:
        return None
    has_collection_constructor = any(
        isinstance(item.get("callee"), dict)
        and _member_method(item.get("callee")) == "ImageCollection"
        for item in receiver_chain
    )
    return bands[0] if has_collection_constructor else None


def _callback_for_map(
    map_call: dict[str, Any], function_bindings: dict[str, dict[str, Any]]
) -> dict[str, Any] | None:
    arguments = map_call.get("arguments")
    if not isinstance(arguments, list) or not arguments:
        return None
    callback = arguments[0]
    if not isinstance(callback, dict):
        return None
    if callback.get("type") in {"FunctionExpression", "ArrowFunctionExpression"}:
        return callback
    if callback.get("type") == "Identifier":
        name = callback.get("name")
        return function_bindings.get(name) if isinstance(name, str) else None
    return None


def _receiver_root_identifier(node: Any) -> str | None:
    if not isinstance(node, dict):
        return None
    if node.get("type") == "Identifier":
        name = node.get("name")
        return name if isinstance(name, str) and name else None
    if node.get("type") == "CallExpression":
        return _receiver_root_identifier(_call_receiver(node))
    if node.get("type") == "MemberExpression":
        return _receiver_root_identifier(node.get("object"))
    return None


def _later_literal_selects(
    search_nodes: Iterable[Any],
    *,
    binding_name: str,
    after_line: int,
    through_line: int,
) -> tuple[str, ...]:
    selected: list[str] = []
    for search_node in search_nodes:
        for node in _walk(search_node):
            if node.get("type") != "CallExpression":
                continue
            if (_call_method(node) or "").lower() != "select":
                continue
            if _receiver_root_identifier(_call_receiver(node)) != binding_name:
                continue
            location = _location(node)
            if location is None or not after_line < location[0] <= through_line:
                continue
            bands = _single_argument_bands(node)
            if bands is not None and len(bands) == 1:
                selected.append(bands[0])
    return tuple(selected)


def _workflow_search_nodes(
    ast: dict[str, Any], workflow: OutputWorkflowDag
) -> tuple[Any, ...]:
    definition_names = {item.rsplit("@", 1)[0] for item in workflow.definition_ids}
    nodes: list[Any] = []
    for statement in ast.get("body", []):
        if not isinstance(statement, dict):
            continue
        location = _location(statement)
        if location is not None and location[0] <= workflow.sink_line <= location[1]:
            nodes.append(statement)
            continue
        if statement.get("type") == "FunctionDeclaration":
            identifier = statement.get("id")
            name = identifier.get("name") if isinstance(identifier, dict) else None
            if name in definition_names:
                nodes.append(statement)
        elif statement.get("type") == "VariableDeclaration":
            for declaration in statement.get("declarations", []):
                if not isinstance(declaration, dict):
                    continue
                identifier = declaration.get("id")
                name = identifier.get("name") if isinstance(identifier, dict) else None
                if name in definition_names:
                    nodes.append(declaration.get("init"))
        elif statement.get("type") == "ExpressionStatement":
            expression = statement.get("expression")
            if (
                not isinstance(expression, dict)
                or expression.get("type") != "AssignmentExpression"
            ):
                continue
            target = expression.get("left")
            name = target.get("name") if isinstance(target, dict) else None
            if name in definition_names:
                nodes.append(expression.get("right"))
    return tuple(nodes)


def _workflow_bindings(
    ast: dict[str, Any], workflow: OutputWorkflowDag
) -> dict[str, dict[str, Any]]:
    definition_names = {item.rsplit("@", 1)[0] for item in workflow.definition_ids}
    bindings: dict[str, dict[str, Any]] = {}
    for statement in ast.get("body", []):
        if not isinstance(statement, dict):
            continue
        if statement.get("type") == "VariableDeclaration":
            for declaration in statement.get("declarations", []):
                if not isinstance(declaration, dict):
                    continue
                identifier = declaration.get("id")
                name = identifier.get("name") if isinstance(identifier, dict) else None
                initializer = declaration.get("init")
                if name in definition_names and isinstance(initializer, dict):
                    bindings[name] = initializer
        elif statement.get("type") == "ExpressionStatement":
            expression = statement.get("expression")
            if not isinstance(expression, dict) or expression.get("type") != "AssignmentExpression":
                continue
            target = expression.get("left")
            name = target.get("name") if isinstance(target, dict) else None
            value = expression.get("right")
            if name in definition_names and isinstance(value, dict):
                bindings[name] = value
    return bindings


def _resolve_identifier_binding(
    node: Any,
    bindings: dict[str, dict[str, Any]],
    seen: frozenset[str] = frozenset(),
) -> Any:
    if not isinstance(node, dict) or node.get("type") != "Identifier":
        return node
    name = node.get("name")
    if not isinstance(name, str) or name in seen or name not in bindings:
        return node
    return _resolve_identifier_binding(bindings[name], bindings, seen | {name})


def _has_parallel_collection_merge(
    ast: dict[str, Any], workflow: OutputWorkflowDag
) -> bool:
    bindings = _workflow_bindings(ast, workflow)
    for search_node in _workflow_search_nodes(ast, workflow):
        for node in _walk(search_node):
            if _call_path(node) not in {
                ("ee", "ImageCollection"),
                ("ee", "FeatureCollection"),
                ("ee", "ImageCollection", "fromImages"),
            }:
                continue
            arguments = node.get("arguments")
            if not isinstance(arguments, list) or len(arguments) != 1:
                continue
            source_array = _resolve_identifier_binding(arguments[0], bindings)
            if not isinstance(source_array, dict) or source_array.get("type") != "ArrayExpression":
                continue
            elements = [item for item in source_array.get("elements", []) if item is not None]
            if len(elements) >= 2:
                return True
    return False


def _has_empty_image_select_root(
    ast: dict[str, Any], workflow: OutputWorkflowDag
) -> bool:
    bindings = _workflow_bindings(ast, workflow)

    def derives_from_empty_image(
        node: Any, seen: frozenset[str] = frozenset()
    ) -> bool:
        if not isinstance(node, dict):
            return False
        if node.get("type") == "Identifier":
            name = node.get("name")
            if not isinstance(name, str) or name in seen or name not in bindings:
                return False
            return derives_from_empty_image(bindings[name], seen | {name})
        if node.get("type") == "MemberExpression":
            return derives_from_empty_image(node.get("object"), seen)
        if node.get("type") != "CallExpression":
            return False
        if _call_path(node) == ("ee", "Image"):
            arguments = node.get("arguments")
            return isinstance(arguments, list) and not arguments
        return derives_from_empty_image(_call_receiver(node), seen)

    for search_node in _workflow_search_nodes(ast, workflow):
        for node in _walk(search_node):
            if (_call_method(node) or "").lower() != "select":
                continue
            if derives_from_empty_image(_call_receiver(node)):
                return True
    return False


def _walk_top_level_execution(node: Any) -> Iterable[dict[str, Any]]:
    if isinstance(node, list):
        for child in node:
            yield from _walk_top_level_execution(child)
        return
    if not isinstance(node, dict):
        return
    if node.get("type") in {
        "FunctionDeclaration",
        "FunctionExpression",
        "ArrowFunctionExpression",
    }:
        return
    yield node
    for key, value in node.items():
        if key not in {"loc", "range"}:
            yield from _walk_top_level_execution(value)


def _top_level_bindings_before(
    ast: dict[str, Any], through_line: int
) -> dict[str, dict[str, Any]]:
    bindings: dict[str, dict[str, Any]] = {}
    for statement in ast.get("body", []):
        if not isinstance(statement, dict):
            continue
        location = _location(statement)
        if location is not None and location[0] > through_line:
            continue
        if statement.get("type") == "VariableDeclaration":
            for declaration in statement.get("declarations", []):
                if not isinstance(declaration, dict):
                    continue
                identifier = declaration.get("id")
                name = identifier.get("name") if isinstance(identifier, dict) else None
                initializer = declaration.get("init")
                if isinstance(name, str) and isinstance(initializer, dict):
                    bindings[name] = initializer
        elif statement.get("type") == "ExpressionStatement":
            expression = statement.get("expression")
            if not isinstance(expression, dict) or expression.get("type") != "AssignmentExpression":
                continue
            target = expression.get("left")
            name = target.get("name") if isinstance(target, dict) else None
            value = expression.get("right")
            if isinstance(name, str) and isinstance(value, dict):
                bindings[name] = value
    return bindings


def _binding_aliases(
    target: str, bindings: dict[str, dict[str, Any]]
) -> frozenset[str]:
    aliases = {target}
    changed = True
    while changed:
        changed = False
        for name, value in bindings.items():
            if value.get("type") != "Identifier":
                continue
            referenced = value.get("name")
            if not isinstance(referenced, str):
                continue
            if name in aliases and referenced not in aliases:
                aliases.add(referenced)
                changed = True
            elif referenced in aliases and name not in aliases:
                aliases.add(name)
                changed = True
    return frozenset(aliases)


def _has_mutable_from_images_dependency(
    ast: dict[str, Any], workflow: OutputWorkflowDag
) -> bool:
    for search_node in _workflow_search_nodes(ast, workflow):
        for node in _walk(search_node):
            if _call_path(node) != ("ee", "ImageCollection", "fromImages"):
                continue
            arguments = node.get("arguments")
            if not isinstance(arguments, list) or len(arguments) != 1:
                continue
            source = arguments[0]
            if isinstance(source, dict) and source.get("type") == "Identifier":
                name = source.get("name")
                if not isinstance(name, str) or not name:
                    continue
                from_images_location = _location(node)
                through_line = (
                    from_images_location[0]
                    if from_images_location is not None
                    else workflow.sink_line
                )
                bindings = _top_level_bindings_before(ast, through_line)
                aliases = _binding_aliases(name, bindings)
                if not any(
                    isinstance(bindings.get(alias), dict)
                    and bindings[alias].get("type") == "ArrayExpression"
                    for alias in aliases
                ):
                    continue
                for statement in ast.get("body", []):
                    if not isinstance(statement, dict):
                        continue
                    statement_location = _location(statement)
                    if statement_location is not None and statement_location[0] > through_line:
                        continue
                    for candidate in _walk_top_level_execution(statement):
                        if (_call_method(candidate) or "").lower() != "push":
                            continue
                        push_location = _location(candidate)
                        if push_location is not None and push_location[0] > through_line:
                            continue
                        receiver_name = _receiver_root_identifier(
                            _call_receiver(candidate)
                        )
                        if receiver_name in aliases:
                            return True
    return False


def _has_static_single_band_mismatch(
    ast: dict[str, Any], workflow: OutputWorkflowDag
) -> bool:
    definition_names = {item.rsplit("@", 1)[0] for item in workflow.definition_ids}
    function_bindings = _function_bindings(ast)
    workflow_search_nodes = _workflow_search_nodes(ast, workflow)
    sink_end_line = max(
        (
            location[1]
            for node in workflow_search_nodes
            if (location := _location(node)) is not None
            and location[0] <= workflow.sink_line <= location[1]
        ),
        default=workflow.sink_line,
    )
    for statement in ast.get("body", []):
        if (
            not isinstance(statement, dict)
            or statement.get("type") != "VariableDeclaration"
        ):
            continue
        statement_location = _location(statement)
        if statement_location is None:
            continue
        for declaration in statement.get("declarations", []):
            if not isinstance(declaration, dict):
                continue
            identifier = declaration.get("id")
            name = identifier.get("name") if isinstance(identifier, dict) else None
            if not isinstance(name, str) or name not in definition_names:
                continue
            for map_call in _find_map_calls(declaration.get("init")):
                if _single_band_select_before_map(map_call) is None:
                    continue
                callback = _callback_for_map(map_call, function_bindings)
                output_band = _callback_literal_output_band(callback)
                if output_band is None:
                    continue
                requested_bands = _later_literal_selects(
                    workflow_search_nodes,
                    binding_name=name,
                    after_line=statement_location[1],
                    through_line=sink_end_line,
                )
                if any(requested != output_band for requested in requested_bands):
                    return True
    return False


def _has_parallel_image_fan_in(ast: dict[str, Any], workflow: OutputWorkflowDag) -> bool:
    for search_node in _workflow_search_nodes(ast, workflow):
        for node in _walk(search_node):
            if node.get("type") != "CallExpression" or (_call_method(node) or "").casefold() != "addbands":
                continue
            arguments = node.get("arguments") or []
            source = arguments[0] if arguments else None
            if not isinstance(source, dict) or source.get("type") != "ArrayExpression":
                continue
            roots = {
                root
                for element in source.get("elements") or []
                if (root := _receiver_root_identifier(element)) is not None
            }
            if len(roots) >= 2:
                return True
    return False


def _top_level_binding_events(ast: dict[str, Any]) -> tuple[tuple[str, int, dict[str, Any]], ...]:
    events: list[tuple[str, int, dict[str, Any]]] = []
    for statement in ast.get("body", []):
        if not isinstance(statement, dict):
            continue
        location = _location(statement)
        if location is None:
            continue
        if statement.get("type") == "VariableDeclaration":
            for declaration in statement.get("declarations") or []:
                identifier = declaration.get("id") if isinstance(declaration, dict) else None
                name = identifier.get("name") if isinstance(identifier, dict) and identifier.get("type") == "Identifier" else None
                initializer = declaration.get("init") if isinstance(declaration, dict) else None
                if isinstance(name, str) and isinstance(initializer, dict):
                    events.append((name, location[0], initializer))
        elif statement.get("type") == "ExpressionStatement":
            expression = statement.get("expression")
            if not isinstance(expression, dict) or expression.get("type") != "AssignmentExpression":
                continue
            left = expression.get("left")
            name = left.get("name") if isinstance(left, dict) and left.get("type") == "Identifier" else None
            value = expression.get("right")
            if isinstance(name, str) and isinstance(value, dict):
                events.append((name, location[0], value))
    return tuple(events)


def _lineage_state(
    node: Any,
    bindings: dict[str, _StaticLineageState],
    literal_band_bindings: Mapping[str, tuple[str, ...]],
) -> tuple[_StaticLineageState, bool, bool]:
    """Propagate literal band/date evidence and report provable invalid operations.

    Unknown values deliberately remain unknown.  A failure is emitted only when a
    literal request contradicts an already known property of the same receiver
    lineage.
    """

    unknown = _StaticLineageState()
    if not isinstance(node, dict):
        return unknown, False, False
    if node.get("type") == "Identifier":
        name = node.get("name")
        return (bindings.get(name, unknown), False, False) if isinstance(name, str) else (unknown, False, False)
    if node.get("type") != "CallExpression":
        return unknown, False, False

    collection_coverage = _literal_image_collection_coverage(node)
    if collection_coverage is not None:
        return _StaticLineageState(catalog_coverage=collection_coverage), False, False

    # ``ee.Image(value)`` is a transparent cast for an already-proven EE image
    # lineage. Preserve literal date and band evidence through that wrapper.
    if _call_path(node) == ("ee", "Image"):
        arguments = node.get("arguments")
        if isinstance(arguments, list) and len(arguments) == 1:
            return _lineage_state(arguments[0], bindings, literal_band_bindings)

    receiver, band_mismatch, temporal_empty = _lineage_state(
        _call_receiver(node), bindings, literal_band_bindings
    )
    method = (_call_method(node) or "").casefold()
    if method == "select":
        requested = _exact_bound_literal_bands(node, literal_band_bindings)
        if requested is None:
            return _StaticLineageState(
                None,
                receiver.date_range,
                receiver.catalog_coverage,
                receiver.catalog_temporal_empty,
            ), band_mismatch, temporal_empty
        requested_set = frozenset(requested)
        if receiver.bands is not None and not requested_set.issubset(receiver.bands):
            band_mismatch = True
        return _StaticLineageState(
            requested_set,
            receiver.date_range,
            receiver.catalog_coverage,
            receiver.catalog_temporal_empty,
        ), band_mismatch, temporal_empty
    if method == "rename":
        renamed = _exact_literal_bands(node)
        if renamed is not None:
            return _StaticLineageState(
                frozenset(renamed),
                receiver.date_range,
                receiver.catalog_coverage,
                receiver.catalog_temporal_empty,
            ), band_mismatch, temporal_empty
        return _StaticLineageState(
            None,
            receiver.date_range,
            receiver.catalog_coverage,
            receiver.catalog_temporal_empty,
        ), band_mismatch, temporal_empty
    if method == "expression":
        # Image.expression creates a single band named "constant" unless a
        # following rename changes it. Inspect argument subexpressions too:
        # their static selects can otherwise hide an invalid derived-band use.
        for argument in node.get("arguments") or []:
            for nested in _walk(argument):
                if nested is argument or nested.get("type") != "CallExpression":
                    continue
                _, nested_band_mismatch, nested_temporal_empty = _lineage_state(
                    nested, bindings, literal_band_bindings
                )
                band_mismatch = band_mismatch or nested_band_mismatch
                temporal_empty = temporal_empty or nested_temporal_empty
        return _StaticLineageState(
            frozenset({"constant"}),
            receiver.date_range,
            receiver.catalog_coverage,
            receiver.catalog_temporal_empty,
        ), band_mismatch, temporal_empty
    if method == "addbands":
        arguments = node.get("arguments")
        added = unknown
        if isinstance(arguments, list) and arguments:
            added, added_band_mismatch, added_temporal_empty = _lineage_state(
                arguments[0], bindings, literal_band_bindings
            )
            band_mismatch = band_mismatch or added_band_mismatch
            temporal_empty = temporal_empty or added_temporal_empty
        bands = (
            receiver.bands | added.bands
            if receiver.bands is not None and added.bands is not None
            else None
        )
        return _StaticLineageState(
            bands,
            receiver.date_range,
            receiver.catalog_coverage,
            receiver.catalog_temporal_empty,
        ), band_mismatch, temporal_empty
    if method in {"filterdate", "filter"}:
        date_range = _literal_filter_date_range(node)
        if date_range is None:
            return _StaticLineageState(
                receiver.bands,
                None,
                receiver.catalog_coverage,
                receiver.catalog_temporal_empty,
            ), band_mismatch, temporal_empty
        if receiver.date_range is not None:
            start = max(receiver.date_range[0], date_range[0])
            end = min(receiver.date_range[1], date_range[1])
            if start >= end:
                temporal_empty = True
            date_range = (start, end)
        catalog_temporal_empty = receiver.catalog_temporal_empty
        if receiver.catalog_coverage is not None:
            coverage_start, coverage_end = receiver.catalog_coverage
            if max(coverage_start, date_range[0]) >= min(coverage_end, date_range[1]):
                catalog_temporal_empty = True
        return _StaticLineageState(
            receiver.bands,
            date_range,
            receiver.catalog_coverage,
            catalog_temporal_empty,
        ), band_mismatch, temporal_empty
    return receiver, band_mismatch, temporal_empty


def _has_static_lineage_contradiction(
    ast: dict[str, Any], workflow: OutputWorkflowDag
) -> tuple[bool, bool, bool]:
    """Check only output-relevant top-level bindings before the workflow sink."""

    definition_names = {item.rsplit("@", 1)[0] for item in workflow.definition_ids}
    bindings: dict[str, _StaticLineageState] = {}
    literal_band_bindings: dict[str, tuple[str, ...]] = {}
    band_mismatch = False
    temporal_empty = False
    catalog_temporal_empty = False
    for name, line, value in _top_level_binding_events(ast):
        if line > workflow.sink_line:
            continue
        literal_bands = _literal_bands(value)
        if literal_bands is None:
            literal_band_bindings.pop(name, None)
        else:
            literal_band_bindings[name] = literal_bands
        state, expression_band_mismatch, expression_temporal_empty = _lineage_state(
            value, bindings, literal_band_bindings
        )
        bindings[name] = state
        if name in definition_names:
            band_mismatch = band_mismatch or expression_band_mismatch
            temporal_empty = temporal_empty or expression_temporal_empty
            catalog_temporal_empty = catalog_temporal_empty or state.catalog_temporal_empty
    return band_mismatch, temporal_empty, catalog_temporal_empty


def _contains_fresh_ee_image_constructor(node: Any) -> bool:
    return any(
        item.get("type") == "CallExpression"
        and (_call_method(item) or "").casefold() in {"image", "imagecollection"}
        and _receiver_root_identifier(_call_receiver(item)) == "ee"
        for item in _walk(node)
    )


def _literal_rename_bands(node: Any) -> frozenset[str]:
    bands: set[str] = set()
    for item in _walk(node):
        if item.get("type") != "CallExpression" or (_call_method(item) or "").casefold() != "rename":
            continue
        values = _single_argument_bands(item)
        if values is not None:
            bands.update(values)
    return frozenset(bands)


def _map_callback_names(node: Any) -> frozenset[str]:
    names: set[str] = set()
    for item in _walk(node):
        if item.get("type") != "CallExpression" or (_call_method(item) or "").casefold() != "map":
            continue
        arguments = item.get("arguments") or []
        callback = arguments[0] if arguments else None
        if isinstance(callback, dict) and callback.get("type") == "Identifier":
            name = callback.get("name")
            if isinstance(name, str):
                names.add(name)
    return frozenset(names)


def _has_stale_derived_band_after_rebind(ast: dict[str, Any], workflow: OutputWorkflowDag) -> bool:
    definition_names = {item.rsplit("@", 1)[0] for item in workflow.definition_ids}
    events = _top_level_binding_events(ast)
    producer_bands: dict[str, frozenset[str]] = {}
    for statement in ast.get("body", []):
        if not isinstance(statement, dict) or statement.get("type") != "FunctionDeclaration":
            continue
        identifier = statement.get("id")
        name = identifier.get("name") if isinstance(identifier, dict) else None
        if isinstance(name, str):
            producer_bands[name] = _literal_rename_bands(statement)

    for _, select_line, expression in events:
        if select_line > workflow.sink_line:
            continue
        for node in _walk(expression):
            if node.get("type") != "CallExpression" or (_call_method(node) or "").casefold() != "select":
                continue
            receiver = _receiver_root_identifier(_call_receiver(node))
            selected = _single_argument_bands(node)
            if receiver not in definition_names or selected is None or len(selected) != 1:
                continue
            band = selected[0]
            rebind_lines = [
                line
                for name, line, value in events
                if name == receiver
                and line < select_line
                and _contains_fresh_ee_image_constructor(value)
            ]
            if not rebind_lines:
                continue
            rebind_line = max(rebind_lines)
            derived_before = any(
                band in _literal_rename_bands(statement)
                for statement in ast.get("body", [])
                if isinstance(statement, dict)
                and (location := _location(statement)) is not None
                and location[1] < rebind_line
            )
            if not derived_before:
                continue
            produced_after = any(
                rebind_line < line < select_line
                and (
                    band in _literal_rename_bands(value)
                    or any(band in producer_bands.get(name, ()) for name in _map_callback_names(value))
                )
                for _, line, value in events
            )
            if not produced_after:
                return True
    return False


def _is_auxiliary_spatial_accessor(
    raw_callee: str, external_spatial_inputs: frozenset[str]
) -> bool:
    receiver, separator, method = raw_callee.rpartition(".")
    receiver_root = receiver.split(".", 1)[0]
    return bool(
        receiver
        and separator
        and method.lower() in _SPATIAL_ACCESSORS
        and receiver_root in external_spatial_inputs
    )


def _normalize_core_chain(
    call_ordinals: tuple[int, ...],
    raw_chain: tuple[str, ...],
    external_spatial_inputs: tuple[str, ...],
) -> tuple[tuple[int, ...], tuple[str, ...], tuple[str, ...]]:
    if len(call_ordinals) != len(raw_chain):
        raise ValueError("core call ordinals and raw callees must align")
    normalized_ordinals: list[int] = []
    normalized: list[str] = []
    removed: list[str] = []
    external_roots = frozenset(external_spatial_inputs)
    for ordinal, raw_callee in zip(call_ordinals, raw_chain, strict=True):
        if _is_auxiliary_spatial_accessor(raw_callee, external_roots):
            removed.append(raw_callee)
        else:
            normalized_ordinals.append(ordinal)
            normalized.append(raw_callee)
    return tuple(normalized_ordinals), tuple(normalized), tuple(removed)


def _fingerprint(
    *,
    source_sha256: str,
    workflow: OutputWorkflowDag,
    normalized_core_chain: tuple[str, ...],
    external_spatial_inputs: tuple[str, ...],
    removed_auxiliary_calls: tuple[str, ...],
) -> str:
    payload = {
        "source_sha256": source_sha256,
        "definition_closure": list(workflow.definition_ids),
        "dependency_edges": [list(edge) for edge in sorted(workflow.dependency_edges)],
        "normalized_core_chain": list(normalized_core_chain),
        "external_input_contract": {
            "identifiers": list(external_spatial_inputs),
            "spatial_accessors": list(removed_auxiliary_calls),
        },
    }
    canonical = json.dumps(
        payload,
        ensure_ascii=True,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("ascii")
    return hashlib.sha256(canonical).hexdigest()


def evaluate_workflow_fidelity(
    *,
    source_sha256: str,
    ast: dict[str, Any],
    workflows: Iterable[OutputWorkflowDag],
) -> tuple[WorkflowFidelityDecision, ...]:
    """Apply fail-closed fidelity checks and same-source exact-output deduplication."""

    if not _SHA256_RE.fullmatch(source_sha256):
        raise ValueError("source_sha256 must be a lowercase 64-character SHA256")
    if (
        not isinstance(ast, dict)
        or ast.get("type") != "Program"
        or not isinstance(ast.get("body"), list)
    ):
        raise ValueError("AST root must be an ESTree Program")

    decisions: list[WorkflowFidelityDecision] = []
    seen_passed_fingerprints: set[str] = set()
    for workflow in workflows:
        if not isinstance(workflow, OutputWorkflowDag):
            raise TypeError("workflows must contain OutputWorkflowDag records")

        external_inputs = tuple(sorted(set(workflow.external_input_identifiers)))
        if workflow.status != "passed" or workflow.fail_closed_reasons:
            fingerprint = _fingerprint(
                source_sha256=source_sha256,
                workflow=workflow,
                normalized_core_chain=workflow.core_raw_callees,
                external_spatial_inputs=external_inputs,
                removed_auxiliary_calls=(),
            )
            upstream_reasons = tuple(
                f"upstream:{reason}" for reason in workflow.fail_closed_reasons
            )
            decisions.append(
                WorkflowFidelityDecision(
                    source_sha256=source_sha256,
                    workflow_id=workflow.workflow_id,
                    sink_root_id=workflow.sink_root_id,
                    sink_line=workflow.sink_line,
                    fidelity_status="fail_closed",
                    fail_closed_reasons=("upstream_dag_not_passed", *upstream_reasons),
                    normalized_core_call_ordinals=(),
                    normalized_core_chain=(),
                    removed_auxiliary_calls=(),
                    external_spatial_inputs=external_inputs,
                    exact_dag_fingerprint=fingerprint,
                    training_admission=_FAILED_ADMISSION,
                )
            )
            continue

        normalized_ordinals, normalized_chain, removed_calls = _normalize_core_chain(
            workflow.core_call_ordinals,
            workflow.core_raw_callees,
            external_inputs,
        )
        fingerprint = _fingerprint(
            source_sha256=source_sha256,
            workflow=workflow,
            normalized_core_chain=normalized_chain,
            external_spatial_inputs=external_inputs,
            removed_auxiliary_calls=removed_calls,
        )
        structural_reasons: list[str] = []
        if _has_parallel_collection_merge(ast, workflow):
            structural_reasons.append("parallel_collection_branches_not_linearizable")
        if _has_empty_image_select_root(ast, workflow):
            structural_reasons.append("empty_image_select_root")
        if _has_mutable_from_images_dependency(ast, workflow):
            structural_reasons.append("mutable_container_dependency_not_closed")
        if _has_parallel_image_fan_in(ast, workflow):
            structural_reasons.append("parallel_image_fan_in_not_linearizable")
        if _has_stale_derived_band_after_rebind(ast, workflow):
            structural_reasons.append("stale_derived_band_after_rebind")
        band_lineage_mismatch, temporal_intersection_empty, catalog_temporal_coverage_empty = (
            _has_static_lineage_contradiction(ast, workflow)
        )
        if band_lineage_mismatch:
            structural_reasons.append("static_band_lineage_select_mismatch")
        if temporal_intersection_empty:
            structural_reasons.append("temporal_filter_intersection_empty")
        if catalog_temporal_coverage_empty:
            structural_reasons.append("catalog_temporal_coverage_empty")
        if structural_reasons:
            decisions.append(
                WorkflowFidelityDecision(
                    source_sha256=source_sha256,
                    workflow_id=workflow.workflow_id,
                    sink_root_id=workflow.sink_root_id,
                    sink_line=workflow.sink_line,
                    fidelity_status="fail_closed",
                    fail_closed_reasons=tuple(structural_reasons),
                    normalized_core_call_ordinals=normalized_ordinals,
                    normalized_core_chain=normalized_chain,
                    removed_auxiliary_calls=removed_calls,
                    external_spatial_inputs=external_inputs,
                    exact_dag_fingerprint=fingerprint,
                    training_admission=_FAILED_ADMISSION,
                )
            )
            continue
        if _has_static_single_band_mismatch(ast, workflow):
            decisions.append(
                WorkflowFidelityDecision(
                    source_sha256=source_sha256,
                    workflow_id=workflow.workflow_id,
                    sink_root_id=workflow.sink_root_id,
                    sink_line=workflow.sink_line,
                    fidelity_status="fail_closed",
                    fail_closed_reasons=("static_single_band_map_output_mismatch",),
                    normalized_core_call_ordinals=normalized_ordinals,
                    normalized_core_chain=normalized_chain,
                    removed_auxiliary_calls=removed_calls,
                    external_spatial_inputs=external_inputs,
                    exact_dag_fingerprint=fingerprint,
                    training_admission=_FAILED_ADMISSION,
                )
            )
            continue

        reasons: tuple[str, ...]
        if fingerprint in seen_passed_fingerprints:
            status = "duplicate"
            reasons = ("exact_output_duplicate",)
            admission = _DUPLICATE_ADMISSION
        else:
            seen_passed_fingerprints.add(fingerprint)
            status = "passed"
            reasons = ()
            admission = _PENDING_ADMISSION
        decisions.append(
            WorkflowFidelityDecision(
                source_sha256=source_sha256,
                workflow_id=workflow.workflow_id,
                sink_root_id=workflow.sink_root_id,
                sink_line=workflow.sink_line,
                fidelity_status=status,
                fail_closed_reasons=reasons,
                normalized_core_call_ordinals=normalized_ordinals,
                normalized_core_chain=normalized_chain,
                removed_auxiliary_calls=removed_calls,
                external_spatial_inputs=external_inputs,
                exact_dag_fingerprint=fingerprint,
                training_admission=admission,
            )
        )
    return tuple(decisions)
