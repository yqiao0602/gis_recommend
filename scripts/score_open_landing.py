#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Score the system's open-landing QGIS chains into a fixed diagnostic report.

Reads the manually graded open_landing_results.csv (the system's top-1 QGIS
alg-id chains + task-intent modality + human A/B/C grade), scores each chain
against the alg-id QGIS operator registry (Neo4j-free), and writes:

  - open_landing_report.json  (machine-readable: overall + by modality + by grade + diversity)
  - open_landing_report.md    (self-explanatory report)

This is the baseline dashboard for the vector-capability work: the by-modality
table shows where chains fail; the by-grade table shows whether ①② track
human-judged correctness; chain diversity quantifies template collapse.

Usage:
    python scripts/score_open_landing.py
    python scripts/score_open_landing.py --csv path/to/results.csv --out-dir path/to/out
    python scripts/score_open_landing.py --operators path/to/qgis_operators.json
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
    parse_open_landing_csv,
    build_report,
    render_markdown,
)

DEFAULT_CSV = ROOT / "outputs_v2" / "diagnostics" / "open_landing_eval" / "open_landing_results.csv"
DEFAULT_OUT_DIR = ROOT / "outputs_v2" / "diagnostics" / "open_landing_eval"


def _print_summary(report: dict) -> None:
    o = report["overall"]

    def f(v):
        return f"{v:.3f}" if isinstance(v, (int, float)) else "—"

    print(f"Open-Landing QGIS Chain Evaluation  n={report['n']}")
    print(f"  OVERALL  validity={f(o.get('operator_validity'))}  "
          f"io_exec={f(o.get('io_executability'))}  "
          f"executable={f(o.get('executable_rate'))}")
    print("  --- by task modality ---")
    for m, a in report["by_modality"].items():
        print(f"    {m or '(none)':<8} n={a['n']:<3} validity={f(a.get('operator_validity'))} "
              f"io_exec={f(a.get('io_executability'))} executable={f(a.get('executable_rate'))}")
    print("  --- by human grade ---")
    for g, a in sorted(report["by_grade"].items()):
        print(f"    grade {g or '(ungraded)':<10} n={a['n']:<3} validity={f(a.get('operator_validity'))} "
              f"io_exec={f(a.get('io_executability'))} executable={f(a.get('executable_rate'))}")
    print("  --- chain diversity (template collapse) ---")
    for m, d in report["diversity_by_modality"].items():
        print(f"    {m or '(none)':<8} n={d['n']:<3} unique={d['unique']:<3} ratio={f(d['unique_ratio'])}")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--csv", type=Path, default=DEFAULT_CSV, help="graded open_landing_results.csv")
    ap.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR, help="output directory")
    ap.add_argument("--operators", type=Path, default=None,
                    help="qgis_operators.json (default: the canonical operators-json file)")
    args = ap.parse_args()

    io_types = load_algid_io_types(args.operators)
    items = parse_open_landing_csv(args.csv)
    report = build_report(items, io_types)

    args.out_dir.mkdir(parents=True, exist_ok=True)
    json_path = args.out_dir / "open_landing_report.json"
    md_path = args.out_dir / "open_landing_report.md"
    with json_path.open("w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    md_path.write_text(render_markdown(report), encoding="utf-8")

    _print_summary(report)
    print(f"\n  Registry: {len(io_types)} QGIS operators (alg-id)")
    print(f"  JSON: {json_path}")
    print(f"  MD:   {md_path}")


if __name__ == "__main__":
    main()
