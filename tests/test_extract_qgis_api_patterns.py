from __future__ import annotations

import csv
import importlib.util
from pathlib import Path


def _load():
    path = Path(__file__).resolve().parents[1] / "scripts" / "extract_qgis_api_patterns.py"
    spec = importlib.util.spec_from_file_location("extract_qgis_api_patterns", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_api_pattern_requires_multiple_signals_and_boundary(tmp_path: Path) -> None:
    module = _load()
    path = tmp_path / "workflow_steps.csv"
    fields = ["name", "normalized_api_name", "semantic_role", "input_type", "output_type"]
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows([
            {"name": "QgsVectorLayer", "normalized_api_name": "qgsvectorlayer", "semantic_role": "", "input_type": "vector", "output_type": "vector"},
            {"name": "geometry", "normalized_api_name": "qgsfeature.geometry", "semantic_role": "", "input_type": "vector", "output_type": "vector"},
            {"name": "QgsCoordinateTransform", "normalized_api_name": "qgscoordinatetransform", "semantic_role": "", "input_type": "vector", "output_type": "vector"},
        ])
    row = module.extract_file(path)
    assert row["status"] == "pattern_candidate"
    assert "vector_layer_io" in row["pattern_names"]
    assert "feature_geometry" in row["pattern_names"]
    assert row["training_row_emitted"] is False


def test_api_pattern_single_signal_is_deferred(tmp_path: Path) -> None:
    module = _load()
    path = tmp_path / "weak_steps.csv"
    path.write_text("name,normalized_api_name,semantic_role,input_type,output_type\nQgsVectorLayer,qgsvectorlayer,,,\n", encoding="utf-8")
    row = module.extract_file(path)
    assert row["status"] == "deferred_insufficient_task_boundary"
    assert row["candidate_l3_sequence"] == []
