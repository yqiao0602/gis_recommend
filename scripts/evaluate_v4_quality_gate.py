#!/usr/bin/env python3
"""V4.6 Quality-Gate 候选/研究评估脚本。

与通用 evaluation/runner.py 的区别：
  - 数据: quality-gate 候选集（而非原始 Step8）
  - Splits: quality-gate 分组 split（而非通用 dataset_splits_v4.json）
  - Checkpoint: V4.6 quality-gate（V4.6 训练 + quality-gate 数据）
  - Set Predictor: V4.6 quality-gate 版本
  - 输出: outputs_v2/v4_quality_gate_evaluation/

所有路径在 transformer_config.py 的 V4_6_QG_* 常量中定义，
无需命令行覆盖。当前主线入口是 Step8 + V4.6 的 gis-evaluate；
本脚本输出必须视为 quality-gate candidate / research artifact。

使用方式：
    python scripts/evaluate_v4_quality_gate.py                    # smoke (200 samples)
    python scripts/evaluate_v4_quality_gate.py --eval-mode dev    # dev (1000 samples)
    python scripts/evaluate_v4_quality_gate.py --eval-mode full   # 全量测试集
    python scripts/evaluate_v4_quality_gate.py --samples 50       # 精确50个样本
    python scripts/evaluate_v4_quality_gate.py --skip-qgis        # 跳过 QGIS chain 评估
    python scripts/evaluate_v4_quality_gate.py --oracle           # 计算 oracle 指标
"""

from __future__ import annotations

import argparse
import json
import random
import sys
import time
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

import torch
from tqdm import tqdm

# ═════════════════════════════════════════════════════════════════
# 在导入其他模块之前，先覆盖关键路径为 quality-gate 版本
# ═════════════════════════════════════════════════════════════════
import gis_recommend.config.transformer_config as cfg

# 保存原始值
_saved_v4_labeled = cfg.V4_LABELED_WORKFLOWS_PATH
_saved_v4_task_vocab = cfg.V4_TASK_TYPE_VOCAB_PATH

# 切换到 quality-gate 路径
cfg.V4_LABELED_WORKFLOWS_PATH = cfg.V4_QG_LABELED_WORKFLOWS_PATH
cfg.V4_TASK_TYPE_VOCAB_PATH = cfg.V4_QG_TASK_TYPE_VOCAB_PATH

print(f"[QG Eval] Data path: {cfg.V4_LABELED_WORKFLOWS_PATH}")
print(f"[QG Eval] Task vocab path: {cfg.V4_TASK_TYPE_VOCAB_PATH}")

# 现在可以安全地导入使用这些常量的模块
from gis_recommend.config.transformer_config import (
    OUTPUT_DIR, V4_QG_LABELED_WORKFLOWS_PATH,
    V4_QG_SPLITS_PATH, V4_6_QG_TRANSFORMER_CHECKPOINT_DIR,
    V4_6_QG_SET_PREDICTOR_CHECKPOINT_DIR, V4_QG_EVALUATION_OUTPUT_DIR,
    L3_EMBEDDINGS_PATH, CLASSIFICATION_HIERARCHY, ID_MAPPINGS_PATH,
    SET_PREDICTOR_SOFT_PRIOR_THRESHOLD, SET_PREDICTOR_CONFIDENCE_THRESHOLD,
)
from gis_recommend.evaluation.semantic_metrics import (
    SemanticMetricsCalculator, SeqMetrics,
    compute_chain_metrics,
)
from gis_recommend.evaluation.sampling import (
    resolve_eval_max_samples, build_test_set,
)
from gis_recommend.data.length_bucket_predictor import (
    BUCKET_DEFS,
    LengthBucketPredictor,
    default_length_stats_path,
)
from gis_recommend.evaluation.diagnostics import (
    compute_oracle_analysis,
    summarize_reranker_diagnostics, print_reranker_diagnostics,
    summarize_repair_diagnostics, print_repair_diagnostics,
    compute_executable_ratio, print_executable_ratio, load_io_types,
)
from gis_recommend.evaluation.report import (
    resolve_report_output_paths, write_json_report,
    print_report, build_report_json,
)

SEED = 42
QG_TEST_SET_PATH = V4_QG_EVALUATION_OUTPUT_DIR / "evaluation_test_set.json"


def _metric_mean(metrics: dict, key: str, default: float = 0.0) -> float:
    value = metrics.get(key, default)
    if isinstance(value, dict):
        return float(value.get("mean", default))
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _mean(values: list[float]) -> float:
    return round(sum(values) / len(values), 6) if values else 0.0


def _chain_mean(rows: list[dict], key: str) -> float:
    vals = []
    for row in rows:
        try:
            vals.append(float(row.get(key, 0.0)))
        except (TypeError, ValueError):
            continue
    return _mean(vals)


def _content_tokens(tokens: list[int]) -> list[int]:
    return [int(token) for token in tokens if int(token) not in {-1, -2, -3, -4}]


def _prediction_tokens_from_result(l3_res: dict) -> list[int]:
    candidates = l3_res.get("all_candidates", []) if isinstance(l3_res, dict) else []
    if not candidates:
        return []
    top = candidates[0]
    if isinstance(top, dict):
        return [int(token) for token in top.get("tokens", [])]
    return [int(token) for token in getattr(top, "tokens", [])]


def _metric_float(metrics: dict, key: str) -> float:
    try:
        return float(metrics.get(key, 0.0))
    except (TypeError, ValueError):
        return 0.0


def build_complexity_bucket_report(
    test_set: list[dict],
    l3_results: list[dict],
    per_sample_metrics: list[dict],
    *,
    length_stats_path: Path | None = None,
    early_eos_ratio_threshold: float = 0.75,
    overlength_ratio_threshold: float = 1.35,
) -> dict:
    """Summarize rollout quality by task-type length bucket."""
    predictor = LengthBucketPredictor(length_stats_path or default_length_stats_path(ROOT))
    buckets: dict[str, list[dict]] = {}
    for idx, (sample, l3_res) in enumerate(zip(test_set, l3_results)):
        task = sample.get("task_metadata", {}) or {}
        task_type = task.get("task_type_normalized") or task.get("task_type") or "Unknown"
        bucket = predictor.predict(str(task_type)).bucket
        ref_tokens = _content_tokens(sample.get("l3_sequence", []) or [])
        pred_tokens = _content_tokens(_prediction_tokens_from_result(l3_res))
        ref_len = len(ref_tokens)
        pred_len = len(pred_tokens)
        ratio = (pred_len / ref_len) if ref_len else 0.0
        metrics = per_sample_metrics[idx] if idx < len(per_sample_metrics) else {}
        buckets.setdefault(bucket, []).append({
            "ref_len": ref_len,
            "pred_len": pred_len,
            "length_ratio": ratio,
            "early_eos": bool(ref_len and pred_len < ref_len * early_eos_ratio_threshold),
            "overlength": bool(ref_len and pred_len > ref_len * overlength_ratio_threshold),
            "set_f1": _metric_float(metrics, "set_f1"),
            "lcs_ratio": _metric_float(metrics, "lcs_ratio"),
            "token_accuracy": _metric_float(metrics, "token_accuracy"),
        })

    ordered = ["short", "medium", "long", "very_long"]
    by_bucket = {}
    for bucket in ordered:
        rows = buckets.get(bucket, [])
        n = len(rows)
        by_bucket[bucket] = {
            "n": n,
            "mean_ref_len": _mean([row["ref_len"] for row in rows]),
            "mean_pred_len": _mean([row["pred_len"] for row in rows]),
            "mean_length_ratio": _mean([row["length_ratio"] for row in rows]),
            "early_eos_rate": _mean([1.0 if row["early_eos"] else 0.0 for row in rows]),
            "overlength_rate": _mean([1.0 if row["overlength"] else 0.0 for row in rows]),
            "set_f1": _mean([row["set_f1"] for row in rows]),
            "lcs_ratio": _mean([row["lcs_ratio"] for row in rows]),
            "token_accuracy": _mean([row["token_accuracy"] for row in rows]),
        }
    return {
        "schema_version": "gis_recommend.v4_6_quality_gate.complexity_bucket_report.v1",
        "length_stats_path": str(length_stats_path or default_length_stats_path(ROOT)),
        "bucket_definitions": [
            {
                "bucket": item.bucket,
                "min_length": item.min_length,
                "eos_suppress_until": item.eos_suppress_until,
                "expected_length": item.expected_length,
            }
            for item in BUCKET_DEFS
        ],
        "thresholds": {
            "early_eos_ratio_threshold": early_eos_ratio_threshold,
            "overlength_ratio_threshold": overlength_ratio_threshold,
        },
        "by_bucket": by_bucket,
    }


def _extract_executable_ratio(executable_report: dict | None) -> float | None:
    if not isinstance(executable_report, dict):
        return None
    for container in (executable_report, executable_report.get("summary", {})):
        if not isinstance(container, dict):
            continue
        for key in ("executable_ratio", "chain_executable_ratio", "valid_ratio"):
            if key in container:
                try:
                    return round(float(container[key]), 6)
                except (TypeError, ValueError):
                    return None
    return None


def build_five_tier_report(
    *,
    n_samples: int,
    aggregate_l3_metrics: dict,
    qgis_report,
    executable_report,
    oracle_report,
) -> dict:
    """Build the planner-era metric view while preserving old raw metrics."""
    qgis_rows = qgis_report if isinstance(qgis_report, list) else []
    qgis_validity_rate = _chain_mean(qgis_rows, "validity")
    qgis_mapping_rate = _chain_mean(qgis_rows, "coverage")
    qgis_io_rate = _chain_mean(qgis_rows, "io_compatibility")
    unknown_ratio = _chain_mean(qgis_rows, "unknown_ratio")
    executable_ratio = _extract_executable_ratio(executable_report)
    if executable_ratio is None:
        executable_ratio = qgis_io_rate if qgis_rows else None

    tier1 = {
        "role": "diagnostic_only",
        "sequence_em": aggregate_l3_metrics.get("sequence_em", {"mean": 0.0}),
        "exact_match": aggregate_l3_metrics.get("exact_match", aggregate_l3_metrics.get("sequence_em", {"mean": 0.0})),
        "token_accuracy": aggregate_l3_metrics.get("token_accuracy", {"mean": 0.0}),
        "lcs_ratio": aggregate_l3_metrics.get("lcs_ratio", {"mean": 0.0}),
        "set_f1": aggregate_l3_metrics.get("set_f1", {"mean": 0.0}),
        "l2_accuracy": aggregate_l3_metrics.get("l2_accuracy", {"mean": 0.0}),
    }
    tier2_3 = {
        "role": "primary_kpi",
        "qgis_chain_validity_rate": qgis_validity_rate,
        "qgis_mapping_rate": qgis_mapping_rate,
        "qgis_io_compatibility_rate": qgis_io_rate,
        "qgis_unknown_ratio": unknown_ratio,
        "executable_chain_ratio": executable_ratio,
        "chain_sample_count": len(qgis_rows),
    }
    tier4 = {
        "role": "complexity_diagnostics",
        "mean_lcs_ratio": _metric_mean(aggregate_l3_metrics, "lcs_ratio"),
        "mean_token_accuracy": _metric_mean(aggregate_l3_metrics, "token_accuracy"),
        "mean_set_f1": _metric_mean(aggregate_l3_metrics, "set_f1"),
    }
    tier5 = {
        "role": "research_analysis",
        "oracle_available": oracle_report is not None,
        "oracle_summary": oracle_report,
    }
    return {
        "schema_version": "gis_recommend.v4_6_quality_gate_evaluation.five_tier.v1",
        "system_lineage": "research",
        "data_profile": "v4_quality_gate",
        "model_profile": "v4_6_quality_gate_candidate",
        "metric_scope": "quality_gate_candidate_evaluation",
        "mainline_eligible": False,
        "n_samples": int(n_samples),
        "primary_kpi": "tier2_3_workflow_usability",
        "tiers": {
            "tier1_sequence_diagnostics": tier1,
            "tier2_3_workflow_usability": tier2_3,
            "tier4_complexity_diagnostics": tier4,
            "tier5_research_analysis": tier5,
        },
        "metric_interpretation": {
            "sequence_em": "historical_workflow_reproduction_rate_not_correctness",
            "token_accuracy": "token_overlap_diagnostic_not_workflow_correctness",
            "lcs_ratio": "sequence_similarity_diagnostic_not_primary_kpi",
            "set_f1": "operator_set_overlap_diagnostic",
            "qgis_chain_validity_rate": "primary_downstream_chain_validity_signal_when_qgis_eval_runs",
            "executable_chain_ratio": "primary_local_io_compatibility_signal_when_enabled",
        },
        "governance": {
            "lineage": "research",
            "mainline_eligible": False,
            "non_mainline_reason": "Current mainline is Step8 + V4.6 gis-evaluate; V4-QG is a candidate/research profile.",
            "sequence_metrics_are_diagnostic": True,
            "usable_workflow_metrics_are_primary": True,
            "qgis_landing_is_downstream_signal": True,
        },
    }


def write_five_tier_markdown(
    path: Path,
    tiered_report: dict,
    complexity_bucket_report: dict | None = None,
) -> None:
    tiers = tiered_report.get("tiers", {})
    usability = tiers.get("tier2_3_workflow_usability", {})
    seq = tiers.get("tier1_sequence_diagnostics", {})
    complexity = tiers.get("tier4_complexity_diagnostics", {})
    interpretation = tiered_report.get("metric_interpretation", {})

    def m(metric: dict | float | int | None) -> float:
        if isinstance(metric, dict):
            return float(metric.get("mean", 0.0))
        if metric is None:
            return 0.0
        return float(metric)

    lines = [
        "# V4.6 Quality-Gate Evaluation Summary",
        "",
        f"Samples: {tiered_report.get('n_samples', 0)}",
        "",
        "## Primary KPIs - Workflow Usability",
        "",
        "| Metric | Value |",
        "| --- | ---: |",
        f"| QGIS chain validity rate | {m(usability.get('qgis_chain_validity_rate')):.4f} |",
        f"| QGIS mapping rate | {m(usability.get('qgis_mapping_rate')):.4f} |",
        f"| QGIS IO compatibility rate | {m(usability.get('qgis_io_compatibility_rate')):.4f} |",
        f"| Executable chain ratio | {m(usability.get('executable_chain_ratio')):.4f} |",
        f"| QGIS unknown ratio | {m(usability.get('qgis_unknown_ratio')):.4f} |",
        "",
        "## Tier 1 Sequence Diagnostics",
        "",
        "These metrics measure historical workflow reproduction, not correctness.",
        "",
        "| Metric | Mean |",
        "| --- | ---: |",
        f"| Sequence EM | {m(seq.get('sequence_em')):.4f} |",
        f"| Token accuracy | {m(seq.get('token_accuracy')):.4f} |",
        f"| LCS ratio | {m(seq.get('lcs_ratio')):.4f} |",
        f"| Set F1 | {m(seq.get('set_f1')):.4f} |",
        "",
        "## Tier 4 Complexity Diagnostics",
        "",
        f"- Mean LCS ratio: {m(complexity.get('mean_lcs_ratio')):.4f}",
        f"- Mean token accuracy: {m(complexity.get('mean_token_accuracy')):.4f}",
        f"- Mean Set F1: {m(complexity.get('mean_set_f1')):.4f}",
        "",
    ]
    if complexity_bucket_report:
        by_bucket = complexity_bucket_report.get("by_bucket", {})
        lines += [
            "### Complexity Bucket Rollout Diagnostics",
            "",
            "| Bucket | n | Ref Len | Pred Len | Len Ratio | Early EOS | Overlength | SetF1 | LCS | TokenAcc |",
            "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
        ]
        for bucket in ("short", "medium", "long", "very_long"):
            row = by_bucket.get(bucket, {}) or {}
            lines.append(
                f"| {bucket} | {int(row.get('n', 0) or 0)} | "
                f"{m(row.get('mean_ref_len')):.2f} | {m(row.get('mean_pred_len')):.2f} | "
                f"{m(row.get('mean_length_ratio')):.4f} | {m(row.get('early_eos_rate')):.4f} | "
                f"{m(row.get('overlength_rate')):.4f} | {m(row.get('set_f1')):.4f} | "
                f"{m(row.get('lcs_ratio')):.4f} | {m(row.get('token_accuracy')):.4f} |"
            )
        lines += [
            "",
            "Bucket diagnostics test whether length-bucket training reduces truncation and length drift by task complexity.",
            "",
        ]
    lines += [
        "## Interpretation Boundary",
        "",
        f"- `sequence_em`: {interpretation.get('sequence_em')}",
        "- Sequence metrics remain useful for debugging but are no longer the main success KPI.",
        "- QGIS chain metrics are downstream landing signals, not proof of GEE workflow semantic equivalence.",
        "",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def run_l3_inference_qg(test_set, device, checkpoint_path=None, sp_checkpoint=None,
                        disable_topk=False, set_prior_mode='soft'):
    """运行 L3 推理 — 使用 quality-gate checkpoint。"""
    from pathlib import Path as _Path

    if checkpoint_path:
        checkpoint = _Path(checkpoint_path)
    else:
        checkpoint = V4_6_QG_TRANSFORMER_CHECKPOINT_DIR / "best_model.pth"
        print(f"  [QG Eval] Defaulting to V4.6 quality-gate checkpoint: {checkpoint}")

    sp_path = (_Path(sp_checkpoint) if sp_checkpoint
               else V4_6_QG_SET_PREDICTOR_CHECKPOINT_DIR / "best_model.pth")

    if not checkpoint.exists():
        print(f"  [ERROR] V4.6 Quality-gate checkpoint not found: {checkpoint}")
        print(f"  [INFO]  Run training first: python scripts/train_v4_6_quality_gate.py")
        print(f"  [INFO]  Or copy the server checkpoint to: {checkpoint.parent}")
        raise FileNotFoundError(str(checkpoint))

    # 使用 QGInferencer 进行推理
    from gis_recommend.inference.infer_l3_candidates_v4_qg import QGInferencer

    inferencer = QGInferencer(
        checkpoint_path=checkpoint,
        device=device,
        set_predictor_path=sp_path,
    )
    inferencer.set_prior_mode = set_prior_mode
    if disable_topk and set_prior_mode == 'hard':
        inferencer.use_topk_set_prediction = False

    set_predictor_loaded = inferencer.set_predictor is not None
    effective_set_prior_mode = (
        set_prior_mode if (set_predictor_loaded or set_prior_mode == 'off') else 'off'
    )
    if set_prior_mode != 'off' and not set_predictor_loaded:
        print("  [WARN] Set predictor unavailable; constraints disabled")

    infer_meta = {
        "transformer_checkpoint": str(checkpoint),
        "set_predictor_checkpoint": str(sp_path),
        "set_predictor_loaded": set_predictor_loaded,
        "requested_set_prior_mode": set_prior_mode,
        "effective_set_prior_mode": effective_set_prior_mode,
        "use_topk_set_prediction": bool(inferencer.use_topk_set_prediction),
        "is_quality_gate": True,
    }

    l3_results = []
    for sample in tqdm(test_set, desc="QG L3 Inference", unit="sample"):
        task = sample.get("task_metadata", {})
        task_type = task.get("task_type_normalized", task.get("task_type", "Unknown"))
        task_name = task.get("task_name", "")
        task_desc = task.get("task_description", "")

        try:
            result = inferencer.infer(task_name, task_desc, task_type)
            l3_results.append(result)
        except Exception as exc:
            print(f"  [WARN] Inference failed for idx={sample.get('index', '?')}: {exc}")
            l3_results.append({"error": str(exc), "candidates": []})

    return l3_results, infer_meta


def main():
    parser = argparse.ArgumentParser(
        prog="evaluate-v4-qg",
        description="Evaluate V4 Quality-Gate candidate/research profile (standalone)",
    )
    parser.add_argument("--eval-mode", choices=["smoke", "dev", "full"], default="smoke",
                        help="Evaluation scale (default: smoke)")
    parser.add_argument("--samples", type=int, default=None,
                        help="Explicit sample count (overrides --eval-mode)")
    parser.add_argument("--skip-qgis", action="store_true",
                        help="Skip QGIS chain evaluation")
    parser.add_argument("--checkpoint", type=str, default=None,
                        help="Path to transformer checkpoint (default: QG best_model.pth)")
    parser.add_argument("--sp-checkpoint", type=str, default=None,
                        help="Path to set predictor checkpoint (default: QG dir)")
    parser.add_argument("--set-prior-mode", choices=["off", "soft", "hard"], default="soft")
    parser.add_argument("--no-topk", action="store_true",
                        help="Disable Top-K mode for set predictor (use threshold mode)")
    parser.add_argument("--oracle", action="store_true",
                        help="Compute oracle metrics from top-N candidates")
    parser.add_argument("--use-reranker", action="store_true",
                        help="Use structured reranker")
    parser.add_argument("--executable-check", action="store_true",
                        help="Compute executable chain ratio (Level 1)")
    parser.add_argument("--report-path", type=str, default=None,
                        help="Override report JSON output path")
    parser.add_argument("--seed", type=int, default=SEED)
    args = parser.parse_args()

    random.seed(args.seed)
    torch.manual_seed(args.seed)
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    effective_max_samples = resolve_eval_max_samples(args.eval_mode, args.samples)

    print("=" * 70)
    print("  V4.6 Quality-Gate Candidate/Research Evaluation")
    print("=" * 70)
    print(f"  Device: {device}")
    print(f"  Eval mode: {args.eval_mode}")
    print(f"  Effective max samples: {'full' if effective_max_samples is None else effective_max_samples}")
    print(f"  Data: {V4_QG_LABELED_WORKFLOWS_PATH}")
    print(f"  Checkpoint dir: {V4_6_QG_TRANSFORMER_CHECKPOINT_DIR}")
    print()

    # ── [1] Load data ──
    print("[1] Loading quality-gate data ...")
    with open(V4_QG_LABELED_WORKFLOWS_PATH, "r", encoding="utf-8") as f:
        raw = json.load(f)
    workflows = raw["labeled_workflows"] if isinstance(raw, dict) and "labeled_workflows" in raw else raw
    print(f"  Loaded {len(workflows)} workflows")

    # ── [2] Build test set (使用 quality-gate splits) ──
    print("\n[2] Building test set (quality-gate splits) ...")
    # 临时覆盖 sampling.py 的 SPLIT_PATH
    import gis_recommend.evaluation.sampling as sampling_mod
    _saved_split = sampling_mod.SPLIT_PATH
    sampling_mod.SPLIT_PATH = V4_QG_SPLITS_PATH

    test_set, coverage_info = build_test_set(workflows, max_samples=effective_max_samples)
    sampling_mod.SPLIT_PATH = _saved_split

    print(f"  Test samples: {len(test_set)}")
    print(f"  Task types included: {len(coverage_info['included'])}")
    if coverage_info.get('excluded'):
        print(f"  Task types excluded (<5 samples): {len(coverage_info['excluded'])}")

    V4_QG_EVALUATION_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    with open(QG_TEST_SET_PATH, "w", encoding="utf-8") as f:
        json.dump({"test_set": test_set, "coverage_info": coverage_info}, f,
                  ensure_ascii=False, indent=2)
    print(f"  Test set saved to {QG_TEST_SET_PATH}")

    # ── [3] L3 inference ──
    print("\n[3] Running L3 inference (quality-gate beam search) ...")
    t0 = time.time()
    l3_results, infer_meta = run_l3_inference_qg(
        test_set, device,
        checkpoint_path=args.checkpoint,
        sp_checkpoint=args.sp_checkpoint,
        disable_topk=args.no_topk,
        set_prior_mode=args.set_prior_mode,
    )
    t_infer = time.time() - t0
    print(f"  Done in {t_infer:.0f}s")

    # ── [4] Compute L3 metrics ──
    print("\n[4] Computing L3 sequence metrics ...")
    with open(ID_MAPPINGS_PATH, "r", encoding="utf-8") as f:
        id_mappings = json.load(f)
    l3_map = id_mappings.get("l3", {})
    id_to_l3_code = {int(v): k for k, v in l3_map.items()}

    calc = SemanticMetricsCalculator(
        l3_embeddings_path=L3_EMBEDDINGS_PATH,
        hierarchy_csv_path=CLASSIFICATION_HIERARCHY,
        id_to_l3_code=id_to_l3_code,
    )

    # 逐样本计算指标
    per_sample_metrics = []
    for sample, l3_res in zip(test_set, l3_results):
        ref = sample.get("l3_sequence", [])
        content_ref = [int(t) for t in ref if int(t) not in {-1, -2, -3, -4}]

        candidates = l3_res.get("all_candidates", []) if isinstance(l3_res, dict) else []
        top1_tokens = []
        if candidates and isinstance(candidates[0], dict):
            top1 = candidates[0]
            top1_tokens = [int(t) for t in top1.get("tokens", []) if int(t) not in {-1, -2, -3, -4}]

        metrics = calc.compute(top1_tokens, content_ref)
        metrics_dict = {
            "soft_set_sim": getattr(metrics, "soft_set_sim", 0.0),
            "sequence_em": float(getattr(metrics, "sequence_em", False)),
            "lcs_ratio": getattr(metrics, "lcs_ratio", 0.0),
            "token_accuracy": getattr(metrics, "token_accuracy", 0.0),
            "exact_match": float(getattr(metrics, "sequence_em", False)),
            "set_f1": getattr(metrics, "set_f1", 0.0),
            "l2_accuracy": getattr(metrics, "l2_accuracy", 0.0),
        }
        per_sample_metrics.append(metrics_dict)

    # 汇总
    n = len(per_sample_metrics)
    agg_metrics = {}
    for key in per_sample_metrics[0] if per_sample_metrics else []:
        vals = [m[key] for m in per_sample_metrics]
        agg_metrics[key] = {
            "mean": round(sum(vals) / n, 6) if n else 0.0,
            "min": round(min(vals), 6) if vals else 0.0,
            "max": round(max(vals), 6) if vals else 0.0,
        }

    print(f"\n  === L3 Metrics Summary (n={n}) ===")
    for k, v in agg_metrics.items():
        print(f"  {k:25s}: mean={v['mean']:.4f}  min={v['min']:.4f}  max={v['max']:.4f}")

    complexity_bucket_report = build_complexity_bucket_report(
        test_set,
        l3_results,
        per_sample_metrics,
    )

    # ── [5] Oracle analysis (optional) ──
    oracle_report = None
    if args.oracle:
        print("\n[5] Computing oracle analysis ...")
        oracle_report = compute_oracle_analysis(test_set, l3_results, calc)

    # ── [6] QGIS chain evaluation (optional) ──
    qgis_report = None
    if not args.skip_qgis:
        print("\n[6] Running QGIS chain evaluation ...")
        try:
            from gis_recommend.evaluation.reranker_pipeline import run_qgis_evaluation
            qgis_report = run_qgis_evaluation(test_set, l3_results)
        except Exception as exc:
            print(f"  [WARN] QGIS evaluation failed: {exc}")
            qgis_report = {"error": str(exc)}

    # ── [7] Executable check (optional) ──
    executable_report = None
    if args.executable_check:
        print("\n[7] Computing executable chain ratio (Level 1) ...")
        io_types = load_io_types()
        if io_types:
            executable_report = compute_executable_ratio(test_set, l3_results, id_to_l3_code, io_types)
            print_executable_ratio(executable_report)

    tiered_report = build_five_tier_report(
        n_samples=n,
        aggregate_l3_metrics=agg_metrics,
        qgis_report=qgis_report,
        executable_report=executable_report,
        oracle_report=oracle_report,
    )

    # ── [8] Write report ──
    print(f"\n[8] Writing evaluation report ...")
    report = {
        "schema_version": "gis_recommend.v4_6_quality_gate_evaluation.v1",
        "system_lineage": "research",
        "data_profile": "v4_quality_gate",
        "model_profile": "v4_6_quality_gate_candidate",
        "metric_scope": "quality_gate_candidate_evaluation",
        "mainline_eligible": False,
        "governance": {
            "lineage": "research",
            "mainline_eligible": False,
            "non_mainline_reason": "Current mainline is Step8 + V4.6 gis-evaluate; V4-QG is a candidate/research profile.",
        },
        "eval_config": {
            "eval_mode": args.eval_mode,
            "effective_samples": n,
            "data_path": str(V4_QG_LABELED_WORKFLOWS_PATH),
            "splits_path": str(V4_QG_SPLITS_PATH),
            "trainer_version": "V4.6",
            "checkpoint_path": infer_meta.get("transformer_checkpoint"),
            "set_predictor_path": infer_meta.get("set_predictor_checkpoint"),
            "is_quality_gate": True,
        },
        "inference_meta": infer_meta,
        "aggregate_l3_metrics": agg_metrics,
        "complexity_bucket_report": complexity_bucket_report,
        "five_tier_metrics": tiered_report,
        "oracle_analysis": oracle_report,
        "qgis_chain_evaluation": qgis_report,
        "executable_chain_ratio": executable_report,
    }

    report_path = Path(getattr(args, "report_path", None) or V4_QG_EVALUATION_OUTPUT_DIR / "evaluation_report.json")
    report_path.parent.mkdir(parents=True, exist_ok=True)
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    print(f"  Report saved to {report_path}")
    summary_path = V4_QG_EVALUATION_OUTPUT_DIR / "evaluation_summary.md"
    write_five_tier_markdown(summary_path, tiered_report, complexity_bucket_report)
    print(f"  Summary saved to {summary_path}")

    # Summary
    print(f"\n{'=' * 70}")
    print(f"  V4.6 Quality-Gate Evaluation Complete")
    print(f"  Lineage: research / non-mainline")
    print(f"  Samples: {n}")
    primary = tiered_report["tiers"]["tier2_3_workflow_usability"]
    print(f"  Primary KPI: Workflow usability / QGIS landing")
    print(f"  QGIS Validity: {primary.get('qgis_chain_validity_rate', 0.0):.4f}")
    print(f"  QGIS Mapping:  {primary.get('qgis_mapping_rate', 0.0):.4f}")
    if agg_metrics:
        print("  Sequence diagnostics (not correctness KPI):")
        print(f"    LCS Ratio:    {agg_metrics['lcs_ratio']['mean']:.4f}")
        print(f"    Token Acc:    {agg_metrics['token_accuracy']['mean']:.4f}")
        print(f"    Set F1:       {agg_metrics['set_f1']['mean']:.4f}")
        print(f"    Exact Match:  {agg_metrics['exact_match']['mean']:.4f}")
    print(f"{'=' * 70}")


if __name__ == "__main__":
    main()
