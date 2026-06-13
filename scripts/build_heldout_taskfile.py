#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Build a showcase task-file + references from the held-out test split.

Phase B of the V4.6 evaluation: unlike the open-landing tasks (text-only,
no references), the held-out workflows carry a real ``task_type`` AND a gold
``l3_codes`` sequence. Running the V4.6 model on them in its native domain and
comparing the model's emitted L3 against the gold L3 unlocks the ③ correctness
axis (operator_set_f1), which open-landing cannot provide.

Emits two order-aligned files (the showcase assigns idx = 1..N in file order):
  - heldout_tasks.jsonl       : showcase input (task_name/description/task_type/group)
  - heldout_references.jsonl  : one line per task {row, task_type, gold_l3_codes}

``group`` carries the real ``task_type`` so the showcase CSV groups by it; the
gold L3 codes are content-only (``<START>``/``<END>`` stripped) for set-F1.

Source:
  outputs_v2/pipeline/step8_quality_gate/labeled_workflows_l3_v4_quality_gate.json
  outputs_v2/pipeline/step8_quality_gate/dataset_splits_v4_quality_gate.json

Usage:
    python scripts/build_heldout_taskfile.py
    python scripts/build_heldout_taskfile.py --max-samples 150 --seed 42
"""
from __future__ import annotations

import argparse
import json
import random
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STEP8 = ROOT / "outputs_v2" / "pipeline" / "step8_quality_gate"
DEFAULT_DATA = STEP8 / "labeled_workflows_l3_v4_quality_gate.json"
DEFAULT_SPLITS = STEP8 / "dataset_splits_v4_quality_gate.json"
DEFAULT_OUT_DIR = ROOT / "outputs_v2" / "diagnostics" / "heldout_v46"

_L3_MARKERS = {"<START>", "<END>", "<PAD>", "<UNK>"}


def _task_type(wf: dict) -> str:
    tm = wf.get("task_metadata", {})
    return str(tm.get("task_type_normalized", tm.get("task_type", "Unknown")))


def _gold_l3_codes(wf: dict) -> list:
    """Content-only gold L3 codes (special markers stripped)."""
    return [str(c) for c in (wf.get("l3_codes") or []) if str(c) not in _L3_MARKERS]


def select_indices(test_indices, max_samples: int, seed: int) -> list:
    test_indices = [int(i) for i in test_indices]
    if max_samples <= 0 or max_samples >= len(test_indices):
        return list(test_indices)
    rng = random.Random(seed)
    # Deterministic but representative; keep split order after sampling so
    # downstream traces are stable (mirrors run_v4_qg_planner.select_eval_indices).
    return sorted(rng.sample(test_indices, k=max_samples))


def build(data_path: Path, splits_path: Path, out_dir: Path, max_samples: int, seed: int) -> int:
    data = json.loads(data_path.read_text(encoding="utf-8"))
    workflows = data.get("labeled_workflows") if isinstance(data, dict) else data
    splits = json.loads(splits_path.read_text(encoding="utf-8"))
    indices = select_indices(splits.get("test_indices", []), max_samples, seed)

    out_dir.mkdir(parents=True, exist_ok=True)
    tasks_path = out_dir / "heldout_tasks.jsonl"
    refs_path = out_dir / "heldout_references.jsonl"

    n = 0
    with tasks_path.open("w", encoding="utf-8") as tf, refs_path.open("w", encoding="utf-8") as rf:
        for row, idx in enumerate(indices, start=1):
            wf = workflows[idx]
            tm = wf.get("task_metadata", {})
            task_type = _task_type(wf)
            tf.write(json.dumps({
                "task_name": str(tm.get("task_name", "")),
                "task_description": str(tm.get("task_description", "")),
                "task_type": task_type,
                "group": task_type,
            }, ensure_ascii=False) + "\n")
            rf.write(json.dumps({
                "row": row,                      # == showcase idx (file order)
                "source_index": idx,
                "task_type": task_type,
                "gold_l3_codes": _gold_l3_codes(wf),
            }, ensure_ascii=False) + "\n")
            n += 1
    return n


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--data", type=Path, default=DEFAULT_DATA)
    ap.add_argument("--splits", type=Path, default=DEFAULT_SPLITS)
    ap.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    ap.add_argument("--max-samples", type=int, default=150)
    ap.add_argument("--seed", type=int, default=42)
    args = ap.parse_args()
    n = build(args.data, args.splits, args.out_dir, args.max_samples, args.seed)
    print(f"Wrote {n} held-out tasks + references -> {args.out_dir}")


if __name__ == "__main__":
    main()
