#!/usr/bin/env python3
"""Evaluation-only edit-penalty calibration sweep for local repair selection.

This script re-scores existing repair candidate traces. It does not train,
load checkpoints, mutate checkpoints, generate candidates, or modify planner
architecture.
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
from scripts.evaluate_repair_scorer_ablations import (  # noqa: E402
    DEFAULT_SCORE_WEIGHTS,
    select_candidate_under_policy,
)


SCHEMA_VERSION = "gis_recommend.v5_final.repair_calibration_sweep.v1"
DEFAULT_EDIT_PENALTIES = (0.0, 0.08, 0.10, 0.12, 0.14, 0.16, 0.20)
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


def run_calibration_sweep(
    samples: Sequence[dict],
    *,
    edit_penalties: Sequence[float] = DEFAULT_EDIT_PENALTIES,
    bootstrap_iterations: int = 500,
    seed: int = 42,
) -> dict:
    """Re-score samples under uniform edit penalties and summarize selection stability."""

    penalties = _normalized_penalties(edit_penalties)
    policy_results: dict[str, dict] = {}
    policy_rows: dict[str, list[dict]] = {}
    for offset, penalty in enumerate(penalties):
        policy = _uniform_edit_policy(penalty)
        rows = [select_candidate_under_policy(sample, policy) for sample in samples]
        name = policy["name"]
        policy_rows[name] = rows
        summary = _summarize_calibration_rows(rows)
        summary["edit_penalty"] = round(float(penalty), 8)
        summary["policy_name"] = name
        summary["bootstrap_intervals"] = _bootstrap_intervals(
            rows,
            iterations=int(bootstrap_iterations),
            seed=int(seed) + offset,
        )
        policy_results[name] = summary
    return {
        "schema_version": f"{SCHEMA_VERSION}.sweep",
        "sample_count": len(samples),
        "edit_penalties": [round(float(value), 8) for value in penalties],
        "policy_results": policy_results,
        "policy_selection_rows": policy_rows,
        "primary_objective": {
            "optimize_for": ["low_corruption", "calibration_stability", "reproducibility"],
            "not_optimized_for": "best_average_gain_alone",
        },
    }


def analyze_calibration_stability(
    sweep_report: dict,
    *,
    subset_sizes: Optional[Sequence[int]] = None,
    seed: int = 42,
) -> dict:
    """Identify conservative, unstable, over-adopting, and collapsed penalty regions."""

    policy_results = sweep_report.get("policy_results", {})
    policy_rows = sweep_report.get("policy_selection_rows", {})
    sample_count = int(sweep_report.get("sample_count", 0) or 0)
    over_adoption = []
    collapse = []
    conservative_safe = []
    unstable = []
    high_preservation = []
    classifications: dict[str, list[str]] = {}

    for name, row in policy_results.items():
        labels = _classify_policy_region(row)
        classifications[name] = labels
        if "over_adoption_region" in labels:
            over_adoption.append(name)
        if "collapse_region" in labels:
            collapse.append(name)
        if "conservative_safe_region" in labels:
            conservative_safe.append(name)
        if "unstable_region" in labels:
            unstable.append(name)
        if "high_preservation_region" in labels:
            high_preservation.append(name)

    stability = {
        "schema_version": f"{SCHEMA_VERSION}.stability",
        "sample_count": sample_count,
        "policy_classifications": classifications,
        "unstable_regions": unstable,
        "over_adoption_regions": over_adoption,
        "collapse_regions": collapse,
        "conservative_safe_regions": conservative_safe,
        "high_preservation_regions": high_preservation,
        "task_stability": _task_stability(policy_rows),
        "subset_scaling": _subset_scaling(policy_rows, sample_count=sample_count, subset_sizes=subset_sizes, seed=seed),
        "calibration_guidance": _calibration_guidance(policy_results, classifications),
    }
    return stability


def evaluate_repair_calibration_sweep(
    *,
    candidate_traces_path: Path,
    output_dir: Path,
    edit_penalties: Sequence[float] = DEFAULT_EDIT_PENALTIES,
    bootstrap_iterations: int = 500,
    subset_sizes: Optional[Sequence[int]] = None,
    seed: int = 42,
    dry_run: bool = False,
) -> dict:
    """Load candidate traces, run the calibration sweep, and write audit artifacts."""

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
        "sample_count": len(samples),
        "edit_penalties": [round(float(value), 8) for value in _normalized_penalties(edit_penalties)],
        "output_dir": str(output_dir),
    }
    if dry_run:
        _write_json(output_dir / "dry_run_summary.json", dry_summary)
        return dry_summary

    sweep = run_calibration_sweep(
        samples,
        edit_penalties=edit_penalties,
        bootstrap_iterations=bootstrap_iterations,
        seed=seed,
    )
    stability = analyze_calibration_stability(sweep, subset_sizes=subset_sizes, seed=seed)
    report = {
        "schema_version": SCHEMA_VERSION,
        "created_at": created_at,
        "dry_run": False,
        "candidate_traces": str(candidate_traces_path),
        "sample_count": len(samples),
        "edit_penalties": sweep["edit_penalties"],
        "policy_results": sweep["policy_results"],
        "stability_summary": {
            "unstable_regions": stability["unstable_regions"],
            "over_adoption_regions": stability["over_adoption_regions"],
            "collapse_regions": stability["collapse_regions"],
            "conservative_safe_regions": stability["conservative_safe_regions"],
            "calibration_guidance": stability["calibration_guidance"],
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
        },
    }
    scan = forbidden_pattern_scan(
        [
            Path(__file__).relative_to(ROOT),
            Path("tests") / "test_repair_calibration_sweep.py",
        ]
    )

    _write_json(output_dir / "calibration_sweep_report.json", report)
    _write_json(output_dir / "calibration_stability_analysis.json", stability)
    _write_json(output_dir / "forbidden_pattern_scan_calibration.json", scan)
    _write_csv(output_dir / "calibration_curves.csv", report)
    _write_markdown(output_dir / "calibration_summary.md", report, stability)
    return report


def forbidden_pattern_scan(files: Sequence[Path]) -> dict:
    """Scan the calibration implementation for forbidden training/architecture patterns."""

    matches = []
    for file_path in files:
        path = ROOT / file_path
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8")
        for pattern in FORBIDDEN_PATTERNS:
            for match in re.finditer(pattern, text, flags=re.IGNORECASE):
                line = text.count("\n", 0, match.start()) + 1
                matches.append({"file": str(file_path), "line": line, "pattern": pattern, "match": match.group(0)})
    return {
        "schema_version": "gis_recommend.v5_final.forbidden_pattern_scan.v1",
        "files": [str(path) for path in files],
        "patterns": list(FORBIDDEN_PATTERNS),
        "match_count": len(matches),
        "matches": matches,
        "result": "pass" if not matches else "fail",
    }


def _summarize_calibration_rows(rows: Sequence[dict]) -> dict:
    selected_deltas = [row.get("selected_metric_delta", _zero_delta()) for row in rows]
    adopted_rows = [row for row in rows if _is_modified_kind(row.get("selected_candidate_kind"))]
    adopted_deltas = [row.get("selected_metric_delta", _zero_delta()) for row in adopted_rows]
    corruptions = [delta.get("lcs_ratio", 0.0) < 0.0 for delta in selected_deltas]
    adopted_corruptions = [delta.get("lcs_ratio", 0.0) < 0.0 for delta in adopted_deltas]
    adopted_positive = [delta.get("lcs_ratio", 0.0) > 0.0 for delta in adopted_deltas]
    kind_counts = Counter(str(row.get("selected_candidate_kind", "unknown")) for row in rows)
    modified_kind_counts = Counter(
        str(row.get("selected_candidate_kind", "unknown"))
        for row in adopted_rows
    )
    return {
        "sample_count": len(rows),
        "repair_adoption_count": len(adopted_rows),
        "repair_adoption_rate": _round_rate(len(adopted_rows), len(rows)),
        "identity_preservation_count": len(rows) - len(adopted_rows),
        "identity_preservation_rate": _round_rate(len(rows) - len(adopted_rows), len(rows)),
        "corruption_count": sum(1 for value in corruptions if value),
        "corruption_rate": round(_mean(1.0 if value else 0.0 for value in corruptions), 8),
        "repair_precision": _conditional_rate(sum(1 for value in adopted_positive if value), len(adopted_rows)),
        "repair_breakage_count": sum(1 for value in adopted_corruptions if value),
        "repair_breakage_rate": _conditional_rate(sum(1 for value in adopted_corruptions if value), len(adopted_rows)),
        "mean_lcs_gain": round(_mean(delta.get("lcs_ratio", 0.0) for delta in selected_deltas), 8),
        "mean_set_f1_gain": round(_mean(delta.get("set_f1", 0.0) for delta in selected_deltas), 8),
        "mean_token_accuracy_gain": round(_mean(delta.get("token_accuracy", 0.0) for delta in selected_deltas), 8),
        "positive_lcs_selection_rate": round(_mean(1.0 if delta.get("lcs_ratio", 0.0) > 0.0 else 0.0 for delta in selected_deltas), 8),
        "selected_candidate_kind_counts": dict(sorted(kind_counts.items())),
        "modified_selected_kind_counts": dict(sorted(modified_kind_counts.items())),
        "selection_entropy": _selection_entropy(kind_counts),
        "selection_entropy_normalized": _selection_entropy(kind_counts, normalized=True),
        "unique_selected_sequence_count": len({tuple(int(token) for token in row.get("selected_tokens", [])) for row in rows}),
    }


def _bootstrap_intervals(rows: Sequence[dict], *, iterations: int, seed: int) -> dict:
    if not rows or iterations <= 0:
        return {"bootstrap_iterations": int(iterations), "metrics": {}}
    rng = random.Random(int(seed))
    metric_values: dict[str, list[float]] = defaultdict(list)
    row_list = list(rows)
    for _ in range(int(iterations)):
        sample = [row_list[rng.randrange(len(row_list))] for _ in row_list]
        summary = _summarize_calibration_rows(sample)
        for metric in (
            "repair_adoption_rate",
            "corruption_rate",
            "mean_lcs_gain",
            "mean_set_f1_gain",
            "mean_token_accuracy_gain",
            "identity_preservation_rate",
        ):
            metric_values[metric].append(float(summary.get(metric, 0.0) or 0.0))
    return {
        "bootstrap_iterations": int(iterations),
        **{
            metric: _interval(values)
            for metric, values in sorted(metric_values.items())
        },
    }


def _classify_policy_region(row: dict) -> list[str]:
    adoption = float(row.get("repair_adoption_rate", 0.0) or 0.0)
    corruption = float(row.get("corruption_rate", 0.0) or 0.0)
    breakage = row.get("repair_breakage_rate")
    breakage_value = float(breakage) if breakage is not None else 0.0
    mean_lcs = float(row.get("mean_lcs_gain", 0.0) or 0.0)
    intervals = row.get("bootstrap_intervals", {})
    lcs_interval = intervals.get("mean_lcs_gain", {})
    ci_low = float(lcs_interval.get("lower", mean_lcs) or 0.0)
    ci_high = float(lcs_interval.get("upper", mean_lcs) or 0.0)

    labels = []
    if adoption >= 0.90 and (mean_lcs <= 0.0 or corruption >= 0.10):
        labels.append("collapse_region")
    if adoption >= 0.25 and (mean_lcs <= 0.0 or corruption >= 0.10 or breakage_value >= 0.25):
        labels.append("over_adoption_region")
    if adoption <= 0.15 and corruption <= 0.05 and breakage_value <= 0.25 and mean_lcs >= 0.0:
        labels.append("conservative_safe_region")
    if adoption <= 0.02:
        labels.append("high_preservation_region")
    if adoption > 0.0 and ci_low <= 0.0 <= ci_high:
        labels.append("unstable_region")
    if not labels:
        labels.append("uncategorized_region")
    return labels


def _task_stability(policy_rows: dict[str, Sequence[dict]]) -> dict:
    task_report = {}
    for name, rows in policy_rows.items():
        grouped: dict[str, list[dict]] = defaultdict(list)
        for row in rows:
            grouped[str(row.get("task_type") or "unknown")].append(row)
        task_summaries = {task: _summarize_calibration_rows(task_rows) for task, task_rows in sorted(grouped.items())}
        usable = [row for row in task_summaries.values() if int(row.get("sample_count", 0)) > 0]
        task_report[name] = {
            "task_count": len(task_summaries),
            "positive_task_rate": round(_mean(1.0 if row.get("mean_lcs_gain", 0.0) > 0.0 else 0.0 for row in usable), 8),
            "negative_task_rate": round(_mean(1.0 if row.get("mean_lcs_gain", 0.0) < 0.0 else 0.0 for row in usable), 8),
            "max_task_corruption_rate": round(max((float(row.get("corruption_rate", 0.0) or 0.0) for row in usable), default=0.0), 8),
            "task_summaries": task_summaries,
        }
    return task_report


def _subset_scaling(
    policy_rows: dict[str, Sequence[dict]],
    *,
    sample_count: int,
    subset_sizes: Optional[Sequence[int]],
    seed: int,
) -> dict:
    if sample_count <= 0:
        return {"subset_sizes": [], "policy_scaling": {}}
    sizes = _normalized_subset_sizes(sample_count, subset_sizes)
    rng = random.Random(int(seed))
    indices = list(range(sample_count))
    rng.shuffle(indices)
    scaling = {}
    for name, rows in policy_rows.items():
        row_list = list(rows)
        policy_scaling = {}
        for size in sizes:
            active_indices = indices[:size]
            subset_rows = [row_list[index] for index in active_indices if index < len(row_list)]
            policy_scaling[str(size)] = _summarize_calibration_rows(subset_rows)
        scaling[name] = policy_scaling
    return {"subset_sizes": sizes, "policy_scaling": scaling}


def _calibration_guidance(policy_results: dict[str, dict], classifications: dict[str, list[str]]) -> dict:
    eligible = []
    for name, row in policy_results.items():
        labels = classifications.get(name, [])
        if "collapse_region" in labels or "over_adoption_region" in labels:
            continue
        if float(row.get("repair_adoption_rate", 0.0) or 0.0) <= 0.0:
            continue
        if float(row.get("corruption_rate", 0.0) or 0.0) > 0.05:
            continue
        breakage = row.get("repair_breakage_rate")
        if breakage is not None and float(breakage) > 0.25:
            continue
        if float(row.get("mean_lcs_gain", 0.0) or 0.0) < 0.0:
            continue
        eligible.append((name, row))
    if not eligible:
        return {
            "recommended_next_validation": None,
            "basis": "no_low_corruption_positive_policy_found",
            "production_change_allowed": False,
        }
    name, row = max(
        eligible,
        key=lambda item: (
            -float(item[1].get("corruption_rate", 0.0) or 0.0),
            -float(item[1].get("repair_breakage_rate") or 0.0),
            float(item[1].get("mean_lcs_gain", 0.0) or 0.0),
            -abs(float(item[1].get("repair_adoption_rate", 0.0) or 0.0) - 0.08),
        ),
    )
    return {
        "recommended_next_validation": name,
        "basis": "low_corruption_first_then_positive_gain",
        "production_change_allowed": False,
        "metrics": {
            "repair_adoption_rate": row.get("repair_adoption_rate"),
            "corruption_rate": row.get("corruption_rate"),
            "repair_breakage_rate": row.get("repair_breakage_rate"),
            "mean_lcs_gain": row.get("mean_lcs_gain"),
            "mean_set_f1_gain": row.get("mean_set_f1_gain"),
            "mean_token_accuracy_gain": row.get("mean_token_accuracy_gain"),
        },
    }


def _uniform_edit_policy(penalty: float) -> dict:
    penalty_value = round(float(penalty), 8)
    return {
        "name": _penalty_name(penalty_value),
        "description": f"Uniform edit penalty {penalty_value:.2f}.",
        "weights": {**DEFAULT_SCORE_WEIGHTS, "edit_penalty": penalty_value},
    }


def _penalty_name(penalty: float) -> str:
    return f"uniform_edit_{float(penalty):.2f}".replace(".", "_")


def _normalized_penalties(edit_penalties: Sequence[float]) -> list[float]:
    return sorted({round(float(value), 8) for value in edit_penalties})


def _normalized_subset_sizes(sample_count: int, subset_sizes: Optional[Sequence[int]]) -> list[int]:
    if subset_sizes:
        sizes = [int(value) for value in subset_sizes if 0 < int(value) <= sample_count]
    else:
        sizes = [25, 50, 100, 200, sample_count]
        sizes = [size for size in sizes if size <= sample_count]
    if sample_count not in sizes:
        sizes.append(sample_count)
    return sorted(set(sizes))


def _write_csv(path: Path, report: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = [
        "policy_name",
        "edit_penalty",
        "sample_count",
        "repair_adoption_rate",
        "corruption_rate",
        "repair_precision",
        "repair_breakage_rate",
        "identity_preservation_rate",
        "mean_lcs_gain",
        "mean_lcs_gain_ci_lower",
        "mean_lcs_gain_ci_upper",
        "mean_set_f1_gain",
        "mean_token_accuracy_gain",
        "selection_entropy",
        "selection_entropy_normalized",
        "unique_selected_sequence_count",
    ]
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for name, row in report.get("policy_results", {}).items():
            ci = row.get("bootstrap_intervals", {}).get("mean_lcs_gain", {})
            writer.writerow(
                {
                    "policy_name": name,
                    "edit_penalty": row.get("edit_penalty"),
                    "sample_count": row.get("sample_count"),
                    "repair_adoption_rate": row.get("repair_adoption_rate"),
                    "corruption_rate": row.get("corruption_rate"),
                    "repair_precision": row.get("repair_precision"),
                    "repair_breakage_rate": row.get("repair_breakage_rate"),
                    "identity_preservation_rate": row.get("identity_preservation_rate"),
                    "mean_lcs_gain": row.get("mean_lcs_gain"),
                    "mean_lcs_gain_ci_lower": ci.get("lower"),
                    "mean_lcs_gain_ci_upper": ci.get("upper"),
                    "mean_set_f1_gain": row.get("mean_set_f1_gain"),
                    "mean_token_accuracy_gain": row.get("mean_token_accuracy_gain"),
                    "selection_entropy": row.get("selection_entropy"),
                    "selection_entropy_normalized": row.get("selection_entropy_normalized"),
                    "unique_selected_sequence_count": row.get("unique_selected_sequence_count"),
                }
            )


def _write_markdown(path: Path, report: dict, stability: dict) -> None:
    guidance = stability.get("calibration_guidance", {})
    lines = [
        "# Repair Edit-Penalty Calibration Sweep",
        "",
        "Evaluation-only scorer calibration over existing repair candidate traces. No training, checkpoint loading, architecture mutation, candidate generation, or retrieval redesign is performed.",
        "",
        f"Samples: `{report.get('sample_count')}`",
        f"Recommended next validation: `{guidance.get('recommended_next_validation')}`",
        f"Production change allowed: `{guidance.get('production_change_allowed')}`",
        "",
        "## Sweep Results",
        "",
        "| Policy | Penalty | Adoption | Corruption | Precision | Breakage | Identity Preservation | LCS Delta | SetF1 Delta | Token Delta |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for name, row in report.get("policy_results", {}).items():
        lines.append(
            f"| `{name}` | {row.get('edit_penalty')} | {row.get('repair_adoption_rate')} | "
            f"{row.get('corruption_rate')} | {row.get('repair_precision')} | {row.get('repair_breakage_rate')} | "
            f"{row.get('identity_preservation_rate')} | {row.get('mean_lcs_gain')} | "
            f"{row.get('mean_set_f1_gain')} | {row.get('mean_token_accuracy_gain')} |"
        )
    lines.extend(
        [
            "",
            "## Region Classification",
            "",
            "```json",
            json.dumps(
                {
                    "unstable_regions": stability.get("unstable_regions", []),
                    "over_adoption_regions": stability.get("over_adoption_regions", []),
                    "collapse_regions": stability.get("collapse_regions", []),
                    "conservative_safe_regions": stability.get("conservative_safe_regions", []),
                    "high_preservation_regions": stability.get("high_preservation_regions", []),
                },
                ensure_ascii=False,
                indent=2,
            ),
            "```",
            "",
            "## Calibration Guidance",
            "",
            "```json",
            json.dumps(guidance, ensure_ascii=False, indent=2),
            "```",
            "",
            "This is scorer calibration evidence only. It is not evidence of generative planning capability.",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _is_modified_kind(kind: Optional[str]) -> bool:
    return str(kind or "unknown") not in {"identity", "unknown", "empty"}


def _selection_entropy(counts: Counter, *, normalized: bool = False) -> float:
    total = sum(counts.values())
    if total <= 0:
        return 0.0
    probs = [count / total for count in counts.values() if count > 0]
    entropy = -sum(prob * math.log(prob, 2) for prob in probs)
    if normalized:
        max_entropy = math.log(max(len(probs), 1), 2)
        return round(entropy / max_entropy, 8) if max_entropy > 0.0 else 0.0
    return round(entropy, 8)


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


def _round_rate(numerator: int, denominator: int) -> float:
    return round(float(numerator) / max(int(denominator), 1), 8)


def _conditional_rate(numerator: int, denominator: int) -> Optional[float]:
    if denominator <= 0:
        return None
    return round(float(numerator) / float(denominator), 8)


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


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _build_parser() -> argparse.ArgumentParser:
    oracle_dir = OUTPUT_DIR / "v5_final_reports" / "repair_oracle_phase"
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate-traces", type=Path, default=oracle_dir / "repair_candidate_traces.json")
    parser.add_argument("--output-dir", type=Path, default=OUTPUT_DIR / "v5_final_reports" / "repair_calibration_sweep")
    parser.add_argument("--edit-penalties", type=float, nargs="+", default=list(DEFAULT_EDIT_PENALTIES))
    parser.add_argument("--bootstrap-iterations", type=int, default=500)
    parser.add_argument("--subset-sizes", type=int, nargs="*", default=None)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--dry-run", action="store_true")
    return parser


def main(argv: Optional[list[str]] = None) -> dict:
    args = _build_parser().parse_args(argv)
    report = evaluate_repair_calibration_sweep(
        candidate_traces_path=args.candidate_traces,
        output_dir=args.output_dir,
        edit_penalties=args.edit_penalties,
        bootstrap_iterations=args.bootstrap_iterations,
        subset_sizes=args.subset_sizes,
        seed=args.seed,
        dry_run=args.dry_run,
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return report


if __name__ == "__main__":
    main()
