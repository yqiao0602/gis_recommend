#!/usr/bin/env python3
"""Build a hash-bound train-only package for complete GEE output workflows."""

from __future__ import annotations

import argparse
from collections import Counter
from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import re
import sys
import tempfile
from types import MappingProxyType
from typing import Any, Iterable
from collections.abc import Mapping


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from gis_recommend.data.gee_workflow_train_schema import (  # noqa: E402
    GeeWorkflowTrainRow,
    TRAINING_ADMISSION,
    TRAINING_SCOPE,
    TRAIN_ONLY_SPLIT,
    validate_stable_94_mapping,
    validate_workflow_train_row,
)


ADJUDICATION_LEDGER_SCHEMA = "gis_recommend.gee_workflow_adjudication_ledger.v1"
ADJUDICATION_ROW_SCHEMA = "gis_recommend.gee_workflow_adjudication.v1"
PACKAGE_SUMMARY_SCHEMA = "gis_recommend.gee_complete_workflow_training_package_summary.v1"
SAMPLE_SCHEMA = "gee_complete_workflow_training_sample_v1"
PACKAGE_ID = "gee_complete_workflow_train_v1"
TASK_TYPE = "GEE_COMPLETE_OUTPUT_WORKFLOW"
START_TOKEN = -3
END_TOKEN = -4
V4_MAX_SEQUENCE_LENGTH = 100
RISK_TASK_TEXT_SCHEMA = "gis_recommend.gee_workflow_task_text_candidate.v1"
FACT_BUNDLE_SCHEMA = "gis_recommend.gee_workflow_fact_bundle.v1"
SOURCE_BACKED_TASK_TEXT_STATUS = "generated_source_backed"
SOURCE_BACKED_FACT_STATUS = "source_backed_complete"


@dataclass(frozen=True)
class FrozenAuthorityProfile:
    """External authority hashes and package counts required for admission."""

    name: str
    risk_packet_sha256: str
    fact_bundles_sha256: str
    task_text_candidates_sha256: str
    review_report_sha256: str
    mapping_sha256: str
    expected_package_counts: Mapping[str, int]
    adjudication_ledger_sha256: str = ""
    deferred_identities: frozenset[str] = frozenset()

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "expected_package_counts",
            MappingProxyType(dict(self.expected_package_counts)),
        )


PRODUCTION_AUTHORITY_PROFILE = FrozenAuthorityProfile(
    name="gee_rulefix2_complete_workflow_v1",
    risk_packet_sha256="c33b1528f98b4ed4a0a2e9a1d2dd021d6eb0f61295ea2ce38a1c02101b6a023f",
    fact_bundles_sha256="feb652c2d5ea0988a5812a5e84a88626b41b8e78a9dada555271d45b9e62e8b6",
    task_text_candidates_sha256="e804b6fbcbe333c5b365006d1e79fd811776c2d2fa099288c6a194cfadedb846",
    review_report_sha256="3755915fb35ea61628ba0c47dec2bac160ea98588370d4d1ca3508def3e7eeef",
    mapping_sha256="005699dfd438e966cda28db8891795a07b9867856951de022cd8704c6e6a4558",
    expected_package_counts={
        "adjudication_rows": 50,
        "adjudication_pass": 47,
        "adjudication_defer": 3,
        "semantic_train_rows": 47,
        "v4_100_rows": 46,
        "length_sidecar_rows": 1,
        "fail_closed_rows": 3,
        "duplicate_rows": 0,
    },
    adjudication_ledger_sha256="68eca1c40820341ceb647521a6dcfc4087f79901a956fd1f1e7612558c91b879",
    deferred_identities=frozenset(
        {
            "01573c7e4f8395b15bba72d1f7584fd4a01550eeb08bca3646c643b5d212a8a2/output-workflow-1",
            "0210773f8242a99d0da3963cb54c7ede30da8b3689af15b4f343b16cc58024cd/output-workflow-1",
            "021df39fe02ecb1abb9a9c2e97d0a6edaeb93ab0a117e029ba9812fdbd2d8629/output-workflow-1",
        }
    ),
)


@dataclass(frozen=True)
class TrainingPackageResult:
    adjudication_manifest: list[dict[str, Any]]
    semantic_train_rows: list[dict[str, Any]]
    v4_100_rows: list[dict[str, Any]]
    length_sidecar: list[dict[str, Any]]
    fail_closed_sidecar: list[dict[str, Any]]
    duplicate_sidecar: list[dict[str, Any]]
    task_type_vocab: dict[str, Any]
    summary: dict[str, Any]


def _read_bytes(path: Path) -> bytes:
    return Path(path).read_bytes()


def _sha256_bytes(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def _sha256_file(path: Path) -> str:
    return _sha256_bytes(_read_bytes(path))


def _canonical_bytes(payload: Any) -> bytes:
    return (
        json.dumps(payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
        + "\n"
    ).encode("utf-8")


def _record_sha256(payload: dict[str, Any]) -> str:
    return _sha256_bytes(_canonical_bytes(payload))


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
            raise ValueError(f"{path}:{line_number} must contain a JSON object")
        rows.append(row)
    return rows


def _identity(row: dict[str, Any]) -> tuple[str, str]:
    source_sha = str(row.get("source_sha256") or "")
    workflow_id = str(row.get("workflow_id") or "")
    if not re.fullmatch(r"[0-9a-f]{64}", source_sha) or not workflow_id:
        raise ValueError("workflow identity requires source_sha256 and workflow_id")
    return source_sha, workflow_id


def _index(rows: Iterable[dict[str, Any]], label: str) -> dict[tuple[str, str], dict[str, Any]]:
    indexed: dict[tuple[str, str], dict[str, Any]] = {}
    for row in rows:
        key = _identity(row)
        if key in indexed:
            raise ValueError(f"duplicate {label} workflow identity: {key}")
        indexed[key] = row
    return indexed


def _validate_profile_authorities(
    *,
    profile: FrozenAuthorityProfile,
    risk_packet_path: Path,
    fact_bundles_path: Path,
    task_text_candidates_path: Path,
    review_report_path: Path,
    id_mappings_path: Path,
    adjudication_ledger_path: Path,
) -> dict[str, str]:
    actual = {
        "risk_packet": _sha256_file(risk_packet_path),
        "fact_bundles": _sha256_file(fact_bundles_path),
        "task_text_candidates": _sha256_file(task_text_candidates_path),
        "review_report": _sha256_file(review_report_path),
        "mapping": _sha256_file(id_mappings_path),
        "adjudication_ledger": _sha256_file(adjudication_ledger_path),
    }
    expected = {
        "risk_packet": profile.risk_packet_sha256,
        "fact_bundles": profile.fact_bundles_sha256,
        "task_text_candidates": profile.task_text_candidates_sha256,
        "review_report": profile.review_report_sha256,
        "mapping": profile.mapping_sha256,
        "adjudication_ledger": profile.adjudication_ledger_sha256,
    }
    for role, expected_sha256 in expected.items():
        if role == "adjudication_ledger" and not expected_sha256:
            continue
        if not re.fullmatch(r"[0-9a-f]{64}", expected_sha256):
            raise ValueError(f"authority profile {profile.name} has invalid {role} SHA256")
        if actual[role] != expected_sha256:
            qualifier = (
                "production profile"
                if profile is PRODUCTION_AUTHORITY_PROFILE
                else "authority profile"
            )
            raise ValueError(
                f"{role} SHA256 does not match {qualifier} {profile.name}: "
                f"expected {expected_sha256}, got {actual[role]}"
            )
    return actual


def freeze_adjudication_manifest(
    *,
    risk_packet_path: Path,
    adjudication_ledger_path: Path,
    review_report_path: Path,
) -> list[dict[str, Any]]:
    """Expand a hash-bound closed review ledger into explicit row decisions."""

    risk_packet_path = Path(risk_packet_path)
    ledger = _load_json(Path(adjudication_ledger_path))
    if ledger.get("schema") != ADJUDICATION_LEDGER_SCHEMA:
        raise ValueError(f"adjudication ledger schema must be {ADJUDICATION_LEDGER_SCHEMA}")
    if not str(ledger.get("review_report_path") or "").strip():
        raise ValueError("adjudication ledger requires a review report path")
    if not re.fullmatch(r"[0-9a-f]{64}", str(ledger.get("review_report_sha256") or "")):
        raise ValueError("adjudication ledger review report SHA256 is invalid")
    if ledger.get("review_report_sha256") != _sha256_file(Path(review_report_path)):
        raise ValueError("review report SHA256 does not match adjudication ledger")
    actual_hash = _sha256_file(risk_packet_path)
    if ledger.get("risk_packet_sha256") != actual_hash:
        raise ValueError("risk packet SHA256 does not match adjudication ledger")
    if ledger.get("default_decision") != "pass":
        raise ValueError("closed adjudication ledger default_decision must be pass")

    risk_rows = _load_jsonl(risk_packet_path)
    risk_index = _index(risk_rows, "risk packet")
    expected = ledger.get("expected_counts") or {}
    if expected.get("rows") != len(risk_rows):
        raise ValueError("adjudication ledger expected row count mismatch")

    exceptions: dict[tuple[str, str], dict[str, Any]] = {}
    for exception in ledger.get("exceptions") or []:
        if not isinstance(exception, dict):
            raise ValueError("adjudication exceptions must be objects")
        key = _identity(exception)
        if key in exceptions:
            raise ValueError(f"duplicate adjudication exception: {key}")
        if key not in risk_index:
            raise ValueError(f"adjudication exception not in risk packet: {key}")
        risk = risk_index[key]
        if exception.get("source_path") != risk.get("source_path"):
            raise ValueError(f"adjudication exception source path mismatch: {key}")
        if exception.get("decision") != "defer_source_ambiguity":
            raise ValueError(f"unsupported adjudication exception decision: {key}")
        if not str(exception.get("reason") or "").strip():
            raise ValueError(f"adjudication exception requires a reason: {key}")
        exceptions[key] = exception

    manifest: list[dict[str, Any]] = []
    for key, risk in sorted(risk_index.items()):
        exception = exceptions.get(key)
        decision = exception["decision"] if exception else "pass"
        row = {
            "schema": ADJUDICATION_ROW_SCHEMA,
            "ledger_id": ledger.get("ledger_id"),
            "risk_packet_sha256": actual_hash,
            "review_report_path": ledger.get("review_report_path"),
            "review_report_sha256": ledger.get("review_report_sha256"),
            "source_sha256": key[0],
            "source_path": risk.get("source_path"),
            "workflow_id": key[1],
            "workflow_key": [key[0], key[1]],
            "decision": decision,
            "reason": (
                exception["reason"]
                if exception
                else "six_dimension_complete_workflow_fidelity_review_passed"
            ),
            "validation_eligible": False,
            "test_eligible": False,
            "production_merge": "not_granted",
        }
        row["adjudication_row_sha256"] = _record_sha256(row)
        manifest.append(row)

    counts = Counter(row["decision"] for row in manifest)
    if counts["pass"] != expected.get("pass"):
        raise ValueError("adjudication pass count mismatch")
    if counts["defer_source_ambiguity"] != expected.get("defer_source_ambiguity"):
        raise ValueError("adjudication defer count mismatch")
    if len(exceptions) != counts["defer_source_ambiguity"]:
        raise ValueError("every deferred adjudication must be an explicit exception")
    return manifest


def _require_same_identity(
    key: tuple[str, str], rows: Iterable[tuple[str, dict[str, Any]]]
) -> None:
    expected_path: str | None = None
    for label, row in rows:
        if _identity(row) != key:
            raise ValueError(f"source identity mismatch in {label}: {key}")
        source_path = str(row.get("source_path") or "")
        if not source_path:
            raise ValueError(f"source identity mismatch in {label}: missing source_path")
        if expected_path is None:
            expected_path = source_path
        elif source_path != expected_path:
            raise ValueError(f"source identity mismatch in {label}: {key}")


def _fact_ids(bundle: dict[str, Any]) -> set[str]:
    result: set[str] = set()
    for field in (
        "dataset_facts",
        "temporal_facts",
        "spatial_input_facts",
        "transformation_facts",
        "output_facts",
    ):
        facts = bundle.get(field)
        if not isinstance(facts, list):
            raise ValueError(f"fact bundle {field} must be a list")
        for fact in facts:
            fact_id = fact.get("fact_id") if isinstance(fact, dict) else None
            if not isinstance(fact_id, str) or not fact_id:
                raise ValueError(f"fact bundle {field} contains a missing fact_id")
            if fact_id in result:
                raise ValueError(f"duplicate fact_id in fact bundle: {fact_id}")
            result.add(fact_id)
    return result


def validate_source_backed_candidate(
    *, fact: dict[str, Any], text: dict[str, Any]
) -> tuple[str, str]:
    """Validate one complete-workflow fact/text pair and return its identity."""

    key = _identity(fact)
    _require_same_identity(key, (("fact bundle", fact), ("task text", text)))
    if fact.get("schema") != FACT_BUNDLE_SCHEMA:
        raise ValueError(f"fact bundle schema must be {FACT_BUNDLE_SCHEMA}: {key}")
    if fact.get("fact_status") != SOURCE_BACKED_FACT_STATUS:
        raise ValueError(f"fact bundle is not source-backed complete: {key}")
    if text.get("schema") != RISK_TASK_TEXT_SCHEMA:
        raise ValueError(f"task text schema must be {RISK_TASK_TEXT_SCHEMA}: {key}")
    if text.get("task_text_status") != SOURCE_BACKED_TASK_TEXT_STATUS:
        raise ValueError(f"task text status is not source-backed: {key}")
    for label, row in (("fact bundle", fact), ("task text", text)):
        if row.get("workflow_key") != [key[0], key[1]]:
            raise ValueError(f"workflow_key mismatch in {label}: {key}")
    if not re.fullmatch(r"[0-9a-f]{64}", str(fact.get("exact_dag_fingerprint") or "")):
        raise ValueError(f"exact DAG fingerprint must be lowercase SHA256: {key}")
    if len(fact.get("output_facts") or []) != 1:
        raise ValueError(f"complete workflow requires exactly one output fact: {key}")

    omissions = fact.get("known_omissions")
    if not isinstance(omissions, list):
        raise ValueError(f"fact bundle known_omissions must be a list: {key}")
    if text.get("known_omissions") != omissions:
        raise ValueError(f"known_omissions mismatch in task text: {key}")
    calibration_stratum = fact.get("calibration_stratum")
    if not isinstance(calibration_stratum, str) or not calibration_stratum.strip():
        raise ValueError(f"fact bundle calibration_stratum is missing: {key}")
    if text.get("calibration_stratum") != calibration_stratum:
        raise ValueError(f"calibration_stratum mismatch in task text: {key}")

    fact_chain = (fact.get("operator_sequence"), fact.get("l3_sequence"))
    if (text.get("operator_sequence"), text.get("l3_sequence")) != fact_chain:
        raise ValueError(f"chain/L3 mismatch in task text: {key}")
    transformations = fact.get("transformation_facts") or []
    transformation_chain = (
        [row.get("canonical_operator") for row in transformations],
        [row.get("l3_code") for row in transformations],
    )
    if transformation_chain != fact_chain:
        raise ValueError(f"chain/L3 mismatch in transformation facts: {key}")

    available_facts = _fact_ids(fact)
    used_facts: set[str] = set()
    clauses = text.get("clauses")
    if not isinstance(clauses, list) or not clauses:
        raise ValueError(f"task text clauses must be non-empty: {key}")
    for clause in clauses:
        if not isinstance(clause, dict) or not str(clause.get("text") or "").strip():
            raise ValueError(f"task text clause is invalid: {key}")
        references = clause.get("used_fact_ids")
        if not isinstance(references, list) or not references:
            raise ValueError(f"task text clause lacks fact references: {key}")
        used_facts.update(str(value) for value in references)
    unknown = sorted(used_facts - available_facts)
    if unknown:
        raise ValueError(f"task text references unknown fact IDs for {key}: {unknown}")
    return key


def _validate_joined_authorities(
    *,
    key: tuple[str, str],
    risk: dict[str, Any],
    fact: dict[str, Any],
    text: dict[str, Any],
    adjudication: dict[str, Any],
) -> None:
    _require_same_identity(
        key,
        (
            ("risk packet", risk),
            ("fact bundle", fact),
            ("task text", text),
            ("adjudication", adjudication),
        ),
    )
    if risk.get("schema") != RISK_TASK_TEXT_SCHEMA:
        raise ValueError(f"risk packet schema must be {RISK_TASK_TEXT_SCHEMA}: {key}")
    if risk.get("task_text_status") != SOURCE_BACKED_TASK_TEXT_STATUS:
        raise ValueError(f"risk packet task_text_status is not source-backed: {key}")
    for label, row in (("risk packet", risk), ("adjudication", adjudication)):
        if row.get("workflow_key") != [key[0], key[1]]:
            raise ValueError(f"workflow_key mismatch in {label}: {key}")
    validate_source_backed_candidate(fact=fact, text=text)

    omissions = risk.get("known_omissions")
    if not isinstance(omissions, list):
        raise ValueError(f"risk packet known_omissions must be a list: {key}")
    for label, row in (("fact bundle", fact), ("task text", text)):
        if row.get("known_omissions") != omissions:
            raise ValueError(f"known_omissions mismatch in {label}: {key}")
    risk_flags = risk.get("risk_flags")
    if not isinstance(risk_flags, list) or text.get("risk_flags") != risk_flags:
        raise ValueError(f"risk_flags mismatch in task text: {key}")
    calibration_stratum = risk.get("calibration_stratum")
    if not isinstance(calibration_stratum, str) or not calibration_stratum.strip():
        raise ValueError(f"risk packet calibration_stratum is missing: {key}")
    for label, row in (("fact bundle", fact), ("task text", text)):
        if row.get("calibration_stratum") != calibration_stratum:
            raise ValueError(f"calibration_stratum mismatch in {label}: {key}")
    if text.get("clauses") != risk.get("clauses"):
        raise ValueError(f"clause lineage mismatch in task text: {key}")

    risk_chain = (risk.get("operator_sequence"), risk.get("l3_sequence"))
    for label, row in (("fact bundle", fact), ("task text", text)):
        if (row.get("operator_sequence"), row.get("l3_sequence")) != risk_chain:
            raise ValueError(f"chain/L3 mismatch in {label}: {key}")
    if text.get("task_name") != risk.get("task_name") or text.get(
        "task_description"
    ) != risk.get("task_description"):
        raise ValueError(f"task text mismatch: {key}")


def _normalized_text(value: Any) -> str:
    return " ".join(str(value).split()).casefold()


def _sample_id(source_sha256: str, workflow_id: str) -> str:
    workflow_slug = re.sub(r"[^a-z0-9]+", "_", workflow_id.casefold()).strip("_")
    identity_digest = hashlib.sha256(
        f"{source_sha256}\0{workflow_id}".encode("utf-8")
    ).hexdigest()[:16]
    return f"gee_workflow_{identity_digest}_{workflow_slug}"


def _semantic_row(
    fact: dict[str, Any], text: dict[str, Any], adjudication: dict[str, Any]
) -> dict[str, Any]:
    row = GeeWorkflowTrainRow(
        sample_id=_sample_id(str(fact["source_sha256"]), str(fact["workflow_id"])),
        source_sha256=str(fact["source_sha256"]),
        source_path=str(fact["source_path"]),
        workflow_id=str(fact["workflow_id"]),
        exact_dag_fingerprint=str(fact["exact_dag_fingerprint"]),
        task_name=str(text["task_name"]),
        task_description=str(text["task_description"]),
        operator_sequence=tuple(str(value) for value in fact["operator_sequence"]),
        l3_sequence=tuple(str(value) for value in fact["l3_sequence"]),
        fact_bundle_sha256=_record_sha256(fact),
        task_text_candidate_sha256=_record_sha256(text),
        adjudication_row_sha256=str(adjudication["adjudication_row_sha256"]),
        known_omissions=tuple(str(value) for value in text.get("known_omissions") or []),
    ).to_dict()
    validate_workflow_train_row(row)
    return row


def _loader_row(row: dict[str, Any], l3_to_id: dict[str, Any]) -> dict[str, Any]:
    codes = list(row["l3_sequence"])
    missing = sorted({code for code in codes if code not in l3_to_id})
    if missing:
        raise ValueError(f"unmapped L3 codes for {row['sample_id']}: {missing}")
    token_ids = [int(l3_to_id[code]) for code in codes]
    model_sequence = [START_TOKEN, *token_ids, END_TOKEN]
    return {
        "schema_version": SAMPLE_SCHEMA,
        "sample_id": row["sample_id"],
        "source": PACKAGE_ID,
        "source_platform": "GEE",
        "target_platform": "L3",
        "training_scope": TRAINING_SCOPE,
        "task_name": row["task_name"],
        "task_description": row["task_description"],
        "task_metadata": {
            "task_type": TASK_TYPE,
            "task_name": row["task_name"],
            "task_description": row["task_description"],
            "source_platform": "GEE",
            "target_platform": "L3",
            "training_scope": TRAINING_SCOPE,
        },
        "operator_sequence": list(row["operator_sequence"]),
        "l3_code_sequence": codes,
        "l3_token_ids": token_ids,
        "l3_sequence": model_sequence,
        "source_sha256": row["source_sha256"],
        "source_path": row["source_path"],
        "workflow_id": row["workflow_id"],
        "exact_dag_fingerprint": row["exact_dag_fingerprint"],
        "fact_bundle_sha256": row["fact_bundle_sha256"],
        "task_text_candidate_sha256": row["task_text_candidate_sha256"],
        "adjudication_row_sha256": row["adjudication_row_sha256"],
        "training_admission": TRAINING_ADMISSION,
        "split": TRAIN_ONLY_SPLIT,
        "validation_eligible": False,
        "test_eligible": False,
        "production_merge": "not_granted",
        "sample_weight": float(row["sample_weight"]),
        "known_omissions": list(row.get("known_omissions") or []),
        "sequence_fit": {
            "content_length": len(token_ids),
            "model_sequence_length": len(model_sequence),
            "v4_max_sequence_length": V4_MAX_SEQUENCE_LENGTH,
            "fits_v4_100": len(model_sequence) <= V4_MAX_SEQUENCE_LENGTH,
            "required_max_sequence_length": len(model_sequence),
        },
    }


def build_training_package(
    *,
    risk_packet_path: Path,
    fact_bundles_path: Path,
    task_text_candidates_path: Path,
    adjudication_ledger_path: Path,
    review_report_path: Path,
    id_mappings_path: Path,
    profile: FrozenAuthorityProfile = PRODUCTION_AUTHORITY_PROFILE,
) -> TrainingPackageResult:
    authority_sha256 = _validate_profile_authorities(
        profile=profile,
        risk_packet_path=Path(risk_packet_path),
        fact_bundles_path=Path(fact_bundles_path),
        task_text_candidates_path=Path(task_text_candidates_path),
        review_report_path=Path(review_report_path),
        id_mappings_path=Path(id_mappings_path),
        adjudication_ledger_path=Path(adjudication_ledger_path),
    )
    manifest = freeze_adjudication_manifest(
        risk_packet_path=Path(risk_packet_path),
        adjudication_ledger_path=Path(adjudication_ledger_path),
        review_report_path=Path(review_report_path),
    )
    risk_index = _index(_load_jsonl(Path(risk_packet_path)), "risk packet")
    fact_index = _index(_load_jsonl(Path(fact_bundles_path)), "fact bundle")
    text_index = _index(_load_jsonl(Path(task_text_candidates_path)), "task text")
    mappings = _load_json(Path(id_mappings_path))
    l3_to_id = validate_stable_94_mapping(mappings.get("l3") or {})

    if profile.deferred_identities:
        actual_deferred = frozenset(
            f"{row['source_sha256']}/{row['workflow_id']}"
            for row in manifest
            if row["decision"] != "pass"
        )
        if actual_deferred != profile.deferred_identities:
            raise ValueError(
                f"deferred identities do not match authority profile {profile.name}"
            )

    semantic_rows: list[dict[str, Any]] = []
    fail_closed: list[dict[str, Any]] = []
    duplicates: list[dict[str, Any]] = []
    dedup: dict[tuple[str, str, tuple[str, ...]], dict[str, Any]] = {}
    for adjudication in manifest:
        key = _identity(adjudication)
        risk = risk_index[key]
        if adjudication["decision"] != "pass":
            fail_closed.append(
                {
                    "schema": "gis_recommend.gee_workflow_fail_closed.v1",
                    "source_sha256": key[0],
                    "source_path": risk["source_path"],
                    "workflow_id": key[1],
                    "workflow_key": [key[0], key[1]],
                    "decision": adjudication["decision"],
                    "reason": adjudication["reason"],
                    "adjudication_row_sha256": adjudication["adjudication_row_sha256"],
                    "training_admission": "not_granted_source_ambiguity",
                    "validation_eligible": False,
                    "test_eligible": False,
                    "production_merge": "not_granted",
                }
            )
            continue
        if key not in fact_index or key not in text_index:
            raise ValueError(f"passing adjudication lacks fact or task-text authority: {key}")
        fact = fact_index[key]
        text = text_index[key]
        _validate_joined_authorities(
            key=key,
            risk=risk,
            fact=fact,
            text=text,
            adjudication=adjudication,
        )
        row = _semantic_row(fact, text, adjudication)
        dedup_key = (
            _normalized_text(row["task_name"]),
            _normalized_text(row["task_description"]),
            tuple(row["l3_sequence"]),
        )
        canonical = dedup.get(dedup_key)
        if canonical is not None:
            duplicates.append(
                {
                    "schema": "gis_recommend.gee_workflow_training_duplicate.v1",
                    "canonical_sample_id": canonical["sample_id"],
                    "duplicate_sample_id": row["sample_id"],
                    "source_sha256": row["source_sha256"],
                    "source_path": row["source_path"],
                    "workflow_id": row["workflow_id"],
                    "dedup_key": "normalized_task_name_description_plus_l3_sequence",
                    "training_admission": "not_granted_duplicate",
                }
            )
            continue
        dedup[dedup_key] = row
        semantic_rows.append(row)

    loader_rows = [_loader_row(row, l3_to_id) for row in semantic_rows]
    v4_rows = [row for row in loader_rows if row["sequence_fit"]["fits_v4_100"]]
    length_rows = [
        {
            "schema": "gis_recommend.gee_workflow_length_sidecar.v1",
            "sample_id": row["sample_id"],
            "source_sha256": row["source_sha256"],
            "source_path": row["source_path"],
            "workflow_id": row["workflow_id"],
            "content_length": row["sequence_fit"]["content_length"],
            "model_sequence_length": row["sequence_fit"]["model_sequence_length"],
            "required_max_sequence_length": row["sequence_fit"][
                "required_max_sequence_length"
            ],
            "operator_sequence": list(row["operator_sequence"]),
            "l3_code_sequence": list(row["l3_code_sequence"]),
            "training_admission": "granted_train_only_requires_long_sequence_loader",
            "validation_eligible": False,
            "test_eligible": False,
            "production_merge": "not_granted",
        }
        for row in loader_rows
        if not row["sequence_fit"]["fits_v4_100"]
    ]
    if len({_identity(row) for row in semantic_rows}) != len(semantic_rows):
        raise ValueError("semantic train rows contain duplicate workflow identities")
    if len({row["sample_id"] for row in loader_rows}) != len(loader_rows):
        raise ValueError("training sample IDs are not unique")

    counts = {
        "adjudication_rows": len(manifest),
        "adjudication_pass": sum(row["decision"] == "pass" for row in manifest),
        "adjudication_defer": sum(row["decision"] != "pass" for row in manifest),
        "semantic_train_rows": len(semantic_rows),
        "v4_100_rows": len(v4_rows),
        "length_sidecar_rows": len(length_rows),
        "fail_closed_rows": len(fail_closed),
        "duplicate_rows": len(duplicates),
    }
    expected_package = profile.expected_package_counts
    if set(expected_package) != set(counts):
        raise ValueError(f"authority profile {profile.name} must freeze all package counts")
    for field, expected_count in expected_package.items():
        if counts.get(field) != expected_count:
            raise ValueError(
                f"authority profile package count mismatch for {field}: "
                f"expected {expected_count}, got {counts.get(field)}"
            )

    task_vocab = {
        "task_type_to_id": {TASK_TYPE: 0},
        "id_to_task_type": {"0": TASK_TYPE},
        "num_types": 1,
    }
    summary = {
        "schema": PACKAGE_SUMMARY_SCHEMA,
        "package_id": PACKAGE_ID,
        "counts": counts,
        "training_scope": TRAINING_SCOPE,
        "training_admission": TRAINING_ADMISSION,
        "split": TRAIN_ONLY_SPLIT,
        "validation_eligible": False,
        "test_eligible": False,
        "production_merge": "not_granted",
        "training_run": False,
        "llm_used": False,
        "authority_profile": profile.name,
        "authority_sha256": authority_sha256,
        "mapping_authority_sha256": profile.mapping_sha256,
        "max_v4_model_sequence_length": max(
            (len(row["l3_sequence"]) for row in v4_rows), default=0
        ),
        "max_semantic_content_length": max(
            (len(row["l3_sequence"]) for row in semantic_rows), default=0
        ),
    }
    return TrainingPackageResult(
        adjudication_manifest=manifest,
        semantic_train_rows=semantic_rows,
        v4_100_rows=v4_rows,
        length_sidecar=length_rows,
        fail_closed_sidecar=fail_closed,
        duplicate_sidecar=duplicates,
        task_type_vocab=task_vocab,
        summary=summary,
    )


def _jsonl_bytes(rows: Iterable[dict[str, Any]]) -> bytes:
    return b"".join(_canonical_bytes(row) for row in rows)


def _json_bytes(payload: Any) -> bytes:
    return (json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode(
        "utf-8"
    )


def _atomic_write(path: Path, content: bytes) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("wb", dir=path.parent, delete=False) as handle:
        handle.write(content)
        temporary = Path(handle.name)
    os.replace(temporary, path)


def _report(summary: dict[str, Any]) -> bytes:
    counts = summary["counts"]
    lines = [
        "# GEE Complete-Workflow Train-Only Package",
        "",
        f"- Adjudication: {counts['adjudication_pass']} pass / {counts['adjudication_defer']} defer",
        f"- Semantic complete-workflow rows: {counts['semantic_train_rows']}",
        f"- Current V4-100 train-only rows: {counts['v4_100_rows']}",
        f"- Length sidecar: {counts['length_sidecar_rows']}",
        f"- Fail-closed sidecar: {counts['fail_closed_rows']}",
        f"- Duplicate sidecar: {counts['duplicate_rows']}",
        "- Validation/test eligibility: false",
        "- Production merge: not granted",
        "- Training run: false",
        "",
    ]
    return "\n".join(lines).encode("utf-8")


def write_outputs(
    result: TrainingPackageResult,
    *,
    output_dir: Path,
    authority_paths: dict[str, Path],
) -> dict[str, Any]:
    output_dir = Path(output_dir)
    loader_payload = {
        "labeled_workflows": result.v4_100_rows,
        "splits": {
            "train_indices": list(range(len(result.v4_100_rows))),
            "val_indices": [],
            "test_indices": [],
        },
    }
    artifacts = {
        "adjudication_manifest.jsonl": _jsonl_bytes(result.adjudication_manifest),
        "semantic_train_rows.jsonl": _jsonl_bytes(result.semantic_train_rows),
        "train_v4_100.json": _json_bytes(loader_payload),
        "length_sidecar.jsonl": _jsonl_bytes(result.length_sidecar),
        "fail_closed_sidecar.jsonl": _jsonl_bytes(result.fail_closed_sidecar),
        "duplicate_sidecar.jsonl": _jsonl_bytes(result.duplicate_sidecar),
        "task_type_vocab.json": _json_bytes(result.task_type_vocab),
        "summary.json": _json_bytes(result.summary),
        "report.md": _report(result.summary),
    }
    artifact_hashes = {name: _sha256_bytes(content) for name, content in artifacts.items()}
    ledger = {
        "schema": "gis_recommend.gee_complete_workflow_hash_ledger.v1",
        "authority_profile": result.summary["authority_profile"],
        "mapping_authority_sha256": result.summary["mapping_authority_sha256"],
        "authority_sha256": {
            name: _sha256_file(path) for name, path in sorted(authority_paths.items())
        },
        "artifact_sha256": dict(sorted(artifact_hashes.items())),
    }
    artifacts["hash_ledger.json"] = _json_bytes(ledger)
    for name, content in artifacts.items():
        _atomic_write(output_dir / name, content)
    return ledger


def main(argv: list[str] | None = None) -> dict[str, Any]:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--risk-packet", type=Path, required=True)
    parser.add_argument("--fact-bundles", type=Path, required=True)
    parser.add_argument("--task-text-candidates", type=Path, required=True)
    parser.add_argument("--adjudication-ledger", type=Path, required=True)
    parser.add_argument("--review-report", type=Path, required=True)
    parser.add_argument("--id-mappings", type=Path, default=ROOT / "outputs_v2/id_mappings_v2.json")
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args(argv)
    paths = {
        "risk_packet": args.risk_packet,
        "fact_bundles": args.fact_bundles,
        "task_text_candidates": args.task_text_candidates,
        "adjudication_ledger": args.adjudication_ledger,
        "review_report": args.review_report,
        "id_mappings": args.id_mappings,
    }
    result = build_training_package(
        risk_packet_path=args.risk_packet,
        fact_bundles_path=args.fact_bundles,
        task_text_candidates_path=args.task_text_candidates,
        adjudication_ledger_path=args.adjudication_ledger,
        review_report_path=args.review_report,
        id_mappings_path=args.id_mappings,
    )
    ledger = write_outputs(result, output_dir=args.output_dir, authority_paths=paths)
    payload = {"summary": result.summary, "hash_ledger": ledger}
    print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
    return payload


if __name__ == "__main__":
    main()
