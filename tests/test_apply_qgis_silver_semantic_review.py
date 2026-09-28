from scripts.apply_qgis_silver_semantic_review import REVIEWS, apply_review


def packet(record_id: str) -> dict:
    return {
        "schema": "gis_recommend.qgis_silver_semantic_review_packet.v1",
        "record_id": record_id,
        "source_sha256": f"sha-{record_id}",
        "sample_id": f"qgis_silver_{record_id}_train_v1",
    }


def silver(record_id: str) -> dict:
    return {
        "schema_version": "gis_recommend.qgis_silver_train_only.v1",
        "record_id": record_id,
        "source_sha256": f"sha-{record_id}",
        "sample_id": f"qgis_silver_{record_id}_train_v1",
        "training_admission": "granted_train_only_qgis_silver_pilot_v1",
        "_training_quality": {"sample_weight": 0.7},
    }


def test_full_review_emits_only_gold_and_retained_silver_for_train_only() -> None:
    rows = [packet(record_id) for record_id in REVIEWS]
    silver_rows = [silver(record_id) for record_id in REVIEWS]

    reviewed, gold, retained, revoked, summary = apply_review(rows, silver_rows)

    assert len(reviewed) == 21
    assert summary["gold_rows"] == 15
    assert summary["retained_silver_rows"] == 4
    assert summary["rejected_rows"] == 2
    assert summary["curated_train_only_rows"] == 19
    assert {row["record_id"] for row in revoked} == {
        "3d2310d2bfb7ec50fcd15b19",
        "632fea18482f1643b8fd2131",
    }
    assert all(row["_training_quality"]["sample_weight"] == 1.0 for row in gold)
    assert all(row["_training_quality"]["sample_weight"] == 0.7 for row in retained)
    assert all(row["training_admission"] == "revoked_semantic_review_reject" for row in revoked)
    assert summary["formal_authority_modified"] is False


def test_review_rejects_a_packet_with_wrong_identity() -> None:
    rows = [packet(record_id) for record_id in REVIEWS]
    rows.pop()
    silver_rows = [silver(record_id) for record_id in REVIEWS]

    try:
        apply_review(rows, silver_rows)
    except ValueError as error:
        assert "identity" in str(error)
    else:
        raise AssertionError("expected identity validation failure")
