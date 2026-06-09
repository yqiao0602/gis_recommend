# -*- coding: utf-8 -*-
"""MVCS v1 Checkpoint Validity Classification — Interpretive Report Layer.

Pure function. Reads Snapshot Truth, produces ValidityReport.
Output is ADVISORY ONLY — never gates loading.
"""

__all__ = ["classify_checkpoint_validity"]

__allowed_imports__ = [
    "torch",
    "hashlib",
    "pathlib",
    "typing",
    "gis_recommend.evidence._schemas",
    "gis_recommend.evidence._boundary",
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


def classify_checkpoint_validity(checkpoint_path: str) -> "ValidityReport":
    """Check structural, provenance, and file integrity of a checkpoint.

    Returns ValidityReport with status ∈ {"valid", "warn", "uncertain"}.

    This function:
      - Loads the checkpoint file
      - Checks format_version support
      - Checks model_state_dict key/shape compatibility
      - Verifies provenance block integrity
      - Verifies file checksum

    This function DOES NOT:
      - Raise on semantic issues (only on I/O errors like file-not-found)
      - Block or alter any runtime code path
      - Write to any file

    The caller (human operator or CLI tool) decides what to do with the report.
    """
    raise NotImplementedError
