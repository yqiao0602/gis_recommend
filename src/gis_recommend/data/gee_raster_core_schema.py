"""Train-only schema contract for GEE raster/L3 core-subworkflow rows.

This module is intentionally small and dependency-free. It defines the row
contract that P2 description rewriting and P3 extractor repair can reuse before
any final token-id export or model training gate.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
import re
from typing import Any


SCHEMA = "gis_recommend.gee_raster_core_train_row.v1"
SOURCE_PLATFORM = "GEE"
TARGET_PLATFORM = "L3"
TRAINING_SCOPE = "core_subworkflow"
MAX_SAMPLE_WEIGHT = 0.5

ADMISSION_TIERS = frozenset(
    {
        "gee_core_p0_accept",
        "gee_core_p2_rewrite",
        "gee_core_p3_extractor_repair",
        "gee_core_p3_taxonomy_repair",
        "gee_core_p4_reviewed",
    }
)
DESCRIPTION_POLICIES = frozenset(
    {
        "original_core_faithful",
        "rewritten_chain_faithful",
        "template_chain_faithful",
        "manual_chain_faithful",
    }
)
REVIEW_SPLITS = frozenset({"train", "val", "test", "train_only"})

_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


@dataclass(frozen=True)
class GeeRasterCoreTrainRow:
    """Canonical train-only GEE raster/L3 core-subworkflow row.

    `l3_sequence` contains content L3 codes only. It deliberately excludes
    `<START>`/`<END>` and token ids because those belong to the later export
    gate, not to the P1/P2/P3 semantic-row contract.
    """

    review_id: str
    script_id: str
    task_name: str
    task_description: str
    l3_sequence: tuple[str, ...]
    operator_sequence: tuple[str, ...]
    source_sha256: str
    source_path: str
    evidence_snippet: str
    admission_tier: str
    sample_weight: float = 0.5
    validation_eligible: bool = False
    test_eligible: bool = False
    description_policy: str = "original_core_faithful"
    known_omissions: tuple[str, ...] = ()
    review_split: str | None = None
    source_platform: str = SOURCE_PLATFORM
    target_platform: str = TARGET_PLATFORM
    training_scope: str = TRAINING_SCOPE

    def to_dict(self) -> dict[str, Any]:
        payload = {
            "schema": SCHEMA,
            "review_id": self.review_id,
            "script_id": self.script_id,
            "source_platform": self.source_platform,
            "target_platform": self.target_platform,
            "training_scope": self.training_scope,
            "task_name": self.task_name,
            "task_description": self.task_description,
            "l3_sequence": list(self.l3_sequence),
            "operator_sequence": list(self.operator_sequence),
            "source_sha256": self.source_sha256,
            "source_path": self.source_path,
            "evidence_snippet": self.evidence_snippet,
            "admission_tier": self.admission_tier,
            "sample_weight": self.sample_weight,
            "validation_eligible": self.validation_eligible,
            "test_eligible": self.test_eligible,
            "description_policy": self.description_policy,
            "known_omissions": list(self.known_omissions),
        }
        if self.review_split is not None:
            payload["review_split"] = self.review_split
        validate_core_train_row(payload)
        return payload


def _as_payload(row: Mapping[str, Any] | GeeRasterCoreTrainRow) -> dict[str, Any]:
    if isinstance(row, GeeRasterCoreTrainRow):
        return row.to_dict()
    if isinstance(row, Mapping):
        return dict(row)
    raise TypeError("row must be a mapping or GeeRasterCoreTrainRow")


def _require_non_empty_str(payload: Mapping[str, Any], field: str) -> str:
    value = payload.get(field)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be a non-empty string")
    return value.strip()


def _require_sequence(payload: Mapping[str, Any], field: str) -> list[str]:
    value = payload.get(field)
    if not isinstance(value, (list, tuple)) or not value:
        raise ValueError(f"{field} must be a non-empty list")
    if any(not isinstance(item, str) or not item.strip() for item in value):
        raise ValueError(f"{field} must contain non-empty strings")
    return [str(item).strip() for item in value]


def validate_core_train_row(row: Mapping[str, Any] | GeeRasterCoreTrainRow) -> None:
    """Validate one P1 GEE core-subworkflow train-only row.

    The validator fails closed: a row with validation/test eligibility, pending
    repair buckets, missing source evidence, or special-token L3 sequences is
    not a valid P1 training candidate.
    """

    payload = _as_payload(row)
    schema = payload.get("schema")
    if schema is not None and schema != SCHEMA:
        raise ValueError(f"schema must be {SCHEMA}")
    if payload.get("source_platform") != SOURCE_PLATFORM:
        raise ValueError(f"source_platform must be {SOURCE_PLATFORM}")
    if payload.get("target_platform") != TARGET_PLATFORM:
        raise ValueError(f"target_platform must be {TARGET_PLATFORM}")
    if payload.get("training_scope") != TRAINING_SCOPE:
        raise ValueError(f"training_scope must be {TRAINING_SCOPE}")
    if payload.get("validation_eligible") is not False:
        raise ValueError("validation_eligible must be false for GEE train-only rows")
    if payload.get("test_eligible") is not False:
        raise ValueError("test_eligible must be false for GEE train-only rows")

    for field in (
        "review_id",
        "script_id",
        "task_name",
        "task_description",
        "source_path",
        "evidence_snippet",
    ):
        _require_non_empty_str(payload, field)

    source_sha256 = _require_non_empty_str(payload, "source_sha256")
    if not _SHA256_RE.fullmatch(source_sha256):
        raise ValueError("source_sha256 must be a lowercase 64-character SHA256")

    l3_sequence = _require_sequence(payload, "l3_sequence")
    operator_sequence = _require_sequence(payload, "operator_sequence")
    if len(l3_sequence) != len(operator_sequence):
        raise ValueError("l3_sequence and operator_sequence must have the same length")
    if any(not code.startswith("L3_") for code in l3_sequence):
        raise ValueError("l3_sequence must contain content L3 codes only")

    admission_tier = _require_non_empty_str(payload, "admission_tier")
    if admission_tier not in ADMISSION_TIERS:
        raise ValueError(
            "admission_tier must be one of "
            f"{sorted(ADMISSION_TIERS)}; got {admission_tier!r}"
        )
    description_policy = _require_non_empty_str(payload, "description_policy")
    if description_policy not in DESCRIPTION_POLICIES:
        raise ValueError(
            "description_policy must be one of "
            f"{sorted(DESCRIPTION_POLICIES)}; got {description_policy!r}"
        )

    sample_weight = payload.get("sample_weight")
    if (
        isinstance(sample_weight, bool)
        or not isinstance(sample_weight, (int, float))
        or not 0 < float(sample_weight) <= MAX_SAMPLE_WEIGHT
    ):
        raise ValueError(
            f"sample_weight must be numeric in the interval (0, {MAX_SAMPLE_WEIGHT}]"
        )

    known_omissions = payload.get("known_omissions", [])
    if not isinstance(known_omissions, (list, tuple)):
        raise ValueError("known_omissions must be a list of strings")
    if any(not isinstance(item, str) or not item.strip() for item in known_omissions):
        raise ValueError("known_omissions must contain non-empty strings")

    review_split = payload.get("review_split")
    if review_split is not None and review_split not in REVIEW_SPLITS:
        raise ValueError(f"review_split must be one of {sorted(REVIEW_SPLITS)}")
