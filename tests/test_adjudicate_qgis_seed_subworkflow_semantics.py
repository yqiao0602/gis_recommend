from scripts.adjudicate_qgis_seed_subworkflow_semantics import adjudicate


def _row(candidate_id: str, operators: list[str]) -> dict:
    return {
        "candidate_id": candidate_id,
        "parent_workflow_id": "parent-1",
        "seed_source_sha256": "a" * 64,
        "split_group_key": "parent_source_sha256:" + "a" * 64,
        "operator_sequence": operators,
    }


def test_three_way_review_keeps_independent_rows_out_of_training() -> None:
    decisions, summary = adjudicate(
        [
            _row("0171d3e9-rest", ["native:reprojectlayer", "native:clip"]),
            _row("0b6ff612-rest", ["native:saveselectedfeatures", "native:saveselectedfeatures"]),
            _row("48970824-rest", ["native:fieldcalculator", "native:fieldcalculator"]),
        ]
    )

    assert [row["decision"] for row in decisions] == [
        "independent_workflow",
        "implementation_subworkflow",
        "duplicate_or_parent_contained",
    ]
    assert summary["decision_counts"] == {
        "duplicate_or_parent_contained": 1,
        "implementation_subworkflow": 1,
        "independent_workflow": 1,
    }
    assert summary["training_rows_emitted"] == 0
