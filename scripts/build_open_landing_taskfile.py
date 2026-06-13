#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Build a showcase task-file (JSONL) from the open-landing task set.

Converts the 80 open-landing tasks (task text + task-intent modality) into the
JSONL format consumed by scripts/run_end_to_end_showcase_eval.py, so the SAME
tasks can be run through the V4.6 model end-to-end and scored by the same QGIS
harness — giving an apples-to-apples baseline-vs-model comparison.

Mapping:
  task_name        <- task text
  task_description <- "" (the model encodes task_name+description as one BERT input)
  task_type        <- "Unknown"  (open-landing tasks carry no task_type; the
                      inferencer maps unknown -> id 0, i.e. a text-only run)
  group            <- the task-intent modality (vec/rast/mixed) verbatim, so the
                      showcase CSV's `group` column carries modality straight
                      through to scoring (no lossy reverse-mapping needed).

Source: outputs_v2/diagnostics/open_landing_eval/open_landing_results.csv
        (the graded baseline CSV; we reuse only its `task` + `modality` columns).

Usage:
    python scripts/build_open_landing_taskfile.py
    python scripts/build_open_landing_taskfile.py --csv <results.csv> --out <tasks.jsonl>
"""
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CSV = ROOT / "outputs_v2" / "diagnostics" / "open_landing_eval" / "open_landing_results.csv"
DEFAULT_OUT = ROOT / "outputs_v2" / "diagnostics" / "open_landing_v46" / "open_landing_tasks.jsonl"


def build_taskfile(csv_path: Path, out_path: Path) -> int:
    rows = []
    with open(csv_path, "r", encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            task = (row.get("task") or "").strip()
            modality = (row.get("modality") or "").strip()
            if not task:
                continue
            rows.append({
                "task_name": task,
                "task_description": "",
                "task_type": "Unknown",
                "group": modality,
            })
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    return len(rows)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--csv", type=Path, default=DEFAULT_CSV)
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = ap.parse_args()
    n = build_taskfile(args.csv, args.out)
    print(f"Wrote {n} tasks -> {args.out}")


if __name__ == "__main__":
    main()
