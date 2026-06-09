"""Mainline evaluation run contract.

This module keeps data/token/report semantics explicit for the Step8 + V4.6
mainline. It does not change model decoding or candidate selection by itself.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from gis_recommend.config.transformer_config import (
    ID_MAPPINGS_PATH,
    OUTPUT_DIR,
    PROJECT_ROOT,
    SET_PREDICTOR_CHECKPOINT_DIR,
    SPECIAL_TOKENS,
    V4_6_TRANSFORMER_CHECKPOINT_DIR,
    V4_LABELED_WORKFLOWS_PATH,
    V4_TASK_TYPE_VOCAB_PATH,
    VOCAB_SIZE,
)


def _internal_special_tokens(vocab_size: int, data_special_tokens: dict[str, int]) -> dict[str, int]:
    return {
        name: vocab_size + abs(value) - 1
        for name, value in data_special_tokens.items()
    }


def _version_family(path: Path) -> str:
    parts = {part.lower() for part in path.parts}
    if "outputs_v2" in parts:
        return "v2"
    if "outputs" in parts:
        return "legacy"
    return "custom"


@dataclass(frozen=True)
class TokenProfile:
    name: str
    content_vocab_size: int
    data_special_tokens: dict[str, int]
    model_special_tokens: dict[str, int]
    content_token_min: int = 0

    @property
    def content_token_max(self) -> int:
        return self.content_vocab_size - 1

    @property
    def special_token_ids(self) -> set[int]:
        return set(self.data_special_tokens.values()) | set(self.model_special_tokens.values())

    def strip_special(self, tokens: list[int]) -> list[int]:
        special = self.special_token_ids
        return [token for token in tokens if token not in special]

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "content_vocab_size": self.content_vocab_size,
            "content_token_range": [self.content_token_min, self.content_token_max],
            "data_special_tokens": dict(self.data_special_tokens),
            "model_special_tokens": dict(self.model_special_tokens),
            "special_token_ids": sorted(self.special_token_ids),
        }


@dataclass(frozen=True)
class DataAuthorityManifest:
    name: str
    version_family: str
    workflow_path: Path
    split_path: Path
    task_vocab_path: Path
    id_mappings_path: Path
    l3_vocab_path: Path
    qgis_io_types_path: Path
    qgis_io_types_status: str
    transformer_checkpoint: Path
    set_predictor_checkpoint: Path
    io_metadata_profile: dict

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "version_family": self.version_family,
            "workflow_path": str(self.workflow_path),
            "split_path": str(self.split_path),
            "task_vocab_path": str(self.task_vocab_path),
            "id_mappings_path": str(self.id_mappings_path),
            "l3_vocab_path": str(self.l3_vocab_path),
            "qgis_io_types_path": str(self.qgis_io_types_path),
            "qgis_io_types_status": self.qgis_io_types_status,
            "transformer_checkpoint": str(self.transformer_checkpoint),
            "set_predictor_checkpoint": str(self.set_predictor_checkpoint),
            "io_metadata_profile": dict(self.io_metadata_profile),
        }


@dataclass(frozen=True)
class MainlineRunContract:
    system_lineage: str
    data_profile: str
    model_profile: str
    metric_scope: str
    mainline_eligible: bool
    candidate_pool_enabled: bool
    decision_core_mode: str
    retrieval_mode: str
    l2_authority: str
    token_profile: TokenProfile
    data_authority: DataAuthorityManifest
    repair_capability: dict
    selection_policy: dict
    l2_role: dict

    def to_report_dict(self) -> dict:
        return {
            "system_lineage": self.system_lineage,
            "data_profile": self.data_profile,
            "model_profile": self.model_profile,
            "metric_scope": self.metric_scope,
            "mainline_eligible": self.mainline_eligible,
            "candidate_pool_enabled": self.candidate_pool_enabled,
            "decision_core_mode": self.decision_core_mode,
            "retrieval_mode": self.retrieval_mode,
            "l2_authority": self.l2_authority,
            "token_profile": self.token_profile.to_dict(),
            "data_authority": self.data_authority.to_dict(),
            "repair_capability": dict(self.repair_capability),
            "selection_policy": dict(self.selection_policy),
            "l2_role": dict(self.l2_role),
        }


def get_mainline_token_profile() -> TokenProfile:
    data_special = dict(SPECIAL_TOKENS)
    return TokenProfile(
        name=f"v2_{VOCAB_SIZE}_l3",
        content_vocab_size=VOCAB_SIZE,
        data_special_tokens=data_special,
        model_special_tokens=_internal_special_tokens(VOCAB_SIZE, data_special),
    )


def legacy_350_l3_token_profile() -> TokenProfile:
    legacy_special = {
        "<PAD>": 350,
        "<UNK>": 351,
        "<START>": 352,
        "<END>": 353,
    }
    return TokenProfile(
        name="legacy_350_l3",
        content_vocab_size=350,
        data_special_tokens=legacy_special,
        model_special_tokens={},
    )


def _resolve_io_types_path(
    io_types_path: Optional[str | Path],
    allow_legacy_io_types: bool,
) -> Path:
    if io_types_path is not None:
        return Path(io_types_path).expanduser().resolve()

    v2_path = OUTPUT_DIR / "qgis_operator_io_types.json"
    if v2_path.exists() or not allow_legacy_io_types:
        return v2_path

    return PROJECT_ROOT / "outputs" / "qgis_operator_io_types.json"


def _io_metadata_profile(path: Path, allow_legacy_io_types: bool) -> dict:
    version_family = _version_family(path)
    exists = path.exists()
    if not exists:
        fallback_status = "missing"
    elif version_family == "legacy":
        fallback_status = "explicit_legacy" if allow_legacy_io_types else "legacy_not_allowed"
    else:
        fallback_status = "available"
    return {
        "version_family": version_family,
        "path": str(path),
        "exists": exists,
        "fallback_status": fallback_status,
    }


def build_mainline_run_contract(
    *,
    checkpoint_path: Optional[str | Path] = None,
    sp_checkpoint: Optional[str | Path] = None,
    io_types_path: Optional[str | Path] = None,
    allow_legacy_io_types: bool = False,
    candidate_pool_enabled: bool = False,
    decision_core_mode: str = "off",
    retrieval_mode: str = "off",
    l2_authority: str = "off",
) -> MainlineRunContract:
    token_profile = get_mainline_token_profile()
    _requested_checkpoint = checkpoint_path
    transformer_checkpoint = (
        Path(checkpoint_path).expanduser().resolve()
        if checkpoint_path
        else V4_6_TRANSFORMER_CHECKPOINT_DIR / "best_model.pth"
    )
    set_predictor_checkpoint = (
        Path(sp_checkpoint).expanduser().resolve()
        if sp_checkpoint
        else SET_PREDICTOR_CHECKPOINT_DIR / "best_model.pth"
    )
    qgis_io_types_path = _resolve_io_types_path(io_types_path, allow_legacy_io_types)
    io_profile = _io_metadata_profile(qgis_io_types_path, allow_legacy_io_types)
    mainline_eligible = (
        io_profile["version_family"] != "legacy"
        and io_profile["fallback_status"] != "legacy_not_allowed"
    )

    data_authority = DataAuthorityManifest(
        name="step8_v4_6_mainline",
        version_family="v2",
        workflow_path=V4_LABELED_WORKFLOWS_PATH,
        split_path=OUTPUT_DIR / "dataset_splits_v4.json",
        task_vocab_path=V4_TASK_TYPE_VOCAB_PATH,
        id_mappings_path=ID_MAPPINGS_PATH,
        l3_vocab_path=OUTPUT_DIR / "l3_vocab_v2.json",
        qgis_io_types_path=qgis_io_types_path,
        qgis_io_types_status=io_profile["fallback_status"],
        transformer_checkpoint=transformer_checkpoint,
        set_predictor_checkpoint=set_predictor_checkpoint,
        io_metadata_profile=io_profile,
    )

    return MainlineRunContract(
        system_lineage="mainline",
        data_profile="step8_v2",
        model_profile="v4_6_l3",
        metric_scope="l3_sequence_metrics_with_v2_token_contract",
        mainline_eligible=mainline_eligible,
        candidate_pool_enabled=candidate_pool_enabled,
        decision_core_mode=decision_core_mode,
        retrieval_mode=retrieval_mode,
        l2_authority=l2_authority,
        token_profile=token_profile,
        data_authority=data_authority,
        repair_capability={
            "current_level": "diagnostic_only",
            "candidate_suggestion": True,
            "runtime_mutation": False,
            "adoption_policy": "never_apply_in_step8_v4_6_mainline",
        },
        selection_policy={
            "primary_selection": "v4_6_latest_checkpoint",
            "optional_reranker": "structured_or_two_stage_when_enabled",
            "qgis_evaluation": "posthoc_diagnostic",
            "execution_awareness": "diagnostic_features_not_hard_authority",
            "workflow_selection_available": "pass --checkpoint <path>/best_gen_composite_model.pth for workflow-level selection",
            "checkpoint_override": bool(_requested_checkpoint),
        },
        l2_role={
            "runtime_role": "interpretation_layer",
            "affects_decoding": False,
            "affects_selection": False,
        },
    )
