# -*- coding: utf-8 -*-
"""Metric bundle snapshot helpers.

Contains:
  - build_metric_bundle() — constructs an observational checkpoint payload

Metric bundles are report-only. They must not validate, block, select,
rerank, or mutate runtime execution.
"""

__all__ = [
    "build_metric_bundle",
    "IncompleteMetricError",
]

__allowed_imports__ = [
    "typing",
    "gis_recommend.evidence._schemas",
]
__forbidden_imports__ = []
__layer__ = "snapshot_report"


class IncompleteMetricError(Exception):
    """Compatibility exception for old callers; this module no longer raises it."""


# ---------------------------------------------------------------------------
# Metric bundle construction (MVCS §1.3 / RULES R08-R10)
# ---------------------------------------------------------------------------

def build_metric_bundle(
    train_metrics: dict,
    val_metrics: dict,
    gen_metrics: dict,
    epoch: int,
    tf_ratio: float,
    ar_ratio: float,
    decode_strategy: str,
    decode_temperature: float | None,
    decode_top_p: float | None,
    decode_rep_penalty: float,
    decode_rep_window: int,
    decode_min_length: int,
    decode_max_length: int,
    selector_metric_name: str,
    selector_direction: str,
) -> dict:
    """Build the MetricBundle dict for checkpoint_v5.

    The returned dict is a snapshot payload. It must not control checkpoint
    loading, sampler selection, decode behavior, or training decisions.
    """
    raise NotImplementedError
