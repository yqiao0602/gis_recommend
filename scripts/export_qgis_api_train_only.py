#!/usr/bin/env python3
"""Cross-pool deduplicate and export QGIS API-pattern train-only rows."""

from __future__ import annotations

import argparse
import hashlib
import json
import tempfile
from pathlib import Path
from typing import Any


SPECIAL_TOKENS = {"<START>": -3, "<END>": -4}


def _normalize_text(value: Any) -> str:
    return "".join(str(value or "").lower().split())


def _pair_key(row: dict[str, Any]) -> str:
    value = {
        "task_name": _normalize_text(row.get("task_name")),
        "task_description": _normalize_text(row.get("task_description")),
        "l3_sequence": row.get("candidate_l3_sequence")
        or row.get("l3_code_sequence")
        or [],
    }
    encoded = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _operator(method_call: str) -> str:
    method = method_call.rsplit(".", 1)[-1].lower()
    prefix = "pyqgis-pattern" if method == "random_point_sampling" else "pyqgis"
    return f"{prefix}:{method}"


def export_train_only(
    candidates: list[dict[str, Any]],
    existing_rows: list[dict[str, Any]],
    code_to_id: dict[str, int],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    existing_pairs = {_pair_key(row) for row in existing_rows}
    exported: list[dict[str, Any]] = []
    ledger: list[dict[str, Any]] = []
    for candidate in candidates:
        if candidate.get("dedup_decision") != "canonical_keep":
            continue
        pair = _pair_key(candidate)
        decision = (
            "existing_training_pair_suppressed"
            if pair in existing_pairs
            else "canonical_keep"
        )
        ledger.append(
            {
                "candidate_id": candidate["candidate_id"],
                "training_pair_key": pair,
                "cross_pool_decision": decision,
                "training_admission": (
                    "not_granted_existing_training_pair_duplicate"
                    if decision != "canonical_keep"
                    else "granted_train_only_qgis_api_v1"
                ),
            }
        )
        if decision != "canonical_keep":
            continue
        l3_codes = [str(value) for value in candidate["candidate_l3_sequence"]]
        try:
            token_ids = [int(code_to_id[code]) for code in l3_codes]
        except KeyError as error:
            raise ValueError(f"L3 code missing from stable110: {error}") from error
        operators = [_operator(call) for call in candidate["semantic_calls"]]
        if len(operators) != len(l3_codes):
            raise ValueError("API semantic call/L3 sequence length mismatch")
        composite_pattern = any(
            operator.startswith("pyqgis-pattern:") for operator in operators
        )
        task_type = (
            "QGIS可验证低层API复合任务"
            if composite_pattern
            else "QGIS可验证低层API几何任务"
        )
        exported.append(
            {
                "schema_version": "qgis_api_training_sample_v1",
                "sample_id": f"qgis_api_{candidate['candidate_id']}_train_v1",
                "record_id": candidate["record_id"],
                "candidate_id": candidate["candidate_id"],
                "source_root_id": candidate["source_root_id"],
                "source_path": candidate["source_path"],
                "source_sha256": candidate["source_sha256"],
                "source_authority_key": candidate["source_authority_key"],
                "source_authority_basis": "normalized_source_body_sha256",
                "source_verification": "verified_sha256",
                "call_span_verification": (
                    "verified_composite_api_pattern"
                    if composite_pattern
                    else "verified_api_calls"
                ),
                "source_span": {
                    "segments": [
                        {
                            "line_start": int(site["line_start"]),
                            "line_end": int(site["line_end"]),
                        }
                        for site in candidate["semantic_call_sites"]
                    ]
                },
                "evidence_snippet": candidate["source_snippet"],
                "operator_sequence": operators,
                "api_pattern_sequence": (
                    list(candidate["semantic_calls"]) if composite_pattern else []
                ),
                "qgis_operator_chain": operators,
                "chain": operators,
                "l3_code_sequence": l3_codes,
                "l3_token_ids": token_ids,
                "l3_sequence": [SPECIAL_TOKENS["<START>"], *token_ids, SPECIAL_TOKENS["<END>"]],
                "l3_codes": ["<START>", *l3_codes, "<END>"],
                "n": len(operators),
                "task_name": candidate["task_name"],
                "task_description": candidate["task_description"],
                "task_type": task_type,
                "task_metadata": {
                    "task_type": task_type,
                    "task_name": candidate["task_name"],
                    "task_description": candidate["task_description"],
                },
                "workflow_scope": (
                    "source_verified_low_level_api_composite_task"
                    if composite_pattern
                    else "source_verified_low_level_api_task"
                ),
                "dependency_edges": candidate["dependency_edges"],
                "parameter_facts": candidate.get("parameter_facts") or {},
                "known_omissions": ["supporting_feature_mutation_and_sink_calls_not_targets"],
                "source_region_key": candidate["source_region_key"],
                "call_graph_key": candidate["call_graph_key"],
                "normalized_dag_key": candidate["normalized_dag_key"],
                "cluster_id": pair,
                "source": "qgis_api_source_verified_semantic_v1",
                "_training_quality": {
                    "tier": (
                        "source_verified_api_pattern_deterministic"
                        if composite_pattern
                        else "source_verified_api_deterministic"
                    ),
                    "sample_weight": 0.7,
                },
                "taxonomy_profile": "stable110_authority_v1",
                "training_admission": "granted_train_only_qgis_api_v1",
                "split": "train_only_qgis_api_v1",
                "validation_eligible": False,
                "test_eligible": False,
                "production_merge": "not_granted",
            }
        )
    summary = {
        "schema": "gis_recommend.qgis_api_train_only_export_summary.v1",
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
        "unique_l3_sequences": len(
            {tuple(row["l3_code_sequence"]) for row in exported}
        ),
        "training_admission": "granted_train_only_qgis_api_v1",
        "validation_eligible": False,
        "test_eligible": False,
        "production_merge": "not_granted",
        "training_run": False,
    }
    return exported, ledger, summary


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
    parser.add_argument("--canonical-candidates", type=Path, required=True)
    parser.add_argument("--existing-pool", type=Path, action="append", default=[])
    parser.add_argument("--stable110-extension", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    if args.output_dir.exists() and any(args.output_dir.iterdir()):
        raise ValueError(f"output directory is not empty: {args.output_dir}")

    candidates = _read_jsonl(args.canonical_candidates)
    existing_rows = [
        row for path in args.existing_pool for row in _read_jsonl(path)
    ]
    extension = _read_json(args.stable110_extension)
    code_to_id = {
        **extension["existing_code_to_id"],
        **extension["proposed_code_to_id_additions"],
    }
    exported, ledger, summary = export_train_only(candidates, existing_rows, code_to_id)
    outputs = {
        "qgis_api_train_only_v1.jsonl": exported,
        "cross_pool_dedup_ledger_v1.jsonl": ledger,
    }
    paths = []
    for name, rows in outputs.items():
        path = args.output_dir / name
        _write_jsonl(path, rows)
        paths.append(path)
    summary_path = args.output_dir / "summary_v1.json"
    _write_json(summary_path, summary)
    paths.append(summary_path)
    inputs = [args.canonical_candidates, *args.existing_pool, args.stable110_extension]
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
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
