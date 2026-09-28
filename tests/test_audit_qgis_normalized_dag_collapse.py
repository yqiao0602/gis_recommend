import json
from pathlib import Path

from scripts.audit_qgis_normalized_dag_collapse import audit, main


def _row(record_id: str, task: str, distance: int, *, dag: str = "dag") -> dict:
    source = (
        "import processing\n"
        f"result = processing.run('native:buffer', {{'INPUT': layer, 'DISTANCE': {distance}, 'OUTPUT': 'memory:'}})\n"
        "processing.run('native:clip', {'INPUT': result['OUTPUT'], 'OVERLAY': mask, 'OUTPUT': 'memory:'})\n"
    )
    return {
        "record_id": record_id,
        "source_sha256": record_id.ljust(64, "0"),
        "source_text": source,
        "processing_calls": [
            {"operator_id": "native:buffer", "line_start": 2, "line_end": 2},
            {"operator_id": "native:clip", "line_start": 3, "line_end": 3},
        ],
        "operator_sequence": ["native:buffer", "native:clip"],
        "family_sequence": ["native:buffer", "native:clip"],
        "l3_code_sequence": ["L3_BUFFER", "L3_CLIP"],
        "provider_io_contracts": [{"input_types": ["vector"], "output_type": "vector"}],
        "dependency_edges": [[0, 1]],
        "full_parent_operator_sequence": ["native:buffer", "native:clip"],
        "matched_span": {"start_index": 0, "end_index_exclusive": 2},
        "normalized_dag_key": dag,
        "task_description": task,
    }


def test_detects_parameter_or_task_variants_as_potential_overmerge() -> None:
    groups, _, summary = audit([_row("a", "buffer roads", 10), _row("b", "buffer buildings", 20)])
    assert groups[0]["assessment"] == "potential_overmerge"
    assert groups[0]["dimensions_differ"]["task"] is True
    assert groups[0]["dimensions_differ"]["parameters"] is True
    assert summary["potential_overmerge"] is True


def test_identical_semantic_rows_are_likely_true_duplicates() -> None:
    groups, _, summary = audit([_row("a", "buffer roads", 10), _row("b", "buffer roads", 10)])
    assert groups[0]["assessment"] == "likely_true_duplicate"
    assert summary["potential_overmerge"] is False


def test_unavailable_parameters_are_not_treated_as_equal_evidence() -> None:
    first = _row("a", "same", 10)
    second = _row("b", "same", 10)
    first["source_text"] = "not valid python ("
    second["source_text"] = "not valid python ("
    groups, _, summary = audit([first, second])
    assert groups[0]["assessment"] == "insufficient_parameter_evidence"
    assert groups[0]["dimensions_differ"]["parameters_unavailable"] is True
    assert summary["potential_overmerge"] is False


def test_cli_writes_auditable_outputs(tmp_path: Path, monkeypatch) -> None:
    ledger = tmp_path / "ledger.jsonl"
    ledger.write_text("\n".join(json.dumps(row) for row in [_row("a", "same", 10), _row("b", "same", 10)]) + "\n", encoding="utf-8")
    output = tmp_path / "out"
    monkeypatch.setattr("sys.argv", ["prog", "--ledger", str(ledger), "--output-dir", str(output)])
    assert main() == 0
    assert (output / "duplicate_groups_v1.jsonl").exists()
    assert (output / "collapse_audit_v1.md").exists()
    assert json.loads((output / "summary_v1.json").read_text(encoding="utf-8"))["duplicate_groups"] == 1


def test_parameter_extraction_respects_nonzero_family_span() -> None:
    row = _row("a", "same", 10)
    row["matched_span"] = {"start_index": 2, "end_index_exclusive": 4}
    row["processing_calls"] = [
        {"operator_id": "native:buffer", "line_start": 2, "line_end": 2},
        {"operator_id": "native:clip", "line_start": 3, "line_end": 3},
        {"operator_id": "native:buffer", "line_start": 2, "line_end": 2},
        {"operator_id": "native:clip", "line_start": 3, "line_end": 3},
    ]
    signatures = audit([row, {**row, "record_id": "b", "source_sha256": "b".ljust(64, "0")}])[0]
    assert signatures[0]["assessment"] == "likely_true_duplicate"
