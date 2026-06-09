#!/usr/bin/env python3
"""Phase 1: Unified checkpoint evaluation with workflow-level metrics.

Iterates over all epoch checkpoints, evaluates each using the QG evaluator
with structured JSON output, and ranks by composite workflow quality score.

Usage:
    python scripts/evaluate_checkpoint_epochs.py \
        --checkpoint-dir outputs_v2/transformer_checkpoints_v4_6_quality_gate \
        --output-dir outputs_v2/checkpoint_eval/ablation_baseline
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Optional

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(SRC))


def find_epoch_checkpoints(checkpoint_dir: Path) -> list[tuple[int, Path, str]]:
    results = []
    for p in checkpoint_dir.glob("checkpoint_epoch_*.pth"):
        m = re.search(r"epoch_(\d+)", p.name)
        if m:
            epoch = int(m.group(1))
            results.append((epoch, p, f"epoch_{epoch:03d}"))
    named_snapshots = [
        (9991, "best_model.pth", "best_model"),
        (9992, "best_gen_set_f1_model.pth", "best_gen_set_f1"),
        (9993, "best_gen_lcs_model.pth", "best_gen_lcs"),
        (9994, "best_gen_composite_model.pth", "best_gen_composite"),
    ]
    for sort_key, filename, label in named_snapshots:
        path = checkpoint_dir / filename
        if path.exists():
            results.append((sort_key, path, label))
    results.sort()
    return results


def _extract_metrics_from_report(report_path: Path) -> dict:
    """Extract primary/supporting/diagnostic metrics from five-tier report JSON."""
    if not report_path.exists():
        return {"error": "report_not_found"}
    with open(report_path, "r", encoding="utf-8") as f:
        report = json.load(f)

    tiers = (report.get("five_tier_metrics") or {}).get("tiers", {})
    tier1 = tiers.get("tier1_sequence_diagnostics", {})
    tier2 = tiers.get("tier2_3_workflow_usability", {})

    def _mean_value(section, key):
        entry = section.get(key, {})
        if isinstance(entry, dict):
            return entry.get("mean")
        return entry if isinstance(entry, (int, float)) else None

    metrics = {
        # Primary (composite)
        "set_f1": _mean_value(tier1, "set_f1"),
        "qgis_mapping_rate": tier2.get("qgis_mapping_rate"),
        "qgis_validity_rate": tier2.get("qgis_chain_validity_rate"),
        "executable_rate": tier2.get("executable_chain_ratio"),
        # Supporting
        "lcs_ratio": _mean_value(tier1, "lcs_ratio"),
        # Diagnostic only
        "token_accuracy": _mean_value(tier1, "token_accuracy"),
        "sequence_em": _mean_value(tier1, "sequence_em"),
    }

    complexity = (report.get("complexity_bucket_report") or {}).get("by_bucket", {})
    metrics["complexity_by_bucket"] = {
        bucket: {
            "n": row.get("n"),
            "mean_ref_len": row.get("mean_ref_len"),
            "mean_pred_len": row.get("mean_pred_len"),
            "mean_length_ratio": row.get("mean_length_ratio"),
            "early_eos_rate": row.get("early_eos_rate"),
            "overlength_rate": row.get("overlength_rate"),
            "set_f1": row.get("set_f1"),
            "lcs_ratio": row.get("lcs_ratio"),
            "token_accuracy": row.get("token_accuracy"),
        }
        for bucket, row in complexity.items()
        if isinstance(row, dict)
    }
    for bucket in ("long", "very_long"):
        row = metrics["complexity_by_bucket"].get(bucket, {})
        prefix = "very_long" if bucket == "very_long" else "long"
        metrics[f"{prefix}_n"] = row.get("n")
        metrics[f"{prefix}_length_ratio"] = row.get("mean_length_ratio")
        metrics[f"{prefix}_early_eos_rate"] = row.get("early_eos_rate")
        metrics[f"{prefix}_overlength_rate"] = row.get("overlength_rate")
        metrics[f"{prefix}_set_f1"] = row.get("set_f1")
        metrics[f"{prefix}_lcs_ratio"] = row.get("lcs_ratio")

    # Use qgis_validity_rate as usable proxy if executable not available
    if metrics["qgis_validity_rate"] is not None and metrics["executable_rate"] is None:
        metrics["executable_rate"] = metrics["qgis_validity_rate"]

    return metrics


def composite_score(m: dict) -> float:
    """Composite workflow quality score from primary metrics.

    Missing metrics are excluded from the weighted sum — the weight is
    redistributed among available metrics so a checkpoint with fewer
    measured dimensions is not penalized.
    """
    weights = {
        "set_f1": 0.35,
        "qgis_validity_rate": 0.25,
        "qgis_mapping_rate": 0.20,
        "executable_rate": 0.20,
    }
    score = 0.0
    total_weight = 0.0
    for key, w in weights.items():
        val = m.get(key)
        if val is not None:
            score += w * float(val)
            total_weight += w
    if total_weight == 0.0:
        return 0.0
    return round(score / total_weight, 6)


def main(argv: Optional[list[str]] = None) -> dict:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--checkpoint-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--eval-samples", type=int, default=200)
    parser.add_argument("--max-checkpoints", type=int, default=0)
    parser.add_argument("--skip-qgis", action="store_true")
    args = parser.parse_args(argv)

    if not args.checkpoint_dir.exists():
        print(f"ERROR: checkpoint dir not found: {args.checkpoint_dir}")
        return {"error": "checkpoint_dir_not_found"}

    epoch_ckpts = find_epoch_checkpoints(args.checkpoint_dir)
    if args.max_checkpoints > 0 and len(epoch_ckpts) > args.max_checkpoints:
        step = max(1, len(epoch_ckpts) // args.max_checkpoints)
        epoch_ckpts = epoch_ckpts[::step][:args.max_checkpoints]

    print(f"Found {len(epoch_ckpts)} checkpoints in {args.checkpoint_dir}")

    args.output_dir.mkdir(parents=True, exist_ok=True)
    results = []

    for epoch, ckpt_path, label in epoch_ckpts:
        report_path = args.output_dir / f"report_{label}.json"
        print(f"  Evaluating {label} ({ckpt_path.name})...")

        cmd = [
            sys.executable, str(ROOT / "scripts" / "evaluate_v4_quality_gate.py"),
            "--eval-mode", "smoke",
            "--samples", str(args.eval_samples),
            "--checkpoint", str(ckpt_path),
            "--report-path", str(report_path),
            "--executable-check",
        ]
        if args.skip_qgis:
            cmd.append("--skip-qgis")

        try:
            subprocess.run(cmd, capture_output=True, timeout=600, cwd=str(ROOT), check=True)
        except subprocess.CalledProcessError as e:
            results.append({"epoch": epoch, "label": label, "error": str(e.stderr)[:500]})
            continue
        except subprocess.TimeoutExpired:
            results.append({"epoch": epoch, "label": label, "error": "timeout"})
            continue

        m = _extract_metrics_from_report(report_path)
        m["epoch"] = epoch
        m["label"] = label
        if "error" not in m:
            m["composite_score"] = composite_score(m)
        results.append(m)

        print(f"    composite={m.get('composite_score', 'N/A'):.4f}  "
              f"SF1={m.get('set_f1')}  usable={m.get('qgis_validity_rate')}  "
              f"QGIS={m.get('qgis_mapping_rate')}  exec={m.get('executable_rate')}")

    # Sort by composite score
    valid = [r for r in results if "error" not in r and r.get("composite_score", 0) > 0.001]
    valid.sort(key=lambda r: r["composite_score"], reverse=True)

    report = {
        "checkpoint_dir": str(args.checkpoint_dir),
        "total_evaluated": len(results),
        "valid_results": len(valid),
        "metric_hierarchy": {
            "primary_composite": {"set_f1": 0.35, "qgis_validity_rate": 0.25, "qgis_mapping_rate": 0.20, "executable_rate": 0.20},
            "supporting": ["lcs_ratio"],
            "diagnostic": ["token_accuracy", "sequence_em"],
            "complexity_diagnostic": [
                "long_length_ratio",
                "long_early_eos_rate",
                "very_long_length_ratio",
                "very_long_early_eos_rate",
            ],
            "note": "Missing metrics redistributed — no penalty for unmeasured dimensions",
        },
        "best_checkpoint": {
            "epoch": valid[0]["epoch"] if valid else None,
            "composite_score": valid[0]["composite_score"] if valid else None,
        } if valid else {"epoch": None, "composite_score": None},
        "all_results": results,
        "ranked": [
            {"rank": i+1, "epoch": r["epoch"],
             "composite_score": r["composite_score"],
             "set_f1": r.get("set_f1"), "qgis_validity": r.get("qgis_validity_rate"),
             "qgis_mapping": r.get("qgis_mapping_rate"), "executable": r.get("executable_rate"),
             "lcs_ratio": r.get("lcs_ratio"),
             "long_n": r.get("long_n"),
             "long_length_ratio": r.get("long_length_ratio"),
             "long_early_eos_rate": r.get("long_early_eos_rate"),
             "very_long_n": r.get("very_long_n"),
             "very_long_length_ratio": r.get("very_long_length_ratio"),
             "very_long_early_eos_rate": r.get("very_long_early_eos_rate")}
            for i, r in enumerate(valid[:15])
        ],
    }

    json_path = args.output_dir / "checkpoint_evaluation.json"
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    # Markdown
    lines = [
        "# Checkpoint Evaluation",
        f"**Directory**: {args.checkpoint_dir}",
        f"**Samples/checkpoint**: {args.eval_samples}",
        "",
        "## Best Checkpoint by Composite Score",
    ]
    if valid:
        lines.append(f"- Epoch {valid[0]['label']}: composite={valid[0]['composite_score']:.4f}")
    lines += [
        "",
        "## Top 15",
        "| Rank | Epoch | Composite | SetF1 | QGIS Val | QGIS Map | Exec | LCS | Long Len | Long EOS | VLong Len | VLong EOS |",
        "|------|-------|-----------|-------|----------|----------|------|-----|----------|----------|-----------|-----------|",
    ]
    for r in report["ranked"]:
        lines.append(f"| {r['rank']} | {r['epoch']} | {r['composite_score']:.4f} | "
                     f"{r.get('set_f1', '-')} | {r.get('qgis_validity', '-')} | "
                     f"{r.get('qgis_mapping', '-')} | {r.get('executable', '-')} | "
                     f"{r.get('lcs_ratio', '-')} | {r.get('long_length_ratio', '-')} | "
                     f"{r.get('long_early_eos_rate', '-')} | {r.get('very_long_length_ratio', '-')} | "
                     f"{r.get('very_long_early_eos_rate', '-')} |")
    lines += [
        "",
        "## Metric Contract",
        "- Primary: SetF1, QGIS Validity, QGIS Mapping, Executable",
        "- Supporting: LCS",
        "- Diagnostic only: TokenAcc, SeqEM",
    ]
    (args.output_dir / "checkpoint_evaluation.md").write_text("\n".join(lines), encoding="utf-8")

    best = report["best_checkpoint"]
    print(f"\nBest: {best['epoch']} (composite={best['composite_score']})")
    print(f"Report: {args.output_dir}")
    return report


if __name__ == "__main__":
    main()
