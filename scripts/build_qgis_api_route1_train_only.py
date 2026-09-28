#!/usr/bin/env python3
"""Build deterministic train-only candidates from route-1 verified rows.

Each verified row carries core operations whose method/line/arguments were
checked against the AST by the pilot verifier.  The first non-structural core
operation (excluding setGeometry/setAttributes/attribute plumbing) selects
the L3 mapping and description template; rows with no such core are deferred.
Descriptions embed literal argument values (e.g. buffer distance) where
verified, keeping the description grounded in source facts only.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import tempfile
from collections import Counter
from collections.abc import Iterable
from pathlib import Path
from typing import Any

SCHEMA = "qgis_train_only_v4_128_stable130_route1_v1"
SPECIAL_TOKENS = {"<START>": -3, "<END>": -4}
ADMISSION = "granted_train_only_route1_verified_v1"
STRUCTURAL = {"setgeometry", "setattributes", "setattribute", "addattributes"}

GROUPS: dict[str, dict[str, Any]] = {
    "buffer": {
        "l3_code": "L3_02_01_01", "token_id": 8,
        "operator": "pyqgis:buffer_features_keep_attributes",
        "task_name": "按距离缓冲要素并保留属性",
        "task_description": "从源图层读取要素，按指定距离创建缓冲区，复制源要素属性到输出要素。",
    },
    "centroid": {
        "l3_code": "L3_02_05_11", "token_id": 18,
        "operator": "pyqgis:centroid",
        "task_name": "提取要素质心并保留属性",
        "task_description": "从源图层读取要素，提取质心几何，复制源要素属性到输出要素。",
    },
    "difference": {
        "l3_code": "L3_02_02_04", "token_id": 11,
        "operator": "pyqgis:erase_features_keep_attributes",
        "task_name": "擦除要素重叠部分并保留属性",
        "task_description": "移除要素与擦除要素重叠的部分，复制源要素属性到输出要素。",
    },
    "frompointxy": {
        "l3_code": "L3_01_01_05", "token_id": 125,
        "operator": "pyqgis:create_point_features_from_coordinates",
        "task_name": "从坐标创建点要素",
        "task_description": "从坐标构造点几何，写入输出要素。",
    },
    "frompolylinexy": {
        "l3_code": "L3_01_01_06", "token_id": 126,
        "operator": "pyqgis:create_polyline_features_from_vertices",
        "task_name": "从顶点创建折线要素",
        "task_description": "从顶点序列构造折线几何，写入输出要素。",
    },
    "fromwkt": {
        "l3_code": "L3_01_01_07", "token_id": 127,
        "operator": "pyqgis:create_features_from_wkt",
        "task_name": "从 WKT 创建要素",
        "task_description": "从 WKT 文本构造几何，写入输出要素。",
    },
    "frompolygonxy": {
        "l3_code": "L3_01_01_08", "token_id": 128,
        "operator": "pyqgis:create_polygon_features_from_vertices",
        "task_name": "从顶点创建多边形要素",
        "task_description": "从顶点序列构造多边形几何，写入输出要素。",
    },
    "addattributes": {
        "l3_code": "L3_01_02_01", "token_id": 1,
        "operator": "pyqgis:add_fields_and_write_features",
        "task_name": "为矢量图层添加字段并写入要素",
        "task_description": "为矢量图层添加字段，提交字段结构更新并写入要素。",
    },
    "changeattributevalue": {
        "l3_code": "L3_01_02_06", "token_id": 4,
        "operator": "pyqgis:set_field_value",
        "task_name": "修改要素字段值",
        "task_description": "修改要素指定字段的值，写入输出要素。",
    },
    "intersection": {
        "l3_code": "L3_02_02_01", "token_id": 9,
        "operator": "pyqgis:intersection",
        "task_name": "计算要素相交部分并保留属性",
        "task_description": "计算要素与另一图层的相交部分，复制源要素属性到输出要素。",
    },
    "unaryunion": {
        "l3_code": "L3_02_02_02", "token_id": 10,
        "operator": "pyqgis:unary_union",
        "task_name": "合并要素几何并保留属性",
        "task_description": "合并要素几何，复制源要素属性到输出要素。",
    },
    "pointonsurface": {
        "l3_code": "L3_02_05_11", "token_id": 18,
        "operator": "pyqgis:point_on_surface",
        "task_name": "提取要素面上点并保留属性",
        "task_description": "提取要素面上的点几何，复制源要素属性到输出要素。",
    },
}


def _json_key(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _pair_key(row: dict[str, Any]) -> str:
    codes = row.get("l3_code_sequence") or [
        code for code in row.get("l3_codes", []) if code not in {"<START>", "<END>"}
    ]
    return _json_key(
        {"task_description": str(row.get("task_description") or "").strip(), "l3_code_sequence": codes}
    )


def _main_core(row: dict[str, Any]) -> dict[str, Any] | None:
    for op in row.get("verified_core_operations") or []:
        if op.get("method") not in STRUCTURAL:
            return op
    return None


def _describe(group: dict[str, Any], core: dict[str, Any]) -> tuple[str, str]:
    name = group["task_name"]
    description = group["task_description"]
    literal_args = [
        str(value.get("value"))
        for value in core.get("key_arguments", {}).values()
        if value.get("kind") == "literal"
    ]
    if literal_args:
        description = f"{description}（参数值：{'、'.join(literal_args[:4])}）"
    return name, description


def build_candidates(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    for row in rows:
        reasons: list[str] = []
        if row.get("llm_status") != "verified":
            reasons.append("pilot_not_verified")
        core = _main_core(row)
        if core is None:
            reasons.append("no_core_operation_beyond_structural_steps")
        group = GROUPS.get((core or {}).get("method", ""))
        if group is None:
            reasons.append(f"core_method_not_mapped:{(core or {}).get('method')}")
        source_span = row.get("source_span") or [
            int(row.get("scope_line_start") or 0),
            int(row.get("scope_line_end") or 0),
        ]
        if not isinstance(source_span, list) or len(source_span) != 2 or source_span[0] < 1:
            reasons.append("source_span_invalid")
        candidate_id = hashlib.sha256(
            _json_key(
                {
                    "source_sha256": row.get("source_sha256"),
                    "core_method": (core or {}).get("method"),
                    "core_line": (core or {}).get("line"),
                    "source": "route1_pilot_v3",
                }
            ).encode()
        ).hexdigest()
        passed = not reasons
        task_name, task_description = _describe(group, core) if passed and group and core else ("", "")
        candidates.append(
            {
                **row,
                "schema": "gis_recommend.qgis_api_route1_candidate.v1",
                "candidate_id": candidate_id,
                "operator_sequence": [group["operator"]] if passed and group else [],
                "candidate_l3_sequence": [group["l3_code"]] if passed and group else [],
                "task_name": task_name,
                "task_description": task_description,
                "core_operation": core,
                "parameter_facts": {
                    "core_method": (core or {}).get("method"),
                    "core_line": (core or {}).get("line"),
                    "key_arguments": (core or {}).get("key_arguments", {}),
                },
                "workflow_scope": "source_verified_llm_candidate_ast_verified",
                "whole_function_semantics_admission": "not_granted",
                "dependency_edges": [],
                "known_omissions": [
                    "whole_function_task_semantics_not_claimed",
                    "llm_candidate_ast_verified_only",
                    "runtime_values_not_invented",
                ],
                "description_source": "route1_ast_verified_facts_only",
                "description_fidelity": "passed" if passed else "deferred",
                "description_fidelity_passed": passed,
                "description_fidelity_reasons": reasons,
                "llm_called": True,
                "training_admission": "not_granted_pending_four_layer_dedup" if passed else "not_granted_description_fidelity_failed",
                "training_row_emitted": False,
                "validation_eligible": False,
                "test_eligible": False,
                "production_merge": "not_granted",
            }
        )
    return candidates


def build_four_layer_dedup(candidates: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    canonical_by_pair: dict[str, dict[str, Any]] = {}
    ledger: list[dict[str, Any]] = []
    for row in sorted(
        (row for row in candidates if row["description_fidelity_passed"]),
        key=lambda row: str(row["candidate_id"]),
    ):
        source_region_key = _json_key(
            {"source_sha256": row.get("source_sha256"), "source_span": row.get("source_span")}
        )
        call_graph_key = _json_key(
            {
                "source_sha256": row.get("source_sha256"),
                "core_line": (row.get("core_operation") or {}).get("line"),
                "sink_line": row.get("sink_line"),
            }
        )
        normalized_dag_key = _json_key(
            {
                "operators": row["operator_sequence"],
                "l3_sequence": row["candidate_l3_sequence"],
                "core_method": (row.get("core_operation") or {}).get("method"),
                "task_boundary": "route1_ast_verified_task_components",
            }
        )
        task_text_key = _json_key(row["task_description"])
        training_pair_key = _pair_key(row)
        original = canonical_by_pair.get(training_pair_key)
        decision = "canonical_keep" if original is None else "exact_training_pair_suppressed"
        if original is None:
            canonical_by_pair[training_pair_key] = row
        ledger.append(
            {
                **row,
                "schema": "gis_recommend.qgis_api_route1_dedup_ledger.v1",
                "source_region_key": source_region_key,
                "call_graph_key": call_graph_key,
                "normalized_dag_key": normalized_dag_key,
                "task_text_key": task_text_key,
                "training_pair_key": training_pair_key,
                "dedup_decision": decision,
                "canonical_candidate_id": row["candidate_id"] if original is None else original["candidate_id"],
            }
        )
    canonical = [row for row in ledger if row["dedup_decision"] == "canonical_keep"]
    return ledger, {
        "description_fidelity_passed": len(ledger),
        "description_fidelity_deferred": len(candidates) - len(ledger),
        "canonical_rows": len(canonical),
        "suppressed_exact_training_pairs": len(ledger) - len(canonical),
        "unique_source_authorities": len({row.get("source_authority_key") for row in ledger}),
        "unique_task_texts": len({row["task_text_key"] for row in ledger}),
        "core_method_counts": dict(
            sorted(Counter((row.get("core_operation") or {}).get("method") for row in ledger).items())
        ),
    }


def export_train_only(
    canonical: list[dict[str, Any]],
    existing_rows: list[dict[str, Any]],
    code_to_id: dict[str, int],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    for group in GROUPS.values():
        if int(code_to_id.get(group["l3_code"], -1)) != group["token_id"]:
            raise ValueError(f"stable130 {group['l3_code']} token contract mismatch")
    existing_pairs = {_pair_key(row) for row in existing_rows}
    exported: list[dict[str, Any]] = []
    cross_pool: list[dict[str, Any]] = []
    for row in canonical:
        group = GROUPS[(row.get("core_operation") or {}).get("method")]
        pair = _pair_key(row)
        decision = "existing_training_pair_suppressed" if pair in existing_pairs else "canonical_keep"
        cross_pool.append(
            {"candidate_id": row["candidate_id"], "training_pair_key": pair, "cross_pool_decision": decision}
        )
        if decision != "canonical_keep":
            continue
        exported.append(
            {
                "schema_version": SCHEMA,
                "sample_id": f"qgis_api_route1_{row['candidate_id']}_train_v1",
                "record_id": row.get("record_id"),
                "candidate_id": row["candidate_id"],
                "source_root_id": row.get("source_root_id") or "unknown",
                "source_path": row["source_path"],
                "source_sha256": row["source_sha256"],
                "source_authority_key": row.get("source_authority_key") or "",
                "source_authority_basis": "normalized_source_body_sha256",
                "source_verification": "verified_sha256",
                "call_span_verification": "route1_llm_candidate_ast_verified",
                "source_span": row.get("source_span"),
                "evidence_snippet": row.get("evidence_snippet") or "",
                "operator_sequence": [group["operator"]],
                "qgis_operator_chain": [group["operator"]],
                "chain": [group["operator"]],
                "l3_code_sequence": [group["l3_code"]],
                "l3_token_ids": [group["token_id"]],
                "l3_sequence": [SPECIAL_TOKENS["<START>"], group["token_id"], SPECIAL_TOKENS["<END>"]],
                "l3_codes": ["<START>", group["l3_code"], "<END>"],
                "n": 1,
                "task_name": row["task_name"],
                "task_description": row["task_description"],
                "task_type": "QGIS可验证低层API局部宏任务",
                "task_metadata": {
                    "task_type": "QGIS可验证低层API局部宏任务",
                    "task_name": row["task_name"],
                    "task_description": row["task_description"],
                },
                "workflow_scope": "source_verified_llm_candidate_ast_verified",
                "whole_function_semantics_admission": "not_granted",
                "dependency_edges": [],
                "parameter_facts": row["parameter_facts"],
                "core_operation": row["core_operation"],
                "known_omissions": row["known_omissions"],
                "source_region_key": row["source_region_key"],
                "call_graph_key": row["call_graph_key"],
                "normalized_dag_key": row["normalized_dag_key"],
                "cluster_id": pair,
                "source": "qgis_api_route1_llm_candidate_ast_verified_v1",
                "_training_quality": {"tier": "llm_candidate_ast_verified_deterministic", "sample_weight": 0.7},
                "taxonomy_profile": "stable130_authority_v1",
                "training_admission": ADMISSION,
                "split": "train",
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
        "core_method_counts": dict(
            sorted(Counter((row.get("core_operation") or {}).get("method") for row in exported).items())
        ),
    }


def _read_json(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    with path.open(encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", newline="", dir=path.parent, delete=False) as handle:
        json.dump(value, handle, ensure_ascii=False, indent=2, sort_keys=True)
        handle.write("\n")
        temporary = Path(handle.name)
    temporary.replace(path)


def _write_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", newline="", dir=path.parent, delete=False) as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
        temporary = Path(handle.name)
    temporary.replace(path)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--verified", type=Path, required=True)
    parser.add_argument("--verified-enrich", type=Path, required=True)
    parser.add_argument("--taxonomy", type=Path, required=True)
    parser.add_argument("--existing-pool", type=Path, action="append", default=[])
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    if args.output_dir.exists() and any(args.output_dir.iterdir()):
        raise ValueError(f"output directory is not empty: {args.output_dir}")
    taxonomy = _read_json(args.taxonomy)
    code_to_id = {
        str(class_row["l3_code"]): int(class_row["token_id"])
        for class_row in taxonomy["classes"]
    }
    verified_rows = _read_jsonl(args.verified)
    enrichment = {
        str(row.get("source_sha256") or ""): row
        for row in _read_jsonl(args.verified_enrich)
    }
    for row in verified_rows:
        extra = enrichment.get(str(row.get("source_sha256") or "")) or {}
        row.update({k: v for k, v in extra.items() if v})
    candidates = build_candidates(verified_rows)
    ledger, dedup_summary = build_four_layer_dedup(candidates)
    canonical = [row for row in ledger if row["dedup_decision"] == "canonical_keep"]
    existing = [row for path in args.existing_pool for row in _read_jsonl(path)]
    exported, cross_pool, export_summary = export_train_only(canonical, existing, code_to_id)
    summary = {
        "schema": "gis_recommend.qgis_api_route1_train_only_summary.v1",
        "input_verified_rows": len(candidates),
        "dedup": dedup_summary,
        "export": export_summary,
        "taxonomy_profile": "stable130_authority_v1",
        "llm_called": True,
        "training_run": False,
        "validation_eligible": False,
        "test_eligible": False,
        "production_merge": "not_granted",
    }
    outputs: dict[str, Any] = {
        "description_mapped_candidates_v1.jsonl": candidates,
        "four_layer_dedup_ledger_v1.jsonl": ledger,
        "canonical_candidates_v1.jsonl": canonical,
        "cross_pool_dedup_ledger_v1.jsonl": cross_pool,
        "qgis_api_route1_train_only_v1.jsonl": exported,
        "summary_v1.json": summary,
    }
    paths: list[Path] = []
    for name, value in outputs.items():
        path = args.output_dir / name
        (_write_jsonl if name.endswith(".jsonl") else _write_json)(path, value)
        paths.append(path)
    _write_json(
        args.output_dir / "hash_ledger_v1.json",
        {
            "schema": "gis_recommend.hash_ledger.v1",
            "inputs": {
                str(index): {"path": str(path), "sha256": _sha256(path)}
                for index, path in enumerate([args.verified, args.verified_enrich, args.taxonomy, *args.existing_pool])
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
