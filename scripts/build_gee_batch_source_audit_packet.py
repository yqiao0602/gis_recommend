#!/usr/bin/env python3
"""Build a source-backed audit packet for selected-risk GEE batch precheck rows.

The input is the deterministic audit precheck sidecar.  This script joins rows
for one risk level to a local source cache keyed by ``source_sha256.txt``,
verifies the content hash, scans small source markers, and emits rule-action
recommendations.

It is a calibration artifact only: no training rows, no validation/test rows,
no mutation of the batch package, and no operator/L3 edits.
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
DEFAULT_PRECHECK = (
    DEFAULT_PACKAGE_DIR
    / "audit_precheck_v1"
    / "audit_precheck_50_v1.jsonl"
)
DEFAULT_SOURCE_CACHE = ROOT / ".tmp_gee_batch_audit_sources_20260725"
DEFAULT_OUTPUT_DIR = DEFAULT_PACKAGE_DIR / "audit_src_v1"

ROW_SCHEMA = "gis_recommend.gee_raster_core_batch_source_audit_row.v1"
SUMMARY_SCHEMA = "gis_recommend.gee_raster_core_batch_source_audit_summary.v1"
HASH_LEDGER_SCHEMA = "gis_recommend.hash_ledger.v1"
REVIEW_ROLE = "source_backed_sampling_audit_rule_calibration"

HUMAN_FIELDS = (
    "human_source_chain_verdict",
    "human_task_text_verdict",
    "human_rule_action_verdict",
    "human_final_decision",
    "human_notes",
    "adjudicated_by",
    "adjudicated_at",
)

CSV_FIELDS = (
    "review_priority",
    "audit_rank",
    "risk_level",
    "risk_score",
    "risk_flags",
    "sample_id",
    "proposal_id",
    "script_id",
    "task_type",
    "task_name",
    "source_lookup_status",
    "source_sha256_verified",
    "source_path",
    "source_cache_path",
    "recommended_rule_actions",
    "source_backed_findings",
    "source_marker_summary",
    "operator_sequence",
    "l3_code_sequence",
    "validation_eligible",
    "test_eligible",
    *HUMAN_FIELDS,
)

_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")

SOURCE_MARKER_PATTERNS: dict[str, tuple[re.Pattern[str], ...]] = {
    "classifier": (
        re.compile(r"ee\.Classifier", re.IGNORECASE),
        re.compile(r"\.train\s*\(", re.IGNORECASE),
        re.compile(r"\.classify\s*\(", re.IGNORECASE),
    ),
    "sampling": (
        re.compile(r"\.sampleRegions\s*\(", re.IGNORECASE),
        re.compile(r"\.sample\s*\(", re.IGNORECASE),
    ),
    "feature_collection": (
        re.compile(r"ee\.FeatureCollection", re.IGNORECASE),
    ),
    "evaluation": (
        re.compile(r"confusionMatrix\s*\(", re.IGNORECASE),
        re.compile(r"errorMatrix\s*\(", re.IGNORECASE),
        re.compile(r"\.accuracy\s*\(", re.IGNORECASE),
        re.compile(r"\.kappa\s*\(", re.IGNORECASE),
    ),
    "display_export": (
        re.compile(r"Map\.addLayer", re.IGNORECASE),
        re.compile(r"\bExport\.", re.IGNORECASE),
        re.compile(r"\bprint\s*\(", re.IGNORECASE),
        re.compile(r"ui\.Chart", re.IGNORECASE),
    ),
    "temporal": (
        re.compile(r"LandTrendr", re.IGNORECASE),
        re.compile(r"linearFit", re.IGNORECASE),
        re.compile(r"sensSlope", re.IGNORECASE),
    ),
    "regional": (
        re.compile(r"reduceRegion", re.IGNORECASE),
        re.compile(r"reduceRegions", re.IGNORECASE),
        re.compile(r"pixelArea", re.IGNORECASE),
        re.compile(r"aggregate_", re.IGNORECASE),
    ),
}


@dataclass(frozen=True)
class SourceAuditPacketResult:
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


def _as_string_list(value: Any) -> list[str]:
    if not isinstance(value, (list, tuple)):
        return []
    return [str(item).strip() for item in value if str(item).strip()]


def _csv_value(value: Any) -> Any:
    if isinstance(value, (list, dict)):
        return json.dumps(value, ensure_ascii=False, sort_keys=True)
    return value


def _operator_has(operators: list[str], *needles: str) -> bool:
    lowered = [operator.lower() for operator in operators]
    return any(needle.lower() in operator for operator in lowered for needle in needles)


def _source_cache_path(source_cache_dir: Path, source_sha256: str) -> Path:
    return Path(source_cache_dir) / f"{source_sha256}.txt"


def _marker_summary(source_text: str) -> dict[str, Any]:
    summary: dict[str, Any] = {}
    for marker_name, patterns in SOURCE_MARKER_PATTERNS.items():
        count = 0
        for pattern in patterns:
            count += len(pattern.findall(source_text))
        summary[f"{marker_name}_count"] = count
        summary[f"has_{marker_name}_marker"] = count > 0
    return summary


def _source_evidence_snippets(source_text: str, *, max_snippets: int = 16) -> list[dict[str, Any]]:
    snippets: list[dict[str, Any]] = []
    seen: set[tuple[str, int]] = set()
    lines = source_text.splitlines()
    for line_number, line in enumerate(lines, start=1):
        for marker_name, patterns in SOURCE_MARKER_PATTERNS.items():
            if not any(pattern.search(line) for pattern in patterns):
                continue
            key = (marker_name, line_number)
            if key in seen:
                continue
            seen.add(key)
            snippets.append(
                {
                    "marker": marker_name,
                    "line": line_number,
                    "text": line.strip()[:260],
                }
            )
            if len(snippets) >= max_snippets:
                return snippets
    return snippets


def _recommendations(
    row: dict[str, Any],
    *,
    source_lookup_status: str,
    marker_summary: dict[str, Any],
) -> tuple[list[str], list[str]]:
    flags = _as_string_list(row.get("risk_flags"))
    operators = _as_string_list(row.get("operator_sequence"))
    actions: list[str] = []
    findings: list[str] = []

    if source_lookup_status != "source_hash_verified":
        return (
            ["fetch_source_for_hash_verification"],
            [f"source lookup is not verified: {source_lookup_status}"],
        )

    if "classification_text_without_classifier_operator" in flags:
        chain_has_classifier = _operator_has(operators, "classifier", ".classify", ".train")
        if marker_summary["has_classifier_marker"] and not chain_has_classifier:
            actions.append("repair_extractor_or_operator_retention_for_classifier_calls")
            findings.append("source contains classifier/train/classify evidence absent from retained chain")
        elif not marker_summary["has_classifier_marker"]:
            actions.append("rewrite_task_text_classification_claim_or_defer")
            findings.append("task text claims classification but verified source has no classifier marker")

    if "vector_or_training_label_text_without_vector_sampling_operator" in flags:
        chain_has_sampling = _operator_has(operators, "sampleregions", ".sample", "featurecollection")
        if marker_summary["has_sampling_marker"] and not chain_has_sampling:
            actions.append("repair_extractor_or_operator_retention_for_sampling_calls")
            findings.append("source contains sample/sampleRegions evidence absent from retained chain")
        elif marker_summary["has_feature_collection_marker"] and not chain_has_sampling:
            actions.append("separate_external_vector_context_from_core_operator_chain")
            findings.append("source contains FeatureCollection context but no sampling call in retained chain")
        else:
            actions.append("rewrite_task_text_label_vector_claim_or_defer")
            findings.append("task text mentions labels/vector evidence but verified source has no sampling marker")

    if "evaluation_text_without_evaluation_operator" in flags:
        chain_has_evaluation = _operator_has(operators, "errormatrix", "confusionmatrix", ".accuracy", ".kappa")
        if marker_summary["has_evaluation_marker"] and not chain_has_evaluation:
            actions.append("move_evaluation_to_sidecar_or_extend_evaluation_extractor")
            findings.append("source contains accuracy/confusion evidence absent from retained chain")
        elif not marker_summary["has_evaluation_marker"]:
            actions.append("rewrite_task_text_evaluation_claim_or_defer")
            findings.append("task text mentions evaluation but verified source has no evaluation marker")

    if "display_or_export_language_requires_core_boundary_check" in flags:
        if marker_summary["has_display_export_marker"]:
            actions.append("keep_display_export_as_noise_sidecar_not_training_target")
            findings.append("source contains Map/print/export/UI evidence; keep outside core training target")
        else:
            actions.append("rewrite_output_language_to_core_product")
            findings.append("task text has output/display language but source display/export marker not found")

    if "advanced_temporal_text_without_temporal_operator" in flags:
        if marker_summary["has_temporal_marker"]:
            actions.append("extend_extractor_for_temporal_module_or_sidecar_external_algorithm")
            findings.append("source contains temporal module/algorithm marker absent from retained chain")
        else:
            actions.append("rewrite_temporal_claim_or_defer")
            findings.append("task text claims advanced temporal analysis but source marker not found")

    if "regional_statistics_text_without_regional_operator" in flags:
        if marker_summary["has_regional_marker"]:
            actions.append("repair_extractor_or_l3_mapping_for_regional_statistics")
            findings.append("source contains regional statistics marker absent from retained chain")
        else:
            actions.append("rewrite_regional_statistics_claim_or_defer")
            findings.append("task text mentions regional statistics but source marker not found")

    if "complex_or_long_chain_review_priority" in flags:
        actions.append("manual_chain_boundary_review")
        findings.append("long or complex chain requires boundary review before rule promotion")

    if "prior_review_split_was_not_train_but_output_is_train_only" in flags:
        actions.append("retain_train_only_split_audit_note")
        findings.append("prior split is audit-only; row remains train-only unless separate gold gate is granted")

    if not actions:
        actions.append("no_source_backed_rule_change_suggested")
        findings.append("no source-backed systematic action identified from current marker set")

    return sorted(set(actions)), findings


def _source_status(source_cache_dir: Path, source_sha256: str) -> tuple[str, Path | None, str]:
    if not _SHA256_RE.fullmatch(str(source_sha256 or "")):
        return "source_sha256_invalid", None, ""
    path = _source_cache_path(source_cache_dir, source_sha256)
    if not path.is_file():
        return "source_missing", path, ""
    actual = _sha256(path)
    if actual != source_sha256:
        return "source_hash_mismatch", path, actual
    return "source_hash_verified", path, actual


def _audit_row(row: dict[str, Any], *, source_cache_dir: Path) -> dict[str, Any]:
    source_sha256 = str(row.get("source_sha256") or "")
    status, cache_path, actual_sha = _source_status(source_cache_dir, source_sha256)
    source_text = ""
    if status == "source_hash_verified" and cache_path is not None:
        source_text = cache_path.read_text(encoding="utf-8", errors="replace")
    markers = _marker_summary(source_text) if source_text else {
        f"{name}_count": 0 for name in SOURCE_MARKER_PATTERNS
    } | {f"has_{name}_marker": False for name in SOURCE_MARKER_PATTERNS}
    actions, findings = _recommendations(
        row,
        source_lookup_status=status,
        marker_summary=markers,
    )
    result = {
        "schema": ROW_SCHEMA,
        "review_role": REVIEW_ROLE,
        "review_priority": row.get("review_priority", ""),
        "audit_rank": row.get("audit_rank", ""),
        "risk_level": row.get("risk_level", ""),
        "risk_score": row.get("risk_score", ""),
        "risk_flags": _as_string_list(row.get("risk_flags")),
        "precheck_status": row.get("precheck_status", ""),
        "sample_id": row.get("sample_id", ""),
        "proposal_id": row.get("proposal_id", ""),
        "script_id": row.get("script_id", ""),
        "task_type": row.get("task_type", ""),
        "task_name": row.get("task_name", ""),
        "task_description": row.get("task_description", ""),
        "source_sha256": source_sha256,
        "source_sha256_actual": actual_sha,
        "source_sha256_verified": status == "source_hash_verified",
        "source_lookup_status": status,
        "source_path": row.get("source_path", ""),
        "source_cache_path": str(cache_path or ""),
        "source_marker_summary": markers,
        "source_evidence_snippets": _source_evidence_snippets(source_text),
        "source_backed_findings": findings,
        "recommended_rule_actions": actions,
        "operator_sequence": _as_string_list(row.get("operator_sequence")),
        "l3_code_sequence": _as_string_list(row.get("l3_code_sequence")),
        "validation_eligible": False,
        "test_eligible": False,
        "training_rows_emitted": 0,
        "mutated_training_package": False,
        "production_merge": "not_granted",
        "next_action": "adjudicate source-backed rule action; repair batch rule or move to sidecar, not row-by-row production editing",
    }
    result.update({field: "" for field in HUMAN_FIELDS})
    return result


def build_source_audit_packet(
    *,
    precheck_path: Path = DEFAULT_PRECHECK,
    source_cache_dir: Path = DEFAULT_SOURCE_CACHE,
    risk_level: str = "high",
    limit: int | None = None,
) -> SourceAuditPacketResult:
    input_rows = _load_jsonl(precheck_path)
    selected = [
        row for row in input_rows if str(row.get("risk_level") or "") == risk_level
    ]
    selected.sort(key=lambda row: int(row.get("review_priority") or 0))
    if limit is not None:
        selected = selected[:limit]

    rows = [_audit_row(row, source_cache_dir=Path(source_cache_dir)) for row in selected]
    source_status_counts = Counter(row["source_lookup_status"] for row in rows)
    action_counts = Counter(action for row in rows for action in row["recommended_rule_actions"])
    risk_flag_counts = Counter(flag for row in rows for flag in row["risk_flags"])
    summary = {
        "schema": SUMMARY_SCHEMA,
        "inputs": {
            "precheck": str(Path(precheck_path)),
            "source_cache_dir": str(Path(source_cache_dir)),
            "risk_level": risk_level,
            "limit": limit,
        },
        "counts": {
            "input_precheck_rows": len(input_rows),
            "selected_rows": len(selected),
            "source_audit_rows": len(rows),
            "source_hash_verified_rows": source_status_counts.get("source_hash_verified", 0),
            "source_missing_rows": source_status_counts.get("source_missing", 0),
            "source_hash_mismatch_rows": source_status_counts.get("source_hash_mismatch", 0),
            "training_rows_emitted": 0,
            "unique_source_sha256": len({row["source_sha256"] for row in rows}),
        },
        "source_lookup_status_counts": dict(sorted(source_status_counts.items())),
        "recommended_rule_action_counts": dict(sorted(action_counts.items())),
        "risk_flag_counts": dict(sorted(risk_flag_counts.items())),
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
            "source_backed_audit_only": True,
            "risk_flags_are_not_rejections": True,
            "do_not_edit_operator_or_l3_sequences": True,
            "do_not_mutate_train11397_package": True,
            "do_not_promote_gee_to_validation_or_test": True,
        },
    }
    return SourceAuditPacketResult(rows=rows, summary=summary)


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


def _csv_text(rows: list[dict[str, Any]]) -> str:
    output = io.StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=CSV_FIELDS, extrasaction="ignore")
    writer.writeheader()
    for row in rows:
        writer.writerow({field: _csv_value(row.get(field, "")) for field in CSV_FIELDS})
    return output.getvalue()


def _output_prefix_for_risk_level(risk_level: str) -> str:
    safe = re.sub(r"[^a-z0-9_]+", "_", str(risk_level or "").strip().lower())
    if not safe:
        raise ValueError("risk_level cannot be empty")
    return f"{safe}_v1"


def _render_report(result: SourceAuditPacketResult) -> str:
    summary = result.summary
    counts = summary["counts"]
    decision = summary["decision"]
    lines = [
        "# GEE Batch Source-Backed Audit Packet v1",
        "",
        "This packet reviews a selected GEE batch audit-precheck risk cluster against",
        "verified source files. It is used to decide whether systemic failures",
        "should repair extractor/text/mapping rules or move rows to sidecars.",
        "",
        "## Result",
        "",
        f"- Input precheck rows: {counts['input_precheck_rows']}",
        f"- Selected risk level: `{summary['inputs']['risk_level']}`",
        f"- Source-audit rows: {counts['source_audit_rows']}",
        f"- Source hash verified rows: {counts['source_hash_verified_rows']}",
        f"- Source missing rows: {counts['source_missing_rows']}",
        f"- Source hash mismatch rows: {counts['source_hash_mismatch_rows']}",
        f"- Training rows emitted: {decision['training_rows_emitted']}",
        f"- Mutated training package: {decision['mutated_training_package']}",
        f"- Validation eligible: {decision['validation_eligible']}",
        f"- Test eligible: {decision['test_eligible']}",
        "",
        "## Recommended rule actions",
        "",
    ]
    for action, count in summary["recommended_rule_action_counts"].items():
        lines.append(f"- `{action}`: {count}")
    lines.extend(
        [
            "",
            "## Boundary",
            "",
            "- Source-backed findings are rule-calibration evidence, not training admission.",
            "- Operator and L3 sequences are copied unchanged from the precheck rows.",
            "- GEE rows remain train-only and excluded from validation/test.",
            "",
        ]
    )
    return "\n".join(lines)


def resolve_output_paths(output_dir: Path, *, output_prefix: str = "high_v1") -> dict[str, Path]:
    output_dir = Path(output_dir)
    return {
        "jsonl": output_dir / f"{output_prefix}.jsonl",
        "csv": output_dir / f"{output_prefix}.csv",
        "summary": output_dir / f"{output_prefix}_summary.json",
        "report": output_dir / f"{output_prefix}_report.md",
        "hash_ledger": output_dir / f"{output_prefix}_hashes.json",
    }


def write_outputs(
    result: SourceAuditPacketResult,
    *,
    precheck_path: Path,
    source_cache_dir: Path,
    output_dir: Path,
    output_prefix: str | None = None,
) -> dict[str, Path]:
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    if output_prefix is None:
        output_prefix = _output_prefix_for_risk_level(str(result.summary["inputs"]["risk_level"]))
    paths = resolve_output_paths(output_dir, output_prefix=output_prefix)

    _atomic_write(paths["jsonl"], _jsonl_text(result.rows))
    _atomic_write(paths["csv"], _csv_text(result.rows))
    _atomic_write(
        paths["summary"],
        json.dumps(result.summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
    )
    _atomic_write(paths["report"], _render_report(result))

    selected_source_paths = sorted(
        {
            Path(str(row.get("source_cache_path")))
            for row in result.rows
            if str(row.get("source_cache_path") or "")
        }
    )
    source_files = {
        path.name: {
            "path": str(path),
            "sha256": _sha256(path),
            "bytes": path.stat().st_size,
        }
        for path in selected_source_paths
        if path.is_file()
    }
    ledger = {
        "schema": HASH_LEDGER_SCHEMA,
        "source_inputs": {
            "precheck": {
                "path": str(Path(precheck_path)),
                "sha256": _sha256(precheck_path),
            },
            "source_cache_files": source_files,
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
    parser.add_argument("--precheck", type=Path, default=DEFAULT_PRECHECK)
    parser.add_argument("--source-cache", type=Path, default=DEFAULT_SOURCE_CACHE)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--risk-level", default="high")
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--output-prefix", default=None)
    args = parser.parse_args(argv)

    result = build_source_audit_packet(
        precheck_path=args.precheck,
        source_cache_dir=args.source_cache,
        risk_level=args.risk_level,
        limit=args.limit,
    )
    return write_outputs(
        result,
        precheck_path=args.precheck,
        source_cache_dir=args.source_cache,
        output_dir=args.output_dir,
        output_prefix=args.output_prefix,
    )


if __name__ == "__main__":
    main()
