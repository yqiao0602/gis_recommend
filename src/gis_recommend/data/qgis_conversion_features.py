"""Source-derived structural features for QGIS workflow conversion."""

from __future__ import annotations

import ast
import hashlib
import json
import warnings
from dataclasses import dataclass
from typing import Any


SIGNATURE_SCHEMA_VERSION = "qgis-conversion-signature-v1"
FEATURE_EXTRACTOR_VERSION = "qgis-conversion-features-v8"

PROVIDER_INPUT_TYPE_CONTRACTS = {
    "gdal:cliprasterbymasklayer": {"INPUT": "raster", "MASK": "vector"},
    "gdal:polygonize": {"INPUT": "raster"},
    "gdal:rastercalculator": {
        "INPUT_A": "raster",
        "INPUT_B": "raster",
        "INPUT_C": "raster",
        "INPUT_D": "raster",
        "INPUT_E": "raster",
        "INPUT_F": "raster",
    },
    "gdal:rasterize": {"INPUT": "vector"},
    "gdal:warpreproject": {"INPUT": "raster"},
    "native:buffer": {"INPUT": "vector"},
    "native:clip": {"INPUT": "vector", "OVERLAY": "vector"},
    "native:createspatialindex": {"INPUT": "vector"},
    "native:difference": {"INPUT": "vector", "OVERLAY": "vector"},
    "native:dissolve": {"INPUT": "vector"},
    "native:extractbyextent": {"INPUT": "vector"},
    "native:fieldcalculator": {"INPUT": "vector"},
    "native:fixgeometries": {"INPUT": "vector"},
    "native:intersection": {"INPUT": "vector", "OVERLAY": "vector"},
    "native:joinattributesbylocation": {"INPUT": "vector", "JOIN": "vector"},
    "native:mergevectorlayers": {"LAYERS": "vector"},
    "native:reprojectlayer": {"INPUT": "vector"},
    "native:retainfields": {"INPUT": "vector"},
    "native:savefeatures": {"INPUT": "vector"},
    "native:saveselectedfeatures": {"INPUT": "vector"},
    "native:symmetricaldifference": {"INPUT": "vector", "OVERLAY": "vector"},
    "qgis:statisticsbycategories": {"INPUT": "vector"},
}

PROVIDER_OUTPUT_TYPE_CONTRACTS = {
    **{
        operator_id: "vector"
        for operator_id in (
            "gdal:polygonize",
            "native:buffer",
            "native:clip",
            "native:difference",
            "native:dissolve",
            "native:extractbyextent",
            "native:fieldcalculator",
            "native:fixgeometries",
            "native:intersection",
            "native:joinattributesbylocation",
            "native:mergevectorlayers",
            "native:reprojectlayer",
            "native:retainfields",
            "native:savefeatures",
            "native:saveselectedfeatures",
            "native:symmetricaldifference",
        )
    },
    "gdal:cliprasterbymasklayer": "raster",
    "gdal:rastercalculator": "raster",
    "gdal:rasterize": "raster",
    "gdal:warpreproject": "raster",
}

RASTER_PATH_SUFFIXES = (".asc", ".img", ".tif", ".tiff", ".vrt")
VECTOR_PATH_SUFFIXES = (".fgb", ".geojson", ".shp")

BENIGN_OUTPUT_CONSUMER_ROLES = {
    "QgsRasterLayer",
    "QgsVectorLayer",
    "addMapLayer",
    "addRasterLayer",
    "addVectorLayer",
    "basename",
    "instance",
    "isinstance",
    "isValid",
    "log_message",
    "print",
    "setName",
}

INPUT_RESOURCE_PARAMETER_NAMES = {
    "INPUT",
    "INPUT_VECTOR",
    "INPUT_RASTER",
    "OVERLAY",
    "OVERLAYS",
    "MASK",
    "JOIN",
    "LAYERS",
    "RASTER",
    "VECTOR",
}


def _name(node: ast.AST) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        base = _name(node.value)
        return f"{base}.{node.attr}" if base else node.attr
    return ""


def _is_processing_call(node: ast.AST) -> bool:
    return isinstance(node, ast.Call) and (
        _name(node.func) == "processing.run"
        or _name(node.func).endswith(".processing.run")
    )


def _operator_id(call: ast.Call) -> str | None:
    if call.args and isinstance(call.args[0], ast.Constant):
        value = str(call.args[0].value).strip().lower()
        return value if ":" in value else None
    return None


def _target_key(node: ast.AST) -> str | None:
    if isinstance(node, ast.Name):
        return f"name:{node.id}"
    if isinstance(node, ast.Attribute):
        value = _target_key(node.value)
        return f"{value}.attr:{node.attr}" if value else None
    if isinstance(node, ast.Subscript):
        value = _target_key(node.value)
        if value and isinstance(node.slice, ast.Constant):
            return f"{value}.key:{node.slice.value}"
    return None


def _reference_keys(node: ast.AST) -> set[str]:
    return {key for child in ast.walk(node) if (key := _target_key(child))}


def _contains_processing_call(node: ast.AST) -> bool:
    return any(_is_processing_call(child) for child in ast.walk(node))


def _references_target(references: set[str], target: str) -> bool:
    return any(ref == target or ref.startswith(target + ".") for ref in references)


def _call_role(call: ast.Call) -> str:
    if isinstance(call.func, ast.Attribute):
        return call.func.attr
    return _name(call.func)


def _parents(tree: ast.AST) -> dict[ast.AST, ast.AST]:
    result: dict[ast.AST, ast.AST] = {}
    for parent in ast.walk(tree):
        for child in ast.iter_child_nodes(parent):
            result[child] = parent
    return result


def _assignment_target(call: ast.Call, parents: dict[ast.AST, ast.AST]) -> str | None:
    current: ast.AST = call
    while current in parents:
        current = parents[current]
        if isinstance(current, ast.Assign):
            return _target_key(current.targets[0]) if current.targets else None
        if isinstance(current, ast.AnnAssign):
            return _target_key(current.target)
        if isinstance(current, (ast.Expr, ast.Return, ast.FunctionDef, ast.AsyncFunctionDef)):
            return None
    return None


def _scope_kind(call: ast.Call, parents: dict[ast.AST, ast.AST]) -> str:
    current: ast.AST = call
    while current in parents:
        current = parents[current]
        if isinstance(current, (ast.FunctionDef, ast.AsyncFunctionDef)):
            return "function"
    return "module"


def _lexical_scope(call: ast.Call, parents: dict[ast.AST, ast.AST]) -> ast.AST:
    current: ast.AST = call
    while current in parents:
        current = parents[current]
        if isinstance(current, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Module)):
            return current
    return current


def _assignment_definitions(
    tree: ast.AST, parents: dict[ast.AST, ast.AST]
) -> list[tuple[ast.AST, int, str, ast.AST]]:
    definitions: list[tuple[ast.AST, int, str, ast.AST]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            targets = node.targets
            value = node.value
        elif isinstance(node, ast.AnnAssign) and node.value is not None:
            targets = [node.target]
            value = node.value
        else:
            continue
        scope = _lexical_scope(node, parents)
        line = int(getattr(node, "lineno", -1))
        for target in targets:
            if key := _target_key(target):
                definitions.append((scope, line, key, value))
    return definitions


def _latest_definition(
    key: str,
    *,
    before_line: int,
    scope: ast.AST,
    definitions: list[tuple[ast.AST, int, str, ast.AST]],
) -> ast.AST | None:
    candidates = [
        (line, value)
        for definition_scope, line, target, value in definitions
        if definition_scope is scope and target == key and line < before_line
    ]
    return max(candidates, key=lambda item: item[0])[1] if candidates else None


def _latest_definition_entry(
    key: str,
    *,
    before_line: int,
    scope: ast.AST,
    definitions: list[tuple[ast.AST, int, str, ast.AST]],
) -> tuple[int, ast.AST] | None:
    candidates = [
        (line, value)
        for definition_scope, line, target, value in definitions
        if definition_scope is scope and target == key and line < before_line
    ]
    return max(candidates, key=lambda item: item[0]) if candidates else None


def _expanded_reference_keys(
    node: ast.AST,
    *,
    call: ast.Call,
    parents: dict[ast.AST, ast.AST],
    definitions: list[tuple[ast.AST, int, str, ast.AST]],
) -> set[str]:
    scope = _lexical_scope(call, parents)
    before_line = int(call.lineno)
    references = set(_reference_keys(node))
    pending = list(references)
    expanded: set[str] = set()
    while pending:
        key = pending.pop()
        if key in expanded:
            continue
        expanded.add(key)
        definition = _latest_definition(
            key,
            before_line=before_line,
            scope=scope,
            definitions=definitions,
        )
        if definition is None or _contains_processing_call(definition):
            continue
        for reference in _reference_keys(definition):
            if reference not in references:
                references.add(reference)
                pending.append(reference)
    return references


def _resolved_parameter_dict(
    call: ast.Call,
    *,
    parents: dict[ast.AST, ast.AST],
    definitions: list[tuple[ast.AST, int, str, ast.AST]],
) -> ast.Dict | None:
    if len(call.args) < 2:
        return None
    current = call.args[1]
    scope = _lexical_scope(call, parents)
    seen: set[str] = set()
    while not isinstance(current, ast.Dict):
        key = _target_key(current)
        if not key or key in seen:
            return None
        seen.add(key)
        definition = _latest_definition(
            key,
            before_line=int(call.lineno),
            scope=scope,
            definitions=definitions,
        )
        if definition is None or _contains_processing_call(definition):
            return None
        current = definition
    return current


def _resolved_parameter_entries(
    call: ast.Call,
    *,
    parents: dict[ast.AST, ast.AST],
    definitions: list[tuple[ast.AST, int, str, ast.AST]],
) -> list[tuple[str, ast.AST]] | None:
    if len(call.args) < 2:
        return None
    current = call.args[1]
    scope = _lexical_scope(call, parents)
    before_line = int(call.lineno)
    tracked: list[tuple[str, int]] = []
    seen: set[str] = set()
    while not isinstance(current, ast.Dict):
        key = _target_key(current)
        if not key or key in seen:
            return None
        seen.add(key)
        definition = _latest_definition_entry(
            key,
            before_line=before_line,
            scope=scope,
            definitions=definitions,
        )
        if definition is None or _contains_processing_call(definition[1]):
            return None
        line, current = definition
        tracked.append((key, line))

    entries = dict(_parameter_entries(current))
    mutations: list[tuple[int, str, ast.AST]] = []
    for key, base_line in tracked:
        prefix = key + ".key:"
        mutations.extend(
            (line, target[len(prefix) :].strip().upper(), value)
            for definition_scope, line, target, value in definitions
            if definition_scope is scope
            and base_line < line < before_line
            and target.startswith(prefix)
        )
    for _, parameter_name, value in sorted(mutations, key=lambda item: item[0]):
        entries[parameter_name] = value
    return list(entries.items())


def _annotation_layer_type(annotation: ast.AST | None) -> tuple[str, str] | None:
    annotation_name = _name(annotation) if annotation is not None else ""
    if annotation_name.endswith("QgsRasterLayer"):
        return "raster", "annotation:QgsRasterLayer"
    if annotation_name.endswith("QgsVectorLayer"):
        return "vector", "annotation:QgsVectorLayer"
    return None


def _scope_argument_layer_type(
    node: ast.AST, scope: ast.AST
) -> tuple[str, str] | None:
    if not isinstance(node, ast.Name) or not isinstance(
        scope, (ast.FunctionDef, ast.AsyncFunctionDef)
    ):
        return None
    arguments = [
        *scope.args.posonlyargs,
        *scope.args.args,
        *scope.args.kwonlyargs,
        *([scope.args.vararg] if scope.args.vararg is not None else []),
        *([scope.args.kwarg] if scope.args.kwarg is not None else []),
    ]
    for argument in arguments:
        if argument.arg == node.id:
            return _annotation_layer_type(argument.annotation)
    return None


def _literal_layer_type(value: str) -> tuple[str, str] | None:
    normalized = value.replace("\\", "/").strip().lower()
    if "|layername=" in normalized:
        return "vector", "provider_uri:layername"
    path = normalized.partition("|")[0].partition("?")[0]
    if path.endswith(RASTER_PATH_SUFFIXES):
        return "raster", f"literal_path:{path.rsplit('.', 1)[-1]}"
    if path.endswith(VECTOR_PATH_SUFFIXES):
        return "vector", f"literal_path:{path.rsplit('.', 1)[-1]}"
    return None


def _infer_layer_type(
    node: ast.AST,
    *,
    call: ast.Call,
    parents: dict[ast.AST, ast.AST],
    definitions: list[tuple[ast.AST, int, str, ast.AST]],
    before_line: int | None = None,
    seen: set[str] | None = None,
) -> tuple[str, str] | None:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return _literal_layer_type(node.value)
    if isinstance(node, (ast.List, ast.Tuple, ast.Set)):
        inferred = [
            _infer_layer_type(
                element,
                call=call,
                parents=parents,
                definitions=definitions,
                before_line=before_line,
                seen=set(seen or set()),
            )
            for element in node.elts
        ]
        known = [item for item in inferred if item is not None]
        known_types = {item[0] for item in known}
        if len(known_types) > 1:
            return "mixed", f"collection:mixed:{','.join(sorted(known_types))}"
        if known and len(known) == len(inferred) and len(known_types) == 1:
            return known[0][0], f"collection:{known[0][1]}"
        return None
    if isinstance(node, ast.Subscript):
        return _infer_layer_type(
            node.value,
            call=call,
            parents=parents,
            definitions=definitions,
            before_line=before_line,
            seen=seen,
        )
    if isinstance(node, ast.Call):
        role = _name(node.func)
        if role.endswith("QgsRasterLayer"):
            return "raster", "constructor:QgsRasterLayer"
        if role.endswith("QgsVectorLayer"):
            return "vector", "constructor:QgsVectorLayer"
        if role.endswith("parameterAsRasterLayer"):
            return "raster", "parameter_accessor:parameterAsRasterLayer"
        if role.endswith("parameterAsVectorLayer"):
            return "vector", "parameter_accessor:parameterAsVectorLayer"
        if role.endswith("parameterAsSource"):
            return "vector", "parameter_accessor:parameterAsSource"
        if _is_processing_call(node):
            operator_id = _operator_id(node)
            output_type = PROVIDER_OUTPUT_TYPE_CONTRACTS.get(operator_id or "")
            if output_type:
                return output_type, f"processing_output:{operator_id}"
        return None

    scope = _lexical_scope(call, parents)
    annotated = _scope_argument_layer_type(node, scope)
    if annotated is not None:
        return annotated
    key = _target_key(node)
    if not key:
        return None
    visited = set(seen or set())
    if key in visited:
        return None
    visited.add(key)
    definition = _latest_definition_entry(
        key,
        before_line=before_line if before_line is not None else int(call.lineno),
        scope=scope,
        definitions=definitions,
    )
    if definition is None:
        return None
    line, value = definition
    return _infer_layer_type(
        value,
        call=call,
        parents=parents,
        definitions=definitions,
        before_line=line,
        seen=visited,
    )


def _provider_input_type_analysis(
    calls: list[ast.Call],
    *,
    parents: dict[ast.AST, ast.AST],
    definitions: list[tuple[ast.AST, int, str, ast.AST]],
) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []
    applicable = False
    for consumer_index, call in enumerate(calls):
        operator_id = _operator_id(call)
        contracts = PROVIDER_INPUT_TYPE_CONTRACTS.get(operator_id or "", {})
        if not contracts:
            continue
        applicable = True
        entries = _resolved_parameter_entries(
            call, parents=parents, definitions=definitions
        )
        for parameter, value in entries or []:
            required_type = contracts.get(parameter)
            if required_type is None:
                continue
            inferred = _infer_layer_type(
                value,
                call=call,
                parents=parents,
                definitions=definitions,
            )
            actual_type, evidence = inferred or ("unknown", "")
            checks.append(
                {
                    "consumer_index": consumer_index,
                    "operator_id": operator_id,
                    "parameter": parameter,
                    "required_type": required_type,
                    "actual_type": actual_type,
                    "evidence": evidence,
                    "status": (
                        "unknown"
                        if inferred is None
                        else "compatible"
                        if actual_type == required_type
                        else "conflict"
                    ),
                }
            )
    conflicts = [
        {key: value for key, value in check.items() if key != "status"}
        for check in checks
        if check["status"] == "conflict"
    ]
    if conflicts:
        status = "conflict"
    elif any(check["status"] == "unknown" for check in checks) or (
        applicable and not checks
    ):
        status = "unknown"
    elif checks:
        status = "compatible"
    else:
        status = "not_applicable"
    return {"checks": checks, "conflicts": conflicts, "status": status}


def _scope_argument_keys(scope: ast.AST) -> set[str]:
    if not isinstance(scope, (ast.FunctionDef, ast.AsyncFunctionDef)):
        return set()
    arguments = scope.args
    nodes = [
        *arguments.posonlyargs,
        *arguments.args,
        *arguments.kwonlyargs,
        *([arguments.vararg] if arguments.vararg is not None else []),
        *([arguments.kwarg] if arguments.kwarg is not None else []),
    ]
    return {f"name:{node.arg}" for node in nodes}


def _unresolved_output_references(
    values: list[ast.AST],
    *,
    call: ast.Call,
    parents: dict[ast.AST, ast.AST],
    definitions: list[tuple[ast.AST, int, str, ast.AST]],
) -> list[str]:
    scope = _lexical_scope(call, parents)
    before_line = int(call.lineno)
    bound = _scope_argument_keys(scope)
    bound.update(
        target
        for definition_scope, line, target, _ in definitions
        if definition_scope is scope and line < before_line
    )
    unresolved: list[str] = []
    for value in values:
        for reference in sorted(_reference_keys(value)):
            if ".key:" not in reference:
                continue
            root, key = reference.rsplit(".key:", 1)
            if key.upper() == "OUTPUT" and root not in bound:
                unresolved.append(reference)
    return unresolved


def _parameter_entries(node: ast.Dict | None) -> list[tuple[str, ast.AST]]:
    if node is None:
        return []
    return [
        (str(key.value).strip().upper(), value)
        for key, value in zip(node.keys, node.values)
        if isinstance(key, ast.Constant)
    ]


def _resource_fingerprints(node: ast.AST) -> set[str]:
    if isinstance(node, (ast.List, ast.Tuple, ast.Set)):
        return {
            fingerprint
            for element in node.elts
            for fingerprint in _resource_fingerprints(element)
        }
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        value = node.value.partition("|")[0].strip()
        if not value or value.upper() == "TEMPORARY_OUTPUT" or value.lower().startswith("memory:"):
            return set()
        return {f"literal:{value.lower()}"}
    if key := _target_key(node):
        return {f"target:{key}"}
    if isinstance(node, (ast.Call, ast.BinOp, ast.JoinedStr)):
        return {f"expression:{ast.dump(node, annotate_fields=True, include_attributes=False)}"}
    return set()


def _output_resource_keys(
    call: ast.Call,
    *,
    parents: dict[ast.AST, ast.AST],
    definitions: list[tuple[ast.AST, int, str, ast.AST]],
) -> set[str]:
    params = _resolved_parameter_entries(call, parents=parents, definitions=definitions)
    return {
        fingerprint
        for key, value in params or []
        if key == "OUTPUT" or key.endswith("_OUTPUT")
        for fingerprint in _resource_fingerprints(value)
    }


def _input_resource_keys(
    call: ast.Call,
    *,
    parents: dict[ast.AST, ast.AST],
    definitions: list[tuple[ast.AST, int, str, ast.AST]],
) -> set[str]:
    params = _resolved_parameter_entries(call, parents=parents, definitions=definitions)
    return {
        fingerprint
        for key, value in params or []
        if key in INPUT_RESOURCE_PARAMETER_NAMES or key.startswith("INPUT_")
        for fingerprint in _resource_fingerprints(value)
    }


def _literal_strings(node: ast.AST) -> list[str]:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return [node.value]
    if isinstance(node, (ast.List, ast.Tuple, ast.Set)):
        return [
            literal
            for element in node.elts
            for literal in _literal_strings(element)
        ]
    if isinstance(node, ast.Dict):
        return [
            literal
            for value in node.values
            for literal in _literal_strings(value)
        ]
    return []


def _is_processing_temporary_path(value: str) -> bool:
    normalized = value.replace("\\", "/").strip().lower()
    return "/processing_" in normalized and "/output." in normalized


def _processing_temporary_input_references(
    calls: list[ast.Call],
    *,
    parents: dict[ast.AST, ast.AST],
    definitions: list[tuple[ast.AST, int, str, ast.AST]],
) -> list[dict[str, Any]]:
    references: list[dict[str, Any]] = []
    for index, call in enumerate(calls):
        entries = _resolved_parameter_entries(
            call, parents=parents, definitions=definitions
        )
        for key, value in entries or []:
            if key not in INPUT_RESOURCE_PARAMETER_NAMES and not key.startswith("INPUT_"):
                continue
            references.extend(
                {
                    "consumer_index": index,
                    "parameter": key,
                    "value": literal,
                }
                for literal in _literal_strings(value)
                if _is_processing_temporary_path(literal)
            )
    return references


def _is_temporary_output(node: ast.AST) -> bool:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value.strip().upper() == "TEMPORARY_OUTPUT"
    target = _target_key(node) or ""
    return target.endswith(".attr:TEMPORARY_OUTPUT")


def _temporary_output_indices(
    calls: list[ast.Call],
    *,
    parents: dict[ast.AST, ast.AST],
    definitions: list[tuple[ast.AST, int, str, ast.AST]],
) -> list[int]:
    result: list[int] = []
    for index, call in enumerate(calls):
        entries = _resolved_parameter_entries(
            call, parents=parents, definitions=definitions
        )
        if any(
            (key == "OUTPUT" or key.endswith("_OUTPUT"))
            and _is_temporary_output(value)
            for key, value in entries or []
        ):
            result.append(index)
    return result


def _workflow_unit_scope(
    literal_calls: list[ast.Call],
    selected_calls: list[ast.Call],
    parents: dict[ast.AST, ast.AST],
) -> str:
    if not selected_calls:
        return "no_candidate_calls"
    selected_scopes = {_lexical_scope(call, parents) for call in selected_calls}
    if len(selected_scopes) != 1:
        return "cross_scope_candidate"
    selected_scope = next(iter(selected_scopes))
    scope_calls = {
        call for call in literal_calls if _lexical_scope(call, parents) is selected_scope
    }
    return (
        "whole_processing_scope"
        if set(selected_calls) == scope_calls
        else "local_subworkflow"
    )


def _control_kinds(call: ast.Call, parents: dict[ast.AST, ast.AST]) -> set[str]:
    result: set[str] = set()
    current: ast.AST = call
    while current in parents:
        current = parents[current]
        if isinstance(current, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Module)):
            break
        if isinstance(current, ast.If):
            result.add("if")
        elif isinstance(current, (ast.For, ast.AsyncFor)):
            result.add("for")
        elif isinstance(current, ast.While):
            result.add("while")
        elif isinstance(current, ast.Try):
            result.add("try")
    return result


@dataclass(frozen=True)
class ConversionFeatures:
    data: dict[str, Any]
    signature_hash: str


def _select_candidate_calls(
    calls: list[ast.Call], call_sites: list[dict[str, Any]] | None
) -> tuple[list[ast.Call], str]:
    if call_sites is None:
        return calls, "all_literal_calls"
    selected: list[ast.Call] = []
    used: set[int] = set()
    for site in call_sites:
        operator_id = str(site.get("operator_id", "")).strip().lower()
        line_start = int(site.get("line_start", 0))
        line_end = int(site.get("line_end", line_start))
        candidates = [
            call
            for call in calls
            if id(call) not in used
            and _operator_id(call) == operator_id
            and call.lineno <= line_end
            and int(call.end_lineno or call.lineno) >= line_start
        ]
        if not candidates:
            return selected, "candidate_alignment_failed"
        chosen = min(candidates, key=lambda call: abs(call.lineno - line_start))
        used.add(id(chosen))
        selected.append(chosen)
    return selected, "candidate_alignment_matched"


def _intermediate_data_transform_calls(
    tree: ast.AST,
    selected_calls: list[ast.Call],
    produced: list[str | None],
) -> list[str]:
    detected: list[str] = []
    seen: set[str] = set()
    selected_call_set = set(selected_calls)
    all_nodes = sorted(
        ast.walk(tree),
        key=lambda node: (
            int(getattr(node, "lineno", -1)),
            int(getattr(node, "col_offset", -1)),
            0 if isinstance(node, (ast.Assign, ast.AnnAssign)) else 1,
        ),
    )
    for index, producer_call in enumerate(selected_calls[:-1]):
        producer_target = produced[index]
        if not producer_target:
            continue
        consumer_call = selected_calls[index + 1]
        interval_start = int(producer_call.end_lineno or producer_call.lineno)
        interval_end = int(consumer_call.lineno)
        tainted = {producer_target}
        for node in all_nodes:
            line = int(getattr(node, "lineno", -1))
            if line <= interval_start or line >= interval_end:
                continue
            if isinstance(node, (ast.Assign, ast.AnnAssign)):
                value = node.value
                if value is None:
                    continue
                targets = node.targets if isinstance(node, ast.Assign) else [node.target]
                target_keys = {key for target in targets if (key := _target_key(target))}
                value_refs = _reference_keys(value)
                if any(_references_target(value_refs, key) for key in tainted):
                    tainted.update(target_keys)
                else:
                    tainted.difference_update(target_keys)
                continue
            if not isinstance(node, ast.Call) or _is_processing_call(node):
                continue
            if any(
                child is not node and child in selected_call_set
                for child in ast.walk(node)
            ):
                continue
            references = _reference_keys(node)
            if not any(_references_target(references, key) for key in tainted):
                continue
            role = _call_role(node)
            if role and role not in seen:
                seen.add(role)
                detected.append(role)
    return detected


def _downstream_data_transform_calls(
    tree: ast.AST,
    selected_calls: list[ast.Call],
    produced: list[str | None],
    output_resources: list[set[str]],
    parents: dict[ast.AST, ast.AST],
) -> list[str]:
    if not selected_calls:
        return []
    final_call = selected_calls[-1]
    scope = _lexical_scope(final_call, parents)
    interval_start = int(final_call.end_lineno or final_call.lineno)
    tainted = {
        *(target for target in produced[-1:] if target),
        *(
            resource[len("target:") :]
            for resource in output_resources[-1]
            if resource.startswith("target:")
        ),
    }
    if not tainted:
        return []
    detected: list[str] = []
    seen: set[str] = set()
    nodes = sorted(
        ast.walk(tree),
        key=lambda node: (
            int(getattr(node, "lineno", -1)),
            int(getattr(node, "col_offset", -1)),
            0 if isinstance(node, (ast.Assign, ast.AnnAssign)) else 1,
        ),
    )

    def record_calls(node: ast.AST) -> None:
        for child in ast.walk(node):
            if not isinstance(child, ast.Call) or _is_processing_call(child):
                continue
            role = _call_role(child)
            if role and role not in BENIGN_OUTPUT_CONSUMER_ROLES and role not in seen:
                seen.add(role)
                detected.append(role)

    for node in nodes:
        line = int(getattr(node, "lineno", -1))
        if line <= interval_start or _lexical_scope(node, parents) is not scope:
            continue
        if isinstance(node, (ast.Assign, ast.AnnAssign)):
            value = node.value
            if value is None:
                continue
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            target_keys = {key for target in targets if (key := _target_key(target))}
            references = _reference_keys(value)
            if any(_references_target(references, key) for key in tainted):
                tainted.update(target_keys)
                record_calls(value)
            else:
                tainted.difference_update(target_keys)
            continue
        if not isinstance(node, ast.Call) or _is_processing_call(node):
            continue
        references = _reference_keys(node)
        if any(_references_target(references, key) for key in tainted):
            record_calls(node)
    return detected


def extract_conversion_features(
    source_text: str, *, call_sites: list[dict[str, Any]] | None = None
) -> ConversionFeatures:
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", SyntaxWarning)
            tree = ast.parse(source_text)
    except SyntaxError:
        data = {
            "signature_schema_version": SIGNATURE_SCHEMA_VERSION,
            "feature_extractor_version": FEATURE_EXTRACTOR_VERSION,
            "parse_status": "syntax_error",
            "operator_ids": [],
            "candidate_alignment_status": "not_parsed",
            "dependency_edges": [],
            "dependency_edge_evidence": [],
            "unresolved_output_references": [],
            "processing_temporary_input_references": [],
            "provider_input_type_checks": [],
            "provider_input_type_conflicts": [],
            "provider_input_type_status": "not_applicable",
            "downstream_data_transform_calls": [],
            "unused_temporary_terminal_indices": [],
            "unbound_output_indices": [],
            "dynamic_operator_count": 0,
            "control_flow_kinds": [],
            "scope_kinds": [],
            "intermediate_data_transform_calls": [],
            "workflow_unit_scope": "unknown",
        }
        encoded = json.dumps(data, sort_keys=True, separators=(",", ":"))
        return ConversionFeatures(data, hashlib.sha256(encoded.encode()).hexdigest())

    parents = _parents(tree)
    calls = sorted(
        (node for node in ast.walk(tree) if _is_processing_call(node)),
        key=lambda node: (node.lineno, node.col_offset),
    )
    all_literal_calls = [call for call in calls if _operator_id(call)]
    selected_calls, alignment_status = _select_candidate_calls(
        all_literal_calls, call_sites
    )
    literal_calls = [(call, _operator_id(call)) for call in selected_calls]
    definitions = _assignment_definitions(tree, parents)
    produced = [_assignment_target(call, parents) for call, _ in literal_calls]
    edges: set[tuple[int, int]] = set()
    edge_kinds: dict[tuple[int, int], set[str]] = {}
    unresolved_output_references: list[dict[str, Any]] = []
    output_resources = [
        _output_resource_keys(call, parents=parents, definitions=definitions)
        for call, _ in literal_calls
    ]
    for consumer_index, (call, _) in enumerate(literal_calls):
        refs: set[str] = set()
        parameter_entries = _resolved_parameter_entries(
            call, parents=parents, definitions=definitions
        )
        parameter_values = (
            [value for _, value in parameter_entries]
            if parameter_entries is not None
            else list(call.args[1:2])
        )
        unresolved_output_references.extend(
            {
                "consumer_index": consumer_index,
                "reference": reference,
            }
            for reference in _unresolved_output_references(
                parameter_values,
                call=call,
                parents=parents,
                definitions=definitions,
            )
        )
        for arg in [*parameter_values, *call.args[2:]]:
            refs.update(
                _expanded_reference_keys(
                    arg,
                    call=call,
                    parents=parents,
                    definitions=definitions,
                )
            )
        for keyword in call.keywords:
            refs.update(
                _expanded_reference_keys(
                    keyword.value,
                    call=call,
                    parents=parents,
                    definitions=definitions,
                )
            )
        matched_producers: set[int] = set()
        for ref in refs:
            candidates = [
                producer_index
                for producer_index, target in enumerate(produced[:consumer_index])
                if target and (ref == target or ref.startswith(target + "."))
            ]
            if candidates:
                matched_producers.add(max(candidates))
        for producer_index in matched_producers:
            edge = (producer_index, consumer_index)
            edges.add(edge)
            edge_kinds.setdefault(edge, set()).add("variable_or_alias")

        input_resources = _input_resource_keys(
            call, parents=parents, definitions=definitions
        )
        for producer_index, producer_resources in enumerate(
            output_resources[:consumer_index]
        ):
            if producer_resources & input_resources:
                edge = (producer_index, consumer_index)
                edges.add(edge)
                edge_kinds.setdefault(edge, set()).add("static_output_path")

    intermediate_calls = _intermediate_data_transform_calls(
        tree, selected_calls, produced
    )
    downstream_calls = _downstream_data_transform_calls(
        tree, selected_calls, produced, output_resources, parents
    )
    producer_indices = {producer for producer, _ in edges}
    temporary_output_indices = _temporary_output_indices(
        selected_calls, parents=parents, definitions=definitions
    )
    unused_temporary_terminal_indices = [
        index
        for index in temporary_output_indices
        if index < len(selected_calls) - 1 and index not in producer_indices
    ]

    provider_input_types = _provider_input_type_analysis(
        selected_calls, parents=parents, definitions=definitions
    )
    data = {
        "signature_schema_version": SIGNATURE_SCHEMA_VERSION,
        "feature_extractor_version": FEATURE_EXTRACTOR_VERSION,
        "parse_status": "parsed",
        "candidate_alignment_status": alignment_status,
        "operator_ids": [operator for _, operator in literal_calls],
        "dependency_edges": [list(edge) for edge in sorted(edges)],
        "dependency_edge_evidence": [
            {
                "producer_index": producer,
                "consumer_index": consumer,
                "kinds": sorted(edge_kinds[(producer, consumer)]),
            }
            for producer, consumer in sorted(edges)
        ],
        "unresolved_output_references": unresolved_output_references,
        "processing_temporary_input_references": _processing_temporary_input_references(
            selected_calls, parents=parents, definitions=definitions
        ),
        "provider_input_type_checks": provider_input_types["checks"],
        "provider_input_type_conflicts": provider_input_types["conflicts"],
        "provider_input_type_status": provider_input_types["status"],
        "downstream_data_transform_calls": downstream_calls,
        "unused_temporary_terminal_indices": unused_temporary_terminal_indices,
        "unbound_output_indices": [i for i, target in enumerate(produced) if target is None],
        "dynamic_operator_count": len(calls) - len(all_literal_calls),
        "control_flow_kinds": sorted(
            {kind for call, _ in literal_calls for kind in _control_kinds(call, parents)}
        ),
        "scope_kinds": sorted({_scope_kind(call, parents) for call, _ in literal_calls}),
        "intermediate_data_transform_calls": intermediate_calls,
        "workflow_unit_scope": _workflow_unit_scope(
            all_literal_calls, selected_calls, parents
        ),
    }
    encoded = json.dumps(data, sort_keys=True, separators=(",", ":"))
    return ConversionFeatures(data, hashlib.sha256(encoded.encode()).hexdigest())
