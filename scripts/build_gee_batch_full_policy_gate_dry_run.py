#!/usr/bin/env python3
"""Apply the calibrated GEE sampling policies to the full batch package as a dry run.

This script does not regenerate or overwrite `train11397_*`.  It reads the
current model-readable GEE raster-core silver package and emits a row-level
sidecar showing how the six sampling-audit policy candidates would affect a
strict future regeneration gate.
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
import re
import tempfile
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PACKAGE_DIR = (
    ROOT
    / "docs/reports/gee_raster_core_v1_review_split_2026-07-24"
    / "gee_raster_core_batch_training_package_v1"
)
DEFAULT_TRAIN_JSON = DEFAULT_PACKAGE_DIR / "train11397_v4_100.json"
DEFAULT_OUTPUT_DIR = DEFAULT_PACKAGE_DIR / "audit_full_policy_gate_v1"
OUTPUT_PREFIX = "full_policy_gate_v1"

ROW_SCHEMA = "gis_recommend.gee_raster_core_batch_full_policy_gate_row.v1"
SUMMARY_SCHEMA = "gis_recommend.gee_raster_core_batch_full_policy_gate_summary.v1"
HASH_LEDGER_SCHEMA = "gis_recommend.hash_ledger.v1"

POLICY_IDS = (
    "display_export_noise_sidecar",
    "evaluation_metrics_sidecar",
    "external_context_sidecar",
    "generic_rule_review_fail_closed",
    "manual_boundary_review_fail_closed",
    "rule_repair_before_regeneration",
)

FAIL_CLOSED_POLICIES = {
    "generic_rule_review_fail_closed",
    "manual_boundary_review_fail_closed",
    "rule_repair_before_regeneration",
}

CLASSIFICATION_TEXT_RE = re.compile(
    r"\b(classif(?:y|ies|ied|ication)|classifier|random forest|cart|svm|land cover classes?)\b",
    re.IGNORECASE,
)
VECTOR_OR_TRAINING_TEXT_RE = re.compile(
    r"\b(training labels?|labeled samples?|sample regions?|ground truth|shapefiles?|"
    r"user-uploaded|uploaded|feature collections?|vector|polygons?)\b",
    re.IGNORECASE,
)
EVALUATION_TEXT_RE = re.compile(
    r"\b(accuracy|confusion matrices?|error matrices?|validation|validated|evaluates?|"
    r"evaluation|kappa)\b",
    re.IGNORECASE,
)
DISPLAY_OR_EXPORT_TEXT_RE = re.compile(
    r"\b(outputs?|outputting|map layers?|visuali[sz](?:e|ation|ing)?|charts?|prints?|"
    r"exports?|display(?:s|ed|ing)?)\b",
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

CLASSIFIER_OPERATOR_MARKERS = ("classifier", ".classify", ".train")
VECTOR_SAMPLING_OPERATOR_MARKERS = (
    "sampleregions",
    ".sample",
    "featurecollection",
    "reduceregions",
)
EVALUATION_OPERATOR_MARKERS = ("errormatrix", "confusionmatrix", ".accuracy", ".kappa")
REGIONAL_STATS_OPERATOR_MARKERS = (
    "reduceregion",
    "reduceregions",
    "pixelarea",
    "featurecollection",
)
TEMPORAL_OPERATOR_MARKERS = ("landtrendr", "linearfit", "senslope", ".reduce")

RISK_WEIGHTS = {
    "classification_text_without_classifier_operator": 3,
    "vector_or_training_label_text_without_vector_sampling_operator": 3,
    "evaluation_text_without_evaluation_operator": 2,
    "regional_statistics_text_without_regional_operator": 2,
    "advanced_temporal_text_without_temporal_operator": 2,
    "display_or_export_language_requires_core_boundary_check": 1,
    "complex_or_long_chain_review_priority": 1,
    "reducer_heavy_chain_review_priority": 1,
    "threshold_mask_heavy_chain_review_priority": 1,
}

CSV_FIELDS = (
    "input_row_index",
    "sample_id",
    "proposal_id",
    "script_id",
    "task_type",
    "task_name",
    "risk_score",
    "risk_level",
    "risk_flags",
    "policy_hits",
    "policy_hit_count",
    "strict_regeneration_disposition",
    "audit_notes",
    "review_split_audit",
    "source_sha256",
    "source_path",
    "training_admission",
    "training_rows_emitted",
    "validation_eligible",
    "test_eligible",
    "production_merge",
)


@dataclass(frozen=True)
class FullPolicyGateDryRunResult:
    rows: list[dict[str, Any]]
    summary: dict[str, Any]


def _filesystem_path(path: Path) -> str:
    text = str(path)
    if os.name != "nt":
        return text
    if text.startswith("\\\\?\\"):
        return text
    absolute = path if path.is_absolute() else Path.cwd() / path
    text = str(absolute)
    if text.startswith("\\\\?\\"):
        return text
    if text.startswith("\\\\"):
        return "\\\\?\\UNC\\" + text.lstrip("\\")
    return "\\\\?\\" + text


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with open(_filesystem_path(Path(path)), "rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _load_train_rows(path: Path) -> list[dict[str, Any]]:
    with open(_filesystem_path(Path(path)), encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain a JSON object package")
    rows = data.get("labeled_workflows")
    if not isinstance(rows, list) or not rows:
        raise ValueError(f"{path} must contain non-empty labeled_workflows")
    if not all(isinstance(row, dict) for row in rows):
        raise ValueError(f"{path} labeled_workflows must contain JSON objects")
    return rows


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


def _model_sequence_length(row: dict[str, Any], operators: list[str]) -> int:
    sequence_fit = row.get("sequence_fit")
    if isinstance(sequence_fit, dict):
        try:
            return int(sequence_fit.get("model_sequence_length") or 0)
        except (TypeError, ValueError):
            pass
    try:
        return int(row.get("model_sequence_length") or 0)
    except (TypeError, ValueError):
        return len(operators) + 2


def _risk_flags(row: dict[str, Any]) -> list[str]:
    operators = _as_string_list(row.get("operator_sequence"))
    operators_lower = [operator.lower() for operator in operators]
    text = _text(row)
    flags: list[str] = []

    if CLASSIFICATION_TEXT_RE.search(text) and not _contains_any_operator(
        operators_lower,
        CLASSIFIER_OPERATOR_MARKERS,
    ):
        flags.append("classification_text_without_classifier_operator")

    if VECTOR_OR_TRAINING_TEXT_RE.search(text) and not _contains_any_operator(
        operators_lower,
        VECTOR_SAMPLING_OPERATOR_MARKERS,
    ):
        flags.append("vector_or_training_label_text_without_vector_sampling_operator")

    if EVALUATION_TEXT_RE.search(text) and not _contains_any_operator(
        operators_lower,
        EVALUATION_OPERATOR_MARKERS,
    ):
        flags.append("evaluation_text_without_evaluation_operator")

    if DISPLAY_OR_EXPORT_TEXT_RE.search(text):
        flags.append("display_or_export_language_requires_core_boundary_check")

    if REGIONAL_STATS_TEXT_RE.search(text) and not _contains_any_operator(
        operators_lower,
        REGIONAL_STATS_OPERATOR_MARKERS,
    ):
        flags.append("regional_statistics_text_without_regional_operator")

    if TEMPORAL_ADVANCED_TEXT_RE.search(text) and not _contains_any_operator(
        operators_lower,
        TEMPORAL_OPERATOR_MARKERS,
    ):
        flags.append("advanced_temporal_text_without_temporal_operator")

    if _model_sequence_length(row, operators) >= 18:
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

    return flags


def _risk_score(flags: list[str]) -> int:
    return sum(RISK_WEIGHTS.get(flag, 1) for flag in flags)


def _risk_level(score: int) -> str:
    if score >= 5:
        return "high"
    if score >= 2:
        return "medium"
    return "low"


def _policy_hits(flags: list[str]) -> list[str]:
    flag_set = set(flags)
    hits: list[str] = []
    if "display_or_export_language_requires_core_boundary_check" in flag_set:
        hits.append("display_export_noise_sidecar")
    if "evaluation_text_without_evaluation_operator" in flag_set:
        hits.append("evaluation_metrics_sidecar")
    if "vector_or_training_label_text_without_vector_sampling_operator" in flag_set:
        hits.append("external_context_sidecar")
    if flag_set & {
        "classification_text_without_classifier_operator",
        "advanced_temporal_text_without_temporal_operator",
        "regional_statistics_text_without_regional_operator",
    }:
        hits.append("rule_repair_before_regeneration")
    if flag_set & {
        "complex_or_long_chain_review_priority",
        "reducer_heavy_chain_review_priority",
        "threshold_mask_heavy_chain_review_priority",
    }:
        hits.append("generic_rule_review_fail_closed")
    return sorted(set(hits))


def _audit_notes(row: dict[str, Any]) -> list[str]:
    if row.get("review_split_audit") in {"val", "test"}:
        return ["prior_review_split_was_not_train"]
    return []


def _strict_regeneration_disposition(policy_hits: list[str]) -> str:
    if set(policy_hits) & FAIL_CLOSED_POLICIES:
        return "fail_closed_policy_backlog_before_regeneration"
    if policy_hits:
        return "sidecar_or_text_review_required_before_regeneration"
    return "provisionally_keep_current_silver_row"


def _gate_row(row: dict[str, Any], *, input_row_index: int) -> dict[str, Any]:
    flags = _risk_flags(row)
    score = _risk_score(flags)
    hits = _policy_hits(flags)
    return {
        "schema": ROW_SCHEMA,
        "input_row_index": input_row_index,
        "sample_id": row.get("sample_id", ""),
        "proposal_id": row.get("proposal_id", ""),
        "script_id": row.get("script_id", ""),
        "task_type": row.get("task_type", ""),
        "task_name": row.get("task_name", ""),
        "task_description": row.get("task_description", ""),
        "operator_sequence": _as_string_list(row.get("operator_sequence")),
        "l3_code_sequence": _as_string_list(row.get("l3_code_sequence")),
        "risk_flags": flags,
        "risk_score": score,
        "risk_level": _risk_level(score),
        "policy_hits": hits,
        "policy_hit_count": len(hits),
        "strict_regeneration_disposition": _strict_regeneration_disposition(hits),
        "audit_notes": _audit_notes(row),
        "review_split_audit": row.get("review_split_audit", ""),
        "source_sha256": row.get("source_sha256", ""),
        "source_path": row.get("source_path", ""),
        "source_identity_status": row.get("source_identity_status", ""),
        "source_platform": row.get("source_platform", ""),
        "target_platform": row.get("target_platform", ""),
        "workflow_scope": row.get("workflow_scope", ""),
        "training_scope": row.get("training_scope", ""),
        "sample_weight": row.get("sample_weight", ""),
        "training_admission": "not_granted_full_policy_gate_dry_run",
        "training_rows_emitted": 0,
        "validation_eligible": False,
        "test_eligible": False,
        "production_merge": "not_granted",
        "current_package_action": "unchanged_sidecar_only",
        "next_action": "use this sidecar to decide explicit full-package regeneration; do not overwrite train11397_*",
    }


def build_full_policy_gate_dry_run(
    *,
    train_json: Path | None = None,
    rows: list[dict[str, Any]] | None = None,
    source_label: str | None = None,
) -> FullPolicyGateDryRunResult:
    if rows is None:
        if train_json is None:
            train_json = DEFAULT_TRAIN_JSON
        rows = _load_train_rows(train_json)
    source_hash = _sha256(train_json) if train_json is not None else ""
    source_text = str(train_json) if train_json is not None else (source_label or "in_memory_rows")

    gate_rows = [
        _gate_row(row, input_row_index=index)
        for index, row in enumerate(rows, start=1)
    ]
    policy_hit_counts = Counter(policy for row in gate_rows for policy in row["policy_hits"])
    policy_hit_counts_with_zeros = {
        policy_id: policy_hit_counts.get(policy_id, 0) for policy_id in POLICY_IDS
    }
    disposition_counts = Counter(row["strict_regeneration_disposition"] for row in gate_rows)
    risk_level_counts = Counter(row["risk_level"] for row in gate_rows)
    risk_flag_counts = Counter(flag for row in gate_rows for flag in row["risk_flags"])
    audit_note_counts = Counter(note for row in gate_rows for note in row["audit_notes"])
    review_split_counts = Counter(_as_str(row.get("review_split_audit")) or "missing" for row in gate_rows)

    summary = {
        "schema": SUMMARY_SCHEMA,
        "source_package": {
            "train_json": source_text,
            "train_json_sha256": source_hash,
            "source_label": source_label or "",
        },
        "counts": {
            "gate_rows": len(gate_rows),
            "policy_hit_rows": sum(1 for row in gate_rows if row["policy_hits"]),
            "policy_candidate_rows": len(POLICY_IDS),
            "strict_regeneration_defer_rows": disposition_counts.get(
                "fail_closed_policy_backlog_before_regeneration",
                0,
            ),
            "sidecar_or_text_review_rows": disposition_counts.get(
                "sidecar_or_text_review_required_before_regeneration",
                0,
            ),
            "provisionally_keep_rows": disposition_counts.get(
                "provisionally_keep_current_silver_row",
                0,
            ),
            "audit_note_rows": sum(1 for row in gate_rows if row["audit_notes"]),
            "training_rows_emitted": 0,
        },
        "risk_level_counts": dict(sorted(risk_level_counts.items())),
        "risk_flag_counts": dict(sorted(risk_flag_counts.items())),
        "policy_hit_counts": dict(sorted(policy_hit_counts_with_zeros.items())),
        "strict_regeneration_disposition_counts": dict(sorted(disposition_counts.items())),
        "review_split_audit_counts": dict(sorted(review_split_counts.items())),
        "audit_note_counts": dict(sorted(audit_note_counts.items())),
        "decision": {
            "dry_run_only": True,
            "mutated_train11397_package": False,
            "admission_change": "none",
            "training_rows_emitted": 0,
            "validation_eligible": False,
            "test_eligible": False,
            "production_merge": "not_granted",
            "llm_used": False,
            "training_run_started": False,
        },
        "policy": {
            "source_platform": "GEE",
            "target_platform": "L3",
            "surface_policy_gate_only": True,
            "source_backed_per_row_audit": False,
            "do_not_mutate_train11397_package": True,
            "do_not_promote_gee_to_validation_or_test": True,
            "strict_regeneration_requires_explicit_authorization": True,
        },
    }
    return FullPolicyGateDryRunResult(rows=gate_rows, summary=summary)


def _atomic_write(path: Path, text: str) -> None:
    os.makedirs(_filesystem_path(path.parent), exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "w",
        encoding="utf-8",
        newline="",
        dir=_filesystem_path(path.parent),
        delete=False,
    ) as handle:
        handle.write(text)
        temporary = Path(handle.name)
    os.replace(_filesystem_path(temporary), _filesystem_path(path))


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


def _render_report(result: FullPolicyGateDryRunResult) -> str:
    summary = result.summary
    counts = summary["counts"]
    lines = [
        "# GEE Full Batch Policy Gate Dry Run v1",
        "",
        "This dry run applies the six sampling-audit policy candidates to the",
        "current 11,397-row GEE raster-core silver package as a sidecar only.",
        "",
        "## Result",
        "",
        f"- Gate rows: {counts['gate_rows']:,}",
        f"- Rows with policy hits: {counts['policy_hit_rows']:,}",
        f"- Strict regeneration defer rows: {counts['strict_regeneration_defer_rows']:,}",
        f"- Sidecar/text-review rows: {counts['sidecar_or_text_review_rows']:,}",
        f"- Provisionally keep rows: {counts['provisionally_keep_rows']:,}",
        f"- Training rows emitted: {counts['training_rows_emitted']:,}",
        "",
        "## Policy hits",
        "",
    ]
    for policy_id, count in summary["policy_hit_counts"].items():
        lines.append(f"- `{policy_id}`: {count:,}")
    lines.extend(
        [
            "",
            "## Boundary",
            "",
            "- This is a surface-policy dry run, not row-level source-backed admission.",
            "- It does not modify `train11397_*`.",
            "- It does not create validation/test data.",
            "- It does not call an LLM or start training.",
            "- Full regeneration requires an explicit next step.",
            "",
        ]
    )
    return "\n".join(lines)


def resolve_output_paths(output_dir: Path, *, output_prefix: str = OUTPUT_PREFIX) -> dict[str, Path]:
    output_dir = Path(output_dir)
    return {
        "jsonl": output_dir / f"{output_prefix}.jsonl",
        "csv": output_dir / f"{output_prefix}.csv",
        "summary": output_dir / f"{output_prefix}_summary.json",
        "report": output_dir / f"{output_prefix}_report.md",
        "hash_ledger": output_dir / f"{output_prefix}_hashes.json",
    }


def write_outputs(
    result: FullPolicyGateDryRunResult,
    *,
    output_dir: Path,
    output_prefix: str = OUTPUT_PREFIX,
    train_json: Path | None = None,
) -> dict[str, Path]:
    paths = resolve_output_paths(output_dir, output_prefix=output_prefix)
    _atomic_write(paths["jsonl"], _jsonl_text(result.rows))
    _atomic_write(paths["csv"], _csv_text(result.rows))
    _atomic_write(
        paths["summary"],
        json.dumps(result.summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
    )
    _atomic_write(paths["report"], _render_report(result))

    source_inputs: dict[str, Any] = {}
    if train_json is not None:
        source_inputs[Path(train_json).name] = {
            "path": str(train_json),
            "sha256": _sha256(train_json),
            "bytes": os.path.getsize(_filesystem_path(Path(train_json))),
        }
    ledger = {
        "schema": HASH_LEDGER_SCHEMA,
        "source_inputs": source_inputs,
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
    _atomic_write(
        paths["hash_ledger"],
        json.dumps(ledger, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
    )
    return paths


def main(argv: list[str] | None = None) -> dict[str, Path]:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--train-json", type=Path, default=DEFAULT_TRAIN_JSON)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--output-prefix", default=OUTPUT_PREFIX)
    args = parser.parse_args(argv)

    result = build_full_policy_gate_dry_run(train_json=args.train_json)
    return write_outputs(
        result,
        output_dir=args.output_dir,
        output_prefix=args.output_prefix,
        train_json=args.train_json,
    )


if __name__ == "__main__":
    main()
