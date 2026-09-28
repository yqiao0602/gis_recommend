#!/usr/bin/env python3
"""M1-V4.6-R1 trainer: V4.6 with the frozen platform-stratified sampler.

Training protocol frozen 2026-09-09 (user preflight PASSED):
  platform 70:30; GEE first-L3 family 37-way; QGIS chain-length 4-bin;
  samples/epoch 8,832 (276 × 32); replacement=True; val frozen 49.

This subclass changes ONLY `_build_train_loader` — no architecture, loss, or
scheduler change. It exists so the frozen sampler is used without editing the
shared V4.5/V4.6 modules (other experiments keep their behaviour).
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

import torch
from torch.utils.data import DataLoader

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from gis_recommend.training.train_v4_6 import ScheduledSamplingTrainerV4_6  # noqa: E402
from scripts.platform_stratified_sampler import build_platform_stratified_sampler  # noqa: E402

# Frozen protocol constants.
GEE_RATIO = 0.70
SAMPLES_PER_EPOCH = 8832  # ceil(8817/32)*32, batch 32
BATCH_SIZE = 32


class PlatformStratifiedTrainerV4_6_R1(ScheduledSamplingTrainerV4_6):
    """V4.6 with the M1-R1 two-level platform sampler (frozen protocol)."""

    def __init__(self, *args, gee_ratio: float = GEE_RATIO, **kwargs):
        super().__init__(*args, **kwargs)
        self.gee_ratio = float(gee_ratio)
        self._sampler_report: dict | None = None

    def _build_train_loader(self, epoch):
        workflows = getattr(self.train_dataset, "workflows", None)
        if workflows is None:
            raise ValueError("train_dataset has no .workflows; cannot platform-stratify")
        sampler, report = build_platform_stratified_sampler(
            workflows, gee_ratio=self.gee_ratio, batch_size=self.batch_size)
        # Protocol: samples/epoch = ceil(N/batch)*batch. For the frozen paper_v1
        # run (N = 8,817, batch 32) this is exactly 8,832; fail closed if the
        # full dataset would silently yield a different epoch size.
        expected = math.ceil(len(workflows) / self.batch_size) * self.batch_size
        if report["samples_per_epoch"] != expected:
            raise ValueError(
                f"epoch definition drift: {report['samples_per_epoch']} != {expected}")
        if len(workflows) == 8817 and self.batch_size == BATCH_SIZE and report["samples_per_epoch"] != SAMPLES_PER_EPOCH:
            raise ValueError(
                f"frozen-protocol drift: {report['samples_per_epoch']} != {SAMPLES_PER_EPOCH}")
        self._sampler_report = report
        if epoch == 0:
            print(f"  [M1-R1] platform sampler: GEE {self.gee_ratio:.0%} / QGIS {1-self.gee_ratio:.0%}"
                  f" | strata GEE={report['gee_strata']} QGIS={len(report['qgis_length_strata'])}"
                  f" | samples/epoch={report['samples_per_epoch']}")
        loader = DataLoader(
            self.train_dataset,
            batch_size=self.batch_size,
            sampler=sampler,
            num_workers=self.num_workers,
            drop_last=True,
        )
        return loader, report["samples_per_epoch"]


def trainer_factory(*args, **kwargs):
    """Entry point for the quality-gate script to instantiate the R1 trainer."""
    return PlatformStratifiedTrainerV4_6_R1(*args, **kwargs)
