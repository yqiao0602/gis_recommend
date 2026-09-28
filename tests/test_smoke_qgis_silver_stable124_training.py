from scripts.smoke_qgis_silver_stable124_training import validate_rows


def _row() -> dict:
    return {
        "schema_version": "gis_recommend.qgis_silver_train_only.v1",
        "sample_id": "silver-1",
        "training_admission": "granted_train_only_qgis_silver_pilot_v1",
        "split": "train_only_qgis_silver_pilot_v1",
        "validation_eligible": False,
        "test_eligible": False,
        "production_merge": "not_granted",
        "gold_admission": "not_granted_independent_semantic_review_required",
        "l3_token_ids": [118],
        "l3_sequence": [-3, 118, -4],
        "task_metadata": {"task_name": "name", "task_description": "description"},
    }


def test_stable124_silver_rows_validate_without_gold_promotion() -> None:
    rows = validate_rows([_row()], expected_rows=1)
    assert rows[0]["l3_token_ids"] == [118]


def test_stable124_silver_rejects_production_merge() -> None:
    row = _row()
    row["production_merge"] = "granted"
    try:
        validate_rows([row], expected_rows=1)
    except ValueError as error:
        assert "production merge" in str(error)
    else:
        raise AssertionError("production-merge Silver row must be rejected")
