#!/usr/bin/env python3
"""Discover source-backed QGIS API families after completed-family exclusion."""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import tempfile
from collections import Counter, defaultdict
from collections.abc import Iterable
from pathlib import Path
from typing import Any

SCHEMA = "gis_recommend.qgis_api_remaining_family_census.v1"
RULE_ID = "qgis-api-local-terminal-macro-census-v1"
FAMILY_CONTRACTS = {
    "raster_calculator": {
        "l3_code": "L3_03_03_A",
        "mapping_status": "exact_stable125",
        "semantic_contract": "evaluate a raster expression and write its raster result",
    },
    "raster_file_export": {
        "l3_code": None,
        "mapping_status": "stable125_contract_review_required",
        "semantic_contract": "write a raster pipe to a raster dataset",
    },
}


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _sha256(path: Path) -> str:
    return _sha256_bytes(path.read_bytes())


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


def _method(node: ast.Call) -> str:
    return _name(node.func).rsplit(".", 1)[-1].lower()


def _parents(tree: ast.AST) -> dict[ast.AST, ast.AST]:
    return {
        child: parent
        for parent in ast.walk(tree)
        for child in ast.iter_child_nodes(parent)
    }


def _scope(node: ast.AST, parents: dict[ast.AST, ast.AST]) -> ast.AST:
    current: ast.AST | None = node
    while current is not None:
        if isinstance(current, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)):
            return current
        current = parents.get(current)
    current = node
    while current in parents:
        current = parents[current]
    return current


def _scope_name(scope: ast.AST, parents: dict[ast.AST, ast.AST]) -> str:
    if isinstance(scope, ast.Module):
        return "<module>"
    names: list[str] = []
    current: ast.AST | None = scope
    while current is not None:
        if isinstance(current, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            names.append(current.name)
        elif isinstance(current, ast.Lambda):
            names.append(f"<lambda:{current.lineno}>")
        current = parents.get(current)
    return ".".join(reversed(names))


def _control_path(node: ast.AST, parents: dict[ast.AST, ast.AST]) -> tuple[str, ...]:
    path: list[str] = []
    current: ast.AST | None = node
    while current is not None:
        parent = parents.get(current)
        if isinstance(parent, ast.If):
            arm = "body" if current in parent.body else "orelse"
            path.append(f"if:{parent.lineno}:{arm}")
        current = parent
    return tuple(reversed(path))


def _control_paths_compatible(first: tuple[str, ...], second: tuple[str, ...]) -> bool:
    first_arms = {entry.rsplit(":", 1)[0]: entry.rsplit(":", 1)[1] for entry in first}
    second_arms = {
        entry.rsplit(":", 1)[0]: entry.rsplit(":", 1)[1] for entry in second
    }
    return all(
        first_arms[key] == second_arms[key]
        for key in first_arms.keys() & second_arms.keys()
    )


def _assignment_targets(call: ast.Call, parents: dict[ast.AST, ast.AST]) -> list[str]:
    current: ast.AST = call
    while isinstance(parents.get(current), (ast.Expr, ast.Tuple, ast.List)):
        current = parents[current]
    parent = parents.get(current)
    if isinstance(parent, ast.Assign) and parent.value is current:
        targets = parent.targets
    elif isinstance(parent, ast.AnnAssign) and parent.value is current or isinstance(parent, ast.NamedExpr) and parent.value is current:
        targets = [parent.target]
    else:
        return []
    return [
        item.id
        for target in targets
        for item in ast.walk(target)
        if isinstance(item, ast.Name) and isinstance(item.ctx, ast.Store)
    ]


def _stored_lines(scope: ast.AST, name: str, parents: dict[ast.AST, ast.AST]) -> list[int]:
    return sorted(
        int(node.lineno)
        for node in ast.walk(scope)
        if isinstance(node, ast.Name)
        and isinstance(node.ctx, ast.Store)
        and node.id == name
        and _scope(node, parents) is scope
    )


def _assignment_value(node: ast.AST) -> ast.AST | None:
    if isinstance(node, (ast.Assign, ast.AnnAssign, ast.NamedExpr)):
        return node.value
    return None


def _target_names(node: ast.AST) -> set[str]:
    if isinstance(node, ast.Assign):
        targets = node.targets
    elif isinstance(node, (ast.AnnAssign, ast.NamedExpr)):
        targets = [node.target]
    else:
        return set()
    return {
        item.id
        for target in targets
        for item in ast.walk(target)
        if isinstance(item, ast.Name) and isinstance(item.ctx, ast.Store)
    }


def _scope_parameters(scope: ast.AST) -> set[str]:
    if not isinstance(scope, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)):
        return set()
    return {
        argument.arg
        for argument in (
            *scope.args.posonlyargs,
            *scope.args.args,
            *scope.args.kwonlyargs,
        )
    }


def _reaching_values(
    scope: ast.AST,
    name: str,
    *,
    before_line: int,
    use_control_path: tuple[str, ...],
    parents: dict[ast.AST, ast.AST],
) -> list[tuple[int, ast.AST]]:
    definitions = sorted(
        (
            int(node.lineno),
            _control_path(node, parents),
            value,
        )
        for node in ast.walk(scope)
        if (value := _assignment_value(node)) is not None
        and name in _target_names(node)
        and int(node.lineno) < before_line
        and _scope(node, parents) is scope
        and _control_paths_compatible(_control_path(node, parents), use_control_path)
    )
    if not definitions:
        return []
    unconditional = [item for item in definitions if not item[1]]
    if unconditional:
        last_unconditional = unconditional[-1]
        later = [item for item in definitions if item[0] > last_unconditional[0]]
        selected = later or [last_unconditional]
    else:
        selected = definitions
    return [(line, value) for line, _, value in selected]


def _fact(
    node: ast.AST | None,
    *,
    scope: ast.AST | None = None,
    before_line: int = 0,
    use_control_path: tuple[str, ...] = (),
    parents: dict[ast.AST, ast.AST] | None = None,
    visited: frozenset[str] = frozenset(),
) -> dict[str, Any]:
    if node is None:
        return {"status": "missing", "source": ""}
    if (
        isinstance(node, ast.Name)
        and scope is not None
        and parents is not None
        and node.id not in visited
    ):
        reaching = _reaching_values(
            scope,
            node.id,
            before_line=before_line,
            use_control_path=use_control_path,
            parents=parents,
        )
        signatures = {ast.dump(value, include_attributes=False) for _, value in reaching}
        if len(signatures) == 1:
            definition_line, value = reaching[0]
            resolved = _fact(
                value,
                scope=scope,
                before_line=definition_line,
                use_control_path=use_control_path,
                parents=parents,
                visited=visited | {node.id},
            )
            return {
                **resolved,
                "resolved_from": node.id,
                "definition_lines": sorted(
                    {definition_line, *resolved.get("definition_lines", [])}
                ),
            }
        if len(signatures) > 1:
            return {
                "status": "ambiguous_reaching_definitions",
                "source": node.id,
                "definition_lines": sorted(line for line, _ in reaching),
            }
        if node.id in _scope_parameters(scope):
            return {"status": "parameter_reference", "source": node.id}
        return {"status": "unresolved_name_reference", "source": node.id}
    if isinstance(node, ast.Constant):
        return {"status": "literal", "value": node.value, "source": repr(node.value)}
    if isinstance(node, ast.JoinedStr):
        return {"status": "fstring", "source": ast.unparse(node)}
    if isinstance(node, ast.Call) and _method(node).startswith("parameteras"):
        return {"status": "processing_parameter", "source": ast.unparse(node)}
    if isinstance(node, ast.Name):
        return {"status": "unresolved_name_reference", "source": node.id}
    if isinstance(node, ast.Subscript):
        return {"status": "dynamic_subscript", "source": ast.unparse(node)}
    if isinstance(node, (ast.BinOp, ast.Call, ast.Attribute)):
        return {"status": "source_expression", "source": ast.unparse(node)}
    return {"status": "unsupported_expression", "source": ast.unparse(node)}


def _looks_like_transform_context(node: ast.AST) -> bool:
    source = ast.unparse(node).lower().replace("_", "")
    return "transformcontext" in source or source in {"context", "ctx"}


def _raster_calculator_arguments(call: ast.Call) -> dict[str, ast.AST | None]:
    values = {
        "expression": _call_argument(call, 0, {"formula", "formulastring"}),
        "output_path": _call_argument(call, 1, {"outputfile", "output_file"}),
        "output_format": _call_argument(call, 2, {"outputformat", "output_format"}),
        "extent": _call_argument(call, 3, {"outputextent", "output_extent"}),
        "output_crs": None,
        "columns": None,
        "rows": None,
        "entries": None,
        "transform_context": None,
    }
    tail = list(call.args[4:])
    if len(tail) == 3:
        values["columns"], values["rows"], values["entries"] = tail
    elif len(tail) == 4 and _looks_like_transform_context(tail[-1]):
        (
            values["columns"],
            values["rows"],
            values["entries"],
            values["transform_context"],
        ) = tail
    elif len(tail) == 4:
        (
            values["output_crs"],
            values["columns"],
            values["rows"],
            values["entries"],
        ) = tail
    elif len(tail) >= 5:
        (
            values["output_crs"],
            values["columns"],
            values["rows"],
            values["entries"],
            values["transform_context"],
        ) = tail[:5]
    keyword_aliases = {
        "output_crs": {"outputcrs", "output_crs"},
        "columns": {"noutputcolumns", "columns"},
        "rows": {"noutputrows", "rows"},
        "entries": {"rasterentries", "entries"},
        "transform_context": {"transformcontext", "transform_context"},
    }
    for field, aliases in keyword_aliases.items():
        if values[field] is None:
            values[field] = next(
                (
                    keyword.value
                    for keyword in call.keywords
                    if keyword.arg and keyword.arg.lower() in aliases
                ),
                None,
            )
    return values


def _call_argument(
    call: ast.Call,
    position: int,
    keyword_names: set[str],
) -> ast.AST | None:
    if position < len(call.args):
        return call.args[position]
    for keyword in call.keywords:
        if keyword.arg and keyword.arg.lower() in keyword_names:
            return keyword.value
    return None


def _base_unit(
    row: dict[str, Any],
    *,
    family_id: str,
    scope_name: str,
    start_line: int,
    end_line: int,
    status: str,
    reason: str,
) -> dict[str, Any]:
    contract = FAMILY_CONTRACTS[family_id]
    identity = {
        "source_authority_key": row.get("source_authority_key"),
        "family_id": family_id,
        "scope": scope_name,
        "start_line": start_line,
        "end_line": end_line,
    }
    return {
        "schema": SCHEMA,
        "family_rule_id": RULE_ID,
        "family_id": family_id,
        "semantic_contract": contract["semantic_contract"],
        "mapping_status": contract["mapping_status"],
        "candidate_l3_sequence": [contract["l3_code"]] if contract["l3_code"] else [],
        "unit_id": hashlib.sha256(
            json.dumps(identity, sort_keys=True).encode("utf-8")
        ).hexdigest(),
        "record_id": row.get("record_id"),
        "source_root_id": row.get("source_root_id"),
        "source_path": row.get("source_path"),
        "source_sha256": row.get("source_sha256"),
        "normalized_source_body_sha256": row.get("normalized_source_body_sha256"),
        "source_authority_key": row.get("source_authority_key"),
        "lexical_scope": scope_name,
        "source_span": [start_line, end_line],
        "macro_status": status,
        "deferred_reason": reason,
        "source_verification": "verified_sha256",
        "description_fidelity": "not_started",
        "deduplication": "not_started",
        "training_admission": "not_granted_family_census_only",
        "training_row_emitted": False,
        "validation_eligible": False,
        "test_eligible": False,
        "production_merge": "not_granted",
        "llm_called": False,
    }


def _raster_calculator_units(
    row: dict[str, Any], tree: ast.AST, parents: dict[ast.AST, ast.AST]
) -> list[dict[str, Any]]:
    units: list[dict[str, Any]] = []
    constructors = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and _method(node) == "qgsrastercalculator"
    ]
    for constructor in sorted(constructors, key=lambda node: (node.lineno, node.col_offset)):
        scope = _scope(constructor, parents)
        scope_name = _scope_name(scope, parents)
        targets = _assignment_targets(constructor, parents)
        if len(targets) != 1:
            units.append(
                _base_unit(
                    row,
                    family_id="raster_calculator",
                    scope_name=scope_name,
                    start_line=int(constructor.lineno),
                    end_line=int(constructor.end_lineno or constructor.lineno),
                    status="deferred",
                    reason="constructor_result_not_single_local_name",
                )
            )
            continue
        receiver = targets[0]
        terminal_calls = [
            node
            for node in ast.walk(scope)
            if isinstance(node, ast.Call)
            and _scope(node, parents) is scope
            and _method(node) == "processcalculation"
            and isinstance(node.func, ast.Attribute)
            and _name(node.func.value) == receiver
            and int(node.lineno) > int(constructor.lineno)
            and _control_paths_compatible(
                _control_path(constructor, parents), _control_path(node, parents)
            )
        ]
        if len(terminal_calls) != 1:
            reason = (
                "process_calculation_call_not_found"
                if not terminal_calls
                else "multiple_process_calculation_calls"
            )
            end_line = max(
                [int(constructor.end_lineno or constructor.lineno)]
                + [int(node.end_lineno or node.lineno) for node in terminal_calls]
            )
            units.append(
                _base_unit(
                    row,
                    family_id="raster_calculator",
                    scope_name=scope_name,
                    start_line=int(constructor.lineno),
                    end_line=end_line,
                    status="deferred",
                    reason=reason,
                )
            )
            continue
        terminal = terminal_calls[0]
        rebound = any(
            int(constructor.lineno) < line < int(terminal.lineno)
            for line in _stored_lines(scope, receiver, parents)
        )
        span = int(terminal.end_lineno or terminal.lineno) - int(constructor.lineno)
        arguments = _raster_calculator_arguments(constructor)
        required_argument_nodes = [
            arguments[field]
            for field in (
                "expression",
                "output_path",
                "output_format",
                "extent",
                "columns",
                "rows",
                "entries",
            )
        ]
        if rebound:
            reason = "calculator_receiver_rebound_before_terminal"
        elif span > 100:
            reason = "macro_span_exceeds_100_lines"
        elif any(node is None for node in required_argument_nodes):
            reason = "constructor_contract_incomplete"
        else:
            reason = ""
        unit = _base_unit(
            row,
            family_id="raster_calculator",
            scope_name=scope_name,
            start_line=int(constructor.lineno),
            end_line=int(terminal.end_lineno or terminal.lineno),
            status="complete" if not reason else "deferred",
            reason=reason,
        )
        fact_kwargs = {
            "scope": scope,
            "before_line": int(constructor.lineno),
            "use_control_path": _control_path(constructor, parents),
            "parents": parents,
        }
        facts = {
            "expression_fact": _fact(arguments["expression"], **fact_kwargs),
            "output_path_fact": _fact(arguments["output_path"], **fact_kwargs),
            "output_format_fact": _fact(arguments["output_format"], **fact_kwargs),
            "extent_fact": _fact(arguments["extent"], **fact_kwargs),
            "output_crs_fact": _fact(arguments["output_crs"], **fact_kwargs),
            "column_count_fact": _fact(arguments["columns"], **fact_kwargs),
            "row_count_fact": _fact(arguments["rows"], **fact_kwargs),
            "raster_entries_fact": _fact(arguments["entries"], **fact_kwargs),
            "transform_context_fact": _fact(
                arguments["transform_context"], **fact_kwargs
            ),
        }
        definition_lines = sorted(
            {
                int(line)
                for fact in facts.values()
                for line in fact.get("definition_lines", [])
            }
        )
        unit.update(
            {
                "constructor_call": _name(constructor.func),
                "terminal_call": _name(terminal.func),
                "receiver": receiver,
                "constructor_signature": (
                    "with_output_crs"
                    if arguments["output_crs"] is not None
                    else "without_output_crs"
                ),
                "evidence_span": [
                    min([int(constructor.lineno), *definition_lines]),
                    int(terminal.end_lineno or terminal.lineno),
                ],
                **facts,
            }
        )
        units.append(unit)
    return units


def _raster_export_units(
    row: dict[str, Any], tree: ast.AST, parents: dict[ast.AST, ast.AST]
) -> list[dict[str, Any]]:
    units: list[dict[str, Any]] = []
    terminals = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and _method(node) == "writeraster"
        and isinstance(node.func, ast.Attribute)
    ]
    for terminal in sorted(terminals, key=lambda node: (node.lineno, node.col_offset)):
        scope = _scope(terminal, parents)
        scope_name = _scope_name(scope, parents)
        receiver = _name(terminal.func.value)
        receiver_leaf = receiver.rsplit(".", 1)[-1]
        constructors = [
            node
            for node in ast.walk(scope)
            if isinstance(node, ast.Call)
            and _scope(node, parents) is scope
            and _method(node) == "qgsrasterfilewriter"
            and receiver_leaf in _assignment_targets(node, parents)
            and int(node.lineno) < int(terminal.lineno)
        ]
        constructor = max(constructors, key=lambda node: node.lineno) if constructors else None
        if constructor is None:
            reason = "writer_constructor_not_found"
            start_line = int(terminal.lineno)
        elif len(terminal.args) < 5:
            reason = "write_raster_contract_incomplete"
            start_line = int(constructor.lineno)
        elif int(terminal.end_lineno or terminal.lineno) - int(constructor.lineno) > 100:
            reason = "macro_span_exceeds_100_lines"
            start_line = int(constructor.lineno)
        else:
            reason = ""
            start_line = int(constructor.lineno)
        unit = _base_unit(
            row,
            family_id="raster_file_export",
            scope_name=scope_name,
            start_line=start_line,
            end_line=int(terminal.end_lineno or terminal.lineno),
            status="complete" if not reason else "deferred",
            reason=reason,
        )
        unit.update(
            {
                "constructor_call": _name(constructor.func) if constructor else "",
                "terminal_call": _name(terminal.func),
                "receiver": receiver,
                "output_path_fact": _fact(constructor.args[0] if constructor and constructor.args else None),
                "pipe_fact": _fact(terminal.args[0] if terminal.args else None),
            }
        )
        units.append(unit)
    return units


def analyze_source(
    row: dict[str, Any], source_text: str, *, source_bytes: bytes | None = None
) -> list[dict[str, Any]]:
    actual_sha = _sha256_bytes(
        source_bytes if source_bytes is not None else source_text.encode("utf-8")
    )
    if actual_sha != str(row.get("source_sha256") or ""):
        raise ValueError("source SHA mismatch")
    tree = ast.parse(source_text)
    parents = _parents(tree)
    units = [
        *_raster_calculator_units(row, tree, parents),
        *_raster_export_units(row, tree, parents),
    ]
    source_lines = source_text.splitlines()
    for unit in units:
        start_line, end_line = (
            int(value) for value in unit.get("evidence_span", unit["source_span"])
        )
        context_start = max(1, start_line - 3)
        context_end = min(len(source_lines), end_line + 3)
        snippet = "\n".join(
            f"{line_number} | {source_lines[line_number - 1]}"
            for line_number in range(context_start, context_end + 1)
        )
        unit["source_snippet"] = snippet
        unit["source_region_sha256"] = _sha256_bytes(snippet.encode("utf-8"))
    return units


def analyze_path(row: dict[str, Any]) -> list[dict[str, Any]]:
    source_path = Path(str(row.get("source_path") or ""))
    if not source_path.is_file():
        return [
            {
                **_base_unit(
                    row,
                    family_id="raster_calculator",
                    scope_name="",
                    start_line=0,
                    end_line=0,
                    status="deferred",
                    reason="source_file_missing",
                ),
                "source_verification": "source_file_missing",
            }
        ]
    payload = source_path.read_bytes()
    return analyze_source(
        row, payload.decode("utf-8-sig", errors="replace"), source_bytes=payload
    )


def _row_methods(row: dict[str, Any]) -> set[str]:
    return {
        str(step.get("name") or "").rsplit(".", 1)[-1].lower()
        for step in row.get("steps") or []
    }


def _candidate_source(row: dict[str, Any]) -> bool:
    methods = _row_methods(row)
    return bool({"qgsrastercalculator", "writeraster"}.intersection(methods))


def build_summary(
    units: list[dict[str, Any]],
    *,
    input_authorities: int,
    excluded_authorities: int,
    remaining_authorities: int,
    prefiltered_authorities: int,
    existing_train_authorities: set[str],
    minimum_support: int,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    family_rows: list[dict[str, Any]] = []
    priority: list[dict[str, Any]] = []
    for family_id, contract in FAMILY_CONTRACTS.items():
        rows = [row for row in units if row["family_id"] == family_id]
        complete = [row for row in rows if row["macro_status"] == "complete"]
        complete_authorities = {str(row["source_authority_key"]) for row in complete}
        net_new = complete_authorities - existing_train_authorities
        failure_counts = Counter(
            str(row["deferred_reason"])
            for row in rows
            if row["macro_status"] != "complete"
        )
        support_gate = (
            "eligible_for_source_disjoint_calibration"
            if contract["mapping_status"] == "exact_stable125"
            and len(net_new) >= minimum_support
            else "deferred"
        )
        family_rows.append(
            {
                "schema": "gis_recommend.qgis_api_remaining_family_summary.v1",
                "family_rule_id": RULE_ID,
                "family_id": family_id,
                "semantic_contract": contract["semantic_contract"],
                "mapping_status": contract["mapping_status"],
                "candidate_l3_sequence": [contract["l3_code"]] if contract["l3_code"] else [],
                "unit_count": len(rows),
                "complete_unit_count": len(complete),
                "complete_source_authority_count": len(complete_authorities),
                "existing_train_authority_overlap": len(
                    complete_authorities & existing_train_authorities
                ),
                "net_new_source_authority_count": len(net_new),
                "deferred_reason_counts": dict(sorted(failure_counts.items())),
                "minimum_support": minimum_support,
                "support_gate": support_gate,
                "training_admission": "not_granted_family_census_only",
                "training_rows_emitted": 0,
            }
        )
        if support_gate == "eligible_for_source_disjoint_calibration":
            priority.extend(
                row
                for row in complete
                if str(row["source_authority_key"]) in net_new
            )
    family_rows.sort(
        key=lambda row: (-int(row["net_new_source_authority_count"]), row["family_id"])
    )
    summary = {
        "schema": "gis_recommend.qgis_api_remaining_family_census_summary.v1",
        "family_rule_id": RULE_ID,
        "input_candidate_authorities": input_authorities,
        "excluded_completed_family_authorities": excluded_authorities,
        "remaining_candidate_authorities": remaining_authorities,
        "prefiltered_source_authorities": prefiltered_authorities,
        "source_verified_units": sum(
            row["source_verification"] == "verified_sha256" for row in units
        ),
        "source_failure_units": sum(
            row["source_verification"] != "verified_sha256" for row in units
        ),
        "priority_family_count": sum(
            row["support_gate"] == "eligible_for_source_disjoint_calibration"
            for row in family_rows
        ),
        "priority_population_units": len(priority),
        "minimum_support": minimum_support,
        "net_new_measure": "source_authority_potential_before_description_and_four_layer_dedup",
        "training_admission": "not_granted_family_census_only",
        "training_rows_emitted": 0,
        "validation_eligible": False,
        "test_eligible": False,
        "production_merge": "not_granted",
        "llm_called": False,
    }
    return family_rows, priority, summary


def select_source_disjoint_review(
    rows: list[dict[str, Any]],
    *,
    per_split: int,
    seed: int,
    max_units_per_source: int = 5,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    by_source: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        source_sha = str(row.get("source_sha256") or "")
        if not source_sha:
            raise ValueError("review row lacks source_sha256")
        by_source[source_sha].append(row)
    ordered = sorted(
        by_source.items(),
        key=lambda item: (
            -len(item[1]),
            hashlib.sha256(f"{seed}:{item[0]}".encode()).hexdigest(),
        ),
    )
    calibration: list[dict[str, Any]] = []
    holdout: list[dict[str, Any]] = []
    for _, source_rows in ordered:
        target = calibration if len(calibration) <= len(holdout) else holdout
        if len(target) >= per_split:
            target = holdout if target is calibration else calibration
        if len(target) >= per_split:
            continue
        ranked_rows = sorted(
            source_rows,
            key=lambda row: hashlib.sha256(
                f"{seed}:{row['unit_id']}".encode()
            ).hexdigest(),
        )
        available = per_split - len(target)
        for representative in ranked_rows[: min(max_units_per_source, available)]:
            target.append(
                {
                    **representative,
                    "review_split": (
                        "calibration" if target is calibration else "holdout"
                    ),
                    "human_boundary_decision": "",
                    "human_mapping_decision": "",
                    "human_description_fidelity": "",
                    "human_notes": "",
                    "training_admission": "not_granted_pending_source_review",
                }
            )
    if len(calibration) != per_split or len(holdout) != per_split:
        raise ValueError(
            f"insufficient source-disjoint review rows: calibration={len(calibration)}, "
            f"holdout={len(holdout)}, required={per_split}"
        )
    cal_sources = {row["source_sha256"] for row in calibration}
    hold_sources = {row["source_sha256"] for row in holdout}
    if cal_sources & hold_sources:
        raise ValueError("source SHA leakage between calibration and holdout")
    cal_authorities = {row["source_authority_key"] for row in calibration}
    hold_authorities = {row["source_authority_key"] for row in holdout}
    if cal_authorities & hold_authorities:
        raise ValueError("normalized-body leakage between calibration and holdout")
    return calibration, holdout


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    with path.open(encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def _atomic_write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "w", encoding="utf-8", newline="", dir=path.parent, delete=False
    ) as handle:
        handle.write(content)
        temporary = Path(handle.name)
    temporary.replace(path)


def _write_json(path: Path, value: Any) -> None:
    _atomic_write(path, json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n")


def _write_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> None:
    _atomic_write(
        path,
        "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows),
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidates", type=Path, required=True)
    parser.add_argument("--exclude-jsonl", type=Path, action="append", default=[])
    parser.add_argument("--existing-train-jsonl", type=Path, action="append", default=[])
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--expected-input-authorities", type=int, default=12949)
    parser.add_argument("--expected-excluded-authorities", type=int, default=324)
    parser.add_argument("--expected-remaining-authorities", type=int, default=12625)
    parser.add_argument("--minimum-support", type=int, default=30)
    parser.add_argument("--review-per-split", type=int, default=20)
    parser.add_argument("--seed", type=int, default=20260805)
    args = parser.parse_args()
    if args.output_dir.exists() and any(args.output_dir.iterdir()):
        raise ValueError(f"output directory is not empty: {args.output_dir}")

    rows = _read_jsonl(args.candidates)
    if len(rows) != args.expected_input_authorities:
        raise ValueError(
            f"expected {args.expected_input_authorities} candidate authorities, got {len(rows)}"
        )
    excluded = {
        str(row.get("source_authority_key") or "")
        for path in args.exclude_jsonl
        for row in _read_jsonl(path)
        if row.get("source_authority_key")
    }
    if len(excluded) != args.expected_excluded_authorities:
        raise ValueError(
            f"expected {args.expected_excluded_authorities} excluded authorities, got {len(excluded)}"
        )
    remaining = [
        row for row in rows if str(row.get("source_authority_key") or "") not in excluded
    ]
    if len(remaining) != args.expected_remaining_authorities:
        raise ValueError(
            f"expected {args.expected_remaining_authorities} remaining authorities, got {len(remaining)}"
        )
    prefiltered = [row for row in remaining if _candidate_source(row)]
    units = [unit for row in prefiltered for unit in analyze_path(row)]
    existing_train_authorities = {
        str(row.get("source_authority_key") or "")
        for path in args.existing_train_jsonl
        for row in _read_jsonl(path)
        if row.get("source_authority_key")
    }
    family_rows, priority, summary = build_summary(
        units,
        input_authorities=len(rows),
        excluded_authorities=len(excluded),
        remaining_authorities=len(remaining),
        prefiltered_authorities=len(prefiltered),
        existing_train_authorities=existing_train_authorities,
        minimum_support=args.minimum_support,
    )
    calibration: list[dict[str, Any]] = []
    holdout: list[dict[str, Any]] = []
    if priority:
        calibration, holdout = select_source_disjoint_review(
            priority, per_split=args.review_per_split, seed=args.seed
        )
    summary.update(
        {
            "review_seed": args.seed,
            "calibration_rows": len(calibration),
            "holdout_rows": len(holdout),
            "calibration_holdout_source_sha_overlap": 0,
            "calibration_holdout_source_authority_overlap": 0,
        }
    )

    args.output_dir.mkdir(parents=True, exist_ok=True)
    artifacts = {
        "family_census_v1.jsonl": family_rows,
        "source_replay_v1.jsonl": units,
        "priority_population_v1.jsonl": priority,
        "calibration_review_v1.jsonl": calibration,
        "holdout_review_v1.jsonl": holdout,
    }
    paths: list[Path] = []
    for name, values in artifacts.items():
        path = args.output_dir / name
        _write_jsonl(path, values)
        paths.append(path)
    summary_path = args.output_dir / "summary_v1.json"
    _write_json(summary_path, summary)
    paths.append(summary_path)
    ledger = {
        "schema": "gis_recommend.hash_ledger.v1",
        "inputs": {
            "candidates": {"path": str(args.candidates), "sha256": _sha256(args.candidates)},
            **{
                f"exclude_{index}": {"path": str(path), "sha256": _sha256(path)}
                for index, path in enumerate(args.exclude_jsonl)
            },
            **{
                f"existing_train_{index}": {"path": str(path), "sha256": _sha256(path)}
                for index, path in enumerate(args.existing_train_jsonl)
            },
        },
        "artifacts": {
            path.name: {"bytes": path.stat().st_size, "sha256": _sha256(path)}
            for path in paths
        },
    }
    _write_json(args.output_dir / "hash_ledger_v1.json", ledger)
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
