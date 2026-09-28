import hashlib
import json
from pathlib import Path

from scripts.build_qgis_processing_operator_evidence_sidecar import build_sidecar, main


def _row(path: Path, operator: str = "native:buffer") -> dict:
    return {
        "record_id": "r1",
        "schema": "gis_recommend.qgis_asset_normalization.v1",
        "asset_type": "processing_operator",
        "source_path": str(path),
        "source_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "processing_operator_ids": [operator],
    }


def test_extracts_call_parameter_io_and_provider_evidence(tmp_path: Path) -> None:
    source = tmp_path / "buffer.py"
    source.write_text(
        "import processing\n"
        "params = {'INPUT': layer, 'DISTANCE': 10, 'OUTPUT': 'memory:'}\n"
        "result = processing.run('native:buffer', params)\n",
        encoding="utf-8",
    )
    rows, summary = build_sidecar([_row(source)], expected_operator_rows=1)
    call = rows[0]["calls"][0]
    assert rows[0]["status"] == "source_verified_ast"
    assert call["source_span"]["line_start"] == 3
    assert call["parameter_evidence"]["status"] == "verified_static_dict"
    assert call["io_evidence"]["keys"] == ["INPUT", "OUTPUT"]
    assert call["provider_evidence"]["provider_id"] == "native"
    assert summary["parameter_verified_call_rows"] == 1
    assert summary["io_key_evidence_call_rows"] == 1


def test_fail_closed_for_dynamic_operator_and_missing_source(tmp_path: Path) -> None:
    source = tmp_path / "dynamic.py"
    source.write_text("import processing\nalgo = get_algorithm()\nprocessing.run(algo, params)\n", encoding="utf-8")
    missing = {
        "record_id": "missing",
        "schema": "gis_recommend.qgis_asset_normalization.v1",
        "asset_type": "processing_operator",
        "source_path": str(tmp_path / "missing.py"),
        "source_sha256": "0" * 64,
        "processing_operator_ids": ["native:buffer"],
    }
    rows, summary = build_sidecar([_row(source), missing], expected_operator_rows=2)
    assert rows[0]["status"] == "deferred"
    assert rows[0]["reason"] == "dynamic_operator_unresolved"
    assert rows[1]["reason"] == "source_unavailable"
    assert summary["source_verified_rows"] == 1
    assert summary["reason_counts"]["source_unavailable"] == 1


def test_cli_writes_candidate_only_artifacts(tmp_path: Path, monkeypatch) -> None:
    source = tmp_path / "buffer.py"
    source.write_text("import processing\nprocessing.run('native:buffer', {'INPUT': layer})\n", encoding="utf-8")
    ledger = tmp_path / "ledger.jsonl"
    ledger.write_text(json.dumps(_row(source)) + "\n", encoding="utf-8")
    output = tmp_path / "out"
    monkeypatch.setattr("sys.argv", ["prog", "--input-ledger", str(ledger), "--output-dir", str(output), "--expected-operator-rows", "1"])
    assert main() == 0
    summary = json.loads((output / "summary_v1.json").read_text(encoding="utf-8"))
    assert summary["training_rows_emitted"] == 0
    assert (output / "operator_evidence_sidecar_v1.jsonl").exists()


def test_records_legacy_runalg_positional_evidence(tmp_path: Path) -> None:
    source = tmp_path / "runalg.py"
    source.write_text(
        "import processing\n"
        "processing.runalg('qgis:clip', layer, mask, output)\n",
        encoding="utf-8",
    )
    rows, summary = build_sidecar([_row(source, "qgis:clip")], expected_operator_rows=1)
    call = rows[0]["calls"][0]
    assert rows[0]["status"] == "source_verified_ast"
    assert call["entrypoint"] == "runalg"
    assert call["parameter_evidence"]["status"] == "verified_positional_arguments"
    assert call["io_evidence"]["status"] == "positional_arguments_present"
    assert summary["parameter_verified_call_rows"] == 0
    assert summary["io_evidence_call_rows"] == 1


def test_records_imported_runalg_form(tmp_path: Path) -> None:
    source = tmp_path / "imported_runalg.py"
    source.write_text(
        "from processing import runalg\n"
        "runalg('qgis:clip', layer, mask, output)\n",
        encoding="utf-8",
    )
    rows, _ = build_sidecar([_row(source, "qgis:clip")], expected_operator_rows=1)
    assert rows[0]["status"] == "source_verified_ast"
    assert rows[0]["calls"][0]["entrypoint"] == "runalg"


def test_name_binding_uses_the_dominating_assignment_not_the_last_one(tmp_path: Path) -> None:
    """Regression: a later assignment elsewhere must not supply this call's parameters."""
    source = tmp_path / "two_joins.py"
    source.write_text(
        "import processing\n"
        "def first(layer, join):\n"
        "    params = {'INPUT': layer, 'JOIN': join, 'METHOD': 1, 'PREFIX': 'a_'}\n"
        "    processing.run('qgis:joinattributesbylocation', params)\n"
        "def second(layer, join):\n"
        "    params = {'INPUT': layer, 'JOIN': join, 'SUMMARIES': [0]}\n"
        "    processing.run('native:buffer', params)\n",
        encoding="utf-8",
    )
    rows, _ = build_sidecar([_row(source, "qgis:joinattributesbylocation")], expected_operator_rows=1)
    evidence = rows[0]["calls"][0]["parameter_evidence"]
    provenance = evidence["binding_provenance"]
    assert evidence["status"] == "verified_static_dict"
    assert evidence["keys"] == ["INPUT", "JOIN", "METHOD", "PREFIX"]
    assert provenance["assignment_lineno"] == 3
    assert provenance["assignment_scope_verified"] is True
    assert provenance["dominance_verified"] is True
    assert provenance["mutation_guard"] == "no_interfering_write"
    assert provenance["assignment_span"]["line_start"] == 3


def test_name_binding_recovers_static_dict_shadowed_by_a_later_expression(tmp_path: Path) -> None:
    """Regression: a later non-dict assignment must not defer a provable recovery."""
    source = tmp_path / "download.py"
    source.write_text(
        "import processing\n"
        "def download(url, target):\n"
        "    params = {'URL': url, 'OUTPUT': target}\n"
        "    processing.run('qgis:filedownloader', params)\n"
        "def unrelated(other):\n"
        "    params = build_params(other)\n"
        "    return params\n",
        encoding="utf-8",
    )
    rows, summary = build_sidecar([_row(source, "qgis:filedownloader")], expected_operator_rows=1)
    evidence = rows[0]["calls"][0]["parameter_evidence"]
    assert evidence["status"] == "verified_static_dict"
    assert evidence["keys"] == ["URL", "OUTPUT"]
    assert summary["name_bound_provenance"]["dominance_verified"] == 1


def test_dict_mutation_between_assignment_and_call_fails_closed(tmp_path: Path) -> None:
    source = tmp_path / "mutated.py"
    source.write_text(
        "import processing\n"
        "def run_it(layer):\n"
        "    params = {'INPUT': layer, 'DISTANCE': 10}\n"
        "    params['DISTANCE'] = compute()\n"
        "    processing.run('native:buffer', params)\n",
        encoding="utf-8",
    )
    rows, summary = build_sidecar([_row(source)], expected_operator_rows=1)
    evidence = rows[0]["calls"][0]["parameter_evidence"]
    assert rows[0]["calls"][0]["parameter_binding"] == "unresolved_name_binding"
    assert evidence["status"] == "deferred"
    assert evidence["reason"] == "interfering_write_before_call"
    assert evidence["binding_provenance"]["interfering_write_lines"] == [4]
    assert summary["parameter_completeness_counts"] == {"parameter_unresolved": 1}


def test_update_call_between_assignment_and_call_fails_closed(tmp_path: Path) -> None:
    source = tmp_path / "updated.py"
    source.write_text(
        "import processing\n"
        "def run_it(layer, extra):\n"
        "    params = {'INPUT': layer}\n"
        "    params.update(extra)\n"
        "    processing.run('native:buffer', params)\n",
        encoding="utf-8",
    )
    rows, _ = build_sidecar([_row(source)], expected_operator_rows=1)
    evidence = rows[0]["calls"][0]["parameter_evidence"]
    assert evidence["status"] == "deferred"
    assert evidence["reason"] == "interfering_write_before_call"


def test_conditional_assignment_that_does_not_dominate_fails_closed(tmp_path: Path) -> None:
    source = tmp_path / "branch.py"
    source.write_text(
        "import processing\n"
        "def run_it(layer, flag):\n"
        "    if flag:\n"
        "        params = {'INPUT': layer, 'DISTANCE': 10}\n"
        "    processing.run('native:buffer', params)\n",
        encoding="utf-8",
    )
    rows, _ = build_sidecar([_row(source)], expected_operator_rows=1)
    evidence = rows[0]["calls"][0]["parameter_evidence"]
    assert evidence["status"] == "deferred"
    assert evidence["reason"] == "no_dominating_assignment"
    assert evidence["binding_provenance"]["dominance_verified"] is False


def test_assignment_from_an_enclosing_scope_fails_closed(tmp_path: Path) -> None:
    source = tmp_path / "closure.py"
    source.write_text(
        "import processing\n"
        "def outer(layer):\n"
        "    params = {'INPUT': layer, 'DISTANCE': 10}\n"
        "    def inner():\n"
        "        processing.run('native:buffer', params)\n"
        "    return inner\n",
        encoding="utf-8",
    )
    rows, _ = build_sidecar([_row(source)], expected_operator_rows=1)
    evidence = rows[0]["calls"][0]["parameter_evidence"]
    assert evidence["status"] == "deferred"
    assert evidence["reason"] == "assignment_outside_call_scope"
    assert evidence["binding_provenance"]["dominance_verified"] is True
    assert evidence["binding_provenance"]["assignment_scope_verified"] is False


def test_parameter_completeness_separates_literal_and_expression_payloads(tmp_path: Path) -> None:
    literal = tmp_path / "literal.py"
    literal.write_text(
        "import processing\n"
        "processing.run('native:buffer', {'INPUT': 'roads.shp', 'DISTANCE': 500})\n",
        encoding="utf-8",
    )
    mixed = tmp_path / "mixed.py"
    mixed.write_text(
        "import processing\n"
        "processing.run('native:buffer', {'INPUT': layer, 'DISTANCE': 500})\n",
        encoding="utf-8",
    )
    rows, summary = build_sidecar([_row(literal), _row(mixed)], expected_operator_rows=2)
    assert rows[0]["calls"][0]["parameter_evidence"]["completeness"] == "static_parameter_complete"
    assert rows[1]["calls"][0]["parameter_evidence"]["completeness"] == "static_parameter_partial"
    assert summary["parameter_completeness_counts"] == {
        "static_parameter_complete": 1,
        "static_parameter_partial": 1,
    }


def test_non_literal_dict_keys_cannot_be_reported_complete(tmp_path: Path) -> None:
    source = tmp_path / "dynamic_key.py"
    source.write_text(
        "import processing\n"
        "processing.run('native:buffer', {'INPUT': 'a.shp', key_name: 500})\n",
        encoding="utf-8",
    )
    rows, _ = build_sidecar([_row(source)], expected_operator_rows=1)
    evidence = rows[0]["calls"][0]["parameter_evidence"]
    assert evidence["unresolved_key_count"] == 1
    assert evidence["completeness"] == "static_parameter_partial"


def test_binding_inside_an_except_handler_is_resolvable(tmp_path: Path) -> None:
    """``except`` bodies are not statement fields, so they must still be indexed."""
    source = tmp_path / "handler.py"
    source.write_text(
        "import processing\n"
        "def run_it(layer):\n"
        "    try:\n"
        "        primary()\n"
        "    except RuntimeError:\n"
        "        params = {'INPUT': layer, 'DISTANCE': 10}\n"
        "        processing.run('native:buffer', params)\n",
        encoding="utf-8",
    )
    rows, _ = build_sidecar([_row(source)], expected_operator_rows=1)
    evidence = rows[0]["calls"][0]["parameter_evidence"]
    assert evidence["status"] == "verified_static_dict"
    assert evidence["keys"] == ["INPUT", "DISTANCE"]
    assert evidence["binding_provenance"]["assignment_lineno"] == 6


def test_try_body_assignment_does_not_dominate_an_except_handler_call(tmp_path: Path) -> None:
    source = tmp_path / "handler_cross.py"
    source.write_text(
        "import processing\n"
        "def run_it(layer):\n"
        "    try:\n"
        "        params = {'INPUT': layer, 'DISTANCE': 10}\n"
        "    except RuntimeError:\n"
        "        processing.run('native:buffer', params)\n",
        encoding="utf-8",
    )
    rows, _ = build_sidecar([_row(source)], expected_operator_rows=1)
    evidence = rows[0]["calls"][0]["parameter_evidence"]
    assert evidence["status"] == "deferred"
    assert evidence["reason"] == "no_dominating_assignment"
