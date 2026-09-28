#!/usr/bin/env python3
"""Replay strict setAttribute local macros against source files.

v1 accepts the provable chain (inside one scope, same control path):
    feature.setAttribute('field_name', literal_value)   # literal name + value
      -> literal single-feature sink (addFeature)

The field name must be a literal string; the value a literal constant or a
unique same-control-path alias of one.  The sink is anchored by target sink
line.  Everything else fails closed.
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

RULE_ID = "qgis-api-setattribute-local-macro-v1"
SINKS = {"addfeature"}



class ReplayDeferred(Exception):
    """Carry a stable fail-closed reason out of AST resolution."""


def _sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _method(node: ast.Call) -> str:
    return _name(node.func).rsplit(".", 1)[-1].lower()


def _base(row: dict[str, Any], status: str, reason: str) -> dict[str, Any]:
    return {
        **row,
        "schema": "gis_recommend.qgis_api_setattribute_replay.v1",
        "setattribute_rule_id": RULE_ID,
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
        raise ReplayDeferred("addattributes_alias_not_unique_or_not_same_control_path")
    return matches[0]


def _resolve_setattribute(
    call: ast.Call, *, scope: ast.AST, parents: dict[ast.AST, ast.AST]
) -> tuple[str, Any, list[int]] | None:
    """Resolve setAttribute(field_name, value).

    Returns (field_name, value, alias_lines) where field_name is a literal
    string and value is a literal constant or a unique same-control-path
    alias of one; None otherwise (fail closed).
    """
    if len(call.args) != 2:
        return None
    name_node = call.args[0]
    if not isinstance(name_node, ast.Constant) or not isinstance(name_node.value, str):
        return None
    value_node = call.args[1]
    if isinstance(value_node, ast.Constant):
        return name_node.value, value_node.value, []
    if isinstance(value_node, ast.Name):
        try:
            assignment = _single_assignment(
                value_node.id,
                scope=scope,
                parents=parents,
                before_line=int(call.lineno),
                control_path=_control_path(call, parents),
            )
        except ReplayDeferred:
            return None
        if isinstance(assignment.value, ast.Constant):
            return name_node.value, assignment.value.value, [int(assignment.lineno)]
    return None


def _feature_names(call: ast.Call) -> list[str]:
    """Feature names from the sink payload (addFeature name only)."""
    if _method(call) == "addfeature" and call.args and isinstance(call.args[0], ast.Name):
        return [call.args[0].id]
    return []


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
    if not _feature_names(sink):
        return _base(row, "deferred", "terminal_sink_not_literal_single_feature")
    scope = _scope_node(sink, parents)
    sink_path = _control_path(sink, parents)
    set_calls = [
        node
        for node in ast.walk(scope)
        if isinstance(node, ast.Call)
        and _method(node) == "setattribute"
        and int(node.lineno) < int(sink.lineno)
        and _control_path(node, parents) == sink_path
    ]
    if len(set_calls) != 1:
        return _base(row, "deferred", "setattribute_call_not_unique")
    set_call = set_calls[0]
    resolved = _resolve_setattribute(set_call, scope=scope, parents=parents)
    if resolved is None:
        return _base(row, "deferred", "setattribute_name_or_value_not_literal_or_unique_alias")
    field_name, value, value_alias_lines = resolved
    evidence_lines = [int(set_call.lineno), int(sink.lineno), *value_alias_lines]
    lines = source_text.splitlines()
    start, end = max(1, min(evidence_lines) - 2), min(len(lines), max(evidence_lines) + 2)
    result = _base(row, "complete", "")
    result.update(
        {
            "setattribute_field_name": field_name,
            "setattribute_value_kind": "literal_value" if not value_alias_lines else "unique_literal_value_alias",
            "setattribute_call_line": int(set_call.lineno),
            "sink_call": _method(sink),
            "sink_line": int(sink.lineno),
            "source_span": [start, end],
            "evidence_snippet": "\n".join(f"{i + 1} | {line}" for i, line in enumerate(lines) if start <= i + 1 <= end),
            "source_authority_key": f"normalized_source_body_sha256:{source_authority(Path(row['source_path']), source_sha256=str(row.get('source_sha256') or '')).get('normalized_source_body_sha256', '')}",
            "source_verification": "verified_sha256",
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
    result = analyze_source(row, path.read_text(encoding="utf-8-sig", errors="replace"), source_bytes=path.read_bytes())
    result.update(source_authority(path, source_sha256=str(row.get("source_sha256") or "")))
    return result


def split_source_authorities(rows: list[dict[str, Any]], *, seed: int) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    import random
    from collections import defaultdict

    rng = random.Random(seed)
    by_authority: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        by_authority[str(row.get("normalized_source_body_sha256") or row.get("source_sha256") or "")].append(row)
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
    parser.add_argument("--seed", type=int, default=20260810)
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
    if {
        row.get("normalized_source_body_sha256") or row.get("source_sha256") for row in calibration
    } & {
        row.get("normalized_source_body_sha256") or row.get("source_sha256") for row in holdout
    }:
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
            "schema": "gis_recommend.qgis_api_setattribute_replay_summary.v1",
            "setattribute_rule_id": RULE_ID,
            "input_source_rows": len(population),
            "input_source_sha_unique": len({row["source_sha256"] for row in population}),
            "source_sha_verified": sum(row.get("source_verification") == "verified_sha256" for row in replay),
            "complete_units": len(complete),
            "complete_normalized_body_authorities": len({row.get("normalized_source_body_sha256") for row in complete}),
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
