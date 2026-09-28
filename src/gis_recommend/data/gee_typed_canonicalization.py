"""Ordinal-aligned typed canonicalization for fidelity-passed GEE workflows."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
from typing import Any, Mapping

from gis_recommend.data.gee_operator_canonicalization import (
    MappingEntry,
    canonicalize_operator_sequence,
    matches_skip_authority,
)
from gis_recommend.data.gee_operator_policy import is_filter_predicate_constructor
from gis_recommend.data.gee_source_evidence import GeeSourceEvidence


_PENDING_ADMISSION = "not_granted_task_text_and_final_dedup_pending"
_OVERRIDE_SCHEMA = "gis_recommend.gee_typed_l3_override_authority.v1"
_SIGNATURE_MISMATCH_POLICIES = frozenset({"fail_closed", "retain_base"})


@dataclass(frozen=True)
class TypedL3Override:
    canonical_operator: str
    receiver_type: str
    primary_l3: str
    mapping_confidence: float
    min_arguments: int
    max_arguments: int
    signature_mismatch_policy: str
    rationale: str


@dataclass(frozen=True)
class TypedL3OverrideAuthority:
    version: str
    base_mapping_sha256: str
    overrides: dict[str, TypedL3Override]


def _sha256(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load_typed_l3_overrides(
    authority_path: Path,
    base_mapping_path: Path,
) -> TypedL3OverrideAuthority:
    """Load a hash-bound, token-preserving typed L3 override authority."""

    authority_path = Path(authority_path)
    base_mapping_path = Path(base_mapping_path)
    payload = json.loads(authority_path.read_text(encoding="utf-8"))
    base_payload = json.loads(base_mapping_path.read_text(encoding="utf-8"))
    if payload.get("schema") != _OVERRIDE_SCHEMA:
        raise ValueError(f"{authority_path} has invalid override schema")
    version = str(payload.get("version") or "").strip()
    if not version:
        raise ValueError(f"{authority_path} has no override version")
    expected_base_sha = str(payload.get("base_mapping_sha256") or "").strip().lower()
    actual_base_sha = _sha256(base_mapping_path)
    if expected_base_sha != actual_base_sha:
        raise ValueError(
            f"{authority_path} base_mapping_sha256 does not match {base_mapping_path}"
        )

    catalog = {
        str(operator).strip().lower()
        for operator in (base_payload.get("gee_op") or {})
        if str(operator).strip()
    }
    stable_l3 = {
        str(code).strip()
        for code in (base_payload.get("l3") or {})
        if str(code).strip()
    }
    rows = payload.get("overrides")
    if not isinstance(rows, list) or not rows:
        raise ValueError(f"{authority_path} contains no overrides")

    overrides: dict[str, TypedL3Override] = {}
    for index, row in enumerate(rows, start=1):
        if not isinstance(row, dict):
            raise ValueError(f"override row {index} must be an object")
        operator = str(row.get("canonical_operator") or "").strip().lower()
        receiver_type = str(row.get("receiver_type") or "").strip().lower()
        primary_l3 = str(row.get("primary_l3") or "").strip()
        confidence = row.get("mapping_confidence")
        min_arguments = row.get("min_arguments")
        max_arguments = row.get("max_arguments")
        mismatch_policy = str(row.get("signature_mismatch_policy") or "").strip()
        rationale = str(row.get("rationale") or "").strip()
        if not operator or operator in overrides:
            raise ValueError(f"override row {index} has invalid or duplicate operator")
        if operator not in catalog:
            raise ValueError(f"override operator is absent from base catalog: {operator}")
        if not receiver_type.startswith("ee.") or not operator.startswith(receiver_type + "."):
            raise ValueError(f"override row {index} has incompatible receiver_type")
        if primary_l3 not in stable_l3:
            raise ValueError(f"override target is absent from stable L3 vocabulary: {primary_l3}")
        if not isinstance(confidence, (int, float)) or not 0.0 <= float(confidence) <= 1.0:
            raise ValueError(f"override row {index} has invalid mapping_confidence")
        if (
            type(min_arguments) is not int
            or type(max_arguments) is not int
            or min_arguments < 0
            or min_arguments > max_arguments
        ):
            raise ValueError(f"override row {index} has invalid argument bounds")
        if mismatch_policy not in _SIGNATURE_MISMATCH_POLICIES:
            raise ValueError(f"override row {index} has invalid signature mismatch policy")
        if not rationale:
            raise ValueError(f"override row {index} has no rationale")
        overrides[operator] = TypedL3Override(
            canonical_operator=operator,
            receiver_type=receiver_type,
            primary_l3=primary_l3,
            mapping_confidence=float(confidence),
            min_arguments=min_arguments,
            max_arguments=max_arguments,
            signature_mismatch_policy=mismatch_policy,
            rationale=rationale,
        )
    return TypedL3OverrideAuthority(
        version=version,
        base_mapping_sha256=actual_base_sha,
        overrides=overrides,
    )


@dataclass(frozen=True)
class TypedCallDecision:
    ordinal: int
    raw_callee: str
    resolution: str
    receiver_type: str | None
    receiver_is_proven_ee: bool
    source_location: dict[str, int] | None
    call_status: str
    canonical_operator: str | None
    l3_code: str | None
    mapping_confidence: float | None
    has_ambiguity: bool


@dataclass(frozen=True)
class WorkflowTypedDecision:
    source_sha256: str
    source_path: str
    workflow_id: str
    calibration_stratum: str
    mapping_status: str
    fail_closed_reasons: tuple[str, ...]
    call_decisions: tuple[TypedCallDecision, ...]
    canonical_operator_sequence: tuple[str, ...]
    l3_sequence: tuple[str, ...]
    mapping_confidences: tuple[float | None, ...]
    training_admission: str
    training_rows_emitted: int


def _base_fields(candidate: dict[str, Any]) -> dict[str, str]:
    return {
        "source_sha256": str(candidate.get("source_sha256") or ""),
        "source_path": str(candidate.get("source_path") or ""),
        "workflow_id": str(candidate.get("workflow_id") or ""),
        "calibration_stratum": str(candidate.get("calibration_stratum") or ""),
    }


def _decision(
    candidate: dict[str, Any],
    *,
    status: str,
    reasons: list[str] | tuple[str, ...],
    calls: list[TypedCallDecision] | tuple[TypedCallDecision, ...] = (),
) -> WorkflowTypedDecision:
    mapped = [call for call in calls if call.call_status in {"mapped", "ambiguous_mapping"}]
    return WorkflowTypedDecision(
        **_base_fields(candidate),
        mapping_status=status,
        fail_closed_reasons=tuple(dict.fromkeys(reasons)),
        call_decisions=tuple(calls),
        canonical_operator_sequence=tuple(
            call.canonical_operator for call in mapped if call.canonical_operator is not None
        ),
        l3_sequence=tuple(call.l3_code for call in mapped if call.l3_code is not None),
        mapping_confidences=tuple(call.mapping_confidence for call in mapped),
        training_admission=_PENDING_ADMISSION,
        training_rows_emitted=0,
    )


def _ordinal_contract_reasons(candidate: dict[str, Any]) -> list[str]:
    ordinals = candidate.get("normalized_core_call_ordinals")
    chain = candidate.get("normalized_core_chain")
    reasons: list[str] = []
    if not isinstance(ordinals, list) or not isinstance(chain, list):
        return ["normalized_ordinal_chain_schema_mismatch"]
    if len(ordinals) != len(chain):
        reasons.append("normalized_ordinal_chain_length_mismatch")
    if any(type(value) is not int for value in ordinals):
        reasons.append("invalid_normalized_core_call_ordinal")
        return reasons
    if any(value < 0 for value in ordinals):
        reasons.append("negative_normalized_core_call_ordinal")
    if len(ordinals) != len(set(ordinals)):
        reasons.append("duplicate_normalized_core_call_ordinal")
    if any(left >= right for left, right in zip(ordinals, ordinals[1:])):
        reasons.append("non_increasing_normalized_core_call_ordinals")
    if any(not isinstance(value, str) or not value for value in chain):
        reasons.append("invalid_normalized_core_chain_value")
    return reasons


def _status_for_reasons(reasons: list[str], mapped_count: int) -> str:
    prefixes = tuple(reasons)
    if any(reason.startswith("l3_override_signature_mismatch") for reason in prefixes):
        return "l3_override_signature_mismatch"
    if any(
        reason.startswith(
            (
                "source_",
                "extractor_version_",
                "normalized_",
                "invalid_normalized_",
                "negative_normalized_",
                "duplicate_normalized_",
                "non_increasing_",
                "duplicate_evidence_ordinal",
                "missing_call_ordinal",
                "call_not_core",
                "raw_callee_mismatch",
                "canonical_operator_not_in_catalog",
                "mapping_metadata_missing",
            )
        )
        for reason in prefixes
    ):
        return "evidence_mismatch"
    if any(reason.startswith("ambiguous_mapping") for reason in prefixes):
        return "ambiguous_mapping"
    if any(reason.startswith("support_classified_retained_call") for reason in prefixes):
        return "support_classified_retained_call"
    if any(reason.startswith("canonical_l3_gap") for reason in prefixes):
        return "canonical_l3_gap"
    if any(reason.startswith("unmapped_raw_call") for reason in prefixes):
        return "unmapped_raw_call"
    if mapped_count == 0:
        return "empty_canonical_chain"
    return "mapping_complete"


def canonicalize_workflow_calls(
    candidate: dict[str, Any],
    evidence: GeeSourceEvidence,
    mapping: dict[str, MappingEntry],
    operator_catalog: frozenset[str],
    *,
    skip_operators: frozenset[str] = frozenset(),
    l3_overrides: Mapping[str, TypedL3Override] | None = None,
    call_argument_counts: Mapping[int, int] | None = None,
) -> WorkflowTypedDecision:
    """Join normalized DAG calls to typed evidence and map every retained call."""

    reasons = _ordinal_contract_reasons(candidate)
    if candidate.get("fidelity_status") != "passed":
        reasons.append("source_candidate_not_fidelity_passed")
    if candidate.get("fail_closed_reasons") not in ([], ()):
        reasons.append("source_candidate_has_fail_closed_reasons")
    if evidence.source_sha256 != candidate.get("source_sha256"):
        reasons.append("source_sha256_mismatch")
    if evidence.source_path != candidate.get("source_path"):
        reasons.append("source_path_mismatch")
    if evidence.extractor_version != candidate.get("extractor_version"):
        reasons.append("extractor_version_mismatch")
    if reasons:
        return _decision(candidate, status="evidence_mismatch", reasons=reasons)

    calls_by_ordinal: dict[int, Any] = {}
    duplicate_ordinals: set[int] = set()
    for call in evidence.ordered_calls:
        if call.ordinal in calls_by_ordinal:
            duplicate_ordinals.add(call.ordinal)
        calls_by_ordinal[call.ordinal] = call
    if duplicate_ordinals:
        return _decision(
            candidate,
            status="evidence_mismatch",
            reasons=[f"duplicate_evidence_ordinal:{value}" for value in sorted(duplicate_ordinals)],
        )

    ordinals = candidate["normalized_core_call_ordinals"]
    raw_chain = candidate["normalized_core_chain"]
    aligned_calls: list[Any] = []
    for ordinal, expected_raw in zip(ordinals, raw_chain, strict=True):
        call = calls_by_ordinal.get(ordinal)
        if call is None:
            reasons.append(f"missing_call_ordinal:{ordinal}")
            continue
        if call.classification != "core":
            reasons.append(f"call_not_core:{ordinal}:{call.classification}")
        if call.raw_callee != expected_raw:
            reasons.append(f"raw_callee_mismatch:{ordinal}")
        aligned_calls.append(call)
    if reasons:
        return _decision(candidate, status="evidence_mismatch", reasons=reasons)

    call_decisions: list[TypedCallDecision] = []
    normalized_overrides = {
        str(operator).strip().lower(): override
        for operator, override in (l3_overrides or {}).items()
    }
    argument_counts = call_argument_counts or {}
    for call in aligned_calls:
        raw_callee = str(call.raw_callee)
        proven_ee = call.resolution in {"ee_namespace", "receiver_ee_binding"} or raw_callee.startswith(
            "ee."
        )
        if is_filter_predicate_constructor(raw_callee):
            call_decisions.append(
                TypedCallDecision(
                    ordinal=call.ordinal,
                    raw_callee=raw_callee,
                    resolution=call.resolution,
                    receiver_type=call.receiver_type,
                    receiver_is_proven_ee=proven_ee,
                    source_location=call.source_location,
                    call_status="skipped_support",
                    canonical_operator=None,
                    l3_code=None,
                    mapping_confidence=None,
                    has_ambiguity=False,
                )
            )
            continue
        mapping_callee = raw_callee
        if (
            "filter_predicate:date" in call.flags
            and call.receiver_type in {"ee.imagecollection", "ee.featurecollection"}
        ):
            mapping_callee = f"{call.receiver_type}.filterdate"
        authority_skipped = matches_skip_authority(
            mapping_callee,
            skip_operators,
            receiver_type=call.receiver_type,
        )
        result = canonicalize_operator_sequence(
            [mapping_callee],
            mapping,
            proven_ee_receivers=[proven_ee],
            receiver_types=[call.receiver_type],
            operator_catalog=operator_catalog,
            skip_operators=skip_operators,
        )
        status = "unmapped_raw_call"
        canonical_operator: str | None = None
        l3_code: str | None = None
        confidence: float | None = None
        ambiguity = False

        if result.canonical_operator_sequence:
            canonical_operator = result.canonical_operator_sequence[0]
            l3_code = result.l3_sequence[0]
            entry = mapping.get(canonical_operator.lower())
            if entry is None:
                reasons.append(f"mapping_metadata_missing:{canonical_operator}")
                status = "evidence_mismatch"
            elif canonical_operator.lower() not in operator_catalog:
                reasons.append(f"canonical_operator_not_in_catalog:{canonical_operator}")
                status = "evidence_mismatch"
                confidence = entry.mapping_confidence
                ambiguity = entry.has_ambiguity
            else:
                confidence = entry.mapping_confidence
                ambiguity = entry.has_ambiguity
                if ambiguity:
                    reasons.append(f"ambiguous_mapping:{canonical_operator}")
                    status = "ambiguous_mapping"
                else:
                    status = "mapped"
                    override = normalized_overrides.get(canonical_operator.lower())
                    if override is not None:
                        argument_count = argument_counts.get(call.ordinal)
                        signature_is_proven = (
                            str(call.receiver_type or "").strip().lower()
                            == override.receiver_type
                            and isinstance(argument_count, int)
                        )
                        signature_matches = (
                            signature_is_proven
                            and isinstance(argument_count, int)
                            and override.min_arguments
                            <= argument_count
                            <= override.max_arguments
                        )
                        if not signature_is_proven:
                            reasons.append(
                                "l3_override_signature_mismatch:"
                                f"{canonical_operator}:arguments=unknown"
                            )
                            status = "l3_override_signature_mismatch"
                            l3_code = None
                            confidence = None
                        elif signature_matches:
                            l3_code = override.primary_l3
                            confidence = override.mapping_confidence
                        elif override.signature_mismatch_policy == "fail_closed":
                            reasons.append(
                                "l3_override_signature_mismatch:"
                                f"{canonical_operator}:arguments={argument_count}"
                            )
                            status = "l3_override_signature_mismatch"
                            l3_code = None
                            confidence = None
        elif result.skipped_raw_operators:
            if authority_skipped:
                status = "skipped_support"
            else:
                reasons.append(f"support_classified_retained_call:{raw_callee}")
                status = "support_classified_retained_call"
        elif result.canonical_unmapped_l3_operators:
            canonical_operator = result.canonical_unmapped_l3_operators[0]
            reasons.append(f"canonical_l3_gap:{canonical_operator}")
            status = "canonical_l3_gap"
        else:
            reasons.append(f"unmapped_raw_call:{raw_callee}")

        call_decisions.append(
            TypedCallDecision(
                ordinal=call.ordinal,
                raw_callee=raw_callee,
                resolution=call.resolution,
                receiver_type=call.receiver_type,
                receiver_is_proven_ee=proven_ee,
                source_location=call.source_location,
                call_status=status,
                canonical_operator=canonical_operator,
                l3_code=l3_code,
                mapping_confidence=confidence,
                has_ambiguity=ambiguity,
            )
        )

    mapped_count = sum(call.call_status == "mapped" for call in call_decisions)
    status = _status_for_reasons(reasons, mapped_count)
    return _decision(candidate, status=status, reasons=reasons, calls=call_decisions)
