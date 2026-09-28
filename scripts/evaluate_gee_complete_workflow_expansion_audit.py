#!/usr/bin/env python3
"""Evaluate the source-disjoint GEE expansion audit without admitting data."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import hashlib
import json
import math
from pathlib import Path
from typing import Any
from collections.abc import Mapping

from scripts.export_gee_complete_workflow_training_package import _identity, _index


HUMAN_FIELDS = (
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
FIDELITY_FIELDS = HUMAN_FIELDS[:6]
VALID_FIDELITY = frozenset({"pass", "fail"})
VALID_CRITICAL = frozenset({"yes", "no"})
VALID_DECISIONS = frozenset({"pass", "fail"})
WILSON_Z_95 = 1.959963984540054


@dataclass(frozen=True)
class FrozenAuditEvaluationProfile:
    """Hashes and row count that define the immutable audit selection."""

    name: str
    expansion_hash_ledger_sha256: str
    original_audit_sha256: str
    source_manifest_sha256: str
    reviewed_packet_sha256: str
    expected_rows: int


@dataclass(frozen=True)
class SamplingAuditEvaluationResult:
    summary: dict[str, Any]
    reviewed_rows: list[dict[str, Any]]


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return payload


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line_number, line in enumerate(Path(path).read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        row = json.loads(line)
        if not isinstance(row, dict):
            raise ValueError(f"{path}:{line_number} must contain an object")
        rows.append(row)
    return rows


def _authority_projection(row: Mapping[str, Any]) -> dict[str, Any]:
    return {
        key: value
        for key, value in row.items()
        if key not in HUMAN_FIELDS and key != "audit_row_authority_sha256"
    }


def _record_sha256(payload: Mapping[str, Any]) -> str:
    content = (
        json.dumps(payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
        + "\n"
    ).encode("utf-8")
    return hashlib.sha256(content).hexdigest()


def _validate_profile(profile: FrozenAuditEvaluationProfile) -> None:
    for field in (
        "expansion_hash_ledger_sha256",
        "original_audit_sha256",
        "source_manifest_sha256",
        "reviewed_packet_sha256",
    ):
        value = getattr(profile, field)
        if not isinstance(value, str) or len(value) != 64 or any(
            character not in "0123456789abcdef" for character in value
        ):
            raise ValueError(f"evaluation profile has invalid {field}")
    if not isinstance(profile.expected_rows, int) or isinstance(profile.expected_rows, bool) or profile.expected_rows <= 0:
        raise ValueError("evaluation profile expected_rows must be a positive integer")


def wilson_lower_bound(successes: int, trials: int, *, z: float = WILSON_Z_95) -> float:
    """Return the two-sided Wilson lower bound for a Bernoulli proportion."""

    if not isinstance(successes, int) or not isinstance(trials, int) or successes < 0 or trials <= 0 or successes > trials:
        raise ValueError("Wilson successes/trials are invalid")
    p = successes / trials
    z_squared = z * z
    denominator = 1.0 + z_squared / trials
    center = (p + z_squared / (2.0 * trials)) / denominator
    margin = z * math.sqrt(p * (1.0 - p) / trials + z_squared / (4.0 * trials * trials)) / denominator
    return center - margin


def _validate_authority_files(
    *,
    original_audit_path: Path,
    source_manifest_path: Path,
    reviewed_packet_path: Path,
    expansion_hash_ledger_path: Path,
    profile: FrozenAuditEvaluationProfile,
) -> tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, Any]]]:
    _validate_profile(profile)
    actual = {
        "expansion_hash_ledger": _sha256_file(expansion_hash_ledger_path),
        "original_audit": _sha256_file(original_audit_path),
        "source_manifest": _sha256_file(source_manifest_path),
        "reviewed_packet": _sha256_file(reviewed_packet_path),
    }
    expected = {
        "expansion_hash_ledger": profile.expansion_hash_ledger_sha256,
        "original_audit": profile.original_audit_sha256,
        "source_manifest": profile.source_manifest_sha256,
        "reviewed_packet": profile.reviewed_packet_sha256,
    }
    for label, expected_sha in expected.items():
        if actual[label] != expected_sha:
            raise ValueError(
                f"{label} SHA256 does not match evaluation profile {profile.name}: "
                f"expected {expected_sha}, got {actual[label]}"
            )
    ledger = _load_json(expansion_hash_ledger_path)
    artifacts = ledger.get("artifact_sha256")
    if not isinstance(artifacts, dict):
        raise ValueError("expansion hash ledger lacks artifact_sha256")
    if ledger.get("audit_reviewed_packet_sha256") != actual["reviewed_packet"]:
        raise ValueError("expansion hash ledger reviewed packet hash drift")
    audit_artifact = f"audit_sample_{profile.expected_rows}.jsonl"
    if artifacts.get(audit_artifact) != actual["original_audit"]:
        raise ValueError("expansion hash ledger audit sample hash drift")
    if artifacts.get("audit_source_manifest.jsonl") != actual["source_manifest"]:
        raise ValueError("expansion hash ledger source manifest hash drift")
    original_rows = _load_jsonl(original_audit_path)
    manifest_rows = _load_jsonl(source_manifest_path)
    return ledger, original_rows, manifest_rows


def evaluate_sampling_audit(
    *,
    original_audit_path: Path,
    reviewed_audit_path: Path,
    source_manifest_path: Path,
    reviewed_packet_path: Path,
    expansion_hash_ledger_path: Path,
    profile: FrozenAuditEvaluationProfile,
) -> SamplingAuditEvaluationResult:
    """Evaluate completed human verdicts against a frozen source-backed sample."""

    _, original_rows, manifest_rows = _validate_authority_files(
        original_audit_path=Path(original_audit_path),
        source_manifest_path=Path(source_manifest_path),
        reviewed_packet_path=Path(reviewed_packet_path),
        expansion_hash_ledger_path=Path(expansion_hash_ledger_path),
        profile=profile,
    )
    reviewed_rows = _load_jsonl(Path(reviewed_audit_path))
    if len(original_rows) != profile.expected_rows or len(reviewed_rows) != profile.expected_rows:
        raise ValueError(
            f"audit row count must equal {profile.expected_rows}: "
            f"original={len(original_rows)}, reviewed={len(reviewed_rows)}"
        )
    original_index = _index(original_rows, "original audit")
    reviewed_index = _index(reviewed_rows, "reviewed audit")
    manifest_index = _index(manifest_rows, "audit source manifest")
    if set(original_index) != set(reviewed_index) or set(original_index) != set(manifest_index):
        raise ValueError("audit identity drift between original, reviewed, and source manifest")

    reviewed_sources = {
        source_sha for source_sha, _ in _index(_load_jsonl(Path(reviewed_packet_path)), "reviewed packet")
    }
    sampled_sources = {source_sha for source_sha, _ in original_index}
    overlap = sorted(sampled_sources & reviewed_sources)
    if overlap:
        raise ValueError(f"audit sample is not source-disjoint from reviewed packet: {overlap}")

    verdict_rows: list[dict[str, Any]] = []
    for key in sorted(original_index):
        original = original_index[key]
        reviewed = reviewed_index[key]
        if original.get("audit_row_authority_sha256") != _record_sha256(
            _authority_projection(original)
        ):
            raise ValueError(f"original audit authority hash drift: {key}")
        if reviewed.get("audit_row_authority_sha256") != original.get("audit_row_authority_sha256"):
            raise ValueError(f"reviewed audit authority drift: {key}")
        if _authority_projection(reviewed) != _authority_projection(original):
            raise ValueError(f"reviewed audit authority drift: {key}")
        manifest = manifest_index[key]
        for field in ("source_sha256", "source_path", "workflow_id", "risk_stratum"):
            if reviewed.get(field) != manifest.get(field) or reviewed.get(field) != original.get(field):
                raise ValueError(f"audit source manifest identity drift: {key}")
        for field in (*FIDELITY_FIELDS, "human_critical_failure", "human_decision"):
            if reviewed.get(field) == "":
                raise ValueError(f"incomplete audit verdict for {field}: {key}")
        for field in FIDELITY_FIELDS:
            if reviewed.get(field) not in VALID_FIDELITY:
                raise ValueError(f"invalid audit verdict for {field}: {key}")
        if reviewed.get("human_critical_failure") not in VALID_CRITICAL:
            raise ValueError(f"invalid audit verdict for human_critical_failure: {key}")
        if reviewed.get("human_decision") not in VALID_DECISIONS:
            raise ValueError(f"invalid audit verdict for human_decision: {key}")
        if not isinstance(reviewed.get("human_notes"), str):
            raise ValueError(f"invalid audit verdict for human_notes: {key}")
        row_passes = all(reviewed[field] == "pass" for field in FIDELITY_FIELDS) and reviewed[
            "human_critical_failure"
        ] == "no"
        if (reviewed["human_decision"] == "pass") != row_passes:
            raise ValueError(f"inconsistent audit verdict: {key}")
        verdict_rows.append(reviewed)

    pass_rows = sum(row["human_decision"] == "pass" for row in verdict_rows)
    critical_failure_rows = sum(
        row["human_critical_failure"] == "yes" for row in verdict_rows
    )
    point_precision = pass_rows / len(verdict_rows)
    wilson_lower = wilson_lower_bound(pass_rows, len(verdict_rows))
    decision = (
        "passed_for_larger_source_disjoint_replay"
        if point_precision >= 0.95
        and wilson_lower >= 0.85
        and critical_failure_rows == 0
        else "failed_rule_repair_required"
    )
    summary = {
        "schema": "gis_recommend.gee_workflow_expansion_audit_evaluation.v1",
        "evaluation_profile": profile.name,
        "reviewed_rows": len(verdict_rows),
        "pass_rows": pass_rows,
        "fail_rows": len(verdict_rows) - pass_rows,
        "point_precision": point_precision,
        "wilson_95_lower": wilson_lower,
        "critical_failure_rows": critical_failure_rows,
        "decision": decision,
        "training_rows_emitted": 0,
        "training_admission": "not_granted_audit_decision_only",
        "validation_eligible": False,
        "test_eligible": False,
        "production_merge": "not_granted",
    }
    return SamplingAuditEvaluationResult(summary=summary, reviewed_rows=verdict_rows)


def main(argv: list[str] | None = None) -> dict[str, Any]:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--original-audit", type=Path, required=True)
    parser.add_argument("--reviewed-audit", type=Path, required=True)
    parser.add_argument("--source-manifest", type=Path, required=True)
    parser.add_argument("--reviewed-packet", type=Path, required=True)
    parser.add_argument("--expansion-hash-ledger", type=Path, required=True)
    parser.add_argument("--profile", type=Path, required=True)
    args = parser.parse_args(argv)
    profile_payload = _load_json(args.profile)
    profile = FrozenAuditEvaluationProfile(**profile_payload)
    result = evaluate_sampling_audit(
        original_audit_path=args.original_audit,
        reviewed_audit_path=args.reviewed_audit,
        source_manifest_path=args.source_manifest,
        reviewed_packet_path=args.reviewed_packet,
        expansion_hash_ledger_path=args.expansion_hash_ledger,
        profile=profile,
    )
    print(json.dumps(result.summary, ensure_ascii=False, sort_keys=True))
    return result.summary


if __name__ == "__main__":
    main()
