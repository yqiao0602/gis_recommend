from __future__ import annotations

from pathlib import Path
from typing import Optional

import torch

from .config import V5FinalConfig
from .model import V5FinalModel


FORMAT_VERSION = "gis_recommend.checkpoint.v5"
MODEL_VERSION = "v5_final"
ARCHITECTURE = "memory_augmented_ar_planner"


class V5FinalCheckpointError(ValueError):
    pass


def _required_provenance(provenance: Optional[dict]) -> dict:
    payload = dict(provenance or {})
    payload.update(
        {
            "format_version": FORMAT_VERSION,
            "model_version": MODEL_VERSION,
            "architecture": ARCHITECTURE,
        }
    )
    return payload


def save_v5_final_checkpoint(
    path: Path | str,
    *,
    model: V5FinalModel,
    config: V5FinalConfig,
    metric_bundle: Optional[dict] = None,
    provenance: Optional[dict] = None,
) -> dict:
    payload = {
        "model_state_dict": model.state_dict(),
        "provenance": _required_provenance(provenance),
        "metric_bundle": dict(metric_bundle or {}),
        "v5_config": config.checkpoint_v5_config(),
    }
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    torch.save(payload, out)
    return payload


def load_v5_final_checkpoint(path: Path | str, *, map_location: str | torch.device = "cpu") -> dict:
    try:
        payload = torch.load(path, map_location=map_location, weights_only=True)
    except TypeError:
        payload = torch.load(path, map_location=map_location)
    _validate_payload(payload, path)
    return payload


def load_v5_final_model(
    path: Path | str,
    *,
    map_location: str | torch.device = "cpu",
) -> tuple[V5FinalModel, dict]:
    payload = load_v5_final_checkpoint(path, map_location=map_location)
    config = V5FinalConfig.from_dict(payload["v5_config"])
    model = V5FinalModel(config)
    model.load_state_dict(payload["model_state_dict"], strict=True)
    model.eval()
    return model, payload


def _validate_payload(payload: object, path: Path | str) -> None:
    if not isinstance(payload, dict):
        raise V5FinalCheckpointError(f"V5 checkpoint must be a wrapped dict: {path}")
    required = {"model_state_dict", "provenance", "metric_bundle", "v5_config"}
    missing = required.difference(payload)
    if missing:
        raise V5FinalCheckpointError(f"Missing V5 checkpoint fields {sorted(missing)}: {path}")
    provenance = payload.get("provenance")
    if not isinstance(provenance, dict):
        raise V5FinalCheckpointError("V5 checkpoint provenance must be a dict")
    if provenance.get("format_version") != FORMAT_VERSION:
        raise V5FinalCheckpointError("Unsupported V5 checkpoint format_version")
    if provenance.get("model_version") != MODEL_VERSION:
        raise V5FinalCheckpointError("Unsupported V5 checkpoint model_version")
    if provenance.get("architecture") != ARCHITECTURE:
        raise V5FinalCheckpointError("Unsupported V5 checkpoint architecture")
    state = payload.get("model_state_dict")
    if not isinstance(state, dict):
        raise V5FinalCheckpointError("V5 checkpoint model_state_dict must be a dict")
    required_prefixes = ("pvm.w_struct.", "pvm.w_key.", "pvm.w_proj.")
    for prefix in required_prefixes:
        if not any(str(key).startswith(prefix) for key in state):
            raise V5FinalCheckpointError(f"V5 checkpoint missing required {prefix} keys")
    config = payload.get("v5_config")
    if not isinstance(config, dict):
        raise V5FinalCheckpointError("V5 checkpoint v5_config must be a dict")
    if config.get("gamma") != 0.3 or config.get("rho") != 1.5:
        raise V5FinalCheckpointError("V5 checkpoint must use fixed gamma=0.3 and rho=1.5")
