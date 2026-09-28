from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest


SCRIPT = (
    Path(__file__).resolve().parents[1]
    / "scripts"
    / "adjudicate_qgis_mapping_gap_stable124.py"
)


def _load_module():
    assert SCRIPT.exists(), "stable124 authority freezer is not implemented"
    spec = importlib.util.spec_from_file_location(
        "adjudicate_qgis_mapping_gap_stable124", SCRIPT
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _stable121() -> dict:
    existing = {f"L3_BASE_{index}": index for index in range(118)}
    return {
        "proposed_taxonomy": "stable121",
        "taxonomy_admission": "granted",
        "existing_code_to_id": existing,
        "proposed_code_to_id_additions": {
            "L3_01_07_01": 118,
            "L3_02_07_09": 119,
            "L3_02_07_07": 120,
        },
    }


def _support(*, failures: int = 0) -> dict:
    return {
        "source_authority_failures": failures,
        "candidate_support": {
            "native:reverselinedirection": {
                "candidate_l3_code": "L3_02_05_09",
                "normalized_source_body_support": 12,
                "unique_source_sha256": 20,
            },
            "native:splitvectorlayer": {
                "candidate_l3_code": "L3_02_06_04",
                "normalized_source_body_support": 22,
                "unique_source_sha256": 40,
            },
            "qgis:definecurrentprojection": {
                "candidate_l3_code": "L3_01_10_02",
                "normalized_source_body_support": 11,
                "unique_source_sha256": 23,
            },
        },
    }


def test_freezes_three_exact_provider_contract_classes() -> None:
    module = _load_module()

    authority, extension, mapping, summary = module.freeze_stable124(
        _stable121(), {"native:existing": "L3_BASE_1"}, _support()
    )

    assert extension["proposed_code_to_id_additions"] == {
        "L3_01_07_01": 118,
        "L3_02_07_09": 119,
        "L3_02_07_07": 120,
        "L3_01_10_02": 121,
        "L3_02_05_09": 122,
        "L3_02_06_04": 123,
    }
    assert {row["operator_id"]: row["l3_code"] for row in authority} == {
        "native:reverselinedirection": "L3_02_05_09",
        "native:splitvectorlayer": "L3_02_06_04",
        "qgis:definecurrentprojection": "L3_01_10_02",
    }
    assert mapping["native:splitvectorlayer"] == "L3_02_06_04"
    assert summary["accepted_new_class_count"] == 3
    assert summary["content_token_count"] == 124


def test_rejects_any_source_authority_failure() -> None:
    module = _load_module()

    with pytest.raises(ValueError, match="source authority"):
        module.freeze_stable124(_stable121(), {}, _support(failures=1))
