#!/usr/bin/env python3
"""Build and export reviewed Add Field -> Calculate Field local macros."""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import tempfile
from collections import Counter
from pathlib import Path
from typing import Any

COMPLETE = "verified_complete_add_calculate_field_macro"
RULE_ID = "add-calculate-field-setattribute-updatefeature-v2"
L3_CODES = ["L3_01_02_01", "L3_01_02_06"]
OPERATORS = ["pyqgis:add_field", "pyqgis:calculate_field"]
SPECIAL_TOKENS = {"<START>": -3, "<END>": -4}
ADMISSION = "granted_train_only_qgis_api_add_calculate_field_local_macro_v1"
SPLIT = "train_only_qgis_api_add_calculate_field_local_macro_v1"
TRAINING_SCHEMA = "qgis_api_training_sample_v1"


def _json_key(value: Any) -> str:
    encoded = json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _normalize_text(value: Any) -> str:
    return "".join(str(value or "").lower().split())


def _authority_set_sha256(rows: list[dict[str, Any]]) -> str:
    keys = sorted(str(row.get("source_authority_key") or "") for row in rows)
    return hashlib.sha256(("\n".join(keys) + "\n").encode()).hexdigest()


def verify_review_authority(
    calibration: list[dict[str, Any]],
    holdout: list[dict[str, Any]],
    approval: dict[str, Any],
) -> set[str]:
    rows = [*calibration, *holdout]
    if approval.get("family_rule_id") != RULE_ID:
        raise ValueError("review authority rule mismatch")
    if len(calibration) != int(approval.get("calibration_rows") or -1):
        raise ValueError("calibration row count mismatch")
    if len(holdout) != int(approval.get("holdout_rows") or -1):
        raise ValueError("holdout row count mismatch")
    if any(row.get("macro_boundary_status") != COMPLETE for row in rows):
        raise ValueError("review packet contains an incomplete macro")
    source_overlap = {row["source_sha256"] for row in calibration} & {
        row["source_sha256"] for row in holdout
    }
    body_overlap = {row["normalized_source_body_sha256"] for row in calibration} & {
        row["normalized_source_body_sha256"] for row in holdout
    }
    if source_overlap or body_overlap:
        raise ValueError("review splits are not source-disjoint")
    keys = {str(row["source_authority_key"]) for row in rows}
    if len(keys) != int(approval.get("accepted_source_authorities") or -1):
        raise ValueError("accepted authority count mismatch")
    if _authority_set_sha256(rows) != approval.get("accepted_authority_set_sha256"):
        raise ValueError("accepted authority hash mismatch")
    if int(approval.get("false_positive_rows", -1)) != 0:
        raise ValueError("review authority contains false positives")
    if int(approval.get("chain_truncation_rows", -1)) != 0:
        raise ValueError("review authority contains chain truncation")
    return keys


def _constant_expression(expressions: dict[str, str]) -> str | None:
    values: list[str] = []
    for expression in expressions.values():
        try:
            value = ast.literal_eval(expression)
        except (ValueError, SyntaxError):
            return None
        if not isinstance(value, (str, int, float, bool)):
            return None
        values.append(repr(value))
    return "、".join(values)


def _calculation_strategy(row: dict[str, Any]) -> tuple[str, str]:
    expressions = {
        str(key): str(value)
        for key, value in (row.get("calculation_expressions") or {}).items()
    }
    values = list(expressions.values())
    snippet = str(row.get("source_snippet") or "").lower()
    constant = _constant_expression(expressions)
    if constant is not None:
        return "constant_assignment", f"将固定值 {constant} 写入该字段"
    if values and all(value in {"i", "contador", "counter"} for value in values):
        return "sequential_identifier", "按要素遍历顺序写入连续编号"
    if values and all(".id()" in value for value in values):
        return "feature_internal_identifier", "写入每个要素的内部 ID"
    if any(".evaluate(" in value for value in values):
        return "qgis_expression", "按已定义的 QGIS 表达式逐要素计算并写入相应字段"
    if "_scale_value" in snippet or "scale values" in snippet:
        return "scaled_or_reclassified_value", "根据指定输入值逐要素分级或缩放并写入该字段"
    if len(expressions) > 1:
        return (
            "multi_field_expression",
            "分别按已验证的字段表达式逐要素计算并写入相应字段",
        )
    source_lines = [
        line.split("|", 1)[-1].lstrip() for line in snippet.splitlines()
    ]
    branch_lines = [
        line
        for line in source_lines
        if line.startswith(("if ", "elif "))
    ]
    expression_is_conditional = any(
        isinstance(ast.parse(value, mode="eval").body, ast.IfExp) for value in values
    )
    if expression_is_conditional or len(branch_lines) > 1:
        return (
            "conditional_expression",
            "按已验证的条件分支逐要素计算并写入该字段",
        )
    return "derived_expression", "按已验证的计算表达式逐要素计算并写入该字段"


def build_candidate(row: dict[str, Any]) -> dict[str, Any]:
    reasons: list[str] = []
    if row.get("macro_boundary_status") != COMPLETE:
        reasons.append("macro_boundary_not_verified")
    if row.get("family_rule_id") != RULE_ID:
        reasons.append("family_rule_contract_mismatch")
    if row.get("source_verification") != "verified_sha256":
        reasons.append("source_sha256_not_verified")
    if list(row.get("candidate_l3_sequence") or []) != L3_CODES:
        reasons.append("stable125_l3_contract_mismatch")
    added_fields = sorted(str(value) for value in row.get("field_names") or [])
    calculated_fields = sorted(
        str(value) for value in row.get("calculated_field_names") or []
    )
    if not added_fields or added_fields != calculated_fields:
        reasons.append("added_and_calculated_field_sets_differ")
    evidence = list(row.get("calculation_call_evidence") or [])
    if not evidence or any(int(item.get("update_feature_line") or 0) <= 0 for item in evidence):
        reasons.append("calculation_call_evidence_incomplete")
    start = int(row.get("macro_line_start") or 0)
    end = int(row.get("macro_line_end") or 0)
    if start <= 0 or end < start:
        reasons.append("macro_source_span_incomplete")

    strategy, strategy_text = _calculation_strategy(row)
    field_text = "、".join(added_fields)
    task_name = f"新增并计算字段 {field_text}"
    task_description = f"向现有矢量图层新增字段 {field_text}，{strategy_text}。"
    passed = not reasons
    source_span = {"segments": [{"line_start": start, "line_end": end}]}
    candidate_id = _json_key(
        {
            "source_authority_key": row.get("source_authority_key"),
            "source_span": source_span,
            "field_names": added_fields,
            "rule_id": RULE_ID,
        }
    )
    semantic_sites = [
        {
            "name": OPERATORS[0],
            "line_start": start,
            "line_end": int(row.get("macro_line_end") or start),
            "arguments": added_fields,
        },
        {
            "name": OPERATORS[1],
            "line_start": min(
                int(item["calculation_line"]) for item in evidence
            )
            if evidence
            else end,
            "line_end": end,
            "arguments": calculated_fields,
        },
    ]
    return {
        **row,
        "schema": "gis_recommend.qgis_api_add_calculate_field_candidate.v1",
        "candidate_id": candidate_id,
        "description_rule_id": "add-calculate-field-source-facts-zh-v1",
        "semantic_calls": OPERATORS,
        "semantic_call_sites": semantic_sites,
        "candidate_l3_sequence": L3_CODES,
        "dependency_edges": [[0, 1]],
        "source_span": source_span,
        "task_name": task_name if passed else "",
        "task_description": task_description if passed else "",
        "parameter_facts": {
            "field_names": added_fields,
            "calculation_expressions": row.get("calculation_expressions") or {},
            "calculation_strategy": strategy,
        },
        "workflow_scope": "source_verified_local_api_macro",
        "whole_function_semantics_admission": "not_granted",
        "known_omissions": [
            "whole_function_task_semantics_not_claimed",
            "calculation_parameters_outside_local_macro_are_not_reconstructed",
        ],
        "description_source": "source_verified_local_macro_facts_only",
        "description_fidelity": "passed" if passed else "deferred",
        "description_fidelity_passed": passed,
        "description_fidelity_reasons": reasons,
        "llm_called": False,
        "training_admission": (
            "not_granted_pending_four_layer_dedup"
            if passed
            else "not_granted_description_fidelity_failed"
        ),
        "training_row_emitted": False,
        "validation_eligible": False,
        "test_eligible": False,
        "production_merge": "not_granted",
    }


def build_four_layer_dedup(
    candidates: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    eligible = [row for row in candidates if row.get("description_fidelity_passed") is True]
    eligible.sort(key=lambda row: str(row["candidate_id"]))
    canonical_by_pair: dict[str, dict[str, Any]] = {}
    ledger: list[dict[str, Any]] = []
    for candidate in eligible:
        source_region_key = _json_key(
            {
                "source_sha256": candidate.get("source_sha256"),
                "source_span": candidate.get("source_span"),
            }
        )
        call_graph_key = _json_key(
            {
                "source_sha256": candidate.get("source_sha256"),
                "semantic_call_sites": candidate.get("semantic_call_sites"),
                "dependency_edges": candidate.get("dependency_edges"),
            }
        )
        normalized_dag_key = _json_key(
            {
                "semantic_calls": candidate.get("semantic_calls"),
                "l3_sequence": candidate.get("candidate_l3_sequence"),
                "calculation_strategy": candidate.get("parameter_facts", {}).get(
                    "calculation_strategy"
                ),
                "field_count": len(candidate.get("field_names") or []),
                "task_boundary": "local_add_calculate_field_macro",
            }
        )
        task_text_key = _json_key(_normalize_text(candidate.get("task_description")))
        training_pair_key = _json_key(
            {
                "task_name": _normalize_text(candidate.get("task_name")),
                "task_description": _normalize_text(candidate.get("task_description")),
                "l3_sequence": candidate.get("candidate_l3_sequence"),
            }
        )
        canonical = canonical_by_pair.get(training_pair_key)
        decision = "canonical_keep" if canonical is None else "exact_training_pair_suppressed"
        if canonical is None:
            canonical_by_pair[training_pair_key] = candidate
        ledger.append(
            {
                **candidate,
                "schema": "gis_recommend.qgis_api_add_calculate_field_dedup_ledger.v1",
                "source_region_key": source_region_key,
                "call_graph_key": call_graph_key,
                "normalized_dag_key": normalized_dag_key,
                "task_text_key": task_text_key,
                "training_pair_key": training_pair_key,
                "dedup_decision": decision,
                "canonical_candidate_id": (
                    candidate["candidate_id"]
                    if canonical is None
                    else canonical["candidate_id"]
                ),
                "training_admission": (
                    "not_granted_pending_train_only_export"
                    if canonical is None
                    else "not_granted_exact_training_pair_duplicate"
                ),
            }
        )
    canonical = [row for row in ledger if row["dedup_decision"] == "canonical_keep"]
    return ledger, {
        "description_fidelity_passed": len(eligible),
        "description_fidelity_deferred": len(candidates) - len(eligible),
        "canonical_rows": len(canonical),
        "suppressed_exact_training_pairs": len(ledger) - len(canonical),
        "unique_source_authorities": len(
            {str(row.get("source_authority_key") or "") for row in eligible}
        ),
        "unique_source_regions": len({row["source_region_key"] for row in ledger}),
        "unique_call_graphs": len({row["call_graph_key"] for row in ledger}),
        "unique_normalized_dags": len({row["normalized_dag_key"] for row in ledger}),
        "unique_task_texts": len({row["task_text_key"] for row in ledger}),
        "description_defer_reason_counts": dict(
            sorted(
                Counter(
                    reason
                    for row in candidates
                    for reason in row.get("description_fidelity_reasons") or []
                ).items()
            )
        ),
    }


def _pair_key(row: dict[str, Any]) -> str:
    return _json_key(
        {
            "task_name": _normalize_text(row.get("task_name")),
            "task_description": _normalize_text(row.get("task_description")),
            "l3_sequence": row.get("candidate_l3_sequence")
            or row.get("l3_code_sequence")
            or [],
        }
    )


def export_train_only(
    candidates: list[dict[str, Any]],
    existing_rows: list[dict[str, Any]],
    code_to_id: dict[str, int],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    existing_pairs = {_pair_key(row) for row in existing_rows}
    token_ids = [int(code_to_id[code]) for code in L3_CODES]
    if token_ids != [1, 4]:
        raise ValueError("stable125 Add/Calculate Field token contract mismatch")
    exported: list[dict[str, Any]] = []
    ledger: list[dict[str, Any]] = []
    for candidate in candidates:
        if candidate.get("dedup_decision") != "canonical_keep":
            continue
        if candidate.get("workflow_scope") != "source_verified_local_api_macro":
            raise ValueError("candidate is not a verified local API macro")
        pair = _pair_key(candidate)
        decision = (
            "existing_training_pair_suppressed"
            if pair in existing_pairs
            else "canonical_keep"
        )
        ledger.append(
            {
                "candidate_id": candidate["candidate_id"],
                "training_pair_key": pair,
                "cross_pool_decision": decision,
                "training_admission": (
                    "not_granted_existing_training_pair_duplicate"
                    if decision != "canonical_keep"
                    else ADMISSION
                ),
            }
        )
        if decision != "canonical_keep":
            continue
        exported.append(
            {
                "schema_version": TRAINING_SCHEMA,
                "sample_id": f"qgis_api_acf_{candidate['candidate_id']}_train_v1",
                "record_id": candidate["record_id"],
                "candidate_id": candidate["candidate_id"],
                "source_root_id": candidate.get("source_root_id") or "unknown",
                "source_path": candidate["source_path"],
                "source_sha256": candidate["source_sha256"],
                "source_authority_key": candidate["source_authority_key"],
                "source_authority_basis": "normalized_source_body_sha256",
                "source_verification": "verified_sha256",
                "call_span_verification": "verified_local_add_calculate_field_macro",
                "source_span": candidate["source_span"],
                "evidence_snippet": candidate["source_snippet"],
                "operator_sequence": OPERATORS,
                "qgis_operator_chain": OPERATORS,
                "chain": OPERATORS,
                "l3_code_sequence": L3_CODES,
                "l3_token_ids": token_ids,
                "l3_sequence": [
                    SPECIAL_TOKENS["<START>"],
                    *token_ids,
                    SPECIAL_TOKENS["<END>"],
                ],
                "l3_codes": ["<START>", *L3_CODES, "<END>"],
                "n": 2,
                "task_name": candidate["task_name"],
                "task_description": candidate["task_description"],
                "task_type": "QGIS可验证低层API局部宏任务",
                "task_metadata": {
                    "task_type": "QGIS可验证低层API局部宏任务",
                    "task_name": candidate["task_name"],
                    "task_description": candidate["task_description"],
                },
                "workflow_scope": "source_verified_local_api_macro",
                "whole_function_semantics_admission": "not_granted",
                "dependency_edges": candidate["dependency_edges"],
                "parameter_facts": candidate["parameter_facts"],
                "known_omissions": candidate["known_omissions"],
                "source_region_key": candidate["source_region_key"],
                "call_graph_key": candidate["call_graph_key"],
                "normalized_dag_key": candidate["normalized_dag_key"],
                "cluster_id": pair,
                "source": "qgis_api_source_verified_add_calculate_field_macro_v1",
                "_training_quality": {
                    "tier": "source_verified_api_local_macro_deterministic",
                    "sample_weight": 0.7,
                },
                "taxonomy_profile": "stable125_authority_v1",
                "training_admission": ADMISSION,
                "split": SPLIT,
                "validation_eligible": False,
                "test_eligible": False,
                "production_merge": "not_granted",
            }
        )
    return exported, ledger, {
        "canonical_input_rows": sum(
            row.get("dedup_decision") == "canonical_keep" for row in candidates
        ),
        "existing_pool_rows": len(existing_rows),
        "cross_pool_suppressed": sum(
            row["cross_pool_decision"] != "canonical_keep" for row in ledger
        ),
        "train_only_rows": len(exported),
        "unique_source_authorities": len(
            {row["source_authority_key"] for row in exported}
        ),
        "unique_source_regions": len({row["source_region_key"] for row in exported}),
        "unique_call_graphs": len({row["call_graph_key"] for row in exported}),
        "unique_normalized_dags": len(
            {row["normalized_dag_key"] for row in exported}
        ),
        "unique_task_texts": len({row["task_description"] for row in exported}),
    }


def _read_json(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


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


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-replay", type=Path, required=True)
    parser.add_argument("--calibration-review", type=Path, required=True)
    parser.add_argument("--holdout-review", type=Path, required=True)
    parser.add_argument("--review-authority", type=Path, required=True)
    parser.add_argument("--existing-pool", type=Path, action="append", default=[])
    parser.add_argument("--stable125-extension", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--expected-complete-macros", type=int, default=30)
    parser.add_argument("--expected-source-authorities", type=int, default=28)
    args = parser.parse_args()
    if args.output_dir.exists() and any(args.output_dir.iterdir()):
        raise ValueError(f"output directory is not empty: {args.output_dir}")

    replay = _read_jsonl(args.source_replay)
    calibration = _read_jsonl(args.calibration_review)
    holdout = _read_jsonl(args.holdout_review)
    approval = _read_json(args.review_authority)
    reviewed_authorities = verify_review_authority(calibration, holdout, approval)
    complete = [row for row in replay if row.get("macro_boundary_status") == COMPLETE]
    if len(complete) != args.expected_complete_macros:
        raise ValueError("complete macro count mismatch")
    complete_authorities = {str(row["source_authority_key"]) for row in complete}
    if len(complete_authorities) != args.expected_source_authorities:
        raise ValueError("complete source authority count mismatch")
    if complete_authorities != reviewed_authorities:
        raise ValueError("review authority does not cover the complete population")

    candidates = [build_candidate(row) for row in complete]
    dedup_ledger, dedup_summary = build_four_layer_dedup(candidates)
    canonical = [row for row in dedup_ledger if row["dedup_decision"] == "canonical_keep"]
    existing_rows = [row for path in args.existing_pool for row in _read_jsonl(path)]
    extension = _read_json(args.stable125_extension)
    if extension.get("proposed_taxonomy") != "stable125":
        raise ValueError("expected stable125 extension")
    code_to_id = {
        **extension["existing_code_to_id"],
        **extension["proposed_code_to_id_additions"],
    }
    training, cross_pool_ledger, export_summary = export_train_only(
        canonical, existing_rows, code_to_id
    )
    summary = {
        "schema": "gis_recommend.qgis_api_add_calculate_field_delivery_summary.v1",
        "family_rule_id": RULE_ID,
        "complete_macro_units": len(complete),
        "complete_source_authorities": len(complete_authorities),
        "review_calibration_rows": len(calibration),
        "review_holdout_rows": len(holdout),
        "review_false_positive_rows": 0,
        "review_chain_truncation_rows": 0,
        **dedup_summary,
        **export_summary,
        "taxonomy_profile": "stable125_authority_v1",
        "training_admission": ADMISSION,
        "validation_eligible": False,
        "test_eligible": False,
        "production_merge": "not_granted",
        "training_run": False,
        "llm_called": False,
    }
    outputs: dict[str, Any] = {
        "description_candidates_v1.jsonl": candidates,
        "four_layer_dedup_ledger_v1.jsonl": dedup_ledger,
        "canonical_candidates_v1.jsonl": canonical,
        "cross_pool_dedup_ledger_v1.jsonl": cross_pool_ledger,
        "qgis_api_add_calculate_field_train_only_v1.jsonl": training,
        "summary_v1.json": summary,
    }
    paths: list[Path] = []
    for name, value in outputs.items():
        path = args.output_dir / name
        if name.endswith(".jsonl"):
            _write_jsonl(path, value)
        else:
            _write_json(path, value)
        paths.append(path)
    inputs = [
        args.source_replay,
        args.calibration_review,
        args.holdout_review,
        args.review_authority,
        *args.existing_pool,
        args.stable125_extension,
    ]
    _write_json(
        args.output_dir / "hash_ledger_v1.json",
        {
            "schema": "gis_recommend.hash_ledger.v1",
            "inputs": {
                str(index): {"path": str(path), "sha256": _sha256(path)}
                for index, path in enumerate(inputs)
            },
            "artifacts": {
                path.name: {"bytes": path.stat().st_size, "sha256": _sha256(path)}
                for path in paths
            },
        },
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
