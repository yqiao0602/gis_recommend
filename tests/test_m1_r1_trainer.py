"""Integration smoke for the M1-R1 trainer wiring (no GPU, no full training)."""

import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from scripts.m1_r1_trainer import (  # noqa: E402
    BATCH_SIZE,
    GEE_RATIO,
    SAMPLES_PER_EPOCH,
    PlatformStratifiedTrainerV4_6_R1,
)


class _FakeDataset:
    def __init__(self, workflows):
        self.workflows = workflows

    def __len__(self):
        return len(self.workflows)

    def __getitem__(self, index):
        return {"index": index, "platform": self.workflows[index]["platform"]}


def _wf(platform, task_type="", codes=1):
    return {
        "platform": platform,
        "task_metadata": {"task_type": task_type} if task_type else {},
        "l3_codes": ["<START>"] + ["L3_01_01_01"] * codes + ["<END>"],
    }


def _corpus():
    """paper_v1 train shape: 8,817 non-empty rows (8,201 GEE + 616 QGIS)."""
    rows = []
    for i in range(8201):
        rows.append(_wf("gee", f"t{i % 37}"))
    rows += [_wf("qgis", codes=1) for _ in range(367)]
    rows += [_wf("qgis", codes=3) for _ in range(249)]
    return rows


def test_frozen_protocol_constants() -> None:
    assert GEE_RATIO == 0.70
    assert BATCH_SIZE == 32
    assert SAMPLES_PER_EPOCH == 8832


def test_loader_uses_platform_sampler_and_reports_epoch() -> None:
    trainer = PlatformStratifiedTrainerV4_6_R1.__new__(PlatformStratifiedTrainerV4_6_R1)
    trainer.train_dataset = _FakeDataset(_corpus())
    trainer.batch_size = BATCH_SIZE
    trainer.num_workers = 0
    trainer.gee_ratio = GEE_RATIO
    trainer._sampler_report = None
    loader, samples = trainer._build_train_loader(0)
    assert samples == SAMPLES_PER_EPOCH
    assert trainer._sampler_report["gee_ratio_target"] == 0.70
    assert trainer._sampler_report["gee_strata"] == 37
    assert len(loader) == 8832 // BATCH_SIZE  # 276 steps/epoch
    # first batch draws the frozen ratio in expectation
    batch = next(iter(loader))
    assert batch is not None


def test_epoch_definition_drift_fails_closed() -> None:
    trainer = PlatformStratifiedTrainerV4_6_R1.__new__(PlatformStratifiedTrainerV4_6_R1)
    trainer.train_dataset = _FakeDataset(_corpus()[:-33])  # 8,784 rows -> 275 steps
    trainer.batch_size = BATCH_SIZE
    trainer.num_workers = 0
    trainer.gee_ratio = GEE_RATIO
    trainer._sampler_report = None
    with pytest.raises(ValueError, match="epoch definition drift"):
        trainer._build_train_loader(0)


def test_missing_workflows_attribute_fails_closed() -> None:
    trainer = PlatformStratifiedTrainerV4_6_R1.__new__(PlatformStratifiedTrainerV4_6_R1)
    trainer.train_dataset = object()
    trainer.batch_size = BATCH_SIZE
    trainer.num_workers = 0
    trainer.gee_ratio = GEE_RATIO
    trainer._sampler_report = None
    with pytest.raises(ValueError, match="no .workflows"):
        trainer._build_train_loader(0)


def test_env_override_hook_is_wired() -> None:
    src = (PROJECT_ROOT / "scripts" / "train_v4_6_quality_gate.py").read_text(encoding="utf-8")
    assert 'GIS_V4_TRAINER' in src and "platform_r1" in src
