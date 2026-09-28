from scripts.build_qgis_workflow_corpus_kpi import build_kpi


def test_kpi_keeps_pending_candidates_out_of_trainable_totals() -> None:
    summary = build_kpi(
        [
            {"semantic_review_decision": "gold"},
            {"semantic_review_decision": "retain_silver"},
            {"semantic_review_decision": "reject"},
        ],
        [
            {
                "review_status": "pending_independent_semantic_review",
                "split_group_key": "parent_source_sha256:a",
            }
        ],
    )

    assert summary["totals"] == {
        "candidate_rows": 4,
        "gold_rows": 1,
        "silver_rows": 1,
        "reject_rows": 1,
        "pending_rows": 1,
        "curated_train_only_rows": 2,
        "gold_silver_followup_rows": 0,
    }
    assert summary["official_authority_included"] is False
    assert summary["lanes"]["seed_subworkflow"]["unique_parent_split_groups"] == 1


def test_kpi_records_completed_semantic_classification_separately() -> None:
    summary = build_kpi(
        [{"semantic_review_decision": "gold"}],
        [{"review_status": "pending_independent_semantic_review", "split_group_key": "parent:a"}],
        [{"decision": "independent_workflow"}],
    )

    lane = summary["lanes"]["seed_subworkflow"]
    assert lane["pending_rows"] == 0
    assert lane["independent_workflow_rows"] == 1
    assert lane["gold_silver_followup_rows"] == 1
    assert summary["totals"]["curated_train_only_rows"] == 1
