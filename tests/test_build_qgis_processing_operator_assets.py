import json
from pathlib import Path

from scripts.build_qgis_processing_operator_assets import build_assets, main


def _row(record_id: str, source: str, operators: list[str]) -> dict:
    return {
        "record_id": record_id,
        "source_sha256": source.ljust(64, "0"),
        "asset_type": "processing_operator",
        "processing_operator_ids": operators,
        "processing_calls": [{"operator_id": operator, "resolution_kind": "literal"} for operator in operators],
        "parameter_evidence_status": "verified_source_ast",
        "provider_io_contracts": [{"operator_id": operators[0], "output_type": "vector"}],
    }


def test_groups_operator_assets_and_preserves_source_support() -> None:
    assets, summary = build_assets([_row("a", "a", ["native:buffer", "native:clip"]), _row("b", "b", ["native:buffer"])], expected_operator_rows=2)
    buffer = next(asset for asset in assets if asset["operator_id"] == "native:buffer")
    assert buffer["support_rows"] == 2
    assert buffer["unique_source_sha256"] == 2
    assert buffer["parameter_evidence_rows"] == 2
    assert summary["operator_assets"] == 2
    assert summary["expected_operator_rows_status"] == "matched"
    assert all(asset["training_rows_emitted"] == 0 for asset in assets)


def test_cli_emits_candidate_only_operator_census(tmp_path: Path, monkeypatch) -> None:
    source = tmp_path / "input.jsonl"
    source.write_text(json.dumps(_row("a", "a", ["native:buffer"])) + "\n", encoding="utf-8")
    output = tmp_path / "out"
    monkeypatch.setattr("sys.argv", ["prog", "--input-ledger", str(source), "--output-dir", str(output), "--expected-operator-rows", "1"])
    assert main() == 0
    summary = json.loads((output / "summary_v1.json").read_text(encoding="utf-8"))
    assert summary["operator_assets"] == 1
    assert summary["expected_operator_rows_status"] == "matched"
    assert (output / "operator_asset_report_v1.md").exists()


def test_uses_normalized_resolution_and_reports_missing_evidence_fields() -> None:
    row = {
        "record_id": "normalized",
        "source_sha256": "c" * 64,
        "asset_type": "processing_operator",
        "processing_operator_ids": ["native:buffer"],
        "processing_call_count": 1,
        "resolution": {"processing": "literal_source_evidence"},
    }
    assets, summary = build_assets([row], expected_operator_rows=1)
    assert assets[0]["resolution_kinds"] == ["literal_source_evidence"]
    assert assets[0]["processing_call_evidence_rows"] == 1
    assert summary["parameter_evidence_availability"] == "not_carried_by_normalized_ledger"
    assert summary["io_evidence_availability"] == "not_carried_by_normalized_ledger"
