#!/usr/bin/env python3
"""Freeze full-source review packets for the bounded QGIS Silver pilot.

This creates evidence for independent semantic review. It does not assign a
review decision, alter Silver training admission, or promote any row to Gold.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import tempfile
from collections.abc import Iterable
from pathlib import Path
from typing import Any

SCHEMA = "gis_recommend.qgis_silver_semantic_review_packet.v1"
SILVER_SCHEMA = "gis_recommend.qgis_silver_train_only.v1"
SILVER_ADMISSION = "granted_train_only_qgis_silver_pilot_v1"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def build_packet(rows: Iterable[dict[str, Any]]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    packet: list[dict[str, Any]] = []
    for row in rows:
        sample_id = str(row.get("sample_id") or "")
        source_path = Path(str(row.get("source_path") or ""))
        if row.get("schema_version") != SILVER_SCHEMA:
            raise ValueError(f"unexpected Silver schema: {sample_id}")
        if row.get("training_admission") != SILVER_ADMISSION:
            raise ValueError(f"unexpected Silver admission: {sample_id}")
        if not sample_id or not source_path.is_file():
            raise ValueError(f"missing review identity or source: {sample_id}")
        if sha256(source_path) != row.get("source_sha256"):
            raise ValueError(f"source SHA256 mismatch: {sample_id}")
        packet.append(
            {
                "schema": SCHEMA,
                "audit_id": f"qgis_silver_semantic_{sample_id}",
                "sample_id": sample_id,
                "record_id": row.get("record_id"),
                "source_path": str(source_path),
                "source_sha256": row["source_sha256"],
                "source_verification": "verified_sha256",
                "source_text": source_path.read_text(encoding="utf-8", errors="replace"),
                "source_span": row.get("source_span") or {},
                "operator_sequence": row.get("operator_sequence") or [],
                "l3_code_sequence": row.get("l3_code_sequence") or [],
                "l3_token_ids": row.get("l3_token_ids") or [],
                "dependency_edges": row.get("dependency_edges") or [],
                "parameter_facts": row.get("parameter_facts") or [],
                "task_name": row.get("task_name") or "",
                "original_task_description": row.get("original_task_description")
                or row.get("task_description")
                or "",
                "task_description": row.get("task_description") or "",
                "description_compaction_status": row.get("description_compaction_status")
                or "unchanged",
                "four_layer_keys": {
                    name: row.get(name) or ""
                    for name in (
                        "source_region_key",
                        "call_graph_key",
                        "normalized_dag_key",
                        "training_pair_key",
                    )
                },
                "review_contract": {
                    "question": "Does source intent support the task description and ordered operator/L3 chain?",
                    "allowed_decisions": ["gold", "retain_silver", "reject"],
                    "gold_requirements": [
                        "source_execution_logic_pass",
                        "task_source_intent_pass",
                        "operator_chain_pass",
                        "l3_alignment_pass",
                    ],
                    "hard_reject_conditions": [
                        "operator_chain_wrong_or_truncated",
                        "task_description_conflicts_with_source",
                        "l3_mapping_conflicts_with_operator",
                        "source_identity_failure",
                    ],
                },
                "source_execution_logic_verdict": "pending",
                "task_source_intent_verdict": "pending",
                "operator_chain_verdict": "pending",
                "l3_alignment_verdict": "pending",
                "semantic_review_decision": "pending",
                "semantic_review_notes": "",
                "gold_admission": "not_granted_independent_semantic_review_required",
                "training_admission": "unchanged_granted_train_only_qgis_silver_pilot_v1",
                "validation_eligible": False,
                "test_eligible": False,
                "production_merge": "not_granted",
            }
        )
    if len({row["sample_id"] for row in packet}) != len(packet):
        raise ValueError("duplicate Silver sample_id")
    return packet, {
        "schema": f"{SCHEMA}.summary",
        "input_rows": len(packet),
        "source_sha256_verified": len(packet),
        "pending_independent_reviews": len(packet),
        "gold_rows": 0,
        "silver_rows": len(packet),
        "reject_rows": 0,
        "training_rows_emitted": 0,
        "training_admission": "unchanged_granted_train_only_qgis_silver_pilot_v1",
        "production_merge": "not_granted",
    }


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "w", encoding="utf-8", newline="", dir=path.parent, delete=False
    ) as handle:
        json.dump(value, handle, ensure_ascii=False, indent=2, sort_keys=True)
        handle.write("\n")
        temporary = Path(handle.name)
    temporary.replace(path)


def write_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "w", encoding="utf-8", newline="", dir=path.parent, delete=False
    ) as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
        temporary = Path(handle.name)
    temporary.replace(path)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    if args.output_dir.exists() and any(args.output_dir.iterdir()):
        raise ValueError(f"output directory is not empty: {args.output_dir}")
    packet, summary = build_packet(read_jsonl(args.input))
    args.output_dir.mkdir(parents=True, exist_ok=True)
    packet_path = args.output_dir / "semantic_review_packet_v1.jsonl"
    summary_path = args.output_dir / "summary_v1.json"
    write_jsonl(packet_path, packet)
    write_json(summary_path, summary)
    write_json(
        args.output_dir / "hash_ledger_v1.json",
        {
            "schema": "gis_recommend.hash_ledger.v1",
            "inputs": {args.input.name: sha256(args.input)},
            "artifacts": {
                path.name: {"bytes": path.stat().st_size, "sha256": sha256(path)}
                for path in (packet_path, summary_path)
            },
        },
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
