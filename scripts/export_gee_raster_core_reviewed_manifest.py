#!/usr/bin/env python3
"""Combine reviewed GEE raster-core train-only packages into one manifest.

This gate combines the existing 17-row accepted package and the newer 18-row
P4 L3-ready package. It also emits a deferred sidecar for P4 rows that still
need operator-to-L3 canonicalization authority. The artifact remains
train-only/manifest-level: it does not create validation/test rows, does not
merge into `outputs_v2`, and does not start training.
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

from gis_recommend.data.gee_raster_core_schema import validate_core_train_row  # noqa: E402
from scripts.audit_gee_training_admission import _atomic_write_text  # noqa: E402


DEFAULT_REPORT_DIR = ROOT / "docs/reports/gee_raster_core_v1_review_split_2026-07-24"
DEFAULT_ACCEPTED_17 = DEFAULT_REPORT_DIR / "gee_raster_core_accepted_train_only_17_v1.jsonl"
DEFAULT_P4_READY_18 = DEFAULT_REPORT_DIR / "gee_p4_l3_ready_train_only_18_v1.jsonl"
DEFAULT_P4_GATE_24 = DEFAULT_REPORT_DIR / "gee_p4_l3_canonicalization_gate_24_v1.jsonl"

MANIFEST_ID = "gee_raster_core_reviewed_train_only_35_v1"
OUTPUT_PREFIX = MANIFEST_ID
ACCEPTED_17_PACKAGE = "gee_raster_core_accepted_train_only_17_v1"
P4_READY_18_PACKAGE = "gee_p4_l3_ready_train_only_18_v1"

MANIFEST_TRAINING_ADMISSION = "not_granted_reviewed_train_only_manifest_gate_passed"
UNRESOLVED_TRAINING_ADMISSION = "not_granted_deferred_mapping_authority_required"

CSV_FIELDS = (
    "schema",
    "manifest_id",
    "manifest_row_index",
    "manifest_split",
    "manifest_training_admission",
    "source_package",
    "source_package_row_index",
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

UNRESOLVED_CSV_FIELDS = (
    "schema",
    "review_id",
    "script_id",
    "source_bucket",
    "canonicalization_status",
    "blocking_reason",
    "unmapped_raw_operators",
    "skipped_raw_operators",
    "quality_flags",
    "task_name",
    "task_description",
    "source_sha256",
    "source_path",
    "evidence_snippet",
    "training_admission",
    "validation_eligible",
    "test_eligible",
    "production_merge",
    "next_action",
)


@dataclass(frozen=True)
class ReviewedManifestResult:
    rows: list[dict[str, Any]]
    unresolved_rows: list[dict[str, Any]]
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


def _sha256(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _as_list(value: Any) -> list[Any]:
    if value is None or value == "":
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, tuple):
        return list(value)
    return [value]


def _as_string_list(value: Any) -> list[str]:
    return [str(item).strip() for item in _as_list(value) if str(item).strip()]


def _validate_train_input_row(row: dict[str, Any], *, package: str) -> None:
    validate_core_train_row(row)
    if row.get("source_platform") != "GEE":
        raise ValueError(f"{package} row must use source_platform=GEE")
    if row.get("target_platform") != "L3":
        raise ValueError(f"{package} row must use target_platform=L3")
    if row.get("training_scope") != "core_subworkflow":
        raise ValueError(f"{package} row must use training_scope=core_subworkflow")
    if row.get("validation_eligible") is not False:
        raise ValueError(f"{package} row must not be validation eligible")
    if row.get("test_eligible") is not False:
        raise ValueError(f"{package} row must not be test eligible")
    if float(row.get("sample_weight") or 0) > 0.5:
        raise ValueError(f"{package} row sample_weight exceeds 0.5")
    if row.get("review_split") != "train":
        raise ValueError(f"{package} row must keep review_split=train")


def _normalize_manifest_row(
    row: dict[str, Any],
    *,
    source_package: str,
    source_package_row_index: int,
    manifest_row_index: int,
) -> dict[str, Any]:
    normalized = dict(row)
    _validate_train_input_row(normalized, package=source_package)
    normalized["manifest_id"] = MANIFEST_ID
    normalized["manifest_row_index"] = manifest_row_index
    normalized["manifest_split"] = "train_only"
    normalized["manifest_training_admission"] = MANIFEST_TRAINING_ADMISSION
    normalized["source_package"] = source_package
    normalized["source_package_row_index"] = source_package_row_index
    normalized["validation_eligible"] = False
    normalized["test_eligible"] = False
    validate_core_train_row(normalized)
    return normalized


def _assert_unique_manifest(rows: list[dict[str, Any]]) -> None:
    for field in ("review_id", "source_sha256"):
        counts = Counter(str(row.get(field) or "") for row in rows)
        duplicated = sorted(value for value, count in counts.items() if count > 1)
        if duplicated:
            raise ValueError(f"duplicate manifest {field} values: {duplicated}")


def _unresolved_sidecar_row(row: dict[str, Any]) -> dict[str, Any]:
    review_id = str(row.get("review_id") or "")
    unmapped = _as_string_list(row.get("unmapped_raw_operators"))
    skipped = _as_string_list(row.get("skipped_raw_operators"))
    quality_flags = _as_string_list(row.get("quality_flags"))
    if not unmapped:
        raise ValueError(f"unresolved P4 row must include unmapped operators: {review_id}")
    return {
        "schema": "gis_recommend.gee_p4_unresolved_sidecar_row.v1",
        "review_id": review_id,
        "script_id": row.get("script_id", ""),
        "source_bucket": row.get("source_bucket", ""),
        "canonicalization_status": "needs_canonicalization_rules",
        "blocking_reason": "operator_to_l3_mapping_authority_missing",
        "unmapped_raw_operators": unmapped,
        "skipped_raw_operators": skipped,
        "quality_flags": quality_flags,
        "task_name": row.get("task_name", ""),
        "task_description": row.get("task_description", ""),
        "source_sha256": row.get("source_sha256", ""),
        "source_path": row.get("source_path", ""),
        "evidence_snippet": row.get("evidence_snippet", ""),
        "training_admission": UNRESOLVED_TRAINING_ADMISSION,
        "validation_eligible": False,
        "test_eligible": False,
        "production_merge": "not_granted",
        "next_action": "add reviewed operator-to-L3 canonicalization authority or keep deferred",
    }


def _build_unresolved_sidecar(p4_gate_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    unresolved = [
        row
        for row in p4_gate_rows
        if row.get("canonicalization_status") == "needs_canonicalization_rules"
    ]
    return [
        _unresolved_sidecar_row(row)
        for row in sorted(unresolved, key=lambda item: str(item.get("review_id") or ""))
    ]


def build_reviewed_train_only_manifest(
    *,
    accepted_train_only_jsonl_path: Path,
    p4_l3_ready_jsonl_path: Path,
    p4_gate_jsonl_path: Path,
) -> ReviewedManifestResult:
    accepted_rows = _load_jsonl(accepted_train_only_jsonl_path)
    p4_ready_rows = _load_jsonl(p4_l3_ready_jsonl_path)
    p4_gate_rows = _load_jsonl(p4_gate_jsonl_path)

    manifest_rows: list[dict[str, Any]] = []
    for row_index, row in enumerate(accepted_rows, start=1):
        manifest_rows.append(
            _normalize_manifest_row(
                row,
                source_package=ACCEPTED_17_PACKAGE,
                source_package_row_index=row_index,
                manifest_row_index=len(manifest_rows) + 1,
            )
        )
    for row_index, row in enumerate(p4_ready_rows, start=1):
        manifest_rows.append(
            _normalize_manifest_row(
                row,
                source_package=P4_READY_18_PACKAGE,
                source_package_row_index=row_index,
                manifest_row_index=len(manifest_rows) + 1,
            )
        )

    _assert_unique_manifest(manifest_rows)
    unresolved_rows = _build_unresolved_sidecar(p4_gate_rows)

    package_counts = Counter(row["source_package"] for row in manifest_rows)
    tier_counts = Counter(row["admission_tier"] for row in manifest_rows)
    source_bucket_counts = Counter(
        str(row.get("p4_source_bucket") or "not_p4")
        for row in manifest_rows
    )
    l3_lengths = [len(row["l3_sequence"]) for row in manifest_rows]
    unresolved_operator_counts = Counter(
        operator
        for row in unresolved_rows
        for operator in row["unmapped_raw_operators"]
    )

    summary = {
        "schema": "gis_recommend.gee_raster_core_reviewed_manifest_summary.v1",
        "manifest_id": MANIFEST_ID,
        "inputs": {
            "accepted_train_only": str(Path(accepted_train_only_jsonl_path)),
            "p4_l3_ready": str(Path(p4_l3_ready_jsonl_path)),
            "p4_gate": str(Path(p4_gate_jsonl_path)),
        },
        "counts": {
            "accepted17_rows": package_counts[ACCEPTED_17_PACKAGE],
            "p4_l3_ready_rows": package_counts[P4_READY_18_PACKAGE],
            "manifest_rows": len(manifest_rows),
            "unresolved_p4_rows": len(unresolved_rows),
            "unique_review_ids": len({row["review_id"] for row in manifest_rows}),
            "unique_source_sha256": len({row["source_sha256"] for row in manifest_rows}),
            "unique_l3_sequences": len({tuple(row["l3_sequence"]) for row in manifest_rows}),
            "unique_operator_sequences": len(
                {tuple(row["operator_sequence"]) for row in manifest_rows}
            ),
            "min_l3_length": min(l3_lengths),
            "max_l3_length": max(l3_lengths),
            "source_package_counts": dict(sorted(package_counts.items())),
            "admission_tier_counts": dict(sorted(tier_counts.items())),
            "source_bucket_counts": dict(sorted(source_bucket_counts.items())),
        },
        "review_ids": {
            "manifest": [row["review_id"] for row in manifest_rows],
            "accepted17": [
                row["review_id"]
                for row in manifest_rows
                if row["source_package"] == ACCEPTED_17_PACKAGE
            ],
            "p4_l3_ready": [
                row["review_id"]
                for row in manifest_rows
                if row["source_package"] == P4_READY_18_PACKAGE
            ],
            "p4_unresolved": [row["review_id"] for row in unresolved_rows],
        },
        "top_unresolved_operators": unresolved_operator_counts.most_common(20),
        "decision": {
            "training_admission": MANIFEST_TRAINING_ADMISSION,
            "production_merge": "not_granted",
            "validation_eligible": False,
            "test_eligible": False,
            "training_run_started": False,
            "llm_used": False,
            "next_gate": "manual paper_v1/training-manifest decision before any model training or expansion",
        },
        "policy": {
            "source_platform": "GEE",
            "target_platform": "L3",
            "training_scope": "core_subworkflow",
            "manifest_split": "train_only",
            "sample_weight_max": 0.5,
            "exclude_from_qgis_operator_chain_gold": True,
            "exclude_from_validation_test": True,
            "unresolved_rows_fail_closed": True,
        },
    }
    return ReviewedManifestResult(
        rows=manifest_rows,
        unresolved_rows=unresolved_rows,
        summary=summary,
    )


def _jsonl_text(rows: list[dict[str, Any]]) -> str:
    return "".join(
        json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"
        for row in rows
    )


def _csv_value(value: Any) -> Any:
    if isinstance(value, (list, dict)):
        return json.dumps(value, ensure_ascii=False, sort_keys=True)
    return value


def _write_csv(path: Path, rows: list[dict[str, Any]], *, fieldnames: tuple[str, ...]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: _csv_value(row.get(field, "")) for field in fieldnames})


def _render_report(summary: dict[str, Any]) -> str:
    counts = summary["counts"]
    decision = summary["decision"]
    lines = [
        "# GEE Raster Core Reviewed Train-only Manifest",
        "",
        "This manifest combines the 17-row accepted GEE raster-core train-only",
        "package with the 18-row P4 L3-ready package. It also keeps unresolved",
        "P4 rows in a separate fail-closed sidecar. This is not a production merge",
        "and does not authorize validation/test use or a training run.",
        "",
        "## Summary",
        "",
        f"- Manifest rows: {counts['manifest_rows']}",
        f"- Existing accepted package rows: {counts['accepted17_rows']}",
        f"- P4 L3-ready rows: {counts['p4_l3_ready_rows']}",
        f"- P4 unresolved sidecar rows: {counts['unresolved_p4_rows']}",
        f"- Unique source SHA256 values: {counts['unique_source_sha256']}",
        f"- Unique L3 sequences: {counts['unique_l3_sequences']}",
        f"- Unique operator sequences: {counts['unique_operator_sequences']}",
        f"- Training admission: `{decision['training_admission']}`",
        f"- Production merge: `{decision['production_merge']}`",
        f"- Validation eligible: `{decision['validation_eligible']}`",
        f"- Test eligible: `{decision['test_eligible']}`",
        f"- Training run started: `{decision['training_run_started']}`",
        "",
        "## Source packages",
        "",
    ]
    for package, count in counts["source_package_counts"].items():
        lines.append(f"- `{package}`: {count}")
    lines.extend(["", "## Deferred P4 rows", ""])
    for review_id in summary["review_ids"]["p4_unresolved"]:
        lines.append(f"- `{review_id}`")
    lines.extend(
        [
            "",
            "## Boundary",
            "",
            "- `source_platform=GEE`",
            "- `target_platform=L3`",
            "- `training_scope=core_subworkflow`",
            "- `manifest_split=train_only`",
            "- `sample_weight <= 0.5`",
            "- Validation/test and production merge are explicitly forbidden.",
            "- This manifest is not QGIS operator-chain gold.",
            "",
        ]
    )
    return "\n".join(lines)


def write_outputs(
    result: ReviewedManifestResult,
    output_dir: Path,
    *,
    output_prefix: str = OUTPUT_PREFIX,
) -> dict[str, Path]:
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    jsonl_path = output_dir / f"{output_prefix}.jsonl"
    csv_path = output_dir / f"{output_prefix}.csv"
    unresolved_jsonl_path = output_dir / f"{output_prefix}_unresolved_p4_sidecar.jsonl"
    unresolved_csv_path = output_dir / f"{output_prefix}_unresolved_p4_sidecar.csv"
    summary_path = output_dir / f"{output_prefix}_summary.json"
    report_path = output_dir / f"{output_prefix}_report.md"
    hash_ledger_path = output_dir / f"{output_prefix}_hash_ledger.json"

    _atomic_write_text(jsonl_path, _jsonl_text(result.rows))
    _write_csv(csv_path, result.rows, fieldnames=CSV_FIELDS)
    _atomic_write_text(unresolved_jsonl_path, _jsonl_text(result.unresolved_rows))
    _write_csv(unresolved_csv_path, result.unresolved_rows, fieldnames=UNRESOLVED_CSV_FIELDS)
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
            for path in (
                jsonl_path,
                csv_path,
                unresolved_jsonl_path,
                unresolved_csv_path,
                summary_path,
                report_path,
            )
        },
    }
    _atomic_write_text(
        hash_ledger_path,
        json.dumps(ledger, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
    )
    return {
        "jsonl": jsonl_path,
        "csv": csv_path,
        "unresolved_jsonl": unresolved_jsonl_path,
        "unresolved_csv": unresolved_csv_path,
        "summary": summary_path,
        "report": report_path,
        "hash_ledger": hash_ledger_path,
    }


def main(argv: list[str] | None = None) -> dict[str, Path]:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--accepted-train-only", type=Path, default=DEFAULT_ACCEPTED_17)
    parser.add_argument("--p4-l3-ready", type=Path, default=DEFAULT_P4_READY_18)
    parser.add_argument("--p4-gate", type=Path, default=DEFAULT_P4_GATE_24)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_REPORT_DIR)
    parser.add_argument("--output-prefix", default=OUTPUT_PREFIX)
    args = parser.parse_args(argv)

    result = build_reviewed_train_only_manifest(
        accepted_train_only_jsonl_path=args.accepted_train_only,
        p4_l3_ready_jsonl_path=args.p4_l3_ready,
        p4_gate_jsonl_path=args.p4_gate,
    )
    return write_outputs(result, args.output_dir, output_prefix=args.output_prefix)


if __name__ == "__main__":
    main()
