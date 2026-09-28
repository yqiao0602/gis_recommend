from scripts.smoke_qgis_reviewed_gold_silver_stable124_training import validate_rows


def _row(decision: str, weight: float) -> dict:
    return {
        "schema_version": "gis_recommend.qgis_silver_train_only.v1",
        "sample_id": f"sample-{decision}-{weight}",
        "semantic_review_decision": decision,
        "gold_admission": "granted_independent_semantic_reviewed_gold_pilot_v1" if decision == "gold" else "not_granted_semantic_review_not_gold",
        "training_admission": "granted_train_only_qgis_silver_pilot_v1" if decision == "gold" else "retained_independent_semantic_reviewed_silver_pilot_v1",
        "_training_quality": {"sample_weight": weight},
        "validation_eligible": False,
        "test_eligible": False,
        "production_merge": "not_granted",
        "l3_token_ids": [118],
        "l3_sequence": [-3, 118, -4],
        "task_metadata": {"task_name": "name", "task_description": "description"},
    }


def test_reviewed_rows_require_exact_gold_silver_distribution() -> None:
    rows = [_row("gold", 1.0) for _ in range(15)] + [_row("retain_silver", 0.7) for _ in range(4)]
    for index, row in enumerate(rows):
        row["sample_id"] = f"sample-{index}"
    assert len(validate_rows(rows, expected_rows=19)) == 19


def test_reviewed_rows_reject_unreviewed_status() -> None:
    rows = [_row("gold", 1.0) for _ in range(15)] + [_row("retain_silver", 0.7) for _ in range(4)]
    for index, row in enumerate(rows):
        row["sample_id"] = f"sample-{index}"
    rows[0]["semantic_review_decision"] = "reject"
    try:
        validate_rows(rows, expected_rows=19)
    except ValueError as error:
        assert "non-trainable" in str(error)
    else:
        raise AssertionError("rejected row must not enter curated V4 smoke")
