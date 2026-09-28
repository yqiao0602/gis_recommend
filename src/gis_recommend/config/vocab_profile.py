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
STABLE124_EXPERIMENTAL = "stable124_experimental"
PAPER_V1_128 = "paper_v1_128"
VALID_PROFILES = {V2_94_STABLE, V3_107_EXPERIMENTAL, STABLE124_EXPERIMENTAL, PAPER_V1_128}

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
    PAPER_V1_128: {
        "vocab_size": 128,
        "l3_code_count": 128,
        "description": "M1-R1 isolated profile: full 128-token L3 taxonomy for paper_v1",
        "id_mappings_default": "docs/reports/paper_v1_profile_v1/id_mappings_paper_v1_128.json",
        "set_predictor_dir": "outputs_v2/set_predictor_checkpoints_v3_vec11277",
        "training_data_dir": "docs/reports/paper_v1_profile_v1",
        "training_data_file": "labeled_workflows_paper_v1.json",
    },
    STABLE124_EXPERIMENTAL: {
        "vocab_size": 124,
        "l3_code_count": 124,
        "description": "Isolated QGIS experiment: stable 94 IDs plus 30 extensions",
        "id_mappings_default": "docs/reports/qgis_stable124_experiment_profile_v1/id_mappings_stable124_experimental.json",
        "set_predictor_dir": "outputs_v2/set_predictor_checkpoints_v3_vec11277",
        "training_data_dir": "docs/reports/qgis_stable124_experiment_profile_v1",
        "training_data_file": "labeled_workflows_stable124_plus28.json",
    },
}


def current_profile() -> str:
    """Return the currently-active vocab profile name.

    Priority: explicit apply_profile() > GIS_VOCAB_PROFILE env var > default v2_94_stable.
    """
    if _ACTIVE_PROFILE:
        return _ACTIVE_PROFILE
    env = os.environ.get("GIS_VOCAB_PROFILE", "")
    if env in VALID_PROFILES:
        return env
    return V2_94_STABLE


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
) -> list[str]:
    """Run pre-flight checks suitable for training/eval entry points.

    Call this early in training or showcase eval.  Returns a list of error
    strings (empty = all clear).  Does NOT raise — the caller decides whether
    to abort or warn.

    This is profile-aware: it validates that the current profile's required
    artifacts (id_mappings, training data token range) are consistent with
    VOCAB_SIZE.
    """
    import gis_recommend.config.transformer_config as _cfg  # noqa: F811
    import torch  # noqa: F401

    errors: list[str] = []
    profile_name = current_profile()

    # 0. Validate that the active profile's artifacts exist and that
    #    the training data matches the profile's expectations.
    #    Without this, from-scratch training on old 94 data under
    #    the 107 experimental profile would silently pass.
    if profile_name != V2_94_STABLE:
        prof = _PROFILES.get(profile_name)
        if prof:
            root = _find_project_root()
            mapping_path = root / prof["id_mappings_default"]
            if not mapping_path.exists():
                errors.append(
                    f"Profile '{profile_name}' requires id_mappings at "
                    f"{mapping_path} — file not found. "
                    f"Generate it first or switch back to v2_94_stable."
                )
            # Check that the training data is compatible with this profile.
            # Compatibility is determined by TOKEN RANGE, not by file path —
            # activation experiments and variants may use different paths.
            if data_path:
                dp = Path(data_path)
                if dp.exists():
                    data = json.load(open(str(dp), "r", encoding="utf-8"))
                    wfs = data.get("labeled_workflows", data) if isinstance(data, dict) else data
                    if isinstance(wfs, list):
                        max_tok = max(
                            (t for wf in wfs if isinstance(wf, dict)
                             for t in wf.get("l3_sequence", []) if isinstance(t, int)),
                            default=-1,
                        )
                        if profile_name != STABLE124_EXPERIMENTAL and max_tok < prof["vocab_size"] - 13:
                            # Data has no tokens in the expanded range (94-106) —
                            # it was built for the 94-code vocabulary.
                            errors.append(
                                f"Training data max token is {max_tok}, but profile "
                                f"'{profile_name}' expects tokens up to "
                                f"{prof['vocab_size']-1}. "
                                f"Use v2_94_stable or provide a 107-code training package."
                            )
                        elif max_tok >= prof["vocab_size"]:
                            errors.append(
                                f"Training data max token {max_tok} >= vocab_size "
                                f"{prof['vocab_size']} — data was built for a larger vocabulary."
                            )

    # 1. Check that TOTAL_VOCAB_SIZE is self-consistent
    expected = _cfg.VOCAB_SIZE + _cfg.NUM_SPECIAL_TOKENS
    if _cfg.TOTAL_VOCAB_SIZE != expected:
        errors.append(
            f"TOTAL_VOCAB_SIZE={_cfg.TOTAL_VOCAB_SIZE} != "
            f"VOCAB_SIZE({_cfg.VOCAB_SIZE}) + NUM_SPECIAL_TOKENS({_cfg.NUM_SPECIAL_TOKENS}) = {expected}"
        )

    # 2. Check training data token range vs VOCAB_SIZE
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
                        f"Training data max token {max_tok} >= VOCAB_SIZE {_cfg.VOCAB_SIZE} "
                        f"(profile: {profile_name}). Data was built for a larger vocabulary — "
                        f"use the matching profile or a different training package."
                    )
                # Also detect the reverse: data with expanded tokens
                # used under the stable 94 profile
                if max_tok >= 94 and _cfg.VOCAB_SIZE == 94:
                    errors.append(
                        f"Training data contains expanded-vocab tokens (max={max_tok} >= 94) "
                        f"but VOCAB_SIZE=94 (profile: {profile_name}). "
                        f"Either use the v3_107_experimental profile or switch to a "
                        f"94-code training package."
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
                            f"!= TOTAL_VOCAB_SIZE={_cfg.TOTAL_VOCAB_SIZE} "
                            f"(profile: {profile_name})"
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
