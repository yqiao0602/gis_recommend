#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Thin wrapper: V4.6 retrain on unified vector-augmented data (10,768 QGIS samples).

⚠️  审查意见 (2026-06-24)：本 wrapper 使用的 vector_unified 数据包含 LLM/API-trace
生成样本、同 prompt 多 label 与 source-quality 混杂；更推荐改用更干净的
step8_quality_gate_qgis_vector_oversampled 包。注意：val/test 混入生成样本是
vector_v2 随机 split 的问题，不应归因到 vector_unified。

Overrides data/splits paths, delegates everything else to train_v4_6_quality_gate.py.
Produces a separate checkpoint dir. Length-stats can be injected when a package-specific
file exists; otherwise this wrapper stops and asks for an explicit --length-stats.

Usage:
    python scripts/train_v4_6_vector_unified.py                     # full train
    python scripts/train_v4_6_vector_unified.py --dry-run           # 1-batch smoke
    python scripts/train_v4_6_vector_unified.py --warmstart <ckpt>  # resume

Manifest:
  data:       outputs_v2/labeled_workflows_l3_v4_vector_unified.json
  splits:     outputs_v2/dataset_splits_v4_vector_unified.json
  task vocab: outputs_v2/pipeline/step8_quality_gate/task_type_vocabulary_v4_quality_gate.json
  length:     outputs_v2/task_type_length_stats_vector_unified.json if present;
              otherwise pass --length-stats explicitly or use the oversampled mainline.
  checkpoint: outputs_v2/transformer_checkpoints_v4_6_warmstart_upsampled/
  alpha:      0.8
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
cfg.V4_6_QG_TRANSFORMER_CHECKPOINT_DIR = ROOT / "outputs_v2" / "transformer_checkpoints_v4_6_warmstart_upsampled"

# Phase 8 proven value — explicit upsampling handles vector bias
cfg.V4_1_FREQ_WEIGHT_ALPHA = 0.8

_UNIFIED_LENGTH_STATS = ROOT / "outputs_v2" / "task_type_length_stats_vector_unified.json"

from scripts.train_v4_6_quality_gate import main as train_main  # noqa: E402


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true", help="1 batch smoke test")
    ap.add_argument("--warmstart", type=Path, default=None)
    ap.add_argument(
        "--no-family-sampler",
        action="store_true",
        help="Disable the V4.6 vector-family/source-quality sampler.",
    )
    args, unknown = ap.parse_known_args()
    # rebuild sys.argv for train_v4_6_quality_gate's argparse
    argv = [__file__] + unknown
    if args.dry_run:
        argv.append("--dry-run")
    if args.warmstart:
        argv += ["--warmstart", str(args.warmstart)]
    if not args.no_family_sampler and "--enable-family-sampler" not in unknown:
        argv.append("--enable-family-sampler")
        print("  ℹ  自动启用 --enable-family-sampler（可用 --no-family-sampler 关闭）")
    # force package-specific length stats unless user already passed --length-stats
    if not any(a.startswith("--length-stats") for a in unknown):
        if not _UNIFIED_LENGTH_STATS.exists():
            raise SystemExit(
                "vector_unified 缺少包专属 length stats: "
                f"{_UNIFIED_LENGTH_STATS}\n"
                "请先生成该文件，或显式传 --length-stats <path>；"
                "推荐改用 step8_quality_gate_qgis_vector_oversampled 主线包。"
            )
        argv.append(f"--length-stats={_UNIFIED_LENGTH_STATS}")
        print(f"  ℹ  自动注入 --length-stats={_UNIFIED_LENGTH_STATS}")
    sys.argv = argv
    train_main()
