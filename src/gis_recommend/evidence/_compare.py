# -*- coding: utf-8 -*-
"""MVCS v1 Metric Comparison + Dispatch Diff — Interpretive Report Layer.

Pure functions:
  - compare_metrics(): compares two checkpoints' metric_bundles
  - diff_dispatch(): compares two checkpoints' trainer dispatch chains
"""

__all__ = ["compare_metrics", "diff_dispatch"]

__allowed_imports__ = [
    "torch",
    "pathlib",
    "typing",
    "gis_recommend.evidence._schemas",
]
__forbidden_imports__ = [
    "torch.optim",
    "torch.nn",
    "gis_recommend.training",
    "gis_recommend.inference",
    "gis_recommend.models",
    "gis_recommend.pipelines",
]
__layer__ = "interpretive_report"


def compare_metrics(
    checkpoint_a_path: str,
    checkpoint_b_path: str,
) -> "ComparisonReport":
    """Compare metrics from two checkpoints.

    Rules:
      - If both use different decode_policy AND the metric is decode_dependent
        → comparable=false, decode_warning emitted.
      - If both use different selector_policy → selector_warning emitted.
      - NEVER declares a winner. Only reports deltas and interpretive notes.
      - NEVER gates runtime behavior.

    Returns ComparisonReport with:
      - metric_deltas: per-metric (value_b - value_a) with comparable flag
      - selector_warning: if selectors differ
      - decode_warning: if decode policies differ
      - interpretive_notes: human-readable observations
      - comparison_valid: false if fundamental incomparability detected
    """
    raise NotImplementedError


def diff_dispatch(
    checkpoint_a_path: str,
    checkpoint_b_path: str,
) -> "DispatchDiff":
    """Compare the effective dispatch chains of two training runs.

    Reads provenance.trainer_mro from each checkpoint.
    For each method in the training API surface:
      - train_epoch
      - _train_step_tf
      - _train_step_ar / _train_step_autoregressive
      - _build_train_loader
      - validate
      - evaluate_generation

    Determines which class in the MRO chain actually handles each method,
    and reports differences.

    Returns DispatchDiff with:
      - shared_mro: classes common to both MRO chains
      - a_only_overrides / b_only_overrides / both_override: method lists
      - effective_dispatch_a / effective_dispatch_b: method→class mappings
      - behavioral_diff: human-readable difference descriptions
    """
    raise NotImplementedError
