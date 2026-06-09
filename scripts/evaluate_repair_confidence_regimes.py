#!/usr/bin/env python3
"""Evaluation-only high-confidence repair regime discovery.

This phase searches for narrow local-repair subspaces with low corruption and
stable positive metric deltas. It consumes persisted repair candidate traces
only. It does not train, load or mutate checkpoints, change architecture,
change production scoring, generate candidates, or redesign retrieval.
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
from typing import Callable, Optional, Sequence


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from gis_recommend.config.transformer_config import OUTPUT_DIR  # noqa: E402


SCHEMA_VERSION = "gis_recommend.v5_final.repair_confidence_regimes.v1"
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


def build_candidate_rows(
    samples: Sequence[dict],
    *,
    token_family_map: Optional[dict[int, str]] = None,
    token_frequency_map: Optional[dict[int, float]] = None,
    transition_matrix: Optional[dict] = None,
) -> list[dict]:
    """Flatten persisted repair traces into candidate-level diagnostic rows."""

    rows: list[dict] = []
    families = token_family_map or {}
    frequencies = token_frequency_map or {}
    transitions = transition_matrix or {}
    for sample_index, sample in enumerate(samples):
        candidates = _candidate_pool(sample)
        if not candidates:
            continue
        identity = _identity_candidate(sample, candidates)
        identity_tokens = _int_list(identity.get("tokens") or sample.get("identity_tokens") or [])
        reference_tokens = _int_list(sample.get("reference_tokens") or [])
        identity_metrics = _metrics(identity, reference_tokens)
        identity_io = _candidate_io(identity)
        identity_invalid = _invalid_transition_rate(identity_tokens, transitions)
        identity_score = _candidate_score(identity)
        retrieval_pool = _retrieval_pool(sample)
        retrieval_gap = _retrieval_similarity_gap(retrieval_pool)
        predicted_tokens = _predicted_tokens(sample)
        task_type = str(sample.get("task_type") or "unknown")
        workflow_length = len(identity_tokens)

        for rank, candidate in enumerate(candidates):
            candidate_tokens = _int_list(candidate.get("tokens") or [])
            kind = _candidate_kind(candidate)
            edit_distance = _edit_distance(candidate, identity_tokens, candidate_tokens)
            is_modified = _is_modified(candidate, kind, edit_distance)
            candidate_metrics = _metrics(candidate, reference_tokens)
            delta = _metric_delta(candidate_metrics, identity_metrics)
            candidate_io = _candidate_io(candidate)
            candidate_invalid = _invalid_transition_rate(candidate_tokens, transitions)
            detail = candidate.get("edit_detail") or {}
            involved = _involved_tokens(kind, identity_tokens, candidate_tokens, detail)
            rarity = _rarity_bin(involved, frequencies)
            family_substitution = _operator_family_substitution(kind, identity_tokens, candidate_tokens, families)
            row = {
                "sample_id": int(sample.get("local_index", sample_index) or sample_index),
                "source_test_index": sample.get("source_test_index"),
                "task_type": task_type,
                "candidate_rank": int(candidate.get("rank", rank) or 0),
                "repair_subtype": kind,
                "is_modified": bool(is_modified),
                "tokens": candidate_tokens,
                "identity_tokens": identity_tokens,
                "reference_tokens": reference_tokens,
                "edit_distance": round(float(edit_distance), 8),
                "multi_edit": bool(edit_distance > 1.0),
                "length_preserving": len(candidate_tokens) == len(identity_tokens),
                "io_preserving": candidate_io >= identity_io,
                "execution_preserving": candidate_io >= identity_io and candidate_invalid <= identity_invalid,
                "operator_family_substitution": bool(family_substitution),
                "operator_rarity_bin": rarity,
                "boundary_transition_edit": _boundary_edit(detail, workflow_length),
                "workflow_length": workflow_length,
                "workflow_length_bin": _length_bin(workflow_length),
                "retrieval_similarity_gap": round(retrieval_gap, 8),
                "retrieval_gap_bin": _gap_bin(retrieval_gap),
                "local_operator_disagreement": _set_distance(candidate_tokens, identity_tokens),
                "local_operator_disagreement_bin": _magnitude_bin(_set_distance(candidate_tokens, identity_tokens)),
                "set_disagreement_magnitude": _predicted_set_disagreement(candidate_tokens, predicted_tokens),
                "set_disagreement_bin": _magnitude_bin(_predicted_set_disagreement(candidate_tokens, predicted_tokens)),
                "candidate_score": _candidate_score(candidate),
                "identity_score": identity_score,
                "score_margin_vs_identity": round(_candidate_score(candidate) - identity_score, 8),
                "set_agreement": _set_agreement(candidate),
                "v5_plausibility": _v5_plausibility(candidate),
                "lcs_retention": _lcs_retention(candidate, identity_tokens, candidate_tokens),
                "io_validity": candidate_io,
                "identity_io_validity": identity_io,
                "invalid_transition_rate": candidate_invalid,
                "identity_invalid_transition_rate": identity_invalid,
                "lcs_delta": delta["lcs_ratio"],
                "set_f1_delta": delta["set_f1"],
                "token_accuracy_delta": delta["token_accuracy"],
                "repair_success": bool(delta["lcs_ratio"] > 0.0),
                "repair_harmful": bool(delta["lcs_ratio"] < 0.0),
                "runtime_safe_features_only": True,
            }
            rows.append(row)
    return rows


def summarize_repair_subtypes(candidate_rows: Sequence[dict]) -> dict:
    """Break candidate outcomes down by subtype and runtime-safe attributes."""

    modified = [row for row in candidate_rows if row.get("is_modified")]
    by_subtype = _summaries_by_key(modified, "repair_subtype")
    attributes = {
        "substitution": lambda row: row.get("repair_subtype") == "operator_substitution",
        "insertion": lambda row: "insertion" in str(row.get("repair_subtype")),
        "deletion": lambda row: row.get("repair_subtype") == "operator_deletion",
        "bridge_insertion": lambda row: row.get("repair_subtype") == "bridge_insertion",
        "multi_edit": lambda row: bool(row.get("multi_edit")),
        "operator_family_substitution": lambda row: bool(row.get("operator_family_substitution")),
        "io_preserving": lambda row: bool(row.get("io_preserving")),
        "length_preserving": lambda row: bool(row.get("length_preserving")),
        "execution_preserving": lambda row: bool(row.get("execution_preserving")),
    }
    return {
        "schema_version": f"{SCHEMA_VERSION}.subtypes",
        "candidate_count": len(candidate_rows),
        "modified_candidate_count": len(modified),
        "by_repair_subtype": by_subtype,
        "by_attribute": {name: _candidate_group_summary([row for row in modified if predicate(row)]) for name, predicate in attributes.items()},
    }


def analyze_local_context(candidate_rows: Sequence[dict]) -> dict:
    """Measure repair outcomes conditioned on local runtime-observable context."""

    modified = [row for row in candidate_rows if row.get("is_modified")]
    return {
        "schema_version": f"{SCHEMA_VERSION}.context",
        "candidate_count": len(candidate_rows),
        "modified_candidate_count": len(modified),
        "by_retrieval_gap": _summaries_by_key(modified, "retrieval_gap_bin"),
        "by_local_operator_disagreement": _summaries_by_key(modified, "local_operator_disagreement_bin"),
        "by_boundary_transition": _summaries_by_key(modified, "boundary_transition_edit"),
        "by_operator_rarity": _summaries_by_key(modified, "operator_rarity_bin"),
        "by_workflow_length": _summaries_by_key(modified, "workflow_length_bin"),
        "by_task_family": _summaries_by_key(modified, "task_type"),
        "by_edit_distance": _summaries_by_key(modified, "edit_distance"),
        "by_set_disagreement": _summaries_by_key(modified, "set_disagreement_bin"),
    }


def search_precision_first_regimes(
    candidate_rows: Sequence[dict],
    *,
    sample_count: int,
    bootstrap_iterations: int = 500,
    seed: int = 42,
    min_sample_count: int = 10,
) -> dict:
    """Search runtime-safe, precision-first repair candidate regimes."""

    specs = _regime_specs(candidate_rows)
    regimes = []
    for offset, spec in enumerate(specs):
        matched = [row for row in candidate_rows if row.get("is_modified") and spec["predicate"](row)]
        if not matched:
            continue
        score_rows = _select_one_per_sample(matched, selector="score")
        oracle_rows = _select_one_per_sample(matched, selector="oracle")
        score_summary = _selection_summary(score_rows, sample_count=sample_count)
        oracle_summary = _selection_summary(oracle_rows, sample_count=sample_count)
        score_summary["bootstrap_intervals"] = _bootstrap_selection_intervals(
            score_rows,
            sample_count=sample_count,
            iterations=bootstrap_iterations,
            seed=seed + offset,
        )
        oracle_summary["bootstrap_intervals"] = _bootstrap_selection_intervals(
            oracle_rows,
            sample_count=sample_count,
            iterations=bootstrap_iterations,
            seed=seed + 1000 + offset,
        )
        score_pass = _meets_high_confidence(score_summary, min_sample_count=min_sample_count)
        oracle_pass = _meets_high_confidence(oracle_summary, min_sample_count=min_sample_count)
        regimes.append(
            {
                "name": spec["name"],
                "description": spec["description"],
                "runtime_safe_features_only": True,
                "matched_candidate_count": len(matched),
                "score_selected": score_summary,
                "oracle_selected": oracle_summary,
                "meets_high_confidence_contract": bool(score_pass),
                "oracle_subspace_meets_contract": bool(oracle_pass),
            }
        )
    regimes.sort(
        key=lambda row: (
            not row["meets_high_confidence_contract"],
            -float(row["score_selected"].get("mean_lcs_delta", 0.0)),
            float(row["score_selected"].get("corruption_rate", 0.0)),
            -int(row["score_selected"].get("trigger_sample_count", 0)),
        )
    )
    return {
        "schema_version": f"{SCHEMA_VERSION}.precision_first",
        "sample_count": int(sample_count),
        "min_sample_count": int(min_sample_count),
        "objective": "precision_first_low_corruption_not_coverage",
        "criteria": {
            "corruption_rate_max": 0.02,
            "mean_lcs_delta": "positive",
            "mean_token_accuracy_delta": "positive",
            "conditional_lcs_bootstrap_ci_lower": "above_zero",
            "nontrivial_sample_count": int(min_sample_count),
        },
        "regimes": regimes,
        "passing_score_selected_regimes": [row["name"] for row in regimes if row["meets_high_confidence_contract"]],
        "passing_oracle_subspaces": [row["name"] for row in regimes if row["oracle_subspace_meets_contract"]],
    }


def bootstrap_regime_validation(precision_report: dict) -> dict:
    """Extract bootstrap validation status for discovered regimes."""

    rows = []
    for regime in precision_report.get("regimes", []):
        score = regime.get("score_selected", {})
        intervals = score.get("bootstrap_intervals", {})
        rows.append(
            {
                "name": regime.get("name"),
                "meets_high_confidence_contract": regime.get("meets_high_confidence_contract"),
                "oracle_subspace_meets_contract": regime.get("oracle_subspace_meets_contract"),
                "trigger_sample_count": score.get("trigger_sample_count"),
                "corruption_rate": score.get("corruption_rate"),
                "mean_lcs_delta": score.get("mean_lcs_delta"),
                "mean_token_accuracy_delta": score.get("mean_token_accuracy_delta"),
                "conditional_lcs_ci": intervals.get("conditional_mean_lcs_delta", {}),
                "overall_lcs_ci": intervals.get("mean_lcs_delta", {}),
            }
        )
    return {
        "schema_version": f"{SCHEMA_VERSION}.bootstrap_validation",
        "sample_count": precision_report.get("sample_count"),
        "score_selected_pass_count": sum(1 for row in rows if row.get("meets_high_confidence_contract")),
        "oracle_subspace_pass_count": sum(1 for row in rows if row.get("oracle_subspace_meets_contract")),
        "rows": rows,
        "interpretation_boundary": "A passing oracle subspace is candidate-existence evidence only; it is not a deployable runtime repair policy unless score-selected criteria also pass.",
    }


def random_control_comparison(
    candidate_rows: Sequence[dict],
    *,
    sample_count: int,
    iterations: int = 200,
    seed: int = 42,
) -> dict:
    """Compare discovered regimes against random modified and random narrow gates."""

    rng = random.Random(int(seed))
    modified = [row for row in candidate_rows if row.get("is_modified")]
    by_sample = _group_by_sample(modified)
    kinds = sorted({str(row.get("repair_subtype")) for row in modified})

    modified_runs = []
    narrow_runs = []
    edit_type_runs = []
    sample_ids = list(range(int(sample_count)))
    for _ in range(int(iterations)):
        selected = [rng.choice(rows) for rows in by_sample.values() if rows]
        modified_runs.append(_selection_summary(selected, sample_count=sample_count))

        keep_count = max(1, int(round(0.10 * max(sample_count, 1))))
        gated_ids = set(rng.sample(sample_ids, min(keep_count, len(sample_ids))))
        gated = [rng.choice(rows) for sample_id, rows in by_sample.items() if sample_id in gated_ids and rows]
        narrow_runs.append(_selection_summary(gated, sample_count=sample_count))

        kind = rng.choice(kinds) if kinds else "none"
        kind_rows = [row for row in modified if row.get("repair_subtype") == kind]
        kind_by_sample = _group_by_sample(kind_rows)
        picked = [rng.choice(rows) for rows in kind_by_sample.values() if rows]
        edit_type_runs.append({**_selection_summary(picked, sample_count=sample_count), "edit_type": kind})

    return {
        "schema_version": f"{SCHEMA_VERSION}.random_controls",
        "iterations": int(iterations),
        "sample_count": int(sample_count),
        "random_modified_selection": _control_summary(modified_runs),
        "random_narrow_gating": _control_summary(narrow_runs),
        "random_edit_type_gating": _control_summary(edit_type_runs),
        "note": "Random controls are evaluation-only baselines; they do not update scorer state or production behavior.",
    }


def evaluate_repair_confidence_regimes(
    *,
    candidate_traces_path: Path,
    output_dir: Path,
    hierarchy_path: Optional[Path] = None,
    id_mappings_path: Optional[Path] = None,
    transition_matrix_path: Optional[Path] = None,
    bootstrap_iterations: int = 500,
    random_iterations: int = 200,
    min_sample_count: int = 10,
    seed: int = 42,
    dry_run: bool = False,
) -> dict:
    """Run the full evaluation-only confidence-regime analysis phase."""

    traces = _load_json(candidate_traces_path)
    samples = traces.get("samples", [])
    if not isinstance(samples, list):
        raise ValueError(f"Invalid candidate trace payload: {candidate_traces_path}")
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

    family_map, frequency_map = _load_hierarchy_maps(hierarchy_path, id_mappings_path)
    transition_matrix = _load_json(transition_matrix_path) if transition_matrix_path and transition_matrix_path.exists() else {}
    candidate_rows = build_candidate_rows(
        samples,
        token_family_map=family_map,
        token_frequency_map=frequency_map,
        transition_matrix=transition_matrix,
    )
    subtype_stats = summarize_repair_subtypes(candidate_rows)
    context = analyze_local_context(candidate_rows)
    precision = search_precision_first_regimes(
        candidate_rows,
        sample_count=len(samples),
        bootstrap_iterations=bootstrap_iterations,
        seed=seed,
        min_sample_count=min_sample_count,
    )
    bootstrap_validation = bootstrap_regime_validation(precision)
    controls = random_control_comparison(
        candidate_rows,
        sample_count=len(samples),
        iterations=random_iterations,
        seed=seed,
    )
    passing = precision.get("passing_score_selected_regimes", [])
    oracle_only = [
        name
        for name in precision.get("passing_oracle_subspaces", [])
        if name not in set(passing)
    ]
    report = {
        "schema_version": SCHEMA_VERSION,
        "created_at": created_at,
        "dry_run": False,
        "candidate_traces": str(candidate_traces_path),
        "sample_count": len(samples),
        "candidate_count": len(candidate_rows),
        "modified_candidate_count": sum(1 for row in candidate_rows if row.get("is_modified")),
        "summary": {
            "score_selected_high_confidence_regime_count": len(passing),
            "oracle_only_high_confidence_subspace_count": len(oracle_only),
            "stable_runtime_repair_policy_exists": bool(passing),
            "repair_opportunity_exists": bool(precision.get("passing_oracle_subspaces")),
            "interpretation": (
                "narrow_score_selected_regime_found"
                if passing
                else "no_stable_runtime_repair_policy_found_under_current_score_selection"
            ),
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
            "production_scorer_changed": False,
            "graph_learning": False,
        },
        "interpretation_boundaries": [
            "Repair opportunity exists is separate from stable runtime repair policy exists.",
            "Oracle-selected subspaces are not deployable policy evidence.",
            "Selective success must not be inflated into global repair capability.",
            "All predicates are diagnostics over persisted traces; production scoring is unchanged.",
        ],
    }
    scan = forbidden_pattern_scan([Path(__file__).relative_to(ROOT), Path("tests") / "test_repair_confidence_regimes.py"])

    _write_json(output_dir / "repair_confidence_regime_report.json", report)
    _write_json(output_dir / "repair_subtype_statistics.json", subtype_stats)
    _write_json(output_dir / "repair_context_analysis.json", context)
    _write_json(output_dir / "precision_first_regimes.json", precision)
    _write_json(output_dir / "bootstrap_regime_validation.json", bootstrap_validation)
    _write_json(output_dir / "random_control_comparison.json", controls)
    _write_json(output_dir / "forbidden_pattern_scan_confidence_regimes.json", scan)
    _write_markdown(output_dir / "summary.md", report, precision, bootstrap_validation, controls)
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


def _regime_specs(candidate_rows: Sequence[dict]) -> list[dict]:
    specs: list[dict] = [
        _spec("kind_operator_substitution", "Operator substitutions only.", lambda row: row["repair_subtype"] == "operator_substitution"),
        _spec("kind_bridge_insertion", "Bridge insertions only.", lambda row: row["repair_subtype"] == "bridge_insertion"),
        _spec("kind_operator_deletion", "Operator deletions only.", lambda row: row["repair_subtype"] == "operator_deletion"),
        _spec("kind_local_swap", "Local swaps only.", lambda row: row["repair_subtype"] == "local_swap"),
        _spec("edit_distance_1", "Single-edit modified candidates.", lambda row: row["edit_distance"] <= 1.0),
        _spec("length_preserving", "Length-preserving repairs.", lambda row: row["length_preserving"]),
        _spec("io_preserving", "IO-preserving repairs.", lambda row: row["io_preserving"]),
        _spec("execution_preserving", "Execution-preserving repairs.", lambda row: row["execution_preserving"]),
        _spec("operator_family_substitution", "Substitutions within the same L2 family.", lambda row: row["operator_family_substitution"]),
        _spec("rare_operator_involved", "Repairs touching at least one rare operator.", lambda row: row["operator_rarity_bin"] == "rare"),
        _spec("high_set_agreement", "Candidate set agreement >= 0.75.", lambda row: row["set_agreement"] >= 0.75),
        _spec("high_v5_plausibility", "Candidate V5 plausibility >= 0.50.", lambda row: row["v5_plausibility"] >= 0.50),
        _spec("high_set_and_v5", "Set agreement >= 0.75 and V5 plausibility >= 0.50.", lambda row: row["set_agreement"] >= 0.75 and row["v5_plausibility"] >= 0.50),
        _spec("high_lcs_retention", "Repair retains at least 90% LCS against identity.", lambda row: row["lcs_retention"] >= 0.90),
        _spec("length_preserving_high_set", "Length-preserving repairs with high set agreement.", lambda row: row["length_preserving"] and row["set_agreement"] >= 0.75),
        _spec("same_family_high_set", "Same-family substitutions with high set agreement.", lambda row: row["operator_family_substitution"] and row["set_agreement"] >= 0.75),
        _spec("tight_retrieval_gap", "Top1/top2 retrieval gap <= 0.05.", lambda row: row["retrieval_gap_bin"] == "tight"),
        _spec("wide_retrieval_gap", "Top1/top2 retrieval gap > 0.15.", lambda row: row["retrieval_gap_bin"] == "wide"),
        _spec("low_set_disagreement", "Low disagreement with predicted operator set.", lambda row: row["set_disagreement_bin"] == "low"),
        _spec("boundary_edit", "Edit occurs near sequence boundary.", lambda row: row["boundary_transition_edit"]),
        _spec("short_workflow", "Identity workflow length <= 5.", lambda row: row["workflow_length_bin"] == "short"),
        _spec("medium_workflow", "Identity workflow length 6-12.", lambda row: row["workflow_length_bin"] == "medium"),
        _spec("long_workflow", "Identity workflow length > 12.", lambda row: row["workflow_length_bin"] == "long"),
    ]
    task_counts = Counter(str(row.get("task_type") or "unknown") for row in candidate_rows if row.get("is_modified"))
    for task, count in sorted(task_counts.items()):
        if count >= 5:
            specs.append(_spec(f"task_{_slug(task)}", f"Task family `{task}`.", lambda row, task=task: row.get("task_type") == task))
    return specs


def _spec(name: str, description: str, predicate: Callable[[dict], bool]) -> dict:
    return {"name": name, "description": description, "predicate": predicate}


def _select_one_per_sample(rows: Sequence[dict], *, selector: str) -> list[dict]:
    grouped = _group_by_sample(rows)
    selected = []
    for group in grouped.values():
        if selector == "oracle":
            selected.append(
                max(
                    group,
                    key=lambda row: (
                        float(row.get("lcs_delta", 0.0)),
                        float(row.get("token_accuracy_delta", 0.0)),
                        float(row.get("set_f1_delta", 0.0)),
                        -float(row.get("edit_distance", 0.0)),
                    ),
                )
            )
        else:
            selected.append(
                max(
                    group,
                    key=lambda row: (
                        float(row.get("candidate_score", 0.0)),
                        float(row.get("v5_plausibility", 0.0)),
                        float(row.get("set_agreement", 0.0)),
                        -float(row.get("edit_distance", 0.0)),
                        -int(row.get("candidate_rank", 999999)),
                    ),
                )
            )
    return selected


def _selection_summary(selected_rows: Sequence[dict], *, sample_count: int) -> dict:
    triggered = len(selected_rows)
    lcs_values = [float(row.get("lcs_delta", 0.0) or 0.0) for row in selected_rows]
    set_values = [float(row.get("set_f1_delta", 0.0) or 0.0) for row in selected_rows]
    token_values = [float(row.get("token_accuracy_delta", 0.0) or 0.0) for row in selected_rows]
    kind_counts = Counter(str(row.get("repair_subtype") or "unknown") for row in selected_rows)
    return {
        "trigger_sample_count": triggered,
        "adoption_rate": _rate(triggered, sample_count),
        "corruption_count": sum(1 for value in lcs_values if value < 0.0),
        "corruption_rate": _rate(sum(1 for value in lcs_values if value < 0.0), triggered),
        "repair_precision": _rate(sum(1 for value in lcs_values if value > 0.0), triggered),
        "mean_lcs_delta": round(_mean([*lcs_values, *([0.0] * max(sample_count - triggered, 0))]), 8),
        "mean_set_f1_delta": round(_mean([*set_values, *([0.0] * max(sample_count - triggered, 0))]), 8),
        "mean_token_accuracy_delta": round(_mean([*token_values, *([0.0] * max(sample_count - triggered, 0))]), 8),
        "conditional_mean_lcs_delta": round(_mean(lcs_values), 8),
        "conditional_mean_set_f1_delta": round(_mean(set_values), 8),
        "conditional_mean_token_accuracy_delta": round(_mean(token_values), 8),
        "selected_candidate_kind_counts": dict(sorted(kind_counts.items())),
        "selection_entropy": _selection_entropy(kind_counts),
    }


def _bootstrap_selection_intervals(
    selected_rows: Sequence[dict],
    *,
    sample_count: int,
    iterations: int,
    seed: int,
) -> dict:
    if not selected_rows or iterations <= 0:
        empty = {"lower": 0.0, "median": 0.0, "upper": 0.0}
        return {
            "bootstrap_iterations": int(iterations),
            "mean_lcs_delta": empty,
            "mean_token_accuracy_delta": empty,
            "conditional_mean_lcs_delta": empty,
            "conditional_mean_token_accuracy_delta": empty,
        }
    rng = random.Random(int(seed))
    rows = list(selected_rows)
    overall_lcs = []
    overall_token = []
    conditional_lcs = []
    conditional_token = []
    for _ in range(int(iterations)):
        sample = [rows[rng.randrange(len(rows))] for _ in rows]
        summary = _selection_summary(sample, sample_count=sample_count)
        overall_lcs.append(summary["mean_lcs_delta"])
        overall_token.append(summary["mean_token_accuracy_delta"])
        conditional_lcs.append(summary["conditional_mean_lcs_delta"])
        conditional_token.append(summary["conditional_mean_token_accuracy_delta"])
    return {
        "bootstrap_iterations": int(iterations),
        "mean_lcs_delta": _interval(overall_lcs),
        "mean_token_accuracy_delta": _interval(overall_token),
        "conditional_mean_lcs_delta": _interval(conditional_lcs),
        "conditional_mean_token_accuracy_delta": _interval(conditional_token),
    }


def _meets_high_confidence(summary: dict, *, min_sample_count: int) -> bool:
    intervals = summary.get("bootstrap_intervals", {})
    lcs_ci = intervals.get("conditional_mean_lcs_delta", {})
    token_ci = intervals.get("conditional_mean_token_accuracy_delta", {})
    return (
        int(summary.get("trigger_sample_count", 0) or 0) >= int(min_sample_count)
        and float(summary.get("corruption_rate", 0.0) or 0.0) <= 0.02
        and float(summary.get("mean_lcs_delta", 0.0) or 0.0) > 0.0
        and float(summary.get("mean_token_accuracy_delta", 0.0) or 0.0) > 0.0
        and float(lcs_ci.get("lower", 0.0) or 0.0) > 0.0
        and float(token_ci.get("lower", 0.0) or 0.0) > 0.0
    )


def _control_summary(runs: Sequence[dict]) -> dict:
    return {
        "run_count": len(runs),
        "adoption_rate": _interval([row.get("adoption_rate", 0.0) for row in runs]),
        "corruption_rate": _interval([row.get("corruption_rate", 0.0) for row in runs]),
        "mean_lcs_delta": _interval([row.get("mean_lcs_delta", 0.0) for row in runs]),
        "mean_token_accuracy_delta": _interval([row.get("mean_token_accuracy_delta", 0.0) for row in runs]),
    }


def _summaries_by_key(rows: Sequence[dict], key: str) -> dict:
    grouped: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        grouped[str(row.get(key))].append(row)
    return {name: _candidate_group_summary(group) for name, group in sorted(grouped.items())}


def _candidate_group_summary(rows: Sequence[dict]) -> dict:
    lcs = [float(row.get("lcs_delta", 0.0) or 0.0) for row in rows]
    token = [float(row.get("token_accuracy_delta", 0.0) or 0.0) for row in rows]
    set_f1 = [float(row.get("set_f1_delta", 0.0) or 0.0) for row in rows]
    return {
        "candidate_count": len(rows),
        "success_rate": _rate(sum(1 for value in lcs if value > 0.0), len(rows)),
        "corruption_rate": _rate(sum(1 for value in lcs if value < 0.0), len(rows)),
        "mean_lcs_delta": round(_mean(lcs), 8),
        "mean_set_f1_delta": round(_mean(set_f1), 8),
        "mean_token_accuracy_delta": round(_mean(token), 8),
    }


def _candidate_pool(sample: dict) -> list[dict]:
    rows = sample.get("repair_candidate_pool") or sample.get("top_repair_candidates") or []
    return [row for row in rows if isinstance(row, dict)]


def _retrieval_pool(sample: dict) -> list[dict]:
    rows = sample.get("retrieval_pool_top") or []
    return [row for row in rows if isinstance(row, dict)]


def _identity_candidate(sample: dict, candidates: Sequence[dict]) -> dict:
    identity_tokens = _int_list(sample.get("identity_tokens") or [])
    for row in candidates:
        if _candidate_kind(row) == "identity":
            return row
    for row in candidates:
        if _int_list(row.get("tokens") or []) == identity_tokens:
            return row
    return list(candidates)[0] if candidates else {"tokens": identity_tokens, "candidate_kind": "identity"}


def _candidate_kind(candidate: dict) -> str:
    return str(candidate.get("repair_operation") or candidate.get("candidate_kind") or candidate.get("repair_kind") or "unknown")


def _is_modified(candidate: dict, kind: str, edit_distance: float) -> bool:
    return kind not in {"identity", "unknown", "empty", "None"} or edit_distance > 0.0


def _metrics(candidate: dict, reference_tokens: Sequence[int]) -> dict:
    attribution = candidate.get("repair_attribution") or {}
    metrics = attribution.get("candidate_metrics") or candidate.get("metrics") or {}
    if metrics:
        return {
            "lcs_ratio": _float(metrics.get("lcs_ratio")),
            "set_f1": _float(metrics.get("set_f1")),
            "token_accuracy": _float(metrics.get("token_accuracy")),
        }
    return _simple_metrics(candidate.get("tokens") or [], reference_tokens)


def _metric_delta(candidate_metrics: dict, identity_metrics: dict) -> dict:
    return {
        "lcs_ratio": round(_float(candidate_metrics.get("lcs_ratio")) - _float(identity_metrics.get("lcs_ratio")), 8),
        "set_f1": round(_float(candidate_metrics.get("set_f1")) - _float(identity_metrics.get("set_f1")), 8),
        "token_accuracy": round(_float(candidate_metrics.get("token_accuracy")) - _float(identity_metrics.get("token_accuracy")), 8),
    }


def _simple_metrics(tokens: Sequence[int], reference_tokens: Sequence[int]) -> dict:
    pred = _int_list(tokens)
    ref = _int_list(reference_tokens)
    return {"lcs_ratio": _lcs_ratio(pred, ref), "set_f1": _set_f1(pred, ref), "token_accuracy": _token_accuracy(pred, ref)}


def _candidate_io(candidate: dict) -> float:
    features = candidate.get("execution_features") or {}
    return _float(candidate.get("io_validity", features.get("io_validity", 1.0)), 1.0)


def _candidate_score(candidate: dict) -> float:
    for key in ("hybrid_score", "execution_aware_score", "score", "retrieval_score"):
        if candidate.get(key) is not None:
            return _float(candidate.get(key))
    return 0.0


def _set_agreement(candidate: dict) -> float:
    features = candidate.get("execution_features") or {}
    set_filter = candidate.get("set_filter") or {}
    return _float(features.get("set_predictor_agreement", set_filter.get("set_predictor_agreement", 0.0)))


def _v5_plausibility(candidate: dict) -> float:
    features = candidate.get("execution_features") or {}
    v5_score = candidate.get("v5_score") or {}
    return _float(features.get("v5_plausibility", v5_score.get("v5_plausibility", 0.0)))


def _lcs_retention(candidate: dict, identity_tokens: Sequence[int], candidate_tokens: Sequence[int]) -> float:
    attribution = candidate.get("repair_attribution") or {}
    return round(_float(attribution.get("lcs_retention"), _lcs_ratio(candidate_tokens, identity_tokens)), 8)


def _edit_distance(candidate: dict, identity_tokens: Sequence[int], candidate_tokens: Sequence[int]) -> float:
    attribution = candidate.get("repair_attribution") or {}
    return _float(
        candidate.get(
            "edit_distance_from_retrieval",
            candidate.get("edit_distance_from_identity", attribution.get("edit_distance", _simple_edit_distance(identity_tokens, candidate_tokens))),
        )
    )


def _involved_tokens(kind: str, identity_tokens: Sequence[int], candidate_tokens: Sequence[int], detail: dict) -> list[int]:
    tokens: list[int] = []
    if detail.get("new_token") is not None:
        tokens.append(int(detail["new_token"]))
    position = detail.get("position")
    if position is not None and _is_int_like(position):
        pos = int(position)
        if 0 <= pos < len(identity_tokens):
            tokens.append(int(identity_tokens[pos]))
        if 0 <= pos < len(candidate_tokens):
            tokens.append(int(candidate_tokens[pos]))
    if kind == "local_swap":
        for key in ("left_position", "right_position"):
            pos = detail.get(key)
            if pos is not None and _is_int_like(pos) and 0 <= int(pos) < len(identity_tokens):
                tokens.append(int(identity_tokens[int(pos)]))
    if not tokens:
        tokens.extend(token for token in candidate_tokens if token not in set(identity_tokens))
    return sorted(set(tokens))


def _operator_family_substitution(kind: str, identity_tokens: Sequence[int], candidate_tokens: Sequence[int], token_family_map: dict[int, str]) -> bool:
    if kind != "operator_substitution" or len(identity_tokens) != len(candidate_tokens):
        return False
    diffs = [(old, new) for old, new in zip(identity_tokens, candidate_tokens) if old != new]
    if len(diffs) != 1:
        return False
    old, new = diffs[0]
    return bool(token_family_map.get(int(old)) and token_family_map.get(int(old)) == token_family_map.get(int(new)))


def _rarity_bin(tokens: Sequence[int], token_frequency_map: dict[int, float]) -> str:
    freqs = [float(token_frequency_map.get(int(token), 0.0) or 0.0) for token in tokens]
    if not freqs:
        return "unknown"
    minimum = min(freqs)
    if minimum <= 100:
        return "rare"
    if minimum <= 1000:
        return "mid"
    return "common"


def _boundary_edit(detail: dict, workflow_length: int) -> bool:
    positions = [detail.get("position"), detail.get("left_position"), detail.get("right_position")]
    clean = [int(value) for value in positions if value is not None and _is_int_like(value)]
    if not clean:
        return False
    return any(pos <= 1 or pos >= max(workflow_length - 2, 0) for pos in clean)


def _retrieval_similarity_gap(retrieval_pool: Sequence[dict]) -> float:
    scores = [_float(row.get("retrieval_score", row.get("score", 0.0))) for row in retrieval_pool]
    if not scores:
        return 0.0
    top1 = scores[0]
    top2 = scores[1] if len(scores) > 1 else 0.0
    return top1 - top2


def _predicted_tokens(sample: dict) -> list[int]:
    rows = (sample.get("set_prediction") or {}).get("top_tokens") or []
    return [int(row.get("token")) for row in rows if isinstance(row, dict) and row.get("token") is not None]


def _predicted_set_disagreement(candidate_tokens: Sequence[int], predicted_tokens: Sequence[int]) -> float:
    predicted = set(_int_list(predicted_tokens))
    if not predicted:
        return 1.0
    candidate = set(_int_list(candidate_tokens))
    return round(1.0 - (len(candidate & predicted) / max(len(predicted), 1)), 8)


def _gap_bin(value: float) -> str:
    if value <= 0.05:
        return "tight"
    if value <= 0.15:
        return "medium"
    return "wide"


def _magnitude_bin(value: float) -> str:
    if value <= 0.25:
        return "low"
    if value <= 0.50:
        return "medium"
    return "high"


def _length_bin(value: int) -> str:
    if value <= 5:
        return "short"
    if value <= 12:
        return "medium"
    return "long"


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


def _load_hierarchy_maps(hierarchy_path: Optional[Path], id_mappings_path: Optional[Path]) -> tuple[dict[int, str], dict[int, float]]:
    if not hierarchy_path or not id_mappings_path or not hierarchy_path.exists() or not id_mappings_path.exists():
        return {}, {}
    id_payload = _load_json(id_mappings_path)
    l3_map = id_payload.get("l3") or {}
    code_to_id = {str(code): int(value) for code, value in l3_map.items() if _is_int_like(value)}
    family_map: dict[int, str] = {}
    frequency_map: dict[int, float] = {}
    with Path(hierarchy_path).open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            code = str(row.get("l3_code") or "")
            if code not in code_to_id:
                continue
            token_id = code_to_id[code]
            family_map[token_id] = str(row.get("l2_code") or row.get("l1_code") or "")
            frequency_map[token_id] = _float(row.get("freq_v2", 0.0))
    return family_map, frequency_map


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


def _write_markdown(path: Path, report: dict, precision: dict, bootstrap_validation: dict, controls: dict) -> None:
    lines = [
        "# Repair Confidence Regimes",
        "",
        "Evaluation-only high-confidence repair regime discovery over existing local-repair traces. No training, checkpoint loading, checkpoint mutation, architecture changes, production scoring changes, learned calibration, graph learning, retrieval redesign, or generation redesign are performed.",
        "",
        f"Samples: `{report.get('sample_count')}`",
        f"Modified candidates: `{report.get('modified_candidate_count')}`",
        "",
        "## Summary",
        "",
        "```json",
        json.dumps(report.get("summary", {}), ensure_ascii=False, indent=2),
        "```",
        "",
        "## Passing Regimes",
        "",
        "```json",
        json.dumps(
            {
                "score_selected": precision.get("passing_score_selected_regimes", []),
                "oracle_subspaces": precision.get("passing_oracle_subspaces", []),
                "score_selected_pass_count": bootstrap_validation.get("score_selected_pass_count"),
                "oracle_subspace_pass_count": bootstrap_validation.get("oracle_subspace_pass_count"),
            },
            ensure_ascii=False,
            indent=2,
        ),
        "```",
        "",
        "## Random Controls",
        "",
        "```json",
        json.dumps(controls, ensure_ascii=False, indent=2),
        "```",
        "",
        "Interpretation boundary: repair opportunity exists is separate from stable runtime repair policy exists. Oracle subspaces are not deployable repair policies.",
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _group_by_sample(rows: Sequence[dict]) -> dict[int, list[dict]]:
    grouped: dict[int, list[dict]] = defaultdict(list)
    for row in rows:
        grouped[int(row.get("sample_id", 0) or 0)].append(row)
    return grouped


def _simple_edit_distance(a: Sequence[int], b: Sequence[int]) -> int:
    left = _int_list(a)
    right = _int_list(b)
    if len(left) == len(right):
        return sum(1 for x, y in zip(left, right) if x != y)
    return abs(len(left) - len(right)) + sum(1 for x, y in zip(left, right) if x != y)


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


def _set_distance(a: Sequence[int], b: Sequence[int]) -> float:
    left = set(_int_list(a))
    right = set(_int_list(b))
    if not left and not right:
        return 0.0
    return round(1.0 - (len(left & right) / max(len(left | right), 1)), 8)


def _selection_entropy(counts: Counter) -> float:
    total = sum(counts.values())
    if total <= 0:
        return 0.0
    probs = [count / total for count in counts.values() if count > 0]
    return round(-sum(prob * math.log(prob, 2) for prob in probs), 8)


def _interval(values: Sequence[float]) -> dict:
    rows = sorted(float(value) for value in values)
    if not rows:
        return {"lower": 0.0, "median": 0.0, "upper": 0.0}
    return {
        "lower": round(_quantile(rows, 0.025), 8),
        "median": round(_quantile(rows, 0.5), 8),
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


def _rate(numerator: int | float, denominator: int | float) -> float:
    return round(float(numerator) / max(float(denominator), 1.0), 8)


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


def _slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", value.lower()).strip("_") or "unknown"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _build_parser() -> argparse.ArgumentParser:
    default_traces = OUTPUT_DIR / "v5_final_reports" / "repair_oracle_phase_heldout_200" / "repair_candidate_traces.json"
    if not default_traces.exists():
        default_traces = OUTPUT_DIR / "v5_final_reports" / "repair_oracle_phase" / "repair_candidate_traces.json"
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate-traces", type=Path, default=default_traces)
    parser.add_argument("--output-dir", type=Path, default=OUTPUT_DIR / "v5_final_reports" / "repair_confidence_regimes")
    parser.add_argument("--hierarchy", type=Path, default=OUTPUT_DIR / "classification_hierarchy_v2.csv")
    parser.add_argument("--id-mappings", type=Path, default=OUTPUT_DIR / "id_mappings_v2.json")
    parser.add_argument("--transition-matrix", type=Path, default=OUTPUT_DIR / "transition_allowed_next.json")
    parser.add_argument("--bootstrap-iterations", type=int, default=500)
    parser.add_argument("--random-iterations", type=int, default=200)
    parser.add_argument("--min-sample-count", type=int, default=10)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--dry-run", action="store_true")
    return parser


def main(argv: Optional[list[str]] = None) -> dict:
    args = _build_parser().parse_args(argv)
    report = evaluate_repair_confidence_regimes(
        candidate_traces_path=args.candidate_traces,
        output_dir=args.output_dir,
        hierarchy_path=args.hierarchy,
        id_mappings_path=args.id_mappings,
        transition_matrix_path=args.transition_matrix,
        bootstrap_iterations=args.bootstrap_iterations,
        random_iterations=args.random_iterations,
        min_sample_count=args.min_sample_count,
        seed=args.seed,
        dry_run=args.dry_run,
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return report


if __name__ == "__main__":
    main()
