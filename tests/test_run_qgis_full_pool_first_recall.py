from pathlib import Path

from scripts.run_qgis_full_pool_first_recall import build_report


def test_full_pool_recall_uses_one_denominator_and_reports_yield():
    census = [
        {"source_sha256": "a", "source_role": "user_workflow", "workflow_value_tier": "tier1"},
        {"source_sha256": "b", "source_role": "unclassified", "workflow_value_tier": "deferred"},
        {"source_sha256": "c", "source_role": "api_plumbing", "workflow_value_tier": "plumbing"},
    ]
    candidates = [
        {"source_sha256": "a", "candidate_kind": "processing_workflow_candidate"},
        {"source_sha256": "x", "candidate_kind": "outside_census"},
    ]
    review = [{"_training_quality": {"sample_weight": 1.0}}, {"_training_quality": {"sample_weight": 0.7}}]
    report = build_report(census, candidates, review, observed_curated_rows=2)
    assert report["census"]["source_rows"] == 3
    assert report["candidate_stage"]["candidate_rows"] == 2
    assert report["candidate_stage"]["candidate_source_recall"] is None
    assert report["candidate_stage"]["candidate_rate_over_census"] == round(1 / 3, 6)
    assert report["review_stage"]["accepted_rows"] == 2
    assert report["review_stage"]["accepted_yield_over_census"] == round(2 / 3, 6)
    assert report["observed_curated_stage"]["linkage"] == "not_asserted_against_candidate_stage"


def test_missing_stages_are_not_estimated():
    report = build_report([{"source_sha256": "a"}])
    assert report["candidate_stage"]["status"] == "not_available"
    assert report["review_stage"]["status"] == "not_available"
    assert report["training_rows_emitted"] == 0
