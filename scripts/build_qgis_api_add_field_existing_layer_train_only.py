#!/usr/bin/env python3
"""Build reviewed existing-layer Add Field macros as isolated train-only rows."""

from __future__ import annotations

import argparse
import hashlib
import json
import tempfile
from collections import Counter
from pathlib import Path
from typing import Any

RULE_ID = "add-field-existing-layer-local-macro-v1"
REVIEW_ID = "qgis-api-add-field-existing-layer-bounded-review-v2"
COMPLETE = "verified_complete_existing_layer_macro"
L3_CODES = ["L3_01_02_01"]
OPERATORS = ["pyqgis:add_field"]
ADMISSION = "granted_train_only_qgis_api_add_field_existing_layer_local_macro_v1"
SPLIT = "train_only_qgis_api_add_field_existing_layer_local_macro_v1"
TRAINING_SCHEMA = "qgis_api_training_sample_v1"


def _json_key(value: Any) -> str:
    encoded = json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _normalize_text(value: Any) -> str:
    return "".join(str(value or "").lower().split())


def _set_sha256(values: set[str]) -> str:
    return hashlib.sha256(("\n".join(sorted(values)) + "\n").encode()).hexdigest()


def verify_review_authority(
    review_rows: list[dict[str, Any]],
    summary: dict[str, Any],
    population: list[dict[str, Any]],
) -> None:
    if summary.get("technical_review_id") != REVIEW_ID:
        raise ValueError("technical review ID mismatch")
    if summary.get("family_rule_id") != RULE_ID:
        raise ValueError("family rule mismatch")
    if summary.get("bounded_batch_admission") != "granted_all_reviewed_units":
        raise ValueError("bounded batch was not admitted")
    if summary.get("family_rule_promotion") != "not_granted_bounded_batch_only":
        raise ValueError("review must not promote the family")
    for key in (
        "source_sha_overlap",
        "normalized_body_overlap",
        "observed_false_positive_count",
        "observed_chain_truncation_count",
    ):
        if int(summary.get(key, -1)) != 0:
            raise ValueError(f"technical review gate failed: {key}")
    if int(summary.get("accepted_macro_units") or -1) != len(review_rows):
        raise ValueError("accepted review unit count mismatch")
    reviewed_units = {str(row.get("candidate_unit_id") or "") for row in review_rows}
    population_units = {str(row.get("candidate_unit_id") or "") for row in population}
    if "" in reviewed_units or len(reviewed_units) != len(review_rows):
        raise ValueError("review unit IDs are missing or repeated")
    if reviewed_units != population_units:
        raise ValueError("review does not cover every bounded population unit")
    if _set_sha256(reviewed_units) != summary.get("accepted_unit_set_sha256"):
        raise ValueError("reviewed unit-set hash mismatch")
    reviewed_authorities = {
        str(row.get("source_authority_key") or "") for row in review_rows
    }
    if _set_sha256(reviewed_authorities) != summary.get("accepted_authority_set_sha256"):
        raise ValueError("reviewed authority-set hash mismatch")
    if any(row.get("technical_review_id") != REVIEW_ID for row in review_rows):
        raise ValueError("review authority mismatch")


def build_candidate(row: dict[str, Any]) -> dict[str, Any]:
    reasons: list[str] = []
    if row.get("family_rule_id") != RULE_ID:
        reasons.append("family_rule_contract_mismatch")
    if row.get("macro_boundary_status") != COMPLETE:
        reasons.append("macro_boundary_not_verified")
    if row.get("source_verification") != "verified_sha256":
        reasons.append("source_sha256_not_verified")
    if row.get("mapping_status") != "existing_stable125_l3":
        reasons.append("stable125_mapping_not_exact")
    if row.get("proposed_l3_code") != L3_CODES[0]:
        reasons.append("stable125_l3_contract_mismatch")
    fields = sorted(str(value) for value in row.get("field_names") or [])
    if not fields or len(fields) != len(set(fields)):
        reasons.append("literal_field_names_missing_or_repeated")
    start = int(row.get("macro_line_start") or 0)
    end = int(row.get("macro_line_end") or 0)
    if start <= 0 or end < start:
        reasons.append("macro_source_span_incomplete")
    if row.get("excluded_additional_scope_semantics"):
        reasons.append("additional_scope_semantics_present")

    field_text = "、".join(fields)
    task_name = f"新增字段 {field_text}"
    task_description = (
        f"向现有矢量图层新增字段 {field_text}，并提交字段结构更新。"
    )
    passed = not reasons
    source_span = {"segments": [{"line_start": start, "line_end": end}]}
    candidate_id = _json_key(
        {
            "candidate_unit_id": row.get("candidate_unit_id"),
            "source_authority_key": row.get("source_authority_key"),
            "source_span": source_span,
            "field_names": fields,
            "rule_id": RULE_ID,
        }
    )
    return {
        **row,
        "schema": "gis_recommend.qgis_api_add_field_existing_layer_candidate.v1",
        "candidate_id": candidate_id,
        "description_rule_id": "add-field-existing-layer-literal-names-zh-v1",
        "semantic_calls": OPERATORS,
        "semantic_call_sites": [
            {
                "name": OPERATORS[0],
                "line_start": start,
                "line_end": end,
                "arguments": fields,
            }
        ],
        "candidate_l3_sequence": L3_CODES,
        "dependency_edges": [],
        "source_span": source_span,
        "task_name": task_name if passed else "",
        "task_description": task_description if passed else "",
        "parameter_facts": {
            "field_names": fields,
            "field_count": len(fields),
            "schema_add_call_count": int(row.get("schema_add_call_count") or 0),
        },
        "workflow_scope": "source_verified_local_api_macro",
        "whole_function_semantics_admission": "not_granted",
        "known_omissions": [
            "whole_function_task_semantics_not_claimed",
            "field_types_not_exported_without_structured_ast_facts",
            "field_value_calculation_not_claimed",
        ],
        "description_source": "source_verified_literal_field_names_only",
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
                "dependency_edges": [],
            }
        )
        normalized_dag_key = _json_key(
            {
                "semantic_calls": OPERATORS,
                "l3_sequence": L3_CODES,
                "field_count": len(candidate.get("field_names") or []),
                "task_boundary": "existing_layer_add_field_schema_commit",
            }
        )
        task_text_key = _json_key(_normalize_text(candidate.get("task_description")))
        training_pair_key = _json_key(
            {
                "task_name": _normalize_text(candidate.get("task_name")),
                "task_description": _normalize_text(candidate.get("task_description")),
                "l3_sequence": L3_CODES,
            }
        )
        canonical = canonical_by_pair.get(training_pair_key)
        decision = "canonical_keep" if canonical is None else "exact_training_pair_suppressed"
        if canonical is None:
            canonical_by_pair[training_pair_key] = candidate
        ledger.append(
            {
                **candidate,
                "schema": "gis_recommend.qgis_api_add_field_existing_layer_dedup_ledger.v1",
                "source_region_key": source_region_key,
                "call_graph_key": call_graph_key,
                "normalized_dag_key": normalized_dag_key,
                "task_text_key": task_text_key,
                "training_pair_key": training_pair_key,
                "dedup_decision": decision,
                "canonical_candidate_id": (
                    candidate["candidate_id"] if canonical is None else canonical["candidate_id"]
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
        "field_count_distribution": dict(
            sorted(Counter(len(row.get("field_names") or []) for row in eligible).items())
        ),
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
    if token_ids != [1]:
        raise ValueError("stable125 Add Field token contract mismatch")
    exported: list[dict[str, Any]] = []
    ledger: list[dict[str, Any]] = []
    for candidate in candidates:
        if candidate.get("dedup_decision") != "canonical_keep":
            continue
        pair = _pair_key(candidate)
        decision = "existing_training_pair_suppressed" if pair in existing_pairs else "canonical_keep"
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
                "sample_id": f"qgis_api_af_{candidate['candidate_id']}_train_v1",
                "record_id": candidate["record_id"],
                "candidate_id": candidate["candidate_id"],
                "source_root_id": candidate.get("source_root_id") or "unknown",
                "source_path": candidate["source_path"],
                "source_sha256": candidate["source_sha256"],
                "source_authority_key": candidate["source_authority_key"],
                "source_authority_basis": "normalized_source_body_sha256",
                "source_verification": "verified_sha256",
                "call_span_verification": "verified_existing_layer_add_field_schema_commit",
                "source_span": candidate["source_span"],
                "evidence_snippet": candidate["source_snippet"],
                "operator_sequence": OPERATORS,
                "qgis_operator_chain": OPERATORS,
                "chain": OPERATORS,
                "l3_code_sequence": L3_CODES,
                "l3_token_ids": token_ids,
                "l3_sequence": [-3, *token_ids, -4],
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
                "dependency_edges": [],
                "parameter_facts": candidate["parameter_facts"],
                "known_omissions": candidate["known_omissions"],
                "source_region_key": candidate["source_region_key"],
                "call_graph_key": candidate["call_graph_key"],
                "normalized_dag_key": candidate["normalized_dag_key"],
                "cluster_id": pair,
                "source": "qgis_api_source_verified_add_field_existing_layer_macro_v1",
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
        "unique_normalized_dags": len({row["normalized_dag_key"] for row in exported}),
        "unique_task_texts": len({row["task_description"] for row in exported}),
    }


def _read_json(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


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


def _write_json(path: Path, value: Any) -> None:
    _atomic_write(path, json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n")


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    _atomic_write(
        path,
        "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows),
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--population", type=Path, required=True)
    parser.add_argument("--technical-review", type=Path, required=True)
    parser.add_argument("--technical-review-summary", type=Path, required=True)
    parser.add_argument("--existing-pool", type=Path, action="append", default=[])
    parser.add_argument("--stable125-extension", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--expected-units", type=int, default=30)
    args = parser.parse_args()
    if args.output_dir.exists() and any(args.output_dir.iterdir()):
        raise ValueError(f"output directory is not empty: {args.output_dir}")
    population = _read_jsonl(args.population)
    if len(population) != args.expected_units:
        raise ValueError("bounded population size mismatch")
    review_rows = _read_jsonl(args.technical_review)
    review_summary = _read_json(args.technical_review_summary)
    verify_review_authority(review_rows, review_summary, population)
    candidates = [build_candidate(row) for row in population]
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
    training, cross_pool, export_summary = export_train_only(
        canonical, existing_rows, code_to_id
    )
    summary = {
        "schema": "gis_recommend.qgis_api_add_field_existing_layer_delivery_summary.v1",
        "family_rule_id": RULE_ID,
        "technical_review_id": REVIEW_ID,
        "bounded_population_units": len(population),
        "bounded_source_authorities": len(
            {str(row["source_authority_key"]) for row in population}
        ),
        "review_calibration_rows": int(review_summary["calibration_rows"]),
        "review_holdout_rows": int(review_summary["holdout_rows"]),
        "review_false_positive_rows": 0,
        "review_chain_truncation_rows": 0,
        "family_rule_promotion": "not_granted_bounded_batch_only",
        "dedup": dedup_summary,
        "export": export_summary,
        "taxonomy_profile": "stable125_authority_v1",
        "training_admission": ADMISSION,
        "training_run": False,
        "validation_eligible": False,
        "test_eligible": False,
        "production_merge": "not_granted",
        "llm_called": False,
    }
    outputs: dict[str, Any] = {
        "description_candidates_v1.jsonl": candidates,
        "four_layer_dedup_ledger_v1.jsonl": dedup_ledger,
        "canonical_candidates_v1.jsonl": canonical,
        "cross_pool_dedup_ledger_v1.jsonl": cross_pool,
        "qgis_api_add_field_existing_layer_train_only_v1.jsonl": training,
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
