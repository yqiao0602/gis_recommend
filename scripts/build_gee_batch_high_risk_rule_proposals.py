#!/usr/bin/env python3
"""Convert GEE high-risk source-audit findings into rule-action proposals.

This is still an audit sidecar, not training admission.  The output proposes
whether each source-verified high-risk row should be rewritten, deferred to a
sidecar, or used to repair extractor/mapping rules.
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
import tempfile
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PACKAGE_DIR = (
    ROOT
    / "docs/reports/gee_raster_core_v1_review_split_2026-07-24"
    / "gee_raster_core_batch_training_package_v1"
)
DEFAULT_SOURCE_AUDIT = DEFAULT_PACKAGE_DIR / "audit_src_v1" / "high_v1.jsonl"
DEFAULT_OUTPUT_DIR = DEFAULT_PACKAGE_DIR / "audit_rule_props_v1"

ROW_SCHEMA = "gis_recommend.gee_raster_core_batch_high_risk_rule_proposal.v1"
SUMMARY_SCHEMA = "gis_recommend.gee_raster_core_batch_high_risk_rule_proposal_summary.v1"
HASH_LEDGER_SCHEMA = "gis_recommend.hash_ledger.v1"
REVIEW_ROLE = "source_backed_sampling_risk_rule_proposal"

HUMAN_FIELDS = (
    "human_accepts_proposal",
    "human_final_decision",
    "human_required_rule_change",
    "human_notes",
    "adjudicated_by",
    "adjudicated_at",
)

CSV_FIELDS = (
    "review_priority",
    "audit_rank",
    "risk_level",
    "proposal_decision",
    "candidate_for_text_rewrite_train_only",
    "decision_reasons",
    "sidecar_requirements",
    "rule_repair_targets",
    "sample_id",
    "task_name",
    "source_sha256",
    "source_lookup_status",
    "risk_flags",
    "recommended_rule_actions",
    "operator_sequence",
    "l3_code_sequence",
    "training_rows_emitted",
    "validation_eligible",
    "test_eligible",
    *HUMAN_FIELDS,
)


@dataclass(frozen=True)
class RuleProposalResult:
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


def _marker(row: dict[str, Any], marker: str) -> bool:
    summary = row.get("source_marker_summary") or {}
    return bool(summary.get(marker))


def _operator_has(operators: list[str], *needles: str) -> bool:
    lowered = [operator.lower() for operator in operators]
    return any(needle.lower() in operator for operator in lowered for needle in needles)


def _classify_row(row: dict[str, Any]) -> tuple[str, bool, list[str], list[str], list[str]]:
    actions = set(_as_string_list(row.get("recommended_rule_actions")))
    flags = set(_as_string_list(row.get("risk_flags")))
    operators = _as_string_list(row.get("operator_sequence"))
    reasons: list[str] = []
    sidecars: list[str] = []
    repairs: list[str] = []

    if row.get("source_lookup_status") != "source_hash_verified":
        return (
            "defer_until_source_verified",
            False,
            ["source_not_hash_verified"],
            ["source_fetch_or_hash_repair"],
            [],
        )

    if "extend_extractor_for_temporal_module_or_sidecar_external_algorithm" in actions:
        reasons.append("external_temporal_module_not_in_retained_chain")
        sidecars.append("external_algorithm_module_sidecar")
        repairs.append("temporal_module_extractor_or_external_algorithm_policy")
        return "defer_external_algorithm_sidecar", False, reasons, sidecars, repairs

    if "repair_extractor_or_l3_mapping_for_regional_statistics" in actions:
        reasons.append("regional_statistics_source_marker_missing_from_retained_chain")
        repairs.append("regional_statistics_extractor_or_l3_mapping")
        sidecars.append("vector_featurecollection_context_sidecar")
        return "defer_regional_statistics_mapping_repair", False, reasons, sidecars, repairs

    chain_has_classifier = _operator_has(operators, "classifier", ".classify", ".train")
    if (
        "move_evaluation_to_sidecar_or_extend_evaluation_extractor" in actions
        and chain_has_classifier
    ):
        reasons.append("core_classifier_chain_retained")
        reasons.append("evaluation_metrics_not_in_retained_chain")
        sidecars.append("evaluation_metrics_sidecar_not_training_target")
        sidecars.append("display_export_noise_sidecar")
        repairs.append("optional_evaluation_extractor")
        return "rewrite_core_classifier_keep_eval_sidecar", True, reasons, sidecars, repairs

    chain_has_raster_stats = _operator_has(operators, "pixelarea", "reduceregion", "reduceregions")
    if (
        "classification_text_without_classifier_operator" in flags
        and chain_has_raster_stats
        and not _marker(row, "has_classifier_marker")
    ):
        reasons.append("classification_text_overstates_threshold_or_area_workflow")
        sidecars.append("display_export_noise_sidecar")
        return "rewrite_core_raster_stats_text", True, reasons, sidecars, []

    if "manual_chain_boundary_review" in actions:
        reasons.append("complex_or_long_chain_requires_boundary_review")
        sidecars.append("external_vector_context_sidecar")
        return "defer_manual_boundary_review", False, reasons, sidecars, []

    if "rewrite_task_text_classification_claim_or_defer" in actions:
        reasons.append("classification_text_has_no_verified_classifier_marker")
        sidecars.append("display_export_noise_sidecar")
        return "rewrite_or_defer_text_overclaim", False, reasons, sidecars, []

    reasons.append("no_specific_high_risk_rule_proposal")
    return "defer_generic_rule_review", False, reasons, sidecars, repairs


def _proposal_row(row: dict[str, Any]) -> dict[str, Any]:
    decision, rewrite_candidate, reasons, sidecars, repairs = _classify_row(row)
    proposal = {
        "schema": ROW_SCHEMA,
        "review_role": REVIEW_ROLE,
        "review_priority": row.get("review_priority", ""),
        "audit_rank": row.get("audit_rank", ""),
        "risk_level": row.get("risk_level", ""),
        "proposal_decision": decision,
        "candidate_for_text_rewrite_train_only": rewrite_candidate,
        "decision_reasons": reasons,
        "sidecar_requirements": sidecars,
        "rule_repair_targets": repairs,
        "sample_id": row.get("sample_id", ""),
        "proposal_id": row.get("proposal_id", ""),
        "script_id": row.get("script_id", ""),
        "task_name": row.get("task_name", ""),
        "task_description": row.get("task_description", ""),
        "task_type": row.get("task_type", ""),
        "source_sha256": row.get("source_sha256", ""),
        "source_lookup_status": row.get("source_lookup_status", ""),
        "source_marker_summary": row.get("source_marker_summary", {}),
        "source_backed_findings": row.get("source_backed_findings", []),
        "source_evidence_snippets": row.get("source_evidence_snippets", []),
        "risk_flags": _as_string_list(row.get("risk_flags")),
        "recommended_rule_actions": _as_string_list(row.get("recommended_rule_actions")),
        "operator_sequence": _as_string_list(row.get("operator_sequence")),
        "l3_code_sequence": _as_string_list(row.get("l3_code_sequence")),
        "training_rows_emitted": 0,
        "training_admission": "not_granted_rule_proposal_only",
        "validation_eligible": False,
        "test_eligible": False,
        "production_merge": "not_granted",
        "next_action": "human/rule-owner confirms proposal, then repair rules or move row family to sidecar",
    }
    proposal.update({field: "" for field in HUMAN_FIELDS})
    return proposal


def build_rule_proposals(source_audit_path: Path = DEFAULT_SOURCE_AUDIT) -> RuleProposalResult:
    source_rows = _load_jsonl(source_audit_path)
    rows = [_proposal_row(row) for row in sorted(source_rows, key=lambda r: int(r.get("review_priority") or 0))]
    risk_levels = sorted({str(row.get("risk_level") or "") for row in rows if str(row.get("risk_level") or "")})
    risk_level = risk_levels[0] if len(risk_levels) == 1 else "mixed"
    decision_counts = Counter(row["proposal_decision"] for row in rows)
    sidecar_counts = Counter(item for row in rows for item in row["sidecar_requirements"])
    repair_counts = Counter(item for row in rows for item in row["rule_repair_targets"])
    summary = {
        "schema": SUMMARY_SCHEMA,
        "inputs": {
            "source_audit": str(Path(source_audit_path)),
            "risk_level": risk_level,
        },
        "counts": {
            "source_audit_rows": len(source_rows),
            "proposal_rows": len(rows),
            "rewrite_candidate_rows": sum(1 for row in rows if row["candidate_for_text_rewrite_train_only"]),
            "deferred_or_rule_repair_rows": sum(
                1 for row in rows if not row["candidate_for_text_rewrite_train_only"]
            ),
            "training_rows_emitted": 0,
            "unique_source_sha256": len({row["source_sha256"] for row in rows}),
        },
        "proposal_decision_counts": dict(sorted(decision_counts.items())),
        "sidecar_requirement_counts": dict(sorted(sidecar_counts.items())),
        "rule_repair_target_counts": dict(sorted(repair_counts.items())),
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
            "proposal_only": True,
            "requires_human_or_rule_owner_confirmation": True,
            "do_not_edit_operator_or_l3_sequences": True,
            "do_not_mutate_train11397_package": True,
            "do_not_promote_gee_to_validation_or_test": True,
        },
    }
    return RuleProposalResult(rows=rows, summary=summary)


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


def _render_report(result: RuleProposalResult) -> str:
    summary = result.summary
    counts = summary["counts"]
    decision = summary["decision"]
    lines = [
        "# GEE Batch Source-Backed Rule Proposals v1",
        "",
        "This packet converts source-backed audit findings for one risk layer into",
        "proposal-only routing decisions. It does not grant training admission.",
        "",
        "## Result",
        "",
        f"- Source-audit rows: {counts['source_audit_rows']}",
        f"- Proposal rows: {counts['proposal_rows']}",
        f"- Rewrite-candidate rows: {counts['rewrite_candidate_rows']}",
        f"- Deferred/rule-repair rows: {counts['deferred_or_rule_repair_rows']}",
        f"- Training rows emitted: {decision['training_rows_emitted']}",
        f"- Validation eligible: {decision['validation_eligible']}",
        f"- Test eligible: {decision['test_eligible']}",
        "",
        "## Proposal decisions",
        "",
    ]
    for name, count in summary["proposal_decision_counts"].items():
        lines.append(f"- `{name}`: {count}")
    lines.extend(
        [
            "",
            "## Rule repair targets",
            "",
        ]
    )
    for name, count in summary["rule_repair_target_counts"].items():
        lines.append(f"- `{name}`: {count}")
    lines.extend(
        [
            "",
            "## Boundary",
            "",
            "- Proposal rows are not accepted training rows.",
            "- Operator/L3 sequences are copied unchanged from source-audit rows.",
            "- Any rewrite candidate still requires a separate train-only export gate.",
            "",
        ]
    )
    return "\n".join(lines)


def _output_prefix_for_risk_level(risk_level: str) -> str:
    safe = "".join(
        char if char.isalnum() or char == "_" else "_"
        for char in str(risk_level or "").strip().lower()
    )
    if not safe:
        raise ValueError("risk_level cannot be empty")
    return f"rule_props_{safe}_v1"


def resolve_output_paths(output_dir: Path, *, output_prefix: str = "rule_props_high_v1") -> dict[str, Path]:
    output_dir = Path(output_dir)
    return {
        "jsonl": output_dir / f"{output_prefix}.jsonl",
        "csv": output_dir / f"{output_prefix}.csv",
        "summary": output_dir / f"{output_prefix}_summary.json",
        "report": output_dir / f"{output_prefix}_report.md",
        "hash_ledger": output_dir / f"{output_prefix}_hashes.json",
    }


def write_outputs(
    result: RuleProposalResult,
    *,
    source_audit_path: Path,
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

    ledger = {
        "schema": HASH_LEDGER_SCHEMA,
        "source_inputs": {
            "source_audit": {
                "path": str(Path(source_audit_path)),
                "sha256": _sha256(source_audit_path),
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
    parser.add_argument("--source-audit", type=Path, default=DEFAULT_SOURCE_AUDIT)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--output-prefix", default=None)
    args = parser.parse_args(argv)

    result = build_rule_proposals(source_audit_path=args.source_audit)
    return write_outputs(
        result,
        source_audit_path=args.source_audit,
        output_dir=args.output_dir,
        output_prefix=args.output_prefix,
    )


if __name__ == "__main__":
    main()
