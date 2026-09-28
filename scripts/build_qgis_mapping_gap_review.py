#!/usr/bin/env python3
"""Build a source-independent review queue for unmapped QGIS operators."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path


def _priority(frequency: int) -> str:
    if frequency >= 20:
        return "P0_frequency_ge_20"
    if frequency >= 10:
        return "P1_frequency_ge_10"
    return "P2_long_tail"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--crosswalk", type=Path, required=True)
    parser.add_argument("--output-csv", type=Path, required=True)
    parser.add_argument("--output-summary", type=Path, required=True)
    args = parser.parse_args()

    payload = json.loads(args.crosswalk.read_text(encoding="utf-8"))
    entries = payload.get("entries")
    if not isinstance(entries, dict):
        raise ValueError("crosswalk entries must be an object")

    rows = []
    for operator_id, entry in entries.items():
        if not isinstance(entry, dict) or entry.get("status") != "pending_review":
            continue
        frequency = int(entry.get("frequency", 0) or 0)
        rows.append(
            {
                "priority": _priority(frequency),
                "operator_id": operator_id,
                "frequency": frequency,
                "official_name": str(entry.get("official_name") or ""),
                "provider": operator_id.partition(":")[0],
                "candidate_mapping_kind": "",
                "candidate_l3_code": "",
                "review_decision": "",
                "review_reason": "",
                "source_evidence": "",
                "reviewer": "",
                "reviewed_at": "",
            }
        )
    rows.sort(key=lambda row: (-row["frequency"], row["operator_id"]))

    fields = list(rows[0]) if rows else [
        "priority",
        "operator_id",
        "frequency",
        "official_name",
        "provider",
        "candidate_mapping_kind",
        "candidate_l3_code",
        "review_decision",
        "review_reason",
        "source_evidence",
        "reviewer",
        "reviewed_at",
    ]
    args.output_csv.parent.mkdir(parents=True, exist_ok=True)
    with args.output_csv.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)

    counts = {priority: sum(row["priority"] == priority for row in rows) for priority in (
        "P0_frequency_ge_20", "P1_frequency_ge_10", "P2_long_tail"
    )}
    summary = {
        "schema_version": "qgis_mapping_gap_review_v1",
        "crosswalk": str(args.crosswalk),
        "pending_operator_count": len(rows),
        "pending_occurrence_count": sum(row["frequency"] for row in rows),
        "priority_counts": counts,
        "review_admission": "not_granted",
        "taxonomy_admission": "not_granted",
        "decision_values": [
            "alias_existing_stable94",
            "restore_old350_l3",
            "new_l3_candidate",
            "exclude_non_target",
            "defer_unresolved",
        ],
    }
    args.output_summary.parent.mkdir(parents=True, exist_ok=True)
    args.output_summary.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(
        f"pending={len(rows)} occurrences={summary['pending_occurrence_count']} "
        f"P0={counts['P0_frequency_ge_20']} P1={counts['P1_frequency_ge_10']} "
        f"P2={counts['P2_long_tail']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
