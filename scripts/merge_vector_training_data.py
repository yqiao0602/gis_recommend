#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Merge vector L3 training samples into labeled_workflows for rebalanced retrain.

Reads the existing labeled_workflows (dict {num_workflows, labeled_workflows: [...]})
plus splits (dict {train_indices, val_indices, test_indices}), appends the vector
training samples with new contiguous indices, then produces UPSAMPLED train_indices
that repeat the vector portion N times. test/val indices are NOT upsampled (vectors
would leak reference into eval).

Upsampling factor: --upsample-factor N means each vector index appears N times in
train_indices. Default 20 gives ~1:1 balance given 1,097 vectors vs 76,884 total
(training-only ratio depends on train split %, but 20x brings vectors to roughly
equivalent probability).

Usage:
    python scripts/merge_vector_training_data.py
    python scripts/merge_vector_training_data.py --upsample-factor 30 --dry-run
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STEP8 = ROOT / "outputs_v2" / "pipeline" / "step8_quality_gate"
DEFAULT_WORKFLOWS = STEP8 / "labeled_workflows_l3_v4_quality_gate.json"
DEFAULT_SPLITS = STEP8 / "dataset_splits_v4_quality_gate.json"
DEFAULT_TASK_VOCAB = STEP8 / "task_type_vocabulary_v4_quality_gate.json"
DEFAULT_VECTOR = ROOT / "outputs_v2" / "vector_training_samples_v2.jsonl"
DEFAULT_OUT_WF = ROOT / "outputs_v2" / "labeled_workflows_l3_v4_vector_rebalanced.json"
DEFAULT_OUT_SPLITS = ROOT / "outputs_v2" / "dataset_splits_v4_vector_rebalanced.json"


def load_workflows(path: Path) -> list:
    raw = json.loads(path.read_text(encoding="utf-8"))
    return raw["labeled_workflows"] if isinstance(raw, dict) else raw


def load_vector_samples(path: Path) -> list:
    samples = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                samples.append(json.loads(line))
    return samples


def build_vector_train_indices(base_total: int, n_vec: int) -> list:
    """Add vector-sample train indices (unique only — upsampling happens via WeightedRandomSampler)."""
    return list(range(base_total, base_total + n_vec))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--workflows", type=Path, default=DEFAULT_WORKFLOWS)
    ap.add_argument("--splits", type=Path, default=DEFAULT_SPLITS)
    ap.add_argument("--task-vocab", type=Path, default=DEFAULT_TASK_VOCAB)
    ap.add_argument("--vector", type=Path, default=DEFAULT_VECTOR)
    ap.add_argument("--out-workflows", type=Path, default=DEFAULT_OUT_WF)
    ap.add_argument("--out-splits", type=Path, default=DEFAULT_OUT_SPLITS)
    ap.add_argument("--upsample-factor", type=int, default=20)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    wfs = load_workflows(args.workflows)
    splits = json.loads(args.splits.read_text(encoding="utf-8"))
    vec = load_vector_samples(args.vector)
    base_total = len(wfs)
    n_vec = len(vec)
    orig_train_n = len(splits["train_indices"])

    # --- sanity checks ---
    task_tt2id = json.loads(args.task_vocab.read_text(encoding="utf-8"))["task_type_to_id"]
    oov_tt = sum(1 for s in vec if s["task_metadata"]["task_type"] not in task_tt2id)
    if oov_tt:
        print(f"[WARN] {oov_tt} vector samples have task_type not in 47 vocab -> will be id 0 (Unknown)")

    # --- produce merged data + upsampled splits ---
    train_indices = list(splits["train_indices"])
    val_indices = list(splits["val_indices"])
    test_indices = list(splits["test_indices"])
    up_vec_train = build_vector_train_indices(base_total, n_vec)
    train_indices.extend(up_vec_train)

    vw = sum(1 for s in vec if s.get("modality") in ("vector", "mixed"))
    vt = sum(1 for s in vec if s.get("modality") == "raster")

    print(f"base workflows: {base_total}  (train={orig_train_n}  val={len(splits['val_indices'])}  test={len(splits['test_indices'])})")
    print(f"vector samples: {n_vec}  (vector-relevant={vw}  raster={vt})")
    print(f"vector train indices: {len(up_vec_train)}")
    print(f"new train_indices: {len(train_indices)}  (vs {orig_train_n} orig, +{len(up_vec_train)})")
    print(f"upbalance: WeightedRandomSampler via compute_token_freq_weights (L3_02 rare -> high weight)")

    merged_wf = {"num_workflows": base_total + n_vec, "labeled_workflows": wfs + vec}
    merged_splits = {
        "train_indices": train_indices,
        "val_indices": val_indices,
        "test_indices": test_indices,
        "_comment": f"vector_samples={n_vec} upsample_factor={args.upsample_factor} orig_train_n={orig_train_n} base_total={base_total}",
    }

    if args.dry_run:
        print("\n[dry-run] no files written")
        return

    args.out_workflows.parent.mkdir(parents=True, exist_ok=True)
    args.out_splits.parent.mkdir(parents=True, exist_ok=True)
    args.out_workflows.write_text(json.dumps(merged_wf, ensure_ascii=False, indent=2), encoding="utf-8")
    args.out_splits.write_text(json.dumps(merged_splits, ensure_ascii=False), encoding="utf-8")
    print(f"\nmerged -> {args.out_workflows}")
    print(f"splits -> {args.out_splits}")


if __name__ == "__main__":
    main()
