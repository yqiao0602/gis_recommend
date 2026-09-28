#!/usr/bin/env python3
"""Build deterministic local-macro descriptions and four-layer dedup evidence."""

from __future__ import annotations

import argparse
import hashlib
import json
import tempfile
from collections import Counter
from pathlib import Path
from typing import Any

L3_CODE = "L3_01_01_01"
RULE_ID = "create-feature-class-local-macro-description-v1"
GEOMETRY_LABELS = {
    "point": "点",
    "multipoint": "多点",
    "linestring": "线",
    "multilinestring": "多线",
    "polygon": "面",
    "multipolygon": "多面",
    "none": "无几何表",
    "dynamic": "指定几何类型的矢量",
}


def _json_key(value: Any) -> str:
    encoded = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _normalize_text(value: Any) -> str:
    return "".join(str(value or "").lower().split())


def _clean_field_names(values: list[Any]) -> list[str]:
    names = []
    for value in values:
        name = " ".join(str(value).split())
        if name and len(name) <= 80 and name not in names:
            names.append(name)
    return names[:12]


def build_candidate(row: dict[str, Any]) -> dict[str, Any]:
    reasons: list[str] = []
    if row.get("macro_source_replay_status") != "verified_complete_macro_alias_chain":
        reasons.append("macro_source_replay_not_verified")
    if int(row.get("complete_macro_chain_count") or 0) != 1:
        reasons.append("requires_exactly_one_complete_macro_chain")
    if row.get("proposed_l3_code") != L3_CODE:
        reasons.append("stable125_l3_contract_mismatch")
    evidence_rows = list(row.get("macro_chain_evidence") or [])
    if len(evidence_rows) != 1:
        reasons.append("macro_chain_evidence_count_mismatch")
        evidence: dict[str, Any] = {}
    else:
        evidence = evidence_rows[0]
    constructor_line = int(evidence.get("constructor_line") or 0)
    writer_lines = [int(value) for value in evidence.get("vector_writer_lines") or []]
    if constructor_line <= 0 or not writer_lines:
        reasons.append("macro_source_span_incomplete")

    geometry_type = str(evidence.get("geometry_type") or "dynamic").lower()
    geometry_label = GEOMETRY_LABELS.get(geometry_type, GEOMETRY_LABELS["dynamic"])
    field_names = _clean_field_names(list(evidence.get("field_names") or []))
    copies_schema = bool(evidence.get("schema_copies_input_fields"))
    populates = bool(evidence.get("populates_features"))
    writer_format = str(evidence.get("writer_format") or "dynamic_vector_format")

    if copies_schema:
        schema_text = "沿用已准备的输入字段结构"
    elif field_names:
        schema_text = "定义字段：" + "、".join(field_names)
    else:
        schema_text = "使用已准备的字段结构"
    population_text = "写入已准备的要素" if populates else "创建空要素类"
    output_text = (
        "矢量数据集" if writer_format == "dynamic_vector_format" else f"{writer_format} 数据"
    )
    task_name = f"创建{geometry_label}要素类"
    task_description = (
        f"创建新的{geometry_label}要素类，{schema_text}，{population_text}，并保存为{output_text}。"
    )
    passed = not reasons
    source_span = {
        "segments": [
            {
                "line_start": constructor_line,
                "line_end": max(writer_lines) if writer_lines else constructor_line,
            }
        ]
    }
    candidate_id = _json_key(
        {
            "source_authority_key": row.get("source_authority_key"),
            "layer_variable": evidence.get("layer_variable"),
            "source_span": source_span,
            "rule_id": RULE_ID,
        }
    )
    return {
        **row,
        "schema": "gis_recommend.qgis_api_create_feature_class_candidate.v1",
        "candidate_id": candidate_id,
        "description_rule_id": RULE_ID,
        "semantic_calls": ["create_feature_class"],
        "semantic_call_sites": [
            {
                "name": "pyqgis:create_feature_class",
                "line_start": constructor_line,
                "line_end": max(writer_lines) if writer_lines else constructor_line,
                "arguments": [],
            }
        ],
        "candidate_l3_sequence": [L3_CODE],
        "dependency_edges": [[0, 1], [1, 2], [2, 3]],
        "source_span": source_span,
        "source_snippet": row.get("macro_source_snippet") or "",
        "task_name": task_name if passed else "",
        "task_description": task_description if passed else "",
        "parameter_facts": {
            "geometry_type": geometry_type,
            "field_names": field_names,
            "schema_copies_input_fields": copies_schema,
            "populates_features": populates,
            "writer_format": writer_format,
        },
        "workflow_scope": "source_verified_local_api_macro",
        "whole_function_semantics_admission": "not_granted",
        "known_omissions": [
            "upstream_feature_or_schema_computation_outside_local_macro_boundary",
            "whole_function_task_semantics_not_claimed",
        ],
        "description_source": "source_verified_local_macro_facts_only",
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
                "macro_chain_evidence": candidate.get("macro_chain_evidence"),
                "dependency_edges": candidate.get("dependency_edges"),
            }
        )
        normalized_dag_key = _json_key(
            {
                "semantic_calls": candidate.get("semantic_calls"),
                "l3_sequence": candidate.get("candidate_l3_sequence"),
                "parameter_facts": candidate.get("parameter_facts"),
                "task_boundary": "local_create_feature_class_macro",
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
                "schema": "gis_recommend.qgis_api_create_feature_class_dedup_ledger.v1",
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
                "dedup_reason": (
                    "unique exact local-macro task-text and L3 pair"
                    if canonical is None
                    else "normalized local-macro task name/text and L3 chain are identical"
                ),
                "training_admission": (
                    "not_granted_pending_train_only_export"
                    if canonical is None
                    else "not_granted_exact_training_pair_duplicate"
                ),
            }
        )
    canonical_rows = [row for row in ledger if row["dedup_decision"] == "canonical_keep"]
    summary = {
        "schema": "gis_recommend.qgis_api_create_feature_class_dedup_summary.v1",
        "input_replay_rows": len(candidates),
        "description_fidelity_passed": len(eligible),
        "description_fidelity_deferred": len(candidates) - len(eligible),
        "canonical_rows": len(canonical_rows),
        "suppressed_exact_training_pairs": len(ledger) - len(canonical_rows),
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
        "whole_function_semantics_admission": "not_granted",
        "llm_called": False,
        "training_admission": "not_granted_description_and_dedup_only",
        "training_rows_emitted": 0,
        "validation_eligible": False,
        "test_eligible": False,
        "production_merge": "not_granted",
    }
    return ledger, summary


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
    _atomic_write(
        path,
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
    )


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    _atomic_write(
        path,
        "".join(
            json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows
        ),
    )


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-replay", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--expected-verified-rows", type=int, default=52)
    args = parser.parse_args()
    if args.output_dir.exists() and any(args.output_dir.iterdir()):
        raise ValueError(f"output directory is not empty: {args.output_dir}")
    replay_rows = _read_jsonl(args.source_replay)
    verified = [
        row
        for row in replay_rows
        if row.get("macro_source_replay_status")
        == "verified_complete_macro_alias_chain"
    ]
    if len(verified) != args.expected_verified_rows:
        raise ValueError(
            f"expected {args.expected_verified_rows} verified rows, got {len(verified)}"
        )
    candidates = [build_candidate(row) for row in verified]
    ledger, summary = build_four_layer_dedup(candidates)
    canonical = [row for row in ledger if row["dedup_decision"] == "canonical_keep"]
    outputs = {
        "description_candidates_v1.jsonl": candidates,
        "four_layer_dedup_ledger_v1.jsonl": ledger,
        "canonical_candidates_v1.jsonl": canonical,
    }
    paths: list[Path] = []
    for name, rows in outputs.items():
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
                args.source_replay.name: {
                    "path": str(args.source_replay),
                    "sha256": _sha256(args.source_replay),
                }
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
