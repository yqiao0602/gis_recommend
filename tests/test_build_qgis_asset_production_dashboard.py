from scripts.build_qgis_asset_production_dashboard import build_dashboard


def test_dashboard_separates_family_yield_from_asset_pools() -> None:
    result = build_dashboard(
        {"input_rows": 10, "source_verified_rows": 9, "asset_type_counts": {"processing_workflow": 4, "api_semantic_unit": 6}},
        [{"family": "a", "reviewed_rows": 4, "silver_candidates": 4, "structural_passed": 4, "dedup_unique": 1}],
        {"silver_candidates": 1, "quality_counts": {"reject": 3}, "gold_candidates": 0, "training_rows_emitted": 0, "formal_authority_modified": False},
    )
    assert result["family_candidate_rows"] == 4
    assert result["dedup_unique_silver_candidates"] == 1
    assert next(row for row in result["asset_pools"] if row["pool"] == "api_semantic_unit")["status"] == "queued"
