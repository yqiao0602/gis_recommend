#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Build a vector L3 training set from described QGIS vector chains.

Pipeline:
  scripts/generate_qgis_chain_descriptions.py [--use-llm]   # produces described.jsonl
  -> THIS script: filter pure_vector + has L3, convert to labeled_workflows schema

Output (outputs_v2/vector_training_samples.jsonl) is mergeable into
labeled_workflows_l3_v4_quality_gate.json for a rebalanced retrain that gives the
model the vector signal it currently lacks (corpus is 99.3% raster).

Usage:
    python scripts/build_vector_training_set.py
    python scripts/build_vector_training_set.py --task-type "Other / Sparse"
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from gis_recommend.data.vector_training_builder import to_training_sample

OUT_DIR = ROOT / "outputs_v2"
STEP8 = OUT_DIR / "pipeline" / "step8_quality_gate"
DEFAULT_DESCRIBED = OUT_DIR / "qgis_chain_dataset_described.jsonl"
DEFAULT_VOCAB = OUT_DIR / "l3_vocab_v2.json"
DEFAULT_TASK_VOCAB = STEP8 / "task_type_vocabulary_v4_quality_gate.json"
DEFAULT_OUT = OUT_DIR / "vector_training_samples.jsonl"


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--described", type=Path, default=DEFAULT_DESCRIBED)
    ap.add_argument("--vocab", type=Path, default=DEFAULT_VOCAB)
    ap.add_argument("--task-vocab", type=Path, default=DEFAULT_TASK_VOCAB)
    ap.add_argument("--task-type", default="Other / Sparse")
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = ap.parse_args()

    vocab = json.loads(args.vocab.read_text(encoding="utf-8"))
    code_to_id = vocab["code_to_id"]
    special_tokens = vocab["special_tokens"]
    task_type_to_id = json.loads(args.task_vocab.read_text(encoding="utf-8"))["task_type_to_id"]
    if args.task_type not in task_type_to_id:
        print(f"  [WARN] task_type {args.task_type!r} not in vocab -> id 0 (Unknown)")

    stats = Counter()
    samples = []
    with args.described.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            rec = json.loads(line)
            stats["total"] += 1
            if rec.get("modality") != "pure_vector":
                continue
            stats["pure_vector"] += 1
            s = to_training_sample(rec, code_to_id=code_to_id, special_tokens=special_tokens,
                                   task_type=args.task_type, task_type_to_id=task_type_to_id)
            if s is None:
                stats["dropped_no_l3_or_oov"] += 1
                continue
            samples.append(s)
            stats["kept"] += 1

    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w", encoding="utf-8") as f:
        for s in samples:
            f.write(json.dumps(s, ensure_ascii=False) + "\n")

    print(f"described={stats['total']}  pure_vector={stats['pure_vector']}  "
          f"kept={stats['kept']}  dropped(no-L3/OOV)={stats['dropped_no_l3_or_oov']}")
    print(f"  task_type={args.task_type!r}  ->  {args.out}")
    if samples:
        ex = samples[0]
        print(f"  example: {ex['task_metadata']['task_name']!r}")
        print(f"           L3: {' -> '.join(ex['l3_codes'])}")


if __name__ == "__main__":
    main()
