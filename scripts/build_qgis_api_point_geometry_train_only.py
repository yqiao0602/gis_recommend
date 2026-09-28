#!/usr/bin/env python3
"""Export source-verified coordinate-pair point macros as bounded train-only rows."""

from __future__ import annotations

import argparse
import hashlib
import json
import tempfile
from collections import Counter
from collections.abc import Iterable
from pathlib import Path
from typing import Any

L3_CODE = "L3_01_01_05"
TOKEN_ID = 125
OPERATOR = "pyqgis:create_point_features_from_coordinates"
RULE_ID = "qgis-api-point-geometry-local-macro-v1"
ADMISSION = "granted_train_only_qgis_api_point_geometry_local_macro_v1"
SPLIT = "train_only_qgis_api_point_geometry_local_macro_v1"
SCHEMA = "qgis_api_training_sample_v1"
SPECIAL_TOKENS = {"<START>": -3, "<END>": -4}


def _json_key(value: Any) -> str:
    encoded = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _normalize_text(value: Any) -> str:
    return "".join(str(value or "").lower().split())


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


def _task_text(origin: str) -> tuple[str, str]:
    text_by_origin = {
        "iterated_record_coordinate_fields": (
            "从记录坐标字段创建点要素",
            "从迭代记录的坐标字段创建点要素并写入目标图层。",
        ),
        "literal_coordinate_pair": (
            "从固定坐标创建点要素",
            "根据源码中的固定坐标创建点要素并写入目标图层。",
        ),
        "derived_or_unresolved_coordinates": (
            "从坐标对创建点要素",
            "根据源码中的坐标对创建点要素并写入目标图层。",
        ),
    }
    try:
        return text_by_origin[origin]
    except KeyError as error:
        raise ValueError(f"unsupported coordinate origin: {origin}") from error


def build_candidates(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    for row in rows:
        reasons: list[str] = []
        if row.get("source_verification") != "verified_sha256":
            reasons.append("source_not_verified")
        if row.get("macro_status") != "complete":
            reasons.append("macro_not_complete")
        if row.get("point_geometry_rule_id") != RULE_ID:
            reasons.append("macro_rule_mismatch")
        if row.get("description_fidelity") != "passed_source_fact_only":
            reasons.append("description_fidelity_not_passed")
        if row.get("proposed_l3_code") != L3_CODE or int(
            row.get("proposed_l3_token_id") or -1
        ) != TOKEN_ID:
            reasons.append("stable126_mapping_mismatch")
        span = list(row.get("source_span") or [])
        if len(span) != 2 or int(span[0]) <= 0 or int(span[1]) < int(span[0]):
            reasons.append("source_span_incomplete")
            source_span = {"segments": []}
        else:
            source_span = {
                "segments": [{"line_start": int(span[0]), "line_end": int(span[1])}]
            }
        origin = str(row.get("coordinate_origin_kind") or "")
        try:
            task_name, task_description = _task_text(origin)
        except ValueError:
            task_name, task_description = "", ""
            reasons.append("coordinate_origin_not_admitted")
        snippet = str(row.get("evidence_snippet") or "")
        if not all(value in snippet for value in ("QgsGeometry.fromPoint", ".setGeometry", "addFeature")):
            reasons.append("macro_evidence_incomplete")
        passed = not reasons
        candidate_id = _json_key(
            {
                "unit_id": row.get("unit_id"),
                "source_authority_key": row.get("source_authority_key"),
                "source_span": source_span,
                "rule_id": RULE_ID,
            }
        )
        candidates.append(
            {
                **row,
                "schema": "gis_recommend.qgis_api_point_geometry_candidate.v1",
                "candidate_id": candidate_id,
                "operator_sequence": [OPERATOR],
                "candidate_l3_sequence": [L3_CODE],
                "source_span": source_span,
                "task_name": task_name if passed else "",
                "task_description": task_description if passed else "",
                "parameter_facts": {
                    "coordinate_origin_kind": origin,
                    "coordinate_component_expressions": list(
                        row.get("coordinate_component_expressions") or []
                    ),
                    "point_factory_call": row.get("point_factory_call"),
                    "sink_call": row.get("sink_call"),
                },
                "workflow_scope": "source_verified_local_api_macro",
                "whole_function_semantics_admission": "not_granted",
                "dependency_edges": [],
                "known_omissions": [
                    "whole_function_task_semantics_not_claimed",
                    "coordinate_provenance_is_limited_to_verified_local_macro_facts",
                    "runtime_coordinate_values_not_invented",
                ],
                "description_source": "source_verified_point_coordinate_macro_facts_only",
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
        )
    return candidates


def build_four_layer_dedup(
    candidates: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    eligible = sorted(
        (row for row in candidates if row.get("description_fidelity_passed") is True),
        key=lambda row: str(row["candidate_id"]),
    )
    canonical_by_pair: dict[str, dict[str, Any]] = {}
    ledger: list[dict[str, Any]] = []
    for row in eligible:
        source_region_key = _json_key(
            {"source_sha256": row.get("source_sha256"), "source_span": row["source_span"]}
        )
        call_graph_key = _json_key(
            {
                "source_sha256": row.get("source_sha256"),
                "point_factory_line": row.get("point_factory_line"),
                "setgeometry_line": row.get("setgeometry_line"),
                "sink_line": row.get("sink_line"),
            }
        )
        normalized_dag_key = _json_key(
            {
                "operators": [OPERATOR],
                "l3_sequence": [L3_CODE],
                "coordinate_origin_kind": row.get("coordinate_origin_kind"),
                "task_boundary": "coordinate_pair_to_same_feature_geometry_to_target_sink",
            }
        )
        task_text_key = _json_key(_normalize_text(row["task_description"]))
        training_pair_key = _pair_key(row)
        canonical = canonical_by_pair.get(training_pair_key)
        decision = "canonical_keep" if canonical is None else "exact_training_pair_suppressed"
        if canonical is None:
            canonical_by_pair[training_pair_key] = row
        ledger.append(
            {
                **row,
                "schema": "gis_recommend.qgis_api_point_geometry_dedup_ledger.v1",
                "source_region_key": source_region_key,
                "call_graph_key": call_graph_key,
                "normalized_dag_key": normalized_dag_key,
                "task_text_key": task_text_key,
                "training_pair_key": training_pair_key,
                "dedup_decision": decision,
                "canonical_candidate_id": (
                    row["candidate_id"] if canonical is None else canonical["candidate_id"]
                ),
            }
        )
    canonical = [row for row in ledger if row["dedup_decision"] == "canonical_keep"]
    return ledger, {
        "description_fidelity_passed": len(eligible),
        "description_fidelity_deferred": len(candidates) - len(eligible),
        "canonical_rows": len(canonical),
        "suppressed_exact_training_pairs": len(eligible) - len(canonical),
        "unique_source_authorities": len(
            {str(row.get("source_authority_key") or "") for row in eligible}
        ),
        "unique_source_regions": len({row["source_region_key"] for row in ledger}),
        "unique_call_graphs": len({row["call_graph_key"] for row in ledger}),
        "unique_normalized_dags": len({row["normalized_dag_key"] for row in ledger}),
        "unique_task_texts": len({row["task_text_key"] for row in ledger}),
        "coordinate_origin_counts": dict(
            sorted(Counter(str(row.get("coordinate_origin_kind") or "") for row in eligible).items())
        ),
    }


def export_train_only(
    canonical: list[dict[str, Any]], existing_rows: list[dict[str, Any]], code_to_id: dict[str, int]
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    if [int(code_to_id[L3_CODE])] != [TOKEN_ID]:
        raise ValueError("stable126 point-feature token contract mismatch")
    existing_pairs = {_pair_key(row) for row in existing_rows}
    exported: list[dict[str, Any]] = []
    cross_pool: list[dict[str, Any]] = []
    for row in canonical:
        pair = _pair_key(row)
        decision = "existing_training_pair_suppressed" if pair in existing_pairs else "canonical_keep"
        cross_pool.append(
            {
                "candidate_id": row["candidate_id"],
                "training_pair_key": pair,
                "cross_pool_decision": decision,
            }
        )
        if decision != "canonical_keep":
            continue
        exported.append(
            {
                "schema_version": SCHEMA,
                "sample_id": f"qgis_api_point_{row['candidate_id']}_train_v1",
                "record_id": row["record_id"],
                "candidate_id": row["candidate_id"],
                "source_root_id": row.get("source_root_id") or "unknown",
                "source_path": row["source_path"],
                "source_sha256": row["source_sha256"],
                "source_authority_key": row["source_authority_key"],
                "source_authority_basis": "normalized_source_body_sha256",
                "source_verification": "verified_sha256",
                "call_span_verification": "verified_point_coordinate_local_macro",
                "source_span": row["source_span"],
                "evidence_snippet": row["evidence_snippet"],
                "operator_sequence": [OPERATOR],
                "qgis_operator_chain": [OPERATOR],
                "chain": [OPERATOR],
                "l3_code_sequence": [L3_CODE],
                "l3_token_ids": [TOKEN_ID],
                "l3_sequence": [SPECIAL_TOKENS["<START>"], TOKEN_ID, SPECIAL_TOKENS["<END>"]],
                "l3_codes": ["<START>", L3_CODE, "<END>"],
                "n": 1,
                "task_name": row["task_name"],
                "task_description": row["task_description"],
                "task_type": "QGIS可验证低层API局部宏任务",
                "task_metadata": {
                    "task_type": "QGIS可验证低层API局部宏任务",
                    "task_name": row["task_name"],
                    "task_description": row["task_description"],
                },
                "workflow_scope": "source_verified_local_api_macro",
                "whole_function_semantics_admission": "not_granted",
                "dependency_edges": [],
                "parameter_facts": row["parameter_facts"],
                "known_omissions": row["known_omissions"],
                "source_region_key": row["source_region_key"],
                "call_graph_key": row["call_graph_key"],
                "normalized_dag_key": row["normalized_dag_key"],
                "cluster_id": pair,
                "source": "qgis_api_source_verified_point_coordinate_macro_v1",
                "_training_quality": {
                    "tier": "source_verified_api_local_macro_deterministic",
                    "sample_weight": 0.7,
                },
                "taxonomy_profile": "stable126_authority_v1",
                "training_admission": ADMISSION,
                "split": SPLIT,
                "validation_eligible": False,
                "test_eligible": False,
                "production_merge": "not_granted",
            }
        )
    return exported, cross_pool, {
        "canonical_input_rows": len(canonical),
        "existing_pool_rows": len(existing_rows),
        "cross_pool_suppressed": sum(
            row["cross_pool_decision"] != "canonical_keep" for row in cross_pool
        ),
        "train_only_rows": len(exported),
        "unique_source_authorities": len({row["source_authority_key"] for row in exported}),
        "unique_source_regions": len({row["source_region_key"] for row in exported}),
        "unique_call_graphs": len({row["call_graph_key"] for row in exported}),
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


def _write_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> None:
    _atomic_write(path, "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--descriptions", type=Path, required=True)
    parser.add_argument("--stable126-extension", type=Path, required=True)
    parser.add_argument("--existing-pool", type=Path, action="append", default=[])
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    if args.output_dir.exists() and any(args.output_dir.iterdir()):
        raise ValueError(f"output directory is not empty: {args.output_dir}")
    extension = _read_json(args.stable126_extension)
    if (
        extension.get("proposed_taxonomy") != "stable126"
        or extension.get("taxonomy_admission") != "granted"
    ):
        raise ValueError("expected granted stable126 extension")
    code_to_id = {
        **extension["existing_code_to_id"],
        **extension["proposed_code_to_id_additions"],
    }
    candidates = build_candidates(_read_jsonl(args.descriptions))
    dedup, dedup_summary = build_four_layer_dedup(candidates)
    canonical = [row for row in dedup if row["dedup_decision"] == "canonical_keep"]
    existing_rows = [row for path in args.existing_pool for row in _read_jsonl(path)]
    exported, cross_pool, export_summary = export_train_only(canonical, existing_rows, code_to_id)
    summary = {
        "schema": "gis_recommend.qgis_api_point_geometry_train_only_summary.v1",
        "rule_id": RULE_ID,
        "input_description_rows": len(candidates),
        "dedup": dedup_summary,
        "export": export_summary,
        "taxonomy_profile": "stable126_authority_v1",
        "llm_called": False,
        "training_run": False,
        "validation_eligible": False,
        "test_eligible": False,
        "production_merge": "not_granted",
    }
    outputs: dict[str, Any] = {
        "description_mapped_candidates_v1.jsonl": candidates,
        "four_layer_dedup_ledger_v1.jsonl": dedup,
        "canonical_candidates_v1.jsonl": canonical,
        "cross_pool_dedup_ledger_v1.jsonl": cross_pool,
        "qgis_api_point_geometry_train_only_v1.jsonl": exported,
        "summary_v1.json": summary,
    }
    paths: list[Path] = []
    for name, value in outputs.items():
        path = args.output_dir / name
        (_write_jsonl if name.endswith(".jsonl") else _write_json)(path, value)
        paths.append(path)
    inputs = [args.descriptions, args.stable126_extension, *args.existing_pool]
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
