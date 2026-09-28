"""Conservative top-level def-use slicing for source-grounded GEE workflows."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable


_KNOWN_GLOBALS = frozenset(
    {
        "Array",
        "Chart",
        "Date",
        "Export",
        "JSON",
        "Map",
        "Math",
        "Number",
        "Object",
        "parseInt",
        "String",
        "console",
        "ee",
        "print",
        "require",
        "ui",
    }
)


@dataclass(frozen=True)
class DataflowDefinition:
    definition_id: str
    target: str
    version: int
    kind: str
    statement_index: int
    start_line: int
    end_line: int
    dependency_ids: tuple[str, ...]
    unresolved_identifiers: tuple[str, ...]


@dataclass(frozen=True)
class BackwardSlice:
    root_id: str
    root_kind: str
    root_line: int
    definition_ids: tuple[str, ...]
    dependency_edges: tuple[tuple[str, str], ...]
    core_call_ordinals: tuple[int, ...]
    unresolved_identifiers: tuple[str, ...]


@dataclass(frozen=True)
class DataflowSliceResult:
    definitions: tuple[DataflowDefinition, ...]
    slices: tuple[BackwardSlice, ...]
    quality_flags: tuple[str, ...]


@dataclass(frozen=True)
class LocalSubworkflowUnit:
    definition_id: str
    target: str
    kind: str
    start_line: int
    end_line: int
    dependency_ids: tuple[str, ...]
    core_call_ordinals: tuple[int, ...]
    unresolved_identifiers: tuple[str, ...]


@dataclass(frozen=True)
class LocalSubworkflowResult:
    units: tuple[LocalSubworkflowUnit, ...]
    quality_flags: tuple[str, ...]


@dataclass(frozen=True)
class _Root:
    root_id: str
    kind: str
    line: int
    start_line: int
    end_line: int
    dependency_ids: tuple[str, ...]
    unresolved_identifiers: tuple[str, ...]
    owned_definition_id: str | None = None
    expression: dict[str, Any] | None = None


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


def _static_binding_name(node: Any) -> str | None:
    if not isinstance(node, dict):
        return None
    if node.get("type") == "Identifier":
        name = node.get("name")
        return name if isinstance(name, str) and name else None
    if node.get("type") != "MemberExpression" or node.get("computed"):
        return None
    root = _static_binding_name(node.get("object"))
    prop = node.get("property")
    name = prop.get("name") if isinstance(prop, dict) and prop.get("type") == "Identifier" else None
    if root is None or not isinstance(name, str) or not name:
        return None
    return f"{root}.{name}"


def _declared_names(node: Any) -> set[str]:
    names: set[str] = set()
    if not isinstance(node, dict):
        return names
    node_type = node.get("type")
    if node_type in {"FunctionExpression", "ArrowFunctionExpression", "FunctionDeclaration"}:
        for parameter in node.get("params", []):
            if isinstance(parameter, dict) and parameter.get("type") == "Identifier":
                name = parameter.get("name")
                if isinstance(name, str):
                    names.add(name)
    if node_type == "VariableDeclarator":
        identifier = node.get("id")
        if isinstance(identifier, dict) and identifier.get("type") == "Identifier":
            name = identifier.get("name")
            if isinstance(name, str):
                names.add(name)
    if node_type == "FunctionDeclaration":
        identifier = node.get("id")
        if isinstance(identifier, dict) and identifier.get("type") == "Identifier":
            name = identifier.get("name")
            if isinstance(name, str):
                names.add(name)
    for key, value in node.items():
        if key in {"id", "params", "loc", "range"}:
            continue
        if isinstance(value, dict):
            names.update(_declared_names(value))
        elif isinstance(value, list):
            for child in value:
                names.update(_declared_names(child))
    return names


def _collect_identifiers(
    node: Any,
    *,
    bound: frozenset[str] = frozenset(),
    property_position: bool = False,
) -> set[str]:
    if not isinstance(node, dict):
        return set()
    node_type = node.get("type")
    if node_type == "Identifier":
        name = node.get("name")
        if property_position or not isinstance(name, str) or name in bound or name in _KNOWN_GLOBALS:
            return set()
        return {name}
    if node_type in {"FunctionExpression", "ArrowFunctionExpression", "FunctionDeclaration"}:
        local_bound = frozenset(set(bound) | _declared_names(node))
        return _collect_identifiers(node.get("body"), bound=local_bound)
    if node_type == "MemberExpression":
        identifiers = _collect_identifiers(node.get("object"), bound=bound)
        identifiers.update(
            _collect_identifiers(
                node.get("property"),
                bound=bound,
                property_position=not bool(node.get("computed")),
            )
        )
        return identifiers
    if node_type == "Property":
        identifiers = _collect_identifiers(
            node.get("key"),
            bound=bound,
            property_position=not bool(node.get("computed")),
        )
        identifiers.update(_collect_identifiers(node.get("value"), bound=bound))
        return identifiers
    identifiers: set[str] = set()
    for key, value in node.items():
        if key in {"id", "loc", "range"}:
            continue
        if isinstance(value, dict):
            identifiers.update(_collect_identifiers(value, bound=bound))
        elif isinstance(value, list):
            for child in value:
                identifiers.update(_collect_identifiers(child, bound=bound))
    return identifiers


def _call_root(node: Any) -> str | None:
    if not isinstance(node, dict) or node.get("type") != "CallExpression":
        return None
    callee = _static_binding_name(node.get("callee"))
    if not callee:
        return None
    return callee.split(".", 1)[0]


def _root_kind(expression: Any) -> str | None:
    root = _call_root(expression)
    if root in {"Map", "Chart", "ui", "print", "console"}:
        return "presentation_sink"
    if root == "Export":
        return "io_sink"
    if root is not None:
        return "expression_sink"
    return None


def _call_location(call: dict[str, Any]) -> tuple[int, int] | None:
    location = call.get("source_location")
    if not isinstance(location, dict):
        return None
    start_line = location.get("start_line")
    end_line = location.get("end_line")
    if not isinstance(start_line, int) or not isinstance(end_line, int):
        return None
    return start_line, end_line


def _static_property_key(node: Any) -> str | None:
    if not isinstance(node, dict):
        return None
    if node.get("type") == "Identifier":
        value = node.get("name")
    elif node.get("type") == "Literal":
        value = node.get("value")
    else:
        return None
    return value if isinstance(value, str) and value else None


def _selected_object_property_value(
    member: dict[str, Any],
    *,
    dependency_lookup: dict[str, str],
    definition_nodes: dict[str, dict[str, Any]],
) -> tuple[str, dict[str, Any]] | None:
    """Resolve ``object[key]`` only when both bindings are statically proven."""

    if member.get("type") != "MemberExpression" or not member.get("computed"):
        return None
    object_node = member.get("object")
    property_node = member.get("property")
    if not isinstance(object_node, dict) or object_node.get("type") != "Identifier":
        return None
    object_name = object_node.get("name")
    if not isinstance(object_name, str):
        return None
    object_definition_id = dependency_lookup.get(object_name)
    object_definition_node = definition_nodes.get(object_definition_id or "")
    if not isinstance(object_definition_node, dict) or object_definition_node.get("type") != "ObjectExpression":
        return None

    key = None
    if isinstance(property_node, dict) and property_node.get("type") == "Identifier":
        property_name = property_node.get("name")
        property_definition_id = (
            dependency_lookup.get(property_name) if isinstance(property_name, str) else None
        )
        key = _static_property_key(definition_nodes.get(property_definition_id or ""))
    else:
        key = _static_property_key(property_node)
    if key is None:
        return None

    matches: list[dict[str, Any]] = []
    for prop in object_definition_node.get("properties", []):
        if not isinstance(prop, dict) or prop.get("type") != "Property":
            continue
        prop_key = _static_property_key(prop.get("key"))
        value = prop.get("value")
        if prop_key == key and isinstance(value, dict):
            matches.append(value)
    if len(matches) != 1:
        return None
    return object_definition_id, matches[0]


def _object_property_projections(
    node: Any,
    *,
    dependency_lookup: dict[str, str],
    definition_nodes: dict[str, dict[str, Any]],
) -> tuple[dict[str, dict[str, Any]], bool]:
    projections: dict[str, dict[str, Any]] = {}
    ambiguous = False

    def walk(value: Any) -> None:
        nonlocal ambiguous
        if isinstance(value, list):
            for child in value:
                walk(child)
            return
        if not isinstance(value, dict):
            return
        if value.get("type") == "MemberExpression" and value.get("computed"):
            object_node = value.get("object")
            object_name = (
                object_node.get("name")
                if isinstance(object_node, dict) and object_node.get("type") == "Identifier"
                else None
            )
            object_definition_id = (
                dependency_lookup.get(object_name) if isinstance(object_name, str) else None
            )
            object_definition_node = definition_nodes.get(object_definition_id or "")
            if isinstance(object_definition_node, dict) and object_definition_node.get("type") == "ObjectExpression":
                selected = _selected_object_property_value(
                    value,
                    dependency_lookup=dependency_lookup,
                    definition_nodes=definition_nodes,
                )
                if selected is None:
                    ambiguous = True
                else:
                    selected_definition_id, selected_value = selected
                    existing = projections.get(selected_definition_id)
                    if existing is not None and existing is not selected_value:
                        ambiguous = True
                    else:
                        projections[selected_definition_id] = selected_value
        for key, child in value.items():
            if key not in {"loc", "range"}:
                walk(child)

    walk(node)
    return projections, ambiguous


def build_backward_slices(
    ast: dict[str, Any], core_call_evidence: Iterable[dict[str, Any]]
) -> DataflowSliceResult:
    """Build source-position-backed slices without inferring missing definitions."""

    body = ast.get("body") if isinstance(ast, dict) and ast.get("type") == "Program" else None
    if not isinstance(body, list):
        raise ValueError("AST root must be an ESTree Program")

    flags: set[str] = set()
    versions: dict[str, list[str]] = {}
    definitions: list[DataflowDefinition] = []
    definitions_by_id: dict[str, DataflowDefinition] = {}
    definition_nodes: dict[str, dict[str, Any]] = {}
    definition_dependency_lookup: dict[str, dict[str, str]] = {}
    roots: list[_Root] = []

    hoisted_functions: dict[str, str] = {}
    function_counts: dict[str, int] = {}
    for statement in body:
        if not isinstance(statement, dict) or statement.get("type") != "FunctionDeclaration":
            continue
        identifier = statement.get("id")
        name = identifier.get("name") if isinstance(identifier, dict) else None
        if isinstance(name, str) and name:
            function_counts[name] = function_counts.get(name, 0) + 1
            hoisted_functions[name] = f"{name}@{function_counts[name]}"

    def resolve_identifiers(names: set[str]) -> tuple[tuple[str, ...], tuple[str, ...]]:
        dependency_ids: list[str] = []
        unresolved: list[str] = []
        for name in sorted(names):
            if versions.get(name):
                dependency_ids.append(versions[name][-1])
            elif name in hoisted_functions:
                dependency_ids.append(hoisted_functions[name])
            else:
                unresolved.append(name)
        return tuple(dependency_ids), tuple(unresolved)

    def add_definition(
        *,
        target: str,
        kind: str,
        statement_index: int,
        location: tuple[int, int],
        dependency_names: set[str],
        definition_node: dict[str, Any],
        forced_id: str | None = None,
    ) -> DataflowDefinition:
        version = len(versions.get(target, [])) + 1
        definition_id = forced_id or f"{target}@{version}"
        dependency_ids, unresolved = resolve_identifiers(dependency_names)
        definition = DataflowDefinition(
            definition_id=definition_id,
            target=target,
            version=version,
            kind=kind,
            statement_index=statement_index,
            start_line=location[0],
            end_line=location[1],
            dependency_ids=dependency_ids,
            unresolved_identifiers=unresolved,
        )
        definitions.append(definition)
        definitions_by_id[definition_id] = definition
        definition_nodes[definition_id] = definition_node
        definition_dependency_lookup[definition_id] = {
            definitions_by_id[dependency_id].target: dependency_id
            for dependency_id in dependency_ids
            if dependency_id in definitions_by_id
        }
        versions.setdefault(target, []).append(definition_id)
        return definition

    for statement_index, statement in enumerate(body):
        if not isinstance(statement, dict):
            continue
        location = _location(statement)
        if location is None:
            flags.add("missing_statement_location")
            continue
        node_type = statement.get("type")
        if node_type == "FunctionDeclaration":
            identifier = statement.get("id")
            name = identifier.get("name") if isinstance(identifier, dict) else None
            if isinstance(name, str) and name:
                add_definition(
                    target=name,
                    kind="function_helper",
                    statement_index=statement_index,
                    location=location,
                    dependency_names=_collect_identifiers(statement),
                    definition_node=statement,
                    forced_id=hoisted_functions.get(name),
                )
            continue
        if node_type == "VariableDeclaration":
            for declaration in statement.get("declarations", []):
                if not isinstance(declaration, dict):
                    continue
                identifier = declaration.get("id")
                name = identifier.get("name") if isinstance(identifier, dict) else None
                if not isinstance(name, str) or not name:
                    flags.add("unsupported_binding_pattern")
                    continue
                init = declaration.get("init")
                # A same-scope ``var name;`` is a no-op redeclaration in JavaScript.
                # It must not replace an earlier value in the def-use version chain.
                if init is None and statement.get("kind") == "var":
                    continue
                kind = (
                    "function_helper"
                    if isinstance(init, dict)
                    and init.get("type") in {"FunctionExpression", "ArrowFunctionExpression"}
                    else "variable"
                )
                add_definition(
                    target=name,
                    kind=kind,
                    statement_index=statement_index,
                    location=location,
                    dependency_names=_collect_identifiers(init),
                    definition_node=init if isinstance(init, dict) else declaration,
                )
            continue
        if node_type != "ExpressionStatement":
            continue
        expression = statement.get("expression")
        if isinstance(expression, dict) and expression.get("type") == "SequenceExpression":
            for child in expression.get("expressions", []):
                if (
                    not isinstance(child, dict)
                    or child.get("type") != "AssignmentExpression"
                    or child.get("operator") != "="
                ):
                    continue
                target = _static_binding_name(child.get("left"))
                if target is None or "." in target:
                    flags.add("unsupported_assignment_target")
                    continue
                child_location = _location(child) or location
                add_definition(
                    target=target,
                    kind="sequence_assignment",
                    statement_index=statement_index,
                    location=child_location,
                    dependency_names=_collect_identifiers(child.get("right")),
                    definition_node=(
                        child.get("right")
                        if isinstance(child.get("right"), dict)
                        else child
                    ),
                )
            continue
        if isinstance(expression, dict) and expression.get("type") == "AssignmentExpression":
            if expression.get("operator") != "=":
                flags.add("compound_assignment_unresolved")
                continue
            target = _static_binding_name(expression.get("left"))
            if target is None or "." in target:
                flags.add("unsupported_assignment_target")
                continue
            add_definition(
                target=target,
                kind="assignment",
                statement_index=statement_index,
                location=location,
                dependency_names=_collect_identifiers(expression.get("right")),
                definition_node=(
                    expression.get("right")
                    if isinstance(expression.get("right"), dict)
                    else expression
                ),
            )
            continue
        kind = _root_kind(expression)
        if kind is None:
            continue
        dependency_ids, unresolved = resolve_identifiers(_collect_identifiers(expression))
        roots.append(
            _Root(
                root_id=f"sink@{location[0]}:{len(roots) + 1}",
                kind=kind,
                line=location[0],
                start_line=location[0],
                end_line=location[1],
                dependency_ids=dependency_ids,
                unresolved_identifiers=unresolved,
                expression=expression,
            )
        )

    consumed = {
        dependency_id
        for definition in definitions
        for dependency_id in definition.dependency_ids
    }
    consumed.update(
        dependency_id for root in roots for dependency_id in root.dependency_ids
    )

    calls = [
        call
        for call in core_call_evidence
        if isinstance(call, dict) and call.get("classification", "core") == "core"
    ]
    definition_core_calls: dict[str, set[int]] = {item.definition_id: set() for item in definitions}
    for definition in definitions:
        for call in calls:
            call_location = _call_location(call)
            ordinal = call.get("ordinal")
            if (
                call_location is not None
                and isinstance(ordinal, int)
                and definition.start_line <= call_location[0]
                and call_location[1] <= definition.end_line
            ):
                definition_core_calls[definition.definition_id].add(ordinal)

    for definition in definitions:
        if definition.definition_id in consumed or definition.kind == "function_helper":
            continue
        if not definition_core_calls[definition.definition_id]:
            continue
        roots.append(
            _Root(
                root_id=f"leaf@{definition.definition_id}",
                kind="unconsumed_core_leaf",
                line=definition.start_line,
                start_line=definition.start_line,
                end_line=definition.end_line,
                dependency_ids=definition.dependency_ids,
                unresolved_identifiers=definition.unresolved_identifiers,
                owned_definition_id=definition.definition_id,
            )
        )

    slices: list[BackwardSlice] = []
    for root in sorted(roots, key=lambda item: (item.line, item.root_id)):
        ordered_ids: list[str] = []
        edges: set[tuple[str, str]] = set()
        unresolved = set(root.unresolved_identifiers)
        visiting: set[str] = set()
        selected_nodes_by_definition: dict[str, dict[str, Any]] = {}

        def visit(definition_id: str, selected_node: dict[str, Any] | None = None) -> None:
            if definition_id in visiting or definition_id in ordered_ids:
                if definition_id in visiting:
                    flags.add("cyclic_definition_dependency")
                return
            definition = definitions_by_id.get(definition_id)
            if definition is None:
                unresolved.add(definition_id.split("@", 1)[0])
                return
            if selected_node is not None:
                selected_nodes_by_definition[definition_id] = selected_node
            visiting.add(definition_id)
            node = selected_node or definition_nodes.get(definition_id)
            dependency_ids = definition.dependency_ids
            definition_unresolved = definition.unresolved_identifiers
            if selected_node is not None:
                selected_names = _collect_identifiers(selected_node)
                lookup = definition_dependency_lookup.get(definition_id, {})
                dependency_ids = tuple(
                    lookup[name] for name in sorted(selected_names) if name in lookup
                )
                definition_unresolved = tuple(
                    sorted(name for name in selected_names if name not in lookup)
                )
            projections, ambiguous_projection = _object_property_projections(
                node,
                dependency_lookup=definition_dependency_lookup.get(definition_id, {}),
                definition_nodes=definition_nodes,
            )
            if ambiguous_projection:
                unresolved.add("dynamic_computed_object_property")
            for dependency_id in dependency_ids:
                edges.add((definition_id, dependency_id))
                visit(dependency_id, projections.get(dependency_id))
            visiting.remove(definition_id)
            unresolved.update(definition_unresolved)
            ordered_ids.append(definition_id)

        root_lookup = {
            definitions_by_id[dependency_id].target: dependency_id
            for dependency_id in root.dependency_ids
            if dependency_id in definitions_by_id
        }
        root_projections, ambiguous_root_projection = _object_property_projections(
            root.expression,
            dependency_lookup=root_lookup,
            definition_nodes=definition_nodes,
        )
        if ambiguous_root_projection:
            unresolved.add("dynamic_computed_object_property")
        for dependency_id in root.dependency_ids:
            visit(dependency_id, root_projections.get(dependency_id))
        if root.owned_definition_id is not None:
            visit(root.owned_definition_id)
        ordered_ids.sort(
            key=lambda definition_id: (
                definitions_by_id[definition_id].start_line,
                definitions_by_id[definition_id].statement_index,
                definition_id,
            )
        )

        ordinals: set[int] = set()
        selected_nodes_by_definition.update(root_projections)
        for definition_id in ordered_ids:
            selected_node = selected_nodes_by_definition.get(definition_id)
            if selected_node is None:
                ordinals.update(definition_core_calls.get(definition_id, set()))
                continue
            selected_location = _location(selected_node)
            for call in calls:
                call_location = _call_location(call)
                ordinal = call.get("ordinal")
                if (
                    selected_location is not None
                    and call_location is not None
                    and isinstance(ordinal, int)
                    and selected_location[0] <= call_location[0]
                    and call_location[1] <= selected_location[1]
                ):
                    ordinals.add(ordinal)
        for call in calls:
            call_location = _call_location(call)
            ordinal = call.get("ordinal")
            if (
                call_location is not None
                and isinstance(ordinal, int)
                and root.start_line <= call_location[0]
                and call_location[1] <= root.end_line
            ):
                ordinals.add(ordinal)

        slices.append(
            BackwardSlice(
                root_id=root.root_id,
                root_kind=root.kind,
                root_line=root.line,
                definition_ids=tuple(ordered_ids),
                dependency_edges=tuple(sorted(edges)),
                core_call_ordinals=tuple(sorted(ordinals)),
                unresolved_identifiers=tuple(sorted(unresolved)),
            )
        )

    return DataflowSliceResult(
        definitions=tuple(definitions),
        slices=tuple(slices),
        quality_flags=tuple(sorted(flags)),
    )


def build_local_subworkflow_units(
    ast: dict[str, Any], core_call_evidence: Iterable[dict[str, Any]]
) -> LocalSubworkflowResult:
    """Split a workflow into definition-owned local units without ancestor expansion."""

    calls = [
        call
        for call in core_call_evidence
        if isinstance(call, dict) and call.get("classification", "core") == "core"
    ]
    dataflow = build_backward_slices(ast, calls)
    units: list[LocalSubworkflowUnit] = []
    flags = set(dataflow.quality_flags)
    for definition in dataflow.definitions:
        ordinals: list[int] = []
        locations: set[tuple[int, int]] = set()
        duplicate_location = False
        for call in calls:
            call_location = _call_location(call)
            ordinal = call.get("ordinal")
            if (
                call_location is None
                or not isinstance(ordinal, int)
                or call_location[0] < definition.start_line
                or call_location[1] > definition.end_line
            ):
                continue
            if call_location in locations:
                duplicate_location = True
            locations.add(call_location)
            ordinals.append(ordinal)
        if not ordinals:
            continue
        if duplicate_location and definition.kind == "function_helper":
            flags.add("repeated_helper_call_location")
        units.append(
            LocalSubworkflowUnit(
                definition_id=definition.definition_id,
                target=definition.target,
                kind=definition.kind,
                start_line=definition.start_line,
                end_line=definition.end_line,
                dependency_ids=definition.dependency_ids,
                core_call_ordinals=tuple(sorted(set(ordinals))),
                unresolved_identifiers=definition.unresolved_identifiers,
            )
        )
    return LocalSubworkflowResult(
        units=tuple(units),
        quality_flags=tuple(sorted(flags)),
    )
