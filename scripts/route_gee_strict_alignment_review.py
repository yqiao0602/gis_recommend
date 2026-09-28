#!/usr/bin/env python3
"""Route strict GEE alignment candidates to scalable conversion actions.

This technical source-review sidecar does not populate human adjudication
fields, emit training rows, or grant dataset admission.
"""

from __future__ import annotations

import argparse
from collections import Counter
import csv
from dataclasses import dataclass
import hashlib
import io
import json
import os
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.build_gee_strict_candidate_source_audit import (  # noqa: E402
    _atomic_write,
    _filesystem_path,
)


DEFAULT_AUTHORITY_DIR = ROOT / (
    "docs/reports/gee_raster_core_v1_review_split_2026-07-24/"
    "gee_raster_core_batch_training_package_v1/strict_candidate_v1/"
    "source_audit_60_v1/authority_v2_2_0"
)
DEFAULT_REVIEW = DEFAULT_AUTHORITY_DIR / "strict_candidate_alignment_review_8_v1.jsonl"
DEFAULT_OUTPUT_DIR = DEFAULT_AUTHORITY_DIR / "alignment_routing_v1"
OUTPUT_PREFIX = "strict_candidate_alignment_routing_8_v1"
AUTHORITY_VERSION = "gee-source-extractor-v2.2.0"


DECISIONS_V1: dict[str, dict[str, str]] = {
    "gee_raster_core_batch_v1_84e0bd4763548dc7": {
        "chain_verdict": "incomplete_minimal_window",
        "task_text_verdict": "describes_repeated_selects_outside_window",
        "routing_decision": "expand_dataflow_slice",
        "notes": "Expand the toBands result through all five indexed select branches before text admission.",
    },
    "gee_raster_core_batch_v1_664c6ffd8611c003": {
        "chain_verdict": "incomplete_minimal_window",
        "task_text_verdict": "describes_power_beam_filter_outside_window",
        "routing_decision": "expand_dataflow_slice",
        "notes": "Follow qa into the only_power callback and summed beam mask; the current window stops after QA masking.",
    },
    "gee_raster_core_batch_v1_4b2938ceff59b1f4": {
        "chain_verdict": "invalid_input_type",
        "task_text_verdict": "not_executable_as_written",
        "routing_decision": "reject_current_chain",
        "notes": "CannyEdgeDetector receives an ImageCollection without a source-proven image aggregation step.",
    },
    "gee_raster_core_batch_v1_96be4fed0ff1d92e": {
        "chain_verdict": "complete_rebuilt",
        "task_text_verdict": "faithful",
        "routing_decision": "accept_rebuilt_pending_export_gate",
        "notes": "The rebuilt chain restores the source-backed gte(50) threshold before Gaussian convolution.",
    },
    "gee_raster_core_batch_v1_a68342ccee735753": {
        "chain_verdict": "complete_rebuilt",
        "task_text_verdict": "needs_dataset_name_rewrite",
        "routing_decision": "rewrite_task_text_then_export_gate",
        "notes": "The chain is complete, but COPERNICUS/S2 must not be described as surface reflectance.",
    },
    "gee_raster_core_batch_v1_36b71985a82a3093": {
        "chain_verdict": "incomplete_minimal_window",
        "task_text_verdict": "describes_three_index_branches",
        "routing_decision": "expand_dataflow_slice",
        "notes": "Recover NDVI, NDWI, NBR and both addBands joins; the current window covers only the first index branch.",
    },
    "gee_raster_core_batch_v1_d53846c796134974": {
        "chain_verdict": "incomplete_minimal_window",
        "task_text_verdict": "describes_three_index_branches",
        "routing_decision": "expand_dataflow_slice",
        "notes": "Recover NDVI, NDWI, NBR and both addBands joins, then deduplicate against the normalized sibling workflow.",
    },
    "gee_raster_core_batch_v1_5ed2feb7f9e92056": {
        "chain_verdict": "oversized_parallel_window",
        "task_text_verdict": "broadly_faithful_but_not_single_chain",
        "routing_decision": "split_repeated_subworkflows",
        "notes": "Split by land-cover, polarization, and year branches; a 139-operator linearized window is not a usable single workflow label.",
    },
}


@dataclass(slots=True)
class AlignmentRoutingResult:
    rows: list[dict[str, Any]]
    summary: dict[str, Any]


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with open(_filesystem_path(Path(path)), encoding="utf-8") as handle:
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


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with open(_filesystem_path(Path(path)), "rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _jsonl_text(rows: list[dict[str, Any]]) -> str:
    return "".join(
        json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"
        for row in rows
    )


def build_alignment_routing(
    *,
    review_jsonl_path: Path,
    decisions: dict[str, dict[str, str]] = DECISIONS_V1,
    authority_version: str = AUTHORITY_VERSION,
) -> AlignmentRoutingResult:
    source_rows = _load_jsonl(review_jsonl_path)
    sample_ids = [str(row.get("sample_id") or "") for row in source_rows]
    if "" in sample_ids or len(set(sample_ids)) != len(sample_ids):
        raise ValueError("review packet must contain unique non-empty sample_id values")
    missing = sorted(set(sample_ids) - set(decisions))
    unknown = sorted(set(decisions) - set(sample_ids))
    if missing or unknown:
        raise ValueError(f"decision coverage mismatch: missing={missing}, unknown={unknown}")

    rows: list[dict[str, Any]] = []
    for source_row in sorted(source_rows, key=lambda row: int(row.get("audit_rank", 0))):
        decision = decisions[str(source_row["sample_id"])]
        row = dict(source_row)
        row.update(
            {
                "source_review_status": "routed",
                "source_review_basis": "source_and_alignment_evidence_v1",
                "source_review_authority_version": authority_version,
                "source_review_chain_verdict": decision["chain_verdict"],
                "source_review_task_text_verdict": decision["task_text_verdict"],
                "routing_decision": decision["routing_decision"],
                "source_review_notes": decision["notes"],
                "training_admission": "not_granted_alignment_routing",
                "validation_eligible": False,
                "test_eligible": False,
                "production_merge": "not_granted",
                "training_rows_emitted": 0,
            }
        )
        rows.append(row)

    counts = Counter(str(row["routing_decision"]) for row in rows)
    summary = {
        "schema": "gis_recommend.gee_strict_candidate_alignment_routing.v1",
        "inputs": {
            "review_jsonl": str(Path(review_jsonl_path)),
            "review_jsonl_sha256": _sha256(Path(review_jsonl_path)),
        },
        "authority_version": authority_version,
        "counts": {"rows": len(rows), "training_rows_emitted": 0},
        "routing_decision_counts": dict(sorted(counts.items())),
        "decision": {
            "training_admission": "not_granted",
            "validation_eligible": False,
            "test_eligible": False,
            "production_merge": "not_granted",
            "training_rows_emitted": 0,
            "human_adjudication_fields_mutated": False,
            "next_gate": "implement and calibrate dataflow expansion, repeated-subworkflow splitting, and task-text rewrite routes",
        },
    }
    return AlignmentRoutingResult(rows=rows, summary=summary)


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
    output = io.StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=fields)
    writer.writeheader()
    for row in rows:
        writer.writerow({field: _csv_value(row.get(field, "")) for field in fields})
    _atomic_write(path, output.getvalue())


def _render_report(summary: dict[str, Any], rows: list[dict[str, Any]]) -> str:
    lines = [
        "# GEE Strict Alignment Routing v1",
        "",
        "Technical source-review routing only. Human adjudication fields remain unchanged and no training rows are emitted.",
        "",
        "## Counts",
        "",
    ]
    for decision, count in summary["routing_decision_counts"].items():
        lines.append(f"- {decision}: {count}")
    lines.extend(["", "## Rows", ""])
    for row in rows:
        lines.extend(
            [
                f"### Rank {row['audit_rank']}: {row.get('task_name', row['sample_id'])}",
                "",
                f"- Route: `{row['routing_decision']}`",
                f"- Chain: `{row['source_review_chain_verdict']}`",
                f"- Task text: `{row['source_review_task_text_verdict']}`",
                f"- Notes: {row['source_review_notes']}",
                "",
            ]
        )
    return "\n".join(lines)


def write_outputs(
    result: AlignmentRoutingResult,
    output_dir: Path,
    *,
    output_prefix: str = OUTPUT_PREFIX,
) -> dict[str, Path]:
    output_dir = Path(output_dir)
    paths = {
        "csv": output_dir / f"{output_prefix}.csv",
        "jsonl": output_dir / f"{output_prefix}.jsonl",
        "summary": output_dir / f"{output_prefix}_summary.json",
        "report": output_dir / f"{output_prefix}_report.md",
        "hash_ledger": output_dir / f"{output_prefix}_hash_ledger.json",
    }
    _write_csv(paths["csv"], result.rows)
    _atomic_write(paths["jsonl"], _jsonl_text(result.rows))
    _atomic_write(paths["summary"], json.dumps(result.summary, ensure_ascii=False, indent=2, sort_keys=True))
    _atomic_write(paths["report"], _render_report(result.summary, result.rows))
    ledger = {
        "schema": "gis_recommend.hash_ledger.v1",
        "source_inputs": {
            "review_jsonl": {
                "path": result.summary["inputs"]["review_jsonl"],
                "sha256": result.summary["inputs"]["review_jsonl_sha256"],
            }
        },
        "artifacts": {
            path.name: {
                "path": str(path),
                "sha256": _sha256(path),
                "bytes": os.path.getsize(_filesystem_path(path)),
            }
            for key, path in paths.items()
            if key != "hash_ledger"
        },
    }
    _atomic_write(paths["hash_ledger"], json.dumps(ledger, ensure_ascii=False, indent=2, sort_keys=True))
    return paths


def main(argv: list[str] | None = None) -> dict[str, Path]:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--review-jsonl", type=Path, default=DEFAULT_REVIEW)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--output-prefix", default=OUTPUT_PREFIX)
    args = parser.parse_args(argv)
    result = build_alignment_routing(review_jsonl_path=args.review_jsonl)
    return write_outputs(result, args.output_dir, output_prefix=args.output_prefix)


if __name__ == "__main__":
    main()
