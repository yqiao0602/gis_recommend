import json
from pathlib import Path

from scripts.build_qgis_family_parameter_assets import build_assets, main


def _row(record_id: str, parameter_key: str, source: str) -> dict:
    return {
        "record_id": record_id,
        "source_sha256": source.ljust(64, "0"),
        "family": "native:dissolve|native:multiparttosingleparts",
        "normalized_dag_key": "dag",
        "l3": ["L3_DISSOLVE", "L3_SPLIT"],
        "parameters": {
            "status": "parsed",
            "semantic_key": parameter_key,
            "key": "raw-" + parameter_key,
            "items": [{"operator_id": "native:dissolve", "parameters": [{"key": "FIELD", "semantic_value": parameter_key}]}],
        },
        "source_structure": {"parent_operator_sequence": ["native:dissolve", "native:multiparttosingleparts"], "matched_span": {"start_index": 0}},
    }


def test_materializes_parameter_parent_and_operator_assets() -> None:
    parameters, structures, operators, summary = build_assets([_row("a", "field-a", "a"), _row("b", "field-b", "b"), _row("c", "field-a", "c")])
    assert len(parameters) == 2
    assert len(structures) == 1
    assert len(operators) == 2
    assert summary["parameter_support"] == 3
    assert all(asset["training_rows_emitted"] == 0 for asset in parameters + structures + operators)


def test_cli_writes_candidate_only_pool(tmp_path: Path, monkeypatch) -> None:
    source = tmp_path / "rows.jsonl"
    source.write_text(json.dumps(_row("a", "field-a", "a")) + "\n", encoding="utf-8")
    output = tmp_path / "out"
    monkeypatch.setattr("sys.argv", ["prog", "--collapse-rows", str(source), "--output-dir", str(output)])
    assert main() == 0
    summary = json.loads((output / "summary_v1.json").read_text(encoding="utf-8"))
    assert summary["parameter_assets"] == 1
    assert summary["training_rows_emitted"] == 0
    assert (output / "asset_pool_report_v1.md").exists()
