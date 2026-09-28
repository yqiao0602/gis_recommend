from __future__ import annotations

from scripts.score_qgis_source_role_tiers import score, score_row


def row(**values):
    defaults = {
        "pool": "Processing",
        "source_role": "unclassified",
        "processing_run_count": 0,
        "task_semantic_signal": False,
        "input_output_signal": False,
        "data_dependency_signal": False,
    }
    defaults.update(values)
    return defaults


def test_score_row_assigns_workflow_and_implementation_tiers() -> None:
    assert score_row(
        row(
            source_role="user_workflow",
            processing_run_count=2,
            task_semantic_signal=True,
            input_output_signal=True,
            data_dependency_signal=True,
        )
    ) == "tier1_multi_step_workflow"
    assert score_row(
        row(
            source_role="user_workflow",
            processing_run_count=1,
            task_semantic_signal=True,
            input_output_signal=True,
        )
    ) == "tier2_single_operator_workflow"
    assert score_row(
        row(
            source_role="processing_implementation",
            processing_run_count=3,
            input_output_signal=True,
        )
    ) == "tier3_processing_implementation"


def test_score_row_assigns_api_and_deferred_tiers() -> None:
    assert score_row(
        row(
            pool="API",
            source_role="api_semantic_operation",
            task_semantic_signal=True,
            input_output_signal=True,
        )
    ) == "api_semantic_knowledge_candidate"
    assert score_row(row(pool="API", source_role="api_plumbing")) == "api_plumbing_evidence_only"
    assert score_row(row(source_role="deferred_source_missing")) == "deferred_source_missing"
    assert score_row(row(source_role="unclassified")) == "unclassified_deferred_cheap_filter"


def test_strict_workflow_gate_requires_all_signals() -> None:
    base = row(source_role="user_workflow", processing_run_count=2)
    for missing in ("task_semantic_signal", "input_output_signal", "data_dependency_signal"):
        candidate = dict(base, task_semantic_signal=True, input_output_signal=True, data_dependency_signal=True)
        candidate[missing] = False
        assert score_row(candidate) == "unclassified_deferred_cheap_filter"


def test_score_is_mutually_exclusive_and_training_closed() -> None:
    rows = [
        row(source_role="user_workflow", processing_run_count=2, task_semantic_signal=True, input_output_signal=True, data_dependency_signal=True),
        row(pool="API", source_role="api_semantic_operation", task_semantic_signal=True, input_output_signal=True),
        row(source_role="deferred_source_missing"),
    ]
    scored, summary = score(rows)
    assert [item["workflow_value_tier"] for item in scored] == [
        "tier1_multi_step_workflow",
        "api_semantic_knowledge_candidate",
        "deferred_source_missing",
    ]
    assert all(item["training_rows_emitted"] == 0 for item in scored)
    assert all(item["training_admission"] == "not_granted_role_tier_scoring" for item in scored)
    assert summary["source_rows"] == 3
    assert summary["training_rows_emitted"] == 0
    assert summary["tier_counts_by_pool"]["Processing"]["deferred_source_missing"] == 1

