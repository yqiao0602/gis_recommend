#!/usr/bin/env python3
"""Replay strict coordinate-transform local macros against source files.

v1 accepts the provable chain:
    geom_var.transform(coord_transform)      # QgsGeometry.transform(...)
      -> same-feature setGeometry(geom_var)
      -> literal single-feature sink (addFeature/addFeatures)

coord_transform must be a unique same-control-path alias or a literal
QgsCoordinateTransform construction.  geom_var must be a unique same-control-
path alias (e.g. from f.geometry()).  Everything else fails closed.
"""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import tempfile
from collections import Counter
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

RULE_ID = "qgis-api-coordinate-transform-local-macro-v1"
SINKS = {"addfeature", "addfeatures"}
UNION_METHOD = "unaryunion"
CT_FACTORY = "unused"


class ReplayDeferred(Exception):
    """Carry a stable fail-closed reason out of AST resolution."""


def _sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _method(node: ast.Call) -> str:
    return _name(node.func).rsplit(".", 1)[-1].lower()


def _base(row: dict[str, Any], status: str, reason: str) -> dict[str, Any]:
    return {
        **row,
        "schema": "gis_recommend.qgis_api_unary_union_replay.v1",
        "unary_union_rule_id": RULE_ID,
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
        raise ReplayDeferred("unary_union_alias_not_unique_or_not_same_control_path")
    return matches[0]


def _is_ct_construction(call: ast.Call) -> bool:
    return _name(call.func).lower() == CT_FACTORY or _name(call.func).lower().endswith(f".{CT_FACTORY}")


def _resolve_coord_transform(
    argument: ast.AST, *, scope: ast.AST, parents: dict[ast.AST, ast.AST], before_line: int, control_path: tuple[str, ...]
) -> tuple[ast.AST, list[int]]:
    """coord_transform must be a QgsCoordinateTransform construction or a unique alias."""
    if isinstance(argument, ast.Call) and _is_ct_construction(argument):
        return argument, []
    if not isinstance(argument, ast.Name):
        raise ReplayDeferred("coord_transform_not_construction_or_unique_alias")
    assignment = _single_assignment(argument.id, scope=scope, parents=parents, before_line=before_line, control_path=control_path)
    if not (isinstance(assignment.value, ast.Call) and _is_ct_construction(assignment.value)):
        raise ReplayDeferred("coord_transform_not_construction_or_unique_alias")
    return assignment.value, [int(assignment.lineno)]


def _feature_name(call: ast.Call) -> str:
    return _name(call.func.value) if isinstance(call.func, ast.Attribute) else ""


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
    sink_path = _control_path(sink, parents)
    transforms = [
        node
        for node in ast.walk(scope)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr.lower() == UNION_METHOD
        and int(node.lineno) < int(sink.lineno)
        and _control_path(node, parents) == sink_path
    ]
    if len(transforms) != 1:
        return _base(row, "deferred", "unary_union_call_not_unique")
    transform_call = transforms[0]
    receiver = transform_call.func.value
    if not isinstance(receiver, ast.Name):
        return _base(row, "deferred", "transform_receiver_not_simple_name")
    geom_var = receiver.id
    union_parent = parents.get(transform_call)
    union_target = None
    if isinstance(union_parent, (ast.Assign, ast.AnnAssign)):
        targets = union_parent.targets if isinstance(union_parent, ast.Assign) else [union_parent.target]
        if len(targets) == 1 and isinstance(targets[0], ast.Name):
            union_target = targets[0].id
    payload_var = union_target or geom_var
    if transform_call.args:
        return _base(row, "deferred", "unary_union_argument_count_not_zero")
    ct_lines: list[int] = []
    set_calls = [
        node
        for node in ast.walk(scope)
        if isinstance(node, ast.Call)
        and _method(node) == "setgeometry"
        and _feature_name(node) == feature
        and int(node.lineno) < int(sink.lineno)
        and _control_path(node, parents) == sink_path
        and isinstance(node.args[0], ast.Name)
        and node.args[0].id == payload_var
    ]
    if len(set_calls) != 1:
        return _base(row, "deferred", "setgeometry_for_unary_union_result_not_unique")
    set_call = set_calls[0]
    try:
        assignment = _single_assignment(
            geom_var,
            scope=scope,
            parents=parents,
            before_line=int(transform_call.lineno),
            control_path=sink_path,
        )
    except ReplayDeferred as error:
        return _base(row, "deferred", str(error))
    result = _base(row, "complete", "")
    result.update(
        {
            "vertex_sequence_kind": "geometry_unary_union_chain",
            "vertex_count": 0,
            "source_span": [int(assignment.lineno), int(sink.lineno)],
            "unary_union_factory_line": int(ct_lines[0]) if ct_lines else None,
            "transform_call_line": int(transform_call.lineno),
            "setgeometry_line": int(set_call.lineno),
            "evidence_snippet": "\n".join(
                f"{i + 1} | {line}"
                for i, line in enumerate(source_text.splitlines())
                if int(assignment.lineno) <= i + 1 <= int(sink.lineno) + 1
            ),
            "source_authority_key": f"normalized_source_body_sha256:{source_authority(Path(row['source_path']), source_sha256=str(row.get('source_sha256') or '')).get('normalized_source_body_sha256', '')}",
        }
    )
    return result


def analyze_path(row: dict[str, Any]) -> dict[str, Any]:
    from pathlib import Path as _P

    raw = str(row.get("source_path") or "")
    path = _P(raw) if raw.startswith("/home/yll") else _P("/home/yll") / raw.lstrip("/")
    if not path.is_file():
        return _base(row, "deferred", "source_file_missing")
    actual = _sha256(path.read_bytes())
    if actual != str(row.get("source_sha256") or ""):
        return _base(row, "deferred", "source_sha256_mismatch")
    return analyze_source(row, path.read_text(encoding="utf-8-sig", errors="replace"), source_bytes=path.read_bytes())


def split_source_authorities(rows: list[dict[str, Any]], *, seed: int) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    import random
    from collections import defaultdict

    rng = random.Random(seed)
    by_authority: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        by_authority[str(row.get("source_authority_key") or "")].append(row)
    calibration: list[dict[str, Any]] = []
    holdout: list[dict[str, Any]] = []
    for authority, members in sorted(by_authority.items()):
        target = holdout if rng.random() < 0.5 else calibration
        target.extend(members)
    return calibration, holdout


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _write_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> None:
    path.write_text("".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows), encoding="utf-8")


def _write_json(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--expected-source-rows", type=int, default=200)
    parser.add_argument("--seed", type=int, default=20260809)
    parser.add_argument("--require-source-sha-disjoint", action="store_true")
    args = parser.parse_args()
    if args.output_dir.exists() and any(args.output_dir.iterdir()):
        raise ValueError(f"output directory is not empty: {args.output_dir}")
    population = _read_jsonl(args.manifest)
    if len(population) != args.expected_source_rows:
        raise ValueError("source replay manifest row count mismatch")
    if args.require_source_sha_disjoint and len({row["source_sha256"] for row in population}) != len(population):
        raise ValueError("source calibration manifest is not source-SHA disjoint")
    replay = [analyze_path(row) for row in population]
    complete = [row for row in replay if row["macro_status"] == "complete"]
    calibration, holdout = split_source_authorities(replay, seed=args.seed)
    if {row.get("source_authority_key") for row in calibration} & {row.get("source_authority_key") for row in holdout}:
        raise ValueError("normalized-body authority leaks between calibration and holdout")
    args.output_dir.mkdir(parents=True, exist_ok=True)
    for name, rows in {
        "population_replay_v1.jsonl": replay,
        "complete_population_v1.jsonl": complete,
        "deferred_population_v1.jsonl": [row for row in replay if row["macro_status"] != "complete"],
        "calibration_review_v1.jsonl": calibration,
        "holdout_review_v1.jsonl": holdout,
    }.items():
        _write_jsonl(args.output_dir / name, rows)
    _write_json(
        args.output_dir / "summary_v1.json",
        {
            "schema": "gis_recommend.qgis_api_unary_union_replay_summary.v1",
            "unary_union_rule_id": RULE_ID,
            "input_source_rows": len(population),
            "input_source_sha_unique": len({row["source_sha256"] for row in population}),
            "source_sha_verified": sum(row.get("source_verification") == "verified_sha256" for row in replay),
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
        },
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
