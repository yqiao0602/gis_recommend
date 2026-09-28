#!/usr/bin/env python3
"""Export P4 L3-ready GEE rows as a train-only candidate package.

This gate consumes `gee_p4_l3_canonicalization_gate_24_v1.jsonl` and exports
only rows whose deterministic canonicalization status is `l3_ready`. It does
not create validation/test rows, does not merge into `outputs_v2`, and does not
start training.
"""

from __future__ import annotations

import argparse
import csv
from collections import Counter
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from gis_recommend.data.gee_raster_core_schema import (  # noqa: E402
    SCHEMA as TRAIN_ROW_SCHEMA,
    validate_core_train_row,
)
from scripts.audit_gee_training_admission import _atomic_write_text  # noqa: E402


DEFAULT_REPORT_DIR = ROOT / "docs/reports/gee_raster_core_v1_review_split_2026-07-24"
DEFAULT_P4_GATE = DEFAULT_REPORT_DIR / "gee_p4_l3_canonicalization_gate_24_v1.jsonl"
OUTPUT_PREFIX = "gee_p4_l3_ready_train_only_18_v1"


CSV_FIELDS = (
    "schema",
    "review_id",
    "script_id",
    "source_platform",
    "target_platform",
    "training_scope",
    "task_name",
    "task_description",
    "l3_sequence",
    "operator_sequence",
    "source_sha256",
    "source_path",
    "evidence_snippet",
    "admission_tier",
    "sample_weight",
    "validation_eligible",
    "test_eligible",
    "description_policy",
    "known_omissions",
    "review_split",
    "p4_source_bucket",
)


@dataclass(frozen=True)
class P4ExportResult:
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
                raise ValueError(f"{path}:{line_number} must contain a JSON object")
            rows.append(row)
    if not rows:
        raise ValueError(f"{path} contains no rows")
    return rows


def _known_omissions(value: Any) -> list[str]:
    if value is None or value == "":
        return []
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, str):
        stripped = value.strip()
        return [stripped] if stripped else []
    return [str(value).strip()] if str(value).strip() else []


def _description_policy(source_bucket: str) -> str:
    if source_bucket == "p4_rewritten_needs_edit":
        return "rewritten_chain_faithful"
    return "manual_chain_faithful"


def _train_row_from_gate(row: dict[str, Any]) -> dict[str, Any]:
    review_id = str(row.get("review_id") or "")
    if row.get("canonicalization_status") != "l3_ready":
        raise ValueError(f"cannot export non-l3-ready row {review_id}")
    train_row = {
        "schema": TRAIN_ROW_SCHEMA,
        "review_id": review_id,
        "script_id": row.get("script_id", ""),
        "source_platform": "GEE",
        "target_platform": "L3",
        "training_scope": "core_subworkflow",
        "task_name": row.get("task_name", ""),
        "task_description": row.get("task_description", ""),
        "l3_sequence": list(row.get("l3_sequence") or []),
        "operator_sequence": list(row.get("canonical_operator_sequence") or []),
        "source_sha256": row.get("source_sha256", ""),
        "source_path": row.get("source_path", ""),
        "evidence_snippet": row.get("evidence_snippet", ""),
        "admission_tier": "gee_core_p4_reviewed",
        "sample_weight": 0.5,
        "validation_eligible": False,
        "test_eligible": False,
        "description_policy": _description_policy(str(row.get("source_bucket") or "")),
        "known_omissions": _known_omissions(row.get("known_omissions")),
        "review_split": "train",
        "p4_source_bucket": row.get("source_bucket", ""),
    }
    validate_core_train_row(train_row)
    return train_row


def _assert_unique(rows: list[dict[str, Any]]) -> None:
    review_counts = Counter(row["review_id"] for row in rows)
    duplicated_reviews = sorted(review_id for review_id, count in review_counts.items() if count > 1)
    if duplicated_reviews:
        raise ValueError(f"duplicate exported review IDs: {duplicated_reviews}")
    source_counts = Counter(row["source_sha256"] for row in rows)
    duplicated_sources = sorted(source_sha for source_sha, count in source_counts.items() if count > 1)
    if duplicated_sources:
        raise ValueError(f"duplicate exported source SHA256 values: {duplicated_sources}")


def build_p4_l3_ready_train_only_export(*, p4_gate_jsonl_path: Path) -> P4ExportResult:
    gate_rows = _load_jsonl(p4_gate_jsonl_path)
    status_counts = Counter(str(row.get("canonicalization_status") or "") for row in gate_rows)
    ready_rows = [
        row for row in gate_rows if row.get("canonicalization_status") == "l3_ready"
    ]
    if not ready_rows:
        raise ValueError("P4 gate has no l3_ready rows")
    rows = [_train_row_from_gate(row) for row in sorted(ready_rows, key=lambda item: item["review_id"])]
    _assert_unique(rows)

    source_bucket_counts = Counter(row["p4_source_bucket"] for row in rows)
    l3_lengths = [len(row["l3_sequence"]) for row in rows]
    summary = {
        "schema": "gis_recommend.gee_p4_l3_ready_train_only_export.v1",
        "inputs": {
            "p4_gate": str(Path(p4_gate_jsonl_path)),
        },
        "counts": {
            "input_gate_rows": len(gate_rows),
            "exported_rows": len(rows),
            "source_status_counts": dict(sorted(status_counts.items())),
            "source_bucket_counts": dict(sorted(source_bucket_counts.items())),
            "unique_review_ids": len({row["review_id"] for row in rows}),
            "unique_source_sha256": len({row["source_sha256"] for row in rows}),
            "unique_l3_sequences": len({tuple(row["l3_sequence"]) for row in rows}),
            "unique_operator_sequences": len({tuple(row["operator_sequence"]) for row in rows}),
            "min_l3_length": min(l3_lengths),
            "max_l3_length": max(l3_lengths),
        },
        "review_ids": [row["review_id"] for row in rows],
        "decision": {
            "training_admission": "not_granted_train_only_export_gate_passed",
            "production_merge": "not_granted",
            "validation_eligible": False,
            "test_eligible": False,
            "training_run_started": False,
            "next_gate": "manual manifest review before combining with other GEE/QGIS train-only packages",
        },
        "policy": {
            "source_platform": "GEE",
            "target_platform": "L3",
            "training_scope": "core_subworkflow",
            "sample_weight": 0.5,
            "force_review_split": "train",
            "exclude_from_qgis_operator_chain_gold": True,
            "llm_used": False,
        },
    }
    return P4ExportResult(rows=rows, summary=summary)


def _jsonl_text(rows: list[dict[str, Any]]) -> str:
    return "".join(
        json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"
        for row in rows
    )


def _csv_value(value: Any) -> Any:
    if isinstance(value, (list, dict)):
        return json.dumps(value, ensure_ascii=False, sort_keys=True)
    return value


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=CSV_FIELDS)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: _csv_value(row.get(field, "")) for field in CSV_FIELDS})


def _sha256(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _render_report(summary: dict[str, Any]) -> str:
    lines = [
        "# GEE P4 L3-ready Train-only Export",
        "",
        "This package exports only P4 rows that passed deterministic operator-to-L3 canonicalization.",
        "It remains train-only candidate data: no validation/test rows, no production merge, and no training run.",
        "",
        "## Summary",
        "",
        f"- Input gate rows: {summary['counts']['input_gate_rows']}",
        f"- Exported rows: {summary['counts']['exported_rows']}",
        f"- Source status counts: `{summary['counts']['source_status_counts']}`",
        f"- Source bucket counts: `{summary['counts']['source_bucket_counts']}`",
        f"- Unique source SHA256 values: {summary['counts']['unique_source_sha256']}",
        f"- Unique L3 sequences: {summary['counts']['unique_l3_sequences']}",
        f"- Training admission: `{summary['decision']['training_admission']}`",
        f"- Production merge: `{summary['decision']['production_merge']}`",
        f"- Validation eligible: `{summary['decision']['validation_eligible']}`",
        f"- Test eligible: `{summary['decision']['test_eligible']}`",
        "",
        "## Included review IDs",
        "",
    ]
    for review_id in summary["review_ids"]:
        lines.append(f"- `{review_id}`")
    lines.extend(
        [
            "",
            "## Boundary",
            "",
            "- `source_platform=GEE`",
            "- `target_platform=L3`",
            "- `training_scope=core_subworkflow`",
            "- `sample_weight=0.5`",
            "- `validation_eligible=false`, `test_eligible=false`",
            "- Not QGIS operator-chain gold.",
            "",
        ]
    )
    return "\n".join(lines)


def write_outputs(
    result: P4ExportResult,
    output_dir: Path,
    *,
    output_prefix: str = OUTPUT_PREFIX,
) -> dict[str, Path]:
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    jsonl_path = output_dir / f"{output_prefix}.jsonl"
    csv_path = output_dir / f"{output_prefix}.csv"
    summary_path = output_dir / f"{output_prefix}_summary.json"
    report_path = output_dir / f"{output_prefix}_report.md"
    hash_ledger_path = output_dir / f"{output_prefix}_hash_ledger.json"

    _atomic_write_text(jsonl_path, _jsonl_text(result.rows))
    _write_csv(csv_path, result.rows)
    _atomic_write_text(summary_path, json.dumps(result.summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
    _atomic_write_text(report_path, _render_report(result.summary))
    ledger = {
        "schema": "gis_recommend.hash_ledger.v1",
        "source_inputs": {
            "p4_gate": {
                "path": result.summary["inputs"]["p4_gate"],
                "sha256": _sha256(Path(result.summary["inputs"]["p4_gate"])),
            }
        },
        "artifacts": {
            path.name: {
                "path": str(path),
                "sha256": _sha256(path),
                "bytes": path.stat().st_size,
            }
            for path in (jsonl_path, csv_path, summary_path, report_path)
        },
    }
    _atomic_write_text(hash_ledger_path, json.dumps(ledger, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
    return {
        "jsonl": jsonl_path,
        "csv": csv_path,
        "summary": summary_path,
        "report": report_path,
        "hash_ledger": hash_ledger_path,
    }


def main(argv: list[str] | None = None) -> dict[str, Path]:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--p4-gate", type=Path, default=DEFAULT_P4_GATE)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_REPORT_DIR)
    parser.add_argument("--output-prefix", default=OUTPUT_PREFIX)
    args = parser.parse_args(argv)
    result = build_p4_l3_ready_train_only_export(p4_gate_jsonl_path=args.p4_gate)
    return write_outputs(result, args.output_dir, output_prefix=args.output_prefix)


if __name__ == "__main__":
    main()
