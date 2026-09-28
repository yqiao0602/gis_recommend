#!/usr/bin/env python3
"""Join P0 gap rows, official QGIS metadata, and source evidence."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path


def _load_rows(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def _summarize(items: object) -> str:
    if not isinstance(items, list):
        return ""
    values = []
    for item in items:
        if not isinstance(item, dict):
            continue
        identifier = str(item.get("identifier") or item.get("name") or "").strip()
        data_type = str(item.get("type") or item.get("dataType") or "").strip()
        if identifier:
            values.append(f"{identifier}:{data_type}" if data_type else identifier)
    return " | ".join(values)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--gap-csv", required=True, type=Path)
    parser.add_argument("--evidence-csv", required=True, type=Path)
    parser.add_argument("--official-json", required=True, type=Path)
    parser.add_argument("--output-csv", required=True, type=Path)
    parser.add_argument("--priority", default="P0_frequency_ge_20")
    args = parser.parse_args()

    gaps = [
        row for row in _load_rows(args.gap_csv)
        if row.get("priority") == args.priority
    ]
    if not gaps:
        raise ValueError(f"no gap rows found for priority {args.priority}")
    evidence = _load_rows(args.evidence_csv)
    official = json.loads(args.official_json.read_text(encoding="utf-8"))
    official_by_id = {
        str(item.get("identifier") or "").lower(): item
        for item in official
        if isinstance(item, dict) and item.get("identifier")
    }
    evidence_by_id: dict[str, list[dict[str, str]]] = {}
    for row in evidence:
        evidence_by_id.setdefault(row["operator_id"].lower(), []).append(row)

    fields = [
        "priority",
        "operator_id",
        "frequency",
        "official_name",
        "official_description",
        "official_input_summary",
        "official_output_summary",
        "evidence_count",
        "source_evidence_json",
        "mapping_kind",
        "candidate_l3_code",
        "decision",
        "confidence",
        "review_reason",
        "reviewer",
        "reviewed_at",
    ]
    output_rows = []
    for gap in gaps:
        operator_id = gap["operator_id"].lower()
        metadata = official_by_id.get(operator_id, {})
        samples = evidence_by_id.get(operator_id, [])
        output_rows.append(
            {
                "priority": gap.get("priority", ""),
                "operator_id": operator_id,
                "frequency": gap.get("frequency", ""),
                "official_name": metadata.get("name", gap.get("official_name", "")),
                "official_description": metadata.get("description", ""),
                "official_input_summary": _summarize(metadata.get("inputs")),
                "official_output_summary": _summarize(metadata.get("outputs")),
                "evidence_count": str(len(samples)),
                "source_evidence_json": json.dumps(samples, ensure_ascii=False, separators=(",", ":")),
                "mapping_kind": "",
                "candidate_l3_code": "",
                "decision": "",
                "confidence": "",
                "review_reason": "",
                "reviewer": "",
                "reviewed_at": "",
            }
        )
    output_rows.sort(key=lambda row: (-int(row["frequency"] or 0), row["operator_id"]))

    args.output_csv.parent.mkdir(parents=True, exist_ok=True)
    with args.output_csv.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(output_rows)
    print(f"review_rows={len(output_rows)} evidence_rows={sum(int(row['evidence_count']) for row in output_rows)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
