#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Score the V4.6 model's open-landing QGIS chains and compare to the baseline.

Reads the showcase CSV produced by run_end_to_end_showcase_eval.py (V4.6 model
end-to-end on the 80 open-landing tasks), scores each landed QGIS chain against
the alg-id QGIS registry (same harness as the baseline), and writes:

  - v46_report.json / v46_report.md   (V4.6: overall + by task-intent modality + diversity)
  - baseline_vs_v46.md                 (side-by-side ①②/executable/diversity per modality)

The baseline report (open_landing_report.json from score_open_landing.py) is the
v3 retrieval baseline on the SAME 80 tasks, so the comparison is apples-to-apples.

Note: V4.6 here runs text-only (task_type=Unknown) and the landing corpus differs
from the baseline's, so deltas reflect BOTH the model's L3 contribution AND the
landing dataset — see the plan's Risks section.

Usage:
    python scripts/score_v46_open_landing.py
    python scripts/score_v46_open_landing.py --showcase-csv <csv> --baseline-json <json>
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from gis_recommend.evaluation.qgis_operator_registry import load_algid_io_types
from gis_recommend.evaluation.open_landing_report import (
    parse_showcase_csv,
    build_report,
    render_markdown,
    compare_reports,
    render_comparison_markdown,
)

DIAG = ROOT / "outputs_v2" / "diagnostics"
DEFAULT_SHOWCASE_CSV = DIAG / "open_landing_v46" / "end_to_end_showcase_eval.csv"
DEFAULT_BASELINE_JSON = DIAG / "open_landing_eval" / "open_landing_report.json"
DEFAULT_OUT_DIR = DIAG / "open_landing_v46"


def _print_summary(report: dict) -> None:
    def f(v):
        return f"{v:.3f}" if isinstance(v, (int, float)) else "—"

    o = report["overall"]
    print(f"V4.6 Open-Landing  n={report['n']}")
    print(f"  OVERALL  validity={f(o.get('operator_validity'))}  "
          f"io_exec={f(o.get('io_executability'))}  executable={f(o.get('executable_rate'))}")
    for m, a in report["by_modality"].items():
        d = report["diversity_by_modality"].get(m, {})
        print(f"    {m or '(none)':<8} n={a['n']:<3} validity={f(a.get('operator_validity'))} "
              f"io_exec={f(a.get('io_executability'))} executable={f(a.get('executable_rate'))} "
              f"unique_ratio={f(d.get('unique_ratio'))}")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--showcase-csv", type=Path, default=DEFAULT_SHOWCASE_CSV)
    ap.add_argument("--baseline-json", type=Path, default=DEFAULT_BASELINE_JSON)
    ap.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    ap.add_argument("--operators", type=Path, default=None)
    args = ap.parse_args()

    io_types = load_algid_io_types(args.operators)
    items = parse_showcase_csv(args.showcase_csv)
    model_report = build_report(items, io_types)

    args.out_dir.mkdir(parents=True, exist_ok=True)
    (args.out_dir / "v46_report.json").write_text(
        json.dumps(model_report, ensure_ascii=False, indent=2), encoding="utf-8")
    (args.out_dir / "v46_report.md").write_text(render_markdown(model_report), encoding="utf-8")

    _print_summary(model_report)
    print(f"  Registry: {len(io_types)} QGIS operators (alg-id)")

    if args.baseline_json.exists():
        baseline = json.loads(args.baseline_json.read_text(encoding="utf-8"))
        cmp = compare_reports(baseline, model_report, labels=("baseline", "v4.6"))
        (args.out_dir / "baseline_vs_v46.json").write_text(
            json.dumps(cmp, ensure_ascii=False, indent=2), encoding="utf-8")
        (args.out_dir / "baseline_vs_v46.md").write_text(render_comparison_markdown(cmp), encoding="utf-8")
        print(f"  Comparison: {args.out_dir / 'baseline_vs_v46.md'}")
    else:
        print(f"  [WARN] baseline report not found, skipping comparison: {args.baseline_json}")


if __name__ == "__main__":
    main()
