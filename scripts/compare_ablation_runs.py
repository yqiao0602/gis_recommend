#!/usr/bin/env python3
"""Phase 1: Unified ablation comparison with workflow-level primary metrics.

Compares checkpoint evaluations across ablation versions using composite
workflow quality score.

Usage:
    python scripts/compare_ablation_runs.py \
        --eval-dirs outputs_v2/checkpoint_eval/ \
        --output-dir outputs_v2/ablation_comparison
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Optional

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(SRC))


def load_eval(dir_path: Path) -> Optional[dict]:
    path = dir_path / "checkpoint_evaluation.json"
    if not path.exists():
        return None
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def main(argv: Optional[list[str]] = None) -> dict:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--eval-dirs", type=Path, required=True,
                        help="Parent directory containing per-ablation eval subdirs")
    parser.add_argument("--output-dir", type=Path,
                        default=ROOT / "outputs_v2" / "ablation_comparison")
    parser.add_argument("--versions", nargs="*",
                        default=["baseline", "mr_all_42", "mr_all_220", "mr_all_1257"])
    args = parser.parse_args(argv)

    results = {}
    for version in args.versions:
        eval_dir = args.eval_dirs / f"ablation_{version}"
        eval_data = load_eval(eval_dir)
        if eval_data:
            best = eval_data.get("best_checkpoint", {})
            ranked = eval_data.get("ranked", [])
            results[version] = {
                "best_epoch": best.get("epoch"),
                "composite_score": best.get("composite_score"),
                "best_metrics": ranked[0] if ranked else {},
                "metric_hierarchy": eval_data.get("metric_hierarchy", {}),
            }

    if len(results) < 2:
        print("ERROR: Need at least 2 evaluation results. Run evaluate_checkpoint_epochs.py first.")
        return {"error": "insufficient_results"}

    args.output_dir.mkdir(parents=True, exist_ok=True)

    lines = [
        "# Ablation Comparison: Workflow Quality Metrics",
        "",
        "## Best Checkpoint per Version",
        "| Version | Best Epoch | Composite | SetF1 | QGIS Val | QGIS Map | Exec | LCS |",
        "|---------|-----------|-----------|-------|----------|----------|------|-----|",
    ]
    for version in args.versions:
        if version not in results:
            continue
        r = results[version]
        m = r["best_metrics"]
        lines.append(
            f"| {version} | {r['best_epoch']} | {r['composite_score']:.4f} | "
            f"{m.get('set_f1', '-')} | {m.get('qgis_validity', '-')} | "
            f"{m.get('qgis_mapping', '-')} | {m.get('executable', '-')} | "
            f"{m.get('lcs_ratio', '-')} |"
        )

    # Delta vs baseline
    baseline = results.get("baseline", {})
    if baseline and baseline.get("composite_score") is not None:
        base_score = baseline["composite_score"]
        lines += [
            "",
            "## Delta vs Baseline",
            "| Version | Composite | Delta | Direction |",
            "|---------|-----------|-------|-----------|",
        ]
        for version in args.versions:
            if version == "baseline" or version not in results:
                continue
            r = results[version]
            if r.get("composite_score") is None:
                continue
            delta = r["composite_score"] - base_score
            direction = "IMPROVED" if delta > 0 else ("DEGRADED" if delta < 0 else "NO CHANGE")
            lines.append(f"| {version} | {r['composite_score']:.4f} | {delta:+.4f} | {direction} |")

    lines += [
        "",
        "## Metric Contract",
        "- **Primary** (in composite): SetF1 (0.35), QGIS Validity (0.25), QGIS Mapping (0.20), Executable (0.20)",
        "- **Supporting**: LCS",
        "- **Diagnostic only**: TokenAcc, SeqEM",
        "",
        "## Interpretation",
        "- Composite score is an absolute workflow-quality metric at the best epoch",
        "- Delta vs baseline determines direction: positive = improved, negative = degraded",
        "- If delta <= 0 at any MR scale, investigate per-source-family attribution before expanding further",
        "- TokenAcc and SeqEM are recorded but do NOT influence model selection",
    ]

    md_path = args.output_dir / "ablation_comparison.md"
    md_path.write_text("\n".join(lines), encoding="utf-8")

    json_path = args.output_dir / "ablation_comparison.json"
    json.dump({"versions_compared": list(results.keys()), "results": results},
              json_path.open("w", encoding="utf-8"), ensure_ascii=False, indent=2)

    print(f"Comparison saved: {args.output_dir}")
    return {"compared": len(results)}


if __name__ == "__main__":
    main()
