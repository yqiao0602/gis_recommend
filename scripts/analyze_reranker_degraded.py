from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_REPORT_PATH = PROJECT_ROOT / "outputs" / "evaluation_report.json"
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "outputs"
EPS = 1e-8


def load_report(report_path: str | Path) -> dict:
    """Load one frozen evaluation report JSON."""
    path = Path(report_path)
    if not path.exists():
        raise FileNotFoundError(f"Report not found: {path}")
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def length_bucket(ref_len: int) -> str:
    """Bucket reference sequence length for degraded-pattern analysis."""
    if ref_len <= 8:
        return "short"
    if ref_len <= 15:
        return "medium"
    return "long"


def _safe_float(value, default: float = 0.0) -> float:
    if value is None:
        return default
    return float(value)


def _resolve_metric_triplet(sample: dict, metric_name: str) -> tuple[float, float, float]:
    """Resolve baseline/final/delta values from per-sample report fields."""
    baseline_key = f"baseline_{metric_name}"
    delta_key = f"delta_{metric_name}"

    baseline = sample.get(baseline_key)
    final = sample.get(metric_name)
    delta = sample.get(delta_key)

    baseline_v = _safe_float(baseline, default=None)
    final_v = _safe_float(final, default=None)
    delta_v = _safe_float(delta, default=None)

    if baseline is None and final is not None and delta is not None:
        baseline_v = final_v - delta_v
    if final is None and baseline is not None and delta is not None:
        final_v = baseline_v + delta_v
    if delta is None and baseline_v is not None and final_v is not None:
        delta_v = final_v - baseline_v

    baseline_v = 0.0 if baseline_v is None else baseline_v
    final_v = baseline_v if final_v is None else final_v
    delta_v = final_v - baseline_v if delta_v is None else delta_v
    return baseline_v, final_v, delta_v


def compute_composite_score(set_f1: float, lcs_ratio: float, length_ratio: float) -> float:
    """Mirror gis_recommend.evaluation.diagnostics reranker composite score."""
    len_score = max(0.0, 1.0 - abs(1.0 - length_ratio))
    return 0.5 * set_f1 + 0.3 * lcs_ratio + 0.2 * len_score


def compute_composite_from_sample(sample: dict) -> tuple[float, float, float]:
    """Return baseline, final and delta composite scores for one sample."""
    baseline_set_f1, final_set_f1, _ = _resolve_metric_triplet(sample, "set_f1")
    baseline_lcs, final_lcs, _ = _resolve_metric_triplet(sample, "lcs_ratio")
    baseline_len, final_len, _ = _resolve_metric_triplet(sample, "length_ratio")

    baseline_score = compute_composite_score(baseline_set_f1, baseline_lcs, baseline_len)
    final_score = compute_composite_score(final_set_f1, final_lcs, final_len)
    return baseline_score, final_score, final_score - baseline_score


def _infer_effect(sample: dict, delta_composite: float) -> str:
    effect = sample.get("reranker_effect")
    if effect in {"improved", "degraded", "unchanged"}:
        return effect
    if delta_composite > EPS:
        return "improved"
    if delta_composite < -EPS:
        return "degraded"
    return "unchanged"


def _build_sample_record(sample: dict) -> dict:
    baseline_set_f1, final_set_f1, delta_set_f1 = _resolve_metric_triplet(sample, "set_f1")
    baseline_lcs, final_lcs, delta_lcs = _resolve_metric_triplet(sample, "lcs_ratio")
    baseline_len, final_len, delta_len = _resolve_metric_triplet(sample, "length_ratio")
    baseline_composite, final_composite, delta_composite = compute_composite_from_sample(sample)

    return {
        "index": sample.get("index"),
        "task_name": sample.get("task_name", ""),
        "task_type": sample.get("task_type", "Unknown"),
        "ref_len": int(sample.get("ref_len", 0) or 0),
        "pred_len": int(sample.get("pred_len", 0) or 0),
        "prediction_changed": bool(sample.get("prediction_changed", False)),
        "selected_from_reranker": bool(sample.get("selected_from_reranker", False)),
        "reranker_pool_size": int(sample.get("reranker_pool_size", 0) or 0),
        "baseline_set_f1": round(baseline_set_f1, 4),
        "final_set_f1": round(final_set_f1, 4),
        "delta_set_f1": round(delta_set_f1, 4),
        "baseline_lcs_ratio": round(baseline_lcs, 4),
        "final_lcs_ratio": round(final_lcs, 4),
        "delta_lcs_ratio": round(delta_lcs, 4),
        "baseline_length_ratio": round(baseline_len, 4),
        "final_length_ratio": round(final_len, 4),
        "delta_length_ratio": round(delta_len, 4),
        "baseline_composite": round(baseline_composite, 4),
        "final_composite": round(final_composite, 4),
        "delta_composite": round(delta_composite, 4),
        "reranker_features": dict(sample.get("reranker_features") or {}),
    }


def _avg_feature(records: list[dict], feature_name: str) -> float:
    values = []
    for record in records:
        features = record.get("reranker_features") or {}
        if feature_name in features and features[feature_name] is not None:
            values.append(float(features[feature_name]))
    if not values:
        return 0.0
    return sum(values) / len(values)


def analyze_report_data(report: dict, top_n: int = 5) -> dict:
    """Analyze improved/degraded/unchanged reranker outcomes from one report."""
    samples = list(report.get("per_sample") or [])
    if not samples:
        raise ValueError("Report does not contain per_sample data")

    if not any(
        ("reranker_effect" in sample)
        or ("baseline_set_f1" in sample)
        or ("delta_set_f1" in sample)
        for sample in samples
    ):
        raise ValueError("Report does not contain reranker diagnostics; reranker analysis is unavailable")

    normalized = []
    grouped = {"improved": [], "degraded": [], "unchanged": []}
    for sample in samples:
        record = _build_sample_record(sample)
        effect = _infer_effect(sample, record["delta_composite"])
        record["reranker_effect"] = effect
        normalized.append(record)
        grouped[effect].append(record)

    degraded = grouped["degraded"]
    improved = grouped["improved"]
    unchanged = grouped["unchanged"]

    task_type_degraded_counts = Counter(record["task_type"] for record in degraded)
    degraded_length_buckets = Counter(length_bucket(record["ref_len"]) for record in degraded)

    feature_names = sorted({
        key
        for record in (degraded + improved)
        for key in (record.get("reranker_features") or {}).keys()
    })
    feature_compare = {}
    for feature_name in feature_names:
        degraded_avg = _avg_feature(degraded, feature_name)
        improved_avg = _avg_feature(improved, feature_name)
        feature_compare[feature_name] = {
            "degraded_avg": round(degraded_avg, 4),
            "improved_avg": round(improved_avg, 4),
            "delta": round(improved_avg - degraded_avg, 4),
        }

    degraded_sorted = sorted(degraded, key=lambda item: (item["delta_composite"], item["index"] or -1))
    improved_sorted = sorted(improved, key=lambda item: (-item["delta_composite"], item["index"] or -1))

    summary = {
        "total": len(normalized),
        "improved": len(improved),
        "degraded": len(degraded),
        "unchanged": len(unchanged),
        "avg_delta_composite_improved": round(
            sum(item["delta_composite"] for item in improved) / len(improved), 4
        ) if improved else 0.0,
        "avg_delta_composite_degraded": round(
            sum(item["delta_composite"] for item in degraded) / len(degraded), 4
        ) if degraded else 0.0,
        "eval_mode": report.get("experiment_meta", {}).get("eval_mode"),
        "use_reranker": report.get("experiment_meta", {}).get("use_reranker"),
    }

    return {
        "summary": summary,
        "task_type_degraded_counts": dict(task_type_degraded_counts),
        "degraded_length_buckets": dict(degraded_length_buckets),
        "feature_compare": feature_compare,
        "top_degraded": degraded_sorted[:top_n],
        "top_improved": improved_sorted[:top_n],
    }


def build_default_output_path(report_path: str | Path) -> Path:
    """Place analysis next to the input report to avoid cross-run overwrites."""
    path = Path(report_path)
    return path.with_name(f"{path.stem}-reranker-degraded-analysis.json")


def save_analysis(analysis: dict, output_path: str | Path) -> Path:
    """Persist the analysis JSON."""
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(analysis, f, ensure_ascii=False, indent=2)
    return path


def print_analysis(analysis: dict) -> None:
    """Print a concise console summary."""
    summary = analysis["summary"]
    print("=" * 70)
    print("Reranker Degraded Analysis")
    print("=" * 70)
    print(
        f"Total={summary['total']}  "
        f"Improved={summary['improved']}  "
        f"Degraded={summary['degraded']}  "
        f"Unchanged={summary['unchanged']}"
    )
    print(
        f"Avg delta composite: improved={summary['avg_delta_composite_improved']:+.4f}, "
        f"degraded={summary['avg_delta_composite_degraded']:+.4f}"
    )

    if analysis["task_type_degraded_counts"]:
        print("\nTop degraded task types:")
        for task_type, count in Counter(analysis["task_type_degraded_counts"]).most_common(10):
            print(f"  {task_type}: {count}")

    if analysis["degraded_length_buckets"]:
        print("\nDegraded length buckets:")
        for bucket in ["short", "medium", "long"]:
            if bucket in analysis["degraded_length_buckets"]:
                print(f"  {bucket}: {analysis['degraded_length_buckets'][bucket]}")

    if analysis["top_degraded"]:
        print("\nWorst degraded samples:")
        for item in analysis["top_degraded"]:
            print(
                f"  idx={item['index']} task_type={item['task_type']} "
                f"delta={item['delta_composite']:+.4f} pool={item['reranker_pool_size']}"
            )


def main() -> None:
    parser = argparse.ArgumentParser(description="Analyze reranker improved/degraded samples from one saved report")
    parser.add_argument("--report-path", type=str, default=str(DEFAULT_REPORT_PATH),
                        help="Path to a frozen evaluation_report JSON")
    parser.add_argument("--top-n", type=int, default=5,
                        help="Number of worst/best samples to keep in the analysis JSON")
    parser.add_argument("--output-path", type=str, default=None,
                        help="Optional output path for the analysis JSON")
    args = parser.parse_args()

    report = load_report(args.report_path)
    analysis = analyze_report_data(report, top_n=args.top_n)
    output_path = Path(args.output_path) if args.output_path else build_default_output_path(args.report_path)
    saved_path = save_analysis(analysis, output_path)
    print_analysis(analysis)
    print(f"\nSaved analysis to {saved_path}")


if __name__ == "__main__":
    main()
