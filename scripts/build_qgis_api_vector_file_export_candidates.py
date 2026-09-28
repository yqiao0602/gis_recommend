#!/usr/bin/env python3
"""Build source-fact vector export descriptions and four-layer dedup evidence."""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import tempfile
from collections import Counter
from pathlib import Path
from typing import Any

COMPLETE = "verified_complete_vector_file_export"
L3_CODE = "L3_07_04_01"
RULE_ID = "vector-file-export-local-macro-description-v1"
KNOWN_FORMATS = {
    "CSV",
    "ESRI Shapefile",
    "FlatGeobuf",
    "GeoJSON",
    "GPKG",
    "KML",
    "SQLite",
    "XLSX",
}


def _json_key(value: Any) -> str:
    encoded = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _normalize_text(value: Any) -> str:
    return "".join(str(value or "").lower().split())


def _literal(expression: Any) -> Any:
    if not isinstance(expression, str) or not expression:
        return None
    try:
        return ast.literal_eval(expression)
    except (SyntaxError, ValueError):
        return None


def _source_span(row: dict[str, Any], evidence: dict[str, Any]) -> dict[str, Any]:
    region = str(row.get("source_region") or "")
    try:
        span = region.rsplit(":", 1)[1]
        start_text, end_text = span.split("-", 1)
        start = int(start_text)
        end = int(end_text)
    except (IndexError, ValueError):
        start = int(evidence.get("writer_line_start") or 0)
        end = int(evidence.get("writer_line_end") or start)
    return {"segments": [{"line_start": start, "line_end": end}]}


def _description_facts(evidence: dict[str, Any]) -> tuple[str, str, dict[str, Any]]:
    writer_format = str(evidence.get("writer_format") or "dynamic_vector_format")
    only_selected = evidence.get("only_selected_features")
    options = {
        str(key).lower(): str(value)
        for key, value in (evidence.get("option_assignments") or {}).items()
    }
    layer_name = _literal(options.get("layername"))
    if not isinstance(layer_name, str) or not layer_name.strip() or len(layer_name) > 80:
        layer_name = None
    create_index = _literal(options.get("createspatialindex"))
    action = options.get("actiononexistingfile", "").lower()

    if writer_format in KNOWN_FORMATS:
        target = f"{writer_format}数据集"
        task_name = (
            f"保存选中的矢量要素为 {writer_format}"
            if only_selected is True
            else f"保存矢量图层为 {writer_format}"
        )
    else:
        target = "目标矢量数据集"
        task_name = (
            "保存选中的矢量要素到目标数据集"
            if only_selected is True
            else "保存矢量图层到目标数据集"
        )

    if only_selected is True:
        description = f"将已准备矢量图层中选中的要素写入{target}"
    elif only_selected is False:
        description = f"将已准备矢量图层的全部要素写入{target}"
    else:
        description = f"将已准备的矢量图层写入{target}"
    if layer_name:
        description += f"，目标图层名为“{layer_name.strip()}”"
    if "createoroverwrite" in action:
        description += "，并按源码指定策略覆盖已有目标"
    if create_index is True:
        description += "，同时创建空间索引"
    elif create_index is False:
        description += "，且不创建空间索引"
    description += "。"
    return task_name, description, {
        "writer_method": str(evidence.get("writer_method") or ""),
        "writer_format": writer_format,
        "only_selected_features": only_selected,
        "layer_name": layer_name,
        "overwrite_existing": "createoroverwrite" in action,
        "create_spatial_index": create_index if isinstance(create_index, bool) else None,
        "input_layer_expression": str(evidence.get("input_layer_expression") or ""),
        "output_path_expression": str(evidence.get("output_path_expression") or ""),
        "option_assignments": options,
    }


def build_candidate(row: dict[str, Any]) -> dict[str, Any]:
    reasons: list[str] = []
    if row.get("source_replay_status") != COMPLETE:
        reasons.append("source_replay_not_complete")
    if row.get("source_replay_verification") != "verified_sha256":
        reasons.append("source_sha256_not_verified")
    if row.get("proposed_l3_code") != L3_CODE:
        reasons.append("stable125_l3_contract_mismatch")
    evidence_rows = list(row.get("writer_evidence") or [])
    if len(evidence_rows) != 1:
        reasons.append("requires_exactly_one_writer_evidence")
        evidence: dict[str, Any] = {}
    else:
        evidence = evidence_rows[0]
    if not evidence.get("input_layer_expression"):
        reasons.append("missing_input_layer_expression")
    if not evidence.get("output_path_expression"):
        reasons.append("missing_output_path_expression")
    if evidence.get("control_flow"):
        reasons.append("writer_under_control_flow")

    task_name, task_description, parameter_facts = _description_facts(evidence)
    source_span = _source_span(row, evidence)
    passed = not reasons
    candidate_id = _json_key(
        {
            "source_authority_key": row.get("source_authority_key"),
            "source_region": row.get("source_region"),
            "rule_id": RULE_ID,
        }
    )
    return {
        **row,
        "schema": "gis_recommend.qgis_api_vector_file_export_candidate.v1",
        "candidate_id": candidate_id,
        "description_rule_id": RULE_ID,
        "semantic_calls": ["save_vector_features_to_file"],
        "semantic_call_sites": [
            {
                "name": "pyqgis:save_vector_features_to_file",
                "line_start": int(evidence.get("writer_line_start") or 0),
                "line_end": int(evidence.get("writer_line_end") or 0),
                "arguments": [],
            }
        ],
        "candidate_l3_sequence": [L3_CODE],
        "dependency_edges": [[0, 1]],
        "source_span": source_span,
        "source_snippet": row.get("source_replay_snippet") or "",
        "task_name": task_name if passed else "",
        "task_description": task_description if passed else "",
        "parameter_facts": parameter_facts,
        "workflow_scope": "source_verified_local_api_macro",
        "whole_function_semantics_admission": "not_granted",
        "known_omissions": [
            "upstream_layer_preparation_outside_local_writer_boundary",
            "whole_function_task_semantics_not_claimed",
            "dynamic_output_path_value_not_claimed",
        ],
        "description_source": "source_verified_local_writer_facts_only",
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
                "writer_evidence": candidate.get("writer_evidence"),
                "dependency_edges": candidate.get("dependency_edges"),
            }
        )
        normalized_dag_key = _json_key(
            {
                "semantic_calls": candidate.get("semantic_calls"),
                "l3_sequence": candidate.get("candidate_l3_sequence"),
                "writer_method": candidate["parameter_facts"].get("writer_method"),
                "writer_format": candidate["parameter_facts"].get("writer_format"),
                "only_selected_features": candidate["parameter_facts"].get(
                    "only_selected_features"
                ),
                "overwrite_existing": candidate["parameter_facts"].get(
                    "overwrite_existing"
                ),
                "create_spatial_index": candidate["parameter_facts"].get(
                    "create_spatial_index"
                ),
                "task_boundary": "local_vector_file_writer_macro",
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
                "schema": "gis_recommend.qgis_api_vector_file_export_dedup_ledger.v1",
                "source_region_key": source_region_key,
                "call_graph_key": call_graph_key,
                "normalized_dag_key": normalized_dag_key,
                "task_text_key": task_text_key,
                "training_pair_key": training_pair_key,
                "dedup_decision": decision,
                "canonical_candidate_id": (
                    candidate["candidate_id"] if canonical is None else canonical["candidate_id"]
                ),
                "dedup_reason": (
                    "unique source-fact task-text and L3 pair"
                    if canonical is None
                    else "normalized task name/text and L3 chain are identical"
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
        "schema": "gis_recommend.qgis_api_vector_file_export_dedup_summary.v1",
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
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--expected-verified-rows", type=int, required=True)
    args = parser.parse_args()
    if args.output_dir.exists() and any(args.output_dir.iterdir()):
        raise ValueError(f"output directory is not empty: {args.output_dir}")
    replay_rows = _read_jsonl(args.source_replay)
    verified = [row for row in replay_rows if row.get("source_replay_status") == COMPLETE]
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
