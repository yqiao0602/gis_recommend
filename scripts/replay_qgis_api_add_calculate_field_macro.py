#!/usr/bin/env python3
"""Replay Add Field -> Calculate Field macros from the Add Field sidecar."""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import tempfile
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from scripts.replay_qgis_api_add_field_local_macro import (
    CallEvidence,
    EvidenceVisitor,
    _expr_name,
    _method_name,
    _receiver,
    _sha256,
    _sha256_bytes,
    _snippet,
    _source_text,
)

SCHEMA = "gis_recommend.qgis_api_add_calculate_field_macro.v2"
SUMMARY_SCHEMA = "gis_recommend.qgis_api_add_calculate_field_macro_summary.v2"
RULE_ID = "add-calculate-field-setattribute-updatefeature-v2"
FAMILY_ID = "add_calculate_field"
L3_SEQUENCE = ["L3_01_02_01", "L3_01_02_06"]
ALLOWED_SCOPE_SEMANTICS = {"getfeatures", "setattribute", "updatefeature"}
MAX_CALCULATION_GAP = 20
MAX_ADJACENT_SCHEMA_MUTATION_GAP = 8
MAX_DOWNSTREAM_FIELD_TRANSFORM_GAP = 12
ADJACENT_SCHEMA_MUTATION_METHODS = {
    "deleteattribute",
    "deleteattributes",
    "renameattribute",
}
SPATIAL_BOUNDARY_METHODS = {
    "closestsegmentwithcontext",
    "contains",
    "crosses",
    "distance",
    "distancetovertex",
    "hausdorffdistance",
    "intersects",
    "nearestneighbor",
    "overlaps",
    "touches",
    "within",
}
DOWNSTREAM_FIELD_TRANSFORM_CALLS = {"normalizevalue", "normalisevalue"}


def _literal_string(node: ast.AST | None) -> str | None:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    return None


def _literal_strings(node: ast.AST) -> set[str]:
    return {
        str(child.value)
        for child in ast.walk(node)
        if isinstance(child, ast.Constant) and isinstance(child.value, str)
    }


def _call_name(call: ast.Call) -> str:
    return _expr_name(call.func).rsplit(".", 1)[-1].lower()


@dataclass(frozen=True)
class AssignmentEvidence:
    node: ast.Assign
    scope: str
    control_path: tuple[str, ...]


class CalculationVisitor(EvidenceVisitor):
    def __init__(self) -> None:
        super().__init__()
        self.assignments: list[AssignmentEvidence] = []

    def visit_Assign(self, node: ast.Assign) -> None:
        self.assignments.append(
            AssignmentEvidence(node, self.scope, tuple(self.control_stack))
        )
        super().visit_Assign(node)


def _base(row: dict[str, Any], status: str) -> dict[str, Any]:
    return {
        **row,
        "schema": SCHEMA,
        "family_rule_id": RULE_ID,
        "selected_family_id": FAMILY_ID,
        "candidate_l3_sequence": L3_SEQUENCE,
        "macro_boundary_status": status,
        "calculated_field_names": [],
        "calculation_expressions": {},
        "calculation_call_evidence": [],
        "description_fidelity": "not_started",
        "deduplication": "not_started",
        "training_admission": "not_granted_source_replay_only",
        "training_row_emitted": False,
        "validation_eligible": False,
        "test_eligible": False,
        "production_merge": "not_granted",
        "llm_called": False,
    }


def _is_family_input(row: dict[str, Any]) -> bool:
    methods = set(row.get("excluded_additional_scope_semantics") or [])
    return (
        row.get("macro_boundary_status") == "deferred_additional_scope_semantics"
        and {"getfeatures", "updatefeature"}.issubset(methods)
        and methods <= ALLOWED_SCOPE_SEMANTICS
    )


def replay_row(row: dict[str, Any]) -> dict[str, Any]:
    if not _is_family_input(row):
        return _base(row, "not_selected_family_input")
    path = Path(str(row.get("source_path") or ""))
    if not path.is_file():
        return _base(row, "source_missing")
    raw = path.read_bytes()
    actual_sha = _sha256_bytes(raw)
    if actual_sha != str(row.get("source_sha256") or ""):
        result = _base(row, "source_sha256_mismatch")
        result["actual_source_sha256"] = actual_sha
        return result
    try:
        text = _source_text(raw)
        tree = ast.parse(text, filename=str(path))
    except (SyntaxError, UnicodeDecodeError, LookupError) as error:
        result = _base(row, "source_parse_failure")
        result["source_parse_error"] = f"{type(error).__name__}: {error}"
        return result

    visitor = CalculationVisitor()
    visitor.visit(tree)
    scope = str(row.get("lexical_scope") or "")
    layer = str(row.get("layer_alias") or "")
    schema_end = int(row.get("macro_line_end") or 0)
    added_fields = set(row.get("field_names") or [])
    all_set_calls = [
        evidence
        for evidence in visitor.calls
        if evidence.scope == scope
        and _method_name(evidence.call) == "setattribute"
        and int(evidence.call.lineno) > schema_end
        and len(evidence.call.args) >= 2
    ]
    set_calls = [
        evidence
        for evidence in all_set_calls
        if _literal_string(evidence.call.args[0]) in added_fields
    ]
    update_calls = [
        evidence
        for evidence in visitor.calls
        if evidence.scope == scope
        and _method_name(evidence.call) == "updatefeature"
        and _expr_name(_receiver(evidence.call)) == layer
        and evidence.call.args
    ]
    target_assignments = [
        assignment
        for assignment in visitor.assignments
        if assignment.scope == scope
        and int(assignment.node.lineno) > schema_end
        and len(assignment.node.targets) == 1
        and isinstance(assignment.node.targets[0], ast.Subscript)
    ]

    def has_additional_field_updates(
        feature: str, control_path: tuple[str, ...], update_line: int
    ) -> bool:
        for assignment in target_assignments:
            target = assignment.node.targets[0]
            if (
                assignment.control_path == control_path
                and _expr_name(target.value) == feature
                and int(assignment.node.lineno) <= update_line
                and _literal_string(target.slice) not in added_fields
            ):
                return True
        for setter in all_set_calls:
            if (
                setter.control_path == control_path
                and _expr_name(_receiver(setter.call)) == feature
                and int(setter.call.lineno) <= update_line
                and _literal_string(setter.call.args[0]) not in added_fields
            ):
                return True
        return False

    matches: list[tuple[str, str, int, Any, Any]] = []
    for setter in set_calls:
        feature = _expr_name(_receiver(setter.call))
        candidates = [
            update
            for update in update_calls
            if _expr_name(update.call.args[0]) == feature
            and update.control_path == setter.control_path
            and int(update.call.lineno) >= int(setter.call.lineno)
            and int(update.call.lineno) - int(setter.call.lineno)
            <= MAX_CALCULATION_GAP
        ]
        if candidates:
            update = min(candidates, key=lambda item: item.call.lineno)
            if has_additional_field_updates(
                feature, setter.control_path, int(update.call.lineno)
            ):
                continue
            field = str(_literal_string(setter.call.args[0]))
            matches.append(
                (
                    field,
                    ast.unparse(setter.call.args[1]),
                    int(setter.call.lineno),
                    setter,
                    update,
                )
            )

    for assignment in target_assignments:
        if assignment.scope != scope or int(assignment.node.lineno) <= schema_end:
            continue
        if len(assignment.node.targets) != 1:
            continue
        target = assignment.node.targets[0]
        if not isinstance(target, ast.Subscript):
            continue
        field = _literal_string(target.slice)
        feature = _expr_name(target.value)
        if not field or field not in added_fields or not feature:
            continue
        candidates = [
            update
            for update in update_calls
            if _expr_name(update.call.args[0]) == feature
            and update.control_path == assignment.control_path
            and int(update.call.lineno) >= int(assignment.node.lineno)
            and int(update.call.lineno) - int(assignment.node.lineno)
            <= MAX_CALCULATION_GAP
        ]
        if candidates:
            update = min(candidates, key=lambda item: item.call.lineno)
            if has_additional_field_updates(
                feature, assignment.control_path, int(update.call.lineno)
            ):
                continue
            matches.append(
                (
                    field,
                    ast.unparse(assignment.node.value),
                    int(assignment.node.lineno),
                    assignment,
                    update,
                )
            )
    if not matches:
        result = _base(row, "deferred_no_same_feature_update_chain")
        result["source_verification"] = "verified_sha256"
        return result

    calculated_fields = sorted(
        {field for field, _, _, _, _ in matches}
    )
    expressions = {
        field: expression for field, expression, _, _, _ in matches
    }
    evidence = [
        {
            "field_name": field,
            "feature_alias": (
                _expr_name(_receiver(setter.call))
                if isinstance(setter, CallEvidence)
                else _expr_name(setter.node.targets[0].value)
            ),
            "calculation_line": calculation_line,
            "calculation_syntax": (
                "setAttribute"
                if isinstance(setter, CallEvidence)
                else "subscript_assignment"
            ),
            "update_feature_line": int(update.call.lineno),
            "control_path": list(setter.control_path),
        }
        for field, _, calculation_line, setter, update in matches
    ]
    end = max(item["update_feature_line"] for item in evidence)
    macro_start = int(row.get("macro_line_start") or schema_end)
    adjacent_schema_mutations = [
        call
        for call in visitor.calls
        if call.scope == scope
        and macro_start - MAX_ADJACENT_SCHEMA_MUTATION_GAP
        <= int(call.call.lineno)
        < macro_start
        and _method_name(call.call) in ADJACENT_SCHEMA_MUTATION_METHODS
    ]
    if adjacent_schema_mutations:
        result = _base(row, "deferred_adjacent_schema_mutation_boundary")
        result.update(
            {
                "source_verification": "verified_sha256",
                "boundary_gate_evidence": {
                    "adjacent_schema_mutation_calls": [
                        {
                            "method": _method_name(call.call),
                            "line": int(call.call.lineno),
                        }
                        for call in adjacent_schema_mutations
                    ]
                },
            }
        )
        return result

    macro_calls = [
        call
        for call in visitor.calls
        if call.scope == scope
        and schema_end < int(call.call.lineno) <= end
    ]
    cross_layer_getfeatures = [
        call
        for call in macro_calls
        if _method_name(call.call) == "getfeatures"
        and _expr_name(_receiver(call.call)) not in {"", layer}
    ]
    spatial_boundary_calls = [
        call
        for call in macro_calls
        if _method_name(call.call) in SPATIAL_BOUNDARY_METHODS
    ]
    if cross_layer_getfeatures or spatial_boundary_calls:
        result = _base(
            row, "deferred_cross_layer_or_spatial_calculation_boundary"
        )
        result.update(
            {
                "source_verification": "verified_sha256",
                "boundary_gate_evidence": {
                    "secondary_getfeatures_lines": sorted(
                        int(call.call.lineno) for call in cross_layer_getfeatures
                    ),
                    "spatial_method_calls": [
                        {
                            "method": _method_name(call.call),
                            "line": int(call.call.lineno),
                        }
                        for call in spatial_boundary_calls
                    ],
                },
            }
        )
        return result

    downstream_field_transforms = [
        call
        for call in visitor.calls
        if call.scope == scope
        and end < int(call.call.lineno) <= end + MAX_DOWNSTREAM_FIELD_TRANSFORM_GAP
        and _call_name(call.call) in DOWNSTREAM_FIELD_TRANSFORM_CALLS
        and bool(_literal_strings(call.call) & set(calculated_fields))
    ]
    if downstream_field_transforms:
        result = _base(row, "deferred_downstream_same_field_transform")
        result.update(
            {
                "source_verification": "verified_sha256",
                "boundary_gate_evidence": {
                    "downstream_field_transform_calls": [
                        {
                            "call": _call_name(call.call),
                            "line": int(call.call.lineno),
                            "field_names": sorted(
                                _literal_strings(call.call) & set(calculated_fields)
                            ),
                        }
                        for call in downstream_field_transforms
                    ]
                },
            }
        )
        return result

    result = _base(row, "verified_complete_add_calculate_field_macro")
    result.update(
        {
            "source_verification": "verified_sha256",
            "calculated_field_names": calculated_fields,
            "calculation_expressions": expressions,
            "calculation_call_evidence": evidence,
            "macro_line_end": end,
            "macro_line_span": end - int(row.get("macro_line_start") or end) + 1,
            "source_snippet": _snippet(
                text, int(row.get("macro_line_start") or end), end
            ),
            "task_name": f"新增并计算字段 {', '.join(calculated_fields)}",
            "task_description": (
                f"向现有矢量图层新增字段 {', '.join(sorted(added_fields))}，"
                f"并逐要素计算字段 {', '.join(calculated_fields)} 的值。"
            ),
            "description_policy": "source_fact_literal_fields_and_verified_update_chain",
            "description_fidelity": "passed_source_fact_only",
        }
    )
    return result


def _rank(row: dict[str, Any], seed: int) -> str:
    return hashlib.sha256(
        f"{seed}:{row.get('source_authority_key')}:{row.get('candidate_unit_id')}".encode()
    ).hexdigest()


def select_review(
    rows: list[dict[str, Any]], per_split: int, seed: int
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    eligible = [
        row
        for row in rows
        if row.get("macro_boundary_status")
        == "verified_complete_add_calculate_field_macro"
    ]
    eligible.sort(key=lambda row: _rank(row, seed))
    selected: list[dict[str, Any]] = []
    sources: set[str] = set()
    bodies: set[str] = set()
    for row in eligible:
        source = str(row.get("source_sha256") or "")
        body = str(row.get("normalized_source_body_sha256") or "")
        if not source or not body or source in sources or body in bodies:
            continue
        selected.append(row)
        sources.add(source)
        bodies.add(body)
        if len(selected) == per_split * 2:
            break
    if len(selected) < per_split * 2:
        raise ValueError(
            f"need {per_split * 2} source-disjoint rows, found {len(selected)}"
        )
    return (
        [{**row, "review_split": "calibration"} for row in selected[:per_split]],
        [{**row, "review_split": "holdout"} for row in selected[per_split:]],
    )


def replay_rows(
    rows: list[dict[str, Any]], review_per_split: int = 0, seed: int = 20260805
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    selected = [row for row in rows if _is_family_input(row)]
    replayed = [replay_row(row) for row in selected]
    calibration: list[dict[str, Any]] = []
    holdout: list[dict[str, Any]] = []
    if review_per_split:
        calibration, holdout = select_review(replayed, review_per_split, seed)
    statuses = Counter(str(row["macro_boundary_status"]) for row in replayed)
    complete = [
        row
        for row in replayed
        if row["macro_boundary_status"]
        == "verified_complete_add_calculate_field_macro"
    ]
    summary = {
        "schema": SUMMARY_SCHEMA,
        "family_rule_id": RULE_ID,
        "input_rows": len(rows),
        "selected_family_rows": len(selected),
        "source_replay_status_counts": dict(sorted(statuses.items())),
        "complete_macro_units": len(complete),
        "complete_macro_source_authorities": len(
            {str(row.get("source_authority_key") or "") for row in complete}
        ),
        "candidate_l3_sequence": L3_SEQUENCE,
        "description_fidelity_rows": len(complete),
        "calibration_rows": len(calibration),
        "holdout_rows": len(holdout),
        "calibration_holdout_source_sha_overlap": len(
            {str(row["source_sha256"]) for row in calibration}
            & {str(row["source_sha256"]) for row in holdout}
        ),
        "calibration_holdout_normalized_body_overlap": len(
            {str(row["normalized_source_body_sha256"]) for row in calibration}
            & {str(row["normalized_source_body_sha256"]) for row in holdout}
        ),
        "training_admission": "not_granted_source_replay_only",
        "training_rows_emitted": 0,
        "validation_eligible": False,
        "test_eligible": False,
        "production_merge": "not_granted",
        "llm_called": False,
    }
    return replayed, calibration, holdout, summary


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


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    _atomic_write(
        path,
        "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows),
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-jsonl", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--expected-input-rows", type=int)
    parser.add_argument("--review-per-split", type=int, default=0)
    parser.add_argument("--seed", type=int, default=20260805)
    args = parser.parse_args()
    if args.output_dir.exists() and any(args.output_dir.iterdir()):
        raise ValueError(f"output directory is not empty: {args.output_dir}")
    rows = _read_jsonl(args.input_jsonl)
    if args.expected_input_rows is not None and len(rows) != args.expected_input_rows:
        raise ValueError(f"expected {args.expected_input_rows} rows, got {len(rows)}")
    replayed, calibration, holdout, summary = replay_rows(
        rows, args.review_per_split, args.seed
    )
    artifacts: list[Path] = []
    for name, values in (
        ("source_replay_v1.jsonl", replayed),
        ("calibration_review_v1.jsonl", calibration),
        ("holdout_review_v1.jsonl", holdout),
    ):
        path = args.output_dir / name
        _write_jsonl(path, values)
        artifacts.append(path)
    summary_path = args.output_dir / "summary_v1.json"
    _write_json(summary_path, summary)
    artifacts.append(summary_path)
    _write_json(
        args.output_dir / "hash_ledger_v1.json",
        {
            "schema": "gis_recommend.hash_ledger.v1",
            "inputs": {
                args.input_jsonl.name: {
                    "path": str(args.input_jsonl),
                    "sha256": _sha256(args.input_jsonl),
                }
            },
            "artifacts": {
                path.name: {"bytes": path.stat().st_size, "sha256": _sha256(path)}
                for path in artifacts
            },
        },
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
