from scripts.build_qgis_seed_subworkflow_review_packet import build_packet


def test_packet_preserves_parent_lineage_and_leaves_decision_blank() -> None:
    packet = build_packet(
        [
            {
                "candidate_id": "candidate-1",
                "training_admission": "not_granted_candidate_only",
                "parent_workflow_id": "parent-1",
                "seed_source_sha256": "a" * 64,
                "seed_source_path": "/source.py",
                "seed_source_span": {"call_sites": []},
                "seed_task_description": "Parent task",
                "task_description": "Subworkflow task",
                "operator_sequence": ["native:buffer", "native:clip"],
                "l3_code_sequence": ["L3_A", "L3_B"],
                "subworkflow_input_types": ["vector"],
                "subworkflow_output_types": ["vector"],
                "split_group_key": "parent_source_sha256:test",
            }
        ]
    )

    assert packet[0]["parent_workflow_id"] == "parent-1"
    assert packet[0]["split_group_key"] == "parent_source_sha256:test"
    assert packet[0]["decision"] == ""


def test_packet_rejects_non_review_only_input() -> None:
    try:
        build_packet([{"candidate_id": "bad", "training_admission": "granted_train_only"}])
    except ValueError as error:
        assert "not review-only" in str(error)
    else:
        raise AssertionError("expected review-only admission guard")
