from scripts.export_qgis_silver_train_only import export


def test_export_silver_marks_gold_closed_and_frames_tokens() -> None:
    row = {
        "quality_class": "silver",
        "admission_status": "silver_candidate",
        "record_id": "r",
        "source_sha256": "a" * 64,
        "operator_sequence": ["native:buffer"],
        "l3_code_sequence": ["L3_02_01_01"],
        "task_name": "创建缓冲区",
        "task_description": "创建缓冲区",
    }
    rows, summary = export([row], {"L3_02_01_01": 8})
    assert rows[0]["l3_sequence"] == [-3, 8, -4]
    assert rows[0]["_training_quality"]["sample_weight"] == 0.7
    assert rows[0]["gold_admission"] == "not_granted_independent_semantic_review_required"
    assert summary["silver_rows"] == 1
    assert summary["gold_rows"] == 0
