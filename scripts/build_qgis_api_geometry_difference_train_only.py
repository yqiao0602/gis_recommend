#!/usr/bin/env python3
"""Build bounded train-only rows for verified geometry-difference macros."""

from __future__ import annotations

import argparse
import hashlib
import json
import tempfile
from pathlib import Path
from typing import Any

RULE_ID = "qgis-api-geometry-difference-local-macro-v1"
REVIEW_ID = "geometry-difference-bounded-full-population-review-v1"
L3_CODES = ["L3_02_02_04"]
OPERATORS = ["pyqgis:geometry_difference"]
SPECIAL_TOKENS = {"<START>": -3, "<END>": -4}
ADMISSION = "granted_train_only_qgis_api_geometry_difference_bounded_v1"
SPLIT = "train_only_qgis_api_geometry_difference_bounded_v1"


def _json_key(value: Any) -> str:
    encoded = json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _normalize_text(value: Any) -> str:
    return "".join(str(value or "").lower().split())


def verify_review_authority(
    review_rows: list[dict[str, Any]],
    summary: dict[str, Any],
    population: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    if summary.get("technical_review_id") != REVIEW_ID:
        raise ValueError("technical review ID mismatch")
    if summary.get("contract_rule_id") != RULE_ID:
        raise ValueError("contract rule mismatch")
    if summary.get("family_rule_promotion") != "not_granted_support_below_30":
        raise ValueError("bounded family promotion gate mismatch")
    for key in (
        "source_sha_overlap",
        "normalized_body_overlap",
        "observed_false_positive_count",
        "observed_chain_truncation_count",
    ):
        if int(summary.get(key, -1)) != 0:
            raise ValueError(f"technical review gate failed: {key}")
    accepted = [row for row in review_rows if row.get("macro_status") == "complete"]
    if len(review_rows) != int(summary.get("reviewed_population_rows") or -1):
        raise ValueError("reviewed population count mismatch")
    if len(accepted) != int(summary.get("accepted_boundary_rows") or -1):
        raise ValueError("accepted review count mismatch")
    population_ids = {str(row.get("unit_id") or "") for row in population}
    accepted_ids = {str(row.get("unit_id") or "") for row in accepted}
    if "" in accepted_ids or accepted_ids != population_ids:
        raise ValueError("accepted review authority does not equal complete population")
    if any(
        row.get("technical_boundary_decision")
        != "accept_complete_geometry_difference_local_macro"
        or row.get("technical_mapping_decision")
        != "accept_exact_stable125_l3_02_02_04"
        for row in accepted
    ):
        raise ValueError("review contains an unaccepted complete row")
    return accepted


def build_candidate(row: dict[str, Any]) -> dict[str, Any]:
    reasons: list[str] = []
    if row.get("contract_rule_id") != RULE_ID:
        reasons.append("contract_rule_mismatch")
    if row.get("macro_status") != "complete":
        reasons.append("macro_boundary_not_complete")
    if row.get("source_verification") != "verified_sha256":
        reasons.append("source_not_verified")
    if row.get("candidate_l3_sequence") != L3_CODES:
        reasons.append("l3_mapping_mismatch")
    if (row.get("receiver_operand_fact") or {}).get("status") != (
        "verified_geometry_accessor"
    ):
        reasons.append("receiver_operand_not_verified")
    if (row.get("argument_operand_fact") or {}).get("status") != (
        "verified_geometry_accessor"
    ):
        reasons.append("argument_operand_not_verified")
    snippet = str(row.get("evidence_snippet") or "")
    if ".difference(" not in snippet or ".setGeometry(" not in snippet:
        reasons.append("macro_evidence_incomplete")
    span = list(row.get("source_span") or [])
    if len(span) != 2 or int(span[0]) <= 0 or int(span[1]) < int(span[0]):
        reasons.append("source_span_incomplete")
        source_span = {"segments": []}
    else:
        source_span = {
            "segments": [{"line_start": int(span[0]), "line_end": int(span[1])}]
        }
    task_name = "擦除相交要素几何"
    task_description = (
        "从源要素几何中扣除与其相交的覆盖要素几何，并将剩余差集写入输出要素。"
    )
    passed = not reasons
    candidate_id = _json_key(
        {
            "unit_id": row.get("unit_id"),
            "source_authority_key": row.get("source_authority_key"),
            "source_span": source_span,
            "rule_id": RULE_ID,
        }
    )
    return {
        **row,
        "schema": "gis_recommend.qgis_api_geometry_difference_candidate.v1",
        "candidate_id": candidate_id,
        "description_rule_id": "geometry-difference-local-macro-facts-zh-v1",
        "semantic_calls": OPERATORS,
        "candidate_l3_sequence": L3_CODES,
        "dependency_edges": [],
        "source_span": source_span,
        "task_name": task_name if passed else "",
        "task_description": task_description if passed else "",
        "parameter_facts": {
            "receiver_geometry_source": (row.get("receiver_operand_fact") or {}).get(
                "source"
            ),
            "cover_geometry_source": (row.get("argument_operand_fact") or {}).get(
                "source"
            ),
            "accumulation_strategy": "guarded_loop_carried_difference",
            "sink_call": row.get("sink_call"),
        },
        "workflow_scope": "source_verified_local_api_macro",
        "whole_function_semantics_admission": "not_granted",
        "known_omissions": [
            "whole_function_task_semantics_not_claimed",
            "feature_selection_and_spatial_index_setup_outside_local_macro_not_reconstructed",
            "runtime_feature_values_not_invented",
        ],
        "description_source": "source_verified_local_difference_contract_facts_only",
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
    }


def build_four_layer_dedup(
    candidates: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    eligible = [row for row in candidates if row["description_fidelity_passed"]]
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
                "difference_call_line": candidate.get("difference_call_line"),
                "setgeometry_call_line": candidate.get("setgeometry_call_line"),
                "sink_call_line": candidate.get("sink_call_line"),
            }
        )
        normalized_dag_key = _json_key(
            {
                "semantic_calls": OPERATORS,
                "l3_sequence": L3_CODES,
                "task_boundary": "guarded_difference_accumulator_to_feature_sink",
            }
        )
        task_text_key = _json_key(_normalize_text(candidate["task_description"]))
        training_pair_key = _json_key(
            {
                "task_name": _normalize_text(candidate["task_name"]),
                "task_description": _normalize_text(candidate["task_description"]),
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
                "schema": "gis_recommend.qgis_api_geometry_difference_dedup_ledger.v1",
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
            }
        )
    return ledger, {
        "description_fidelity_passed": len(eligible),
        "description_fidelity_deferred": len(candidates) - len(eligible),
        "canonical_rows": sum(row["dedup_decision"] == "canonical_keep" for row in ledger),
        "suppressed_exact_training_pairs": sum(
            row["dedup_decision"] != "canonical_keep" for row in ledger
        ),
        "unique_source_authorities": len(
            {str(row["source_authority_key"]) for row in eligible}
        ),
        "unique_source_regions": len({row["source_region_key"] for row in ledger}),
        "unique_call_graphs": len({row["call_graph_key"] for row in ledger}),
        "unique_normalized_dags": len({row["normalized_dag_key"] for row in ledger}),
        "unique_task_texts": len({row["task_text_key"] for row in ledger}),
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
    ledger: list[dict[str, Any]],
    existing_rows: list[dict[str, Any]],
    code_to_id: dict[str, int],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    token_ids = [int(code_to_id[code]) for code in L3_CODES]
    if token_ids != [11]:
        raise ValueError("stable125 Erase token contract mismatch")
    existing_pairs = {_pair_key(row) for row in existing_rows}
    exported: list[dict[str, Any]] = []
    cross_pool: list[dict[str, Any]] = []
    for candidate in ledger:
        if candidate["dedup_decision"] != "canonical_keep":
            continue
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
            }
        )
        if decision != "canonical_keep":
            continue
        exported.append(
            {
                "schema_version": "qgis_api_training_sample_v1",
                "sample_id": f"qgis_api_gdiff_{candidate['candidate_id']}_train_v1",
                "record_id": candidate["record_id"],
                "candidate_id": candidate["candidate_id"],
                "source_root_id": candidate.get("source_root_id") or "unknown",
                "source_path": candidate["source_path"],
                "source_sha256": candidate["source_sha256"],
                "source_authority_key": candidate["source_authority_key"],
                "source_authority_basis": "normalized_source_body_sha256",
                "source_verification": "verified_sha256",
                "call_span_verification": "verified_geometry_difference_local_macro",
                "source_span": candidate["source_span"],
                "evidence_snippet": candidate["evidence_snippet"],
                "operator_sequence": OPERATORS,
                "qgis_operator_chain": OPERATORS,
                "chain": OPERATORS,
                "l3_code_sequence": L3_CODES,
                "l3_token_ids": token_ids,
                "l3_sequence": [SPECIAL_TOKENS["<START>"], *token_ids, SPECIAL_TOKENS["<END>"]],
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
                "source": "qgis_api_source_verified_geometry_difference_bounded_v1",
                "aggregate_source_pool": "qgis_api_geometry_difference_train_only_v1",
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
            row["dedup_decision"] == "canonical_keep" for row in ledger
        ),
        "existing_pool_rows": len(existing_rows),
        "cross_pool_suppressed": sum(
            row["cross_pool_decision"] != "canonical_keep" for row in cross_pool
        ),
        "train_only_rows": len(exported),
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
    _atomic_write(
        path, json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    )


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
    parser.add_argument("--expected-population", type=int, default=29)
    parser.add_argument("--expected-train-rows", type=int, default=1)
    args = parser.parse_args()
    if args.output_dir.exists() and any(args.output_dir.iterdir()):
        raise ValueError(f"output directory is not empty: {args.output_dir}")
    population = _read_jsonl(args.population)
    if len(population) != args.expected_population:
        raise ValueError("complete population count mismatch")
    review_rows = _read_jsonl(args.technical_review)
    review_summary = _read_json(args.technical_review_summary)
    accepted = verify_review_authority(review_rows, review_summary, population)
    candidates = [build_candidate(row) for row in accepted]
    ledger, dedup_summary = build_four_layer_dedup(candidates)
    existing_rows = [row for path in args.existing_pool for row in _read_jsonl(path)]
    extension = _read_json(args.stable125_extension)
    code_to_id = {
        **extension["existing_code_to_id"],
        **extension["proposed_code_to_id_additions"],
    }
    training, cross_pool, export_summary = export_train_only(
        ledger, existing_rows, code_to_id
    )
    if len(training) != args.expected_train_rows:
        raise ValueError("train-only row count mismatch")
    summary = {
        "schema": "gis_recommend.qgis_api_geometry_difference_delivery_summary.v1",
        "contract_rule_id": RULE_ID,
        "technical_review_id": REVIEW_ID,
        "accepted_population_rows": len(accepted),
        "accepted_source_authorities": len(
            {str(row["source_authority_key"]) for row in accepted}
        ),
        "family_rule_promotion": "not_granted_support_below_30",
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
    args.output_dir.mkdir(parents=True, exist_ok=True)
    outputs: dict[str, Any] = {
        "description_candidates_v1.jsonl": candidates,
        "four_layer_dedup_ledger_v1.jsonl": ledger,
        "cross_pool_dedup_ledger_v1.jsonl": cross_pool,
        "qgis_api_geometry_difference_train_only_v1.jsonl": training,
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
