# -*- coding: utf-8 -*-
"""gis_recommend.evidence — checkpoint snapshot/report helpers.

Boundary rule:
  This package is report-only. It MUST NOT be imported by training/,
  inference/, models/, or pipelines/ to decide runtime behavior.
"""

__all__ = [
    "build_provenance_block",
    "build_metric_bundle",
    "ProvenanceBlock",
    "MetricBundle",
    "CheckpointV5",
    "CodeIdentity",
    "ConfigSnapshot",
    "DatasetIdentity",
    "FrameworkIdentity",
    "SelectorPolicy",
    "DecodePolicy",
    "MetricEntry",
    "EpochContext",
    # Interpretive Report
    "classify_checkpoint_validity",
    "reconstruct_lineage",
    "recompute_metrics",
    "compare_metrics",
    "diff_dispatch",
    "generate_archaeology_report",
    # Report dataclasses
    "ValidityReport",
    "LineageGraph",
    "RecomputeReport",
    "ComparisonReport",
    "DispatchDiff",
    "ArchaeologyReport",
]

__allowed_imports__ = [
    "torch",
    "json",
    "hashlib",
    "uuid",
    "dataclasses",
    "datetime",
    "pathlib",
    "typing",
    "sys",
    "gis_recommend.models.transformer_model_v4",  # read-only for shape validation
    "gis_recommend.config.transformer_config",    # read-only for format_version list
]

__forbidden_imports__ = []

__layer__ = "snapshot_report"

from gis_recommend.evidence._schemas import (
    ProvenanceBlock,
    MetricBundle,
    CheckpointV5,
    CodeIdentity,
    ConfigSnapshot,
    DatasetIdentity,
    FrameworkIdentity,
    SelectorPolicy,
    DecodePolicy,
    MetricEntry,
    EpochContext,
    ValidityReport,
    LineageGraph,
    RecomputeReport,
    ComparisonReport,
    DispatchDiff,
    ArchaeologyReport,
)

from gis_recommend.evidence._provenance import (
    build_provenance_block,
)

from gis_recommend.evidence._metric_bundle import (
    build_metric_bundle,
)

from gis_recommend.evidence._validity import classify_checkpoint_validity
from gis_recommend.evidence._lineage import reconstruct_lineage
from gis_recommend.evidence._recompute import recompute_metrics
from gis_recommend.evidence._compare import compare_metrics, diff_dispatch
from gis_recommend.evidence._archaeology import generate_archaeology_report
