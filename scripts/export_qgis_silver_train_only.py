#!/usr/bin/env python3
"""Export the bounded, source-verified Silver workflow pilot.

Silver is train-only candidate data. It is never promoted to Gold authority or
benchmark data by this script.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

SCHEMA = "gis_recommend.qgis_silver_train_only.v1"
START_TOKEN, END_TOKEN = -3, -4


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def export(rows: list[dict[str, Any]], code_to_id: dict[str, int]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    selected = [row for row in rows if row.get("quality_class") == "silver" and row.get("admission_status") == "silver_candidate"]
    output: list[dict[str, Any]] = []
    for row in selected:
        operators = [str(value) for value in row.get("operator_sequence") or row.get("operator_ids") or []]
        l3_codes = [str(value) for value in row.get("l3_code_sequence") or row.get("mapped_l3_chain") or []]
        if not operators or len(operators) != len(l3_codes):
            raise ValueError(f"operator/L3 alignment failure: {row.get('record_id')}")
        token_ids = [code_to_id[code] for code in l3_codes]
        record_id = str(row["record_id"])
        source_path = str(row.get("source_path") or "")
        output.append(
            {
                "schema_version": SCHEMA,
                "sample_id": f"qgis_silver_{record_id}_train_v1",
                "record_id": record_id,
                "candidate_id": record_id,
                "source_root_id": row.get("source_root_id") or "unknown",
                "source_path": source_path,
                "source_sha256": row["source_sha256"],
                "source_verification": "verified_sha256",
                "source_authority_basis": "source_sha256",
                "source_span": {"call_sites": row.get("call_sites") or []},
                "evidence_snippet": row.get("source_snippet") or "",
                "operator_sequence": operators,
                "qgis_operator_chain": operators,
                "chain": operators,
                "l3_code_sequence": l3_codes,
                "l3_codes": ["<START>", *l3_codes, "<END>"],
                "l3_token_ids": token_ids,
                "l3_sequence": [START_TOKEN, *token_ids, END_TOKEN],
                "n": len(operators),
                "task_name": row.get("task_name") or "QGIS Processing 工作流",
                "task_description": row.get("task_description") or "",
                "task_type": "QGIS Silver Processing 工作流",
                "task_metadata": {
                    "task_name": row.get("task_name") or "QGIS Processing 工作流",
                    "task_description": row.get("task_description") or "",
                    "task_type": "QGIS Silver Processing 工作流",
                },
                "workflow_scope": row.get("workflow_unit_scope") or "whole_processing_scope",
                "dependency_edges": row.get("dependency_edges") or [],
                "parameter_facts": row.get("parameter_facts") or [],
                "source_region_key": row.get("source_region_key") or "",
                "call_graph_key": row.get("call_graph_key") or "",
                "normalized_dag_key": row.get("normalized_dag_key") or "",
                "training_pair_key": row.get("training_pair_key") or "",
                "taxonomy_profile": "stable124_authority_v1",
                "mapping_authority": "stable124_composed_v1",
                "_training_quality": {
                    "tier": "source_verified_processing_silver",
                    "sample_weight": 0.7,
                    "gold_status": "not_granted",
                },
                "training_admission": "granted_train_only_qgis_silver_pilot_v1",
                "split": "train_only_qgis_silver_pilot_v1",
                "validation_eligible": False,
                "test_eligible": False,
                "production_merge": "not_granted",
                "gold_admission": "not_granted_independent_semantic_review_required",
                "llm_called": False,
                "training_row_emitted": True,
            }
        )
    return output, {
        "schema": f"{SCHEMA}.summary",
        "input_rows": len(rows),
        "silver_rows": len(output),
        "gold_rows": 0,
        "source_sha256_unique": len({row["source_sha256"] for row in output}),
        "training_rows_emitted": len(output),
        "training_admission": "granted_train_only_qgis_silver_pilot_v1",
        "gold_admission": "not_granted",
        "validation_eligible": False,
        "test_eligible": False,
        "production_merge": "not_granted",
        "training_run": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ledger", type=Path, required=True)
    parser.add_argument("--extension", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    extension = json.loads(args.extension.read_text(encoding="utf-8"))
    code_to_id = {**extension["existing_code_to_id"], **extension["proposed_code_to_id_additions"]}
    rows, summary = export(read_jsonl(args.ledger), code_to_id)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    package = args.output_dir / "qgis_silver_train_only_v1.jsonl"
    summary_path = args.output_dir / "summary_v1.json"
    package.write_text("".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows), encoding="utf-8")
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (args.output_dir / "hash_ledger_v1.json").write_text(json.dumps({"inputs": {args.ledger.name: sha256(args.ledger), args.extension.name: sha256(args.extension)}, "artifacts": {package.name: sha256(package), summary_path.name: sha256(summary_path)}}, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
