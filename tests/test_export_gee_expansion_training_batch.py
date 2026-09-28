from __future__ import annotations

import hashlib

import pytest

from scripts.export_gee_expansion_training_batch import build_expansion_training_batch


def _sha(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _proposal(number: int) -> dict:
    source_sha = _sha(f"source-{number}")
    workflow_id = f"output-workflow-{number}"
    return {
        "schema": "gis_recommend.gee_workflow_expansion_proposal.v1",
        "proposal_id": f"proposal-{number}",
        "source_sha256": source_sha,
        "source_path": f"data/script_{number}.txt",
        "workflow_id": workflow_id,
        "workflow_key": [source_sha, workflow_id],
        "exact_dag_fingerprint": _sha(f"dag-{number}"),
        "task_name": f"Task {number}",
        "task_description": f"Apply the complete workflow {number}.",
        "operator_sequence": ["ee.image.clip"],
        "l3_sequence": ["L3_TEST_00"],
        "risk_flags": ["external_spatial_identifier"],
        "known_omissions": ["dynamic_transformation_arguments"],
        "calibration_stratum": "linear_export",
        "evidence_locations": [],
        "fact_bundle_sha256": _sha(f"fact-{number}"),
        "task_text_candidate_sha256": _sha(f"text-{number}"),
        "proposal_status": "pending_sampling_audit",
        "training_admission": "not_granted_pending_sampling_audit",
        "validation_eligible": False,
        "test_eligible": False,
        "production_merge": "not_granted",
    }


def _reviewed(proposal: dict) -> dict:
    return {
        **proposal,
        "schema": "gis_recommend.gee_workflow_expansion_audit_row.v1",
        "human_dataset_fidelity": "pass",
        "human_temporal_fidelity": "pass",
        "human_spatial_fidelity": "pass",
        "human_transformation_fidelity": "pass",
        "human_output_fidelity": "pass",
        "human_task_text_fidelity": "pass",
        "human_critical_failure": "no",
        "human_decision": "pass",
        "human_notes": "source-backed pass",
    }


def _mapping() -> dict[str, int]:
    return {f"L3_TEST_{index:02d}": index for index in range(94)}


def _evaluation(rows: int = 1) -> dict:
    return {
        "reviewed_rows": rows,
        "pass_rows": rows,
        "fail_rows": 0,
        "point_precision": 1.0,
        "wilson_95_lower": 0.9,
        "critical_failure_rows": 0,
        "decision": "passed_for_larger_source_disjoint_replay",
    }


def test_sampling_pass_authorizes_the_complete_proposal_population() -> None:
    proposals = [_proposal(1), _proposal(2)]
    result = build_expansion_training_batch(
        proposal_rows=proposals,
        reviewed_audit_rows=[_reviewed(proposals[0])],
        audit_evaluation=_evaluation(),
        existing_semantic_rows=[],
        l3_to_id=_mapping(),
        minimum_audit_rows=1,
    )

    assert len(result.admission_manifest) == 2
    assert len(result.new_semantic_rows) == 2
    assert len(result.new_v4_rows) == 2
    assert len(result.combined_v4_rows) == 2
    assert result.summary["counts"]["authorized_population_rows"] == 2
    assert result.summary["training_admission"] == "granted_train_only_gee_complete_workflow_v1"


def test_failed_sampling_evaluation_cannot_grant_batch_admission() -> None:
    proposal = _proposal(1)
    evaluation = _evaluation()
    evaluation["decision"] = "failed_rule_repair_required"
    with pytest.raises(ValueError, match="does not authorize batch admission"):
        build_expansion_training_batch(
            proposal_rows=[proposal],
            reviewed_audit_rows=[_reviewed(proposal)],
            audit_evaluation=evaluation,
            existing_semantic_rows=[],
            l3_to_id=_mapping(),
            minimum_audit_rows=1,
        )


def test_existing_source_overlap_is_fail_closed() -> None:
    proposal = _proposal(1)
    existing = {
        **proposal,
        "schema": "gis_recommend.gee_workflow_train_row.v1",
        "sample_id": "existing",
        "adjudication_row_sha256": _sha("adjudication"),
        "adjudication_decision": "pass",
        "training_admission": "granted_train_only_gee_complete_workflow_v1",
        "split": "train_only_gee_complete_workflow_v1",
        "source_platform": "GEE",
        "target_platform": "L3",
        "training_scope": "complete_output_workflow",
        "sample_weight": 0.5,
    }
    with pytest.raises(ValueError, match="source overlap"):
        build_expansion_training_batch(
            proposal_rows=[proposal],
            reviewed_audit_rows=[_reviewed(proposal)],
            audit_evaluation=_evaluation(),
            existing_semantic_rows=[existing],
            l3_to_id=_mapping(),
            minimum_audit_rows=1,
        )
