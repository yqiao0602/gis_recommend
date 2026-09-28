#!/usr/bin/env python3
"""Build a human review packet for GEE P2 rewritten descriptions.

This script prepares review material only. It does not adjudicate, train,
promote validation/test rows, or mutate the P2 rewrite input.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.audit_gee_training_admission import _atomic_write_text  # noqa: E402


DEFAULT_REPORT_DIR = ROOT / "docs/reports/gee_raster_core_v1_review_split_2026-07-24"
DEFAULT_P2_REWRITES = DEFAULT_REPORT_DIR / "gee_p2_rewrite_8_v1.jsonl"
OUTPUT_PREFIX = "gee_p2_rewrite_8_review_packet_v1"

HUMAN_FIELDS = (
    "human_task_text_faithful",
    "human_known_omissions_correct",
    "human_should_enter_train_only",
    "human_review_notes",
)

CSV_FIELDS = (
    "review_id",
    "script_id",
    "review_status",
    "rewritten_task_name",
    "rewritten_task_description",
    "original_task_name",
    "original_task_description",
    "operator_sequence",
    "l3_sequence",
    "known_omissions",
    "salvage_reason",
    "evidence_snippet",
    "source_sha256",
    "source_path",
    "admission_tier",
    "sample_weight",
    "validation_eligible",
    "test_eligible",
    *HUMAN_FIELDS,
)


@dataclass(slots=True)
class ReviewPacketResult:
    rows: list[dict[str, Any]]
    summary: dict[str, Any]


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with Path(path).open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            record = json.loads(line)
            if not isinstance(record, dict):
                raise ValueError(f"line {line_number} must contain a JSON object")
            rows.append(record)
    if not rows:
        raise ValueError(f"{path} contains no rows")
    return rows


def _json_value(value: Any) -> Any:
    if isinstance(value, (list, dict)):
        return json.dumps(value, ensure_ascii=False, sort_keys=True)
    return value


def _review_row(row: dict[str, Any]) -> dict[str, Any]:
    packet = {
        "review_id": row["review_id"],
        "script_id": row["script_id"],
        "review_status": "pending",
        "rewritten_task_name": row["task_name"],
        "rewritten_task_description": row["task_description"],
        "original_task_name": row.get("original_task_name", ""),
        "original_task_description": row.get("original_task_description", ""),
        "operator_sequence": row["operator_sequence"],
        "l3_sequence": row["l3_sequence"],
        "known_omissions": row["known_omissions"],
        "salvage_reason": row.get("salvage_reason", ""),
        "evidence_snippet": row.get("evidence_snippet", ""),
        "source_sha256": row["source_sha256"],
        "source_path": row["source_path"],
        "admission_tier": row["admission_tier"],
        "sample_weight": row["sample_weight"],
        "validation_eligible": row["validation_eligible"],
        "test_eligible": row["test_eligible"],
    }
    for field in HUMAN_FIELDS:
        packet[field] = ""
    return packet


def build_review_packet(*, p2_rewrite_jsonl_path: Path) -> ReviewPacketResult:
    source_rows = _load_jsonl(p2_rewrite_jsonl_path)
    rows = [_review_row(row) for row in sorted(source_rows, key=lambda item: item["review_id"])]
    pending = sum(1 for row in rows if row["review_status"] == "pending")
    summary = {
        "schema": "gis_recommend.gee_p2_rewrite_review_packet.v1",
        "inputs": {"p2_rewrites": str(Path(p2_rewrite_jsonl_path))},
        "counts": {
            "rows": len(rows),
            "pending_human_review": pending,
            "adjudicated_rows": 0,
        },
        "decision": {
            "training_admission": "not_granted_pending_human_text_fidelity_review",
            "validation_eligible": False,
            "test_eligible": False,
            "next_gate": "fill human review fields and recompute P2 admission",
        },
        "human_field_policy": {
            "human_task_text_faithful": "yes | no | needs_edit",
            "human_known_omissions_correct": "yes | no | needs_edit",
            "human_should_enter_train_only": "yes_train_only | no | needs_edit",
            "human_review_notes": "free text",
        },
    }
    return ReviewPacketResult(rows=rows, summary=summary)


def _jsonl_text(rows: list[dict[str, Any]]) -> str:
    return "".join(
        json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"
        for row in rows
    )


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=CSV_FIELDS)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: _json_value(row.get(field, "")) for field in CSV_FIELDS})


def _sha256(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _render_instructions(summary: dict[str, Any], rows: list[dict[str, Any]]) -> str:
    lines = [
        "# GEE P2 Rewrite Human Review Packet",
        "",
        "This packet reviews only task-text fidelity for deterministic P2 rewrites.",
        "Do not use this packet to grant validation/test admission or QGIS operator-chain gold status.",
        "",
        "## Required human fields",
        "",
        "- `human_task_text_faithful`: `yes`, `no`, or `needs_edit`.",
        "- `human_known_omissions_correct`: `yes`, `no`, or `needs_edit`.",
        "- `human_should_enter_train_only`: `yes_train_only`, `no`, or `needs_edit`.",
        "- `human_review_notes`: concise reason for the decision.",
        "",
        "Accept only if the rewritten task name/description describes exactly the retained operator/L3 chain,",
        "and all omitted original-script behavior is represented only in `known_omissions`.",
        "",
        "## Summary",
        "",
        f"- Rows: {summary['counts']['rows']}",
        f"- Pending human review: {summary['counts']['pending_human_review']}",
        f"- Training admission: `{summary['decision']['training_admission']}`",
        "",
        "## Rows",
        "",
    ]
    for row in rows:
        lines.extend(
            [
                f"### {row['review_id']}",
                "",
                f"- Rewritten task: {row['rewritten_task_name']}",
                f"- Description: {row['rewritten_task_description']}",
                f"- Known omissions: {', '.join(row['known_omissions'])}",
                f"- Operators: {', '.join(row['operator_sequence'])}",
                "",
            ]
        )
    return "\n".join(lines)


def write_outputs(
    result: ReviewPacketResult,
    output_dir: Path,
    *,
    output_prefix: str = OUTPUT_PREFIX,
) -> dict[str, Path]:
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    csv_path = output_dir / f"{output_prefix}.csv"
    jsonl_path = output_dir / f"{output_prefix}.jsonl"
    summary_path = output_dir / f"{output_prefix}_summary.json"
    instructions_path = output_dir / f"{output_prefix}_instructions.md"
    hash_ledger_path = output_dir / f"{output_prefix}_hash_ledger.json"

    _write_csv(csv_path, result.rows)
    _atomic_write_text(jsonl_path, _jsonl_text(result.rows))
    _atomic_write_text(summary_path, json.dumps(result.summary, ensure_ascii=False, indent=2, sort_keys=True))
    _atomic_write_text(instructions_path, _render_instructions(result.summary, result.rows))
    ledger = {
        "schema": "gis_recommend.hash_ledger.v1",
        "source_inputs": {
            "p2_rewrites": {
                "path": result.summary["inputs"]["p2_rewrites"],
                "sha256": _sha256(Path(result.summary["inputs"]["p2_rewrites"])),
            }
        },
        "artifacts": {
            csv_path.name: {"path": str(csv_path), "sha256": _sha256(csv_path), "bytes": csv_path.stat().st_size},
            jsonl_path.name: {"path": str(jsonl_path), "sha256": _sha256(jsonl_path), "bytes": jsonl_path.stat().st_size},
            summary_path.name: {"path": str(summary_path), "sha256": _sha256(summary_path), "bytes": summary_path.stat().st_size},
            instructions_path.name: {"path": str(instructions_path), "sha256": _sha256(instructions_path), "bytes": instructions_path.stat().st_size},
        },
    }
    _atomic_write_text(hash_ledger_path, json.dumps(ledger, ensure_ascii=False, indent=2, sort_keys=True))
    return {
        "csv": csv_path,
        "jsonl": jsonl_path,
        "summary": summary_path,
        "instructions": instructions_path,
        "hash_ledger": hash_ledger_path,
    }


def main(argv: list[str] | None = None) -> dict[str, Path]:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--p2-rewrites", type=Path, default=DEFAULT_P2_REWRITES)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_REPORT_DIR)
    parser.add_argument("--output-prefix", default=OUTPUT_PREFIX)
    args = parser.parse_args(argv)

    result = build_review_packet(p2_rewrite_jsonl_path=args.p2_rewrites)
    return write_outputs(result, args.output_dir, output_prefix=args.output_prefix)


if __name__ == "__main__":
    main()
