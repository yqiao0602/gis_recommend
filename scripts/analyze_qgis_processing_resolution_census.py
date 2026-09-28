#!/usr/bin/env python3
"""Analyze every source in the QGIS Processing-resolution authority pool."""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import tempfile
import warnings
from collections import Counter, defaultdict
from collections.abc import Iterable
from pathlib import Path
from typing import Any

SCHEMA = "gis_recommend.qgis_processing_resolution_census.v2"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _load_jsonl(path: Path) -> Iterable[dict[str, Any]]:
    with path.open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            value = json.loads(line)
            if not isinstance(value, dict):
                raise TypeError(f"expected JSON object at {path}:{line_number}")
            yield value


def _parents(tree: ast.AST) -> dict[ast.AST, ast.AST]:
    return {child: node for node in ast.walk(tree) for child in ast.iter_child_nodes(node)}


def _scope(node: ast.AST, parents: dict[ast.AST, ast.AST]) -> ast.AST:
    current = node
    while current in parents:
        current = parents[current]
        if isinstance(current, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)):
            return current
    return tree_root(node, parents)


def tree_root(node: ast.AST, parents: dict[ast.AST, ast.AST]) -> ast.AST:
    while node in parents:
        node = parents[node]
    return node


def _scope_name(scope: ast.AST, parents: dict[ast.AST, ast.AST]) -> str:
    if isinstance(scope, ast.Module):
        return "<module>"
    parts: list[str] = []
    current: ast.AST | None = scope
    while current is not None:
        if isinstance(current, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            parts.append(current.name)
        current = parents.get(current)
    return ".".join(reversed(parts)) or "<scope>"


def _dotted_name(node: ast.AST) -> str | None:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        prefix = _dotted_name(node.value)
        return f"{prefix}.{node.attr}" if prefix else node.attr
    if isinstance(node, ast.Call) and not node.args and not node.keywords:
        return _dotted_name(node.func)
    return None


def _target_names(target: ast.AST) -> set[str]:
    if isinstance(target, ast.Name):
        return {target.id}
    if isinstance(target, (ast.Tuple, ast.List)):
        return {name for item in target.elts for name in _target_names(item)}
    return set()


def _assignment_definitions(
    tree: ast.AST, parents: dict[ast.AST, ast.AST]
) -> dict[tuple[ast.AST, str], list[tuple[int, ast.AST]]]:
    definitions: dict[tuple[ast.AST, str], list[tuple[int, ast.AST]]] = defaultdict(list)
    for node in ast.walk(tree):
        values: list[tuple[ast.AST, ast.AST]] = []
        if isinstance(node, ast.Assign):
            values.extend((target, node.value) for target in node.targets)
        elif isinstance(node, ast.AnnAssign) and node.value is not None:
            values.append((node.target, node.value))
        for target, value in values:
            for name in _target_names(target):
                definitions[(_scope(node, parents), name)].append((node.lineno, value))
    for entries in definitions.values():
        entries.sort(key=lambda item: item[0])
    return definitions


def _visible_definition(
    name: str,
    *,
    node: ast.AST,
    parents: dict[ast.AST, ast.AST],
    definitions: dict[tuple[ast.AST, str], list[tuple[int, ast.AST]]],
) -> ast.AST | None:
    line = int(getattr(node, "lineno", 10**12))
    current_scope = _scope(node, parents)
    root = tree_root(node, parents)
    for candidate_scope in (current_scope, root):
        candidates = [
            value
            for definition_line, value in definitions.get((candidate_scope, name), [])
            if definition_line < line
        ]
        if candidates:
            return candidates[-1]
    return None


def _algorithm_by_id_expression(node: ast.AST | None) -> ast.AST | None:
    if not isinstance(node, ast.Call) or not node.args:
        return None
    if not isinstance(node.func, ast.Attribute) or node.func.attr != "algorithmById":
        return None
    if _dotted_name(node.func.value) != "QgsApplication.processingRegistry":
        return None
    return node.args[0]


def _processing_operator_expression(
    call: ast.Call,
    *,
    parents: dict[ast.AST, ast.AST],
    definitions: dict[tuple[ast.AST, str], list[tuple[int, ast.AST]]],
) -> ast.AST | None:
    if not isinstance(call.func, ast.Attribute) or call.func.attr != "run":
        return None
    receiver = call.func.value
    if _dotted_name(receiver) in {"processing", "qgis.processing"}:
        return call.args[0] if call.args else None

    direct_expression = _algorithm_by_id_expression(receiver)
    if direct_expression is not None:
        return direct_expression

    if isinstance(receiver, ast.Name):
        definition = _visible_definition(
            receiver.id,
            node=call,
            parents=parents,
            definitions=definitions,
        )
        return _algorithm_by_id_expression(definition)
    return None


def _is_direct_processing_call(call: ast.Call) -> bool:
    return (
        isinstance(call.func, ast.Attribute)
        and call.func.attr == "run"
        and _dotted_name(call.func.value) in {"processing", "qgis.processing"}
    )


def _is_processing_call(call: ast.AST) -> bool:
    """Compatibility predicate for direct ``processing.run`` recovery users.

    Registry and wrapper invocation need their surrounding lexical context to
    resolve, so they are intentionally handled by ``_processing_operator_expression``
    instead of this context-free predicate.
    """

    return isinstance(call, ast.Call) and bool(call.args) and _is_direct_processing_call(call)


def _static_bool(
    node: ast.AST,
    *,
    context: ast.AST,
    parents: dict[ast.AST, ast.AST],
    definitions: dict[tuple[ast.AST, str], list[tuple[int, ast.AST]]],
    seen: set[tuple[int, str]] | None = None,
) -> bool | None:
    """Resolve only a source-proven Boolean value used for an ``IfExp`` guard."""

    seen = set() if seen is None else set(seen)
    if isinstance(node, ast.Constant) and isinstance(node.value, bool):
        return node.value
    if isinstance(node, ast.Name):
        marker = (id(_scope(context, parents)), node.id)
        if marker in seen:
            return None
        value = _visible_definition(
            node.id, node=context, parents=parents, definitions=definitions
        )
        if value is None:
            return None
        seen.add(marker)
        return _static_bool(
            value,
            context=context,
            parents=parents,
            definitions=definitions,
            seen=seen,
        )
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.Not):
        value = _static_bool(
            node.operand,
            context=context,
            parents=parents,
            definitions=definitions,
            seen=seen,
        )
        return None if value is None else not value
    return None


def _static_strings(
    node: ast.AST,
    *,
    context: ast.AST,
    parents: dict[ast.AST, ast.AST],
    definitions: dict[tuple[ast.AST, str], list[tuple[int, ast.AST]]],
    seen: set[tuple[int, str]] | None = None,
) -> set[str] | None:
    seen = set() if seen is None else set(seen)
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return {node.value} if node.value.strip() else None
    if isinstance(node, ast.Name):
        marker = (id(_scope(context, parents)), node.id)
        if marker in seen:
            return None
        value = _visible_definition(
            node.id, node=context, parents=parents, definitions=definitions
        )
        if value is None:
            return None
        seen.add(marker)
        return _static_strings(
            value,
            context=context,
            parents=parents,
            definitions=definitions,
            seen=seen,
        )
    if isinstance(node, ast.IfExp):
        condition = _static_bool(
            node.test,
            context=context,
            parents=parents,
            definitions=definitions,
            seen=seen,
        )
        if condition is not None:
            return _static_strings(
                node.body if condition else node.orelse,
                context=context,
                parents=parents,
                definitions=definitions,
                seen=seen,
            )
        # A runtime guard has more than one possible operator.  Preserve both
        # possibilities so the recovery driver defers it as a branch instead
        # of silently choosing one.
        body = _static_strings(
            node.body,
            context=context,
            parents=parents,
            definitions=definitions,
            seen=seen,
        )
        other = _static_strings(
            node.orelse,
            context=context,
            parents=parents,
            definitions=definitions,
            seen=seen,
        )
        return body | other if body and other else None
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
        left = _static_strings(
            node.left,
            context=context,
            parents=parents,
            definitions=definitions,
            seen=seen,
        )
        right = _static_strings(
            node.right,
            context=context,
            parents=parents,
            definitions=definitions,
            seen=seen,
        )
        if not left or not right or len(left) * len(right) > 32:
            return None
        return {a + b for a in left for b in right}
    if isinstance(node, ast.JoinedStr):
        values: set[str] = {""}
        for part in node.values:
            if isinstance(part, ast.Constant) and isinstance(part.value, str):
                candidates = {part.value}
            elif isinstance(part, ast.FormattedValue):
                candidates = _static_strings(
                    part.value,
                    context=context,
                    parents=parents,
                    definitions=definitions,
                    seen=seen,
                )
            else:
                candidates = None
            if not candidates or len(values) * len(candidates) > 32:
                return None
            values = {a + b for a in values for b in candidates}
        return values
    if isinstance(node, (ast.List, ast.Tuple, ast.Set)):
        values: set[str] = set()
        for item in node.elts:
            resolved = _static_strings(
                item,
                context=context,
                parents=parents,
                definitions=definitions,
                seen=seen,
            )
            if not resolved:
                return None
            values.update(resolved)
        return values or None
    if isinstance(node, ast.Subscript):
        container = node.value
        if isinstance(container, ast.Name):
            definition = _visible_definition(
                container.id,
                node=context,
                parents=parents,
                definitions=definitions,
            )
            if definition is not None:
                container = definition
        key = node.slice.value if isinstance(node.slice, ast.Constant) else None
        if isinstance(container, ast.Dict) and key is not None:
            for item_key, item_value in zip(container.keys, container.values):
                if isinstance(item_key, ast.Constant) and item_key.value == key:
                    return _static_strings(
                        item_value,
                        context=context,
                        parents=parents,
                        definitions=definitions,
                        seen=seen,
                    )
        # A numeric literal index into a literal list or tuple is as static as
        # a literal dictionary key.  Slices, negative indexes, and every
        # non-literal container remain unresolved to avoid guessing a runtime
        # operator selection.
        if (
            isinstance(container, (ast.List, ast.Tuple))
            and isinstance(key, int)
            and not isinstance(key, bool)
            and 0 <= key < len(container.elts)
        ):
            return _static_strings(
                container.elts[key],
                context=context,
                parents=parents,
                definitions=definitions,
                seen=seen,
            )
    return None


def _assigned_name(call: ast.Call, parents: dict[ast.AST, ast.AST]) -> str | None:
    current: ast.AST = call
    parent = parents.get(current)
    if isinstance(parent, ast.Subscript):
        current = parent
        parent = parents.get(current)
    if isinstance(parent, ast.Assign):
        names = {name for target in parent.targets for name in _target_names(target)}
        return next(iter(names)) if len(names) == 1 else None
    if isinstance(parent, ast.AnnAssign):
        names = _target_names(parent.target)
        return next(iter(names)) if len(names) == 1 else None
    return None


def _contains_output_alias(
    call: ast.Call,
    *,
    tree: ast.AST,
    parents: dict[ast.AST, ast.AST],
) -> bool:
    if isinstance(parents.get(call), ast.Subscript):
        return True
    target = _assigned_name(call, parents)
    if not target:
        return False
    call_scope = _scope(call, parents)
    for node in ast.walk(tree):
        if not isinstance(node, ast.Subscript) or node.lineno <= call.lineno:
            continue
        if _scope(node, parents) is not call_scope:
            continue
        if isinstance(node.value, ast.Name) and node.value.id == target:
            return True
    return False


def _is_processing_algorithm_class(node: ast.ClassDef) -> bool:
    for base in node.bases:
        if isinstance(base, ast.Name) and base.id == "QgsProcessingAlgorithm":
            return True
        if isinstance(base, ast.Attribute) and base.attr == "QgsProcessingAlgorithm":
            return True
    return False


def analyze_source(source_text: str) -> dict[str, Any]:
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", SyntaxWarning)
        tree = ast.parse(source_text)
    parents = _parents(tree)
    definitions = _assignment_definitions(tree, parents)
    processing_calls = [
        (
            node,
            _processing_operator_expression(
                node,
                parents=parents,
                definitions=definitions,
            ),
        )
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
    ]
    processing_calls = [row for row in processing_calls if row[1] is not None]
    processing_calls.sort(key=lambda row: (row[0].lineno, row[0].col_offset))
    calls = [call for call, _ in processing_calls]
    operator_expressions = {
        id(call): expression for call, expression in processing_calls
    }
    dynamic_evidence: list[dict[str, Any]] = []
    literal_ids: list[str] = []
    for call in calls:
        expression = operator_expressions[id(call)]
        if (
            isinstance(expression, ast.Constant)
            and isinstance(expression.value, str)
            and expression.value.strip()
        ):
            literal_ids.append(expression.value.strip())
            continue
        resolved = _static_strings(
            expression,
            context=call,
            parents=parents,
            definitions=definitions,
        )
        operator_ids = sorted(
            value.strip() for value in (resolved or set()) if value.strip()
        )
        dynamic_evidence.append(
            {
                "line": call.lineno,
                "expression_kind": type(expression).__name__,
                "expression": ast.unparse(expression),
                "status": "resolved_static_candidates" if operator_ids else "unresolved",
                "operator_ids": operator_ids,
            }
        )

    processing_scopes = {_scope(call, parents) for call in calls}
    processing_functions = {
        node.name: node
        for node in processing_scopes
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }
    helper_edges: set[tuple[str, str]] = set()
    for caller_name, caller in processing_functions.items():
        for node in ast.walk(caller):
            if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Name):
                continue
            if node.func.id in processing_functions and node.func.id != caller_name:
                helper_edges.add((caller_name, node.func.id))

    algorithm_classes = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.ClassDef) and _is_processing_algorithm_class(node)
    ]
    process_methods = [
        child
        for algorithm_class in algorithm_classes
        for child in algorithm_class.body
        if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef))
        and child.name == "processAlgorithm"
    ]
    custom_calls = [
        call
        for method in process_methods
        for call in ast.walk(method)
        if id(call) in operator_expressions
    ]
    custom_literal_calls = [
        call
        for call in custom_calls
        if isinstance(operator_expressions[id(call)], ast.Constant)
        and isinstance(operator_expressions[id(call)].value, str)
        and operator_expressions[id(call)].value.strip()
    ]
    resolved_dynamic = [row for row in dynamic_evidence if row["operator_ids"]]
    resolved_ids = sorted(
        {operator_id for row in resolved_dynamic for operator_id in row["operator_ids"]}
    )
    return {
        "parse_status": "parsed",
        "processing_call_count": len(calls),
        "literal_processing_call_count": len(literal_ids),
        "literal_operator_ids": literal_ids,
        "dynamic_processing_call_count": len(dynamic_evidence),
        "resolved_dynamic_call_count": len(resolved_dynamic),
        "unresolved_dynamic_call_count": len(dynamic_evidence) - len(resolved_dynamic),
        "resolved_dynamic_operator_ids": resolved_ids,
        "dynamic_call_evidence": dynamic_evidence,
        "processing_scope_count": len(processing_scopes),
        "processing_scopes": sorted(
            _scope_name(scope, parents) for scope in processing_scopes
        ),
        "helper_edge_count": len(helper_edges),
        "helper_edges": [list(edge) for edge in sorted(helper_edges)],
        "has_cross_function_processing_flow": bool(helper_edges),
        "parameter_dict_name_call_count": sum(
            _is_direct_processing_call(call)
            and len(call.args) >= 2
            and isinstance(call.args[1], ast.Name)
            for call in calls
        ),
        "output_alias_call_count": sum(
            _contains_output_alias(call, tree=tree, parents=parents) for call in calls
        ),
        "processing_algorithm_class_count": len(algorithm_classes),
        "process_algorithm_method_count": len(process_methods),
        "custom_embedded_processing_call_count": len(custom_calls),
        "custom_embedded_literal_processing_call_count": len(custom_literal_calls),
        "custom_embedded_multistep": len(custom_calls) >= 2,
    }


def _source_key(record: dict[str, Any]) -> tuple[str, str, str]:
    canonical = record.get("canonical_source") or record
    return (
        str(record.get("content_sha256") or ""),
        str(canonical.get("source_root_id") or ""),
        str(canonical.get("relative_path") or ""),
    )


def build_census(
    layered_path: Path, manifest_path: Path
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    manifest = {_source_key(row): row for row in _load_jsonl(manifest_path)}
    inputs = [
        row
        for row in _load_jsonl(layered_path)
        if row.get("broad_bucket") == "processing_needs_resolution"
    ]
    rows: list[dict[str, Any]] = []
    failures: list[dict[str, str]] = []
    for record in inputs:
        key = _source_key(record)
        source = manifest.get(key)
        if source is None:
            failures.append({"content_sha256": key[0], "reason": "manifest_join_missing"})
            continue
        source_path = Path(str(source.get("source_path") or ""))
        if not source_path.is_file():
            failures.append({"content_sha256": key[0], "reason": "source_file_missing"})
            continue
        if _sha256(source_path) != key[0]:
            failures.append({"content_sha256": key[0], "reason": "source_sha256_mismatch"})
            continue
        try:
            evidence = analyze_source(
                source_path.read_text(encoding="utf-8-sig", errors="replace")
            )
        except SyntaxError:
            failures.append({"content_sha256": key[0], "reason": "source_parse_failed"})
            continue
        rows.append(
            {
                "schema": SCHEMA,
                "content_sha256": key[0],
                "source_root_id": key[1],
                "relative_path": key[2],
                "source_path": str(source_path),
                "primary_layer": record.get("primary_layer"),
                "catalog_miss_ids": record.get("catalog_miss_ids") or [],
                "screening_literal_operator_ids": record.get("literal_operator_ids") or [],
                "is_processing_algorithm": bool(record.get("is_processing_algorithm")),
                **evidence,
                "training_admission": "not_granted_census_only",
                "training_row_emitted": False,
            }
        )

    layers = Counter(str(row["primary_layer"]) for row in rows)
    dynamic_rows = [
        row for row in rows if row["primary_layer"] == "dynamic_or_blank_processing_id"
    ]
    catalog_rows = [
        row for row in rows if row["primary_layer"] == "explicit_processing_catalog_miss"
    ]
    custom_rows = [
        row
        for row in rows
        if row["primary_layer"]
        == "processing_algorithm_implementation_or_custom"
    ]
    fully_resolved = [
        row
        for row in dynamic_rows
        if row["dynamic_processing_call_count"] > 0
        and row["unresolved_dynamic_call_count"] == 0
    ]
    partially_resolved = [
        row
        for row in dynamic_rows
        if row["resolved_dynamic_call_count"] > 0
        and row["unresolved_dynamic_call_count"] > 0
    ]
    opportunities = {
        "dynamic_id_fully_resolved": len(fully_resolved),
        "dynamic_id_partially_resolved": len(partially_resolved),
        "helper_cross_function": sum(
            bool(row["has_cross_function_processing_flow"]) for row in rows
        ),
        "output_alias": sum(row["output_alias_call_count"] > 0 for row in rows),
        "parameter_dict_name": sum(
            row["parameter_dict_name_call_count"] > 0 for row in rows
        ),
        "custom_embedded_multistep": sum(
            bool(row["custom_embedded_multistep"]) for row in custom_rows
        ),
    }
    summary = {
        "schema": f"{SCHEMA}.summary",
        "input_processing_resolution_records": len(inputs),
        "verified_source_records": len(rows),
        "primary_layer_counts": dict(sorted(layers.items())),
        "source_failures": failures,
        "catalog_miss": {
            "records": len(catalog_rows),
            "unique_operator_ids": len(
                {
                    operator_id
                    for row in catalog_rows
                    for operator_id in row["catalog_miss_ids"]
                }
            ),
        },
        "dynamic_resolution": {
            "records": len(dynamic_rows),
            "fully_resolved_records": len(fully_resolved),
            "partially_resolved_records": len(partially_resolved),
            "unresolved_records": len(dynamic_rows)
            - len(fully_resolved)
            - len(partially_resolved),
            "resolved_calls": sum(
                row["resolved_dynamic_call_count"] for row in dynamic_rows
            ),
            "unresolved_calls": sum(
                row["unresolved_dynamic_call_count"] for row in dynamic_rows
            ),
        },
        "custom_algorithm": {
            "records": len(custom_rows),
            "with_process_algorithm": sum(
                row["process_algorithm_method_count"] > 0 for row in custom_rows
            ),
            "with_embedded_processing": sum(
                row["custom_embedded_processing_call_count"] > 0
                for row in custom_rows
            ),
            "with_embedded_multistep": opportunities["custom_embedded_multistep"],
        },
        "recovery_opportunity_records": opportunities,
        "decision": {
            "training_admission": "not_granted_census_only",
            "next_gate": "implement highest-coverage source-backed recovery family",
        },
    }
    return rows, summary


def _atomic_write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "w", encoding="utf-8", newline="", dir=path.parent, delete=False
    ) as handle:
        handle.write(text)
        temporary = Path(handle.name)
    temporary.replace(path)


def write_outputs(
    rows: list[dict[str, Any]],
    summary: dict[str, Any],
    *,
    layered_path: Path,
    manifest_path: Path,
    output_dir: Path,
) -> None:
    ledger_path = output_dir / "resolution_census_v2.jsonl"
    summary_path = output_dir / "summary_v2.json"
    report_path = output_dir / "report_v2.md"
    hash_path = output_dir / "hash_ledger_v2.json"
    _atomic_write(
        ledger_path,
        "".join(
            json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
            + "\n"
            for row in rows
        ),
    )
    _atomic_write(
        summary_path,
        json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
    )
    opportunities = summary["recovery_opportunity_records"]
    report = [
        "# QGIS Processing Resolution Census v2",
        "",
        f"- Input records: {summary['input_processing_resolution_records']}",
        f"- Verified sources: {summary['verified_source_records']}",
        f"- Source failures: {len(summary['source_failures'])}",
        "- Training rows emitted: 0",
        "",
        "## Recovery Opportunities",
        "",
        "| Pattern | Independent source records |",
        "|---|---:|",
        *[f"| {name} | {count} |" for name, count in opportunities.items()],
        "",
    ]
    _atomic_write(report_path, "\n".join(report))
    hashes = {
        "schema": "gis_recommend.hash_ledger.v2",
        "source_inputs": {
            layered_path.name: _sha256(layered_path),
            manifest_path.name: _sha256(manifest_path),
        },
        "artifacts": {
            path.name: _sha256(path)
            for path in (ledger_path, summary_path, report_path)
        },
    }
    _atomic_write(
        hash_path,
        json.dumps(hashes, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--layered-content", type=Path, required=True)
    parser.add_argument("--corpus-manifest", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args(argv)
    if args.output_dir.exists() and any(args.output_dir.iterdir()):
        raise ValueError(f"output directory is not empty: {args.output_dir}")
    rows, summary = build_census(args.layered_content, args.corpus_manifest)
    write_outputs(
        rows,
        summary,
        layered_path=args.layered_content,
        manifest_path=args.corpus_manifest,
        output_dir=args.output_dir,
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
