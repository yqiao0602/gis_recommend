#!/usr/bin/env python3
"""Platform-stratified sampler for M1 V4.6 controlled rerun on paper_v1.

Two-level sampling (user-fixed protocol 2026-09-08):
  Level 1 — platform ratio, GEE:QGIS configurable (main plan 70:30);
  Level 2 — platform-specific stratification:
      GEE  : task_type balanced (the 47 semantic task types, same signal the
             original V4.5 WeightedRandomSampler used);
      QGIS : chain-length balanced over four strata (1, 2-3, 4-7, 8+), because
             QGIS has only 3 provenance-type task_types and its real imbalance
             is single-step (367) vs multi-step (262).

Epoch definition (user-fixed): samples_per_epoch = ceil(N / batch_size) *
batch_size (e.g. 279*32 = 8,928 for paper_v1 train), NOT len(dataset).
Replacement=True throughout. Validation stays frozen and un-sampled.

The pilot's purpose is protocol verification only (observed ratios, stratum
coverage, repetition rates, batch contract) — never model selection.
"""

from __future__ import annotations

import math
from collections import Counter
from typing import Any

import torch
from torch.utils.data import WeightedRandomSampler

# M1-R1 frozen protocol: the effective train set is paper_v1's 8,817 non-empty
# rows (95 empty-text rows are excluded), batch 32 -> ceil(8817/32)*32 = 8,832.
TRAIN_ROWS = 8817
BATCH_SIZE = 32
SAMPLES_PER_EPOCH = math.ceil(TRAIN_ROWS / BATCH_SIZE) * BATCH_SIZE  # 8832


def _platform(row: dict[str, Any]) -> str:
    return str(row.get("platform") or row.get("source_platform") or "").lower()


def _content_tokens(row: dict[str, Any]) -> list[Any]:
    """Content-token list of a workflow row, accepting both representations:
    the manifest's ``l3_codes``/``l3_chain`` (L3_xx_xx_xx strings) and the V4
    trainer's ``l3_sequence`` (integer token ids with -3 START / -4 END)."""
    for key in ("l3_codes", "l3_chain"):
        codes = row.get(key)
        if codes:
            content = [c for c in codes if str(c).startswith("L3")]
            if content:
                return content
    sequence = row.get("l3_sequence")
    if sequence:
        return [t for t in sequence if isinstance(t, int) and t >= 0]
    return []


def _task_type(row: dict[str, Any]) -> str:
    """GEE-internal stratum key. The 8,283-row authority carries a constant
    task_type ('GEE_COMPLETE_OUTPUT_WORKFLOW'); the semantic signal available
    per row is the first content token (entry family, 37 strata)."""
    meta = row.get("task_metadata") or {}
    explicit = str(meta.get("task_type") or row.get("task_type") or "")
    if explicit and explicit != "GEE_COMPLETE_OUTPUT_WORKFLOW":
        return explicit
    content = _content_tokens(row)
    return str(content[0]) if content else ""


def _chain_length(row: dict[str, Any]) -> int:
    return len(_content_tokens(row))


def _length_stratum(length: int) -> str:
    if length <= 1:
        return "1"
    if length <= 3:
        return "2-3"
    if length <= 7:
        return "4-7"
    return "8+"


def compute_platform_stratified_weights(
    workflows: list[dict[str, Any]],
    *,
    gee_ratio: float,
) -> tuple[list[float], dict[str, Any]]:
    """Per-row sampling weights implementing the two-level protocol.

    weight(row) = (platform_target_share / platform_row_share)
                * (stratum_target_share / stratum_row_share within platform)
    Rows are drawn with replacement; multiplying by the two inverse-share
    factors makes the expected per-epoch composition match the protocol.
    """
    if not 0.0 < gee_ratio < 1.0:
        raise ValueError(f"gee_ratio must be in (0,1), got {gee_ratio}")
    platforms = [_platform(w) for w in workflows]
    platform_counts = Counter(platforms)
    unknown = {p for p in platform_counts if p not in ("gee", "qgis")}
    if unknown:
        raise ValueError(f"unknown platform labels: {unknown}")

    n_gee, n_qgis = platform_counts["gee"], platform_counts["qgis"]
    if n_gee == 0 or n_qgis == 0:
        raise ValueError("both platforms must be present")

    # Level 1: platform factor — each platform's total weight mass equals its
    # target share of the epoch.
    platform_factor = {"gee": gee_ratio, "qgis": 1.0 - gee_ratio}

    # Level 2: within-platform stratum factors — each stratum's total mass is
    # uniform inside its platform (1/count per row, normalized by the number of
    # strata so each platform's strata sum to exactly its platform mass).
    gee_task_counts: Counter[str] = Counter()
    qgis_len_counts: Counter[str] = Counter()
    strata: list[str] = []
    for w, p in zip(workflows, platforms):
        if p == "gee":
            t = _task_type(w)
            gee_task_counts[t] += 1
            strata.append(t)
        else:
            s = _length_stratum(_chain_length(w))
            qgis_len_counts[s] += 1
            strata.append(s)

    gee_tasks = [t for t in gee_task_counts if t]
    if len(gee_tasks) != len(gee_task_counts):
        raise ValueError("GEE rows with empty task_type cannot be stratified")
    stratum_factor: dict[tuple[str, str], float] = {}
    for t, count in gee_task_counts.items():
        stratum_factor[("gee", t)] = 1.0 / (count * len(gee_task_counts))
    for s, count in qgis_len_counts.items():
        stratum_factor[("qgis", s)] = 1.0 / (count * len(qgis_len_counts))

    weights = [
        platform_factor[p] * stratum_factor[(p, s)]
        for p, s in zip(platforms, strata)
    ]
    report = {
        "rows": len(workflows),
        "platform_counts": dict(platform_counts),
        "gee_ratio_target": gee_ratio,
        "gee_strata": len(gee_task_counts),
        "qgis_length_strata": dict(qgis_len_counts),
        "weight_min": min(weights),
        "weight_max": max(weights),
        "expected_qgis_repeats_per_epoch": round(
            (1.0 - gee_ratio) * len(workflows) / n_qgis, 2),
        "expected_gee_usage_per_epoch": round(
            gee_ratio * len(workflows) / n_gee, 3),
    }
    return weights, report


def build_platform_stratified_sampler(
    workflows: list[dict[str, Any]],
    *,
    gee_ratio: float,
    batch_size: int = BATCH_SIZE,
) -> tuple[WeightedRandomSampler, dict[str, Any]]:
    weights, report = compute_platform_stratified_weights(workflows, gee_ratio=gee_ratio)
    samples_per_epoch = math.ceil(len(workflows) / batch_size) * batch_size
    report["samples_per_epoch"] = samples_per_epoch
    sampler = WeightedRandomSampler(
        weights=weights, num_samples=samples_per_epoch, replacement=True)
    return sampler, report


def audit_sampled_epoch(
    workflows: list[dict[str, Any]],
    indices: list[int],
) -> dict[str, Any]:
    """Observed-composition audit for a drawn epoch (pilot verification)."""
    drawn = [workflows[i] for i in indices]
    platforms = Counter(_platform(w) for w in drawn)
    qgis_lengths = Counter(_length_stratum(_chain_length(w)) for w in drawn if _platform(w) == "qgis")
    gee_tasks = Counter(_task_type(w) for w in drawn if _platform(w) == "gee")
    qgis_ids = Counter(i for i in indices if _platform(workflows[i]) == "qgis")
    return {
        "n": len(drawn),
        "platform_share": {
            "gee": round(platforms.get("gee", 0) / len(drawn), 4),
            "qgis": round(platforms.get("qgis", 0) / len(drawn), 4),
        },
        "qgis_length_strata_share": {
            s: round(c / max(platforms.get("qgis", 0), 1), 4)
            for s, c in sorted(qgis_lengths.items())
        },
        "gee_task_types_observed": len(gee_tasks),
        "qgis_unique_rows_drawn": len(qgis_ids),
        "qgis_expected_unique_rows": len(
            [w for w in workflows if _platform(w) == "qgis"]),
    }
