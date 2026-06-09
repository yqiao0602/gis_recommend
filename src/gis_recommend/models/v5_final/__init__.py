"""V5_final isolated runtime package.

V5_final is a memory-augmented autoregressive workflow planner with diagnostic
retrieval-attention traces.  Diagnostic artifacts exported here are report-only:
they must not gate training, loading, decoding, or downstream execution.
"""

from .checkpoint import (
    V5FinalCheckpointError,
    load_v5_final_checkpoint,
    load_v5_final_model,
    save_v5_final_checkpoint,
)
from .config import V5FinalConfig
from .diagnostics import DIAGNOSTIC_DISCLAIMER, extract_diagnostic_graph
from .empirical import build_v5_empirical_prediction_record
from .io_mask import IOMaskBuilder
from .losses import compute_v5_loss
from .model import DecodeResult, FrozenBertEncoder, V5FinalModel, V5ForwardOutput
from .text_features import deterministic_task_embeddings

__all__ = [
    "DIAGNOSTIC_DISCLAIMER",
    "DecodeResult",
    "FrozenBertEncoder",
    "IOMaskBuilder",
    "V5FinalCheckpointError",
    "V5FinalConfig",
    "V5FinalModel",
    "V5ForwardOutput",
    "build_v5_empirical_prediction_record",
    "compute_v5_loss",
    "deterministic_task_embeddings",
    "extract_diagnostic_graph",
    "load_v5_final_checkpoint",
    "load_v5_final_model",
    "save_v5_final_checkpoint",
]
