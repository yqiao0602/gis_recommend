#!/usr/bin/env python3
"""Build a human-review packet for source-derived QGIS subworkflow candidates."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path
from typing import Any

REVIEW_OPTIONS = (
    "independent_workflow",
    "implementation_subworkflow",
    "duplicate_or_parent_contained",
)


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def build_packet(rows: list[dict[str, Any]]) -> list[dict[str, str]]:
    packet: list[dict[str, str]] = []
    for row in sorted(rows, key=lambda item: str(item["candidate_id"])):
        if row.get("training_admission") != "not_granted_candidate_only":
            raise ValueError(f"candidate is not review-only: {row.get('candidate_id')}")
        packet.append(
            {
                "candidate_id": str(row["candidate_id"]),
                "parent_workflow_id": str(row.get("parent_workflow_id") or ""),
                "parent_source_sha256": str(row.get("seed_source_sha256") or ""),
                "source_path": str(row.get("seed_source_path") or ""),
                "source_span": json.dumps(row.get("seed_source_span"), ensure_ascii=False, sort_keys=True),
                "parent_task": str(row.get("seed_task_description") or ""),
                "subworkflow_task": str(row.get("task_description") or ""),
                "operators": json.dumps(row.get("operator_sequence") or [], ensure_ascii=False),
                "l3_codes": json.dumps(row.get("l3_code_sequence") or [], ensure_ascii=False),
                "input_types": json.dumps(row.get("subworkflow_input_types") or [], ensure_ascii=False),
                "output_types": json.dumps(row.get("subworkflow_output_types") or [], ensure_ascii=False),
                "split_group_key": str(row.get("split_group_key") or ""),
                "decision": "",
                "review_reason": "",
            }
        )
    return packet


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidates", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    packet = build_packet(_read_jsonl(args.candidates))
    args.output_dir.mkdir(parents=True, exist_ok=True)
    packet_path = args.output_dir / "subworkflow_semantic_review_packet_v1.csv"
    with packet_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(packet[0]) if packet else [])
        writer.writeheader()
        writer.writerows(packet)
    summary = {
        "schema": "gis_recommend.qgis_seed_subworkflow_review_packet.v1.summary",
        "review_rows": len(packet),
        "review_decision_options": list(REVIEW_OPTIONS),
        "training_admission": "not_granted_candidate_only",
        "split_policy": "all_parent_subworkflows_must_share_one_split",
    }
    summary_path = args.output_dir / "summary_v1.json"
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    hashes = {path.name: hashlib.sha256(path.read_bytes()).hexdigest() for path in (packet_path, summary_path)}
    (args.output_dir / "hash_ledger_v1.json").write_text(
        json.dumps(hashes, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
