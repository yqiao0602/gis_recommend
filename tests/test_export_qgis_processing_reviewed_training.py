from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys

import pytest


SCRIPT_PATH = (
    Path(__file__).resolve().parents[1]
    / "scripts"
    / "export_qgis_processing_reviewed_training.py"
)


def _module():
    assert SCRIPT_PATH.is_file(), "reviewed Processing exporter is not implemented"
    spec = importlib.util.spec_from_file_location(
        "export_qgis_processing_reviewed_training", SCRIPT_PATH
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _candidate(candidate_id: str, dedup_status: str = "canonical_candidate") -> dict:
    return {
        "candidate_id": candidate_id,
        "candidate_lane": "split_single_step",
        "record_id": f"record-{candidate_id}",
        "unit_id": f"unit-{candidate_id}",
        "source_sha256": hashlib.sha256(candidate_id.encode()).hexdigest(),
        "source_authority_key": f"body:{candidate_id}",
        "source_path": f"/home/yll/{candidate_id}.py",
        "source_snippet": "1 | processing.run('native:buffer', params)",
        "review_split": "calibration",
        "dedup_status": dedup_status,
        "dedup_duplicate_of": "prior" if dedup_status != "canonical_candidate" else "",
        "operator_ids": ["native:buffer"],
        "mapped_l3_chain": ["L3_02_01_01"],
        "call_sites": [
            {
                "ordinal": 1,
                "operator_id": "native:buffer",
                "line_start": 1,
                "line_end": 1,
            }
        ],
        "dependency_edges": [],
        "workflow_unit_scope": "local_subworkflow",
        "task_name": f"buffer {candidate_id}",
        "task_description": f"buffer the input for {candidate_id}",
        "parameter_facts": [{"DISTANCE": 10}],
        "known_omissions": ["outside_explicit_processing_dag_not_described"],
    }


def _decision(module, row: dict) -> dict:
    return {
        "candidate_id": row["candidate_id"],
        "record_id": row["record_id"],
        "source_sha256": row["source_sha256"],
        "source_authority_key": row["source_authority_key"],
        "unit_id": row["unit_id"],
        "candidate_payload_sha256": module._record_sha256(row),
        "boundary_decision": "pass",
        "operator_decision": "pass",
        "l3_decision": "pass",
        "description_decision": "pass",
    }


def test_exports_only_hash_bound_canonical_rows_and_suppresses_cross_pool_duplicates() -> None:
    module = _module()
    accepted = _candidate("accepted")
    cross_pool_duplicate = _candidate("cross-pool")
    duplicate = _candidate("duplicate", "duplicate_training_pair")
    existing = {
        **cross_pool_duplicate,
        "sample_id": "existing-cross-pool",
        "operator_sequence": cross_pool_duplicate["operator_ids"],
        "l3_code_sequence": cross_pool_duplicate["mapped_l3_chain"],
    }

    training, ledger, summary = module.build_training_package(
        review_rows=[accepted, cross_pool_duplicate, duplicate],
        decisions=[
            _decision(module, accepted),
            _decision(module, cross_pool_duplicate),
        ],
        existing_rows=[existing],
        code_to_id={"L3_02_01_01": 8},
    )

    assert [row["candidate_id"] for row in training] == ["accepted"]
    assert training[0]["l3_sequence"] == [-3, 8, -4]
    assert training[0]["taxonomy_profile"] == "stable110_authority_v1"
    assert training[0]["source_verification"] == "verified_sha256"
    assert training[0]["source_replay_authority"] == "qgis_processing_second_batch_v5"
    assert training[0]["split"] == "train_only_qgis_processing_review_v1"
    assert training[0]["validation_eligible"] is False
    assert training[0]["test_eligible"] is False
    assert training[0]["production_merge"] == "not_granted"
    assert {row["export_decision"] for row in ledger} == {
        "accepted_train_only",
        "cross_pool_duplicate",
        "dedup_exclusion",
    }
    assert summary["reviewed_canonical_rows"] == 2
    assert summary["train_only_rows"] == 1


def test_rejects_tampered_or_missing_adjudication() -> None:
    module = _module()
    candidate = _candidate("accepted")
    decision = _decision(module, candidate)

    with pytest.raises(ValueError, match="payload SHA256"):
        module.build_training_package(
            review_rows=[{**candidate, "task_description": "tampered"}],
            decisions=[decision],
            existing_rows=[],
            code_to_id={"L3_02_01_01": 8},
        )

    with pytest.raises(ValueError, match="missing adjudication"):
        module.build_training_package(
            review_rows=[candidate],
            decisions=[],
            existing_rows=[],
            code_to_id={"L3_02_01_01": 8},
        )


def test_script_is_directly_executable() -> None:
    result = subprocess.run(
        [sys.executable, str(SCRIPT_PATH), "--help"],
        cwd=SCRIPT_PATH.parents[1],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr


def test_candidate_replay_package_is_hash_bound(tmp_path: Path) -> None:
    module = _module()
    candidate_path = tmp_path / "candidate_batch_v1.jsonl"
    candidate_path.write_text(
        json.dumps(_candidate("replayed"), sort_keys=True) + "\n",
        encoding="utf-8",
    )
    ledger_path = tmp_path / "hash_ledger_v1.json"
    ledger_path.write_text(
        json.dumps(
            {
                "schema": "gis_recommend.hash_ledger.v1",
                "artifacts": {
                    candidate_path.name: {
                        "sha256": hashlib.sha256(candidate_path.read_bytes()).hexdigest()
                    }
                },
            }
        ),
        encoding="utf-8",
    )

    assert module._validate_candidate_package(tmp_path) == candidate_path

    candidate_path.write_text("tampered\n", encoding="utf-8")
    with pytest.raises(ValueError, match="candidate package SHA256 mismatch"):
        module._validate_candidate_package(tmp_path)


def test_rule_authority_only_generalizes_dual_split_exact_signatures() -> None:
    module = _module()
    calibration = _candidate("calibration")
    holdout = {**_candidate("holdout"), "review_split": "holdout"}
    covered = _candidate("covered")
    uncovered = {**_candidate("uncovered"), "description_policy": "different"}

    training, ledger, summary = module.build_training_package(
        review_rows=[calibration, holdout],
        candidate_rows=[calibration, holdout, covered, uncovered],
        decisions=[
            _decision(module, calibration),
            _decision(module, holdout),
        ],
        existing_rows=[],
        code_to_id={"L3_02_01_01": 8},
        rule_authority={
            "status": "granted_source_disjoint_zero_failure",
            "signature_fields": list(module.RULE_SIGNATURE_FIELDS),
        },
    )

    assert {row["candidate_id"] for row in training} == {
        "calibration",
        "holdout",
        "covered",
    }
    decisions = {row["candidate_id"]: row["export_decision"] for row in ledger}
    assert decisions["covered"] == "accepted_train_only"
    assert decisions["uncovered"] == "rule_signature_deferred"
    assert summary["rule_authority_admitted_rows"] == 1


def test_rule_authority_keeps_undecided_review_signatures_deferred() -> None:
    module = _module()
    calibration = _candidate("calibration")
    holdout = {**_candidate("holdout"), "review_split": "holdout"}
    deferred = {
        **_candidate("deferred"),
        "description_policy": "unapproved-policy",
        "review_split": "holdout",
    }

    training, ledger, summary = module.build_training_package(
        review_rows=[calibration, holdout, deferred],
        candidate_rows=[calibration, holdout, deferred],
        decisions=[
            _decision(module, calibration),
            _decision(module, holdout),
        ],
        existing_rows=[],
        code_to_id={"L3_02_01_01": 8},
        rule_authority={
            "status": "granted_source_disjoint_zero_failure",
            "signature_fields": list(module.RULE_SIGNATURE_FIELDS),
        },
    )

    assert {row["candidate_id"] for row in training} == {
        "calibration",
        "holdout",
    }
    deferred_entry = next(
        row for row in ledger if row["candidate_id"] == "deferred"
    )
    assert deferred_entry["export_decision"] == "rule_signature_deferred"
    assert summary["rule_signature_deferred_rows"] == 1


def test_rule_replay_ledger_derives_record_unit_for_direct_candidates() -> None:
    module = _module()
    calibration = _candidate("calibration")
    holdout = {**_candidate("holdout"), "review_split": "holdout"}
    direct = {
        **_candidate("direct"),
        "candidate_lane": "direct",
        "workflow_unit_scope": "whole_processing_scope",
    }
    direct.pop("unit_id")

    training, ledger, summary = module.build_training_package(
        review_rows=[calibration, holdout],
        candidate_rows=[calibration, holdout, direct],
        decisions=[
            _decision(module, calibration),
            _decision(module, holdout),
        ],
        existing_rows=[],
        code_to_id={"L3_02_01_01": 8},
        rule_authority={
            "status": "granted_source_disjoint_zero_failure",
            "signature_fields": list(module.RULE_SIGNATURE_FIELDS),
        },
    )

    direct_ledger = next(row for row in ledger if row["candidate_id"] == "direct")
    assert {row["candidate_id"] for row in training} == {"calibration", "holdout"}
    assert direct_ledger["unit_id"] == "record:record-direct"
    assert direct_ledger["export_decision"] == "rule_signature_deferred"
    assert summary["rule_signature_deferred_rows"] == 1


def test_adjudicated_direct_candidate_uses_record_unit_identity() -> None:
    module = _module()
    direct = {
        **_candidate("direct-adjudicated"),
        "candidate_lane": "direct",
        "workflow_unit_scope": "whole_processing_scope",
    }
    direct.pop("unit_id")
    decision = {
        **_decision(module, {**direct, "unit_id": "unused"}),
        "unit_id": f"record:{direct['record_id']}",
        "candidate_payload_sha256": module._record_sha256(direct),
    }

    training, _, _ = module.build_training_package(
        review_rows=[direct],
        decisions=[decision],
        existing_rows=[],
        code_to_id={"L3_02_01_01": 8},
    )

    assert training[0]["unit_id"] == f"record:{direct['record_id']}"


def test_export_records_explicit_taxonomy_and_source_replay_authorities() -> None:
    module = _module()
    candidate = _candidate("stable118")

    training, _, summary = module.build_training_package(
        review_rows=[candidate],
        decisions=[_decision(module, candidate)],
        existing_rows=[],
        code_to_id={"L3_02_01_01": 8},
        taxonomy_profile="stable118_authority_v1",
        source_replay_authority="qgis_processing_stable118_structural_delta_batch_v1",
    )

    assert training[0]["taxonomy_profile"] == "stable118_authority_v1"
    assert (
        training[0]["source_replay_authority"]
        == "qgis_processing_stable118_structural_delta_batch_v1"
    )
    assert summary["taxonomy_profile"] == "stable118_authority_v1"
