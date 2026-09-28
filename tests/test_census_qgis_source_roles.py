from scripts.census_qgis_source_roles import classify_source


def row(path: str = "script.py") -> dict:
    return {"source_path": path, "source_root_id": ""}


def test_processing_implementation_is_not_user_workflow() -> None:
    source = """
from qgis.core import QgsProcessingAlgorithm
class A(QgsProcessingAlgorithm):
    def processAlgorithm(self, parameters, context, feedback):
        processing.run('native:buffer', {'INPUT': parameters['INPUT']})
        processing.run('native:clip', {'INPUT': 'x'})
"""
    result = classify_source(row(), source)
    assert result["source_role"] == "processing_implementation"
    assert result["processing_run_count"] == 2


def test_standalone_processing_script_is_user_workflow() -> None:
    result = classify_source(row(), "processing.run('native:buffer', {'INPUT': layer})")
    assert result["source_role"] == "user_workflow"
    assert result["task_semantic_signal"] is True


def test_api_semantic_operation_has_task_signal() -> None:
    result = classify_source(row(), '"""Compute centroid of parcels"""\npoint = feature.geometry().centroid()')
    assert result["source_role"] == "api_semantic_operation"
    assert result["api_semantic_methods"] == ["centroid"]
    assert result["task_semantic_signal"] is True


def test_api_plumbing_is_not_semantic_workflow() -> None:
    result = classify_source(row(), "provider = layer.dataProvider()\nprovider.addFeatures([feature])")
    assert result["source_role"] == "api_plumbing"
    assert result["api_plumbing_methods"] == ["addfeatures", "dataprovider"]


def test_model_marker_takes_precedence() -> None:
    result = classify_source(row("workflow.model3"), "processing.run('native:buffer', {})")
    assert result["source_role"] == "user_workflow"
    assert result["classification_basis"] == "model_or_history_marker"
