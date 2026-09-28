from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest


SCRIPT = (
    Path(__file__).resolve().parents[1]
    / "scripts"
    / "adjudicate_qgis_mapping_gap_stable120.py"
)


def _load_module():
    assert SCRIPT.exists(), "stable120 authority freezer is not implemented"
    spec = importlib.util.spec_from_file_location(
        "adjudicate_qgis_mapping_gap_stable120", SCRIPT
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _stable118() -> dict:
    existing = {f"L3_BASE_{index}": index for index in range(110)}
    del existing["L3_BASE_67"]
    existing["L3_07_04_01"] = 67
    return {
        "proposed_taxonomy": "stable118",
        "taxonomy_admission": "granted",
        "existing_code_to_id": existing,
        "proposed_code_to_id_additions": {
            f"L3_STABLE118_{index}": 110 + index for index in range(8)
        },
    }


def test_freezes_two_exact_classes_and_one_existing_l3_alias() -> None:
    module = _load_module()
    mapping = {
        "native:buffer": "L3_BASE_1",
        "native:savefeatures": "L3_07_04_01",
    }

    authority, extension, composed, summary = module.freeze_stable120(
        _stable118(), mapping
    )

    assert {row["operator_id"]: row["l3_code"] for row in authority} == {
        "native:createspatialindex": "L3_01_07_01",
        "native:saveselectedfeatures": "L3_07_04_01",
        "native:snapgeometries": "L3_02_07_09",
    }
    assert extension["proposed_code_to_id_additions"] == {
        "L3_01_07_01": 118,
        "L3_02_07_09": 119,
    }
    assert sorted(
        {
            **extension["existing_code_to_id"],
            **extension["proposed_code_to_id_additions"],
        }.values()
    ) == list(range(120))
    assert composed["native:savefeatures"] == "L3_07_04_01"
    assert composed["native:saveselectedfeatures"] == "L3_07_04_01"
    assert summary["accepted_new_class_count"] == 2
    assert summary["accepted_mapping_count"] == 3
    assert summary["content_token_count"] == 120
    assert summary["training_rows_emitted"] == 0


def test_rejects_existing_operator_mapping_collision() -> None:
    module = _load_module()

    with pytest.raises(ValueError, match="operator already mapped"):
        module.freeze_stable120(
            _stable118(), {"native:createspatialindex": "L3_WRONG"}
        )
