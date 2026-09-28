#!/usr/bin/env python3
"""Recover complete random-point sampling workflows from QGIS API sources."""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import tempfile
from pathlib import Path
from typing import Any, Iterable


RULE_ID = "lexical-scope-random-point-sampling-v1"
POINT_FACTORIES = {
    "qgsgeometry.frompoint",
    "qgsgeometry.frompointxy",
}
CONTAINMENT_METHODS = {"contains", "within"}


def _call_name(node: ast.AST) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        prefix = _call_name(node.value)
        return f"{prefix}.{node.attr}" if prefix else node.attr
    if isinstance(node, ast.Call):
        return _call_name(node.func)
    return ""


def _method(node: ast.Call) -> str:
    return _call_name(node.func).rsplit(".", 1)[-1].lower()


class _ScopeIndex(ast.NodeVisitor):
    def __init__(self) -> None:
        self.stack: list[str] = []
        self.scopes: dict[str, ast.FunctionDef | ast.AsyncFunctionDef] = {}

    def visit_ClassDef(self, node: ast.ClassDef) -> None:  # noqa: N802
        self.stack.append(node.name)
        self.generic_visit(node)
        self.stack.pop()

    def _visit_function(
        self, node: ast.FunctionDef | ast.AsyncFunctionDef
    ) -> None:
        qualified = ".".join([*self.stack, node.name])
        self.scopes[qualified] = node
        self.stack.append(node.name)
        self.generic_visit(node)
        self.stack.pop()

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:  # noqa: N802
        self._visit_function(node)

    def visit_AsyncFunctionDef(  # noqa: N802
        self, node: ast.AsyncFunctionDef
    ) -> None:
        self._visit_function(node)


def _parent_index(root: ast.AST) -> dict[ast.AST, ast.AST]:
    return {
        child: parent
        for parent in ast.walk(root)
        for child in ast.iter_child_nodes(parent)
    }


def _ancestor(
    node: ast.AST,
    parents: dict[ast.AST, ast.AST],
    kind: type[ast.AST],
    *,
    stop: ast.AST | None = None,
) -> ast.AST | None:
    current = node
    while current in parents:
        current = parents[current]
        if isinstance(current, kind):
            return current
        if current is stop:
            return None
    return None


def _ancestors_until(
    node: ast.AST, parents: dict[ast.AST, ast.AST], stop: ast.AST
) -> list[ast.AST]:
    ancestors: list[ast.AST] = []
    current = node
    while current in parents:
        current = parents[current]
        if current is stop:
            break
        ancestors.append(current)
    return ancestors


def _names(node: ast.AST) -> set[str]:
    return {item.id for item in ast.walk(node) if isinstance(item, ast.Name)}


def _incremented_names(loop: ast.While) -> set[str]:
    names: set[str] = set()
    for node in ast.walk(loop):
        if isinstance(node, ast.AugAssign) and isinstance(node.target, ast.Name):
            names.add(node.target.id)
    return names


def _bounded_sampling_loop(loop: ast.While) -> tuple[bool, list[str]]:
    if not isinstance(loop.test, ast.BoolOp) or not isinstance(loop.test.op, ast.And):
        return False, []
    comparisons = [node for node in ast.walk(loop.test) if isinstance(node, ast.Compare)]
    if len(comparisons) < 2:
        return False, []
    controlled = _names(loop.test) & _incremented_names(loop)
    return len(controlled) >= 2, sorted(controlled)


def _point_factory_for_set_geometry(
    loop: ast.While, set_geometry: ast.Call
) -> tuple[str, int] | None:
    if not set_geometry.args:
        return None
    payload = set_geometry.args[0]
    if isinstance(payload, ast.Call):
        name = _call_name(payload.func).lower()
        return (name, payload.lineno) if name in POINT_FACTORIES else None
    if not isinstance(payload, ast.Name):
        return None
    assignments: list[tuple[str, int]] = []
    for node in ast.walk(loop):
        if not isinstance(node, (ast.Assign, ast.AnnAssign)):
            continue
        value = node.value
        if not isinstance(value, ast.Call) or node.lineno >= set_geometry.lineno:
            continue
        targets = node.targets if isinstance(node, ast.Assign) else [node.target]
        if any(
            isinstance(target, ast.Name) and target.id == payload.id
            for target in targets
        ):
            name = _call_name(value.func).lower()
            if name in POINT_FACTORIES:
                assignments.append((name, node.lineno))
    return max(assignments, key=lambda item: item[1]) if assignments else None


def _source_step(
    *, step_index: int, call_name: str, call_role: str, node: ast.Call
) -> dict[str, Any]:
    return {
        "step_index": step_index,
        "call_name": call_name,
        "call_role": call_role,
        "line_start": node.lineno,
        "line_end": int(getattr(node, "end_lineno", node.lineno)),
        "terminal_evidence": call_role == "sink_output",
    }


def _sidecar(row: dict[str, Any], failure_labels: list[str]) -> dict[str, Any]:
    return {
        **row,
        "schema": "gis_recommend.qgis_api_random_point_workflow_sidecar.v1",
        "random_point_recovery_rule_id": RULE_ID,
        "random_point_recovery_status": "deferred_incomplete_task_boundary",
        "failure_labels": sorted(set(failure_labels)),
        "candidate_l3_sequence": [],
        "mapping_admission": "not_started",
        "description_fidelity": "not_started",
        "deduplication": "not_started",
        "training_admission": "not_granted_random_point_recovery_sidecar",
        "training_row_emitted": False,
        "validation_eligible": False,
        "test_eligible": False,
        "production_merge": "not_granted",
    }


def recover_row(
    row: dict[str, Any],
) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    if row.get("training_row_emitted") is not False:
        raise ValueError("random-point recovery input must emit zero training rows")
    path = Path(str(row["source_path"]))
    try:
        payload = path.read_bytes()
    except OSError:
        return None, _sidecar(row, ["source_unavailable"])
    if hashlib.sha256(payload).hexdigest() != str(row.get("source_sha256") or ""):
        return None, _sidecar(row, ["source_sha256_mismatch"])
    try:
        source = payload.decode("utf-8-sig")
        tree = ast.parse(source, filename=str(path))
    except (UnicodeDecodeError, SyntaxError):
        return None, _sidecar(row, ["source_ast_unparseable"])

    scopes = _ScopeIndex()
    scopes.visit(tree)
    lexical_scope = str(row.get("lexical_scope") or "")
    scope = scopes.scopes.get(lexical_scope)
    if scope is None:
        method_name = lexical_scope.rsplit(".", 1)[-1]
        same_name = [
            node
            for qualified, node in scopes.scopes.items()
            if qualified.rsplit(".", 1)[-1] == method_name
        ]
        scope = same_name[0] if len(same_name) == 1 else None
    if scope is None:
        return None, _sidecar(row, ["lexical_scope_not_found"])

    parents = _parent_index(scope)
    set_geometry_calls = [
        node
        for node in ast.walk(scope)
        if isinstance(node, ast.Call) and _method(node) == "setgeometry"
    ]
    if len(set_geometry_calls) != 1:
        return None, _sidecar(row, ["non_unique_set_geometry_terminal"])
    set_geometry = set_geometry_calls[0]
    loop = _ancestor(set_geometry, parents, ast.While)
    if not isinstance(loop, ast.While):
        return None, _sidecar(row, ["missing_sampling_loop"])

    failure_labels: list[str] = []
    bounded_loop, loop_control_names = _bounded_sampling_loop(loop)
    if not bounded_loop:
        failure_labels.append("missing_bounded_sampling_loop")

    loop_calls = [node for node in ast.walk(loop) if isinstance(node, ast.Call)]
    random_calls = [
        node for node in loop_calls if _call_name(node.func).lower() == "random.random"
    ]
    if len(random_calls) != 2:
        failure_labels.append("missing_two_coordinate_random_draws")

    point_factory = _point_factory_for_set_geometry(loop, set_geometry)
    if point_factory is None:
        failure_labels.append("missing_point_geometry_factory")

    controlling_predicates = [
        node
        for node in _ancestors_until(set_geometry, parents, loop)
        if isinstance(node, ast.If)
    ]
    predicate_calls = [
        call
        for predicate in controlling_predicates
        for call in ast.walk(predicate.test)
        if isinstance(call, ast.Call)
    ]
    containment_calls = [
        node for node in predicate_calls if _method(node) in CONTAINMENT_METHODS
    ]
    if not containment_calls:
        failure_labels.append("missing_containment_predicate")
    min_distance_calls = [
        node
        for node in predicate_calls
        if "checkmindistance" in _call_name(node.func).replace("_", "").lower()
    ]
    if not min_distance_calls:
        failure_labels.append("missing_min_distance_predicate")

    terminal_call_names = {
        str(step.get("call_name") or "").lower()
        for step in row.get("steps") or []
        if step.get("call_role") == "sink_output"
    }
    sink_calls = [
        node
        for node in loop_calls
        if _call_name(node.func).lower() in terminal_call_names
        and node.lineno > set_geometry.lineno
    ]
    if len(sink_calls) != 1:
        failure_labels.append("missing_unique_sink_output")
    elif controlling_predicates:
        sink_predicates = {
            node
            for node in _ancestors_until(sink_calls[0], parents, loop)
            if isinstance(node, ast.If)
        }
        if not set(controlling_predicates).issubset(sink_predicates):
            failure_labels.append("sink_outside_sampling_acceptance_branch")

    if failure_labels:
        return None, _sidecar(row, failure_labels)

    assert point_factory is not None
    sink_call = sink_calls[0]
    containment_names = sorted({_call_name(node.func) for node in containment_calls})
    min_distance_names = sorted({_call_name(node.func) for node in min_distance_calls})
    semantic_step = {
        "step_index": 0,
        "call_name": "random_point_sampling",
        "call_role": "composite_algorithm",
        "line_start": loop.lineno,
        "line_end": int(getattr(loop, "end_lineno", loop.lineno)),
        "terminal_evidence": False,
    }
    recovered_steps = [
        semantic_step,
        _source_step(
            step_index=1,
            call_name=_call_name(set_geometry.func),
            call_role="feature_mutation",
            node=set_geometry,
        ),
        _source_step(
            step_index=2,
            call_name=_call_name(sink_call.func),
            call_role="sink_output",
            node=sink_call,
        ),
    ]
    recovery_key = "|".join(
        [RULE_ID, str(row["candidate_id"]), str(loop.lineno), str(loop.end_lineno)]
    )
    candidate = {
        **row,
        "schema": "gis_recommend.qgis_api_random_point_workflow_candidate.v1",
        "upstream_candidate_id": row["candidate_id"],
        "candidate_id": hashlib.sha256(recovery_key.encode("utf-8")).hexdigest(),
        "random_point_recovery_rule_id": RULE_ID,
        "random_point_recovery_status": "resolved_complete_lexical_scope_workflow",
        "source_span": [scope.lineno, int(scope.end_lineno)],
        "evidence_snippet": ast.get_source_segment(source, scope) or "",
        "sampling_loop_span": [loop.lineno, int(loop.end_lineno)],
        "sampling_loop_snippet": ast.get_source_segment(source, loop) or "",
        "original_boundary_steps": list(row.get("steps") or []),
        "steps": recovered_steps,
        "semantic_calls": ["random_point_sampling"],
        "dependency_edges": [[0, 1], [1, 2]],
        "random_point_facts": {
            "random_draw_calls": len(random_calls),
            "bounded_loop": bounded_loop,
            "loop_control_names": loop_control_names,
            "point_factory_call": point_factory[0],
            "point_factory_line": point_factory[1],
            "containment_calls": containment_names,
            "min_distance_calls": min_distance_names,
            "set_geometry_line": set_geometry.lineno,
            "sink_output_line": sink_call.lineno,
        },
        "candidate_l3_sequence": [],
        "mapping_admission": "not_started",
        "description_fidelity": "not_started",
        "deduplication": "not_started",
        "training_admission": "not_granted_random_point_boundary_candidate",
        "training_row_emitted": False,
        "validation_eligible": False,
        "test_eligible": False,
        "production_merge": "not_granted",
    }
    return candidate, None


def recover_rows(
    rows: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    sidecar: list[dict[str, Any]] = []
    for row in rows:
        candidate, deferred = recover_row(row)
        if candidate is not None:
            candidates.append(candidate)
        if deferred is not None:
            sidecar.append(deferred)
    failure_counts: dict[str, int] = {}
    for row in sidecar:
        for label in row["failure_labels"]:
            failure_counts[label] = failure_counts.get(label, 0) + 1
    summary = {
        "schema": "gis_recommend.qgis_api_random_point_recovery_summary.v1",
        "random_point_recovery_rule_id": RULE_ID,
        "input_units": len(rows),
        "resolved_candidate_units": len(candidates),
        "resolved_source_authorities": len(
            {str(row["source_authority_key"]) for row in candidates}
        ),
        "deferred_units": len(sidecar),
        "failure_label_counts": dict(sorted(failure_counts.items())),
        "l3_mapping_rows": 0,
        "description_fidelity_rows": 0,
        "training_rows_emitted": 0,
        "training_admission": "not_granted_boundary_recovery_only",
    }
    return candidates, sidecar, summary


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    with path.open(encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _atomic_write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "w", encoding="utf-8", newline="", dir=path.parent, delete=False
    ) as handle:
        handle.write(content)
        temporary = Path(handle.name)
    temporary.replace(path)


def _write_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> None:
    _atomic_write(
        path,
        "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows),
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-jsonl", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--expected-rows", type=int)
    args = parser.parse_args()
    if args.output_dir.exists() and any(args.output_dir.iterdir()):
        raise ValueError(f"output directory is not empty: {args.output_dir}")
    rows = _read_jsonl(args.input_jsonl)
    if args.expected_rows is not None and len(rows) != args.expected_rows:
        raise ValueError(f"input rows {len(rows)} != expected {args.expected_rows}")
    candidates, sidecar, summary = recover_rows(rows)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    outputs = {
        "random_point_candidates_v1.jsonl": candidates,
        "random_point_sidecar_v1.jsonl": sidecar,
    }
    artifacts: list[Path] = []
    for name, output_rows in outputs.items():
        path = args.output_dir / name
        _write_jsonl(path, output_rows)
        artifacts.append(path)
    summary_path = args.output_dir / "summary_v1.json"
    _atomic_write(
        summary_path,
        json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
    )
    artifacts.append(summary_path)
    ledger = {
        "schema": "gis_recommend.hash_ledger.v1",
        "inputs": {
            "input_jsonl": {
                "path": str(args.input_jsonl),
                "sha256": _sha256(args.input_jsonl),
            }
        },
        "artifacts": {
            path.name: {"sha256": _sha256(path), "bytes": path.stat().st_size}
            for path in artifacts
        },
    }
    _atomic_write(
        args.output_dir / "hash_ledger_v1.json",
        json.dumps(ledger, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
