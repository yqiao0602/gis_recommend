from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest


SCRIPT = (
    Path(__file__).resolve().parents[1]
    / "scripts"
    / "adjudicate_qgis_mapping_gap_stable121.py"
)
SPEC = importlib.util.spec_from_file_location(
    "adjudicate_qgis_mapping_gap_stable121", SCRIPT
)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def _extension() -> dict:
    codes = {f"L3_{index:03d}": index for index in range(119)}
    del codes["L3_102"]
    codes["L3_01_05_04"] = 102
    return {
        "proposed_taxonomy": "stable120",
        "taxonomy_admission": "granted",
        "existing_code_to_id": codes,
        "proposed_code_to_id_additions": {"L3_02_07_09": 119},
    }


def _support(value: int = 30) -> dict:
    return {
        "candidate_support": {
            "native:removeduplicatesbyattribute": {
                "candidate_l3_code": "L3_01_05_04",
                "normalized_source_body_support": value,
                "support_gate": 30,
                "support_gate_passed": value >= 30,
            },
            "qgis:voronoipolygons": {
                "candidate_l3_code": "L3_02_07_07",
                "normalized_source_body_support": value,
                "support_gate": 30,
                "support_gate_passed": value >= 30,
            },
        }
    }


def test_freezes_one_new_class_and_one_existing_l3_alias() -> None:
    extension = _extension()
    base_mapping = {"native:existing": "L3_000"}

    authority, stable121, mapping, summary = MODULE.freeze_stable121(
        extension, base_mapping, _support()
    )

    assert stable121["proposed_code_to_id_additions"] == {
        "L3_02_07_09": 119,
        "L3_02_07_07": 120,
    }
    assert mapping["qgis:voronoipolygons"] == "L3_02_07_07"
    assert mapping["native:removeduplicatesbyattribute"] == "L3_01_05_04"
    assert summary["accepted_new_class_count"] == 1
    assert summary["accepted_existing_l3_alias_count"] == 1
    assert {row["authority_kind"] for row in authority} == {
        "minimum_exact_l3_extension",
        "existing_l3_alias",
    }


def test_rejects_support_below_gate() -> None:
    extension = _extension()

    with pytest.raises(ValueError, match="support gate"):
        MODULE.freeze_stable121(extension, {}, _support(29))
