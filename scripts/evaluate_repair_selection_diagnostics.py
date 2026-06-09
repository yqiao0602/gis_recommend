#!/usr/bin/env python3
"""Evaluation-only repair selection diagnostics for retrieval-centered planning.

This phase consumes the previous repair oracle artifacts and explains why
modified local-repair candidates are not selected.  It does not train, load a
model, mutate checkpoints, or generate new workflow candidates.
"""

from __future__ import annotations

import argparse
import json
import random
import sys
from collections import Counter
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


SCHEMA_VERSION = "gis_recommend.v5_final.repair_selection_diagnostics.v1"
DEFAULT_SCORE_WEIGHTS = {
    "retrieval": 0.20,
    "io": 0.80,
    "set": 0.45,
    "length": 0.20,
    "agreement": 0.10,
    "edit_penalty": 0.20,
    "v5": 0.35,
}
DEFAULT_THRESHOLD_POLICIES = {
    "conservative": 0.02,
    "balanced": -0.03,
    "aggressive": -0.10,
}
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
]


def decompose_candidate_score(candidate: dict, *, weights: Optional[dict[str, float]] = None) -> dict:
    """Extract raw and weighted scorer terms from one candidate trace row."""

    active_weights = dict(DEFAULT_SCORE_WEIGHTS)
    if weights:
        active_weights.update({str(key): float(value) for key, value in weights.items()})
    features = candidate.get("execution_features") or {}
    v5_score = candidate.get("v5_score") or {}
    raw_terms = {
        "retrieval_score": _float(features.get("retrieval_score", candidate.get("retrieval_score", candidate.get("score", 0.0)))),
        "execution_score": _float(features.get("io_validity", candidate.get("io_validity", 1.0))),
        "set_agreement": _float(features.get("set_predictor_agreement", (candidate.get("set_filter") or {}).get("set_predictor_agreement", 0.0))),
        "length_prior": _float(features.get("length_prior", candidate.get("length_prior", 0.0))),
        "retrieval_agreement": _float(features.get("retrieval_agreement", 0.0)),
        "edit_penalty": _float(
            features.get(
                "edit_distance_penalty",
                candidate.get("edit_distance_from_retrieval", candidate.get("edit_distance_from_source", 0.0)),
            )
        ),
        "v5_score": _float(features.get("v5_plausibility", v5_score.get("v5_plausibility", 0.0))),
    }
    weighted_terms = {
        "retrieval_score": round(active_weights["retrieval"] * raw_terms["retrieval_score"], 8),
        "execution_score": round(active_weights["io"] * raw_terms["execution_score"], 8),
        "set_agreement": round(active_weights["set"] * raw_terms["set_agreement"], 8),
        "length_prior": round(active_weights["length"] * raw_terms["length_prior"], 8),
        "retrieval_agreement": round(active_weights["agreement"] * raw_terms["retrieval_agreement"], 8),
        "edit_penalty": round(-active_weights["edit_penalty"] * raw_terms["edit_penalty"], 8),
        "v5_score": round(active_weights["v5"] * raw_terms["v5_score"], 8),
    }
    computed = round(sum(weighted_terms.values()), 8)
    return {
        "tokens": [int(token) for token in candidate.get("tokens", [])],
        "candidate_kind": _candidate_kind(candidate),
        "is_modified": _is_modified_candidate(candidate),
        "raw_terms": raw_terms,
        "weighted_terms": weighted_terms,
        "computed_aggregate_score": computed,
        "final_aggregate_score": _candidate_score(candidate, default=computed),
        "rank": candidate.get("rank"),
        "metrics": _candidate_metrics(candidate),
        "metric_delta_vs_identity": _candidate_metric_delta(candidate),
    }


def strongest_suppressing_term(identity_decomposition: dict, modified_decomposition: dict) -> dict:
    """Return the weighted term that most suppresses a modified candidate."""

    deltas = {}
    identity_terms = identity_decomposition.get("weighted_terms", {})
    modified_terms = modified_decomposition.get("weighted_terms", {})
    for key in sorted(set(identity_terms) | set(modified_terms)):
        deltas[key] = round(_float(modified_terms.get(key)) - _float(identity_terms.get(key)), 8)
    if not deltas:
        return {"term": "none", "delta": 0.0, "term_deltas": {}}
    term, delta = min(deltas.items(), key=lambda item: (item[1], item[0]))
    if delta >= 0.0:
        return {"term": "none", "delta": round(delta, 8), "term_deltas": deltas}
    return {"term": term, "delta": round(delta, 8), "term_deltas": deltas}


def analyze_identity_bias(samples: Sequence[dict], *, near_miss_margin: float = 0.05) -> dict:
    """Measure identity-vs-modified selection and near-miss behavior."""

    identity_selected = 0
    modified_selected = 0
    modified_available = 0
    near_misses = 0
    margins = []
    selected_kinds = Counter()
    for sample in samples:
        candidates = _sample_candidates(sample)
        if not candidates:
            continue
        selected = _selected_candidate(candidates)
        identity = _identity_candidate(sample, candidates)
        modified = _modified_candidates(candidates)
        selected_kind = _candidate_kind(selected)
        selected_kinds.update([selected_kind])
        if _is_modified_candidate(selected):
            modified_selected += 1
        else:
            identity_selected += 1
        if modified:
            modified_available += 1
            best_modified = _best_by_score(modified)
            margin = round(_candidate_score(identity) - _candidate_score(best_modified), 8)
            margins.append(margin)
            if not _is_modified_candidate(selected) and _candidate_score(best_modified) >= _candidate_score(identity) - float(near_miss_margin):
                near_misses += 1
    total = max(len(samples), 1)
    available = max(modified_available, 1)
    return {
        "sample_count": len(samples),
        "identity_selected_count": identity_selected,
        "modified_selected_count": modified_selected,
        "identity_selection_frequency": round(identity_selected / total, 8),
        "modified_selection_frequency": round(modified_selected / total, 8),
        "modified_candidate_available_count": modified_available,
        "modified_candidate_availability_rate": round(modified_available / total, 8),
        "modified_near_miss_count": near_misses,
        "modified_near_miss_rate": round(near_misses / available, 8),
        "near_miss_margin": float(near_miss_margin),
        "identity_minus_best_modified_score_margin": _distribution(margins),
        "selected_candidate_kind_counts": dict(sorted(selected_kinds.items())),
    }


def attribute_oracle_gap(sample: dict, *, calibration_margin: float = 0.02) -> dict:
    """Attribute selected-vs-oracle repair gap for one sample."""

    candidates = _sample_candidates(sample)
    identity = _identity_candidate(sample, candidates)
    selected = _selected_candidate(candidates) if candidates else identity
    oracle = _best_modified_by_metric(candidates) or identity
    selected_decomp = decompose_candidate_score(selected)
    identity_decomp = decompose_candidate_score(identity)
    oracle_decomp = decompose_candidate_score(oracle)
    selected_metrics = selected_decomp["metrics"]
    identity_metrics = identity_decomp["metrics"]
    oracle_metrics = oracle_decomp["metrics"]
    score_delta = round(oracle_decomp["final_aggregate_score"] - selected_decomp["final_aggregate_score"], 8)
    metric_delta = {
        "lcs_ratio": round(_float(oracle_metrics.get("lcs_ratio")) - _float(selected_metrics.get("lcs_ratio")), 8),
        "set_f1": round(_float(oracle_metrics.get("set_f1")) - _float(selected_metrics.get("set_f1")), 8),
        "token_accuracy": round(_float(oracle_metrics.get("token_accuracy")) - _float(selected_metrics.get("token_accuracy")), 8),
    }
    oracle_identity_gain = {
        "lcs_ratio": round(_float(oracle_metrics.get("lcs_ratio")) - _float(identity_metrics.get("lcs_ratio")), 8),
        "set_f1": round(_float(oracle_metrics.get("set_f1")) - _float(identity_metrics.get("set_f1")), 8),
        "token_accuracy": round(_float(oracle_metrics.get("token_accuracy")) - _float(identity_metrics.get("token_accuracy")), 8),
    }
    suppression = strongest_suppressing_term(identity_decomp, oracle_decomp)
    category = classify_oracle_gap(
        identity_decomposition=identity_decomp,
        selected_decomposition=selected_decomp,
        oracle_decomposition=oracle_decomp,
        score_delta=score_delta,
        metric_delta=metric_delta,
        oracle_identity_gain=oracle_identity_gain,
        suppression=suppression,
        calibration_margin=calibration_margin,
    )
    return {
        "local_index": sample.get("local_index"),
        "source_test_index": sample.get("source_test_index"),
        "task_type": sample.get("task_type"),
        "selected_candidate_kind": selected_decomp["candidate_kind"],
        "oracle_candidate_kind": oracle_decomp["candidate_kind"],
        "selected_candidate_score": selected_decomp["final_aggregate_score"],
        "oracle_candidate_score": oracle_decomp["final_aggregate_score"],
        "identity_candidate_score": identity_decomp["final_aggregate_score"],
        "score_delta": score_delta,
        "metric_delta": metric_delta,
        "oracle_identity_gain": oracle_identity_gain,
        "strongest_suppressor": suppression,
        "failure_category": category,
        "selected_tokens": selected_decomp["tokens"],
        "oracle_tokens": oracle_decomp["tokens"],
    }


def classify_oracle_gap(
    *,
    identity_decomposition: dict,
    selected_decomposition: dict,
    oracle_decomposition: dict,
    score_delta: float,
    metric_delta: dict,
    oracle_identity_gain: dict,
    suppression: dict,
    calibration_margin: float,
    eps: float = 1e-9,
) -> str:
    """Classify why the best repaired candidate was not selected."""

    if _float(oracle_identity_gain.get("lcs_ratio")) <= eps:
        return "retrieval_saturation"
    if _float(metric_delta.get("lcs_ratio")) <= eps:
        return "selection_aligned_or_evaluation_mismatch"
    selected_raw = selected_decomposition.get("raw_terms", {})
    oracle_raw = oracle_decomposition.get("raw_terms", {})
    if _float(oracle_raw.get("execution_score")) < _float(selected_raw.get("execution_score")) - eps:
        return "execution_conflict"
    if float(score_delta) >= -float(calibration_margin):
        return "calibration_collapse"
    if suppression.get("term") == "edit_penalty":
        return "edit_oversuppression"
    if suppression.get("term") == "retrieval_score":
        return "retrieval_dominance"
    return "ranking_inversion"


def threshold_sweep(samples: Sequence[dict], *, policies: Optional[dict[str, float]] = None) -> dict:
    """Run evaluation-only repair acceptance margins against scorer outputs."""

    active_policies = dict(DEFAULT_THRESHOLD_POLICIES if policies is None else policies)
    results = {}
    for name, margin in active_policies.items():
        selected_rows = []
        for sample in samples:
            candidates = _sample_candidates(sample)
            identity = _identity_candidate(sample, candidates)
            modified = _modified_candidates(candidates)
            chosen = identity
            if modified:
                best_modified = _best_by_score(modified)
                if _candidate_score(best_modified) >= _candidate_score(identity) + float(margin):
                    chosen = best_modified
            selected_rows.append(chosen)
        results[str(name)] = _selection_policy_summary(selected_rows, samples, acceptance_margin=float(margin))
    return results


def random_modified_control(samples: Sequence[dict], *, seed: int = 42) -> dict:
    """Compare current scorer selection against deterministic random repair acceptance."""

    rng = random.Random(int(seed))
    random_rows = []
    current_rows = []
    for sample in samples:
        candidates = _sample_candidates(sample)
        modified = _modified_candidates(candidates)
        current_rows.append(_selected_candidate(candidates) if candidates else {})
        random_rows.append(rng.choice(modified) if modified else _identity_candidate(sample, candidates))
    random_summary = _selection_policy_summary(random_rows, samples, acceptance_margin=None)
    current_summary = _selection_policy_summary(current_rows, samples, acceptance_margin=None)
    return {
        "seed": int(seed),
        "sample_count": len(samples),
        "random_evaluated_samples": len(random_rows),
        "random_repair_adoption_rate": random_summary["repair_adoption_rate"],
        "random_corruption_rate": random_summary["corruption_rate"],
        "random_mean_lcs_gain": random_summary["mean_lcs_gain"],
        "random_mean_set_f1_gain": random_summary["mean_set_f1_gain"],
        "random_mean_token_accuracy_gain": random_summary["mean_token_accuracy_gain"],
        "current_modified_selection_rate": current_summary["repair_adoption_rate"],
        "current_corruption_rate": current_summary["corruption_rate"],
        "current_mean_lcs_gain": current_summary["mean_lcs_gain"],
        "current_mean_set_f1_gain": current_summary["mean_set_f1_gain"],
        "current_mean_token_accuracy_gain": current_summary["mean_token_accuracy_gain"],
        "scorer_beats_random_by_lcs": bool(current_summary["mean_lcs_gain"] > random_summary["mean_lcs_gain"]),
        "lcs_gain_delta_current_minus_random": round(current_summary["mean_lcs_gain"] - random_summary["mean_lcs_gain"], 8),
        "note": "Random control uses modified candidates only when available; no model or training is invoked.",
    }


def evaluate_repair_selection_diagnostics(
    *,
    oracle_report_path: Path,
    candidate_traces_path: Path,
    output_dir: Path,
    near_miss_margin: float,
    calibration_margin: float,
    seed: int,
    dry_run: bool = False,
) -> dict:
    oracle_report = _load_json(oracle_report_path)
    traces = _load_json(candidate_traces_path)
    samples = traces.get("samples", [])
    if not isinstance(samples, list):
        raise ValueError(f"Invalid candidate trace payload: {candidate_traces_path}")
    output_dir.mkdir(parents=True, exist_ok=True)
    created_at = _now()
    dry_summary = {
        "schema_version": SCHEMA_VERSION,
        "created_at": created_at,
        "dry_run": True,
        "oracle_report": str(oracle_report_path),
        "candidate_traces": str(candidate_traces_path),
        "output_dir": str(output_dir),
        "sample_count": len(samples),
    }
    if dry_run:
        _write_json(output_dir / "dry_run_summary.json", dry_summary)
        return dry_summary

    scorer_terms = analyze_scorer_terms(samples)
    identity_bias = analyze_identity_bias(samples, near_miss_margin=float(near_miss_margin))
    oracle_gaps = [attribute_oracle_gap(sample, calibration_margin=float(calibration_margin)) for sample in samples]
    failure_report = build_failure_breakdown(oracle_gaps)
    sweep_report = {
        "schema_version": f"{SCHEMA_VERSION}.threshold_sweep",
        "created_at": created_at,
        "policies": threshold_sweep(samples),
        "policy_definition": "Accept best modified candidate when score >= identity score + acceptance_margin.",
    }
    random_report = {
        "schema_version": f"{SCHEMA_VERSION}.random_control",
        "created_at": created_at,
        **random_modified_control(samples, seed=int(seed)),
    }
    diagnostics = {
        "schema_version": SCHEMA_VERSION,
        "created_at": created_at,
        "dry_run": False,
        "oracle_report": str(oracle_report_path),
        "candidate_traces": str(candidate_traces_path),
        "sample_count": len(samples),
        "source_oracle_summary": oracle_report.get("oracle_summary", {}),
        "identity_bias": identity_bias,
        "oracle_gap_summary": _oracle_gap_summary(oracle_gaps),
        "scorer_term_summary": scorer_terms.get("summary", {}),
        "threshold_sweep_summary": sweep_report["policies"],
        "random_control_summary": {
            key: value
            for key, value in random_report.items()
            if key
            not in {
                "schema_version",
                "created_at",
            }
        },
        "dominant_bottleneck": infer_dominant_bottleneck(failure_report, scorer_terms, identity_bias, random_report),
        "runtime_contract": {
            "evaluation_only": True,
            "training_run": False,
            "checkpoint_loaded": False,
            "checkpoint_mutated": False,
            "architecture_modified": False,
            "new_loss_added": False,
            "gradient_usage": False,
            "report_objects_gate_runtime": False,
        },
    }
    scorer_report = {
        "schema_version": f"{SCHEMA_VERSION}.scorer_terms",
        "created_at": created_at,
        "score_weights": dict(DEFAULT_SCORE_WEIGHTS),
        **scorer_terms,
    }
    failure_report = {
        "schema_version": f"{SCHEMA_VERSION}.failure_breakdown",
        "created_at": created_at,
        **failure_report,
    }

    _write_json(output_dir / "diagnostics_report.json", diagnostics)
    _write_json(output_dir / "scorer_term_analysis.json", scorer_report)
    _write_json(output_dir / "threshold_sweep.json", sweep_report)
    _write_json(output_dir / "failure_breakdown.json", failure_report)
    _write_json(output_dir / "random_control_comparison.json", random_report)
    _write_markdown(output_dir / "summary.md", diagnostics, failure_report, sweep_report, random_report)
    scan = forbidden_pattern_scan(
        [
            Path(__file__).relative_to(ROOT),
            Path("tests") / "test_repair_selection_diagnostics.py",
        ]
    )
    _write_json(output_dir / "forbidden_pattern_scan_repair_selection_diagnostics.json", scan)
    return diagnostics


def analyze_scorer_terms(samples: Sequence[dict]) -> dict:
    decompositions = []
    suppressor_counts: Counter = Counter()
    term_delta_totals: Counter = Counter()
    modified_count = 0
    identity_term_rows = []
    modified_term_rows = []
    for sample in samples:
        candidates = _sample_candidates(sample)
        identity = _identity_candidate(sample, candidates)
        identity_decomp = decompose_candidate_score(identity)
        identity_term_rows.append(identity_decomp["weighted_terms"])
        sample_rows = []
        for rank, candidate in enumerate(candidates):
            decomp = decompose_candidate_score(candidate)
            decomp["local_index"] = sample.get("local_index")
            decomp["source_test_index"] = sample.get("source_test_index")
            decomp["candidate_rank"] = int(candidate.get("rank", rank) or 0)
            if decomp["is_modified"]:
                modified_count += 1
                modified_term_rows.append(decomp["weighted_terms"])
                suppression = strongest_suppressing_term(identity_decomp, decomp)
                decomp["strongest_suppressor_vs_identity"] = suppression
                suppressor_counts.update([suppression["term"]])
                for term, delta in suppression.get("term_deltas", {}).items():
                    term_delta_totals[term] += float(delta)
            sample_rows.append(decomp)
        decompositions.append(
            {
                "local_index": sample.get("local_index"),
                "source_test_index": sample.get("source_test_index"),
                "candidate_decompositions": sample_rows,
            }
        )
    mean_term_deltas = {
        key: round(value / max(modified_count, 1), 8)
        for key, value in sorted(term_delta_totals.items())
    }
    summary = {
        "sample_count": len(samples),
        "candidate_count": sum(len(_sample_candidates(sample)) for sample in samples),
        "modified_candidate_count": modified_count,
        "strongest_suppressor_counts": dict(sorted(suppressor_counts.items())),
        "most_common_modified_suppressor": suppressor_counts.most_common(1)[0][0] if suppressor_counts else "none",
        "mean_identity_weighted_terms": _mean_terms(identity_term_rows),
        "mean_modified_weighted_terms": _mean_terms(modified_term_rows),
        "mean_modified_minus_identity_weighted_terms": mean_term_deltas,
    }
    return {"summary": summary, "samples": decompositions}


def build_failure_breakdown(oracle_gaps: Sequence[dict]) -> dict:
    counts = Counter(row.get("failure_category", "unknown") for row in oracle_gaps)
    total = max(len(oracle_gaps), 1)
    return {
        "sample_count": len(oracle_gaps),
        "failure_counts": dict(sorted(counts.items())),
        "failure_rates": {key: round(value / total, 8) for key, value in sorted(counts.items())},
        "oracle_gap_rows": list(oracle_gaps),
        "definitions": {
            "ranking_inversion": "Oracle repair improves metrics but receives lower aggregate score for reasons other than a dominant single suppressor.",
            "calibration_collapse": "Oracle repair is within the configured score margin but is still not selected.",
            "edit_oversuppression": "Edit penalty is the strongest negative score delta against the identity candidate.",
            "execution_conflict": "Oracle repair has lower execution/IO score than the selected candidate.",
            "retrieval_dominance": "Retrieval-score delta is the strongest suppressor for a useful modified candidate.",
            "retrieval_saturation": "No modified repair improves the identity candidate by LCS.",
            "selection_aligned_or_evaluation_mismatch": "Selected output is already no worse by the measured LCS signal, or metrics disagree.",
        },
    }


def infer_dominant_bottleneck(failure_report: dict, scorer_terms: dict, identity_bias: dict, random_report: dict) -> dict:
    counts = failure_report.get("failure_counts", {})
    top_failure = max(counts.items(), key=lambda item: item[1])[0] if counts else "unknown"
    suppressors = scorer_terms.get("summary", {}).get("strongest_suppressor_counts", {})
    top_suppressor = max(suppressors.items(), key=lambda item: item[1])[0] if suppressors else "none"
    scorer_beats_random = bool(random_report.get("scorer_beats_random_by_lcs"))
    if top_failure == "edit_oversuppression":
        bottleneck = "edit_penalty_oversuppression"
    elif top_failure == "calibration_collapse":
        bottleneck = "confidence_calibration"
    elif top_failure == "retrieval_dominance":
        bottleneck = "retrieval_dominance"
    elif top_failure == "ranking_inversion":
        bottleneck = "scorer_blindness"
    elif not scorer_beats_random:
        bottleneck = "scorer_blindness_or_random_repair_competitive"
    elif identity_bias.get("identity_selection_frequency", 0.0) > 0.9 and top_suppressor != "none":
        bottleneck = "over_preservation_bias"
    else:
        bottleneck = "mixed_or_inconclusive"
    return {
        "primary": bottleneck,
        "top_failure_category": top_failure,
        "top_modified_candidate_suppressor": top_suppressor,
        "scorer_beats_random_by_lcs": scorer_beats_random,
        "evidence_only": True,
    }


def forbidden_pattern_scan(files: Sequence[Path]) -> dict:
    import re

    matches = []
    for file in files:
        path = ROOT / file
        text = path.read_text(encoding="utf-8") if path.exists() else ""
        for pattern in FORBIDDEN_PATTERNS:
            regex = re.compile(pattern, flags=re.IGNORECASE)
            for match in regex.finditer(text):
                line_no = text.count("\n", 0, match.start()) + 1
                matches.append({"file": str(file), "line": line_no, "pattern": pattern, "match": match.group(0)})
    return {
        "schema_version": "gis_recommend.v5_final.forbidden_pattern_scan.v1",
        "files": [str(file) for file in files],
        "patterns": list(FORBIDDEN_PATTERNS),
        "match_count": len(matches),
        "matches": matches,
        "result": "pass" if not matches else "fail",
    }


def _selection_policy_summary(selected_rows: Sequence[dict], samples: Sequence[dict], *, acceptance_margin: Optional[float]) -> dict:
    adopted = [_is_modified_candidate(row) for row in selected_rows]
    deltas = [_candidate_metric_delta(row) for row in selected_rows]
    corruptions = [delta["lcs_ratio"] < 0.0 for delta in deltas]
    return {
        "sample_count": len(selected_rows),
        "acceptance_margin": acceptance_margin,
        "repair_adoption_count": sum(1 for value in adopted if value),
        "repair_adoption_rate": round(_mean(1.0 if value else 0.0 for value in adopted), 8),
        "corruption_count": sum(1 for value in corruptions if value),
        "corruption_rate": round(_mean(1.0 if value else 0.0 for value in corruptions), 8),
        "mean_lcs_gain": round(_mean(delta["lcs_ratio"] for delta in deltas), 8),
        "mean_set_f1_gain": round(_mean(delta["set_f1"] for delta in deltas), 8),
        "mean_token_accuracy_gain": round(_mean(delta["token_accuracy"] for delta in deltas), 8),
        "net_positive_lcs_rate": round(_mean(1.0 if delta["lcs_ratio"] > 0.0 else 0.0 for delta in deltas), 8),
    }


def _oracle_gap_summary(rows: Sequence[dict]) -> dict:
    return {
        "sample_count": len(rows),
        "mean_score_delta_oracle_minus_selected": round(_mean(row.get("score_delta", 0.0) for row in rows), 8),
        "mean_metric_delta_oracle_minus_selected": {
            "lcs_ratio": round(_mean(row.get("metric_delta", {}).get("lcs_ratio", 0.0) for row in rows), 8),
            "set_f1": round(_mean(row.get("metric_delta", {}).get("set_f1", 0.0) for row in rows), 8),
            "token_accuracy": round(_mean(row.get("metric_delta", {}).get("token_accuracy", 0.0) for row in rows), 8),
        },
        "ranking_inversion_rate": round(_mean(1.0 if row.get("score_delta", 0.0) < 0.0 and row.get("metric_delta", {}).get("lcs_ratio", 0.0) > 0.0 else 0.0 for row in rows), 8),
    }


def _candidate_metrics(candidate: dict) -> dict:
    attribution = candidate.get("repair_attribution") or {}
    metrics = attribution.get("candidate_metrics") or candidate.get("metrics") or {}
    return {
        "lcs_ratio": _float(metrics.get("lcs_ratio")),
        "set_f1": _float(metrics.get("set_f1")),
        "token_accuracy": _float(metrics.get("token_accuracy")),
    }


def _candidate_metric_delta(candidate: dict) -> dict:
    attribution = candidate.get("repair_attribution") or {}
    if any(key in attribution for key in ("lcs_delta", "set_f1_delta", "token_accuracy_delta")):
        return {
            "lcs_ratio": _float(attribution.get("lcs_delta")),
            "set_f1": _float(attribution.get("set_f1_delta")),
            "token_accuracy": _float(attribution.get("token_accuracy_delta")),
        }
    metrics = _candidate_metrics(candidate)
    identity_metrics = attribution.get("identity_metrics") or {}
    return {
        "lcs_ratio": round(metrics["lcs_ratio"] - _float(identity_metrics.get("lcs_ratio")), 8),
        "set_f1": round(metrics["set_f1"] - _float(identity_metrics.get("set_f1")), 8),
        "token_accuracy": round(metrics["token_accuracy"] - _float(identity_metrics.get("token_accuracy")), 8),
    }


def _sample_candidates(sample: dict) -> list[dict]:
    candidates = sample.get("repair_candidate_pool") or sample.get("top_repair_candidates") or []
    return [row for row in candidates if isinstance(row, dict)]


def _selected_candidate(candidates: Sequence[dict]) -> dict:
    rows = list(candidates)
    return rows[0] if rows else {}


def _identity_candidate(sample: dict, candidates: Sequence[dict]) -> dict:
    identity_tokens = [int(token) for token in sample.get("identity_tokens", [])]
    for row in candidates:
        if _candidate_kind(row) == "identity":
            return row
    if identity_tokens:
        for row in candidates:
            if [int(token) for token in row.get("tokens", [])] == identity_tokens:
                return row
    return list(candidates)[0] if candidates else {"tokens": identity_tokens, "candidate_kind": "identity"}


def _modified_candidates(candidates: Sequence[dict]) -> list[dict]:
    return [row for row in candidates if _is_modified_candidate(row)]


def _best_modified_by_metric(candidates: Sequence[dict]) -> Optional[dict]:
    modified = _modified_candidates(candidates)
    if not modified:
        return None
    return max(
        modified,
        key=lambda row: (
            _candidate_metrics(row)["lcs_ratio"],
            _candidate_metrics(row)["token_accuracy"],
            _candidate_metrics(row)["set_f1"],
            -int(_float(row.get("edit_distance_from_retrieval", row.get("edit_distance_from_source", 0.0)))),
        ),
    )


def _best_by_score(candidates: Sequence[dict]) -> dict:
    rows = list(candidates)
    return max(
        rows,
        key=lambda row: (
            _candidate_score(row),
            _float(row.get("retrieval_score", row.get("score", 0.0))),
            -_float(row.get("edit_distance_from_retrieval", row.get("edit_distance_from_source", 0.0))),
        ),
    )


def _candidate_kind(candidate: dict) -> str:
    return str(candidate.get("repair_operation") or candidate.get("candidate_kind") or candidate.get("repair_kind") or "unknown")


def _is_modified_candidate(candidate: dict) -> bool:
    kind = _candidate_kind(candidate)
    edit_distance = _float(candidate.get("edit_distance_from_retrieval", candidate.get("edit_distance_from_source", 0.0)))
    return kind != "identity" and (edit_distance > 0.0 or kind not in {"unknown", "identity"})


def _candidate_score(candidate: dict, *, default: float = 0.0) -> float:
    for key in ("execution_aware_score", "hybrid_score", "final_aggregate_score", "score"):
        if candidate.get(key) is not None:
            return _float(candidate.get(key))
    return float(default)


def _mean_terms(rows: Sequence[dict]) -> dict:
    keys = sorted({key for row in rows for key in row})
    return {key: round(_mean(row.get(key, 0.0) for row in rows), 8) for key in keys}


def _distribution(values: Sequence[float]) -> dict:
    rows = sorted(float(value) for value in values)
    if not rows:
        return {"count": 0, "min": 0.0, "p25": 0.0, "median": 0.0, "p75": 0.0, "max": 0.0, "mean": 0.0}
    return {
        "count": len(rows),
        "min": round(rows[0], 8),
        "p25": round(_quantile(rows, 0.25), 8),
        "median": round(_quantile(rows, 0.50), 8),
        "p75": round(_quantile(rows, 0.75), 8),
        "max": round(rows[-1], 8),
        "mean": round(_mean(rows), 8),
    }


def _quantile(rows: Sequence[float], q: float) -> float:
    if not rows:
        return 0.0
    pos = (len(rows) - 1) * float(q)
    lower = int(pos)
    upper = min(lower + 1, len(rows) - 1)
    weight = pos - lower
    return rows[lower] * (1.0 - weight) + rows[upper] * weight


def _float(value, default: float = 0.0) -> float:
    try:
        if value is None:
            return float(default)
        return float(value)
    except (TypeError, ValueError):
        return float(default)


def _mean(values) -> float:
    rows = [float(value) for value in values]
    return sum(rows) / max(len(rows), 1)


def _load_json(path: Path) -> dict:
    with Path(path).open("r", encoding="utf-8") as f:
        payload = json.load(f)
    if not isinstance(payload, dict):
        raise ValueError(f"Expected JSON object: {path}")
    return payload


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _write_markdown(path: Path, diagnostics: dict, failure_report: dict, sweep_report: dict, random_report: dict) -> None:
    dominant = diagnostics.get("dominant_bottleneck", {})
    identity = diagnostics.get("identity_bias", {})
    lines = [
        "# Repair Selection Diagnostics",
        "",
        "Evaluation-only diagnostics over the existing repair oracle traces. No training, model loading, or checkpoint mutation is performed.",
        "",
        f"Samples: `{diagnostics.get('sample_count')}`",
        f"Dominant bottleneck: `{dominant.get('primary')}`",
        f"Top failure category: `{dominant.get('top_failure_category')}`",
        f"Top suppressor: `{dominant.get('top_modified_candidate_suppressor')}`",
        "",
        "## Identity Bias",
        "",
        "```json",
        json.dumps(identity, ensure_ascii=False, indent=2),
        "```",
        "",
        "## Failure Breakdown",
        "",
        "```json",
        json.dumps(
            {
                "failure_counts": failure_report.get("failure_counts", {}),
                "failure_rates": failure_report.get("failure_rates", {}),
            },
            ensure_ascii=False,
            indent=2,
        ),
        "```",
        "",
        "## Threshold Sweep",
        "",
        "```json",
        json.dumps(sweep_report.get("policies", {}), ensure_ascii=False, indent=2),
        "```",
        "",
        "## Random Control",
        "",
        "```json",
        json.dumps(
            {
                key: value
                for key, value in random_report.items()
                if key not in {"schema_version", "created_at"}
            },
            ensure_ascii=False,
            indent=2,
        ),
        "```",
        "",
        "Generation contribution is zero in this phase; all measurements are selection diagnostics over retrieval/local-repair candidates.",
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _build_parser() -> argparse.ArgumentParser:
    oracle_dir = OUTPUT_DIR / "v5_final_reports" / "repair_oracle_phase"
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--oracle-report", type=Path, default=oracle_dir / "repair_oracle_report.json")
    parser.add_argument("--candidate-traces", type=Path, default=oracle_dir / "repair_candidate_traces.json")
    parser.add_argument("--output-dir", type=Path, default=OUTPUT_DIR / "v5_final_reports" / "repair_selection_diagnostics")
    parser.add_argument("--near-miss-margin", type=float, default=0.05)
    parser.add_argument("--calibration-margin", type=float, default=0.02)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--dry-run", action="store_true")
    return parser


def main(argv: Optional[list[str]] = None) -> dict:
    args = _build_parser().parse_args(argv)
    report = evaluate_repair_selection_diagnostics(
        oracle_report_path=args.oracle_report,
        candidate_traces_path=args.candidate_traces,
        output_dir=args.output_dir,
        near_miss_margin=args.near_miss_margin,
        calibration_margin=args.calibration_margin,
        seed=args.seed,
        dry_run=args.dry_run,
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return report


if __name__ == "__main__":
    main()
