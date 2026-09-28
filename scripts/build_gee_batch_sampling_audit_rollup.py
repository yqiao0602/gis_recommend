#!/usr/bin/env python3
"""Roll up GEE batch sampling-audit sidecars across high/medium/low risk layers.

This script reads only completed source-audit, rule-proposal, and
rewrite/backlog summaries.  It produces a compact calibration report and
fail-closed policy candidates for the 50-row audit sample.

It does not mutate `train11397_*`, does not emit training rows, does not create
validation/test rows, and does not call an LLM.
"""

from __future__ import annotations

import argparse
from collections import Counter
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
DEFAULT_OUTPUT_DIR = DEFAULT_PACKAGE_DIR / "audit_sampling_rollup_v1"
OUTPUT_PREFIX = "sampling_audit_rollup_v1"

SUMMARY_SCHEMA = "gis_recommend.gee_raster_core_batch_sampling_audit_rollup_summary.v1"
POLICY_SCHEMA = "gis_recommend.gee_raster_core_batch_sampling_audit_policy_candidate.v1"
HASH_LEDGER_SCHEMA = "gis_recommend.hash_ledger.v1"

RISK_LAYERS = ("high", "medium", "low")

SOURCE_AUDIT_SUMMARIES = {
    "high": ("audit_src_v1", "high_v1_summary.json"),
    "medium": ("audit_src_medium_v1", "medium_v1_summary.json"),
    "low": ("audit_src_low_v1", "low_v1_summary.json"),
}
RULE_PROPOSAL_SUMMARIES = {
    "high": ("audit_rule_props_v1", "rule_props_high_v1_summary.json"),
    "medium": ("audit_rule_props_medium_v1", "rule_props_medium_v1_summary.json"),
    "low": ("audit_rule_props_low_v1", "rule_props_low_v1_summary.json"),
}
REWRITE_SUMMARIES = {
    "high": ("audit_rewrites_v1", "rewrite_candidates_v1_summary.json"),
    "medium": ("audit_rewrites_medium_v1", "rewrite_candidates_medium_v1_summary.json"),
    "low": ("audit_rewrites_low_v1", "rewrite_candidates_low_v1_summary.json"),
}


class SamplingAuditRollupResult:
    def __init__(self, *, summary: dict[str, Any], policy_candidates: list[dict[str, Any]]) -> None:
        self.summary = summary
        self.policy_candidates = policy_candidates


def _json(path: Path) -> dict[str, Any]:
    with open(_filesystem_path(Path(path)), encoding="utf-8") as handle:
        row = json.load(handle)
    if not isinstance(row, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return row


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


def _summary_path(package_dir: Path, mapping: dict[str, tuple[str, str]], risk_level: str) -> Path:
    directory, filename = mapping[risk_level]
    return Path(package_dir) / directory / filename


def _counter_add(counter: Counter[str], mapping: dict[str, Any] | None) -> None:
    for key, value in (mapping or {}).items():
        counter[str(key)] += int(value)


def _policy(
    *,
    policy_id: str,
    support_count: int,
    evidence: list[str],
    recommended_action: str,
    applies_to_training_target: bool = False,
) -> dict[str, Any]:
    return {
        "schema": POLICY_SCHEMA,
        "policy_id": policy_id,
        "support_count": support_count,
        "evidence": evidence,
        "recommended_action": recommended_action,
        "applies_to_training_target": applies_to_training_target,
        "training_admission": "not_granted_policy_candidate",
        "validation_eligible": False,
        "test_eligible": False,
        "production_merge": "not_granted",
    }


def _policy_candidates(
    *,
    source_action_counts: Counter[str],
    proposal_decision_counts: Counter[str],
    sidecar_requirement_counts: Counter[str],
    rule_repair_target_counts: Counter[str],
) -> list[dict[str, Any]]:
    candidates = [
        _policy(
            policy_id="display_export_noise_sidecar",
            support_count=source_action_counts["keep_display_export_as_noise_sidecar_not_training_target"],
            evidence=["Map.addLayer/print/export/UI markers are frequent but not core L3 targets"],
            recommended_action="always keep display/export/UI evidence as sidecar unless a separate export target is explicitly admitted",
        ),
        _policy(
            policy_id="generic_rule_review_fail_closed",
            support_count=proposal_decision_counts["defer_generic_rule_review"],
            evidence=["many source-verified rows have no specific safe rewrite or repair rule"],
            recommended_action="keep generic rule-review rows fail-closed; do not use them to change or admit training rows",
        ),
        _policy(
            policy_id="manual_boundary_review_fail_closed",
            support_count=proposal_decision_counts["defer_manual_boundary_review"],
            evidence=["complex boundary cases need chain-scope review before any rule promotion"],
            recommended_action="keep manual-boundary rows out of training until a bounded structural rule is approved",
        ),
        _policy(
            policy_id="evaluation_metrics_sidecar",
            support_count=sidecar_requirement_counts["evaluation_metrics_sidecar_not_training_target"],
            evidence=["accuracy/confusion evidence appears around classifier workflows but is not part of retained core chain"],
            recommended_action="keep evaluation/confusion/accuracy as sidecar unless an evaluation-operator taxonomy rule is admitted",
        ),
        _policy(
            policy_id="external_context_sidecar",
            support_count=(
                sidecar_requirement_counts["external_vector_context_sidecar"]
                + sidecar_requirement_counts["vector_featurecollection_context_sidecar"]
                + sidecar_requirement_counts["external_algorithm_module_sidecar"]
            ),
            evidence=["external vector collections or external modules occur as context around core raster workflows"],
            recommended_action="record external context as provenance/sidecar; do not add it to target chains by inference",
        ),
        _policy(
            policy_id="rule_repair_before_regeneration",
            support_count=sum(rule_repair_target_counts.values()),
            evidence=["some rows need extractor or L3 mapping repair before safe regeneration"],
            recommended_action="repair rule families first; regenerate only through an explicit batch gate",
        ),
    ]
    return sorted(candidates, key=lambda row: (-row["support_count"], row["policy_id"]))


def build_sampling_audit_rollup(package_dir: Path = DEFAULT_PACKAGE_DIR) -> SamplingAuditRollupResult:
    package_dir = Path(package_dir)

    source_action_counts: Counter[str] = Counter()
    proposal_decision_counts: Counter[str] = Counter()
    sidecar_requirement_counts: Counter[str] = Counter()
    rule_repair_target_counts: Counter[str] = Counter()
    risk_layer_counts: dict[str, dict[str, int]] = {}
    source_inputs: dict[str, Path] = {}

    totals = Counter()
    for risk_level in RISK_LAYERS:
        source_path = _summary_path(package_dir, SOURCE_AUDIT_SUMMARIES, risk_level)
        proposal_path = _summary_path(package_dir, RULE_PROPOSAL_SUMMARIES, risk_level)
        rewrite_path = _summary_path(package_dir, REWRITE_SUMMARIES, risk_level)
        source_summary = _json(source_path)
        proposal_summary = _json(proposal_path)
        rewrite_summary = _json(rewrite_path)
        source_inputs[source_path.name] = source_path
        source_inputs[proposal_path.name] = proposal_path
        source_inputs[rewrite_path.name] = rewrite_path

        _counter_add(source_action_counts, source_summary.get("recommended_rule_action_counts"))
        _counter_add(proposal_decision_counts, proposal_summary.get("proposal_decision_counts"))
        _counter_add(sidecar_requirement_counts, proposal_summary.get("sidecar_requirement_counts"))
        _counter_add(rule_repair_target_counts, proposal_summary.get("rule_repair_target_counts"))

        layer_counts = {
            "source_audit_rows": int(source_summary["counts"]["source_audit_rows"]),
            "source_hash_verified_rows": int(source_summary["counts"]["source_hash_verified_rows"]),
            "rule_proposal_rows": int(proposal_summary["counts"]["proposal_rows"]),
            "rewrite_candidate_rows": int(proposal_summary["counts"]["rewrite_candidate_rows"]),
            "schema_valid_train_only_candidate_rows": int(
                rewrite_summary["counts"]["schema_valid_train_only_candidate_rows"]
            ),
            "deferred_backlog_rows": int(rewrite_summary["counts"]["deferred_backlog_rows"]),
            "training_rows_emitted": int(rewrite_summary["counts"]["training_rows_emitted"]),
        }
        risk_layer_counts[risk_level] = layer_counts
        totals.update(layer_counts)

    policies = _policy_candidates(
        source_action_counts=source_action_counts,
        proposal_decision_counts=proposal_decision_counts,
        sidecar_requirement_counts=sidecar_requirement_counts,
        rule_repair_target_counts=rule_repair_target_counts,
    )
    summary = {
        "schema": SUMMARY_SCHEMA,
        "inputs": {
            "package_dir": str(package_dir),
            "risk_layers": list(RISK_LAYERS),
        },
        "counts": {
            "risk_layers": len(RISK_LAYERS),
            "source_audit_rows": totals["source_audit_rows"],
            "source_hash_verified_rows": totals["source_hash_verified_rows"],
            "rule_proposal_rows": totals["rule_proposal_rows"],
            "rewrite_candidate_rows": totals["rewrite_candidate_rows"],
            "schema_valid_train_only_candidate_rows": totals[
                "schema_valid_train_only_candidate_rows"
            ],
            "deferred_backlog_rows": totals["deferred_backlog_rows"],
            "training_rows_emitted": totals["training_rows_emitted"],
            "policy_candidate_rows": len(policies),
        },
        "risk_layer_counts": risk_layer_counts,
        "source_action_counts": dict(sorted(source_action_counts.items())),
        "proposal_decision_counts": dict(sorted(proposal_decision_counts.items())),
        "sidecar_requirement_counts": dict(sorted(sidecar_requirement_counts.items())),
        "rule_repair_target_counts": dict(sorted(rule_repair_target_counts.items())),
        "policy_candidate_ids": [row["policy_id"] for row in policies],
        "decision": {
            "training_rows_emitted": 0,
            "mutated_train11397_package": False,
            "validation_eligible": False,
            "test_eligible": False,
            "production_merge": "not_granted",
            "training_run_started": False,
            "llm_used": False,
            "admission_change": "none",
            "next_gate": "formalize policy candidates or regenerate through an explicit batch gate",
        },
        "policy": {
            "rollup_only": True,
            "risk_flags_are_calibration_signals": True,
            "do_not_edit_operator_or_l3_sequences": True,
            "do_not_mutate_train11397_package": True,
            "do_not_promote_gee_to_validation_or_test": True,
        },
    }
    return SamplingAuditRollupResult(summary=summary, policy_candidates=policies)


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


def _render_report(result: SamplingAuditRollupResult) -> str:
    summary = result.summary
    counts = summary["counts"]
    lines = [
        "# GEE Batch Sampling-Audit Rollup v1",
        "",
        "This report aggregates the completed high/medium/low source-backed",
        "sampling audit sidecars for the 50-row GEE batch audit sample.",
        "",
        "## Result",
        "",
        f"- Source-audit rows: {counts['source_audit_rows']}",
        f"- Source hash verified rows: {counts['source_hash_verified_rows']}",
        f"- Rule proposal rows: {counts['rule_proposal_rows']}",
        f"- Deterministic rewrite sidecar candidates: {counts['rewrite_candidate_rows']}",
        f"- Schema-valid train-only sidecar candidates: {counts['schema_valid_train_only_candidate_rows']}",
        f"- Deferred/backlog rows: {counts['deferred_backlog_rows']}",
        f"- Training rows emitted: {counts['training_rows_emitted']}",
        "",
        "## Risk layers",
        "",
    ]
    for risk_level in RISK_LAYERS:
        layer = summary["risk_layer_counts"][risk_level]
        lines.append(
            f"- `{risk_level}`: source={layer['source_audit_rows']}, "
            f"rewrite={layer['rewrite_candidate_rows']}, backlog={layer['deferred_backlog_rows']}"
        )
    lines.extend(["", "## Policy candidates", ""])
    for row in result.policy_candidates:
        lines.append(
            f"- `{row['policy_id']}` support={row['support_count']}: "
            f"{row['recommended_action']}"
        )
    lines.extend(
        [
            "",
            "## Boundary",
            "",
            "- Rollup output is calibration evidence only.",
            "- It does not append to or rewrite `train11397_full.json` / `train11397_v4_100.json`.",
            "- GEE rows remain train-only and validation/test ineligible.",
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
        "summary": output_dir / f"{output_prefix}_summary.json",
        "policy_candidates": output_dir / f"{output_prefix}_policy_candidates.jsonl",
        "report": output_dir / f"{output_prefix}_report.md",
        "hash_ledger": output_dir / f"{output_prefix}_hashes.json",
    }


def _source_summary_paths(package_dir: Path) -> dict[str, Path]:
    paths: dict[str, Path] = {}
    for mapping in (SOURCE_AUDIT_SUMMARIES, RULE_PROPOSAL_SUMMARIES, REWRITE_SUMMARIES):
        for risk_level in RISK_LAYERS:
            path = _summary_path(package_dir, mapping, risk_level)
            paths[path.name] = path
    return paths


def write_outputs(
    result: SamplingAuditRollupResult,
    *,
    package_dir: Path,
    output_dir: Path,
    output_prefix: str = OUTPUT_PREFIX,
) -> dict[str, Path]:
    paths = resolve_output_paths(output_dir, output_prefix=output_prefix)
    _atomic_write(
        paths["summary"],
        json.dumps(result.summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
    )
    _atomic_write(paths["policy_candidates"], _jsonl_text(result.policy_candidates))
    _atomic_write(paths["report"], _render_report(result))

    source_inputs = {
        name: {
            "path": str(path),
            "sha256": _sha256(path),
            "bytes": os.path.getsize(_filesystem_path(path)),
        }
        for name, path in sorted(_source_summary_paths(Path(package_dir)).items())
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
    parser.add_argument("--package-dir", type=Path, default=DEFAULT_PACKAGE_DIR)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--output-prefix", default=OUTPUT_PREFIX)
    args = parser.parse_args(argv)

    result = build_sampling_audit_rollup(package_dir=args.package_dir)
    return write_outputs(
        result,
        package_dir=args.package_dir,
        output_dir=args.output_dir,
        output_prefix=args.output_prefix,
    )


if __name__ == "__main__":
    main()
