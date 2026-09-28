#!/usr/bin/env python3
"""Build and export reviewed local QGIS layer ``setCrs`` train-only rows."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import tempfile
from collections import Counter
from collections.abc import Iterable
from pathlib import Path
from typing import Any

RULE_ID = "qgis-api-local-layer-set-crs-metadata-v1"
REVIEW_ID = "qgis-api-local-layer-set-crs-source-disjoint-review-v1"
L3_CODES = ["L3_01_10_02"]
OPERATORS = ["pyqgis:set_layer_crs_metadata"]
SPECIAL_TOKENS = {"<START>": -3, "<END>": -4}
ADMISSION = "granted_train_only_qgis_api_set_crs_local_macro_v1"
SPLIT = "train_only_qgis_api_set_crs_local_macro_v1"
TRAINING_SCHEMA = "qgis_api_training_sample_v1"


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
    if summary.get("family_rule_id") != RULE_ID:
        raise ValueError("family rule mismatch")
    if summary.get("family_rule_promotion") != (
        "granted_for_local_qgis_layer_set_crs_metadata_macro"
    ):
        raise ValueError("setCrs family rule was not promoted")
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
        raise ValueError("review authority mismatch")


def _layer_kind(row: dict[str, Any]) -> str:
    constructor = str(row.get("receiver_constructor") or "").rsplit(".", 1)[-1]
    if constructor == "QgsVectorLayer":
        return "矢量"
    if constructor == "QgsRasterLayer":
        return "栅格"
    return ""


def _literal_crs_label(value: Any) -> str:
    text = str(value).strip()
    match = re.search(r"(?i)epsg\s*:\s*(\d+)", text)
    if match:
        return f"EPSG:{match.group(1)}"
    if re.fullmatch(r"\d+", text):
        return f"EPSG:{text}"
    return text if 0 < len(text) <= 80 else ""


def _description(row: dict[str, Any]) -> tuple[str, str, str, str]:
    kind = _layer_kind(row)
    if not kind:
        return "", "", "", "receiver_layer_kind_unknown"
    fact = row.get("crs_fact") or {}
    status = str(fact.get("status") or "missing")
    value_fact = fact.get("value_fact") or {}
    if status == "crs_constructor" and value_fact.get("status") == "literal":
        label = _literal_crs_label(value_fact.get("value"))
        if not label:
            return "", "", "", "literal_crs_label_not_usable"
        strategy = f"literal:{label.lower()}"
        return (
            f"为{kind}图层定义 {label} 坐标系",
            f"将{kind}图层的坐标参考系元数据定义为 {label}，不变换图层中的坐标值。",
            strategy,
            "",
        )

    source = str(fact.get("source") or "").lower().replace("_", "")
    constructor = str(fact.get("constructor") or "").lower()
    if "qgsproject" in source:
        source_role = "project_crs"
        source_text = "当前 QGIS 工程的坐标参考系"
    elif ".sourcecrs(" in source or ".crs(" in source:
        source_role = "source_layer_crs"
        source_text = "源图层的坐标参考系"
    elif status == "crs_constructor" and "fromepsgid" in constructor:
        source_role = "dynamic_epsg_identifier"
        source_text = "源码或调用参数提供的 EPSG 标识"
    elif status == "crs_constructor":
        source_role = "dynamic_crs_identifier"
        source_text = "源码或调用参数提供的 CRS 标识"
    elif status == "source_expression":
        source_role = "source_defined_crs_object"
        source_text = "源码中已构造的坐标参考系对象"
    else:
        return "", "", "", "crs_fact_not_description_ready"
    return (
        f"按{source_text}定义{kind}图层坐标系",
        f"将{kind}图层的坐标参考系元数据设置为{source_text}，不变换图层中的坐标值。",
        source_role,
        "",
    )


def build_candidate(row: dict[str, Any]) -> dict[str, Any]:
    reasons: list[str] = []
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
    task_name, task_description, strategy, description_reason = _description(row)
    if description_reason:
        reasons.append(description_reason)
    span = list(row.get("source_span") or [])
    if len(span) != 2 or int(span[0]) <= 0 or int(span[1]) < int(span[0]):
        reasons.append("macro_source_span_incomplete")
        source_span = {"segments": []}
    else:
        source_span = {
            "segments": [{"line_start": int(span[0]), "line_end": int(span[1])}]
        }
    if "setCrs" not in str(row.get("source_snippet") or ""):
        reasons.append("set_crs_evidence_missing")
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
        "schema": "gis_recommend.qgis_api_set_crs_candidate.v1",
        "candidate_id": candidate_id,
        "description_rule_id": "set-crs-source-role-facts-zh-v1",
        "semantic_calls": OPERATORS,
        "semantic_call_sites": [
            {
                "name": "setCrs",
                "line_start": int(span[0]) if len(span) == 2 else 0,
                "line_end": int(span[1]) if len(span) == 2 else 0,
            }
        ],
        "candidate_l3_sequence": L3_CODES,
        "dependency_edges": [],
        "source_span": source_span,
        "task_name": task_name if passed else "",
        "task_description": task_description if passed else "",
        "parameter_facts": {
            "layer_kind": _layer_kind(row),
            "crs": row.get("crs_fact") or {},
            "description_strategy": strategy,
        },
        "workflow_scope": "source_verified_local_api_macro",
        "whole_function_semantics_admission": "not_granted",
        "known_omissions": [
            "whole_function_task_semantics_not_claimed",
            "coordinate_values_are_not_transformed",
            "runtime_crs_identifier_not_invented",
        ],
        "description_source": "source_verified_local_set_crs_facts_only",
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
                "layer_kind": candidate.get("parameter_facts", {}).get("layer_kind"),
                "description_strategy": candidate.get("parameter_facts", {}).get(
                    "description_strategy"
                ),
                "task_boundary": "local_layer_set_crs_metadata",
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
                "schema": "gis_recommend.qgis_api_set_crs_dedup_ledger.v1",
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
        "description_strategy_counts": dict(
            sorted(
                Counter(
                    str(row.get("parameter_facts", {}).get("description_strategy") or "")
                    for row in eligible
                ).items()
            )
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
    if token_ids != [121]:
        raise ValueError("stable125 Define Projection token contract mismatch")
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
                "sample_id": f"qgis_api_scrs_{candidate['candidate_id']}_train_v1",
                "record_id": candidate["record_id"],
                "candidate_id": candidate["candidate_id"],
                "source_root_id": candidate.get("source_root_id") or "unknown",
                "source_path": candidate["source_path"],
                "source_sha256": candidate["source_sha256"],
                "source_authority_key": candidate["source_authority_key"],
                "source_authority_basis": "normalized_source_body_sha256",
                "source_verification": "verified_sha256",
                "call_span_verification": "verified_local_layer_set_crs_metadata_macro",
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
                "source": "qgis_api_source_verified_set_crs_metadata_macro_v1",
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


def _write_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> None:
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
    code_to_id = {
        **extension["existing_code_to_id"],
        **extension["proposed_code_to_id_additions"],
    }
    exported, cross_pool, export_summary = export_train_only(
        canonical, existing_rows, code_to_id
    )
    summary = {
        "schema": "gis_recommend.qgis_api_set_crs_train_only_summary.v1",
        "family_rule_id": RULE_ID,
        "technical_review_id": REVIEW_ID,
        "population_rows": len(population),
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
        "qgis_api_set_crs_train_only_v1.jsonl": exported,
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
