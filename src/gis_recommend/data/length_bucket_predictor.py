"""Task-conditioned workflow length bucket prediction.

Pure lookup from precomputed task_type_length_stats.json — no training required.
Provides per-task decoding constraints for EOS suppression and min_length.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


@dataclass(frozen=True)
class LengthBucket:
    bucket: str
    min_length: int
    eos_suppress_until: int
    expected_length: int


BUCKET_DEFS = [
    LengthBucket("short", 1, 0, 3),
    LengthBucket("medium", 3, 2, 5),
    LengthBucket("long", 5, 4, 8),
    LengthBucket("very_long", 7, 6, 13),
]

_FALLBACK = BUCKET_DEFS[1]  # medium


def _classify(median: int) -> LengthBucket:
    if median <= 4:
        return BUCKET_DEFS[0]
    if median <= 7:
        return BUCKET_DEFS[1]
    if median <= 12:
        return BUCKET_DEFS[2]
    return BUCKET_DEFS[3]


def default_length_stats_path(project_root: Optional[Path] = None) -> Path:
    if project_root is None:
        project_root = Path(__file__).resolve().parents[3]
    candidates = [
        project_root / "outputs_v2" / "pipeline" / "step8_quality_gate" / "task_type_length_stats.json",
        project_root / "outputs_v2" / "task_type_length_stats.json",
        project_root / "outputs" / "task_type_length_stats.json",
    ]
    for path in candidates:
        if path.exists():
            return path
    return candidates[0]


class LengthBucketPredictor:
    def __init__(self, stats_path: Optional[Path] = None) -> None:
        if stats_path is None:
            stats_path = default_length_stats_path()
        self._by_task: dict[str, LengthBucket] = {}
        if stats_path.exists():
            raw = json.loads(stats_path.read_text(encoding="utf-8"))
            for task_type, stats in raw.get("by_task_type", {}).items():
                median = int(stats.get("median", 8))
                self._by_task[task_type] = _classify(median)
        else:
            self._by_task = {}

    def predict(self, task_type: str) -> LengthBucket:
        return self._by_task.get(task_type, _FALLBACK)
