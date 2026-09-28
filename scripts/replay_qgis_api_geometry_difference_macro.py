#!/usr/bin/env python3
"""Replay bounded geometry-difference macros from verified QGIS API sources."""

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

from scripts.analyze_qgis_api_mutation_upstream import (
    _control_path,
    _definitions,
    _name,
    _parents,
    _scope_node,
)

RULE_ID = "qgis-api-geometry-difference-local-macro-v1"
L3_CODE = "L3_02_02_04"
GEOMETRY_ACCESSORS = {"geometry", "constgeometry"}
GEOMETRY_WRAPPERS = {"qgsgeometry"}
SAFE_GEOMETRY_OBSERVERS = {
    "boundingbox",
    "isempty",
    "isgeosempty",
    "isgeosvalid",
    "isnull",
    "type",
    "wkbtype",
}


class ReplayDeferred(Exception):
    """Carry a stable fail-closed reason out of the AST replay."""

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _method(node: ast.Call) -> str:
    return _name(node.func).rsplit(".", 1)[-1].lower()


def _is_path_prefix(prefix: tuple[str, ...], path: tuple[str, ...]) -> bool:
    return len(prefix) <= len(path) and path[: len(prefix)] == prefix


def _definition(
    name: str,
    *,
    scope: ast.AST,
    parents: dict[ast.AST, ast.AST],
    before_line: int,
    use_path: tuple[str, ...],
) -> dict[str, Any]:
    rows = [
        row
        for row in _definitions(scope, parents, before_line).get(name, [])
        if _is_path_prefix(tuple(row["control_path"]), use_path)
    ]
    if not rows:
        raise ReplayDeferred("operand_or_alias_definition_missing")
    latest_line = max(int(row["line"]) for row in rows)
    latest = [row for row in rows if int(row["line"]) == latest_line]
    if len(latest) != 1:
        raise ReplayDeferred("ambiguous_payload_alias")
    return latest[0]


def _unwrap_difference_call(expression: ast.AST) -> ast.Call | None:
    current = expression
    while (
        isinstance(current, ast.Call)
        and _method(current) in GEOMETRY_WRAPPERS
        and len(current.args) == 1
        and not current.keywords
    ):
        current = current.args[0]
    if isinstance(current, ast.Call) and _method(current) == "difference":
        return current
    return None


def _enclosed_by_loop(node: ast.AST, parents: dict[ast.AST, ast.AST]) -> bool:
    current: ast.AST | None = node
    while current is not None:
        if isinstance(current, (ast.For, ast.AsyncFor, ast.While)):
            return True
        if isinstance(current, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)):
            return False
        current = parents.get(current)
    return False


def _common_path_length(left: tuple[str, ...], right: tuple[str, ...]) -> int:
    count = 0
    for left_item, right_item in zip(left, right):
        if left_item != right_item:
            break
        count += 1
    return count


def _enclosing_loop_lines(
    node: ast.AST, parents: dict[ast.AST, ast.AST]
) -> tuple[int, ...]:
    lines: list[int] = []
    current: ast.AST | None = node
    while current is not None:
        if isinstance(current, (ast.For, ast.AsyncFor, ast.While)):
            lines.append(int(current.lineno))
        if isinstance(current, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)):
            break
        current = parents.get(current)
    return tuple(reversed(lines))


def _mutually_exclusive_if_paths(
    left: tuple[str, ...], right: tuple[str, ...]
) -> bool:
    left_arms = {
        item.rsplit(":", 1)[0]: item.rsplit(":", 1)[-1]
        for item in left
        if item.startswith("if:")
    }
    right_arms = {
        item.rsplit(":", 1)[0]: item.rsplit(":", 1)[-1]
        for item in right
        if item.startswith("if:")
    }
    return any(
        key in right_arms and arm != right_arms[key]
        for key, arm in left_arms.items()
    )


def _loop_carried_difference(
    name: str,
    *,
    scope: ast.AST,
    parents: dict[ast.AST, ast.AST],
    before_line: int,
    use_path: tuple[str, ...],
) -> tuple[ast.Call, list[int]] | None:
    definitions = _definitions(scope, parents, before_line).get(name, [])
    candidates: list[tuple[dict[str, Any], ast.Call]] = []
    for definition in definitions:
        difference = _unwrap_difference_call(definition["value"])
        if (
            difference is not None
            and isinstance(difference.func, ast.Attribute)
            and _name(difference.func.value) == name
            and _enclosed_by_loop(difference, parents)
        ):
            candidates.append((definition, difference))
    if not candidates:
        return None
    maximum_prefix = max(
        _common_path_length(tuple(item[0]["control_path"]), use_path)
        for item in candidates
    )
    selected = [
        item
        for item in candidates
        if _common_path_length(tuple(item[0]["control_path"]), use_path)
        == maximum_prefix
    ]
    latest_line = max(int(item[0]["line"]) for item in selected)
    selected = [item for item in selected if int(item[0]["line"]) == latest_line]
    if len(selected) != 1:
        raise ReplayDeferred("ambiguous_loop_carried_difference")
    update, difference = selected[0]
    update_line = int(update["line"])
    later_assignments = [
        row
        for row in definitions
        if update_line < int(row["line"]) < before_line
        and _is_path_prefix(
            tuple(row["control_path"][:maximum_prefix]),
            use_path[:maximum_prefix],
        )
    ]
    if later_assignments:
        raise ReplayDeferred("geometry_reassigned_after_difference")
    unsafe_calls = [
        node
        for node in ast.walk(scope)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and _name(node.func.value) == name
        and update_line < int(node.lineno) < before_line
        and _method(node) not in SAFE_GEOMETRY_OBSERVERS
    ]
    if unsafe_calls:
        raise ReplayDeferred("downstream_geometry_transform_or_mutation")
    return difference, [update_line]


def _resolve_payload_difference(
    expression: ast.AST,
    *,
    scope: ast.AST,
    parents: dict[ast.AST, ast.AST],
    before_line: int,
    use_path: tuple[str, ...],
    visited: frozenset[str] = frozenset(),
) -> tuple[ast.Call, list[int]]:
    if isinstance(expression, ast.Name):
        if expression.id in visited:
            raise ReplayDeferred("cyclic_payload_alias")
        loop_carried = _loop_carried_difference(
            expression.id,
            scope=scope,
            parents=parents,
            before_line=before_line,
            use_path=use_path,
        )
        if loop_carried is not None:
            return loop_carried
        definition = _definition(
            expression.id,
            scope=scope,
            parents=parents,
            before_line=before_line,
            use_path=use_path,
        )
        call, lines = _resolve_payload_difference(
            definition["value"],
            scope=scope,
            parents=parents,
            before_line=int(definition["line"]),
            use_path=use_path,
            visited=visited | {expression.id},
        )
        return call, [int(definition["line"]), *lines]
    if not isinstance(expression, ast.Call):
        raise ReplayDeferred("difference_result_provenance_incomplete")
    method = _method(expression)
    if method == "difference":
        if len(expression.args) != 1 or expression.keywords:
            raise ReplayDeferred("difference_signature_not_exact")
        return expression, []
    if method in GEOMETRY_WRAPPERS and len(expression.args) == 1 and not expression.keywords:
        return _resolve_payload_difference(
            expression.args[0],
            scope=scope,
            parents=parents,
            before_line=int(expression.lineno),
            use_path=use_path,
            visited=visited,
        )
    raise ReplayDeferred("downstream_geometry_transform_or_external_call")


def _prove_geometry_operand(
    expression: ast.AST,
    *,
    scope: ast.AST,
    parents: dict[ast.AST, ast.AST],
    before_line: int,
    use_path: tuple[str, ...],
    visited: frozenset[str] = frozenset(),
) -> tuple[dict[str, Any], list[int]]:
    if isinstance(expression, ast.Name):
        if expression.id in visited:
            raise ReplayDeferred("cyclic_operand_alias")
        definition = _definition(
            expression.id,
            scope=scope,
            parents=parents,
            before_line=before_line,
            use_path=use_path,
        )
        fact, lines = _prove_geometry_operand(
            definition["value"],
            scope=scope,
            parents=parents,
            before_line=int(definition["line"]),
            use_path=use_path,
            visited=visited | {expression.id},
        )
        return fact, [int(definition["line"]), *lines]
    if not isinstance(expression, ast.Call):
        raise ReplayDeferred("difference_operand_provenance_incomplete")
    method = _method(expression)
    if method in GEOMETRY_ACCESSORS and not expression.args and not expression.keywords:
        return {
            "status": "verified_geometry_accessor",
            "source": ast.unparse(expression),
            "line": int(expression.lineno),
        }, []
    if method in GEOMETRY_WRAPPERS and len(expression.args) == 1 and not expression.keywords:
        fact, lines = _prove_geometry_operand(
            expression.args[0],
            scope=scope,
            parents=parents,
            before_line=int(expression.lineno),
            use_path=use_path,
            visited=visited,
        )
        return {**fact, "wrapped_by": _name(expression.func)}, lines
    raise ReplayDeferred("difference_operand_provenance_incomplete")


def _matching_calls(
    tree: ast.AST, targets: set[tuple[int, str]]
) -> list[ast.Call]:
    return [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and any(
            int(node.lineno) == line
            and _name(node.func).lower().endswith(name.rsplit(".", 1)[-1])
            for line, name in targets
        )
    ]


def _base(row: dict[str, Any], status: str, reason: str) -> dict[str, Any]:
    return {
        **row,
        "schema": "gis_recommend.qgis_api_geometry_difference_replay.v1",
        "contract_rule_id": RULE_ID,
        "family_id": "geometry_difference",
        "macro_status": status,
        "deferred_reason": reason,
        "mapping_status": (
            "exact_stable125_existing_l3" if status == "complete" else "not_granted"
        ),
        "candidate_l3_sequence": [L3_CODE] if status == "complete" else [],
        "family_rule_promotion": "not_granted_support_below_30",
        "description_fidelity": "not_started",
        "training_admission": "not_granted_source_replay_only",
        "training_row_emitted": False,
        "validation_eligible": False,
        "test_eligible": False,
        "production_merge": "not_granted",
        "llm_called": False,
    }


def analyze_source(
    row: dict[str, Any], source_text: str, *, source_bytes: bytes | None = None
) -> dict[str, Any]:
    actual_sha = _sha256_bytes(
        source_bytes if source_bytes is not None else source_text.encode("utf-8")
    )
    if actual_sha != str(row.get("source_sha256") or ""):
        raise ValueError("source SHA mismatch")
    tree = ast.parse(source_text)
    parents = _parents(tree)
    setgeometry_targets = {
        (int(step["line_start"]), str(step.get("call_name") or "").lower())
        for step in row.get("steps") or []
        if step.get("call_role") == "feature_mutation"
        and str(step.get("call_name") or "").lower().endswith(".setgeometry")
    }
    sink_targets = {
        (int(step["line_start"]), str(step.get("call_name") or "").lower())
        for step in row.get("steps") or []
        if step.get("call_role") == "sink_output"
    }
    setgeometry_calls = _matching_calls(tree, setgeometry_targets)
    sink_calls = _matching_calls(tree, sink_targets)
    if len(setgeometry_calls) != 1:
        return _base(row, "deferred", "setgeometry_call_not_unique")
    if len(sink_calls) != 1:
        return _base(row, "deferred", "sink_call_not_unique")
    setgeometry = setgeometry_calls[0]
    sink = sink_calls[0]
    scope = _scope_node(setgeometry, parents)
    if _scope_node(sink, parents) is not scope:
        return _base(row, "deferred", "sink_outside_geometry_scope")
    use_path = _control_path(setgeometry, parents)
    if _control_path(sink, parents) != use_path:
        return _base(row, "deferred", "sink_control_path_mismatch")
    if not setgeometry.args:
        return _base(row, "deferred", "setgeometry_payload_missing")
    feature_name = _name(setgeometry.func.value)
    if not sink.args or feature_name not in {
        item.id for item in ast.walk(sink.args[0]) if isinstance(item, ast.Name)
    }:
        return _base(row, "deferred", "sink_payload_feature_mismatch")
    try:
        difference, alias_lines = _resolve_payload_difference(
            setgeometry.args[0],
            scope=scope,
            parents=parents,
            before_line=int(setgeometry.lineno),
            use_path=use_path,
        )
        receiver_fact, receiver_lines = _prove_geometry_operand(
            difference.func.value,
            scope=scope,
            parents=parents,
            before_line=int(difference.lineno),
            use_path=_control_path(difference, parents),
        )
        argument_fact, argument_lines = _prove_geometry_operand(
            difference.args[0],
            scope=scope,
            parents=parents,
            before_line=int(difference.lineno),
            use_path=_control_path(difference, parents),
        )
    except ReplayDeferred as error:
        result = _base(row, "deferred", error.reason)
        result["setgeometry_payload_expression"] = ast.unparse(setgeometry.args[0])
        result["setgeometry_payload_call_names"] = [
            _name(node.func)
            for node in ast.walk(setgeometry.args[0])
            if isinstance(node, ast.Call)
        ]
        return result
    if not (int(difference.lineno) < int(setgeometry.lineno) <= int(sink.lineno)):
        return _base(row, "deferred", "difference_setgeometry_sink_order_invalid")
    repeated_setgeometry = []
    for node in ast.walk(scope):
        if not (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and _name(node.func.value) == feature_name
            and _method(node) == "setgeometry"
            and int(difference.lineno) < int(node.lineno) < int(sink.lineno)
            and node is not setgeometry
        ):
            continue
        node_path = _control_path(node, parents)
        mutually_exclusive = _mutually_exclusive_if_paths(node_path, use_path)
        loop_sensitive = bool(
            _enclosing_loop_lines(node, parents)
            or _enclosing_loop_lines(setgeometry, parents)
        )
        if not mutually_exclusive or loop_sensitive:
            repeated_setgeometry.append(node)
    if repeated_setgeometry:
        return _base(row, "deferred", "geometry_reassigned_before_sink")

    evidence_lines = sorted(
        {
            int(difference.lineno),
            int(setgeometry.lineno),
            int(sink.lineno),
            *alias_lines,
            *receiver_lines,
            *argument_lines,
        }
    )
    source_lines = source_text.splitlines()
    start = max(1, min(evidence_lines) - 2)
    end = min(len(source_lines), max(evidence_lines) + 2)
    snippet = "\n".join(
        f"{line} | {source_lines[line - 1]}" for line in range(start, end + 1)
    )
    payload = {
        "baseline_candidate_id": row.get("candidate_id"),
        "difference_line": int(difference.lineno),
        "setgeometry_line": int(setgeometry.lineno),
        "sink_line": int(sink.lineno),
        "contract_rule_id": RULE_ID,
    }
    unit_id = hashlib.sha256(
        json.dumps(payload, sort_keys=True).encode("utf-8")
    ).hexdigest()
    return {
        **_base(row, "complete", ""),
        "unit_id": unit_id,
        "baseline_candidate_id": str(row.get("candidate_id") or ""),
        "source_span": [start, end],
        "macro_call_span": [int(difference.lineno), int(sink.lineno)],
        "difference_call": _name(difference.func),
        "difference_call_line": int(difference.lineno),
        "setgeometry_call": _name(setgeometry.func),
        "setgeometry_call_line": int(setgeometry.lineno),
        "sink_call": _name(sink.func),
        "sink_call_line": int(sink.lineno),
        "output_feature": feature_name,
        "receiver_operand_fact": receiver_fact,
        "argument_operand_fact": argument_fact,
        "evidence_snippet": snippet,
        "evidence_sha256": _sha256_bytes(snippet.encode("utf-8")),
    }


def analyze_path(row: dict[str, Any]) -> dict[str, Any]:
    source_path = Path(str(row.get("source_path") or ""))
    if not source_path.is_file():
        return {
            **_base(row, "deferred", "source_file_missing"),
            "source_verification": "source_file_missing",
        }
    payload = source_path.read_bytes()
    return analyze_source(
        row, payload.decode("utf-8-sig", errors="replace"), source_bytes=payload
    )


def geometry_difference_authorities(anchor_rows: list[dict[str, Any]]) -> set[str]:
    anchors = [
        row for row in anchor_rows if row.get("anchor_family") == "geometry_difference"
    ]
    if len(anchors) != 1:
        raise ValueError(
            "semantic anchor must contain exactly one geometry_difference row"
        )
    return {str(value) for value in anchors[0].get("source_authority_keys") or []}


def is_geometry_difference_row(
    row: dict[str, Any], *, authority_keys: set[str] | None = None
) -> bool:
    upstream_calls = row.get("upstream_calls") or []
    if not upstream_calls:
        return False
    return (
        row.get("slice_status") == "resolved_local_call_chain"
        and str(upstream_calls[-1].get("call_name") or "")
        .rsplit(".", 1)[-1]
        .lower()
        == "difference"
        and (
            authority_keys is None
            or str(row.get("source_authority_key") or "") in authority_keys
        )
    )


def split_full_population(
    rows: list[dict[str, Any]], *, seed: int
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    by_authority: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        by_authority[str(row["source_authority_key"])].append(row)
    calibration: list[dict[str, Any]] = []
    holdout: list[dict[str, Any]] = []
    for authority, authority_rows in sorted(
        by_authority.items(),
        key=lambda item: hashlib.sha256(f"{seed}:{item[0]}".encode()).hexdigest(),
    ):
        target = calibration if len(calibration) <= len(holdout) else holdout
        split = "calibration" if target is calibration else "holdout"
        target.extend({**row, "review_split": split} for row in authority_rows)
    return calibration, holdout


def build_summary(
    population: list[dict[str, Any]], replay: list[dict[str, Any]]
) -> dict[str, Any]:
    complete = [row for row in replay if row["macro_status"] == "complete"]
    return {
        "schema": "gis_recommend.qgis_api_geometry_difference_replay_summary.v1",
        "contract_rule_id": RULE_ID,
        "input_units": len(population),
        "input_source_authorities": len(
            {str(row["source_authority_key"]) for row in population}
        ),
        "source_verified_units": sum(
            row.get("source_verification") == "verified_sha256" for row in replay
        ),
        "complete_units": len(complete),
        "complete_source_authorities": len(
            {str(row["source_authority_key"]) for row in complete}
        ),
        "deferred_units": len(replay) - len(complete),
        "deferred_reason_counts": dict(
            sorted(
                Counter(
                    str(row["deferred_reason"])
                    for row in replay
                    if row["macro_status"] != "complete"
                ).items()
            )
        ),
        "candidate_l3_sequence": [L3_CODE],
        "minimum_family_promotion_support": 30,
        "family_rule_promotion": "not_granted_support_below_30",
        "whole_population_review_required": True,
        "training_admission": "not_granted_source_replay_only",
        "training_rows_emitted": 0,
        "validation_eligible": False,
        "test_eligible": False,
        "production_merge": "not_granted",
        "llm_called": False,
    }


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    with path.open(encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def _sha256(path: Path) -> str:
    return _sha256_bytes(path.read_bytes())


def _atomic_write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "w", encoding="utf-8", newline="", dir=path.parent, delete=False
    ) as handle:
        handle.write(content)
        temporary = Path(handle.name)
    temporary.replace(path)


def _write_json(path: Path, value: Any) -> None:
    _atomic_write(
        path, json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    )


def _write_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> None:
    _atomic_write(
        path,
        "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows),
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mutation-upstream", type=Path, required=True)
    parser.add_argument("--semantic-anchor", type=Path, required=True)
    parser.add_argument("--exclude-reviewed", type=Path, action="append", default=[])
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--expected-units", type=int, default=31)
    parser.add_argument("--expected-authorities", type=int, default=18)
    parser.add_argument("--seed", type=int, default=20260805)
    args = parser.parse_args()
    if args.output_dir.exists() and any(args.output_dir.iterdir()):
        raise ValueError(f"output directory is not empty: {args.output_dir}")
    source_rows = _read_jsonl(args.mutation_upstream)
    authority_keys = geometry_difference_authorities(
        _read_jsonl(args.semantic_anchor)
    )
    excluded_ids = {
        str(row.get("baseline_candidate_id") or row.get("candidate_id") or "")
        for path in args.exclude_reviewed
        for row in _read_jsonl(path)
    }
    population = [
        row
        for row in source_rows
        if is_geometry_difference_row(row, authority_keys=authority_keys)
        and str(row.get("candidate_id") or "") not in excluded_ids
    ]
    if len(population) != args.expected_units:
        raise ValueError(
            f"geometry-difference unit count mismatch: {len(population)} "
            f"!= {args.expected_units}"
        )
    authority_count = len({row["source_authority_key"] for row in population})
    if authority_count != args.expected_authorities:
        raise ValueError(
            f"geometry-difference authority count mismatch: {authority_count} "
            f"!= {args.expected_authorities}"
        )
    replay = [analyze_path(row) for row in population]
    calibration, holdout = split_full_population(replay, seed=args.seed)
    summary = build_summary(population, replay)
    summary.update(
        {
            "review_seed": args.seed,
            "calibration_rows": len(calibration),
            "holdout_rows": len(holdout),
            "calibration_holdout_authority_overlap": len(
                {row["source_authority_key"] for row in calibration}
                & {row["source_authority_key"] for row in holdout}
            ),
            "calibration_holdout_source_sha_overlap": len(
                {row["source_sha256"] for row in calibration}
                & {row["source_sha256"] for row in holdout}
            ),
        }
    )
    if summary["calibration_holdout_authority_overlap"]:
        raise ValueError("normalized-body leakage between calibration and holdout")
    if summary["calibration_holdout_source_sha_overlap"]:
        raise ValueError("source SHA leakage between calibration and holdout")
    args.output_dir.mkdir(parents=True, exist_ok=True)
    outputs = {
        "population_replay_v1.jsonl": replay,
        "complete_population_v1.jsonl": [
            row for row in replay if row["macro_status"] == "complete"
        ],
        "deferred_population_v1.jsonl": [
            row for row in replay if row["macro_status"] != "complete"
        ],
        "calibration_review_v1.jsonl": calibration,
        "holdout_review_v1.jsonl": holdout,
    }
    paths: list[Path] = []
    for name, rows in outputs.items():
        path = args.output_dir / name
        _write_jsonl(path, rows)
        paths.append(path)
    summary_path = args.output_dir / "summary_v1.json"
    _write_json(summary_path, summary)
    paths.append(summary_path)
    _write_json(
        args.output_dir / "hash_ledger_v1.json",
        {
            "schema": "gis_recommend.hash_ledger.v1",
            "inputs": {
                "mutation_upstream": {
                    "path": str(args.mutation_upstream),
                    "sha256": _sha256(args.mutation_upstream),
                },
                "semantic_anchor": {
                    "path": str(args.semantic_anchor),
                    "sha256": _sha256(args.semantic_anchor),
                },
                **{
                    f"exclude_reviewed_{index}": {
                        "path": str(path),
                        "sha256": _sha256(path),
                    }
                    for index, path in enumerate(args.exclude_reviewed)
                },
            },
            "artifacts": {
                path.name: {"bytes": path.stat().st_size, "sha256": _sha256(path)}
                for path in paths
            },
        },
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
