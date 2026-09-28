#!/usr/bin/env python3
"""Build a dry-run executable policy gate for the GEE 50-row sampling audit.

The gate materializes the six rollup policy candidates as row-level
fail-closed checks over the completed high/medium/low source-backed sampling
audit sidecars.  It is deliberately a dry run: no `train11397_*` file is read
for mutation, no training rows are emitted, no validation/test rows are
created, and no LLM is called.
"""

from __future__ import annotations

import argparse
from collections import Counter
import csv
import hashlib
import io
import json
import os
from pathlib import Path
import tempfile
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PACKAGE_DIR = (
    ROOT
    / "docs/reports/gee_raster_core_v1_review_split_2026-07-24"
    / "gee_raster_core_batch_training_package_v1"
)
DEFAULT_OUTPUT_DIR = DEFAULT_PACKAGE_DIR / "audit_sampling_policy_gate_v1"
OUTPUT_PREFIX = "sampling_policy_gate_v1"

ROW_SCHEMA = "gis_recommend.gee_raster_core_batch_sampling_policy_gate_row.v1"
SUMMARY_SCHEMA = "gis_recommend.gee_raster_core_batch_sampling_policy_gate_summary.v1"
HASH_LEDGER_SCHEMA = "gis_recommend.hash_ledger.v1"

RISK_LAYERS = ("high", "medium", "low")
SOURCE_AUDIT_FILES = {
    "high": ("audit_src_v1", "high_v1.jsonl"),
    "medium": ("audit_src_medium_v1", "medium_v1.jsonl"),
    "low": ("audit_src_low_v1", "low_v1.jsonl"),
}
RULE_PROPOSAL_FILES = {
    "high": ("audit_rule_props_v1", "rule_props_high_v1.jsonl"),
    "medium": ("audit_rule_props_medium_v1", "rule_props_medium_v1.jsonl"),
    "low": ("audit_rule_props_low_v1", "rule_props_low_v1.jsonl"),
}
ROLLUP_POLICY_CANDIDATES = (
    "audit_sampling_rollup_v1",
    "sampling_audit_rollup_v1_policy_candidates.jsonl",
)

EXTERNAL_CONTEXT_SIDECARS = {
    "external_vector_context_sidecar",
    "vector_featurecollection_context_sidecar",
    "external_algorithm_module_sidecar",
}

CSV_FIELDS = (
    "risk_level",
    "review_priority",
    "audit_rank",
    "sample_id",
    "proposal_id",
    "script_id",
    "task_type",
    "task_name",
    "proposal_decision",
    "gate_disposition",
    "policy_hits",
    "policy_hit_count",
    "source_sha256",
    "source_path",
    "source_lookup_status",
    "candidate_for_text_rewrite_train_only",
    "training_rows_emitted",
    "validation_eligible",
    "test_eligible",
    "production_merge",
)


class PolicyGateDryRunResult:
    def __init__(self, *, rows: list[dict[str, Any]], summary: dict[str, Any]) -> None:
        self.rows = rows
        self.summary = summary


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


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with open(_filesystem_path(Path(path)), encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            row = json.loads(line)
            if not isinstance(row, dict):
                raise ValueError(f"{path}:{line_number} must contain a JSON object")
            rows.append(row)
    return rows


def _as_string_list(value: Any) -> list[str]:
    if not isinstance(value, (list, tuple)):
        return []
    return [str(item).strip() for item in value if str(item).strip()]


def _input_path(package_dir: Path, mapping: dict[str, tuple[str, str]], risk_level: str) -> Path:
    directory, filename = mapping[risk_level]
    return Path(package_dir) / directory / filename


def _policy_candidates_path(package_dir: Path) -> Path:
    directory, filename = ROLLUP_POLICY_CANDIDATES
    return Path(package_dir) / directory / filename


def _source_audit_by_sample_id(package_dir: Path) -> dict[str, dict[str, Any]]:
    rows_by_sample: dict[str, dict[str, Any]] = {}
    for risk_level in RISK_LAYERS:
        for row in _load_jsonl(_input_path(package_dir, SOURCE_AUDIT_FILES, risk_level)):
            sample_id = str(row.get("sample_id") or "")
            if not sample_id:
                raise ValueError("source-audit row missing sample_id")
            if sample_id in rows_by_sample:
                raise ValueError(f"duplicate sample_id in source-audit rows: {sample_id}")
            rows_by_sample[sample_id] = row
    return rows_by_sample


def _rule_proposal_rows(package_dir: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for risk_level in RISK_LAYERS:
        for row in _load_jsonl(_input_path(package_dir, RULE_PROPOSAL_FILES, risk_level)):
            normalized = dict(row)
            if not normalized.get("risk_level"):
                normalized["risk_level"] = risk_level
            rows.append(normalized)
    rows.sort(key=lambda row: int(row.get("review_priority") or 0))
    return rows


def _policy_hits(source_row: dict[str, Any], proposal_row: dict[str, Any]) -> list[str]:
    actions = set(_as_string_list(source_row.get("recommended_rule_actions")))
    sidecars = set(_as_string_list(proposal_row.get("sidecar_requirements")))
    repairs = set(_as_string_list(proposal_row.get("rule_repair_targets")))
    decision = str(proposal_row.get("proposal_decision") or "")

    hits: list[str] = []
    if "keep_display_export_as_noise_sidecar_not_training_target" in actions:
        hits.append("display_export_noise_sidecar")
    if (
        "move_evaluation_to_sidecar_or_extend_evaluation_extractor" in actions
        or "evaluation_metrics_sidecar_not_training_target" in sidecars
    ):
        hits.append("evaluation_metrics_sidecar")
    if sidecars & EXTERNAL_CONTEXT_SIDECARS:
        hits.append("external_context_sidecar")
    if decision == "defer_generic_rule_review":
        hits.append("generic_rule_review_fail_closed")
    if decision == "defer_manual_boundary_review":
        hits.append("manual_boundary_review_fail_closed")
    if repairs:
        hits.append("rule_repair_before_regeneration")
    return sorted(set(hits))


def _gate_disposition(proposal_row: dict[str, Any]) -> str:
    if proposal_row.get("candidate_for_text_rewrite_train_only"):
        return "rewrite_sidecar_candidate_not_admitted"
    return "fail_closed_policy_backlog"


def _gate_row(source_row: dict[str, Any], proposal_row: dict[str, Any]) -> dict[str, Any]:
    hits = _policy_hits(source_row, proposal_row)
    return {
        "schema": ROW_SCHEMA,
        "risk_level": proposal_row.get("risk_level") or source_row.get("risk_level", ""),
        "review_priority": proposal_row.get("review_priority", ""),
        "audit_rank": proposal_row.get("audit_rank", ""),
        "sample_id": proposal_row.get("sample_id", ""),
        "proposal_id": proposal_row.get("proposal_id", ""),
        "script_id": proposal_row.get("script_id", ""),
        "task_type": proposal_row.get("task_type", ""),
        "task_name": proposal_row.get("task_name", ""),
        "task_description": proposal_row.get("task_description", ""),
        "proposal_decision": proposal_row.get("proposal_decision", ""),
        "gate_disposition": _gate_disposition(proposal_row),
        "policy_hits": hits,
        "policy_hit_count": len(hits),
        "source_sha256": proposal_row.get("source_sha256", ""),
        "source_path": source_row.get("source_path", ""),
        "source_lookup_status": source_row.get("source_lookup_status", ""),
        "candidate_for_text_rewrite_train_only": bool(
            proposal_row.get("candidate_for_text_rewrite_train_only")
        ),
        "decision_reasons": proposal_row.get("decision_reasons", []),
        "sidecar_requirements": proposal_row.get("sidecar_requirements", []),
        "rule_repair_targets": proposal_row.get("rule_repair_targets", []),
        "recommended_rule_actions": source_row.get("recommended_rule_actions", []),
        "training_admission": "not_granted_policy_gate_dry_run",
        "training_rows_emitted": 0,
        "validation_eligible": False,
        "test_eligible": False,
        "production_merge": "not_granted",
        "next_action": "formalize policy and rerun batch gate before any regeneration",
    }


def build_policy_gate_dry_run(package_dir: Path = DEFAULT_PACKAGE_DIR) -> PolicyGateDryRunResult:
    package_dir = Path(package_dir)
    source_by_sample = _source_audit_by_sample_id(package_dir)
    proposal_rows = _rule_proposal_rows(package_dir)
    policy_candidates = _load_jsonl(_policy_candidates_path(package_dir))

    rows: list[dict[str, Any]] = []
    for proposal_row in proposal_rows:
        sample_id = str(proposal_row.get("sample_id") or "")
        source_row = source_by_sample.get(sample_id)
        if source_row is None:
            raise ValueError(f"missing source-audit row for sample_id={sample_id!r}")
        rows.append(_gate_row(source_row, proposal_row))

    policy_hit_counts = Counter(policy for row in rows for policy in row["policy_hits"])
    gate_disposition_counts = Counter(row["gate_disposition"] for row in rows)
    risk_level_counts = Counter(str(row.get("risk_level") or "") for row in rows)
    source_status_counts = Counter(str(source_by_sample[row["sample_id"]].get("source_lookup_status") or "") for row in rows)

    summary = {
        "schema": SUMMARY_SCHEMA,
        "inputs": {
            "package_dir": str(package_dir),
            "source_audit_layers": list(RISK_LAYERS),
            "rule_proposal_layers": list(RISK_LAYERS),
            "rollup_policy_candidates": str(_policy_candidates_path(package_dir)),
        },
        "counts": {
            "gate_rows": len(rows),
            "source_hash_verified_rows": source_status_counts.get("source_hash_verified", 0),
            "policy_candidate_rows": len(policy_candidates),
            "rewrite_sidecar_candidate_rows": gate_disposition_counts.get(
                "rewrite_sidecar_candidate_not_admitted",
                0,
            ),
            "fail_closed_backlog_rows": gate_disposition_counts.get(
                "fail_closed_policy_backlog",
                0,
            ),
            "training_rows_emitted": 0,
        },
        "risk_level_counts": dict(sorted(risk_level_counts.items())),
        "source_lookup_status_counts": dict(sorted(source_status_counts.items())),
        "gate_disposition_counts": dict(sorted(gate_disposition_counts.items())),
        "policy_hit_counts": dict(sorted(policy_hit_counts.items())),
        "decision": {
            "training_rows_emitted": 0,
            "mutated_train11397_package": False,
            "validation_eligible": False,
            "test_eligible": False,
            "production_merge": "not_granted",
            "training_run_started": False,
            "llm_used": False,
            "admission_change": "none",
            "dry_run_only": True,
        },
        "policy": {
            "do_not_edit_operator_or_l3_sequences": True,
            "do_not_mutate_train11397_package": True,
            "do_not_promote_gee_to_validation_or_test": True,
            "formalize_before_regeneration": True,
        },
    }
    return PolicyGateDryRunResult(rows=rows, summary=summary)


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


def _csv_text(rows: list[dict[str, Any]]) -> str:
    output = io.StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=CSV_FIELDS, extrasaction="ignore")
    writer.writeheader()
    for row in rows:
        writer.writerow({field: _csv_value(row.get(field, "")) for field in CSV_FIELDS})
    return output.getvalue()


def _render_report(result: PolicyGateDryRunResult) -> str:
    summary = result.summary
    counts = summary["counts"]
    lines = [
        "# GEE Batch Sampling Policy Gate Dry Run v1",
        "",
        "This dry run materializes the rollup policy candidates as row-level",
        "fail-closed gate decisions over the 50 source-backed sampling-audit rows.",
        "",
        "## Result",
        "",
        f"- Gate rows: {counts['gate_rows']}",
        f"- Source hash verified rows: {counts['source_hash_verified_rows']}",
        f"- Rewrite sidecar candidates not admitted: {counts['rewrite_sidecar_candidate_rows']}",
        f"- Fail-closed backlog rows: {counts['fail_closed_backlog_rows']}",
        f"- Training rows emitted: {counts['training_rows_emitted']}",
        "",
        "## Policy hits",
        "",
    ]
    for policy_id, count in summary["policy_hit_counts"].items():
        lines.append(f"- `{policy_id}`: {count}")
    lines.extend(
        [
            "",
            "## Boundary",
            "",
            "- Dry-run rows are not accepted training rows.",
            "- This artifact does not append to or rewrite `train11397_*`.",
            "- Validation/test and production merge remain forbidden.",
            "",
        ]
    )
    return "\n".join(lines)


def resolve_output_paths(
    output_dir: Path,
    *,
    output_prefix: str = OUTPUT_PREFIX,
) -> dict[str, Path]:
    output_dir = Path(output_dir)
    return {
        "jsonl": output_dir / f"{output_prefix}.jsonl",
        "csv": output_dir / f"{output_prefix}.csv",
        "summary": output_dir / f"{output_prefix}_summary.json",
        "report": output_dir / f"{output_prefix}_report.md",
        "hash_ledger": output_dir / f"{output_prefix}_hashes.json",
    }


def _source_input_paths(package_dir: Path) -> dict[str, Path]:
    paths: dict[str, Path] = {
        _policy_candidates_path(package_dir).name: _policy_candidates_path(package_dir)
    }
    for mapping in (SOURCE_AUDIT_FILES, RULE_PROPOSAL_FILES):
        for risk_level in RISK_LAYERS:
            path = _input_path(package_dir, mapping, risk_level)
            paths[path.name] = path
    return paths


def write_outputs(
    result: PolicyGateDryRunResult,
    *,
    package_dir: Path,
    output_dir: Path,
    output_prefix: str = OUTPUT_PREFIX,
) -> dict[str, Path]:
    paths = resolve_output_paths(output_dir, output_prefix=output_prefix)
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
            name: {
                "path": str(path),
                "sha256": _sha256(path),
                "bytes": os.path.getsize(_filesystem_path(path)),
            }
            for name, path in sorted(_source_input_paths(Path(package_dir)).items())
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
    parser.add_argument("--package-dir", type=Path, default=DEFAULT_PACKAGE_DIR)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--output-prefix", default=OUTPUT_PREFIX)
    args = parser.parse_args(argv)

    result = build_policy_gate_dry_run(package_dir=args.package_dir)
    return write_outputs(
        result,
        package_dir=args.package_dir,
        output_dir=args.output_dir,
        output_prefix=args.output_prefix,
    )


if __name__ == "__main__":
    main()
