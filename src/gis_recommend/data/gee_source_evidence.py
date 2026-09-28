"""Versioned evidence contract for source-grounded GEE call extraction."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
import re
from typing import Any


SCHEMA = "gis_recommend.gee_source_evidence.v1"
CLASSIFICATIONS = frozenset({"core", "io", "presentation", "support", "unresolved"})
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


@dataclass(frozen=True)
class CallEvidence:
    ordinal: int
    raw_callee: str | None
    classification: str
    resolution: str
    scope: str
    context: str
    receiver_type: str | None = None
    source_location: dict[str, int] | None = None
    flags: tuple[str, ...] = ()


@dataclass
class GeeSourceEvidence:
    source_path: str
    source_sha256: str
    extractor_version: str
    ordered_calls: list[CallEvidence] = field(default_factory=list)
    core_operator_chain: list[int] = field(default_factory=list)
    io_contract: list[int] = field(default_factory=list)
    presentation_actions: list[int] = field(default_factory=list)
    support_calls: list[int] = field(default_factory=list)
    unresolved_calls: list[int] = field(default_factory=list)
    quality_flags: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        validate_evidence(self)
        payload = asdict(self)
        payload["schema"] = SCHEMA
        return {"schema": payload.pop("schema"), **payload}


def validate_evidence(evidence: GeeSourceEvidence) -> None:
    if not _SHA256_RE.fullmatch(evidence.source_sha256):
        raise ValueError("source_sha256 must be a lowercase 64-character SHA256")
    if not evidence.source_path:
        raise ValueError("source_path must not be empty")
    if not evidence.extractor_version:
        raise ValueError("extractor_version must not be empty")

    ordinals: set[int] = set()
    for call in evidence.ordered_calls:
        if call.ordinal in ordinals:
            raise ValueError(f"duplicate ordinal: {call.ordinal}")
        ordinals.add(call.ordinal)
        if call.classification not in CLASSIFICATIONS:
            raise ValueError(f"unknown classification: {call.classification}")

    layers = {
        "core_operator_chain": evidence.core_operator_chain,
        "io_contract": evidence.io_contract,
        "presentation_actions": evidence.presentation_actions,
        "support_calls": evidence.support_calls,
        "unresolved_calls": evidence.unresolved_calls,
    }
    expected_classification = {
        "core_operator_chain": "core",
        "io_contract": "io",
        "presentation_actions": "presentation",
        "support_calls": "support",
        "unresolved_calls": "unresolved",
    }
    calls_by_ordinal = {call.ordinal: call for call in evidence.ordered_calls}
    referenced: set[int] = set()
    for layer_name, references in layers.items():
        for ordinal in references:
            if ordinal not in ordinals:
                raise ValueError(f"{layer_name} references unknown call ordinal: {ordinal}")
            actual = calls_by_ordinal[ordinal].classification
            expected = expected_classification[layer_name]
            if actual != expected:
                raise ValueError(
                    f"classification mismatch for ordinal {ordinal}: {layer_name} expects {expected}, got {actual}"
                )
            if ordinal in referenced:
                raise ValueError(f"call ordinal appears in multiple layers: {ordinal}")
            referenced.add(ordinal)
    missing = ordinals.difference(referenced)
    if missing:
        raise ValueError(f"ordered calls missing from classification layers: {sorted(missing)}")
