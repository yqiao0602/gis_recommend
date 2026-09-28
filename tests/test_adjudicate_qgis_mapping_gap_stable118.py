from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest


SCRIPT = (
    Path(__file__).resolve().parents[1]
    / "scripts"
    / "adjudicate_qgis_mapping_gap_stable118.py"
)


def _load_module():
    assert SCRIPT.exists(), "stable118 authority freezer is not implemented"
    spec = importlib.util.spec_from_file_location(
        "adjudicate_qgis_mapping_gap_stable118", SCRIPT
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _stable110() -> dict:
    existing = {f"L3_BASE_{index}": index for index in range(108)}
    del existing["L3_BASE_15"]
    existing["L3_02_03_05"] = 15
    return {
        "proposed_taxonomy": "stable110",
        "taxonomy_admission": "granted",
        "existing_code_to_id": existing,
        "proposed_code_to_id_additions": {
            "L3_02_05_16": 108,
            "L3_02_05_17": 109,
        },
    }


def test_freezes_minimum_yield_classes_and_preserves_stable110_tokens() -> None:
    module = _load_module()
    corrected_mapping = {"native:buffer": "L3_BASE_1"}

    authority, extension, mapping, summary = module.freeze_stable118(
        _stable110(), corrected_mapping
    )

    assert {row["operator_id"]: row["l3_code"] for row in authority} == {
        "native:ruggednessindex": "L3_04_02_02",
        "native:setzfromraster": "L3_02_05_18",
        "native:splitlinesbylength": "L3_02_05_19",
        "grass7:r.lake": "L3_04_05_09",
        "native:pointstopath": "L3_02_07_04",
        "native:calculatevectoroverlaps": "L3_02_04_04",
        "native:createpointslayerfromtable": "L3_01_01_04",
        "qgis:basicstatisticsforfields": "L3_01_08_04",
        "native:aggregate": "L3_02_03_05",
    }
    assert extension["proposed_code_to_id_additions"] == {
        "L3_04_02_02": 110,
        "L3_02_05_18": 111,
        "L3_02_05_19": 112,
        "L3_01_08_04": 113,
        "L3_04_05_09": 114,
        "L3_02_07_04": 115,
        "L3_02_04_04": 116,
        "L3_01_01_04": 117,
    }
    assert extension["existing_token_ids_unchanged"] is True
    assert sorted(
        {
            **extension["existing_code_to_id"],
            **extension["proposed_code_to_id_additions"],
        }.values()
    ) == list(range(118))
    assert mapping["native:buffer"] == "L3_BASE_1"
    assert len(mapping) == len(corrected_mapping) + 9
    assert summary["accepted_mapping_count"] == 9
    assert summary["accepted_new_class_count"] == 8
    assert summary["content_token_count"] == 118
    assert summary["training_rows_emitted"] == 0
    assert {row["mapping_admission"] for row in authority} == {"granted"}


def test_rejects_operator_or_code_collisions() -> None:
    module = _load_module()

    with pytest.raises(ValueError, match="operator already mapped"):
        module.freeze_stable118(
            _stable110(), {"native:ruggednessindex": "L3_WRONG"}
        )

    stable110 = _stable110()
    stable110["existing_code_to_id"]["L3_04_02_02"] = 0
    with pytest.raises(ValueError, match="stable118 code already exists"):
        module.freeze_stable118(stable110, {})
