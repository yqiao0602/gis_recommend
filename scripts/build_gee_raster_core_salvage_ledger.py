#!/usr/bin/env python3
"""Build a salvage ledger for the 50-row GEE raster-core adjudication.

This is a read-only classification pass. It does not regenerate GEE source
artifacts, does not train models, and does not modify the original review
packages.
"""

from __future__ import annotations

import argparse
from collections import Counter
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
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from scripts.audit_gee_training_admission import _atomic_write_text  # noqa: E402


DEFAULT_REVIEW_CSV = (
    ROOT
    / "docs/reports/gee_raster_core_v1_review_split_2026-07-24/adjudicated_review_50_v1.csv"
)
DEFAULT_OUTPUT_DIR = (
    ROOT / "docs/reports/gee_raster_core_v1_review_split_2026-07-24"
)

BUCKET_ORDER = (
    "accept_core_now",
    "rewrite_description_then_train",
    "extractor_repair_required",
    "taxonomy_or_mapping_gap",
    "reject",
)

ACCEPT_IDS = {
    "gee_raster_core_review_001",
    "gee_raster_core_review_008",
    "gee_raster_core_review_011",
    "gee_raster_core_review_017",
    "gee_raster_core_review_023",
    "gee_raster_core_review_036",
    "gee_raster_core_review_037",
    "gee_raster_core_review_041",
    "gee_raster_core_review_043",
}

REWRITE_IDS = {
    "gee_raster_core_review_002",
    "gee_raster_core_review_003",
    "gee_raster_core_review_015",
    "gee_raster_core_review_016",
    "gee_raster_core_review_019",
    "gee_raster_core_review_025",
    "gee_raster_core_review_032",
    "gee_raster_core_review_048",
}

TAXONOMY_IDS = {
    "gee_raster_core_review_013",
    "gee_raster_core_review_024",
    "gee_raster_core_review_039",
}

REJECT_IDS = {
    "gee_raster_core_review_028",
    "gee_raster_core_review_040",
}

NEXT_STEP_BY_BUCKET = {
    "accept_core_now": "direct_train_only",
    "rewrite_description_then_train": "rewrite_description_then_review",
    "extractor_repair_required": "repair_extractor_then_review",
    "taxonomy_or_mapping_gap": "repair_taxonomy_then_review",
    "reject": "drop_or_research_later",
}

TRAIN_CANDIDATE_AFTER_FOLLOWUP = {
    "accept_core_now": True,
    "rewrite_description_then_train": True,
    "extractor_repair_required": True,
    "taxonomy_or_mapping_gap": True,
    "reject": False,
}

FIELD_ORDER = [
    "review_id",
    "split",
    "script_id",
    "source_sha256",
    "source_path",
    "task_type",
    "task_name",
    "task_description",
    "l3_length",
    "l3_sequence_hash",
    "l3_codes_json",
    "operator_sequence_json",
    "sample_weight",
    "human_task_text_faithful_to_core_chain",
    "human_l3_chain_correct",
    "human_chain_complete_for_task",
    "human_should_enter_training",
    "human_reviewer_notes",
    "salvage_bucket",
    "salvage_next_step",
    "salvage_reason",
    "salvage_train_candidate_after_followup",
    "salvage_confidence",
]


@dataclass(slots=True)
class SalvageLedgerResult:
    report: dict[str, Any]
    rows: list[dict[str, Any]]


def _load_csv(path: Path) -> list[dict[str, Any]]:
    with Path(path).open(encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    if not rows:
        raise ValueError(f"{path} contains no rows")
    return rows


def _sha256(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _bucket_for_review_id(review_id: str) -> str:
    if review_id in ACCEPT_IDS:
        return "accept_core_now"
    if review_id in REWRITE_IDS:
        return "rewrite_description_then_train"
    if review_id in TAXONOMY_IDS:
        return "taxonomy_or_mapping_gap"
    if review_id in REJECT_IDS:
        return "reject"
    return "extractor_repair_required"


def _normalize_note(note: str, bucket: str) -> str:
    text = " ".join((note or "").split())
    if bucket == "accept_core_now":
        text = text.removeprefix("Accept as train-only raster/L3 semantics candidate. ").strip()
    else:
        text = text.removeprefix("Defer. ").strip()
    return text


def _confidence_for_bucket(bucket: str) -> str:
    return {
        "accept_core_now": "high",
        "rewrite_description_then_train": "medium_high",
        "extractor_repair_required": "medium",
        "taxonomy_or_mapping_gap": "medium",
        "reject": "low",
    }[bucket]


def _classify_row(row: dict[str, Any]) -> dict[str, Any]:
    review_id = str(row.get("review_id") or "").strip()
    if not review_id:
        raise ValueError("missing review_id")
    bucket = _bucket_for_review_id(review_id)
    note = str(row.get("human_reviewer_notes") or "")
    return {
        **row,
        "salvage_bucket": bucket,
        "salvage_next_step": NEXT_STEP_BY_BUCKET[bucket],
        "salvage_reason": _normalize_note(note, bucket),
        "salvage_train_candidate_after_followup": TRAIN_CANDIDATE_AFTER_FOLLOWUP[bucket],
        "salvage_confidence": _confidence_for_bucket(bucket),
    }


def _jsonl_text(rows: list[dict[str, Any]]) -> str:
    return "".join(
        json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"
        for row in rows
    )


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELD_ORDER)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in FIELD_ORDER})


def _render_markdown(report: dict[str, Any]) -> str:
    counts = report["counts"]
    lines = [
        "# GEE Raster Core Salvage Ledger",
        "",
        "P0 salvage classification for the 50-row adjudicated GEE raster-core pack.",
        "This remains train-only planning material and does not grant validation/test admission.",
        "",
        "## Summary",
        "",
        f"- Rows: {counts['rows']:,}",
        f"- Accepted core-now: {counts['salvage_buckets']['accept_core_now']:,}",
        f"- Rewrite-needed: {counts['salvage_buckets']['rewrite_description_then_train']:,}",
        f"- Extractor-repair: {counts['salvage_buckets']['extractor_repair_required']:,}",
        f"- Taxonomy/mapping gap: {counts['salvage_buckets']['taxonomy_or_mapping_gap']:,}",
        f"- Reject: {counts['salvage_buckets']['reject']:,}",
        "",
        "## Decision",
        "",
        f"- Training admission: `{report['decision']['training_admission']}`",
        f"- Validation eligible: `{report['decision']['validation_eligible']}`",
        f"- Test eligible: `{report['decision']['test_eligible']}`",
        f"- Next gate: {report['decision']['next_gate']}",
        "",
        "## Bucket IDs",
        "",
    ]
    for bucket in BUCKET_ORDER:
        lines.append(f"### {bucket}")
        for review_id in report["bucket_review_ids"][bucket]:
            lines.append(f"- `{review_id}`")
        if not report["bucket_review_ids"][bucket]:
            lines.append("- None")
        lines.append("")
    return "\n".join(lines)


def build_salvage_ledger(
    *,
    review_csv_path: Path,
    output_dir: Path,
) -> SalvageLedgerResult:
    rows_in = _load_csv(review_csv_path)
    rows = [_classify_row(row) for row in rows_in]
    bucket_counts = Counter(row["salvage_bucket"] for row in rows)
    next_step_counts = Counter(row["salvage_next_step"] for row in rows)
    human_counts = Counter(row["human_should_enter_training"] for row in rows)
    bucket_review_ids = {
        bucket: [row["review_id"] for row in rows if row["salvage_bucket"] == bucket]
        for bucket in BUCKET_ORDER
    }
    report = {
        "schema": "gis_recommend.gee_raster_core_salvage_ledger.v1",
        "inputs": {
            "review_csv": str(Path(review_csv_path)),
        },
        "salvage_buckets": {bucket: bucket_counts[bucket] for bucket in BUCKET_ORDER},
        "counts": {
            "rows": len(rows),
            "human_should_enter_training": dict(sorted(human_counts.items())),
            "salvage_buckets": {bucket: bucket_counts[bucket] for bucket in BUCKET_ORDER},
            "salvage_next_steps": dict(sorted(next_step_counts.items())),
            "train_candidate_after_followup": sum(
                bool(row["salvage_train_candidate_after_followup"]) for row in rows
            ),
            "direct_train_only": bucket_counts["accept_core_now"],
        },
        "bucket_review_ids": bucket_review_ids,
        "decision": {
            "training_admission": "not_granted",
            "validation_eligible": False,
            "test_eligible": False,
            "next_gate": "P1 schema definition and chain-faithful description rewrite",
        },
    }
    return SalvageLedgerResult(report=report, rows=rows)


def write_outputs(result: SalvageLedgerResult, output_dir: Path) -> dict[str, Path]:
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    csv_path = output_dir / "gee_salvage_50_v1.csv"
    jsonl_path = output_dir / "gee_salvage_50_v1.jsonl"
    report_json = output_dir / "gee_salvage_50_summary_v1.json"
    report_md = output_dir / "gee_salvage_50_report_v1.md"
    hash_ledger = output_dir / "gee_salvage_50_hash_ledger_v1.json"

    _write_csv(csv_path, result.rows)
    _atomic_write_text(report_json, json.dumps(result.report, ensure_ascii=False, indent=2, sort_keys=True))
    _atomic_write_text(report_md, _render_markdown(result.report))
    _atomic_write_text(jsonl_path, _jsonl_text(result.rows))

    ledger = {
        "schema": "gis_recommend.hash_ledger.v1",
        "source_inputs": {
            "csv": {
                "path": result.report["inputs"]["review_csv"],
                "sha256": _sha256(Path(result.report["inputs"]["review_csv"])),
            }
        },
        "artifacts": {
            "gee_salvage_50_v1.csv": {"path": str(csv_path), "sha256": _sha256(csv_path), "bytes": csv_path.stat().st_size},
            "gee_salvage_50_v1.jsonl": {"path": str(jsonl_path), "sha256": _sha256(jsonl_path), "bytes": jsonl_path.stat().st_size},
            "gee_salvage_50_summary_v1.json": {"path": str(report_json), "sha256": _sha256(report_json), "bytes": report_json.stat().st_size},
            "gee_salvage_50_report_v1.md": {"path": str(report_md), "sha256": _sha256(report_md), "bytes": report_md.stat().st_size},
        },
    }
    _atomic_write_text(hash_ledger, json.dumps(ledger, ensure_ascii=False, indent=2, sort_keys=True))
    return {
        "csv": csv_path,
        "jsonl": jsonl_path,
        "report_json": report_json,
        "report_md": report_md,
        "hash_ledger": hash_ledger,
    }


def main(argv: list[str] | None = None) -> dict[str, Path]:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--review-csv", type=Path, default=DEFAULT_REVIEW_CSV)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    args = parser.parse_args(argv)

    result = build_salvage_ledger(
        review_csv_path=args.review_csv,
        output_dir=args.output_dir,
    )
    return write_outputs(result, args.output_dir)


if __name__ == "__main__":
    main()
