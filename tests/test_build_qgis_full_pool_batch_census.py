from __future__ import annotations

import importlib.util
from pathlib import Path


def _load(name: str):
    path = Path(__file__).resolve().parents[1] / "scripts" / f"{name}.py"
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_full_pool_census_requires_8466_verified_rows() -> None:
    module = _load("build_qgis_full_pool_batch_census")
    result = module.build_census(
        {"input_processing_resolution_records": 8466, "verified_source_records": 8466, "primary_layer_counts": {}},
        {"input_rows": 3163, "mapping_complete_rows": 775, "action_counts": {}},
    )
    assert result["input_rows"] == 8466
    assert result["batch_gate"]["training_rows_emitted"] == 0
    assert result["batch_gate"]["production_merge"] == "not_granted"


def test_full_pool_census_rejects_wrong_authority_size() -> None:
    module = _load("build_qgis_full_pool_batch_census")
    try:
        module.build_census({"input_processing_resolution_records": 10, "verified_source_records": 10}, {})
    except ValueError:
        return
    raise AssertionError("wrong authority size must fail closed")
