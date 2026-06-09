# -*- coding: utf-8 -*-
"""MVCS v1 Archaeology Report Generator — Interpretive Report Layer.

Pure function. Composes all 5 other interpretive functions into a
comprehensive archaeology report. The top-level entry point for
checkpoint archaeology.
"""

__all__ = ["generate_archaeology_report"]

__allowed_imports__ = [
    "pathlib",
    "typing",
    "gis_recommend.evidence._schemas",
    "gis_recommend.evidence._validity",
    "gis_recommend.evidence._lineage",
    "gis_recommend.evidence._recompute",
    "gis_recommend.evidence._compare",
]
__forbidden_imports__ = [
    "torch",
    "torch.optim",
    "torch.nn",
    "gis_recommend.training",
    "gis_recommend.inference",
    "gis_recommend.models",
    "gis_recommend.pipelines",
]
__layer__ = "interpretive_report"


def generate_archaeology_report(
    checkpoint_path: str,
    known_checkpoints: list[str],
    dataset_path: str | None = None,
) -> "ArchaeologyReport":
    """Generate a comprehensive checkpoint archaeology report.

    Composes:
      1. classify_checkpoint_validity(checkpoint_path) → ValidityReport
      2. reconstruct_lineage(checkpoint_path, known_checkpoints) → LineageGraph
      3. recompute_metrics(checkpoint_path, dataset_path) → RecomputeReport (if dataset available)
      4. For each known checkpoint, if parent exists:
         compare_metrics(parent_path, checkpoint_path) → ComparisonReport
         diff_dispatch(parent_path, checkpoint_path) → DispatchDiff
      5. Combine all into ArchaeologyReport

    The report:
      - Presents archival_truth and derived_truth side by side.
      - Surfaces all broken links, hash mismatches, decode policy mismatches.
      - Labels confidence and uncertainty sources explicitly.
      - Provides recommended_actions that are ADVISORY ONLY.

    Never writes to any file. Never gates any runtime behavior.
    Never triggers any training, inference, or deployment action.
    """
    raise NotImplementedError
