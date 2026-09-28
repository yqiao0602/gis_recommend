#!/usr/bin/env python3
"""Confirm GEE P4 proposal sidecars into an adjudication sidecar.

This script does not mutate the original P4 rereview packet and does not emit
training rows. It records confirmed proposal decisions in a separate sidecar so
rewrite/export gates can consume a stable adjudication artifact.
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
DEFAULT_PROPOSALS = (
    DEFAULT_REPORT_DIR / "gee_p4_review_proposals_1_10_v1.jsonl",
    DEFAULT_REPORT_DIR / "gee_p4_review_proposals_11_20_v1.jsonl",
    DEFAULT_REPORT_DIR / "gee_p4_review_proposals_21_28_v1.jsonl",
)
OUTPUT_PREFIX = "gee_p4_review_adjudication_28_v1"
ADJUDICATION_BASIS = "confirmed_p4_proposal_v1"


@dataclass(slots=True)
class P4AdjudicationResult:
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
                raise ValueError(f"{path} line {line_number} must be a JSON object")
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


def _load_proposals(paths: list[Path]) -> dict[str, dict[str, Any]]:
    proposals: dict[str, dict[str, Any]] = {}
    for path in paths:
        for row in _load_jsonl(path):
            review_id = str(row.get("review_id", ""))
            if not review_id:
                raise ValueError(f"{path} contains proposal without review_id")
            if review_id in proposals:
                raise ValueError(f"duplicate proposal for {review_id!r}")
            proposals[review_id] = row
    return proposals


def _adjudicate_row(packet_row: dict[str, Any], proposal: dict[str, Any]) -> dict[str, Any]:
    row = dict(packet_row)
    row["review_status"] = "adjudicated"
    row["adjudication_basis"] = ADJUDICATION_BASIS
    row["adjudication_batch"] = proposal.get("proposal_batch", "")
    row["human_task_text_faithful_to_new_chain"] = proposal["proposed_task_text_faithful"]
    row["human_new_chain_correct"] = proposal["proposed_new_chain_correct"]
    row["human_new_chain_complete_for_core_subworkflow"] = proposal[
        "proposed_new_chain_complete_for_core_subworkflow"
    ]
    row["human_should_enter_train_only"] = proposal["proposed_should_enter_train_only"]
    row["human_known_omissions"] = proposal.get("proposed_known_omissions", "")
    row["human_review_notes"] = (
        f"Confirmed from P4 proposal batch {proposal.get('proposal_batch', '')}: "
        f"{proposal.get('proposed_review_notes', '')}"
    ).strip()
    return row


def build_p4_adjudication(
    *,
    review_packet_jsonl_path: Path,
    proposal_jsonl_paths: list[Path],
    require_all_rows: bool = True,
) -> P4AdjudicationResult:
    packet_rows = _load_jsonl(review_packet_jsonl_path)
    packet_by_id = {str(row.get("review_id", "")): row for row in packet_rows}
    if "" in packet_by_id:
        raise ValueError("every packet row must have a review_id")
    if len(packet_by_id) != len(packet_rows):
        raise ValueError("review packet contains duplicate review_id values")

    proposals = _load_proposals(proposal_jsonl_paths)
    missing = sorted(set(packet_by_id) - set(proposals))
    unknown = sorted(set(proposals) - set(packet_by_id))
    if missing and require_all_rows:
        raise ValueError(f"missing proposals for {missing[:3]}")
    if unknown:
        raise ValueError(f"unknown proposals for {unknown[:3]}")

    selected_ids = sorted(set(packet_by_id) & set(proposals))
    if not selected_ids:
        raise ValueError("no packet rows covered by proposals")
    rows = [_adjudicate_row(packet_by_id[review_id], proposals[review_id]) for review_id in selected_ids]

    accepted = sum(1 for row in rows if row["human_should_enter_train_only"] == "yes_train_only")
    needs_edit = sum(1 for row in rows if row["human_should_enter_train_only"] == "needs_edit")
    deferred = sum(1 for row in rows if row["human_should_enter_train_only"] == "defer")
    rejected = sum(1 for row in rows if row["human_should_enter_train_only"] == "no")
    training_admission = (
        "not_granted_pending_export_gate"
        if needs_edit == 0 and deferred == 0
        else "not_granted_pending_rewrite_and_export_gate"
    )
    summary = {
        "schema": "gis_recommend.gee_p4_review_adjudication.v1",
        "inputs": {
            "review_packet": str(Path(review_packet_jsonl_path)),
            "proposal_jsonl_paths": [str(Path(path)) for path in proposal_jsonl_paths],
        },
        "counts": {
            "packet_rows": len(packet_rows),
            "rows": len(rows),
            "accepted_train_only": accepted,
            "needs_edit": needs_edit,
            "deferred": deferred,
            "rejected": rejected,
            "pending": 0,
        },
        "decision": {
            "training_admission": training_admission,
            "validation_eligible": False,
            "test_eligible": False,
            "next_gate": "rewrite needs_edit rows, then train-only export gate for accepted rows",
        },
        "policy": {
            "adjudication_basis": ADJUDICATION_BASIS,
            "original_packet_mutated": False,
            "llm_used": False,
            "training_rows_emitted": False,
        },
    }
    return P4AdjudicationResult(rows=rows, summary=summary)


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
        "# GEE P4 Review Adjudication",
        "",
        "Confirmed sidecar derived from P4 proposal batches.",
        "It does not emit training rows and does not grant validation/test admission.",
        "",
        "## Summary",
        "",
        f"- Rows: {summary['counts']['rows']}",
        f"- Accepted train-only: {summary['counts']['accepted_train_only']}",
        f"- Needs edit: {summary['counts']['needs_edit']}",
        f"- Deferred: {summary['counts']['deferred']}",
        f"- Rejected: {summary['counts']['rejected']}",
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
                f"- Task text faithful: {row['human_task_text_faithful_to_new_chain']}",
                f"- New chain correct: {row['human_new_chain_correct']}",
                f"- Core complete: {row['human_new_chain_complete_for_core_subworkflow']}",
                f"- Should enter train-only: {row['human_should_enter_train_only']}",
                f"- Notes: {row['human_review_notes']}",
                "",
            ]
        )
    return "\n".join(lines)


def write_outputs(
    result: P4AdjudicationResult,
    output_dir: Path,
    *,
    output_prefix: str = OUTPUT_PREFIX,
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
            },
            "proposal_jsonl_paths": [
                {"path": path, "sha256": _sha256(Path(path))}
                for path in result.summary["inputs"]["proposal_jsonl_paths"]
            ],
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
    parser.add_argument("--proposal-jsonl", type=Path, action="append", default=[])
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_REPORT_DIR)
    parser.add_argument("--output-prefix", default=OUTPUT_PREFIX)
    parser.add_argument("--allow-subset", action="store_true")
    args = parser.parse_args(argv)

    proposal_paths = args.proposal_jsonl or list(DEFAULT_PROPOSALS)
    result = build_p4_adjudication(
        review_packet_jsonl_path=args.review_packet,
        proposal_jsonl_paths=proposal_paths,
        require_all_rows=not args.allow_subset,
    )
    return write_outputs(result, args.output_dir, output_prefix=args.output_prefix)


if __name__ == "__main__":
    main()
