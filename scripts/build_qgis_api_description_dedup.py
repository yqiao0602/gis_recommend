#!/usr/bin/env python3
"""Build deterministic QGIS API descriptions and a four-layer dedup ledger."""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import tempfile
from collections import Counter
from pathlib import Path
from typing import Any


SEMANTICS = {
    "buffer": {
        "l3": "L3_02_01_01",
        "name": "创建几何缓冲区",
        "description": "为输入几何创建指定距离的缓冲区，并将缓冲结果写入输出要素。",
    },
    "intersection": {
        "l3": "L3_02_02_01",
        "name": "计算几何相交部分",
        "description": "计算输入几何与另一几何的相交部分，并将相交结果写入输出要素。",
    },
    "simplify": {
        "l3": "L3_02_05_01",
        "name": "简化要素几何",
        "description": "按指定容差简化输入要素的几何，并将简化结果写入输出要素。",
    },
    "centroid": {
        "l3": "L3_02_05_11",
        "name": "提取要素质心",
        "description": "计算输入要素几何的质心，并将质心几何写入输出要素。",
    },
    "convexHull": {
        "l3": "L3_02_05_12",
        "name": "创建凸包几何",
        "description": "计算输入几何的最小凸包，并将凸包几何写入输出要素。",
    },
    "random_point_sampling": {
        "l3": "L3_02_06_06",
        "name": "在目标几何内随机采样点",
        "description": "在目标几何内随机采样满足最小距离约束的点，并写入输出点图层。",
    },
}
RANDOM_POINT_SCOPE_TEXT = {
    "RandomPointsLayer.processAlgorithm": {
        "name": "在输入图层内随机采样点",
        "description": "在输入图层覆盖范围内随机生成指定数量的候选点，仅保留位于要素几何内部且满足最小距离约束的点，并写入输出点图层。",
    },
    "RandomPointsPolygonsFixed.processAlgorithm": {
        "name": "为每个多边形固定数量采样点",
        "description": "为输入图层中的每个多边形随机生成固定数量的点，仅保留位于对应多边形内部且满足最小距离约束的点，并写入输出点图层。",
    },
    "RandomPointsPolygonsVariable.processAlgorithm": {
        "name": "按多边形属性随机采样点",
        "description": "根据每个多边形的属性值确定采样数量，在对应多边形内部随机生成满足最小距离约束的点，并写入输出点图层。",
    },
    "RandomPointsPolygons.processAlgorithm": {
        "name": "按数量或密度在多边形内采样点",
        "description": "按指定数量或面积密度确定每个多边形的采样点数，在对应多边形内部随机生成满足最小距离约束的点，并写入输出点图层。",
    },
    "PointSample.addSamplePoints": {
        "name": "在分层目标几何内随机采样点",
        "description": "在目标分层几何内部随机生成指定数量且满足最小距离约束的采样点，并将采样点及其分层标识写入输出图层。",
    },
}


def _method(call_name: str) -> str:
    return call_name.rsplit(".", 1)[-1]


def _json_key(value: Any) -> str:
    encoded = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _normalize_text(value: Any) -> str:
    return "".join(str(value or "").lower().split())


def _literal(argument: str) -> Any | None:
    try:
        value = ast.literal_eval(argument)
    except (SyntaxError, ValueError):
        return None
    if isinstance(value, (bool, int, float, str)):
        return value
    return None


def build_description_candidate(row: dict[str, Any]) -> dict[str, Any]:
    reasons: list[str] = []
    calls = [str(value) for value in row.get("semantic_calls") or []]
    methods = [_method(call) for call in calls]
    l3_sequence = [str(value) for value in row.get("candidate_l3_sequence") or []]
    if row.get("source_replay_status") != "verified":
        reasons.append("source_replay_not_verified")
    if len(methods) != 1:
        reasons.append("description_rule_requires_single_semantic_call")
    semantic = SEMANTICS.get(methods[0]) if len(methods) == 1 else None
    if semantic is None and len(methods) == 1:
        reasons.append("unsupported_description_semantic")
    elif l3_sequence != [semantic["l3"]]:
        reasons.append("semantic_l3_contract_mismatch")
    if methods == ["random_point_sampling"]:
        scoped_semantic = RANDOM_POINT_SCOPE_TEXT.get(
            str(row.get("lexical_scope") or "")
        )
        if scoped_semantic is None:
            reasons.append("unsupported_random_point_lexical_scope")
        else:
            semantic = {"l3": "L3_02_06_06", **scoped_semantic}

    sites = list(row.get("semantic_call_sites") or [])
    if len(sites) != len(calls):
        reasons.append("semantic_call_site_coverage_mismatch")
    arguments = [str(value) for value in (sites[0].get("arguments") or [])] if sites else []
    literal_arguments = [_literal(argument) for argument in arguments]
    if methods == ["buffer"] and literal_arguments and literal_arguments[0] == 0:
        reasons.append("zero_distance_buffer_not_a_buffer_task")

    task_name = str(semantic["name"]) if semantic else ""
    task_description = str(semantic["description"]) if semantic else ""
    parameter_facts: dict[str, Any] = {}
    if semantic and literal_arguments:
        first = literal_arguments[0]
        if isinstance(first, (int, float)) and first != 0:
            label = "缓冲距离" if methods == ["buffer"] else "简化容差"
            if methods[0] in {"buffer", "simplify"}:
                parameter_facts[label] = first
                task_description = task_description[:-1] + f"，{label}为 {first}。"

    passed = not reasons
    return {
        **row,
        "schema": "gis_recommend.qgis_api_description_candidate.v1",
        "task_name": task_name if passed else "",
        "task_description": task_description if passed else "",
        "parameter_facts": parameter_facts,
        "description_source": "source_verified_semantic_rule_only",
        "description_fidelity": "passed" if passed else "deferred",
        "description_fidelity_passed": passed,
        "description_fidelity_reasons": reasons,
        "llm_called": False,
        "legacy_task_text_used": False,
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
    ledger: list[dict[str, Any]] = []
    canonical_by_pair: dict[str, dict[str, Any]] = {}
    for candidate in eligible:
        source_region_key = _json_key(
            {
                "source_sha256": candidate.get("source_sha256"),
                "source_span": candidate.get("source_span") or [],
            }
        )
        semantic_methods = [_method(str(call)) for call in candidate.get("semantic_calls") or []]
        call_graph_key = _json_key(
            {
                "source_sha256": candidate.get("source_sha256"),
                "semantic_methods": semantic_methods,
                "semantic_call_sites": candidate.get("semantic_call_sites") or [],
                "dependency_edges": candidate.get("dependency_edges") or [],
            }
        )
        normalized_dag_key = _json_key(
            {
                "semantic_methods": semantic_methods,
                "l3_sequence": candidate.get("candidate_l3_sequence") or [],
                "task_boundary": "semantic_transform_to_feature_output",
            }
        )
        task_text_key = _json_key(_normalize_text(candidate.get("task_description")))
        training_pair_key = _json_key(
            {
                "task_name": _normalize_text(candidate.get("task_name")),
                "task_description": _normalize_text(candidate.get("task_description")),
                "l3_sequence": candidate.get("candidate_l3_sequence") or [],
            }
        )
        row = {
            **candidate,
            "schema": "gis_recommend.qgis_api_four_layer_dedup_ledger.v1",
            "source_region_key": source_region_key,
            "call_graph_key": call_graph_key,
            "normalized_dag_key": normalized_dag_key,
            "task_text_key": task_text_key,
            "training_pair_key": training_pair_key,
            "dedup_decision": "canonical_keep",
            "canonical_candidate_id": candidate["candidate_id"],
            "dedup_reason": "unique exact task-text and L3 training pair",
            "training_admission": "not_granted_pending_train_only_export",
        }
        canonical = canonical_by_pair.get(training_pair_key)
        if canonical is None:
            canonical_by_pair[training_pair_key] = row
        else:
            row["dedup_decision"] = "exact_training_pair_suppressed"
            row["canonical_candidate_id"] = canonical["candidate_id"]
            row["dedup_reason"] = "normalized task name/text and L3 chain are identical"
            row["training_admission"] = "not_granted_exact_training_pair_duplicate"
        ledger.append(row)

    canonical = [row for row in ledger if row["dedup_decision"] == "canonical_keep"]
    summary = {
        "schema": "gis_recommend.qgis_api_description_dedup_summary.v1",
        "input_source_verified_proposals": len(candidates),
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
        "fidelity_defer_reason_counts": dict(
            sorted(
                Counter(
                    reason
                    for row in candidates
                    for reason in row.get("description_fidelity_reasons") or []
                ).items()
            )
        ),
        "llm_called": False,
        "training_admission": "not_granted_description_and_dedup_census_only",
        "training_rows_emitted": 0,
        "validation_eligible": False,
        "test_eligible": False,
        "production_merge": "not_granted",
    }
    return ledger, summary


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    with path.open(encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def _read_jsonls(paths: list[Path]) -> list[dict[str, Any]]:
    return [row for path in paths for row in _read_jsonl(path)]


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
    parser.add_argument(
        "--source-verified-proposals", type=Path, nargs="+", required=True
    )
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    if args.output_dir.exists() and any(args.output_dir.iterdir()):
        raise ValueError(f"output directory is not empty: {args.output_dir}")

    inputs = _read_jsonls(args.source_verified_proposals)
    candidates = [build_description_candidate(row) for row in inputs]
    ledger, summary = build_four_layer_dedup(candidates)
    canonical = [row for row in ledger if row["dedup_decision"] == "canonical_keep"]
    deferred = [row for row in candidates if not row["description_fidelity_passed"]]
    values = {
        "description_candidates_v1.jsonl": candidates,
        "description_fidelity_deferred_v1.jsonl": deferred,
        "four_layer_dedup_ledger_v1.jsonl": ledger,
        "canonical_candidates_v1.jsonl": canonical,
    }
    paths = []
    for name, rows in values.items():
        path = args.output_dir / name
        _write_jsonl(path, rows)
        paths.append(path)
    summary_path = args.output_dir / "summary_v1.json"
    _write_json(summary_path, summary)
    paths.append(summary_path)
    _write_json(
        args.output_dir / "hash_ledger_v1.json",
        {
            "schema": "gis_recommend.hash_ledger.v1",
            "inputs": {
                f"source_verified_proposals_{index:02d}": {
                    "path": str(path),
                    "sha256": _sha256(path),
                }
                for index, path in enumerate(args.source_verified_proposals)
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
