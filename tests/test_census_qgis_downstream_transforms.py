import json

from scripts.census_qgis_downstream_transforms import build_census, main


def _row(
    body: str,
    unit: str,
    calls: list[str],
    reasons: list[str],
    low_level_roles: list[str] | None = None,
) -> dict:
    return {
        "normalized_source_body_sha256": body,
        "unit_id": unit,
        "split_class": "multi_step_local_dag",
        "operator_ids": ["native:fixgeometries", "native:buffer"],
        "local_structure_reasons": reasons,
        "local_risk_evidence": {
            "downstream_data_transform_calls": calls,
            "downstream_low_level_data_transform_roles": low_level_roles or [],
        },
    }


def test_census_deduplicates_units_and_keeps_semantic_continuations_closed() -> None:
    rows = [
        _row(
            "body-a",
            "unit-a",
            ["getFeatures", "setGeometry", "addFeature"],
            [
                "downstream_data_transform",
                "downstream_low_level_data_transform:addFeature",
                "downstream_low_level_data_transform:setGeometry",
            ],
            ["addFeature", "setGeometry"],
        ),
        _row(
            "body-a",
            "unit-a",
            ["getFeatures", "setGeometry", "addFeature"],
            [
                "downstream_data_transform",
                "downstream_low_level_data_transform:addFeature",
                "downstream_low_level_data_transform:setGeometry",
            ],
            ["addFeature", "setGeometry"],
        ),
        _row(
            "body-b",
            "unit-b",
            ["QgsLayerTreeLayer", "insertChildNode", "setText"],
            ["downstream_data_transform"],
        ),
    ]

    census = build_census(rows, minimum_support=30)

    assert census["summary"]["unique_multi_step_units"] == 2
    assert census["summary"]["normalized_body_authorities"] == 2
    assert census["summary"]["safe_support_authorities"] == 1
    assert census["summary"]["support_pass_safe_families"] == 0
    assert census["summary"]["low_level_sink_units"] == 1
    assert census["summary"]["low_level_sink_authorities"] == 1
    assert census["summary"]["low_level_sink_route"] == "qgis_api_pattern_deferred"
    assert census["summary"]["training_rows_emitted"] == 0
    decisions = {row["downstream_role_status"] for row in census["units"]}
    assert decisions == {"presentation_only", "semantic_continuation"}


def test_main_writes_hash_bound_report(tmp_path) -> None:
    input_path = tmp_path / "input.jsonl"
    input_path.write_text(
        json.dumps(
            _row(
                "body-a",
                "unit-a",
                ["getFeatures"],
                ["downstream_data_transform"],
            )
        )
        + "\n",
        encoding="utf-8",
    )
    output_dir = tmp_path / "report"

    assert (
        main(
            [
                "--input-jsonl",
                str(input_path),
                "--output-dir",
                str(output_dir),
            ]
        )
        == 0
    )

    ledger = json.loads((output_dir / "hash_ledger_v1.json").read_text())
    assert str(input_path) in ledger["source_inputs"]
    assert set(ledger["artifacts"]) == {
        "downstream_families_v1.jsonl",
        "downstream_units_v1.jsonl",
        "report_v1.md",
        "summary_v1.json",
    }
