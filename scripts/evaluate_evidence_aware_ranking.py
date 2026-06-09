#!/usr/bin/env python3
"""P0: Evidence-aware Ranking Calibration Evaluation.

Answers: "If evidence-aware ranking replaces legacy top1, does usable/executable/LCS/SetF1
improve?" Produces stratified analysis and PASS/FAIL/NEEDS_CALIBRATION verdict.

Usage:
    python scripts/evaluate_evidence_aware_ranking.py \
        --report outputs_v2/v4_qg_planner_reports/phase1_candidate_rerank/planner_report.json \
        --output-dir outputs_v2/p0_evidence_aware_calibration
"""

from __future__ import annotations

import argparse
import copy
import json
import sys
from collections import defaultdict
from collections import Counter
from pathlib import Path
from typing import Optional

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(SRC))

from gis_recommend.evaluation.shadow_phase import select_evidence_aware_candidate  # noqa: E402
from gis_recommend.evaluation.semantic_metrics import SemanticMetricsCalculator  # noqa: E402


def _mean(values: list[float]) -> Optional[float]:
    return sum(values) / len(values) if values else None


def _rate(numerator: int, denominator: int) -> float:
    return round(numerator / max(denominator, 1), 6)


def _fmt_optional(value: Optional[float]) -> str:
    return "NA" if value is None else f"{value:.4f}"


def _as_metric_float(value) -> Optional[float]:
    if value is None:
        return None
    return float(value)


def compute_candidate_metrics(tokens: list[int], reference_tokens: Optional[list[int]]) -> Optional[dict]:
    """Compute observable reference metrics for offline calibration only."""
    if reference_tokens is None:
        return None
    return {
        "set_f1": round(SemanticMetricsCalculator.set_f1(tokens, reference_tokens), 6),
        "lcs_ratio": round(SemanticMetricsCalculator.lcs_ratio(tokens, reference_tokens), 6),
        "token_accuracy": round(SemanticMetricsCalculator.token_accuracy(tokens, reference_tokens), 6),
        "sequence_em": bool(SemanticMetricsCalculator.sequence_em(tokens, reference_tokens)),
    }


def build_evidence_aware_selection(candidates: list[dict]) -> dict:
    """Select a candidate with observable support without mutating inputs."""
    if not candidates:
        return {"candidate_id": None, "tokens": None, "score_terms": {}, "observable_terms": [], "missing_terms": []}

    best: Optional[dict] = None
    best_score = float("-inf")
    for candidate in candidates:
        row = copy.deepcopy(candidate)
        raw_score = row.get("raw_score")
        score_terms = {"raw_score": _as_metric_float(raw_score)}
        observable_terms: list[str] = []
        missing_terms: list[str] = []

        if raw_score is None:
            score = 0.0
            missing_terms.append("raw_score_missing")
        else:
            score = float(raw_score)

        if row.get("candidate_origin") == "synthetic":
            score -= 1000.0
            observable_terms.append("synthetic_candidate")
        if row.get("source") == "retrieval_shadow":
            score += 0.1
            observable_terms.append("retrieval_shadow")
        if row.get("task_type_match") is True:
            score += 0.2
            observable_terms.append("task_type_match")
        if row.get("local_transition_valid") is True:
            score += 0.2
            observable_terms.append("local_transition_valid")

        row["evidence_aware_score"] = round(score, 6)
        row["score_terms"] = score_terms
        row["observable_terms"] = observable_terms
        row["missing_terms"] = missing_terms
        if score > best_score:
            best_score = score
            best = row

    return best or {"candidate_id": None, "tokens": None, "score_terms": {}, "observable_terms": [], "missing_terms": []}


def evaluate_records(records: list[dict]) -> dict:
    """Evaluate offline candidate records without writing back to records."""
    samples = []
    legacy_setf1: list[float] = []
    ea_setf1: list[float] = []
    legacy_usable: list[float] = []
    ea_usable: list[float] = []

    for record in copy.deepcopy(records):
        candidates = record.get("candidates") or []
        reference_tokens = record.get("reference_tokens")
        legacy = next((c for c in candidates if c.get("legacy_selected")), None)
        ea = build_evidence_aware_selection(candidates)

        legacy_metrics = compute_candidate_metrics(legacy.get("tokens", []), reference_tokens) if legacy else None
        ea_metrics = compute_candidate_metrics(ea.get("tokens", []), reference_tokens) if ea.get("tokens") is not None else None

        if legacy_metrics:
            legacy_setf1.append(legacy_metrics["set_f1"])
        if ea_metrics:
            ea_setf1.append(ea_metrics["set_f1"])
        if legacy is not None and "usable" in legacy:
            legacy_usable.append(1.0 if legacy.get("usable") else 0.0)
        if "usable" in ea:
            ea_usable.append(1.0 if ea.get("usable") else 0.0)

        samples.append({
            "sample_id": record.get("sample_id"),
            "legacy_candidate_id": legacy.get("candidate_id") if legacy else None,
            "evidence_aware_candidate_id": ea.get("candidate_id"),
            "legacy_metrics": legacy_metrics,
            "evidence_aware_metrics": ea_metrics,
            "diagnostic_metrics": {
                "token_accuracy": (ea_metrics or {}).get("token_accuracy"),
                "sequence_em": (ea_metrics or {}).get("sequence_em"),
            },
        })

    return {
        "summary": {
            "sample_count": len(records),
            "primary_metrics": {
                "set_f1": {
                    "legacy_mean": _mean(legacy_setf1),
                    "evidence_aware_mean": _mean(ea_setf1),
                    "delta_mean": _delta_mean(legacy_setf1, ea_setf1),
                },
                "usable_rate": {
                    "legacy_mean": _mean(legacy_usable),
                    "evidence_aware_mean": _mean(ea_usable),
                    "delta_mean": _delta_mean(legacy_usable, ea_usable),
                },
            },
            "metric_interpretation": {
                "set_f1": "primary_multi_solution_operator_set_overlap",
                "usable": "primary_workflow_usability_signal",
                "executable": "primary_execution_feasibility_signal",
                "qgis_mapping": "primary_platform_mapping_signal",
                "lcs": "supporting_sequence_order_signal",
                "token_accuracy": "positional_reference_reproduction_diagnostic_not_workflow_correctness",
                "sequence_em": "strict_reference_reproduction_diagnostic_not_primary",
            },
        },
        "samples": samples,
    }


def render_markdown(result: dict) -> str:
    summary = result.get("summary") or {}
    primary = summary.get("primary_metrics") or {}
    interpretation = summary.get("metric_interpretation") or {}
    lines = [
        "# Evidence-aware Ranking Evaluation",
        "",
        "## Primary Multi-solution Signals",
        "| Metric | Legacy | Evidence-aware | Delta |",
        "|--------|--------|----------------|-------|",
    ]
    for metric in ("set_f1", "usable_rate"):
        row = primary.get(metric) or {}
        lines.append(
            f"| {metric} | {_fmt_optional(row.get('legacy_mean'))} | "
            f"{_fmt_optional(row.get('evidence_aware_mean'))} | {_fmt_optional(row.get('delta_mean'))} |"
        )
    lines.extend([
        "",
        "## Diagnostic",
        f"- TokenAcc: {interpretation.get('token_accuracy')}",
        f"- Sequence EM: {interpretation.get('sequence_em')}",
    ])
    return "\n".join(lines)


def main(argv: Optional[list[str]] = None) -> dict:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", type=Path, required=True,
                        help="Path to planner_report.json or evaluation_report.json")
    parser.add_argument("--output-dir", type=Path,
                        default=ROOT / "outputs_v2" / "p0_evidence_aware_calibration")
    parser.add_argument("--min-samples", type=int, default=50,
                        help="Minimum samples for PASS verdict")
    args = parser.parse_args(argv)

    with open(args.report, "r", encoding="utf-8") as f:
        report = json.load(f)

    per_sample = report.get("per_sample", [])
    if not per_sample:
        print("ERROR: report has no per_sample data")
        return {"verdict": "FAIL", "reason": "no_per_sample_data"}

    legacy_metrics: dict[str, list[float]] = defaultdict(list)
    ea_metrics: dict[str, list[float]] = defaultdict(list)

    by_task: dict[str, dict] = defaultdict(lambda: {"legacy": defaultdict(list), "ea": defaultdict(list), "samples": 0})
    by_pool_size: dict[str, dict] = defaultdict(lambda: {"legacy": defaultdict(list), "ea": defaultdict(list), "samples": 0})
    ea_differs_count = 0
    synthetic_count = 0
    total_valid = 0
    primary_improved = 0
    primary_regressed = 0
    per_sample_comparison_count = 0

    for sample in per_sample:
        dt = sample.get("decision_trace") or {}
        ea_sel = dt.get("evidence_aware_selection") or {}
        ea_rank = dt.get("evidence_aware_ranking") or {}
        comparison_metrics = ea_rank.get("comparison_metrics") or {}
        legacy_cmp = comparison_metrics.get("legacy") or {}
        ea_cmp = comparison_metrics.get("evidence_aware") or {}

        l_setf1 = sample.get("set_f1")
        l_lcs = sample.get("lcs_ratio")
        usable_info = (sample.get("selected") or {}).get("usability") or {}
        l_usable = 1.0 if usable_info.get("usable") else None
        l_exec = usable_info.get("executable_qgis_mapping_rate")

        if l_setf1 is None and l_lcs is None and not comparison_metrics:
            continue

        total_valid += 1
        if comparison_metrics:
            per_sample_comparison_count += 1
        if ea_sel.get("differs_from_legacy"):
            ea_differs_count += 1
        if legacy_cmp.get("available"):
            for metric_name in ("set_f1", "lcs_ratio", "usable", "executable", "qgis_mapping"):
                value = legacy_cmp.get(metric_name)
                if value is not None:
                    legacy_metrics[metric_name].append(float(value))
        if ea_cmp.get("available"):
            for metric_name in ("set_f1", "lcs_ratio", "usable", "executable", "qgis_mapping"):
                value = ea_cmp.get(metric_name)
                if value is not None:
                    ea_metrics[metric_name].append(float(value))

        if legacy_cmp.get("available") and ea_cmp.get("available"):
            improved_primary = False
            regressed_primary = False
            for metric_name in ("set_f1", "usable", "executable", "qgis_mapping"):
                legacy_value = legacy_cmp.get(metric_name)
                ea_value = ea_cmp.get(metric_name)
                if legacy_value is None or ea_value is None:
                    continue
                if float(ea_value) > float(legacy_value):
                    improved_primary = True
                if float(ea_value) < float(legacy_value):
                    regressed_primary = True
            if improved_primary and not regressed_primary:
                primary_improved += 1
            elif regressed_primary and not improved_primary:
                primary_regressed += 1

        task = sample.get("task_type", "unknown")
        if legacy_cmp.get("available"):
            for metric_name in ("set_f1", "lcs_ratio", "usable", "executable", "qgis_mapping"):
                value = legacy_cmp.get(metric_name)
                if value is not None:
                    by_task[task]["legacy"][metric_name].append(float(value))
        if ea_cmp.get("available"):
            for metric_name in ("set_f1", "lcs_ratio", "usable", "executable", "qgis_mapping"):
                value = ea_cmp.get(metric_name)
                if value is not None:
                    by_task[task]["ea"][metric_name].append(float(value))
        by_task[task]["samples"] += 1

        pool_sz = len((dt.get("evidence_aware_ranking") or {}).get("selections") or {})
        sz_bucket = "1" if pool_sz <= 1 else ("2-3" if pool_sz <= 3 else "4+")
        if legacy_cmp.get("available"):
            for metric_name in ("set_f1", "lcs_ratio", "usable", "executable", "qgis_mapping"):
                value = legacy_cmp.get(metric_name)
                if value is not None:
                    by_pool_size[sz_bucket]["legacy"][metric_name].append(float(value))
        if ea_cmp.get("available"):
            for metric_name in ("set_f1", "lcs_ratio", "usable", "executable", "qgis_mapping"):
                value = ea_cmp.get(metric_name)
                if value is not None:
                    by_pool_size[sz_bucket]["ea"][metric_name].append(float(value))
        by_pool_size[sz_bucket]["samples"] += 1

        ctx = (dt.get("observation_coverage") or {}).get("observation_context") or {}
        if ctx.get("synthetic_candidate_present"):
            synthetic_count += 1

    n = max(total_valid, 1)
    primary_metrics = {
        metric: {
            "legacy_mean": _mean(legacy_metrics[metric]),
            "evidence_aware_mean": _mean(ea_metrics[metric]),
            "delta_mean": _delta_mean(legacy_metrics[metric], ea_metrics[metric]),
            "sample_count": max(len(legacy_metrics[metric]), len(ea_metrics[metric])),
        }
        for metric in ("set_f1", "usable", "executable", "qgis_mapping")
    }
    primary_metrics["usable_rate"] = dict(primary_metrics["usable"])
    supporting_metrics = {
        "lcs": {
            "legacy_mean": _mean(legacy_metrics["lcs_ratio"]),
            "evidence_aware_mean": _mean(ea_metrics["lcs_ratio"]),
            "delta_mean": _delta_mean(legacy_metrics["lcs_ratio"], ea_metrics["lcs_ratio"]),
            "sample_count": max(len(legacy_metrics["lcs_ratio"]), len(ea_metrics["lcs_ratio"])),
        }
    }

    reasons = []
    verdict = "PASS"
    if n < args.min_samples or per_sample_comparison_count == 0:
        verdict = "NEEDS_CALIBRATION"
        if n < args.min_samples:
            reasons.append(f"insufficient_samples ({n} < {args.min_samples})")
        if per_sample_comparison_count == 0:
            reasons.append("no_comparable_per_sample_data")
    if ea_differs_count == 0:
        verdict = "NEEDS_CALIBRATION"
        reasons.append("ea_never_differs_from_legacy")
    if verdict == "PASS" and primary_improved == 0:
        verdict = "NEEDS_CALIBRATION"
        reasons.append("primary_metric_not_improved")
    if primary_regressed > 0 and verdict == "PASS":
        verdict = "NEEDS_CALIBRATION"
        reasons.append("primary_metric_regressed_on_some_samples")

    task_summary = {}
    for task, data in sorted(by_task.items()):
        if data["legacy"]:
            task_summary[task] = {
                "sample_count": data["samples"],
                "legacy_setf1_mean": _mean(data["legacy"]["set_f1"]),
                "evidence_aware_setf1_mean": _mean(data["ea"]["set_f1"]),
                "set_f1_delta_mean": _delta_mean(data["legacy"]["set_f1"], data["ea"]["set_f1"]),
                "legacy_usable_mean": _mean(data["legacy"]["usable"]),
                "evidence_aware_usable_mean": _mean(data["ea"]["usable"]),
            }

    pool_summary = {}
    for bucket, data in sorted(by_pool_size.items()):
        pool_summary[bucket] = {
            "sample_count": data["samples"],
            "legacy_setf1_mean": _mean(data["legacy"]["set_f1"]),
            "evidence_aware_setf1_mean": _mean(data["ea"]["set_f1"]),
            "set_f1_delta_mean": _delta_mean(data["legacy"]["set_f1"], data["ea"]["set_f1"]),
        }

    result = {
        "verdict": verdict,
        "reasons": reasons or ["no_critical_issues_detected"],
        "sample_info": {
            "total_samples": len(per_sample),
            "valid_samples_for_eval": total_valid,
            "comparable_samples": per_sample_comparison_count,
            "ea_differs_from_legacy_count": ea_differs_count,
            "ea_differs_rate": _rate(ea_differs_count, n),
            "primary_improved_count": primary_improved,
            "primary_regressed_count": primary_regressed,
            "primary_improved_rate": _rate(primary_improved, n),
            "synthetic_present_count": synthetic_count,
        },
        "primary_metrics": primary_metrics,
        "supporting_metrics": supporting_metrics,
        "stratified": {
            "by_task_type": task_summary,
            "by_pool_size": pool_summary,
        },
        "metric_contract": {
            "primary": ["set_f1", "usable", "executable", "qgis_mapping"],
            "supporting": ["lcs"],
            "diagnostic_only": ["token_acc", "sequence_em"],
            "oracle": "candidate pool upper bound — not system capability",
            "multi_solution_policy": "TokenAcc is diagnostic only; SetF1/usable/executable/QGIS mapping are the primary signals.",
        },
    }

    args.output_dir.mkdir(parents=True, exist_ok=True)
    json_path = args.output_dir / "evidence_aware_calibration.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    md_lines = [
        f"# P0 Evidence-aware Ranking Calibration",
        "",
        f"**Verdict**: {verdict}",
        "",
        f"- Report: {args.report}",
        f"- Valid samples: {total_valid}/{len(per_sample)}",
        f"- Comparable samples: {per_sample_comparison_count}/{len(per_sample)}",
        f"- EA differs from legacy: {ea_differs_count}/{n} ({_rate(ea_differs_count, n):.1%})",
        f"- Primary improvement count: {primary_improved}",
        f"- Primary regression count: {primary_regressed}",
        f"- Legacy SetF1 mean: {primary_metrics['set_f1']['legacy_mean']}",
        f"- Evidence-aware SetF1 mean: {primary_metrics['set_f1']['evidence_aware_mean']}",
        f"- Legacy usable mean: {primary_metrics['usable']['legacy_mean']}",
        f"- Evidence-aware usable mean: {primary_metrics['usable']['evidence_aware_mean']}",
        "",
        "## Reasons",
        *(f"- {r}" for r in (reasons or ["none"])),
        "",
        "## Metric Contract",
        "- **Primary**: SetF1, Usable, Executable, QGIS Mapping",
        "- **Supporting**: LCS",
        "- **Diagnostic only**: TokenAcc, Sequence EM",
        "- **Oracle**: Candidate pool upper bound — not system capability",
        "- TokenAcc is positional reproduction only and must not be read as workflow correctness.",
        "",
        "## Per-Task SetF1",
        "| Task | Samples | Legacy SetF1 | EA SetF1 | Delta |",
        "|------|---------|-------------|----------|-------|",
        *(f"| {t} | {d['sample_count']} | {_fmt_optional(d['legacy_setf1_mean'])} |"
          f" {_fmt_optional(d['evidence_aware_setf1_mean'])} | {_fmt_optional(d['set_f1_delta_mean'])} |"
          for t, d in sorted(task_summary.items())),
        "",
        "## Per Pool Size",
        "| Bucket | Samples | Legacy SetF1 | EA SetF1 | Delta |",
        "|--------|---------|-------------|----------|-------|",
        *(f"| {b} | {d['sample_count']} | {_fmt_optional(d['legacy_setf1_mean'])} |"
          f" {_fmt_optional(d['evidence_aware_setf1_mean'])} | {_fmt_optional(d['set_f1_delta_mean'])} |"
          for b, d in sorted(pool_summary.items())),
        "",
        "## Next Steps",
        "- **PASS**: Proceed to shadow selector mainline comparison",
        "- **FAIL**: Investigate degradation source",
        "- **NEEDS_CALIBRATION**: Tune evidence-aware weights per task/source",
    ]
    (args.output_dir / "evidence_aware_calibration.md").write_text("\n".join(md_lines), encoding="utf-8")

    print(f"\nP0 Calibration complete. Verdict: {verdict}")
    print(f"  JSON: {json_path}")
    print(f"  MD:   {args.output_dir / 'evidence_aware_calibration.md'}")
    return result


def _delta_mean(left: list[float], right: list[float]) -> Optional[float]:
    if not left or not right:
        return None
    count = min(len(left), len(right))
    value = _mean([right[i] - left[i] for i in range(count)])
    return round(value, 6) if value is not None else None


if __name__ == "__main__":
    main()
