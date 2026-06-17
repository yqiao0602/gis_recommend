#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Score the vector-fix retrained V4.6 model vs the original V4.6.

Loads the vector-fix checkpoint, runs the 80 open_landing showcase on it, scores
via the QGIS harness, and writes a 3-way comparison: baseline vs V4.6 vs V4.6-vector-fix
by task-intent modality. Answers: did adding 1,097 vector training samples fix the
vector->raster collapse?

Usage:
    python scripts/score_v46_vector_fix.py
    python scripts/score_v46_vector_fix.py --vector-fix-ckpt <path>
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
DEFAULT_VECTOR_FIX_CKPT = ROOT / "outputs_v2" / "transformer_checkpoints_v4_6_vector_fix" / "best_model.pth"
DEFAULT_BASELINE_JSON = DIAG / "open_landing_eval" / "open_landing_report.json"
DEFAULT_V46_JSON = DIAG / "open_landing_v46" / "v46_report.json"
DEFAULT_OUT_DIR = DIAG / "open_landing_vector_fix"


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--vector-fix-ckpt", type=Path, default=DEFAULT_VECTOR_FIX_CKPT)
    ap.add_argument("--baseline-json", type=Path, default=DEFAULT_BASELINE_JSON)
    ap.add_argument("--v46-json", type=Path, default=DEFAULT_V46_JSON)
    ap.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    ap.add_argument("--max-tasks", type=int, default=80)
    args = ap.parse_args()

    io_types = load_algid_io_types()

    # 1. run showcase with vector-fix checkpoint
    args.out_dir.mkdir(parents=True, exist_ok=True)
    import subprocess
    print(f"Running showcase with vector-fix checkpoint: {args.vector_fix_ckpt}")
    if not args.vector_fix_ckpt.exists():
        print(f"  [FATAL] checkpoint not found: {args.vector_fix_ckpt}")
        sys.exit(1)
    showcase_out = args.out_dir / "showcase_vf"
    showcase_out.mkdir(parents=True, exist_ok=True)
    subprocess.run([
        sys.executable, str(ROOT / "scripts" / "run_end_to_end_showcase_eval.py"),
        "--task-file", str(ROOT / "outputs_v2" / "diagnostics" / "open_landing_v46" / "open_landing_tasks.jsonl"),
        "--output-dir", str(showcase_out),
        "--checkpoint", str(args.vector_fix_ckpt),
        "--max-tasks", str(args.max_tasks),
    ], check=True, env={**__import__("os").environ, "PYTHONUTF8": "1", "PYTHONIOENCODING": "utf-8"})

    # 2. score vector-fix
    items = parse_showcase_csv(showcase_out / "end_to_end_showcase_eval.csv")
    vf_report = build_report(items, io_types)
    (args.out_dir / "v46_vector_fix_report.json").write_text(
        json.dumps(vf_report, ensure_ascii=False, indent=2), encoding="utf-8")
    (args.out_dir / "v46_vector_fix_report.md").write_text(
        render_markdown(vf_report), encoding="utf-8")

    # 3. three-way comparison: baseline vs V4.6 vs vector-fix
    labels = ("baseline", "v4.6", "v4.6-vecfix")
    three = ["| modality | baseline ① val | V4.6 ① val | V4.6-vecfix ① val | base→V4.6 Δ | V4.6→vecfix Δ |"]
    three.append("|---|--:|--:|--:|--:|--:|")
    base = json.loads(args.baseline_json.read_text(encoding="utf-8")) if args.baseline_json.exists() else None
    v46 = json.loads(args.v46_json.read_text(encoding="utf-8")) if args.v46_json.exists() else None

    def _mv(v):
        return f"{v:.3f}" if isinstance(v, (int, float)) else "—"

    for m in ["vec", "rast", "mixed"]:
        bv = base["by_modality"].get(m, {}) if base else {}
        vv = v46["by_modality"].get(m, {}) if v46 else {}
        fv = vf_report["by_modality"].get(m, {})
        b_val = _mv(bv.get("operator_validity")) if bv else "—"
        v_val = _mv(vv.get("operator_validity")) if vv else "—"
        f_val = _mv(fv.get("operator_validity"))
        bv46_d = _mv((vv.get("operator_validity") or 0) - (bv.get("operator_validity") or 0)) if bv and vv else "—"
        v46f_d = _mv(fv.get("operator_validity", 0) - (vv.get("operator_validity") or 0)) if vv else "—"
        three.append(f"| {m} | {b_val} | {v_val} | {f_val} | {bv46_d} | {v46f_d} |")
    three.append("")

    o = vf_report["overall"]
    print(f"\nVector-fix V4.6  n={vf_report['n']}")
    print(f"  OVERALL  validity={_mv(o.get('operator_validity'))}  io_exec={_mv(o.get('io_executability'))}  "
          f"executable={_mv(o.get('executable_rate'))}")
    for m, a in vf_report["by_modality"].items():
        d = vf_report["diversity_by_modality"].get(m, {})
        print(f"    {m or '(none)':<8} n={a['n']:<3} validity={_mv(a.get('operator_validity'))} "
              f"io_exec={_mv(a.get('io_executability'))} executable={_mv(a.get('executable_rate'))} "
              f"unique_ratio={_mv(d.get('unique_ratio'))}")
    print("\n".join(three))

    (args.out_dir / "three_way_comparison.md").write_text(
        "## baseline vs V4.6 vs V4.6-vector-fix\n\n" + "\n".join(three), encoding="utf-8")

    print(f"\n  Three-way comparison: {args.out_dir / 'three_way_comparison.md'}")

    # 4. if original V4.6 report exists, produce a direct v4.6->vecfix delta table
    if v46:
        cmp_v46_vf = compare_reports(v46, vf_report, labels=("v4.6", "v4.6-vecfix"))
        (args.out_dir / "v46_vs_v46_vecfix.json").write_text(
            json.dumps(cmp_v46_vf, ensure_ascii=False, indent=2), encoding="utf-8")
        (args.out_dir / "v46_vs_v46_vecfix.md").write_text(
            render_comparison_markdown(cmp_v46_vf), encoding="utf-8")
        print(f"  V4.6 vs vector-fix: {args.out_dir / 'v46_vs_v46_vecfix.md'}")


if __name__ == "__main__":
    main()
