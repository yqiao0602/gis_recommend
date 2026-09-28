#!/usr/bin/env python3
"""Build a rule-calibration precheck packet for the GEE batch audit sample.

This script is deliberately non-admitting.  It reads the deterministic
``audit_sample_50.jsonl`` emitted by the batch exporter, adds risk flags and
blank human-review fields, and writes a sidecar packet for sampling audit.

It does not mutate the batch package, emit training rows, promote GEE rows to
validation/test, or infer missing operators.
"""

from __future__ import annotations

import argparse
from collections import Counter
import csv
from dataclasses import dataclass
import hashlib
import io
import json
from pathlib import Path
import re
import tempfile
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PACKAGE_DIR = (
    ROOT
    / "docs/reports/gee_raster_core_v1_review_split_2026-07-24"
    / "gee_raster_core_batch_training_package_v1"
)
DEFAULT_AUDIT_SAMPLE = DEFAULT_PACKAGE_DIR / "audit_sample_50.jsonl"
DEFAULT_OUTPUT_DIR = DEFAULT_PACKAGE_DIR / "audit_precheck_v1"

PRECHECK_SCHEMA = "gis_recommend.gee_raster_core_batch_audit_precheck_row.v1"
SUMMARY_SCHEMA = "gis_recommend.gee_raster_core_batch_audit_precheck_summary.v1"
HASH_LEDGER_SCHEMA = "gis_recommend.hash_ledger.v1"
REVIEW_ROLE = "sampling_audit_rule_calibration"
PRECHECK_STATUS = "pending_human_sampling_audit"

HUMAN_FIELDS = (
    "human_decision",
    "human_chain_verdict",
    "human_text_verdict",
    "human_l3_verdict",
    "human_required_action",
    "human_notes",
    "adjudicated_by",
    "adjudicated_at",
)

CSV_FIELDS = (
    "review_priority",
    "risk_level",
    "risk_score",
    "risk_flags",
    "precheck_status",
    "audit_rank",
    "audit_status",
    "sample_id",
    "proposal_id",
    "script_id",
    "task_type",
    "task_name",
    "task_description",
    "operator_sequence",
    "l3_code_sequence",
    "model_sequence_length",
    "source_evidence_status",
    "requires_source_lookup_for_final_adjudication",
    "source_sha256",
    "source_path",
    "review_split_audit",
    "audit_questions",
    *HUMAN_FIELDS,
)

CLASSIFICATION_TEXT_RE = re.compile(
    r"\b(classif(?:y|ies|ication|ied)?|classifier|random forest|cart|svm|training labels?|"
    r"labeled samples?|ground truth)\b",
    re.IGNORECASE,
)
VECTOR_OR_TRAINING_TEXT_RE = re.compile(
    r"\b(training labels?|labeled samples?|sample regions?|ground truth|shapefiles?|"
    r"user-uploaded|feature collections?|vector|polygons?)\b",
    re.IGNORECASE,
)
EVALUATION_TEXT_RE = re.compile(
    r"\b(accuracy|confusion matrices?|error matrices?|validation|validated|evaluates?|kappa)\b",
    re.IGNORECASE,
)
DISPLAY_OR_EXPORT_TEXT_RE = re.compile(
    r"\b(outputs?|outputting|map layers?|visuali[sz](?:e|ation|ing)?|charts?|prints?|exports?)\b",
    re.IGNORECASE,
)
REGIONAL_STATS_TEXT_RE = re.compile(
    r"\b(zonal|administrative boundar(?:y|ies)|region(?:al)? statistics|per boundary|"
    r"within (?:a|the) region|area statistics)\b",
    re.IGNORECASE,
)
TEMPORAL_ADVANCED_TEXT_RE = re.compile(
    r"\b(landtrendr|time-series|time series|trend|disturbance year|year of detection)\b",
    re.IGNORECASE,
)

CLASSIFIER_OPERATOR_MARKERS = (
    "classifier",
    ".classify",
    ".train",
)
VECTOR_SAMPLING_OPERATOR_MARKERS = (
    "sampleregions",
    ".sample",
    "featurecollection",
    "reduceregions",
)
EVALUATION_OPERATOR_MARKERS = (
    "errormatrix",
    "confusionmatrix",
    ".accuracy",
    ".kappa",
)
REGIONAL_STATS_OPERATOR_MARKERS = (
    "reduceregion",
    "reduceregions",
    "pixelarea",
    "featurecollection",
)
TEMPORAL_OPERATOR_MARKERS = (
    "landtrendr",
    "linearfit",
    "senslope",
    ".reduce",
)


@dataclass(frozen=True)
class AuditPrecheckResult:
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


def _sha256(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _as_str(value: Any) -> str:
    return str(value or "").strip()


def _as_string_list(value: Any) -> list[str]:
    if not isinstance(value, (list, tuple)):
        return []
    return [str(item).strip() for item in value if str(item).strip()]


def _contains_any_operator(operators_lower: list[str], markers: tuple[str, ...]) -> bool:
    return any(marker in operator for operator in operators_lower for marker in markers)


def _text(row: dict[str, Any]) -> str:
    return f"{_as_str(row.get('task_name'))} {_as_str(row.get('task_description'))}"


def _risk_flags(row: dict[str, Any]) -> list[str]:
    operators = _as_string_list(row.get("operator_sequence"))
    operators_lower = [operator.lower() for operator in operators]
    text = _text(row)
    flags: list[str] = []

    if CLASSIFICATION_TEXT_RE.search(text) and not _contains_any_operator(
        operators_lower, CLASSIFIER_OPERATOR_MARKERS
    ):
        flags.append("classification_text_without_classifier_operator")

    if VECTOR_OR_TRAINING_TEXT_RE.search(text) and not _contains_any_operator(
        operators_lower, VECTOR_SAMPLING_OPERATOR_MARKERS
    ):
        flags.append("vector_or_training_label_text_without_vector_sampling_operator")

    if EVALUATION_TEXT_RE.search(text) and not _contains_any_operator(
        operators_lower, EVALUATION_OPERATOR_MARKERS
    ):
        flags.append("evaluation_text_without_evaluation_operator")

    if DISPLAY_OR_EXPORT_TEXT_RE.search(text):
        flags.append("display_or_export_language_requires_core_boundary_check")

    if REGIONAL_STATS_TEXT_RE.search(text) and not _contains_any_operator(
        operators_lower, REGIONAL_STATS_OPERATOR_MARKERS
    ):
        flags.append("regional_statistics_text_without_regional_operator")

    if TEMPORAL_ADVANCED_TEXT_RE.search(text) and not _contains_any_operator(
        operators_lower, TEMPORAL_OPERATOR_MARKERS
    ):
        flags.append("advanced_temporal_text_without_temporal_operator")

    model_sequence_length = int(row.get("model_sequence_length") or 0)
    if model_sequence_length >= 18:
        flags.append("complex_or_long_chain_review_priority")

    reducer_count = sum(1 for operator in operators_lower if "reduce" in operator)
    if reducer_count >= 3:
        flags.append("reducer_heavy_chain_review_priority")

    threshold_mask_count = sum(
        1
        for operator in operators_lower
        if any(marker in operator for marker in (".gt", ".gte", ".lt", ".lte", ".eq", "mask"))
    )
    if threshold_mask_count >= 5:
        flags.append("threshold_mask_heavy_chain_review_priority")

    if row.get("review_split_audit") in {"val", "test"}:
        flags.append("prior_review_split_was_not_train_but_output_is_train_only")

    return flags


def _risk_score(flags: list[str]) -> int:
    weights = {
        "classification_text_without_classifier_operator": 3,
        "vector_or_training_label_text_without_vector_sampling_operator": 3,
        "evaluation_text_without_evaluation_operator": 2,
        "regional_statistics_text_without_regional_operator": 2,
        "advanced_temporal_text_without_temporal_operator": 2,
        "display_or_export_language_requires_core_boundary_check": 1,
        "complex_or_long_chain_review_priority": 1,
        "reducer_heavy_chain_review_priority": 1,
        "threshold_mask_heavy_chain_review_priority": 1,
        "prior_review_split_was_not_train_but_output_is_train_only": 1,
    }
    return sum(weights.get(flag, 1) for flag in flags)


def _risk_level(score: int) -> str:
    if score >= 5:
        return "high"
    if score >= 2:
        return "medium"
    return "low"


def _precheck_row(row: dict[str, Any]) -> dict[str, Any]:
    operators = _as_string_list(row.get("operator_sequence"))
    l3_codes = _as_string_list(row.get("l3_code_sequence"))
    if len(operators) != len(l3_codes):
        raise ValueError(
            f"operator/L3 length mismatch for sample_id={row.get('sample_id')}: "
            f"{len(operators)} != {len(l3_codes)}"
        )

    flags = _risk_flags(row)
    score = _risk_score(flags)
    result = {
        "schema": PRECHECK_SCHEMA,
        "review_priority": 0,
        "risk_level": _risk_level(score),
        "risk_score": score,
        "risk_flags": flags,
        "precheck_status": PRECHECK_STATUS,
        "review_role": REVIEW_ROLE,
        "audit_rank": int(row.get("audit_rank") or 0),
        "audit_status": row.get("audit_status", ""),
        "sample_id": row.get("sample_id", ""),
        "proposal_id": row.get("proposal_id", ""),
        "script_id": row.get("script_id", ""),
        "task_type": row.get("task_type", ""),
        "task_name": row.get("task_name", ""),
        "task_description": row.get("task_description", ""),
        "operator_sequence": operators,
        "l3_code_sequence": l3_codes,
        "model_sequence_length": row.get("model_sequence_length", ""),
        "source_evidence_status": "server_path_hash_only",
        "requires_source_lookup_for_final_adjudication": True,
        "source_sha256": row.get("source_sha256", ""),
        "source_path": row.get("source_path", ""),
        "review_split_audit": row.get("review_split_audit", ""),
        "audit_questions": row.get("audit_questions", []),
        "validation_eligible": False,
        "test_eligible": False,
        "training_rows_emitted": 0,
        "mutated_training_package": False,
        "next_action": "human sampling audit; fix systematic extractor/text/mapping failure rules, not individual production rows",
    }
    result.update({field: "" for field in HUMAN_FIELDS})
    return result


def build_audit_precheck(audit_sample_path: Path = DEFAULT_AUDIT_SAMPLE) -> AuditPrecheckResult:
    input_rows = _load_jsonl(audit_sample_path)
    rows = [_precheck_row(row) for row in input_rows]
    rows.sort(key=lambda row: (-int(row["risk_score"]), int(row["audit_rank"])))
    for priority, row in enumerate(rows, start=1):
        row["review_priority"] = priority

    risk_flag_counts = Counter(flag for row in rows for flag in row["risk_flags"])
    risk_level_counts = Counter(row["risk_level"] for row in rows)
    review_split_counts = Counter(row.get("review_split_audit") or "missing" for row in rows)

    summary = {
        "schema": SUMMARY_SCHEMA,
        "inputs": {
            "audit_sample": str(Path(audit_sample_path)),
        },
        "counts": {
            "input_rows": len(input_rows),
            "precheck_rows": len(rows),
            "requires_source_lookup_rows": sum(
                1 for row in rows if row["requires_source_lookup_for_final_adjudication"]
            ),
            "high_risk_rows": risk_level_counts.get("high", 0),
            "medium_risk_rows": risk_level_counts.get("medium", 0),
            "low_risk_rows": risk_level_counts.get("low", 0),
            "unique_source_sha256": len({row["source_sha256"] for row in rows}),
            "unique_operator_sequences": len({tuple(row["operator_sequence"]) for row in rows}),
            "unique_l3_sequences": len({tuple(row["l3_code_sequence"]) for row in rows}),
        },
        "risk_flag_counts": dict(sorted(risk_flag_counts.items())),
        "risk_level_counts": dict(sorted(risk_level_counts.items())),
        "review_split_audit_counts": dict(sorted(review_split_counts.items())),
        "decision": {
            "review_role": REVIEW_ROLE,
            "training_rows_emitted": 0,
            "mutated_training_package": False,
            "validation_eligible": False,
            "test_eligible": False,
            "production_merge": "not_granted",
            "training_run_started": False,
            "llm_used": False,
            "admission_change": "none",
        },
        "policy": {
            "source_platform": "GEE",
            "target_platform": "L3",
            "risk_flags_are_audit_priorities_not_rejections": True,
            "source_lookup_required_for_final_adjudication": True,
            "do_not_edit_operator_or_l3_sequences_in_precheck": True,
            "do_not_promote_gee_to_validation_or_test": True,
            "do_not_mutate_train11397_package": True,
        },
    }
    return AuditPrecheckResult(rows=rows, summary=summary)


def _atomic_write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "w", encoding="utf-8", newline="", dir=path.parent, delete=False
    ) as handle:
        handle.write(text)
        temporary = Path(handle.name)
    temporary.replace(path)


def _jsonl_text(rows: list[dict[str, Any]]) -> str:
    return "".join(
        json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"
        for row in rows
    )


def _csv_value(value: Any) -> Any:
    if isinstance(value, (list, dict)):
        return json.dumps(value, ensure_ascii=False, sort_keys=True)
    return value


def _csv_text(rows: list[dict[str, Any]]) -> str:
    output = io.StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=CSV_FIELDS, extrasaction="ignore")
    writer.writeheader()
    for row in rows:
        writer.writerow({field: _csv_value(row.get(field, "")) for field in CSV_FIELDS})
    return output.getvalue()


def _render_report(result: AuditPrecheckResult) -> str:
    summary = result.summary
    counts = summary["counts"]
    decision = summary["decision"]
    lines = [
        "# GEE Raster Core Batch Audit Precheck v1",
        "",
        "This packet is for sampling-audit rule calibration over the deterministic",
        "GEE raster-core batch package. It adds risk flags and blank human-review",
        "fields to the 50-row audit sample without emitting or mutating training data.",
        "",
        "## Result",
        "",
        f"- Input audit rows: {counts['input_rows']}",
        f"- Precheck rows: {counts['precheck_rows']}",
        f"- High-risk rows: {counts['high_risk_rows']}",
        f"- Medium-risk rows: {counts['medium_risk_rows']}",
        f"- Low-risk rows: {counts['low_risk_rows']}",
        f"- Rows requiring source lookup: {counts['requires_source_lookup_rows']}",
        f"- Training rows emitted: {decision['training_rows_emitted']}",
        f"- Mutated training package: {decision['mutated_training_package']}",
        f"- Validation eligible: {decision['validation_eligible']}",
        f"- Test eligible: {decision['test_eligible']}",
        f"- Review role: `{decision['review_role']}`",
        "",
        "## Risk flags",
        "",
    ]
    for flag, count in summary["risk_flag_counts"].items():
        lines.append(f"- `{flag}`: {count}")
    lines.extend(
        [
            "",
            "## Boundary",
            "",
            "- Risk flags are audit priorities, not automatic rejection labels.",
            "- Final adjudication still requires source lookup; current evidence is path/hash only.",
            "- Operator and L3 sequences are copied from the batch audit sample and are not edited here.",
            "- This artifact does not promote GEE rows to validation/test and does not start training.",
            "",
        ]
    )
    return "\n".join(lines)


def resolve_output_paths(output_dir: Path) -> dict[str, Path]:
    output_dir = Path(output_dir)
    return {
        "jsonl": output_dir / "audit_precheck_50_v1.jsonl",
        "csv": output_dir / "audit_precheck_50_v1.csv",
        "summary": output_dir / "audit_precheck_50_v1_summary.json",
        "report": output_dir / "audit_precheck_50_v1_report.md",
        "hash_ledger": output_dir / "audit_precheck_50_v1_hash_ledger.json",
    }


def write_outputs(
    result: AuditPrecheckResult,
    *,
    audit_sample_path: Path,
    output_dir: Path,
) -> dict[str, Path]:
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    paths = resolve_output_paths(output_dir)

    _atomic_write(paths["jsonl"], _jsonl_text(result.rows))
    _atomic_write(paths["csv"], _csv_text(result.rows))
    _atomic_write(
        paths["summary"],
        json.dumps(result.summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
    )
    _atomic_write(paths["report"], _render_report(result))

    ledger = {
        "schema": HASH_LEDGER_SCHEMA,
        "source_inputs": {
            "audit_sample": {
                "path": str(Path(audit_sample_path)),
                "sha256": _sha256(audit_sample_path),
            }
        },
        "artifacts": {
            path.name: {
                "path": str(path),
                "sha256": _sha256(path),
                "bytes": path.stat().st_size,
            }
            for key, path in paths.items()
            if key != "hash_ledger"
        },
    }
    _atomic_write(
        paths["hash_ledger"],
        json.dumps(ledger, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
    )
    return paths


def main(argv: list[str] | None = None) -> dict[str, Path]:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--audit-sample", type=Path, default=DEFAULT_AUDIT_SAMPLE)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    args = parser.parse_args(argv)

    result = build_audit_precheck(args.audit_sample)
    return write_outputs(
        result,
        audit_sample_path=args.audit_sample,
        output_dir=args.output_dir,
    )


if __name__ == "__main__":
    main()
