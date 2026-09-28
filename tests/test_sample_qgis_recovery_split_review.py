from scripts.sample_qgis_recovery_split_review import build_review_sample


def _row(index: int, rule_id: str, *, signature: str, controls: list[str]) -> dict:
    action = "split_subworkflow" if rule_id == "split-disconnected-scopes-v1" else "recover_call_graph"
    return {
        "record_id": f"record-{index}",
        "source_sha256": f"sha-{index}",
        "source_path": f"/{index}.py",
        "source_root_id": "test",
        "signature_hash": signature,
        "rule_id": rule_id,
        "action": action,
        "workflow_unit_scope": "whole_processing_scope",
        "structure_class": "unresolved",
        "operator_ids": ["native:buffer", "native:centroids"],
        "mapped_l3_chain": ["L3_A", "L3_B"],
        "dependency_edges": [],
        "call_sites": [],
        "source_snippet": "processing.run(...)\n",
        "reason": {"control_flow_kinds": controls},
    }


def test_sample_is_quota_balanced_source_disjoint_and_signature_diverse() -> None:
    rules = [
        "recover-control-flow-v1",
        "recover-missing-data-edges-v1",
        "recover-cross-scope-candidate-v1",
        "split-disconnected-scopes-v1",
    ]
    rows = [
        _row(rule_index * 100 + item, rule, signature=f"{rule}-sig-{item % 3}", controls=["for"] if item % 2 else [])
        for rule_index, rule in enumerate(rules)
        for item in range(6)
    ]

    sample, summary = build_review_sample(rows, quota_per_rule=3, seed=17)

    assert len(sample) == 12
    assert summary["selected_by_rule"] == {rule: 3 for rule in rules}
    assert len({row["source_sha256"] for row in sample}) == 12
    assert all(row["training_row_emitted"] is False for row in sample)
    assert all(row["review_status"] == "pending_human_review" for row in sample)
    assert all(len({row["signature_hash"] for row in sample if row["rule_id"] == rule}) == 3 for rule in rules)


def test_insufficient_rule_population_fails_closed() -> None:
    rows = [_row(1, "recover-control-flow-v1", signature="sig", controls=[])]

    try:
        build_review_sample(rows, quota_per_rule=2, seed=17)
    except ValueError as exc:
        assert "insufficient rows" in str(exc)
    else:
        raise AssertionError("expected fail-closed quota validation")
