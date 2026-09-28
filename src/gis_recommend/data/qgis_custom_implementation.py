from __future__ import annotations

import ast
import hashlib
import warnings
from collections import defaultdict
from collections.abc import Callable, Iterable
from typing import Any


_CONTROL_FLOW_NODES = {
    ast.If: "if",
    ast.For: "for",
    ast.AsyncFor: "for",
    ast.While: "while",
    ast.Try: "try",
    ast.With: "with",
    ast.AsyncWith: "with",
    ast.Match: "match",
}


def _literal_string(node: ast.AST | None) -> str | None:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value.strip().lower()
    return None


def _is_processing_run(node: ast.Call) -> bool:
    return (
        isinstance(node.func, ast.Attribute)
        and node.func.attr == "run"
        and isinstance(node.func.value, ast.Name)
        and node.func.value.id == "processing"
    )


def _self_method_name(node: ast.Call) -> str | None:
    if (
        isinstance(node.func, ast.Attribute)
        and isinstance(node.func.value, ast.Name)
        and node.func.value.id == "self"
    ):
        return node.func.attr
    return None


def _algorithm_name(method: ast.FunctionDef | ast.AsyncFunctionDef) -> str | None:
    for node in ast.walk(method):
        if isinstance(node, ast.Return):
            value = _literal_string(node.value)
            if value:
                return value
    return None


def _body_hash(methods: list[ast.FunctionDef | ast.AsyncFunctionDef]) -> str:
    payload = "\n".join(
        ast.dump(method, annotate_fields=True, include_attributes=False)
        for method in methods
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _extract_method_calls(
    method_name: str,
    methods: dict[str, ast.FunctionDef | ast.AsyncFunctionDef],
    module_functions: dict[str, ast.FunctionDef | ast.AsyncFunctionDef],
) -> dict[str, Any]:
    literal_calls: list[dict[str, Any]] = []
    reachable_helpers: list[str] = []
    control_flow: set[str] = set()
    dynamic_operator_count = 0
    recursive_helper = False

    def definition(key: str) -> ast.FunctionDef | ast.AsyncFunctionDef:
        kind, name = key.split(":", 1)
        return methods[name] if kind == "method" else module_functions[name]

    def visit(node: ast.AST, active_key: str, stack: tuple[str, ...]) -> None:
        nonlocal dynamic_operator_count, recursive_helper
        kind = _CONTROL_FLOW_NODES.get(type(node))
        if kind:
            control_flow.add(kind)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Lambda)):
            if node is not definition(active_key):
                return
        if isinstance(node, ast.Call):
            for argument in [*node.args, *(keyword.value for keyword in node.keywords)]:
                visit(argument, active_key, stack)
            if _is_processing_run(node):
                operator_id = _literal_string(node.args[0] if node.args else None)
                if operator_id is None:
                    dynamic_operator_count += 1
                else:
                    literal_calls.append(
                        {
                            "operator_id": operator_id,
                            "line_start": int(node.lineno),
                            "line_end": int(getattr(node, "end_lineno", node.lineno)),
                            "implementation_method": active_key.split(":", 1)[1],
                        }
                    )
                return
            helper_name = _self_method_name(node)
            if helper_name in methods:
                helper_key = f"method:{helper_name}"
                if helper_key in stack:
                    recursive_helper = True
                    return
                if helper_name not in reachable_helpers:
                    reachable_helpers.append(helper_name)
                visit(methods[helper_name], helper_key, (*stack, helper_key))
                return
            if isinstance(node.func, ast.Name) and node.func.id in module_functions:
                helper_key = f"module:{node.func.id}"
                if helper_key in stack:
                    recursive_helper = True
                    return
                if helper_key not in reachable_helpers:
                    reachable_helpers.append(helper_key)
                visit(module_functions[node.func.id], helper_key, (*stack, helper_key))
                return
            return
        for child in ast.iter_child_nodes(node):
            visit(child, active_key, stack)

    process_key = f"method:{method_name}"
    visit(methods[method_name], process_key, (process_key,))
    reachable_methods = [methods[method_name]]
    for helper in reachable_helpers:
        if helper.startswith("module:"):
            reachable_methods.append(module_functions[helper.split(":", 1)[1]])
        else:
            reachable_methods.append(methods[helper])
    return {
        "literal_calls": literal_calls,
        "reachable_helpers": reachable_helpers,
        "control_flow_kinds": sorted(control_flow),
        "dynamic_operator_count": dynamic_operator_count,
        "recursive_helper": recursive_helper,
        "implementation_body_sha256": _body_hash(reachable_methods),
    }


def extract_custom_implementations(source_text: str) -> list[dict[str, Any]]:
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", SyntaxWarning)
            tree = ast.parse(source_text)
    except SyntaxError:
        return []

    implementations: list[dict[str, Any]] = []
    module_functions = {
        node.name: node
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }
    for class_node in (node for node in tree.body if isinstance(node, ast.ClassDef)):
        methods = {
            node.name: node
            for node in class_node.body
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        }
        name_method = methods.get("name")
        process_method = methods.get("processAlgorithm")
        if name_method is None or process_method is None:
            continue
        name = _algorithm_name(name_method)
        if not name:
            continue
        extracted = _extract_method_calls(
            "processAlgorithm", methods, module_functions
        )
        if extracted["recursive_helper"]:
            status = "deferred_recursive_helper"
        elif extracted["dynamic_operator_count"]:
            status = "deferred_dynamic_operator"
        elif not extracted["literal_calls"]:
            status = "deferred_no_literal_processing_dag"
        else:
            status = "complete_literal_dag"
        implementations.append(
            {
                "algorithm_id": f"script:{name}",
                "class_name": class_node.name,
                "process_line_start": int(process_method.lineno),
                "process_line_end": int(
                    getattr(process_method, "end_lineno", process_method.lineno)
                ),
                "literal_operator_ids": [
                    call["operator_id"] for call in extracted["literal_calls"]
                ],
                "call_sites": extracted["literal_calls"],
                "reachable_helpers": extracted["reachable_helpers"],
                "control_flow_kinds": extracted["control_flow_kinds"],
                "dynamic_operator_count": extracted["dynamic_operator_count"],
                "implementation_body_sha256": extracted[
                    "implementation_body_sha256"
                ],
                "extraction_status": status,
            }
        )
    return implementations


def build_implementation_index(
    implementations: Iterable[dict[str, Any]],
) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, dict[str, dict[str, Any]]] = defaultdict(dict)
    for implementation in implementations:
        algorithm_id = str(implementation.get("algorithm_id") or "").lower()
        body_hash = str(implementation.get("implementation_body_sha256") or "")
        if algorithm_id and body_hash:
            grouped[algorithm_id].setdefault(body_hash, implementation)
    return {
        algorithm_id: [variants[key] for key in sorted(variants)]
        for algorithm_id, variants in sorted(grouped.items())
    }


def _default_canonicalize(operator_id: str, catalog_ids: set[str]) -> str | None:
    normalized = operator_id.strip().lower()
    if normalized in catalog_ids:
        return normalized
    provider, separator, slug = normalized.partition(":")
    if not separator:
        return None
    provider_candidates = {
        "qgis": ("native",),
        "native": ("qgis",),
        "gdalogr": ("gdal",),
        "grass": ("grass7",),
        "sagang": ("saga",),
    }.get(provider, ())
    for candidate_provider in provider_candidates:
        candidate = f"{candidate_provider}:{slug}"
        if candidate in catalog_ids:
            return candidate
    return None


def expand_custom_implementation(
    algorithm_id: str,
    implementation_index: dict[str, list[dict[str, Any]]],
    *,
    catalog_ids: set[str],
    canonicalize_operator: Callable[[str, set[str]], str | None] | None = None,
    implementation_body_bindings: dict[str, str] | None = None,
    implementation_id_aliases: dict[str, str] | None = None,
) -> dict[str, Any]:
    canonicalize = canonicalize_operator or _default_canonicalize
    body_bindings = {
        str(key).strip().lower(): str(value)
        for key, value in (implementation_body_bindings or {}).items()
    }
    aliases = {
        str(key).strip().lower(): str(value).strip().lower()
        for key, value in (implementation_id_aliases or {}).items()
    }

    def expand(current: str, stack: tuple[str, ...]) -> dict[str, Any]:
        normalized = aliases.get(current.strip().lower(), current.strip().lower())
        if normalized in stack:
            return {
                "expansion_status": "deferred_recursive_implementation",
                "expanded_operator_ids": [],
                "expanded_custom_ids": [normalized],
                "unresolved_operator_ids": [normalized],
            }
        variants = implementation_index.get(normalized, [])
        if not variants:
            return {
                "expansion_status": "deferred_missing_implementation",
                "expanded_operator_ids": [],
                "expanded_custom_ids": [normalized],
                "unresolved_operator_ids": [normalized],
            }
        bound_body = body_bindings.get(normalized)
        if bound_body:
            variants = [
                variant
                for variant in variants
                if variant.get("implementation_body_sha256") == bound_body
            ]
            if not variants:
                return {
                    "expansion_status": "deferred_binding_mismatch",
                    "expanded_operator_ids": [],
                    "expanded_custom_ids": [normalized],
                    "unresolved_operator_ids": [normalized],
                }
        if len(variants) != 1:
            return {
                "expansion_status": "deferred_ambiguous_implementation",
                "expanded_operator_ids": [],
                "expanded_custom_ids": [normalized],
                "unresolved_operator_ids": [normalized],
            }
        implementation = variants[0]
        if implementation.get("extraction_status") != "complete_literal_dag":
            return {
                "expansion_status": str(implementation.get("extraction_status")),
                "expanded_operator_ids": [],
                "expanded_custom_ids": [normalized],
                "unresolved_operator_ids": [normalized],
            }

        expanded: list[str] = []
        custom_ids = [normalized]
        for operator_id in implementation.get("literal_operator_ids") or []:
            operator = str(operator_id).strip().lower()
            canonical = canonicalize(operator, catalog_ids)
            if canonical is not None:
                expanded.append(canonical)
                continue
            if operator.startswith("script:"):
                nested = expand(operator, (*stack, normalized))
                if nested["expansion_status"] != "expanded_complete":
                    return {
                        **nested,
                        "expanded_custom_ids": list(
                            dict.fromkeys([normalized, *nested["expanded_custom_ids"]])
                        ),
                    }
                expanded.extend(nested["expanded_operator_ids"])
                custom_ids.extend(nested["expanded_custom_ids"])
                continue
            return {
                "expansion_status": "deferred_unresolved_operator",
                "expanded_operator_ids": [],
                "expanded_custom_ids": list(dict.fromkeys(custom_ids)),
                "unresolved_operator_ids": [operator],
            }
        return {
            "expansion_status": "expanded_complete",
            "expanded_operator_ids": expanded,
            "expanded_custom_ids": list(dict.fromkeys(custom_ids)),
            "unresolved_operator_ids": [],
        }

    return expand(algorithm_id, ())
