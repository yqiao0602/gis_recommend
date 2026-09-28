#!/usr/bin/env python3
"""Build reviewed Raster Calculator local macros and export train-only rows."""

from __future__ import annotations

import argparse
import hashlib
import json
import tempfile
from collections import Counter
from collections.abc import Iterable
from pathlib import Path
from typing import Any

RULE_ID = "qgis-api-local-terminal-macro-census-v1"
REVIEW_ID = "raster-calculator-local-terminal-macro-review-v1"
L3_CODES = ["L3_03_03_A"]
OPERATORS = ["pyqgis:raster_calculator"]
SPECIAL_TOKENS = {"<START>": -3, "<END>": -4}
ADMISSION = "granted_train_only_qgis_api_raster_calculator_local_macro_v1"
SPLIT = "train_only_qgis_api_raster_calculator_local_macro_v1"
TRAINING_SCHEMA = "qgis_api_training_sample_v1"
DESCRIPTION_READY = {
    "literal",
    "fstring",
    "source_expression",
    "processing_parameter",
    "parameter_reference",
}


def _json_key(value: Any) -> str:
    encoded = json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _normalize_text(value: Any) -> str:
    return "".join(str(value or "").lower().split())


def verify_review_authority(
    review_rows: list[dict[str, Any]], summary: dict[str, Any]
) -> None:
    if summary.get("technical_review_id") != REVIEW_ID:
        raise ValueError("technical review ID mismatch")
    if summary.get("family_rule_promotion") != (
        "granted_for_raster_calculator_local_terminal_macro"
    ):
        raise ValueError("Raster Calculator family rule was not promoted")
    for key in (
        "source_sha_overlap",
        "normalized_body_overlap",
        "observed_false_positive_count",
        "observed_chain_truncation_count",
    ):
        if int(summary.get(key, -1)) != 0:
            raise ValueError(f"technical review gate failed: {key}")
    expected = int(summary.get("accepted_boundary_rows") or -1)
    if expected != len(review_rows) or expected < 1:
        raise ValueError("review row count mismatch")
    if any(row.get("technical_review_id") != REVIEW_ID for row in review_rows):
        raise ValueError("review packet contains a different review authority")
    if any(
        row.get("technical_boundary_decision") != "accept_complete_local_macro"
        or row.get("technical_mapping_decision")
        != "accept_exact_stable125_l3_03_03_a"
        for row in review_rows
    ):
        raise ValueError("review packet contains an unaccepted decision")


def _expression_description(fact: dict[str, Any]) -> tuple[str, str, str]:
    status = str(fact.get("status") or "missing")
    if status not in DESCRIPTION_READY:
        return "", "", "expression_provenance_not_description_ready"
    if status == "literal":
        expression = str(fact.get("value") or "").strip()
        if not expression:
            return "", "", "literal_expression_value_missing"
        return (
            "按明确表达式执行栅格计算",
            f"按栅格表达式“{expression}”计算输入栅格，并将计算结果写出为新的栅格数据。",
            "",
        )
    if status in {"fstring", "source_expression"}:
        expression = str(fact.get("source") or "").strip()
        if not expression:
            return "", "", "source_expression_missing"
        return (
            "按源码构造表达式执行栅格计算",
            f"按源码中确定构造的栅格表达式“{expression}”计算输入栅格，并将计算结果写出为新的栅格数据。",
            "",
        )
    if status == "processing_parameter":
        return (
            "按 Processing 参数表达式执行栅格计算",
            "按 Processing 参数提供的栅格表达式计算输入栅格，并将计算结果写出为新的栅格数据。",
            "",
        )
    return (
        "按调用参数表达式执行栅格计算",
        "按调用方传入的栅格表达式计算输入栅格，并将计算结果写出为新的栅格数据。",
        "",
    )


def build_candidate(row: dict[str, Any]) -> dict[str, Any]:
    reasons: list[str] = []
    if row.get("family_id") != "raster_calculator":
        reasons.append("family_contract_mismatch")
    if row.get("family_rule_id") != RULE_ID:
        reasons.append("family_rule_contract_mismatch")
    if row.get("macro_status") != "complete":
        reasons.append("macro_boundary_not_verified")
    if row.get("source_verification") != "verified_sha256":
        reasons.append("source_sha256_not_verified")
    if row.get("mapping_status") != "exact_stable125":
        reasons.append("stable125_mapping_not_exact")
    if list(row.get("candidate_l3_sequence") or []) != L3_CODES:
        reasons.append("stable125_l3_contract_mismatch")
    if row.get("constructor_signature") not in {
        "with_output_crs",
        "without_output_crs",
    }:
        reasons.append("constructor_signature_not_verified")

    task_name, task_description, expression_reason = _expression_description(
        row.get("expression_fact") or {}
    )
    if expression_reason:
        reasons.append(expression_reason)
    span = list(row.get("source_span") or [])
    if len(span) != 2 or int(span[0]) <= 0 or int(span[1]) < int(span[0]):
        reasons.append("macro_source_span_incomplete")
        source_span = {"segments": []}
    else:
        source_span = {
            "segments": [{"line_start": int(span[0]), "line_end": int(span[1])}]
        }
    snippet = str(row.get("source_snippet") or "")
    if "QgsRasterCalculator" not in snippet or "processCalculation" not in snippet:
        reasons.append("macro_endpoint_evidence_missing")

    passed = not reasons
    candidate_id = _json_key(
        {
            "unit_id": row.get("unit_id"),
            "source_authority_key": row.get("source_authority_key"),
            "source_span": source_span,
            "rule_id": RULE_ID,
        }
    )
    start = int(span[0]) if len(span) == 2 else 0
    end = int(span[1]) if len(span) == 2 else 0
    expression_fact = row.get("expression_fact") or {}
    return {
        **row,
        "schema": "gis_recommend.qgis_api_raster_calculator_candidate.v1",
        "candidate_id": candidate_id,
        "description_rule_id": "raster-calculator-expression-facts-zh-v1",
        "semantic_calls": OPERATORS,
        "semantic_call_sites": [
            {
                "name": "QgsRasterCalculator",
                "line_start": start,
                "line_end": start,
            },
            {
                "name": "processCalculation",
                "line_start": end,
                "line_end": end,
            },
        ],
        "candidate_l3_sequence": L3_CODES,
        "dependency_edges": [[0, 1]],
        "source_span": source_span,
        "task_name": task_name if passed else "",
        "task_description": task_description if passed else "",
        "parameter_facts": {
            "expression": expression_fact,
            "output_path": row.get("output_path_fact") or {},
            "output_format": row.get("output_format_fact") or {},
            "constructor_signature": row.get("constructor_signature"),
        },
        "workflow_scope": "source_verified_local_api_macro",
        "whole_function_semantics_admission": "not_granted",
        "known_omissions": [
            "whole_function_task_semantics_not_claimed",
            "upstream_raster_entry_construction_outside_local_macro_not_reconstructed",
            "runtime_expression_value_not_invented",
        ],
        "description_source": "source_verified_local_macro_expression_facts_only",
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
        expression_fact = candidate.get("expression_fact") or {}
        expression_signature = (
            expression_fact.get("value")
            or expression_fact.get("source")
            or expression_fact.get("status")
        )
        normalized_dag_key = _json_key(
            {
                "semantic_calls": candidate.get("semantic_calls"),
                "l3_sequence": candidate.get("candidate_l3_sequence"),
                "expression_status": expression_fact.get("status"),
                "expression_signature": _normalize_text(expression_signature),
                "task_boundary": "local_raster_calculator_terminal_macro",
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
                "schema": "gis_recommend.qgis_api_raster_calculator_dedup_ledger.v1",
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
    if token_ids != [34]:
        raise ValueError("stable125 Raster Calculator token contract mismatch")
    exported: list[dict[str, Any]] = []
    cross_pool: list[dict[str, Any]] = []
    for candidate in candidates:
        if candidate.get("dedup_decision") != "canonical_keep":
            continue
        if candidate.get("workflow_scope") != "source_verified_local_api_macro":
            raise ValueError("candidate is not a verified local API macro")
        if candidate.get("whole_function_semantics_admission") != "not_granted":
            raise ValueError("whole-function semantics must remain ungranted")
        pair = _pair_key(candidate)
        decision = (
            "existing_training_pair_suppressed"
            if pair in existing_pairs
            else "canonical_keep"
        )
        cross_pool.append(
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
                "sample_id": f"qgis_api_rc_{candidate['candidate_id']}_train_v1",
                "record_id": candidate["record_id"],
                "candidate_id": candidate["candidate_id"],
                "source_root_id": candidate.get("source_root_id") or "unknown",
                "source_path": candidate["source_path"],
                "source_sha256": candidate["source_sha256"],
                "source_authority_key": candidate["source_authority_key"],
                "source_authority_basis": "normalized_source_body_sha256",
                "source_verification": "verified_sha256",
                "call_span_verification": "verified_local_raster_calculator_terminal_macro",
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
                "n": 1,
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
                "source": "qgis_api_source_verified_raster_calculator_macro_v1",
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
    return exported, cross_pool, {
        "canonical_input_rows": sum(
            row.get("dedup_decision") == "canonical_keep" for row in candidates
        ),
        "existing_pool_rows": len(existing_rows),
        "cross_pool_suppressed": sum(
            row["cross_pool_decision"] != "canonical_keep" for row in cross_pool
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


def _write_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> None:
    _atomic_write(
        path,
        "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows),
    )


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--population", type=Path, required=True)
    parser.add_argument("--technical-review", type=Path, required=True)
    parser.add_argument("--technical-review-summary", type=Path, required=True)
    parser.add_argument("--existing-pool", type=Path, action="append", default=[])
    parser.add_argument("--stable125-extension", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    if args.output_dir.exists() and any(args.output_dir.iterdir()):
        raise ValueError(f"output directory is not empty: {args.output_dir}")

    population = _read_jsonl(args.population)
    review_rows = _read_jsonl(args.technical_review)
    review_summary = _read_json(args.technical_review_summary)
    verify_review_authority(review_rows, review_summary)
    candidates = [build_candidate(row) for row in population]
    dedup_ledger, dedup_summary = build_four_layer_dedup(candidates)
    canonical = [row for row in dedup_ledger if row["dedup_decision"] == "canonical_keep"]
    existing_rows = [
        row for path in args.existing_pool for row in _read_jsonl(path)
    ]
    extension = _read_json(args.stable125_extension)
    if extension.get("proposed_taxonomy") != "stable125":
        raise ValueError("expected stable125 extension")
    code_to_id = {
        **extension["existing_code_to_id"],
        **extension["proposed_code_to_id_additions"],
    }
    exported, cross_pool, export_summary = export_train_only(
        canonical, existing_rows, code_to_id
    )
    summary = {
        "schema": "gis_recommend.qgis_api_raster_calculator_train_only_summary.v1",
        "family_rule_id": RULE_ID,
        "technical_review_id": REVIEW_ID,
        "population_rows": len(population),
        "expression_status_counts": dict(
            sorted(
                Counter(
                    str((row.get("expression_fact") or {}).get("status") or "missing")
                    for row in population
                ).items()
            )
        ),
        "dedup": dedup_summary,
        "export": export_summary,
        "taxonomy_profile": "stable125_authority_v1",
        "training_admission": ADMISSION,
        "llm_called": False,
        "training_run": False,
        "validation_eligible": False,
        "test_eligible": False,
        "production_merge": "not_granted",
    }
    outputs: dict[str, Any] = {
        "description_candidates_v1.jsonl": candidates,
        "four_layer_dedup_ledger_v1.jsonl": dedup_ledger,
        "canonical_candidates_v1.jsonl": canonical,
        "cross_pool_dedup_ledger_v1.jsonl": cross_pool,
        "qgis_api_raster_calculator_train_only_v1.jsonl": exported,
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
        args.population,
        args.technical_review,
        args.technical_review_summary,
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
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
