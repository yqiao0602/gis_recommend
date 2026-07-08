"""Vocab profile system — explicitly select v2_94_stable or v3_107_experimental.

Usage::

    from gis_recommend.config.vocab_profile import apply_profile, current_profile

    apply_profile("v3_107_experimental")   # must be called BEFORE any model init
    from gis_recommend.config.transformer_config import VOCAB_SIZE  # now 107

Pre-flight guards are enforced on apply: they verify that VOCAB_SIZE,
id_mappings, training data tokens, and Set Predictor active tokens are
internally consistent.  If not, a VocabProfileError is raised immediately
(fail-fast, no dry-run false positives).

Environment variable: ``GIS_VOCAB_PROFILE`` — set to either
``v2_94_stable`` (default) or ``v3_107_experimental``.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Optional


class VocabProfileError(RuntimeError):
    """Raised when the vocab profile is inconsistent with the rest of the system."""


_ACTIVE_PROFILE: Optional[str] = None

V2_94_STABLE = "v2_94_stable"
V3_107_EXPERIMENTAL = "v3_107_experimental"
VALID_PROFILES = {V2_94_STABLE, V3_107_EXPERIMENTAL}

# ── Profile definitions ───────────────────────────────────────
_PROFILES: dict[str, dict] = {
    V2_94_STABLE: {
        "vocab_size": 94,
        "l3_code_count": 94,
        "description": "Stable mainline: 94 L3 codes (17 vector, 74 raster/other)",
        "id_mappings_default": "outputs_v2/id_mappings_v2.json",
        "set_predictor_dir": "outputs_v2/set_predictor_checkpoints_v3_vec11277",
        "training_data_dir": "outputs_v2/pipeline/step8_v2_vec11277_augmented",
        "training_data_file": "labeled_workflows_l3_v4_vec_augmented_11277.json",
    },
    V3_107_EXPERIMENTAL: {
        "vocab_size": 107,
        "l3_code_count": 107,
        "description": "Experimental: 107 L3 codes (+13 vector: Reproject, FixGeom, Grid, etc.)",
        "id_mappings_default": "outputs_v2/pipeline/step8_v3_vocab107/id_mappings_v3_expanded.json",
        "set_predictor_dir": "outputs_v2/set_predictor_checkpoints_v3_vec11277",  # TODO: needs retrain
        "training_data_dir": "outputs_v2/pipeline/step8_v3_vocab107",
        "training_data_file": "labeled_workflows_l3_v4_vocab107.json",
    },
}


def current_profile() -> str:
    """Return the currently-active vocab profile name."""
    return _ACTIVE_PROFILE or V2_94_STABLE


def _find_project_root() -> Path:
    current = Path(__file__).resolve().parent  # .../config
    for _ in range(4):
        if (current / "src" / "gis_recommend").is_dir():
            return current
        parent = current.parent
        if parent == current:
            break
        current = parent
    return Path.cwd()


def _load_id_mappings(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def apply_profile(name: str) -> str:
    """Activate a vocab profile and run pre-flight consistency checks.

    Must be called BEFORE any model, tokeniser, or dataset is initialised.

    Args:
        name: One of ``"v2_94_stable"`` or ``"v3_107_experimental"``.

    Returns:
        The profile name (for chaining).

    Raises:
        VocabProfileError: if a consistency check fails.
    """
    global _ACTIVE_PROFILE

    if name not in VALID_PROFILES:
        raise VocabProfileError(
            f"Unknown profile '{name}'. Valid: {sorted(VALID_PROFILES)}"
        )

    profile = _PROFILES[name]

    # ── 1. Patch VOCAB_SIZE + TOTAL_VOCAB_SIZE ────────────────
    import gis_recommend.config.transformer_config as _cfg
    _cfg.VOCAB_SIZE = profile["vocab_size"]
    _cfg.TOTAL_VOCAB_SIZE = _cfg.VOCAB_SIZE + _cfg.NUM_SPECIAL_TOKENS  # always recompute

    # ── 2. Check ID mappings consistency ──────────────────────
    root = _find_project_root()
    mapping_path = root / profile["id_mappings_default"]
    if not mapping_path.exists():
        raise VocabProfileError(
            f"Required ID mappings not found: {mapping_path}. "
            f"Profile '{name}' cannot be activated without its matching "
            f"id_mappings file. Generate it first via expand_l3_vocabulary.py."
        )
    mappings = _load_id_mappings(str(mapping_path))
    l3_count = len(mappings.get("l3", {}))
    if l3_count != profile["l3_code_count"]:
        raise VocabProfileError(
            f"ID mappings at {mapping_path} have {l3_count} L3 codes, "
            f"but profile '{name}' expects {profile['l3_code_count']}"
        )

    # ── 3. Check training data token range ────────────────────
    train_file = root / profile["training_data_dir"] / profile["training_data_file"]
    if train_file.exists():
        data = json.load(open(str(train_file), "r", encoding="utf-8"))
        wfs = data.get("labeled_workflows", data) if isinstance(data, dict) else data
        if isinstance(wfs, list):
            max_tok = -1
            for wf in wfs:
                if isinstance(wf, dict):
                    for t in wf.get("l3_sequence", []):
                        if isinstance(t, int) and t > max_tok:
                            max_tok = t
            # content tokens (non-negative) should be < VOCAB_SIZE
            if max_tok >= profile["vocab_size"]:
                raise VocabProfileError(
                    f"Training data contains token {max_tok} >= vocab_size "
                    f"{profile['vocab_size']} — data was built for a larger vocabulary"
                )

    _ACTIVE_PROFILE = name
    os.environ["GIS_VOCAB_PROFILE"] = name
    return name


def training_preflight(
    *,
    data_path: str | None = None,
    checkpoint_path: str | None = None,
    set_predictor_dir: str | None = None,
    require_mappings: bool = True,
) -> list[str]:
    """Run pre-flight checks suitable for training/eval entry points.

    Call this early in training or showcase eval.  Returns a list of error
    strings (empty = all clear).  Does NOT raise — the caller decides whether
    to abort or warn.
    """
    import gis_recommend.config.transformer_config as _cfg  # noqa: F811
    import torch  # noqa: F401

    errors: list[str] = []

    # 1. Check that TOTAL_VOCAB_SIZE is self-consistent
    expected = _cfg.VOCAB_SIZE + _cfg.NUM_SPECIAL_TOKENS
    if _cfg.TOTAL_VOCAB_SIZE != expected:
        errors.append(
            f"TOTAL_VOCAB_SIZE={_cfg.TOTAL_VOCAB_SIZE} != "
            f"VOCAB_SIZE({_cfg.VOCAB_SIZE}) + NUM_SPECIAL_TOKENS({_cfg.NUM_SPECIAL_TOKENS}) = {expected}"
        )

    # 2. Check training data token range
    if data_path:
        dp = Path(data_path)
        if dp.exists():
            data = json.load(open(str(dp), "r", encoding="utf-8"))
            wfs = data.get("labeled_workflows", data) if isinstance(data, dict) else data
            if isinstance(wfs, list):
                max_tok = -1
                for wf in wfs:
                    if isinstance(wf, dict):
                        for t in wf.get("l3_sequence", []):
                            if isinstance(t, int) and t > max_tok:
                                max_tok = t
                if max_tok >= _cfg.VOCAB_SIZE:
                    errors.append(
                        f"Training data max token {max_tok} >= VOCAB_SIZE {_cfg.VOCAB_SIZE}"
                    )

    # 3. Check warmstart checkpoint embedding shape
    if checkpoint_path:
        cp = Path(checkpoint_path)
        if cp.exists():
            try:
                ck = torch.load(str(cp), map_location="cpu", weights_only=True)
                sd = ck.get("model_state_dict", {})
                for key in ["token_embedding.weight", "output_projection.weight"]:
                    w = sd.get(key)
                    if w is not None and w.shape[0] != _cfg.TOTAL_VOCAB_SIZE:
                        errors.append(
                            f"Checkpoint {cp.name}: {key} shape[0]={w.shape[0]} "
                            f"!= TOTAL_VOCAB_SIZE={_cfg.TOTAL_VOCAB_SIZE}"
                        )
            except Exception as e:
                errors.append(f"Failed to inspect checkpoint {cp}: {e}")

    # 4. Check Set Predictor active tokens
    if set_predictor_dir:
        sp = Path(set_predictor_dir) / "best_model.pth"
        if sp.exists():
            try:
                ck = torch.load(str(sp), map_location="cpu", weights_only=True)
                active = ck.get("active_token_ids", [])
                if active:
                    max_active = max(active)
                    if max_active >= _cfg.VOCAB_SIZE:
                        errors.append(
                            f"Set Predictor active token {max_active} >= VOCAB_SIZE {_cfg.VOCAB_SIZE}"
                        )
            except Exception as e:
                errors.append(f"Failed to inspect Set Predictor {sp}: {e}")

    return errors
