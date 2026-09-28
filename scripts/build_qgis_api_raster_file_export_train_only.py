#!/usr/bin/env python3
"""Build source-verified GeoTIFF writer macros and export train-only rows."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import tempfile
from collections import Counter
from pathlib import Path
from typing import Any

RULE_ID = "qgis-api-raster-file-export-contract-v1"
REVIEW_ID = "raster-file-export-exact-geotiff-review-v1"
L3_CODES = ["L3_07_04_05"]
OPERATORS = ["pyqgis:export_raster_to_geotiff"]
SPECIAL_TOKENS = {"<START>": -3, "<END>": -4}
ADMISSION = "granted_train_only_qgis_api_raster_file_export_geotiff_v1"
SPLIT = "train_only_qgis_api_raster_file_export_geotiff_v1"
TRAINING_SCHEMA = "qgis_api_training_sample_v1"


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
) -> None:
    if summary.get("technical_review_id") != REVIEW_ID:
        raise ValueError("technical review ID mismatch")
    if summary.get("contract_rule_id") != RULE_ID:
        raise ValueError("contract rule mismatch")
    if summary.get("family_rule_promotion") != (
        "granted_exact_geotiff_local_writer_contract_only"
    ):
        raise ValueError("exact GeoTIFF writer contract was not promoted")
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
    population_units = {str(row.get("unit_id") or "") for row in population}
    review_units = {str(row.get("unit_id") or "") for row in review_rows}
    if "" in review_units or not review_units.issubset(population_units):
        raise ValueError("review rows are not a subset of the eligible population")
    if any(
        row.get("technical_boundary_decision")
        != "accept_complete_local_writer_macro"
        or row.get("technical_mapping_decision")
        != "accept_exact_stable125_l3_07_04_05"
        for row in review_rows
    ):
        raise ValueError("review packet contains an unaccepted decision")


def _bounded_fact_text(fact: dict[str, Any], *, maximum: int = 72) -> str:
    status = str(fact.get("status") or "")
    if status == "literal":
        value = str(fact.get("value") or "").strip()
    elif status in {"source_expression", "fstring"}:
        value = str(fact.get("source") or "").strip()
    else:
        return ""
    return value if value and len(value) <= maximum else ""


def _compact_label(value: str) -> str:
    normalized = value.strip().strip("'\"")
    if not normalized:
        return ""
    tail = re.split(r"[/\\]", normalized)[-1]
    return tail if len(tail) <= 48 else ""


def _destination_phrase(row: dict[str, Any]) -> tuple[str, str, str]:
    fact = row.get("output_path_fact") or {}
    fact_source = str(fact.get("source") or "").strip()
    fact_value = str(fact.get("value") or "").strip()
    fragments = [
        str(value).strip()
        for value in row.get("output_path_string_fragments") or []
        if str(value).strip()
    ]
    label_candidates = [fact_value, *reversed(fragments)]
    label = next(
        (
            compact
            for value in label_candidates
            if (compact := _compact_label(value))
            and compact.lower() not in {".tif", ".tiff", "*.tif", "*.tiff"}
        ),
        "",
    )
    signature = fact_value or fact_source or " ".join(fragments) or "caller_provided_output"
    if label:
        return f"GeoTIFF 文件“{label}”", signature, label
    if fact_source and len(fact_source) <= 36:
        return (
            f"源码目标“{fact_source}”指定的 GeoTIFF 文件",
            signature,
            fact_source,
        )
    return "调用方指定的 GeoTIFF 文件", signature, ""


def _source_root(value: str) -> str:
    match = re.match(r"([A-Za-z_][A-Za-z0-9_]*)", value)
    return match.group(1) if match else ""


def _geometry_phrases(row: dict[str, Any]) -> tuple[list[str], dict[str, str]]:
    facts = {
        "columns": _bounded_fact_text(row.get("column_count_fact") or {}),
        "rows": _bounded_fact_text(row.get("row_count_fact") or {}),
        "extent": _bounded_fact_text(row.get("extent_fact") or {}),
        "crs": _bounded_fact_text(row.get("crs_fact") or {}),
        "transform_context": _bounded_fact_text(
            row.get("transform_context_fact") or {}
        ),
    }
    phrases: list[str] = []
    if facts["columns"] and facts["rows"]:
        if facts["columns"].isdigit() and facts["rows"].isdigit():
            phrases.append(f"输出尺寸为 {facts['columns']}×{facts['rows']} 像元")
        else:
            roots = {
                _source_root(facts["columns"]),
                _source_root(facts["rows"]),
            } - {""}
            if len(roots) == 1:
                phrases.append(f"输出尺寸取自源码对象“{next(iter(roots))}”")
            else:
                phrases.append("输出尺寸沿用源码计算结果")
    if facts["extent"] or facts["crs"]:
        phrases.append("输出范围和 CRS 沿用源码设定")
    if facts["transform_context"]:
        phrases.append("使用源码提供的坐标变换上下文")
    return phrases, {key: value for key, value in facts.items() if value}


def build_candidate(row: dict[str, Any]) -> dict[str, Any]:
    reasons: list[str] = []
    if row.get("contract_rule_id") != RULE_ID:
        reasons.append("contract_rule_mismatch")
    if row.get("family_id") != "raster_file_export":
        reasons.append("family_contract_mismatch")
    if row.get("macro_status") != "complete":
        reasons.append("macro_boundary_not_verified")
    if row.get("source_verification") != "verified_sha256":
        reasons.append("source_sha256_not_verified")
    if row.get("contract_class") != "geotiff" or row.get("contract_status") != "source_backed":
        reasons.append("geotiff_contract_not_source_backed")
    if row.get("mapping_status") != "exact_stable125_existing_l3":
        reasons.append("stable125_mapping_not_exact")
    if list(row.get("candidate_l3_sequence") or []) != L3_CODES:
        reasons.append("stable125_l3_contract_mismatch")
    if row.get("write_raster_overload") not in {
        "with_transform_context",
        "without_transform_context",
    }:
        reasons.append("write_raster_overload_not_verified")
    span = list(row.get("source_span") or [])
    if len(span) != 2 or int(span[0]) <= 0 or int(span[1]) < int(span[0]):
        reasons.append("macro_source_span_incomplete")
        source_span = {"segments": []}
    else:
        source_span = {
            "segments": [{"line_start": int(span[0]), "line_end": int(span[1])}]
        }
    snippet = str(row.get("contract_evidence_snippet") or "")
    if "QgsRasterFileWriter" not in snippet or "writeRaster" not in snippet:
        reasons.append("macro_endpoint_evidence_missing")

    destination_phrase, destination_signature, destination_label = _destination_phrase(row)
    geometry_phrases, geometry_facts = _geometry_phrases(row)
    creation_options = sorted(
        {
            str(value).strip()
            for value in row.get("creation_option_strings") or []
            if str(value).strip() and len(str(value).strip()) <= 80
        }
    )
    description_parts = [f"将栅格管线写出为{destination_phrase}"]
    description_parts.extend(geometry_phrases)
    if creation_options:
        description_parts.append(
            "采用创建选项“" + "；".join(creation_options) + "”"
        )
    task_name = (
        f"导出 GeoTIFF 栅格至 {destination_label}"
        if destination_label
        else "导出 GeoTIFF 栅格"
    )
    task_description = "，".join(description_parts) + "。"
    if len(task_description) > 220:
        reasons.append("deterministic_description_too_long")

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
    return {
        **row,
        "schema": "gis_recommend.qgis_api_raster_file_export_candidate.v1",
        "candidate_id": candidate_id,
        "description_rule_id": "raster-file-export-source-contract-facts-zh-v1",
        "semantic_calls": OPERATORS,
        "semantic_call_sites": [
            {
                "name": "QgsRasterFileWriter",
                "line_start": start,
                "line_end": start,
            },
            {"name": "writeRaster", "line_start": end, "line_end": end},
        ],
        "candidate_l3_sequence": L3_CODES,
        "dependency_edges": [],
        "source_span": source_span,
        "task_name": task_name if passed else "",
        "task_description": task_description if passed else "",
        "parameter_facts": {
            "output_contract": "GeoTIFF",
            "contract_basis": row.get("contract_basis"),
            "destination_signature": destination_signature,
            "geometry": geometry_facts,
            "creation_options": creation_options,
            "write_raster_overload": row.get("write_raster_overload"),
        },
        "workflow_scope": "source_verified_local_api_macro",
        "whole_function_semantics_admission": "not_granted",
        "known_omissions": [
            "whole_function_task_semantics_not_claimed",
            "upstream_raster_pipe_construction_outside_local_macro_not_reconstructed",
            "runtime_output_path_value_not_invented",
        ],
        "description_source": "source_verified_local_writer_contract_facts_only",
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
            }
        )
        normalized_dag_key = _json_key(
            {
                "semantic_calls": OPERATORS,
                "l3_sequence": L3_CODES,
                "write_raster_overload": candidate.get("write_raster_overload"),
                "contract_basis": candidate.get("contract_basis"),
                "task_boundary": "local_raster_file_writer_terminal_macro",
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
                "schema": "gis_recommend.qgis_api_raster_file_export_dedup_ledger.v1",
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
        "contract_basis_counts": dict(
            sorted(Counter(str(row.get("contract_basis") or "") for row in eligible).items())
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
    if token_ids != [68]:
        raise ValueError("stable125 GeoTIFF export token contract mismatch")
    exported: list[dict[str, Any]] = []
    cross_pool: list[dict[str, Any]] = []
    for candidate in candidates:
        if candidate.get("dedup_decision") != "canonical_keep":
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
                "sample_id": f"qgis_api_rfe_{candidate['candidate_id']}_train_v1",
                "record_id": candidate["record_id"],
                "candidate_id": candidate["candidate_id"],
                "source_root_id": candidate.get("source_root_id") or "unknown",
                "source_path": candidate["source_path"],
                "source_sha256": candidate["source_sha256"],
                "source_authority_key": candidate["source_authority_key"],
                "source_authority_basis": "normalized_source_body_sha256",
                "source_verification": "verified_sha256",
                "call_span_verification": "verified_local_geotiff_writer_macro",
                "source_span": candidate["source_span"],
                "evidence_snippet": candidate["contract_evidence_snippet"],
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
                "dependency_edges": [],
                "parameter_facts": candidate["parameter_facts"],
                "known_omissions": candidate["known_omissions"],
                "source_region_key": candidate["source_region_key"],
                "call_graph_key": candidate["call_graph_key"],
                "normalized_dag_key": candidate["normalized_dag_key"],
                "cluster_id": pair,
                "source": "qgis_api_source_verified_geotiff_writer_macro_v1",
                "aggregate_source_pool": "qgis_api_raster_file_export_train_only_v1",
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
    parser.add_argument("--expected-units", type=int, default=53)
    parser.add_argument("--expected-authorities", type=int, default=49)
    args = parser.parse_args()
    if args.output_dir.exists() and any(args.output_dir.iterdir()):
        raise ValueError(f"output directory is not empty: {args.output_dir}")
    population = _read_jsonl(args.population)
    if len(population) != args.expected_units:
        raise ValueError("eligible population size mismatch")
    if len({row["source_authority_key"] for row in population}) != args.expected_authorities:
        raise ValueError("eligible source authority count mismatch")
    review_rows = _read_jsonl(args.technical_review)
    review_summary = _read_json(args.technical_review_summary)
    verify_review_authority(review_rows, review_summary, population)
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
    training, cross_pool, export_summary = export_train_only(
        canonical, existing_rows, code_to_id
    )
    summary = {
        "schema": "gis_recommend.qgis_api_raster_file_export_delivery_summary.v1",
        "contract_rule_id": RULE_ID,
        "technical_review_id": REVIEW_ID,
        "population_units": len(population),
        "population_source_authorities": len(
            {str(row["source_authority_key"]) for row in population}
        ),
        "review_calibration_rows": int(review_summary["calibration_rows"]),
        "review_holdout_rows": int(review_summary["holdout_rows"]),
        "review_false_positive_rows": 0,
        "review_chain_truncation_rows": 0,
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
        "qgis_api_raster_file_export_train_only_v1.jsonl": training,
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
