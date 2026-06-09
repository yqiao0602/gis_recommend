#!/usr/bin/env python3
"""Build a unified workflow-planning benchmark artifact.

This runner compares benchmark families without treating their metrics as the
same task.  It is an artifact unifier, not a training or inference launcher.
"""

from __future__ import annotations

import argparse
import json
import sys
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


SCHEMA_VERSION = "gis_recommend.workflow_benchmark.unified.v1"

DEFAULT_V4_TF_METRICS = {
    "loss": 2.5186,
    "perplexity": 12.4,
    "top1_accuracy": 0.483,
    "top5_accuracy": 0.713,
    "teacher_forced_sequence_exact_match": 0.023,
}
DEFAULT_V4_AR_METRICS = {
    "autoregressive_sequence_exact_match": 0.0,
    "autoregressive_token_accuracy": 0.211,
}
DEFAULT_SET_PREDICTOR_METRICS = {
    "set_f1": 0.7113795280456543,
}


def build_metric_row(
    *,
    system: str,
    task: str,
    prediction_mode: str,
    metric_scope: str,
    vocabulary: str,
    metrics: dict,
    source: dict,
    data_family: str = "quality_gate_v2",
    notes: Optional[list[str]] = None,
) -> dict:
    teacher_forced = prediction_mode == "teacher_forced"
    rollout = prediction_mode == "rollout"
    retrieval_based = "retrieval" in task or prediction_mode in {"retrieval", "retrieval_hybrid"}
    set_based = task == "operator_set_prediction" or metric_scope == "set"
    generation_based = "generation" in task or prediction_mode in {"rollout", "autoregressive_generation"}
    return {
        "system": str(system),
        "task": str(task),
        "data_family": str(data_family),
        "vocabulary": str(vocabulary),
        "prediction_mode": str(prediction_mode),
        "metric_scope": str(metric_scope),
        "teacher_forced": bool(teacher_forced),
        "rollout": bool(rollout),
        "retrieval_based": bool(retrieval_based),
        "generation_based": bool(generation_based and not retrieval_based),
        "set_based": bool(set_based),
        "metrics": _round_metrics(metrics),
        "source": dict(source),
        "comparison_group_id": _comparison_group_id(task, prediction_mode, metric_scope, vocabulary),
        "notes": list(notes or []),
    }


def build_comparison_groups(rows: Sequence[dict]) -> list[dict]:
    grouped: dict[str, list[dict]] = {}
    for row in rows:
        grouped.setdefault(row["comparison_group_id"], []).append(row)
    groups = []
    for group_id, members in sorted(grouped.items()):
        exemplar = members[0]
        groups.append(
            {
                "group_id": group_id,
                "task": exemplar["task"],
                "prediction_modes": sorted({row["prediction_mode"] for row in members}),
                "metric_scope": exemplar["metric_scope"],
                "vocabulary": exemplar["vocabulary"],
                "systems": [row["system"] for row in members],
                "direct_comparison_allowed": True,
                "rule": "Only rows sharing this exact task/scope/vocabulary group may be directly compared; prediction_mode remains explicit in each row.",
            }
        )
    return groups


def build_unified_benchmark(
    *,
    v5_report_path: Path,
    hybrid_report_path: Path,
    output_path: Optional[Path],
    v4_tf_metrics: Optional[dict] = None,
    v4_ar_metrics: Optional[dict] = None,
    set_predictor_metrics: Optional[dict] = None,
) -> dict:
    rows = [
        build_metric_row(
            system="v4_quality_gate_teacher_forced",
            task="operator_token_prediction",
            prediction_mode="teacher_forced",
            metric_scope="token",
            vocabulary="v2_l3_98",
            metrics=v4_tf_metrics or DEFAULT_V4_TF_METRICS,
            source={
                "type": "external_reported_metric",
                "path": str(OUTPUT_DIR / "transformer_checkpoints_v4_2_quality_gate" / "training_history_v4_2.json"),
                "available_locally": (OUTPUT_DIR / "transformer_checkpoints_v4_2_quality_gate" / "training_history_v4_2.json").exists(),
            },
            notes=["Teacher-forced token metrics must not be compared directly with rollout metrics."],
        ),
        build_metric_row(
            system="v4_quality_gate_autoregressive",
            task="autoregressive_workflow_generation",
            prediction_mode="rollout",
            metric_scope="sequence",
            vocabulary="v2_l3_98",
            metrics=v4_ar_metrics or DEFAULT_V4_AR_METRICS,
            source={
                "type": "external_reported_metric",
                "path": str(OUTPUT_DIR / "transformer_checkpoints_v4_2_quality_gate" / "training_history_v4_2.json"),
                "available_locally": (OUTPUT_DIR / "transformer_checkpoints_v4_2_quality_gate" / "training_history_v4_2.json").exists(),
            },
            notes=["Rollout AR metrics are comparable to generation rollouts, not teacher-forced Top1/Top5."],
        ),
        build_metric_row(
            system="set_predictor_quality_gate",
            task="operator_set_prediction",
            prediction_mode="set_prediction",
            metric_scope="set",
            vocabulary="v2_l3_active_47",
            metrics=set_predictor_metrics or DEFAULT_SET_PREDICTOR_METRICS,
            source={
                "type": "external_reported_metric",
                "path": str(OUTPUT_DIR / "set_predictor_checkpoints_v3_quality_gate"),
                "available_locally": (OUTPUT_DIR / "set_predictor_checkpoints_v3_quality_gate").exists(),
            },
            notes=["SetF1 is a set prediction metric and must not be mixed with sequence-token accuracy."],
        ),
    ]
    rows.extend(_rows_from_v5_report(Path(v5_report_path)))
    rows.extend(_rows_from_hybrid_report(Path(hybrid_report_path)))

    artifact = {
        "schema_version": SCHEMA_VERSION,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "benchmark_protocol": {
            "data_family": "outputs_v2_quality_gate",
            "cross_task_metric_mixing_allowed": False,
            "teacher_forced_vs_rollout_direct_comparison_allowed": False,
            "set_vs_sequence_direct_comparison_allowed": False,
            "retrieval_performance_is_not_generation_capability": True,
            "architecture_reopened": False,
        },
        "benchmark_rows": rows,
        "comparison_groups": build_comparison_groups(rows),
        "benchmark_family_summary": _family_summary(rows),
        "interpretation_guardrails": [
            "Do not compare V4 teacher-forced Top1/Top5 directly against V5 rollout token accuracy.",
            "Do not inflate retrieval-centered planning metrics into pure generation capability.",
            "Use Set Predictor SetF1 as operator-set evidence, not as sequence planning accuracy.",
            "Pure autoregressive rollout remains a separate task from retrieval-centered planning.",
        ],
    }
    if output_path is not None:
        _write_json(Path(output_path), artifact)
        _write_markdown(Path(output_path).with_suffix(".md"), artifact)
    return artifact


def _rows_from_v5_report(path: Path) -> list[dict]:
    if not path.exists():
        return [
            build_metric_row(
                system="v5_final_pure_generation",
                task="autoregressive_workflow_generation",
                prediction_mode="rollout",
                metric_scope="sequence",
                vocabulary="v2_l3_98",
                metrics={},
                source={"type": "missing_artifact", "path": str(path), "available_locally": False},
                notes=["V5 report path was missing when the unified benchmark was built."],
            )
        ]
    payload = _load_json(path)
    metrics = payload.get("metrics", {})
    selected = {
        "token_accuracy": metrics.get("token_accuracy"),
        "lcs_ratio": metrics.get("lcs_ratio"),
        "set_f1": metrics.get("set_f1"),
        "sequence_exact_match": metrics.get("sequence_em", metrics.get("exact_match")),
        "top5_token_accuracy": metrics.get("top5_token_accuracy"),
        "perplexity": metrics.get("perplexity"),
        "io_validity": metrics.get("io_validity"),
        "avg_abs_length_error": metrics.get("avg_abs_length_error"),
    }
    return [
        build_metric_row(
            system="v5_final_pure_generation",
            task="autoregressive_workflow_generation",
            prediction_mode="rollout",
            metric_scope="sequence",
            vocabulary="v2_l3_98",
            metrics=_drop_none(selected),
            source={"type": "artifact", "path": str(path), "schema_version": payload.get("schema_version"), "available_locally": True},
            notes=["V5_final pure generation is a rollout/generation baseline, not retrieval planning."],
        )
    ]


def _rows_from_hybrid_report(path: Path) -> list[dict]:
    if not path.exists():
        return [
            build_metric_row(
                system="retrieval_centered_planner_retrieval_only",
                task="retrieval_centered_workflow_planning",
                prediction_mode="retrieval",
                metric_scope="sequence",
                vocabulary="v2_l3_98",
                metrics={},
                source={"type": "missing_artifact", "path": str(path), "available_locally": False},
            ),
            build_metric_row(
                system="retrieval_centered_planner_hybrid",
                task="retrieval_centered_workflow_planning",
                prediction_mode="retrieval_hybrid",
                metric_scope="sequence",
                vocabulary="v2_l3_98",
                metrics={},
                source={"type": "missing_artifact", "path": str(path), "available_locally": False},
            ),
        ]
    payload = _load_json(path)
    metrics = payload.get("metrics", {})
    rows = []
    for system, key, mode in [
        ("retrieval_centered_planner_retrieval_only", "retrieval_only", "retrieval"),
        ("retrieval_centered_planner_hybrid", "hybrid", "retrieval_hybrid"),
    ]:
        row_metrics = metrics.get(key, {}) or {}
        selected = {
            "token_accuracy": row_metrics.get("token_accuracy"),
            "lcs_ratio": row_metrics.get("lcs_ratio"),
            "set_f1": row_metrics.get("set_f1"),
            "sequence_exact_match": row_metrics.get("sequence_em", row_metrics.get("exact_match")),
            "top5_sequence_accuracy": row_metrics.get("top5_sequence_accuracy"),
            "io_validity": row_metrics.get("io_validity"),
            "executable_completion": row_metrics.get("executable_completion"),
            "avg_abs_length_error": row_metrics.get("avg_abs_length_error"),
        }
        if key == "hybrid":
            selected["rerank_lcs_delta"] = (payload.get("contribution_attribution", {}).get("rerank_contribution", {}) or {}).get("lcs_delta")
            selected["repair_lcs_delta"] = (payload.get("contribution_attribution", {}).get("repair_contribution", {}) or {}).get("lcs_delta")
        rows.append(
            build_metric_row(
                system=system,
                task="retrieval_centered_workflow_planning",
                prediction_mode=mode,
                metric_scope="sequence",
                vocabulary="v2_l3_98",
                metrics=_drop_none(selected),
                source={"type": "artifact", "path": str(path), "schema_version": payload.get("schema_version"), "available_locally": True},
                notes=["Retrieval-centered planning metrics must not be reported as pure generation."],
            )
        )
    return rows


def _family_summary(rows: Sequence[dict]) -> dict:
    by_system = {row["system"]: row for row in rows}
    return {
        "best_current_execution_direction": "retrieval_centered_workflow_planning",
        "operator_set_signal": by_system.get("set_predictor_quality_gate", {}).get("metrics", {}),
        "pure_generation_rows": [
            row["system"]
            for row in rows
            if row["task"] == "autoregressive_workflow_generation"
        ],
        "retrieval_planning_rows": [
            row["system"]
            for row in rows
            if row["task"] == "retrieval_centered_workflow_planning"
        ],
        "caution": "This summary names benchmark families only; direct metric comparison is limited to comparison_groups.",
    }


def _comparison_group_id(task: str, prediction_mode: str, metric_scope: str, vocabulary: str) -> str:
    del prediction_mode
    return f"{task}|{metric_scope}|{vocabulary}"


def _round_metrics(metrics: dict) -> dict:
    out = {}
    for key, value in metrics.items():
        if isinstance(value, float):
            out[key] = round(value, 8)
        else:
            out[key] = value
    return out


def _drop_none(metrics: dict) -> dict:
    return {key: value for key, value in metrics.items() if value is not None}


def _load_json(path: Path) -> dict:
    with Path(path).open("r", encoding="utf-8") as f:
        payload = json.load(f)
    if not isinstance(payload, dict):
        raise ValueError(f"Expected JSON object: {path}")
    return payload


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _write_markdown(path: Path, artifact: dict) -> None:
    lines = [
        "# Unified Workflow Benchmark",
        "",
        f"Schema: `{artifact['schema_version']}`",
        "",
        "## Protocol",
        "",
        "- Cross-task metric mixing is forbidden.",
        "- Teacher-forced token prediction, rollout generation, retrieval planning, and set prediction are separate benchmark families.",
        "- Retrieval-centered scores are planning metrics, not pure generation metrics.",
        "",
        "## Rows",
        "",
        "| System | Task | Mode | Scope | Vocabulary | Key Metrics |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for row in artifact["benchmark_rows"]:
        metrics = ", ".join(f"{key}={value}" for key, value in row.get("metrics", {}).items())
        lines.append(
            f"| `{row['system']}` | `{row['task']}` | `{row['prediction_mode']}` | "
            f"`{row['metric_scope']}` | `{row['vocabulary']}` | {metrics} |"
        )
    lines.extend(
        [
            "",
            "## Comparison Groups",
            "",
            "| Group | Systems | Rule |",
            "| --- | --- | --- |",
        ]
    )
    for group in artifact["comparison_groups"]:
        systems = ", ".join(f"`{system}`" for system in group["systems"])
        lines.append(f"| `{group['group_id']}` | {systems} | {group['rule']} |")
    lines.extend(
        [
            "",
            "## Guardrails",
            "",
            *[f"- {item}" for item in artifact["interpretation_guardrails"]],
            "",
        ]
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--v5-report", type=Path, default=OUTPUT_DIR / "v5_final_reports" / "stage1" / "evaluation_report.json")
    parser.add_argument(
        "--hybrid-report",
        type=Path,
        default=OUTPUT_DIR / "v5_final_reports" / "v5_hybrid_planner_multistage" / "hybrid_planner_report.json",
    )
    parser.add_argument("--out", type=Path, default=OUTPUT_DIR / "v5_final_reports" / "unified_benchmark" / "unified_workflow_benchmark.json")
    return parser


def main(argv: Optional[list[str]] = None) -> dict:
    args = _build_parser().parse_args(argv)
    artifact = build_unified_benchmark(
        v5_report_path=args.v5_report,
        hybrid_report_path=args.hybrid_report,
        output_path=args.out,
    )
    print(f"Wrote unified benchmark: {args.out}")
    print(f"Wrote markdown summary: {args.out.with_suffix('.md')}")
    return artifact


if __name__ == "__main__":
    main()
