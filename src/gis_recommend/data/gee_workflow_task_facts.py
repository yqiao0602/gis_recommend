"""Source-backed fact and task-text construction for frozen GEE workflows."""

from __future__ import annotations

from collections.abc import Iterable
from datetime import date
import json
import math
import re
from typing import Any

from gis_recommend.data.gee_dataflow_slicer import build_backward_slices


FACT_SCHEMA = "gis_recommend.gee_workflow_fact_bundle.v1"
TASK_TEXT_SCHEMA = "gis_recommend.gee_workflow_task_text_candidate.v1"
_PUBLIC_PROJECT_ASSET_PREFIXES = (
    "projects/planet-nicfi/assets/basemaps/",
    "projects/sat-io/open-datasets/",
    "projects/soilgrids-isric/",
)
_DATASET_CONSTRUCTORS = frozenset(
    {
        "ee.Image",
        "ee.ImageCollection",
        "ee.Feature",
        "ee.FeatureCollection",
    }
)
_GENERATED_IMAGE_CONSTRUCTORS = frozenset({"ee.Image.pixelLonLat"})
_SPATIAL_RESOURCE_CONSTRUCTORS = frozenset({"ee.Feature", "ee.FeatureCollection"})
_LANDSAT_PLATFORM_TOKEN_PATTERN = re.compile(r"L[A-Z][0-9]{2}")
_ISO_DATE_PATTERN = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}")
_VALID_LANDSAT_PLATFORM_TOKENS = frozenset(
    {"LC08", "LC09", "LE07", "LT04", "LT05", "LM01", "LM02", "LM03", "LM04", "LM05"}
)
_SPATIAL_METHODS = frozenset(
    {
        "clip",
        "cliptocollection",
        "filterbounds",
        "geometry",
        "intersection",
        "intersects",
        "paint",
        "reducebounds",
        "reduceRegion".lower(),
        "reduceRegions".lower(),
        "sample",
        "sampleregions",
    }
)
_OUTPUT_FIELDS = frozenset(
    {
        "assetId",
        "crs",
        "crsTransform",
        "description",
        "dimensions",
        "fileFormat",
        "fileNamePrefix",
        "fileDimensions",
        "folder",
        "formatOptions",
        "framesPerSecond",
        "maxFrames",
        "maxPixels",
        "maxVertices",
        "pyramidingPolicy",
        "region",
        "scale",
        "selectors",
        "shardSize",
        "skipEmptyTiles",
    }
)
_POSITIONAL_EXPORT_FIELDS = {
    "Export.image.toDrive": (
        "image",
        "description",
        "folder",
        "fileNamePrefix",
        "dimensions",
        "region",
        "scale",
        "crs",
        "crsTransform",
        "maxPixels",
        "shardSize",
        "fileDimensions",
        "skipEmptyTiles",
        "fileFormat",
        "formatOptions",
    ),
    "Export.image.toAsset": (
        "image",
        "description",
        "assetId",
        "pyramidingPolicy",
        "dimensions",
        "region",
        "scale",
        "crs",
        "crsTransform",
        "maxPixels",
    ),
    "Export.table.toDrive": (
        "collection",
        "description",
        "folder",
        "fileNamePrefix",
        "fileFormat",
        "selectors",
        "maxVertices",
    ),
    "Export.table.toAsset": ("collection", "description", "assetId", "maxVertices"),
    "Export.video.toDrive": (
        "collection",
        "description",
        "folder",
        "fileNamePrefix",
        "framesPerSecond",
        "dimensions",
        "region",
        "scale",
        "crs",
        "maxFrames",
    ),
    "Export.image": ("image", "description", "config"),
}

_EXPORT_FAMILY_CONTRACTS = {
    "Export.image": ("image", "ee.image", "image"),
    "Export.table": ("collection", "ee.featurecollection", "table"),
    "Export.video": ("collection", None, "video"),
    "Export.map": ("image", "ee.image", "map tiles"),
}


def _validate_public_dataset_id(value: str) -> None:
    if not value.startswith("LANDSAT/"):
        return
    platform_token = value.split("/", 2)[1]
    if (
        _LANDSAT_PLATFORM_TOKEN_PATTERN.fullmatch(platform_token)
        and platform_token not in _VALID_LANDSAT_PLATFORM_TOKENS
    ):
        raise ValueError(
            "invalid_public_dataset_id: unsupported LANDSAT platform token "
            f"{platform_token}"
        )


def _walk(node: Any) -> Iterable[dict[str, Any]]:
    if isinstance(node, dict):
        yield node
        for key, value in node.items():
            if key not in {"loc", "range"}:
                yield from _walk(value)
    elif isinstance(node, list):
        for value in node:
            yield from _walk(value)


def _callee_name(node: Any) -> str | None:
    if not isinstance(node, dict):
        return None
    if node.get("type") == "Identifier":
        name = node.get("name")
        return name if isinstance(name, str) and name else None
    if node.get("type") != "MemberExpression" or node.get("computed"):
        return None
    root = _callee_name(node.get("object"))
    prop = node.get("property")
    name = prop.get("name") if isinstance(prop, dict) else None
    return f"{root}.{name}" if root and isinstance(name, str) else None


def _location(node: Any) -> dict[str, int] | None:
    if not isinstance(node, dict):
        return None
    location = node.get("loc")
    start = location.get("start") if isinstance(location, dict) else None
    end = location.get("end") if isinstance(location, dict) else None
    if not isinstance(start, dict) or not isinstance(end, dict):
        return None
    values = {
        "start_line": start.get("line"),
        "start_column": start.get("column"),
        "end_line": end.get("line"),
        "end_column": end.get("column"),
    }
    if not all(isinstance(value, int) for value in values.values()):
        return None
    return values  # type: ignore[return-value]


def _location_key(location: Any) -> tuple[int, int, int, int] | None:
    if not isinstance(location, dict):
        return None
    values = tuple(
        location.get(key)
        for key in ("start_line", "start_column", "end_line", "end_column")
    )
    return values if all(isinstance(value, int) for value in values) else None  # type: ignore[return-value]


def _definition_node(ast: dict[str, Any], definition: Any) -> dict[str, Any]:
    statement = ast["body"][definition.statement_index]
    if definition.kind == "function_helper":
        return statement
    if statement.get("type") == "VariableDeclaration":
        for declaration in statement.get("declarations", []):
            identifier = declaration.get("id") if isinstance(declaration, dict) else None
            if isinstance(identifier, dict) and identifier.get("name") == definition.target:
                init = declaration.get("init")
                return init if isinstance(init, dict) else declaration
    expression = statement.get("expression")
    candidates = (
        expression.get("expressions", [])
        if isinstance(expression, dict) and expression.get("type") == "SequenceExpression"
        else [expression]
    )
    for candidate in candidates:
        if not isinstance(candidate, dict) or candidate.get("type") != "AssignmentExpression":
            continue
        left = candidate.get("left")
        if isinstance(left, dict) and left.get("name") == definition.target:
            right = candidate.get("right")
            return right if isinstance(right, dict) else candidate
    return statement


def _ast_without_locations(node: Any) -> Any:
    if isinstance(node, dict):
        return {
            key: _ast_without_locations(value)
            for key, value in node.items()
            if key not in {"loc", "range"}
        }
    if isinstance(node, list):
        return [_ast_without_locations(value) for value in node]
    return node


def _closure_bindings(
    ast: dict[str, Any], definition_ids: Iterable[str]
) -> tuple[list[tuple[str, dict[str, Any]]], dict[str, dict[str, Any]]]:
    definitions = build_backward_slices(ast, []).definitions
    by_id = {definition.definition_id: definition for definition in definitions}
    requested = [str(value) for value in definition_ids]
    missing = sorted(set(requested) - set(by_id))
    if missing:
        raise ValueError(f"definition IDs missing from AST: {missing}")
    ordered = [(value, _definition_node(ast, by_id[value])) for value in requested]
    bindings: dict[str, dict[str, Any]] = {}
    for definition_id, node in ordered:
        target = by_id[definition_id].target
        bindings[target] = node

    helpers: dict[str, list[dict[str, Any]]] = {}
    for _, node in ordered:
        if node.get("type") != "FunctionDeclaration":
            continue
        identifier = node.get("id")
        helper_name = identifier.get("name") if isinstance(identifier, dict) else None
        if isinstance(helper_name, str):
            helpers.setdefault(helper_name, []).append(node)

    formal_actuals: dict[str, list[dict[str, Any]]] = {}
    for helper_name, declarations in helpers.items():
        if len(declarations) != 1:
            continue
        params = declarations[0].get("params") or []
        if not all(
            isinstance(param, dict)
            and param.get("type") == "Identifier"
            and isinstance(param.get("name"), str)
            for param in params
        ):
            continue
        calls = [
            candidate
            for _, node in ordered
            for candidate in _walk(node)
            if candidate.get("type") == "CallExpression"
            and _callee_name(candidate.get("callee")) == helper_name
        ]
        if not calls:
            continue
        for index, param in enumerate(params):
            actuals: list[dict[str, Any]] = []
            for call in calls:
                arguments = call.get("arguments") or []
                if index >= len(arguments):
                    actuals = []
                    break
                actual = arguments[index]
                if not isinstance(actual, dict) or actual.get("type") == "SpreadElement":
                    actuals = []
                    break
                actuals.append(actual)
            if actuals:
                formal_actuals.setdefault(param["name"], []).extend(actuals)

    for formal, actuals in formal_actuals.items():
        if formal in bindings:
            continue
        signatures = [_ast_without_locations(actual) for actual in actuals]
        if all(signature == signatures[0] for signature in signatures[1:]):
            bindings[formal] = actuals[0]

    local_initializers: dict[str, list[dict[str, Any]]] = {}
    for declarations in helpers.values():
        if len(declarations) != 1:
            continue
        body = declarations[0].get("body")
        statements = body.get("body") if isinstance(body, dict) else None
        for statement in statements or []:
            if not isinstance(statement, dict) or statement.get("type") != "VariableDeclaration":
                continue
            for declaration in statement.get("declarations") or []:
                identifier = declaration.get("id") if isinstance(declaration, dict) else None
                initializer = declaration.get("init") if isinstance(declaration, dict) else None
                name = identifier.get("name") if isinstance(identifier, dict) else None
                if (
                    isinstance(name, str)
                    and isinstance(initializer, dict)
                    and identifier.get("type") == "Identifier"
                ):
                    local_initializers.setdefault(name, []).append(initializer)
    for name, initializers in local_initializers.items():
        if name in bindings:
            continue
        signatures = [_ast_without_locations(value) for value in initializers]
        if all(signature == signatures[0] for signature in signatures[1:]):
            bindings[name] = initializers[0]
    return ordered, bindings


def _static_value(
    node: Any,
    bindings: dict[str, dict[str, Any]],
    seen: frozenset[str] = frozenset(),
) -> tuple[bool, Any]:
    if not isinstance(node, dict):
        return False, None
    node_type = node.get("type")
    if node_type == "Literal":
        return True, node.get("value")
    if node_type == "Identifier":
        name = node.get("name")
        if not isinstance(name, str) or name in seen or name not in bindings:
            return False, None
        return _static_value(bindings[name], bindings, seen | {name})
    if node_type == "MemberExpression":
        property_node = node.get("property")
        if node.get("computed"):
            property_status, property_value = _static_value(property_node, bindings, seen)
            if not property_status or not isinstance(property_value, (str, int)):
                return False, None
        else:
            property_value = (
                property_node.get("name") if isinstance(property_node, dict) else None
            )
            if not isinstance(property_value, str):
                return False, None
        object_node = node.get("object")
        if isinstance(object_node, dict) and object_node.get("type") == "Identifier":
            object_name = object_node.get("name")
            bound_object = (
                bindings.get(object_name)
                if isinstance(object_name, str) and object_name not in seen
                else None
            )
            if isinstance(bound_object, dict) and bound_object.get("type") == "ObjectExpression":
                for prop in bound_object.get("properties") or []:
                    if _property_name(prop) == property_value:
                        return _static_value(
                            prop.get("value"),
                            bindings,
                            seen | {object_name},
                        )
                return False, None
        object_status, object_value = _static_value(object_node, bindings, seen)
        if not object_status:
            return False, None
        if isinstance(object_value, dict) and property_value in object_value:
            return True, object_value[property_value]
        if (
            isinstance(object_value, list)
            and isinstance(property_value, int)
            and not isinstance(property_value, bool)
            and 0 <= property_value < len(object_value)
        ):
            return True, object_value[property_value]
        return False, None
    if node_type == "ArrayExpression":
        values = [_static_value(value, bindings, seen) for value in node.get("elements", [])]
        return (all(status for status, _ in values), [value for _, value in values])
    if node_type == "ObjectExpression":
        result: dict[str, Any] = {}
        for prop in node.get("properties", []):
            if not isinstance(prop, dict) or prop.get("type") != "Property" or prop.get("computed"):
                return False, None
            key_node = prop.get("key")
            key = (
                key_node.get("name")
                if isinstance(key_node, dict) and key_node.get("type") == "Identifier"
                else key_node.get("value") if isinstance(key_node, dict) else None
            )
            status, value = _static_value(prop.get("value"), bindings, seen)
            if not isinstance(key, str) or not status:
                return False, None
            result[key] = value
        return True, result
    if node_type == "TemplateLiteral" and not node.get("expressions"):
        quasis = node.get("quasis") or []
        return True, "".join(
            str((quasi.get("value") or {}).get("cooked") or "")
            for quasi in quasis
            if isinstance(quasi, dict)
        )
    if node_type == "UnaryExpression" and node.get("operator") in {"+", "-"}:
        status, value = _static_value(node.get("argument"), bindings, seen)
        if status and isinstance(value, (int, float)) and not isinstance(value, bool):
            return True, value if node.get("operator") == "+" else -value
    if node_type == "BinaryExpression" and node.get("operator") in {"+", "<<", ">>", ">>>"}:
        left_status, left = _static_value(node.get("left"), bindings, seen)
        right_status, right = _static_value(node.get("right"), bindings, seen)
        if left_status and right_status:
            operator = node.get("operator")
            if operator == "+" and (isinstance(left, str) or isinstance(right, str)):
                return True, f"{left}{right}"
            if (
                isinstance(left, (int, float))
                and not isinstance(left, bool)
                and isinstance(right, (int, float))
                and not isinstance(right, bool)
            ):
                if operator == "+":
                    return True, left + right
                if not isinstance(left, int) or not isinstance(right, int):
                    return False, None
                shift = right & 31
                unsigned_left = left & 0xFFFFFFFF
                if operator == ">>>":
                    return True, unsigned_left >> shift
                signed_left = (
                    unsigned_left - 0x100000000
                    if unsigned_left >= 0x80000000
                    else unsigned_left
                )
                shifted = signed_left >> shift if operator == ">>" else signed_left << shift
                shifted &= 0xFFFFFFFF
                return True, shifted - 0x100000000 if shifted >= 0x80000000 else shifted
    if node_type == "CallExpression":
        callee = _callee_name(node.get("callee"))
        values = [_static_value(argument, bindings, seen) for argument in node.get("arguments", [])]
        if not all(status for status, _ in values):
            return False, None
        arguments = [value for _, value in values]
        if callee == "ee.Date" and len(arguments) == 1:
            return True, arguments[0]
        if (
            callee == "ee.Date.fromYMD"
            and len(arguments) == 3
            and all(isinstance(value, int) and not isinstance(value, bool) for value in arguments)
        ):
            year, month, day = arguments
            if 1 <= month <= 12 and 1 <= day <= 31:
                return True, f"{year:04d}-{month:02d}-{day:02d}"
        if callee in {"ee.Date.parse", "ee.DateRange"}:
            return True, {"callee": callee, "arguments": arguments}
        callee_node = node.get("callee")
        if isinstance(callee_node, dict) and callee_node.get("type") == "MemberExpression":
            prop = callee_node.get("property")
            method = prop.get("name") if isinstance(prop, dict) else None
            base_status, base = _static_value(callee_node.get("object"), bindings, seen)
            if base_status and method == "toString" and not arguments:
                if isinstance(base, bool):
                    return True, "true" if base else "false"
                if isinstance(base, str):
                    return True, base
                if isinstance(base, int) and not isinstance(base, bool):
                    return True, str(base)
                if isinstance(base, float) and math.isfinite(base):
                    return True, str(int(base)) if base.is_integer() else str(base)
            if base_status and method in {"advance", "difference", "format", "get", "millis"}:
                return True, {"base": base, "operation": method, "arguments": arguments}
    return False, None


def _constructor_resource(
    node: Any,
    bindings: dict[str, dict[str, Any]],
    seen: frozenset[str] = frozenset(),
    allowed_constructors: frozenset[str] = _DATASET_CONSTRUCTORS,
) -> tuple[str, str] | None:
    if not isinstance(node, dict):
        return None
    if node.get("type") == "Identifier":
        name = node.get("name")
        if isinstance(name, str) and name not in seen and name in bindings:
            return _constructor_resource(
                bindings[name],
                bindings,
                seen | {name},
                allowed_constructors,
            )
        return None
    if node.get("type") == "CallExpression":
        callee_node = node.get("callee")
        if isinstance(callee_node, dict) and callee_node.get("type") == "MemberExpression":
            receiver_resource = _constructor_resource(
                callee_node.get("object"),
                bindings,
                seen,
                allowed_constructors,
            )
            if receiver_resource is not None:
                return receiver_resource
    for candidate in _walk(node):
        if candidate.get("type") != "CallExpression":
            continue
        callee = _callee_name(candidate.get("callee"))
        if callee not in allowed_constructors and not str(callee or "").startswith("ee.Geometry"):
            continue
        arguments = candidate.get("arguments") or []
        status, value = _static_value(arguments[0], bindings, seen) if arguments else (False, None)
        if status and isinstance(value, str) and value:
            return callee, value
        if str(callee or "").startswith("ee.Geometry"):
            static_status, static_arguments = _static_arguments(candidate, bindings)
            if static_status == "all":
                return "ee.Geometry", json.dumps(
                    {"constructor": callee, "arguments": static_arguments},
                    ensure_ascii=False,
                    sort_keys=True,
                )
    return None


def _call_index(ast: dict[str, Any]) -> dict[tuple[int, int, int, int], dict[str, Any]]:
    result: dict[tuple[int, int, int, int], dict[str, Any]] = {}
    for node in _walk(ast):
        if node.get("type") != "CallExpression":
            continue
        key = _location_key(_location(node))
        if key is not None:
            result[key] = node
    return result


def _validate_classifier_evaluation_lineage(
    ast: dict[str, Any],
    *,
    relevant_nodes: Iterable[dict[str, Any]] | None = None,
) -> None:
    """Reject classifier metrics that are computed from an untrained object."""

    bindings: dict[str, dict[str, Any]] = {}
    train_names: set[str] = set()
    for node in _walk(ast):
        if node.get("type") != "VariableDeclarator":
            continue
        identifier = node.get("id")
        name = identifier.get("name") if isinstance(identifier, dict) else None
        initializer = node.get("init")
        if not isinstance(name, str) or not isinstance(initializer, dict):
            continue
        bindings[name] = initializer
        if _callee_name(initializer.get("callee")):
            callee = str(_callee_name(initializer.get("callee"))).casefold()
            if callee.endswith(".train"):
                train_names.add(name)

    def is_trained(node: Any, seen: frozenset[str] = frozenset()) -> bool:
        if not isinstance(node, dict):
            return False
        if node.get("type") == "Identifier":
            name = node.get("name")
            if not isinstance(name, str) or name in seen:
                return False
            if name in train_names:
                return True
            bound = bindings.get(name)
            return is_trained(bound, seen | {name})
        if node.get("type") != "CallExpression":
            return False
        callee = str(_callee_name(node.get("callee")) or "").casefold()
        if callee.endswith(".train"):
            return True
        if callee.endswith(".classify"):
            arguments = node.get("arguments") or []
            return bool(arguments) and is_trained(arguments[-1], seen)
        return False

    evaluation_roots: Any = ast if relevant_nodes is None else list(relevant_nodes)
    for node in _walk(evaluation_roots):
        if node.get("type") != "CallExpression":
            continue
        callee = str(_callee_name(node.get("callee")) or "")
        method = callee.rsplit(".", 1)[-1].casefold() if "." in callee else ""
        if method == "confusionmatrix":
            receiver = node.get("callee", {}).get("object")
            if not is_trained(receiver):
                raise ValueError(
                    "confusionMatrix must be called on a trained classifier with source-backed lineage"
                )
        elif method == "errormatrix":
            receiver = node.get("callee", {}).get("object")
            if isinstance(receiver, dict) and receiver.get("type") == "Identifier":
                bound = bindings.get(receiver.get("name"))
                if (
                    isinstance(bound, dict)
                    and str(_callee_name(bound.get("callee")) or "")
                    .casefold()
                    .endswith(".classify")
                    and not is_trained((bound.get("arguments") or [None])[-1])
                ):
                    raise ValueError(
                        "errorMatrix must consume a classification result backed by a trained classifier"
                    )


def _fact_id(prefix: str, index: int) -> str:
    return f"{prefix}-{index:04d}"


def _static_arguments(
    node: dict[str, Any], bindings: dict[str, dict[str, Any]]
) -> tuple[str, list[Any]]:
    arguments = node.get("arguments") or []
    values: list[tuple[bool, Any]] = []
    has_partial = False
    for argument in arguments:
        is_static, value = _static_value(argument, bindings)
        if not is_static and isinstance(argument, dict) and argument.get("type") == "ObjectExpression":
            proven_fields: dict[str, Any] = {}
            for prop in argument.get("properties") or []:
                name = _property_name(prop)
                field_status, field_value = _static_value(
                    prop.get("value") if isinstance(prop, dict) else None,
                    bindings,
                )
                if name is not None and field_status:
                    proven_fields[name] = field_value
            if proven_fields:
                value = proven_fields
                has_partial = True
        values.append((is_static, value))
    static_count = sum(status for status, _ in values)
    status = (
        "all"
        if static_count == len(values)
        else "partial"
        if static_count or has_partial
        else "none"
    )
    return status, [value if is_static or value is not None else None for is_static, value in values]


def _resolved_binding_node(
    node: Any,
    bindings: dict[str, dict[str, Any]],
    seen: frozenset[str] = frozenset(),
) -> dict[str, Any] | None:
    if not isinstance(node, dict):
        return None
    if node.get("type") != "Identifier":
        return node
    name = node.get("name")
    if not isinstance(name, str) or name in seen:
        return None
    bound = bindings.get(name)
    if bound is None:
        return None
    return _resolved_binding_node(bound, bindings, seen | {name})


def _dynamic_argument_kind(
    node: Any, bindings: dict[str, dict[str, Any]]
) -> str | None:
    resolved = _resolved_binding_node(node, bindings)
    if not isinstance(resolved, dict) or resolved.get("type") != "CallExpression":
        return None
    if str(_callee_name(resolved.get("callee")) or "") != "ee.Date":
        return None
    arguments = resolved.get("arguments") or []
    if len(arguments) != 1:
        return None
    date_now = arguments[0]
    if not isinstance(date_now, dict) or date_now.get("type") != "CallExpression":
        return None
    if str(_callee_name(date_now.get("callee")) or "") != "Date.now":
        return None
    return "runtime_current_date" if not (date_now.get("arguments") or []) else None


def _dynamic_argument_kinds(
    node: dict[str, Any], bindings: dict[str, dict[str, Any]]
) -> list[str | None]:
    kinds: list[str | None] = []
    for argument in node.get("arguments") or []:
        is_static, _ = _static_value(argument, bindings)
        kinds.append(None if is_static else _dynamic_argument_kind(argument, bindings) or "unresolved_dynamic")
    return kinds


def _mapped_decisions(decisions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        decision
        for decision in decisions
        if decision.get("call_status") in {None, "mapped"}
        and decision.get("canonical_operator") is not None
        and decision.get("l3_code") is not None
    ]


def _validate_authority(typed: dict[str, Any], fidelity: dict[str, Any]) -> None:
    identity_fields = ("source_sha256", "source_path", "workflow_id")
    if any(typed.get(field) != fidelity.get(field) for field in identity_fields):
        raise ValueError("workflow identity mismatch")
    if typed.get("mapping_status") != "mapping_complete" or typed.get("fail_closed_reasons"):
        raise ValueError("typed workflow is not mapping-complete")
    if (
        fidelity.get("fidelity_status") != "passed"
        or fidelity.get("facts_supported") is not True
        or fidelity.get("fail_closed_reasons")
    ):
        raise ValueError("fidelity workflow is not source-backed and passed")
    decisions = typed.get("call_decisions") or []
    mapped_decisions = _mapped_decisions(decisions)
    operators = typed.get("canonical_operator_sequence") or []
    l3 = typed.get("l3_sequence") or []
    if (
        not decisions
        or not mapped_decisions
        or len(mapped_decisions) != len(operators)
        or len(operators) != len(l3)
    ):
        raise ValueError("frozen chain length mismatch")
    ordinals = [decision.get("ordinal") for decision in decisions]
    raw = [decision.get("raw_callee") for decision in decisions]
    if ordinals != fidelity.get("normalized_core_call_ordinals"):
        raise ValueError("frozen ordinal mismatch")
    if raw != fidelity.get("normalized_core_chain"):
        raise ValueError("frozen raw chain mismatch")
    if [decision.get("canonical_operator") for decision in mapped_decisions] != operators:
        raise ValueError("frozen canonical chain mismatch")
    if [decision.get("l3_code") for decision in mapped_decisions] != l3:
        raise ValueError("frozen L3 chain mismatch")


def _dataset_facts(
    closure_nodes: list[tuple[str, dict[str, Any]]],
    bindings: dict[str, dict[str, Any]],
    generated_image_locations: frozenset[tuple[int, int, int, int]] = frozenset(),
) -> list[dict[str, Any]]:
    values: dict[tuple[str, str, tuple[int, int, int, int] | None], dict[str, Any]] = {}
    for definition_id, definition_node in closure_nodes:
        for node in _walk(definition_node):
            if node.get("type") != "CallExpression":
                continue
            constructor = _callee_name(node.get("callee"))
            if constructor in _GENERATED_IMAGE_CONSTRUCTORS:
                location = _location(node)
                if _location_key(location) not in generated_image_locations:
                    continue
                key = (constructor, "generated", _location_key(location))
                values[key] = {
                    "fact_type": "generated_image_source",
                    "constructor": constructor,
                    "value": "pixel longitude/latitude bands",
                    "definition_id": definition_id,
                    "source_location": location,
                    "text_use": "allowed_generated_image",
                }
                continue
            if constructor not in _DATASET_CONSTRUCTORS:
                continue
            arguments = node.get("arguments") or []
            status, value = _static_value(arguments[0], bindings) if arguments else (False, None)
            string_resource = isinstance(value, str) and bool(value)
            image_literal = (
                constructor == "ee.Image"
                and (
                    isinstance(value, bool)
                    or (
                        isinstance(value, (int, float))
                        and not isinstance(value, bool)
                        and math.isfinite(value)
                    )
                )
            )
            if not status or not (string_resource or image_literal):
                continue
            if string_resource:
                _validate_public_dataset_id(value)
            location = _location(node)
            value_key = json.dumps(value, ensure_ascii=False, sort_keys=True)
            key = (constructor, value_key, _location_key(location))
            values[key] = {
                "fact_type": "dataset",
                "constructor": constructor,
                "value": value,
                "definition_id": definition_id,
                "source_location": location,
                "text_use": (
                    "allowed_literal"
                    if image_literal
                    else "omitted_private_asset"
                    if _is_private_asset(value)
                    else "allowed"
                ),
            }
    facts = [
        values[key]
        for key in sorted(values, key=lambda item: (item[1], item[0], item[2] or (0, 0, 0, 0)))
    ]
    for index, fact in enumerate(facts, start=1):
        fact["fact_id"] = _fact_id("dataset", index)
    return facts


def _pixel_lon_lat_source_location(
    node: Any,
    bindings: dict[str, dict[str, Any]],
    ambiguous_names: frozenset[str] = frozenset(),
    seen: frozenset[str] = frozenset(),
) -> dict[str, int] | None:
    if not isinstance(node, dict):
        return None
    if node.get("type") == "Identifier":
        name = node.get("name")
        if (
            not isinstance(name, str)
            or name in ambiguous_names
            or name in seen
            or name not in bindings
        ):
            return None
        return _pixel_lon_lat_source_location(
            bindings[name], bindings, ambiguous_names, seen | {name}
        )
    if node.get("type") != "CallExpression":
        return None
    if _callee_name(node.get("callee")) == "ee.Image.pixelLonLat":
        return _location(node)
    callee = node.get("callee")
    receiver = callee.get("object") if isinstance(callee, dict) else None
    return _pixel_lon_lat_source_location(
        receiver, bindings, ambiguous_names, seen
    )


def _lexically_ambiguous_names(ast: dict[str, Any]) -> frozenset[str]:
    scopes: list[set[str]] = [set()]

    def visit(node: Any, scope_index: int) -> None:
        if not isinstance(node, dict):
            if isinstance(node, list):
                for value in node:
                    visit(value, scope_index)
            return
        node_type = node.get("type")
        if node_type in {"FunctionDeclaration", "FunctionExpression", "ArrowFunctionExpression"}:
            if node_type == "FunctionDeclaration":
                identifier = node.get("id")
                name = identifier.get("name") if isinstance(identifier, dict) else None
                if isinstance(name, str):
                    scopes[scope_index].add(name)
            nested_scope = len(scopes)
            scopes.append(set())
            for parameter in node.get("params") or []:
                if isinstance(parameter, dict) and parameter.get("type") == "Identifier":
                    name = parameter.get("name")
                    if isinstance(name, str):
                        scopes[nested_scope].add(name)
            visit(node.get("body"), nested_scope)
            return
        if node_type == "VariableDeclarator":
            identifier = node.get("id")
            name = identifier.get("name") if isinstance(identifier, dict) else None
            if isinstance(name, str):
                scopes[scope_index].add(name)
        for key, value in node.items():
            if key in {"id", "params", "loc", "range"}:
                continue
            visit(value, scope_index)

    visit(ast, 0)
    owners: dict[str, int] = {}
    ambiguous: set[str] = set()
    for scope_index, names in enumerate(scopes):
        for name in names:
            previous = owners.setdefault(name, scope_index)
            if previous != scope_index:
                ambiguous.add(name)
    return frozenset(ambiguous)


def _retained_generated_image_locations(
    typed: dict[str, Any],
    calls: dict[tuple[int, int, int, int], dict[str, Any]],
    bindings: dict[str, dict[str, Any]],
    ambiguous_names: frozenset[str],
) -> frozenset[tuple[int, int, int, int]]:
    locations: set[tuple[int, int, int, int]] = set()
    for decision in _mapped_decisions(typed["call_decisions"]):
        key = _location_key(decision.get("source_location"))
        node = calls.get(key) if key is not None else None
        if node is None:
            continue
        callee = node.get("callee")
        candidates = [callee.get("object") if isinstance(callee, dict) else None]
        candidates.extend(node.get("arguments") or [])
        for candidate in candidates:
            location = _pixel_lon_lat_source_location(
                candidate, bindings, ambiguous_names
            )
            location_key = _location_key(location)
            if location_key is not None:
                locations.add(location_key)
    return frozenset(locations)


def _transformation_facts(
    typed: dict[str, Any],
    calls: dict[tuple[int, int, int, int], dict[str, Any]],
    bindings: dict[str, dict[str, Any]],
    dataset_facts: list[dict[str, Any]],
    ambiguous_names: frozenset[str],
) -> list[dict[str, Any]]:
    facts: list[dict[str, Any]] = []
    pixel_source_fact_ids = {
        _location_key(fact.get("source_location")): fact["fact_id"]
        for fact in dataset_facts
        if fact.get("constructor") == "ee.Image.pixelLonLat"
        and _location_key(fact.get("source_location")) is not None
    }
    mapped_decisions = _mapped_decisions(typed["call_decisions"])
    for index, decision in enumerate(mapped_decisions, start=1):
        key = _location_key(decision.get("source_location"))
        node = calls.get(key) if key is not None else None
        if node is None:
            raise ValueError(f"mapped call span missing from AST: ordinal {decision.get('ordinal')}")
        static_status, arguments = _static_arguments(
            _semantic_argument_node(
                decision,
                node,
                bindings=bindings,
                ambiguous_names=ambiguous_names,
            ),
            bindings,
        )
        fact = {
            "fact_id": _fact_id("transform", index),
            "fact_type": "transformation",
            "ordinal": decision["ordinal"],
            "raw_callee": decision["raw_callee"],
            "canonical_operator": decision["canonical_operator"],
            "l3_code": decision["l3_code"],
            "receiver_type": decision.get("receiver_type"),
            "source_location": decision["source_location"],
            "static_status": static_status,
            "static_arguments": arguments,
            "text_use": "allowed_operator_and_static_arguments",
        }
        if str(decision["canonical_operator"]).casefold() == "ee.image.select":
            callee = node.get("callee")
            receiver = callee.get("object") if isinstance(callee, dict) else None
            origin_location = _pixel_lon_lat_source_location(
                receiver, bindings, ambiguous_names
            )
            source_fact_id = pixel_source_fact_ids.get(_location_key(origin_location))
            if source_fact_id is not None:
                fact["receiver_source_fact_id"] = source_fact_id
                fact["receiver_source_constructor"] = "ee.Image.pixelLonLat"
        facts.append(fact)
    return facts


def _temporal_facts(
    transformations: list[dict[str, Any]],
    calls: dict[tuple[int, int, int, int], dict[str, Any]] | None = None,
    bindings: dict[str, dict[str, Any]] | None = None,
    ambiguous_names: frozenset[str] = frozenset(),
) -> list[dict[str, Any]]:
    facts: list[dict[str, Any]] = []
    temporal_operators = frozenset(
        {
            "ee.imagecollection.filterdate",
            "ee.filter.date",
            "ee.filter.calendarrange",
            "ee.filter.dayofyear",
        }
    )
    for transformation in transformations:
        operator = transformation["canonical_operator"].casefold()
        if operator in temporal_operators:
            static_status = transformation["static_status"]
            key = _location_key(transformation.get("source_location"))
            temporal_node = calls.get(key) if calls is not None and key is not None else None
            if temporal_node is not None:
                temporal_node = _semantic_argument_node(transformation, temporal_node)
            dynamic_kinds = (
                _dynamic_argument_kinds(temporal_node, bindings or {})
                if temporal_node is not None
                else []
            )
            text_use = "allowed" if static_status == "all" else "omitted_dynamic"
            if (
                static_status != "all"
                and dynamic_kinds
                and "runtime_current_date" in dynamic_kinds
                and "unresolved_dynamic" not in dynamic_kinds
            ):
                text_use = "allowed_with_runtime_current_date"
            facts.append(
                {
                    "fact_id": _fact_id("temporal", len(facts) + 1),
                    "fact_type": "temporal",
                    "operator_fact_id": transformation["fact_id"],
                    "canonical_operator": transformation["canonical_operator"],
                    "ordinal": transformation["ordinal"],
                    "arguments": transformation["static_arguments"],
                    "dynamic_argument_kinds": dynamic_kinds,
                    "static_status": static_status,
                    "source_location": transformation["source_location"],
                    "text_use": text_use,
                }
            )
            continue
        if operator not in {"ee.imagecollection.filter", "ee.featurecollection.filter"}:
            continue
        key = _location_key(transformation.get("source_location"))
        filter_node = calls.get(key) if calls is not None and key is not None else None
        predicate = _filter_predicate_node(
            filter_node,
            bindings or {},
            ambiguous_names,
        )
        if (
            not isinstance(predicate, dict)
            or predicate.get("type") != "CallExpression"
            or str(_callee_name(predicate.get("callee")) or "").casefold()
            != "ee.filter.calendarrange"
        ):
            continue
        static_status, static_arguments = _static_arguments(predicate, bindings or {})
        facts.append(
            {
                "fact_id": _fact_id("temporal", len(facts) + 1),
                "fact_type": "temporal",
                "operator_fact_id": transformation["fact_id"],
                "canonical_operator": "ee.filter.calendarrange",
                "ordinal": transformation["ordinal"],
                "arguments": static_arguments,
                "static_status": static_status,
                "source_location": _location(predicate),
                "text_use": "allowed" if static_status == "all" else "omitted_dynamic",
            }
        )
    return facts


def _validate_static_temporal_intervals(facts: list[dict[str, Any]]) -> None:
    absolute_interval_operators = frozenset(
        {"ee.imagecollection.filterdate", "ee.filter.date"}
    )
    for fact in facts:
        operator = str(fact.get("canonical_operator") or "").casefold()
        arguments = fact.get("arguments") or []
        if (
            operator not in absolute_interval_operators
            or fact.get("static_status") != "all"
            or len(arguments) < 2
            or not all(isinstance(value, str) for value in arguments[:2])
            or not all(_ISO_DATE_PATTERN.fullmatch(value) for value in arguments[:2])
        ):
            continue
        try:
            start, end = (date.fromisoformat(value) for value in arguments[:2])
        except ValueError as exc:
            raise ValueError(
                f"invalid_static_filterdate_interval: {arguments[0]} to {arguments[1]}"
            ) from exc
        if start >= end:
            raise ValueError(
                f"invalid_static_filterdate_interval: {arguments[0]} to {arguments[1]}"
            )


def _spatial_argument_nodes(node: dict[str, Any], method: str) -> list[dict[str, Any]]:
    """Return only arguments that carry spatial input for a known method."""

    arguments = [value for value in node.get("arguments") or [] if isinstance(value, dict)]
    method = method.casefold()
    if method == "geometry":
        callee = node.get("callee")
        receiver = callee.get("object") if isinstance(callee, dict) else None
        return [receiver] if isinstance(receiver, dict) else []
    property_names = {
        "reduceregion": frozenset({"geometry"}),
        "reduceregions": frozenset({"collection"}),
        "sample": frozenset({"region"}),
        "sampleregions": frozenset({"collection"}),
    }.get(method)
    if property_names is not None and arguments:
        first = arguments[0]
        if first.get("type") == "ObjectExpression":
            result: list[dict[str, Any]] = []
            for prop in first.get("properties") or []:
                if _property_name(prop) not in property_names:
                    continue
                value = prop.get("value")
                if isinstance(value, dict):
                    result.append(value)
            return result
    if method in {
        "clip",
        "cliptocollection",
        "filterbounds",
        "intersection",
        "intersects",
        "paint",
        "reducebounds",
        "reduceregion",
        "reduceregions",
        "sample",
        "sampleregions",
    }:
        return arguments[:1]
    return []


def _spatial_facts(
    typed: dict[str, Any],
    fidelity: dict[str, Any],
    calls: dict[tuple[int, int, int, int], dict[str, Any]],
    bindings: dict[str, dict[str, Any]],
    export_node: dict[str, Any],
) -> list[dict[str, Any]]:
    facts: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()

    def add(resolution: str, value: str, location: dict[str, int] | None, ordinal: int | None) -> None:
        key = (resolution, value)
        if key in seen:
            return
        seen.add(key)
        facts.append(
            {
                "fact_id": _fact_id("spatial", len(facts) + 1),
                "fact_type": "spatial_input",
                "resolution": resolution,
                "value": value,
                "ordinal": ordinal,
                "source_location": location,
                "text_use": "allowed_source_defined_region",
            }
        )

    for decision in _mapped_decisions(typed["call_decisions"]):
        method = str(decision["canonical_operator"]).rsplit(".", 1)[-1].casefold()
        if method not in _SPATIAL_METHODS:
            continue
        key = _location_key(decision.get("source_location"))
        node = calls.get(key) if key is not None else None
        if node is None:
            continue
        for argument in _spatial_argument_nodes(node, method):
            resource = _constructor_resource(
                argument,
                bindings,
                allowed_constructors=_SPATIAL_RESOURCE_CONSTRUCTORS,
            )
            if resource is not None:
                add("exact_bound_resource", resource[1], _location(argument), decision["ordinal"])
            elif isinstance(argument, dict) and argument.get("type") == "Identifier":
                name = argument.get("name")
                if isinstance(name, str):
                    add(
                        "opaque_expression" if name in bindings else "external_identifier",
                        "source-defined" if name in bindings else name,
                        _location(argument),
                        decision["ordinal"],
                    )
            else:
                add("opaque_expression", "source-defined", _location(argument), decision["ordinal"])
    for value in fidelity.get("external_spatial_inputs") or []:
        add("external_identifier", str(value), None, None)
    region_node = _output_region_node(export_node)
    if region_node is not None:
        resource = _constructor_resource(
            region_node,
            bindings,
            allowed_constructors=_SPATIAL_RESOURCE_CONSTRUCTORS,
        )
        if resource is not None:
            add("exact_bound_resource", resource[1], _location(region_node), None)
        elif isinstance(region_node, dict) and region_node.get("type") == "Identifier":
            name = region_node.get("name")
            if isinstance(name, str):
                add(
                    "opaque_expression" if name in bindings else "external_identifier",
                    "source-defined" if name in bindings else name,
                    _location(region_node),
                    None,
                )
        else:
            status, value = _static_value(region_node, bindings)
            if status:
                add("exact_static_geometry", json.dumps(value, ensure_ascii=False, sort_keys=True), _location(region_node), None)
            else:
                add("opaque_expression", "source-defined", _location(region_node), None)
    return facts


def _property_name(node: Any) -> str | None:
    if not isinstance(node, dict) or node.get("computed"):
        return None
    key = node.get("key")
    if not isinstance(key, dict):
        return None
    value = key.get("name") if key.get("type") == "Identifier" else key.get("value")
    return value if isinstance(value, str) else None


def _export_call(ast: dict[str, Any], sink_line: int) -> dict[str, Any]:
    candidates = [
        node
        for node in _walk(ast)
        if node.get("type") == "CallExpression"
        and (_location(node) or {}).get("start_line") == sink_line
        and str(_callee_name(node.get("callee")) or "").startswith("Export.")
    ]
    if len(candidates) != 1:
        raise ValueError(f"expected one Export sink at line {sink_line}; found {len(candidates)}")
    return candidates[0]


def _output_region_node(node: dict[str, Any]) -> dict[str, Any] | None:
    export_kind = str(_callee_name(node.get("callee")) or "")
    arguments = node.get("arguments") or []
    first = arguments[0] if arguments else None
    if isinstance(first, dict) and first.get("type") == "ObjectExpression":
        for prop in first.get("properties") or []:
            if _property_name(prop) == "region":
                value = prop.get("value")
                return value if isinstance(value, dict) else None
        return None
    if export_kind == "Export.image" and len(arguments) >= 3:
        config = arguments[2]
        if isinstance(config, dict) and config.get("type") == "ObjectExpression":
            for prop in config.get("properties") or []:
                if _property_name(prop) == "region":
                    value = prop.get("value")
                    return value if isinstance(value, dict) else None
        return None
    fields = _POSITIONAL_EXPORT_FIELDS.get(export_kind, ())
    if "region" not in fields:
        return None
    index = fields.index("region")
    value = arguments[index] if index < len(arguments) else None
    return value if isinstance(value, dict) else None


_EE_CONSTRUCTOR_TYPES = {
    "ee.Image": "ee.image",
    "ee.ImageCollection": "ee.imagecollection",
    "ee.Feature": "ee.feature",
    "ee.FeatureCollection": "ee.featurecollection",
    "ee.Filter": "ee.filter",
    "ee.Reducer": "ee.reducer",
}
_IMAGE_COLLECTION_PRESERVING_METHODS = frozenset(
    {"filter", "filterbounds", "filterdate", "filtermetadata", "map", "merge", "select", "sort"}
)
_IMAGE_RETURNING_METHODS = frozenset(
    {
        "first",
        "mean",
        "median",
        "min",
        "max",
        "mosaic",
        "reduce",
        "qualitymosaic",
    }
)
_IMAGE_TO_FEATURE_COLLECTION_METHODS = frozenset(
    {"reduceregions", "sample", "sampleregions", "stratifiedsample"}
)
_REQUIRED_ARGUMENT_ARITY = {
    "ee.filter.bounds": 1,
    "ee.filter.date": 2,
    "ee.filter.eq": 2,
    "ee.filter.lt": 2,
    "ee.filter.listcontains": 2,
    "ee.imagecollection.filterbounds": 1,
    "ee.imagecollection.filterdate": 2,
    "ee.imagecollection.filtermetadata": 3,
}


def _infer_ee_type(
    node: Any,
    bindings: dict[str, dict[str, Any]],
    seen: frozenset[str] = frozenset(),
) -> str | None:
    """Infer only types needed for output contracts; unknown stays unknown."""

    if not isinstance(node, dict):
        return None
    node_type = node.get("type")
    if node_type == "Identifier":
        name = node.get("name")
        if not isinstance(name, str) or name in seen or name not in bindings:
            return None
        return _infer_ee_type(bindings[name], bindings, seen | {name})
    if node_type != "CallExpression":
        return None
    callee = _callee_name(node.get("callee"))
    direct_type = _EE_CONSTRUCTOR_TYPES.get(str(callee))
    if direct_type is not None:
        return direct_type
    callee_node = node.get("callee")
    receiver = callee_node.get("object") if isinstance(callee_node, dict) else None
    receiver_type = _infer_ee_type(receiver, bindings, seen)
    property_node = callee_node.get("property") if isinstance(callee_node, dict) else None
    method_name = property_node.get("name") if isinstance(property_node, dict) else None
    method = method_name.casefold() if isinstance(method_name, str) else (
        callee.rsplit(".", 1)[-1].casefold() if isinstance(callee, str) and "." in callee else ""
    )
    if not method:
        return None
    if receiver_type == "ee.imagecollection":
        if method in _IMAGE_COLLECTION_PRESERVING_METHODS:
            return "ee.imagecollection"
        if method in _IMAGE_RETURNING_METHODS:
            return "ee.image"
    if (
        receiver_type == "ee.image"
        and method in _IMAGE_TO_FEATURE_COLLECTION_METHODS
    ):
        return "ee.featurecollection"
    if receiver_type == "ee.image":
        return "ee.image"
    if receiver_type == "ee.featurecollection":
        if method in {"filter", "filtermetadata", "merge", "select", "map"}:
            return "ee.featurecollection"
        if method == "geometry":
            return "ee.geometry"
    if receiver_type == "ee.feature" and method == "geometry":
        return "ee.geometry"
    return None


def _output_input_node(node: dict[str, Any]) -> dict[str, Any] | None:
    export_kind = str(_callee_name(node.get("callee")) or "")
    export_family = _export_family(export_kind)
    input_field = _EXPORT_FAMILY_CONTRACTS[export_family][0]
    arguments = node.get("arguments") or []
    first = arguments[0] if arguments else None
    if isinstance(first, dict) and first.get("type") == "ObjectExpression":
        for prop in first.get("properties") or []:
            if input_field is not None and _property_name(prop) == input_field:
                value = prop.get("value")
                return value if isinstance(value, dict) else None
        return None
    if export_kind == "Export.image":
        return first if isinstance(first, dict) else None
    positional = _POSITIONAL_EXPORT_FIELDS.get(export_kind, ())
    if positional and positional[0] == input_field:
        return first if isinstance(first, dict) else None
    return None


def _export_family(export_kind: str) -> str:
    for family in _EXPORT_FAMILY_CONTRACTS:
        if export_kind == family or export_kind.startswith(f"{family}."):
            return family
    raise ValueError(f"unsupported Export family: {export_kind or 'unknown'}")


def _validate_required_call_arguments(
    typed: dict[str, Any],
    calls: dict[tuple[int, int, int, int], dict[str, Any]],
) -> None:
    for decision in _mapped_decisions(typed.get("call_decisions") or []):
        operator = str(decision.get("canonical_operator") or "").casefold()
        required = _REQUIRED_ARGUMENT_ARITY.get(operator)
        if required is None:
            continue
        node = calls.get(_location_key(decision.get("source_location")))
        if node is None:
            continue
        node = _semantic_argument_node(decision, node)
        actual = len([value for value in node.get("arguments") or [] if isinstance(value, dict)])
        if actual < required:
            raise ValueError(
                f"required argument missing for {operator}: expected {required}, got {actual}"
            )


def _filter_predicate_node(
    node: dict[str, Any] | None,
    bindings: dict[str, dict[str, Any]],
    ambiguous_names: frozenset[str] = frozenset(),
) -> dict[str, Any] | None:
    arguments = node.get("arguments") or [] if node is not None else []
    predicate = arguments[0] if arguments else None
    if not isinstance(predicate, dict):
        return None
    if predicate.get("type") != "Identifier":
        return predicate
    resolved = predicate
    seen: set[str] = set()
    ambiguous_binding = False
    while resolved.get("type") == "Identifier":
        name = resolved.get("name")
        if not isinstance(name, str) or name in seen:
            return predicate
        seen.add(name)
        ambiguous_binding = ambiguous_binding or name in ambiguous_names
        bound = bindings.get(name)
        if not isinstance(bound, dict):
            return predicate
        resolved = bound
    callee = (
        str(_callee_name(resolved.get("callee")) or "").casefold()
        if resolved.get("type") == "CallExpression"
        else ""
    )
    if ambiguous_binding and callee in {
        "ee.filter.calendarrange",
        "ee.filter.date",
        "ee.filter.dayofyear",
    }:
        raise ValueError(
            "unresolved_temporal_predicate_binding: "
            f"ambiguous identifier chain {sorted(seen)}"
        )
    return resolved


def _semantic_argument_node(
    decision: dict[str, Any],
    node: dict[str, Any],
    bindings: dict[str, dict[str, Any]] | None = None,
    ambiguous_names: frozenset[str] = frozenset(),
) -> dict[str, Any]:
    canonical_operator = str(decision.get("canonical_operator") or "").casefold()
    if str(decision.get("raw_callee") or "").casefold().endswith(".filter"):
        predicate = _filter_predicate_node(
            node,
            bindings or {},
            ambiguous_names,
        )
        predicate_operator = (
            str(_callee_name(predicate.get("callee")) or "").casefold()
            if isinstance(predicate, dict) and predicate.get("type") == "CallExpression"
            else ""
        )
        if (
            canonical_operator == "ee.imagecollection.filterdate"
            and predicate_operator == "ee.filter.date"
        ):
            return predicate
        if (
            canonical_operator
            in {"ee.imagecollection.filter", "ee.featurecollection.filter"}
            and predicate_operator == "ee.filter.calendarrange"
        ):
            return predicate
    return node


def _chain_output_type(typed: dict[str, Any]) -> str | None:
    """Use the frozen output-relevant terminal operator as a conservative fallback."""

    sequence = typed.get("canonical_operator_sequence") or []
    feature_collection_seen = False
    for raw_operator in reversed(sequence):
        operator = str(raw_operator).casefold()
        if operator.startswith("ee.image."):
            method = operator.rsplit(".", 1)[-1]
            if method in _IMAGE_TO_FEATURE_COLLECTION_METHODS:
                return "ee.featurecollection"
            return "ee.image"
        if operator.startswith("ee.terrain."):
            return "ee.image"
        if operator.startswith("ee.imagecollection."):
            method = operator.rsplit(".", 1)[-1]
            if method in _IMAGE_RETURNING_METHODS:
                return "ee.image"
            if method in _IMAGE_COLLECTION_PRESERVING_METHODS:
                return "ee.imagecollection"
        if operator.startswith("ee.featurecollection."):
            method = operator.rsplit(".", 1)[-1]
            if method != "geometry":
                feature_collection_seen = True
    if feature_collection_seen:
        return "ee.featurecollection"
    return None


def _output_fact(node: dict[str, Any], bindings: dict[str, dict[str, Any]]) -> dict[str, Any]:
    export_kind = str(_callee_name(node.get("callee")))
    arguments = node.get("arguments") or []
    fields: dict[str, Any] = {}
    dynamic_fields: list[str] = []
    signature = "named_object"
    first = arguments[0] if arguments else None
    if isinstance(first, dict) and first.get("type") == "ObjectExpression":
        for prop in first.get("properties") or []:
            name = _property_name(prop)
            if name is None:
                continue
            status, value = _static_value(prop.get("value"), bindings)
            if status and name in _OUTPUT_FIELDS:
                fields[name] = value
            elif name in _OUTPUT_FIELDS:
                dynamic_fields.append(name)
    else:
        signature = "legacy_positional"
        positional_names = _POSITIONAL_EXPORT_FIELDS.get(export_kind, ())
        for name, argument in zip(positional_names, arguments):
            status, value = _static_value(argument, bindings)
            if status and name in _OUTPUT_FIELDS:
                fields[name] = value
            elif name in _OUTPUT_FIELDS:
                dynamic_fields.append(name)
        if export_kind == "Export.image" and len(arguments) >= 3:
            config = arguments[2]
            if isinstance(config, dict) and config.get("type") == "ObjectExpression":
                for prop in config.get("properties") or []:
                    name = _property_name(prop)
                    if name not in _OUTPUT_FIELDS:
                        continue
                    status, value = _static_value(prop.get("value"), bindings)
                    if status:
                        fields[name] = value
                    else:
                        dynamic_fields.append(name)
    input_node = _output_input_node(node)
    input_type = _infer_ee_type(input_node, bindings)
    return {
        "fact_id": _fact_id("output", 1),
        "fact_type": "output",
        "export_kind": export_kind,
        "signature": signature,
        "static_fields": fields,
        "dynamic_fields": sorted(dynamic_fields),
        "input_type": {
            "resolution": "exact" if input_type is not None else "unknown",
            "value": input_type,
            "source_location": _location(input_node),
        },
        "source_location": _location(node),
        "text_use": "allowed_output_contract",
    }


def build_workflow_fact_bundle(
    typed: dict[str, Any], fidelity: dict[str, Any], ast: dict[str, Any]
) -> dict[str, Any]:
    """Build one fail-closed workflow fact bundle from frozen authority inputs."""

    _validate_authority(typed, fidelity)
    closure_nodes, bindings = _closure_bindings(ast, fidelity.get("definition_ids") or [])
    calls = _call_index(ast)
    _validate_classifier_evaluation_lineage(
        ast,
        relevant_nodes=[node for _, node in closure_nodes],
    )
    _validate_required_call_arguments(typed, calls)
    ambiguous_names = _lexically_ambiguous_names(ast)
    generated_image_locations = _retained_generated_image_locations(
        typed, calls, bindings, ambiguous_names
    )
    datasets = _dataset_facts(
        closure_nodes, bindings, generated_image_locations
    )
    transformations = _transformation_facts(
        typed, calls, bindings, datasets, ambiguous_names
    )
    temporals = _temporal_facts(
        transformations,
        calls=calls,
        bindings=bindings,
        ambiguous_names=ambiguous_names,
    )
    _validate_static_temporal_intervals(temporals)
    export_node = _export_call(ast, int(fidelity["sink_line"]))
    spatials = _spatial_facts(typed, fidelity, calls, bindings, export_node)
    output = _output_fact(export_node, bindings)
    export_kind = str(output.get("export_kind") or "")
    if export_kind == "Export.image":
        raise ValueError("unsupported_legacy_callable_export: Export.image")
    export_family = _export_family(export_kind)
    if export_family in {"Export.image", "Export.map"}:
        input_type = (output.get("input_type") or {}).get("value") or _chain_output_type(typed)
        output["input_type"]["value"] = input_type
        output["input_type"]["resolution"] = "exact" if input_type is not None else "unknown"
        if input_type != "ee.image":
            raise ValueError(
                f"{export_kind} input must be provably ee.image, got {input_type or 'unknown'}"
            )
        if export_family == "Export.image":
            region_node = _output_region_node(export_node)
            region_type = _infer_ee_type(region_node, bindings)
            if region_type == "ee.image":
                raise ValueError(
                    f"{export_kind} region must be geometry-like, got {region_type}"
                )
    elif export_family == "Export.table":
        input_type = (output.get("input_type") or {}).get("value") or _chain_output_type(typed)
        output["input_type"]["value"] = input_type
        output["input_type"]["resolution"] = (
            "exact" if input_type is not None else "unknown"
        )
        if input_type != "ee.featurecollection":
            raise ValueError(
                f"{export_kind} input must be provably ee.featurecollection, "
                f"got {input_type or 'unknown'}"
            )
    omissions: set[str] = set()
    if not temporals:
        omissions.add("no_source_backed_temporal_operation")
    elif any(fact["static_status"] != "all" for fact in temporals):
        omissions.add("dynamic_temporal_argument")
    if not spatials:
        omissions.add("no_source_backed_spatial_input")
    elif any(fact["resolution"] == "opaque_expression" for fact in spatials):
        omissions.add("opaque_spatial_expression")
    if any(fact["static_status"] != "all" for fact in transformations):
        omissions.add("dynamic_transformation_arguments")
    if any(field != "region" for field in output["dynamic_fields"]):
        omissions.add("dynamic_output_fields")
    return {
        "schema": FACT_SCHEMA,
        "workflow_key": [typed["source_sha256"], typed["workflow_id"]],
        "source_sha256": typed["source_sha256"],
        "source_path": typed["source_path"],
        "workflow_id": typed["workflow_id"],
        "calibration_stratum": typed.get("calibration_stratum"),
        "exact_dag_fingerprint": fidelity.get("exact_dag_fingerprint"),
        "definition_ids": list(fidelity.get("definition_ids") or []),
        "dependency_edges": list(fidelity.get("dependency_edges") or []),
        "dataset_facts": datasets,
        "temporal_facts": temporals,
        "spatial_input_facts": spatials,
        "transformation_facts": transformations,
        "output_facts": [output],
        "known_omissions": sorted(omissions),
        "operator_sequence": list(typed["canonical_operator_sequence"]),
        "l3_sequence": list(typed["l3_sequence"]),
        "fact_status": "source_backed_complete",
        "training_admission": "not_granted_task_text_and_final_dedup_pending",
        "training_rows_emitted": 0,
    }


def _operator_label(operator: str) -> str:
    method = operator.rsplit(".", 1)[-1]
    return re.sub(r"[_-]+", " ", method).strip()


def _is_private_asset(value: str) -> bool:
    normalized = value.casefold()
    if normalized.startswith(_PUBLIC_PROJECT_ASSET_PREFIXES):
        return False
    return normalized.startswith(("users/", "projects/"))


def _temporal_clause(fact: dict[str, Any]) -> str:
    operator = str(fact.get("canonical_operator") or "").casefold()
    arguments = fact.get("arguments") or []
    label = {
        "ee.imagecollection.filterdate": "filterDate",
        "ee.filter.date": "date",
        "ee.filter.calendarrange": "calendarRange",
        "ee.filter.dayofyear": "dayOfYear",
    }.get(operator, "temporal")
    if len(arguments) >= 2:
        dynamic_kinds = fact.get("dynamic_argument_kinds") or []

        def render_argument(index: int) -> str:
            if index < len(dynamic_kinds) and dynamic_kinds[index] == "runtime_current_date":
                return "runtime current date"
            return str(arguments[index])

        start, end = render_argument(0), render_argument(1)
        closing = ")" if operator in {"ee.imagecollection.filterdate", "ee.filter.date"} else "]"
        suffix = (
            f" for {arguments[2]}"
            if operator == "ee.filter.calendarrange" and len(arguments) >= 3
            else ""
        )
        return f"Apply the {label} interval [{start}, {end}{closing}{suffix}."
    rendered = json.dumps(arguments, ensure_ascii=False)
    return f"Apply the source-defined {label} constraint {rendered}."


def render_chain_faithful_task_text(bundle: dict[str, Any]) -> dict[str, Any]:
    """Render conservative task text and retain clause-to-fact traceability."""

    transformations = bundle.get("transformation_facts") or []
    operators = [fact["canonical_operator"] for fact in transformations]
    l3 = [fact["l3_code"] for fact in transformations]
    if operators != bundle.get("operator_sequence") or l3 != bundle.get("l3_sequence"):
        raise ValueError("task text cannot alter the frozen chain")

    clauses: list[dict[str, Any]] = []
    imagery = [
        fact
        for fact in bundle.get("dataset_facts") or []
        if fact.get("constructor") in {"ee.Image", "ee.ImageCollection"}
    ]
    asset_imagery = [fact for fact in imagery if isinstance(fact.get("value"), str)]
    literal_imagery = [fact for fact in imagery if not isinstance(fact.get("value"), str)]
    public = [
        fact for fact in asset_imagery if not _is_private_asset(str(fact["value"]))
    ]
    if asset_imagery and len(public) == len(asset_imagery):
        values = sorted({str(fact["value"]) for fact in public})
        dataset_text = "Use " + ", ".join(values) + " as the source imagery."
        dataset_ids = [fact["fact_id"] for fact in public]
    elif asset_imagery:
        dataset_text = "Use the source imagery defined by the workflow."
        dataset_ids = [fact["fact_id"] for fact in asset_imagery]
    if asset_imagery:
        clauses.append({"text": dataset_text, "used_fact_ids": dataset_ids})
    if literal_imagery:
        values = ", ".join(
            json.dumps(fact["value"], ensure_ascii=False)
            for fact in literal_imagery
        )
        label = "a constant image with value" if len(literal_imagery) == 1 else "constant images with values"
        clauses.append(
            {
                "text": f"Use {label} {values}.",
                "used_fact_ids": [fact["fact_id"] for fact in literal_imagery],
            }
        )

    generated_pixel_coordinates = [
        fact
        for fact in bundle.get("dataset_facts") or []
        if fact.get("constructor") == "ee.Image.pixelLonLat"
    ]
    if generated_pixel_coordinates:
        generated_by_id = {
            fact["fact_id"]: fact for fact in generated_pixel_coordinates
        }
        clauses.append(
            {
                "text": "Create a pixel longitude/latitude image with ee.Image.pixelLonLat().",
                "used_fact_ids": [fact["fact_id"] for fact in generated_pixel_coordinates],
            }
        )
        for transformation in transformations:
            if (
                str(transformation.get("canonical_operator") or "").casefold()
                != "ee.image.select"
                or transformation.get("static_status") != "all"
            ):
                continue
            arguments = transformation.get("static_arguments") or []
            band = arguments[0] if arguments else None
            source_fact_id = transformation.get("receiver_source_fact_id")
            if (
                not isinstance(band, str)
                or band not in {"longitude", "latitude"}
                or source_fact_id not in generated_by_id
            ):
                continue
            clauses.append(
                {
                    "text": (
                        "From the generated pixel longitude/latitude image, "
                        f"select its {band} band."
                    ),
                    "used_fact_ids": [
                        source_fact_id,
                        transformation["fact_id"],
                    ],
                }
            )

    feature_data = [
        fact
        for fact in bundle.get("dataset_facts") or []
        if fact.get("constructor") in {"ee.Feature", "ee.FeatureCollection"}
    ]
    public_features = [
        fact for fact in feature_data if not _is_private_asset(str(fact["value"]))
    ]
    if feature_data and len(public_features) == len(feature_data):
        values = sorted({str(fact["value"]) for fact in public_features})
        feature_text = "Use " + ", ".join(values) + " as the source feature data."
        feature_ids = [fact["fact_id"] for fact in public_features]
    else:
        feature_text = "Use the source feature data defined by the workflow."
        feature_ids = [fact["fact_id"] for fact in feature_data]
    if feature_data:
        clauses.append({"text": feature_text, "used_fact_ids": feature_ids})

    rendered_temporal = [
        fact
        for fact in bundle.get("temporal_facts") or []
        if fact.get("text_use") in {"allowed", "allowed_with_runtime_current_date"}
    ]
    if rendered_temporal:
        clauses.append(
            {
                "text": " ".join(_temporal_clause(fact) for fact in rendered_temporal),
                "used_fact_ids": [fact["fact_id"] for fact in rendered_temporal],
            }
        )

    spatial = bundle.get("spatial_input_facts") or []
    if spatial:
        clauses.append(
            {
                "text": "Use the source-defined spatial input where required by the workflow.",
                "used_fact_ids": [fact["fact_id"] for fact in spatial],
            }
        )

    labels = [_operator_label(operator) for operator in operators]
    clauses.append(
        {
            "text": "Apply the following GEE operations in order: " + "; ".join(labels) + ".",
            "used_fact_ids": [fact["fact_id"] for fact in transformations],
        }
    )

    output = (bundle.get("output_facts") or [])[0]
    export_kind = str(output["export_kind"])
    export_family = _export_family(export_kind)
    output_family = _EXPORT_FAMILY_CONTRACTS[export_family][2]
    clauses.append(
        {
            "text": f"Produce the resulting {output_family} as the workflow output.",
            "used_fact_ids": [output["fact_id"]],
        }
    )
    if export_family == "Export.map":
        output_name = output_family
    else:
        article = "an" if output_family[:1].casefold() in {"a", "e", "i", "o", "u"} else "a"
        output_name = f"{article} {output_family}"
    task_name = f"Create {output_name} with an ordered {len(operators)}-step GEE workflow"
    return {
        "schema": TASK_TEXT_SCHEMA,
        "source_sha256": bundle["source_sha256"],
        "source_path": bundle["source_path"],
        "workflow_id": bundle["workflow_id"],
        "workflow_key": list(bundle["workflow_key"]),
        "calibration_stratum": bundle.get("calibration_stratum"),
        "task_name": task_name,
        "task_description": " ".join(clause["text"] for clause in clauses),
        "clauses": clauses,
        "operator_sequence": operators,
        "l3_sequence": l3,
        "known_omissions": list(bundle.get("known_omissions") or []),
        "risk_flags": (["chain_exceeds_v4_content_limit"] if len(operators) > 98 else []),
        "task_text_status": "generated_source_backed",
        "training_admission": "not_granted_risk_review_and_final_dedup_pending",
        "production_merge": "not_granted",
        "validation_eligible": False,
        "test_eligible": False,
        "training_rows_emitted": 0,
    }


def _normalized_text(value: Any) -> str:
    return " ".join(str(value).split()).casefold()


def deduplicate_task_text_candidates(
    rows: Iterable[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    kept: dict[tuple[str, str, tuple[str, ...]], dict[str, Any]] = {}
    duplicates: list[dict[str, Any]] = []
    ordered = sorted(
        rows,
        key=lambda row: (str(row.get("source_sha256")), str(row.get("workflow_id"))),
    )
    for row in ordered:
        key = (
            _normalized_text(row.get("task_name")),
            _normalized_text(row.get("task_description")),
            tuple(str(value) for value in row.get("l3_sequence") or []),
        )
        canonical = kept.get(key)
        if canonical is None:
            kept[key] = row
            continue
        duplicates.append(
            {
                "schema": "gis_recommend.gee_workflow_task_text_duplicate.v1",
                "canonical_workflow_key": canonical.get("workflow_key"),
                "duplicate_workflow_key": row.get("workflow_key"),
                "dedup_key": "normalized_task_name_description_plus_l3_sequence",
                "training_admission": "not_granted_duplicate",
                "training_rows_emitted": 0,
            }
        )
    return list(kept.values()), duplicates
