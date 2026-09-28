#!/usr/bin/env python3
"""Replay strict point-geometry construction macros against QGIS source files."""

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

from gis_recommend.data.qgis_source_authority import source_authority
from scripts.analyze_qgis_api_mutation_upstream import (
    _control_path,
    _name,
    _parents,
    _scope_node,
)

RULE_ID = "qgis-api-point-geometry-local-macro-v1"
POINT_FACTORIES = {"qgsgeometry.frompoint", "qgsgeometry.frompointxy"}
POINT_VALUE_CONSTRUCTORS = {"qgspoint", "qgspointxy"}
SINKS = {"addfeature", "addfeatures"}


class ReplayDeferred(Exception):
    """Carry a stable fail-closed reason out of payload resolution."""


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _method(node: ast.Call) -> str:
    return _name(node.func).rsplit(".", 1)[-1].lower()


def _base(row: dict[str, Any], status: str, reason: str) -> dict[str, Any]:
    return {
        **row,
        "schema": "gis_recommend.qgis_api_point_geometry_replay.v1",
        "point_geometry_rule_id": RULE_ID,
        "macro_status": status,
        "deferred_reason": reason,
        "mapping_status": "not_started_boundary_calibration_only",
        "candidate_l3_sequence": [],
        "description_fidelity": "not_started",
        "training_admission": "not_granted_source_replay_only",
        "training_row_emitted": False,
        "validation_eligible": False,
        "test_eligible": False,
        "production_merge": "not_granted",
        "llm_called": False,
    }


def _assigned_name(call: ast.Call, parents: dict[ast.AST, ast.AST]) -> str:
    parent = parents.get(call)
    if isinstance(parent, ast.Assign) and len(parent.targets) == 1 and isinstance(parent.targets[0], ast.Name):
        return parent.targets[0].id
    if isinstance(parent, ast.AnnAssign) and isinstance(parent.target, ast.Name):
        return parent.target.id
    return ""


def _resolve_factory(
    payload: ast.AST,
    *,
    scope: ast.AST,
    parents: dict[ast.AST, ast.AST],
    before_line: int,
    control_path: tuple[str, ...],
) -> tuple[ast.Call, list[int]]:
    if isinstance(payload, ast.Call) and _name(payload.func).lower() in POINT_FACTORIES:
        return payload, []
    if not isinstance(payload, ast.Name):
        raise ReplayDeferred("setgeometry_payload_not_direct_point_factory")
    assignments = []
    for node in ast.walk(scope):
        if not isinstance(node, (ast.Assign, ast.AnnAssign)) or int(node.lineno) >= before_line:
            continue
        targets = node.targets if isinstance(node, ast.Assign) else [node.target]
        if not any(isinstance(target, ast.Name) and target.id == payload.id for target in targets):
            continue
        value = node.value
        if not isinstance(value, ast.Call) or _name(value.func).lower() not in POINT_FACTORIES:
            continue
        if _control_path(node, parents) != control_path:
            continue
        assignments.append(node)
    if len(assignments) != 1:
        raise ReplayDeferred("point_factory_alias_not_unique_or_not_same_control_path")
    assignment = assignments[0]
    assert isinstance(assignment.value, ast.Call)
    return assignment.value, [int(assignment.lineno)]


def _feature_name(set_geometry: ast.Call) -> str:
    if not isinstance(set_geometry.func, ast.Attribute):
        return ""
    return _name(set_geometry.func.value)


def _sink_matches_feature(sink: ast.Call, feature: str) -> bool:
    if _method(sink) == "addfeature":
        return len(sink.args) == 1 and isinstance(sink.args[0], ast.Name) and sink.args[0].id == feature
    if _method(sink) == "addfeatures":
        return (
            len(sink.args) == 1
            and isinstance(sink.args[0], ast.List)
            and len(sink.args[0].elts) == 1
            and isinstance(sink.args[0].elts[0], ast.Name)
            and sink.args[0].elts[0].id == feature
        )
    return False


def _for_target_names(node: ast.AST) -> set[str]:
    if isinstance(node, ast.Name):
        return {node.id}
    if isinstance(node, (ast.Tuple, ast.List)):
        return {name for item in node.elts for name in _for_target_names(item)}
    return set()


def _enclosing_for_targets(
    node: ast.AST, parents: dict[ast.AST, ast.AST], scope: ast.AST
) -> set[str]:
    names: set[str] = set()
    current = node
    while current in parents:
        current = parents[current]
        if current is scope:
            break
        if isinstance(current, (ast.For, ast.AsyncFor)):
            names.update(_for_target_names(current.target))
    return names


def _member_root(expression: ast.AST) -> str:
    current = expression
    while isinstance(current, (ast.Attribute, ast.Subscript)):
        current = current.value
    return current.id if isinstance(current, ast.Name) else ""


def _coordinate_origin(
    factory: ast.Call, *, parents: dict[ast.AST, ast.AST], scope: ast.AST
) -> tuple[str, list[str]]:
    argument = factory.args[0]
    if (
        not isinstance(argument, ast.Call)
        or _method(argument) not in POINT_VALUE_CONSTRUCTORS
    ):
        return "not_a_direct_coordinate_constructor", []
    components = list(argument.args)
    expressions = [ast.unparse(component) for component in components]
    if len(components) < 2:
        return "coordinate_component_count_not_pair", expressions
    if all(isinstance(component, ast.Constant) and isinstance(component.value, (int, float)) for component in components[:2]):
        return "literal_coordinate_pair", expressions
    roots = [_member_root(component) for component in components[:2]]
    loop_targets = _enclosing_for_targets(factory, parents, scope)
    if roots[0] and roots[0] == roots[1] and roots[0] in loop_targets:
        return "iterated_record_coordinate_fields", expressions
    return "derived_or_unresolved_coordinates", expressions


def analyze_source(
    row: dict[str, Any], source_text: str, *, source_bytes: bytes | None = None
) -> dict[str, Any]:
    payload = source_bytes if source_bytes is not None else source_text.encode("utf-8")
    if _sha256_bytes(payload) != str(row.get("source_sha256") or ""):
        raise ValueError("source SHA mismatch")
    try:
        tree = ast.parse(source_text)
    except SyntaxError:
        return _base(row, "deferred", "source_ast_unparseable")
    parents = _parents(tree)
    sink_line = int(row.get("sink_line") or 0)
    sink_candidates = [
        node for node in ast.walk(tree)
        if isinstance(node, ast.Call) and int(node.lineno) == sink_line and _method(node) in SINKS
    ]
    if len(sink_candidates) != 1:
        return _base(row, "deferred", "terminal_sink_not_unique")
    sink = sink_candidates[0]
    scope = _scope_node(sink, parents)
    sink_path = _control_path(sink, parents)
    set_geometries = [
        node for node in ast.walk(scope)
        if isinstance(node, ast.Call)
        and _method(node) == "setgeometry"
        and int(node.lineno) < int(sink.lineno)
        and _control_path(node, parents) == sink_path
        and _sink_matches_feature(sink, _feature_name(node))
    ]
    if len(set_geometries) != 1:
        return _base(row, "deferred", "setgeometry_for_terminal_feature_not_unique")
    set_geometry = set_geometries[0]
    feature = _feature_name(set_geometry)
    if not feature or len(set_geometry.args) != 1 or set_geometry.keywords:
        return _base(row, "deferred", "setgeometry_payload_missing_or_ambiguous")
    try:
        factory, alias_lines = _resolve_factory(
            set_geometry.args[0],
            scope=scope,
            parents=parents,
            before_line=int(set_geometry.lineno),
            control_path=sink_path,
        )
    except ReplayDeferred as error:
        return _base(row, "deferred", str(error))
    if not factory.args:
        return _base(row, "deferred", "point_factory_arguments_missing")
    if not (int(factory.lineno) <= int(set_geometry.lineno) < int(sink.lineno)):
        return _base(row, "deferred", "point_setgeometry_sink_order_invalid")
    conflicting_writes = [
        node for node in ast.walk(scope)
        if isinstance(node, ast.Call)
        and node is not set_geometry
        and _method(node) == "setgeometry"
        and _feature_name(node) == feature
        and int(set_geometry.lineno) < int(node.lineno) < int(sink.lineno)
    ]
    if conflicting_writes:
        return _base(row, "deferred", "geometry_reassigned_before_sink")
    evidence_lines = [int(factory.lineno), int(set_geometry.lineno), int(sink.lineno), *alias_lines]
    source_lines = source_text.splitlines()
    start = max(1, min(evidence_lines) - 2)
    end = min(len(source_lines), max(evidence_lines) + 2)
    snippet = "\n".join(f"{line} | {source_lines[line - 1]}" for line in range(start, end + 1))
    unit_id = hashlib.sha256(
        json.dumps(
            {"source_sha256": row["source_sha256"], "factory_line": factory.lineno, "sink_line": sink.lineno, "rule": RULE_ID},
            sort_keys=True,
        ).encode("utf-8")
    ).hexdigest()
    coordinate_origin, coordinate_components = _coordinate_origin(
        factory, parents=parents, scope=scope
    )
    return {
        **_base(row, "complete", ""),
        "unit_id": unit_id,
        "source_span": [start, end],
        "macro_call_span": [int(factory.lineno), int(sink.lineno)],
        "point_factory_call": _name(factory.func),
        "point_factory_line": int(factory.lineno),
        "point_factory_argument_expression": ast.unparse(factory.args[0]),
        "point_factory_argument_call_names": sorted(
            {
                _name(node.func)
                for node in ast.walk(factory.args[0])
                if isinstance(node, ast.Call)
            }
        ),
        "point_factory_argument_kind": type(factory.args[0]).__name__.lower(),
        "coordinate_origin_kind": coordinate_origin,
        "coordinate_component_expressions": coordinate_components,
        "setgeometry_call": _name(set_geometry.func),
        "setgeometry_line": int(set_geometry.lineno),
        "sink_call": _name(sink.func),
        "sink_line": int(sink.lineno),
        "output_feature": feature,
        "evidence_snippet": snippet,
        "evidence_sha256": _sha256_bytes(snippet.encode("utf-8")),
        "source_verification": "verified_sha256",
    }


def analyze_path(row: dict[str, Any]) -> dict[str, Any]:
    path = Path(str(row.get("source_path") or ""))
    if not path.is_file():
        return _base(row, "deferred", "source_file_missing")
    payload = path.read_bytes()
    result = analyze_source(row, payload.decode("utf-8-sig", errors="replace"), source_bytes=payload)
    # All rows, including deferred ones, need the same authority basis before splitting.
    result.update(source_authority(path, source_sha256=str(row["source_sha256"])))
    return result


def split_source_authorities(rows: list[dict[str, Any]], *, seed: int) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        authority = str(row.get("source_authority_key") or row.get("source_sha256") or "")
        groups[authority].append(row)
    calibration: list[dict[str, Any]] = []
    holdout: list[dict[str, Any]] = []
    for authority, members in sorted(groups.items(), key=lambda item: hashlib.sha256(f"{seed}:{item[0]}".encode()).hexdigest()):
        target = calibration if len(calibration) <= len(holdout) else holdout
        split = "calibration" if target is calibration else "holdout"
        target.extend({**row, "review_split": split} for row in members)
    return calibration, holdout


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    with path.open(encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def _sha256(path: Path) -> str:
    return _sha256_bytes(path.read_bytes())


def _atomic_write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", newline="", dir=path.parent, delete=False) as handle:
        handle.write(content)
        temporary = Path(handle.name)
    temporary.replace(path)


def _write_json(path: Path, value: Any) -> None:
    _atomic_write(path, json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n")


def _write_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> None:
    _atomic_write(path, "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--expected-source-rows", type=int, default=200)
    parser.add_argument("--seed", type=int, default=20260805)
    args = parser.parse_args()
    if args.output_dir.exists() and any(args.output_dir.iterdir()):
        raise ValueError(f"output directory is not empty: {args.output_dir}")
    population = _read_jsonl(args.manifest)
    if len(population) != args.expected_source_rows:
        raise ValueError("source calibration manifest row count mismatch")
    if len({str(row.get("source_sha256")) for row in population}) != len(population):
        raise ValueError("source calibration manifest has duplicate source SHA")
    replay = [analyze_path(row) for row in population]
    complete = [row for row in replay if row["macro_status"] == "complete"]
    calibration, holdout = split_source_authorities(replay, seed=args.seed)
    calibration_authorities = {str(row.get("source_authority_key") or row["source_sha256"]) for row in calibration}
    holdout_authorities = {str(row.get("source_authority_key") or row["source_sha256"]) for row in holdout}
    if calibration_authorities & holdout_authorities:
        raise ValueError("normalized-body authority leaks between calibration and holdout")
    args.output_dir.mkdir(parents=True, exist_ok=True)
    outputs = {
        "population_replay_v1.jsonl": replay,
        "complete_population_v1.jsonl": complete,
        "deferred_population_v1.jsonl": [row for row in replay if row["macro_status"] != "complete"],
        "calibration_review_v1.jsonl": calibration,
        "holdout_review_v1.jsonl": holdout,
    }
    paths: list[Path] = []
    for name, rows in outputs.items():
        path = args.output_dir / name
        _write_jsonl(path, rows)
        paths.append(path)
    summary_path = args.output_dir / "summary_v1.json"
    _write_json(summary_path, {
        "schema": "gis_recommend.qgis_api_point_geometry_replay_summary.v1",
        "point_geometry_rule_id": RULE_ID,
        "input_source_rows": len(population),
        "source_sha_verified": sum(row.get("source_verification") == "verified_sha256" for row in replay),
        "normalized_body_authorities": len({str(row.get("source_authority_key")) for row in replay if row.get("source_authority_key")}),
        "complete_units": len(complete),
        "complete_normalized_body_authorities": len({str(row.get("source_authority_key")) for row in complete}),
        "deferred_units": len(replay) - len(complete),
        "deferred_reason_counts": dict(sorted(Counter(str(row["deferred_reason"]) for row in replay if row["macro_status"] != "complete").items())),
        "review_seed": args.seed,
        "calibration_rows": len(calibration),
        "holdout_rows": len(holdout),
        "calibration_holdout_authority_overlap": 0,
        "training_rows_emitted": 0,
        "training_admission": "not_granted_source_replay_only",
        "llm_called": False,
    })
    paths.append(summary_path)
    _write_json(args.output_dir / "hash_ledger_v1.json", {
        "schema": "gis_recommend.hash_ledger.v1",
        "inputs": {"manifest": {"path": str(args.manifest), "sha256": _sha256(args.manifest)}},
        "artifacts": {path.name: {"bytes": path.stat().st_size, "sha256": _sha256(path)} for path in paths},
    })
    print(summary_path.read_text(encoding="utf-8"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
