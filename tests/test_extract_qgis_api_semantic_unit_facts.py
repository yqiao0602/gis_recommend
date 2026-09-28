import hashlib
import json
from pathlib import Path

from scripts.extract_qgis_api_semantic_unit_facts import build, extract_row


def _row(path: Path, methods: list[str]) -> dict:
    return {
        "record_id": "r1",
        "schema": "gis_recommend.qgis_asset_normalization.v1",
        "asset_type": "api_semantic_unit",
        "source_path": str(path),
        "source_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "source_root_id": "github_merge",
        "api_methods": methods,
    }


def _write(path: Path, text: str) -> Path:
    path.write_text(text, encoding="utf-8")
    return path


def test_no_row_can_be_qualified_in_phase_one(tmp_path: Path) -> None:
    source = _write(
        tmp_path / "a.py",
        "from qgis.core import QgsGeometry\n"
        "def run(feature):\n"
        "    geometry = feature.geometry()\n"
        "    result = geometry.buffer(500, 8)\n"
        "    return result\n",
    )
    facts, summary = build([_row(source, ["buffer"])])
    assert facts[0]["decision"] == "DEFERRED"
    assert facts[0]["semantic_status"] == "candidate_geometry_semantic"
    assert facts[0]["decision_reason"] == "awaiting_l3_mapping_proof_phase2"
    assert facts[0]["l3_mapping_status"] == "not_attempted_phase1"
    assert facts[0]["l3_candidate"] is None
    assert summary["qualified_rows"] == 0
    assert summary["training_rows_emitted"] == 0


def test_semantic_action_is_not_an_l3_code(tmp_path: Path) -> None:
    source = _write(
        tmp_path / "a.py",
        "def run(feature):\n"
        "    geometry = feature.geometry()\n"
        "    return geometry.buffer(10)\n",
    )
    facts, _ = build([_row(source, ["buffer"])])
    assert facts[0]["semantic_action"] == "geometry_transform:buffer"
    assert "L3_" not in facts[0]["semantic_action"]


def test_shapely_receiver_fails_closed(tmp_path: Path) -> None:
    source = _write(
        tmp_path / "a.py",
        "import shapely\n"
        "def run(points):\n"
        "    shape = shapely.geometry.Point(0, 0)\n"
        "    return shapely.buffer(shape, 10)\n",
    )
    facts, summary = build([_row(source, ["buffer"])])
    assert facts[0]["decision"] == "FAIL_CLOSED"
    assert facts[0]["semantic_status"] == "not_qgis_semantics"
    assert facts[0]["receiver"]["foreign_module"] == "shapely"
    assert summary["decision_counts"]["FAIL_CLOSED"] == 1


def test_geopandas_transform_fails_closed(tmp_path: Path) -> None:
    source = _write(
        tmp_path / "a.py",
        "import geopandas\n"
        "def run(path):\n"
        "    frame = geopandas.read_file(path)\n"
        "    return frame.to_crs(4326).transform(2)\n",
    )
    facts, _ = build([_row(source, ["transform"])])
    assert facts[0]["decision"] == "FAIL_CLOSED"
    assert facts[0]["receiver"]["foreign_module"] == "geopandas"


def test_unproven_local_receiver_is_deferred_not_qualified(tmp_path: Path) -> None:
    source = _write(
        tmp_path / "a.py",
        "def run(thing):\n"
        "    return thing.buffer(5)\n",
    )
    facts, _ = build([_row(source, ["buffer"])])
    assert facts[0]["decision"] == "DEFERRED"
    assert facts[0]["semantic_status"] == "ambiguous_receiver"
    assert facts[0]["receiver"]["kind"] == "local_name_no_dominating_binding"


def test_predicate_and_measurement_are_not_workflow_steps(tmp_path: Path) -> None:
    predicate = _write(
        tmp_path / "p.py",
        "def run(feature, other):\n"
        "    geometry = feature.geometry()\n"
        "    if geometry.contains(other):\n"
        "        return True\n",
    )
    measurement = _write(
        tmp_path / "m.py",
        "def run(feature, other):\n"
        "    geometry = feature.geometry()\n"
        "    value = geometry.distance(other)\n"
        "    return value\n",
    )
    facts, _ = build([_row(predicate, ["contains"]), _row(measurement, ["distance"])])
    assert [row["semantic_status"] for row in facts] == ["not_a_workflow_step"] * 2
    assert facts[0]["decision_reason"] == "spatial_predicate_returns_scalar_not_geometry"
    assert facts[1]["decision_reason"] == "measurement_returns_scalar_not_geometry"


def test_discarded_result_is_deferred(tmp_path: Path) -> None:
    source = _write(
        tmp_path / "a.py",
        "def run(feature):\n"
        "    geometry = feature.geometry()\n"
        "    geometry.buffer(10)\n"
        "    return geometry\n",
    )
    facts, _ = build([_row(source, ["buffer"])])
    assert facts[0]["semantic_status"] == "result_unused"
    assert facts[0]["return_target"]["kind"] == "discarded_expression_statement"


def test_qgis_factory_receiver_and_argument_facts(tmp_path: Path) -> None:
    source = _write(
        tmp_path / "a.py",
        "from qgis.core import QgsGeometry\n"
        "def run(wkt):\n"
        "    result = QgsGeometry.fromWkt(wkt).buffer(500, segments=8)\n"
        "    return result\n",
    )
    facts, _ = build([_row(source, ["buffer"])])
    row = facts[0]
    assert row["receiver"]["kind"] == "qgis_geometry_factory"
    assert row["receiver"]["qgis_type"] == "QgsGeometry.fromWkt"
    assert row["argument_facts"]["positional"][0]["literal_value"] == 500
    assert row["argument_facts"]["keyword"]["segments"]["literal_value"] == 8
    assert row["argument_facts"]["all_literal"] is True
    assert row["return_target"]["kind"] == "assignment"
    assert row["enclosing_scope"]["function"] == "run"


def test_sha_mismatch_and_missing_source_defer(tmp_path: Path) -> None:
    source = _write(tmp_path / "a.py", "def run(f):\n    return f.geometry().buffer(1)\n")
    bad = {**_row(source, ["buffer"]), "source_sha256": "0" * 64}
    missing = {**_row(source, ["buffer"]), "source_path": str(tmp_path / "nope.py")}
    facts, summary = build([bad, missing])
    assert [row["semantic_status"] for row in facts] == ["source_sha256_mismatch", "source_unavailable"]
    assert summary["source_verified_rows"] == 0
    assert summary["qualified_rows"] == 0


def test_cli_writes_hash_bound_artifacts(tmp_path: Path, monkeypatch) -> None:
    from scripts.extract_qgis_api_semantic_unit_facts import main

    source = _write(tmp_path / "a.py", "def run(f):\n    g = f.geometry()\n    return g.buffer(1)\n")
    ledger = tmp_path / "ledger.jsonl"
    ledger.write_text(json.dumps(_row(source, ["buffer"])) + "\n", encoding="utf-8")
    out = tmp_path / "out"
    monkeypatch.setattr("sys.argv", ["prog", "--normalized-ledger", str(ledger), "--output-dir", str(out)])
    assert main() == 0
    hashes = json.loads((out / "hash_ledger_v1.json").read_text(encoding="utf-8"))
    assert "normalized_ledger_input" in hashes
    assert json.loads((out / "summary_v1.json").read_text(encoding="utf-8"))["qualified_rows"] == 0


def test_shapely_only_keyword_fails_closed_despite_plausible_receiver(tmp_path: Path) -> None:
    """``cap_style`` does not exist in PyQGIS ``buffer(distance, segments)``."""
    source = _write(
        tmp_path / "a.py",
        "def run(frame, distance):\n"
        "    geom = frame.geometry()\n"
        "    return geom.buffer(distance, cap_style=2, join_style=1)\n",
    )
    facts, summary = build([_row(source, ["buffer"])])
    assert facts[0]["decision"] == "FAIL_CLOSED"
    assert facts[0]["semantic_status"] == "not_qgis_semantics"
    assert facts[0]["decision_reason"] == "foreign_only_keyword_argument:cap_style"
    assert summary["qualified_rows"] == 0


def test_bare_geometry_attribute_is_not_a_qgis_receiver(tmp_path: Path) -> None:
    """``frame.geometry.buffer(...)`` is the GeoDataFrame idiom, not PyQGIS."""
    source = _write(
        tmp_path / "a.py",
        "def run(frame, distance):\n"
        "    return frame.geometry.buffer(distance)\n",
    )
    facts, _ = build([_row(source, ["buffer"])])
    assert facts[0]["decision"] == "DEFERRED"
    assert facts[0]["semantic_status"] == "ambiguous_receiver"
    assert "attribute_accessor_not_a_call" in facts[0]["decision_reason"]


def test_geometry_call_accessor_remains_a_qgis_receiver(tmp_path: Path) -> None:
    source = _write(
        tmp_path / "a.py",
        "def run(feature, distance):\n"
        "    return feature.geometry().buffer(distance, 8)\n",
    )
    facts, _ = build([_row(source, ["buffer"])])
    assert facts[0]["receiver"]["kind"] == "qgis_geometry_accessor"
    assert facts[0]["semantic_status"] == "candidate_geometry_semantic"
