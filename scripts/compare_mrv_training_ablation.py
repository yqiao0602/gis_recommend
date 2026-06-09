#!/usr/bin/env python3
"""Compare baseline vs MRV training ablation evaluation reports.

This is a read-only comparison scaffold. It consumes already-produced JSON
reports and writes aligned deltas; it does not train, run inference, load
checkpoints, or mutate source data.
"""

from __future__ import annotations

import argparse
import json
import random
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Sequence


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


SCHEMA_VERSION = "gis_recommend.v4_qg.mrv_training_ablation_comparison.v1"
DEFAULT_OUTPUT_DIR = ROOT / "outputs_v2" / "v4_qg_mr_ablation" / "comparison"

METRIC_PATHS: dict[str, tuple[tuple[Any, ...], ...]] = {
    "top1_usable_rate": (
        ("aggregate_metrics", "selected_top1_usable_rate"),
        ("aggregate_metrics", "top1_usable_rate"),
        ("metrics", "top1_usable_rate"),
    ),
    "top3_any_usable_rate": (
        ("aggregate_metrics", "pool_top3_any_usable_rate"),
        ("aggregate_metrics", "top3_any_usable_rate"),
        ("metrics", "top3_any_usable_rate"),
    ),
    "top5_any_usable_rate": (
        ("aggregate_metrics", "pool_top5_any_usable_rate"),
        ("aggregate_metrics", "top5_any_usable_rate"),
        ("metrics", "top5_any_usable_rate"),
    ),
    "mean_usability_score": (
        ("aggregate_metrics", "mean_selected_usability_score"),
        ("aggregate_metrics", "mean_usability_score"),
        ("metrics", "mean_usability_score"),
    ),
    "mean_qgis_mapping_rate": (
        ("aggregate_metrics", "mean_selected_qgis_mapping_rate"),
        ("aggregate_metrics", "mean_executable_qgis_mapping_rate"),
        ("metrics", "mean_qgis_mapping_rate"),
    ),
    "mean_logic_consistency": (
        ("aggregate_metrics", "mean_selected_logic_consistency"),
        ("aggregate_metrics", "mean_workflow_logic_consistency"),
        ("metrics", "mean_logic_consistency"),
    ),
    "invalid_harmful_rate": (
        ("aggregate_metrics", "invalid_harmful_rate"),
        ("aggregate_metrics", "harmful_step_rate"),
        ("metrics", "invalid_harmful_rate"),
    ),
    "diversity_score": (
        ("aggregate_metrics", "diversity_score"),
        ("aggregate_metrics", "mean_diversity_score"),
        ("metrics", "diversity_score"),
    ),
    "canonicalized_lcs_ratio": (
        ("overall", "canonicalized_metrics", "lcs_ratio"),
        ("aggregate_metrics", "canonicalized_lcs_ratio"),
        ("metrics", "canonicalized_lcs_ratio"),
    ),
    "canonicalized_set_f1": (
        ("overall", "canonicalized_metrics", "set_f1"),
        ("aggregate_metrics", "canonicalized_set_f1"),
        ("metrics", "canonicalized_set_f1"),
    ),
    "canonicalized_token_accuracy": (
        ("overall", "canonicalized_metrics", "token_accuracy"),
        ("aggregate_metrics", "canonicalized_token_accuracy"),
        ("metrics", "canonicalized_token_accuracy"),
    ),
    "canonicalized_exact_match": (
        ("overall", "canonicalized_metrics", "exact_match"),
        ("overall", "canonicalized_metrics", "sequence_em"),
        ("aggregate_metrics", "canonicalized_exact_match"),
        ("metrics", "canonicalized_exact_match"),
    ),
    "raw_lcs_ratio": (
        ("overall", "raw_metrics", "lcs_ratio"),
        ("aggregate_metrics", "raw_lcs_ratio"),
        ("metrics", "raw_lcs_ratio"),
    ),
    "raw_set_f1": (
        ("overall", "raw_metrics", "set_f1"),
        ("aggregate_metrics", "raw_set_f1"),
        ("metrics", "raw_set_f1"),
    ),
    "raw_token_accuracy": (
        ("overall", "raw_metrics", "token_accuracy"),
        ("aggregate_metrics", "raw_token_accuracy"),
        ("metrics", "raw_token_accuracy"),
    ),
    "exact_match": (
        ("aggregate_metrics", "exact_match"),
        ("metrics", "exact_match"),
        ("overall", "raw_metrics", "exact_match"),
        ("overall", "raw_metrics", "sequence_em"),
    ),
}

SAMPLE_METRIC_PATHS: dict[str, tuple[tuple[Any, ...], ...]] = {
    "top1_usable_rate": (
        ("metrics", "top1_usable_rate"),
        ("metrics", "top1_usable"),
        ("selected", "usability", "usable"),
        ("retrieval", "top1", "per_candidate", 0, "usable"),
    ),
    "mean_usability_score": (
        ("metrics", "mean_usability_score"),
        ("metrics", "usability_score"),
        ("selected", "usability", "usability_score"),
        ("retrieval", "top1", "per_candidate", 0, "usability_score"),
    ),
    "mean_qgis_mapping_rate": (
        ("metrics", "mean_qgis_mapping_rate"),
        ("metrics", "executable_qgis_mapping_rate"),
        ("selected", "usability", "executable_qgis_mapping_rate"),
        ("retrieval", "top1", "per_candidate", 0, "executable_qgis_mapping_rate"),
    ),
    "mean_logic_consistency": (
        ("metrics", "mean_logic_consistency"),
        ("metrics", "workflow_logic_consistency"),
        ("selected", "usability", "workflow_logic_consistency"),
        ("retrieval", "top1", "per_candidate", 0, "workflow_logic_consistency"),
    ),
    "invalid_harmful_rate": (
        ("metrics", "invalid_harmful_rate"),
        ("metrics", "harmful_step_rate"),
        ("selected", "usability", "harmful_step_rate"),
        ("retrieval", "top1", "per_candidate", 0, "harmful_step_rate"),
    ),
    "canonicalized_lcs_ratio": (
        ("metrics", "canonicalized_lcs_ratio"),
        ("canonicalized_metrics", "lcs_ratio"),
    ),
    "canonicalized_set_f1": (
        ("metrics", "canonicalized_set_f1"),
        ("canonicalized_metrics", "set_f1"),
    ),
    "canonicalized_token_accuracy": (
        ("metrics", "canonicalized_token_accuracy"),
        ("canonicalized_metrics", "token_accuracy"),
    ),
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _load_json(path: Path) -> dict:
    with Path(path).open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, dict):
        raise ValueError(f"Expected JSON object: {path}")
    return payload


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _get_path(payload: Any, path: Sequence[Any]) -> Any:
    current = payload
    for part in path:
        if isinstance(part, int):
            if not isinstance(current, list) or part >= len(current):
                return None
            current = current[part]
        else:
            if not isinstance(current, dict) or part not in current:
                return None
            current = current[part]
    return current


def _to_float(value: Any) -> float | None:
    if isinstance(value, bool):
        return float(value)
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str) and value.strip():
        try:
            return float(value)
        except ValueError:
            return None
    return None


def extract_metrics(report: dict) -> tuple[dict[str, float], list[str]]:
    metrics: dict[str, float] = {}
    missing: list[str] = []
    for metric, paths in METRIC_PATHS.items():
        value = None
        for path in paths:
            value = _to_float(_get_path(report, path))
            if value is not None:
                break
        if value is None:
            missing.append(metric)
        else:
            metrics[metric] = round(value, 8)
    return metrics, missing


def _sample_id(row: dict, index: int) -> str:
    for key in ("sample_id", "test_index", "id"):
        value = row.get(key)
        if value is not None:
            return str(value)
    return str(index)


def _extract_sample_metrics(report: dict) -> dict[str, dict[str, float]]:
    rows = report.get("per_sample", [])
    if not isinstance(rows, list):
        return {}
    out: dict[str, dict[str, float]] = {}
    for index, row in enumerate(rows):
        if not isinstance(row, dict):
            continue
        sample_metrics: dict[str, float] = {}
        for metric, paths in SAMPLE_METRIC_PATHS.items():
            value = None
            for path in paths:
                value = _to_float(_get_path(row, path))
                if value is not None:
                    break
            if value is not None:
                sample_metrics[metric] = value
        if sample_metrics:
            out[_sample_id(row, index)] = sample_metrics
    return out


def _bootstrap_ci(values: Sequence[float], *, iterations: int, seed: int) -> dict:
    values = [float(value) for value in values]
    if not values:
        return {"n": 0, "iterations": int(iterations), "mean_delta": None}
    if len(values) == 1 or iterations <= 0:
        mean_delta = sum(values) / len(values)
        return {
            "n": len(values),
            "iterations": int(iterations),
            "mean_delta": round(mean_delta, 8),
            "ci95_low": None,
            "ci95_high": None,
            "n_small": True,
        }
    rng = random.Random(int(seed))
    means = sorted(
        sum(rng.choice(values) for _ in values) / len(values)
        for _ in range(int(iterations))
    )
    low_index = max(0, int(0.025 * (len(means) - 1)))
    high_index = min(len(means) - 1, int(0.975 * (len(means) - 1)))
    mean_delta = sum(values) / len(values)
    return {
        "n": len(values),
        "iterations": int(iterations),
        "mean_delta": round(mean_delta, 8),
        "ci95_low": round(means[low_index], 8),
        "ci95_high": round(means[high_index], 8),
        "mostly_positive": means[low_index] > 0.0,
        "mostly_negative": means[high_index] < 0.0,
    }


def _paired_bootstrap_delta(
    baseline_report: dict,
    variant_report: dict,
    *,
    bootstrap_iterations: int,
    seed: int,
) -> dict[str, dict]:
    baseline_samples = _extract_sample_metrics(baseline_report)
    variant_samples = _extract_sample_metrics(variant_report)
    common_ids = sorted(set(baseline_samples) & set(variant_samples))
    if not common_ids:
        return {}
    out: dict[str, dict] = {}
    for metric in SAMPLE_METRIC_PATHS:
        deltas = []
        for sample_id in common_ids:
            base_value = baseline_samples[sample_id].get(metric)
            variant_value = variant_samples[sample_id].get(metric)
            if base_value is not None and variant_value is not None:
                deltas.append(float(variant_value) - float(base_value))
        if deltas:
            out[metric] = _bootstrap_ci(
                deltas,
                iterations=bootstrap_iterations,
                seed=seed,
            )
    return out


def _manifest_versions(manifest: dict | None) -> dict[str, dict]:
    if not manifest:
        return {}
    versions = manifest.get("versions", [])
    if not isinstance(versions, list):
        return {}
    return {
        str(version.get("version_name", "")): version
        for version in versions
        if isinstance(version, dict) and version.get("version_name")
    }


def _safe_delta(variant: float, baseline: float) -> float:
    return round(float(variant) - float(baseline), 8)


def _relative_delta(delta: float, baseline: float) -> float | None:
    if baseline == 0.0:
        return None
    return round(float(delta) / abs(float(baseline)), 8)


def compare_reports(
    *,
    baseline_report_path: Path,
    variant_report_paths: dict[str, Path],
    manifest_path: Path | None = None,
    bootstrap_iterations: int = 500,
    seed: int = 42,
) -> dict:
    baseline_report = _load_json(Path(baseline_report_path))
    baseline_metrics, baseline_missing = extract_metrics(baseline_report)
    manifest = _load_json(Path(manifest_path)) if manifest_path else None
    manifest_by_version = _manifest_versions(manifest)

    comparisons = []
    for version_name, report_path in variant_report_paths.items():
        variant_report = _load_json(Path(report_path))
        variant_metrics, variant_missing = extract_metrics(variant_report)
        metric_deltas: dict[str, float] = {}
        relative_deltas: dict[str, float | None] = {}
        warnings: list[str] = []
        for metric in METRIC_PATHS:
            if metric not in baseline_metrics:
                if metric not in variant_missing:
                    warnings.append(f"missing baseline metric: {metric}")
                continue
            if metric not in variant_metrics:
                warnings.append(f"missing variant metric: {metric}")
                continue
            delta = _safe_delta(variant_metrics[metric], baseline_metrics[metric])
            metric_deltas[metric] = delta
            relative_deltas[metric] = _relative_delta(delta, baseline_metrics[metric])

        bootstrap_delta_ci = _paired_bootstrap_delta(
            baseline_report,
            variant_report,
            bootstrap_iterations=bootstrap_iterations,
            seed=seed,
        )
        if not bootstrap_delta_ci:
            warnings.append("no paired per-sample metrics available for bootstrap delta CIs")

        manifest_version = manifest_by_version.get(version_name, {})
        comparisons.append(
            {
                "version_name": version_name,
                "report_path": str(report_path),
                "schema_version": str(variant_report.get("schema_version", "")),
                "metrics": variant_metrics,
                "missing_metrics": variant_missing,
                "metric_deltas": metric_deltas,
                "relative_deltas": relative_deltas,
                "bootstrap_delta_ci": bootstrap_delta_ci,
                "manifest_counts": manifest_version.get("counts", {}),
                "selected_variant_count": len(manifest_version.get("selected_variant_ids", []) or []),
                "warnings": warnings,
            }
        )

    return {
        "schema_version": SCHEMA_VERSION,
        "created_at": _now(),
        "governance": {
            "comparison_only": True,
            "no_training": True,
            "no_inference": True,
            "no_checkpoint_loading": True,
            "no_checkpoint_modification": True,
            "no_source_data_mutation": True,
        },
        "baseline": {
            "report_path": str(baseline_report_path),
            "schema_version": str(baseline_report.get("schema_version", "")),
            "metrics": baseline_metrics,
            "missing_metrics": baseline_missing,
        },
        "manifest": {
            "path": str(manifest_path) if manifest_path else None,
            "no_training_started": bool((manifest or {}).get("no_training_started", False)),
            "version_count": int((manifest or {}).get("version_count", len(manifest_by_version))),
        },
        "comparisons": comparisons,
        "metric_contract": {
            "primary_metrics": [
                "top1_usable_rate",
                "top3_any_usable_rate",
                "top5_any_usable_rate",
                "mean_usability_score",
                "invalid_harmful_rate",
                "diversity_score",
                "canonicalized_lcs_ratio",
                "canonicalized_set_f1",
                "canonicalized_token_accuracy",
            ],
            "secondary_metrics": ["canonicalized_exact_match", "exact_match"],
            "bootstrap_requires_paired_per_sample_metrics": True,
        },
    }


def write_markdown_summary(path: Path, report: dict) -> None:
    lines = [
        "# MRV Training Ablation Comparison",
        "",
        f"Schema: `{report['schema_version']}`",
        f"Created: {report['created_at']}",
        "",
        "## Boundary",
        "",
        "- Read-only comparison of existing evaluation reports.",
        "- No training, inference, checkpoint loading, checkpoint mutation, or source-data mutation.",
        "- Exact match is secondary; usability and canonicalized metrics are primary.",
        "",
        "## Baseline",
        "",
        f"- Report: `{report['baseline']['report_path']}`",
        f"- Extracted metrics: {len(report['baseline']['metrics'])}",
        "",
        "## Deltas",
        "",
        "| Version | Metric | Baseline | Variant | Delta | Relative Delta |",
        "| --- | --- | ---: | ---: | ---: | ---: |",
    ]
    baseline_metrics = report["baseline"]["metrics"]
    for comparison in report["comparisons"]:
        version = comparison["version_name"]
        for metric, delta in comparison["metric_deltas"].items():
            baseline_value = baseline_metrics.get(metric)
            variant_value = comparison["metrics"].get(metric)
            relative = comparison["relative_deltas"].get(metric)
            relative_text = "" if relative is None else f"{relative:.6f}"
            lines.append(
                f"| {version} | {metric} | {baseline_value:.6f} | "
                f"{variant_value:.6f} | {delta:+.6f} | {relative_text} |"
            )

    warnings = [
        f"{comparison['version_name']}: {warning}"
        for comparison in report["comparisons"]
        for warning in comparison.get("warnings", [])
    ]
    if warnings:
        lines.extend(["", "## Warnings", ""])
        for warning in warnings:
            lines.append(f"- {warning}")

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _parse_variant_report(value: str) -> tuple[str, Path]:
    if "=" in value:
        name, raw_path = value.split("=", 1)
        name = name.strip()
        if not name:
            raise ValueError(f"Invalid --variant-report name: {value}")
        return name, Path(raw_path)
    path = Path(value)
    return path.stem, path


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline-report", required=True, type=Path)
    parser.add_argument(
        "--variant-report",
        action="append",
        default=[],
        help="Variant report as NAME=PATH. May be repeated.",
    )
    parser.add_argument("--manifest", type=Path, default=None)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--bootstrap-iterations", type=int, default=500)
    parser.add_argument("--seed", type=int, default=42)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> dict:
    args = parse_args(argv)
    if not args.variant_report:
        raise ValueError("At least one --variant-report NAME=PATH is required")
    variant_paths = dict(_parse_variant_report(value) for value in args.variant_report)
    report = compare_reports(
        baseline_report_path=args.baseline_report,
        variant_report_paths=variant_paths,
        manifest_path=args.manifest,
        bootstrap_iterations=args.bootstrap_iterations,
        seed=args.seed,
    )
    output_dir = Path(args.output_dir)
    _write_json(output_dir / "mrv_training_ablation_comparison.json", report)
    write_markdown_summary(
        output_dir / "mrv_training_ablation_comparison_summary.md",
        report,
    )
    print("MRV training ablation comparison written:")
    print(f"  output_dir: {output_dir}")
    for comparison in report["comparisons"]:
        print(
            f"  {comparison['version_name']}: "
            f"{len(comparison['metric_deltas'])} metric deltas"
        )
    return report


if __name__ == "__main__":
    main()
