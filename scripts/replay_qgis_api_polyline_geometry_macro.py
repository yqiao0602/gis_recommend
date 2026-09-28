#!/usr/bin/env python3
"""Replay strict polyline-construction local macros against source files."""

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

RULE_ID = "qgis-api-polyline-geometry-local-macro-v1"
FACTORIES = {"qgsgeometry.frompolyline", "qgsgeometry.frompolylinexy"}
POINTS = {"qgspoint", "qgspointxy"}
SINKS = {"addfeature", "addfeatures"}


class ReplayDeferred(Exception):
    """Carry a stable fail-closed reason out of AST resolution."""


def _sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _method(node: ast.Call) -> str:
    return _name(node.func).rsplit(".", 1)[-1].lower()


def _base(row: dict[str, Any], status: str, reason: str) -> dict[str, Any]:
    return {
        **row,
        "schema": "gis_recommend.qgis_api_polyline_geometry_replay.v1",
        "polyline_geometry_rule_id": RULE_ID,
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


def _valid_sequence(value: ast.AST) -> int:
    if not isinstance(value, (ast.List, ast.Tuple)) or len(value.elts) < 2:
        return 0
    if all(
        isinstance(item, ast.Call) and _name(item.func).lower() in POINTS
        for item in value.elts
    ):
        return len(value.elts)
    return 0


def _single_assignment(
    name: str, *, scope: ast.AST, parents: dict[ast.AST, ast.AST], before_line: int, control_path: tuple[str, ...]
) -> ast.Assign | ast.AnnAssign:
    matches: list[ast.Assign | ast.AnnAssign] = []
    for node in ast.walk(scope):
        if not isinstance(node, (ast.Assign, ast.AnnAssign)) or int(node.lineno) >= before_line:
            continue
        targets = node.targets if isinstance(node, ast.Assign) else [node.target]
        if any(isinstance(target, ast.Name) and target.id == name for target in targets) and _control_path(node, parents) == control_path:
            matches.append(node)
    if len(matches) != 1:
        raise ReplayDeferred("polyline_alias_not_unique_or_not_same_control_path")
    return matches[0]


def _resolve_factory(
    payload: ast.AST, *, scope: ast.AST, parents: dict[ast.AST, ast.AST], before_line: int, control_path: tuple[str, ...]
) -> tuple[ast.Call, list[int]]:
    if isinstance(payload, ast.Call) and _name(payload.func).lower() in FACTORIES:
        return payload, []
    if not isinstance(payload, ast.Name):
        raise ReplayDeferred("setgeometry_payload_not_direct_polyline_factory")
    assignment = _single_assignment(payload.id, scope=scope, parents=parents, before_line=before_line, control_path=control_path)
    if not isinstance(assignment.value, ast.Call) or _name(assignment.value.func).lower() not in FACTORIES:
        raise ReplayDeferred("setgeometry_payload_not_direct_polyline_factory")
    return assignment.value, [int(assignment.lineno)]


def _resolve_vertex_sequence(
    factory: ast.Call, *, scope: ast.AST, parents: dict[ast.AST, ast.AST], control_path: tuple[str, ...]
) -> tuple[int, str, list[int]]:
    if len(factory.args) != 1:
        raise ReplayDeferred("polyline_factory_argument_count_not_one")
    argument = factory.args[0]
    count = _valid_sequence(argument)
    if count:
        return count, "literal_point_sequence", []
    if not isinstance(argument, ast.Name):
        raise ReplayDeferred("polyline_vertex_sequence_not_literal_or_unique_alias")
    try:
        assignment = _single_assignment(
            argument.id,
            scope=scope,
            parents=parents,
            before_line=int(factory.lineno),
            control_path=control_path,
        )
    except ReplayDeferred as error:
        raise ReplayDeferred(
            "polyline_vertex_sequence_not_literal_or_unique_alias"
        ) from error
    count = _valid_sequence(assignment.value)
    if not count:
        raise ReplayDeferred("polyline_vertex_sequence_not_literal_or_unique_alias")
    return count, "unique_literal_point_sequence_alias", [int(assignment.lineno)]


def _feature_name(call: ast.Call) -> str:
    return _name(call.func.value) if isinstance(call.func, ast.Attribute) else ""


def _sink_matches_feature(call: ast.Call, feature: str) -> bool:
    if _method(call) == "addfeature":
        return len(call.args) == 1 and isinstance(call.args[0], ast.Name) and call.args[0].id == feature
    return (
        _method(call) == "addfeatures"
        and len(call.args) == 1
        and isinstance(call.args[0], ast.List)
        and len(call.args[0].elts) == 1
        and isinstance(call.args[0].elts[0], ast.Name)
        and call.args[0].elts[0].id == feature
    )


def _sink_feature(call: ast.Call) -> str:
    if _method(call) == "addfeature" and len(call.args) == 1:
        return call.args[0].id if isinstance(call.args[0], ast.Name) else ""
    if (
        _method(call) == "addfeatures"
        and len(call.args) == 1
        and isinstance(call.args[0], ast.List)
        and len(call.args[0].elts) == 1
        and isinstance(call.args[0].elts[0], ast.Name)
    ):
        return call.args[0].elts[0].id
    return ""


def analyze_source(row: dict[str, Any], source_text: str, *, source_bytes: bytes | None = None) -> dict[str, Any]:
    try:
        tree = ast.parse(source_text)
    except SyntaxError:
        return _base(row, "deferred", "source_ast_unparseable")
    parents = _parents(tree)
    target_sink_line = int(row.get("sink_line") or 0)
    target_sinks = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and _method(node) in SINKS
        and int(node.lineno) == target_sink_line
    ]
    if len(target_sinks) != 1:
        return _base(row, "deferred", "terminal_sink_not_unique_at_discovery_anchor")
    sink = target_sinks[0]
    feature = _sink_feature(sink)
    if not feature:
        return _base(row, "deferred", "terminal_sink_not_literal_single_feature")
    scope = _scope_node(sink, parents)
    factory_path = _control_path(sink, parents)
    set_calls = [
        node
        for node in ast.walk(scope)
        if isinstance(node, ast.Call)
        and _method(node) == "setgeometry"
        and _feature_name(node) == feature
        and int(node.lineno) < int(sink.lineno)
        and _control_path(node, parents) == factory_path
    ]
    matches: list[tuple[ast.Call, ast.Call, list[int]]] = []
    for set_call in set_calls:
        if len(set_call.args) != 1:
            continue
        try:
            factory, aliases = _resolve_factory(set_call.args[0], scope=scope, parents=parents, before_line=int(set_call.lineno), control_path=factory_path)
        except ReplayDeferred:
            continue
        matches.append((set_call, factory, aliases))
    if len(matches) != 1:
        return _base(row, "deferred", "setgeometry_for_polyline_factory_not_unique")
    set_call, factory, factory_alias_lines = matches[0]
    try:
        vertex_count, vertex_kind, vertex_alias_lines = _resolve_vertex_sequence(
            factory, scope=scope, parents=parents, control_path=factory_path
        )
    except ReplayDeferred as error:
        return _base(row, "deferred", str(error))
    conflicting = [
        node for node in set_calls
        if _feature_name(node) == feature and int(set_call.lineno) < int(node.lineno) < int(sink.lineno)
    ]
    if conflicting:
        return _base(row, "deferred", "geometry_reassigned_before_sink")
    evidence_lines = [int(factory.lineno), int(set_call.lineno), int(sink.lineno), *factory_alias_lines, *vertex_alias_lines]
    lines = source_text.splitlines()
    start, end = max(1, min(evidence_lines) - 2), min(len(lines), max(evidence_lines) + 2)
    snippet = "\n".join(f"{line} | {lines[line - 1]}" for line in range(start, end + 1))
    return {
        **_base(row, "complete", ""),
        "unit_id": hashlib.sha256(json.dumps({"source_sha256": row["source_sha256"], "factory_line": factory.lineno, "sink_line": sink.lineno, "rule": RULE_ID}, sort_keys=True).encode()).hexdigest(),
        "source_span": [start, end],
        "macro_call_span": [int(factory.lineno), int(sink.lineno)],
        "polyline_factory_call": _name(factory.func),
        "polyline_factory_line": int(factory.lineno),
        "vertex_sequence_kind": vertex_kind,
        "vertex_count": vertex_count,
        "setgeometry_call": _name(set_call.func),
        "setgeometry_line": int(set_call.lineno),
        "sink_call": _name(sink.func),
        "sink_line": int(sink.lineno),
        "output_feature": feature,
        "evidence_snippet": snippet,
        "evidence_sha256": _sha256(snippet.encode()),
        "source_verification": "verified_sha256",
    }


def analyze_path(row: dict[str, Any]) -> dict[str, Any]:
    path = Path(str(row.get("source_path") or ""))
    if not path.is_file():
        return _base(row, "deferred", "source_file_missing")
    payload = path.read_bytes()
    result = analyze_source(row, payload.decode("utf-8-sig", errors="replace"), source_bytes=payload)
    result.update(source_authority(path, source_sha256=str(row["source_sha256"])))
    return result


def split_source_authorities(rows: list[dict[str, Any]], *, seed: int) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        groups[str(row.get("source_authority_key") or row.get("source_sha256") or "")].append(row)
    calibration: list[dict[str, Any]] = []
    holdout: list[dict[str, Any]] = []
    for authority, members in sorted(groups.items(), key=lambda item: _sha256(f"{seed}:{item[0]}".encode())):
        target = calibration if len(calibration) <= len(holdout) else holdout
        split = "calibration" if target is calibration else "holdout"
        target.extend({**row, "review_split": split} for row in members)
    return calibration, holdout


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    with path.open(encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", newline="", dir=path.parent, delete=False) as handle:
        json.dump(value, handle, ensure_ascii=False, indent=2, sort_keys=True)
        handle.write("\n")
        temporary = Path(handle.name)
    temporary.replace(path)


def _write_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", newline="", dir=path.parent, delete=False) as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
        temporary = Path(handle.name)
    temporary.replace(path)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--expected-source-rows", type=int, default=200)
    parser.add_argument("--seed", type=int, default=20260805)
    parser.add_argument("--require-source-sha-disjoint", action="store_true")
    args = parser.parse_args()
    if args.output_dir.exists() and any(args.output_dir.iterdir()):
        raise ValueError(f"output directory is not empty: {args.output_dir}")
    population = _read_jsonl(args.manifest)
    if len(population) != args.expected_source_rows:
        raise ValueError("source replay manifest row count mismatch")
    if any(len(str(row.get("source_sha256") or "")) != 64 for row in population):
        raise ValueError("source replay manifest contains an invalid source SHA")
    if args.require_source_sha_disjoint and len({row["source_sha256"] for row in population}) != len(population):
        raise ValueError("source calibration manifest is not source-SHA disjoint")
    replay = [analyze_path(row) for row in population]
    complete = [row for row in replay if row["macro_status"] == "complete"]
    calibration, holdout = split_source_authorities(replay, seed=args.seed)
    left = {row.get("source_authority_key") for row in calibration}
    right = {row.get("source_authority_key") for row in holdout}
    if left & right:
        raise ValueError("normalized-body authority leaks between calibration and holdout")
    args.output_dir.mkdir(parents=True, exist_ok=True)
    outputs = {
        "population_replay_v1.jsonl": replay,
        "complete_population_v1.jsonl": complete,
        "deferred_population_v1.jsonl": [row for row in replay if row["macro_status"] != "complete"],
        "calibration_review_v1.jsonl": calibration,
        "holdout_review_v1.jsonl": holdout,
    }
    for name, rows in outputs.items():
        _write_jsonl(args.output_dir / name, rows)
    summary = {
        "schema": "gis_recommend.qgis_api_polyline_geometry_replay_summary.v1",
        "polyline_geometry_rule_id": RULE_ID,
        "input_source_rows": len(population),
        "input_source_sha_unique": len({row["source_sha256"] for row in population}),
        "input_source_sha_disjoint_required": bool(args.require_source_sha_disjoint),
        "source_sha_verified": sum(row.get("source_verification") == "verified_sha256" for row in replay),
        "normalized_body_authorities": len({row.get("source_authority_key") for row in replay}),
        "complete_units": len(complete),
        "complete_normalized_body_authorities": len({row.get("source_authority_key") for row in complete}),
        "deferred_units": len(replay) - len(complete),
        "deferred_reason_counts": dict(sorted(Counter(row["deferred_reason"] for row in replay if row["macro_status"] != "complete").items())),
        "calibration_rows": len(calibration),
        "holdout_rows": len(holdout),
        "calibration_holdout_authority_overlap": 0,
        "training_rows_emitted": 0,
        "training_admission": "not_granted_source_replay_only",
        "llm_called": False,
    }
    _write_json(args.output_dir / "summary_v1.json", summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
