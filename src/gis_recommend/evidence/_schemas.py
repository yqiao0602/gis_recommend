# -*- coding: utf-8 -*-
from __future__ import annotations

"""MVCS v1 Schema Definitions — Snapshot Evidence Layer.

All dataclass definitions for checkpoint_v5 format.
These are PURE DATA definitions — no logic, no validation, no I/O.
"""

__all__ = [
    "ProvenanceBlock",
    "CodeIdentity",
    "ConfigSnapshot",
    "DatasetIdentity",
    "FrameworkIdentity",
    "SelectorPolicy",
    "DecodePolicy",
    "MetricEntry",
    "EpochContext",
    "MetricBundle",
    "CheckpointV5",
    # Interpretive report schemas
    "ValidityReport",
    "StructuralCheck",
    "ProvenanceCheck",
    "IntegrityCheck",
    "LineageGraph",
    "LineageNode",
    "LineageEdge",
    "BrokenLink",
    "RecomputeReport",
    "RecomputeContext",
    "DivergenceFlag",
    "ComparisonReport",
    "CheckpointIdentity",
    "MetricDelta",
    "DispatchDiff",
    "ArchaeologyReport",
]

__allowed_imports__ = ["dataclasses", "typing"]
__forbidden_imports__ = ["torch", "torch.nn", "torch.optim"]
__layer__ = "snapshot_evidence"

from dataclasses import dataclass, field
from typing import Any


# ===========================================================================
# Snapshot Truth — Provenance Block
# ===========================================================================

@dataclass(frozen=True)
class CodeIdentity:
    script_path: str
    script_sha256: str
    model_module_sha256: str
    config_module_sha256: str


@dataclass(frozen=True)
class ConfigSnapshot:
    warmstart_path: str | None
    constants: dict[str, Any]


@dataclass(frozen=True)
class DatasetIdentity:
    data_path: str
    data_sha256: str
    num_train: int
    num_val: int
    num_test: int
    split_seed: int
    num_task_types: int


@dataclass(frozen=True)
class FrameworkIdentity:
    python_version: str
    pytorch_version: str
    cuda_version: str | None
    gpu_name: str | None


@dataclass(frozen=True)
class ProvenanceBlock:
    format_version: str          # "gis_recommend.checkpoint.v5"
    run_id: str                  # UUID4, opaque
    parent_run_id: str | None
    parent_checkpoint_sha256: str | None
    timestamp_iso: str
    trainer_class: str
    trainer_mro: list[str]
    code_identity: CodeIdentity
    config_snapshot: ConfigSnapshot
    dataset_identity: DatasetIdentity
    framework_identity: FrameworkIdentity
    training_history_sha256: str | None


# ===========================================================================
# Snapshot Truth — Metric Bundle
# ===========================================================================

@dataclass(frozen=True)
class SelectorPolicy:
    metric_name: str             # "val_loss" | "ar_token_acc" | ...
    direction: str               # "minimize" | "maximize"


@dataclass(frozen=True)
class DecodePolicy:
    strategy: str                # "greedy" | "nucleus" | "beam"
    temperature: float | None
    top_p: float | None
    rep_penalty: float
    rep_window: int
    min_length: int
    max_length: int


@dataclass(frozen=True)
class MetricEntry:
    name: str
    value: float
    phase: str                   # "train" | "val" | "test"
    decode_dependent: bool


@dataclass(frozen=True)
class EpochContext:
    epoch: int
    tf_ratio: float
    ar_ratio: float


@dataclass(frozen=True)
class MetricBundle:
    selector_policy: SelectorPolicy
    decode_policy: DecodePolicy | None
    metrics: list[MetricEntry]
    epoch_context: EpochContext


# ===========================================================================
# Checkpoint v5 — top-level container
# ===========================================================================

@dataclass(frozen=True)
class CheckpointV5:
    model_state_dict: dict[str, Any]
    task_classifier_state_dict: dict[str, Any] | None
    epoch: int
    model_config: dict[str, Any]
    provenance: ProvenanceBlock
    metric_bundle: MetricBundle
    val_loss: float | None
    ar_token_acc: float | None
    ar_seq_em: float | None


# ===========================================================================
# Interpretive Report — Validity
# ===========================================================================

@dataclass(frozen=True)
class StructuralCheck:
    can_load_model: bool
    format_supported: bool
    key_mismatches: list[str]
    shape_mismatches: list[str]


@dataclass(frozen=True)
class ProvenanceCheck:
    has_provenance: bool
    has_parent: bool
    parent_checkpoint_exists: bool | None
    parent_hash_matches: bool | None
    code_sha256_matches_current: bool | None
    config_diff_summary: str | None


@dataclass(frozen=True)
class IntegrityCheck:
    file_sha256: str
    file_size_bytes: int
    torch_load_succeeded: bool


@dataclass(frozen=True)
class ValidityReport:
    checkpoint_path: str
    format_version: str | None
    status: str                  # "valid" | "warn" | "uncertain" — ADVISORY ONLY
    structural_check: StructuralCheck
    provenance_check: ProvenanceCheck
    integrity_check: IntegrityCheck
    recommendations: list[str]


# ===========================================================================
# Interpretive Report — Lineage
# ===========================================================================

@dataclass(frozen=True)
class LineageNode:
    run_id: str
    trainer_class: str
    timestamp: str | None
    selector_policy: str | None
    epoch: int | None
    parent_run_id: str | None
    is_root: bool


@dataclass(frozen=True)
class LineageEdge:
    from_run_id: str
    to_run_id: str
    warmstart_path: str | None
    parent_hash_matches: bool


@dataclass(frozen=True)
class BrokenLink:
    child_run_id: str
    declared_parent_id: str
    reason: str


@dataclass(frozen=True)
class LineageGraph:
    root_run_id: str | None
    nodes: list[LineageNode]
    edges: list[LineageEdge]
    broken_links: list[BrokenLink]
    max_depth: int
    is_contiguous: bool


# ===========================================================================
# Interpretive Report — Recompute
# ===========================================================================

@dataclass(frozen=True)
class RecomputeContext:
    decode_policy_used: dict[str, Any]
    decode_policy_matches_stored: bool
    seed: int | None
    python_version: str
    pytorch_version: str
    cuda_version: str | None
    gpu_name: str | None
    num_batches_evaluated: int
    dataset_sha256: str


@dataclass(frozen=True)
class DivergenceFlag:
    metric_name: str
    delta: float
    severity: str               # "negligible" | "notable" | "significant"
    possible_causes: list[str]


@dataclass(frozen=True)
class RecomputeReport:
    checkpoint_path: str
    recompute_timestamp: str
    recompute_context: RecomputeContext
    stored_metrics: dict[str, float]       # archival_truth
    recomputed_metrics: dict[str, float]   # derived_truth
    deltas: dict[str, float]
    divergence_flags: list[DivergenceFlag]
    conclusion: str


# ===========================================================================
# Interpretive Report — Compare
# ===========================================================================

@dataclass(frozen=True)
class CheckpointIdentity:
    run_id: str
    trainer_class: str
    epoch: int
    selector_policy: str
    timestamp: str | None


@dataclass(frozen=True)
class MetricDelta:
    metric_name: str
    value_a: float
    value_b: float
    delta: float
    direction_better: str | None
    comparable: bool


@dataclass(frozen=True)
class ComparisonReport:
    checkpoint_a: CheckpointIdentity
    checkpoint_b: CheckpointIdentity
    selector_warning: str | None
    decode_warning: str | None
    metric_deltas: list[MetricDelta]
    interpretive_notes: list[str]
    comparison_valid: bool


# ===========================================================================
# Interpretive Report — Dispatch Diff
# ===========================================================================

@dataclass(frozen=True)
class DispatchDiff:
    trainer_a: str
    trainer_b: str
    shared_mro: list[str]
    a_only_overrides: list[str]
    b_only_overrides: list[str]
    both_override: list[str]
    effective_dispatch_a: dict[str, str]
    effective_dispatch_b: dict[str, str]
    behavioral_diff: list[str]


# ===========================================================================
# Interpretive Report — Archaeology (top-level composed report)
# ===========================================================================

@dataclass(frozen=True)
class ArchaeologyReport:
    checkpoint_path: str
    run_id: str
    trainer_class: str
    timestamp: str | None
    lineage_graph: LineageGraph
    stored_metrics: dict[str, float]
    decode_policy: dict[str, Any]
    selector_policy: dict[str, Any]
    validity: ValidityReport
    recompute: RecomputeReport | None
    config_summary: str
    config_diff_from_parent: str | None
    findings: list[str]
    confidence: str             # "high" | "medium" | "low"
    uncertainty_sources: list[str]
    recommended_actions: list[str]
