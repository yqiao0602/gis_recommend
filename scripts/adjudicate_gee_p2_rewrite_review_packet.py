#!/usr/bin/env python3
"""Adjudicate the GEE P2 rewrite human review packet.

This script writes a human-sidecar decision file for the eight deterministic
P2 rewrites. It does not mutate the review packet input, does not grant
validation/test admission, and does not export training rows.
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
from scripts.build_gee_p2_rewrite_review_packet import (  # noqa: E402
    CSV_FIELDS,
    HUMAN_FIELDS,
    _json_value,
)


DEFAULT_REPORT_DIR = ROOT / "docs/reports/gee_raster_core_v1_review_split_2026-07-24"
DEFAULT_REVIEW_PACKET = DEFAULT_REPORT_DIR / "gee_p2_rewrite_8_review_packet_v1.jsonl"
OUTPUT_PREFIX = "gee_p2_rewrite_8_review_packet_adjudicated_v1"

EXPECTED_REVIEW_IDS = (
    "gee_raster_core_review_002",
    "gee_raster_core_review_003",
    "gee_raster_core_review_015",
    "gee_raster_core_review_016",
    "gee_raster_core_review_019",
    "gee_raster_core_review_025",
    "gee_raster_core_review_032",
    "gee_raster_core_review_048",
)

DECISIONS_V1: dict[str, dict[str, str]] = {
    "gee_raster_core_review_002": {
        "human_task_text_faithful": "yes",
        "human_known_omissions_correct": "yes",
        "human_should_enter_train_only": "yes_train_only",
        "human_review_notes": "Retained select/mosaic/reduceRegions/limit chain is described; volume, area multiplication, and top-5 ranking stay in known omissions.",
    },
    "gee_raster_core_review_003": {
        "human_task_text_faithful": "yes",
        "human_known_omissions_correct": "yes",
        "human_should_enter_train_only": "yes_train_only",
        "human_review_notes": "NDVI mask, pixel-area multiplication, and region reduction are preserved; display layers and printed summaries remain omitted.",
    },
    "gee_raster_core_review_015": {
        "human_task_text_faithful": "yes",
        "human_known_omissions_correct": "yes",
        "human_should_enter_train_only": "yes_train_only",
        "human_review_notes": "Select/filter/reduce/reduceRegions chain matches the rewritten task; watershed area and export behavior stay omitted.",
    },
    "gee_raster_core_review_016": {
        "human_task_text_faithful": "needs_edit",
        "human_known_omissions_correct": "yes",
        "human_should_enter_train_only": "needs_edit",
        "human_review_notes": "The retained cumulative-cost idea is right, but the text introduces a vague image-collection filter step that is not grounded cleanly in the evidence and needs tightening before train-only admission.",
    },
    "gee_raster_core_review_019": {
        "human_task_text_faithful": "needs_edit",
        "human_known_omissions_correct": "yes",
        "human_should_enter_train_only": "needs_edit",
        "human_review_notes": "The mask/area chain is sound, but 'cloud criteria' is not supported by the retained evidence; the description should be rewritten around the actual date/path/row filtering.",
    },
    "gee_raster_core_review_025": {
        "human_task_text_faithful": "yes",
        "human_known_omissions_correct": "yes",
        "human_should_enter_train_only": "yes_train_only",
        "human_review_notes": "Random Forest sampling/training/classification and class-area reduction are faithfully described; accuracy metrics remain omitted.",
    },
    "gee_raster_core_review_032": {
        "human_task_text_faithful": "yes",
        "human_known_omissions_correct": "yes",
        "human_should_enter_train_only": "yes_train_only",
        "human_review_notes": "Calibrated precipitation select/filterDate/filterBounds chain is faithful; clipping and downstream analysis remain omitted.",
    },
    "gee_raster_core_review_048": {
        "human_task_text_faithful": "yes",
        "human_known_omissions_correct": "yes",
        "human_should_enter_train_only": "yes_train_only",
        "human_review_notes": "TerraClimate mean/toBands/rename chain is preserved; annual composites, WorldClim comparison, and print output remain omitted.",
    },
}

DECISIONS_V2: dict[str, dict[str, str]] = {
    **DECISIONS_V1,
    "gee_raster_core_review_016": {
        "human_task_text_faithful": "yes",
        "human_known_omissions_correct": "yes",
        "human_should_enter_train_only": "yes_train_only",
        "human_review_notes": "V2 text grounds the cumulative-cost mask and retained country-code collection filter without claiming peat-forest overlay, alert display, or visual assessment.",
    },
    "gee_raster_core_review_019": {
        "human_task_text_faithful": "yes",
        "human_known_omissions_correct": "yes",
        "human_should_enter_train_only": "yes_train_only",
        "human_review_notes": "V2 text replaces unsupported cloud-criteria wording with source-evidenced date and WRS path/row metadata filtering while preserving the NDVI-temperature mask and area chain.",
    },
}

DECISIONS_BY_VERSION = {
    "v1": DECISIONS_V1,
    "v2": DECISIONS_V2,
}

V2_TEXT_GUARDS = {
    "gee_raster_core_review_016": {
        "required": ("country-code",),
        "forbidden": ("related image collection",),
    },
    "gee_raster_core_review_019": {
        "required": ("wrs path/row",),
        "forbidden": ("cloud criteria",),
    },
}


@dataclass(slots=True)
class AdjudicationResult:
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


def _jsonl_text(rows: list[dict[str, Any]]) -> str:
    return "".join(
        json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"
        for row in rows
    )


def _sha256(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _adjudicate_row(row: dict[str, Any], *, decisions: dict[str, dict[str, str]]) -> dict[str, Any]:
    review_id = row["review_id"]
    decision = decisions.get(review_id)
    if decision is None:
        raise ValueError(f"unexpected review_id {review_id!r}")
    adjudicated = dict(row)
    adjudicated["review_status"] = "adjudicated"
    for field in HUMAN_FIELDS:
        adjudicated[field] = decision[field]
    return adjudicated


def _enforce_v2_text_guards(rows: list[dict[str, Any]]) -> None:
    by_id = {row["review_id"]: row for row in rows}
    for review_id, guard in V2_TEXT_GUARDS.items():
        row = by_id.get(review_id)
        if row is None:
            raise ValueError(f"v2 text guard missing row {review_id}")
        text = (
            f"{row.get('rewritten_task_name', '')} "
            f"{row.get('rewritten_task_description', '')}"
        ).lower()
        missing = [marker for marker in guard["required"] if marker not in text]
        present_forbidden = [marker for marker in guard["forbidden"] if marker in text]
        if missing or present_forbidden:
            raise ValueError(
                f"v2 text guard failed for {review_id}: "
                f"missing={missing}, forbidden={present_forbidden}"
            )


def build_adjudication(
    *,
    review_packet_jsonl_path: Path,
    decision_version: str = "v1",
) -> AdjudicationResult:
    if decision_version not in DECISIONS_BY_VERSION:
        raise ValueError(f"decision_version must be one of {sorted(DECISIONS_BY_VERSION)}")
    decisions = DECISIONS_BY_VERSION[decision_version]
    source_rows = _load_jsonl(review_packet_jsonl_path)
    if decision_version == "v2":
        _enforce_v2_text_guards(source_rows)
    rows = [
        _adjudicate_row(row, decisions=decisions)
        for row in sorted(source_rows, key=lambda item: item["review_id"])
    ]
    review_ids = [row["review_id"] for row in rows]
    if tuple(review_ids) != EXPECTED_REVIEW_IDS:
        raise ValueError(f"unexpected review ids: {review_ids}")

    accepted_train_only = sum(1 for row in rows if row["human_should_enter_train_only"] == "yes_train_only")
    needs_edit = sum(1 for row in rows if row["human_task_text_faithful"] == "needs_edit")
    rejected = sum(1 for row in rows if row["human_should_enter_train_only"] == "no")
    training_admission = (
        "not_granted_pending_needs_edit_resolution"
        if needs_edit
        else "not_granted_pending_train_only_export_gate"
    )
    next_gate = (
        "resolve needs_edit rows before any train-only export gate"
        if needs_edit
        else "export accepted train-only subset only after schema and lineage gate"
    )
    summary = {
        "schema": "gis_recommend.gee_p2_rewrite_review_packet_adjudicated.v1",
        "inputs": {"review_packet": str(Path(review_packet_jsonl_path))},
        "decision_version": decision_version,
        "counts": {
            "rows": len(rows),
            "adjudicated_rows": len(rows),
            "accepted_train_only": accepted_train_only,
            "needs_edit": needs_edit,
            "rejected": rejected,
            "pending_human_review": 0,
        },
        "decision": {
            "training_admission": training_admission,
            "validation_eligible": False,
            "test_eligible": False,
            "next_gate": next_gate,
        },
        "row_decision_policy": {
            "human_task_text_faithful": "yes | needs_edit | no",
            "human_known_omissions_correct": "yes | needs_edit | no",
            "human_should_enter_train_only": "yes_train_only | needs_edit | no",
        },
    }
    return AdjudicationResult(rows=rows, summary=summary)


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=CSV_FIELDS)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: _json_value(row.get(field, "")) for field in CSV_FIELDS})


def _render_report(summary: dict[str, Any], rows: list[dict[str, Any]]) -> str:
    lines = [
        "# GEE P2 Rewrite Human Adjudication",
        "",
        "This sidecar records human review decisions for the deterministic P2 rewrites.",
        "It does not grant validation/test admission.",
        "",
        "## Summary",
        "",
        f"- Rows: {summary['counts']['rows']}",
        f"- Adjudicated rows: {summary['counts']['adjudicated_rows']}",
        f"- Accepted train-only: {summary['counts']['accepted_train_only']}",
        f"- Needs edit: {summary['counts']['needs_edit']}",
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
                f"- Task text faithful: {row['human_task_text_faithful']}",
                f"- Known omissions correct: {row['human_known_omissions_correct']}",
                f"- Should enter train-only: {row['human_should_enter_train_only']}",
                f"- Notes: {row['human_review_notes']}",
                "",
            ]
        )
    return "\n".join(lines)


def write_outputs(
    result: AdjudicationResult,
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
            }
        },
        "artifacts": {
            csv_path.name: {"path": str(csv_path), "sha256": _sha256(csv_path), "bytes": csv_path.stat().st_size},
            jsonl_path.name: {"path": str(jsonl_path), "sha256": _sha256(jsonl_path), "bytes": jsonl_path.stat().st_size},
            summary_path.name: {"path": str(summary_path), "sha256": _sha256(summary_path), "bytes": summary_path.stat().st_size},
            report_path.name: {"path": str(report_path), "sha256": _sha256(report_path), "bytes": report_path.stat().st_size},
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
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_REPORT_DIR)
    parser.add_argument("--decision-version", choices=sorted(DECISIONS_BY_VERSION), default="v1")
    parser.add_argument("--output-prefix", default=OUTPUT_PREFIX)
    args = parser.parse_args(argv)

    result = build_adjudication(
        review_packet_jsonl_path=args.review_packet,
        decision_version=args.decision_version,
    )
    return write_outputs(result, args.output_dir, output_prefix=args.output_prefix)


if __name__ == "__main__":
    main()
