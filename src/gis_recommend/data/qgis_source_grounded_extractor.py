"""Deterministic extraction of source-grounded QGIS operator evidence."""

from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Any

from gis_recommend.data.qgis_pilot import (
    classify_qgis_api_call,
    normalize_qgis_operation,
)


_PROVIDER_QUALIFIED_ID = re.compile(
    r"^[A-Za-z][A-Za-z0-9_.-]*:[A-Za-z0-9][A-Za-z0-9_.-]*$"
)

_DIRECT_API_OPERATOR_RULES = (
    (("qgsgeometry.buffer",), ("native:buffer", "qgis:buffer"), "buffer"),
    (("qgsgeometry.intersection",), ("native:intersection", "qgis:intersection"), "intersection"),
    (("qgsgeometry.difference",), ("native:difference", "qgis:difference"), "difference"),
    (("qgsgeometry.combine", "qgsgeometry.unaryunion"), ("native:union", "qgis:union"), "union"),
    (("qgsgeometry.simplify",), ("native:simplifygeometries", "qgis:simplifygeometries"), "simplify"),
    (("qgsgeometry.makevalid",), ("native:fixgeometries", "qgis:fixgeometries"), "geometry_repair"),
    (("qgscoordinatetransform", "qgsgeometry.transform"), ("native:reprojectlayer", "qgis:reprojectlayer"), "crs_transform"),
    (("gdal.warp",), ("gdal:warpreproject",), "crs_transform"),
    (("qgsrastercalculator",), ("qgis:rastercalculator",), "raster_calculation"),
    (("gdal.rasterizelayer", "gdal.rasterize"), ("gdal:rasterize",), "rasterize"),
    (("gdal.polygonize",), ("gdal:polygonize",), "polygonize"),
    (("gdal.translate",), ("gdal:translate",), "data_export"),
    (("gdal.buildvrt",), ("gdal:buildvirtualraster",), "raster_merge"),
    (("qgsgeometry.centroid",), ("native:centroids", "qgis:centroids"), "centroid"),
    (("qgszonalstatistics",), ("native:zonalstatisticsfb", "qgis:zonalstatisticsfb", "native:zonalstatistics", "qgis:zonalstatistics"), "zonal_statistics"),
)


def _node_type(node: Mapping[str, Any]) -> str:
    return str(node.get("type") or node.get("_type") or "")


def _source_position(node: Mapping[str, Any], ordinal: int) -> tuple[int, int, int]:
    line = node.get("lineno")
    column = node.get("col_offset")
    return (
        int(line) if isinstance(line, int) else 2**31 - 1,
        int(column) if isinstance(column, int) else 2**31 - 1,
        ordinal,
    )


def _walk_ast(value: Any):
    ordinal = 0

    def visit(item: Any):
        nonlocal ordinal
        if isinstance(item, Mapping):
            current = ordinal
            ordinal += 1
            yield item, current
            for child in item.values():
                yield from visit(child)
        elif isinstance(item, list):
            for child in item:
                yield from visit(child)

    yield from visit(value)


def _literal_string(node: Any) -> str | None:
    if not isinstance(node, Mapping):
        return None
    if _node_type(node) not in {"Constant", "Str"}:
        return None
    value = node.get("value", node.get("s"))
    return value.strip() if isinstance(value, str) else None


def _literal_strings(value: Any) -> list[str]:
    return [
        literal
        for node, _ in _walk_ast(value)
        if (literal := _literal_string(node)) is not None
    ]


def _base_name(node: Any) -> str:
    if not isinstance(node, Mapping):
        return ""
    node_kind = _node_type(node)
    if node_kind == "Name":
        return str(node.get("id") or "")
    if node_kind == "Attribute":
        parent = _base_name(node.get("value"))
        attribute = str(node.get("attr") or "")
        return ".".join(part for part in (parent, attribute) if part)
    return ""


def _callable_name(node: Any) -> str:
    if not isinstance(node, Mapping):
        return ""
    if _node_type(node) == "Call":
        called = _callable_name(node.get("func"))
        return f"{called}()" if called else ""
    return _base_name(node)


def _returned_literal(class_node: Mapping[str, Any], method_name: str) -> str | None:
    for child in class_node.get("body") or []:
        if not isinstance(child, Mapping):
            continue
        if _node_type(child) not in {"FunctionDef", "AsyncFunctionDef"}:
            continue
        if child.get("name") != method_name:
            continue
        for statement in child.get("body") or []:
            if isinstance(statement, Mapping) and _node_type(statement) == "Return":
                return _literal_string(statement.get("value"))
    return None


def _module_provider(module: str) -> str | None:
    normalized = module.lower()
    if normalized == "qgis" or normalized.startswith("qgis."):
        return "qgis"
    if (
        normalized in {"gdal", "osgeo", "osgeo.gdal"}
        or normalized.startswith("osgeo.gdal.")
        or ".gdal." in normalized
        or normalized.endswith(".gdal")
    ):
        return "gdal"
    return None


def _import_provider_aliases(ast_record: Mapping[str, Any]) -> dict[str, str]:
    aliases = {}
    for node, _ in _walk_ast(ast_record):
        node_kind = _node_type(node)
        if node_kind == "ImportFrom":
            module = str(node.get("module") or "")
            provider = _module_provider(module)
            if provider is None:
                continue
            for alias in node.get("names") or []:
                if not isinstance(alias, Mapping) or not alias.get("name"):
                    continue
                local_name = str(alias.get("asname") or alias.get("name"))
                aliases[local_name] = provider
        elif node_kind == "Import":
            for alias in node.get("names") or []:
                if not isinstance(alias, Mapping) or not alias.get("name"):
                    continue
                module = str(alias.get("name"))
                provider = _module_provider(module)
                if provider is None:
                    continue
                local_name = str(alias.get("asname") or module.partition(".")[0])
                aliases[local_name] = provider
    return aliases


def _provider_evidence(
    class_node: Mapping[str, Any], import_provider_aliases: Mapping[str, str]
) -> list[str]:
    providers = set()
    for base in class_node.get("bases") or []:
        normalized = _base_name(base).lower()
        if "qgisalgorithm" in normalized:
            providers.add("qgis")
        if "gdalalgorithm" in normalized:
            providers.add("gdal")
        if "nativealgorithm" in normalized:
            providers.add("native")
        base_name = _base_name(base)
        root_name = base_name.partition(".")[0]
        provider = import_provider_aliases.get(root_name)
        if provider is not None:
            providers.add(provider)
    return sorted(providers)


def _literal_value(node: Any) -> Any:
    if not isinstance(node, Mapping):
        return None
    if _node_type(node) not in {"Constant", "Str", "Num"}:
        return None
    return node.get("value", node.get("s", node.get("n")))


def _method_schema(class_node: Mapping[str, Any], method_name: str) -> list[dict[str, Any]]:
    schema = []
    for node, _ in _walk_ast(class_node.get("body") or []):
        if _node_type(node) != "Call":
            continue
        callable_name = _callable_name(node.get("func"))
        if callable_name.rpartition(".")[2].lower() != method_name.lower():
            continue
        arguments = node.get("args") or []
        constructor = ""
        values = []
        if arguments and isinstance(arguments[0], Mapping) and _node_type(arguments[0]) == "Call":
            constructor = _callable_name(arguments[0].get("func"))
            values = [_literal_value(argument) for argument in arguments[0].get("args") or []]
        schema.append(
            {
                "constructor": constructor or None,
                "name": values[0] if values else None,
                "description": values[1] if len(values) > 1 else None,
                "arguments": [value for value in values if value is not None],
            }
        )
    return schema


def _catalog_operator_ids(catalog: Mapping[str, Any]) -> set[str]:
    return {
        str(operator_id).strip().lower()
        for operator_id in catalog
        if isinstance(operator_id, str) and ":" in operator_id
    }


def _resolve_class_operator(
    algorithm_name: str,
    provider_evidence: list[str],
    catalog_ids: set[str],
) -> tuple[str | None, list[str], str | None]:
    normalized_name = algorithm_name.strip().lower()
    if _PROVIDER_QUALIFIED_ID.fullmatch(normalized_name):
        operator_id, candidates = (
            (normalized_name, [normalized_name])
            if normalized_name in catalog_ids
            else (None, [])
        )
        return operator_id, candidates, None if operator_id else "unresolved_catalog_identity"

    suffix_candidates = sorted(
        operator_id
        for operator_id in catalog_ids
        if operator_id.partition(":")[2] == normalized_name
    )
    if provider_evidence:
        provider_candidates = [
            operator_id
            for operator_id in suffix_candidates
            if operator_id.partition(":")[0] in provider_evidence
        ]
        if len(provider_candidates) == 1:
            return provider_candidates[0], provider_candidates, None
        if len(provider_candidates) > 1:
            return None, provider_candidates, "ambiguous_provider_evidence"
        if suffix_candidates:
            return None, suffix_candidates, "provider_conflict"
        return None, [], "unresolved_catalog_identity"

    if len(suffix_candidates) == 1:
        return suffix_candidates[0], suffix_candidates, None
    reason = (
        "ambiguous_catalog_identity"
        if len(suffix_candidates) > 1
        else "unresolved_catalog_identity"
    )
    return None, suffix_candidates, reason


def extract_ast_evidence(
    ast_record: Mapping[str, Any],
    catalog: Mapping[str, Any],
) -> dict[str, list[dict[str, Any]]]:
    """Extract E0/E1 evidence from a serialized Python AST.

    Resolution is exact and fail-closed. Unknown provider-qualified literals and
    ambiguous class identities are retained for review instead of being mapped.
    """

    catalog_ids = _catalog_operator_ids(catalog)
    import_provider_aliases = _import_provider_aliases(ast_record)
    explicit_candidates = []
    class_nodes = []
    literal_bindings: dict[str, list[str]] = {}
    for node, ordinal in _walk_ast(ast_record):
        position = _source_position(node, ordinal)
        if _node_type(node) == "Assign":
            values = _literal_strings(node.get("value"))
            for target in node.get("targets") or []:
                if isinstance(target, Mapping) and _node_type(target) == "Name":
                    literal_bindings[str(target.get("id") or "")] = values
        if _node_type(node) == "Call":
            callable_name = _callable_name(node.get("func")).lower()
            is_explicit_algorithm_call = callable_name in {
                "processing.run",
                "processing.runandloadresults",
                "processing.runalg",
                "general.runalg",
            } or callable_name.endswith((".algorithmbyid", ".createalgorithmbyid"))
            arguments = node.get("args") or []
            literal = _literal_string(arguments[0]) if arguments else None
            if (
                is_explicit_algorithm_call
                and literal
                and _PROVIDER_QUALIFIED_ID.fullmatch(literal)
            ):
                explicit_candidates.append((position, literal.lower()))
            if callable_name in {
                "subprocess.call",
                "subprocess.run",
                "subprocess.check_call",
                "subprocess.check_output",
            }:
                command_literals = [
                    value
                    for descendant, _ in _walk_ast(node.get("args") or [])
                    if (value := _literal_string(descendant)) is not None
                ]
                for argument in node.get("args") or []:
                    if isinstance(argument, Mapping) and _node_type(argument) == "Name":
                        command_literals.extend(
                            literal_bindings.get(str(argument.get("id") or ""), [])
                        )
                command_names = {
                    value.replace("\\", "/").rsplit("/", 1)[-1].lower()
                    for value in command_literals
                }
                if command_names.intersection(
                    {"gdal_calc", "gdal_calc.py", "osgeo_utils.gdal_calc"}
                ):
                    explicit_candidates.append(
                        (position, "gdal:rastercalculator")
                    )
        if _node_type(node) == "ClassDef":
            class_nodes.append((position, node))

    explicit_operators = []
    unresolved_explicit_ids = []
    ast_operator_events = []
    for position, operator_id in sorted(explicit_candidates):
        line = None if position[0] == 2**31 - 1 else position[0]
        if operator_id in catalog_ids:
            explicit_operators.append(
                {
                    "operator_id": operator_id,
                    "line": line,
                    "evidence_tier": "E0",
                }
            )
            ast_operator_events.append(
                {
                    "operator_id": operator_id,
                    "evidence_tier": "E0",
                    "line": line,
                    "source_ordinal": position[2],
                }
            )
        else:
            unresolved_explicit_ids.append({"operator_id": operator_id, "line": line})

    class_operators = []
    custom_components = []
    for position, class_node in sorted(class_nodes, key=lambda item: item[0]):
        class_name = str(class_node.get("name") or "")
        line = None if position[0] == 2**31 - 1 else position[0]
        algorithm_name = _returned_literal(class_node, "name")
        if not algorithm_name:
            custom_components.append(
                {
                    "class_name": class_name,
                    "line": line,
                    "reason": "class_without_catalog_identity",
                    "evidence_tier": "E3",
                }
            )
            continue

        providers = _provider_evidence(class_node, import_provider_aliases)
        operator_id, candidates, unresolved_reason = _resolve_class_operator(
            algorithm_name, providers, catalog_ids
        )
        if operator_id is not None:
            class_operators.append(
                {
                    "class_name": class_name,
                    "operator_id": operator_id,
                    "algorithm_name": algorithm_name,
                    "display_name": _returned_literal(class_node, "displayName"),
                    "group_id": _returned_literal(class_node, "groupId"),
                    "provider_evidence": providers,
                    "parameter_schema": _method_schema(class_node, "addParameter"),
                    "output_schema": _method_schema(class_node, "addOutput"),
                    "line": line,
                    "evidence_tier": "E1",
                }
            )
            ast_operator_events.append(
                {
                    "operator_id": operator_id,
                    "evidence_tier": "E1",
                    "line": line,
                    "source_ordinal": position[2],
                }
            )
            continue

        custom = {
            "class_name": class_name,
            "line": line,
            "reason": unresolved_reason,
            "algorithm_name": algorithm_name,
        }
        if providers:
            custom["provider_evidence"] = providers
        if candidates:
            custom["candidate_operator_ids"] = candidates
        custom["evidence_tier"] = "E3"
        custom_components.append(custom)

    return {
        "explicit_operators": explicit_operators,
        "unresolved_explicit_ids": unresolved_explicit_ids,
        "class_operators": class_operators,
        "custom_components": custom_components,
        "ast_operator_events": sorted(
            ast_operator_events,
            key=lambda item: (
                item["line"] if item["line"] is not None else 2**31 - 1,
                item["source_ordinal"],
            ),
        ),
    }


def _ordered_steps(steps: list[Mapping[str, Any]]) -> list[dict[str, Any]]:
    positioned = []
    for ordinal, step in enumerate(steps):
        clean = dict(step)
        try:
            statement_index = int(clean.get("statement_index"))
        except (TypeError, ValueError):
            statement_index = 2**31 - 1
        positioned.append((statement_index, ordinal, clean))
    return [item[2] for item in sorted(positioned)]


def _evidence_id(step: Mapping[str, Any], ordinal: int) -> str:
    explicit = step.get("evidence_id") or step.get("step_id")
    return str(explicit) if explicit else f"ordered-step-{ordinal + 1}"


def _direct_api_operator(
    operation: str, catalog_ids: set[str]
) -> tuple[str | None, str | None, list[str]]:
    for patterns, operator_candidates, semantic_family in _DIRECT_API_OPERATOR_RULES:
        if not any(
            operation == pattern or operation.startswith(f"{pattern}.")
            for pattern in patterns
        ):
            continue
        present_candidates = [
            operator_id
            for operator_id in operator_candidates
            if operator_id in catalog_ids
        ]
        if len(present_candidates) == 1:
            return present_candidates[0], semantic_family, present_candidates
        return None, semantic_family, present_candidates
    return None, None, []


def _unsupported_category(operation: str) -> str:
    classification = classify_qgis_api_call(
        {"operation": operation, "channel": "direct_api"}
    )
    category = classification["category"]
    if category == "semantic_anchor":
        return "supporting_evidence"
    if category in {"data_access", "infrastructure"}:
        return category
    return "unknown" if category == "processing_operator" else category


def _step_source_line(step: Mapping[str, Any]) -> int | None:
    for key in ("source_line", "lineno", "line"):
        value = step.get(key)
        if isinstance(value, int):
            return value
    return None


def _operator_detail(
    step: Mapping[str, Any],
    operator_id: str,
    evidence_tier: str,
    evidence_id: str,
    semantic_family: str,
) -> dict[str, Any]:
    return {
        "operator_id": operator_id,
        "evidence_tier": evidence_tier,
        "evidence_ids": [evidence_id],
        "statement_index": step.get("statement_index"),
        "source_line": _step_source_line(step),
        "semantic_step_id": step.get("semantic_step_id"),
        "semantic_family": semantic_family,
        "confidence": 1.0 if evidence_tier == "E0" else 0.9,
        "arguments": step.get("args", step.get("arguments", [])),
        "input_roles": step.get("input_roles", []),
        "output_roles": step.get("output_roles", []),
        "dependencies": step.get("dependencies", []),
        "scope": step.get("scope"),
    }


def compile_source_grounded_record(
    ast_record: Mapping[str, Any],
    ordered_steps: list[Mapping[str, Any]],
    catalog: Mapping[str, Any],
    *,
    task_text_provenance: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Compile AST and ordered call evidence into a fail-closed record."""

    ast_evidence = extract_ast_evidence(ast_record, catalog)
    catalog_ids = _catalog_operator_ids(catalog)
    ordered_operator_evidence = []
    unsupported_evidence = []
    semantic_groups: dict[tuple[str, str], dict[str, Any]] = {}

    for ordinal, step in enumerate(_ordered_steps(ordered_steps)):
        operation = normalize_qgis_operation(step.get("operation"))
        evidence_id = _evidence_id(step, ordinal)
        channel = str(step.get("channel") or "")
        operator_id = None
        evidence_tier = None
        semantic_family = None
        candidate_operator_ids = []

        if operation in catalog_ids and (
            channel in {"processing_algorithms", "custom_algorithms"}
            or _PROVIDER_QUALIFIED_ID.fullmatch(operation)
        ):
            operator_id = operation
            evidence_tier = "E0"
            semantic_family = "explicit_processing"
        elif channel == "direct_api":
            operator_id, semantic_family, candidate_operator_ids = (
                _direct_api_operator(operation, catalog_ids)
            )
            if operator_id is not None:
                evidence_tier = "E2"

        if operator_id is None:
            unsupported = {
                "evidence_id": evidence_id,
                "operation": operation,
                "category": _unsupported_category(operation),
                "statement_index": step.get("statement_index"),
                "source_line": _step_source_line(step),
                "arguments": step.get("args", step.get("arguments", [])),
                "input_roles": step.get("input_roles", []),
                "output_roles": step.get("output_roles", []),
                "dependencies": step.get("dependencies", []),
                "scope": step.get("scope"),
            }
            if semantic_family is not None:
                unsupported["semantic_family"] = semantic_family
            if candidate_operator_ids:
                unsupported["candidate_operator_ids"] = candidate_operator_ids
            unsupported_evidence.append(unsupported)
            continue

        detail = _operator_detail(
            step,
            operator_id,
            evidence_tier,
            evidence_id,
            semantic_family,
        )
        semantic_step_id = detail["semantic_step_id"]
        group_key = (str(semantic_step_id), operator_id)
        if (
            evidence_tier in {"E0", "E2"}
            and semantic_step_id
            and group_key in semantic_groups
        ):
            semantic_groups[group_key]["evidence_ids"].append(evidence_id)
            continue
        ordered_operator_evidence.append(detail)
        if evidence_tier in {"E0", "E2"} and semantic_step_id:
            semantic_groups[group_key] = detail

    ast_operator_evidence = []
    for item in ast_evidence["ast_operator_events"]:
        evidence_prefix = "ast" if item["evidence_tier"] == "E0" else "class"
        ast_operator_evidence.append(
            {
                "operator_id": item["operator_id"],
                "evidence_tier": item["evidence_tier"],
                "evidence_ids": [f"{evidence_prefix}-line-{item['line']}"],
                "line": item["line"],
                "source_ordinal": item["source_ordinal"],
                "semantic_family": "explicit_processing"
                if item["evidence_tier"] == "E0"
                else "self_describing_class",
                "confidence": 1.0,
                "arguments": [],
                "input_roles": [],
                "output_roles": [],
                "dependencies": [],
                "scope": None,
            }
        )

    parallel_ast_operator_evidence = []
    supporting_operator_evidence = []
    has_e1_identity = any(
        item["evidence_tier"] == "E1" for item in ast_operator_evidence
    )
    has_e0_identity = any(
        item["evidence_tier"] == "E0"
        for item in ordered_operator_evidence + ast_operator_evidence
    )
    if has_e1_identity and not has_e0_identity:
        operator_evidence = [
            item
            for item in ast_operator_evidence
            if item["evidence_tier"] == "E1"
        ]
        supporting_operator_evidence = ordered_operator_evidence
        cross_source_ordering = "e1_authoritative"
    elif ordered_operator_evidence and ast_operator_evidence:
        ordered_source_lines = {
            item["source_line"]
            for item in ordered_operator_evidence
            if isinstance(item.get("source_line"), int)
        }
        ast_source_lines = {
            item["line"]
            for item in ast_operator_evidence
            if isinstance(item.get("line"), int)
        }
        if (
            all(
                isinstance(item.get("source_line"), int)
                for item in ordered_operator_evidence
            )
            and ordered_source_lines.intersection(ast_source_lines)
        ):
            operator_evidence = list(ordered_operator_evidence)
            unmatched_ast_evidence = []
            for ast_item in ast_operator_evidence:
                matches = [
                    ordered_item
                    for ordered_item in ordered_operator_evidence
                    if ordered_item["source_line"] == ast_item["line"]
                    and ordered_item["operator_id"] == ast_item["operator_id"]
                ]
                if len(matches) == 1:
                    matches[0]["evidence_ids"].extend(ast_item["evidence_ids"])
                    matches[0].setdefault(
                        "corroborating_evidence_tiers", []
                    ).append(ast_item["evidence_tier"])
                elif len(matches) > 1:
                    parallel_ast_operator_evidence.append(ast_item)
                else:
                    unmatched_ast_evidence.append(ast_item)
            operator_evidence.extend(unmatched_ast_evidence)
            operator_evidence.sort(
                key=lambda item: (
                    item.get("source_line", item.get("line", 2**31 - 1)),
                    item.get("source_ordinal", 0),
                )
            )
            cross_source_ordering = (
                "partially_comparable"
                if parallel_ast_operator_evidence
                else "shared_source_line"
            )
        else:
            operator_evidence = ordered_operator_evidence
            parallel_ast_operator_evidence = ast_operator_evidence
            cross_source_ordering = "not_comparable"
    elif ordered_operator_evidence:
        operator_evidence = ordered_operator_evidence
        cross_source_ordering = "ordered_steps_only"
    else:
        operator_evidence = ast_operator_evidence
        cross_source_ordering = "ast_only"

    evidence_tiers = {item["evidence_tier"] for item in operator_evidence}
    evidence_tiers.update(
        item["evidence_tier"] for item in parallel_ast_operator_evidence
    )
    evidence_tiers.update(
        item["evidence_tier"] for item in supporting_operator_evidence
    )
    if ast_evidence["custom_components"]:
        evidence_tiers.add("E3")

    confidences = [item["confidence"] for item in operator_evidence]

    return {
        **ast_evidence,
        "operator_chain": [item["operator_id"] for item in operator_evidence],
        "operator_evidence": operator_evidence,
        "parallel_ast_operator_chain": [
            item["operator_id"] for item in parallel_ast_operator_evidence
        ],
        "parallel_ast_operator_evidence": parallel_ast_operator_evidence,
        "supporting_operator_chain": [
            item["operator_id"] for item in supporting_operator_evidence
        ],
        "supporting_operator_evidence": supporting_operator_evidence,
        "cross_source_ordering": cross_source_ordering,
        "unsupported_evidence": unsupported_evidence,
        "evidence_tiers": sorted(evidence_tiers),
        "confidence": min(confidences) if confidences else None,
        "reviewer_status": "pending_human_review",
        "task_text_provenance": dict(task_text_provenance)
        if task_text_provenance is not None
        else {"status": "not_provided"},
        "taxonomy_admission": "not_granted",
        "training_admission": "not_granted",
        "training_rows_emitted": 0,
    }
