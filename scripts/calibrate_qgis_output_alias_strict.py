#!/usr/bin/env python3
"""Calibrate a strict direct-output-alias rule on frozen source labels."""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import math
import tempfile
import warnings
from pathlib import Path
from typing import Any, Mapping, Sequence

from gis_recommend.data.qgis_conversion_features import (
    _assignment_definitions,
    _is_processing_call,
    _lexical_scope,
    _parents,
    _reference_keys,
    _resolved_parameter_entries,
)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _control_path(
    node: ast.AST, parents: Mapping[ast.AST, ast.AST]
) -> tuple[tuple[ast.AST, str], ...]:
    path: list[tuple[ast.AST, str]] = []
    child = node
    parent = parents.get(child)
    blocked = (ast.If, ast.For, ast.AsyncFor, ast.While, ast.Try, ast.With, ast.AsyncWith)
    while parent is not None:
        if isinstance(parent, blocked):
            branch = next(
                (
                    field
                    for field, value in ast.iter_fields(parent)
                    if value is child or isinstance(value, list) and child in value
                ),
                "",
            )
            path.append((parent, branch))
        child = parent
        parent = parents.get(child)
    return tuple(reversed(path))


def _dominates(
    definition: ast.AST, use: ast.AST, parents: Mapping[ast.AST, ast.AST]
) -> bool:
    definition_path = _control_path(definition, parents)
    use_path = _control_path(use, parents)
    return definition_path == use_path[: len(definition_path)]


def _simple_assignment(node: ast.AST) -> tuple[str, ast.AST] | None:
    if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
        return node.targets[0].id, node.value
    if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name) and node.value is not None:
        return node.target.id, node.value
    return None


def _selected_calls(
    tree: ast.AST, call_sites: Sequence[Mapping[str, Any]]
) -> list[ast.Call]:
    calls = sorted(
        (node for node in ast.walk(tree) if _is_processing_call(node)),
        key=lambda node: (node.lineno, node.col_offset),
    )
    selected: list[ast.Call] = []
    used: set[int] = set()
    for site in call_sites:
        start = int(site.get("line_start") or 0)
        end = int(site.get("line_end") or start)
        matches = [
            call
            for call in calls
            if id(call) not in used
            and call.lineno <= end
            and int(call.end_lineno or call.lineno) >= start
        ]
        if len(matches) != 1:
            raise ValueError(f"call_alignment_not_unique:{start}-{end}")
        selected.append(matches[0])
        used.add(id(matches[0]))
    return selected


def inspect_strict_output_alias(
    source_text: str, *, call_sites: Sequence[Mapping[str, Any]]
) -> dict[str, Any]:
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", SyntaxWarning)
            tree = ast.parse(source_text)
        selected_calls = _selected_calls(tree, call_sites)
    except (SyntaxError, ValueError) as exc:
        return {"status": "fail_closed", "reason": str(exc), "evidence": []}

    parents = _parents(tree)
    definitions = _assignment_definitions(tree, parents)
    selected_ids = {id(call) for call in selected_calls}
    assignments = [
        node
        for node in ast.walk(tree)
        if isinstance(node, (ast.Assign, ast.AnnAssign)) and _simple_assignment(node)
    ]
    evidence: list[dict[str, Any]] = []
    for alias_assignment in assignments:
        alias_name, value = _simple_assignment(alias_assignment) or ("", alias_assignment)
        if not (
            isinstance(value, ast.Subscript)
            and isinstance(value.value, ast.Name)
            and isinstance(value.slice, ast.Constant)
            and value.slice.value == "OUTPUT"
        ):
            continue
        result_name = value.value.id
        scope = _lexical_scope(alias_assignment, parents)
        if isinstance(scope, (ast.FunctionDef, ast.AsyncFunctionDef)) and alias_name in {
            argument.arg
            for argument in (*scope.args.posonlyargs, *scope.args.args, *scope.args.kwonlyargs)
        }:
            continue
        alias_writes = [
            node
            for node in assignments
            if _lexical_scope(node, parents) is scope
            and (_simple_assignment(node) or ("", node))[0] == alias_name
        ]
        if len(alias_writes) != 1:
            continue
        producers = [
            node
            for node in assignments
            if int(node.lineno) < int(alias_assignment.lineno)
            and _lexical_scope(node, parents) is scope
            and (_simple_assignment(node) or ("", node))[0] == result_name
        ]
        if not producers:
            continue
        producer_assignment = max(producers, key=lambda node: int(node.lineno))
        _, producer_value = _simple_assignment(producer_assignment) or ("", producer_assignment)
        if not (_is_processing_call(producer_value) and id(producer_value) in selected_ids):
            continue

        consumers: list[ast.Call] = []
        for call in selected_calls:
            if int(call.lineno) <= int(alias_assignment.lineno):
                continue
            if _lexical_scope(call, parents) is not scope or not _dominates(alias_assignment, call, parents):
                continue
            entries = _resolved_parameter_entries(
                call, parents=parents, definitions=definitions
            )
            if any(
                f"name:{alias_name}" in _reference_keys(parameter_value)
                for _, parameter_value in entries or []
            ):
                consumers.append(call)
        if consumers:
            evidence.append(
                {
                    "alias": alias_name,
                    "result": result_name,
                    "producer_line": int(producer_value.lineno),
                    "alias_line": int(alias_assignment.lineno),
                    "consumer_lines": [int(call.lineno) for call in consumers],
                }
            )
    return {
        "status": "rule_candidate" if evidence else "fail_closed",
        "reason": "strict_direct_alias_found" if evidence else "no_strict_direct_alias",
        "evidence": evidence,
    }


def _wilson_lower(successes: int, total: int) -> float:
    if total == 0:
        return 0.0
    z = 1.959963984540054
    ratio = successes / total
    denominator = 1 + z * z / total
    centre = ratio + z * z / (2 * total)
    margin = z * math.sqrt((ratio * (1 - ratio) + z * z / (4 * total)) / total)
    return (centre - margin) / denominator


def calibrate(
    review_rows: list[dict[str, Any]], proposal_rows: list[dict[str, Any]]
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    labels = {str(row["record_id"]): str(row["proposal_decision"]) for row in proposal_rows}
    rows: list[dict[str, Any]] = []
    for review in sorted(
        (row for row in review_rows if row.get("family") == "output_alias"),
        key=lambda row: str(row["record_id"]),
    ):
        path = Path(str(review["source_path"]))
        verified = path.is_file() and _sha256(path) == review["source_sha256"]
        result = (
            inspect_strict_output_alias(
                path.read_text(encoding="utf-8-sig", errors="replace"),
                call_sites=review.get("call_sites") or [],
            )
            if verified
            else {"status": "fail_closed", "reason": "source_sha_mismatch", "evidence": []}
        )
        prediction = result["status"] == "rule_candidate"
        expected = labels[str(review["record_id"])] == "true_positive"
        rows.append(
            {
                "schema": "gis_recommend.qgis_output_alias_strict_calibration.v1",
                "record_id": review["record_id"],
                "source_path": str(path),
                "source_sha256": review["source_sha256"],
                "source_verification": "verified_sha256" if verified else "failed",
                "expected_true_positive": expected,
                "strict_rule_status": result["status"],
                "strict_rule_reason": result["reason"],
                "evidence": result["evidence"],
                "training_admission": "not_granted_rule_calibration_only",
                "training_row_emitted": False,
                "validation_eligible": False,
                "test_eligible": False,
                "production_merge": "not_granted",
            }
        )
    tp = sum(row["expected_true_positive"] and row["strict_rule_status"] == "rule_candidate" for row in rows)
    fp = sum(not row["expected_true_positive"] and row["strict_rule_status"] == "rule_candidate" for row in rows)
    fn = sum(row["expected_true_positive"] and row["strict_rule_status"] != "rule_candidate" for row in rows)
    tn = len(rows) - tp - fp - fn
    predicted = tp + fp
    precision = tp / predicted if predicted else 0.0
    summary = {
        "schema": "gis_recommend.qgis_output_alias_strict_calibration_summary.v1",
        "rows": len(rows),
        "true_positive": tp,
        "false_positive": fp,
        "false_negative": fn,
        "true_negative": tn,
        "precision": precision,
        "recall": tp / (tp + fn) if tp + fn else 0.0,
        "wilson_lower_95": _wilson_lower(tp, predicted),
        "promotion_eligible": precision >= 0.95 and _wilson_lower(tp, predicted) >= 0.80,
        "training_admission": "not_granted_rule_calibration_only",
        "training_rows_emitted": 0,
        "validation_eligible": False,
        "test_eligible": False,
        "production_merge": "not_granted",
    }
    return rows, summary


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _atomic_write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", newline="", dir=path.parent, delete=False) as handle:
        handle.write(text)
        temporary = Path(handle.name)
    temporary.replace(path)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--review", type=Path, required=True)
    parser.add_argument("--proposals", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    rows, summary = calibrate(_load_jsonl(args.review), _load_jsonl(args.proposals))
    output = args.output_dir / "calibration_v1.jsonl"
    summary_path = args.output_dir / "summary_v1.json"
    report = args.output_dir / "report_v1.md"
    hashes = args.output_dir / "hash_ledger_v1.json"
    _atomic_write(output, "".join(json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n" for row in rows))
    _atomic_write(summary_path, json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
    _atomic_write(report, "# QGIS strict output-alias calibration v1\n\nCalibration only; no training rows are emitted.\n")
    _atomic_write(hashes, json.dumps({
        "schema": "gis_recommend.hash_ledger.v1",
        "inputs": {str(args.review): _sha256(args.review), str(args.proposals): _sha256(args.proposals)},
        "artifacts": {path.name: _sha256(path) for path in (output, summary_path, report)},
    }, ensure_ascii=False, indent=2, sort_keys=True) + "\n")


if __name__ == "__main__":
    main()
