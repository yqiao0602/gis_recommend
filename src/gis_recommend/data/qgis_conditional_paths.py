"""Recover bounded Processing paths around optional passthrough branches."""

from __future__ import annotations

import ast
import itertools
import warnings
from collections.abc import Mapping, Sequence
from typing import Any

from gis_recommend.data.qgis_conversion_features import (
    _assignment_definitions,
    _assignment_target,
    _expanded_reference_keys,
    _is_processing_call,
    _lexical_scope,
    _operator_id,
    _parents,
    _reference_keys,
    _target_key,
    extract_conversion_features,
)


MATCHER_VERSION = "conditional-passthrough-paths-v1"

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


def _result(status: str, *, reasons: Sequence[str] = (), **evidence: Any) -> dict[str, Any]:
    return {
        "schema": "gis_recommend.qgis_conditional_passthrough_match.v1",
        "matcher_version": MATCHER_VERSION,
        "rule_id": MATCHER_VERSION,
        "status": status,
        "reasons": sorted(set(reasons)),
        "merge_targets": [],
        "optional_producer_indices": [],
        "common_consumer_indices": [],
        "path_operator_ids": [],
        "paths": [],
        **evidence,
    }


def _is_descendant(node: ast.AST, ancestor: ast.AST, parents: Mapping[ast.AST, ast.AST]) -> bool:
    current = node
    while current in parents:
        current = parents[current]
        if current is ancestor:
            return True
    return False


def _branch(node: ast.AST, conditional: ast.If, parents: Mapping[ast.AST, ast.AST]) -> str | None:
    for statement in conditional.body:
        if node is statement or _is_descendant(node, statement, parents):
            return "body"
    for statement in conditional.orelse:
        if node is statement or _is_descendant(node, statement, parents):
            return "orelse"
    return None


def _ancestor_conditionals(
    node: ast.AST, scope: ast.AST, parents: Mapping[ast.AST, ast.AST]
) -> list[ast.If]:
    result: list[ast.If] = []
    current = node
    while current in parents:
        current = parents[current]
        if current is scope:
            break
        if isinstance(current, ast.If):
            result.append(current)
    return result


def _unsupported_control_flow(
    calls: Sequence[ast.Call], scope: ast.AST, parents: Mapping[ast.AST, ast.AST]
) -> list[str]:
    kinds: set[str] = set()
    for call in calls:
        current: ast.AST = call
        while current in parents:
            current = parents[current]
            if current is scope:
                break
            if isinstance(current, (ast.For, ast.AsyncFor, ast.While)):
                kinds.add("for" if isinstance(current, (ast.For, ast.AsyncFor)) else "while")
            elif isinstance(current, (ast.Try, ast.TryStar)):
                kinds.add("try")
    return [f"unsupported_control_flow:{kind}" for kind in sorted(kinds)]


def _align_calls(
    literal_calls: Sequence[ast.Call], call_sites: Sequence[Mapping[str, Any]]
) -> tuple[list[ast.Call], list[str]]:
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
            and int(call.lineno) <= end
            and int(call.end_lineno or call.lineno) >= start
        ]
        if not candidates:
            return [], [f"call_site_alignment_failed:{operator_id}@{start}-{end}"]
        chosen = min(candidates, key=lambda call: abs(int(call.lineno) - start))
        used.add(id(chosen))
        aligned.append(chosen)
    return sorted(aligned, key=lambda call: (call.lineno, call.col_offset)), []


def _assignments_in_statements(
    statements: Sequence[ast.stmt], parents: Mapping[ast.AST, ast.AST]
) -> list[tuple[int, str, ast.AST]]:
    assignments: list[tuple[int, str, ast.AST]] = []
    for statement in statements:
        for node in ast.walk(statement):
            if isinstance(node, ast.Assign) and node.targets:
                target = _target_key(node.targets[0])
                value = node.value
            elif isinstance(node, ast.AnnAssign) and node.value is not None:
                target = _target_key(node.target)
                value = node.value
            else:
                continue
            if target:
                assignments.append((int(node.lineno), target, value))
    return sorted(assignments)


def _latest_alias_target(
    branch_statements: Sequence[ast.stmt],
    branch_calls: Sequence[ast.Call],
    parents: Mapping[ast.AST, ast.AST],
    definitions: Sequence[tuple[ast.AST, int, str, ast.AST]],
) -> tuple[str | None, set[str]]:
    final_call = max(branch_calls, key=lambda call: (call.lineno, call.col_offset))
    call_target = _assignment_target(final_call, dict(parents))
    if not call_target:
        return None, set()
    target = call_target
    source_references = _expanded_reference_keys(
        final_call,
        call=final_call,
        parents=dict(parents),
        definitions=list(definitions),
    )
    for line, candidate_target, value in _assignments_in_statements(
        branch_statements, parents
    ):
        if line <= int(final_call.end_lineno or final_call.lineno):
            continue
        references = _reference_keys(value)
        if target in references or any(ref.startswith(target + ".") for ref in references):
            target = candidate_target
    return target, source_references


def _passthrough_source(
    statements: Sequence[ast.stmt], merge_target: str
) -> set[str] | None:
    matches: list[set[str]] = []
    for statement in statements:
        if isinstance(statement, ast.Assign) and statement.targets:
            target = _target_key(statement.targets[0])
            value = statement.value
        elif isinstance(statement, ast.AnnAssign) and statement.value is not None:
            target = _target_key(statement.target)
            value = statement.value
        else:
            if any(_is_processing_call(node) for node in ast.walk(statement)):
                return None
            continue
        if target != merge_target or any(_is_processing_call(node) for node in ast.walk(value)):
            continue
        if _target_key(value) is None:
            return None
        references = _reference_keys(value)
        if len(references) != 1:
            return None
        matches.append(references)
    return matches[-1] if len(matches) == 1 else None


def _implicit_passthrough_source(
    merge_target: str,
    conditional: ast.If,
    scope: ast.AST,
    definitions: Sequence[tuple[ast.AST, int, str, ast.AST]],
) -> set[str] | None:
    candidates = [
        (line, value)
        for definition_scope, line, target, value in definitions
        if definition_scope is scope
        and target == merge_target
        and line < int(conditional.lineno)
        and not any(_is_processing_call(node) for node in ast.walk(value))
    ]
    if not candidates:
        return None
    references = _reference_keys(max(candidates, key=lambda item: item[0])[1])
    return references if len(references) == 1 else None


def _direct_processing_consumers(
    calls: Sequence[ast.Call],
    merge_target: str,
    *,
    after_line: int,
    parents: Mapping[ast.AST, ast.AST],
    definitions: Sequence[tuple[ast.AST, int, str, ast.AST]],
) -> list[ast.Call]:
    return [
        call
        for call in calls
        if int(call.lineno) > after_line
        and any(
            reference == merge_target or reference.startswith(merge_target + ".")
            for reference in _expanded_reference_keys(
                call,
                call=call,
                parents=dict(parents),
                definitions=list(definitions),
            )
        )
    ]


def _path_payloads(
    optional_groups: Sequence[Sequence[int]],
    mandatory_indices: Sequence[int],
    operator_ids: Sequence[str],
    dependency_edges: Sequence[Sequence[int]],
) -> list[dict[str, Any]]:
    payloads: list[dict[str, Any]] = []
    seen: set[tuple[int, ...]] = set()
    for decisions in itertools.product((True, False), repeat=len(optional_groups)):
        included = set(mandatory_indices)
        for enabled, group in zip(decisions, optional_groups, strict=True):
            if enabled:
                included.update(group)
        indices = tuple(sorted(included))
        if indices in seen:
            continue
        seen.add(indices)
        remap = {old: new for new, old in enumerate(indices)}
        original_edges = {
            (int(source), int(target))
            for source, target in dependency_edges
            if int(source) in included and int(target) in included
        }
        enabled_groups = [
            list(group)
            for enabled, group in zip(decisions, optional_groups, strict=True)
            if enabled
        ]
        for left, right in zip(enabled_groups, enabled_groups[1:]):
            original_edges.add((left[-1], right[0]))
        if enabled_groups and mandatory_indices:
            original_edges.add((enabled_groups[-1][-1], mandatory_indices[0]))
        edges = [
            [remap[source], remap[target]]
            for source, target in sorted(original_edges)
        ]
        payloads.append(
            {
                "call_indices": list(indices),
                "operator_ids": [operator_ids[index] for index in indices],
                "dependency_edges": edges,
            }
        )
    return payloads


def match_conditional_passthrough_paths(
    source_text: str, *, call_sites: Sequence[Mapping[str, Any]], max_paths: int = 64
) -> dict[str, Any]:
    """Match optional Processing producers that feed one unconditional consumer.

    The matcher is evidence-only. A match does not grant training admission.
    """

    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", SyntaxWarning)
            tree = ast.parse(source_text)
    except SyntaxError:
        return _result("deferred", reasons=["source_syntax_error"])

    parents = _parents(tree)
    literal_calls = sorted(
        (
            node
            for node in ast.walk(tree)
            if _is_processing_call(node) and _operator_id(node)
        ),
        key=lambda call: (call.lineno, call.col_offset),
    )
    aligned, alignment_reasons = _align_calls(literal_calls, call_sites)
    if alignment_reasons:
        return _result("deferred", reasons=alignment_reasons)
    if len(aligned) < 2:
        return _result("deferred", reasons=["fewer_than_two_processing_calls"])

    scopes = {_lexical_scope(call, parents) for call in aligned}
    if len(scopes) != 1:
        return _result("deferred", reasons=["cross_lexical_scope"])
    scope = next(iter(scopes))
    scope_calls = [
        call for call in literal_calls if _lexical_scope(call, parents) is scope
    ]
    call_index = {id(call): index for index, call in enumerate(aligned)}
    aligned_ids = set(call_index)

    reasons = _unsupported_control_flow(aligned, scope, parents)
    candidate_conditionals = sorted(
        {
            conditional
            for call in aligned
            for conditional in _ancestor_conditionals(call, scope, parents)
        },
        key=lambda node: (node.lineno, node.col_offset),
    )
    if not candidate_conditionals:
        reasons.append("no_conditional_processing_producer")
    if any(
        isinstance(node, (ast.Return, ast.Raise))
        and any(_is_descendant(node, conditional, parents) for conditional in candidate_conditionals)
        for node in ast.walk(scope)
    ):
        reasons.append("conditional_early_exit")

    definitions = _assignment_definitions(scope, parents)
    optional_groups: list[list[int]] = []
    merge_targets: list[str] = []
    last_conditional_end = 0
    for conditional in candidate_conditionals:
        last_conditional_end = max(
            last_conditional_end, int(conditional.end_lineno or conditional.lineno)
        )
        body_calls = [
            call for call in aligned if _branch(call, conditional, parents) == "body"
        ]
        else_calls = [
            call for call in aligned if _branch(call, conditional, parents) == "orelse"
        ]
        if body_calls and else_calls:
            reasons.append("processing_calls_in_both_branches")
            continue
        branch_calls = body_calls or else_calls
        if not branch_calls:
            continue
        active_statements = conditional.body if body_calls else conditional.orelse
        passive_statements = conditional.orelse if body_calls else conditional.body
        merge_target, first_call_references = _latest_alias_target(
            active_statements, branch_calls, parents, definitions
        )
        if not merge_target:
            reasons.append("conditional_producer_has_no_merge_target")
            continue
        if passive_statements:
            passthrough = _passthrough_source(passive_statements, merge_target)
        else:
            passthrough = _implicit_passthrough_source(
                merge_target, conditional, scope, definitions
            )
        if not passthrough:
            reasons.append("branch_is_not_original_input_passthrough")
            continue
        if not (
            passthrough & first_call_references
            or merge_target in first_call_references
            or any(ref.startswith(merge_target + ".") for ref in first_call_references)
        ):
            reasons.append("producer_does_not_consume_passthrough_input")
            continue
        group = sorted(call_index[id(call)] for call in branch_calls)
        optional_groups.append(group)
        merge_targets.append(merge_target)

    unique_merge_targets = sorted(set(merge_targets))
    if len(unique_merge_targets) > 1:
        reasons.append("multiple_merge_targets")

    common_consumers: list[ast.Call] = []
    if len(unique_merge_targets) == 1:
        common_consumers = _direct_processing_consumers(
            scope_calls,
            unique_merge_targets[0],
            after_line=last_conditional_end,
            parents=parents,
            definitions=definitions,
        )
        if len(common_consumers) != 1:
            reasons.append(
                "merge_target_has_multiple_processing_consumers"
                if len(common_consumers) > 1
                else "merge_target_has_no_common_processing_consumer"
            )

    if common_consumers and id(common_consumers[0]) not in aligned_ids:
        reasons.append("common_consumer_missing_from_call_sites")
    if len(unique_merge_targets) == 1 and common_consumers:
        consumer_line = int(common_consumers[0].lineno)
        if any(
            definition_scope is scope
            and target == unique_merge_targets[0]
            and last_conditional_end < line < consumer_line
            for definition_scope, line, target, _ in definitions
        ):
            reasons.append("merge_target_rebound_before_common_consumer")

    if candidate_conditionals:
        region_start = min(int(node.lineno) for node in candidate_conditionals)
        region_end = max(
            int(call.end_lineno or call.lineno) for call in aligned
        )
        if any(
            id(call) not in aligned_ids
            and region_start <= int(call.lineno) <= region_end
            for call in scope_calls
        ):
            reasons.append("unlisted_processing_call_in_region")

    low_level_roles = sorted(
        {
            node.func.attr
            for node in ast.walk(scope)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr in LOW_LEVEL_DATA_TRANSFORM_METHODS
            and int(node.lineno) >= min(
                (int(item.lineno) for item in candidate_conditionals), default=0
            )
        }
    )
    reasons.extend(f"low_level_data_transform:{role}" for role in low_level_roles)

    features = extract_conversion_features(source_text, call_sites=call_sites).data
    if features.get("provider_input_type_conflicts"):
        reasons.append("provider_input_type_conflict")
    if features.get("unresolved_output_references"):
        reasons.append("unresolved_output_reference")
    if features.get("processing_temporary_input_references"):
        reasons.append("processing_temporary_input_reference")
    if features.get("intermediate_data_transform_calls"):
        reasons.append("intermediate_data_transform")
    if features.get("downstream_data_transform_calls"):
        reasons.append("downstream_data_transform")

    if len(optional_groups) > 6 or 2 ** len(optional_groups) > max_paths:
        reasons.append("path_enumeration_limit_exceeded")
    if reasons:
        return _result(
            "deferred",
            reasons=reasons,
            merge_targets=unique_merge_targets,
            provider_input_type_status=features.get(
                "provider_input_type_status", "not_applicable"
            ),
        )

    consumer_index = call_index[id(common_consumers[0])]
    optional_indices = sorted({index for group in optional_groups for index in group})
    mandatory_indices = [
        index
        for index, call in enumerate(aligned)
        if index not in optional_indices
        and not _ancestor_conditionals(call, scope, parents)
        and index >= consumer_index
    ]
    if consumer_index not in mandatory_indices:
        return _result("deferred", reasons=["common_consumer_not_mandatory"])

    operator_ids = [_operator_id(call) or "" for call in aligned]
    dependency_edges = [
        [int(source), int(target)]
        for source, target in features.get("dependency_edges") or []
    ]
    paths = _path_payloads(
        optional_groups, mandatory_indices, operator_ids, dependency_edges
    )
    return _result(
        "matched",
        merge_targets=unique_merge_targets,
        optional_producer_indices=optional_indices,
        common_consumer_indices=[consumer_index],
        path_operator_ids=[path["operator_ids"] for path in paths],
        paths=paths,
        provider_input_type_status=features.get(
            "provider_input_type_status", "not_applicable"
        ),
        provider_input_type_checks=features.get("provider_input_type_checks") or [],
        provider_input_type_conflicts=[],
        training_admission="not_granted_rule_calibration_only",
        training_row_emitted=False,
        validation_eligible=False,
        test_eligible=False,
        production_merge="not_granted",
    )


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


def _call_site(call: ast.Call) -> dict[str, Any]:
    return {
        "operator_id": _operator_id(call) or "",
        "line_start": int(call.lineno),
        "line_end": int(call.end_lineno or call.lineno),
    }


def discover_conditional_passthrough_units(
    source_text: str,
    *,
    max_optional_conditionals: int = 6,
    max_scope_processing_calls: int = 24,
    max_scope_conditionals: int = 8,
) -> list[dict[str, Any]]:
    """Discover matched conditional-passthrough units without an external call list."""

    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", SyntaxWarning)
            tree = ast.parse(source_text)
    except SyntaxError:
        return []
    parents = _parents(tree)
    literal_calls = sorted(
        (
            node
            for node in ast.walk(tree)
            if _is_processing_call(node) and _operator_id(node)
        ),
        key=lambda call: (call.lineno, call.col_offset),
    )
    grouped: dict[ast.AST, list[ast.Call]] = {}
    for call in literal_calls:
        grouped.setdefault(_lexical_scope(call, parents), []).append(call)

    units: list[dict[str, Any]] = []
    seen: set[tuple[str, tuple[tuple[str, int], ...]]] = set()
    for scope, scope_calls in grouped.items():
        if not 2 <= len(scope_calls) <= max_scope_processing_calls:
            continue
        conditional_calls: dict[ast.If, list[ast.Call]] = {}
        for call in scope_calls:
            conditionals = _ancestor_conditionals(call, scope, parents)
            if conditionals:
                conditional_calls.setdefault(conditionals[-1], []).append(call)
        conditionals = sorted(
            conditional_calls, key=lambda node: (node.lineno, node.col_offset)
        )
        if len(conditionals) > max_scope_conditionals:
            continue
        consumers = [
            call
            for call in scope_calls
            if not _ancestor_conditionals(call, scope, parents)
        ]
        for consumer in consumers:
            prior_conditionals = [
                conditional
                for conditional in conditionals
                if int(conditional.end_lineno or conditional.lineno)
                < int(consumer.lineno)
            ]
            max_width = min(len(prior_conditionals), max_optional_conditionals)
            for width in range(max_width, 0, -1):
                window = prior_conditionals[-width:]
                branch_calls = sorted(
                    {
                        call
                        for conditional in window
                        for call in conditional_calls[conditional]
                    },
                    key=lambda call: (call.lineno, call.col_offset),
                )
                selected = sorted(
                    [*branch_calls, consumer],
                    key=lambda call: (call.lineno, call.col_offset),
                )
                call_sites = [_call_site(call) for call in selected]
                result = match_conditional_passthrough_paths(
                    source_text, call_sites=call_sites
                )
                if result["status"] != "matched":
                    continue
                name = _scope_name(scope, parents)
                key = (
                    name,
                    tuple(
                        (str(site["operator_id"]), int(site["line_start"]))
                        for site in call_sites
                    ),
                )
                if key not in seen:
                    seen.add(key)
                    units.append(
                        {
                            **result,
                            "lexical_scope": name,
                            "call_sites": call_sites,
                            "discovery_status": "matched_from_literal_scope_scan",
                        }
                    )
                break
    return sorted(
        units,
        key=lambda unit: (
            min(int(site["line_start"]) for site in unit["call_sites"]),
            unit["lexical_scope"],
        ),
    )
