#!/usr/bin/env python3
"""Export accepted GEE raster-core rows as a train-only candidate package.

This gate combines only the nine P0 `accept_core_now` rows and the eight P2 v2
`yes_train_only` rewrite rows. It does not call an LLM, does not create
validation/test rows, does not merge into outputs_v2, and does not run training.
"""

from __future__ import annotations

import argparse
from collections import Counter
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
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from gis_recommend.data.gee_raster_core_schema import (  # noqa: E402
    SCHEMA as TRAIN_ROW_SCHEMA,
    validate_core_train_row,
)
from scripts.audit_gee_training_admission import _atomic_write_text  # noqa: E402


DEFAULT_REPORT_DIR = ROOT / "docs/reports/gee_raster_core_v1_review_split_2026-07-24"
DEFAULT_SALVAGE_CSV = DEFAULT_REPORT_DIR / "gee_salvage_50_v1.csv"
DEFAULT_SOURCE_SNIPPETS = DEFAULT_REPORT_DIR / "source_evidence_snippets.jsonl"
DEFAULT_P2_TRAIN_ROWS = DEFAULT_REPORT_DIR / "gee_p2_rewrite_8_v2_train_rows.jsonl"
DEFAULT_P2_ADJUDICATION = (
    DEFAULT_REPORT_DIR / "gee_p2_rewrite_8_review_packet_adjudicated_v2.jsonl"
)
OUTPUT_PREFIX = "gee_raster_core_accepted_train_only_17_v1"

P0_ACCEPT_BUCKET = "accept_core_now"
P2_ACCEPT_DECISION = "yes_train_only"
EXPECTED_P0_ACCEPT_COUNT = 9
EXPECTED_P2_ACCEPT_COUNT = 8
EXPECTED_TOTAL_COUNT = 17

CSV_FIELDS = [
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
]


@dataclass(frozen=True)
class ExportResult:
    rows: list[dict[str, Any]]
    summary: dict[str, Any]


def _sha256(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _load_csv(path: Path) -> list[dict[str, str]]:
    with Path(path).open(encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    if not rows:
        raise ValueError(f"{path} contains no rows")
    return rows


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with Path(path).open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            record = json.loads(line)
            if not isinstance(record, dict):
                raise ValueError(f"{path}:{line_number} must contain a JSON object")
            rows.append(record)
    if not rows:
        raise ValueError(f"{path} contains no rows")
    return rows


def _json_string_list(value: str, *, field: str, review_id: str) -> list[str]:
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError as exc:
        raise ValueError(f"invalid {field} JSON for {review_id}: {exc}") from exc
    if not isinstance(parsed, list) or any(not isinstance(item, str) for item in parsed):
        raise ValueError(f"{field} must be a JSON string list for {review_id}")
    return parsed


def _load_snippets(path: Path) -> dict[str, str]:
    snippets: dict[str, str] = {}
    for line_number, record in enumerate(_load_jsonl(path), start=1):
        review_id = str(record.get("review_id") or "")
        evidence_lines = record.get("evidence_lines") or []
        if not review_id:
            raise ValueError(f"missing review_id in snippets line {line_number}")
        if not isinstance(evidence_lines, list):
            raise ValueError(f"evidence_lines must be a list for {review_id}")
        snippet = "\n".join(
            f"{item.get('line')}: {item.get('text')}"
            for item in evidence_lines[:12]
            if isinstance(item, dict)
        ).strip()
        snippets[review_id] = snippet
    return snippets


def _p0_train_row_from_salvage(
    salvage_row: dict[str, str],
    *,
    evidence_snippet: str,
) -> dict[str, Any]:
    review_id = salvage_row["review_id"]
    train_row = {
        "schema": TRAIN_ROW_SCHEMA,
        "review_id": review_id,
        "script_id": salvage_row["script_id"],
        "source_platform": "GEE",
        "target_platform": "L3",
        "training_scope": "core_subworkflow",
        "task_name": salvage_row["task_name"],
        "task_description": salvage_row["task_description"],
        "l3_sequence": _json_string_list(
            salvage_row["l3_codes_json"],
            field="l3_codes_json",
            review_id=review_id,
        ),
        "operator_sequence": _json_string_list(
            salvage_row["operator_sequence_json"],
            field="operator_sequence_json",
            review_id=review_id,
        ),
        "source_sha256": salvage_row["source_sha256"],
        "source_path": salvage_row["source_path"],
        "evidence_snippet": evidence_snippet,
        "admission_tier": "gee_core_p0_accept",
        "sample_weight": float(salvage_row.get("sample_weight") or 0.5),
        "validation_eligible": False,
        "test_eligible": False,
        "description_policy": "original_core_faithful",
        "known_omissions": [],
        "review_split": "train",
    }
    validate_core_train_row(train_row)
    return train_row


def _index_unique_by_review_id(rows: list[dict[str, Any]], *, label: str) -> dict[str, dict[str, Any]]:
    indexed: dict[str, dict[str, Any]] = {}
    for row in rows:
        review_id = str(row.get("review_id") or "")
        if not review_id:
            raise ValueError(f"{label} row missing review_id")
        if review_id in indexed:
            raise ValueError(f"duplicate review_id in {label}: {review_id}")
        indexed[review_id] = row
    return indexed


def _validate_p2_v2_adjudication(
    *,
    p2_train_rows: list[dict[str, Any]],
    p2_adjudications: list[dict[str, Any]],
) -> None:
    train_by_id = _index_unique_by_review_id(p2_train_rows, label="P2 train rows")
    adjudication_by_id = _index_unique_by_review_id(p2_adjudications, label="P2 adjudication")
    if set(train_by_id) != set(adjudication_by_id):
        raise ValueError("P2 v2 adjudication review IDs do not match P2 train rows")
    if len(train_by_id) != EXPECTED_P2_ACCEPT_COUNT:
        raise ValueError(
            f"P2 v2 adjudication must cover {EXPECTED_P2_ACCEPT_COUNT} rows; "
            f"got {len(train_by_id)}"
        )
    for review_id, row in adjudication_by_id.items():
        if row.get("review_status") != "adjudicated":
            raise ValueError(f"P2 v2 adjudication row is not adjudicated: {review_id}")
        if row.get("human_should_enter_train_only") != P2_ACCEPT_DECISION:
            raise ValueError(
                "P2 v2 adjudication must contain only yes_train_only rows; "
                f"{review_id} has {row.get('human_should_enter_train_only')!r}"
            )
        if row.get("human_task_text_faithful") != "yes":
            raise ValueError(
                "P2 v2 adjudication must contain only task-text-faithful rows; "
                f"{review_id} has {row.get('human_task_text_faithful')!r}"
            )
        if row.get("human_known_omissions_correct") != "yes":
            raise ValueError(
                "P2 v2 adjudication must contain only rows with correct omissions; "
                f"{review_id} has {row.get('human_known_omissions_correct')!r}"
            )


def _normalize_p2_train_row(row: dict[str, Any]) -> dict[str, Any]:
    normalized = dict(row)
    normalized["schema"] = TRAIN_ROW_SCHEMA
    normalized["source_platform"] = "GEE"
    normalized["target_platform"] = "L3"
    normalized["training_scope"] = "core_subworkflow"
    normalized["admission_tier"] = "gee_core_p2_rewrite"
    normalized["sample_weight"] = float(normalized.get("sample_weight") or 0.5)
    normalized["validation_eligible"] = False
    normalized["test_eligible"] = False
    normalized["description_policy"] = "rewritten_chain_faithful"
    normalized["known_omissions"] = list(normalized.get("known_omissions") or [])
    normalized["review_split"] = "train"
    validate_core_train_row(normalized)
    return normalized


def _assert_unique_export(rows: list[dict[str, Any]]) -> None:
    review_ids = [row["review_id"] for row in rows]
    if len(set(review_ids)) != len(review_ids):
        duplicates = sorted(item for item, count in Counter(review_ids).items() if count > 1)
        raise ValueError(f"duplicate exported review_id values: {duplicates}")
    source_hashes = [row["source_sha256"] for row in rows]
    if len(set(source_hashes)) != len(source_hashes):
        duplicates = sorted(item for item, count in Counter(source_hashes).items() if count > 1)
        raise ValueError(f"duplicate exported source_sha256 values: {duplicates}")


def build_accepted_train_only_export(
    *,
    salvage_csv_path: Path,
    source_snippets_path: Path,
    p2_train_rows_path: Path,
    p2_adjudication_jsonl_path: Path,
) -> ExportResult:
    salvage_rows = _load_csv(salvage_csv_path)
    snippets = _load_snippets(source_snippets_path)
    p2_train_rows = _load_jsonl(p2_train_rows_path)
    p2_adjudications = _load_jsonl(p2_adjudication_jsonl_path)
    _validate_p2_v2_adjudication(
        p2_train_rows=p2_train_rows,
        p2_adjudications=p2_adjudications,
    )

    p0_salvage_rows = [
        row for row in salvage_rows if row.get("salvage_bucket") == P0_ACCEPT_BUCKET
    ]
    if len(p0_salvage_rows) != EXPECTED_P0_ACCEPT_COUNT:
        raise ValueError(
            f"expected {EXPECTED_P0_ACCEPT_COUNT} P0 accept_core_now rows, "
            f"got {len(p0_salvage_rows)}"
        )

    p0_rows: list[dict[str, Any]] = []
    for salvage_row in sorted(p0_salvage_rows, key=lambda item: item["review_id"]):
        review_id = salvage_row["review_id"]
        evidence_snippet = snippets.get(review_id, "")
        if not evidence_snippet:
            raise ValueError(f"missing evidence snippet for {review_id}")
        p0_rows.append(
            _p0_train_row_from_salvage(
                salvage_row,
                evidence_snippet=evidence_snippet,
            )
        )

    p2_rows = [
        _normalize_p2_train_row(row)
        for row in sorted(p2_train_rows, key=lambda item: item["review_id"])
    ]
    rows = [*p0_rows, *p2_rows]
    if len(rows) != EXPECTED_TOTAL_COUNT:
        raise ValueError(f"expected {EXPECTED_TOTAL_COUNT} exported rows, got {len(rows)}")
    _assert_unique_export(rows)

    tier_counts = Counter(row["admission_tier"] for row in rows)
    l3_lengths = [len(row["l3_sequence"]) for row in rows]
    operator_counts = Counter(
        operator
        for row in rows
        for operator in row["operator_sequence"]
    )
    summary = {
        "schema": "gis_recommend.gee_raster_core_accepted_train_only_export.v1",
        "inputs": {
            "salvage_csv": str(Path(salvage_csv_path)),
            "source_snippets": str(Path(source_snippets_path)),
            "p2_train_rows": str(Path(p2_train_rows_path)),
            "p2_adjudication": str(Path(p2_adjudication_jsonl_path)),
        },
        "counts": {
            "p0_accept_rows": tier_counts["gee_core_p0_accept"],
            "p2_v2_accepted_rows": tier_counts["gee_core_p2_rewrite"],
            "exported_rows": len(rows),
            "unique_review_ids": len({row["review_id"] for row in rows}),
            "unique_source_sha256": len({row["source_sha256"] for row in rows}),
            "unique_l3_sequences": len(
                {tuple(row["l3_sequence"]) for row in rows}
            ),
            "unique_operator_sequences": len(
                {tuple(row["operator_sequence"]) for row in rows}
            ),
            "min_l3_length": min(l3_lengths),
            "max_l3_length": max(l3_lengths),
        },
        "review_ids": {
            "p0_accept": [row["review_id"] for row in p0_rows],
            "p2_v2_accepted": [row["review_id"] for row in p2_rows],
            "all": [row["review_id"] for row in rows],
        },
        "top_operators": operator_counts.most_common(20),
        "decision": {
            "training_admission": "not_granted_train_only_export_gate_passed",
            "production_merge": "not_granted",
            "validation_eligible": False,
            "test_eligible": False,
            "llm_called": False,
            "next_gate": "manual manifest review before any training manifest or expansion",
        },
        "policy": {
            "source_platform": "GEE",
            "target_platform": "L3",
            "training_scope": "core_subworkflow",
            "sample_weight_max": 0.5,
            "force_review_split": "train",
            "exclude_from_qgis_operator_chain_gold": True,
        },
    }
    return ExportResult(rows=rows, summary=summary)


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
    if not rows:
        raise ValueError("cannot write empty GEE accepted train-only CSV")
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=CSV_FIELDS)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: _csv_value(row.get(field, "")) for field in CSV_FIELDS})


def _render_report(summary: dict[str, Any]) -> str:
    counts = summary["counts"]
    decision = summary["decision"]
    lines = [
        "# GEE Raster Core Accepted Train-only Export",
        "",
        "This package combines only P0 accepted core rows and P2 v2 accepted",
        "chain-faithful rewrite rows. It remains a candidate export gate: no LLM",
        "was called, no validation/test rows are created, and no training run is",
        "authorized by this artifact.",
        "",
        "## Summary",
        "",
        f"- Exported rows: {counts['exported_rows']}",
        f"- P0 accept rows: {counts['p0_accept_rows']}",
        f"- P2 v2 accepted rows: {counts['p2_v2_accepted_rows']}",
        f"- Unique source SHA256 values: {counts['unique_source_sha256']}",
        f"- Unique L3 sequences: {counts['unique_l3_sequences']}",
        f"- Training admission: `{decision['training_admission']}`",
        f"- Production merge: `{decision['production_merge']}`",
        f"- Validation eligible: `{decision['validation_eligible']}`",
        f"- Test eligible: `{decision['test_eligible']}`",
        "",
        "## Included review IDs",
        "",
        "### P0 accept_core_now",
    ]
    for review_id in summary["review_ids"]["p0_accept"]:
        lines.append(f"- `{review_id}`")
    lines.extend(["", "### P2 v2 yes_train_only"])
    for review_id in summary["review_ids"]["p2_v2_accepted"]:
        lines.append(f"- `{review_id}`")
    lines.extend(
        [
            "",
            "## Boundary",
            "",
            "- `source_platform=GEE`",
            "- `target_platform=L3`",
            "- `training_scope=core_subworkflow`",
            "- `sample_weight <= 0.5`",
            "- `validation_eligible=false`, `test_eligible=false`",
            "- Not QGIS operator-chain gold.",
            "",
        ]
    )
    return "\n".join(lines)


def write_outputs(
    result: ExportResult,
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
    _atomic_write_text(
        summary_path,
        json.dumps(result.summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
    )
    _atomic_write_text(report_path, _render_report(result.summary))

    ledger = {
        "schema": "gis_recommend.hash_ledger.v1",
        "source_inputs": {
            name: {
                "path": path,
                "sha256": _sha256(Path(path)),
            }
            for name, path in sorted(result.summary["inputs"].items())
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
    _atomic_write_text(
        hash_ledger_path,
        json.dumps(ledger, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
    )
    return {
        "jsonl": jsonl_path,
        "csv": csv_path,
        "summary": summary_path,
        "report": report_path,
        "hash_ledger": hash_ledger_path,
    }


def main(argv: list[str] | None = None) -> dict[str, Path]:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--salvage-csv", type=Path, default=DEFAULT_SALVAGE_CSV)
    parser.add_argument("--source-snippets", type=Path, default=DEFAULT_SOURCE_SNIPPETS)
    parser.add_argument("--p2-train-rows", type=Path, default=DEFAULT_P2_TRAIN_ROWS)
    parser.add_argument("--p2-adjudication", type=Path, default=DEFAULT_P2_ADJUDICATION)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_REPORT_DIR)
    parser.add_argument("--output-prefix", default=OUTPUT_PREFIX)
    args = parser.parse_args(argv)

    result = build_accepted_train_only_export(
        salvage_csv_path=args.salvage_csv,
        source_snippets_path=args.source_snippets,
        p2_train_rows_path=args.p2_train_rows,
        p2_adjudication_jsonl_path=args.p2_adjudication,
    )
    return write_outputs(result, args.output_dir, output_prefix=args.output_prefix)


if __name__ == "__main__":
    main()
