# -*- coding: utf-8 -*-
"""Checkpoint provenance snapshot helpers.

Contains:
  - build_provenance_block() — constructs an observational snapshot block

This module does not load checkpoints and does not gate runtime execution.
"""

__all__ = [
    "build_provenance_block",
    "StructuralIncompatibilityError",
    "ProvenanceError",
    "ProvenanceIntegrityError",
]

__allowed_imports__ = [
    "torch",
    "json",
    "hashlib",
    "uuid",
    "datetime",
    "pathlib",
    "sys",
    "typing",
    "gis_recommend.evidence._schemas",
    "gis_recommend.evidence._boundary",
    "gis_recommend.config.transformer_config",
]
__forbidden_imports__ = []
__layer__ = "snapshot_report"


class StructuralIncompatibilityError(Exception):
    """Compatibility exception for old callers; this module no longer raises it."""


class ProvenanceError(Exception):
    """Raised when provenance block cannot be built on first save."""


class ProvenanceIntegrityError(Exception):
    """Raised when provenance is modified mid-run or run_id changes."""


# ---------------------------------------------------------------------------
# Provenance block construction (MVCS §1.2 / RULES R03-R07)
# ---------------------------------------------------------------------------

def build_provenance_block(
    trainer_instance,  # ScheduledSamplingTrainerV4_X
    warmstart_checkpoint_loaded: bool,
    warmstart_checkpoint_path: str,
    warmstart_run_id: str | None,
    warmstart_file_sha256: str | None,
    training_history_sha256: str | None = None,
) -> dict:
    """Build the ProvenanceBlock dict for checkpoint_v5.

    The returned dict is a snapshot payload. It must not control checkpoint
    loading, sampler selection, decode behavior, or training decisions.

    Fields computed:
      - run_id: UUID4, generated fresh
      - parent_run_id: from warmstart source, or null
      - parent_checkpoint_sha256: sha256 of warmstart .pth file, or null
      - timestamp_iso: UTC ISO 8601
      - trainer_class: fully-qualified class name
      - trainer_mro: full MRO chain
      - code_identity: sha256 of script, model module, config module
      - config_snapshot: all V4_* constants + warmstart_path
      - dataset_identity: data file sha256, split counts, seed, task types
      - framework_identity: python, pytorch, cuda, gpu
      - training_history_sha256: null at first save, set at training end
    """
    raise NotImplementedError
