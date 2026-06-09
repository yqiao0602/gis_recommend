# -*- coding: utf-8 -*-
"""Report generation and persistence for the evaluation pipeline.

Extracted from scripts/evaluate_system.py (2026-04-16). Handles:
  - Path slugification and archive naming
  - Terminal-friendly report printing
  - JSON report assembly and writing

Public API:
    slugify_report_tag(tag)
    build_report_archive_path(tag, now)
    resolve_report_output_paths(report_out, report_tag, now)
    write_json_report(report, output_path)
    print_report(test_set, seq_metrics, agg, chain_results, by_type)
    build_report_json(...)
"""
from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Optional

from gis_recommend.config.transformer_config import OUTPUT_DIR
from gis_recommend.evaluation.semantic_metrics import (
    SeqMetrics, AggregateMetrics,
)
from gis_recommend.evaluation.shadow_phase import (
    build_candidate_pool_trace,
    build_evidence_bundle,
    build_shadow_decision_core,
    select_evidence_aware_candidate,
)

REPORT_PATH = OUTPUT_DIR / "evaluation_report.json"
REPORT_ARCHIVE_DIR = OUTPUT_DIR / "evaluation_reports"


def slugify_report_tag(report_tag: Optional[str]) -> str:
    """Convert a human label into a stable filename fragment."""
    if not report_tag:
        return ""
    slug = re.sub(r"[^A-Za-z0-9._-]+", "-", report_tag.strip())
    slug = slug.strip("-._")
    return slug.lower()


def build_report_archive_path(
    report_tag: Optional[str] = None,
    now: Optional[datetime] = None,
) -> Path:
    """Build a timestamped archive report path for one evaluation run."""
    timestamp = (now or datetime.now()).strftime("%Y%m%d-%H%M%S")
    slug = slugify_report_tag(report_tag)
    filename = f"evaluation-report-{timestamp}.json"
    if slug:
        filename = f"evaluation-report-{slug}-{timestamp}.json"
    return REPORT_ARCHIVE_DIR / filename


def resolve_report_output_paths(
    report_out: Optional[str],
    report_tag: Optional[str] = None,
    now: Optional[datetime] = None,
) -> list[Path]:
    """Return all report destinations for the current run.

    Always keep the latest report at REPORT_PATH.
    Persist one additional copy either to the explicit destination or to a timestamped archive.
    """
    targets = [REPORT_PATH]
    extra_path = Path(report_out) if report_out else build_report_archive_path(report_tag=report_tag, now=now)
    if extra_path not in targets:
        targets.append(extra_path)
    return targets


def write_json_report(report: dict, output_path: Path) -> None:
    """Write a JSON report and create parent directories if needed."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)


def print_report(
    test_set: list,
    seq_metrics: list[SeqMetrics],
    agg: AggregateMetrics,
    chain_results: Optional[list],
    by_type: dict,
):
    """Print evaluation report to console."""
    print("\n" + "=" * 70)
    print(f"  L3 Generation Evaluation (N={agg.n})")
    print("=" * 70)
    print(f"  Token Accuracy (Top-1):  {agg.token_accuracy*100:6.2f}%   <- positional exact match")
    print(f"  Sequence Exact Match:    {agg.sequence_em*100:6.2f}%   <- full sequence match")
    print(f"  Set F1 (token overlap):  {agg.set_f1*100:6.2f}%   <- token set overlap")
    print(f"  Soft Set Sim:            {agg.soft_set_sim:6.4f}    <- avg best-match cosine")
    print(f"  L2-Set F1:               {agg.l2_set_f1*100:6.2f}%   <- L2 category overlap")
    print(f"  L2-Positional Accuracy:  {agg.l2_accuracy*100:6.2f}%   <- positional L2 match")
    print(f"  LCS Ratio:               {agg.lcs_ratio:6.4f}    <- subsequence overlap")
    print(f"  Length Ratio (mean):      {agg.length_ratio:6.4f}")

    if chain_results:
        valid_chains = [c for c in chain_results if c.get("total_steps", 0) > 0]
        if valid_chains:
            avg_cov = sum(c["coverage"] for c in valid_chains) / len(valid_chains)
            avg_val = sum(c["validity"] for c in valid_chains) / len(valid_chains)
            avg_exist = sum(c.get("existence_validity", c["validity"]) for c in valid_chains) / len(valid_chains)
            avg_struct = sum(c.get("structural_validity", c["validity"]) for c in valid_chains) / len(valid_chains)
            avg_io = sum(c["io_compatibility"] for c in valid_chains) / len(valid_chains)
            avg_conf = sum(c["chain_confidence"] for c in valid_chains) / len(valid_chains)

            print(f"\n{'=' * 70}")
            print(f"  QGIS Chain Evaluation (N={len(valid_chains)})")
            print(f"{'=' * 70}")
            print(f"  Coverage Score:    {avg_cov:6.4f}    <- % non-UNKNOWN steps")
            print(f"  Validity Score:    {avg_val:6.4f}    <- composite chain quality")
            print(f"  Exist. Validity:   {avg_exist:6.4f}    <- % non-UNKNOWN steps found in KG")
            print(f"  Struct. Validity:  {avg_struct:6.4f}    <- issue/critical-unknown penalty")
            print(f"  I/O Compatibility: {avg_io:6.4f}    <- % compatible pairs")
            print(f"  Chain Confidence:  {avg_conf:6.4f}    <- combined score")

    print(f"\n{'=' * 70}")
    print(f"  Breakdown by Task Type")
    print(f"{'=' * 70}")
    header = f"  {'Task Type':<40} {'N':>4} {'SetF1':>6} {'SoftSim':>8} {'L2F1':>6} {'LCS':>6} {'TokAcc':>7}"
    if chain_results:
        header += f" {'Cov':>6} {'Val':>6} {'Str':>6} {'I/O':>6}"
    print(header)
    print("  " + "-" * len(header.strip()))

    for tt in sorted(by_type.keys()):
        info = by_type[tt]
        line = f"  {tt:<40} {info['n']:>4} {info['set_f1']*100:>5.1f}% {info['soft_set_sim']:>8.4f} {info['l2_set_f1']*100:>5.1f}% {info['lcs_ratio']:>6.4f} {info['token_accuracy']*100:>6.1f}%"
        if chain_results and "coverage" in info:
            line += f" {info['coverage']:>6.3f} {info['validity']:>6.3f} {info.get('structural_validity', info['validity']):>6.3f} {info['io_compatibility']:>6.3f}"
        print(line)


def _build_shadow_comparison_summary(per_sample: list[dict], run_contract) -> dict:
    """Phase1.5: aggregate shadow comparison diagnostics across all samples."""
    if run_contract is None or not getattr(run_contract, "candidate_pool_enabled", False):
        return {}

    from collections import Counter
    changed = 0
    same = 0
    synthetic_fallbacks = 0
    missing_confidence = 0
    risk_counter: Counter = Counter()
    evidence_missing: Counter = Counter()

    total = 0
    for entry in per_sample:
        shadow = (entry.get("decision_trace") or {}).get("shadow_decision_core") or {}
        if not shadow:
            continue
        total += 1

        outcome = shadow.get("comparison_outcome") or {}
        if outcome.get("changed_selection"):
            changed += 1
        elif outcome.get("same_tokens"):
            same += 1

        if shadow.get("fallback_reason") == "synthetic_only_candidate_pool":
            synthetic_fallbacks += 1

        if shadow.get("shadow_confidence") is None:
            missing_confidence += 1

        for flag in shadow.get("risk_flags") or []:
            risk_counter[flag] += 1

        bundle = entry.get("evidence_bundle") or {}
        if (bundle.get("generation_evidence") or {}).get("status") == "missing":
            evidence_missing["generation"] += 1
        if (bundle.get("mapping_evidence") or {}).get("status") == "missing":
            evidence_missing["mapping"] += 1
        if (bundle.get("execution_evidence") or {}).get("status") in ("missing", "not_applicable"):
            evidence_missing["execution"] += 1

    return {
        "total_samples": total,
        "changed_selection_count": changed,
        "changed_selection_rate": round(changed / max(total, 1), 6),
        "same_selection_count": same,
        "synthetic_fallback_count": synthetic_fallbacks,
        "missing_confidence_count": missing_confidence,
        "risk_flag_distribution": dict(risk_counter),
        "evidence_missing_distribution": dict(evidence_missing),
    }


def _build_shadow_observation_summary(per_sample: list[dict], run_contract) -> dict:
    """Phase1.6a: aggregate observed facts only — no quality claims."""
    if run_contract is None or not getattr(run_contract, "candidate_pool_enabled", False):
        return {}

    total = 0
    comp_possible = 0
    changed = 0
    tie_count = 0
    risk_profile_changed = 0
    missing_evidence_count = 0
    consistency_risk = 0
    consistency_missing = 0
    synthetic_only = 0

    for entry in per_sample:
        shadow = (entry.get("decision_trace") or {}).get("shadow_decision_core") or {}
        if not shadow:
            continue
        total += 1

        obs = shadow.get("observed_comparison") or {}
        if obs.get("comparison_possible"):
            comp_possible += 1
        if obs.get("selection_changed"):
            changed += 1
        if obs.get("same_selection"):
            tie_count += 1
        if obs.get("risk_profile_changed"):
            risk_profile_changed += 1
        if obs.get("missing_evidence_changed"):
            missing_evidence_count += 1

        diag = shadow.get("diagnostic_consistency") or {}
        if diag.get("shadow_selected_but_higher_risk"):
            consistency_risk += 1
        if diag.get("shadow_selected_missing_evidence"):
            consistency_missing += 1
        if diag.get("synthetic_only_pool"):
            synthetic_only += 1

    n = max(total, 1)
    return {
        "total_samples": total,
        "comparison_possible_count": comp_possible,
        "selection_changed_count": changed,
        "selection_changed_rate": round(changed / n, 6),
        "same_selection_rate": round(tie_count / n, 6),
        "synthetic_fallback_rate": round(synthetic_only / n, 6),
        "missing_evidence_rate": round(missing_evidence_count / n, 6),
        "risk_profile_changed_rate": round(risk_profile_changed / n, 6),
        "evidence_change_distribution": {
            "missing_evidence_triggered": missing_evidence_count,
            "risk_profile_changed": risk_profile_changed,
        },
        "diagnostic_consistency": {
            "shadow_selected_but_higher_risk_count": consistency_risk,
            "shadow_selected_missing_evidence_count": consistency_missing,
        },
    }


def _build_counterfactual_observation(
    entry: dict,
    seq_metric: SeqMetrics,
    shadow: dict,
    evidence: dict,
) -> dict:
    """Phase1.7: counterfactual observation — existing artifacts only, no new metrics."""
    obs = shadow.get("observed_comparison") or {}
    outcome = shadow.get("comparison_outcome") or {}
    legacy_exists = bool(outcome.get("legacy_candidate_exists"))
    shadow_exists = bool(outcome.get("shadow_candidate_exists"))
    comparison_possible = obs.get("comparison_possible", False)

    # Legacy observed metrics (from already-computed artifacts)
    legacy_lcs = seq_metric.lcs_ratio if seq_metric else None
    legacy_token_acc = seq_metric.token_accuracy if seq_metric else None
    legacy_set_f1 = seq_metric.set_f1 if seq_metric else None

    # Usability / executable are not in mainline per-sample — only in V4-QG planner
    legacy_usability = entry.get("usability_score") if "usability_score" in entry else None
    legacy_executable = entry.get("executable_qgis_mapping_rate") if "executable_qgis_mapping_rate" in entry else None

    # Semantic from entry's qgis_score_components
    qgis_comp = entry.get("qgis_score_components") or {}
    legacy_semantic = qgis_comp.get("semantic_score") if qgis_comp else None

    legacy_observed = {
        "sequence_lcs": legacy_lcs,
        "token_acc": legacy_token_acc,
        "set_f1": legacy_set_f1,
        "usability": legacy_usability,
        "executable": legacy_executable,
        "semantic_coverage": legacy_semantic,
    }

    # Shadow observed: from evidence bundle (no sequence metrics computed against reference)
    mapping = evidence.get("mapping_evidence") or {}
    sem = mapping.get("semantic_score") or {}
    shadow_semantic = float(sem["value"]) if sem.get("status") == "available" and sem.get("value") is not None else None

    exec_ev = evidence.get("execution_evidence") or {}
    shadow_validity = None
    if exec_ev.get("status") == "available" and exec_ev.get("validity", {}).get("value") is not None:
        shadow_validity = float(exec_ev["validity"]["value"])

    shadow_observed = {
        "sequence_lcs": None,
        "token_acc": None,
        "set_f1": None,
        "usability": None,
        "executable": shadow_validity,
        "semantic_coverage": shadow_semantic,
    }

    # Deltas only where both non-None
    def _delta(leg: Optional[float], shad: Optional[float]) -> Optional[float]:
        if leg is None or shad is None:
            return None
        return round(shad - leg, 6)

    metric_diff = {
        "sequence_lcs_delta": _delta(legacy_lcs, shadow_observed["sequence_lcs"]),
        "token_acc_delta": _delta(legacy_token_acc, shadow_observed["token_acc"]),
        "set_f1_delta": _delta(legacy_set_f1, shadow_observed["set_f1"]),
        "usability_delta": _delta(legacy_usability, shadow_observed["usability"]),
        "executable_delta": _delta(legacy_executable, shadow_observed["executable"]),
        "semantic_coverage_delta": _delta(legacy_semantic, shadow_semantic),
    }

    comparable = any(v is not None for v in metric_diff.values())
    metric_diff_available = comparable and comparison_possible

    missing_reason = None
    if not comparison_possible:
        missing_reason = "comparison_not_possible"
    elif not comparable:
        missing_reason = "no_comparable_metrics_available"

    return {
        "comparison_valid": comparison_possible and comparable,
        "comparison_possible": comparison_possible,
        "legacy_candidate_exists": legacy_exists,
        "shadow_candidate_exists": shadow_exists,
        "legacy_metrics_available": True,
        "shadow_metrics_available": shadow_exists,
        "metric_difference_available": metric_diff_available,
        "missing_reason": missing_reason,
        "legacy_observed_metrics": legacy_observed,
        "shadow_observed_metrics": shadow_observed,
        "metric_difference": metric_diff,
    }


def _build_shadow_counterfactual_summary(per_sample: list[dict], run_contract) -> dict:
    """Phase1.7: aggregate counterfactual observation — counts only, no quality claims."""
    if run_contract is None or not getattr(run_contract, "candidate_pool_enabled", False):
        return {}

    total = 0
    valid = 0
    possible = 0
    diff_available = 0
    missing_dist: dict[str, int] = {}

    for entry in per_sample:
        cf = (entry.get("decision_trace") or {}).get("counterfactual_observation") or {}
        if not cf:
            continue
        total += 1
        if cf.get("comparison_valid"):
            valid += 1
        if cf.get("comparison_possible"):
            possible += 1
        if cf.get("metric_difference_available"):
            diff_available += 1
        reason = cf.get("missing_reason")
        if reason:
            missing_dist[reason] = missing_dist.get(reason, 0) + 1

    n = max(total, 1)
    return {
        "total_samples": total,
        "comparison_valid_count": valid,
        "comparison_valid_rate": round(valid / n, 6),
        "comparison_possible_count": possible,
        "metric_difference_available_count": diff_available,
        "missing_metric_distribution": missing_dist,
    }


VALID_CHANGE_REASONS = frozenset({
    "candidate_id_changed",
    "source_changed",
    "mapping_presence_changed",
    "semantic_presence_changed",
    "execution_presence_changed",
    "risk_profile_changed",
    "missing_evidence_changed",
})


def _build_difference_attribution(shadow: dict, evidence: dict) -> dict:
    """Build difference_attribution from existing shadow sections — catalog observed changes only."""
    outcome = shadow.get("comparison_outcome") or {}
    obs = shadow.get("observed_comparison") or {}
    diag = shadow.get("diagnostic_consistency") or {}

    legacy_exists = bool(outcome.get("legacy_candidate_exists"))
    shadow_exists = bool(outcome.get("shadow_candidate_exists"))
    selection_changed = bool(obs.get("selection_changed"))

    if not legacy_exists or not shadow_exists:
        return {
            "selection_changed": False,
            "observed_changes": {},
            "change_reasons": [],
            "attribution_status": "not_applicable",
        }

    if not selection_changed:
        return {
            "selection_changed": False,
            "observed_changes": {k: False for k in _observed_change_keys()},
            "change_reasons": [],
            "attribution_status": "no_observed_difference",
        }

    mapping = evidence.get("mapping_evidence") or {}
    exec_ev = evidence.get("execution_evidence") or {}

    candidate_changed = selection_changed
    tokens_changed = not obs.get("same_tokens", True)
    source_changed = not obs.get("same_source", True)
    risk_profile_changed = bool(obs.get("risk_profile_changed"))
    missing_evidence_changed = bool(obs.get("missing_evidence_changed"))

    mapping_evidence_changed = mapping.get("status") != "available"
    semantic_evidence_changed = (mapping.get("semantic_score") or {}).get("status") != "available"
    execution_evidence_changed = exec_ev.get("status") != "available"
    retrieval_evidence_changed = any(
        row.get("source") == "retrieval_shadow"
        for row in shadow.get("candidate_pool_trace", []) or []
    )

    observed_changes = {
        "candidate_changed": candidate_changed,
        "tokens_changed": tokens_changed,
        "source_changed": source_changed,
        "risk_profile_changed": risk_profile_changed,
        "missing_evidence_changed": missing_evidence_changed,
        "mapping_evidence_changed": mapping_evidence_changed,
        "semantic_evidence_changed": semantic_evidence_changed,
        "execution_evidence_changed": execution_evidence_changed,
        "retrieval_evidence_changed": retrieval_evidence_changed,
    }

    change_reasons = []
    if candidate_changed:
        change_reasons.append("candidate_id_changed")
    if source_changed:
        change_reasons.append("source_changed")
    if mapping_evidence_changed:
        change_reasons.append("mapping_presence_changed")
    if semantic_evidence_changed:
        change_reasons.append("semantic_presence_changed")
    if execution_evidence_changed:
        change_reasons.append("execution_presence_changed")
    if risk_profile_changed:
        change_reasons.append("risk_profile_changed")
    if missing_evidence_changed:
        change_reasons.append("missing_evidence_changed")

    # Sanity check: all reasons in VALID_CHANGE_REASONS
    change_reasons = [r for r in change_reasons if r in VALID_CHANGE_REASONS]

    return {
        "selection_changed": selection_changed,
        "observed_changes": observed_changes,
        "change_reasons": change_reasons,
        "attribution_status": "observed_difference",
    }


def _observed_change_keys() -> list[str]:
    return [
        "candidate_changed", "tokens_changed", "source_changed",
        "risk_profile_changed", "missing_evidence_changed",
        "mapping_evidence_changed", "semantic_evidence_changed",
        "execution_evidence_changed", "retrieval_evidence_changed",
    ]


def _build_shadow_difference_summary(per_sample: list[dict], run_contract) -> dict:
    """Aggregate observed difference counts — presence only, no quality claims."""
    if run_contract is None or not getattr(run_contract, "candidate_pool_enabled", False):
        return {}

    total = 0
    changed = 0
    dist: dict[str, int] = {}

    for entry in per_sample:
        da = (entry.get("decision_trace") or {}).get("difference_attribution") or {}
        if not da:
            continue
        total += 1
        if da.get("selection_changed"):
            changed += 1
        for reason in da.get("change_reasons") or []:
            dist[reason] = dist.get(reason, 0) + 1

    # Map reasons to distribution keys
    n = max(total, 1)
    return {
        "total_samples": total,
        "selection_changed_count": changed,
        "difference_distribution": {
            "candidate_changed": dist.get("candidate_id_changed", 0),
            "source_changed": dist.get("source_changed", 0),
            "risk_profile_changed": dist.get("risk_profile_changed", 0),
            "mapping_changed": dist.get("mapping_presence_changed", 0),
            "semantic_changed": dist.get("semantic_presence_changed", 0),
            "execution_changed": dist.get("execution_presence_changed", 0),
            "missing_evidence_changed": dist.get("missing_evidence_changed", 0),
        },
    }


VALID_CONTRADICTIONS = frozenset({
    "selection_changed_without_observed_change",
    "risk_change_missing",
    "synthetic_shadow_selected",
    "comparison_invalid_with_metric_difference",
    "missing_evidence_inconsistency",
    "candidate_presence_inconsistency",
})


def _build_diagnostic_audit(shadow: dict, decision_trace: dict) -> dict:
    """Detect contradictions between existing artifact sections — no quality claims."""
    outcome = shadow.get("comparison_outcome") or {}
    obs = shadow.get("observed_comparison") or {}
    diag_cons = shadow.get("diagnostic_consistency") or {}
    da = decision_trace.get("difference_attribution") or {}
    cf = decision_trace.get("counterfactual_observation") or {}

    shadow_exists = bool(outcome.get("shadow_candidate_exists"))
    legacy_exists = bool(outcome.get("legacy_candidate_exists"))

    if not legacy_exists and not shadow_exists:
        return {
            "audit_valid": False,
            "contradictions": [],
            "observed_consistency": {k: True for k in _consistency_keys()},
            "audit_status": "not_applicable",
        }

    contradictions = []
    changes = da.get("observed_changes") or {}

    # 1. selection_changed_without_observed_change
    sel_changed = bool(obs.get("selection_changed"))
    any_observed = any(v for k, v in changes.items() if k != "candidate_changed")
    if sel_changed and not any_observed:
        contradictions.append("selection_changed_without_observed_change")

    # 2. risk_change_missing
    if "risk_profile_changed" in (da.get("change_reasons") or []) and not changes.get("risk_profile_changed", True):
        contradictions.append("risk_change_missing")

    # 3. synthetic_shadow_selected
    if diag_cons.get("synthetic_only_pool") and shadow_exists:
        contradictions.append("synthetic_shadow_selected")

    # 4. comparison_invalid_with_metric_difference
    if not cf.get("comparison_valid", True) and cf.get("metric_difference_available"):
        contradictions.append("comparison_invalid_with_metric_difference")

    # 5. missing_evidence_inconsistency
    if not changes.get("missing_evidence_changed", True) and "missing_evidence_changed" in (da.get("change_reasons") or []):
        contradictions.append("missing_evidence_inconsistency")

    # 6. candidate_presence_inconsistency
    if not shadow_exists and outcome.get("shadow_has_real_candidate"):
        contradictions.append("candidate_presence_inconsistency")

    contradictions = [c for c in contradictions if c in VALID_CONTRADICTIONS]

    consistent = len(contradictions) == 0
    return {
        "audit_valid": True,
        "contradictions": contradictions,
        "observed_consistency": {
            "selection_consistent": "selection_changed_without_observed_change" not in contradictions,
            "risk_consistent": "risk_change_missing" not in contradictions,
            "candidate_presence_consistent": (
                "synthetic_shadow_selected" not in contradictions
                and "candidate_presence_inconsistency" not in contradictions
            ),
            "evidence_consistent": "missing_evidence_inconsistency" not in contradictions,
            "comparison_consistent": "comparison_invalid_with_metric_difference" not in contradictions,
        },
        "audit_status": "consistent" if consistent else "inconsistent",
    }


def _consistency_keys() -> list:
    return ["selection_consistent", "risk_consistent", "candidate_presence_consistent",
            "evidence_consistent", "comparison_consistent"]


def _build_shadow_diagnostic_summary(per_sample: list[dict], run_contract) -> dict:
    """Aggregate consistency audit — counts only, no health/quality scores."""
    if run_contract is None or not getattr(run_contract, "candidate_pool_enabled", False):
        return {}

    total = 0
    consistent = 0
    inconsistent = 0
    dist: dict[str, int] = {}

    for entry in per_sample:
        audit = (entry.get("decision_trace") or {}).get("diagnostic_audit") or {}
        if not audit:
            continue
        total += 1
        status = audit.get("audit_status")
        if status == "consistent":
            consistent += 1
        elif status == "inconsistent":
            inconsistent += 1
        for c in audit.get("contradictions") or []:
            dist[c] = dist.get(c, 0) + 1

    return {
        "total_samples": total,
        "consistent_count": consistent,
        "inconsistent_count": inconsistent,
        "contradiction_distribution": {
            "selection_changed_without_observed_change": dist.get("selection_changed_without_observed_change", 0),
            "risk_change_missing": dist.get("risk_change_missing", 0),
            "synthetic_shadow_selected": dist.get("synthetic_shadow_selected", 0),
            "comparison_invalid_with_metric_difference": dist.get("comparison_invalid_with_metric_difference", 0),
            "missing_evidence_inconsistency": dist.get("missing_evidence_inconsistency", 0),
            "candidate_presence_inconsistency": dist.get("candidate_presence_inconsistency", 0),
        },
    }


def _build_runtime_readiness_observation(shadow: dict, evidence: dict, decision_trace: dict) -> dict:
    """Phase1.10: runtime readiness observation — observation states only, no deployment/approval."""
    outcome = shadow.get("comparison_outcome") or {}
    cf = decision_trace.get("counterfactual_observation") or {}
    da = decision_trace.get("difference_attribution") or {}
    audit = decision_trace.get("diagnostic_audit") or {}

    shadow_exists = bool(outcome.get("shadow_candidate_exists"))
    legacy_exists = bool(outcome.get("legacy_candidate_exists"))

    if not legacy_exists and not shadow_exists:
        return {
            "observation_available": False,
            "evidence_observation": {},
            "comparison_observation": {},
            "diagnostic_observation": {},
            "observation_status": "not_applicable",
        }

    ev = evidence or {}
    gen = ev.get("generation_evidence") or {}
    mapping = ev.get("mapping_evidence") or {}
    exec_ev = ev.get("execution_evidence") or {}
    sem = mapping.get("semantic_score") or {}

    evidence_observation = {
        "generation_available": gen.get("status") == "available",
        "mapping_available": mapping.get("status") == "available",
        "execution_available": exec_ev.get("status") == "available",
        "semantic_available": sem.get("status") == "available",
        "retrieval_available": any(
            row.get("source") == "retrieval_shadow"
            for row in shadow.get("candidate_pool_trace", []) or []
        ),
    }

    comparison_observation = {
        "comparison_possible": bool(cf.get("comparison_possible")),
        "comparison_valid": bool(cf.get("comparison_valid")),
        "difference_observed": da.get("selection_changed", False),
    }

    diagnostic_observation = {
        "diagnostic_available": audit.get("audit_valid", False),
        "contradiction_present": bool(audit.get("contradictions")),
        "synthetic_dependency_present": shadow.get("diagnostic_consistency", {}).get("synthetic_only_pool", False),
    }

    any_observed = any(evidence_observation.values()) or comparison_observation["comparison_possible"]
    all_observed = all([
        evidence_observation["generation_available"],
        comparison_observation["comparison_possible"],
    ])

    if all_observed:
        status = "observation_available"
    elif any_observed:
        status = "partial_observation"
    else:
        status = "partial_observation"

    return {
        "observation_available": any_observed,
        "evidence_observation": evidence_observation,
        "comparison_observation": comparison_observation,
        "diagnostic_observation": diagnostic_observation,
        "observation_status": status,
    }


def _build_shadow_runtime_readiness_summary(per_sample: list[dict], run_contract) -> dict:
    """Phase1.10: aggregate observation distribution — presence counts only."""
    if run_contract is None or not getattr(run_contract, "candidate_pool_enabled", False):
        return {}

    total = 0
    obs_avail = 0
    partial = 0
    not_applicable = 0
    ev_dist: dict[str, int] = {}
    cmp_dist: dict[str, int] = {}
    diag_dist: dict[str, int] = {}

    for entry in per_sample:
        ro = (entry.get("decision_trace") or {}).get("runtime_readiness_observation") or {}
        if not ro:
            continue
        total += 1
        status = ro.get("observation_status")
        if status == "observation_available":
            obs_avail += 1
        elif status == "partial_observation":
            partial += 1
        elif status == "not_applicable":
            not_applicable += 1

        for key in ("generation_available", "mapping_available", "execution_available",
                     "semantic_available", "retrieval_available"):
            if (ro.get("evidence_observation") or {}).get(key):
                ev_dist[key] = ev_dist.get(key, 0) + 1

        for key in ("comparison_possible", "comparison_valid", "difference_observed"):
            if (ro.get("comparison_observation") or {}).get(key):
                cmp_dist[key] = cmp_dist.get(key, 0) + 1

        for key in ("contradiction_present", "synthetic_dependency_present"):
            if (ro.get("diagnostic_observation") or {}).get(key):
                diag_dist[key] = diag_dist.get(key, 0) + 1

    return {
        "total_samples": total,
        "observation_available_count": obs_avail,
        "partial_observation_count": partial,
        "not_applicable_count": not_applicable,
        "evidence_distribution": ev_dist,
        "comparison_distribution": cmp_dist,
        "diagnostic_distribution": diag_dist,
    }


def _build_artifact_provenance(decision_trace: dict, candidate_pool_trace: list) -> dict:
    """Phase1.11: catalog which observation fields come from which upstream artifacts."""
    da = decision_trace.get("difference_attribution")
    audit = decision_trace.get("diagnostic_audit")
    cf = decision_trace.get("counterfactual_observation")
    ro = decision_trace.get("runtime_readiness_observation")

    provenance_available = bool(da or audit or cf or ro)
    if not provenance_available:
        return {
            "provenance_available": False,
            "field_sources": {},
            "source_distribution": {},
            "provenance_status": "not_applicable",
        }

    field_sources = {
        "difference_attribution": _provenance_tags(da),
        "diagnostic_audit": _provenance_tags(audit),
        "counterfactual_observation": _provenance_tags(cf),
        "runtime_readiness_observation": _provenance_tags(ro),
    }

    has_candidate_pool = bool(candidate_pool_trace)
    has_evidence = any(field_sources.get(k) for k in ("counterfactual_observation", "runtime_readiness_observation"))
    has_comparison = bool(field_sources.get("difference_attribution"))
    has_diagnostic = bool(field_sources.get("diagnostic_audit"))

    source_distribution = {
        "candidate_pool": has_candidate_pool,
        "evidence_bundle": has_evidence,
        "comparison_artifact": has_comparison,
        "counterfactual_artifact": bool(field_sources.get("counterfactual_observation")),
        "diagnostic_artifact": has_diagnostic,
    }

    all_sources = all([has_candidate_pool, has_evidence, has_comparison])
    if all_sources:
        status = "provenance_available"
    elif provenance_available:
        status = "partial_provenance"
    else:
        status = "not_applicable"

    return {
        "provenance_available": provenance_available,
        "field_sources": field_sources,
        "source_distribution": source_distribution,
        "provenance_status": status,
    }


def _provenance_tags(section: dict | None) -> list[str]:
    """Return upstream source tags for a decision_trace section."""
    if not section:
        return []
    return sorted(k for k in section if not k.startswith("_"))


def _build_shadow_provenance_summary(per_sample: list[dict], run_contract) -> dict:
    """Phase1.11: aggregate provenance observation — presence counts only."""
    if run_contract is None or not getattr(run_contract, "candidate_pool_enabled", False):
        return {}

    total = 0
    prov_avail = 0
    partial = 0
    source_dist: dict[str, int] = {}

    for entry in per_sample:
        ap = (entry.get("decision_trace") or {}).get("artifact_provenance") or {}
        if not ap:
            continue
        total += 1
        status = ap.get("provenance_status")
        if status == "provenance_available":
            prov_avail += 1
        elif status == "partial_provenance":
            partial += 1

        for key in ("candidate_pool", "evidence_bundle", "comparison_artifact",
                     "counterfactual_artifact", "diagnostic_artifact"):
            if (ap.get("source_distribution") or {}).get(key):
                source_dist[key] = source_dist.get(key, 0) + 1

    return {
        "total_samples": total,
        "provenance_available_count": prov_avail,
        "partial_provenance_count": partial,
        "source_distribution": source_dist,
    }


def _build_cross_artifact_relationship(
    decision_trace: dict, shadow: dict, evidence: dict, candidate_pool_trace: list,
) -> dict:
    """Phase1.12: cross-artifact relationship — presence catalog and shared references only."""
    dt = decision_trace
    presence = {
        "candidate_pool_present": bool(candidate_pool_trace),
        "evidence_bundle_present": bool(evidence),
        "comparison_present": bool(dt.get("difference_attribution")),
        "diagnostic_present": bool(dt.get("diagnostic_audit")),
        "provenance_present": bool(dt.get("artifact_provenance")),
        "counterfactual_present": bool(dt.get("counterfactual_observation")),
        "readiness_present": bool(dt.get("runtime_readiness_observation")),
    }
    count_present = sum(1 for v in presence.values() if v)
    relationship_available = count_present >= 2

    if not relationship_available:
        if not presence["candidate_pool_present"]:
            reason = "missing_candidate_pool"
        elif not presence["evidence_bundle_present"]:
            reason = "missing_evidence"
        else:
            reason = "insufficient_artifacts"
        return {
            "relationship_available": False,
            "artifact_presence": presence,
            "shared_candidate_reference": {},
            "shared_evidence_reference": {},
            "shared_diagnostic_reference": {},
            "relationship_missing_reason": reason,
        }

    # Shared candidate reference: trace + shadow decision core share candidate_ids
    trace_ids = {row.get("candidate_id") for row in (candidate_pool_trace or [])}
    shadow_ids = set()
    for key in ("legacy_candidate_id", "shadow_candidate_id"):
        val = shadow.get(key)
        if val is not None:
            shadow_ids.add(val)
    candidate_overlap = bool(trace_ids & shadow_ids)

    # Evidence reference types
    evidence_types = []
    ev = evidence or {}
    for section in ("generation_evidence", "mapping_evidence", "execution_evidence"):
        if (ev.get(section) or {}).get("status") == "available":
            evidence_types.append(section)

    # Diagnostic reference types
    diagnostic_types = []
    audit = dt.get("diagnostic_audit") or {}
    if audit.get("contradictions"):
        diagnostic_types.append("contradiction")
    if audit.get("observed_consistency"):
        diagnostic_types.append("consistency_check")
    diag_cons = shadow.get("diagnostic_consistency") or {}
    if diag_cons.get("synthetic_only_pool"):
        diagnostic_types.append("synthetic_pool")

    return {
        "relationship_available": True,
        "artifact_presence": presence,
        "shared_candidate_reference": {
            "candidate_id_overlap_exists": candidate_overlap,
            "candidate_count_match": None,
        },
        "shared_evidence_reference": {
            "evidence_overlap_exists": len(evidence_types) > 0,
            "evidence_types": evidence_types,
        },
        "shared_diagnostic_reference": {
            "diagnostic_overlap_exists": len(diagnostic_types) > 0,
            "diagnostic_types": diagnostic_types,
        },
        "relationship_missing_reason": None,
    }


def _build_cross_artifact_summary(per_sample: list[dict], run_contract) -> dict:
    """Phase1.12: aggregate cross-artifact relationship — presence counts only."""
    if run_contract is None or not getattr(run_contract, "candidate_pool_enabled", False):
        return {}

    total = 0
    rel_avail = 0
    partial = 0
    presence_dist: dict[str, int] = {}
    ev_ref_dist: dict[str, int] = {}
    diag_ref_dist: dict[str, int] = {}

    for entry in per_sample:
        cr = (entry.get("decision_trace") or {}).get("cross_artifact_relationship") or {}
        if not cr:
            continue
        total += 1
        if cr.get("relationship_available"):
            rel_avail += 1
        else:
            partial += 1

        for key, val in (cr.get("artifact_presence") or {}).items():
            if val:
                presence_dist[key] = presence_dist.get(key, 0) + 1

        for et in (cr.get("shared_evidence_reference") or {}).get("evidence_types") or []:
            ev_ref_dist[et] = ev_ref_dist.get(et, 0) + 1

        for dt in (cr.get("shared_diagnostic_reference") or {}).get("diagnostic_types") or []:
            diag_ref_dist[dt] = diag_ref_dist.get(dt, 0) + 1

    return {
        "total_samples": total,
        "relationship_available_count": rel_avail,
        "partial_relationship_count": partial,
        "artifact_presence_distribution": presence_dist,
        "evidence_reference_distribution": ev_ref_dist,
        "diagnostic_reference_distribution": diag_ref_dist,
    }


def _build_shadow_selector_comparison(shadow: dict, candidate_pool_trace: list) -> dict:
    """Phase2.0: shadow selector controlled comparison — disagreement/reproducibility catalog only."""
    outcome = shadow.get("comparison_outcome") or {}
    obs = shadow.get("observed_comparison") or {}
    diag = shadow.get("diagnostic_consistency") or {}
    da = {}  # difference_attribution not yet available at this point in per-sample loop

    legacy_exists = bool(outcome.get("legacy_candidate_exists"))
    shadow_exists = bool(outcome.get("shadow_candidate_exists"))
    same_sel = bool(obs.get("same_selection"))
    synthetic_only = bool(diag.get("synthetic_only_pool"))

    comparison_available = legacy_exists and shadow_exists

    # Selector state
    selector_state = {
        "legacy_candidate_exists": legacy_exists,
        "shadow_candidate_exists": shadow_exists,
        "same_selection": same_sel,
        "different_selection": legacy_exists and shadow_exists and not same_sel,
        "synthetic_only_pool": synthetic_only,
    }

    # Disagreement observation
    disagreement_exists = selector_state["different_selection"]
    disagreement_reasons = []
    if disagreement_exists:
        if not obs.get("same_tokens", True):
            disagreement_reasons.append("token_difference")
        if not obs.get("same_source", True):
            disagreement_reasons.append("source_difference")
        if obs.get("risk_profile_changed"):
            disagreement_reasons.append("risk_profile_difference")
        if obs.get("missing_evidence_changed"):
            disagreement_reasons.append("evidence_availability_difference")

    disagreement_observation = {
        "disagreement_exists": disagreement_exists,
        "disagreement_reason_types": disagreement_reasons,
        "disagreement_reason_count": len(disagreement_reasons),
        "missing_reason": None if comparison_available else (
            "no_shadow_candidate" if not shadow_exists else "no_legacy_candidate"),
    }

    # Reproducibility observation: same input → same shadow trace
    # Cannot verify without running multiple times. Mark as null (not yet observed).
    reproducible = None
    repro_reason = "reproducibility_not_verified_in_single_pass_evaluation"

    # Fallback observation
    fallback_observation = {
        "fallback_triggered": bool(shadow.get("fallback_triggered")),
        "fallback_reason": shadow.get("fallback_reason"),
        "synthetic_only_pool": synthetic_only,
    }

    return {
        "comparison_available": comparison_available,
        "selector_state": selector_state,
        "disagreement_observation": disagreement_observation,
        "reproducibility_observation": {
            "reproducible": reproducible,
            "reproducibility_reason": repro_reason,
        },
        "fallback_observation": fallback_observation,
    }


def _build_shadow_selector_summary(per_sample: list[dict], run_contract) -> dict:
    """Phase2.0: aggregate selector comparison — counts only, no quality claims."""
    if run_contract is None or not getattr(run_contract, "candidate_pool_enabled", False):
        return {}

    total = 0
    comp_avail = 0
    disagreement = 0
    repro_missing = 0
    fallback = 0
    synthetic_only = 0
    reason_dist: dict[str, int] = {}

    for entry in per_sample:
        sc = (entry.get("decision_trace") or {}).get("shadow_selector_comparison") or {}
        if not sc:
            continue
        total += 1
        if sc.get("comparison_available"):
            comp_avail += 1
        if (sc.get("disagreement_observation") or {}).get("disagreement_exists"):
            disagreement += 1
        if (sc.get("reproducibility_observation") or {}).get("reproducible") is None:
            repro_missing += 1
        if (sc.get("fallback_observation") or {}).get("fallback_triggered"):
            fallback += 1
        if (sc.get("fallback_observation") or {}).get("synthetic_only_pool"):
            synthetic_only += 1

        for reason in (sc.get("disagreement_observation") or {}).get("disagreement_reason_types") or []:
            reason_dist[reason] = reason_dist.get(reason, 0) + 1

    n = max(total, 1)
    return {
        "total_samples": total,
        "comparison_available_count": comp_avail,
        "disagreement_count": disagreement,
        "disagreement_rate": round(disagreement / n, 6),
        "reproducible_count": 0,
        "reproducibility_missing_count": repro_missing,
        "fallback_count": fallback,
        "synthetic_only_pool_count": synthetic_only,
        "disagreement_distribution": reason_dist,
    }


def _build_disagreement_characterization(shadow: dict, evidence: dict, trace: list) -> dict:
    """Phase2.0a: characterize disagreement conditions from existing artifacts only."""
    outcome = shadow.get("comparison_outcome") or {}
    obs = shadow.get("observed_comparison") or {}
    diag = shadow.get("diagnostic_consistency") or {}

    legacy_exists = bool(outcome.get("legacy_candidate_exists"))
    shadow_exists = bool(outcome.get("shadow_candidate_exists"))
    disagreement_present = bool(obs.get("selection_changed"))

    characterization_available = legacy_exists and shadow_exists
    if not characterization_available:
        return {
            "characterization_available": False,
            "disagreement_present": False,
            "observable_conditions": {},
            "artifact_context": {"candidate_pool_size": None, "evidence_type_count": None,
                                 "missing_reason": "comparison_not_possible"},
        }

    source_changed = not obs.get("same_source", True)
    tokens_changed = not obs.get("same_tokens", True)
    risk_profile_changed = bool(obs.get("risk_profile_changed"))
    evidence_presence_changed = bool(obs.get("missing_evidence_changed"))

    synthetic_present = bool(diag.get("synthetic_only_pool"))

    retrieval_present = any(
        row.get("source") == "retrieval_shadow"
        for row in (trace or [])
    )

    candidate_pool_size = len(trace) if trace else None

    ev_types = 0
    ev = evidence or {}
    for s in ("generation_evidence", "mapping_evidence", "execution_evidence"):
        if (ev.get(s) or {}).get("status") == "available":
            ev_types += 1
    evidence_type_count = ev_types if ev else None

    return {
        "characterization_available": True,
        "disagreement_present": disagreement_present,
        "observable_conditions": {
            "source_changed": source_changed,
            "tokens_changed": tokens_changed,
            "risk_profile_changed": risk_profile_changed,
            "evidence_presence_changed": evidence_presence_changed,
            "synthetic_candidate_present": synthetic_present,
            "retrieval_candidate_present": retrieval_present,
        },
        "artifact_context": {
            "candidate_pool_size": candidate_pool_size,
            "evidence_type_count": evidence_type_count,
            "missing_reason": None,
        },
    }


def _build_disagreement_summary(per_sample: list[dict], run_contract) -> dict:
    """Phase2.0a: aggregate disagreement characterization — counts only."""
    if run_contract is None or not getattr(run_contract, "candidate_pool_enabled", False):
        return {}

    total = 0
    dis_count = 0
    source_ch = 0
    tokens_ch = 0
    risk_ch = 0
    evidence_ch = 0
    synthetic = 0
    retrieval = 0

    for entry in per_sample:
        dc = (entry.get("decision_trace") or {}).get("disagreement_characterization") or {}
        if not dc or not dc.get("characterization_available"):
            continue
        total += 1
        if dc.get("disagreement_present"):
            dis_count += 1
        cond = dc.get("observable_conditions") or {}
        if cond.get("source_changed"):
            source_ch += 1
        if cond.get("tokens_changed"):
            tokens_ch += 1
        if cond.get("risk_profile_changed"):
            risk_ch += 1
        if cond.get("evidence_presence_changed"):
            evidence_ch += 1
        if cond.get("synthetic_candidate_present"):
            synthetic += 1
        if cond.get("retrieval_candidate_present"):
            retrieval += 1

    return {
        "total_samples": total,
        "disagreement_count": dis_count,
        "source_changed_count": source_ch,
        "tokens_changed_count": tokens_ch,
        "risk_profile_changed_count": risk_ch,
        "evidence_presence_changed_count": evidence_ch,
        "synthetic_candidate_count": synthetic,
        "retrieval_candidate_count": retrieval,
    }


# ═══════════════════════════════════════════════════════════════════════
# Phase2.1a: Semantic Boundary
#
# OBSERVATION_ARTIFACTS — neutral observation IDs only.
# These represent observable state. NOT: decision, selector, score, confidence,
# quality, correctness, runtime authority, recommendation.
#
# Internal mapping resolves neutral IDs to actual decision_trace keys.
# ═══════════════════════════════════════════════════════════════════════
OBSERVATION_ARTIFACTS = [
    "candidate_observation",
    "counterfactual_observation",
    "difference_attribution",
    "diagnostic_audit",
    "runtime_readiness_observation",
    "artifact_provenance",
    "cross_artifact_relationship",
    "selection_observation",
    "disagreement_characterization",
    "observation_coverage",
    "observed_comparison",
    "diagnostic_consistency",
]

_OBSERVATION_SOURCE_MAP = {
    "candidate_observation": "shadow_decision_core",
    "selection_observation": "shadow_selector_comparison",
    "counterfactual_observation": "counterfactual_observation",
    "difference_attribution": "difference_attribution",
    "diagnostic_audit": "diagnostic_audit",
    "runtime_readiness_observation": "runtime_readiness_observation",
    "artifact_provenance": "artifact_provenance",
    "cross_artifact_relationship": "cross_artifact_relationship",
    "disagreement_characterization": "disagreement_characterization",
    "observation_coverage": "observation_coverage",
    "observed_comparison": "observed_comparison",
    "diagnostic_consistency": "diagnostic_consistency",
}

# Nested sections (inside shadow_decision_core)
_NESTED_ARTIFACTS = frozenset({"observed_comparison", "diagnostic_consistency"})

# ═══════════════════════════════════════════════════════════════════════
# LEGACY_DECISION_SEMANTICS — code-enforced exclusion.
# These fields are NOT observation artifacts. Observation builders and
# summaries MUST NOT reference them.
# ═══════════════════════════════════════════════════════════════════════
LEGACY_DECISION_SEMANTICS = frozenset({
    "score", "shadow_confidence", "confidence_status", "risk_penalty",
    "priority", "weight",
})


def _observation_artifact_valid(name: str) -> bool:
    """True if name is in OBSERVATION_ARTIFACTS and NOT in LEGACY_DECISION_SEMANTICS."""
    return name in OBSERVATION_ARTIFACTS and name not in LEGACY_DECISION_SEMANTICS


def _build_observation_coverage(decision_trace: dict, candidate_pool_trace: list, evidence_present: bool) -> dict:
    """Phase2.1: catalog which observation sections exist — pure presence/absence."""
    observed = {}
    missing = []

    shadow = decision_trace.get("shadow_decision_core") or {}
    for neutral_id in OBSERVATION_ARTIFACTS:
        if neutral_id == "observation_coverage":
            continue
        if neutral_id in LEGACY_DECISION_SEMANTICS:
            continue

        source_key = _OBSERVATION_SOURCE_MAP.get(neutral_id, neutral_id)
        if neutral_id in _NESTED_ARTIFACTS:
            present = bool(shadow.get(source_key))
        elif neutral_id in ("candidate_observation", "selection_observation"):
            present = bool(decision_trace.get(source_key))
        else:
            present = bool(decision_trace.get(source_key))
        observed[neutral_id] = present
        if not present:
            missing.append(neutral_id)

    coverage_available = any(observed.values())
    partially = coverage_available and len(missing) > 0

    # Artifact presence only — no behavioral derivation
    candidate_pool_present = bool(candidate_pool_trace)
    retrieval_present = any(
        row.get("source") == "retrieval_shadow"
        for row in (candidate_pool_trace or [])
    )

    return {
        "coverage_available": coverage_available,
        "observed_artifacts": observed,
        "missing_artifacts": missing,
        "partially_observed": partially,
        "observation_context": {
            "candidate_pool_present": candidate_pool_present,
            "evidence_bundle_present": evidence_present,
            "retrieval_present": retrieval_present,
            "synthetic_candidate_present": (
                shadow.get("diagnostic_consistency") or {}
            ).get("synthetic_only_pool", False),
        },
    }


def _build_observation_coverage_summary(per_sample: list[dict], run_contract) -> dict:
    """Phase2.1: aggregate observation coverage — counts only."""
    if run_contract is None or not getattr(run_contract, "candidate_pool_enabled", False):
        return {}

    total = 0
    coverage_avail = 0
    partial = 0
    missing_dist: dict[str, int] = {}
    presence_dist: dict[str, int] = {}

    for entry in per_sample:
        oc = (entry.get("decision_trace") or {}).get("observation_coverage") or {}
        if not oc:
            continue
        total += 1
        if oc.get("coverage_available"):
            coverage_avail += 1
        if oc.get("partially_observed"):
            partial += 1
        for m in oc.get("missing_artifacts") or []:
            missing_dist[m] = missing_dist.get(m, 0) + 1
        for key, val in (oc.get("observed_artifacts") or {}).items():
            if val:
                presence_dist[key] = presence_dist.get(key, 0) + 1

    return {
        "total_samples": total,
        "coverage_available_count": coverage_avail,
        "partial_observation_count": partial,
        "missing_distribution": missing_dist,
        "artifact_presence_distribution": presence_dist,
    }


OBSERVATION_REFERENCE_FIELDS = frozenset({
    "presence", "availability", "exists", "present", "missing",
    "source", "reference", "lineage", "id", "count", "status",
    "observation", "relationship", "coverage", "audit", "artifact",
    "provenance", "comparison", "difference", "diagnostic",
    "readiness", "consistency", "disagreement", "selector",
    "counterfactual", "characterization", "attribution",
})


def _build_observation_registry_audit(decision_trace: dict) -> dict:
    """Phase2.2: self-audit registry consistency — presence/reference checks only."""
    actual_observed = set()
    shadow = decision_trace.get("shadow_decision_core") or {}
    for neutral_id in OBSERVATION_ARTIFACTS:
        source_key = _OBSERVATION_SOURCE_MAP.get(neutral_id, neutral_id)
        if neutral_id in _NESTED_ARTIFACTS:
            present = bool(shadow.get(source_key))
        elif neutral_id in ("candidate_observation", "selection_observation"):
            present = bool(decision_trace.get(source_key))
        else:
            present = bool(decision_trace.get(source_key))
        if present:
            actual_observed.add(neutral_id)

    # Registry: all observed neutral IDs are in OBSERVATION_ARTIFACTS
    # All registry entries have source mapping
    unmapped = [n for n in OBSERVATION_ARTIFACTS if n not in _OBSERVATION_SOURCE_MAP]
    registry_consistent = len(actual_observed) > 0 and len(unmapped) == 0
    mapping_consistent = len(unmapped) == 0

    # Isolation: no legacy semantics in observed artifact names or source keys
    leaks = []
    for neutral_id in actual_observed:
        if neutral_id in LEGACY_DECISION_SEMANTICS:
            leaks.append(neutral_id)
    for neutral_id in OBSERVATION_ARTIFACTS:
        source_key = _OBSERVATION_SOURCE_MAP.get(neutral_id, "")
        for legacy in LEGACY_DECISION_SEMANTICS:
            if legacy in source_key.lower():
                leaks.append(neutral_id)
    isolation_consistent = len(leaks) == 0

    # Reference-only: all section names match presence/reference tokens
    non_reference = []
    for neutral_id in actual_observed:
        tokens = set(neutral_id.lower().replace("_", " ").split())
        if not (tokens & OBSERVATION_REFERENCE_FIELDS):
            non_reference.append(neutral_id)
    reference_only = len(non_reference) == 0

    audit_available = len(actual_observed) > 0

    return {
        "audit_available": audit_available,
        "registry_consistent": registry_consistent,
        "mapping_consistent": mapping_consistent,
        "isolation_consistent": isolation_consistent,
        "registered_artifacts": sorted(actual_observed),
        "missing_registry_entries": sorted(set(OBSERVATION_ARTIFACTS) - actual_observed),
        "unmapped_artifacts": unmapped,
        "legacy_semantic_leaks": sorted(set(leaks)),
        "observation_reference_only": reference_only,
    }


def _build_registry_audit_summary(per_sample: list[dict], run_contract) -> dict:
    """Phase2.2: aggregate registry audit — counts only."""
    if run_contract is None or not getattr(run_contract, "candidate_pool_enabled", False):
        return {}

    total = 0
    audit_avail = 0
    reg_consistent = 0
    map_consistent = 0
    iso_consistent = 0
    leak_dist: dict[str, int] = {}

    for entry in per_sample:
        ra = (entry.get("decision_trace") or {}).get("observation_registry_audit") or {}
        if not ra or not ra.get("audit_available"):
            continue
        total += 1
        audit_avail += 1
        if ra.get("registry_consistent"):
            reg_consistent += 1
        if ra.get("mapping_consistent"):
            map_consistent += 1
        if ra.get("isolation_consistent"):
            iso_consistent += 1
        for leak in ra.get("legacy_semantic_leaks") or []:
            leak_dist[leak] = leak_dist.get(leak, 0) + 1

    return {
        "total_samples": total,
        "audit_available_count": audit_avail,
        "registry_consistent_count": reg_consistent,
        "mapping_consistent_count": map_consistent,
        "isolation_consistent_count": iso_consistent,
        "semantic_leak_distribution": leak_dist,
    }


FORBIDDEN_CONTRACT_TERMS = frozenset({
    "score", "confidence", "probability", "quality", "correctness",
    "trust", "importance", "priority", "weight",
    "recommendation", "better", "worse", "improvement", "degradation",
    "deployment", "approval", "runtime authority",
})

RUNTIME_ISOLATION_FIELDS = frozenset({
    "pred_tokens", "metrics", "selection", "reranker", "beam",
})


def _build_observation_contract_audit(decision_trace: dict) -> dict:
    """Phase2.3: executable contract lock — runtime/semantic/registry isolation checks."""
    all_artifact_names = set(OBSERVATION_ARTIFACTS)
    for nid in OBSERVATION_ARTIFACTS:
        sk = _OBSERVATION_SOURCE_MAP.get(nid, nid)
        all_artifact_names.add(sk)

    # Runtime isolation: exact match — no observation artifact name IS a runtime field
    runtime_violations = sorted(
        art for art in all_artifact_names
        if any(art == rt or art == rt.lower() for rt in RUNTIME_ISOLATION_FIELDS)
    )
    runtime_isolation_satisfied = len(runtime_violations) == 0

    # Semantic isolation: no artifact name contains forbidden terms as word boundaries
    forbidden_detected = []
    for art_name in all_artifact_names:
        parts = set(art_name.lower().replace("_", " ").split())
        for term in FORBIDDEN_CONTRACT_TERMS:
            if term in parts or term.replace(" ", "_") in parts:
                forbidden_detected.append(art_name)
                break
    semantic_isolation_satisfied = len(forbidden_detected) == 0

    # Artifact registry: all decision_trace keys are known observation/metadata keys
    known_obs_keys = set(OBSERVATION_ARTIFACTS) | set(_OBSERVATION_SOURCE_MAP.values())
    known_obs_keys.add("observation_registry_audit")
    known_obs_keys.add("observation_contract_audit")
    meta_keys = {"selected_by", "decision_features", "diagnostic_features",
                  "hard_constraints", "posthoc_metrics"}
    registry_violations = sorted(
        k for k in decision_trace if not k.startswith("_")
        and k not in known_obs_keys and k not in meta_keys
    )
    artifact_registry_satisfied = len(registry_violations) == 0

    contract_satisfied = (runtime_isolation_satisfied and
                          semantic_isolation_satisfied and
                          artifact_registry_satisfied)

    audit_available = len(decision_trace) > 0

    return {
        "audit_available": audit_available,
        "contract_satisfied": contract_satisfied,
        "runtime_isolation_satisfied": runtime_isolation_satisfied,
        "semantic_isolation_satisfied": semantic_isolation_satisfied,
        "artifact_registry_satisfied": artifact_registry_satisfied,
        "forbidden_terms_detected": sorted(set(forbidden_detected)),
        "runtime_writeback_detected": sorted(set(runtime_violations)),
        "registry_violations": sorted(set(registry_violations)),
        "contract_scope": "observation_only",
    }


def _build_contract_audit_summary(per_sample: list[dict], run_contract) -> dict:
    """Phase2.3: aggregate contract audit — counts only."""
    if run_contract is None or not getattr(run_contract, "candidate_pool_enabled", False):
        return {}

    total = 0
    satisfied = 0
    runtime_iso = 0
    semantic_iso = 0
    registry_sat = 0
    forbidden_dist: dict[str, int] = {}

    for entry in per_sample:
        ca = (entry.get("decision_trace") or {}).get("observation_contract_audit") or {}
        if not ca or not ca.get("audit_available"):
            continue
        total += 1
        if ca.get("contract_satisfied"):
            satisfied += 1
        if ca.get("runtime_isolation_satisfied"):
            runtime_iso += 1
        if ca.get("semantic_isolation_satisfied"):
            semantic_iso += 1
        if ca.get("artifact_registry_satisfied"):
            registry_sat += 1
        for term in ca.get("forbidden_terms_detected") or []:
            forbidden_dist[term] = forbidden_dist.get(term, 0) + 1

    return {
        "total_samples": total,
        "contract_satisfied_count": satisfied,
        "runtime_isolation_count": runtime_iso,
        "semantic_isolation_count": semantic_iso,
        "registry_satisfied_count": registry_sat,
        "forbidden_term_distribution": forbidden_dist,
    }


def _build_offline_validation_observation(entry: dict, seq_metric) -> dict:
    """Phase3.0: catalog validation artifact availability — presence only, no validation."""
    legacy_metrics_present = seq_metric is not None
    cf_present = bool((entry.get("decision_trace") or {}).get("counterfactual_observation"))
    diag_present = bool((entry.get("decision_trace") or {}).get("diagnostic_audit"))
    shadow_metrics_present = cf_present

    present = []
    missing = []
    for name, available in [
        ("legacy_metrics", legacy_metrics_present),
        ("shadow_metrics", shadow_metrics_present),
        ("counterfactual", cf_present),
        ("diagnostic", diag_present),
    ]:
        if available:
            present.append(name)
        else:
            missing.append(name)

    # Phase3.0a: dynamic reference-only audit
    result_fields = [
        "observation_available", "validation_artifacts_present", "validation_artifacts_missing",
        "legacy_metrics_present", "shadow_metrics_present",
        "counterfactual_present", "diagnostic_present", "reference_only_audit",
    ]
    non_reference = []
    for field in result_fields:
        parts = set(field.lower().replace("_", " ").split())
        if parts & FORBIDDEN_CONTRACT_TERMS:
            non_reference.append(field)

    reference_only_audit = {
        "audit_available": True,
        "reference_only_satisfied": len(non_reference) == 0,
        "observed_fields": result_fields,
        "non_reference_fields": non_reference,
    }

    return {
        "observation_available": legacy_metrics_present or shadow_metrics_present,
        "validation_artifacts_present": present,
        "validation_artifacts_missing": missing,
        "legacy_metrics_present": legacy_metrics_present,
        "shadow_metrics_present": shadow_metrics_present,
        "counterfactual_present": cf_present,
        "diagnostic_present": diag_present,
        "reference_only_audit": reference_only_audit,
    }


def _build_offline_validation_summary(per_sample: list[dict], run_contract) -> dict:
    """Phase3.0: aggregate validation artifact availability — counts only."""
    if run_contract is None or not getattr(run_contract, "candidate_pool_enabled", False):
        return {}

    total = 0
    obs_avail = 0
    legacy = 0
    shadow = 0
    cf = 0
    diag = 0
    ref_satisfied = 0
    missing_dist: dict[str, int] = {}
    non_ref_dist: dict[str, int] = {}

    for entry in per_sample:
        ov = (entry.get("decision_trace") or {}).get("offline_validation_observation") or {}
        if not ov:
            continue
        total += 1
        if ov.get("observation_available"):
            obs_avail += 1
        if ov.get("legacy_metrics_present"):
            legacy += 1
        if ov.get("shadow_metrics_present"):
            shadow += 1
        if ov.get("counterfactual_present"):
            cf += 1
        if ov.get("diagnostic_present"):
            diag += 1
        for m in ov.get("validation_artifacts_missing") or []:
            missing_dist[m] = missing_dist.get(m, 0) + 1
        ra = ov.get("reference_only_audit") or {}
        if ra.get("reference_only_satisfied"):
            ref_satisfied += 1
        for nf in ra.get("non_reference_fields") or []:
            non_ref_dist[nf] = non_ref_dist.get(nf, 0) + 1

    return {
        "total_samples": total,
        "observation_available_count": obs_avail,
        "legacy_metrics_present_count": legacy,
        "shadow_metrics_present_count": shadow,
        "counterfactual_present_count": cf,
        "diagnostic_present_count": diag,
        "missing_distribution": missing_dist,
        "reference_only_satisfied_count": ref_satisfied,
        "non_reference_distribution": non_ref_dist,
    }


ARTIFACT_CATEGORIES = {
    "candidate_observation": "candidate_related",
    "observed_comparison": "comparison_related",
    "diagnostic_consistency": "diagnostic_related",
    "counterfactual_observation": "comparison_related",
    "difference_attribution": "comparison_related",
    "diagnostic_audit": "diagnostic_related",
    "runtime_readiness_observation": "diagnostic_related",
    "artifact_provenance": "registry_related",
    "cross_artifact_relationship": "registry_related",
    "selection_observation": "candidate_related",
    "disagreement_characterization": "comparison_related",
    "observation_coverage": "registry_related",
    "observation_registry_audit": "registry_related",
    "observation_contract_audit": "diagnostic_related",
}


def _build_observation_surface_audit(decision_trace: dict) -> dict:
    """Phase3.1: observation surface completeness — presence/absence by category."""
    registered = len(OBSERVATION_ARTIFACTS)
    present = 0
    missing = []
    present_ids = set()

    shadow = decision_trace.get("shadow_decision_core") or {}
    for neutral_id in OBSERVATION_ARTIFACTS:
        sk = _OBSERVATION_SOURCE_MAP.get(neutral_id, neutral_id)
        if neutral_id in _NESTED_ARTIFACTS:
            exists = bool(shadow.get(sk))
        elif neutral_id == "observation_coverage":
            exists = bool(decision_trace.get(sk))
        else:
            exists = bool(decision_trace.get(sk))
        if exists:
            present += 1
            present_ids.add(neutral_id)
        else:
            missing.append(neutral_id)

    # Category counts: present only (Phase3.1a fix)
    categories: dict[str, int] = {}
    for neutral_id in present_ids:
        cat = ARTIFACT_CATEGORIES.get(neutral_id, "unclassified")
        categories[cat] = categories.get(cat, 0) + 1

    # Registry structure: all registered
    registered_categories: dict[str, int] = {}
    for neutral_id in OBSERVATION_ARTIFACTS:
        cat = ARTIFACT_CATEGORIES.get(neutral_id, "unclassified")
        registered_categories[cat] = registered_categories.get(cat, 0) + 1

    fully = present == registered
    partially = present > 0 and not fully

    # Phase3.1b: dynamic reference-only audit
    surface_fields = [
        "observation_available", "observed_artifacts", "artifact_categories",
        "registered_artifact_categories", "completeness_observation",
        "reference_only_audit",
    ]
    non_ref = []
    for field in surface_fields:
        parts = set(field.lower().replace("_", " ").split())
        if parts & FORBIDDEN_CONTRACT_TERMS:
            non_ref.append(field)
    ref_audit = {
        "audit_available": True,
        "reference_only_satisfied": len(non_ref) == 0,
        "inspected_fields": list(surface_fields),
        "non_reference_fields": non_ref,
    }

    return {
        "observation_available": present > 0,
        "observed_artifacts": {
            "total_registered": registered,
            "total_present": present,
            "total_missing": registered - present,
        },
        "artifact_categories": categories,
        "registered_artifact_categories": registered_categories,
        "completeness_observation": {
            "fully_observed": fully,
            "partially_observed": partially,
            "missing_artifacts": missing,
        },
        "reference_only_audit": ref_audit,
    }


def _build_observation_surface_summary(per_sample: list[dict], run_contract) -> dict:
    """Phase3.1: aggregate surface completeness — counts only."""
    if run_contract is None or not getattr(run_contract, "candidate_pool_enabled", False):
        return {}

    total = 0
    obs_avail = 0
    fully = 0
    partially = 0
    missing_dist: dict[str, int] = {}
    cat_dist: dict[str, int] = {}

    for entry in per_sample:
        sa = (entry.get("decision_trace") or {}).get("observation_surface_audit") or {}
        if not sa or not sa.get("observation_available"):
            continue
        total += 1
        obs_avail += 1
        co = sa.get("completeness_observation") or {}
        if co.get("fully_observed"):
            fully += 1
        if co.get("partially_observed"):
            partially += 1
        for m in co.get("missing_artifacts") or []:
            missing_dist[m] = missing_dist.get(m, 0) + 1
        for cat, cnt in (sa.get("artifact_categories") or {}).items():
            cat_dist[cat] = cat_dist.get(cat, 0) + cnt

    return {
        "total_samples": total,
        "observation_available_count": obs_avail,
        "fully_observed_count": fully,
        "partially_observed_count": partially,
        "missing_distribution": missing_dist,
        "category_distribution": cat_dist,
    }


def _build_observation_reference_summary(per_sample: list[dict], run_contract) -> dict:
    """Phase3.1b: aggregate reference-only audit — counts only."""
    if run_contract is None or not getattr(run_contract, "candidate_pool_enabled", False):
        return {}

    total = 0
    ref_satisfied = 0
    non_ref_dist: dict[str, int] = {}

    for entry in per_sample:
        sa = (entry.get("decision_trace") or {}).get("observation_surface_audit") or {}
        ra = sa.get("reference_only_audit") or {}
        if not ra or not ra.get("audit_available"):
            continue
        total += 1
        if ra.get("reference_only_satisfied"):
            ref_satisfied += 1
        for nf in ra.get("non_reference_fields") or []:
            non_ref_dist[nf] = non_ref_dist.get(nf, 0) + 1

    return {
        "total_samples": total,
        "reference_only_satisfied_count": ref_satisfied,
        "non_reference_distribution": non_ref_dist,
    }


def _metric_delta(leg: Optional[float], shad: Optional[float]) -> Optional[float]:
    if leg is None or shad is None:
        return None
    return round(shad - leg, 6)


def _build_shadow_offline_evaluation(shadow: dict, evidence: dict, seq_metric) -> dict:
    """Phase4: shadow offline evaluation — observed metric comparison, no quality claims."""
    outcome = shadow.get("comparison_outcome") or {}
    legacy_exists = bool(outcome.get("legacy_candidate_exists"))
    shadow_exists = bool(outcome.get("shadow_candidate_exists"))
    comparison_available = legacy_exists and shadow_exists

    # Legacy metrics from already-computed seq_metrics
    legacy_lcs = seq_metric.lcs_ratio if seq_metric else None
    legacy_token_acc = seq_metric.token_accuracy if seq_metric else None
    legacy_set_f1 = seq_metric.set_f1 if seq_metric else None

    # Usability / executable not available in mainline report
    legacy_usable = None
    legacy_executable = None

    # Semantic from evidence bundle
    mapping = evidence.get("mapping_evidence") or {}
    sem = mapping.get("semantic_score") or {}
    legacy_semantic = float(sem["value"]) if sem.get("status") == "available" and sem.get("value") is not None else None

    legacy_observed = {
        "sequence_lcs": legacy_lcs,
        "token_acc": legacy_token_acc,
        "set_f1": legacy_set_f1,
        "usable": legacy_usable,
        "executable": legacy_executable,
        "semantic_coverage": legacy_semantic,
    }

    # Shadow observed: sequence metrics never computed against reference → None
    exec_ev = evidence.get("execution_evidence") or {}
    shadow_validity = float(exec_ev["validity"]["value"]) if (
        exec_ev.get("status") == "available"
        and (exec_ev.get("validity") or {}).get("value") is not None
    ) else None

    shadow_semantic = float(sem["value"]) if sem.get("status") == "available" and sem.get("value") is not None else None

    shadow_observed = {
        "sequence_lcs": None,
        "token_acc": None,
        "set_f1": None,
        "usable": None,
        "executable": shadow_validity,
        "semantic_coverage": shadow_semantic,
    }

    # Deltas only where both non-None
    metric_difference = {
        "sequence_lcs_delta": _metric_delta(legacy_lcs, shadow_observed["sequence_lcs"]),
        "token_acc_delta": _metric_delta(legacy_token_acc, shadow_observed["token_acc"]),
        "set_f1_delta": _metric_delta(legacy_set_f1, shadow_observed["set_f1"]),
        "usable_delta": _metric_delta(legacy_usable, shadow_observed["usable"]),
        "executable_delta": _metric_delta(legacy_executable, shadow_observed["executable"]),
        "semantic_coverage_delta": _metric_delta(legacy_semantic, shadow_semantic),
    }

    comparable = any(v is not None for v in metric_difference.values())
    comparable_metrics_available = comparable and comparison_available

    return {
        "comparison_available": comparison_available,
        "legacy_output_available": legacy_exists,
        "shadow_output_available": shadow_exists,
        "comparable_metrics_available": comparable_metrics_available,
        "legacy_observed_metrics": legacy_observed,
        "shadow_observed_metrics": shadow_observed,
        "metric_difference": metric_difference,
    }


def _build_shadow_offline_eval_summary(per_sample: list[dict], run_contract) -> dict:
    """Phase4: aggregate offline evaluation — counts/means only, no quality claims."""
    if run_contract is None or not getattr(run_contract, "candidate_pool_enabled", False):
        return {}

    total = 0
    comp_avail = 0
    comp_metrics = 0
    lcs_deltas = []
    tok_deltas = []
    setf1_deltas = []
    usable_deltas = []
    exec_deltas = []
    missing_dist: dict[str, int] = {}

    for entry in per_sample:
        se = (entry.get("decision_trace") or {}).get("shadow_offline_evaluation") or {}
        if not se:
            continue
        total += 1
        if se.get("comparison_available"):
            comp_avail += 1
        if se.get("comparable_metrics_available"):
            comp_metrics += 1

        md = se.get("metric_difference") or {}
        for key, val in md.items():
            if val is None:
                missing_dist[key] = missing_dist.get(key, 0) + 1
            else:
                val_f = float(val)
                if key == "sequence_lcs_delta":
                    lcs_deltas.append(val_f)
                elif key == "token_acc_delta":
                    tok_deltas.append(val_f)
                elif key == "set_f1_delta":
                    setf1_deltas.append(val_f)

        u_val = md.get("usable_delta")
        if u_val is not None:
            usable_deltas.append(int(u_val))
        e_val = md.get("executable_delta")
        if e_val is not None:
            exec_deltas.append(int(e_val))

    def _mean(vals):
        return round(sum(vals) / len(vals), 6) if vals else None

    return {
        "total_samples": total,
        "comparison_available_count": comp_avail,
        "comparable_metrics_count": comp_metrics,
        "sequence_lcs_delta_mean": _mean(lcs_deltas),
        "token_acc_delta_mean": _mean(tok_deltas),
        "set_f1_delta_mean": _mean(setf1_deltas),
        "usable_delta_distribution": {
            str(v): usable_deltas.count(v) for v in sorted(set(usable_deltas))
        },
        "executable_delta_distribution": {
            str(v): exec_deltas.count(v) for v in sorted(set(exec_deltas))
        },
        "missing_metric_distribution": missing_dist,
    }


def _build_shadow_task_slice(decision_trace: dict, task_type: Optional[str]) -> dict:
    """Phase4.1: task-slice analysis — carry task category + metric deltas."""
    se = decision_trace.get("shadow_offline_evaluation") or {}
    deltas = se.get("metric_difference") or {}

    slice_available = bool(se.get("comparison_available")) and task_type is not None

    return {
        "slice_available": slice_available,
        "task_category": task_type,
        "metric_presence": {
            "sequence_lcs_present": deltas.get("sequence_lcs_delta") is not None,
            "token_acc_present": deltas.get("token_acc_delta") is not None,
            "set_f1_present": deltas.get("set_f1_delta") is not None,
            "usable_present": deltas.get("usable_delta") is not None,
            "executable_present": deltas.get("executable_delta") is not None,
            "semantic_coverage_present": deltas.get("semantic_coverage_delta") is not None,
        },
        "observed_deltas": {
            "sequence_lcs_delta": deltas.get("sequence_lcs_delta"),
            "token_acc_delta": deltas.get("token_acc_delta"),
            "set_f1_delta": deltas.get("set_f1_delta"),
            "usable_delta": deltas.get("usable_delta"),
            "executable_delta": deltas.get("executable_delta"),
            "semantic_coverage_delta": deltas.get("semantic_coverage_delta"),
        },
    }


def _build_shadow_task_slice_summary(per_sample: list[dict], run_contract) -> dict:
    """Phase4.1: aggregate task slices — per-category means, no quality claims."""
    if run_contract is None or not getattr(run_contract, "candidate_pool_enabled", False):
        return {}

    total = 0
    cat_counts: dict[str, int] = {}
    cat_lcs: dict[str, list[float]] = {}
    cat_tok: dict[str, list[float]] = {}
    cat_f1: dict[str, list[float]] = {}
    cat_usable: dict[str, list[int]] = {}
    cat_exec: dict[str, list[int]] = {}
    cat_missing: dict[str, dict[str, int]] = {}

    for entry in per_sample:
        ts = (entry.get("decision_trace") or {}).get("shadow_task_slice") or {}
        if not ts or not ts.get("slice_available"):
            continue
        total += 1
        cat = ts.get("task_category") or "unknown"
        cat_counts[cat] = cat_counts.get(cat, 0) + 1

        od = ts.get("observed_deltas") or {}
        if od.get("sequence_lcs_delta") is not None:
            cat_lcs.setdefault(cat, []).append(float(od["sequence_lcs_delta"]))
        if od.get("token_acc_delta") is not None:
            cat_tok.setdefault(cat, []).append(float(od["token_acc_delta"]))
        if od.get("set_f1_delta") is not None:
            cat_f1.setdefault(cat, []).append(float(od["set_f1_delta"]))
        if od.get("usable_delta") is not None:
            cat_usable.setdefault(cat, []).append(int(od["usable_delta"]))
        if od.get("executable_delta") is not None:
            cat_exec.setdefault(cat, []).append(int(od["executable_delta"]))

        mp = ts.get("metric_presence") or {}
        mcount = sum(1 for v in mp.values() if not v)
        if mcount > 0:
            cat_missing.setdefault(cat, {})["missing_count"] = \
                cat_missing.setdefault(cat, {}).get("missing_count", 0) + mcount

    def _m(vals):
        return round(sum(vals) / len(vals), 6) if vals else None

    per_category = {}
    for cat in cat_counts:
        ud_vals = cat_usable.get(cat, [])
        ed_vals = cat_exec.get(cat, [])
        per_category[cat] = {
            "sample_count": cat_counts[cat],
            "sequence_lcs_delta_mean": _m(cat_lcs.get(cat, [])),
            "token_acc_delta_mean": _m(cat_tok.get(cat, [])),
            "set_f1_delta_mean": _m(cat_f1.get(cat, [])),
            "usable_delta_distribution": {str(v): ud_vals.count(v) for v in sorted(set(ud_vals))},
            "executable_delta_distribution": {str(v): ed_vals.count(v) for v in sorted(set(ed_vals))},
            "missing_metric_distribution": cat_missing.get(cat, {}),
        }

    return {
        "total_samples": total,
        "category_distribution": cat_counts,
        "per_category": per_category,
    }


def _build_shadow_dataset_slice(task_type: Optional[str], evidence: dict, candidate_pool_trace: list, metric_present: bool) -> dict:
    """Phase4.2: dataset slice observation — catalog per-sample observable attributes."""
    slice_available = task_type is not None

    ev = evidence or {}
    has_exec = (ev.get("execution_evidence") or {}).get("status") == "available"
    has_map = (ev.get("mapping_evidence") or {}).get("status") == "available"
    sem = (ev.get("mapping_evidence") or {}).get("semantic_score") or {}
    has_sem = sem.get("status") == "available"

    synthetic_present = any(
        row.get("source") == "legacy_selected_fallback" or row.get("candidate_origin") == "synthetic"
        for row in (candidate_pool_trace or [])
    )
    retrieval_present = any(
        row.get("source") == "retrieval_shadow"
        for row in (candidate_pool_trace or [])
    )

    return {
        "slice_available": slice_available,
        "dataset_context": {
            "task_type_present": task_type is not None,
            "evidence_present": bool(evidence),
            "metric_present": metric_present,
        },
        "observed_slice_attributes": {
            "has_execution_evidence": has_exec,
            "has_mapping_evidence": has_map,
            "has_semantic_evidence": has_sem,
            "synthetic_candidate_present": synthetic_present,
            "retrieval_candidate_present": retrieval_present,
        },
    }


def _build_shadow_dataset_slice_summary(per_sample: list[dict], run_contract) -> dict:
    """Phase4.2: aggregate dataset slice — distribution counts only."""
    if run_contract is None or not getattr(run_contract, "candidate_pool_enabled", False):
        return {}

    total = 0
    slice_avail = 0
    task_dist: dict[str, int] = {}
    ev_dist: dict[str, int] = {}
    synth = 0
    retr = 0

    for entry in per_sample:
        ds = (entry.get("decision_trace") or {}).get("shadow_dataset_slice") or {}
        if not ds or not ds.get("slice_available"):
            continue
        total += 1
        slice_avail += 1
        ctx = ds.get("dataset_context") or {}
        if ctx.get("task_type_present"):
            task_dist[entry.get("task_type", "unknown")] = task_dist.get(entry.get("task_type", "unknown"), 0) + 1
        if ctx.get("evidence_present"):
            ev_dist["evidence_present"] = ev_dist.get("evidence_present", 0) + 1
        attr = ds.get("observed_slice_attributes") or {}
        if attr.get("synthetic_candidate_present"):
            synth += 1
        if attr.get("retrieval_candidate_present"):
            retr += 1

    return {
        "total_samples": total,
        "slice_available_count": slice_avail,
        "task_distribution": task_dist,
        "evidence_distribution": ev_dist,
        "synthetic_distribution": {"synthetic_present_count": synth},
        "retrieval_distribution": {"retrieval_present_count": retr},
    }


def _build_shadow_replay_evaluation(shadow: dict, seq_metric, ref_tokens: Optional[list]) -> dict:
    """Phase4.3: shadow replay evaluation — compute shadow metrics against reference where possible."""
    outcome = shadow.get("comparison_outcome") or {}
    shadow_candidate = shadow.get("shadow_selection") or {}
    shadow_tokens = shadow_candidate.get("tokens") if shadow_candidate else None

    replay_available = bool(outcome.get("shadow_candidate_exists"))
    legacy_metrics_available = seq_metric is not None

    # Legacy from already-computed seq_metrics
    legacy_metrics = {
        "sequence_lcs": seq_metric.lcs_ratio if seq_metric else None,
        "token_acc": seq_metric.token_accuracy if seq_metric else None,
        "set_f1": seq_metric.set_f1 if seq_metric else None,
    }

    # Shadow: compute against reference only if both exist
    shadow_metrics_available = shadow_tokens is not None and ref_tokens is not None
    shadow_metrics = {"sequence_lcs": None, "token_acc": None, "set_f1": None}

    if shadow_metrics_available:
        ref = [t for t in ref_tokens if t >= 0]  # strip special tokens
        sw = [t for t in shadow_tokens if t >= 0]
        # LCS ratio
        from gis_recommend.training.train_v4_2 import ScheduledSamplingTrainerV4_2
        shadow_metrics["sequence_lcs"] = round(
            ScheduledSamplingTrainerV4_2._lcs_ratio(sw, ref), 6)
        shadow_metrics["set_f1"] = round(
            ScheduledSamplingTrainerV4_2._set_f1(sw, ref), 6)
        # Token accuracy: positional match, normalized
        min_len = min(len(sw), len(ref))
        if min_len > 0:
            tok_match = sum(1 for i in range(min_len) if sw[i] == ref[i])
            shadow_metrics["token_acc"] = round(tok_match / max(len(sw), len(ref)), 6)
        else:
            shadow_metrics["token_acc"] = None

    # Deltas only where both non-None
    metric_difference = {
        "sequence_lcs_delta": _metric_delta(legacy_metrics["sequence_lcs"], shadow_metrics["sequence_lcs"]),
        "token_acc_delta": _metric_delta(legacy_metrics["token_acc"], shadow_metrics["token_acc"]),
        "set_f1_delta": _metric_delta(legacy_metrics["set_f1"], shadow_metrics["set_f1"]),
    }

    metric_difference_available = any(v is not None for v in metric_difference.values())

    missing_reason = None
    if not replay_available:
        missing_reason = "no_shadow_candidate"
    elif not shadow_metrics_available:
        missing_reason = "no_reference_tokens"

    return {
        "replay_available": replay_available,
        "legacy_metrics_available": legacy_metrics_available,
        "shadow_metrics_available": shadow_metrics_available,
        "metric_difference_available": metric_difference_available,
        "missing_reason": missing_reason,
        "legacy_metrics": legacy_metrics,
        "shadow_metrics": shadow_metrics,
        "metric_difference": metric_difference,
    }


def _build_shadow_replay_summary(per_sample: list[dict], run_contract) -> dict:
    """Phase4.3: aggregate replay evaluation — counts/means only."""
    if run_contract is None or not getattr(run_contract, "candidate_pool_enabled", False):
        return {}

    total = 0
    replay_avail = 0
    shadow_avail = 0
    diff_avail = 0
    missing_dist: dict[str, int] = {}
    lcs_deltas = []
    tok_deltas = []
    f1_deltas = []

    for entry in per_sample:
        sr = (entry.get("decision_trace") or {}).get("shadow_replay_evaluation") or {}
        if not sr:
            continue
        total += 1
        if sr.get("replay_available"):
            replay_avail += 1
        if sr.get("shadow_metrics_available"):
            shadow_avail += 1
        if sr.get("metric_difference_available"):
            diff_avail += 1

        reason = sr.get("missing_reason")
        if reason:
            missing_dist[reason] = missing_dist.get(reason, 0) + 1

        md = sr.get("metric_difference") or {}
        if md.get("sequence_lcs_delta") is not None:
            lcs_deltas.append(float(md["sequence_lcs_delta"]))
        if md.get("token_acc_delta") is not None:
            tok_deltas.append(float(md["token_acc_delta"]))
        if md.get("set_f1_delta") is not None:
            f1_deltas.append(float(md["set_f1_delta"]))

    def _m(vals):
        return round(sum(vals) / len(vals), 6) if vals else None

    return {
        "total_samples": total,
        "replay_available_count": replay_avail,
        "shadow_metrics_available_count": shadow_avail,
        "metric_difference_available_count": diff_avail,
        "missing_distribution": missing_dist,
        "sequence_lcs_delta_mean": _m(lcs_deltas),
        "token_acc_delta_mean": _m(tok_deltas),
        "set_f1_delta_mean": _m(f1_deltas),
    }


def _build_shadow_failure_observation(decision_trace: dict, evidence: dict, candidate_pool_trace: list) -> dict:
    """Phase4.4: failure pattern observation — catalog conditions when metrics are missing."""
    sr = decision_trace.get("shadow_replay_evaluation") or {}
    metric_available = sr.get("shadow_metrics_available", False)

    ev = evidence or {}
    exec_missing = (ev.get("execution_evidence") or {}).get("status") != "available"
    sem_missing = ((ev.get("mapping_evidence") or {}).get("semantic_score") or {}).get("status") != "available"
    map_missing = (ev.get("mapping_evidence") or {}).get("status") != "available"

    # Synthetic from diagnostic_consistency
    shadow = decision_trace.get("shadow_decision_core") or {}
    dc = shadow.get("diagnostic_consistency") or {}
    synthetic_present = bool(dc.get("synthetic_only_pool"))

    # Retrieval from candidate_pool_trace artifact presence
    retrieval_present = any(
        row.get("source") == "retrieval_shadow"
        for row in (candidate_pool_trace or [])
    )

    sm = sr.get("shadow_metrics") or {}
    return {
        "observation_available": sr.get("replay_available", False),
        "metric_available": metric_available,
        "observable_conditions": {
            "execution_evidence_missing": exec_missing,
            "semantic_evidence_missing": sem_missing,
            "mapping_evidence_missing": map_missing,
            "synthetic_candidate_present": synthetic_present,
            "retrieval_candidate_present": retrieval_present,
        },
        "observed_metric_state": {
            "sequence_lcs_present": sm.get("sequence_lcs") is not None,
            "token_acc_present": sm.get("token_acc") is not None,
            "set_f1_present": sm.get("set_f1") is not None,
        },
    }


def _build_shadow_failure_summary(per_sample: list[dict], run_contract) -> dict:
    """Phase4.4: aggregate failure patterns — condition distribution only."""
    if run_contract is None or not getattr(run_contract, "candidate_pool_enabled", False):
        return {}

    total = 0
    obs_avail = 0
    cond_dist: dict[str, int] = {}
    metric_dist: dict[str, int] = {}

    for entry in per_sample:
        sf = (entry.get("decision_trace") or {}).get("shadow_failure_observation") or {}
        if not sf or not sf.get("observation_available"):
            continue
        total += 1
        obs_avail += 1
        for key, val in (sf.get("observable_conditions") or {}).items():
            if val:
                cond_dist[key] = cond_dist.get(key, 0) + 1
        for key, val in (sf.get("observed_metric_state") or {}).items():
            if val:
                metric_dist[key] = metric_dist.get(key, 0) + 1

    return {
        "total_samples": total,
        "observation_available_count": obs_avail,
        "condition_distribution": cond_dist,
        "metric_presence_distribution": metric_dist,
    }


def _build_shadow_runtime_trial(decision_trace: dict) -> dict:
    """Phase5.0: controlled runtime shadow trial — authority OFF, observe deltas only."""
    sr = decision_trace.get("shadow_replay_evaluation") or {}
    outcome = (decision_trace.get("shadow_decision_core") or {}).get("comparison_outcome") or {}

    trial_available = sr.get("replay_available", False)
    legacy_exists = bool(outcome.get("legacy_candidate_exists"))
    shadow_exists = bool(outcome.get("shadow_candidate_exists"))
    comparison_available = sr.get("shadow_metrics_available", False)

    # Observed outcome from metric deltas
    md = sr.get("metric_difference") or {}
    available_deltas = {k: v for k, v in md.items() if v is not None}
    shadow_win = None
    legacy_win = None
    tie_obs = None

    if available_deltas and comparison_available:
        all_pos = all(v > 0 for v in available_deltas.values())
        all_neg = all(v < 0 for v in available_deltas.values())
        all_zero = all(v == 0 for v in available_deltas.values())

        if all_pos:
            shadow_win = True
            legacy_win = False
            tie_obs = False
        elif all_neg:
            shadow_win = False
            legacy_win = True
            tie_obs = False
        elif all_zero:
            shadow_win = False
            legacy_win = False
            tie_obs = True
        # mixed cases: leave all as None

    return {
        "trial_available": trial_available,
        "legacy_candidate_exists": legacy_exists,
        "shadow_candidate_exists": shadow_exists,
        "legacy_metrics_available": sr.get("legacy_metrics_available", False),
        "shadow_metrics_available": comparison_available,
        "comparison_available": comparison_available,
        "observed_outcome": {
            "shadow_win_observed": shadow_win,
            "legacy_win_observed": legacy_win,
            "tie_observed": tie_obs,
        },
        "runtime_authority": {
            "shadow_authority_enabled": False,
            "shadow_weight": 0.0,
        },
    }


def _build_shadow_runtime_summary(per_sample: list[dict], run_contract) -> dict:
    """Phase5.0: aggregate runtime trial — counts only, authority OFF."""
    if run_contract is None or not getattr(run_contract, "candidate_pool_enabled", False):
        return {}

    total = 0
    trial_avail = 0
    comp_avail = 0
    sw_win = 0
    lw_win = 0
    tie = 0
    auth_enabled = 0
    weights = []

    for entry in per_sample:
        rt = (entry.get("decision_trace") or {}).get("shadow_runtime_trial") or {}
        if not rt or not rt.get("trial_available"):
            continue
        total += 1
        trial_avail += 1
        if rt.get("comparison_available"):
            comp_avail += 1
        oo = rt.get("observed_outcome") or {}
        if oo.get("shadow_win_observed"):
            sw_win += 1
        if oo.get("legacy_win_observed"):
            lw_win += 1
        if oo.get("tie_observed"):
            tie += 1
        ra = rt.get("runtime_authority") or {}
        if ra.get("shadow_authority_enabled"):
            auth_enabled += 1
        weights.append(ra.get("shadow_weight", 0.0))

    return {
        "total_samples": total,
        "trial_available_count": trial_avail,
        "comparison_available_count": comp_avail,
        "shadow_win_count": sw_win,
        "legacy_win_count": lw_win,
        "tie_count": tie,
        "shadow_authority_enabled_count": auth_enabled,
        "mean_shadow_weight": round(sum(weights) / max(len(weights), 1), 6),
    }


def _build_shadow_authority_readiness(decision_trace: dict) -> dict:
    """Phase5.1: authority readiness observation — catalog prerequisites, no authority grant."""
    rt = decision_trace.get("shadow_runtime_trial") or {}
    sr = decision_trace.get("shadow_replay_evaluation") or {}
    se = decision_trace.get("shadow_offline_evaluation") or {}

    readiness_available = rt.get("trial_available", False)
    metric_available = sr.get("shadow_metrics_available", False)
    usable_available = (se.get("legacy_observed_metrics") or {}).get("usable") is not None
    execution_available = (se.get("shadow_observed_metrics") or {}).get("executable") is not None
    comparison_available = rt.get("comparison_available", False)

    oo = rt.get("observed_outcome") or {}
    sw_win = oo.get("shadow_win_observed")

    return {
        "readiness_observation_available": readiness_available,
        "metric_observation_available": metric_available,
        "usable_observation_available": usable_available,
        "execution_observation_available": execution_available,
        "comparison_observation_available": comparison_available,
        "observed_conditions": {
            "shadow_win_observed": sw_win,
            "usable_not_worse": None,
            "execution_not_worse": None,
        },
        "authority_state": {
            "shadow_authority_enabled": False,
            "shadow_weight": 0.0,
        },
    }


def _build_shadow_authority_summary(per_sample: list[dict], run_contract) -> dict:
    """Phase5.1: aggregate authority readiness — counts only, authority OFF."""
    if run_contract is None or not getattr(run_contract, "candidate_pool_enabled", False):
        return {}

    total = 0
    ready = 0
    metric = 0
    usable = 0
    exec_avail = 0
    sw_win = 0
    auth_en = 0
    weights = []

    for entry in per_sample:
        ar = (entry.get("decision_trace") or {}).get("shadow_authority_readiness") or {}
        if not ar or not ar.get("readiness_observation_available"):
            continue
        total += 1
        ready += 1
        if ar.get("metric_observation_available"):
            metric += 1
        if ar.get("usable_observation_available"):
            usable += 1
        if ar.get("execution_observation_available"):
            exec_avail += 1
        oc = ar.get("observed_conditions") or {}
        if oc.get("shadow_win_observed"):
            sw_win += 1
        auth = ar.get("authority_state") or {}
        if auth.get("shadow_authority_enabled"):
            auth_en += 1
        weights.append(auth.get("shadow_weight", 0.0))

    return {
        "total_samples": total,
        "readiness_available_count": ready,
        "metric_available_count": metric,
        "usable_available_count": usable,
        "execution_available_count": exec_avail,
        "shadow_win_observed_count": sw_win,
        "authority_enabled_count": auth_en,
        "mean_shadow_weight": round(sum(weights) / max(len(weights), 1), 6),
    }


def _build_shadow_runtime_execution(shadow: dict) -> dict:
    """Phase5.2: shadow runtime dry-run — catalog selection path, no authority."""
    outcome = shadow.get("comparison_outcome") or {}
    same_sel = shadow.get("same_selection", False)
    fallback = shadow.get("fallback_triggered", False)

    execution_available = bool(outcome.get("legacy_candidate_exists"))
    legacy_exists = bool(outcome.get("legacy_candidate_exists"))
    shadow_exists = bool(outcome.get("shadow_candidate_exists"))

    skip_reason = None
    if fallback:
        skip_reason = shadow.get("fallback_reason")

    return {
        "execution_available": execution_available,
        "legacy_selected_candidate": shadow.get("legacy_candidate_id"),
        "shadow_selected_candidate": shadow.get("shadow_candidate_id"),
        "legacy_candidate_exists": legacy_exists,
        "shadow_candidate_exists": shadow_exists,
        "same_selection": same_sel,
        "shadow_execution_skipped": fallback,
        "skip_reason": skip_reason,
    }


def _build_shadow_runtime_exec_summary(per_sample: list[dict], run_contract) -> dict:
    """Phase5.2: aggregate runtime execution — counts only."""
    if run_contract is None or not getattr(run_contract, "candidate_pool_enabled", False):
        return {}

    total = 0
    exec_avail = 0
    shadow_exists = 0
    same = 0
    diff = 0
    skip_dist: dict[str, int] = {}

    for entry in per_sample:
        re = (entry.get("decision_trace") or {}).get("shadow_runtime_execution") or {}
        if not re or not re.get("execution_available"):
            continue
        total += 1
        exec_avail += 1
        if re.get("shadow_candidate_exists"):
            shadow_exists += 1
        if re.get("same_selection"):
            same += 1
        else:
            diff += 1
        if re.get("shadow_execution_skipped"):
            skip_dist[re.get("skip_reason") or "unknown"] = skip_dist.get(re.get("skip_reason") or "unknown", 0) + 1

    return {
        "total_samples": total,
        "execution_available_count": exec_avail,
        "shadow_candidate_exists_count": shadow_exists,
        "same_selection_count": same,
        "selection_difference_count": diff,
        "skip_distribution": skip_dist,
    }


def _build_shadow_runtime_evidence(decision_trace: dict) -> dict:
    """Phase5.3: runtime evidence collection — catalog observable difference conditions."""
    da = decision_trace.get("difference_attribution") or {}
    oc = da.get("observed_changes") or {}
    sel_diff = da.get("selection_changed", False)

    evidence_available = decision_trace.get("shadow_runtime_execution") is not None
    evidence_missing = not bool(da)

    missing_types = []
    if not da:
        missing_types.append("difference_attribution")

    return {
        "evidence_available": evidence_available,
        "selection_difference_observed": sel_diff,
        "observable_difference_conditions": {
            "token_difference_present": oc.get("tokens_changed", False),
            "source_difference_present": oc.get("source_changed", False),
            "execution_evidence_difference": oc.get("execution_evidence_changed", False),
            "semantic_evidence_difference": oc.get("semantic_evidence_changed", False),
            "mapping_evidence_difference": oc.get("mapping_evidence_changed", False),
            "synthetic_candidate_difference": False,
            "retrieval_candidate_difference": oc.get("retrieval_evidence_changed", False),
        },
        "evidence_missing": evidence_missing,
        "missing_evidence_types": missing_types,
    }


def _build_shadow_runtime_evidence_summary(per_sample: list[dict], run_contract) -> dict:
    """Phase5.3: aggregate runtime evidence — distribution counts only."""
    if run_contract is None or not getattr(run_contract, "candidate_pool_enabled", False):
        return {}

    total = 0
    ev_avail = 0
    sel_diff = 0
    ev_missing = 0
    diff_dist: dict[str, int] = {}
    miss_dist: dict[str, int] = {}

    for entry in per_sample:
        re = (entry.get("decision_trace") or {}).get("shadow_runtime_evidence") or {}
        if not re or not re.get("evidence_available"):
            continue
        total += 1
        ev_avail += 1
        if re.get("selection_difference_observed"):
            sel_diff += 1
        if re.get("evidence_missing"):
            ev_missing += 1
        for key, val in (re.get("observable_difference_conditions") or {}).items():
            if val:
                diff_dist[key] = diff_dist.get(key, 0) + 1
        for mt in re.get("missing_evidence_types") or []:
            miss_dist[mt] = miss_dist.get(mt, 0) + 1

    return {
        "total_samples": total,
        "evidence_available_count": ev_avail,
        "selection_difference_count": sel_diff,
        "evidence_missing_count": ev_missing,
        "observable_difference_distribution": diff_dist,
        "missing_distribution": miss_dist,
    }


def _build_shadow_runtime_pattern(decision_trace: dict) -> dict:
    """Phase5.4: runtime pattern observation — catalog repeated difference conditions."""
    re = decision_trace.get("shadow_runtime_evidence") or {}
    oc = re.get("observable_difference_conditions") or {}

    pattern_available = re.get("evidence_available", False)
    any_diff = any(v for v in oc.values() if v)

    return {
        "pattern_available": pattern_available,
        "repeated_difference_observed": any_diff,
        "observable_pattern": {
            "token_difference_repeat": oc.get("token_difference_present", False),
            "source_difference_repeat": oc.get("source_difference_present", False),
            "execution_difference_repeat": oc.get("execution_evidence_difference", False),
            "semantic_difference_repeat": oc.get("semantic_evidence_difference", False),
            "mapping_difference_repeat": oc.get("mapping_evidence_difference", False),
            "synthetic_difference_repeat": oc.get("synthetic_candidate_difference", False),
            "retrieval_difference_repeat": oc.get("retrieval_candidate_difference", False),
        },
        "pattern_observation_missing": not pattern_available,
        "missing_pattern_fields": [] if pattern_available else ["runtime_evidence"],
    }


def _build_shadow_runtime_pattern_summary(per_sample: list[dict], run_contract) -> dict:
    """Phase5.4: aggregate runtime patterns — distribution counts only."""
    if run_contract is None or not getattr(run_contract, "candidate_pool_enabled", False):
        return {}

    total = 0
    pat_avail = 0
    repeat_diff = 0
    missing = 0
    pat_dist: dict[str, int] = {}

    for entry in per_sample:
        rp = (entry.get("decision_trace") or {}).get("shadow_runtime_pattern") or {}
        if not rp:
            continue
        total += 1
        if rp.get("pattern_available"):
            pat_avail += 1
        if rp.get("repeated_difference_observed"):
            repeat_diff += 1
        if rp.get("pattern_observation_missing"):
            missing += 1
        for key, val in (rp.get("observable_pattern") or {}).items():
            if val:
                pat_dist[key] = pat_dist.get(key, 0) + 1

    return {
        "total_samples": total,
        "pattern_available_count": pat_avail,
        "repeated_difference_count": repeat_diff,
        "missing_count": missing,
        "pattern_distribution": pat_dist,
    }


def _build_shadow_influence_probe(shadow: dict, legacy_score) -> dict:
    """Phase5.5: shadow influence probe — non-authoritative scoring, recorded alongside legacy."""
    shadow_sel = shadow.get("shadow_selection") or {}
    legacy_sel = shadow.get("legacy_selection") or {}
    same_sel = shadow.get("same_selection", False)

    shadow_score = shadow_sel.get("raw_score")
    legacy_score_val = legacy_score
    score_delta = _metric_delta(legacy_score_val, shadow_score)

    # Top-K overlap: Jaccard between legacy tokens and shadow tokens
    legacy_tokens = set(legacy_sel.get("tokens") or [])
    shadow_tokens = set(shadow_sel.get("tokens") or [])
    union = legacy_tokens | shadow_tokens
    topk_overlap = len(legacy_tokens & shadow_tokens) / max(len(union), 1) if union else None

    probe_available = shadow_sel is not None

    return {
        "probe_available": bool(probe_available),
        "shadow_score": shadow_score,
        "legacy_score": legacy_score_val,
        "score_delta": score_delta,
        "ranking_agreement": same_sel,
        "topk_overlap_ratio": round(topk_overlap, 6) if topk_overlap is not None else None,
        "influence_candidate": shadow.get("shadow_candidate_id"),
    }


def _build_shadow_influence_summary(per_sample: list[dict], run_contract) -> dict:
    """Phase5.5: aggregate influence probe — means/counts only."""
    if run_contract is None or not getattr(run_contract, "candidate_pool_enabled", False):
        return {}

    total = 0
    probe_avail = 0
    agree = 0
    deltas = []
    overlaps = []

    for entry in per_sample:
        ip = (entry.get("decision_trace") or {}).get("shadow_influence_probe") or {}
        if not ip or not ip.get("probe_available"):
            continue
        total += 1
        probe_avail += 1
        if ip.get("ranking_agreement"):
            agree += 1
        sd = ip.get("score_delta")
        if sd is not None:
            deltas.append(float(sd))
        to = ip.get("topk_overlap_ratio")
        if to is not None:
            overlaps.append(float(to))

    return {
        "total_samples": total,
        "probe_available_count": probe_avail,
        "ranking_agreement_count": agree,
        "mean_score_delta": round(sum(deltas) / max(len(deltas), 1), 6) if deltas else None,
        "mean_topk_overlap": round(sum(overlaps) / max(len(overlaps), 1), 6) if overlaps else None,
    }


def _build_signal_extraction(decision_trace: dict, sample_id: str) -> dict:
    """Extract stable, non-semantic signals from decision_trace for lightweight reranker."""
    re = decision_trace.get("shadow_runtime_execution") or {}
    ip = decision_trace.get("shadow_influence_probe") or {}
    fe = decision_trace.get("shadow_failure_observation") or {}
    rv = decision_trace.get("shadow_runtime_evidence") or {}

    sel_agree = int(re.get("same_selection", False))
    score_delta = ip.get("score_delta")
    retrieval = int((fe.get("observable_conditions") or {}).get("retrieval_candidate_present", False))
    execution = int(not (fe.get("observable_conditions") or {}).get("execution_evidence_missing", True))
    sem_diff = int((rv.get("observable_difference_conditions") or {}).get("semantic_evidence_difference", False))

    has_shadow = re.get("shadow_candidate_exists", False)
    has_legacy = re.get("legacy_candidate_exists", False)

    return {
        "sample_id": sample_id,
        "signals": {
            "selection_agreement": sel_agree,
            "score_delta": score_delta,
            "retrieval_present": retrieval,
            "execution_present": execution,
            "semantic_difference_flag": sem_diff,
        },
        "metadata": {
            "has_shadow": has_shadow,
            "has_legacy": has_legacy,
        },
    }


def _build_signal_extraction_summary(per_sample: list[dict], run_contract) -> dict:
    """Aggregate signal extraction — distribution counts only."""
    if run_contract is None or not getattr(run_contract, "candidate_pool_enabled", False):
        return {}

    total = 0
    agree = 0
    score_none = 0
    retrieval = 0
    execution = 0
    sem = 0

    for entry in per_sample:
        sx = (entry.get("decision_trace") or {}).get("signal_extraction") or {}
        if not sx or not sx.get("signals"):
            continue
        total += 1
        s = sx["signals"]
        if s.get("selection_agreement"):
            agree += 1
        if s.get("score_delta") is None:
            score_none += 1
        if s.get("retrieval_present"):
            retrieval += 1
        if s.get("execution_present"):
            execution += 1
        if s.get("semantic_difference_flag"):
            sem += 1

    return {
        "total_samples": total,
        "selection_agreement_count": agree,
        "score_delta_missing_count": score_none,
        "retrieval_present_count": retrieval,
        "execution_present_count": execution,
        "semantic_difference_count": sem,
    }


def _build_reranker_update_signal(decision_trace: dict, sample_id: str) -> dict:
    """Minimal deterministic signal from shadow_influence_probe for reranker adjustment."""
    ip = decision_trace.get("shadow_influence_probe") or {}

    score_delta = ip.get("score_delta")
    sel_agree = int(ip.get("ranking_agreement", False))
    valid = score_delta is not None

    return {
        "sample_id": sample_id,
        "signal": {
            "score_delta": score_delta,
            "selection_agreement": sel_agree,
            "valid": valid,
        },
    }


def _evidence_aware_score(row: dict, evidence: dict) -> float:
    """Phase B1: evidence-aware candidate score — generation + evidence bonuses/penalties."""
    base = float(row.get("raw_score") or 0.0)
    score = base

    # Retrieval source bonus
    if row.get("source") == "retrieval_shadow":
        score += 0.10

    # Synthetic candidate penalty
    if row.get("candidate_origin") == "synthetic":
        score -= 0.50

    # Evidence penalties
    ev = evidence or {}
    if (ev.get("mapping_evidence") or {}).get("status") != "available":
        score -= 0.15
    if (ev.get("execution_evidence") or {}).get("status") not in ("available",):
        score -= 0.15
    sem = (ev.get("mapping_evidence") or {}).get("semantic_score") or {}
    if sem.get("status") != "available":
        score -= 0.10

    return round(score, 6)


def _build_evidence_aware_ranking(trace: list, evidence: dict, shadow: dict, seq_metric) -> dict:
    """Phase B1: evidence-aware ranking experiment — compare 4 selection strategies."""
    if not trace:
        return {"experiment_available": False, "missing_reason": "no_candidate_pool"}

    # ── score all candidates ──
    scored = []
    for row in trace:
        s = _evidence_aware_score(row, evidence)
        scored.append((s, row))
    scored.sort(key=lambda x: x[0], reverse=True)

    # ── selections ──
    legacy_row = next((r for r in trace if r.get("legacy_selected")), None)
    shadow_row = next((r for r in trace if r.get("candidate_id") == shadow.get("shadow_candidate_id")), None)

    ea_best = scored[0][1] if scored else None
    # Oracle: best non-synthetic by raw_score
    real = [(s, r) for s, r in scored if r.get("candidate_origin") != "synthetic"]
    oracle_best = real[0][1] if real else (scored[0][1] if scored else None)

    # ── metrics: compute against reference where possible ──
    ref_available = seq_metric is not None
    legacy_metrics = _quick_metrics(legacy_row, ref_available, seq_metric)
    shadow_metrics = _quick_metrics(shadow_row, ref_available, seq_metric)
    ea_metrics = _quick_metrics(ea_best, ref_available, seq_metric)
    oracle_metrics = _quick_metrics(oracle_best, ref_available, seq_metric)

    return {
        "experiment_available": True,
        "candidate_pool_size": len(trace),
        "selections": {
            "legacy": {"candidate_id": legacy_row.get("candidate_id") if legacy_row else None,
                        "score": legacy_row.get("raw_score") if legacy_row else None},
            "shadow": {"candidate_id": shadow_row.get("candidate_id") if shadow_row else None,
                        "score": shadow_row.get("raw_score") if shadow_row else None},
            "evidence_aware": {"candidate_id": ea_best.get("candidate_id") if ea_best else None,
                                "evidence_score": _evidence_aware_score(ea_best, evidence) if ea_best else None},
            "oracle_best": {"candidate_id": oracle_best.get("candidate_id") if oracle_best else None,
                             "raw_score": oracle_best.get("raw_score") if oracle_best else None},
        },
        "comparison_metrics": {
            "legacy": legacy_metrics,
            "shadow": shadow_metrics,
            "evidence_aware": ea_metrics,
            "oracle_best": oracle_metrics,
        },
        "ranking_improvement": {
            "ea_vs_legacy_score_delta": round(
                (_evidence_aware_score(ea_best, evidence) if ea_best else 0) -
                (legacy_row.get("raw_score") or 0), 6
            ) if legacy_row and ea_best else None,
            "ea_differs_from_legacy": bool(
                ea_best and legacy_row and
                ea_best.get("candidate_id") != legacy_row.get("candidate_id")
            ),
        },
    }


def _quick_metrics(row: dict | None, ref_available: bool, seq_metric) -> dict:
    """Minimal metrics for a candidate against reference."""
    if row is None or not ref_available or seq_metric is None:
        return {"available": False}
    return {
        "available": True,
        "raw_score": row.get("raw_score"),
        "candidate_origin": row.get("candidate_origin", "real"),
        "source": row.get("source"),
    }


def _build_evidence_aware_ranking_summary(per_sample: list[dict], run_contract) -> dict:
    """Phase B1: aggregate ranking experiment — comparison counts."""
    if run_contract is None or not getattr(run_contract, "candidate_pool_enabled", False):
        return {}

    total = 0
    ea_differs = 0
    ea_better_score = 0
    shadow_differs = 0

    for entry in per_sample:
        er = (entry.get("decision_trace") or {}).get("evidence_aware_ranking") or {}
        if not er or not er.get("experiment_available"):
            continue
        total += 1
        ri = er.get("ranking_improvement") or {}
        if ri.get("ea_differs_from_legacy"):
            ea_differs += 1
        delta = ri.get("ea_vs_legacy_score_delta")
        if delta is not None and delta > 0:
            ea_better_score += 1

        sel = er.get("selections") or {}
        if (sel.get("shadow") or {}).get("candidate_id") != (sel.get("legacy") or {}).get("candidate_id"):
            shadow_differs += 1

    n = max(total, 1)
    return {
        "total_samples": total,
        "ea_differs_from_legacy_count": ea_differs,
        "ea_differs_rate": round(ea_differs / n, 6),
        "ea_better_score_count": ea_better_score,
        "shadow_differs_count": shadow_differs,
    }


def _build_evidence_aware_selection_summary(per_sample: list[dict], run_contract) -> dict:
    """P0: aggregate evidence-aware selection — counts only."""
    if run_contract is None or not getattr(run_contract, "candidate_pool_enabled", False):
        return {}

    total = 0
    selected = 0
    differs = 0

    for entry in per_sample:
        ea = (entry.get("decision_trace") or {}).get("evidence_aware_selection") or {}
        if not ea or not ea.get("candidate_id"):
            continue
        total += 1
        selected += 1
        if ea.get("differs_from_legacy"):
            differs += 1

    n = max(total, 1)
    return {
        "total_samples": total,
        "evidence_aware_selected_count": selected,
        "differs_from_legacy_count": differs,
        "differs_rate": round(differs / n, 6) if n > 0 else 0.0,
    }


def build_report_json(
    test_set: list,
    seq_metrics: list[SeqMetrics],
    agg: AggregateMetrics,
    l3_results: list,
    chain_results: Optional[list],
    by_type: dict,
    coverage_info: dict,
    reranker_diagnostics: Optional[dict] = None,
    repair_diagnostics: Optional[dict] = None,
    run_contract=None,
) -> dict:
    """Build full report as JSON-serializable dict."""
    selection_policy = getattr(run_contract, "selection_policy", {}) if run_contract else {}
    diag_per_sample = reranker_diagnostics.get("per_sample", []) if reranker_diagnostics else []
    repair_per_sample = repair_diagnostics.get("per_sample", []) if repair_diagnostics else []
    per_sample = []
    for i in range(len(test_set)):
        l3_result = l3_results[i]
        entry = {
            "index": test_set[i]["index"],
            "task_type": test_set[i]["task_type"],
            "task_name": test_set[i]["task_name"],
            "ref_len": seq_metrics[i].ref_len,
            "pred_len": seq_metrics[i].pred_len,
            "set_f1": round(seq_metrics[i].set_f1, 4),
            "soft_set_sim": round(seq_metrics[i].soft_set_sim, 4),
            "l2_set_f1": round(seq_metrics[i].l2_set_f1, 4),
            "l2_accuracy": round(seq_metrics[i].l2_accuracy, 4),
            "lcs_ratio": round(seq_metrics[i].lcs_ratio, 4),
            "token_accuracy": round(seq_metrics[i].token_accuracy, 4),
            "sequence_em": seq_metrics[i].sequence_em,
            "length_ratio": round(seq_metrics[i].length_ratio, 4),
            "pred_score": l3_result.get("pred_score"),
        }
        if "pred_l3_score" in l3_result:
            entry["pred_l3_score"] = l3_result["pred_l3_score"]
        if l3_result.get("reranker_score") is not None:
            entry["reranker_score"] = l3_result["reranker_score"]
        if l3_result.get("reranker_pool_size"):
            entry["reranker_pool_size"] = l3_result["reranker_pool_size"]
        if l3_result.get("reranker_features") is not None:
            entry["reranker_features"] = l3_result["reranker_features"]
        if l3_result.get("qgis_score_components") is not None:
            entry["qgis_score_components"] = l3_result["qgis_score_components"]
        if l3_result.get("selected_qgis_chain") is not None:
            entry["selected_qgis_chain"] = l3_result["selected_qgis_chain"]
        if "selected_from_reranker" in l3_result:
            entry["selected_from_reranker"] = bool(l3_result["selected_from_reranker"])
        if i < len(diag_per_sample):
            entry.update(diag_per_sample[i])
        if i < len(repair_per_sample):
            entry.update(repair_per_sample[i])
        if chain_results:
            entry["chain"] = chain_results[i]
        if run_contract is not None:
            selected_by = (
                "optional_reranker"
                if bool(l3_result.get("selected_from_reranker"))
                else selection_policy.get("primary_selection", "v4_6_beam_top1")
            )
            candidate_pool_trace = build_candidate_pool_trace(l3_result, contract=run_contract)
            evidence_bundle = build_evidence_bundle(
                l3_result,
                contract=run_contract,
                chain_result=chain_results[i] if chain_results else None,
            )
            shadow_decision_core = build_shadow_decision_core(
                candidate_pool_trace,
                evidence_bundle,
                contract=run_contract,
            )
            entry["candidate_pool_trace"] = candidate_pool_trace
            entry["evidence_bundle"] = evidence_bundle
            if retrieval_shadow_pool := l3_result.get("retrieval_shadow_pool"):
                entry["retrieval_shadow_pool"] = retrieval_shadow_pool
            entry["decision_trace"] = {
                "selected_by": selected_by,
                "decision_features": {
                    "pred_score": entry.get("pred_score"),
                    "pred_l3_score": entry.get("pred_l3_score"),
                    "reranker_score": entry.get("reranker_score"),
                    "qgis_score_components": entry.get("qgis_score_components"),
                    "selected_from_reranker": entry.get("selected_from_reranker", False),
                },
                "diagnostic_features": {
                    "reranker_features": entry.get("reranker_features"),
                    "repair_diagnostics": entry.get("repair_diagnostics"),
                },
                "hard_constraints": [],
                "posthoc_metrics": {
                    "chain": entry.get("chain"),
                    "qgis_evaluation": selection_policy.get("qgis_evaluation", "posthoc_diagnostic"),
                },
                "shadow_decision_core": shadow_decision_core,
            }
            # ── Phase1.7: counterfactual observation ──
            counterfactual = _build_counterfactual_observation(
                entry, seq_metrics[i], shadow_decision_core, evidence_bundle,
            )
            entry["decision_trace"]["counterfactual_observation"] = counterfactual
            # ── Phase1.8: difference attribution ──
            diff_attr = _build_difference_attribution(
                shadow_decision_core, evidence_bundle,
            )
            entry["decision_trace"]["difference_attribution"] = diff_attr
            # ── Phase1.9: diagnostic consistency audit ──
            diag_audit = _build_diagnostic_audit(
                shadow_decision_core, entry["decision_trace"],
            )
            entry["decision_trace"]["diagnostic_audit"] = diag_audit
            # ── Phase1.10: runtime readiness observation ──
            readiness_obs = _build_runtime_readiness_observation(
                shadow_decision_core, evidence_bundle, entry["decision_trace"],
            )
            entry["decision_trace"]["runtime_readiness_observation"] = readiness_obs
            # ── Phase1.11: artifact provenance observation ──
            entry["decision_trace"]["artifact_provenance"] = _build_artifact_provenance(
                entry["decision_trace"], candidate_pool_trace,
            )
            # ── Phase1.12: cross-artifact relationship observation ──
            entry["decision_trace"]["cross_artifact_relationship"] = _build_cross_artifact_relationship(
                entry["decision_trace"], shadow_decision_core, evidence_bundle, candidate_pool_trace,
            )
            # ── Phase2.0: shadow selector controlled comparison ──
            entry["decision_trace"]["shadow_selector_comparison"] = _build_shadow_selector_comparison(
                shadow_decision_core, candidate_pool_trace,
            )
            # ── Phase2.0a: disagreement characterization ──
            entry["decision_trace"]["disagreement_characterization"] = _build_disagreement_characterization(
                shadow_decision_core, evidence_bundle, candidate_pool_trace,
            )
            # ── Phase2.1: observation coverage ──
            entry["decision_trace"]["observation_coverage"] = _build_observation_coverage(
                entry["decision_trace"], candidate_pool_trace, bool(evidence_bundle),
            )
            # ── Phase2.2: observation registry audit ──
            entry["decision_trace"]["observation_registry_audit"] = _build_observation_registry_audit(
                entry["decision_trace"],
            )
            # ── Phase2.3: observation contract audit ──
            entry["decision_trace"]["observation_contract_audit"] = _build_observation_contract_audit(
                entry["decision_trace"],
            )
            # ── Phase3.0: offline validation observation ──
            entry["decision_trace"]["offline_validation_observation"] = _build_offline_validation_observation(
                entry, seq_metrics[i],
            )
            # ── Phase3.1: observation surface completeness audit ──
            entry["decision_trace"]["observation_surface_audit"] = _build_observation_surface_audit(
                entry["decision_trace"],
            )
            # ── Phase4: shadow offline evaluation ──
            entry["decision_trace"]["shadow_offline_evaluation"] = _build_shadow_offline_evaluation(
                shadow_decision_core, evidence_bundle, seq_metrics[i],
            )
            # ── Phase4.1: shadow task slice analysis ──
            entry["decision_trace"]["shadow_task_slice"] = _build_shadow_task_slice(
                entry["decision_trace"], entry.get("task_type"),
            )
            # ── Phase4.2: dataset slice observation ──
            entry["decision_trace"]["shadow_dataset_slice"] = _build_shadow_dataset_slice(
                entry.get("task_type"), evidence_bundle, candidate_pool_trace,
                seq_metrics[i] is not None,
            )
            # ── Phase4.3: shadow replay evaluation ──
            entry["decision_trace"]["shadow_replay_evaluation"] = _build_shadow_replay_evaluation(
                shadow_decision_core, seq_metrics[i],
                test_set[i].get("reference_tokens"),
            )
            # ── Phase4.4: shadow failure pattern observation ──
            entry["decision_trace"]["shadow_failure_observation"] = _build_shadow_failure_observation(
                entry["decision_trace"], evidence_bundle, candidate_pool_trace,
            )
            # ── Phase5.0: controlled runtime shadow trial ──
            entry["decision_trace"]["shadow_runtime_trial"] = _build_shadow_runtime_trial(
                entry["decision_trace"],
            )
            # ── Phase5.1: authority readiness observation ──
            entry["decision_trace"]["shadow_authority_readiness"] = _build_shadow_authority_readiness(
                entry["decision_trace"],
            )
            # ── Phase5.2: shadow runtime dry-run ──
            entry["decision_trace"]["shadow_runtime_execution"] = _build_shadow_runtime_execution(
                shadow_decision_core,
            )
            # ── Phase5.3: shadow runtime evidence collection ──
            entry["decision_trace"]["shadow_runtime_evidence"] = _build_shadow_runtime_evidence(
                entry["decision_trace"],
            )
            # ── Phase5.4: shadow runtime pattern observation ──
            entry["decision_trace"]["shadow_runtime_pattern"] = _build_shadow_runtime_pattern(
                entry["decision_trace"],
            )
            # ── Phase5.5: shadow influence probe ──
            entry["decision_trace"]["shadow_influence_probe"] = _build_shadow_influence_probe(
                shadow_decision_core, entry.get("pred_score"),
            )
            # ── Signal extraction ──
            entry["decision_trace"]["signal_extraction"] = _build_signal_extraction(
                entry["decision_trace"], str(test_set[i].get("index", i)),
            )
            # ── Reranker update signal ──
            entry["decision_trace"]["reranker_update_signal"] = _build_reranker_update_signal(
                entry["decision_trace"], str(test_set[i].get("index", i)),
            )
            # ── Phase B1: evidence-aware ranking experiment ──
            entry["decision_trace"]["evidence_aware_ranking"] = _build_evidence_aware_ranking(
                candidate_pool_trace, evidence_bundle, shadow_decision_core, seq_metrics[i],
            )
            # ── P0: Evidence-aware candidate selection (replacement) ──
            ea_candidate = select_evidence_aware_candidate(candidate_pool_trace, evidence_bundle)
            legacy_tokens_for_compare = l3_result.get("pred_tokens") or []
            entry["decision_trace"]["evidence_aware_selection"] = {
                "candidate_id": ea_candidate.get("candidate_id") if ea_candidate else None,
                "tokens": ea_candidate.get("tokens") if ea_candidate else None,
                "evidence_aware_score": ea_candidate.get("evidence_aware_score") if ea_candidate else None,
                "source": ea_candidate.get("source") if ea_candidate else None,
                "differs_from_legacy": bool(
                    ea_candidate and ea_candidate.get("tokens") != legacy_tokens_for_compare
                ),
            } if ea_candidate else {"candidate_id": None, "tokens": None}
        per_sample.append(entry)

    # ── Phase1.5: shadow comparison aggregate summary ──
    shadow_summary = _build_shadow_comparison_summary(per_sample, run_contract)
    lift_summary = _build_shadow_observation_summary(per_sample, run_contract)
    counterfactual_summary = _build_shadow_counterfactual_summary(per_sample, run_contract)
    diff_summary = _build_shadow_difference_summary(per_sample, run_contract)
    diag_summary = _build_shadow_diagnostic_summary(per_sample, run_contract)
    readiness_summary = _build_shadow_runtime_readiness_summary(per_sample, run_contract)
    provenance_summary = _build_shadow_provenance_summary(per_sample, run_contract)
    cross_artifact_summary = _build_cross_artifact_summary(per_sample, run_contract)
    selector_summary = _build_shadow_selector_summary(per_sample, run_contract)
    disagreement_summary = _build_disagreement_summary(per_sample, run_contract)
    coverage_summary = _build_observation_coverage_summary(per_sample, run_contract)
    registry_audit_summary = _build_registry_audit_summary(per_sample, run_contract)
    contract_audit_summary = _build_contract_audit_summary(per_sample, run_contract)
    offline_val_summary = _build_offline_validation_summary(per_sample, run_contract)
    surface_summary = _build_observation_surface_summary(per_sample, run_contract)
    ref_summary = _build_observation_reference_summary(per_sample, run_contract)
    offline_eval_summary = _build_shadow_offline_eval_summary(per_sample, run_contract)
    task_slice_summary = _build_shadow_task_slice_summary(per_sample, run_contract)
    dataset_slice_summary = _build_shadow_dataset_slice_summary(per_sample, run_contract)
    replay_summary = _build_shadow_replay_summary(per_sample, run_contract)
    failure_summary = _build_shadow_failure_summary(per_sample, run_contract)
    runtime_trial_summary = _build_shadow_runtime_summary(per_sample, run_contract)
    authority_summary = _build_shadow_authority_summary(per_sample, run_contract)
    runtime_exec_summary = _build_shadow_runtime_exec_summary(per_sample, run_contract)
    runtime_evidence_summary = _build_shadow_runtime_evidence_summary(per_sample, run_contract)
    pattern_summary = _build_shadow_runtime_pattern_summary(per_sample, run_contract)
    influence_summary = _build_shadow_influence_summary(per_sample, run_contract)
    signal_summary = _build_signal_extraction_summary(per_sample, run_contract)
    ranking_exp_summary = _build_evidence_aware_ranking_summary(per_sample, run_contract)
    ea_selection_summary = _build_evidence_aware_selection_summary(per_sample, run_contract)

    report = {
        "aggregate": agg.to_dict(),
        "shadow_comparison_summary": shadow_summary,
        "shadow_observation_summary": lift_summary,
        "shadow_counterfactual_summary": counterfactual_summary,
        "shadow_difference_summary": diff_summary,
        "shadow_diagnostic_summary": diag_summary,
        "shadow_runtime_readiness_summary": readiness_summary,
        "shadow_provenance_summary": provenance_summary,
        "shadow_cross_artifact_summary": cross_artifact_summary,
        "shadow_selector_summary": selector_summary,
        "shadow_disagreement_summary": disagreement_summary,
        "shadow_observation_coverage_summary": coverage_summary,
        "shadow_registry_audit_summary": registry_audit_summary,
        "shadow_contract_audit_summary": contract_audit_summary,
        "shadow_offline_validation_summary": offline_val_summary,
        "shadow_observation_surface_summary": surface_summary,
        "shadow_observation_reference_summary": ref_summary,
        "shadow_offline_evaluation_summary": offline_eval_summary,
        "shadow_task_slice_summary": task_slice_summary,
        "shadow_dataset_slice_summary": dataset_slice_summary,
        "shadow_replay_summary": replay_summary,
        "shadow_failure_summary": failure_summary,
        "shadow_runtime_summary": runtime_trial_summary,
        "shadow_authority_summary": authority_summary,
        "shadow_runtime_execution_summary": runtime_exec_summary,
        "shadow_runtime_evidence_summary": runtime_evidence_summary,
        "shadow_runtime_pattern_summary": pattern_summary,
        "shadow_influence_summary": influence_summary,
        "signal_extraction_summary": signal_summary,
        "evidence_aware_ranking_summary": ranking_exp_summary,
        "evidence_aware_selection_summary": ea_selection_summary,
        "by_task_type": by_type,
        "coverage_info": coverage_info,
        "per_sample": per_sample,
    }
    if run_contract is not None:
        report["system_lineage"] = run_contract.system_lineage
        report["data_profile"] = run_contract.data_profile
        report["model_profile"] = run_contract.model_profile
        report["metric_scope"] = run_contract.metric_scope
        report["mainline_eligible"] = run_contract.mainline_eligible
        report["candidate_pool_enabled"] = run_contract.candidate_pool_enabled
        report["decision_core_mode"] = run_contract.decision_core_mode
        report["retrieval_mode"] = run_contract.retrieval_mode
        report["l2_authority"] = run_contract.l2_authority
        report["run_contract"] = run_contract.to_report_dict()
    if reranker_diagnostics is not None:
        report["reranker_diagnostics"] = reranker_diagnostics
    if repair_diagnostics is not None:
        report["repair_diagnostics"] = repair_diagnostics
    return report
