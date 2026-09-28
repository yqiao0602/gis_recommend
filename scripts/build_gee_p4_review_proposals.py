#!/usr/bin/env python3
"""Build proposal-only decisions for a GEE P4 rereview packet.

The proposal sidecar preserves the original packet and leaves all human
adjudication fields untouched. It never grants training, validation, or test
admission; a separate human confirmation step is required before export.
"""

from __future__ import annotations

import argparse
import csv
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.audit_gee_training_admission import _atomic_write_text  # noqa: E402


DEFAULT_REPORT_DIR = ROOT / "docs/reports/gee_raster_core_v1_review_split_2026-07-24"
DEFAULT_REVIEW_PACKET = DEFAULT_REPORT_DIR / "gee_p4_rereview_packet_28_v1.jsonl"
HUMAN_FIELDS = (
    "human_task_text_faithful_to_new_chain",
    "human_new_chain_correct",
    "human_new_chain_complete_for_core_subworkflow",
    "human_should_enter_train_only",
    "human_known_omissions",
    "human_review_notes",
)
DECISION_FIELDS = (
    "task_text_faithful",
    "new_chain_correct",
    "core_complete",
    "should_enter_train_only",
    "known_omissions",
    "review_notes",
)
TASK_TEXT_VALUES = {"yes", "needs_edit", "no"}
CHAIN_VALUES = {"yes", "partial", "no"}
ADMISSION_VALUES = {"yes_train_only", "needs_edit", "defer", "no"}


@dataclass(slots=True)
class ProposalResult:
    rows: list[dict[str, Any]]
    summary: dict[str, Any]


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with Path(path).open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            row = json.loads(line)
            if not isinstance(row, dict):
                raise ValueError(f"line {line_number} must contain a JSON object")
            rows.append(row)
    if not rows:
        raise ValueError(f"{path} contains no rows")
    return rows


def _jsonl_text(rows: list[dict[str, Any]]) -> str:
    return "".join(
        json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"
        for row in rows
    )


def _sha256(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _validate_decision(review_id: str, decision: dict[str, str]) -> None:
    missing = [field for field in DECISION_FIELDS if field not in decision]
    if missing:
        raise ValueError(f"decision for {review_id!r} missing fields: {missing}")
    if decision["task_text_faithful"] not in TASK_TEXT_VALUES:
        raise ValueError(f"invalid task_text_faithful for {review_id!r}")
    if decision["new_chain_correct"] not in CHAIN_VALUES:
        raise ValueError(f"invalid new_chain_correct for {review_id!r}")
    if decision["core_complete"] not in CHAIN_VALUES:
        raise ValueError(f"invalid core_complete for {review_id!r}")
    if decision["should_enter_train_only"] not in ADMISSION_VALUES:
        raise ValueError(f"invalid should_enter_train_only for {review_id!r}")


def build_p4_review_proposals(
    *,
    review_packet_jsonl_path: Path,
    decisions: dict[str, dict[str, str]],
    batch_id: str,
    require_all_rows: bool = True,
) -> ProposalResult:
    source_rows = _load_jsonl(review_packet_jsonl_path)
    source_ids = {str(row.get("review_id", "")) for row in source_rows}
    if "" in source_ids:
        raise ValueError("every P4 row must have a review_id")
    decision_ids = set(decisions)
    missing = sorted(source_ids - decision_ids)
    unknown = sorted(decision_ids - source_ids)
    if missing and require_all_rows:
        raise ValueError(f"missing decision for {missing[0]!r}")
    if unknown:
        raise ValueError(f"unknown decision for {unknown[0]!r}")
    selected_source_rows = [
        row for row in source_rows if str(row["review_id"]) in decision_ids
    ]
    if not selected_source_rows:
        raise ValueError("no source rows selected by decisions")

    rows: list[dict[str, Any]] = []
    for source_row in sorted(selected_source_rows, key=lambda row: str(row["review_id"])):
        review_id = str(source_row["review_id"])
        decision = decisions[review_id]
        _validate_decision(review_id, decision)
        row = dict(source_row)
        row["proposal_status"] = "proposal_only"
        row["proposal_batch"] = batch_id
        row["proposed_task_text_faithful"] = decision["task_text_faithful"]
        row["proposed_new_chain_correct"] = decision["new_chain_correct"]
        row["proposed_new_chain_complete_for_core_subworkflow"] = decision["core_complete"]
        row["proposed_should_enter_train_only"] = decision["should_enter_train_only"]
        row["proposed_known_omissions"] = decision["known_omissions"]
        row["proposed_review_notes"] = decision["review_notes"]
        rows.append(row)

    count = lambda value: sum(  # noqa: E731
        1 for row in rows if row["proposed_should_enter_train_only"] == value
    )
    summary = {
        "schema": "gis_recommend.gee_p4_review_proposals.v1",
        "inputs": {"review_packet": str(Path(review_packet_jsonl_path))},
        "batch_id": batch_id,
        "counts": {
            "source_packet_rows": len(source_rows),
            "rows": len(rows),
            "proposal_yes_train_only": count("yes_train_only"),
            "proposal_needs_edit": count("needs_edit"),
            "proposal_defer": count("defer"),
            "proposal_rejected": count("no"),
        },
        "decision": {
            "training_admission": "not_granted_proposal_only",
            "validation_eligible": False,
            "test_eligible": False,
            "next_gate": "human confirmation of proposal decisions, then P4 export gate",
        },
        "policy": {
            "human_fields_untouched": True,
            "llm_used": False,
            "training_rows_emitted": False,
        },
    }
    return ProposalResult(rows=rows, summary=summary)


def _csv_value(value: Any) -> str:
    if isinstance(value, (list, dict)):
        return json.dumps(value, ensure_ascii=False, sort_keys=True)
    return "" if value is None else str(value)


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    fields: list[str] = []
    for row in rows:
        for field in row:
            if field not in fields:
                fields.append(field)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: _csv_value(row.get(field, "")) for field in fields})


def _render_report(summary: dict[str, Any], rows: list[dict[str, Any]]) -> str:
    lines = [
        "# GEE P4 Review Proposals",
        "",
        "Proposal-only sidecar. It does not mutate human fields or grant admission.",
        "",
        f"- Batch: `{summary['batch_id']}`",
        f"- Rows: {summary['counts']['rows']}",
        f"- Proposed yes_train_only: {summary['counts']['proposal_yes_train_only']}",
        f"- Proposed needs_edit: {summary['counts']['proposal_needs_edit']}",
        f"- Proposed defer: {summary['counts']['proposal_defer']}",
        f"- Proposed reject: {summary['counts']['proposal_rejected']}",
        "",
        "## Rows",
        "",
    ]
    for row in rows:
        lines.extend(
            [
                f"### {row['review_id']}",
                "",
                f"- Proposed task text: {row['proposed_task_text_faithful']}",
                f"- Proposed chain correct: {row['proposed_new_chain_correct']}",
                f"- Proposed core completeness: {row['proposed_new_chain_complete_for_core_subworkflow']}",
                f"- Proposed train-only: {row['proposed_should_enter_train_only']}",
                f"- Known omissions: {row['proposed_known_omissions']}",
                f"- Notes: {row['proposed_review_notes']}",
                "",
            ]
        )
    return "\n".join(lines)


def write_outputs(
    result: ProposalResult,
    output_dir: Path,
    *,
    output_prefix: str,
) -> dict[str, Path]:
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    csv_path = output_dir / f"{output_prefix}.csv"
    jsonl_path = output_dir / f"{output_prefix}.jsonl"
    summary_path = output_dir / f"{output_prefix}_summary.json"
    report_path = output_dir / f"{output_prefix}_report.md"
    hash_ledger_path = output_dir / f"{output_prefix}_hash_ledger.json"

    _write_csv(csv_path, result.rows)
    _atomic_write_text(jsonl_path, _jsonl_text(result.rows))
    _atomic_write_text(summary_path, json.dumps(result.summary, ensure_ascii=False, indent=2, sort_keys=True))
    _atomic_write_text(report_path, _render_report(result.summary, result.rows))
    ledger = {
        "schema": "gis_recommend.hash_ledger.v1",
        "source_inputs": {
            "review_packet": {
                "path": result.summary["inputs"]["review_packet"],
                "sha256": _sha256(Path(result.summary["inputs"]["review_packet"])),
            }
        },
        "artifacts": {
            path.name: {
                "path": str(path),
                "sha256": _sha256(path),
                "bytes": path.stat().st_size,
            }
            for path in (csv_path, jsonl_path, summary_path, report_path)
        },
    }
    _atomic_write_text(hash_ledger_path, json.dumps(ledger, ensure_ascii=False, indent=2, sort_keys=True))
    return {
        "csv": csv_path,
        "jsonl": jsonl_path,
        "summary": summary_path,
        "report": report_path,
        "hash_ledger": hash_ledger_path,
    }


def main(argv: list[str] | None = None) -> dict[str, Path]:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--review-packet", type=Path, default=DEFAULT_REVIEW_PACKET)
    parser.add_argument("--decisions-json", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_REPORT_DIR)
    parser.add_argument("--batch-id", required=True)
    parser.add_argument("--output-prefix", required=True)
    parser.add_argument("--allow-subset", action="store_true")
    args = parser.parse_args(argv)

    decisions = json.loads(args.decisions_json.read_text(encoding="utf-8"))
    if not isinstance(decisions, dict):
        raise ValueError("decisions JSON must be an object keyed by review_id")
    result = build_p4_review_proposals(
        review_packet_jsonl_path=args.review_packet,
        decisions=decisions,
        batch_id=args.batch_id,
        require_all_rows=not args.allow_subset,
    )
    return write_outputs(result, args.output_dir, output_prefix=args.output_prefix)


if __name__ == "__main__":
    main()
