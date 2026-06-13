#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Phase B: score V4.6 on the held-out split, unlocking ③ correctness.

Reads the showcase JSON (V4.6 run on the held-out tasks: each record carries the
model's emitted L3 via ``l3_parts`` and the landed QGIS chain via
``qgis_landing.top1_chain``) plus the order-aligned references (gold ``l3_codes``),
and computes per task:

  ③ correctness (L3 level) : set_overlap_prf(model L3 codes, gold L3 codes) — the
                             clean, platform-agnostic correctness signal the
                             held-out split provides (open-landing could not).
  ①② grounding (QGIS level): score_qgis_chain on the landed alg-id chain.

Aggregated overall + by real task_type. This is the V4.6 model measured in its
NATIVE domain (real task_type, gold references) — complementing Phase A's
text-only open-landing comparison.

Usage:
    python scripts/score_heldout_v46.py
    python scripts/score_heldout_v46.py --showcase-json <json> --references <jsonl>
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
from gis_recommend.evaluation.qgis_chain_metrics import (
    score_qgis_chain,
    set_overlap_prf,
    aggregate_by,
)

DIAG = ROOT / "outputs_v2" / "diagnostics" / "heldout_v46"
DEFAULT_SHOWCASE_JSON = DIAG / "end_to_end_showcase_eval.json"
DEFAULT_REFERENCES = DIAG / "heldout_references.jsonl"
DEFAULT_OUT_DIR = DIAG


def _load_references(path: Path) -> dict:
    refs = {}
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                r = json.loads(line)
                refs[int(r["row"])] = r
    return refs


def build_heldout_records(showcase_records: list, refs: dict, io_types: dict) -> list:
    recs = []
    for rec in showcase_records:
        row = int(rec.get("idx", 0))
        ref = refs.get(row, {})
        model_l3 = [p.get("code") for p in (rec.get("l3_parts") or []) if p.get("code")]
        gold_l3 = ref.get("gold_l3_codes", [])
        l3 = set_overlap_prf(model_l3, gold_l3)
        chain = (rec.get("qgis_landing") or {}).get("top1_chain", []) or []
        q = score_qgis_chain(chain, io_types=io_types)
        recs.append({
            "row": row,
            "task_type": ref.get("task_type") or rec.get("task_type", "Unknown"),
            "operator_validity": q["operator_validity"],
            "io_executability": q["io_executability"],
            "executable": q["executable"],
            "operator_set_f1": l3["f1"],          # ③ at L3 level (model L3 vs gold L3)
            "l3_precision": l3["precision"],
            "l3_recall": l3["recall"],
            "n_model_l3": len(model_l3),
            "n_gold_l3": len(gold_l3),
            "qgis_n_steps": q["n_steps"],
        })
    return recs


def _fmt(v):
    return f"{v:.3f}" if isinstance(v, (int, float)) else "—"


def render_markdown(report: dict) -> str:
    o = report["overall"]
    L = [
        "# Held-out V4.6 Evaluation (native domain: real task_type + gold L3)",
        "",
        f"n={report['n']}. ③ set_f1 is at the **L3 level** (model L3 vs gold L3 codes); "
        "①② are at the **QGIS level** on the landed chain.",
        "",
        "## Overall",
        "",
        "| | n | ① validity | ② io_exec | executable | ③ L3 set_f1 |",
        "|---|--:|--:|--:|--:|--:|",
        f"| overall | {o.get('n')} | {_fmt(o.get('operator_validity'))} | {_fmt(o.get('io_executability'))} "
        f"| {_fmt(o.get('executable_rate'))} | {_fmt(o.get('operator_set_f1'))} |",
        "",
        "## By task_type (top by n)",
        "",
        "| task_type | n | ① validity | ② io_exec | executable | ③ L3 set_f1 |",
        "|---|--:|--:|--:|--:|--:|",
    ]
    groups = report["by_task_type"]
    for tt in sorted(groups, key=lambda k: (-groups[k].get("n", 0), k)):
        a = groups[tt]
        L.append(f"| {tt} | {a.get('n')} | {_fmt(a.get('operator_validity'))} "
                 f"| {_fmt(a.get('io_executability'))} | {_fmt(a.get('executable_rate'))} "
                 f"| {_fmt(a.get('operator_set_f1'))} |")
    L.append("")
    return "\n".join(L)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--showcase-json", type=Path, default=DEFAULT_SHOWCASE_JSON)
    ap.add_argument("--references", type=Path, default=DEFAULT_REFERENCES)
    ap.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    ap.add_argument("--operators", type=Path, default=None)
    args = ap.parse_args()

    io_types = load_algid_io_types(args.operators)
    showcase = json.loads(args.showcase_json.read_text(encoding="utf-8"))
    records_in = showcase.get("records", [])
    refs = _load_references(args.references)
    recs = build_heldout_records(records_in, refs, io_types)

    agg = aggregate_by(recs, "task_type")
    report = {"n": len(recs), "overall": agg["overall"], "by_task_type": agg["groups"]}

    args.out_dir.mkdir(parents=True, exist_ok=True)
    (args.out_dir / "heldout_v46_report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    (args.out_dir / "heldout_v46_report.md").write_text(render_markdown(report), encoding="utf-8")

    o = report["overall"]
    print(f"Held-out V4.6  n={report['n']}")
    print(f"  OVERALL  validity={_fmt(o.get('operator_validity'))}  "
          f"io_exec={_fmt(o.get('io_executability'))}  executable={_fmt(o.get('executable_rate'))}  "
          f"L3_set_f1={_fmt(o.get('operator_set_f1'))}")
    print(f"  Report: {args.out_dir / 'heldout_v46_report.md'}")


if __name__ == "__main__":
    main()
