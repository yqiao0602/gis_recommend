#!/usr/bin/env python3
"""Build deterministic train-only rewrite sidecars for GEE audit rows.

This handles rows already routed by
`build_gee_batch_high_risk_rule_proposals.py` as text-rewrite candidates.
It joins the source-backed audit packet to recover `source_path`, rewrites task
text without changing the frozen operator/L3 chains, validates the candidate
rows against the GEE raster-core schema, and writes the remaining audit rows
to a fail-closed rule backlog.

It does not mutate `train11397_*`, does not start training, does not create
validation/test rows, and does not call an LLM.
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
import tempfile
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


DEFAULT_PACKAGE_DIR = (
    ROOT
    / "docs/reports/gee_raster_core_v1_review_split_2026-07-24"
    / "gee_raster_core_batch_training_package_v1"
)
DEFAULT_RULE_PROPS = DEFAULT_PACKAGE_DIR / "audit_rule_props_v1" / "rule_props_high_v1.jsonl"
DEFAULT_SOURCE_AUDIT = DEFAULT_PACKAGE_DIR / "audit_src_v1" / "high_v1.jsonl"
DEFAULT_OUTPUT_DIR = DEFAULT_PACKAGE_DIR / "audit_rewrites_v1"

ROW_SCHEMA = "gis_recommend.gee_raster_core_batch_rewrite.v1"
BACKLOG_SCHEMA = "gis_recommend.gee_raster_core_batch_rule_backlog.v1"
SUMMARY_SCHEMA = "gis_recommend.gee_raster_core_batch_rewrite_summary.v1"
HASH_LEDGER_SCHEMA = "gis_recommend.hash_ledger.v1"
TRAINING_ADMISSION = "not_granted_rewrite_sidecar_schema_gate_passed"
OUTPUT_PREFIX = "rewrite_candidates_v1"

REWRITE_CSV_FIELDS = (
    "review_id",
    "sample_id",
    "proposal_id",
    "script_id",
    "proposal_decision",
    "task_type",
    "task_name",
    "task_description",
    "original_task_name",
    "original_task_description",
    "operator_sequence",
    "l3_sequence",
    "known_omissions",
    "source_sha256",
    "source_path",
    "source_audit_join_status",
    "schema_gate_status",
    "training_admission",
    "validation_eligible",
    "test_eligible",
    "production_merge",
    "training_rows_emitted",
)

BACKLOG_CSV_FIELDS = (
    "sample_id",
    "proposal_id",
    "script_id",
    "proposal_decision",
    "task_name",
    "source_sha256",
    "source_path",
    "decision_reasons",
    "sidecar_requirements",
    "rule_repair_targets",
    "next_action",
    "training_admission",
    "validation_eligible",
    "test_eligible",
)


@dataclass(frozen=True)
class RewriteSpec:
    task_name: str
    task_description: str
    known_omissions: tuple[str, ...]


REWRITE_SPECS_BY_DECISION: dict[str, RewriteSpec] = {
    "rewrite_core_classifier_keep_eval_sidecar": RewriteSpec(
        task_name="Classify sea ice concentration from SAR object properties",
        task_description=(
            "The retained core workflow trains a Random Forest classifier using "
            "SAR HH/HV object-property features and labeled ice-concentration "
            "samples, then applies the classifier to create a sea-ice "
            "concentration raster output."
        ),
        known_omissions=(
            "external feature collections and labeled sample provenance are source context",
            "validation classifier",
            "confusion matrices and accuracy metrics",
            "Map display, print output, and display/export noise",
        ),
    ),
    "rewrite_core_raster_stats_text": RewriteSpec(
        task_name="Quantify built-up surface area from thresholded GHSL raster",
        task_description=(
            "Select and clip the GHSL built-up surface raster, derive equality "
            "and threshold masks for built-up categories, apply those masks to "
            "pixel area images, and summarize total and new built-up area with "
            "reduceRegion."
        ),
        known_omissions=(
            "map styling, display, and print outputs",
            "classified-map or built-up intensity visualization language",
            "broader urbanization interpretation beyond threshold-mask area statistics",
        ),
    ),
}

REWRITE_SPECS_BY_SAMPLE_ID: dict[str, RewriteSpec] = {
    "gee_raster_core_batch_v1_78327a27fc37eeec": RewriteSpec(
        task_name="Classify land cover from Sentinel-2 training samples",
        task_description=(
            "The retained core workflow filters Sentinel-2 imagery by region, "
            "date, and metadata, selects spectral bands, mosaics and averages "
            "the image collection, builds training sample regions, trains a "
            "Random Forest land-cover classifier, and applies it to generate "
            "classified land-cover rasters."
        ),
        known_omissions=(
            "external feature collections and labeled sample provenance are source context",
            "confusion matrices and accuracy metrics",
            "Map display, print output, and display/export noise",
        ),
    ),
}

FORBIDDEN_TEXT_MARKERS_BY_DECISION: dict[str, tuple[str, ...]] = {
    "rewrite_core_classifier_keep_eval_sidecar": (
        "validation",
        "confusion",
        "accuracy",
        "map.addlayer",
        "display",
        "export",
        "print ",
    ),
    "rewrite_core_raster_stats_text": (
        "classified map",
        "classification",
        "visual styling",
        "map.addlayer",
        "display",
        "export",
        "print ",
    ),
}


@dataclass(slots=True)
class HighRiskRewriteResult:
    rows: list[dict[str, Any]]
    train_rows: list[dict[str, Any]]
    backlog_rows: list[dict[str, Any]]
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
    digest = hashlib.sha256()
    with open(_filesystem_path(Path(path)), "rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _filesystem_path(path: Path) -> str:
    """Return a filesystem path string that is safe for long Windows paths."""

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


def _as_string_list(value: Any) -> list[str]:
    if not isinstance(value, (list, tuple)):
        return []
    return [str(item).strip() for item in value if str(item).strip()]


def _review_id(sample_id: str) -> str:
    prefix = "gee_raster_core_batch_v1_"
    suffix = sample_id[len(prefix) :] if sample_id.startswith(prefix) else sample_id
    if not suffix:
        raise ValueError("sample_id cannot be empty when building review_id")
    return f"gee_raster_core_batch_rewrite_{suffix}"


def _source_audit_by_sample_id(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    by_sample: dict[str, dict[str, Any]] = {}
    for row in rows:
        sample_id = str(row.get("sample_id") or "")
        if not sample_id:
            raise ValueError("source audit row is missing sample_id")
        if sample_id in by_sample:
            raise ValueError(f"duplicate source audit sample_id: {sample_id}")
        by_sample[sample_id] = row
    return by_sample


def _joined_source_row(row: dict[str, Any], source_by_sample: dict[str, dict[str, Any]]) -> dict[str, Any]:
    sample_id = str(row.get("sample_id") or "")
    source_row = source_by_sample.get(sample_id)
    if source_row is None:
        raise ValueError(f"missing source audit row for sample_id={sample_id!r}")
    if source_row.get("source_lookup_status") != "source_hash_verified":
        raise ValueError(f"source audit row is not hash-verified for sample_id={sample_id!r}")
    if source_row.get("source_sha256") != row.get("source_sha256"):
        raise ValueError(f"source_sha256 mismatch for sample_id={sample_id!r}")
    source_path = str(source_row.get("source_path") or "").strip()
    if not source_path:
        raise ValueError(f"source_path missing after source-audit join for sample_id={sample_id!r}")
    return source_row


def _evidence_snippet(row: dict[str, Any]) -> str:
    snippets = row.get("source_evidence_snippets") or []
    if not isinstance(snippets, list):
        return ""
    lines: list[str] = []
    for item in snippets[:12]:
        if not isinstance(item, dict):
            continue
        line = item.get("line", "")
        marker = item.get("marker", "")
        text = str(item.get("text") or "").strip()
        if text:
            lines.append(f"{line} [{marker}] {text}".strip())
    return "\n".join(lines).strip()


def _check_rewritten_text(decision: str, train_row: dict[str, Any]) -> None:
    text = f"{train_row['task_name']} {train_row['task_description']}".lower()
    forbidden = [
        marker
        for marker in FORBIDDEN_TEXT_MARKERS_BY_DECISION.get(decision, ())
        if marker in text
    ]
    if forbidden:
        raise ValueError(f"forbidden rewritten text markers for {train_row['review_id']}: {forbidden}")


def _rewrite_spec_for_row(row: dict[str, Any]) -> RewriteSpec:
    sample_id = str(row.get("sample_id") or "")
    if sample_id in REWRITE_SPECS_BY_SAMPLE_ID:
        return REWRITE_SPECS_BY_SAMPLE_ID[sample_id]
    decision = str(row.get("proposal_decision") or "")
    spec = REWRITE_SPECS_BY_DECISION.get(decision)
    if spec is None:
        raise ValueError(f"missing rewrite spec for proposal_decision={decision!r}")
    return spec


def _train_row(row: dict[str, Any], source_row: dict[str, Any], spec: RewriteSpec) -> dict[str, Any]:
    sample_id = str(row.get("sample_id") or "")
    evidence = _evidence_snippet(source_row) or _evidence_snippet(row)
    train_row = {
        "schema": TRAIN_ROW_SCHEMA,
        "review_id": _review_id(sample_id),
        "script_id": row.get("script_id", ""),
        "source_platform": "GEE",
        "target_platform": "L3",
        "training_scope": "core_subworkflow",
        "task_name": spec.task_name,
        "task_description": spec.task_description,
        "l3_sequence": _as_string_list(row.get("l3_code_sequence")),
        "operator_sequence": _as_string_list(row.get("operator_sequence")),
        "source_sha256": row.get("source_sha256", ""),
        "source_path": source_row.get("source_path", ""),
        "evidence_snippet": evidence,
        "admission_tier": "gee_core_p2_rewrite",
        "sample_weight": 0.5,
        "validation_eligible": False,
        "test_eligible": False,
        "description_policy": "rewritten_chain_faithful",
        "known_omissions": list(spec.known_omissions),
        "review_split": "train_only",
        "sample_id": sample_id,
        "proposal_id": row.get("proposal_id", ""),
        "task_type": row.get("task_type", ""),
        "proposal_decision": row.get("proposal_decision", ""),
        "training_admission": TRAINING_ADMISSION,
        "production_merge": "not_granted",
    }
    validate_core_train_row(train_row)
    _check_rewritten_text(str(row.get("proposal_decision") or ""), train_row)
    return train_row


def _rewrite_sidecar_row(
    row: dict[str, Any],
    *,
    source_row: dict[str, Any],
    train_row: dict[str, Any],
) -> dict[str, Any]:
    return {
        "schema": ROW_SCHEMA,
        **train_row,
        "original_task_name": row.get("task_name", ""),
        "original_task_description": row.get("task_description", ""),
        "source_audit_join_status": "source_hash_verified_path_joined",
        "source_marker_summary": source_row.get("source_marker_summary", {}),
        "source_backed_findings": row.get("source_backed_findings", []),
        "source_evidence_snippets": source_row.get("source_evidence_snippets", []),
        "decision_reasons": row.get("decision_reasons", []),
        "sidecar_requirements": row.get("sidecar_requirements", []),
        "rule_repair_targets": row.get("rule_repair_targets", []),
        "schema_gate_status": "schema_valid_train_only_candidate",
        "training_rows_emitted": 0,
        "next_action": (
            "keep as rewrite sidecar; only a later dataset-level admission gate may "
            "merge this into a regenerated train-only package"
        ),
    }


def _backlog_row(row: dict[str, Any], source_by_sample: dict[str, dict[str, Any]]) -> dict[str, Any]:
    source_row = source_by_sample.get(str(row.get("sample_id") or "")) or {}
    return {
        "schema": BACKLOG_SCHEMA,
        "sample_id": row.get("sample_id", ""),
        "proposal_id": row.get("proposal_id", ""),
        "script_id": row.get("script_id", ""),
        "proposal_decision": row.get("proposal_decision", ""),
        "task_name": row.get("task_name", ""),
        "task_description": row.get("task_description", ""),
        "source_sha256": row.get("source_sha256", ""),
        "source_path": source_row.get("source_path", ""),
        "decision_reasons": row.get("decision_reasons", []),
        "sidecar_requirements": row.get("sidecar_requirements", []),
        "rule_repair_targets": row.get("rule_repair_targets", []),
        "operator_sequence": _as_string_list(row.get("operator_sequence")),
        "l3_code_sequence": _as_string_list(row.get("l3_code_sequence")),
        "training_admission": "not_granted_high_risk_rule_backlog",
        "validation_eligible": False,
        "test_eligible": False,
        "production_merge": "not_granted",
        "next_action": _backlog_next_action(str(row.get("proposal_decision") or "")),
    }


def _backlog_next_action(decision: str) -> str:
    if decision == "defer_external_algorithm_sidecar":
        return "define external temporal module sidecar/exclusion policy before considering this family"
    if decision == "defer_manual_boundary_review":
        return "review external vector/training-label boundary and retained chain scope before admission"
    if decision == "defer_regional_statistics_mapping_repair":
        return "repair regional-statistics extractor/L3 mapping authority before admission"
    return "keep fail-closed until a source-backed rule owner resolves this decision"


def build_high_risk_rewrites(
    *,
    rule_props_path: Path = DEFAULT_RULE_PROPS,
    source_audit_path: Path = DEFAULT_SOURCE_AUDIT,
    output_prefix: str = OUTPUT_PREFIX,
) -> HighRiskRewriteResult:
    rule_rows = _load_jsonl(rule_props_path)
    source_rows = _load_jsonl(source_audit_path)
    source_by_sample = _source_audit_by_sample_id(source_rows)

    rewrite_rows: list[dict[str, Any]] = []
    train_rows: list[dict[str, Any]] = []
    backlog_rows: list[dict[str, Any]] = []

    for row in sorted(rule_rows, key=lambda item: int(item.get("review_priority") or 0)):
        if not row.get("candidate_for_text_rewrite_train_only"):
            backlog_rows.append(_backlog_row(row, source_by_sample))
            continue
        spec = _rewrite_spec_for_row(row)
        source_row = _joined_source_row(row, source_by_sample)
        train_row = _train_row(row, source_row, spec)
        rewrite_rows.append(
            _rewrite_sidecar_row(row, source_row=source_row, train_row=train_row)
        )
        train_rows.append(train_row)

    decision_counts = Counter(str(row.get("proposal_decision") or "") for row in rule_rows)
    backlog_decision_counts = Counter(row["proposal_decision"] for row in backlog_rows)
    omission_counts = Counter(item for row in rewrite_rows for item in row["known_omissions"])
    summary = {
        "schema": SUMMARY_SCHEMA,
        "output_prefix": output_prefix,
        "inputs": {
            "rule_props": str(Path(rule_props_path)),
            "source_audit": str(Path(source_audit_path)),
        },
        "counts": {
            "rule_proposal_rows": len(rule_rows),
            "source_audit_rows": len(source_rows),
            "rewrite_candidate_rows": len(rewrite_rows),
            "schema_valid_train_only_candidate_rows": len(train_rows),
            "deferred_backlog_rows": len(backlog_rows),
            "training_rows_emitted": 0,
            "validation_rows_emitted": 0,
            "test_rows_emitted": 0,
            "unique_rewrite_source_sha256": len({row["source_sha256"] for row in rewrite_rows}),
        },
        "proposal_decision_counts": dict(sorted(decision_counts.items())),
        "backlog_decision_counts": dict(sorted(backlog_decision_counts.items())),
        "risk_levels": sorted(
            {
                str(row.get("risk_level") or "")
                for row in [*rule_rows, *source_rows]
                if str(row.get("risk_level") or "")
            }
        ),
        "known_omission_counts": dict(sorted(omission_counts.items())),
        "rewrite_ids": [row["review_id"] for row in rewrite_rows],
        "backlog_sample_ids": [row["sample_id"] for row in backlog_rows],
        "decision": {
            "training_admission": TRAINING_ADMISSION,
            "validation_eligible": False,
            "test_eligible": False,
            "production_merge": "not_granted",
            "training_run_started": False,
            "llm_used": False,
            "mutated_train11397_package": False,
            "next_gate": (
                "use this sidecar for rule calibration; regenerate/merge any future "
                "batch training package only through a separate explicit admission gate"
            ),
        },
        "policy": {
            "rewrite_sidecar_only": True,
            "preserve_operator_order": True,
            "allow_operator_add_delete_reorder": False,
            "known_omissions_are_sidecar_only": True,
            "source_path_join_required": True,
            "do_not_mutate_train11397_package": True,
            "do_not_promote_gee_to_validation_or_test": True,
        },
    }
    return HighRiskRewriteResult(
        rows=rewrite_rows,
        train_rows=train_rows,
        backlog_rows=backlog_rows,
        summary=summary,
    )


def _atomic_write(path: Path, text: str) -> None:
    os.makedirs(_filesystem_path(path.parent), exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "w", encoding="utf-8", newline="", dir=_filesystem_path(path.parent), delete=False
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


def _csv_text(rows: list[dict[str, Any]], *, fieldnames: tuple[str, ...]) -> str:
    output = io.StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=fieldnames, extrasaction="ignore")
    writer.writeheader()
    for row in rows:
        writer.writerow({field: _csv_value(row.get(field, "")) for field in fieldnames})
    return output.getvalue()


def _render_report(result: HighRiskRewriteResult) -> str:
    summary = result.summary
    counts = summary["counts"]
    lines = [
        "# GEE Batch Source-Backed Rewrites",
        "",
        "This packet rewrites only the source-backed rows that were routed as",
        "train-only text-rewrite candidates. It keeps the frozen operator/L3",
        "chains unchanged and writes the other sampled audit rows to a",
        "fail-closed rule backlog.",
        "",
        "## Result",
        "",
        f"- Output prefix: `{summary['output_prefix']}`",
        f"- Rule-proposal rows: {counts['rule_proposal_rows']}",
        f"- Rewrite candidates: {counts['rewrite_candidate_rows']}",
        f"- Schema-valid train-only candidate rows: {counts['schema_valid_train_only_candidate_rows']}",
        f"- Deferred backlog rows: {counts['deferred_backlog_rows']}",
        f"- Training rows emitted into train11397 package: {counts['training_rows_emitted']}",
        f"- Validation rows emitted: {counts['validation_rows_emitted']}",
        f"- Test rows emitted: {counts['test_rows_emitted']}",
        f"- Training admission: `{summary['decision']['training_admission']}`",
        f"- Production merge: `{summary['decision']['production_merge']}`",
        f"- LLM used: `{summary['decision']['llm_used']}`",
        "",
        "## Rewritten rows",
        "",
    ]
    for row in result.rows:
        lines.extend(
            [
                f"### {row['review_id']}",
                "",
                f"- Proposal decision: `{row['proposal_decision']}`",
                f"- Task name: {row['task_name']}",
                f"- Task description: {row['task_description']}",
                f"- Operator calls retained: {len(row['operator_sequence'])}",
                f"- L3 calls retained: {len(row['l3_sequence'])}",
                f"- Known omissions: {', '.join(row['known_omissions'])}",
                "",
            ]
        )
    lines.extend(
        [
            "## Deferred rule backlog",
            "",
        ]
    )
    for row in result.backlog_rows:
        lines.append(
            f"- `{row['proposal_decision']}` / `{row['sample_id']}`: {row['next_action']}"
        )
    lines.extend(
        [
            "",
            "## Boundary",
            "",
            "- This sidecar does not append to or rewrite `train11397_full.json` / `train11397_v4_100.json`.",
            "- Candidate rows remain train-only and validation/test ineligible.",
            "- Operator and L3 sequences are copied from the source-backed rule proposal without reordering.",
            "",
        ]
    )
    return "\n".join(lines)


def _suffix_from_output_prefix(output_prefix: str) -> str:
    prefix = output_prefix.strip()
    if not prefix:
        raise ValueError("output_prefix cannot be empty")
    marker = "rewrite_candidates_"
    if prefix.startswith(marker):
        suffix = prefix[len(marker) :]
    else:
        suffix = prefix
    if not suffix:
        raise ValueError(f"cannot derive output suffix from output_prefix={output_prefix!r}")
    return suffix


def resolve_output_paths(output_dir: Path, *, output_prefix: str = OUTPUT_PREFIX) -> dict[str, Path]:
    output_dir = Path(output_dir)
    suffix = _suffix_from_output_prefix(output_prefix)
    return {
        "jsonl": output_dir / f"{output_prefix}.jsonl",
        "csv": output_dir / f"{output_prefix}.csv",
        "train_candidates_jsonl": output_dir / f"rewrite_train_only_candidates_{suffix}.jsonl",
        "backlog_jsonl": output_dir / f"deferred_rule_backlog_{suffix}.jsonl",
        "backlog_csv": output_dir / f"deferred_rule_backlog_{suffix}.csv",
        "summary": output_dir / f"{output_prefix}_summary.json",
        "report": output_dir / f"{output_prefix}_report.md",
        "hash_ledger": output_dir / f"{output_prefix}_hashes.json",
    }


def write_outputs(
    result: HighRiskRewriteResult,
    *,
    rule_props_path: Path,
    source_audit_path: Path,
    output_dir: Path,
    output_prefix: str = OUTPUT_PREFIX,
) -> dict[str, Path]:
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    paths = resolve_output_paths(output_dir, output_prefix=output_prefix)

    _atomic_write(paths["jsonl"], _jsonl_text(result.rows))
    _atomic_write(paths["csv"], _csv_text(result.rows, fieldnames=REWRITE_CSV_FIELDS))
    _atomic_write(paths["train_candidates_jsonl"], _jsonl_text(result.train_rows))
    _atomic_write(paths["backlog_jsonl"], _jsonl_text(result.backlog_rows))
    _atomic_write(paths["backlog_csv"], _csv_text(result.backlog_rows, fieldnames=BACKLOG_CSV_FIELDS))
    _atomic_write(
        paths["summary"],
        json.dumps(result.summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
    )
    _atomic_write(paths["report"], _render_report(result))

    ledger = {
        "schema": HASH_LEDGER_SCHEMA,
        "source_inputs": {
            "rule_props": {
                "path": str(Path(rule_props_path)),
                "sha256": _sha256(rule_props_path),
            },
            "source_audit": {
                "path": str(Path(source_audit_path)),
                "sha256": _sha256(source_audit_path),
            },
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
    _atomic_write(
        paths["hash_ledger"],
        json.dumps(ledger, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
    )
    return paths


def main(argv: list[str] | None = None) -> dict[str, Path]:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rule-props", type=Path, default=DEFAULT_RULE_PROPS)
    parser.add_argument("--source-audit", type=Path, default=DEFAULT_SOURCE_AUDIT)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--output-prefix", default=OUTPUT_PREFIX)
    args = parser.parse_args(argv)

    result = build_high_risk_rewrites(
        rule_props_path=args.rule_props,
        source_audit_path=args.source_audit,
        output_prefix=args.output_prefix,
    )
    return write_outputs(
        result,
        rule_props_path=args.rule_props,
        source_audit_path=args.source_audit,
        output_dir=args.output_dir,
        output_prefix=args.output_prefix,
    )


if __name__ == "__main__":
    main()
