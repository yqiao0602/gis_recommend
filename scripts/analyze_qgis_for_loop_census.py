#!/usr/bin/env python3
"""Census QGIS Processing calls enclosed by ``for`` loops.

The output is a source-backed structural census only.  It never emits training
rows and deliberately keeps dynamic iteration and loop-carried state closed.
"""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import tempfile
import warnings
from collections import Counter
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

ROOT = Path(__file__).resolve().parents[1]
import sys

sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from gis_recommend.data.qgis_conversion_features import (  # noqa: E402
    _is_processing_call,
    _operator_id,
)
from gis_recommend.data.qgis_source_authority import source_authority  # noqa: E402
from gis_recommend.data.qgis_subworkflow_splitter import (  # noqa: E402
    literalize_processing_operator_ids,
)


DEFAULT_MANIFEST = Path(
    "/home/qy/system_redesign/diagnostics/qgis_legacy_provider_recovery_v2/"
    "l3_gate_v3/l3_gated_manifest_v1.jsonl"
)
DEFAULT_FAMILY_CENSUS = Path(
    "/home/qy/system_redesign/diagnostics/qgis_legacy_provider_recovery_v2/"
    "mapped_recovery_split_family_census_v2/family_census_v1.jsonl"
)
DEFAULT_OUTPUT_DIR = Path(
    "/home/qy/system_redesign/diagnostics/qgis_legacy_provider_recovery_v2/"
    "qgis_for_loop_census_v3"
)
SUPPORTED_ACTIONS = {"recover_call_graph", "split_subworkflow"}
MAX_SMALL_ITERATIONS = 10


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def join_for_loop_inputs(
    manifest_rows: Sequence[Mapping[str, Any]],
    family_rows: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    selected: dict[str, Mapping[str, Any]] = {}
    for row in family_rows:
        if "control_flow:for" not in (row.get("blocker_reasons") or []):
            continue
        record_id = str(row.get("record_id") or "")
        if not record_id:
            raise ValueError("family census row has no record_id")
        if record_id in selected:
            raise ValueError(f"duplicate family census record_id:{record_id}")
        selected[record_id] = row
    manifest_by_id: dict[str, Mapping[str, Any]] = {}
    for row in manifest_rows:
        record_id = str(row.get("record_id") or "")
        if record_id not in selected:
            continue
        if record_id in manifest_by_id:
            raise ValueError(f"duplicate manifest record_id:{record_id}")
        manifest_by_id[record_id] = row
    missing = sorted(set(selected) - set(manifest_by_id))
    if missing:
        raise ValueError(f"family census record_ids missing from manifest:{len(missing)}")
    joined: list[dict[str, Any]] = []
    for record_id in sorted(selected):
        family = selected[record_id]
        row = dict(manifest_by_id[record_id])
        row["blocker_reasons"] = list(family.get("blocker_reasons") or [])
        row["family_source_authority_key"] = family.get("source_authority_key")
        joined.append(row)
    return joined


def _parents(tree: ast.AST) -> dict[ast.AST, ast.AST]:
    parents: dict[ast.AST, ast.AST] = {}
    for node in ast.walk(tree):
        for child in ast.iter_child_nodes(node):
            parents[child] = node
    return parents


def _assignment_targets(node: ast.AST) -> set[str]:
    targets: list[ast.AST] = []
    if isinstance(node, ast.Assign):
        targets.extend(node.targets)
    elif isinstance(node, ast.AnnAssign):
        targets.append(node.target)
    elif isinstance(node, (ast.AugAssign, ast.NamedExpr)):
        targets.append(node.target)
    result: set[str] = set()
    for target in targets:
        for child in ast.walk(target):
            if isinstance(child, ast.Name):
                result.add(child.id)
    return direct_class, direct_count, direct_evidence


def _load_names(node: ast.AST) -> set[str]:
    return {child.id for child in ast.walk(node) if isinstance(child, ast.Name) and isinstance(child.ctx, ast.Load)}


def _store_names(node: ast.AST) -> set[str]:
    return {child.id for child in ast.walk(node) if isinstance(child, ast.Name) and isinstance(child.ctx, ast.Store)}


def _scope_root(node: ast.AST, parents: Mapping[ast.AST, ast.AST]) -> ast.AST:
    current = node
    while current in parents:
        current = parents[current]
        if isinstance(current, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Module)):
            return current
    return current


def _enclosing_loops(node: ast.AST, parents: Mapping[ast.AST, ast.AST]) -> list[ast.For | ast.AsyncFor]:
    loops: list[ast.For | ast.AsyncFor] = []
    current = node
    while current in parents:
        current = parents[current]
        if isinstance(current, (ast.For, ast.AsyncFor)):
            loops.append(current)
        if isinstance(current, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Module)):
            break
    return list(reversed(loops))


def _aligned_calls(tree: ast.AST, call_sites: Sequence[Mapping[str, Any]]) -> list[ast.Call]:
    calls = sorted(
        (node for node in ast.walk(tree) if _is_processing_call(node) and _operator_id(node)),
        key=lambda node: (int(node.lineno), int(node.col_offset)),
    )
    result: list[ast.Call] = []
    used: set[int] = set()
    for site in call_sites:
        operator_id = str(site.get("operator_id") or "").strip().lower()
        start = int(site.get("line_start") or 0)
        end = int(site.get("line_end") or start)
        candidates = [
            call
            for call in calls
            if id(call) not in used
            and _operator_id(call) == operator_id
            and int(call.lineno) <= end
            and int(call.end_lineno or call.lineno) >= start
        ]
        if not candidates:
            raise ValueError(f"call_site_alignment_failed:{operator_id}@{start}-{end}")
        chosen = min(candidates, key=lambda call: abs(int(call.lineno) - start))
        used.add(id(chosen))
        result.append(chosen)
    return result


def _static_iteration_expression(iterable: ast.AST) -> tuple[str, int | None, str]:
    if isinstance(iterable, ast.Call) and isinstance(iterable.func, ast.Name) and iterable.func.id == "range":
        values: list[int] = []
        for arg in iterable.args:
            if not isinstance(arg, ast.Constant) or not isinstance(arg.value, int):
                return "dynamic", None, "range_non_literal"
            values.append(int(arg.value))
        if not 1 <= len(values) <= 3:
            return "unknown", None, "range_arity"
        try:
            count = len(range(*values))
        except ValueError:
            return "unknown", None, "range_invalid_step"
        return ("fixed_small" if count <= MAX_SMALL_ITERATIONS else "fixed_large"), count, "range_literal"
    if isinstance(iterable, (ast.List, ast.Tuple, ast.Set, ast.Dict)):
        count = len(iterable.elts) if hasattr(iterable, "elts") else len(iterable.keys)
        return ("fixed_small" if count <= MAX_SMALL_ITERATIONS else "fixed_large"), count, "literal_iterable"
    if isinstance(iterable, ast.Constant) and isinstance(iterable.value, (str, bytes)):
        count = len(iterable.value)
        return ("fixed_small" if count <= MAX_SMALL_ITERATIONS else "fixed_large"), count, "literal_string"
    if isinstance(iterable, ast.Name):
        return "dynamic", None, f"name:{iterable.id}"
    return "unknown", None, type(iterable).__name__


def _preceding_binding(
    node: ast.For | ast.AsyncFor,
    name: str,
    parents: Mapping[ast.AST, ast.AST],
) -> ast.AST | None:
    candidates: list[tuple[int, ast.AST]] = []
    for statement in _loop_siblings(node, parents):
        if int(statement.lineno) >= int(node.lineno):
            continue
        if isinstance(statement, ast.Assign) and len(statement.targets) == 1:
            target = statement.targets[0]
            value = statement.value
        elif isinstance(statement, ast.AnnAssign) and statement.value is not None:
            target = statement.target
            value = statement.value
        else:
            continue
        if isinstance(target, ast.Name) and target.id == name:
            candidates.append((int(statement.lineno), value))
    if not candidates:
        return None
    return max(candidates, key=lambda item: item[0])[1]


def _resolve_static_iteration(
    expression: ast.AST,
    node: ast.For | ast.AsyncFor,
    parents: Mapping[ast.AST, ast.AST],
    seen_names: set[str] | None = None,
) -> tuple[str, int | None, str]:
    seen_names = set(seen_names or ())
    direct_class, direct_count, direct_evidence = _static_iteration_expression(expression)
    if direct_class.startswith("fixed_"):
        return direct_class, direct_count, direct_evidence
    if isinstance(expression, ast.Name):
        if expression.id in seen_names:
            return "unknown", None, f"recursive_name:{expression.id}"
        binding = _preceding_binding(node, expression.id, parents)
        if binding is None:
            return direct_class, direct_count, direct_evidence
        binding_class, count, evidence = _resolve_static_iteration(
            binding, node, parents, seen_names | {expression.id}
        )
        if binding_class.startswith("fixed_"):
            return binding_class, count, f"name_static:{expression.id}:{evidence}"
        return direct_class, direct_count, direct_evidence
    if isinstance(expression, ast.Call) and isinstance(expression.func, ast.Name):
        function_name = expression.func.id
        if function_name in {"enumerate", "sorted", "reversed"} and expression.args:
            nested = _resolve_static_iteration(expression.args[0], node, parents, seen_names)
            if nested[0].startswith("fixed_"):
                return nested[0], nested[1], f"{function_name}:{nested[2]}"
        if function_name == "zip" and expression.args:
            nested_values = [
                _resolve_static_iteration(argument, node, parents, seen_names)
                for argument in expression.args
            ]
            if nested_values and all(value[0].startswith("fixed_") and value[1] is not None for value in nested_values):
                count = min(int(value[1]) for value in nested_values)
                iteration_class = "fixed_small" if count <= MAX_SMALL_ITERATIONS else "fixed_large"
                evidence = ",".join(value[2] for value in nested_values)
                return iteration_class, count, f"zip:{evidence}"
    return direct_class, direct_count, direct_evidence


def _static_iteration_count(
    node: ast.For | ast.AsyncFor,
    parents: Mapping[ast.AST, ast.AST],
) -> tuple[str, int | None, str]:
    return _resolve_static_iteration(node.iter, node, parents)


def _control_flow(loop: ast.For | ast.AsyncFor) -> tuple[list[str], list[str], int]:
    kinds: set[str] = set()
    statements: set[str] = set()
    nested = 0
    for node in ast.walk(loop):
        if node is loop:
            continue
        if isinstance(node, (ast.For, ast.AsyncFor)):
            nested += 1
            kinds.add("nested_for")
        elif isinstance(node, ast.While):
            kinds.add("nested_while")
        elif isinstance(node, (ast.Try, ast.TryStar)):
            kinds.add("try")
        elif isinstance(node, ast.If):
            kinds.add("if")
        elif isinstance(node, ast.Break):
            statements.add("break")
        elif isinstance(node, ast.Continue):
            statements.add("continue")
        elif isinstance(node, ast.Return):
            statements.add("return")
        elif isinstance(node, ast.Raise):
            statements.add("raise")
    return sorted(kinds), sorted(statements), nested


def _loop_siblings(loop: ast.For | ast.AsyncFor, parents: Mapping[ast.AST, ast.AST]) -> list[ast.stmt]:
    scope = _scope_root(loop, parents)
    body = getattr(scope, "body", [])
    return [statement for statement in body if isinstance(statement, ast.stmt)]


def _outer_definitions(loop: ast.For | ast.AsyncFor, parents: Mapping[ast.AST, ast.AST]) -> set[str]:
    siblings = _loop_siblings(loop, parents)
    before = [statement for statement in siblings if int(statement.lineno) < int(loop.lineno)]
    names: set[str] = set()
    for statement in before:
        names.update(_store_names(statement))
    return names


def _direct_target_names(target: ast.AST) -> set[str]:
    if isinstance(target, ast.Name):
        return {target.id}
    if isinstance(target, (ast.Tuple, ast.List)):
        return {
            name
            for element in target.elts
            for name in _direct_target_names(element)
        }
    return set()


def _dependency_class(loop: ast.For | ast.AsyncFor, parents: Mapping[ast.AST, ast.AST]) -> tuple[str, list[str]]:
    del parents  # The classification depends on per-iteration data flow, not outer bindings.
    loop_target_names = _store_names(loop.target)
    written = {
        name
        for statement in loop.body
        for name in _store_names(statement)
        if name not in loop_target_names
    }
    definite: set[str] = set()
    carried: set[str] = set()

    for statement in loop.body:
        if isinstance(statement, ast.Assign):
            carried.update((_load_names(statement.value) & written) - definite)
            for target in statement.targets:
                carried.update((_load_names(target) & written) - definite)
                definite.update(_direct_target_names(target))
            continue

        if isinstance(statement, ast.AnnAssign):
            if statement.value is not None:
                carried.update((_load_names(statement.value) & written) - definite)
            carried.update((_load_names(statement.target) & written) - definite)
            definite.update(_direct_target_names(statement.target))
            continue

        if isinstance(statement, ast.AugAssign):
            # AugAssign always reads its target before writing it. Keep it closed
            # even when an earlier statement appears to initialize the name.
            carried.update(_direct_target_names(statement.target) & written)
            carried.update((_load_names(statement.value) & written) - definite)
            continue

        loads = _load_names(statement) & written
        carried.update(loads - definite)

        # Bindings hidden behind control flow are not definite for subsequent
        # statements. Only unconditional top-level definitions are propagated.
        if isinstance(statement, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            definite.add(statement.name)

    return ("loop_carried_state" if carried else "independent"), sorted(carried)


def _output_aggregation(loop: ast.For | ast.AsyncFor) -> tuple[str, list[str]]:
    methods: set[str] = set()
    targets: set[str] = set()
    for node in ast.walk(loop):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            if node.func.attr in {"append", "extend", "add", "update"}:
                methods.add(node.func.attr)
                if isinstance(node.func.value, ast.Name):
                    targets.add(node.func.value.id)
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Subscript) and isinstance(target.value, ast.Name):
                    methods.add("subscript")
                    targets.add(target.value.id)
    if not methods:
        return "none", []
    if len(methods) == 1:
        return next(iter(methods)), sorted(targets)
    return "multiple", sorted(targets)


def _post_loop_consumers(loop: ast.For | ast.AsyncFor, parents: Mapping[ast.AST, ast.AST], written: set[str]) -> list[str]:
    end_line = int(loop.end_lineno or loop.lineno)
    consumers: set[str] = set()
    for statement in _loop_siblings(loop, parents):
        if int(statement.lineno) <= end_line:
            continue
        consumers.update(_load_names(statement) & written)
    return sorted(consumers)


def _candidate_class(
    iteration_class: str,
    dependency_class: str,
    control_flow_kinds: Sequence[str],
    control_flow_statements: Sequence[str],
    nested_count: int,
) -> str:
    if dependency_class == "loop_carried_state":
        return "loop_carried_state"
    if control_flow_kinds or control_flow_statements or nested_count:
        return "complex_control_flow"
    if iteration_class == "fixed_small":
        return "fixed_small_independent"
    if iteration_class == "fixed_large":
        return "fixed_large"
    if iteration_class == "dynamic":
        return "dynamic"
    return "unknown"


def analyze_for_loops(source_text: str, *, call_sites: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", SyntaxWarning)
        tree = ast.parse(source_text)
    matched = _aligned_calls(tree, call_sites)
    parents = _parents(tree)
    loops: list[dict[str, Any]] = []
    seen: set[int] = set()
    for call in matched:
        for loop in _enclosing_loops(call, parents):
            if id(loop) in seen:
                continue
            seen.add(id(loop))
            loop_calls = [candidate for candidate in matched if loop in _enclosing_loops(candidate, parents)]
            iteration_class, count, evidence = _static_iteration_count(loop, parents)
            control_kinds, control_statements, nested_count = _control_flow(loop)
            dependency, carried = _dependency_class(loop, parents)
            output_kind, output_targets = _output_aggregation(loop)
            written = _store_names(loop)
            loops.append(
                {
                    "line_start": int(loop.lineno),
                    "line_end": int(loop.end_lineno or loop.lineno),
                    "loop_kind": "async_for" if isinstance(loop, ast.AsyncFor) else "for",
                    "iterable_expression": ast.unparse(loop.iter),
                    "iterable_evidence": evidence,
                    "iteration_class": iteration_class,
                    "static_iteration_count": count,
                    "nested_loop_count": nested_count,
                    "control_flow_kinds": control_kinds,
                    "control_flow_statements": control_statements,
                    "processing_call_count": len(loop_calls),
                    "operator_ids": [_operator_id(candidate) for candidate in loop_calls],
                    "dependency_class": dependency,
                    "loop_carried_names": carried,
                    "output_aggregation": output_kind,
                    "output_targets": output_targets,
                    "post_loop_consumers": _post_loop_consumers(loop, parents, written),
                    "candidate_class": _candidate_class(
                        iteration_class,
                        dependency,
                        control_kinds,
                        control_statements,
                        nested_count,
                    ),
                }
            )
    loops.sort(key=lambda item: (item["line_start"], item["line_end"]))
    return {
        "schema": "gis_recommend.qgis_for_loop_analysis.v3",
        "matched_call_count": len(matched),
        "relevant_loop_count": len(loops),
        "loops": loops,
        "alignment_status": "matched_full_call_sites",
    }


def build_for_loop_census(manifest_rows: Sequence[Mapping[str, Any]]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    inputs = [
        dict(row)
        for row in manifest_rows
        if row.get("action") in SUPPORTED_ACTIONS
        and "control_flow:for" in (row.get("blocker_reasons") or [])
    ]
    rows: list[dict[str, Any]] = []
    failures: list[dict[str, str]] = []
    for parent in inputs:
        path = Path(str(parent.get("source_path") or ""))
        record_id = str(parent.get("record_id") or "")
        try:
            if not path.is_file():
                raise ValueError("source_file_missing")
            expected = str(parent.get("source_sha256") or "")
            if _sha256(path) != expected:
                raise ValueError("source_sha256_mismatch")
            source_text = path.read_text(encoding="utf-8-sig", errors="replace")
            if parent.get("provider_migrations") or parent.get("resolution_status") == "fixed_chain_recovered":
                source_text = literalize_processing_operator_ids(
                    source_text,
                    call_sites=parent.get("call_sites") or [],
                    require_full_coverage=not bool(parent.get("provider_migrations")),
                )
            analysis = analyze_for_loops(source_text, call_sites=parent.get("call_sites") or [])
            authority = source_authority(path, source_sha256=expected)
        except (OSError, SyntaxError, ValueError) as exc:
            failures.append({"record_id": record_id, "reason": str(exc)})
            continue
        row = {
            "schema": "gis_recommend.qgis_for_loop_census.v3",
            "record_id": record_id,
            "action": parent.get("action"),
            "rule_id": parent.get("rule_id"),
            "source_root_id": parent.get("source_root_id"),
            "source_path": str(path),
            "source_sha256": expected,
            **authority,
            "blocker_reasons": list(parent.get("blocker_reasons") or []),
            "ordered_operator_ids": [str(site.get("operator_id") or "").lower() for site in parent.get("call_sites") or []],
            **analysis,
            "training_admission": "not_granted_census_only",
            "training_row_emitted": False,
            "validation_eligible": False,
            "test_eligible": False,
            "production_merge": "not_granted",
        }
        rows.append(row)
    candidate_counts = Counter(
        loop["candidate_class"] for row in rows for loop in row["loops"]
    )
    candidate_authorities: dict[str, set[str]] = {}
    authority_candidates: dict[str, set[str]] = {}
    for row in rows:
        for loop in row["loops"]:
            candidate_authorities.setdefault(loop["candidate_class"], set()).add(
                row["source_authority_key"]
            )
            authority_candidates.setdefault(row["source_authority_key"], set()).add(
                loop["candidate_class"]
            )
    iteration_counts = Counter(
        loop["iteration_class"] for row in rows for loop in row["loops"]
    )
    dependency_counts = Counter(
        loop["dependency_class"] for row in rows for loop in row["loops"]
    )
    summary = {
        "schema": "gis_recommend.qgis_for_loop_census.summary.v3",
        "input_rows": len(inputs),
        "verified_rows": len(rows),
        "failed_rows": len(failures),
        "failures": failures,
        "unique_source_authorities": len({row["source_authority_key"] for row in rows}),
        "relevant_loops": sum(row["relevant_loop_count"] for row in rows),
        "candidate_classes": dict(sorted(candidate_counts.items())),
        "candidate_authority_support": {
            name: len(authorities)
            for name, authorities in sorted(candidate_authorities.items())
        },
        "unambiguous_candidate_authority_support": {
            name: sum(classes == {name} for classes in authority_candidates.values())
            for name in sorted({name for classes in authority_candidates.values() for name in classes})
            if any(classes == {name} for classes in authority_candidates.values())
        },
        "iteration_classes": dict(sorted(iteration_counts.items())),
        "dependency_classes": dict(sorted(dependency_counts.items())),
        "training_rows_emitted": 0,
        "decision": {
            "training_admission": "not_granted_census_only",
            "next_gate": "source-disjoint calibration of fixed_small_independent only",
            "fixed_small_rule_requirements": {
                "max_static_iteration_count": MAX_SMALL_ITERATIONS,
                "no_loop_carried_state": True,
                "no_complex_control_flow": True,
                "precision": 0.95,
                "wilson_lower_95": 0.80,
                "minimum_source_authority_support": 30,
            },
        },
    }
    return rows, summary


def _atomic_write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=path.parent, delete=False) as handle:
        handle.write(text)
        temporary = Path(handle.name)
    temporary.replace(path)


def write_outputs(
    rows: Sequence[Mapping[str, Any]],
    summary: Mapping[str, Any],
    *,
    manifest_path: Path,
    family_census_path: Path,
    output_dir: Path,
) -> dict[str, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    ledger = output_dir / "for_loop_census_v3.jsonl"
    summary_path = output_dir / "summary_v3.json"
    report = output_dir / "report_v3.md"
    hashes = output_dir / "hash_ledger_v3.json"
    _atomic_write(ledger, "".join(json.dumps(dict(row), ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n" for row in rows))
    _atomic_write(summary_path, json.dumps(dict(summary), ensure_ascii=False, indent=2, sort_keys=True) + "\n")
    report_lines = [
        "# QGIS For-Loop Census v3",
        "",
        "Source-backed structural census only; no training rows are emitted.",
        "",
        f"- Input rows: {summary['input_rows']}",
        f"- Verified rows: {summary['verified_rows']}",
        f"- Relevant loops: {summary['relevant_loops']}",
        f"- Unique source authorities: {summary['unique_source_authorities']}",
        f"- Candidate classes: {summary['candidate_classes']}",
        f"- Iteration classes: {summary['iteration_classes']}",
        f"- Dependency classes: {summary['dependency_classes']}",
        "- Training rows emitted: 0",
        "",
        "Only a source-disjoint fixed-small-independent rule with support >=30, precision >=0.95, and Wilson lower >=0.80 may proceed to calibration.",
    ]
    _atomic_write(report, "\n".join(report_lines) + "\n")
    payload = {
        "schema": "gis_recommend.qgis_for_loop_census.hash_ledger.v3",
        "source_inputs": {
            "l3_manifest": {"path": str(manifest_path), "sha256": _sha256(manifest_path)},
            "family_census": {"path": str(family_census_path), "sha256": _sha256(family_census_path)},
        },
        "artifacts": {path.name: {"path": str(path), "sha256": _sha256(path)} for path in (ledger, summary_path, report)},
    }
    _atomic_write(hashes, json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
    return {"ledger": ledger, "summary": summary_path, "report": report, "hash_ledger": hashes}


def main(argv: Sequence[str] | None = None) -> dict[str, Path]:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--family-census", type=Path, default=DEFAULT_FAMILY_CENSUS)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    args = parser.parse_args(argv)
    inputs = join_for_loop_inputs(
        _load_jsonl(args.manifest), _load_jsonl(args.family_census)
    )
    rows, summary = build_for_loop_census(inputs)
    return write_outputs(
        rows,
        summary,
        manifest_path=args.manifest,
        family_census_path=args.family_census,
        output_dir=args.output_dir,
    )


if __name__ == "__main__":
    main()
