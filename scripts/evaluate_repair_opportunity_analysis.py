#!/usr/bin/env python3
"""Evaluation-only repair opportunity attribution for retrieval-centered planning.

This phase asks whether useful local repairs are predictable from existing
candidate traces. It does not train, load checkpoints, mutate checkpoints,
generate new candidates, or change retrieval/model architecture.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import random
import re
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Sequence


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from gis_recommend.config.transformer_config import OUTPUT_DIR  # noqa: E402


SCHEMA_VERSION = "gis_recommend.v5_final.repair_opportunity_analysis.v1"
FORBIDDEN_PATTERNS = [
    r"strict\s*=\s*False",
    r"weights_only\s*=\s*False",
    r"learned[_ -]?gamma",
    r"gated[_ -]?write",
    r"learned[_ -]?gating",
    r"graph[_ -]?loss",
    r"entropy[_ -]?regular",
    r"alpha[_ -]?anneal",
    r"\.backward\(",
    r"optimizer\.step\(",
    r"torch\.optim",
]


SIGNAL_COLUMNS = [
    "retrieval_top1_top2_gap",
    "retrieval_topk_entropy",
    "retrieval_score_std",
    "retrieval_candidate_set_disagreement",
    "retrieval_candidate_lcs_disagreement",
    "retrieval_unique_sequence_rate",
    "retrieval_density",
    "identity_invalid_transition_rate",
    "identity_io_validity",
    "modified_invalid_candidate_rate",
    "io_validity_margin",
    "bridge_candidate_available",
    "bridge_repair_success",
    "predicted_set_missing_rate",
    "retrieved_set_reference_deficit",
    "set_predictor_agreement",
    "operator_coverage_deficit",
    "missing_critical_operator_count",
    "length_abs_error",
    "length_ratio_error",
    "identity_repetition_rate",
    "identity_redundancy_rate",
    "structural_divergence_from_retrieval_neighborhood",
    "retrieval_length_std",
    "branching_proxy_repetition",
    "best_repair_edit_distance",
    "best_repair_lcs_retention",
]


def build_opportunity_rows(samples: Sequence[dict], *, transition_matrix: Optional[dict] = None) -> list[dict]:
    """Build one diagnostic signal row per sample."""

    return [_build_opportunity_row(sample, transition_matrix=transition_matrix or {}) for sample in samples]


def analyze_success_correlations(
    rows: Sequence[dict],
    *,
    bootstrap_iterations: int = 300,
    seed: int = 42,
) -> dict:
    """Measure signal association with oracle repair success."""

    target = [float(row.get("repair_success", 0.0) or 0.0) for row in rows]
    harmful = [float(row.get("repair_harmful", 0.0) or 0.0) for row in rows]
    signals = {}
    weak = []
    unstable = []
    spurious = []
    for name in SIGNAL_COLUMNS:
        values = [float(row.get(name, 0.0) or 0.0) for row in rows]
        corr = _pearson(values, target)
        harmful_corr = _pearson(values, harmful)
        interval = _bootstrap_correlation_interval(values, target, iterations=bootstrap_iterations, seed=seed + len(signals))
        nonzero_count = sum(1 for value in values if abs(value) > 1e-12)
        triggered_success = sum(1 for row, value in zip(rows, values) if abs(value) > 1e-12 and row.get("repair_success"))
        signal = {
            "correlation_with_repair_success": round(corr, 8),
            "correlation_with_harmful_repair": round(harmful_corr, 8),
            "bootstrap_interval": interval,
            "nonzero_count": nonzero_count,
            "nonzero_rate": _rate(nonzero_count, len(rows)),
            "positive_success_count_when_nonzero": triggered_success,
            "interpretation": _signal_interpretation(corr, interval, nonzero_count, len(rows)),
        }
        signals[name] = signal
        if abs(corr) < 0.10:
            weak.append(name)
        if interval["lower"] <= 0.0 <= interval["upper"]:
            unstable.append(name)
        if nonzero_count < max(5, int(0.05 * max(len(rows), 1))):
            spurious.append(name)
    return {
        "schema_version": f"{SCHEMA_VERSION}.correlations",
        "target": "repair_success",
        "sample_count": len(rows),
        "bootstrap_iterations": int(bootstrap_iterations),
        "signals": signals,
        "statistically_weak_signals": weak,
        "unstable_correlations": unstable,
        "likely_spurious_associations": spurious,
        "limitations": _limitations(len(rows), weak, unstable, spurious),
    }


def evaluate_opportunity_indicators(rows: Sequence[dict]) -> dict:
    """Evaluate hand-written opportunity indicators without training."""

    indicators = {
        "high_retrieval_ambiguity": lambda row: row["retrieval_top1_top2_gap"] <= 0.05
        or row["retrieval_topk_entropy"] >= 0.80,
        "set_deficit_or_length_anomaly": lambda row: row["predicted_set_missing_rate"] >= 0.25
        or row["retrieved_set_reference_deficit"] > 0.0
        or row["length_abs_error"] >= 1.0,
        "bridge_opportunity": lambda row: bool(row["bridge_candidate_available"])
        and (row["predicted_set_missing_rate"] > 0.0 or row["length_abs_error"] > 0.0),
        "low_set_agreement": lambda row: row["set_predictor_agreement"] < 0.50,
        "local_low_risk_repair_available": lambda row: row["best_repair_edit_distance"] <= 1.0
        and row["best_repair_lcs_retention"] >= 0.75,
        "combined_conservative": lambda row: (
            (row["predicted_set_missing_rate"] >= 0.25 or row["retrieved_set_reference_deficit"] > 0.0)
            and row["best_repair_edit_distance"] <= 1.0
            and row["identity_io_validity"] >= 1.0
        ),
    }
    report = {}
    for name, predicate in indicators.items():
        report[name] = _indicator_metrics(rows, predicate)
    return {
        "schema_version": f"{SCHEMA_VERSION}.opportunity_indicators",
        "sample_count": len(rows),
        "target": "oracle_repair_success",
        "indicators": report,
        "note": "Heuristic indicators are diagnostic only; no learned model or runtime gating is created.",
    }


def refine_failure_taxonomy(rows: Sequence[dict]) -> dict:
    """Produce a second-pass taxonomy separating opportunity and failure causes."""

    counts = Counter(row.get("failure_taxonomy_v2", "unknown") for row in rows)
    total = max(len(rows), 1)
    return {
        "schema_version": f"{SCHEMA_VERSION}.failure_taxonomy_v2",
        "sample_count": len(rows),
        "failure_counts": dict(sorted(counts.items())),
        "failure_rates": {key: round(value / total, 8) for key, value in sorted(counts.items())},
        "category_definitions": {
            "repair_opportunity_available": "Oracle local repair improves identity; selected scorer may still miss it.",
            "retrieval_already_optimal": "Neither repair nor retrieval-pool oracle improves identity.",
            "repair_candidate_quality_failure": "Retrieval-pool oracle can improve, but local repair candidate pool cannot.",
            "scorer_ranking_failure": "Useful local repair exists but selected candidate is not the best repair.",
            "structural_corruption": "Best local repair is worse and increases structural anomaly proxies.",
            "execution_corruption": "Best local repair weakens execution/transition validity proxies.",
            "ambiguity_driven_failure": "Failure coincides with high retrieval ambiguity and no useful repair.",
        },
        "rows": [
            {
                "local_index": row.get("local_index"),
                "source_test_index": row.get("source_test_index"),
                "task_type": row.get("task_type"),
                "failure_taxonomy_v2": row.get("failure_taxonomy_v2"),
                "repair_success": row.get("repair_success"),
                "repair_harmful": row.get("repair_harmful"),
                "best_repair_kind": row.get("best_repair_kind"),
                "oracle_repair_lcs_gain": row.get("oracle_repair_lcs_gain"),
            }
            for row in rows
        ],
    }


def analyze_repair_locality(rows: Sequence[dict]) -> dict:
    """Summarize which local edit types/distances are associated with success."""

    by_kind: dict[str, list[dict]] = defaultdict(list)
    by_distance: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        by_kind[str(row.get("best_repair_kind") or "none")].append(row)
        by_distance[str(int(row.get("best_repair_edit_distance", 0) or 0))].append(row)
    return {
        "schema_version": f"{SCHEMA_VERSION}.locality",
        "sample_count": len(rows),
        "by_edit_type": {key: _locality_group_summary(group) for key, group in sorted(by_kind.items())},
        "by_edit_distance": {key: _locality_group_summary(group) for key, group in sorted(by_distance.items(), key=lambda item: int(item[0]))},
        "local_vs_global": {
            "local_edit_distance_le_1": _locality_group_summary([row for row in rows if row.get("best_repair_edit_distance", 0.0) <= 1.0]),
            "larger_edit_distance_gt_1": _locality_group_summary([row for row in rows if row.get("best_repair_edit_distance", 0.0) > 1.0]),
        },
    }


def evaluate_repair_opportunity_analysis(
    *,
    candidate_traces_path: Path,
    output_dir: Path,
    transition_matrix_path: Optional[Path] = None,
    bootstrap_iterations: int = 300,
    seed: int = 42,
    dry_run: bool = False,
) -> dict:
    """Run the full evaluation-only opportunity attribution phase."""

    traces = _load_json(candidate_traces_path)
    samples = traces.get("samples", [])
    if not isinstance(samples, list):
        raise ValueError(f"Invalid candidate trace payload: {candidate_traces_path}")
    transition_matrix = _load_json(transition_matrix_path) if transition_matrix_path and transition_matrix_path.exists() else {}
    output_dir.mkdir(parents=True, exist_ok=True)
    created_at = _now()
    if dry_run:
        report = {
            "schema_version": SCHEMA_VERSION,
            "created_at": created_at,
            "dry_run": True,
            "candidate_traces": str(candidate_traces_path),
            "sample_count": len(samples),
            "output_dir": str(output_dir),
        }
        _write_json(output_dir / "dry_run_summary.json", report)
        return report

    rows = build_opportunity_rows(samples, transition_matrix=transition_matrix)
    correlations = analyze_success_correlations(rows, bootstrap_iterations=bootstrap_iterations, seed=seed)
    indicators = evaluate_opportunity_indicators(rows)
    taxonomy = refine_failure_taxonomy(rows)
    locality = analyze_repair_locality(rows)
    report = {
        "schema_version": SCHEMA_VERSION,
        "created_at": created_at,
        "dry_run": False,
        "candidate_traces": str(candidate_traces_path),
        "transition_matrix": str(transition_matrix_path) if transition_matrix_path else None,
        "sample_count": len(rows),
        "summary": _opportunity_summary(rows),
        "retrieval_ambiguity_analysis": _signal_family_summary(rows, [
            "retrieval_top1_top2_gap",
            "retrieval_topk_entropy",
            "retrieval_candidate_set_disagreement",
            "retrieval_candidate_lcs_disagreement",
            "retrieval_density",
        ]),
        "io_inconsistency_analysis": _signal_family_summary(rows, [
            "identity_invalid_transition_rate",
            "identity_io_validity",
            "modified_invalid_candidate_rate",
            "io_validity_margin",
            "bridge_candidate_available",
        ]),
        "set_mismatch_analysis": _signal_family_summary(rows, [
            "predicted_set_missing_rate",
            "retrieved_set_reference_deficit",
            "set_predictor_agreement",
            "operator_coverage_deficit",
            "missing_critical_operator_count",
        ]),
        "structural_anomaly_analysis": _signal_family_summary(rows, [
            "length_abs_error",
            "length_ratio_error",
            "identity_repetition_rate",
            "identity_redundancy_rate",
            "structural_divergence_from_retrieval_neighborhood",
            "retrieval_length_std",
        ]),
        "opportunity_indicators": indicators["indicators"],
        "statistical_cautions": {
            "statistically_weak_signals": correlations["statistically_weak_signals"],
            "unstable_correlations": correlations["unstable_correlations"],
            "likely_spurious_associations": correlations["likely_spurious_associations"],
            "sample_size_limitations": correlations["limitations"],
        },
        "runtime_contract": {
            "evaluation_only": True,
            "training_run": False,
            "checkpoint_loaded": False,
            "checkpoint_mutated": False,
            "architecture_modified": False,
            "new_loss_added": False,
            "gradient_usage": False,
            "candidate_generation_run": False,
            "retrieval_redesign": False,
            "generation_redesign": False,
            "graph_learning": False,
        },
    }
    scan = forbidden_pattern_scan(
        [
            Path(__file__).relative_to(ROOT),
            Path("tests") / "test_repair_opportunity_analysis.py",
        ]
    )

    _write_json(output_dir / "repair_opportunity_analysis.json", report)
    _write_json(output_dir / "repair_success_correlations.json", correlations)
    _write_json(output_dir / "repair_failure_taxonomy_v2.json", taxonomy)
    _write_json(output_dir / "repair_locality_analysis.json", locality)
    _write_json(output_dir / "forbidden_pattern_scan_repair_opportunity.json", scan)
    _write_signal_table(output_dir / "opportunity_signal_table.csv", rows)
    _write_markdown(output_dir / "opportunity_prediction_summary.md", report, correlations, indicators, taxonomy, locality)
    return report


def forbidden_pattern_scan(files: Sequence[Path]) -> dict:
    matches = []
    for file_path in files:
        path = ROOT / file_path
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8")
        for pattern in FORBIDDEN_PATTERNS:
            for match in re.finditer(pattern, text, flags=re.IGNORECASE):
                matches.append(
                    {
                        "file": str(file_path),
                        "line": text.count("\n", 0, match.start()) + 1,
                        "pattern": pattern,
                        "match": match.group(0),
                    }
                )
    return {
        "schema_version": "gis_recommend.v5_final.forbidden_pattern_scan.v1",
        "files": [str(path) for path in files],
        "patterns": list(FORBIDDEN_PATTERNS),
        "match_count": len(matches),
        "matches": matches,
        "result": "pass" if not matches else "fail",
    }


def _build_opportunity_row(sample: dict, *, transition_matrix: dict) -> dict:
    candidates = _candidate_pool(sample)
    retrieval_pool = _retrieval_pool(sample)
    identity = _identity_candidate(sample, candidates, retrieval_pool)
    modified = [row for row in candidates if _is_modified(row)]
    best_repair = _best_modified_by_lcs(modified) or identity
    selected = ((sample.get("oracle") or {}).get("selected_candidate") or candidates[0]) if candidates else identity
    reference_tokens = _int_list(sample.get("reference_tokens") or [])
    identity_tokens = _int_list(identity.get("tokens") or sample.get("identity_tokens") or [])
    best_repair_tokens = _int_list(best_repair.get("tokens") or [])
    identity_metrics = _metrics(identity, reference_tokens)
    best_metrics = _metrics(best_repair, reference_tokens)
    selected_metrics = _metrics(selected, reference_tokens)
    oracle = sample.get("oracle") or {}
    retrieval_oracle_gain = _metric_delta(
        (oracle.get("best_retrieval_pool_metrics") or {}),
        (oracle.get("identity_metrics") or identity_metrics),
    )
    repair_gain = _metric_delta(best_metrics, identity_metrics)

    retrieval_signals = _retrieval_signals(retrieval_pool, identity_tokens)
    set_signals = _set_signals(sample, identity, identity_tokens, reference_tokens)
    structure_signals = _structure_signals(identity_tokens, reference_tokens, retrieval_pool)
    io_signals = _io_signals(identity, modified, identity_tokens, transition_matrix)
    locality = _repair_locality(best_repair, best_repair_tokens, identity_tokens)
    row = {
        "local_index": sample.get("local_index"),
        "source_test_index": sample.get("source_test_index"),
        "task_type": sample.get("task_type"),
        "repair_success": 1 if repair_gain["lcs_ratio"] > 0.0 else 0,
        "repair_harmful": 1 if repair_gain["lcs_ratio"] < 0.0 else 0,
        "retrieval_sufficient": 1 if repair_gain["lcs_ratio"] <= 0.0 and retrieval_oracle_gain["lcs_ratio"] <= 0.0 else 0,
        "oracle_repair_lcs_gain": repair_gain["lcs_ratio"],
        "oracle_repair_set_f1_gain": repair_gain["set_f1"],
        "oracle_repair_token_accuracy_gain": repair_gain["token_accuracy"],
        "retrieval_oracle_lcs_gain": round(float(retrieval_oracle_gain.get("lcs_ratio", 0.0) or 0.0), 8),
        "selected_lcs_delta_vs_identity": round(selected_metrics["lcs_ratio"] - identity_metrics["lcs_ratio"], 8),
        "best_repair_kind": _candidate_kind(best_repair),
        "best_repair_io_validity": _float(best_repair.get("io_validity", (best_repair.get("execution_features") or {}).get("io_validity", 1.0)), 1.0),
        "selected_candidate_kind": _candidate_kind(selected),
        **retrieval_signals,
        **io_signals,
        **set_signals,
        **structure_signals,
        **locality,
    }
    row["failure_taxonomy_v2"] = _classify_failure_v2(row)
    return row


def _retrieval_signals(retrieval_pool: Sequence[dict], identity_tokens: Sequence[int]) -> dict:
    scores = [_score(row) for row in retrieval_pool]
    top1 = scores[0] if scores else 0.0
    top2 = scores[1] if len(scores) > 1 else 0.0
    sequences = [_int_list(row.get("tokens", [])) for row in retrieval_pool]
    return {
        "retrieval_top1_score": round(top1, 8),
        "retrieval_top2_score": round(top2, 8),
        "retrieval_top1_top2_gap": round(top1 - top2, 8),
        "retrieval_topk_entropy": _score_entropy(scores),
        "retrieval_score_std": _std(scores),
        "retrieval_candidate_set_disagreement": _mean_pairwise_set_distance(sequences),
        "retrieval_candidate_lcs_disagreement": _mean_pairwise_lcs_distance(sequences),
        "retrieval_unique_sequence_rate": _rate(len({tuple(seq) for seq in sequences}), len(sequences)),
        "retrieval_density": round(_mean(scores), 8),
        "structural_divergence_from_retrieval_neighborhood": _mean([_set_distance(identity_tokens, seq) for seq in sequences[1:]]),
        "retrieval_length_std": _std([len(seq) for seq in sequences]),
    }


def _io_signals(identity: dict, modified: Sequence[dict], identity_tokens: Sequence[int], transition_matrix: dict) -> dict:
    identity_io = _float(identity.get("io_validity", (identity.get("execution_features") or {}).get("io_validity", 1.0)), 1.0)
    modified_io = [_float(row.get("io_validity", (row.get("execution_features") or {}).get("io_validity", 1.0)), 1.0) for row in modified]
    bridge_available = any(_candidate_kind(row) == "bridge_insertion" for row in modified)
    return {
        "identity_io_validity": round(identity_io, 8),
        "modified_invalid_candidate_rate": round(_mean(1.0 if value < 1.0 else 0.0 for value in modified_io), 8),
        "io_validity_margin": round(identity_io - _mean(modified_io), 8),
        "identity_invalid_transition_rate": _invalid_transition_rate(identity_tokens, transition_matrix),
        "bridge_candidate_available": 1.0 if bridge_available else 0.0,
    }


def _set_signals(sample: dict, identity: dict, identity_tokens: Sequence[int], reference_tokens: Sequence[int]) -> dict:
    predicted_tokens = _predicted_tokens(sample)
    identity_set = set(identity_tokens)
    reference_set = set(reference_tokens)
    predicted_set = set(predicted_tokens)
    features = identity.get("execution_features") or {}
    set_filter = identity.get("set_filter") or {}
    set_agreement = _float(features.get("set_predictor_agreement", set_filter.get("set_predictor_agreement", 0.0)))
    coverage = _float(features.get("operator_coverage_consistency", set_filter.get("candidate_recall", set_agreement)))
    missing_predicted = predicted_set - identity_set
    missing_reference = reference_set - identity_set
    return {
        "predicted_set_size": len(predicted_set),
        "predicted_set_missing_rate": _rate(len(missing_predicted), len(predicted_set)),
        "retrieved_set_reference_deficit": _rate(len(missing_reference), len(reference_set)),
        "set_predictor_agreement": round(set_agreement, 8),
        "operator_coverage_deficit": round(1.0 - coverage, 8),
        "missing_critical_operator_count": len(missing_reference),
    }


def _structure_signals(identity_tokens: Sequence[int], reference_tokens: Sequence[int], retrieval_pool: Sequence[dict]) -> dict:
    identity_len = len(identity_tokens)
    reference_len = len(reference_tokens)
    length_abs_error = abs(identity_len - reference_len)
    return {
        "length_abs_error": float(length_abs_error),
        "length_ratio_error": round(float(length_abs_error) / max(reference_len, 1), 8),
        "identity_repetition_rate": _repetition_rate(identity_tokens),
        "identity_redundancy_rate": _redundancy_rate(identity_tokens),
        "branching_proxy_repetition": _repetition_rate(identity_tokens),
        "retrieval_pool_size": len(retrieval_pool),
    }


def _repair_locality(best_repair: dict, best_repair_tokens: Sequence[int], identity_tokens: Sequence[int]) -> dict:
    attribution = best_repair.get("repair_attribution") or {}
    edit_distance = _float(
        best_repair.get(
            "edit_distance_from_retrieval",
            best_repair.get("edit_distance_from_identity", attribution.get("edit_distance", 0.0)),
        )
    )
    return {
        "best_repair_edit_distance": round(edit_distance, 8),
        "best_repair_lcs_retention": round(_float(attribution.get("lcs_retention"), _lcs_ratio(best_repair_tokens, identity_tokens)), 8),
        "bridge_repair_success": 1.0 if _candidate_kind(best_repair) == "bridge_insertion" else 0.0,
    }


def _classify_failure_v2(row: dict) -> str:
    if row["best_repair_io_validity"] < row["identity_io_validity"] or row["identity_invalid_transition_rate"] > 0.0:
        return "execution_corruption"
    if row["repair_harmful"] and (row["length_abs_error"] > 0.0 or row["identity_repetition_rate"] > 0.0):
        return "structural_corruption"
    if row["repair_success"] and row["selected_candidate_kind"] != row["best_repair_kind"]:
        return "scorer_ranking_failure"
    if row["repair_success"]:
        return "repair_opportunity_available"
    if row["retrieval_sufficient"]:
        return "retrieval_already_optimal"
    if row["retrieval_top1_top2_gap"] <= 0.05 or row["retrieval_topk_entropy"] >= 0.80:
        return "ambiguity_driven_failure"
    return "repair_candidate_quality_failure"


def _opportunity_summary(rows: Sequence[dict]) -> dict:
    return {
        "sample_count": len(rows),
        "repair_success_rate": round(_mean(row["repair_success"] for row in rows), 8),
        "repair_harmful_rate": round(_mean(row["repair_harmful"] for row in rows), 8),
        "retrieval_sufficient_rate": round(_mean(row["retrieval_sufficient"] for row in rows), 8),
        "mean_oracle_repair_lcs_gain": round(_mean(row["oracle_repair_lcs_gain"] for row in rows), 8),
        "mean_oracle_repair_set_f1_gain": round(_mean(row["oracle_repair_set_f1_gain"] for row in rows), 8),
        "mean_oracle_repair_token_accuracy_gain": round(_mean(row["oracle_repair_token_accuracy_gain"] for row in rows), 8),
    }


def _signal_family_summary(rows: Sequence[dict], signals: Sequence[str]) -> dict:
    return {
        signal: {
            "mean": round(_mean(row.get(signal, 0.0) for row in rows), 8),
            "success_mean": round(_mean(row.get(signal, 0.0) for row in rows if row.get("repair_success")), 8),
            "harmful_mean": round(_mean(row.get(signal, 0.0) for row in rows if row.get("repair_harmful")), 8),
            "retrieval_sufficient_mean": round(_mean(row.get(signal, 0.0) for row in rows if row.get("retrieval_sufficient")), 8),
        }
        for signal in signals
    }


def _indicator_metrics(rows: Sequence[dict], predicate) -> dict:
    predicted = [bool(predicate(row)) for row in rows]
    actual = [bool(row.get("repair_success")) for row in rows]
    harmful = [bool(row.get("repair_harmful")) for row in rows]
    tp = sum(1 for pred, act in zip(predicted, actual) if pred and act)
    fp = sum(1 for pred, act in zip(predicted, actual) if pred and not act)
    tn = sum(1 for pred, act in zip(predicted, actual) if not pred and not act)
    fn = sum(1 for pred, act in zip(predicted, actual) if not pred and act)
    triggered = max(tp + fp, 1)
    return {
        "trigger_count": tp + fp,
        "trigger_rate": _rate(tp + fp, len(rows)),
        "precision": _rate(tp, tp + fp),
        "recall": _rate(tp, tp + fn),
        "false_positive_rate": _rate(fp, fp + tn),
        "corruption_rate_when_triggered": _rate(sum(1 for pred, harm in zip(predicted, harmful) if pred and harm), triggered),
        "true_positive_count": tp,
        "false_positive_count": fp,
        "false_negative_count": fn,
        "true_negative_count": tn,
    }


def _locality_group_summary(group: Sequence[dict]) -> dict:
    return {
        "sample_count": len(group),
        "repair_success_rate": round(_mean(row.get("repair_success", 0.0) for row in group), 8),
        "repair_harmful_rate": round(_mean(row.get("repair_harmful", 0.0) for row in group), 8),
        "mean_lcs_gain": round(_mean(row.get("oracle_repair_lcs_gain", 0.0) for row in group), 8),
        "mean_set_f1_gain": round(_mean(row.get("oracle_repair_set_f1_gain", 0.0) for row in group), 8),
        "mean_token_accuracy_gain": round(_mean(row.get("oracle_repair_token_accuracy_gain", 0.0) for row in group), 8),
    }


def _bootstrap_correlation_interval(values: Sequence[float], target: Sequence[float], *, iterations: int, seed: int) -> dict:
    if not values or len(values) != len(target) or iterations <= 0:
        return {"lower": 0.0, "median": 0.0, "upper": 0.0}
    rng = random.Random(int(seed))
    correlations = []
    size = len(values)
    for _ in range(int(iterations)):
        indices = [rng.randrange(size) for _ in range(size)]
        correlations.append(_pearson([values[i] for i in indices], [target[i] for i in indices]))
    return _interval(correlations)


def _signal_interpretation(corr: float, interval: dict, nonzero_count: int, sample_count: int) -> str:
    if nonzero_count < max(5, int(0.05 * max(sample_count, 1))):
        return "likely_spurious_low_support"
    if interval["lower"] <= 0.0 <= interval["upper"]:
        return "unstable_ci_crosses_zero"
    if abs(corr) < 0.10:
        return "statistically_weak"
    return "directional_signal_for_followup"


def _limitations(sample_count: int, weak: Sequence[str], unstable: Sequence[str], spurious: Sequence[str]) -> list[str]:
    notes = [
        "All signals are observational correlations over persisted candidate traces; no causal claim is made.",
        "Set Predictor fields may be fallback task-type frequency priors when a trained checkpoint is absent.",
    ]
    if sample_count < 500:
        notes.append(f"Sample size is modest ({sample_count}); bootstrap intervals should be treated as screening evidence only.")
    if weak:
        notes.append(f"{len(weak)} signals have absolute correlation below 0.10.")
    if unstable:
        notes.append(f"{len(unstable)} signals have bootstrap intervals crossing zero.")
    if spurious:
        notes.append(f"{len(spurious)} signals have low nonzero support and may be spurious.")
    return notes


def _candidate_pool(sample: dict) -> list[dict]:
    rows = sample.get("repair_candidate_pool") or sample.get("top_repair_candidates") or []
    return [row for row in rows if isinstance(row, dict)]


def _retrieval_pool(sample: dict) -> list[dict]:
    rows = sample.get("retrieval_pool_top") or []
    return [row for row in rows if isinstance(row, dict)]


def _identity_candidate(sample: dict, candidates: Sequence[dict], retrieval_pool: Sequence[dict]) -> dict:
    identity_tokens = _int_list(sample.get("identity_tokens") or [])
    for row in candidates:
        if _candidate_kind(row) == "identity":
            return row
    for row in retrieval_pool:
        if _int_list(row.get("tokens", [])) == identity_tokens:
            return row
    return (list(candidates) or list(retrieval_pool) or [{"tokens": identity_tokens, "candidate_kind": "identity"}])[0]


def _best_modified_by_lcs(candidates: Sequence[dict]) -> Optional[dict]:
    modified = [row for row in candidates if _is_modified(row)]
    if not modified:
        return None
    return max(
        modified,
        key=lambda row: (
            _metrics(row, [])["lcs_ratio"],
            _metrics(row, [])["token_accuracy"],
            _metrics(row, [])["set_f1"],
            -_float(row.get("edit_distance_from_retrieval", row.get("edit_distance_from_source", 0.0))),
        ),
    )


def _metrics(candidate: dict, reference_tokens: Sequence[int]) -> dict:
    attribution = candidate.get("repair_attribution") or {}
    metrics = attribution.get("candidate_metrics") or candidate.get("metrics") or {}
    if metrics:
        return {
            "lcs_ratio": _float(metrics.get("lcs_ratio")),
            "set_f1": _float(metrics.get("set_f1")),
            "token_accuracy": _float(metrics.get("token_accuracy")),
        }
    return _simple_metrics(candidate.get("tokens", []), reference_tokens)


def _metric_delta(candidate_metrics: dict, identity_metrics: dict) -> dict:
    return {
        "lcs_ratio": round(_float(candidate_metrics.get("lcs_ratio")) - _float(identity_metrics.get("lcs_ratio")), 8),
        "set_f1": round(_float(candidate_metrics.get("set_f1")) - _float(identity_metrics.get("set_f1")), 8),
        "token_accuracy": round(_float(candidate_metrics.get("token_accuracy")) - _float(identity_metrics.get("token_accuracy")), 8),
    }


def _simple_metrics(tokens: Sequence[int], reference_tokens: Sequence[int]) -> dict:
    pred = _int_list(tokens)
    ref = _int_list(reference_tokens)
    return {
        "lcs_ratio": _lcs_ratio(pred, ref),
        "set_f1": _set_f1(pred, ref),
        "token_accuracy": _token_accuracy(pred, ref),
    }


def _score(candidate: dict) -> float:
    for key in ("retrieval_score", "score", "fusion_score", "hybrid_score", "execution_aware_score"):
        if candidate.get(key) is not None:
            return _float(candidate.get(key))
    return 0.0


def _candidate_kind(candidate: dict) -> str:
    return str(candidate.get("repair_operation") or candidate.get("candidate_kind") or candidate.get("repair_kind") or "unknown")


def _is_modified(candidate: dict) -> bool:
    kind = _candidate_kind(candidate)
    edit_distance = _float(candidate.get("edit_distance_from_retrieval", candidate.get("edit_distance_from_source", 0.0)))
    return kind not in {"identity", "unknown", "empty"} or edit_distance > 0.0


def _predicted_tokens(sample: dict) -> list[int]:
    rows = (sample.get("set_prediction") or {}).get("top_tokens") or []
    return [int(row.get("token")) for row in rows if isinstance(row, dict) and row.get("token") is not None]


def _invalid_transition_rate(tokens: Sequence[int], transition_matrix: dict) -> float:
    if not transition_matrix or len(tokens) < 2:
        return 0.0
    allowed = transition_matrix.get("allowed_next") or transition_matrix.get("transitions") or transition_matrix
    invalid = 0
    total = 0
    for left, right in zip(tokens, tokens[1:]):
        options = allowed.get(str(left), allowed.get(int(left), [])) if isinstance(allowed, dict) else []
        if isinstance(options, dict):
            options = options.keys()
        option_set = {int(value) for value in options if _is_int_like(value)}
        if option_set and int(right) not in option_set:
            invalid += 1
        total += 1
    return _rate(invalid, total)


def _score_entropy(scores: Sequence[float]) -> float:
    positive = [max(float(score), 0.0) for score in scores]
    total = sum(positive)
    if total <= 0.0:
        return 0.0
    probs = [value / total for value in positive if value > 0.0]
    entropy = -sum(prob * math.log(prob, 2) for prob in probs)
    max_entropy = math.log(max(len(probs), 1), 2)
    return round(entropy / max_entropy, 8) if max_entropy > 0.0 else 0.0


def _mean_pairwise_set_distance(sequences: Sequence[Sequence[int]]) -> float:
    return round(_mean(_set_distance(a, b) for i, a in enumerate(sequences) for b in sequences[i + 1 :]), 8)


def _mean_pairwise_lcs_distance(sequences: Sequence[Sequence[int]]) -> float:
    return round(_mean(1.0 - _lcs_ratio(a, b) for i, a in enumerate(sequences) for b in sequences[i + 1 :]), 8)


def _set_distance(a: Sequence[int], b: Sequence[int]) -> float:
    left = set(_int_list(a))
    right = set(_int_list(b))
    if not left and not right:
        return 0.0
    return round(1.0 - (len(left & right) / max(len(left | right), 1)), 8)


def _lcs_ratio(a: Sequence[int], b: Sequence[int]) -> float:
    left = _int_list(a)
    right = _int_list(b)
    if not left or not right:
        return 0.0
    dp = [0] * (len(right) + 1)
    for token in left:
        prev = 0
        for j, other in enumerate(right, start=1):
            old = dp[j]
            if token == other:
                dp[j] = prev + 1
            else:
                dp[j] = max(dp[j], dp[j - 1])
            prev = old
    return round(dp[-1] / max(len(right), 1), 8)


def _set_f1(a: Sequence[int], b: Sequence[int]) -> float:
    left = set(_int_list(a))
    right = set(_int_list(b))
    if not left and not right:
        return 1.0
    if not left or not right:
        return 0.0
    precision = len(left & right) / len(left)
    recall = len(left & right) / len(right)
    if precision + recall == 0.0:
        return 0.0
    return round(2 * precision * recall / (precision + recall), 8)


def _token_accuracy(a: Sequence[int], b: Sequence[int]) -> float:
    left = _int_list(a)
    right = _int_list(b)
    if not right:
        return 0.0
    return round(sum(1 for x, y in zip(left, right) if x == y) / len(right), 8)


def _repetition_rate(tokens: Sequence[int]) -> float:
    rows = _int_list(tokens)
    if not rows:
        return 0.0
    counts = Counter(rows)
    repeated = sum(count - 1 for count in counts.values() if count > 1)
    return round(repeated / len(rows), 8)


def _redundancy_rate(tokens: Sequence[int]) -> float:
    rows = _int_list(tokens)
    if not rows:
        return 0.0
    return round(1.0 - (len(set(rows)) / len(rows)), 8)


def _pearson(values: Sequence[float], target: Sequence[float]) -> float:
    if len(values) != len(target) or not values:
        return 0.0
    mean_x = _mean(values)
    mean_y = _mean(target)
    numerator = sum((float(x) - mean_x) * (float(y) - mean_y) for x, y in zip(values, target))
    denom_x = math.sqrt(sum((float(x) - mean_x) ** 2 for x in values))
    denom_y = math.sqrt(sum((float(y) - mean_y) ** 2 for y in target))
    if denom_x <= 0.0 or denom_y <= 0.0:
        return 0.0
    return numerator / (denom_x * denom_y)


def _interval(values: Sequence[float]) -> dict:
    rows = sorted(float(value) for value in values)
    if not rows:
        return {"lower": 0.0, "median": 0.0, "upper": 0.0}
    return {
        "lower": round(_quantile(rows, 0.025), 8),
        "median": round(_quantile(rows, 0.50), 8),
        "upper": round(_quantile(rows, 0.975), 8),
    }


def _quantile(rows: Sequence[float], q: float) -> float:
    if not rows:
        return 0.0
    pos = (len(rows) - 1) * float(q)
    lower = int(pos)
    upper = min(lower + 1, len(rows) - 1)
    weight = pos - lower
    return rows[lower] * (1.0 - weight) + rows[upper] * weight


def _std(values: Sequence[float]) -> float:
    rows = [float(value) for value in values]
    if not rows:
        return 0.0
    mean = _mean(rows)
    return round(math.sqrt(sum((value - mean) ** 2 for value in rows) / len(rows)), 8)


def _rate(numerator: int, denominator: int) -> float:
    return round(float(numerator) / max(int(denominator), 1), 8)


def _mean(values) -> float:
    rows = [float(value) for value in values]
    return sum(rows) / max(len(rows), 1)


def _float(value, default: float = 0.0) -> float:
    try:
        if value is None:
            return float(default)
        return float(value)
    except (TypeError, ValueError):
        return float(default)


def _int_list(values: Sequence[int]) -> list[int]:
    return [int(value) for value in values or [] if _is_int_like(value)]


def _is_int_like(value) -> bool:
    try:
        int(value)
        return True
    except (TypeError, ValueError):
        return False


def _load_json(path: Optional[Path]) -> dict:
    if path is None:
        return {}
    with Path(path).open("r", encoding="utf-8") as f:
        payload = json.load(f)
    if not isinstance(payload, dict):
        raise ValueError(f"Expected JSON object: {path}")
    return payload


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _write_signal_table(path: Path, rows: Sequence[dict]) -> None:
    fields = [
        "local_index",
        "source_test_index",
        "task_type",
        "repair_success",
        "repair_harmful",
        "retrieval_sufficient",
        "oracle_repair_lcs_gain",
        "best_repair_kind",
        "failure_taxonomy_v2",
        *SIGNAL_COLUMNS,
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field) for field in fields})


def _write_markdown(path: Path, report: dict, correlations: dict, indicators: dict, taxonomy: dict, locality: dict) -> None:
    lines = [
        "# Repair Opportunity Attribution",
        "",
        "Evaluation-only diagnostics over existing retrieval/local-repair candidate traces. No training, checkpoint loading, candidate generation, architecture changes, graph learning, retrieval redesign, or generation redesign are performed.",
        "",
        f"Samples: `{report.get('sample_count')}`",
        "",
        "## Summary",
        "",
        "```json",
        json.dumps(report.get("summary", {}), ensure_ascii=False, indent=2),
        "```",
        "",
        "## Heuristic Opportunity Indicators",
        "",
        "| Indicator | Trigger Rate | Precision | Recall | FPR | Corruption When Triggered |",
        "| --- | ---: | ---: | ---: | ---: | ---: |",
    ]
    for name, row in indicators.get("indicators", {}).items():
        lines.append(
            f"| `{name}` | {row.get('trigger_rate')} | {row.get('precision')} | {row.get('recall')} | "
            f"{row.get('false_positive_rate')} | {row.get('corruption_rate_when_triggered')} |"
        )
    lines.extend(
        [
            "",
            "## Failure Taxonomy V2",
            "",
            "```json",
            json.dumps(
                {
                    "failure_counts": taxonomy.get("failure_counts", {}),
                    "failure_rates": taxonomy.get("failure_rates", {}),
                },
                ensure_ascii=False,
                indent=2,
            ),
            "```",
            "",
            "## Statistical Cautions",
            "",
            "```json",
            json.dumps(
                {
                    "statistically_weak_signals": correlations.get("statistically_weak_signals", []),
                    "unstable_correlations": correlations.get("unstable_correlations", []),
                    "likely_spurious_associations": correlations.get("likely_spurious_associations", []),
                    "limitations": correlations.get("limitations", []),
                },
                ensure_ascii=False,
                indent=2,
            ),
            "```",
            "",
            "## Locality",
            "",
            "```json",
            json.dumps(locality.get("by_edit_type", {}), ensure_ascii=False, indent=2),
            "```",
            "",
            "This report is scorer/opportunity diagnostics only. It is not evidence of generative planning capability, autonomous repair intelligence, or planner creativity.",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _build_parser() -> argparse.ArgumentParser:
    default_dir = OUTPUT_DIR / "v5_final_reports" / "repair_oracle_phase_heldout_200"
    fallback_dir = OUTPUT_DIR / "v5_final_reports" / "repair_oracle_phase"
    default_traces = default_dir / "repair_candidate_traces.json"
    if not default_traces.exists():
        default_traces = fallback_dir / "repair_candidate_traces.json"
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate-traces", type=Path, default=default_traces)
    parser.add_argument("--transition-matrix", type=Path, default=OUTPUT_DIR / "transition_allowed_next.json")
    parser.add_argument("--output-dir", type=Path, default=OUTPUT_DIR / "v5_final_reports" / "repair_opportunity_analysis")
    parser.add_argument("--bootstrap-iterations", type=int, default=300)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--dry-run", action="store_true")
    return parser


def main(argv: Optional[list[str]] = None) -> dict:
    args = _build_parser().parse_args(argv)
    report = evaluate_repair_opportunity_analysis(
        candidate_traces_path=args.candidate_traces,
        output_dir=args.output_dir,
        transition_matrix_path=args.transition_matrix,
        bootstrap_iterations=args.bootstrap_iterations,
        seed=args.seed,
        dry_run=args.dry_run,
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return report


if __name__ == "__main__":
    main()
