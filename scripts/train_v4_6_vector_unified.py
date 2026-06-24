#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Thin wrapper: V4.6 retrain on rebalanced (1,097 QGIS-vector-augmented) data.

Overrides data/splits paths, delegates everything else to train_v4_6_quality_gate.py.
Produces a separate checkpoint dir. All upstream architecture/config/trainer unchanged.

Usage:
    python scripts/train_v4_6_vector_fix.py              # full train
    python scripts/train_v4_6_vector_fix.py --dry-run    # 1-batch smoke
    python scripts/train_v4_6_vector_fix.py --warmstart <prev_ckpt>  # resume from ckpt
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

# ── override data paths BEFORE importing the trainer (config reads these) ──
import gis_recommend.config.transformer_config as cfg

cfg.DATA_PATH = str(ROOT / "outputs_v2" / "labeled_workflows_l3_v4_vector_unified.json")
cfg.V4_QG_LABELED_WORKFLOWS_PATH = Path(cfg.DATA_PATH)
cfg.SPLITS_PATH = str(ROOT / "outputs_v2" / "dataset_splits_v4_vector_unified.json")
cfg.V4_QG_SPLITS_PATH = Path(cfg.SPLITS_PATH)
# separate checkpoint dir (phase 7)
cfg.V4_6_QG_TRANSFORMER_CHECKPOINT_DIR = ROOT / "outputs_v2" / "transformer_checkpoints_v4_6_warmstart_upsampled"

# bump freq_weight alpha for stronger rare-token (L3_02 vector) upbalance
cfg.V4_1_FREQ_WEIGHT_ALPHA = 0.8  # Phase 8 proven value — explicit upsampling handles vector bias

from scripts.train_v4_6_quality_gate import main as train_main  # noqa: E402


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true", help="1 batch smoke test")
    ap.add_argument("--warmstart", type=Path, default=None)
    args, unknown = ap.parse_known_args()
    # rebuild sys.argv for train_v4_6_quality_gate's argparse
    argv = [__file__] + unknown
    if args.dry_run:
        argv.append("--dry-run")
    if args.warmstart:
        argv += ["--warmstart", str(args.warmstart)]
    sys.argv = argv
    train_main()
