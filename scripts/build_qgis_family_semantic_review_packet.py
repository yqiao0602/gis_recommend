#!/usr/bin/env python3
"""Freeze source-fact semantic review packets for qualified family rows."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

SCHEMA = "gis_recommend.qgis_family_semantic_review_packet.v1"


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def build_packet(rows: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    packet: list[dict[str, Any]] = []
    seen: set[str] = set()
    for row in rows:
        if row.get("qualification_status") != "ready_for_independent_semantic_review":
            raise ValueError(f"row is not qualification-ready: {row.get('review_id') or row.get('record_id')}")
        review_id = str(row.get("review_id") or row.get("candidate_id") or row.get("record_id") or "")
        source_path = Path(str(row.get("source_path") or ""))
        expected_sha = str(row.get("source_sha256") or "")
        if not review_id or review_id in seen or not source_path.is_file():
            raise ValueError(f"missing/duplicate review identity or source: {review_id}")
        actual_sha = hashlib.sha256(source_path.read_bytes()).hexdigest()
        if actual_sha != expected_sha:
            raise ValueError(f"source SHA mismatch: {review_id}")
        seen.add(review_id)
        packet.append({
            "schema": SCHEMA,
            "review_id": review_id,
            "source_path": str(source_path),
            "source_sha256": expected_sha,
            "source_text": source_path.read_text(encoding="utf-8", errors="replace"),
            "split": row.get("split"),
            "family_sequence": row.get("family_sequence") or [],
            "full_parent_operator_sequence": row.get("full_parent_operator_sequence") or [],
            "matched_span": row.get("matched_span") or {},
            "proposed_l3_sequence": row.get("proposed_l3_sequence") or [],
            "provider_io_contracts": row.get("provider_io_contracts") or [],
            "task_text_candidate": row.get("task_text_candidate") or "",
            "processing_calls": row.get("processing_calls") or [],
            "audit_checks": row.get("audit_checks") or {},
            "parent_source_sha256": row.get("parent_source_sha256") or expected_sha,
            "review_contract": {
                "question": "Does the source intent support the task and ordered family/L3 chain?",
                "allowed_decisions": ["gold", "retain_silver", "reject"],
                "gold_requirements": ["source_execution_logic_pass", "task_source_intent_pass", "operator_chain_pass", "l3_alignment_pass", "io_contract_pass"],
                "hard_reject_conditions": ["source_identity_failure", "operator_chain_wrong_or_truncated", "task_conflicts_with_source", "l3_conflicts_with_operator", "io_contract_conflict"],
            },
            "source_execution_logic_verdict": "pending",
            "task_source_intent_verdict": "pending",
            "operator_chain_verdict": "pending",
            "l3_alignment_verdict": "pending",
            "io_contract_verdict": "pending",
            "semantic_review_decision": "pending",
            "semantic_review_notes": "",
            "training_admission": "not_granted_independent_family_semantic_review_required",
            "training_rows_emitted": 0,
            "validation_eligible": False,
            "test_eligible": False,
            "production_merge": "not_granted",
        })
    packet.sort(key=lambda row: (str(row.get("split") or ""), str(row["source_sha256"]), row["review_id"]))
    return packet, {
        "schema": f"{SCHEMA}.summary",
        "input_rows": len(rows),
        "packet_rows": len(packet),
        "source_sha_verified_rows": len(packet),
        "unique_source_sha256": len({row["source_sha256"] for row in packet}),
        "pending_independent_reviews": len(packet),
        "decision_counts": {"pending": len(packet)},
        "training_rows_emitted": 0,
        "training_admission": "not_granted_independent_family_semantic_review_required",
        "production_merge": "not_granted",
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    packet, summary = build_packet(read_jsonl(args.input))
    args.output_dir.mkdir(parents=True, exist_ok=True)
    packet_path = args.output_dir / "semantic_review_packet_v1.jsonl"
    summary_path = args.output_dir / "summary_v1.json"
    packet_path.write_text("".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in packet), encoding="utf-8")
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (args.output_dir / "hash_ledger_v1.json").write_text(json.dumps({path.name: hashlib.sha256(path.read_bytes()).hexdigest() for path in (packet_path, summary_path)}, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
