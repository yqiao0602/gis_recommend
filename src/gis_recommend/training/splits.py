# -*- coding: utf-8 -*-
"""Dataset split validation and deterministic creation helpers."""

from __future__ import annotations

import json
import random
from pathlib import Path
from typing import Any


SPLIT_KEYS = ("train_indices", "val_indices", "test_indices")


def _split_problem(splits: dict[str, Any], n_workflows: int) -> str | None:
    seen: set[int] = set()
    for key in SPLIT_KEYS:
        values = splits.get(key)
        if not isinstance(values, list):
            return f"{key} missing_or_not_list"
        for idx in values:
            if not isinstance(idx, int):
                return f"{key} non_integer_index {idx!r}"
            if idx < 0 or idx >= n_workflows:
                return f"{key} out_of_range_index {idx} for {n_workflows} workflows"
            if idx in seen:
                return f"{key} duplicate_index {idx}"
            seen.add(idx)
    if len(seen) != n_workflows:
        return f"coverage_mismatch {len(seen)} indices for {n_workflows} workflows"
    return None


def create_splits(n_workflows: int, train_ratio: float = 0.8, val_ratio: float = 0.1,
                  seed: int = 42) -> dict[str, list[int]]:
    indices = list(range(n_workflows))
    rng = random.Random(seed)
    rng.shuffle(indices)
    n_train = int(n_workflows * train_ratio)
    n_val = int(n_workflows * val_ratio)
    return {
        "train_indices": indices[:n_train],
        "val_indices": indices[n_train:n_train + n_val],
        "test_indices": indices[n_train + n_val:],
    }


def load_or_create_valid_splits(workflows: list, split_path: Path | str,
                                train_ratio: float = 0.8, val_ratio: float = 0.1,
                                seed: int = 42) -> dict[str, list[int]]:
    """Load a split file only if it exactly covers the current workflow list."""
    split_path = Path(split_path)
    n = len(workflows)
    if split_path.exists():
        with split_path.open(encoding="utf-8") as f:
            splits = json.load(f)
        problem = _split_problem(splits, n)
        if problem is None:
            print(f"  Loaded existing splits from {split_path}")
            return splits
        print(f"  Existing splits invalid ({problem}); rebuilding {split_path}")

    splits = create_splits(n, train_ratio=train_ratio, val_ratio=val_ratio, seed=seed)
    split_path.parent.mkdir(parents=True, exist_ok=True)
    with split_path.open("w", encoding="utf-8") as f:
        json.dump(splits, f)
    print(
        "  Created new splits: "
        f"train={len(splits['train_indices'])}, "
        f"val={len(splits['val_indices'])}, "
        f"test={len(splits['test_indices'])}"
    )
    return splits


def validate_split_indices(splits: dict[str, Any], n_workflows: int) -> None:
    """Raise ValueError when split indices do not match the current dataset."""
    problem = _split_problem(splits, n_workflows)
    if problem is not None:
        raise ValueError(f"Invalid dataset splits: {problem}")


def validate_index_subset(indices: list[Any], n_workflows: int, label: str = "indices") -> None:
    """Raise ValueError when a single split subset has invalid indices."""
    seen: set[int] = set()
    for idx in indices:
        if not isinstance(idx, int):
            raise ValueError(f"Invalid dataset splits: {label} non_integer_index {idx!r}")
        if idx < 0 or idx >= n_workflows:
            raise ValueError(
                f"Invalid dataset splits: {label} out_of_range_index {idx} "
                f"for {n_workflows} workflows"
            )
        if idx in seen:
            raise ValueError(f"Invalid dataset splits: {label} duplicate_index {idx}")
        seen.add(idx)
