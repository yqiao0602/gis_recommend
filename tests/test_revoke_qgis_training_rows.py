from scripts.revoke_qgis_training_rows import filter_training_rows


def test_rows_with_semantically_excluded_operators_are_revoked() -> None:
    rows = [
        {
            "sample_id": "keep",
            "record_id": "one",
            "qgis_operator_chain": ["native:buffer"],
            "training_admission": "granted_train_only",
        },
        {
            "sample_id": "ruggedness",
            "record_id": "two",
            "qgis_operator_chain": ["native:ruggednessindex"],
            "training_admission": "granted_train_only",
        },
        {
            "sample_id": "statistics",
            "record_id": "three",
            "operator_sequence": ["native:buffer", "qgis:basicstatisticsforfields"],
            "training_admission": "granted_train_only",
        },
    ]
    exclusions = {
        "native:ruggednessindex": {"excluded_l3_code": "L3_04_01_01"},
        "qgis:basicstatisticsforfields": {"excluded_l3_code": "L3_01_08_03"},
    }

    kept, revoked = filter_training_rows(rows, exclusions)

    assert [row["sample_id"] for row in kept] == ["keep"]
    assert [row["sample_id"] for row in revoked] == ["ruggedness", "statistics"]
    assert revoked[0]["excluded_operator_ids"] == ["native:ruggednessindex"]
    assert revoked[1]["excluded_operator_ids"] == ["qgis:basicstatisticsforfields"]
    assert all(row["action"] == "revoke_training_row" for row in revoked)
