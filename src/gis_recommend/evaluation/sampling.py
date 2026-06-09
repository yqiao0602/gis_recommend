# -*- coding: utf-8 -*-
"""Test set construction and stratified sampling for the evaluation pipeline.

Extracted from scripts/evaluate_system.py (2026-04-16) to keep sampling concerns
isolated from reranker/report logic.

Public API:
    resolve_eval_max_samples(eval_mode, explicit_samples)
    build_test_set(workflows, max_samples=None)

Internal helpers (prefixed with _) are exported for tests but not intended for
external use.
"""
from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path
from typing import Optional

from gis_recommend.config.transformer_config import OUTPUT_DIR
from gis_recommend.training.splits import validate_index_subset

SPLIT_PATH = OUTPUT_DIR / "dataset_splits_v4.json"

EVAL_MODE_MAX_SAMPLES = {
    "smoke": 200,
    "dev": 1000,
    "full": None,
}


def resolve_eval_max_samples(eval_mode: str, explicit_samples: Optional[int]) -> Optional[int]:
    """Resolve the effective sample budget for this evaluation run."""
    if explicit_samples is not None:
        return explicit_samples
    return EVAL_MODE_MAX_SAMPLES[eval_mode]


def _allocate_type_quotas(by_type: dict[str, list], max_samples: int) -> dict[str, int]:
    """Allocate deterministic stratified sample quotas per task type."""
    groups = sorted(by_type.items())
    total_items = sum(len(items) for _, items in groups)
    if max_samples >= total_items:
        return {tt: len(items) for tt, items in groups}

    quotas = {tt: 0 for tt, _ in groups}
    if max_samples <= 0:
        return quotas

    if max_samples < len(groups):
        ranked = sorted(groups, key=lambda kv: (-len(kv[1]), kv[0]))
        for tt, _ in ranked[:max_samples]:
            quotas[tt] = 1
        return quotas

    for tt, _ in groups:
        quotas[tt] = 1
    remaining = max_samples - len(groups)
    if remaining <= 0:
        return quotas

    capacity = {tt: len(items) - quotas[tt] for tt, items in groups}
    total_capacity = sum(max(v, 0) for v in capacity.values())
    if total_capacity <= 0:
        return quotas

    fractional: list[tuple[float, str]] = []
    for tt, _ in groups:
        cap = max(capacity[tt], 0)
        if cap == 0:
            continue
        raw_extra = remaining * cap / total_capacity
        extra = min(cap, int(raw_extra))
        quotas[tt] += extra
        fractional.append((raw_extra - extra, tt))

    leftover = max_samples - sum(quotas.values())
    for _, tt in sorted(fractional, key=lambda item: (-item[0], item[1])):
        if leftover <= 0:
            break
        if quotas[tt] < len(by_type[tt]):
            quotas[tt] += 1
            leftover -= 1

    if leftover > 0:
        for tt, _ in sorted(groups, key=lambda kv: (-len(kv[1]), kv[0])):
            if leftover <= 0:
                break
            while quotas[tt] < len(by_type[tt]) and leftover > 0:
                quotas[tt] += 1
                leftover -= 1

    return quotas


def _select_evenly_spaced_items(items: list[tuple[int, dict]], k: int) -> list[tuple[int, dict]]:
    """Pick k deterministic representatives across the sorted item list."""
    if k <= 0:
        return []

    items_sorted = sorted(items, key=lambda x: (len(x[1]["l3_sequence"]), x[0]))
    n = len(items_sorted)
    if k >= n:
        return items_sorted
    if k == 1:
        return [items_sorted[n // 2]]

    chosen = []
    used = set()
    for i in range(k):
        idx = int(i * (n - 1) / (k - 1))
        while idx in used and idx + 1 < n:
            idx += 1
        used.add(idx)
        chosen.append(items_sorted[idx])
    return chosen


def build_test_set(
    workflows: list,
    max_samples: Optional[int] = None,
    *,
    split_path: Optional[Path] = None,
) -> tuple[list, dict]:
    """Build test set from dataset_splits_v4.json (same split as training).

    Uses the test_indices from the training split file to ensure
    NO overlap with training/validation data.

    Then applies deterministic stratified subsampling if max_samples is specified.

    Args:
        workflows: the full labeled workflow list (V4).
        max_samples: if given and smaller than the test split, take a stratified sample.
        split_path: override the default dataset_splits_v4.json path (used in tests).
    """
    path = split_path or SPLIT_PATH
    if not path.exists():
        raise FileNotFoundError(
            f"Split file not found: {path}. "
            f"Run training first to generate dataset_splits_v4.json"
        )
    with open(path, 'r', encoding='utf-8') as f:
        splits = json.load(f)
    test_indices = splits['test_indices']
    validate_index_subset(test_indices, len(workflows), label="test_indices")
    print(f"  Loaded {len(test_indices)} test indices from {path}")

    test_workflows = [workflows[i] for i in test_indices]

    by_type: dict[str, list] = defaultdict(list)
    for i, w in enumerate(test_workflows):
        tt = w.get("task_metadata", {}).get("task_type", "Unknown")
        by_type[tt].append((test_indices[i], w))

    coverage_info = {"included": [], "excluded": []}

    if max_samples is None or max_samples >= len(test_indices):
        selected_indices = list(test_indices)
        for tt, items in sorted(by_type.items()):
            coverage_info["included"].append(
                {"task_type": tt, "count": len(items), "sampled": len(items)}
            )
    else:
        quotas = _allocate_type_quotas(by_type, max_samples)
        selected_indices = []
        for tt, items in sorted(by_type.items()):
            k = quotas.get(tt, 0)
            if k <= 0:
                coverage_info["excluded"].append({"task_type": tt, "count": len(items)})
                continue

            selected = _select_evenly_spaced_items(items, k)
            coverage_info["included"].append(
                {"task_type": tt, "count": len(items), "sampled": len(selected)}
            )
            selected_indices.extend([idx for idx, _ in selected])

    test_set = []
    for idx in selected_indices:
        w = workflows[idx]
        test_set.append({
            "index": idx,
            "task_type": w.get("task_metadata", {}).get("task_type", "Unknown"),
            "task_name": w.get("task_metadata", {}).get("task_name", ""),
            "task_description": w.get("task_metadata", {}).get("task_description", ""),
            "l3_sequence": w["l3_sequence"],
            "l3_codes": w.get("l3_codes", []),
        })

    return test_set, coverage_info
