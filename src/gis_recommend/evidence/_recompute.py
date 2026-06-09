# -*- coding: utf-8 -*-
"""MVCS v1 Metric Recomputation — Interpretive Report Layer.

Pure function. Loads a model from checkpoint, re-runs evaluation,
produces RecomputeReport comparing archival_truth vs derived_truth.
"""

__all__ = ["recompute_metrics"]

__allowed_imports__ = [
    "torch",
    "datetime",
    "sys",
    "pathlib",
    "typing",
    "gis_recommend.evidence._schemas",
]
__forbidden_imports__ = [
    "torch.optim",          # never train
    "torch.nn",             # never modify model
    "gis_recommend.training",
    "gis_recommend.inference",
    "gis_recommend.models",
    "gis_recommend.pipelines",
]
__layer__ = "interpretive_report"


def recompute_metrics(
    checkpoint_path: str,
    dataset_path: str,
    decode_policy_override: dict | None = None,
    seed: int | None = None,
) -> "RecomputeReport":
    """Recompute metrics from a checkpoint against a dataset.

    Rules:
      1. If decode_policy_override is None → use stored decode_policy
         from checkpoint.metric_bundle.
      2. ALL recomputed metrics are labeled derived_truth.
      3. Stored metrics are labeled archival_truth.
      4. Deltas are computed as: recomputed - stored.
      5. Divergence flags annotated with possible_causes.

    When recomputation is VALID:
      - model_state_dict loads successfully
      - dataset is available at dataset_path
      - decode_policy is known (from bundle or override)

    When recomputation is UNDEFINED:
      - Returns RecomputeReport with empty metrics and conclusion explaining why.

    Never writes to any file. Never gates any runtime behavior.
    """
    raise NotImplementedError
