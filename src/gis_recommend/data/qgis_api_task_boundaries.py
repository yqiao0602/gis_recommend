"""Conservative lexical task-boundary recovery for low-level PyQGIS calls."""

from __future__ import annotations

import ast
import hashlib
import json
from collections import defaultdict
from typing import Any


GEOMETRY_METHODS = {
    "buffer",
    "centroid",
    "combine",
    "convexhull",
    "difference",
    "intersection",
    "interpolate",
    "makevalid",
    "offsetcurve",
    "simplify",
    "smooth",
    "symdifference",
    "transform",
    "unaryunion",
}
ATTRIBUTE_METHODS = {
    "addattribute",
    "addattributes",
    "changeattributevalue",
    "changeattributevalues",
    "deleteattribute",
    "deleteattributes",
    "setattribute",
    "setattributes",
    "updatefields",
}
TERMINAL_STATIC_CALLS = {
    "qgsvectorfilewriter.writeasvectorformat",
    "qgsvectorfilewriter.writeasvectorformatv2",
    "qgsvectorfilewriter.writeasvectorformatv3",
}
BOUNDARY_RULE_ID = "typed-terminal-control-path-dag-v6"


def _name(node: ast.AST) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        base = _name(node.value)
        return f"{base}.{node.attr}" if base else node.attr
    if isinstance(node, ast.Call):
        return _name(node.func)
    if isinstance(node, ast.Subscript):
        return _name(node.value)
    return ""


def _parents(tree: ast.AST) -> dict[ast.AST, ast.AST]:
    return {
        child: parent
        for parent in ast.walk(tree)
        for child in ast.iter_child_nodes(parent)
    }


def _depth(node: ast.AST, parents: dict[ast.AST, ast.AST]) -> int:
    depth = 0
    current = node
    while current in parents:
        depth += 1
        current = parents[current]
    return depth


def _scope_node(node: ast.AST, parents: dict[ast.AST, ast.AST]) -> ast.AST:
    current: ast.AST | None = node
    while current is not None:
        if isinstance(current, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)):
            return current
        current = parents.get(current)
    current = node
    while parents.get(current) is not None:
        current = parents[current]
    return current


def _scope_name(scope: ast.AST, parents: dict[ast.AST, ast.AST]) -> str:
    if isinstance(scope, ast.Module):
        return "<module>"
    names = []
    current: ast.AST | None = scope
    while current is not None:
        if isinstance(current, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            names.append(current.name)
        elif isinstance(current, ast.Lambda):
            names.append(f"<lambda:{current.lineno}>")
        current = parents.get(current)
    return ".".join(reversed(names))


def _target_names(call: ast.Call, parents: dict[ast.AST, ast.AST]) -> list[str]:
    current: ast.AST = call
    while isinstance(parents.get(current), (ast.Expr, ast.Tuple, ast.List)):
        current = parents[current]
    parent = parents.get(current)
    target: ast.AST | None = None
    if isinstance(parent, ast.Assign) and parent.value is current:
        target = parent.targets[0] if parent.targets else None
    elif isinstance(parent, ast.AnnAssign) and parent.value is current:
        target = parent.target
    elif isinstance(parent, ast.NamedExpr) and parent.value is current:
        target = parent.target
    if target is None:
        return []
    return [
        node.id
        for node in ast.walk(target)
        if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store)
    ]


def _loaded_names(node: ast.AST) -> set[str]:
    return {
        item.id
        for item in ast.walk(node)
        if isinstance(item, ast.Name) and isinstance(item.ctx, ast.Load)
    }


def _stored_name_bindings(
    scope: ast.AST, parents: dict[ast.AST, ast.AST]
) -> dict[str, list[tuple[int, list[str]]]]:
    bindings: dict[str, list[tuple[int, list[str]]]] = defaultdict(list)
    for node in ast.walk(scope):
        if not (
            isinstance(node, ast.Name)
            and isinstance(node.ctx, ast.Store)
            and _scope_node(node, parents) is scope
        ):
            continue
        bindings[node.id].append((int(node.lineno), _control_path(node, parents)))
    return {
        name: sorted(values, key=lambda value: (value[0], value[1]))
        for name, values in bindings.items()
    }


def _control_path(
    node: ast.AST, parents: dict[ast.AST, ast.AST]
) -> list[str]:
    path = []
    current: ast.AST | None = node
    while current is not None:
        parent = parents.get(current)
        if isinstance(parent, ast.If):
            arm = "body" if current in parent.body else "orelse"
            path.append(f"if:{parent.lineno}:{arm}")
        current = parent
    return list(reversed(path))


def _control_paths_compatible(first: list[str], second: list[str]) -> bool:
    first_arms = {entry.rsplit(":", 1)[0]: entry.rsplit(":", 1)[1] for entry in first}
    second_arms = {
        entry.rsplit(":", 1)[0]: entry.rsplit(":", 1)[1] for entry in second
    }
    return all(
        first_arms[key] == second_arms[key]
        for key in first_arms.keys() & second_arms.keys()
    )


def _receiver(call: ast.Call) -> str:
    return _name(call.func.value) if isinstance(call.func, ast.Attribute) else ""


def _feature_name(name: str) -> bool:
    lowered = name.lower()
    return lowered in {"f", "ft", "feat", "feature", "outfeat", "outfeature"} or any(
        token in lowered for token in ("_feature", "feature_", "newfeature")
    )


def _seed_scope_types(scope: ast.AST) -> dict[str, str]:
    types: dict[str, str] = {}
    if isinstance(scope, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)):
        arguments = scope.args
        for argument in (
            *arguments.posonlyargs,
            *arguments.args,
            *arguments.kwonlyargs,
        ):
            name = argument.arg
            lowered = name.lower()
            if _feature_name(lowered):
                types[name] = "feature"
            elif lowered in {"geometry", "geom"} or lowered.endswith("_geometry"):
                types[name] = "geometry"
            elif "sink" in lowered:
                types[name] = "feature_sink"
            elif lowered == "writer" or lowered.endswith("_writer"):
                types[name] = "vector_writer"
            elif "index" in lowered or lowered.endswith("idx"):
                types[name] = "spatial_index"
    for node in ast.walk(scope):
        if not isinstance(node, (ast.For, ast.AsyncFor)):
            continue
        if not isinstance(node.iter, ast.Call) or not _name(node.iter.func).lower().endswith(
            ".getfeatures"
        ):
            continue
        for target in ast.walk(node.target):
            if isinstance(target, ast.Name):
                types[target.id] = "feature"
    return types


def _infer_result_types(
    call_name: str, receiver: str, receiver_type: str, targets: list[str]
) -> dict[str, str]:
    lowered = call_name.lower()
    result_type = ""
    if lowered == "qgsvectorlayer":
        result_type = "vector_layer"
    elif lowered == "qgsrasterlayer":
        result_type = "raster_layer"
    elif lowered in {"qgsfeature", "qgsvectorlayerutils.createfeature"}:
        result_type = "feature"
    elif lowered == "qgsspatialindex":
        result_type = "spatial_index"
    elif lowered == "qgscoordinatetransform":
        result_type = "coordinate_transform"
    elif lowered.startswith("qgsgeometry") or lowered.endswith(".geometry"):
        result_type = "geometry"
    elif lowered in {"qgsvectorfilewriter", "qgsvectorfilewriter.create"}:
        result_type = "vector_writer"
    elif lowered.endswith(".parameterassink"):
        return {targets[0]: "feature_sink"} if targets else {}
    elif lowered.endswith(".dataprovider"):
        result_type = {
            "vector_layer": "vector_provider",
            "raster_layer": "raster_provider",
        }.get(receiver_type, "provider")
    elif lowered == "qgsrastercalculator":
        result_type = "raster_calculator"
    if not result_type:
        return {}
    return {target: result_type for target in targets}


def _classify(
    call_name: str,
    receiver: str,
    receiver_type: str,
    argument_types: set[str],
) -> tuple[str, str, bool] | None:
    lowered = call_name.lower()
    method = lowered.rpartition(".")[2]
    receiver_leaf = receiver.lower().rpartition(".")[2]

    if lowered in TERMINAL_STATIC_CALLS:
        return "sink_output", "sink_output", True
    if method in {"addfeature", "addfeatures"} and (
        receiver_type in {"feature_sink", "vector_writer"}
        or receiver_leaf in {"sink", "writer", "output_sink"}
    ):
        return "sink_output", "sink_output", True
    if receiver_type == "raster_writer" and method == "writeraster":
        return "sink_output", "sink_output", True
    if method == "setgeometry" and (
        receiver_type == "feature" or _feature_name(receiver_leaf)
    ):
        return "feature_mutation", "feature_geometry", False
    if method in {"setattribute", "setattributes"} and (
        receiver_type == "feature" or _feature_name(receiver_leaf)
    ):
        return "attribute_mutation", "field_attribute_edit", False
    if method in ATTRIBUTE_METHODS - {"setattribute", "setattributes"} and (
        receiver_type in {"vector_layer", "vector_provider"}
        or "provider" in receiver_leaf
        or receiver_leaf in {"pr", "dp", "vl", "vlayer", "layer"}
    ):
        return "attribute_mutation", "field_attribute_edit", False
    if method in GEOMETRY_METHODS and (
        receiver_type == "geometry"
        or receiver_leaf in {"geometry", "geom"}
        or receiver_leaf.endswith("_geometry")
    ):
        if method == "transform" and "coordinate_transform" in argument_types:
            return "crs_transform", "crs_transform", False
        return "geometry_transform", "feature_geometry", False
    if receiver_type == "coordinate_transform" and method == "transform":
        return "crs_transform", "crs_transform", False
    if (
        receiver_type == "spatial_index"
        or "index" in receiver_leaf
        or receiver_leaf.endswith("idx")
    ) and method in {"intersects", "nearestneighbor"}:
        return "spatial_query", "spatial_index_query", False
    if receiver_type == "raster_calculator" and method == "processcalculation":
        return "raster_calculation", "raster_io_pixel", False
    return None


def _terminal_ancestor_components(
    steps: list[dict[str, Any]], edges: list[list[int]]
) -> list[list[int]]:
    predecessors: dict[int, set[int]] = defaultdict(set)
    for source, target in edges:
        predecessors[target].add(source)
    components = []
    for terminal in (
        index for index, step in enumerate(steps) if step["terminal_evidence"]
    ):
        pending = [terminal]
        ancestors: set[int] = set()
        while pending:
            current = pending.pop()
            if current in ancestors:
                continue
            ancestors.add(current)
            pending.extend(sorted(predecessors[current], reverse=True))
        components.append(sorted(ancestors))
    return components


def _component_record(
    scope: str,
    steps: list[dict[str, Any]],
    edges: list[list[int]],
    component: list[int],
) -> dict[str, Any]:
    index_map = {old: new for new, old in enumerate(component)}
    component_steps = [steps[index] for index in component]
    component_edges = sorted(
        [
            [index_map[source], index_map[target]]
            for source, target in edges
            if source in index_map and target in index_map
        ]
    )
    terminal_count = sum(bool(step["terminal_evidence"]) for step in component_steps)
    payload = {
        "scope": scope,
        "steps": [
            (step["call_role"], step["line_start"], step["call_name"])
            for step in component_steps
        ],
        "edges": component_edges,
    }
    return {
        "unit_id": hashlib.sha256(
            json.dumps(payload, sort_keys=True).encode("utf-8")
        ).hexdigest(),
        "lexical_scope": scope,
        "source_span": [
            min(step["line_start"] for step in component_steps),
            max(step["line_end"] for step in component_steps),
        ],
        "steps": component_steps,
        "dependency_edges": component_edges,
        "terminal_evidence_count": terminal_count,
        "pattern_names": sorted(
            {step["pattern_family"] for step in component_steps}
        ),
    }


def extract_task_boundaries(source_text: str) -> dict[str, Any]:
    tree = ast.parse(source_text)
    parents = _parents(tree)
    calls_by_scope: dict[ast.AST, list[ast.Call]] = defaultdict(list)
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            calls_by_scope[_scope_node(node, parents)].append(node)

    semantic_steps = []
    candidate_units = []
    deferred_units = []
    for scope, calls in sorted(
        calls_by_scope.items(),
        key=lambda item: min(call.lineno for call in item[1]),
    ):
        scope_name = _scope_name(scope, parents)
        types = _seed_scope_types(scope)
        stored_name_bindings = _stored_name_bindings(scope, parents)
        steps: list[dict[str, Any]] = []
        step_calls: list[ast.Call] = []
        for call in sorted(
            calls,
            key=lambda item: (
                item.lineno,
                -_depth(item, parents),
                item.col_offset,
            ),
        ):
            call_name = _name(call.func)
            receiver = _receiver(call)
            receiver_leaf = receiver.rpartition(".")[2]
            targets = _target_names(call, parents)
            receiver_type = types.get(receiver_leaf, "")
            argument_names = set().union(*(_loaded_names(arg) for arg in call.args)) if call.args else set()
            argument_types = {types[name] for name in argument_names if name in types}
            inferred = _infer_result_types(
                call_name, receiver, receiver_type, targets
            )
            classification = _classify(
                call_name, receiver, receiver_type, argument_types
            )
            types.update(inferred)
            if classification is None:
                continue
            role, family, terminal = classification
            if terminal and call_name.lower() in TERMINAL_STATIC_CALLS:
                data_names = _loaded_names(call.args[0]) if call.args else set()
                consumes = sorted(data_names)
            else:
                consumes = sorted(
                    argument_names | ({receiver_leaf} if receiver_leaf else set())
                )
            produces = list(targets)
            if role in {"feature_mutation", "attribute_mutation"} and receiver_leaf:
                produces.append(receiver_leaf)
            step = {
                "step_index": len(steps),
                "call_name": call_name,
                "call_role": role,
                "pattern_family": family,
                "line_start": int(call.lineno),
                "line_end": int(call.end_lineno or call.lineno),
                "lexical_scope": scope_name,
                "receiver": receiver,
                "receiver_type": receiver_type,
                "assignment_targets": targets,
                "consumed_names": consumes,
                "produced_names": sorted(set(produces)),
                "terminal_evidence": terminal,
                "control_path": _control_path(call, parents),
            }
            steps.append(step)
            step_calls.append(call)
            semantic_steps.append(step)

        produced_by: dict[str, int] = {}
        edges: list[list[int]] = []
        for index, step in enumerate(steps):
            for name in step["consumed_names"]:
                if name in produced_by and produced_by[name] != index:
                    producer = produced_by[name]
                    rebound = any(
                        steps[producer]["line_end"] < line <= step["line_start"]
                        and _control_paths_compatible(
                            steps[producer]["control_path"], binding_path
                        )
                        and _control_paths_compatible(
                            binding_path, step["control_path"]
                        )
                        for line, binding_path in stored_name_bindings.get(name, [])
                    )
                    if rebound:
                        produced_by.pop(name, None)
                        continue
                    if not _control_paths_compatible(
                        steps[producer]["control_path"], step["control_path"]
                    ):
                        continue
                    edge = [producer, index]
                    if edge not in edges:
                        edges.append(edge)
            if step["terminal_evidence"]:
                produced_by.clear()
            else:
                for name in step["produced_names"]:
                    produced_by[name] = index

        for consumer_index, (consumer, consumer_call) in enumerate(
            zip(steps, step_calls)
        ):
            if (
                consumer["call_role"] != "feature_mutation"
                or not consumer["call_name"].lower().endswith(".setgeometry")
                or not consumer_call.args
            ):
                continue
            payload_nodes = set(ast.walk(consumer_call.args[0]))
            for producer_index, (producer, producer_call) in enumerate(
                zip(steps, step_calls)
            ):
                if (
                    producer_index != consumer_index
                    and producer["call_role"] in {"geometry_transform", "crs_transform"}
                    and producer_call in payload_nodes
                    and _control_paths_compatible(
                        producer["control_path"], consumer["control_path"]
                    )
                ):
                    edge = [producer_index, consumer_index]
                    if edge not in edges:
                        edges.append(edge)

        for component in _terminal_ancestor_components(steps, edges):
            unit = _component_record(scope_name, steps, edges, component)
            has_operation = any(
                not step["terminal_evidence"] for step in unit["steps"]
            )
            span = int(unit["source_span"][1]) - int(unit["source_span"][0])
            outside_steps = [
                step
                for index, step in enumerate(steps)
                if index not in component
                and unit["source_span"][0]
                <= step["line_start"]
                <= unit["source_span"][1]
            ]
            outside_names = {
                name
                for step in outside_steps
                for name in step["produced_names"]
            }
            interleaved = any(
                step["terminal_evidence"]
                and unit["source_span"][1] < step["line_start"] <= unit["source_span"][1] + 8
                and bool(outside_names & set(step["consumed_names"]))
                for step in steps
            )
            unit_terminal = next(
                step for step in unit["steps"] if step["terminal_evidence"]
            )
            unit_produced_names = {
                name
                for step in unit["steps"]
                for name in step["produced_names"]
            }
            adjacent_same_receiver_terminal = any(
                index not in component
                and step["terminal_evidence"]
                and unit_terminal["line_end"] < step["line_start"] <= unit_terminal["line_end"] + 8
                and unit_terminal["call_name"].lower() not in TERMINAL_STATIC_CALLS
                and step["receiver"] == unit_terminal["receiver"]
                and not (unit_produced_names & set(step["consumed_names"]))
                and _control_paths_compatible(
                    unit_terminal["control_path"], step["control_path"]
                )
                for index, step in enumerate(steps)
            )
            if (
                len(component) >= 2
                and has_operation
                and unit["dependency_edges"]
                and span <= 100
                and not interleaved
                and not adjacent_same_receiver_terminal
            ):
                unit.update(
                    {
                        "boundary_status": "candidate",
                        "boundary_rule_id": BOUNDARY_RULE_ID,
                        "training_admission": "not_granted_task_boundary_only",
                        "training_row_emitted": False,
                    }
                )
                candidate_units.append(unit)
            else:
                reason = (
                    "source_span_exceeds_100_lines"
                    if span > 100
                    else (
                        "adjacent_same_receiver_different_payload_terminal"
                        if adjacent_same_receiver_terminal
                        else (
                            "interleaved_semantic_steps_outside_terminal_path"
                            if interleaved
                            else "terminal_component_has_no_connected_operation"
                        )
                    )
                )
                unit.update(
                    {
                        "boundary_status": "deferred",
                        "reason": reason,
                        "training_admission": "not_granted",
                        "training_row_emitted": False,
                    }
                )
                deferred_units.append(unit)

    return {
        "schema": "gis_recommend.qgis_api_task_boundaries.v1",
        "semantic_steps": sorted(
            semantic_steps,
            key=lambda step: (step["line_start"], step["step_index"]),
        ),
        "candidate_units": candidate_units,
        "deferred_units": deferred_units,
        "training_admission": "not_granted_task_boundary_extraction_only",
        "training_rows_emitted": 0,
    }
