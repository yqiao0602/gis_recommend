from scripts.build_qgis_workflow_gold_silver import classify


def candidate(record_id: str, description_passed: bool = True) -> dict:
    return {
        "record_id": record_id,
        "source_sha256": record_id * 64,
        "canonical_operator_ids": ["native:buffer"],
        "mapped_l3_chain": ["L3_02_01_01"],
        "call_sites": [{"line_start": 1, "line_end": 1}],
        "task_name": "创建缓冲区",
        "task_description": "创建缓冲区",
        "description_fidelity_passed": description_passed,
        "parameter_evidence_status": "verified_source_ast",
        "mapping_complete": True,
    }


def test_structural_fidelity_candidate_is_silver_not_gold() -> None:
    rows, summary = classify([candidate("a")], [])
    assert rows[0]["quality_class"] == "silver"
    assert summary["silver_candidates"] == 1
    assert summary["gold_candidates"] == 0
    assert summary["training_rows_emitted"] == 0


def test_duplicate_is_rejected_against_baseline() -> None:
    rows, summary = classify([candidate("a")], [candidate("baseline")])
    assert rows[0]["quality_class"] == "reject"
    assert rows[0]["admission_status"] == "duplicate"
    assert summary["silver_candidates"] == 0
