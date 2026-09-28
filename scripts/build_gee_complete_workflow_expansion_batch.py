#!/usr/bin/env python3
"""Build a hash-bound, proposal-only census for GEE workflow expansion."""

from __future__ import annotations

import argparse
from collections import Counter
from collections.abc import Mapping
import csv
from dataclasses import dataclass
import hashlib
import io
import json
import os
from pathlib import Path
import re
import shutil
import tempfile
from types import MappingProxyType
from typing import Any

from scripts.export_gee_complete_workflow_training_package import (
    V4_MAX_SEQUENCE_LENGTH,
    _identity,
    _index,
    _load_jsonl,
    _normalized_text,
    _record_sha256,
    validate_source_backed_candidate,
    validate_stable_94_mapping,
)


EXPECTED_COUNT_FIELDS = frozenset(
    {
        "canonical_candidates",
        "reviewed_identities",
        "remaining",
        "excluded_reviewed_source_overlap",
        "proposal_eligible",
        "excluded_existing_or_batch_duplicate",
        "deferred_length",
        "fail_closed_semantic_gate",
    }
)
EXPANSION_BATCH_PROFILE_SCHEMA = (
    "gis_recommend.gee_workflow_expansion_batch_profile.v1"
)
EXPANSION_BATCH_PROFILE_FIELDS = frozenset(
    {
        "schema",
        "name",
        "authority_sha256",
        "expected_counts",
        "audit",
        "training_admission",
        "validation_eligible",
        "test_eligible",
        "production_merge",
    }
)
AUTHORITY_SHA256_FIELDS = frozenset(
    {
        "existing_semantic_rows",
        "fact_bundles",
        "mapping",
        "reviewed_packet",
        "task_text_candidates",
    }
)
AUDIT_PROFILE_FIELDS = frozenset(
    {"name", "sample_size", "expected_source_support", "quotas"}
)
TRAINING_ADMISSION = "not_granted_pending_sampling_audit"
PRODUCTION_MERGE = "not_granted"
RISK_STRATA = (
    "external_dynamic",
    "long_or_repeated",
    "multi_dataset_private",
    "no_temporal_operation",
    "other",
    "spatial_omission",
)
RISK_REPRESENTATIVE_PRIORITY = (
    "spatial_omission",
    "long_or_repeated",
    "multi_dataset_private",
    "no_temporal_operation",
    "external_dynamic",
    "other",
)
HUMAN_AUDIT_FIELDS = (
    "human_dataset_fidelity",
    "human_temporal_fidelity",
    "human_spatial_fidelity",
    "human_transformation_fidelity",
    "human_output_fidelity",
    "human_task_text_fidelity",
    "human_critical_failure",
    "human_decision",
    "human_notes",
)
MAX_SOURCE_SNIPPET_LINES = 80


@dataclass(frozen=True)
class FrozenExpansionProfile:
    """Hash-bound authorities and expected census counts."""

    name: str
    fact_bundles_sha256: str
    task_text_candidates_sha256: str
    reviewed_packet_sha256: str
    existing_semantic_rows_sha256: str
    mapping_sha256: str
    expected_counts: Mapping[str, int]

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "expected_counts", MappingProxyType(dict(self.expected_counts))
        )


PRODUCTION_EXPANSION_PROFILE = FrozenExpansionProfile(
    name="gee_complete_workflow_expansion_census_v1",
    fact_bundles_sha256=(
        "feb652c2d5ea0988a5812a5e84a88626b41b8e78a9dada555271d45b9e62e8b6"
    ),
    task_text_candidates_sha256=(
        "e804b6fbcbe333c5b365006d1e79fd811776c2d2fa099288c6a194cfadedb846"
    ),
    reviewed_packet_sha256=(
        "c33b1528f98b4ed4a0a2e9a1d2dd021d6eb0f61295ea2ce38a1c02101b6a023f"
    ),
    existing_semantic_rows_sha256=(
        "5c2677f81d69f7cbeae155556ebd1bc200b1b96b7e182983f55c0d3e08952c81"
    ),
    mapping_sha256=(
        "005699dfd438e966cda28db8891795a07b9867856951de022cd8704c6e6a4558"
    ),
    expected_counts={
        "canonical_candidates": 176,
        "reviewed_identities": 50,
        "remaining": 126,
        "excluded_reviewed_source_overlap": 43,
        "proposal_eligible": 83,
        "excluded_existing_or_batch_duplicate": 0,
        "deferred_length": 0,
        "fail_closed_semantic_gate": 0,
    },
)


@dataclass(frozen=True)
class ExpansionCensusResult:
    remaining_ledger: list[dict[str, Any]]
    proposal_rows: list[dict[str, Any]]
    source_overlap_sidecar: list[dict[str, Any]]
    fail_closed_sidecar: list[dict[str, Any]]
    duplicate_sidecar: list[dict[str, Any]]
    length_sidecar: list[dict[str, Any]]
    summary: dict[str, Any]


@dataclass(frozen=True)
class FrozenAuditSamplingProfile:
    """Fixed source support and quotas for a source-disjoint audit."""

    name: str
    sample_size: int
    expected_source_support: Mapping[str, int]
    quotas: Mapping[str, int]

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "expected_source_support",
            MappingProxyType(dict(self.expected_source_support)),
        )
        object.__setattr__(self, "quotas", MappingProxyType(dict(self.quotas)))


PRODUCTION_AUDIT_SAMPLING_PROFILE = FrozenAuditSamplingProfile(
    name="gee_complete_workflow_expansion_audit_30_v1",
    sample_size=30,
    expected_source_support={
        "external_dynamic": 22,
        "long_or_repeated": 5,
        "multi_dataset_private": 9,
        "no_temporal_operation": 7,
        "other": 1,
        "spatial_omission": 6,
    },
    quotas={
        "external_dynamic": 13,
        "long_or_repeated": 3,
        "multi_dataset_private": 5,
        "no_temporal_operation": 4,
        "other": 1,
        "spatial_omission": 4,
    },
)


def _require_exact_fields(
    payload: Mapping[str, Any], *, expected: frozenset[str], label: str
) -> None:
    actual = set(payload)
    if actual != expected:
        missing = sorted(expected - actual)
        extra = sorted(actual - expected)
        raise ValueError(f"{label} fields mismatch: missing={missing}, extra={extra}")


def _require_non_negative_counts(
    payload: Any, *, expected: frozenset[str], label: str
) -> dict[str, int]:
    if not isinstance(payload, dict):
        raise ValueError(f"{label} must be an object")
    _require_exact_fields(payload, expected=expected, label=label)
    if any(
        not isinstance(value, int) or isinstance(value, bool) or value < 0
        for value in payload.values()
    ):
        raise ValueError(f"{label} must contain non-negative integer counts")
    return dict(payload)


def load_expansion_batch_profile(
    path: Path,
) -> tuple[FrozenExpansionProfile, FrozenAuditSamplingProfile]:
    """Load one proposal-only expansion and audit authority profile."""

    try:
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise ValueError(f"invalid expansion batch profile JSON: {error}") from error
    if not isinstance(payload, dict):
        raise ValueError("expansion batch profile must be a JSON object")
    _require_exact_fields(
        payload,
        expected=EXPANSION_BATCH_PROFILE_FIELDS,
        label="expansion batch profile",
    )
    if payload["schema"] != EXPANSION_BATCH_PROFILE_SCHEMA:
        raise ValueError(
            f"expansion batch profile schema must be {EXPANSION_BATCH_PROFILE_SCHEMA}"
        )
    name = payload["name"]
    if not isinstance(name, str) or not name.strip():
        raise ValueError("expansion batch profile name must be a non-empty string")

    authority = payload["authority_sha256"]
    if not isinstance(authority, dict):
        raise ValueError("authority_sha256 must be an object")
    _require_exact_fields(
        authority,
        expected=AUTHORITY_SHA256_FIELDS,
        label="authority_sha256",
    )
    if any(
        not isinstance(value, str) or re.fullmatch(r"[0-9a-f]{64}", value) is None
        for value in authority.values()
    ):
        raise ValueError("authority_sha256 must contain lowercase SHA256 values")

    expected_counts = _require_non_negative_counts(
        payload["expected_counts"],
        expected=EXPECTED_COUNT_FIELDS,
        label="expected_counts",
    )
    audit = payload["audit"]
    if not isinstance(audit, dict):
        raise ValueError("audit must be an object")
    _require_exact_fields(audit, expected=AUDIT_PROFILE_FIELDS, label="audit")
    audit_name = audit["name"]
    if not isinstance(audit_name, str) or not audit_name.strip():
        raise ValueError("audit name must be a non-empty string")
    sample_size = audit["sample_size"]
    if not isinstance(sample_size, int) or isinstance(sample_size, bool) or sample_size < 0:
        raise ValueError("audit sample_size must be a non-negative integer")
    risk_fields = frozenset(RISK_STRATA)
    expected_source_support = _require_non_negative_counts(
        audit["expected_source_support"],
        expected=risk_fields,
        label="expected source support",
    )
    quotas = _require_non_negative_counts(
        audit["quotas"], expected=risk_fields, label="audit quotas"
    )

    if payload["training_admission"] != TRAINING_ADMISSION:
        raise ValueError(f"training_admission must remain {TRAINING_ADMISSION}")
    if payload["validation_eligible"] is not False:
        raise ValueError("validation_eligible must remain false")
    if payload["test_eligible"] is not False:
        raise ValueError("test_eligible must remain false")
    if payload["production_merge"] != PRODUCTION_MERGE:
        raise ValueError(f"production_merge must remain {PRODUCTION_MERGE}")

    expansion_profile = FrozenExpansionProfile(
        name=name,
        fact_bundles_sha256=authority["fact_bundles"],
        task_text_candidates_sha256=authority["task_text_candidates"],
        reviewed_packet_sha256=authority["reviewed_packet"],
        existing_semantic_rows_sha256=authority["existing_semantic_rows"],
        mapping_sha256=authority["mapping"],
        expected_counts=expected_counts,
    )
    audit_profile = FrozenAuditSamplingProfile(
        name=audit_name,
        sample_size=sample_size,
        expected_source_support=expected_source_support,
        quotas=quotas,
    )
    _validate_audit_profile(audit_profile)
    return expansion_profile, audit_profile


@dataclass(frozen=True)
class StratifiedAuditPacketResult:
    source_representatives: list[dict[str, Any]]
    audit_rows: list[dict[str, Any]]
    source_manifest: list[dict[str, Any]]
    summary: dict[str, Any]


@dataclass(frozen=True)
class SourceDisjointReplaySelectionResult:
    """Proposal-only artifacts for one larger source-disjoint replay slice."""

    selection_ledger: list[dict[str, Any]]
    selection_manifest: list[dict[str, Any]]
    excluded_source_manifest: list[dict[str, Any]]
    audit_packet_input: list[dict[str, Any]]
    summary: dict[str, Any]
    hash_ledger: dict[str, Any]


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _authority_sha256(
    *,
    fact_bundles_path: Path,
    task_text_candidates_path: Path,
    reviewed_packet_path: Path,
    existing_semantic_rows_path: Path,
    id_mappings_path: Path,
) -> dict[str, str]:
    return {
        "fact_bundles": _sha256_file(fact_bundles_path),
        "task_text_candidates": _sha256_file(task_text_candidates_path),
        "reviewed_packet": _sha256_file(reviewed_packet_path),
        "existing_semantic_rows": _sha256_file(existing_semantic_rows_path),
        "mapping": _sha256_file(id_mappings_path),
    }


def _validate_profile(
    *,
    profile: FrozenExpansionProfile,
    fact_bundles_path: Path,
    task_text_candidates_path: Path,
    reviewed_packet_path: Path,
    existing_semantic_rows_path: Path,
    id_mappings_path: Path,
) -> dict[str, str]:
    actual = _authority_sha256(
        fact_bundles_path=fact_bundles_path,
        task_text_candidates_path=task_text_candidates_path,
        reviewed_packet_path=reviewed_packet_path,
        existing_semantic_rows_path=existing_semantic_rows_path,
        id_mappings_path=id_mappings_path,
    )
    expected = {
        "fact_bundles": profile.fact_bundles_sha256,
        "task_text_candidates": profile.task_text_candidates_sha256,
        "reviewed_packet": profile.reviewed_packet_sha256,
        "existing_semantic_rows": profile.existing_semantic_rows_sha256,
        "mapping": profile.mapping_sha256,
    }
    qualifier = (
        "production profile"
        if profile is PRODUCTION_EXPANSION_PROFILE
        else "authority profile"
    )
    for field, expected_sha256 in expected.items():
        label = field.replace("_", " ")
        if not re.fullmatch(r"[0-9a-f]{64}", expected_sha256):
            raise ValueError(f"{profile.name} has invalid {label} SHA256")
        if actual[field] != expected_sha256:
            raise ValueError(
                f"{label} SHA256 does not match {qualifier} {profile.name}: "
                f"expected {expected_sha256}, got {actual[field]}"
            )
    if set(profile.expected_counts) != EXPECTED_COUNT_FIELDS:
        raise ValueError(
            f"authority profile {profile.name} must freeze all expansion counts"
        )
    if any(
        not isinstance(value, int) or isinstance(value, bool) or value < 0
        for value in profile.expected_counts.values()
    ):
        raise ValueError(f"authority profile {profile.name} has invalid expected counts")
    return actual


def _load_mapping(path: Path) -> dict[str, int]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return validate_stable_94_mapping(payload.get("l3") or {})


def _l3_sequence(row: dict[str, Any], *, label: str) -> tuple[str, ...]:
    values = row.get("l3_sequence")
    if not isinstance(values, list):
        raise ValueError(f"{label} l3_sequence must be a list")
    if any(not isinstance(value, str) or not value for value in values):
        raise ValueError(f"{label} l3_sequence contains an invalid L3 code")
    return tuple(values)


def _validate_mapped_chain(
    row: dict[str, Any], *, label: str, l3_to_id: Mapping[str, int]
) -> tuple[str, ...]:
    sequence = _l3_sequence(row, label=label)
    missing = sorted(set(sequence) - set(l3_to_id))
    if missing:
        raise ValueError(f"unmapped L3 codes in {label}: {missing}")
    return sequence


def _dedup_key(
    row: dict[str, Any], *, label: str, l3_to_id: Mapping[str, int]
) -> tuple[str, str, tuple[str, ...]]:
    task_name = str(row.get("task_name") or "").strip()
    task_description = str(row.get("task_description") or "").strip()
    if not task_name or not task_description:
        raise ValueError(f"{label} requires task_name and task_description")
    return (
        _normalized_text(task_name),
        _normalized_text(task_description),
        _validate_mapped_chain(row, label=label, l3_to_id=l3_to_id),
    )


def _terminal_row(
    text: dict[str, Any], *, terminal_status: str, reason: str
) -> dict[str, Any]:
    source_sha, workflow_id = _identity(text)
    return {
        "schema": "gis_recommend.gee_workflow_expansion_terminal.v1",
        "source_sha256": source_sha,
        "source_path": str(text.get("source_path") or ""),
        "workflow_id": workflow_id,
        "workflow_key": [source_sha, workflow_id],
        "terminal_status": terminal_status,
        "reason": reason,
        "training_admission": TRAINING_ADMISSION,
        "validation_eligible": False,
        "test_eligible": False,
        "production_merge": PRODUCTION_MERGE,
    }


def _proposal_row(fact: dict[str, Any], text: dict[str, Any]) -> dict[str, Any]:
    source_sha, workflow_id = _identity(text)
    proposal_id = hashlib.sha256(
        f"{source_sha}\0{workflow_id}".encode("utf-8")
    ).hexdigest()[:24]
    evidence_locations: list[dict[str, Any]] = []
    for fact_type, field in (
        ("dataset", "dataset_facts"),
        ("temporal", "temporal_facts"),
        ("spatial_input", "spatial_input_facts"),
        ("transformation", "transformation_facts"),
        ("output", "output_facts"),
    ):
        for evidence in fact.get(field) or []:
            location = evidence.get("source_location") if isinstance(evidence, dict) else None
            if isinstance(location, dict):
                evidence_locations.append(
                    {
                        "fact_id": evidence.get("fact_id"),
                        "fact_type": fact_type,
                        "source_location": dict(location),
                    }
                )
    return {
        "schema": "gis_recommend.gee_workflow_expansion_proposal.v1",
        "proposal_id": f"gee_expansion_{proposal_id}",
        "source_sha256": source_sha,
        "source_path": str(text["source_path"]),
        "workflow_id": workflow_id,
        "workflow_key": [source_sha, workflow_id],
        "exact_dag_fingerprint": str(fact["exact_dag_fingerprint"]),
        "task_name": str(text["task_name"]),
        "task_description": str(text["task_description"]),
        "operator_sequence": list(fact["operator_sequence"]),
        "l3_sequence": list(fact["l3_sequence"]),
        "risk_flags": list(text.get("risk_flags") or []),
        "known_omissions": list(text.get("known_omissions") or []),
        "calibration_stratum": str(text["calibration_stratum"]),
        "evidence_locations": evidence_locations,
        "fact_bundle_sha256": _record_sha256(fact),
        "task_text_candidate_sha256": _record_sha256(text),
        "proposal_status": "pending_sampling_audit",
        "training_admission": TRAINING_ADMISSION,
        "validation_eligible": False,
        "test_eligible": False,
        "production_merge": PRODUCTION_MERGE,
    }


def classify_risk_stratum(row: Mapping[str, Any]) -> str:
    """Assign one deterministic audit stratum from frozen candidate risk flags."""

    values = row.get("risk_flags")
    if not isinstance(values, list) or any(not isinstance(value, str) for value in values):
        raise ValueError("proposal risk_flags must be a list of strings")
    flags = set(values)
    if "no_source_backed_spatial_input" in flags or "opaque_spatial_expression" in flags:
        return "spatial_omission"
    if "long_chain_20_plus" in flags or "repeated_operator" in flags:
        return "long_or_repeated"
    if "multiple_dataset_facts" in flags or "private_asset_redacted" in flags:
        return "multi_dataset_private"
    if "no_source_backed_temporal_operation" in flags:
        return "no_temporal_operation"
    if {
        "dynamic_transformation_arguments",
        "external_spatial_identifier",
    }.issubset(flags):
        return "external_dynamic"
    return "other"


def largest_remainder_quotas(
    source_support: Mapping[str, int], *, sample_size: int
) -> dict[str, int]:
    """Allocate a deterministic proportional sample using integer remainders."""

    if tuple(source_support) != RISK_STRATA:
        raise ValueError("source support must contain the six risk strata in fixed order")
    counts = dict(source_support)
    if any(not isinstance(value, int) or isinstance(value, bool) or value < 0 for value in counts.values()):
        raise ValueError("source support counts must be non-negative integers")
    total = sum(counts.values())
    if not isinstance(sample_size, int) or isinstance(sample_size, bool) or not 0 <= sample_size <= total:
        raise ValueError("audit sample_size must be between zero and source support")
    if total == 0:
        return {stratum: 0 for stratum in RISK_STRATA}
    quotas: dict[str, int] = {}
    remainders: list[tuple[int, int, str]] = []
    for order, stratum in enumerate(RISK_STRATA):
        quota, remainder = divmod(counts[stratum] * sample_size, total)
        quotas[stratum] = quota
        remainders.append((-remainder, order, stratum))
    for _, _, stratum in sorted(remainders)[: sample_size - sum(quotas.values())]:
        quotas[stratum] += 1
    return quotas


def _validate_audit_profile(profile: FrozenAuditSamplingProfile) -> None:
    for label, values in (
        ("expected source support", profile.expected_source_support),
        ("audit quotas", profile.quotas),
    ):
        if tuple(values) != RISK_STRATA:
            raise ValueError(f"{label} must contain the six risk strata in fixed order")
        if any(not isinstance(value, int) or isinstance(value, bool) or value < 0 for value in values.values()):
            raise ValueError(f"{label} must contain non-negative integer counts")
    if sum(profile.quotas.values()) != profile.sample_size:
        raise ValueError("audit quotas must sum to sample_size")
    computed = largest_remainder_quotas(
        profile.expected_source_support, sample_size=profile.sample_size
    )
    if dict(profile.quotas) != computed:
        raise ValueError("audit quotas do not match deterministic largest-remainder allocation")


def _source_representatives(
    proposal_rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    priority = {stratum: index for index, stratum in enumerate(RISK_REPRESENTATIVE_PRIORITY)}
    identities: set[tuple[str, str]] = set()
    by_source: dict[str, tuple[tuple[int, str, str], dict[str, Any]]] = {}
    for proposal in proposal_rows:
        identity = _identity(proposal)
        if identity in identities:
            raise ValueError(f"duplicate proposal workflow identity: {identity}")
        identities.add(identity)
        if proposal.get("proposal_status") != "pending_sampling_audit":
            raise ValueError(f"proposal is not pending sampling audit: {identity}")
        if proposal.get("training_admission") != TRAINING_ADMISSION:
            raise ValueError(f"proposal training admission drift: {identity}")
        stratum = classify_risk_stratum(proposal)
        representative = {**proposal, "risk_stratum": stratum}
        rank = (priority[stratum], identity[1], str(proposal.get("proposal_id") or ""))
        current = by_source.get(identity[0])
        if current is None or rank < current[0]:
            by_source[identity[0]] = (rank, representative)
    return [by_source[source_sha][1] for source_sha in sorted(by_source)]


def _audit_population(
    proposal_rows: list[dict[str, Any]], *, reviewed_packet_path: Path
) -> tuple[list[dict[str, Any]], set[str], dict[str, int]]:
    reviewed_sources = {
        source_sha
        for source_sha, _ in _index(
            _load_jsonl(Path(reviewed_packet_path)), "audit reviewed packet"
        )
    }
    all_representatives = _source_representatives(proposal_rows)
    excluded_sources = {
        row["source_sha256"]
        for row in all_representatives
        if row["source_sha256"] in reviewed_sources
    }
    representatives = [
        row
        for row in all_representatives
        if row["source_sha256"] not in reviewed_sources
    ]
    support = Counter(row["risk_stratum"] for row in representatives)
    source_support = {stratum: support[stratum] for stratum in RISK_STRATA}
    return representatives, excluded_sources, source_support


def _verified_source(
    proposal: Mapping[str, Any], *, source_root: Path
) -> tuple[bytes, Path]:
    root = Path(source_root).resolve()
    relative = Path(str(proposal.get("source_path") or ""))
    if relative.is_absolute() or not relative.parts:
        raise ValueError("proposal source_path must be relative to source_root")
    path = (root / relative).resolve()
    try:
        path.relative_to(root)
    except ValueError as error:
        raise ValueError("proposal source_path escapes source_root") from error
    content = path.read_bytes()
    actual_sha = hashlib.sha256(content).hexdigest()
    if actual_sha != proposal.get("source_sha256"):
        raise ValueError(
            f"source SHA256 mismatch for {proposal.get('source_path')}: "
            f"expected {proposal.get('source_sha256')}, got {actual_sha}"
        )
    return content, path


def _source_snippet(content: bytes, evidence_locations: Any) -> str:
    if not isinstance(evidence_locations, list) or not evidence_locations:
        raise ValueError("proposal requires fact-backed evidence locations")
    lines = content.decode("utf-8", errors="replace").splitlines()
    selected: set[int] = set()
    for evidence in evidence_locations:
        location = evidence.get("source_location") if isinstance(evidence, dict) else None
        if not isinstance(location, dict):
            raise ValueError("proposal evidence location is invalid")
        start = location.get("start_line")
        end = location.get("end_line")
        if not isinstance(start, int) or isinstance(start, bool) or not isinstance(end, int) or isinstance(end, bool):
            raise ValueError("proposal evidence location requires integer line bounds")
        if start < 1 or end < start or end > len(lines):
            raise ValueError("proposal evidence location is outside the source file")
        selected.update(range(max(1, start - 2), min(len(lines), end + 2) + 1))
    chosen = sorted(selected)[:MAX_SOURCE_SNIPPET_LINES]
    return "\n".join(f"L{line_number:04d}: {lines[line_number - 1]}" for line_number in chosen)


def build_stratified_audit_packet(
    *,
    proposal_rows: list[dict[str, Any]],
    reviewed_packet_path: Path,
    audit_reviewed_packet_path: Path | None = None,
    source_root: Path,
    profile: FrozenAuditSamplingProfile = PRODUCTION_AUDIT_SAMPLING_PROFILE,
) -> StratifiedAuditPacketResult:
    """Select and source-verify a deterministic proposal-only audit sample."""

    _validate_audit_profile(profile)
    audit_reviewed_path = Path(audit_reviewed_packet_path or reviewed_packet_path)
    representatives, excluded_sources, source_support = _audit_population(
        proposal_rows, reviewed_packet_path=audit_reviewed_path
    )
    if source_support != dict(profile.expected_source_support):
        raise ValueError(
            f"source support does not match audit profile {profile.name}: "
            f"expected {dict(profile.expected_source_support)}, got {source_support}"
        )

    sampled: list[dict[str, Any]] = []
    for stratum in RISK_STRATA:
        members = sorted(
            (row for row in representatives if row["risk_stratum"] == stratum),
            key=lambda row: (row["source_sha256"], row["workflow_id"]),
        )
        sampled.extend(members[: profile.quotas[stratum]])

    audit_rows: list[dict[str, Any]] = []
    source_manifest: list[dict[str, Any]] = []
    for audit_index, proposal in enumerate(sampled, 1):
        content, path = _verified_source(proposal, source_root=Path(source_root))
        snippet = _source_snippet(content, proposal.get("evidence_locations"))
        audit_row = {
            **proposal,
            "schema": "gis_recommend.gee_workflow_expansion_audit_row.v1",
            "audit_index": audit_index,
            "source_sha256_verified": True,
            "source_bytes": len(content),
            "source_snippet": snippet,
            "audit_status": "pending_human_review",
        }
        audit_row["audit_row_authority_sha256"] = _record_sha256(audit_row)
        audit_row.update({field: "" for field in HUMAN_AUDIT_FIELDS})
        audit_rows.append(audit_row)
        source_manifest.append(
            {
                "schema": "gis_recommend.gee_workflow_expansion_audit_source.v1",
                "audit_index": audit_index,
                "source_sha256": proposal["source_sha256"],
                "source_path": proposal["source_path"],
                "source_bytes": len(content),
                "source_sha256_verified": True,
                "resolved_under_source_root": str(path.relative_to(Path(source_root).resolve())).replace("\\", "/"),
                "risk_stratum": proposal["risk_stratum"],
                "workflow_id": proposal["workflow_id"],
            }
        )

    if len(audit_rows) != profile.sample_size:
        raise ValueError("audit sample size does not match sampling profile")
    if len({row["source_sha256"] for row in audit_rows}) != len(audit_rows):
        raise ValueError("audit sample must contain unique sources")
    summary = {
        "schema": "gis_recommend.gee_workflow_expansion_audit_summary.v1",
        "sampling_profile": profile.name,
        "proposal_rows": len(proposal_rows),
        "eligible_sources": len(representatives),
        "audit_reviewed_packet_sha256": _sha256_file(audit_reviewed_path),
        "audit_reviewed_excluded_sources": len(excluded_sources),
        "source_support": source_support,
        "audit_sample_rows": len(audit_rows),
        "audit_quotas": dict(profile.quotas),
        "audit_status": "pending_sampling_audit",
        "training_rows_emitted": 0,
        "training_admission": TRAINING_ADMISSION,
        "validation_eligible": False,
        "test_eligible": False,
        "production_merge": PRODUCTION_MERGE,
    }
    return StratifiedAuditPacketResult(
        source_representatives=representatives,
        audit_rows=audit_rows,
        source_manifest=source_manifest,
        summary=summary,
    )


def _validate_selection_proposal(
    row: dict[str, Any], *, label: str, l3_to_id: Mapping[str, int]
) -> tuple[str, str]:
    identity = _identity(row)
    if row.get("schema") != "gis_recommend.gee_workflow_expansion_proposal.v1":
        raise ValueError(f"{label} schema is not an expansion proposal: {identity}")
    if row.get("workflow_key") != [identity[0], identity[1]]:
        raise ValueError(f"{label} workflow_key mismatch: {identity}")
    if not str(row.get("source_path") or "").strip():
        raise ValueError(f"{label} source_path is missing: {identity}")
    if row.get("proposal_status") != "pending_sampling_audit":
        raise ValueError(f"{label} is not pending sampling audit: {identity}")
    if row.get("training_admission") != TRAINING_ADMISSION:
        raise ValueError(f"{label} training admission drift: {identity}")
    if row.get("validation_eligible") is not False:
        raise ValueError(f"{label} validation eligibility drift: {identity}")
    if row.get("test_eligible") is not False:
        raise ValueError(f"{label} test eligibility drift: {identity}")
    if row.get("production_merge") != PRODUCTION_MERGE:
        raise ValueError(f"{label} production merge drift: {identity}")
    if not re.fullmatch(
        r"[0-9a-f]{64}", str(row.get("exact_dag_fingerprint") or "")
    ):
        raise ValueError(f"{label} exact DAG fingerprint is invalid: {identity}")
    for field in ("fact_bundle_sha256", "task_text_candidate_sha256"):
        if not re.fullmatch(r"[0-9a-f]{64}", str(row.get(field) or "")):
            raise ValueError(f"{label} {field} is invalid: {identity}")
    operators = row.get("operator_sequence")
    if not isinstance(operators, list) or any(
        not isinstance(value, str) or not value for value in operators
    ):
        raise ValueError(f"{label} operator_sequence is invalid: {identity}")
    dedup_key = _dedup_key(row, label=label, l3_to_id=l3_to_id)
    if len(operators) != len(dedup_key[2]):
        raise ValueError(f"{label} operator/L3 length mismatch: {identity}")
    classify_risk_stratum(row)
    return identity


def _selection_permission_fields() -> dict[str, Any]:
    return {
        "training_admission": TRAINING_ADMISSION,
        "validation_eligible": False,
        "test_eligible": False,
        "production_merge": PRODUCTION_MERGE,
    }


def _selection_artifact_bytes(
    *,
    selection_ledger: list[dict[str, Any]],
    selection_manifest: list[dict[str, Any]],
    excluded_source_manifest: list[dict[str, Any]],
    audit_packet_input: list[dict[str, Any]],
    summary: dict[str, Any],
) -> dict[str, bytes]:
    return {
        "selection_ledger.jsonl": _canonical_jsonl(selection_ledger),
        "selection_manifest.jsonl": _canonical_jsonl(selection_manifest),
        "excluded_source_manifest.jsonl": _canonical_jsonl(excluded_source_manifest),
        "audit_packet_input.jsonl": _canonical_jsonl(audit_packet_input),
        "summary.json": _pretty_json(summary),
    }


def build_source_disjoint_replay_selection(
    *,
    candidate_proposals_path: Path,
    reviewed_packet_path: Path,
    prior_proposals_path: Path,
    id_mappings_path: Path,
    target_source_count: int = 100,
    audit_sample_size: int = 30,
) -> SourceDisjointReplaySelectionResult:
    """Select a bounded, hash-bound source-disjoint proposal replay batch."""

    if (
        not isinstance(target_source_count, int)
        or isinstance(target_source_count, bool)
        or target_source_count < 1
    ):
        raise ValueError("target_source_count must be a positive integer")
    if (
        not isinstance(audit_sample_size, int)
        or isinstance(audit_sample_size, bool)
        or audit_sample_size < 0
    ):
        raise ValueError("audit_sample_size must be a non-negative integer")

    paths = {
        "candidate_proposals": Path(candidate_proposals_path),
        "reviewed_packet": Path(reviewed_packet_path),
        "prior_proposals": Path(prior_proposals_path),
        "mapping": Path(id_mappings_path),
    }
    authority_sha256 = {
        role: _sha256_file(path) for role, path in paths.items()
    }
    l3_to_id = _load_mapping(paths["mapping"])
    candidate_index = _index(
        _load_jsonl(paths["candidate_proposals"]), "larger replay proposal"
    )
    reviewed_index = _index(
        _load_jsonl(paths["reviewed_packet"]), "reviewed packet"
    )
    prior_index = _index(
        _load_jsonl(paths["prior_proposals"]), "prior expansion proposal"
    )

    candidate_dedup: dict[tuple[str, str, tuple[str, ...]], tuple[str, str]] = {}
    for identity in sorted(candidate_index):
        row = candidate_index[identity]
        _validate_selection_proposal(
            row, label="larger replay proposal", l3_to_id=l3_to_id
        )
        dedup_key = _dedup_key(
            row, label="larger replay proposal", l3_to_id=l3_to_id
        )
        canonical = candidate_dedup.get(dedup_key)
        if canonical is not None:
            raise ValueError(
                "larger replay proposal authority contains a semantic duplicate: "
                f"{identity} duplicates {canonical}"
            )
        candidate_dedup[dedup_key] = identity
    for identity in sorted(prior_index):
        _validate_selection_proposal(
            prior_index[identity],
            label="prior expansion proposal",
            l3_to_id=l3_to_id,
        )

    reviewed_sources = {source_sha for source_sha, _ in reviewed_index}
    prior_sources = {source_sha for source_sha, _ in prior_index}
    candidate_sources = {source_sha for source_sha, _ in candidate_index}
    excluded_sources = reviewed_sources | prior_sources
    eligible_sources = sorted(candidate_sources - excluded_sources)
    selected_sources = set(eligible_sources[:target_source_count])

    selected_source_rank = {
        source_sha: rank
        for rank, source_sha in enumerate(sorted(selected_sources), 1)
    }
    selection_ledger: list[dict[str, Any]] = []
    selection_manifest: list[dict[str, Any]] = []
    for identity in sorted(candidate_index):
        proposal = candidate_index[identity]
        source_sha, workflow_id = identity
        if source_sha in reviewed_sources:
            status = "excluded_reviewed_source"
            reason = "source SHA256 is present in the frozen reviewed packet"
        elif source_sha in prior_sources:
            status = "excluded_prior_proposal_source"
            reason = "source SHA256 is present in the frozen prior proposal authority"
        elif source_sha in selected_sources:
            status = "selected_for_larger_source_disjoint_replay"
            reason = "source SHA256 is within the stable bounded selection"
        else:
            status = "not_selected_target_limit"
            reason = "source SHA256 sorts after the configured source target"
        ledger_row = {
            "schema": "gis_recommend.gee_source_disjoint_selection_ledger.v1",
            "source_sha256": source_sha,
            "source_path": str(proposal["source_path"]),
            "workflow_id": workflow_id,
            "workflow_key": [source_sha, workflow_id],
            "proposal_id": str(proposal["proposal_id"]),
            "selection_status": status,
            "reason": reason,
            **_selection_permission_fields(),
        }
        selection_ledger.append(ledger_row)
        if source_sha not in selected_sources:
            continue
        manifest_row = {
            **proposal,
            "schema": "gis_recommend.gee_source_disjoint_selection_manifest.v1",
            "selection_status": status,
            "selected_source_rank": selected_source_rank[source_sha],
            **_selection_permission_fields(),
        }
        manifest_row["selection_row_sha256"] = _record_sha256(manifest_row)
        selection_manifest.append(manifest_row)

    source_paths: dict[str, set[str]] = {}
    for row in (*reviewed_index.values(), *prior_index.values()):
        source_paths.setdefault(str(row["source_sha256"]), set()).add(
            str(row.get("source_path") or "")
        )
    excluded_source_manifest = [
        {
            "schema": "gis_recommend.gee_source_disjoint_exclusion.v1",
            "source_sha256": source_sha,
            "source_paths": sorted(path for path in source_paths[source_sha] if path),
            "exclusion_authorities": [
                role
                for role, members in (
                    ("reviewed_packet", reviewed_sources),
                    ("prior_proposals", prior_sources),
                )
                if source_sha in members
            ],
            "present_in_candidate_authority": source_sha in candidate_sources,
            **_selection_permission_fields(),
        }
        for source_sha in sorted(excluded_sources)
    ]

    selected_proposals = [
        candidate_index[identity]
        for identity in sorted(candidate_index)
        if identity[0] in selected_sources
    ]
    representatives = _source_representatives(selected_proposals)
    support_counter = Counter(row["risk_stratum"] for row in representatives)
    risk_source_support = {
        stratum: support_counter[stratum] for stratum in RISK_STRATA
    }
    bounded_audit_size = min(audit_sample_size, len(representatives))
    audit_quotas = largest_remainder_quotas(
        risk_source_support, sample_size=bounded_audit_size
    )
    sampled_representatives: list[dict[str, Any]] = []
    for stratum in RISK_STRATA:
        members = sorted(
            (row for row in representatives if row["risk_stratum"] == stratum),
            key=lambda row: (row["source_sha256"], row["workflow_id"]),
        )
        sampled_representatives.extend(members[: audit_quotas[stratum]])
    audit_packet_input = []
    for audit_index, proposal in enumerate(sampled_representatives, 1):
        row = {
            **proposal,
            "schema": "gis_recommend.gee_source_disjoint_audit_packet_input.v1",
            "audit_index": audit_index,
            "audit_status": "pending_source_verification_and_human_review",
            **_selection_permission_fields(),
        }
        row["audit_input_row_sha256"] = _record_sha256(row)
        audit_packet_input.append(row)

    counts = {
        "candidate_rows": len(candidate_index),
        "candidate_sources": len(candidate_sources),
        "reviewed_sources": len(reviewed_sources),
        "prior_proposal_rows": len(prior_index),
        "prior_proposal_sources": len(prior_sources),
        "excluded_candidate_sources": len(candidate_sources & excluded_sources),
        "eligible_sources": len(eligible_sources),
        "selected_sources": len(selected_sources),
        "selected_rows": len(selection_manifest),
        "not_selected_target_limit_sources": len(eligible_sources)
        - len(selected_sources),
        "audit_packet_input_rows": len(audit_packet_input),
    }
    summary = {
        "schema": "gis_recommend.gee_source_disjoint_selection_summary.v1",
        "selection_policy": "source_sha256_ascending_bounded_v1",
        "target_source_count": target_source_count,
        "audit_sample_size_requested": audit_sample_size,
        "audit_sample_size_bounded": bounded_audit_size,
        "counts": counts,
        "risk_source_support": risk_source_support,
        "audit_quotas": audit_quotas,
        "proposal_status": "pending_sampling_audit",
        "training_rows_emitted": 0,
        **_selection_permission_fields(),
    }
    artifact_bytes = _selection_artifact_bytes(
        selection_ledger=selection_ledger,
        selection_manifest=selection_manifest,
        excluded_source_manifest=excluded_source_manifest,
        audit_packet_input=audit_packet_input,
        summary=summary,
    )
    hash_ledger = {
        "schema": "gis_recommend.gee_source_disjoint_selection_hash_ledger.v1",
        "selection_policy": summary["selection_policy"],
        "authority_sha256": authority_sha256,
        "artifact_sha256": {
            name: hashlib.sha256(content).hexdigest()
            for name, content in sorted(artifact_bytes.items())
        },
        "training_rows_emitted": 0,
        **_selection_permission_fields(),
    }
    return SourceDisjointReplaySelectionResult(
        selection_ledger=selection_ledger,
        selection_manifest=selection_manifest,
        excluded_source_manifest=excluded_source_manifest,
        audit_packet_input=audit_packet_input,
        summary=summary,
        hash_ledger=hash_ledger,
    )


def _with_schema(row: dict[str, Any], schema: str, **extra: Any) -> dict[str, Any]:
    return {**row, "schema": schema, **extra}


def _validate_terminal_counts(counts: Mapping[str, int]) -> None:
    if counts["remaining"] != sum(
        counts[field]
        for field in (
            "excluded_reviewed_source_overlap",
            "proposal_eligible",
            "excluded_existing_or_batch_duplicate",
            "deferred_length",
            "fail_closed_semantic_gate",
        )
    ):
        raise ValueError("remaining candidates do not have exactly one terminal status")


def _validate_expected_counts(
    counts: Mapping[str, int], *, profile: FrozenExpansionProfile
) -> None:
    for field, expected in profile.expected_counts.items():
        if counts[field] != expected:
            raise ValueError(
                f"authority profile count mismatch for {field}: "
                f"expected {expected}, got {counts[field]}"
            )


def _route_expansion_census(
    *,
    fact_bundles_path: Path,
    task_text_candidates_path: Path,
    reviewed_packet_path: Path,
    existing_semantic_rows_path: Path,
    id_mappings_path: Path,
    authority_profile_name: str,
    authority_sha256: Mapping[str, str],
) -> ExpansionCensusResult:
    """Route every unreviewed canonical task-text identity to one terminal state."""

    paths = {
        "fact_bundles_path": Path(fact_bundles_path),
        "task_text_candidates_path": Path(task_text_candidates_path),
        "reviewed_packet_path": Path(reviewed_packet_path),
        "existing_semantic_rows_path": Path(existing_semantic_rows_path),
        "id_mappings_path": Path(id_mappings_path),
    }
    l3_to_id = _load_mapping(paths["id_mappings_path"])
    fact_index = _index(
        _load_jsonl(paths["fact_bundles_path"]), "expansion fact bundle"
    )
    text_index = _index(
        _load_jsonl(paths["task_text_candidates_path"]),
        "canonical task-text candidate",
    )
    reviewed_index = _index(
        _load_jsonl(paths["reviewed_packet_path"]), "reviewed packet"
    )
    existing_rows = _load_jsonl(paths["existing_semantic_rows_path"])

    reviewed_identities = set(reviewed_index)
    reviewed_sources = {source_sha for source_sha, _ in reviewed_identities}
    remaining_identities = sorted(set(text_index) - reviewed_identities)

    seen_dedup: dict[tuple[str, str, tuple[str, ...]], dict[str, str]] = {}
    for row in existing_rows:
        identity = _identity(row)
        key = _dedup_key(row, label="existing semantic row", l3_to_id=l3_to_id)
        seen_dedup.setdefault(
            key,
            {
                "kind": "existing_semantic_row",
                "source_sha256": identity[0],
                "workflow_id": identity[1],
            },
        )

    remaining_ledger: list[dict[str, Any]] = []
    proposal_rows: list[dict[str, Any]] = []
    source_overlap_sidecar: list[dict[str, Any]] = []
    fail_closed_sidecar: list[dict[str, Any]] = []
    duplicate_sidecar: list[dict[str, Any]] = []
    length_sidecar: list[dict[str, Any]] = []

    for identity in remaining_identities:
        text = text_index[identity]
        source_sha, workflow_id = identity
        if source_sha in reviewed_sources:
            terminal = _terminal_row(
                text,
                terminal_status="excluded_reviewed_source_overlap",
                reason="source SHA256 overlaps the reviewed packet under another workflow identity",
            )
            remaining_ledger.append(terminal)
            source_overlap_sidecar.append(
                _with_schema(
                    terminal,
                    "gis_recommend.gee_workflow_expansion_source_overlap.v1",
                )
            )
            continue

        fact = fact_index.get(identity)
        try:
            if fact is None:
                raise ValueError("matching fact bundle is missing")
            validate_source_backed_candidate(fact=fact, text=text)
            if str(fact.get("source_path") or "") != str(text.get("source_path") or ""):
                raise ValueError("fact/text source_path mismatch")
            dedup_key = _dedup_key(
                text, label="task-text candidate", l3_to_id=l3_to_id
            )
        except (TypeError, ValueError) as error:
            terminal = _terminal_row(
                text,
                terminal_status="fail_closed_semantic_gate",
                reason=str(error),
            )
            remaining_ledger.append(terminal)
            fail_closed_sidecar.append(
                _with_schema(
                    terminal,
                    "gis_recommend.gee_workflow_expansion_semantic_failure.v1",
                )
            )
            continue

        canonical = seen_dedup.get(dedup_key)
        if canonical is not None:
            terminal = _terminal_row(
                text,
                terminal_status="excluded_existing_or_batch_duplicate",
                reason=(
                    "normalized task name, task description, and L3 sequence duplicate "
                    f"{canonical['kind']}"
                ),
            )
            remaining_ledger.append(terminal)
            duplicate_sidecar.append(
                _with_schema(
                    terminal,
                    "gis_recommend.gee_workflow_expansion_duplicate.v1",
                    duplicate_of_source_sha256=canonical["source_sha256"],
                    duplicate_of_workflow_id=canonical["workflow_id"],
                    dedup_key="normalized_task_name_description_plus_l3_sequence",
                )
            )
            continue

        seen_dedup[dedup_key] = {
            "kind": "expansion_batch_candidate",
            "source_sha256": source_sha,
            "workflow_id": workflow_id,
        }
        content_length = len(dedup_key[2])
        model_sequence_length = content_length + 2
        if model_sequence_length > V4_MAX_SEQUENCE_LENGTH:
            terminal = _terminal_row(
                text,
                terminal_status="deferred_length",
                reason=(
                    f"model sequence length {model_sequence_length} exceeds "
                    f"V4 maximum {V4_MAX_SEQUENCE_LENGTH}; no truncation permitted"
                ),
            )
            remaining_ledger.append(terminal)
            length_sidecar.append(
                _with_schema(
                    terminal,
                    "gis_recommend.gee_workflow_expansion_length_sidecar.v1",
                    content_length=content_length,
                    model_sequence_length=model_sequence_length,
                    v4_max_sequence_length=V4_MAX_SEQUENCE_LENGTH,
                    operator_sequence=list(fact["operator_sequence"]),
                    l3_sequence=list(fact["l3_sequence"]),
                )
            )
            continue

        terminal = _terminal_row(
            text,
            terminal_status="proposal_eligible",
            reason="passed deterministic expansion gates pending sampling audit",
        )
        remaining_ledger.append(terminal)
        proposal_rows.append(_proposal_row(fact, text))

    status_counts = {
        status: sum(row["terminal_status"] == status for row in remaining_ledger)
        for status in (
            "excluded_reviewed_source_overlap",
            "proposal_eligible",
            "excluded_existing_or_batch_duplicate",
            "deferred_length",
            "fail_closed_semantic_gate",
        )
    }
    counts = {
        "canonical_candidates": len(text_index),
        "reviewed_identities": len(reviewed_identities),
        "remaining": len(remaining_identities),
        **status_counts,
    }
    _validate_terminal_counts(counts)
    if len({_identity(row) for row in remaining_ledger}) != len(remaining_ledger):
        raise ValueError("remaining ledger contains duplicate workflow identities")

    summary = {
        "schema": "gis_recommend.gee_workflow_expansion_census_summary.v1",
        "authority_profile": authority_profile_name,
        "authority_sha256": dict(authority_sha256),
        "counts": counts,
        "terminal_priority": [
            "excluded_reviewed_source_overlap",
            "fail_closed_semantic_gate",
            "excluded_existing_or_batch_duplicate",
            "deferred_length",
            "proposal_eligible",
        ],
        "proposal_status": "pending_sampling_audit",
        "training_admission": TRAINING_ADMISSION,
        "validation_eligible": False,
        "test_eligible": False,
        "production_merge": PRODUCTION_MERGE,
    }
    return ExpansionCensusResult(
        remaining_ledger=remaining_ledger,
        proposal_rows=proposal_rows,
        source_overlap_sidecar=source_overlap_sidecar,
        fail_closed_sidecar=fail_closed_sidecar,
        duplicate_sidecar=duplicate_sidecar,
        length_sidecar=length_sidecar,
        summary=summary,
    )


def build_expansion_census(
    *,
    fact_bundles_path: Path,
    task_text_candidates_path: Path,
    reviewed_packet_path: Path,
    existing_semantic_rows_path: Path,
    id_mappings_path: Path,
    profile: FrozenExpansionProfile = PRODUCTION_EXPANSION_PROFILE,
) -> ExpansionCensusResult:
    """Replay routing under a frozen hash- and count-bound authority profile."""

    paths = {
        "fact_bundles_path": Path(fact_bundles_path),
        "task_text_candidates_path": Path(task_text_candidates_path),
        "reviewed_packet_path": Path(reviewed_packet_path),
        "existing_semantic_rows_path": Path(existing_semantic_rows_path),
        "id_mappings_path": Path(id_mappings_path),
    }
    authority_sha256 = _validate_profile(profile=profile, **paths)
    result = _route_expansion_census(
        **paths,
        authority_profile_name=profile.name,
        authority_sha256=authority_sha256,
    )
    _validate_expected_counts(result.summary["counts"], profile=profile)
    return result


def freeze_expansion_batch_profile(
    *,
    fact_bundles_path: Path,
    task_text_candidates_path: Path,
    reviewed_packet_path: Path,
    existing_semantic_rows_path: Path,
    id_mappings_path: Path,
    name: str,
    audit_name: str,
    audit_sample_size: int = 30,
) -> dict[str, Any]:
    """Derive a frozen profile from one routing pass over exact input bytes."""

    if not isinstance(name, str) or not name.strip():
        raise ValueError("name must be a non-empty string")
    if not isinstance(audit_name, str) or not audit_name.strip():
        raise ValueError("audit_name must be a non-empty string")
    paths = {
        "fact_bundles_path": Path(fact_bundles_path),
        "task_text_candidates_path": Path(task_text_candidates_path),
        "reviewed_packet_path": Path(reviewed_packet_path),
        "existing_semantic_rows_path": Path(existing_semantic_rows_path),
        "id_mappings_path": Path(id_mappings_path),
    }
    authority_sha256 = _authority_sha256(**paths)
    census = _route_expansion_census(
        **paths,
        authority_profile_name=name,
        authority_sha256=authority_sha256,
    )
    _, _, source_support = _audit_population(
        census.proposal_rows,
        reviewed_packet_path=paths["reviewed_packet_path"],
    )
    eligible_sources = sum(source_support.values())
    if audit_sample_size > eligible_sources:
        raise ValueError(
            f"audit sample requires {audit_sample_size} eligible sources; "
            f"found {eligible_sources}"
        )
    quotas = largest_remainder_quotas(
        source_support, sample_size=audit_sample_size
    )
    audit_profile = FrozenAuditSamplingProfile(
        name=audit_name,
        sample_size=audit_sample_size,
        expected_source_support=source_support,
        quotas=quotas,
    )
    _validate_audit_profile(audit_profile)
    return {
        "schema": EXPANSION_BATCH_PROFILE_SCHEMA,
        "name": name,
        "authority_sha256": authority_sha256,
        "expected_counts": dict(census.summary["counts"]),
        "audit": {
            "name": audit_name,
            "sample_size": audit_sample_size,
            "expected_source_support": source_support,
            "quotas": quotas,
        },
        "training_admission": TRAINING_ADMISSION,
        "validation_eligible": False,
        "test_eligible": False,
        "production_merge": PRODUCTION_MERGE,
    }


def _canonical_jsonl(rows: list[dict[str, Any]]) -> bytes:
    return b"".join(
        (
            json.dumps(row, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
            + "\n"
        ).encode("utf-8")
        for row in rows
    )


def _pretty_json(payload: Any) -> bytes:
    return (
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    ).encode("utf-8")


def _audit_csv(rows: list[dict[str, Any]]) -> bytes:
    fieldnames = sorted({field for row in rows for field in row})
    output = io.StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=fieldnames, lineterminator="\n")
    writer.writeheader()
    for row in rows:
        writer.writerow(
            {
                field: (
                    json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
                    if isinstance(value, (dict, list))
                    else value
                )
                for field, value in row.items()
            }
        )
    return output.getvalue().encode("utf-8")


def _expansion_report(summary: dict[str, Any]) -> bytes:
    census = summary["census"]["counts"]
    audit = summary["audit"]
    lines = [
        "# GEE Complete-Workflow Expansion Proposal Batch",
        "",
        f"- Remaining canonical candidates: {census['remaining']}",
        f"- Excluded reviewed-source overlap: {census['excluded_reviewed_source_overlap']}",
        f"- Proposal eligible: {census['proposal_eligible']}",
        f"- Eligible unique sources: {audit['eligible_sources']}",
        f"- Stratified audit sample: {audit['audit_sample_rows']}",
        "- Audit status: pending human review",
        "- New training rows emitted: 0",
        "- Validation/test eligibility: false",
        "- Production merge: not granted",
        "",
    ]
    return "\n".join(lines).encode("utf-8")


def write_expansion_outputs(
    *,
    census_result: ExpansionCensusResult,
    audit_result: StratifiedAuditPacketResult,
    output_dir: Path,
) -> dict[str, Any]:
    """Publish the complete proposal/audit package through one directory rename."""

    output_dir = Path(output_dir)
    if output_dir.exists():
        raise FileExistsError(f"output directory already exists: {output_dir}")
    summary = {
        "schema": "gis_recommend.gee_workflow_expansion_package_summary.v1",
        "census": census_result.summary,
        "audit": audit_result.summary,
        "training_rows_emitted": 0,
        "training_admission": TRAINING_ADMISSION,
        "validation_eligible": False,
        "test_eligible": False,
        "production_merge": PRODUCTION_MERGE,
    }
    audit_sample_rows = audit_result.summary["audit_sample_rows"]
    if (
        not isinstance(audit_sample_rows, int)
        or isinstance(audit_sample_rows, bool)
        or audit_sample_rows < 0
    ):
        raise ValueError("audit_sample_rows must be a non-negative integer")
    if audit_sample_rows != len(audit_result.audit_rows) or audit_sample_rows != len(
        audit_result.source_manifest
    ):
        raise ValueError("audit sample row count drift")
    artifacts = {
        "remaining_ledger.jsonl": _canonical_jsonl(census_result.remaining_ledger),
        "proposal_candidates.jsonl": _canonical_jsonl(census_result.proposal_rows),
        "source_overlap_sidecar.jsonl": _canonical_jsonl(census_result.source_overlap_sidecar),
        "semantic_fail_closed_sidecar.jsonl": _canonical_jsonl(census_result.fail_closed_sidecar),
        "duplicate_sidecar.jsonl": _canonical_jsonl(census_result.duplicate_sidecar),
        "length_sidecar.jsonl": _canonical_jsonl(census_result.length_sidecar),
        f"audit_sample_{audit_sample_rows}.jsonl": _canonical_jsonl(audit_result.audit_rows),
        f"audit_sample_{audit_sample_rows}.csv": _audit_csv(audit_result.audit_rows),
        "audit_source_manifest.jsonl": _canonical_jsonl(audit_result.source_manifest),
        "summary.json": _pretty_json(summary),
        "report.md": _expansion_report(summary),
    }
    artifact_sha256 = {
        name: hashlib.sha256(content).hexdigest()
        for name, content in sorted(artifacts.items())
    }
    hash_ledger = {
        "schema": "gis_recommend.gee_workflow_expansion_hash_ledger.v1",
        "authority_profile": census_result.summary.get("authority_profile"),
        "sampling_profile": audit_result.summary.get("sampling_profile"),
        "audit_reviewed_packet_sha256": audit_result.summary.get(
            "audit_reviewed_packet_sha256"
        ),
        "audit_reviewed_excluded_sources": audit_result.summary.get(
            "audit_reviewed_excluded_sources"
        ),
        "authority_sha256": census_result.summary.get("authority_sha256"),
        "artifact_sha256": artifact_sha256,
    }
    artifacts["hash_ledger.json"] = _pretty_json(hash_ledger)

    output_dir.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(
        tempfile.mkdtemp(prefix=f".{output_dir.name}.staging-", dir=output_dir.parent)
    )
    try:
        for name, content in artifacts.items():
            (staging / name).write_bytes(content)
        os.replace(staging, output_dir)
    except BaseException:
        shutil.rmtree(staging, ignore_errors=True)
        raise
    return hash_ledger


def write_source_disjoint_selection(
    result: SourceDisjointReplaySelectionResult, *, output_dir: Path
) -> dict[str, Any]:
    """Atomically publish proposal-only source-disjoint selection artifacts."""

    output_dir = Path(output_dir)
    if output_dir.exists():
        raise FileExistsError(f"output directory already exists: {output_dir}")
    artifacts = _selection_artifact_bytes(
        selection_ledger=result.selection_ledger,
        selection_manifest=result.selection_manifest,
        excluded_source_manifest=result.excluded_source_manifest,
        audit_packet_input=result.audit_packet_input,
        summary=result.summary,
    )
    actual_hashes = {
        name: hashlib.sha256(content).hexdigest()
        for name, content in sorted(artifacts.items())
    }
    if actual_hashes != result.hash_ledger.get("artifact_sha256"):
        raise ValueError("source-disjoint selection artifacts drifted after construction")
    artifacts["hash_ledger.json"] = _pretty_json(result.hash_ledger)

    output_dir.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(
        tempfile.mkdtemp(prefix=f".{output_dir.name}.staging-", dir=output_dir.parent)
    )
    try:
        for name, content in artifacts.items():
            (staging / name).write_bytes(content)
        os.replace(staging, output_dir)
    except BaseException:
        shutil.rmtree(staging, ignore_errors=True)
        raise
    return result.hash_ledger


def main(argv: list[str] | None = None) -> dict[str, Any]:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fact-bundles", type=Path, required=True)
    parser.add_argument("--task-text-candidates", type=Path, required=True)
    parser.add_argument("--reviewed-packet", type=Path, required=True)
    parser.add_argument("--audit-reviewed-packet", type=Path)
    parser.add_argument("--existing-semantic-rows", type=Path, required=True)
    parser.add_argument("--id-mappings", type=Path, required=True)
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--authority-profile", type=Path)
    args = parser.parse_args(argv)

    if args.authority_profile is None:
        expansion_profile = PRODUCTION_EXPANSION_PROFILE
        audit_profile = PRODUCTION_AUDIT_SAMPLING_PROFILE
    else:
        expansion_profile, audit_profile = load_expansion_batch_profile(
            args.authority_profile
        )

    census = build_expansion_census(
        fact_bundles_path=args.fact_bundles,
        task_text_candidates_path=args.task_text_candidates,
        reviewed_packet_path=args.reviewed_packet,
        existing_semantic_rows_path=args.existing_semantic_rows,
        id_mappings_path=args.id_mappings,
        profile=expansion_profile,
    )
    audit = build_stratified_audit_packet(
        proposal_rows=census.proposal_rows,
        reviewed_packet_path=args.reviewed_packet,
        audit_reviewed_packet_path=args.audit_reviewed_packet,
        source_root=args.source_root,
        profile=audit_profile,
    )
    ledger = write_expansion_outputs(
        census_result=census,
        audit_result=audit,
        output_dir=args.output_dir,
    )
    payload = {"summary": {"census": census.summary, "audit": audit.summary}, "hash_ledger": ledger}
    print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
    return payload


if __name__ == "__main__":
    main()
