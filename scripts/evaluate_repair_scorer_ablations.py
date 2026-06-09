#!/usr/bin/env python3
"""Evaluation-only scorer ablations for local repair candidate selection.

This script re-scores existing repair oracle candidate pools.  It does not
train, load checkpoints, mutate checkpoints, or modify model architecture.
"""

from __future__ import annotations

import argparse
import json
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
from scripts.evaluate_repair_selection_diagnostics import (  # noqa: E402
    DEFAULT_SCORE_WEIGHTS,
    attribute_oracle_gap,
    decompose_candidate_score,
    forbidden_pattern_scan,
    threshold_sweep,
)


SCHEMA_VERSION = "gis_recommend.v5_final.repair_scorer_ablations.v1"
DEFAULT_ABLATION_POLICIES = {
    "baseline_reconstructed": {
        "name": "baseline_reconstructed",
        "description": "Reconstruct current execution-aware scorer from persisted score terms.",
        "weights": dict(DEFAULT_SCORE_WEIGHTS),
    },
    "no_edit_penalty": {
        "name": "no_edit_penalty",
        "description": "Set edit penalty weight to zero while keeping all other terms unchanged.",
        "weights": {**DEFAULT_SCORE_WEIGHTS, "edit_penalty": 0.0},
    },
    "piecewise_edit_penalty": {
        "name": "piecewise_edit_penalty",
        "description": "Use operation-specific edit penalties instead of one uniform edit penalty.",
        "weights": {**DEFAULT_SCORE_WEIGHTS, "edit_penalty": 0.0},
        "operation_edit_penalties": {
            "operator_substitution": 0.04,
            "operator_deletion": 0.06,
            "local_swap": 0.08,
            "bridge_insertion": 0.12,
            "insertion": 0.12,
            "removal": 0.06,
            "substitution": 0.04,
        },
    },
    "uniform_edit_0_08": {
        "name": "uniform_edit_0_08",
        "description": "Lower uniform edit penalty to 0.08.",
        "weights": {**DEFAULT_SCORE_WEIGHTS, "edit_penalty": 0.08},
    },
    "uniform_edit_0_10": {
        "name": "uniform_edit_0_10",
        "description": "Lower uniform edit penalty to 0.10.",
        "weights": {**DEFAULT_SCORE_WEIGHTS, "edit_penalty": 0.10},
    },
    "uniform_edit_0_12": {
        "name": "uniform_edit_0_12",
        "description": "Lower uniform edit penalty to 0.12.",
        "weights": {**DEFAULT_SCORE_WEIGHTS, "edit_penalty": 0.12},
    },
    "uniform_edit_0_14": {
        "name": "uniform_edit_0_14",
        "description": "Lower uniform edit penalty to 0.14.",
        "weights": {**DEFAULT_SCORE_WEIGHTS, "edit_penalty": 0.14},
    },
    "uniform_edit_0_16": {
        "name": "uniform_edit_0_16",
        "description": "Lower uniform edit penalty to 0.16.",
        "weights": {**DEFAULT_SCORE_WEIGHTS, "edit_penalty": 0.16},
    },
    "execution_set_heavy": {
        "name": "execution_set_heavy",
        "description": "Increase set/V5/local plausibility relative to preservation pressure.",
        "weights": {
            "retrieval": 0.12,
            "io": 0.80,
            "set": 0.70,
            "length": 0.20,
            "agreement": 0.10,
            "edit_penalty": 0.06,
            "v5": 0.45,
        },
    },
    "retrieval_preservation_heavy": {
        "name": "retrieval_preservation_heavy",
        "description": "Keep strong retrieval preservation and current uniform edit penalty.",
        "weights": {
            "retrieval": 0.35,
            "io": 0.80,
            "set": 0.35,
            "length": 0.20,
            "agreement": 0.10,
            "edit_penalty": 0.20,
            "v5": 0.25,
        },
    },
}


def rescore_candidate(candidate: dict, policy: dict) -> dict:
    """Score one candidate under an evaluation-only ablation policy."""

    weights = _policy_weights(policy)
    base = decompose_candidate_score(candidate, weights={**DEFAULT_SCORE_WEIGHTS, "edit_penalty": 0.0})
    raw_terms = base["raw_terms"]
    edit_weight = _operation_edit_weight(candidate, policy)
    weighted_terms = {
        "retrieval_score": round(weights.get("retrieval", 0.0) * raw_terms["retrieval_score"], 8),
        "execution_score": round(weights.get("io", 0.0) * raw_terms["execution_score"], 8),
        "set_agreement": round(weights.get("set", 0.0) * raw_terms["set_agreement"], 8),
        "length_prior": round(weights.get("length", 0.0) * raw_terms["length_prior"], 8),
        "retrieval_agreement": round(weights.get("agreement", 0.0) * raw_terms["retrieval_agreement"], 8),
        "v5_score": round(weights.get("v5", 0.0) * raw_terms["v5_score"], 8),
        "edit_penalty": round(-float(edit_weight) * raw_terms["edit_penalty"], 8),
    }
    ablated_score = round(sum(weighted_terms.values()), 8)
    return {
        **base,
        "policy_name": str(policy.get("name", "unnamed_policy")),
        "weighted_terms": weighted_terms,
        "edit_penalty_weight_used": round(float(edit_weight), 8),
        "ablated_score": ablated_score,
        "original_score": base["final_aggregate_score"],
        "repair_operation": _candidate_kind(candidate),
    }


def select_candidate_under_policy(sample: dict, policy: dict) -> dict:
    """Select the highest-scoring candidate after applying one ablation policy."""

    candidates = _sample_candidates(sample)
    rescored = []
    for rank, candidate in enumerate(candidates):
        row = rescore_candidate(candidate, policy)
        row["candidate_rank"] = int(candidate.get("rank", rank) or 0)
        rescored.append(row)
    if not rescored:
        return _empty_policy_selection(sample, policy)
    selected = max(
        rescored,
        key=lambda row: (
            float(row.get("ablated_score", 0.0)),
            float(row.get("raw_terms", {}).get("retrieval_score", 0.0)),
            -float(row.get("raw_terms", {}).get("edit_penalty", 0.0)),
            -int(row.get("candidate_rank", 999999)),
        ),
    )
    identity = _identity_decomposition(sample, rescored)
    oracle = _oracle_modified_decomposition(rescored)
    return {
        "local_index": sample.get("local_index"),
        "source_test_index": sample.get("source_test_index"),
        "task_type": sample.get("task_type"),
        "policy_name": str(policy.get("name", "unnamed_policy")),
        "selected_candidate_kind": selected["candidate_kind"],
        "selected_tokens": selected["tokens"],
        "selected_score": selected["ablated_score"],
        "selected_metric_delta": _metric_delta_from_identity(selected, identity),
        "selected_weighted_terms": selected["weighted_terms"],
        "identity_score": identity["ablated_score"],
        "oracle_candidate_kind": oracle["candidate_kind"] if oracle else None,
        "oracle_metric_delta": _metric_delta_from_identity(oracle, identity) if oracle else _zero_delta(),
        "oracle_score": oracle["ablated_score"] if oracle else None,
        "oracle_tokens": oracle["tokens"] if oracle else [],
        "candidate_count": len(rescored),
        "modified_candidate_count": sum(1 for row in rescored if row["is_modified"]),
        "failure_category": _classify_policy_selection(selected, oracle, identity),
    }


def run_ablation_studies(samples: Sequence[dict], *, policies: Optional[dict[str, dict]] = None) -> dict:
    """Run all evaluation-only scorer ablations over existing candidate pools."""

    active_policies = dict(DEFAULT_ABLATION_POLICIES if policies is None else policies)
    policy_results = {}
    policy_rows = {}
    for name, policy in active_policies.items():
        policy = {**policy, "name": policy.get("name", name)}
        rows = [select_candidate_under_policy(sample, policy) for sample in samples]
        policy_rows[str(name)] = rows
        policy_results[str(name)] = _summarize_policy_rows(rows)
        policy_results[str(name)]["description"] = str(policy.get("description", ""))
        policy_results[str(name)]["weights"] = _policy_weights(policy)
        policy_results[str(name)]["operation_edit_penalties"] = dict(policy.get("operation_edit_penalties", {}))
        policy_results[str(name)]["failure_counts"] = dict(sorted(Counter(row["failure_category"] for row in rows).items()))
    return {
        "schema_version": f"{SCHEMA_VERSION}.ablation_results",
        "sample_count": len(samples),
        "policies": policy_results,
        "policy_selection_rows": policy_rows,
    }


def recommend_scoring_policy(ablation_report: dict, *, max_corruption_rate: float = 0.10) -> dict:
    """Choose a quantitative low-risk policy from ablation results."""

    policies = ablation_report.get("policies", {})
    eligible = {
        name: row
        for name, row in policies.items()
        if float(row.get("corruption_rate", 0.0)) <= float(max_corruption_rate)
        and float(row.get("mean_lcs_gain", 0.0)) > 0.0
        and float(row.get("repair_adoption_rate", 0.0)) > 0.0
    }
    if eligible:
        name, row = max(
            eligible.items(),
            key=lambda item: (
                float(item[1].get("mean_lcs_gain", 0.0)),
                -float(item[1].get("corruption_rate", 0.0)),
                float(item[1].get("repair_adoption_rate", 0.0)),
            ),
        )
        basis = "max_lcs_gain_under_corruption_limit"
    else:
        name, row = max(
            policies.items(),
            key=lambda item: (
                -float(item[1].get("corruption_rate", 1.0)),
                float(item[1].get("mean_lcs_gain", 0.0)),
                float(item[1].get("repair_adoption_rate", 0.0)),
            ),
        ) if policies else ("none", {})
        basis = "no_positive_low_corruption_policy_found"
    return {
        "recommended_policy": name,
        "basis": basis,
        "max_corruption_rate": float(max_corruption_rate),
        "metrics": {
            "repair_adoption_rate": row.get("repair_adoption_rate", 0.0),
            "corruption_rate": row.get("corruption_rate", 0.0),
            "mean_lcs_gain": row.get("mean_lcs_gain", 0.0),
            "mean_set_f1_gain": row.get("mean_set_f1_gain", 0.0),
            "mean_token_accuracy_gain": row.get("mean_token_accuracy_gain", 0.0),
        },
        "quantitative_note": "Recommendation is evaluation-only and must be validated on held-out traces before changing production scoring.",
    }


def evaluate_repair_scorer_ablations(
    *,
    candidate_traces_path: Path,
    output_dir: Path,
    oracle_report_path: Optional[Path],
    seed: int,
    dry_run: bool = False,
) -> dict:
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
        "candidate_traces": str(candidate_traces_path),
        "oracle_report": str(oracle_report_path) if oracle_report_path else None,
        "sample_count": len(samples),
        "output_dir": str(output_dir),
    }
    if dry_run:
        _write_json(output_dir / "dry_run_summary.json", dry_summary)
        return dry_summary

    oracle_report = _load_json(oracle_report_path) if oracle_report_path and oracle_report_path.exists() else {}
    ablations = run_ablation_studies(samples)
    recommendation = recommend_scoring_policy(ablations)
    baseline_gaps = [attribute_oracle_gap(sample) for sample in samples]
    failure_breakdown = _failure_breakdown_from_gaps(baseline_gaps)
    term_diagnostics = _term_diagnostics(samples, ablations)
    threshold_report = {
        "schema_version": f"{SCHEMA_VERSION}.threshold_sweep",
        "created_at": created_at,
        "policies": threshold_sweep(samples),
        "note": "Score-margin sweep over existing scorer outputs; no candidate generation or training.",
    }
    report = {
        "schema_version": SCHEMA_VERSION,
        "created_at": created_at,
        "dry_run": False,
        "candidate_traces": str(candidate_traces_path),
        "oracle_report": str(oracle_report_path) if oracle_report_path else None,
        "sample_count": len(samples),
        "source_oracle_summary": oracle_report.get("oracle_summary", {}),
        "ablation_summary": {name: _strip_policy_details(row) for name, row in ablations["policies"].items()},
        "recommendation": recommendation,
        "runtime_contract": {
            "evaluation_only": True,
            "training_run": False,
            "checkpoint_loaded": False,
            "checkpoint_mutated": False,
            "architecture_modified": False,
            "new_loss_added": False,
            "gradient_usage": False,
        },
    }
    scan = forbidden_pattern_scan(
        [
            Path(__file__).relative_to(ROOT),
            Path("tests") / "test_repair_scorer_ablations.py",
        ]
    )

    _write_json(output_dir / "scorer_ablation_report.json", report)
    _write_json(output_dir / "ablation_results.json", ablations)
    _write_json(output_dir / "scoring_recommendation.json", {"schema_version": f"{SCHEMA_VERSION}.recommendation", "created_at": created_at, **recommendation})
    _write_json(output_dir / "failure_breakdown.json", failure_breakdown)
    _write_json(output_dir / "threshold_sweep.json", threshold_report)
    _write_json(output_dir / "scorer_term_diagnostics.json", term_diagnostics)
    _write_json(output_dir / "forbidden_pattern_scan_repair_scorer_ablations.json", scan)
    _write_markdown(output_dir / "scorer_ablation_summary.md", report, ablations, failure_breakdown, threshold_report)
    return report


def _summarize_policy_rows(rows: Sequence[dict]) -> dict:
    selected_deltas = [row["selected_metric_delta"] for row in rows]
    oracle_deltas = [row["oracle_metric_delta"] for row in rows]
    adopted = [_is_modified_kind(row.get("selected_candidate_kind")) for row in rows]
    corruptions = [delta["lcs_ratio"] < 0.0 for delta in selected_deltas]
    oracle_positive = [max(delta["lcs_ratio"], 0.0) for delta in oracle_deltas]
    return {
        "sample_count": len(rows),
        "repair_adoption_count": sum(1 for value in adopted if value),
        "repair_adoption_rate": round(_mean(1.0 if value else 0.0 for value in adopted), 8),
        "corruption_count": sum(1 for value in corruptions if value),
        "corruption_rate": round(_mean(1.0 if value else 0.0 for value in corruptions), 8),
        "mean_lcs_gain": round(_mean(delta["lcs_ratio"] for delta in selected_deltas), 8),
        "mean_set_f1_gain": round(_mean(delta["set_f1"] for delta in selected_deltas), 8),
        "mean_token_accuracy_gain": round(_mean(delta["token_accuracy"] for delta in selected_deltas), 8),
        "positive_lcs_selection_rate": round(_mean(1.0 if delta["lcs_ratio"] > 0.0 else 0.0 for delta in selected_deltas), 8),
        "selected_candidate_kind_counts": dict(sorted(Counter(row["selected_candidate_kind"] for row in rows).items())),
        "oracle_repair_ceiling": {
            "mean_lcs_gain": round(_mean(oracle_positive), 8),
            "mean_raw_lcs_gain": round(_mean(delta["lcs_ratio"] for delta in oracle_deltas), 8),
            "positive_oracle_rate": round(_mean(1.0 if delta["lcs_ratio"] > 0.0 else 0.0 for delta in oracle_deltas), 8),
            "oracle_corruption_rate": round(_mean(1.0 if delta["lcs_ratio"] < 0.0 else 0.0 for delta in oracle_deltas), 8),
        },
    }


def _term_diagnostics(samples: Sequence[dict], ablations: dict) -> dict:
    baseline_rows = []
    for sample in samples:
        for candidate in _sample_candidates(sample):
            baseline_rows.append(decompose_candidate_score(candidate))
    return {
        "schema_version": f"{SCHEMA_VERSION}.term_diagnostics",
        "created_at": _now(),
        "candidate_count": len(baseline_rows),
        "identity_vs_modified_metric_summary": _identity_vs_modified_metric_summary(samples),
        "policy_score_summary": {
            name: {
                "mean_lcs_gain": row.get("mean_lcs_gain"),
                "repair_adoption_rate": row.get("repair_adoption_rate"),
                "corruption_rate": row.get("corruption_rate"),
                "failure_counts": row.get("failure_counts"),
                "weights": row.get("weights"),
                "operation_edit_penalties": row.get("operation_edit_penalties"),
            }
            for name, row in ablations.get("policies", {}).items()
        },
    }


def _identity_vs_modified_metric_summary(samples: Sequence[dict]) -> dict:
    identity_metrics = []
    modified_deltas = []
    for sample in samples:
        candidates = _sample_candidates(sample)
        identity = _identity_candidate(sample, candidates)
        identity_metrics.append(_candidate_metrics(identity))
        for candidate in candidates:
            if _is_modified_candidate(candidate):
                modified_deltas.append(_candidate_delta(candidate))
    return {
        "identity_count": len(identity_metrics),
        "modified_count": len(modified_deltas),
        "mean_identity_metrics": _mean_metric_rows(identity_metrics),
        "mean_modified_delta_vs_identity": _mean_metric_rows(modified_deltas),
        "modified_positive_lcs_rate": round(_mean(1.0 if row["lcs_ratio"] > 0.0 else 0.0 for row in modified_deltas), 8),
        "modified_corruption_rate": round(_mean(1.0 if row["lcs_ratio"] < 0.0 else 0.0 for row in modified_deltas), 8),
    }


def _failure_breakdown_from_gaps(gaps: Sequence[dict]) -> dict:
    counts = Counter(row.get("failure_category", "unknown") for row in gaps)
    total = max(len(gaps), 1)
    return {
        "schema_version": f"{SCHEMA_VERSION}.failure_breakdown",
        "created_at": _now(),
        "sample_count": len(gaps),
        "failure_counts": dict(sorted(counts.items())),
        "failure_rates": {key: round(value / total, 8) for key, value in sorted(counts.items())},
        "oracle_gap_rows": list(gaps),
    }


def _classify_policy_selection(selected: dict, oracle: Optional[dict], identity: dict) -> str:
    if oracle is None or _metric_delta_from_identity(oracle, identity)["lcs_ratio"] <= 0.0:
        return "retrieval_saturation"
    selected_delta = _metric_delta_from_identity(selected, identity)
    oracle_delta = _metric_delta_from_identity(oracle, identity)
    if selected["tokens"] == oracle["tokens"]:
        return "repair_success" if selected_delta["lcs_ratio"] > 0.0 else "repair_corruption"
    if selected_delta["lcs_ratio"] < 0.0:
        return "repair_corruption"
    if oracle_delta["lcs_ratio"] > selected_delta["lcs_ratio"]:
        return "scoring_misranking"
    return "selection_aligned_or_metric_tie"


def _metric_delta_from_identity(candidate: Optional[dict], identity: dict) -> dict:
    if not candidate:
        return _zero_delta()
    candidate_metrics = candidate.get("metrics", {})
    identity_metrics = identity.get("metrics", {})
    return {
        "lcs_ratio": round(float(candidate_metrics.get("lcs_ratio", 0.0)) - float(identity_metrics.get("lcs_ratio", 0.0)), 8),
        "set_f1": round(float(candidate_metrics.get("set_f1", 0.0)) - float(identity_metrics.get("set_f1", 0.0)), 8),
        "token_accuracy": round(float(candidate_metrics.get("token_accuracy", 0.0)) - float(identity_metrics.get("token_accuracy", 0.0)), 8),
    }


def _oracle_modified_decomposition(rescored: Sequence[dict]) -> Optional[dict]:
    modified = [row for row in rescored if row["is_modified"]]
    if not modified:
        return None
    return max(
        modified,
        key=lambda row: (
            float(row.get("metrics", {}).get("lcs_ratio", 0.0)),
            float(row.get("metrics", {}).get("token_accuracy", 0.0)),
            float(row.get("metrics", {}).get("set_f1", 0.0)),
            -float(row.get("raw_terms", {}).get("edit_penalty", 0.0)),
        ),
    )


def _identity_decomposition(sample: dict, rescored: Sequence[dict]) -> dict:
    identity_tokens = [int(token) for token in sample.get("identity_tokens", [])]
    for row in rescored:
        if row["candidate_kind"] == "identity":
            return row
    if identity_tokens:
        for row in rescored:
            if row["tokens"] == identity_tokens:
                return row
    return rescored[0] if rescored else {
        "tokens": identity_tokens,
        "candidate_kind": "identity",
        "is_modified": False,
        "ablated_score": 0.0,
        "metrics": {"lcs_ratio": 0.0, "set_f1": 0.0, "token_accuracy": 0.0},
        "raw_terms": {},
        "weighted_terms": {},
    }


def _operation_edit_weight(candidate: dict, policy: dict) -> float:
    operation_weights = {str(key): float(value) for key, value in (policy.get("operation_edit_penalties") or {}).items()}
    kind = _candidate_kind(candidate)
    if kind in operation_weights:
        return operation_weights[kind]
    return float(_policy_weights(policy).get("edit_penalty", 0.0))


def _policy_weights(policy: dict) -> dict:
    weights = dict(DEFAULT_SCORE_WEIGHTS)
    weights.update({str(key): float(value) for key, value in (policy.get("weights") or {}).items()})
    return weights


def _strip_policy_details(row: dict) -> dict:
    return {
        key: value
        for key, value in row.items()
        if key
        in {
            "description",
            "sample_count",
            "repair_adoption_count",
            "repair_adoption_rate",
            "corruption_count",
            "corruption_rate",
            "mean_lcs_gain",
            "mean_set_f1_gain",
            "mean_token_accuracy_gain",
            "positive_lcs_selection_rate",
            "selected_candidate_kind_counts",
            "failure_counts",
            "oracle_repair_ceiling",
            "weights",
            "operation_edit_penalties",
        }
    }


def _empty_policy_selection(sample: dict, policy: dict) -> dict:
    return {
        "local_index": sample.get("local_index"),
        "source_test_index": sample.get("source_test_index"),
        "task_type": sample.get("task_type"),
        "policy_name": str(policy.get("name", "unnamed_policy")),
        "selected_candidate_kind": "empty",
        "selected_tokens": [],
        "selected_score": 0.0,
        "selected_metric_delta": _zero_delta(),
        "identity_score": 0.0,
        "oracle_candidate_kind": None,
        "oracle_metric_delta": _zero_delta(),
        "failure_category": "empty_candidate_pool",
        "candidate_decompositions": [],
    }


def _sample_candidates(sample: dict) -> list[dict]:
    candidates = sample.get("repair_candidate_pool") or sample.get("top_repair_candidates") or []
    return [row for row in candidates if isinstance(row, dict)]


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


def _is_modified_candidate(candidate: dict) -> bool:
    return _is_modified_kind(_candidate_kind(candidate)) or float(candidate.get("edit_distance_from_retrieval", candidate.get("edit_distance_from_source", 0.0)) or 0.0) > 0.0


def _is_modified_kind(kind: Optional[str]) -> bool:
    return str(kind or "unknown") not in {"identity", "unknown", "empty"}


def _candidate_kind(candidate: dict) -> str:
    return str(candidate.get("repair_operation") or candidate.get("candidate_kind") or candidate.get("repair_kind") or "unknown")


def _candidate_metrics(candidate: dict) -> dict:
    attribution = candidate.get("repair_attribution") or {}
    metrics = attribution.get("candidate_metrics") or candidate.get("metrics") or {}
    return {
        "lcs_ratio": float(metrics.get("lcs_ratio", 0.0) or 0.0),
        "set_f1": float(metrics.get("set_f1", 0.0) or 0.0),
        "token_accuracy": float(metrics.get("token_accuracy", 0.0) or 0.0),
    }


def _candidate_delta(candidate: dict) -> dict:
    attribution = candidate.get("repair_attribution") or {}
    return {
        "lcs_ratio": float(attribution.get("lcs_delta", 0.0) or 0.0),
        "set_f1": float(attribution.get("set_f1_delta", 0.0) or 0.0),
        "token_accuracy": float(attribution.get("token_accuracy_delta", 0.0) or 0.0),
    }


def _mean_metric_rows(rows: Sequence[dict]) -> dict:
    return {
        "lcs_ratio": round(_mean(row.get("lcs_ratio", 0.0) for row in rows), 8),
        "set_f1": round(_mean(row.get("set_f1", 0.0) for row in rows), 8),
        "token_accuracy": round(_mean(row.get("token_accuracy", 0.0) for row in rows), 8),
    }


def _zero_delta() -> dict:
    return {"lcs_ratio": 0.0, "set_f1": 0.0, "token_accuracy": 0.0}


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


def _write_markdown(path: Path, report: dict, ablations: dict, failure_breakdown: dict, threshold_report: dict) -> None:
    recommendation = report.get("recommendation", {})
    lines = [
        "# Repair Scorer Ablations",
        "",
        "Evaluation-only re-scoring of existing repair candidate pools. No model training, checkpoint loading, or architecture changes are performed.",
        "",
        f"Samples: `{report.get('sample_count')}`",
        f"Recommended policy: `{recommendation.get('recommended_policy')}`",
        f"Recommendation basis: `{recommendation.get('basis')}`",
        "",
        "## Policy Results",
        "",
        "| Policy | Adoption | Corruption | Mean LCS Gain | Mean SetF1 Gain | Mean Token Gain |",
        "| --- | ---: | ---: | ---: | ---: | ---: |",
    ]
    for name, row in ablations.get("policies", {}).items():
        lines.append(
            f"| `{name}` | {row.get('repair_adoption_rate')} | {row.get('corruption_rate')} | "
            f"{row.get('mean_lcs_gain')} | {row.get('mean_set_f1_gain')} | {row.get('mean_token_accuracy_gain')} |"
        )
    lines.extend(
        [
            "",
            "## Recommendation",
            "",
            "```json",
            json.dumps(recommendation, ensure_ascii=False, indent=2),
            "```",
            "",
            "## Baseline Failure Breakdown",
            "",
            "```json",
            json.dumps(
                {
                    "failure_counts": failure_breakdown.get("failure_counts", {}),
                    "failure_rates": failure_breakdown.get("failure_rates", {}),
                },
                ensure_ascii=False,
                indent=2,
            ),
            "```",
            "",
            "## Threshold Sweep",
            "",
            "```json",
            json.dumps(threshold_report.get("policies", {}), ensure_ascii=False, indent=2),
            "```",
            "",
            "Generation contribution is zero in this phase; these are scorer diagnostics over existing retrieval/local-repair candidates.",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _build_parser() -> argparse.ArgumentParser:
    oracle_dir = OUTPUT_DIR / "v5_final_reports" / "repair_oracle_phase"
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate-traces", type=Path, default=oracle_dir / "repair_candidate_traces.json")
    parser.add_argument("--oracle-report", type=Path, default=oracle_dir / "repair_oracle_report.json")
    parser.add_argument("--output-dir", type=Path, default=OUTPUT_DIR / "v5_final_reports" / "repair_scorer_ablations")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--dry-run", action="store_true")
    return parser


def main(argv: Optional[list[str]] = None) -> dict:
    args = _build_parser().parse_args(argv)
    report = evaluate_repair_scorer_ablations(
        candidate_traces_path=args.candidate_traces,
        output_dir=args.output_dir,
        oracle_report_path=args.oracle_report,
        seed=args.seed,
        dry_run=args.dry_run,
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return report


if __name__ == "__main__":
    main()
