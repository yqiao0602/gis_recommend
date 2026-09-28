#!/usr/bin/env python3
"""Admit a gated GEE proposal population after a passing sampling audit."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import shutil
import tempfile
from typing import Any, Iterable

from gis_recommend.data.gee_workflow_train_schema import (
    GeeWorkflowTrainRow,
    TRAINING_ADMISSION,
    validate_stable_94_mapping,
    validate_workflow_train_row,
)
from scripts.evaluate_gee_complete_workflow_expansion_audit import (
    FIDELITY_FIELDS,
    FrozenAuditEvaluationProfile,
    _load_json,
    _load_jsonl,
    evaluate_sampling_audit,
)
from scripts.export_gee_complete_workflow_training_package import (
    V4_MAX_SEQUENCE_LENGTH,
    _loader_row,
    _normalized_text,
    _record_sha256,
    _sample_id,
)


@dataclass(frozen=True)
class ExpansionTrainingBatchResult:
    admission_manifest: list[dict[str, Any]]
    new_semantic_rows: list[dict[str, Any]]
    new_v4_rows: list[dict[str, Any]]
    new_length_sidecar: list[dict[str, Any]]
    duplicate_sidecar: list[dict[str, Any]]
    combined_semantic_rows: list[dict[str, Any]]
    combined_v4_rows: list[dict[str, Any]]
    combined_length_sidecar: list[dict[str, Any]]
    summary: dict[str, Any]


def _identity(row: dict[str, Any]) -> tuple[str, str]:
    source_sha = str(row.get("source_sha256") or "")
    workflow_id = str(row.get("workflow_id") or "")
    if len(source_sha) != 64 or not workflow_id:
        raise ValueError("row requires source_sha256 and workflow_id")
    return source_sha, workflow_id


def _index(rows: Iterable[dict[str, Any]], label: str) -> dict[tuple[str, str], dict[str, Any]]:
    result: dict[tuple[str, str], dict[str, Any]] = {}
    for row in rows:
        key = _identity(row)
        if key in result:
            raise ValueError(f"duplicate {label} identity: {key}")
        result[key] = row
    return result


def _dedup_key(row: dict[str, Any]) -> tuple[str, str, tuple[str, ...]]:
    return (
        _normalized_text(row.get("task_name")),
        _normalized_text(row.get("task_description")),
        tuple(str(value) for value in row.get("l3_sequence") or []),
    )


def _validate_sampling_authority(
    *,
    reviewed_rows: list[dict[str, Any]],
    evaluation: dict[str, Any],
    proposal_index: dict[tuple[str, str], dict[str, Any]],
    minimum_audit_rows: int,
) -> None:
    if evaluation.get("decision") != "passed_for_larger_source_disjoint_replay":
        raise ValueError("sampling evaluation does not authorize batch admission")
    if len(reviewed_rows) < minimum_audit_rows:
        raise ValueError("sampling audit does not meet the minimum reviewed-row count")
    expected = len(reviewed_rows)
    count_fields = {
        "reviewed_rows": expected,
        "pass_rows": expected,
        "fail_rows": 0,
        "critical_failure_rows": 0,
    }
    for field, value in count_fields.items():
        if evaluation.get(field) != value:
            raise ValueError(f"sampling evaluation {field} must equal {value}")
    if float(evaluation.get("point_precision", 0.0)) < 0.95:
        raise ValueError("sampling audit point precision is below 0.95")
    if float(evaluation.get("wilson_95_lower", 0.0)) < 0.85:
        raise ValueError("sampling audit Wilson lower bound is below 0.85")

    reviewed_index = _index(reviewed_rows, "reviewed audit")
    if not set(reviewed_index) <= set(proposal_index):
        raise ValueError("reviewed audit contains identities outside the proposal authority")
    if len({source_sha for source_sha, _ in reviewed_index}) != len(reviewed_index):
        raise ValueError("sampling audit must be source-disjoint")
    for key, row in reviewed_index.items():
        if row.get("human_decision") != "pass":
            raise ValueError(f"reviewed audit decision is not pass: {key}")
        if row.get("human_critical_failure") != "no":
            raise ValueError(f"reviewed audit contains a critical failure: {key}")
        if any(row.get(field) != "pass" for field in FIDELITY_FIELDS):
            raise ValueError(f"reviewed audit fidelity is not fully passed: {key}")


def _admission_row(proposal: dict[str, Any], evaluation: dict[str, Any]) -> dict[str, Any]:
    source_sha, workflow_id = _identity(proposal)
    row = {
        "schema": "gis_recommend.gee_expansion_batch_admission.v1",
        "source_sha256": source_sha,
        "source_path": str(proposal["source_path"]),
        "workflow_id": workflow_id,
        "workflow_key": [source_sha, workflow_id],
        "proposal_id": str(proposal["proposal_id"]),
        "proposal_row_sha256": _record_sha256(proposal),
        "decision": "pass",
        "admission_basis": "passed_source_disjoint_stratified_sampling_audit",
        "audit_evaluation_sha256": _record_sha256(evaluation),
        "training_admission": TRAINING_ADMISSION,
        "validation_eligible": False,
        "test_eligible": False,
        "production_merge": "not_granted",
    }
    row["admission_row_sha256"] = _record_sha256(row)
    return row


def _semantic_row(proposal: dict[str, Any], admission: dict[str, Any]) -> dict[str, Any]:
    row = GeeWorkflowTrainRow(
        sample_id=_sample_id(str(proposal["source_sha256"]), str(proposal["workflow_id"])),
        source_sha256=str(proposal["source_sha256"]),
        source_path=str(proposal["source_path"]),
        workflow_id=str(proposal["workflow_id"]),
        exact_dag_fingerprint=str(proposal["exact_dag_fingerprint"]),
        task_name=str(proposal["task_name"]),
        task_description=str(proposal["task_description"]),
        operator_sequence=tuple(str(value) for value in proposal["operator_sequence"]),
        l3_sequence=tuple(str(value) for value in proposal["l3_sequence"]),
        fact_bundle_sha256=str(proposal["fact_bundle_sha256"]),
        task_text_candidate_sha256=str(proposal["task_text_candidate_sha256"]),
        adjudication_row_sha256=str(admission["admission_row_sha256"]),
        known_omissions=tuple(str(value) for value in proposal.get("known_omissions") or []),
    ).to_dict()
    validate_workflow_train_row(row)
    return row


def _validate_proposal(row: dict[str, Any], l3_to_id: dict[str, int]) -> None:
    if row.get("schema") != "gis_recommend.gee_workflow_expansion_proposal.v1":
        raise ValueError("proposal schema drift")
    if row.get("proposal_status") != "pending_sampling_audit":
        raise ValueError("proposal status drift")
    if row.get("training_admission") != "not_granted_pending_sampling_audit":
        raise ValueError("proposal training admission drift")
    if row.get("validation_eligible") is not False or row.get("test_eligible") is not False:
        raise ValueError("proposal validation/test permission drift")
    if row.get("production_merge") != "not_granted":
        raise ValueError("proposal production permission drift")
    operators = row.get("operator_sequence")
    l3_codes = row.get("l3_sequence")
    if not isinstance(operators, list) or not isinstance(l3_codes, list) or not operators:
        raise ValueError("proposal requires non-empty operator and L3 sequences")
    if len(operators) != len(l3_codes):
        raise ValueError("proposal operator/L3 sequence length mismatch")
    missing = sorted(set(l3_codes) - set(l3_to_id))
    if missing:
        raise ValueError(f"proposal contains unmapped L3 codes: {missing}")
    if row.get("workflow_key") != list(_identity(row)):
        raise ValueError("proposal workflow_key drift")


def build_expansion_training_batch(
    *,
    proposal_rows: list[dict[str, Any]],
    reviewed_audit_rows: list[dict[str, Any]],
    audit_evaluation: dict[str, Any],
    existing_semantic_rows: list[dict[str, Any]],
    l3_to_id: dict[str, int],
    minimum_audit_rows: int = 30,
) -> ExpansionTrainingBatchResult:
    l3_to_id = validate_stable_94_mapping(l3_to_id)
    proposal_index = _index(proposal_rows, "proposal")
    if not proposal_index:
        raise ValueError("proposal authority is empty")
    for row in proposal_index.values():
        _validate_proposal(row, l3_to_id)
    _validate_sampling_authority(
        reviewed_rows=reviewed_audit_rows,
        evaluation=audit_evaluation,
        proposal_index=proposal_index,
        minimum_audit_rows=minimum_audit_rows,
    )

    for row in existing_semantic_rows:
        validate_workflow_train_row(row)
    existing_sources = {str(row["source_sha256"]) for row in existing_semantic_rows}
    proposal_sources = {source_sha for source_sha, _ in proposal_index}
    overlap = sorted(existing_sources & proposal_sources)
    if overlap:
        raise ValueError(f"proposal source overlap with existing training authority: {overlap}")

    seen = {_dedup_key(row): str(row["sample_id"]) for row in existing_semantic_rows}
    admissions: list[dict[str, Any]] = []
    new_semantic: list[dict[str, Any]] = []
    duplicates: list[dict[str, Any]] = []
    for key in sorted(proposal_index):
        proposal = proposal_index[key]
        admission = _admission_row(proposal, audit_evaluation)
        admissions.append(admission)
        semantic = _semantic_row(proposal, admission)
        dedup_key = _dedup_key(semantic)
        canonical = seen.get(dedup_key)
        if canonical is not None:
            duplicates.append(
                {
                    "schema": "gis_recommend.gee_expansion_batch_duplicate.v1",
                    "source_sha256": key[0],
                    "workflow_id": key[1],
                    "duplicate_sample_id": semantic["sample_id"],
                    "canonical_sample_id": canonical,
                    "reason": "normalized task name, description, and L3 sequence duplicate",
                    "training_admission": "not_granted_duplicate",
                }
            )
            continue
        seen[dedup_key] = str(semantic["sample_id"])
        new_semantic.append(semantic)

    combined_semantic = [*existing_semantic_rows, *new_semantic]
    if len({str(row["sample_id"]) for row in combined_semantic}) != len(combined_semantic):
        raise ValueError("combined semantic rows contain duplicate sample IDs")

    new_loader = [_loader_row(row, l3_to_id) for row in new_semantic]
    combined_loader = [_loader_row(row, l3_to_id) for row in combined_semantic]
    new_v4 = [row for row in new_loader if row["sequence_fit"]["fits_v4_100"]]
    new_length = [row for row in new_loader if not row["sequence_fit"]["fits_v4_100"]]
    combined_v4 = [row for row in combined_loader if row["sequence_fit"]["fits_v4_100"]]
    combined_length = [row for row in combined_loader if not row["sequence_fit"]["fits_v4_100"]]

    counts = {
        "audit_reviewed_rows": len(reviewed_audit_rows),
        "authorized_population_rows": len(proposal_rows),
        "new_semantic_rows": len(new_semantic),
        "new_v4_100_rows": len(new_v4),
        "new_length_sidecar_rows": len(new_length),
        "new_duplicate_rows": len(duplicates),
        "existing_semantic_rows": len(existing_semantic_rows),
        "combined_semantic_rows": len(combined_semantic),
        "combined_v4_100_rows": len(combined_v4),
        "combined_length_sidecar_rows": len(combined_length),
    }
    summary = {
        "schema": "gis_recommend.gee_expansion_training_batch_summary.v1",
        "admission_policy": "deterministic_gate_plus_source_disjoint_stratified_sampling_v1",
        "audit_decision": audit_evaluation["decision"],
        "counts": counts,
        "training_admission": TRAINING_ADMISSION,
        "split": "train_only_gee_complete_workflow_v1",
        "validation_eligible": False,
        "test_eligible": False,
        "production_merge": "not_granted",
        "training_run": False,
    }
    return ExpansionTrainingBatchResult(
        admission_manifest=admissions,
        new_semantic_rows=new_semantic,
        new_v4_rows=new_v4,
        new_length_sidecar=new_length,
        duplicate_sidecar=duplicates,
        combined_semantic_rows=combined_semantic,
        combined_v4_rows=combined_v4,
        combined_length_sidecar=combined_length,
        summary=summary,
    )


def _jsonl(rows: Iterable[dict[str, Any]]) -> bytes:
    return b"".join(
        (json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")
        for row in rows
    )


def _loader_payload(rows: list[dict[str, Any]]) -> bytes:
    payload = {
        "labeled_workflows": rows,
        "splits": {"train_indices": list(range(len(rows))), "val_indices": [], "test_indices": []},
    }
    return (json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")


def write_expansion_training_batch(
    result: ExpansionTrainingBatchResult,
    *,
    output_dir: Path,
    authority_paths: dict[str, Path],
) -> dict[str, Any]:
    output_dir = Path(output_dir)
    if output_dir.exists():
        raise FileExistsError(f"output directory already exists: {output_dir}")
    artifacts = {
        "admission_manifest.jsonl": _jsonl(result.admission_manifest),
        "new_semantic_train_rows.jsonl": _jsonl(result.new_semantic_rows),
        "new_train_v4_100.json": _loader_payload(result.new_v4_rows),
        "new_length_sidecar.jsonl": _jsonl(result.new_length_sidecar),
        "duplicate_sidecar.jsonl": _jsonl(result.duplicate_sidecar),
        "combined_semantic_train_rows.jsonl": _jsonl(result.combined_semantic_rows),
        "combined_train_v4_100.json": _loader_payload(result.combined_v4_rows),
        "combined_length_sidecar.jsonl": _jsonl(result.combined_length_sidecar),
        "summary.json": (json.dumps(result.summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8"),
    }
    ledger = {
        "schema": "gis_recommend.gee_expansion_training_batch_hash_ledger.v1",
        "authority_sha256": {
            name: hashlib.sha256(Path(path).read_bytes()).hexdigest()
            for name, path in sorted(authority_paths.items())
        },
        "artifact_sha256": {
            name: hashlib.sha256(content).hexdigest() for name, content in sorted(artifacts.items())
        },
    }
    artifacts["hash_ledger.json"] = (json.dumps(ledger, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")
    output_dir.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=f".{output_dir.name}.staging-", dir=output_dir.parent))
    try:
        for name, content in artifacts.items():
            (staging / name).write_bytes(content)
        os.replace(staging, output_dir)
    except BaseException:
        shutil.rmtree(staging, ignore_errors=True)
        raise
    return ledger


def _load_mapping(path: Path) -> dict[str, int]:
    payload = _load_json(path)
    return validate_stable_94_mapping(payload.get("l3") or {})


def main(argv: list[str] | None = None) -> dict[str, Any]:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--proposal-candidates", type=Path, required=True)
    parser.add_argument("--original-audit", type=Path, required=True)
    parser.add_argument("--reviewed-audit", type=Path, required=True)
    parser.add_argument("--source-manifest", type=Path, required=True)
    parser.add_argument("--reviewed-packet", type=Path, required=True)
    parser.add_argument("--expansion-hash-ledger", type=Path, required=True)
    parser.add_argument("--evaluation-profile", type=Path, required=True)
    parser.add_argument("--existing-semantic-rows", type=Path, required=True)
    parser.add_argument("--id-mappings", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args(argv)

    profile = FrozenAuditEvaluationProfile(**_load_json(args.evaluation_profile))
    evaluation = evaluate_sampling_audit(
        original_audit_path=args.original_audit,
        reviewed_audit_path=args.reviewed_audit,
        source_manifest_path=args.source_manifest,
        reviewed_packet_path=args.reviewed_packet,
        expansion_hash_ledger_path=args.expansion_hash_ledger,
        profile=profile,
    )
    result = build_expansion_training_batch(
        proposal_rows=_load_jsonl(args.proposal_candidates),
        reviewed_audit_rows=evaluation.reviewed_rows,
        audit_evaluation=evaluation.summary,
        existing_semantic_rows=_load_jsonl(args.existing_semantic_rows),
        l3_to_id=_load_mapping(args.id_mappings),
    )
    authority_paths = {
        "proposal_candidates": args.proposal_candidates,
        "original_audit": args.original_audit,
        "reviewed_audit": args.reviewed_audit,
        "source_manifest": args.source_manifest,
        "reviewed_packet": args.reviewed_packet,
        "expansion_hash_ledger": args.expansion_hash_ledger,
        "evaluation_profile": args.evaluation_profile,
        "existing_semantic_rows": args.existing_semantic_rows,
        "mapping": args.id_mappings,
    }
    ledger = write_expansion_training_batch(result, output_dir=args.output_dir, authority_paths=authority_paths)
    payload = {"summary": result.summary, "hash_ledger": ledger}
    print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
    return payload


if __name__ == "__main__":
    main()
