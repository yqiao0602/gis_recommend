from __future__ import annotations

import hashlib
from pathlib import Path

from scripts.audit_qgis_runalg_adapter_calibration import audit_row


def test_independent_audit_accepts_matching_direct_variable_edge(tmp_path: Path) -> None:
    source = tmp_path / "workflow.py"
    source.write_text(
        "import processing\n"
        "first = processing.runalg('native:buffer', roads, 20)\n"
        "processing.runalg('native:clip', first, boundary)\n",
        encoding="utf-8",
    )
    row = {
        "record_id": "fixture",
        "source_path": str(source),
        "source_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
        "calibration_role": "calibration",
        "status": "adapter_structural_recovered",
        "expected_operator_ids": ["native:buffer", "native:clip"],
        "dependency_edges": [[0, 1]],
    }

    result = audit_row(row)

    assert result["status"] == "accepted_structural_match"
    assert result["dependency_edges"] == [[0, 1]]
    assert result["training_rows_emitted"] == 0


def test_independent_audit_rejects_unfounded_edge(tmp_path: Path) -> None:
    source = tmp_path / "workflow.py"
    source.write_text(
        "import processing\n"
        "first = processing.runalg('native:buffer', roads, 20)\n"
        "processing.runalg('native:clip', another_layer, boundary)\n",
        encoding="utf-8",
    )
    row = {
        "record_id": "fixture",
        "source_path": str(source),
        "source_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
        "calibration_role": "calibration",
        "status": "adapter_structural_recovered",
        "expected_operator_ids": ["native:buffer", "native:clip"],
        "dependency_edges": [[0, 1]],
    }

    result = audit_row(row)

    assert result["status"] == "reject_dependency_edge_mismatch"
    assert result["independent_edges"] == []


def test_independent_audit_accepts_whitelisted_layer_materialization_alias(tmp_path: Path) -> None:
    source = tmp_path / "workflow.py"
    source.write_text(
        "import processing\n"
        "result = processing.runalg('native:buffer', roads, 20)\n"
        "layer = QgsVectorLayer(result['OUTPUT'], 'buffer')\n"
        "processing.runalg('native:clip', layer, boundary)\n",
        encoding="utf-8",
    )
    row = {
        "record_id": "fixture",
        "source_path": str(source),
        "source_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
        "calibration_role": "calibration",
        "status": "adapter_structural_recovered",
        "expected_operator_ids": ["native:buffer", "native:clip"],
        "dependency_edges": [[0, 1]],
    }

    assert audit_row(row)["status"] == "accepted_structural_match"


def test_independent_audit_uses_latest_rebound_result(tmp_path: Path) -> None:
    source = tmp_path / "workflow.py"
    source.write_text(
        "import processing\n"
        "result = processing.runalg('native:buffer', roads, 20)\n"
        "result = processing.runalg('native:clip', result, boundary)\n"
        "processing.runalg('native:dissolve', result)\n",
        encoding="utf-8",
    )
    row = {
        "record_id": "fixture",
        "source_path": str(source),
        "source_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
        "calibration_role": "calibration",
        "status": "adapter_structural_recovered",
        "expected_operator_ids": ["native:buffer", "native:clip", "native:dissolve"],
        "dependency_edges": [[0, 1], [1, 2]],
    }

    assert audit_row(row)["status"] == "accepted_structural_match"


def test_independent_audit_treats_equivalent_edge_order_as_a_match(tmp_path: Path) -> None:
    source = tmp_path / "workflow.py"
    source.write_text(
        "import processing\n"
        "first = processing.runalg('native:buffer', roads, 20)\n"
        "second = processing.runalg('native:clip', first, boundary)\n"
        "processing.runalg('native:dissolve', first, second)\n",
        encoding="utf-8",
    )
    row = {
        "record_id": "fixture",
        "source_path": str(source),
        "source_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
        "calibration_role": "calibration",
        "status": "adapter_structural_recovered",
        "expected_operator_ids": ["native:buffer", "native:clip", "native:dissolve"],
        "dependency_edges": [[1, 2], [0, 1], [0, 2]],
    }

    assert audit_row(row)["status"] == "accepted_structural_match"
