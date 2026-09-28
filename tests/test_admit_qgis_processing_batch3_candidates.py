from scripts.admit_qgis_processing_batch3_candidates import build_ledger


def _row(authority: str, name: str = "任务", operator: str = "native:buffer") -> dict:
    return {
        "candidate_id": authority + name + operator,
        "candidate_rule": "recovery-connected-local-dag-v1",
        "description_fidelity_passed": True,
        "normalized_source_body_sha256": authority,
        "source_authority_key": "normalized_source_body_sha256:" + authority,
        "source_sha256": authority + "-source",
        "source_path": "/home/yll/script.py",
        "operator_ids": [operator],
        "mapped_l3_chain": ["L3_02_01_01"],
        "call_sites": [{"operator_id": operator, "line_start": 1, "line_end": 1}],
        "dependency_edges": [],
        "workflow_unit_scope": "local_subworkflow",
        "task_name": name,
        "task_description": name + "描述",
    }


def test_same_authority_and_pair_are_suppressed():
    rows = [_row("a", operator="native:buffer"), _row("a", operator="native:buffer"), _row("b", operator="native:buffer")]
    rows[1]["candidate_id"] = "a-duplicate"
    ledger, summary, audit = build_ledger(rows, [])
    assert summary["unique_source_authorities"] == 2
    assert summary["dedup_decision_counts"]["same_authority_suppressed"] == 1
    assert summary["dedup_decision_counts"]["exact_training_pair_suppressed"] == 1
    assert len([r for r in ledger if r["dedup_decision"] == "canonical_keep"]) == 1
    assert len(audit) == 1


def test_existing_training_pair_is_blocked():
    candidate = _row("a")
    existing = {"task_name": "任务", "task_description": "任务描述", "l3_code_sequence": ["L3_02_01_01"]}
    _ledger, summary, _ = build_ledger([candidate], [existing])
    assert summary["dedup_decision_counts"]["existing_training_pair_suppressed"] == 1
    assert summary["canonical_rows_before_audit"] == 0
