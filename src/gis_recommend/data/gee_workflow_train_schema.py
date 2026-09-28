"""Fail-closed train-only schema for complete output-relevant GEE workflows."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
import re
from typing import Any


SCHEMA = "gis_recommend.gee_workflow_train_row.v1"
SOURCE_PLATFORM = "GEE"
TARGET_PLATFORM = "L3"
TRAINING_SCOPE = "complete_output_workflow"
ADJUDICATION_DECISION = "pass"
TRAINING_ADMISSION = "granted_train_only_gee_complete_workflow_v1"
TRAIN_ONLY_SPLIT = "train_only_gee_complete_workflow_v1"
MAX_SAMPLE_WEIGHT = 0.5

_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_L3_CODE_RE = re.compile(r"^L3_[A-Z0-9][A-Z0-9_]*$")


@dataclass(frozen=True)
class GeeWorkflowTrainRow:
    """Source-backed semantic row for one complete output workflow."""

    sample_id: str
    source_sha256: str
    source_path: str
    workflow_id: str
    exact_dag_fingerprint: str
    task_name: str
    task_description: str
    operator_sequence: tuple[str, ...]
    l3_sequence: tuple[str, ...]
    fact_bundle_sha256: str
    task_text_candidate_sha256: str
    adjudication_row_sha256: str
    known_omissions: tuple[str, ...] = ()
    sample_weight: float = MAX_SAMPLE_WEIGHT
    source_platform: str = SOURCE_PLATFORM
    target_platform: str = TARGET_PLATFORM
    training_scope: str = TRAINING_SCOPE
    adjudication_decision: str = ADJUDICATION_DECISION
    training_admission: str = TRAINING_ADMISSION
    split: str = TRAIN_ONLY_SPLIT
    validation_eligible: bool = False
    test_eligible: bool = False
    production_merge: str = "not_granted"

    def to_dict(self) -> dict[str, Any]:
        payload = {
            "schema": SCHEMA,
            "sample_id": self.sample_id,
            "source_platform": self.source_platform,
            "target_platform": self.target_platform,
            "training_scope": self.training_scope,
            "source_sha256": self.source_sha256,
            "source_path": self.source_path,
            "workflow_id": self.workflow_id,
            "exact_dag_fingerprint": self.exact_dag_fingerprint,
            "task_name": self.task_name,
            "task_description": self.task_description,
            "operator_sequence": list(self.operator_sequence),
            "l3_sequence": list(self.l3_sequence),
            "fact_bundle_sha256": self.fact_bundle_sha256,
            "task_text_candidate_sha256": self.task_text_candidate_sha256,
            "adjudication_row_sha256": self.adjudication_row_sha256,
            "adjudication_decision": self.adjudication_decision,
            "training_admission": self.training_admission,
            "split": self.split,
            "validation_eligible": self.validation_eligible,
            "test_eligible": self.test_eligible,
            "production_merge": self.production_merge,
            "sample_weight": self.sample_weight,
            "known_omissions": list(self.known_omissions),
        }
        validate_workflow_train_row(payload)
        return payload


def _payload(row: Mapping[str, Any] | GeeWorkflowTrainRow) -> dict[str, Any]:
    if isinstance(row, GeeWorkflowTrainRow):
        return row.to_dict()
    if isinstance(row, Mapping):
        return dict(row)
    raise TypeError("row must be a mapping or GeeWorkflowTrainRow")


def _non_empty_str(payload: Mapping[str, Any], field: str) -> str:
    value = payload.get(field)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be a non-empty string")
    return value.strip()


def _sha256(payload: Mapping[str, Any], field: str) -> str:
    value = _non_empty_str(payload, field)
    if not _SHA256_RE.fullmatch(value):
        raise ValueError(f"{field} must be a lowercase 64-character SHA256")
    return value


def _sequence(payload: Mapping[str, Any], field: str) -> list[str]:
    value = payload.get(field)
    if not isinstance(value, (list, tuple)) or not value:
        raise ValueError(f"{field} must be a non-empty list")
    if any(not isinstance(item, str) or not item.strip() for item in value):
        raise ValueError(f"{field} must contain non-empty strings")
    return [str(item).strip() for item in value]


def validate_stable_94_mapping(mapping: Mapping[str, Any]) -> dict[str, int]:
    """Validate and normalize the frozen stable-94 L3-to-token mapping."""

    if not isinstance(mapping, Mapping) or len(mapping) != 94:
        actual = len(mapping) if isinstance(mapping, Mapping) else "non-mapping"
        raise ValueError(f"stable-94 mapping must contain exactly 94 L3 entries, got {actual}")
    normalized: dict[str, int] = {}
    for code, token_id in mapping.items():
        if not isinstance(code, str) or not _L3_CODE_RE.fullmatch(code):
            raise ValueError(f"stable-94 mapping key must be a valid L3 code: {code!r}")
        if isinstance(token_id, bool) or not isinstance(token_id, int):
            raise ValueError(f"stable-94 mapping values must be non-bool int values: {code}")
        normalized[code] = token_id
    token_ids = list(normalized.values())
    if len(set(token_ids)) != len(token_ids):
        raise ValueError("stable-94 mapping token IDs must be unique")
    if set(token_ids) != set(range(94)):
        raise ValueError("stable-94 mapping token IDs must be exactly 0..93")
    return normalized


def validate_workflow_train_row(
    row: Mapping[str, Any] | GeeWorkflowTrainRow,
) -> None:
    """Validate one complete-workflow semantic train-only row."""

    payload = _payload(row)
    if payload.get("schema") != SCHEMA:
        raise ValueError(f"schema must be {SCHEMA}")
    expected_fields = {
        "source_platform": SOURCE_PLATFORM,
        "target_platform": TARGET_PLATFORM,
        "training_scope": TRAINING_SCOPE,
        "adjudication_decision": ADJUDICATION_DECISION,
        "training_admission": TRAINING_ADMISSION,
        "split": TRAIN_ONLY_SPLIT,
        "production_merge": "not_granted",
    }
    for field, expected in expected_fields.items():
        if payload.get(field) != expected:
            raise ValueError(f"{field} must be {expected}")
    if payload.get("validation_eligible") is not False:
        raise ValueError("validation_eligible must be false")
    if payload.get("test_eligible") is not False:
        raise ValueError("test_eligible must be false")

    for field in (
        "sample_id",
        "source_path",
        "workflow_id",
        "task_name",
        "task_description",
    ):
        _non_empty_str(payload, field)
    _sha256(payload, "exact_dag_fingerprint")
    for field in (
        "source_sha256",
        "fact_bundle_sha256",
        "task_text_candidate_sha256",
        "adjudication_row_sha256",
    ):
        _sha256(payload, field)

    operators = _sequence(payload, "operator_sequence")
    l3_codes = _sequence(payload, "l3_sequence")
    if len(operators) != len(l3_codes):
        raise ValueError("operator_sequence and l3_sequence must have the same length")
    if any(not code.startswith("L3_") for code in l3_codes):
        raise ValueError("l3_sequence must contain content L3 codes only")

    weight = payload.get("sample_weight")
    if (
        isinstance(weight, bool)
        or not isinstance(weight, (int, float))
        or not 0 < float(weight) <= MAX_SAMPLE_WEIGHT
    ):
        raise ValueError(f"sample_weight must be in (0, {MAX_SAMPLE_WEIGHT}]")
    omissions = payload.get("known_omissions")
    if not isinstance(omissions, (list, tuple)):
        raise ValueError("known_omissions must be a list of strings")
    if any(not isinstance(item, str) or not item.strip() for item in omissions):
        raise ValueError("known_omissions must contain non-empty strings")
