"""Split cross-scope QGIS Processing candidates into connected local units."""

from __future__ import annotations

import ast
import builtins
import hashlib
import json
import warnings
from collections import defaultdict
from collections.abc import Mapping, Sequence
from typing import Any

from gis_recommend.data.qgis_conversion_features import (
    FEATURE_EXTRACTOR_VERSION,
    _assignment_definitions,
    _assignment_target,
    _input_resource_keys,
    _is_processing_call,
    _lexical_scope,
    _operator_id,
    _output_resource_keys,
    _parents,
    extract_conversion_features,
)


SPLITTER_VERSION = "qgis-local-subworkflow-splitter-v9"

LOW_LEVEL_DATA_TRANSFORM_METHODS = {
    "addFeature",
    "addFeatures",
    "changeAttributeValue",
    "changeGeometry",
    "commitChanges",
    "deleteFeature",
    "deleteFeatures",
    "deleteSelectedFeatures",
    "materialize",
    "setGeometry",
    "startEditing",
    "updateFeature",
}


def literalize_processing_operator_ids(
    source_text: str,
    *,
    call_sites: Sequence[Mapping[str, Any]],
    require_full_coverage: bool = True,
) -> str:
    """Replace verified operator expressions in memory while preserving line numbers."""

    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", SyntaxWarning)
            tree = ast.parse(source_text)
    except SyntaxError as exc:
        raise ValueError("cannot literalize unparseable source") from exc
    calls = sorted(
        (node for node in ast.walk(tree) if _is_processing_call(node) and node.args),
        key=lambda node: (node.lineno, node.col_offset),
    )
    if require_full_coverage and len(calls) != len(call_sites):
        raise ValueError(
            f"processing call coverage mismatch: source={len(calls)} sites={len(call_sites)}"
        )

    aligned_calls: list[ast.Call] = []
    used: set[int] = set()
    for site in call_sites:
        site_start = int(site.get("line_start") or 0)
        site_end = int(site.get("line_end") or site_start)
        candidates = [
            (index, call)
            for index, call in enumerate(calls)
            if index not in used
            and int(call.lineno) <= site_end
            and int(call.end_lineno or call.lineno) >= site_start
        ]
        if len(candidates) != 1:
            raise ValueError(
                f"cannot uniquely align verified call site at {site_start}-{site_end}"
            )
        index, call = candidates[0]
        used.add(index)
        aligned_calls.append(call)

    encoded_lines = source_text.encode("utf-8").splitlines(keepends=True)
    line_offsets: list[int] = []
    offset = 0
    for line in encoded_lines:
        line_offsets.append(offset)
        offset += len(line)
    replacements: list[tuple[int, int, bytes]] = []
    for call, site in zip(aligned_calls, call_sites):
        expression = call.args[0]
        source_start = int(call.lineno)
        source_end = int(call.end_lineno or call.lineno)
        site_start = int(site.get("line_start") or 0)
        site_end = int(site.get("line_end") or site_start)
        if source_start > site_end or source_end < site_start:
            raise ValueError(
                f"cannot align verified call site at {site_start}-{site_end}"
            )
        if expression.lineno != expression.end_lineno:
            raise ValueError("multiline dynamic operator expressions are not supported")
        operator_id = str(site.get("operator_id") or "").strip().lower()
        if ":" not in operator_id:
            raise ValueError(f"invalid verified operator ID: {operator_id!r}")
        start = line_offsets[expression.lineno - 1] + expression.col_offset
        end = line_offsets[expression.end_lineno - 1] + int(expression.end_col_offset)
        replacement = json.dumps(operator_id, ensure_ascii=False).encode("utf-8")
        replacements.append((start, end, replacement))

    encoded = source_text.encode("utf-8")
    for start, end, replacement in reversed(replacements):
        encoded = encoded[:start] + replacement + encoded[end:]
    literalized = encoded.decode("utf-8")
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", SyntaxWarning)
        verified_tree = ast.parse(literalized)
    verified_calls = sorted(
        (
            node
            for node in ast.walk(verified_tree)
            if _is_processing_call(node) and _operator_id(node)
        ),
        key=lambda node: (node.lineno, node.col_offset),
    )
    if require_full_coverage:
        verified_ids = [_operator_id(call) for call in verified_calls]
    else:
        verified_ids = []
        for site in call_sites:
            site_start = int(site.get("line_start") or 0)
            site_end = int(site.get("line_end") or site_start)
            candidates = [
                call
                for call in verified_calls
                if int(call.lineno) <= site_end
                and int(call.end_lineno or call.lineno) >= site_start
            ]
            if len(candidates) != 1:
                raise ValueError(
                    f"cannot verify literalized call site at {site_start}-{site_end}"
                )
            verified_ids.append(_operator_id(candidates[0]))
    if verified_ids != [str(site["operator_id"]).strip().lower() for site in call_sites]:
        raise ValueError("literalized operator chain verification failed")
    return literalized


def _scope_name(scope: ast.AST, parents: Mapping[ast.AST, ast.AST]) -> str:
    names: list[str] = []
    current = scope
    while not isinstance(current, ast.Module):
        if isinstance(current, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            names.append(current.name)
        if current not in parents:
            break
        current = parents[current]
    return ".".join(reversed(names)) or "<module>"


def _connected_components(count: int, edges: Sequence[Sequence[int]]) -> list[list[int]]:
    adjacency = {index: set() for index in range(count)}
    for source, target in edges:
        adjacency[int(source)].add(int(target))
        adjacency[int(target)].add(int(source))
    components: list[list[int]] = []
    remaining = set(range(count))
    while remaining:
        start = min(remaining)
        pending = [start]
        component: set[int] = set()
        while pending:
            current = pending.pop()
            if current in component:
                continue
            component.add(current)
            pending.extend(adjacency[current] - component)
        remaining -= component
        components.append(sorted(component))
    return components


def _unit_id(scope: str, call_sites: Sequence[Mapping[str, Any]], edges: list[list[int]]) -> str:
    payload = {
        "scope": scope,
        "calls": [
            {
                "operator_id": site["operator_id"],
                "line_start": int(site["line_start"]),
                "line_end": int(site.get("line_end") or site["line_start"]),
            }
            for site in call_sites
        ],
        "edges": edges,
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return "local_" + hashlib.sha256(encoded.encode("utf-8")).hexdigest()[:20]


def _local_structure_reasons(features: Mapping[str, Any], operator_count: int) -> list[str]:
    reasons: list[str] = []
    reasons.extend(
        f"control_flow:{kind}"
        for kind in sorted(set(features.get("control_flow_kinds") or []))
    )
    if features.get("unresolved_output_references"):
        reasons.append("unresolved_output_reference")
    if features.get("processing_temporary_input_references"):
        reasons.append("processing_temporary_input_reference")
    if features.get("provider_input_type_conflicts"):
        reasons.append("provider_input_type_conflict")
    if features.get("intermediate_data_transform_calls"):
        reasons.append("intermediate_data_transform")
    if features.get("downstream_data_transform_calls"):
        reasons.append("downstream_data_transform")
    if features.get("unused_temporary_terminal_indices"):
        reasons.append("unused_temporary_terminal")
    consumers = {
        int(target) for _, target in features.get("dependency_edges") or []
    }
    if operator_count > 1 and consumers != set(range(1, operator_count)):
        reasons.append("missing_data_edges")
    evidence_kinds = {
        str(kind)
        for item in features.get("dependency_edge_evidence") or []
        for kind in item.get("kinds") or []
    }
    for kind in sorted(evidence_kinds - {"variable_or_alias", "static_output_path"}):
        reasons.append(f"unsupported_dependency_evidence:{kind}")
    return reasons


def _target_names(target: ast.AST) -> set[str]:
    if isinstance(target, ast.Name):
        return {target.id}
    if isinstance(target, ast.Starred):
        return _target_names(target.value)
    if isinstance(target, (ast.Tuple, ast.List)):
        return {
            name
            for element in target.elts
            for name in _target_names(element)
        }
    return set()


def _function_argument_names(scope: ast.AST) -> set[str]:
    if not isinstance(scope, (ast.FunctionDef, ast.AsyncFunctionDef)):
        return set()
    arguments = scope.args
    names = {
        argument.arg
        for argument in (
            list(arguments.posonlyargs)
            + list(arguments.args)
            + list(arguments.kwonlyargs)
        )
    }
    if arguments.vararg is not None:
        names.add(arguments.vararg.arg)
    if arguments.kwarg is not None:
        names.add(arguments.kwarg.arg)
    return names


def _imported_names(node: ast.Import | ast.ImportFrom) -> set[str]:
    names: set[str] = set()
    for alias in node.names:
        if alias.name == "*":
            continue
        names.add(alias.asname or alias.name.split(".", 1)[0])
    return names


def _name_binding_scope(
    node: ast.AST, parents: Mapping[ast.AST, ast.AST]
) -> ast.AST:
    current = node
    while current in parents:
        current = parents[current]
        if isinstance(
            current,
            (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Lambda, ast.Module),
        ):
            return current
    return current


def _names_bound_before(
    scope: ast.AST,
    *,
    before_line: int,
    parents: Mapping[ast.AST, ast.AST],
) -> set[str]:
    names = _function_argument_names(scope)
    for node in ast.walk(scope):
        if _name_binding_scope(node, parents) is not scope:
            continue
        if isinstance(node, (ast.Global, ast.Nonlocal)):
            names.update(node.names)
            continue
        line = int(getattr(node, "lineno", -1))
        if line < 0 or line >= before_line:
            continue
        if isinstance(node, ast.Assign):
            for target in node.targets:
                names.update(_target_names(target))
        elif isinstance(node, (ast.AnnAssign, ast.AugAssign, ast.NamedExpr)):
            names.update(_target_names(node.target))
        elif isinstance(node, (ast.For, ast.AsyncFor)):
            names.update(_target_names(node.target))
        elif isinstance(node, (ast.With, ast.AsyncWith)):
            for item in node.items:
                if item.optional_vars is not None:
                    names.update(_target_names(item.optional_vars))
        elif isinstance(node, ast.ExceptHandler) and node.name:
            names.add(node.name)
        elif isinstance(node, (ast.Import, ast.ImportFrom)):
            names.update(_imported_names(node))
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            names.add(node.name)
    return names


def _module_scope(
    scope: ast.AST, parents: Mapping[ast.AST, ast.AST]
) -> ast.Module | None:
    current = scope
    while not isinstance(current, ast.Module):
        if current not in parents:
            return None
        current = parents[current]
    return current


def _processing_parameter_expression(call: ast.Call) -> ast.AST | None:
    if len(call.args) >= 2:
        return call.args[1]
    for keyword in call.keywords:
        if keyword.arg in {"parameters", "params"}:
            return keyword.value
    return None


def _safe_parameter_factory_names(
    expression: ast.AST,
    *,
    qgis_processing_utils_bound: bool,
) -> tuple[set[int], list[dict[str, Any]]]:
    if not qgis_processing_utils_bound:
        return set(), []
    safe_names: set[int] = set()
    evidence: list[dict[str, Any]] = []
    for node in ast.walk(expression):
        if not (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "generateTempFilename"
            and isinstance(node.func.value, ast.Name)
            and node.func.value.id == "QgsProcessingUtils"
            and len(node.args) == 1
            and not node.keywords
            and isinstance(node.args[0], ast.Constant)
            and isinstance(node.args[0].value, str)
            and node.args[0].value.strip()
        ):
            continue
        safe_names.add(id(node.func.value))
        evidence.append(
            {
                "factory": "QgsProcessingUtils.generateTempFilename",
                "line": int(node.lineno),
                "literal_suffix": node.args[0].value,
            }
        )
    return safe_names, evidence


def _has_qgis_core_wildcard_import(
    module: ast.Module | None,
    *,
    before_line: int,
    parents: Mapping[ast.AST, ast.AST],
) -> bool:
    if module is None:
        return False
    return any(
        isinstance(node, ast.ImportFrom)
        and node.module == "qgis.core"
        and any(alias.name == "*" for alias in node.names)
        and int(getattr(node, "lineno", before_line)) < before_line
        and _name_binding_scope(node, parents) is module
        for node in ast.walk(module)
    )


def _processing_call_structure_reasons(
    scope: ast.AST,
    *,
    parents: Mapping[ast.AST, ast.AST],
    calls: Sequence[ast.Call],
    parameter_factory_evidence: list[dict[str, Any]] | None = None,
) -> list[str]:
    reasons: list[str] = []
    unresolved_names: set[str] = set()
    module = _module_scope(scope, parents)
    builtin_names = set(dir(builtins))
    for call in calls:
        parameter_expression = _processing_parameter_expression(call)
        if len(call.args) > 2 and not isinstance(call.args[1], ast.Dict):
            reasons.append("legacy_positional_processing_signature")
        if parameter_expression is None:
            continue
        bound_names = _names_bound_before(
            scope,
            before_line=int(call.lineno),
            parents=parents,
        )
        if module is not None and module is not scope:
            bound_names.update(
                _names_bound_before(
                    module,
                    before_line=int(call.lineno),
                    parents=parents,
                )
            )
        safe_factory_names, factory_evidence = _safe_parameter_factory_names(
            parameter_expression,
            qgis_processing_utils_bound=(
                "QgsProcessingUtils" in bound_names
                or _has_qgis_core_wildcard_import(
                    module,
                    before_line=int(call.lineno),
                    parents=parents,
                )
            ),
        )
        if parameter_factory_evidence is not None:
            parameter_factory_evidence.extend(factory_evidence)
        unresolved_names.update(
            node.id
            for node in ast.walk(parameter_expression)
            if isinstance(node, ast.Name)
            and isinstance(node.ctx, ast.Load)
            and id(node) not in safe_factory_names
            and node.id not in bound_names
            and node.id not in builtin_names
        )
    if "legacy_positional_processing_signature" in reasons:
        reasons = ["legacy_positional_processing_signature"]
    reasons.extend(
        f"unresolved_processing_parameter_name:{name}"
        for name in sorted(unresolved_names)
    )
    return reasons


def _if_control_path(
    node: ast.AST,
    scope: ast.AST,
    parents: Mapping[ast.AST, ast.AST],
) -> tuple[tuple[ast.If, str], ...]:
    path: list[tuple[ast.If, str]] = []
    child = node
    while child in parents:
        parent = parents[child]
        if parent is scope:
            break
        if isinstance(parent, ast.If):
            branch = "body" if child in parent.body else "orelse"
            path.append((parent, branch))
        child = parent
    return tuple(reversed(path))


def _condition_syntax_kind(node: ast.AST) -> str:
    if isinstance(node, ast.Name):
        return "name"
    if isinstance(node, ast.Attribute):
        return "attribute"
    if isinstance(node, ast.Subscript):
        return "subscript"
    if isinstance(node, ast.Call):
        return "call"
    if isinstance(node, ast.Compare):
        return "comparison"
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.Not):
        return "negation"
    if isinstance(node, ast.BoolOp):
        if isinstance(node.op, ast.And):
            return "boolean_and"
        if isinstance(node.op, ast.Or):
            return "boolean_or"
    return type(node).__name__.lower()


def _condition_evidence(if_node: ast.If, branch: str) -> dict[str, Any]:
    normalized_expression = ast.unparse(if_node.test)
    normalized_ast = ast.dump(
        if_node.test,
        annotate_fields=True,
        include_attributes=False,
    )
    return {
        "if_line": int(if_node.lineno),
        "branch": branch,
        "condition_expression": normalized_expression,
        "normalized_condition_expression": normalized_expression,
        "normalized_condition_key": hashlib.sha256(
            normalized_ast.encode("utf-8")
        ).hexdigest(),
        "required_condition_value": branch == "body",
        "condition_syntax_kind": _condition_syntax_kind(if_node.test),
        "condition_semantic_status": "syntax_only_not_admitted",
    }


def _control_path_evidence(
    calls: Sequence[ast.Call],
    scope: ast.AST,
    parents: Mapping[ast.AST, ast.AST],
) -> tuple[str, list[dict[str, Any]]]:
    paths = [_if_control_path(call, scope, parents) for call in calls]
    if not any(paths):
        return "unconditional", []
    if len(set(paths)) != 1 or not paths[0]:
        return "mixed", []
    return (
        "same_if_branch",
        [
            _condition_evidence(if_node, branch)
            for if_node, branch in paths[0]
        ],
    )


def _lexical_boundary_reasons(
    scope: ast.AST,
    parents: Mapping[ast.AST, ast.AST],
    call_sites: Sequence[Mapping[str, Any]],
    source_text: str,
) -> tuple[list[str], list[str]]:
    first_end = min(
        int(site.get("line_end") or site["line_start"]) for site in call_sites
    )
    last_start = max(int(site["line_start"]) for site in call_sites)
    last_end = max(
        int(site.get("line_end") or site["line_start"]) for site in call_sites
    )
    reasons: list[str] = []
    if any(
        isinstance(node, (ast.Return, ast.Raise))
        and first_end < int(getattr(node, "lineno", 0)) < last_start
        for node in ast.walk(scope)
    ):
        reasons.append("conditional_early_exit")

    downstream_roles = sorted(
        {
            node.func.attr
            for node in ast.walk(scope)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr in LOW_LEVEL_DATA_TRANSFORM_METHODS
            and int(getattr(node, "lineno", 0)) > last_end
            and _lexical_scope(node, parents) is scope
        }
    )
    reasons.extend(
        f"downstream_low_level_data_transform:{role}" for role in downstream_roles
    )
    reasons.extend(
        _downstream_processing_consumer_reasons(
            scope, parents, call_sites, source_text
        )
    )
    return reasons, downstream_roles


def _resource_matches(produced: set[str], consumed: set[str]) -> bool:
    if produced & consumed:
        return True
    produced_targets = {
        resource[len("target:") :]
        for resource in produced
        if resource.startswith("target:")
    }
    consumed_targets = {
        resource[len("target:") :]
        for resource in consumed
        if resource.startswith("target:")
    }
    return any(
        consumed_target == produced_target
        or consumed_target.startswith(produced_target + ".")
        for produced_target in produced_targets
        for consumed_target in consumed_targets
    )


def _align_component_calls(
    scope: ast.AST,
    call_sites: Sequence[Mapping[str, Any]],
) -> list[ast.Call]:
    literal_calls = sorted(
        (
            node
            for node in ast.walk(scope)
            if _is_processing_call(node) and _operator_id(node)
        ),
        key=lambda node: (node.lineno, node.col_offset),
    )
    aligned: list[ast.Call] = []
    used: set[int] = set()
    for site in call_sites:
        operator_id = str(site.get("operator_id") or "").strip().lower()
        start = int(site.get("line_start") or 0)
        end = int(site.get("line_end") or start)
        candidates = [
            call
            for call in literal_calls
            if id(call) not in used
            and _operator_id(call) == operator_id
            and call.lineno <= end
            and int(call.end_lineno or call.lineno) >= start
        ]
        if not candidates:
            return []
        chosen = min(candidates, key=lambda call: abs(call.lineno - start))
        used.add(id(chosen))
        aligned.append(chosen)
    return aligned


def _produced_resources(
    calls: Sequence[ast.Call],
    *,
    parents: Mapping[ast.AST, ast.AST],
    definitions: Sequence[tuple[ast.AST, int, str, ast.AST]],
) -> set[str]:
    resources: set[str] = set()
    for call in calls:
        resources.update(
            _output_resource_keys(
                call, parents=dict(parents), definitions=list(definitions)
            )
        )
        target = _assignment_target(call, dict(parents))
        if target:
            resources.add(f"target:{target}")
            resources.add(f"target:{target}.key:OUTPUT")
    return resources


def _downstream_processing_consumer_reasons(
    scope: ast.AST,
    parents: Mapping[ast.AST, ast.AST],
    call_sites: Sequence[Mapping[str, Any]],
    source_text: str,
) -> list[str]:
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", SyntaxWarning)
            tree = ast.parse(source_text)
    except SyntaxError:
        return []
    tree_parents = _parents(tree)
    tree_scopes = [
        node
        for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Module))
        and _scope_name(node, tree_parents) == _scope_name(scope, parents)
    ]
    if not tree_scopes:
        return []
    tree_scope = tree_scopes[0]
    component_calls = _align_component_calls(tree_scope, call_sites)
    if not component_calls:
        return []
    component_call_ids = {id(call) for call in component_calls}
    last_end = max(int(call.end_lineno or call.lineno) for call in component_calls)
    definitions = _assignment_definitions(tree_scope, tree_parents)
    produced = _produced_resources(
        component_calls, parents=tree_parents, definitions=definitions
    )
    if not produced:
        return []

    reasons: list[str] = []
    seen: set[str] = set()
    downstream_calls = sorted(
        (
            node
            for node in ast.walk(tree_scope)
            if _is_processing_call(node)
            and _operator_id(node)
            and id(node) not in component_call_ids
            and int(getattr(node, "lineno", 0)) > last_end
        ),
        key=lambda node: (node.lineno, node.col_offset),
    )
    for call in downstream_calls:
        consumed = _input_resource_keys(
            call, parents=tree_parents, definitions=definitions
        )
        if not _resource_matches(produced, consumed):
            continue
        operator_id = _operator_id(call) or "unknown"
        if operator_id not in seen:
            seen.add(operator_id)
            reasons.append(f"downstream_processing_consumer:{operator_id}")
    return reasons


def split_candidate_into_local_units(
    source_text: str, *, call_sites: Sequence[Mapping[str, Any]]
) -> list[dict[str, Any]]:
    """Return source-ordered connected components bounded by lexical scope."""

    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", SyntaxWarning)
            tree = ast.parse(source_text)
    except SyntaxError as exc:
        raise ValueError("cannot split unparseable source") from exc
    parents = _parents(tree)
    literal_calls = sorted(
        (node for node in ast.walk(tree) if _is_processing_call(node) and _operator_id(node)),
        key=lambda node: (node.lineno, node.col_offset),
    )
    aligned: list[tuple[Mapping[str, Any], ast.Call]] = []
    used: set[int] = set()
    for site in call_sites:
        operator_id = str(site.get("operator_id") or "").strip().lower()
        start = int(site.get("line_start") or 0)
        end = int(site.get("line_end") or start)
        candidates = [
            call
            for call in literal_calls
            if id(call) not in used
            and _operator_id(call) == operator_id
            and call.lineno <= end
            and int(call.end_lineno or call.lineno) >= start
        ]
        if not candidates:
            raise ValueError(f"cannot align call site: {operator_id}@{start}-{end}")
        chosen = min(candidates, key=lambda call: abs(call.lineno - start))
        used.add(id(chosen))
        aligned.append((site, chosen))

    grouped: dict[ast.AST, list[Mapping[str, Any]]] = defaultdict(list)
    first_line: dict[ast.AST, int] = {}
    for site, call in aligned:
        scope = _lexical_scope(call, parents)
        grouped[scope].append(site)
        first_line[scope] = min(first_line.get(scope, call.lineno), call.lineno)

    units: list[dict[str, Any]] = []
    for scope in sorted(grouped, key=lambda value: first_line[value]):
        scope_sites = list(grouped[scope])
        all_scope_calls = [
            call for call in literal_calls if _lexical_scope(call, parents) is scope
        ]
        all_scope_sites = [
            {
                "operator_id": _operator_id(call),
                "line_start": int(call.lineno),
                "line_end": int(call.end_lineno or call.lineno),
            }
            for call in all_scope_calls
        ]
        all_scope_features = extract_conversion_features(
            source_text, call_sites=all_scope_sites
        ).data
        features = extract_conversion_features(source_text, call_sites=scope_sites).data
        if features["candidate_alignment_status"] != "candidate_alignment_matched":
            raise ValueError(f"cannot align calls inside lexical scope: {_scope_name(scope, parents)}")
        edges = [list(map(int, edge)) for edge in features["dependency_edges"]]
        for component in _connected_components(len(scope_sites), edges):
            component_sites = [dict(scope_sites[index]) for index in component]
            component_operators = [
                str(scope_sites[index]["operator_id"]).strip().lower()
                for index in component
            ]
            component_features = extract_conversion_features(
                source_text, call_sites=component_sites
            ).data
            if (
                component_features["candidate_alignment_status"]
                != "candidate_alignment_matched"
            ):
                raise ValueError(
                    f"cannot align connected component: {_scope_name(scope, parents)}"
                )
            component_edges = [
                list(map(int, edge))
                for edge in component_features.get("dependency_edges") or []
            ]
            edge_evidence = [
                {
                    "producer_index": int(item["producer_index"]),
                    "consumer_index": int(item["consumer_index"]),
                    "kinds": list(item.get("kinds") or []),
                }
                for item in component_features.get("dependency_edge_evidence") or []
            ]
            selected_all_indices: list[int] = []
            for site in component_sites:
                selected_all_indices.append(
                    next(
                        index
                        for index, candidate in enumerate(all_scope_sites)
                        if candidate["operator_id"]
                        == str(site["operator_id"]).strip().lower()
                        and candidate["line_start"]
                        <= int(site.get("line_end") or site["line_start"])
                        and candidate["line_end"] >= int(site["line_start"])
                    )
                )
            component_index_by_all = {
                all_index: component_index
                for component_index, all_index in enumerate(selected_all_indices)
            }
            all_evidence = {
                (int(item["producer_index"]), int(item["consumer_index"])): list(
                    item.get("kinds") or []
                )
                for item in all_scope_features.get("dependency_edge_evidence") or []
            }
            downstream_processing_consumers = [
                {
                    "consumer_operator_id": all_scope_sites[consumer]["operator_id"],
                    "consumer_line_start": all_scope_sites[consumer]["line_start"],
                    "producer_component_index": component_index_by_all[producer],
                    "kinds": all_evidence.get((producer, consumer), []),
                }
                for producer, consumer in all_scope_features.get("dependency_edges") or []
                if int(producer) in component_index_by_all
                and int(consumer) not in component_index_by_all
            ]
            structure_reasons = _local_structure_reasons(
                component_features, len(component_operators)
            )
            component_calls = _align_component_calls(scope, component_sites)
            if len(component_calls) != len(component_sites):
                raise ValueError(
                    f"cannot align component calls: {_scope_name(scope, parents)}"
                )
            parameter_factory_evidence: list[dict[str, Any]] = []
            structure_reasons.extend(
                _processing_call_structure_reasons(
                    scope,
                    parents=parents,
                    calls=component_calls,
                    parameter_factory_evidence=parameter_factory_evidence,
                )
            )
            boundary_reasons, downstream_low_level_roles = _lexical_boundary_reasons(
                scope, parents, component_sites, source_text
            )
            structure_reasons.extend(boundary_reasons)
            is_multi_step = len(component_operators) >= 2
            control_path_status, control_path = _control_path_evidence(
                component_calls, scope, parents
            )
            boundary_rule_ids: list[str] = []
            if (
                is_multi_step
                and control_path_status == "same_if_branch"
                and "control_flow:if" in structure_reasons
            ):
                boundary_rule_ids.append(
                    "candidate:same-if-branch-local-dag-v1"
                )
            parameter_factory_evidence = sorted(
                {
                    (
                        str(item["factory"]),
                        int(item["line"]),
                        str(item["literal_suffix"]),
                    ): item
                    for item in parameter_factory_evidence
                }.values(),
                key=lambda item: (int(item["line"]), str(item["factory"])),
            )
            structure_status = (
                "deferred"
                if structure_reasons
                else "eligible"
                if is_multi_step
                else "single_step_not_training_target"
            )
            name = _scope_name(scope, parents)
            units.append(
                {
                    "schema": "gis_recommend.qgis_local_subworkflow_unit.v1",
                    "unit_id": _unit_id(name, component_sites, component_edges),
                    "lexical_scope": name,
                    "operator_ids": component_operators,
                    "call_sites": component_sites,
                    "dependency_edges": component_edges,
                    "dependency_edge_evidence": edge_evidence,
                    "split_class": (
                        "multi_step_local_dag"
                        if is_multi_step
                        else "single_step_local_unit"
                    ),
                    "local_structure_status": structure_status,
                    "local_structure_reasons": structure_reasons,
                    "boundary_rule_ids": boundary_rule_ids,
                    "parameter_factory_evidence": parameter_factory_evidence,
                    "local_risk_evidence": {
                        "control_flow_kinds": component_features.get(
                            "control_flow_kinds"
                        )
                        or [],
                        "control_path_status": control_path_status,
                        "control_path": control_path,
                        "unresolved_output_references": component_features.get(
                            "unresolved_output_references"
                        )
                        or [],
                        "processing_temporary_input_references": component_features.get(
                            "processing_temporary_input_references"
                        )
                        or [],
                        "provider_input_type_conflicts": component_features.get(
                            "provider_input_type_conflicts"
                        )
                        or [],
                        "provider_input_type_checks": component_features.get(
                            "provider_input_type_checks"
                        )
                        or [],
                        "provider_input_type_status": component_features.get(
                            "provider_input_type_status"
                        )
                        or "not_applicable",
                        "intermediate_data_transform_calls": component_features.get(
                            "intermediate_data_transform_calls"
                        )
                        or [],
                        "downstream_data_transform_calls": component_features.get(
                            "downstream_data_transform_calls"
                        )
                        or [],
                        "unused_temporary_terminal_indices": component_features.get(
                            "unused_temporary_terminal_indices"
                        )
                        or [],
                        "downstream_low_level_data_transform_roles": downstream_low_level_roles,
                        "downstream_processing_consumers": downstream_processing_consumers,
                    },
                    "workflow_unit_scope": "local_subworkflow",
                    "feature_extractor_version": FEATURE_EXTRACTOR_VERSION,
                    "splitter_version": SPLITTER_VERSION,
                    "training_admission": (
                        "not_granted_pending_split_rule_audit"
                        if structure_status == "eligible"
                        else "not_granted_local_structure_deferred"
                    ),
                    "training_row_emitted": False,
                    "validation_eligible": False,
                    "test_eligible": False,
                }
            )
    units.sort(key=lambda unit: min(int(site["line_start"]) for site in unit["call_sites"]))
    return units
